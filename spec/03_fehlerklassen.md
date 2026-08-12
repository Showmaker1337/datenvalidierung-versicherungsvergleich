# Spezifikation 3 — Fehlerklassen, Injektionsvarianten und Ground Truth

Diese Datei wird **erst nach dem Freeze des Regelkatalogs** implementiert.

Konzeptionelle Referenzen, die in der Arbeit zitiert werden müssen: BART
(Arocena et al. 2015) für kontrollierte Injektion mit steuerbarer Menge und
Reparaturschwierigkeit, Jenga (Schelter et al. 2021) für den Korruptionskatalog,
REIN (Abdelaal et al. 2023) für die Kombination aus Benchmark-Injektion und eigener
Python-Fehlergeneratorbibliothek. REIN legitimiert das Vorgehen: ein eigener Injektor in
Python ist publizierte Praxis, keine Behelfslösung.

---

## 1. Die acht Fehlerklassen (Faktor UV1)

Abgeleitet aus Achse B der Taxonomie. Die Zuordnung ist bewusst **nicht bijektiv** — B1
und B2 werden feiner aufgelöst, weil sie die häufigsten Praxisfälle sind.

| ID | Fehlerklasse | Achse B | Zielfelder |
|---|---|---|---|
| F1 | Fehlender Wert (explizit und implizit) | B1 | alle Pflichtfelder |
| F2 | Format- und Syntaxverletzung | B2 | PLZ, IBAN, BIC, E-Mail, HSN, TSN, Datumsfelder |
| F3 | Wertebereichs- und Katalogverletzung | B2 | Zahlweise, Sparte, Typklassen, Regionalklassen, ZÜRS, SF-Klasse, Bauartklasse |
| F4 | Fachlich unmöglicher, syntaktisch valider Wert | B3 | Erstzulassung, Baujahr, Wohnfläche, Deckungssummen, Fahrzeugwert |
| F5 | Intra-Record-Inkonsistenz inkl. Beitragsarithmetik | B4 | Brutto/Netto/Steuer, SF ↔ Alter, Kennzeichen ↔ Antrieb, Sublimits |
| F6 | Duplikat mit Konfliktwerten (exakt) | B5 | Angebotszeilen, Personensätze |
| F7 | Veralteter Tarifstand / Gültigkeitsverletzung | B6 | Berechnungszeitpunkt, Tarifgültigkeit |
| F8 | Einheiten- und Repräsentationsfehler zwischen Quellen | B7 | Selbstbehalt, Beiträge, Skalierung |

Zusätzlich die beiden **Held-out-Klassen** aus dem Regelkatalog:

| ID | Held-out-Klasse | Erwarteter Recall |
|---|---|---|
| HO1 | Semantische Duplikate (Namensvarianten, Tippfehler) | ≈ 0 |
| HO2 | Semantisch falsche, formal gültige Werte | ≈ 0 |

---

## 2. Injektionsvarianten

**Das ist der methodisch wichtigste Teil der ganzen Implementierung.** Jede Fehlerklasse
bekommt mehrere Varianten, und nur ein Teil davon spiegelt die Regelbedingung exakt.
Nur so wird der klassenweise Recall aussagekräftig statt trivial 1,0 — und nur so lässt
sich der Zirkularitätsvorwurf empirisch entkräften statt bloß rhetorisch.

Die `injektor_variante_id` wird im Ground Truth mitgeloggt, und der Recall wird **je
Variante** berichtet.

### F1 — Fehlender Wert

| Variante | Verfälschung | Spiegelt Regel exakt? |
|---|---|---|
| F1-a | Wert auf `None` / `NaN` setzen | ja (R-001) |
| F1-b | Leerstring | **nein** — auf der Rohschicht nicht von einem planmäßig leeren Feld unterscheidbar. Nur über die Pflichtfeldregeln R-001 und R-057 erkennbar, nicht über R-025. Ein Informationsverlust der Serialisierung, kein Implementierungsmangel |
| F1-c | `"-"` | nein |
| F1-d | `"k.A."` | nein |
| F1-e | Numerisches Sentinel `9999` bzw. `99999999` | nein |
| F1-f | Datums-Sentinel `1900-01-01` | nein |

### F2 — Format und Syntax

