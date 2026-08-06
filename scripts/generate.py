"""Erzeugt den sauberen Datensatz eines Laufs unter ``data/runs/<run_id>/clean``.

Aufruf::

    python scripts/generate.py --config config/default.yaml --run-id lauf01
    python scripts/generate.py --run-id probe --n-anfragen 500 --still

Geschrieben werden je Entitaet zwei Parquet-Dateien — ``typed/<entitaet>.parquet``
und ``raw/<entitaet>.parquet`` — sowie ``manifest.json`` mit Zeilenzahlen,
Hashwerten, Seeds und der vollstaendigen Konfiguration.

Zwei Laeufe mit derselben ``run_id`` und derselben Konfiguration erzeugen
bitgleiche Dateien; das prueft ``tests/test_reproduzierbarkeit.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ermoeglicht den Aufruf "python scripts/generate.py" ohne editierbare
# Installation. Muss vor den Projektimporten stehen.
_WURZEL = Path(__file__).resolve().parents[1]
if str(_WURZEL) not in sys.path:
    sys.path.insert(0, str(_WURZEL))

import argparse  # noqa: E402
import dataclasses  # noqa: E402
import time  # noqa: E402
from typing import TYPE_CHECKING  # noqa: E402

from src.common.config import lade_config  # noqa: E402
from src.common.seeding import wurzel_seeds  # noqa: E402
from src.generator.pipeline import erzeuge_datensatz, schreibe_datensatz  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

__all__ = ["main"]


def main(argumente: Sequence[str] | None = None) -> int:
    """Einstiegspunkt des Skripts.

    Args:
        argumente: Kommandozeilenargumente; ``None`` nimmt ``sys.argv``.

    Returns:
        Den Rueckgabewert des Prozesses.
    """
    parser = argparse.ArgumentParser(
        description="Erzeugt den sauberen Datensatz eines Laufs deterministisch."
    )
    parser.add_argument("--config", type=Path, default=None, help="Pfad zur Konfigurationsdatei")
    parser.add_argument("--run-id", required=True, help="Kennung des Laufs")
    parser.add_argument("--seed", type=int, default=None, help="Master-Seed uebersteuern")
    parser.add_argument(
        "--n-anfragen", type=int, default=None, help="Anzahl der Anfragen uebersteuern"
    )
    parser.add_argument("--still", action="store_true", help="Keine Fortschrittsausgabe")
    optionen = parser.parse_args(argumente)

    config = lade_config(optionen.config)
    if optionen.seed is not None:
        config = dataclasses.replace(config, master_seed=optionen.seed)
    if optionen.n_anfragen is not None:
        config = dataclasses.replace(config, n_anfragen=optionen.n_anfragen)

    seed_basis = wurzel_seeds(config.master_seed).basis
    if not optionen.still:
        print(
            f"Datensatz wird erzeugt (run_id={optionen.run_id}, "
            f"master_seed={config.master_seed}, n_anfragen={config.n_anfragen})"
        )

    beginn = time.perf_counter()
    datensatz = erzeuge_datensatz(config, seed_basis)
    dauer = time.perf_counter() - beginn
    ziel = schreibe_datensatz(config, optionen.run_id, datensatz, seed_basis)

    if not optionen.still:
        for name, rahmen in datensatz.items():
            print(f"  {name:<16} {len(rahmen):>8} Zeilen")
        print(f"Erzeugung in {dauer:.1f} s. Geschrieben nach {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
