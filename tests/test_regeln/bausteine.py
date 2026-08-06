"""Minimaldatensaetze fuer die Regeltests.

Jeder Regeltest arbeitet auf **handgebauten** Datenrahmen, nicht auf dem
Generator-Output. Der Grund ist methodisch: Ein Test gegen den Generator wuerde
nur zeigen, dass zwei Implementierungen zueinander passen. Ein Test gegen einen
von Hand gesetzten Wert zeigt, dass die Regel das prueft, was im Katalog steht.

Aufbau
------

:data:`STANDARD` haelt je Entitaet eine vollstaendige, **regelkonforme** Zeile.
Ein Testfall nennt nur die Felder, die er aendert; alles Uebrige bleibt sauber.
Damit ist jede Abweichung im Test sichtbar, statt in einer Wand von Feldwerten zu
verschwinden.

Der Weg durch beide Schichten
-----------------------------

:func:`baue` geht denselben Weg wie der spaetere Experimentlauf: typisierte Zeilen
werden serialisiert, die Rohschicht kann punktuell veraendert werden, und erst
daraus entsteht die typisierte Schicht durch Parsen. Nur so sind Fehler
darstellbar, die es auf der typisierten Schicht gar nicht geben kann — ein
``31022026`` als Datum oder eine Postleitzahl ohne fuehrende Null.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Final

import pandas as pd

from src.common.iban import baue_iban
from src.common.serialisierung import SPALTEN_JE_ENTITAET, serialisiere, typisierter_rahmen
from src.rules.katalog import regel
from src.rules.modell import Kontext, baue_kontext

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence

    from src.common.config import Config
    from src.rules.modell import Befund

__all__ = [
    "REFERENZ",
    "STANDARD",
    "VORGANG_HAUSRAT",
    "VORGANG_KFZ",
    "Fall",
    "baue",
    "kennungen",
    "pruefe",
    "pruefe_fall",
]

#: Gueltige IBAN mit richtiger Pruefziffer.
IBAN_GUELTIG: Final[str] = baue_iban("10000000", "1234567890")

#: Dieselbe IBAN mit verfaelschter Pruefziffer — formal richtig, rechnerisch falsch.
IBAN_PRUEFZIFFER_FALSCH: Final[str] = (
    IBAN_GUELTIG[:-1] + ("0" if IBAN_GUELTIG[-1] != "0" else "1")
)

#: Regelkonforme Standardzeile je Entitaet.
#:
#: Die Werte sind untereinander konsistent: Der Bruttobeitrag ist die Summe aus
#: Netto und Steuer, die Steuer entspricht dem Effektivsatz der Sparte 051, die
#: Erstzulassung liegt vor der Zulassung auf den Versicherungsnehmer, und die
#: abgeleiteten Fahrzeug- und Regionalmerkmale stimmen mit :data:`REFERENZ`
#: ueberein.
STANDARD: Final[Mapping[str, Mapping[str, Any]]] = {
    "anfrage": {
        "row_id": 1,
        "anfrage_id": "A1",
        "eingangszeitpunkt": dt.datetime(2026, 1, 15, 10, 0, 0),  # noqa: DTZ001
        "kanal": "MAKLER",
        "sparte": "051",
        "vn_person_id": "P1",
        "versicherungsbeginn": dt.date(2026, 2, 1),
        "vorvertrag_vorhanden": True,
        "vorversicherer_vu_nr": "00001",
        "zahlweise": 1,
        "waehrung": "EUR",
        "anfrage_status": "ANGEBOT",
    },
    "person": {
        "row_id": 1,
        "person_id": "P1",
        "anfrage_id": "A1",
        "rolle": "VN",
        "anrede": "HERR",
        "nachname": "Muster",
        "vorname": "Max",
        "geburtsdatum": dt.date(1985, 3, 4),
        "plz": "01067",
        "ort": "Musterstadt",
        "strasse": "Hauptstrasse",
        "hausnummer": "12",
        "email": "max.muster@beispielmail.de",
        "familienstand": "LEDIG",
        "wohneigentum": True,
        "fuehrerschein_datum": dt.date(2003, 5, 20),
    },
    "risiko_kfz": {
        "row_id": 1,
        "risiko_id": "K1",
        "anfrage_id": "A1",
        "hsn": "0005",
        "tsn": "AAA",
        "wagniskennziffer": "112",
        "erstzulassung": dt.date(2018, 4, 1),
        "zulassung_auf_vn": dt.date(2019, 6, 1),
        "leistung_kw": 90,
        "antriebsart": "BENZIN",
        "neupreis_eur": Decimal("30000.00"),
        "fahrzeugwert_aktuell": Decimal("12000.00"),
        "art_kennzeichen": "01",
        "zulassungsbezirk": "DD",
        "jahresfahrleistung_km": 12000,
        "nutzungsart": "02",
        "eigentumsverhaeltnis": "1",
        "nutzerkreis": "VN",
        "alter_juengster_fahrer": 41,
        "abstellplatz": "GARAGE",
        "sf_klasse_hp": "SF10",
        "sf_klasse_vk": None,
        "schaeden_letzte_5j": 0,
        "typklasse_hp": 15,
        "typklasse_tk": None,
        "typklasse_vk": None,
        "regionalklasse_hp": 5,
        "regionalklasse_tk": 7,
        "regionalklasse_vk": 4,
    },
    "risiko_hausrat": {
        "row_id": 1,
        "risiko_id": "H1",
        "anfrage_id": "A1",
        "wohnflaeche_qm": 80,
        "versicherungssumme_eur": Decimal("60000.00"),
        "unterversicherungsverzicht": True,
        "bauartklasse": "1",
        "baujahr": 1995,
        "gebaeudeart": "EFH",
        "stockwerk": None,
        "zuers_zone": 1,
        "elementar_eingeschlossen": False,
        "sublimit_fahrrad_eur": Decimal("1000.00"),
        "sublimit_wertsachen_eur": Decimal("6000.00"),
    },
    "tarif": {
        "row_id": 1,
        "tarif_id": "T1",
        "vu_nummer": "00001",
        "produktname": "Basis Kfz HP",
        "sparte": "051",
        "tarifgeneration": "2026-01",
        "gueltig_ab": dt.date(2026, 1, 1),
        "gueltig_bis": dt.date(2026, 12, 31),
        "deckungsart": 11,
        "deckungssumme_personen_eur": Decimal("100000000.00"),
        "deckungssumme_sach_eur": Decimal("100000000.00"),
        "deckungssumme_vermoegen_eur": Decimal("100000000.00"),
        "werkstattbindung": True,
    },
    "angebot": {
        "row_id": 1,
        "angebot_id": "G1",
        "anfrage_id": "A1",
        "tarif_id": "T1",
        "rang": 1,
        "nettobeitrag_jahr_eur": Decimal("500.00"),
        "versicherungsteuer_satz": Decimal("19.00"),
        "versicherungsteuer_eur": Decimal("95.00"),
        "bruttobeitrag_jahr_eur": Decimal("595.00"),
        "ratenzahlungszuschlag_prozent": Decimal("0.00"),
        "zahlbeitrag_rate_eur": Decimal("595.00"),
        "sb_tk_eur": None,
        "sb_vk_eur": None,
        "sb_hausrat_prozent": None,
        "sb_hausrat_eur": None,
        "annahmeentscheidung": "ANNAHME",
        "berechnungszeitpunkt": dt.datetime(2026, 1, 15, 10, 0, 30),  # noqa: DTZ001
        "quell_schnittstelle": "BIPRO_420",
    },
    "zahlung": {
        "row_id": 1,
        "zahlung_id": "Z1",
        "anfrage_id": "A1",
        "iban": IBAN_GUELTIG,
        "bic": "MUSTDEFFXXX",
        "sepa_mandat_datum": dt.date(2026, 1, 20),
        "kontoinhaber": "Max Muster",
    },
}


def _referenztabellen() -> dict[str, pd.DataFrame]:
    """Baut die Referenztabellen passend zu :data:`STANDARD`.

    Bewusst **nicht** die echten Referenzdateien: Ein Regeltest soll an einem
    ueberschaubaren, im Test sichtbaren Wertevorrat scheitern oder bestehen, nicht
    an einer 8.000-zeiligen CSV.
    """
    return {
        "plz_ort": pd.DataFrame(
            {
                "plz": pd.array(["01067", "10115"], dtype="string"),
                "ort": pd.array(["Musterstadt", "Beispielstadt"], dtype="string"),
                "bundesland": pd.array(["SN", "BE"], dtype="string"),
                "zulassungsbezirk": pd.array(["DD", "B"], dtype="string"),
            }
        ),
        "regionalklassen": pd.DataFrame(
            {
                "zulassungsbezirk": pd.array(["DD", "B"], dtype="string"),
                "regionalklasse_hp": [5, 8],
                "regionalklasse_tk": [7, 11],
                "regionalklasse_vk": [4, 6],
            }
        ),
        "typklassen": pd.DataFrame(
            {
                "hsn": pd.array(["0005", "0600"], dtype="string"),
                "tsn": pd.array(["AAA", "BBB"], dtype="string"),
                "hersteller": pd.array(["Musterwerke", "Beispielbau"], dtype="string"),
                "modell": pd.array(["M1", "B2"], dtype="string"),
                "leistung_kw": [90, 150],
                "antriebsart": pd.array(["BENZIN", "ELEKTRO"], dtype="string"),
                "typklasse_hp": [15, 20],
                "typklasse_tk": [20, 25],
                "typklasse_vk": [22, 28],
                "neupreis_eur": pd.Series(
                    [Decimal("30000.00"), Decimal("55000.00")], dtype=object
                ),
            }
        ),
        "vu_stammdaten": pd.DataFrame(
            {
                "vu_nummer": pd.array(["00001", "00002"], dtype="string"),
                "vu_name": pd.array(
                    ["Nordstern Versicherung AG", "Suedwind Versicherung AG"], dtype="string"
                ),
                "marktanteil": [0.6, 0.4],
                "quell_schnittstelle": pd.array(["BIPRO_420", "GDV"], dtype="string"),
            }
        ),
        "zuers_zonen": pd.DataFrame(
            {
                "plz": pd.array(["01067", "10115"], dtype="string"),
                "zuers_zone": [1, 2],
            }
        ),
        "sf_beitragssatz": pd.DataFrame(
            {
                "sf_klasse": pd.array(["0", "SF10", "SF50"], dtype="string"),
                "beitragssatz_prozent": [100, 40, 16],
            }
        ),
        "waehrungen": pd.DataFrame(
            {
                "code": pd.array(["EUR", "CHF", "USD"], dtype="string"),
                "name": pd.array(["Euro", "Swiss Franc", "US Dollar"], dtype="string"),
                "numerisch": [978, 756, 840],
            }
        ),
    }


#: Referenztabellen der Regeltests, passend zu :data:`STANDARD`.
REFERENZ: Final[Mapping[str, pd.DataFrame]] = _referenztabellen()

#: Ein vollstaendiger, regelkonformer Kfz-Vorgang aus einer Zeile je Entitaet.
VORGANG_KFZ: Final[dict[str, list[dict[str, Any]]]] = {
    "anfrage": [{}],
    "person": [{}],
    "risiko_kfz": [{}],
    "tarif": [{}],
    "angebot": [{}],
    "zahlung": [{}],
}

#: Ein vollstaendiger, regelkonformer Hausratvorgang.
#:
#: Der Steuersatz ist der Effektivsatz der Sparte 130 (16,15 Prozent), die Steuer
#: daraus gerechnet und der Bruttobeitrag ihre Summe mit dem Netto — sonst
#: schluegen R-031 bis R-033 schon auf dem positiven Fall an.
VORGANG_HAUSRAT: Final[dict[str, list[dict[str, Any]]]] = {
    "anfrage": [{"sparte": "130"}],
    "person": [{}],
    "risiko_hausrat": [{}],
    "tarif": [{"sparte": "130"}],
    "angebot": [
        {
            "versicherungsteuer_satz": Decimal("16.15"),
            "versicherungsteuer_eur": Decimal("80.75"),
            "bruttobeitrag_jahr_eur": Decimal("580.75"),
            "zahlbeitrag_rate_eur": Decimal("580.75"),
            "sb_hausrat_eur": Decimal("150.00"),
        }
    ],
    "zahlung": [{}],
}


def _zeilen(entitaet: str, ueberschreibungen: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Baut einen typisierten Datenrahmen aus Abweichungen zur Standardzeile."""
    vorlage = STANDARD[entitaet]
    spalten = SPALTEN_JE_ENTITAET[entitaet]
    zeilen: list[dict[str, Any]] = []
    for nummer, abweichung in enumerate(ueberschreibungen, start=1):
        unbekannt = sorted(set(abweichung) - set(spalten))
        if unbekannt:
            raise KeyError(f"{entitaet}: unbekannte Felder {unbekannt}")
        zeile = {**vorlage, "row_id": nummer, **abweichung}
        zeilen.append(zeile)
    return typisierter_rahmen(
        {spalte: [zeile[spalte] for zeile in zeilen] for spalte in spalten}, entitaet
    )


