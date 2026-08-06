# Phase 2 — Datengenerator

> Voraussetzung: Phase 1 abgeschlossen, Tests grün.
> Kopiere alles ab der Trennlinie in Claude Code.

---

Baue den Datengenerator. Lies vorher `CLAUDE.md` und `spec/01_datenmodell.md` erneut.

**Der Generator erzeugt einen vollständig regelkonformen, sauberen Datensatz.** Er kennt
den Regelkatalog nicht und darf nichts aus `src/rules/` importieren (Architekturregel A1)
— er erfüllt die fachlichen Abhängigkeiten, weil sie in der Domäne gelten, nicht weil eine
Regel sie prüft.

## Aufgabe 0 — Orientierung (immer zuerst)

Dieser Prompt setzt Phase 1 voraus, aber **nicht**, dass du sie selbst gebaut hast.
Verschaffe dir zuerst einen Überblick, bevor du etwas Neues schreibst:

1. `CLAUDE.md` lesen — Architekturregeln und Konventionen.
2. `spec/01_datenmodell.md` vollständig lesen, insbesondere die Abschnitte 2.8
   (SF-Ordinalskala), 3 (Feldspezifikation), 5 (Pflichtfeldprofil) und 6 (Datenschichten).
3. **`src/common/` vollständig sichten.** Dort liegen bereits `config.py`, `seeding.py`,
   `enums.py`, `wertebereiche.py`, `geld.py`, `iban.py`, `referenz.py`, `pfade.py` und
   `pflichtfelder.py`. Übernimm die dort etablierten Funktionsnamen und Signaturen, statt
   neue zu erfinden.
4. `docs/iteration_log.md`, `docs/verteilungsquellen.md` und `git log --oneline`
   überfliegen — dort stehen die Entscheidungen aus Phase 1.

Findest du einen Widerspruch zwischen diesem Prompt und dem vorhandenen Code, melde ihn,
statt eigenmächtig eine Seite zu ändern.

## Aufgabe 1 — Modul `src/generator/`

```
src/generator/
├── __init__.py
├── verteilungen.py     # gekapselte Ziehungsfunktionen, alle über den übergebenen Generator
├── anfrage.py
├── person.py
├── risiko_kfz.py
├── risiko_hausrat.py
├── tarif.py
├── angebot.py
├── zahlung.py
└── pipeline.py         # orchestriert und schreibt df_clean
```

Öffentliche Schnittstelle:

```python
def erzeuge_datensatz(config: Config, seed_basis: SeedSequence) -> dict[str, pd.DataFrame]
```

Rückgabe: ein Dict mit den Schlüsseln `anfrage`, `person`, `risiko_kfz`,
`risiko_hausrat`, `tarif`, `angebot`, `zahlung`.

## Aufgabe 2 — Die fachlichen Abhängigkeiten, die zwingend erfüllt sein müssen

Der Generator zieht **nicht** unabhängig pro Feld. Er baut die Abhängigkeitskette in
dieser Reihenfolge auf:

1. **Tarifstammdaten zuerst.** Je Anbieter und Sparte mindestens drei aufeinanderfolgende
   Generationen mit lückenlos aneinandergrenzenden Gültigkeitszeiträumen. Ohne mehrere
   Generationen ist die Fehlerklasse „veralteter Tarifstand" später nicht injizierbar.
2. **Person:** PLZ aus der Referenz ziehen, `ort` und `zulassungsbezirk` daraus ableiten.
   Geburtsdatum aus der Altersverteilung (Zensus), nicht uniform.
3. **Anfrage:** Sparte nach konfigurierter Verteilung, Kanal, Zahlweise aus dem
   zulässigen Katalog, Eingangszeitpunkt ≤ `stichtag`.
4. **Risiko:** je nach Sparte. Bei Kfz die (HSN, TSN) aus der Referenz ziehen und
   `leistung_kw`, `antriebsart`, `neupreis_eur`, alle Typklassen **aus dem Referenzeintrag
   übernehmen**, nicht neu würfeln. Regionalklassen über den `zulassungsbezirk`. Bei
   Hausrat die ZÜRS-Zone über die PLZ.
5. **Angebot:** Für jedes Angebot wird ein Tarif gewählt, **dessen Gültigkeitsfenster den
   Berechnungszeitpunkt enthält** (`gueltig_ab` ≤ `berechnungszeitpunkt` ≤ `gueltig_bis`).
   Ohne diese Bedingung ist R-055 auf sauberen Daten in rund zwei Dritteln der Fälle
   verletzt, weil je Anbieter mehrere Generationen existieren. Danach die
   Beitragsberechnung von unten nach oben (siehe Aufgabe 3).
