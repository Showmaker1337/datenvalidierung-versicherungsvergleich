"""Kennzahlen gegen handgerechnete Konfusionsmatrizen.

Jede Zahl in diesem Modul ist auf Papier nachrechenbar und steht als Rechnung im
Docstring oder im Kommentar daneben. Das ist Absicht: Die Metrik ist der Teil des
Prototyps, der nicht durch einen Blick auf die Ausgabe plausibilisierbar ist —
eine Precision von 0,63 sieht richtig aus, egal ob sie es ist. Belegt wird
deshalb nicht "die Funktion laeuft", sondern "die Funktion liefert genau diesen
Wert, und der Wert folgt aus dieser Formel".

Besonderes Gewicht liegt auf den Randfaellen, weil dort die dokumentierten
**Wahlentscheidungen** der Arbeit sitzen (``src/evaluation/metriken.py``,
Abschnitt 7): ``|T(D)| = 0`` ergibt Precision ``0.0`` und nicht ``1.0``,
``|E| = 0`` ergibt Recall ``0.0``, MCC ist ``0.0`` bei entartetem Nenner und
``None`` ohne ``tn``. Diese Zahlen sind keine Nebensache — bei sechzig Varianten
und kleinen Fehlerraten sind leere Gruppen der Normalfall, und eine andere Wahl
verschoebe jeden Macro-Wert der Arbeit.
"""

from __future__ import annotations

import math

import pytest

from src.evaluation.metriken import (
    clopper_pearson,
    f1,
    fpr_clean,
    kennzahlen,
    konfusion_mengen,
    konfusion_zellen,
    mcc,
    pr_auc,
    precision,
    recall,
)
from src.evaluation.modell import AuswertungsFehler, Konfusion

#: Drei verfaelschte Zellen eines gedachten Laufs.
WAHRHEIT = frozenset(
    {
        ("person", 1, "plz"),
        ("person", 2, "ort"),
        ("person", 3, "email"),
    }
)

#: Zelluniversum des gedachten Laufs: hundert Zellen.
UNIVERSUM = 100


# ---------------------------------------------------------------------------
# Konfusionsmatrix der Zellebene
# ---------------------------------------------------------------------------


def test_perfekte_erkennung_ergibt_precision_und_recall_eins() -> None:
    """Wer genau die drei verfaelschten Zellen meldet, erreicht 3/3 und 3/3.

    Der Ankerfall: Ist er falsch, ist jede andere Zahl der Arbeit ebenfalls
    falsch, ohne dass es auffiele.
    """
    konfusion = konfusion_zellen(WAHRHEIT, WAHRHEIT, UNIVERSUM)

    assert (konfusion.tp, konfusion.fp, konfusion.fn) == (3, 0, 0)
    assert konfusion.tn == 97
    assert precision(konfusion) == 1.0
    assert recall(konfusion) == 1.0
    assert f1(precision(konfusion), recall(konfusion)) == 1.0


def test_keine_meldung_ergibt_recall_null_und_drei_fn() -> None:
    """Ein Verfahren ohne jede Meldung uebersieht alle drei Zellen.

    Zugleich der Beleg fuer die dokumentierte Wahl ``|T(D)| = 0`` ergibt
    Precision ``0.0``: ``1.0`` waere eine Belohnung fuers Nichtstun und stuende
    dann in jeder Ergebnistabelle neben einem Recall von null.
    """
    konfusion = konfusion_zellen(frozenset(), WAHRHEIT, UNIVERSUM)

    assert (konfusion.tp, konfusion.fp, konfusion.fn, konfusion.tn) == (0, 0, 3, 97)
    assert recall(konfusion) == 0.0
    assert precision(konfusion) == 0.0
    assert f1(precision(konfusion), recall(konfusion)) == 0.0


