# Regelbasierte Datenvalidierung in Versicherungsvergleichssystemen

Prototyp und Evaluationsumgebung zur Bachelorarbeit:

> **Regelbasierte Datenvalidierung in Versicherungsvergleichssystemen: Entwicklung und
> experimentelle Evaluation eines Prototyps zur Erkennung typischer
> Datenqualitätsmängel**

## Forschungsfrage

> Inwieweit kann ein regelbasiertes Validierungsverfahren, dessen Regeln aus einer
> literaturbasiert hergeleiteten Fehlertaxonomie abgeleitet sind, Datenqualitätsmängel in
> strukturierten Daten von Versicherungsvergleichssystemen zuverlässig erkennen?

## Was dieses Repository enthält

Das Projekt erzeugt einen synthetischen Datensatz, verfälscht ihn kontrolliert, lässt einen
Regelkatalog darauf laufen und misst die Erkennungsleistung gegen den bekannten Ground
Truth.

**Der Prototyp erkennt Fehler. Er korrigiert sie nicht.** Reparatur liegt ausdrücklich
außerhalb des Scopes.

## Datenschutz — ausschließlich synthetische Daten

Es werden **keinerlei echte Personen- oder Bestandsdaten** verarbeitet. Sämtliche Datensätze
werden zur Laufzeit synthetisch erzeugt (Faker, Gebietsschema `de_DE`, deterministisch
geseedet). Es finden **keine Netzwerkzugriffe zur Laufzeit** statt; alle Referenzdaten liegen
als versionierte Dateien unter `data/reference/` im Repository.

