# Spezifikation der Vergleichsverfahren B0, B2 und B3

Diese Datei beantwortet die Frage, wie die Vergleichsverfahren tatsächlich rechnen — in einer
Genauigkeit, die eine Nachimplementierung allein aus diesem Text erlaubt. Jede Angabe trägt
ihre Fundstelle in der Form `datei.py:zeile`. Was im Quelltext nicht existiert, steht hier als
**nicht vorhanden** und wird nicht rekonstruiert.

Stand: Commit-Stand des Repositories zum Zeitpunkt der Erstellung; Bibliotheksversionen aus
`requirements.txt` (`scikit-learn==1.9.0`, `pydantic==2.13.4`, `cuallee==0.15.4`,
`pandas==3.0.5`, `numpy==2.5.1`).

---

## Teil 1 — B2: Isolation Forest

Modul: `src/baselines/b2_isolation_forest.py` (964 Zeilen). Der Modul-Docstring
(`b2_isolation_forest.py:1-156`) begründet die Entwurfsentscheidungen; die folgenden Punkte
nennen den ausführenden Code.

### Merkmalsaufbereitung

#### 1. Auf welchem DataFrame arbeitet B2?

Auf **beiden Schichten, aber mit klarer Rollenteilung**:

| Zweck | Schicht | Fundstelle |
|---|---|---|
| Merkmalsmatrix (Modelleingabe) | `df_typed` | `b2_isolation_forest.py:925`, verwendet in `:429` |
| Maske der befüllten Zellen (Ausgabe) | `df_raw` | `b2_isolation_forest.py:926`, verwendet in `:939` und `:465` |
| Zeilenkennungen | `df_typed`, Spalte `row_id` | `b2_isolation_forest.py:937`, `:473-496` |

Wichtig für die Arbeit: Die typisierte Schicht, die B2 sieht, ist **nicht** der saubere
Generatorausgang, sondern das **zurückgeparste verfälschte `df_raw`**. Der Prüfkontext wird in
`scripts/evaluate.py:648` aus `ergebnis.df_raw_dirty` gebaut, und `src/rules/modell.py:494`
erzeugt die typisierte Schicht daraus über `parse` (`src/common/serialisierung.py:634`). Ein
Rohwert, der sich nicht parsen lässt, wird dabei zu `pd.NA` — für B2 also zu einem Fehlwert
mit Indikatorspalte (siehe Punkt 6 und Punkt 19).

#### 2. Alle Entitäten gemeinsam oder je Entität ein Modell?

**Je Entität ein eigenes Modell.** Die Schleife über die sieben Entitäten steht in
`b2_isolation_forest.py:890`; je Durchlauf wird in `:933` genau einmal gefittet.

Es findet **kein Join statt**. Begründung im Modul-Docstring `b2_isolation_forest.py:17-24`:
Ein Join würde Zeilen vervielfachen und damit die Zählung der Satzebene zerstören.
Zusammengeführt werden erst die Ergebnisse, und zwar auf der Ebene der markierten Zeilen
(`b2_isolation_forest.py:550-559`) und der markierten Zellen (`:562-574`).

Eine Entität ohne Zeilen (`b2_isolation_forest.py:927-928`) oder ohne eine einzige
Merkmalsspalte mit Varianz (`:930-931`) bekommt kein Modell; der Grund wird über
`uebersprungene_entitaeten()` (`:842-856`) berichtet und landet in `metrics.json`. In der Serie
s01 ist dieses Feld in allen Läufen leer.

#### 3. Welche Spalten gehen ein, welche nicht, und wie viele sind es?

**Ausschlussregel: eine Namensheuristik.** `b2_isolation_forest.py:328-338`:

```python
return spalte == "row_id" or spalte.endswith("_id")
```

Angewandt wird sie in `b2_isolation_forest.py:426-427`. Ausgeschlossen sind damit `row_id` und
jede Spalte, deren Name auf `_id` endet — also alle Primär- und Fremdschlüssel. Begründung im
Modul-Docstring `b2_isolation_forest.py:90-93`: Eine ordinal kodierte UUID ist Rauschen mit
maximaler Kardinalität. Es gibt **keine** Ausschlussliste nach Datentyp und **keine**
Konfigurationsoption dafür.

Alle übrigen Schemaspalten (`SPALTEN_JE_ENTITAET`, `src/common/serialisierung.py:297`) gehen
ein. Danach wirken zwei datenabhängige Schritte: Indikatorspalten kommen hinzu
(`b2_isolation_forest.py:436-438`), Spalten ohne Varianz fallen weg (`:440-444`).

**Merkmalszahl aus dem Schema** (deterministisch, aus `src/common/serialisierung.py:146-291`):

| Entität | Schemaspalten | davon Schlüssel | Merkmalsspalten vor Indikatoren |
|---|---|---|---|
| anfrage | 12 | 3 | 9 |
| person | 16 | 3 | 13 |
| risiko_kfz | 29 | 3 | 26 |
| risiko_hausrat | 14 | 3 | 11 |
| tarif | 13 | 2 | 11 |
| angebot | 18 | 4 | 14 |
| zahlung | 7 | 3 | 4 |
| **Summe** | **109** | **21** | **88** |

**Tatsächliche Merkmalszahl.** Sie wird in keinem Laufartefakt protokolliert — in
`metrics.json` steht sie **nicht vorhanden**. Nachgemessen wurde sie deshalb in einem rein
lesenden Durchlauf mit dem kanonischen Basisdatensatz (`basis_index = 0`, `n_anfragen = 10000`
aus `config/default.yaml:12`), der nichts geschrieben hat:

| Entität | clean | dirty F1, Rate 0,10 | dirty F3, Rate 0,10 |
|---|---|---|---|
| anfrage | 9 (1 Indikator) | 18 (9) | 9 (1) |
| person | 21 (8) | 26 (13) | 21 (8) |
| risiko_kfz | 30 (5) | 52 (26) | 31 (6) |
| risiko_hausrat | 14 (3) | 22 (11) | 14 (3) |
| tarif | 16 (5) | 21 (10) | 16 (5) |
| angebot | 25 (11) | 28 (14) | 25 (11) |
| zahlung | 6 (2) | 8 (4) | 6 (2) |
| **Summe** | **121** | **175** | **122** |

