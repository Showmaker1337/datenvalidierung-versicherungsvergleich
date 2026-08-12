"""Orchestrierung der Auswertung: Verfahren ausfuehren, messen, bewerten.

Dieses Modul ist der Ablauf und nicht die Rechnung. Die Kennzahlen stehen in
:mod:`src.evaluation.metriken`, die Wahrheitsmengen in
:mod:`src.evaluation.ground_truth`, die Ausgabeformate in
:mod:`src.evaluation.langformat`. Hier steht, in welcher Reihenfolge das
zusammenkommt — und vier Entscheidungen darueber, die das Ergebnis beeinflussen.

Gemessen wird der ganze Aufruf, nicht nur ``erkenne``
------------------------------------------------------

:func:`fuehre_aus` schliesst Laufzeit und Speicher um **alle** Aufrufe des
Verfahrens: ``erkenne``, und wo vorhanden ``satzmeldungen`` und ``zellscores``.
Der Grund ist die Vergleichbarkeit. Die drei Methoden sind keine drei Arbeiten,
sondern drei Fragen an ein Ergebnis: Der Prototyp laesst den Katalog einmal
laufen und beantwortet die zweite Frage aus seinem Zwischenspeicher, B2 fittet
einmal und liest die Scores derselben Matrix ab. Wuerde nur ``erkenne`` gemessen,
haenge die Laufzeit eines Verfahrens daran, welche Zusatzprotokolle es erfuellt
und in welcher Reihenfolge die Pipeline sie abfragt — eine Messgroesse ueber die
Aufrufreihenfolge, nicht ueber das Verfahren.

Der Speicher wird ueber ``tracemalloc`` als **Spitzenwert** gemessen, nicht als
Endstand: Interessant ist, wie viel ein Verfahren zur Laufzeit braucht, nicht wie
viel danach noch belegt ist. ``tracemalloc`` verlangsamt den Lauf spuerbar — es
protokolliert jede Allokation —, deshalb ist die Messung ueber
``messe_speicher=False`` abschaltbar. In Phase 6 mit mehreren tausend Laeufen ist
sie das auch: Der Speicherbedarf ist eine Eigenschaft des Verfahrens und der
Datensatzgroesse, keine der Fehlerrate, und muss nicht tausendfach wiederholt
werden.

Beide Schalterstellungen werden immer gerechnet
------------------------------------------------

Je Verfahren entstehen **zwei** :class:`~src.evaluation.modell.Auswertung` —
``mitgezogen_als_fehler=False`` und ``True``. Die Wahl steht nicht in einem
Parameter dieses Moduls, weil sie keine Laufoption ist, sondern eine
methodische Festlegung mit einer Gegenrechnung (``spec/03``, Abschnitt 2;
:mod:`src.evaluation.metriken`, Abschnitt 6). Wer nur eine der beiden Zahlen
persistiert, muss fuer die andere alle Laeufe wiederholen.

Nicht lokalisierende Verfahren bekommen einen Grund, keine Null
----------------------------------------------------------------

Ist :attr:`~src.evaluation.modell.Verfahren.lokalisiert_zellen` ``False``, sind
alle drei Ebenen mit ``kennzahlen=None`` und
:data:`NICHT_LOKALISIERT_GRUND` besetzt — auch die gruppenweisen Recalls bleiben
leer. Das betrifft B3. Eine Konfusionsmatrix voller Nullen waere an dieser Stelle
kein konservativer Wert, sondern eine Falschaussage: Sie behauptete, das
Verfahren habe nichts gefunden, obwohl es sehr wohl Verstoesse meldet — nur ohne
Zeilenbezug, und damit nicht zuordenbar. Der Befund von B3 ist die Diagnoseguete
selbst; er steht in ``results/b3_framework.json`` und nicht in einer
Konfusionsmatrix.

Der Recall der Constraint-Ebene wird nicht neu gerechnet
---------------------------------------------------------

Auf der Constraint-Ebene wechselt nur die Precision ihre Einheit; ``fn`` bleibt
die Zahl der Wahrheits**zellen**, die in keinem gemeldeten Verstoss vorkommen
(:mod:`src.evaluation.metriken`, Abschnitt 8). Die gruppenweisen Recalls der
Constraint-Ebene sind damit **dieselben** wie auf der Zellebene. Sie werden
einmal gerechnet und in beide Ebenen uebernommen, statt zweimal dasselbe zu
zaehlen — der Einheitenbruch ist so auch im Quelltext sichtbar und nicht in zwei
Rechenwegen versteckt, die zufaellig dasselbe ergeben muessen.
"""

