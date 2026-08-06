"""Tests des Regelkatalogs als Ganzes.

Der Katalog ist das Design-Artefakt der Arbeit; seine Kennzahlen stehen in
``spec/02_regelkatalog.md`` und werden im Anhang zitiert. Dieser Test haelt die
Implementierung an genau diesen Zahlen fest — sonst wanderte der Katalog
unbemerkt von seiner Spezifikation weg.

Ausserdem wird hier geprueft, dass **jede** Regel einen positiven und einen
negativen Testfall hat. Ohne diese Pruefung koennte eine Regel unbemerkt ohne
Test bleiben; die Zusicherung "je Regel mindestens ein positiver und ein
negativer Fall" waere dann eine Behauptung statt einer Eigenschaft.
"""

from __future__ import annotations

import csv
from typing import TYPE_CHECKING

import pytest

from src.common.pfade import Schicht
from src.rules.katalog import GRUPPENBEREICHE, KATALOG, REGELN_JE_GRUPPE, regel
from src.rules.modell import RegelFehler
from tests.test_regeln.test_g1_attribut import FAELLE as FAELLE_G1
from tests.test_regeln.test_g2_satz import FAELLE as FAELLE_G2
from tests.test_regeln.test_g3_relation import FAELLE as FAELLE_G3
from tests.test_regeln.test_g4_relationen import FAELLE as FAELLE_G4
from tests.test_regeln.test_g5_quellen import FAELLE as FAELLE_G5

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from pathlib import Path

    from src.common.config import Config

#: Alle Regeltestfaelle des Projekts.
ALLE_FAELLE = (*FAELLE_G1, *FAELLE_G2, *FAELLE_G3, *FAELLE_G4, *FAELLE_G5)

#: Regeln auf der Rohschicht (spec/02, Abschnitt "Auf welcher Datenschicht eine
#: Regel arbeitet"). Format-, Typ- und Sentinel-Pruefungen sind auf typisierten
#: Daten per Konstruktion nicht verletzbar.
ROHSCHICHT_REGELN = frozenset(
    {
        "R-002",
        "R-003",
        "R-004",
        "R-005",
        "R-006",
        "R-007",
        "R-008",
        "R-009",
        "R-013",
        "R-017",
        "R-025",
    }
)

#: Regeln, die keine verursachende Zelle benennen koennen (spec/02, R-047 und R-048).
DIAGNOSEREGELN = frozenset({"R-047", "R-048"})

#: Kennzahlen des Katalogs (spec/02, Abschnitt "Kennzahlen des Katalogs").
REGELN_GESAMT = 58
HARTE_REGELN = 47
WARNUNGEN = 11


def test_katalogumfang() -> None:
    """Der Katalog enthaelt genau die 58 Regeln R-001 bis R-058."""
    assert len(KATALOG) == REGELN_GESAMT
    erwartet = [f"R-{nummer:03d}" for nummer in range(1, REGELN_GESAMT + 1)]
    assert [eintrag.regel_id for eintrag in KATALOG] == erwartet


@pytest.mark.parametrize(("gruppe", "bereich"), sorted(GRUPPENBEREICHE.items()))
def test_gruppengroessen(gruppe: str, bereich: tuple[int, int]) -> None:
    """Die Gruppengroessen entsprechen den festen ID-Bereichen aus spec/02."""
    unten, oben = bereich
    assert len(REGELN_JE_GRUPPE[gruppe]) == oben - unten + 1


def test_schweregrade() -> None:
    """47 harte Regeln und 11 Warnungen — die Kennzahl aus spec/02."""
    hart = sum(1 for eintrag in KATALOG if eintrag.schweregrad == "HART")
    assert hart == HARTE_REGELN
    assert len(KATALOG) - hart == WARNUNGEN


def test_datenschicht() -> None:
    """Genau die elf Format-, Typ- und Sentinel-Regeln arbeiten auf der Rohschicht."""
    roh = {eintrag.regel_id for eintrag in KATALOG if eintrag.schicht is Schicht.RAW}
    assert roh == ROHSCHICHT_REGELN


def test_zellmetrik_kennzeichen() -> None:
    """Nur R-047 und R-048 stehen ausserhalb der Zellmetrik."""
    ausgenommen = {eintrag.regel_id for eintrag in KATALOG if not eintrag.in_zellmetrik}
    assert ausgenommen == DIAGNOSEREGELN


def test_metadaten_sind_gefuellt() -> None:
    """Jede Regel traegt Beschreibung, Entitaet, Literatur und fachliche Grundlage."""
    for eintrag in KATALOG:
        assert eintrag.beschreibung.strip(), f"{eintrag.regel_id} ohne Beschreibung"
        assert eintrag.entitaet.strip(), f"{eintrag.regel_id} ohne Entitaet"
        assert eintrag.literatur, f"{eintrag.regel_id} ohne Literaturbeleg"
        assert eintrag.fachliche_grundlage.strip(), (
            f"{eintrag.regel_id} ohne fachliche Grundlage"
        )
        assert eintrag.spalten, f"{eintrag.regel_id} ohne betroffene Spalten"


def test_unbekannte_regel_wird_gemeldet() -> None:
    """Eine Kennung ausserhalb des Katalogs bricht ab, statt still nichts zu tun."""
    with pytest.raises(RegelFehler, match="Unbekannte Regel"):
        regel("R-999")


@pytest.mark.parametrize("regel_id", [eintrag.regel_id for eintrag in KATALOG])
def test_je_regel_ein_positiver_und_ein_negativer_fall(regel_id: str) -> None:
    """Jede Regel hat mindestens einen positiven und einen negativen Testfall."""
    faelle = [fall for fall in ALLE_FAELLE if fall.regel_id == regel_id]
    positiv = [fall for fall in faelle if not fall.verletzt]
    negativ = [fall for fall in faelle if fall.verletzt]
    assert positiv, f"{regel_id} hat keinen positiven Testfall"
    assert negativ, f"{regel_id} hat keinen negativen Testfall"


def test_mindestens_116_regeltestfaelle() -> None:
    """58 Regeln mal zwei Faelle sind die Untergrenze aus der Phasenvorgabe."""
    assert len(ALLE_FAELLE) >= 2 * REGELN_GESAMT


def test_export_enthaelt_alle_regeln(config: Config, tmp_path: Path) -> None:
    """Der Katalogexport bildet jede Regel mit vollstaendigen Metadaten ab."""
    from scripts.export_katalog import SPALTEN, main  # noqa: PLC0415 - Skriptaufruf im Test

    assert main(["--ziel", str(tmp_path), "--still"]) == 0
    pfad = tmp_path / "regelkatalog.csv"
    assert pfad.is_file()

    with pfad.open(encoding="utf-8", newline="") as datei:
        zeilen = list(csv.DictReader(datei))

    assert [zeile["regel_id"] for zeile in zeilen] == [
        eintrag.regel_id for eintrag in KATALOG
    ]
    assert list(zeilen[0]) == list(SPALTEN)
    assert all(zeile["schicht"] in {"raw", "typed"} for zeile in zeilen)
    assert {zeile["regel_id"] for zeile in zeilen if zeile["in_zellmetrik"] == "nein"} == (
        DIAGNOSEREGELN
    )
    assert config.pfade.results.name == "results"