Auf dem sauberen Datensatz entfernt der Varianzfilter genau zwei Spalten: `anfrage.waehrung`
und `risiko_kfz.wagniskennziffer`. Beide sind im Modell konstant.

Die Zahlen sind eine Messung an einem Basisdatensatz, nicht aus einem s01-Lauf ausgelesen; die
s01-Läufe verwenden andere Injektionsseeds. Die Größenordnung und der Klassenunterschied sind
davon unberührt — dazu Punkt 19.

#### 4. Kodierung kategorialer Spalten

**Ordinal**, über eine nach dem Wert **sortierte** Kategorienliste —
`b2_isolation_forest.py:382-403`, der Kern in `:397-398`:

```python
kategorien = sorted({wert for wert in werte if not _ist_leer(wert)})
stufe = {kategorie: float(nummer) for nummer, kategorie in enumerate(kategorien)}
```

Kategorial behandelt werden die Feldtypen `TEXT` und `WAHRHEIT` (`b2_isolation_forest.py:430`).
Kein One-Hot, kein Hashing, kein Frequency-Encoding, kein Target-Encoding.

**Aus einer kategorialen Spalte entsteht genau eine Merkmalsspalte** — plus die Indikatorspalte,
falls die Spalte mindestens einen Fehlwert trägt. Die Kardinalität der Kategorie geht also
nicht in die Spaltenzahl ein, sondern nur in den Wertebereich der einen Spalte.

Die Sortierung ist Teil der Reproduzierbarkeit (Modul-Docstring `b2_isolation_forest.py:82-88`):
Eine Kodierung nach Auftretensreihenfolge hinge an der Zeilenreihenfolge, eine über ein
unsortiertes `set` an der Hashfolge des Prozesses. Dass eine ordinale Kodierung eine Ordnung
suggeriert, die es fachlich nicht gibt, ist im selben Absatz als bekannte Schwäche benannt.

Kategoriale Merkmalsspalten vor Indikatoren, aus dem Schema: anfrage 6, person 11, risiko_kfz
12, risiko_hausrat 4, tarif 5, angebot 2, zahlung 3 — zusammen **43 von 88**.

#### 5. Datums- und Geldfelder

`b2_isolation_forest.py:341-357`:

| Feldtyp | Abbildung | Fundstelle |
|---|---|---|
| `DATUM` | `float(wert.toordinal())` — Tage seit dem proleptischen 1. Januar 1 | `:353-354` |
| `ZEITPUNKT` | `float((pd.Timestamp(wert) - _EPOCHE).total_seconds())`, `_EPOCHE = 1970-01-01` | `:355-356`, `:226` |
| `DEZIMAL` (Geld) | `float(wert)`, also `float(Decimal)` | `:357` |
| `GANZZAHL` | `float(wert)` | `:357` |

Ja, Datumsangaben werden in eine Zahl überführt — als Ordinalzahl des Kalendertages.
Zeitpunkte bewusst **nicht** über `datetime.timestamp()`: Das interpretiert einen naiven
Zeitpunkt in der Zeitzone des ausführenden Rechners und machte das Ergebnis maschinenabhängig
(Modul-Docstring `b2_isolation_forest.py:76-80`, Architekturregel A2).

Geld wird im Modellraum zu `float`. Das ist die einzige Stelle des Projekts, an der das
zulässig ist, und im Docstring `b2_isolation_forest.py:74-76` ausdrücklich so vermerkt;
fachlich bleibt Geld `Decimal`. Eine Währungs- oder Betragsnormierung findet **nicht** statt.

#### 6. Fehlwerte

Drei Mechanismen, kein Zeilenausschluss:

1. **Numerische Spalten: Imputation mit dem Median der Spalte** — `b2_isolation_forest.py:377`:
   `median = float(np.median(vorhanden)) if vorhanden else 0.0`. Eingesetzt wird er in `:378`.
   Eine vollständig leere Spalte wird damit konstant und fällt dem Varianzfilter zum Opfer
   (`:370-372`).
2. **Kategoriale Spalten: eigene Stufe `-1.0`** — `_FEHLSTUFE` in `b2_isolation_forest.py:219`,
   gesetzt in `:400`. Da die regulären Stufen bei `0.0` beginnen (`:398`), ist sie von jeder
   echten Kategorie unterscheidbar.
3. **Zusätzlicher Indikator je betroffener Spalte** — `b2_isolation_forest.py:436-438`. Trägt
   eine Spalte mindestens einen Fehlwert, entsteht direkt hinter ihr die binäre Spalte
   `<spalte>__fehlt` (`_INDIKATOR_SUFFIX` in `:222`).

Ein **Zeilenausschluss** findet nicht statt. Ausgeschlossen werden nur ganze Entitäten ohne
Zeilen oder ohne jede Varianz (`b2_isolation_forest.py:927-931`), und das wird berichtet.

Die Begründung für den Indikator steht im Modul-Docstring `b2_isolation_forest.py:54-66` und
gehört in die Arbeit: Eine mit dem Median aufgefüllte Zelle liegt per Konstruktion in der
Mitte der Verteilung und ist damit das Gegenteil einer Anomalie. Ohne Indikator hätte B2 auf
der Fehlerklasse F1 strukturell einen Recall nahe null — als Artefakt der Vorverarbeitung, nicht
als Eigenschaft des Verfahrens. Die Entscheidung fällt ausdrücklich **zugunsten der Baseline**.

#### 7. Skalierung oder Standardisierung

**Keine.** Im gesamten Modul kommt kein Scaler, keine Normalisierung und keine
Standardisierung vor; `_baue_merkmale` (`b2_isolation_forest.py:406-448`) stapelt die kodierten
Spalten unverändert mit `np.column_stack` (`:447`). Für einen Isolation Forest ist das
unerheblich — er splittet achsenparallel auf einzelnen Merkmalen und ist gegenüber monotonen
Umskalierungen einzelner Spalten invariant.

