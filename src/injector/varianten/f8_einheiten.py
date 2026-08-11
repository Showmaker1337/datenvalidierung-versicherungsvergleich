"""F8 — Einheiten- und Repraesentationsfehler zwischen Quellen (``spec/03``, Abschnitt 2).

Empirische Ursache: Zwei Anbieter liefern dasselbe Feld in verschiedenen
Einheiten. Der eine gibt Betraege in Cent, der andere in Euro; der eine liefert
den Jahresbeitrag, der andere den Monatsbeitrag; der eine fuehrt den Selbstbehalt
als Betrag, der andere als Prozentsatz der Versicherungssumme. Solange jede
Quelle fuer sich konsistent ist, faellt nichts auf — der Fehler entsteht erst
beim Zusammenfuehren. Das ist der Multi-Source-Fall im Sinne von Rahm und Do.

F8-a wirkt auf Anbieterebene
----------------------------

Die Variante stellt **einen Anbieter je Anfrage** auf die andere
Einheitenkonvention um, nicht eine einzelne Zeile. Sie laeuft deshalb ueber die
Zuordnung Anbieter auf Quellschnittstelle: Getroffen werden alle Angebote der
Anfrage, die ueber dieselbe Schnittstelle geliefert wurden. Eine zeilenweise
Umstellung waere kein Multi-Source-Fehler, sondern ein Einzelfehler.

Kohaerente Skalierung bei F8-b bis F8-e
---------------------------------------

Skaliert wird immer das **gesamte Beitragstupel** und die Rangfolge wird
mitgezogen. Die Begruendung steht im Docstring von
:mod:`src.injector.varianten.bausteine`.

F8-e ist der wertvollste Einzelfall des Injektors
-------------------------------------------------

Sie teilt **alle** Angebote einer Anfrage durch zwoelf. Eine relationale
Plausibilitaetspruefung, die ein Angebot gegen den Median der uebrigen haelt,
greift dann nicht: Der Median wandert mit. Die Variante zeigt die strukturelle
Grenze relationaler Pruefungen und gehoert ausdruecklich in die Diskussion der
Arbeit — sie soll **nicht** erkannt werden.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Final

from src.injector.modell import Aenderung, Fehlerklasse, Variante, Zellaenderung, Zielart
from src.injector.rohwerte import LEER, betrag_lesen, betrag_schreiben, ganzzahl_lesen
from src.injector.varianten.bausteine import (
    BEITRAGSSPALTEN,
    kandidaten_aus_feldern,
    skaliere_beitraege,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    from numpy.random import Generator

    from src.injector.modell import AnwendungsFunktion, Injektionskontext, Kandidat

__all__ = ["ANKERSPALTE", "BEITRAGSZUSATZ", "VARIANTEN", "kandidaten_beitragstupel"]

#: Ankerspalte aller Varianten, die das Beitragstupel skalieren.
ANKERSPALTE: Final[str] = BEITRAGSSPALTEN[0]

#: Die uebrigen Spalten des Beitragstupels — sie gehen als Zusatzspalten in das
#: adressierbare Zelluniversum ein.
BEITRAGSZUSATZ: Final[tuple[str, ...]] = BEITRAGSSPALTEN[1:]

#: Faktor der Cent-statt-Euro-Verwechslung (Variante F8-b).
_FAKTOR_CENT: Final[Decimal] = Decimal(100)
#: Faktor der Euro-statt-Cent-Verwechslung (Variante F8-c).
_FAKTOR_EURO: Final[Decimal] = Decimal(1) / Decimal(100)
#: Faktor der Monats-statt-Jahresbeitrag-Verwechslung (Varianten F8-d und F8-e).
_FAKTOR_MONAT: Final[Decimal] = Decimal(1) / Decimal(12)
#: Hundert Prozent — Nenner der Selbstbehaltsumrechnung.
_PROZENT: Final[Decimal] = Decimal(100)


def kandidaten_beitragstupel(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Bepreiste Angebote mit vollstaendig lesbarem Beitragstupel.

    Args:
        kontext: Lesende Sicht auf den sauberen Datensatz.

    Returns:
        Die Kandidaten mit :data:`ANKERSPALTE` als Ankerspalte.
    """
    return kandidaten_aus_feldern(
        kontext, (("angebot", ANKERSPALTE),), zeilenbedingung=hat_beitragstupel
    )


def hat_beitragstupel(kontext: Injektionskontext, entitaet: str, row_id: int) -> bool:
    """Prueft, ob eine Angebotszeile bepreist ist und alle vier Beitragsfelder traegt.

    Args:
        kontext: Lesende Sicht auf den sauberen Datensatz.
        entitaet: Name der Entitaet.
        row_id: Zeilenkennung.

    Returns:
        ``True``, wenn Rang und alle Beitragsfelder lesbar sind.
    """
    if ganzzahl_lesen(kontext.wert(entitaet, row_id, "rang")) is None:
        return False
    return all(
        betrag_lesen(kontext.wert(entitaet, row_id, spalte)) is not None
        for spalte in BEITRAGSSPALTEN
    )