def test_gemischte_erkennung_rechnet_von_hand_nach() -> None:
    """Zwei Treffer, ein Fehlalarm, eine uebersehene Zelle ergeben 2/3 und 2/3.

    Precision ``2/(2+1)``, Recall ``2/(2+1)``, F1 als harmonisches Mittel
    ebenfalls ``2/3``, ``tn = 100 - 2 - 1 - 1 = 96``.
    """
    markiert = frozenset({("person", 1, "plz"), ("person", 2, "ort"), ("person", 4, "strasse")})

    konfusion = konfusion_zellen(markiert, WAHRHEIT, UNIVERSUM)
    werte = kennzahlen(konfusion)

    assert (konfusion.tp, konfusion.fp, konfusion.fn, konfusion.tn) == (2, 1, 1, 96)
    assert werte.precision == pytest.approx(2 / 3)
    assert werte.recall == pytest.approx(2 / 3)
    assert werte.f1 == pytest.approx(2 / 3)


def test_leerer_ground_truth_ergibt_recall_null_und_lauter_fehlalarme() -> None:
    """Ohne verfaelschte Zelle ist jede Meldung ein Fehlalarm und der Recall null.

    Der Fall ist keine Spitzfindigkeit: Genau so sieht der Clean-Baseline-Lauf
    aus, und dort ist ``fp`` die einzige interessante Zahl.
    """
    markiert = frozenset({("person", 1, "plz"), ("person", 2, "ort")})

    konfusion = konfusion_zellen(markiert, frozenset(), UNIVERSUM)

    assert (konfusion.tp, konfusion.fp, konfusion.fn, konfusion.tn) == (0, 2, 0, 98)
    assert recall(konfusion) == 0.0
    assert precision(konfusion) == 0.0


def test_leere_mengen_ergeben_beide_kennzahlen_null() -> None:
    """Meldet niemand etwas und ist nichts verfaelscht, sind Precision und Recall null.

    Die Konvention ist nicht schoen, aber sie ist ansteckungsfrei: ``nan`` zoege
    jeden Macro-Mittelwert der Arbeit mit sich.
    """
    konfusion = konfusion_zellen(frozenset(), frozenset(), UNIVERSUM)

    assert (konfusion.tp, konfusion.fp, konfusion.fn, konfusion.tn) == (0, 0, 0, 100)
    assert precision(konfusion) == 0.0
    assert recall(konfusion) == 0.0
    assert f1(precision(konfusion), recall(konfusion)) == 0.0


def test_zu_kleines_universum_bricht_ab() -> None:
    """Ein negatives ``tn`` wird gemeldet statt gerechnet.

    Es kann nur entstehen, wenn Markierungen und Universum aus verschiedenen
    Datensaetzen stammen — dem sauberen und dem verfaelschten etwa. Jede Kennzahl
    darauf waere wertlos, und der Fehler faellt sonst erst in Phase 6 auf.
    """
    with pytest.raises(AuswertungsFehler, match="Grundgesamtheit"):
        konfusion_mengen(WAHRHEIT, WAHRHEIT, 2)


# ---------------------------------------------------------------------------
# MCC
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tp", "fp", "fn", "tn", "erwartet"),
    [
        # (3*3 - 1*1) / sqrt(4*4*4*4) = 8 / 16 = 0.5
        (3, 1, 1, 3, 0.5),
        # (3*3 - 0*0) / sqrt(3*3*3*3) = 9 / 9 = 1.0
        (3, 0, 0, 3, 1.0),
        # (0*0 - 3*3) / sqrt(3*3*3*3) = -9 / 9 = -1.0
        (0, 3, 3, 0, -1.0),
    ],
)
def test_mcc_gegen_handrechnung(tp: int, fp: int, fn: int, tn: int, erwartet: float) -> None:
    """Der MCC trifft die von Hand gerechneten Werte, auch am unteren Rand.

    Der MCC ist die Kennzahl, die in der Arbeit die Accuracy ersetzt; sie muss
    ueber den ganzen Wertebereich stimmen und nicht nur im gutmuetigen Bereich.
    """
    konfusion = Konfusion(tp=tp, fp=fp, fn=fn, tn=tn, grundgesamtheit=tp + fp + fn + tn)

    assert mcc(konfusion) == pytest.approx(erwartet)


def test_mcc_ist_null_bei_entartetem_nenner() -> None:
    """Ist ein Faktor des Nenners null, gilt die Konvention MCC gleich ``0.0``.

    Ohne die Konvention entstuende eine Division durch null — und zwar genau in
    dem haeufigen Fall, dass ein Verfahren auf einem Lauf gar nichts meldet.
    """
    konfusion = Konfusion(tp=0, fp=0, fn=3, tn=97, grundgesamtheit=100)

    assert mcc(konfusion) == 0.0


