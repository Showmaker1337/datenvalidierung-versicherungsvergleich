"""Prueft die gemeinsamen Bausteine unter ``src/common``.

Diese Bausteine tragen alle spaeteren Phasen. Ein Fehler in :mod:`src.common.geld`
oder :mod:`src.common.config` wuerde sich still durch Generator, Regel-Engine und
Auswertung ziehen.
"""

from __future__ import annotations

import dataclasses
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

import pandas as pd
import pytest

from src.common import wertebereiche as wb
from src.common.config import KonfigurationsFehler, lade_config
from src.common.enums import (
    ANFRAGESTATUS_REIHENFOLGE,
    BAUARTKLASSEN,
    RATENANZAHL_JE_ZAHLWEISE,
    SF_KLASSEN,
    SF_KLASSEN_NUMERISCH,
    SF_KLASSEN_SONDER,
    ZAHLWEISEN_IM_GENERATOR,
    Anfragestatus,
    Quellschnittstelle,
    Sparte,
    Zahlweise,
    ist_kfz_sparte,
    schadenfreie_jahre,
    sf_ordnung,
)
from src.common.geld import GeldFehler, als_string, aus_string, runde, summe, von_float, zu_decimal
from src.common.pfade import Artefakt, PfadFehler, lauf_verzeichnis, sha256_dataframe, sha256_datei
from src.common.pflichtfelder import (
    KERNPFLICHTFELDER,
    PFLICHTFELDER_JE_SCHNITTSTELLE,
    PROFILFELDER,
    ist_pflicht,
    optionale_felder,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from pathlib import Path

    from src.common.config import Config


# ---------------------------------------------------------------------------
# config.py
# ---------------------------------------------------------------------------


def test_konfiguration_laedt_die_erwarteten_werte(config: Config) -> None:
    """Die ausgelieferte Konfiguration entspricht der Vorgabe."""
    assert config.stichtag == date(2026, 6, 30)
    assert config.master_seed == 20260630
    assert config.n_anfragen == 10000
    assert config.angebote_je_anfrage.minimum == 3
    assert config.angebote_je_anfrage.maximum == 12
    assert config.schwellen.r031_toleranz_eur == Decimal("0.02")
    # Obergrenze empirisch bestimmt, weil R-053 den Jahresbeitrag prueft und nicht
    # die Rate (docs/iteration_log.md, "Vorbemerkung zu R-053").
    assert config.schwellen.r053_korridor_kfz_eur == (Decimal(40), Decimal(13000))
    assert config.schwellen.r053_korridor_hausrat_eur == (Decimal(20), Decimal(2000))


def test_stichtag_ersetzt_die_systemzeit(config: Config) -> None:
    """Architekturregel A2: Das Referenzdatum kommt aus der Konfiguration."""
    assert config.stichtag != date.today()  # noqa: DTZ011


def test_konfiguration_ist_eingefroren(config: Config) -> None:
    """Kein Programmteil kann die Konfiguration nachtraeglich veraendern."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.master_seed = 1  # type: ignore[misc]


def test_pfade_sind_absolut(config: Config) -> None:
    """Alle Pfade sind gegen das Wurzelverzeichnis aufgeloest."""
    assert config.pfade.reference.is_absolute()
    assert config.pfade.runs.is_absolute()
    assert config.pfade.results.is_absolute()
    assert config.pfade.reference.parent.parent == config.pfade.wurzel


def test_sparten_verteilung_ist_vollstaendig_und_geordnet(config: Config) -> None:
    """Alle Sparten kommen vor, die Summe ist 1, die Reihenfolge ist festgelegt."""
    assert set(config.sparten_verteilung) == {sparte.value for sparte in Sparte}
    assert abs(sum(config.sparten_verteilung.values()) - 1.0) < 1e-9
    assert list(config.sparten_verteilung) == sorted(config.sparten_verteilung)


def test_toleranzschwellen_sind_decimal(config: Config) -> None:
    """Geldschwellen sind Decimal — sonst kaeme die Binaerdarstellung in die Regel."""
    assert isinstance(config.schwellen.r031_toleranz_eur, Decimal)
    assert isinstance(config.schwellen.r036_toleranz_je_rate_eur, Decimal)
    assert config.schwellen.r031_toleranz_eur == Decimal("0.02")


def test_fehlende_datei_wirft(tmp_path: Path) -> None:
    """Eine nicht vorhandene Konfigurationsdatei bricht ab."""
    with pytest.raises(KonfigurationsFehler, match="nicht gefunden"):
        lade_config(tmp_path / "gibtesnicht.yaml")


def test_fehlender_pflichtschluessel_wirft(tmp_path: Path) -> None:
    """Ein fehlender Schluessel wird nicht still durch einen Default ersetzt."""
    pfad = tmp_path / "unvollstaendig.yaml"
    pfad.write_text("master_seed: 1\n", encoding="utf-8")
    with pytest.raises(KonfigurationsFehler, match="fehlt"):
        lade_config(pfad)


def test_unbekannter_schluessel_wirft(config: Config, tmp_path: Path) -> None:
    """Ein Tippfehler in der Konfiguration bleibt nicht wirkungslos."""
    original = config.quelldatei.read_text(encoding="utf-8")
    pfad = tmp_path / "mit_tippfehler.yaml"
    pfad.write_text(original + "\nn_anfrage: 5\n", encoding="utf-8")
    with pytest.raises(KonfigurationsFehler, match="Unbekannte Schluessel"):
        lade_config(pfad)


def test_falsche_spartensumme_wirft(config: Config, tmp_path: Path) -> None:
    """Eine Verteilung, die nicht auf 1 summiert, waere ein stiller Messfehler."""
    original = config.quelldatei.read_text(encoding="utf-8")
    verfaelscht = original.replace('"051": 0.35', '"051": 0.45')
    pfad = tmp_path / "falsche_summe.yaml"
    pfad.write_text(verfaelscht, encoding="utf-8")
    with pytest.raises(KonfigurationsFehler, match="summieren"):
        lade_config(pfad)


# ---------------------------------------------------------------------------
# geld.py
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("eingabe", "erwartet"),
    [
        ("0.005", "0.01"),
        ("0.015", "0.02"),
        ("0.025", "0.03"),
        ("2.345", "2.35"),
        ("-0.005", "-0.01"),
        ("1234.5", "1234.50"),
        ("7", "7.00"),
    ],
)
def test_runde_arbeitet_kaufmaennisch(eingabe: str, erwartet: str) -> None:
    """ROUND_HALF_UP statt bankers rounding: 0,015 wird immer zu 0,02, nie zu 0,01."""
    assert runde(Decimal(eingabe)) == Decimal(erwartet)


def test_float_wird_abgewiesen() -> None:
    """Geld ist niemals float (CLAUDE.md, Abschnitt 5)."""
    with pytest.raises(GeldFehler, match="float"):
        zu_decimal(0.1)  # type: ignore[arg-type]


def test_wahrheitswert_ist_kein_betrag() -> None:
    """``True`` ist in Python ein ``int`` — hier waere das ein stiller Fehler."""
    with pytest.raises(GeldFehler):
        zu_decimal(True)  # noqa: FBT003


def test_von_float_vermeidet_die_binaerentwicklung() -> None:
    """Der Umweg ueber ``repr`` verhindert Artefakte wie 0.1 + 0.2."""
    assert von_float(0.1 + 0.2) == Decimal("0.30")
    assert von_float(1234.567) == Decimal("1234.57")


def test_summe_rundet_erst_am_ende() -> None:
    """Zwischenrundungen wuerden sich ueber viele Angebotszeilen aufsummieren."""
    assert summe([Decimal("0.004")] * 3) == Decimal("0.01")
    assert summe([]) == Decimal("0.00")


def test_serialisierung_und_rueckweg() -> None:
    """Das Format der Rohschicht ist Dezimalpunkt mit zwei Stellen (spec/01, Abschnitt 6)."""
    assert als_string(Decimal("1234.5")) == "1234.50"
    assert als_string(-7) == "-7.00"
    assert aus_string("1234.50") == Decimal("1234.50")


@pytest.mark.parametrize("text", ["1234,50", "1.234.50", "k.A.", "", "1234", "1234.5", "abc"])
def test_unbrauchbarer_betrag_liefert_none(text: str) -> None:
    """Ein nicht parsbarer Wert ist ein Befund, kein Absturz (spec/01, Abschnitt 6)."""
    assert aus_string(text) is None


# ---------------------------------------------------------------------------
# enums.py
# ---------------------------------------------------------------------------


def test_zahlweise_kennt_3_und_7_nicht() -> None:
    """GDV Anlage 14: Die Schluessel 3 und 7 existieren nicht (R-010, F3-d, F3-e)."""
    werte = {zahlweise.value for zahlweise in Zahlweise}
    assert werte == {1, 2, 4, 5, 6, 8, 9}
    assert 3 not in werte
    assert 7 not in werte


def test_generator_zieht_weder_sonstiges_noch_beitragsfrei() -> None:
    """spec/01, Abschnitt 3.1: 5 und 9 bleiben gueltig, kommen aber nicht vor."""
    gezogen = {zahlweise.value for zahlweise in ZAHLWEISEN_IM_GENERATOR}
    assert gezogen == {1, 2, 4, 6, 8}
    assert Zahlweise.SONSTIGES not in ZAHLWEISEN_IM_GENERATOR
    assert Zahlweise.BEITRAGSFREI not in ZAHLWEISEN_IM_GENERATOR


def test_ratenanzahl_mapping() -> None:
    """Die Ratenanzahl entspricht spec/01, Abschnitt 3.1."""
    erwartet = {1: 1, 2: 2, 4: 4, 5: 1, 6: 1, 8: 12, 9: 1}
    assert {int(k): v for k, v in RATENANZAHL_JE_ZAHLWEISE.items()} == erwartet


def test_sparten_und_kfz_zuordnung() -> None:
    """051, 052 und 053 sind Kfz, 130 ist Hausrat."""
    assert {sparte.value for sparte in Sparte} == {"051", "052", "053", "130"}
    assert ist_kfz_sparte("051")
    assert ist_kfz_sparte("053")
    assert not ist_kfz_sparte("130")


def test_bauartklassen_enthalten_kein_j() -> None:
    """GDV Anlage 12 kennt A bis I; ``J`` ist die Injektionsvariante F3-h."""
    assert "I" in BAUARTKLASSEN
    assert "J" not in BAUARTKLASSEN
    assert set(BAUARTKLASSEN) == set("012345678ABCDEFGHI")


def test_sf_katalog_ist_vollstaendig() -> None:
    """Vier Sonderklassen und SF1 bis SF50, alle als String (R-013)."""
    assert len(SF_KLASSEN) == 54
    assert set(SF_KLASSEN_SONDER) == {"M", "S", "0", "1/2"}
    assert SF_KLASSEN_NUMERISCH[0] == "SF1"
    assert SF_KLASSEN_NUMERISCH[-1] == "SF50"


# --- schadenfreie_jahre() fuer R-029 ---------------------------------------


@pytest.mark.parametrize(
    ("sf_klasse", "erwartet"),
    [
        ("M", 0),
        ("S", 0),
        ("0", 0),
        ("1/2", 0),
        ("SF1", 1),
        ("SF12", 12),
        ("SF50", 50),
    ],
)
def test_schadenfreie_jahre(sf_klasse: str, erwartet: int) -> None:
    """Abbildung nach spec/01, Abschnitt 2.8."""
    assert schadenfreie_jahre(sf_klasse) == erwartet


def test_alle_sonderklassen_bedeuten_null_schadenfreie_jahre() -> None:
    """R-029 ist bei Sonderklassen trivial erfuellt — fachlich korrekt, kein Ausweichen."""
    assert all(schadenfreie_jahre(klasse) == 0 for klasse in SF_KLASSEN_SONDER)


def test_schadenfreie_jahre_deckt_den_gesamten_katalog_ab() -> None:
    """Kein gueltiger Katalogwert darf ``None`` liefern — sonst uebersaehe R-029 ihn."""
    assert all(schadenfreie_jahre(klasse) is not None for klasse in SF_KLASSEN)


# --- sf_ordnung() fuer R-030 -----------------------------------------------


@pytest.mark.parametrize(
    ("sf_klasse", "erwartet"),
    [
        ("M", -3),
        ("S", -2),
        ("0", -1),
        ("1/2", 0),
        ("SF1", 1),
        ("SF12", 12),
        ("SF50", 50),
    ],
)
def test_sf_ordnung(sf_klasse: str, erwartet: int) -> None:
    """Abbildung nach spec/01, Abschnitt 2.8."""
    assert sf_ordnung(sf_klasse) == erwartet


def _ordnung(sf_klasse: str) -> int:
    """Wie :func:`sf_ordnung`, bricht aber bei einem Wert ausserhalb des Katalogs ab."""
    wert = sf_ordnung(sf_klasse)
    assert wert is not None, f"{sf_klasse!r} ist kein gueltiger Katalogwert"
    return wert


def test_sf_ordnung_ist_ueber_den_gesamten_katalog_streng_steigend() -> None:
    """Vollstaendige Ordnung: M < S < 0 < 1/2 < SF1 < ... < SF50."""
    reihenfolge = ["M", "S", "0", "1/2", *SF_KLASSEN_NUMERISCH]
    werte = [_ordnung(klasse) for klasse in reihenfolge]
    assert werte == sorted(werte)
    assert len(set(werte)) == len(werte), "Kein Wert darf doppelt vorkommen"


def test_sf_ordnung_grenzfaelle() -> None:
    """Die beiden Faelle, die eine unvollstaendige Ordnung stillschweigend uebergehen wuerde."""
    # M ist schlechter als S — mit einer Abbildung auf 0 waeren beide gleich.
    assert _ordnung("M") < _ordnung("S")
    # 1/2 ist schlechter als SF1, aber besser als 0.
    assert _ordnung("0") < _ordnung("1/2") < _ordnung("SF1")


def test_die_beiden_abbildungen_messen_verschiedenes() -> None:
    """Kernaussage aus spec/01, Abschnitt 2.8: eine Funktion reicht nicht.

    Bei ``schadenfreie_jahre`` sind ``M`` und ``1/2`` gleich (beide null Jahre),
    bei ``sf_ordnung`` liegen drei Stufen dazwischen.
    """
    assert schadenfreie_jahre("M") == schadenfreie_jahre("1/2")
    assert sf_ordnung("M") != sf_ordnung("1/2")


# --- Werte ausserhalb des Katalogs -----------------------------------------


@pytest.mark.parametrize("unsinn", ["SF0", "SF51", "SF", "12", "", "sf12", "SFx", "N", "1/3"])
def test_ungueltige_sf_klasse_liefert_none(unsinn: str) -> None:
    """Ein Wert ausserhalb des Katalogs ist ein Befund von R-013, kein Absturz."""
    assert schadenfreie_jahre(unsinn) is None
    assert sf_ordnung(unsinn) is None


def test_anfragestatus_reihenfolge_ist_vollstaendig() -> None:
    """Die Prozessreihenfolge enthaelt jeden Status genau einmal."""
    assert set(ANFRAGESTATUS_REIHENFOLGE) == set(Anfragestatus)
    assert len(ANFRAGESTATUS_REIHENFOLGE) == len(set(ANFRAGESTATUS_REIHENFOLGE))


# ---------------------------------------------------------------------------
# wertebereiche.py
# ---------------------------------------------------------------------------


def test_versicherungsteuer_effektivsaetze() -> None:
    """19,00 Prozent fuer Kfz, 16,15 Prozent fuer Hausrat (R-033)."""
    saetze = wb.VERSICHERUNGSTEUER_EFFEKTIVSATZ
    assert saetze[Sparte.KFZ_HAFTPFLICHT] == Decimal("19.00")
    assert saetze[Sparte.KFZ_VOLLKASKO] == Decimal("19.00")
    assert saetze[Sparte.KFZ_TEILKASKO] == Decimal("19.00")
    assert saetze[Sparte.HAUSRAT] == Decimal("16.15")
    assert set(saetze) == set(Sparte)


def test_effektivsatz_hausrat_folgt_aus_nominalsatz_und_bemessungsgrundlage() -> None:
    """16,15 = 19,00 mal 0,85 — der Unterschied ist in der Arbeit zu erklaeren."""
    berechnet = wb.VERSICHERUNGSTEUER_NOMINALSATZ * wb.BEMESSUNGSGRUNDLAGE_HAUSRAT
    assert runde(berechnet) == wb.VERSICHERUNGSTEUER_EFFEKTIVSATZ[Sparte.HAUSRAT]


def test_pflvg_mindestdeckungssummen() -> None:
    """PflVG, Anlage zu Paragraf 4 Absatz 2 (R-024)."""
    assert Decimal("7500000.00") == wb.PFLVG_MINDESTDECKUNG_PERSONEN_EUR
    assert Decimal("1300000.00") == wb.PFLVG_MINDESTDECKUNG_SACH_EUR
    assert Decimal("50000.00") == wb.PFLVG_MINDESTDECKUNG_VERMOEGEN_EUR


def test_typklassen_und_regionalklassen_grenzen() -> None:
    """16 / 24 / 25 Typklassen, 12 / 16 / 9 Regionalklassen."""
    assert wb.TYPKLASSE_HP == (10, 25)
    assert wb.TYPKLASSE_TK == (10, 33)
    assert wb.TYPKLASSE_VK == (10, 34)
    assert wb.REGIONALKLASSE_HP == (1, 12)
    assert wb.REGIONALKLASSE_TK == (1, 16)
    assert wb.REGIONALKLASSE_VK == (1, 9)


def test_bic_laengen_schliessen_9_und_10_aus() -> None:
    """ISO 9362 kennt nur 8 oder 11 Zeichen (R-005, F2-e)."""
    assert wb.BIC_LAENGEN == (8, 11)


def test_sentinel_ausnahmen_sind_begruendet() -> None:
    """9999 ist in Fahrleistung und Sublimits ein legitimer Wert (R-025)."""
    assert 9999 in wb.SENTINEL_NUMERISCH
    assert "risiko_kfz.jahresfahrleistung_km" in wb.SENTINEL_AUSNAHMEFELDER
    assert "risiko_hausrat.sublimit_fahrrad_eur" in wb.SENTINEL_AUSNAHMEFELDER
    assert "" in wb.SENTINEL_TEXT, "Der Leerstring ist ein Fehlerwert, kein Fehlwert (F1-b)"


def test_nulldatum_ist_ein_sentinel_kein_leerwert() -> None:
    """``00000000`` ist ein als Wert getarnter Fehlwert (spec/01, Abschnitt 6).

    Waere es der regulaere Leerwert, koennte R-025 es nicht mehr melden und R-009
    muesste es als Nicht-Kalendertag ausnehmen. Leer ist stattdessen der
    Leerstring — und der steht nicht in dieser Liste.
    """
    assert "00000000" in wb.SENTINEL_DATUM
    assert "01011900" in wb.SENTINEL_DATUM, "1900-01-01 im Rohformat TTMMJJJJ"
    assert "" not in wb.SENTINEL_DATUM, "Der Leerstring ist der regulaere Leerwert"


# ---------------------------------------------------------------------------
# pflichtfelder.py
# ---------------------------------------------------------------------------


def test_bipro_verlangt_mehr_als_csv_import() -> None:
    """Kernaussage des Multi-Source-Problems (R-057)."""
    bipro = set(PFLICHTFELDER_JE_SCHNITTSTELLE[Quellschnittstelle.BIPRO_420])
    csv = set(PFLICHTFELDER_JE_SCHNITTSTELLE[Quellschnittstelle.CSV_IMPORT])
    assert csv < bipro
    assert csv == {"risiko_kfz.jahresfahrleistung_km"}


def test_bic_ist_die_ausnahme_vom_muster() -> None:
    """Einzige Zeile der Tabelle, in der GDV strenger ist als BIPRO_RNEXT."""
    assert ist_pflicht("zahlung.bic", Quellschnittstelle.BIPRO_420)
    assert ist_pflicht("zahlung.bic", Quellschnittstelle.GDV)
    assert not ist_pflicht("zahlung.bic", Quellschnittstelle.BIPRO_RNEXT)
    assert not ist_pflicht("zahlung.bic", Quellschnittstelle.CSV_IMPORT)


def test_kernpflichtfelder_gelten_unabhaengig_von_der_schnittstelle() -> None:
    """R-001 steht ueber dem Profil."""
    for schnittstelle in Quellschnittstelle:
        for feld in KERNPFLICHTFELDER:
            assert ist_pflicht(feld, schnittstelle)


def test_optionale_felder_ergaenzen_die_pflichtfelder(
) -> None:
    """Pflicht- und optionale Profilfelder ergeben zusammen alle Profilfelder."""
    for schnittstelle in Quellschnittstelle:
        pflicht = set(PFLICHTFELDER_JE_SCHNITTSTELLE[schnittstelle])
        optional = set(optionale_felder(schnittstelle))
        assert pflicht | optional == set(PROFILFELDER)
        assert not pflicht & optional


def test_profilfelder_sind_eindeutig() -> None:
    """Kein Feld steht zweimal in der Tabelle."""
    assert len(PROFILFELDER) == len(set(PROFILFELDER))


# ---------------------------------------------------------------------------
# pfade.py
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("run_id", ["lauf1", "F3-d_r05_w12", "A", "a" * 64])
def test_gueltige_run_ids(config: Config, run_id: str) -> None:
    """Zulaessige Kennungen werden angenommen."""
    assert lauf_verzeichnis(config, run_id).name == run_id


@pytest.mark.parametrize(
    "run_id", ["", "..", "../geheim", "lauf/1", "lauf 1", "lauf.1", "-lauf", "a" * 65]
)
def test_unzulaessige_run_ids_werden_abgewiesen(config: Config, run_id: str) -> None:
    """Keine Kennung darf aus ``data/runs`` herausfuehren."""
    with pytest.raises(PfadFehler):
        lauf_verzeichnis(config, run_id)


def test_lauf_verzeichnis_liegt_unter_runs(config: Config) -> None:
    """Das Laufverzeichnis liegt immer unterhalb des konfigurierten Pfades."""
    verzeichnis = lauf_verzeichnis(config, "probe")
    assert verzeichnis.parent == config.pfade.runs


def test_artefaktnamen_sind_eindeutig() -> None:
    """Zwei Artefakte duerfen nicht auf dieselbe Datei zeigen."""
    namen = [artefakt.value for artefakt in Artefakt]
    assert len(namen) == len(set(namen))


def test_dataframe_hash_ist_stabil_und_empfindlich() -> None:
    """Gleiche Daten ergeben denselben Hash, eine geaenderte Zelle einen anderen."""
    erster = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    zweiter = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    dritter = pd.DataFrame({"a": [1, 2, 4], "b": ["x", "y", "z"]})

    assert sha256_dataframe(erster) == sha256_dataframe(zweiter)
    assert sha256_dataframe(erster) != sha256_dataframe(dritter)


def test_dataframe_hash_beachtet_spaltenreihenfolge() -> None:
    """Reihenfolge gehoert zur Reproduzierbarkeit und darf nicht wegnormiert werden."""
    erster = pd.DataFrame({"a": [1], "b": [2]})
    zweiter = pd.DataFrame({"b": [2], "a": [1]})
    assert sha256_dataframe(erster) != sha256_dataframe(zweiter)


def test_dataframe_hash_traegt_decimal_exakt() -> None:
    """Decimal-Werte gehen ohne Umweg ueber float in den Hash ein."""
    erster = pd.DataFrame({"betrag": [Decimal("1234.50")]})
    zweiter = pd.DataFrame({"betrag": [Decimal("1234.500")]})
    assert sha256_dataframe(erster) != sha256_dataframe(zweiter)


def test_hash_einer_fehlenden_datei_wirft(tmp_path: Path) -> None:
    """Kein stiller Fallback auf einen Leerhash."""
    with pytest.raises(PfadFehler, match="nicht gefunden"):
        sha256_datei(tmp_path / "gibtesnicht.csv")
