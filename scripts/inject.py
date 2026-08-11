"""Verfaelscht einen sauberen Datensatz kontrolliert und schreibt den Ground Truth.

Aufruf::

    python scripts/inject.py --serie s01 --design A --klasse F3 --rate 0.02 --wdh 7
    python scripts/inject.py --serie s01 --design A --klasse mix --rate 0.02 --wdh 1
    python scripts/inject.py --serie probe --design A --klasse F6 --rate 0.05 --wdh 0 \
        --n-anfragen 500 --behalten

Pfadschema
----------

Experimentlaeufe landen unter
``data/runs/<serie>/<design>/<klasse>/<rate>/<wdh>/``. In Phase 6 variieren
Fehlerklasse, Fehlerrate, Wiederholung und Varianzdesign; ein Pfad, der nur die
Fehlerrate kodierte, liesse tausende Laeufe einander ueberschreiben.

Die ``run_id`` traegt dieselbe Information als ein Token, etwa
``s01_A_F3_r0200_w07``. Damit bleibt Architekturregel A2 woertlich erfuellt: Der
Lauf ist allein aus ``run_id`` und Konfiguration reproduzierbar. Ad-hoc-Laeufe
ohne Faktorstufen — etwa der Clean-Baseline-Lauf — behalten die flache Form
``data/runs/<run_id>/``.

Was aufbewahrt wird
-------------------

``df_raw_dirty`` wird **nicht** dauerhaft gespeichert. Bei mehreren tausend
Laeufen zu je rund 60.000 Zeilen entstuenden zweistellige Gigabyte, und der
verfaelschte Datensatz ist aus ``seed_basis`` und ``seed_inject`` jederzeit exakt
reproduzierbar. Dauerhaft abgelegt werden ``error_log.parquet``,
``error_log_records.parquet``, ``config.yaml`` und ``manifest.json``; spaeter
kommen ``detections`` und ``metrics.json`` hinzu.

Das Flag ``--behalten`` legt die verfaelschten Daten zusaetzlich je Entitaet unter
``dirty/`` ab. Standard ist aus. Der Gegencheck braucht die Dateien nicht — er
laeuft im selben Prozess auf den Datenrahmen im Speicher.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ermoeglicht den Aufruf "python scripts/inject.py" ohne editierbare
# Installation. Muss vor den Projektimporten stehen.
_WURZEL = Path(__file__).resolve().parents[1]
if str(_WURZEL) not in sys.path:
    sys.path.insert(0, str(_WURZEL))

import argparse  # noqa: E402
import dataclasses  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from typing import TYPE_CHECKING, Any, Final  # noqa: E402

import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from src.common.config import als_dict as konfiguration_als_dict  # noqa: E402
from src.common.config import lade_config  # noqa: E402
from src.common.pfade import (  # noqa: E402
    DIRTY,
    MISCHMODUS,
    Artefakt,
    Schicht,
    entitaet_pfad,
    experiment_run_id,
    experiment_verzeichnis,
    sha256_dataframe,
)
from src.common.seeding import Strom, lauf_seed, wurzel_seeds  # noqa: E402
from src.common.serialisierung import ENTITAETEN, serialisiere  # noqa: E402
from src.generator.pipeline import erzeuge_datensatz  # noqa: E402
from src.injector import Fehlerklasse, injiziere  # noqa: E402
from src.verify import pruefe_ground_truth, schreibe_bericht  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence

    from numpy.random import SeedSequence

    from src.common.config import Config
    from src.injector import Injektionsergebnis

__all__ = ["main"]

#: Gewichte des praxisnahen Mischmodus (spec/03, Abschnitt 3).
#:
#: Dubletten und Unvollstaendigkeit dominieren die Branchenempirie.
MISCHGEWICHTE: Final[Mapping[str, float]] = {
    "F1": 0.30,
    "F6": 0.30,
    "F5": 0.15,
    "F3": 0.10,
    "F2": 0.05,
    "F8": 0.05,
    "F7": 0.03,
    "F4": 0.02,
}

#: Dateiname des Gegencheckberichts unter ``results/``.
_GEGENCHECK: Final[str] = "ground_truth_check.json"

#: Zahl der Bytes, mit denen ein Name als Faktorstufe kodiert wird.
_NAMENSBYTES: Final[int] = 8


def _namensfaktor(name: str) -> int:
    """Kodiert einen Namen reproduzierbar als nicht negative ganze Zahl.

    ``hash()`` waere hier falsch: Python streut Zeichenketten je Prozess anders,
    zwei Laeufe derselben Serie bekaemen verschiedene Seeds (Architekturregel A2).
    SHA-256 ist prozessuebergreifend stabil.

    Args:
        name: Zu kodierender Name, etwa der Serien- oder der Designname.

    Returns:
        Die Kodierung als ganze Zahl.
    """
    verdichtet = hashlib.sha256(name.encode("utf-8")).digest()[:_NAMENSBYTES]
    return int.from_bytes(verdichtet, "big")


def _gewichte(klasse: str) -> dict[str, float]:
    """Bestimmt die Klassengewichte eines Laufs.

    Args:
        klasse: Fehlerklasse oder ``mix``.

    Returns:
        Die Gewichte je Fehlerklasse.

    Raises:
        SystemExit: Bei einer unbekannten Fehlerklasse.
    """
    if klasse == MISCHMODUS:
        return dict(MISCHGEWICHTE)
    bekannt = [eintrag.value for eintrag in Fehlerklasse]
    if klasse not in bekannt:
        raise SystemExit(
            f"Unbekannte Fehlerklasse: {klasse!r}. Bekannt sind: {bekannt} und {MISCHMODUS!r}."
        )
    return {klasse: 1.0}


def _lade_clean(config: Config, clean_run: str | None) -> tuple[dict[str, pd.DataFrame], str]:
    """Beschafft die Rohschicht des sauberen Datensatzes.

    Ohne ``--clean-run`` wird sie im selben Prozess aus dem Basisstrom erzeugt.
    Das ist keine Notloesung, sondern die genauere Variante: Der saubere Datensatz
    haengt allein an ``master_seed`` und Konfiguration und muss deshalb nicht
    zwischengespeichert werden.

    Args:
        config: Geladene Konfiguration.
        clean_run: Kennung eines bereits erzeugten Laufs, oder ``None``.

    Returns:
        Die sieben Datenrahmen der Rohschicht und die Herkunftsangabe fuer das
        Manifest.

    Raises:
        SystemExit: Wenn eine Entitaetsdatei des angegebenen Laufs fehlt.
    """
    if clean_run is None:
        typisiert = erzeuge_datensatz(config, wurzel_seeds(config.master_seed).basis)
        return {name: serialisiere(typisiert[name]) for name in ENTITAETEN}, "erzeugt"

    daten: dict[str, pd.DataFrame] = {}
    for name in ENTITAETEN:
        pfad = entitaet_pfad(config, clean_run, Schicht.RAW, name)
        if not pfad.is_file():
            raise SystemExit(
                f"Rohschicht des Laufs {clean_run!r} unvollstaendig: {pfad} fehlt. "
                "Zuerst 'python scripts/generate.py --run-id <id>' ausfuehren."
            )
        daten[name] = pd.read_parquet(pfad).astype("string")
    return daten, f"data/runs/{clean_run}/clean/raw"


def _seed_inject(config: Config, optionen: argparse.Namespace) -> SeedSequence:
    """Leitet den Injektionsstrom aus den Faktorstufen des Laufs ab.

    Alle Faktorstufen gehen ein — Serie, Varianzdesign, Fehlerklasse, Fehlerrate
    und Wiederholung. Damit ist der Lauf allein aus seiner ``run_id`` und der
    Konfiguration reproduzierbar, unabhaengig von Reihenfolge und Parallelitaet
    (Architekturregel A2).
    """
    return lauf_seed(
        config.master_seed,
        Strom.INJEKTION,
        _namensfaktor(optionen.serie),
        _namensfaktor(optionen.design),
        _namensfaktor(optionen.klasse),
        round(optionen.rate * 10000),
        optionen.wdh,
    )


def _manifest(  # noqa: PLR0913 - das Manifest fuehrt alle Angaben des Laufs
    *,
    optionen: argparse.Namespace,
    config: Config,
    ergebnis: Injektionsergebnis,
    herkunft: str,
    zeilen: Mapping[str, int],
    hashes_clean: Mapping[str, str],
    hashes_dirty: Mapping[str, str],
    gegencheck_sauber: bool,
) -> dict[str, Any]:
    """Stellt das Manifest des Laufs zusammen.

    Bewusst **ohne Zeitstempel und ohne Laufzeit**: Derselbe Lauf soll byteweise
    dasselbe Manifest erzeugen (Architekturregel A2).
    """
    return {
        "run_id": ergebnis.run_id,
        "erzeugt_von": "scripts/inject.py",
        "faktorstufen": {
            "serie": optionen.serie,
            "design": optionen.design,
            "klasse": optionen.klasse,
            "fehlerrate": optionen.rate,
            "wiederholung": optionen.wdh,
        },
        "klassen_gewichte": dict(sorted(_gewichte(optionen.klasse).items())),
        "seeds": dict(sorted(ergebnis.seeds.items())),
        "clean_datensatz": {"herkunft": herkunft, "zeilen": dict(sorted(zeilen.items()))},
        "zelluniversum": dict(sorted(ergebnis.universum.items())),
        "einheit_je_klasse": dict(sorted(ergebnis.einheit_je_klasse.items())),
        "angefordert_je_klasse": dict(sorted(ergebnis.ziel_je_klasse.items())),
        "injiziert_je_klasse": dict(sorted(ergebnis.fehler_je_klasse.items())),
        "injiziert_je_variante": dict(sorted(ergebnis.fehler_je_variante.items())),
        "mitgezogene_zellen": ergebnis.mitgezogene_zellen,
        "logzeilen": {
            "error_log": len(ergebnis.error_log),
            "error_log_records": len(ergebnis.error_log_records),
        },
        "sha256": {
            "df_clean": dict(sorted(hashes_clean.items())),
            "df_dirty": dict(sorted(hashes_dirty.items())),
        },
        "gegencheck_sauber": gegencheck_sauber,
        "konfiguration": konfiguration_als_dict(config),
    }


def _schreibe_json(pfad: Path, inhalt: Mapping[str, Any]) -> None:
    """Schreibt eine JSON-Datei mit fester Formatierung."""
    pfad.write_text(
        json.dumps(inhalt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _argumente() -> argparse.ArgumentParser:
    """Baut den Argumentparser des Skripts."""
    parser = argparse.ArgumentParser(
        description="Verfaelscht einen sauberen Datensatz kontrolliert und protokolliert alles."
    )
    parser.add_argument("--config", type=Path, default=None, help="Pfad zur Konfigurationsdatei")
    parser.add_argument("--serie", required=True, help="Name der Versuchsserie, etwa s01")
    parser.add_argument("--design", required=True, help="Kennbuchstabe des Varianzdesigns")
    parser.add_argument(
        "--klasse",
        required=True,
        help=f"Fehlerklasse F1 bis F8, HO1, HO2 oder {MISCHMODUS!r} fuer den Mischmodus",
    )
    parser.add_argument("--rate", type=float, required=True, help="Fehlerrate als Anteil")
    parser.add_argument("--wdh", type=int, required=True, help="Nummer der Wiederholung")
    parser.add_argument(
        "--clean-run",
        default=None,
        help="Kennung eines erzeugten Laufs; ohne Angabe wird der saubere Datensatz erzeugt",
    )
    parser.add_argument("--seed", type=int, default=None, help="Master-Seed uebersteuern")
    parser.add_argument(
        "--n-anfragen", type=int, default=None, help="Anzahl der Anfragen uebersteuern"
    )
    parser.add_argument(
        "--behalten",
        action="store_true",
        help="Legt df_raw_dirty zusaetzlich je Entitaet unter dirty/ ab",
    )
    parser.add_argument("--still", action="store_true", help="Keine Fortschrittsausgabe")
    return parser


def main(argumente: Sequence[str] | None = None) -> int:
    """Einstiegspunkt des Skripts.

    Args:
        argumente: Kommandozeilenargumente; ``None`` nimmt ``sys.argv``.

    Returns:
        ``0``, wenn der Gegencheck sauber durchlief, sonst ``1``. Eine Abweichung
        im Ground Truth ist ein Abbruchgrund, kein Hinweis: Auf ihr beruht jede
        spaeter berichtete Kennzahl.
    """
    optionen = _argumente().parse_args(argumente)

    config = lade_config(optionen.config)
    if optionen.seed is not None:
        config = dataclasses.replace(config, master_seed=optionen.seed)
    if optionen.n_anfragen is not None:
        config = dataclasses.replace(config, n_anfragen=optionen.n_anfragen)

    run_id = experiment_run_id(
        optionen.serie, optionen.design, optionen.klasse, optionen.rate, optionen.wdh
    )
    ziel = experiment_verzeichnis(
        config,
        optionen.serie,
        optionen.design,
        optionen.klasse,
        optionen.rate,
        optionen.wdh,
        anlegen=True,
    )
    if not optionen.still:
        print(f"Injektion (run_id={run_id}, klasse={optionen.klasse}, rate={optionen.rate})")

    beginn = time.perf_counter()
    daten_clean, herkunft = _lade_clean(config, optionen.clean_run)
    ergebnis = injiziere(
        daten_clean,
        optionen.rate,
        _gewichte(optionen.klasse),
        _seed_inject(config, optionen),
        run_id,
        config=config,
    )
    dauer = time.perf_counter() - beginn

    bericht = pruefe_ground_truth(
        daten_clean, ergebnis.df_raw_dirty, ergebnis.error_log, ergebnis.error_log_records
    )

    hashes_clean = {name: sha256_dataframe(daten_clean[name]) for name in ENTITAETEN}
    hashes_dirty = {name: sha256_dataframe(ergebnis.df_raw_dirty[name]) for name in ENTITAETEN}

    ergebnis.error_log.to_parquet(ziel / Artefakt.ERROR_LOG.value, index=False)
    ergebnis.error_log_records.to_parquet(ziel / Artefakt.ERROR_LOG_RECORDS.value, index=False)
    (ziel / Artefakt.CONFIG.value).write_text(
        yaml.safe_dump(
            {
                "lauf": {
                    "run_id": run_id,
                    "serie": optionen.serie,
                    "design": optionen.design,
                    "klasse": optionen.klasse,
                    "fehlerrate": optionen.rate,
                    "wiederholung": optionen.wdh,
                    "klassen_gewichte": dict(sorted(_gewichte(optionen.klasse).items())),
                    "seeds": dict(sorted(ergebnis.seeds.items())),
                    "clean_datensatz": herkunft,
                },
                "konfiguration": konfiguration_als_dict(config),
            },
            allow_unicode=True,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )
    _schreibe_json(
        ziel / Artefakt.MANIFEST.value,
        _manifest(
            optionen=optionen,
            config=config,
            ergebnis=ergebnis,
            herkunft=herkunft,
            zeilen={name: len(daten_clean[name]) for name in ENTITAETEN},
            hashes_clean=hashes_clean,
            hashes_dirty=hashes_dirty,
            gegencheck_sauber=bericht.sauber,
        ),
    )

    if optionen.behalten:
        verzeichnis = ziel / DIRTY
        verzeichnis.mkdir(parents=True, exist_ok=True)
        for name in ENTITAETEN:
            ergebnis.df_raw_dirty[name].to_parquet(verzeichnis / f"{name}.parquet", index=False)

    berichtspfad = schreibe_bericht(
        bericht,
        config.pfade.results / _GEGENCHECK,
        run_id=run_id,
        zusatz={
            "klasse": optionen.klasse,
            "fehlerrate": optionen.rate,
            "zelluniversum": dict(sorted(ergebnis.universum.items())),
            "injiziert_je_klasse": dict(sorted(ergebnis.fehler_je_klasse.items())),
        },
    )

    if not optionen.still:
        _zeige(ergebnis, dauer, sauber=bericht.sauber)
        print(f"\nArtefakte in {ziel}")
        print(f"Gegencheck in {berichtspfad}")
    return 0 if bericht.sauber else 1


def _zeige(ergebnis: Injektionsergebnis, dauer: float, *, sauber: bool) -> None:
    """Gibt die Kernzahlen des Laufs aus."""
    for klasse, universum in sorted(ergebnis.universum.items()):
        einheit = ergebnis.einheit_je_klasse[klasse]
        print(
            f"  {klasse:<4} Universum {universum:>8} {einheit}n, "
            f"injiziert {ergebnis.fehler_je_klasse.get(klasse, 0):>6}"
        )
    print(f"  Logzeilen zellbasiert {len(ergebnis.error_log)}")
    print(f"  Logzeilen satzbasiert {len(ergebnis.error_log_records)}")
    print(f"  davon mitgezogen      {ergebnis.mitgezogene_zellen}")
    print(f"  Laufzeit              {dauer:.1f} s")
    print("\nGegencheck: " + ("ohne Abweichung." if sauber else "ABWEICHUNG — siehe Bericht."))


if __name__ == "__main__":
    raise SystemExit(main())
