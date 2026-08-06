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
- Wertebereiche und Schwellenwerte, einschließlich der Werte in `config/default.yaml`,
- die Geltungsbereiche, also welche Entitäten und Felder eine Regel betrifft,
- die Schweregrade `HART` und `WARNUNG`,
- die Zuordnung zu den Achsen A (Granularität), B (Fehlerklasse) und C (Erkennbarkeitsgrad).

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
