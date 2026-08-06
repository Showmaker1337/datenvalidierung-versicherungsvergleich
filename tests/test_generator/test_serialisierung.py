"""Prueft den Weg zwischen typisierter Schicht und Rohschicht.

Kernaussage: ``parse(serialisiere(x)) == x`` fuer **alle** Entitaeten, alle
Datentypen und ausdruecklich auch fuer leere Werte. Ohne diese Eigenschaft waere
nach der Injektion nicht mehr unterscheidbar, ob ein Unterschied aus der
Verfaelschung stammt oder aus dem Umweg ueber die Rohschicht.

Zusaetzlich wird geprueft, dass der Parser **keine Ausnahme wirft**: Ein nicht
parsebarer Wert wird zu ``pd.NA`` und die Stelle wird protokolliert. Ein ``raise``
wuerde spaeter den gesamten Experimentlauf abbrechen, statt einen Befund zu
liefern.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pandas as pd
import pytest

from src.common.serialisierung import (
    ENTITAETEN,
    FELDTYP_JE_SPALTE,
    LEER_ROH,
    PARSEFEHLER_SPALTEN,
    SPALTEN_JE_ENTITAET,
    Feldtyp,
    SerialisierungsFehler,
    bestimme_entitaet,
    parse,
    serialisiere,
    typisierter_rahmen,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from src.common.config import Config


@pytest.mark.parametrize("entitaet", ENTITAETEN)
def test_roundtrip_auf_dem_erzeugten_datensatz(
    datensatz: dict[str, pd.DataFrame], entitaet: str
) -> None:
    """Der Roundtrip fuehrt jede Entitaet unveraendert zurueck."""
    original = datensatz[entitaet]
    roh = serialisiere(original)
    zurueck, parse_fehler = parse(roh)
    assert list(parse_fehler.columns) == list(PARSEFEHLER_SPALTEN)
    assert parse_fehler.empty, parse_fehler.head().to_dict("records")
    assert zurueck.equals(original), _erste_abweichung(original, zurueck)


def _erste_abweichung(erwartet: pd.DataFrame, gemessen: pd.DataFrame) -> str:
    """Beschreibt die erste abweichende Spalte, damit ein Fehlschlag lesbar ist."""
    for spalte in erwartet.columns:
        if not erwartet[spalte].equals(gemessen[spalte]):
            return (
                f"Spalte {spalte}: {erwartet[spalte].head(3).tolist()} "
                f"statt {gemessen[spalte].head(3).tolist()} "
                f"(dtype {erwartet[spalte].dtype} gegen {gemessen[spalte].dtype})"
            )
    return "keine Abweichung gefunden"


@pytest.mark.parametrize("entitaet", ENTITAETEN)
def test_rohschicht_fuehrt_alle_spalten_als_zeichenkette(
    datensatz: dict[str, pd.DataFrame], entitaet: str
) -> None:
    """In ``df_raw`` ist jede Spalte eine Zeichenkette und keine Zelle fehlend."""
    roh = serialisiere(datensatz[entitaet])
    assert list(roh.columns) == list(SPALTEN_JE_ENTITAET[entitaet])
    for spalte in roh.columns:
        assert roh[spalte].dtype == "string", f"{spalte} ist nicht als Zeichenkette gefuehrt"
        assert roh[spalte].notna().all(), f"{spalte} enthaelt einen Fehlwert statt Leerstring"


def test_leere_werte_werden_zum_leerstring(datensatz: dict[str, pd.DataFrame]) -> None:
    """Ein leerer Wert der typisierten Schicht wird in der Rohschicht zum Leerstring."""
    personen = datensatz["person"]
    roh = serialisiere(personen)
    leer = personen["fuehrerschein_datum"].isna()
    assert leer.any(), "Der Datensatz enthaelt keinen leeren Fuehrerscheintag"
    assert (roh.loc[leer, "fuehrerschein_datum"] == LEER_ROH).all()
    assert (roh.loc[~leer, "fuehrerschein_datum"] != LEER_ROH).all()


def test_datum_wird_im_gdv_format_geschrieben(datensatz: dict[str, pd.DataFrame]) -> None:
    """Ein Datum erscheint in der Rohschicht als ``TTMMJJJJ``."""
    roh = serialisiere(datensatz["risiko_kfz"])
    werte = [wert for wert in roh["erstzulassung"] if wert != LEER_ROH]
    assert werte
    assert all(len(wert) == 8 and wert.isdigit() for wert in werte)


@pytest.mark.parametrize("entitaet", ENTITAETEN)
def test_roundtrip_auf_leerem_rahmen(entitaet: str) -> None:
    """Auch ein Datenrahmen ohne Zeilen ueberlebt den Roundtrip mit seinen Dtypes."""
    leer = typisierter_rahmen({name: [] for name in SPALTEN_JE_ENTITAET[entitaet]}, entitaet)
    zurueck, parse_fehler = parse(serialisiere(leer))
    assert zurueck.equals(leer)
    assert parse_fehler.empty


@pytest.mark.parametrize("entitaet", ENTITAETEN)
def test_roundtrip_bei_durchgaengig_leeren_feldern(entitaet: str) -> None:
    """Eine Zeile, in der alles leer ist, kommt unveraendert zurueck."""
    leerzeile = {name: [None] for name in SPALTEN_JE_ENTITAET[entitaet]}
    original = typisierter_rahmen(leerzeile, entitaet)
    roh = serialisiere(original)
    assert set(roh.iloc[0]) == {LEER_ROH}
    zurueck, parse_fehler = parse(roh)
    assert zurueck.equals(original)
    assert parse_fehler.empty


def test_roundtrip_mit_randwerten_je_datentyp() -> None:
    """Schaltjahrestag, negative Zahl, hoher Betrag und Mitternacht ueberleben den Weg."""
    daten: dict[str, list[Any]] = {
        "row_id": [1, 2],
        "risiko_id": ["a", "b"],
        "anfrage_id": ["x", "y"],
        "wohnflaeche_qm": [20, 350],
        "versicherungssumme_eur": [Decimal("0.00"), Decimal("800000.00")],
        "unterversicherungsverzicht": [True, False],
        "bauartklasse": ["0", "I"],
        "baujahr": [1850, 2026],
        "gebaeudeart": ["EFH", "MIETWOHNUNG"],
        "stockwerk": [-1, 25],
        "zuers_zone": [1, 4],
        "elementar_eingeschlossen": [False, True],
        "sublimit_fahrrad_eur": [Decimal("0.01"), Decimal("10000.00")],
        "sublimit_wertsachen_eur": [None, Decimal("1234.56")],
    }
    original = typisierter_rahmen(daten, "risiko_hausrat")
    zurueck, parse_fehler = parse(serialisiere(original))
    assert parse_fehler.empty
    assert zurueck.equals(original)


def test_roundtrip_mit_schaltjahrestag_und_mitternacht() -> None:
    """Der 29. Februar und ein Zeitpunkt um Mitternacht bleiben erhalten."""
    daten: dict[str, list[Any]] = {
        "row_id": [1],
        "anfrage_id": ["a"],
        "eingangszeitpunkt": [dt.datetime(2024, 2, 29, 0, 0, 0)],  # noqa: DTZ001
        "kanal": ["WEB"],
        "sparte": ["051"],
        "vn_person_id": ["p"],
        "versicherungsbeginn": [dt.date(2024, 2, 29)],
        "vorvertrag_vorhanden": [True],
        "vorversicherer_vu_nr": ["01234"],
        "zahlweise": [8],
        "waehrung": ["EUR"],
        "anfrage_status": ["ANGEBOT"],
    }
    original = typisierter_rahmen(daten, "anfrage")
    roh = serialisiere(original)
    assert roh.loc[0, "versicherungsbeginn"] == "29022024"
    assert roh.loc[0, "eingangszeitpunkt"] == "2024-02-29T00:00:00"
    fuehrende_null = roh.loc[0, "vorversicherer_vu_nr"]
    assert fuehrende_null == "01234", "Die fuehrende Null darf nicht verloren gehen"
    zurueck, parse_fehler = parse(roh)
    assert parse_fehler.empty
    assert zurueck.equals(original)


def test_parser_wirft_keine_ausnahme_und_protokolliert() -> None:
    """Nicht parsebare Werte werden zu ``pd.NA`` und landen im Protokoll."""
    roh = serialisiere(
        typisierter_rahmen(
            {name: [None] for name in SPALTEN_JE_ENTITAET["risiko_hausrat"]}, "risiko_hausrat"
        )
    )
    roh.loc[0, "row_id"] = "k.A."
    roh.loc[0, "baujahr"] = "19x0"
    roh.loc[0, "versicherungssumme_eur"] = "1.234,56"
    roh.loc[0, "unterschiedlich"] = None  # Spalte wird gleich wieder entfernt
    roh = roh.drop(columns=["unterschiedlich"])

    typisiert, parse_fehler = parse(roh)
    assert len(parse_fehler) == 3
    assert set(parse_fehler["spalte"]) == {"row_id", "baujahr", "versicherungssumme_eur"}
    assert set(parse_fehler["entitaet"]) == {"risiko_hausrat"}
    assert typisiert["baujahr"].isna().all()
    assert typisiert["versicherungssumme_eur"].isna().all()


def test_gdv_nulldatum_ist_ein_befund() -> None:
    """``00000000`` wird zu ``pd.NA`` **und** protokolliert (siehe Modul-Docstring dort)."""
    roh = serialisiere(
        typisierter_rahmen({name: [None] for name in SPALTEN_JE_ENTITAET["person"]}, "person")
    )
    roh.loc[0, "geburtsdatum"] = "00000000"
    roh.loc[0, "fuehrerschein_datum"] = "31022026"
    typisiert, parse_fehler = parse(roh)
    assert typisiert["geburtsdatum"].isna().all()
    assert set(parse_fehler["spalte"]) == {"geburtsdatum", "fuehrerschein_datum"}


def test_unbekannte_spalte_bricht_ab() -> None:
    """Eine Spalte ausserhalb des Schemas ist ein Programmierfehler, kein Datenbefund."""
    rahmen = pd.DataFrame({"erfunden": pd.array(["x"], dtype="string")})
    with pytest.raises(SerialisierungsFehler):
        serialisiere(rahmen)
    with pytest.raises(SerialisierungsFehler):
        bestimme_entitaet(rahmen)


def test_entitaet_wird_aus_der_spaltenmenge_erkannt(
    datensatz: dict[str, pd.DataFrame],
) -> None:
    """Jede Entitaet ist an ihrer Spaltenmenge eindeutig erkennbar."""
    for name, rahmen in datensatz.items():
        assert bestimme_entitaet(rahmen) == name
        assert bestimme_entitaet(serialisiere(rahmen)) == name


def test_jede_spalte_hat_einen_feldtyp() -> None:
    """Das Schema deckt jede Spalte jeder Entitaet ab."""
    for entitaet in ENTITAETEN:
        for spalte in SPALTEN_JE_ENTITAET[entitaet]:
            assert spalte in FELDTYP_JE_SPALTE
            assert isinstance(FELDTYP_JE_SPALTE[spalte], Feldtyp)


def test_parquet_erhaelt_die_typisierung(
    datensatz: dict[str, pd.DataFrame], tmp_path_factory: pytest.TempPathFactory, config: Config
) -> None:
    """Beide Schichten ueberstehen den Weg durch Parquet unveraendert.

    Ohne diese Eigenschaft waere der auf Platte abgelegte Datensatz nicht
    derselbe wie der im Speicher erzeugte — und die spaeteren Phasen arbeiteten
    auf anderen Werten als die Tests hier.
    """
    assert config.stichtag is not None
    verzeichnis = tmp_path_factory.mktemp("parquet")
    for name, rahmen in datensatz.items():
        for schicht, inhalt in (("typed", rahmen), ("raw", serialisiere(rahmen))):
            pfad = verzeichnis / f"{name}_{schicht}.parquet"
            inhalt.to_parquet(pfad, index=False)
            assert pd.read_parquet(pfad).equals(inhalt), f"{name}/{schicht}"
