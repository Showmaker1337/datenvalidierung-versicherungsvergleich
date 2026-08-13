# Reproduktion der Experimentserie s01

Dieses Verzeichnis enthaelt alles, was gebraucht wird, um jede Zahl der
Ergebnistabellen nachzurechnen. Der Weg ist immer derselbe: Zahl in der Tabelle
→ `run_id` im Langformat → Seeds dieses Laufs in `seeds.json` → Kommando unten.

## Stand des Codes

- Commit: `32baf8aed1851c08e03980cb380075f8657672a0`
- Zweig: `main`
- Regelkatalog eingefroren mit Tag `freeze-regelkatalog`, Commit `30ca5ea429a0abddec7050af1d1a42cdf9942548`
- Arbeitsverzeichnis beim Packen sauber: False

Der Freeze-Commit ist ueber `git rev-parse freeze-regelkatalog^{commit}` bestimmt und
**nicht** ueber die Objekt-ID des annotierten Tags (`3f64827ce95801aec6df29d0d18232404c4af206`).
Die Objekt-ID benennt das Tag, nicht den Codestand.

## Umgebung

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r umgebung/requirements.txt
```

Der Frameworkvergleich wird **getrennt** installiert und nimmt an keinem Lauf
teil:

```bash
pip install -r umgebung/requirements-vergleich.txt
```

`umgebung/pip_freeze.txt` haelt den tatsaechlichen Stand der Umgebung fest, in
der die Serie gerechnet wurde.

## Kommandos in der richtigen Reihenfolge

```bash
python scripts/build_reference.py
python scripts/run_experiment.py --config config/experiment.yaml
python scripts/framework_vergleich.py
python scripts/analyze.py --config config/experiment.yaml
python scripts/make_repro_package.py
```

`scripts/build_reference.py` ist nur noetig, wenn `data/reference/` fehlt; die
Tabellen sind versioniert und ihre Hashwerte stehen in `hashes.json`.

## Einen einzelnen Lauf nachrechnen

Jeder Lauf ist allein aus seiner `run_id` und der Konfiguration reproduzierbar.
Die Kennung `<serie>_<design>_<klasse>_r<bp>_w<nn>` traegt alle Faktorstufen;
`<bp>` ist die Fehlerrate in Basispunkten, `<nn>` die Wiederholung.

```bash
python scripts/inject.py --serie s01 --design A --klasse F3 --rate 0.02 --wdh 7
python scripts/evaluate.py --serie s01 --design A --klasse F3 --rate 0.02 --wdh 7
```

`scripts/evaluate.py` stellt den verfaelschten Datensatz aus den Seeds neu her
und vergleicht ihn Entitaet fuer Entitaet gegen die SHA-256-Werte im
`manifest.json` des Laufs. Weicht ein Wert ab, bricht es ab — das ist der
Reproduzierbarkeitsnachweis fuer diesen Lauf.

Fuer die Laeufe des Teilversuchs T5 (Datenvarianz) kommen `--basis-index` und
`--injektions-index` hinzu; beide stehen je Lauf in `seeds.json`.

## Umfang der Serie

- Laeufe im Plan: 1035
- Gerechnete Laeufe: 0
- Gescheiterte Laeufe: **0** von 1035 im Plan
- `PYTHONHASHSEED` beim Lauf: `0`
- Arbeitsprozesse: 8

Die Zahl gescheiterter Laeufe gehoert in die Arbeit. Stillschweigend mit weniger
Laeufen weiterzurechnen waere eine verdeckte Stichprobenreduktion; die Liste der
Fehlschlaege steht in `results/failed_runs.json`.

## Was nicht in diesem Paket liegt

Der **verfaelschte Datensatz** jedes Laufs. Er wird nicht dauerhaft gespeichert:
Bei 1035 Laeufen zu je mehreren
zehntausend Zeilen entstuenden zweistellige Gigabyte, und er ist aus
`seed_basis` und `seed_inject` jederzeit exakt wiederherstellbar. Genau das tut
`scripts/evaluate.py`.
