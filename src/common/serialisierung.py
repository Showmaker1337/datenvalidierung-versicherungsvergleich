"""Serialisierung zwischen typisierter Innenansicht und Rohschicht.

``spec/01_datenmodell.md``, Abschnitt 6, fuehrt zwei Datenschichten ein:

* ``df_typed`` — geparst und typisiert (``date``, ``Decimal``, ``int``, ``bool``).
  Hier laufen die fachlichen Pruefungen.
* ``df_raw`` — **alle** Spalten als Zeichenkette. Bildet ab, was aus einer
  Schnittstelle ankommt; nur hier sind Format-, Typ- und Sentinel-Fehler
  ueberhaupt darstellbar.

Dieses Modul ist die einzige Stelle, an der zwischen beiden Schichten gewandelt
wird. Es liegt in ``src/common``, weil Generator, Injektor und Regel-Engine
dieselbe Abbildung brauchen (Architekturregel A1).

Der Parser wirft keine Ausnahme
-------------------------------

Ein nicht parsebarer Wert wird zu ``pd.NA`` und die Stelle wird in
``parse_fehler`` protokolliert. Genau solche Werte untersucht diese Arbeit; ein
``raise`` wuerde den Experimentlauf abbrechen, statt einen Befund zu liefern
(spec/01, Abschnitt 6: "Parsefehler = Befund, kein Absturz").

Leere Werte in der Rohschicht
-----------------------------

Ein leerer Wert wird zum **leeren String** — fuer alle Typen, auch fuer
Datumsfelder (``spec/01``, Abschnitt 6, Zeile "leer"). Das ist keine Formalie: Der
saubere Datensatz enthaelt planmaessig leere Datumsfelder — ``geburtsdatum`` bei
``anrede`` = FIRMA, ``fuehrerschein_datum`` ausserhalb der Kfz-Sparten. Mit
``00000000`` wuerde R-009 ("jedes Datumsfeld der Rohschicht ist ein existierender
Kalendertag") auf dem sauberen Datensatz ausloesen, denn ``00000000`` ist kein
Kalendertag. Der Clean-Baseline-Lauf haette dann Fehlalarme, die keine sind.

Umgekehrt bleibt ``00000000`` in der Rohschicht ein **Befund**: Der Parser gibt
dafuer ``pd.NA`` zurueck *und* protokolliert die Stelle. Ein solcher Wert kann
nur aus einer Injektion stammen, und R-009 soll ihn melden.

Der Preis dieser Festlegung: Auf der Rohschicht ist ein eingeschleuster Leerstring
nicht von einem planmaessig leeren Feld zu unterscheiden. Die Injektionsvariante
F1-b ist deshalb nur ueber die Pflichtfeldregeln R-001 und R-057 erkennbar, nicht
ueber die Sentinel-Regel R-025 (CLAUDE.md, Abschnitt 5;
``spec/03_fehlerklassen.md``, Variante F1-b). Das ist ein Informationsverlust der
Serialisierung, kein Implementierungsmangel — und gehoert in die Diskussion der
Arbeit.

Die Entscheidung selbst ist in ``docs/verteilungsquellen.md``, Abschnitt 4.8
vermerkt.
"""

from __future__ import annotations

import datetime as dt
import re
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

import numpy as np
import pandas as pd

from src.common.geld import als_string, aus_string

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Callable, Iterable, Mapping, Sequence
    from decimal import Decimal

__all__ = [
    "ENTITAETEN",
    "FELDTYP_JE_SPALTE",
    "LEER_ROH",
    "PARSEFEHLER_SPALTEN",
    "SPALTEN_JE_ENTITAET",
    "Feldtyp",
    "SerialisierungsFehler",
    "bestimme_entitaet",
    "leere_zellen",
    "parse",
    "serialisiere",
    "typisierter_rahmen",
]


class SerialisierungsFehler(ValueError):
    """Ein Datenrahmen passt nicht zum hinterlegten Schema."""


