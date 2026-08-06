"""Enums und Schluesselkataloge des Datenmodells.

Alle Werte stammen aus ``spec/01_datenmodell.md``, Abschnitt 3. Fachliche
Bezeichner sind deutsch, technische englisch (CLAUDE.md, Abschnitt 5).

Dieses Modul ist bewusst frei von Abhaengigkeiten: Generator, Regel-Engine,
Injektor und Gegencheck importieren es gemeinsam (Architekturregel A1).
"""

from __future__ import annotations

from enum import IntEnum, StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping

__all__ = [
    "ANFRAGESTATUS_REIHENFOLGE",
    "BAUARTKLASSEN",
    "KFZ_SPARTEN",
    "RATENANZAHL_JE_ZAHLWEISE",
    "SF_KLASSEN",
    "SF_KLASSEN_NUMERISCH",
    "SF_KLASSEN_SONDER",
    "SF_MAX_NUMERISCH",
    "WAEHRUNG_STANDARD",
    "WAGNISKENNZIFFER_PKW",
    "ZAHLWEISEN_IM_GENERATOR",
    "Abstellplatz",
    "Anfragestatus",
    "Annahmeentscheidung",
    "Anrede",
    "Antriebsart",
    "ArtKennzeichen",
    "Deckungsart",
    "Eigentumsverhaeltnis",
    "Familienstand",
    "Gebaeudeart",
    "Kanal",
    "Nutzerkreis",
    "Nutzungsart",
    "Quellschnittstelle",
    "Rolle",
    "Sparte",
    "Zahlweise",
    "ist_kfz_sparte",
    "sf_numerischer_teil",
]


class Sparte(StrEnum):
    """Spartenschluessel nach GDV Anlage 1 (Feld 5 der Entitaet ``anfrage``)."""

    KFZ_HAFTPFLICHT = "051"
    KFZ_VOLLKASKO = "052"
    KFZ_TEILKASKO = "053"
    HAUSRAT = "130"


#: Sparten, die eine ``risiko_kfz``-Zeile nach sich ziehen.
KFZ_SPARTEN: Final[tuple[Sparte, ...]] = (
    Sparte.KFZ_HAFTPFLICHT,
    Sparte.KFZ_VOLLKASKO,
    Sparte.KFZ_TEILKASKO,
)


def ist_kfz_sparte(sparte: str) -> bool:
    """Gibt zurueck, ob der Spartenschluessel zu einem Kfz-Risiko gehoert."""
    return sparte in {s.value for s in KFZ_SPARTEN}


class Zahlweise(IntEnum):
    """Zahlweise nach GDV Anlage 14.

    Die Schluessel **3 und 7 existieren nicht**. Eine reine Bereichspruefung
    ``1 <= x <= 9`` wuerde sie durchlassen — nur die Katalogpruefung faengt sie
    (Regel R-010, Injektionsvarianten F3-d und F3-e).
    """

    JAEHRLICH = 1
    HALBJAEHRLICH = 2
    VIERTELJAEHRLICH = 4
    SONSTIGES = 5
    EINMALBETRAG = 6
    MONATLICH = 8
    BEITRAGSFREI = 9


#: Ratenanzahl je Zahlweise (spec/01_datenmodell.md, Abschnitt 3.1).
RATENANZAHL_JE_ZAHLWEISE: Final[Mapping[Zahlweise, int]] = MappingProxyType(
    {
        Zahlweise.JAEHRLICH: 1,
        Zahlweise.HALBJAEHRLICH: 2,
        Zahlweise.VIERTELJAEHRLICH: 4,
        Zahlweise.SONSTIGES: 1,
        Zahlweise.EINMALBETRAG: 1,
        Zahlweise.MONATLICH: 12,
        Zahlweise.BEITRAGSFREI: 1,
    }
)

#: Zahlweisen, die der Generator zieht.
#:
#: ``SONSTIGES`` (5) hat keine definierte Semantik, ``BEITRAGSFREI`` (9) waere mit
#: einem positiven Beitrag fachlich widerspruechlich. Beide bleiben gueltige
#: Katalogwerte — R-010 prueft gegen den vollstaendigen GDV-Katalog —, kommen im
#: Datensatz aber nicht vor (spec/01_datenmodell.md, Abschnitt 3.1).
ZAHLWEISEN_IM_GENERATOR: Final[tuple[Zahlweise, ...]] = (
    Zahlweise.JAEHRLICH,
    Zahlweise.HALBJAEHRLICH,
    Zahlweise.VIERTELJAEHRLICH,
    Zahlweise.EINMALBETRAG,
    Zahlweise.MONATLICH,
)


