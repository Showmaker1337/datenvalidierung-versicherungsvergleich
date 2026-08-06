# CLAUDE.md — Projektgedächtnis

Diese Datei liegt im Wurzelverzeichnis des Repositories und wird von Claude Code
bei jedem Start automatisch gelesen. Sie beschreibt, was dieses Projekt ist,
welche Regeln unverhandelbar sind und wie gearbeitet wird.

---

## 1. Was dieses Projekt ist

Prototyp und Evaluationsumgebung für eine Bachelorarbeit mit dem Titel:

> **Regelbasierte Datenvalidierung in Versicherungsvergleichssystemen: Entwicklung
> und experimentelle Evaluation eines Prototyps zur Erkennung typischer
> Datenqualitätsmängel**

Forschungsfrage:

> Inwieweit kann ein regelbasiertes Validierungsverfahren, dessen Regeln aus einer
> literaturbasiert hergeleiteten Fehlertaxonomie abgeleitet sind, Datenqualitätsmängel
> in strukturierten Daten von Versicherungsvergleichssystemen zuverlässig erkennen?

Das Projekt erzeugt einen **synthetischen** Datensatz, verfälscht ihn kontrolliert,
lässt einen Regelkatalog darauf laufen und misst die Erkennungsleistung gegen den
bekannten Ground Truth. Es werden **keine echten Personen- oder Bestandsdaten**
verarbeitet.

**Der Prototyp erkennt Fehler. Er korrigiert sie nicht.** Reparatur ist explizit
außerhalb des Scopes und darf nicht implementiert werden.

---

## 2. Die vier unverhandelbaren Architekturregeln

Diese vier Regeln tragen die wissenschaftliche Verteidigbarkeit der Arbeit. Wenn eine
Anforderung mit ihnen kollidiert, gewinnen immer diese Regeln — dann nachfragen statt
umgehen.

### A1 — Keine Importe zwischen Generator, Injektor und Regel-Engine

```
src/generator/   darf NICHT aus src/rules/ oder src/injector/ importieren
src/injector/    darf NICHT aus src/rules/ oder src/generator/ importieren
src/rules/       darf NICHT aus src/generator/ oder src/injector/ importieren
src/verify/      darf NICHT aus src/injector/ importieren
```

`src/verify/` ist der unabhängige Gegencheck des Ground Truth. Teilt er Code mit dem
Injektor, prüft er nichts.

Gemeinsame Definitionen (Enums, Konstanten, Referenzdaten, Pfade) liegen ausschließlich
in `src/common/`. Alle drei Pakete dürfen aus `src/common/` importieren, sonst nichts
voneinander. Ein Test (`tests/test_architecture.py`) prüft diese Regel am Importgraphen
und muss immer grün sein.

**Grund:** Sobald der Injektor die Regeln kennt, misst das Experiment nur noch, ob
dieselbe Bedingung zweimal implementiert wurde. Der Nachweis am Importgraphen ist
objektiv und wird in der Arbeit zitiert.

### A2 — Vollständige Reproduzierbarkeit

Jeder Lauf ist allein aus `run_id` und Konfiguration exakt reproduzierbar.

- Hierarchisches Seeding über `numpy.random.SeedSequence`, niemals ein globaler Seed.
- Kein `random.random()`, kein `np.random.seed()`, kein ungeseedeter Faker.
- Keine Iteration über `set` oder ungeordnete `dict`-Ansichten, wenn das Ergebnis
  die Reihenfolge beeinflusst.
- Keine Systemzeit in fachlichen Berechnungen. Das Referenzdatum kommt aus der
  Konfiguration (`stichtag`), nicht aus `date.today()`.
- Versionen in `requirements.txt` gepinnt.

### A3 — Ground Truth ist heilig

Der Injektor protokolliert **jede** Verfälschung. Die Protokollregeln stehen in
`spec/03_fehlerklassen.md`, Abschnitt 5, und sind vollständig umzusetzen — insbesondere
die Effektivitätsprüfung (`wert_clean != wert_dirty`) und der unabhängige Diff-Gegencheck.

`row_id` ist niemals Ziel einer Verfälschung.

### A4 — Der Regelkatalog ist eingefroren

Nach dem Git-Tag `freeze-regelkatalog` wird keine Regel mehr inhaltlich geändert.
Notwendige Korrekturen (etwa aus dem Clean-Baseline-Lauf) werden als **Iteration 2**
in `docs/iteration_log.md` dokumentiert: Regel-ID, alte Fassung, neue Fassung,
Begründung, Datum. Niemals stillschweigend ändern.

---

## 3. Verzeichnisstruktur

```
.
├── CLAUDE.md
├── README.md
├── requirements.txt
├── pyproject.toml
├── config/
│   └── default.yaml            # Stichtag, Pfade, Faktorstufen, Master-Seed
├── spec/                       # Fachliche Spezifikation — Quelle der Wahrheit
│   ├── 01_datenmodell.md
│   ├── 02_regelkatalog.md
│   └── 03_fehlerklassen.md
├── _prompts/                   # Phasenprompts für den Nutzer — KEIN Projektinhalt
├── scripts/                    # ausführbare Einstiegspunkte je Phase
├── src/
│   ├── common/                 # Enums, Konstanten, Config, Referenzdaten, Pfade, Seeding
│   ├── generator/              # Erzeugt df_typed und df_raw
│   ├── rules/                  # Regelkatalog + Ausführung
│   ├── injector/               # Erzeugt df_raw_dirty + error_log
│   ├── verify/                 # unabhängiger Ground-Truth-Gegencheck
│   ├── baselines/              # B0 Pydantic, B2 IsolationForest, B3 cuallee
│   ├── evaluation/             # Metriken, Statistik, Abbildungen
│   └── cli.py                  # Einstiegspunkt
├── data/
│   ├── reference/              # Referenztabellen (versioniert, im Repo)
│   └── runs/<run_id>/          # Laufartefakte (nicht im Repo)
├── tests/
├── docs/
│   ├── iteration_log.md
│   └── verteilungsquellen.md   # Je Feld: woher stammt die Verteilungsannahme
└── results/                    # Tabellen und Abbildungen für die Arbeit
```

