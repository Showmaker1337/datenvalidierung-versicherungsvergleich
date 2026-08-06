# Phase 2b — Nachtrag zu den Befunden aus Phase 2

> Kurzer Nachtrag vor Phase 3. Kopiere alles ab der Trennlinie in Claude Code.

---

Du hast in Phase 2 vier Stellen gemeldet, an denen die Spezifikation nicht trug. Drei davon
sind zu deinen Gunsten entschieden, eine deckt einen echten Fehler in der Spezifikation auf
und erfordert Nacharbeit. Lies `spec/01_datenmodell.md` (Abschnitt 6) und
`spec/02_regelkatalog.md` (R-041, R-053, R-057) neu ein.

## 1 — Leeres Datum: deine Entscheidung wird zur Regel

Der Widerspruch in `spec/01`, Abschnitt 6 ist aufgelöst — und zwar so, wie du es umgesetzt
hast: **Leer wird zum Leerstring, für alle Typen, auch für Datumsfelder.**

Die Begründung steht jetzt in der Spezifikation: Würde `00000000` der reguläre Leerwert,
wäre es ein legitimer Nullwert. R-025 könnte es dann nicht mehr als impliziten Fehlwert
melden, und R-009 müsste es als Nicht-Kalendertag ausnehmen. Beide Regeln verlören ihre
Schärfe. Die Zuordnung ist jetzt eindeutig:

| Wert in `df_raw` | Bedeutung | Reaktion |
|---|---|---|
| Leerstring | regulär leer | kein Befund |
| `00000000` | Sentinel | R-025 |
| `01011900` | Sentinel | R-025 |
| `31022026` | kein Kalendertag | R-009 |

**Zu tun:** Nichts am Code. Prüfe nur, dass `00000000` in der Sentinel-Liste in
`common/wertebereiche.py` steht — es ist jetzt ausdrücklich ein Fehlwert, kein Leerwert.

## 2 — Pflichtfeldprofil je Kanal: übernommen

Deine Analyse war richtig: `quell_schnittstelle` ist ein Feld von `angebot`, die
Profilfelder liegen aber überwiegend auf der Anfrageseite. Dein Abschnitt 5.1 in `spec/01`
bleibt bestehen, und **R-057 ist entsprechend zweigeteilt worden**: Anfrageseite gegen das
Kanalprofil, Angebotsseite gegen das Schnittstellenprofil. Das steht jetzt im Regelkatalog,
damit Phase 3 nicht wieder darüber stolpert.

## 3 — Anwendbarkeitsbedingung: übernommen

Dein Abschnitt 5.2 bleibt. R-041 und R-057 tragen jetzt im Katalog den ausdrücklichen
Verweis darauf. **Zu tun:** Nichts jetzt — relevant für Phase 3.

## 4 — R-053: mein Fehler, und er kostet dich Nacharbeit

Du hast recht: Die Regel sagte „`zahlbeitrag_rate_eur` … €/Jahr". Das ist in sich
widersprüchlich — die Rate ist bei monatlicher Zahlweise ein Zwölftel des Jahresbeitrags
und läge systematisch unterhalb des Korridors.

**Die Regel ist korrigiert: R-053 prüft jetzt `bruttobeitrag_jahr_eur`.**

Damit entfallen beide Kompromisse, die du eingehen musstest:

- **Die Zahlweise wird wieder frei gezogen**, unabhängig von der Beitragshöhe. Die
  Kopplung „günstige Verträge werden seltener monatlich gezahlt" war zwar marktüblich, aber
  sie war eine künstliche Abhängigkeit im Datensatz, die nur aus dem Spezifikationsfehler
  folgte. Solche Abhängigkeiten können später die Auswertung beeinflussen, ohne dass jemand
  die Ursache kennt.
- **Die Kappung an der Obergrenze entfällt.** Die 2,4 Prozent gekappter Vollkasko-Angebote
  haben die Beitragsverteilung am oberen Rand verzerrt.

**Zu tun:** Beides zurückbauen, Generator neu laufen lassen, Hashes und Tests aktualisieren.
Prüfe danach, ob die Jahresbruttobeiträge tatsächlich im Korridor liegen — bei einem
Malus-Vollkaskovertrag mit hoher Typklasse könnte es weiterhin eng werden. Falls einzelne
Angebote den Korridor auch als Jahresbeitrag überschreiten: **nicht kappen**, sondern
melden. Dann ist der Korridor zu eng gewählt und der Schwellenwert gehört angepasst — er
steht in `config.schwellen`, genau dafür.

**Deine Beobachtung bleibt trotzdem gültig und gehört in die Arbeit:** Ein fester
C2-Schwellenwert erzeugt am Rand des Wertebereichs zwangsläufig Fehlalarme. Nur war der
Rand hier künstlich erzeugt. Halte den Punkt in `docs/iteration_log.md` fest, damit er beim
Schreiben nicht verlorengeht.

## Was ausdrücklich bestätigt bleibt

- **Abgelehnte Angebote ohne Rang**, übrige lückenlos 1..m, mindestens zwei bepreiste
  Angebote je Anfrage.
- **FIRMA nur in Sparte 130.** Richtig — ohne Bezugsalter wären R-028 und R-029 undefiniert.
  Reale Firmenwagen gibt es zwar, aber das ist eine vertretbare Modellvereinfachung.
  Trage sie in `docs/verteilungsquellen.md` ein, falls noch nicht geschehen.
- **Geschichtete PLZ-Ziehung für Hausrat.** Gut begründet: Bei 0,4 Prozent Anteil für
  ZÜRS-Zone 4 sind das je Lauf nur rund ein Dutzend Fälle — ohne Schichtung wäre R-048 schon
  auf sauberen Daten instabil. Dokumentiere die Schichtung als Modellannahme, weil sie die
  PLZ-Verteilung für Hausrat an ZÜRS koppelt.
- **Der Generator liest keine Schwellenwerte aus `config.schwellen`.** Richtig und wichtig:
  Sonst erzeugte jede Schwellenvariation in Phase 6 einen anderen Datensatz, und Ursache und
  Wirkung wären nicht mehr trennbar.

## Abnahme

1. Zahlweise wird unabhängig von der Beitragshöhe gezogen.
2. Keine Kappung mehr an der Beitragsobergrenze.
3. Jahresbruttobeiträge liegen im Korridor aus `config.schwellen` — oder die Überschreitung
   ist benannt statt versteckt.
4. `00000000` steht in der Sentinel-Liste.
5. `pytest`, `ruff`, `mypy` grün; Hashes aktualisiert.
6. Commit und Push.

Halte danach an. Phase 3 kommt als eigener Prompt — und danach der Freeze.
