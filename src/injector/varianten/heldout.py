"""HO1 und HO2 — die beiden Held-out-Klassen (``spec/03``, Abschnitt 2).

Beide Klassen sind bewusst so gebaut, dass der Regelkatalog sie **nicht** finden
kann. Der erwartete Recall liegt bei etwa null. Sie sind kein Versaeumnis,
sondern die Kontrollbedingung des Experiments: Ohne sie liesse sich nicht
zeigen, dass der gemessene Recall an den Regeln liegt und nicht daran, dass jede
Verfaelschung irgendwie auffaellt.

HO1 — semantische Duplikate
---------------------------

Zwei Saetze meinen dieselbe Person, stehen aber nicht Zeichen fuer Zeichen gleich:
"Mueller" neben "Müller", "Hauptstr." neben "Hauptstraße", ein Zeichendreher im
Vornamen. Empirische Ursache sind verschiedene Erfassungswege — ein Formular
ohne Umlaute, eine telefonische Aufnahme, ein Import aus einem System mit
eingeschraenktem Zeichensatz. Ein exakter Duplikatabgleich sieht sie nicht; dafuer
braeuchte es ein Aehnlichkeitsmass, und genau das hat der Katalog nicht.

HO2 — semantisch falsch, formal gueltig
---------------------------------------

Der Wert ist in jeder Hinsicht zulaessig, er ist nur nicht der richtige. Eine
existierende Postleitzahl mit passendem Ort — nur eben die falsche. Ein
Beitragstupel, das kohaerent um fuenfzehn Prozent gesenkt wurde und im plausiblen
Korridor bleibt. Beide Faelle sind ohne die wahre Auspraegung nicht entscheidbar.

Auch HO2-b skaliert **kohaerent** und zieht die Rangfolge mit. Eine Senkung nur
des Zahlbeitrags verletzte die Ratenpruefung immer — der Ratenzuschlag betraegt
hoechstens acht Prozent — und waere damit zu hundert Prozent erkennbar. Als
Held-out-Klasse waere sie dann unbrauchbar.
"""

from __future__ import annotations