Die praktische Folge bleibt trotzdem erwähnenswert: Die Merkmale liegen in völlig verschiedenen
Größenordnungen nebeneinander (Sekunden seit 1970 in der Größenordnung 10⁹, ordinale
Kategorienstufen im einstelligen Bereich). Da jedes Merkmal für sich betrachtet wird, ist das
kein Fehler, sondern eine Eigenschaft des Verfahrens.

### Modell

#### 8. Der vollständige Konstruktoraufruf

Wörtlich aus `b2_isolation_forest.py:517-527`:

```python
from sklearn.ensemble import IsolationForest  # noqa: PLC0415 - Importkosten nur bei Bedarf

modell = IsolationForest(
    n_estimators=_N_ESTIMATORS,
    max_samples="auto",
    contamination="auto",
    bootstrap=False,
    random_state=int(seed_als_int(seed) % _SEED_MODUL),
)
modell.fit(matrix)
return np.asarray(modell.score_samples(matrix), dtype=np.float64)
```

mit `_N_ESTIMATORS = 100` (`b2_isolation_forest.py:232`) und `_SEED_MODUL = 2**32` (`:229`).
Das ist der einzige `IsolationForest`-Aufruf des Projekts.

#### 9. Die einzelnen Parameter

| Parameter | Wert | gesetzt? | Fundstelle |
|---|---|---|---|
| `n_estimators` | `100` | ja (entspricht dem sklearn-Standard) | `b2_isolation_forest.py:520`, `:232` |
| `max_samples` | `"auto"` | ja (entspricht dem sklearn-Standard) | `b2_isolation_forest.py:521` |
| `max_features` | `1.0` | **nicht gesetzt — scikit-learn-Standard** | im Aufruf `b2_isolation_forest.py:519-525` nicht enthalten |
| `bootstrap` | `False` | ja (entspricht dem sklearn-Standard) | `b2_isolation_forest.py:523` |
| `random_state` | aus der Seed-Ableitung des Laufs | ja (sklearn-Standard wäre `None`) | `b2_isolation_forest.py:524` |
| `contamination` | `"auto"` | ja (entspricht dem sklearn-Standard) | `b2_isolation_forest.py:522` |
| `n_jobs`, `verbose`, `warm_start` | `None`, `0`, `False` | **nicht gesetzt — scikit-learn-Standards** | — |

Für die Arbeit gehört die Bedeutung von `max_samples="auto"` dazu: scikit-learn setzt daraus
`min(256, n_samples)`. Jeder der 100 Bäume sieht also höchstens 256 Zeilen — bei der Entität
`angebot` mit rund 63.000 Zeilen sind das 0,4 Prozent je Baum. Das ist die
scikit-learn-Vorgabe und der veröffentlichte Standardwert des Verfahrens, aber es ist keine
Selbstverständlichkeit und sollte im Text stehen.

`contamination="auto"` ist gesetzt, wirkt aber nicht: Der daraus berechnete `offset_` wird nie
gelesen. Die Schwellen entstehen außerhalb des Modells (Punkt 12). Der Docstring
`b2_isolation_forest.py:507-508` sagt das ausdrücklich.

Der Modul-Docstring `b2_isolation_forest.py:151-155` hält fest, dass keine Hyperparametersuche
stattgefunden hat: Sie wäre ein zweites Experiment mit eigener Methodik.

#### 10. Herkunft von `random_state`

**Aus der Seed-Ableitung des Laufs**, nicht fest verdrahtet und nicht aus der Konfiguration.
Die Kette in voller Länge:

1. `scripts/evaluate.py:339-363` bildet den Modellstrom
   `lauf_seed(master_seed, Strom.MODELL, serie, design, segment, rate_in_bp, injektions_index)`
   — dieselben Faktorstufen wie der Injektionsstrom (`scripts/inject.py:328-336`).
   `Strom.MODELL = 2` steht in `src/common/seeding.py:77`.
2. Dieser Strom geht in den Konstruktor der Baseline: `scripts/evaluate.py:401`
   `IsolationForestBaseline(_seed_modell(config, optionen), wahrheit=wahrheit)`, gespeichert in
   `b2_isolation_forest.py:736`.
3. Je Entität wird daraus ein fester Teilstrom abgeleitet: `b2_isolation_forest.py:933`
   `teilstrom(self._seed, nummer)`, wobei `nummer` die Position der Entität in `ENTITAETEN`
   ist (`b2_isolation_forest.py:890`, `src/common/serialisierung.py:294`).
   `teilstrom` (`src/common/seeding.py:155-177`) bildet die Entropie direkt aus
   `[seed, nummer]` und benutzt bewusst **kein** `spawn()`.
4. Erst hier wird daraus eine ganze Zahl:
   `int(seed_als_int(seed) % 2**32)` (`b2_isolation_forest.py:524`, `src/common/seeding.py:198`).
   Die Modulo-Operation ist nötig, weil scikit-learn nur ganzzahlige Seeds unterhalb dieser
   Grenze annimmt (Docstring `b2_isolation_forest.py:144-145`).

Ein globaler Zustand (`np.random.seed`, `random.seed`) kommt nirgends vor.

#### 11. Neu fitten oder Modell wiederverwenden — und auf welchen Daten?

**Je Lauf wird neu gefittet.** Das Verfahrensobjekt entsteht je Lauf frisch
(`scripts/evaluate.py:401` in einer Lambda-Fabrik), und `_berechne`
(`b2_isolation_forest.py:886-904`) fittet je Entität genau einmal.

**Innerhalb eines Laufs wird das Ergebnis zwischengespeichert.** `_lauf`
(`b2_isolation_forest.py:877-884`) merkt sich Kontext und Ergebnis; Schlüssel ist die
**Objektidentität** des Kontexts (`:880`, `gespeichert[0] is kontext`), nicht sein Inhalt. Die
Pipeline reicht je Lauf genau ein Kontextobjekt an `erkenne`, `zellscores` und `sweep` weiter —
`erkenne` wird für die Laufzeitmessung und für das Schreiben der Meldungen zweimal aufgerufen
und beim zweiten Mal aus dem Zwischenspeicher beantwortet. Der Wald wird dabei nicht neu
gebaut. Die Begründung steht im Klassen-Docstring `b2_isolation_forest.py:707-713`.