class Feldtyp(StrEnum):
    """Typ eines Feldes in der typisierten Schicht ``df_typed``."""

    TEXT = "TEXT"
    """Zeichenkette. Umfasst auch PLZ, HSN, TSN und SF-Klasse — sie sind niemals Ganzzahlen."""

    GANZZAHL = "GANZZAHL"
    """Ganze Zahl ohne fuehrende Nullen."""

    DEZIMAL = "DEZIMAL"
    """Geldbetrag oder Prozentsatz als :class:`~decimal.Decimal`, niemals ``float``."""

    DATUM = "DATUM"
    """Kalendertag als :class:`datetime.date`; Rohform ``TTMMJJJJ``."""

    ZEITPUNKT = "ZEITPUNKT"
    """Zeitpunkt als :class:`datetime.datetime`; Rohform ISO 8601."""

    WAHRHEIT = "WAHRHEIT"
    """Wahrheitswert; Rohform ``J`` beziehungsweise ``N``."""


#: Darstellung eines leeren Wertes in der Rohschicht (siehe Modul-Docstring).
LEER_ROH: Final[str] = ""

#: Wahrheitswerte in der Rohschicht (spec/01, Abschnitt 6).
_ROH_JA: Final[str] = "J"
_ROH_NEIN: Final[str] = "N"

#: Laenge des GDV-Datumsformats ``TTMMJJJJ``.
_DATUM_LAENGE: Final[int] = 8

#: Rohform einer ganzen Zahl: optionales Vorzeichen, danach nur Ziffern.
_MUSTER_GANZZAHL: Final[re.Pattern[str]] = re.compile(r"^-?\d+$")

#: pandas-Dtype je Feldtyp. ``object`` haelt ``Decimal`` und ``datetime.date``
#: verlustfrei; beide ueberstehen den Weg durch Parquet unveraendert.
_DTYPE_JE_FELDTYP: Final[Mapping[Feldtyp, str]] = MappingProxyType(
    {
        Feldtyp.TEXT: "string",
        Feldtyp.GANZZAHL: "Int64",
        Feldtyp.DEZIMAL: "object",
        Feldtyp.DATUM: "object",
        Feldtyp.ZEITPUNKT: "datetime64[us]",
        Feldtyp.WAHRHEIT: "boolean",
    }
)

_T: Final = Feldtyp.TEXT
_G: Final = Feldtyp.GANZZAHL
_D: Final = Feldtyp.DEZIMAL
_TAG: Final = Feldtyp.DATUM
_ZP: Final = Feldtyp.ZEITPUNKT
_W: Final = Feldtyp.WAHRHEIT