from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from src.injector.modell import (
    Aenderung,
    Fehlerklasse,
    Kandidat,
    Satzaenderung,
    Variante,
    Zellaenderung,
    Zielart,
)
from src.injector.varianten.bausteine import kopiere_zeile, neue_uuid, satz_kandidaten
from src.injector.varianten.f8_einheiten import (
    BEITRAGSZUSATZ,
    kandidaten_beitragstupel,
    skalierung,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence

    from numpy.random import Generator

    from src.injector.modell import Injektionskontext

__all__ = ["VARIANTEN"]

#: Ersetzungen eines Erfassungswegs ohne deutsche Sonderzeichen (Variante HO1-a).
_UMSCHRIFT: Final[Mapping[str, str]] = MappingProxyType(
    {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
    }
)

#: Abkuerzungen, wie sie eine telefonische Aufnahme erzeugt (Variante HO1-a).
_ABKUERZUNGEN: Final[Mapping[str, str]] = MappingProxyType(
    {"straße": "str.", "Straße": "Str.", "strasse": "str.", "Strasse": "Str."}
)

#: Mindestlaenge, ab der sich ein Zeichendreher bilden laesst (Variante HO1-b).
_MINDESTLAENGE_DREHER: Final[int] = 2

#: Mindestzahl bekannter Anschriften, damit sich eine andere waehlen laesst (HO2-a).
_MINDESTANZAHL_ANSCHRIFTEN: Final[int] = 2

#: Faktor der Beitragssenkung um fuenfzehn Prozent (Variante HO2-b).
_FAKTOR_SENKUNG: Final[Decimal] = Decimal("0.85")


# ---------------------------------------------------------------------------
# HO1 — semantische Duplikate
# ---------------------------------------------------------------------------


def _umschrift(wert: str) -> str:
    """Ersetzt Umlaute und Eszett durch ihre Ersatzschreibweise."""
    for zeichen, ersatz in _UMSCHRIFT.items():
        wert = wert.replace(zeichen, ersatz)
    return wert


def _abgekuerzt(wert: str) -> str:
    """Kuerzt Strassenbezeichnungen ab."""
    for lang, kurz in _ABKUERZUNGEN.items():
        wert = wert.replace(lang, kurz)
    return wert


def _schreibvariante(kontext: Injektionskontext, row_id: int) -> dict[str, str] | None:
    """Bildet die Schreibvariante eines Personensatzes, oder ``None``, wenn sie gleich bliebe."""
    nachname = kontext.wert("person", row_id, "nachname")
    strasse = kontext.wert("person", row_id, "strasse")
    neuer_nachname = _umschrift(nachname)
    neue_strasse = _abgekuerzt(_umschrift(strasse))
    if neuer_nachname == nachname and neue_strasse == strasse:
        return None
    return {"nachname": neuer_nachname, "strasse": neue_strasse}


def _kandidaten_schreibvariante(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Personensaetze, deren Name oder Anschrift eine Schreibvariante zulaesst."""
    return satz_kandidaten(
        kontext,
        "person",
        zeilenbedingung=lambda ktx, _entitaet, row_id: _schreibvariante(ktx, row_id) is not None,
    )


def _dreher(wert: str, rng: Generator) -> str | None:
    """Vertauscht zwei benachbarte, verschiedene Zeichen."""
    stellen = [i for i in range(len(wert) - 1) if wert[i] != wert[i + 1]]
    if not stellen:
        return None
    stelle = stellen[int(rng.integers(0, len(stellen)))]
    return wert[:stelle] + wert[stelle + 1] + wert[stelle] + wert[stelle + 2 :]


def _kandidaten_tippfehler(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Personensaetze, deren Vorname einen Zeichendreher zulaesst."""
    return satz_kandidaten(
        kontext,
        "person",
        zeilenbedingung=lambda ktx, _entitaet, row_id: _dreherfaehig(
            ktx.wert("person", row_id, "vorname")
        ),
    )


def _dreherfaehig(wert: str) -> bool:
    """Trifft zu, wenn der Wert zwei benachbarte, verschiedene Zeichen enthaelt."""
    if len(wert) < _MINDESTLAENGE_DREHER:
        return False
    return any(wert[i] != wert[i + 1] for i in range(len(wert) - 1))


def _person_kopie(
    kontext: Injektionskontext, kandidat: Kandidat, rng: Generator, aenderungen: Mapping[str, str]
) -> Aenderung:
    """Baut die Kopie eines Personensatzes mit den uebergebenen Abweichungen."""
    werte = kopiere_zeile(kontext, kandidat.entitaet, kandidat.row_id)
    werte["person_id"] = neue_uuid(rng)
    werte.update(aenderungen)
    return Aenderung(
        saetze=(
            Satzaenderung(
                entitaet=kandidat.entitaet, referenz_row_id=kandidat.row_id, werte=werte
            ),
        )
    )


def _duplikat_schreibvariante(
    kontext: Injektionskontext, kandidat: Kandidat, rng: Generator
) -> Aenderung | None:
    """HO1-a: Personensatz in einer Schreibvariante ohne Umlaute und mit Abkuerzung."""
    variante = _schreibvariante(kontext, kandidat.row_id)
    if variante is None:
        return None
    return _person_kopie(kontext, kandidat, rng, variante)


def _duplikat_tippfehler(
    kontext: Injektionskontext, kandidat: Kandidat, rng: Generator
) -> Aenderung | None:
    """HO1-b: Personensatz mit einem Zeichendreher im Vornamen."""
    vorname = kontext.wert("person", kandidat.row_id, "vorname")
    verdreht = _dreher(vorname, rng)
    if verdreht is None:
        return None
    return _person_kopie(kontext, kandidat, rng, {"vorname": verdreht})


# ---------------------------------------------------------------------------
# HO2 — semantisch falsch, formal gueltig
# ---------------------------------------------------------------------------


def _kandidaten_anschrift(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Personensaetze mit gefuellter Postleitzahl und gefuelltem Ort."""
    return tuple(
        Kandidat(entitaet="person", row_id=row_id, spalte="plz")
        for row_id in kontext.row_ids["person"]
        if kontext.wert("person", row_id, "plz") and kontext.wert("person", row_id, "ort")
    )


def _andere_anschrift(
    kontext: Injektionskontext, kandidat: Kandidat, rng: Generator
) -> Aenderung | None:
    """HO2-a: Eine andere, ebenfalls existierende Postleitzahl samt passendem Ort."""
    anschriften = kontext.anschriften
    if len(anschriften) < _MINDESTANZAHL_ANSCHRIFTEN:
        return None
    bisher = kontext.wert("person", kandidat.row_id, "plz")
    for _ in range(len(anschriften)):
        plz, ort = anschriften[int(rng.integers(0, len(anschriften)))]
        if plz != bisher:
            return Aenderung(
                zellen=(
                    Zellaenderung("person", kandidat.row_id, "plz", plz),
                    Zellaenderung("person", kandidat.row_id, "ort", ort),
                )
            )
    return None


VARIANTEN: Sequence[Variante] = (
    Variante(
        variante_id="HO1-a",
        fehlerklasse=Fehlerklasse.HO1,
        zielart=Zielart.SATZ,
        beschreibung="Personensatz dupliziert, Name ohne Umlaute und Strasse abgekuerzt",
        ursache="Zweiter Erfassungsweg ohne deutsche Sonderzeichen",
        kandidaten=_kandidaten_schreibvariante,
        anwenden=_duplikat_schreibvariante,
    ),
    Variante(
        variante_id="HO1-b",
        fehlerklasse=Fehlerklasse.HO1,
        zielart=Zielart.SATZ,
        beschreibung="Personensatz dupliziert, Vorname mit Zeichendreher",
        ursache="Tippfehler bei einer zweiten manuellen Erfassung",
        kandidaten=_kandidaten_tippfehler,
        anwenden=_duplikat_tippfehler,
    ),
    Variante(
        variante_id="HO2-a",
        fehlerklasse=Fehlerklasse.HO2,
        zielart=Zielart.ZELLE,
        beschreibung="Postleitzahl durch eine andere existierende ersetzt, Ort mitgezogen",
        ursache="Verwechselte Anschrift; beide Angaben sind fuer sich stimmig",
        kandidaten=_kandidaten_anschrift,
        anwenden=_andere_anschrift,
        zusatzspalten=("ort",),
    ),
    Variante(
        variante_id="HO2-b",
        fehlerklasse=Fehlerklasse.HO2,
        zielart=Zielart.ZELLE,
        beschreibung="Gesamtes Beitragstupel kohaerent um fuenfzehn Prozent gesenkt",
        ursache="Rabattstufe eines anderen Vertrags uebernommen",
        kandidaten=kandidaten_beitragstupel,
        anwenden=skalierung(_FAKTOR_SENKUNG, ganze_anfrage=False),
        zieht_rang_nach=True,
        zusatzspalten=BEITRAGSZUSATZ,
    ),
)
