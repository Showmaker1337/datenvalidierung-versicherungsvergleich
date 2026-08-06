# Spezifikation 1 — Datenmodell und Referenzdaten

Quelle der Wahrheit für den Datengenerator. Jede Änderung hier zieht eine Änderung im
Generator nach sich, nicht umgekehrt.

**Vorbemerkung zur Domäne:** Die Feldnamen, Formate und Wertebereiche orientieren sich am
GDV-Datensatz VU-Vermittler (Release 2023, öffentlich dokumentiert unter
`gdv-online.de/vuvm/bestand/rel2023/`) sowie an den Eingabefeldern gängiger
Vergleichsrechner. Der Datensatz ist synthetisch; er bildet die Struktur nach, nicht reale
Bestände.

---

## 1. Entitätenübersicht

Sternschema um die Vergleichsanfrage, nachempfunden dem GDV-Aufbau
Satzart 0200 (allgemeiner Vertragsteil) → 0210.xxx (spartenspezifisch) → 0220.xxx
(wagnisspezifisch).

| Entität | Zeilen je Anfrage | Rolle |
|---|---|---|
| `anfrage` | 1 | Anker |
| `person` | 1–2 | Versicherungsnehmer, optional zweite versicherte Person |
| `risiko_kfz` | 0–1 | nur bei Sparte 051/052/053 |
| `risiko_hausrat` | 0–1 | nur bei Sparte 130 |
| `tarif` | Stammdaten | eigenständige Tabelle, nicht je Anfrage |
| `angebot` | 3–12 | die eigentlichen Vergleichszeilen |
| `zahlung` | 1 | Bankverbindung |

Erzeugt werden zwei Sparten: **Kfz (051 Haftpflicht, 052 Vollkasko, 053 Teilkasko)** und
**Verbundene Hausrat (130)**. Zwei Sparten sind zwingend — nur dadurch entstehen
spartenabhängige Regeln (insbesondere die Versicherungsteuer).

Standardumfang eines Laufs: **10.000 Anfragen**. Die Zahl der Angebote je Anfrage ist
rechtsschief verteilt (Modus 5, Spanne 3 bis 12), sodass rund **60.000 Angebotszeilen**
entstehen. Eine Gleichverteilung über 3 bis 12 ergäbe 75.000 — beide Zahlen sind
vertretbar, aber sie müssen zueinander passen.

**Vereinfachung:** Im Modell schließen sich die Sparten gegenseitig aus, eine Anfrage
betrifft genau eine Sparte. In der Realität umfasst eine Kfz-Vergleichsanfrage immer die
Haftpflicht und optional Teil- oder Vollkasko; Kaskoschutz ohne Haftpflicht wird in
Deutschland nicht verkauft. Für die Regelmechanik ist das folgenlos, für die
Realitätsnähe nicht — als bewusste Vereinfachung in der Arbeit kennzeichnen.

---

## 2. Referenzdaten

Liegen als CSV/Parquet unter `data/reference/` und werden **einmalig deterministisch
erzeugt** (Seed aus der Konfiguration), danach versioniert und nicht mehr verändert.
Generator und Regel-Engine lesen dieselben Dateien.

### 2.1 `plz_ort.csv`

| Spalte | Typ | Inhalt |
|---|---|---|
| `plz` | str(5) | fünfstellig, führende Null möglich |
| `ort` | str | Ortsname |
| `bundesland` | str | Kürzel |
| `zulassungsbezirk` | str(1–3) | Unterscheidungszeichen des Kfz-Kennzeichens |

Bezugsquelle: OpenPLZ API (`openplzapi.org`) oder BKG-Postleitzahlgebiete. Falls kein
Download möglich ist, eine synthetische Tabelle mit ca. 8.000 Einträgen erzeugen, die die
Leitzonen-Systematik einhält (erste Ziffer 0–9). **Wichtig:** Ein Zulassungsbezirk kann
mehrere PLZ umfassen; eine PLZ gehört zu genau einem Zulassungsbezirk in diesem Modell
(vereinfachende Annahme, in der Arbeit als solche kennzeichnen — real können PLZ-Gebiete
Bezirksgrenzen schneiden).

### 2.2 `regionalklassen.csv`

| Spalte | Typ | Wertebereich |
|---|---|---|
| `zulassungsbezirk` | str | Schlüssel |
| `regionalklasse_hp` | int | 1–12 |
| `regionalklasse_tk` | int | 1–16 |
| `regionalklasse_vk` | int | 1–9 |

Verteilung um die Mitte zentriert (Index 100 entspricht dem Bundesdurchschnitt). Das
echte Verzeichnis des GDV ist nicht als Bulk-Download verfügbar — nur die
Klassenanzahlen sind öffentlich. Die Zuordnung wird deshalb synthetisch erzeugt und ist
in der Arbeit als Modellannahme zu kennzeichnen.

### 2.3 `typklassen.csv`

| Spalte | Typ | Wertebereich |
|---|---|---|
| `hsn` | str(4) | vierstellig numerisch, führende Nullen |
| `tsn` | str(3) | dreistellig alphanumerisch `[A-Z0-9]{3}` |
| `hersteller` | str | Klartext |
| `modell` | str | Klartext |
| `leistung_kw` | int | 1–1500 |
| `antriebsart` | enum | BENZIN, DIESEL, ELEKTRO, HYBRID, GAS |
| `typklasse_hp` | int | **10–25** |
| `typklasse_tk` | int | **10–33** |
| `typklasse_vk` | int | **10–34** |
| `neupreis_eur` | Decimal | 8.000–250.000 |

