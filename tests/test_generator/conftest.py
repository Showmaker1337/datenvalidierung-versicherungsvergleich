"""Vorrichtungen der Generatortests.

Der Datensatz wird **einmal je Testlauf** erzeugt und von allen Tests geteilt.
Zweitausend Anfragen sind der Kompromiss: gross genug, dass auch die kleinste
ZUERS-Zone besetzt ist (0,4 Prozent von 600 Hausratzeilen), klein genug fuer eine
Laufzeit im Sekundenbereich.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import pytest

from src.common.referenz import lade_alle
from src.common.seeding import wurzel_seeds
from src.generator.pipeline import erzeuge_datensatz

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from pathlib import Path

    import pandas as pd
    from numpy.random import SeedSequence

    from src.common.config import Config

#: Anfragezahl der Testdatensaetze.
TEST_ANFRAGEN = 2000


@pytest.fixture(scope="session")
def testkonfiguration(config: Config) -> Config:
    """Die ausgelieferte Konfiguration mit verkleinerter Anfragezahl."""
    return dataclasses.replace(config, n_anfragen=TEST_ANFRAGEN)


@pytest.fixture(scope="session")
def seed_basis(testkonfiguration: Config) -> SeedSequence:
    """Der Basisstrom des Testdatensatzes."""
    return wurzel_seeds(testkonfiguration.master_seed).basis


@pytest.fixture(scope="session")
def datensatz(
    testkonfiguration: Config,
    seed_basis: SeedSequence,
    referenzverzeichnis: Path,
) -> dict[str, pd.DataFrame]:
    """Der erzeugte Datensatz, einmal je Testlauf.

    Args:
        testkonfiguration: Verkleinerte Konfiguration.
        seed_basis: Basisstrom.
        referenzverzeichnis: Erzwingt eine klare Meldung, wenn die Referenzdaten
            fehlen, statt einer Ausnahme tief im Generator.

    Returns:
        Die sieben typisierten Datenrahmen.
    """
    assert referenzverzeichnis.is_dir()
    return erzeuge_datensatz(testkonfiguration, seed_basis)


@pytest.fixture(scope="session")
def referenzdaten(testkonfiguration: Config, referenzverzeichnis: Path) -> dict[str, pd.DataFrame]:
    """Die sieben Referenztabellen, gegen die der Generator abgeglichen wird."""
    assert referenzverzeichnis.is_dir()
    return lade_alle(testkonfiguration)