| Variante | Verfälschung | Spiegelt Regel exakt? |
|---|---|---|
| F2-a | PLZ als Integer (führende Null verloren: `01067` → `1067`) | teilweise |
| F2-b | PLZ mit vier oder sechs Ziffern | ja (R-002) |
| F2-c | IBAN mit einer geänderten Ziffer (Prüfsumme bricht, Format bleibt) | ja (R-004) |
| F2-d | IBAN mit 21 oder 23 Zeichen | ja (R-003) |
| F2-e | BIC mit 9 oder 10 Zeichen | ja (R-005) |
| F2-f | Datum `31022026` — formal acht Ziffern, kein Kalendertag | ja (R-009) |
| F2-g | Datum `01132026` — Monat 13 | ja (R-009) |
| F2-h | Datum im Fremdformat `2026-02-01` statt `TTMMJJJJ` | nein (aus anderer Schnittstelle) |
| F2-i | Datum als Excel-Serial `45231` | nein |
| F2-j | HSN mit drei statt vier Stellen | ja (R-007) |
| F2-k | TSN mit Kleinbuchstaben | teilweise |
| F2-l | E-Mail ohne `@` oder ohne Punkt in der Domain | ja (R-006) |

### F3 — Wertebereich und Katalog

| Variante | Verfälschung | Spiegelt Regel exakt? |
|---|---|---|
| F3-a | Typklasse auf `99` setzen (weit außerhalb) | ja (R-014) |
| F3-b | Typklasse auf `9` setzen (knapp unterhalb der Untergrenze) | ja (R-014) |
| F3-c | Typklasse als Text `"TK12"` | nein (Typfehler statt Bereichsfehler) |
| F3-d | Zahlweise auf `3` setzen — **existiert im GDV-Katalog nicht, liegt aber im Zahlenbereich** | ja (R-010), aber nur durch Katalogprüfung, nicht durch Bereichsprüfung |
| F3-e | Zahlweise auf `7` setzen | wie F3-d |
| F3-f | ZÜRS-Zone auf `5` | ja (R-016) |
| F3-g | SF-Klasse als Integer `12` statt `"SF12"` | nein |
| F3-h | Bauartklasse `J` (existiert nicht) | ja (R-017) |
| F3-i | Regionalklasse auf `0` oder auf einen Wert über der Klassenobergrenze setzen | ja (R-015) |

Die Varianten F3-d und F3-e sind das Lehrbuchbeispiel des Katalogs: Eine reine
Range-Prüfung (1 ≤ x ≤ 9) lässt sie durch, nur die Domain-Prüfung fängt sie.

### F4 — Fachlich unmöglich, syntaktisch valide

| Variante | Verfälschung | Spiegelt Regel exakt? |
|---|---|---|
| F4-a | Erstzulassung auf `stichtag` + 2 Jahre | ja (R-026) |
| F4-b | Baujahr auf Jahr(`stichtag`) + 5 | ja (R-023) |
| F4-c | Wohnfläche auf 5.000 m² | ja (R-022) |
| F4-d | Wohnfläche auf 8 m² (knapp unterhalb der Schwelle) | ja (R-022), Grenzfall |
| F4-e | Fahrzeugwert auf das Dreifache des Neupreises | ja (R-038) |
| F4-f | Deckungssumme Personen auf 5.000.000 (unter PflVG-Minimum) | ja (R-024) |
| F4-g | Beitrag oder Versicherungssumme negativ setzen | ja (R-021) |

### F5 — Intra-Record-Inkonsistenz

| Variante | Verfälschung | Spiegelt Regel exakt? |
|---|---|---|
| F5-a | Brutto und Netto vertauschen (Brutto < Netto) | ja (R-031) |
| F5-b | Steuerbetrag mit falschem Satz berechnen (19 % statt 16,15 % bei Hausrat) | ja (R-032/R-033) |
| F5-c | Steuersatz der falschen Sparte eintragen | ja (R-033) |
| F5-d | Bruttobeitrag um 0,50 € **senken** (kleiner Arithmetikfehler oberhalb der Toleranz) | ja (R-031), Grenzfall |
| F5-e | Bruttobeitrag um 0,01 € **senken** (**innerhalb** der Toleranz) | nein — **erwartet unentdeckt**, prüft die Toleranzdefinition |
| F5-f | SF-Klasse auf einen Wert über (Alter − 17) setzen | ja (R-029) |
| F5-g | E-Kennzeichen setzen, Antriebsart auf BENZIN belassen | ja (R-039) |
| F5-h | Sublimit über die Versicherungssumme heben | ja (R-042) |
| F5-i | Ratenzuschlag > 0 bei jährlicher Zahlweise | ja (R-035) |

Variante F5-e ist bewusst so gebaut, dass sie **nicht** erkannt werden soll. Sie prüft,
ob die Toleranzgrenze korrekt implementiert ist, und liefert einen erklärbaren False
Negative — ein Befund, kein Fehler.

#### F5-d und F5-e sind Senkungen, keine Erhöhungen

