"""Prueft die Inferenzstatistik gegen handgerechnete Beispiele.

Jeder Test dieser Datei vergleicht gegen einen Wert, der **ausserhalb** des
Programms bestimmt wurde — von Hand aus der Definition oder aus einem
Lehrbuchbeispiel. Ein Test, der die Implementierung gegen sich selbst prueft,
belegt nur, dass sie sich nicht veraendert hat, nicht dass sie richtig ist.

Der wichtigste Test ist :func:`test_bootstrap_entartet_weicht_auf_clopper_pearson_aus`
------------------------------------------------------------------------------------

Ohne den Ausweichweg bricht ausgerechnet die Abbildung, die das "inwieweit" der
Forschungsfrage beantwortet: Bei den Held-out-Klassen liefert jede Wiederholung
denselben Recall, die Jackknife-Streuung ist null und die BCa-Beschleunigung ein
Bruch ``0/0``.
"""

from __future__ import annotations

import math

import pytest

from src.evaluation.modell import AuswertungsFehler
from src.evaluation.statistik import (
    Intervallart,
    art_anova_interaktion,
    bootstrap_ci,
    cliffs_delta,
    friedman,
    holm,
    page_trend,
    rang_biserial,
    seed_warnung,
    spearman,
    wilcoxon_gepaart,
)

#: Toleranz beim Vergleich von Gleitkommazahlen.
TOLERANZ = 1e-9


# ---------------------------------------------------------------------------
# Wilcoxon und rank-biserial
# ---------------------------------------------------------------------------


def test_wilcoxon_exakter_p_wert_bei_fuenf_gleichgerichteten_paaren() -> None:
    """Fuenf Paare, alle Differenzen positiv: p = 2 / 2**5 = 0,0625.

    Handrechnung: Bei fuenf von null verschiedenen Differenzen gibt es 2**5 = 32
    Vorzeichenverteilungen. Genau zwei davon sind mindestens so extrem wie die
    beobachtete (alle positiv, alle negativ), also p = 2/32.
    """
    ergebnis = wilcoxon_gepaart([2.0, 3.0, 4.0, 5.0, 6.0], [1.0, 2.0, 3.0, 4.0, 5.0])
    assert ergebnis.p_wert == pytest.approx(2 / 32)
    assert ergebnis.statistik == pytest.approx(15.0)  # W+ = 1+2+3+4+5
    assert ergebnis.effekt == pytest.approx(1.0)


def test_rank_biserial_aus_der_definition() -> None:
    """``r = (W+ - W-) / (W+ + W-)`` an einem von Hand gerechneten Beispiel.

    Differenzen: +1, +1, +1, -4. Betraege 1, 1, 1, 4; mittlere Raenge 2, 2, 2, 4.
    Damit ist W+ = 6, W- = 4 und r = (6-4)/10 = 0,2.
    """
    erste = [2.0, 2.0, 2.0, 1.0]
    zweite = [1.0, 1.0, 1.0, 5.0]
    assert rang_biserial(erste, zweite) == pytest.approx(0.2)


