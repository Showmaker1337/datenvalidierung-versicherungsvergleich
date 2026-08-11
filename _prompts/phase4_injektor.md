# Phase 4 — Fehlerinjektor und Ground Truth

> Voraussetzung: Phase 3 abgeschlossen, **Git-Tag `freeze-regelkatalog` gesetzt**.
> Neuer Chat. Kopiere alles ab der Trennlinie in Claude Code.

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

## Aufgabe 0 — Orientierung (immer zuerst)

Dieser Prompt setzt voraus, dass die vorherigen Phasen abgeschlossen sind, aber **nicht**,
dass du sie selbst gebaut hast. Verschaffe dir zuerst einen Überblick, bevor du etwas Neues
schreibst:

1. `CLAUDE.md` lesen — Architekturregeln und Konventionen.
2. Die in diesem Prompt genannten Abschnitte der `spec/`-Dateien lesen.
3. **Den vorhandenen Code sichten:** `src/common/` vollständig, dazu die Module der
   vorherigen Phasen. Übernimm die dort etablierten Funktionsnamen, Signaturen und
   Konventionen, statt neue zu erfinden.
4. `docs/iteration_log.md`, `results/freeze.json` und `git log --oneline` überfliegen —
   dort stehen die Entscheidungen der vorherigen Phasen und der Stand des Freeze.

