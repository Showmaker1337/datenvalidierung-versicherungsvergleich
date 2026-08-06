# Phase 3b — Spezifikation nachziehen, dann Freeze

> Kurz, vor dem Git-Tag. Kopiere alles ab der Trennlinie in Claude Code.

---

Du hast fünf Stellen gemeldet, an denen die Spezifikation mehrdeutig war. Drei sind
entschieden und in den Dateien korrigiert, zwei musst du nachtragen. **Das ist bewusst noch
vor dem Freeze**, weil die eingefrorene Spezifikation den tatsächlich implementierten Stand
tragen muss — sonst friert der Tag ein Dokument ein, das den Code nicht beschreibt.

## Bereits korrigiert — lies neu ein

**R-025 und der Leerstring.** Deine Auflösung zugunsten von `spec/01` ist richtig und steht
jetzt so in `CLAUDE.md`, Abschnitt 5. Der Widerspruch war meiner: Ich hatte den Leerstring
in `CLAUDE.md` zum Fehlerwert erklärt und in `spec/01` zum regulären Leerwert. Auf der
Rohschicht sind beide Fälle nicht unterscheidbar, also gewinnt `spec/01`.

Die Folge ist in `spec/03`, Variante F1-b, jetzt ausdrücklich vermerkt: erkennbar nur über
R-001 und R-057, nicht über R-025. **Und sie ist als das benannt, was sie ist** — ein
Informationsverlust der Serialisierung, kein Implementierungsmangel. Genau das passiert an
realen Schnittstellen, wenn ein Format zwischen „nicht belegt" und „leer geliefert" nicht
unterscheidet. Der Punkt gehört in die Diskussion der Arbeit.

**Kennzahlen der Achse C.** Deine Auszählung stimmt, meine Zusammenfassung nicht. In
`spec/02` steht jetzt C1 = 44, C2 = 11, C3 = 3 mit den drei C3-Regeln namentlich (R-050,
R-051, R-058). Danke fürs Nachzählen — die Zahl wäre so in die Arbeit gewandert.

**R-034 als Umkehrschluss.** Richtig entschieden. Schlüssel zu erfinden, die im Modell nicht
vorkommen, wäre schlechter als die Ableitung aus dem Steuersatzkatalog. Halte die
Begründung im Docstring fest, falls noch nicht geschehen.

## Aufgabe 1 — `spec/01`, Abschnitte 5.1 und 5.2 nachtragen

Du hast beide in Phase 2 implementiert, aber die Spezifikation trägt sie nicht. R-041,
R-057 und `pflichtfelder.py` verweisen ins Leere.

Trage die tatsächlich implementierten Inhalte nach:

- **Abschnitt 5.1 — Pflichtfeldprofil je `kanal`.** Die Tabelle Kanal × Feld → Pflicht oder
  optional, so wie sie in `pflichtfelder.py` steht. Dazu ein Satz, warum die Anfrageseite am
  Kanal hängt und nicht an der Quellschnittstelle.
- **Abschnitt 5.2 — Anwendbarkeitsbedingungen.** Wann eine Pflichtfeldprüfung *nicht* gilt:
  spartenbedingt (`sb_tk_eur` nur bei Kasko) und zeilenbezogen (`familienstand` nicht bei
  `anrede` = FIRMA). Nimm den Fall, der dir im Clean-Baseline-Lauf 135 Fehlalarme beschert
  hat, ausdrücklich als Beispiel auf — er zeigt, warum die Bedingung nötig ist.

Schreibe, was im Code steht. Erfinde nichts dazu, und ändere nichts am Verhalten.

## Aufgabe 2 — Die vier kleineren Auslegungen in die Spezifikation

Deine Entscheidungen sind alle vertretbar, aber sie stehen bisher nur im Iterationslog.
Trage sie an der jeweiligen Regel in `spec/02` als kurzen Zusatz nach, damit der eingefrorene
Katalog vollständig ist:

- **R-032** nutzt die Toleranz von R-031 (kein zweiter Schlüssel für denselben Rundungsschritt)
- **R-054** verlangt mindestens zwei Vergleichsangebote
- **R-052** nimmt die Mehrheit als Bezugspunkt
- **R-009** prüft Datums-, nicht Zeitpunktfelder

## Aufgabe 3 — Die Abweichung von der Prompt-Vorgabe dokumentieren

`pruefe` gibt zwei Kanäle zurück statt eines DataFrame. Deine Begründung trägt: Ein einzelner
Datenrahmen kann den satzbezogenen Kanal nicht führen. Halte das in `docs/iteration_log.md`
fest, mit den betroffenen Regeln (R-043, R-045, R-046, R-047, R-048, R-055) — in Phase 5
braucht der Evaluator diese Information.

## Abnahme

1. `spec/01` hat die Abschnitte 5.1 und 5.2, inhaltlich deckungsgleich mit `pflichtfelder.py`.
2. Die vier Auslegungen stehen an der jeweiligen Regel in `spec/02`.
3. Die Zwei-Kanal-Rückgabe ist im Iterationslog dokumentiert.
4. Clean-Baseline-Lauf weiterhin null Meldungen (Regression).
5. `pytest`, `ruff`, `mypy` grün. Commit und Push.

**Danach ist der Stand freeze-reif.** Setze den Tag nicht selbst — das macht der Nutzer.

Halte an und berichte, was du nachgetragen hast.
