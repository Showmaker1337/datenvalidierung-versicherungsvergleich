"""G1 — Regeln auf Attributwertebene (R-001 bis R-025).

Eine G1-Regel betrachtet **eine Zelle fuer sich**: Ist der Wert vorhanden, hat er
das richtige Format, liegt er im Katalog oder im Wertebereich? Beziehungen zwischen
Feldern gehoeren nach G2, Beziehungen zwischen Zeilen nach G3.

Elf dieser Regeln laufen auf der **Rohschicht** (``spec/02``, Abschnitt "Auf welcher
Datenschicht eine Regel arbeitet"): R-002 bis R-009, R-013, R-017 und R-025. Auf der
typisierten Schicht waeren sie per Konstruktion nicht verletzbar — in einer
``datetime.date`` kann kein 31. Februar stehen, und eine als String gefuehrte
Postleitzahl kann keine fuehrende Null verlieren.

pandera
-------

Die reinen Spaltenpruefungen laufen ueber pandera mit ``lazy=True``, damit **alle**
Verstoesse einer Spalte gesammelt werden statt beim ersten abzubrechen
(:func:`_pruefe_spalten`). Regeln mit Bedingungen ueber mehrere Felder oder
Entitaeten — R-001, R-012, R-021, R-024, R-025 — sind eigene Pruefungen; dafuer ist
pandera nicht gedacht.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Final

import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaErrors

from src.common import wertebereiche as wb
from src.common.enums import (
    BAUARTKLASSEN,
    SF_KLASSEN,
    WAEHRUNG_STANDARD,
    Anfragestatus,
    ArtKennzeichen,
    Nutzungsart,
    Sparte,
    Zahlweise,
)
from src.common.iban import hat_deutsches_format, ist_gueltig
from src.common.pfade import Schicht
from src.common.pflichtfelder import KERNPFLICHTFELDER
from src.common.serialisierung import FELDTYP_JE_SPALTE, SPALTEN_JE_ENTITAET, Feldtyp
from src.rules.modell import (
    Befund,
    Befundsammler,
    Regel,
    leerer_befund,
    row_ids,
    text,
    werte,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Callable, Mapping, Sequence

    from src.rules.modell import Kontext

__all__ = ["REGELN"]

# ---------------------------------------------------------------------------
# Muster
# ---------------------------------------------------------------------------

#: Postleitzahl: genau fuenf Ziffern, fuehrende Null eingeschlossen (R-002).
_MUSTER_PLZ: Final[re.Pattern[str]] = re.compile(r"^\d{5}$")

#: Herstellerschluesselnummer: genau vier Ziffern (R-007).
_MUSTER_HSN: Final[re.Pattern[str]] = re.compile(r"^\d{4}$")

#: Typschluesselnummer: drei Grossbuchstaben oder Ziffern (R-008).
_MUSTER_TSN: Final[re.Pattern[str]] = re.compile(r"^[A-Z0-9]{3}$")

#: Vereinfachtes RFC-5322-Muster (R-006).
#:
#: Bewusst vereinfacht: Das vollstaendige Muster aus RFC 5322 laesst zitierte
#: lokale Teile und Kommentare zu und ist als regulaerer Ausdruck weder lesbar
#: noch pruefbar. Geprueft wird die in der Praxis uebliche Form
#: ``lokalteil@domaene.tld`` — genau die Ebene, auf der die Fehlerklasse
#: "Misspellings" nach Rahm und Do sichtbar wird.
_MUSTER_EMAIL: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r"@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*\.[A-Za-z]{2,}$"
)

#: Laenge des GDV-Datumsformats ``TTMMJJJJ`` (R-009).
_DATUM_LAENGE: Final[int] = 8


# ---------------------------------------------------------------------------
# Gemeinsame Pruefmechanik
# ---------------------------------------------------------------------------


def _leer(rohwert: str) -> bool:
    """Gibt zurueck, ob ein Rohwert leer ist.

    Auf der Rohschicht ist der leere String die Darstellung eines leeren Wertes
    (``spec/01``, Abschnitt 6). Format- und Katalogregeln pruefen leere Zellen
    **nicht** — dafuer sind die Pflichtfeldregeln R-001 und R-057 zustaendig.
    """
    return rohwert == ""


def _pruefe_spalten(  # noqa: PLR0913 - Regel, Entitaet und Schicht gehen getrennt ein
    kontext: Kontext,
    *,
    regel_id: str,
    entitaet: str,
    schicht: Schicht,
    pruefungen: Mapping[str, Callable[[Any], bool]],
    meldung: Callable[[str, Any], str],
) -> Befund:
    """Prueft mehrere Spalten einer Entitaet elementweise mit pandera.

    ``lazy=True`` ist wesentlich: Ohne dieses Kennzeichen bricht pandera beim
    ersten Verstoss ab, und die Auswertung saehe je Spalte hoechstens einen
    Treffer.

    Args:
        kontext: Pruefkontext.
        regel_id: Kennung der Regel.
        entitaet: Zu pruefende Entitaet.
        schicht: Datenschicht der Regel.
        pruefungen: Je Spalte ein Praedikat, das ``True`` fuer zulaessige Werte
            zurueckgibt. Leere Zellen erreichen das Praedikat nicht.
        meldung: Bildet Spaltenname und Wert auf den Meldungstext ab.

    Returns:
        Den :class:`~src.rules.modell.Befund`.
    """
    rahmen = kontext.rahmen(schicht, entitaet)
    if rahmen.empty:
        return leerer_befund()

    schema = pa.DataFrameSchema(
        {
            spalte: pa.Column(
                nullable=True,
                required=False,
                checks=[pa.Check(praedikat, element_wise=True, name=regel_id)],
            )
            for spalte, praedikat in pruefungen.items()
        },
        strict=False,
    )

    sammler = Befundsammler(regel_id)
    try:
        schema.validate(rahmen, lazy=True)
    except SchemaErrors as fehler:
        kennungen = row_ids(rahmen)
        # pandera meldet die Indexmarke, nicht die Zeilenposition. Beide fallen bei
        # einem RangeIndex zusammen — verlassen wird sich darauf nicht.
        position_je_marke = {marke: nummer for nummer, marke in enumerate(rahmen.index)}
        treffer = fehler.failure_cases
        treffer = treffer[treffer["index"].notna()]
        # Feste Reihenfolge: erst nach Zeile, dann nach Spalte. pandera sortiert
        # nach Spalte; ohne diese Sortierung haengt die Reihenfolge der
        # verstoss_id an der Reihenfolge des Schemas (Architekturregel A2).
        for _, zeile in treffer.sort_values(["index", "column"], kind="stable").iterrows():
            position = position_je_marke[zeile["index"]]
            spalte = str(zeile["column"])
            wert = rahmen[spalte].iloc[position]
            sammler.melde(entitaet, kennungen[position], (spalte,), meldung(spalte, wert))
    return sammler.befund()


def _ist_zeichenkettenspalte(spalte: pd.Series) -> bool:
    """Gibt zurueck, ob eine Spalte als Zeichenkette gefuehrt wird.

    Grundlage des Typteils von R-002, R-013 und R-017: Postleitzahl,
    Schadenfreiheitsklasse und Bauartklasse sind **niemals** Ganzzahlen. Wird ein
    solches Feld als Integer gefuehrt, geht die fuehrende Null verloren
    (``01067`` wird zu ``1067``) und die Sonderklassen ``1/2``, ``S`` und ``M``
    sind gar nicht darstellbar.
    """
    if pd.api.types.is_string_dtype(spalte):
        return True
    if spalte.dtype != object:
        return False
    return all(wert is None or pd.isna(wert) or isinstance(wert, str) for wert in spalte)


def _typpruefung(
    kontext: Kontext,
    *,
    entitaet: str,
    spalten: Sequence[str],
    sammler: Befundsammler,
) -> None:
    """Meldet Spalten, die entgegen dem Datenmodell nicht als Zeichenkette gefuehrt sind.

    Die Pruefung schlaegt auf der Rohschicht des sauberen Datensatzes nie an —
    dort ist per Definition alles Zeichenkette. Sie greift, sobald eine
    Verarbeitungsstufe die Spalte umtypisiert hat, und ist genau der Fall, den
    Foidl et al. als "Integer as String" fuehren.
    """
    rahmen = kontext.rahmen(Schicht.RAW, entitaet)
    kennungen = row_ids(rahmen)
    for spalte in spalten:
        if _ist_zeichenkettenspalte(rahmen[spalte]):
            continue
        for position, wert in enumerate(text(rahmen, spalte)):
            if _leer(wert):
                continue
            sammler.melde(
                entitaet,
                kennungen[position],
                (spalte,),
                f"{spalte} ist nicht als Zeichenkette gefuehrt "
                f"(Spaltentyp {rahmen[spalte].dtype}), Wert {wert!r}",
            )


# ---------------------------------------------------------------------------
# R-001 — Kernpflichtfelder
# ---------------------------------------------------------------------------


def pruefe_r001(kontext: Kontext) -> Befund:
    """Kernpflichtfelder sind nicht leer; ohne sie ist keine Tarifierung moeglich.

    Der bedingte Teil — ``anrede`` ungleich FIRMA erzwingt ein ``geburtsdatum`` —
    ist eine Conditional Functional Dependency im Sinne von Fan et al. und das
    zweite CFD-Beispiel der Arbeit neben R-033: Eine juristische Person hat kein
    Geburtsdatum.

    **Leer heisst hier ``None``, nicht Leerstring.** Ein Feld mit dem Wert ``""``
    ist formal gefuellt; das ist die Injektionsvariante F1-b, die diese Regel
    bewusst nicht faengt (``spec/03``, Abschnitt 2).
    """
    sammler = Befundsammler("R-001")
    for feld in KERNPFLICHTFELDER:
        entitaet, _, spalte = feld.partition(".")
        rahmen = kontext.rahmen(Schicht.TYPED, entitaet)
        kennungen = row_ids(rahmen)
        for position, wert in enumerate(werte(rahmen, spalte)):
            if wert is None:
                sammler.melde(
                    entitaet,
                    kennungen[position],
                    (spalte,),
                    f"Kernpflichtfeld {entitaet}.{spalte} ist leer",
                )

    person = kontext.rahmen(Schicht.TYPED, "person")
    kennungen = row_ids(person)
    anreden = werte(person, "anrede")
    geburtstage = werte(person, "geburtsdatum")
    for position, anrede in enumerate(anreden):
        if anrede is None or str(anrede) == "FIRMA" or geburtstage[position] is not None:
            continue
        sammler.melde(
            "person",
            kennungen[position],
            ("geburtsdatum", "anrede"),
            f"geburtsdatum ist leer, obwohl anrede={anrede!r} eine natuerliche Person ist",
        )
    return sammler.befund()


# ---------------------------------------------------------------------------
# R-002 bis R-009 — Format und Syntax auf der Rohschicht
# ---------------------------------------------------------------------------


def pruefe_r002(kontext: Kontext) -> Befund:
    r"""``plz`` erfuellt ``^\d{5}$`` und ist als Zeichenkette gefuehrt.

    Beide Teile sind noetig. Der Musterteil faengt den sichtbaren Schaden — eine
    als Integer gefuehrte Postleitzahl ``01067`` kommt als ``1067`` zurueck und
    hat dann vier Stellen. Der Typteil faengt die Ursache, auch wenn die
    fuehrende Null zufaellig fehlte.
    """
    sammler = Befundsammler("R-002")
    _typpruefung(kontext, entitaet="person", spalten=("plz",), sammler=sammler)
    rahmen = kontext.rahmen(Schicht.RAW, "person")
    kennungen = row_ids(rahmen)
    for position, wert in enumerate(text(rahmen, "plz")):
        if _leer(wert) or _MUSTER_PLZ.match(wert):
            continue
        sammler.melde(
            "person",
            kennungen[position],
            ("plz",),
            f"plz={wert!r} erfuellt nicht das Muster ^\\d{{5}}$",
        )
    return sammler.befund()


def pruefe_r003(kontext: Kontext) -> Befund:
    r"""``iban`` erfuellt ``^DE\d{20}$`` — die deutsche IBAN hat 22 Zeichen (ISO 13616)."""
    return _pruefe_spalten(
        kontext,
        regel_id="R-003",
        entitaet="zahlung",
        schicht=Schicht.RAW,
        pruefungen={"iban": lambda wert: _leer(str(wert)) or hat_deutsches_format(str(wert))},
        meldung=lambda _, wert: f"iban={wert!r} erfuellt nicht das Muster ^DE\\d{{20}}$",
    )


def pruefe_r004(kontext: Kontext) -> Befund:
    """``iban`` besteht die Pruefziffernpruefung Mod 97-10 (ISO 7064).

    Getrennt von R-003: Eine IBAN kann formal richtig aufgebaut sein und trotzdem
    eine falsche Pruefziffer tragen — das ist der klassische Zahlendreher.
    """
    return _pruefe_spalten(
        kontext,
        regel_id="R-004",
        entitaet="zahlung",
        schicht=Schicht.RAW,
        pruefungen={"iban": lambda wert: _leer(str(wert)) or ist_gueltig(str(wert))},
        meldung=lambda _, wert: f"iban={wert!r} besteht die Pruefziffernpruefung Mod 97-10 nicht",
    )


def pruefe_r005(kontext: Kontext) -> Befund:
    """``bic`` hat exakt acht oder elf Zeichen — neun oder zehn gibt es nach ISO 9362 nicht."""
    return _pruefe_spalten(
        kontext,
        regel_id="R-005",
        entitaet="zahlung",
        schicht=Schicht.RAW,
        pruefungen={"bic": lambda wert: _leer(str(wert)) or len(str(wert)) in wb.BIC_LAENGEN},
        meldung=lambda _, wert: (
            f"bic={wert!r} hat {len(str(wert))} Zeichen; zulaessig sind {list(wb.BIC_LAENGEN)}"
        ),
    )


def pruefe_r006(kontext: Kontext) -> Befund:
    """``email`` erfuellt das vereinfachte RFC-5322-Muster."""
    return _pruefe_spalten(
        kontext,
        regel_id="R-006",
        entitaet="person",
        schicht=Schicht.RAW,
        pruefungen={"email": lambda wert: _leer(str(wert)) or bool(_MUSTER_EMAIL.match(str(wert)))},
        meldung=lambda _, wert: f"email={wert!r} erfuellt das RFC-5322-Muster nicht",
    )


def pruefe_r007(kontext: Kontext) -> Befund:
    r"""``hsn`` erfuellt ``^\d{4}$`` (KBA, Zulassungsbescheinigung Teil I, Feld 2.1)."""
    return _pruefe_spalten(
        kontext,
        regel_id="R-007",
        entitaet="risiko_kfz",
        schicht=Schicht.RAW,
        pruefungen={"hsn": lambda wert: _leer(str(wert)) or bool(_MUSTER_HSN.match(str(wert)))},
        meldung=lambda _, wert: f"hsn={wert!r} erfuellt nicht das Muster ^\\d{{4}}$",
    )


def pruefe_r008(kontext: Kontext) -> Befund:
    """``tsn`` erfuellt ``^[A-Z0-9]{3}$`` (Zulassungsbescheinigung Teil I, Feld 2.2)."""
    return _pruefe_spalten(
        kontext,
        regel_id="R-008",
        entitaet="risiko_kfz",
        schicht=Schicht.RAW,
        pruefungen={"tsn": lambda wert: _leer(str(wert)) or bool(_MUSTER_TSN.match(str(wert)))},
        meldung=lambda _, wert: f"tsn={wert!r} erfuellt nicht das Muster ^[A-Z0-9]{{3}}$",
    )


#: Datumsspalten des Schemas — Grundlage von R-009.
#:
#: Nur Felder vom Typ :attr:`~src.common.serialisierung.Feldtyp.DATUM`. Die beiden
#: Zeitpunktfelder (``eingangszeitpunkt``, ``berechnungszeitpunkt``) stehen in ISO
#: 8601 und sind keine Datumsfelder im Sinne der Regel; ihre Wohlgeformtheit
#: pruefen die fachlichen Regeln R-055 und R-057 mittelbar ueber den Parser.
_DATUMSSPALTEN: Final[tuple[str, ...]] = tuple(
    sorted(name for name, typ in FELDTYP_JE_SPALTE.items() if typ is Feldtyp.DATUM)
)


def _datumsbefund(rohwert: str) -> str | None:
    """Prueft Format und Kalendergueltigkeit eines Rohdatums getrennt.

    Args:
        rohwert: Wert aus der Rohschicht im Format ``TTMMJJJJ``.

    Returns:
        Den Grund des Verstosses, oder ``None``, wenn der Wert ein existierender
        Kalendertag ist.
    """
    if len(rohwert) != _DATUM_LAENGE or not rohwert.isdigit():
        return "kein Datum im Format TTMMJJJJ"
    try:
        dt.date(int(rohwert[4:8]), int(rohwert[2:4]), int(rohwert[0:2]))
    except ValueError:
        return "kein existierender Kalendertag"
    return None


def pruefe_r009(kontext: Kontext) -> Befund:
    """Jedes Datumsfeld der Rohschicht ist ein existierender Kalendertag.

    **Zwei getrennte Pruefungen.** ``31022026`` ist achtstellig und rein
    numerisch, also formatgueltig — aber der 31. Februar existiert nicht. Erst die
    zweite Pruefung faengt ihn.

    Die Regel arbeitet zwingend auf der Rohschicht: In einer ``datetime.date``
    ist ein solcher Wert nicht schreibbar (``spec/01``, Abschnitt 6).
    """
    sammler = Befundsammler("R-009")
    for entitaet in SPALTEN_JE_ENTITAET:
        rahmen = kontext.rahmen(Schicht.RAW, entitaet)
        if rahmen.empty:
            continue
        kennungen = row_ids(rahmen)
        for spalte in SPALTEN_JE_ENTITAET[entitaet]:
            if spalte not in _DATUMSSPALTEN:
                continue
            for position, wert in enumerate(text(rahmen, spalte)):
                if _leer(wert):
                    continue
                grund = _datumsbefund(wert)
                if grund is not None:
                    sammler.melde(
                        entitaet,
                        kennungen[position],
                        (spalte,),
                        f"{spalte}={wert!r} ist {grund}",
                    )
    return sammler.befund()


# ---------------------------------------------------------------------------
# R-010 bis R-020 — Kataloge
# ---------------------------------------------------------------------------

#: Gueltige Zahlweisen nach GDV Anlage 14 (R-010).
_ZAHLWEISEN: Final[frozenset[int]] = frozenset(int(wert) for wert in Zahlweise)

#: Gueltige Spartenschluessel nach GDV Anlage 1 (R-011).
_SPARTEN: Final[frozenset[str]] = frozenset(wert.value for wert in Sparte)


def pruefe_r010(kontext: Kontext) -> Befund:
    """``zahlweise`` steht im GDV-Katalog {1, 2, 4, 5, 6, 8, 9}.

    **Katalogpruefung, nicht Bereichspruefung.** Die Schluessel 3 und 7 existieren
    nicht; eine Pruefung ``1 <= x <= 9`` liesse sie durch. Genau daran zeigt sich
    der Unterschied zwischen einem Wertebereich und einem Katalog.
    """
    return _pruefe_spalten(
        kontext,
        regel_id="R-010",
        entitaet="anfrage",
        schicht=Schicht.TYPED,
        pruefungen={"zahlweise": lambda wert: int(wert) in _ZAHLWEISEN},
        meldung=lambda _, wert: (
            f"zahlweise={wert} steht nicht im GDV-Katalog {sorted(_ZAHLWEISEN)}"
        ),
    )


def pruefe_r011(kontext: Kontext) -> Befund:
    """``sparte`` steht im GDV-Spartenverzeichnis {051, 052, 053, 130}."""
    sammler = Befundsammler("R-011")
    for entitaet in ("anfrage", "tarif"):
        rahmen = kontext.rahmen(Schicht.TYPED, entitaet)
        kennungen = row_ids(rahmen)
        for position, wert in enumerate(werte(rahmen, "sparte")):
            if wert is None or str(wert) in _SPARTEN:
                continue
            sammler.melde(
                entitaet,
                kennungen[position],
                ("sparte",),
                f"sparte={wert!r} steht nicht im Spartenverzeichnis {sorted(_SPARTEN)}",
            )
    return sammler.befund()


def pruefe_r012(kontext: Kontext) -> Befund:
    """``waehrung`` ist ein ISO-4217-Code **und** im Kontext dieses Systems ``EUR``.

    Zwei Stufen, getrennt gemeldet. Die erste prueft die syntaktische Gueltigkeit
    gegen den vollstaendigen Katalog in ``waehrungen.csv``, die zweite die
    fachliche Zulaessigkeit im Modell. ``CHF`` besteht die erste Stufe und faellt
    durch die zweite — ein kleines Beispiel dafuer, dass "gueltig" und "zulaessig"
    nicht dasselbe sind.
    """
    sammler = Befundsammler("R-012")
    katalog = frozenset(str(wert) for wert in kontext.referenztabelle("waehrungen")["code"])
    rahmen = kontext.rahmen(Schicht.TYPED, "anfrage")
    kennungen = row_ids(rahmen)
    for position, wert in enumerate(werte(rahmen, "waehrung")):
        if wert is None:
            continue
        code = str(wert)
        if code not in katalog:
            sammler.melde(
                "anfrage",
                kennungen[position],
                ("waehrung",),
                f"waehrung={code!r} steht nicht im ISO-4217-Katalog",
            )
        elif code != WAEHRUNG_STANDARD:
            sammler.melde(
                "anfrage",
                kennungen[position],
                ("waehrung",),
                f"waehrung={code!r} ist ein gueltiger ISO-4217-Code, im Modell ist aber nur "
                f"{WAEHRUNG_STANDARD} zulaessig",
            )
    return sammler.befund()


def pruefe_r013(kontext: Kontext) -> Befund:
    """``sf_klasse_*`` steht im Katalog und ist als Zeichenkette gefuehrt.

    Die Sonderklassen ``0``, ``1/2``, ``S`` und ``M`` sind **keine Zahlen**. Eine
    Integer-Typisierung ist hier kein Darstellungsdetail, sondern ein
    Modellierungsfehler: ``1/2`` und ``S`` waeren gar nicht schreibbar.
    """
    spalten = ("sf_klasse_hp", "sf_klasse_vk")
    sammler = Befundsammler("R-013")
    _typpruefung(kontext, entitaet="risiko_kfz", spalten=spalten, sammler=sammler)
    rahmen = kontext.rahmen(Schicht.RAW, "risiko_kfz")
    kennungen = row_ids(rahmen)
    katalog = frozenset(SF_KLASSEN)
    for spalte in spalten:
        for position, wert in enumerate(text(rahmen, spalte)):
            if _leer(wert) or wert in katalog:
                continue
            sammler.melde(
                "risiko_kfz",
                kennungen[position],
                (spalte,),
                f"{spalte}={wert!r} steht nicht im Katalog der Schadenfreiheitsklassen",
            )
    return sammler.befund()


def _im_bereich(wert: Any, grenzen: tuple[int, int]) -> bool:  # noqa: ANN401
    """Gibt zurueck, ob ein ganzzahliger Wert im geschlossenen Intervall liegt."""
    return grenzen[0] <= int(wert) <= grenzen[1]


def _bereichspruefung(grenzen: tuple[int, int]) -> Callable[[Any], bool]:
    """Baut ein Praedikat, das einen ganzzahligen Wert gegen ein Intervall prueft.

    Bewusst eine Fabrikfunktion und kein Lambda mit Vorgabewert: Die drei
    Typklassen haben verschiedene Grenzen, und ein Lambda in der Schleife wuerde
    die Grenze der letzten Runde binden.
    """

    def erfuellt(wert: Any) -> bool:  # noqa: ANN401
        return _im_bereich(wert, grenzen)

    return erfuellt


def _mindestwertpruefung(grenze: Decimal) -> Callable[[Any], bool]:
    """Baut ein Praedikat, das einen Betrag gegen eine Untergrenze prueft."""

    def erfuellt(wert: Any) -> bool:  # noqa: ANN401
        return Decimal(str(wert)) >= grenze

    return erfuellt


def pruefe_r014(kontext: Kontext) -> Befund:
    """Die Typklassen liegen in den Grenzen des GDV-Typklassenverzeichnisses.

    16 Klassen in der Haftpflicht (10 bis 25), 24 in der Teilkasko (10 bis 33),
    25 in der Vollkasko (10 bis 34). Die drei Bereiche sind verschieden — eine
    gemeinsame Grenze waere fachlich falsch.
    """
    grenzen = {
        "typklasse_hp": wb.TYPKLASSE_HP,
        "typklasse_tk": wb.TYPKLASSE_TK,
        "typklasse_vk": wb.TYPKLASSE_VK,
    }
    return _pruefe_spalten(
        kontext,
        regel_id="R-014",
        entitaet="risiko_kfz",
        schicht=Schicht.TYPED,
        pruefungen={
            spalte: _bereichspruefung(bereich) for spalte, bereich in grenzen.items()
        },
        meldung=lambda spalte, wert: (
            f"{spalte}={wert} liegt ausserhalb von {list(grenzen[spalte])}"
        ),
    )


def pruefe_r015(kontext: Kontext) -> Befund:
    """Die Regionalklassen liegen in den Grenzen des GDV-Regionalklassenverzeichnisses.

    12 Stufen in der Haftpflicht, 16 in der Teilkasko, 9 in der Vollkasko.
    """
    grenzen = {
        "regionalklasse_hp": wb.REGIONALKLASSE_HP,
        "regionalklasse_tk": wb.REGIONALKLASSE_TK,
        "regionalklasse_vk": wb.REGIONALKLASSE_VK,
    }
    return _pruefe_spalten(
        kontext,
        regel_id="R-015",
        entitaet="risiko_kfz",
        schicht=Schicht.TYPED,
        pruefungen={
            spalte: _bereichspruefung(bereich) for spalte, bereich in grenzen.items()
        },
        meldung=lambda spalte, wert: (
            f"{spalte}={wert} liegt ausserhalb von {list(grenzen[spalte])}"
        ),
    )


def pruefe_r016(kontext: Kontext) -> Befund:
    """``zuers_zone`` steht in den ZUERS-Gefaehrdungsklassen {1, 2, 3, 4}."""
    return _pruefe_spalten(
        kontext,
        regel_id="R-016",
        entitaet="risiko_hausrat",
        schicht=Schicht.TYPED,
        pruefungen={"zuers_zone": lambda wert: int(wert) in wb.ZUERS_ZONEN},
        meldung=lambda _, wert: (
            f"zuers_zone={wert} steht nicht im Katalog {list(wb.ZUERS_ZONEN)}"
        ),
    )


def pruefe_r017(kontext: Kontext) -> Befund:
    """``bauartklasse`` steht in GDV Anlage 12 und ist als Zeichenkette gefuehrt.

    Der Katalog ist gemischt numerisch und alphabetisch (``0`` bis ``8``, ``A``
    bis ``I``) und deshalb zwingend eine Zeichenkette. Der Buchstabe ``J``
    existiert nicht.
    """
    sammler = Befundsammler("R-017")
    _typpruefung(
        kontext, entitaet="risiko_hausrat", spalten=("bauartklasse",), sammler=sammler
    )
    rahmen = kontext.rahmen(Schicht.RAW, "risiko_hausrat")
    kennungen = row_ids(rahmen)
    katalog = frozenset(BAUARTKLASSEN)
    for position, wert in enumerate(text(rahmen, "bauartklasse")):
        if _leer(wert) or wert in katalog:
            continue
        sammler.melde(
            "risiko_hausrat",
            kennungen[position],
            ("bauartklasse",),
            f"bauartklasse={wert!r} steht nicht in GDV Anlage 12",
        )
    return sammler.befund()


def pruefe_r018(kontext: Kontext) -> Befund:
    """``anfrage_status`` steht im definierten Enum."""
    katalog = frozenset(wert.value for wert in Anfragestatus)
    return _pruefe_spalten(
        kontext,
        regel_id="R-018",
        entitaet="anfrage",
        schicht=Schicht.TYPED,
        pruefungen={"anfrage_status": lambda wert: str(wert) in katalog},
        meldung=lambda _, wert: (
            f"anfrage_status={wert!r} steht nicht im Katalog {sorted(katalog)}"
        ),
    )


def pruefe_r019(kontext: Kontext) -> Befund:
    """``nutzungsart`` steht im Katalog der GDV-Satzart 0210.050."""
    katalog = frozenset(wert.value for wert in Nutzungsart)
    return _pruefe_spalten(
        kontext,
        regel_id="R-019",
        entitaet="risiko_kfz",
        schicht=Schicht.TYPED,
        pruefungen={"nutzungsart": lambda wert: str(wert) in katalog},
        meldung=lambda _, wert: f"nutzungsart={wert!r} steht nicht im Katalog {sorted(katalog)}",
    )


def pruefe_r020(kontext: Kontext) -> Befund:
    """``art_kennzeichen`` steht im Katalog der GDV-Satzart 0210.050."""
    katalog = frozenset(wert.value for wert in ArtKennzeichen)
    return _pruefe_spalten(
        kontext,
        regel_id="R-020",
        entitaet="risiko_kfz",
        schicht=Schicht.TYPED,
        pruefungen={"art_kennzeichen": lambda wert: str(wert) in katalog},
        meldung=lambda _, wert: (
            f"art_kennzeichen={wert!r} steht nicht im Katalog {sorted(katalog)}"
        ),
    )


# ---------------------------------------------------------------------------
# R-021 bis R-024 — Wertebereiche
# ---------------------------------------------------------------------------

#: Beitrags- und Summenfelder je Entitaet (R-021).
#:
#: Geltungsbereich nach ``spec/02``: ``angebot``, ``risiko_hausrat`` und
#: ``tarif``. ``risiko_kfz.neupreis_eur`` und ``fahrzeugwert_aktuell`` sind
#: bewusst **nicht** enthalten — sie sind Fahrzeugwerte, keine Beitrags- oder
#: Versicherungssummen, und werden von R-038 gegeneinander geprueft.
_BEITRAGS_UND_SUMMENFELDER: Final[Mapping[str, tuple[str, ...]]] = {
    "angebot": (
        "nettobeitrag_jahr_eur",
        "versicherungsteuer_satz",
        "versicherungsteuer_eur",
        "bruttobeitrag_jahr_eur",
        "ratenzahlungszuschlag_prozent",
        "zahlbeitrag_rate_eur",
        "sb_tk_eur",
        "sb_vk_eur",
        "sb_hausrat_prozent",
        "sb_hausrat_eur",
    ),
    "risiko_hausrat": (
        "versicherungssumme_eur",
        "sublimit_fahrrad_eur",
        "sublimit_wertsachen_eur",
    ),
    "tarif": (
        "deckungssumme_personen_eur",
        "deckungssumme_sach_eur",
        "deckungssumme_vermoegen_eur",
    ),
}


def pruefe_r021(kontext: Kontext) -> Befund:
    """Alle Beitrags- und Summenfelder sind groesser oder gleich null.

    Ein negativer Beitrag ist fachlich unmoeglich — es gibt keine Versicherung,
    die Geld auszahlt, statt es zu nehmen.
    """
    sammler = Befundsammler("R-021")
    for entitaet, spalten in _BEITRAGS_UND_SUMMENFELDER.items():
        rahmen = kontext.rahmen(Schicht.TYPED, entitaet)
        kennungen = row_ids(rahmen)
        for spalte in spalten:
            for position, wert in enumerate(werte(rahmen, spalte)):
                if wert is None or Decimal(str(wert)) >= 0:
                    continue
                sammler.melde(
                    entitaet,
                    kennungen[position],
                    (spalte,),
                    f"{spalte}={wert} ist negativ",
                )
    return sammler.befund()


def pruefe_r022(kontext: Kontext) -> Befund:
    """``wohnflaeche_qm`` liegt im plausiblen Korridor.

    Schwellenwertbasiert (C2) und deshalb eine **Warnung**: Der Korridor steht in
    ``config.schwellen.r022_wohnflaeche`` und wird in der Arbeit variiert. Werte
    ausserhalb sind Eingabe- oder Einheitenfehler — etwa Quadratfuss statt
    Quadratmeter.
    """
    grenzen = kontext.schwellen.r022_wohnflaeche
    return _pruefe_spalten(
        kontext,
        regel_id="R-022",
        entitaet="risiko_hausrat",
        schicht=Schicht.TYPED,
        pruefungen={"wohnflaeche_qm": lambda wert: _im_bereich(wert, grenzen)},
        meldung=lambda _, wert: (
            f"wohnflaeche_qm={wert} liegt ausserhalb des plausiblen Korridors {list(grenzen)}"
        ),
    )


def pruefe_r023(kontext: Kontext) -> Befund:
    """``baujahr`` liegt zwischen 1500 und dem Jahr des Stichtags.

    Die Obergrenze kommt aus der Konfiguration (``stichtag``), nicht aus der
    Systemzeit (Architekturregel A2). Die Untergrenze ist bewusst weiter gefasst
    als der Ziehungsbereich des Generators: Die Regel soll ein **unmoegliches**
    Baujahr erkennen, kein ungewoehnliches.
    """
    grenzen = (wb.BAUJAHR_UNTERGRENZE_REGEL, kontext.stichtag.year)
    return _pruefe_spalten(
        kontext,
        regel_id="R-023",
        entitaet="risiko_hausrat",
        schicht=Schicht.TYPED,
        pruefungen={"baujahr": lambda wert: _im_bereich(wert, grenzen)},
        meldung=lambda _, wert: f"baujahr={wert} liegt ausserhalb von {list(grenzen)}",
    )


def pruefe_r024(kontext: Kontext) -> Befund:
    """Die Deckungssummen erreichen die gesetzliche Mindestdeckung.

    PflVG, Anlage zu Paragraf 4 Absatz 2. Leere Felder werden uebergangen: Nur
    die Kfz-Haftpflicht fuehrt Deckungssummen; in den uebrigen Sparten sind sie
    durch Zweckbindung leer (``spec/01``, Abschnitt 3.5).
    """
    mindestdeckung = {
        "deckungssumme_personen_eur": wb.PFLVG_MINDESTDECKUNG_PERSONEN_EUR,
        "deckungssumme_sach_eur": wb.PFLVG_MINDESTDECKUNG_SACH_EUR,
        "deckungssumme_vermoegen_eur": wb.PFLVG_MINDESTDECKUNG_VERMOEGEN_EUR,
    }
    return _pruefe_spalten(
        kontext,
        regel_id="R-024",
        entitaet="tarif",
        schicht=Schicht.TYPED,
        pruefungen={
            spalte: _mindestwertpruefung(grenze) for spalte, grenze in mindestdeckung.items()
        },
        meldung=lambda spalte, wert: (
            f"{spalte}={wert} unterschreitet die gesetzliche Mindestdeckung "
            f"{mindestdeckung[spalte]}"
        ),
    )


# ---------------------------------------------------------------------------
# R-025 — implizite Fehlwerte
# ---------------------------------------------------------------------------

#: Feldtypen, in denen ein numerisches Sentinel geprueft wird (R-025).
_NUMERISCHE_TYPEN: Final[frozenset[Feldtyp]] = frozenset({Feldtyp.GANZZAHL, Feldtyp.DEZIMAL})


def _als_zahl(rohwert: str) -> Decimal | None:
    """Wandelt einen Rohwert in eine Zahl um, oder ``None``, wenn er keine ist."""
    try:
        return Decimal(rohwert)
    except (InvalidOperation, ValueError):
        return None


def pruefe_r025(kontext: Kontext) -> Befund:
    """Kein Feld enthaelt einen impliziten Fehlwert.

    Implizite Fehlwerte sind Fehlwerte, die als gefuellte Werte getarnt sind —
    der klassische Fall, den eine reine NOT-NULL-Pruefung verfehlt. Die Regel
    arbeitet auf der Rohschicht, weil ``k.A.`` in einer ``Decimal``-Spalte gar
    nicht schreibbar waere.

    Drei Wertevorraete je Datentyp, alle aus
    :mod:`src.common.wertebereiche`:

    * Textfelder: :data:`~src.common.wertebereiche.SENTINEL_TEXT_ROHSCHICHT`
      (``-``, ``k.A.``, ``n/a``, ``unbekannt``). **Der Leerstring fehlt bewusst**;
      die Begruendung steht an der Konstanten.
    * Datumsfelder: :data:`~src.common.wertebereiche.SENTINEL_DATUM`
      (``00000000``, ``01011900`` und ihre ISO-Schreibweisen).
    * Numerische Felder: :data:`~src.common.wertebereiche.SENTINEL_NUMERISCH`
      (9999, 99999999) — **ausgenommen** die Felder aus
      :data:`~src.common.wertebereiche.SENTINEL_AUSNAHMEFELDER`, in denen 9999 ein
      legitimer Wert ist.

    Die Ausnahmeliste ist selbst ein Ergebnis: Sie zeigt die Grenze von
    Sentinel-Heuristiken, sobald der Sentinel im fachlich zulaessigen Wertebereich
    liegt. Der Erkennbarkeitsgrad ist deshalb C2 und der Schweregrad WARNUNG.
    """
    sammler = Befundsammler("R-025")
    text_sentinels = {wert.casefold() for wert in wb.SENTINEL_TEXT_ROHSCHICHT}
    datums_sentinels = frozenset(wb.SENTINEL_DATUM)
    zahl_sentinels = {Decimal(wert) for wert in wb.SENTINEL_NUMERISCH}
    ausnahmen = frozenset(wb.SENTINEL_AUSNAHMEFELDER)
    technisch = frozenset(wb.TECHNISCHE_SCHLUESSELFELDER)

    for entitaet, spalten in SPALTEN_JE_ENTITAET.items():
        rahmen = kontext.rahmen(Schicht.RAW, entitaet)
        if rahmen.empty:
            continue
        kennungen = row_ids(rahmen)
        for spalte in spalten:
            if spalte in technisch or f"{entitaet}.{spalte}" in ausnahmen:
                continue
            feldtyp = FELDTYP_JE_SPALTE[spalte]
            for position, wert in enumerate(text(rahmen, spalte)):
                if _leer(wert):
                    continue
                grund = _sentinelbefund(
                    wert,
                    feldtyp,
                    text_sentinels=text_sentinels,
                    datums_sentinels=datums_sentinels,
                    zahl_sentinels=zahl_sentinels,
                )
                if grund is not None:
                    sammler.melde(
                        entitaet,
                        kennungen[position],
                        (spalte,),
                        f"{spalte}={wert!r} ist ein {grund}",
                    )
    return sammler.befund()


def _sentinelbefund(
    wert: str,
    feldtyp: Feldtyp,
    *,
    text_sentinels: set[str],
    datums_sentinels: frozenset[str],
    zahl_sentinels: set[Decimal],
) -> str | None:
    """Gibt den Sentinel-Befund eines Rohwerts zurueck, oder ``None``."""
    if feldtyp is Feldtyp.TEXT and wert.strip().casefold() in text_sentinels:
        return "impliziter Fehlwert in einem Textfeld"
    if feldtyp is Feldtyp.DATUM and wert in datums_sentinels:
        return "impliziter Fehlwert in einem Datumsfeld"
    if feldtyp in _NUMERISCHE_TYPEN:
        zahl = _als_zahl(wert)
        if zahl is not None and zahl in zahl_sentinels:
            return "impliziter Fehlwert in einem numerischen Feld"
    return None


# ---------------------------------------------------------------------------
# Registrierung
# ---------------------------------------------------------------------------

REGELN: Final[tuple[Regel, ...]] = (
    Regel(
        regel_id="R-001",
        beschreibung=(
            "Kernpflichtfelder sind nicht leer; bei anrede ungleich FIRMA zusaetzlich "
            "das Geburtsdatum"
        ),
        entitaet="anfrage, person",
        spalten=(
            "anfrage_id",
            "eingangszeitpunkt",
            "sparte",
            "vn_person_id",
            "nachname",
            "plz",
            "geburtsdatum",
            "anrede",
        ),
        granularitaet="G1",
        fehlerklasse_b="B1",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD", "KIM", "FAN", "DAMA"),
        fachliche_grundlage=(
            "Ohne diese Felder ist keine Tarifierung moeglich. Der bedingte Teil ist ein "
            "CFD-Beispiel: Eine juristische Person hat kein Geburtsdatum"
        ),
        schicht=Schicht.TYPED,
        pruefe=pruefe_r001,
    ),
    Regel(
        regel_id="R-002",
        beschreibung="plz erfuellt ^\\d{5}$ und ist als Zeichenkette gefuehrt",
        entitaet="person",
        spalten=("plz",),
        granularitaet="G1",
        fehlerklasse_b="B2",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("FOI", "RD"),
        fachliche_grundlage="Fuehrende Null (01067) geht bei Integer-Typisierung verloren",
        schicht=Schicht.RAW,
        pruefe=pruefe_r002,
    ),
    Regel(
        regel_id="R-003",
        beschreibung="iban erfuellt ^DE\\d{20}$ (genau 22 Zeichen)",
        entitaet="zahlung",
        spalten=("iban",),
        granularitaet="G1",
        fehlerklasse_b="B2",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD", "DAMA"),
        fachliche_grundlage="ISO 13616, deutsche IBAN-Laenge",
        schicht=Schicht.RAW,
        pruefe=pruefe_r003,
    ),
    Regel(
        regel_id="R-004",
        beschreibung="iban besteht die Pruefziffernpruefung Mod 97-10",
        entitaet="zahlung",
        spalten=("iban",),
        granularitaet="G1",
        fehlerklasse_b="B2",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD", "ISO"),
        fachliche_grundlage="ISO 7064",
        schicht=Schicht.RAW,
        pruefe=pruefe_r004,
    ),
    Regel(
        regel_id="R-005",
        beschreibung="bic hat exakt 8 oder 11 Zeichen",
        entitaet="zahlung",
        spalten=("bic",),
        granularitaet="G1",
        fehlerklasse_b="B2",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD",),
        fachliche_grundlage="ISO 9362 — 9 oder 10 Zeichen existieren nicht",
        schicht=Schicht.RAW,
        pruefe=pruefe_r005,
    ),
    Regel(
        regel_id="R-006",
        beschreibung="email erfuellt das vereinfachte RFC-5322-Muster",
        entitaet="person",
        spalten=("email",),
        granularitaet="G1",
        fehlerklasse_b="B2",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD", "FOI"),
        fachliche_grundlage="RFC 5322, vereinfachte Form",
        schicht=Schicht.RAW,
        pruefe=pruefe_r006,
    ),
    Regel(
        regel_id="R-007",
        beschreibung="hsn erfuellt ^\\d{4}$",
        entitaet="risiko_kfz",
        spalten=("hsn",),
        granularitaet="G1",
        fehlerklasse_b="B2",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD",),
        fachliche_grundlage="KBA, Zulassungsbescheinigung Teil I, Feld 2.1",
        schicht=Schicht.RAW,
        pruefe=pruefe_r007,
    ),
    Regel(
        regel_id="R-008",
        beschreibung="tsn erfuellt ^[A-Z0-9]{3}$",
        entitaet="risiko_kfz",
        spalten=("tsn",),
        granularitaet="G1",
        fehlerklasse_b="B2",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD",),
        fachliche_grundlage="Zulassungsbescheinigung Teil I, Feld 2.2",
        schicht=Schicht.RAW,
        pruefe=pruefe_r008,
    ),
    Regel(
        regel_id="R-009",
        beschreibung="Jedes Datumsfeld der Rohschicht ist ein existierender Kalendertag",
        entitaet="alle",
        spalten=_DATUMSSPALTEN,
        granularitaet="G1",
        fehlerklasse_b="B2",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD", "FOI"),
        fachliche_grundlage=(
            "31022026 ist formal achtstellig, aber kein Kalendertag. Zwingend auf der "
            "Rohschicht (spec/01, Abschnitt 6)"
        ),
        schicht=Schicht.RAW,
        pruefe=pruefe_r009,
    ),
    Regel(
        regel_id="R-010",
        beschreibung="zahlweise steht im GDV-Katalog {1, 2, 4, 5, 6, 8, 9}",
        entitaet="anfrage",
        spalten=("zahlweise",),
        granularitaet="G1",
        fehlerklasse_b="B2",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD", "KIM"),
        fachliche_grundlage="GDV Anlage 14 — 3 und 7 existieren nicht",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r010,
    ),
    Regel(
        regel_id="R-011",
        beschreibung="sparte steht im Spartenverzeichnis {051, 052, 053, 130}",
        entitaet="anfrage, tarif",
        spalten=("sparte",),
        granularitaet="G1",
        fehlerklasse_b="B2",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD",),
        fachliche_grundlage="GDV Anlage 1, Spartenverzeichnis",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r011,
    ),
    Regel(
        regel_id="R-012",
        beschreibung=(
            "waehrung existiert im ISO-4217-Katalog und ist im Kontext dieses Systems EUR"
        ),
        entitaet="anfrage",
        spalten=("waehrung",),
        granularitaet="G1",
        fehlerklasse_b="B2",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD",),
        fachliche_grundlage="ISO 4217, zweistufig: syntaktische Gueltigkeit und Zulaessigkeit",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r012,
    ),
    Regel(
        regel_id="R-013",
        beschreibung=(
            "sf_klasse_* steht im Katalog {0, 1/2, S, M, SF1..SF50} und ist Zeichenkette"
        ),
        entitaet="risiko_kfz",
        spalten=("sf_klasse_hp", "sf_klasse_vk"),
        granularitaet="G1",
        fehlerklasse_b="B2",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD", "FOI"),
        fachliche_grundlage="Sonderklassen sind keine Zahlen; Integer-Typisierung ist ein Fehler",
        schicht=Schicht.RAW,
        pruefe=pruefe_r013,
    ),
    Regel(
        regel_id="R-014",
        beschreibung="typklasse_hp in [10,25], _tk in [10,33], _vk in [10,34]",
        entitaet="risiko_kfz",
        spalten=("typklasse_hp", "typklasse_tk", "typklasse_vk"),
        granularitaet="G1",
        fehlerklasse_b="B2",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD", "KIM", "DAMA"),
        fachliche_grundlage="GDV-Typklassenverzeichnis: 16 / 24 / 25 Klassen",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r014,
    ),
    Regel(
        regel_id="R-015",
        beschreibung="regionalklasse_hp in [1,12], _tk in [1,16], _vk in [1,9]",
        entitaet="risiko_kfz",
        spalten=("regionalklasse_hp", "regionalklasse_tk", "regionalklasse_vk"),
        granularitaet="G1",
        fehlerklasse_b="B2",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD",),
        fachliche_grundlage="GDV-Regionalklassen: 12 / 16 / 9 Stufen",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r015,
    ),
    Regel(
        regel_id="R-016",
        beschreibung="zuers_zone steht in {1, 2, 3, 4}",
        entitaet="risiko_hausrat",
        spalten=("zuers_zone",),
        granularitaet="G1",
        fehlerklasse_b="B2",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD",),
        fachliche_grundlage="ZUERS-Gefaehrdungsklassen",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r016,
    ),
    Regel(
        regel_id="R-017",
        beschreibung="bauartklasse steht in GDV Anlage 12 und ist als Zeichenkette gefuehrt",
        entitaet="risiko_hausrat",
        spalten=("bauartklasse",),
        granularitaet="G1",
        fehlerklasse_b="B2",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD", "FOI"),
        fachliche_grundlage="GDV Anlage 12 — gemischt numerisch und alphabetisch",
        schicht=Schicht.RAW,
        pruefe=pruefe_r017,
    ),
    Regel(
        regel_id="R-018",
        beschreibung="anfrage_status steht im definierten Enum",
        entitaet="anfrage",
        spalten=("anfrage_status",),
        granularitaet="G1",
        fehlerklasse_b="B2",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD",),
        fachliche_grundlage="Prozessstatus des Vergleichssystems",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r018,
    ),
    Regel(
        regel_id="R-019",
        beschreibung="nutzungsart steht in {01, 02, 03, 08}",
        entitaet="risiko_kfz",
        spalten=("nutzungsart",),
        granularitaet="G1",
        fehlerklasse_b="B2",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD",),
        fachliche_grundlage="GDV Satzart 0210.050",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r019,
    ),
    Regel(
        regel_id="R-020",
        beschreibung="art_kennzeichen steht in {01, 04, 54}",
        entitaet="risiko_kfz",
        spalten=("art_kennzeichen",),
        granularitaet="G1",
        fehlerklasse_b="B2",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD",),
        fachliche_grundlage="GDV Satzart 0210.050",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r020,
    ),
    Regel(
        regel_id="R-021",
        beschreibung="Alle Beitrags- und Summenfelder sind groesser oder gleich null",
        entitaet="angebot, risiko_hausrat, tarif",
        spalten=tuple(
            spalte for spalten in _BEITRAGS_UND_SUMMENFELDER.values() for spalte in spalten
        ),
        granularitaet="G1",
        fehlerklasse_b="B3",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD", "KIM"),
        fachliche_grundlage="Negative Beitraege sind fachlich unmoeglich",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r021,
    ),
    Regel(
        regel_id="R-022",
        beschreibung="wohnflaeche_qm liegt im plausiblen Korridor (config.schwellen)",
        entitaet="risiko_hausrat",
        spalten=("wohnflaeche_qm",),
        granularitaet="G1",
        fehlerklasse_b="B3",
        erkennbarkeit_c="C2",
        schweregrad="WARNUNG",
        literatur=("ABE", "FOI"),
        fachliche_grundlage="Werte ausserhalb sind Eingabe- oder Einheitenfehler",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r022,
    ),
    Regel(
        regel_id="R-023",
        beschreibung="baujahr liegt zwischen 1500 und dem Jahr des Stichtags",
        entitaet="risiko_hausrat",
        spalten=("baujahr",),
        granularitaet="G1",
        fehlerklasse_b="B3",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD", "FOI"),
        fachliche_grundlage="Ein Baujahr in der Zukunft ist unmoeglich",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r023,
    ),
    Regel(
        regel_id="R-024",
        beschreibung=(
            "deckungssumme_personen >= 7.500.000, _sach >= 1.300.000, _vermoegen >= 50.000"
        ),
        entitaet="tarif",
        spalten=(
            "deckungssumme_personen_eur",
            "deckungssumme_sach_eur",
            "deckungssumme_vermoegen_eur",
        ),
        granularitaet="G1",
        fehlerklasse_b="B3",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD", "DAMA"),
        fachliche_grundlage="PflVG, Anlage zu Paragraf 4 Absatz 2 — gesetzliche Mindestdeckung",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r024,
    ),
    Regel(
        regel_id="R-025",
        beschreibung=(
            "Kein Feld enthaelt einen impliziten Fehlwert (Sentinel je Datentyp, "
            "ausgenommen die Felder mit legitimem Sentinelwert)"
        ),
        entitaet="alle",
        spalten=("*",),
        granularitaet="G1",
        fehlerklasse_b="B1",
        erkennbarkeit_c="C2",
        schweregrad="WARNUNG",
        literatur=("FOI", "RD", "KIM"),
        fachliche_grundlage=(
            "Fehlwerte, die als gefuellte Werte getarnt sind. Die Ausnahmeliste zeigt die "
            "Grenze von Sentinel-Heuristiken"
        ),
        schicht=Schicht.RAW,
        pruefe=pruefe_r025,
    ),
)
