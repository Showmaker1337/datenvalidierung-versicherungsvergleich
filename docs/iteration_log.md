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

**Angepasst:** `schwellen.r053_korridor_kfz_eur` von `[40, 6000]` auf `[40, 25000]`.
Hausrat bleibt bei `[20, 2000]` — dort wird der Korridor nicht ausgereizt.

**Was das für die Regel bedeutet.** R-053 zielt auf die Cent-statt-Euro-Verwechslung, also
auf einen Faktor 100. Mit der Obergrenze 25.000 € wird ein solcher Fehler weiterhin bei
jedem Vertrag ab 250 € Jahresbeitrag erkannt — das sind rund drei Viertel der Kfz-Angebote
und fast alle Vollkaskoverträge. Die Verschiebung kostet Trennschärfe nur am unteren Rand.

**Zwei Punkte, die in der Arbeit gehören:**

1. **Ein fester C2-Schwellenwert erzeugt am Rand des Wertebereichs zwangsläufig
   Fehlalarme.** Die 0,5 Prozent oben sind der Beleg. Hier war der Rand teilweise künstlich
   (Kappung), der Befund gilt aber auch ohne sie: Bei 6.000 € hätte R-053 auf sauberen
   Daten 301 von 60.943 Angeboten gemeldet.
2. **Die Obergrenze 25.000 € ist empirisch bestimmt, nicht strukturell garantiert.** Das
   Beitragsmodell kann rechnerisch bis rund 38.700 € erreichen, wenn alle Faktoren
   gleichzeitig am Extrem liegen (Wahrscheinlichkeit ≈ 10⁻¹¹, in fünf Läufen nie
   beobachtet). Wer eine harte Garantie will, setzt die Grenze auf 40.000 € — um den Preis,
   dass R-053 dann erst ab 400 € Jahresbeitrag greift.

---

---

## Iteration 2 — Korrekturen nach dem Freeze

*Noch keine Einträge.*
