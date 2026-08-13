"""Haelt die Variantentabelle der Auswertung gegen Injektor und Regelkatalog.

``src/evaluation/varianten.py`` schreibt die Zuordnung Variante auf Regel aus
``spec/03``, Abschnitt 2 ab — sie darf laut Abschnitt 6 **nicht** aus dem
Quelltext des Injektors stammen. Der Preis dieser Trennung ist eine Abschrift,
die auseinanderlaufen kann; dieser Test ist der Gegenwert.

Ein Test darf beide Seiten kennen. Der Produktivcode darf es nicht: Wuerde
``src/evaluation`` aus ``src/injector`` importieren, maesse das Experiment nur
noch, ob dieselbe Bedingung zweimal geschrieben wurde.
"""

from __future__ import annotations

from src.evaluation.varianten import (
    ALLE_VARIANTEN_IDS,
    VARIANTENTABELLE,
    Spiegelung,
    klasse_je_variante,
    variantenbezug,
)
from src.injector.varianten import ALLE_VARIANTEN
from src.rules.katalog import REGEL_JE_ID

#: Varianten, die laut spec/03 absichtlich unentdeckt bleiben sollen.
ERWARTET_UNENTDECKT = {"F5-e", "F7-d", "F8-e", "HO1-a", "HO1-b", "HO2-a", "HO2-b"}


def test_kennungen_stimmen_mit_dem_injektor_ueberein() -> None:
    """Beide Seiten kennen dieselben sechzig Varianten, in derselben Reihenfolge."""
    aus_injektor = [eintrag.variante_id for eintrag in ALLE_VARIANTEN]
    assert list(ALLE_VARIANTEN_IDS) == aus_injektor


def test_fehlerklassen_stimmen_mit_dem_injektor_ueberein() -> None:
    """Jede Variante gehoert auf beiden Seiten zur selben Fehlerklasse."""
    zuordnung = klasse_je_variante()
    abweichungen = [
        (eintrag.variante_id, zuordnung[eintrag.variante_id], eintrag.fehlerklasse.value)
        for eintrag in ALLE_VARIANTEN
        if zuordnung[eintrag.variante_id] != eintrag.fehlerklasse.value
    ]
    assert not abweichungen, abweichungen


def test_alle_erwarteten_regeln_existieren() -> None:
    """Jede genannte Regel-ID steht im eingefrorenen Katalog."""
    unbekannt = sorted(
        {
            regel_id
            for eintrag in VARIANTENTABELLE
            for regel_id in eintrag.erwartete_regeln
            if regel_id not in REGEL_JE_ID
        }
    )
    assert not unbekannt, unbekannt


def test_erwartet_unentdeckte_varianten_sind_die_aus_der_spezifikation() -> None:
    """Genau die in ``spec/03`` genannten Varianten sind als unentdeckt gefuehrt."""
    gefuehrt = {
        eintrag.variante_id for eintrag in VARIANTENTABELLE if eintrag.erwartet_unentdeckt
    }
    assert gefuehrt == ERWARTET_UNENTDECKT


def test_unentdeckte_varianten_nennen_keine_erwartete_regel() -> None:
    """Eine Variante, die nicht gefunden werden soll, hat keine Zielregel.

    Beides zugleich waere ein Widerspruch: Eine Regel, die auf sie zielt, und die
    Erwartung, dass sie unentdeckt bleibt.
    """
    widersprueche = [
        eintrag.variante_id
        for eintrag in VARIANTENTABELLE
        if eintrag.erwartet_unentdeckt and eintrag.erwartete_regeln
    ]
    assert not widersprueche, widersprueche


def test_nicht_exakt_spiegelnde_varianten_haben_eine_begruendung() -> None:
    """Jede Einstufung ausser "ja" traegt einen Satz Begruendung.

    Ohne Begruendung waere die Spalte in ``t4_varianten.csv`` eine Behauptung,
    und die Abbildung 5 liesse sich ohne den Spezifikationstext nicht lesen.
    """
    ohne = [
        eintrag.variante_id
        for eintrag in VARIANTENTABELLE
        if eintrag.spiegelung is not Spiegelung.JA and not eintrag.anmerkung
    ]
    assert not ohne, ohne


def test_variantenbezug_meldet_unbekannte_kennung() -> None:
    """Eine unbekannte Kennung wird gemeldet und nicht als "spiegelt nicht" gefuehrt."""
    import pytest  # noqa: PLC0415 - nur fuer diesen Test gebraucht

    with pytest.raises(KeyError, match="Unbekannte injektor_variante_id"):
        variantenbezug("F9-z")


def test_jede_klasse_hat_mindestens_eine_exakt_spiegelnde_variante() -> None:
    """Ausser bei den Held-out-Klassen gibt es je Klasse eine Zielregel.

    Sonst waere der klassenweise Recall trivial null, und die Klasse maesse
    nichts ueber den Katalog.
    """
    ohne_ziel = sorted(
        {
            eintrag.fehlerklasse
            for eintrag in VARIANTENTABELLE
            if not eintrag.fehlerklasse.startswith("HO")
        }
        - {
            eintrag.fehlerklasse
            for eintrag in VARIANTENTABELLE
            if eintrag.spiegelung is Spiegelung.JA
        }
    )
    assert not ohne_ziel, ohne_ziel
