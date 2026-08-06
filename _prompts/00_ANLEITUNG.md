# Anleitung — Prompt-Paket für Claude Code

Bachelorarbeit: *Regelbasierte Datenvalidierung in Versicherungsvergleichssystemen*

---

## Was in diesem Paket liegt

```
00_ANLEITUNG.md              ← diese Datei
CLAUDE.md                    → ins Wurzelverzeichnis des Projekts kopieren
spec/
  01_datenmodell.md          → nach <projekt>/spec/ kopieren
  02_regelkatalog.md         → nach <projekt>/spec/ kopieren
  03_fehlerklassen.md        → nach <projekt>/spec/ kopieren
prompts/
  phase0_git.md              ← zuerst: Git und GitHub
  phase1_setup.md
  phase2_generator.md
  phase3_regelengine.md      ← danach kommt der FREEZE
  phase4_injektor.md
  phase5_evaluator_baselines.md
  phase6_experiment.md
```

Die drei `spec/`-Dateien sind **keine Prompts**. Sie sind die fachliche Spezifikation und
werden ins Projekt gelegt, damit Claude Code sie in jeder Phase lesen kann. Sie sind
zugleich der Teil, den du inhaltlich verantwortest — der Regelkatalog ist das
Design-Artefakt deiner Arbeit.

---

## Setup

```bash
mkdir dq-validierung && cd dq-validierung
git init
mkdir spec

# Aus diesem Paket kopieren:
cp <paket>/CLAUDE.md .
cp <paket>/spec/*.md spec/

git add -A && git commit -m "Spezifikation und Projektgedaechtnis"
claude
```

---

## Ablauf

| Schritt | Prompt | Ergebnis |
|---|---|---|
| 0 | `phase0_git.md` | Git-Repository, `.gitignore`, `.gitattributes`, privates GitHub-Repo |
| 1 | `phase1_setup.md` | Projektgerüst, `src/common/`, Referenzdaten |
| 2 | `phase2_generator.md` | `df_clean` — der saubere synthetische Datensatz |
| 3 | `phase3_regelengine.md` | 58 Regeln implementiert, Clean-Baseline-Lauf ohne Meldungen |
| **→** | **FREEZE** | `git tag freeze-regelkatalog` — **du selbst, nicht Claude Code** |
| 4 | `phase4_injektor.md` | `df_dirty` + Ground Truth + Gegencheck |
| 5 | `phase5_evaluator_baselines.md` | Metriken, B0, B2, B3 |
| 6 | `phase6_experiment.md` | 1.680 Läufe plus fünf Teilversuche, Statistik, 10 Abbildungen, 8 Tabellen |

Nach jeder Phase: Tests laufen lassen, Ergebnis prüfen, committen. Erst dann die nächste
Phase starten. Claude Code ist angewiesen, am Ende jeder Phase anzuhalten und zu berichten.

---

## Warum die Reihenfolge nicht verhandelbar ist

Der Regelkatalog wird **vor** dem Fehlerinjektor gebaut und dann eingefroren. Das ist der
einzige Punkt dieses Ablaufs, an dem du nicht abkürzen solltest.

Der Grund ist der Zirkularitätsvorwurf: Wenn Regeln und injizierte Fehler beide aus
derselben Quelle stammen und gleichzeitig entstehen, misst dein Experiment im Extremfall
nur, ob dieselbe Bedingung zweimal programmiert wurde. Ein F1-Wert von 0,98 wäre dann
bedeutungslos.

Drei Mechanismen im Paket wirken dagegen:

1. **Die Import-Trennung.** `src/injector/` darf nichts aus `src/rules/` importieren. Ein
   Test prüft das am Importgraphen — die Trennung ist damit belegbar, nicht bloß behauptet.
2. **Der Freeze mit Git-Tag.** Der Commit-Hash ist der Beleg dafür, dass die Regeln nicht
   nachträglich auf die Fehler zugeschnitten wurden. **Notiere ihn — er gehört in den
   Anhang der Arbeit.**
