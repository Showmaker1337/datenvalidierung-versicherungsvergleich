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
| `geburtsdatum` / Altersverteilung | Zensus 2022 bzw. Destatis Altersstruktur | **Phase 2 — umgesetzt** (3.2) |
| `wohnflaeche_qm`, `baujahr` | Zensus 2022, Gebäude- und Wohnungszählung | **Phase 2 — umgesetzt** (3.5) |
| `zuers_zone` | GDV Naturgefahren-Datenservice (92,4 / 6,1 / 1,1 / 0,4 %) | **Phase 1 — umgesetzt** |
| `vu_nummer` (Anbietergewichte) | GDV „Fakten zur Versicherungswirtschaft", Marktanteile | **Phase 1 — umgesetzt** |
| `jahresfahrleistung_km`, Fahrzeugalter | freMTPL2freq (CASdatasets) als Strukturvorbild | **Phase 2 — umgesetzt** (3.4) |
| Beitragsniveau | GDV-Durchschnittsbeiträge je Sparte | **Phase 2 — umgesetzt** (3.6) |

Ausdrücklich als **Modellannahme** gekennzeichnet (keine öffentliche Quelle verfügbar):
Regionalklassen-Zuordnung, SF-Beitragssatztabelle, Typklassen-Zuordnung.

---

## 2. Entscheidungen der Phase 1 — Referenzdaten

Alle sieben Tabellen entstehen deterministisch in `scripts/build_reference.py` aus
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

#### Monotonie: nicht-steigend, nicht streng fallend

`spec/01`, Abschnitt 2.6, fordert ausdrücklich `satz(SF n+1) ≤ satz(SF n)`. **Plateaus sind
zulässig und erwünscht.** Der Grund ist zweifach:

- **Rechnerisch.** Zwischen den Ankerwerten 58 und 16 liegen 43 ganze Zahlen; zu besetzen
  sind 50 Klassen. Eine streng fallende Folge ganzzahliger Prozentwerte müsste 50
  verschiedene Werte annehmen — das ist unmöglich.
- **Fachlich.** Reale Beitragssatztabellen flachen bei hohen Schadenfreiheitsklassen
  ohnehin ab; zwischen SF 40 und SF 45 unterscheidet sich der Satz bei vielen Versicherern
  nicht mehr. Die Plateaus bilden die Realität ab, sie sind kein Kompromiss.

Umgesetzt sind 12 Plateaus — das erste zwischen SF 26 und SF 27, die übrigen elf ab SF 31,
also durchgehend im oberen SF-Bereich. `tests/test_referenz.py` prüft „nicht steigend", den
Abfall über die Gesamtspanne **und** dass kein Plateau unterhalb von SF 20 auftritt: Dort
bringt jedes schadenfreie Jahr real noch eine spürbare Ersparnis, ein flacher Verlauf wäre
dort ein Modellfehler.

#### Zwei weitere Vereinfachungen, in der Arbeit zu benennen

| Vereinfachung | Modell | Realität |
|---|---|---|
| Höchste Klasse | SF 50 | Die **meisten Versicherer enden bei SF 35**. Klassen darüber existieren nur bei einzelnen Anbietern. Der breitere Bereich ist im Modell nützlich, weil er die Monotoniebedingung über eine längere Spanne prüfbar macht — er ist aber nicht marktüblich. |
| Startwert | SF 1 = 58 % | **Viele moderne Tabellen setzen SF 1 auf 100 %** und staffeln erst darunter. Der hier gewählte Wert folgt dem älteren Schema, in dem SF 1 bereits einen deutlichen Rabatt gegenüber der Klasse 0 bedeutet. |

Beide Punkte berühren die Regelmechanik nicht — R-013 prüft gegen den Katalog, und der
Beitragssatz ist als Monotoniebedingung formuliert, nicht als Abgleich gegen feste Werte.
Für die Realitätsnähe sind sie relevant und gehören deshalb in die Diskussion.

### 2.7 `waehrungen.csv` — belegte Referenzdaten

| Merkmal | Quelle |
|---|---|
| `code`, `name`, `numerisch` | ISO 4217, bezogen über das Python-Paket `pycountry` |

