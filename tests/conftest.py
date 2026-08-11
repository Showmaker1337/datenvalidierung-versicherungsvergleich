"""Gemeinsame Vorrichtungen der Testsuite."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from src.common.config import lade_config
from src.common.seeding import wurzel_seeds
from src.common.serialisierung import ENTITAETEN, serialisiere
from src.generator.pipeline import erzeuge_datensatz

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    import pandas as pd

    from src.common.config import Config

#: Wurzelverzeichnis des Repositories.
WURZEL = Path(__file__).resolve().parents[1]

#: Anfragezahl der Injektionstests.
#:
#: Klein genug fuer die Laufzeit, gross genug, dass jede der sechzig Varianten
#: Kandidaten findet — auch die seltenen wie F2-a, das eine fuehrende Null in der
#: Postleitzahl voraussetzt.
INJEKTOR_ANFRAGEN = 400


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


@pytest.fixture(scope="session")
def config_injektor(config: Config, referenzverzeichnis: Path) -> Config:
    """Die Konfiguration der Injektionstests mit verkleinertem Datensatz."""
    assert referenzverzeichnis.is_dir()
    return dataclasses.replace(config, n_anfragen=INJEKTOR_ANFRAGEN)


@pytest.fixture(scope="session")
def daten_clean(config_injektor: Config) -> dict[str, pd.DataFrame]:
    """Die Rohschicht eines sauberen Datensatzes — Eingabe des Injektors.

    Der Injektor arbeitet ausschliesslich auf ``df_raw``; die typisierte Schicht
    braucht er nicht und darf sie auch nicht bekommen (spec/01, Abschnitt 6).
    """
    typisiert = erzeuge_datensatz(
        config_injektor, wurzel_seeds(config_injektor.master_seed).basis
    )
    return {name: serialisiere(typisiert[name]) for name in ENTITAETEN}
