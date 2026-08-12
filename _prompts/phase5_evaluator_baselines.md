# Phase 5 — Evaluator und Baselines

> Voraussetzung: Phase 4 und 4b abgeschlossen, Gegencheck sauber.
> Neuer Chat. Kopiere alles ab der Trennlinie in Claude Code.

---

Baue den Evaluator und die drei Vergleichsverfahren. Lies vorher `CLAUDE.md` und
`spec/03_fehlerklassen.md`, Abschnitt 4.

## Aufgabe 0 — Orientierung (immer zuerst)

Dieser Prompt setzt voraus, dass die vorherigen Phasen abgeschlossen sind, aber **nicht**,
dass du sie selbst gebaut hast. Verschaffe dir zuerst einen Überblick, bevor du etwas Neues
schreibst:

1. `CLAUDE.md` lesen — Architekturregeln und Konventionen.
2. Die in diesem Prompt genannten Abschnitte der `spec/`-Dateien lesen.
3. **Den vorhandenen Code sichten:** `src/common/` vollständig, dazu die Module der
   vorherigen Phasen. Übernimm die dort etablierten Funktionsnamen, Signaturen und
   Konventionen, statt neue zu erfinden.
4. `docs/iteration_log.md` und `git log --oneline` überfliegen — dort stehen die
   Entscheidungen der vorherigen Phasen.

Erfinde keine Funktion neu, die es schon gibt. Findest du einen Widerspruch zwischen diesem
Prompt und dem vorhandenen Code, melde ihn, statt eigenmächtig eine Seite zu ändern.

## Aufgabe 1 — Metriken (`src/evaluation/metriken.py`)

Der Metrikstandard der Literatur ist Precision, Recall und F1 auf **Zellebene** gegen eine
Ground-Truth-Kopie. Definition nach Abedjan et al. (2016):

```
T(D) = die vom Verfahren als fehlerhaft markierten Zellen
E    = die tatsächlich fehlerhaften Zellen (aus error_log)

P  = |T(D) ∩ E| / |T(D)|
R  = |T(D) ∩ E| / |E|
F1 = 2·P·R / (P + R)
```

Eine „Zelle" ist das Tripel `(entitaet, row_id, spalte)`.

### Drei Auswertungsebenen

| Ebene | Einheit | Rolle |
|---|---|---|
| **Zellebene** | `(entitaet, row_id, spalte)` | **Primärmetrik.** Micro-averaged, zusätzlich Recall je Fehlerklasse und je Injektionsvariante |
| **Constraint-Ebene** | `verstoss_id` | Zweite Hauptsicht. Ein mehrspaltiger Verstoß gilt als Treffer, wenn **mindestens eine** seiner Zellen im Ground Truth liegt, und zählt dann als ein TP statt als 1 TP plus k FP |
| Satzebene | `(entitaet, row_id)` | Sekundärmetrik. Eine Zeile ist True Positive, wenn mindestens eine injizierte Fehlerzelle darin erkannt wurde. **Die einzige Ebene, auf der F6 und HO1 auswertbar sind** — dort kommen Zeilen hinzu, ein zellweises Diff ist undefiniert |
| Regelebene | `regel_id` | Diagnostisch. Trefferzahl, Precision je Regel, Anteil „einzige treffende Regel" |

**Warum die Constraint-Ebene nötig ist:** R-031 prüft die Beziehung zwischen Brutto, Netto
und Steuer und meldet alle drei Zellen. Der Injektor verfälscht aber nur eine davon. Streng
zellbasiert ergibt das bei perfekter Erkennung 1 TP und 2 FP — die Precision wäre
strukturell auf ein Drittel gedeckelt, als Artefakt der Berichtskonvention. Berichte beide
Sichten und diskutiere die Differenz; das ist ein eigener Absatz in der Arbeit und nimmt
eine sichere Kolloquiumsfrage vorweg.

### Sechs Festlegungen, die explizit implementiert und dokumentiert werden

1. **Keine Doppelzählung.** `T(D)` ist die **Vereinigungsmenge** der markierten Zellen,
   nicht die Summe der Regeltreffer. Nutze die Sicht `markierte_zellen` aus Phase 3.
2. **Keine Mehrfachinjektion.** Der Injektor verbietet sie bereits; die Metrik verlässt
   sich darauf und prüft es per Assertion.
3. **Klassenweise Precision ist nicht definierbar.** Für klassenweisen Recall reicht der
   Ground Truth. Ein False Positive hat aber keine Fehlerklasse — dort ist gar kein Fehler.
   Weise deshalb aus: **Recall je Fehlerklasse und je Variante**, **Precision global und je
   Regel**. Dokumentiere diese Asymmetrie im Docstring und in `README.md`.