#: Spalten je Entitaet in fester Reihenfolge (spec/01, Abschnitt 3).
#:
#: ``row_id`` steht ueberall an erster Stelle. Die Reihenfolge ist Teil der
#: Reproduzierbarkeit: Sie geht in den Hashwert eines Datenrahmens ein.
_SCHEMA: Final[tuple[tuple[str, tuple[tuple[str, Feldtyp], ...]], ...]] = (
    (
        "anfrage",
        (
            ("row_id", _G),
            ("anfrage_id", _T),
            ("eingangszeitpunkt", _ZP),
            ("kanal", _T),
            ("sparte", _T),
            ("vn_person_id", _T),
            ("versicherungsbeginn", _TAG),
            ("vorvertrag_vorhanden", _W),
            ("vorversicherer_vu_nr", _T),
            ("zahlweise", _G),
            ("waehrung", _T),
            ("anfrage_status", _T),
        ),
    ),
    (
        "person",
        (
            ("row_id", _G),
            ("person_id", _T),
            ("anfrage_id", _T),
            ("rolle", _T),
            ("anrede", _T),
            ("nachname", _T),
            ("vorname", _T),
            ("geburtsdatum", _TAG),
            ("plz", _T),
            ("ort", _T),
            ("strasse", _T),
            ("hausnummer", _T),
            ("email", _T),
            ("familienstand", _T),
            ("wohneigentum", _W),
            ("fuehrerschein_datum", _TAG),
        ),
    ),
    (
        "risiko_kfz",
        (
            ("row_id", _G),
            ("risiko_id", _T),
            ("anfrage_id", _T),
            ("hsn", _T),
            ("tsn", _T),
            ("wagniskennziffer", _T),
            ("erstzulassung", _TAG),
            ("zulassung_auf_vn", _TAG),
            ("leistung_kw", _G),
            ("antriebsart", _T),
            ("neupreis_eur", _D),
            ("fahrzeugwert_aktuell", _D),
            ("art_kennzeichen", _T),
            ("zulassungsbezirk", _T),
            ("jahresfahrleistung_km", _G),
            ("nutzungsart", _T),
            ("eigentumsverhaeltnis", _T),
            ("nutzerkreis", _T),
            ("alter_juengster_fahrer", _G),
            ("abstellplatz", _T),
            ("sf_klasse_hp", _T),
            ("sf_klasse_vk", _T),
            ("schaeden_letzte_5j", _G),
            ("typklasse_hp", _G),
            ("typklasse_tk", _G),
            ("typklasse_vk", _G),
            ("regionalklasse_hp", _G),
            ("regionalklasse_tk", _G),
            ("regionalklasse_vk", _G),
        ),
    ),
    (
        "risiko_hausrat",
        (
            ("row_id", _G),
            ("risiko_id", _T),
            ("anfrage_id", _T),
            ("wohnflaeche_qm", _G),
            ("versicherungssumme_eur", _D),
            ("unterversicherungsverzicht", _W),
            ("bauartklasse", _T),
            ("baujahr", _G),
            ("gebaeudeart", _T),
            ("stockwerk", _G),
            ("zuers_zone", _G),
            ("elementar_eingeschlossen", _W),
            ("sublimit_fahrrad_eur", _D),
            ("sublimit_wertsachen_eur", _D),
        ),
    ),
    (
        "tarif",
        (
            ("row_id", _G),
            ("tarif_id", _T),
            ("vu_nummer", _T),
            ("produktname", _T),
            ("sparte", _T),
            ("tarifgeneration", _T),
            ("gueltig_ab", _TAG),
            ("gueltig_bis", _TAG),
            ("deckungsart", _G),
            ("deckungssumme_personen_eur", _D),
            ("deckungssumme_sach_eur", _D),
            ("deckungssumme_vermoegen_eur", _D),
            ("werkstattbindung", _W),
        ),
    ),
    (
        "angebot",
        (
            ("row_id", _G),
            ("angebot_id", _T),
            ("anfrage_id", _T),
            ("tarif_id", _T),
            ("rang", _G),
            ("nettobeitrag_jahr_eur", _D),
            ("versicherungsteuer_satz", _D),
            ("versicherungsteuer_eur", _D),
            ("bruttobeitrag_jahr_eur", _D),
            ("ratenzahlungszuschlag_prozent", _D),
            ("zahlbeitrag_rate_eur", _D),
            ("sb_tk_eur", _D),
            ("sb_vk_eur", _D),
            ("sb_hausrat_prozent", _D),
            ("sb_hausrat_eur", _D),
            ("annahmeentscheidung", _T),
            ("berechnungszeitpunkt", _ZP),
            ("quell_schnittstelle", _T),
        ),
    ),
    (
        "zahlung",
        (
            ("row_id", _G),
            ("zahlung_id", _T),
            ("anfrage_id", _T),
            ("iban", _T),
            ("bic", _T),
            ("sepa_mandat_datum", _TAG),
            ("kontoinhaber", _T),
        ),
    ),
)

#: Namen der sieben Entitaeten in fester Reihenfolge.
ENTITAETEN: Final[tuple[str, ...]] = tuple(name for name, _ in _SCHEMA)

#: Spalten je Entitaet in fester Reihenfolge.
SPALTEN_JE_ENTITAET: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {name: tuple(spalte for spalte, _ in felder) for name, felder in _SCHEMA}
)


