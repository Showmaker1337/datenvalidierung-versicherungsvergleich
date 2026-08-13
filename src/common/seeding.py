"""Hierarchisches Seeding (Architekturregel A2).

Dies ist die **einzige** Stelle im Projekt, an der ein Zufallsgenerator entsteht.
Weder ``random.random()`` noch ``np.random.seed()`` noch ein ungeseedeter Faker
duerfen sonst irgendwo auftauchen.

Zwei Ebenen
-----------

:func:`wurzel_seeds`
    Spaltet den Master-Seed einmalig in die drei Stroeme *basis*, *injektion* und
    *modell* auf. Rueckgabe sind ``SeedSequence``-Objekte, keine ganzen Zahlen —
    aus ihnen lassen sich beliebig weitere Kinder ableiten.

:func:`lauf_seed`
    Leitet den Seed eines Einzellaufs **aus seiner Faktorkombination** ab.

Warum die zweite Ebene nicht ueber ``spawn()`` laufen darf
----------------------------------------------------------

``SeedSequence.spawn()`` ist ein Zaehler: Das n-te Kind haengt davon ab, wie
viele Kinder vorher erzeugt wurden. In Phase 6 laufen tausende Einzellaeufe
parallel; mit ``spawn()`` haengt das Ergebnis dann an der Reihenfolge, in der
Worker Auftraege abholen, und damit an der Worker-Zahl. Ein Lauf waere nicht mehr
allein aus ``run_id`` und Konfiguration reproduzierbar.

:func:`lauf_seed` baut die Entropie stattdessen direkt aus
``[master_seed, strom, *faktoren]``. Dieselbe Faktorkombination ergibt immer
denselben Seed, unabhaengig von Reihenfolge, Parallelitaet und Wiederholung.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Final

import numpy as np
from numpy.random import Generator, SeedSequence

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from faker import Faker

__all__ = [
    "FAKER_LOCALE",
    "Seeds",
    "Strom",
    "faker_instanz",
    "generator",
    "lauf_seed",
    "seed_als_int",
    "teilstrom",
    "wurzel_seeds",
]

#: Gebietsschema aller mit Faker erzeugten Basisdaten.
FAKER_LOCALE: Final[str] = "de_DE"

#: Anzahl der Woerter, aus denen ein ganzzahliger Seed gebildet wird.
_ZUSTANDSWOERTER: Final[int] = 4


class Strom(IntEnum):
    """Benannte Zufallsstroeme.

    Der Wert geht als zweites Element in die Entropie von :func:`lauf_seed` ein.
    Die Zahlen sind Teil der Reproduzierbarkeit und duerfen nachtraeglich nicht
    mehr geaendert werden — neue Stroeme bekommen neue Zahlen.
    """

    BASIS = 0
    """Erzeugung des sauberen Datensatzes."""

    INJEKTION = 1
    """Ziehung der zu verfaelschenden Zellen."""

    MODELL = 2
    """Modellseitige Ziehungen, etwa das Subsampling der Baseline B2."""

    REFERENZ = 3
    """Einmalige Erzeugung der Referenztabellen unter ``data/reference``."""

    STATISTIK = 4
    """Ziehungen der Auswertung, insbesondere der Bootstrap-Konfidenzintervalle.

    Getrennt von :attr:`MODELL`, weil die beiden nichts miteinander zu tun haben:
    :attr:`MODELL` gehoert zum Messvorgang (das Subsampling von B2), dieser Strom
    zur Auswertung der bereits gemessenen Zahlen. Ein gemeinsamer Strom haette
    zur Folge, dass eine geaenderte Bootstrap-Einstellung die Baseline B2
    veraendert — und damit die Messwerte selbst.
    """


@dataclass(frozen=True, slots=True)
class Seeds:
    """Die drei Wurzelstroeme eines Laufs.

    Attributes:
        basis: Strom des Basisdatensatzes.
        injektion: Strom der Fehlerinjektion.
        modell: Strom der modellseitigen Ziehungen.
    """

    basis: SeedSequence
    injektion: SeedSequence
    modell: SeedSequence


def wurzel_seeds(master_seed: int) -> Seeds:
    """Spaltet den Master-Seed in die drei Wurzelstroeme auf.

    Args:
        master_seed: Master-Seed aus der Konfiguration.

    Returns:
        Die drei ``SeedSequence``-Objekte als :class:`Seeds`.

    Raises:
        ValueError: Wenn der Master-Seed negativ ist.
    """
    if master_seed < 0:
        raise ValueError(f"master_seed muss nicht negativ sein, war {master_seed}")
    basis, injektion, modell = SeedSequence(master_seed).spawn(3)
    return Seeds(basis=basis, injektion=injektion, modell=modell)


def lauf_seed(master_seed: int, strom: int, *faktoren: int) -> SeedSequence:
    """Leitet den Seed eines Einzellaufs aus seiner Faktorkombination ab.

    Reihenfolgeunabhaengig und damit parallelisierbar: Dieselben Argumente
    ergeben immer dieselbe ``SeedSequence``, unabhaengig davon, wann und in
    welcher Reihenfolge der Lauf ausgefuehrt wird.

    Args:
        master_seed: Master-Seed aus der Konfiguration.
        strom: Wert aus :class:`Strom`.
        *faktoren: Faktorstufen des Laufs, zum Beispiel Fehlerklasse,
            Fehlerrate und Wiederholungsnummer — jeweils als ganze Zahl kodiert.

    Returns:
        Die ``SeedSequence`` des Laufs.

    Raises:
        ValueError: Wenn ein Argument negativ ist. Negative Werte wuerden von
            ``SeedSequence`` zurueckgewiesen; die Pruefung hier liefert die
            aussagekraeftigere Meldung.
    """
    entropie = [master_seed, int(strom), *(int(faktor) for faktor in faktoren)]
    negative = [wert for wert in entropie if wert < 0]
    if negative:
        raise ValueError(f"Seed-Bestandteile muessen nicht negativ sein, waren {negative}")
    return SeedSequence(entropie)


def teilstrom(seed: SeedSequence, nummer: int) -> SeedSequence:
    """Leitet einen benannten Teilstrom aus einer ``SeedSequence`` ab.

    Ein Erzeugungsschritt — etwa die Ziehung der Personen oder die
    Beitragsberechnung — bekommt damit einen eigenen, von den uebrigen Schritten
    unabhaengigen Zufallsstrom.

    Bewusst **nicht** ueber ``spawn()``: Das n-te Kind einer ``SeedSequence``
    haengt davon ab, wie viele Kinder vorher gezogen wurden. Eine neu eingefuegte
    Ziehung wuerde alle nachfolgenden Stroeme verschieben und den gesamten
    Datensatz veraendern. Die Entropie wird stattdessen direkt aus
    ``[seed, nummer]`` gebildet: Dieselbe Nummer ergibt immer denselben Strom,
    unabhaengig von Reihenfolge, Anzahl und Zeitpunkt der Ableitungen
    (Architekturregel A2, gleiche Begruendung wie bei :func:`lauf_seed`).

    Args:
        seed: Ausgangsstrom, zum Beispiel ``Seeds.basis``.
        nummer: Feste Nummer des Teilstroms. Eine neue Ziehung bekommt eine neue
            Nummer; bereits vergebene Nummern werden nicht mehr geaendert.

    Returns:
        Die ``SeedSequence`` des Teilstroms.

    Raises:
        ValueError: Wenn die Nummer negativ ist.
    """
    if nummer < 0:
        raise ValueError(f"Nummer eines Teilstroms muss nicht negativ sein, war {nummer}")
    return SeedSequence([seed_als_int(seed), nummer])


def generator(seed: SeedSequence) -> Generator:
    """Erzeugt den NumPy-Zufallsgenerator zu einer ``SeedSequence``.

    Args:
        seed: Ergebnis von :func:`wurzel_seeds` oder :func:`lauf_seed`.

    Returns:
        Einen ``numpy.random.Generator`` (PCG64).
    """
    return np.random.default_rng(seed)


def seed_als_int(seed: SeedSequence) -> int:
    """Bildet eine ``SeedSequence`` auf eine ganze Zahl ab.

    Wird gebraucht, wo eine Bibliothek nur einen ganzzahligen Seed annimmt —
    etwa Faker — und um ``seed_base`` und ``seed_inject`` im Ground Truth zu
    protokollieren.

    ``generate_state`` ist rein: Es veraendert den Zustand der ``SeedSequence``
    nicht und liefert bei gleicher Eingabe immer dasselbe Ergebnis.

    Args:
        seed: Die abzubildende ``SeedSequence``.

    Returns:
        Eine nicht negative ganze Zahl mit 128 Bit.
    """
    zustand = seed.generate_state(_ZUSTANDSWOERTER, dtype=np.uint32)
    wert = 0
    for wort in zustand:
        wert = (wert << 32) | int(wort)
    return wert


def faker_instanz(seed: SeedSequence, locale: str = FAKER_LOCALE) -> Faker:
    """Erzeugt eine geseedete Faker-Instanz.

    Bewusst ``seed_instance`` statt des klassenweiten ``Faker.seed``: Der
    Klassenaufruf setzt einen **globalen** Zustand, den sich alle Faker-Instanzen
    im Prozess teilen. Das widerspricht Architekturregel A2 ("niemals ein
    globaler Seed") und macht parallele Laeufe voneinander abhaengig.

    Args:
        seed: Ergebnis von :func:`wurzel_seeds` oder :func:`lauf_seed`.
        locale: Gebietsschema, standardmaessig ``de_DE``.

    Returns:
        Eine ausschliesslich ueber diesen Seed gesteuerte Faker-Instanz.
    """
    from faker import Faker  # noqa: PLC0415  (Importkosten nur bei Bedarf)

    instanz = Faker(locale)
    instanz.seed_instance(seed_als_int(seed))
    return instanz
