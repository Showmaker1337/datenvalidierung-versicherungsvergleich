"""Fuehrt den Regelkatalog auf einem Datensatz aus.

Aufruf::

    python scripts/validate.py --run-id lauf01 --dataset clean

Der **Clean-Baseline-Lauf** ist die fuenfte Protokollregel aus
``spec/03_fehlerklassen.md``, Abschnitt 5: Der vollstaendige Katalog laeuft auf
``df_clean``, und die Erwartung ist **null Meldungen**. Jede Meldung ist entweder
ein Generatorfehler — der Generator erzeugt selbst ungueltige Daten — oder eine zu
streng formulierte Regel. Beides muss vor dem Freeze behoben sein.

Die dabei gemessene False-Positive-Rate **gehoert in die Arbeit**. Sie ist der
Beleg dafuer, dass die Grundannahme "alles nicht Injizierte ist sauber" ueberhaupt
traegt. Ohne diese Zahl ist jede spaeter berichtete Precision unbelegt.

Geschrieben werden ``results/clean_baseline.json`` sowie unter
``data/runs/<run_id>/clean/`` die Rohtreffer, die Vereinigungsmenge markierter
Zellen, die satzbezogenen Befunde und ``rule_timing.json``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ermoeglicht den Aufruf "python scripts/validate.py" ohne editierbare
# Installation. Muss vor den Projektimporten stehen.
_WURZEL = Path(__file__).resolve().parents[1]
if str(_WURZEL) not in sys.path:
    sys.path.insert(0, str(_WURZEL))

import argparse  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from typing import TYPE_CHECKING  # noqa: E402

from src.common.config import lade_config  # noqa: E402
from src.common.pfade import Schicht  # noqa: E402
from src.common.serialisierung import ENTITAETEN  # noqa: E402
from src.rules.engine import lade_kontext, pruefe_alles, schreibe_detektionen  # noqa: E402
from src.rules.katalog import alle_regeln  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    from src.rules.engine import Detektionen
    from src.rules.modell import Kontext

__all__ = ["baue_bericht", "main"]

#: Derzeit gueltige Datensaetze. ``dirty`` entsteht erst nach dem Freeze (Phase 4).
_DATENSAETZE: tuple[str, ...] = ("clean",)

#: Dateiname des Berichts unter ``results/``.
_BERICHT: str = "clean_baseline.json"


def _zelluniversum(kontext: Kontext) -> dict[str, int]:
    """Zaehlt die adressierbaren Zellen je Entitaet auf der Rohschicht.

    Bezugsgroesse der False-Positive-Rate. Gezaehlt wird auf der Rohschicht, weil
    beide Schichten dieselbe Zellmenge haben und die Rohschicht die Sicht ist, auf
    der der Injektor spaeter arbeitet.
    """
    universum: dict[str, int] = {}
    for entitaet in ENTITAETEN:
        rahmen = kontext.rahmen(Schicht.RAW, entitaet)
        universum[entitaet] = int(len(rahmen) * len(rahmen.columns))
    return universum


def baue_bericht(kontext: Kontext, detektionen: Detektionen, run_id: str) -> dict[str, object]:
    """Stellt den Bericht des Clean-Baseline-Laufs zusammen.

    Args:
        kontext: Geprueter Kontext.
        detektionen: Ergebnis des Katalogdurchlaufs.
        run_id: Kennung des Laufs.

    Returns:
        Ein JSON-faehiges Abbildungsobjekt. Bewusst **ohne Zeitstempel**: Der
        Bericht soll bei gleichem Lauf byteweise gleich sein.
    """
    universum = _zelluniversum(kontext)
    zellen_gesamt = sum(universum.values())
    markierte = len(detektionen.markierte_zellen)
    regeln = alle_regeln()

    return {
        "run_id": run_id,
        "datensatz": "clean",
        "regeln_gesamt": len(regeln),
        "meldungen_gesamt": detektionen.anzahl_meldungen,
        "satzbefunde_gesamt": detektionen.anzahl_saetze,
        "markierte_zellen": markierte,
        "zellen_gesamt": zellen_gesamt,
        "false_positive_rate_zellen": (markierte / zellen_gesamt) if zellen_gesamt else 0.0,
        "regeln_mit_meldungen": sorted(
            regel_id
            for regel_id, anzahl in detektionen.meldungen_je_regel.items()
            if anzahl > 0
        ),
        "regeln_mit_satzbefunden": sorted(
            regel_id for regel_id, anzahl in detektionen.saetze_je_regel.items() if anzahl > 0
        ),
        "meldungen_je_regel": dict(sorted(detektionen.meldungen_je_regel.items())),
        "satzbefunde_je_regel": dict(sorted(detektionen.saetze_je_regel.items())),
        "zeilen_je_entitaet": {
            entitaet: len(kontext.rahmen(Schicht.RAW, entitaet)) for entitaet in ENTITAETEN
        },
        "zellen_je_entitaet": universum,
    }


def _zeige(bericht: dict[str, object], detektionen: Detektionen, dauer: float) -> None:
    """Gibt die Kernzahlen des Laufs aus."""
    print(f"Regeln ausgefuehrt      {bericht['regeln_gesamt']}")
    print(f"Zellmeldungen           {bericht['meldungen_gesamt']}")
    print(f"Satzbefunde             {bericht['satzbefunde_gesamt']}")
    print(f"Markierte Zellen        {bericht['markierte_zellen']} von {bericht['zellen_gesamt']}")
    print(f"False-Positive-Rate     {bericht['false_positive_rate_zellen']:.3e}")
    print(f"Laufzeit                {dauer:.1f} s")

    auffaellig = [
        (regel_id, anzahl)
        for regel_id, anzahl in sorted(detektionen.meldungen_je_regel.items())
        if anzahl > 0
    ]
    satzauffaellig = [
        (regel_id, anzahl)
        for regel_id, anzahl in sorted(detektionen.saetze_je_regel.items())
        if anzahl > 0
    ]
    if not auffaellig and not satzauffaellig:
        print("\nNull Meldungen auf dem sauberen Datensatz — die Erwartung ist erfuellt.")
        return
    print("\nMeldungen je Regel (Erwartung ist null):")
    for regel_id, anzahl in auffaellig:
        print(f"  {regel_id}  {anzahl:>8} Zellmeldungen")
    for regel_id, anzahl in satzauffaellig:
        print(f"  {regel_id}  {anzahl:>8} Satzbefunde")


def main(argumente: Sequence[str] | None = None) -> int:
    """Einstiegspunkt des Skripts.

    Args:
        argumente: Kommandozeilenargumente; ``None`` nimmt ``sys.argv``.

    Returns:
        ``0``, wenn der Lauf durchlief. Der Rueckgabewert sagt **nichts** ueber die
        Zahl der Meldungen aus — sie steht im Bericht und ist dort die eigentliche
        Kennzahl.
    """
    parser = argparse.ArgumentParser(
        description="Fuehrt den vollstaendigen Regelkatalog auf einem Datensatz aus."
    )
    parser.add_argument("--config", type=Path, default=None, help="Pfad zur Konfigurationsdatei")
    parser.add_argument("--run-id", required=True, help="Kennung des Laufs")
    parser.add_argument(
        "--dataset",
        default="clean",
        choices=_DATENSAETZE,
        help="Zu pruefender Datensatz. 'dirty' entsteht erst nach dem Freeze (Phase 4).",
    )
    parser.add_argument("--still", action="store_true", help="Keine Fortschrittsausgabe")
    optionen = parser.parse_args(argumente)

    config = lade_config(optionen.config)
    if not optionen.still:
        print(f"Regelkatalog wird geprueft (run_id={optionen.run_id}, dataset={optionen.dataset})")

    kontext = lade_kontext(config, optionen.run_id)
    beginn = time.perf_counter()
    detektionen = pruefe_alles(kontext)
    dauer = time.perf_counter() - beginn

    ziel = schreibe_detektionen(config, optionen.run_id, detektionen, unterordner=optionen.dataset)
    bericht = baue_bericht(kontext, detektionen, optionen.run_id)

    config.pfade.results.mkdir(parents=True, exist_ok=True)
    berichtspfad = config.pfade.results / _BERICHT
    berichtspfad.write_text(
        json.dumps(bericht, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    if not optionen.still:
        _zeige(bericht, detektionen, dauer)
        print(f"\nArtefakte in {ziel}")
        print(f"Bericht in    {berichtspfad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
