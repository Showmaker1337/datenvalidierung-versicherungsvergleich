"""Die Constraint-Ebene repariert die strukturelle Deckelung der Precision.

Eine Regel ueber mehrere Felder meldet **alle** beteiligten Zellen. R-031 prueft
die Beziehung zwischen Nettobeitrag, Versicherungsteuer und Bruttobeitrag und
nennt deshalb drei Zellen; der Injektor hat aber nur eine davon verfaelscht. Streng
zellbasiert ergibt perfekte Erkennung damit einen Treffer und zwei Fehlalarme —
eine Precision von einem Drittel als Artefakt der Berichtskonvention, nicht des
Detektors.

Die Constraint-Ebene wechselt dafuer die Einheit: gezaehlt wird die
``verstoss_id``, und ein Verstoss ist ein Treffer, sobald **mindestens eine**
seiner Zellen im Ground Truth liegt. Der Recall bleibt zellbasiert, denn die Frage
der Arbeit lautet, ob jeder injizierte Fehler gefunden wird. Dieser Einheitenbruch
ist Absicht und wird hier mitgeprueft: ``fn`` muss auf beiden Ebenen dieselbe Zahl
sein, und ``tn`` muss auf der Constraint-Ebene ``None`` bleiben — es gibt keine
abzaehlbare Menge nicht erkannter Verstoesse.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from src.evaluation.modell import Ebene
from src.evaluation.pipeline import bewerte
from tests.test_evaluation import Zellverfahren, daten, kennzahlen_von, kontext, wahrheit

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from src.common.config import Config

#: Ein dreispaltiger Verstoss auf einer Zeile, wie ihn R-031 meldet.
BEITRAGSVERSTOSS = (
    ("angebot", 1, "nettobeitrag_jahr_eur", "R-031", "R-031#000001"),
    ("angebot", 1, "versicherungsteuer_eur", "R-031", "R-031#000001"),
    ("angebot", 1, "bruttobeitrag_jahr_eur", "R-031", "R-031#000001"),
)

#: Die einzige tatsaechlich verfaelschte Zelle dieses Verstosses.
VERFAELSCHTE_ZELLE = ("angebot", 1, "versicherungsteuer_eur", "F5", "F5-a", False)


def test_dreispaltiger_verstoss_ergibt_zellbasiert_ein_tp_und_zwei_fp(config: Config) -> None:
    """Zellbasiert liefert der Verstoss einen Treffer und zwei Fehlalarme.

    Das ist die Deckelung, um die es geht: Die Precision liegt bei einem Drittel,
    obwohl der Detektor genau den richtigen Datensatz beanstandet hat.
    """
    daten_dirty = daten(2, entitaet="angebot")
    gt = wahrheit(daten_dirty, zellen=[VERFAELSCHTE_ZELLE])

    ergebnis = bewerte(
        [Zellverfahren(BEITRAGSVERSTOSS)], kontext(config, daten_dirty), gt, messe_speicher=False
    )[0]
    werte = kennzahlen_von(ergebnis, Ebene.ZELLE)

    assert (werte.konfusion.tp, werte.konfusion.fp, werte.konfusion.fn) == (1, 2, 0)
    assert werte.precision == pytest.approx(1 / 3)
    assert werte.recall == 1.0


def test_derselbe_verstoss_ergibt_constraintbasiert_ein_tp_und_kein_fp(config: Config) -> None:
    """Constraint-basiert ist derselbe Befund ein Treffer ohne Fehlalarm.

    Der eigentliche Zweck der Ebene. Die beiden Zahlen nebeneinander zeigen, wie
    viel der zellbasierten Precision auf die Berichtskonvention entfaellt.
    """
    daten_dirty = daten(2, entitaet="angebot")
    gt = wahrheit(daten_dirty, zellen=[VERFAELSCHTE_ZELLE])

    ergebnis = bewerte(
        [Zellverfahren(BEITRAGSVERSTOSS)], kontext(config, daten_dirty), gt, messe_speicher=False
    )[0]
    werte = kennzahlen_von(ergebnis, Ebene.CONSTRAINT)

    assert (werte.konfusion.tp, werte.konfusion.fp, werte.konfusion.fn) == (1, 0, 0)
    assert werte.precision == 1.0


def test_constraint_ebene_fuehrt_kein_tn(config: Config) -> None:
    """``tn``, MCC und die Fehlalarmrate bleiben auf der Constraint-Ebene ``None``.

    Es gibt keine abzaehlbare Menge nicht erkannter Verstoesse. Eine Null waere an
    dieser Stelle eine Behauptung, die niemand belegen kann; ``None`` faellt in
    jeder Tabelle auf.
    """
    daten_dirty = daten(2, entitaet="angebot")
    gt = wahrheit(daten_dirty, zellen=[VERFAELSCHTE_ZELLE])

    ergebnis = bewerte(
        [Zellverfahren(BEITRAGSVERSTOSS)], kontext(config, daten_dirty), gt, messe_speicher=False
    )[0]
    werte = kennzahlen_von(ergebnis, Ebene.CONSTRAINT)

    assert werte.konfusion.tn is None
    assert werte.konfusion.grundgesamtheit is None
    assert werte.mcc is None
    assert werte.fpr_clean is None


def test_verstoss_ohne_verfaelschte_zelle_bleibt_ein_fehlalarm(config: Config) -> None:
    """Ein Verstoss, von dem keine Zelle im Ground Truth liegt, zaehlt als Fehlalarm.

    Sonst waere die Constraint-Ebene keine Reparatur, sondern eine Amnestie: Die
    Precision stiege auch dort, wo ein Verfahren tatsaechlich danebengegriffen hat.
    """
    daten_dirty = daten(2, entitaet="angebot")
    gt = wahrheit(daten_dirty, zellen=[VERFAELSCHTE_ZELLE])
    meldungen = (
        *BEITRAGSVERSTOSS,
        ("angebot", 2, "nettobeitrag_jahr_eur", "R-031", "R-031#000002"),
        ("angebot", 2, "versicherungsteuer_eur", "R-031", "R-031#000002"),
        ("angebot", 2, "bruttobeitrag_jahr_eur", "R-031", "R-031#000002"),
    )

    ergebnis = bewerte(
        [Zellverfahren(meldungen)], kontext(config, daten_dirty), gt, messe_speicher=False
    )[0]
    constraint = kennzahlen_von(ergebnis, Ebene.CONSTRAINT)
    zelle = kennzahlen_von(ergebnis, Ebene.ZELLE)

    assert (constraint.konfusion.tp, constraint.konfusion.fp) == (1, 1)
    assert constraint.precision == 0.5
    assert (zelle.konfusion.tp, zelle.konfusion.fp) == (1, 5)


def test_uebersehene_zelle_zaehlt_auf_beiden_ebenen_gleich(config: Config) -> None:
    """``fn`` bleibt zellbasiert und ist auf beiden Ebenen dieselbe Zahl.

    Genau hier sitzt der Einheitenbruch, den der Modul-Docstring der Metriken
    offenlegt: Nur die Precision wechselt die Einheit, der Recall nicht. Waere
    auch ``fn`` constraint-basiert, koennte ein Verfahren seinen Recall heben,
    indem es weniger Verstoesse mit mehr Zellen meldet.
    """
    daten_dirty = daten(2, entitaet="angebot")
    gt = wahrheit(
        daten_dirty,
        zellen=[VERFAELSCHTE_ZELLE, ("angebot", 2, "rang", "F8", "F8-a", False)],
    )

    ergebnis = bewerte(
        [Zellverfahren(BEITRAGSVERSTOSS)], kontext(config, daten_dirty), gt, messe_speicher=False
    )[0]
    constraint = kennzahlen_von(ergebnis, Ebene.CONSTRAINT)
    zelle = kennzahlen_von(ergebnis, Ebene.ZELLE)

    assert constraint.konfusion.fn == zelle.konfusion.fn == 1
    assert constraint.recall == zelle.recall == pytest.approx(0.5)


def test_ein_verstoss_ueber_zwei_wahrheitszellen_senkt_den_recall_nicht(config: Config) -> None:
    """Ein Verstoss, der zwei injizierte Zellen zugleich ueberdeckt, zaehlt zweimal.

    Der Fall ist bei F8 der Regelfall: Die kohaerente Skalierung trifft mehrere
    Beitragsfelder derselben Zeile, und R-031 meldet sie in **einem** Verstoss.
    Wuerde der Recall aus der Verstosszahl gebildet, zaehlte dieser eine Verstoss
    einmal statt zweimal, und der Constraint-Recall fiele auf 0,5, waehrend die
    Zellebene und die Gruppentabellen derselben Auswertung 2/3 berichten. In
    **einer** ``metrics.json`` stuenden dann zwei Zahlen unter dem Namen ``recall``.
    """
    daten_dirty = daten(2, entitaet="angebot")
    gt = wahrheit(
        daten_dirty,
        zellen=[
            ("angebot", 1, "nettobeitrag_jahr_eur", "F8", "F8-b", False),
            ("angebot", 1, "bruttobeitrag_jahr_eur", "F8", "F8-b", False),
            ("angebot", 2, "zahlbeitrag_rate_eur", "F8", "F8-b", False),
        ],
    )

    ergebnis = bewerte(
        [Zellverfahren(BEITRAGSVERSTOSS)], kontext(config, daten_dirty), gt, messe_speicher=False
    )[0]
    constraint = kennzahlen_von(ergebnis, Ebene.CONSTRAINT)
    zelle = kennzahlen_von(ergebnis, Ebene.ZELLE)

    assert (constraint.konfusion.tp, constraint.konfusion.fp) == (1, 0)
    assert constraint.konfusion.tp_recall == 2
    assert constraint.recall == zelle.recall == pytest.approx(2 / 3)


def test_zwei_regeln_auf_derselben_zelle_heben_den_recall_nicht(config: Config) -> None:
    """Zwei Verstoesse auf **einer** injizierten Zelle zaehlen fuer den Recall einmal.

    Der Datums-Sentinel loest R-009 und R-025 gleichzeitig aus. Wuerde der Recall
    aus der Verstosszahl gebildet, zaehlte dieselbe gefundene Zelle zweimal und der
    Constraint-Recall stiege auf 2/3, obwohl nur einer von zwei injizierten Fehlern
    gefunden wurde. Das waere genau die Doppelzaehlung, die die Vereinigungsmenge
    aus Festlegung 1 ausschliesst — hier durch die Hintertuer der Ebenenrechnung.
    """
    daten_dirty = daten(2, entitaet="angebot")
    gt = wahrheit(
        daten_dirty,
        zellen=[
            VERFAELSCHTE_ZELLE,
            ("angebot", 2, "rang", "F8", "F8-a", False),
        ],
    )
    doppelmeldung = (
        ("angebot", 1, "versicherungsteuer_eur", "R-009", "R-009#000001"),
        ("angebot", 1, "versicherungsteuer_eur", "R-025", "R-025#000001"),
    )

    ergebnis = bewerte(
        [Zellverfahren(doppelmeldung)], kontext(config, daten_dirty), gt, messe_speicher=False
    )[0]
    constraint = kennzahlen_von(ergebnis, Ebene.CONSTRAINT)
    zelle = kennzahlen_von(ergebnis, Ebene.ZELLE)

    assert (constraint.konfusion.tp, constraint.konfusion.fp) == (2, 0)
    assert constraint.konfusion.tp_recall == 1
    assert constraint.recall == zelle.recall == pytest.approx(0.5)
