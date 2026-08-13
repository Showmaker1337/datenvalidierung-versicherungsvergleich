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

- **Stand:** implementiert, Clean-Baseline-Lauf ohne Meldungen, **eingefroren**.
- **Tag:** `freeze-regelkatalog`, gesetzt am 2026-08-06.
- **Commit-Hash:** `30ca5ea429a0abddec7050af1d1a42cdf9942548`

Die vollständigen Freeze-Angaben stehen am Ende dieses Dokuments und maschinenlesbar in
`results/freeze.json`.

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

## Phase 3 — Präzisierungen bei der Implementierung des Katalogs

Alle folgenden Punkte fanden **vor** dem Freeze statt und gehören damit zur
Ausgangsfassung. Sie sind **keine Iteration 2**. Festgehalten werden sie trotzdem, weil
jeder von ihnen eine Modellannahme oder eine Auslegungsentscheidung betrifft, die in der
Arbeit begründet werden muss.

### R-057 — Anwendbarkeitsbedingung um den Familienstand erweitert

- **Datum:** 2026-08-06
- **Anlass:** Befund aus dem Clean-Baseline-Lauf. **Es war der einzige.**
- **Alte Fassung:** Die Anwendbarkeitsbedingung (`spec/01`, Abschnitt 5.2) war nur über die
  Sparte formuliert: `angebot.sb_tk_eur` nur in 052/053, `angebot.sb_vk_eur` nur in 052.
- **Neue Fassung:** Die Bedingung kennt zusätzlich einen zeilenbezogenen Ausschluss.
  `person.familienstand` wird bei `anrede` = FIRMA nicht geprüft.
- **Begründung:** Eine juristische Person hat keinen Familienstand; der Generator lässt das
  Feld dort planmäßig leer (`spec/01`, Abschnitt 3.2). Ohne den Ausschluss meldete R-057 bei
  10.000 Anfragen **135 Fehlalarme** — 196 Firmensätze, davon 135 unter einem Kanalprofil,
  das den Familienstand als Pflicht führt. Das ist kein fehlender Wert, sondern ein nicht
  existierender.
- **Auswirkung auf die Messung:** Die False-Positive-Rate von R-057 auf sauberen Daten fällt
  von 135 auf 0. Ohne die Korrektur wäre die Grundannahme „alles nicht Injizierte ist
  sauber" für dieses Feld verletzt gewesen.

### R-025 — der Leerstring bleibt außen vor

- **Datum:** 2026-08-06
- **Anlass:** Widerspruch zwischen `CLAUDE.md`, Abschnitt 5 und `spec/01`, Abschnitt 6.
- **Der Widerspruch:** `CLAUDE.md` führte den Leerstring als *Fehlerwert* und verlangte, dass
  R-025 ihn meldet. `spec/01`, Abschnitt 6 legt in der Tabelle „Zuordnung" dagegen fest:
  „Leerstring | regulär leer | kein Befund" — und genau so serialisiert
  `src/common/serialisierung.py` jeden leeren Wert.
- **Entscheidung:** Aufgelöst zugunsten von `spec/01`, Abschnitt 6. Die Sentinel-Liste für
  Textfelder auf der Rohschicht steht als `SENTINEL_TEXT_ROHSCHICHT` in
  `src/common/wertebereiche.py` und enthält den Leerstring nicht.
- **Begründung:** Auf der Rohschicht sind „leer" und „Leerstring" **nicht unterscheidbar**.
  Meldete R-025 den Leerstring, träfe es jedes planmäßig leere Feld — rund 30 Prozent aller
  optionalen Profilfelder. Der Clean-Baseline-Lauf hätte zehntausende Fehlalarme, die keine
  sind.
- **Stand der Spezifikation:** Erledigt. `CLAUDE.md`, Abschnitt 5 trägt die Auflösung; die
  Folge ist in `spec/03` an der Variante F1-b vermerkt.
- **Folge für die Auswertung, und die gehört in die Arbeit:** Die Injektionsvariante F1-b
  (Leerstring) ist damit **nur** über die Pflichtfeldregeln R-001 und R-057 erkennbar, nicht
  über R-025. Das ist **kein Implementierungsmangel, sondern ein Informationsverlust der
  Serialisierung** — genau das passiert an realen Schnittstellen, wenn ein Format zwischen
  „nicht belegt" und „leer geliefert" nicht unterscheidet. Der niedrige Recall dieser
  Variante ist damit vorhergesagt und begründet, nicht überraschend.

### R-025 — `row_id` ist von der Sentinel-Prüfung ausgenommen

- **Datum:** 2026-08-06
- **Begründung:** `row_id` ist eine fortlaufende technische Nummer und niemals Ziel einer
  Injektion (Architekturregel A3). Bei 62.826 Angebotszeilen kommt der Wert 9999 dort
  **planmäßig** vor. Die Ausnahme steht als `TECHNISCHE_SCHLUESSELFELDER` in
  `src/common/wertebereiche.py`, nicht als Literal im Regelcode.

### R-034 — Umsetzung über den Umkehrschluss aus dem Steuersatzkatalog

- **Datum:** 2026-08-06
- **Sachlage:** Die Regel verlangt `versicherungsteuer_eur` = 0 bei den nach § 4 VersStG
  steuerfreien Sparten (Leben, Kranken, BU, Rente, Pflege). Diese Sparten kommen im
  Datenmodell nicht vor, und ihre GDV-Spartenschlüssel sind im Projekt nirgends belegt.
- **Entscheidung:** Die Regel prüft jede Sparte, die **keinen Effektivsatz** im Katalog
  `VERSICHERUNGSTEUER_EFFEKTIVSATZ` hat. Damit werden keine Schlüssel erfunden, die im
  Modell nicht hinterlegt sind.
- **Kennzeichnung:** Im Metadatenfeld `fachliche_grundlage` und im Docstring als **im
  aktuellen Datenmodell nicht auslösbar** vermerkt. Der Testfall setzt eine steuerfreie
  Sparte ausdrücklich, damit die Regel trotzdem geprüft ist.

### R-032 — Toleranz aus R-031 übernommen

- **Datum:** 2026-08-06
- **Sachlage:** Der Katalog nennt die Toleranz von ±0,02 € nur bei R-031. Beide Regeln
  betreffen denselben Rundungsschritt.
- **Entscheidung:** R-032 verwendet `schwellen.r031_toleranz_eur`. Ein eigener
  Konfigurationsschlüssel wurde **nicht** angelegt — zwei Schwellen für denselben
  Rundungsschritt könnten auseinanderlaufen, ohne dass es auffiele.

### R-054 — mindestens zwei Vergleichsangebote

- **Datum:** 2026-08-06
- **Entscheidung:** Die Regel prüft ein Angebot nur, wenn die Anfrage **mindestens drei**
  bepreiste Angebote hat, der Median also aus mindestens zwei Werten gebildet wird.
- **Begründung:** Bei genau zwei bepreisten Angeboten ist der „Median der übrigen" das
  jeweils andere Angebot. Ein Faktor-12-Unterschied ließe dann beide Seiten füreinander wie
  der Fehler aussehen; die Regel müsste beide melden und käme bestenfalls auf eine Precision
  von 0,5.
- **Auswirkung auf die Messung:** Kostet Recall bei Anfragen mit zwei bepreisten Angeboten.
  Bei der Angebotsverteilung des Generators (Modus 5, Spanne 3 bis 12) betrifft das einen
  kleinen Teil der Anfragen; die Zahl ist in Phase 5 zu berichten.

### R-052 — Mehrheit als Bezugspunkt

- **Datum:** 2026-08-06
- **Entscheidung:** Gemeldet wird die Konvention, die innerhalb der Anfrage **in der
  Minderheit** ist. Bei Gleichstand werden alle beteiligten Angebote gemeldet.
- **Begründung:** Welche der beiden Einheitenkonventionen die richtige ist, sagt keine Norm.
  Die Mehrheit ist der einzige verfügbare Bezugspunkt. Diese Heuristik ist der Grund für die
  Einstufung C2 und den Schweregrad WARNUNG.

### R-043 — `n` bezieht sich auf die bepreisten Angebote

- **Datum:** 2026-08-06
- **Entscheidung:** Die Rangfolge umfasst genau die Angebote mit
  `annahmeentscheidung` ≠ ABLEHNUNG. Ein abgelehntes Angebot mit Rang ist ebenso ein
  Verstoß wie ein bepreistes ohne Rang.
