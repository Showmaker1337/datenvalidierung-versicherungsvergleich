"""Prueft Architekturregel A2 — vollstaendige Reproduzierbarkeit.

Kern des Tests: ``scripts/build_reference.py`` wird zweimal als eigener Prozess
mit demselben Seed ausgefuehrt; die SHA-256-Hashes aller sieben Tabellen muessen
uebereinstimmen. Bewusst als Unterprozess und nicht als Funktionsaufruf — nur so
sind auch Prozessstart, Importreihenfolge und Dateiausgabe mitgeprueft.

Der Gegentest ist ebenso wichtig: Mit einem **anderen** Seed muessen sich die
Dateien unterscheiden. Ein Skript, das den Seed ignoriert, waere sonst
"reproduzierbar" im leeren Sinn.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from numpy.random import SeedSequence

from src.common.pfade import REFERENZ_DATEIEN, sha256_datei
from src.common.seeding import (
    Strom,
    faker_instanz,
    generator,
    lauf_seed,
    seed_als_int,
    wurzel_seeds,
)

WURZEL = Path(__file__).resolve().parents[1]
SKRIPT = WURZEL / "scripts" / "build_reference.py"


def _baue(ziel: Path, seed: int) -> dict[str, str]:
    """Fuehrt das Referenzskript aus und gibt die Hashwerte der Ergebnisse zurueck."""
    ergebnis = subprocess.run(
        [sys.executable, str(SKRIPT), "--ziel", str(ziel), "--seed", str(seed), "--still"],
        cwd=WURZEL,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ergebnis.returncode == 0, f"build_reference.py schlug fehl:\n{ergebnis.stderr}"
    return {name: sha256_datei(ziel / name) for name in REFERENZ_DATEIEN}


@pytest.fixture(scope="module")
def hashes_gleicher_seed(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict[str, str], ...]:
    """Zwei Laeufe mit demselben Seed in zwei getrennten Verzeichnissen."""
    erster = _baue(tmp_path_factory.mktemp("lauf_a"), 20260630)
    zweiter = _baue(tmp_path_factory.mktemp("lauf_b"), 20260630)
    return (erster, zweiter)


@pytest.mark.parametrize("dateiname", REFERENZ_DATEIEN)
def test_gleicher_seed_erzeugt_bitgleiche_datei(
    hashes_gleicher_seed: tuple[dict[str, str], ...], dateiname: str
) -> None:
    """Zwei Laeufe mit demselben Seed liefern bitgleiche Referenztabellen."""
    erster, zweiter = hashes_gleicher_seed
    assert erster[dateiname] == zweiter[dateiname], f"{dateiname} ist nicht reproduzierbar"


def test_anderer_seed_erzeugt_andere_dateien(
    hashes_gleicher_seed: tuple[dict[str, str], ...], tmp_path: Path
) -> None:
    """Gegenprobe: Der Seed wirkt sich tatsaechlich aus."""
    erster, _ = hashes_gleicher_seed
    anders = _baue(tmp_path / "lauf_c", 987654321)

    verschieden = [name for name in REFERENZ_DATEIEN if erster[name] != anders[name]]
    assert len(verschieden) >= 5, (
        "Mit einem anderen Seed muessen sich nahezu alle Tabellen unterscheiden, "
        f"verschieden waren nur: {verschieden}"
    )
    # sf_beitragssatz.csv folgt einer festen Formel und haengt bewusst nicht am Seed.
    assert erster["sf_beitragssatz.csv"] == anders["sf_beitragssatz.csv"]


def test_versionierte_referenzdaten_entsprechen_dem_master_seed(
    referenzverzeichnis: Path, tmp_path: Path
) -> None:
    """Die eingecheckten Dateien sind mit dem Master-Seed aus der Konfiguration erzeugt.

    Schuetzt davor, dass jemand eine Referenzdatei von Hand aendert, ohne das
    Skript anzupassen — dann waere die Herkunft der Daten nicht mehr belegbar.
    """
    frisch = _baue(tmp_path / "frisch", 20260630)
    for name in REFERENZ_DATEIEN:
        assert sha256_datei(referenzverzeichnis / name) == frisch[name], (
            f"{name} unter data/reference weicht vom Skriptergebnis ab"
        )


# ---------------------------------------------------------------------------
# Seeding-Eigenschaften
# ---------------------------------------------------------------------------


def test_lauf_seed_ist_reihenfolgeunabhaengig() -> None:
    """Derselbe Faktorsatz ergibt immer denselben Seed — unabhaengig von der Aufrufreihenfolge.

    Genau das leistet ``spawn()`` nicht: Mit ``spawn()`` haengt das Ergebnis
    daran, wie viele Kinder vorher gezogen wurden, und damit an der Worker-Zahl.
    """
    zuerst = lauf_seed(20260630, Strom.BASIS, 3, 5, 7)
    dazwischen = [lauf_seed(20260630, Strom.INJEKTION, i) for i in range(20)]
    danach = lauf_seed(20260630, Strom.BASIS, 3, 5, 7)

    assert list(zuerst.generate_state(4)) == list(danach.generate_state(4))
    assert len(dazwischen) == 20


def test_spawn_ist_reihenfolgeabhaengig() -> None:
    """Gegenprobe zur Begruendung von :func:`lauf_seed`."""
    wurzel = SeedSequence(20260630)
    erstes_kind = wurzel.spawn(1)[0]
    zweites_kind = wurzel.spawn(1)[0]
    assert list(erstes_kind.generate_state(4)) != list(zweites_kind.generate_state(4))


def test_verschiedene_faktoren_ergeben_verschiedene_seeds() -> None:
    """Unterschiedliche Faktorstufen duerfen nicht auf denselben Strom fallen."""
    zustaende = {
        tuple(lauf_seed(20260630, Strom.BASIS, klasse, rate, wiederholung).generate_state(4))
        for klasse in range(8)
        for rate in range(6)
        for wiederholung in range(5)
    }
    assert len(zustaende) == 8 * 6 * 5


def test_stroeme_sind_getrennt() -> None:
    """Basis-, Injektions- und Modellstrom liefern verschiedene Zufallsfolgen."""
    seeds = wurzel_seeds(20260630)
    zahlen = {
        name: generator(seed).integers(0, 2**32, size=5).tolist()
        for name, seed in (
            ("basis", seeds.basis),
            ("injektion", seeds.injektion),
            ("modell", seeds.modell),
        )
    }
    assert zahlen["basis"] != zahlen["injektion"] != zahlen["modell"]
    assert zahlen["basis"] != zahlen["modell"]


def test_wurzel_seeds_sind_reproduzierbar() -> None:
    """Derselbe Master-Seed erzeugt dieselben drei Wurzelstroeme."""
    erste = wurzel_seeds(20260630)
    zweite = wurzel_seeds(20260630)
    assert seed_als_int(erste.basis) == seed_als_int(zweite.basis)
    assert seed_als_int(erste.injektion) == seed_als_int(zweite.injektion)
    assert seed_als_int(erste.modell) == seed_als_int(zweite.modell)


def test_seed_als_int_veraendert_die_sequenz_nicht() -> None:
    """``generate_state`` ist rein — zweimaliges Ablesen liefert denselben Wert."""
    seed = lauf_seed(20260630, Strom.REFERENZ, 0)
    assert seed_als_int(seed) == seed_als_int(seed)


def test_generator_ist_reproduzierbar() -> None:
    """Zwei Generatoren aus derselben SeedSequence liefern dieselbe Folge."""
    ziehung = [
        generator(lauf_seed(20260630, Strom.BASIS, 1)).normal(size=10).tolist() for _ in range(2)
    ]
    assert ziehung[0] == ziehung[1]


def test_faker_ist_geseedet_und_reproduzierbar() -> None:
    """Faker liefert bei gleichem Seed gleiche Werte und bei anderem Seed andere."""
    seed = lauf_seed(20260630, Strom.BASIS, 42)
    erster = [faker_instanz(seed).last_name() for _ in range(2)]
    assert erster[0] == erster[1]

    anderer = faker_instanz(lauf_seed(20260630, Strom.BASIS, 43)).last_name()
    zweiter_lauf = faker_instanz(seed).last_name()
    assert zweiter_lauf == erster[0]
    assert isinstance(anderer, str)


def test_faker_instanzen_beeinflussen_sich_nicht() -> None:
    """Instanzseeding statt globalem ``Faker.seed`` — sonst waeren parallele Laeufe gekoppelt."""
    seed = lauf_seed(20260630, Strom.BASIS, 7)
    erster = faker_instanz(seed)
    stoerer = faker_instanz(lauf_seed(20260630, Strom.BASIS, 8))

    erwartet = [erster.last_name() for _ in range(3)]

    erster_erneut = faker_instanz(seed)
    for _ in range(5):
        stoerer.last_name()
    gemessen = [erster_erneut.last_name() for _ in range(3)]

    assert gemessen == erwartet
