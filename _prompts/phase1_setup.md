# Phase 1 — Projektgerüst, gemeinsame Bausteine und Referenzdaten

> Kopiere alles ab der Trennlinie in Claude Code.

---

Du baust den Prototyp für eine Bachelorarbeit über regelbasierte Datenvalidierung in
Versicherungsvergleichssystemen. Lies zuerst `CLAUDE.md` und `spec/01_datenmodell.md`
vollständig. Beides ist verbindlich.

**Diese Phase erzeugt ausschließlich das Gerüst, die gemeinsamen Bausteine und die
Referenzdaten. Kein Generator, keine Regeln, kein Injektor.** Halte am Ende an und
berichte.

## Aufgabe 1 — Projektstruktur

Lege die Struktur aus `CLAUDE.md`, Abschnitt 3 an. `requirements.txt` mit gepinnten
Versionen für: pandas, pyarrow, pandera, faker, pydantic, scikit-learn, cuallee, scipy,
numpy, matplotlib, pytest, hypothesis, pyyaml.

`pyproject.toml` mit ruff und mypy, beide auf strikte Einstellungen.

`config/default.yaml` mit mindestens:

```yaml
stichtag: "2026-06-30"          # Referenzdatum für alle Altersberechnungen
master_seed: 20260630
n_anfragen: 10000
angebote_je_anfrage: {min: 3, max: 12}
sparten_verteilung: {"051": 0.35, "052": 0.20, "053": 0.15, "130": 0.30}
pfade:
  reference: "data/reference"
  runs: "data/runs"
  results: "results"

# Schwellenwerte der heuristischen Regeln (C2).
# Sie stehen bewusst hier und nicht im Code, weil sie in der Arbeit
# diskutiert und variiert werden.
schwellen:
  r047_spreizung_max: 6.0          # max/min Zahlbeitrag je Anfrage
  r048_zuers_toleranz_relativ: 0.30
  r053_korridor_kfz_eur: [40, 6000]
  r053_korridor_hausrat_eur: [20, 2000]
  r054_faktor: 12.0
  r054_toleranz_relativ: 0.05
  r022_wohnflaeche: [10, 1000]
  r031_toleranz_eur: 0.02
  r036_toleranz_je_rate_eur: 0.01  # skaliert mit der Ratenanzahl
```

## Aufgabe 2 — `src/common/`

`config.py`
: Lädt `config/default.yaml` in eine typisierte, eingefrorene Dataclass `Config`. Alle
  Pfade, Faktorstufen, Schwellenwerte und der Stichtag hängen daran. **Jede andere
  Komponente bekommt `Config` übergeben und liest nie selbst YAML.**

`seeding.py`
: Hierarchisches Seeding über `numpy.random.SeedSequence`. **Zwei Ebenen:**

  ```python
  def wurzel_seeds(master_seed: int) -> Seeds
      # gibt SeedSequence-OBJEKTE zurück (nicht Integer!), Felder:
      # basis, injektion, modell  — aus ss.spawn(3)

  def lauf_seed(master_seed: int, strom: int, *faktoren: int) -> SeedSequence
      # faktorbasiert und reihenfolgeunabhängig:
      # SeedSequence([master_seed, strom, *faktoren])
  ```

  `lauf_seed` ist die entscheidende Funktion: In Phase 6 laufen tausende Einzelläufe
  parallel, und jeder muss seinen Seed **aus seiner Faktorkombination** ableiten, nicht
  aus einem laufenden Zähler. `SeedSequence.spawn()` ist ein Zähler und damit
  reihenfolgeabhängig — es darf für Einzelläufe nicht verwendet werden, sonst hängen die
  Ergebnisse von der Worker-Zahl ab.

  Zusätzlich Hilfsfunktionen, die aus einer `SeedSequence` einen `numpy.random.Generator`
  und eine geseedete `Faker`-Instanz erzeugen. **Nirgendwo sonst im Projekt wird ein
  Zufallsgenerator erzeugt.**

`enums.py`
: Alle Enums und Schlüsselkataloge aus `spec/01_datenmodell.md` als `StrEnum` oder
  eingefrorene Konstanten: Sparten, Zahlweise (nur 1, 2, 4, 5, 6, 8, 9 — **3 und 7
  existieren nicht**), Kanal, Anrede, Rolle, Nutzungsart, Art Kennzeichen,
  Eigentumsverhältnis, Nutzerkreis, Abstellplatz, Gebäudeart, Bauartklasse,
  Annahmeentscheidung, Anfragestatus, Quellschnittstelle, SF-Klassen.

`wertebereiche.py`
: Alle numerischen Grenzen als benannte Konstanten: Typklassen (HP 10–25, TK 10–33,
  VK 10–34), Regionalklassen (1–12 / 1–16 / 1–9), ZÜRS 1–4, Wohnfläche, Baujahr,
  PflVG-Mindestdeckungssummen (7.500.000 / 1.300.000 / 50.000), Versicherungsteuer-
  Effektivsätze je Sparte (051/052/053 → 19.00, 130 → 16.15).

`geld.py`
: Rechnen mit `Decimal`. Eine Funktion `runde(betrag) -> Decimal` mit `ROUND_HALF_UP` auf
  zwei Nachkommastellen. **Nirgendwo im Projekt wird Geld als float geführt.**

