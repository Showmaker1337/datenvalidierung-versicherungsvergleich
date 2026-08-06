# Phase 1b — Nachtrag zu den Spezifikationslücken

> Kurzer Nachtrag vor Phase 2. Kopiere alles ab der Trennlinie in Claude Code.

---

Du hast in Phase 1 drei Lücken in der Spezifikation gemeldet. Alle drei sind jetzt in
`spec/01_datenmodell.md` und `spec/02_regelkatalog.md` entschieden. Lies beide Dateien neu
ein und setze die Entscheidungen um. Das ist ein kleiner Nachtrag, keine neue Phase.

## 1 — SF-Beitragssatz: die Spezifikation wurde an deine Umsetzung angepasst

`spec/01`, Abschnitt 2.6 fordert jetzt ausdrücklich **nicht-steigende**, nicht streng
fallende Monotonie. Deine Fassung mit Plateaus ist damit die spezifikationskonforme, nicht
die abweichende. Der Grund steht dort: Plateaus bei hohen Klassen bilden reale
Beitragssatztabellen ab, sie sind kein Kompromiss.

**Zu tun:** Nur den Test und den Docstring anpassen, falls dort noch „streng monoton" steht.
Die Daten bleiben, wie sie sind. Ergänze in `docs/verteilungsquellen.md` die beiden weiteren
Vereinfachungen aus `spec/01`: dass die meisten Versicherer bei SF 35 enden und dass viele
moderne Tabellen SF 1 auf 100 Prozent statt auf 58 setzen.

## 2 — SF-Sonderklassen: zwei getrennte Abbildungen statt einer

`spec/01`, Abschnitt 2.8 definiert jetzt **zwei** Funktionen, weil R-029 und R-030
Verschiedenes messen:

| SF-Klasse | `schadenfreie_jahre()` | `sf_ordnung()` |
|---|---|---|
| `M` | 0 | −3 |
| `S` | 0 | −2 |
| `0` | 0 | −1 |
| `1/2` | 0 | 0 |
| `SF1` … `SF50` | 1 … 50 | 1 … 50 |

`schadenfreie_jahre()` bedient R-029 (mehr schadenfreie Jahre als Führerscheinbesitz).
Sonderklassen bedeuten null schadenfreie Jahre — die Regel ist dort trivial erfüllt, und
das ist fachlich korrekt.

`sf_ordnung()` bedient R-030 (Vollkasko-SF nicht besser als Haftpflicht-SF). Sie braucht
eine vollständige Ordnung, damit die Regel auch für Sonderklassen greift statt sie
stillschweigend zu überspringen.

**Zu tun:** Ersetze `sf_numerischer_teil()` durch diese beiden Funktionen in
`src/common/`. Tests für beide, insbesondere die Grenzfälle `M` gegen `S` und `1/2` gegen
`SF1`.

## 3 — ISO-4217-Katalog: Referenzdatei über `pycountry`

`spec/01`, Abschnitt 2.7 führt `waehrungen.csv` als siebte Referenztabelle ein: `code`,
`name`, `numerisch`, rund 180 Einträge.

**Erzeuge sie einmalig über das Python-Paket `pycountry`** und lege das Ergebnis als CSV
ab. Nimm `pycountry` in `requirements.txt` auf. Schreibe die Liste **nicht** aus dem
Gedächtnis in den Quelltext — eine falsche Währungsliste fällt niemandem auf und macht die
Regel wertlos.

R-012 ist in `spec/02` jetzt zweistufig: Der Code muss im Katalog existieren
(syntaktische Gültigkeit) **und** im Kontext dieses Systems `EUR` sein (fachliche
Zulässigkeit). Beide Stufen werden getrennt gemeldet. Das ist ein kleines, aber gutes
Beispiel dafür, dass „gültig" und „zulässig" nicht dasselbe sind — es taucht in der Arbeit
wieder auf.

**Zu tun:** `waehrungen.csv` erzeugen, `referenz.py` um den Loader erweitern, Test auf
Vollständigkeit und darauf, dass `EUR` enthalten ist. Die Regel selbst kommt erst in
Phase 3.

## 4 — Faker: deine Abweichung wird zur Regel

`CLAUDE.md`, Abschnitt 4 nennt jetzt ausdrücklich `faker.seed_instance()` und verbietet das
klassenweite `Faker.seed()`. Deine Begründung war richtig: Globaler Zustand widerspricht
Architekturregel A2. Nichts zu tun, nur zur Kenntnis.

## Was ausdrücklich bestätigt bleibt

- **PLZ synthetisch.** Die Begründung trägt: kein Massendownload, `pageSize` auf 50
  gedeckelt, und das Unterscheidungszeichen des Zulassungsbezirks ist gar nicht Teil der
  API. Eine gemischt reale und synthetische Tabelle wäre schwerer zu verteidigen als eine
  durchgängig synthetische. Bleibt so.
- **Getrennte Baujahrgrenzen** (`GENERATOR_BAUJAHR_UNTERGRENZE` 1850 gegen
  `BAUJAHR_UNTERGRENZE_REGEL` 1500). Richtig erkannt: Die Regel soll ein unmögliches
  Baujahr fangen, nicht ein ungewöhnliches. Bleibt so.
- **`pflichtfelder.py` vorgezogen.** Richtig — das Profil brauchen Generator und
  Regel-Engine gemeinsam, in `common` verhindert es später eine A1-Verletzung.

## Abnahme

1. `waehrungen.csv` existiert mit rund 180 Einträgen, `EUR` enthalten.
2. `schadenfreie_jahre()` und `sf_ordnung()` implementiert und getestet.
3. Kein Test und kein Docstring behauptet mehr strenge Monotonie.
4. `pytest`, `ruff` und `mypy` grün.
5. Commit und Push.

Halte danach an. Phase 2 kommt als eigener Prompt.