from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

import pandas as pd

from src.common.serialisierung import ENTITAETEN
from src.evaluation.metriken import (
    STANDARD_ALPHA,
    gruppenrecall,
    kennzahlen,
    konfusion_constraints,
    konfusion_mengen,
    kreuztabelle,
    macro_recall,
    pr_auc,
    regeldiagnose,
    variantengewichteter_klassenrecall,
)
from src.evaluation.modell import (
    ROW_ID_OHNE_BEZUG,
    SATZ_SPALTEN,
    VERSTOSS_SPALTEN,
    Auswertung,
    AuswertungsFehler,
    Ebene,
    Ebenenauswertung,
    Kennzahlen,
    Laufmessung,
    MitSatzmeldungen,
    MitZellscore,
    Verfahrensergebnis,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Iterable, Mapping, Sequence

    from src.evaluation.ground_truth import GroundTruth
    from src.evaluation.modell import Gruppenrecall, Kontext, Verfahren

__all__ = [
    "NICHT_LOKALISIERT_GRUND",
    "bewerte",
    "fuehre_aus",
]

#: Begruendung, die ein Verfahren ohne Zeilenbezug auf allen Ebenen traegt.
#:
#: Bewusst ein Satz und keine Null: Eine Null in der Ergebnistabelle liest sich
#: wie "hat nichts gefunden", der Satz sagt "kann nicht gemessen werden, und das
#: ist der Befund".
NICHT_LOKALISIERT_GRUND: Final[str] = (
    "Der Report des Frameworks nennt keine Zeile; eine Konfusionsmatrix auf Zell-, "
    "Constraint- oder Satzebene ist damit nicht bildbar. Das ist das Messergebnis der "
    "Kennzahl Diagnoseguete, kein fehlender Wert."
)

#: Zeilen, auf die Laufzeit und Speicher normiert werden.
_NORMIERUNG: Final[int] = 1000

#: Name der technischen Zeilenkennung.
#:
#: Sie ist nach Architekturregel A3 niemals Ziel einer Injektion. Eine Markierung
#: auf ihr ist deshalb ein garantierter Fehlalarm und wird getrennt gezaehlt
#: (:attr:`~src.evaluation.modell.Verfahrensergebnis.markierte_zellen_row_id`).
_ROW_ID: Final[str] = "row_id"

#: Bytes je Mebibyte.
_MEBIBYTE: Final[float] = 1024.0 * 1024.0


# ---------------------------------------------------------------------------
# Ausfuehren und messen
# ---------------------------------------------------------------------------


def _zeilen_gesamt(kontext: Kontext) -> int:
    """Zaehlt die Zeilen aller Entitaeten des verfaelschten Datensatzes.

    Args:
        kontext: Pruefkontext ueber beide Datenschichten.

    Returns:
        Die Summe der Zeilenzahlen in Schemareihenfolge.

    Raises:
        AuswertungsFehler: Wenn eine Entitaet fehlt oder der Datensatz leer ist.
            Ohne Zeilen gibt es keine normierte Laufzeit, und eine Division durch
            null stillschweigend zu einer Null zu machen hiesse, eine Messung zu
            erfinden.
    """
    fehlend = [name for name in ENTITAETEN if name not in kontext.raw]
    if fehlend:
        raise AuswertungsFehler(
            f"Der Rohschicht des Kontexts fehlen die Entitaeten {fehlend}. Vorhanden sind "
            f"{sorted(kontext.raw)}."
        )
    gesamt = sum(len(kontext.raw[name]) for name in ENTITAETEN)
    if gesamt == 0:
        raise AuswertungsFehler(
            "Der auszuwertende Datensatz hat keine einzige Zeile. Laufzeit und Speicher "
            "lassen sich darauf nicht normieren."
        )
    return gesamt


def fuehre_aus(
    verfahren: Verfahren,
    kontext: Kontext,
    *,
    messe_speicher: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, Laufmessung]:
    """Fuehrt ein Verfahren auf einem Kontext aus und misst dabei Laufzeit und Speicher.

    Gemessen wird der vollstaendige Aufruf einschliesslich der Zusatzprotokolle
    (siehe Modul-Docstring).

    Args:
        verfahren: Das auszufuehrende Verfahren.
        kontext: Pruefkontext ueber beide Datenschichten des **verfaelschten**
            Datensatzes.
        messe_speicher: Schaltet die ``tracemalloc``-Messung ein. Sie verlangsamt
            den Lauf spuerbar und ist deshalb in Phase 6 abschaltbar; ohne sie
            bleiben die beiden Speicherfelder der Messung ``None``.

    Returns:
        Ein Tupel aus Zellmeldungen, satzbezogenen Meldungen, Zellscores und der
        :class:`~src.evaluation.modell.Laufmessung`. Die satzbezogenen Meldungen
        sind ein leerer Rahmen mit den Spalten
        :data:`~src.evaluation.modell.SATZ_SPALTEN`, wenn das Verfahren das
        Zusatzprotokoll nicht erfuellt; die Zellscores sind dann ``None``.

    Raises:
        AuswertungsFehler: Wenn der Datensatz leer ist oder eine Entitaet fehlt.
    """
    zeilen = _zeilen_gesamt(kontext)
    schon_aktiv = tracemalloc.is_tracing()
    if messe_speicher and not schon_aktiv:
        tracemalloc.start()

    spitze = 0
    beginn = time.perf_counter()
    try:
        if messe_speicher:
            tracemalloc.reset_peak()
        meldungen = verfahren.erkenne(kontext)
        saetze = (
            verfahren.satzmeldungen(kontext)
            if isinstance(verfahren, MitSatzmeldungen)
            else pd.DataFrame(columns=list(SATZ_SPALTEN))
        )
        scores = verfahren.zellscores(kontext) if isinstance(verfahren, MitZellscore) else None
        if messe_speicher:
            _, spitze = tracemalloc.get_traced_memory()
    finally:
        if messe_speicher and not schon_aktiv:
            tracemalloc.stop()
    dauer = time.perf_counter() - beginn

    speicher = spitze / _MEBIBYTE if messe_speicher else None
    messung = Laufmessung(
        laufzeit_s=dauer,
        laufzeit_s_je_1000_zeilen=dauer / zeilen * _NORMIERUNG,
        speicher_mb=speicher,
        speicher_mb_je_1000_zeilen=None if speicher is None else speicher / zeilen * _NORMIERUNG,
        zeilen_gesamt=zeilen,
    )
    return meldungen, saetze, scores, messung


# ---------------------------------------------------------------------------
# Aufbereitung der Meldungen
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Meldungssicht:
    """Die aus den Meldungen eines Verfahrens abgeleiteten Sichten.

    Einmal gebildet und fuer beide Schalterstellungen verwendet: Die Meldungen
    haengen nicht daran, welche Zellen als Wahrheit gelten.

    Attributes:
        markierte_zellen: Vereinigungsmenge der markierten Tripel.
        markierte_saetze: Vereinigungsmenge der markierten Zeilen, einschliesslich
            der Zeilen aus den satzbezogenen Meldungen.
        zellen_je_regel: Je ``regel_id`` die gemeldeten Zellen in Meldereihenfolge.
        zellen_je_verstoss: Je ``verstoss_id`` die gemeldeten Zellen.
        meldungen_gesamt: Zeilen des Meldungsrahmens vor der Vereinigung.
        ohne_zeilenbezug: Meldungen mit
            :data:`~src.evaluation.modell.ROW_ID_OHNE_BEZUG`.
    """

    markierte_zellen: frozenset[tuple[str, int, str]]
    markierte_saetze: frozenset[tuple[str, int]]
    zellen_je_regel: Mapping[str, tuple[tuple[str, int, str], ...]]
    zellen_je_verstoss: Mapping[str, tuple[tuple[str, int, str], ...]]
    meldungen_gesamt: int
    ohne_zeilenbezug: int


def _pruefe_spalten(rahmen: pd.DataFrame, pflicht: Sequence[str], was: str) -> None:
    """Stellt sicher, dass ein Meldungsrahmen das vereinbarte Format hat.

    Args:
        rahmen: Der Rahmen.
        pflicht: Erwartete Spalten.
        was: Bezeichnung fuer die Fehlermeldung.

    Raises:
        AuswertungsFehler: Wenn eine Spalte fehlt.
    """
    fehlend = [spalte for spalte in pflicht if spalte not in rahmen.columns]
    if fehlend:
        raise AuswertungsFehler(
            f"Dem {was} fehlen die Spalten {fehlend}. Vorhanden sind {list(rahmen.columns)}."
        )


def _baue_sicht(meldungen: pd.DataFrame, saetze: pd.DataFrame) -> _Meldungssicht:
    """Leitet aus den Meldungen eines Verfahrens alle benoetigten Sichten ab.

    Die Vereinigung mehrfach gemeldeter Zellen findet **hier** statt und nicht in
    den Adaptern: Sie ist fuer alle vier Verfahren dieselbe Operation und darf
    nicht in vier Adaptern je einmal implementiert sein
    (:mod:`src.evaluation.metriken`, Abschnitt 1).

    Args:
        meldungen: Zellmeldungen mit den Spalten
            :data:`~src.evaluation.modell.VERSTOSS_SPALTEN`.
        saetze: Satzbezogene Meldungen mit den Spalten
            :data:`~src.evaluation.modell.SATZ_SPALTEN`.

    Returns:
        Die :class:`_Meldungssicht`.

    Raises:
        AuswertungsFehler: Wenn ein Rahmen das Format verletzt oder eine Meldung
            eine negative ``row_id`` ausserhalb von
            :data:`~src.evaluation.modell.ROW_ID_OHNE_BEZUG` traegt.
    """
    _pruefe_spalten(meldungen, VERSTOSS_SPALTEN, "Meldungsrahmen des Verfahrens")
    _pruefe_spalten(saetze, SATZ_SPALTEN, "Satzmeldungsrahmen des Verfahrens")

    markiert: dict[tuple[str, int, str], None] = {}
    je_regel: dict[str, list[tuple[str, int, str]]] = {}
    je_verstoss: dict[str, list[tuple[str, int, str]]] = {}
    ohne = 0

    spalten = ["entitaet", "row_id", "spalte", "regel_id", "verstoss_id"]
    for entitaet, row_id, spalte, regel_id, verstoss_id in meldungen[spalten].itertuples(
        index=False, name=None
    ):
        kennung = int(row_id)
        if kennung == ROW_ID_OHNE_BEZUG:
            ohne += 1
            continue
        if kennung < 0:
            raise AuswertungsFehler(
                f"Meldung mit unzulaessiger row_id {kennung} in {entitaet}.{spalte} "
                f"({regel_id}). Die einzige zulaessige negative Kennung ist "
                f"{ROW_ID_OHNE_BEZUG} fuer Meldungen ohne Zeilenbezug."
            )
        zelle = (str(entitaet), kennung, str(spalte))
        markiert.setdefault(zelle, None)
        je_regel.setdefault(str(regel_id), []).append(zelle)
        je_verstoss.setdefault(str(verstoss_id), []).append(zelle)

    zeilen = {(entitaet, row_id) for entitaet, row_id, _ in markiert}
    for entitaet, betroffene in saetze[["entitaet", "betroffene_row_ids"]].itertuples(
        index=False, name=None
    ):
        zeilen.update((str(entitaet), int(kennung)) for kennung in betroffene)

    return _Meldungssicht(
        markierte_zellen=frozenset(markiert),
        markierte_saetze=frozenset(zeilen),
        zellen_je_regel=MappingProxyType(
            {regel_id: tuple(zellen) for regel_id, zellen in je_regel.items()}
        ),
        zellen_je_verstoss=MappingProxyType(
            {verstoss_id: tuple(zellen) for verstoss_id, zellen in je_verstoss.items()}
        ),
        meldungen_gesamt=len(meldungen),
        ohne_zeilenbezug=ohne,
    )


def _scorepaare(
    scores: pd.DataFrame | None,
    wahrheit: frozenset[tuple[str, int, str]],
) -> tuple[list[float], list[bool]] | None:
    """Bereitet die Zellscores fuer die PR-AUC auf.

    Args:
        scores: Scoretabelle mit den Spalten
            :data:`~src.evaluation.modell.SCORE_SPALTEN`, oder ``None``.
        wahrheit: Zellwahrheit der jeweiligen Schalterstellung.

    Returns:
        Score und Wahrheitswert je bewerteter Zelle, oder ``None``, wenn das
        Verfahren keinen Score liefert. Fuer den Prototyp, B0 und B3 wird
        ausdruecklich **kein** Pseudo-Score erfunden
        (:mod:`src.evaluation.metriken`, Abschnitt 4).
    """
    if scores is None:
        return None
    werte: list[float] = []
    wahr: list[bool] = []
    for entitaet, row_id, spalte, score in scores[
        ["entitaet", "row_id", "spalte", "score"]
    ].itertuples(index=False, name=None):
        werte.append(float(score))
        wahr.append((str(entitaet), int(row_id), str(spalte)) in wahrheit)
    return werte, wahr


# ---------------------------------------------------------------------------
# Aufbereitung der Wahrheit
# ---------------------------------------------------------------------------


def _je_gruppe[Einheit](paare: Iterable[tuple[str, Einheit]]) -> dict[str, list[Einheit]]:
    """Gruppiert Wahrheitseinheiten nach ihrer Gruppenkennung.

    Args:
        paare: Paare aus Gruppenkennung und Einheit, in fester Reihenfolge.

    Returns:
        Je Gruppe die Einheiten in Eingabereihenfolge. Bewusst ueber eine Liste
        und nicht ueber eine Menge gesammelt: Die Reihenfolge ist Teil der
        Reproduzierbarkeit (Architekturregel A2); die Entdopplung uebernimmt
        :func:`~src.evaluation.metriken.gruppenrecall`.
    """
    ergebnis: dict[str, list[Einheit]] = {}
    for gruppe, einheit in paare:
        ergebnis.setdefault(gruppe, []).append(einheit)
    return ergebnis


def _klasse_je_variante(wahrheit: GroundTruth) -> dict[str, str]:
    """Bildet die Zuordnung Injektionsvariante auf Fehlerklasse aus dem Ground Truth.

    Die Zuordnung wird **nicht** aus der Variantenkennung geparst: Ein ``split``
    am Bindestrich waere eine zweite, stille Definition derselben Zuordnung
    (:func:`~src.evaluation.metriken.variantengewichteter_klassenrecall`).
    Varianten mit dem Kontingent 0 tauchen deshalb hier nicht auf — sie stehen im
    Manifest, aber in keiner Logzeile.

    Args:
        wahrheit: Ground Truth des Laufs.

    Returns:
        Je Variante ihre Fehlerklasse.
    """
    zuordnung: dict[str, str] = {}
    for zelle in wahrheit.zellen:
        zuordnung.setdefault(zelle.injektor_variante_id, zelle.fehlerklasse)
    for satz in wahrheit.saetze:
        zuordnung.setdefault(satz.injektor_variante_id, satz.fehlerklasse)
    return zuordnung


def _variantengewichtet(
    varianten: Sequence[Gruppenrecall],
    klasse_je_variante: Mapping[str, str],
    klassen: Sequence[str],
) -> Mapping[str, float]:
    """Bildet den variantengewichteten Klassenrecall ueber die besetzten Varianten.

    Varianten ohne Eintrag im Ground Truth werden vorher entfernt. Das sind genau
    die Varianten mit dem Kontingent 0, die aus dem Manifest in die Tabellen
    uebernommen wurden, damit sie sichtbar bleiben; sie haben ``n = 0`` und gingen
    in ein ungewichtetes Mittel der besetzten Varianten ohnehin nicht ein. Ihre
    Klasse zu erfinden, um sie durch die Pruefung zu bringen, waere genau der
    ``split`` am Bindestrich, den :mod:`src.evaluation.metriken` ausschliesst.

    Args:
        varianten: Recall je Variante.
        klasse_je_variante: Zuordnung aus dem Ground Truth.
        klassen: Auszuweisende Fehlerklassen.

    Returns:
        Je Klasse das ungewichtete Mittel ihrer Variantenrecalls.
    """
    bekannt = [eintrag for eintrag in varianten if eintrag.gruppe in klasse_je_variante]
    return variantengewichteter_klassenrecall(bekannt, klasse_je_variante, klassen=klassen)


def _nicht_auswertbar(ebene: Ebene) -> Ebenenauswertung:
    """Baut die Auswertung einer Ebene, auf der nichts messbar ist.

    Args:
        ebene: Die betroffene Ebene.

    Returns:
        Eine Auswertung ohne Kennzahlen und ohne gruppenweise Recalls, aber mit
        :data:`NICHT_LOKALISIERT_GRUND`.
    """
    return Ebenenauswertung(
        ebene=ebene,
        kennzahlen=None,
        nicht_auswertbar_grund=NICHT_LOKALISIERT_GRUND,
        recall_je_klasse=(),
        recall_je_variante=(),
        recall_variantengewichtet_je_klasse=MappingProxyType({}),
        macro_recall_klassen=None,
        macro_recall_varianten=None,
    )


# ---------------------------------------------------------------------------
# Die Auswertung eines Verfahrens
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Ebenenteile:
    """Die gemeinsamen Bestandteile einer Ebenenauswertung.

    Attributes:
        recall_je_klasse: Recall je Fehlerklasse.
        recall_je_variante: Recall je Injektionsvariante.
        variantengewichtet: Variantengewichteter Klassenrecall.
    """

    recall_je_klasse: tuple[Gruppenrecall, ...]
    recall_je_variante: tuple[Gruppenrecall, ...]
    variantengewichtet: Mapping[str, float]


def _ebenenteile[Einheit](
    einheiten_je_klasse: Mapping[str, Sequence[Einheit]],
    einheiten_je_variante: Mapping[str, Sequence[Einheit]],
    gefunden: frozenset[Einheit],
    wahrheit: GroundTruth,
    klasse_je_variante: Mapping[str, str],
) -> _Ebenenteile:
    """Berechnet die gruppenweisen Recalls einer Ebene.

    Args:
        einheiten_je_klasse: Wahrheitseinheiten je Fehlerklasse.
        einheiten_je_variante: Wahrheitseinheiten je Variante.
        gefunden: Vom Verfahren markierte Einheiten dieser Ebene.
        wahrheit: Ground Truth; liefert die auszuweisenden Klassen und Varianten
            einschliesslich derer mit ``n = 0``.
        klasse_je_variante: Zuordnung Variante auf Klasse.

    Returns:
        Die :class:`_Ebenenteile`.
    """
    je_klasse = gruppenrecall(
        einheiten_je_klasse, gefunden, gruppen=wahrheit.klassen, alpha=STANDARD_ALPHA
    )
    je_variante = gruppenrecall(
        einheiten_je_variante, gefunden, gruppen=wahrheit.varianten, alpha=STANDARD_ALPHA
    )
    return _Ebenenteile(
        recall_je_klasse=je_klasse,
        recall_je_variante=je_variante,
        variantengewichtet=_variantengewichtet(je_variante, klasse_je_variante, wahrheit.klassen),
    )


def _als_ebenenauswertung(
    ebene: Ebene,
    kennzahlen_der_ebene: Kennzahlen,
    teile: _Ebenenteile,
) -> Ebenenauswertung:
    """Setzt eine Ebenenauswertung aus Kennzahlen und Gruppenteilen zusammen.

    Die beiden Macro-Mittel entstehen hier und nicht in
    :func:`_ebenenteile`: Sie sind eine Aggregation ueber die Gruppenrecalls
    derselben Ebene und haetten in den geteilten Teilen der Zell- und der
    Constraint-Ebene sonst zweimal denselben Wert.

    Args:
        ebene: Die ausgewertete Ebene.
        kennzahlen_der_ebene: Die Kennzahlen der Ebene.
        teile: Die gruppenweisen Recalls.

    Returns:
        Die :class:`~src.evaluation.modell.Ebenenauswertung`.
    """
    return Ebenenauswertung(
        ebene=ebene,
        kennzahlen=kennzahlen_der_ebene,
        nicht_auswertbar_grund=None,
        recall_je_klasse=teile.recall_je_klasse,
        recall_je_variante=teile.recall_je_variante,
        recall_variantengewichtet_je_klasse=teile.variantengewichtet,
        macro_recall_klassen=macro_recall(teile.recall_je_klasse),
        macro_recall_varianten=macro_recall(teile.recall_je_variante),
    )


def _auswerte_schalterstellung(
    sicht: _Meldungssicht,
    wahrheit: GroundTruth,
    klasse_je_variante: Mapping[str, str],
    scores: pd.DataFrame | None,
    *,
    mitgezogen_als_fehler: bool,
) -> Auswertung:
    """Wertet ein Verfahren fuer **eine** Stellung des Schalters aus.

    Args:
        sicht: Aufbereitete Meldungen des Verfahrens.
        wahrheit: Ground Truth des Laufs.
        klasse_je_variante: Zuordnung Variante auf Klasse.
        scores: Zellscores des Verfahrens, oder ``None``.
        mitgezogen_als_fehler: Ob mitgezogene Zellen zum Ground Truth zaehlen.

    Returns:
        Die :class:`~src.evaluation.modell.Auswertung` aller drei Ebenen samt
        Regeldiagnose und Kreuztabelle.
    """
    zellwahrheit = wahrheit.zellmenge(mitgezogen_als_fehler=mitgezogen_als_fehler)
    satzwahrheit = wahrheit.satzmenge(mitgezogen_als_fehler=mitgezogen_als_fehler)
    zellmenge = frozenset(zellwahrheit)
    satzmenge = frozenset(satzwahrheit)

    zellteile = _ebenenteile(
        _je_gruppe((eintrag.fehlerklasse, zelle) for zelle, eintrag in zellwahrheit.items()),
        _je_gruppe(
            (eintrag.injektor_variante_id, zelle) for zelle, eintrag in zellwahrheit.items()
        ),
        sicht.markierte_zellen,
        wahrheit,
        klasse_je_variante,
    )
    satzteile = _ebenenteile(
        _je_gruppe(
            (eintrag.fehlerklasse, zeile)
            for zeile, eintraege in satzwahrheit.items()
            for eintrag in eintraege
        ),
        _je_gruppe(
            (eintrag.injektor_variante_id, zeile)
            for zeile, eintraege in satzwahrheit.items()
            for eintrag in eintraege
        ),
        sicht.markierte_saetze,
        wahrheit,
        klasse_je_variante,
    )

    paare = _scorepaare(scores, zellmenge)
    flaeche = None if paare is None else pr_auc(paare[0], paare[1])

    ebenen = {
        Ebene.ZELLE: _als_ebenenauswertung(
            Ebene.ZELLE,
            kennzahlen(
                konfusion_mengen(sicht.markierte_zellen, zellmenge, wahrheit.universum_zellen),
                pr_auc=flaeche,
            ),
            zellteile,
        ),
        Ebene.CONSTRAINT: _als_ebenenauswertung(
            Ebene.CONSTRAINT,
            kennzahlen(
                konfusion_constraints(sicht.zellen_je_verstoss, zellmenge, sicht.markierte_zellen)
            ),
            # Der Recall bleibt zellbasiert; die Gruppenteile sind deshalb
            # dieselben wie auf der Zellebene (siehe Modul-Docstring).
            zellteile,
        ),
        Ebene.SATZ: _als_ebenenauswertung(
            Ebene.SATZ,
            kennzahlen(
                konfusion_mengen(sicht.markierte_saetze, satzmenge, wahrheit.universum_saetze)
            ),
            satzteile,
        ),
    }

    return Auswertung(
        mitgezogen_als_fehler=mitgezogen_als_fehler,
        ebenen=MappingProxyType(ebenen),
        regeldiagnose=regeldiagnose(sicht.zellen_je_regel, zellmenge),
        kreuztabelle=kreuztabelle(
            sicht.zellen_je_regel,
            {zelle: eintrag.fehlerklasse for zelle, eintrag in zellwahrheit.items()},
        ),
    )


def _leere_auswertung(*, mitgezogen_als_fehler: bool) -> Auswertung:
    """Baut die Auswertung eines Verfahrens ohne Zeilenbezug.

    Args:
        mitgezogen_als_fehler: Die Schalterstellung.

    Returns:
        Eine Auswertung, deren drei Ebenen den
        :data:`NICHT_LOKALISIERT_GRUND` tragen. Regeldiagnose und Kreuztabelle
        bleiben leer: Beide ordnen Regeln zu Zellen zu, und genau diese Zuordnung
        fehlt.
    """
    return Auswertung(
        mitgezogen_als_fehler=mitgezogen_als_fehler,
        ebenen=MappingProxyType({ebene: _nicht_auswertbar(ebene) for ebene in Ebene}),
        regeldiagnose=(),
        kreuztabelle=(),
    )


def bewerte(
    verfahren: Sequence[Verfahren],
    kontext: Kontext,
    wahrheit: GroundTruth,
    *,
    messe_speicher: bool = True,
) -> tuple[Verfahrensergebnis, ...]:
    """Fuehrt alle Verfahren aus und wertet sie gegen den Ground Truth aus.

    Je Verfahren entstehen **zwei** Auswertungen — ``mitgezogen_als_fehler``
    ``False`` und ``True``, in dieser Reihenfolge. Die erste ist die
    Hauptauswertung der Arbeit, die zweite die Sensitivitaetsrechnung im Anhang.

    Args:
        verfahren: Die zu vergleichenden Verfahren, in Berichtsreihenfolge.
        kontext: Pruefkontext ueber beide Datenschichten des **verfaelschten**
            Datensatzes.
        wahrheit: Ground Truth desselben Laufs.
        messe_speicher: Reicht die ``tracemalloc``-Messung an
            :func:`fuehre_aus` durch.

    Returns:
        Je Verfahren ein :class:`~src.evaluation.modell.Verfahrensergebnis`, in
        der Reihenfolge der Eingabe.

    Raises:
        AuswertungsFehler: Wenn zwei Verfahren denselben Namen tragen — die
            Ergebnisse werden im Langformat und in ``metrics.json`` ueber ihren
            Namen adressiert, und zwei gleichnamige Verfahren wuerden einander
            still ueberschreiben.
    """
    namen = [eintrag.name for eintrag in verfahren]
    doppelt = sorted({name for name in namen if namen.count(name) > 1})
    if doppelt:
        raise AuswertungsFehler(
            f"Die Verfahrensnamen {doppelt} kommen mehrfach vor. Jedes Verfahren wird ueber "
            "seinen Namen adressiert und braucht deshalb einen eindeutigen."
        )

    klasse_je_variante = _klasse_je_variante(wahrheit)
    ergebnisse: list[Verfahrensergebnis] = []
    for eintrag in verfahren:
        meldungen, saetze, scores, messung = fuehre_aus(
            eintrag, kontext, messe_speicher=messe_speicher
        )
        sicht = _baue_sicht(meldungen, saetze)
        if eintrag.lokalisiert_zellen:
            auswertungen = tuple(
                _auswerte_schalterstellung(
                    sicht,
                    wahrheit,
                    klasse_je_variante,
                    scores,
                    mitgezogen_als_fehler=schalter,
                )
                for schalter in (False, True)
            )
        else:
            auswertungen = tuple(
                _leere_auswertung(mitgezogen_als_fehler=schalter) for schalter in (False, True)
            )

        ergebnisse.append(
            Verfahrensergebnis(
                verfahren=eintrag.name,
                beschreibung=eintrag.beschreibung,
                lokalisiert_zellen=eintrag.lokalisiert_zellen,
                in_inferenzstatistik=eintrag.in_inferenzstatistik,
                messung=messung,
                meldungen_gesamt=sicht.meldungen_gesamt,
                markierte_zellen=len(sicht.markierte_zellen),
                meldungen_ohne_zeilenbezug=sicht.ohne_zeilenbezug,
                markierte_zellen_row_id=sum(
                    1 for zelle in sicht.markierte_zellen if zelle[2] == _ROW_ID
                ),
                auswertungen=(auswertungen[0], auswertungen[1]),
            )
        )
    return tuple(ergebnisse)
