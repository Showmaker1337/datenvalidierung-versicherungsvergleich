# HYP4 mit der Wiederholungsstruktur — ART-ANOVA als Blockmodell

Nachrechnung ohne einen einzigen neuen Lauf: Dieselben Ergebnisse der Serie s01,
dasselbe Langformat, dieselbe Aligned-Rank-Transformation — nur das Modell auf den
Raengen bekommt den Term, der die Paarung abbildet.

Erzeugt aus `results/metrics_long.parquet` durch
`src.evaluation.blockmodell.schreibe_bericht`.

## Der Einwand

Die vorregistrierte Fassung rechnet `f1 ~ verfahren * fehlerklasse`. Prototyp und B2
werden aber auf **demselben** Injektionslauf ausgewertet — derselbe verfaelschte
Datensatz geht an beide. Die Beobachtungen sind gepaart; das Modell behandelt sie als
unabhaengig und laesst die gesamte Streuung zwischen den Laeufen im Fehlerterm stehen,
obwohl sie beide Verfahren gleichermassen trifft und den Vergleich gar nicht stoert.

## Was geaendert wurde und was nicht

| | vorregistriert | Blockmodell |
|---|---|---|
| Daten | Serie s01, Langformat | **unveraendert** |
| Ausrichtung | `y - zeilenmittel - spaltenmittel + gesamtmittel` | **unveraendert** |
| Rangbildung | ueber alle ausgerichteten Werte | **unveraendert** |
| Modell | `raenge ~ verfahren * fehlerklasse` | `raenge ~ verfahren * fehlerklasse + Error(block)` |
| Fehlerterm | Residuum ueber alle Beobachtungen | Residuum **innerhalb** der Bloecke |

Die Ausrichtung bleibt bewusst ohne Blockterm: Wobbrock et al. (2011) richten an den
festen Effekten des vollen faktoriellen Modells aus und ueberlassen den Blockterm der
Modellanpassung; die R-Umsetzung `ARTool` verfaehrt ebenso. Wuerde man den Block schon
in der Ausrichtung entfernen, waere der Fehlerterm doppelt bereinigt.

Der Block ist in der **Fehlerklasse geschachtelt** und nicht mit ihr gekreuzt: Ein
Injektionslauf traegt genau eine Klasse, und `seed_inject` geht aus Serie, Design,
Klasse, Rate und Wiederholung hervor — `F1|w07` und `F3|w07` sind verschiedene
Verfaelschungen und keine Wiederholung derselben Bedingung. Es entsteht damit ein
Split-Plot-Aufbau: Klasse zwischen den Bloecken, Verfahren innerhalb. Bei balanciertem
Aufbau — und die Balanciertheit wird erzwungen, nicht unterstellt — ist der F-Test des
Interaktionsterms identisch mit dem des gemischten Modells
`raenge ~ verfahren * fehlerklasse + (1 | block)`.

## Ergebnis

| Ebene | Modell | F | df1 | df2 | p | partielles Eta-Quadrat | N | Bloecke | Blockanteil am Fehlerterm |
|---|---|---|---|---|---|---|---|---|---|
| satzebene | vorregistriert, ohne Blockterm | 5776,75 | 6 | 266 | 1,66e-278 | 0,9924 | 280 | — | — |
| satzebene | Blockmodell, wiederholung | 6080,84 | 6 | 133 | 1,29e-159 | 0,9964 | 280 | 140 | 52,5% |
| satzebene | Blockmodell, lauf | 2534,51 | 6 | 553 | < 1e-308 (Unterlauf) | 0,9649 | 1120 | 560 | 56,2% |
| zellebene | vorregistriert, ohne Blockterm | 1590,03 | 6 | 266 | 3,74e-205 | 0,9729 | 280 | — | — |
| zellebene | Blockmodell, wiederholung | 1798,21 | 6 | 133 | 1,1e-124 | 0,9878 | 280 | 140 | 55,8% |
| zellebene | Blockmodell, lauf | 2363,11 | 6 | 553 | < 1e-308 (Unterlauf) | 0,9625 | 1120 | 560 | 58,2% |

