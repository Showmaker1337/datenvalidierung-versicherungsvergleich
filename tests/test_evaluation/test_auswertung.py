"""Prueft die Auswertungskette: Langformat, Hypothesen, Tabellen, Abbildungen.

Gefahren wird ein Miniexperiment mit drei Fehlerklassen und drei Ratenstufen.
Weniger geht nicht: Der Friedman-Test braucht mindestens drei Gruppen, der
Page-Trendtest mindestens drei geordnete Stufen. Mit zwei Klassen liefe die
Auswertung nicht durch — und der Test pruefte genau die Stelle nicht, an der sie
scheitern koennte.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts import analyze, run_experiment
from src.common.config import lade_config
from src.evaluation import abbildungen, tabellen
from src.evaluation.experimentplan import lade_plan
from tests.experimentumgebung import baue_plan, baue_umgebung, mini_plan

#: Der Frameworkvergleich ist kein Experimentlauf und entsteht getrennt.
FRAMEWORKVERGLEICH = Path(__file__).resolve().parents[2] / "results" / "framework_vergleich.json"


@pytest.fixture(scope="module")
def ausgewertet(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Faehrt ein Miniexperiment und wertet es vollstaendig aus.

    Der Frameworkvergleich wird in die Testumgebung kopiert statt neu erzeugt: Er
    haengt nicht am Experiment, sondern am Regelkatalog und an den beiden
    Frameworks, und sein Neuaufbau kostete Minuten ohne Erkenntnisgewinn fuer
    diesen Test.
    """
    if not FRAMEWORKVERGLEICH.is_file():
        pytest.skip(
            f"{FRAMEWORKVERGLEICH.name} fehlt. Einmalig "
            "'python scripts/framework_vergleich.py' ausfuehren."
        )
    verzeichnis = tmp_path_factory.mktemp("auswertung")
    fach_config = baue_umgebung(verzeichnis)
    ziel = verzeichnis / "results"
    ziel.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FRAMEWORKVERGLEICH, ziel / FRAMEWORKVERGLEICH.name)
    plan = baue_plan(
        verzeichnis,
        mini_plan(
            serie="au",
            klassen=("F2", "F3", "F4"),
            raten=(0.01, 0.02, 0.05),
            verfahren=("prototyp", "B0", "B2"),
            wiederholungen=3,
            n_anfragen=200,
            mit_teilversuchen=True,
        ),
    )
    assert (
        run_experiment.main(
            ["--config", str(plan), "--fach-config", str(fach_config), "--worker", "4"]
        )
        == 0
    )
    assert (
        analyze.main(
            ["--config", str(plan), "--fach-config", str(fach_config), "--still"]
        )
        == 0
    )
    return (fach_config, plan)


def test_hypothesen_werden_geschrieben(ausgewertet: tuple[Path, Path]) -> None:
    """``hypothesen.json`` und ``hypothesen.md`` entstehen und tragen alle vier."""
    fach_config, _ = ausgewertet
    ergebnisse = lade_config(fach_config).pfade.results
    inhalt = json.loads((ergebnisse / "hypothesen.json").read_text(encoding="utf-8"))
    kennungen = [eintrag["kennung"] for eintrag in inhalt["hypothesen"]]
    assert kennungen == ["HYP1", "HYP2", "HYP3", "HYP4"]
    assert (ergebnisse / "hypothesen.md").is_file()


def test_jede_hypothese_traegt_test_p_effekt_und_entscheidung(
    ausgewertet: tuple[Path, Path],
) -> None:
    """Abnahmekriterium 4: je Hypothese Teststatistik, korrigiertes p, Effekt, Entscheidung."""
    fach_config, _ = ausgewertet
    ergebnisse = lade_config(fach_config).pfade.results
    inhalt = json.loads((ergebnisse / "hypothesen.json").read_text(encoding="utf-8"))
    for hypothese in inhalt["hypothesen"]:
        assert hypothese["entscheidung"] in {
            "gestuetzt",
            "teilweise gestuetzt",
            "nicht gestuetzt",
        }
        assert hypothese["begruendung"]
        for familie in hypothese["familien"]:
            assert familie["vergleiche"], hypothese["kennung"]
            for vergleich in familie["vergleiche"]:
                assert vergleich["test"]
                assert vergleich["p_wert"] is not None
                assert vergleich["p_korrigiert"] is not None
                assert vergleich["effektmass"]