def test_mcc_ohne_tn_ist_none() -> None:
    """Ohne abzaehlbare negative Klasse gibt es keinen MCC, also ``None``.

    Das ist der Fall der Constraint-Ebene. Eine Null waere dort eine Behauptung
    ueber ein Verfahren, obwohl gar nichts gemessen werden kann.
    """
    konfusion = Konfusion(tp=5, fp=2, fn=1, tn=None, grundgesamtheit=None)

    assert mcc(konfusion) is None


def test_mcc_bleibt_bei_grossem_universum_endlich() -> None:
    """Auch bei einem Universum in Millionenhoehe bleibt der MCC eine echte Zahl.

    Belegt die Entwurfsentscheidung, die vier Faktoren als ``int`` zu bilden: Als
    ``float`` sprengte das Viererprodukt bei realistischen Laufgroessen die
    Mantisse, und das Ergebnis waere still ungenau.
    """
    konfusion = Konfusion(tp=600, fp=400, fn=400, tn=3_000_000, grundgesamtheit=3_001_400)

    wert = mcc(konfusion)

    assert wert is not None
    assert math.isfinite(wert)
    assert 0.0 < wert < 1.0


# ---------------------------------------------------------------------------
# Fehlalarmrate auf den sauberen Zellen
# ---------------------------------------------------------------------------


def test_fpr_clean_bezieht_sich_auf_die_nicht_verfaelschten_zellen() -> None:
    """Der Nenner ist die Grundgesamtheit ohne die verfaelschten Zellen.

    ``|E| = tp + fn = 3``, also ``fp / (100 - 3) = 3/97``. Genau diese
    Bezugsgroesse benutzt auch der Clean-Baseline-Lauf; nur deshalb duerfen beide
    Zahlen in der Arbeit nebeneinander stehen.
    """
    konfusion = Konfusion(tp=2, fp=3, fn=1, tn=94, grundgesamtheit=100)

    assert fpr_clean(konfusion) == pytest.approx(3 / 97)


def test_fpr_clean_ist_null_ohne_saubere_zellen() -> None:
    """War jede Einheit verfaelscht, ist die Rate null statt undefiniert."""
    konfusion = Konfusion(tp=4, fp=0, fn=0, tn=0, grundgesamtheit=4)

    assert fpr_clean(konfusion) == 0.0


def test_fpr_clean_ist_ohne_tn_none() -> None:
    """Ohne ``tn`` ist die Rate nicht bildbar und damit ``None``."""
    konfusion = Konfusion(tp=1, fp=1, fn=1, tn=None, grundgesamtheit=None)

    assert fpr_clean(konfusion) is None


# ---------------------------------------------------------------------------
# Clopper-Pearson
# ---------------------------------------------------------------------------


def test_clopper_pearson_trifft_die_bekannten_randwerte() -> None:
    """Fuer ``k=0, n=5`` und ``k=n=5`` stimmen die Grenzen mit der Literatur ueberein.

    Beide Werte sind geschlossen nachrechenbar: Die Grenze ist ``1 - 0.025**(1/5)``
    beziehungsweise ``0.025**(1/5)``, also rund 0,5218 und 0,4782. Damit ist
    belegt, dass hier das **exakte** Intervall gerechnet wird und nicht die
    Normalapproximation, die bei diesen ``n`` weit danebenliegt.
    """
    ohne_treffer = clopper_pearson(0, 5)
    nur_treffer = clopper_pearson(5, 5)

    assert ohne_treffer[0] == 0.0
    assert ohne_treffer[1] == pytest.approx(1 - 0.025 ** (1 / 5), abs=1e-4)
    assert ohne_treffer[1] == pytest.approx(0.5218, abs=1e-4)
    assert nur_treffer[0] == pytest.approx(0.025 ** (1 / 5), abs=1e-4)
    assert nur_treffer[0] == pytest.approx(0.4782, abs=1e-4)
    assert nur_treffer[1] == 1.0