**Gefittet und gescort wird auf denselben Daten.** `b2_isolation_forest.py:526-527`:
`modell.fit(matrix)` und unmittelbar danach `modell.score_samples(matrix)` — dieselbe `matrix`.
Es gibt keine Trennung in Trainings- und Testmenge. Das ist für unüberwachte Anomalieerkennung
üblich (es gibt keine Labels, an denen man überanpassen könnte) und sollte im Text als
Entwurfsentscheidung genannt werden.

Ebenso gehört dazu: Es wird **genau einmal** gefittet und **genau einmal** gescort, obwohl
sieben Kontaminationsstufen ausgewertet werden. Begründung im Modul-Docstring
`b2_isolation_forest.py:26-45`: `contamination` beeinflusst bei `IsolationForest` nicht das
Modell, sondern nur den Entscheidungs-Offset. Ein Neufitten je Stufe kostete das Siebenfache an
Rechenzeit ohne inhaltlichen Unterschied.

#### 12. Score und binäre Entscheidung

**`score_samples`** — `b2_isolation_forest.py:527`. `decision_function` und `predict` werden
nirgends aufgerufen (im ganzen Repository kommen beide Namen nur in Prosa vor).

Die Orientierung ist die von scikit-learn: **kleiner heißt anomaler**
(`b2_isolation_forest.py:285-286`, `:515`).

Die binäre Entscheidung je Stufe entsteht in zwei Schritten:

1. **Schwelle als Perzentil auf denselben Scores** — `b2_isolation_forest.py:530-542`, der Kern
   in `:541`:
   ```python
   {stufe: float(np.percentile(scores, 100.0 * stufe)) for stufe in CONTAMINATION_STUFEN}
   ```
   Die Schwellen werden je Entität gebildet (`b2_isolation_forest.py:941`), nicht global.
2. **Vergleich** — `b2_isolation_forest.py:545-547`:
   ```python
   return np.asarray(lauf.scores < lauf.schwellen[contamination], dtype=np.bool_)
   ```
   Anomal ist also `score < schwelle`, strikt kleiner. Dieselbe Konvention, die
   `IsolationForest` intern für `offset_` verwendet (`b2_isolation_forest.py:537-538`).

Für die PR-AUC gibt `zellscores` (`b2_isolation_forest.py:783-802`) den Score **negiert**
zurück (`:688`), weil die Auswertung die umgekehrte Orientierung verlangt: dort heißt größer
anomaler.

### Sweep und Auswahl

#### 13. Wo stehen die sieben Kontaminationsstufen?

**Im Code**, nicht in der Konfiguration — `b2_isolation_forest.py:205`:

```python
CONTAMINATION_STUFEN: Final[tuple[float, ...]] = (0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2)
```

Weder `config/default.yaml` noch `config/experiment.yaml` enthalten einen Eintrag zu
`contamination` oder zu B2 über die Verfahrensliste hinaus. Der Kommentar `:203-204` hält fest,
dass die Reihenfolge Teil des Ausgabeformats ist.

Die Vorgabestufe ohne Ground Truth ist `STANDARD_CONTAMINATION = 0.02`
(`b2_isolation_forest.py:208`), verwendet in `:637`.

#### 14. Auswahlkriterium, Ebene und tatsächliches Ergebnis in s01

**Kriterium: beste F1. Ebene: Satzebene, bei `mitgezogen_als_fehler = False`.**

- Die Wahrheitsmengen werden in `b2_isolation_forest.py:609-610` mit
  `mitgezogen_als_fehler=False` gezogen.
- Je Stufe wird die Konfusionsmatrix auf Satz- und Zellebene gebildet
  (`b2_isolation_forest.py:619-620`), die F1 der Satzebene in `:628`.
- Gewählt wird in `_beste_stufe` (`b2_isolation_forest.py:644-663`). **Bei Gleichstand gewinnt
  die kleinere `contamination`** (`:661`, strikt `>`): weniger markierte Zeilen bei gleicher
  Leistung ist die sparsamere Erklärung. Die Regel ist deterministisch und damit
  A2-verträglich.
- Der Vermerk im Ergebnis ist `_WAHL_UEBER_F1` (`b2_isolation_forest.py:211`) und steht in
  jeder `metrics.json` unter `verfahren.B2.stufenwahl`. Ohne Ground Truth stünde dort
  `_WAHL_OHNE_WAHRHEIT` (`:214`).
- Die gewählte Stufe gilt danach für **alle** Ebenen und **beide** Schalterstellungen von
  `mitgezogen_als_fehler`.

Das ist ein **ausgewiesener Vorteil für die Baseline**: Ein unüberwachtes Verfahren, das
seinen Betriebspunkt an der Wahrheit ausrichten darf, steht besser da als der Prototyp, der
ohne jede Anpassung antritt (Modul-Docstring `b2_isolation_forest.py:111-123`). `contamination`
wird ausdrücklich **nicht** auf die wahre Fehlerrate gesetzt (`:125-128`).

**Protokolliert ist es.** Der vollständige Sweep steht je Lauf in `metrics.json` unter
`verfahren.B2.sweep`, geschrieben in `scripts/evaluate.py:435` und dort eingehängt über
`src/evaluation/langformat.py:869`. Ausgewertet über alle 660 B2-Läufe der Serie s01 (560
Hauptversuch, 80 Teilversuch T1, 20 Mischmodus T3); alle 660 haben die Stufe über die F1
gewählt, keiner über die Vorgabe:

