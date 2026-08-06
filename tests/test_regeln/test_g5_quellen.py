"""Regeltests der Gruppe G5 (R-052 bis R-058).

G5 ist die Gruppe der Multi-Source-Fehler. Drei Faelle sind hier besonders:

* **R-052** braucht drei Angebote. Bei zweien gaebe es keine Mehrheit, an der sich
  die Regel ausrichten koennte — der Testfall belegt genau die Heuristik, die im
  Regeldocstring beschrieben ist.
* **R-054** braucht ebenfalls drei bepreiste Angebote: Der Median der *uebrigen*
  ist erst ab zwei Vergleichswerten aussagekraeftig.
* **R-057** wird ueber den Eingangskanal gesteuert. Der Standardvorgang laeuft
  ueber MAKLER, also das GDV-Profil: Strasse und Hausnummer sind dort Pflicht, die
  E-Mail-Adresse nicht.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import TYPE_CHECKING, Any

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

#: Grundform eines Hausrat-Angebots mit Selbstbehalt als Betrag.
_HAUSRAT_ANGEBOT: dict[str, Any] = dict(_HAUSRAT["angebot"][0])


def _hausrat_angebote(*abweichungen: dict[str, Any]) -> list[dict[str, Any]]:
    """Baut mehrere Hausrat-Angebote derselben Anfrage."""
    return [
        {
            **_HAUSRAT_ANGEBOT,
            "angebot_id": f"G{nummer}",
            "tarif_id": "T1",
            "rang": nummer,
            **abweichung,
        }
        for nummer, abweichung in enumerate(abweichungen, start=1)
    ]


def _kfz_angebote(*brutto: str) -> list[dict[str, Any]]:
    """Baut mehrere Kfz-Angebote derselben Anfrage mit vorgegebenem Bruttobeitrag."""
    return [
        {
            "angebot_id": f"G{nummer}",
            "rang": nummer,
            "bruttobeitrag_jahr_eur": Decimal(wert),
            "zahlbeitrag_rate_eur": Decimal(wert),
        }
        for nummer, wert in enumerate(brutto, start=1)
    ]


FAELLE: tuple[Fall, ...] = (
    # --- R-052 Einheitenkonvention des Selbstbehalts ------------------------
    Fall(
        "R-052",
        "alle-angebote-in-euro",
        verletzt=False,
        zeilen={**_HAUSRAT, "angebot": _hausrat_angebote({}, {}, {})},
    ),
    Fall(
        "R-052",
        "ein-anbieter-liefert-prozent",
        verletzt=True,
        zeilen={
            **_HAUSRAT,
            "angebot": _hausrat_angebote(
                {},
                {},
                {"sb_hausrat_eur": None, "sb_hausrat_prozent": Decimal("10.00")},
            ),
        },
        spalten=("sb_hausrat_prozent",),
    ),
    # --- R-053 Beitragskorridor je Sparte -----------------------------------
    Fall("R-053", "im-korridor", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-053",
        "cent-statt-euro",
        verletzt=True,
        zeilen={**_SAUBER, "angebot": [{"bruttobeitrag_jahr_eur": Decimal("59500.00")}]},
        spalten=("bruttobeitrag_jahr_eur",),
    ),
    Fall(
        "R-053",
        "hausratkorridor-ueberschritten",
        verletzt=True,
        zeilen={
            **_HAUSRAT,
            "angebot": [{**_HAUSRAT_ANGEBOT, "bruttobeitrag_jahr_eur": Decimal("5000.00")}],
        },
        spalten=("bruttobeitrag_jahr_eur",),
    ),
    # --- R-054 Monats- statt Jahresbeitrag ----------------------------------
    Fall(
        "R-054",
        "aehnliche-beitraege",
        verletzt=False,
        zeilen={**_SAUBER, "angebot": _kfz_angebote("600.00", "610.00", "620.00")},
    ),
    Fall(
        "R-054",
        "zwei-angebote-werden-uebersprungen",
        verletzt=False,
        zeilen={**_SAUBER, "angebot": _kfz_angebote("600.00", "50.00")},
    ),
    Fall(
        "R-054",
        "ein-angebot-ist-ein-zwoelftel",
        verletzt=True,
        zeilen={**_SAUBER, "angebot": _kfz_angebote("50.00", "600.00", "610.00")},
        spalten=("bruttobeitrag_jahr_eur",),
    ),
    # --- R-055 Tarifstand ---------------------------------------------------
    Fall("R-055", "im-gueltigkeitsfenster", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-055",
        "veralteter-tarifstand",
        verletzt=True,
        zeilen={
            **_SAUBER,
            "angebot": [
                {"berechnungszeitpunkt": dt.datetime(2025, 1, 15, 10, 0, 30)}  # noqa: DTZ001
            ],
        },
        spalten=("berechnungszeitpunkt", "tarif_id"),
    ),
    # --- R-056 Gueltigkeitszeitraum -----------------------------------------
    Fall("R-056", "ende-nach-beginn", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-056",
        "ende-vor-beginn",
        verletzt=True,
        zeilen={**_SAUBER, "tarif": [{"gueltig_bis": dt.date(2025, 1, 1)}]},
        spalten=("gueltig_bis", "gueltig_ab"),
    ),
    # --- R-057 Pflichtfeldprofil --------------------------------------------
    Fall("R-057", "profil-eingehalten", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-057",
        "email-bei-gdv-optional",
        verletzt=False,
        zeilen={**_SAUBER, "person": [{"email": None}]},
    ),
    Fall(
        "R-057",
        "selbstbehalt-in-der-haftpflicht-nicht-anwendbar",
        verletzt=False,
        zeilen={**_SAUBER, "angebot": [{"sb_tk_eur": None, "sb_vk_eur": None}]},
    ),
    Fall(
        "R-057",
        "firma-ohne-familienstand-nicht-anwendbar",
        verletzt=False,
        zeilen={
            **_SAUBER,
            "anfrage": [{"kanal": "APP"}],
            "person": [
                {
                    "anrede": "FIRMA",
                    "vorname": None,
                    "geburtsdatum": None,
                    "familienstand": None,
                }
            ],
        },
    ),
    Fall(
        "R-057",
        "strasse-bei-gdv-pflicht",
        verletzt=True,
        zeilen={**_SAUBER, "person": [{"strasse": None}]},
        spalten=("strasse",),
    ),
    Fall(
        "R-057",
        "email-bei-bipro-pflicht",
        verletzt=True,
        zeilen={**_SAUBER, "anfrage": [{"kanal": "APP"}], "person": [{"email": None}]},
        spalten=("email",),
    ),
    Fall(
        "R-057",
        "vollkasko-selbstbehalt-fehlt",
        verletzt=True,
        zeilen={
            **_SAUBER,
            "anfrage": [{"sparte": "052"}],
            "angebot": [{"sb_tk_eur": Decimal("150.00"), "sb_vk_eur": None}],
        },
        spalten=("sb_vk_eur",),
    ),
    # --- R-058 Regionalklassen ----------------------------------------------
    Fall("R-058", "klassen-stimmen", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-058",
        "bezirk-nicht-in-der-referenz",
        verletzt=True,
        zeilen={**_SAUBER, "risiko_kfz": [{"zulassungsbezirk": "XX"}]},
        spalten=("zulassungsbezirk",),
    ),
    Fall(
        "R-058",
        "haftpflichtklasse-weicht-ab",
        verletzt=True,
        zeilen={**_SAUBER, "risiko_kfz": [{"regionalklasse_hp": 9}]},
        spalten=("regionalklasse_hp",),
    ),
)


@pytest.mark.parametrize("fall", FAELLE, ids=kennungen(FAELLE))
def test_regel(config: Config, fall: Fall) -> None:
    """Jede G5-Regel meldet den Verstoss und schweigt auf regelkonformen Daten."""
    pruefe_fall(config, fall)