def baue(
    config: Config,
    zeilen: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    roh: Mapping[str, Mapping[int, Mapping[str, str]]] | None = None,
    referenz: Mapping[str, pd.DataFrame] | None = None,
) -> Kontext:
    """Baut einen Pruefkontext aus Abweichungen zur Standardzeile.

    Args:
        config: Geladene Konfiguration.
        zeilen: Je Entitaet die Zeilen als Abweichung von :data:`STANDARD`.
            Nicht genannte Entitaeten bleiben leer.
        roh: Punktuelle Aenderungen an der **Rohschicht**, als
            Entitaet auf Zeilenindex auf Spalte auf Rohwert. Nur so sind Format-,
            Typ- und Sentinel-Fehler darstellbar.
        referenz: Referenztabellen; ohne Angabe :data:`REFERENZ`.

    Returns:
        Den Kontext ueber beide Schichten. Die typisierte Schicht entsteht durch
        **Parsen der Rohschicht** — denselben Weg geht der spaetere Experimentlauf.
    """
    rohschicht = {
        entitaet: serialisiere(_zeilen(entitaet, abweichungen))
        for entitaet, abweichungen in zeilen.items()
    }
    for entitaet, zeilenwerte in (roh or {}).items():
        rahmen = rohschicht[entitaet]
        for index, felder in zeilenwerte.items():
            for spalte, wert in felder.items():
                rahmen.loc[index, spalte] = wert
    return baue_kontext(
        config, raw=rohschicht, referenz=referenz if referenz is not None else REFERENZ
    )


