# Phase 6 — Experimentläufe, Statistik und Abbildungen

> Voraussetzung: Phase 5 abgeschlossen, Tests grün.
> Kopiere alles ab der Trennlinie in Claude Code.

---

Baue den Experiment-Runner, die statistische Auswertung und die Abbildungen für die Arbeit.

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

## Aufgabe 1 — Experimentdesign

### Hauptversuch (vollfaktoriell)

| Faktor | Stufen | Anzahl |
|---|---|---|
| UV1 Fehlerklasse | F1, F2, F3, F4, F5, F7, F8 | **7** |
| UV2 Fehlerrate | 0,01 / 0,02 / 0,05 / 0,10 | **4** |
| UV5 Verfahren | Prototyp / B0 / B2 | **3** |

→ 84 Zellen × **20 Seeds** = **1.680 Läufe**.

Drei Faktorstufen sind bewusst **nicht** im Hauptversuch:

- **F6 (Duplikate)** erzeugt zusätzliche Zeilen und hat keinen zellbasierten Ground Truth.
  Ein zellbasiertes F1 ist dort undefiniert. F6 läuft als eigener, satzbasierter
  Teilversuch.
- **B3** führt dieselben Regeln aus wie der Prototyp — die Erkennungsleistung ist per
  Konstruktion identisch, ein Wilcoxon-Test dagegen testet eine Nullhypothese, von der man
  weiß, dass sie gilt. B3 wird qualitativ verglichen (Ausdrückbarkeit, Codezeilen,
  Laufzeit, Diagnosegüte), nicht statistisch.
- **Die Fehlerraten 0,005 und 0,20** entfallen: 0,5 Prozent ist bei mehreren Klassen
  statistisch zu dünn, 20 Prozent ist praxisfern.

Wenn die Rechenzeit es hergibt, können 0,005 und 0,20 sowie 30 statt 20 Seeds ergänzt
werden. Das ist eine Erweiterung, keine Voraussetzung — dokumentiere, was tatsächlich
gelaufen ist.

### Fünf Teilversuche

| Teilversuch | Design | Zweck |
|---|---|---|
| **T1 Duplikate** | F6, 4 Raten, 3 Verfahren, 20 Seeds, **satzbasierte Metrik** | Die laut Branchenempirie häufigste Fehlerklasse |
| **T2 Held-out** | HO1 und HO2, Rate 0,02, 20 Seeds, nur Prototyp | Erwarteter Recall nahe null — die Antwort auf das „inwieweit" |
| **T3 Praxismix** | alle Klassen gemeinsam mit den Gewichten aus `spec/03`, Rate 0,02, 20 Seeds, alle Verfahren | Realistischer Fehlermix statt isolierter Klassen. Inhaltlich der interessanteste Teilversuch |
| **T4 Skalierung** | 1.000 / 10.000 / 100.000 Anfragen, Rate 0,02, Prototyp und B0, 5 Seeds | Laufzeit und Speicher |
| **T5 Datenvarianz** | eine Klasse (F5), Rate 0,02, 20 verschiedene **Basisdatensatz**-Seeds, nur Prototyp | Vergleich gegen die Injektionsvarianz des Hauptversuchs |

## Aufgabe 2 — Seeding

Verwende `lauf_seed` aus `src/common/seeding.py` (Phase 1):

```python
seed = lauf_seed(master_seed, strom, klasse_idx, rate_idx, verfahren_idx, wdh_idx)
```

**Nicht** `SeedSequence.spawn()` für Einzelläufe. `spawn()` ist ein Zähler und damit
reihenfolgeabhängig — bei paralleler Ausführung hingen die Ergebnisse von der Worker-Zahl
ab, und `tests/test_determinismus.py` würde fehlschlagen.

**Zwei Varianzquellen:**

- Der **Hauptversuch** hält den Basisdatensatz fest und variiert nur den Injektions-Seed →
  misst die **Injektionsvarianz**.
- **T5** variiert den Basisdatensatz-Seed → misst die **Datenvarianz**.

Ist die Datenvarianz deutlich größer als die Injektionsvarianz, hängt das Ergebnis am
Generator und nicht am Verfahren. Das musst du wissen, bevor es jemand anderes bemerkt,
und es gehört so in die Arbeit.

Determinismus absichern: `PYTHONHASHSEED=0`, gepinnte Versionen, keine Iteration über
ungeordnete Strukturen, `pip freeze` je Experimentserie archivieren.

## Aufgabe 3 — Runner

`scripts/run_experiment.py --config config/experiment.yaml [--nur-teilversuch T3]`