def _feldtypen_je_spalte() -> Mapping[str, Feldtyp]:
    """Baut die Abbildung Spaltenname auf Feldtyp und prueft sie auf Widersprueche.

    Einige Spaltennamen kommen in mehreren Entitaeten vor (``row_id``,
    ``anfrage_id``, ``sparte``, ``risiko_id``). Sie muessen ueberall denselben Typ
    haben, sonst waere eine Abbildung ohne Entitaetsangabe nicht moeglich.
    """
    typen: dict[str, Feldtyp] = {}
    for entitaet, felder in _SCHEMA:
        for spalte, feldtyp in felder:
            bekannt = typen.setdefault(spalte, feldtyp)
            if bekannt is not feldtyp:
                raise SerialisierungsFehler(
                    f"Spalte {spalte!r} hat in {entitaet} den Typ {feldtyp} "
                    f"und anderswo {bekannt}"
                )
    return MappingProxyType(typen)


#: Feldtyp je Spaltenname, entitaetsuebergreifend eindeutig.
FELDTYP_JE_SPALTE: Final[Mapping[str, Feldtyp]] = _feldtypen_je_spalte()

#: Spalten des Parsefehler-Protokolls.
PARSEFEHLER_SPALTEN: Final[tuple[str, ...]] = (
    "entitaet",
    "zeile",
    "row_id",
    "spalte",
    "wert_roh",
    "grund",
)


# ---------------------------------------------------------------------------
# Schema-Hilfsfunktionen
# ---------------------------------------------------------------------------


def bestimme_entitaet(rahmen: pd.DataFrame) -> str:
    """Bestimmt die Entitaet eines Datenrahmens anhand seiner Spaltenmenge.

    Args:
        rahmen: Typisierter oder roher Datenrahmen.

    Returns:
        Den Namen der Entitaet.

    Raises:
        SerialisierungsFehler: Wenn die Spaltenmenge zu keiner Entitaet passt.
            Bewusst kein Ersatzwert — ein unbekanntes Schema soll auffallen.
    """
    vorhanden = set(rahmen.columns)
    for name, spalten in SPALTEN_JE_ENTITAET.items():
        if vorhanden == set(spalten):
            return name
    raise SerialisierungsFehler(
        f"Spaltenmenge passt zu keiner Entitaet: {sorted(vorhanden)}. "
        f"Bekannt sind: {list(ENTITAETEN)}"
    )


def _feldtyp(spalte: str) -> Feldtyp:
    """Gibt den Feldtyp einer Spalte zurueck."""
    feldtyp = FELDTYP_JE_SPALTE.get(spalte)
    if feldtyp is None:
        raise SerialisierungsFehler(
            f"Unbekannte Spalte: {spalte!r}. Das Schema steht in spec/01_datenmodell.md, "
            "Abschnitt 3, und in diesem Modul."
        )
    return feldtyp


def typisierter_rahmen(daten: Mapping[str, Sequence[Any]], entitaet: str) -> pd.DataFrame:
    """Baut einen typisierten Datenrahmen mit den Dtypes des Schemas.

    Die Generatormodule liefern reine Python-Listen; erst hier bekommen sie die
    fuer den Parquet- und Roundtrip-Weg noetigen Dtypes. Leere Werte sind
    ``None``: In den Objektspalten ist ``None`` das, was aus Parquet
    zurueckkommt, und ``pd.NA`` waere davon verschieden.

    Args:
        daten: Abbildung Spaltenname auf Werteliste.
        entitaet: Name der Entitaet; bestimmt Spaltenmenge und Reihenfolge.

    Returns:
        Den Datenrahmen mit den Spalten in Schemareihenfolge.

    Raises:
        SerialisierungsFehler: Bei unbekannter Entitaet, fehlenden oder
            ueberzaehligen Spalten.
    """
    spalten = SPALTEN_JE_ENTITAET.get(entitaet)
    if spalten is None:
        raise SerialisierungsFehler(
            f"Unbekannte Entitaet: {entitaet!r}. Bekannt sind: {list(ENTITAETEN)}"
        )
    fehlend = [name for name in spalten if name not in daten]
    ueberzaehlig = [name for name in daten if name not in spalten]
    if fehlend or ueberzaehlig:
        raise SerialisierungsFehler(
            f"Entitaet {entitaet}: fehlende Spalten {fehlend}, ueberzaehlige {ueberzaehlig}"
        )
    return pd.DataFrame(
        {name: _typisierte_werte(list(daten[name]), _feldtyp(name)) for name in spalten}
    )