def test_clopper_pearson_ist_ohne_versuche_voellig_uninformativ() -> None:
    """Bei ``n = 0`` ist das Intervall ``(0, 1)``.

    Der Fall ist der Normalfall einer Variante mit Kontingent null. Ein Intervall
    ``(0, 0)`` waere dort eine Aussage, die niemand gemessen hat.
    """
    assert clopper_pearson(0, 0) == (0.0, 1.0)


def test_clopper_pearson_umschliesst_den_punktschaetzer() -> None:
    """Die Grenzen liegen um den Anteilswert und innerhalb von null und eins."""
    unten, oben = clopper_pearson(2, 10)

    assert 0.0 <= unten <= 0.2 <= oben <= 1.0


def test_clopper_pearson_weist_unmoegliche_eingaben_ab() -> None:
    """Mehr Treffer als Versuche und ein ``alpha`` ausserhalb von (0,1) brechen ab.

    Kein stiller Fallback: Ein ``k > n`` kann nur aus einer falsch gebildeten
    Gruppenzuordnung stammen, und die faerbte sonst nur das Konfidenzintervall
    ein wenig ein.
    """
    with pytest.raises(AuswertungsFehler, match="0 <= k <= n"):
        clopper_pearson(6, 5)
    with pytest.raises(AuswertungsFehler, match="alpha"):
        clopper_pearson(1, 5, alpha=1.5)


# ---------------------------------------------------------------------------
# PR-AUC
# ---------------------------------------------------------------------------


def test_pr_auc_gegen_handrechnung() -> None:
    """Vier Einheiten, zwei davon verfaelscht, ergeben eine Flaeche von 5/6.

    Absteigend nach Score: Treffer, Fehlalarm, Treffer, Fehlalarm. Die
    stufenweise Summation ergibt ``1/1 * 0.5 + 2/3 * 0.5 = 0.8333``. Der Wert
    belegt zugleich, dass hoehere Scores als "anomaler" gelesen werden — mit der
    umgekehrten Orientierung kaeme 0,4167 heraus.
    """
    flaeche = pr_auc([0.9, 0.8, 0.7, 0.6], [True, False, True, False])

    assert flaeche == pytest.approx(5 / 6)


def test_pr_auc_ist_ohne_zwei_klassen_none() -> None:
    """Liegen alle Einheiten in derselben Klasse, gibt es keine Kurve.

    ``None`` statt einer Zahl: Eine Precision-Recall-Kurve ohne positive Einheit
    ist nicht definiert, und jede ausgewiesene Flaeche waere frei erfunden.
    """
    assert pr_auc([0.9, 0.8], [False, False]) is None
    assert pr_auc([], []) is None


def test_pr_auc_weist_ungleich_lange_folgen_ab() -> None:
    """Score- und Wahrheitsfolge muessen gleich lang sein."""
    with pytest.raises(AuswertungsFehler, match="gleich lang"):
        pr_auc([0.9, 0.8], [True])


# ---------------------------------------------------------------------------
# Zusammenbau
# ---------------------------------------------------------------------------


def test_kennzahlen_tragen_die_rohwerte_weiter() -> None:
    """Die Kennzahlen fuehren ihre Konfusionsmatrix mit.

    Das ist die Entwurfsentscheidung, die Phase 6 traegt: Aus abgelegten
    Rohwerten ist eine weitere Kennzahl in Sekunden nachgerechnet, aus fehlenden
    Rohwerten nur durch das Wiederholen tausender Laeufe.
    """
    konfusion = Konfusion(tp=2, fp=1, fn=1, tn=96, grundgesamtheit=100)

    werte = kennzahlen(konfusion, pr_auc=0.75)

    assert werte.konfusion is konfusion
    assert werte.pr_auc == 0.75
    assert werte.mcc == pytest.approx(mcc(konfusion))
    assert werte.fpr_clean == pytest.approx(fpr_clean(konfusion))


def test_kennzahlen_lassen_pr_auc_ohne_score_offen() -> None:
    """Ohne uebergebenen Score bleibt die PR-AUC ``None``.

    Fuer Prototyp, B0 und B3 wird ausdruecklich **kein** Pseudo-Score erfunden;
    sie liefern binaere Entscheidungen und damit genau einen Betriebspunkt.
    """
    werte = kennzahlen(Konfusion(tp=1, fp=1, fn=1, tn=97, grundgesamtheit=100))

    assert werte.pr_auc is None
