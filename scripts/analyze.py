"""Wertet die Experimentserie aus: Hypothesen, Tabellen, Abbildungen.

Aufruf::

    python scripts/analyze.py
    python scripts/analyze.py --config config/experiment.yaml --nur tabellen

Das Skript liest ``results/metrics_long.parquet`` und schreibt:

``results/hypothesen.json`` und ``results/hypothesen.md``
    Je Hypothese Teststatistik, roher und korrigierter p-Wert, Effektstaerke und
    Entscheidung — mit dem je Hypothese passenden Testverfahren.
``results/tables/t1..t10`` als CSV und als Markdown
    Die zehn Ergebnistabellen.
``results/figures/abb01..abb10`` als PDF, PNG und Bildunterschrift
    Die zehn Abbildungen.
``results/befunde_aus_der_entwicklung.md``
    Die Befunde 11 bis 14 aus ``docs/iteration_log.md`` in der Form, in der sie
    in die Diskussion gehoeren. Sie sind kein interner Notizzettel: Befund 14
    beschreibt einen Confounder, der ohne den Probelauf erst in 1.680 Laeufen
    aufgefallen waere — als scheinbarer Sachtrend der Held-out-Klasse HO2 ueber
    Faktor UV2.

Der Schwellen-Sweep von B2 kommt aus den ``metrics.json``
----------------------------------------------------------

Abbildung 3 braucht Precision und Recall je ``contamination``-Stufe. Diese Werte
stehen nicht im Langformat — dort ist eine Zeile **ein** gemessener Wert, und ein
Sweep waere eine zweite Dimension. Sie stehen in der ``metrics.json`` jedes Laufs
unter ``verfahrenszusatz.B2.sweep``. Das Skript sammelt sie von dort ein; alle
uebrigen Zahlen der Auswertung stammen ausschliesslich aus dem Langformat.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ermoeglicht den Aufruf "python scripts/analyze.py" ohne editierbare
# Installation. Muss vor den Projektimporten stehen.
_WURZEL = Path(__file__).resolve().parents[1]
if str(_WURZEL) not in sys.path:
    sys.path.insert(0, str(_WURZEL))

import argparse  # noqa: E402
import json  # noqa: E402
from typing import TYPE_CHECKING, Any, Final  # noqa: E402

import pandas as pd  # noqa: E402

from scripts.inject import _schreibe_json  # noqa: E402
from src.common.config import lade_config  # noqa: E402
from src.common.pfade import Artefakt, experiment_verzeichnis  # noqa: E402
from src.evaluation import abbildungen, tabellen  # noqa: E402
from src.evaluation.ergebnisse import als_json, lade_ergebnisse  # noqa: E402
from src.evaluation.experimentplan import (  # noqa: E402
    STANDARD_PLAN,
    Versuchsplan,
    lade_plan,
    laeufe,
)
from src.evaluation.hypothesen import (  # noqa: E402
    alle_hypothesen,
    als_markdown,
    hypothesen_als_dict,
)
from src.evaluation.statistik import seed_warnung  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    from src.common.config import Config

__all__ = ["main", "sammle_b2_sweep"]

#: Dateiname des laufuebergreifenden Langformats unter ``results/``.
_LANGFORMAT: Final[str] = "metrics_long.parquet"

#: Dateinamen der Auswertungsartefakte unter ``results/``.
_HYPOTHESEN_JSON: Final[str] = "hypothesen.json"
_HYPOTHESEN_MD: Final[str] = "hypothesen.md"
_BEFUNDE_MD: Final[str] = "befunde_aus_der_entwicklung.md"
_FRAMEWORKVERGLEICH: Final[str] = "framework_vergleich.json"

#: Unterverzeichnisse der Tabellen und Abbildungen.
_TABELLEN: Final[str] = "tables"
_ABBILDUNGEN: Final[str] = "figures"

#: Zahl der Vergleiche je Hypothesenfamilie — Grundlage der Stichprobenwarnung.
_VERGLEICHE_JE_FAMILIE: Final[dict[str, int]] = {
    "HYP1-Recall": 7,
    "HYP1-Precision": 7,
    "HYP2-paarweise": 21,
    "HYP3-Trend": 7,
    "HYP4-paarweise": 7,
}


def sammle_b2_sweep(plan: Versuchsplan, config: Config) -> pd.DataFrame:
    """Sammelt den Schwellen-Sweep von B2 aus den ``metrics.json`` der Laeufe.

    Args:
        plan: Der Versuchsplan.
        config: Geladene Konfiguration; liefert das Laufverzeichnis.

    Returns:
        Je Lauf und ``contamination``-Stufe eine Zeile mit ``precision_satz``,
        ``recall_satz``, ``f1_satz`` und ``gewaehlt``. Leer, wenn kein Lauf B2
        gerechnet hat.
    """
    zeilen: list[dict[str, Any]] = []
    for lauf in laeufe(plan):
        if "B2" not in lauf.verfahren:
            continue
        pfad = (
            experiment_verzeichnis(
                config, lauf.serie, lauf.design, lauf.segment, lauf.fehlerrate, lauf.wiederholung
            )
            / Artefakt.METRICS.value
        )
        if not pfad.is_file():
            continue
        inhalt = json.loads(pfad.read_text(encoding="utf-8"))
        sweep = inhalt.get("verfahrenszusatz", {}).get("B2", {}).get("sweep", [])
        zeilen.extend(
            {"run_id": lauf.run_id, "klasse": lauf.klasse, **stufe} for stufe in sweep
        )
    return pd.DataFrame(zeilen)


def _befunde_markdown(plan: Versuchsplan) -> str:
    """Formuliert die Befunde 11 bis 14 fuer die Ergebnisdarstellung.

    Sie stehen in ``docs/iteration_log.md`` und gehoeren in die Diskussion der
    Arbeit — nicht als Fussnote in einer Fehlerliste. Die Datei hier macht sie in
    den **Ergebnisdateien** wiederfindbar, damit niemand den Entwicklungslog
    durchsuchen muss.

    Args:
        plan: Der Versuchsplan; liefert die Ratenstufen fuer den Bezug.

    Returns:
        Den Inhalt von ``results/befunde_aus_der_entwicklung.md``.
    """
    raten = ", ".join(f"{rate:.1%}".replace(".", ",") for rate in sorted(plan.hauptversuch.raten))
    return f"""# Befunde aus der Entwicklung, die in die Ergebnisdarstellung gehoeren

