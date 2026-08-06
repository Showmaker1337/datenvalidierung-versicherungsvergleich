"""Einstiegspunkt des Prototyps.

Aufruf::

    python -m src.cli config
    python -m src.cli referenz [--ziel VERZEICHNIS] [--seed ZAHL]
    python -m src.cli generieren --run-id KENNUNG [--seed ZAHL] [--n-anfragen ZAHL]
    python -m src.cli pruefen --run-id KENNUNG
    python -m src.cli katalog [--ziel VERZEICHNIS]

Der Befehlsvorrat waechst mit den Phasen mit. Er enthaelt ausschliesslich
Befehle, die es wirklich gibt — kein Platzhalter fuer noch nicht gebaute Phasen
(CLAUDE.md, Abschnitt 7).
"""

from __future__ import annotations

import argparse
import dataclasses
from pathlib import Path
from typing import TYPE_CHECKING

from src.common.config import lade_config
from src.common.pfade import REFERENZ_DATEIEN, sha256_datei

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    from src.common.config import Config

__all__ = ["main"]


def _zeige_config(config: Config) -> None:
    """Gibt die geladene Konfiguration und den Zustand der Referenzdaten aus."""
    print(f"Quelldatei              {config.quelldatei}")
    print(f"Stichtag                {config.stichtag.isoformat()}")
    print(f"Master-Seed             {config.master_seed}")
    print(f"Anfragen je Lauf        {config.n_anfragen}")
    print(
        "Angebote je Anfrage     "
        f"{config.angebote_je_anfrage.minimum} bis {config.angebote_je_anfrage.maximum}"
    )
    verteilung = ", ".join(
        f"{sparte}={gewicht:.2f}" for sparte, gewicht in config.sparten_verteilung.items()
    )
    print(f"Spartenverteilung       {verteilung}")
    print(f"Referenzdaten           {config.pfade.reference}")
    print(f"Laufartefakte           {config.pfade.runs}")
    print(f"Ergebnisse              {config.pfade.results}")
    print()
    print("Referenztabellen:")
    for name in REFERENZ_DATEIEN:
        pfad = config.pfade.reference / name
        zustand = sha256_datei(pfad)[:16] if pfad.is_file() else "fehlt"
        print(f"  {name:<24} {zustand}")


def _baue_referenz(config: Config, ziel: Path | None) -> None:
    """Erzeugt die Referenztabellen neu.

    Die Erzeugung steht in ``scripts/build_reference.py`` und wird von hier nur
    aufgerufen. Die Kommandozeile ist die aeusserste Schicht und darf die
    Phasenskripte kennen; umgekehrt gilt das nicht. Doppelter Code waere hier
    die schlechtere Loesung, weil die Referenzdaten dann zwei Erzeugungswege
    haetten.
    """
    from scripts.build_reference import baue_referenzdaten  # noqa: PLC0415

    verzeichnis = ziel if ziel is not None else config.pfade.reference
    print(f"Referenzdaten werden erzeugt (master_seed={config.master_seed}) nach {verzeichnis}")
    baue_referenzdaten(config, verzeichnis)


def _erzeuge_datensatz(config: Config, run_id: str) -> None:
    """Erzeugt den sauberen Datensatz eines Laufs.

    Die Erzeugung steht in ``scripts/generate.py`` und wird von hier nur
    aufgerufen — dieselbe Begruendung wie bei :func:`_baue_referenz`.
    """
    from scripts.generate import main as generieren  # noqa: PLC0415

    generieren(["--run-id", run_id, "--seed", str(config.master_seed),
                "--n-anfragen", str(config.n_anfragen)])


def _pruefe_datensatz(run_id: str) -> None:
    """Fuehrt den Regelkatalog auf dem sauberen Datensatz eines Laufs aus."""
    from scripts.validate import main as pruefen  # noqa: PLC0415

    pruefen(["--run-id", run_id, "--dataset", "clean"])


def _exportiere_katalog(ziel: Path | None) -> None:
    """Exportiert den Regelkatalog als CSV fuer den Anhang der Arbeit."""
    from scripts.export_katalog import main as exportieren  # noqa: PLC0415

    exportieren(["--ziel", str(ziel)] if ziel is not None else [])


def main(argumente: Sequence[str] | None = None) -> int:
    """Einstiegspunkt der Kommandozeile.

    Args:
        argumente: Kommandozeilenargumente; ``None`` nimmt ``sys.argv``.

    Returns:
        Den Rueckgabewert des Prozesses.
    """
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="Prototyp zur regelbasierten Datenvalidierung in Vergleichssystemen",
    )
    parser.add_argument("--config", type=Path, default=None, help="Pfad zur Konfigurationsdatei")
    unterbefehle = parser.add_subparsers(dest="befehl", required=True)

    unterbefehle.add_parser("config", help="Geladene Konfiguration und Referenzdaten anzeigen")

    referenz = unterbefehle.add_parser("referenz", help="Referenztabellen deterministisch erzeugen")
    referenz.add_argument("--ziel", type=Path, default=None, help="Zielverzeichnis")
    referenz.add_argument("--seed", type=int, default=None, help="Master-Seed uebersteuern")

    erzeugen = unterbefehle.add_parser("generieren", help="Sauberen Datensatz eines Laufs erzeugen")
    erzeugen.add_argument("--run-id", required=True, help="Kennung des Laufs")
    erzeugen.add_argument("--seed", type=int, default=None, help="Master-Seed uebersteuern")
    erzeugen.add_argument(
        "--n-anfragen", type=int, default=None, help="Anzahl der Anfragen uebersteuern"
    )

    pruefen = unterbefehle.add_parser(
        "pruefen", help="Regelkatalog auf dem sauberen Datensatz eines Laufs ausfuehren"
    )
    pruefen.add_argument("--run-id", required=True, help="Kennung des Laufs")

    katalog = unterbefehle.add_parser(
        "katalog", help="Regelkatalog als CSV fuer den Anhang exportieren"
    )
    katalog.add_argument("--ziel", type=Path, default=None, help="Zielverzeichnis")

    optionen = parser.parse_args(argumente)
    config = lade_config(optionen.config)

    if optionen.befehl == "config":
        _zeige_config(config)
        return 0

    if optionen.befehl == "pruefen":
        _pruefe_datensatz(optionen.run_id)
        return 0

    if optionen.befehl == "katalog":
        _exportiere_katalog(optionen.ziel)
        return 0

    if optionen.seed is not None:
        config = dataclasses.replace(config, master_seed=optionen.seed)

    if optionen.befehl == "generieren":
        if optionen.n_anfragen is not None:
            config = dataclasses.replace(config, n_anfragen=optionen.n_anfragen)
        _erzeuge_datensatz(config, optionen.run_id)
        return 0

    _baue_referenz(config, optionen.ziel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