def test_wilcoxon_bei_lauter_nulldifferenzen_meldet_es() -> None:
    """Gleiche Reihen sind nicht testbar, und das Ergebnis sagt es."""
    ergebnis = wilcoxon_gepaart([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
    assert ergebnis.p_wert == 1.0
    assert ergebnis.effekt == 0.0
    assert "nichts zu messen" in ergebnis.hinweis


def test_wilcoxon_verlangt_gleich_lange_reihen() -> None:
    """Ungleich lange Reihen sind kein Sonderfall, sondern ein Fehler."""
    with pytest.raises(AuswertungsFehler, match="gleich lang"):
        wilcoxon_gepaart([1.0, 2.0], [1.0])


# ---------------------------------------------------------------------------
# Cliff's Delta
# ---------------------------------------------------------------------------


def test_cliffs_delta_aus_der_definition() -> None:
    """``delta = (#(a>b) - #(a<b)) / (n_a * n_b)``.

    Mit a = [1, 2, 3] und b = [2, 3]: groesser in 2 Paaren (3>2, 3>... nein:
    (1,2) kleiner, (1,3) kleiner, (2,2) gleich, (2,3) kleiner, (3,2) groesser,
    (3,3) gleich. Also groesser = 1, kleiner = 3, delta = (1-3)/6 = -1/3.
    """
    assert cliffs_delta([1.0, 2.0, 3.0], [2.0, 3.0]) == pytest.approx(-1 / 3)


def test_cliffs_delta_ist_eins_bei_vollstaendiger_trennung() -> None:
    """Liegt jede Beobachtung von ``a`` ueber jeder von ``b``, ist delta = 1."""
    assert cliffs_delta([5.0, 6.0], [1.0, 2.0]) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Friedman und Page
# ---------------------------------------------------------------------------


def test_friedman_gegen_handrechnung() -> None:
    """Vier Bloecke, drei Gruppen mit identischer Rangfolge.

    Handrechnung: Jede Zeile hat die Raenge 1, 2, 3, also R = (4, 8, 12) bei
    n = 4 Bloecken und k = 3 Gruppen::

        chi2 = 12 / (n*k*(k+1)) * sum(R_j^2) - 3*n*(k+1)
             = 12 / (4*3*4) * (16 + 64 + 144) - 3*4*4
             = 0,25 * 224 - 48 = 8,0

    Kendalls W = chi2 / (n * (k-1)) = 8 / 8 = 1,0 — vollstaendige Konkordanz.
    """
    matrix = [[1.0, 2.0, 3.0]] * 4
    ergebnis = friedman(matrix)
    assert ergebnis.statistik == pytest.approx(8.0)
    assert ergebnis.effekt == pytest.approx(1.0)


def test_page_trend_gegen_handrechnung() -> None:
    """Vier Bloecke, drei geordnete Stufen mit durchgehend steigendem Trend.

    Handrechnung: Raenge je Block 1, 2, 3, also Rangsummen R = (4, 8, 12)::

        L      = 1*4 + 2*8 + 3*12 = 56
        E[L]   = n*k*(k+1)^2 / 4 = 4*3*16/4 = 48
        Var[L] = n*(k^3-k)^2 / (144*(k-1)) = 4*576 / 288 = 8
        z      = (56 - 48) / sqrt(8) = 2,8284...
    """
    matrix = [[1.0, 2.0, 3.0]] * 4
    ergebnis = page_trend(matrix)
    assert ergebnis.statistik == pytest.approx(56.0)
    erwartetes_z = (56.0 - 48.0) / math.sqrt(8.0)
    assert ergebnis.effekt == pytest.approx(erwartetes_z / math.sqrt(4))
    assert ergebnis.p_wert < 0.01
    assert ergebnis.seitig == "einseitig"


def test_page_trend_erkennt_fallenden_trend_nicht_als_steigend() -> None:
    """Ein fallender Trend darf keinen kleinen einseitigen p-Wert liefern."""
    ergebnis = page_trend([[3.0, 2.0, 1.0]] * 4)
    assert ergebnis.p_wert > 0.9


def test_friedman_verlangt_mindestens_drei_gruppen() -> None:
    """Mit zwei Gruppen ist der Friedman-Test nicht definiert."""
    with pytest.raises(AuswertungsFehler, match="mindestens 3 Gruppen"):
        friedman([[1.0, 2.0]] * 5)


# ---------------------------------------------------------------------------
# Spearman
# ---------------------------------------------------------------------------


def test_spearman_ist_eins_bei_monotonem_zusammenhang() -> None:
    """Eine streng monoton steigende Beziehung ergibt rho = 1."""
    ergebnis = spearman([0.01, 0.02, 0.05, 0.10], [0.3, 0.4, 0.6, 0.8])
    assert ergebnis.statistik == pytest.approx(1.0)
    assert ergebnis.effektmass == "Spearmans rho"


# ---------------------------------------------------------------------------
# Holm-Bonferroni
# ---------------------------------------------------------------------------


def test_holm_gegen_handrechnung() -> None:
    """Drei p-Werte, aufsteigend mit den Faktoren 3, 2, 1 multipliziert.

    Handrechnung: 0,01*3 = 0,03; 0,02*2 = 0,04; 0,03*1 = 0,03. Das laufende
    Maximum macht daraus 0,03; 0,04; 0,04 — ein spaeterer Vergleich darf nie
    einen kleineren korrigierten Wert bekommen als ein frueherer.
    """
    assert holm([0.01, 0.02, 0.03]) == pytest.approx((0.03, 0.04, 0.04))


def test_holm_erhaelt_die_eingabereihenfolge() -> None:
    """Die Rueckgabe steht in derselben Reihenfolge wie die Eingabe."""
    assert holm([0.03, 0.01, 0.02]) == pytest.approx((0.04, 0.03, 0.04))


def test_holm_deckelt_bei_eins() -> None:
    """Kein korrigierter p-Wert wird groesser als eins."""
    korrigiert = holm([0.4, 0.5, 0.6])
    assert all(wert <= 1.0 for wert in korrigiert)
    assert korrigiert[0] == pytest.approx(1.0)


def test_holm_weist_werte_ausserhalb_des_intervalls_zurueck() -> None:
    """Ein p-Wert ausserhalb von [0, 1] ist ein Fehler, kein Grenzfall."""
    with pytest.raises(AuswertungsFehler, match=r"\[0, 1\]"):
        holm([0.5, 1.5])


def test_holm_auf_leerer_familie() -> None:
    """Eine leere Familie ergibt eine leere Rueckgabe."""
    assert holm([]) == ()


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


def test_bootstrap_ist_reproduzierbar() -> None:
    """Zwei Aufrufe mit denselben Angaben liefern dasselbe Intervall."""
    werte = [0.80, 0.82, 0.79, 0.85, 0.81, 0.83, 0.80, 0.84, 0.78, 0.86]
    erstes = bootstrap_ci(werte, resamples=500, seed=7, gruppe="F3|recall")
    zweites = bootstrap_ci(werte, resamples=500, seed=7, gruppe="F3|recall")
    assert erstes == zweites


def test_bootstrap_gruppen_bekommen_verschiedene_ziehungen() -> None:
    """Zwei Gruppen mit denselben Werten bekommen nicht dieselben Ziehungen.

    Waeren die Ziehungsindizes gleich, waeren die Intervalle benachbarter Gruppen
    kuenstlich gleichfoermig — der Bootstrap wuerde dieselbe Zufallsfolge
    wiederverwenden.
    """
    werte = [0.80, 0.82, 0.79, 0.85, 0.81, 0.83, 0.80, 0.84, 0.78, 0.86]
    erstes = bootstrap_ci(werte, resamples=500, seed=7, gruppe="F3|recall")
    zweites = bootstrap_ci(werte, resamples=500, seed=7, gruppe="F4|recall")
    assert erstes.punkt == pytest.approx(zweites.punkt)
    assert (erstes.unten, erstes.oben) != (zweites.unten, zweites.oben)


def test_bootstrap_intervall_enthaelt_den_punktschaetzer() -> None:
    """Das Intervall schliesst den Mittelwert ein."""
    werte = [0.60, 0.65, 0.62, 0.70, 0.58, 0.66, 0.61, 0.69, 0.63, 0.64]
    intervall = bootstrap_ci(werte, resamples=2000, seed=7, gruppe="probe")
    assert intervall.art is Intervallart.BCA
    assert intervall.unten <= intervall.punkt <= intervall.oben


def test_bootstrap_entartet_weicht_auf_clopper_pearson_aus() -> None:
    """Konstante Werte: der Bootstrap entartet, Clopper-Pearson uebernimmt.

    Das ist der Erwartungsfall bei den Held-out-Klassen mit Recall null. Die
    obere Grenze ist die exakte Clopper-Pearson-Grenze fuer 0 von 4.000, also
    ``1 - (alpha/2)**(1/n)``; sie ist positiv und **kein** Punkt.
    """
    intervall = bootstrap_ci([0.0] * 20, seed=7, anteil=(0, 4000), gruppe="HO2|recall")
    assert intervall.art is Intervallart.CLOPPER_PEARSON
    assert intervall.unten == 0.0
    assert intervall.oben == pytest.approx(1 - (0.025) ** (1 / 4000), rel=1e-6)
    assert "entartet" in intervall.hinweis


def test_bootstrap_entartet_ohne_anteilszahlen_wird_zum_punkt() -> None:
    """Ohne Anteilszahlen bleibt ein Punktintervall — mit sichtbarem Vermerk."""
    intervall = bootstrap_ci([0.25] * 12, seed=7, gruppe="probe")
    assert intervall.art is Intervallart.ENTARTET
    assert (intervall.unten, intervall.punkt, intervall.oben) == (0.25, 0.25, 0.25)
    assert intervall.hinweis


def test_bootstrap_weist_leere_folge_zurueck() -> None:
    """Eine leere Wertefolge ist ein Fehler, kein leeres Intervall."""
    with pytest.raises(AuswertungsFehler, match="leer"):
        bootstrap_ci([])


# ---------------------------------------------------------------------------
# ART-ANOVA
# ---------------------------------------------------------------------------


def test_art_anova_findet_eine_klare_interaktion() -> None:
    """Eine gekreuzte Interaktion wird gefunden.

    Aufbau: Verfahren A ist bei Klasse X gut und bei Klasse Y schlecht, Verfahren
    B umgekehrt. Die Haupteffekte sind damit null, die Interaktion maximal.
    """
    werte: list[float] = []
    verfahren: list[str] = []
    klassen: list[str] = []
    for nummer in range(8):
        stoerung = nummer * 0.001
        for name, klasse, wert in (
            ("A", "X", 0.9),
            ("A", "Y", 0.1),
            ("B", "X", 0.1),
            ("B", "Y", 0.9),
        ):
            werte.append(wert + stoerung)
            verfahren.append(name)
            klassen.append(klasse)
    ergebnis = art_anova_interaktion(werte, verfahren, klassen)
    assert ergebnis.p_wert < 0.001
    assert ergebnis.effekt is not None
    assert ergebnis.effekt > 0.5


def test_art_anova_findet_keine_interaktion_wo_keine_ist() -> None:
    """Rein additive Daten ergeben keinen signifikanten Interaktionsterm."""
    werte: list[float] = []
    verfahren: list[str] = []
    klassen: list[str] = []
    for nummer in range(8):
        stoerung = (nummer % 4) * 0.01
        for name, versatz_a in (("A", 0.0), ("B", 0.2)):
            for klasse, versatz_b in (("X", 0.0), ("Y", 0.3)):
                werte.append(0.4 + versatz_a + versatz_b + stoerung)
                verfahren.append(name)
                klassen.append(klasse)
    ergebnis = art_anova_interaktion(werte, verfahren, klassen)
    assert ergebnis.p_wert > 0.05


def test_art_anova_verlangt_besetzte_zellen() -> None:
    """Eine leere Faktorkombination macht den Interaktionsterm unschaetzbar."""
    with pytest.raises(AuswertungsFehler, match="besetzt"):
        art_anova_interaktion(
            [1.0, 2.0, 3.0], ["A", "A", "B"], ["X", "Y", "X"]
        )


# ---------------------------------------------------------------------------
# Warnung zur Stichprobengroesse
# ---------------------------------------------------------------------------


def test_seed_warnung_nennt_die_richtigen_zahlen() -> None:
    """Bei zehn Wiederholungen stimmen die Grenzen des exakten Tests.

    Handrechnung: kleinster erreichbarer zweiseitiger p-Wert 2/2**10 = 0,001953;
    zweitkleinster 4/2**10 = 0,003906. Nach Holm ueber 7 Vergleiche werden daraus
    0,01367 und (mit dem Faktor 6) 0,02344 — beide signifikant. Ueber 21
    Vergleiche werden daraus 0,04102 (signifikant) und 0,07813 (nicht mehr).
    """
    text = seed_warnung(10, {"HYP1-Recall": 7, "HYP2-paarweise": 21})
    assert "0.00195" in text
    assert "0.00391" in text
    assert "0.0137 (signifikant)" in text
    assert "0.0234 (signifikant)" in text
    assert "0.0410 (signifikant)" in text
    assert "0.0781 (nicht signifikant)" in text


def test_seed_warnung_schweigt_bei_genug_wiederholungen() -> None:
    """Bei zwanzig Wiederholungen gibt es nichts zu warnen."""
    assert seed_warnung(20, {"HYP1-Recall": 7}) == ""
