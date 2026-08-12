# Phase 5b — Nachtrag: B3 einordnen, Kennzahlen probelaufen

> Direkt im Anschluss an Phase 5, **im selben Chat**. Kopiere alles ab der Trennlinie.

---

Fünf Nachträge. Der zweite ist der wichtigste — er betrifft die Aussage, mit der die Arbeit
die Frage „Warum ein eigener Prototyp?" beantwortet.

## Aufgabe 1 — Zuerst committen und pushen

Phase 5 unverändert committen und pushen, danach die Änderungen aus diesem Nachtrag als
eigener Commit.

## Aufgabe 2 — Die Lokalisierungsaussage von B3 einengen

Dein Befund ist richtig: cuallee liefert je Regel eine Zeile mit
`id, timestamp, check, level, column, rule, value, rows, violations, pass_rate,
pass_threshold, status` — keine Zeilen-ID, keinen Ausgangswert. Eine zellweise
Konfusionsmatrix ist daraus tatsächlich nicht bildbar.

**Der Satz darf aber nicht über cuallee hinaus verallgemeinert werden.** Great
Expectations — in `CLAUDE.md`, Abschnitt 4, ausdrücklich als Alternative für B3 genannt —
liefert genau das, was cuallee nicht liefert: Bei `result_format: COMPLETE` und
konfigurierten `unexpected_index_column_names` gibt `unexpected_index_list` je
fehlgeschlagener Zeile ein Dictionary mit Zeilenkennung **und** fehlerhaftem Wert zurück,
dazu `unexpected_index_query` als nachvollziehbare Abfrage.

Stünde in der Arbeit „etablierte Frameworks können Fehler nicht auf die Zelle
lokalisieren", genügt einem Prüfer die Kenntnis von Great Expectations, um die Aussage zu
kippen — und mit ihr die Begründung des Artefakts. Das wäre vermeidbar.

### Was zu tun ist

Formuliere die Kennzahl „Diagnosegüte" in `README.md`, im Docstring von
`b3_framework.py` und überall, wo du sie beschreibst, als **Eigenschaft von cuallee**, nicht
als Eigenschaft der Kategorie. Etwa: *cuallee berichtet auf Constraint-Ebene; Zeilen- und
Wertbezug sind in seinem Ausgabeformat nicht vorgesehen. Andere Frameworks entscheiden das
anders — Great Expectations liefert mit `unexpected_index_list` genau diesen Bezug.*

### Und: stelle die Argumentation um

Die tragfähige Antwort auf „Warum ein eigener Prototyp?" ist nicht die Lokalisierung,
sondern die **Ausdrückbarkeit** — und die ist frameworkübergreifend belastbar, weil sie an
der Form der Regeln hängt und nicht am Berichtsformat:

**36,2 Prozent des Katalogs sind in einer DataFrame-Check-API abbildbar. 63,8 Prozent nicht.**

Das betrifft die bedingten Regeln (CFD-Form wie R-001), die relationalen (R-044, R-052,
R-054), die satzübergreifenden und die algorithmischen (R-004 Prüfziffer, R-009 realer
Kalendertag). Diese Grenze verschiebt sich durch die Wahl des Frameworks nur wenig — sie
liegt in der Ausdrucksmächtigkeit spaltenweiser Prüfausdrücke selbst.

Führe die Lokalisierung als **zweiten, nachgeordneten** Punkt mit der cuallee-Einschränkung.
Damit steht die Kernaussage auf der Zahl, die hält.

## Aufgabe 3 — Optional, wenn Zeit ist: ein kleiner Great-Expectations-Gegenschnitt

Nur wenn es zeitlich passt, und **strikt begrenzt**: Implementiere fünf bis acht der G1-Regeln
zusätzlich in Great Expectations — darunter R-001 (bedingt), R-004 (Prüfziffer) und zwei,
die in cuallee glatt durchgehen. Miss dieselben vier Kennzahlen.