`iban.py`
: `berechne_pruefziffer(bankleitzahl, kontonummer) -> str` und
  `ist_gueltig(iban) -> bool` nach ISO 7064 Mod 97-10 (Pseudocode in
  `spec/02_regelkatalog.md`, Abschnitt G1). Diese Datei liegt in `common`, weil sowohl der
  Generator (gültige IBANs erzeugen) als auch die Regel-Engine (prüfen) sie brauchen —
  das ist zulässig und verletzt Architekturregel A1 nicht.

`referenz.py`
: Lädt die Referenztabellen aus `data/reference/` mit Caching. Wirft eine
  aussagekräftige Exception, wenn eine Datei fehlt — **kein stiller Fallback**.

`pfade.py`
: Lauf-Verzeichnisse, Artefaktnamen, SHA-256-Hashing von DataFrames.

## Aufgabe 3 — Referenzdaten erzeugen

Ein Skript `scripts/build_reference.py`, das alle Tabellen aus
`spec/01_datenmodell.md`, Abschnitt 2, deterministisch erzeugt und nach
`data/reference/` schreibt: `plz_ort.csv`, `regionalklassen.csv`, `typklassen.csv`,
`vu_stammdaten.csv`, `zuers_zonen.csv`, `sf_beitragssatz.csv`, `waehrungen.csv`.

Beachte:

- **`plz_ort.csv`:** Versuche zuerst, echte PLZ-Daten von OpenPLZ API oder BKG zu
  beziehen und im Repo abzulegen. Gelingt das nicht, erzeuge rund 8.000 synthetische
  Einträge, die die Leitzonen-Systematik einhalten. Dokumentiere die gewählte Variante in
  `docs/verteilungsquellen.md`. Zur Laufzeit wird **nichts** nachgeladen.
- **`sf_beitragssatz.csv`:** Der Beitragssatz muss über die numerischen SF-Klassen streng
  monoton fallen. Ankerwerte SF 1 ≈ 58 %, SF 50 ≈ 16 %. Sonderklassen: M = 245, S = 155,
  0 = 100, 1/2 = 70.
- **`zuers_zonen.csv`:** Die Zonenanteile über alle PLZ müssen 92,4 / 6,1 / 1,1 / 0,4
  Prozent ergeben (Toleranz 0,3 Prozentpunkte).
- **`typklassen.csv`:** HSN vierstellig mit führenden Nullen als String, TSN dreistellig
  alphanumerisch. Alle drei Typklassenspalten innerhalb ihrer jeweiligen Grenzen.

Alle Tabellen werden **einmalig** erzeugt und danach versioniert. Ein zweiter Lauf mit
demselben Seed muss bitgleiche Dateien liefern.

## Aufgabe 4 — Tests

- `tests/test_architecture.py`: Prüft am Importgraphen (per `ast`-Parsing der Quelldateien,
  nicht per Laufzeit-Import), dass `src/generator/`, `src/injector/` und `src/rules/`
  nicht voneinander importieren und dass `src/verify/` nicht aus `src/injector/`
  importiert — jeweils auch transitiv. Der Test muss **jetzt schon** existieren und grün
  sein, obwohl die Pakete noch leer sind.
- `tests/test_iban.py`: Prüft `common/iban.py` gegen mindestens fünf bekannte gültige
  deutsche IBANs und fünf ungültige.
- `tests/test_referenz.py`: Prüft, dass alle Referenztabellen die in
  `spec/01_datenmodell.md` genannten Wertebereiche einhalten, dass die ZÜRS-Verteilung
  stimmt und dass die SF-Beitragssätze monoton fallen.
- `tests/test_reproduzierbarkeit.py`: `scripts/build_reference.py` zweimal mit demselben
  Seed ausführen und die SHA-256-Hashes vergleichen.

## Aufgabe 5 — Dokumentation

`README.md` mit Projektzweck, Installation und den Kommandos je Phase.
`docs/verteilungsquellen.md` anlegen mit der Tabelle aus `spec/01_datenmodell.md`,
Abschnitt 4, und den in dieser Phase getroffenen Entscheidungen eintragen.
`docs/iteration_log.md` als leere Datei mit Kopfzeile anlegen — sie wird ab Phase 3
gebraucht.

Lege außerdem die leeren Paketverzeichnisse `src/generator/`, `src/rules/`,
`src/injector/`, `src/verify/`, `src/baselines/`, `src/evaluation/` und `scripts/` mit
`__init__.py` an, damit der Architekturtest von Anfang an etwas zu prüfen hat.

## Abnahmekriterien

1. `pytest` läuft grün durch.
2. `ruff check` und `mypy src/` sind sauber.
3. `python scripts/build_reference.py` erzeugt alle sieben Referenztabellen.
4. Zwei Läufe mit demselben Seed erzeugen identische Hashes.
5. `data/reference/` liegt im Repository, `data/runs/` ist über `.gitignore` ausgeschlossen.

## Nicht in dieser Phase

Kein Datengenerator, keine Validierungsregeln, kein Fehlerinjektor, keine Metriken.
Wenn dir beim Lesen der Spezifikation ein Widerspruch oder eine Lücke auffällt: melde ihn,
statt ihn eigenmächtig aufzulösen.

Halte am Ende an und berichte: was gebaut wurde, welche Testergebnisse vorliegen, welche
Entscheidungen du treffen musstest und wo du eine Lücke in der Spezifikation siehst.