| Klasse | 0,001 | 0,005 | 0,01 | 0,02 | 0,05 | 0,1 | 0,2 | häufigste | n |
|---|---|---|---|---|---|---|---|---|---|
| F1 | 0 | 0 | 0 | 0 | 0 | 0 | **80** | 0,2 | 80 |
| F2 | 0 | 0 | 0 | 14 | 26 | 1 | **39** | 0,2 | 80 |
| F3 | 0 | 1 | 0 | 6 | 23 | 14 | **36** | 0,2 | 80 |
| F4 | 0 | 0 | 0 | 0 | 0 | 5 | **75** | 0,2 | 80 |
| F5 | 0 | 0 | 0 | 0 | 0 | 0 | **80** | 0,2 | 80 |
| F6 | 0 | 0 | 0 | 0 | 0 | 0 | **80** | 0,2 | 80 |
| F7 | 0 | 0 | 0 | 0 | 0 | 5 | **75** | 0,2 | 80 |
| F8 | 0 | 1 | 1 | 5 | **53** | 20 | 0 | 0,05 | 80 |
| mix | 0 | 0 | 0 | 0 | 0 | 0 | **20** | 0,2 | 20 |

Häufigste Stufe je Klasse und Fehlerrate (der Mischmodus lief nur bei 0,02):

| Klasse | 0,01 | 0,02 | 0,05 | 0,10 |
|---|---|---|---|---|
| F1 | 0,2 | 0,2 | 0,2 | 0,2 |
| F2 | 0,02 | 0,05 | 0,2 | 0,2 |
| F3 | 0,05 | 0,05 | 0,2 | 0,2 |
| F4 | 0,2 | 0,2 | 0,2 | 0,2 |
| F5 | 0,2 | 0,2 | 0,2 | 0,2 |
| F6 | 0,2 | 0,2 | 0,2 | 0,2 |
| F7 | 0,2 | 0,2 | 0,2 | 0,2 |
| F8 | 0,05 | 0,05 | 0,05 | 0,1 |

**Das gehört in die Arbeit:** In sechs von neun Klassen gewinnt mit 0,2 die **größte
angebotene** Stufe. Die F1 auf der Satzebene steigt dort also über den ganzen Sweep hinweg
monoton an — die Obergrenze des Sweeps ist bindend, nicht das Optimum. Ein weiter geöffneter
Sweep hätte B2 dort vermutlich noch etwas besser dastehen lassen. Da B2 selbst mit diesem
wahrheitsgestützten Betriebspunkt in keiner einzigen der sieben Hauptklassen gegen den
Prototyp gewinnt, schwächt das die Aussage nicht ab, sondern macht sie belastbarer — die
Grenze der Baseline liegt nicht an der Wahl des Schwellwerts.

Nur F8 (relationale Plausibilität) bevorzugt durchgängig eine kleine Stufe. F2 und F3 wandern
mit der Fehlerrate: Bei 0,01 und 0,02 gewinnt eine kleine Stufe, ab 0,05 die größte.

### Umrechnung auf die Zellebene

#### 15. Von der anomalen Zeile zur Zellmenge

`erkenne` (`b2_isolation_forest.py:742-781`) arbeitet so:

1. Über alle modellierten Entitäten und darin über alle Zeilen unterhalb der Schwelle
   (`:760-762`).
2. **Eine markierte Zeile ergibt genau eine `verstoss_id`** — `B2-anomalie#<laufende Nummer>`,
   sechsstellig, vergeben in Schema- und Zeilenreihenfolge (`:763-764`, Kennung
   `B2_REGEL_ID = "B2-anomalie"` in `:199`).
3. **Je befüllter Zelle dieser Zeile entsteht eine Meldezeile** (`:770-780`). Die Meldung nennt
   Score, Schwelle und Stufe (`:765-768`).

**„Befüllt" heißt: Rohwert weder `NA` noch Leerstring.** `b2_isolation_forest.py:451-470`, der
Kern in `:465`:

```python
(~roh[spalte].isna() & (roh[spalte] != LEER_ROH)).fillna(value=False).to_numpy(dtype=bool)
```

Das ist dieselbe Definition, mit der `spec/01`, Abschnitt 6 einen leeren Wert beschreibt.
Entscheidend: Die Maske wird auf der **Rohschicht** gebildet (`b2_isolation_forest.py:939`,
`:926`), nicht auf der typisierten. Ein Wert, der sich nicht parsen ließ, gilt hier trotzdem als
befüllt.

**Die Zeilenkennung ist nicht ausgenommen.** Die Spaltenliste für die Zellmarkierung ist
`SPALTEN_JE_ENTITAET[entitaet]` (`b2_isolation_forest.py:934`) — **alle** Schemaspalten,
einschließlich `row_id` und aller `*_id`-Spalten. Damit gilt für B2 eine Asymmetrie, die
ausdrücklich gewollt ist (Modul-Docstring `b2_isolation_forest.py:90-93` und `:95-109`):
Schlüsselspalten fließen **nicht** als Merkmal ein, zählen aber bei der Zellmarkierung **mit**.
Wie viele Zellmarkierungen auf `row_id` entfallen, steht je Lauf in `metrics.json` unter
`verfahren.B2.markierte_zellen_row_id` (`src/evaluation/langformat.py:796`) — im Beispiellauf
`s01/A/F1/r0100/w00` sind es 21.114 von 292.139.

Die Umrechnung ist für B2 bei der Precision ungnädig (eine verfälschte Zelle zieht rund zwei
Dutzend Fehlalarme nach sich) und beim Recall großzügig (wird die Zeile getroffen, gilt jede
ihrer Zellen als gefunden). Beides ist bekannt und im Docstring `b2_isolation_forest.py:103-109`
benannt; für B2 ist die **Satzebene** der Primärvergleich.

---

## Teil 2 — B0 und B3

### 16. B0: was das Pydantic-Modell tatsächlich prüft

Modul: `src/baselines/b0_schema.py` (737 Zeilen).

**Schicht: die Rohschicht.** `b0_schema.py:677` (`rahmen = kontext.raw[entitaet]`), Rohwerte
gelesen in `:515-525`. Ein leeres Feld wird beim Aufbau der Zeilendarstellung **weggelassen**
statt auf `None` gesetzt — nur so meldet pydantic den Fehlertyp `missing` statt eines
Typfehlers über `None` (Docstring `b0_schema.py:100-115`).

