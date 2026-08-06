# Verteilungsquellen

Für jedes Feld mit nicht-uniformer Verteilung wird hier festgehalten: Feldname, gewählte
Verteilung, Parameter und Quelle der Annahme. Grundlage ist `spec/01_datenmodell.md`,
Abschnitt 4.

**Zweck:** Im Kolloquium ist eine ausdrücklich gekennzeichnete Modellannahme deutlich
besser als eine unbelegte Zahl. Wo keine öffentliche Quelle existiert, steht das hier
ausdrücklich.

---

## 1. Verpflichtend zu belegende Verteilungen

Diese Tabelle stammt aus `spec/01_datenmodell.md`, Abschnitt 4. Die Spalte „Status" gibt
an, in welcher Phase die Verteilung umgesetzt wird.

| Feld | Quelle | Status |
|---|---|---|
| `geburtsdatum` / Altersverteilung | Zensus 2022 bzw. Destatis Altersstruktur | Phase 2 |
| `wohnflaeche_qm`, `baujahr` | Zensus 2022, Gebäude- und Wohnungszählung | Phase 2 |
| `zuers_zone` | GDV Naturgefahren-Datenservice (92,4 / 6,1 / 1,1 / 0,4 %) | **Phase 1 — umgesetzt** |
| `vu_nummer` (Anbietergewichte) | GDV „Fakten zur Versicherungswirtschaft", Marktanteile | **Phase 1 — umgesetzt** |
| `jahresfahrleistung_km`, Fahrzeugalter | freMTPL2freq (CASdatasets) als Strukturvorbild | Phase 2 |
| Beitragsniveau | GDV-Durchschnittsbeiträge je Sparte | Phase 2 |

Ausdrücklich als **Modellannahme** gekennzeichnet (keine öffentliche Quelle verfügbar):
Regionalklassen-Zuordnung, SF-Beitragssatztabelle, Typklassen-Zuordnung.

---

## 2. Entscheidungen der Phase 1 — Referenzdaten

Alle sechs Tabellen entstehen deterministisch in `scripts/build_reference.py` aus
`master_seed` und `config/default.yaml`. Zur Laufzeit wird **nichts** nachgeladen.

### 2.1 `plz_ort.csv` — synthetisch, nach dem gescheiterten Realbezug

`spec/01_datenmodell.md`, Abschnitt 2.1, verlangt, zuerst echte PLZ-Daten zu beziehen
(OpenPLZ API oder BKG) und nur ersatzweise synthetisch zu erzeugen. Der Realbezug wurde
am 6. August 2026 versucht und **verworfen**. Die Gründe, in der Reihenfolge ihres
Gewichts:

1. **Das Unterscheidungszeichen des Zulassungsbezirks ist überhaupt nicht Teil der API.**
   Es bestimmt im Modell die Regionalklassen (R-058) und müsste in jedem Fall synthetisch
   erzeugt werden. Eine gemischte Tabelle aus echten PLZ und synthetischen Bezirken ist
   in der Arbeit schwerer zu verteidigen als eine durchgängig synthetische, weil der
   Leser je Spalte nachhalten müsste, was belegt ist und was nicht.
2. **Kein Massendownload.** Die API deckelt `pageSize` auf 50 und bietet keinen
   Bulk-Endpunkt. Ein vollständiger Abzug der Ortschaften bräuchte über 2.400 Anfragen an
   einen frei betriebenen Dienst.
3. **Der sparsame Weg liefert die falsche Granularität.** Über Kreise und Gemeinden wären
   rund 420 Anfragen nötig, jede Gemeinde trägt dort aber nur **eine** Postleitzahl.
   Großstädte wären mit einer statt mit fünfzig PLZ vertreten; die Leitzonen-Systematik
   wäre nicht mehr abgebildet.
4. **Reproduzierbarkeit.** Ein netzfreier Aufbau erfüllt Architekturregel A2 ohne
   Zusatzannahmen. `tests/test_reproduzierbarkeit.py` prüft die Bitgleichheit zweier
   Läufe; mit einer externen Quelle hinge dieser Nachweis an deren Verfügbarkeit und
   Datenstand.

**Umsetzung:** 8.000 Postleitzahlen, 400 Zulassungsbezirke.