def _objektfeld(werte: list[Any]) -> np.ndarray:
    """Baut ein eindimensionales Objektfeld, ohne dass numpy die Werte auslegt."""
    feld = np.empty(len(werte), dtype=object)
    feld[:] = werte
    return feld


def _zeitpunktfeld(werte: list[Any]) -> np.ndarray:
    """Baut ein ``datetime64[us]``-Feld; leere Werte werden zu ``NaT``.

    Bewusst ohne ``pd.to_datetime``: Die Umwandlung soll nicht von der
    Typerkennung von pandas abhaengen, sondern fest definiert sein.
    """
    leer = np.datetime64("NaT", "us")
    return np.array(
        [
            leer
            if wert is None or pd.isna(wert)
            else np.datetime64(dt.datetime.fromisoformat(str(wert)), "us")
            for wert in werte
        ],
        dtype="datetime64[us]",
    )


def _typisierte_werte(werte: list[Any], feldtyp: Feldtyp) -> Any:  # noqa: ANN401
    """Wandelt eine Werteliste in ein indexfreies Feld mit dem Dtype des Feldtyps.

    Indexfrei ist wesentlich: Ein ``pd.DataFrame`` aus mehreren ``Series`` richtet
    diese am Index aus. Felder ohne Index werden dagegen der Reihe nach uebernommen.
    """
    if feldtyp is Feldtyp.ZEITPUNKT:
        return _zeitpunktfeld(werte)
    if _DTYPE_JE_FELDTYP[feldtyp] == "object":
        return _objektfeld(werte)
    # Der Dtype steht erst zur Laufzeit fest; die Ueberladungen der pandas-Stubs
    # verlangen ein Literal.
    return pd.array(werte, dtype=_DTYPE_JE_FELDTYP[feldtyp])  # type: ignore[call-overload]


def leere_zellen(rahmen: pd.DataFrame, masken: Mapping[str, Sequence[bool]]) -> pd.DataFrame:
    """Setzt ausgewaehlte Zellen auf leer, ohne den Dtype der Spalte zu verlieren.

    ``Series.mask`` waere hier falsch: In einer Objektspalte setzt es ``NaN`` statt
    ``None``, und die beiden sind fuer den Vergleich zweier Datenrahmen
    verschieden. Diese Funktion baut die Spalte deshalb ueber dieselbe
    Typisierung neu auf, die auch :func:`typisierter_rahmen` verwendet.

    Args:
        rahmen: Datenrahmen der typisierten Schicht.
        masken: Je Spalte eine Folge von Wahrheitswerten; ``True`` leert die Zelle.

    Returns:
        Eine Kopie mit den geleerten Zellen.

    Raises:
        SerialisierungsFehler: Bei einer Spalte ausserhalb des Schemas.
    """
    ergebnis = rahmen.copy()
    for spalte, maske in masken.items():
        feldtyp = _feldtyp(spalte)
        werte = [
            None if treffer else wert
            for treffer, wert in zip(maske, rahmen[spalte], strict=True)
        ]
        ergebnis[spalte] = _typisierte_werte(werte, feldtyp)
    return ergebnis


# ---------------------------------------------------------------------------
# Serialisierung df_typed -> df_raw
# ---------------------------------------------------------------------------


def _roh_text(wert: Any) -> str:  # noqa: ANN401
    """Serialisiert eine Zeichenkette."""
    return str(wert)


def _roh_ganzzahl(wert: Any) -> str:  # noqa: ANN401
    """Serialisiert eine ganze Zahl ohne fuehrende Nullen."""
    return str(int(wert))


