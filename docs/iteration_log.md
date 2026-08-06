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

### Vorbemerkung zu R-053 — Korrektur **vor** dem Freeze

Diese Änderung ist **keine Iteration 2**. Sie fand vor dem Freeze statt, gehört also
noch zur Ausgangsfassung. Sie wird hier trotzdem festgehalten, weil sie eine
Modellannahme betrifft, die in der Arbeit begründet werden muss.

**Was falsch war.** Die ursprüngliche Fassung von R-053 lautete: „`zahlbeitrag_rate_eur`
liegt je Sparte im plausiblen Korridor (Kfz: 40 – 6.000 €/Jahr …)". Das ist in sich
widersprüchlich — `zahlbeitrag_rate_eur` ist die **Rate**, bei monatlicher Zahlweise also
ein Zwölftel des Jahresbeitrags. Sie läge systematisch unterhalb eines Jahreskorridors.

**Was geändert wurde.** R-053 prüft jetzt `bruttobeitrag_jahr_eur`.

**Folge für den Generator (Phase 2).** Zwei Kompromisse, die nur aus dem
Spezifikationsfehler folgten, wurden zurückgebaut:

- Die Zahlweise war an die Beitragshöhe gekoppelt, damit die Rate im Korridor blieb. Das
  war eine künstliche Abhängigkeit im Datensatz, deren Ursache später niemand mehr gekannt
  hätte. Sie wird jetzt frei gezogen.
- Der Nettobeitrag wurde an den Korridorgrenzen gekappt. Das verzerrte den oberen Rand der
  Verteilung: rund 2,4 Prozent der Vollkasko-Angebote lagen exakt auf demselben Wert. Es
  wird nicht mehr gekappt.

**Folge für den Schwellenwert.** Ohne Kappung überschreiten rund 0,5 Prozent der
Kfz-Angebote die alte Obergrenze von 6.000 €. Gemessen über fünf unabhängige Seeds mit je
10.000 Anfragen (zusammen über 300.000 Angebotszeilen):

| Sparte | Minimum | Median | p99 | Maximum über alle Seeds | über 6.000 € |
|---|---|---|---|---|---|
| 051 Kfz-HP | 73 € | 466 € | 3.224 € | 8.937 € | 0,05 % |
| 052 Vollkasko | 137 € | 983 € | 8.419 € | **20.665 €** | 2,39 % |
| 053 Teilkasko | 90 € | 334 € | 879 € | 1.198 € | 0 % |
| 130 Hausrat | 51 € | 241 € | 600 € | 1.235 € | 0 % |

Der Grund liegt in der Domäne, nicht im Generator: Ein Vollkaskovertrag in der Malusklasse
(Beitragssatz 245 %) auf einem Fahrzeug hoher Typklasse erreicht rechnerisch fünfstellige
Jahresbeiträge. Der Korridor war zu eng gewählt.

**Zwischenstand:** `schwellen.r053_korridor_kfz_eur` zunächst von `[40, 6000]` auf
`[40, 25000]`. Dieser Wert war jedoch nur die Folge eines unplausiblen Verteilungsrandes;
er wurde nach der Kalibrierung unten auf `[40, 13000]` korrigiert.

---

### Vorbemerkung zur Kalibrierung des Vollkasko-Randes

Ebenfalls **vor** dem Freeze, im selben Zug wie die R-053-Korrektur.

**Was unplausibel war.** Nach dem Rückbau der Kappung lag der 99. Perzentilwert der
Vollkasko bei 8.419 € Jahresbeitrag und das Maximum bei 20.264 €. Für eine private
Vollkasko ist das nicht plausibel.

**Der Eingriff — eine Annahmebedingung, kein Filter.** In den Sparten 052 (Vollkasko) und
053 (Teilkasko) erhalten Risiken mit `sf_klasse_hp` ∈ {`M`, `S`} kein Angebot. Versicherer
nehmen Malus- und Schadenklassen in der Kasko überwiegend gar nicht an. In der Haftpflicht
bleiben die Klassen erhalten — dort besteht Kontrahierungszwang nach § 5 PflVG, und die
Einstufung ist fachlich relevant.

Umgesetzt ist das als Annahmebedingung: Die betroffene Anfrage wird als
**Haftpflichtanfrage** geführt und bekommt entsprechend nur Haftpflichtangebote. Es
entstehen erst gar keine Kaskoangebote für diese Risiken.

**Eine Lücke im ersten Anlauf.** `sf_klasse_vk` wird aus der Haftpflichtklasse nach unten
gezogen und konnte dadurch selbst auf `M` oder `S` fallen — auch dann, wenn die
Haftpflichtklasse die Annahmebedingung erfüllte. Über diesen Umweg war der Beitragssatz von
245 Prozent weiter im Datensatz: Das Maximum sank zunächst nur von 20.264 € auf 17.051 €.
Die Kaskoklasse ist jetzt nach unten auf `0` begrenzt.