- Läuft die Faktorstufen ab, mit Fortschrittsanzeige und Checkpointing: Ein bereits
  abgeschlossener Lauf wird beim nächsten Start übersprungen, nicht wiederholt.
- Parallelisierung über `multiprocessing`, Worker-Zahl konfigurierbar. Die Ergebnisse
  müssen **unabhängig von der Worker-Zahl identisch** sein.
- Schreibt je Lauf `metrics.json` und aggregiert alles nach `results/metrics_long.parquet`.
- **Speicher:** Der verfälschte Datensatz wird nach der Auswertung gelöscht. Aufbewahrt
  werden nur `error_log`, `error_log_records`, `detections` und `metrics.json`. Ohne diese
  Regel entstehen bei 1.680 Läufen zweistellige Gigabyte. Der verfälschte Datensatz ist aus
  den Seeds jederzeit exakt reproduzierbar.
- Bricht bei einem Einzelfehler nicht die Serie ab, sondern protokolliert ihn in
  `results/failed_runs.json` und macht weiter. Am Ende wird die Zahl fehlgeschlagener Läufe
  ausgewiesen — **stillschweigend weniger Läufe zu verwenden wäre eine verdeckte
  Stichprobenreduktion.**

### Laufzeit realistisch einschätzen

Der Engpass ist B2: Fitten und Scoren des Isolation Forest über fünf Entitäten. Miss nach
den ersten zwanzig Läufen die tatsächliche Zeit je Lauf und rechne hoch. Wenn die
Hochrechnung über zwölf Stunden liegt, reduziere in dieser Reihenfolge und dokumentiere es:

1. `n_anfragen` von 10.000 auf 3.000 (für die Metrikstabilität reichen rund 600.000 Zellen
   locker; 10.000 bleiben für T4 Skalierung)
2. Seeds von 20 auf 15
3. Fehlerrate 0,10 streichen

Denke daran: `contamination` beeinflusst bei `IsolationForest` nur den Offset, nicht das
Modell — einmal fitten, einmal scoren, sieben Schwellen auf dieselben Scores anwenden
(siehe Phase 5).

## Aufgabe 4 — Statistische Auswertung (`src/evaluation/statistik.py`)

**Deskriptiv**

- Mittelwert mit 95-Prozent-**Bootstrap-Konfidenzintervall** (BCa, 10.000 Resamples) über
  die Seeds.
- **Fallback zwingend implementieren:** Ist die Statistik über alle Seeds konstant — was
  bei den Held-out-Klassen mit Recall 0 der Erwartungsfall ist —, degeneriert die
  BCa-Beschleunigung (Division durch null im Jackknife). Fange das ab und weiche auf ein
  **Clopper-Pearson-Intervall** für den Anteil aus. Ohne diesen Fallback bricht ausgerechnet
  die Abbildung, die das „inwieweit" der Forschungsfrage beantwortet.

**Inferenz je Hypothese**

| Hypothese | Verfahren |
|---|---|
| HYP1 (Prototyp vs. B0) | **Wilcoxon-Vorzeichen-Rangtest**, gepaart über identische Seeds |
| HYP2 (Recall unterscheidet sich zwischen Fehlerklassen) | **Friedman-Test** über die 7 Klassen, danach paarweise Wilcoxon mit Holm-Korrektur |
| HYP3 (Precision steigt mit der Fehlerrate) | **Page-Trendtest** oder Spearman-Korrelation über die geordneten Ratenstufen — kein Wilcoxon, das ist eine Trendhypothese |
| HYP4 (Prototyp vs. B2 ist fehlerklassenabhängig) | Interaktionseffekt: **ART-ANOVA** (Aligned Rank Transform). Falls das zu aufwendig wird, ein explizit als **deskriptiv** deklarierter Vergleich der Effektstärken je Klasse — dann aber ohne p-Wert-Behauptung |

Ein t-Test ist nirgends angemessen: F1-Verteilungen sind nicht normalverteilt und nach oben
beschränkt. REIN verwendet ebenfalls den Wilcoxon-Vorzeichen-Rangtest.

**Multiplizität**

- **Holm-Bonferroni über alle Tests einer Hypothesenfamilie.** Die Zahl der Vergleiche wird
  je Familie ausgewiesen.
- HYP1: 7 Klassen × 1 Baseline = 7 Vergleiche. HYP2: 21 paarweise Klassenvergleiche.
  HYP4: 7 Vergleiche.