Quelle: `docs/iteration_log.md`. Diese Datei stellt die vier Befunde zusammen,
die nicht nur die Implementierung betreffen, sondern das **Ergebnis** — sie
gehoeren in die Diskussion und in die Limitationen.

## Befund 11 — die Ursache der elf Rangverstoesse war keine der drei erwarteten

Bei der Held-out-Klasse HO2 blieb in 11 von 1.217 skalierten Angeboten die
Rangfolge verletzt. Die drei naheliegenden Ursachen — falsches Sortierfeld,
Gleichstand, Rundung — schieden je an einem Messwert aus. Die tatsaechliche
Ursache war eine vierte: **Interferenz zwischen zwei Anwendungen derselben
Variante innerhalb einer Anfrage**. Alle 11 betroffenen Anfragen hatten mehr als
ein skaliertes Angebot; von den 1.102 Anfragen mit genau einem war keine
einzige betroffen.

## Befund 12 — der Effekt wuchs mit der Fehlerrate

| Fehlerrate | skalierte Angebote | Anfragen mit >= 2 | R-044-Verstoesse | Anteil | HO2-Recall |
|---|---|---|---|---|---|
| 0,005 | 304 | 2 | 0 | 0,00 % | 0,00000 |
| 0,010 | 609 | 14 | 3 | 0,49 % | 0,00223 |
| 0,020 | 1.217 | 57 | 11 | 0,90 % | 0,00410 |
| 0,050 | 3.044 | 294 | 65 | 2,14 % | 0,00968 |