3. **Die Injektionsvarianten.** Jede Fehlerklasse hat mehrere Varianten, von denen nur ein
   Teil die Regelbedingung exakt spiegelt. Der Recall je Variante wird berichtet. Fällt er
   bei den nicht-spiegelnden Varianten ab, ist der Vorwurf empirisch entkräftet statt nur
   rhetorisch.

Dazu kommen die beiden **Held-out-Klassen** (HO1 semantische Duplikate, HO2 semantisch
falsche, formal gültige Werte), für die bewusst keine Regel existiert. Deren Recall nahe
null ist kein Misserfolg, sondern die ehrlichste Antwort auf das „inwieweit" deiner
Forschungsfrage.

**Eine Einschränkung, die du selbst benennen solltest:** Die Import-Trennung belegt „kein
Codeaustausch", nicht „keine Kenntnis". Die Spalte „Spiegelt Regel exakt?" in
`spec/03_fehlerklassen.md` ordnet jede Variante einer Regel zu — wer den Injektor entlang
dieser Tabelle baut, baut ihn intellektuell aus dem Regelkatalog heraus. Das ist kein
Fehler, aber es begrenzt die Reichweite des Arguments. Diese Grenze in den Limitationen
selbst zu benennen ist stärker, als sie zu bestreiten.

---

## Was du selbst verantworten musst

Claude Code implementiert. Die fachliche Herleitung ist deine Leistung und muss es auch
bleiben:

- **Den Regelkatalog** (`spec/02_regelkatalog.md`) vor Phase 3 durchgehen und die Spalten
  „Literatur" und „Fachliche Grundlage" gegen die Originalquellen prüfen. Streiche, was du
  nicht belegen kannst, ergänze, was du belegen kannst.
- **Die Fehlertaxonomie** aus der Literatur herleiten. Der Katalog ist bereits entlang der
  drei Achsen strukturiert; die Herleitung selbst gehört ins Theoriekapitel und stammt von
  dir.
- **Die Verteilungsannahmen** in `docs/verteilungsquellen.md` prüfen und belegen. Wo keine
  Quelle existiert, muss „Modellannahme" stehen.
- **Die Schwellenwerte** der C2-Regeln (R-047, R-048, R-053, R-054) begründen. Sie stehen
  in der Konfiguration, nicht im Code, damit du sie diskutieren und variieren kannst.

---

## Wo du kürzen kannst, wenn die Zeit knapp wird

Der Umfang ist bewusst großzügig geschnitten. Falls es eng wird, in dieser Reihenfolge:

1. **`n_anfragen` von 10.000 auf 3.000** im Hauptversuch. Für die Metrikstabilität reichen
   rund 600.000 Zellen locker; 10.000 bleiben nur für den Skalierungs-Teilversuch.
2. **Teilversuch T5 (Datenvarianz) auf 5 Seeds** reduzieren.
3. **Fehlerrate 0,10 streichen** — drei Stufen genügen für den Prävalenzeffekt.
4. **Seeds von 20 auf 15.**
5. **Regelkatalog von 58 auf rund 40 kürzen.** Streichbar sind die Regeln ohne
   Injektionsvariante und ohne eigene methodische Rolle: R-011, R-012, R-018, R-019, R-020,
   R-027, R-028, R-030, R-040, R-041, R-057. Behalten würde ich in jedem Fall alles, was
   eine Geschichte trägt: R-010 (Katalog- statt Bereichsprüfung), R-025 (Sentinels und ihre
   Grenzen), R-033 (Conditional Functional Dependency), R-034 (nicht auslösbar, ehrlich
   gekennzeichnet), R-045 und R-046 (exakte Duplikate als Kontrast zu HO1), R-052 bis R-054
   (Multi-Source), R-055 (Aktualität). **40 Regeln mit sauberer Herleitung sind
   wissenschaftlich mehr wert als 58 mit halber.**
6. **Regeltests parametrisieren** statt einzeln schreiben: eine Tabelle mit je einem
   positiven und einem negativen Fall pro Regel, ausgeführt über `pytest.mark.parametrize`.
   Gleiche Abdeckung, ein Tag statt zwei Wochen.

