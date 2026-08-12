"""Mehrfach gemeldete Zellen zaehlen einmal, nicht mehrfach.

``T(D)`` ist die **Vereinigungsmenge** der markierten Zellen und nicht die Summe
der Regeltreffer (``src/evaluation/metriken.py``, Abschnitt 1). Diese Festlegung
ist keine Bequemlichkeit, sondern verhindert eine Metrikfalle: Bei summierter
Zaehlung erzeugte ein einziger injizierter Fehler, den zwei Regeln gleichzeitig
sehen, einen Treffer **und** einen Fehlalarm. Die Precision fiele, obwohl der
Katalog besser wurde, indem er den Fehler doppelt absicherte.

Der Fall ist im Katalog der Normalfall und nicht die Ausnahme: Ein Sentinelwert
in einem Datumsfeld verletzt R-009 (Kalendertag) und R-025 (Sentinel) zugleich.
Gemessen wird deshalb hier, dass die Vereinigung in der Pipeline stattfindet —
und nicht in einem der vier Adapter, wo sie dreimal fehlen koennte.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.evaluation.modell import Ebene
from src.evaluation.pipeline import bewerte
from tests.test_evaluation import Zellverfahren, daten, kennzahlen_von, kontext, wahrheit

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from src.common.config import Config

#: Zwei Meldungen derselben Zelle aus zwei verschiedenen Regeln.
DOPPELMELDUNG = (
    ("person", 1, "plz", "R-009", "R-009#000001"),
    ("person", 1, "plz", "R-025", "R-025#000001"),
)


def test_zwei_regeln_auf_derselben_zelle_ergeben_ein_tp(config: Config) -> None:
    """Zwei Meldungen derselben verfaelschten Zelle ergeben einen Treffer, keine zwei.

    Die Kernaussage des Moduls. Zaehlte die Pipeline Rohtreffer, stuende hier
    ``tp = 1`` und ``fp = 1`` — eine Precision von 0,5 fuer einen Katalog, der
    genau die richtige Zelle gefunden hat.
    """
    daten_dirty = daten(3)
    gt = wahrheit(daten_dirty, zellen=[("person", 1, "plz", "F2", "F2-a", False)])

    ergebnis = bewerte(
        [Zellverfahren(DOPPELMELDUNG)], kontext(config, daten_dirty), gt, messe_speicher=False
    )[0]
    konfusion = kennzahlen_von(ergebnis, Ebene.ZELLE).konfusion

    assert (konfusion.tp, konfusion.fp, konfusion.fn) == (1, 0, 0)
    assert kennzahlen_von(ergebnis, Ebene.ZELLE).precision == 1.0


def test_rohtreffer_und_vereinigung_werden_beide_berichtet(config: Config) -> None:
    """Neben der Vereinigungsmenge bleibt die Zahl der Rohtreffer stehen.

    Ihre Differenz ist selbst ein Befund ueber die Redundanz des Katalogs und darf
    deshalb nicht in der Vereinigung verschwinden.
    """
    daten_dirty = daten(3)
    gt = wahrheit(daten_dirty, zellen=[("person", 1, "plz", "F2", "F2-a", False)])

    ergebnis = bewerte(
        [Zellverfahren(DOPPELMELDUNG)], kontext(config, daten_dirty), gt, messe_speicher=False
    )[0]

    assert ergebnis.meldungen_gesamt == 2
    assert ergebnis.markierte_zellen == 1


def test_doppelt_gemeldeter_fehlalarm_zaehlt_ebenfalls_einmal(config: Config) -> None:
    """Auch ein Fehlalarm wird durch die zweite Meldung nicht zu zwei Fehlalarmen.

    Die Vereinigung darf nicht nur in die guenstige Richtung wirken: Waere sie nur
    auf Treffer angewandt, waere sie eine Beschoenigung und keine Definition.
    """
    daten_dirty = daten(3)
    gt = wahrheit(daten_dirty)
    meldungen = (
        ("person", 2, "ort", "R-009", "R-009#000001"),
        ("person", 2, "ort", "R-025", "R-025#000001"),
    )

    ergebnis = bewerte(
        [Zellverfahren(meldungen)], kontext(config, daten_dirty), gt, messe_speicher=False
    )[0]
    konfusion = kennzahlen_von(ergebnis, Ebene.ZELLE).konfusion

    assert (konfusion.tp, konfusion.fp, konfusion.fn) == (0, 1, 0)
    assert ergebnis.meldungen_gesamt == 2


def test_regeldiagnose_weist_die_geteilte_zelle_beiden_regeln_zu(config: Config) -> None:
    """Beide Regeln behalten ihren Treffer, aber keine war die einzige Melderin.

    Die Vereinigung geschieht in der Metrik, nicht in der Diagnose: Fuer die Frage
    "was ginge ohne diese Regel verloren?" muss sichtbar bleiben, dass beide
    Regeln dieselbe Zelle gesehen haben. Genau das misst
    ``anteil_einzige_regel`` — hier null fuer die geteilte Zelle und eins fuer die
    Regel, die allein meldet.
    """
    daten_dirty = daten(3)
    gt = wahrheit(
        daten_dirty,
        zellen=[
            ("person", 1, "plz", "F2", "F2-a", False),
            ("person", 2, "ort", "F1", "F1-a", False),
        ],
    )
    meldungen = (*DOPPELMELDUNG, ("person", 2, "ort", "R-001", "R-001#000001"))

    ergebnis = bewerte(
        [Zellverfahren(meldungen)], kontext(config, daten_dirty), gt, messe_speicher=False
    )[0]
    diagnose = {eintrag.regel_id: eintrag for eintrag in ergebnis.auswertungen[0].regeldiagnose}

    assert diagnose["R-009"].tp == 1
    assert diagnose["R-025"].tp == 1
    assert diagnose["R-009"].anteil_einzige_regel == 0.0
    assert diagnose["R-025"].anteil_einzige_regel == 0.0
    assert diagnose["R-001"].anteil_einzige_regel == 1.0


def test_zwei_zellen_derselben_zeile_markieren_eine_zeile(config: Config) -> None:
    """Auf der Satzebene wird dieselbe Zeile durch zwei Zellen einmal markiert.

    Die Entdopplung gilt auf jeder Ebene mit ihrer eigenen Einheit; auf der
    Satzebene ist die Einheit ``(entitaet, row_id)``. Ohne sie waere die
    Satzprecision eine Funktion der Zahl verletzter Felder je Zeile.
    """
    daten_dirty = daten(3)
    gt = wahrheit(daten_dirty, zellen=[("person", 1, "plz", "F2", "F2-a", False)])
    meldungen = (
        ("person", 1, "plz", "R-011", "R-011#000001"),
        ("person", 1, "ort", "R-012", "R-012#000001"),
    )

    ergebnis = bewerte(
        [Zellverfahren(meldungen)], kontext(config, daten_dirty), gt, messe_speicher=False
    )[0]
    konfusion = kennzahlen_von(ergebnis, Ebene.SATZ).konfusion

    assert (konfusion.tp, konfusion.fp, konfusion.fn) == (1, 0, 0)
    assert konfusion.grundgesamtheit == 3