Die einzige Referenztabelle dieses Projekts, die **nicht** synthetisch ist und keine
Modellannahme enthält: Der ISO-4217-Katalog ist ein offizieller Standard, `pycountry`
führt ihn mit. Erzeugt werden 178 Einträge, sortiert nach `code`.

**Warum nicht im Quelltext.** Eine von Hand gepflegte Währungsliste fällt niemandem auf,
wenn sie falsch ist — und macht R-012 wertlos: Die Regel meldete dann Fehler, wo keine
sind, oder, schlimmer, keine, wo welche sind. `tests/test_referenz.py` bindet die
Referenzdatei deshalb an `pycountry` zurück.

**Versionsabhängigkeit.** ISO 4217 wird fortgeschrieben. Die Version von `pycountry`
(26.2.16) ist in `requirements.txt` gepinnt, weil sie den Inhalt der Datei und damit ihren
Hashwert bestimmt. Ein Versionswechsel kann die Tabelle verändern und ist wie jede andere
Änderung an den Referenzdaten zu behandeln.

**Zwei Stufen in R-012.** Der Katalog trägt nur die erste Stufe — existiert der Code
überhaupt? Die zweite Stufe fragt, ob er im Kontext dieses Systems zulässig ist, und dort
lautet die Antwort `EUR`. Beide Stufen werden getrennt gemeldet. Ein `USD` wäre
*syntaktisch gültig*, aber *fachlich unzulässig*; ein `EURO` wäre beides nicht. Diese
Unterscheidung taucht in der Arbeit als Beispiel wieder auf.

### 2.8 Ordinalskala der SF-Klassen

`spec/01`, Abschnitt 2.8 definiert **zwei** Abbildungen, weil R-029 und R-030
Verschiedenes messen. Beide liegen in `src/common/enums.py`.

| SF-Klasse | `schadenfreie_jahre()` | `sf_ordnung()` |
|---|---|---|
| `M` | 0 | −3 |
| `S` | 0 | −2 |
| `0` | 0 | −1 |
| `1/2` | 0 | 0 |
| `SF1` … `SF50` | 1 … 50 | 1 … 50 |

`schadenfreie_jahre()` bedient R-029 (nicht länger schadenfrei als Führerscheinbesitz).
Alle Sonderklassen bedeuten null schadenfreie Jahre; die Regel ist dort trivial erfüllt.
Das ist fachlich korrekt: Wer in der Malusklasse steht, hat gerade keine schadenfreie
Historie vorzuweisen.

`sf_ordnung()` bedient R-030 (Vollkasko-Klasse nicht besser als Haftpflicht-Klasse). Sie
braucht eine **totale** Ordnung, damit die Regel auch dann greift, wenn eine der beiden
Klassen eine Sonderklasse ist, statt den Vergleich stillschweigend zu überspringen.

Der Unterschied ist wesentlich und im Test festgehalten: Bei `schadenfreie_jahre()` sind
`M` und `1/2` gleich, bei `sf_ordnung()` liegen drei Stufen dazwischen. Eine einzige
Abbildung könnte nicht beides leisten.

