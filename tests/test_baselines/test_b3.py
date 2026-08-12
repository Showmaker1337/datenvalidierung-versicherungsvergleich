"""Smoke-Test der Baseline B3 (cuallee) auf einem Minimaldatensatz.

B3 ist der Vergleich gegen ein etabliertes Framework: **derselbe** Regelinhalt
der Gruppe G1, formuliert in einer fremden, deklarativen Check-API. Die tragende
Kennzahl des Vergleichs ist die **Ausdrueckbarkeit** — 21 der 25 G1-Regeln. Dazu
kommt eine Eigenschaft des Reports von cuallee: Er nennt Spalte, Regel und die
Zahl der Verstoesse, aber **keine Zeile und keinen Ausgangswert**.

Das ist eine Eigenschaft **dieses Werkzeugs**, nicht seiner Gattung. Great
Expectations liefert den Zeilenbezug; der Gegenschnitt dazu steht in
``tests/test_baselines/test_b3b.py``.

Was hier geprueft wird
----------------------

Erstens, dass die Uebersetzung funktioniert: Eine Katalogverletzung auf der
Rohschicht kommt als Meldung mit der richtigen Regelkennung und der richtigen
Spalte an, und ein regelkonformer Vorgang loest keine aus. Zweitens, dass jede
Meldung ``row_id`` gleich
:data:`~src.evaluation.modell.ROW_ID_OHNE_BEZUG` traegt. Das ist kein fehlender
Wert, den ein spaeterer Ausbau nachliefern koennte, sondern das Messergebnis der
Kennzahl Diagnoseguete: ``cuallee.pandas_validation.summary`` gibt je Regel eine
Zahl zurueck, keine Zeilenliste. Weil daraus folgt, dass B3 auf **keiner** der
drei Ebenen eine Konfusionsmatrix bekommt, traegt dieser eine Test die
Auswertbarkeit des gesamten B3-Vergleichs.

Drittens, dass der Zeitstempel des Frameworks verworfen wird. Ein Zeitstempel im
Ergebnis widerspricht Architekturregel A2; er wuerde zwei ansonsten identische
Laeufe verschieden aussehen lassen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from src.baselines.b3_framework import (
    DIAGNOSEGUETE,
    REGELN_G1,
    REGELN_KATALOG,
    B3Fehler,
    B3Framework,
)
from src.evaluation.modell import ROW_ID_OHNE_BEZUG, VERSTOSS_SPALTEN
from tests.test_regeln.bausteine import VORGANG_KFZ, baue

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    import pandas as pd

    from src.common.config import Config
    from src.evaluation.modell import Kontext

#: Zwei Katalogverletzungen auf der Rohschicht: ein Schluessel, den es nicht gibt,
#: und eine Postleitzahl ohne fuehrende Null.
KATALOGVERLETZUNGEN = {
    "anfrage": {0: {"zahlweise": "7"}},
    "person": {0: {"plz": "1067"}},
}


@pytest.fixture(scope="module")
def sauber(config: Config) -> Kontext:
    """Ein vollstaendiger, regelkonformer Kfz-Vorgang."""
    return baue(config, VORGANG_KFZ)


@pytest.fixture(scope="module")
def verfaelscht(config: Config) -> Kontext:
    """Derselbe Vorgang mit zwei Katalogverletzungen auf der Rohschicht."""
    return baue(config, VORGANG_KFZ, roh=KATALOGVERLETZUNGEN)


@pytest.fixture(scope="module")
def meldungen(verfaelscht: Kontext) -> pd.DataFrame:
    """Die Meldungen eines Laufs auf dem verfaelschten Minimaldatensatz."""
    return B3Framework().erkenne(verfaelscht)


def test_ausgabeformat_entspricht_dem_berichtsschema(meldungen: pd.DataFrame) -> None:
    """B3 liefert genau die Spalten, gegen die die Auswertung liest.

    Die Spalte ``timestamp`` des cuallee-Reports ist dabei ausdruecklich **nicht**
    enthalten: Ein Zeitstempel im Ergebnis widerspricht Architekturregel A2 und
    liesse zwei identische Laeufe verschieden aussehen.
    """
    assert tuple(meldungen.columns) == VERSTOSS_SPALTEN
    assert "timestamp" not in meldungen.columns


def test_katalogverletzung_wird_gefunden(meldungen: pd.DataFrame) -> None:
    """Beide eingebauten Katalogverletzungen kommen mit Regel und Spalte an.

    ``zahlweise = 7`` ist ein Schluessel, den die GDV-Anlage 14 nicht kennt;
    ``plz = 1067`` verletzt das Fuenf-Ziffern-Muster. Geprueft wird die Zuordnung
    Regel auf Spalte, denn genau sie ist das, was der Report von cuallee ueberhaupt
    hergibt.
    """
    gefunden = set(
        zip(meldungen["regel_id"], meldungen["entitaet"], meldungen["spalte"], strict=True)
    )

    assert ("R-010", "anfrage", "zahlweise") in gefunden
    assert ("R-002", "person", "plz") in gefunden


def test_regelkonformer_vorgang_ergibt_keine_meldung(sauber: Kontext) -> None:
    """Auf regelkonformen Daten meldet B3 nichts.

    Das ist alles andere als selbstverstaendlich: In unserem Modell ist der
    Leerstring ein **regulaer leerer** Wert, waehrend jede Musterpruefung von
    cuallee ihn als Verstoss zaehlen wuerde. Erst die vorangestellte Alternative
    ``^$|`` und der Leerstring in jeder erlaubten Wertemenge machen das Framework
    auf unserem Datenmodell brauchbar — Framework-Reibung, die in die Kennzahl
    "Aufwand" eingeht. Schlaegt dieser Test fehl, ist sie unvollstaendig
    ausgeglichen.
    """
    assert B3Framework().erkenne(sauber).empty


def test_keine_meldung_nennt_eine_zeile(meldungen: pd.DataFrame) -> None:
    """Jede Meldung traegt ``ROW_ID_OHNE_BEZUG`` — der zentrale B3-Befund.

    Der Report von cuallee nennt Spalte, Regel und die Zahl der Verstoesse, aber
    keine Zeile. Damit ist auf keiner der drei Ebenen eine Konfusionsmatrix
    bildbar, und die Auswertung traegt fuer B3 einen ``nicht_auswertbar_grund``
    statt Nullen. Dieser Test haelt die Grundlage jener Entscheidung fest: Waere
    ein Zeilenbezug doch vorhanden, waere die Nichtauswertbarkeit eine
    Behauptung statt einer Messung.
    """
    assert not meldungen.empty
    assert set(meldungen["row_id"]) == {ROW_ID_OHNE_BEZUG}
    assert not B3Framework.lokalisiert_zellen


def test_zweimal_derselbe_kontext_ergibt_bitgleiche_ausgabe(
    verfaelscht: Kontext, meldungen: pd.DataFrame
) -> None:
    """Zwei Instanzen auf demselben Kontext liefern denselben Rahmen (A2).

    Bewusst der vollstaendige Rahmenvergleich und nicht nur die Zeilenzahl: Die
    fortlaufende ``verstoss_id`` haengt an der Reihenfolge, in der Entitaeten und
    Regeln durchlaufen werden, und der Meldungstext an den Werten des Reports.
    """
    zweiter = B3Framework().erkenne(verfaelscht)

    assert meldungen.equals(zweiter)


def test_bericht_weist_die_nicht_ausdrueckbaren_regeln_aus(verfaelscht: Kontext) -> None:
    """R-004 und R-009 sind in der Check-API gar nicht formulierbar.

    R-004 ist die Pruefziffer nach ISO 7064 Mod 97-10 — nur ueber den
    Escape-Hatch mit eigener Python-Funktion und damit nicht mehr deklarativ.
    R-009 verlangt einen existierenden Kalendertag; ein Muster erkennt acht
    Ziffern, aber nicht den 31. Februar. R-001 und R-025 sind **teilweise**
    formulierbar und zaehlen deshalb nicht als ausdrueckbar — eine halbe Regel ist
    keine Regel, und die Gegenrechnung bleibt trotzdem sichtbar.
    """
    verfahren = B3Framework()
    verfahren.erkenne(verfaelscht)
    bericht = verfahren.bericht()

    assert bericht.nicht_ausdrueckbar == ("R-004", "R-009")
    assert bericht.teilweise == ("R-001", "R-025")
    assert len(bericht.ausdrueckbar) == REGELN_G1 - len(bericht.teilweise) - len(
        bericht.nicht_ausdrueckbar
    )
    assert bericht.anteil_ausdrueckbar_g1 == len(bericht.ausdrueckbar) / REGELN_G1
    assert bericht.anteil_ausdrueckbar_katalog == len(bericht.ausdrueckbar) / REGELN_KATALOG


def test_bericht_haelt_die_diagnoseguete_fest(verfaelscht: Kontext) -> None:
    """Der Bericht nennt ausdruecklich, was der Report ueber einen Fund aussagt.

    Spalte, Regel und Anzahl ja, Zeile und Ausgangswert nein. Dieselbe Aussage
    steht als Zusicherung in :data:`~src.baselines.b3_framework.DIAGNOSEGUETE`
    und wird hier gegen das tatsaechliche Verhalten gehalten, damit die Tabelle
    im Anhang nicht von der Messung abweichen kann.
    """
    verfahren = B3Framework()
    verfahren.erkenne(verfaelscht)
    bericht = verfahren.bericht()

    assert bericht.diagnoseguete == DIAGNOSEGUETE
    assert bericht.diagnoseguete["zeile"] is False
    assert bericht.diagnoseguete["ausgangswert"] is False
    assert bericht.laufzeit_s > 0.0


def test_bericht_ohne_lauf_ist_ein_fehler() -> None:
    """Ohne ``erkenne``-Aufruf gibt es keine Laufzeit, sondern eine Ausnahme.

    Eine Null waere von einer gemessenen Null nicht zu unterscheiden und stuende
    als Aufwandskennzahl in der Arbeit — genau die Art stillen Fallbacks, die
    ``CLAUDE.md``, Abschnitt 5 ausschliesst.
    """
    with pytest.raises(B3Fehler, match="Laufzeit"):
        B3Framework().bericht()
