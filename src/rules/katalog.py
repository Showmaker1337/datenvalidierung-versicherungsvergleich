"""Registry aller Regeln des Katalogs.

Der Katalog ist das **Design-Artefakt der Bachelorarbeit**. Er wird vor der
Implementierung des Fehlerinjektors eingefroren (Git-Tag ``freeze-regelkatalog``),
und ``scripts/export_katalog.py`` erzeugt daraus die Mapping-Tabelle im Anhang.

Dieses Modul fuegt die fuenf Gruppenmodule zusammen und prueft die Zusammenstellung
**beim Import**. Die Pruefung ist kein Beiwerk: Ein vergessener Eintrag, eine
doppelte Kennung oder eine Regel in der falschen Gruppe wuerden sonst erst in der
Ergebnistabelle auffallen — also dann, wenn die Messung schon gelaufen ist.

Geprueft wird gegen die festen ID-Bereiche aus ``spec/02_regelkatalog.md``:

======================  =========  ========
Bereich                 Achse A    Anzahl
======================  =========  ========
R-001 bis R-025         G1               25
R-026 bis R-042         G2               17
R-043 bis R-048         G3                6
R-049 bis R-051         G4                3
R-052 bis R-058         G5                7
======================  =========  ========
"""

from __future__ import annotations

import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from src.rules import g1_attribut, g2_satz, g3_relation, g4_relationen, g5_quellen
from src.rules.modell import RegelFehler

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping

    from src.rules.modell import Regel

__all__ = [
    "GRUPPENBEREICHE",
    "KATALOG",
    "REGELN_JE_GRUPPE",
    "REGEL_JE_ID",
    "alle_regeln",
    "regel",
]

#: Zulaessiges Muster einer Regelkennung.
_MUSTER_REGEL_ID: Final[re.Pattern[str]] = re.compile(r"^R-(\d{3})$")

#: Fester ID-Bereich je Gruppe (spec/02, Kopfabschnitt): Gruppe auf (erste, letzte).
GRUPPENBEREICHE: Final[Mapping[str, tuple[int, int]]] = MappingProxyType(
    {
        "G1": (1, 25),
        "G2": (26, 42),
        "G3": (43, 48),
        "G4": (49, 51),
        "G5": (52, 58),
    }
)


def _zusammenstellen() -> tuple[Regel, ...]:
    """Fuegt die Gruppenmodule in der Reihenfolge der Regelkennungen zusammen."""
    gesammelt = (
        *g1_attribut.REGELN,
        *g2_satz.REGELN,
        *g3_relation.REGELN,
        *g4_relationen.REGELN,
        *g5_quellen.REGELN,
    )
    return tuple(sorted(gesammelt, key=lambda eintrag: eintrag.regel_id))


def _nummer(regel_id: str) -> int:
    """Liest die laufende Nummer einer Regelkennung."""
    treffer = _MUSTER_REGEL_ID.match(regel_id)
    if treffer is None:
        raise RegelFehler(f"Unzulaessige Regelkennung: {regel_id!r}. Erwartet wird R-0xx.")
    return int(treffer.group(1))


def _pruefe(regeln: tuple[Regel, ...]) -> None:
    """Prueft Vollstaendigkeit, Eindeutigkeit und Gruppenzuordnung des Katalogs.

    Raises:
        RegelFehler: Bei doppelter Kennung, fehlender Regel, ueberzaehliger Regel
            oder falscher Gruppenzuordnung. Bewusst ein Abbruch beim Import: Ein
            unvollstaendiger Katalog darf nicht messen.
    """
    kennungen = [eintrag.regel_id for eintrag in regeln]
    doppelt = sorted({kennung for kennung in kennungen if kennungen.count(kennung) > 1})
    if doppelt:
        raise RegelFehler(f"Doppelte Regelkennungen im Katalog: {doppelt}")

    erste = min(bereich[0] for bereich in GRUPPENBEREICHE.values())
    letzte = max(bereich[1] for bereich in GRUPPENBEREICHE.values())
    erwartet = {f"R-{nummer:03d}" for nummer in range(erste, letzte + 1)}
    fehlend = sorted(erwartet - set(kennungen))
    if fehlend:
        raise RegelFehler(f"Im Katalog fehlen die Regeln: {fehlend}")
    ueberzaehlig = sorted(set(kennungen) - erwartet)
    if ueberzaehlig:
        raise RegelFehler(
            f"Der Katalog enthaelt Regeln ausserhalb von R-{erste:03d} bis R-{letzte:03d}: "
            f"{ueberzaehlig}. Der Katalog ist verbindlich; fehlende Regeln werden gemeldet, "
            "nicht ergaenzt (CLAUDE.md, Abschnitt 7)."
        )

    for eintrag in regeln:
        nummer = _nummer(eintrag.regel_id)
        unten, oben = GRUPPENBEREICHE[eintrag.granularitaet]
        if not unten <= nummer <= oben:
            raise RegelFehler(
                f"{eintrag.regel_id} traegt die Granularitaet {eintrag.granularitaet}, deren "
                f"ID-Bereich R-{unten:03d} bis R-{oben:03d} lautet"
            )


#: Alle Regeln des Katalogs, nach Regelkennung geordnet.
KATALOG: Final[tuple[Regel, ...]] = _zusammenstellen()
_pruefe(KATALOG)

#: Regel je Kennung.
REGEL_JE_ID: Final[Mapping[str, Regel]] = MappingProxyType(
    {eintrag.regel_id: eintrag for eintrag in KATALOG}
)

#: Regeln je Gruppe, in Katalogreihenfolge.
REGELN_JE_GRUPPE: Final[Mapping[str, tuple[Regel, ...]]] = MappingProxyType(
    {
        gruppe: tuple(eintrag for eintrag in KATALOG if eintrag.granularitaet == gruppe)
        for gruppe in GRUPPENBEREICHE
    }
)


def alle_regeln() -> tuple[Regel, ...]:
    """Gibt alle Regeln des Katalogs in Kennungsreihenfolge zurueck."""
    return KATALOG


def regel(regel_id: str) -> Regel:
    """Gibt eine einzelne Regel zurueck.

    Args:
        regel_id: Kennung, zum Beispiel ``"R-031"``.

    Returns:
        Die Regel.

    Raises:
        RegelFehler: Wenn die Kennung nicht im Katalog steht.
    """
    if regel_id not in REGEL_JE_ID:
        raise RegelFehler(f"Unbekannte Regel: {regel_id!r}")
    return REGEL_JE_ID[regel_id]
