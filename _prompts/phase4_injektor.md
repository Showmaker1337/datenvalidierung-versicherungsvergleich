# Phase 4 — Fehlerinjektor und Ground Truth

> Voraussetzung: Phase 3 abgeschlossen, **Git-Tag `freeze-regelkatalog` gesetzt**.
> Kopiere alles ab der Trennlinie in Claude Code.

---

Baue den Fehlerinjektor. Lies vorher `CLAUDE.md` und **`spec/03_fehlerklassen.md`
vollständig**.

**Wichtigste Vorgabe dieser Phase:** `src/injector/` importiert **nichts** aus
`src/rules/`. Nicht die Regeln, nicht ihre Konstanten, nicht ihre Hilfsfunktionen. Du
darfst den Regelkatalog beim Bauen des Injektors **nicht als Vorlage verwenden**. Der
Injektor bildet empirische Fehlerursachen ab — Erfassungsfehler, Schnittstellenkonvertierung,
Legacy-Migration, Freitexteingabe —, nicht die Komplemente der Prüfbedingungen.

Diese Trennung ist der Kern der methodischen Absicherung gegen den Zirkularitätsvorwurf
und wird in der Arbeit am Importgraphen belegt.

## Aufgabe 1 — Modul `src/injector/`

```
src/injector/
├── __init__.py
├── modell.py       # Variantendefinition, Log-Schemata
├── varianten/
│   ├── f1_fehlend.py
│   ├── f2_format.py
│   ├── f3_wertebereich.py
│   ├── f4_unmoeglich.py
│   ├── f5_inkonsistenz.py
│   ├── f6_duplikate.py
│   ├── f7_aktualitaet.py
│   ├── f8_einheiten.py
│   └── heldout.py      # HO1, HO2
├── auswahl.py      # welche Zellen werden getroffen
├── protokoll.py    # error_log + error_log_records
└── pipeline.py
```

Öffentliche Schnittstelle:

```python
def injiziere(
    daten: dict[str, pd.DataFrame],
    fehlerrate: float,
    klassen_gewichte: dict[str, float],
    seed_inject: int,
    run_id: str,
) -> Injektionsergebnis        # df_dirty, error_log, error_log_records
```

## Aufgabe 2 — Alle Injektionsvarianten implementieren

Setze **jede** Variante aus `spec/03_fehlerklassen.md`, Abschnitt 2, um. Das sind 60
Varianten über zehn Klassen (F1–F8 mit 56, HO1 und HO2 mit 4). Jede bekommt eine stabile `injektor_variante_id` wie `F3-d`.

Besonders zu beachten:

- **F5-e** (Bruttobeitrag um 0,01 € verändern) soll **nicht** erkannt werden. Sie prüft,
  ob die Toleranzgrenze korrekt implementiert ist, und liefert einen erklärbaren False
  Negative — das ist ein Befund, kein Bug.
- **F7-d** und **F8-e** sollen ebenfalls nicht erkannt werden. Bei F8-e werden **alle**
  Angebote einer Anfrage durch 12 geteilt; die relationale Prüfung greift nicht, weil der
  Median mitwandert. Diese Variante ist der wertvollste Einzelfall des Injektors und gehört
  in die Diskussion der Arbeit.
- **F6 (Duplikate)** und **HO1** erzeugen zusätzliche Zeilen. Sie werden ausschließlich im
  satzbasierten Log protokolliert.
- **F8-a** wirkt auf Anbieter-Ebene: Ein Anbieter je Anfrage stellt die Einheitenkonvention
  um. Das ist ein Multi-Source-Fehler und muss über die Zuordnung Anbieter →
  Quellschnittstelle laufen.
