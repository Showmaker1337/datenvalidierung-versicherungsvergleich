"""Vergleichsverfahren B2: unueberwachte Anomalieerkennung mit ``IsolationForest``.

B2 ist die unueberwachte Gegenprobe des Vergleichs. Es kennt weder den
Regelkatalog noch die Fehlertaxonomie; es sieht ausschliesslich die Zahlenmatrix
des verfaelschten Datensatzes und beantwortet eine einzige Frage: *Welche Zeile
sieht anders aus als die uebrigen?* Der Abstand zwischen dieser Antwort und der
des Regelkatalogs ist eine der Kernaussagen der Arbeit — er beziffert, wie viel
Fachwissen ueber die Domaene beitraegt, das aus der Verteilung allein nicht
ablesbar ist.

Dieses Modul importiert **nichts** aus ``src.rules`` (Abschnitt 1 des
Phasenkontrakts). Ein Blick in den Regelkatalog waere derselbe Zirkelschluss, den
Architekturregel A1 zwischen Injektor und Regel-Engine ausschliesst: Gemessen
wuerde dann nicht mehr die Leistung eines Anomalieverfahrens, sondern die
Uebereinstimmung zweier Implementierungen derselben Bedingung.

Ein Modell je Entitaet
----------------------

Die sieben Entitaeten haben verschiedene Schemata; eine gemeinsame Merkmalsmatrix
gaebe es nur ueber einen Join, und der wuerde Zeilen vervielfachen und damit die
Zaehlung der Satzebene zerstoeren. Es wird deshalb je Entitaet **ein** Modell
gefittet, und die Ergebnisse werden erst auf der Ebene der markierten Zellen und
Zeilen wieder zusammengefuehrt.

Genau ein Fit, genau ein ``score_samples``, sieben Schwellen
------------------------------------------------------------

``contamination`` beeinflusst bei ``IsolationForest`` **nicht** das Modell,
sondern ausschliesslich den Entscheidungs-Offset (``offset_``), gegen den
``decision_function`` die Scores vergleicht. Die Baeume, das Subsampling und damit
jeder einzelne Score sind davon unberuehrt.

Deshalb wird je Entitaet genau einmal gefittet und genau einmal
``score_samples`` aufgerufen. Die sieben Stufen aus :data:`CONTAMINATION_STUFEN`
werden anschliessend als **Schwellen auf dieselben Scores** angewendet:
``schwelle = float(np.percentile(scores, 100 * contamination))``, anomal ist
``score < schwelle``. Das ist genau die Rechnung, die ``IsolationForest`` selbst
fuer ``offset_`` ausfuehrt — nur eben siebenmal statt einmal, ohne den Wald
siebenmal neu zu bauen.

Ein Neufitten je Stufe kostete das Siebenfache an Rechenzeit ohne jeden
inhaltlichen Unterschied. Bei mehreren tausend Laeufen in Phase 6 ist das der
Unterschied zwischen Stunden und Tagen — und damit keine Mikrooptimierung,
sondern die Voraussetzung dafuer, dass das Experiment durchfuehrbar bleibt.

Fehlwerte: auffuellen **und** anzeigen
--------------------------------------

``IsolationForest`` nimmt kein ``NaN`` entgegen. Numerische Spalten werden
deshalb mit dem **Median** der Spalte aufgefuellt, kategoriale bekommen die
eigene Stufe :data:`_FEHLSTUFE`.

Damit allein waere ein fehlender Wert fuer das Verfahren jedoch **unsichtbar** —
und Fehlwerte sind die haeufigste Fehlerklasse dieser Arbeit (F1). Eine mit dem
Median aufgefuellte Zelle liegt per Konstruktion in der Mitte der Verteilung und
ist damit das Gegenteil einer Anomalie; B2 haette bei F1 strukturell einen Recall
nahe null, und zwar als Artefakt der Vorverarbeitung, nicht als Eigenschaft des
Verfahrens.

Jede Spalte mit mindestens einem Fehlwert bekommt deshalb zusaetzlich eine
binaere Indikatorspalte ``<spalte>__fehlt``. Erst sie macht das Fehlen selbst zu
einem Merkmal, ueber das der Wald splitten kann. Die Entscheidung faellt
ausdruecklich **zugunsten der Baseline**: Sie hebt deren Erkennungsleistung, und
ein Vergleich ist nur dann etwas wert, wenn das Vergleichsverfahren in seiner
besten erreichbaren Form antritt.

Spalten ohne Varianz werden entfernt. Sie tragen keine Information, kosten aber
in jedem Baum Rechenzeit.

Merkmale: was einfliesst und was nicht
--------------------------------------

Numerische Felder gehen direkt ein: ``GANZZAHL`` und ``DEZIMAL`` als ``float``
(bei ``DEZIMAL`` ueber ``float(Decimal)`` — nur hier, im Modellraum, ist das
zulaessig; fachlich bleibt Geld ``Decimal``), ``DATUM`` als ``date.toordinal()``,
``ZEITPUNKT`` als Sekunden seit dem 1. Januar 1970. Bewusst **nicht** ueber
``datetime.timestamp()``: Das interpretiert einen naiven Zeitpunkt in der
Zeitzone des ausfuehrenden Rechners und machte das Ergebnis maschinenabhaengig
(Architekturregel A2).

Kategoriale Felder (``TEXT``, ``WAHRHEIT``) werden **ordinal** ueber eine nach
dem Wert sortierte Kategorienliste kodiert. Die Sortierung ist kein Detail,
sondern Teil der Reproduzierbarkeit: Eine Kodierung nach Auftretensreihenfolge
haenge an der Zeilenreihenfolge, eine ueber ein ``set`` an der Hashfolge des
Prozesses. Dass eine ordinale Kodierung eine Ordnung suggeriert, die es fachlich
nicht gibt, ist eine bekannte Schwaeche — sie trifft jedes Anomalieverfahren auf
kategorialen Daten und gehoert in die Diskussion, nicht in eine stille Umgehung.

**Schluesselspalten fliessen nicht ein**: ``row_id`` und alle Spalten auf
``_id``. Eine ordinal kodierte UUID ist Rauschen mit maximaler Kardinalitaet; sie
macht jede Zeile gleich einzigartig und verwaessert das Isolationskriterium. Fuer
die Markierung der Zellen zaehlen sie dagegen mit (siehe naechster Abschnitt).

Die Umrechnung auf die Zellebene benachteiligt B2
--------------------------------------------------

``IsolationForest`` bewertet **Zeilen**, nicht Zellen. Eine als anomal markierte
Zeile markiert deshalb **alle ihre befuellten Zellen** (Rohwert ungleich
Leerstring), einschliesslich der Schluesselspalten: Das Verfahren behauptet, an
dieser Zeile stimme etwas nicht, ohne sagen zu koennen, wo.

Diese Umrechnung ist fuer B2 bei der Precision ungnaedig (eine verfaelschte Zelle
zieht rund zwei Dutzend Fehlalarme nach sich) und beim Recall grosszuegig (wird
die Zeile getroffen, gilt jede ihrer Zellen als gefunden). Beides ist bekannt und
bewusst: Fuer B2 ist die **Satzebene** der Primaervergleich, die Zellebene wird
mitberichtet, damit alle vier Verfahren auf derselben Ebene nebeneinander stehen.
Die Diagnoseguete — "welche Zelle ist es?" — ist hier die gemessene Groesse, kein
Nebeneffekt der Aufbereitung.

Die Stufenwahl ist bewusst optimistisch zugunsten der Baseline
---------------------------------------------------------------

Die verwendete Stufe wird nach der **besten F1 auf der Satzebene** bei
``mitgezogen_als_fehler=False`` gewaehlt; dieselbe Stufe gilt danach fuer alle
Ebenen und beide Schalterstellungen. Dafuer braucht B2 den Ground Truth, den der
Konstruktor optional entgegennimmt.

Das ist ein Zugestaendnis an die Baseline und wird als solches ausgewiesen: Ein
unueberwachtes Verfahren, das seinen Betriebspunkt an der Wahrheit ausrichten
darf, ist gegenueber dem Prototyp im Vorteil, der ohne jede Anpassung antritt.
Faellt B2 auch unter dieser Bedingung deutlich ab, ist das Ergebnis belastbarer,
als wenn man ihm die schlechteste Stufe zuwiese.

``contamination`` wird ausdruecklich **nicht** auf die wahre Fehlerrate gesetzt.
Das waere die Weitergabe genau der Groesse, die das Experiment variiert, und die
gemessene Leistung haenge dann daran, wie gut die Rate geraten wurde — eine
Information, die in der Praxis niemand hat.

Ohne Ground Truth wird die mittlere Stufe :data:`STANDARD_CONTAMINATION`
verwendet und im Ergebnis vermerkt (:meth:`IsolationForestBaseline.stufenwahl`).
Der vollstaendige Sweep steht ueber :meth:`IsolationForestBaseline.sweep` zur
Verfuegung und gehoert in ``metrics.json``: Erst er zeigt, ob das Ergebnis an der
Stufe haengt oder nicht.

Reproduzierbarkeit
------------------

Der Seed kommt aus einer ``SeedSequence``, die dem Konstruktor uebergeben wird
(ueblicherweise ``lauf_seed(master_seed, Strom.MODELL, ...)``). Je Entitaet wird
daraus ueber :func:`~src.common.seeding.teilstrom` ein fester Teilstrom
abgeleitet; die Nummer ist die Position der Entitaet in
:data:`~src.common.serialisierung.ENTITAETEN` und aendert sich nicht mehr.
``random_state`` erhaelt ``int(seed_als_int(seed) % 2**32)``, weil ``sklearn`` nur
ganzzahlige Seeds unterhalb dieser Grenze annimmt.

Weder ``np.random.seed`` noch ein globaler Zustand kommen vor. Zusammen mit den
sortierten Kategorienlisten und der festen Spaltenreihenfolge des Schemas ergibt
derselbe Seed auf denselben Daten bitgleiche Scores (Architekturregel A2).

Die uebrigen Hyperparameter sind die ``sklearn``-Vorgaben und werden nicht
angepasst: ``n_estimators=100``, ``max_samples="auto"``, ``bootstrap=False``.
Eine Hyperparametersuche waere ein zweites Experiment mit eigener Methodik; die
Arbeit vergleicht ein Standardverfahren in Standardeinstellung mit einem
Regelkatalog.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

import numpy as np
import pandas as pd

from src.common.seeding import seed_als_int, teilstrom
from src.common.serialisierung import (
    ENTITAETEN,
    FELDTYP_JE_SPALTE,
    LEER_ROH,
    SPALTEN_JE_ENTITAET,
    Feldtyp,
)
from src.evaluation.metriken import f1, konfusion_mengen, konfusion_zellen, precision, recall
from src.evaluation.modell import SCORE_SPALTEN, VERSTOSS_SPALTEN, AuswertungsFehler

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence

    from numpy.random import SeedSequence
    from numpy.typing import NDArray

    from src.evaluation.ground_truth import GroundTruth
    from src.evaluation.modell import Kontext

__all__ = [
    "B2_REGEL_ID",
    "CONTAMINATION_STUFEN",
    "STANDARD_CONTAMINATION",
    "IsolationForestBaseline",
    "Sweepstufe",
]

#: Regelkennung aller Meldungen dieses Verfahrens.
#:
#: B2 hat nur eine "Regel" — die Zeile weicht ab. Die Regeldiagnose der
#: Auswertung weist B2 deshalb genau eine Zeile aus; auch das ist ein Befund.
B2_REGEL_ID: Final[str] = "B2-anomalie"

#: Die sieben ausgewerteten ``contamination``-Stufen, aufsteigend.
#:
#: Sie sind **Schwellen auf denselben Scores**, kein Modellparameter (siehe
#: Modul-Docstring). Die Reihenfolge ist Teil des Ausgabeformats.
CONTAMINATION_STUFEN: Final[tuple[float, ...]] = (0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2)

#: Stufe, die ohne Ground Truth verwendet wird — die mittlere der sieben.
STANDARD_CONTAMINATION: Final[float] = 0.02

#: Vermerk im Ergebnis: Die Stufe wurde ueber die beste F1 der Satzebene gewaehlt.
_WAHL_UEBER_F1: Final[str] = "beste F1 auf der Satzebene (mitgezogen_als_fehler=False)"

#: Vermerk im Ergebnis: Es lag kein Ground Truth vor, die Vorgabe wurde verwendet.
_WAHL_OHNE_WAHRHEIT: Final[str] = (
    f"ohne Ground Truth: feste Vorgabe contamination={STANDARD_CONTAMINATION}"
)

#: Kategoriale Stufe eines fehlenden Wertes.
_FEHLSTUFE: Final[float] = -1.0

#: Namenszusatz der binaeren Indikatorspalte je Spalte mit Fehlwerten.
_INDIKATOR_SUFFIX: Final[str] = "__fehlt"

#: Bezugspunkt der Zeitpunktkodierung. Fest verdrahtet und nicht der Systemzeit
#: entnommen (Architekturregel A2).
_EPOCHE: Final[pd.Timestamp] = pd.Timestamp("1970-01-01")

#: Obergrenze eines ganzzahligen ``random_state`` in ``sklearn``.
_SEED_MODUL: Final[int] = 2**32

#: ``sklearn``-Vorgabe: Zahl der Baeume.
_N_ESTIMATORS: Final[int] = 100


@dataclass(frozen=True, slots=True)
class Sweepstufe:
    """Ergebnis **einer** ``contamination``-Stufe des Schwellen-Sweeps.

    Attributes:
        contamination: Die Stufe aus :data:`CONTAMINATION_STUFEN`.
        markierte_saetze: Zahl der Zeilen unterhalb der Schwelle.
        markierte_zellen: Zahl der daraus folgenden Zellmarkierungen.
        f1_satz: F1 auf der Satzebene bei ``mitgezogen_als_fehler=False``;
            ``None``, wenn dem Verfahren kein Ground Truth uebergeben wurde.
        f1_zelle: Dasselbe auf der Zellebene, nachrichtlich.
        precision_satz: Precision auf der Satzebene; ``None`` ohne Ground Truth.
        recall_satz: Recall auf der Satzebene; ``None`` ohne Ground Truth.
        gewaehlt: ``True`` fuer die Stufe, mit der
            :meth:`IsolationForestBaseline.erkenne` gemeldet hat.
    """

    contamination: float
    markierte_saetze: int
    markierte_zellen: int
    f1_satz: float | None
    f1_zelle: float | None
    precision_satz: float | None
    recall_satz: float | None
    gewaehlt: bool


@dataclass(frozen=True, slots=True)
class _Uebersprungen:
    """Eine Entitaet, fuer die kein Modell gebildet werden konnte.

    Attributes:
        grund: Klartext, warum. Wird ueber
            :meth:`IsolationForestBaseline.uebersprungene_entitaeten` berichtet
            statt stillschweigend verschluckt.
    """

    grund: str


@dataclass(frozen=True, slots=True)
class _Entitaetslauf:
    """Das gefittete Ergebnis einer Entitaet.

    Attributes:
        entitaet: Tabellenname.
        row_ids: Zeilenkennungen in Zeilenreihenfolge.
        spalten: **Alle** Schemaspalten der Entitaet; Grundlage der
            Zellmarkierung, nicht der Merkmalsmatrix.
        befuellt: Maske ``(Zeile, Spalte)``: Rohwert ungleich Leerstring.
        scores: ``score_samples`` in der Orientierung von ``sklearn`` —
            **kleiner** heisst anomaler.
        schwellen: Je ``contamination``-Stufe die Perzentilschwelle auf
            ``scores``.
    """

    entitaet: str
    row_ids: tuple[int, ...]
    spalten: tuple[str, ...]
    befuellt: NDArray[np.bool_]
    scores: NDArray[np.float64]
    schwellen: Mapping[float, float]


@dataclass(frozen=True, slots=True)
class _Lauf:
    """Das vollstaendige Ergebnis eines Kontexts, einmal berechnet.

    Attributes:
        entitaeten: Ergebnis je modellierter Entitaet, in Schemareihenfolge.
        sweep: Alle sieben Stufen.
        contamination: Die verwendete Stufe.
        stufenwahl: Wie sie zustande kam.
        uebersprungen: Entitaet auf Grund, warum kein Modell gebildet wurde.
    """

    entitaeten: tuple[_Entitaetslauf, ...]
    sweep: tuple[Sweepstufe, ...]
    contamination: float
    stufenwahl: str
    uebersprungen: Mapping[str, str]


# ---------------------------------------------------------------------------
# Merkmalsaufbereitung
# ---------------------------------------------------------------------------


def _ist_leer(wert: Any) -> bool:  # noqa: ANN401 - der Wert kommt aus einer Objektspalte
    """Gibt zurueck, ob ein Wert der typisierten Schicht fehlt."""
    return wert is None or bool(pd.isna(wert))


def _ist_schluessel(spalte: str) -> bool:
    """Gibt zurueck, ob eine Spalte ein Schluessel ist und damit nicht einfliesst.

    Args:
        spalte: Spaltenname.

    Returns:
        ``True`` fuer ``row_id`` und jede Spalte auf ``_id`` (siehe
        Modul-Docstring: eine ordinal kodierte UUID ist Rauschen).
    """
    return spalte == "row_id" or spalte.endswith("_id")


def _numerischer_wert(wert: Any, feldtyp: Feldtyp) -> float | None:  # noqa: ANN401
    """Bildet einen typisierten Einzelwert auf eine Gleitkommazahl ab.

    Args:
        wert: Wert aus der typisierten Schicht.
        feldtyp: Feldtyp der Spalte.

    Returns:
        Die Zahl, oder ``None`` bei einem fehlenden Wert.
    """
    if _ist_leer(wert):
        return None
    if feldtyp is Feldtyp.DATUM:
        return float(wert.toordinal())
    if feldtyp is Feldtyp.ZEITPUNKT:
        return float((pd.Timestamp(wert) - _EPOCHE).total_seconds())
    return float(wert)


def _kodiere_numerisch(
    werte: Sequence[Any], feldtyp: Feldtyp
) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
    """Kodiert eine numerische Spalte und fuellt Fehlwerte mit dem Median.

    Args:
        werte: Werte der typisierten Schicht in Zeilenreihenfolge.
        feldtyp: Feldtyp der Spalte.

    Returns:
        Die kodierte Spalte und die Maske der Fehlwerte. Ist die Spalte
        vollstaendig leer, entsteht eine konstante Spalte; sie faellt danach der
        Varianzpruefung zum Opfer und traegt damit nichts bei.
    """
    roh = [_numerischer_wert(wert, feldtyp) for wert in werte]
    fehlt = np.array([wert is None for wert in roh], dtype=np.bool_)
    vorhanden = [wert for wert in roh if wert is not None]
    median = float(np.median(vorhanden)) if vorhanden else 0.0
    kodiert = np.array([median if wert is None else wert for wert in roh], dtype=np.float64)
    return kodiert, fehlt


def _kodiere_kategorial(werte: Sequence[Any]) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
    """Kodiert eine kategoriale Spalte ordinal ueber eine sortierte Kategorienliste.

    Die Sortierung ist Teil der Reproduzierbarkeit (Modul-Docstring); eine
    Kodierung nach Auftretensreihenfolge waere von der Zeilenreihenfolge
    abhaengig.

    Args:
        werte: Werte der typisierten Schicht in Zeilenreihenfolge.

    Returns:
        Die kodierte Spalte — Fehlwerte tragen :data:`_FEHLSTUFE` — und die Maske
        der Fehlwerte.
    """
    fehlt = np.array([_ist_leer(wert) for wert in werte], dtype=np.bool_)
    kategorien = sorted({wert for wert in werte if not _ist_leer(wert)})
    stufe = {kategorie: float(nummer) for nummer, kategorie in enumerate(kategorien)}
    kodiert = np.array(
        [_FEHLSTUFE if leer else stufe[wert] for wert, leer in zip(werte, fehlt, strict=True)],
        dtype=np.float64,
    )
    return kodiert, fehlt


def _baue_merkmale(
    typisiert: pd.DataFrame, entitaet: str
) -> tuple[tuple[str, ...], NDArray[np.float64]]:
    """Baut die Merkmalsmatrix einer Entitaet.

    Die Spaltenreihenfolge ist die Schemareihenfolge; direkt hinter jeder Spalte
    mit Fehlwerten steht ihre Indikatorspalte. Die Reihenfolge ist fest und geht
    in das Ergebnis des Waldes ein.

    Args:
        typisiert: Typisierte Schicht der Entitaet.
        entitaet: Name der Entitaet.

    Returns:
        Die Namen der verbliebenen Merkmalsspalten und die Matrix. Spalten ohne
        Varianz sind entfernt; bleibt keine uebrig, ist das Namenstupel leer.
    """
    namen: list[str] = []
    spalten: list[NDArray[np.float64]] = []
    for spalte in SPALTEN_JE_ENTITAET[entitaet]:
        if _ist_schluessel(spalte):
            continue
        feldtyp = FELDTYP_JE_SPALTE[spalte]
        werte = list(typisiert[spalte])
        if feldtyp in (Feldtyp.TEXT, Feldtyp.WAHRHEIT):
            kodiert, fehlt = _kodiere_kategorial(werte)
        else:
            kodiert, fehlt = _kodiere_numerisch(werte, feldtyp)
        namen.append(spalte)
        spalten.append(kodiert)
        if bool(fehlt.any()):
            namen.append(f"{spalte}{_INDIKATOR_SUFFIX}")
            spalten.append(fehlt.astype(np.float64))

    behalten = [
        nummer
        for nummer, spalte in enumerate(spalten)
        if spalte.size > 0 and float(spalte.min()) != float(spalte.max())
    ]
    if not behalten:
        return (), np.zeros((len(typisiert), 0), dtype=np.float64)
    matrix = np.column_stack([spalten[nummer] for nummer in behalten])
    return tuple(namen[nummer] for nummer in behalten), matrix


def _befuellt(roh: pd.DataFrame, spalten: Sequence[str]) -> NDArray[np.bool_]:
    """Baut die Maske der befuellten Zellen aus der Rohschicht.

    Befuellt heisst: Rohwert ungleich Leerstring. Das ist dieselbe Definition,
    mit der ``spec/01``, Abschnitt 6 einen leeren Wert beschreibt.

    Args:
        roh: Rohschicht der Entitaet.
        spalten: Spalten in Schemareihenfolge.

    Returns:
        Eine Maske der Form ``(Zeilen, Spalten)``.
    """
    masken = [
        (~roh[spalte].isna() & (roh[spalte] != LEER_ROH)).fillna(value=False).to_numpy(dtype=bool)
        for spalte in spalten
    ]
    if not masken:
        return np.zeros((len(roh), 0), dtype=np.bool_)
    return np.column_stack(masken)


def _row_ids(typisiert: pd.DataFrame, entitaet: str) -> tuple[int, ...]:
    """Liest die Spalte ``row_id`` als Tupel ganzer Zahlen.

    Args:
        typisiert: Typisierte Schicht der Entitaet.
        entitaet: Name der Entitaet, nur fuer die Fehlermeldung.

    Returns:
        Die Zeilenkennungen in Zeilenreihenfolge.

    Raises:
        AuswertungsFehler: Bei einer fehlenden ``row_id``. Sie ist niemals Ziel
            einer Injektion (Architekturregel A3); fehlt sie, ist der Datensatz
            beschaedigt und jede darauf gerechnete Kennzahl wertlos.
    """
    kennungen: list[int] = []
    for zeile, wert in enumerate(typisiert["row_id"]):
        if _ist_leer(wert):
            raise AuswertungsFehler(
                f"{entitaet}: row_id fehlt in Zeile {zeile}. Die Spalte ist niemals Ziel "
                "einer Injektion (A3); der verfaelschte Datensatz ist beschaedigt."
            )
        kennungen.append(int(wert))
    return tuple(kennungen)


# ---------------------------------------------------------------------------
# Modell
# ---------------------------------------------------------------------------


def _scores(matrix: NDArray[np.float64], seed: SeedSequence) -> NDArray[np.float64]:
    """Fittet **einmal** und gibt die Scores von ``score_samples`` zurueck.

    ``contamination`` bleibt auf ``"auto"``: Der daraus berechnete ``offset_``
    wird nicht verwendet, die Schwellen entstehen ausserhalb (Modul-Docstring).

    Args:
        matrix: Merkmalsmatrix der Entitaet.
        seed: Teilstrom dieser Entitaet.

    Returns:
        Die Scores in der Orientierung von ``sklearn``: kleiner heisst anomaler.
    """
    from sklearn.ensemble import IsolationForest  # noqa: PLC0415 - Importkosten nur bei Bedarf

    modell = IsolationForest(
        n_estimators=_N_ESTIMATORS,
        max_samples="auto",
        contamination="auto",
        bootstrap=False,
        random_state=int(seed_als_int(seed) % _SEED_MODUL),
    )
    modell.fit(matrix)
    return np.asarray(modell.score_samples(matrix), dtype=np.float64)


def _schwellen(scores: NDArray[np.float64]) -> Mapping[float, float]:
    """Berechnet die Perzentilschwelle je ``contamination``-Stufe.

    Args:
        scores: Die Scores einer Entitaet.

    Returns:
        Eine unveraenderliche Abbildung Stufe auf Schwelle. Anomal ist
        ``score < schwelle`` — dieselbe Konvention wie bei ``offset_``.
    """
    return MappingProxyType(
        {stufe: float(np.percentile(scores, 100.0 * stufe)) for stufe in CONTAMINATION_STUFEN}
    )


def _anomal(lauf: _Entitaetslauf, contamination: float) -> NDArray[np.bool_]:
    """Gibt die Maske der anomalen Zeilen einer Entitaet zurueck."""
    return np.asarray(lauf.scores < lauf.schwellen[contamination], dtype=np.bool_)


def _markierte_saetze(
    entitaeten: Sequence[_Entitaetslauf], contamination: float
) -> set[tuple[str, int]]:
    """Sammelt die als anomal markierten Zeilen ueber alle Entitaeten."""
    return {
        (lauf.entitaet, row_id)
        for lauf in entitaeten
        for row_id, anomal in zip(lauf.row_ids, _anomal(lauf, contamination), strict=True)
        if anomal
    }


def _markierte_zellen(
    entitaeten: Sequence[_Entitaetslauf], contamination: float
) -> set[tuple[str, int, str]]:
    """Sammelt die befuellten Zellen aller als anomal markierten Zeilen."""
    ergebnis: set[tuple[str, int, str]] = set()
    for lauf in entitaeten:
        for position in np.flatnonzero(_anomal(lauf, contamination)):
            row_id = lauf.row_ids[int(position)]
            ergebnis.update(
                (lauf.entitaet, row_id, lauf.spalten[int(nummer)])
                for nummer in np.flatnonzero(lauf.befuellt[int(position)])
            )
    return ergebnis


# ---------------------------------------------------------------------------
# Schwellen-Sweep
# ---------------------------------------------------------------------------


def _stufe_ohne_wahrheit(contamination: float, saetze: int, zellen: int) -> Sweepstufe:
    """Baut den Sweepeintrag einer Stufe ohne Ground Truth."""
    return Sweepstufe(
        contamination=contamination,
        markierte_saetze=saetze,
        markierte_zellen=zellen,
        f1_satz=None,
        f1_zelle=None,
        precision_satz=None,
        recall_satz=None,
        gewaehlt=contamination == STANDARD_CONTAMINATION,
    )


def _baue_sweep(
    entitaeten: Sequence[_Entitaetslauf], wahrheit: GroundTruth | None
) -> tuple[tuple[Sweepstufe, ...], float, str]:
    """Wertet alle sieben Stufen auf denselben Scores aus und waehlt eine davon.

    Args:
        entitaeten: Die gefitteten Entitaeten.
        wahrheit: Ground Truth des Laufs, oder ``None``.

    Returns:
        Die sieben Stufen, die gewaehlte ``contamination`` und den Vermerk, wie
        sie zustande kam.
    """
    satzwahrheit = set(wahrheit.satzmenge(mitgezogen_als_fehler=False)) if wahrheit else set()
    zellwahrheit = set(wahrheit.zellmenge(mitgezogen_als_fehler=False)) if wahrheit else set()

    stufen: list[Sweepstufe] = []
    for contamination in CONTAMINATION_STUFEN:
        saetze = _markierte_saetze(entitaeten, contamination)
        zellen = _markierte_zellen(entitaeten, contamination)
        if wahrheit is None:
            stufen.append(_stufe_ohne_wahrheit(contamination, len(saetze), len(zellen)))
            continue
        k_satz = konfusion_mengen(saetze, satzwahrheit, wahrheit.universum_saetze)
        k_zelle = konfusion_zellen(zellen, zellwahrheit, wahrheit.universum_zellen)
        p_satz = precision(k_satz)
        r_satz = recall(k_satz)
        stufen.append(
            Sweepstufe(
                contamination=contamination,
                markierte_saetze=len(saetze),
                markierte_zellen=len(zellen),
                f1_satz=f1(p_satz, r_satz),
                f1_zelle=f1(precision(k_zelle), recall(k_zelle)),
                precision_satz=p_satz,
                recall_satz=r_satz,
                gewaehlt=False,
            )
        )

    if wahrheit is None:
        return tuple(stufen), STANDARD_CONTAMINATION, _WAHL_OHNE_WAHRHEIT

    beste = _beste_stufe(stufen)
    gewaehlt = tuple(replace(stufe, gewaehlt=stufe.contamination == beste) for stufe in stufen)
    return gewaehlt, beste, _WAHL_UEBER_F1


def _beste_stufe(stufen: Sequence[Sweepstufe]) -> float:
    """Waehlt die Stufe mit der besten F1 auf der Satzebene.

    Bei Gleichstand gewinnt die **kleinere** ``contamination``: Sie markiert
    weniger Zeilen und ist damit die sparsamere Erklaerung derselben Leistung.
    Die Regel ist deterministisch und damit A2-vertraeglich.

    Args:
        stufen: Alle Stufen in aufsteigender Reihenfolge.

    Returns:
        Die gewaehlte ``contamination``.
    """
    beste = stufen[0]
    for stufe in stufen[1:]:
        wert = stufe.f1_satz if stufe.f1_satz is not None else 0.0
        bisher = beste.f1_satz if beste.f1_satz is not None else 0.0
        if wert > bisher:
            beste = stufe
    return beste.contamination


def _scoretabelle(lauf: _Entitaetslauf) -> pd.DataFrame:
    """Baut die Zellscore-Tabelle einer Entitaet.

    Der Score wird **negiert** ausgegeben: ``sklearn`` liefert kleinere Werte fuer
    anomalere Zeilen, :data:`~src.evaluation.modell.SCORE_SPALTEN` verlangt die
    umgekehrte Orientierung. Nur so zeigt die PR-AUC in die richtige Richtung.

    Args:
        lauf: Ergebnis der Entitaet.

    Returns:
        Einen Datenrahmen mit den Spalten
        :data:`~src.evaluation.modell.SCORE_SPALTEN`.
    """
    zeilen, spalten = np.nonzero(lauf.befuellt)
    kennungen = np.asarray(lauf.row_ids, dtype=np.int64)
    namen = np.asarray(lauf.spalten, dtype=object)
    return pd.DataFrame(
        {
            "entitaet": np.repeat(lauf.entitaet, zeilen.size),
            "row_id": kennungen[zeilen],
            "spalte": namen[spalten],
            "score": -lauf.scores[zeilen],
        }
    )


# ---------------------------------------------------------------------------
# Das Verfahren
# ---------------------------------------------------------------------------


class IsolationForestBaseline:
    """Baseline B2: ``IsolationForest`` je Entitaet, sieben Schwellen auf einem Fit.

    Erfuellt die Protokolle :class:`~src.evaluation.modell.Verfahren` und
    :class:`~src.evaluation.modell.MitZellscore`. Satzbezogene Meldungen liefert
    B2 **nicht**: Es markiert Zeilen ueber ihre Zellen, und
    :class:`~src.evaluation.modell.MitSatzmeldungen` ist dem Prototyp
    vorbehalten, der ein Duplikatpaar als solches benennen kann.

    Der zuletzt ausgewertete Kontext wird zwischengespeichert. Schluessel ist die
    **Objektidentitaet** des Kontexts, nicht sein Inhalt: Ein Vergleich zweier
    Datensaetze waere teurer als das Fitten selbst, und die Pipeline reicht je
    Lauf genau ein Kontextobjekt an :meth:`erkenne`, :meth:`zellscores` und
    :meth:`sweep` weiter. Der Kontext wird dabei referenziert und nicht nur seine
    ``id`` gemerkt — sonst koennte der Speicher freigegeben und dieselbe ``id``
    an ein anderes Objekt vergeben werden.
    """

    name: str = "B2"
    beschreibung: str = (
        "Unueberwachte Anomalieerkennung (sklearn IsolationForest), je Entitaet ein Modell"
    )
    lokalisiert_zellen: bool = True
    in_inferenzstatistik: bool = True

    def __init__(self, seed_modell: SeedSequence, *, wahrheit: GroundTruth | None = None) -> None:
        """Legt das Verfahren an.

        Args:
            seed_modell: Zufallsstrom des Modells, ueblicherweise
                ``lauf_seed(master_seed, Strom.MODELL, *faktoren)``. Je Entitaet
                wird daraus ein fester Teilstrom abgeleitet.
            wahrheit: Ground Truth des Laufs. Mit Angabe wird die
                ``contamination``-Stufe ueber die beste F1 der Satzebene gewaehlt
                — eine bewusst optimistische Einstellung zugunsten der Baseline
                (Modul-Docstring). Ohne Angabe gilt
                :data:`STANDARD_CONTAMINATION`.
        """
        self._seed = seed_modell
        self._wahrheit = wahrheit
        self._zwischenspeicher: tuple[Kontext, _Lauf] | None = None

    # -- oeffentliche Schnittstelle -----------------------------------------

    def erkenne(self, kontext: Kontext) -> pd.DataFrame:
        """Meldet die Zellen aller als anomal markierten Zeilen.

        Eine markierte Zeile ergibt **eine** ``verstoss_id`` und je befuellter
        Zelle eine Meldezeile. Die Kennung ist ``B2-anomalie#<laufende Nummer>``,
        vergeben in Schema- und Zeilenreihenfolge und damit reproduzierbar.

        Args:
            kontext: Pruefkontext ueber beide Datenschichten des verfaelschten
                Datensatzes.

        Returns:
            Einen Datenrahmen mit den Spalten
            :data:`~src.evaluation.modell.VERSTOSS_SPALTEN`.
        """
        lauf = self._lauf(kontext)
        zeilen: list[tuple[str, int, str, str, str, str]] = []
        nummer = 0
        for teil in lauf.entitaeten:
            schwelle = teil.schwellen[lauf.contamination]
            for position in np.flatnonzero(_anomal(teil, lauf.contamination)):
                nummer += 1
                verstoss_id = f"{B2_REGEL_ID}#{nummer:06d}"
                meldung = (
                    f"Anomaliescore {float(teil.scores[position]):.6f} unterschreitet die "
                    f"Schwelle {schwelle:.6f} bei contamination {lauf.contamination:g}"
                )
                row_id = teil.row_ids[int(position)]
                zeilen.extend(
                    (
                        teil.entitaet,
                        row_id,
                        teil.spalten[int(index)],
                        B2_REGEL_ID,
                        verstoss_id,
                        meldung,
                    )
                    for index in np.flatnonzero(teil.befuellt[int(position)])
                )
        return pd.DataFrame(zeilen, columns=list(VERSTOSS_SPALTEN))

    def zellscores(self, kontext: Kontext) -> pd.DataFrame:
        """Gibt den Anomaliescore je bewerteter Zelle zurueck.

        Bewertet ist jede befuellte Zelle jeder modellierten Zeile — dieselbe
        Menge, aus der :meth:`erkenne` schoepft. Damit bezieht sich die PR-AUC auf
        genau die Einheiten, ueber die B2 ueberhaupt eine Aussage macht.

        Args:
            kontext: Pruefkontext ueber beide Datenschichten.

        Returns:
            Einen Datenrahmen mit den Spalten
            :data:`~src.evaluation.modell.SCORE_SPALTEN`; hoehere Werte bedeuten
            "anomaler" (siehe :func:`_scoretabelle`).
        """
        lauf = self._lauf(kontext)
        teile = [_scoretabelle(teil) for teil in lauf.entitaeten]
        if not teile:
            return pd.DataFrame([], columns=list(SCORE_SPALTEN))
        return pd.concat(teile, ignore_index=True)

    def sweep(self) -> tuple[Sweepstufe, ...]:
        """Gibt den vollstaendigen Schwellen-Sweep des zuletzt bewerteten Laufs zurueck.

        Returns:
            Alle sieben Stufen in aufsteigender Reihenfolge; genau eine traegt
            ``gewaehlt=True``.

        Raises:
            AuswertungsFehler: Wenn noch kein Kontext bewertet wurde. Bewusst
                kein leeres Tupel: Das waere von "der Sweep ist leer" nicht zu
                unterscheiden.
        """
        return self._fertiger_lauf().sweep

    def gewaehlte_contamination(self) -> float:
        """Gibt die verwendete ``contamination``-Stufe zurueck.

        Returns:
            Die Stufe, mit der :meth:`erkenne` gemeldet hat.

        Raises:
            AuswertungsFehler: Wenn noch kein Kontext bewertet wurde.
        """
        return self._fertiger_lauf().contamination

    def stufenwahl(self) -> str:
        """Gibt den Vermerk zurueck, wie die Stufe zustande kam.

        Returns:
            Einen Klartextvermerk. Er gehoert in ``metrics.json``: Ohne ihn ist
            nicht erkennbar, ob die Stufe an der Wahrheit ausgerichtet wurde oder
            die Vorgabe ist.

        Raises:
            AuswertungsFehler: Wenn noch kein Kontext bewertet wurde.
        """
        return self._fertiger_lauf().stufenwahl

    def uebersprungene_entitaeten(self) -> Mapping[str, str]:
        """Gibt die Entitaeten zurueck, fuer die kein Modell gebildet wurde.

        Eine Entitaet ohne Zeilen oder ohne eine einzige Merkmalsspalte mit
        Varianz liefert keinen Score. Das wird berichtet und nicht verschwiegen:
        Sonst waere ihre Abwesenheit in den Ergebnissen von "nichts gefunden"
        nicht zu unterscheiden.

        Returns:
            Eine Abbildung Entitaet auf den Grund.

        Raises:
            AuswertungsFehler: Wenn noch kein Kontext bewertet wurde.
        """
        return self._fertiger_lauf().uebersprungen

    # -- Innenleben ---------------------------------------------------------

    def _fertiger_lauf(self) -> _Lauf:
        """Gibt den zwischengespeicherten Lauf zurueck.

        Returns:
            Den Lauf des zuletzt bewerteten Kontexts.

        Raises:
            AuswertungsFehler: Wenn noch kein Kontext bewertet wurde.
        """
        if self._zwischenspeicher is None:
            raise AuswertungsFehler(
                "B2 wurde noch nicht ausgefuehrt. Erst erkenne(kontext) aufrufen, dann "
                "sweep(), gewaehlte_contamination(), stufenwahl() oder "
                "uebersprungene_entitaeten()."
            )
        return self._zwischenspeicher[1]

    def _lauf(self, kontext: Kontext) -> _Lauf:
        """Berechnet den Lauf oder gibt den zwischengespeicherten zurueck."""
        gespeichert = self._zwischenspeicher
        if gespeichert is not None and gespeichert[0] is kontext:
            return gespeichert[1]
        lauf = self._berechne(kontext)
        self._zwischenspeicher = (kontext, lauf)
        return lauf

    def _berechne(self, kontext: Kontext) -> _Lauf:
        """Fittet je Entitaet einmal und wertet den Schwellen-Sweep aus."""
        entitaeten: list[_Entitaetslauf] = []
        uebersprungen: dict[str, str] = {}
        for nummer, entitaet in enumerate(ENTITAETEN):
            ergebnis = self._entitaet(kontext, entitaet, nummer)
            if isinstance(ergebnis, _Uebersprungen):
                uebersprungen[entitaet] = ergebnis.grund
            else:
                entitaeten.append(ergebnis)

        sweep, contamination, stufenwahl = _baue_sweep(entitaeten, self._wahrheit)
        return _Lauf(
            entitaeten=tuple(entitaeten),
            sweep=sweep,
            contamination=contamination,
            stufenwahl=stufenwahl,
            uebersprungen=MappingProxyType(uebersprungen),
        )

    def _entitaet(
        self, kontext: Kontext, entitaet: str, nummer: int
    ) -> _Entitaetslauf | _Uebersprungen:
        """Bildet das Modell einer Entitaet.

        Args:
            kontext: Pruefkontext.
            entitaet: Name der Entitaet.
            nummer: Position in :data:`~src.common.serialisierung.ENTITAETEN`;
                zugleich die feste Nummer des Teilstroms.

        Returns:
            Das Ergebnis, oder den Grund, warum kein Modell gebildet wurde.

        Raises:
            AuswertungsFehler: Wenn die Entitaet in einer der beiden Schichten
                fehlt. Ein stillschweigend eingesetzter leerer Rahmen wuerde die
                Grundgesamtheit verfaelschen, ohne dass es jemandem auffiele.
        """
        typisiert = _hole(kontext.typed, entitaet, "typisierten Schicht")
        roh = _hole(kontext.raw, entitaet, "Rohschicht")
        if len(typisiert) == 0:
            return _Uebersprungen("keine Zeilen")
        namen, matrix = _baue_merkmale(typisiert, entitaet)
        if not namen:
            return _Uebersprungen("keine Merkmalsspalte mit Varianz")

        scores = _scores(matrix, teilstrom(self._seed, nummer))
        spalten = SPALTEN_JE_ENTITAET[entitaet]
        return _Entitaetslauf(
            entitaet=entitaet,
            row_ids=_row_ids(typisiert, entitaet),
            spalten=spalten,
            befuellt=_befuellt(roh, spalten),
            scores=scores,
            schwellen=_schwellen(scores),
        )


def _hole(quelle: Mapping[str, pd.DataFrame], entitaet: str, was: str) -> pd.DataFrame:
    """Holt einen Datenrahmen aus einer Schicht des Kontexts.

    Args:
        quelle: Die Schicht.
        entitaet: Name der Entitaet.
        was: Bezeichnung der Schicht fuer die Fehlermeldung.

    Returns:
        Den Datenrahmen.

    Raises:
        AuswertungsFehler: Wenn die Entitaet fehlt.
    """
    if entitaet not in quelle:
        raise AuswertungsFehler(
            f"Entitaet {entitaet!r} fehlt in der {was} des Kontexts. "
            f"Vorhanden sind: {sorted(quelle)}"
        )
    return quelle[entitaet]
