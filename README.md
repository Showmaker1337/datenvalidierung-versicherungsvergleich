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
| 5 | Metriken auf vier Ebenen sowie die Baselines B0, B2 und B3 | `python scripts/evaluate.py --serie s01 --design A --klasse F3 --rate 0.02 --wdh 7` (abgeschlossen) |
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
python scripts/inject.py --serie v01 --design A --modus variante --variante F7-c --wdh 0
```

Der Teilversuch **Variantencharakterisierung**: Injiziert wird genau eine Variante, und zwar
bis an ihr Universum heran. Die Fehlerrate bezieht sich dann auf das Universum dieser
Variante und ist standardmäßig 1,0; `--max-fehler ZAHL` begrenzt die Zahl nach oben. Der Lauf
landet unter der Variantenkennung statt unter der Klasse, also
`data/runs/v01/A/F7-c/r10000/w00/`.

Diese Läufe gehören **nicht** in den faktoriellen Versuchsplan — siehe „Zuteilung auf die
Varianten" weiter unten.

```bash
python scripts/evaluate.py --serie s01 --design A --klasse F3 --rate 0.02 --wdh 7
```

Bewertet Prototyp und die drei Vergleichsverfahren auf einem bereits verfälschten Lauf. Der
Aufruf trägt **dieselben Faktorstufen** wie der zugehörige `inject.py`-Aufruf; daraus findet
er das Laufverzeichnis und liest `manifest.json`, `error_log.parquet` und
`error_log_records.parquet`.

Der verfälschte Datensatz wird dabei **neu erzeugt** statt geladen — er wird bewusst nicht
dauerhaft gespeichert und ist aus `seed_basis` und `seed_inject` exakt reproduzierbar. Als
Nebenprodukt entsteht ein **Reproduzierbarkeitsnachweis**: Die SHA-256-Werte von `df_clean`
und `df_dirty` werden gegen `manifest.json` geprüft, und eine Abweichung bricht den Lauf ab.
Damit belegt jeder Auswertungslauf Architekturregel A2 für sich selbst.

Geschrieben werden nach `data/runs/<serie>/<design>/<klasse>/<rate>/<wdh>/` die Datei
`metrics.json` und je Verfahren `detections_<verfahren>.parquet`, dazu fortgeschrieben
`results/metrics_long.parquet` und `results/b3_framework.json`.

Optionen: `--config DATEI`, `--modus variante --variante F7-c`, `--verfahren prototyp B0 B2 B3`
(Auswahl), `--clean-run ID`, `--seed ZAHL`, `--n-anfragen ZAHL`, `--kein-speicher`, `--still`.
`--kein-speicher` schaltet `tracemalloc` ab; die Speichermessung verlangsamt den Lauf spürbar
und wird in Phase 6 nicht für jeden der tausenden Läufe gebraucht.

```bash
python scripts/framework_vergleich.py
```

Stellt cuallee und Great Expectations auf denselben sieben G1-Regeln nebeneinander und
schreibt `results/framework_vergleich.json`. **Keine dritte Baseline** — der Gegenschnitt
tritt in keiner Konfusionsmatrix an und geht nicht in die Inferenzstatistik ein; er liefert
die zweite Spalte der Frameworkvergleichstabelle. Vor dem Vergleich wird eine Fehlerklasse
injiziert (Standard `F2`), weil sich die Kennzahl Diagnosegüte nur an einem echten Fund
zeigen lässt. Optionen: `--config DATEI`, `--n-anfragen ZAHL`, `--klasse KLASSE` (`keine`
lässt den Datensatz sauber), `--rate ANTEIL`, `--ziel VERZEICHNIS`, `--still`.

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
| F5 Intra-Record-Inkonsistenz | 232.660 | Zellen | 4.652 |
| F6 Duplikate | 73.398 | **Sätze** | 1.468 |
| F7 Aktualität | 120.895 | Zellen | 2.418 |
| F8 Einheiten | 268.034 | Zellen | 5.336 |
| HO1 Semantische Duplikate | 12.400 | **Sätze** | 248 |
| HO2 Semantisch falsch | 268.564 | Zellen | 5.368 |

**„2 Prozent Fehlerrate" bedeutet je Klasse eine andere absolute Fehlerzahl** — hier zwischen
248 und 22.744, also um den Faktor 90 auseinander. Verlangt die angeforderte Rate mehr
Einheiten, als das Universum hergibt, bricht der Injektor mit klarer Meldung ab; er füllt
**nicht** stillschweigend weniger auf.

Bei F6 und HO1 ist die Bezugseinheit die **duplizierbare Zeile**, nicht die Zelle: Beide
Klassen fügen Zeilen hinzu und haben keine Zielzelle. Das `manifest.json` weist die Einheit je
Klasse aus.

### Geänderte Zellen sind nicht gleich fehlerhafte Zellen

Bei den Skalierungsklassen wird die Preisrangfolge mitgezogen (siehe unten). Diese Rangzellen
sind gegenüber den verfälschten Daten **korrekt** — sie tragen den richtigen Rang zum
verfälschten Beitrag — und zählen deshalb nicht als Fehler. Verändert ist der Datensatz an
ihnen trotzdem. Das `manifest.json` führt beide Zahlen getrennt:

| Feld | Bedeutung | F3 bei 2 % | F8 bei 2 % | HO2 bei 2 % |
|---|---|---|---|---|
| `zellen_fehlerhaft` | Trägerzellen — **darauf** bezieht sich die Fehlerrate | 1.148 | 5.336 | 5.368 |
| `mitgezogene_zellen` | nachgeführte Rangzellen, keine Fehler | 0 | 3.651 | 2.228 |
| `zellen_geaendert_gesamt` | alle veränderten Zellen | 1.148 | 8.987 | 7.596 |

**„Zwei Prozent" bedeutet für F8 also nicht nur wegen des klassenspezifischen Universums
etwas anderes als für F3, sondern zusätzlich, weil der Datensatz dort an zwei Dritteln mehr
Stellen verändert ist, als die Fehlerrate nominell angibt.** Für die Metrik zählt die erste
Zahl, für die Beschreibung des verfälschten Datensatzes die dritte.

### Zuteilung auf die Varianten — proportional, nicht gleichmäßig

Das Kontingent einer Klasse wird proportional zum adressierbaren Universum **jeder Variante**
zugeteilt. Eine gleichmäßige Zuteilung sähe fairer aus, erzeugte aber einen Confounder:
Varianten mit kleinem Universum — F4-f, F7-c und F7-d wirken auf der Entität `tarif` mit nur
231 Zeilen — stoßen mit steigender Fehlerrate an ihre Decke, ihr Rest ginge an die reichlich
vorhandenen Varianten, und **die Zusammensetzung der Klasse verschöbe sich mit der
Fehlerrate**. Die Fehlerrate ist aber Faktor UV2; ein Trendtest über die Ratenstufen könnte
Ratenwirkung und Mischungsverschiebung dann nicht trennen.

Bei proportionaler Zuteilung ist der Variantenanteil über alle sechs Ratenstufen konstant.
Umverteilt wird **nichts**; erreicht eine Variante ihr Kontingent nicht, bricht der Injektor
ab. Das `manifest.json` weist je Variante Universum, Anteil, angefordert und injiziert aus.

Der Preis: Knappe Varianten bekommen im faktoriellen Plan kleine Fallzahlen, bei kleiner Rate
auch einmal null. Dafür gibt es den zweiten Laufmodus:

```bash
python scripts/inject.py --serie v01 --design A --modus variante --variante F7-c --wdh 0
```

Er injiziert nur diese eine Variante und schöpft ihr Universum aus — 231 Injektionen statt
der fünf, die der faktorielle Plan ihr bei zwei Prozent gibt. Diese Läufe bilden den
Teilversuch **Variantencharakterisierung** und gehören nicht in den faktoriellen Plan. Damit
hat jede Frage ihren eigenen sauberen Lauf: die Klassenwirkung über Ratenstufen den
faktoriellen Plan mit konstanter Mischung, die Variantenwirkung den erschöpfenden Einzellauf.

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

## Auswertung und Vergleichsverfahren (Phase 5)

Der Evaluator misst die Erkennungsleistung gegen den bekannten Ground Truth und behandelt
den Prototyp und die drei Baselines über **dasselbe Protokoll**: `erkenne(kontext)` gibt
Meldungen im Format von `detections.parquet` zurück. Der Evaluator kennt nur dieses
Protokoll und keine Verfahrensdetails.

### Vier Auswertungsebenen

| Ebene | Einheit | Rolle |
|---|---|---|
| **Zellebene** | `(entitaet, row_id, spalte)` | **Primärmetrik**, micro-averaged; dazu Recall je Fehlerklasse und je Injektionsvariante |
| **Constraint-Ebene** | `verstoss_id` | Zweite Hauptsicht; ein mehrspaltiger Verstoß zählt als **ein** Treffer statt als 1 TP plus k FP |
| Satzebene | `(entitaet, row_id)` | Sekundärmetrik; die **einzige** Ebene, auf der F6 und HO1 auswertbar sind |
| Regelebene | `regel_id` | Diagnostisch: Trefferzahl, Precision je Regel, Anteil „einzige treffende Regel" |

**Auf der Constraint-Ebene wechselt nur die Precision die Einheit.** Der Recall bleibt
zellbasiert und ist zahlengleich mit dem der Zellebene — die Frage lautet, ob jeder
injizierte Fehler gefunden wurde, und ein Verstoß, der eine injizierte Zelle überdeckt, hat
sie gefunden. Die Konfusionsmatrix führt dafür ein eigenes Feld `tp_recall`; würde der Recall
aus der Verstoßzahl gebildet, wäre er in beide Richtungen falsch (`docs/iteration_log.md`,
Phase 5, Befund 1).

> **Constraint-Ebene und Zellebene haben denselben Recall, und das ist korrekt — per
> Konstruktion.** Zähler wie Nenner sind in beiden Fällen injizierte Zellen; nur die
> Precision unterscheidet sich, weil dort Verstöße statt Zellen im Nenner stehen. Ohne
> diesen Satz liest sich die Gleichheit in der Ergebnistabelle wie ein Kopierfehler, und die
> Constraint-Ebene wirkt überflüssig — dabei ist sie genau für die Precision eingeführt
> worden.

### Was immer geloggt wird

Die **Rohwerte** TP, FP, FN und TN — nicht nur die abgeleiteten Kennzahlen, damit sich jede
Metrik später neu berechnen lässt, ohne die Läufe zu wiederholen. Dazu `fpr_clean` (die
Fehlalarmrate auf den **nicht** verfälschten Zellen — praktisch die wichtigste Kennzahl, weil
ein Validator mit hoher FP-Rate im Betrieb unbrauchbar ist), Laufzeit und Speicher normiert
auf 1.000 Zeilen, die Kreuztabelle `regel_id` × `fehlerklasse` und der Recall je
`injektor_variante_id` — **immer mit `n` und Clopper-Pearson-Intervall**.

**Accuracy wird nirgends ausgewiesen.** Bei einem Prozent Fehlern erreicht „markiere nichts"
99 Prozent. Stattdessen steht **MCC** neben F1. **PR-AUC nur für B2**: Eine
Precision-Recall-Kurve braucht einen kontinuierlichen Score, und nur
`IsolationForest.decision_function` hat einen. Prototyp, B0 und B3 liefern binäre
Entscheidungen, also genau einen Betriebspunkt — ein Pseudo-Score wird nicht erfunden.

**Eine Asymmetrie, die in die Arbeit gehört:** Ausgewiesen werden **Recall je Fehlerklasse
und je Variante**, aber **Precision nur global und je Regel**. Ein False Positive hat keine
Fehlerklasse — dort ist gar kein Fehler. Eine klassenweise Precision ist deshalb nicht
definierbar, nicht bloß nicht berechnet.

### Mitgezogene Zellen: ein Schalter, keine stille Festlegung

Der Injektor markiert im `error_log` mit `mitgezogen`, welche Zellen nur zur Wahrung der
Kohärenz nachgeführt wurden — die Rangzellen bei der Skalierung des Beitragstupels. Sie sind
gegenüber den verfälschten Daten **korrekt**; ein Verfahren, das sie nicht meldet, macht
keinen Fehler.

Genau deshalb ist die Entscheidung ein Parameter `mitgezogen_als_fehler` und keine
Festlegung im Code: Sie hebt den Recall von F8 und HO2 spürbar. Je Lauf werden **beide**
Varianten berechnet und in `metrics.json` und `results/metrics_long.parquet` geführt. In die
Arbeit gehört die Hauptauswertung mit `False` und die Gegenrechnung als Sensitivitätszeile im
Anhang. Zwei Zahlen nebeneinander beenden die Diskussion, eine Zahl allein eröffnet sie.

### Zell- und variantengewichteter Klassenrecall

Je Klasse werden **beide** Zahlen berichtet. Die zellgewichtete beantwortet „wenn Fehler
dieser Klasse gleichverteilt über alle adressierbaren Zellen auftreten, wie viel findet der
Katalog?", die variantengewichtete „wie viele der Fehlerbilder dieser Klasse findet der
Katalog, unabhängig davon, wie häufig sie sind?". Beide Fragen sind legitim, sie haben nur
verschiedene Antworten — und die Differenz ist selbst ein Ergebnis.

Nötig ist das, weil die proportionale Zuteilung die Klassen intern sehr ungleich macht: F4
besteht zu 73,5 Prozent aus F4-g, HO2 zu 90,7 Prozent aus HO2-b. Ohne die
variantengewichtete Gegenzahl liest sich der hohe Klassenrecall von F4 und der niedrige von
HO2 wie ein inhaltlicher Befund, obwohl beides eine Eigenschaft der Gewichtung ist. Die
belastbare variantengewichtete Zahl stammt aus den Läufen mit `--modus variante`, wo jede
Variante ihr volles `n` hat.

### Die drei Vergleichsverfahren

| | Verfahren | Was es misst |
|---|---|---|
| **B0** | pydantic v2, reine Schemavalidierung | Die **untere Schranke**: Was fangen Datentypen, Nullable-Constraints und Feldlängen allein? |
| **B2** | scikit-learn `IsolationForest` | Was fängt ein unüberwachtes Anomalieverfahren ohne jedes Domänenwissen? |
| **B3** | dieselben G1-Regelinhalte in cuallee | **Nicht** die Erkennungsqualität — die ist für abgedeckte Regeln per Konstruktion identisch —, sondern Ausdrückbarkeit, Aufwand, Laufzeit und Diagnosegüte |

**B2 wird bewusst optimistisch eingestellt:** `contamination` wird über
`[0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2]` gesweept und die **beste erreichte F1**
berichtet. Der Wald wird dabei **einmal** gefittet und `score_samples` **einmal** gerufen;
`contamination` beeinflusst bei `IsolationForest` nur den Entscheidungs-Offset, nicht das
Modell. Ein Neufitten je Stufe kostete das Siebenfache ohne jeden Nutzen — bei mehreren
tausend Läufen der Unterschied zwischen Stunden und Tagen. `contamination` wird ausdrücklich
**nicht** auf die wahre Fehlerrate gesetzt; das wäre unfair und angreifbar.

**B2 arbeitet auf Zeilenebene.** Für die Zellmetrik markiert eine als anomal erkannte Zeile
alle ihre befüllten Zellen. Diese Umrechnung benachteiligt B2 bei der Precision und begünstigt
es beim Recall; für B2 ist deshalb die **Satzebene** der Primärvergleich und die Zellebene die
Zusatzangabe.

### B3 — die vier Kennzahlen

| Kennzahl | Ergebnis |
|---|---|
| **Anteil ausdrückbarer Regeln** | **21 von 25** G1-Regeln (84 %), bezogen auf den ganzen Katalog **36,2 %** (21 von 58) |
| Nicht ausdrückbar | R-004 (IBAN-Prüfziffer ISO 7064) und R-009 (existierender Kalendertag) |
| Nur teilweise | R-001 (der bedingte Teil ist eine CFD) und R-025 (die Feldausnahmen der Sentinel-Prüfung) |
| Codezeilen je Regel | 46 gegen 326 über 23 Regeln (Faktor 7,1); über die 21 **vollständig** ausdrückbaren 40 gegen 266 (Faktor 6,7) |
| Laufzeit | rund 10 s gegen 47 s des vollständigen Prototyps (58 Regeln statt 25) |
| Diagnosegüte (cuallee) | Spalte **ja**, Regel **ja**, Zahl der Verstöße **ja** — **Zeile nein, Ausgangswert nein** |

#### Die tragende Zahl ist die Ausdrückbarkeit

**36,2 Prozent des Katalogs sind in cuallee abbildbar, 63,8 Prozent nicht.** Das ist die
Antwort auf „Warum ein eigener Prototyp?", und sie hängt an der **Form der Regeln** und nicht
am Berichtsformat eines Werkzeugs. Vier Regelformen sprengen eine spaltenweise Check-API:

- **bedingte Regeln** in CFD-Form — R-001 macht die Pflicht eines Feldes vom Wert eines
  anderen Feldes derselben Zeile abhängig;
- **relationale Regeln** über mehrere Zeilen einer Tabelle — R-044 (Sortierung), R-052
  (Mehrheitsentscheid je Anfrage), R-054 (Median der übrigen Angebote);
- **satz- und quellenübergreifende Regeln**, die zwei Tabellen zugleich brauchen;
- **algorithmische Regeln** — R-004 (Prüfziffer nach ISO 7064) und R-009 (realer
  Kalendertag). Ein Muster erkennt acht Ziffern, aber nicht den 31. Februar.

#### Wie weit die Zahl trägt — der Gegenschnitt mit Great Expectations

Die 36,2 Prozent sind **für cuallee gemessen**, und der Gegenschnitt zeigt, dass sie nicht
frameworkunabhängig sind. Sieben G1-Regeln wurden zusätzlich in Great Expectations
formuliert (`python scripts/framework_vergleich.py`):

| Regel | cuallee | Great Expectations | Codezeilen cuallee / GE |
|---|---|---|---|
| R-001 (bedingt) | teilweise | **ja** | 3 / 13 |
| R-002 (Muster) | ja | ja | 1 / 1 |
| R-004 (Prüfziffer) | **nein** | **nein** | — / — |
| R-009 (Kalendertag) | **nein** | **ja** | — / 8 |
| R-010 (Katalog) | ja | ja | 2 / 2 |
| R-014 (Bereich) | ja | ja | 3 / 11 |
| R-021 (Untergrenze) | ja | ja | 4 / 4 |
| **Summe** | **4 von 7 (57 %)** | **6 von 7 (86 %)** | |

Zwei benennbare Fähigkeiten erklären den Unterschied: `row_condition` macht eine Erwartung
vom Wert eines anderen Feldes derselben Zeile abhängig (deckt R-001 vollständig ab), und
`ExpectColumnValuesToMatchStrftimeFormat` parst den Wert wirklich, statt ihn gegen ein Muster
zu halten (deckt R-009 ab). **Beide scheitern an R-004** — eine Prüfziffer ist ein
Algorithmus, kein Prädikat über einen Spaltenwert.

Frameworkübergreifend belastbar ist deshalb nicht die eine Zahl, sondern der **Kern** der
Grenze: die relationalen Regeln (R-043 bis R-048, R-052, R-054), die quellenübergreifenden
(R-049 bis R-051, R-055 bis R-058) und die algorithmischen (R-004). Allein die Gruppen G3
bis G5 umfassen 16 der 58 Regeln, und sie bleiben beiden Frameworks verschlossen.

Nebenbefund: Great Expectations drückt mehr aus, kostet dafür aber mehr Quelltext —
Ausdrucksmächtigkeit und Knappheit gehen auseinander.

#### Nachgeordnet: die Diagnosegüte — und zwar als Eigenschaft von cuallee

`cuallee.pandas_validation.summary` gibt je Regel einen Wahrheitswert oder eine Zahl zurück,
niemals eine Zeilenkennung. B3 kann deshalb keine zellbasierte Konfusionsmatrix erzeugen:
Seine Meldungen tragen `row_id = -1`, das Verfahren trägt `lokalisiert_zellen = False`, und
der Evaluator schreibt für alle Ebenen `null` **mit Begründung** statt Nullen — eine Null
läse sich wie „hat nichts gefunden".

**Dieser Befund gilt für cuallee und nicht für die Kategorie.** cuallee berichtet auf
Constraint-Ebene; ein Zeilen- und Wertbezug ist in seinem Ausgabeformat nicht vorgesehen.
Andere Frameworks entscheiden das anders: **Great Expectations** liefert mit
`result_format: COMPLETE` und konfigurierten `unexpected_index_column_names` genau diesen
Bezug — `unexpected_index_list` gibt je fehlgeschlagener Zeile Zeilenkennung und fehlerhaften
Wert, dazu `unexpected_index_query` als nachvollziehbare Abfrage.

Der Satz „etablierte Frameworks können Fehler nicht auf die Zelle lokalisieren" wäre also
**falsch**. Nachgemessen liefert Great Expectations auf einem F2-verfälschten Datensatz etwa
`{'plz': '4946', 'row_id': '90'}` — Zeile und Ausgangswert. Die Diagnosegüte ist deshalb der
zweite, nachgeordnete Punkt und ein Befund über den **Gestaltungsraum** der Werkzeuge: Ein
Validator, dessen Report die fehlerhafte Zeile nicht benennt, ist im Betrieb nicht
nachbearbeitbar — aber das ist eine Entwurfsentscheidung des jeweiligen Frameworks, keine
Eigenschaft der Gattung.

**B3 gehört nicht in die Inferenzstatistik** — ein Wilcoxon-Test gegen ein Verfahren, das
dieselben Regeln ausführt, testet eine Nullhypothese, von der man weiß, dass sie gilt. Das
Verfahren trägt dafür das Merkmal `in_inferenzstatistik = False`.

### Ein Beispiellauf

Fehlerklasse F3 (Wertebereichs- und Katalogverletzung), zwei Prozent Fehlerrate, 10.000
Anfragen — 1.148 injizierte Zellen in einem Universum von 1.769.095 Zellen und 105.571 Zeilen,
`mitgezogen_als_fehler = False`:

| Verfahren | Ebene | Precision | Recall | F1 | MCC | `fpr_clean` |
|---|---|---|---|---|---|---|
| Prototyp | Zelle | 0,534 | 0,867 | 0,661 | 0,680 | 0,00049 |
| Prototyp | Constraint | **1,000** | 0,867 | 0,929 | — | — |
| Prototyp | Satz | 1,000 | 0,876 | 0,934 | 0,935 | 0,0 |
| B0 | Zelle | 1,000 | 0,133 | 0,235 | 0,365 | 0,0 |
| B2 | Satz | 0,032 | 0,061 | 0,042 | 0,030 | 0,0196 |
| B3 | — | nicht auswertbar (kein Zeilenbezug) | | | | |

Die Zeile, die den Absatz über die Constraint-Ebene trägt: Der Prototyp meldet 1.565
Constraint-Verstöße, von denen **jeder** mindestens eine injizierte Zelle überdeckt — die
Precision ist dort exakt 1,000. Zellbasiert sind es 995 Treffer und 869 Fehlalarme, weil
mehrspaltige Regeln wie R-051 und R-058 alle abgeleiteten Felder melden, der Injektor aber
nur eines verfälscht hat. In diesem Lauf geht damit **jeder einzelne** der 869 scheinbaren
Fehlalarme auf die Berichtskonvention zurück und keiner auf einen Detektionsfehler. Beide
Zahlen stehen nebeneinander, statt dass eine gewählt wird — und die Differenz zwischen 0,534
und 1,000 ist genau der Betrag, den eine rein zellbasierte Berichterstattung dem Verfahren
zu Unrecht anlastet.

Ebenfalls sichtbar: B2 markiert 2.112 Zellen der Spalte `row_id`. Sie sind nach
Architekturregel A3 **niemals** Injektionsziel und damit garantierte Fehlalarme — eine Folge
der Zeile-auf-Zellen-Umrechnung, nicht der Erkennungsleistung. Der Evaluator weist die Zahl
als `markierte_zellen_row_id` getrennt aus.

Die Zahlen stammen aus einem einzelnen Lauf einer einzelnen Fehlerklasse und sind **keine**
Ergebnisse der Arbeit — der Versuchsplan über alle Klassen, Ratenstufen und Wiederholungen
ist Phase 6.

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

**Die Grenze verläuft innerhalb von `config/default.yaml`.** Eingefroren sind dort die
**Regelschwellen** — der gesamte Abschnitt `schwellen`, also alles, was in ein Prädikat
eingeht. Nicht eingefroren sind die **Versuchsparameter**: `master_seed`, `stichtag`,
`n_anfragen`, `sparten_verteilung`, `pfade`, `referenzdaten` sowie die Faktorstufen der
Phase 6 (Fehlerraten, Wiederholungszahl, Varianzdesign).

Die Entscheidungsprobe trägt die Trennung: Eine geänderte Faktorstufe ändert nicht, was die
Regeln auf einem *gegebenen* Datensatz melden — sie erzeugt einen *anderen* Datensatz.
Phase 6 ist deshalb keine Serie von Regeländerungen.

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
src/        common, generator, rules, injector, verify, evaluation, baselines
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

Das Kontingent einer Klasse wird **proportional zum adressierbaren Universum jeder Variante**
verteilt, damit der Anteil jeder Variante über alle Ratenstufen konstant bleibt. Es wird
**nicht** umverteilt: Erreicht eine Variante ihr Kontingent nicht, bricht der Injektor ab.
Beides ist nötig, damit Faktor UV2 (Fehlerrate) interpretierbar bleibt — die Begründung steht
oben unter „Zuteilung auf die Varianten — proportional, nicht gleichmäßig".

### `src/evaluation/` — der Evaluator

| Modul | Inhalt |
|---|---|
| `modell.py` | Protokoll `Verfahren`, die beiden optionalen Zusatzprotokolle, `Konfusion`, `Kennzahlen` und die übrigen Ergebnistypen |
| `ground_truth.py` | Liest beide Ground-Truth-Logs zu Zell- und Satzwahrheit zusammen; prüft dabei Protokollregel 2 und A3 |
| `metriken.py` | Konfusionsmatrizen und Kennzahlen auf allen Ebenen, Clopper-Pearson, PR-AUC, Kreuztabelle, Regeldiagnose |
| `pipeline.py` | Führt die Verfahren aus, misst Laufzeit und Speicher, baut beide Schalterstellungen |
| `langformat.py` | `metrics.json` je Lauf und `results/metrics_long.parquet` über alle Läufe |

Importiert **nichts** aus `src/injector/` und `src/generator/`. Alles, was die Auswertung über
Fehlerklassen und Varianten wissen muss, steht in den beiden Logs und im `manifest.json` des
Laufs — die Zuordnung Variante → Regel entsteht laut `spec/03`, Abschnitt 6 erst hier und darf
nicht aus dem Injektorquelltext stammen.

### `src/baselines/` — die Vergleichsverfahren

| Modul | Inhalt |
|---|---|
| `prototyp.py` | Adapter des eigenen Regelkatalogs auf das Protokoll `Verfahren` |
| `b0_schema.py` | **B0** — pydantic v2, nur Typen, Nullable-Constraints und Feldlängen |
| `b2_isolation_forest.py` | **B2** — scikit-learn `IsolationForest` je Entität, Schwellensweep über sieben Stufen |
| `b3_framework.py` | **B3** — dieselben G1-Regelinhalte in cuallee |
| `b3b_great_expectations.py` | **Gegenschnitt** — sieben derselben Regeln in Great Expectations. Keine Baseline, zweite Spalte der Frameworkvergleichstabelle |
| `codezeilen.py` | Misst „Codezeilen je Regel" über den AST, statt sie zu schätzen |

`b0_schema.py`, `b2_isolation_forest.py` und `b3_framework.py` importieren **nichts** aus
`src/rules/` — ein Blick in den Regelkatalog wäre genau der Zirkelschluss, den die Arbeit
ausschließen will. Nur `prototyp.py` darf ihn kennen. Geprüft wird das am Quelltext in
`tests/test_baselines/test_unabhaengigkeit.py`, mit Negativkontrolle.

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