def pruefe(
    config: Config,
    regel_id: str,
    zeilen: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    roh: Mapping[str, Mapping[int, Mapping[str, str]]] | None = None,
    referenz: Mapping[str, pd.DataFrame] | None = None,
) -> Befund:
    """Fuehrt **eine** Regel auf einem Minimaldatensatz aus.

    Genau eine Regel je Test: Ein Verstoss loest oft mehrere Regeln aus — ein
    Sentinel-Datum verletzt R-009 und R-025 zugleich. Wuerde der Test den ganzen
    Katalog laufen lassen, sagte sein Ergebnis nichts ueber die gemeinte Regel aus.

    Args:
        config: Geladene Konfiguration.
        regel_id: Kennung der zu pruefenden Regel.
        zeilen: Je Entitaet die Zeilen als Abweichung von :data:`STANDARD`.
        roh: Punktuelle Aenderungen an der Rohschicht.
        referenz: Referenztabellen; ohne Angabe :data:`REFERENZ`.

    Returns:
        Den Befund der Regel.
    """
    kontext = baue(config, zeilen, roh=roh, referenz=referenz)
    return regel(regel_id).pruefe(kontext)


@dataclass(frozen=True, slots=True)
class Fall:
    """Ein Regeltestfall — positiv oder negativ.

    Attributes:
        regel_id: Zu pruefende Regel.
        beschreibung: Kurzbeschreibung; geht in die Testkennung ein.
        verletzt: ``True``, wenn die Regel anschlagen **muss**.
        zeilen: Je Entitaet die Zeilen als Abweichung von :data:`STANDARD`.
        roh: Punktuelle Aenderungen an der Rohschicht.
        spalten: Erwartete gemeldete Spalten. Leer heisst: nicht geprueft.
        satzbezogen: ``True``, wenn die Regel den satzbezogenen Kanal fuellt
            statt des Zellkanals (R-047, R-048).
    """

    regel_id: str
    beschreibung: str
    verletzt: bool
    zeilen: Mapping[str, Sequence[Mapping[str, Any]]]
    roh: Mapping[str, Mapping[int, Mapping[str, str]]] | None = None
    spalten: tuple[str, ...] = ()
    satzbezogen: bool = False
    referenz: Mapping[str, pd.DataFrame] | None = field(default=None, repr=False)

    @property
    def kennung(self) -> str:
        """Kennung des Testfalls fuer die Testausgabe."""
        art = "negativ" if self.verletzt else "positiv"
        return f"{self.regel_id}-{art}-{self.beschreibung}"


