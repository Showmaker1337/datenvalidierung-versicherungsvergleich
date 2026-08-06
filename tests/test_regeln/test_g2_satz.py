"""Regeltests der Gruppe G2 (R-026 bis R-042).

Alle Faelle arbeiten auf der typisierten Schicht: G2 prueft Beziehungen zwischen
Feldern eines Satzes, nicht ihre Schreibweise.

Zwei Faelle verdienen einen Blick. **R-034** braucht eine steuerfreie Sparte; sie
kommt im Datenmodell nicht vor, weshalb der Testfall sie ausdruecklich setzt — die
Regel ist damit geprueft, obwohl sie im Experiment nie ausloest. **R-041** wird nur
in der Hausratsparte geprueft; der dritte Fall belegt, dass ein Kfz-Angebot ohne
Hausrat-Selbstbehalt kein Verstoss ist.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from tests.test_regeln.bausteine import (
    VORGANG_HAUSRAT,
    VORGANG_KFZ,
    Fall,
    kennungen,
    pruefe_fall,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from src.common.config import Config

_SAUBER = VORGANG_KFZ
_HAUSRAT = VORGANG_HAUSRAT

#: Die sechs Beitragsfelder eines Angebots, alle leer (R-037).
_OHNE_BEITRAG: dict[str, object] = {
    "annahmeentscheidung": "ABLEHNUNG",
    "rang": None,
    "nettobeitrag_jahr_eur": None,
    "versicherungsteuer_satz": None,
    "versicherungsteuer_eur": None,
    "bruttobeitrag_jahr_eur": None,
    "ratenzahlungszuschlag_prozent": None,
    "zahlbeitrag_rate_eur": None,
}


FAELLE: tuple[Fall, ...] = (
    # --- R-026 Erstzulassung ------------------------------------------------
    Fall("R-026", "vor-dem-stichtag", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-026",
        "in-der-zukunft",
        verletzt=True,
        zeilen={
            **_SAUBER,
            "risiko_kfz": [
                {"erstzulassung": dt.date(2027, 1, 1), "zulassung_auf_vn": dt.date(2027, 2, 1)}
            ],
        },
        spalten=("erstzulassung",),
    ),
    # --- R-027 Zulassung auf den Versicherungsnehmer ------------------------
    Fall("R-027", "in-richtiger-reihenfolge", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-027",
        "zulassung-vor-erstzulassung",
        verletzt=True,
        zeilen={**_SAUBER, "risiko_kfz": [{"zulassung_auf_vn": dt.date(2017, 1, 1)}]},
        spalten=("zulassung_auf_vn", "erstzulassung"),
    ),
    Fall(
        "R-027",
        "zulassung-nach-dem-stichtag",
        verletzt=True,
        zeilen={**_SAUBER, "risiko_kfz": [{"zulassung_auf_vn": dt.date(2027, 1, 1)}]},
        spalten=("zulassung_auf_vn",),
    ),
    # --- R-028 Fuehrerschein ------------------------------------------------
    Fall("R-028", "erwerb-mit-18", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-028",
        "erwerb-vor-dem-17-geburtstag",
        verletzt=True,
        zeilen={**_SAUBER, "person": [{"fuehrerschein_datum": dt.date(1999, 1, 1)}]},
        spalten=("fuehrerschein_datum",),
    ),
    Fall(
        "R-028",
        "erwerb-nach-dem-stichtag",
        verletzt=True,
        zeilen={**_SAUBER, "person": [{"fuehrerschein_datum": dt.date(2027, 1, 1)}]},
        spalten=("fuehrerschein_datum",),
    ),
    # --- R-029 Schadenfreie Jahre gegen das Alter ---------------------------
    Fall("R-029", "sf10-bei-41-jahren", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-029",
        "sonderklasse-erfuellt-trivial",
        verletzt=False,
        zeilen={**_SAUBER, "risiko_kfz": [{"sf_klasse_hp": "M"}]},
    ),
    Fall(
        "R-029",
        "sf40-bei-41-jahren",
        verletzt=True,
        zeilen={**_SAUBER, "risiko_kfz": [{"sf_klasse_hp": "SF40"}]},
        spalten=("sf_klasse_hp",),
    ),
    # --- R-030 Ordnung der SF-Klassen ---------------------------------------
    Fall(
        "R-030",
        "vollkasko-schlechter-eingestuft",
        verletzt=False,
        zeilen={**_SAUBER, "risiko_kfz": [{"sf_klasse_vk": "SF5"}]},
    ),
    Fall(
        "R-030",
        "vollkasko-besser-eingestuft",
        verletzt=True,
        zeilen={**_SAUBER, "risiko_kfz": [{"sf_klasse_vk": "SF20"}]},
        spalten=("sf_klasse_vk",),
    ),
    # --- R-031 Beitragsarithmetik -------------------------------------------
    Fall("R-031", "brutto-ist-netto-plus-steuer", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-031",
        "innerhalb-der-toleranz",
        verletzt=False,
        zeilen={**_SAUBER, "angebot": [{"bruttobeitrag_jahr_eur": Decimal("595.02")}]},
    ),
    Fall(
        "R-031",
        "brutto-passt-nicht",
        verletzt=True,
        zeilen={**_SAUBER, "angebot": [{"bruttobeitrag_jahr_eur": Decimal("600.00")}]},
        spalten=(
            "bruttobeitrag_jahr_eur",
            "nettobeitrag_jahr_eur",
            "versicherungsteuer_eur",
        ),
    ),
    # --- R-032 Steuerbetrag -------------------------------------------------
    Fall("R-032", "steuer-korrekt-gerundet", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-032",
        "steuer-falsch-berechnet",
        verletzt=True,
        zeilen={**_SAUBER, "angebot": [{"versicherungsteuer_eur": Decimal("90.00")}]},
        spalten=("versicherungsteuer_eur", "versicherungsteuer_satz"),
    ),
    # --- R-033 Effektivsatz je Sparte (CFD) ---------------------------------
    Fall("R-033", "19-prozent-in-der-kfz-sparte", verletzt=False, zeilen=_SAUBER),
    Fall("R-033", "16-15-prozent-im-hausrat", verletzt=False, zeilen=_HAUSRAT),
    Fall(
        "R-033",
        "hausratsatz-in-der-kfz-sparte",
        verletzt=True,
        zeilen={**_SAUBER, "angebot": [{"versicherungsteuer_satz": Decimal("16.15")}]},
        spalten=("versicherungsteuer_satz",),
    ),
    # --- R-034 Steuerfreie Sparten (im Datenmodell nicht ausloesbar) --------
    Fall(
        "R-034",
        "steuerfreie-sparte-ohne-steuer",
        verletzt=False,
        zeilen={
            **_SAUBER,
            "anfrage": [{"sparte": "010"}],
            "angebot": [{"versicherungsteuer_eur": Decimal("0.00")}],
        },
    ),
    Fall("R-034", "steuerpflichtige-sparte-mit-steuer", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-034",
        "steuerfreie-sparte-mit-steuer",
        verletzt=True,
        zeilen={**_SAUBER, "anfrage": [{"sparte": "010"}]},
        spalten=("versicherungsteuer_eur",),
    ),
    # --- R-035 Ratenzuschlag ohne Ratenzahlung ------------------------------
    Fall("R-035", "jaehrlich-ohne-zuschlag", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-035",
        "monatlich-mit-zuschlag",
        verletzt=False,
        zeilen={
            **_SAUBER,
            "anfrage": [{"zahlweise": 8}],
            "angebot": [
                {
                    "ratenzahlungszuschlag_prozent": Decimal("3.00"),
                    "zahlbeitrag_rate_eur": Decimal("51.06"),
                }
            ],
        },
    ),
    Fall(
        "R-035",
        "jaehrlich-mit-zuschlag",
        verletzt=True,
        zeilen={**_SAUBER, "angebot": [{"ratenzahlungszuschlag_prozent": Decimal("3.00")}]},
        spalten=("ratenzahlungszuschlag_prozent",),
    ),
    # --- R-036 Unterjaehrige Zahlung ----------------------------------------
    Fall("R-036", "jaehrliche-zahlung", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-036",
        "zwoelf-raten-mit-rundungsverlust",
        verletzt=False,
        zeilen={
            **_SAUBER,
            "anfrage": [{"zahlweise": 8}],
            "angebot": [{"zahlbeitrag_rate_eur": Decimal("49.59")}],
        },
    ),
    Fall(
        "R-036",
        "zwoelf-raten-guenstiger-als-jaehrlich",
        verletzt=True,
        zeilen={
            **_SAUBER,
            "anfrage": [{"zahlweise": 8}],
            "angebot": [{"zahlbeitrag_rate_eur": Decimal("40.00")}],
        },
        spalten=("zahlbeitrag_rate_eur", "bruttobeitrag_jahr_eur"),
    ),
    # --- R-037 Ablehnung und Beitragsfelder ---------------------------------
    Fall("R-037", "annahme-mit-beitrag", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-037",
        "ablehnung-ohne-beitrag",
        verletzt=False,
        zeilen={**_SAUBER, "angebot": [_OHNE_BEITRAG]},
    ),
    Fall(
        "R-037",
        "ablehnung-mit-beitrag",
        verletzt=True,
        zeilen={**_SAUBER, "angebot": [{"annahmeentscheidung": "ABLEHNUNG"}]},
        spalten=("annahmeentscheidung", "nettobeitrag_jahr_eur"),
    ),
    Fall(
        "R-037",
        "annahme-ohne-beitrag",
        verletzt=True,
        zeilen={**_SAUBER, "angebot": [{**_OHNE_BEITRAG, "annahmeentscheidung": "ANNAHME"}]},
        spalten=("annahmeentscheidung", "bruttobeitrag_jahr_eur"),
    ),
    # --- R-038 Fahrzeugwert -------------------------------------------------
    Fall("R-038", "restwert-unter-neupreis", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-038",
        "restwert-ueber-neupreis",
        verletzt=True,
        zeilen={**_SAUBER, "risiko_kfz": [{"fahrzeugwert_aktuell": Decimal("40000.00")}]},
        spalten=("fahrzeugwert_aktuell", "neupreis_eur"),
    ),
    # --- R-039 E-Kennzeichen ------------------------------------------------
    Fall("R-039", "normales-kennzeichen", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-039",
        "e-kennzeichen-mit-elektroantrieb",
        verletzt=False,
        zeilen={
            **_SAUBER,
            "risiko_kfz": [{"art_kennzeichen": "54", "antriebsart": "ELEKTRO"}],
        },
    ),
    Fall(
        "R-039",
        "e-kennzeichen-mit-benziner",
        verletzt=True,
        zeilen={**_SAUBER, "risiko_kfz": [{"art_kennzeichen": "54"}]},
        spalten=("art_kennzeichen", "antriebsart"),
    ),
    # --- R-040 Unterversicherungsverzicht -----------------------------------
    Fall("R-040", "summe-reicht-aus", verletzt=False, zeilen=_HAUSRAT),
    Fall(
        "R-040",
        "ohne-verzicht-keine-untergrenze",
        verletzt=False,
        zeilen={
            **_HAUSRAT,
            "risiko_hausrat": [
                {
                    "unterversicherungsverzicht": False,
                    "versicherungssumme_eur": Decimal("10000.00"),
                    "sublimit_wertsachen_eur": Decimal("2000.00"),
                }
            ],
        },
    ),
    Fall(
        "R-040",
        "verzicht-bei-zu-kleiner-summe",
        verletzt=True,
        zeilen={
            **_HAUSRAT,
            "risiko_hausrat": [
                {
                    "versicherungssumme_eur": Decimal("10000.00"),
                    "sublimit_fahrrad_eur": Decimal("500.00"),
                    "sublimit_wertsachen_eur": Decimal("2000.00"),
                }
            ],
        },
        spalten=("versicherungssumme_eur", "wohnflaeche_qm"),
    ),
    # --- R-041 Exklusivitaet des Hausrat-Selbstbehalts ----------------------
    Fall("R-041", "genau-ein-feld-gefuellt", verletzt=False, zeilen=_HAUSRAT),
    Fall("R-041", "kfz-sparte-nicht-anwendbar", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-041",
        "beide-felder-gefuellt",
        verletzt=True,
        zeilen={
            **_HAUSRAT,
            "angebot": [
                {
                    **_HAUSRAT["angebot"][0],
                    "sb_hausrat_prozent": Decimal("10.00"),
                }
            ],
        },
        spalten=("sb_hausrat_prozent", "sb_hausrat_eur"),
    ),
    Fall(
        "R-041",
        "kein-feld-gefuellt",
        verletzt=True,
        zeilen={
            **_HAUSRAT,
            "angebot": [{**_HAUSRAT["angebot"][0], "sb_hausrat_eur": None}],
        },
        spalten=("sb_hausrat_prozent", "sb_hausrat_eur"),
    ),
    # --- R-042 Sublimits ----------------------------------------------------
    Fall("R-042", "sublimits-unter-der-summe", verletzt=False, zeilen=_HAUSRAT),
    Fall(
        "R-042",
        "fahrradsublimit-ueber-der-summe",
        verletzt=True,
        zeilen={
            **_HAUSRAT,
            "risiko_hausrat": [{"sublimit_fahrrad_eur": Decimal("70000.00")}],
        },
        spalten=("sublimit_fahrrad_eur", "versicherungssumme_eur"),
    ),
)


@pytest.mark.parametrize("fall", FAELLE, ids=kennungen(FAELLE))
def test_regel(config: Config, fall: Fall) -> None:
    """Jede G2-Regel meldet den Verstoss und schweigt auf regelkonformen Daten."""
    pruefe_fall(config, fall)
