"""F2 — Format- und Syntaxverletzung (``spec/03``, Abschnitt 2).

Empirische Ursachen, nach Haeufigkeit geordnet:

* **Typkonvertierung.** Eine Postleitzahl laeuft durch eine Tabellenkalkulation
  oder einen ungetypten Import und verliert die fuehrende Null (F2-a). Ein
  Datumsfeld wird als Seriennummer exportiert (F2-i).
* **Fremdes Format.** Eine Schnittstelle liefert ISO-Datumsangaben, das
  Zielsystem erwartet ``TTMMJJJJ`` (F2-h).
* **Zeichendreher und Tippfehler** bei manueller Erfassung — sie brechen
  Pruefziffern, ohne das Format anzutasten (F2-c).
* **Feldlaengen.** Abgeschnittene oder aufgefuellte Werte aus Fixed-Length-Formaten
  (F2-b, F2-d, F2-e, F2-j).

Alle Varianten arbeiten auf der **Rohschicht**. Auf typisierten Spalten waeren
sie nicht schreibbar: In einer ``datetime64``-Spalte kann kein 31. Februar stehen
(``spec/01``, Abschnitt 6).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from src.common.serialisierung import FELDTYP_JE_SPALTE, Feldtyp
from src.common.wertebereiche import BIC_LAENGEN, HSN_LAENGE, IBAN_LAENGE_DE, PLZ_LAENGE
from src.injector.modell import Fehlerklasse, Variante, Zielart
from src.injector.rohwerte import excel_serial, ganzzahl_schreiben, tag_lesen
from src.injector.varianten.bausteine import (
    einzelne_zelle,
    felder_ohne_schluessel,
    kandidaten_aus_feldern,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    from numpy.random import Generator

    from src.injector.modell import Aenderung, Injektionskontext, Kandidat

__all__ = ["VARIANTEN"]

#: Feld der Postleitzahl.
_PLZ: Final[tuple[tuple[str, str], ...]] = (("person", "plz"),)
#: Feld der IBAN.
_IBAN: Final[tuple[tuple[str, str], ...]] = (("zahlung", "iban"),)
#: Feld der BIC.
_BIC: Final[tuple[tuple[str, str], ...]] = (("zahlung", "bic"),)
#: Feld der E-Mail-Adresse.
_EMAIL: Final[tuple[tuple[str, str], ...]] = (("person", "email"),)
#: Feld der Herstellerschluesselnummer.
_HSN: Final[tuple[tuple[str, str], ...]] = (("risiko_kfz", "hsn"),)
#: Feld der Typschluesselnummer.
_TSN: Final[tuple[tuple[str, str], ...]] = (("risiko_kfz", "tsn"),)

#: Erste Ziffernstelle der IBAN, ab der verfaelscht wird — hinter dem Laenderkuerzel.
_IBAN_ERSTE_ZIFFER: Final[int] = 2
#: Tag, der in keinem Februar existiert (Variante F2-f).
_TAG_OHNE_KALENDER: Final[str] = "31"
#: Monat, den es nicht gibt (Variante F2-g).
_MONAT_OHNE_KALENDER: Final[str] = "13"
#: Fuellzeichen, mit dem eine BIC auf eine unzulaessige Laenge gebracht wird.
_BIC_FUELLZEICHEN: Final[str] = "X"


def _datumsfelder() -> tuple[tuple[str, str], ...]:
    """Gibt alle Datumsfelder ausserhalb der Schluesselspalten zurueck."""
    return tuple(
        (entitaet, spalte)
        for entitaet, spalte in felder_ohne_schluessel()
        if FELDTYP_JE_SPALTE[spalte] is Feldtyp.DATUM
    )


# ---------------------------------------------------------------------------
# Postleitzahl
# ---------------------------------------------------------------------------


def _fuehrende_null(wert: str) -> bool:
    """Trifft auf Postleitzahlen zu, die eine fuehrende Null tragen."""
    return wert.isdigit() and wert.startswith("0")


def _kandidaten_plz_null(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Postleitzahlen mit fuehrender Null — nur dort wirkt der Typverlust."""
    return kandidaten_aus_feldern(kontext, _PLZ, wertbedingung=_fuehrende_null)