6. **Zahlung:** IBAN mit korrekter Prüfziffer über `common/iban.py`.
7. **Pflichtfeldprofil anwenden.** Felder, die für die jeweilige `quell_schnittstelle` in
   `spec/01`, Abschnitt 5 als *optional* markiert sind, werden mit einer Wahrscheinlichkeit
   von 30 Prozent **leer** gelassen. Nutze dafür `common/pflichtfelder.py` aus Phase 1.
   **Das ist Teil des sauberen Datensatzes, kein Fehler.** Ohne diesen Schritt sind alle
   Felder überall gefüllt, der Datensatz ist unrealistisch homogen, und R-057 hätte später
   nichts zu prüfen. Kernpflichtfelder aus R-001 bleiben unabhängig von der Schnittstelle
   immer gefüllt.

Kritische Abhängigkeiten, die häufig übersehen werden:

- `sf_klasse_hp`: `schadenfreie_jahre(...)` ≤ Alter(VN) − 17. Ziehe zuerst das Alter, dann
  die Obergrenze der SF-Klasse. Die Abbildung ist in `spec/01`, Abschnitt 2.8 definiert und
  liegt bereits in `src/common/`.
- `sf_ordnung(sf_klasse_vk)` ≤ `sf_ordnung(sf_klasse_hp)` — die vollständige Ordnung
  einschließlich der Sonderklassen, ebenfalls aus `spec/01`, Abschnitt 2.8.
- `fuehrerschein_datum` ≥ Geburtsdatum + 17 Jahre.
- `erstzulassung` ≤ `zulassung_auf_vn` ≤ `stichtag`.
- `art_kennzeichen` = `54` nur bei elektrischer oder hybrider Antriebsart.
- `fahrzeugwert_aktuell` über eine Restwertkurve aus `neupreis_eur` und Fahrzeugalter,
  immer ≤ `neupreis_eur`.
- `unterversicherungsverzicht` = True nur, wenn `versicherungssumme_eur` ≥ 650 ×
  `wohnflaeche_qm`.
- Bei Hausrat: entweder `sb_hausrat_prozent` **oder** `sb_hausrat_eur` füllen, nie beide.
- `sepa_mandat_datum` ≤ `versicherungsbeginn`.
- Zweckbindung: Für eine Sparte irrelevante Felder bleiben **leer**, nicht mit
  Platzhaltern gefüllt (`fuehrerschein_datum` nur bei Kfz, ZÜRS nur bei Hausrat).

## Aufgabe 3 — Beitragsberechnung

Rechne strikt von unten nach oben, alles in `Decimal`:

```
nettobeitrag_jahr   = f(Typklasse, Regionalklasse, SF-Beitragssatz, Selbstbehalt,
                        Anbieter-Basisniveau, Fahrleistung)   # Kfz
                    = g(Versicherungssumme, ZÜRS-Zone, Bauartklasse,
                        Selbstbehalt, Anbieter-Basisniveau)    # Hausrat

versicherungsteuer_satz = Effektivsatz der Sparte    # 051/052/053 → 19.00, 130 → 16.15
versicherungsteuer      = runde(nettobeitrag_jahr * satz / 100)
bruttobeitrag_jahr      = nettobeitrag_jahr + versicherungsteuer
zahlbeitrag_rate        = runde(bruttobeitrag_jahr * (1 + rzz/100) / ratenanzahl)
```

Der Ratenzuschlag ist 0 bei `zahlweise` ∈ {1, 5, 6, 9} — also bei allen Zahlweisen mit
Ratenanzahl 1 — und sonst zwischen 0,5 und 8 Prozent. **Die Untergrenze von 0,5 Prozent
ist nicht kosmetisch:** Bei zwölf Raten und Ratenzuschlag 0 summiert sich der
Rundungsverlust auf bis zu 0,06 €, und R-036 würde auf sauberen Daten auslösen.

`ratenanzahl`: 1→1, 2→2, 4→4, 5→1, 6→1, 8→12, 9→1. Die Zahlweisen 5 und 9 werden nicht
gezogen (siehe `spec/01`, Abschnitt 3.1).

Der `rang` wird **nach** der Beitragsberechnung vergeben: aufsteigend nach
`zahlbeitrag_rate_eur`, lückenlos ab 1.

Bei `annahmeentscheidung` = ABLEHNUNG bleiben alle Beitragsfelder leer, und die Zeile
erhält keinen Rang (oder wird aus der Rangfolge ausgenommen — entscheide dich, dokumentiere
es in `README.md` und halte es konsistent).

