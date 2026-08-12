"""Auswertungstests: gemeinsame Bausteine der sechs Testmodule.

Warum die Tests ohne Laufartefakte auskommen
--------------------------------------------

Kein Test dieses Pakets laedt ein ``error_log.parquet`` und keiner ruft den
Injektor. Ground Truth und Meldungen werden **von Hand** gesetzt. Der Grund ist
derselbe wie bei den Regeltests (``tests/test_regeln/bausteine.py``): Ein Test
gegen erzeugte Laufartefakte zeigt nur, dass zwei Implementierungen zueinander
passen. Hier soll aber gezeigt werden, dass eine Konfusionsmatrix genau die
Zahlen liefert, die man auf Papier ausrechnet — und das geht nur, wenn beide
Seiten der Rechnung im Test stehen.

Ein zweiter Grund ist praktisch: Ein echter Lauf braucht Referenzdaten, den
Generator und den Injektor. Faellt eine dieser Stufen aus, faerbte sich die
Auswertung mit rot, ohne dass an ihr etwas falsch waere.

Warum die Bausteine im Paketmodul stehen
----------------------------------------

Vier der sechs Testmodule brauchen dieselbe Vorrichtung: einen
Miniaturdatensatz, einen :class:`~src.evaluation.modell.Kontext` darueber, ein
Verfahren mit fest vorgegebenen Meldungen und einen Zugriff auf die gesuchte
Ebene. Diese Vorrichtung liegt genau einmal hier, statt viermal kopiert zu werden
— vier Kopien einer Testvorrichtung geraten genauso aus dem Tritt wie vier Kopien
einer Definition.

Der Kontext wird direkt gebaut, nicht ueber ``baue_kontext``
-------------------------------------------------------------

:func:`kontext` setzt den :class:`~src.evaluation.modell.Kontext` unmittelbar
zusammen, statt ihn ueber :func:`src.rules.modell.baue_kontext` aus einer Schicht
abzuleiten. Der Weg ueber ``baue_kontext`` wuerde die Rohschicht parsen und damit
die Serialisierung mitpruefen — die hat ihre eigenen Tests. Fuer die Auswertung
ist der Kontext nur Traeger zweier Groessen: der Zeilenzahl (Normierung der
Laufzeit) und der Spaltenzahl (Zelluniversum). Die Testverfahren lesen aus ihm
keinen einzigen Wert; ihre Meldungen stehen im Test.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pandas as pd

from src.common.serialisierung import ENTITAETEN, SPALTEN_JE_ENTITAET
from src.evaluation.ground_truth import (
    ERROR_LOG_PFLICHTSPALTEN,
    RECORDS_PFLICHTSPALTEN,
    lade_ground_truth,
)
from src.evaluation.modell import SATZ_SPALTEN, VERSTOSS_SPALTEN, Kontext

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence

    from src.common.config import Config
    from src.evaluation.ground_truth import GroundTruth
    from src.evaluation.modell import (
        Ebene,
        Ebenenauswertung,
        Gruppenrecall,
        Kennzahlen,
        Verfahrensergebnis,
    )

__all__ = [
    "LAUF_ID",
    "Satzverfahren",
    "Zellverfahren",
    "daten",
    "ebene_von",
    "gruppe_von",
    "kennzahlen_von",
    "kontext",
    "satzlog",
    "wahrheit",
    "zelllog",
]

#: Laufkennung der Tests. Ohne Faktorstufen — es wird kein Experimentlauf gestellt.
LAUF_ID: Final[str] = "test_eval"

#: Eine Zellmeldung: Entitaet, Zeile, Spalte, Regel, ``verstoss_id``.
type Zellmeldung = tuple[str, int, str, str, str]

#: Eine Satzmeldung: Entitaet, Regel, ``verstoss_id``, betroffene Zeilen.
type Satzmeldung = tuple[str, str, str, Sequence[int]]

#: Eine Zeile des ``error_log``: Entitaet, Zeile, Spalte, Klasse, Variante, mitgezogen.
type Logzelle = tuple[str, int, str, str, str, bool]

#: Eine Zeile des ``error_log_records``: Entitaet, Klasse, Variante, betroffene Zeilen.
type Logsatz = tuple[str, str, str, Sequence[int]]


# ---------------------------------------------------------------------------
# Miniaturdatensatz und Kontext
# ---------------------------------------------------------------------------


def _rahmen(spalten: Sequence[str], zeilen: int) -> pd.DataFrame:
    """Baut einen Rohschichtrahmen mit belegter ``row_id`` und leeren Feldern.

    Args:
        spalten: Spaltennamen der Entitaet, in Schemareihenfolge.
        zeilen: Zahl der Zeilen.

    Returns:
        Den Rahmen; ``row_id`` traegt die Kennungen 1 bis ``zeilen``, jedes andere
        Feld den Leerstring. Die Werte spielen keine Rolle — gebraucht werden nur
        Zeilen- und Spaltenzahl.
    """
    return pd.DataFrame(
        {
            spalte: [str(nummer + 1) if spalte == "row_id" else "" for nummer in range(zeilen)]
            for spalte in spalten
        },
        columns=list(spalten),
    )


def daten(zeilen: int, *, entitaet: str = "person") -> dict[str, pd.DataFrame]:
    """Baut die Rohschicht eines Miniaturdatensatzes.

    Nur **eine** Entitaet traegt Zeilen; alle uebrigen bleiben leer, sind aber
    vorhanden. Das haelt das Zelluniversum klein und von Hand nachrechenbar
    (``zeilen`` mal Spaltenzahl der gewaehlten Entitaet) und erfuellt zugleich die
    Erwartung der Pipeline, jede Entitaet des Schemas vorzufinden.

    Args:
        zeilen: Zeilenzahl der belegten Entitaet.
        entitaet: Name der belegten Entitaet.

    Returns:
        Je Entitaet einen Rahmen der Rohschicht.
    """
    return {
        name: _rahmen(SPALTEN_JE_ENTITAET[name], zeilen if name == entitaet else 0)
        for name in ENTITAETEN
    }


def kontext(config: Config, daten_dirty: Mapping[str, pd.DataFrame]) -> Kontext:
    """Baut den Pruefkontext ueber einen Miniaturdatensatz.

    Beide Schichten zeigen auf dieselben Rahmen (siehe Modul-Docstring): Die
    Testverfahren lesen keinen Wert, ihre Meldungen sind vorgegeben. Die
    Referenztabellen bleiben leer, damit kein Test dieses Pakets von den
    versionierten Referenzdaten abhaengt.

    Args:
        config: Die geladene Konfiguration.
        daten_dirty: Rohschicht des Miniaturdatensatzes.

    Returns:
        Den :class:`~src.evaluation.modell.Kontext`.
    """
    return Kontext(config=config, typed=dict(daten_dirty), raw=dict(daten_dirty), referenz={})


# ---------------------------------------------------------------------------
# Ground Truth von Hand
# ---------------------------------------------------------------------------


def zelllog(eintraege: Sequence[Logzelle] = ()) -> pd.DataFrame:
    """Baut ein ``error_log`` aus Tupeln.

    Args:
        eintraege: Je Zelle ein Tupel aus Entitaet, Zeile, Spalte, Fehlerklasse,
            Injektionsvariante und dem Kennzeichen ``mitgezogen``.

    Returns:
        Den Rahmen mit den Pflichtspalten des ``error_log``.
    """
    return pd.DataFrame(list(eintraege), columns=list(ERROR_LOG_PFLICHTSPALTEN))


def satzlog(eintraege: Sequence[Logsatz] = ()) -> pd.DataFrame:
    """Baut ein ``error_log_records`` aus Tupeln.

    Args:
        eintraege: Je satzbezogener Verfaelschung ein Tupel aus Entitaet,
            Fehlerklasse, Injektionsvariante und den betroffenen Zeilen.

    Returns:
        Den Rahmen mit den Pflichtspalten des ``error_log_records``.
    """
    return pd.DataFrame(
        [
            (entitaet, klasse, variante, list(zeilen))
            for entitaet, klasse, variante, zeilen in eintraege
        ],
        columns=list(RECORDS_PFLICHTSPALTEN),
    )


def wahrheit(
    daten_dirty: Mapping[str, pd.DataFrame],
    *,
    zellen: Sequence[Logzelle] = (),
    saetze: Sequence[Logsatz] = (),
    klassen: Sequence[str] | None = None,
    varianten: Sequence[str] | None = None,
) -> GroundTruth:
    """Baut den Ground Truth eines Tests aus handgesetzten Logzeilen.

    Args:
        daten_dirty: Rohschicht des Miniaturdatensatzes; bestimmt beide Universen.
        zellen: Zeilen des ``error_log``.
        saetze: Zeilen des ``error_log_records``.
        klassen: Zusaetzlich auszuweisende Fehlerklassen, wie sie sonst aus dem
            ``manifest.json`` kommen.
        varianten: Ebenso fuer die Injektionsvarianten.

    Returns:
        Den :class:`~src.evaluation.ground_truth.GroundTruth`.
    """
    return lade_ground_truth(
        zelllog(zellen),
        satzlog(saetze),
        daten_dirty,
        run_id=LAUF_ID,
        klassen=klassen,
        varianten=varianten,
    )


# ---------------------------------------------------------------------------
# Verfahren mit vorgegebenen Meldungen
# ---------------------------------------------------------------------------


class Zellverfahren:
    """Ein Verfahren, dessen Zellmeldungen der Test woertlich vorgibt.

    Erfuellt :class:`~src.evaluation.modell.Verfahren`, aber **nicht**
    :class:`~src.evaluation.modell.MitSatzmeldungen`. Damit ist im Test steuerbar,
    ob die Satzebene ausschliesslich aus markierten Zellen entsteht.

    Attributes:
        name: Kurzname in den Ergebnistabellen.
        beschreibung: Ein Satz fuer den Bericht.
        lokalisiert_zellen: ``True`` — jede Meldung nennt Entitaet, Zeile und Feld.
        in_inferenzstatistik: ``True``; ohne Wirkung in diesen Tests.
    """

    name: str = "test"
    beschreibung: str = "Testverfahren mit fest vorgegebenen Meldungen"
    lokalisiert_zellen: bool = True
    in_inferenzstatistik: bool = True

    def __init__(self, meldungen: Sequence[Zellmeldung], *, name: str = "test") -> None:
        """Legt das Verfahren mit seinen Meldungen an.

        Args:
            meldungen: Je Meldung ein Tupel aus Entitaet, Zeile, Spalte,
                ``regel_id`` und ``verstoss_id``.
            name: Kurzname; noetig, sobald mehrere Verfahren zugleich bewertet
                werden, denn die Pipeline verlangt eindeutige Namen.
        """
        self.name = name
        self._meldungen = tuple(meldungen)

    def erkenne(self, kontext: Kontext) -> pd.DataFrame:
        """Gibt die vorgegebenen Zellmeldungen zurueck.

        Args:
            kontext: Pruefkontext; wird nicht gelesen, die Meldungen stehen im
                Test.

        Returns:
            Einen Rahmen mit den Spalten
            :data:`~src.evaluation.modell.VERSTOSS_SPALTEN`.
        """
        del kontext
        return pd.DataFrame(
            [
                (entitaet, row_id, spalte, regel_id, verstoss_id, f"{regel_id}: Testmeldung")
                for entitaet, row_id, spalte, regel_id, verstoss_id in self._meldungen
            ],
            columns=list(VERSTOSS_SPALTEN),
        )


class Satzverfahren(Zellverfahren):
    """Ein Verfahren, das zusaetzlich satzbezogene Befunde meldet.

    Erfuellt damit auch :class:`~src.evaluation.modell.MitSatzmeldungen`. Nur so
    sind F6 und HO1 ueberhaupt auffindbar: Ein Duplikat hat keine verursachende
    Zelle (``spec/03_fehlerklassen.md``, Abschnitt 4.2).
    """

    def __init__(
        self,
        meldungen: Sequence[Zellmeldung],
        saetze: Sequence[Satzmeldung],
        *,
        name: str = "test",
    ) -> None:
        """Legt das Verfahren mit Zell- und Satzmeldungen an.

        Args:
            meldungen: Zellmeldungen wie bei :class:`Zellverfahren`.
            saetze: Je Satzbefund ein Tupel aus Entitaet, ``regel_id``,
                ``verstoss_id`` und den betroffenen Zeilen.
            name: Kurzname des Verfahrens.
        """
        super().__init__(meldungen, name=name)
        self._saetze = tuple(saetze)

    def satzmeldungen(self, kontext: Kontext) -> pd.DataFrame:
        """Gibt die vorgegebenen Satzbefunde zurueck.

        Args:
            kontext: Pruefkontext; wird nicht gelesen.

        Returns:
            Einen Rahmen mit den Spalten
            :data:`~src.evaluation.modell.SATZ_SPALTEN`.
        """
        del kontext
        return pd.DataFrame(
            [
                (entitaet, regel_id, verstoss_id, list(zeilen), f"{regel_id}: Testmeldung")
                for entitaet, regel_id, verstoss_id, zeilen in self._saetze
            ],
            columns=list(SATZ_SPALTEN),
        )


# ---------------------------------------------------------------------------
# Zugriff auf das Ergebnis
# ---------------------------------------------------------------------------


def ebene_von(
    ergebnis: Verfahrensergebnis,
    ebene: Ebene,
    *,
    mitgezogen: bool = False,
) -> Ebenenauswertung:
    """Holt die Auswertung einer Ebene aus einem Verfahrensergebnis.

    Args:
        ergebnis: Das Ergebnis eines Verfahrens.
        ebene: Die gesuchte Ebene.
        mitgezogen: Schalterstellung ``mitgezogen_als_fehler``. ``False`` steht
            fest an Position 0 des Auswertungspaares; genau das wird hier
            nebenbei mitgeprueft.

    Returns:
        Die :class:`~src.evaluation.modell.Ebenenauswertung`.
    """
    auswertung = ergebnis.auswertungen[1 if mitgezogen else 0]
    assert auswertung.mitgezogen_als_fehler is mitgezogen
    return auswertung.ebenen[ebene]


def kennzahlen_von(
    ergebnis: Verfahrensergebnis,
    ebene: Ebene,
    *,
    mitgezogen: bool = False,
) -> Kennzahlen:
    """Holt die Kennzahlen einer Ebene und stellt sicher, dass es sie gibt.

    Args:
        ergebnis: Das Ergebnis eines Verfahrens.
        ebene: Die gesuchte Ebene.
        mitgezogen: Schalterstellung ``mitgezogen_als_fehler``.

    Returns:
        Die :class:`~src.evaluation.modell.Kennzahlen` der Ebene.
    """
    auswertung = ebene_von(ergebnis, ebene, mitgezogen=mitgezogen)
    assert auswertung.kennzahlen is not None, auswertung.nicht_auswertbar_grund
    return auswertung.kennzahlen


def gruppe_von(gruppen: Sequence[Gruppenrecall], gruppe: str) -> Gruppenrecall:
    """Sucht eine Gruppe im gruppenweisen Recall.

    Args:
        gruppen: Die Gruppenrecalls einer Ebene.
        gruppe: Gesuchte Fehlerklasse oder Injektionsvariante.

    Returns:
        Den :class:`~src.evaluation.modell.Gruppenrecall` dieser Gruppe.
    """
    treffer = [eintrag for eintrag in gruppen if eintrag.gruppe == gruppe]
    assert len(treffer) == 1, f"{gruppe!r} kommt {len(treffer)} mal vor"
    return treffer[0]
