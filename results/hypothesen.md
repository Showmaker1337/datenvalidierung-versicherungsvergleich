# Hypothesen HYP1 bis HYP4

Erzeugt von `scripts/analyze.py`. Jede Zahl stammt aus
`results/metrics_long.parquet`; jede Zeile dort traegt eine `run_id`, die alle
Faktorstufen ihres Laufs kodiert.

- Signifikanzniveau: alpha = 0,05
- Multiplizitaetskorrektur: Holm-Bonferroni, **je Familie getrennt**
- Aggregationsebene: ueber die Fehlerraten aggregiert, je Fehlerklasse getestet
- Kein t-Test: F1-Verteilungen sind nach oben beschraenkt und nicht normalverteilt.

**Namensgebung.** HYP1 bis HYP4 sind die Hypothesen, HO1 und HO2 die beiden
Held-out-Fehlerklassen. Die Held-out-Klassen kommen in keiner Hypothese vor —
sie sind der Teilversuch T2 und werden deskriptiv berichtet. Eine Hypothese
„der Recall ist null“ waere eine Nullhypothese, und die laesst sich nicht
bestaetigen.

## Ueberblick

| Hypothese | Primaertest | p | Effektstaerke | Entscheidung |
|---|---|---|---|---|
| HYP1 | zwei Familien gepaarter Wilcoxon-Tests | — | — | teilweise gestuetzt |
| HYP2 | Friedman-Test | < 0,001 | Kendalls W = 1,000 | gestuetzt |
| HYP3 | Page-Trendtest | < 0,001 | z / sqrt(n) = 0,705 | gestuetzt |
| HYP4 | ART-ANOVA (Aligned Rank Transform), Interaktion | < 0,001 | partielles Eta-Quadrat = 0,973 | teilweise gestuetzt |

## HYP1

> Der Prototyp erreicht einen hoeheren Recall als B0, ohne dass die Precision signifikant faellt.

**Entscheidung: teilweise gestuetzt.** In 4 von 7 Fehlerklassen ist der Recall des Prototyps signifikant hoeher und die Precision nicht signifikant niedriger. Signifikant gefallen ist die Precision bei: ['F1', 'F2', 'F3'].

### Familie HYP1-Recall — 7 Vergleiche

Recall des Prototyps gegen B0, je Fehlerklasse, einseitig. Kennzahl: `recall`. Nach Holm-Korrektur signifikant: 7 von 7.

| Gruppe | n | Statistik | p roh | p korrigiert | Effektstaerke | signifikant |
|---|---|---|---|---|---|---|
| F1 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F2 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F3 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F4 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F5 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F7 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F8 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |

### Familie HYP1-Precision — 7 Vergleiche

Precision des Prototyps gegen B0, je Fehlerklasse, zweiseitig. Kennzahl: `precision`. Nach Holm-Korrektur signifikant: 7 von 7.

| Gruppe | n | Statistik | p roh | p korrigiert | Effektstaerke | signifikant |
|---|---|---|---|---|---|---|
| F1 | 20 | 0,0 | < 0,001 | < 0,001 | rank-biserial r = -1,000 | ja |
| F2 | 20 | 0,0 | < 0,001 | < 0,001 | rank-biserial r = -1,000 | ja |
| F3 | 20 | 0,0 | < 0,001 | < 0,001 | rank-biserial r = -1,000 | ja |
| F4 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F5 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F7 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F8 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |

**Zur Einordnung.**

- Der Recall-Teil allein waere nahezu tautologisch: B0 prueft eine Teilmenge der Bedingungen des Katalogs. Erst die Precision-Bedingung macht daraus eine Hypothese, die scheitern kann.
- Die beiden Familien werden getrennt nach Holm korrigiert; eine gemeinsame Korrektur ueber 14 Vergleiche waere unnoetig streng, weil die Precision-Familie der Absicherung dient und nicht der Bestaetigung.
- ACHTUNG bei der Deutung der Precision: In den Klassen ['F4', 'F5', 'F7', 'F8'] meldet B0 ueberhaupt nichts. Seine Precision ist dort konventionsgemaess 0,0 — das heisst 'keine Meldung' und nicht 'alle Meldungen falsch'. Ein Precision-Vergleich gegen diese Null stellt eine Messung neben eine Festlegung; die Precision-Bedingung von HYP1 ist nur in den uebrigen Klassen inhaltlich geprueft.

