# Phase 3 — Regel-Engine und Clean-Baseline-Lauf

> Voraussetzung: Phase 2 abgeschlossen, Tests grün.
> **Nach dieser Phase folgt der Freeze. Danach wird keine Regel mehr inhaltlich geändert.**
> Kopiere alles ab der Trennlinie in Claude Code.

---

Implementiere den Regelkatalog. Lies vorher `CLAUDE.md` und **`spec/02_regelkatalog.md`
vollständig**. Der Katalog ist verbindlich: Implementiere genau diese 58 Regeln, keine
mehr und keine weniger. Fällt dir eine fehlende Regel auf, melde sie — ergänze sie nicht
eigenmächtig.

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

## Aufgabe 1 — Modul `src/rules/`

```
src/rules/
├── __init__.py
├── modell.py       # Regel-Metadaten und Ergebnistypen
├── katalog.py      # Registry aller Regeln
├── g1_attribut.py  # R-001 – R-025
├── g2_satz.py      # R-026 – R-042
├── g3_relation.py  # R-043 – R-048
├── g4_relationen.py # R-049 – R-051
├── g5_quellen.py   # R-052 – R-058
└── engine.py       # Ausführung, Ergebnisaggregation
```

`src/rules/` importiert **nichts** aus `src/generator/` oder `src/injector/`
(Architekturregel A1). Gemeinsame Wertebereiche kommen aus `src/common/wertebereiche.py`.

## Aufgabe 2 — Datenmodell einer Regel

```python
@dataclass(frozen=True)
class Regel:
    regel_id: str                 # "R-014"
    beschreibung: str             # das Prädikat in einem Satz
    entitaet: str                 # Zieltabelle
    spalten: tuple[str, ...]      # betroffene Spalten (für die Zell-Zuordnung)
    granularitaet: str            # "G1" … "G5"
    fehlerklasse_b: str           # "B1" … "B7"
    erkennbarkeit_c: str          # "C1" … "C4"
    schweregrad: str              # "HART" | "WARNUNG"
    literatur: tuple[str, ...]    # ("RD", "KIM", "DAMA")
    fachliche_grundlage: str      # z. B. "GDV Anlage 14"
    pruefe: Callable[[Kontext], pd.DataFrame]
```

`Kontext` bündelt **beide Datenschichten** (`raw` und `typed`), die Referenztabellen, die
Konfiguration mit den Schwellenwerten und den Stichtag. Regeln über mehrere Tabellen
(R-029, R-049 bis R-051, R-055) brauchen den vollen Kontext.

Jede Regel deklariert in ihren Metadaten das Feld `schicht: "raw" | "typed"`. Welche Regel
auf welcher Schicht arbeitet, steht in `spec/02_regelkatalog.md` im Abschnitt „Auf welcher
Datenschicht eine Regel arbeitet". **Format-, Typ- und Sentinel-Regeln müssen zwingend auf
`raw` laufen** — auf der typisierten Schicht sind sie per Konstruktion nicht verletzbar.

`pruefe` gibt einen DataFrame der **Verstöße** zurück, eine Zeile je verletzter Zelle:

| Spalte | Inhalt |
|---|---|
| `entitaet` | Tabellenname |
| `row_id` | betroffene Zeile |
| `spalte` | betroffenes Feld |
| `regel_id` | |
| `meldung` | menschenlesbar, mit dem konkreten Wert |

Für satzbezogene Regeln (R-043, R-045, R-046, R-048, R-055) zusätzlich ein zweiter
Rückgabekanal mit `betroffene_row_ids: list[int]`, analog zum satzbasierten Ground Truth
aus `spec/03_fehlerklassen.md`, Abschnitt 4.2.

**Mehrspaltige Verstöße — hier steckt eine Metrikfalle.** Verletzt eine Regel eine
Beziehung zwischen mehreren Feldern (etwa R-031 über Brutto, Netto und Steuer), meldet sie
alle beteiligten Spalten. Der Injektor verfälscht aber typischerweise nur **eine** dieser
Zellen. Bei strenger Zellmetrik ergäbe das 1 TP und 2 FP — bei perfekter Erkennung. Die
Precision wäre damit strukturell auf etwa ein Drittel gedeckelt, und zwar als Artefakt der
Berichtskonvention, nicht des Detektors.

