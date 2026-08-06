"""Personen — Versicherungsnehmer und optionale zweite versicherte Person.

Die Postleitzahl kommt aus der Referenztabelle; ``ort`` und ``zulassungsbezirk``
werden **aus ihr abgeleitet**, nicht unabhaengig gezogen (R-050, R-058). Das
Geburtsdatum folgt der Altersstruktur der erwachsenen Bevoelkerung, nicht einer
Gleichverteilung (spec/01, Abschnitt 4).

Zweckbindung: Der Fuehrerscheintag wird nur in den Kfz-Sparten gefuellt. Bei
``anrede`` = FIRMA bleiben Vorname, Geburtsdatum und Familienstand leer — eine
juristische Person hat davon nichts. Der leere Geburtstag ist zugleich der
bedingte Teil von R-001.
"""

from __future__ import annotations

import datetime as dt
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from src.common.enums import Anrede, Familienstand, Rolle, ist_kfz_sparte
from src.common.serialisierung import SPALTEN_JE_ENTITAET, typisierter_rahmen
from src.generator.verteilungen import (
    datum_plus_jahre,
    erzeuge_uuids,
    jahre_zwischen,
    waehle_index,
    ziehe_wahrheit,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence

    import pandas as pd
    from faker import Faker
    from numpy.random import Generator

    from src.common.config import Config

__all__ = ["Personen", "erzeuge_personen"]

#: Altersstruktur der Bevoelkerung ab 18 Jahren: (Untergrenze, Obergrenze, Anteil).
#:
#: Quelle: Zensus 2022 beziehungsweise Destatis-Altersstruktur, auf Fuenfjahres-
#: gruppen zusammengefasst und auf die Bevoelkerung ab 18 Jahren umgerechnet.
_ALTERSGRUPPEN: Final[tuple[tuple[int, int, float], ...]] = (
    (18, 19, 0.026),
    (20, 24, 0.062),
    (25, 29, 0.070),
    (30, 34, 0.076),
    (35, 39, 0.078),
    (40, 44, 0.074),
    (45, 49, 0.069),
    (50, 54, 0.084),
    (55, 59, 0.093),
    (60, 64, 0.087),
    (65, 69, 0.076),
    (70, 74, 0.063),
    (75, 79, 0.058),
    (80, 84, 0.050),
    (85, 89, 0.025),
    (90, 95, 0.009),
)

#: Wahrscheinlichkeit einer zweiten versicherten Person je Anfrage (Modellannahme).
_P_ZWEITE_PERSON: Final[float] = 0.25

#: Wahrscheinlichkeit einer juristischen Person; nur in der Sparte Hausrat.
#:
#: **Modellvereinfachung:** In den Kfz-Sparten tritt ausschliesslich eine
#: natuerliche Person als Versicherungsnehmer auf. Andernfalls waeren
#: Fuehrerscheintag und Schadenfreiheitsklasse ohne Bezugsalter, und R-028 sowie
#: R-029 waeren dort grundsaetzlich nicht auswertbar. In der Arbeit als
#: Vereinfachung zu kennzeichnen.
_P_FIRMA_HAUSRAT: Final[float] = 0.06

#: Anreden natuerlicher Personen mit ihren Gewichten (Modellannahme).
_ANREDEN_NATUERLICH: Final[tuple[tuple[Anrede, float], ...]] = (
    (Anrede.HERR, 0.52),
    (Anrede.FRAU, 0.46),
    (Anrede.DIVERS, 0.02),
)

#: Familienstand je Altersgruppe: Obergrenze des Alters und Gewichte in der
#: Reihenfolge LEDIG, VERHEIRATET, GESCHIEDEN, VERWITWET (Modellannahme, an der
#: Destatis-Struktur orientiert).
_FAMILIENSTAND_NACH_ALTER: Final[tuple[tuple[int, tuple[float, float, float, float]], ...]] = (
    (29, (0.85, 0.13, 0.02, 0.00)),
    (49, (0.35, 0.52, 0.12, 0.01)),
    (69, (0.16, 0.62, 0.17, 0.05)),
    (_ALTERSGRUPPEN[-1][1], (0.08, 0.55, 0.10, 0.27)),
)

_FAMILIENSTAENDE: Final[tuple[Familienstand, ...]] = (
    Familienstand.LEDIG,
    Familienstand.VERHEIRATET,
    Familienstand.GESCHIEDEN,
    Familienstand.VERWITWET,
)

#: Wohneigentumsquote je Altersgruppe: Obergrenze des Alters und Wahrscheinlichkeit.
_WOHNEIGENTUM_NACH_ALTER: Final[tuple[tuple[int, float], ...]] = (
    (29, 0.15),
    (49, 0.42),
    (69, 0.60),
    (_ALTERSGRUPPEN[-1][1], 0.62),
)

#: Wohneigentumsquote juristischer Personen (Modellannahme).
_P_WOHNEIGENTUM_FIRMA: Final[float] = 0.35

#: Alter beim Fuehrerscheinerwerb: (Untergrenze, Obergrenze, Anteil).
#:
#: Strukturvorbild: Altersverteilung der Fahranfaenger; 17 steht fuer das
#: begleitete Fahren. **Modellannahme.**
_FUEHRERSCHEINALTER: Final[tuple[tuple[int, int, float], ...]] = (
    (17, 17, 0.06),
    (18, 18, 0.44),
    (19, 20, 0.24),
    (21, 25, 0.16),
    (26, 40, 0.10),
)

#: Postfaecher der erzeugten Adressen (rein synthetisch).
_EMAIL_DOMAENEN: Final[tuple[str, ...]] = (
    "beispielmail.de",
    "musterpost.de",
    "testkonto.de",
    "synthmail.de",
    "probeadresse.de",
)

#: Lokalteil, wenn aus dem Namen keine verwendbaren Zeichen bleiben.
_EMAIL_ERSATZ: Final[str] = "kontakt"

#: Feldlaengen aus spec/01, Abschnitt 3.2.
_MAX_NACHNAME: Final[int] = 50
_MAX_VORNAME: Final[int] = 30
_MAX_STRASSE: Final[int] = 30
_MAX_EMAIL: Final[int] = 60
_MAX_LOKALTEIL: Final[int] = 30

#: Formen der Hausnummer: schlichte Zahl, Zahl mit Buchstabe, Nummernbereich.
_HAUSNUMMER_GEWICHTE: Final[tuple[float, float, float]] = (0.78, 0.15, 0.07)
_FORM_BUCHSTABE: Final[int] = 1
_FORM_BEREICH: Final[int] = 2

#: Umschrift der deutschen Sonderzeichen fuer die Adressbildung.
_UMSCHRIFT: Final[Mapping[str, str]] = {
    "ä": "ae",
    "ö": "oe",
    "ü": "ue",
    "ß": "ss",
    "æ": "ae",
    "ø": "oe",
    "å": "aa",
}


@dataclass(frozen=True, slots=True)
class Personen:
    """Personendaten samt der vom Versicherungsnehmer abgeleiteten Groessen.

    Attributes:
        rahmen: Die Entitaet ``person``.
        vn_person_id: Kennung des Versicherungsnehmers je Anfrage.
        vn_name: Vollstaendiger Name des Versicherungsnehmers je Anfrage.
        vn_geburtsdatum: Geburtsdatum des Versicherungsnehmers, ``None`` bei FIRMA.
        vn_alter: Alter zum Stichtag, ``None`` bei FIRMA.
        vn_fuehrerschein: Fuehrerscheintag, ``None`` ausserhalb der Kfz-Sparten.
    """

    rahmen: pd.DataFrame
    vn_person_id: tuple[str, ...]
    vn_name: tuple[str, ...]
    vn_geburtsdatum: tuple[dt.date | None, ...]
    vn_alter: tuple[int | None, ...]
    vn_fuehrerschein: tuple[dt.date | None, ...]


@dataclass(frozen=True, slots=True)
class _Rohperson:
    """Zwischenstand einer Person, bevor die Spalten gefuellt werden."""

    anfrage_index: int
    rolle: Rolle
    anrede: Anrede
    nachname: str
    vorname: str | None
    geburtsdatum: dt.date | None
    alter: int | None
    fuehrerschein: dt.date | None

    @property
    def vollname(self) -> str:
        """Name in der Form, in der er als Kontoinhaber erscheint."""
        if self.vorname is None:
            return self.nachname
        return f"{self.vorname} {self.nachname}"


def _umschrift(text: str) -> str:
    """Bildet einen Namen auf reine ASCII-Kleinbuchstaben ab."""
    gewandelt = "".join(_UMSCHRIFT.get(zeichen, zeichen) for zeichen in text.lower())
    zerlegt = unicodedata.normalize("NFKD", gewandelt)
    ohne_akzente = "".join(zeichen for zeichen in zerlegt if not unicodedata.combining(zeichen))
    gefiltert = "".join(
        zeichen if zeichen.isalnum() and zeichen.isascii() else "." for zeichen in ohne_akzente
    )
    return ".".join(teil for teil in gefiltert.split(".") if teil)


def _adresse(vorname: str | None, nachname: str, domaene: str) -> str:
    """Bildet eine E-Mail-Adresse nach dem vereinfachten RFC-5322-Muster (R-006)."""
    teile = [_umschrift(teil) for teil in (vorname, nachname) if teil]
    lokal = ".".join(teil for teil in teile if teil)[:_MAX_LOKALTEIL].strip(".")
    return f"{lokal or _EMAIL_ERSATZ}@{domaene}"[:_MAX_EMAIL]


def _wohneigentum_wahrscheinlichkeit(alter: int | None) -> float:
    """Gibt die Wohneigentumsquote der Altersgruppe zurueck."""
    if alter is None:
        return _P_WOHNEIGENTUM_FIRMA
    for obergrenze, quote in _WOHNEIGENTUM_NACH_ALTER:
        if alter <= obergrenze:
            return quote
    return _WOHNEIGENTUM_NACH_ALTER[-1][1]


def _familienstand_gewichte(alter: int) -> tuple[float, float, float, float]:
    """Gibt die Gewichte des Familienstands fuer die Altersgruppe zurueck."""
    for obergrenze, gewichte in _FAMILIENSTAND_NACH_ALTER:
        if alter <= obergrenze:
            return gewichte
    return _FAMILIENSTAND_NACH_ALTER[-1][1]


def _geburtsdatum(rng: Generator, stichtag: dt.date, unten: int, oben: int) -> dt.date:
    """Zieht ein Geburtsdatum, das zum Stichtag auf ein Alter in ``[unten, oben]`` fuehrt."""
    fruehestens = datum_plus_jahre(stichtag, -(oben + 1)) + dt.timedelta(days=1)
    spaetestens = datum_plus_jahre(stichtag, -unten)
    spanne = (spaetestens - fruehestens).days
    return fruehestens + dt.timedelta(days=int(rng.integers(0, spanne + 1)))


def _fuehrerschein(rng: Generator, geburtsdatum: dt.date, stichtag: dt.date) -> dt.date:
    """Zieht einen Fuehrerscheintag, der R-028 erfuellt (Erwerb fruehestens mit 17)."""
    gewichte = [anteil for _, _, anteil in _FUEHRERSCHEINALTER]
    unten, oben, _ = _FUEHRERSCHEINALTER[int(waehle_index(rng, 1, gewichte)[0])]
    alter = jahre_zwischen(geburtsdatum, stichtag)
    erwerbsalter = min(int(rng.integers(unten, oben + 1)), alter)

    untergrenze = datum_plus_jahre(geburtsdatum, erwerbsalter)
    obergrenze = min(
        datum_plus_jahre(geburtsdatum, erwerbsalter + 1) - dt.timedelta(days=1), stichtag
    )
    spanne = max((obergrenze - untergrenze).days, 0)
    return untergrenze + dt.timedelta(days=int(rng.integers(0, spanne + 1)))


def _baue_person(  # noqa: PLR0913 - Anrede, Rolle und Sparte steuern die Ziehung getrennt
    rng: Generator,
    faker: Faker,
    stichtag: dt.date,
    *,
    anfrage_index: int,
    rolle: Rolle,
    ist_kfz: bool,
    firma: bool,
) -> _Rohperson:
    """Zieht Anrede, Name, Geburtsdatum und Fuehrerscheintag einer einzelnen Person."""
    if firma:
        return _Rohperson(
            anfrage_index=anfrage_index,
            rolle=rolle,
            anrede=Anrede.FIRMA,
            nachname=faker.company()[:_MAX_NACHNAME],
            vorname=None,
            geburtsdatum=None,
            alter=None,
            fuehrerschein=None,
        )

    anrede = _ANREDEN_NATUERLICH[
        int(waehle_index(rng, 1, [gewicht for _, gewicht in _ANREDEN_NATUERLICH])[0])
    ][0]
    if anrede is Anrede.HERR:
        vorname = faker.first_name_male()
    elif anrede is Anrede.FRAU:
        vorname = faker.first_name_female()
    else:
        vorname = faker.first_name()

    gruppe = _ALTERSGRUPPEN[
        int(waehle_index(rng, 1, [anteil for _, _, anteil in _ALTERSGRUPPEN])[0])
    ]
    geburtsdatum = _geburtsdatum(rng, stichtag, gruppe[0], gruppe[1])
    return _Rohperson(
        anfrage_index=anfrage_index,
        rolle=rolle,
        anrede=anrede,
        nachname=faker.last_name()[:_MAX_NACHNAME],
        vorname=vorname[:_MAX_VORNAME],
        geburtsdatum=geburtsdatum,
        alter=jahre_zwischen(geburtsdatum, stichtag),
        fuehrerschein=_fuehrerschein(rng, geburtsdatum, stichtag) if ist_kfz else None,
    )


def _hausnummern(rng: Generator, anzahl: int) -> list[str]:
    """Zieht Hausnummern, teils mit Buchstabenzusatz oder als Nummernbereich."""
    zahlen = rng.integers(1, 180, size=anzahl)
    formen = waehle_index(rng, anzahl, list(_HAUSNUMMER_GEWICHTE))
    zusaetze = rng.integers(0, 4, size=anzahl)
    ergebnis: list[str] = []
    for index in range(anzahl):
        zahl = int(zahlen[index])
        if formen[index] == _FORM_BUCHSTABE:
            ergebnis.append(f"{zahl}{'abcd'[int(zusaetze[index])]}")
        elif formen[index] == _FORM_BEREICH:
            ergebnis.append(f"{zahl}-{zahl + 2}")
        else:
            ergebnis.append(str(zahl))
    return ergebnis


def _ziehe_familienstand(rng: Generator, personen: Sequence[_Rohperson]) -> list[str | None]:
    """Zieht den Familienstand altersabhaengig; juristische Personen bleiben leer."""
    ergebnis: list[str | None] = []
    for person in personen:
        if person.alter is None:
            ergebnis.append(None)
            continue
        gewichte = _familienstand_gewichte(person.alter)
        ergebnis.append(_FAMILIENSTAENDE[int(waehle_index(rng, 1, list(gewichte))[0])].value)
    return ergebnis


def erzeuge_personen(  # noqa: PLR0913 - die Anschrift kommt aus drei Referenzspalten
    config: Config,
    rng: Generator,
    faker: Faker,
    *,
    anfrage_ids: Sequence[str],
    sparten: Sequence[str],
    plz_werte: Sequence[str],
    ortsnamen: Sequence[str],
) -> Personen:
    """Erzeugt je Anfrage einen Versicherungsnehmer und optional eine zweite Person.

    Args:
        config: Geladene Konfiguration; liefert den Stichtag.
        rng: Zufallsgenerator des Teilstroms "Person".
        faker: Geseedete Faker-Instanz fuer Namen und Strassennamen.
        anfrage_ids: Kennung je Anfrage.
        sparten: Spartenschluessel je Anfrage.
        plz_werte: Postleitzahl je Anfrage.
        ortsnamen: Ortsname je Anfrage, aus der Referenz zur Postleitzahl.

    Returns:
        Die :class:`Personen` mit Datenrahmen und den Groessen des
        Versicherungsnehmers je Anfrage.
    """
    stichtag = config.stichtag
    anzahl_anfragen = len(anfrage_ids)

    ist_firma = ziehe_wahrheit(
        rng,
        [0.0 if ist_kfz_sparte(sparte) else _P_FIRMA_HAUSRAT for sparte in sparten],
    )
    hat_zweite = ziehe_wahrheit(rng, [_P_ZWEITE_PERSON] * anzahl_anfragen)

    # Die Versicherungsnehmer stehen zuerst; ihre Position ist damit gleich dem
    # Index der Anfrage. Erst danach folgen die zweiten versicherten Personen.
    versicherungsnehmer = [
        _baue_person(
            rng,
            faker,
            stichtag,
            anfrage_index=index,
            rolle=Rolle.VN,
            ist_kfz=ist_kfz_sparte(sparten[index]),
            firma=bool(ist_firma[index]),
        )
        for index in range(anzahl_anfragen)
    ]
    weitere = [
        _baue_person(
            rng,
            faker,
            stichtag,
            anfrage_index=index,
            rolle=Rolle.VP,
            ist_kfz=ist_kfz_sparte(sparten[index]),
            firma=False,
        )
        for index in range(anzahl_anfragen)
        if hat_zweite[index]
    ]
    # Nach Anfrage gruppiert, Versicherungsnehmer vor zweiter Person. Die
    # Sortierung ist stabil und haengt nur an bereits gezogenen Werten.
    alle = sorted(
        [*versicherungsnehmer, *weitere], key=lambda person: (person.anfrage_index, person.rolle)
    )

    # Anschrift und Strasse haengen an der Anfrage, nicht an der Person: Beide
    # Personen einer Anfrage wohnen im Modell unter derselben Adresse.
    strassen = [faker.street_name()[:_MAX_STRASSE] for _ in range(anzahl_anfragen)]
    hausnummern = _hausnummern(rng, anzahl_anfragen)
    domaenen = waehle_index(rng, len(alle), [1.0] * len(_EMAIL_DOMAENEN))
    familienstaende = _ziehe_familienstand(rng, alle)
    wohneigentum = ziehe_wahrheit(
        rng, [_wohneigentum_wahrscheinlichkeit(person.alter) for person in alle]
    )
    person_ids = erzeuge_uuids(rng, len(alle))

    vn_kennung: dict[int, str] = {}
    spalten: dict[str, list[object]] = {name: [] for name in SPALTEN_JE_ENTITAET["person"]}
    for laufende, person in enumerate(alle):
        anfrage = person.anfrage_index
        if person.rolle is Rolle.VN:
            vn_kennung[anfrage] = person_ids[laufende]
        spalten["row_id"].append(laufende + 1)
        spalten["person_id"].append(person_ids[laufende])
        spalten["anfrage_id"].append(anfrage_ids[anfrage])
        spalten["rolle"].append(person.rolle.value)
        spalten["anrede"].append(person.anrede.value)
        spalten["nachname"].append(person.nachname)
        spalten["vorname"].append(person.vorname)
        spalten["geburtsdatum"].append(person.geburtsdatum)
        spalten["plz"].append(plz_werte[anfrage])
        spalten["ort"].append(ortsnamen[anfrage])
        spalten["strasse"].append(strassen[anfrage])
        spalten["hausnummer"].append(hausnummern[anfrage])
        spalten["email"].append(
            _adresse(person.vorname, person.nachname, _EMAIL_DOMAENEN[int(domaenen[laufende])])
        )
        spalten["familienstand"].append(familienstaende[laufende])
        spalten["wohneigentum"].append(bool(wohneigentum[laufende]))
        spalten["fuehrerschein_datum"].append(person.fuehrerschein)

    return Personen(
        rahmen=typisierter_rahmen(spalten, "person"),
        vn_person_id=tuple(vn_kennung[index] for index in range(anzahl_anfragen)),
        vn_name=tuple(person.vollname for person in versicherungsnehmer),
        vn_geburtsdatum=tuple(person.geburtsdatum for person in versicherungsnehmer),
        vn_alter=tuple(person.alter for person in versicherungsnehmer),
        vn_fuehrerschein=tuple(person.fuehrerschein for person in versicherungsnehmer),
    )