Die Blockdefinitionen im Klartext:

- **wiederholung** — Block = (Fehlerklasse, Wiederholung), Antwort ueber die vier Ratenstufen gemittelt
- **lauf** — Block = einzelner Injektionslauf (run_id), keine Vorabmittelung

### Die Rechnung ist nachgerechnet

Bei genau zwei Stufen des Innerhalb-Faktors — Prototyp gegen B2 — ist der
Split-Plot-F-Test des Interaktionsterms rechnerisch identisch mit einer
**Einweg-Varianzanalyse der Rangdifferenzen je Block**: Man bildet je Block
`d = Rang(Prototyp) - Rang(B2)` und vergleicht die Gruppenmittel von `d` ueber die
sieben Fehlerklassen. Der Weg ist ein voellig anderer, das Ergebnis muss dasselbe
sein. Diese Gegenprobe (`src.evaluation.blockmodell.gegenprobe`) bildet Ausrichtung
und Raenge eigenstaendig nach und beruehrt `src.evaluation.statistik` nicht — ein
gemeinsamer Rechenweg wuerde einen gemeinsamen Fehler nicht aufdecken.

| Ebene | Modell | F (Quadratsummen) | F (Gegenprobe) | relative Abweichung |
|---|---|---|---|---|
| satzebene | wiederholung | 6080,8361073286 | 6080,8361073284 | 2.89e-14 |
| satzebene | lauf | 2534,5142292399 | 2534,5142292399 | 4.66e-15 |
| zellebene | wiederholung | 1798,2079954159 | 1798,2079954159 | 4.17e-15 |
| zellebene | lauf | 2363,1060627813 | 2363,1060627813 | 1.35e-15 |

## Aendert sich die inhaltliche Aussage?

**Nein.** Der Interaktionsterm ist in jedem der vier Modelle auf dem Niveau
alpha = 0,05 signifikant, auf beiden Metrikebenen und
unter beiden Blockdefinitionen. Die Aussage von HYP4 — der Abstand zwischen
Prototyp und B2 haengt von der Fehlerklasse ab — traegt mit Blockterm genauso wie
ohne. Auch die Entscheidung bleibt: Sie lautet weiterhin
**teilweise gestuetzt**, denn sie haengt nicht am Omnibustest allein,
sondern zusaetzlich an der Richtung, und die Richtungsaussage entscheidet sich in
den klassenweisen Vergleichen.

Der Einwand war trotzdem berechtigt. Er betrifft die **Genauigkeit der Angabe**,
nicht das Ergebnis: Freiheitsgrade und Fehlerterm des bisherigen Modells waren zu
gross, und ein Gutachter kann das nicht wissen, solange die Zahl nicht daneben
steht. Jetzt steht sie daneben.

### Warum sich am F-Wert so wenig aendert

Der Blockterm bindet rund die Haelfte des Fehlerterms, den ein Modell ohne ihn haette
(genaue Anteile im Hinweis je Test) — und er kostet zugleich rund die Haelfte der
Fehlerfreiheitsgrade. Beides hebt sich im mittleren Quadrat des Nenners fast auf, und
deshalb steigt der F-Wert nur um wenige Prozent, statt sich zu vervielfachen.

An der **Gesamt**quadratsumme der Raenge macht der Blockterm dagegen nur wenige
Prozent aus. Das ist kein Widerspruch, sondern die Folge eines sehr grossen
Interaktionseffekts: Wenn ein Term neunundneunzig Prozent der Streuung erklaert,
bleibt fuer alles uebrige zusammen wenig Raum. Die aussagekraeftige Bezugsgroesse ist
deshalb der Fehlerterm und nicht die Gesamtsumme — der Hinweis je Test weist sie so
aus.