Beide Funktionen geben `None` zurück, wenn der Wert nicht im Katalog steht. Das ist kein
Fehler der Funktion, sondern ein Befund von R-013 — deshalb wird keine Ausnahme geworfen
(vergleiche `spec/01`, Abschnitt 6: „Parsefehler = Befund, kein Absturz").

---

## 3. Nachtrag zu Phase 1 — die drei gemeldeten Lücken

Alle drei in Phase 1 gemeldeten Lücken sind entschieden und umgesetzt.

| Lücke | Entscheidung | Fundstelle |
|---|---|---|
| SF-Monotonie „monoton" gegen „streng monoton" | nicht-steigend; Plateaus sind zulässig und fachlich richtig | `spec/01`, Abschnitt 2.6 |
| Zahlwert der SF-Sonderklassen | zwei getrennte Abbildungen statt einer | `spec/01`, Abschnitt 2.8 |
| ISO-4217-Katalog | siebte Referenztabelle `waehrungen.csv`, erzeugt über `pycountry` | `spec/01`, Abschnitt 2.7 |

Zusätzlich bestätigt: Faker wird über `seed_instance()` geseedet, das klassenweite
`Faker.seed()` ist in `CLAUDE.md`, Abschnitt 4 nun ausdrücklich verboten — globaler Zustand
widerspricht Architekturregel A2.

---

## 4. Entscheidungen der Phase 2 — der saubere Datensatz

Alle Ziehungen laufen über `src/generator/verteilungen.py` und bekommen ihren
Zufallsgenerator übergeben. Die Teilströme sind in `src/generator/pipeline.py` fest
nummeriert; eine neue Ziehung bekommt eine neue Nummer, damit die übrigen Ströme
unverändert bleiben.

Wo unten **Modellannahme** steht, existiert keine öffentliche Quelle. Das ist kein Mangel,
sondern Transparenz — und im Kolloquium besser als eine unbelegte Zahl.

### 4.1 Anfrage

| Feld | Verteilung / Parameter | Quelle |
|---|---|---|
| `sparte` | exakte Aufteilung nach `config.sparten_verteilung` (35 / 20 / 15 / 30 %), anschließend gemischt. **Danach greift die Annahmebedingung der Kaskosparten** (siehe 4.4): realisiert 36,2 / 19,3 / 14,5 / 30,0 % | Konfiguration; die exakte Aufteilung statt einer Ziehung ist **Modellentscheidung** (Varianzreduktion) |
| `kanal` | WEB 42 %, MAKLER 24 %, APP 14 %, API_BIPRO 12 %, TELEFON 8 % | Modellannahme |
| `eingangszeitpunkt` | Tag gleichverteilt über 730 Tage vor `stichtag`; Uhrzeit über einen festen Tagesgang (Maximum 9–11 und 14–17 Uhr) | Modellannahme; der Tagesgang ist für keine Regel von Belang, fällt aber bei jeder Sichtprobe auf |
| `versicherungsbeginn` | Vorlauf log-normal, Median 20 Tage, σ = 1,10, gekappt bei 365 Tagen | Modellannahme |
| `anfrage_status` | NEU 5 %, TARIFIERT 18 %, ANGEBOT 45 %, ANTRAG 25 %, STORNIERT 7 % | Modellannahme |
| `zahlweise` | jährlich 35 %, monatlich 35 %, vierteljährlich 15 %, halbjährlich 12 %, Einmalbetrag 3 % — **unabhängig von der Beitragshöhe gezogen** | Modellannahme. Eine frühere Fassung koppelte beides an einen Ratenkorridor; die Kopplung ist entfallen, siehe 4.6 |
| `vorvertrag_vorhanden` | zwingend `True`, sobald `schadenfreie_jahre(sf_klasse_hp) > 0`; sonst mit 55 % | spec/01, Abschnitt 3.1 beziehungsweise Modellannahme |
| Angebote je Anfrage | gammaförmig über 3 bis 12 mit Modus 5 (Form 3,0, Skala 1,5); Mittelwert rund 6,3 → rund 63.000 Angebotszeilen bei 10.000 Anfragen | spec/01, Abschnitt 1 |

**Postleitzahl.** Für die Hausrat-Anfragen wird nach ZÜRS-Zone geschichtet gezogen: Die
Zellzahlen je Zone stehen über das Größte-Reste-Verfahren vorab fest, gezogen wird nur die
Postleitzahl innerhalb der Zone. Grund ist Zone 4 mit einem Anteil von 0,4 Prozent — bei
3.000 Hausratzeilen sind das zwölf erwartete Fälle bei einer Streuung von rund 3,5. Eine
gewöhnliche Ziehung verfehlt die von R-048 geforderte relative Toleranz von 30 Prozent in
etwa jedem dritten Lauf. **Die Randverteilung bleibt die belegte des GDV; nur die
Stichprobenstreuung entfällt.** Für alle übrigen Anfragen wird die PLZ gleichverteilt
gezogen.

### 4.2 Person

| Feld | Verteilung / Parameter | Quelle |
|---|---|---|
| `geburtsdatum` | 16 Fünfjahresgruppen von 18 bis 95 mit den Anteilen 2,6 / 6,2 / 7,0 / 7,6 / 7,8 / 7,4 / 6,9 / 8,4 / 9,3 / 8,7 / 7,6 / 6,3 / 5,8 / 5,0 / 2,5 / 0,9 %; innerhalb der Gruppe gleichverteilt | **Zensus 2022 / Destatis-Altersstruktur**, auf die Bevölkerung ab 18 Jahren umgerechnet und gerundet |
| `anrede` | HERR 52 %, FRAU 46 %, DIVERS 2 % der natürlichen Personen | Modellannahme |
| `anrede` = FIRMA | 6 % — **nur in der Sparte 130** | Modellvereinfachung, siehe 4.7 |
| `familienstand` | altersabhängig, vier Gruppen (≤ 29 / ≤ 49 / ≤ 69 / darüber) mit den Gewichten (85/13/2/0), (35/52/12/1), (16/62/17/5), (8/55/10/27) % für LEDIG / VERHEIRATET / GESCHIEDEN / VERWITWET | Modellannahme, an der Destatis-Struktur orientiert |
| `wohneigentum` | altersabhängig 15 / 42 / 60 / 62 %; juristische Personen 35 % | Modellannahme |
| zweite versicherte Person | 25 % je Anfrage | Modellannahme |
| `fuehrerschein_datum` | Erwerbsalter 17 (6 %), 18 (44 %), 19–20 (24 %), 21–25 (16 %), 26–40 (10 %), gekappt beim Alter der Person; Tag innerhalb des Erwerbsjahres gleichverteilt | Modellannahme, orientiert an der Altersverteilung der Fahranfänger |

### 4.3 Zahlung

| Feld | Verteilung / Parameter | Quelle |
|---|---|---|
| `iban` | Bankleitzahl gleichverteilt über 10.000.000–99.999.999, Kontonummer zehn Ziffern, Prüfziffer nach ISO 7064 Mod 97-10 über `src/common/iban.py` | ISO 13616 / ISO 7064 |
| `bic` | vier Buchstaben, Ländercode `DE`, zwei alphanumerische Zeichen, mit 55 % zusätzlich drei Filialstellen | ISO 9362 |
| `sepa_mandat_datum` | gleichverteilt zwischen Anfrageeingang und Versicherungsbeginn | Modellannahme |
| `kontoinhaber` | mit 92 % der Versicherungsnehmer, sonst ein abweichender Name | Modellannahme |

### 4.4 Kfz-Risiko

| Feld | Verteilung / Parameter | Quelle |
|---|---|---|
| Fahrzeugalter → `erstzulassung` | log-normal, Median 6 Jahre, σ = 0,70, gekappt bei 30 Jahren und beim 1. Januar 1990 | **freMTPL2freq (CASdatasets)** als Strukturvorbild; Parameter Modellannahme |
| `zulassung_auf_vn` | mit 45 % gleich der Erstzulassung (Neuwagen), sonst gleichverteilt bis zum Stichtag; Untergrenze zusätzlich der 18. Geburtstag | Modellannahme |
| `jahresfahrleistung_km` | log-normal, Median 12.000 km, σ = 0,45, gerastert auf 500 km, gekappt auf 1.000–60.000 | **freMTPL2freq** als Strukturvorbild; spec/01, Abschnitt 3.3 |
| `fahrzeugwert_aktuell` | Restwertkurve `exp(−0,16 × Alter)`, Untergrenze 10 % des Neupreises, log-normale Streuung σ = 0,10, gekappt beim Neupreis | Modellannahme |
| `art_kennzeichen` | E-Kennzeichen mit 40 % bei ELEKTRO oder HYBRID, sonst Saisonkennzeichen mit 7 % | Modellannahme; die Bindung an den Antrieb folgt dem EmoG |
| `nutzungsart` | privat 85,5 %, geschäftlich 9 %, gemischt 5 %, Taxi 0,5 % | Modellannahme |
| `eigentumsverhaeltnis` | Eigentum 82 %, Leasing 18 % | Modellannahme |
| `nutzerkreis` | VN 45 %, VN_PARTNER 32 %, VN_FAMILIE 15 %, BELIEBIG 8 % | Modellannahme |
| `abstellplatz` | Garage 35 %, Straße 35 %, Stellplatz 20 %, Carport 10 % | Modellannahme |
| `schaeden_letzte_5j` | 72 / 18 / 6 / 2,5 / 1 / 0,5 % für 0 bis 5 Schäden | Modellannahme |
| `sf_klasse_hp` | Sonderklassen zusammen 5,5 % (M 0,8 %, S 1,2 %, `0` 2,0 %, `1/2` 1,5 %); sonst Stufe = Obergrenze × Beta(3,0; 1,2), gerundet. Obergrenze = min(Alter − 17, Jahre seit Führerscheinerwerb, 50) | Modellannahme; die Obergrenze folgt R-029 und dem Führerscheinbesitz |
| `sf_klasse_vk` | Abstand zur Haftpflichtklasse auf der Ordinalskala: 0 (75 %), 1 (13 %), 2 (8 %), 3 (4 %); nach unten begrenzt auf `0` | Modellannahme; der nicht negative Abstand sichert R-030, die Untergrenze die Annahmebedingung unten |

#### Annahmebedingung der Kaskosparten

> In den Sparten **052 (Vollkasko)** und **053 (Teilkasko)** erhalten Risiken mit
> `sf_klasse_hp` ∈ {`M`, `S`} **kein Angebot**. In der Haftpflicht (051) bleiben sie
> erhalten.

**Fachliche Begründung.** Versicherer nehmen Risiken in der Malusklasse (Beitragssatz
245 %) oder in der Schadenklasse (155 %) in der Kasko überwiegend gar nicht an — die Kasko
unterliegt keinem Kontrahierungszwang. In der Haftpflicht besteht er dagegen nach § 5
PflVG, und die Einstufung ist dort fachlich relevant.

**Umsetzung als Annahmebedingung, nicht als Filter.** Die betroffene Anfrage wird als
Haftpflichtanfrage geführt und bekommt entsprechend nur Haftpflichtangebote; es entstehen
erst gar keine Kaskoangebote für diese Risiken. Die Mindestzahl bepreister Angebote je
Anfrage bleibt dadurch unberührt.

Die Kaskoklasse `sf_klasse_vk` wird zusätzlich nach unten auf `0` begrenzt. Sie wird aus der
Haftpflichtklasse nach unten gezogen und könnte die Bedingung sonst unterlaufen — eine
Anfrage mit Haftpflichtklasse `0` bekäme eine Vollkaskoklasse `M`, und der Beitragssatz von
245 % wäre über den Umweg der Kaskoeinstufung wieder im Datensatz.

**Warum das kein Wegdefinieren eines unbequemen Ausreißers ist.** Der Eingriff beseitigt
eine Konstellation, die im Modell entstehen kann und im Markt nicht existiert — nicht einen
Wert, der stört. Ohne ihn lag der p99 der Vollkasko bei 8.419 € und das Maximum bei
20.264 € Jahresbeitrag; beides ist für eine private Vollkasko nicht plausibel. Messwerte
vorher und nachher in [`docs/iteration_log.md`](iteration_log.md).

**Nebenwirkung, die benannt gehört.** Rund 1,2 % aller Anfragen wechseln dadurch von
052/053 nach 051. Der Hausratanteil und die Kfz-Summe bleiben exakt; innerhalb der
Kfz-Sparten verschiebt sich die Verteilung. In der Haftpflicht tragen dadurch 6,9 % der
Risiken eine Malus- oder Schadenklasse statt der gezogenen gut 3 % — eine
Selektionswirkung, die es im Markt genauso gibt.

### 4.5 Hausratrisiko

| Feld | Verteilung / Parameter | Quelle |
|---|---|---|
| `wohnflaeche_qm` | log-normal, Median 85 m², σ = 0,42, gekappt auf 20–350 | **Zensus 2022**, Gebäude- und Wohnungszählung (Durchschnitt rund 92 m² je Wohnung; der Median liegt wegen der Rechtsschiefe darunter) |
| `baujahr` | Baualtersklassen bis 1918 (12 %), 1919–1948 (12 %), 1949–1978 (32 %), 1979–1990 (13 %), 1991–2000 (12 %), 2001–2010 (8 %), 2011–2022 (9 %), ab 2023 (2 %); innerhalb der Klasse gleichverteilt | **Zensus 2022**, Gebäude- und Wohnungszählung |
| `versicherungssumme_eur` | 650 €/m² × Wohnfläche × log-normal (σ = 0,22), auf 1.000 € abgerundet, gekappt auf 10.000–800.000 | Branchenübliche Faustregel (spec/01, Abschnitt 3.4); Streuung Modellannahme |
| `unterversicherungsverzicht` | 72 %, aber nur wo die Summe 650 €/m² erreicht | Modellannahme; die Bedingung sichert R-040 |
| `bauartklasse` | `1` 42 %, `2` 18 %, `3` 10 %, `0` 5 %, `4` 5 %, `5` 4 %, `6`–`8` je 2–3 %, `A`–`I` je 1 % | Modellannahme (GDV Anlage 12 gibt nur den Katalog vor, keine Anteile) |
| `gebaeudeart` | EFH 28 %, MIETWOHNUNG 22 %, ETW 18 %, MFH 16 %, RH 9 %, DHH 7 % | Modellannahme, an der Zensus-Struktur orientiert |
| `stockwerk` | nur bei ETW, MIETWOHNUNG und MFH; −1 (3 %), 0 (22 %), 1 (23 %), 2 (20 %), 3 (15 %), 4 (9 %), 5 (5 %), 6 (2 %), 7 (1 %) | Modellannahme |
| `elementar_eingeschlossen` | je ZÜRS-Zone 55 / 45 / 30 / 10 % | Modellannahme; der niedrige Wert in Zone 4 folgt spec/01, Abschnitt 3.4 |
| `sublimit_fahrrad_eur` | Stufen 0 / 500 / 1.000 / 1.500 / 2.000 / 3.000 / 5.000 / 10.000 mit 30 / 16 / 18 / 12 / 11 / 7 / 4 / 2 % | Modellannahme |
| `sublimit_wertsachen_eur` | Anteil der Versicherungssumme 0 / 5 / 10 / 15 / 20 / 25 / 30 % mit 10 / 14 / 22 / 18 / 18 / 10 / 8 %, auf 100 € abgerundet | Modellannahme |

### 4.6 Tarif und Beitrag

**Tarifgenerationen.** Je Anbieter und Sparte entstehen drei bis fünf Generationen (Gewichte
35 / 40 / 25 %) mit lückenlos aneinandergrenzenden Gültigkeitszeiträumen. Sie decken die
Spanne von 30 Monaten vor dem Stichtag bis 6 Monate danach ab; die kürzeste Laufzeit
beträgt vier Monate. Ohne mehrere Generationen wäre die Fehlerklasse „veralteter
Tarifstand" (R-055) nicht injizierbar.

**Deckungsart (nur Sparte 051).** `11` unbegrenzt 72 %, `13` gesetzliche Mindestdeckung
10 %, `16` sonstige 18 % (Modellannahme). Bei `13` exakt die Werte aus der Anlage zu § 4
Abs. 2 PflVG; „unbegrenzt" wird über eine pauschale Höchstsumme von 100 Mio. € abgebildet,
weil „unbegrenzt" im Datenmodell kein darstellbarer Wert ist.

**Beitragsmodell.** Gerechnet wird durchgängig in `Decimal`, von unten nach oben:

```
Kfz:      netto = Grundbeitrag(Sparte) × VU-Niveau
                × exp(0,045 × (Typklasse − Mitte))
                × exp(0,050 × (Regionalklasse − Mitte))
                × SF-Beitragssatz/100
                × (Fahrleistung / 12.000)^0,25
                × Selbstbehaltfaktor

Hausrat:  netto = Grundbeitrag × VU-Niveau
                × (Versicherungssumme / 62.000)^0,70
                × ZÜRS-Faktor × Bauartfaktor × Elementarfaktor
                × Selbstbehaltfaktor
```

| Größe | Wert | Quelle |
|---|---|---|
| Grundbeitrag 051 / 052 | 1.100 € / 2.300 € — **Beitrag bei Satz 100 %**, nicht der Durchschnittsbeitrag; der Median des SF-Satzes liegt bei rund 29 % | Größenordnung angelehnt an die **GDV-Durchschnittsbeiträge je Sparte**; die Werte selbst sind Modellannahme |
| Grundbeitrag 053 / 130 | 225 € / 200 € — hier direkt der Durchschnittsbeitrag, weil die Teilkasko keine SF-Einstufung kennt | dito |
| VU-Niveau | je Anbieter fest, log-normal σ = 0,16, gekappt auf 0,78–1,42 | Modellannahme |
| ZÜRS-Faktor | 1,00 / 1,06 / 1,15 / 1,30 | Modellannahme |
| Elementarzuschlag | 1,25 | Modellannahme |
| Bauartfaktor | 0,95 bis 1,35 über die 18 Klassen | Modellannahme |
| Selbstbehaltnachlass | TK bis 0,80, VK bis 0,72, Hausrat bis 0,84 (Betrag) beziehungsweise 0,86 (Prozent) | Modellannahme |
| Zuschlag bei ANNAHME_MIT_ZUSCHLAG | 1,15 | Modellannahme |
| `annahmeentscheidung` | ANNAHME 85 %, ANNAHME_MIT_ZUSCHLAG 8 %, PRUEFUNG 4 %, ABLEHNUNG 3 %; mindestens zwei bepreiste Angebote je Anfrage | Modellannahme |
| `ratenzahlungszuschlag_prozent` | 0 bei Ratenanzahl 1, sonst gleichverteilt zwischen 0,50 und 8,00 | spec/01, Abschnitt 3.6; die **Untergrenze von 0,5 %** verhindert, dass R-036 rundungsbedingt auf sauberen Daten auslöst |
| Selbstbehaltkonvention Hausrat | 35 % der Anfragen in Prozent, 65 % als Betrag — **je Anfrage einheitlich** | Modellannahme; die Einheitlichkeit sichert R-052 |

**Kein Beitragskorridor im Generator.** Der Beitrag wird **nicht** gekappt, und die
Zahlweise wird **unabhängig** von der Beitragshöhe gezogen. Beides war in einer früheren
Fassung anders, solange R-053 die Rate statt des Jahresbeitrags prüfte; die Begründung des
Rückbaus steht in [`docs/iteration_log.md`](iteration_log.md), Abschnitt „Vorbemerkung zu
R-053".

Der Generator liest die Schwellen aus `config.schwellen` weiterhin **nicht**: Sie werden in
der Arbeit variiert; ein Generator, der an ihnen hängt, würde bei jeder Variation einen
anderen Datensatz erzeugen und die Läufe unvergleichbar machen. Die Einhaltung wird
stattdessen im Test geprüft (`tests/test_generator/test_beitrag.py`).

Die erzeugten Bruttojahresbeiträge nach der Kalibrierung des rechten Randes (10.000
Anfragen, Master-Seed der Konfiguration):

| Sparte | Minimum | Median | p99 | p99,9 | Maximum |
|---|---|---|---|---|---|
| 051 Kfz-HP | 79 € | 478 € | 3.820 € | 5.396 € | 8.937 € |
| 052 Vollkasko | 127 € | 948 € | 4.384 € | 6.948 € | 9.691 € |
| 053 Teilkasko | 80 € | 334 € | 884 € | 1.087 € | 1.202 € |
| 130 Hausrat | 57 € | 240 € | 600 € | 797 € | 1.102 € |

Der Korridor von R-053 ist daraufhin für Kfz auf `[40, 13000]` gesetzt: höchster
beobachteter Wert über fünf unabhängige Seeds 9.691 €, plus 30 Prozent Sicherheitsmarge,
glatt gerundet. Über alle fünf Seeds liegt kein Angebot außerhalb des Korridors, in keine
Richtung. Hausrat bleibt bei `[20, 2000]` — dort wird der Korridor nicht ausgereizt.

Die Spreizung max/min je Anfrage bleibt durch die Grenzen des VU-Niveaus, des
Selbstbehaltnachlasses und des Zuschlags rechnerisch unter dem Faktor 3,2 und damit
deutlich unter dem Schwellenwert 6 von R-047 (gemessen: 2,81).

### 4.7 Modellvereinfachungen der Phase 2

| Vereinfachung | Umsetzung | Warum |
|---|---|---|
| Juristische Personen | `anrede` = FIRMA nur in der Sparte 130 | In den Kfz-Sparten fehlte sonst das Bezugsalter für Führerscheindatum und Schadenfreiheitsklasse; R-028 und R-029 wären dort grundsätzlich nicht auswertbar |
| Selbstbehalt der Haftpflicht | keiner | Die Kfz-Haftpflicht kennt marktüblich keinen Selbstbehalt |
| SF-Einstufung der Teilkasko | keine | Entspricht der deutschen Marktpraxis; der Beitrag hängt dort nur an Typ- und Regionalklasse |
| Annahme in der Kasko | Malus- und Schadenklasse werden **kategorisch** nicht angenommen | Real nehmen einzelne Versicherer solche Risiken mit hohen Zuschlägen doch an. Die kategorische Fassung ist die einfachere und für die Regelmechanik folgenlose Variante (siehe 4.4) |
| Beitragsniveau je Generation | konstant je Anbieter | Ein Niveau je Tarifgeneration wäre realistischer, ändert an der Regelmechanik aber nichts |
| Zeitzone | naive Ortszeit ohne Offset | GDV-Zeitstempel führen keinen Offset; eine zeitzonenbewusste Darstellung wäre Scheingenauigkeit |
| PLZ-Ziehung Hausrat | nach ZÜRS-Zone geschichtet statt gleichverteilt | **Koppelt die PLZ-Verteilung der Hausrat-Anfragen an ZÜRS.** Die Randverteilung der Zonen bleibt die belegte des GDV, aber die Postleitzahlen sind innerhalb der Sparte 130 nicht mehr gleichverteilt — Zone-4-PLZ sind dort gegenüber einer freien Ziehung leicht überrepräsentiert, Zone-1-PLZ leicht unter. Ohne die Schichtung wäre R-048 schon auf sauberen Daten instabil (siehe 4.1) |

### 4.8 Leeres Datum in der Rohschicht — ein Widerspruch in spec/01

`spec/01_datenmodell.md`, Abschnitt 6, enthält zu leeren Datumsfeldern zwei Aussagen, die
sich widersprechen: Die Zeile `date` nennt `00000000` als Darstellung des leeren Datums,
die Zeile `leer` den leeren String für **alle** Typen.

Umgesetzt ist der **leere String**. Der Grund ist inhaltlich: Der saubere Datensatz enthält
planmäßig leere Datumsfelder — `geburtsdatum` bei `anrede` = FIRMA, `fuehrerschein_datum`
außerhalb der Kfz-Sparten. Mit `00000000` würde R-009 („jedes Datumsfeld der Rohschicht ist
ein existierender Kalendertag") auf dem sauberen Datensatz auslösen, denn `00000000` ist
kein Kalendertag. Der Clean-Baseline-Lauf hätte dann Fehlalarme, die keine sind.

Umgekehrt bleibt `00000000` in der Rohschicht ein **Befund**: Der Parser gibt dafür `pd.NA`
zurück *und* protokolliert die Stelle. Ein solcher Wert kann nur aus einer Injektion
stammen, und R-009 soll ihn melden.

**Anmerkung für Phase 4:** Die Sentinel-Liste `SENTINEL_DATUM` in
`src/common/wertebereiche.py` führt `0000-00-00` und `1900-01-01` im ISO-Format. Die
Rohschicht schreibt Datumswerte aber als `TTMMJJJJ`. Die Injektionsvariante F1-c muss das
berücksichtigen, sonst schreibt sie einen Wert, den kein Datumsfeld je enthalten könnte.

---

## 5. Was weiterhin offen bleibt

Alle vier in Phase 2 gemeldeten Punkte sind entschieden:

| Punkt | Entscheidung | Fundstelle |
|---|---|---|
| Leeres Datum in der Rohschicht | Leerstring für alle Typen; `00000000` ist ein Sentinel (R-025), kein Leerwert | `spec/01`, Abschnitt 6 |
| Pflichtfeldprofil je Kanal | übernommen, R-057 ist zweigeteilt | `spec/01`, Abschnitt 5.1; `spec/02`, R-057 |
| Anwendbarkeit vor Profil | übernommen, R-041 und R-057 verweisen darauf | `spec/01`, Abschnitt 5.2 |
| R-053 auf die Rate bezogen | **Spezifikationsfehler**, korrigiert: R-053 prüft `bruttobeitrag_jahr_eur`. Kappung und Zahlweisenkopplung im Generator zurückgebaut, Schwellenwert angepasst | `spec/02`, R-053; `docs/iteration_log.md` |

Der in Phase 2b gemeldete Vorbehalt zum rechten Rand der Vollkasko-Verteilung ist
inzwischen ebenfalls erledigt: Die Annahmebedingung der Kaskosparten (4.4) halbiert p99 und
Maximum, der Korridor von R-053 ist daraufhin neu bestimmt.

Damit ist aus Phase 2 nichts mehr offen.
