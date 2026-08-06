"""IBAN-Pruefziffern nach ISO 7064 Mod 97-10.

Dieses Modul liegt bewusst in ``src/common``: Der Generator braucht es, um
gueltige IBANs zu erzeugen, die Regel-Engine, um sie zu pruefen (R-003, R-004).
Gemeinsame Definitionen gehoeren nach ``src/common`` — das ist genau der Fall,
den Architekturregel A1 vorsieht, und keine Verletzung.

Die Umsetzung folgt dem Pseudocode in ``spec/02_regelkatalog.md``, Abschnitt G1:

1. Leerzeichen entfernen, in Grossbuchstaben wandeln
2. die ersten vier Zeichen ans Ende verschieben
3. jeden Buchstaben ersetzen (A=10, B=11, ..., Z=35)
4. Ergebnis als ganze Zahl interpretieren
5. gueltig genau dann, wenn ``zahl mod 97 == 1``
"""

from __future__ import annotations

import re
from typing import Final

__all__ = [
    "IbanFehler",
    "baue_iban",
    "berechne_pruefziffer",
    "hat_deutsches_format",
    "ist_gueltig",
    "normalisiere",
]

#: Laenge der deutschen Bankleitzahl.
_BLZ_LAENGE: Final[int] = 8
#: Laenge der auf volle Breite aufgefuellten Kontonummer.
_KONTO_LAENGE: Final[int] = 10
#: Mindestlaenge einer IBAN nach ISO 13616 (Laenderkuerzel, Pruefziffer, BBAN).
_IBAN_MINDESTLAENGE: Final[int] = 5
#: Modulus nach ISO 7064 Mod 97-10.
_MODULUS: Final[int] = 97
#: Numerische Darstellung von "DE00" am Ende der umgestellten Zeichenkette.
_LAENDERKENNUNG_DE_NUMERISCH: Final[str] = "131400"

#: Deutsche IBAN: "DE" gefolgt von genau 20 Ziffern (R-003).
_MUSTER_DE: Final[re.Pattern[str]] = re.compile(r"^DE\d{20}$")
#: Nur Ziffern.
_MUSTER_ZIFFERN: Final[re.Pattern[str]] = re.compile(r"^\d+$")


class IbanFehler(ValueError):
    """Eine IBAN oder ihre Bestandteile sind nicht verarbeitbar."""


def normalisiere(iban: str) -> str:
    """Entfernt Leerzeichen und wandelt in Grossbuchstaben (Schritt 1).

    Args:
        iban: IBAN in beliebiger Schreibweise.

    Returns:
        Die IBAN ohne Leerraum in Grossbuchstaben.
    """
    return "".join(iban.split()).upper()


def _numerische_darstellung(iban: str) -> int | None:
    """Setzt die Schritte 2 bis 4 des Pseudocodes um.

    Args:
        iban: Bereits normalisierte IBAN.

    Returns:
        Die Zahl aus der umgestellten Zeichenkette, oder ``None``, wenn die
        IBAN zu kurz ist oder Zeichen ausserhalb ``[A-Z0-9]`` enthaelt.
    """
    if len(iban) < _IBAN_MINDESTLAENGE:
        return None
    umgestellt = iban[4:] + iban[:4]
    ziffern: list[str] = []
    for zeichen in umgestellt:
        if zeichen.isdigit():
            ziffern.append(zeichen)
        elif "A" <= zeichen <= "Z":
            ziffern.append(str(ord(zeichen) - ord("A") + 10))
        else:
            return None
    return int("".join(ziffern))


def ist_gueltig(iban: str) -> bool:
    """Prueft die IBAN-Pruefziffer nach ISO 7064 Mod 97-10 (R-004).

    Geprueft wird ausschliesslich die Pruefziffer. Das Laengen- und Musterkriterium
    der deutschen IBAN ist eine eigene Regel (R-003) und steht in
    :func:`hat_deutsches_format`.

    Args:
        iban: IBAN in beliebiger Schreibweise.

    Returns:
        ``True``, wenn die Pruefziffer stimmt, sonst ``False``. Die Funktion
        wirft keine Ausnahme — ein unbrauchbarer Wert ist ein Befund, kein Absturz.
    """
    zahl = _numerische_darstellung(normalisiere(iban))
    if zahl is None:
        return False
    return zahl % _MODULUS == 1


def hat_deutsches_format(iban: str) -> bool:
    r"""Prueft das Muster der deutschen IBAN: ``^DE\d{20}$`` (R-003).

    Args:
        iban: IBAN, wie sie in der Rohschicht steht — ohne Normalisierung, denn
            eingestreute Leerzeichen sind hier bereits ein Formatverstoss.

    Returns:
        ``True`` bei genau 22 Zeichen im geforderten Muster.
    """
    return bool(_MUSTER_DE.match(iban))


def berechne_pruefziffer(bankleitzahl: str, kontonummer: str) -> str:
    """Berechnet die zweistellige Pruefziffer einer deutschen IBAN.

    Args:
        bankleitzahl: Achtstellige Bankleitzahl.
        kontonummer: Kontonummer mit hoechstens zehn Ziffern; kuerzere Nummern
            werden links mit Nullen aufgefuellt.

    Returns:
        Die Pruefziffer als zweistellige Zeichenkette, zum Beispiel ``"89"``.

    Raises:
        IbanFehler: Wenn Bankleitzahl oder Kontonummer nicht rein numerisch
            sind oder die zulaessige Laenge ueberschreiten.
    """
    if not _MUSTER_ZIFFERN.match(bankleitzahl) or len(bankleitzahl) != _BLZ_LAENGE:
        raise IbanFehler(f"Bankleitzahl muss aus {_BLZ_LAENGE} Ziffern bestehen: {bankleitzahl!r}")
    if not _MUSTER_ZIFFERN.match(kontonummer) or len(kontonummer) > _KONTO_LAENGE:
        raise IbanFehler(
            f"Kontonummer muss aus hoechstens {_KONTO_LAENGE} Ziffern bestehen: {kontonummer!r}"
        )
    bban = bankleitzahl + kontonummer.rjust(_KONTO_LAENGE, "0")
    rest = int(bban + _LAENDERKENNUNG_DE_NUMERISCH) % _MODULUS
    return f"{98 - rest:02d}"


def baue_iban(bankleitzahl: str, kontonummer: str) -> str:
    """Setzt eine gueltige deutsche IBAN aus Bankleitzahl und Kontonummer zusammen.

    Args:
        bankleitzahl: Achtstellige Bankleitzahl.
        kontonummer: Kontonummer mit hoechstens zehn Ziffern.

    Returns:
        Die vollstaendige IBAN mit 22 Zeichen.

    Raises:
        IbanFehler: Wenn die Bestandteile nicht verarbeitbar sind.
    """
    pruefziffer = berechne_pruefziffer(bankleitzahl, kontonummer)
    return f"DE{pruefziffer}{bankleitzahl}{kontonummer.rjust(_KONTO_LAENGE, '0')}"
