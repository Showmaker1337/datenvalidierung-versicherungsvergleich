# Phase 6b — Nachtrag: zwei fehlende Auswertungen, vier Klarstellungen

> Im selben Chat. Kopiere alles ab der Trennlinie.

---

Die Serie steht. Sechs Nachträge, davon zwei mit inhaltlicher Folge für die Hypothesen.

## Aufgabe 1 — Committen und pushen

Phase 6 unverändert committen und pushen, dieser Nachtrag als eigener Commit.

## Aufgabe 2 — HYP3 auf beiden Metrikebenen rechnen

`p = 3,6·10⁻¹⁷` bei `ρ = 0,069` ist ein hochsignifikanter, praktisch bedeutungsloser
Effekt. Die Erklärung steht schon in deinen eigenen Zahlen: Auf der Constraint-Ebene
erreichen F2, F3, F4 und F5 eine Precision von 1,000 bei unverändertem Recall. Wo die
Precision bereits eins ist, kann kein Prävalenzeffekt entstehen.

Damit liegt der Verdacht nahe, dass der gemessene Trend **kein Prävalenzeffekt des
Verfahrens ist, sondern ein Effekt der Berichtskonvention**: Auf der Zellebene erzeugt jede
Injektion über mehrspaltige Regeln zusätzliche Falschmeldungen, und deren Zahl wächst mit
der Injektionszahl — die Precision steigt deshalb kaum, obwohl sie es bei konstanten
Fehlalarmen deutlich müsste.

Rechne den Page-Trendtest **zusätzlich auf der Constraint-Precision** und stelle beide
Ergebnisse nebeneinander. Erwartung: Der Effekt verschwindet dort oder kehrt sich um. Trifft
das zu, ist HYP3 nicht „schwach gestützt", sondern präzise beantwortbar — der Prävalenzeffekt
existiert auf der Zellebene und ist dort ein Artefakt der Konvention. Das ist eine deutlich
stärkere Aussage als ein kleines ρ.

Ergänze `t2_fehlerraten.csv` und `results/hypothesen.md` um beide Sichten.

## Aufgabe 3 — HYP4 auf der Satzebene rechnen, das war die Vorgabe

Für B2 war die **Satzebene als Primärvergleich** festgelegt, die Zellebene nur zusätzlich
(Phase 5, Aufgabe 3). Dein Bericht führt B2 mit `F1 = 0,026` — das ist die Zellebene.

Der Grund für die Festlegung: B2 markiert ganze Zeilen, und die Umrechnung „markierte Zeile
markiert alle ihre befüllten Zellen" deckelt seine Precision auf etwa den Kehrwert der
Spaltenzahl. Ein Zellvergleich misst dort zu einem großen Teil die Umrechnung und nicht das
Verfahren.

Rechne HYP4 auf der Satzebene neu. Die Aussage „B2 gewinnt in keiner Klasse" ist erst dann
belastbar — und wenn sie sich bestätigt, ist sie **stärker** als jetzt, weil der Einwand
vorweggenommen ist. Gewinnt B2 auf der Satzebene in einzelnen Klassen, gehört das ebenso in
die Arbeit; dann trägt die Richtungsaussage von HYP4 teilweise doch.

Weise in beiden Fällen aus, dass B2 seine `contamination`-Stufe über den Ground Truth wählen
durfte. Ein Verfahren, das trotz dieses Vorteils verliert, verliert überzeugend.

## Aufgabe 4 — Die Familiengröße bei HYP1 an die Auswertung anpassen

Deine Entscheidung ist richtig: In den vier Klassen, in denen B0 nichts meldet, ist seine
Precision eine Konvention und keine Messung. Zieh die Konsequenz auch in der Korrektur.

- Die Precision-Vergleiche dieser vier Klassen sind **nicht durchgeführt**, nicht
  „durchgeführt und nicht signifikant". Weise sie als „nicht anwendbar" aus.
- Die Holm-Familie der Precision-Hälfte hat damit **drei** Vergleiche, nicht sieben. Rechne
  die korrigierten p-Werte mit der tatsächlichen Familiengröße und nenne sie in
  `hypothesen.md` ausdrücklich.