## HYP2

> Der Recall des Prototyps unterscheidet sich signifikant zwischen den Fehlerklassen.

**Primaertest:** Friedman-Test (zweiseitig), n = 20.

- Teststatistik: 120,000
- p (unkorrigiert): < 0,001
- Kendalls W: 1,000
- Hinweis: 7 Gruppen, 20 Bloecke

**Entscheidung: gestuetzt.** Friedman-Test ueber 7 Klassen und 20 Bloecke: chi2 = 120.000, p = 1.63e-23, Kendalls W = 1.000. Nach Holm-Korrektur sind 20 der 21 paarweisen Vergleiche signifikant.

### Familie HYP2-paarweise — 21 Vergleiche

paarweise Klassenvergleiche des Prototyp-Recalls, zweiseitig. Kennzahl: `recall`. Nach Holm-Korrektur signifikant: 20 von 21.

| Gruppe | n | Statistik | p roh | p korrigiert | Effektstaerke | signifikant |
|---|---|---|---|---|---|---|
| F1 gegen F2 | 20 | 0,0 | < 0,001 | < 0,001 | rank-biserial r = -1,000 | ja |
| F1 gegen F3 | 20 | 0,0 | < 0,001 | < 0,001 | rank-biserial r = -1,000 | ja |
| F1 gegen F4 | 20 | 0,0 | < 0,001 | < 0,001 | rank-biserial r = -1,000 | ja |
| F1 gegen F5 | 20 | 0,0 | < 0,001 | < 0,001 | rank-biserial r = -1,000 | ja |
| F1 gegen F7 | 20 | 0,0 | < 0,001 | < 0,001 | rank-biserial r = -1,000 | ja |
| F1 gegen F8 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F2 gegen F3 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F2 gegen F4 | 20 | 0,0 | 1,000 | 1,000 | rank-biserial r = 0,000 | nein |
| F2 gegen F5 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F2 gegen F7 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F2 gegen F8 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F3 gegen F4 | 20 | 0,0 | < 0,001 | < 0,001 | rank-biserial r = -1,000 | ja |
| F3 gegen F5 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F3 gegen F7 | 20 | 0,0 | < 0,001 | < 0,001 | rank-biserial r = -1,000 | ja |
| F3 gegen F8 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F4 gegen F5 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F4 gegen F7 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F4 gegen F8 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F5 gegen F7 | 20 | 0,0 | < 0,001 | < 0,001 | rank-biserial r = -1,000 | ja |
| F5 gegen F8 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F7 gegen F8 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |

**Zur Einordnung.**

- Die paarweisen Vergleiche sind nur unter einem signifikanten Friedman-Test interpretierbar; sonst waeren sie ein Fischzug ueber 21 Kombinationen.

## HYP3

> Die Precision steigt mit steigender Fehlerrate (Praevalenzeffekt).

**Primaertest:** Page-Trendtest (einseitig), n = 140.

- Teststatistik: 3785,000
- p (unkorrigiert): < 0,001
- z / sqrt(n): 0,705
- Hinweis: 4 geordnete Stufen, 140 Bloecke, Normalapproximation, z=8.344

**Entscheidung: gestuetzt.** Page-Trendtest ueber 140 Bloecke (Klasse x Wiederholung) und 4 geordnete Ratenstufen: L = 3785.0, p = 3.59e-17. Spearman ueber alle Beobachtungen: rho = 0.069 (p = 0.103). Einzeln signifikant sind 3 der 7 Klassen.

### Familie HYP3-Trend — 7 Vergleiche

Page-Trendtest der Precision ueber die geordneten Ratenstufen, je Klasse. Kennzahl: `precision`. Nach Holm-Korrektur signifikant: 3 von 7.