- **Kohärente Skalierung bei F8-b bis F8-e und HO2-b.** Skaliert wird immer das **gesamte
  Beitragstupel** — `nettobeitrag_jahr_eur`, `versicherungsteuer_eur`,
  `bruttobeitrag_jahr_eur` und `zahlbeitrag_rate_eur` gemeinsam mit demselben Faktor.
  Würde nur der Zahlbeitrag skaliert, verletzten diese Varianten sofort R-031 und R-036 und
  wären garantiert erkannt — womit F8-e und HO2-b ihren Zweck verlören. Die Rangfolge ist
  mitzuziehen, sonst löst zusätzlich R-044 aus.

## Aufgabe 3 — Zellauswahl

- Der Injektor arbeitet auf der **Rohschicht** `df_raw` (alle Spalten String). Nur dort
  sind Format-, Typ- und Sentinel-Verfälschungen überhaupt schreibbar; eine typisierte
  Spalte nimmt weder `31022026` noch `"k.A."` auf, und `pyarrow` schreibt gemischt
  typisierte Spalten gar nicht erst.
- Die Zielzellen werden über den Generator aus `seed_inject` gezogen, unabhängig von
  `seed_base`. Damit lässt sich derselbe saubere Datensatz mit vielen verschiedenen
  Fehlerkonfigurationen verfälschen und die Injektionsvarianz von der Datenvarianz trennen.
- **Keine Doppelinjektion:** Ein Set bereits getroffener `(entitaet, row_id, spalte)`-Tripel
  wird geführt; bei Kollision wird neu gezogen.
- **`row_id` ist niemals Ziel.** Ebenso wenig Primärschlüsselspalten, außer eine Variante
  verlangt es ausdrücklich (F6).
- **Die Fehlerrate bezieht sich auf das klassenspezifische adressierbare Zelluniversum**,
  nicht auf alle befüllten Zellen des Datensatzes. Siehe `spec/03_fehlerklassen.md`,
  Abschnitt 3 — dort steht die verbindliche Definition und die Begründung. Der Injektor
  berechnet dieses Universum je Klasse vor der Ziehung und protokolliert seine Größe im
  `manifest.json`. Verlangt die angeforderte Rate mehr Zellen als vorhanden, **bricht er
  mit einer klaren Fehlermeldung ab** und füllt nicht stillschweigend weniger auf.
  Dokumentiere die Definition zusätzlich in `README.md` — sie ändert die Interpretation
  jeder Ergebnistabelle.

## Aufgabe 4 — Die sechs Protokollregeln

Setze `spec/03_fehlerklassen.md`, Abschnitt 5, vollständig um:

1. `row_id` niemals Ziel.
2. Keine Doppelinjektion.
3. **Effektivitätsprüfung:** Für jede Log-Zeile gilt `wert_clean != wert_dirty`. Erzeugt
   eine Variante zufällig denselben Wert, wird sie verworfen und neu gezogen. Ohne diese
   Prüfung entsteht eine Phantom-Ground-Truth und damit ein garantiertes False Negative.
4. **Unabhängiger Diff-Gegencheck** — siehe Aufgabe 5.
5. Clean-Baseline-Lauf (bereits in Phase 3 erbracht, hier erneut als Regressionstest).
6. **Persistenz:** `config.yaml`, `error_log.parquet`, `error_log_records.parquet`,
   SHA-256 von `df_clean` und `df_dirty` je Lauf.

## Aufgabe 5 — Der unabhängige Gegencheck

`src/verify/diff_check.py` — bewusst **außerhalb** von `src/injector/`, in einem eigenen
Modul. Der Architekturtest prüft, dass `src/verify/` nichts aus `src/injector/` importiert.

Dieses Modul berechnet ein zellweises Diff zwischen `df_clean` und `df_dirty` über
`row_id` und gleicht es gegen `error_log` ab:

- Jede im Diff gefundene Abweichung muss im `error_log` stehen.
- Jede `error_log`-Zeile muss im Diff auftauchen.
- Zeilen, die nur in `df_dirty` existieren, müssen im `error_log_records` stehen.
- Zeilen, die nur in `df_clean` existieren, ebenso.

