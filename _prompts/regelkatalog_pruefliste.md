# Prüfliste Regelkatalog — vor Phase 3 und dem Freeze

Kein Prompt für Claude Code. Ein Arbeitsdokument für dich.

---

## Warum jetzt

Der Regelkatalog ist das Design-Artefakt deiner Bachelorarbeit. Im Kolloquium wird niemand
fragen, ob der Code läuft — gefragt wird, **warum genau diese Regeln und woher sie kommen**.
Die Spalten „Literatur" und „Fachliche Grundlage" habe ich gesetzt; verantworten musst du sie.

Nach dem Git-Tag `freeze-regelkatalog` wird jede Änderung zur deklarierten Iteration mit
eigener Ergebnistabelle. Deshalb: jetzt.

**Zeitbedarf:** Stufe 1 etwa zwei bis drei Stunden. Stufe 2 einen halben Tag. Stufe 3 nur,
wenn Zeit bleibt.

---

## Wie ehrlich die Zuordnungen sind

Ich habe die Literaturkürzel nach bestem Wissen gesetzt, aber **nicht jede einzelne
Zuordnung im Original nachgeschlagen.** Die Verteilung über 58 Regeln:

| Kürzel | Quelle | Verweise | Wie sicher |
|---|---|---|---|
| RD | Rahm & Do (2000) | 40 | **Hoch.** Das Paper ist kurz, frei verfügbar und deckt genau diese Problemklassen ab |
| FAN | Fan et al. (2008), CFD | 17 | **Mittel.** Das Konzept passt eindeutig; ob jedes meiner Beispiele dort auch als CFD firmiert, habe ich nicht geprüft |
| FOI | Foidl et al. (2022), Data Smells | 12 | **Mittel.** Die 36 Smells sind benannt; welcher Smell zu welcher Regel gehört, solltest du selbst zuordnen |
| DAMA | DAMA UK (2013) | 10 | **Hoch.** Nur sechs Dimensionen, die Zuordnung ist eindeutig |
| KIM | Kim et al. (2003) | 7 | **Niedrig.** Ich verweise teils auf Nummern wie „2.1.1.1", die ich aus Sekundärquellen habe. **Das ist der schwächste Punkt im ganzen Katalog** |
| CHU | Chu et al. (2013), Denial Constraints | 7 | **Mittel.** Konzept passt, formale Prüfung steht aus |
| ABE | Abedjan et al. (2016) | 5 | **Hoch.** Vier klare Klassen, leicht nachprüfbar |
| ISO | ISO/IEC 25012 | 3 | **Mittel.** Die Norm ist kostenpflichtig — prüfe, ob deine Hochschule Zugang hat |
| OLI | Oliveira et al. (2005) | 2 | **Niedrig.** Zwei ähnliche Papiere derselben Gruppe aus 2005, widersprüchliche Angaben in der Sekundärliteratur |

---

## Stufe 1 — Pflicht (zwei bis drei Stunden)

### 1.1 Die sieben Zitationen, die schiefgehen können

Diese prüfst du zuerst, weil sie am ehesten falsch sind:

- [ ] **Alle KIM-Verweise mit Nummern** (R-010, R-014, R-021, R-025, R-041). Ich zitiere dort
      Hierarchiepunkte wie „2.1.1.1" aus Sekundärquellen. **Schlag im Original nach.** Stimmt
      die Nummer nicht, streiche sie und verweise nur auf die Oberklasse — oder entferne KIM
      bei dieser Regel ganz.
