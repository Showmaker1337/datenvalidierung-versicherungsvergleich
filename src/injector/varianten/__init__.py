"""Registry der sechzig Injektionsvarianten (``spec/03``, Abschnitt 2).

Die Zusammenstellung wird **beim Import** geprueft: Kennungen sind eindeutig, die
Zahl der Varianten je Klasse stimmt mit der Spezifikation ueberein, und jede
Variante gehoert zu genau der Klasse, die ihre Kennung nennt. Ein Tippfehler in
einer ``injektor_variante_id`` faellt damit sofort auf und nicht erst in der
Auswertung, wo eine Variante ohne Treffer wie ein Befund aussaehe.

Die Reihenfolge ist fest: Klassen in der Reihenfolge von
:class:`src.injector.modell.Fehlerklasse`, darin die Varianten in der Reihenfolge
ihrer Kennung. Sie geht in die Zuteilung der Injektionskontingente ein und ist
damit Teil der Reproduzierbarkeit.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from src.injector.modell import Fehlerklasse, InjektionsFehler
from src.injector.varianten import (
    f1_fehlend,
    f2_format,
    f3_wertebereich,
    f4_unmoeglich,
    f5_inkonsistenz,
    f6_duplikate,
    f7_aktualitaet,
    f8_einheiten,
    heldout,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping

    from src.injector.modell import Variante

__all__ = [
    "ALLE_VARIANTEN",
    "ANZAHL_JE_KLASSE",
    "VARIANTEN_JE_KLASSE",
    "variante",
]

#: Sollzahl der Varianten je Klasse (spec/03, Abschnitt 2).
ANZAHL_JE_KLASSE: Final[Mapping[Fehlerklasse, int]] = MappingProxyType(
    {
        Fehlerklasse.F1: 6,
        Fehlerklasse.F2: 12,
        Fehlerklasse.F3: 9,
        Fehlerklasse.F4: 7,
        Fehlerklasse.F5: 9,
        Fehlerklasse.F6: 4,
        Fehlerklasse.F7: 4,
        Fehlerklasse.F8: 5,
        Fehlerklasse.HO1: 2,
        Fehlerklasse.HO2: 2,
    }
)


def _sammle() -> tuple[Variante, ...]:
    """Fuegt die Varianten aller Module zusammen und prueft die Zusammenstellung."""
    gesammelt = [
        *f1_fehlend.VARIANTEN,
        *f2_format.VARIANTEN,
        *f3_wertebereich.VARIANTEN,
        *f4_unmoeglich.VARIANTEN,
        *f5_inkonsistenz.VARIANTEN,
        *f6_duplikate.VARIANTEN,
        *f7_aktualitaet.VARIANTEN,
        *f8_einheiten.VARIANTEN,
        *heldout.VARIANTEN,
    ]

    kennungen = [eintrag.variante_id for eintrag in gesammelt]
    doppelt = sorted({kennung for kennung in kennungen if kennungen.count(kennung) > 1})
    if doppelt:
        raise InjektionsFehler(f"Doppelte injektor_variante_id: {doppelt}")

    for eintrag in gesammelt:
        praefix = eintrag.variante_id.split("-")[0]
        if praefix != eintrag.fehlerklasse.value:
            raise InjektionsFehler(
                f"Variante {eintrag.variante_id} ist der Klasse "
                f"{eintrag.fehlerklasse.value} zugeordnet"
            )

    for klasse, soll in ANZAHL_JE_KLASSE.items():
        ist = sum(1 for eintrag in gesammelt if eintrag.fehlerklasse is klasse)
        if ist != soll:
            raise InjektionsFehler(
                f"Klasse {klasse.value}: {ist} Varianten implementiert, "
                f"{soll} nach spec/03 erwartet"
            )

    return tuple(
        sorted(
            gesammelt,
            key=lambda eintrag: (
                list(Fehlerklasse).index(eintrag.fehlerklasse),
                eintrag.variante_id,
            ),
        )
    )


#: Alle Varianten in fester Reihenfolge.
ALLE_VARIANTEN: Final[tuple[Variante, ...]] = _sammle()

#: Die Varianten je Fehlerklasse in fester Reihenfolge.
VARIANTEN_JE_KLASSE: Final[Mapping[Fehlerklasse, tuple[Variante, ...]]] = MappingProxyType(
    {
        klasse: tuple(
            eintrag for eintrag in ALLE_VARIANTEN if eintrag.fehlerklasse is klasse
        )
        for klasse in Fehlerklasse
    }
)


def variante(variante_id: str) -> Variante:
    """Gibt eine Variante zu ihrer Kennung zurueck.

    Args:
        variante_id: Kennung, zum Beispiel ``F3-d``.

    Returns:
        Die Variante.

    Raises:
        InjektionsFehler: Wenn die Kennung unbekannt ist. Bewusst kein
            Ersatzwert — eine unbekannte Kennung ist ein Tippfehler.
    """
    for eintrag in ALLE_VARIANTEN:
        if eintrag.variante_id == variante_id:
            return eintrag
    raise InjektionsFehler(
        f"Unbekannte injektor_variante_id: {variante_id!r}. "
        f"Bekannt sind: {[eintrag.variante_id for eintrag in ALLE_VARIANTEN]}"
    )
