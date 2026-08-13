"""Prueft, dass der verfaelschte Datensatz nach einem Lauf nicht liegen bleibt.

Bei rund tausend Laeufen zu je mehreren zehntausend Zeilen entstuenden sonst
zweistellige Gigabyte (CLAUDE.md, Abschnitt 3). Der verfaelschte Datensatz ist
aus ``seed_basis`` und ``seed_inject`` jederzeit exakt wiederherstellbar; ihn
aufzubewahren waere Speicherverbrauch ohne Gegenwert.

Der Test prueft beide Richtungen: Was **nicht** bleiben darf, ist weg, und was
bleiben **muss**, ist da. Nur die erste Haelfte zu pruefen waere gefaehrlich —
ein Lauf, der gar nichts schreibt, bestuende sie muehelos.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from scripts import run_experiment
from src.common.config import lade_config
from src.common.pfade import DIRTY, Artefakt, experiment_verzeichnis
from src.evaluation.experimentplan import lade_plan, laeufe
from tests.experimentumgebung import baue_plan, baue_umgebung, mini_plan

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from pathlib import Path

#: Artefakte, die dauerhaft aufbewahrt werden.
BLEIBT = (
    Artefakt.ERROR_LOG.value,
    Artefakt.ERROR_LOG_RECORDS.value,
    Artefakt.METRICS.value,
    Artefakt.MANIFEST.value,
    Artefakt.CONFIG.value,
)

#: Artefakte, die nach dem Lauf nicht mehr existieren duerfen.
GEHT_WEG = (
    Artefakt.DF_RAW_DIRTY.value,
    Artefakt.DF_RAW_CLEAN.value,
    Artefakt.DF_TYPED_CLEAN.value,
)


@pytest.fixture(scope="module")
def gerechnet(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Faehrt ein sehr kleines Experiment."""
    verzeichnis = tmp_path_factory.mktemp("speicher")
    fach_config = baue_umgebung(verzeichnis)
    plan = baue_plan(
        verzeichnis,
        mini_plan(
            serie="sp",
            klassen=("F3",),
            raten=(0.02,),
            verfahren=("prototyp",),
            wiederholungen=2,
        ),
    )
    assert (
        run_experiment.main(
            ["--config", str(plan), "--fach-config", str(fach_config), "--worker", "1"]
        )
        == 0
    )
    return (fach_config, plan)


def test_verfaelschter_datensatz_bleibt_nicht_liegen(gerechnet: tuple[Path, Path]) -> None:
    """Weder ``dirty/`` noch die Parquet-Dateien der Datensaetze existieren."""
    fach_config, planpfad = gerechnet
    config = lade_config(fach_config)
    plan = lade_plan(planpfad)
    for lauf in laeufe(plan):
        ziel = experiment_verzeichnis(
            config, lauf.serie, lauf.design, lauf.segment, lauf.fehlerrate, lauf.wiederholung
        )
        assert not (ziel / DIRTY).exists(), f"{lauf.run_id}: {DIRTY} liegt noch da"
        vorhanden = [name for name in GEHT_WEG if (ziel / name).exists()]
        assert not vorhanden, f"{lauf.run_id}: {vorhanden} liegen noch da"


def test_ground_truth_und_kennzahlen_bleiben(gerechnet: tuple[Path, Path]) -> None:
    """Die dauerhaft aufzubewahrenden Artefakte sind vorhanden und nicht leer."""
    fach_config, planpfad = gerechnet
    config = lade_config(fach_config)
    plan = lade_plan(planpfad)
    for lauf in laeufe(plan):
        ziel = experiment_verzeichnis(
            config, lauf.serie, lauf.design, lauf.segment, lauf.fehlerrate, lauf.wiederholung
        )
        for name in BLEIBT:
            pfad = ziel / name
            assert pfad.is_file(), f"{lauf.run_id}: {name} fehlt"
            assert pfad.stat().st_size > 0, f"{lauf.run_id}: {name} ist leer"


def test_laufverzeichnis_bleibt_klein(gerechnet: tuple[Path, Path]) -> None:
    """Ein Laufverzeichnis bleibt deutlich unter einem Megabyte.

    Die Zahl ist grosszuegig gewaehlt und trotzdem aussagekraeftig: Der
    verfaelschte Datensatz dieses Miniexperiments allein waere um ein Vielfaches
    groesser. Der Test schlaegt damit an, sobald jemand die Aufbewahrungsregel
    aufweicht — auch dann, wenn er die Dateien anders benennt als in
    :data:`GEHT_WEG`.
    """
    fach_config, planpfad = gerechnet
    config = lade_config(fach_config)
    plan = lade_plan(planpfad)
    grenze = 1_000_000
    for lauf in laeufe(plan):
        ziel = experiment_verzeichnis(
            config, lauf.serie, lauf.design, lauf.segment, lauf.fehlerrate, lauf.wiederholung
        )
        groesse = sum(pfad.stat().st_size for pfad in ziel.rglob("*") if pfad.is_file())
        assert groesse < grenze, f"{lauf.run_id}: {groesse} Byte im Laufverzeichnis"
