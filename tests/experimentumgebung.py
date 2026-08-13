"""Gemeinsame Vorrichtung der Experimenttests: temporaere Konfiguration und Plan.

Die Tests duerfen weder in ``data/runs`` noch in ``results`` schreiben — ein
Testlauf, der die echten Laufartefakte anfasst, koennte eine gerechnete Serie
beschaedigen, und ein Test, der auf ihr aufbaut, waere je nach Zustand des
Arbeitsverzeichnisses gruen oder rot.

:func:`baue_umgebung` schreibt deshalb eine eigene ``default.yaml`` mit
**absoluten** Pfaden unterhalb des Testverzeichnisses. Die Referenztabellen
bleiben die echten: Sie sind versioniert, gehoeren zum Repository und wuerden bei
einer Neuerzeugung nur Zeit kosten.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

from src.common.config import STANDARD_KONFIGURATION

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence
    from pathlib import Path

__all__ = ["baue_plan", "baue_umgebung", "mini_plan"]


def baue_umgebung(verzeichnis: Path) -> Path:
    """Schreibt eine Konfiguration, die in ein Testverzeichnis schreibt.

    Args:
        verzeichnis: Zielverzeichnis, ueblicherweise ``tmp_path``.

    Returns:
        Den Pfad der geschriebenen Konfigurationsdatei.
    """
    rohdaten = yaml.safe_load(STANDARD_KONFIGURATION.read_text(encoding="utf-8"))
    wurzel = STANDARD_KONFIGURATION.resolve().parents[1]
    rohdaten["pfade"] = {
        "reference": str(wurzel / rohdaten["pfade"]["reference"]),
        "runs": str(verzeichnis / "runs"),
        "results": str(verzeichnis / "results"),
    }
    pfad = verzeichnis / "default.yaml"
    pfad.write_text(
        yaml.safe_dump(rohdaten, allow_unicode=True, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    return pfad


def baue_plan(verzeichnis: Path, inhalt: Mapping[str, Any], name: str = "plan.yaml") -> Path:
    """Schreibt einen Versuchsplan in ein Testverzeichnis.

    Args:
        verzeichnis: Zielverzeichnis.
        inhalt: Der Plan als Woerterbuch.
        name: Dateiname.

    Returns:
        Den Pfad der geschriebenen Datei.
    """
    pfad = verzeichnis / name
    pfad.write_text(
        yaml.safe_dump(dict(inhalt), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )
    return pfad


def mini_plan(  # noqa: PLR0913 - jede Angabe ist eine Faktorstufe des Plans
    *,
    serie: str = "t",
    klassen: Sequence[str] = ("F3", "F4"),
    raten: Sequence[float] = (0.01, 0.02),
    verfahren: Sequence[str] = ("prototyp", "B0"),
    wiederholungen: int = 3,
    n_anfragen: int = 200,
    mit_teilversuchen: bool = False,
) -> dict[str, Any]:
    """Baut den Plan eines Mini-Experiments.

    Vorgabe ist der im Phasenprompt genannte Zuschnitt: zwei Fehlerklassen, zwei
    Ratenstufen, zwei Verfahren, drei Wiederholungen.

    Args:
        serie: Name der Versuchsserie.
        klassen: Fehlerklassen.
        raten: Fehlerraten.
        verfahren: Verfahren.
        wiederholungen: Zahl der Wiederholungen.
        n_anfragen: Groesse des Basisdatensatzes.
        mit_teilversuchen: Ergaenzt einen Varianten- und einen Datenvarianzblock.

    Returns:
        Den Plan als Woerterbuch.
    """
    teilversuche: list[dict[str, Any]] = []
    if mit_teilversuchen:
        teilversuche = [
            {
                "kennung": "T5",
                "titel": "Datenvarianz",
                "design": "D",
                "modus": "klasse",
                "gruppen": [klassen[0]],
                "raten": [raten[0]],
                "verfahren": ["prototyp"],
                "wiederholungen": 2,
                "n_anfragen": n_anfragen,
                "basis_variiert": True,
                "max_fehler": None,
                "messe_speicher": False,
            },
            {
                "kennung": "T6",
                "titel": "Variantencharakterisierung",
                "design": "V",
                "modus": "variante",
                "gruppen": ["F3-a", "F4-f"],
                "raten": [1.0],
                "verfahren": ["prototyp"],
                "wiederholungen": 1,
                "n_anfragen": n_anfragen,
                "basis_variiert": False,
                "max_fehler": 25,
                "messe_speicher": True,
            },
        ]
    return {
        "serie": serie,
        "worker": 2,
        "schreibe_detections": False,
        "statistik": {"alpha": 0.05, "bootstrap_resamples": 200, "seed_bootstrap": 7},
        "hauptversuch": {
            "kennung": "haupt",
            "titel": "Mini-Hauptversuch",
            "design": "A",
            "modus": "klasse",
            "gruppen": list(klassen),
            "raten": [float(rate) for rate in raten],
            "verfahren": list(verfahren),
            "wiederholungen": wiederholungen,
            "n_anfragen": n_anfragen,
            "basis_variiert": False,
            "max_fehler": None,
            "messe_speicher": False,
        },
        "teilversuche": teilversuche,
    }