4. **Prävalenzabhängigkeit.** Berechne zusätzlich **MCC** (Matthews-Korrelationskoeffizient).
   Bei Fehlerraten unter einem Prozent ist er aussagekräftiger als F1.
   **Accuracy wird nirgends als Hauptmetrik ausgewiesen** — bei einem Prozent Fehlern
   erreicht „markiere nichts" 99 Prozent Accuracy.
   **PR-AUC nur für B2.** Eine Precision-Recall-Kurve braucht einen kontinuierlichen Score.
   Der Prototyp, B0 und B3 liefern binäre Entscheidungen — daraus ergibt sich genau ein
   Punkt im PR-Raum, keine Kurve und keine Fläche. Nur `IsolationForest.decision_function`
   hat einen Score. Berechne PR-AUC deshalb ausschließlich für B2 und weise für die übrigen
   Verfahren den einzelnen Betriebspunkt aus. Erfinde keinen Pseudo-Score.
5. **Micro und Macro — und zwar auf zwei Ebenen.** Micro-Averaging über alle Zellen
   entspricht der Literatur; Macro-Averaging über Fehlerklassen zusätzlich berichten, damit
   seltene Klassen sichtbar bleiben.

   **Zusätzlich Macro über Varianten innerhalb jeder Klasse.** Seit Phase 4b wird das
   Klassenkontingent proportional zum Universum jeder Variante verteilt. Das hält die
   Mischung über die Ratenstufen konstant — genau dafür wurde es gebaut —, macht die
   Klassen aber intern sehr ungleich: F4-g stellt 73,5 Prozent der Klasse F4, HO2-b 90,7
   Prozent von HO2, F4-f 0,1 Prozent. Der zellgewichtete Klassen-Recall ist damit
   praktisch der Recall seiner größten Variante.

   Das ist kein Fehler, sondern eine Definitionsfrage: Zellgewichtung beantwortet „wenn
   Fehler dieser Klasse gleichverteilt über alle adressierbaren Zellen auftreten, wie viel
   findet der Katalog?" Variantengewichtung beantwortet „wie viele der Fehlerbilder dieser
   Klasse findet der Katalog, unabhängig davon, wie häufig sie sind?" Beide Fragen sind
   legitim, sie haben nur verschiedene Antworten.

   Berichte deshalb je Klasse **beide** Zahlen. Die variantengewichtete stammt aus den
   Läufen mit `--modus variante` (dort hat jede Variante ihr volles n), die zellgewichtete
   aus dem faktoriellen Plan. Die Differenz zwischen beiden ist selbst ein Ergebnis: Sie
   zeigt, wie stark der Klassenwert von der Mischung abhängt.

   **Zwei Stellen, an denen das in der Diskussion ausdrücklich anzusprechen ist:** F4
   besteht zu 73,5 Prozent aus F4-g, und F4-g löst nach dem Befund aus Phase 4 zwangsläufig
   R-021 zusammen mit R-031 bzw. R-024 aus — der Klassen-Recall von F4 liegt also nahe
   eins, weitgehend durch die Zuteilung. Umgekehrt besteht HO2 zu 90,7 Prozent aus HO2-b,
   der kohärenten Beitragssenkung, die per Konstruktion unentdeckt bleiben soll — der
   Klassen-Recall von HO2 liegt nahe null, ebenfalls durch die Zuteilung. Ohne die
   variantengewichtete Gegenzahl liest beides wie ein inhaltlicher Befund, obwohl es eine
   Eigenschaft der Gewichtung ist.
6. **Mitgezogene Zellen: als Schalter, nicht als stille Festlegung.** Der Injektor
   markiert im `error_log` mit `mitgezogen`, welche Zellen nur zur Wahrung der Kohärenz
   nachgeführt wurden — vor allem die Rangzellen bei der Skalierung des Beitragstupels.
   Diese Zellen sind gegenüber den verfälschten Daten **korrekt**; ein Verfahren, das sie
   nicht meldet, macht keinen Fehler. Sie gehören deshalb nicht in `E`.

   **Genau deshalb darf die Entscheidung nicht unsichtbar sein.** Sie hebt den Recall von
   F8 und HO2 spürbar — bei F8 stehen 5.362 fehlerhaften Zellen 2.957 mitgezogene
   gegenüber. Eine Prüferin, die das im Code entdeckt und nicht in der Arbeit, liest es als
   „Falsch-Negative wegdefiniert".

   Implementiere die Berücksichtigung als Parameter `mitgezogen_als_fehler: bool = False`
   und berechne für jeden Lauf **beide** Varianten. `metrics.json` und
   `results/metrics_long.parquet` führen beide Werte. In der Arbeit steht die
   Hauptauswertung mit `False`, die Gegenrechnung als Sensitivitätszeile im Anhang, dazu
   der Satz, warum eine nachgeführte Rangzelle kein Datenqualitätsmangel ist. Zwei Zahlen
   nebeneinander beenden die Diskussion, eine Zahl allein eröffnet sie.