def _roh_datum(wert: Any) -> str:  # noqa: ANN401
    """Serialisiert ein Datum im GDV-Format ``TTMMJJJJ``."""
    tag = dt.date.fromisoformat(str(wert)[:10])
    return f"{tag.day:02d}{tag.month:02d}{tag.year:04d}"


def _roh_zeitpunkt(wert: Any) -> str:  # noqa: ANN401
    """Serialisiert einen Zeitpunkt nach ISO 8601, sekundengenau."""
    return pd.Timestamp(wert).to_pydatetime().isoformat(sep="T", timespec="seconds")


def _roh_wahrheit(wert: Any) -> str:  # noqa: ANN401
    """Serialisiert einen Wahrheitswert als ``J`` beziehungsweise ``N``."""
    return _ROH_JA if bool(wert) else _ROH_NEIN


#: Serialisierungsfunktion je Feldtyp.
_ROHFORM: Final[Mapping[Feldtyp, Callable[[Any], str]]] = MappingProxyType(
    {
        Feldtyp.TEXT: _roh_text,
        Feldtyp.GANZZAHL: _roh_ganzzahl,
        Feldtyp.DEZIMAL: als_string,
        Feldtyp.DATUM: _roh_datum,
        Feldtyp.ZEITPUNKT: _roh_zeitpunkt,
        Feldtyp.WAHRHEIT: _roh_wahrheit,
    }
)


def _roh_wert(wert: Any, feldtyp: Feldtyp) -> str:  # noqa: ANN401
    """Serialisiert einen Einzelwert fuer die Rohschicht."""
    if wert is None or pd.isna(wert):
        return LEER_ROH
    return _ROHFORM[feldtyp](wert)


def serialisiere(df_typed: pd.DataFrame) -> pd.DataFrame:
    """Wandelt die typisierte Schicht in die Rohschicht.

    Serialisierungsregeln nach ``spec/01_datenmodell.md``, Abschnitt 6:
    ``date`` als ``TTMMJJJJ``, ``datetime`` als ISO 8601, ``Decimal`` mit
    Dezimalpunkt und zwei Nachkommastellen, ``bool`` als ``J``/``N``, leere Werte
    als leerer String (siehe Modul-Docstring).

    Args:
        df_typed: Typisierter Datenrahmen einer Entitaet.

    Returns:
        Einen Datenrahmen mit denselben Spalten in derselben Reihenfolge,
        **alle** als ``string``.

    Raises:
        SerialisierungsFehler: Bei einer Spalte ausserhalb des Schemas.
    """
    spalten = {
        name: pd.array(
            [_roh_wert(wert, _feldtyp(name)) for wert in df_typed[name]],
            dtype="string",
        )
        for name in df_typed.columns
    }
    return pd.DataFrame(spalten, index=df_typed.index.copy())


# ---------------------------------------------------------------------------
# Parsen df_raw -> df_typed
# ---------------------------------------------------------------------------


def _parse_ganzzahl(text: str) -> tuple[int | None, str | None]:
    """Parst eine ganze Zahl aus der Rohschicht."""
    if not _MUSTER_GANZZAHL.match(text):
        return None, "keine ganze Zahl"
    return int(text), None


def _parse_dezimal(text: str) -> tuple[Decimal | None, str | None]:
    """Parst einen Dezimalwert aus der Rohschicht."""
    wert = aus_string(text)
    if wert is None:
        return None, "kein Betrag im Format 0.00"
    return wert, None


def _parse_datum(text: str) -> tuple[dt.date | None, str | None]:
    """Parst ein Datum im GDV-Format ``TTMMJJJJ``."""
    if len(text) != _DATUM_LAENGE or not text.isdigit():
        return None, "kein Datum im Format TTMMJJJJ"
    try:
        return dt.date(int(text[4:8]), int(text[2:4]), int(text[0:2])), None
    except ValueError:
        return None, "kein existierender Kalendertag"


def _parse_zeitpunkt(text: str) -> tuple[dt.datetime | None, str | None]:
    """Parst einen Zeitpunkt im ISO-8601-Format."""
    try:
        return dt.datetime.fromisoformat(text), None
    except ValueError:
        return None, "kein Zeitpunkt nach ISO 8601"


