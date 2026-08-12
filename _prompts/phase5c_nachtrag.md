# Phase 5c — Die elf R-044-Fälle klären, bevor Phase 6 rechnet

> Im selben Chat. Kopiere alles ab der Trennlinie.

---

Du hattest recht und ich unrecht: Ausdrückbarkeit ist frameworkabhängig, cuallee 4 von 7
gegen GE 6 von 7 auf denselben Regeln. Ich hatte „ähnlich begrenzt" behauptet, ohne es zu
messen — du hast es gemessen. Deine Ersatzformulierung über den strukturellen Kern in
G3–G5 ist die richtige. Aufgabe 4 macht sie belastbar.

Zuerst aber die offene Frage, die du gestellt hast.

## Aufgabe 1 — Die elf Fälle diagnostizieren, noch nichts ändern

Richtig, dass du den Injektor nicht angefasst hast. Ändere weiterhin nichts, bevor
feststeht, **warum** in 11 von 1.217 skalierten Angeboten die Rangfolge verletzt bleibt.
Prüfe die drei plausiblen Ursachen an genau diesen 11 Fällen:

1. **Falsches Sortierfeld.** R-044 prüft die Ordnung nach `zahlbeitrag_rate_eur`. Sortiert
   der Injektor nach `bruttobeitrag_jahr_eur` um, sind das zwei verschiedene Ordnungen,
   sobald Angebote derselben Anfrage unterschiedliche `zahlweise` haben — die Rate ist
   Brutto mal Ratenzuschlag geteilt durch Ratenanzahl. Das ist der wahrscheinlichste
   Kandidat, weil er genau in seltenen Konstellationen zuschlägt.
2. **Gleichstand.** Fallen nach der Skalierung zwei Raten auf denselben Cent, ist die
   Rangzuweisung nicht eindeutig, und eine strikt aufsteigende Prüfung schlägt an.
3. **Rundung.** `ROUND_HALF_UP` auf zwei Nachkommastellen kann bei nahe beieinander
   liegenden Angeboten eine Inversion um einen Cent erzeugen.

Berichte, welcher Fall vorliegt, mit Beispielzeilen.

## Aufgabe 2 — Die Entscheidungsregel steht vorher fest

Damit die Entscheidung nicht vom Ergebnis abhängt, hier vorab:

**Ursache 1 (falsches Sortierfeld) ⇒ Fehler, wird korrigiert.** Dann weicht die
Implementierung von ihrer eigenen Spezifikation ab; `spec/03` verlangt das Mitziehen der
Rangfolge ausdrücklich. Eine Implementierung an ihre Spezifikation anzugleichen ist keine
ergebnisgetriebene Änderung, auch wenn sie jetzt auffällt. Die Phase-4-Artefakte werden neu
erzeugt, der Gegencheck erneut gefahren, die Korrektur in `docs/iteration_log.md`
dokumentiert. Das kostet Rechenzeit, aber es passiert **vor** 1.680 Läufen und nicht danach.

**Ursache 2 oder 3 (Gleichstand, Rundung) ⇒ kein Fehler, wird dokumentiert.** Dann ist das
Versprechen aus `spec/03` in 99,1 Prozent der Fälle einlösbar und im Rest nicht, weil
kohärente Skalierung Preiskollisionen nicht verhindern kann. Der Injektor bleibt
unverändert, und der Befund gehört in die Diskussion: Selbst eine bewusst unauffällig
gebaute Verfälschung hinterlässt in seltenen Konstellationen eine Spur.

In beiden Fällen bleibt der Regelkatalog unberührt.

## Aufgabe 3 — Prüfen, ob der Effekt mit der Fehlerrate wächst

Unabhängig von der Ursache: Zähle die R-044-Treffer auf HO2 bei mindestens drei
Ratenstufen. Wächst ihr **Anteil** an den skalierten Angeboten mit der Rate, hat die
Held-out-Klasse HO2 einen steigenden Recall über UV2 — und zwar nicht, weil der Katalog
besser würde, sondern weil mehr Skalierungen mehr Ordnungskollisionen erzeugen. Das wäre
dieselbe Sorte Artefakt wie die Mischungsverschiebung aus Phase 4b, nur kleiner.

Bleibt der Anteil konstant, ist es ein Niveau-Effekt und harmlos. Halte das Ergebnis so
oder so fest — es ist die Grundlage dafür, wie HO2 in der Arbeit interpretiert wird.

## Aufgabe 4 — Den strukturellen Kern messen statt behaupten

Deine Formulierung — der frameworkübergreifende Kern sind die relationalen (R-043 bis
R-048, R-052, R-054), die quellenübergreifenden (R-049 bis R-051, R-055 bis R-058) und das
algorithmische R-004, zusammen 16 von 58 allein in G3–G5 — trägt die Begründung des
Artefakts. Genau deshalb sollte sie nicht auf einem Formarguments stehen bleiben.

Setze **zwei bis drei** Regeln aus G3–G5 in beiden Frameworks an: eine relationale mit
Gruppenbezug (R-054 gegen den Median der übrigen Angebote einer Anfrage), eine
satzübergreifende (R-046) und, wenn es schnell geht, R-004. Miss, ob und wie sie sich
ausdrücken lassen.

Erwartung: Beide scheitern, weil das Prüfmodell zeilen- und spaltenweise Prädikate über
**eine** Tabelle kennt, aber keine Gruppierung mit Rückbezug auf die Gruppe. Bestätigt sich
das, ist die zentrale Aussage der Arbeit ein Messergebnis und keine Plausibilität. Fällt es
anders aus, willst du das ebenfalls wissen — dann verschiebt sich die Begründung, aber sie
verschiebt sich rechtzeitig.

## Aufgabe 5 — Zwei Aufräumpunkte

**Great Expectations gehört nicht in `requirements.txt`.** 17 transitive Abhängigkeiten für
einen Vergleich, der nicht in die Inferenzstatistik eingeht, verwässern das
Reproduzierbarkeitspaket des eigentlichen Experiments. Zieh GE in eine eigene
`requirements-vergleich.txt` und vermerke in `README.md`, dass der Frameworkvergleich
separat installiert wird. A2 verlangt gepinnte Versionen für die Läufe — die bleiben davon
unberührt und werden schlanker.

**In den Metriken zwei Dinge auseinanderhalten.** Ein Treffer auf einer Zelle, die der
Injektor verfälscht hat, ist per Definition ein True Positive — auch wenn die auslösende
Regel gar nicht auf diese Fehlerart zielt, wie R-044 bei HO2. Schreibe in die
Metrikdokumentation einen Satz, der „der Fehler wurde erkannt" von „eine Nebenwirkung der
Verfälschung wurde erkannt" trennt, und verweise auf die Kreuztabelle `regel_id` ×
`fehlerklasse` als Beleg: Dass bei HO2 ausschließlich R-044 auftaucht, ist selbst die
Diagnose.

## Abnahme

1. Ursache der 11 Fälle benannt, mit Beispielen.
2. Nach der vorab festgelegten Regel gehandelt — korrigiert oder dokumentiert.
3. Ratenabhängigkeit des Effekts gemessen und festgehalten.
4. Zwei bis drei G3–G5-Regeln in beiden Frameworks geprüft, Ergebnis in der
   Vergleichstabelle.
5. GE aus `requirements.txt` heraus.
6. Trennung „Fehler erkannt" / „Nebenwirkung erkannt" dokumentiert.

Halte an und berichte. Danach ist der Stand bereit für Phase 6.
