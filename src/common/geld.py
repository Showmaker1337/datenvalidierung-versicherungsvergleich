"""Rechnen mit Geldbetraegen.

Geld ist im gesamten Projekt :class:`~decimal.Decimal`, niemals ``float``
(CLAUDE.md, Abschnitt 5). Dieses Modul ist die einzige Stelle, an der gerundet
und serialisiert wird.

Der Schutz gegen ``float`` ist absichtlich hart: :func:`zu_decimal` **wirft** bei
einem ``float``, statt still zu konvertieren. Wer aus einer Ziehung einen Betrag
gewinnt, geht bewusst ueber :func:`von_float` — dann steht die Umwandlung im
Quelltext und ist im Review sichtbar.
"""

from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Iterable

__all__ = [
    "NACHKOMMASTELLEN",
    "GeldFehler",
    "als_string",
    "aus_string",
    "runde",
    "summe",
    "von_float",
    "zu_decimal",
]

#: Anzahl der Nachkommastellen aller Geldbetraege.
NACHKOMMASTELLEN: Final[int] = 2

#: Quantisierungsvorlage fuer :func:`runde`.
_QUANTUM: Final[Decimal] = Decimal("0.01")

#: Serialisierungsformat der Rohschicht: Dezimalpunkt, zwei Nachkommastellen,
#: kein Tausendertrenner, optionales Vorzeichen (spec/01, Abschnitt 6).
_MUSTER_BETRAG: Final[re.Pattern[str]] = re.compile(r"^-?\d+\.\d{2}$")


class GeldFehler(ValueError):
    """Ein Wert kann nicht als Geldbetrag verarbeitet werden."""


def zu_decimal(betrag: Decimal | int | str) -> Decimal:
    """Wandelt einen Wert in ein :class:`~decimal.Decimal` um.

    Args:
        betrag: Betrag als ``Decimal``, ``int`` oder Dezimalzeichenkette.

    Returns:
        Den Wert als ``Decimal``.

    Raises:
        GeldFehler: Bei ``float``, ``bool`` oder nicht interpretierbarer Zeichenkette.

    Note:
        Die Pruefung laeuft ueber eine als ``object`` gefuehrte Kopie. Die
        Typannotation schliesst ``float`` bereits aus; die Pruefung zur Laufzeit
        greift trotzdem, weil Aufrufe aus ungetypten Zusammenhaengen — etwa aus
        einer pandas-Spalte — am Typsystem vorbeikommen.
    """
    wert: object = betrag
    if isinstance(wert, bool):
        raise GeldFehler(f"Wahrheitswert ist kein Geldbetrag: {wert!r}")
    if isinstance(wert, Decimal):
        return wert
    if isinstance(wert, int):
        return Decimal(wert)
    if isinstance(wert, float):
        raise GeldFehler(
            f"Geld wird niemals als float gefuehrt: {wert!r}. "
            "Fuer eine bewusste Umwandlung von_float() verwenden."
        )
    if not isinstance(wert, str):
        raise GeldFehler(f"Kein Geldbetrag: {wert!r} ({type(wert).__name__})")
    try:
        return Decimal(wert)
    except InvalidOperation as fehler:
        raise GeldFehler(f"Kein interpretierbarer Geldbetrag: {wert!r}") from fehler


def von_float(betrag: float) -> Decimal:
    """Wandelt einen ``float`` bewusst und verlustarm in einen Geldbetrag um.

    Die Umwandlung laeuft ueber ``repr``, nicht ueber ``Decimal(float)``. Damit
    wird der kuerzeste Dezimalwert genommen, der den ``float`` eindeutig
    beschreibt, statt seiner vollstaendigen Binaerentwicklung.

    Args:
        betrag: Ergebnis einer Ziehung oder Berechnung in Gleitkomma.

    Returns:
        Den auf zwei Nachkommastellen gerundeten Betrag.

    Raises:
        GeldFehler: Wenn der Wert nicht endlich ist.
    """
    if not math.isfinite(betrag):
        raise GeldFehler(f"Nicht endlicher Wert ist kein Geldbetrag: {betrag!r}")
    return runde(Decimal(repr(betrag)))


def runde(betrag: Decimal | int | str) -> Decimal:
    """Rundet auf zwei Nachkommastellen, kaufmaennisch (``ROUND_HALF_UP``).

    Args:
        betrag: Zu rundender Betrag.

    Returns:
        Den Betrag mit genau zwei Nachkommastellen.
    """
    return zu_decimal(betrag).quantize(_QUANTUM, rounding=ROUND_HALF_UP)


def summe(betraege: Iterable[Decimal | int | str]) -> Decimal:
    """Summiert Geldbetraege exakt und rundet erst am Ende.

    Args:
        betraege: Beliebig viele Betraege.

    Returns:
        Die gerundete Summe; ``Decimal("0.00")`` bei leerer Eingabe.
    """
    gesamt = Decimal(0)
    for einzeln in betraege:
        gesamt += zu_decimal(einzeln)
    return runde(gesamt)


def als_string(betrag: Decimal | int | str) -> str:
    """Serialisiert einen Betrag fuer die Rohschicht ``df_raw``.

    Dezimalpunkt, genau zwei Nachkommastellen, kein Tausendertrenner
    (spec/01_datenmodell.md, Abschnitt 6).

    Args:
        betrag: Zu serialisierender Betrag.

    Returns:
        Die Zeichenkettendarstellung, zum Beispiel ``"1234.50"``.
    """
    return f"{runde(betrag):f}"


def aus_string(text: str) -> Decimal | None:
    """Parst einen Betrag aus der Rohschicht zurueck.

    Args:
        text: Zeichenkette aus ``df_raw``.

    Returns:
        Den Betrag, oder ``None``, wenn der Wert nicht dem Serialisierungsformat
        entspricht. Ein nicht parsbarer Wert ist ein Befund, kein Absturz
        (spec/01_datenmodell.md, Abschnitt 6).
    """
    if not _MUSTER_BETRAG.match(text):
        return None
    return Decimal(text)