def _parse_wahrheit(text: str) -> tuple[bool | None, str | None]:
    """Parst einen Wahrheitswert (``J``/``N``)."""
    if text == _ROH_JA:
        return True, None
    if text == _ROH_NEIN:
        return False, None
    return None, "kein Wahrheitswert (J/N)"


def _parse_text(text: str) -> tuple[str, str | None]:
    """Uebernimmt eine Zeichenkette unveraendert."""
    return text, None


#: Parsefunktion je Feldtyp.
_PARSEFORM: Final[Mapping[Feldtyp, Callable[[str], tuple[Any, str | None]]]] = MappingProxyType(
    {
        Feldtyp.TEXT: _parse_text,
        Feldtyp.GANZZAHL: _parse_ganzzahl,
        Feldtyp.DEZIMAL: _parse_dezimal,
        Feldtyp.DATUM: _parse_datum,
        Feldtyp.ZEITPUNKT: _parse_zeitpunkt,
        Feldtyp.WAHRHEIT: _parse_wahrheit,
    }
)


def _parse_wert(text: str, feldtyp: Feldtyp) -> tuple[Any, str | None]:
    """Parst einen Einzelwert; gibt ``(Wert, Grund)`` zurueck, Grund ``None`` bei Erfolg."""
    if text == LEER_ROH:
        return None, None
    return _PARSEFORM[feldtyp](text)


def _rohtexte(spalte: Iterable[Any]) -> list[str]:
    """Liest eine Rohspalte als Liste von Zeichenketten; Fehlwerte werden zum leeren String."""
    return [LEER_ROH if wert is None or pd.isna(wert) else str(wert) for wert in spalte]


def parse(df_raw: pd.DataFrame, entitaet: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Wandelt die Rohschicht in die typisierte Schicht.

    **Der Parser wirft keine Ausnahme.** Ein nicht parsebarer Wert wird zu
    ``pd.NA`` beziehungsweise ``None`` und die Stelle wird protokolliert.

    Args:
        df_raw: Roher Datenrahmen einer Entitaet, alle Spalten als Zeichenkette.
        entitaet: Name der Entitaet. Ohne Angabe wird sie aus der Spaltenmenge
            bestimmt.

    Returns:
        Ein Paar aus typisiertem Datenrahmen und Protokoll der Parsefehler. Das
        Protokoll hat die Spalten :data:`PARSEFEHLER_SPALTEN` und ist leer, wenn
        jeder Wert parsebar war.

    Raises:
        SerialisierungsFehler: Wenn die Entitaet unbekannt ist oder eine Spalte
            nicht im Schema steht. Das ist ein Programmierfehler, kein Datenbefund.
    """
    name = entitaet if entitaet is not None else bestimme_entitaet(df_raw)
    if name not in SPALTEN_JE_ENTITAET:
        raise SerialisierungsFehler(
            f"Unbekannte Entitaet: {name!r}. Bekannt sind: {list(ENTITAETEN)}"
        )

    row_ids = _rohtexte(df_raw["row_id"]) if "row_id" in df_raw.columns else None
    spalten: dict[str, Any] = {}
    protokoll: list[tuple[str, int, str, str, str, str]] = []

    for spaltenname in df_raw.columns:
        feldtyp = _feldtyp(spaltenname)
        werte: list[Any] = []
        for zeile, text in enumerate(_rohtexte(df_raw[spaltenname])):
            wert, grund = _parse_wert(text, feldtyp)
            werte.append(wert)
            if grund is not None:
                kennung = row_ids[zeile] if row_ids is not None else LEER_ROH
                protokoll.append((name, zeile, kennung, spaltenname, text, grund))
        spalten[spaltenname] = _typisierte_werte(werte, feldtyp)

    df_typed = pd.DataFrame(spalten, index=df_raw.index.copy())
    parse_fehler = pd.DataFrame(protokoll, columns=list(PARSEFEHLER_SPALTEN))
    return df_typed, parse_fehler