Deshalb: Jede Verstoßzeile bekommt zusätzlich eine `verstoss_id` (eine ID je erkanntem
Constraint-Verstoß, gemeinsam für alle beteiligten Zellen). Der Evaluator wertet später
beide Sichten aus — streng zellbasiert und constraint-basiert (ein Verstoß gilt als
Treffer, wenn mindestens eine seiner Zellen im Ground Truth liegt). Die Differenz zwischen
beiden Sichten ist ein eigener Absatz in der Arbeit.

## Aufgabe 3 — Die 58 Regeln implementieren

Setze `spec/02_regelkatalog.md` Zeile für Zeile um. Die Regel-IDs sind fest vergeben und
dürfen nicht verschoben werden.

Fallstricke, die explizit zu beachten sind:

- **R-002 / R-013 / R-017:** PLZ, SF-Klasse und Bauartklasse sind Strings. Prüfe auch den
  **Typ**, nicht nur den Wert — eine als Integer geführte PLZ ist bereits der Fehler.
- **R-009:** Ein achtstelliger Zahlenstring wie `31022026` ist formatgültig, aber kein
  Kalendertag. Prüfe beides getrennt.
- **R-010:** Katalogprüfung, nicht Bereichsprüfung. `zahlweise = 3` liegt im Zahlenbereich
  und ist trotzdem ungültig.
- **R-025:** Prüft auf der Rohschicht. Die Sentinel-Listen je Datentyp und die
  **Ausnahmeliste** (`jahresfahrleistung_km`, Sublimit-Felder — dort ist 9999 ein legitimer
  Wert) kommen aus `common/wertebereiche.py`, nicht als Literale in den Regelcode.
- **R-031 / R-032:** Toleranz exakt ±0,02 €, Vergleich in `Decimal`, nie in float.
- **R-033:** Der Effektivsatz hängt von der Sparte ab — das ist die Conditional Functional
  Dependency, die in der Arbeit als Beispiel dient. Kommentiere sie entsprechend.
- **R-034:** Bewusst implementieren, obwohl im aktuellen Datenmodell nicht auslösbar.
  Kennzeichne das im Docstring **und** in den Metadaten (Feld `fachliche_grundlage`).
- **R-047 / R-048 / R-053 / R-054:** Schwellenwertbasiert. Die Schwellen kommen aus der
  Konfiguration, nicht als Literal im Code — sie werden in der Arbeit diskutiert und
  müssen ohne Codeänderung variierbar sein.
- **R-054:** Vergleich gegen den **Median der übrigen Angebote derselben Anfrage**, nicht
  gegen einen absoluten Wert. Monats- statt Jahresbeitrag ist ein Faktor 12.
- **R-058:** Referenzabgleich der Regionalklassen gegen `regionalklassen.csv` über
  `zulassungsbezirk`, nicht über PLZ. Kein Bezug zu `tarif` — `risiko_kfz` hat keinen.
- **R-047, R-048:** Diese beiden melden keine einzelne verursachende Zelle. R-047 weiß
  nicht, welches der n Angebote das falsche ist; R-048 prüft eine Verteilung über den
  Gesamtdatensatz. Beide werden als **Diagnosekennzahl** geführt und fließen nicht in die
  Zellmetrik ein. Kennzeichne das im Metadatenfeld `in_zellmetrik: False`.

## Aufgabe 4 — Ausführungsengine

```python
def pruefe_alles(kontext: Kontext, regeln: Sequence[Regel]) -> Detektionen
```

- Führt alle Regeln aus und sammelt die Verstöße.
- `detections.parquet` mit den Spalten oben.
- **Deduplizierung für die Metrik:** Zusätzlich eine Sicht `markierte_zellen` als
  **Vereinigungsmenge** der Tripel `(entitaet, row_id, spalte)`. Markieren mehrere Regeln
  dieselbe Zelle, zählt sie **einmal**. Andernfalls wird die Precision künstlich klein.
  Beide Sichten werden gespeichert: die Rohtreffer je Regel für die Diagnose, die
  Vereinigungsmenge für die Metrik.
- Laufzeit je Regel messen und in `rule_timing.json` ablegen.

Wo pandera sinnvoll einsetzbar ist (G1-Regeln auf Spaltenebene), nutze es mit
`lazy=True`, damit alle Verstöße gesammelt statt beim ersten abgebrochen werden. Für G2
bis G5 schreibe eigene Prüffunktionen — pandera ist dafür nicht gedacht.

## Aufgabe 5 — Clean-Baseline-Lauf

`scripts/validate.py --run-id <id> --dataset clean`