Diesen Schnitt machst du am besten **vor Phase 1**, nicht während Phase 6.

---

## Nach Phase 6: was noch fehlt

Der Code ist dann fertig. Für die Arbeit fehlen noch drei Dinge, die kein Programm liefert:

1. **Die dokumentierte Literaturrecherche.** Durchsuchte Datenbanken, Suchstrings,
   Zeitraum, Ein- und Ausschlusskriterien, Trefferzahlen je Stufe. Ohne sie ist weder die
   „literaturbasierte Herleitung" noch die behauptete Forschungslücke belegbar.
2. **Die Taxonomie-Evaluation.** Der billige Abdeckungstest: Ordne die 36 Data Smells von
   Foidl et al. (2022) den Achsen A, B und C zu. Der Anteil eindeutig zuordenbarer Smells
   ist eine berichtbare Kennzahl.
3. **Die kritische Würdigung.** Zitiere Liu et al. (2025, arXiv:2507.10934) und Abedjan et
   al. (2016) selbst in den Limitationen — beide belegen quantitativ, dass synthetisch
   injizierte Fehler von realen abweichen. Wer die Schwäche des eigenen Designs mit Beleg
   selbst vorträgt, nimmt sie dem Prüfer aus der Hand.

---

## Wenn Claude Code abweicht

Die Prompts enthalten je Phase einen Abschnitt „Nicht in dieser Phase". Wenn Claude Code
trotzdem vorgreift — etwa den Injektor schon in Phase 3 baut —, brich ab und verweise auf
`CLAUDE.md`, Abschnitt 2 (die vier unverhandelbaren Architekturregeln) und Abschnitt 7
(was nicht zu tun ist).

Ein häufiger Reflex ist, den Regelkatalog nach dem Freeze anzupassen, wenn eine Messung
schlecht ausfällt. Das ist der eine Fall, in dem du hart bleiben musst: Notwendige
Korrekturen werden als **Iteration 2** in `docs/iteration_log.md` dokumentiert und mit
eigener Ergebnistabelle berichtet. Ein unerwartetes Ergebnis ist ein Befund, kein Anlass,
das Artefakt zu ändern.


---

## Änderungsstand

Dieses Paket wurde nach der Erstfassung einer kritischen Gegenprüfung unterzogen und
überarbeitet. Die wichtigsten Korrekturen:

- `row_id` existiert jetzt in **jeder** Entität — ohne sie wäre der Ground Truth für fünf
  von sieben Tabellen nicht protokollierbar gewesen.
- Die **Fehlerrate bezieht sich auf das klassenspezifische Zelluniversum**, nicht auf alle
  befüllten Zellen. Andernfalls wären die oberen Ratenstufen für die Hälfte der
  Fehlerklassen rechnerisch unerreichbar gewesen.
- Es gibt eine **Rohdatenschicht** (`df_raw`, alle Spalten String) neben der typisierten
  Schicht. Ohne sie wären sieben Regeln per Konstruktion nicht verletzbar und ein Dutzend
  Injektionsvarianten nicht umsetzbar — und `pyarrow` hätte die gemischt typisierten
  Spalten gar nicht erst geschrieben.
- Die Beitragsskalierung bei F8 und HO2-b erfolgt **kohärent über das gesamte
  Beitragstupel**. Andernfalls wären genau die drei Varianten, die unentdeckt bleiben
  sollen, garantiert erkannt worden — und damit der wertvollste Befund der Arbeit hinfällig.
- Der Evaluator berichtet zusätzlich eine **Constraint-Ebene**, weil mehrspaltige Verstöße
  sonst per Konstruktion False Positives erzeugen und die Precision auf ein Drittel deckeln.
- Jede Hypothese hat jetzt ein **passendes Testverfahren** (Wilcoxon, Friedman,
  Page-Trendtest, ART-ANOVA) statt pauschal Wilcoxon für alles.
