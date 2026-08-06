"""Gemeinsame Vorrichtungen der Testsuite."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from src.common.config import lade_config

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from src.common.config import Config

#: Wurzelverzeichnis des Repositories.
WURZEL = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def config() -> Config:
    """Die ausgelieferte Konfiguration."""
    return lade_config()


@pytest.fixture(scope="session")
def referenzverzeichnis(config: Config) -> Path:
    """Verzeichnis der versionierten Referenztabellen.

    Ueberspringt die abhaengigen Tests mit klarer Meldung, wenn die
    Referenzdaten noch nicht erzeugt wurden.
    """
    verzeichnis = config.pfade.reference
    if not verzeichnis.is_dir():
        pytest.skip(
            f"Referenzdaten fehlen unter {verzeichnis}. "
            "Einmalig 'python scripts/build_reference.py' ausfuehren."
        )
    return verzeichnis