Rund 3.000 Kombinationen. Die Wertebereiche sind öffentlich belegt (16 / 24 / 25 Klassen).

### 2.4 `vu_stammdaten.csv`

| Spalte | Typ | Inhalt |
|---|---|---|
| `vu_nummer` | str(5) | fünfstellig, linksbündig |
| `vu_name` | str | Fantasiename, klar als synthetisch erkennbar (z. B. „Nordstern Versicherung AG") |
| `marktanteil` | float | Gewicht für die Anbieterziehung, summiert auf 1 |
| `quell_schnittstelle` | enum | BIPRO_420, BIPRO_RNEXT, GDV, CSV_IMPORT |

12 bis 15 Anbieter. **Wichtig für die Multi-Source-Fehlerklasse:** Die Zuordnung
Anbieter → Schnittstelle ist fest und bestimmt später sowohl das erwartete
Pflichtfeldniveau als auch die Einheitenkonvention.

### 2.5 `zuers_zonen.csv`

`plz` → `zuers_zone` (1–4). Ziehung mit den vom GDV publizierten Anteilen:
**92,4 % / 6,1 % / 1,1 % / 0,4 %**.

### 2.6 `sf_beitragssatz.csv`

`sf_klasse` (str) → `beitragssatz_prozent` (int).

**Monotonie: nicht-steigend, nicht streng fallend.** Über die numerischen Klassen SF 1 bis
SF 50 gilt `satz(SF n+1) ≤ satz(SF n)`. Plateaus sind ausdrücklich zulässig und erwünscht.

Der Grund ist zweifach. Rechnerisch: Zwischen den Ankerwerten 58 und 16 liegen 43 ganze
Zahlen, zu besetzen sind 50 Klassen — strenge Monotonie ist bei ganzzahligen Prozentwerten
unmöglich. Fachlich: Reale Beitragssatztabellen flachen bei hohen Schadenfreiheitsklassen
ohnehin ab; zwischen SF 40 und SF 45 unterscheidet sich der Satz bei vielen Versicherern
nicht mehr. Die Plateaus bilden also die Realität ab, sie sind kein Kompromiss.

Ankerwerte: SF 1 ≈ 58 %, SF 50 ≈ 16 %. Sonderklassen: `M` = 245 %, `S` = 155 %,
`0` = 100 %, `1/2` = 70 %.

Es gibt keine branchenweit verbindliche Tabelle — die Sätze sind versichererindividuell.
In der Arbeit als Modellannahme kennzeichnen. Zwei weitere Vereinfachungen gehören
ebenfalls benannt: Die meisten Versicherer enden bei SF 35, nicht bei SF 50, und viele
moderne Tabellen setzen SF 1 auf 100 % statt auf 58 %.

### 2.7 `waehrungen.csv`

`code` (str, 3 Zeichen) → `name` (str) → `numerisch` (int). Der vollständige ISO-4217-Katalog,
rund 180 Einträge. Grundlage für R-012.

**Erzeugung:** einmalig über das Python-Paket `pycountry` (enthält die ISO-4217-Liste),
danach als CSV versioniert. Nicht aus dem Gedächtnis in den Quelltext schreiben — eine
falsche Währungsliste fällt niemandem auf und macht die Regel wertlos. Zur Laufzeit wird
nichts nachgeladen.

### 2.8 Ordinalskala der SF-Klassen

R-029 und R-030 brauchen einen Zahlwert für die SF-Klasse. Die Sonderklassen sind keine
Zahlen, aber sie haben eine fachliche Ordnung. Definiert werden deshalb **zwei getrennte
Abbildungen**, weil die beiden Regeln Verschiedenes messen:

| SF-Klasse | `schadenfreie_jahre()` | `sf_ordnung()` |
|---|---|---|
| `M` (Malus) | 0 | −3 |
| `S` (Schadenklasse) | 0 | −2 |
| `0` | 0 | −1 |
| `1/2` | 0 | 0 |
| `SF1` … `SF50` | 1 … 50 | 1 … 50 |

**`schadenfreie_jahre()` für R-029.** Die Regel prüft, ob jemand mehr schadenfreie Jahre
angibt, als er den Führerschein besitzen kann. Alle Sonderklassen bedeuten null
schadenfreie Jahre, die Regel ist dort also trivial erfüllt — und das ist fachlich korrekt,
nicht ein Ausweichen.

**`sf_ordnung()` für R-030.** Die Regel vergleicht zwei SF-Klassen miteinander. Dafür wird
eine vollständige Ordnung über alle Werte gebraucht, einschließlich der Sonderklassen. Mit
dieser Abbildung greift R-030 auch für Sonderklassen, statt sie stillschweigend zu
überspringen.

Beide Funktionen gehören nach `src/common/`, weil Generator und Regel-Engine sie brauchen.

---

## 3. Feldspezifikation

Legende Abhängigkeiten: `→` bedeutet „bestimmt", `↔` bedeutet „muss korrespondieren mit".

### 3.1 `anfrage`

| # | Feld | Typ | Wertebereich / Format | Abhängigkeit |
|---|---|---|---|---|
| 1 | `anfrage_id` | str | UUID4 | PK |
| 2 | `row_id` | int | fortlaufend, eindeutig | **nie Ziel der Injektion** |
| 3 | `eingangszeitpunkt` | datetime | ISO 8601, innerhalb der letzten 24 Monate vor `stichtag` | ≤ `stichtag` |
| 4 | `kanal` | enum | WEB, APP, MAKLER, API_BIPRO, TELEFON | → erwartetes Pflichtfeldniveau |
| 5 | `sparte` | str(3) | 051, 052, 053, 130 | → welche Risiko-Entität existiert |
| 6 | `vn_person_id` | str | FK → `person` | Pflicht |
| 7 | `versicherungsbeginn` | date | ≥ Datum(`eingangszeitpunkt`), ≤ +12 Monate | |
| 8 | `vorvertrag_vorhanden` | bool | | Kfz: bei SF > 0 muss `True` sein |
| 9 | `vorversicherer_vu_nr` | str(5) | nur wenn `vorvertrag_vorhanden` | FK → `vu_stammdaten` |
| 10 | `zahlweise` | int | **{1, 2, 4, 5, 6, 8, 9}** — 3 und 7 existieren nicht (GDV Anlage 14) | → Ratenanzahl, → Ratenzuschlag |
| 11 | `waehrung` | str(3) | ISO 4217, hier immer `EUR` | |
| 12 | `anfrage_status` | enum | NEU, TARIFIERT, ANGEBOT, ANTRAG, STORNIERT | monoton in Prozessreihenfolge |

Ratenanzahl-Mapping: `1`→1 (jährlich), `2`→2 (halbjährlich), `4`→4 (vierteljährlich),
`5`→1 (sonstiges), `6`→1 (Einmalbetrag), `8`→12 (monatlich), `9`→1 (beitragsfrei).

**Vereinfachung:** Die Zahlweisen `5` (sonstiges) und `9` (beitragsfrei) werden im
Generator **nicht gezogen**. Zahlweise `9` bedeutet beitragsfrei und wäre mit einem
positiven Beitrag fachlich widersprüchlich; Zahlweise `5` hat keine definierte Semantik.
Beide bleiben im Katalog gültiger Werte (R-010 prüft gegen den vollständigen GDV-Katalog),
kommen aber nicht vor. In der Arbeit als Modellvereinfachung kennzeichnen.

### 3.2 `person`

| # | Feld | Typ | Wertebereich / Format | Abhängigkeit |
|---|---|---|---|---|
| 0 | `row_id` | int | fortlaufend je Entität, eindeutig | **nie Ziel der Injektion** |
| 13 | `person_id` | str | UUID4 | PK |
| 14 | `anfrage_id` | str | FK | |
| 15 | `rolle` | enum | VN, VP | genau eine `VN` je Anfrage |
| 16 | `anrede` | enum | HERR, FRAU, DIVERS, FIRMA | FIRMA → `geburtsdatum` leer |
| 17 | `nachname` | str(≤50) | Faker `de_DE` | nicht leer, außer `anrede` = FIRMA |
| 18 | `vorname` | str(≤30) | Faker `de_DE` | |
| 19 | `geburtsdatum` | date | Alter 18–95 zum `stichtag`; Verteilung aus Zensus-Altersstruktur | → `alter`, → SF-Plausibilität |
| 20 | `plz` | str(5) | FK → `plz_ort` | → `ort`, → `zulassungsbezirk`, → `zuers_zone` |
| 21 | `ort` | str(≤50) | muss zu `plz` passen | Länge großzügig, damit lange Ortsnamen aus der Referenz die Schemavalidierung nicht auslösen |
| 22 | `strasse` | str(≤30) | Faker | |
| 23 | `hausnummer` | str(≤10) | | |
| 24 | `email` | str(≤60) | RFC-5322-vereinfacht | Kanal WEB/APP → Pflicht |
| 25 | `familienstand` | enum | LEDIG, VERHEIRATET, GESCHIEDEN, VERWITWET | |
| 26 | `wohneigentum` | bool | | Kfz-Rabattmerkmal |
| 27 | `fuehrerschein_datum` | date | ≥ `geburtsdatum` + 17 Jahre, ≤ `stichtag` | nur Sparte 051–053, sonst leer |

Zweckbindung: Felder, die für eine Sparte fachlich irrelevant sind, sind **leer**, nicht
mit Platzhaltern gefüllt. Das ist zugleich eine prüfbare Regel (Datenminimierung).

### 3.3 `risiko_kfz` (nur Sparte 051/052/053)

| # | Feld | Typ | Wertebereich / Format | Abhängigkeit |
|---|---|---|---|---|
| 0 | `row_id` | int | fortlaufend je Entität, eindeutig | **nie Ziel der Injektion** |
| 28 | `risiko_id` | str | UUID4 | PK |
| 29 | `anfrage_id` | str | FK | |
| 30 | `hsn` | str(4) | FK → `typklassen` | ↔ `tsn` |
| 31 | `tsn` | str(3) | FK → `typklassen` | |
| 32 | `wagniskennziffer` | str(3) | `112` = PKW | |
| 33 | `erstzulassung` | date | ≥ 1990-01-01, ≤ `stichtag` | ≤ `zulassung_auf_vn` |
| 34 | `zulassung_auf_vn` | date | ≥ `erstzulassung`, ≤ `stichtag` | ≥ `geburtsdatum` + 18 J. |
| 35 | `leistung_kw` | int | aus `typklassen` | |
| 36 | `antriebsart` | enum | aus `typklassen` | ↔ `art_kennzeichen` |
| 37 | `neupreis_eur` | Decimal(10,2) | aus `typklassen` | ≥ `fahrzeugwert_aktuell` |
| 38 | `fahrzeugwert_aktuell` | Decimal(10,2) | Restwertkurve über Fahrzeugalter | > 0 wenn Vollkasko |
| 39 | `art_kennzeichen` | str(2) | `01` normal, `04` Saison, `54` E-Kennzeichen | `54` → Antrieb ELEKTRO/HYBRID |
| 40 | `zulassungsbezirk` | str | aus `plz_ort` über `person.plz` | → Regionalklassen |
| 41 | `jahresfahrleistung_km` | int | 1.000–60.000, log-normal um 12.000 | |
| 42 | `nutzungsart` | str(2) | `01` geschäftlich, `02` privat, `03` Taxi, `08` gemischt | |
| 43 | `eigentumsverhaeltnis` | str(1) | `1` Eigentum VN, `3` Leasing | |
| 44 | `nutzerkreis` | enum | VN, VN_PARTNER, VN_FAMILIE, BELIEBIG | → `alter_juengster_fahrer` |
| 45 | `alter_juengster_fahrer` | int | 17–95 | ≤ Alter VN wenn `nutzerkreis` = VN |
| 46 | `abstellplatz` | enum | GARAGE, CARPORT, STELLPLATZ, STRASSE | |
| 47 | `sf_klasse_hp` | str | `0`, `1/2`, `S`, `M`, `SF1`…`SF50` | **numerischer Teil ≤ Alter − 17** |
| 48 | `sf_klasse_vk` | str | dito, nur wenn Vollkasko | ≤ `sf_klasse_hp` |
| 49 | `schaeden_letzte_5j` | int | 0–5, stark rechtsschief (meist 0) | |
| 50 | `typklasse_hp` | int | aus `typklassen`, 10–25 | |
| 51 | `typklasse_tk` | int | aus `typklassen`, 10–33 | nur wenn TK/VK |
| 52 | `typklasse_vk` | int | aus `typklassen`, 10–34 | nur wenn VK |
| 53 | `regionalklasse_hp` | int | aus `regionalklassen`, 1–12 | über `zulassungsbezirk` |
| 54 | `regionalklasse_tk` | int | 1–16 | |
| 55 | `regionalklasse_vk` | int | 1–9 | |

### 3.4 `risiko_hausrat` (nur Sparte 130)

| # | Feld | Typ | Wertebereich / Format | Abhängigkeit |
|---|---|---|---|---|
| 0 | `row_id` | int | fortlaufend je Entität, eindeutig | **nie Ziel der Injektion** |
| 56 | `risiko_id` | str | UUID4 | PK |
| 57 | `anfrage_id` | str | FK | |
| 58 | `wohnflaeche_qm` | int | 20–350, Verteilung aus Zensus 2022 | → `versicherungssumme_eur` |
| 59 | `versicherungssumme_eur` | Decimal(12,2) | 10.000–800.000 | bei Unterversicherungsverzicht ≥ 650 × Wohnfläche |
| 60 | `unterversicherungsverzicht` | bool | | |
| 61 | `bauartklasse` | str(1) | GDV Anlage 12: `0`, `1`–`5`, `6`–`8`, `A`–`I` | gemischt alphanumerisch → String |
| 62 | `baujahr` | int | 1850–Jahr(`stichtag`), Verteilung aus Zensus | ≤ Jahr(`stichtag`) |
| 63 | `gebaeudeart` | enum | EFH, DHH, RH, MFH, ETW, MIETWOHNUNG | ETW/MIETWOHNUNG → `stockwerk` gesetzt |
| 64 | `stockwerk` | int | −1 bis 25 | |
| 65 | `zuers_zone` | int | 1–4 aus `zuers_zonen` über `person.plz` | |
| 66 | `elementar_eingeschlossen` | bool | bei Zone 4 selten `True` | |
| 67 | `sublimit_fahrrad_eur` | Decimal(10,2) | 0–10.000 | ≤ `versicherungssumme_eur` |
| 68 | `sublimit_wertsachen_eur` | Decimal(10,2) | 0 bis 30 % der VS | ≤ `versicherungssumme_eur` |

### 3.5 `tarif` (Stammdaten)

| # | Feld | Typ | Wertebereich / Format | Abhängigkeit |
|---|---|---|---|---|
| 0 | `row_id` | int | fortlaufend je Entität, eindeutig | **nie Ziel der Injektion** |
| 69 | `tarif_id` | str | z. B. `NST-KFZ-2026-01` | PK |
| 70 | `vu_nummer` | str(5) | FK → `vu_stammdaten` | |
| 71 | `produktname` | str(≤20) | | |
| 72 | `sparte` | str(3) | 051, 052, 053, 130 | ↔ `anfrage.sparte` |
| 73 | `tarifgeneration` | str | `JJJJ-MM` | |
| 74 | `gueltig_ab` | date | | < `gueltig_bis` |
| 75 | `gueltig_bis` | date | | > `gueltig_ab` |
| 76 | `deckungsart` | int | `11` unbegrenzt, `13` gesetzl. Mindestdeckung, `16` sonstige | nur Kfz-HP |
| 77 | `deckungssumme_personen_eur` | Decimal(12,2) | ≥ 7.500.000 | bei `13` exakt 7.500.000 |
| 78 | `deckungssumme_sach_eur` | Decimal(12,2) | ≥ 1.300.000 | bei `13` exakt 1.300.000 |
| 79 | `deckungssumme_vermoegen_eur` | Decimal(12,2) | ≥ 50.000 | bei `13` exakt 50.000 |
| 80 | `werkstattbindung` | bool | | |

Gesetzliche Grundlage der Mindestsummen: PflVG, Anlage zu § 4 Abs. 2.

**Tarifgenerationen:** Je Anbieter und Sparte mindestens drei aufeinanderfolgende
Generationen mit lückenlos aneinandergrenzenden Gültigkeitszeiträumen anlegen. Nur
dadurch wird die Fehlerklasse „veralteter Tarifstand" überhaupt injizierbar.

### 3.6 `angebot`

| # | Feld | Typ | Wertebereich / Format | Abhängigkeit |
|---|---|---|---|---|
| 81 | `angebot_id` | str | UUID4 | PK |
| 82 | `row_id` | int | fortlaufend | **nie Ziel der Injektion** |
| 83 | `anfrage_id` | str | FK | |
| 84 | `tarif_id` | str | FK | |
| 85 | `rang` | int | 1..n je Anfrage, lückenlos | sortiert nach `zahlbeitrag_rate_eur` |
| 86 | `nettobeitrag_jahr_eur` | Decimal(10,2) | > 0 | Basis der Steuerberechnung |
| 87 | `versicherungsteuer_satz` | Decimal(5,2) | siehe unten | aus `sparte` |
| 88 | `versicherungsteuer_eur` | Decimal(10,2) | | = `netto` × `satz` / 100, ROUND_HALF_UP |
| 89 | `bruttobeitrag_jahr_eur` | Decimal(10,2) | | = `netto` + `steuer` |
| 90 | `ratenzahlungszuschlag_prozent` | Decimal(4,2) | 0–8 | > 0 nur wenn `zahlweise` ≠ 1 und ≠ 6 |
| 91 | `zahlbeitrag_rate_eur` | Decimal(10,2) | | = `brutto` × (1 + RZZ/100) / Ratenanzahl |
| 92 | `sb_tk_eur` | Decimal(8,2) | {0, 150, 300, 500, 1000} | nur TK/VK |
| 93 | `sb_vk_eur` | Decimal(8,2) | {0, 300, 500, 1000, 2500} | ≥ `sb_tk_eur` |
| 94 | `sb_hausrat_prozent` | Decimal(5,2) | 0–100 | **exklusiv** zu `sb_hausrat_eur` |
| 95 | `sb_hausrat_eur` | Decimal(10,2) | {0, 150, 250, 500, 1000} | |
| 96 | `annahmeentscheidung` | enum | ANNAHME, ANNAHME_MIT_ZUSCHLAG, ABLEHNUNG, PRUEFUNG | ABLEHNUNG → Beitragsfelder leer |
| 97 | `berechnungszeitpunkt` | datetime | ≥ `eingangszeitpunkt`, Δ ≤ 60 s | muss in `[gueltig_ab, gueltig_bis]` liegen |
| 98 | `quell_schnittstelle` | enum | aus `vu_stammdaten` | → erwartetes Pflichtfeldniveau |

**Versicherungsteuer — die spartenabhängige Falle.** Zwei Größen sauber trennen:

| Sparte | Nominalsatz (§ 6 VersStG) | Bemessungsgrundlage (§ 5) | **Effektivsatz** |
|---|---|---|---|
| 051/052/053 Kfz | 19 % | 100 % | **19,00 %** |
| 130 Hausrat inkl. Feuer | 19 % | 85 % | **16,15 %** |

Im Datenmodell wird der **Effektivsatz** in `versicherungsteuer_satz` geführt. In der
Arbeit muss der Unterschied zwischen Nominal- und Effektivsatz erklärt und
`§ 6 Abs. 2 i. V. m. § 5 Abs. 1 Nr. 3 VersStG` zitiert werden — die verbreitete Angabe
„Hausrat 16,15 %" ist ein Effektivsatz, kein Nominalsatz.

Die Sätze für Leben, Kranken und BU (steuerfrei nach § 4 VersStG) sind im Modell nicht
relevant, weil diese Sparten nicht erzeugt werden. Die entsprechende Regel wird trotzdem
implementiert und im Regelkatalog als **nicht auslösbar im aktuellen Datenmodell**
gekennzeichnet — das ist ehrlicher als sie wegzulassen.

### 3.7 `zahlung`

| # | Feld | Typ | Wertebereich / Format | Abhängigkeit |
|---|---|---|---|---|
| 0 | `row_id` | int | fortlaufend je Entität, eindeutig | **nie Ziel der Injektion** |
| 99 | `zahlung_id` | str | UUID4 | PK |
| 100 | `anfrage_id` | str | FK | |
| 101 | `iban` | str(22) | `^DE\d{20}$`, ISO 7064 Mod 97-10 gültig | |
| 102 | `bic` | str(8) oder str(11) | nie 9 oder 10 Zeichen | |
| 103 | `sepa_mandat_datum` | date | ≤ `versicherungsbeginn` | |
| 104 | `kontoinhaber` | str(≤60) | | ≠ VN → Kennzeichen abweichender Zahler |

---

## 4. Verteilungsquellen dokumentieren

Für jedes Feld mit nicht-uniformer Verteilung wird in `docs/verteilungsquellen.md`
festgehalten: Feldname, gewählte Verteilung, Parameter, Quelle der Annahme.

Verpflichtend belegt werden:

| Feld | Quelle |
|---|---|
| `geburtsdatum` / Altersverteilung | Zensus 2022 bzw. Destatis Altersstruktur |
| `wohnflaeche_qm`, `baujahr` | Zensus 2022, Gebäude- und Wohnungszählung |
| `zuers_zone` | GDV Naturgefahren-Datenservice (92,4 / 6,1 / 1,1 / 0,4 %) |
| `vu_nummer` (Anbietergewichte) | GDV „Fakten zur Versicherungswirtschaft", Marktanteile |
| `jahresfahrleistung_km`, Fahrzeugalter | freMTPL2freq (CASdatasets) als Strukturvorbild |
| Beitragsniveau | GDV-Durchschnittsbeiträge je Sparte |

Wo keine Quelle verfügbar ist (Regionalklassen-Zuordnung, SF-Beitragssatztabelle,
Typklassen-Zuordnung), wird das ausdrücklich als **Modellannahme** vermerkt. Das ist kein
Mangel, sondern Transparenz — und im Kolloquium deutlich besser als eine unbelegte Zahl.

---

## 5. Pflichtfeldprofil je Quellschnittstelle

Grundlage für R-057. Ohne diese Tabelle ist die Regel nicht implementierbar.

Hintergrund aus der Praxis: Versicherer befüllen dieselben Felder unterschiedlich tief.
BiPRO-Schnittstellen liefern strukturiert und vollständig, klassische GDV-Lieferungen und
manuelle CSV-Importe deutlich lückenhafter. Genau das ist ein Multi-Source-Problem im
Sinne von Rahm & Do.

| Feld | BIPRO_420 | BIPRO_RNEXT | GDV | CSV_IMPORT |
|---|---|---|---|---|
| `person.email` | Pflicht | Pflicht | optional | optional |
| `person.strasse`, `person.hausnummer` | Pflicht | Pflicht | Pflicht | optional |
| `person.familienstand` | Pflicht | Pflicht | optional | optional |
| `person.wohneigentum` | Pflicht | Pflicht | optional | optional |
| `risiko_kfz.abstellplatz` | Pflicht | Pflicht | optional | optional |
| `risiko_kfz.alter_juengster_fahrer` | Pflicht | Pflicht | Pflicht | optional |
| `risiko_kfz.jahresfahrleistung_km` | Pflicht | Pflicht | Pflicht | Pflicht |
| `risiko_hausrat.sublimit_fahrrad_eur` | Pflicht | Pflicht | optional | optional |
| `risiko_hausrat.sublimit_wertsachen_eur` | Pflicht | Pflicht | optional | optional |
| `angebot.sb_tk_eur`, `angebot.sb_vk_eur` | Pflicht | Pflicht | Pflicht | optional |
| `zahlung.bic` | Pflicht | optional | Pflicht | optional |
| `zahlung.kontoinhaber` | Pflicht | Pflicht | optional | optional |

Kernfelder aus R-001 sind unabhängig von der Schnittstelle immer Pflicht.

Der Generator setzt die als „optional" markierten Felder bei der jeweiligen Schnittstelle
mit einer Wahrscheinlichkeit von 30 Prozent auf leer. **Das ist Teil des sauberen
Datensatzes, kein Fehler** — R-057 prüft nur, dass ein bei dieser Schnittstelle als
Pflicht markiertes Feld nicht leer ist.

Die Tabelle oben ist die **Quelle** des Profils. Sie ist aber nur auf die Entität `angebot`
unmittelbar anwendbar; für die Anfrageseite braucht es die Übersetzung in Abschnitt 5.1.

### 5.1 Wirksames Profil je `kanal` — die Anfrageseite

**Warum diese Übersetzung nötig ist.** Die Profiltabelle in Abschnitt 5 ist nach
`quell_schnittstelle` geschlüsselt. Dieses Feld gehört zur Entität `angebot`: Es beschreibt,
über welche Schnittstelle **ein Versicherer sein Angebot liefert**. Die meisten Profilfelder
liegen dagegen auf der Anfrageseite (`person`, `risiko_*`, `zahlung`) — sie werden **einmal
je Anfrage** erfasst und an alle angefragten Versicherer verschickt. Ihr Befüllungsgrad hängt
deshalb nicht am liefernden Versicherer, sondern am Eingangskanal. Abschnitt 3.1 sagt zu
`kanal` genau das: „→ erwartetes Pflichtfeldniveau".

Ohne diese Übersetzung wäre das Profil auf der Anfrageseite gar nicht anwendbar: Eine
Anfrage hat drei bis zwölf Angebote mit unterschiedlichen Schnittstellen, und das strengste
Profil unter ihnen würde faktisch immer greifen. Dann wäre jedes Feld überall gefüllt und
R-057 hätte auf der Anfrageseite nichts zu prüfen.

Die Zuordnung ist eine **Modellannahme** (siehe `docs/verteilungsquellen.md`). Sie hält die
Vorgabe aus Abschnitt 3.2 ein, dass `email` bei den Kanälen WEB und APP Pflicht ist:

| Kanal | wirksames Profil |
|---|---|
| `WEB` | `BIPRO_RNEXT` |
| `APP` | `BIPRO_420` |
| `API_BIPRO` | `BIPRO_420` |
| `MAKLER` | `GDV` |
| `TELEFON` | `CSV_IMPORT` |

Daraus ergibt sich für die anfrageseitigen Felder:

| Feld | `WEB` | `APP` | `API_BIPRO` | `MAKLER` | `TELEFON` |
|---|---|---|---|---|---|
| `person.email` | Pflicht | Pflicht | Pflicht | optional | optional |
| `person.strasse` | Pflicht | Pflicht | Pflicht | Pflicht | optional |
| `person.hausnummer` | Pflicht | Pflicht | Pflicht | Pflicht | optional |
| `person.familienstand` | Pflicht | Pflicht | Pflicht | optional | optional |
| `person.wohneigentum` | Pflicht | Pflicht | Pflicht | optional | optional |
| `risiko_kfz.abstellplatz` | Pflicht | Pflicht | Pflicht | optional | optional |
| `risiko_kfz.alter_juengster_fahrer` | Pflicht | Pflicht | Pflicht | Pflicht | optional |
| `risiko_kfz.jahresfahrleistung_km` | Pflicht | Pflicht | Pflicht | Pflicht | Pflicht |
| `risiko_hausrat.sublimit_fahrrad_eur` | Pflicht | Pflicht | Pflicht | optional | optional |
| `risiko_hausrat.sublimit_wertsachen_eur` | Pflicht | Pflicht | Pflicht | optional | optional |
| `zahlung.bic` | optional | Pflicht | Pflicht | Pflicht | optional |
| `zahlung.kontoinhaber` | Pflicht | Pflicht | Pflicht | optional | optional |

Die Zeile `zahlung.bic` folgt als einzige nicht dem Muster „BiPRO strenger als GDV": Die BIC
ist bei `BIPRO_RNEXT` optional, bei `GDV` dagegen Pflicht. Das ist so gewollt und steht
bereits in der Quelltabelle in Abschnitt 5.

**Die Angebotsseite bleibt bei der Quellschnittstelle.** Für `angebot.sb_tk_eur` und
`angebot.sb_vk_eur` gilt weiterhin die Tabelle aus Abschnitt 5, geschlüsselt nach dem Feld
`quell_schnittstelle` der jeweiligen Angebotszeile. R-057 ist deshalb **zweigeteilt**.

Umgesetzt in `src/common/pflichtfelder.py` (`PROFIL_JE_KANAL`, `ist_pflicht`).

### 5.2 Anwendbarkeitsbedingungen — wann eine Pflichtfeldprüfung nicht gilt

**Ein Feld, das die Zweckbindung ohnehin leer lässt, ist kein fehlender Wert, sondern ein
nicht existierender.** Es wird deshalb nicht auf Vollständigkeit geprüft. Ohne diese
Bedingung meldete R-057 Felder, die es in der jeweiligen Zeile gar nicht geben kann — ein
Fehlalarm, der ausschließlich aus der Prüfkonvention entstünde.

Zwei Arten von Bedingungen kommen vor:

| Feld | Bedingung | Art | Fachlicher Grund |
|---|---|---|---|
| `angebot.sb_tk_eur` | nur Sparte 052, 053 | spartenbedingt | Ein Teilkasko-Selbstbehalt existiert nur bei Kaskodeckung (Abschnitt 3.6) |
| `angebot.sb_vk_eur` | nur Sparte 052 | spartenbedingt | Ein Vollkasko-Selbstbehalt existiert nur in der Vollkasko (Abschnitt 3.6) |
| `person.familienstand` | nicht bei `anrede` = FIRMA | zeilenbezogen | Eine juristische Person hat keinen Familienstand (Abschnitt 3.2) |

**Warum die zeilenbezogene Bedingung nötig ist — ein gemessenes Beispiel.** Im
Clean-Baseline-Lauf der Phase 3 war zunächst nur die spartenbedingte Form umgesetzt. Auf
10.000 Anfragen meldete R-057 daraufhin **135 Fehlalarme**: Der Datensatz enthält 196
Personensätze mit `anrede` = FIRMA, bei denen `familienstand` planmäßig leer ist; 135 davon
gehören zu einer Anfrage, deren Kanalprofil den Familienstand als Pflicht führt. Das war der
**einzige** Befund des gesamten Clean-Baseline-Laufs. Nach Aufnahme der zeilenbezogenen
Bedingung sind es null (`docs/iteration_log.md`, Abschnitt „Phase 3").

**Die Bedingung gilt vor dem Profil, nicht danach.** Erst wird geprüft, ob das Feld in dieser
Zeile fachlich existiert; nur dann wird gefragt, ob das Profil es als Pflicht führt.

**Auch R-041 verweist hierher.** Die Regel „genau eines von `sb_hausrat_prozent` und
`sb_hausrat_eur` ist gefüllt" gilt nur, wenn die Sparte einen Hausrat-Selbstbehalt kennt —
also in Sparte 130. In den Kfz-Sparten sind beide Felder durch Zweckbindung leer; eine
Prüfung dort meldete jeden Kfz-Vergleich.

Umgesetzt in `src/rules/g5_quellen.py` (`_ANWENDBARKEIT`) und in
`src/rules/g2_satz.py` (R-041).

---

## 6. Zwei Datenschichten: `df_raw` und `df_typed`

Diese Trennung ist keine Formalie. Ohne sie sind mehrere Regeln nicht verletzbar und
mehrere Fehlerklassen nicht injizierbar.

| Schicht | Typisierung | Zweck |
|---|---|---|
| **`df_raw`** | **alle Spalten als String** | Bildet ab, was aus einer Schnittstelle ankommt. Hier sind Formatfehler, Typfehler und Sentinel-Werte überhaupt darstellbar |
| **`df_typed`** | `date`, `Decimal`, `int`, `bool`, kategorial | Ergebnis des Parsens. Hier laufen die fachlichen Prüfungen |

### Warum das nötig ist

In einer `datetime64`-Spalte kann kein `31022026` stehen — der Wert ist nicht schreibbar.
Eine als String geführte PLZ kann keine führende Null verlieren. Ein `Decimal`-Feld nimmt
kein `"k.A."` auf. Und `pyarrow` schreibt gemischt typisierte Spalten nicht in Parquet,
sondern wirft `ArrowInvalid`.

Ohne Rohschicht wären R-002, R-007, R-008, R-009, R-013, R-017 und R-025 **per Konstruktion
nicht verletzbar** — sie würden in der Auswertung mit undefiniertem Recall erscheinen. Und
die Injektionsvarianten F1-b bis F1-f, F2-a, F2-f bis F2-k, F3-c und F3-g wären nicht
umsetzbar.

Zugleich ist die Trennung fachlich richtig: GDV-Datensätze sind Fixed-Length-Strings, das
Parsen ist ein eigener Verarbeitungsschritt — und genau dort entstehen in der Praxis die
Format- und Skalierungsfehler, um die es in dieser Arbeit geht.

### Verarbeitungskette

```
Generator  →  df_typed (sauber, intern konsistent)
           →  serialisieren  →  df_raw (alle Spalten str)

Injektor   →  arbeitet auf df_raw  →  df_raw_dirty

Regel-Engine → Formatregeln auf df_raw_dirty
             → parsen (Parsefehler = Befund, kein Absturz)
             → fachliche Regeln auf df_typed_dirty
```

Der Parser gibt für nicht parsebare Werte `pd.NA` zurück **und protokolliert die Stelle**.
Er wirft keine Exception — ein nicht parsebarer Wert ist genau der Fall, den die Arbeit
untersucht.

### Serialisierungsregeln `df_typed` → `df_raw`

| Typ | Serialisierung |
|---|---|
| `date` | `TTMMJJJJ` (GDV-Konvention). **Leer wird zum Leerstring, nicht zu `00000000`** |
| `datetime` | ISO 8601 |
| `Decimal` | Dezimalpunkt, zwei Nachkommastellen, kein Tausendertrenner |
| `int` | ohne führende Nullen, außer bei HSN und PLZ |
| `bool` | `J` / `N` |
| leer | leerer String in `df_raw`, `pd.NA` in `df_typed` — **für alle Typen, auch für Datumsfelder** |

**Warum `00000000` nicht der Leerwert ist.** Im echten GDV-Format steht `00000000` für
„nicht belegt". In diesem Modell wird es bewusst **nicht** so verwendet, denn dann wäre es
ein legitimer Nullwert — und R-025 könnte es nicht mehr als impliziten Fehlwert melden,
während R-009 es als Nicht-Kalendertag ausnehmen müsste. Beide Regeln verlören ihre Schärfe.

Die Zuordnung ist deshalb eindeutig:

| Wert in `df_raw` | Bedeutung | Reaktion |
|---|---|---|
| Leerstring | regulär leer | kein Befund |
| `00000000` | Sentinel, als Wert getarnter Fehlwert | R-025 meldet |
| `01011900` | Sentinel | R-025 meldet |
| `31022026` | acht Ziffern, kein Kalendertag | R-009 meldet |

Das ist eine bewusste Abweichung vom GDV-Original und in der Arbeit als solche zu
kennzeichnen. Der Gewinn: Die Unterscheidung zwischen *leer* und *als leer getarnt* bleibt
messbar — und genau darum kreist die Fehlerklasse B1.

**Beide Schichten werden als Parquet abgelegt.** `df_raw` ist damit typstabil (alles str)
und der Injektor kann jeden beliebigen Fehlerwert schreiben.