### Was immer geloggt wird

- Rohwerte `TP`, `FP`, `FN`, `TN` — **nicht nur** die abgeleiteten Metriken. Damit lässt
  sich jede Metrik später neu berechnen, ohne die Läufe zu wiederholen.
- `fpr_clean`: False-Positive-Rate auf den **nicht** verfälschten Zellen. Praktisch die
  wichtigste Kennzahl, weil ein Validator mit hoher FP-Rate im Betrieb unbrauchbar ist.
- `laufzeit_s` und `speicher_mb`, normiert auf 1.000 Zeilen.
- **Kreuztabelle `regel_id` × `fehlerklasse`**: Welche Regel fängt welchen Fehlertyp? Diese
  Matrix zeigt Über- und Unterdeckung des Katalogs und wird eine der aussagekräftigsten
  Abbildungen der Arbeit.
- **Recall je `injektor_variante_id`, immer mit `n`.** Das ist der empirische Beleg gegen
  den Zirkularitätsvorwurf: Varianten, die die Regelbedingung nicht spiegeln, zeigen einen
  niedrigeren Recall. Die Zahl der tatsächlich injizierten Fehler je Variante steht im
  `manifest.json` und schwankt stark — F4-f, F7-c und F7-d sind durch nur 231 Tarifzeilen
  begrenzt. Führe `n` in **jeder** variantenweisen Tabelle mit und rechne ein
  Clopper-Pearson-Intervall dazu.

  Das gilt besonders für die drei erwartet unentdeckten Varianten F5-e, F7-d und F8-e.
  „Recall 0" ist die inhaltlich wichtigste Aussage des Injektors — aber bei n = 5 ist sie
  statistisch fast leer, und ohne Intervall daneben liest sie sich stärker, als sie ist.
  Nimm für diese Tabelle die Läufe aus dem Modus `--modus variante` (erschöpfendes n je
  Variante), nicht die des faktoriellen Plans, und weise die Herkunft aus.

Ausgabe: `metrics.json` je Lauf plus `results/metrics_long.parquet` als Langformat-Tabelle
über alle Läufe (eine Zeile je Lauf × Verfahren × Fehlerklasse × Metrik).

## Aufgabe 2 — Baseline B0: reine Schemavalidierung

`src/baselines/b0_schema.py` mit pydantic v2.

Nur Typen, Nullable-Constraints und Feldlängen aus `spec/01_datenmodell.md` — **keine
fachlichen Regeln**, keine Wertebereiche über den Datentyp hinaus, keine
Feldabhängigkeiten. B0 ist die untere Schranke: Was fangen Datentypen allein?

Die Ausgabe hat dasselbe Format wie `detections.parquet`, damit der Evaluator beide
Verfahren gleich behandelt. Als `regel_id` wird `B0-<feldname>` vergeben.

Miss die Laufzeit mit. Zeilenweise Validierung ist langsam — das ist selbst ein
berichtenswertes Nebenergebnis.

## Aufgabe 3 — Baseline B2: Isolation Forest

`src/baselines/b2_isolation_forest.py` mit scikit-learn.

- Numerische Felder je Entität, kategoriale über Ordinal- oder One-Hot-Kodierung.
- Der Detektor arbeitet auf **Zeilenebene** und markiert ganze Zeilen als Anomalie. Für die
  zellbasierte Metrik gilt: Eine als anomal markierte Zeile markiert **alle** ihre
  befüllten Zellen. Dokumentiere diese Umrechnung explizit — sie benachteiligt B2 bei der
  Precision und begünstigt es beim Recall. Weise deshalb für B2 die Satzebene als
  Primärvergleich aus und die Zellebene zusätzlich.