Unter der Blockdefinition `lauf` faellt der F-Wert dagegen, weil dort eine **andere
Antwortgroesse** eingeht: der F1-Wert je einzelnem Lauf statt sein Mittel ueber die
vier Ratenstufen. Die Mittelung glaettet, der Einzelwert nicht. Beide Zahlen
beantworten dieselbe Frage mit verschiedener Aufloesung; keine ist die Korrektur der
anderen.

Praktisch heisst das: Der Einwand trifft eine Angabe, die in diesem Datensatz
**robust** ist. Bei einem kleineren Effekt oder mehr Streuung zwischen den Laeufen
koennte derselbe Fehler das Ergebnis kippen; hier tut er es nicht. Das ist ein
Ergebnis ueber diesen Datensatz und kein Freibrief fuer das falsche Modell.

## Konsistenz mit den klassenweisen Vergleichen

Die gepaarten Wilcoxon-Tests je Fehlerklasse und ihre Holm-Korrektur bleiben
**unveraendert**. Sie sind von dem Einwand gar nicht betroffen: Ein gepaarter Test
rechnet die Paarung bereits ein, indem er auf den Differenzen je Wiederholung
arbeitet. Geprueft wird hier nur, ob ihr Bild zum neuen Omnibustest passt.

| Familie | Familiengroesse (Holm) | berichtet | signifikant | Prototyp vorn | B2 vorn | Effekt min | Effekt max |
|---|---|---|---|---|---|---|---|
| HYP4-paarweise-Satz | 7 | 7 | 7 | 7 (F1, F2, F3, F4, F5, F7, F8) | 0 (—) | 1,000 | 1,000 |
| HYP4-paarweise-Zelle | 7 | 7 | 7 | 7 (F1, F2, F3, F4, F5, F7, F8) | 0 (—) | 1,000 | 1,000 |

**Die Rang-biseriale Korrelation ist in jeder Klasse gesaettigt (1,000).** Der
Prototyp gewinnt in allen zwanzig Wiederholungen jeder Klasse; mehr kann das
Effektmass eines Vorzeichen-Rangtests nicht anzeigen. Es misst die
Richtungskonsistenz, nicht die **Groesse** des Abstands — und genau die Groesse ist
der Gegenstand der Interaktionshypothese. Die paarweisen Tests koennen die
Interaktion deshalb weder bestaetigen noch widerlegen; sie koennten ihr nur
widersprechen, und das tun sie nicht.

Wo der Abstand tatsaechlich variiert, zeigt das Mittel der gepaarten Differenz
`F1(Prototyp) - F1(B2)` je Klasse:

| Ebene | F1 | F2 | F3 | F4 | F5 | F7 | F8 | Spannweite |
|---|---|---|---|---|---|---|---|---|
| satzebene | 0,155 | 0,834 | 0,875 | 0,923 | 0,785 | 0,717 | 0,168 | 0,768 |
| zellebene | 0,450 | 0,883 | 0,658 | 0,451 | 0,542 | 0,502 | 0,388 | 0,495 |

Der Abstand schwankt ueber die Klassen um ein Vielfaches, waehrend sein Vorzeichen
nie wechselt. Das ist genau das Bild, das ein signifikanter Interaktionsterm bei
durchweg gleichgerichteten Einzelvergleichen erzeugt — beides zusammen ist die
Aussage von HYP4: Die Interaktion ist belegt, die Richtungsaussage 'statistisch
gewinnt bei Ausreissern' ist es nicht.

## Was diese Rechnung nicht ist

Sie ersetzt die vorregistrierte Fassung **nicht**. `src/evaluation/hypothesen.py` und
`results/hypothesen.json` bleiben unveraendert; die Zahlen dort sind weiterhin die
der Voranmeldung. Eine nachtraeglich ersetzte Zahl nimmt dem Leser die Moeglichkeit,
den Unterschied zu pruefen — und der Unterschied ist hier die eigentliche Auskunft.