Führt den vollständigen Katalog auf `df_clean` aus. **Erwartung: null Meldungen.**

Jede Meldung ist entweder ein Generatorfehler oder eine zu streng formulierte Regel.
Beides muss vor dem Freeze behoben sein. Schreibe das Ergebnis nach
`results/clean_baseline.json` mit: Zahl der Meldungen je Regel, Gesamtzahl, daraus
abgeleitete False-Positive-Rate auf sauberen Daten.

**Diese Kennzahl muss in der Arbeit stehen.** Sie ist der Beweis dafür, dass die
Grundannahme „alles nicht Injizierte ist sauber" überhaupt trägt.

Falls du zur Behebung eine Regel anpassen musst: Das ist noch **vor** dem Freeze zulässig
und erlaubt. Dokumentiere jede Anpassung trotzdem in `docs/iteration_log.md`.

## Aufgabe 6 — Tests

- `tests/test_regeln/`: **Je Regel mindestens ein positiver und ein negativer Fall**, auf
  handgebauten Minimal-DataFrames, nicht auf dem Generator-Output. 58 Regeln → mindestens
  116 Testfälle. Benenne die Testdateien nach den Regelgruppen.
- `tests/test_invariante.py`: property-based mit hypothesis. Erzeuge schemakonforme
  Minimalsätze und prüfe die Invariante: **schemakonforme Daten erzeugen null Meldungen.**
  Mindestens 200 Beispiele je Entität.
  **Beschränke die Invariante auf die Regelgruppen G1 und G2.** Für G3 bis G5 wäre sie
  falsch: Einzelne schemakonforme Entitäten verletzen die referenzielle Integrität immer,
  und eine hypothesis-Strategie, die einen referenziell konsistenten Mehrtabellen-Graphen
  erzeugt, würde im Kern den Generator nachbauen. Begründe die Einschränkung im Docstring —
  sie ist methodisch sauber, aber sie muss benannt sein.
- `tests/test_engine.py`: Prüft die Deduplizierung — zwei Regeln, die dieselbe Zelle
  markieren, ergeben in `markierte_zellen` genau einen Eintrag.
- `tests/test_architecture.py` muss grün bleiben.

## Aufgabe 7 — Katalogexport

`scripts/export_katalog.py` erzeugt `results/regelkatalog.csv` aus den Regel-Metadaten:
Regel-ID, Beschreibung, Entität, Spalten, G/B/C, Schweregrad, Literatur, fachliche
Grundlage. **Diese Datei geht direkt in den Anhang der Arbeit** — sie ist die
Mapping-Tabelle in Kurzform.

## Abnahmekriterien

1. Alle 58 Regeln implementiert, IDs stimmen mit `spec/02_regelkatalog.md` überein,
   jede mit deklarierter Schicht (`raw` / `typed`) und `in_zellmetrik`-Kennzeichen.
2. Clean-Baseline-Lauf: null Meldungen auf `df_clean`.
3. Mindestens 116 Regeltests, alle grün.
4. Property-based Invariante hält.
5. `results/regelkatalog.csv` exportiert.
6. `tests/test_architecture.py` grün.

## Nicht in dieser Phase

Kein Fehlerinjektor, keine Metriken, keine Baselines. Der Injektor kommt **erst nach dem
Freeze** — das ist der Kern der methodischen Absicherung.

Halte am Ende an und berichte, insbesondere: Welche Regeln mussten für den
Clean-Baseline-Lauf angepasst werden und warum? Bei welchen Regeln war die Spezifikation
mehrdeutig?

---

## Danach: FREEZE

Nach erfolgreicher Abnahme dieser Phase führst **du selbst** (nicht Claude Code) aus:

```bash
git add -A
git commit -m "Regelkatalog vollstaendig implementiert, Clean-Baseline-Lauf ohne Meldungen"
git tag -a freeze-regelkatalog -m "Freeze des Regelkatalogs vor Implementierung des Fehlerinjektors"
git rev-parse freeze-regelkatalog     # Hash notieren
```

Trage Hash und Datum in `docs/iteration_log.md` ein. **Dieser Hash gehört in den Anhang
der Bachelorarbeit** — er ist der Beleg dafür, dass die Regeln nicht nachträglich auf die
injizierten Fehler zugeschnitten wurden. Ohne diesen Beleg ist die Behauptung nicht
überprüfbar.

Ab hier gilt: Jede Regeländerung ist eine deklarierte Iteration 2 mit eigener
Ergebnistabelle.
