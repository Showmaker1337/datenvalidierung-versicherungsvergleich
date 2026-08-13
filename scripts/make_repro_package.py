"""Baut das Reproduzierbarkeitspaket unter ``results/reproduction/``.

Aufruf::

    python scripts/make_repro_package.py
    python scripts/make_repro_package.py --config config/experiment.yaml

Was entsteht
------------

``konfiguration/``
    Kopien von ``config/default.yaml`` und ``config/experiment.yaml``.
``umgebung/``
    ``pip_freeze.txt`` (der tatsaechliche Stand der Umgebung),
    ``requirements.txt`` und ``requirements-vergleich.txt``. Die beiden
    Anforderungsdateien bleiben **getrennt**: Der Frameworkvergleich wird separat
    installiert und nimmt an keinem Lauf teil. Siebzehn transitive
    Abhaengigkeiten fuer einen Vergleich, der nicht in die Inferenzstatistik
    eingeht, gehoeren nicht in das Paket des eigentlichen Experiments.
``git.json``
    Commit des aktuellen Standes und Commit des Tags ``freeze-regelkatalog``.
    Fuer den Tag gilt ``git rev-parse freeze-regelkatalog^{commit}`` — das ist der
    **Commit**, nicht das Tag-Objekt. Ein annotiertes Tag hat eine eigene
    Objekt-ID, und wer sie angibt, nennt nicht den Codestand.
``seeds.json``
    Master-Seed, Stroeme und die abgeleiteten Seeds **jedes** Laufs.
``hashes.json``
    SHA-256 aller Ein- und Ausgabedateien.
``laufbericht.json``
    Zahl der gerechneten und der gescheiterten Laeufe.
``README_reproduction.md``
    Die exakten Kommandos in der richtigen Reihenfolge.

Damit ist jeder Einzelwert der Ergebnistabellen rueckverfolgbar: von der Zahl in
der Tabelle ueber die ``run_id`` im Langformat zu den Seeds dieses Laufs und von
dort zu den Kommandos, die ihn erzeugen. Das ist Hevner Guideline 5 (Research
Rigor) in konkreter Form und gehoert in den Anhang.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ermoeglicht den Aufruf "python scripts/make_repro_package.py" ohne editierbare
# Installation. Muss vor den Projektimporten stehen.
_WURZEL = Path(__file__).resolve().parents[1]
if str(_WURZEL) not in sys.path:
    sys.path.insert(0, str(_WURZEL))

import argparse  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
from typing import TYPE_CHECKING, Any, Final  # noqa: E402

from scripts.inject import _namensfaktor, _schreibe_json  # noqa: E402
from src.common.config import STANDARD_KONFIGURATION, als_dict, lade_config  # noqa: E402
from src.common.pfade import (  # noqa: E402
    REFERENZ_DATEIEN,
    Artefakt,
    experiment_verzeichnis,
    sha256_datei,
)
from src.common.seeding import Strom, lauf_seed, seed_als_int, wurzel_seeds  # noqa: E402
from src.evaluation.experimentplan import STANDARD_PLAN, lade_plan, laeufe  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    from src.common.config import Config
    from src.evaluation.experimentplan import Lauf, Versuchsplan

__all__ = ["main"]

#: Name des Pakets unterhalb von ``results/``.
PAKET: Final[str] = "reproduction"

#: Name des Tags, ab dem der Regelkatalog eingefroren ist.
FREEZE_TAG: Final[str] = "freeze-regelkatalog"

#: Basispunkte einer Rate von 100 Prozent — Kodierung der Rate als Faktorstufe.
_BASISPUNKTE: Final[int] = 10000

#: Ergebnisdateien, die in die Hashliste gehoeren.
_ERGEBNISDATEIEN: Final[tuple[str, ...]] = (
    "metrics_long.parquet",
    "hypothesen.json",
    "hypothesen.md",
    "befunde_aus_der_entwicklung.md",
    "framework_vergleich.json",
    "b3_framework.json",
    "ground_truth_check.json",
    "clean_baseline.json",
    "freeze.json",
    "regelkatalog.csv",
    "failed_runs.json",
    "experiment_lauf.json",
    "reproduktionsstichprobe.json",
)


def _git(*argumente: str) -> str | None:
    """Fuehrt ein Git-Kommando aus und gibt seine Ausgabe zurueck.

    Args:
        *argumente: Argumente hinter ``git``.

    Returns:
        Die Ausgabe ohne Zeilenende, oder ``None``, wenn das Kommando
        fehlschlaegt — etwa weil das Verzeichnis kein Repository ist oder der Tag
        fehlt. Bewusst kein Abbruch: Das Paket ist auch ohne Git-Angaben besser
        als kein Paket, und die fehlende Angabe steht sichtbar als ``null`` darin.
    """
    fertig = subprocess.run(  # noqa: S603 - fest verdrahtete Argumente, kein Schalenaufruf
        ["git", *argumente],  # noqa: S607 - git wird aus dem Pfad aufgeloest
        capture_output=True,
        text=True,
        cwd=str(_WURZEL),
        check=False,
    )
    if fertig.returncode != 0:
        return None
    return fertig.stdout.strip()


def _git_angaben() -> dict[str, Any]:
    """Sammelt die Git-Angaben des Pakets.

    Returns:
        Commit des aktuellen Standes, Commit des Freeze-Tags, Tag-Objekt und
        Zustand des Arbeitsverzeichnisses.
    """
    status = _git("status", "--porcelain")
    return {
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "freeze_tag": FREEZE_TAG,
        "freeze_commit": _git("rev-parse", f"{FREEZE_TAG}^{{commit}}"),
        "freeze_tagobjekt": _git("rev-parse", FREEZE_TAG),
        "hinweis_freeze": (
            "Zitiert wird der Commit, nicht das Tag-Objekt: Ein annotiertes Tag hat eine "
            "eigene Objekt-ID, und wer sie angibt, nennt nicht den Codestand."
        ),
        "arbeitsverzeichnis_sauber": status == "" if status is not None else None,
        "unversionierte_aenderungen": status.splitlines() if status else [],
    }


def _seeds_eines_laufs(config: Config, lauf: Lauf) -> dict[str, Any]:
    """Leitet die Seeds eines Laufs ab, ohne ihn auszufuehren.

    Verwendet werden dieselben Funktionen wie im Lauf selbst
    (:func:`~src.common.seeding.lauf_seed`), damit hier keine zweite Ableitung
    entsteht. Zwei Ableitungen derselben Seeds waeren ein A2-Risiko, das erst
    auffiele, wenn jemand das Paket benutzt.

    Args:
        config: Geladene Konfiguration.
        lauf: Der Lauf.

    Returns:
        Die Seeds als ganze Zahlen samt Faktorstufen.
    """
    faktoren = (
        _namensfaktor(lauf.serie),
        _namensfaktor(lauf.design),
        _namensfaktor(lauf.segment),
        round(lauf.fehlerrate * _BASISPUNKTE),
        lauf.injektions_index,
    )
    basis = (
        wurzel_seeds(config.master_seed).basis
        if lauf.basis_index == 0
        else lauf_seed(config.master_seed, Strom.BASIS, lauf.basis_index)
    )
    return {
        "run_id": lauf.run_id,
        "teilversuch": lauf.teilversuch,
        "klasse": lauf.klasse,
        "variante": lauf.variante,
        "fehlerrate": lauf.fehlerrate,
        "wiederholung": lauf.wiederholung,
        "basis_index": lauf.basis_index,
        "injektions_index": lauf.injektions_index,
        "n_anfragen": lauf.n_anfragen,
        "max_fehler": lauf.max_fehler,
        "verfahren": list(lauf.verfahren),
        "seed_basis": str(seed_als_int(basis)),
        "seed_inject": str(
            seed_als_int(lauf_seed(config.master_seed, Strom.INJEKTION, *faktoren))
        ),
        "seed_modell": str(
            seed_als_int(lauf_seed(config.master_seed, Strom.MODELL, *faktoren))
        ),
    }


def _hashes(  # noqa: C901, PLR0912 - eine Verzweigung je Dateigruppe, alle gleich flach
    config: Config, plan: Versuchsplan
) -> dict[str, dict[str, str]]:
    """Bildet die SHA-256-Werte aller Ein- und Ausgabedateien.

    Args:
        config: Geladene Konfiguration.
        plan: Der Versuchsplan.

    Returns:
        Je Gruppe eine Abbildung Pfad auf Hashwert, jeweils nach Pfad sortiert.
    """
    eingaben: dict[str, str] = {}
    for pfad in (STANDARD_KONFIGURATION, STANDARD_PLAN, _WURZEL / "requirements.txt"):
        if pfad.is_file():
            eingaben[pfad.relative_to(_WURZEL).as_posix()] = sha256_datei(pfad)
    for name in REFERENZ_DATEIEN:
        pfad = config.pfade.reference / name
        if pfad.is_file():
            eingaben[f"data/reference/{name}"] = sha256_datei(pfad)

    ausgaben: dict[str, str] = {}
    for name in _ERGEBNISDATEIEN:
        pfad = config.pfade.results / name
        if pfad.is_file():
            ausgaben[f"results/{name}"] = sha256_datei(pfad)
    for unterverzeichnis in ("tables", "figures"):
        verzeichnis = config.pfade.results / unterverzeichnis
        if not verzeichnis.is_dir():
            continue
        for pfad in sorted(verzeichnis.iterdir()):
            if pfad.is_file():
                ausgaben[f"results/{unterverzeichnis}/{pfad.name}"] = sha256_datei(pfad)

    laufartefakte: dict[str, str] = {}
    for lauf in laeufe(plan):
        ziel = experiment_verzeichnis(
            config, lauf.serie, lauf.design, lauf.segment, lauf.fehlerrate, lauf.wiederholung
        )
        for artefakt in (Artefakt.ERROR_LOG, Artefakt.ERROR_LOG_RECORDS, Artefakt.METRICS):
            pfad = ziel / artefakt.value
            if pfad.is_file():
                laufartefakte[f"{lauf.run_id}/{artefakt.value}"] = sha256_datei(pfad)

    return {
        "eingaben": dict(sorted(eingaben.items())),
        "ausgaben": dict(sorted(ausgaben.items())),
        "laufartefakte": dict(sorted(laufartefakte.items())),
    }


def _readme(plan: Versuchsplan, git: dict[str, Any], bericht: dict[str, Any]) -> str:
    """Formuliert ``README_reproduction.md``.

    Args:
        plan: Der Versuchsplan.
        git: Ergebnis von :func:`_git_angaben`.
        bericht: Inhalt von ``results/experiment_lauf.json``, oder ein leeres
            Woerterbuch.

    Returns:
        Den Dateiinhalt.
    """
    gescheitert = bericht.get("laeufe_gescheitert")
    gerechnet = bericht.get("laeufe_gerechnet")
    zeile_fehlschlaege = (
        f"- Gescheiterte Laeufe: **{gescheitert}** von {bericht.get('laeufe_im_plan')} im Plan"
        if gescheitert is not None
        else "- Gescheiterte Laeufe: unbekannt (results/experiment_lauf.json fehlt)"
    )
    return f"""# Reproduktion der Experimentserie {plan.serie}

