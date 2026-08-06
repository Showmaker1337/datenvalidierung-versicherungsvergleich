"""Laden der Referenztabellen aus ``data/reference``.

Generator und Regel-Engine lesen dieselben Dateien (spec/01, Abschnitt 2). Die
Spaltentypen sind hier fest hinterlegt und werden **nicht** von pandas geraten:

* ``plz``, ``hsn``, ``tsn``, ``sf_klasse`` und ``vu_nummer`` sind Zeichenketten.
  Als Ganzzahl gelesen verloeren sie ihre fuehrende Null — genau der Fehler, den
  R-002, R-007 und R-013 aufdecken sollen.
* ``neupreis_eur`` wird als :class:`~decimal.Decimal` gefuehrt, niemals als
  ``float`` (CLAUDE.md, Abschnitt 5).

Fehlt eine Datei oder eine Spalte, wird eine aussagekraeftige Ausnahme geworfen.
Es gibt keinen stillen Fallback.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from functools import cache
from typing import TYPE_CHECKING, Final

import pandas as pd

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping
    from pathlib import Path

    from src.common.config import Config

__all__ = [
    "DEZIMALSPALTEN",
    "SPALTEN",
    "ReferenzFehler",
    "lade_alle",
    "lade_plz_ort",
    "lade_regionalklassen",
    "lade_sf_beitragssatz",
    "lade_tabelle",
    "lade_typklassen",
    "lade_vu_stammdaten",
    "lade_zuers_zonen",
    "leere_zwischenspeicher",
]


class ReferenzFehler(RuntimeError):
    """Eine Referenztabelle fehlt, ist unvollstaendig oder nicht lesbar."""


#: Erwartete Spalten je Tabelle mit ihrem pandas-Dtype.
#:
#: ``"string"`` erzwingt die Zeichenkettendarstellung. ``"object"`` steht fuer
#: Spalten, die nach dem Einlesen zu ``Decimal`` gewandelt werden.
SPALTEN: Final[Mapping[str, Mapping[str, str]]] = {
    "plz_ort": {
        "plz": "string",
        "ort": "string",
        "bundesland": "string",
        "zulassungsbezirk": "string",
    },
    "regionalklassen": {
        "zulassungsbezirk": "string",
        "regionalklasse_hp": "int64",
        "regionalklasse_tk": "int64",
        "regionalklasse_vk": "int64",
    },
    "typklassen": {
        "hsn": "string",
        "tsn": "string",
        "hersteller": "string",
        "modell": "string",
        "leistung_kw": "int64",
        "antriebsart": "string",
        "typklasse_hp": "int64",
        "typklasse_tk": "int64",
        "typklasse_vk": "int64",
        "neupreis_eur": "object",
    },
    "vu_stammdaten": {
        "vu_nummer": "string",
        "vu_name": "string",
        "marktanteil": "float64",
        "quell_schnittstelle": "string",
    },
    "zuers_zonen": {
        "plz": "string",
        "zuers_zone": "int64",
    },
    "sf_beitragssatz": {
        "sf_klasse": "string",
        "beitragssatz_prozent": "int64",
    },
}

#: Spalten, die als :class:`~decimal.Decimal` gefuehrt werden.
DEZIMALSPALTEN: Final[Mapping[str, tuple[str, ...]]] = {
    "typklassen": ("neupreis_eur",),
}


def _lies_csv(pfad: Path, tabelle: str) -> pd.DataFrame:
    """Liest eine Referenz-CSV mit fest vorgegebenen Spaltentypen."""
    spalten = SPALTEN[tabelle]
    # Dezimalspalten werden zunaechst als Zeichenkette gelesen. Ein Umweg ueber
    # float wuerde die exakte Darstellung zerstoeren, noch bevor Decimal greift.
    dtypen = {name: ("string" if typ == "object" else typ) for name, typ in spalten.items()}
    try:
        rahmen = pd.read_csv(
            pfad,
            dtype=dtypen,
            keep_default_na=False,
            na_values=[],
            encoding="utf-8",
        )
    except (OSError, ValueError) as fehler:
        raise ReferenzFehler(f"Referenztabelle {tabelle} ist nicht lesbar: {pfad}") from fehler

    fehlend = [name for name in spalten if name not in rahmen.columns]
    if fehlend:
        raise ReferenzFehler(
            f"Referenztabelle {tabelle} ({pfad}) fehlen die Spalten {fehlend}. "
            f"Erwartet werden: {list(spalten)}"
        )
    ueberzaehlig = [name for name in rahmen.columns if name not in spalten]
    if ueberzaehlig:
        raise ReferenzFehler(
            f"Referenztabelle {tabelle} ({pfad}) hat unerwartete Spalten: {ueberzaehlig}"
        )
    if rahmen.empty:
        raise ReferenzFehler(f"Referenztabelle {tabelle} ({pfad}) ist leer")

    for spalte in DEZIMALSPALTEN.get(tabelle, ()):
        try:
            werte = [Decimal(str(wert)) for wert in rahmen[spalte]]
            rahmen[spalte] = pd.Series(werte, index=rahmen.index, dtype=object)
        except (InvalidOperation, ValueError) as fehler:
            raise ReferenzFehler(
                f"Spalte {spalte} in {tabelle} ({pfad}) enthaelt keinen Dezimalwert"
            ) from fehler

    return rahmen[list(spalten)]


@cache
def _lade_zwischengespeichert(tabelle: str, verzeichnis: Path) -> pd.DataFrame:
    """Liest eine Tabelle einmalig ein und haelt sie im Zwischenspeicher."""
    if tabelle not in SPALTEN:
        raise ReferenzFehler(
            f"Unbekannte Referenztabelle: {tabelle!r}. Bekannt sind: {sorted(SPALTEN)}"
        )
    pfad = verzeichnis / f"{tabelle}.csv"
    if not pfad.is_file():
        raise ReferenzFehler(
            f"Referenztabelle {tabelle} fehlt: {pfad}. "
            "Die Referenzdaten werden einmalig mit 'python scripts/build_reference.py' erzeugt "
            "und danach versioniert."
        )
    return _lies_csv(pfad, tabelle)


def lade_tabelle(tabelle: str, config: Config) -> pd.DataFrame:
    """Laedt eine Referenztabelle.

    Args:
        tabelle: Name ohne Endung, zum Beispiel ``"plz_ort"``.
        config: Geladene Konfiguration; liefert das Referenzverzeichnis.

    Returns:
        Eine eigenstaendige Kopie des zwischengespeicherten Datenrahmens. Die
        Kopie verhindert, dass eine Aenderung an einer Stelle im Programm die
        Referenzdaten aller anderen Stellen veraendert.

    Raises:
        ReferenzFehler: Wenn die Tabelle unbekannt ist, die Datei fehlt, Spalten
            fehlen oder ueberzaehlig sind oder die Tabelle leer ist.
    """
    return _lade_zwischengespeichert(tabelle, config.pfade.reference.resolve()).copy()


def lade_plz_ort(config: Config) -> pd.DataFrame:
    """Laedt ``plz_ort.csv`` (PLZ, Ort, Bundesland, Zulassungsbezirk)."""
    return lade_tabelle("plz_ort", config)


def lade_regionalklassen(config: Config) -> pd.DataFrame:
    """Laedt ``regionalklassen.csv`` (Zulassungsbezirk auf Regionalklassen)."""
    return lade_tabelle("regionalklassen", config)


def lade_typklassen(config: Config) -> pd.DataFrame:
    """Laedt ``typklassen.csv`` (HSN/TSN auf Fahrzeugmerkmale und Typklassen)."""
    return lade_tabelle("typklassen", config)


def lade_vu_stammdaten(config: Config) -> pd.DataFrame:
    """Laedt ``vu_stammdaten.csv`` (Anbieter, Marktanteil, Quellschnittstelle)."""
    return lade_tabelle("vu_stammdaten", config)


def lade_zuers_zonen(config: Config) -> pd.DataFrame:
    """Laedt ``zuers_zonen.csv`` (PLZ auf ZUERS-Zone)."""
    return lade_tabelle("zuers_zonen", config)


def lade_sf_beitragssatz(config: Config) -> pd.DataFrame:
    """Laedt ``sf_beitragssatz.csv`` (SF-Klasse auf Beitragssatz)."""
    return lade_tabelle("sf_beitragssatz", config)


def lade_alle(config: Config) -> dict[str, pd.DataFrame]:
    """Laedt alle Referenztabellen.

    Args:
        config: Geladene Konfiguration.

    Returns:
        Eine nach Tabellennamen sortierte Abbildung Name auf Datenrahmen.

    Raises:
        ReferenzFehler: Sobald eine Tabelle fehlt oder unbrauchbar ist.
    """
    return {name: lade_tabelle(name, config) for name in sorted(SPALTEN)}


def leere_zwischenspeicher() -> None:
    """Verwirft den Zwischenspeicher.

    Wird in Tests gebraucht, die Referenzdateien in wechselnde temporaere
    Verzeichnisse schreiben.
    """
    _lade_zwischengespeichert.cache_clear()