**Wichtig für die spätere Auswertung:** Die Beitragsniveaus müssen sich zwischen den
Anbietern realistisch unterscheiden, aber die Spreizung max/min je Anfrage soll den Faktor
6 nicht überschreiten — sonst löst später eine Plausibilitätsregel schon auf sauberen
Daten aus.

## Aufgabe 4 — Determinismus

- Die einzige Zufallsquelle ist der aus `seed_basis` erzeugte Generator aus
  `common/seeding.py`. `seed_basis` ist eine `SeedSequence`, kein Integer — so hat es
  Phase 1 angelegt.
- Faker wird über `faker.seed_instance()` je Instanz geseedet, **nicht** über das
  klassenweite `Faker.seed()` — Letzteres setzt globalen Zustand und widerspricht A2.
- Keine Iteration über `set`. Sortiere Schlüssel explizit, wo die Reihenfolge das Ergebnis
  beeinflusst.
- Kein `date.today()`. Das Referenzdatum ist `config.stichtag`.

## Aufgabe 5 — Ausgabe

`scripts/generate.py --config config/default.yaml --run-id <id>` schreibt nach
`data/runs/<run_id>/clean/`:

- `typed/<entitaet>.parquet` — die typisierte Schicht
- `raw/<entitaet>.parquet` — die Rohschicht, **alle Spalten als String**
- `manifest.json` mit Zeilenzahlen, SHA-256 je Datei, verwendeten Seeds, Konfiguration

Die Serialisierungsregeln `df_typed` → `df_raw` stehen in `spec/01_datenmodell.md`,
Abschnitt 6. Implementiere zusätzlich den Rückweg als `src/common/serialisierung.py` mit
`serialisiere(df_typed) -> df_raw` und `parse(df_raw) -> tuple[df_typed, parse_fehler]`.

**Der Parser wirft keine Exception.** Ein nicht parsebarer Wert wird zu `pd.NA` und die
Stelle wird in `parse_fehler` protokolliert — nicht parsebare Werte sind genau der Fall,
den diese Arbeit untersucht. Ein `raise` an dieser Stelle würde später den gesamten
Experimentlauf abbrechen.

## Aufgabe 6 — Tests

- `tests/test_generator/test_abhaengigkeiten.py`: Prüft **jede** der oben genannten
  fachlichen Abhängigkeiten auf dem erzeugten Datensatz. Dieser Test ist bewusst
  redundant zur späteren Regel-Engine — er darf sie aber nicht importieren, sondern
  formuliert die Bedingungen eigenständig.
- `tests/test_generator/test_beitrag.py`: Beitragsarithmetik inklusive Rundung, für beide
  Sparten, an mindestens zehn Stichproben.
- `tests/test_generator/test_verteilungen.py`: ZÜRS-Anteile, Altersverteilung und
  Sparten-Anteile innerhalb der Toleranz.
- `tests/test_generator/test_serialisierung.py`: Roundtrip `parse(serialisiere(x)) == x`
  für alle Entitäten und alle Datentypen, inklusive leerer Werte.
- `tests/test_reproduzierbarkeit.py` erweitern: zwei Läufe mit gleichem `seed_basis`
  erzeugen identische Hashes über alle Entitäten.

## Aufgabe 7 — Dokumentation

`docs/verteilungsquellen.md` vervollständigen: für **jedes** Feld mit nicht-uniformer
Verteilung ein Eintrag mit Feldname, gewählter Verteilung, Parametern und Quelle. Wo keine
Quelle existiert (Regionalklassen-Zuordnung, SF-Beitragssätze, Typklassen-Zuordnung),
ausdrücklich „Modellannahme" eintragen. Diese Tabelle geht später in den Anhang der Arbeit.

## Abnahmekriterien

1. `pytest` grün, `ruff` und `mypy` sauber.
2. 10.000 Anfragen werden in unter fünf Minuten erzeugt, mit rund 60.000 Angebotszeilen
   (rechtsschiefe Verteilung der Angebotszahl, Modus 5).
3. `parse(serialisiere(df_typed))` ergibt wieder `df_typed` — Roundtrip-Test.
4. Zwei Läufe mit gleichem Seed → identische Hashes.
5. `tests/test_architecture.py` weiterhin grün — der Generator importiert nichts aus
   `src/rules/` oder `src/injector/`.
6. `docs/verteilungsquellen.md` ist vollständig.

## Nicht in dieser Phase

Keine Validierungsregeln, kein Injektor, keine Metriken. Halte am Ende an und berichte,
insbesondere: welche Verteilungsannahmen du treffen musstest und welche davon unbelegt
sind.
