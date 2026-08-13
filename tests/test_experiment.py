"""Prueft den Experiment-Runner an einem vollstaendigen Mini-Experiment.

Der Zuschnitt ist der aus dem Phasenprompt: zwei Fehlerklassen, zwei
Ratenstufen, zwei Verfahren, drei Wiederholungen — zwoelf Laeufe. Er ist klein
genug fuer die Testsuite und gross genug, dass jeder Codeweg des Runners einmal
laeuft.

Der wichtigste Test dieser Datei ist :func:`test_manifest_gleicht_handlauf`
-----------------------------------------------------------------------------

Er belegt, dass der Runner **denselben Lauf** erzeugt wie ein Aufruf von
``scripts/inject.py`` von Hand. Ohne diesen Nachweis waere der Runner eine
zweite, moeglicherweise abweichende Implementierung desselben Vorgangs, und die
Aussage "jeder Einzellauf des Experiments ist unabhaengig nachvollziehbar"
stuende auf einer Behauptung statt auf einer Messung.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pandas as pd
import pytest

from scripts import inject, run_experiment
from src.common.config import lade_config
from src.common.pfade import Artefakt, experiment_verzeichnis
from src.evaluation.experimentplan import (
    MODUS_KLASSE,
    MODUS_VARIANTE,
    lade_plan,
    laeufe,
)
from tests.experimentumgebung import baue_plan, baue_umgebung, mini_plan

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from pathlib import Path

#: Artefakte, die nach einem Lauf im Laufverzeichnis liegen muessen.
PFLICHTARTEFAKTE = (
    Artefakt.ERROR_LOG.value,
    Artefakt.ERROR_LOG_RECORDS.value,
    Artefakt.CONFIG.value,
    Artefakt.MANIFEST.value,
    Artefakt.METRICS.value,
    run_experiment.LANGFORMAT_JE_LAUF,
)


@pytest.fixture(scope="module")
def gerechnet(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, int]:
    """Faehrt das Mini-Experiment einmal und gibt Konfiguration, Plan und Rueckgabewert zurueck."""
    verzeichnis = tmp_path_factory.mktemp("experiment")
    fach_config = baue_umgebung(verzeichnis)
    plan = baue_plan(verzeichnis, mini_plan(mit_teilversuchen=True))
    rueckgabe = run_experiment.main(
        [
            "--config",
            str(plan),
            "--fach-config",
            str(fach_config),
            "--worker",
            "2",
        ]
    )
    return (fach_config, plan, rueckgabe)


def test_serie_laeuft_ohne_fehlschlag(gerechnet: tuple[Path, Path, int]) -> None:
    """Kein Lauf scheitert, und die Fehlerliste weist das aus."""
    fach_config, _, rueckgabe = gerechnet
    assert rueckgabe == 0
    config = lade_config(fach_config)
    liste = json.loads(
        (config.pfade.results / run_experiment.FEHLERLISTE).read_text(encoding="utf-8")
    )
    assert liste["gescheiterte_laeufe"] == 0, liste["laeufe"]
    assert liste["gerechnete_laeufe"] > 0


def test_alle_artefakte_entstehen(gerechnet: tuple[Path, Path, int]) -> None:
    """Jeder Lauf legt alle Pflichtartefakte ab."""
    fach_config, planpfad, _ = gerechnet
    config = lade_config(fach_config)
    plan = lade_plan(planpfad)
    for lauf in laeufe(plan):
        ziel = experiment_verzeichnis(
            config, lauf.serie, lauf.design, lauf.segment, lauf.fehlerrate, lauf.wiederholung
        )
        fehlend = [name for name in PFLICHTARTEFAKTE if not (ziel / name).is_file()]
        assert not fehlend, f"{lauf.run_id}: {fehlend} fehlen in {ziel}"


def test_langformat_enthaelt_alle_laeufe(gerechnet: tuple[Path, Path, int]) -> None:
    """Das laufuebergreifende Langformat traegt jeden Lauf des Plans."""
    fach_config, planpfad, _ = gerechnet
    config = lade_config(fach_config)
    plan = lade_plan(planpfad)
    lang = pd.read_parquet(config.pfade.results / "metrics_long.parquet")
    erwartet = {lauf.run_id for lauf in laeufe(plan)}
    assert set(lang["run_id"]) == erwartet
    assert not lang.empty


def test_metrics_json_traegt_alle_verfahren(gerechnet: tuple[Path, Path, int]) -> None:
    """``metrics.json`` enthaelt jedes im Plan angeforderte Verfahren."""
    fach_config, planpfad, _ = gerechnet
    config = lade_config(fach_config)
    plan = lade_plan(planpfad)
    for lauf in laeufe(plan):
        ziel = experiment_verzeichnis(
            config, lauf.serie, lauf.design, lauf.segment, lauf.fehlerrate, lauf.wiederholung
        )
        inhalt = json.loads((ziel / Artefakt.METRICS.value).read_text(encoding="utf-8"))
        gerechnete = set(inhalt["verfahren"])
        assert set(lauf.verfahren) <= gerechnete, lauf.run_id


def test_wiederaufnahme_ueberspringt_fertige_laeufe(
    gerechnet: tuple[Path, Path, int], capsys: pytest.CaptureFixture[str]
) -> None:
    """Ein zweiter Aufruf rechnet nichts neu, sondern ueberspringt alles."""
    fach_config, planpfad, _ = gerechnet
    rueckgabe = run_experiment.main(
        ["--config", str(planpfad), "--fach-config", str(fach_config), "--worker", "1"]
    )
    ausgabe = capsys.readouterr().out
    assert rueckgabe == 0
    assert "Laeufe gerechnet       0" in ausgabe
    assert "davon offen:               0" in ausgabe


def test_manifest_gleicht_handlauf(gerechnet: tuple[Path, Path, int]) -> None:
    """Der Runner erzeugt denselben Lauf wie ``scripts/inject.py`` von Hand.

    Aufgerufen wird ``scripts/inject.py`` mit **exakt** denselben Faktorstufen und
    derselben Konfiguration; es schreibt damit in dasselbe Laufverzeichnis.
    Verglichen wird das ``manifest.json`` vor und nach diesem Aufruf. Es traegt
    die Faktorstufen, beide Seeds, die Zuteilung je Variante, die Zellzahlen und
    die SHA-256-Werte des sauberen **und** des verfaelschten Datensatzes — sind
    sie gleich, ist es derselbe Lauf.

    Einziger zugelassener Unterschied ist der Schluessel ``teilversuch``: Er ist
    eine Angabe des Versuchsplans, und ``scripts/inject.py`` kennt keinen Plan.

    Ohne diesen Nachweis waere der Runner eine zweite, moeglicherweise
    abweichende Implementierung desselben Vorgangs.
    """
    fach_config, planpfad, _ = gerechnet
    config = lade_config(fach_config)
    plan = lade_plan(planpfad)
    lauf = next(eintrag for eintrag in laeufe(plan) if eintrag.modus == MODUS_KLASSE)
    ziel = experiment_verzeichnis(
        config, lauf.serie, lauf.design, lauf.segment, lauf.fehlerrate, lauf.wiederholung
    )
    aus_runner = json.loads((ziel / Artefakt.MANIFEST.value).read_text(encoding="utf-8"))

    argumente = [
        "--config",
        str(fach_config),
        "--serie",
        lauf.serie,
        "--design",
        lauf.design,
        "--klasse",
        lauf.klasse,
        "--rate",
        str(lauf.fehlerrate),
        "--wdh",
        str(lauf.wiederholung),
        "--n-anfragen",
        str(lauf.n_anfragen),
        "--still",
    ]
    assert inject.main(argumente) == 0
    von_hand = json.loads((ziel / Artefakt.MANIFEST.value).read_text(encoding="utf-8"))

    assert aus_runner.pop("teilversuch") == lauf.teilversuch
    assert "teilversuch" not in von_hand
    assert aus_runner == von_hand


def test_variantenlauf_traegt_seine_variante(gerechnet: tuple[Path, Path, int]) -> None:
    """Ein Lauf im Variantenmodus injiziert genau eine Variante."""
    fach_config, planpfad, _ = gerechnet
    config = lade_config(fach_config)
    plan = lade_plan(planpfad)
    varianten = [eintrag for eintrag in laeufe(plan) if eintrag.modus == MODUS_VARIANTE]
    assert varianten, "Der Testplan enthaelt keinen Variantenlauf"
    for lauf in varianten:
        ziel = experiment_verzeichnis(
            config, lauf.serie, lauf.design, lauf.segment, lauf.fehlerrate, lauf.wiederholung
        )
        manifest = json.loads((ziel / Artefakt.MANIFEST.value).read_text(encoding="utf-8"))
        assert manifest["faktorstufen"]["variante"] == lauf.variante
        assert set(manifest["zuteilung_je_variante"]) == {lauf.variante}


def test_datenvarianz_variiert_den_basisdatensatz(gerechnet: tuple[Path, Path, int]) -> None:
    """Im Teilversuch T5 unterscheidet sich der saubere Datensatz je Wiederholung.

    Der Nachweis laeuft ueber die SHA-256-Werte des sauberen Datensatzes: Sie
    muessen sich unterscheiden, waehrend der Injektionsstrom gleich bleibt. Ohne
    diese Trennung maesse T5 die Summe aus Daten- und Injektionsvarianz statt der
    Datenvarianz allein.
    """
    fach_config, planpfad, _ = gerechnet
    config = lade_config(fach_config)
    plan = lade_plan(planpfad)
    laeufe_t5 = [eintrag for eintrag in laeufe(plan) if eintrag.teilversuch == "T5"]
    assert len(laeufe_t5) > 1

    hashes: set[str] = set()
    injektionsstroeme: set[str] = set()
    for lauf in laeufe_t5:
        ziel = experiment_verzeichnis(
            config, lauf.serie, lauf.design, lauf.segment, lauf.fehlerrate, lauf.wiederholung
        )
        manifest = json.loads((ziel / Artefakt.MANIFEST.value).read_text(encoding="utf-8"))
        hashes.add(json.dumps(manifest["sha256"]["df_clean"], sort_keys=True))
        injektionsstroeme.add(str(manifest["seeds"]["seed_inject"]))

    assert len(hashes) == len(laeufe_t5), "Die Basisdatensaetze von T5 sind nicht verschieden"
    assert len(injektionsstroeme) == 1, "Der Injektionsstrom von T5 variiert mit"