Erfinde keine Funktion neu, die es schon gibt. Findest du einen Widerspruch zwischen diesem
Prompt und dem vorhandenen Code, melde ihn, statt eigenmächtig eine Seite zu ändern.

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
    daten_raw: dict[str, pd.DataFrame],   # Rohschicht, alle Spalten String
    fehlerrate: float,
    klassen_gewichte: dict[str, float],
    seed_inject: SeedSequence,
    run_id: str,
) -> Injektionsergebnis        # df_raw_dirty, error_log, error_log_records
```

**Zwei Festlegungen zur Signatur**, weil frühere Fassungen dieses Prompts sie verkürzt
notiert hatten:

- `seed_inject` ist eine **`numpy.random.SeedSequence`**, kein `int` — genau wie
  `seed_basis` beim Generator. Ein roher `int` würde A2 unterlaufen: Die Faktorstufen
  gehen über `lauf_seed(master, strom, *faktoren)` in den Strom ein, und dieser Mechanismus
  steht seit Phase 1. Der vorhandene Code gewinnt.
- Der Parameter heißt `daten_raw`, weil der Injektor ausschließlich auf der Rohschicht
  arbeitet (Aufgabe 3). Wird ihm versehentlich `df_typed` übergeben, soll er das erkennen
  und mit klarer Meldung abbrechen — keine stille Konvertierung.

## Aufgabe 2 — Alle Injektionsvarianten implementieren

Setze **jede** Variante aus `spec/03_fehlerklassen.md`, Abschnitt 2, um. Das sind 60
Varianten über zehn Klassen (F1 6, F2 12, F3 9, F4 7, F5 9, F6 4, F7 4, F8 5, HO1 2,
HO2 2). Jede bekommt eine stabile `injektor_variante_id` wie `F3-d`.

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

### F5-d und F5-e sind Senkungen, keine Erhöhungen

`spec/03` lässt die Richtung offen („um 0,50 € / 0,01 € verändern"). Setze beide als
**Verringerung** des Bruttobeitrags um. Trage diese Präzisierung in `spec/03` nach; sie
ändert keine Regel und ist deshalb kein Fall von Iteration 2.

Der Grund liegt bei R-036 (`zahlbeitrag_rate_eur` × Ratenanzahl ≥ `bruttobeitrag_jahr_eur`
− 0,01 × Ratenanzahl). Bei jährlicher Zahlweise ist die Ratenanzahl 1 und der Ratenzuschlag
0, also gilt auf sauberen Daten `rate = brutto` — die Ungleichung ist exakt ausgeschöpft.

- Eine **Erhöhung** um 0,50 € verletzt dort zusätzlich R-036. F5-d würde dann von zwei
  Regeln gemeldet, und die Zuordnung Variante → Regel in der Ergebnistabelle wäre falsch —
  genau der Fehler, den `spec/03` bei der kohärenten Skalierung schon einmal beschreibt.
- Eine **Erhöhung** um 0,01 € landet bei jährlicher Zahlweise exakt auf der Grenze von
  R-036. Sie besteht die Prüfung zwar (`≥`), aber eine „erwartet unentdeckte" Variante
  darf nicht auf einer Grenzgleichheit balancieren.
- Eine **Senkung** ist in beiden Fällen eindeutig: R-036 bekommt zusätzlichen Spielraum,
  R-031 entscheidet allein. F5-d wird sauber von R-031 gefangen, F5-e sauber von keiner.

Als Fehlerbild ist die Senkung ebenso realistisch wie die Erhöhung — ein Rundungs- oder
Übertragungsfehler kennt keine Vorzugsrichtung.

## Aufgabe 3 — Zellauswahl

- Der Injektor arbeitet auf der **Rohschicht** `df_raw` (alle Spalten String). Nur dort
  sind Format-, Typ- und Sentinel-Verfälschungen überhaupt schreibbar; eine typisierte
  Spalte nimmt weder `31022026` noch `"k.A."` auf, und `pyarrow` schreibt gemischt
  typisierte Spalten gar nicht erst.
- Die Zielzellen werden über den Generator aus `seed_inject` gezogen, unabhängig von
  `seed_basis`. Damit lässt sich derselbe saubere Datensatz mit vielen verschiedenen
  Fehlerkonfigurationen verfälschen und die Injektionsvarianz von der Datenvarianz trennen.
- **Keine Doppelinjektion:** Ein Set bereits getroffener `(entitaet, row_id, spalte)`-Tripel
  wird geführt; bei Kollision wird neu gezogen.
- **`row_id` ist niemals Ziel.** Ebenso wenig Primärschlüsselspalten, außer eine Variante
  verlangt es ausdrücklich (F6).
- **Neue Zeilen bekommen neue `row_id`s.** F6 und HO1 duplizieren Sätze; die Kopie erhält
  eine frische, im Datensatz noch nicht vergebene `row_id`, die Originalzeile bleibt
  unverändert. Ihre `row_id` wandert als `referenz_row_id` ins satzbasierte Log. Das ist
  keine Formalie: Der Gegencheck aus Aufgabe 5 joint `df_clean` und `df_dirty` über
  `row_id` — eine wiederverwendete `row_id` ließe den Join aufblähen und den Check
  wertlos werden.
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

**Verhältnis zu `run_id` — bitte auflösen, nicht nebeneinander stehen lassen.** `CLAUDE.md`,
Abschnitt 3, nennt bisher `data/runs/<run_id>/`, und die Läufe aus Phase 2 und 3 heißen
flach `baseline01` und `freeze_check`. Beides soll weiter gelten:

- Ad-hoc-Läufe ohne Faktorstufen behalten die flache Form `data/runs/<run_id>/`.
- Experimentläufe bekommen die verschachtelte Form oben, und ihr `run_id` ist dieselbe
  Information als ein Token: `<serie>_<design>_<klasse>_r<bp>_w<nn>`, etwa
  `s01_A_F3_r0200_w07`. Dabei ist `<bp>` die Rate in Basispunkten, vierstellig
  (`round(rate * 10000)`, also 0,02 → `0200`), und `<nn>` die Wiederholung zweistellig.
  Dasselbe Token bildet die Segmente `<rate>` und `<wdh>` im Pfad.

Damit bleibt A2 wörtlich erfüllt — der Lauf ist allein aus `run_id` und Konfiguration
reproduzierbar, weil `run_id` alle Faktorstufen trägt. Aktualisiere `CLAUDE.md`,
Abschnitt 3, entsprechend und schreibe `run_id` in jedes `manifest.json`.

Geschrieben werden:

- `error_log.parquet`, `error_log_records.parquet`
- `manifest.json` mit `run_id`, allen Seeds, Hashes, der Größe des adressierbaren
  Zelluniversums und der Zahl injizierter Fehler je Klasse und je Variante

**Aufräumen — und der Widerspruch dazu, den frühere Fassungen dieses Prompts hatten.**
`df_raw_dirty` wird **nicht** dauerhaft gespeichert. Bei mehreren tausend Läufen à rund
60.000 Zeilen entstünden zweistellige Gigabyte. Der verfälschte Datensatz ist aus
`seed_basis` und `seed_inject` jederzeit exakt reproduzierbar — das ist zugleich das
saubere Argument dafür. Dauerhaft aufbewahrt werden nur `error_log`,
`error_log_records`, `manifest.json` und später `detections` und `metrics.json`.

Für diese Phase brauchst du die verfälschten Daten aber zum Hinsehen. Gib `inject.py`
deshalb ein **`--behalten`**-Flag, das die Parquet-Dateien je Entität zusätzlich ablegt.
Standard ist **aus**. Der Gegencheck aus Aufgabe 5 läuft im selben Prozess auf den
DataFrames im Speicher und braucht die Dateien nicht.

## Aufgabe 7 — Tests

- `tests/test_ground_truth.py`:
  - Effektivitätsprüfung hält für alle Log-Zeilen
  - keine Doppelinjektion
  - `row_id` nie verfälscht, neue Zeilen haben neue `row_id`s
  - Diff-Gegencheck ohne Abweichung, für mindestens drei Fehlerraten
  - Zahl der Log-Zeilen entspricht der angeforderten Fehlerrate bezogen auf das
    klassenspezifische Universum (Toleranz 5 % relativ)
  - Bei einer Rate, die das Universum übersteigt, bricht der Injektor mit klarer Meldung ab
- `tests/test_injektor/test_varianten.py`: Je Variante ein Test, der prüft, dass die
  Verfälschung die beabsichtigte Form hat (etwa: F3-d setzt tatsächlich `zahlweise = 3`).
- `tests/test_reproduzierbarkeit.py` erweitern: gleicher `seed_inject` → identische
  `error_log`-Hashes.

### `tests/test_architecture.py` — jetzt zum ersten Mal aussagekräftig

Bis eben enthielt `src/injector/` nur eine leere `__init__.py`. Die A1-Prüfung war damit
**trivial grün**: Es gab keinen Import, den sie hätte finden können. Ab dieser Phase prüft
sie echten Code, und genau darauf beruft sich die Arbeit.

Ergänze deshalb zwei Dinge:

1. Die Prüfung erfasst `src/injector/` → `src/rules/` **direkt und transitiv**, ebenso
   `src/verify/` → `src/injector/`.
2. Eine **Negativkontrolle**: ein Test, der dem Prüfmechanismus einen künstlichen
   Importgraphen mit einer verbotenen Kante vorlegt und erwartet, dass er sie meldet.
   Ein Test, der nicht fehlschlagen kann, belegt nichts — und dieser Test trägt in der
   Arbeit die Aussage, dass Injektor und Regelwerk unabhängig sind. Er soll zeigen können,
   dass er greift.

## Abnahmekriterien

1. Alle 60 Varianten aus `spec/03_fehlerklassen.md` implementiert.
2. Diff-Gegencheck ohne Abweichung.
3. `results/ground_truth_check.json` erzeugt.
4. `tests/test_architecture.py` grün, inklusive Negativkontrolle.
5. Reproduzierbarkeit über Seeds bestätigt.

## Nicht in dieser Phase

Keine Metriken, keine Baselines, keine Experimentläufe.

Und vor allem: **keine Änderung am Regelkatalog.** Fällt dir beim Bauen des Injektors auf,
dass eine Regel eine Variante nicht fängt — das ist ein Ergebnis, kein Fehler. Notiere es
in `docs/iteration_log.md`, ändere nichts.

Die Entscheidungsprobe dafür ist die, die du beim Freeze selbst formuliert hast:

> Ändert sich durch die Korrektur die Menge der gemeldeten Zellen auf irgendeinem
> Datensatz? Ja ⇒ Regeländerung, Iteration 2. Nein ⇒ Korrektur am Beleg.

Präzisierungen am Injektor, an `spec/03` und an Formulierungen fallen unter „Beleg" und
sind frei. Prädikate, Wertebereiche, Schwellenwerte, Geltungsbereiche, Schweregrade und
die Achsenzuordnung in `spec/02` sind eingefroren.

Halte am Ende an und berichte: Welche Varianten hast du gebaut, wie viele Fehler wurden
je Klasse injiziert, und ist der Gegencheck sauber durchgelaufen?