| Merkmal | Verteilung / Aufbau | Quelle |
|---|---|---|
| Leitziffer (erste Stelle) | feste Gewichte je Leitzone 0–9, Summe 1 | Näherung der realen PLZ-Dichte, **Modellannahme** |
| PLZ-Bereich je Leitzone | `z0000`–`z9999`; Leitzone 0 ab `01000` | 00000–00999 sind real nicht vergeben |
| Zulassungsbezirk | zusammenhängender Nummernblock je Bezirk | bildet ab, dass ein Kreis einen zusammenhängenden PLZ-Bereich abdeckt; **Modellannahme** |
| Größe eines Bezirks | log-normal (σ = 0,7) über die Bezirke | erzeugt Großstädte und Landkreise nebeneinander; **Modellannahme** |
| Unterscheidungszeichen | ein bis drei Großbuchstaben, Anteile 5 / 35 / 60 % | Näherung der realen Längenverteilung; anschließend über alle Leitzonen gemischt |
| Bundesland | feste Gewichte je Leitzone | Näherung der realen Zuordnung, **Modellannahme** |
| Ortsname | Bestimmungswort + Grundwort, optional Zusatz (25 %) oder „Bad " (3 %) | rein synthetisch |

**Vereinfachende Annahmen, in der Arbeit zu kennzeichnen:**

- Eine PLZ gehört zu genau einem Zulassungsbezirk. Real können PLZ-Gebiete Bezirksgrenzen
  schneiden (so bereits in `spec/01`, Abschnitt 2.1 vermerkt).
- Ein Zulassungsbezirk liegt in genau einem Bundesland.
- Die Ortsnamen sind erfunden. Einzelne können zufällig mit realen Namen übereinstimmen;
  ein Bezug zu realen Orten besteht nicht.

### 2.2 `regionalklassen.csv` — Modellannahme

Das echte GDV-Verzeichnis ist nicht als Massendownload verfügbar; öffentlich sind nur die
Klassenanzahlen (12 / 16 / 9).

| Merkmal | Verteilung | Begründung |
|---|---|---|
| latenter Risikoindex je Bezirk | Standardnormal | |
| `regionalklasse_hp/_tk/_vk` | je 0,8 × Index + 0,6 × eigenes Rauschen, danach über die Normalverteilungsquantile auf das Klassenintervall abgebildet | ergibt die in `spec/01`, Abschnitt 2.2 geforderte, um die Mitte zentrierte Verteilung |

Die Gewichte 0,8 und 0,6 ergeben zusammen wieder Varianz 1; die drei Klassen sind dadurch
mit rund 0,64 korreliert, aber nicht identisch. **Das ist fachlich beabsichtigt:** Ein
Bezirk mit hoher Schadenlast ist es meist in allen drei Deckungen. Ohne diese Korrelation
prüfte R-058 gegen reines Rauschen.

### 2.3 `typklassen.csv` — Modellannahme

3.000 HSN/TSN-Kombinationen, 40 Hersteller. Hersteller- und Modellnamen sind erfunden.

| Merkmal | Verteilung | Begründung |
|---|---|---|
| HSN | eine je Hersteller, vierstellig mit führenden Nullen | Aufbau der Zulassungsbescheinigung Teil I, Feld 2.1 |
| TSN | innerhalb der HSN eindeutig, `[A-Z0-9]{3}` | Feld 2.2 |
| Modelle je Hersteller | log-normal (σ = 0,6), mindestens 1 | Modellannahme |
| `leistung_kw` | log-normal um 105 kW (σ = 0,42), auf 35–480 begrenzt; Elektro und Hybrid × 1,25 | Modellannahme, orientiert an der PKW-Bestandsstruktur |
| `antriebsart` | Benzin 45 %, Diesel 28 %, Hybrid 13 %, Elektro 11 %, Gas 3 % | Näherung des PKW-Bestands, **Modellannahme** |
| `neupreis_eur` | (6.000 + 330 × kW) × log-normal (σ = 0,28), auf 8.000–250.000 begrenzt, auf 10 € gerundet | Modellannahme |
| `typklasse_hp/_tk/_vk` | 0,45 × z(kW) + 0,45 × z(Preis) + 0,55 × Rauschen, danach auf das jeweilige Klassenintervall abgebildet | Typklassen folgen dem Schadenbedarf; ohne Kopplung an Leistung und Preis prüfte R-051 gegen Rauschen |

### 2.4 `vu_stammdaten.csv`

