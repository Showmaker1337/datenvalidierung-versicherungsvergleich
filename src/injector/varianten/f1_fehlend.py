"""F1 — fehlender Wert, explizit und implizit (``spec/03``, Abschnitt 2).

Empirische Ursache: Ein Feld wird bei der Erfassung uebersprungen, geht bei der
Konvertierung zwischen zwei Formaten verloren oder wird von einem Altsystem mit
einem Platzhalter belegt, weil das Zielformat keinen Nullwert kennt. Die letzte
Ursache ist die haeufigste und zugleich die unangenehmste: Der Platzhalter ist
syntaktisch ein Wert und faellt in keiner Vollstaendigkeitspruefung auf.

Warum F1-a und F1-b verschiedene Varianten bleiben
--------------------------------------------------

F1-a laesst das Feld **fehlen** (``pd.NA`` in der Rohschicht), F1-b liefert es
**leer** (Leerstring). Auf der Speicherebene ist das ein Unterschied, wie ihn
jede Schnittstelle kennt, die zwischen ``null`` und ``""`` trennt. Nach dem
Parsen ist er verschwunden: ``spec/01``, Abschnitt 6 serialisiert jeden leeren
Wert als Leerstring, und der Parser macht aus beidem ``pd.NA``.

Das ist kein Implementierungsmangel, sondern ein **Informationsverlust der
Serialisierung** — genau das passiert an realen Schnittstellen, wenn ein Format
zwischen "nicht belegt" und "leer geliefert" nicht unterscheidet. Die Folge fuer
die Auswertung steht in ``CLAUDE.md``, Abschnitt 5: F1-b ist nur ueber die
Pflichtfeldregeln erkennbar, nicht ueber die Sentinel-Regel.

Die Platzhalterwerte stehen als Literal in diesem Modul
-------------------------------------------------------

``"-"``, ``"k.A."``, ``9999``, ``99999999`` und der 1. Januar 1900 stammen aus
``spec/03``, Abschnitt 2 und werden hier ausgeschrieben, nicht aus
:mod:`src.common.wertebereiche` importiert. Sie stimmen mit den dortigen
Sentinel-Listen ueberein, weil beide aus derselben Taxonomie kommen — nicht,
weil der Injektor sie von der Pruefseite uebernimmt. Der Unterschied ist fuer die
Unabhaengigkeitsargumentation der Arbeit wesentlich.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import TYPE_CHECKING, Final

from src.common.serialisierung import FELDTYP_JE_SPALTE, Feldtyp
from src.injector.modell import Fehlerklasse, Variante, Zielart
from src.injector.rohwerte import LEER, betrag_schreiben, ganzzahl_schreiben, tag_schreiben
from src.injector.varianten.bausteine import (
    einzelne_zelle,
    felder_ohne_schluessel,
    kandidaten_aus_feldern,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    from numpy.random import Generator

    from src.injector.modell import (
        Aenderung,
        AnwendungsFunktion,
        Injektionskontext,
        Kandidat,
    )

__all__ = ["VARIANTEN"]

#: Textplatzhalter der Varianten F1-c und F1-d (spec/03, Abschnitt 2).
_STRICH: Final[str] = "-"
_KEINE_ANGABE: Final[str] = "k.A."

#: Numerische Platzhalter der Variante F1-e (spec/03, Abschnitt 2).
_SENTINEL_GANZZAHL: Final[int] = 9999
_SENTINEL_DEZIMAL: Final[Decimal] = Decimal(99999999)

#: Datumsplatzhalter der Variante F1-f (spec/03, Abschnitt 2).
_SENTINEL_TAG: Final[dt.date] = dt.date(1900, 1, 1)

#: Feldtypen, in denen ein numerischer Platzhalter vorkommen kann.
_NUMERISCHE_TYPEN: Final[frozenset[Feldtyp]] = frozenset({Feldtyp.GANZZAHL, Feldtyp.DEZIMAL})


def _felder(typen: frozenset[Feldtyp] | None = None) -> tuple[tuple[str, str], ...]:
    """Gibt die Zielfelder der Klasse zurueck, wahlweise auf Feldtypen eingeschraenkt."""
    alle = felder_ohne_schluessel()
    if typen is None:
        return alle
    return tuple(
        (entitaet, spalte)
        for entitaet, spalte in alle
        if FELDTYP_JE_SPALTE[spalte] in typen
    )


def _kandidaten_alle(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Alle gefuellten Zellen ausserhalb der Schluesselspalten."""
    return kandidaten_aus_feldern(kontext, _felder())


