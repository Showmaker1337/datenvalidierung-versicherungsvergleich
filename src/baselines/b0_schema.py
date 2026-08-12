"""Baseline B0: reine Schemavalidierung mit ``pydantic`` v2.

B0 ist die **untere Schranke** des Vergleichs. Es beantwortet die Frage, wie weit
man kommt, wenn man ueber die Daten nichts weiss ausser dem, was in einer
Schnittstellenbeschreibung steht: welchen Typ ein Feld hat, ob es belegt sein
muss und wie lang es sein darf. Alles, was darueber hinausgeht, ist Fachwissen —
und genau dieses Fachwissen ist der Gegenstand der Arbeit. Waere es in B0
enthalten, waere B0 keine Baseline mehr, sondern ein zweiter Prototyp.

Was B0 prueft — und was ausdruecklich nicht
-------------------------------------------

Geprueft werden genau drei Dinge:

1. **Typ.** Laesst sich der Rohwert in den Feldtyp aus ``spec/01``, Abschnitt 3
   ueberfuehren? Die Rohschicht liefert ausschliesslich Zeichenketten
   (``spec/01``, Abschnitt 6); ``pydantic`` bekommt sie im nachgiebigen Modus
   (``strict=False``) und wandelt sie um.
2. **Nullable-Constraint.** Ist ein als Pflicht ausgewiesenes Feld belegt?
3. **Feldlaenge.** Exakte Laengen (``plz`` fuenf Zeichen) und Obergrenzen
   (``nachname`` hoechstens fuenfzig).

Nicht geprueft werden — jede Auslassung ist Absicht:

* **Keine Enums.** ``kanal``, ``anrede``, ``familienstand``, ``gebaeudeart``,
  ``annahmeentscheidung`` und alle uebrigen Aufzaehlungen sind fuer B0 einfach
  Text. Ein Wertekatalog ist bereits Domaenenwissen.
* **Keine Wertebereiche ueber den Datentyp hinaus.** Kein ``ge=0``, kein
  ``le=100``, kein ``max_digits``. Insbesondere wird ``Decimal(10,2)`` aus
  ``spec/01`` **nicht** als ``max_digits=10, decimal_places=2`` umgesetzt: Eine
  Stellenzahlgrenze faenge Skalierungsfehler der Klasse F3 (Faktor 1000) ab, und
  das waere eine Plausibilitaetspruefung, keine Typpruefung. Die untere Schranke
  bliebe dann nicht unten.
* **Keine Feldabhaengigkeiten.** Weder zwischen Feldern einer Zeile noch zwischen
  Entitaeten. Ein Fremdschluessel wird auf Belegung geprueft, nicht auf Existenz
  des Ziels.
* **Keine Pruefziffern.** Die IBAN wird auf zweiundzwanzig Zeichen geprueft, nicht
  auf ISO 7064 Mod 97-10.
* **Keine Muster.** Auch dort nicht, wo ein Muster naheliegt: ``bic`` hat acht
  **oder** elf Zeichen, und das ist hier als **Laengenmenge** hinterlegt und nicht
  als regulaerer Ausdruck. Ein Ausdruck wie ``^[A-Z]{6}[A-Z0-9]{2}...`` waere eine
  Formatregel und gehoerte damit in den Prototyp, nicht in die Baseline.

Die eine Ausnahme, die keine ist: das Datum
--------------------------------------------

Eine Grenze laesst sich nicht ziehen, und sie wird hier benannt statt verschwiegen.
``spec/01``, Abschnitt 6 legt die Rohform eines Datums als ``TTMMJJJJ`` fest. Wer
diese Zeichenkette in ein ``datetime.date`` ueberfuehrt — und genau das ist die
Typpruefung, die B0 ausmacht —, weist ``31022026`` zwangslaeufig zurueck: Den Tag
gibt es nicht, das Objekt ist nicht konstruierbar. Damit deckt B0 den Inhalt der
Prototypregel R-009 ("jedes Datumsfeld der Rohschicht ist ein existierender
Kalendertag") **vollstaendig** ab, ohne sie zu kennen.

Das ist keine eingeschmuggelte Fachregel, sondern die Eigenschaft eines Typs: Die
Menge der gueltigen Kalendertage **ist** der Wertebereich von ``date``. Fuer die
Auswertung folgt daraus zweierlei, und beides gehoert in die Arbeit:

* B0 erreicht auf der Fehlerklasse F2 (Format und Syntax) einen deutlich hoeheren
  Recall als auf F1 — der Abstand zwischen Baseline und Prototyp ist je
  Fehlerklasse verschieden gross, und genau das ist die interessante Aussage.
* Dieselbe Regel fuehrt die Baseline B3 als **nicht** ausdrueckbar. Eine
  DataFrame-Check-API kennt Muster, aber keinen Kalender; acht Ziffern sind
  formulierbar, der 31. Februar nicht. Ein Typsystem loest die Aufgabe also
  nebenbei, das etablierte Framework gar nicht. Diese Umkehrung der erwarteten
  Rangfolge ist ein eigenes Ergebnis des Vergleichs.

Warum ``person.nachname`` kein Pflichtfeld ist
----------------------------------------------

Diese Abgrenzung entscheidet ueber einen sichtbaren Teil des Ergebnisses und wird
deshalb hier ausgeschrieben.

``spec/01``, Abschnitt 3.2 fuehrt ``nachname`` mit der Abhaengigkeit
"nicht leer, **ausser** ``anrede`` = FIRMA". Das ist keine Nullable-Angabe,
sondern eine **bedingte funktionale Abhaengigkeit**: Ob das Feld belegt sein muss,
haengt vom Wert eines anderen Feldes derselben Zeile ab. Wer sie in ein Schema
schreibt, hat den Wertekatalog von ``anrede`` bereits vorausgesetzt und eine
fachliche Regel formuliert — im Prototyp ist das R-001, hergeleitet und belegt.

B0 kennt solche Bedingungen per Definition nicht. Ein unbedingtes
``nachname: str`` waere zudem sachlich falsch: Es wuerde auf dem **sauberen**
Datensatz bei jeder Firmenzeile ausloesen, also Fehlalarme erzeugen, wo kein
Fehler ist. Ein optionales ``nachname: str | None`` ist die einzige Fassung, die
ein reines Schema hergibt.

Die Folge ist messbar und gehoert in die Arbeit: Die Fehlerklasse F1 (fehlende
Pflichtangaben) trifft ueberwiegend Felder, deren Pflichtcharakter bedingt ist —
an ``kanal``, an ``sparte``, an ``anrede``. B0 kann davon nur den unbedingten Rest
finden und erreicht auf F1 deshalb einen kleinen Recall. Das ist kein Defekt der
Baseline, sondern die gesuchte Aussage: Der Abstand zwischen B0 und dem Prototyp
**ist** der Beitrag der Fehlertaxonomie.

Pflicht sind entsprechend nur die Felder, die ``spec/01``, Abschnitt 3 **ohne
Bedingung** als Schluessel oder als Pflicht auszeichnet: ``row_id``, alle Primaer-
und Fremdschluessel sowie ``anfrage.eingangszeitpunkt``, ``anfrage.sparte`` und
``person.plz``. ``anfrage.vorversicherer_vu_nr`` ist zwar ein Fremdschluessel,
gilt aber nur "wenn ``vorvertrag_vorhanden``" — also bedingt und damit optional.

Leer heisst leer: der Schluessel fehlt, statt ``None`` zu tragen
-----------------------------------------------------------------

Auf der Rohschicht ist ein leerer Wert der **Leerstring** (``spec/01``,
Abschnitt 6). Beim Aufbau der Zeilendarstellung wird ein leeres Feld deshalb
**weggelassen** statt auf ``None`` gesetzt. Der Unterschied ist kein Detail: Nur
so meldet ``pydantic`` fuer ein leeres Pflichtfeld den Fehlertyp ``missing``
("Field required") — also genau die Nullable-Verletzung — statt eines
Typfehlers ueber ``None``. Die Nullable-Pruefung bleibt damit dem Framework
ueberlassen und wird nicht von Hand nachgebaut.

Der Preis dieser Serialisierung ist bekannt und in ``CLAUDE.md``, Abschnitt 5
festgehalten: Ein injizierter Leerstring (Variante F1-b) ist auf der Rohschicht
von einem planmaessig leeren Feld nicht zu unterscheiden. B0 findet ihn folglich
nur in den unbedingten Pflichtfeldern — dieselbe Grenze, die auch der Prototyp
dort hat, wo er nicht mit einer Bedingung nachhelfen kann.

Ein Modell je Entitaet, erzeugt aus dem Schema
-----------------------------------------------

Die sieben Modelle entstehen ueber :func:`pydantic.create_model` aus
:data:`~src.common.serialisierung.SPALTEN_JE_ENTITAET` und
:data:`~src.common.serialisierung.FELDTYP_JE_SPALTE`, nicht als
einhundertvier von Hand geschriebene Feldzeilen. Der Grund ist die eine Quelle
der Wahrheit: Das Schema steht in ``src/common/serialisierung.py``, und eine
handgeschriebene Kopie geriete beim ersten Feldwechsel aus dem Tritt — nicht
sichtbar als Fehler, sondern als leise verschobene Kennzahl. Das Vergleichbare
bleibt so vergleichbar: B0 sieht dieselben Spalten wie der Prototyp.

``ConfigDict(strict=False, extra="forbid")`` ist die Konfiguration aller sieben
Modelle. ``strict=False``, weil die Rohschicht nur Zeichenketten liefert und die
Umwandlung genau der Vorgang ist, dessen Fehleranfaelligkeit gemessen werden soll.
``extra="forbid"``, damit eine Spalte, die es im Schema nicht gibt, auffaellt
statt durchzurutschen.

Zwei Rohformen kann ``pydantic`` nicht von sich aus lesen und bekommen deshalb je
einen ``BeforeValidator``: das GDV-Datum ``TTMMJJJJ`` (``pydantic`` erwartet ISO
8601) und den Wahrheitswert ``J``/``N`` (``pydantic`` kennt ``true``/``yes``/``1``,
aber nicht die GDV-Kuerzel). Diese beiden Vorschalter sind **Framework-Reibung**
und werden als solche berichtet: Sie sind der Preis dafuer, ein allgemeines
Schemawerkzeug auf ein Branchenformat zu setzen. Zeitpunkt, ganze Zahl und
Dezimalwert liest ``pydantic`` dagegen unveraendert aus der Rohform.

Zeilenweise Validierung ist langsam — und genau das ist ein Ergebnis
---------------------------------------------------------------------

``pydantic`` validiert Objekte, nicht Spalten. Ein Lauf mit rund
einhunderttausend Zeilen bedeutet einhunderttausend Aufrufe von
``model_validate``, jeder mit dem Aufbau eines Modellobjekts. Der Prototyp
arbeitet dagegen spaltenweise auf ``pandas``. Der Laufzeitunterschied ist deshalb
kein Implementierungsdetail, sondern eine Eigenschaft der Werkzeugklasse; er wird
in :class:`~src.evaluation.modell.Laufmessung` mitgemessen und gehoert in die
Diskussion. Eine Beschleunigung ueber Stapelvalidierung waere moeglich, wuerde
aber genau die Eigenschaft verstecken, die hier berichtet werden soll.

Berichtsform
------------

Jeder Einzelfehler wird eine eigene Meldung: ``regel_id`` ist ``B0-<feldname>``,
``verstoss_id`` ist ``B0-<feldname>#<laufende Nummer>``. Meldet ``pydantic`` fuer
eine Zeile mehrere Fehler, entstehen mehrere Meldungen. B0 kennt keine
mehrspaltigen Bedingungen, also faellt hier je Verstoss genau eine Zelle an; die
Constraint-Ebene der Auswertung ist fuer B0 damit fast identisch zur Zellebene.
Auch das ist die Aussage und kein Mangel der Behandlung.

Der Meldungstext nennt die Spalte, eine deutsche Klartextfassung der Fehlerart
und den Rohwert. Fehlerarten, fuer die keine Klartextfassung hinterlegt ist,
tragen den Text von ``pydantic`` unveraendert weiter — beschoenigt wird nichts,
denn die Diagnoseguete der Baseline ist selbst eine Messgroesse.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Any, Final

import pandas as pd
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    StringConstraints,
    ValidationError,
    create_model,
)

from src.common.serialisierung import (
    ENTITAETEN,
    FELDTYP_JE_SPALTE,
    LEER_ROH,
    SPALTEN_JE_ENTITAET,
    Feldtyp,
)
from src.evaluation.modell import ROW_ID_OHNE_BEZUG, VERSTOSS_SPALTEN, AuswertungsFehler

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Iterable, Iterator, Mapping, Sequence

    from pydantic import ValidationInfo
    from pydantic_core import ErrorDetails

    from src.evaluation.modell import Kontext, Verfahren

__all__ = [
    "EXAKTE_LAENGE",
    "LAENGENMENGE",
    "MAX_LAENGE",
    "MODELLE",
    "PFLICHTFELDER",
    "B0Schema",
]

#: Laenge des GDV-Datumsformats ``TTMMJJJJ``.
_DATUM_LAENGE: Final[int] = 8

#: Rohform des Wahrheitswertes "wahr" (spec/01, Abschnitt 6).
_ROH_JA: Final[str] = "J"

#: Rohform des Wahrheitswertes "falsch".
_ROH_NEIN: Final[str] = "N"

#: Praefix aller Regel- und Verstosskennungen dieser Baseline.
_PRAEFIX: Final[str] = "B0"


# ---------------------------------------------------------------------------
# Die Schemaangaben aus spec/01, Abschnitt 3
# ---------------------------------------------------------------------------

#: Felder mit **exakt** vorgegebener Laenge (spec/01, Abschnitt 3, Spalte
#: "Wertebereich / Format", Schreibweise ``str(n)``).
#:
#: ``iban`` steht hier mit zweiundzwanzig Zeichen, weil das die Laenge der
#: deutschen IBAN ist — die Pruefziffer bleibt B0 verborgen, ihre Laenge nicht.
EXAKTE_LAENGE: Final[Mapping[str, int]] = MappingProxyType(
    {
        "art_kennzeichen": 2,
        "bauartklasse": 1,
        "eigentumsverhaeltnis": 1,
        "hsn": 4,
        "iban": 22,
        "nutzungsart": 2,
        "plz": 5,
        "sparte": 3,
        "tsn": 3,
        "vu_nummer": 5,
        "waehrung": 3,
        "wagniskennziffer": 3,
    }
)

#: Felder mit einer Laengenobergrenze (Schreibweise ``str(<=n)``).
MAX_LAENGE: Final[Mapping[str, int]] = MappingProxyType(
    {
        "email": 60,
        "hausnummer": 10,
        "kontoinhaber": 60,
        "nachname": 50,
        "ort": 50,
        "produktname": 20,
        "strasse": 30,
        "vorname": 30,
    }
)

#: Felder, deren Laenge aus einer **Menge** zulaessiger Werte stammt.
#:
#: Nur ``bic``: acht oder elf Zeichen, niemals neun oder zehn (spec/01,
#: Abschnitt 3.7). Bewusst als Laengenmenge und nicht als Muster — siehe
#: Modul-Docstring.
LAENGENMENGE: Final[Mapping[str, tuple[int, ...]]] = MappingProxyType({"bic": (8, 11)})

#: Unbedingte Pflichtfelder je Entitaet, in Schemareihenfolge.
#:
#: Enthalten sind ``row_id``, alle Primaer- und Fremdschluessel sowie die drei
#: Felder, die ``spec/01``, Abschnitt 3 ohne Bedingung als Pflicht auszeichnet.
#: Bedingte Pflichten (``person.nachname``, ``person.email``,
#: ``anfrage.vorversicherer_vu_nr``) stehen ausdruecklich **nicht** darin; die
#: Begruendung steht im Modul-Docstring.
PFLICHTFELDER: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "anfrage": ("row_id", "anfrage_id", "eingangszeitpunkt", "sparte", "vn_person_id"),
        "person": ("row_id", "person_id", "anfrage_id", "plz"),
        "risiko_kfz": ("row_id", "risiko_id", "anfrage_id", "hsn", "tsn"),
        "risiko_hausrat": ("row_id", "risiko_id", "anfrage_id"),
        "tarif": ("row_id", "tarif_id", "vu_nummer"),
        "angebot": ("row_id", "angebot_id", "anfrage_id", "tarif_id"),
        "zahlung": ("row_id", "zahlung_id", "anfrage_id"),
    }
)

#: Python-Typ je Feldtyp der typisierten Schicht.
_GRUNDTYP: Final[Mapping[Feldtyp, type[object]]] = MappingProxyType(
    {
        Feldtyp.TEXT: str,
        Feldtyp.GANZZAHL: int,
        Feldtyp.DEZIMAL: Decimal,
        Feldtyp.DATUM: dt.date,
        Feldtyp.ZEITPUNKT: dt.datetime,
        Feldtyp.WAHRHEIT: bool,
    }
)

#: Deutsche Klartextfassung der Fehlerarten von ``pydantic``.
#:
#: Nicht erfasste Arten behalten den Text des Frameworks; siehe
#: :func:`_klartext`.
_KLARTEXT: Final[Mapping[str, str]] = MappingProxyType(
    {
        "bool_parsing": "kein Wahrheitswert",
        "bool_type": "kein Wahrheitswert",
        "date_parsing": "kein Datum",
        "date_type": "kein Datum",
        "datetime_from_date_parsing": "kein Zeitpunkt nach ISO 8601",
        "datetime_parsing": "kein Zeitpunkt nach ISO 8601",
        "datetime_type": "kein Zeitpunkt nach ISO 8601",
        "decimal_parsing": "kein Dezimalwert",
        "decimal_type": "kein Dezimalwert",
        "extra_forbidden": "Feld gehoert nicht zum Schema der Entitaet",
        "int_parsing": "keine ganze Zahl",
        "int_type": "keine ganze Zahl",
        "missing": "Pflichtfeld ist nicht belegt",
        "string_too_long": "Wert ist laenger als das Feld zulaesst",
        "string_too_short": "Wert ist kuerzer als das Feld verlangt",
        "string_type": "kein Text",
    }
)


# ---------------------------------------------------------------------------
# Vorschalter fuer die beiden Rohformen, die pydantic nicht kennt
# ---------------------------------------------------------------------------


def _lies_datum(wert: Any) -> Any:  # noqa: ANN401 - pydantic reicht den Rohwert ungetypt durch
    """Ueberfuehrt die Rohform ``TTMMJJJJ`` in ein :class:`datetime.date`.

    Args:
        wert: Rohwert aus ``df_raw``. Nicht-Zeichenketten werden unveraendert
            durchgereicht, damit ein bereits typisierter Wert die Pruefung passiert.

    Returns:
        Den Kalendertag.

    Raises:
        ValueError: Wenn der Wert nicht acht Ziffern hat oder keinen existierenden
            Kalendertag bezeichnet. ``pydantic`` verpackt die Ausnahme in seine
            :class:`~pydantic.ValidationError`.
    """
    if not isinstance(wert, str):
        return wert
    if len(wert) != _DATUM_LAENGE or not wert.isdigit():
        raise ValueError("kein Datum im Format TTMMJJJJ")
    try:
        return dt.date(int(wert[4:8]), int(wert[2:4]), int(wert[0:2]))
    except ValueError as fehler:
        raise ValueError("kein existierender Kalendertag") from fehler


def _lies_wahrheit(wert: Any) -> Any:  # noqa: ANN401 - siehe :func:`_lies_datum`
    """Ueberfuehrt die Rohform ``J``/``N`` in einen Wahrheitswert.

    Bewusst **nur** diese beiden Kuerzel: ``pydantic`` wuerde im nachgiebigen
    Modus auch ``true``, ``yes`` und ``1`` annehmen. Das waere keine Grosszuegigkeit,
    sondern ein blinder Fleck — die Injektionsvarianten der Klasse F2 schreiben
    genau solche Fremdformen in ein Wahrheitsfeld.

    Args:
        wert: Rohwert aus ``df_raw``.

    Returns:
        Den Wahrheitswert.

    Raises:
        ValueError: Bei jeder anderen Zeichenkette.
    """
    if not isinstance(wert, str):
        return wert
    if wert == _ROH_JA:
        return True
    if wert == _ROH_NEIN:
        return False
    raise ValueError("kein Wahrheitswert (J/N)")


def _pruefe_laengenmenge(wert: str, info: ValidationInfo) -> str:
    """Prueft die Laenge gegen die Menge zulaessiger Laengen des Feldes.

    Args:
        wert: Bereits als Text validierter Wert.
        info: Kontext von ``pydantic``; liefert den Feldnamen.

    Returns:
        Den unveraenderten Wert.

    Raises:
        ValueError: Wenn die Laenge nicht in der Menge liegt.
    """
    erlaubt = LAENGENMENGE[str(info.field_name)]
    if len(wert) not in erlaubt:
        stellen = " oder ".join(str(zahl) for zahl in erlaubt)
        raise ValueError(f"Laenge {len(wert)} unzulaessig, erlaubt sind {stellen} Zeichen")
    return wert


# ---------------------------------------------------------------------------
# Aufbau der sieben Modelle
# ---------------------------------------------------------------------------


def _annotation(spalte: str) -> Any:  # noqa: ANN401 - eine Typannotation ist zur Laufzeit ein Wert
    """Baut die Feldannotation einer Spalte aus Feldtyp und Laengenangabe.

    Args:
        spalte: Spaltenname aus dem Schema.

    Returns:
        Den Grundtyp, bei Bedarf umhuellt von einem ``Annotated`` mit Vorschalter
        und Laengenbedingung.

    Raises:
        AuswertungsFehler: Wenn die Spalte nicht im Schema steht. Bewusst kein
            Ersatztyp — eine unbekannte Spalte waere ein stiller Messfehler.
    """
    feldtyp = FELDTYP_JE_SPALTE.get(spalte)
    if feldtyp is None:
        raise AuswertungsFehler(
            f"B0: Spalte {spalte!r} steht nicht im Schema aus src/common/serialisierung.py"
        )

    metadaten: list[Any] = []
    if feldtyp is Feldtyp.DATUM:
        metadaten.append(BeforeValidator(_lies_datum))
    elif feldtyp is Feldtyp.WAHRHEIT:
        metadaten.append(BeforeValidator(_lies_wahrheit))

    if spalte in EXAKTE_LAENGE:
        laenge = EXAKTE_LAENGE[spalte]
        metadaten.append(StringConstraints(min_length=laenge, max_length=laenge))
    elif spalte in MAX_LAENGE:
        metadaten.append(StringConstraints(max_length=MAX_LAENGE[spalte]))
    elif spalte in LAENGENMENGE:
        metadaten.append(AfterValidator(_pruefe_laengenmenge))

    grundtyp = _GRUNDTYP[feldtyp]
    if not metadaten:
        return grundtyp
    # Die Annotation entsteht zur Laufzeit; ``Annotated`` nimmt ihre Bestandteile
    # deshalb als Tupel entgegen statt als geschriebene Subskription.
    return Annotated[(grundtyp, *metadaten)]


def _baue_modell(entitaet: str) -> type[BaseModel]:
    """Erzeugt das ``pydantic``-Modell einer Entitaet.

    Args:
        entitaet: Name der Entitaet.

    Returns:
        Das Modell. Pflichtfelder haben keinen Vorgabewert, alle uebrigen den
        Vorgabewert ``None``.
    """
    pflicht = set(PFLICHTFELDER[entitaet])
    felder: dict[str, Any] = {}
    for spalte in SPALTEN_JE_ENTITAET[entitaet]:
        annotation = _annotation(spalte)
        felder[spalte] = (annotation, ...) if spalte in pflicht else (annotation | None, None)

    name = "B0" + "".join(teil.capitalize() for teil in entitaet.split("_"))
    return create_model(
        name,
        __config__=ConfigDict(strict=False, extra="forbid"),
        **felder,
    )


def _baue_modelle() -> Mapping[str, type[BaseModel]]:
    """Erzeugt die Modelle aller sieben Entitaeten in Schemareihenfolge.

    Returns:
        Die Abbildung Entitaetsname auf Modell.

    Raises:
        AuswertungsFehler: Wenn :data:`PFLICHTFELDER` eine Entitaet nicht kennt
            oder ein dort genanntes Feld nicht im Schema steht. Beides waere ein
            Tippfehler, der sonst als stillschweigend gelockerte Pruefung in die
            Kennzahlen einginge.
    """
    fehlend = [name for name in ENTITAETEN if name not in PFLICHTFELDER]
    if fehlend:
        raise AuswertungsFehler(f"B0: PFLICHTFELDER nennt die Entitaeten {fehlend} nicht")
    for entitaet, spalten in PFLICHTFELDER.items():
        unbekannt = [name for name in spalten if name not in SPALTEN_JE_ENTITAET[entitaet]]
        if unbekannt:
            raise AuswertungsFehler(
                f"B0: Pflichtfelder {unbekannt} gehoeren nicht zur Entitaet {entitaet!r}"
            )
    return MappingProxyType({name: _baue_modell(name) for name in ENTITAETEN})


#: Ein ``pydantic``-Modell je Entitaet, aufgebaut beim Import des Moduls.
#:
#: Der Aufbau kostet einmalig wenige Millisekunden; ihn je Lauf zu wiederholen
#: wuerde in Phase 6 mehrere tausend Mal anfallen, ohne etwas zu aendern.
MODELLE: Final[Mapping[str, type[BaseModel]]] = _baue_modelle()


# ---------------------------------------------------------------------------
# Hilfsfunktionen der Ausfuehrung
# ---------------------------------------------------------------------------


def _rohtexte(spalte: Iterable[Any]) -> list[str]:
    """Liest eine Rohspalte als Liste von Zeichenketten.

    Args:
        spalte: Werte einer Spalte der Rohschicht.

    Returns:
        Die Werte als Text; Fehlwerte werden zum Leerstring, der Darstellung
        eines leeren Wertes in ``df_raw``.
    """
    return [LEER_ROH if wert is None or pd.isna(wert) else str(wert) for wert in spalte]


def _row_id(text: str) -> int:
    """Liest eine ``row_id`` aus ihrer Rohform.

    Args:
        text: Rohwert der Spalte ``row_id``.

    Returns:
        Die Zeilenkennung, oder :data:`~src.evaluation.modell.ROW_ID_OHNE_BEZUG`,
        wenn der Wert keine ganze Zahl ist. Letzteres kann nur aus einer
        beschaedigten Datei stammen — ``row_id`` ist niemals Ziel einer Injektion
        (Architekturregel A3). Die Meldung bleibt dann sichtbar, wird aber keiner
        falschen Zeile zugeschlagen.
    """
    try:
        return int(text)
    except ValueError:
        return ROW_ID_OHNE_BEZUG


def _klartext(eintrag: ErrorDetails) -> str:
    """Gibt die deutsche Fassung einer Fehlerart zurueck.

    Args:
        eintrag: Einzelfehler aus :meth:`pydantic.ValidationError.errors`.

    Returns:
        Die hinterlegte Klartextfassung. Fuer Fehler aus den Vorschaltern
        (``value_error``) den dort formulierten Text, fuer alle uebrigen den Text
        von ``pydantic`` unveraendert — die Diagnoseguete der Baseline wird
        gemessen, nicht geschoent.
    """
    hinterlegt = _KLARTEXT.get(str(eintrag["type"]))
    if hinterlegt is not None:
        return hinterlegt
    return str(eintrag["msg"]).removeprefix("Value error, ")


def _zeilendaten(rahmen: pd.DataFrame, spalten: Sequence[str]) -> list[list[str]]:
    """Liest die Rohschicht spaltenweise ein, damit sie zeilenweise nutzbar ist.

    Args:
        rahmen: Datenrahmen der Rohschicht.
        spalten: Spalten in Schemareihenfolge.

    Returns:
        Je Spalte die Werteliste, in derselben Reihenfolge wie ``spalten``.
    """
    return [_rohtexte(rahmen[name]) for name in spalten]


# ---------------------------------------------------------------------------
# Das Verfahren
# ---------------------------------------------------------------------------


class B0Schema:
    """Baseline B0: Typ-, Nullable- und Laengenpruefung mit ``pydantic`` v2.

    Erfuellt das Protokoll :class:`~src.evaluation.modell.Verfahren`. Satzbezogene
    Befunde und Anomaliescores gibt es nicht: B0 kennt weder Beziehungen zwischen
    Zeilen noch einen kontinuierlichen Score, sondern faellt je Feld eine binaere
    Entscheidung. Die Zusatzprotokolle
    :class:`~src.evaluation.modell.MitSatzmeldungen` und
    :class:`~src.evaluation.modell.MitZellscore` werden deshalb bewusst **nicht**
    erfuellt — eine leere Implementierung saehe in der Auswertung aus wie "nichts
    gefunden", was etwas anderes ist als "kann es nicht".
    """

    name = "B0"
    beschreibung = (
        "Schemavalidierung mit pydantic v2: Typ, Nullable-Constraint und Feldlaenge, "
        "ohne Enums, Wertebereiche, Feldabhaengigkeiten, Pruefziffern und Muster"
    )
    lokalisiert_zellen = True
    in_inferenzstatistik = True

    def erkenne(self, kontext: Kontext) -> pd.DataFrame:
        """Validiert jede Zeile jeder Entitaet gegen ihr Schemamodell.

        Die Entitaeten werden in der Reihenfolge von
        :data:`~src.common.serialisierung.ENTITAETEN` durchlaufen, die Zeilen in
        Rahmenreihenfolge und die Einzelfehler in der Reihenfolge, in der
        ``pydantic`` sie meldet. Damit ist die Ausgabe bei gleicher Eingabe
        bitgleich reproduzierbar (Architekturregel A2).

        Args:
            kontext: Pruefkontext ueber beide Datenschichten. B0 verwendet
                ausschliesslich die **Rohschicht** — auf der typisierten Schicht
                waeren Typfehler per Konstruktion nicht darstellbar
                (``spec/01``, Abschnitt 6).

        Returns:
            Einen Datenrahmen mit den Spalten
            :data:`~src.evaluation.modell.VERSTOSS_SPALTEN`, eine Zeile je
            Einzelfehler.

        Raises:
            AuswertungsFehler: Wenn eine Entitaet in der Rohschicht fehlt oder
                ihre Spaltenmenge nicht zum Schema passt.
        """
        meldungen: list[tuple[str, int, str, str, str, str]] = []
        laufend: dict[str, int] = {}

        for entitaet in ENTITAETEN:
            rahmen = self._rohrahmen(kontext, entitaet)
            spalten = SPALTEN_JE_ENTITAET[entitaet]
            modell = MODELLE[entitaet]
            werte = _zeilendaten(rahmen, spalten)
            kennungen = _rohtexte(rahmen["row_id"])

            for position in range(len(rahmen)):
                zeile = {
                    name: spaltenwerte[position]
                    for name, spaltenwerte in zip(spalten, werte, strict=True)
                    if spaltenwerte[position] != LEER_ROH
                }
                try:
                    modell.model_validate(zeile)
                except ValidationError as fehler:
                    meldungen.extend(
                        self._als_meldungen(
                            entitaet, _row_id(kennungen[position]), zeile, fehler, laufend
                        )
                    )

        return pd.DataFrame(meldungen, columns=list(VERSTOSS_SPALTEN))

    @staticmethod
    def _rohrahmen(kontext: Kontext, entitaet: str) -> pd.DataFrame:
        """Holt den Rohrahmen einer Entitaet und prueft seine Spaltenmenge.

        Args:
            kontext: Pruefkontext.
            entitaet: Name der Entitaet.

        Returns:
            Den Datenrahmen der Rohschicht.

        Raises:
            AuswertungsFehler: Wenn die Entitaet fehlt oder ihre Spaltenmenge vom
                Schema abweicht. Bewusst kein leerer Ersatzrahmen: Ein fehlender
                Rahmen ergaebe null Meldungen und damit eine Kennzahl, die aussieht
                wie ein Messergebnis.
        """
        if entitaet not in kontext.raw:
            raise AuswertungsFehler(
                f"B0: Entitaet {entitaet!r} fehlt in der Rohschicht des Kontexts. "
                f"Vorhanden sind: {sorted(kontext.raw)}"
            )
        rahmen = kontext.raw[entitaet]
        erwartet = set(SPALTEN_JE_ENTITAET[entitaet])
        vorhanden = set(rahmen.columns)
        if vorhanden != erwartet:
            raise AuswertungsFehler(
                f"B0: Entitaet {entitaet!r} hat fehlende Spalten "
                f"{sorted(erwartet - vorhanden)} und ueberzaehlige "
                f"{sorted(vorhanden - erwartet)}"
            )
        return rahmen

    @staticmethod
    def _als_meldungen(
        entitaet: str,
        row_id: int,
        zeile: Mapping[str, str],
        fehler: ValidationError,
        laufend: dict[str, int],
    ) -> Iterator[tuple[str, int, str, str, str, str]]:
        """Wandelt eine :class:`~pydantic.ValidationError` in Berichtszeilen.

        Args:
            entitaet: Name der Entitaet.
            row_id: Zeilenkennung.
            zeile: Die validierten Rohwerte ohne die leeren Felder.
            fehler: Die Ausnahme von ``pydantic``.
            laufend: Zaehler je ``regel_id``; wird fortgeschrieben.

        Yields:
            Je Einzelfehler ein Tupel in der Reihenfolge von
            :data:`~src.evaluation.modell.VERSTOSS_SPALTEN`.

        Raises:
            AuswertungsFehler: Wenn ein Fehler keiner Spalte zugeordnet ist. Ein
                modellweiter Fehler waere in der Zellmetrik nicht verortbar; da
                die Modelle keine modellweiten Pruefungen haben, kann er nur aus
                einer Fehlkonfiguration stammen.
        """
        for eintrag in fehler.errors():
            ort = eintrag["loc"]
            if not ort:
                raise AuswertungsFehler(
                    f"B0: Fehler ohne Feldbezug in {entitaet} (row_id {row_id}): "
                    f"{eintrag['type']} — {eintrag['msg']}"
                )
            spalte = str(ort[0])
            regel_id = f"{_PRAEFIX}-{spalte}"
            laufend[regel_id] = laufend.get(regel_id, 0) + 1
            rohwert = zeile.get(spalte, LEER_ROH)
            yield (
                entitaet,
                row_id,
                spalte,
                regel_id,
                f"{regel_id}#{laufend[regel_id]:06d}",
                f"{spalte}: {_klartext(eintrag)} (Rohwert {rohwert!r})",
            )


if TYPE_CHECKING:  # pragma: no cover - belegt die Protokolltreue bei der Typpruefung
    _protokolltreue: Verfahren = B0Schema()