class Kanal(StrEnum):
    """Eingangskanal der Anfrage. Bestimmt das erwartete Pflichtfeldniveau."""

    WEB = "WEB"
    APP = "APP"
    MAKLER = "MAKLER"
    API_BIPRO = "API_BIPRO"
    TELEFON = "TELEFON"


class Anrede(StrEnum):
    """Anrede. ``FIRMA`` ist eine juristische Person und hat kein Geburtsdatum."""

    HERR = "HERR"
    FRAU = "FRAU"
    DIVERS = "DIVERS"
    FIRMA = "FIRMA"


class Rolle(StrEnum):
    """Rolle einer Person: Versicherungsnehmer oder versicherte Person."""

    VN = "VN"
    VP = "VP"


class Familienstand(StrEnum):
    """Familienstand der Person."""

    LEDIG = "LEDIG"
    VERHEIRATET = "VERHEIRATET"
    GESCHIEDEN = "GESCHIEDEN"
    VERWITWET = "VERWITWET"


class Nutzungsart(StrEnum):
    """Nutzungsart des Fahrzeugs (GDV Satzart 0210.050)."""

    GESCHAEFTLICH = "01"
    PRIVAT = "02"
    TAXI = "03"
    GEMISCHT = "08"


class ArtKennzeichen(StrEnum):
    """Art des Kennzeichens (GDV Satzart 0210.050).

    ``ELEKTRO`` (54) setzt nach EmoG einen elektrischen Antrieb voraus (R-039).
    """

    NORMAL = "01"
    SAISON = "04"
    ELEKTRO = "54"


class Eigentumsverhaeltnis(StrEnum):
    """Eigentumsverhaeltnis am Fahrzeug."""

    EIGENTUM_VN = "1"
    LEASING = "3"


class Nutzerkreis(StrEnum):
    """Kreis der berechtigten Fahrer. Bestimmt ``alter_juengster_fahrer``."""

    VN = "VN"
    VN_PARTNER = "VN_PARTNER"
    VN_FAMILIE = "VN_FAMILIE"
    BELIEBIG = "BELIEBIG"


class Abstellplatz(StrEnum):
    """Naechtlicher Abstellplatz des Fahrzeugs."""

    GARAGE = "GARAGE"
    CARPORT = "CARPORT"
    STELLPLATZ = "STELLPLATZ"
    STRASSE = "STRASSE"


class Gebaeudeart(StrEnum):
    """Gebaeudeart des Hausratrisikos.

    ``ETW`` und ``MIETWOHNUNG`` verlangen ein gesetztes ``stockwerk``.
    """

    EFH = "EFH"
    DHH = "DHH"
    RH = "RH"
    MFH = "MFH"
    ETW = "ETW"
    MIETWOHNUNG = "MIETWOHNUNG"


class Annahmeentscheidung(StrEnum):
    """Annahmeentscheidung des Versicherers. ``ABLEHNUNG`` laesst alle Beitragsfelder leer."""

    ANNAHME = "ANNAHME"
    ANNAHME_MIT_ZUSCHLAG = "ANNAHME_MIT_ZUSCHLAG"
    ABLEHNUNG = "ABLEHNUNG"
    PRUEFUNG = "PRUEFUNG"


class Anfragestatus(StrEnum):
    """Status der Anfrage im Prozess."""

    NEU = "NEU"
    TARIFIERT = "TARIFIERT"
    ANGEBOT = "ANGEBOT"
    ANTRAG = "ANTRAG"
    STORNIERT = "STORNIERT"


#: Prozessreihenfolge der Anfragestatus (spec/01, Abschnitt 3.1: "monoton in
#: Prozessreihenfolge"). ``STORNIERT`` ist ein Abbruchzustand und steht am Ende.
ANFRAGESTATUS_REIHENFOLGE: Final[tuple[Anfragestatus, ...]] = (
    Anfragestatus.NEU,
    Anfragestatus.TARIFIERT,
    Anfragestatus.ANGEBOT,
    Anfragestatus.ANTRAG,
    Anfragestatus.STORNIERT,
)