def kennungen(faelle: Sequence[Fall]) -> list[str]:
    """Gibt die Testkennungen einer Fallfolge zurueck."""
    return [fall.kennung for fall in faelle]


def pruefe_fall(config: Config, fall: Fall) -> None:
    """Fuehrt einen Testfall aus und prueft das Ergebnis.

    Args:
        config: Geladene Konfiguration.
        fall: Der Testfall.

    Raises:
        AssertionError: Wenn die Regel anders entscheidet als erwartet.
    """
    befund = pruefe(
        config, fall.regel_id, fall.zeilen, roh=fall.roh, referenz=fall.referenz
    )
    gemeldet = befund.saetze if fall.satzbezogen else befund.zellen

    if not fall.verletzt:
        assert not befund, (
            f"{fall.regel_id} meldet auf regelkonformen Daten ({fall.beschreibung}): "
            f"{[eintrag.meldung for eintrag in befund.zellen][:3]}"
            f"{[eintrag.meldung for eintrag in befund.saetze][:3]}"
        )
        return

    assert gemeldet, (
        f"{fall.regel_id} meldet den Verstoss nicht ({fall.beschreibung})"
    )
    if fall.spalten:
        tatsaechlich = {eintrag.spalte for eintrag in befund.zellen}
        fehlend = sorted(set(fall.spalten) - tatsaechlich)
        assert not fehlend, (
            f"{fall.regel_id} meldet die Spalten {sorted(tatsaechlich)}, "
            f"erwartet wurden auch {fehlend}"
        )
    for eintrag in befund.zellen:
        assert eintrag.verstoss_id.startswith(fall.regel_id), (
            f"verstoss_id {eintrag.verstoss_id!r} gehoert nicht zu {fall.regel_id}"
        )
