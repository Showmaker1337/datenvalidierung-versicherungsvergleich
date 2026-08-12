"""Duplikate sind nur auf der Satzebene messbar — auf der Zellebene gar nicht.

Bei F6 (exaktes Duplikat mit Konfliktwerten) und HO1 (semantisches Duplikat) fuegt
der Injektor eine **Zeile** hinzu. Ein zellweises Diff ist dort undefiniert: Es
gibt keine saubere Vorgaengerzelle, gegen die man vergleichen koennte
(``spec/03_fehlerklassen.md``, Abschnitt 4.2). Der Fehler ist eine Eigenschaft des
Zeilenpaares, und protokolliert wird er im ``error_log_records``, nicht im
``error_log``.

Fuer die Auswertung folgt daraus zweierlei, und beides wird hier belegt. Erstens:
Auf der Zellebene haben diese Klassen ``n = 0`` — sie tauchen in der Tabelle auf,
aber ohne Wahrheitseinheit. Ein Recall von null waere dort kein Befund ueber den
Katalog, sondern ueber die Ebene, und ``n`` macht den Unterschied sichtbar.
Zweitens: Auf der Satzebene zaehlen **beide** Partner des Paares. Keine Regel kann
sagen, welche der beiden Zeilen die hinzugefuegte ist; wuerde nur eine als
Wahrheit gefuehrt, produzierte jede korrekt arbeitende Duplikatregel je Paar genau
ein garantiertes False Positive.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.evaluation.modell import Ebene
from src.evaluation.pipeline import bewerte
from tests.test_evaluation import (
    Satzverfahren,
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

#: Zwei Duplikatpaare: ein exaktes (F6) und ein semantisches (HO1).
DUPLIKATE = (
    ("person", "F6", "F6-a", (1, 2)),
    ("person", "HO1", "HO1-a", (3, 4)),
)

#: Zwei Satzbefunde, die genau diese vier Zeilen benennen.
DUPLIKATBEFUNDE = (
    ("person", "R-043", "R-043#000001", (1, 2)),
    ("person", "R-045", "R-045#000001", (3, 4)),
)


def test_zellebene_schliesst_duplikatklassen_aus(config: Config) -> None:
    """F6 und HO1 haben auf der Zellebene keine einzige Wahrheitseinheit.

    Die Klassen bleiben in der Tabelle sichtbar, tragen dort aber ``n = 0``. Genau
    diese Unterscheidung rettet die Interpretation: Ein Recall von null bei
    ``n = 0`` ist keine Aussage ueber den Katalog.
    """
    daten_dirty = daten(6)
    gt = wahrheit(daten_dirty, saetze=DUPLIKATE)

    ergebnis = bewerte(
        [Satzverfahren((), DUPLIKATBEFUNDE)], kontext(config, daten_dirty), gt, messe_speicher=False
    )[0]
    zellebene = ebene_von(ergebnis, Ebene.ZELLE)

    assert gruppe_von(zellebene.recall_je_klasse, "F6").n == 0
    assert gruppe_von(zellebene.recall_je_klasse, "HO1").n == 0
    assert kennzahlen_von(ergebnis, Ebene.ZELLE).konfusion.tp == 0
    assert zellebene.macro_recall_klassen is None


def test_satzebene_erfasst_beide_partner_jedes_duplikatpaares(config: Config) -> None:
    """Auf der Satzebene tragen F6 und HO1 je zwei Wahrheitszeilen, und beide werden gefunden.

    Das Gegenstueck zum vorigen Test: dieselbe Wahrheit, dieselben Meldungen, aber
    eine Ebene, auf der die Einheit zur Fehlerklasse passt.
    """
    daten_dirty = daten(6)
    gt = wahrheit(daten_dirty, saetze=DUPLIKATE)

    ergebnis = bewerte(
        [Satzverfahren((), DUPLIKATBEFUNDE)], kontext(config, daten_dirty), gt, messe_speicher=False
    )[0]
    satzebene = ebene_von(ergebnis, Ebene.SATZ)
    konfusion = kennzahlen_von(ergebnis, Ebene.SATZ).konfusion

    assert gruppe_von(satzebene.recall_je_klasse, "F6").n == 2
    assert gruppe_von(satzebene.recall_je_klasse, "F6").recall == 1.0
    assert gruppe_von(satzebene.recall_je_klasse, "HO1").n == 2
    assert (konfusion.tp, konfusion.fp, konfusion.fn, konfusion.tn) == (4, 0, 0, 2)
    assert satzebene.macro_recall_klassen == 1.0


def test_ohne_satzkanal_bleibt_das_duplikat_unentdeckt(config: Config) -> None:
    """Ein Verfahren ohne satzbezogene Meldungen findet kein einziges Duplikat.

    Belegt, dass die Satzebene ihre Treffer wirklich aus dem zweiten Kanal zieht
    und nicht aus einer Nachsicht der Auswertung. Fuer B0 und B2 ist das die
    gemessene Obergrenze bei F6 und HO1.
    """
    daten_dirty = daten(6)
    gt = wahrheit(daten_dirty, saetze=DUPLIKATE)

    ohne_satzkanal = Zellverfahren(())

    ergebnis = bewerte([ohne_satzkanal], kontext(config, daten_dirty), gt, messe_speicher=False)[0]
    konfusion = kennzahlen_von(ergebnis, Ebene.SATZ).konfusion

    assert (konfusion.tp, konfusion.fp, konfusion.fn) == (0, 0, 4)
    assert kennzahlen_von(ergebnis, Ebene.SATZ).recall == 0.0


def test_markierte_zelle_hebt_ihre_zeile_auf_die_satzebene(config: Config) -> None:
    """Eine markierte Zelle macht ihre Zeile auch auf der Satzebene zur Meldung.

    Die Satzebene ist die Vereinigung aus den Zeilen der markierten Zellen und den
    satzbezogenen Meldungen. Ohne den ersten Teil waere ein zellgenaues Verfahren
    auf der Satzebene grundlos blind.
    """
    daten_dirty = daten(6)
    gt = wahrheit(
        daten_dirty,
        zellen=[("person", 5, "plz", "F3", "F3-b", False)],
        saetze=DUPLIKATE,
    )
    meldungen = (("person", 5, "plz", "R-011", "R-011#000001"),)

    ergebnis = bewerte(
        [Zellverfahren(meldungen)], kontext(config, daten_dirty), gt, messe_speicher=False
    )[0]
    satzebene = ebene_von(ergebnis, Ebene.SATZ)
    konfusion = kennzahlen_von(ergebnis, Ebene.SATZ).konfusion

    assert (konfusion.tp, konfusion.fp, konfusion.fn) == (1, 0, 4)
    assert gruppe_von(satzebene.recall_je_klasse, "F3").recall == 1.0
    assert gruppe_von(satzebene.recall_je_klasse, "F6").recall == 0.0
