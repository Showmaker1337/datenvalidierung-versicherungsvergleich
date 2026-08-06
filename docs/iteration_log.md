# Iterationslog des Regelkatalogs

Diese Datei dokumentiert **jede** inhaltliche Änderung an einer Regel nach dem Git-Tag
`freeze-regelkatalog` (Architekturregel A4). Sie wird ab Phase 3 gebraucht und ist bis
dahin bewusst leer.

## Warum es diese Datei gibt

Der Regelkatalog ist das Design-Artefakt der Arbeit. Er wird **vor** dem Fehlerinjektor
entwickelt und anschließend eingefroren. Der Commit-Hash des Tags belegt, dass die
Validierungsregeln nicht nachträglich auf die injizierten Fehler zugeschnitten wurden.

Notwendige Korrekturen — etwa aus dem Clean-Baseline-Lauf, in dem eine zu streng
formulierte Regel auf sauberen Daten auslöst — sind erlaubt, aber niemals stillschweigend.
Sie werden hier als **Iteration 2** eingetragen und in der Arbeit berichtet. Eine
dokumentierte Korrektur ist ein Befund; eine unbemerkte ist ein Methodenfehler.

## Eintragsformat

Je Änderung ein Abschnitt mit allen fünf Angaben:

```markdown
### R-0xx — <Kurztitel der Änderung>

- **Datum:** JJJJ-MM-TT
- **Iteration:** 2
- **Alte Fassung:** <wörtliches Prädikat vor der Änderung>
- **Neue Fassung:** <wörtliches Prädikat nach der Änderung>
- **Begründung:** <warum die alte Fassung nicht tragfähig war; bei Befunden aus dem
  Clean-Baseline-Lauf mit Anzahl der Fehlalarme>
- **Auswirkung auf die Messung:** <welche Ergebnistabellen sich ändern>
```

---

## Iteration 1 — Ausgangsfassung

Der Katalog in `spec/02_regelkatalog.md` mit 58 Regeln (R-001 bis R-058).

- **Stand:** noch nicht implementiert, Freeze steht aus.
- **Tag:** `freeze-regelkatalog` — wird nach Phase 3 gesetzt.

---

## Iteration 2 — Korrekturen nach dem Freeze

*Noch keine Einträge.*