14 Anbieter mit klar synthetischen Namen („Nordstern Versicherung AG").

| Merkmal | Verteilung | Quelle |
|---|---|---|
| `marktanteil` | rechtsschief, Gewicht ∝ 1 / (Rang + 1,5)^1,1, anschließend gemischt und normiert | Form angelehnt an GDV „Fakten zur Versicherungswirtschaft"; die konkreten Werte sind **Modellannahme** |
| `quell_schnittstelle` | BIPRO_420 35 %, BIPRO_RNEXT 30 %, GDV 20 %, CSV_IMPORT 15 %; jede Schnittstelle mindestens einmal | Modellannahme; die Zuordnung Anbieter → Schnittstelle ist fest und trägt die Multi-Source-Fehlerklasse |

Die Marktanteile summieren nach Rundung auf sechs Nachkommastellen **exakt** auf 1; die
Restdifferenz wird dem größten Anbieter zugeschlagen.

### 2.5 `zuers_zonen.csv` — belegte Verteilung

| Merkmal | Verteilung | Quelle |
|---|---|---|
| `zuers_zone` | 92,4 / 6,1 / 1,1 / 0,4 % | GDV Naturgefahren-Datenservice |

**Umsetzung:** Die Zellzahlen je Zone stehen vorab fest (7.392 / 488 / 88 / 32 bei 8.000
PLZ); die Zuordnung erfolgt über die Rangfolge eines latenten Gefährdungsindex. Die
Anteile werden dadurch **exakt** getroffen, nicht nur im Erwartungswert.

Der Index trägt einen Bezirksanteil (Standardnormal je Bezirk plus 0,8 × Rauschen je PLZ).
Damit sind benachbarte Postleitzahlen ähnlich eingestuft — Hochwassergefährdung ist
räumlich geclustert, nicht unabhängig gestreut. Das ist eine **Modellannahme** zur
räumlichen Struktur; die Randverteilung selbst ist belegt.

### 2.6 `sf_beitragssatz.csv` — Modellannahme

Es gibt keine branchenweit verbindliche Tabelle; die Sätze sind versichererindividuell.
Die Regel ist deshalb als **Monotoniebedingung** formuliert, nicht als Abgleich gegen eine
feste Tabelle (`spec/01`, Abschnitt 2.6).

| Klasse | Satz | Herkunft |
|---|---|---|
| M | 245 % | Vorgabe `spec/01`, Abschnitt 2.6 |
| S | 155 % | dito |
| 0 | 100 % | dito |
| 1/2 | 70 % | dito |
| SF 1 … SF 50 | 16 + 42 × ((50 − i) / 49)^1,7, kaufmännisch auf ganze Prozent gerundet | konvexer Verlauf: die ersten schadenfreien Jahre bringen viel, die späteren wenig |

Die Ankerwerte SF 1 = 58 % und SF 50 = 16 % werden exakt getroffen.

#### Offener Punkt: „monoton" versus „streng monoton"

`spec/01`, Abschnitt 2.6, führt `beitragssatz_prozent` als **`int`** und fordert einen
über die numerischen Klassen **monoton fallenden** Verlauf. Der Phasenprompt formuliert
strenger: „streng monoton fallend".

**Beides zusammen ist rechnerisch unmöglich.** Zwischen 58 und 16 liegen 43 ganze Zahlen;
zu besetzen sind 50 Klassen. Eine streng fallende Folge ganzer Zahlen müsste 50
verschiedene Werte annehmen.

**Umgesetzt ist die Fassung aus der Spezifikation:** ganze Zahlen, Verlauf nicht steigend.
Es entstehen 12 Plateaus — das erste zwischen SF 26 und SF 27, die übrigen elf ab SF 31,
also durchgehend im oberen SF-Bereich, wo reale Beitragssatztabellen ebenfalls abflachen.
`tests/test_referenz.py` prüft entsprechend „nicht steigend" und den Abfall über die
Gesamtspanne.

Wenn strenge Monotonie gewünscht ist, gibt es genau zwei saubere Wege — beide erfordern
eine Änderung an `spec/01_datenmodell.md`:

| Weg | Änderung | Nebenwirkung |
|---|---|---|
| A | `beitragssatz_prozent` als `Decimal` mit einer Nachkommastelle | Feldtyp ändert sich; Serialisierung und Regelformulierung sind anzupassen |
| B | Ankerwerte spreizen, etwa SF 1 = 62 %, SF 50 = 13 % | die in `spec/01` genannten Ankerwerte „≈ 58" und „≈ 16" werden verlassen |

Bis zur Entscheidung bleibt es bei der Fassung der Spezifikation.

---

## 3. Was in dieser Phase bewusst **nicht** festgelegt wurde

- **ISO-4217-Katalog (R-012).** Der vollständige Katalog gültiger Währungscodes ist noch
  nicht hinterlegt. Er wird in Phase 3 als Referenzdatei ergänzt und nicht aus dem
  Gedächtnis in den Quelltext geschrieben. Bis dahin existiert nur die Konstante
  `WAEHRUNG_STANDARD = "EUR"`.
- **Numerischer Wert der SF-Sonderklassen.** `sf_numerischer_teil()` liefert für `M`, `S`,
  `0` und `1/2` bewusst `None`. R-029 und R-030 sprechen vom „numerischen Teil"
  beziehungsweise von „wenn beide numerisch"; welchen Zahlwert die Sonderklassen dabei
  annehmen, legt die Spezifikation nicht fest. Eine Festlegung (etwa `"0" → 0`) gehört
  vor der Umsetzung in `spec/02_regelkatalog.md`.