| Gruppe | n | Statistik | p roh | p korrigiert | Effektstaerke | signifikant |
|---|---|---|---|---|---|---|
| F1 | 20 | 558,0 | < 0,001 | < 0,001 | z / sqrt(n) = 1,005 | ja |
| F2 | 20 | 511,0 | 0,197 | 0,417 | z / sqrt(n) = 0,191 | nein |
| F3 | 20 | 596,0 | < 0,001 | < 0,001 | z / sqrt(n) = 1,663 | ja |
| F4 | 20 | 514,0 | 0,139 | 0,417 | z / sqrt(n) = 0,242 | nein |
| F5 | 20 | 600,0 | < 0,001 | < 0,001 | z / sqrt(n) = 1,732 | ja |
| F7 | 20 | 525,0 | 0,026 | 0,106 | z / sqrt(n) = 0,433 | nein |
| F8 | 20 | 481,0 | 0,929 | 0,929 | z / sqrt(n) = -0,329 | nein |

**Zur Einordnung.**

- UV2 ist erst seit Phase 4b sauber testbar: Das Klassenkontingent wird proportional zum Universum jeder Variante verteilt, die Variantenmischung ist damit ueber alle Ratenstufen identisch. Vorher haette ein Trend ueber die Ratenstufen teils die Rate gemessen und teils eine Verschiebung der Variantenmischung; HYP3 ist erst dadurch eine Hypothese ueber die Fehlerrate (docs/iteration_log.md, Phase 4, Befund 4).
- Ein zweiter Confounder derselben Bauart wurde in Phase 5 gefunden und beseitigt: Kohaerenz, die je Verfaelschung gegen den Ausgangszustand hergestellt wird, bricht bei Ueberlagerung innerhalb derselben Bezugsgruppe und waere als scheinbarer Sachtrend von HO2 ueber UV2 aufgetaucht (docs/iteration_log.md, Befund 14).
- Ein Wilcoxon-Test waere hier das falsche Werkzeug: Er verglicht zwei Stufen ohne Ordnung und liesse die Information ungenutzt, dass die Stufen aufsteigend sind.

## HYP4

> Der Unterschied zwischen Prototyp und B2 ist fehlerklassenabhaengig: regelbasiert gewinnt bei Format- und Regelverletzungen, statistisch bei Ausreissern.

**Primaertest:** ART-ANOVA (Aligned Rank Transform), Interaktion (einseitig), n = 280.

- Teststatistik: 1590,027
- p (unkorrigiert): < 0,001
- partielles Eta-Quadrat: 0,973
- Hinweis: F(6, 266); 2 x 7 Faktorstufen

**Entscheidung: teilweise gestuetzt.** ART-ANOVA, Interaktion Verfahren x Fehlerklasse auf F1: F(6, 266); 2 x 7 Faktorstufen, F = 1590.03, p = 3.74e-205, partielles Eta-Quadrat = 0.973. Nach Holm-Korrektur gewinnt der Prototyp in 7 Klassen (['F1', 'F2', 'F3', 'F4', 'F5', 'F7', 'F8']), B2 in 0 Klassen ([]). Die Hypothese behauptet zweierlei: eine Interaktion und eine Richtung. Die Interaktion ist belegt — der Abstand zwischen den Verfahren haengt deutlich von der Fehlerklasse ab. Die Richtungsaussage 'statistisch gewinnt bei Ausreissern' ist es **nicht**: B2 liegt in keiner einzigen Klasse vorn. Deshalb 'teilweise gestuetzt' und nicht 'gestuetzt'.

### Familie HYP4-paarweise — 7 Vergleiche

F1 des Prototyps gegen B2, je Fehlerklasse, zweiseitig. Kennzahl: `f1`. Nach Holm-Korrektur signifikant: 7 von 7.

| Gruppe | n | Statistik | p roh | p korrigiert | Effektstaerke | signifikant |
|---|---|---|---|---|---|---|
| F1 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F2 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F3 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F4 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F5 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F7 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |
| F8 | 20 | 210,0 | < 0,001 | < 0,001 | rank-biserial r = 1,000 | ja |

**Zur Einordnung.**

- Die ART-ANOVA prueft die Interaktion auf Raengen der um beide Haupteffekte bereinigten Werte; sie setzt keine Normalitaet voraus. Der p-Wert bezieht sich ausschliesslich auf den Interaktionsterm.
- B2 waehlt seine contamination-Stufe ueber die beste F1 der Satzebene und bekommt dafuer den Ground Truth zu sehen. Das ist eine bewusst optimistische Einstellung zugunsten der Baseline; der Prototyp bekommt keine vergleichbare Anpassung.