Die Entscheidung zu HYP1 ändert sich dadurch voraussichtlich nicht — die Korrektur wird
schwächer, nicht stärker. Aber eine Familiengröße, die nicht zur Zahl der berichteten Tests
passt, ist im Kolloquium eine sichere Frage.

## Aufgabe 5 — Die Laufzahl transparent aufschreiben

**Wichtig fürs Schreiben, kein Mangel.** Mein Prompt sprach von 1.680 Läufen, gelaufen sind
1.035. Das ist keine Reduktion, sondern eine andere Zählweise: Ein Injektionslauf wird von
allen drei Verfahren ausgewertet.

7 Klassen × 4 Raten × 20 Wiederholungen = **560 Injektionsläufe** im Hauptversuch, ausgewertet
mit drei Verfahren = 1.680 Verfahrensauswertungen. Dazu die Teilversuche T1 bis T6, zusammen
1.035 Läufe insgesamt.

Schreibe beide Zahlen mit ihrer Herleitung in `README.md` und in den Ergebnisteil. „1.035 von
1.680 geplanten Läufen" wäre eine verdeckte Stichprobenreduktion — genau das, was der
Versuchsplan ausschließen wollte, und es stünde als Vorwurf im Raum, obwohl nichts fehlt.

## Aufgabe 6 — Drei Zahlen schärfen

**Die vier stummen Regeln unterscheiden.** R-030, R-047, R-048 und R-049 haben nie gemeldet.
Prüfe je Regel, welcher der beiden Gründe vorliegt, und weise ihn in `t3_regeldiagnose.csv`
als eigene Spalte aus:

- **Keine Injektionsvariante zielt darauf** ⇒ Überdeckung. Der Katalog deckt mehr ab als die
  Fehlertaxonomie adressiert. Ein Befund über das Verhältnis von Katalog und Taxonomie.
- **Der Generator erzeugt keine Konstellation, in der die Regel greifen könnte** ⇒ die Regel
  ist in diesem Aufbau nicht prüfbar. Eine Limitation.

Das sind zwei verschiedene Aussagen, und nur die erste ist ein Ergebnis.

**Die Trefferquote der Vorab-Zuordnung beziffern.** `spec/03` notiert je Variante, ob sie
eine Regelbedingung spiegelt — festgelegt, bevor gemessen wurde. Du hast vier Abweichungen
gefunden: F1-a und F8-d überschätzt, F2-a und F2-k unterschätzt. Schreib die Quote als Zahl
hin (56 von 60, sofern es bei vier bleibt) und rahme sie als das, was sie ist: eine vorab
formulierte, falsifizierbare Erwartung, die überwiegend, aber nicht vollständig eingetroffen
ist. Das ist ein Gütezeichen der Methode, kein Makel der Spezifikation.

**HO1 klar benennen.** Auf der Satzebene 0,795 bei Precision 1,000, auf der Zellebene 0 —
und ausschließlich über R-046. Formuliere es unmissverständlich: Der Katalog erkennt den
Beinahe-Duplikat **nicht** an der Namensähnlichkeit, sondern an einer davon unabhängigen
Integritätsverletzung. HO1 ist als Held-out-Klasse für Ähnlichkeitserkennung damit
bestätigt, nicht widerlegt. Ohne diesen Satz liest sich 0,795 wie eine Generalisierung des
Katalogs, und das wäre die falsche Schlussfolgerung.

## Abnahme

1. Committet und gepusht.
2. HYP3 auf Zell- und Constraint-Ebene, beide in `hypothesen.md` und `t2`.
3. HYP4 auf der Satzebene gerechnet, Ergebnis mit dem Zellebenen-Ergebnis nebeneinander.
4. Holm-Familiengrößen passen zur Zahl der tatsächlich durchgeführten Tests.
5. Laufzahl mit Herleitung dokumentiert.
6. Stumme Regeln nach Grund unterschieden, Vorab-Trefferquote beziffert, HO1 eindeutig
   formuliert.

Kein Eingriff in Regelkatalog, Generator oder Injektor. Weichen Ergebnisse ab, sind sie
Befunde.