class Quellschnittstelle(StrEnum):
    """Schnittstelle, ueber die ein Anbieter liefert.

    Bestimmt das erwartete Pflichtfeldniveau (R-057) und die Einheitenkonvention
    (R-052). Die Zuordnung Anbieter zu Schnittstelle ist in ``vu_stammdaten.csv``
    fest hinterlegt.
    """

    BIPRO_420 = "BIPRO_420"
    BIPRO_RNEXT = "BIPRO_RNEXT"
    GDV = "GDV"
    CSV_IMPORT = "CSV_IMPORT"


class Antriebsart(StrEnum):
    """Antriebsart des Fahrzeugs (Referenztabelle ``typklassen.csv``)."""

    BENZIN = "BENZIN"
    DIESEL = "DIESEL"
    ELEKTRO = "ELEKTRO"
    HYBRID = "HYBRID"
    GAS = "GAS"


class Deckungsart(IntEnum):
    """Deckungsart der Kfz-Haftpflicht (nur Sparte 051)."""

    UNBEGRENZT = 11
    GESETZLICHE_MINDESTDECKUNG = 13
    SONSTIGE = 16


#: Wagniskennziffer fuer PKW (GDV).
WAGNISKENNZIFFER_PKW: Final[str] = "112"

#: Waehrung des gesamten Datensatzes (ISO 4217).
#:
#: R-012 prueft gegen den vollstaendigen ISO-4217-Katalog. Dieser Katalog ist
#: bewusst noch nicht hinterlegt — er wird in Phase 3 als Referenzdatei ergaenzt,
#: nicht aus dem Gedaechtnis in den Quellcode geschrieben.
WAEHRUNG_STANDARD: Final[str] = "EUR"

#: Bauartklassen nach GDV Anlage 12.
#:
#: Gemischt numerisch und alphabetisch, deshalb zwingend String (R-017). Der
#: Buchstabe ``J`` existiert nicht — er ist die Injektionsvariante F3-h.
BAUARTKLASSEN: Final[tuple[str, ...]] = (
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "I",
)

#: Hoechste numerische Schadenfreiheitsklasse.
SF_MAX_NUMERISCH: Final[int] = 50

#: Sonderklassen der Schadenfreiheitsklasse. Keine Zahlen, deshalb zwingend String (R-013).
SF_KLASSEN_SONDER: Final[tuple[str, ...]] = ("M", "S", "0", "1/2")

#: Numerische Schadenfreiheitsklassen ``SF1`` bis ``SF50``.
SF_KLASSEN_NUMERISCH: Final[tuple[str, ...]] = tuple(
    f"SF{stufe}" for stufe in range(1, SF_MAX_NUMERISCH + 1)
)

#: Vollstaendiger Katalog gueltiger Schadenfreiheitsklassen (R-013).
SF_KLASSEN: Final[tuple[str, ...]] = SF_KLASSEN_SONDER + SF_KLASSEN_NUMERISCH


def sf_numerischer_teil(sf_klasse: str) -> int | None:
    """Gibt den numerischen Teil einer Schadenfreiheitsklasse zurueck.

    Args:
        sf_klasse: Wert aus :data:`SF_KLASSEN`, zum Beispiel ``"SF12"``.

    Returns:
        Die Stufe als ``int`` fuer ``SF1`` bis ``SF50``, sonst ``None``.

    Die vier Sonderklassen ``M``, ``S``, ``0`` und ``1/2`` liefern bewusst
    ``None``: ``spec/02_regelkatalog.md`` formuliert R-029 und R-030 ueber den
    "numerischen Teil" beziehungsweise "wenn beide numerisch" und legt fuer die
    Sonderklassen keinen Zahlwert fest. Eine Zuordnung ``"0" -> 0`` waere eine
    zusaetzliche Annahme und gehoert erst nach Klaerung in die Spezifikation.
    """
    if not sf_klasse.startswith("SF"):
        return None
    rest = sf_klasse[2:]
    if not rest.isdigit():
        return None
    stufe = int(rest)
    if not 1 <= stufe <= SF_MAX_NUMERISCH:
        return None
    return stufe