Ziel ist **nicht** eine dritte Baseline. GE geht wie B3 **nicht** in die Inferenzstatistik.
Ziel ist eine zweite Spalte in der Frameworkvergleichstabelle, die zeigt: Ausdrückbarkeit
ist bei beiden ähnlich begrenzt, Diagnosegüte unterscheidet sich deutlich. Aus einer
Verteidigung gegen einen möglichen Einwand wird damit ein eigener Befund über den
Gestaltungsraum.

Wenn die Zeit nicht reicht: Aufgabe 2 allein genügt, dann wird die fehlende zweite
Framework-Studie als Limitation benannt.

## Aufgabe 4 — Zwei Ergebnisse dokumentieren, die wie Fehler aussehen

**Constraint-Ebene und Zellebene haben denselben Recall.** Nach deiner Korrektur ist das
korrekt und zwar per Konstruktion: Zähler wie Nenner sind in beiden Fällen injizierte
Zellen, nur die Precision unterscheidet sich, weil dort Verstöße statt Zellen im Nenner
stehen. Schreibe genau diesen Satz in den Docstring und in `README.md`. Ohne ihn liest die
Gleichheit wie ein Copy-Paste-Fehler, und die Constraint-Ebene wirkt überflüssig — dabei
ist sie genau für die Precision eingeführt worden.

**B0 fängt R-009 mit.** Dass der Datumsparser von pydantic den 31. Februar zurückweist,
ist kein Mangel der B0-Definition, sondern ein Befund: Die Grenze zwischen Typprüfung und
fachlicher Regel ist nicht scharf. Für die Achse C der Taxonomie ist das relevant — eine
Regel, die als fachlich eingeordnet ist, fällt bei passender Typwahl kostenlos an. Notiere
es in `docs/iteration_log.md` als Material für die Diskussion, nicht als Korrektur.

## Aufgabe 5 — `ruff format` bewusst nicht ausführen, und zwar aktenkundig

Deine Entscheidung ist richtig, aber die Begründung im Log sollte die stärkere sein: Ein
Reformat würde auch `src/rules/` anfassen. Nach der Entscheidungsprobe ist das keine
Regeländerung — die Menge der gemeldeten Zellen bleibt gleich. Aber wer den Tag gegen HEAD
diffed, um zu prüfen, dass die Regeln unverändert sind, bekommt dann Formatierungsrauschen
über alle Regelmodule statt einer leeren Ausgabe. Der Freeze soll **nachprüfbar** bleiben,
nicht nur gültig.

Halte in `docs/iteration_log.md` fest: `ruff format` wird für den Bestand nicht ausgeführt,
neue Dateien werden format-konform geschrieben, Begründung wie oben. Damit „repariert" das
niemand später versehentlich.

## Aufgabe 6 — Probelauf der beiden Gewichtungen, bevor Phase 6 rechnet

Führe den Evaluator einmal auf je einem vorhandenen Lauf der Klassen **F4** und **HO2** aus
und berichte:

- Klassen-Recall zellgewichtet und variantengewichtet, nebeneinander
- Recall je Variante mit `n` und Clopper-Pearson-Intervall
- beide Einstellungen von `mitgezogen_als_fehler`

Erwartung aus der Zuteilung: F4 nahe eins zellgewichtet (F4-g stellt 73,5 Prozent und löst
zwangsläufig aus), HO2 nahe null (HO2-b stellt 90,7 Prozent und soll unentdeckt bleiben) —
und beide variantengewichtet deutlich anders. Weicht das ab, stimmt etwas an der Gewichtung
nicht, und das will man an zwei Läufen merken und nicht an 1.680.

## Abnahme

1. Phase 5 committet, dieser Nachtrag als eigener Commit.
2. Lokalisierungsaussage überall auf cuallee eingegrenzt, GE namentlich als Gegenbeispiel.
3. Ausdrückbarkeit als Hauptargument, Diagnosegüte nachgeordnet.
4. Recall-Gleichheit der Constraint-Ebene und der B0/R-009-Befund dokumentiert.
5. `ruff format`-Entscheidung mit Freeze-Begründung im Iterationslog.
6. Probelauf gerechnet und berichtet.

Am Regelkatalog ändert sich nichts.