Die Richtung war ursprünglich offen gelassen („um 0,50 € / 0,01 € verändern"). Festgelegt
ist beides als **Verringerung** des Bruttobeitrags. Der Grund liegt bei R-036
(`zahlbeitrag_rate_eur` × Ratenanzahl ≥ `bruttobeitrag_jahr_eur` − 0,01 × Ratenanzahl): Bei
jährlicher Zahlweise ist die Ratenanzahl 1 und der Ratenzuschlag 0, auf sauberen Daten gilt
dort also `rate = brutto` — die Ungleichung ist exakt ausgeschöpft.

- Eine **Erhöhung** um 0,50 € verletzte dort zusätzlich R-036. F5-d würde von zwei Regeln
  gemeldet, und die Zuordnung Variante → Regel in der Ergebnistabelle wäre falsch — genau
  der Fehler, den dieser Abschnitt bei der kohärenten Skalierung schon einmal beschreibt.
- Eine **Erhöhung** um 0,01 € landete bei jährlicher Zahlweise exakt auf der Grenze von
  R-036. Sie bestünde die Prüfung zwar (`≥`), aber eine „erwartet unentdeckte" Variante darf
  nicht auf einer Grenzgleichheit balancieren.
- Eine **Senkung** ist in beiden Fällen eindeutig: R-036 bekommt zusätzlichen Spielraum,
  R-031 entscheidet allein.

Als Fehlerbild ist die Senkung ebenso realistisch wie die Erhöhung — ein Rundungs- oder
Übertragungsfehler kennt keine Vorzugsrichtung. Die Festlegung ändert keine Regel und ist
deshalb kein Fall von Iteration 2.

### F6 — Exakte Duplikate

| Variante | Verfälschung | Spiegelt Regel exakt? |
|---|---|---|
| F6-a | Angebotszeile vollständig duplizieren, neue `angebot_id`, gleicher `rang` | ja (R-043/R-045) |
| F6-b | Angebotszeile duplizieren, `rang` neu vergeben (Rangfolge bekommt eine Lücke) | ja (R-043) |
| F6-c | Angebotszeile duplizieren, ein Beitragsfeld leicht abweichend (Konfliktduplikat) | ja (R-045) |
| F6-d | Zweiten Personensatz mit `rolle` = VN anlegen | ja (R-046) |

**Achtung:** Diese Klasse erzeugt zusätzliche Zeilen. Das zellbasierte Ground-Truth-Schema
greift hier nicht — siehe Abschnitt 4.

### F7 — Aktualität

| Variante | Verfälschung | Spiegelt Regel exakt? |
|---|---|---|
| F7-a | `tarif_id` auf eine ältere Generation umbiegen, deren Gültigkeit vor dem Berechnungszeitpunkt endete | ja (R-055) |
| F7-b | `berechnungszeitpunkt` um 18 Monate zurückdatieren | ja (R-055) |
| F7-c | `gueltig_bis` vor `gueltig_ab` legen | ja (R-056) |
| F7-d | Tarifgeneration um eine Stufe zurücksetzen, Gültigkeitszeitraum aber unverändert lassen | nein — **erwartet unentdeckt**, weil das Feld `tarifgeneration` nicht regelgeprüft wird |

### F8 — Einheiten und Repräsentation

| Variante | Verfälschung | Spiegelt Regel exakt? |
|---|---|---|
| F8-a | Bei einem Anbieter je Anfrage den Selbstbehalt von Betrag auf Prozent umstellen | ja (R-052) |
| F8-b | **Gesamtes Beitragstupel** mit 100 multiplizieren (Cent-statt-Euro) | ja (R-053) |
| F8-c | **Gesamtes Beitragstupel** durch 100 teilen | ja (R-053) |
| F8-d | **Gesamtes Beitragstupel** durch 12 teilen (Monats- statt Jahresbeitrag), ein Angebot | ja (R-054) |
| F8-e | **Gesamtes Beitragstupel** durch 12 teilen **bei allen** Angeboten einer Anfrage | nein — **erwartet unentdeckt**, weil R-054 relational gegen den Median der übrigen Angebote prüft und dieser mitwandert |

### Kohärente Skalierung — sonst kippt der wichtigste Befund

**„Gesamtes Beitragstupel" ist die entscheidende Vorgabe** und meint: `nettobeitrag_jahr_eur`,
`versicherungsteuer_eur`, `bruttobeitrag_jahr_eur` und `zahlbeitrag_rate_eur` werden
**gemeinsam** mit demselben Faktor skaliert.

Der Grund: Würde nur `zahlbeitrag_rate_eur` geteilt, verletzte das Angebot sofort R-031
(Brutto = Netto + Steuer) und R-036 (Rate × Ratenanzahl ≥ Brutto). Die Varianten wären
dann **garantiert erkannt** — und zwar von den falschen Regeln. F8-e, laut Konzept der
wertvollste Einzelfall des Injektors, wäre wertlos, und die Zuordnung Variante → Regel in
der Auswertung wäre falsch.

Bei kohärenter Skalierung bleiben R-031, R-032 und R-036 erfüllt, und nur die dafür
vorgesehenen Regeln greifen: R-053 bei F8-b/c, R-054 bei F8-d, keine bei F8-e.

**Nebenwirkung, die zu dokumentieren ist:** F8-d verändert die Rangfolge innerhalb der
Anfrage und löst dadurch R-044 aus. Entweder der Injektor passt `rang` mit an (sauber,
empfohlen) oder das wird als bekannter Nebentreffer in der Auswertung ausgewiesen.

Variante F8-e zeigt die strukturelle Grenze relationaler Plausibilitätsprüfungen und
gehört ausdrücklich in die Diskussion der Arbeit.

### HO1 / HO2 — Held-out

| Variante | Verfälschung |
|---|---|
| HO1-a | Personensatz duplizieren, Nachname zu `Mueller` statt `Müller`, Straße `Hauptstr.` statt `Hauptstraße` |
| HO1-b | Personensatz duplizieren, Vorname mit Tippfehler (Zeichendreher) |
| HO2-a | PLZ durch eine andere **existierende** PLZ ersetzen, `ort` konsistent mitziehen |
| HO2-b | **Gesamtes Beitragstupel** kohärent um 15 % senken — bleibt im plausiblen Korridor und erfüllt weiterhin R-031, R-032 und R-036 |

Auch bei HO2-b gilt die kohärente Skalierung: Eine Senkung nur des Zahlbeitrags würde
R-036 immer verletzen (weil der Ratenzuschlag höchstens 8 Prozent beträgt) und wäre damit
zu 100 Prozent erkennbar — als Held-out-Klasse unbrauchbar. Wie bei F8-d ist die
Rangfolge mitzuziehen oder der R-044-Nebentreffer auszuweisen.

---

## 3. Fehlerraten (Faktor UV2)

### Die Bezugsgröße ist klassenspezifisch — das ist keine Feinheit

Eine Fehlerrate von 20 Prozent „aller befüllten Zellen" ist für die meisten Klassen
**rechnerisch unerreichbar**, weil jede Klasse nur eine begrenzte Menge an Zielfeldern hat.
Beispiel bei 10.000 Anfragen: F3 adressiert nur 57.376 Zellen (Typklassen, Zahlweise,
ZÜRS-Zone, SF-Klassen, Bauartklasse, Regionalklassen) — die maximal erreichbare Rate
bezogen auf alle rund 1,77 Millionen Zellen liegt damit bei etwa 3 Prozent. Für F7-c und
F7-d sind es sogar nur 231 Tarifzeilen insgesamt.

> **Gemessene Universumsgrößen** bei 10.000 Anfragen, 62.826 Angeboten und 231 Tarifen
> (Lauf `s01_A_*_r0200_w01` auf `baseline01`):
>
> | Klasse | Universum | Einheit |
> |---|---|---|
> | F1 | 1.137.175 | Zellen |
> | F2 | 111.731 | Zellen |
> | F3 | 57.376 | Zellen |
> | F4 | 84.055 | Zellen |
> | F5 | 232.660 | Zellen |
> | F6 | 73.398 | Sätze |
> | F7 | 120.895 | Zellen |
> | F8 | 268.034 | Zellen |
> | HO1 | 12.400 | Sätze |
> | HO2 | 268.564 | Zellen |
>
> Bei zwei Prozent Fehlerrate liegen die absoluten Fehlerzahlen damit zwischen 248 (HO1)
> und 22.744 (F1) — um den Faktor 90 auseinander. Genau deshalb muss die Bezugsgröße in
> der Arbeit stehen.

Würde man die Rate auf alle befüllten Zellen beziehen, schlüge der Injektor bei den
oberen Ratenstufen für die Hälfte der Klassen fehl — und zwar erst nach Stunden Laufzeit.

**Verbindliche Definition:**

> Die Fehlerrate ist der Anteil verfälschter Zellen am **klassenspezifischen
> adressierbaren Zelluniversum** — also an der Menge aller Zellen, die von mindestens
> einer Variante dieser Fehlerklasse überhaupt getroffen werden können.

Der Injektor berechnet dieses Universum je Klasse vor der Ziehung und protokolliert seine
Größe im `manifest.json`. Wenn die angeforderte Rate mehr Zellen verlangt, als das
Universum hergibt, bricht er mit einer klaren Fehlermeldung ab — **er füllt nicht
stillschweigend weniger auf**.

Diese Definition muss in der Arbeit stehen, weil sie die Interpretation **jeder**
Ergebnistabelle ändert: „2 Prozent Fehlerrate" bedeutet je Klasse eine andere absolute
Fehlerzahl.

### Stufen

**0,5 % / 1 % / 2 % / 5 % / 10 % / 20 %**

Zur Einordnung in der Arbeit: REIN arbeitet mit 1 bis 58 Prozent, Abedjan et al. berichten
reale Raten von 0,1 bis 34 Prozent auf echten Datensätzen.

### Modus „praxisnah" als eigener Teilversuch

Im Hauptexperiment ist die Fehlerklasse ein Faktor — **pro Lauf wird genau eine Klasse
injiziert**. Ein Mischungsverhältnis ist dort per Konstruktion nicht anwendbar.

Der praxisnahe Mischmodus wird deshalb als **eigener Teilversuch** gefahren, in dem alle
Klassen gemeinsam injiziert werden, mit Gewichten aus der Branchenempirie (Dubletten und
Unvollständigkeit dominieren): F1 30 %, F6 30 %, F5 15 %, F3 10 %, F2 5 %, F8 5 %,
F7 3 %, F4 2 %.

Dieser Teilversuch ist inhaltlich der interessanteste der ganzen Arbeit, weil er die Frage
beantwortet: Wie schlägt sich das Verfahren bei einem realistischen Fehlermix statt bei
isolierten Klassen? 30 Seeds, eine Fehlerrate (2 Prozent), alle Verfahren.

## 4. Ground Truth — zwei Ebenen

### 4.1 Zellbasiertes Log (`error_log.parquet`)

Eine Zeile je verfälschter Zelle. Deckt F1 bis F5, F7 (Varianten a, b, d), F8 und HO2 ab.

| Spalte | Typ | Inhalt |
|---|---|---|
| `run_id` | str | Lauf-ID |
| `master_seed` | int | |
| `seed_base` | int | Seed des Basisdatensatzes |
| `seed_inject` | int | Seed der Injektion |
| `entitaet` | str | Tabellenname |
| `row_id` | int | stabile Zeilen-ID, **nie Ziel der Injektion** |
| `spalte` | str | Feldname |
| `fehlerklasse` | str | F1 … F8, HO1, HO2 |
| `injektor_variante_id` | str | z. B. `F3-d` |
| `wert_clean` | str | serialisierter Ausgangswert |
| `wert_dirty` | str | serialisierter verfälschter Wert |

### 4.2 Satzbasiertes Log (`error_log_records.parquet`)

Eine Zeile je satzbezogenem Fehler. Nötig für F6 (Duplikate), F7-c
(Gültigkeitsverletzung auf Tarifebene), HO1 und alle Fälle, in denen Zeilen hinzukommen
oder entfernt werden.

| Spalte | Typ | Inhalt |
|---|---|---|
| `run_id`, `master_seed`, `seed_base`, `seed_inject` | | wie oben |
| `entitaet` | str | |
| `fehlerklasse` | str | |
| `injektor_variante_id` | str | |
| `betroffene_row_ids` | list[int] | alle beteiligten Zeilen |
| `referenz_row_id` | int | die Originalzeile, aus der dupliziert wurde |

**Ohne diese zweite Ebene bricht die Auswertung genau bei der Fehlerklasse, die laut
Branchenempirie die häufigste ist.** Eine hinzugefügte Duplikatzeile hat keinen sauberen
Vorgängerwert, und `df_dirty` hat dann mehr Zeilen als `df_clean` — ein zellweises Diff
ist dort undefiniert.

Diese Klassen werden auf **Satz- bzw. Satzpaarebene** ausgewertet und in der
Ergebnisdarstellung getrennt ausgewiesen.

---

## 4a. Welche Regeln keine Variante haben

Fünfzehn Regeln aus `spec/02_regelkatalog.md` haben bewusst keine Injektionsvariante:
R-011, R-012, R-018, R-019, R-020, R-024, R-027, R-028, R-030, R-034, R-037, R-040,
R-041, R-050, R-057.

Sie können in der Auswertung nur Precision kosten, nie Recall bringen. Der Anteil
unbenutzter Regeln ist die Kennzahl „Überdeckung des Katalogs" — ein Ergebnis, kein
Versäumnis: Ein literaturbasiert hergeleiteter Katalog deckt notwendigerweise mehr ab,
als ein konkretes Fehlermodell auslöst. Diese Deutung gehört aktiv in die Arbeit.

---

## 5. Die sechs Protokollregeln

Verbindlich. Jede einzelne ist als Test in `tests/test_ground_truth.py` umzusetzen.

1. **Stabile, unantastbare Zeilen-ID.** `row_id` ist niemals Ziel der Injektion.
   Andernfalls geht die Zuordnung zwischen Ground Truth und Detektion verloren.

2. **Keine Doppelinjektion.** Eine Zelle wird höchstens einmal verfälscht. Der Injektor
   führt ein Set bereits getroffener `(entitaet, row_id, spalte)`-Tripel und zieht neu,
   wenn eine Kollision auftritt.

3. **Effektivitätsprüfung.** Für jede Log-Zeile gilt `wert_clean != wert_dirty`. Ein
   Injektor, der zufällig denselben Wert erzeugt, produziert eine Phantom-Ground-Truth
   und damit ein garantiertes False Negative. Das klingt trivial und ist trotzdem der
   häufigste Bug in solchen Aufbauten.

4. **Unabhängiger Diff-Gegencheck.** Nach der Injektion wird ein zellweises Diff zwischen
   `df_clean` und `df_dirty` über `row_id` berechnet und gegen `error_log` abgeglichen.
   Die Mengen müssen identisch sein. **Dieser Check ist unabhängig vom Injektorcode zu
   implementieren** — er deckt Protokollierungslücken auf, die der Injektor selbst nicht
   sehen kann. Zeilen, die nur in `df_dirty` existieren, müssen im satzbasierten Log
   auftauchen. Das Ergebnis gehört in den Anhang der Arbeit.

5. **Clean-Baseline-Lauf.** Der vollständige Regelkatalog läuft auf `df_clean`.
   Erwartung: null Meldungen. Jede Meldung ist entweder ein Generatorfehler (der Generator
   erzeugt selbst ungültige Daten) oder eine zu streng formulierte Regel. Die auf sauberen
   Daten gemessene False-Positive-Rate **muss in der Arbeit stehen** — sie ist der Beweis
   dafür, dass die Grundannahme „alles nicht Injizierte ist sauber" überhaupt trägt.

6. **Persistenz und Nachvollziehbarkeit.** Je Lauf werden abgelegt: `config.yaml` mit
   allen Faktorstufen und Seeds, `error_log.parquet`, `error_log_records.parquet`,
   `detections.parquet`, `metrics.json` sowie SHA-256-Hashes von `df_clean` und
   `df_dirty`. Damit ist jeder Einzelwert der Ergebnistabelle rückverfolgbar.

---

## 5a. Präzisierungen aus der Implementierung (Phase 4)

Alle folgenden Punkte betreffen den **Injektor**, nicht den Regelkatalog. Sie ändern kein
Prädikat, keinen Wertebereich und keinen Schwellenwert und sind deshalb **kein Fall von
Iteration 2**. Festgehalten werden sie, weil jeder von ihnen die Interpretation des Ground
Truth berührt.

### 5a.1 `seed_base` und `seed_inject` sind Zeichenketten

Abschnitt 4.1 führt beide als `int`. `seed_als_int` liefert einen **128-Bit-Wert**; er passt
in keine `int64`-Parquetspalte. Ihn abzuschneiden wäre genau die Art stiller Ungenauigkeit,
die Architekturregel A2 ausschließt. Beide Spalten werden deshalb als Dezimalzeichenkette
geführt.

### 5a.2 Zusätzliche Spalte `mitgezogen` im zellbasierten Log

Die kohärente Skalierung verlangt, die Rangfolge mitzuziehen (Abschnitt 2). Die dabei
veränderte Zelle `angebot.rang` ist nach der Skalierung **richtig**, nicht falsch: Sie trägt
den korrekten Rang zum verfälschten Beitrag.

- Stünde sie ununterscheidbar als injizierter Fehler im Log, wäre sie ein garantiertes False
  Negative, und der gemessene Recall fiele, ohne dass ein Detektor etwas übersehen hätte.
  Das ist die Phantom-Ground-Truth aus Protokollregel 3 in anderer Gestalt.
- Stünde sie **gar nicht** im Log, fände der Diff-Gegencheck eine Abweichung ohne
  Protokolleintrag.

Beides löst die Spalte `mitgezogen` (`bool`): Sie steht im Log, geht aber weder in das
adressierbare Zelluniversum noch in die Fehlerrate ein. Die Auswertung in Phase 5 wertet
ausschließlich die Trägerzellen (`mitgezogen = False`) als injizierte Fehler.

Gemessen bei zwei Prozent Fehlerrate und 10.000 Anfragen: F8 erzeugt zu 5.336 Trägerzellen
3.651 mitgezogene Rangzellen, HO2 zu 5.368 Trägerzellen 2.228. Alle übrigen Klassen erzeugen
keine. Das `manifest.json` weist beide Zahlen getrennt aus (`zellen_fehlerhaft` und
`zellen_geaendert_gesamt`): Der Datensatz ist bei diesen Klassen an deutlich mehr Stellen
verändert, als die Fehlerrate nominell angibt.

### 5a.3 F7-c steht in beiden Logs

Abschnitt 4.2 nennt F7-c als Fall des satzbasierten Logs, weil die Verletzung den
Gültigkeitszeitraum einer Tarifzeile als Ganzes betrifft. Die Variante verändert aber eine
konkrete Zelle (`tarif.gueltig_bis`), und die **muss** im zellbasierten Log stehen, sonst
fände der Diff-Gegencheck eine Abweichung ohne Protokolleintrag. Sie erscheint deshalb in
beiden Logs; im satzbasierten ohne `referenz_row_id`, weil nichts dupliziert wurde. Die
Spalte ist entsprechend nullable.

### 5a.4 Bezugseinheit der Fehlerrate bei F6 und HO1

Beide Klassen fügen Zeilen hinzu und haben keine Zielzelle. Ihr adressierbares Universum ist
die Menge der **duplizierbaren Zeilen**, und die Fehlerrate bezieht sich darauf. Das
`manifest.json` weist die Einheit je Klasse aus (`zelle` beziehungsweise `satz`), damit die
Zahlen in der Auswertung nicht stillschweigend verwechselt werden.

### 5a.5 F1-a und F1-b auf der Speicherebene

F1-a lässt das Feld **fehlen** (`pd.NA` in der Rohschicht), F1-b liefert es **leer**
(Leerstring). Auf der Speicherebene ist das ein Unterschied, wie ihn jede Schnittstelle
kennt, die zwischen `null` und `""` trennt. Nach dem Parsen ist er verschwunden — und im Log
stehen beide als Leerstring, weil das Diff des Gegenchecks sie ebenso zusammenführt.

Folge für die Auswertung: Die beiden Varianten sind für den Regelkatalog **nicht
unterscheidbar**. Ihr Recall wird gleich ausfallen. Das ist der Informationsverlust der
Serialisierung aus Abschnitt 2 (Variante F1-b), hier zum zweiten Mal sichtbar.

### 5a.6 Zielfelder von F1 und F4-g

- **F1** adressiert alle Felder außer `row_id` sowie den Primär- und Fremdschlüsseln. Ein
  verlorener Schlüssel ist eine **referentielle** Störung und damit eine andere Fehlerart
  als die hier modellierte Unvollständigkeit.
- **F4-g** („Beitrag oder Versicherungssumme negativ") trifft `nettobeitrag_jahr_eur`,
  `versicherungssumme_eur` und die drei Deckungssummen. Als Beitrag ist der **Nettobeitrag**
  gewählt: Er ist die Ausgangsgröße der Beitragsrechnung und damit das Feld, das eine Storno-
  oder Gutschriftverarbeitung negativ führt.

**Bekannte Nebentreffer, in der Auswertung auszuweisen:** F4-g verletzt neben R-021 auch die
Beitragsarithmetik (R-031) beziehungsweise die PflVG-Mindestdeckung (R-024). Das ist keine
Schwäche der Variante, sondern eine Eigenschaft eines Vorzeichenfehlers: Er kann in einem
arithmetisch verknüpften Satz gar nicht isoliert auftreten. Die `verstoss_id` der Regel-Engine
und die Spalte `injektor_variante_id` erlauben die getrennte Auswertung.

### 5a.7 Zuteilung auf die Varianten — proportional zum eigenen Universum

Das Kontingent einer Klasse wird **proportional zum adressierbaren Universum jeder
Variante** zugeteilt:

> n_i = Rate · |Klassenuniversum| · universum_i / Σ_j universum_j

**Warum nicht gleichmäßig.** Eine gleichmäßige Zuteilung sieht fairer aus, erzeugt aber
einen Confounder im Kern des Versuchsplans. Varianten mit kleinem Universum — F4-f, F7-c und
F7-d wirken auf der Entität `tarif` mit nur 231 Zeilen — stoßen mit steigender Fehlerrate an
ihre Decke. Ihr nicht ausgeschöpfter Rest ginge an die reichlich vorhandenen Varianten, und
**die Zusammensetzung der Klasse verschöbe sich mit der Fehlerrate**. Die Fehlerrate ist aber
Faktor UV2: Ein gemessener Zusammenhang „höhere Rate → anderer Recall" wäre dann teils
Ratenwirkung, teils Verschiebung der Variantenmischung, und der Trendtest über die
Ratenstufen könnte beides nicht trennen.

Bei proportionaler Zuteilung ist der Anteil jeder Variante **über alle Ratenstufen
konstant**. Gerundet wird nach Hare-Niemeyer, damit die Quoten exakt auf das
Klassenkontingent summieren.

**Es läuft nichts über.** Die Summe der Variantenuniversen ist wegen Überschneidungen — F4-c
und F4-d treffen beide `wohnflaeche_qm` — nie kleiner als das Klassenuniversum. Damit gilt
für jede Rate bis 1: n_i ≤ universum_i. Es wird deshalb **nicht umverteilt**; erreicht eine
Variante ihr Kontingent nicht, bricht der Injektor ab.

Drei Nebenwirkungen, alle im `manifest.json` sichtbar:

1. **Seltene Varianten fallen bei kleiner Rate aus.** Liegt der Anteil unter einer halben
   Einheit, ist das Kontingent null. Bei der obersten Ratenstufe passiert das nicht mehr.
2. **Gruppengranularität.** Eine kohärente Skalierung verändert vier Beitragsfelder auf
   einmal. Die erreichte Zahl weicht deshalb um weniger als eine Gruppengröße von der
   zugeteilten ab — reihenfolgeunabhängig und im Manifest je Variante ausgewiesen.
3. **Knappe Varianten bekommen im faktoriellen Plan kleine Fallzahlen.** F7-c erreicht bei
   zwei Prozent eine einstellige Zahl statt der 231, die ihr Universum hergäbe.

### 5a.8 Teilversuch „Variantencharakterisierung"

Für die klassenweise Auswertung ist eine kleine Fallzahl bei knappen Varianten richtig — sie
ist genau ihr Anteil an der Klasse. Für den Recall **je `injektor_variante_id`** ist sie zu
wenig: Bei n = 5 sagt er nichts, und gerade dieser Recall ist der empirische Beleg gegen den
Zirkularitätsvorwurf.

Dafür gibt es einen zweiten Laufmodus:

```
python scripts/inject.py --serie v01 --design A --modus variante --variante F7-c --wdh 0
```

Er injiziert **nur diese eine Variante**, und zwar bis an ihr Universum heran; `--max-fehler`
begrenzt die Zahl nach oben. Bezugsgröße der Fehlerrate ist dann das Universum dieser
Variante.

Diese Läufe gehören **nicht** in den faktoriellen Versuchsplan, sondern in einen eigenen
Teilversuch. Damit hat jede der beiden Fragen ihren eigenen sauberen Lauf: die Klassenwirkung
über Ratenstufen den faktoriellen Plan mit konstanter Mischung, die Variantenwirkung den
erschöpfenden Einzellauf mit belastbarem n und brauchbarem Konfidenzintervall.

### 5a.9 Wie die Auswertung die beiden Logs liest (Phase 5)

Auch dieser Abschnitt ändert **nichts** am Injektor. Er hält fest, wie die Auswertung aus den
beiden Logs ihre Wahrheitsmengen bildet — Festlegungen, die die Ergebnistabellen bestimmen
und deshalb nicht im Quelltext versteckt bleiben dürfen.

**Zellwahrheit.** Ausschließlich aus `error_log.parquet`. Ob die mit `mitgezogen` markierten
Zellen dazugehören, entscheidet der Parameter `mitgezogen_als_fehler`; berechnet werden je
Lauf **beide** Varianten (Abschnitt 5a.2).

**Satzwahrheit.** Die Vereinigung aus zwei Quellen:

1. jede Zeile, die mindestens eine Zelle im `error_log` hat, und
2. **alle** `row_id` aus `betroffene_row_ids` des `error_log_records`.

Punkt 2 heißt bei den Duplikatklassen F6 und HO1: **Beide Partner des Paares zählen als
fehlerhaft**, die hinzugefügte Zeile ebenso wie die Originalzeile. Das ist keine Großzügigkeit,
sondern die einzig definierbare Festlegung. Ein Duplikat ist eine Eigenschaft des *Paares*;
keine Regel kann sagen, welche der beiden Zeilen die hinzugefügte ist, und die neue `row_id`
vergibt der Injektor rein technisch aus dem noch nicht benutzten Zahlenraum. Würde nur die
neue Zeile als fehlerhaft geführt, bekäme jede korrekt arbeitende Duplikatregel für die
Originalzeile einen Fehlalarm angerechnet.

**Zelluniversum.** `Zeilen × Spalten` über alle sieben Entitäten des **verfälschten**
Datensatzes — dieselbe Definition wie im Clean-Baseline-Lauf (`scripts/validate.py`), damit
die dort gemessene False-Positive-Rate und die hier gemessene nebeneinander stehen dürfen.
`row_id` wird mitgezählt. Sie ist nach Architekturregel A3 niemals Ziel einer Injektion und
gehört damit strukturell zu den echten Negativen; eine Markierung auf ihr ist ein garantierter
Fehlalarm und wird getrennt ausgewiesen.

**Satzuniversum.** Die Zeilenzahl des verfälschten Datensatzes über alle Entitäten. Bei F6
und HO1 ist sie größer als die des sauberen — genau deshalb ist ein zellweises Diff dort
undefiniert (Abschnitt 4.2).

---

## 6. Was der Injektor nicht darf

- Er importiert **nichts** aus `src/rules/`. Nicht die Regeln, nicht ihre Konstanten,
  nicht ihre Hilfsfunktionen. Gemeinsame Wertebereiche kommen aus `src/common/`.
- Er verwendet keine Regel-IDs in seiner Logik. Die Spalte `injektor_variante_id`
  referenziert Injektionsvarianten, nicht Regeln. Die Zuordnung Variante → Regel entsteht
  erst in der **Auswertung**, nicht in der Erzeugung.
- Er passt seine Verfälschungen nicht daran an, ob eine Regel sie findet.
