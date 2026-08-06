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
| 3 | Regelkatalog implementiert, Clean-Baseline-Lauf ohne Meldungen | folgt in Phase 3 |
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
er steht in `config.schwellen`, genau dafür. Genau das ist geschehen: Die Obergrenze für
Kfz wurde von 6.000 auf 25.000 € angehoben, mit Messwerten begründet in
[`docs/iteration_log.md`](docs/iteration_log.md).

## Freeze des Regelkatalogs

*Wird nach Phase 3 gefüllt.*

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
| `pfade.py` | Laufverzeichnisse, Artefaktnamen, SHA-256-Hashwerte. |

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