def _kandidaten_plz(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Alle fuenfstelligen Postleitzahlen."""
    return kandidaten_aus_feldern(
        kontext, _PLZ, wertbedingung=lambda wert: len(wert) == PLZ_LAENGE and wert.isdigit()
    )


def _plz_als_ganzzahl(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F2-a: Die Postleitzahl lief durch einen Ganzzahltyp und verlor die fuehrende Null."""
    if kandidat.spalte is None:
        return None
    wert = kontext.wert(kandidat.entitaet, kandidat.row_id, kandidat.spalte)
    return einzelne_zelle(kandidat, ganzzahl_schreiben(int(wert)))


def _plz_falsche_laenge(
    kontext: Injektionskontext, kandidat: Kandidat, rng: Generator
) -> Aenderung | None:
    """F2-b: Die Postleitzahl hat vier oder sechs Ziffern."""
    if kandidat.spalte is None:
        return None
    wert = kontext.wert(kandidat.entitaet, kandidat.row_id, kandidat.spalte)
    if bool(rng.integers(0, 2)):
        return einzelne_zelle(kandidat, wert[:-1])
    return einzelne_zelle(kandidat, wert + str(int(rng.integers(0, 10))))


# ---------------------------------------------------------------------------
# IBAN und BIC
# ---------------------------------------------------------------------------


def _deutsche_iban(wert: str) -> bool:
    """Trifft auf IBANs im deutschen Format zu."""
    return len(wert) == IBAN_LAENGE_DE and wert.startswith("DE") and wert[2:].isdigit()


def _kandidaten_iban(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Alle IBANs im deutschen Format."""
    return kandidaten_aus_feldern(kontext, _IBAN, wertbedingung=_deutsche_iban)


def _iban_ziffer_verdreht(
    kontext: Injektionskontext, kandidat: Kandidat, rng: Generator
) -> Aenderung | None:
    """F2-c: Eine Ziffer ist vertippt — die Pruefsumme bricht, das Format bleibt."""
    if kandidat.spalte is None:
        return None
    wert = kontext.wert(kandidat.entitaet, kandidat.row_id, kandidat.spalte)
    stelle = int(rng.integers(_IBAN_ERSTE_ZIFFER, IBAN_LAENGE_DE))
    versatz = int(rng.integers(1, 10))
    neue_ziffer = str((int(wert[stelle]) + versatz) % 10)
    return einzelne_zelle(kandidat, wert[:stelle] + neue_ziffer + wert[stelle + 1 :])


def _iban_falsche_laenge(
    kontext: Injektionskontext, kandidat: Kandidat, rng: Generator
) -> Aenderung | None:
    """F2-d: Die IBAN hat 21 oder 23 Zeichen."""
    if kandidat.spalte is None:
        return None
    wert = kontext.wert(kandidat.entitaet, kandidat.row_id, kandidat.spalte)
    if bool(rng.integers(0, 2)):
        stelle = int(rng.integers(_IBAN_ERSTE_ZIFFER, IBAN_LAENGE_DE))
        return einzelne_zelle(kandidat, wert[:stelle] + wert[stelle + 1 :])
    stelle = int(rng.integers(_IBAN_ERSTE_ZIFFER, IBAN_LAENGE_DE + 1))
    ziffer = str(int(rng.integers(0, 10)))
    return einzelne_zelle(kandidat, wert[:stelle] + ziffer + wert[stelle:])


def _kandidaten_bic(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Alle BIC mit zulaessiger Laenge."""
    return kandidaten_aus_feldern(
        kontext, _BIC, wertbedingung=lambda wert: len(wert) in BIC_LAENGEN
    )


def _bic_falsche_laenge(
    kontext: Injektionskontext, kandidat: Kandidat, rng: Generator
) -> Aenderung | None:
    """F2-e: Die BIC hat 9 oder 10 Zeichen — beide Laengen gibt es nach ISO 9362 nicht."""
    if kandidat.spalte is None:
        return None
    wert = kontext.wert(kandidat.entitaet, kandidat.row_id, kandidat.spalte)
    kurz, lang = BIC_LAENGEN
    ziel = kurz + 1 + int(rng.integers(0, 2))
    if len(wert) == lang:
        return einzelne_zelle(kandidat, wert[:ziel])
    return einzelne_zelle(kandidat, wert + _BIC_FUELLZEICHEN * (ziel - len(wert)))


# ---------------------------------------------------------------------------
# Datumsfelder
# ---------------------------------------------------------------------------


def _kandidaten_datum(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Alle gefuellten Datumsfelder."""
    return kandidaten_aus_feldern(kontext, _datumsfelder())


def _rohdatum(kontext: Injektionskontext, kandidat: Kandidat) -> str | None:
    """Liest den Rohwert eines Datumsfeldes."""
    if kandidat.spalte is None:
        return None
    return kontext.wert(kandidat.entitaet, kandidat.row_id, kandidat.spalte)


def _kein_kalendertag(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F2-f: Acht Ziffern, aber kein Kalendertag — der 31. Februar."""
    wert = _rohdatum(kontext, kandidat)
    if wert is None or tag_lesen(wert) is None:
        return None
    return einzelne_zelle(kandidat, _TAG_OHNE_KALENDER + "02" + wert[4:8])


def _monat_dreizehn(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F2-g: Monat 13 — typisch fuer eine vertauschte Tag- und Monatsstelle."""
    wert = _rohdatum(kontext, kandidat)
    if wert is None or tag_lesen(wert) is None:
        return None
    return einzelne_zelle(kandidat, wert[0:2] + _MONAT_OHNE_KALENDER + wert[4:8])


def _fremdformat(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F2-h: ISO-Datum statt ``TTMMJJJJ`` — der Wert stammt aus einer anderen Schnittstelle."""
    wert = _rohdatum(kontext, kandidat)
    if wert is None:
        return None
    tag = tag_lesen(wert)
    if tag is None:
        return None
    return einzelne_zelle(kandidat, tag.isoformat())


def _tabellenkalkulation(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F2-i: Seriennummer statt Datum — unformatierter Export aus einer Tabellenkalkulation."""
    wert = _rohdatum(kontext, kandidat)
    if wert is None:
        return None
    tag = tag_lesen(wert)
    if tag is None:
        return None
    return einzelne_zelle(kandidat, ganzzahl_schreiben(excel_serial(tag)))


# ---------------------------------------------------------------------------
# Fahrzeugschluessel und E-Mail
# ---------------------------------------------------------------------------


def _kandidaten_hsn(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Alle vierstelligen Herstellerschluesselnummern."""
    return kandidaten_aus_feldern(
        kontext, _HSN, wertbedingung=lambda wert: len(wert) == HSN_LAENGE
    )


def _hsn_verkuerzt(
    kontext: Injektionskontext, kandidat: Kandidat, rng: Generator
) -> Aenderung | None:
    """F2-j: Die HSN hat drei statt vier Stellen — eine Ziffer ging beim Import verloren."""
    if kandidat.spalte is None:
        return None
    wert = kontext.wert(kandidat.entitaet, kandidat.row_id, kandidat.spalte)
    stelle = int(rng.integers(0, len(wert)))
    return einzelne_zelle(kandidat, wert[:stelle] + wert[stelle + 1 :])


def _kandidaten_tsn(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Typschluesselnummern, die Grossbuchstaben enthalten."""
    return kandidaten_aus_feldern(
        kontext, _TSN, wertbedingung=lambda wert: wert != wert.lower()
    )


def _tsn_kleingeschrieben(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F2-k: Die TSN steht in Kleinbuchstaben — fehlende Normalisierung beim Import."""
    if kandidat.spalte is None:
        return None
    wert = kontext.wert(kandidat.entitaet, kandidat.row_id, kandidat.spalte)
    return einzelne_zelle(kandidat, wert.lower())


def _adressierbar(wert: str) -> bool:
    """Trifft auf E-Mail-Adressen mit Klammeraffe und Punkt in der Domain zu."""
    kopf, trenner, domain = wert.partition("@")
    return bool(kopf) and bool(trenner) and "." in domain


def _kandidaten_email(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Alle E-Mail-Adressen mit Klammeraffe und Punkt in der Domain."""
    return kandidaten_aus_feldern(kontext, _EMAIL, wertbedingung=_adressierbar)


def _email_zerlegt(
    kontext: Injektionskontext, kandidat: Kandidat, rng: Generator
) -> Aenderung | None:
    """F2-l: Der Klammeraffe oder der Punkt in der Domain fehlt."""
    if kandidat.spalte is None:
        return None
    wert = kontext.wert(kandidat.entitaet, kandidat.row_id, kandidat.spalte)
    if bool(rng.integers(0, 2)):
        return einzelne_zelle(kandidat, wert.replace("@", "", 1))
    kopf, _, domain = wert.partition("@")
    stelle = domain.rindex(".")
    return einzelne_zelle(kandidat, f"{kopf}@{domain[:stelle]}{domain[stelle + 1 :]}")


VARIANTEN: Sequence[Variante] = (
    Variante(
        variante_id="F2-a",
        fehlerklasse=Fehlerklasse.F2,
        zielart=Zielart.ZELLE,
        beschreibung="PLZ als Ganzzahl gefuehrt, fuehrende Null verloren",
        ursache="Typkonvertierung in einem ungetypten Import oder in einer Tabellenkalkulation",
        kandidaten=_kandidaten_plz_null,
        anwenden=_plz_als_ganzzahl,
    ),
    Variante(
        variante_id="F2-b",
        fehlerklasse=Fehlerklasse.F2,
        zielart=Zielart.ZELLE,
        beschreibung="PLZ mit vier oder sechs Ziffern",
        ursache="Feldlaenge in einem Fixed-Length-Format falsch abgegriffen",
        kandidaten=_kandidaten_plz,
        anwenden=_plz_falsche_laenge,
    ),
    Variante(
        variante_id="F2-c",
        fehlerklasse=Fehlerklasse.F2,
        zielart=Zielart.ZELLE,
        beschreibung="IBAN mit einer geaenderten Ziffer",
        ursache="Tippfehler bei manueller Erfassung; das Format bleibt unauffaellig",
        kandidaten=_kandidaten_iban,
        anwenden=_iban_ziffer_verdreht,
    ),
    Variante(
        variante_id="F2-d",
        fehlerklasse=Fehlerklasse.F2,
        zielart=Zielart.ZELLE,
        beschreibung="IBAN mit 21 oder 23 Zeichen",
        ursache="Abgeschnittenes oder aufgefuelltes Feld beim Satzartwechsel",
        kandidaten=_kandidaten_iban,
        anwenden=_iban_falsche_laenge,
    ),
    Variante(
        variante_id="F2-e",
        fehlerklasse=Fehlerklasse.F2,
        zielart=Zielart.ZELLE,
        beschreibung="BIC mit 9 oder 10 Zeichen",
        ursache="Fixed-Length-Feld auf eine Laenge gebracht, die ISO 9362 nicht kennt",
        kandidaten=_kandidaten_bic,
        anwenden=_bic_falsche_laenge,
    ),
    Variante(
        variante_id="F2-f",
        fehlerklasse=Fehlerklasse.F2,
        zielart=Zielart.ZELLE,
        beschreibung="Datum 31.02. — acht Ziffern, kein Kalendertag",
        ursache="Erfassungsfehler ohne Kalenderpruefung im Eingabefeld",
        kandidaten=_kandidaten_datum,
        anwenden=_kein_kalendertag,
    ),
    Variante(
        variante_id="F2-g",
        fehlerklasse=Fehlerklasse.F2,
        zielart=Zielart.ZELLE,
        beschreibung="Datum mit Monat 13",
        ursache="Vertauschte Tag- und Monatsstelle bei manueller Erfassung",
        kandidaten=_kandidaten_datum,
        anwenden=_monat_dreizehn,
    ),
    Variante(
        variante_id="F2-h",
        fehlerklasse=Fehlerklasse.F2,
        zielart=Zielart.ZELLE,
        beschreibung="Datum im ISO-Format statt TTMMJJJJ",
        ursache="Wert stammt aus einer Schnittstelle mit anderer Datumskonvention",
        kandidaten=_kandidaten_datum,
        anwenden=_fremdformat,
    ),
    Variante(
        variante_id="F2-i",
        fehlerklasse=Fehlerklasse.F2,
        zielart=Zielart.ZELLE,
        beschreibung="Datum als Seriennummer einer Tabellenkalkulation",
        ursache="Unformatierter Export; die Zelle traegt die Tageszahl statt des Datums",
        kandidaten=_kandidaten_datum,
        anwenden=_tabellenkalkulation,
    ),
    Variante(
        variante_id="F2-j",
        fehlerklasse=Fehlerklasse.F2,
        zielart=Zielart.ZELLE,
        beschreibung="HSN mit drei statt vier Stellen",
        ursache="Ziffer beim Import verloren, etwa durch Ganzzahlkonvertierung",
        kandidaten=_kandidaten_hsn,
        anwenden=_hsn_verkuerzt,
    ),
    Variante(
        variante_id="F2-k",
        fehlerklasse=Fehlerklasse.F2,
        zielart=Zielart.ZELLE,
        beschreibung="TSN in Kleinbuchstaben",
        ursache="Fehlende Normalisierung beim Uebernehmen aus einem Fremdsystem",
        kandidaten=_kandidaten_tsn,
        anwenden=_tsn_kleingeschrieben,
    ),
    Variante(
        variante_id="F2-l",
        fehlerklasse=Fehlerklasse.F2,
        zielart=Zielart.ZELLE,
        beschreibung="E-Mail ohne Klammeraffe oder ohne Punkt in der Domain",
        ursache="Freitexteingabe ohne Formatpruefung",
        kandidaten=_kandidaten_email,
        anwenden=_email_zerlegt,
    ),
)
