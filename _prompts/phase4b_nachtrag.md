# Phase 4b — Nachtrag: Zuteilung, Buchführung, Commit

> Direkt im Anschluss an Phase 4, **im selben Chat**. Kopiere alles ab der Trennlinie.

---

Vier Nachträge zu Phase 4. Die ersten beiden sind Buchführung, der dritte ist eine
Designentscheidung, die vor Phase 6 fallen muss — danach kosten 1.680 Läufe die
Wiederholung.

## Aufgabe 1 — Zuerst committen und pushen

Committe den Stand von Phase 4 unverändert und pushe ihn. Erst danach die Änderungen aus
diesem Nachtrag, als eigener Commit. Der Verlauf soll zeigen, was der Injektor beim Bau
war und was danach aus der Auswertungslogik heraus geändert wurde — nicht beides vermischt.

## Aufgabe 2 — Die Grenze innerhalb von `config/default.yaml` festhalten

Du hast beim Freeze „Schwellenwerte (auch die in `config/default.yaml`)" eingefroren. Das
ist richtig, aber in derselben Datei stehen laut `CLAUDE.md`, Abschnitt 3, auch Stichtag,
Pfade, **Faktorstufen** und Master-Seed. Phase 6 variiert Fehlerraten und Wiederholungen,
die dort liegen.

Ergänze in `docs/iteration_log.md` beim Freeze-Umfang einen Satz, der beides trennt:

- **Eingefroren** sind Regelschwellen — die Toleranz von R-031/R-036, der Korridor von
  R-053, die vier C2-Schwellen und alles andere, was in ein Prädikat eingeht.
- **Nicht eingefroren** sind Versuchsparameter — Fehlerraten, Wiederholungszahl,
  Master-Seed, Stichtag, Pfade.

Deine eigene Entscheidungsprobe trägt die Trennung: Eine geänderte Faktorstufe ändert
nicht, was die Regeln auf einem gegebenen Datensatz melden — sie erzeugt einen anderen
Datensatz. Ohne den Satz liest jemand später „die Konfiguration ist eingefroren" und hält
Phase 6 für eine Regeländerung.

## Aufgabe 3 — Die Zuteilung auf Varianten umstellen

**Das ist der inhaltliche Kern dieses Nachtrags.**

Du berichtest, dass F4-f, F7-c und F7-d ihr Kontingent nicht ausschöpfen — es gibt nur 231
Tarifzeilen — und dass der Rest an die übrigen Varianten der Klasse geht. Diese
Umverteilung erzeugt ein Problem, das erst in Phase 6 sichtbar würde:

**Die Zusammensetzung einer Klasse verschiebt sich mit der Fehlerrate.** Je höher die Rate,
desto früher stoßen die knappen Varianten an ihre Decke und desto größer wird der Anteil
der reichlich vorhandenen. Fehlerrate ist aber Faktor UV2 des Experiments. Ein gemessener
Zusammenhang „höhere Rate → anderer Recall" wäre dann teils ein Ratenwirkung, teils eine
Verschiebung der Variantenmischung — und der Page-Trendtest über die Ratenstufen misst
beides zusammen, ohne sie trennen zu können. Das ist ein Confounder im Kern des
Versuchsplans, kein Randdetail.

### Umstellung

Teile das Kontingent **proportional zum eigenen adressierbaren Universum jeder Variante**
zu, normiert auf das Klassenkontingent:

```
n_i = rate × |Klassenuniversum| × universum_i / Σ_j universum_j
```

Da die Summe der Variantenuniversen wegen Überschneidungen (F4-c und F4-d treffen beide
`wohnflaeche_qm`) nie kleiner ist als das Klassenuniversum, gilt `n_i ≤ universum_i` für
jede Rate ≤ 1. Es läuft also nie etwas über, es muss nie etwas umverteilt werden, das
Klassenkontingent bleibt unverändert — und der Anteil jeder Variante ist über **alle**
Ratenstufen konstant. Genau das braucht UV2.

Protokolliere je Lauf im `manifest.json`: Universum je Variante, zugeteilte Zahl je
Variante und den resultierenden Anteil. Der Anteil muss über die Ratenstufen identisch
sein; schreibe dafür einen Test.

### Der Preis, und was ihn ausgleicht

Bei proportionaler Zuteilung bekommt F7-c bei 2 Prozent nur noch eine einstellige Zahl an
Fehlern statt 231. Für die klassenweise Auswertung ist das richtig, für die
**variantenweise** Auswertung zu wenig — und gerade der Recall je
`injektor_variante_id` ist der empirische Beleg gegen den Zirkularitätsvorwurf. Bei n = 5
sagt er nichts.

Ergänze deshalb einen zweiten Modus in `scripts/inject.py`:

`--modus variante --variante F7-c` erzeugt einen Lauf, der **nur diese eine Variante**
injiziert, und zwar mit der größten Zahl, die ihr Universum hergibt (Obergrenze über einen
Parameter begrenzbar). Diese Läufe gehören **nicht** in den faktoriellen Versuchsplan,
sondern in einen eigenen Teilversuch „Variantencharakterisierung". Dort steht dann je
Variante ein belastbares n mit brauchbarem Konfidenzintervall.

Damit hat jede der beiden Fragen ihren eigenen sauberen Lauf: die Klassenwirkung über
Ratenstufen den faktoriellen Plan mit konstanter Mischung, die Variantenwirkung den
erschöpfenden Einzellauf.

## Aufgabe 4 — Geänderte Zellen sind nicht gleich fehlerhafte Zellen

Deine Spalte `mitgezogen` ist die richtige Entscheidung — eine nachgeführte Rangzelle ist
gegenüber den verfälschten Daten korrekt und darf nicht als unerkannter Fehler zählen.
Sie hat aber eine Nebenwirkung, die ausgewiesen werden muss:

Bei F8 stehen 5.362 fehlerhaften Zellen 2.957 mitgezogene gegenüber, bei HO2 5.374 zu
1.233. Der Datensatz ist dort also an rund der Hälfte mehr Stellen verändert, als die
Fehlerrate nominell angibt. „Zwei Prozent" bedeutet für F8 etwas anderes als für F3 —
nicht nur wegen des klassenspezifischen Universums, sondern zusätzlich wegen der
Mitzieh-Zellen.

Weise im `manifest.json` beide Zahlen getrennt aus, mit sprechenden Namen, etwa
`zellen_fehlerhaft` und `zellen_geaendert_gesamt`, und ergänze in `README.md` einen Satz
dazu an der Stelle, an der die Bezugsgröße der Fehlerrate erklärt wird.

## Abnahme

1. Phase 4 committet und gepusht, dieser Nachtrag als eigener Commit.
2. Freeze-Umfang in `docs/iteration_log.md` um die `config`-Trennung ergänzt.
3. Proportionale Zuteilung implementiert, Anteile über Ratenstufen konstant, per Test
   abgesichert, im Manifest protokolliert.
4. `--modus variante` vorhanden und an mindestens einer knappen Variante erprobt.
5. Beide Zellzahlen getrennt im Manifest, Erläuterung in `README.md`.
6. Gegencheck weiterhin sauber, `pytest`, `ruff`, `mypy` grün.

**Keine Änderung am Regelkatalog.** Die Befunde aus Phase 4 bleiben Befunde.

Halte an und berichte, wie sich die Variantenanteile je Klasse durch die Umstellung
verschoben haben.
