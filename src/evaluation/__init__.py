"""Auswertung: Ground Truth, Konfusionsmatrizen, Kennzahlen und Berichte.

Dieses Paket misst, wie gut ein Verfahren die injizierten Datenqualitaetsmaengel
findet. Es vergleicht den regelbasierten Prototyp mit drei Baselines (B0
``pydantic``, B2 ``IsolationForest``, B3 ``cuallee``) auf drei Auswertungsebenen
und schreibt die Ergebnisse in ``metrics.json`` und
``results/metrics_long.parquet``.

Es importiert **nichts** aus ``src.injector`` und nichts aus ``src.generator``.
Alles, was die Auswertung ueber Fehlerklassen und Varianten wissen muss, steht in
den beiden Ground-Truth-Logs und im ``manifest.json`` des Laufs. Der Grund ist
derselbe, aus dem der Injektor die Regeln nicht kennen darf: Die Zuordnung
Variante auf Regel entsteht laut ``spec/03_fehlerklassen.md``, Abschnitt 6 erst
hier. Stammte sie aus dem Quelltext des Injektors, maesse das Experiment nur noch,
ob dieselbe Bedingung zweimal geschrieben wurde. Aus ``src.rules`` **darf**
importiert werden — die Auswertung braucht den Pruefkontext und das Berichtsformat.

Module
------

``modell``
    Verfahrensprotokoll, Ergebnistypen, Konstanten.
``ground_truth``
    Beide Ground-Truth-Logs zu Wahrheitsmengen aufbereitet.
``metriken``
    Konfusionsmatrizen und Kennzahlen auf allen Ebenen; traegt die sechs
    methodischen Festlegungen der Phase.
``langformat``
    ``metrics.json`` und das laufuebergreifende Langformat.
``pipeline``
    Orchestrierung: Verfahren ausfuehren, messen, auswerten.

Ab Phase 6 kommen die Module der Ergebnisdarstellung hinzu. Sie werden hier
bewusst **nicht** re-exportiert: ``abbildungen`` zieht matplotlib in den Prozess,
``tabellen`` und ``hypothesen`` ziehen scipy. Wer den Experiment-Runner startet,
braucht nichts davon, und ein Import von ``src.evaluation`` soll nicht mehrere
Sekunden kosten.

``varianten``
    Zuordnung Injektionsvariante auf Regel, abgeschrieben aus ``spec/03``,
    Abschnitt 2 — nicht aus dem Injektor (siehe dort, Abschnitt 6).
``experimentplan``
    Der Versuchsplan aus ``config/experiment.yaml``, aufgefaltet zu Einzellaeufen.
``ergebnisse``
    Zugriff auf ``results/metrics_long.parquet`` — die eine Quelle aller
    Ergebniszahlen.
``statistik``
    Konfidenzintervalle, Hypothesentests, Effektstaerken.
``hypothesen``
    HYP1 bis HYP4, je mit dem zu ihnen passenden Testverfahren.
``tabellen``
    Die zehn Ergebnistabellen.
``abbildungen``
    Die zehn Abbildungen samt Bildunterschriften.
"""

from __future__ import annotations

from src.evaluation.ground_truth import (
    GroundTruth,
    Satzwahrheit,
    Zellwahrheit,
    lade_ground_truth,
)
from src.evaluation.langformat import (
    METRICS_LONG_SPALTEN,
    baue_langformat,
    baue_metrics,
    schreibe_langformat,
    schreibe_metrics,
)
from src.evaluation.modell import (
    KEINE_FEHLERKLASSE,
    ROW_ID_OHNE_BEZUG,
    SCORE_SPALTEN,
    Auswertung,
    AuswertungsFehler,
    Ebene,
    Ebenenauswertung,
    Gruppenrecall,
    Kennzahlen,
    Konfusion,
    Kreuzeintrag,
    Laufmessung,
    MitSatzmeldungen,
    MitZellscore,
    Regeldiagnose,
    Verfahren,
    Verfahrensergebnis,
)
from src.evaluation.pipeline import bewerte, fuehre_aus

__all__ = [
    "KEINE_FEHLERKLASSE",
    "METRICS_LONG_SPALTEN",
    "ROW_ID_OHNE_BEZUG",
    "SCORE_SPALTEN",
    "Auswertung",
    "AuswertungsFehler",
    "Ebene",
    "Ebenenauswertung",
    "GroundTruth",
    "Gruppenrecall",
    "Kennzahlen",
    "Konfusion",
    "Kreuzeintrag",
    "Laufmessung",
    "MitSatzmeldungen",
    "MitZellscore",
    "Regeldiagnose",
    "Satzwahrheit",
    "Verfahren",
    "Verfahrensergebnis",
    "Zellwahrheit",
    "baue_langformat",
    "baue_metrics",
    "bewerte",
    "fuehre_aus",
    "lade_ground_truth",
    "schreibe_langformat",
    "schreibe_metrics",
]
