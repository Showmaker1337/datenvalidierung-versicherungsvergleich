"""Smoke-Test des Prototyp-Adapters auf einem Minimaldatensatz.

Der Adapter enthaelt keine Pruefbedingung — die stehen im Katalog und sind in
``tests/test_regeln/`` je Regel einzeln geprueft. Hier wird die
**Uebersetzungsleistung** geprueft: das Berichtsformat, die Bitgleichheit zweier
Laeufe (Architekturregel A2), der Filter auf ``in_zellmetrik`` und der
Zwischenspeicher.

Warum ein handgebauter Datensatz
--------------------------------

Wie in den Regeltests wird gegen :mod:`tests.test_regeln.bausteine` gearbeitet und
nicht gegen den Generator. Ein Test gegen den Generator zeigte nur, dass zwei
Implementierungen zueinander passen; ein Test gegen einen von Hand gesetzten Wert
zeigt, dass der Adapter den Fehler durchreicht, der wirklich im Datensatz steht.

Der eingebaute Fehler ist eine Postleitzahl mit vier Ziffern auf der Rohschicht.
Er ist mit Absicht einer, den **mehrere** Regeln sehen (R-002 formal, R-050 gegen
die Referenztabelle): Genau daran zeigt sich, dass der Adapter die Rohtreffer
weiterreicht und die Vereinigung der Auswertung ueberlaesst.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from src.baselines.prototyp import Prototyp
from src.evaluation.modell import SATZ_SPALTEN, VERSTOSS_SPALTEN, AuswertungsFehler
from src.rules.katalog import alle_regeln
from tests.test_regeln.bausteine import VORGANG_KFZ, baue

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from src.common.config import Config
    from src.evaluation.modell import Kontext

#: Rohschichtaenderung des eingebauten Fehlers: eine Postleitzahl ohne fuehrende Null.
FEHLENDE_NULL = {"person": {0: {"plz": "1067"}}}


@pytest.fixture(scope="module")
def sauber(config: Config) -> Kontext:
    """Ein vollstaendiger, regelkonformer Kfz-Vorgang."""
    return baue(config, VORGANG_KFZ)


@pytest.fixture(scope="module")
def verfaelscht(config: Config) -> Kontext:
    """Derselbe Vorgang mit einer vierstelligen Postleitzahl auf der Rohschicht."""
    return baue(config, VORGANG_KFZ, roh=FEHLENDE_NULL)


def test_ausgabeformat_entspricht_dem_berichtsschema(sauber: Kontext) -> None:
    """Beide Kanaele liefern genau die Spalten, gegen die die Auswertung liest.

    Das Berichtsformat hat genau eine Quelle (``src.rules.modell``), und alle vier
    Verfahren schreiben dagegen. Weicht ein Adapter ab, faellt es erst in der
    Auswertung auf — dort aber als fehlende Kennzahl, nicht als Formatfehler.
    """
    prototyp = Prototyp()

    assert tuple(prototyp.erkenne(sauber).columns) == VERSTOSS_SPALTEN
    assert tuple(prototyp.satzmeldungen(sauber).columns) == SATZ_SPALTEN


def test_regelkonformer_vorgang_ergibt_keine_meldung(sauber: Kontext) -> None:
    """Auf schemakonformen Daten meldet der Adapter nichts.

    Die Kern-Invariante des Katalogs ist in ``tests/test_invariante.py``
    property-based geprueft; hier zaehlt, dass der Adapter sie nicht durch seine
    Filterung oder seinen Zwischenspeicher verletzt.
    """
    prototyp = Prototyp()

    assert prototyp.erkenne(sauber).empty
    assert prototyp.satzmeldungen(sauber).empty


def test_eingebauter_fehler_wird_gefunden(verfaelscht: Kontext) -> None:
    """Die vierstellige Postleitzahl erscheint als Zellmeldung auf ``person.plz``.

    Geprueft wird die Lokalisierung, nicht nur die Zahl der Meldungen: Ohne
    Entitaet, Zeile und Feld waere die Meldung auf der Zellebene nicht
    auswertbar.
    """
    meldungen = Prototyp().erkenne(verfaelscht)
    orte = set(zip(meldungen["entitaet"], meldungen["row_id"], meldungen["spalte"], strict=True))

    assert orte == {("person", 1, "plz")}
    assert "R-002" in set(meldungen["regel_id"]), (
        f"Die Formatregel hat nicht gemeldet; gemeldet haben: {sorted(set(meldungen['regel_id']))}"
    )


def test_rohtreffer_bleiben_ungefaltet(verfaelscht: Kontext) -> None:
    """Mehrere Regeln auf derselben Zelle ergeben mehrere Meldezeilen.

    Der Adapter reicht die Rohtreffer weiter und bildet **nicht** die
    Vereinigungsmenge. Die gehoert in die Auswertung: Sie ist fuer alle vier
    Verfahren dieselbe Operation und darf nicht in vier Adaptern je einmal
    stehen. Ausserdem braucht die Regeldiagnose die Zuordnung Meldung auf Regel,
    die eine vorgezogene Vereinigung verloere.
    """
    meldungen = Prototyp().erkenne(verfaelscht)

    assert len(meldungen) > 1, (
        "Die vierstellige Postleitzahl verletzt Format- und Referenzregel zugleich; "
        f"der Adapter liefert aber nur {len(meldungen)} Meldung(en)"
    )
    assert len(set(meldungen["regel_id"])) == len(meldungen)


def test_erkenne_meldet_nur_zellmetrische_regeln(verfaelscht: Kontext) -> None:
    """Regeln mit ``in_zellmetrik=False`` erscheinen im Zellkanal nicht.

    R-047 und R-048 nennen keine verursachende Zelle. Wuerden ihre Meldungen in
    die Zellmetrik eingehen, faellt die Precision und die Fehlalarmrate steigt —
    als Artefakt der Berichtskonvention, nicht des Detektors. Der Test prueft die
    Zusicherung an der Modulgrenze, nicht das heutige Verhalten der beiden Regeln.
    """
    ohne_zellmetrik = {eintrag.regel_id for eintrag in alle_regeln() if not eintrag.in_zellmetrik}
    gemeldet = set(Prototyp().erkenne(verfaelscht)["regel_id"])

    assert ohne_zellmetrik, "Der Katalog kennt keine Regel ohne Zellmetrik — der Test misst nichts"
    assert not (gemeldet & ohne_zellmetrik)


def test_zweimal_derselbe_kontext_ergibt_bitgleiche_ausgabe(verfaelscht: Kontext) -> None:
    """Zwei frische Adapter auf demselben Kontext liefern denselben Rahmen (A2).

    Bewusst zwei **verschiedene** Instanzen: Ein Adapter, der sein Ergebnis
    zwischenspeichert, gaebe beim zweiten Aufruf trivial dasselbe zurueck. Die
    Aussage ist, dass die Berechnung selbst keinen verborgenen Zustand hat.
    """
    erster = Prototyp().erkenne(verfaelscht)
    zweiter = Prototyp().erkenne(verfaelscht)

    assert erster.equals(zweiter)


def test_ein_kontext_wird_nur_einmal_geprueft(verfaelscht: Kontext) -> None:
    """Zell- und Satzkanal stammen aus **einem** Katalogdurchlauf.

    Der Nachweis laeuft ueber die Laufzeitmessung der Engine: Zwei Durchlaeufe
    ergaeben zwei verschiedene ``perf_counter``-Differenzen. Bleiben die Zahlen
    ueber drei Zugriffe gleich, wurde der Katalog genau einmal ausgefuehrt. Ohne
    Zwischenspeicher liefe er dreimal — bei mehreren tausend Laeufen der Phase 6
    der Unterschied zwischen Stunden und Tagen.
    """
    prototyp = Prototyp()
    prototyp.erkenne(verfaelscht)
    nach_erkenne = dict(prototyp.laufzeiten_je_regel())
    prototyp.satzmeldungen(verfaelscht)
    nach_satzmeldungen = dict(prototyp.laufzeiten_je_regel())

    assert nach_erkenne == nach_satzmeldungen


def test_laufzeiten_ohne_lauf_sind_ein_fehler() -> None:
    """Ohne geprueften Kontext gibt es keine Laufzeit, sondern eine Ausnahme.

    Null Sekunden je Regel waere eine Messung, die es nicht gibt, und in der
    Aufwandstabelle von einer echten Null nicht zu unterscheiden — genau die Art
    stillen Fallbacks, die ``CLAUDE.md``, Abschnitt 5 ausschliesst.
    """
    with pytest.raises(AuswertungsFehler, match="Laufzeitmessung"):
        Prototyp().laufzeiten_je_regel()
