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
| 4 | `df_raw_dirty` + Ground Truth + unabhängiger Gegencheck | folgt in Phase 4 |
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

## Freeze des Regelkatalogs

*Der Tag wird nach Abnahme dieser Phase gesetzt.*

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
