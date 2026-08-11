"""Lesen und Schreiben einzelner Werte der Rohschicht.

Der Injektor arbeitet ausschliesslich auf ``df_raw`` (``spec/01_datenmodell.md``,
Abschnitt 6): Dort ist jede Spalte eine Zeichenkette, und nur dort sind Format-,
Typ- und Sentinel-Verfaelschungen ueberhaupt schreibbar.

``src.common.serialisierung`` wandelt **ganze Datenrahmen**. Der Injektor braucht
den Zugriff auf **einzelne Zellen**: Er liest einen Betrag, skaliert ihn und
schreibt ihn zurueck, ohne die Spalte anzufassen. Dieses Modul ist die dafuer
noetige Schmalspur. Die Formate sind dieselben — Datum ``TTMMJJJJ``, Zeitpunkt
ISO 8601, Betrag mit Dezimalpunkt und zwei Nachkommastellen — und die
Geldarithmetik laeuft ueber :mod:`src.common.geld`, damit Rundung und
Serialisierung an genau einer Stelle definiert bleiben.

Keine Funktion wirft bei einem unbrauchbaren Wert. Ein Wert, der sich nicht lesen
laesst, gibt ``None`` zurueck; die aufrufende Variante gilt dann fuer diese Zelle
als nicht anwendbar. Das ist dieselbe Haltung wie beim Parser der Rohschicht:
Ein unbrauchbarer Wert ist ein Befund, kein Absturz.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import TYPE_CHECKING, Final

from src.common.geld import als_string, aus_string

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from decimal import Decimal

__all__ = [
    "EXCEL_EPOCHE",
    "LEER",
    "betrag_lesen",
    "betrag_schreiben",
    "excel_serial",
    "ganzzahl_lesen",
    "ganzzahl_schreiben",
    "ist_leer",
    "monate_verschieben",
    "tag_lesen",
    "tag_schreiben",
    "zeitpunkt_lesen",
    "zeitpunkt_schreiben",
]

#: Darstellung eines leeren Wertes in der Rohschicht (spec/01, Abschnitt 6).
LEER: Final[str] = ""

#: Laenge des GDV-Datumsformats ``TTMMJJJJ``.
_DATUM_LAENGE: Final[int] = 8

#: Rohform einer ganzen Zahl: optionales Vorzeichen, danach nur Ziffern.
_MUSTER_GANZZAHL: Final[re.Pattern[str]] = re.compile(r"^-?\d+$")

#: Tag null der Tabellenkalkulations-Zeitrechnung (Variante F2-i).
#:
#: Excel zaehlt ab dem 1. Januar 1900 und behandelt 1900 faelschlich als
#: Schaltjahr; die uebliche Umrechnung setzt deshalb den 30. Dezember 1899 als
#: Nullpunkt an. Genau dieser Wert erscheint, wenn eine Datumsspalte
#: unformatiert aus einer Tabellenkalkulation exportiert wird.
EXCEL_EPOCHE: Final[dt.date] = dt.date(1899, 12, 30)

#: Monate eines Jahres — Grundlage von :func:`monate_verschieben`.
_MONATE_JE_JAHR: Final[int] = 12


def ist_leer(wert: str) -> bool:
    """Gibt zurueck, ob eine Rohzelle leer ist.

    Args:
        wert: Zellinhalt der Rohschicht.

    Returns:
        ``True`` beim Leerstring.
    """
    return wert == LEER


def tag_lesen(roh: str) -> dt.date | None:
    """Liest ein Datum im GDV-Format ``TTMMJJJJ``.

    Args:
        roh: Zellinhalt der Rohschicht.

    Returns:
        Den Kalendertag, oder ``None``, wenn der Wert kein existierender
        Kalendertag im geforderten Format ist.
    """
    if len(roh) != _DATUM_LAENGE or not roh.isdigit():
        return None
    try:
        return dt.date(int(roh[4:8]), int(roh[2:4]), int(roh[0:2]))
    except ValueError:
        return None


def tag_schreiben(tag: dt.date) -> str:
    """Serialisiert einen Kalendertag als ``TTMMJJJJ``.

    Args:
        tag: Zu serialisierender Tag.

    Returns:
        Die achtstellige Zeichenkette.
    """
    return f"{tag.day:02d}{tag.month:02d}{tag.year:04d}"


def zeitpunkt_lesen(roh: str) -> dt.datetime | None:
    """Liest einen Zeitpunkt nach ISO 8601.

    Args:
        roh: Zellinhalt der Rohschicht.

    Returns:
        Den Zeitpunkt, oder ``None`` bei unbrauchbarem Wert.
    """
    try:
        return dt.datetime.fromisoformat(roh)
    except ValueError:
        return None


def zeitpunkt_schreiben(zeitpunkt: dt.datetime) -> str:
    """Serialisiert einen Zeitpunkt sekundengenau nach ISO 8601.

    Args:
        zeitpunkt: Zu serialisierender Zeitpunkt.

    Returns:
        Die Zeichenkette, zum Beispiel ``2026-05-01T09:13:00``.
    """
    return zeitpunkt.isoformat(sep="T", timespec="seconds")


def betrag_lesen(roh: str) -> Decimal | None:
    """Liest einen Geldbetrag aus der Rohschicht.

    Args:
        roh: Zellinhalt der Rohschicht.

    Returns:
        Den Betrag, oder ``None``, wenn der Wert nicht dem Format ``0.00``
        entspricht.
    """
    return aus_string(roh)


def betrag_schreiben(betrag: Decimal) -> str:
    """Serialisiert einen Geldbetrag fuer die Rohschicht.

    Args:
        betrag: Zu serialisierender Betrag.

    Returns:
        Die Zeichenkette mit Dezimalpunkt und zwei Nachkommastellen.
    """
    return als_string(betrag)


def ganzzahl_lesen(roh: str) -> int | None:
    """Liest eine ganze Zahl aus der Rohschicht.

    Args:
        roh: Zellinhalt der Rohschicht.

    Returns:
        Die Zahl, oder ``None``, wenn der Wert keine ganze Zahl ist.
    """
    if not _MUSTER_GANZZAHL.match(roh):
        return None
    return int(roh)


def ganzzahl_schreiben(zahl: int) -> str:
    """Serialisiert eine ganze Zahl ohne fuehrende Nullen.

    Args:
        zahl: Zu serialisierende Zahl.

    Returns:
        Die Zeichenkettendarstellung.
    """
    return str(zahl)


def excel_serial(tag: dt.date) -> int:
    """Rechnet einen Kalendertag in eine Tabellenkalkulations-Seriennummer um.

    Args:
        tag: Umzurechnender Tag.

    Returns:
        Die Zahl der Tage seit :data:`EXCEL_EPOCHE`.
    """
    return (tag - EXCEL_EPOCHE).days


def monate_verschieben(zeitpunkt: dt.datetime, monate: int) -> dt.datetime:
    """Verschiebt einen Zeitpunkt um ganze Monate.

    Der Tag im Monat wird beibehalten, solange der Zielmonat ihn hergibt, sonst
    auf den letzten Tag des Zielmonats gekuerzt. Die Uhrzeit bleibt unveraendert.

    Args:
        zeitpunkt: Ausgangszeitpunkt.
        monate: Zahl der zu verschiebenden Monate; negativ verschiebt zurueck.

    Returns:
        Den verschobenen Zeitpunkt.
    """
    laufend = zeitpunkt.year * _MONATE_JE_JAHR + (zeitpunkt.month - 1) + monate
    jahr, monat = divmod(laufend, _MONATE_JE_JAHR)
    monat += 1
    letzter = _letzter_tag(jahr, monat)
    return zeitpunkt.replace(year=jahr, month=monat, day=min(zeitpunkt.day, letzter))


def _letzter_tag(jahr: int, monat: int) -> int:
    """Gibt die Zahl der Tage eines Monats zurueck."""
    if monat == _MONATE_JE_JAHR:
        return (dt.date(jahr + 1, 1, 1) - dt.timedelta(days=1)).day
    return (dt.date(jahr, monat + 1, 1) - dt.timedelta(days=1)).day
