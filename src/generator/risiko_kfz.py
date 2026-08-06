"""Kfz-Risiko — nur in den Sparten 051, 052 und 053.

Die abgeleiteten Fahrzeugmerkmale werden **aus dem Referenzeintrag uebernommen**
und nicht neu gewuerfelt: ``leistung_kw``, ``antriebsart``, ``neupreis_eur`` und
die Typklassen stammen aus der Zeile zu (``hsn``, ``tsn``) in ``typklassen.csv``
(Grundlage von R-051), die Regionalklassen aus dem Eintrag zum
``zulassungsbezirk`` in ``regionalklassen.csv`` (R-058).

Die Kette der zeitlichen Abhaengigkeiten wird von unten nach oben aufgebaut:
Geburtsdatum bestimmt die Obergrenze des Fuehrerscheintags, dieser zusammen mit
dem Alter die Obergrenze der Schadenfreiheitsklasse (R-029), die Erstzulassung
die Untergrenze der Zulassung auf den Versicherungsnehmer (R-027).

Zweckbindung nach spec/01, Abschnitt 3.3: ``typklasse_tk`` nur bei Teil- oder
Vollkasko, ``typklasse_vk`` und ``sf_klasse_vk`` nur bei Vollkasko. Die
Regionalklassen sind dort ausdruecklich **nicht** eingeschraenkt und deshalb
immer gefuellt.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Final

import numpy as np

from src.common import wertebereiche as wb
from src.common.enums import (
    SF_KLASSEN_NUMERISCH,
    SF_KLASSEN_SONDER,
    SF_MAX_NUMERISCH,
    WAGNISKENNZIFFER_PKW,
    Abstellplatz,
    Antriebsart,
    ArtKennzeichen,
    Eigentumsverhaeltnis,
    Nutzerkreis,
    Nutzungsart,
    Sparte,
    schadenfreie_jahre,
    sf_ordnung,
)
from src.common.geld import runde, zu_decimal
from src.common.serialisierung import typisierter_rahmen
from src.generator.verteilungen import (
    datum_plus_jahre,
    erzeuge_uuids,
    jahre_zwischen,
    waehle_index,
    ziehe_ganzzahl_lognormal,
    ziehe_lognormal,
    ziehe_wahrheit,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence

    import pandas as pd
    from numpy.random import Generator

    from src.common.config import Config

__all__ = ["RisikoKfz", "erzeuge_risiko_kfz"]

#: Fahrzeugalter zum Stichtag: log-normal um sechs Jahre.
#:
#: Strukturvorbild: Altersstruktur des PKW-Bestands, wie sie auch dem Datensatz
#: freMTPL2freq zugrunde liegt. **Modellannahme.**
_FAHRZEUGALTER_MEDIAN_JAHRE: Final[float] = 6.0
_FAHRZEUGALTER_SIGMA: Final[float] = 0.70
_FAHRZEUGALTER_MAX_JAHRE: Final[int] = 30

#: Tage eines mittleren Jahres, fuer die Umrechnung des Fahrzeugalters.
_TAGE_JE_JAHR: Final[float] = 365.25

#: Jahresfahrleistung: log-normal um 12.000 km (spec/01, Abschnitt 3.3).
_FAHRLEISTUNG_MEDIAN: Final[float] = 12_000.0
_FAHRLEISTUNG_SIGMA: Final[float] = 0.45
_FAHRLEISTUNG_SCHRITT: Final[int] = 500

#: Restwertkurve: jaehrlicher Wertverlust und Restwertuntergrenze (Modellannahme).
_WERTVERLUST_JE_JAHR: Final[float] = 0.16
_RESTWERT_UNTERGRENZE: Final[float] = 0.10
_RESTWERT_STREUUNG: Final[float] = 0.10

#: Wahrscheinlichkeit, dass das Fahrzeug direkt bei Erstzulassung auf den
#: Versicherungsnehmer zugelassen wurde (Neuwagenkauf).
_P_ERSTHALTER: Final[float] = 0.45

#: Wahrscheinlichkeit eines E-Kennzeichens bei elektrischem oder hybridem Antrieb.
_P_E_KENNZEICHEN: Final[float] = 0.40

#: Wahrscheinlichkeit eines Saisonkennzeichens bei allen uebrigen Antrieben.
_P_SAISONKENNZEICHEN: Final[float] = 0.07

#: Nutzungsart mit Gewichten (Modellannahme).
_NUTZUNGSART_GEWICHTE: Final[tuple[tuple[Nutzungsart, float], ...]] = (
    (Nutzungsart.PRIVAT, 0.855),
    (Nutzungsart.GESCHAEFTLICH, 0.090),
    (Nutzungsart.GEMISCHT, 0.050),
    (Nutzungsart.TAXI, 0.005),
)

#: Eigentumsverhaeltnis mit Gewichten (Modellannahme).
_EIGENTUM_GEWICHTE: Final[tuple[tuple[Eigentumsverhaeltnis, float], ...]] = (
    (Eigentumsverhaeltnis.EIGENTUM_VN, 0.82),
    (Eigentumsverhaeltnis.LEASING, 0.18),
)

#: Nutzerkreis mit Gewichten (Modellannahme).
_NUTZERKREIS_GEWICHTE: Final[tuple[tuple[Nutzerkreis, float], ...]] = (
    (Nutzerkreis.VN, 0.45),
    (Nutzerkreis.VN_PARTNER, 0.32),
    (Nutzerkreis.VN_FAMILIE, 0.15),
    (Nutzerkreis.BELIEBIG, 0.08),
)

#: Abstellplatz mit Gewichten (Modellannahme).
_ABSTELLPLATZ_GEWICHTE: Final[tuple[tuple[Abstellplatz, float], ...]] = (
    (Abstellplatz.GARAGE, 0.35),
    (Abstellplatz.STRASSE, 0.35),
    (Abstellplatz.STELLPLATZ, 0.20),
    (Abstellplatz.CARPORT, 0.10),
)

#: Zahl der Schaeden in fuenf Jahren, stark rechtsschief (spec/01, Abschnitt 3.3).
_SCHADEN_GEWICHTE: Final[tuple[float, ...]] = (0.720, 0.180, 0.060, 0.025, 0.010, 0.005)

#: Gewichte der Sonderklassen; der Rest entfaellt auf die numerischen Klassen.
_SF_SONDER_GEWICHTE: Final[Mapping[str, float]] = {
    "M": 0.008,
    "S": 0.012,
    "0": 0.020,
    "1/2": 0.015,
}

#: Formparameter der Beta-Verteilung, die die Schadenfreiheitsklasse an ihre
#: Obergrenze heranfuehrt: die meisten Fahrer sind nahe am moeglichen Maximum.
_SF_BETA_A: Final[float] = 3.0
_SF_BETA_B: Final[float] = 1.2

#: Vollstaendige Ordnung der SF-Klassen (spec/01, Abschnitt 2.8), aufsteigend.
_SF_REIHENFOLGE: Final[tuple[str, ...]] = ("M", "S", "0", "1/2", *SF_KLASSEN_NUMERISCH)

#: Abstand der Vollkaskoklasse zur Haftpflichtklasse mit seinen Gewichten.
#:
#: Der Abstand ist nie negativ; damit gilt ``sf_ordnung(vk) <= sf_ordnung(hp)``
#: (R-030) auch dann, wenn eine der beiden Klassen eine Sonderklasse ist.
_SF_VK_ABSTAND_GEWICHTE: Final[tuple[float, float, float, float]] = (0.75, 0.13, 0.08, 0.04)

#: Streuung des Partneralters um das Alter des Versicherungsnehmers, in Jahren.
_PARTNERALTER_SIGMA: Final[float] = 5.0

#: Sparten mit Kaskodeckung.
_KASKOSPARTEN: Final[frozenset[str]] = frozenset(
    {Sparte.KFZ_VOLLKASKO.value, Sparte.KFZ_TEILKASKO.value}
)

#: Schadenfreiheitsklassen, die in der Kasko nicht angenommen werden.
#:
#: Malus- und Schadenklasse. Begruendung in :func:`_wirksame_sparte`.
_KEINE_KASKO_ANNAHME: Final[frozenset[str]] = frozenset({"M", "S"})

#: Niedrigste in der Kasko annehmbare Einstufung, als Position in
#: :data:`_SF_REIHENFOLGE`. Alles darunter sind die nicht angenommenen Klassen.
_SF_KASKO_UNTERGRENZE: Final[int] = len(_KEINE_KASKO_ANNAHME)


@dataclass(frozen=True, slots=True)
class RisikoKfz:
    """Kfz-Risiken samt der fuer die Beitragsberechnung gebrauchten Groessen.

    Alle Folgen sind ueber die Position der Kfz-Anfrage indiziert, nicht ueber den
    Index in der Gesamtmenge der Anfragen.

    Attributes:
        rahmen: Die Entitaet ``risiko_kfz``.
        sparte: **Wirksame** Sparte je Kfz-Anfrage nach der Annahmebedingung
            (siehe :func:`_wirksame_sparte`). Sie kann von der gezogenen Sparte
            abweichen und ist ab hier massgeblich.
        sf_klasse_hp: Schadenfreiheitsklasse der Haftpflicht je Kfz-Anfrage.
        beitrags_sf_klasse: Klasse, deren Beitragssatz in die Berechnung eingeht;
            ``None`` in der Teilkasko, die keine eigene Einstufung kennt.
        typklasse: Fuer die Sparte massgebliche Typklasse je Kfz-Anfrage.
        regionalklasse: Fuer die Sparte massgebliche Regionalklasse je Kfz-Anfrage.
        jahresfahrleistung_km: Fahrleistung je Kfz-Anfrage.
    """

    rahmen: pd.DataFrame
    sparte: tuple[str, ...]
    sf_klasse_hp: tuple[str, ...]
    beitrags_sf_klasse: tuple[str | None, ...]
    typklasse: tuple[int, ...]
    regionalklasse: tuple[int, ...]
    jahresfahrleistung_km: tuple[int, ...]


def _wirksame_sparte(gezogene_sparte: str, sf_klasse_hp: str) -> str:
    """Wendet die Annahmebedingung der Kaskosparten an.

    **Fachliche Grundlage.** Versicherer nehmen Risiken in der Malusklasse (``M``)
    oder in der Schadenklasse (``S``) in der Kasko ueberwiegend gar nicht an. In
    der Haftpflicht besteht dagegen Kontrahierungszwang (Paragraf 5 PflVG), und
    die beiden Klassen sind dort fachlich relevant.

    Eine solche Anfrage bekommt deshalb kein Kaskoangebot, sondern wird als
    Haftpflichtanfrage gefuehrt. Das ist eine **Annahmebedingung**, kein
    nachtraegliches Filtern: Es entstehen erst gar keine Kaskoangebote fuer diese
    Risiken.

    Ohne diese Bedingung entsteht im Modell eine Konstellation, die es im Markt
    nicht gibt: Beitragssatz 245 Prozent mal hoher Typ- und Regionalklasse ergibt
    Vollkaskobeitraege jenseits von 20.000 Euro im Jahr.

    Args:
        gezogene_sparte: Die in der Anfrage gezogene Sparte.
        sf_klasse_hp: Schadenfreiheitsklasse der Haftpflicht.

    Returns:
        Die wirksame Sparte; ``051`` statt ``052``/``053``, wenn die
        Annahmebedingung greift, sonst die gezogene Sparte unveraendert.
    """
    if gezogene_sparte in _KASKOSPARTEN and sf_klasse_hp in _KEINE_KASKO_ANNAHME:
        return Sparte.KFZ_HAFTPFLICHT.value
    return gezogene_sparte


def _ziehe_sf_klassen(rng: Generator, obergrenzen: Sequence[int]) -> list[str]:
    """Zieht Schadenfreiheitsklassen, die R-029 erfuellen.

    Args:
        rng: Zufallsgenerator.
        obergrenzen: Hoechste zulaessige Zahl schadenfreier Jahre je Zeile.

    Returns:
        Die Klassen als Zeichenketten aus dem Katalog.
    """
    anzahl = len(obergrenzen)
    sondernamen = tuple(_SF_SONDER_GEWICHTE)
    gewicht_sonder = sum(_SF_SONDER_GEWICHTE.values())
    ist_sonder = ziehe_wahrheit(rng, [gewicht_sonder] * anzahl)
    sonderwahl = waehle_index(rng, anzahl, [_SF_SONDER_GEWICHTE[name] for name in sondernamen])
    naehe = rng.beta(_SF_BETA_A, _SF_BETA_B, size=anzahl)

    klassen: list[str] = []
    for index, roh_obergrenze in enumerate(obergrenzen):
        # Der Katalog endet bei SF 50; ein 80-Jaehriger koennte rechnerisch 63
        # schadenfreie Jahre vorweisen, die Klasse dazu gibt es aber nicht (R-013).
        obergrenze = min(roh_obergrenze, SF_MAX_NUMERISCH)
        if obergrenze < 1 or ist_sonder[index]:
            klassen.append(sondernamen[int(sonderwahl[index])])
            continue
        stufe = round(float(naehe[index]) * obergrenze)
        klassen.append(f"SF{min(max(stufe, 1), obergrenze)}")
    return klassen


def _ziehe_sf_vollkasko(rng: Generator, haftpflicht: Sequence[str]) -> list[str]:
    """Zieht die Vollkaskoklasse; sie ist nie besser eingestuft als die Haftpflicht (R-030).

    Der Abstand zur Haftpflichtklasse ist nie negativ, die Klasse faellt aber
    nicht unter die niedrigste in der Kasko annehmbare Einstufung: Malus und
    Schadenklasse sind hier ausgeschlossen. Andernfalls unterliefe die Ziehung
    die Annahmebedingung aus :func:`_wirksame_sparte` — eine Anfrage mit
    Haftpflichtklasse ``0`` bekaeme eine Vollkaskoklasse ``M``, und der
    Beitragssatz von 245 Prozent waere ueber den Umweg der Kaskoeinstufung
    wieder im Datensatz.
    """
    abstaende = waehle_index(rng, len(haftpflicht), list(_SF_VK_ABSTAND_GEWICHTE))
    return [
        _SF_REIHENFOLGE[
            max(_SF_REIHENFOLGE.index(klasse) - int(abstaende[index]), _SF_KASKO_UNTERGRENZE)
        ]
        for index, klasse in enumerate(haftpflicht)
    ]


def _ziehe_erstzulassung(rng: Generator, anzahl: int, stichtag: dt.date) -> list[dt.date]:
    """Zieht die Erstzulassung aus der Altersstruktur des Fahrzeugbestands."""
    alter = ziehe_lognormal(rng, anzahl, _FAHRZEUGALTER_MEDIAN_JAHRE, _FAHRZEUGALTER_SIGMA)
    tage = np.clip(alter, 0.0, float(_FAHRZEUGALTER_MAX_JAHRE)) * _TAGE_JE_JAHR
    fruehestens = wb.ERSTZULASSUNG_FRUEHESTENS
    ergebnis: list[dt.date] = []
    for versatz in tage:
        tag = stichtag - dt.timedelta(days=int(versatz))
        ergebnis.append(max(tag, fruehestens))
    return ergebnis


def _ziehe_zulassung_auf_vn(
    rng: Generator,
    erstzulassungen: Sequence[dt.date],
    geburtsdaten: Sequence[dt.date | None],
    stichtag: dt.date,
) -> list[dt.date]:
    """Zieht den Tag der Zulassung auf den Versicherungsnehmer.

    Untergrenze ist die Erstzulassung und zugleich der 18. Geburtstag
    (spec/01, Abschnitt 3.3), Obergrenze der Stichtag.
    """
    ersthalter = ziehe_wahrheit(rng, [_P_ERSTHALTER] * len(erstzulassungen))
    anteile = rng.random(len(erstzulassungen))
    ergebnis: list[dt.date] = []
    for index, erstzulassung in enumerate(erstzulassungen):
        untergrenze = erstzulassung
        geburtsdatum = geburtsdaten[index]
        if geburtsdatum is not None:
            untergrenze = max(untergrenze, datum_plus_jahre(geburtsdatum, 18))
        untergrenze = min(untergrenze, stichtag)
        spanne = (stichtag - untergrenze).days
        versatz = 0 if ersthalter[index] else int(float(anteile[index]) * (spanne + 1))
        ergebnis.append(untergrenze + dt.timedelta(days=min(versatz, spanne)))
    return ergebnis


def _fahrzeugwerte(
    rng: Generator,
    neupreise: Sequence[Decimal],
    erstzulassungen: Sequence[dt.date],
    stichtag: dt.date,
) -> list[Decimal]:
    """Bildet den aktuellen Fahrzeugwert ueber eine Restwertkurve (R-038).

    Der Restwert faellt exponentiell mit dem Fahrzeugalter, hat eine Untergrenze
    und ist nie groesser als der Neupreis.
    """
    streuung = np.exp(rng.normal(0.0, _RESTWERT_STREUUNG, size=len(neupreise)))
    werte: list[Decimal] = []
    for index, neupreis in enumerate(neupreise):
        alter = (stichtag - erstzulassungen[index]).days / _TAGE_JE_JAHR
        faktor = max(float(np.exp(-_WERTVERLUST_JE_JAHR * alter)), _RESTWERT_UNTERGRENZE)
        faktor = min(faktor * float(streuung[index]), 1.0)
        werte.append(runde(zu_decimal(neupreis) * Decimal(repr(faktor))))
    return werte


def _art_kennzeichen(rng: Generator, antriebsarten: Sequence[str]) -> list[str]:
    """Zieht die Kennzeichenart; ``54`` setzt einen elektrischen Antrieb voraus (R-039)."""
    elektrisch = {Antriebsart.ELEKTRO.value, Antriebsart.HYBRID.value}
    ist_elektrisch = [antrieb in elektrisch for antrieb in antriebsarten]
    e_kennzeichen = ziehe_wahrheit(
        rng, [_P_E_KENNZEICHEN if wert else 0.0 for wert in ist_elektrisch]
    )
    saison = ziehe_wahrheit(rng, [_P_SAISONKENNZEICHEN] * len(antriebsarten))
    ergebnis: list[str] = []
    for index in range(len(antriebsarten)):
        if e_kennzeichen[index]:
            ergebnis.append(ArtKennzeichen.ELEKTRO.value)
        elif saison[index]:
            ergebnis.append(ArtKennzeichen.SAISON.value)
        else:
            ergebnis.append(ArtKennzeichen.NORMAL.value)
    return ergebnis


def _alter_juengster_fahrer(
    rng: Generator, nutzerkreise: Sequence[str], vn_alter: Sequence[int]
) -> list[int]:
    """Zieht das Alter des juengsten Fahrers; es liegt nie ueber dem Alter des VN."""
    untergrenze = wb.ALTER_JUENGSTER_FAHRER[0]
    abweichung = np.abs(rng.normal(0.0, _PARTNERALTER_SIGMA, size=len(nutzerkreise)))
    anteile = rng.random(len(nutzerkreise))
    ergebnis: list[int] = []
    for index, kreis in enumerate(nutzerkreise):
        alter = vn_alter[index]
        if kreis == Nutzerkreis.VN.value:
            ergebnis.append(alter)
        elif kreis == Nutzerkreis.VN_PARTNER.value:
            ergebnis.append(max(alter - int(abweichung[index]), untergrenze))
        else:
            spanne = alter - untergrenze
            ergebnis.append(untergrenze + int(float(anteile[index]) * (spanne + 1)))
    return [min(wert, vn_alter[index]) for index, wert in enumerate(ergebnis)]


def _jahre_seit_fuehrerschein(fuehrerschein: dt.date | None, stichtag: dt.date) -> int:
    """Gibt die Jahre seit dem Fuehrerscheinerwerb zurueck; ohne Schein sind es null."""
    if fuehrerschein is None:
        return 0
    return jahre_zwischen(fuehrerschein, stichtag)


def _kategorie(rng: Generator, anzahl: int, katalog: Sequence[tuple[object, float]]) -> list[str]:
    """Zieht Enum-Werte nach Gewichten und gibt ihre Zeichenketten zurueck."""
    indizes = waehle_index(rng, anzahl, [gewicht for _, gewicht in katalog])
    return [str(katalog[int(index)][0]) for index in indizes]


def _regionalklassen_je_zeile(
    regionalklassen: pd.DataFrame, zulassungsbezirke: Sequence[str]
) -> dict[str, list[int]]:
    """Schlaegt die drei Regionalklassen je Zulassungsbezirk nach (R-058).

    Raises:
        ValueError: Wenn ein Zulassungsbezirk in der Referenz fehlt. Bewusst kein
            Ersatzwert: Ein erfundener Wert wuerde R-058 auf sauberen Daten
            verletzen.
    """
    tabelle = regionalklassen.set_index("zulassungsbezirk")
    fehlend = sorted(set(zulassungsbezirke) - set(tabelle.index))
    if fehlend:
        raise ValueError(f"Zulassungsbezirke fehlen in regionalklassen.csv: {fehlend[:5]}")
    zeilen = tabelle.reindex(list(zulassungsbezirke))
    return {
        name: [int(wert) for wert in zeilen[name]]
        for name in ("regionalklasse_hp", "regionalklasse_tk", "regionalklasse_vk")
    }


def erzeuge_risiko_kfz(  # noqa: PLR0913 - Referenz, Person und Sparte gehen getrennt ein
    config: Config,
    rng: Generator,
    *,
    anfrage_ids: Sequence[str],
    sparten: Sequence[str],
    zulassungsbezirke: Sequence[str],
    vn_alter: Sequence[int],
    vn_geburtsdatum: Sequence[dt.date | None],
    vn_fuehrerschein: Sequence[dt.date | None],
    typklassen: pd.DataFrame,
    regionalklassen: pd.DataFrame,
) -> RisikoKfz:
    """Erzeugt die Kfz-Risiken der Kfz-Anfragen.

    Args:
        config: Geladene Konfiguration; liefert den Stichtag.
        rng: Zufallsgenerator des Teilstroms "Risiko Kfz".
        anfrage_ids: Kennung je Kfz-Anfrage.
        sparten: Spartenschluessel je Kfz-Anfrage.
        zulassungsbezirke: Zulassungsbezirk je Kfz-Anfrage, aus der Postleitzahl.
        vn_alter: Alter des Versicherungsnehmers je Kfz-Anfrage.
        vn_geburtsdatum: Geburtsdatum des Versicherungsnehmers je Kfz-Anfrage.
        vn_fuehrerschein: Fuehrerscheintag des Versicherungsnehmers je Kfz-Anfrage.
        typklassen: Referenztabelle ``typklassen``.
        regionalklassen: Referenztabelle ``regionalklassen``.

    Returns:
        Das :class:`RisikoKfz` mit Datenrahmen und Beitragsgroessen.
    """
    stichtag = config.stichtag
    anzahl = len(anfrage_ids)
    fahrzeuge = rng.integers(0, len(typklassen), size=anzahl)
    referenz = typklassen.iloc[fahrzeuge].reset_index(drop=True)
    regional = _regionalklassen_je_zeile(regionalklassen, zulassungsbezirke)
    typ = {
        name: [int(wert) for wert in referenz[name]]
        for name in ("typklasse_hp", "typklasse_tk", "typklasse_vk")
    }
    hsn_werte = [str(wert) for wert in referenz["hsn"]]
    tsn_werte = [str(wert) for wert in referenz["tsn"]]
    leistungen = [int(wert) for wert in referenz["leistung_kw"]]

    erstzulassungen = _ziehe_erstzulassung(rng, anzahl, stichtag)
    zulassungen = _ziehe_zulassung_auf_vn(rng, erstzulassungen, vn_geburtsdatum, stichtag)
    neupreise = [zu_decimal(wert) for wert in referenz["neupreis_eur"]]
    fahrzeugwerte = _fahrzeugwerte(rng, neupreise, erstzulassungen, stichtag)
    antriebsarten = [str(wert) for wert in referenz["antriebsart"]]
    kennzeichen = _art_kennzeichen(rng, antriebsarten)

    fahrleistungen = ziehe_ganzzahl_lognormal(
        rng,
        anzahl,
        median=_FAHRLEISTUNG_MEDIAN,
        sigma=_FAHRLEISTUNG_SIGMA,
        unten=wb.GENERATOR_JAHRESFAHRLEISTUNG_KM[0],
        oben=wb.GENERATOR_JAHRESFAHRLEISTUNG_KM[1],
        schrittweite=_FAHRLEISTUNG_SCHRITT,
    )
    nutzungsarten = _kategorie(rng, anzahl, _NUTZUNGSART_GEWICHTE)
    eigentum = _kategorie(rng, anzahl, _EIGENTUM_GEWICHTE)
    nutzerkreise = _kategorie(rng, anzahl, _NUTZERKREIS_GEWICHTE)
    abstellplaetze = _kategorie(rng, anzahl, _ABSTELLPLATZ_GEWICHTE)
    juengste_fahrer = _alter_juengster_fahrer(rng, nutzerkreise, vn_alter)
    schaeden = waehle_index(rng, anzahl, list(_SCHADEN_GEWICHTE))

    # Obergrenze der Schadenfreiheitsklasse: R-029 verlangt hoechstens Alter minus
    # 17. Der Fuehrerscheinbesitz ist die schaerfere und fachlich richtige Grenze —
    # laenger als seit dem Erwerb kann niemand schadenfrei gefahren sein.
    obergrenzen = [
        min(
            vn_alter[index] - wb.FUEHRERSCHEIN_MINDESTALTER_JAHRE,
            _jahre_seit_fuehrerschein(vn_fuehrerschein[index], stichtag),
        )
        for index in range(anzahl)
    ]
    sf_hp = _ziehe_sf_klassen(rng, obergrenzen)
    sf_vk_alle = _ziehe_sf_vollkasko(rng, sf_hp)
    risiko_ids = erzeuge_uuids(rng, anzahl)

    # Annahmebedingung der Kaskosparten: Malus- und Schadenklasse werden dort
    # nicht angenommen und als Haftpflichtanfrage gefuehrt. Ab hier ist
    # ausschliesslich die wirksame Sparte massgeblich.
    wirksam = [
        _wirksame_sparte(sparten[index], sf_hp[index]) for index in range(anzahl)
    ]
    vollkasko = [sparte == Sparte.KFZ_VOLLKASKO.value for sparte in wirksam]
    teilkasko = [sparte == Sparte.KFZ_TEILKASKO.value for sparte in wirksam]

    spalten: dict[str, list[object]] = {
        "row_id": list(range(1, anzahl + 1)),
        "risiko_id": list(risiko_ids),
        "anfrage_id": list(anfrage_ids),
        "hsn": list(hsn_werte),
        "tsn": list(tsn_werte),
        "wagniskennziffer": [WAGNISKENNZIFFER_PKW] * anzahl,
        "erstzulassung": list(erstzulassungen),
        "zulassung_auf_vn": list(zulassungen),
        "leistung_kw": list(leistungen),
        "antriebsart": list(antriebsarten),
        "neupreis_eur": list(neupreise),
        "fahrzeugwert_aktuell": list(fahrzeugwerte),
        "art_kennzeichen": list(kennzeichen),
        "zulassungsbezirk": list(zulassungsbezirke),
        "jahresfahrleistung_km": [int(wert) for wert in fahrleistungen],
        "nutzungsart": list(nutzungsarten),
        "eigentumsverhaeltnis": list(eigentum),
        "nutzerkreis": list(nutzerkreise),
        "alter_juengster_fahrer": list(juengste_fahrer),
        "abstellplatz": list(abstellplaetze),
        "sf_klasse_hp": list(sf_hp),
        # Zweckbindung nach spec/01, Abschnitt 3.3.
        "sf_klasse_vk": _nur_wenn(sf_vk_alle, vollkasko),
        "schaeden_letzte_5j": [int(wert) for wert in schaeden],
        "typklasse_hp": list(typ["typklasse_hp"]),
        "typklasse_tk": _nur_wenn(
            typ["typklasse_tk"], [a or b for a, b in zip(vollkasko, teilkasko, strict=True)]
        ),
        "typklasse_vk": _nur_wenn(typ["typklasse_vk"], vollkasko),
        "regionalklasse_hp": list(regional["regionalklasse_hp"]),
        "regionalklasse_tk": list(regional["regionalklasse_tk"]),
        "regionalklasse_vk": list(regional["regionalklasse_vk"]),
    }

    return RisikoKfz(
        rahmen=typisierter_rahmen(spalten, "risiko_kfz"),
        sparte=tuple(wirksam),
        sf_klasse_hp=tuple(sf_hp),
        # Die Teilkasko kennt keine eigene Schadenfreiheitseinstufung.
        beitrags_sf_klasse=tuple(
            _je_deckung(
                sf_vk_alle[index],
                None,
                sf_hp[index],
                ist_vollkasko=vollkasko[index],
                ist_teilkasko=teilkasko[index],
            )
            for index in range(anzahl)
        ),
        typklasse=tuple(
            _je_deckung(
                typ["typklasse_vk"][index],
                typ["typklasse_tk"][index],
                typ["typklasse_hp"][index],
                ist_vollkasko=vollkasko[index],
                ist_teilkasko=teilkasko[index],
            )
            for index in range(anzahl)
        ),
        regionalklasse=tuple(
            _je_deckung(
                regional["regionalklasse_vk"][index],
                regional["regionalklasse_tk"][index],
                regional["regionalklasse_hp"][index],
                ist_vollkasko=vollkasko[index],
                ist_teilkasko=teilkasko[index],
            )
            for index in range(anzahl)
        ),
        jahresfahrleistung_km=tuple(int(wert) for wert in fahrleistungen),
    )


def _nur_wenn(werte: Sequence[object], bedingung: Sequence[bool]) -> list[object]:
    """Uebernimmt einen Wert nur dort, wo die Bedingung gilt; sonst bleibt das Feld leer."""
    return [wert if treffer else None for wert, treffer in zip(werte, bedingung, strict=True)]


def _je_deckung[T](
    vollkaskowert: T,
    teilkaskowert: T,
    haftpflichtwert: T,
    *,
    ist_vollkasko: bool,
    ist_teilkasko: bool,
) -> T:
    """Waehlt den fuer die Sparte massgeblichen Wert aus."""
    if ist_vollkasko:
        return vollkaskowert
    if ist_teilkasko:
        return teilkaskowert
    return haftpflichtwert


def _pruefe_ordnung() -> None:
    """Selbstpruefung der SF-Reihenfolge gegen :func:`sf_ordnung`.

    Ohne sie koennte die Reihenfolge in diesem Modul stillschweigend von der
    Ordinalskala in ``src/common/enums.py`` abweichen — und ``_ziehe_sf_vollkasko``
    wuerde R-030 verletzen, ohne dass es auffiele.
    """
    ordnungen = [sf_ordnung(klasse) for klasse in _SF_REIHENFOLGE]
    if None in ordnungen or ordnungen != sorted(wert for wert in ordnungen if wert is not None):
        raise ValueError("Die SF-Reihenfolge weicht von sf_ordnung() ab")
    if set(_SF_SONDER_GEWICHTE) != set(SF_KLASSEN_SONDER):
        raise ValueError("Die Sonderklassen weichen vom Katalog ab")
    if set(_SF_REIHENFOLGE[:_SF_KASKO_UNTERGRENZE]) != _KEINE_KASKO_ANNAHME:
        raise ValueError(
            "Die Kasko-Untergrenze zeigt nicht auf die nicht angenommenen Klassen: "
            f"{_SF_REIHENFOLGE[:_SF_KASKO_UNTERGRENZE]}"
        )
    stufen = enumerate(SF_KLASSEN_NUMERISCH, start=1)
    if any(schadenfreie_jahre(klasse) != stufe for stufe, klasse in stufen):
        raise ValueError("SF-Katalog und schadenfreie_jahre() passen nicht zusammen")


_pruefe_ordnung()