def test_die_vier_hypothesen_nutzen_vier_verschiedene_verfahren(
    ausgewertet: tuple[Path, Path],
) -> None:
    """Jede Hypothese bekommt das zu ihr passende Testverfahren.

    HYP2 den Friedman-Test, HYP3 den Page-Trendtest, HYP4 die ART-ANOVA, HYP1
    zwei Familien gepaarter Wilcoxon-Tests. Waeren es viermal dieselben Tests,
    waere mindestens einer davon falsch gewaehlt.
    """
    fach_config, _ = ausgewertet
    ergebnisse = lade_config(fach_config).pfade.results
    inhalt = json.loads((ergebnisse / "hypothesen.json").read_text(encoding="utf-8"))
    je_kennung = {eintrag["kennung"]: eintrag for eintrag in inhalt["hypothesen"]}

    assert je_kennung["HYP1"]["primaertest"] is None
    assert all(
        vergleich["test"] == "Wilcoxon-Vorzeichen-Rangtest"
        for familie in je_kennung["HYP1"]["familien"]
        for vergleich in familie["vergleiche"]
    )
    assert je_kennung["HYP2"]["primaertest"]["test"] == "Friedman-Test"
    assert je_kennung["HYP3"]["primaertest"]["test"] == "Page-Trendtest"
    assert "ART-ANOVA" in je_kennung["HYP4"]["primaertest"]["test"]


def test_alle_zehn_tabellen_entstehen(ausgewertet: tuple[Path, Path]) -> None:
    """Abnahmekriterium 3: zehn Tabellen als CSV und als Markdown."""
    fach_config, _ = ausgewertet
    verzeichnis = lade_config(fach_config).pfade.results / "tables"
    for name in tabellen.TABELLENNAMEN:
        for endung in ("csv", "md"):
            pfad = verzeichnis / f"{name}.{endung}"
            assert pfad.is_file(), pfad
            assert pfad.stat().st_size > 0, pfad


def test_alle_zehn_abbildungen_entstehen(ausgewertet: tuple[Path, Path]) -> None:
    """Abnahmekriterium 3: zehn Abbildungen als PDF, PNG und Bildunterschrift."""
    fach_config, _ = ausgewertet
    verzeichnis = lade_config(fach_config).pfade.results / "figures"
    for name in abbildungen.ABBILDUNGSNAMEN:
        for endung in ("pdf", "png", "txt"):
            pfad = verzeichnis / f"{name}.{endung}"
            assert pfad.is_file(), pfad
            assert pfad.stat().st_size > 0, pfad


def test_regeltabelle_fuehrt_alle_regeln_des_katalogs(ausgewertet: tuple[Path, Path]) -> None:
    """Regeln ohne Treffer bleiben in ``t3_regeldiagnose`` stehen."""
    import pandas as pd  # noqa: PLC0415 - nur fuer diesen Test gebraucht

    from src.rules.katalog import KATALOG  # noqa: PLC0415 - nur fuer diesen Test gebraucht

    fach_config, _ = ausgewertet
    pfad = lade_config(fach_config).pfade.results / "tables" / "t3_regeldiagnose.csv"
    tabelle = pd.read_csv(pfad)
    assert len(tabelle) == len(KATALOG)
    assert set(tabelle["regel_id"]) == {regel.regel_id for regel in KATALOG}
    assert bool(tabelle["ohne_treffer"].any()), (
        "Kein einziger Eintrag ohne Treffer — dann prueft dieser Test nichts"
    )


def test_variantentabelle_stammt_aus_dem_variantenteilversuch(
    ausgewertet: tuple[Path, Path],
) -> None:
    """Abnahmekriterium 3a: ``t4_varianten`` kommt aus T6, nicht aus dem Hauptversuch.

    Belegt ueber die Fallzahl: Der Testplan injiziert im Variantenmodus mit
    ``max_fehler = 25``. Genau die beiden Varianten des Teilversuchs haben
    deshalb ein ``n`` groesser null; alle uebrigen bleiben leer, obwohl der
    Hauptversuch ihre Klassen gerechnet hat.
    """
    import pandas as pd  # noqa: PLC0415 - nur fuer diesen Test gebraucht

    fach_config, planpfad = ausgewertet
    plan = lade_plan(planpfad)
    block = next(eintrag for eintrag in plan.teilversuche if eintrag.kennung == "T6")
    pfad = lade_config(fach_config).pfade.results / "tables" / "t4_varianten.csv"
    tabelle = pd.read_csv(pfad)

    besetzt = set(tabelle.loc[tabelle["n"] > 0, "variante"])
    assert besetzt == set(block.gruppen)
    assert len(tabelle) == 60, "Die Tabelle fuehrt alle sechzig Varianten"


def test_befunde_datei_nennt_befund_vierzehn(ausgewertet: tuple[Path, Path]) -> None:
    """Die Befunde aus der Entwicklung sind in den Ergebnisdateien wiederfindbar."""
    fach_config, _ = ausgewertet
    pfad = lade_config(fach_config).pfade.results / "befunde_aus_der_entwicklung.md"
    text = pfad.read_text(encoding="utf-8")
    assert "Befund 14" in text
    assert "Ueberlagerung" in text
    assert "HO2" in text