Dieses Verzeichnis enthaelt alles, was gebraucht wird, um jede Zahl der
Ergebnistabellen nachzurechnen. Der Weg ist immer derselbe: Zahl in der Tabelle
→ `run_id` im Langformat → Seeds dieses Laufs in `seeds.json` → Kommando unten.

## Stand des Codes

- Commit: `{git.get("commit")}`
- Zweig: `{git.get("branch")}`
- Regelkatalog eingefroren mit Tag `{FREEZE_TAG}`, Commit `{git.get("freeze_commit")}`
- Arbeitsverzeichnis beim Packen sauber: {git.get("arbeitsverzeichnis_sauber")}

Der Freeze-Commit ist ueber `git rev-parse {FREEZE_TAG}^{{commit}}` bestimmt und
**nicht** ueber die Objekt-ID des annotierten Tags (`{git.get("freeze_tagobjekt")}`).
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
python scripts/inject.py --serie {plan.serie} --design A --klasse F3 --rate 0.02 --wdh 7
python scripts/evaluate.py --serie {plan.serie} --design A --klasse F3 --rate 0.02 --wdh 7
```

`scripts/evaluate.py` stellt den verfaelschten Datensatz aus den Seeds neu her
und vergleicht ihn Entitaet fuer Entitaet gegen die SHA-256-Werte im
`manifest.json` des Laufs. Weicht ein Wert ab, bricht es ab — das ist der
Reproduzierbarkeitsnachweis fuer diesen Lauf.

Fuer die Laeufe des Teilversuchs T5 (Datenvarianz) kommen `--basis-index` und
`--injektions-index` hinzu; beide stehen je Lauf in `seeds.json`.

## Umfang der Serie

- Laeufe im Plan: {bericht.get("laeufe_im_plan", "unbekannt")}
- Gerechnete Laeufe: {gerechnet if gerechnet is not None else "unbekannt"}
{zeile_fehlschlaege}
- `PYTHONHASHSEED` beim Lauf: `{bericht.get("pythonhashseed")}`
- Arbeitsprozesse: {bericht.get("worker", "unbekannt")}

Die Zahl gescheiterter Laeufe gehoert in die Arbeit. Stillschweigend mit weniger
Laeufen weiterzurechnen waere eine verdeckte Stichprobenreduktion; die Liste der
Fehlschlaege steht in `results/failed_runs.json`.

## Was nicht in diesem Paket liegt

Der **verfaelschte Datensatz** jedes Laufs. Er wird nicht dauerhaft gespeichert:
Bei {bericht.get("laeufe_im_plan", "tausenden")} Laeufen zu je mehreren
zehntausend Zeilen entstuenden zweistellige Gigabyte, und er ist aus
`seed_basis` und `seed_inject` jederzeit exakt wiederherstellbar. Genau das tut
`scripts/evaluate.py`.
"""


def _argumente() -> argparse.ArgumentParser:
    """Baut den Argumentparser des Skripts."""
    parser = argparse.ArgumentParser(
        description="Baut das Reproduzierbarkeitspaket unter results/reproduction/."
    )
    parser.add_argument(
        "--config", type=Path, default=STANDARD_PLAN, help="Pfad des Versuchsplans"
    )
    parser.add_argument(
        "--fach-config",
        type=Path,
        default=None,
        dest="fach_config",
        help="Pfad der fachlichen Konfiguration",
    )
    parser.add_argument("--still", action="store_true", help="Keine Fortschrittsausgabe")
    return parser


def main(argumente: Sequence[str] | None = None) -> int:
    """Einstiegspunkt des Skripts.

    Args:
        argumente: Kommandozeilenargumente; ``None`` nimmt ``sys.argv``.

    Returns:
        ``0`` bei Erfolg.
    """
    optionen = _argumente().parse_args(argumente)
    plan = lade_plan(optionen.config)
    config = lade_config(optionen.fach_config)

    ziel = config.pfade.results / PAKET
    (ziel / "konfiguration").mkdir(parents=True, exist_ok=True)
    (ziel / "umgebung").mkdir(parents=True, exist_ok=True)

    for quelle in (STANDARD_KONFIGURATION, optionen.config):
        if quelle.is_file():
            shutil.copy2(quelle, ziel / "konfiguration" / quelle.name)
    for name in ("requirements.txt", "requirements-vergleich.txt"):
        quelle = _WURZEL / name
        if quelle.is_file():
            shutil.copy2(quelle, ziel / "umgebung" / name)

    einfrieren = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        capture_output=True,
        text=True,
        check=False,
    )
    (ziel / "umgebung" / "pip_freeze.txt").write_text(
        einfrieren.stdout, encoding="utf-8", newline="\n"
    )

    git = _git_angaben()
    _schreibe_json(ziel / "git.json", git)

    alle = laeufe(plan)
    _schreibe_json(
        ziel / "seeds.json",
        {
            "master_seed": config.master_seed,
            "stroeme": {strom.name.lower(): int(strom) for strom in Strom},
            "hinweis": (
                "Jeder Lauf leitet seine Seeds allein aus seiner Faktorkombination ab "
                "(src/common/seeding.lauf_seed), niemals ueber SeedSequence.spawn(). Das "
                "Ergebnis haengt damit nicht von der Reihenfolge oder der Zahl der "
                "Arbeitsprozesse ab."
            ),
            "konfiguration": als_dict(config),
            "laeufe": [_seeds_eines_laufs(config, lauf) for lauf in alle],
        },
    )
    _schreibe_json(ziel / "hashes.json", _hashes(config, plan))

    berichtspfad = config.pfade.results / "experiment_lauf.json"
    bericht: dict[str, Any] = (
        json.loads(berichtspfad.read_text(encoding="utf-8")) if berichtspfad.is_file() else {}
    )
    _schreibe_json(ziel / "laufbericht.json", bericht)
    (ziel / "README_reproduction.md").write_text(
        _readme(plan, git, bericht), encoding="utf-8", newline="\n"
    )

    if not optionen.still:
        hashes = json.loads((ziel / "hashes.json").read_text(encoding="utf-8"))
        print(f"Reproduzierbarkeitspaket in {ziel}")
        print(f"  Laeufe mit Seeds       {len(alle)}")
        for gruppe, eintraege in hashes.items():
            print(f"  Hashwerte {gruppe:<14} {len(eintraege)}")
        print(f"  Commit                 {git.get('commit')}")
        print(f"  Freeze-Commit          {git.get('freeze_commit')}")
        if bericht:
            print(f"  Gescheiterte Laeufe    {bericht.get('laeufe_gescheitert')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