- Lege die Aggregationsebene vorab fest: über die Fehlerraten aggregieren, je Klasse testen.
  Wird zusätzlich je Rate getestet, vervierfacht sich die Zahl — dann muss das im Text
  stehen.

**Effektstärken**

- **Matched-pairs rank-biserial correlation** r = (W⁺ − W⁻) / (W⁺ + W⁻) für die gepaarten
  Wilcoxon-Tests. Das ist das zum Test passende Maß.
- Zusätzlich **Cliff's Delta** für die ungepaarten Vergleiche.
- **Nicht beide von Cliff's Delta und Vargha-Delaney A₁₂ berichten** — es gilt exakt
  δ = 2·A₁₂ − 1, das ist dieselbe Information in zwei Skalen und fällt im Kolloquium auf.

**Warnhinweis im Report**

Wenn die Zahl der Seeds unter 20 liegt, gibt die Auswertung eine sichtbare Warnung aus. Der
korrekte Wortlaut: Bei n = 10 hat der exakte Wilcoxon-Test einen kleinstmöglichen p-Wert
von 2/2¹⁰ ≈ 0,00195. Unter Holm-Korrektur über 7 Vergleiche ist der kleinste Wert damit
0,0137 und noch signifikant — der zweitkleinste mögliche p-Wert (0,0039) ergibt korrigiert
0,023 und ebenfalls. Bei 21 Vergleichen (HYP2) wird es dagegen eng: 0,00195 × 21 = 0,041,
und der zweite Vergleich ist bereits nicht mehr signifikant. **Die Warnung muss diese Zahlen
korrekt nennen** — eine pauschale Aussage „praktisch kein Spielraum" wäre falsch und stünde
sonst im Report und damit potenziell in der Arbeit.

## Aufgabe 5 — Hypothesen

| ID | Hypothese |
|---|---|
| **HYP1** | Der Prototyp erreicht einen höheren **Recall** als B0, **ohne dass die Precision signifikant fällt.** Der Recall-Teil allein wäre nahezu tautologisch, weil B0 eine Teilmenge des Katalogs ist — erst die Precision-Bedingung macht daraus eine Hypothese, die scheitern kann |
| **HYP2** | Der Recall des Prototyps unterscheidet sich signifikant zwischen den Fehlerklassen |
| **HYP3** | Die Precision steigt mit steigender Fehlerrate (Prävalenzeffekt) |
| **HYP4** | Der Unterschied zwischen Prototyp und B2 ist **fehlerklassenabhängig**: regelbasiert gewinnt bei Format- und Regelverletzungen, statistisch bei Ausreißern |

Beachte die Namensgebung: **HYP1 bis HYP4** sind die Hypothesen, **HO1 und HO2** die
Held-out-Fehlerklassen. Nicht vermischen — beides landet in Ergebnisdateien.

Für jede Hypothese: Teststatistik, p-Wert roh und korrigiert, Effektstärke, Entscheidung.
Ausgabe nach `results/hypothesen.json` und als Markdown-Tabelle in `results/hypothesen.md`.

## Aufgabe 6 — Abbildungen (`src/evaluation/abbildungen.py`)

Alle als PDF **und** PNG (300 dpi) nach `results/figures/`. Schriftgröße mindestens 9 pt,
Graustufen-tauglich (unterschiedliche Marker und Linienstile, nicht nur Farbe).

| Nr | Abbildung | Inhalt |
|---|---|---|
| 1 | Heatmap | Fehlerklasse × Fehlerrate, F1 als Farbwert, nur Prototyp, nur die 7 zellbasierten Klassen |
| 2 | Boxplots | F1-Verteilung über die Seeds, je Verfahren, je Fehlerklasse |
| 3 | PR-Kurve | **nur B2** (einziges Verfahren mit kontinuierlichem Score); die übrigen Verfahren als einzelne Betriebspunkte in dasselbe Diagramm |
| 4 | Balkendiagramm | Recall je Fehlerklasse mit Konfidenzintervall, HO1 und HO2 deutlich abgesetzt |
| 5 | **Recall je Injektionsvariante** | gruppiert nach Fehlerklasse, mit Markierung „spiegelt Regel exakt". **Die wichtigste Abbildung der Arbeit** — sie zeigt empirisch, dass nicht-spiegelnde Varianten schlechter erkannt werden, und entkräftet damit den Zirkularitätsvorwurf |
| 6 | Kreuztabelle als Heatmap | `regel_id` × `fehlerklasse`, zeigt Über- und Unterdeckung des Katalogs inklusive der 15 Regeln ohne Treffer |
| 7 | Laufzeitkurve | Laufzeit über Datensatzgröße, je Verfahren, log-log (aus T4) |
| 8 | Varianzvergleich | Injektionsvarianz (Hauptversuch) gegen Datenvarianz (T5) |
| 9 | Zellmetrik vs. Constraint-Metrik | Precision beider Sichten je Fehlerklasse — macht das Artefakt mehrspaltiger Verstöße sichtbar |
| 10 | Praxismix | Ergebnisse aus T3 gegen die isolierten Klassen des Hauptversuchs |

