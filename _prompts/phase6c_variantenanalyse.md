# Phase 6c — Die Variantenanalyse schärfen, ohne umzuetikettieren

> Letzter Nachtrag zur Programmarbeit. Im selben Chat.

---

Ihre 45 von 60 sind belastbarer als meine geschätzten 56, und die Aufschlüsselung nach
Richtung ist wichtiger als die Quote. Vier Festlegungen dazu — die dritte bringt eine
Auswertung, die ohne einen einzigen neuen Lauf auskommt.

## Aufgabe 1 — Die Vorab-Zuordnung bleibt die Hauptauswertung

**Der Kontrast 0,918 zu 0,499 wird nicht neu gerechnet.** Er beruht auf der Spalte
„spiegelt Regel exakt" aus `spec/03`, und die stand fest, bevor irgendetwas gemessen wurde.
Genau das ist ihr Wert. Eine nachträglich korrigierte Einteilung, aus der ein größerer
Kontrast folgt, wäre an die Daten angepasst — und damit wertlos als Beleg gegen den
Zirkularitätsvorwurf, dem sie dienen soll.

Falls du eine Fassung mit korrigierter Einteilung rechnest: ausschließlich als
**ausdrücklich als post hoc gekennzeichnete Sensitivitätsrechnung** im Anhang, nie als
Hauptzahl und nie in Abbildung 5.

## Aufgabe 2 — Die Richtung der Abweichungen ausdrücklich benennen

Elf Unterschätzungen gegen vier Überschätzungen heißt: Die falsch eingeordneten Varianten
liegen überwiegend in der **unteren** Gruppe und werden dort besser erkannt, als die
Einteilung erwartet hat. Sie ziehen den Mittelwert der unteren Gruppe nach oben und
**verkleinern** den gemessenen Abstand.

Daraus folgt ein Satz, der in die Ergebnisdarstellung gehört:

> Der gemessene Kontrast von 0,918 zu 0,499 ist konservativ. Die Abweichungen zwischen
> Vorab-Einteilung und Messung wirken überwiegend in Richtung eines kleineren Unterschieds;
> bei zutreffender Einteilung fiele er größer aus.

Eine Hauptzahl, die als Untergrenze ausgewiesen ist, ist im Kolloquium eine deutlich
stärkere Position als eine, die verteidigt werden muss.

## Aufgabe 3 — Die dritte Kategorie, die schon in den Daten liegt

Die Einteilung „spiegelt die Regelbedingung / spiegelt sie nicht" ist binär, das Ergebnis
aber dreiwertig. Die Kreuztabelle `regel_id` × Variante enthält bereits, **welche** Regel
tatsächlich getroffen hat. Werte sie so aus:

| Kategorie | Bedeutung |
|---|---|
| **A** | erkannt durch die Regel, die `spec/03` der Variante zuordnet |
| **B** | erkannt, aber durch eine **andere** Regel |
| **C** | nicht erkannt |

Das ist keine Umetikettierung, sondern eine Messung — die Regel-ID steht im Ergebnis, sie
wird nicht neu vergeben.

Und Kategorie B ist inhaltlich der stärkste Einzelbefund, den die Arbeit machen kann: Eine
Variante, die von einer Regel gefangen wird, die **nicht** gegen sie entworfen wurde, ist
das Gegenteil von Zirkularität. Dein R-049-Beispiel zeigt dieselbe Logik von der anderen
Seite — die Regel schweigt korrekt, weil der Fremdschlüssel auflösbar bleibt.

Deine elf Unterschätzungen dürften überwiegend in B fallen: Sentinelwerte über R-025,
Fremdformate über die Typregeln. Wenn das so ist, hat der Katalog eine Deckung, die über
seine eigene Herleitung hinausreicht — ein Ergebnis über das Verhältnis von Regelkatalog
und Taxonomie, nicht bloß eine Korrektur an `spec/03`.

Ausgabe: eine Spalte `trefferkategorie` in `t4_varianten.csv`, die Verteilung A/B/C je
Fehlerklasse in `README.md`, und Abbildung 5 mit drei statt zwei Gruppen — sofern das
lesbar bleibt, sonst als eigene kleine Abbildung daneben.

## Aufgabe 4 — Zwei Kleinigkeiten festhalten

`spearman` gibt bei konstanter Reihe `None` mit Begründung zurück statt einer Null. Das ist
richtig und der Grund gehört in den Docstring, falls er dort noch nicht steht: Eine Null
liest sich als „gemessen, kein Zusammenhang", und das ist eine andere Aussage als „nicht
messbar". Dieselbe Unterscheidung trägt die Precision-Behandlung bei B0.

Der T4-Kennungskonflikt, der zwei von drei Blöcken überschrieben hat, ist im Iterationslog
zu vermerken — mit dem Hinweis, **wodurch** er aufgefallen ist: durch die Forderung, die
Laufzahl mit Herleitung aufzuschreiben. Eine Transparenzanforderung, die einen stillen
Datenverlust findet, ist selbst ein kleines Ergebnis über die Arbeitsweise.

## Abnahme

1. Hauptkontrast unverändert auf Basis der Vorab-Einteilung.
2. Konservativitätsaussage in der Ergebnisdarstellung.
3. Kategorien A/B/C aus der Kreuztabelle abgeleitet, in `t4` und `README.md`.
4. Beide Kleinigkeiten dokumentiert. Committet und gepusht.

Danach ist die Programmarbeit abgeschlossen.
