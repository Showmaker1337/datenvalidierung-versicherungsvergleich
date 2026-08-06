# Spezifikation 2 — Regelkatalog

**Dieser Katalog ist das Design-Artefakt der Bachelorarbeit.** Er wird vor der
Implementierung des Fehlerinjektors eingefroren (Git-Tag `freeze-regelkatalog`).

58 Regeln, gruppiert nach Achse A (Prüfgranularität). Die ID-Bereiche sind fest:

| Bereich | Achse A | Anzahl |
|---|---|---|
| R-001 – R-025 | G1 Attributwert | 25 |
| R-026 – R-042 | G2 Tupel / Satz | 17 |
| R-043 – R-048 | G3 Relation | 6 |
| R-049 – R-051 | G4 relationsübergreifend | 3 |
| R-052 – R-058 | G5 quellenübergreifend | 7 |

---

## Achsen der Taxonomie

**Achse A — Prüfgranularität:** G1 Attributwert · G2 Tupel · G3 Relation ·
G4 relationsübergreifend · G5 quellenübergreifend.

**Achse B — Fehlerklasse:** B1 Vollständigkeit · B2 Gültigkeit/Konformität ·
B3 Genauigkeit/Plausibilität · B4 Konsistenz · B5 Eindeutigkeit · B6 Aktualität ·
B7 Repräsentationseinheitlichkeit.

**Achse C — Erkennbarkeitsgrad:** C1 deterministisch durch Constraint ·
C2 heuristisch/schwellenwertbasiert · C3 nur gegen externe Referenzdaten ·
C4 nicht automatisiert erkennbar.

**Schweregrad:** `HART` = eindeutige Verletzung · `WARNUNG` = Plausibilitätshinweis,
False Positives erwartet.

**Literaturkürzel:** RD = Rahm & Do (2000) · KIM = Kim et al. (2003) ·
OLI = Oliveira et al. (2005) · FOI = Foidl et al. (2022) · ABE = Abedjan et al. (2016) ·
FAN = Fan et al. (2008), CFD · CHU = Chu et al. (2013), Denial Constraints ·
DAMA = DAMA UK (2013) · ISO = ISO/IEC 25012.

---

## G1 — Attributwertebene (R-001 – R-025)