**Wirkung**, gemessen an denselben 10.000 Anfragen:

| Sparte | p99 vorher | p99 nachher | Maximum vorher | Maximum nachher |
|---|---|---|---|---|
| 051 Kfz-HP | 3.224 € | 3.820 € | 8.937 € | 8.937 € |
| 052 Vollkasko | **8.419 €** | **4.384 €** | **20.264 €** | **9.691 €** |
| 053 Teilkasko | 879 € | 884 € | 1.198 € | 1.202 € |
| 130 Hausrat | 600 € | 600 € | 1.188 € | 1.102 € |

Der p99 der Vollkasko fällt um 48 Prozent, das Maximum um 52 Prozent. Der p99 der
Haftpflicht steigt leicht, weil die umgehängten Malus-Risiken dort hinzukommen — fachlich
richtig, denn genau dort gehören sie hin.

**Nebenwirkung auf die Spartenanteile.** Gezogen wird weiterhin exakt nach Konfiguration;
die Annahmebedingung hängt danach rund 1,2 Prozent aller Anfragen von 052/053 auf 051 um.
Realisiert: 051 = 36,2 % (statt 35,0), 052 = 19,3 % (statt 20,0), 053 = 14,5 % (statt 15,0).
**Der Hausratanteil und die Kfz-Summe bleiben exakt** — die Verschiebung findet
ausschließlich innerhalb der Kfz-Sparten statt. In der Haftpflicht tragen dadurch 6,9 %
der Risiken eine Malus- oder Schadenklasse statt der gezogenen gut 3 %.

**Neuer Korridor.** Höchster beobachteter Jahresbeitrag über fünf unabhängige Seeds mit je
10.000 Anfragen: 9.691 €. Plus 30 Prozent Sicherheitsmarge = 12.598 €, glatt gerundet:

> `schwellen.r053_korridor_kfz_eur` von `[40, 25000]` auf **`[40, 13000]`**.
> Hausrat bleibt bei `[20, 2000]`.

Null Überschreitungen über alle fünf Seeds, in beide Richtungen.

---

### Der methodische Befund: Korridorbreite gegen Erkennungsschwelle

**Das ist kein Nebensatz, sondern ein quantifiziertes Ergebnis über C2-Regeln.**

R-053 zielt auf die Cent-statt-Euro-Verwechslung, also auf einen Faktor 100. Ein solcher
Fehler wird genau dann erkannt, wenn der verfälschte Wert die Obergrenze überschreitet —
die Erkennungsschwelle ist also *Obergrenze geteilt durch 100*. Die Breite des legitimen
Wertebereichs bestimmt damit unmittelbar, ab welchem Vertrag die Regel überhaupt greift:

| Obergrenze | Erkennungsschwelle | erfasste Kfz-Angebote |
|---|---|---|
| 6.000 € (ursprünglich) | 60 €/Jahr | 100,0 % |
| **13.000 € (jetzt)** | **130 €/Jahr** | **99,4 %** |
| 25.000 € (Zwischenstand) | 250 €/Jahr | 87,3 % |

Ohne die Kalibrierung hätte die Regel 12,7 Prozent der Kfz-Angebote nicht mehr abgedeckt —
nicht weil die Fehler dort schwerer zu finden wären, sondern allein weil der legitime
Wertebereich weiter gefasst werden musste. **Eine korridorbasierte Regel verliert
Trennschärfe genau in dem Maß, in dem der legitime Wertebereich breit ist.** Das gilt
unabhängig von diesem Datensatz und gehört in die Diskussion der Arbeit.

**Zwei Punkte, die ebenfalls in die Arbeit gehören:**

1. **Ein fester C2-Schwellenwert erzeugt am Rand des Wertebereichs zwangsläufig
   Fehlalarme.** Bei 6.000 € hätte R-053 vor der Kalibrierung 301 von 60.943 sauberen
   Angeboten gemeldet (0,49 %). Nach der Kalibrierung sind es bei 13.000 € null — der
   Schwellenwert passt jetzt zum Wertebereich, statt ihn zu beschneiden.
2. **Die Obergrenze 13.000 € ist empirisch bestimmt, nicht strukturell garantiert.** Das
   Beitragsmodell kann rechnerisch höhere Werte erreichen, wenn alle Faktoren gleichzeitig
   am Extrem liegen. In fünf Läufen mit zusammen über 300.000 Angebotszeilen lag das
   Maximum bei 9.691 €.

---

---

## Iteration 2 — Korrekturen nach dem Freeze

*Noch keine Einträge.*