## Installation

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
.venv/bin/python -m pip install -r requirements.txt           # Linux/macOS
```

Getestet mit CPython 3.12.10 unter Windows 11. `requires-python` steht auf `>=3.12`, weil
die Typprüfung der numpy-Stubs Python 3.12 voraussetzt.

Eine Installation des Projekts selbst ist nicht nötig: `pyproject.toml` legt das
Wurzelverzeichnis über `tool.pytest.ini_options.pythonpath` auf den Importpfad, und die
Skripte unter `scripts/` setzen ihn beim Start selbst.

## Phasenübersicht

| Phase | Ergebnis | Kommando |
|---|---|---|
| 0 | Git-Repository, `.gitignore`, `.gitattributes`, privates GitHub-Repo | — (abgeschlossen) |
| 1 | Projektgerüst, `src/common/`, Referenzdaten | `python scripts/build_reference.py` (abgeschlossen) |
| 2 | `df_clean` — der saubere synthetische Datensatz in beiden Schichten | `python scripts/generate.py --run-id <id>` (abgeschlossen) |
| 3 | Regelkatalog implementiert, Clean-Baseline-Lauf ohne Meldungen | `python scripts/validate.py --run-id <id> --dataset clean` (abgeschlossen) |
| **→** | **Freeze des Regelkatalogs** (`git tag freeze-regelkatalog`) | — |
| 4 | `df_raw_dirty` + Ground Truth + unabhängiger Gegencheck | `python scripts/inject.py --serie s01 --design A --klasse F3 --rate 0.02 --wdh 7` (abgeschlossen) |
| 5 | Metriken sowie die Baselines B0, B2 und B3 | folgt in Phase 5 |
| 6 | Hauptversuch, Teilversuche, Statistik, Abbildungen und Tabellen | folgt in Phase 6 |

Die Einstiegspunkte je Phase entstehen unter `scripts/` beziehungsweise in `src/cli.py`. Die
konkreten Kommandos werden hier eingetragen, sobald sie existieren.

## Kommandos

```bash
python -m src.cli config
```

Zeigt die geladene Konfiguration und die Kurzhashes der sieben Referenztabellen.

```bash
python scripts/build_reference.py
```

Erzeugt die Referenztabellen unter `data/reference/` deterministisch neu. Sie sind
versioniert und müssen im Normalfall **nicht** neu erzeugt werden — der Aufruf dient dem
Nachweis, dass die eingecheckten Dateien aus `master_seed` und Konfiguration hervorgehen.
Optionen: `--ziel VERZEICHNIS`, `--seed ZAHL`, `--still`.

```bash
python scripts/generate.py --run-id lauf01
```

Erzeugt den sauberen Datensatz unter `data/runs/<run_id>/clean/`: je Entität eine
Parquetdatei in `typed/` und `raw/` sowie `manifest.json` mit Zeilenzahlen, SHA-256-Werten,
Seeds und der vollständigen Konfiguration. Optionen: `--config DATEI`, `--seed ZAHL`,
`--n-anfragen ZAHL`, `--still`.

Ein Lauf mit der ausgelieferten Konfiguration erzeugt 10.000 Anfragen, 12.514 Personen,
7.000 Kfz-Risiken, 3.000 Hausratrisiken, 231 Tarife, 62.826 Angebote und 10.000 Zahlungen
in rund zehn Sekunden.

```bash
python scripts/validate.py --run-id lauf01 --dataset clean
```

Führt den vollständigen Regelkatalog auf dem sauberen Datensatz aus. Geschrieben werden
`results/clean_baseline.json` sowie unter `data/runs/<run_id>/clean/` die Rohtreffer je Regel
(`detections.parquet`), die Vereinigungsmenge markierter Zellen
(`markierte_zellen.parquet`), die satzbezogenen Befunde (`detections_records.parquet`) und
die Laufzeit je Regel (`rule_timing.json`). Optionen: `--config DATEI`, `--still`.

```bash
python scripts/inject.py --serie s01 --design A --klasse F3 --rate 0.02 --wdh 7 --clean-run lauf01
```

Verfälscht die Rohschicht kontrolliert, schreibt beide Ground-Truth-Logs und lässt den
unabhängigen Gegencheck darüber laufen. Geschrieben werden nach
`data/runs/<serie>/<design>/<klasse>/<rate>/<wdh>/` die Dateien `error_log.parquet`,
`error_log_records.parquet`, `config.yaml` und `manifest.json` sowie nach
`results/ground_truth_check.json` der Bericht des Gegenchecks. Der Rückgabewert ist `1`,
wenn der Gegencheck eine Abweichung findet.

Optionen: `--config DATEI`, `--clean-run ID` (ohne Angabe wird der saubere Datensatz aus dem
Master-Seed erzeugt), `--seed ZAHL`, `--n-anfragen ZAHL`, `--behalten`, `--still`. Für den
Mischmodus-Teilversuch `--klasse mix`.

```bash
python scripts/export_katalog.py
```

Erzeugt `results/regelkatalog.csv` aus den Regel-Metadaten — die Mapping-Tabelle für den
Anhang der Arbeit. Optionen: `--ziel VERZEICHNIS`, `--still`.

```bash
python -m pytest
```

Vollständige Testsuite.

```bash
python -m ruff check . && python -m mypy
```

Linting (vollständiger ruff-Regelsatz) und strikte Typprüfung.

## Reproduzierbarkeit

Jeder Lauf ist allein aus `run_id` und Konfiguration exakt reproduzierbar. Das Seeding
erfolgt hierarchisch über `numpy.random.SeedSequence`; ein globaler Seed wird nirgends
verwendet. Das fachliche Referenzdatum stammt aus der Konfiguration (`stichtag`), nicht aus
der Systemzeit.

Zwei Ebenen (`src/common/seeding.py`):

- `wurzel_seeds(master_seed)` spaltet den Master-Seed einmalig in die Ströme *basis*,
  *injektion* und *modell* auf.
- `lauf_seed(master_seed, strom, *faktoren)` leitet den Seed eines Einzellaufs **aus seiner
  Faktorkombination** ab. `SeedSequence.spawn()` ist ein Zähler und damit
  reihenfolgeabhängig; in Phase 6 hingen die Ergebnisse damit an der Worker-Zahl.

Faker wird über `seed_instance` geseedet, nicht über das klassenweite `Faker.seed` — sonst
teilten sich alle Instanzen im Prozess einen globalen Zustand.

- **Python:** 3.12 (getestet mit 3.12.10)
- **Abhängigkeiten:** `requirements.txt` mit gepinnten Versionen

Zeilenenden sind über `.gitattributes` auf LF festgelegt und `core.autocrlf` steht auf
`false`, damit die SHA-256-Hashes der CSV- und Parquet-Dateien plattformübergreifend stabil
bleiben.

Laufartefakte unter `data/runs/` sind bewusst nicht versioniert — sie sind aus Master-Seed
und Konfiguration exakt reproduzierbar.

### Laufverzeichnisse — zwei Formen

Ad-hoc-Läufe ohne Faktorstufen behalten die flache Form `data/runs/<run_id>/`.
Experimentläufe bekommen die verschachtelte Form
`data/runs/<serie>/<design>/<klasse>/<rate>/<wdh>/`, weil in Phase 6 Fehlerklasse,
Fehlerrate, Wiederholung und Varianzdesign variieren und ein Pfad, der nur die Fehlerrate
kodierte, tausende Läufe einander überschreiben ließe.

Die `run_id` trägt dieselbe Information als ein Token: `s01_A_F3_r0200_w07`. Dabei ist der
Ratenteil die Rate in Basispunkten, vierstellig (0,02 → `0200`), und der Wiederholungsteil
zweistellig. Damit bleibt A2 wörtlich erfüllt: Der Lauf ist allein aus `run_id` und
Konfiguration reproduzierbar. Für den Mischmodus tritt `mix` an die Stelle der Klasse.

`df_raw_dirty` wird **nicht** dauerhaft gespeichert; der verfälschte Datensatz ist aus
`seed_basis` und `seed_inject` jederzeit exakt reproduzierbar. `--behalten` legt ihn zum
Hinsehen zusätzlich unter `dirty/` ab.

## Der saubere Datensatz (Phase 2)

Der Generator erzeugt einen **vollständig regelkonformen** Datensatz. Er kennt den
Regelkatalog nicht und importiert nichts aus `src/rules` oder `src/injector`
(Architekturregel A1); er erfüllt die fachlichen Abhängigkeiten, weil sie in der Domäne
gelten.

Sieben Entitäten, in beiden Schichten abgelegt: `anfrage`, `person`, `risiko_kfz`,
`risiko_hausrat`, `tarif`, `angebot`, `zahlung`.

### Zwei Datenschichten

`df_typed` ist die typisierte Innenansicht (`datetime.date`, `Decimal`, `int`, `bool`),
`df_raw` die Rohschicht mit **allen** Spalten als Zeichenkette. Ohne diese Trennung wären
mehrere Regeln per Konstruktion nicht verletzbar — in einer `datetime64`-Spalte kann kein
`31022026` stehen. `src/common/serialisierung.py` ist die einzige Stelle, an der zwischen
beiden gewandelt wird, und `parse(serialisiere(x)) == x` ist als Test festgehalten.

**Der Parser wirft keine Ausnahme.** Ein nicht parsebarer Wert wird zu `pd.NA` und die
Stelle wird in `parse_fehler` protokolliert. Ein `raise` würde später den gesamten
Experimentlauf abbrechen, statt einen Befund zu liefern.

### Getroffene Festlegungen

| Frage | Entscheidung | Begründung |
|---|---|---|
| Rang bei `annahmeentscheidung` = ABLEHNUNG | Die Zeile bleibt **ohne Rang** (`rang` leer) und wird aus der Rangfolge ausgenommen; die übrigen Angebote der Anfrage tragen lückenlos 1..m | Ein abgelehntes Risiko hat keinen Preis und gehört damit in keine Preisrangfolge. R-043 („lückenlos 1..n") bezieht sich auf die bepreisten Angebote |
| Leere Beitragsfelder bei ABLEHNUNG | Leer sind `nettobeitrag_jahr_eur`, `versicherungsteuer_satz`, `versicherungsteuer_eur`, `bruttobeitrag_jahr_eur`, `ratenzahlungszuschlag_prozent`, `zahlbeitrag_rate_eur` und `rang`. Selbstbehalte und Berechnungszeitpunkt bleiben gefüllt | Selbstbehalt und Zeitpunkt sind keine Beitragsfelder; sie beschreiben die angefragte Deckung, nicht ihren Preis |
| Mindestzahl bepreister Angebote | zwei je Anfrage | Sonst gäbe es Anfragen ohne Rangfolge und ohne Spreizung; mehrere Relationsregeln wären dort nicht auswertbar |
| Leeres Datum in der Rohschicht | leerer String, nicht `00000000` | `00000000` ist in diesem Modell ein **Sentinel** und wird von R-025 gemeldet. Wäre es der Leerwert, verlören R-025 und R-009 ihre Schärfe (`spec/01`, Abschnitt 6) |
| Profil der anfrageseitigen Felder | über den Eingangskanal, nicht über die Quellschnittstelle des Angebots | Die Felder werden einmal je Anfrage erfasst und an alle Versicherer verschickt. Die Zuordnung steht jetzt in `spec/01`, Abschnitt 5.1 |

### Was der Generator bewusst nicht tut

Er liest **keine** Schwellenwerte aus `config.schwellen`. Diese Werte werden in der Arbeit
variiert; ein Generator, der an ihnen hängt, würde bei jeder Variation einen anderen
Datensatz erzeugen und die Läufe unvergleichbar machen. Die Einhaltung wird stattdessen im
Test geprüft.

Er **kappt keine Beiträge** an einer Obergrenze und **koppelt die Zahlweise nicht** an die
Beitragshöhe. Beides gab es in einer früheren Fassung, solange R-053 die Rate statt des
Jahresbeitrags prüfte. Eine Kappung verzerrt den oberen Rand der Verteilung, eine Kopplung
erzeugt eine künstliche Abhängigkeit im Datensatz, deren Ursache später niemand mehr kennt.
Liegt ein Beitrag außerhalb des Korridors von R-053, gehört der Schwellenwert angepasst —
er steht in `config.schwellen`, genau dafür. Die Obergrenze für Kfz steht nach der
Kalibrierung des Vollkasko-Randes bei 13.000 €, empirisch bestimmt über fünf unabhängige
Seeds und mit Messwerten begründet in [`docs/iteration_log.md`](docs/iteration_log.md).

Was der Generator dagegen **sehr wohl** abbildet, ist die Annahmepolitik des Marktes: In
Teil- und Vollkasko erhalten Risiken in der Malus- oder Schadenklasse kein Angebot, in der
Haftpflicht bleiben sie erhalten. Das ist eine Annahmebedingung, kein nachträgliches
Filtern — die betroffene Anfrage wird als Haftpflichtanfrage geführt.

## Der Regelkatalog (Phase 3)

58 Regeln, gruppiert nach Prüfgranularität: **G1** Attributwert (R-001–R-025), **G2** Satz
(R-026–R-042), **G3** Relation (R-043–R-048), **G4** relationsübergreifend (R-049–R-051),
**G5** quellenübergreifend (R-052–R-058). Davon 47 `HART` und 11 `WARNUNG`; nach
Erkennbarkeitsgrad 44 × C1, 11 × C2, 3 × C3.

Der Katalog importiert **nichts** aus `src/generator` oder `src/injector`
(Architekturregel A1). Gemeinsame Wertebereiche kommen aus `src/common/wertebereiche.py`.

### Auf welcher Schicht eine Regel arbeitet

Elf Regeln laufen zwingend auf der Rohschicht: R-002 bis R-009, R-013, R-017 und R-025.
Format-, Typ- und Sentinel-Prüfungen sind auf typisierten Daten per Konstruktion nicht
verletzbar — in einer `datetime.date` kann kein 31. Februar stehen. Jede Regel deklariert
ihre Schicht in den Metadaten; `tests/test_katalog.py` hält die Zuordnung fest.

### Zwei Sichten auf die Treffer

| Datei | Inhalt | Zweck |
|---|---|---|
| `detections.parquet` | jede Meldung jeder Regel | Diagnose je Regel |
| `markierte_zellen.parquet` | Vereinigungsmenge der Tripel `(entitaet, row_id, spalte)` | Metrik |

Markieren mehrere Regeln dieselbe Zelle, zählt sie **einmal**. Ein Datums-Sentinel wie
`00000000` löst R-009 und R-025 gleichzeitig aus; ohne Deduplizierung ergäbe ein einziger
injizierter Fehler zwei Treffer und die Precision fiele, ohne dass der Detektor schlechter
wäre.

Aus demselben Grund trägt jede Verstoßzeile eine `verstoss_id`: eine Kennung je erkanntem
Constraint-Verstoß, gemeinsam für alle beteiligten Zellen. R-031 meldet Brutto, Netto und
Steuer; der Injektor verfälscht aber nur eine der drei Zellen. Die Auswertung wertet später
beide Sichten aus — streng zellbasiert und constraint-basiert.

**R-047 und R-048 gehen nicht in die Zellmetrik ein** (`in_zellmetrik = False`). R-047 weiß
nicht, welches der n Angebote das falsche ist; R-048 prüft eine Verteilung über den
Gesamtdatensatz und hat überhaupt keine verursachende Zelle. Beide werden als
Diagnosekennzahl geführt.

### Clean-Baseline-Lauf

**Null Meldungen** auf `df_clean` — 58 Regeln, 0 markierte Zellen von 1.769.095,
False-Positive-Rate 0,0. Gegengeprüft über vier unabhängige Master-Seeds mit zusammen rund
7,06 Millionen Zellen. Der Bericht steht in
[`results/clean_baseline.json`](results/clean_baseline.json), die Auslegungsentscheidungen
und der eine dabei gefundene Regelfehler in
[`docs/iteration_log.md`](docs/iteration_log.md).

Diese Kennzahl ist der Beleg dafür, dass die Grundannahme „alles nicht Injizierte ist
sauber" trägt. Ohne sie wäre jede später berichtete Precision unbelegt.

## Der Fehlerinjektor (Phase 4)

Der Injektor verfälscht die **Rohschicht** `df_raw` kontrolliert und protokolliert jede
einzelne Verfälschung. Sechzig Injektionsvarianten über acht Fehlerklassen und zwei
Held-out-Klassen (`spec/03_fehlerklassen.md`, Abschnitt 2).

Er importiert **nichts** aus `src/rules` und nichts aus `src/generator`. Er kennt weder die
Regeln noch ihre Konstanten noch ihre Hilfsfunktionen und verwendet keine Regel-IDs in seiner
Logik. Die Varianten bilden **empirische Fehlerursachen** ab — Erfassungsfehler,
Schnittstellenkonvertierung, Legacy-Migration, Freitexteingabe —, nicht die Komplemente der
Prüfbedingungen. Die Zuordnung Variante → Regel entsteht erst in der Auswertung.

Diese Trennung ist der Kern der methodischen Absicherung gegen den Zirkularitätsvorwurf und
wird am Importgraphen belegt (`tests/test_architecture.py`, einschließlich einer
Negativkontrolle, die dem Prüfmechanismus eine verbotene Kante vorlegt).

### Die Bezugsgröße der Fehlerrate — sie ändert jede Ergebnistabelle

> Die Fehlerrate ist der Anteil verfälschter Zellen am **klassenspezifischen adressierbaren
> Zelluniversum** — also an der Menge aller Zellen, die von mindestens einer Variante dieser
> Fehlerklasse überhaupt getroffen werden können.

Der Grund ist rechnerisch zwingend: Jede Klasse adressiert nur einen Teil des Datensatzes.
Bezöge man die Rate auf alle befüllten Zellen, wären die oberen Ratenstufen für die meisten
Klassen unerreichbar. Gemessen bei 10.000 Anfragen:

| Klasse | Universum | Einheit | injiziert bei 2 % |
|---|---|---|---|
| F1 Fehlender Wert | 1.137.175 | Zellen | 22.744 |
| F2 Format und Syntax | 111.731 | Zellen | 2.235 |
| F3 Wertebereich und Katalog | 57.376 | Zellen | 1.148 |
| F4 Fachlich unmöglich | 84.055 | Zellen | 1.681 |
| F5 Intra-Record-Inkonsistenz | 232.660 | Zellen | 4.653 |
| F6 Duplikate | 73.398 | **Sätze** | 1.468 |
| F7 Aktualität | 120.895 | Zellen | 2.418 |
| F8 Einheiten | 268.034 | Zellen | 5.362 |
| HO1 Semantische Duplikate | 12.400 | **Sätze** | 248 |
| HO2 Semantisch falsch | 268.564 | Zellen | 5.374 |

**„2 Prozent Fehlerrate" bedeutet je Klasse eine andere absolute Fehlerzahl** — hier zwischen
248 und 22.744, also um den Faktor 90 auseinander. Verlangt die angeforderte Rate mehr
Einheiten, als das Universum hergibt, bricht der Injektor mit klarer Meldung ab; er füllt
**nicht** stillschweigend weniger auf.

Bei F6 und HO1 ist die Bezugseinheit die **duplizierbare Zeile**, nicht die Zelle: Beide
Klassen fügen Zeilen hinzu und haben keine Zielzelle. Das `manifest.json` weist die Einheit je
Klasse aus.

### Zwei Ebenen des Ground Truth

| Datei | Inhalt |
|---|---|
| `error_log.parquet` | eine Zeile je verfälschter Zelle |
| `error_log_records.parquet` | eine Zeile je satzbezogenem Fehler (F6, F7-c, HO1) |

Eine hinzugefügte Duplikatzeile hat keinen sauberen Vorgängerwert, und `df_dirty` hat dann
mehr Zeilen als `df_clean` — ein zellweises Diff ist dort undefiniert. Ohne die zweite Ebene
bräche die Auswertung genau bei der Fehlerklasse, die laut Branchenempirie die häufigste ist.

Das zellbasierte Log trägt eine Spalte `mitgezogen`. Sie trennt **Trägerzellen** vom Rang, der
bei den Skalierungsvarianten nur der Satzstimmigkeit wegen nachgeführt wird. Eine mitgezogene
Zelle ist nach der Skalierung richtig, nicht falsch; sie als injizierten Fehler zu zählen
ergäbe ein garantiertes False Negative. Sie muss trotzdem im Log stehen, sonst fände der
Gegencheck eine Abweichung ohne Protokolleintrag. Nur die Trägerzellen gehen in die
Fehlerrate ein.

### Der unabhängige Gegencheck

`src/verify/diff_check.py` berechnet ein zellweises Diff zwischen `df_clean` und `df_dirty`
über `row_id` und gleicht es gegen beide Logs ab. Das Modul liegt bewusst **außerhalb** von
`src/injector` und teilt keinen Code mit ihm — ein Gegencheck, der die Logik des Geprüften
teilt, bestätigt nur, dass diese Logik mit sich selbst übereinstimmt. Der Architekturtest
prüft die Kante am Importgraphen.

Ergebnis über alle zehn Klassen und den Mischmodus bei 10.000 Anfragen: **keine Abweichung**.
Der Bericht steht in [`results/ground_truth_check.json`](results/ground_truth_check.json) und
gehört in den Anhang der Arbeit.

### Was der Injektor bewusst nicht erkennbar macht

Vier Varianten sollen **nicht** gefunden werden. Sie sind die Kontrollbedingung des
Experiments:

| Variante | Warum sie unentdeckt bleibt |
|---|---|
| F5-e | Bruttobeitrag um 0,01 € gesenkt — innerhalb der Toleranz von R-031. Prüft, ob die Toleranzgrenze korrekt implementiert ist |
| F7-d | Tarifgeneration zurückgesetzt, Gültigkeitszeitraum unverändert — das Feld `tarifgeneration` wird nicht regelgeprüft |
| F8-e | **Alle** Angebote einer Anfrage durch 12 geteilt. R-054 prüft relational gegen den Median der übrigen Angebote, und der wandert mit |
| HO1, HO2 | Semantische Duplikate und semantisch falsche, formal gültige Werte — dafür bräuchte es ein Ähnlichkeitsmaß beziehungsweise die wahre Ausprägung |

F8-e zeigt die strukturelle Grenze relationaler Plausibilitätsprüfungen und gehört
ausdrücklich in die Diskussion der Arbeit.

## Freeze des Regelkatalogs

Der Regelkatalog wurde **vor** dem Fehlerinjektor entwickelt und anschließend eingefroren.
Der Commit-Hash dieses Tags belegt, dass die Validierungsregeln nicht nachträglich auf die
injizierten Fehler zugeschnitten wurden. **Ohne diesen Beleg ist die Behauptung nicht
überprüfbar** — er gehört deshalb in den Anhang der Arbeit.

| Angabe | Wert |
|---|---|
| Tag | `freeze-regelkatalog` |
| **Commit-Hash** | **`30ca5ea429a0abddec7050af1d1a42cdf9942548`** |
| Tag-Objekt | `3f64827ce95801aec6df29d0d18232404c4af206` |
| Datum | 2026-08-06 |
| Regeln im Katalog | 58 (25 / 17 / 6 / 3 / 7 über G1 bis G5; 47 HART, 11 WARNUNG) |
| Clean-Baseline-Lauf | **null Verstöße** bei 1.769.095 geprüften Zellen |
| Regeltestfälle | 163 (81 positiv, 82 negativ), Testsuite gesamt 593 |

Zu zitieren ist der **Commit-Hash**. `git rev-parse freeze-regelkatalog` liefert bei einem
annotierten Tag die Hülle des Tag-Objekts, nicht den Codestand; den Commit liefert
`git rev-parse freeze-regelkatalog^{commit}`.

```bash
git show freeze-regelkatalog
```

Maschinenlesbar in [`results/freeze.json`](results/freeze.json) — die Datei wandert ins
Reproduzierbarkeitspaket.

### Was der Freeze umfasst

**Eingefroren sind die Regeln selbst:** Prädikate, Wertebereiche, Schwellenwerte,
Geltungsbereiche, Schweregrade und die Zuordnung zu den Achsen A, B und C. Jede Änderung
daran ist ab jetzt eine **Iteration 2** und wird in
[`docs/iteration_log.md`](docs/iteration_log.md) mit eigener Ergebnistabelle berichtet.

**Nicht eingefroren sind die Belege daneben:** die Spalten „Literatur" und „Fachliche
Grundlage" im Katalog sowie Formulierungen in `spec/`. Sie dokumentieren die Herleitung und
dürfen jederzeit korrigiert werden, solange sich das geprüfte Prädikat nicht ändert. Der
Freeze belegt, dass die Regeln vor dem Injektor feststanden — nicht, dass jede Fußnote von
Anfang an richtig war.

- **Tag:** `freeze-regelkatalog`
- **Commit-Hash:** _(nach Phase 3 eintragen)_
- **Datum:** _(nach Phase 3 eintragen)_

Der Regelkatalog wird vor dem Fehlerinjektor entwickelt und anschließend eingefroren. Der
Commit-Hash dieses Tags belegt, dass die Validierungsregeln nicht nachträglich auf die
injizierten Fehler zugeschnitten wurden. Notwendige Korrekturen nach dem Freeze werden als
Iteration 2 in `docs/iteration_log.md` dokumentiert, niemals stillschweigend vorgenommen.

## Struktur

```
config/     Stichtag, Pfade, Faktorstufen, Master-Seed
spec/       Fachliche Spezifikation — Quelle der Wahrheit
scripts/    Ausführbare Einstiegspunkte je Phase
src/        common, generator, rules, injector, verify, baselines, evaluation
data/       reference (versioniert), runs (nicht versioniert)
tests/      Architektur-, Reproduzierbarkeits-, Regel- und Ground-Truth-Tests
docs/       Iterationslog und Verteilungsquellen
results/    Tabellen und Abbildungen für die Arbeit
```

Die Trennung von Generator, Injektor und Regel-Engine ist unverhandelbar und wird in
`tests/test_architecture.py` am Importgraphen geprüft. Die Begründung steht in `CLAUDE.md`,
Abschnitt 2.

### `src/common/` — die gemeinsamen Bausteine

Das einzige Paket, aus dem Generator, Regel-Engine, Injektor und Gegencheck importieren
dürfen.

| Modul | Inhalt |
|---|---|
| `config.py` | Lädt `config/default.yaml` in die eingefrorene Dataclass `Config`. Einzige Stelle, die YAML liest. Fehlende **und** unbekannte Schlüssel brechen ab. |
| `seeding.py` | Hierarchisches Seeding, `numpy`-Generator, geseedete Faker-Instanz. Einzige Stelle, an der ein Zufallsgenerator entsteht. |
| `enums.py` | Enums und Schlüsselkataloge aus `spec/01`, Abschnitt 3. |
| `wertebereiche.py` | Numerische Grenzen, Steuersätze, PflVG-Mindestdeckungen, Sentinel-Werte. |
| `geld.py` | `Decimal`-Arithmetik mit `ROUND_HALF_UP`. Weist `float` ausdrücklich zurück. |
| `iban.py` | Prüfziffern nach ISO 7064 Mod 97-10 — von Generator und Regel-Engine gemeinsam genutzt. |
| `referenz.py` | Lädt die Referenztabellen mit festen Spaltentypen und Zwischenspeicher. |
| `pflichtfelder.py` | Pflichtfeldprofil je Quellschnittstelle und Zuordnung Kanal → Profil (`spec/01`, Abschnitt 5). |
| `serialisierung.py` | Schema beider Datenschichten, `serialisiere` und `parse`. Der Parser wirft keine Ausnahme. |
| `datum.py` | Kalenderarithmetik über ganze Jahre — von Generator und Regel-Engine gemeinsam genutzt. |
| `pfade.py` | Laufverzeichnisse, Artefaktnamen, SHA-256-Hashwerte. |

### `src/rules/` — der Regelkatalog

| Modul | Inhalt |
|---|---|
| `modell.py` | `Regel`, `Kontext` über beide Schichten, `Befund` mit Zell- und Satzkanal, `Befundsammler` (vergibt die `verstoss_id`). |
| `katalog.py` | Registry der 58 Regeln. Prüft Vollständigkeit, Eindeutigkeit und Gruppenzuordnung **beim Import**. |
| `g1_attribut.py` … `g5_quellen.py` | Die Regeln je Granularitätsgruppe samt ihrer Metadaten. |
| `engine.py` | Ausführung, Deduplizierung, Laufzeitmessung, Artefakte. |

Die reinen Spaltenprüfungen der Gruppe G1 laufen über **pandera** mit `lazy=True`, damit
alle Verstöße einer Spalte gesammelt statt beim ersten abgebrochen werden. Für G2 bis G5
sind es eigene Prüffunktionen — dafür ist pandera nicht gedacht.

### `src/injector/` — der Fehlerinjektor

| Modul | Inhalt |
|---|---|
| `modell.py` | `Fehlerklasse`, `Variante`, `Aenderung`, `Injektionskontext`, Log-Schemata. Weist typisierte Daten zurück, statt still zu konvertieren |
| `rohwerte.py` | Lesen und Schreiben einzelner Werte der Rohschicht (`TTMMJJJJ`, ISO 8601, `Decimal`) |
| `varianten/` | Die 60 Varianten je Fehlerklasse; `__init__` prüft die Zusammenstellung **beim Import** |
| `auswahl.py` | Adressierbares Zelluniversum je Klasse, Kontingente je Variante, Mischung der Kandidaten |
| `protokoll.py` | Aufbau von `error_log` und `error_log_records` |
| `pipeline.py` | Orchestrierung; öffentlicher Einstiegspunkt `injiziere` |

Das Kontingent einer Klasse wird **gleichmäßig auf ihre Varianten** verteilt, damit der
Recall je Variante aussagekräftig bleibt: Zöge man die Zellen einfach aus dem
Klassenuniversum, bekämen Varianten mit kleiner Kandidatenmenge — etwa F2-a, das eine
führende Null voraussetzt — zu wenige Treffer. Kann eine Variante ihr Kontingent nicht
füllen, geht der Rest an die übrigen Varianten derselben Klasse.

### `src/verify/` — der unabhängige Gegencheck

| Modul | Inhalt |
|---|---|
| `diff_check.py` | Zellweises Diff `df_clean` gegen `df_dirty` über `row_id`, abgeglichen gegen beide Ground-Truth-Logs |

Importiert **nichts** aus `src/injector` und kennt weder die Variantendefinitionen noch die
Log-Schemakonstanten des Injektors. Die Spaltennamen, gegen die es prüft, stammen aus
`spec/03`, nicht aus dem Quelltext des Injektors.

### Referenzdaten

Sieben Tabellen unter `data/reference/`, einmalig deterministisch erzeugt und versioniert:
`plz_ort.csv` (8.000 PLZ, 400 Zulassungsbezirke), `regionalklassen.csv`, `typklassen.csv`
(3.000 HSN/TSN-Kombinationen), `vu_stammdaten.csv` (14 Anbieter), `zuers_zonen.csv`,
`sf_beitragssatz.csv` und `waehrungen.csv` (ISO-4217-Katalog, 178 Einträge).

Bis auf `waehrungen.csv` sind sämtliche Daten synthetisch — der Währungskatalog ist ein
offizieller Standard und wird über das Paket `pycountry` bezogen, nicht von Hand gepflegt.
Welche Verteilung woher stammt und welche Annahme wo getroffen wurde, steht in
[`docs/verteilungsquellen.md`](docs/verteilungsquellen.md) — einschließlich der Begründung,
warum der Bezug echter PLZ-Daten über die OpenPLZ API geprüft und verworfen wurde.

## Lizenz

Bewusst keine Lizenzdatei. Bei einer Abschlussarbeit hängt die Lizenzfrage von der
Hochschulordnung ab.
