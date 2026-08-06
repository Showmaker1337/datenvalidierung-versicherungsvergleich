# Phase 3c — Freeze des Regelkatalogs

> Nach Phase 3b, wenn alle Tests grün sind. Kopiere alles ab der Trennlinie in Claude Code.

---

Setze den Freeze des Regelkatalogs. Das ist ein kleiner Schritt mit großer Bedeutung: Der
Commit-Hash dieses Tags ist in der Bachelorarbeit der Beleg dafür, dass die
Validierungsregeln feststanden, **bevor** der Fehlerinjektor existierte. Ohne ihn ist die
Behauptung nicht überprüfbar.

## Aufgabe 1 — Vorbedingungen prüfen, nicht annehmen

Führe alle vier Prüfungen aus und **brich ab, wenn eine fehlschlägt**. Melde dich dann, statt
den Tag trotzdem zu setzen.

1. `pytest` läuft vollständig grün durch.
2. `ruff check .` und `mypy` sind sauber.
3. **Der Clean-Baseline-Lauf meldet null Verstöße.** Führe ihn jetzt erneut aus, nicht aus
   dem Gedächtnis — das ist die inhaltlich entscheidende Bedingung.
4. `git status` zeigt ein sauberes Arbeitsverzeichnis, `git log origin/main..HEAD` ist leer
   (alles gepusht).

Prüfe zusätzlich, dass alle 58 Regeln im Katalog registriert sind und
`results/regelkatalog.csv` dem aktuellen Stand entspricht.

## Aufgabe 2 — Tag setzen und pushen

```bash
git tag -a freeze-regelkatalog -m "Freeze des Regelkatalogs vor Implementierung des Fehlerinjektors"
git push origin main --follow-tags
```

`git push` allein überträgt keine Tags. Prüfe danach mit `git ls-remote --tags origin`, dass
der Tag tatsächlich auf GitHub liegt — ein nur lokaler Tag ist im Anhang der Arbeit wertlos.

Falls der Push wegen des Account-Wechsels scheitert: melde dich, führe kein `gh auth login`
und keinen Accountwechsel von dir aus durch.

## Aufgabe 3 — Den Hash dokumentieren

Ermittle `git rev-parse freeze-regelkatalog` und trage ihn an drei Stellen ein:

- **`README.md`**, in den Abschnitt „Freeze des Regelkatalogs": Hash, Datum, Zahl der Regeln
  (58), Ergebnis des Clean-Baseline-Laufs (null Verstöße bei rund 1,77 Mio. geprüften Zellen)
  und die Zahl der Regeltests (163).
- **`docs/iteration_log.md`**, als Abschluss von Iteration 1.
- **`results/freeze.json`** — neu anzulegen, maschinenlesbar: Hash, Datum, Regelzahl,
  Testzahl, Clean-Baseline-Ergebnis, Commit-Hash von `main`. Diese Datei wandert später ins
  Reproduzierbarkeitspaket.

## Aufgabe 4 — Festhalten, was der Freeze umfasst

Schreibe in `docs/iteration_log.md` einen kurzen Abschnitt mit genau dieser Abgrenzung:

**Eingefroren sind die Regeln selbst** — Prädikate, Wertebereiche, Schwellenwerte,
Geltungsbereiche, Schweregrade, die Zuordnung zu den Achsen A, B und C. Jede Änderung daran
ab jetzt ist Iteration 2 und wird mit eigener Ergebnistabelle berichtet.

**Nicht eingefroren sind die Belege daneben** — die Spalten „Literatur" und „Fachliche
Grundlage" im Katalog sowie Formulierungen in `spec/`. Diese dokumentieren die Herleitung
und dürfen jederzeit korrigiert werden, solange sich das geprüfte Prädikat nicht ändert.
Der Grund: Der Freeze belegt, dass die Regeln vor dem Injektor feststanden — er belegt nicht,
dass jede Fußnote von Anfang an richtig war.

Diese Unterscheidung ist wichtig, weil die Literaturbelege des Katalogs noch geprüft werden.
Ohne sie müsste jede korrigierte Quellenangabe als Regeländerung deklariert werden, was
sachlich falsch wäre.

## Aufgabe 5 — Bericht

Melde:

- den vollen Commit-Hash des Tags,
- die URL zum Tag auf GitHub,
- das Ergebnis aller vier Vorbedingungsprüfungen,
- ob der Tag auf dem Remote angekommen ist.

## Nicht in dieser Phase

Kein Fehlerinjektor, keine Änderung an `src/rules/`, keine neuen Regeln. Der Injektor kommt
als eigener Prompt — **nach** diesem Tag, das ist der ganze Punkt.
