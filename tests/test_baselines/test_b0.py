"""Smoke-Test der Baseline B0 (pydantic v2) auf einem Minimaldatensatz.

B0 ist die **untere Schranke** des Vergleichs: Typ, unbedingte Pflicht und
Feldlaenge, sonst nichts. Geprueft wird deshalb beides — dass B0 findet, was in
seinen Zustaendigkeitsbereich faellt, und dass es liegen laesst, was nicht
hineingehoert. Die zweite Haelfte ist die wichtigere: Sie ist der Grund, warum
B0 auf der Fehlerklasse F1 nur einen kleinen Recall erreichen kann, und ohne sie
liest sich diese Zahl wie ein Mangel der Implementierung statt wie die Aussage
des Vergleichs.

Der Weg durch beide Schichten
-----------------------------

B0 arbeitet ausschliesslich auf der **Rohschicht**. Die eingebauten Fehler werden
deshalb ueber den ``roh``-Parameter von :func:`tests.test_regeln.bausteine.baue`
gesetzt: Auf der typisierten Schicht waere ein Typfehler per Konstruktion nicht
darstellbar — ``"neunzig"`` passt in keine ``Int64``-Spalte (``spec/01``,
Abschnitt 6).
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import pytest

from src.baselines.b0_schema import PFLICHTFELDER, B0Schema
from src.evaluation.modell import VERSTOSS_SPALTEN, AuswertungsFehler
from tests.test_regeln.bausteine import VORGANG_KFZ, baue

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from src.common.config import Config
    from src.evaluation.modell import Kontext


@pytest.fixture(scope="module")
def sauber(config: Config) -> Kontext:
    """Ein vollstaendiger, schemakonformer Kfz-Vorgang."""
    return baue(config, VORGANG_KFZ)


def test_ausgabeformat_entspricht_dem_berichtsschema(sauber: Kontext) -> None:
    """B0 liefert genau die Spalten, gegen die die Auswertung liest.

    Auch auf einem fehlerfreien Datensatz: Ein leerer Rahmen ohne Spalten waere in
    der Auswertung nicht von einem Rahmen mit falschen Spalten zu unterscheiden.
    """
    meldungen = B0Schema().erkenne(sauber)

    assert tuple(meldungen.columns) == VERSTOSS_SPALTEN
    assert meldungen.empty


def test_typfehler_wird_gefunden(config: Config) -> None:
    """Ein nicht parsbarer Rohwert in einem Ganzzahlfeld wird gemeldet.

    Das ist der Kern von B0: ``leistung_kw`` ist im Schema eine ganze Zahl, und
    ``"neunzig"`` ist keine. Geprueft werden Ort und Regelkennung, denn nur mit
    beidem ist die Meldung auf der Zellebene auswertbar.
    """
    kontext = baue(config, VORGANG_KFZ, roh={"risiko_kfz": {0: {"leistung_kw": "neunzig"}}})

    meldungen = B0Schema().erkenne(kontext)
    orte = set(zip(meldungen["entitaet"], meldungen["row_id"], meldungen["spalte"], strict=True))

    assert orte == {("risiko_kfz", 1, "leistung_kw")}
    assert set(meldungen["regel_id"]) == {"B0-leistung_kw"}
    assert meldungen.loc[0, "verstoss_id"] == "B0-leistung_kw#000001"


def test_laengenfehler_wird_gefunden(config: Config) -> None:
    """Eine vierstellige Postleitzahl verletzt die exakte Feldlaenge.

    Bewusst dieselbe Verfaelschung wie im Prototyp-Test: An ihr laesst sich
    ablesen, dass B0 den Fehler zwar sieht, ihn aber als Laengenverstoss meldet
    und nicht als Musterverstoss — B0 kennt keine Muster.
    """
    kontext = baue(config, VORGANG_KFZ, roh={"person": {0: {"plz": "1067"}}})

    meldungen = B0Schema().erkenne(kontext)

    assert set(meldungen["regel_id"]) == {"B0-plz"}
    assert "kuerzer" in str(meldungen.loc[0, "meldung"])


def test_bedingte_pflicht_bleibt_unentdeckt(config: Config) -> None:
    """Ein leerer ``nachname`` wird von B0 **nicht** gemeldet — und das ist richtig.

    "Nicht leer, ausser ``anrede`` gleich FIRMA" ist eine bedingte funktionale
    Abhaengigkeit und damit eine fachliche Regel. B0 kennt per Definition keine
    Feldabhaengigkeiten; ``nachname`` steht deshalb nicht in
    :data:`~src.baselines.b0_schema.PFLICHTFELDER`. Dieser Test schreibt die
    Abgrenzung fest: Ohne ihn koennte sie spaeter stillschweigend aufgeweicht
    werden, und der Vergleich verloere seine untere Schranke.
    """
    kontext = baue(config, VORGANG_KFZ, roh={"person": {0: {"nachname": ""}}})

    assert "nachname" not in PFLICHTFELDER["person"]
    assert B0Schema().erkenne(kontext).empty


def test_zweimal_derselbe_kontext_ergibt_bitgleiche_ausgabe(config: Config) -> None:
    """Zwei Instanzen auf demselben Kontext liefern denselben Rahmen (A2).

    B0 vergibt fortlaufende ``verstoss_id``. Die Nummerierung haengt an der
    Reihenfolge von Entitaeten, Zeilen und Einzelfehlern; waere eine davon
    ungeordnet, faellt es genau hier auf.
    """
    kontext = baue(
        config,
        VORGANG_KFZ,
        roh={
            "person": {0: {"plz": "1067"}},
            "risiko_kfz": {0: {"leistung_kw": "neunzig", "erstzulassung": "31022018"}},
        },
    )

    erster = B0Schema().erkenne(kontext)
    zweiter = B0Schema().erkenne(kontext)

    assert len(erster) >= 3, f"Der Testfall loest nur {len(erster)} Meldung(en) aus"
    assert erster.equals(zweiter)


def test_fehlende_entitaet_ist_ein_fehler(sauber: Kontext) -> None:
    """Eine fehlende Entitaet bricht ab, statt null Meldungen zu liefern.

    Ein stillschweigend eingesetzter leerer Rahmen ergaebe eine Kennzahl, die
    aussieht wie ein Messergebnis ("B0 hat in ``zahlung`` nichts gefunden"), in
    Wahrheit aber nur bedeutet, dass dort nie gemessen wurde.
    """
    ohne_zahlung = {name: rahmen for name, rahmen in sauber.raw.items() if name != "zahlung"}
    beschaedigt = dataclasses.replace(sauber, raw=ohne_zahlung)

    with pytest.raises(AuswertungsFehler, match="zahlung"):
        B0Schema().erkenne(beschaedigt)