**Implementiere dieses Modul, ohne Code aus `src/injector/` wiederzuverwenden.** Es deckt
genau die Protokollierungslücken auf, die der Injektor selbst nicht sehen kann. Ein
Gegencheck, der die Logik des Geprüften teilt, prüft nichts.

Ergebnis nach `results/ground_truth_check.json`. Diese Datei gehört in den Anhang der
Arbeit.

## Aufgabe 6 — Ausgabe

`scripts/inject.py --serie <name> --design A|B --klasse F3 --rate 0.02 --wdh 7`

schreibt nach `data/runs/<serie>/<design>/<klasse>/<rate>/<wdh>/`:

**Das Pfadschema ist wichtig:** In Phase 6 variieren Fehlerklasse, Fehlerrate,
Wiederholung und Varianzdesign. Ein Pfad, der nur die Fehlerrate kodiert, lässt tausende
Läufe einander überschreiben. Für den Mischmodus-Teilversuch tritt `mix` an die Stelle der
Klasse.

- je Entität eine Parquet-Datei
- `error_log.parquet`, `error_log_records.parquet`
- `manifest.json` mit allen Seeds, Hashes, der Größe des adressierbaren Zelluniversums und
  der Zahl injizierter Fehler je Klasse und je Variante

**Aufräumen:** `df_raw_dirty` wird nach der Auswertung verworfen und **nicht** dauerhaft
gespeichert. Bei mehreren tausend Läufen à rund 60.000 Zeilen entstünden sonst zweistellige
Gigabyte. Der verfälschte Datensatz ist aus `seed_base` und `seed_inject` jederzeit exakt
reproduzierbar — das ist zugleich das saubere Argument dafür. Dauerhaft aufbewahrt werden
nur `error_log`, `error_log_records`, `detections` und `metrics.json`.

## Aufgabe 7 — Tests

- `tests/test_ground_truth.py`:
  - Effektivitätsprüfung hält für alle Log-Zeilen
  - keine Doppelinjektion
  - `row_id` nie verfälscht
  - Diff-Gegencheck ohne Abweichung, für mindestens drei Fehlerraten
  - Zahl der Log-Zeilen entspricht der angeforderten Fehlerrate bezogen auf das
    klassenspezifische Universum (Toleranz 5 % relativ)
  - Bei einer Rate, die das Universum übersteigt, bricht der Injektor mit klarer Meldung ab
- `tests/test_injektor/test_varianten.py`: Je Variante ein Test, der prüft, dass die
  Verfälschung die beabsichtigte Form hat (etwa: F3-d setzt tatsächlich `zahlweise = 3`).
- `tests/test_reproduzierbarkeit.py` erweitern: gleicher `seed_inject` → identische
  `error_log`-Hashes.
- `tests/test_architecture.py`: **muss jetzt zusätzlich prüfen**, dass `src/injector/`
  nichts aus `src/rules/` importiert — direkt oder transitiv.

## Abnahmekriterien

1. Alle Varianten aus `spec/03_fehlerklassen.md` implementiert.
2. Diff-Gegencheck ohne Abweichung.
3. `results/ground_truth_check.json` erzeugt.
4. `tests/test_architecture.py` grün — kein Import von `rules` in `injector`.
5. Reproduzierbarkeit über Seeds bestätigt.

## Nicht in dieser Phase

Keine Metriken, keine Baselines, keine Experimentläufe. Und vor allem: **keine Änderung am
Regelkatalog.** Fällt dir beim Bauen des Injektors auf, dass eine Regel eine Variante nicht
fängt — das ist ein Ergebnis, kein Fehler. Notiere es, ändere nichts.

Halte am Ende an und berichte: Welche Varianten hast du gebaut, wie viele Fehler wurden
je Klasse injiziert, und ist der Gegencheck sauber durchgelaufen?