Der Anteil blieb nicht konstant, er wuchs — und mit ihm der gemessene Recall der
Held-out-Klasse. Ein Trendtest ueber die Ratenstufen haette damit einen
Confounder gemessen und keinen Sacheffekt.

## Befund 13 — der strukturelle Kern der Framework-Grenze, gemessen

Die Aussage, der frameworkuebergreifend belastbare Teil der Grenze seien die
relationalen, die quellenuebergreifenden und die algorithmischen Regeln, stand
bis Phase 5 auf einem Formargument. Sie ist gemessen: R-046 und R-054 sind in
**keinem** der beiden Frameworks ausdrueckbar. Keines der 57
Great-Expectations-Erwartungen und keines der cuallee-Praedikate traegt `Group`
oder `Partition` im Namen. Ein Pruefmodell aus zeilen- und spaltenweisen
Praedikaten ueber **eine** Tabelle kennt keine Gruppierung mit Rueckbezug auf die
Gruppe — genau das verlangen R-043 bis R-048, R-052 und R-054.

## Befund 14 — Kohaerenz gegen den Ausgangszustand haelt nicht unter Ueberlagerung

**Der eigentliche Ertrag, und er gehoert als Ergebnis in die Arbeit.**

> Wird Kohaerenz **je Verfaelschung** gegen den **unverfaelschten
> Ausgangszustand** hergestellt, ist sie bei mehrfacher Anwendung innerhalb
> derselben Bezugsgruppe nicht mehr gewaehrleistet. Die Verletzung entsteht nicht
> in der einzelnen Verfaelschung, sondern in ihrer **Ueberlagerung** — und sie
> waechst ueberproportional mit der Fehlerrate, weil die Zahl der mehrfach
> getroffenen Bezugsgruppen einem Geburtstagsproblem folgt.

**Warum das ueber diesen Prototyp hinausweist.** Der Befund betrifft jeden
Fehlerinjektor, der relationale Nebenbedingungen bedienen muss — also jeden, der
auf normalisierten Daten arbeitet. Er laesst sich gegen BART und Jenga stellen:
Beide erzeugen Verfaelschungen unter Nebenbedingungen und stehen vor derselben
Frage, sobald zwei Verfaelschungen dieselbe Bezugsgruppe treffen.

**Warum er in die Limitationen gehoert.** Der Fehler wurde durch die eigene
Messung gefunden, nicht durch Nachdenken. Er war in keiner der drei Hypothesen
enthalten, mit denen die Suche begann, und er waere ohne den Probelauf ueber
mehrere Ratenstufen erst in den Laeufen dieser Serie aufgefallen — als scheinbar
inhaltlicher Trend der Held-out-Klasse HO2 ueber Faktor UV2 (Fehlerrate,
Stufen {raten}). **Dass er vorher gefunden wurde, ist Teil des Ergebnisses.**

**Die Loesung.** Die Rangfolge wird einmalig am Ende des Laufs gegen den
Endzustand nachgefuehrt, statt je Verfaelschung gegen den sauberen Stand. Damit
wird jede Rangzelle genau einmal geschrieben, die Endrangfolge ist eine reine
Funktion des Endzustands und haengt nicht mehr von der Reihenfolge der
Injektionen ab, und Universum wie Kandidatenmenge bleiben unberuehrt — die
Bezugsgroesse der Fehlerrate ist unangetastet, Faktor UV2 bleibt sauber.

