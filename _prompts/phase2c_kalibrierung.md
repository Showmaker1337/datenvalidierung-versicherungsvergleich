# Phase 2c — Kalibrierung des Beitragsmodells

> Letzter Nachtrag vor Phase 3. Kopiere alles ab der Trennlinie in Claude Code.

---

Zwei Punkte aus deinem Bericht zu Phase 2b. Der erste ist eine fachliche Entscheidung, der
zweite eine Klarstellung.

## 1 — Der rechte Rand der Vollkasko-Verteilung wird kalibriert

Dein Befund ist richtig und die Zurückhaltung war angemessen: p99 bei 8.419 €, 2,4 Prozent
über 6.000 €, Maximum über 20.000 € — das ist für eine private Vollkasko nicht plausibel.
Ein Prüfer mit Versicherungshintergrund sieht das sofort.

**Ursache und Eingriff.** Du hast die Ursache korrekt benannt: Malus- und Schadenklassen
(245 % und 155 %) multipliziert mit hohem Typklassen- und Regionalklassenfaktor. In der
Realität kommt diese Kombination in der Vollkasko praktisch nicht vor — **Versicherer nehmen
Risiken in Malus- oder Schadenklasse in der Vollkasko überwiegend gar nicht an.** Genau das
wird jetzt abgebildet:

> In den Sparten **052 (Vollkasko)** und **053 (Teilkasko)** erhalten Risiken mit
> `sf_klasse_hp` ∈ {`M`, `S`} **kein Angebot**. In der Haftpflicht (051) bleiben sie
> erhalten — dort besteht Kontrahierungszwang und die Klassen sind fachlich relevant.

Setze das als Annahmebedingung um, nicht als nachträgliches Filtern: Es entstehen erst gar
keine Kasko-Angebote für diese Risiken. Achte darauf, dass die Mindestzahl bepreister
Angebote je Anfrage weiterhin eingehalten wird — betroffene Anfragen bekommen entsprechend
nur Haftpflichtangebote.

**Warum das kein Taschenspielertrick ist:** Der Eingriff hat eine fachliche Begründung, die
in `docs/verteilungsquellen.md` gehört. Er beseitigt nicht einen unbequemen Ausreißer,
sondern eine Konstellation, die im Modell entstehen kann und im Markt nicht existiert.

**Danach:** Korridor für R-053 empirisch neu bestimmen, wieder über mindestens fünf
unabhängige Seeds. Setze die Obergrenze auf den beobachteten Maximalwert plus rund
30 Prozent Sicherheitsmarge und runde auf einen glatten Wert. Erwartung: irgendwo zwischen
6.000 und 10.000 €. Berichte den neuen p99 je Sparte.

Halte in `docs/iteration_log.md` fest: alter und neuer Korridor, alter und neuer p99, und die
Begründung des Eingriffs. Das ist Iteration 1, noch vor dem Freeze.

**Was als Diskussionspunkt erhalten bleibt** — und wichtiger wird, nicht unwichtiger: Die
Erkennungsschwelle einer korridorbasierten Regel hängt an der Breite des legitimen
Wertebereichs. Bei einem Korridor bis 25.000 € griff R-053 erst ab 250 € Jahresbeitrag; bei
8.000 € greift sie ab 80 €. **Rechne beide Schwellen aus und schreibe sie ins
Iterationslog.** Das ist ein quantifizierter methodischer Befund über C2-Regeln, kein
Nebensatz — er gehört in die Diskussion der Arbeit.

## 2 — `_prompts/` gehört ins Repository

Hier liegt ein Missverständnis vor, das meine Formulierung verursacht hat. In `CLAUDE.md`
steht „`_prompts/` ist kein Projektinhalt". Das heißt: **Du arbeitest daraus nichts von dir
aus ab.** Es heißt nicht, dass der Ordner nicht versioniert wird — `phase0_git.md` führt ihn
ausdrücklich unter „Nicht ignoriert werden", weil er dokumentiert, wie das Projekt
entstanden ist.

**Zu tun:** `_prompts/` committen. Und präzisiere die Zeile in `CLAUDE.md` so, dass die
Unterscheidung klar ist: nicht abarbeiten, aber versionieren.

Für die Bachelorarbeit ist das relevant: Der Ordner belegt zusammen mit dem Commit-Verlauf,
in welcher Reihenfolge spezifiziert und implementiert wurde — und dass die Spezifikation vor
der Implementierung stand.

## Abnahme

1. Keine Kasko-Angebote mehr für `sf_klasse_hp` ∈ {`M`, `S`}; Haftpflicht unverändert.
2. Mindestzahl bepreister Angebote je Anfrage weiterhin eingehalten.
3. Neuer R-053-Korridor empirisch über mindestens fünf Seeds bestimmt, null Überschreitungen.
4. Neuer p99 je Sparte berichtet.
5. Beide Erkennungsschwellen (alt und neu) im Iterationslog.
6. Begründung des Eingriffs in `docs/verteilungsquellen.md`.
7. `_prompts/` committet, `CLAUDE.md` präzisiert.
8. `pytest`, `ruff`, `mypy` grün; Hashes aktualisiert; Commit und Push.

Halte danach an. Phase 3 kommt als eigener Prompt — und danach der Freeze.
