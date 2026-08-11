"""F3 — Wertebereichs- und Katalogverletzung (``spec/03``, Abschnitt 2).

Empirische Ursachen:

* **Falsche Schluesseltabelle.** Ein Vorsystem kennt einen Schluessel, den der
  GDV-Katalog nicht fuehrt, oder verwendet eine hausinterne Nummerierung. Das
  ist die Ursache hinter F3-d und F3-e: Die Zahlweisen 3 und 7 gibt es im
  Katalog nicht, sie liegen aber mitten im Zahlenbereich der gueltigen
  Schluessel. Wer nur die Spanne prueft, sieht sie nicht.
* **Bereichsueberschreitung** durch eine Ziffernverwechslung oder eine
  Nummerierung, die bei null statt bei eins beginnt (F3-a, F3-b, F3-f, F3-i).
* **Typverwechslung.** Ein Bezeichner wandert mitsamt seines Praefixes in ein
  numerisches Feld (F3-c) oder verliert es (F3-g).

Die Varianten F3-d und F3-e sind das Lehrbuchbeispiel des Katalogs und der Grund,
warum eine reine Bereichspruefung nicht genuegt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from src.common.wertebereiche import REGIONALKLASSE_HP, REGIONALKLASSE_TK, REGIONALKLASSE_VK
from src.injector.modell import Fehlerklasse, Variante, Zielart
from src.injector.rohwerte import ganzzahl_schreiben
from src.injector.varianten.bausteine import einzelne_zelle, kandidaten_aus_feldern

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence

    from numpy.random import Generator

    from src.injector.modell import Aenderung, AnwendungsFunktion, Injektionskontext, Kandidat

__all__ = ["VARIANTEN"]

#: Typklassenfelder der Kfz-Risikozeile.
_TYPKLASSEN: Final[tuple[tuple[str, str], ...]] = (
    ("risiko_kfz", "typklasse_hp"),
    ("risiko_kfz", "typklasse_tk"),
    ("risiko_kfz", "typklasse_vk"),
)

#: Regionalklassenfelder samt ihrer Obergrenze aus dem GDV-Verzeichnis.
_REGIONALKLASSEN: Final[Mapping[str, int]] = {
    "regionalklasse_hp": REGIONALKLASSE_HP[1],
    "regionalklasse_tk": REGIONALKLASSE_TK[1],
    "regionalklasse_vk": REGIONALKLASSE_VK[1],
}

#: Schadenfreiheitsklassenfelder.
_SF_KLASSEN: Final[tuple[tuple[str, str], ...]] = (
    ("risiko_kfz", "sf_klasse_hp"),
    ("risiko_kfz", "sf_klasse_vk"),
)

#: Weit ausserhalb jeder Typklassenspanne (Variante F3-a).
_TYPKLASSE_WEIT_AUSSERHALB: Final[int] = 99
#: Knapp unterhalb der Untergrenze aller drei Typklassenspannen (Variante F3-b).
_TYPKLASSE_KNAPP_DARUNTER: Final[int] = 9
#: Praefix, mit dem eine Typklasse zum Text wird (Variante F3-c).
_TYPKLASSE_PRAEFIX: Final[str] = "TK"
#: Zahlweisen, die der GDV-Katalog nicht kennt (Varianten F3-d und F3-e).
_ZAHLWEISE_OHNE_KATALOG: Final[tuple[str, str]] = ("3", "7")
#: Praefix der numerischen Schadenfreiheitsklassen.
_SF_PRAEFIX: Final[str] = "SF"
#: Bauartklasse, die GDV Anlage 12 nicht fuehrt (Variante F3-h).
_BAUARTKLASSE_OHNE_KATALOG: Final[str] = "J"
#: ZUERS-Zone ausserhalb der vier Gefaehrdungsklassen (Variante F3-f).
_ZUERS_AUSSERHALB: Final[str] = "5"
#: Untergrenze, die eine bei null beginnende Nummerierung erzeugt (Variante F3-i).
_REGIONALKLASSE_NULL: Final[str] = "0"


def _kandidaten_typklasse(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Alle gefuellten Typklassenfelder."""
    return kandidaten_aus_feldern(kontext, _TYPKLASSEN)