- **Fairness-Regel für `contamination`:** Sweepe über
  `[0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2]` und berichte die **beste erreichte F1**.
  **Wichtig für die Laufzeit:** `contamination` beeinflusst bei `IsolationForest` nur den
  Entscheidungs-Offset, nicht das Modell. Fitte **einmal**, rufe `score_samples` einmal auf
  und wende die sieben Schwellen auf dieselben Scores an. Ein Neufitten je Stufe kostet das
  Siebenfache ohne jeden Nutzen — bei mehreren tausend Läufen ist das der Unterschied
  zwischen Stunden und Tagen.
  Deklariere das im Text als bewusst optimistische Einstellung zugunsten der Baseline.
  Setze `contamination` nicht heimlich auf die wahre Fehlerrate — das wäre unfair zugunsten
  von B2 und angreifbar.
- Der Seed kommt aus `seed_model`.

## Aufgabe 4 — Baseline B3: dieselben Regeln in einem etablierten Framework

`src/baselines/b3_framework.py` mit **cuallee** (bevorzugt, weil peer-reviewed im Journal
of Open Source Software publiziert und damit wissenschaftlich zitierbar). Alternativ Great
Expectations.

Implementiere **nur die G1-Regeln** (R-001 bis R-025) im Framework — mehr ist mit
DataFrame-Check-APIs nicht sinnvoll ausdrückbar, und genau das ist das Ergebnis.

B3 misst **nicht** die Erkennungsqualität — die ist für die abgedeckten Regeln per
Konstruktion identisch. B3 misst:

| Kennzahl | Bedeutung |
|---|---|
| Anteil ausdrückbarer Regeln | Wie viele der 58 Regeln lassen sich im Framework abbilden? |
| Codezeilen je Regel | Aufwand im Vergleich zum eigenen Prototyp |
| Laufzeit | |
| Diagnosegüte | Enthält der Fehlerreport Zeile, Spalte und Ausgangswert? |

Diese vier Kennzahlen beantworten die Frage „Warum ein eigener Prototyp?" — der wertvollste
Vergleich für eine Design-Science-Arbeit.

**B3 gehört nicht in die Inferenzstatistik.** Ein Wilcoxon-Test gegen ein Verfahren, das
dieselben Regeln ausführt, testet eine Nullhypothese, von der man weiß, dass sie gilt.
Stelle sicher, dass die spätere Statistik B3 ausschließt.

## Aufgabe 5 — Einheitliche Verfahrensschnittstelle

```python
class Verfahren(Protocol):
    name: str
    def erkenne(self, kontext: Kontext) -> pd.DataFrame: ...   # Format wie detections
```

Prototyp, B0, B2 und B3 implementieren dasselbe Protokoll. Der Evaluator kennt nur dieses
Protokoll und keine Verfahrensdetails.

## Aufgabe 6 — Tests

- `tests/test_evaluation/test_metriken.py`: Metriken gegen handgerechnete
  Konfusionsmatrizen. Mindestens: perfekte Erkennung, keine Erkennung, gemischt, und der
  Grenzfall `|T(D)| = 0` (Precision ist dann undefiniert — definiere sie als 0 und
  dokumentiere die Wahl).
- `tests/test_evaluation/test_dedup.py`: Zwei Regeln auf derselben Zelle ergeben ein `TP`,
  nicht zwei.
- `tests/test_baselines/`: Je Baseline ein Smoke-Test auf einem Mini-Datensatz.
- `tests/test_evaluation/test_ebenen.py`: Prüft, dass die Satzebene die Klassen F6 und HO1
  tatsächlich erfasst, die Zellebene sie hingegen ausschließt.
- `tests/test_evaluation/test_constraint_ebene.py`: Ein dreispaltiger Verstoß mit einer
  injizierten Zelle ergibt zellbasiert 1 TP und 2 FP, constraint-basiert 1 TP und 0 FP.
- `tests/test_evaluation/test_mitgezogen.py`: Derselbe Lauf ergibt mit
  `mitgezogen_als_fehler = True` einen niedrigeren Recall als mit `False`, und die
  Differenz entspricht genau der Zahl der mitgezogenen Zellen im Nenner.

## Abnahmekriterien

1. Metriken auf allen drei Ebenen berechenbar.
2. Rohwerte TP/FP/FN/TN werden persistiert.
3. Alle drei Baselines laufen über die gemeinsame Schnittstelle.
4. Kreuztabelle `regel_id` × `fehlerklasse` wird erzeugt.
5. Recall je `injektor_variante_id` wird ausgewiesen, mit `n` und Konfidenzintervall.
6. Beide Varianten von `mitgezogen_als_fehler` werden je Lauf berechnet und persistiert.
7. Tests grün.

## Nicht in dieser Phase

Keine Experimentläufe über alle Faktorstufen, keine Signifikanztests, keine Abbildungen.
Halte am Ende an und berichte — insbesondere die Kennzahl „Anteil der im Framework
ausdrückbaren Regeln" für B3.
