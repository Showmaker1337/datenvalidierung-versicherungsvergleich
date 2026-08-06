"""Exportiert den Regelkatalog als CSV fuer den Anhang der Arbeit.

Aufruf::

    python scripts/export_katalog.py

Erzeugt ``results/regelkatalog.csv`` aus den Metadaten der 58 Regeln. **Diese
Datei geht direkt in den Anhang** — sie ist die Mapping-Tabelle in Kurzform:

    Literaturbeleg -> Taxonomieklasse (A/B/C) -> Regel-ID -> Injektionsvariante
    -> Auswertungsklasse

Die Spalte "Injektionsvariante" kommt erst nach Phase 4 hinzu; bis dahin endet die
Kette bei der Regel-ID.

Der Export liest ausschliesslich die Metadaten aus ``src/rules/katalog.py``. Damit
kann die Anhangstabelle nicht von der Implementierung abweichen — sie ist deren
Abbild, keine gepflegte Zweitschrift.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ermoeglicht den Aufruf "python scripts/export_katalog.py" ohne editierbare
# Installation. Muss vor den Projektimporten stehen.
_WURZEL = Path(__file__).resolve().parents[1]
if str(_WURZEL) not in sys.path:
    sys.path.insert(0, str(_WURZEL))

import argparse  # noqa: E402
import csv  # noqa: E402
from typing import TYPE_CHECKING, Final  # noqa: E402

from src.common.config import lade_config  # noqa: E402
from src.rules.katalog import alle_regeln  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    from src.rules.modell import Regel

__all__ = ["SPALTEN", "main", "zeile"]

#: Dateiname des Exports unter ``results/``.
_DATEI: Final[str] = "regelkatalog.csv"

#: Kopfzeile der Anhangstabelle.
SPALTEN: Final[tuple[str, ...]] = (
    "regel_id",
    "beschreibung",
    "entitaet",
    "spalten",
    "granularitaet_a",
    "fehlerklasse_b",
    "erkennbarkeit_c",
    "schweregrad",
    "literatur",
    "fachliche_grundlage",
    "schicht",
    "in_zellmetrik",
)

#: Platzhalter fuer "alle Felder der Entitaet" in der Spalte ``spalten`` (R-025).
_ALLE_FELDER: Final[str] = "*"


def zeile(regel: Regel) -> dict[str, str]:
    """Bildet eine Regel auf ihre Zeile in der Anhangstabelle ab.

    Args:
        regel: Die zu exportierende Regel.

    Returns:
        Eine Abbildung Spaltenname auf Zeichenkette. Mehrwertige Felder werden mit
        Semikolon getrennt — ein Komma waere im CSV die zweite Trennebene und in
        einer Tabellenkalkulation kaum lesbar.
    """
    spalten = (
        "alle Felder der Entitaet"
        if regel.spalten == (_ALLE_FELDER,)
        else "; ".join(regel.spalten)
    )
    return {
        "regel_id": regel.regel_id,
        "beschreibung": regel.beschreibung,
        "entitaet": regel.entitaet,
        "spalten": spalten,
        "granularitaet_a": regel.granularitaet,
        "fehlerklasse_b": regel.fehlerklasse_b,
        "erkennbarkeit_c": regel.erkennbarkeit_c,
        "schweregrad": regel.schweregrad,
        "literatur": "; ".join(regel.literatur),
        "fachliche_grundlage": regel.fachliche_grundlage,
        "schicht": regel.schicht.value,
        "in_zellmetrik": "ja" if regel.in_zellmetrik else "nein",
    }


def main(argumente: Sequence[str] | None = None) -> int:
    """Einstiegspunkt des Skripts.

    Args:
        argumente: Kommandozeilenargumente; ``None`` nimmt ``sys.argv``.

    Returns:
        Den Rueckgabewert des Prozesses.
    """
    parser = argparse.ArgumentParser(
        description="Exportiert den Regelkatalog als CSV fuer den Anhang der Arbeit."
    )
    parser.add_argument("--config", type=Path, default=None, help="Pfad zur Konfigurationsdatei")
    parser.add_argument("--ziel", type=Path, default=None, help="Zielverzeichnis")
    parser.add_argument("--still", action="store_true", help="Keine Fortschrittsausgabe")
    optionen = parser.parse_args(argumente)

    config = lade_config(optionen.config)
    verzeichnis = optionen.ziel if optionen.ziel is not None else config.pfade.results
    verzeichnis.mkdir(parents=True, exist_ok=True)
    pfad = verzeichnis / _DATEI

    regeln = alle_regeln()
    with pfad.open("w", encoding="utf-8", newline="") as datei:
        schreiber = csv.DictWriter(datei, fieldnames=list(SPALTEN), lineterminator="\n")
        schreiber.writeheader()
        for regel in regeln:
            schreiber.writerow(zeile(regel))

    if not optionen.still:
        hart = sum(1 for regel in regeln if regel.schweregrad == "HART")
        print(f"{len(regeln)} Regeln exportiert nach {pfad}")
        print(f"  davon HART {hart}, WARNUNG {len(regeln) - hart}")
        for gruppe in ("G1", "G2", "G3", "G4", "G5"):
            anzahl = sum(1 for regel in regeln if regel.granularitaet == gruppe)
            print(f"  {gruppe}: {anzahl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