def _kandidaten_numerisch(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Gefuellte Zellen numerischer Felder."""
    return kandidaten_aus_feldern(kontext, _felder(_NUMERISCHE_TYPEN))


def _kandidaten_datum(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Gefuellte Zellen von Datumsfeldern."""
    return kandidaten_aus_feldern(kontext, _felder(frozenset({Feldtyp.DATUM})))


def _fester_wert(wert: str | None) -> AnwendungsFunktion:
    """Baut eine Anwendungsfunktion, die immer denselben Rohwert schreibt.

    Args:
        wert: Zu schreibender Rohwert; ``None`` steht fuer einen fehlenden Wert.

    Returns:
        Die Anwendungsfunktion der Variante.
    """

    def anwenden(
        _kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
    ) -> Aenderung | None:
        return einzelne_zelle(kandidat, wert)

    return anwenden


def _sentinel_numerisch(
    _kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """Setzt den zum Feldtyp passenden numerischen Platzhalter."""
    if kandidat.spalte is None:
        return None
    if FELDTYP_JE_SPALTE[kandidat.spalte] is Feldtyp.GANZZAHL:
        return einzelne_zelle(kandidat, ganzzahl_schreiben(_SENTINEL_GANZZAHL))
    return einzelne_zelle(kandidat, betrag_schreiben(_SENTINEL_DEZIMAL))


def _sentinel_datum(
    _kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """Setzt den Datumsplatzhalter im GDV-Format."""
    return einzelne_zelle(kandidat, tag_schreiben(_SENTINEL_TAG))


VARIANTEN: Sequence[Variante] = (
    Variante(
        variante_id="F1-a",
        fehlerklasse=Fehlerklasse.F1,
        zielart=Zielart.ZELLE,
        beschreibung="Wert fehlt vollstaendig (pd.NA in der Rohschicht)",
        ursache="Feld bei der Erfassung uebersprungen oder in der Konvertierung verloren",
        kandidaten=_kandidaten_alle,
        anwenden=_fester_wert(None),
    ),
    Variante(
        variante_id="F1-b",
        fehlerklasse=Fehlerklasse.F1,
        zielart=Zielart.ZELLE,
        beschreibung="Wert durch Leerstring ersetzt",
        ursache="Schnittstelle liefert das Feld leer statt es wegzulassen",
        kandidaten=_kandidaten_alle,
        anwenden=_fester_wert(LEER),
    ),
    Variante(
        variante_id="F1-c",
        fehlerklasse=Fehlerklasse.F1,
        zielart=Zielart.ZELLE,
        beschreibung='Wert durch "-" ersetzt',
        ursache="Freitexteingabe: Erfasser traegt einen Strich ein, wo nichts vorliegt",
        kandidaten=_kandidaten_alle,
        anwenden=_fester_wert(_STRICH),
    ),
    Variante(
        variante_id="F1-d",
        fehlerklasse=Fehlerklasse.F1,
        zielart=Zielart.ZELLE,
        beschreibung='Wert durch "k.A." ersetzt',
        ursache="Freitexteingabe: ausgeschriebener Platzhalter statt eines Nullwerts",
        kandidaten=_kandidaten_alle,
        anwenden=_fester_wert(_KEINE_ANGABE),
    ),
    Variante(
        variante_id="F1-e",
        fehlerklasse=Fehlerklasse.F1,
        zielart=Zielart.ZELLE,
        beschreibung="Numerisches Sentinel 9999 beziehungsweise 99999999",
        ursache="Legacy-Migration: Zielformat kennt keinen Nullwert, Neunerfolge steht dafuer",
        kandidaten=_kandidaten_numerisch,
        anwenden=_sentinel_numerisch,
    ),
    Variante(
        variante_id="F1-f",
        fehlerklasse=Fehlerklasse.F1,
        zielart=Zielart.ZELLE,
        beschreibung="Datums-Sentinel 1900-01-01",
        ursache="Legacy-Migration: kleinstmoegliches Datum als Ersatz fuer ein leeres Feld",
        kandidaten=_kandidaten_datum,
        anwenden=_sentinel_datum,
    ),
)