- [ ] **OLI bei R-049** („Multi-Relation"). Klär zuerst, welches der beiden 2005er-Papiere du
      zitierst, dann ob der Begriff dort so vorkommt.
- [ ] **ISO bei R-004, R-021, R-050.** Ohne Normzugang: streichen. Eine nicht eingesehene
      Norm zu zitieren ist riskanter als sie wegzulassen.
- [ ] **FOI „Integer as String" bei R-002** und **FOI „Dummy Value" bei R-025.** Prüfe, ob
      die Smells in Foidl et al. genau so heißen. Die Namen habe ich aus dem Gedächtnis.
- [ ] **DAMA UK, nicht DMBOK.** Vergewissere dich, dass du das White Paper von 2013 zitierst
      und nicht das DMBOK — die Dimensionslisten unterscheiden sich, und die Verwechslung ist
      ein leichtes Angriffsziel.
- [ ] **ABE bei R-047** („Outliers"). Abedjan et al. nennen vier Klassen; prüfe, dass deine
      Zuordnung zu ihrer Definition passt.
- [ ] **Schelter et al. bei R-048.** Ich verweise auf „Metrik-Constraints" in Deequ. Prüfen
      oder streichen.

### 1.2 Die Domänenquellen — das ist wichtiger als die Literatur

Hier bist du fachlich angreifbar, und hier lässt sich alles belegen:

- [ ] **R-010 Zahlungsweise.** GDV Anlage 14 aufrufen und die Werte 1, 2, 4, 5, 6, 8, 9
      bestätigen. Screenshot in den Anhang — das ist dein bestes Beispiel für den Unterschied
      zwischen Bereichs- und Katalogprüfung.
- [ ] **R-014 / R-015 Typ- und Regionalklassen.** Wertebereiche 10–25 / 10–33 / 10–34 und
      12 / 16 / 9 Stufen gegen eine GDV-Publikation belegen.
- [ ] **R-024 Deckungssummen.** PflVG, Anlage zu § 4 Abs. 2 im **Gesetzestext** nachschlagen,
      nicht über Vergleichsportale. Die kursierenden Zahlen sind teils veraltet.
- [ ] **R-032 / R-033 Versicherungsteuer.** § 6 Abs. 2 **in Verbindung mit** § 5 Abs. 1 Nr. 3
      VersStG. Der Unterschied zwischen Nominalsatz (19 %) und Effektivsatz (16,15 %) muss in
      der Arbeit erklärt sein — sonst wirkt die Zahl falsch.
- [ ] **R-016 ZÜRS.** Vier Gefährdungsklassen und die Verteilung 92,4 / 6,1 / 1,1 / 0,4 %
      gegen den GDV-Naturgefahrenreport.
- [ ] **R-004 IBAN.** ISO 13616 und ISO 7064 Mod 97-10. Der Algorithmus ist breit
      dokumentiert; eine zitierfähige Quelle genügt.
- [ ] **R-017 Bauartklasse.** GDV Anlage 12.
- [ ] **R-019 / R-020.** GDV Satzart 0210.050.

### 1.3 Die vier Schwellenwerte begründen

Sie stehen in `config.schwellen`, damit du sie diskutieren kannst. Für jeden brauchst du
**einen Satz Begründung** in der Arbeit:

- [ ] **R-047**, Spreizung max/min ≤ 6 je Anfrage. Woher die 6? Wenn es eine Setzung ist:
      als solche kennzeichnen und sagen, was ein anderer Wert ändern würde.
- [ ] **R-048**, ZÜRS-Toleranz 30 % relativ. Begründung: absolute Prozentpunkte wären bei
      Zone 4 (0,4 %) wirkungslos — ±5 Punkte erlaubten Faktor 13,5.
- [ ] **R-053**, Korridor [40, 13.000] für Kfz. Empirisch bestimmt über fünf Seeds, plus
      34 % Marge. **Mit der Erkennungsschwellen-Tabelle aus dem Iterationslog belegen** —
      das ist dein stärkster methodischer Befund zu C2-Regeln.
- [ ] **R-054**, Faktor 12 ± 5 %. Warum 5 und nicht 10?

---

## Stufe 2 — Sollte (halber Tag)

### 2.1 Die drei Achsen belegen

- [ ] Jede Regel hat eine A/B/C-Zuordnung. **Geh alle 58 durch und prüfe, ob du jede in einem
      Satz begründen könntest.** Wo du zögerst, ist die Zuordnung wahrscheinlich falsch.
- [ ] Besonders **Achse C**: Ist R-030 wirklich C2 und nicht C1? Ist R-050 wirklich C3?
      Diese Achse steuert deine Hypothesen — Fehler dort verzerren die Interpretation.
- [ ] Die Kennzahlentabelle am Ende des Katalogs (47 HART / 11 WARNUNG, 45 C1 / 11 C2 / 2 C3)
      selbst nachzählen. Sie geht in die Arbeit.

### 2.2 Taxonomie-Abdeckungstest

Der billige Test, der deine Taxonomie evaluierbar macht:

- [ ] Nimm die **36 Data Smells** aus Foidl et al. (2022) und ordne jeden einzelnen den
      Achsen A, B und C zu.
- [ ] Zähle, wie viele eindeutig zuordenbar sind. Das ist eine berichtbare Kennzahl für die
      kollektive Vollständigkeit deiner Taxonomie.
- [ ] Jeder nicht zuordenbare Smell ist eine echte Lücke — benenne sie, statt sie zu
      übergehen. Aufwand: zwei bis drei Stunden, Ertrag: ein eigener Evaluationsabschnitt
      für das Theoriekapitel.

### 2.3 Die Mapping-Tabelle für den Anhang

- [ ] Aus `results/regelkatalog.csv` (entsteht in Phase 3) und den Injektionsvarianten aus
      `spec/03` eine durchgehende Tabelle bauen:
      Literaturquelle → Taxonomieklasse → Regel-ID → Injektionsvariante → Auswertungsklasse.
- [ ] Diese eine Tabelle beantwortet die meisten Nachfragen zur Herleitung, bevor sie
      gestellt werden.

---

## Stufe 3 — Wenn Zeit bleibt

- [ ] **Nickerson, Varshney & Muntermann (2013)** als Methode der Taxonomiekonstruktion
      lesen und die eigene Konstruktion daran ausrichten. Das ist die naheliegendste
      Prüferfrage bei einer Arbeit, deren Kernartefakt eine Taxonomie ist.
- [ ] **Die Literaturrecherche dokumentieren** (Datenbanken, Suchstrings, Zeitraum, Ein- und
      Ausschlusskriterien, Trefferzahlen). Ohne sie ist „literaturbasiert hergeleitet" nicht
      belegbar. Referenzen: Webster & Watson (2002), vom Brocke et al. (2009).

---

## Wenn du kürzen musst: die Streichliste

Fünfzehn Regeln haben keine Injektionsvariante. Elf davon kannst du streichen, ohne dass die
Arbeit etwas verliert:

**Streichbar:** R-011 (Sparte im Katalog), R-012 (Währung), R-018 (Anfragestatus),
R-019 (Nutzungsart), R-020 (Art Kennzeichen), R-027 (Zulassungsdatum), R-028 (Führerschein),
R-030 (SF-VK ≤ SF-HP), R-040 (Unterversicherungsverzicht), R-041 (Selbstbehalt exklusiv),
R-057 (Pflichtfeldprofil).

Das sind reine Katalog- und Bereichsprüfungen ohne eigene methodische Rolle. 47 Regeln mit
sauberer Herleitung sind wissenschaftlich mehr wert als 58 mit halber.

**Auf keinen Fall streichen** — diese tragen jeweils eine Geschichte:

| Regel | Warum sie bleibt |
|---|---|
| R-010 | Katalog- statt Bereichsprüfung: Zahlweise 3 liegt im Zahlenbereich und existiert trotzdem nicht |
| R-025 | Sentinels und ihre Grenzen — inklusive der Ausnahmeliste für Felder, in denen 9999 legitim ist |
| R-033 | Das CFD-Beispiel: Der zulässige Steuersatz hängt von der Sparte ab |
| R-034 | Im aktuellen Modell nicht auslösbar, bewusst implementiert und so gekennzeichnet. Ehrlichkeit als Methode |
| R-045 / R-046 | Exakte Duplikate als Kontrast zu den semantischen in HO1 |
| R-052 – R-054 | Die Multi-Source-Gruppe: der Kern der Domäne |
| R-055 | Veralteter Tarifstand — die klassische Fehlerklasse von Vergleichsportalen |
| R-024, R-031, R-032 | Gesetzlich belegbar, damit unangreifbar |

**Wichtig:** Wenn du streichst, musst du es **vor** Phase 3 tun. Und die 15 Regeln ohne
Variante sind selbst ein Ergebnis — der Anteil unbenutzter Regeln ist die Kennzahl
„Überdeckung des Katalogs". Formuliere das aktiv, statt es zu verschweigen: Ein
literaturbasiert hergeleiteter Katalog deckt notwendigerweise mehr ab, als ein konkretes
Fehlermodell auslöst.

---

## Am Ende

- [ ] Alle nicht belegbaren Literaturverweise gestrichen oder ersetzt
- [ ] Alle Domänenquellen mit Fundstelle notiert (für Fußnoten und Anhang)
- [ ] Vier Schwellenwerte je mit einem Satz begründet
- [ ] Kennzahlentabelle nachgezählt und korrigiert
- [ ] Entscheidung über Streichungen getroffen
- [ ] `spec/02_regelkatalog.md` committet

Danach: `_prompts/phase3_regelengine.md` — und danach der Freeze.