def _kandidaten_zahlweise(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Alle gefuellten Zahlweisen."""
    return kandidaten_aus_feldern(kontext, (("anfrage", "zahlweise"),))


def _kandidaten_zuers(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Alle gefuellten ZUERS-Zonen."""
    return kandidaten_aus_feldern(kontext, (("risiko_hausrat", "zuers_zone"),))


def _kandidaten_bauartklasse(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Alle gefuellten Bauartklassen."""
    return kandidaten_aus_feldern(kontext, (("risiko_hausrat", "bauartklasse"),))


def _kandidaten_sf_numerisch(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Schadenfreiheitsklassen der Form ``SFn`` — nur dort laesst sich das Praefix verlieren."""
    return kandidaten_aus_feldern(
        kontext, _SF_KLASSEN, wertbedingung=lambda wert: wert.startswith(_SF_PRAEFIX)
    )


def _kandidaten_regionalklasse(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Alle gefuellten Regionalklassenfelder."""
    return kandidaten_aus_feldern(
        kontext, tuple(("risiko_kfz", spalte) for spalte in _REGIONALKLASSEN)
    )


def _fester_text(wert: str) -> AnwendungsFunktion:
    """Baut eine Anwendungsfunktion, die immer denselben Rohwert schreibt.

    Args:
        wert: Zu schreibender Rohwert.

    Returns:
        Die Anwendungsfunktion der Variante.
    """

    def anwenden(
        _kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
    ) -> Aenderung | None:
        return einzelne_zelle(kandidat, wert)

    return anwenden


def _typklasse_als_text(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F3-c: Die Typklasse traegt ihr Praefix mit — ein Typ-, kein Bereichsfehler."""
    if kandidat.spalte is None:
        return None
    wert = kontext.wert(kandidat.entitaet, kandidat.row_id, kandidat.spalte)
    return einzelne_zelle(kandidat, _TYPKLASSE_PRAEFIX + wert)


def _sf_ohne_praefix(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F3-g: Die Schadenfreiheitsklasse steht als blosse Zahl."""
    if kandidat.spalte is None:
        return None
    wert = kontext.wert(kandidat.entitaet, kandidat.row_id, kandidat.spalte)
    return einzelne_zelle(kandidat, wert.removeprefix(_SF_PRAEFIX))


def _regionalklasse_ausserhalb(
    _kontext: Injektionskontext, kandidat: Kandidat, rng: Generator
) -> Aenderung | None:
    """F3-i: Regionalklasse auf null oder ueber die Klassenobergrenze."""
    if kandidat.spalte is None:
        return None
    if bool(rng.integers(0, 2)):
        return einzelne_zelle(kandidat, _REGIONALKLASSE_NULL)
    obergrenze = _REGIONALKLASSEN[kandidat.spalte]
    return einzelne_zelle(kandidat, ganzzahl_schreiben(obergrenze + 1))


VARIANTEN: Sequence[Variante] = (
    Variante(
        variante_id="F3-a",
        fehlerklasse=Fehlerklasse.F3,
        zielart=Zielart.ZELLE,
        beschreibung="Typklasse auf 99 — weit ausserhalb der Spanne",
        ursache="Ziffernverwechslung oder Platzhalter aus einem Vorsystem",
        kandidaten=_kandidaten_typklasse,
        anwenden=_fester_text(ganzzahl_schreiben(_TYPKLASSE_WEIT_AUSSERHALB)),
    ),
    Variante(
        variante_id="F3-b",
        fehlerklasse=Fehlerklasse.F3,
        zielart=Zielart.ZELLE,
        beschreibung="Typklasse auf 9 — knapp unterhalb der Untergrenze",
        ursache="Hausinterne Nummerierung, die bei eins statt bei zehn beginnt",
        kandidaten=_kandidaten_typklasse,
        anwenden=_fester_text(ganzzahl_schreiben(_TYPKLASSE_KNAPP_DARUNTER)),
    ),
    Variante(
        variante_id="F3-c",
        fehlerklasse=Fehlerklasse.F3,
        zielart=Zielart.ZELLE,
        beschreibung='Typklasse als Text, etwa "TK12"',
        ursache="Bezeichner aus der Anzeige uebernommen statt des Schluesselwerts",
        kandidaten=_kandidaten_typklasse,
        anwenden=_typklasse_als_text,
    ),
    Variante(
        variante_id="F3-d",
        fehlerklasse=Fehlerklasse.F3,
        zielart=Zielart.ZELLE,
        beschreibung="Zahlweise auf 3 — im Zahlenbereich, aber nicht im Katalog",
        ursache="Vorsystem fuehrt eine eigene Zahlweisentabelle",
        kandidaten=_kandidaten_zahlweise,
        anwenden=_fester_text(_ZAHLWEISE_OHNE_KATALOG[0]),
    ),
    Variante(
        variante_id="F3-e",
        fehlerklasse=Fehlerklasse.F3,
        zielart=Zielart.ZELLE,
        beschreibung="Zahlweise auf 7 — im Zahlenbereich, aber nicht im Katalog",
        ursache="Vorsystem fuehrt eine eigene Zahlweisentabelle",
        kandidaten=_kandidaten_zahlweise,
        anwenden=_fester_text(_ZAHLWEISE_OHNE_KATALOG[1]),
    ),
    Variante(
        variante_id="F3-f",
        fehlerklasse=Fehlerklasse.F3,
        zielart=Zielart.ZELLE,
        beschreibung="ZUERS-Zone auf 5",
        ursache="Erweiterte Zonenskala eines Drittanbieters uebernommen",
        kandidaten=_kandidaten_zuers,
        anwenden=_fester_text(_ZUERS_AUSSERHALB),
    ),
    Variante(
        variante_id="F3-g",
        fehlerklasse=Fehlerklasse.F3,
        zielart=Zielart.ZELLE,
        beschreibung="SF-Klasse als blosse Zahl statt SFn",
        ursache="Numerische Uebernahme eines gemischt alphanumerischen Schluessels",
        kandidaten=_kandidaten_sf_numerisch,
        anwenden=_sf_ohne_praefix,
    ),
    Variante(
        variante_id="F3-h",
        fehlerklasse=Fehlerklasse.F3,
        zielart=Zielart.ZELLE,
        beschreibung='Bauartklasse "J" — existiert in GDV Anlage 12 nicht',
        ursache="Fortgeschriebene Buchstabenreihe ohne Blick in den Katalog",
        kandidaten=_kandidaten_bauartklasse,
        anwenden=_fester_text(_BAUARTKLASSE_OHNE_KATALOG),
    ),
    Variante(
        variante_id="F3-i",
        fehlerklasse=Fehlerklasse.F3,
        zielart=Zielart.ZELLE,
        beschreibung="Regionalklasse auf 0 oder ueber die Klassenobergrenze",
        ursache="Nummerierung ab null oder Verwechslung der drei Klassenspannen",
        kandidaten=_kandidaten_regionalklasse,
        anwenden=_regionalklasse_ausserhalb,
    ),
)