| ID | Prädikat (muss erfüllt sein) | Geltungsbereich | A/B/C | Schwere | Literatur | Fachliche Grundlage |
|---|---|---|---|---|---|---|
| R-001 | Kernpflichtfelder sind nicht leer: `anfrage_id`, `sparte`, `eingangszeitpunkt`, `vn_person_id`, `nachname`, `plz`. Bedingt zusätzlich: `anrede` ≠ FIRMA → `geburtsdatum` nicht leer | alle | G1/B1/C1 | HART | RD; KIM 1.2; FAN CFD; DAMA Completeness | Ohne diese Felder ist keine Tarifierung möglich. Der bedingte Teil ist ein zweites CFD-Beispiel neben R-033: Eine juristische Person hat kein Geburtsdatum |
| R-002 | `plz` erfüllt `^\d{5}$` und ist als String geführt | person | G1/B2/C1 | HART | FOI „Integer as String"; RD „Illegal attribute values" | Führende Null (`01067`) geht bei Integer-Typisierung verloren |
| R-003 | `iban` erfüllt `^DE\d{20}$` (genau 22 Zeichen) | zahlung | G1/B2/C1 | HART | RD; DAMA Validity | ISO 13616, deutsche IBAN-Länge |
| R-004 | `iban` besteht die Prüfziffernprüfung Mod 97-10 | zahlung | G1/B2/C1 | HART | RD; ISO Accuracy | ISO 7064, siehe Pseudocode unten |
| R-005 | `bic` hat exakt 8 oder 11 Zeichen | zahlung | G1/B2/C1 | HART | RD | ISO 9362 — 9 oder 10 Zeichen existieren nicht |
| R-006 | `email` erfüllt das vereinfachte RFC-5322-Muster | person | G1/B2/C1 | HART | RD „Misspellings"; FOI Syntactic | |
| R-007 | `hsn` erfüllt `^\d{4}$` | risiko_kfz | G1/B2/C1 | HART | RD | KBA, Zulassungsbescheinigung Teil I, Feld 2.1 |
| R-008 | `tsn` erfüllt `^[A-Z0-9]{3}$` | risiko_kfz | G1/B2/C1 | HART | RD | Zulassungsbescheinigung Teil I, Feld 2.2 |
| R-009 | Jedes Datumsfeld auf der Rohdatenschicht ist ein existierender Kalendertag | alle (Rohschicht `df_raw`) | G1/B2/C1 | HART | RD; FOI | `31022026` ist formal achtstellig, aber kein Kalendertag. **Diese Regel arbeitet zwingend auf der Rohdatenschicht** — auf der typisierten Schicht ist sie per Konstruktion nicht verletzbar (siehe `spec/01`, Abschnitt 6) |
| R-010 | `zahlweise` ∈ {1, 2, 4, 5, 6, 8, 9} | anfrage | G1/B2/C1 | HART | RD „Illegal attribute values"; KIM 2.1.1.1 | GDV Anlage 14 — **3 und 7 existieren nicht.** Reine Bereichsprüfung würde sie durchlassen |
| R-011 | `sparte` ∈ {051, 052, 053, 130} | anfrage, tarif | G1/B2/C1 | HART | RD | GDV Anlage 1, Spartenverzeichnis |
| R-012 | `waehrung` existiert im ISO-4217-Katalog (`waehrungen.csv`) **und** ist im Kontext dieses Systems `EUR` | anfrage | G1/B2/C1 | HART | RD | ISO 4217. Zweistufig: Die erste Stufe prüft syntaktische Gültigkeit gegen den Katalog, die zweite die fachliche Zulässigkeit im Modell. Ein hübsches kleines Beispiel dafür, dass „gültig“ und „zulässig“ nicht dasselbe sind — beide Stufen werden getrennt gemeldet |
| R-013 | `sf_klasse_*` ∈ {`0`, `1/2`, `S`, `M`, `SF1`…`SF50`} und als String geführt | risiko_kfz | G1/B2/C1 | HART | RD; FOI Encoding | Sonderklassen sind keine Zahlen — Integer-Typisierung ist hier ein Modellierungsfehler |
| **R-014** | `typklasse_hp` ∈ [10, 25], `typklasse_tk` ∈ [10, 33], `typklasse_vk` ∈ [10, 34] | risiko_kfz | G1/B2/C1 | HART | RD; KIM 2.1.1.1; DAMA Validity | GDV-Typklassenverzeichnis: 16 / 24 / 25 Klassen |
| R-015 | `regionalklasse_hp` ∈ [1, 12], `_tk` ∈ [1, 16], `_vk` ∈ [1, 9] | risiko_kfz | G1/B2/C1 | HART | RD | GDV-Regionalklassen: 12 / 16 / 9 Stufen |
| R-016 | `zuers_zone` ∈ {1, 2, 3, 4} | risiko_hausrat | G1/B2/C1 | HART | RD | ZÜRS-Gefährdungsklassen |
| R-017 | `bauartklasse` ∈ {`0`,`1`–`5`,`6`–`8`,`A`–`I`} und als String geführt | risiko_hausrat | G1/B2/C1 | HART | RD; FOI Encoding | GDV Anlage 12 — gemischt numerisch/alphabetisch |
| R-018 | `anfrage_status` ∈ definiertem Enum | anfrage | G1/B2/C1 | HART | RD | |
| R-019 | `nutzungsart` ∈ {`01`, `02`, `03`, `08`} | risiko_kfz | G1/B2/C1 | HART | RD | GDV Satzart 0210.050 |
| R-020 | `art_kennzeichen` ∈ {`01`, `04`, `54`} | risiko_kfz | G1/B2/C1 | HART | RD | GDV Satzart 0210.050 |
| R-021 | Alle Beitrags- und Summenfelder sind ≥ 0 | angebot, risiko_hausrat, tarif | G1/B3/C1 | HART | RD; KIM 2.1 | Negative Beiträge sind fachlich unmöglich |
| R-022 | `wohnflaeche_qm` ∈ [10, 1000] | risiko_hausrat | G1/B3/C2 | WARNUNG | ABE Outliers; FOI Believability | Werte außerhalb sind Eingabe- oder Einheitenfehler |
| R-023 | `baujahr` ∈ [1500, Jahr(`stichtag`)] | risiko_hausrat | G1/B3/C1 | HART | RD; FOI | Baujahr in der Zukunft ist unmöglich |
| R-024 | `deckungssumme_personen_eur` ≥ 7.500.000 ∧ `_sach` ≥ 1.300.000 ∧ `_vermoegen` ≥ 50.000 | tarif | G1/B3/C1 | HART | RD; DAMA Accuracy | PflVG, Anlage zu § 4 Abs. 2 — gesetzliche Mindestdeckung |
| R-025 | Kein Feld enthält einen impliziten Fehlwert. Textfelder: Leerstring, `-`, `k.A.`, `n/a`, `unbekannt`. Datumsfelder: `0000-00-00`, `1900-01-01`. Numerische Felder: `9999` und `99999999` — **aber nur in Feldern, deren fachlicher Wertebereich diese Zahlen ausschließt.** Ausgenommen sind `jahresfahrleistung_km` und alle Sublimit-Felder, in denen 9999 ein legitimer Wert ist | alle | G1/B1/C2 | WARNUNG | FOI *Dummy Value*; RD; KIM 2.2 | Fehlwerte, die als gefüllte Werte getarnt sind — der klassische Fall, den reine NOT-NULL-Prüfungen verfehlen. Die Ausnahmeliste ist selbst ein Diskussionspunkt: Sie zeigt die Grenze von Sentinel-Heuristiken, sobald der Sentinel im legitimen Wertebereich liegt |

