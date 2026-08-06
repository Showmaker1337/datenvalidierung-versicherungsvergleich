"""Angebote — Tarifwahl, Beitragsberechnung und Rangfolge.

Zwei Bedingungen tragen dieses Modul, beide aus spec/02:

* **Tarifwahl (R-055).** Gewaehlt wird der Tarif, dessen Gueltigkeitsfenster den
  Berechnungszeitpunkt enthaelt. Je Anbieter und Sparte gibt es mehrere
  Generationen; ohne diese Bedingung waere R-055 auf sauberen Daten in rund zwei
  Dritteln der Faelle verletzt.
* **Beitragsarithmetik (R-031, R-032, R-036).** Gerechnet wird strikt von unten
  nach oben und ausschliesslich in :class:`~decimal.Decimal`.

Keine Kappung, keine Kopplung
----------------------------

Der Beitrag wird **nicht** an einen Korridor gekappt, und die Zahlweise wird
**unabhaengig** von der Beitragshoehe gezogen. Beides war in einer frueheren
Fassung anders, solange R-053 die Rate statt des Jahresbeitrags pruefte:

* Die Kappung an einer Obergrenze verzerrte den oberen Rand der
  Beitragsverteilung — rund zwei Prozent der Vollkasko-Angebote lagen exakt auf
  demselben Wert.
* Die Kopplung "guenstige Vertraege werden seltener monatlich gezahlt" war zwar
  marktueblich, aber eine kuenstliche Abhaengigkeit im Datensatz. Solche
  Abhaengigkeiten koennen die Auswertung beeinflussen, ohne dass ihre Ursache
  sichtbar ist.

Liegt ein Angebot ausserhalb des Korridors von R-053, gehoert der Schwellenwert
angepasst, nicht der Datensatz. Er steht in ``config.schwellen`` — genau dafuer.

Der Generator liest diese Schwellen trotzdem **nicht**: Sie werden in der Arbeit
variiert; ein Generator, der an ihnen haengt, wuerde bei jeder Variation einen
anderen Datensatz erzeugen und die Laeufe unvergleichbar machen. Die Einhaltung
wird stattdessen im Test geprueft (``tests/test_generator/test_beitrag.py``).
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Final

from src.common import wertebereiche as wb
from src.common.enums import (
    RATENANZAHL_JE_ZAHLWEISE,
    ZAHLWEISEN_IM_GENERATOR,
    Annahmeentscheidung,
    Sparte,
    Zahlweise,
)
from src.common.geld import runde, von_float
from src.common.serialisierung import SPALTEN_JE_ENTITAET, typisierter_rahmen
from src.generator.verteilungen import (
    erzeuge_uuids,
    waehle_index,
    waehle_ohne_zuruecklegen,
    ziehe_lognormal,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence

    import pandas as pd
    from numpy.random import Generator

    from src.common.config import Config
    from src.generator.tarif import Tarifstamm

__all__ = ["Angebote", "Risikoprofil", "erzeuge_angebote"]

# ---------------------------------------------------------------------------
# Beitragsniveau je Sparte
#
# In den Sparten 051 und 052 ist die Bezugsgroesse der **Grundbeitrag**, also der
# Nettojahresbeitrag bei einem Beitragssatz von 100 Prozent (Schadenfreiheits-
# klasse 0). Der tatsaechliche Beitrag entsteht erst durch die Multiplikation mit
# dem Satz der Schadenfreiheitsklasse, der im Median bei rund 29 Prozent liegt.
#
# Die Teilkasko kennt in Deutschland **keine** Schadenfreiheitseinstufung; dort
# ist die Bezugsgroesse deshalb direkt der Durchschnittsbeitrag, ebenso im
# Hausrat.
#
# Groessenordnung angelehnt an die GDV-Durchschnittsbeitraege je Sparte; die
# konkreten Werte sind **Modellannahme** (docs/verteilungsquellen.md).
# ---------------------------------------------------------------------------
_BASISBEITRAG: Final[Mapping[str, float]] = {
    Sparte.KFZ_HAFTPFLICHT.value: 1_100.0,
    Sparte.KFZ_VOLLKASKO.value: 2_300.0,
    Sparte.KFZ_TEILKASKO.value: 225.0,
    Sparte.HAUSRAT.value: 200.0,
}

#: Streuung des Anbieter-Basisniveaus und seine Grenzen (Modellannahme).
#:
#: Die Grenzen begrenzen zugleich die Spreizung je Anfrage: Innerhalb einer
#: Anfrage unterscheiden sich die Angebote nur ueber dieses Niveau, den
#: Selbstbehalt, den Zuschlag bei Annahme mit Erschwernis und den Ratenzuschlag.
_VU_NIVEAU_SIGMA: Final[float] = 0.16
_VU_NIVEAU_GRENZEN: Final[tuple[float, float]] = (0.78, 1.42)

#: Empfindlichkeit des Beitrags gegenueber Typ- und Regionalklasse (Modellannahme).
_TYPKLASSE_STEIGUNG: Final[float] = 0.045
_REGIONALKLASSE_STEIGUNG: Final[float] = 0.050

#: Exponent der Fahrleistung: Der Beitrag steigt unterproportional mit den Kilometern.
_FAHRLEISTUNG_EXPONENT: Final[float] = 0.25
_FAHRLEISTUNG_BEZUG: Final[float] = 12_000.0

#: Bezugsgroesse und Exponent der Versicherungssumme im Hausrat (Modellannahme).
_VS_BEZUG: Final[float] = 62_000.0
_VS_EXPONENT: Final[float] = 0.70

#: Zuschlagsfaktor je ZUERS-Zone (Modellannahme).
_ZUERS_FAKTOR: Final[Mapping[int, float]] = {1: 1.00, 2: 1.06, 3: 1.15, 4: 1.30}

#: Zuschlag fuer eingeschlossene Elementargefahren (Modellannahme).
_ELEMENTAR_FAKTOR: Final[float] = 1.25

#: Zuschlag bei Annahme mit Erschwernis (Modellannahme).
_ZUSCHLAG_FAKTOR: Final[float] = 1.15

#: Faktor je Bauartklasse: Massivbauweise ist guenstiger als Fachwerk und Holz.
#: **Modellannahme.**
_BAUART_FAKTOR: Final[Mapping[str, float]] = {
    "0": 0.95,
    "1": 1.00,
    "2": 1.04,
    "3": 1.09,
    "4": 1.14,
    "5": 1.18,
    "6": 1.22,
    "7": 1.26,
    "8": 1.30,
    "A": 1.06,
    "B": 1.10,
    "C": 1.13,
    "D": 1.16,
    "E": 1.19,
    "F": 1.22,
    "G": 1.26,
    "H": 1.30,
    "I": 1.35,
}

#: Nachlass je Selbstbehaltstufe Teilkasko (Modellannahme).
_SB_TK_FAKTOR: Final[Mapping[Decimal, float]] = {
    Decimal("0.00"): 1.00,
    Decimal("150.00"): 0.94,
    Decimal("300.00"): 0.90,
    Decimal("500.00"): 0.86,
    Decimal("1000.00"): 0.80,
}

#: Nachlass je Selbstbehaltstufe Vollkasko (Modellannahme).
_SB_VK_FAKTOR: Final[Mapping[Decimal, float]] = {
    Decimal("0.00"): 1.00,
    Decimal("300.00"): 0.92,
    Decimal("500.00"): 0.87,
    Decimal("1000.00"): 0.80,
    Decimal("2500.00"): 0.72,
}

#: Nachlass je Selbstbehaltstufe Hausrat, Betragsvariante (Modellannahme).
_SB_HAUSRAT_EUR_FAKTOR: Final[Mapping[Decimal, float]] = {
    Decimal("0.00"): 1.00,
    Decimal("150.00"): 0.95,
    Decimal("250.00"): 0.92,
    Decimal("500.00"): 0.88,
    Decimal("1000.00"): 0.84,
}

#: Stufen und Nachlaesse der Prozentvariante des Hausrat-Selbstbehalts.
_SB_HAUSRAT_PROZENT_FAKTOR: Final[Mapping[Decimal, float]] = {
    Decimal("0.00"): 1.00,
    Decimal("5.00"): 0.96,
    Decimal("10.00"): 0.92,
    Decimal("15.00"): 0.89,
    Decimal("20.00"): 0.86,
}

#: Wahrscheinlichkeit, dass eine Hausrat-Anfrage den Selbstbehalt in Prozent fuehrt.
#:
#: Die Konvention gilt **je Anfrage** fuer alle ihre Angebote (R-052): Ein
#: Vergleich, in dem ein Anbieter Euro und ein anderer Prozent liefert, ist nicht
#: zulaessig.
_P_SB_KONVENTION_PROZENT: Final[float] = 0.35

#: Annahmeentscheidungen mit Gewichten (Modellannahme).
_ENTSCHEIDUNG_GEWICHTE: Final[tuple[tuple[Annahmeentscheidung, float], ...]] = (
    (Annahmeentscheidung.ANNAHME, 0.85),
    (Annahmeentscheidung.ANNAHME_MIT_ZUSCHLAG, 0.08),
    (Annahmeentscheidung.PRUEFUNG, 0.04),
    (Annahmeentscheidung.ABLEHNUNG, 0.03),
)

#: Kleinste Zahl bepreister Angebote je Anfrage.
#:
#: Ohne sie koennte eine Anfrage rechnerisch nur aus Ablehnungen bestehen; dann
#: gaebe es keine Rangfolge und keine Spreizung, und mehrere Relationsregeln
#: waeren auf dieser Anfrage nicht auswertbar.
_MINDESTENS_BEPREIST: Final[int] = 2

#: Formparameter der Angebotszahl: Gamma-foermig mit Modus bei fuenf Angeboten.
#:
#: spec/01, Abschnitt 1 verlangt eine rechtsschiefe Verteilung mit Modus 5 ueber
#: die Spanne 3 bis 12, damit aus 10.000 Anfragen rund 60.000 Angebotszeilen
#: entstehen — nicht die 75.000 einer Gleichverteilung.
_ANGEBOTSZAHL_FORM: Final[float] = 3.0
_ANGEBOTSZAHL_SKALA: Final[float] = 1.5

#: Ratenzuschlag: Untergrenze und Obergrenze in Prozent.
#:
#: Die Untergrenze von 0,5 Prozent ist **nicht kosmetisch**. Bei zwoelf Raten und
#: einem Zuschlag von null summiert sich der Rundungsverlust auf bis zu 0,06 Euro,
#: und R-036 ("unterjaehrige Zahlung ist nie guenstiger als jaehrliche") wuerde
#: auf sauberen Daten ausloesen.
_RZZ_UNTERGRENZE: Final[Decimal] = Decimal("0.50")
_RZZ_OBERGRENZE: Final[Decimal] = wb.RATENZAHLUNGSZUSCHLAG_PROZENT[1]

#: Gewichte der Zahlweisen (Modellannahme).
_ZAHLWEISE_GEWICHTE: Final[Mapping[Zahlweise, float]] = {
    Zahlweise.JAEHRLICH: 0.35,
    Zahlweise.MONATLICH: 0.35,
    Zahlweise.VIERTELJAEHRLICH: 0.15,
    Zahlweise.HALBJAEHRLICH: 0.12,
    Zahlweise.EINMALBETRAG: 0.03,
}

#: Hoechstabstand zwischen Eingangs- und Berechnungszeitpunkt in Sekunden.
_BERECHNUNG_DELTA_MAX: Final[int] = wb.BERECHNUNG_DELTA_MAX_SEKUNDEN


@dataclass(frozen=True, slots=True)
class Risikoprofil:
    """Alle Groessen einer Anfrage, die in den Beitrag eingehen.

    Die Zusammenstellung geschieht in der Pipeline; dieses Modul kennt die
    Risikoentitaeten dadurch nicht im Einzelnen.

    Attributes:
        sparte: Spartenschluessel der Anfrage.
        typklasse: Fuer die Sparte massgebliche Typklasse (nur Kfz).
        regionalklasse: Fuer die Sparte massgebliche Regionalklasse (nur Kfz).
        sf_beitragssatz: Beitragssatz der Schadenfreiheitsklasse in Prozent;
            ``None`` in der Teilkasko und im Hausrat.
        jahresfahrleistung_km: Fahrleistung (nur Kfz).
        versicherungssumme_eur: Versicherungssumme (nur Hausrat).
        zuers_zone: ZUERS-Zone (nur Hausrat).
        bauartklasse: Bauartklasse (nur Hausrat).
        elementar_eingeschlossen: Elementarschutz (nur Hausrat).
    """

    sparte: str
    typklasse: int | None = None
    regionalklasse: int | None = None
    sf_beitragssatz: Decimal | None = None
    jahresfahrleistung_km: int | None = None
    versicherungssumme_eur: Decimal | None = None
    zuers_zone: int | None = None
    bauartklasse: str | None = None
    elementar_eingeschlossen: bool | None = None


@dataclass(frozen=True, slots=True)
class Angebote:
    """Angebote samt der aus ihnen abgeleiteten Zahlweise.

    Attributes:
        rahmen: Die Entitaet ``angebot``.
        zahlweise: Gezogene Zahlweise je Anfrage.
    """

    rahmen: pd.DataFrame
    zahlweise: tuple[int, ...]


@dataclass(slots=True)
class _Rohangebot:
    """Zwischenstand eines Angebots vor der Ratenrechnung."""

    anfrage_index: int
    tarif_id: str
    quell_schnittstelle: str
    berechnungszeitpunkt: dt.datetime
    entscheidung: str
    nettobeitrag: Decimal | None
    sb_tk: Decimal | None
    sb_vk: Decimal | None
    sb_hausrat_prozent: Decimal | None
    sb_hausrat_eur: Decimal | None


def _beitragsniveau_je_vu(rng: Generator, vu_nummern: Sequence[str]) -> dict[str, float]:
    """Zieht je Anbieter ein festes Beitragsniveau.

    Args:
        rng: Zufallsgenerator.
        vu_nummern: Anbieter in der Reihenfolge der Referenztabelle.

    Returns:
        Eine Abbildung Anbieter auf seinen Beitragsfaktor.
    """
    unten, oben = _VU_NIVEAU_GRENZEN
    roh = ziehe_lognormal(rng, len(vu_nummern), 1.0, _VU_NIVEAU_SIGMA)
    return {
        nummer: min(max(float(roh[index]), unten), oben)
        for index, nummer in enumerate(vu_nummern)
    }


def _angebotszahlen(rng: Generator, anzahl: int, minimum: int, maximum: int) -> list[int]:
    """Zieht die Zahl der Angebote je Anfrage: rechtsschief mit Modus fuenf."""
    stufen = list(range(minimum, maximum + 1))
    gewichte = [
        (stufe - minimum + 1) ** (_ANGEBOTSZAHL_FORM - 1.0)
        * math.exp(-(stufe - minimum + 1) / _ANGEBOTSZAHL_SKALA)
        for stufe in stufen
    ]
    return [stufen[int(index)] for index in waehle_index(rng, anzahl, gewichte)]


def _selbstbehalt_kfz(
    rng: Generator, sparte: str
) -> tuple[Decimal | None, Decimal | None, float]:
    """Zieht die Kfz-Selbstbehalte und den zugehoerigen Beitragsfaktor.

    Returns:
        Ein Tripel aus Teilkasko-Selbstbehalt, Vollkasko-Selbstbehalt und Faktor.
        In der Haftpflicht gibt es keinen Selbstbehalt; beide Werte bleiben leer.
    """
    if sparte == Sparte.KFZ_HAFTPFLICHT.value:
        return None, None, 1.0
    if sparte == Sparte.KFZ_TEILKASKO.value:
        stufen = list(wb.SB_TK_EUR_STUFEN)
        gewaehlt = stufen[int(waehle_index(rng, 1, [1.0] * len(stufen))[0])]
        return gewaehlt, None, _SB_TK_FAKTOR[gewaehlt]

    vk_stufen = list(wb.SB_VK_EUR_STUFEN)
    sb_vk = vk_stufen[int(waehle_index(rng, 1, [1.0] * len(vk_stufen))[0])]
    # spec/01, Abschnitt 3.6: sb_vk_eur >= sb_tk_eur.
    moegliche_tk = [stufe for stufe in wb.SB_TK_EUR_STUFEN if stufe <= sb_vk]
    sb_tk = moegliche_tk[int(waehle_index(rng, 1, [1.0] * len(moegliche_tk))[0])]
    return sb_tk, sb_vk, _SB_VK_FAKTOR[sb_vk]


def _selbstbehalt_hausrat(
    rng: Generator, *, in_prozent: bool
) -> tuple[Decimal | None, Decimal | None, float]:
    """Zieht den Hausrat-Selbstbehalt in der Konvention der Anfrage (R-041, R-052).

    Returns:
        Ein Tripel aus Prozentwert, Betragswert und Faktor. Genau einer der beiden
        Werte ist gefuellt.
    """
    tabelle = _SB_HAUSRAT_PROZENT_FAKTOR if in_prozent else _SB_HAUSRAT_EUR_FAKTOR
    stufen = list(tabelle)
    gewaehlt = stufen[int(waehle_index(rng, 1, [1.0] * len(stufen))[0])]
    if in_prozent:
        return gewaehlt, None, tabelle[gewaehlt]
    return None, gewaehlt, tabelle[gewaehlt]


def _netto_kfz(profil: Risikoprofil, vu_faktor: float, sb_faktor: float) -> float:
    """Berechnet den Nettojahresbeitrag eines Kfz-Angebots."""
    if profil.typklasse is None or profil.regionalklasse is None:
        raise ValueError(f"Kfz-Profil ohne Typ- oder Regionalklasse: {profil}")
    typ_mitte = sum(wb.TYPKLASSE_HP) / 2.0
    regio_mitte = sum(wb.REGIONALKLASSE_HP) / 2.0
    sf_faktor = float(profil.sf_beitragssatz) / 100.0 if profil.sf_beitragssatz is not None else 1.0
    fahrleistung = float(profil.jahresfahrleistung_km or _FAHRLEISTUNG_BEZUG)
    beitrag: float = (
        _BASISBEITRAG[profil.sparte]
        * vu_faktor
        * math.exp(_TYPKLASSE_STEIGUNG * (profil.typklasse - typ_mitte))
        * math.exp(_REGIONALKLASSE_STEIGUNG * (profil.regionalklasse - regio_mitte))
        * sf_faktor
        * (fahrleistung / _FAHRLEISTUNG_BEZUG) ** _FAHRLEISTUNG_EXPONENT
        * sb_faktor
    )
    return beitrag


def _netto_hausrat(profil: Risikoprofil, vu_faktor: float, sb_faktor: float) -> float:
    """Berechnet den Nettojahresbeitrag eines Hausrat-Angebots."""
    if profil.versicherungssumme_eur is None or profil.zuers_zone is None:
        raise ValueError(f"Hausrat-Profil ohne Versicherungssumme oder ZUERS-Zone: {profil}")
    if profil.bauartklasse is None:
        raise ValueError(f"Hausrat-Profil ohne Bauartklasse: {profil}")
    beitrag: float = (
        _BASISBEITRAG[profil.sparte]
        * vu_faktor
        * (float(profil.versicherungssumme_eur) / _VS_BEZUG) ** _VS_EXPONENT
        * _ZUERS_FAKTOR[profil.zuers_zone]
        * _BAUART_FAKTOR[profil.bauartklasse]
        * (_ELEMENTAR_FAKTOR if profil.elementar_eingeschlossen else 1.0)
        * sb_faktor
    )
    return beitrag


def _steuer(netto: Decimal, sparte: str) -> tuple[Decimal, Decimal, Decimal]:
    """Berechnet Steuersatz, Steuerbetrag und Bruttojahresbeitrag (R-032, R-033, R-031)."""
    satz = wb.VERSICHERUNGSTEUER_EFFEKTIVSATZ[Sparte(sparte)]
    steuer = runde(netto * satz / Decimal(100))
    return satz, steuer, netto + steuer


def _waehle_zahlweise(rng: Generator) -> Zahlweise:
    """Zieht die Zahlweise **unabhaengig von der Beitragshoehe**.

    Bis zur Korrektur von R-053 (die Regel prueft den Jahresbeitrag, nicht die
    Rate) war die Ziehung auf die Ratenanzahlen eingeschraenkt, bei denen die Rate
    in einem Korridor blieb. Das erzeugte eine kuenstliche Abhaengigkeit zwischen
    Beitragshoehe und Zahlweise, die spaeter die Auswertung haette beeinflussen
    koennen, ohne dass ihre Ursache im Datensatz sichtbar gewesen waere.
    """
    zulaessig = list(ZAHLWEISEN_IM_GENERATOR)
    gewichte = [_ZAHLWEISE_GEWICHTE[zahlweise] for zahlweise in zulaessig]
    return zulaessig[int(waehle_index(rng, 1, gewichte)[0])]


def _ratenzuschlag(rng: Generator, ratenanzahl: int) -> Decimal:
    """Zieht den Ratenzahlungszuschlag; bei einer Rate ist er null (R-035)."""
    if ratenanzahl == 1:
        return Decimal("0.00")
    spanne = _RZZ_OBERGRENZE - _RZZ_UNTERGRENZE
    return runde(_RZZ_UNTERGRENZE + Decimal(repr(float(rng.random()))) * spanne)


def _entscheidungen(rng: Generator, anzahl: int) -> list[str]:
    """Zieht die Annahmeentscheidungen einer Anfrage, mit Mindestzahl bepreister Angebote."""
    gewichte = [gewicht for _, gewicht in _ENTSCHEIDUNG_GEWICHTE]
    gezogen = [
        _ENTSCHEIDUNG_GEWICHTE[int(index)][0].value
        for index in waehle_index(rng, anzahl, gewichte)
    ]
    ablehnung = Annahmeentscheidung.ABLEHNUNG.value
    bepreist = sum(1 for wert in gezogen if wert != ablehnung)
    for position, wert in enumerate(gezogen):
        if bepreist >= min(_MINDESTENS_BEPREIST, anzahl):
            break
        if wert == ablehnung:
            gezogen[position] = Annahmeentscheidung.ANNAHME.value
            bepreist += 1
    return gezogen


def _baue_rohangebote(  # noqa: PLR0913 - die Angebotszeile buendelt sieben Quellen
    rng: Generator,
    *,
    anfrage_index: int,
    profil: Risikoprofil,
    eingangszeitpunkt: dt.datetime,
    vu_auswahl: Sequence[str],
    tarifstamm: Tarifstamm,
    schnittstelle_je_vu: Mapping[str, str],
    vu_niveau: Mapping[str, float],
    sb_in_prozent: bool,
) -> list[_Rohangebot]:
    """Baut die Angebote einer Anfrage bis einschliesslich des Nettobeitrags."""
    entscheidungen = _entscheidungen(rng, len(vu_auswahl))
    versatz = rng.integers(1, _BERECHNUNG_DELTA_MAX + 1, size=len(vu_auswahl))
    ist_hausrat = profil.sparte == Sparte.HAUSRAT.value

    angebote: list[_Rohangebot] = []
    for position, vu_nummer in enumerate(vu_auswahl):
        berechnung = eingangszeitpunkt + dt.timedelta(seconds=int(versatz[position]))
        if ist_hausrat:
            sb_prozent, sb_eur, sb_faktor = _selbstbehalt_hausrat(rng, in_prozent=sb_in_prozent)
            sb_tk, sb_vk = None, None
            roh = _netto_hausrat(profil, vu_niveau[vu_nummer], sb_faktor)
        else:
            sb_tk, sb_vk, sb_faktor = _selbstbehalt_kfz(rng, profil.sparte)
            sb_prozent, sb_eur = None, None
            roh = _netto_kfz(profil, vu_niveau[vu_nummer], sb_faktor)

        entscheidung = entscheidungen[position]
        if entscheidung == Annahmeentscheidung.ANNAHME_MIT_ZUSCHLAG.value:
            roh *= _ZUSCHLAG_FAKTOR
        # Bewusst **ohne** Kappung an einer Beitragsobergrenze: Ein gekappter
        # Beitrag verzerrt den oberen Rand der Verteilung. Liegt ein Angebot
        # ausserhalb des Korridors von R-053, gehoert der Schwellenwert angepasst,
        # nicht der Datensatz (docs/verteilungsquellen.md, Abschnitt 4.6).
        netto = (
            None
            if entscheidung == Annahmeentscheidung.ABLEHNUNG.value
            else von_float(roh)
        )
        angebote.append(
            _Rohangebot(
                anfrage_index=anfrage_index,
                tarif_id=tarifstamm.finde(vu_nummer, profil.sparte, berechnung.date()),
                quell_schnittstelle=schnittstelle_je_vu[vu_nummer],
                berechnungszeitpunkt=berechnung,
                entscheidung=entscheidung,
                nettobeitrag=netto,
                sb_tk=sb_tk,
                sb_vk=sb_vk,
                sb_hausrat_prozent=sb_prozent,
                sb_hausrat_eur=sb_eur,
            )
        )
    return angebote


def erzeuge_angebote(  # noqa: PLR0913 - Tarif, Anbieter und Risiko gehen getrennt ein
    config: Config,
    rng: Generator,
    *,
    anfrage_ids: Sequence[str],
    profile: Sequence[Risikoprofil],
    eingangszeitpunkte: Sequence[dt.datetime],
    tarifstamm: Tarifstamm,
    vu_stammdaten: pd.DataFrame,
) -> Angebote:
    """Erzeugt alle Angebotszeilen und bestimmt dabei die Zahlweise je Anfrage.

    Args:
        config: Geladene Konfiguration; liefert die Spanne der Angebotszahl.
        rng: Zufallsgenerator des Teilstroms "Angebot".
        anfrage_ids: Kennung je Anfrage.
        profile: Risikoprofil je Anfrage.
        eingangszeitpunkte: Eingangszeitpunkt je Anfrage.
        tarifstamm: Tarifstammdaten mit Nachschlagestruktur.
        vu_stammdaten: Referenztabelle der Anbieter.

    Returns:
        Die :class:`Angebote` mit Datenrahmen und Zahlweise je Anfrage.
    """
    vu_nummern = [str(wert) for wert in vu_stammdaten["vu_nummer"]]
    marktanteile = [float(wert) for wert in vu_stammdaten["marktanteil"]]
    schnittstelle_je_vu = {
        nummer: str(vu_stammdaten["quell_schnittstelle"].iloc[index])
        for index, nummer in enumerate(vu_nummern)
    }
    vu_niveau = _beitragsniveau_je_vu(rng, vu_nummern)

    anzahl_anfragen = len(anfrage_ids)
    angebotszahlen = _angebotszahlen(
        rng,
        anzahl_anfragen,
        config.angebote_je_anfrage.minimum,
        min(config.angebote_je_anfrage.maximum, len(vu_nummern)),
    )
    sb_konventionen = rng.random(anzahl_anfragen) < _P_SB_KONVENTION_PROZENT

    rohangebote: list[list[_Rohangebot]] = []
    for index in range(anzahl_anfragen):
        auswahl = waehle_ohne_zuruecklegen(rng, marktanteile, angebotszahlen[index])
        rohangebote.append(
            _baue_rohangebote(
                rng,
                anfrage_index=index,
                profil=profile[index],
                eingangszeitpunkt=eingangszeitpunkte[index],
                vu_auswahl=[vu_nummern[int(position)] for position in auswahl],
                tarifstamm=tarifstamm,
                schnittstelle_je_vu=schnittstelle_je_vu,
                vu_niveau=vu_niveau,
                sb_in_prozent=bool(sb_konventionen[index]),
            )
        )

    return _vervollstaendige(rng, anfrage_ids, profile, rohangebote)


def _vervollstaendige(
    rng: Generator,
    anfrage_ids: Sequence[str],
    profile: Sequence[Risikoprofil],
    rohangebote: Sequence[Sequence[_Rohangebot]],
) -> Angebote:
    """Rechnet Steuer, Brutto, Ratenzuschlag und Rate und vergibt die Raenge."""
    spalten: dict[str, list[object]] = {name: [] for name in SPALTEN_JE_ENTITAET["angebot"]}
    zahlweisen: list[int] = []
    gesamtzahl = sum(len(gruppe) for gruppe in rohangebote)
    angebot_ids = erzeuge_uuids(rng, gesamtzahl)
    laufende = 0

    for index, gruppe in enumerate(rohangebote):
        sparte = profile[index].sparte
        brutto_je_angebot = {
            position: _steuer(angebot.nettobeitrag, sparte)
            for position, angebot in enumerate(gruppe)
            if angebot.nettobeitrag is not None
        }
        zahlweise = _waehle_zahlweise(rng)
        ratenanzahl = RATENANZAHL_JE_ZAHLWEISE[zahlweise]
        zahlweisen.append(int(zahlweise))

        raten: dict[int, tuple[Decimal, Decimal]] = {}
        for position, (_, _, brutto) in brutto_je_angebot.items():
            zuschlag = _ratenzuschlag(rng, ratenanzahl)
            aufschlag = Decimal(1) + zuschlag / Decimal(100)
            raten[position] = (zuschlag, runde(brutto * aufschlag / ratenanzahl))

        # Der Rang wird erst nach der Beitragsberechnung vergeben: aufsteigend
        # nach der Rate, lueckenlos ab 1. Abgelehnte Angebote bleiben ohne Rang
        # (Entscheidung dokumentiert in README.md).
        reihenfolge = sorted(
            raten, key=lambda position: (raten[position][1], gruppe[position].tarif_id)
        )
        rang_je_position = {position: rang for rang, position in enumerate(reihenfolge, start=1)}

        for position, angebot in enumerate(gruppe):
            werte = brutto_je_angebot.get(position)
            spalten["row_id"].append(laufende + 1)
            spalten["angebot_id"].append(angebot_ids[laufende])
            spalten["anfrage_id"].append(anfrage_ids[index])
            spalten["tarif_id"].append(angebot.tarif_id)
            spalten["rang"].append(rang_je_position.get(position))
            spalten["nettobeitrag_jahr_eur"].append(angebot.nettobeitrag)
            spalten["versicherungsteuer_satz"].append(werte[0] if werte else None)
            spalten["versicherungsteuer_eur"].append(werte[1] if werte else None)
            spalten["bruttobeitrag_jahr_eur"].append(werte[2] if werte else None)
            spalten["ratenzahlungszuschlag_prozent"].append(
                raten[position][0] if position in raten else None
            )
            spalten["zahlbeitrag_rate_eur"].append(
                raten[position][1] if position in raten else None
            )
            spalten["sb_tk_eur"].append(angebot.sb_tk)
            spalten["sb_vk_eur"].append(angebot.sb_vk)
            spalten["sb_hausrat_prozent"].append(angebot.sb_hausrat_prozent)
            spalten["sb_hausrat_eur"].append(angebot.sb_hausrat_eur)
            spalten["annahmeentscheidung"].append(angebot.entscheidung)
            spalten["berechnungszeitpunkt"].append(angebot.berechnungszeitpunkt)
            spalten["quell_schnittstelle"].append(angebot.quell_schnittstelle)
            laufende += 1

    return Angebote(
        rahmen=typisierter_rahmen(spalten, "angebot"), zahlweise=tuple(zahlweisen)
    )
