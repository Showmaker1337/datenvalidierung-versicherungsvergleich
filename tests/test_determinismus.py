"""Prueft, dass die Ergebnisse nicht von der Zahl der Arbeitsprozesse abhaengen.

Dies ist der Test, der Architekturregel A2 fuer die Parallelisierung belegt.
Waeren die Seeds ueber ``SeedSequence.spawn()`` abgeleitet, haenge das Ergebnis
davon ab, in welcher Reihenfolge die Prozesse ihre Auftraege abholen — und damit
an der Worker-Zahl. Genau deshalb leitet
:func:`src.common.seeding.lauf_seed` die Entropie direkt aus der
Faktorkombination ab.

Verglichen wird nicht "ungefaehr gleich", sondern **bitgleich**: dieselben
SHA-256-Werte im Manifest und derselbe Inhalt des Langformats.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pandas as pd
import pytest

from scripts import run_experiment
from src.common.config import lade_config
from src.common.pfade import Artefakt, experiment_verzeichnis
from src.evaluation.experimentplan import lade_plan, laeufe
from tests.experimentumgebung import baue_plan, baue_umgebung, mini_plan

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from pathlib import Path

#: Spalten, ueber die das Langformat vor dem Vergleich sortiert wird.
_SCHLUESSEL = ("run_id", "verfahren", "ebene", "gruppe_art", "gruppe", "metrik")

#: Kennzahlen, die vom Vergleich ausgenommen sind.
#:
#: Laufzeit und Speicherbedarf sind Messungen **der Maschine**, nicht des
#: Verfahrens: Sie haengen an der Auslastung des Rechners und schwanken zwischen
#: zwei Durchgaengen schon deshalb, weil beim zweiten mehr Prozesse gleichzeitig
#: rechnen. Sie mitzuvergleichen hiesse, Determinismus dort zu verlangen, wo er
#: nicht behauptet wird — und der Test schluege bei jedem Lauf fehl, ohne dass
#: ein einziges Ergebnis abwiche. Genau diese Kennzahlen stehen deshalb in
#: ``t6_laufzeit`` und in keiner Ergebnisaussage der Arbeit.
_ZEITMESSUNGEN = frozenset(
    {"laufzeit_s", "laufzeit_s_je_1000_zeilen", "speicher_mb", "speicher_mb_je_1000_zeilen"}
)


def _fahre(verzeichnis: Path, worker: int) -> tuple[Path, Path]:
    """Faehrt das Mini-Experiment mit einer festen Zahl von Prozessen.

    Args:
        verzeichnis: Eigenes Arbeitsverzeichnis dieses Durchgangs.
        worker: Zahl der Arbeitsprozesse.

    Returns:
        Konfigurations- und Planpfad des Durchgangs.
    """
    fach_config = baue_umgebung(verzeichnis)
    plan = baue_plan(verzeichnis, mini_plan(mit_teilversuchen=True))
    rueckgabe = run_experiment.main(
        [
            "--config",
            str(plan),
            "--fach-config",
            str(fach_config),
            "--worker",
            str(worker),
        ]
    )
    assert rueckgabe == 0
    return (fach_config, plan)


@pytest.fixture(scope="module")
def beide_durchgaenge(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[tuple[Path, Path], tuple[Path, Path]]:
    """Faehrt dasselbe Mini-Experiment mit einem und mit vier Prozessen."""
    einer = _fahre(tmp_path_factory.mktemp("worker1"), 1)
    vier = _fahre(tmp_path_factory.mktemp("worker4"), 4)
    return (einer, vier)


def test_langformat_ist_gleich(
    beide_durchgaenge: tuple[tuple[Path, Path], tuple[Path, Path]],
) -> None:
    """Beide Durchgaenge erzeugen dasselbe Langformat."""
    tabellen = []
    for fach_config, _ in beide_durchgaenge:
        config = lade_config(fach_config)
        lang = pd.read_parquet(config.pfade.results / "metrics_long.parquet")
        ohne_zeit = lang[~lang["metrik"].isin(_ZEITMESSUNGEN)]
        tabellen.append(ohne_zeit.sort_values(list(_SCHLUESSEL)).reset_index(drop=True))
    pd.testing.assert_frame_equal(tabellen[0], tabellen[1])


def test_hashes_sind_gleich(
    beide_durchgaenge: tuple[tuple[Path, Path], tuple[Path, Path]],
) -> None:
    """Beide Durchgaenge erzeugen bitgleiche Datensaetze.

    Der Vergleich laeuft ueber die SHA-256-Werte im Manifest: Sie decken den
    sauberen **und** den verfaelschten Datensatz je Entitaet ab. Zwei Laeufe mit
    gleichen Kennzahlen, aber verschiedenen Datensaetzen waeren kein Beleg fuer
    Reproduzierbarkeit — die Kennzahlen koennten sich zufaellig gleichen.
    """
    einer, vier = beide_durchgaenge
    config_eins = lade_config(einer[0])
    config_vier = lade_config(vier[0])
    plan = lade_plan(einer[1])

    for lauf in laeufe(plan):
        pfade = [
            experiment_verzeichnis(
                config, lauf.serie, lauf.design, lauf.segment, lauf.fehlerrate, lauf.wiederholung
            )
            / Artefakt.MANIFEST.value
            for config in (config_eins, config_vier)
        ]
        manifeste = [json.loads(pfad.read_text(encoding="utf-8")) for pfad in pfade]
        assert manifeste[0]["sha256"] == manifeste[1]["sha256"], lauf.run_id
        assert manifeste[0]["seeds"] == manifeste[1]["seeds"], lauf.run_id


def test_metrics_sind_gleich(
    beide_durchgaenge: tuple[tuple[Path, Path], tuple[Path, Path]],
) -> None:
    """Beide Durchgaenge erzeugen dieselbe ``metrics.json`` je Lauf.

    Ausgenommen ist der Abschnitt ``messung``: Laufzeit und Speicherbedarf sind
    Eigenschaften der Maschine und nicht des Verfahrens (siehe
    :data:`_ZEITMESSUNGEN`).
    """
    einer, vier = beide_durchgaenge
    config_eins = lade_config(einer[0])
    config_vier = lade_config(vier[0])
    plan = lade_plan(einer[1])

    for lauf in laeufe(plan):
        inhalte = [
            json.loads(
                (
                    experiment_verzeichnis(
                        config,
                        lauf.serie,
                        lauf.design,
                        lauf.segment,
                        lauf.fehlerrate,
                        lauf.wiederholung,
                    )
                    / Artefakt.METRICS.value
                ).read_text(encoding="utf-8")
            )
            for config in (config_eins, config_vier)
        ]
        for inhalt in inhalte:
            for angaben in inhalt["verfahren"].values():
                angaben.pop("messung", None)
        assert inhalte[0] == inhalte[1], lauf.run_id