Jede Abbildung bekommt eine Bildunterschrift als eigene `.txt`-Datei daneben, damit sie
direkt in die Arbeit übernommen werden kann.

## Aufgabe 7 — Ergebnistabellen

Nach `results/tables/` als CSV **und** als Markdown:

- `t1_hauptergebnis.csv` — P/R/F1 je Verfahren und Fehlerklasse, mit Konfidenzintervall
- `t2_fehlerraten.csv` — F1 und MCC über die Fehlerraten (PR-AUC nur für B2)
- `t3_regeldiagnose.csv` — je Regel: Treffer, Precision, Anteil „einzige treffende Regel".
  **Die Regeln ohne Treffer bleiben in der Tabelle** und werden als Überdeckung
  interpretiert, nicht stillschweigend entfernt
- `t4_varianten.csv` — Recall je Injektionsvariante mit der Spalte „spiegelt Regel exakt"
- `t5_baseline_b3.csv` — Ausdrückbarkeit, Codezeilen je Regel, Laufzeit, Diagnosegüte
- `t6_laufzeit.csv` — Laufzeit und Speicher, normiert auf 1.000 Zeilen
- `t7_teilversuche.csv` — Ergebnisse aus T1 bis T5 im Überblick
- `t8_metrikvergleich.csv` — Zellmetrik gegen Constraint-Metrik

## Aufgabe 8 — Reproduzierbarkeitspaket

`scripts/make_repro_package.py` erzeugt `results/reproduction/` mit:

- allen Konfigurationen und Seeds
- `pip freeze`
- Git-Commit-Hash des aktuellen Standes **und** des Tags `freeze-regelkatalog`
- SHA-256 aller Ein- und Ausgabedateien
- `README_reproduction.md` mit den exakten Kommandos in der richtigen Reihenfolge
- der Zahl fehlgeschlagener Läufe aus `failed_runs.json`

Damit ist jeder Einzelwert der Ergebnistabellen rückverfolgbar. Das ist Hevner Guideline 5
(Research Rigor) in konkreter Form und gehört in den Anhang.

## Aufgabe 9 — Tests

- `tests/test_evaluation/test_statistik.py`: Wilcoxon, Friedman, Page-Trendtest,
  Bootstrap-CI inklusive Degenerationsfall, Holm-Korrektur und rank-biserial gegen
  handgerechnete Beispiele.
- `tests/test_experiment.py`: Ein Mini-Experiment (2 Klassen × 2 Raten × 2 Verfahren ×
  3 Seeds) läuft vollständig durch und erzeugt alle Artefakte.
- `tests/test_determinismus.py`: Dasselbe Mini-Experiment mit 1 und mit 4 Workern liefert
  identische Ergebnisse.
- `tests/test_experiment_speicher.py`: Nach einem Lauf existiert der verfälschte Datensatz
  nicht mehr, `error_log` und `metrics.json` schon.

## Abnahmekriterien

1. Mini-Experiment läuft vollständig durch, alle Artefakte entstehen.
2. Ergebnisse sind unabhängig von der Worker-Zahl.
3. Alle zehn Abbildungen und acht Tabellen werden erzeugt.
4. `results/hypothesen.md` enthält je Hypothese Teststatistik, korrigierten p-Wert,
   Effektstärke und Entscheidung — mit dem je Hypothese passenden Testverfahren.
5. Der Bootstrap degeneriert bei den Held-out-Klassen nicht, sondern weicht auf
   Clopper-Pearson aus.
6. Reproduzierbarkeitspaket vollständig.
7. Tests grün.

## Nicht in dieser Phase

Keine Änderung am Regelkatalog, am Generator oder am Injektor. Wenn ein Ergebnis
unerwartet ausfällt, ist das ein Befund — kein Anlass, das Artefakt anzupassen.

Halte am Ende an und berichte: die Hauptergebnisse in Zahlen, welche Hypothesen gehalten
haben, wie hoch die tatsächliche Laufzeit war und wo die Ergebnisse von deiner Erwartung
abweichen.
