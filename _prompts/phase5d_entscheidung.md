# Phase 5d — Entscheidung: Kohärenzpflege nach der Injektion

> Im selben Chat. Kopiere alles ab der Trennlinie.

---

Deine Diagnose ist besser als meine drei Hypothesen — Interferenz zwischen zwei Anwendungen
derselben Variante innerhalb einer Anfrage stand auf keiner meiner Listen, und die Zahlen
belegen sie sauber: alle 11 betroffenen Anfragen haben mehr als eine Skalierung, keine der
1.102 mit genau einer ist betroffen. Auch die Ratenabhängigkeit ist damit erklärt und nicht
nur gemessen: 2 / 14 / 57 / 294 Anfragen mit ≥ 2 Skalierungen, und die Verstöße folgen
proportional.

**Zur Entscheidung: nicht (b).** Deine Begründung trägt. Eine Obergrenze je Anfrage
verkleinert das adressierbare Universum, und das Universum ist die Bezugsgröße der
Fehlerrate — also genau die Größe, die UV2 variiert. Phase 4b hat diese Kopplung gerade
entfernt; (b) führte sie durch die Hintertür wieder ein, samt Abbruch an den oberen
Ratenstufen.

**Aber auch nicht (a) in der beschriebenen Form.** Der Preis, den du dafür nennst — die
Variante liest den Arbeitsstand statt des sauberen Kontextes — ist vermeidbar.

## Aufgabe 1 — Prüfe zuerst diese dritte Möglichkeit

Trenne **Verfälschung** und **Kohärenzpflege** zeitlich, statt den Kontext der Variante zu
ändern:

- Die Varianten bleiben, wie sie sind: Sie skalieren das Beitragstupel gegen den **sauberen**
  Kontext, jede Anwendung unabhängig. Der dokumentierte Invariant bleibt bestehen, keine
  Variante bekommt eine zweite Datenquelle.
- Die Rangfolge wird **nicht mehr je Anwendung** nachgezogen, sondern **einmal am Ende des
  Laufs** über alle betroffenen Anfragen, gegen den dann vorliegenden Endstand.

Das ist sachlich die richtige Einordnung: Das Nachziehen des Rangs ist keine Verfälschung,
sondern Kohärenzpflege — deshalb sind diese Zellen ja als `mitgezogen` markiert und nicht
Teil von `E`. Ein Nachbearbeitungsschritt ist der Ort, an den sie gehören.

Drei Eigenschaften, die dabei besser werden als bei (a):

1. Jede Rangzelle wird **genau einmal** geschrieben. Keine Mehrfachschreibungen, keine
   Sonderbehandlung im Kollisionsset.
2. Die Endrangfolge ist eine **reine Funktion des Endzustands** und hängt nicht mehr von der
   Reihenfolge der Injektionen ab. Bei (a) hinge sie daran. Für A2 ist das die stärkere
   Eigenschaft, und sie lässt sich in einem Satz erklären.
3. Universum und Kandidatenmenge bleiben unangetastet, UV2 bleibt sauber.

Findest du beim Umsetzen einen Grund, warum das am vorhandenen Aufbau nicht geht — ich
sehe den Code nicht —, dann gilt (a), und der Wegfall des Invariants wird im Iterationslog
mit Begründung festgehalten. Melde das dann, statt umzuschwenken und es nur zu erwähnen.

## Aufgabe 2 — Die Falle dabei

**Der Nachbearbeitungsschritt darf nur Anfragen anfassen, in denen eine skalierende Variante
gewirkt hat** — F8-b bis F8-e und HO2-b, erkennbar am `error_log`.

Er darf **nicht** über alle Anfragen laufen. F6-b vergibt den Rang beim Duplizieren
absichtlich so, dass die Rangfolge eine Lücke bekommt; das ist die Verfälschung selbst und
muss stehen bleiben. Ein pauschaler Reparaturlauf würde sie stillschweigend beheben, und
F6-b wäre danach über R-043 nicht mehr auffindbar — ein deutlich schlimmerer Fehler als der,
den wir gerade beheben.

Schreibe dafür einen Test: Nach dem Kohärenzschritt ist die Rangfolge in einem F6-b-Lauf
weiterhin verletzt.

## Aufgabe 3 — Neu erzeugen und gegenprüfen

Phase-4-Artefakte für die betroffenen Klassen neu erzeugen, Gegencheck erneut fahren.
Regressionsprüfung mit klarer Erwartung:

- R-044-Treffer auf HO2: **null**, und zwar auf **allen** vier geprüften Ratenstufen. Nicht
  nur bei 0,02 — die Ratenabhängigkeit war der eigentliche Befund.
- HO2-Recall: 0,000 statt 0,0022 / 0,0041 / 0,0097.
- F8 unverändert in der Größenordnung; falls nicht, melde die Abweichung, statt sie
  wegzuerklären.

Dokumentiere die Korrektur in `docs/iteration_log.md` mit Ursache, gewählter Lösung und
den verworfenen Alternativen samt ihrer Kosten. Regelkatalog unberührt.

## Aufgabe 4 — Das ist ein Ergebnis, nicht nur ein Bugfix

Halte den Befund so fest, dass er in die Arbeit übernommen werden kann:

> Wird Kohärenz je Verfälschung gegen den unverfälschten Ausgangszustand hergestellt, ist
> sie bei mehrfacher Anwendung innerhalb derselben Bezugsgruppe nicht mehr gewährleistet.
> Die Verletzung entsteht nicht in der einzelnen Verfälschung, sondern in ihrer
> Überlagerung, und wächst überproportional mit der Fehlerrate.

Das betrifft jeden Fehlerinjektor, der relationale Nebenbedingungen bedienen muss — die
Arbeit kann das gegen BART und Jenga stellen. Es gehört zu den Punkten, an denen der
Prototyp etwas über das Verfahren zeigt und nicht nur über den Katalog. Für die
Limitationen ist es außerdem der bessere Beleg als eine allgemeine Bemerkung: Der Fehler
wurde durch die eigene Messung gefunden, nicht durch Nachdenken.

## Abnahme

1. Kohärenzschritt nachgelagert umgesetzt — oder begründet auf (a) ausgewichen.
2. F6-b bleibt verletzt, per Test abgesichert.
3. R-044 auf HO2 null über alle Ratenstufen, HO2-Recall 0,000.
4. Gegencheck sauber, `pytest`, `ruff`, `mypy` grün, committet und gepusht.
5. Befund als Ergebnis formuliert im Iterationslog.

Danach ist Phase 6 dran.