def skalierung(faktor: Decimal, *, ganze_anfrage: bool) -> AnwendungsFunktion:
    """Baut eine Anwendungsfunktion, die das Beitragstupel kohaerent skaliert.

    Args:
        faktor: Skalierungsfaktor.
        ganze_anfrage: ``True`` skaliert **alle** bepreisten Angebote der
            Anfrage, ``False`` nur die getroffene Zeile.

    Returns:
        Die Anwendungsfunktion der Variante.
    """

    def anwenden(
        kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
    ) -> Aenderung | None:
        anfrage_id = kontext.wert(kandidat.entitaet, kandidat.row_id, "anfrage_id")
        if not ganze_anfrage:
            return skaliere_beitraege(kontext, anfrage_id, (kandidat.row_id,), faktor)
        angebote = tuple(
            row_id
            for row_id in kontext.angebote_je_anfrage.get(anfrage_id, ())
            if hat_beitragstupel(kontext, "angebot", row_id)
        )
        if not angebote:
            return None
        return skaliere_beitraege(kontext, anfrage_id, angebote, faktor)

    return anwenden


# ---------------------------------------------------------------------------
# F8-a — Selbstbehalt von Betrag auf Prozent
# ---------------------------------------------------------------------------


def _kandidaten_selbstbehalt(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Hausratangebote mit einem als Betrag gefuehrten Selbstbehalt."""
    return kandidaten_aus_feldern(
        kontext, (("angebot", "sb_hausrat_eur"),), zeilenbedingung=_hat_bezugsgroesse
    )


def _hat_bezugsgroesse(kontext: Injektionskontext, entitaet: str, row_id: int) -> bool:
    """Trifft zu, wenn zur Anfrage eine Hausrat-Versicherungssumme vorliegt."""
    anfrage_id = kontext.wert(entitaet, row_id, "anfrage_id")
    return anfrage_id in kontext.versicherungssumme_je_anfrage


def _selbstbehalt_als_prozent(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F8-a: Ein Anbieter je Anfrage fuehrt den Selbstbehalt als Prozentsatz."""
    anfrage_id = kontext.wert(kandidat.entitaet, kandidat.row_id, "anfrage_id")
    schnittstelle = kontext.wert(kandidat.entitaet, kandidat.row_id, "quell_schnittstelle")
    summe = kontext.versicherungssumme_je_anfrage.get(anfrage_id)
    if summe is None or summe <= 0:
        return None

    zellen: list[Zellaenderung] = []
    for row_id in kontext.angebote_je_anfrage.get(anfrage_id, ()):
        if kontext.wert("angebot", row_id, "quell_schnittstelle") != schnittstelle:
            continue
        betrag = betrag_lesen(kontext.wert("angebot", row_id, "sb_hausrat_eur"))
        if betrag is None:
            continue
        zellen.append(
            Zellaenderung(
                entitaet="angebot",
                row_id=row_id,
                spalte="sb_hausrat_prozent",
                wert_dirty=betrag_schreiben(betrag / summe * _PROZENT),
            )
        )
        zellen.append(
            Zellaenderung(
                entitaet="angebot", row_id=row_id, spalte="sb_hausrat_eur", wert_dirty=LEER
            )
        )
    if not zellen:
        return None
    return Aenderung(zellen=tuple(zellen))


VARIANTEN: Sequence[Variante] = (
    Variante(
        variante_id="F8-a",
        fehlerklasse=Fehlerklasse.F8,
        zielart=Zielart.ZELLE,
        beschreibung="Ein Anbieter je Anfrage stellt den Selbstbehalt von Betrag auf Prozent um",
        ursache="Zwei Quellschnittstellen mit verschiedener Einheitenkonvention",
        kandidaten=_kandidaten_selbstbehalt,
        anwenden=_selbstbehalt_als_prozent,
        zusatzspalten=("sb_hausrat_prozent",),
    ),
    Variante(
        variante_id="F8-b",
        fehlerklasse=Fehlerklasse.F8,
        zielart=Zielart.ZELLE,
        beschreibung="Gesamtes Beitragstupel mit 100 multipliziert",
        ursache="Cent-Werte einer Quelle als Euro uebernommen",
        kandidaten=kandidaten_beitragstupel,
        anwenden=skalierung(_FAKTOR_CENT, ganze_anfrage=False),
        zusatzspalten=BEITRAGSZUSATZ,
    ),
    Variante(
        variante_id="F8-c",
        fehlerklasse=Fehlerklasse.F8,
        zielart=Zielart.ZELLE,
        beschreibung="Gesamtes Beitragstupel durch 100 geteilt",
        ursache="Euro-Werte einer Quelle als Cent uebernommen",
        kandidaten=kandidaten_beitragstupel,
        anwenden=skalierung(_FAKTOR_EURO, ganze_anfrage=False),
        zusatzspalten=BEITRAGSZUSATZ,
    ),
    Variante(
        variante_id="F8-d",
        fehlerklasse=Fehlerklasse.F8,
        zielart=Zielart.ZELLE,
        beschreibung="Gesamtes Beitragstupel eines Angebots durch 12 geteilt",
        ursache="Monatsbeitrag einer Quelle als Jahresbeitrag uebernommen",
        kandidaten=kandidaten_beitragstupel,
        anwenden=skalierung(_FAKTOR_MONAT, ganze_anfrage=False),
        zusatzspalten=BEITRAGSZUSATZ,
    ),
    Variante(
        variante_id="F8-e",
        fehlerklasse=Fehlerklasse.F8,
        zielart=Zielart.ZELLE,
        beschreibung="Gesamtes Beitragstupel aller Angebote einer Anfrage durch 12 geteilt",
        ursache="Der gesamte Vergleichslauf lief in Monatsbeitraegen",
        kandidaten=kandidaten_beitragstupel,
        anwenden=skalierung(_FAKTOR_MONAT, ganze_anfrage=True),
        zusatzspalten=BEITRAGSZUSATZ,
    ),
)
