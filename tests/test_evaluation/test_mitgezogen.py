"""Mitgezogene Zellen als Schalter: derselbe Lauf, zwei Recalls.

Skaliert der Injektor den Beitrag eines Angebots (F8), aendert sich die Reihenfolge
der Angebote einer Anfrage. Der Injektor fuehrt ``angebot.rang`` deshalb nach und
protokolliert diese Zellen mit ``mitgezogen = True``. Gegenueber den verfaelschten
Daten sind sie **korrekt**: Der nachgefuehrte Rang passt zum verfaelschten Beitrag.
Ein Verfahren, das sie nicht meldet, macht keinen Fehler.

Deshalb ist ``mitgezogen_als_fehler`` ein Schalter und keine im Quelltext
versteckte Entscheidung. Die Hauptauswertung der Arbeit steht auf ``False``, die
Sensitivitaetsrechnung im Anhang auf ``True``. Zwei Zahlen nebeneinander beenden
die Diskussion; eine Zahl allein eroeffnet sie.

Belegt wird hier, dass die Differenz **genau** dort entsteht, wo sie hingehoert:
im Nenner des Recalls. Der Zaehler bleibt gleich — es wurde nichts zusaetzlich
gefunden —, der Nenner waechst um die Zahl der mitgezogenen Zellen. Und in die
Gegenrichtung: Wer die mitgezogenen Zellen doch meldet, verliert bei ``False``
Precision, weil sie dort Fehlalarme sind.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from src.evaluation.modell import Ebene
from src.evaluation.pipeline import bewerte
from tests.test_evaluation import (
    Zellverfahren,
    daten,
    ebene_von,
    gruppe_von,
    kennzahlen_von,
    kontext,
    wahrheit,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from src.common.config import Config

#: Zwei skalierte Beitraege und zwei deswegen nachgefuehrte Raenge.
F8_ZELLEN = (
    ("angebot", 1, "nettobeitrag_jahr_eur", "F8", "F8-a", False),
    ("angebot", 2, "nettobeitrag_jahr_eur", "F8", "F8-a", False),
    ("angebot", 3, "rang", "F8", "F8-a", True),
    ("angebot", 4, "rang", "F8", "F8-a", True),
)

#: Ein Verfahren, das genau die beiden echten Verfaelschungen findet.
ECHTE_TREFFER = (
    ("angebot", 1, "nettobeitrag_jahr_eur", "R-031", "R-031#000001"),
    ("angebot", 2, "nettobeitrag_jahr_eur", "R-031", "R-031#000002"),
)


def test_mitgezogene_zellen_senken_den_recall(config: Config) -> None:
    """Mit ``mitgezogen_als_fehler=True`` faellt der Recall von 1,0 auf 0,5.

    Der Zaehler bleibt bei zwei Treffern; nur der Ground Truth waechst von zwei
    auf vier Zellen. Genau diese Verschiebung ist die Sensitivitaetsrechnung des
    Anhangs.
    """
    daten_dirty = daten(4, entitaet="angebot")
    gt = wahrheit(daten_dirty, zellen=F8_ZELLEN)

    ergebnis = bewerte(
        [Zellverfahren(ECHTE_TREFFER)], kontext(config, daten_dirty), gt, messe_speicher=False
    )[0]
    ohne = kennzahlen_von(ergebnis, Ebene.ZELLE, mitgezogen=False)
    mit = kennzahlen_von(ergebnis, Ebene.ZELLE, mitgezogen=True)

    assert mit.recall < ohne.recall
    assert ohne.recall == 1.0
    assert mit.recall == pytest.approx(0.5)
    assert (ohne.konfusion.tp, ohne.konfusion.fn) == (2, 0)
    assert (mit.konfusion.tp, mit.konfusion.fn) == (2, 2)


def test_die_differenz_steckt_genau_im_nenner(config: Config) -> None:
    """Der Recall mit Schalter ist ``tp / (n_ohne + Zahl der mitgezogenen Zellen)``.

    Die woertliche Pruefung der Festlegung: Es wird nichts zusaetzlich gefunden
    und nichts zusaetzlich als Fehlalarm gewertet — der Ground Truth waechst, und
    zwar um exakt die mitgezogenen Zellen.
    """
    daten_dirty = daten(4, entitaet="angebot")
    gt = wahrheit(daten_dirty, zellen=F8_ZELLEN)
    mitgezogene = sum(1 for zelle in gt.zellen if zelle.mitgezogen)

    ergebnis = bewerte(
        [Zellverfahren(ECHTE_TREFFER)], kontext(config, daten_dirty), gt, messe_speicher=False
    )[0]
    ohne = gruppe_von(ebene_von(ergebnis, Ebene.ZELLE).recall_je_klasse, "F8")
    mit = gruppe_von(ebene_von(ergebnis, Ebene.ZELLE, mitgezogen=True).recall_je_klasse, "F8")

    assert mitgezogene == 2
    assert mit.n == ohne.n + mitgezogene
    assert mit.tp == ohne.tp
    assert mit.recall == pytest.approx(mit.tp / (ohne.n + mitgezogene))


def test_gemeldete_mitgezogene_zellen_sind_ohne_schalter_fehlalarme(config: Config) -> None:
    """Wer die nachgefuehrten Raenge meldet, verliert bei ``False`` Precision.

    Die Gegenrichtung desselben Schalters, und der Grund, warum beide Zahlen
    berichtet werden: Bei ``True`` sieht dasselbe Verfahren fehlerfrei aus. Welche
    der beiden Lesarten gilt, ist eine methodische Festlegung und darf nicht im
    Quelltext verschwinden.
    """
    daten_dirty = daten(4, entitaet="angebot")
    gt = wahrheit(daten_dirty, zellen=F8_ZELLEN)
    meldungen = (
        *ECHTE_TREFFER,
        ("angebot", 3, "rang", "R-030", "R-030#000001"),
        ("angebot", 4, "rang", "R-030", "R-030#000002"),
    )

    ergebnis = bewerte(
        [Zellverfahren(meldungen)], kontext(config, daten_dirty), gt, messe_speicher=False
    )[0]
    ohne = kennzahlen_von(ergebnis, Ebene.ZELLE, mitgezogen=False)
    mit = kennzahlen_von(ergebnis, Ebene.ZELLE, mitgezogen=True)

    assert (ohne.konfusion.tp, ohne.konfusion.fp) == (2, 2)
    assert ohne.precision == pytest.approx(0.5)
    assert (mit.konfusion.tp, mit.konfusion.fp) == (4, 0)
    assert mit.precision == 1.0
    assert mit.recall == 1.0


def test_der_schalter_wirkt_auch_auf_der_satzebene(config: Config) -> None:
    """Zeilen, die ihren Eintrag nur mitgezogenen Zellen verdanken, entfallen bei ``False``.

    Die Satzwahrheit erbt die Regel von der Zellwahrheit: Eine Zeile gilt nur dann
    als mitgezogen, wenn **alle** ihre Logzellen mitgezogen sind. Die beiden
    nachgefuehrten Rangzeilen erfuellen das und zaehlen deshalb ohne Schalter
    nicht als uebersehen.
    """
    daten_dirty = daten(4, entitaet="angebot")
    gt = wahrheit(daten_dirty, zellen=F8_ZELLEN)

    ergebnis = bewerte(
        [Zellverfahren(ECHTE_TREFFER)], kontext(config, daten_dirty), gt, messe_speicher=False
    )[0]
    ohne = kennzahlen_von(ergebnis, Ebene.SATZ, mitgezogen=False)
    mit = kennzahlen_von(ergebnis, Ebene.SATZ, mitgezogen=True)

    assert (ohne.konfusion.tp, ohne.konfusion.fp, ohne.konfusion.fn) == (2, 0, 0)
    assert (mit.konfusion.tp, mit.konfusion.fp, mit.konfusion.fn) == (2, 0, 2)
