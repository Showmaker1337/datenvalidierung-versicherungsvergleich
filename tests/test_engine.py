"""Tests der Ausfuehrungsengine.

Der Kern ist die **Deduplizierung**. Ein einziger verfaelschter Wert loest oft
mehrere Regeln aus: Ein Datums-Sentinel wie ``00000000`` ist zugleich kein
existierender Kalendertag (R-009) und ein impliziter Fehlwert (R-025). Wuerde die
Auswertung beide Meldungen zaehlen, ergaebe ein einziger injizierter Fehler zwei
Treffer — und die Precision fiele, ohne dass der Detektor schlechter waere.

Die Vereinigungsmenge ``markierte_zellen`` verhindert das. Die Rohtreffer bleiben
daneben erhalten, weil die Diagnose je Regel sie braucht.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pandas as pd
import pytest

from src.common.pfade import Schicht
from src.rules.engine import (
    DETEKTIONEN_DATEI,
    MARKIERTE_ZELLEN_DATEI,
    SATZBEFUNDE_DATEI,
    TIMING_DATEI,
    ZELL_SPALTEN,
    pruefe_alles,
    schreibe_detektionen,
)
from src.rules.katalog import alle_regeln, regel
from src.rules.modell import VERSTOSS_SPALTEN, baue_kontext
from tests.test_regeln.bausteine import REFERENZ, VORGANG_KFZ, baue

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from pathlib import Path

    from src.common.config import Config
    from src.rules.modell import Kontext

#: Die beiden Regeln, die auf einem Datums-Sentinel gemeinsam anschlagen.
_DOPPELTREFFER = ("R-009", "R-025")


@pytest.fixture
def kontext_mit_sentinel(config: Config) -> Kontext:
    """Ein Vorgang, in dem ``person.geburtsdatum`` den Sentinel ``00000000`` traegt."""
    return baue(config, VORGANG_KFZ, roh={"person": {0: {"geburtsdatum": "00000000"}}})


def test_zwei_regeln_eine_zelle(kontext_mit_sentinel: Kontext) -> None:
    """Zwei Regeln auf derselben Zelle ergeben genau einen Eintrag in ``markierte_zellen``."""
    regeln = [regel(kennung) for kennung in _DOPPELTREFFER]
    detektionen = pruefe_alles(kontext_mit_sentinel, regeln)

    gemeldet = set(detektionen.verstoesse["regel_id"])
    assert gemeldet == set(_DOPPELTREFFER), (
        f"Erwartet wurden Meldungen beider Regeln, gemeldet haben {sorted(gemeldet)}"
    )
    assert len(detektionen.verstoesse) == 2, "Beide Rohtreffer muessen erhalten bleiben"
    assert len(detektionen.markierte_zellen) == 1, (
        "Die Vereinigungsmenge darf dieselbe Zelle nur einmal enthalten"
    )
    eintrag = detektionen.markierte_zellen.iloc[0]
    assert (eintrag["entitaet"], eintrag["spalte"]) == ("person", "geburtsdatum")


def test_verstoss_id_bindet_die_zellen_eines_constraints(config: Config) -> None:
    """Ein mehrspaltiger Verstoss traegt in allen Zellen dieselbe ``verstoss_id``.

    Ohne diese Bindung waere die constraint-basierte Sicht der Auswertung nicht
    rekonstruierbar: R-031 meldet Brutto, Netto und Steuer, der Injektor hat aber
    nur eine der drei Zellen verfaelscht.
    """
    from decimal import Decimal  # noqa: PLC0415 - nur hier gebraucht

    kontext = baue(
        config,
        {**VORGANG_KFZ, "angebot": [{"bruttobeitrag_jahr_eur": Decimal("600.00")}]},
    )
    detektionen = pruefe_alles(kontext, [regel("R-031")])

    assert len(detektionen.verstoesse) == 3, "R-031 meldet alle drei beteiligten Spalten"
    assert len(set(detektionen.verstoesse["verstoss_id"])) == 1, (
        "Alle drei Zellen gehoeren zu einem Constraint-Verstoss"
    )
    assert len(detektionen.markierte_zellen) == 3, (
        "Drei verschiedene Zellen bleiben auch nach der Dedup drei Eintraege"
    )


def test_spalten_und_leerer_lauf(config: Config) -> None:
    """Ein sauberer Vorgang erzeugt leere Ergebnisrahmen mit vollstaendigem Schema."""
    detektionen = pruefe_alles(baue(config, VORGANG_KFZ))

    assert detektionen.anzahl_meldungen == 0
    assert detektionen.anzahl_saetze == 0
    assert list(detektionen.verstoesse.columns) == list(VERSTOSS_SPALTEN)
    assert list(detektionen.markierte_zellen.columns) == list(ZELL_SPALTEN)


def test_laufzeit_je_regel(config: Config) -> None:
    """Die Laufzeitmessung deckt jede Regel des Katalogs ab."""
    detektionen = pruefe_alles(baue(config, VORGANG_KFZ))

    erwartet = {eintrag.regel_id for eintrag in alle_regeln()}
    assert set(detektionen.laufzeiten) == erwartet
    assert all(dauer >= 0.0 for dauer in detektionen.laufzeiten.values())


def test_diagnoseregeln_bleiben_aus_der_zellmetrik(config: Config) -> None:
    """Regeln mit ``in_zellmetrik=False`` erscheinen nicht in ``markierte_zellen``."""
    ausgenommen = [eintrag for eintrag in alle_regeln() if not eintrag.in_zellmetrik]
    assert ausgenommen, "Der Katalog soll Diagnoseregeln enthalten (R-047, R-048)"

    from decimal import Decimal  # noqa: PLC0415 - nur hier gebraucht

    kontext = baue(
        config,
        {
            **VORGANG_KFZ,
            "tarif": [{"tarif_id": "T1"}, {"tarif_id": "T2"}],
            "angebot": [
                {"angebot_id": "G1", "rang": 1, "zahlbeitrag_rate_eur": Decimal("100.00")},
                {
                    "angebot_id": "G2",
                    "tarif_id": "T2",
                    "rang": 2,
                    "zahlbeitrag_rate_eur": Decimal("1000.00"),
                },
            ],
        },
    )
    detektionen = pruefe_alles(kontext, ausgenommen)

    assert detektionen.anzahl_saetze > 0, "R-047 muss die Spreizung satzbezogen melden"
    assert detektionen.markierte_zellen.empty, (
        "Eine Diagnosekennzahl darf keine Zelle in die Metrik einbringen"
    )


def test_artefakte_werden_geschrieben(
    config: Config, kontext_mit_sentinel: Kontext, tmp_path: Path
) -> None:
    """Rohtreffer, Vereinigungsmenge, Satzbefunde und Laufzeiten landen auf der Platte."""
    import dataclasses  # noqa: PLC0415 - nur hier gebraucht

    lauf_config = dataclasses.replace(
        config, pfade=dataclasses.replace(config.pfade, runs=tmp_path)
    )
    detektionen = pruefe_alles(kontext_mit_sentinel, [regel(kennung) for kennung in _DOPPELTREFFER])
    ziel = schreibe_detektionen(lauf_config, "testlauf", detektionen, unterordner="clean")

    for datei in (DETEKTIONEN_DATEI, MARKIERTE_ZELLEN_DATEI, SATZBEFUNDE_DATEI, TIMING_DATEI):
        assert (ziel / datei).is_file(), f"{datei} fehlt"

    gelesen = pd.read_parquet(ziel / DETEKTIONEN_DATEI)
    assert list(gelesen.columns) == list(VERSTOSS_SPALTEN)
    assert len(gelesen) == 2

    timing = json.loads((ziel / TIMING_DATEI).read_text(encoding="utf-8"))
    assert set(timing["laufzeit_sekunden_je_regel"]) == set(_DOPPELTREFFER)


def test_kontext_ergaenzt_fehlende_entitaeten(config: Config) -> None:
    """Ein Kontext aus einer Entitaet fuellt die uebrigen leer und schemakonform auf.

    Ohne diese Ergaenzung muesste jeder Regeltest alle sieben Entitaeten bauen,
    auch die, um die es gar nicht geht.
    """
    kontext = baue_kontext(config, typed={}, referenz=REFERENZ)
    for entitaet in ("anfrage", "person", "angebot"):
        assert kontext.rahmen(Schicht.TYPED, entitaet).empty
        assert kontext.rahmen(Schicht.RAW, entitaet).empty

    detektionen = pruefe_alles(kontext)
    assert detektionen.anzahl_meldungen == 0
    assert detektionen.anzahl_saetze == 0