- **Begründung:** Folgt der in Phase 2 getroffenen Festlegung (README, „Getroffene
  Festlegungen"): Ein abgelehntes Risiko hat keinen Preis und gehört in keine
  Preisrangfolge.

### R-009 — Abgrenzung auf Datumsfelder

- **Datum:** 2026-08-06
- **Entscheidung:** Geprüft werden die Felder vom Typ `DATUM` (Rohform `TTMMJJJJ`), nicht
  die beiden Zeitpunktfelder `eingangszeitpunkt` und `berechnungszeitpunkt` (ISO 8601).
- **Begründung:** Der Katalog spricht von „Datumsfeld". Ein Zeitpunkt ist im Datenmodell ein
  eigener Typ mit eigener Serialisierung; ihn mitzuprüfen würde die Regel verbreitern,
  ohne dass der Katalog es verlangt.

### Rückgabetyp von `pruefe` — zwei Kanäle statt eines Datenrahmens

- **Datum:** 2026-08-06
- **Abweichung von der Phasenvorgabe:** Der Phasenprompt sieht
  `pruefe: Callable[[Kontext], pd.DataFrame]` vor. Implementiert ist
  `Callable[[Kontext], Befund]` mit **zwei** Kanälen: `Befund.zellen` und `Befund.saetze`.
- **Begründung:** Ein einzelner Datenrahmen der Form
  `(entitaet, row_id, spalte, regel_id, verstoss_id, meldung)` kann den satzbezogenen Kanal
  nicht führen. Dort gibt es keine Spalte, und bei einem fehlenden Satz gibt es nicht einmal
  eine Zeile: R-046 kann bei null Versicherungsnehmern **keine Zelle benennen** — es
  existiert keine. Derselbe Fall ist im Ground Truth bereits vorgesehen
  (`spec/03`, Abschnitt 4.2, `error_log_records.parquet`).
- **Betroffene Regeln — das braucht der Evaluator in Phase 5:**

  | Regel | Zellkanal | Satzkanal | `in_zellmetrik` |
  |---|---|---|---|
  | R-043 Rangfolge | ja | ja, alle Angebote der Anfrage | ja |
  | R-045 Duplikate | ja | ja, alle Zeilen der Duplikatgruppe | ja |
  | R-046 genau ein VN | ja, wenn Sätze existieren | ja, auch bei null Treffern | ja |
  | R-047 Beitragsspreizung | **nein** | ja, alle bepreisten Angebote | **nein** |
  | R-048 ZÜRS-Verteilung | **nein** | ja, alle Zeilen der abweichenden Zone | **nein** |
  | R-055 Tarifstand | ja | ja, die betroffene Angebotszeile | ja |

  Alle übrigen 52 Regeln füllen ausschließlich den Zellkanal.
- **Die Berichtsform bleibt unverändert.** `Befund.als_rahmen()` erzeugt genau den im
  Phasenprompt beschriebenen Datenrahmen; er landet unverändert in `detections.parquet`. Der
  Satzkanal geht zusätzlich nach `detections_records.parquet` und ist damit das Gegenstück zu
  `error_log_records.parquet`.
- **Auswirkung auf die Messung:** Keine auf die Zellmetrik. Die satzbezogenen Befunde von
  R-047 und R-048 werden als eigene Diagnosekennzahl berichtet, die von R-043, R-045, R-046
  und R-055 zusätzlich zur Zellmetrik.

### Kennzahl der Achse C in `spec/02` — Rechenfehler in der Zusammenfassung

- **Datum:** 2026-08-06
- **Befund:** Die Tabelle „Kennzahlen des Katalogs" in `spec/02_regelkatalog.md` nennt
  C1 = 45, C2 = 11, C3 = 2. Ausgezählt über die Regeltabellen selbst ergibt sich
  **C1 = 44, C2 = 11, C3 = 3**. Drei Regeln tragen C3: R-050, R-051 und **R-058**.
- **Entscheidung:** Maßgeblich ist die Regeltabelle, nicht die Zusammenfassung. Die
  Implementierung folgt ihr; `results/regelkatalog.csv` weist die Verteilung 44 / 11 / 3
  aus.
- **Stand der Spezifikation:** Erledigt. Die Kennzahlentabelle in `spec/02` nennt jetzt
  C1 = 44, C2 = 11, C3 = 3 und führt die drei C3-Regeln namentlich auf.
- **Auswirkung:** Keine auf die Messung — nur auf die zitierte Kennzahl. Die Zahlen
  47 HART / 11 WARNUNG und die Gruppengrößen 25 / 17 / 6 / 3 / 7 stimmen mit der
  Implementierung überein und werden in `tests/test_katalog.py` festgehalten.

---

## Ergebnis des Clean-Baseline-Laufs

**Null Meldungen.** Der vollständige Katalog aus 58 Regeln läuft auf `df_clean` ohne einen
einzigen Befund — weder zellbezogen noch satzbezogen.

| Kennzahl | Wert |
|---|---|
| Regeln ausgeführt | 58 |
| Zellmeldungen | **0** |
| Satzbefunde | **0** |
| Markierte Zellen | **0** von 1.769.095 |
| False-Positive-Rate auf sauberen Daten | **0,0** |
| Laufzeit des Katalogs | rund 15 s (10.000 Anfragen, 62.826 Angebote) |

Gegengeprüft über **vier unabhängige Master-Seeds** (20260630, 11111, 424242, 987654) mit
je 10.000 Anfragen, zusammen rund 7,06 Millionen Zellen: in jedem Lauf null Meldungen.

Der Bericht steht in `results/clean_baseline.json`, die Laufzeiten je Regel in
`data/runs/<run_id>/clean/rule_timing.json`.

**Diese Kennzahl gehört in die Arbeit.** Sie ist der Beleg dafür, dass die Grundannahme
„alles nicht Injizierte ist sauber" trägt. Ohne sie wäre jede später berichtete Precision
unbelegt.

---

## Abschluss von Iteration 1 — der Freeze

Gesetzt am **2026-08-06**, nach grüner Testsuite, sauberer Typ- und Lintprüfung und einem
erneut ausgeführten Clean-Baseline-Lauf ohne Verstöße.

| Angabe | Wert |
|---|---|
| Tag | `freeze-regelkatalog` |
| **Commit-Hash** | **`30ca5ea429a0abddec7050af1d1a42cdf9942548`** |
| Tag-Objekt | `3f64827ce95801aec6df29d0d18232404c4af206` |
| Datum | 2026-08-06 |
| Regeln | 58 — G1 25, G2 17, G3 6, G4 3, G5 7; davon 47 HART und 11 WARNUNG |
| Clean-Baseline | 0 Zellmeldungen, 0 Satzbefunde, 0 markierte Zellen von 1.769.095 |
| Regeltestfälle | 163 (81 positiv, 82 negativ); Testsuite gesamt 593 |
| Remote | `https://github.com/Showmaker1337/Bachelorarbeit_Programm` |

**Zu zitieren ist der Commit-Hash, nicht das Tag-Objekt.** `git rev-parse freeze-regelkatalog`
gibt bei einem annotierten Tag die Hülle des Tag-Objekts zurück; den Codestand liefert
`git rev-parse freeze-regelkatalog^{commit}`. Beide Werte stehen oben, damit im Anhang der
Arbeit nicht der falsche landet.

### Was der Freeze umfasst — und was nicht

**Eingefroren sind die Regeln selbst.** Dazu gehören:

- die Prädikate — was eine Regel prüft,
- Wertebereiche und Schwellenwerte, einschließlich der **Regelschwellen** in
  `config/default.yaml`,
- die Geltungsbereiche, also welche Entitäten und Felder eine Regel betrifft,
- die Schweregrade `HART` und `WARNUNG`,
- die Zuordnung zu den Achsen A (Granularität), B (Fehlerklasse) und C (Erkennbarkeitsgrad).

### Die Grenze verläuft **innerhalb** von `config/default.yaml`

Die Datei enthält zweierlei, und nur das eine ist eingefroren:

| Eingefroren — **Regelschwellen** | Nicht eingefroren — **Versuchsparameter** |
|---|---|
| `schwellen.r031_toleranz_eur`, `schwellen.r036_toleranz_je_rate_eur` | `master_seed` |
| `schwellen.r053_korridor_kfz_eur`, `schwellen.r053_korridor_hausrat_eur` | `stichtag` |
| `schwellen.r022_wohnflaeche` | `n_anfragen`, `angebote_je_anfrage` |
| `schwellen.r047_spreizung_max`, `schwellen.r048_zuers_toleranz_relativ` | `sparten_verteilung` |
| `schwellen.r054_faktor`, `schwellen.r054_toleranz_relativ` | `pfade`, `referenzdaten` |
| — kurz: alles, was in ein Prädikat eingeht | Fehlerraten, Wiederholungszahl und alle übrigen Faktorstufen der Phase 6 |

**Die eigene Entscheidungsprobe trägt die Trennung.** Ändert sich durch die Änderung die
Menge der gemeldeten Zellen auf einem *gegebenen* Datensatz? Bei einer Regelschwelle: ja —
Iteration 2. Bei einer Faktorstufe: nein. Eine andere Fehlerrate oder ein anderer Seed
erzeugt einen *anderen Datensatz*; die Regeln prüfen auf jedem Datensatz unverändert
dasselbe.

Ohne diese Präzisierung liest jemand später „Schwellenwerte, einschließlich der Werte in
`config/default.yaml`, sind eingefroren" und hält Phase 6 — die Fehlerraten und
Wiederholungen variiert — für eine Serie von Regeländerungen. Der Satz stünde dann gegen den
Versuchsplan.

Jede Änderung daran ist ab jetzt eine **Iteration 2**: Regel-ID, alte Fassung, neue Fassung,
Begründung, Datum — und eine eigene Ergebnistabelle in der Auswertung. Niemals
stillschweigend.

**Nicht eingefroren sind die Belege daneben.** Dazu gehören:

- die Spalte „Literatur" im Katalog,
- die Spalte „Fachliche Grundlage" im Katalog,
- Formulierungen, Beispiele und Begründungstexte in `spec/`.

Diese Angaben dokumentieren die **Herleitung**, nicht die Prüfung. Sie dürfen jederzeit
korrigiert werden, solange sich das geprüfte Prädikat nicht ändert.

**Warum diese Unterscheidung nötig ist.** Der Freeze belegt, dass die Regeln vor dem
Fehlerinjektor feststanden. Er belegt **nicht**, dass jede Fußnote von Anfang an richtig war.
Die Literaturbelege des Katalogs werden noch geprüft; ohne diese Abgrenzung müsste jede
korrigierte Quellenangabe als Regeländerung deklariert werden — sachlich falsch und für die
Aussagekraft von Iteration 2 schädlich, weil echte Regeländerungen dann im Rauschen
verschwänden.

**Die Probe im Zweifelsfall:** Ändert sich durch die Korrektur die Menge der gemeldeten
Zellen auf irgendeinem Datensatz? Wenn ja, ist es eine Regeländerung und damit Iteration 2.
Wenn nein, ist es eine Korrektur am Beleg.

---

## Iteration 2 — Korrekturen nach dem Freeze

*Noch keine Einträge.*

---

## Phase 4 — Befunde beim Bau des Fehlerinjektors

**Keiner dieser Punkte ist eine Iteration 2.** Der Regelkatalog ist unverändert: kein
Prädikat, kein Wertebereich, kein Schwellenwert, kein Geltungsbereich, kein Schweregrad und
keine Achsenzuordnung wurde angefasst. Geändert wurden ausschließlich der Injektor,
`spec/03_fehlerklassen.md` (die Spezifikation des Injektors) und die Belegtexte.

Die Entscheidungsprobe aus dem Freeze: *Ändert sich durch die Korrektur die Menge der
gemeldeten Zellen auf irgendeinem Datensatz?* Für jeden Punkt unten lautet die Antwort
**nein** — die Regeln melden auf jedem Datensatz genau dasselbe wie vor Phase 4.

### Befund 1 — F5-d und F5-e sind als Senkung umzusetzen

- **Datum:** 2026-08-10
- **Sachlage:** `spec/03` ließ die Richtung offen („um 0,50 € / 0,01 € verändern"). Bei
  jährlicher Zahlweise ist die Ratenanzahl 1 und der Ratenzuschlag 0; auf sauberen Daten gilt
  dort `rate = brutto`, die Ungleichung von R-036 ist also **exakt ausgeschöpft**.
- **Folge einer Erhöhung:** F5-d verletzte zusätzlich R-036 und würde von zwei Regeln
  gemeldet — die Zuordnung Variante → Regel in der Ergebnistabelle wäre falsch. F5-e landete
  exakt auf der Grenze von R-036; eine „erwartet unentdeckte" Variante darf nicht auf einer
  Grenzgleichheit balancieren.
- **Entscheidung:** Beide Varianten senken den Bruttobeitrag. R-036 bekommt dadurch
  zusätzlichen Spielraum, R-031 entscheidet allein. Als Fehlerbild ist die Senkung ebenso
  realistisch wie die Erhöhung.
- **Auswirkung auf die Messung:** Keine auf die Regeln. F5-d wird sauber von R-031 gefangen,
  F5-e sauber von keiner Regel — wie vorgesehen.

### Befund 2 — F1-a und F1-b sind für den Katalog nicht unterscheidbar

- **Datum:** 2026-08-10
- **Sachlage:** F1-a lässt das Feld fehlen (`pd.NA`), F1-b liefert es leer (Leerstring). Auf
  der Speicherebene ist das ein Unterschied; nach dem Parsen ist er verschwunden, weil
  `spec/01`, Abschnitt 6 jeden leeren Wert als Leerstring serialisiert.
- **Folge für die Auswertung:** Der Recall beider Varianten fällt gleich aus. Das ist die
  Fortsetzung des in Phase 3 zu R-025 festgehaltenen Informationsverlusts der
  Serialisierung — vorhergesagt und begründet, nicht überraschend.
- **Regeländerung:** keine. Der Befund gehört in die Diskussion, nicht in den Katalog.

### Befund 3 — F4-g löst zwangsläufig mehr als eine Regel aus

- **Datum:** 2026-08-10
- **Sachlage:** Ein negativer Nettobeitrag verletzt R-021 (Beitrag > 0) **und** R-031
  (Brutto = Netto + Steuer). Eine negative Deckungssumme verletzt R-021 und R-024
  (PflVG-Mindestdeckung).
- **Bewertung:** Das ist keine Schwäche der Variante, sondern eine Eigenschaft eines
  Vorzeichenfehlers: In einem arithmetisch verknüpften Satz kann er gar nicht isoliert
  auftreten.
- **Entscheidung:** Kein Eingriff. Die Nebentreffer werden in Phase 5 über `verstoss_id` und
  `injektor_variante_id` getrennt ausgewiesen.

### Befund 4 — die gleichmäßige Zuteilung war ein Confounder für Faktor UV2

- **Datum:** 2026-08-11 (Nachtrag zu Phase 4)
- **Sachlage:** Ursprünglich wurde das Klassenkontingent gleichmäßig auf die Varianten
  verteilt, und der nicht ausgeschöpfte Rest knapper Varianten ging an die übrigen. F4-f,
  F7-c und F7-d wirken auf der Entität `tarif` mit nur **231 Zeilen** und stoßen früh an ihre
  Decke.
- **Das Problem:** Je höher die Fehlerrate, desto früher stoßen die knappen Varianten an ihre
  Decke und desto größer wird der Anteil der reichlich vorhandenen. **Die Zusammensetzung
  einer Klasse verschöbe sich damit mit der Fehlerrate** — und die Fehlerrate ist Faktor UV2.
  Ein gemessener Zusammenhang „höhere Rate → anderer Recall" wäre teils Ratenwirkung, teils
  Verschiebung der Variantenmischung, und der Page-Trendtest über die Ratenstufen könnte
  beides nicht trennen. Das ist ein Confounder im Kern des Versuchsplans.
- **Entscheidung:** Zuteilung **proportional zum adressierbaren Universum jeder Variante**,
  gerundet nach Hare-Niemeyer. Der Anteil jeder Variante ist damit über alle sechs
  Ratenstufen konstant. Es wird **nicht mehr umverteilt**; erreicht eine Variante ihr
  Kontingent nicht, bricht der Injektor ab.
- **Warum nichts überläuft:** Die Summe der Variantenuniversen ist wegen Überschneidungen
  (F4-c und F4-d treffen beide `wohnflaeche_qm`) nie kleiner als das Klassenuniversum. Damit
  gilt für jede Rate bis 1: `n_i ≤ universum_i`.
- **Auswirkung auf die Messung:** Die Variantenanteile verschieben sich gegenüber der ersten
  Fassung erheblich. Bei F4 fällt F4-f von 16,1 auf 0,1 Prozent, F4-g steigt von 16,1 auf
  73,5 Prozent; bei F7 fallen F7-c und F7-d von je 9,6 auf 0,2 Prozent. Das
  Klassenkontingent bleibt unverändert.
- **Der Preis, und was ihn ausgleicht:** F7-c bekommt bei zwei Prozent noch fünf Injektionen
  statt 231. Für die klassenweise Auswertung ist das richtig — es ist genau ihr Anteil an der
  Klasse. Für den Recall **je Variante** ist es zu wenig. Dafür gibt es den Teilversuch
  „Variantencharakterisierung": `--modus variante --variante F7-c` injiziert nur diese eine
  Variante und schöpft ihr Universum aus (231 von 231, gemessen). Diese Läufe gehören nicht
  in den faktoriellen Plan.
- **Zwei dokumentierte Nebenwirkungen:** Seltene Varianten können bei kleiner Rate das
  Kontingent null bekommen (bei der obersten Ratenstufe nicht mehr), und die
  Gruppengranularität der kohärenten Skalierung lässt die erreichte Zahl um weniger als eine
  Gruppengröße von der zugeteilten abweichen. Beides steht im `manifest.json`.

### Befund 5 — mitgezogene Rangzellen sind keine Fehler

- **Datum:** 2026-08-10
- **Sachlage:** `spec/03`, Abschnitt 2 verlangt bei den Skalierungsvarianten, die Rangfolge
  mitzuziehen, sonst löst zusätzlich R-044 aus. Die nachgeführte Zelle `angebot.rang` ist nach
  der Skalierung aber **richtig** — sie trägt den korrekten Rang zum verfälschten Beitrag.
- **Das Dilemma:** Stünde sie ununterscheidbar im `error_log`, wäre sie ein garantiertes
  False Negative und der Recall fiele, ohne dass ein Detektor etwas übersehen hätte. Stünde
  sie gar nicht im Log, fände der Diff-Gegencheck eine Abweichung ohne Protokolleintrag.
- **Entscheidung:** Zusätzliche Spalte `mitgezogen` im zellbasierten Log. Sie steht im Log,
  geht aber weder in das Zelluniversum noch in die Fehlerrate ein.
- **Größenordnung:** Bei zwei Prozent Fehlerrate und 10.000 Anfragen entstehen zu 5.336
  Trägerzellen der Klasse F8 zusätzlich 3.651 mitgezogene Rangzellen, bei HO2 zu 5.368
  Trägerzellen 2.228. Ohne die Unterscheidung fiele der gemessene Recall von F8 rechnerisch um
  gut 40 Prozent — allein durch die Buchführung.
- **Nachtrag vom 2026-08-11:** Beide Zahlen stehen jetzt getrennt und mit sprechenden Namen
  im `manifest.json` — `zellen_fehlerhaft` und `zellen_geaendert_gesamt`. Der Grund ist eine
  Nebenwirkung, die ausgewiesen gehört: Bei F8 und HO2 ist der Datensatz an rund zwei Dritteln
  mehr Stellen verändert, als die Fehlerrate nominell angibt. „Zwei Prozent" bedeutet für F8
  also nicht nur wegen des klassenspezifischen Universums etwas anderes als für F3. Für die
  Metrik zählt `zellen_fehlerhaft`, für die Beschreibung des verfälschten Datensatzes
  `zellen_geaendert_gesamt`.

### Ergebnis des Gegenchecks

Über alle zehn Fehlerklassen, den Mischmodus und drei Variantenläufe, bei 10.000 Anfragen und
zwei Prozent Fehlerrate: **keine Abweichung** in 14 Läufen. Diff und Ground Truth stimmen
zellweise überein, jede hinzugefügte Zeile steht im satzbasierten Log, keine Zelle ist
doppelt injiziert, und für jede Log-Zeile gilt `wert_clean != wert_dirty`.

Der Bericht steht in `results/ground_truth_check.json` und sammelt die Läufe unter ihrer
`run_id`, statt sie zu überschreiben.

---

## Phase 5 — Befunde beim Bau des Evaluators und der Vergleichsverfahren

**Keiner dieser Punkte ist eine Iteration 2.** Der Regelkatalog ist unverändert: kein
Prädikat, kein Wertebereich, kein Schwellenwert, kein Geltungsbereich, kein Schweregrad und
keine Achsenzuordnung wurde angefasst. Geändert wurden ausschließlich die neuen Pakete
`src/evaluation/` und `src/baselines/` sowie die Dokumentation.

Die Entscheidungsprobe aus dem Freeze — *Ändert sich durch die Korrektur die Menge der
gemeldeten Zellen auf irgendeinem Datensatz?* — lautet für jeden Punkt unten **nein**.

### Befund 1 — auf der Constraint-Ebene wechselt nur die Precision die Einheit

- **Datum:** 2026-08-12
- **Sachlage:** Die Constraint-Ebene zählt die `verstoss_id`, um die strukturelle Deckelung
  der Precision aufzuheben: R-031 meldet Brutto, Netto und Steuer, der Injektor hat nur eine
  der drei Zellen verfälscht — zellbasiert ergibt perfekte Erkennung 1 TP und 2 FP. Der erste
  Entwurf bildete daraus **auch** den Recall, also `tp / (tp + fn)` mit Verstößen im Zähler
  und Wahrheitszellen im Nenner.
- **Warum das falsch ist:** Der Bruch mischt zwei Einheiten, und zwar in **beide** Richtungen.
  Ein Verstoß, der zwei injizierte Zellen zugleich überdeckt — bei F8 der Regelfall, weil die
  kohärente Skalierung mehrere Beitragsfelder trifft —, zählt einmal statt zweimal und drückt
  den Recall. Zwei Regeln, die dieselbe injizierte Zelle melden — der Datums-Sentinel löst
  R-009 und R-025 gleichzeitig aus —, zählen zweimal statt einmal und heben ihn. Letzteres
  ist genau die Doppelzählung, die die Vereinigungsmenge ausschließen soll.
- **Nachgerechnet:** Ein Verstoß über zwei von drei Wahrheitszellen ergibt zellbasiert 0,667
  und constraint-basiert 0,500; zwei Regeln auf einer von zwei Wahrheitszellen ergeben
  zellbasiert 0,500 und constraint-basiert 0,667. In **einer** `metrics.json` hätten damit
  zwei verschiedene Zahlen unter dem Namen `recall` gestanden — die eine in der
  Konfusionsmatrix der Ebene, die andere in ihren zellweise gebildeten Gruppentabellen.
- **Entscheidung:** Die Konfusionsmatrix trägt ein eigenes Feld `tp_recall` — den Zähler des
  Recalls, wenn er in einer anderen Einheit gezählt wird als `tp`. Nur die Constraint-Ebene
  setzt es; der Recall bleibt dort zahlengleich mit dem der Zellebene. Beide Werte werden
  persistiert, damit der Recall aus den Rohwerten nachrechenbar bleibt.
- **Wie er gefunden wurde:** Nicht durch die Tests. Der erste Test der Constraint-Ebene prüfte
  nur den entarteten Fall — ein Verstoß über *genau eine* Wahrheitszelle und `fn = 0` —, in
  dem beide Einheiten zufällig übereinstimmen. Zwei ergänzte Tests decken jetzt die beiden
  Richtungen ab.

### Befund 2 — cuallee nennt keine Zeile, und das ist das Ergebnis

- **Datum:** 2026-08-12
- **Sachlage:** `cuallee.pandas_validation.summary` gibt je Regel Spalte, Regelname, Zahl der
  Verstöße und eine Bestehensquote zurück — **keine Zeile und keinen Ausgangswert**. Die
  Prüffunktionen liefern intern einen Wahrheitswert oder eine Zahl je Regel, nicht je Zeile.
- **Folge:** B3 kann keine zellbasierte Konfusionsmatrix erzeugen. Seine Meldungen tragen
  deshalb `row_id = -1`, das Verfahren trägt `lokalisiert_zellen = False`, und der Evaluator
  schreibt für alle drei Ebenen `null` **mit Begründung** statt Nullen. Eine Null läse sich
  wie „hat nichts gefunden"; die Aussage ist aber „kann nicht gemessen werden, und genau das
  ist die Kennzahl Diagnosegüte".
- **Deutung für die Arbeit:** Das ist kein Implementierungsmangel und keine Schwäche des
  Frameworks im Detail, sondern die zentrale Antwort auf die Frage „Warum ein eigener
  Prototyp?". Ein Validator, dessen Report die fehlerhafte Zeile nicht benennt, ist im Betrieb
  nicht nachbearbeitbar.

### Befund 3 — B0 deckt R-009 ab, ohne sie zu kennen

- **Datum:** 2026-08-12
- **Sachlage:** B0 soll die untere Schranke sein: nur Typen, Nullable-Constraints und
  Feldlängen. Die Rohform eines Datums ist `TTMMJJJJ`; wer sie in ein `datetime.date`
  überführt, weist `31022026` zwangsläufig zurück.
- **Folge:** B0 deckt den Inhalt von R-009 („jedes Datumsfeld der Rohschicht ist ein
  existierender Kalendertag") vollständig ab. Das ist keine eingeschmuggelte Fachregel,
  sondern die Eigenschaft eines Typs — die Menge der gültigen Kalendertage **ist** der
  Wertebereich von `date`.
- **Deutung für die Arbeit:** Der Abstand zwischen Baseline und Prototyp ist je Fehlerklasse
  verschieden groß. Bemerkenswert ist die Umkehrung der erwarteten Rangfolge: Dieselbe Regel
  löst das Typsystem nebenbei, während das etablierte Framework B3 sie gar nicht ausdrücken
  kann — eine DataFrame-Check-API kennt Muster, aber keinen Kalender.

### Befund 4 — `person.nachname` ist für B0 kein Pflichtfeld

- **Datum:** 2026-08-12
- **Sachlage:** `spec/01`, Abschnitt 3.2 führt `nachname` mit „nicht leer, **außer**
  `anrede` = FIRMA". Das ist keine Nullable-Angabe, sondern eine bedingte funktionale
  Abhängigkeit — im Prototyp ist das R-001.
- **Entscheidung:** B0 führt als Pflicht nur die Felder, die `spec/01` **ohne Bedingung** als
  Schlüssel oder als Pflicht ausweist. Ein unbedingtes `nachname: str` wäre zudem sachlich
  falsch: Es löste auf dem **sauberen** Datensatz bei jeder Firmenzeile aus.
- **Folge:** F1 trifft überwiegend Felder, deren Pflichtcharakter bedingt ist. B0 erreicht
  dort deshalb einen kleinen Recall. Der Abstand zum Prototyp **ist** der Beitrag der
  Fehlertaxonomie.

### Befund 5 — B2 markiert Zellen, die nie fehlerhaft sein können

- **Datum:** 2026-08-12
- **Sachlage:** B2 arbeitet auf Zeilenebene; für die Zellmetrik markiert eine anomale Zeile
  alle ihre befüllten Zellen. Dazu gehört `row_id`, die nach Architekturregel A3 **niemals**
  Ziel einer Injektion ist.
- **Entscheidung:** Die Umrechnung bleibt wie spezifiziert — sie wird nicht heimlich zugunsten
  von B2 beschnitten. Stattdessen weist der Evaluator `markierte_zellen_row_id` getrennt aus.
  Diese Meldungen sind garantierte Fehlalarme und drücken B2s Zell-Precision, ohne über seine
  Erkennungsleistung etwas auszusagen.
- **Deutung für die Arbeit:** Deshalb ist für B2 die **Satzebene** der Primärvergleich und die
  Zellebene die Zusatzangabe. Die Umrechnung benachteiligt B2 bei der Precision und begünstigt
  es beim Recall; beides gehört benannt.

### Befund 6 — die Fehlwertbehandlung von B2 ist eine Entscheidung zu seinen Gunsten

- **Datum:** 2026-08-12
- **Sachlage:** `IsolationForest` nimmt kein `NaN`. Numerische Spalten werden mit dem Median
  aufgefüllt, kategoriale bekommen die eigene Stufe `-1`, und **jede** Spalte mit mindestens
  einem Fehlwert bekommt eine binäre Indikatorspalte `<spalte>__fehlt`.
- **Begründung:** Ohne den Indikator wäre ein fehlender Wert für ein Anomalieverfahren
  unsichtbar — die Median-Auffüllung macht die Zeile ja gerade unauffällig. B2 hätte auf der
  Fehlerklasse F1 dann per Konstruktion keinen Recall, und der Vergleich wäre wertlos.
- **Ebenfalls zugunsten von B2:** `contamination` wird über sieben Stufen gesweept und die
  **beste erreichte F1** berichtet. Das ist eine bewusst optimistische Einstellung und in der
  Arbeit als solche zu deklarieren. `contamination` wird ausdrücklich **nicht** auf die wahre
  Fehlerrate gesetzt — das wäre unfair und angreifbar.

---

## Phase 5, Nachtrag — Frameworkvergleich, zwei Ergebnisse und eine Werkzeugentscheidung

**Auch hier keine Iteration 2.** Der Regelkatalog ist unverändert.

### Befund 7 — die Lokalisierungsaussage gilt für cuallee, nicht für die Gattung

- **Datum:** 2026-08-12
- **Sachlage:** Befund 2 hält fest, dass `cuallee.pandas_validation.summary` weder Zeile
  noch Ausgangswert liefert. Das ist richtig und nachgemessen. Der Satz darf aber **nicht**
  auf "etablierte Frameworks können Fehler nicht auf die Zelle lokalisieren" verallgemeinert
  werden.
- **Gegenbeispiel, nachgemessen:** Great Expectations 1.20.0 liefert bei
  `result_format: COMPLETE` mit konfigurierten `unexpected_index_column_names` in
  `unexpected_index_list` je fehlgeschlagener Zeile ein Dictionary aus Zeilenkennung **und**
  fehlerhaftem Wert, dazu `unexpected_index_query` als nachvollziehbare Abfrage. Auf einem
  F2-verfälschten Datensatz etwa `{'plz': '4946', 'row_id': '90'}`.
- **Warum das zählt:** Stünde die Verallgemeinerung in der Arbeit, genügte einem Prüfer die
  Kenntnis von Great Expectations, um sie zu kippen — und mit ihr die Begründung des
  Artefakts, wenn sie darauf gebaut wäre.
- **Entscheidung:** Die Kennzahl Diagnosegüte wird überall als Eigenschaft von cuallee
  formuliert, mit Great Expectations namentlich als Gegenbeispiel. Die Begründung des
  Artefakts steht auf der **Ausdrückbarkeit**; die Diagnosegüte ist der zweite,
  nachgeordnete Punkt und ein Befund über den Gestaltungsraum der Werkzeuge.

### Befund 8 — auch die Ausdrückbarkeit ist nicht ganz frameworkunabhängig

- **Datum:** 2026-08-12
- **Sachlage:** Der Gegenschnitt legt sieben G1-Regeln zusätzlich Great Expectations vor
  (`src/baselines/b3b_great_expectations.py`, `scripts/framework_vergleich.py`). Ergebnis auf
  denselben sieben Regeln: **cuallee 4 von 7 (57 %), Great Expectations 6 von 7 (86 %)**.
- **Die beiden Unterschiede sind benennbar**, nicht zufällig:
  - `row_condition` mit `condition_parser="pandas"` macht eine Erwartung vom Wert eines
    anderen Feldes derselben Zeile abhängig. R-001 ist damit **vollständig** formulierbar,
    also auch der bedingte Teil; in cuallee bleibt nur der unbedingte.
  - `ExpectColumnValuesToMatchStrftimeFormat` parst den Wert wirklich. Der 31. Februar fällt
    damit auf, R-009 ist formulierbar; in cuallee erkennt `has_pattern` acht Ziffern, aber
    keinen Kalender.
- **Beide scheitern an R-004.** Eine Prüfziffer nach ISO 7064 ist ein Algorithmus, kein
  Prädikat über einen Spaltenwert. Die Auffangtür beider Frameworks — `is_custom`
  beziehungsweise eine eigene Expectation-Klasse — misst nur noch die selbst geschriebene
  Prüfung.
- **Folge für die Arbeit, und sie ist unbequem:** Die Zahl **36,2 Prozent ist für cuallee
  gemessen** und muss auch so ausgewiesen werden. Frameworkübergreifend belastbar ist der
  Kern der Grenze, und der liegt nicht bei den bedingten Regeln, sondern bei den
  **relationalen** (R-043 bis R-048, R-052, R-054), den **quellenübergreifenden** (R-049 bis
  R-051, R-055 bis R-058) und den **algorithmischen** (R-004). Allein die Gruppen G3 bis G5
  umfassen 16 der 58 Regeln, und sie bleiben beiden Frameworks verschlossen.
- **Nebenbefund Aufwand:** Great Expectations drückt mehr aus, kostet dafür aber mehr
  Quelltext — R-001 dreizehn Zeilen gegen drei, R-014 elf gegen drei. Ausdrucksmächtigkeit
  und Knappheit gehen hier auseinander.

### Befund 9 — Constraint-Ebene und Zellebene haben denselben Recall, und das ist richtig

- **Datum:** 2026-08-12
- **Sachlage:** Nach der Korrektur aus Befund 1 sind die Recallwerte beider Ebenen in jedem
  Lauf identisch. Zähler wie Nenner sind dieselbe Menge — die injizierten Zellen.
- **Warum das dokumentiert gehört:** Die Gleichheit sieht in der Ergebnistabelle wie ein
  Kopierfehler aus, und die Constraint-Ebene wirkt überflüssig. Sie ist aber genau für die
  **Precision** eingeführt worden: Im Beispiellauf F3 steht dort 1,000 gegen 0,534 auf der
  Zellebene, weil mehrspaltige Regeln wie R-051 und R-058 alle abgeleiteten Felder melden.
  Der Satz "nur die Precision unterscheidet sich" gehört in die Arbeit.

### Befund 10 — B0 fängt R-009 mit, und die Achse C wackelt dadurch

- **Datum:** 2026-08-12
- **Sachlage:** Siehe Befund 3. Der Datumsparser von pydantic weist `31022026` zurück, weil
  ein `datetime.date` mit diesem Wert nicht konstruierbar ist. B0 deckt den Inhalt von R-009
  damit vollständig ab, ohne die Regel zu kennen.
- **Material für die Diskussion, keine Korrektur:** Die Grenze zwischen Typprüfung und
  fachlicher Regel ist nicht scharf. Für die **Achse C** der Taxonomie ist das relevant:
  R-009 ist als C1 (deterministisch) eingeordnet und fachlich hergeleitet — sie fällt bei
  passender Typwahl trotzdem kostenlos an. Die Einordnung einer Regel auf Achse C sagt also
  etwas über ihre Prüfbarkeit aus, aber nicht darüber, ob ein Verfahren sie eigens
  implementieren muss.
- **Verschärft wird der Punkt durch Befund 8:** Dieselbe Regel führt cuallee als *nicht*
  ausdrückbar, Great Expectations als ausdrückbar, und ein reines Typsystem erledigt sie
  nebenbei. Die erwartete Rangfolge "Typsystem < Framework < eigener Katalog" gilt für
  R-009 nicht.

### Werkzeugentscheidung — `ruff format` wird für den Bestand nicht ausgeführt

- **Datum:** 2026-08-12
- **Sachlage:** `ruff format --check` würde 52 der 114 Dateien umformatieren. Das Projekt hat
  von Anfang an nur `ruff check` (den Linter) durchgesetzt, nie den Formatierer.
- **Entscheidung:** Der Bestand wird **nicht** umformatiert. Neue Dateien werden
  format-konform geschrieben; alle Dateien der Phase 5 sind es.
- **Begründung — sie ist stärker als "das wäre ein großer Diff":** Ein Reformat fasst auch
  `src/rules/` an. Nach der Entscheidungsprobe des Freeze ist das **keine** Regeländerung —
  die Menge der gemeldeten Zellen bleibt auf jedem Datensatz gleich. Aber wer den Tag
  `freeze-regelkatalog` gegen `HEAD` diffed, um zu prüfen, dass die Regeln unverändert sind,
  bekommt dann Formatierungsrauschen über alle Regelmodule statt einer leeren Ausgabe. **Der
  Freeze soll nachprüfbar bleiben, nicht nur gültig.** Diese Notiz steht hier, damit die
  Entscheidung nicht später versehentlich "repariert" wird.

### Probelauf der beiden Gewichtungen (F4, HO2, F8)

Vor dem Hauptversuch auf je einem Lauf mit 10.000 Anfragen und zwei Prozent Fehlerrate
gerechnet, Verfahren Prototyp. Zweck: die Gewichtung an zwei Läufen prüfen und nicht an 1.680.

| Klasse | Recall zellgewichtet | Recall variantengewichtet | größte Variante |
|---|---|---|---|
| F4 | 1,000 | 1,000 | F4-g mit 1.236 von 1.681 Zellen (73,5 %) |
| HO2 | 0,0041 | 0,0023 | HO2-b mit 4.868 von 5.368 Zellen (90,7 %) |
| F8 | 0,3084 | 0,3119 | F8-b mit 1.308 von 5.328 Zellen (24,6 %) |

Die beiden Anteile 73,5 % und 90,7 % treffen die aus Phase 4b dokumentierten Werte exakt —
die Zuteilung arbeitet wie beabsichtigt.

**Zwei Abweichungen von der Erwartung, beide erklärbar:**

1. **F4 ist auch variantengewichtet 1,000.** Erwartet war ein deutlicher Unterschied, weil
   F4-g drei Viertel der Klasse stellt. Tatsächlich haben **alle sieben** F4-Varianten den
   Recall 1,000 — der Klassenwert von 1,000 ist also nicht bloß ein Zuteilungseffekt, sondern
   eine stärkere Aussage: F4 wird vollständig erkannt, unabhängig von der Gewichtung. Ein
   Unterschied zwischen den beiden Gewichtungen kann nur dort auftreten, wo die Varianten
   einer Klasse **verschieden gut** erkannt werden; bei F4 tun sie das nicht.
2. **Bei HO2 hebt `mitgezogen_als_fehler = True` den Recall, statt ihn zu senken**
   (0,0058 gegen 0,0041). Der Grund: Der Prototyp findet dort ausschließlich über R-044, und
   dieser Verstoß meldet je Paar zwei `rang`-Zellen (mitgezogen) und zwei
   `zahlbeitrag_rate_eur`-Zellen (Träger). Zählt man die mitgezogenen mit, verdoppelt sich
   `tp` von 22 auf 44, während der Nenner nur um den Faktor 1,42 wächst. Bei **F8** wirkt der
   Schalter wie erwartet und deutlich: 0,3084 gegen 0,1828, weil dort von 3.705 mitgezogenen
   Zellen nur 8 gefunden werden.

   **Die Richtung des Schalters ist damit klassenabhängig und darf in der Arbeit nicht
   pauschal als "senkt den Recall" beschrieben werden.** Genau dafür werden beide Werte je
   Lauf berechnet.

**Ein Nebenbefund, der vor Phase 6 zu entscheiden ist:** R-044 meldet auf dem HO2-Lauf
**11 Verstöße**. HO2-b ist als held-out gedacht und soll unentdeckt bleiben; `spec/03`,
Abschnitt 2 verlangt deshalb, die Rangfolge bei der kohärenten Skalierung mitzuziehen, damit
die Rangregel gerade **nicht** zusätzlich auslöst. In 11 von 1.217 skalierten Angeboten
(0,9 %) bleibt die Ordnung trotzdem verletzt. Der gemessene HO2-Recall von 0,004 statt 0,000
geht vollständig auf diese 11 Fälle zurück. Das ist keine Änderung am Regelkatalog und keine
am Ground Truth — aber es ist eine offene Frage an den Injektor, und sie gehört beantwortet,
bevor 1.680 Läufe darauf aufbauen.

---

## Phase 5, zweiter Nachtrag — Diagnose der elf R-044-Fälle und der strukturelle Kern

**Auch hier keine Iteration 2, und keine Änderung am Injektor.** Der Regelkatalog ist
unverändert.

### Befund 11 — die Ursache der elf Fälle ist keine der drei erwarteten

- **Datum:** 2026-08-12
- **Frage:** Warum bleibt bei HO2 in 11 von 1.217 skalierten Angeboten die Rangfolge
  verletzt, obwohl `spec/03`, Abschnitt 2 das Mitziehen der Rangfolge verlangt?

**Die drei naheliegenden Ursachen scheiden aus, jede an einem Messwert:**

1. **Falsches Sortierfeld — nein.** `bausteine.neue_raenge` sortiert nach
   `zahlbeitrag_rate_eur`, also nach genau dem Feld, das R-044 prüft. Nachgelesen im
   Quelltext und an den Daten bestätigt.
2. **Gleichstand — nein.** Der erste gemeldete Fall lautet „rang=1 trägt die Rate 679,77,
   der nachfolgende rang=2 die kleinere Rate 591,68". Eine Differenz von 88 Euro ist kein
   Gleichstand.
3. **Rundung — nein.** Aus demselben Grund: `ROUND_HALF_UP` auf zwei Nachkommastellen kann
   eine Inversion um einen Cent erzeugen, nicht um 88 Euro.

**Die tatsächliche Ursache ist eine vierte: Interferenz zwischen zwei Anwendungen derselben
Variante innerhalb einer Anfrage.**

Die Zahlen sind eindeutig. Von den 11 betroffenen Anfragen haben **alle 11** mehr als ein
skaliertes Angebot; von den 1.102 Anfragen mit genau einem skalierten Angebot ist **keine
einzige** betroffen.

Der Mechanismus: HO2-b skaliert ein **einzelnes** Angebot je Anwendung
(`skalierung(..., ganze_anfrage=False)`) und führt danach die Rangfolge der ganzen Anfrage
nach. Der `Injektionskontext` zeigt dabei durchgehend den **sauberen** Stand — das ist so
dokumentiert und mit „keine Zelle wird zweimal getroffen" begründet. Diese Begründung trägt
für **Zellen**, aber nicht für eine **Ordnung über Zeilen**: Wird ein zweites Angebot
derselben Anfrage skaliert, berechnet dessen Nachführung die Rangfolge gegen den sauberen
Zahlbeitrag des ersten — und ist blind dafür, dass dieser inzwischen selbst gesenkt wurde.

Der gemessene Beispielfall, Anfrage `ccfbc6f3`, sechs Angebote, drei davon skaliert:

| row_id | Rate clean | Rate dirty | Rang clean | Rang dirty | skaliert |
|---|---|---|---|---|---|
| 3830 | 696,09 | 591,68 | 1 | 2 | ja |
| 3833 | 799,73 | 679,77 | 2 | 1 | ja |
| 3834 | 900,10 | — | 3 | 4 | |
| 3831 | 968,77 | — | 4 | 5 | |
| 3832 | 1041,80 | — | 5 | 6 | |
| 3835 | 1053,98 | 895,88 | 6 | 3 | ja |

Als 3833 skaliert wurde, sah die Nachführung für 3830 den sauberen Wert 696,09 gegen den
neuen eigenen Wert 679,77 — 3833 wird korrekt Rang 1, 3830 Rang 2. Zu diesem Zeitpunkt ist
das richtig. 3830 wurde aber selbst auf 591,68 gesenkt, und damit steht am Ende Rang 1 mit
679,77 vor Rang 2 mit 591,68. Genau das meldet R-044.

### Befund 12 — der Effekt wächst mit der Fehlerrate

- **Datum:** 2026-08-12
- **Messung:** HO2 bei vier Ratenstufen, je 10.000 Anfragen, Verfahren Prototyp.

| Fehlerrate | skalierte Angebote | Anfragen mit ≥ 2 | R-044-Verstöße | Anteil an skaliert | HO2-Recall (Zellebene) |
|---|---|---|---|---|---|
| 0,005 | 304 | 2 | 0 | 0,00 % | 0,00000 |
| 0,010 | 609 | 14 | 3 | 0,49 % | 0,00223 |
| 0,020 | 1.217 | 57 | 11 | 0,90 % | 0,00410 |
| 0,050 | 3.044 | 294 | 65 | 2,14 % | 0,00968 |

**Der Anteil bleibt nicht konstant, er wächst.** Und mit ihm der gemessene Recall der
Held-out-Klasse HO2 — von null bei der kleinsten Ratenstufe auf knapp ein Prozent bei der
größten.

Das ist genau die Sorte Artefakt wie die Mischungsverschiebung aus Phase 4b, nur kleiner:
**HO2 bekäme über UV2 einen steigenden Recall, und zwar nicht, weil der Katalog besser
würde, sondern weil mehr Skalierungen mehr Ordnungskollisionen erzeugen.** Die Zahl der
Anfragen mit mindestens zwei Skalierungen wächst überproportional (2, 14, 57, 294) — ein
Geburtstagsproblem —, und die Verstöße folgen ihr proportional (Verhältnis konstant um 0,2).

Ein Trendtest über die Ratenstufen für HO2 misst damit denselben Confounder, den die
proportionale Zuteilung aus Phase 4b gerade beseitigt hat.

### Entscheidung — offen, und warum sie nicht einseitig getroffen wird

Die vorab festgelegte Regel ordnet den Fall eindeutig zu: Es ist **keine** prinzipielle
Unmöglichkeit (wie Gleichstand oder Rundung es wären), sondern eine **Abweichung der
Implementierung von ihrer eigenen Spezifikation**. `spec/03` verlangt das Mitziehen der
Rangfolge, damit die Rangregel gerade nicht zusätzlich auslöst; in der beschriebenen
Konstellation leistet die Implementierung das nicht. Nach der Regel heißt das: korrigieren,
Artefakte neu erzeugen, Gegencheck erneut fahren.

**Der Injektor ist trotzdem unverändert geblieben**, weil das *Wie* die Semantik des
Versuchsplans berührt und nicht aus der Regel folgt. Jede korrekte Behebung braucht Zugriff
auf den **Arbeitsstand** statt auf den sauberen Kontext, und der Kontext ist absichtlich
unveränderlich:

- **(a) Rangfolge gegen den Arbeitsstand berechnen.** Fachlich die richtige Lösung; die
  Kandidatenmenge bleibt unberührt. Kosten: Die dokumentierte Invariante „der Kontext zeigt
  immer den sauberen Stand" fällt, und die Varianten bekommen eine zweite Datenquelle.
- **(b) Höchstens eine Skalierung je Anfrage zulassen.** Kleiner Eingriff, Kontext bleibt
  unverändert. Kosten: Das adressierbare Universum von HO2-b und F8 schrumpft, und bei der
  obersten Ratenstufe könnte die Variante ihr Kontingent nicht mehr erreichen — dann bricht
  der Injektor ab, wie vorgesehen. Bei 0,05 wären 294 von 3.044 Kandidaten betroffen.

Empfehlung: **(a)**, weil (b) die Bezugsgröße der Fehlerrate verändert und damit genau die
Größe antastet, um die es in UV2 geht.

### Befund 13 — der strukturelle Kern der Framework-Grenze, gemessen

- **Datum:** 2026-08-12
- **Sachlage:** Befund 8 stellte die Aussage auf, der frameworkübergreifend belastbare Teil
  der Grenze seien die relationalen, die quellenübergreifenden und die algorithmischen
  Regeln. Diese Aussage trägt die Begründung des Artefakts und stand bis hierher auf einem
  Formargument. Sie ist jetzt gemessen.
- **Vorgelegt wurden zwei G3-Regeln** zusätzlich zu den sieben aus G1: R-046 (je Anfrage
  genau ein VN — satzübergreifend mit Gruppenbezug) und R-054 (Abweichung vom Median der
  **übrigen** Angebote derselben Anfrage — Aggregat mit Rückbezug auf die Gruppe).
- **Ergebnis:** Beide sind in **keinem** der beiden Frameworks ausdrückbar. Keines der 57
  Great-Expectations-Erwartungen und keines der cuallee-Prädikate trägt `Group` oder
  `Partition` im Namen; Aggregate gibt es nur über die ganze Spalte (cuallee
  `has_percentile`) beziehungsweise den ganzen Batch (`ExpectColumnMedianToBeBetween`).
- **Zwei Feinheiten, die zur Ehrlichkeit gehören:**
  - Great Expectations formuliert mit `row_condition='rolle == "VN"'` plus
    `ExpectColumnValuesToBeUnique` die **Hälfte** von R-046, nämlich „höchstens ein VN je
    Anfrage" — nachgemessen. „Mindestens einer" braucht die Tabelle `anfrage`, und eine
    Erwartung sieht immer nur einen Batch. cuallee schafft auch diese Hälfte nicht, weil ihm
    die Zeilenbedingung fehlt.
  - R-044 ließe sich in Great Expectations je Anfrage über `row_condition` nachbilden. Das
    wären 10.000 Erwartungen statt einer Regel — kein Ausdrücken, sondern ein Ausrollen.
- **Damit steht die zentrale Aussage auf einer Messung:** Ein Prüfmodell aus zeilen- und
  spaltenweisen Prädikaten über **eine** Tabelle kennt keine Gruppierung mit Rückbezug auf
  die Gruppe. Genau das verlangen R-043 bis R-048, R-052 und R-054.

### Aufräumpunkt — Great Expectations aus `requirements.txt` herausgezogen

- **Datum:** 2026-08-12
- **Entscheidung:** `great_expectations==1.20.0` steht jetzt in
  `requirements-vergleich.txt` und wird separat installiert.
- **Begründung:** Siebzehn transitive Abhängigkeiten für einen Vergleich, der nicht in die
  Inferenzstatistik eingeht, verwässern das Reproduzierbarkeitspaket des eigentlichen
  Experiments. A2 verlangt gepinnte Versionen für die **Läufe**; die bleiben unberührt und
  werden schlanker. Ohne die Zusatzinstallation überspringt sich `test_b3b.py` selbst
  (`pytest.importorskip`) und `scripts/framework_vergleich.py` bricht mit einem
  Installationshinweis ab.

### Aufräumpunkt — „Fehler erkannt" ist nicht „Nebenwirkung erkannt"

- **Datum:** 2026-08-12
- **Festgehalten im Modul-Docstring von `src/evaluation/metriken.py`, Abschnitt 9.**
- **Sachlage:** Ein Treffer auf einer verfälschten Zelle ist per Definition ein True
  Positive, auch wenn die auslösende Regel gar nicht auf diese Fehlerart zielt. Die Metrik
  kennt nur „liegt die markierte Zelle im Ground Truth?", und das ist richtig so — jede
  feinere Zurechnung wäre eine Auslegung und keine Messung.
- **Für die Deutung reicht das nicht.** Zwei Fälle sehen in der Ergebnistabelle identisch
  aus: eine Regel erkennt den Fehler, auf den sie zielt (R-013 auf F3-g), oder eine Regel
  erkennt eine **Nebenwirkung** (R-044 auf HO2 — die kohärente Senkung bleibt unentdeckt,
  entdeckt wird die Ordnungskollision, die sie hinterlässt).
- **Beleg ist die Kreuztabelle `regel_id` × `fehlerklasse`.** Dass bei HO2 ausschließlich
  R-044 auftaucht, ist selbst die Diagnose: Bei einer Klasse, deren Recall von einer auf sie
  zielenden Regel getragen wird, stünde dort eine andere Regel. Wer einen Klassen-Recall
  ohne die Kreuztabelle interpretiert, kann die beiden Fälle nicht unterscheiden.

---

## Phase 5, dritter Nachtrag — Kohärenz wird ein eigener Schritt

**Der Regelkatalog bleibt unberührt.** Geändert wurde ausschließlich der Injektor, und zwar
an einer Stelle: Das Nachführen der Preisrangfolge wandert aus den Varianten in einen
nachgelagerten Schritt der Pipeline.

### Befund 14 — Kohärenz gegen den Ausgangszustand hält nicht unter Überlagerung

**Das ist der eigentliche Ertrag von Befund 11, und er gehört als Ergebnis in die Arbeit,
nicht als Fußnote in die Fehlerliste.**

> Wird Kohärenz **je Verfälschung** gegen den **unverfälschten Ausgangszustand** hergestellt,
> ist sie bei mehrfacher Anwendung innerhalb derselben Bezugsgruppe nicht mehr gewährleistet.
> Die Verletzung entsteht nicht in der einzelnen Verfälschung, sondern in ihrer
> **Überlagerung** — und sie wächst überproportional mit der Fehlerrate, weil die Zahl der
> mehrfach getroffenen Bezugsgruppen einem Geburtstagsproblem folgt.

Der gemessene Beleg steht in den Befunden 11 und 12: elf verletzte Rangfolgen bei zwei
Prozent, alle in Anfragen mit mehr als einer Skalierung, keine einzige in den 1.102 mit genau
einer; und ein mit der Fehlerrate wachsender Anteil von 0,00 / 0,49 / 0,90 / 2,14 Prozent.

**Warum das über diesen Prototyp hinausweist.** Der Befund betrifft **jeden** Fehlerinjektor,
der relationale Nebenbedingungen bedienen muss — und das ist jeder, der auf normalisierten
Daten arbeitet. Die Arbeit kann ihn gegen BART und Jenga stellen: Beide erzeugen
Verfälschungen unter Nebenbedingungen, und beide stehen vor derselben Frage, sobald zwei
Verfälschungen dieselbe Bezugsgruppe treffen. Er gehört damit zu den Punkten, an denen der
Prototyp etwas über das **Verfahren** zeigt und nicht nur über den Katalog.

Für die Limitationen ist er außerdem der bessere Beleg als eine allgemeine Bemerkung: **Der
Fehler wurde durch die eigene Messung gefunden, nicht durch Nachdenken.** Er war in keiner
der drei Hypothesen enthalten, mit denen die Suche begann, und er wäre ohne den Probelauf
über mehrere Ratenstufen erst in 1.680 Läufen aufgefallen — als scheinbar inhaltlicher
Trend der Held-out-Klasse HO2 über Faktor UV2.

### Die gewählte Lösung — Kohärenz zeitlich von der Verfälschung trennen

Die Varianten bleiben unverändert: Sie skalieren das Beitragstupel gegen den **sauberen**
Kontext, jede Anwendung unabhängig. Der dokumentierte Invariant „der Kontext zeigt immer den
sauberen Stand" bleibt bestehen, und keine Variante bekommt eine zweite Datenquelle.

Die Rangfolge wird **einmalig am Ende des Laufs** nachgeführt, über alle Anfragen mit
mindestens einer Skalierung und gegen den dann vorliegenden Endstand
(`src.injector.pipeline._ziehe_raenge_nach`). Das ist zugleich die sachlich richtige
Einordnung: Das Nachziehen des Rangs ist **keine Verfälschung, sondern Kohärenzpflege** —
genau deshalb sind diese Zellen als `mitgezogen` markiert und nicht Teil von `E`. Ein
Nachbearbeitungsschritt ist der Ort, an den sie gehören.

Umgesetzt über ein neues Merkmal `Variante.zieht_rang_nach`; es tragen genau die fünf
skalierenden Varianten F8-b, F8-c, F8-d, F8-e und HO2-b. Die Variante meldet damit nur an,
dass ihre Anfrage betroffen ist — nachgeführt wird zentral.

**Drei Eigenschaften, die eine Nachführung innerhalb der Variante nicht hätte:**

1. **Jede Rangzelle wird genau einmal geschrieben.** Keine Mehrfachschreibung, keine
   Sonderbehandlung im Kollisionsset.
2. **Die Endrangfolge ist eine reine Funktion des Endzustands** und hängt nicht mehr von der
   Reihenfolge der Injektionen ab. Für Architekturregel A2 ist das die stärkere Eigenschaft,
   und sie lässt sich in einem Satz erklären.
3. **Universum und Kandidatenmenge bleiben unberührt** — und damit die Bezugsgröße der
   Fehlerrate. Faktor UV2 bleibt sauber.

### Die verworfenen Alternativen und ihre Kosten

| Alternative | Warum verworfen |
|---|---|
| **(a) Rangfolge je Anwendung gegen den Arbeitsstand** | Behebt den Fehler, aber die Variante liest dann den Arbeitsstand statt des sauberen Kontexts. Der dokumentierte Invariant fällt, jede Variante bekommt eine zweite Datenquelle, und die Endrangfolge hängt weiterhin von der Reihenfolge der Injektionen ab. |
| **(b) Höchstens eine Skalierung je Anfrage** | Verkleinert das adressierbare Universum von HO2-b und F8 — und das Universum ist die **Bezugsgröße der Fehlerrate**, also genau die Größe, die UV2 variiert. Phase 4b hat diese Kopplung gerade entfernt; (b) führte sie durch die Hintertür wieder ein. Zusätzlich könnte die Variante bei der obersten Ratenstufe ihr Kontingent verfehlen und der Injektor abbrechen — bei 0,05 wären 294 von 3.044 Kandidaten betroffen. |

### Die Falle, und wie sie abgesichert ist

Der Kohärenzschritt darf **nur** Anfragen anfassen, in denen eine skalierende Variante
gewirkt hat. Ein pauschaler Reparaturlauf über alle Anfragen wäre ein deutlich schwererer
Fehler als der behobene: **F6-b vergibt den Rang der Duplikatzeile absichtlich so, dass die
Rangfolge eine Lücke bekommt — das ist die Verfälschung selbst.** Ein Nachführen würde sie
stillschweigend reparieren, und F6-b wäre danach über R-043 nicht mehr auffindbar. Dasselbe
gilt für den doppelten Rang aus F6-a und F6-c.

Abgesichert ist das zweifach: Der Schritt läuft nur über die gemerkten Anfragen, **und** er
lässt Anfragen aus, in denen eine satzbasierte Variante eine Angebotszeile hinzugefügt hat
(relevant nur im Mischmodus, weil sonst je Lauf genau eine Klasse läuft). Dazu kommt der
Test `test_f6b_luecke_bleibt_bestehen`, der genau diese Nichteinmischung festhält.

Ebenfalls ausgelassen werden Rangzellen, die eine **andere** Variante als Trägerzelle
verfälscht hat — etwa F1 auf `angebot.rang` im Mischmodus. Sie werden nicht überschrieben.

### Regressionsprüfung

**HO2 über alle vier Ratenstufen, je 10.000 Anfragen:**

| Fehlerrate | R-044 vorher | R-044 nachher | Recall vorher | Recall nachher |
|---|---|---|---|---|
| 0,005 | 0 | **0** | 0,00000 | **0,00000** |
| 0,010 | 3 | **0** | 0,00223 | **0,00000** |
| 0,020 | 11 | **0** | 0,00410 | **0,00000** |
| 0,050 | 65 | **0** | 0,00968 | **0,00000** |

Die Held-out-Klasse HO2 bleibt jetzt auf **allen** Ratenstufen unentdeckt — genau wie
konstruiert. Der scheinbare Trend über UV2 ist verschwunden, weil er nie einer war.

**F8 und F4 bei zwei Prozent:**

| Klasse | Kennzahl | vorher | nachher |
|---|---|---|---|
| F8 | Recall (`mitgezogen=False`) | 0,3084 | 0,3061 |
| F8 | Precision | 0,8349 | 0,8368 |
| F8 | Trägerzellen `n` | 5.328 | 5.328 |
| F8 | mitgezogene Zellen | 3.705 | 3.603 |
| F4 | Recall / Precision | 1,0000 / 0,2969 | 1,0000 / 0,2969 |

Die Größenordnung stimmt, und die kleinen Abweichungen sind erklärt, nicht wegerklärt:

- Die **Trägerzellen sind unverändert** (5.328). Das muss so sein — der Kohärenzschritt fasst
  keine Trägerzelle an. Die Bezugsgröße der Fehlerrate ist unberührt.
- Die **mitgezogenen Zellen sinken um 102**, weil die Rangfolge jetzt einmal am Ende gegen
  den Endstand berechnet wird statt mehrfach gegen den sauberen Stand. Mehrfachschreibungen
  entfallen, und Ränge, die sich zwischenzeitlich hin- und zurückbewegten, bleiben stehen.
- Der **Recall sinkt um 0,0023**, weil auch auf F8 die R-044-Treffer verschwinden: vorher
  fing der Katalog dort 12 Zellen über die Sortierregel, jetzt null. Das ist eine
  **Verbesserung der Messung**, kein Verlust: Diese Treffer waren „Nebenwirkung erkannt" und
  nicht „Fehler erkannt" (Abschnitt 9 im Docstring von `metriken.py`).
- Die Kreuztabelle von F8 trägt jetzt ausschließlich Regeln, die auf Einheiten- und
  Skalierungsfehler zielen — R-032, R-052, R-053, R-054. R-044 kommt nicht mehr vor. Der
  F8-Recall wird damit vollständig von Regeln getragen, die für diese Fehlerart hergeleitet
  wurden.
- F4 ist **unverändert**, wie es sein muss: Die Klasse erzeugt keine mitgezogenen Zellen.

**Alle Prüfungen:**

| Prüfung | Erwartung | Ergebnis |
|---|---|---|
| R-044-Treffer auf HO2, alle vier Ratenstufen | 0 | **0** |
| HO2-Recall (Zellebene) | 0,000 | **0,00000** |
| R-044-Treffer auf F8 | — | **0** (vorher 6 Verstöße, 12 Zellen) |
| F8 in der Größenordnung unverändert | ja | 0,3061 gegen 0,3084 |
| F4 unverändert | ja | ja |
| Gegencheck über alle neu erzeugten Läufe | ohne Abweichung | ohne Abweichung |
| `test_f6b_luecke_bleibt_bestehen` | F6-b bleibt verletzt | grün |
| `test_rangfolge_bleibt_nach_skalierung_stimmig` (F8, HO2, Rate 0,05) | keine Verletzung | grün |

---

## Phase 6 — Versuchsplan, Statistik und Ergebnisdarstellung

**Der Regelkatalog bleibt unberührt.** Diese Phase misst, sie ändert nichts am Prototyp.
Geändert wurden ausschließlich `scripts/inject.py` und `scripts/evaluate.py`, und zwar
abwärtskompatibel um zwei Schalter (siehe „Zwei neue Schalter" weiter unten).

### Entscheidung 1 — vier statt sechs Ratenstufen im Hauptversuch

- **Datum:** 2026-08-12
- **Sachlage:** `spec/03`, Abschnitt 3 nennt sechs Stufen (0,5 / 1 / 2 / 5 / 10 / 20 Prozent).
  Der Hauptversuch fährt vier: **1 / 2 / 5 / 10 Prozent**.
- **Begründung:**
  - **0,005 entfällt.** Bei den knappen Klassen liegt die absolute Fehlerzahl dann im
    niedrigen zweistelligen Bereich; der klassenweise Recall streut dort stärker als der
    Effekt, den er zeigen soll.
  - **0,20 entfällt.** Abedjan et al. berichten reale Raten von 0,1 bis 34 Prozent.
    Zwanzig Prozent liegt am oberen Rand und ist für ein Vergleichsportal praxisfern.
- **Folge für den Umfang:** 7 Klassen × 4 Raten × 3 Verfahren = 84 Zellen × 20
  Wiederholungen = 1.680 Zellmessungen. Sie entstehen aus **560 Läufen**: Ein Lauf
  verfälscht einen Datensatz und lässt alle drei Verfahren darauf laufen.
- **Warum nicht drei Läufe je Zelle:** Die drei Verfahren sähen dann verschiedene
  Datensätze, und der gepaarte Wilcoxon-Test verlöre seine Paarung. Die Paarung ist der
  Grund für seine höhere Trennschärfe gegenüber dem ungepaarten Test.

### Entscheidung 2 — 20 statt 30 Seeds im Mischmodus

- **Sachlage:** `spec/03`, Abschnitt 3 nennt für den praxisnahen Mischmodus 30 Seeds, der
  Phasenprompt 20.
- **Entschieden: 20**, dieselbe Zahl wie im Hauptversuch.
- **Begründung:** Abbildung 10 stellt den Praxismix neben den Mittelwert über die isolierten
  Klassen. Hätte eine Seite 30 und die andere 20 Wiederholungen, unterschieden sich die
  Breiten der Konfidenzintervalle aus einem Grund, der nichts mit der Sache zu tun hat.

### Entscheidung 3 — die Konfiguration trägt keine Faktorstufen, und das bleibt so

- **Sachlage:** Der Phasenprompt geht davon aus, in `config/default.yaml` stünden inzwischen
  Ratenstufen. **Das ist nicht der Fall** — die Datei enthält Stichtag, Master-Seed,
  Datensatzgröße, Spartenverteilung, Schwellenwerte und Referenzdatenumfang, aber keine
  einzige Faktorstufe. Die Ratenstufen stehen in `spec/03`, Abschnitt 3.
- **Entschieden:** Der Versuchsplan bekommt eine **eigene** Datei `config/experiment.yaml`,
  gelesen von `src/evaluation/experimentplan.py`. `config/default.yaml` bleibt unverändert.
- **Begründung:** Die beiden Dateien haben verschiedene Lebensdauern. Die fachliche
  Konfiguration ist seit dem Freeze stabil und geht in jeden Lauf ein; der Versuchsplan ist
  eine Aussage über *dieses* Experiment. Sie zu vermischen hieße, den Master-Seed neben der
  Zahl der Wiederholungen zu führen — und eine Änderung des einen sähe aus wie eine des
  anderen.

### Entscheidung 4 — Teilversuch T6 ist nötig, nicht optional

- **Sachlage:** Seit der universumsproportionalen Zuteilung (Phase 4, Befund 4) bekommen
  knappe Varianten im faktoriellen Plan einstellige Fallzahlen: F4-f bei zwei Prozent eine
  einzige Injektion, F7-c fünf.
- **Entschieden:** Abbildung 5 und `t4_varianten.csv` stammen **ausschließlich** aus dem
  Teilversuch T6 (`--modus variante`), in dem jede Variante ihr Universum ausschöpft.
- **Deckelung, ausgewiesen statt stillschweigend:** `max_fehler: 3000`. Varianten mit
  kleinerem Universum werden erschöpfend injiziert, größere auf 3.000 gezogen. Bei 3.000
  liegt das Clopper-Pearson-Intervall selbst im ungünstigsten Fall p = 0,5 bei rund
  ±1,8 Prozentpunkten.
- **Die fünf Wiederholungen sind Replikate, keine Vergrößerung der Stichprobe.** Bei
  Varianten unterhalb der Deckelung injizieren alle fünf dieselben Zellen. `t4_varianten`
  berichtet deshalb das **Mittel** über die Wiederholungen und nicht ihre Summe — sonst wäre
  n dort fünfmal zu groß und das Intervall entsprechend zu eng.

### Entscheidung 5 — zwei Varianzquellen brauchen zwei Indizes

- **Sachlage:** Der Hauptversuch misst die **Injektionsvarianz** (fester Basisdatensatz,
  variierender Injektionsstrom), T5 die **Datenvarianz** (fester Injektionsstrom, zwanzig
  Basisdatensätze).
- **Entschieden:** Der Versuchsplan führt `basis_index` und `injektions_index` getrennt.
  Im Regelfall ist `injektions_index` gleich der Wiederholung und `basis_index` null.
- **Begründung:** Variierten beide zugleich, mäße T5 die **Summe** aus beiden Streuungen,
  und der Vergleich in Abbildung 8 verlöre seinen Sinn.

### Zwei neue Schalter in `scripts/inject.py` und `scripts/evaluate.py`

Beide sind abwärtskompatibel — ohne Angabe verhalten sich die Skripte exakt wie vorher, und
jeder bisherige Lauf bleibt bitgleich reproduzierbar.

| Schalter | Vorgabe | Zweck |
|---|---|---|
| `--basis-index` | `0` | Wählt den Basisdatensatz. `0` ist der kanonische aus `wurzel_seeds(master_seed).basis`. Nur T5 setzt ihn ungleich null. |
| `--injektions-index` | keine | Nummer, die in `seed_inject` eingeht; ohne Angabe die Wiederholung. Nur T5 hält sie fest, während `--basis-index` variiert. |

Damit ist **jeder** Lauf des Experiments von Hand nachvollziehbar, auch die des Teilversuchs
T5. `tests/test_experiment.py::test_manifest_gleicht_handlauf` belegt das: Der Runner und
ein Aufruf von `scripts/inject.py` mit denselben Faktorstufen erzeugen ein Manifest, das
sich in **keinem** Feld unterscheidet — einschließlich der SHA-256-Werte des sauberen und
des verfälschten Datensatzes.

### Entscheidung 6 — der Runner rechnet in einem Prozess, und das wird ausgewiesen

- **Sachlage:** Getrennt aufgerufen erzeugt `inject.py` den sauberen Datensatz und
  `evaluate.py` erzeugt ihn ein zweites Mal, um den verfälschten wiederherzustellen. Bei
  1.035 Läufen wären das rund 2.000 Datensatzerzeugungen zu je zwölf Sekunden — knapp sieben
  Stunden allein dafür.
- **Entschieden:** `scripts/run_experiment.py` erzeugt den sauberen Datensatz einmal je
  Arbeitsprozess und Faktorkombination und verfälscht ihn je Lauf neu.
- **Der Preis, ehrlich benannt:** Der Hashvergleich von `evaluate.py` ist im Runner trivial
  erfüllt, weil beide Seiten dasselbe Objekt sind. Er wird deshalb **nicht** als bestandener
  Nachweis geführt, sondern in `metrics.json` als `"identitaet"` gekennzeichnet. Der echte,
  prozessübergreifende Nachweis entsteht über `--stichprobe`: Dort läuft `scripts/evaluate.py`
  in einem eigenen Prozess, stellt den verfälschten Datensatz neu aus den Seeds her und
  vergleicht ihn Entität für Entität gegen das Manifest. Das Ergebnis steht in
  `results/reproduktionsstichprobe.json`.

### Entscheidung 7 — `PYTHONHASHSEED` wird erzwungen, nicht erhofft

`scripts/run_experiment.py` startet sich einmalig mit `PYTHONHASHSEED=0` neu, wenn die
Variable nicht gesetzt ist, und schreibt den Wert in `results/experiment_lauf.json`. Der
Neustart läuft über einen **Unterprozess** und nicht über `os.execve`: Unter Windows gibt es
kein echtes `exec`; die Bibliotheksfunktion legt dort einen neuen Prozess an und beendet den
alten sofort — die aufrufende Schale sähe den Aufruf als beendet an, während die Arbeit noch
läuft, und verlöre die Ausgabe.

Das Projekt umgeht die Streuung an den Stellen, die zählen (`_namensfaktor` hasht mit
SHA-256, es wird nicht über ungeordnete Mengen iteriert). „Wir haben aufgepasst" ist
allerdings kein Nachweis.

### Entscheidung 8 — `detections_*.parquet` werden standardmäßig nicht abgelegt

- **Sachlage:** Die Rohmeldungen je Verfahren wären bei 1.035 Läufen zweistellige Gigabyte.
- **Entschieden:** `schreibe_detections: false` als Vorgabe, `--detections` schaltet sie ein.
- **Begründung:** **Keine** Tabelle und **keine** Abbildung braucht sie. Die Regeldiagnose
  und die Kreuztabelle Regel × Fehlerklasse stehen bereits im Langformat; die Rohmeldungen
  wären eine dritte Fassung derselben Information. Für das Nachsehen an einem Einzelfall
  genügt `python scripts/evaluate.py` auf diesem Lauf.

### Entscheidung 9 — die Zuordnung Variante → Regel entsteht in der Auswertung

`spec/03`, Abschnitt 6 verlangt es wörtlich. Umgesetzt in `src/evaluation/varianten.py`:
Die Tabelle ist aus der **Spezifikation** abgeschrieben, nicht aus dem Quelltext des
Injektors, und `src/evaluation` importiert nichts aus `src/injector`. Der Preis dieser
Trennung ist eine Abschrift, die auseinanderlaufen kann; bezahlt wird er mit
`tests/test_evaluation/test_varianten.py`, das beide Seiten gegeneinander hält. Ein Test
darf beide kennen — der Produktivcode nicht.

Die Spalte „spiegelt Regel exakt" hat **drei** Stufen (ja / teilweise / nein), nicht zwei.
F2-a verletzt die Längenbedingung von R-002 nur bei Postleitzahlen mit führender Null, F2-k
trifft eine Musterbedingung, die Kleinbuchstaben nicht ausdrücklich ausschließt. Beide als
„spiegelt exakt" zu führen würde den Beleg gegen die Zirkularität schwächen; beide als
„spiegelt nicht" zu führen wäre in die andere Richtung geschönt.

### Entscheidung 10 — je Hypothese das passende Testverfahren, kein t-Test

| Hypothese | Behauptung | Primärtest | Warum nicht anders |
|---|---|---|---|
| HYP1 | Prototyp findet mehr als B0, ohne dass die Precision fällt | gepaarter Wilcoxon-Test, zwei Familien | Die drei Verfahren sehen denselben Datensatz; die Paarung ist vorhanden und wird genutzt |
| HYP2 | Der Recall unterscheidet sich zwischen den Klassen | Friedman-Test, danach 21 paarweise Wilcoxon-Tests | Sieben verbundene Gruppen auf denselben Blöcken |
| HYP3 | Die Precision steigt mit der Fehlerrate | Page-Trendtest über die geordneten Stufen | Ein Wilcoxon-Test verglicht zwei Stufen **ohne Ordnung** und ließe die Information ungenutzt, dass die Stufen aufsteigend sind |
| HYP4 | Der Unterschied zu B2 ist klassenabhängig | ART-ANOVA, Interaktionsterm | Das ist eine Interaktions- und keine Mittelwerthypothese |

Ein t-Test kommt nirgends vor: F1-Verteilungen sind nach oben durch 1 beschränkt, oft
linksschief und bei den Held-out-Klassen auf einen einzigen Wert entartet.

Die Multiplizitätskorrektur ist Holm-Bonferroni, **je Familie getrennt**. Die beiden Familien
von HYP1 (Recall und Precision) werden nicht gemeinsam korrigiert: Sie prüfen verschiedene
Kennzahlen, und eine gemeinsame Korrektur über vierzehn Vergleiche wäre unnötig streng — die
Precision-Familie dient der Absicherung, nicht der Bestätigung.

### Entscheidung 11 — der Bootstrap muss entarten dürfen

Die BCa-Beschleunigung wird aus einem Jackknife geschätzt. Liefern alle Wiederholungen
denselben Wert — bei den Held-out-Klassen mit Recall null der **Erwartungsfall** —, ist die
Jackknife-Streuung null und die Beschleunigung ein Bruch `0/0`.

`src/evaluation/statistik.bootstrap_ci` fängt das ab und weicht auf ein exaktes
**Clopper-Pearson-Intervall** aus, sobald der Aufrufer die zugrunde liegenden Anteilszahlen
mitgibt. Das Ergebnis sagt in seinem Feld `art` immer, welcher Weg genommen wurde; in
Abbildung 4 sind diese Balken mit `CP` markiert. Ohne den Ausweichweg bräche ausgerechnet die
Abbildung, die das „inwieweit" der Forschungsfrage beantwortet.

### Entscheidung 12 — die Warnung zur Stichprobengröße rechnet, statt zu raunen

`seed_warnung` bestimmt die Grenzen des exakten Wilcoxon-Tests für die **tatsächliche** Zahl
der Wiederholungen. Eine pauschale Warnung wäre je nach Familiengröße schlicht falsch. Bei
zehn Wiederholungen gilt:

| Familie | kleinster erreichbarer korrigierter p-Wert | zweitkleinster |
|---|---|---|
| 7 Vergleiche (HYP1, HYP4) | 0,0137 — signifikant | 0,0234 — signifikant |
| 21 Vergleiche (HYP2) | 0,0410 — signifikant | 0,0781 — **nicht** mehr |

Bei den geplanten 20 Wiederholungen greift die Warnung nicht; sie steht für den Fall, dass
jemand die Serie verkleinert.

---

## Phase 6, Nachtrag — zwei Metrikebenen, zwei Familiengrößen, zwei Zählweisen

**Kein Eingriff in Regelkatalog, Generator oder Injektor.** Geändert wurden Auswertung und
Berichterstattung. Zwei der sechs Nachträge haben inhaltliche Folgen für die Hypothesen.

### Befund 15 — der Prävalenzeffekt ist ein Artefakt der Berichtskonvention

- **Datum:** 2026-08-12
- **Auslöser:** `p = 3,6 · 10⁻¹⁷` bei `ρ = 0,069` ist ein hochsignifikanter, praktisch
  bedeutungsloser Effekt. Die Erklärung stand schon in den eigenen Zahlen: Auf der
  Constraint-Ebene erreichen F2, F3, F4 und F5 eine Precision von 1,000 bei unverändertem
  Recall. Wo die Precision bereits eins ist, kann kein Prävalenzeffekt entstehen.
- **Vermutung:** Der gemessene Trend ist kein Prävalenzeffekt des Verfahrens, sondern einer
  der Berichtskonvention. Auf der Zellebene erzeugt jede Injektion über mehrspaltige Regeln
  zusätzliche Falschmeldungen; ihre Zahl wächst mit der Injektionszahl. Die Precision steigt
  deshalb kaum, obwohl sie es bei konstanten Fehlalarmen deutlich müsste.
- **Prüfung:** Page-Trendtest auf **beiden** Metrikebenen.

| Ebene | Page *L* | *p* | Spearman ρ | einzeln signifikante Klassen |
|---|---|---|---|---|
| Zellebene | 3.785 | 3,6 · 10⁻¹⁷ | 0,069 | 3 von 7 |
| Constraint-Ebene | 3.494 | **0,570** | −0,002 | **0 von 7** |

- **Ergebnis: Die Vermutung trifft zu.** Der Effekt verschwindet vollständig. HYP3 ist damit
  nicht „schwach gestützt", sondern präzise beantwortbar: **Der Prävalenzeffekt existiert
  auf der Zellebene und ist dort ein Artefakt der Konvention.** Das ist eine deutlich
  stärkere Aussage als ein kleines ρ.
- **Umgesetzt:** `pruefe_hyp3` rechnet beide Ebenen, `t2_fehlerraten.csv` führt beide
  Precision-Spalten samt Differenz, `results/hypothesen.md` stellt sie nebeneinander. Die
  Entscheidung lautet „teilweise gestützt" mit ausformulierter Begründung.

### Befund 16 — B2 verliert auch auf seiner eigenen Primärebene

- **Datum:** 2026-08-12
- **Sachlage:** Für B2 war die **Satzebene** als Primärvergleich festgelegt (Phase 5,
  Aufgabe 3), die Zellebene nur zusätzlich. Der erste Bericht führte B2 mit `F1 = 0,026` —
  das ist die Zellebene.
- **Warum die Festlegung besteht:** B2 markiert ganze Zeilen. Die Umrechnung „markierte
  Zeile markiert alle ihre befüllten Zellen" deckelt seine Precision auf etwa den Kehrwert
  der Spaltenzahl. Ein Zellvergleich misst dort zu einem großen Teil die Umrechnung und
  nicht das Verfahren.
- **Ergebnis:**

| Ebene | ART-ANOVA Interaktion | η²ₚ | Prototyp gewinnt | B2 gewinnt |
|---|---|---|---|---|
| Satzebene (primär) | *F*(6, 266) = 5776,7, *p* < 10⁻²⁰⁰ | 0,992 | 7 von 7 | **0** |
| Zellebene (Kontrolle) | *F*(6, 266) = 1590,0, *p* < 10⁻²⁰⁰ | 0,973 | 7 von 7 | 0 |

  B2 ist auf der Satzebene deutlich besser — bei F1 etwa 0,473 statt 0,066 — und liegt
  trotzdem in **keiner** Klasse vorn. Die Aussage „B2 gewinnt in keiner Klasse" ist damit
  belastbar, und der naheliegende Einwand ist vorweggenommen.
- **Dazu gehört der Hinweis, der die Aussage trägt:** B2 durfte seine `contamination`-Stufe
  über die beste F1 der Satzebene wählen und bekam dafür den Ground Truth zu sehen. Der
  Prototyp bekommt keine vergleichbare Anpassung. Ein Verfahren, das trotz dieses Vorteils
  auf seiner eigenen Primärebene in keiner Klasse gewinnt, verliert überzeugend.

### Entscheidung 13 — die Holm-Familie zählt nur durchgeführte Tests

In F4, F5, F7 und F8 meldet B0 **überhaupt nichts**; seine Precision ist dort
konventionsgemäß 0,0 — eine Festlegung, keine Messung. Diese vier Precision-Vergleiche
werden deshalb **nicht durchgeführt** und als „nicht anwendbar" ausgewiesen.

Die Konsequenz für die Korrektur: **Die Familie HYP1-Precision hat drei Vergleiche, nicht
sieben.** Eine Familiengröße, die nicht zur Zahl der berichteten Tests passt, korrigiert
gegen Tests, die es nicht gibt. Umgesetzt über `Vergleich.anwendbar`; `Familie.anzahl` ist
die Holm-Größe, `Familie.berichtet` die Zahl der Tabellenzeilen, und beide stehen in jeder
Ausgabe nebeneinander.

Die Entscheidung zu HYP1 ändert sich dadurch nicht — die Korrektur wird schwächer, nicht
stärker. Das Ergebnis wird schärfer: In **allen drei** Klassen, in denen die
Precision-Bedingung überhaupt prüfbar ist, fällt die Precision signifikant.

### Entscheidung 14 — die Laufzahl bekommt ihre Herleitung

Der Phasenprompt sprach von 1.680 Läufen, gelaufen sind 1.035. Das ist keine Reduktion,
sondern eine andere Zählweise:

- Ein **Injektionslauf** verfälscht einen Datensatz.
- Eine **Verfahrensauswertung** ist ein Verfahren auf einem solchen Lauf.

Der Hauptversuch hat 7 Klassen × 4 Raten × 20 Wiederholungen = **560 Injektionsläufe**,
ausgewertet mit drei Verfahren = **1.680 Verfahrensauswertungen**. Über alle Blöcke sind es
**1.035 Injektionsläufe** und **2.370 Verfahrensauswertungen**.

„1.035 von 1.680 geplanten Läufen" wäre eine verdeckte Stichprobenreduktion — genau das, was
der Versuchsplan ausschließen wollte, und es stünde als Vorwurf im Raum, obwohl nichts
fehlt. Beide Zahlen stehen mit Herleitung je Block in `results/experiment_lauf.json` unter
`zaehlweise` und in der README.

### Befund 17 — alle vier stummen Regeln sind Überdeckung, keine Limitation

Die Unterscheidung wird **aus den Ground-Truth-Logs abgeleitet** und nicht behauptet: Für
jede Regel wird geprüft, ob eine Injektionsvariante auf sie zielt und ob ihre Felder in der
Serie überhaupt verfälscht wurden.

| Regel | Entität | Variante zielt darauf | Felder verfälscht | Einordnung |
|---|---|---|---|---|
| R-030 | risiko_kfz | nein | ja | Überdeckung |
| R-047 | angebot | nein | ja | Überdeckung |
| R-048 | risiko_hausrat | nein | ja | Überdeckung |
| R-049 | alle | nein | ja | Überdeckung |

Keine ist „in diesem Aufbau nicht prüfbar" — das wäre der Fall, wenn ihre Felder von keiner
Injektion getroffen würden, und wäre eine Limitation statt eines Ergebnisses.

Aufschlussreich ist R-049 (Auflösbarkeit aller Fremdschlüssel): `angebot.tarif_id` **wird**
von F7-a verfälscht, aber auf eine andere *existierende* Tarif-ID. Der Fremdschlüssel bleibt
auflösbar, und die Regel schweigt korrekt. Sie war der Verfälschung ausgesetzt und hat sie
richtig nicht als Verstoß gewertet.

### Befund 18 — die Vorab-Zuordnung trifft bei 45 von 60 Varianten zu

Die Spalte „spiegelt Regel exakt" in `spec/03`, Abschnitt 2 wurde **vor** jeder Messung
festgelegt. Sie ist damit eine falsifizierbare Erwartung; ihre Trefferquote ist eine
Gütezahl der Methode und kein Makel der Spezifikation, wo sie danebenliegt.

Geprüft wird gegen einen Recall von 0,5 — die einzige Schwelle, die sich ohne Blick auf die
Daten begründen lässt; bei der Einstufung „teilweise" gegen einen Wert echt zwischen 0 und 1.

**45 von 60 treffen zu.** Die 15 Abweichungen haben zwei Richtungen, und der Unterschied ist
wichtiger als die Quote:

- **Überschätzt (4): F1-a, F8-a, F8-c, F8-d.** Eine greifende Regel war erwartet, der
  Katalog findet die Variante trotzdem überwiegend nicht. F1-a ist der klarste Fall:
  `spec/03` führt sie als „ja (R-001)", gemessen sind 0,219 — weil F1 alle Felder trifft und
  R-001 nur Pflichtfelder prüft. Diese vier **schwächen** die Aussage über den Katalog.
- **Unterschätzt (11): F1-c, F1-d, F1-e, F1-f, F2-a, F2-h, F2-i, F2-k, F3-g, HO1-a, HO1-b.**
  Keine Regel war erwartet, der Katalog findet sie trotzdem — die Sentinelwerte über R-025,
  die Fremdformate über die Typregeln, HO1 über R-046. Diese elf **verkleinern den Kontrast**
  zwischen spiegelnden und nicht spiegelnden Varianten und relativieren den Abstand 0,918 zu
  0,499 aus Abbildung 5.

Die Zahl steht in `t4_varianten.csv` (Spalten `erwartung_eingetroffen` und
`abweichungsrichtung`), im Kopf der Markdown-Fassung und in der Bildunterschrift von
Abbildung 5.

### Präzisierung — HO1 ist als Held-out-Klasse bestätigt, nicht widerlegt

Der satzbasierte Recall von 0,795 ist **keine** Generalisierung des Katalogs auf unscharfe
Dubletten:

> Der Katalog erkennt die Beinahe-Dublette nicht an der Namensähnlichkeit, sondern an einer
> davon unabhängigen Integritätsverletzung: Der duplizierte Personensatz erzeugt einen
> zweiten Versicherungsnehmer in derselben Anfrage, und das meldet R-046.

Die Kreuztabelle zeigt es: bei HO1 ausschließlich R-046. Auf der Zellebene bleibt der Recall
0. Als Held-out-Klasse für **Ähnlichkeitserkennung** ist HO1 damit bestätigt — keine Regel
des Katalogs vergleicht Namen oder Adressen auf Ähnlichkeit, und keine hat es getan.

Ohne diesen Satz liest sich 0,795 wie eine Generalisierung des Katalogs, und das wäre die
falsche Schlussfolgerung. Die Bildunterschrift von Abbildung 4 formuliert ihn jetzt selbst,
und zwar **abhängig von den Daten**: Sie ergänzt ihn nur, wenn ein Held-out-Balken
tatsächlich über zehn Prozent liegt.

### Randfall, den erst die Testsuite gefunden hat

Auf der Constraint-Ebene ist die Precision mehrerer Klassen über alle Ratenstufen exakt
1,000. Die Spearman-Korrelation ist auf einer konstanten Reihe **nicht definiert**; SciPy
warnt, und die Testsuite behandelt Warnungen als Fehler. `spearman` gibt dort jetzt
`effekt = None` mit Begründung zurück statt einer Null. Eine Null läse sich als „gemessen,
kein Zusammenhang" — und das ist etwas anderes als „nicht messbar".

---

## Phase 6, zweiter Nachtrag — die dritte Kategorie und zwei Notizen

**Kein Eingriff in Regelkatalog, Generator oder Injektor.** Es kam kein einziger Lauf hinzu:
Die neue Auswertung liest die bereits vorhandene Kreuztabelle anders.

### Festlegung — der Hauptkontrast bleibt auf der Vorab-Einteilung

Der Abstand 0,918 zu 0,499 aus Abbildung 5 wird **nicht** neu gerechnet. Er beruht auf der
Spalte „spiegelt Regel exakt" aus `spec/03`, und die stand fest, bevor irgendetwas gemessen
wurde — genau darin liegt ihr Wert.

Eine nachträglich korrigierte Einteilung, aus der ein größerer Kontrast folgte, wäre an die
Daten angepasst und damit wertlos als Beleg gegen den Zirkularitätsvorwurf, dem sie dient.
Falls eine solche Fassung je gerechnet wird, gehört sie ausschließlich als **ausdrücklich
als post hoc gekennzeichnete Sensitivitätsrechnung** in den Anhang, nie als Hauptzahl und
nie in Abbildung 5. Abbildung 5 ist unverändert geblieben.

### Befund 19 — der Kontrast ist konservativ, nicht optimistisch

Elf Unterschätzungen stehen vier Überschätzungen gegenüber. Die falsch eingeordneten
Varianten liegen damit **überwiegend in der unteren Gruppe** und werden dort besser erkannt,
als die Einteilung erwartet hat; sie ziehen deren Mittelwert nach oben.

> Der gemessene Kontrast von 0,918 zu 0,499 ist konservativ. Die Abweichungen zwischen
> Vorab-Einteilung und Messung wirken überwiegend in Richtung eines kleineren Unterschieds;
> bei zutreffender Einteilung fiele er größer aus.

Eine Hauptzahl, die als Untergrenze ausgewiesen ist, ist eine deutlich stärkere Position als
eine, die verteidigt werden muss. Der Satz steht in der Bildunterschrift von Abbildung 5 und
in der README — und er wird **datenabhängig** erzeugt: Er erscheint nur, solange die
Unterschätzungen tatsächlich überwiegen.

### Befund 20 — Kategorie B: Regeln fangen, wofür sie nicht entworfen wurden

Die Vorab-Einteilung ist binär, das Ergebnis ist es nicht. Die Kreuztabelle `regel_id` gegen
Variante enthält bereits, **welche** Regel getroffen hat; im Teilversuch T6 injiziert jeder
Lauf genau eine Variante, also ist die Zuordnung eindeutig. Das ist keine Umetikettierung,
sondern eine Messung — die Regel-ID steht im Ergebnis und wird nicht neu vergeben.

| Kategorie | Bedeutung | Anzahl |
|---|---|---|
| A | erkannt durch die Regel, die `spec/03` zuordnet | 44 |
| B | erkannt, aber durch eine **andere** Regel | 5 |
| C | nicht erkannt | 5 |
| S | satzbasierte Klasse, zellbasierte Zuordnung nicht definiert | 6 |

**Kategorie B im Einzelnen:**

| Variante | erwartet | tatsächlich getroffen | Recall |
|---|---|---|---|
| F2-h Datum im Fremdformat | R-008 | R-009, R-001 | 1,000 |
| F2-i Datum als Excel-Serial | R-008 | R-009, R-001 | 1,000 |
| F2-k TSN in Kleinbuchstaben | R-007 | R-008, R-051 | 1,000 |
| F3-g SF-Klasse als Integer | R-011 | R-013 | 1,000 |
| F8-e alle Angebote durch 12 | *(keine)* | R-053 | 0,121 |

> Eine Variante, die von einer Regel gefangen wird, die **nicht gegen sie entworfen wurde**,
> ist das Gegenteil von Zirkularität.

Der Katalog hat dort eine Deckung, die über seine eigene Herleitung hinausreicht — ein
Ergebnis über das Verhältnis von Regelkatalog und Fehlertaxonomie und nicht bloß eine
Korrektur an `spec/03`.

**Der bemerkenswerteste Fall ist F8-e.** Die Variante soll die strukturelle Grenze
relationaler Plausibilitätsprüfung zeigen: R-054 vergleicht gegen den Median der übrigen
Angebote, und wenn alle Angebote einer Anfrage skaliert werden, wandert der Median mit —
R-054 *kann* sie konstruktionsbedingt nicht finden. Gefunden wird sie trotzdem zu 12,1 %,
nämlich von **R-053**, einer Regel über die absolute Größenordnung. Die Grenze der einen
Prüfform wird von einer anderen teilweise aufgefangen. Das gehört in die Diskussion neben
Befund 13 (dem strukturellen Kern der Framework-Grenze).

Dieselbe Logik von der anderen Seite zeigt R-049: Sie schweigt korrekt, weil F7-a den
Fremdschlüssel auf eine andere *existierende* Tarif-ID umbiegt.

### Korrektur an der eigenen ersten Fassung — Kategorie S

Die erste Fassung der Kategorisierung führte **F6-a bis F6-d und HO1-a/b als „nicht
erkannt"**, obwohl F6-a bis F6-c satzbasiert einen Recall von 1,000 erreichen. Ursache: Die
Kreuztabelle ist **zellbasiert** definiert, und diese Klassen erzeugen zusätzliche Zeilen —
auf der Zellebene haben sie keine einzige Wahrheitszelle, jede Zellmeldung dort ist ein
Fehlalarm, und die Frage „welche Regel hat den Fehler gefunden" ist gar nicht gestellt.

Sie nach C zu sortieren wäre eine glatte Falschaussage gewesen. Eingeführt ist deshalb eine
vierte, ausdrücklich benannte Ausprägung **S** samt der Spalte `meldende_regeln`, die für
diese Varianten nennt, welche Regeln in ihren Läufen überhaupt gemeldet haben — eine
schwächere Aussage als „hat den Fehler gefunden", und sie ist als solche gekennzeichnet.

Für HO1 bestätigt sie die Deutung: ausschließlich **R-046**, also die Integritätsverletzung
und nicht die Namensähnlichkeit.

**Aufgefallen ist der Fehler beim Gegenlesen der Kategorienverteilung** — vier F6-Varianten
mit Recall 1,000 in der Spalte „nicht erkannt" sind ein Widerspruch, den die Zahlen selbst
zeigen. Es gibt keinen automatischen Test, der ihn gefunden hätte; die Kategorien waren
vorher nicht Teil der Auswertung.

### Notiz 1 — „nicht messbar" ist nicht „gemessen null"

`spearman` gibt bei einer konstanten Reihe `effekt = None` mit Begründung zurück statt einer
Null. Der Grund steht jetzt im Docstring, zusammen mit dem Querverweis auf denselben
Gedanken bei B0: Meldet ein Verfahren in einer Klasse gar nichts, ist seine Precision
konventionsgemäß 0,0 — eine Festlegung und keine Messung, und der Vergleich dagegen wird als
„nicht anwendbar" geführt.

Beide Male geht es um denselben Fehler: eine Zahl auszuweisen, wo keine gemessen wurde. Er
fällt später nicht mehr auf, weil eine Null in einer Ergebnistabelle nicht danach aussieht.

### Notiz 2 — wie der T4-Kennungskonflikt gefunden wurde

Der Teilversuch T4 besteht aus drei Blöcken mit derselben Kennung und verschiedenen
Datensatzgrößen. Die erste Fassung der Laufzahl-Herleitung schlüsselte je Kennung in ein
Wörterbuch auf und ließ damit **zwei der drei Blöcke verschwinden**: Der Laufbericht wies
1.025 statt 1.035 Injektionsläufe aus.

Die Abweichung betraf genau die zehn Läufe, die T4 bei 1.000 und 10.000 Anfragen rechnet.
Nichts hätte darauf hingewiesen — die Serie war vollständig, alle Artefakte lagen vor, kein
Test schlug an. Gefunden wurde er allein durch den Abgleich der aufgeschriebenen Herleitung
mit dem Versuchsplan.

**Das ist selbst ein kleines Ergebnis über die Arbeitsweise:** Die Anforderung, eine Zahl
nicht nur zu nennen, sondern ihre Herleitung aufzuschreiben, hat einen stillen Datenverlust
sichtbar gemacht. Eine Transparenzanforderung ist hier keine Fleißaufgabe gewesen, sondern
ein Prüfmittel.
