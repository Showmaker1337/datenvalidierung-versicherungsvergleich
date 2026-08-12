"""Smoke-Test der Baseline B2 (sklearn IsolationForest) auf einem Minimaldatensatz.

B2 ist das einzige unueberwachte Verfahren des Vergleichs und das einzige mit
einem kontinuierlichen Score. Geprueft werden deshalb drei Dinge, die die anderen
Adapter nicht haben: dass eine grob abweichende Zeile ueberhaupt gefunden wird,
dass der Score in die richtige Richtung zeigt, und dass der Schwellen-Sweep
saemtliche sieben Stufen auf **denselben** Scores auswertet.

Der Minimaldatensatz
--------------------

Dreissig unauffaellige Fahrzeugzeilen und **eine** grob abweichende. Die
Abweichung liegt in drei Merkmalen zugleich (Leistung, Neupreis,
Jahresfahrleistung), damit sie nicht am Zufall des Waldes haengt: Ein Test, der
bei einem anderen Seed umkippt, prueft die Bibliothek und nicht den Adapter.

Dreissig Zeilen sind zugleich das Minimum, mit dem die Schwellenrechnung
aussagekraeftig ist. Bei ``contamination = 0.02`` liegt das zweite Perzentil von
einunddreissig Scores knapp ueber dem kleinsten Wert; anomal ist ``score <
schwelle``, und markiert wird damit genau die eine Zeile, die am staerksten
abweicht. Faende das Verfahren die eingebaute Abweichung nicht, waere sie nicht
die anomalste — und genau das soll der Test ausschliessen.

Die uebrigen Entitaeten tragen nur eine Zeile und damit keine Varianz. Dass B2
sie ueberspringt und den Grund **berichtet**, ist selbst eine Aussage des
Vergleichs und wird hier festgehalten.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any, Final

import pytest
from numpy.random import SeedSequence

from src.baselines.b2_isolation_forest import (
    B2_REGEL_ID,
    CONTAMINATION_STUFEN,
    STANDARD_CONTAMINATION,
    IsolationForestBaseline,
)
from src.evaluation.modell import SCORE_SPALTEN, VERSTOSS_SPALTEN, AuswertungsFehler
from tests.test_regeln.bausteine import VORGANG_KFZ, baue

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    import pandas as pd

    from src.common.config import Config
    from src.evaluation.modell import Kontext

#: Zahl der unauffaelligen Fahrzeugzeilen.
UNAUFFAELLIG: Final[int] = 30

#: ``row_id`` der eingebauten Ausreisserzeile — sie wird als letzte angehaengt.
AUSREISSER: Final[int] = UNAUFFAELLIG + 1

#: Fester Zufallsstrom des Modells; A2 verlangt einen Seed, keinen Zufall.
SEED: Final[int] = 20260630


def _fahrzeugzeilen() -> list[dict[str, Any]]:
    """Baut dreissig unauffaellige Fahrzeugzeilen und eine grob abweichende.

    Returns:
        Die Abweichungen zur Standardzeile aus
        :data:`tests.test_regeln.bausteine.STANDARD`, in Zeilenreihenfolge.
    """
    zeilen: list[dict[str, Any]] = [
        {"leistung_kw": 80 + nummer, "jahresfahrleistung_km": 9000 + 200 * nummer}
        for nummer in range(UNAUFFAELLIG)
    ]
    zeilen.append(
        {
            "leistung_kw": 4000,
            "jahresfahrleistung_km": 900_000,
            "neupreis_eur": Decimal("990000.00"),
        }
    )
    return zeilen


@pytest.fixture(scope="module")
def kontext(config: Config) -> Kontext:
    """Ein Vorgang mit einunddreissig Fahrzeugzeilen, davon eine grob abweichende."""
    return baue(config, {**VORGANG_KFZ, "risiko_kfz": _fahrzeugzeilen()})


@pytest.fixture(scope="module")
def meldungen(kontext: Kontext) -> pd.DataFrame:
    """Die Meldungen eines Laufs auf dem Minimaldatensatz."""
    return IsolationForestBaseline(SeedSequence(SEED)).erkenne(kontext)


def test_ausgabeformat_entspricht_dem_berichtsschema(meldungen: pd.DataFrame) -> None:
    """B2 liefert genau die Spalten, gegen die die Auswertung liest.

    Alle Meldungen tragen dieselbe ``regel_id``: B2 hat nur eine "Regel" — die
    Zeile weicht ab. Die Regeldiagnose der Auswertung weist B2 deshalb genau eine
    Zeile aus, und auch das ist ein Befund und kein Mangel.
    """
    assert tuple(meldungen.columns) == VERSTOSS_SPALTEN
    assert set(meldungen["regel_id"]) == {B2_REGEL_ID}


def test_grob_abweichende_zeile_wird_gefunden(meldungen: pd.DataFrame) -> None:
    """Markiert wird genau die eingebaute Ausreisserzeile, keine der uebrigen.

    Der Test prueft beide Richtungen: Ein Verfahren, das alles markiert, faende
    den Ausreisser ebenfalls — es haette nur keinerlei Precision.
    """
    markiert = set(zip(meldungen["entitaet"], meldungen["row_id"], strict=True))

    assert markiert == {("risiko_kfz", AUSREISSER)}


def test_eine_markierte_zeile_ergibt_eine_verstoss_id(meldungen: pd.DataFrame) -> None:
    """Alle Zellen einer markierten Zeile teilen sich eine ``verstoss_id``.

    Das ist die Einheit der Constraint-Ebene: B2 faellt **eine** Entscheidung je
    Zeile und schreibt sie auf alle befuellten Zellen um. Auf der Zellebene kostet
    ihn diese Umrechnung Precision, auf der Constraint-Ebene nicht — genau
    deshalb wird sie getrennt ausgewiesen.
    """
    assert set(meldungen["verstoss_id"]) == {f"{B2_REGEL_ID}#000001"}
    assert len(meldungen) > 1


def test_zellscores_zeigen_in_die_richtung_der_anomalie(kontext: Kontext) -> None:
    """Der hoechste Score gehoert zur markierten Zeile.

    ``sklearn`` liefert **kleinere** Werte fuer anomalere Zeilen; die
    Score-Tabelle verlangt die umgekehrte Orientierung, weil sonst die PR-AUC
    verkehrt herum stuende. Ein Vorzeichenfehler an dieser Stelle wuerde als
    aussagekraeftige, aber falsche Kennzahl in die Arbeit wandern.
    """
    scores = IsolationForestBaseline(SeedSequence(SEED)).zellscores(kontext)

    assert tuple(scores.columns) == SCORE_SPALTEN
    spitze = scores.loc[scores["score"] == scores["score"].max()]
    assert set(zip(spitze["entitaet"], spitze["row_id"], strict=True)) == {
        ("risiko_kfz", AUSREISSER)
    }


def test_zweimal_derselbe_seed_ergibt_bitgleiche_ausgabe(
    kontext: Kontext, meldungen: pd.DataFrame
) -> None:
    """Zwei Instanzen mit demselben Seed liefern denselben Rahmen (A2).

    Der Wald ist ein Zufallsverfahren; ohne den durchgereichten
    :class:`~numpy.random.SeedSequence` waere jeder Lauf ein anderer und keine
    Kennzahl der Phase 6 reproduzierbar.
    """
    zweiter = IsolationForestBaseline(SeedSequence(SEED)).erkenne(kontext)

    assert meldungen.equals(zweiter)


def test_sweep_wertet_alle_sieben_stufen_aus(kontext: Kontext) -> None:
    """Der Sweep enthaelt alle sieben Stufen in aufsteigender Reihenfolge.

    Die Stufen sind Schwellen auf **denselben** Scores und kein Modellparameter:
    ``contamination`` beeinflusst bei ``IsolationForest`` nur den
    Entscheidungs-Offset. Dass die Zahl der markierten Zeilen mit der Stufe
    monoton waechst, ist der beobachtbare Beleg dafuer — bei sieben getrennten
    Fits waere sie es nicht zwingend.
    """
    verfahren = IsolationForestBaseline(SeedSequence(SEED))
    verfahren.erkenne(kontext)
    sweep = verfahren.sweep()

    assert tuple(stufe.contamination for stufe in sweep) == CONTAMINATION_STUFEN
    markierte = [stufe.markierte_saetze for stufe in sweep]
    assert markierte == sorted(markierte)


def test_ohne_ground_truth_gilt_die_vorgabe(kontext: Kontext) -> None:
    """Ohne Wahrheit wird die mittlere Stufe genommen und das vermerkt.

    Die Kennzahlen des Sweeps bleiben dann ``None`` statt null: Eine Null waere
    von einer gemessenen F1 von null nicht zu unterscheiden. Der Vermerk gehoert
    in ``metrics.json``, sonst ist spaeter nicht erkennbar, ob die Stufe an der
    Wahrheit ausgerichtet wurde oder die Vorgabe ist.
    """
    verfahren = IsolationForestBaseline(SeedSequence(SEED))
    verfahren.erkenne(kontext)

    assert verfahren.gewaehlte_contamination() == STANDARD_CONTAMINATION
    assert "ohne Ground Truth" in verfahren.stufenwahl()
    assert all(stufe.f1_satz is None for stufe in verfahren.sweep())
    gewaehlt = [stufe.contamination for stufe in verfahren.sweep() if stufe.gewaehlt]
    assert gewaehlt == [STANDARD_CONTAMINATION]


def test_uebersprungene_entitaeten_werden_berichtet(kontext: Kontext) -> None:
    """Entitaeten ohne Varianz oder ohne Zeilen werden genannt, nicht verschwiegen.

    Sonst waere ihre Abwesenheit in den Ergebnissen von "B2 hat dort nichts
    gefunden" nicht zu unterscheiden. Im Minimaldatensatz trifft das jede Entitaet
    ausser ``risiko_kfz``: eine Zeile traegt keine Varianz, und ``risiko_hausrat``
    ist im Kfz-Vorgang gar nicht besetzt.
    """
    verfahren = IsolationForestBaseline(SeedSequence(SEED))
    verfahren.erkenne(kontext)
    uebersprungen = verfahren.uebersprungene_entitaeten()

    assert "risiko_kfz" not in uebersprungen
    assert uebersprungen["risiko_hausrat"] == "keine Zeilen"
    assert uebersprungen["person"] == "keine Merkmalsspalte mit Varianz"


def test_sweep_ohne_lauf_ist_ein_fehler() -> None:
    """Ohne bewerteten Kontext gibt es keinen Sweep, sondern eine Ausnahme.

    Ein leeres Tupel waere von "der Sweep ist leer" nicht zu unterscheiden — genau
    die Art stillen Fallbacks, die ``CLAUDE.md``, Abschnitt 5 ausschliesst.
    """
    with pytest.raises(AuswertungsFehler):
        IsolationForestBaseline(SeedSequence(SEED)).sweep()