**Die sieben Modelle entstehen zur Importzeit** aus dem Schema, nicht von Hand:
`create_model` in `b0_schema.py:472-475`, aufgerufen aus `_baue_modelle` (`:479-507`),
Ergebnis in `MODELLE` (`:507`). Konfiguration aller sieben:
`ConfigDict(strict=False, extra="forbid")` (`b0_schema.py:474`).

**Erzeugt werden genau vier Arten von Constraints** (`_annotation`, `b0_schema.py:413-452`):

| Art | Umsetzung | Fundstelle |
|---|---|---|
| Typ | `_GRUNDTYP[feldtyp]`: `str`, `int`, `Decimal`, `date`, `datetime`, `bool` | `b0_schema.py:295-309`, `:447` |
| Nullbarkeit | Pflichtfeld ohne Vorgabewert, sonst `annotation \| None` mit Vorgabe `None` | `b0_schema.py:469`, Liste in `:282-297` |
| exakte Länge | `StringConstraints(min_length=n, max_length=n)`, 12 Felder | `b0_schema.py:439-441`, Liste `:237-252` |
| Höchstlänge | `StringConstraints(max_length=n)`, 8 Felder | `b0_schema.py:442-443`, Liste `:255-265` |

**Ja, es gibt drei Validatoren über den reinen Datentyp hinaus** — und alle drei sind im
Modul-Docstring als Grenzfall benannt:

1. `BeforeValidator(_lies_datum)` für jedes `DATUM` (`b0_schema.py:434-435`, Funktion
   `:337-357`). Er verlangt acht Ziffern und konstruiert daraus ein `datetime.date`; der
   31. Februar scheitert dabei zwangsläufig. Damit deckt B0 den Inhalt der Prototypregel R-009
   vollständig ab, **ohne sie zu kennen**. Der Docstring `b0_schema.py:44-72` argumentiert, dass
   das keine eingeschmuggelte Fachregel ist, sondern die Eigenschaft eines Typs: Die Menge der
   gültigen Kalendertage **ist** der Wertebereich von `date`. Diese Grenze gehört in die Arbeit,
   weil sie den überraschend hohen Recall von B0 auf der Fehlerklasse F2 erklärt.
2. `BeforeValidator(_lies_wahrheit)` für jedes `WAHRHEIT` (`b0_schema.py:436-437`, Funktion
   `:362-384`). Er akzeptiert **nur** `J` und `N` (`:381-384`) — de facto also eine
   Zwei-Werte-Aufzählung. Begründet in `:365-368`: pydantic würde im nachgiebigen Modus auch
   `true`, `yes` und `1` annehmen, und genau solche Fremdformen schreiben die
   Injektionsvarianten der Klasse F2 in ein Wahrheitsfeld. Ohne diese Einschränkung hätte B0
   dort einen blinden Fleck.
3. `AfterValidator(_pruefe_laengenmenge)` für `bic` (`b0_schema.py:444-445`, Funktion
   `:388-405`, Datenlage `LAENGENMENGE = {"bic": (8, 11)}` in `:273`). Bewusst als
   **Längenmenge** und nicht als regulärer Ausdruck.

**Nicht vorhanden sind:** reguläre Ausdrücke (kein `pattern=` im Modul), Wertebereiche (`ge`,
`le`, `gt`, `lt`), `max_digits`/`decimal_places`, Enums/Wertekataloge, Feldabhängigkeiten
innerhalb einer Zeile oder zwischen Entitäten, Fremdschlüsselauflösung und Prüfziffern
(IBAN nur 22 Zeichen, nicht ISO 7064). Die Auslassungen sind einzeln im Docstring
`b0_schema.py:23-42` begründet.