### Pseudocode R-004 (IBAN, ISO 7064 Mod 97-10)

```
1. Leerzeichen entfernen, in Großbuchstaben wandeln
2. Die ersten 4 Zeichen ans Ende verschieben
3. Jeden Buchstaben ersetzen: A=10, B=11, ..., Z=35
4. Ergebnis als ganze Zahl interpretieren
5. gültig genau dann, wenn zahl mod 97 == 1
```

---

## G2 — Satzebene (R-026 – R-042)

| ID | Prädikat (muss erfüllt sein) | Geltungsbereich | A/B/C | Schwere | Literatur | Fachliche Grundlage |
|---|---|---|---|---|---|---|
| R-026 | `erstzulassung` ≤ `stichtag` | risiko_kfz | G2/B3/C1 | HART | RD „Violated attribute dependencies"; FAN | Erstzulassung kann nicht in der Zukunft liegen |
| R-027 | `erstzulassung` ≤ `zulassung_auf_vn` ≤ `stichtag` | risiko_kfz | G2/B4/C1 | HART | FAN CFD; RD | Ein Fahrzeug wird nicht vor seiner Erstzulassung auf den VN zugelassen |
| R-028 | `fuehrerschein_datum` ≥ `geburtsdatum` + 17 Jahre ∧ ≤ `stichtag` | person | G2/B4/C1 | HART | FAN; RD | Begleitetes Fahren ab 17 ist die Untergrenze |
| R-029 | `schadenfreie_jahre(sf_klasse_hp)` ≤ Alter(VN) − 17 (Abbildung siehe `spec/01`, Abschnitt 2.8; Sonderklassen ergeben 0 und erfüllen die Regel trivial) | risiko_kfz + person | G2/B4/C1 | HART | FAN CFD; CHU | Man kann nicht länger schadenfrei fahren, als man den Führerschein besitzt |
| R-030 | `sf_ordnung(sf_klasse_vk)` ≤ `sf_ordnung(sf_klasse_hp)` (vollständige Ordnung einschließlich der Sonderklassen, siehe `spec/01`, Abschnitt 2.8) | risiko_kfz | G2/B4/C2 | WARNUNG | FAN | Marktüblich; Ausnahmen existieren, daher Warnung |
| **R-031** | `bruttobeitrag_jahr_eur` = `nettobeitrag_jahr_eur` + `versicherungsteuer_eur`, Toleranz ±0,02 € | angebot | G2/B4/C1 | HART | FAN CFD; CHU DC; DAMA Consistency | Beitragsarithmetik |
| R-032 | `versicherungsteuer_eur` = ROUND_HALF_UP(`netto` × `satz` / 100, 2) | angebot | G2/B4/C1 | HART | FAN | § 6 i. V. m. § 5 VersStG |
| R-033 | `versicherungsteuer_satz` entspricht dem Effektivsatz der Sparte (051/052/053 → 19,00; 130 → 16,15) | angebot | G2/B4/C1 | HART | FAN CFD | § 6 Abs. 2 i. V. m. § 5 Abs. 1 Nr. 3 VersStG. **Musterbeispiel einer Conditional Functional Dependency:** Der zulässige Wert hängt vom Wert eines anderen Feldes ab |
| R-034 | Bei steuerfreien Sparten (Leben, Kranken, BU, Rente, Pflege) ist `versicherungsteuer_eur` = 0 | angebot | G2/B4/C1 | HART | FAN | § 4 VersStG. **Im aktuellen Datenmodell nicht auslösbar**, da diese Sparten nicht erzeugt werden — bewusst implementiert und als solche gekennzeichnet |
| R-035 | `zahlweise` ∈ {1, 6} → `ratenzahlungszuschlag_prozent` = 0 | anfrage + angebot | G2/B4/C1 | HART | FAN CFD | Ohne Ratenzahlung kein Ratenzuschlag |
| R-036 | `zahlbeitrag_rate_eur` × Ratenanzahl(`zahlweise`) ≥ `bruttobeitrag_jahr_eur` − (0,01 × Ratenanzahl) | angebot | G2/B4/C1 | HART | CHU DC | Unterjährige Zahlung ist nie günstiger als jährliche. **Die Toleranz skaliert mit der Ratenanzahl**, weil sich der Rundungsfehler je Rate aufsummiert: Bei 12 Raten sind bis zu 0,06 € Differenz rein rundungsbedingt. Eine feste Toleranz von 0,02 € würde auf sauberen Daten auslösen |
| R-037 | `annahmeentscheidung` = ABLEHNUNG ↔ alle Beitragsfelder leer | angebot | G2/B4/C1 | HART | FAN; RD | Ein abgelehntes Risiko hat keinen Beitrag |
| R-038 | `fahrzeugwert_aktuell` ≤ `neupreis_eur` | risiko_kfz | G2/B3/C1 | HART | CHU DC | Ein Fahrzeug ist nicht mehr wert als neu |
| R-039 | `art_kennzeichen` = `54` → `antriebsart` ∈ {ELEKTRO, HYBRID} | risiko_kfz | G2/B4/C1 | HART | FAN CFD | E-Kennzeichen setzt elektrischen Antrieb voraus (EmoG) |
| R-040 | `unterversicherungsverzicht` = True → `versicherungssumme_eur` ≥ 650 × `wohnflaeche_qm` | risiko_hausrat | G2/B4/C2 | WARNUNG | FAN CFD | Branchenübliche Faustregel 650 €/m². Als Modellannahme kennzeichnen |
| R-041 | Genau eines von `sb_hausrat_prozent` und `sb_hausrat_eur` ist gefüllt — **nur anwendbar, wenn die Sparte einen Hausrat-Selbstbehalt kennt** (`spec/01`, Abschnitt 5.2) | angebot | G2/B4/C2 | WARNUNG | RD; KIM | **Modellannahme des Schemas**, kein Domänenfakt — reale Produkte kennen kombinierte Formen („10 %, mind. 500 €, max. 2.500 €") |
| R-042 | `sublimit_fahrrad_eur` ≤ `versicherungssumme_eur` ∧ `sublimit_wertsachen_eur` ≤ `versicherungssumme_eur` | risiko_hausrat | G2/B4/C1 | HART | CHU DC | Ein Sublimit kann die Gesamtsumme nicht übersteigen |

---

## G3 — Relationsebene (R-043 – R-048)

| ID | Prädikat (muss erfüllt sein) | Geltungsbereich | A/B/C | Schwere | Literatur | Fachliche Grundlage |
|---|---|---|---|---|---|---|
| R-043 | `rang` je `anfrage_id` ist lückenlos 1..n und eindeutig | angebot | G3/B5/C1 | HART | RD „Uniqueness violation"; DAMA Uniqueness | Ein Vergleichsergebnis hat eine vollständige Rangfolge |
| R-044 | `rang` ist aufsteigend nach `zahlbeitrag_rate_eur` sortiert | angebot | G3/B4/C1 | HART | CHU DC | Ein Preisvergleich sortiert nach Preis |
| R-045 | Kein Duplikat über (`anfrage_id`, `tarif_id`) | angebot | G3/B5/C1 | HART | RD; ABE Duplicates; DAMA Uniqueness | Derselbe Tarif erscheint nicht zweimal im selben Vergleich. `tarifgeneration` ist kein Feld von `angebot` und wäre über `tarif_id` ohnehin funktional bestimmt |
| R-046 | Je `anfrage_id` existiert genau eine `person` mit `rolle` = VN | person | G3/B5/C1 | HART | RD; OLI | |
| R-047 | max(`zahlbeitrag_rate_eur`) / min(...) je `anfrage_id` ≤ 6 | angebot | G3/B3/C2 | WARNUNG | ABE Outliers; FOI Believability | Eine extreme Spreizung deutet auf einen Einheiten- oder Mappingfehler bei einem Anbieter hin. Schwellenwert ist eine Modellannahme und im Text zu begründen |
| R-048 | Die empirische Verteilung von `zuers_zone` weicht je Zone um höchstens **30 Prozent relativ** von (92,4 / 6,1 / 1,1 / 0,4) ab | risiko_hausrat, Gesamtdatensatz | G3/B3/C2 | WARNUNG | ABE; Schelter et al. (Deequ, Metrik-Constraints) | Verteilungsprüfung statt Einzelwertprüfung. **Relative statt absolute Toleranz:** ±5 Prozentpunkte würden Zone 4 einen Sprung von 0,4 auf 5,4 Prozent erlauben — Faktor 13,5 — also genau den Fall nicht fangen, für den die Regel gedacht ist. **Diese Regel meldet keine einzelne Zelle** und geht deshalb nicht in die Zellmetrik ein, sondern wird als eigene Diagnosekennzahl berichtet |

---

## G4 — Relationsübergreifend (R-049 – R-051)

| ID | Prädikat (muss erfüllt sein) | Geltungsbereich | A/B/C | Schwere | Literatur | Fachliche Grundlage |
|---|---|---|---|---|---|---|
| R-049 | Alle Fremdschlüssel sind auflösbar: `angebot.anfrage_id`, `angebot.tarif_id`, `anfrage.vn_person_id`, `risiko_*.anfrage_id`, `zahlung.anfrage_id` | alle | G4/B4/C1 | HART | RD „Referential integrity violation"; OLI Multi-Relation | Entspricht der GDV-Referenzlogik (Satzart 0220 → 0210 über Referenznummer, → 0100 über Personennummer) |
| R-050 | `plz` existiert in `plz_ort` ∧ `ort` stimmt mit dem Referenzeintrag überein | person | G4/B3/C3 | HART | RD „Wrong references"; FAN CFD; ISO Accuracy (semantic) | Klassisches CFD-Beispiel: Land bestimmt PLZ bestimmt Ort |
| R-051 | (`hsn`, `tsn`) existiert in `typklassen` ∧ die abgeleiteten Felder `leistung_kw`, `antriebsart`, `typklasse_*` stimmen mit dem Referenzeintrag überein | risiko_kfz | G4/B4/C3 | HART | RD; FAN | Abweichung deutet auf einen Mappingfehler zwischen Schnittstelle und Fahrzeugkatalog hin |

---

## G5 — Quellenübergreifend (R-052 – R-058)

Diese Gruppe ist der Kern der Domäne: Ein Vergleichssystem bezieht strukturell
gleichartige Sachverhalte über Schnittstellen mit unterschiedlicher Semantik, Kodierung
und Aktualität (GDV und BiPRO koexistieren). Das ist die Lehrbuchdefinition eines
Multi-Source-Problems nach Rahm & Do.

| ID | Prädikat (muss erfüllt sein) | Geltungsbereich | A/B/C | Schwere | Literatur | Fachliche Grundlage |
|---|---|---|---|---|---|---|
| **R-052** | Innerhalb einer `anfrage_id` verwenden alle Angebote dieselbe Einheitenkonvention für den Selbstbehalt (entweder alle Prozent oder alle Betrag) | angebot | G5/B7/C2 | WARNUNG | RD „Different value representations"; KIM 2.2.3; FOI Consistency; DAMA Consistency | Anbieter A liefert den Selbstbehalt in Euro, Anbieter B in Prozent — der Vergleich wird dadurch unzulässig |
| R-053 | **`bruttobeitrag_jahr_eur`** liegt je Sparte im plausiblen Korridor (Kfz: 40 – 6.000 €; Hausrat: 20 – 2.000 €). **Nicht `zahlbeitrag_rate_eur`** — die Rate ist bei monatlicher Zahlweise ein Zwölftel und läge systematisch unterhalb des Korridors | angebot | G5/B3/C2 | WARNUNG | ABE Outliers; FOI | Werte weit außerhalb deuten auf Cent-statt-Euro-Interpretation hin — Ursache: implizite Dezimalstellen im GDV-Format („10,2" bedeutet 10 Vor- und 2 Nachkommastellen ohne Trennzeichen) |
| R-054 | Kein Angebot einer Anfrage weicht um näherungsweise den Faktor 12 (± 5 %) vom Median der übrigen Angebote derselben Anfrage ab | angebot | G5/B7/C2 | WARNUNG | RD; FOI Consistency | Monats- statt Jahresbeitrag. **Wichtig:** Diese Verwechslung ist ein Faktor 12 und deshalb nicht über eine absolute Untergrenze zu finden, sondern nur relational |
| R-055 | `berechnungszeitpunkt` ∈ [`tarif.gueltig_ab`, `tarif.gueltig_bis`] | angebot + tarif | G5/B6/C1 | HART | RD; DAMA Timeliness; ISO Currentness | **Veralteter Tarifstand** — die klassische Fehlerklasse von Vergleichsportalen. Ursache in der Praxis: GDV-Bestandsdaten werden meist nur monatlich erzeugt, Änderungen kommen mit Wochen Verzug an |
| R-056 | `tarif.gueltig_bis` > `tarif.gueltig_ab` | tarif | G5/B6/C1 | HART | RD | |
| R-057 | Das Pflichtfeldprofil ist eingehalten, **zweigeteilt**: (a) Felder der Anfrageseite (`person`, `risiko_*`, `zahlung`) gegen das Profil je `anfrage.kanal`; (b) Felder von `angebot` gegen das Profil je `quell_schnittstelle`. Die Zweiteilung ist nötig, weil `quell_schnittstelle` ein Feld von `angebot` ist, die Anfrageseite aber einmal je Anfrage erfasst wird — es gäbe sonst kein eindeutiges Profil. Beide Profile stehen in `spec/01`, Abschnitte 5 und 5.1. **Anwendbarkeitsbedingung beachten** (`spec/01`, Abschnitt 5.2): Ein Feld, das die Zweckbindung ohnehin leer lässt, wird nicht geprüft | angebot + anfrage | G5/B1/C2 | WARNUNG | RD Multi-Source; DAMA Completeness | Versicherer befüllen dasselbe Feld unterschiedlich tief; das Pflichtfeldprofil steht in `spec/01_datenmodell.md`, Abschnitt 5 |
| R-058 | `regionalklasse_hp`, `_tk` und `_vk` stimmen mit dem Eintrag zu `zulassungsbezirk` in `regionalklassen.csv` überein | risiko_kfz | G5/B4/C3 | HART | FAN CFD; CHU DC | Referenzabgleich, analog zu R-051 für HSN/TSN. **Achtung:** Regionalklassen hängen am Zulassungsbezirk, nicht an der PLZ — PLZ-Gebiete können Bezirksgrenzen schneiden. Der Bezug zum Tarifstand entfällt, weil `risiko_kfz` keinen Bezug zu `tarif` hat |

---

## Regeln, die bewusst NICHT im Katalog stehen (Held-out)

Diese Fehlerarten werden injiziert, aber **nicht** geprüft. Der erwartete Recall liegt
nahe null. Das ist kein Mangel, sondern das ehrlichste Ergebnis der Arbeit: Es
quantifiziert die Grenze regelbasierter Verfahren und beantwortet das „inwieweit" der
Forschungsfrage.

| Held-out-Klasse | Beschreibung | Warum nicht regelbasiert erkennbar |
|---|---|---|
| **HO1 — Semantische Duplikate** | Zwei `person`-Sätze mit „Müller, Hans-Peter" und „Mueller, Hans Peter", gleichem Geburtsdatum, leicht abweichender Straßenschreibweise | Erfordert Fuzzy-Matching und Schwellenwertentscheidungen, nicht ein deterministisches Prädikat. Achse C4 |
| **HO2 — Semantisch falsche, aber formal gültige Werte** | Eine gültige, existierende PLZ, die aber nicht die Adresse des VN ist; ein plausibler, aber falscher Beitrag | Erfordert externen Abgleich gegen die Realität (semantische Accuracy nach Batini & Scannapieco). Achse C3/C4 |

**Wichtige Abgrenzung für die Auswertung:** R-045 prüft *exakte* Duplikate über einen
definierten Schlüssel. HO1 sind *semantische* Duplikate. Ohne diese explizite Abgrenzung
wirkt die Hypothese „der Recall unterscheidet sich zwischen Fehlerklassen" trivial
erfüllt, weil der Unterschied nur die Definitionsgrenze abbildet.

---

## Mapping-Tabelle

Der Katalog oben **ist** die Mapping-Tabelle in Kurzform. Für den Anhang der Arbeit wird
sie um die Spalte „Injektionsvarianten" ergänzt, sobald `spec/03_fehlerklassen.md`
umgesetzt ist:

```
Literaturbeleg → Taxonomieklasse (A/B/C) → Regel-ID → Injektionsvariante → Auswertungsklasse
```

Diese eine Tabelle beantwortet im Kolloquium die meisten Nachfragen zur Herleitung,
bevor sie gestellt werden.

---

## Kennzahlen des Katalogs

| Kennzahl | Wert |
|---|---|
| Regeln gesamt | 58 |
| davon HART | 47 |
| davon WARNUNG | 11 |
| C1 (deterministisch) | 45 |
| C2 (heuristisch) | 11 |
| C3 (referenzdatenabhängig) | 2 |
| Nicht auslösbar im aktuellen Datenmodell | 1 (R-034) |

Diese Verteilung ist selbst ein Ergebnis: Sie sagt vorab, wo hohe Precision zu erwarten
ist (C1) und wo systematisch False Positives entstehen werden (C2).

---

## Auf welcher Datenschicht eine Regel arbeitet

`spec/01_datenmodell.md`, Abschnitt 6, führt zwei Schichten ein: `df_raw` (alle Felder als
String, wie aus einer Schnittstelle geliefert) und `df_typed` (geparst und typisiert).

| Regelgruppe | Schicht | Begründung |
|---|---|---|
| R-002, R-007, R-008, R-009, R-013, R-017, R-025 | **`df_raw`** | Format-, Typ- und Sentinel-Prüfungen sind auf typisierten Daten per Konstruktion nicht verletzbar. Eine `datetime.date` kann kein 31.02. sein, eine als String geführte PLZ hat keine verlorene führende Null |
| R-003, R-004, R-005, R-006 | `df_raw` | Prüfziffern und Muster |
| alle übrigen | `df_typed` | Fachliche Prüfungen setzen geparste Werte voraus |

Diese Zweiteilung bildet zugleich die Realität der Domäne ab: GDV-Datensätze sind
Fixed-Length-Strings, das Parsen ist ein eigener Verarbeitungsschritt — und genau dort
entstehen in der Praxis die Format- und Skalierungsfehler.

---

## Regeln ohne zugehörige Injektionsvariante

Fünfzehn Regeln haben in `spec/03_fehlerklassen.md` bewusst keine eigene Variante:
R-011, R-012, R-018, R-019, R-020, R-024, R-027, R-028, R-030, R-034, R-037, R-040,
R-041, R-050, R-057.

**Das ist Absicht und ein berichtbares Ergebnis, kein Versäumnis.** Diese Regeln können in
der Auswertung nur Precision kosten, nie Recall bringen. Der Anteil unbenutzter Regeln ist
die Kennzahl „Überdeckung des Katalogs" und gehört in die Ergebnisdarstellung
(`t3_regeldiagnose.csv`): Ein literaturbasiert hergeleiteter Katalog deckt notwendigerweise
mehr ab, als ein konkretes Fehlermodell auslöst.

Formuliere das in der Arbeit aktiv, statt es zu verschweigen — ein Prüfer, der 15 Regeln
mit null Treffern in der Tabelle findet, wird sonst annehmen, sie seien vergessen worden.
