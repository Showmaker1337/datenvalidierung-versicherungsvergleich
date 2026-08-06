"""Regeltests der Gruppe G1 (R-001 bis R-025).

Je Regel mindestens ein positiver und ein negativer Fall auf handgebauten
Minimaldatensaetzen. Die Faelle stehen als Datentabelle, nicht als je zwei
Funktionen: Nur so bleibt sichtbar, **welcher einzelne Wert** eine Regel ausloest,
statt in fuenfzig fast gleichen Testkoerpern zu verschwinden.

Elf dieser Regeln arbeiten auf der Rohschicht. Ihre negativen Faelle setzen den
Wert deshalb ueber ``roh`` — auf der typisierten Schicht waeren sie gar nicht
darstellbar.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from tests.test_regeln.bausteine import (
    IBAN_PRUEFZIFFER_FALSCH,
    VORGANG_HAUSRAT,
    VORGANG_KFZ,
    Fall,
    kennungen,
    pruefe_fall,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from src.common.config import Config

#: Kurznamen der beiden Vorgangsvorlagen aus ``bausteine``.
_SAUBER = VORGANG_KFZ
_HAUSRAT = VORGANG_HAUSRAT


FAELLE: tuple[Fall, ...] = (
    # --- R-001 Kernpflichtfelder -------------------------------------------
    Fall("R-001", "vollstaendig", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-001",
        "nachname-leer",
        verletzt=True,
        zeilen={**_SAUBER, "person": [{"nachname": None}]},
        spalten=("nachname",),
    ),
    Fall(
        "R-001",
        "natuerliche-person-ohne-geburtsdatum",
        verletzt=True,
        zeilen={**_SAUBER, "person": [{"geburtsdatum": None}]},
        spalten=("geburtsdatum",),
    ),
    Fall(
        "R-001",
        "firma-ohne-geburtsdatum-ist-zulaessig",
        verletzt=False,
        zeilen={
            **_SAUBER,
            "person": [{"anrede": "FIRMA", "geburtsdatum": None, "vorname": None}],
        },
    ),
    # --- R-002 Postleitzahl -------------------------------------------------
    Fall("R-002", "fuenfstellig", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-002",
        "fuehrende-null-verloren",
        verletzt=True,
        zeilen=_SAUBER,
        roh={"person": {0: {"plz": "1067"}}},
        spalten=("plz",),
    ),
    # --- R-003 IBAN-Format --------------------------------------------------
    Fall("R-003", "deutsche-iban", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-003",
        "zu-kurz",
        verletzt=True,
        zeilen=_SAUBER,
        roh={"zahlung": {0: {"iban": "DE1234567890"}}},
        spalten=("iban",),
    ),
    # --- R-004 IBAN-Pruefziffer --------------------------------------------
    Fall("R-004", "pruefziffer-stimmt", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-004",
        "pruefziffer-falsch",
        verletzt=True,
        zeilen=_SAUBER,
        roh={"zahlung": {0: {"iban": IBAN_PRUEFZIFFER_FALSCH}}},
        spalten=("iban",),
    ),
    # --- R-005 BIC ----------------------------------------------------------
    Fall("R-005", "elf-zeichen", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-005",
        "neun-zeichen",
        verletzt=True,
        zeilen=_SAUBER,
        roh={"zahlung": {0: {"bic": "MUSTDEFFX"}}},
        spalten=("bic",),
    ),
    # --- R-006 E-Mail -------------------------------------------------------
    Fall("R-006", "gueltige-adresse", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-006",
        "ohne-at-zeichen",
        verletzt=True,
        zeilen=_SAUBER,
        roh={"person": {0: {"email": "max.muster.beispielmail.de"}}},
        spalten=("email",),
    ),
    # --- R-007 HSN ----------------------------------------------------------
    Fall("R-007", "vierstellig", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-007",
        "dreistellig",
        verletzt=True,
        zeilen=_SAUBER,
        roh={"risiko_kfz": {0: {"hsn": "005"}}},
        spalten=("hsn",),
    ),
    # --- R-008 TSN ----------------------------------------------------------
    Fall("R-008", "drei-grossbuchstaben", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-008",
        "kleinbuchstaben",
        verletzt=True,
        zeilen=_SAUBER,
        roh={"risiko_kfz": {0: {"tsn": "aaa"}}},
        spalten=("tsn",),
    ),
    # --- R-009 Kalendertag --------------------------------------------------
    Fall("R-009", "existierende-daten", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-009",
        "31-februar",
        verletzt=True,
        zeilen=_SAUBER,
        roh={"risiko_kfz": {0: {"erstzulassung": "31022026"}}},
        spalten=("erstzulassung",),
    ),
    Fall(
        "R-009",
        "kein-datumsformat",
        verletzt=True,
        zeilen=_SAUBER,
        roh={"person": {0: {"geburtsdatum": "1985-03-04"}}},
        spalten=("geburtsdatum",),
    ),
    # --- R-010 Zahlweise ----------------------------------------------------
    Fall("R-010", "jaehrlich", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-010",
        "schluessel-3-existiert-nicht",
        verletzt=True,
        zeilen={**_SAUBER, "anfrage": [{"zahlweise": 3}]},
        spalten=("zahlweise",),
    ),
    # --- R-011 Sparte -------------------------------------------------------
    Fall("R-011", "sparte-051", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-011",
        "unbekannte-sparte",
        verletzt=True,
        zeilen={**_SAUBER, "anfrage": [{"sparte": "099"}]},
        spalten=("sparte",),
    ),
    Fall(
        "R-011",
        "unbekannte-sparte-im-tarif",
        verletzt=True,
        zeilen={**_SAUBER, "tarif": [{"sparte": "099"}]},
        spalten=("sparte",),
    ),
    # --- R-012 Waehrung -----------------------------------------------------
    Fall("R-012", "eur", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-012",
        "gueltig-aber-unzulaessig",
        verletzt=True,
        zeilen={**_SAUBER, "anfrage": [{"waehrung": "CHF"}]},
        spalten=("waehrung",),
    ),
    Fall(
        "R-012",
        "nicht-im-iso-katalog",
        verletzt=True,
        zeilen={**_SAUBER, "anfrage": [{"waehrung": "XYZ"}]},
        spalten=("waehrung",),
    ),
    # --- R-013 SF-Klasse ----------------------------------------------------
    Fall("R-013", "sf10", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-013",
        "sonderklasse-ein-halb",
        verletzt=False,
        zeilen={**_SAUBER, "risiko_kfz": [{"sf_klasse_hp": "1/2"}]},
    ),
    Fall(
        "R-013",
        "sf99-existiert-nicht",
        verletzt=True,
        zeilen=_SAUBER,
        roh={"risiko_kfz": {0: {"sf_klasse_hp": "SF99"}}},
        spalten=("sf_klasse_hp",),
    ),
    # --- R-014 Typklassen ---------------------------------------------------
    Fall("R-014", "im-bereich", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-014",
        "typklasse-hp-unter-10",
        verletzt=True,
        zeilen={**_SAUBER, "risiko_kfz": [{"typklasse_hp": 9}]},
        spalten=("typklasse_hp",),
    ),
    Fall(
        "R-014",
        "typklasse-vk-ueber-34",
        verletzt=True,
        zeilen={**_SAUBER, "risiko_kfz": [{"typklasse_vk": 35}]},
        spalten=("typklasse_vk",),
    ),
    # --- R-015 Regionalklassen ---------------------------------------------
    Fall("R-015", "im-bereich", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-015",
        "regionalklasse-hp-ueber-12",
        verletzt=True,
        zeilen={**_SAUBER, "risiko_kfz": [{"regionalklasse_hp": 13}]},
        spalten=("regionalklasse_hp",),
    ),
    Fall(
        "R-015",
        "regionalklasse-vk-ueber-9",
        verletzt=True,
        zeilen={**_SAUBER, "risiko_kfz": [{"regionalklasse_vk": 10}]},
        spalten=("regionalklasse_vk",),
    ),
    # --- R-016 ZUERS-Zone ---------------------------------------------------
    Fall("R-016", "zone-1", verletzt=False, zeilen=_HAUSRAT),
    Fall(
        "R-016",
        "zone-5-existiert-nicht",
        verletzt=True,
        zeilen={**_HAUSRAT, "risiko_hausrat": [{"zuers_zone": 5}]},
        spalten=("zuers_zone",),
    ),
    # --- R-017 Bauartklasse -------------------------------------------------
    Fall("R-017", "bauartklasse-1", verletzt=False, zeilen=_HAUSRAT),
    Fall(
        "R-017",
        "buchstabe-j-existiert-nicht",
        verletzt=True,
        zeilen=_HAUSRAT,
        roh={"risiko_hausrat": {0: {"bauartklasse": "J"}}},
        spalten=("bauartklasse",),
    ),
    # --- R-018 Anfragestatus ------------------------------------------------
    Fall("R-018", "angebot", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-018",
        "unbekannter-status",
        verletzt=True,
        zeilen={**_SAUBER, "anfrage": [{"anfrage_status": "ERLEDIGT"}]},
        spalten=("anfrage_status",),
    ),
    # --- R-019 Nutzungsart --------------------------------------------------
    Fall("R-019", "privat", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-019",
        "schluessel-04-existiert-nicht",
        verletzt=True,
        zeilen={**_SAUBER, "risiko_kfz": [{"nutzungsart": "04"}]},
        spalten=("nutzungsart",),
    ),
    # --- R-020 Art des Kennzeichens ----------------------------------------
    Fall("R-020", "normal", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-020",
        "schluessel-02-existiert-nicht",
        verletzt=True,
        zeilen={**_SAUBER, "risiko_kfz": [{"art_kennzeichen": "02"}]},
        spalten=("art_kennzeichen",),
    ),
    # --- R-021 Nichtnegativitaet -------------------------------------------
    Fall("R-021", "alle-nicht-negativ", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-021",
        "negativer-nettobeitrag",
        verletzt=True,
        zeilen={**_SAUBER, "angebot": [{"nettobeitrag_jahr_eur": Decimal("-1.00")}]},
        spalten=("nettobeitrag_jahr_eur",),
    ),
    Fall(
        "R-021",
        "negatives-sublimit",
        verletzt=True,
        zeilen={**_HAUSRAT, "risiko_hausrat": [{"sublimit_fahrrad_eur": Decimal("-500.00")}]},
        spalten=("sublimit_fahrrad_eur",),
    ),
    # --- R-022 Wohnflaeche --------------------------------------------------
    Fall("R-022", "80-quadratmeter", verletzt=False, zeilen=_HAUSRAT),
    Fall(
        "R-022",
        "fuenf-quadratmeter",
        verletzt=True,
        zeilen={**_HAUSRAT, "risiko_hausrat": [{"wohnflaeche_qm": 5}]},
        spalten=("wohnflaeche_qm",),
    ),
    # --- R-023 Baujahr ------------------------------------------------------
    Fall("R-023", "1995", verletzt=False, zeilen=_HAUSRAT),
    Fall(
        "R-023",
        "baujahr-in-der-zukunft",
        verletzt=True,
        zeilen={**_HAUSRAT, "risiko_hausrat": [{"baujahr": 2030}]},
        spalten=("baujahr",),
    ),
    # --- R-024 Mindestdeckung ----------------------------------------------
    Fall("R-024", "unbegrenzte-deckung", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-024",
        "leere-deckungssummen-ausserhalb-der-haftpflicht",
        verletzt=False,
        zeilen={
            **_SAUBER,
            "tarif": [
                {
                    "sparte": "130",
                    "deckungsart": None,
                    "deckungssumme_personen_eur": None,
                    "deckungssumme_sach_eur": None,
                    "deckungssumme_vermoegen_eur": None,
                }
            ],
        },
    ),
    Fall(
        "R-024",
        "personenschaden-unter-mindestdeckung",
        verletzt=True,
        zeilen={**_SAUBER, "tarif": [{"deckungssumme_personen_eur": Decimal("1000000.00")}]},
        spalten=("deckungssumme_personen_eur",),
    ),
    # --- R-025 Implizite Fehlwerte -----------------------------------------
    Fall("R-025", "keine-sentinel", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-025",
        "leeres-optionales-feld-ist-kein-sentinel",
        verletzt=False,
        zeilen=_SAUBER,
        roh={"person": {0: {"email": ""}}},
    ),
    Fall(
        "R-025",
        "text-sentinel",
        verletzt=True,
        zeilen=_SAUBER,
        roh={"person": {0: {"vorname": "k.A."}}},
        spalten=("vorname",),
    ),
    Fall(
        "R-025",
        "datums-sentinel",
        verletzt=True,
        zeilen=_SAUBER,
        roh={"person": {0: {"geburtsdatum": "01011900"}}},
        spalten=("geburtsdatum",),
    ),
    Fall(
        "R-025",
        "numerisches-sentinel",
        verletzt=True,
        zeilen=_SAUBER,
        roh={"risiko_kfz": {0: {"leistung_kw": "9999"}}},
        spalten=("leistung_kw",),
    ),
    Fall(
        "R-025",
        "ausnahmefeld-jahresfahrleistung",
        verletzt=False,
        zeilen=_SAUBER,
        roh={"risiko_kfz": {0: {"jahresfahrleistung_km": "9999"}}},
    ),
)


@pytest.mark.parametrize("fall", FAELLE, ids=kennungen(FAELLE))
def test_regel(config: Config, fall: Fall) -> None:
    """Jede G1-Regel meldet den Verstoss und schweigt auf regelkonformen Daten."""
    pruefe_fall(config, fall)