**Pflichtfelder sind nur die unbedingten** (`PFLICHTFELDER`, `b0_schema.py:282-297`): `row_id`,
alle Primär- und Fremdschlüssel sowie `anfrage.eingangszeitpunkt`, `anfrage.sparte` und
`person.plz`. Bedingte Pflichten — `person.nachname` („nicht leer, außer `anrede` = FIRMA"),
`person.email`, `anfrage.vorversicherer_vu_nr` — stehen ausdrücklich **nicht** darin. Der
Docstring `b0_schema.py:70-98` begründet das ausführlich und benennt die messbare Folge: Die
Fehlerklasse F1 trifft überwiegend Felder mit bedingtem Pflichtcharakter, B0 findet davon nur
den unbedingten Rest, und **genau dieser Abstand ist der Beitrag der Fehlertaxonomie**.

Berichtsform: `regel_id = B0-<feldname>`, `verstoss_id = B0-<feldname>#<Nummer>`; je
Einzelfehler eine Meldung. Da B0 keine mehrspaltigen Bedingungen kennt, ist die
Constraint-Ebene für B0 fast identisch zur Zellebene (Docstring `b0_schema.py:155-168`).

### 17. B3: welche G1-Regeln cuallee ausdrücken kann

Modul: `src/baselines/b3_framework.py` (1381 Zeilen). Vorgelegt bekommt B3 nur die G1-Regeln
R-001 bis R-025, also die Attributwertebene (`REGELN_G1 = 25` in `b3_framework.py:265`,
`REGELN_KATALOG = 58` in `:262`). Die Einstufung je Regel steht in `_AUSDRUECKBARKEIT`
(`b3_framework.py:302-329`).

**Ausdrückbar — 21 Regeln** (`_AUSDRUECKBARKEIT`, jeweils `"ja"`):

R-002, R-003, R-005, R-006, R-007, R-008, R-010, R-011, R-012, R-013, R-014, R-015, R-016,
R-017, R-018, R-019, R-020, R-021, R-022, R-023, R-024
(`b3_framework.py:305-306`, `:308-311`, `:313-327`).

Das sind Formatmuster, Katalogzugehörigkeiten und Wertebereiche — also genau die Regelformen,
die eine spaltenweise Check-API vorsieht. Der Anteil 21/25 = 0,84 und 21/58 = 0,3621 steht in
jeder `metrics.json` eines B3-Laufs unter `verfahren.B3.b3_bericht.anteil_ausdrueckbarer_regeln`
sowie in `results/tables/t5_frameworkvergleich.md`.

**Nicht in dieser Zahl enthalten — vier Regeln**, davon zwei gar nicht und zwei nur teilweise
formulierbar. Teilweise ausdrückbare Regeln zählen ausdrücklich **nicht** als ausdrückbar
(`b3_framework.py:156-157`, Feld-Docstring `:1116-1119`): eine halbe Regel ist keine.

| Regel | Einstufung | Grund in einem Satz | Fundstelle |
|---|---|---|---|
| **R-004** (IBAN-Prüfziffer, ISO 7064 Mod 97-10) | `nein` | Ein Modulo-97-Rechenverfahren ist ein Algorithmus, kein Prädikat; cuallee böte nur den Ausstieg `is_custom`, und eine Regel, die das Framework bloß aufruft statt formuliert, zählt nicht als ausdrückbar. | `b3_framework.py:307`, Begründung `:146-149` |
| **R-009** (jedes Datumsfeld ist ein existierender Kalendertag) | `nein` | Ein Muster erkennt acht Ziffern, aber nicht den 31. Februar — und die Datumsprädikate von cuallee setzen bereits einen Datumstyp voraus, den es auf der Rohschicht nicht gibt und auf der typisierten Schicht die Regel unverletzbar macht. | `b3_framework.py:312`, Begründung `:150-155` |
| **R-001** (Pflichtfelder) | `teilweise` | Der unbedingte Teil (sechs Kernpflichtfelder belegt) geht; der bedingte Teil („`anrede` ungleich FIRMA erzwingt ein `geburtsdatum`") ist eine bedingte funktionale Abhängigkeit und in einer spaltenweisen Check-API nicht formulierbar. | `b3_framework.py:304`, Begründung `:159-162` |
| **R-025** (implizite Fehlwerte / Sentinels) | `teilweise` | Die Sentinel-Liste geht, die Feldausnahmen nicht — in `jahresfahrleistung_km` und den Sublimit-Feldern ist `9999` ein legitimer Wert, weshalb die numerischen Sentinels ganz entfallen und nur Text- und Datumssentinels geprüft werden. | `b3_framework.py:328`, Begründung `:163-168` |

Die vier Regelformen, an denen eine spaltenweise Check-API generell scheitert — bedingte
Regeln in CFD-Form, relationale Regeln über mehrere Zeilen, quellenübergreifende Regeln und
algorithmische Regeln — sind im Modul-Docstring `b3_framework.py:25-38` aufgezählt.

**Eine Einschränkung, die in die Arbeit gehört:** Die Kennzahl „Anteil ausdrückbarer Regeln"
ist **nicht** frameworkunabhängig. Der Vergleich mit Great Expectations
(`results/tables/t5_frameworkvergleich.md`) zeigt 0,8571 statt 0,8400 auf derselben Auswahl:
`row_condition` deckt R-001 ab, `ExpectColumnValuesToMatchStrftimeFormat` deckt R-009 ab. An
R-004 scheitern beide. Frameworkübergreifend belastbar ist der relationale und
quellenübergreifende Kern der Grenze, nicht die Zahl selbst.

B3 arbeitet auf **beiden** Schichten: die Rohsicht in `b3_framework.py:1007-1034`
(`kontext.rahmen(Schicht.RAW, …)` in `:1025`), die numerische Sicht in `:1078-1105`
(`kontext.rahmen(Schicht.TYPED, …)` in `:1091`). Wegen des fehlenden Zeilenbezugs im
cuallee-Report trägt B3 `lokalisiert_zellen = False` und geht nicht in die Inferenzstatistik
ein (Docstring `b3_framework.py:40-58`).

---

## Teil 3 — Sichtprüfung

### 18. Hängt die B2-Merkmalsaufbereitung vom Ground Truth ab?

**Nein.** Kein Befund.

Der Ground Truth erreicht B2 an genau einer Stelle: über den Konstruktorparameter `wahrheit`
(`b2_isolation_forest.py:723`, gesetzt in `scripts/evaluate.py:401`), gespeichert als
`self._wahrheit` (`b2_isolation_forest.py:737`). Von dort wird er **ausschließlich** an
`_baue_sweep` weitergereicht (`b2_isolation_forest.py:897`) und dort nur zur Bewertung der
sieben Stufen benutzt (`:609-610`, `:619-620`). Das ist die in Punkt 14 beschriebene,
ausdrücklich als Vorteil ausgewiesene Stufenwahl.

Die Aufbereitungskette ist davon vollständig getrennt:

- `_baue_merkmale(typisiert, entitaet)` (`b2_isolation_forest.py:406`) nimmt nur den
  Datenrahmen und den Entitätsnamen entgegen.
- `_kodiere_numerisch` (`:360`) und `_kodiere_kategorial` (`:382`) nehmen nur Werte und
  Feldtyp.
- `_ist_schluessel` (`:328`) nimmt nur den Spaltennamen.
- `_scores(matrix, seed)` (`:504`) nimmt nur Matrix und Teilstrom.

Keine dieser Funktionen hat Zugriff auf `self`, auf die Fehlerklasse, auf die Fehlerrate oder
auf den Ground Truth. Auch über die Konfiguration gibt es keinen Weg: `config` wird in der
Aufbereitung nirgends gelesen, und `config/default.yaml` wie `config/experiment.yaml` enthalten
keinen B2-spezifischen Eintrag außer der Verfahrensliste.

Ebenfalls geprüft und unauffällig: Der Prüfkontext wird aus `ergebnis.df_raw_dirty` gebaut
(`scripts/evaluate.py:648`) — B2 sieht ausschließlich den verfälschten Datensatz, nie den
sauberen.

### 19. Hängt der Merkmalsraum von Fehlerklasse oder Fehlerrate ab?

**Ja — und zwar deutlich. Das ist ein Befund und gehört in die Arbeit.**

Zwei Stellen der Aufbereitung sind datenabhängig, und der verfälschte Datensatz ist Teil dieser
Daten:

1. **Die Indikatorspalten.** `b2_isolation_forest.py:436-438` legt `<spalte>__fehlt` genau dann
   an, wenn die Spalte im **vorliegenden** Datensatz mindestens einen Fehlwert trägt. Die
   Fehlerklasse F1 erzeugt Fehlwerte; F3 (Skalierung) erzeugt keine. Zusätzlich wird jeder
   Rohwert, der sich nicht parsen lässt, beim Aufbau der typisierten Schicht zu `pd.NA`
   (`src/rules/modell.py:494`) — auch Format- und Typfehler schlagen also auf den Merkmalsraum
   durch.
2. **Der Varianzfilter.** `b2_isolation_forest.py:440-444` entfernt jede Spalte mit
   `min == max`. Ob eine Spalte Varianz hat, hängt vom Datensatz ab.

Gemessen (rein lesend, kanonischer Basisdatensatz, `n_anfragen = 10000`; Spaltenzahl der
Merkmalsmatrix, Summe über alle sieben Entitäten):

| Datensatz | Merkmalsspalten gesamt | davon Indikatoren |
|---|---|---|
| clean | 121 | 35 |
| F1, Rate 0,01 | 172 | 81 |
| F1, Rate 0,10 | 175 | 87 |
| F3, Rate 0,10 | 122 | 36 |

Am deutlichsten bei `risiko_kfz`: 30 Spalten auf dem sauberen Datensatz, 31 unter F3, **52**
unter F1.

**Die Folge, die in die Arbeit gehört:** Der Vergleich über die Fehlerklassen hinweg ist für
B2 **nicht gleich konfiguriert**. Unter F1 arbeitet der Isolation Forest in einem um rund 45
Prozent breiteren Merkmalsraum als unter F3, und der Zuwachs besteht ausschließlich aus
Indikatorspalten, die das Fehlen genau der injizierten Werte anzeigen.

Drei Dinge sind dazu zu sagen, und alle drei sollten im Text stehen:

- Die Abhängigkeit ist **kein Zugriff auf den Ground Truth**. Der Indikator entsteht aus dem
  vorliegenden Datensatz, nicht aus dem Fehlerprotokoll; das Verfahren sieht, *dass* ein Wert
  fehlt, aber nicht, *dass er verfälscht wurde*. Fehlwerte gibt es auch im sauberen Datensatz
  (35 Indikatorspalten dort).
- Die Abhängigkeit ist **erklärt gewollt** und war vor der Messung begründet
  (`b2_isolation_forest.py:54-66`): Ohne Indikator hätte B2 auf F1 strukturell einen Recall
  nahe null, und zwar als Artefakt der Vorverarbeitung. Sie wirkt **zugunsten** von B2 in
  derjenigen Klasse, in der die Baseline sonst chancenlos wäre.
- Die Abhängigkeit **schwächt die Hauptaussage nicht ab, sondern verstärkt sie**: B2 tritt in
  der für sie günstigsten erreichbaren Form an — breiterer Merkmalsraum genau dort, wo es
  hilft, plus ein an der Wahrheit ausgerichteter Betriebspunkt — und verliert trotzdem in allen
  sieben Hauptklassen gegen den Prototyp.

Was man **nicht** sagen darf, solange das so ist: dass B2 „unter identischen Bedingungen" über
die Fehlerklassen hinweg verglichen wurde. Identisch ist der Algorithmus samt aller
Hyperparameter, nicht die Breite seiner Eingabe.

---

## Nebenbefunde beim Lesen

Zwei Dinge sind beim Lesen aufgefallen, die nicht Teil der Fragestellung waren. Sie werden hier
gemeldet und **nicht behoben**.

### Befund 21 — Abbildung 3 enthält die B2-Kurve nicht

`scripts/analyze.py:124` liest den Schwellen-Sweep unter dem Pfad

```python
inhalt.get("verfahrenszusatz", {}).get("B2", {}).get("sweep", [])
```

Geschrieben wird er aber unter `verfahren.B2.sweep`: `scripts/evaluate.py:435` liefert die
Zusatzangaben, und `src/evaluation/langformat.py:869` mischt sie **in den Verfahrensblock**
(`verfahren[name] = {**verfahren[name], **dict(angaben)}`). Einen Schlüssel `verfahrenszusatz`
gibt es in `metrics.json` nicht (`src/evaluation/langformat.py:871-877` zeigt die vollständige
Rückgabe: `run_id`, `erzeugt_von`, `faktorstufen`, `ground_truth`, `verfahren`).

`sammle_b2_sweep` gibt deshalb immer einen leeren Datenrahmen zurück. `abbildung_3`
(`src/evaluation/abbildungen.py:391`) prüft in `:411` auf `if not sweep.empty:` und überspringt
die Kurve stillschweigend. Nachgesehen in `results/figures/abb03_pr_kurve.png`: Die Abbildung
zeigt nur die Betriebspunkte von Prototyp und B0, ihre Legende hat zwei Einträge. Die
Bildunterschrift `results/figures/abb03_pr_kurve.txt` beschreibt dagegen eine Kurve mit sieben
beschrifteten Stufen.

Die Daten sind vollständig vorhanden — in jeder der 660 `metrics.json` mit B2. Betroffen ist
allein die Abbildung; keine Tabelle, keine Kennzahl und keine Hypothese liest den Sweep. Die
Tabelle in Punkt 14 dieses Dokuments ist aus denselben Dateien gerechnet.

### Befund 22 — die Merkmalszahl wird nirgends protokolliert

`metrics.json` hält für B2 `contamination`, `stufenwahl`, `uebersprungene_entitaeten` und den
vollständigen Sweep fest (`scripts/evaluate.py:429-436`), aber **nicht** die Breite der
Merkmalsmatrix je Entität. Angesichts von Befund 19 — der Merkmalsraum hängt von der
Fehlerklasse ab — wäre das die Größe, an der man die Ungleichheit der Bedingungen nachträglich
und ohne Neuberechnung hätte ablesen können. Sichtbar wurde sie hier nur durch eine eigens
gerechnete Messung.
