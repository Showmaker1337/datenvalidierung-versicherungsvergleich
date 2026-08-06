"""Regeltests der Gruppe G3 (R-043 bis R-048).

G3 prueft Bedingungen zwischen Zeilen derselben Tabelle. Die Faelle brauchen
deshalb mehrere Zeilen je Entitaet — ein einzelnes Angebot kann weder eine
Rangfolge noch ein Duplikat verletzen.

R-047 und R-048 melden **satzbezogen** und nicht auf Zellebene; ihre Faelle tragen
deshalb ``satzbezogen=True``. Fuer R-048 wird eine Verteilung mit tausend
Hausratzeilen gebaut: Eine Verteilungspruefung braucht eine Verteilung, und mit
zehn Zeilen waere die kleinste Zone (0,4 Prozent) nicht darstellbar.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest

from src.common.wertebereiche import ZUERS_ANTEILE_GDV, ZUERS_ZONEN
from tests.test_regeln.bausteine import VORGANG_HAUSRAT, VORGANG_KFZ, Fall, kennungen, pruefe_fall

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from src.common.config import Config

_SAUBER = VORGANG_KFZ

#: Zwei bepreiste Angebote derselben Anfrage in richtiger Rangfolge.
_ZWEI_ANGEBOTE: list[dict[str, Any]] = [
    {
        "angebot_id": "G1",
        "tarif_id": "T1",
        "rang": 1,
        "zahlbeitrag_rate_eur": Decimal("500.00"),
    },
    {
        "angebot_id": "G2",
        "tarif_id": "T2",
        "rang": 2,
        "zahlbeitrag_rate_eur": Decimal("700.00"),
    },
]

#: Zwei Tarifzeilen, damit die Angebote auf verschiedene Tarife zeigen koennen.
_ZWEI_TARIFE: list[dict[str, Any]] = [{"tarif_id": "T1"}, {"tarif_id": "T2"}]


def _zuers_verteilung(anzahl: int) -> list[dict[str, Any]]:
    """Baut Hausratzeilen in den vom GDV publizierten ZUERS-Anteilen.

    Die Zellzahlen stehen vorab fest; damit prueft der positive Fall die Regel und
    nicht die Streuung einer Ziehung.
    """
    zeilen: list[dict[str, Any]] = []
    for index, zone in enumerate(ZUERS_ZONEN[:-1]):
        zeilen.extend([{"zuers_zone": zone}] * round(anzahl * ZUERS_ANTEILE_GDV[index]))
    zeilen.extend([{"zuers_zone": ZUERS_ZONEN[-1]}] * (anzahl - len(zeilen)))
    return zeilen


FAELLE: tuple[Fall, ...] = (
    # --- R-043 Rangfolge ----------------------------------------------------
    Fall(
        "R-043",
        "lueckenlos-1-bis-2",
        verletzt=False,
        zeilen={**_SAUBER, "tarif": _ZWEI_TARIFE, "angebot": _ZWEI_ANGEBOTE},
    ),
    Fall(
        "R-043",
        "abgelehntes-angebot-ohne-rang",
        verletzt=False,
        zeilen={
            **_SAUBER,
            "tarif": _ZWEI_TARIFE,
            "angebot": [
                _ZWEI_ANGEBOTE[0],
                {
                    **_ZWEI_ANGEBOTE[1],
                    "rang": None,
                    "annahmeentscheidung": "ABLEHNUNG",
                },
            ],
        },
    ),
    Fall(
        "R-043",
        "rang-doppelt-vergeben",
        verletzt=True,
        zeilen={
            **_SAUBER,
            "tarif": _ZWEI_TARIFE,
            "angebot": [_ZWEI_ANGEBOTE[0], {**_ZWEI_ANGEBOTE[1], "rang": 1}],
        },
        spalten=("rang",),
    ),
    Fall(
        "R-043",
        "bepreistes-angebot-ohne-rang",
        verletzt=True,
        zeilen={
            **_SAUBER,
            "tarif": _ZWEI_TARIFE,
            "angebot": [_ZWEI_ANGEBOTE[0], {**_ZWEI_ANGEBOTE[1], "rang": None}],
        },
        spalten=("rang",),
    ),
    # --- R-044 Sortierung nach Preis ----------------------------------------
    Fall(
        "R-044",
        "aufsteigend-nach-rate",
        verletzt=False,
        zeilen={**_SAUBER, "tarif": _ZWEI_TARIFE, "angebot": _ZWEI_ANGEBOTE},
    ),
    Fall(
        "R-044",
        "gleiche-raten-sind-zulaessig",
        verletzt=False,
        zeilen={
            **_SAUBER,
            "tarif": _ZWEI_TARIFE,
            "angebot": [
                _ZWEI_ANGEBOTE[0],
                {**_ZWEI_ANGEBOTE[1], "zahlbeitrag_rate_eur": Decimal("500.00")},
            ],
        },
    ),
    Fall(
        "R-044",
        "rang-1-ist-teurer",
        verletzt=True,
        zeilen={
            **_SAUBER,
            "tarif": _ZWEI_TARIFE,
            "angebot": [
                {**_ZWEI_ANGEBOTE[0], "zahlbeitrag_rate_eur": Decimal("900.00")},
                {**_ZWEI_ANGEBOTE[1], "zahlbeitrag_rate_eur": Decimal("100.00")},
            ],
        },
        spalten=("rang", "zahlbeitrag_rate_eur"),
    ),
    # --- R-045 Duplikate ----------------------------------------------------
    Fall(
        "R-045",
        "verschiedene-tarife",
        verletzt=False,
        zeilen={**_SAUBER, "tarif": _ZWEI_TARIFE, "angebot": _ZWEI_ANGEBOTE},
    ),
    Fall(
        "R-045",
        "derselbe-tarif-zweimal",
        verletzt=True,
        zeilen={
            **_SAUBER,
            "angebot": [_ZWEI_ANGEBOTE[0], {**_ZWEI_ANGEBOTE[1], "tarif_id": "T1"}],
        },
        spalten=("anfrage_id", "tarif_id"),
    ),
    # --- R-046 Genau ein Versicherungsnehmer --------------------------------
    Fall(
        "R-046",
        "ein-vn-und-eine-vp",
        verletzt=False,
        zeilen={
            **_SAUBER,
            "person": [{}, {"person_id": "P2", "rolle": "VP", "nachname": "Beispiel"}],
        },
    ),
    Fall(
        "R-046",
        "zwei-versicherungsnehmer",
        verletzt=True,
        zeilen={**_SAUBER, "person": [{}, {"person_id": "P2", "nachname": "Beispiel"}]},
        spalten=("rolle",),
    ),
    Fall(
        "R-046",
        "kein-versicherungsnehmer",
        verletzt=True,
        zeilen={**_SAUBER, "person": [{"rolle": "VP"}]},
        satzbezogen=True,
    ),
    # --- R-047 Beitragsspreizung (Diagnosekennzahl) -------------------------
    Fall(
        "R-047",
        "spreizung-unter-der-schwelle",
        verletzt=False,
        zeilen={**_SAUBER, "tarif": _ZWEI_TARIFE, "angebot": _ZWEI_ANGEBOTE},
        satzbezogen=True,
    ),
    Fall(
        "R-047",
        "spreizung-faktor-zehn",
        verletzt=True,
        zeilen={
            **_SAUBER,
            "tarif": _ZWEI_TARIFE,
            "angebot": [
                {**_ZWEI_ANGEBOTE[0], "zahlbeitrag_rate_eur": Decimal("100.00")},
                {**_ZWEI_ANGEBOTE[1], "zahlbeitrag_rate_eur": Decimal("1000.00")},
            ],
        },
        satzbezogen=True,
    ),
    # --- R-048 ZUERS-Verteilung (Diagnosekennzahl) --------------------------
    Fall(
        "R-048",
        "verteilung-wie-publiziert",
        verletzt=False,
        zeilen={
            **VORGANG_HAUSRAT,
            "risiko_hausrat": _zuers_verteilung(1000),
        },
        satzbezogen=True,
    ),
    Fall(
        "R-048",
        "alle-in-zone-vier",
        verletzt=True,
        zeilen={
            **VORGANG_HAUSRAT,
            "risiko_hausrat": [{"zuers_zone": 4}] * 100,
        },
        satzbezogen=True,
    ),
)


@pytest.mark.parametrize("fall", FAELLE, ids=kennungen(FAELLE))
def test_regel(config: Config, fall: Fall) -> None:
    """Jede G3-Regel meldet den Verstoss und schweigt auf regelkonformen Daten."""
    pruefe_fall(config, fall)