---

## 4. Technologie

| Zweck | Bibliothek | Hinweis |
|---|---|---|
| DataFrames | pandas | Parquet als Austauschformat |
| Regel-Engine | pandera | `lazy=True`, damit alle Verstöße gesammelt werden |
| Basisdaten | Faker (`de_DE`) | über `faker.seed_instance()` geseedet, **nicht** über das klassenweite `Faker.seed()` — Letzteres setzt globalen Zustand und widerspricht A2 |
| Baseline B0 | pydantic v2 | reine Typ- und Constraint-Validierung |
| Baseline B2 | scikit-learn | `IsolationForest` |
| Baseline B3 | cuallee (bevorzugt) oder great_expectations | derselbe Regelinhalt, anderes Framework |
| Eigentests | pytest, hypothesis | property-based Test der Kern-Invariante |
| Statistik | scipy, numpy | Wilcoxon, Bootstrap |
| Abbildungen | matplotlib | keine Seaborn-Abhängigkeit nötig |

Nicht verwenden: Deequ/PyDeequ (Spark), dbt, Soda Core, SDV.

---

## 5. Konventionen

- **Sprache:** Fachliche Bezeichner (Feldnamen, Enum-Werte, Domänenbegriffe) auf
  Deutsch, exakt wie in `spec/01_datenmodell.md`. Technische Bezeichner
  (`run_id`, `error_log`, `seed_base`) auf Englisch. Kommentare und Docstrings auf Deutsch.
- **Typannotationen** überall. `from __future__ import annotations` in jeder Moduldatei.
- **Keine stillen Fallbacks.** Fehlt eine Referenzdatei oder ein Konfigurationswert,
  wird eine aussagekräftige Exception geworfen — niemals ein Defaultwert stillschweigend
  eingesetzt.
- **Keine Netzwerkzugriffe zur Laufzeit.** Referenzdaten liegen als Dateien im Repo.
- **Geld** ist `Decimal`, niemals `float`. Rundung immer explizit mit
  `ROUND_HALF_UP` auf zwei Nachkommastellen.
- **Datumsfelder** intern als `datetime.date`. Das GDV-Format `TTMMJJJJ` ist ein
  Serialisierungsformat, kein internes Format.
- **Postleitzahlen, HSN, TSN, SF-Klassen** sind Strings. Niemals Integer — die führende
  Null geht sonst verloren, und SF-Sonderklassen (`0`, `1/2`, `S`, `M`) sind keine Zahlen.
- **„Leer" bedeutet immer `pd.NA` bzw. `None`, niemals der Leerstring.** Der Leerstring ist
  in diesem Projekt ein *Fehlerwert* (Injektionsvariante F1-b), kein Fehlwert. Diese
  Unterscheidung ist wichtig, weil R-025 den Leerstring als impliziten Fehlwert meldet.
- **Zwei Datenschichten.** `df_typed` ist die typisierte Innenansicht, `df_raw` die
  Rohschicht mit allen Spalten als String. Der Injektor arbeitet auf `df_raw`, Format- und
  Typregeln ebenfalls, fachliche Regeln auf dem geparsten `df_typed`. Die Serialisierungs-
  regeln stehen in `spec/01_datenmodell.md`, Abschnitt 6. **Ohne diese Trennung sind
  mehrere Regeln per Konstruktion nicht verletzbar.**

---

## 6. Tests

Jede Phase endet mit grünen Tests. `pytest` muss ohne Fehler durchlaufen, bevor eine
Phase als abgeschlossen gilt.

Pflichttests:

1. `tests/test_architecture.py` — Importgraph verletzt A1 nicht.
2. `tests/test_reproduzierbarkeit.py` — zweimal derselbe Seed erzeugt bitgleiche Ausgabe.
3. `tests/test_regeln/` — je Regel mindestens ein positiver und ein negativer Fall.
4. `tests/test_invariante.py` — property-based mit hypothesis: schemakonforme Daten
   erzeugen null Meldungen.
5. `tests/test_ground_truth.py` — Diff-Gegencheck, Effektivitätsprüfung, keine
   Doppelinjektion.

---

## 7. Was Claude Code nicht tun soll

- Keine Reparatur- oder Korrekturfunktionen implementieren.
- Keine Regeln erfinden, die nicht in `spec/02_regelkatalog.md` stehen. Fehlt etwas,
  erst nachfragen und die Spezifikation ergänzen, dann implementieren.
- Den Regelkatalog nach dem Freeze nicht anpassen, um Messergebnisse zu verbessern.
- Keine echten Personendaten, keine externen Datenquellen zur Laufzeit laden.
- Keine `TODO`-Platzhalter in ausgelieferten Funktionen. Was nicht fertig ist, wird
  benannt, nicht stillschweigend leer gelassen.
- Nicht mehrere Phasen auf einmal abarbeiten. Am Ende jeder Phase anhalten und den
  Stand berichten.
- **`_prompts/` ist kein Projektinhalt.** Der Ordner enthält die Phasenprompts, die der
  Nutzer nacheinander einfügt. Lies dort nichts von dir aus und arbeite keine Phase ab, die
  nicht ausdrücklich beauftragt wurde. Insbesondere: Der Fehlerinjektor entsteht erst nach
  dem Git-Tag `freeze-regelkatalog`, auch wenn seine Spezifikation bereits vorliegt.
