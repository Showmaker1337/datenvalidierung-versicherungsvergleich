# Befunde aus der Entwicklung, die in die Ergebnisdarstellung gehoeren

Quelle: `docs/iteration_log.md`. Diese Datei stellt die vier Befunde zusammen,
die nicht nur die Implementierung betreffen, sondern das **Ergebnis** — sie
gehoeren in die Diskussion und in die Limitationen.

## Befund 11 — die Ursache der elf Rangverstoesse war keine der drei erwarteten

Bei der Held-out-Klasse HO2 blieb in 11 von 1.217 skalierten Angeboten die
Rangfolge verletzt. Die drei naheliegenden Ursachen — falsches Sortierfeld,
Gleichstand, Rundung — schieden je an einem Messwert aus. Die tatsaechliche
Ursache war eine vierte: **Interferenz zwischen zwei Anwendungen derselben
Variante innerhalb einer Anfrage**. Alle 11 betroffenen Anfragen hatten mehr als
ein skaliertes Angebot; von den 1.102 Anfragen mit genau einem war keine
einzige betroffen.

## Befund 12 — der Effekt wuchs mit der Fehlerrate

| Fehlerrate | skalierte Angebote | Anfragen mit >= 2 | R-044-Verstoesse | Anteil | HO2-Recall |
|---|---|---|---|---|---|
| 0,005 | 304 | 2 | 0 | 0,00 % | 0,00000 |
| 0,010 | 609 | 14 | 3 | 0,49 % | 0,00223 |
| 0,020 | 1.217 | 57 | 11 | 0,90 % | 0,00410 |
| 0,050 | 3.044 | 294 | 65 | 2,14 % | 0,00968 |

Der Anteil blieb nicht konstant, er wuchs — und mit ihm der gemessene Recall der
Held-out-Klasse. Ein Trendtest ueber die Ratenstufen haette damit einen
Confounder gemessen und keinen Sacheffekt.

## Befund 13 — der strukturelle Kern der Framework-Grenze, gemessen

Die Aussage, der frameworkuebergreifend belastbare Teil der Grenze seien die
relationalen, die quellenuebergreifenden und die algorithmischen Regeln, stand
bis Phase 5 auf einem Formargument. Sie ist gemessen: R-046 und R-054 sind in
**keinem** der beiden Frameworks ausdrueckbar. Keines der 57
Great-Expectations-Erwartungen und keines der cuallee-Praedikate traegt `Group`
oder `Partition` im Namen. Ein Pruefmodell aus zeilen- und spaltenweisen
Praedikaten ueber **eine** Tabelle kennt keine Gruppierung mit Rueckbezug auf die
Gruppe — genau das verlangen R-043 bis R-048, R-052 und R-054.

## Befund 14 — Kohaerenz gegen den Ausgangszustand haelt nicht unter Ueberlagerung

**Der eigentliche Ertrag, und er gehoert als Ergebnis in die Arbeit.**

> Wird Kohaerenz **je Verfaelschung** gegen den **unverfaelschten
> Ausgangszustand** hergestellt, ist sie bei mehrfacher Anwendung innerhalb
> derselben Bezugsgruppe nicht mehr gewaehrleistet. Die Verletzung entsteht nicht
> in der einzelnen Verfaelschung, sondern in ihrer **Ueberlagerung** — und sie
> waechst ueberproportional mit der Fehlerrate, weil die Zahl der mehrfach
> getroffenen Bezugsgruppen einem Geburtstagsproblem folgt.

**Warum das ueber diesen Prototyp hinausweist.** Der Befund betrifft jeden
Fehlerinjektor, der relationale Nebenbedingungen bedienen muss — also jeden, der
auf normalisierten Daten arbeitet. Er laesst sich gegen BART und Jenga stellen:
Beide erzeugen Verfaelschungen unter Nebenbedingungen und stehen vor derselben
Frage, sobald zwei Verfaelschungen dieselbe Bezugsgruppe treffen.

**Warum er in die Limitationen gehoert.** Der Fehler wurde durch die eigene
Messung gefunden, nicht durch Nachdenken. Er war in keiner der drei Hypothesen
enthalten, mit denen die Suche begann, und er waere ohne den Probelauf ueber
mehrere Ratenstufen erst in den Laeufen dieser Serie aufgefallen — als scheinbar
inhaltlicher Trend der Held-out-Klasse HO2 ueber Faktor UV2 (Fehlerrate,
Stufen 1,0%, 2,0%, 5,0%, 10,0%). **Dass er vorher gefunden wurde, ist Teil des Ergebnisses.**

**Die Loesung.** Die Rangfolge wird einmalig am Ende des Laufs gegen den
Endzustand nachgefuehrt, statt je Verfaelschung gegen den sauberen Stand. Damit
wird jede Rangzelle genau einmal geschrieben, die Endrangfolge ist eine reine
Funktion des Endzustands und haengt nicht mehr von der Reihenfolge der
Injektionen ab, und Universum wie Kandidatenmenge bleiben unberuehrt — die
Bezugsgroesse der Fehlerrate ist unangetastet, Faktor UV2 bleibt sauber.

Nach der Korrektur bleibt HO2 auf **allen** Ratenstufen unentdeckt, genau wie
konstruiert. Der scheinbare Trend ueber UV2 ist verschwunden, weil er nie einer
war.