Nach der Korrektur bleibt HO2 auf **allen** Ratenstufen unentdeckt, genau wie
konstruiert. Der scheinbare Trend ueber UV2 ist verschwunden, weil er nie einer
war.
"""


def _argumente() -> argparse.ArgumentParser:
    """Baut den Argumentparser des Skripts."""
    parser = argparse.ArgumentParser(
        description="Wertet die Experimentserie aus: Hypothesen, Tabellen, Abbildungen."
    )
    parser.add_argument(
        "--config", type=Path, default=STANDARD_PLAN, help="Pfad des Versuchsplans"
    )
    parser.add_argument(
        "--fach-config",
        type=Path,
        default=None,
        dest="fach_config",
        help="Pfad der fachlichen Konfiguration",
    )
    parser.add_argument(
        "--nur",
        nargs="+",
        default=None,
        choices=("hypothesen", "tabellen", "abbildungen", "befunde"),
        help="Nur diese Artefakte erzeugen",
    )
    parser.add_argument("--still", action="store_true", help="Keine Fortschrittsausgabe")
    return parser


def main(argumente: Sequence[str] | None = None) -> int:  # noqa: C901, PLR0912 - linear
    """Einstiegspunkt des Skripts.

    Args:
        argumente: Kommandozeilenargumente; ``None`` nimmt ``sys.argv``.

    Returns:
        ``0`` bei Erfolg.
    """
    optionen = _argumente().parse_args(argumente)
    plan = lade_plan(optionen.config)
    config = lade_config(optionen.fach_config)
    gewuenscht = set(optionen.nur or ("hypothesen", "tabellen", "abbildungen", "befunde"))

    ergebnisse = config.pfade.results
    ergebnisse.mkdir(parents=True, exist_ok=True)
    lang = lade_ergebnisse(ergebnisse / _LANGFORMAT, plan)
    if not optionen.still:
        print(f"Langformat: {len(lang)} Zeilen aus {lang['run_id'].nunique()} Laeufen.")

    warnung = seed_warnung(
        plan.hauptversuch.wiederholungen,
        _VERGLEICHE_JE_FAMILIE,
        alpha=plan.statistik.alpha,
    )
    if warnung and not optionen.still:
        print()
        print(warnung)
        print()

    if "hypothesen" in gewuenscht:
        gepruefte = alle_hypothesen(lang, plan)
        _schreibe_json(
            ergebnisse / _HYPOTHESEN_JSON,
            als_json(
                hypothesen_als_dict(gepruefte, alpha=plan.statistik.alpha, warnung=warnung)
            ),
        )
        (ergebnisse / _HYPOTHESEN_MD).write_text(
            als_markdown(gepruefte, alpha=plan.statistik.alpha, warnung=warnung),
            encoding="utf-8",
            newline="\n",
        )
        if not optionen.still:
            for ergebnis in gepruefte:
                print(f"  {ergebnis.kennung}: {ergebnis.entscheidung}")

    if "tabellen" in gewuenscht:
        gebaut = tabellen.baue_alle(
            lang, plan, frameworkvergleich=ergebnisse / _FRAMEWORKVERGLEICH
        )
        for name, tabelle in gebaut.items():
            tabellen.schreibe_tabelle(tabelle, ergebnisse / _TABELLEN, name)
            if not optionen.still:
                print(f"  {name}: {len(tabelle)} Zeilen")

    if "abbildungen" in gewuenscht:
        sweep = sammle_b2_sweep(plan, config)
        gezeichnet = abbildungen.baue_alle(
            lang, plan, ergebnisse / _ABBILDUNGEN, sweep=sweep
        )
        if not optionen.still:
            for name in gezeichnet:
                print(f"  {name}: PDF, PNG und Bildunterschrift")

    if "befunde" in gewuenscht:
        (ergebnisse / _BEFUNDE_MD).write_text(
            _befunde_markdown(plan), encoding="utf-8", newline="\n"
        )
        if not optionen.still:
            print(f"  {_BEFUNDE_MD}")

    if not optionen.still:
        print(f"\nAlles in {ergebnisse}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
