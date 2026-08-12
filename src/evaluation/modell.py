"""Datenmodell der Auswertung: Verfahrensprotokoll, Ergebnistypen, Konstanten.

Dieses Modul definiert, **was** ein zu vergleichendes Verfahren ist und in welcher
Form seine Messung abgelegt wird. Die Kennzahlen selbst entstehen in
``metriken.py``, der Ground Truth in ``ground_truth.py``, die Orchestrierung in
``pipeline.py``.

Vier Entwurfsentscheidungen tragen dieses Modul.

Ein Verfahren ist ein Protokoll, keine Basisklasse
--------------------------------------------------

Der Prototyp, ``pydantic`` (B0), ``IsolationForest`` (B2) und ``cuallee`` (B3)
haben nichts gemeinsam ausser der Frage, die an sie gestellt wird: *Welche Zellen
haeltst du fuer fehlerhaft?* Eine gemeinsame Basisklasse wuerde drei fremden
Bibliotheken eine Vererbungshierarchie aufzwingen, die sie nicht brauchen, und die
Adapter zu Unterklassen machen statt zu dem, was sie sind — duenne Uebersetzer.
:class:`Verfahren` ist deshalb ein :class:`typing.Protocol`: strukturelle
Typisierung, kein Import in die Gegenrichtung, und jeder Adapter bleibt eine
gewoehnliche Klasse.

Die beiden Zusatzprotokolle :class:`MitSatzmeldungen` und :class:`MitZellscore`
sind bewusst **getrennt** und ``runtime_checkable``. Nicht jedes Verfahren liefert
satzbezogene Befunde (nur der Prototyp tut es), und nur B2 liefert einen
kontinuierlichen Score. Waeren beide Methoden Teil von :class:`Verfahren`, muessten
drei von vier Adaptern leere Implementierungen tragen — und ein leerer Rueckgabewert
sieht in der Auswertung genauso aus wie "nichts gefunden", was er nicht ist.

``Kontext``, ``VERSTOSS_SPALTEN`` und ``SATZ_SPALTEN`` werden re-exportiert
--------------------------------------------------------------------------

Sie stammen aus :mod:`src.rules.modell` und werden hier **nicht** nachgebaut. Der
:class:`~src.rules.modell.Kontext` ist ein reiner Datenbehaelter ueber beide
Datenschichten und ueber die Referenztabellen; er enthaelt keine einzige Regel und
keine Pruefbedingung. Ein zweiter, gleich aussehender Behaelter in
``src/evaluation`` haette deshalb keinen inhaltlichen Vorteil, aber einen
handfesten Nachteil: Zwei Definitionen derselben Sache geraten frueher oder
spaeter aus dem Tritt, und der Fehler faellt erst auf, wenn eine Baseline eine
Spalte nicht mehr sieht, die der Prototyp sieht. Dasselbe gilt fuer die beiden
Spaltentupel — sie sind das Berichtsformat, gegen das alle vier Verfahren
schreiben, und ein Format hat genau eine Quelle.

``src/evaluation`` importiert im Gegenzug **nichts** aus ``src.injector`` und
nichts aus ``src.generator``. Alles, was die Auswertung ueber Fehlerklassen und
Varianten wissen muss, steht in den beiden Ground-Truth-Logs und im
``manifest.json`` des Laufs. Die Zuordnung Variante auf Regel entsteht laut
``spec/03_fehlerklassen.md``, Abschnitt 6 erst hier; sie darf nicht aus dem
Quelltext des Injektors stammen, sonst misst das Experiment nur noch, ob dieselbe
Bedingung zweimal geschrieben wurde.

Die Ergebnistypen tragen die Rohwerte, nicht nur die Kennzahlen
---------------------------------------------------------------

:class:`Konfusion` haelt ``tp``, ``fp``, ``fn``, ``tn`` und die Grundgesamtheit.
Erst daraus entstehen Precision, Recall, F1 und MCC. Der Grund ist praktisch: Bei
mehreren tausend Laeufen in Phase 6 ist das Nachrechnen einer weiteren Kennzahl
aus abgelegten Rohwerten eine Sekunde Arbeit, das Wiederholen der Laeufe dagegen
Stunden. Deshalb werden ``TP``, ``FP``, ``FN`` und ``TN`` in ``metrics.json`` und
im Langformat **immer** mitgeschrieben.

``tn`` und ``grundgesamtheit`` sind ``int | None``. ``None`` heisst nicht "null",
sondern "die negative Klasse ist auf dieser Ebene nicht abzaehlbar" — so auf der
Constraint-Ebene, wo die Einheit ein erkannter Verstoss ist und es keine
abzaehlbare Menge nicht erkannter Verstoesse gibt. Eine Null an dieser Stelle
waere eine Behauptung, die niemand belegen kann; ``None`` ist der ehrliche Wert
und faellt in jeder Tabelle auf.

Zwei Auswertungen je Verfahren, nicht eine
------------------------------------------

:class:`Verfahrensergebnis` traegt ein Paar :class:`Auswertung` — eine mit
``mitgezogen_als_fehler=False``, eine mit ``True``. Mitgezogene Zellen sind
gegenueber den verfaelschten Daten *korrekt* (``spec/03``, Abschnitt 2:
nachgefuehrte ``angebot.rang``); ein Verfahren, das sie nicht meldet, macht keinen
Fehler. Genau deshalb darf ihre Behandlung nicht unsichtbar im Quelltext
verschwinden: Sie hebt den Recall von F8 und HO2 spuerbar. Zwei Zahlen
nebeneinander beenden die Diskussion, eine Zahl allein eroeffnet sie. Die
Reihenfolge im Tupel ist fest — ``False`` zuerst, dann ``True`` —, damit die
Hauptauswertung immer an Position 0 steht.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

from src.rules.modell import SATZ_SPALTEN, VERSTOSS_SPALTEN, Kontext

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping

    import pandas as pd

__all__ = [
    "KEINE_FEHLERKLASSE",
    "ROW_ID_OHNE_BEZUG",
    "SATZ_SPALTEN",
    "SCORE_SPALTEN",
    "VERSTOSS_SPALTEN",
    "Auswertung",
    "AuswertungsFehler",
    "Ebene",
    "Ebenenauswertung",
    "Gruppenrecall",
    "Kennzahlen",
    "Konfusion",
    "Kontext",
    "Kreuzeintrag",
    "Laufmessung",
    "MitSatzmeldungen",
    "MitZellscore",
    "Regeldiagnose",
    "Verfahren",
    "Verfahrensergebnis",
]

#: Zeilenkennung einer Meldung **ohne** Zeilenbezug.
#:
#: B3 (``cuallee``) nennt in seinem Report die Spalte, die Regel und die Zahl der
#: Verstoesse — aber keine Zeile. Solche Meldungen tragen hier ``-1`` und werden
#: aus der Zell- und der Satzebene herausgehalten, statt sie einer beliebigen
#: Zeile zuzuschlagen. Das ist der gemessene Befund zur Diagnoseguete, kein
#: fehlender Wert.
#:
#: Der Befund ist eine Eigenschaft **dieses Werkzeugs**, nicht der Gattung: Great
#: Expectations liefert mit ``unexpected_index_list`` Zeilenkennung und
#: Ausgangswert. Der Gegenschnitt dazu steht in
#: :mod:`src.baselines.b3b_great_expectations`. Das Feld bleibt deshalb allgemein
#: gehalten — es kennzeichnet eine Meldung ohne Zeilenbezug, nicht "ein Framework".
ROW_ID_OHNE_BEZUG: Final[int] = -1

#: Spalten der Zellscore-Tabelle (nur B2 fuellt sie).
#:
#: ``score`` ist der Anomaliescore der Zeile, in dem hoehere Werte "anomaler"
#: bedeuten. Nur mit dieser Orientierung ist die PR-AUC richtig herum.
SCORE_SPALTEN: Final[tuple[str, ...]] = ("entitaet", "row_id", "spalte", "score")

#: Platzhalter fuer die Fehlerklasse einer Zelle, die gar keinen Fehler traegt.
#:
#: Ein False Positive hat keine Fehlerklasse — dort ist kein Fehler. In der
#: Kreuztabelle Regel gegen Fehlerklasse steht dafuer dieses Zeichen und **nicht**
#: eine erfundene Klasse "sonstige"; siehe :mod:`src.evaluation.metriken`.
KEINE_FEHLERKLASSE: Final[str] = "-"


class AuswertungsFehler(RuntimeError):
    """Die Auswertung ist nicht durchfuehrbar oder ihre Eingaben widersprechen sich.

    Bewusst eine Ausnahme und kein stiller Ersatzwert: Ein doppelt protokollierter
    Ground Truth oder eine Konfusionsmatrix, die ueber ihre Grundgesamtheit
    hinauswaechst, ist ein Programmier- oder Datenfehler. Ein stillschweigend
    gesetzter Defaultwert wuerde ihn in eine Kennzahl verwandeln, die niemand mehr
    als falsch erkennt.
    """


class Ebene(StrEnum):
    """Die drei Auswertungsebenen.

    Die Werte sind die Bezeichner, unter denen die Ebene in ``metrics.json`` und
    im Langformat erscheint. Sie sind Teil des Ausgabeformats und werden
    nachtraeglich nicht mehr geaendert.
    """

    ZELLE = "zellebene"
    """Einheit ``(entitaet, row_id, spalte)``. Primaermetrik der Arbeit."""

    CONSTRAINT = "constraintebene"
    """Einheit ``verstoss_id``. Repariert die strukturelle Deckelung der Precision."""

    SATZ = "satzebene"
    """Einheit ``(entitaet, row_id)``. Einzige Ebene, auf der F6 und HO1 messbar sind."""


# ---------------------------------------------------------------------------
# Das Verfahrensprotokoll
# ---------------------------------------------------------------------------


class Verfahren(Protocol):
    """Ein Erkennungsverfahren im Vergleich.

    Attributes:
        name: Kurzname im Bericht, zum Beispiel ``"prototyp"``, ``"B0"``,
            ``"B2"``, ``"B3"``.
        beschreibung: Ein Satz, der im Anhang neben dem Namen steht.
        lokalisiert_zellen: ``False``, wenn das Verfahren keine Zeile benennt.
            Dann ist auf **keiner** Ebene eine Konfusionsmatrix bildbar; die
            Auswertung traegt statt Nullen einen ``nicht_auswertbar_grund``. Das
            betrifft B3 und ist dort das Messergebnis, nicht ein Defekt.
        in_inferenzstatistik: ``False``, wenn das Verfahren nicht in die
            Wilcoxon-Vergleiche eingeht. Bei B3 waere ein Test gegen ein
            Verfahren, das inhaltlich dieselben Regeln ausfuehrt, ein Test einer
            Nullhypothese, von der man weiss, dass sie gilt.
    """

    name: str
    beschreibung: str
    lokalisiert_zellen: bool
    in_inferenzstatistik: bool

    def erkenne(self, kontext: Kontext) -> pd.DataFrame:
        """Meldet die fuer fehlerhaft gehaltenen Zellen.

        Args:
            kontext: Pruefkontext ueber beide Datenschichten des **verfaelschten**
                Datensatzes.

        Returns:
            Einen Datenrahmen mit den Spalten :data:`VERSTOSS_SPALTEN`. Meldungen
            ohne Zeilenbezug tragen ``row_id`` gleich :data:`ROW_ID_OHNE_BEZUG`.
        """
        ...


@runtime_checkable
class MitSatzmeldungen(Protocol):
    """Zusatzprotokoll fuer Verfahren mit satzbezogenen Befunden.

    Nur der Prototyp erfuellt es. Duplikate (F6, HO1) sind eine Eigenschaft eines
    **Zeilenpaares**; eine verursachende Zelle gibt es dort nicht (``spec/03``,
    Abschnitt 4.2). Wer solche Befunde melden kann, meldet sie hier.
    """

    def satzmeldungen(self, kontext: Kontext) -> pd.DataFrame:
        """Meldet die satzbezogenen Befunde.

        Args:
            kontext: Pruefkontext ueber beide Datenschichten.

        Returns:
            Einen Datenrahmen mit den Spalten :data:`SATZ_SPALTEN`.
        """
        ...


@runtime_checkable
class MitZellscore(Protocol):
    """Zusatzprotokoll fuer Verfahren mit kontinuierlichem Anomaliescore.

    Nur B2 erfuellt es. Eine Precision-Recall-Kurve braucht einen Score; der
    Prototyp, B0 und B3 liefern binaere Entscheidungen und damit genau einen
    Betriebspunkt. Fuer sie wird **kein** Pseudo-Score erfunden, und ihre PR-AUC
    bleibt ``None``.
    """

    def zellscores(self, kontext: Kontext) -> pd.DataFrame:
        """Gibt den Anomaliescore je bewerteter Zelle zurueck.

        Args:
            kontext: Pruefkontext ueber beide Datenschichten.

        Returns:
            Einen Datenrahmen mit den Spalten :data:`SCORE_SPALTEN`; hoehere Werte
            bedeuten "anomaler".
        """
        ...


# ---------------------------------------------------------------------------
# Ergebnistypen
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Konfusion:
    """Die vier Rohwerte einer Konfusionsmatrix.

    Auf der Zell- und der Satzebene zaehlen alle vier Werte **dieselbe** Einheit,
    und alle Kennzahlen folgen aus ihnen. Auf der Constraint-Ebene ist das nicht
    so: Dort zaehlen ``tp`` und ``fp`` gemeldete Verstoesse, ``fn`` dagegen
    uebersehene Wahrheitszellen — es gibt keine abzaehlbare Menge "nicht
    gemeldeter Verstoesse", gegen die man zaehlen koennte. ``tp / (tp + fn)``
    waere dort ein Bruch aus zwei Einheiten und **kein Recall**. Deshalb gibt es
    ``tp_recall``.

    Attributes:
        tp: Richtig markierte Einheiten.
        fp: Faelschlich markierte Einheiten.
        fn: Uebersehene Einheiten des Ground Truth.
        tn: Richtig nicht markierte Einheiten; ``None``, wo die negative Klasse
            nicht abzaehlbar ist (Constraint-Ebene).
        grundgesamtheit: Zahl aller Einheiten der Ebene; ``None`` mit derselben
            Begruendung wie bei ``tn``.
        tp_recall: Zaehler des Recalls, wenn er in einer **anderen** Einheit
            gezaehlt wird als ``tp`` — also die Zahl der gefundenen
            Wahrheitseinheiten. ``None`` heisst "dieselbe Einheit wie ``tp``" und
            ist der Normalfall; nur die Constraint-Ebene setzt den Wert.
            :func:`~src.evaluation.metriken.recall` liest ihn und bildet den
            Recall damit aus ``tp_recall / (tp_recall + fn)``, also durchgehend
            zellbasiert.
    """

    tp: int
    fp: int
    fn: int
    tn: int | None
    grundgesamtheit: int | None
    tp_recall: int | None = None


@dataclass(frozen=True, slots=True)
class Kennzahlen:
    """Die aus einer :class:`Konfusion` abgeleiteten Kennzahlen.

    Attributes:
        konfusion: Die zugrunde liegenden Rohwerte.
        precision: ``tp / (tp + fp)``; ``0.0`` bei leerer Meldungsmenge.
        recall: ``tp / (tp + fn)``, mit ``tp_recall`` an der Stelle von ``tp``,
            sobald dieses gesetzt ist; ``0.0`` bei leerem Ground Truth.
        f1: Harmonisches Mittel; ``0.0``, wenn beide Faktoren null sind.
        mcc: Matthews-Korrelationskoeffizient; ``None`` ohne ``tn``.
        fpr_clean: Fehlalarmrate auf den **nicht** verfaelschten Einheiten;
            ``None`` ohne ``tn``.
        pr_auc: Flaeche unter der Precision-Recall-Kurve; ``None`` fuer jedes
            Verfahren mit binaerer Entscheidung.
    """

    konfusion: Konfusion
    precision: float
    recall: float
    f1: float
    mcc: float | None
    fpr_clean: float | None
    pr_auc: float | None


@dataclass(frozen=True, slots=True)
class Gruppenrecall:
    """Recall einer Gruppe von Wahrheitseinheiten samt Konfidenzintervall.

    Gruppe ist entweder eine Fehlerklasse (``"F3"``) oder eine
    ``injektor_variante_id`` (``"F4-g"``).

    Attributes:
        gruppe: Kennung der Gruppe.
        n: Zahl der Wahrheitseinheiten dieser Gruppe auf der jeweiligen Ebene.
            Wird **immer** mitgefuehrt — ein Recall ohne sein ``n`` ist in einer
            Tabelle mit sechzig Varianten nicht interpretierbar.
        tp: Davon gefundene Einheiten.
        recall: ``tp / n``; ``0.0`` bei ``n = 0``.
        ci_unten: Untere Clopper-Pearson-Grenze zum Niveau ``1 - alpha``.
        ci_oben: Obere Clopper-Pearson-Grenze.
    """

    gruppe: str
    n: int
    tp: int
    recall: float
    ci_unten: float
    ci_oben: float


@dataclass(frozen=True, slots=True)
class Regeldiagnose:
    """Diagnostische Kennzahlen einer einzelnen Regel.

    Keine Konfusionsmatrix: Ein Recall je Regel waere nicht definiert, weil der
    Ground Truth Fehlerklassen kennt, aber keine Regel-IDs.

    Attributes:
        regel_id: Kennung der Regel, zum Beispiel ``"R-031"``.
        meldungen: Zahl der von dieser Regel gemeldeten **verschiedenen** Zellen.
        tp: Davon Zellen, die im Ground Truth liegen.
        precision: ``tp / meldungen``; ``0.0`` ohne Meldung.
        anteil_einzige_regel: Anteil der Treffer, bei denen **keine andere** Regel
            dieselbe Zelle gemeldet hat. Die Kennzahl beantwortet, wie viel eine
            Regel zur Erkennungsleistung des Katalogs beitraegt, das ohne sie
            verloren ginge.
    """

    regel_id: str
    meldungen: int
    tp: int
    precision: float
    anteil_einzige_regel: float


@dataclass(frozen=True, slots=True)
class Kreuzeintrag:
    """Eine Zelle der Kreuztabelle Regel gegen Fehlerklasse.

    Attributes:
        regel_id: Meldende Regel.
        fehlerklasse: Fehlerklasse der getroffenen Zellen;
            :data:`KEINE_FEHLERKLASSE` fuer False Positives, weil dort gar kein
            Fehler liegt und damit auch keine Klasse.
        treffer: Zahl der Zellen in dieser Kombination.
    """

    regel_id: str
    fehlerklasse: str
    treffer: int


@dataclass(frozen=True, slots=True)
class Ebenenauswertung:
    """Vollstaendige Auswertung einer der drei Ebenen.

    Attributes:
        ebene: Die ausgewertete Ebene.
        kennzahlen: Die Kennzahlen; ``None``, wenn das Verfahren keine Zeile
            benennt und damit keine Konfusionsmatrix bildbar ist.
        nicht_auswertbar_grund: Klartextbegruendung, wenn ``kennzahlen`` ``None``
            ist; sonst ``None``. Bewusst ein Text und keine Null: Eine Null in der
            Ergebnistabelle liest sich wie "hat nichts gefunden", der Text sagt
            "kann nicht gemessen werden, und das ist der Befund".
        recall_je_klasse: Recall je Fehlerklasse, in Klassenreihenfolge.
        recall_je_variante: Recall je ``injektor_variante_id``.
        recall_variantengewichtet_je_klasse: Ungewichtetes Mittel der
            Variantenrecalls einer Klasse. Gegenzahl zum zellgewichteten
            Klassenrecall.
        macro_recall_klassen: Ungewichtetes Mittel ueber alle Klassen mit ``n > 0``.
        macro_recall_varianten: Dasselbe ueber alle Varianten mit ``n > 0``.
    """

    ebene: Ebene
    kennzahlen: Kennzahlen | None
    nicht_auswertbar_grund: str | None
    recall_je_klasse: tuple[Gruppenrecall, ...]
    recall_je_variante: tuple[Gruppenrecall, ...]
    recall_variantengewichtet_je_klasse: Mapping[str, float]
    macro_recall_klassen: float | None
    macro_recall_varianten: float | None


@dataclass(frozen=True, slots=True)
class Auswertung:
    """Alle drei Ebenen fuer **einen** Wert von ``mitgezogen_als_fehler``.

    Attributes:
        mitgezogen_als_fehler: Ob mitgezogene Zellen zum Ground Truth zaehlen.
            ``False`` ist die Hauptauswertung der Arbeit, ``True`` die
            Sensitivitaetsrechnung im Anhang.
        ebenen: Auswertung je :class:`Ebene`.
        regeldiagnose: Diagnose je Regel; nur auf der Zellebene definiert und
            deshalb nur einmal je Auswertung gefuehrt.
        kreuztabelle: Kreuztabelle Regel gegen Fehlerklasse; ebenfalls nur
            zellbasiert.
    """

    mitgezogen_als_fehler: bool
    ebenen: Mapping[Ebene, Ebenenauswertung]
    regeldiagnose: tuple[Regeldiagnose, ...]
    kreuztabelle: tuple[Kreuzeintrag, ...]


@dataclass(frozen=True, slots=True)
class Laufmessung:
    """Laufzeit und Speicherbedarf eines Verfahrens auf einem Lauf.

    Die normierten Werte machen Laeufe verschiedener Groesse vergleichbar; die
    Rohwerte bleiben daneben stehen, damit die Normierung nachvollziehbar ist.

    Attributes:
        laufzeit_s: Wanduhrzeit des Durchlaufs in Sekunden.
        laufzeit_s_je_1000_zeilen: Auf tausend Zeilen normierte Laufzeit.
        speicher_mb: Spitzenwert der Speicherbelegung in Mebibyte; ``None``, wenn
            die Messung abgeschaltet war.
        speicher_mb_je_1000_zeilen: Entsprechend normiert; ``None`` ebenso.
        zeilen_gesamt: Zeilen aller Entitaeten des verfaelschten Datensatzes.
    """

    laufzeit_s: float
    laufzeit_s_je_1000_zeilen: float
    speicher_mb: float | None
    speicher_mb_je_1000_zeilen: float | None
    zeilen_gesamt: int


@dataclass(frozen=True, slots=True)
class Verfahrensergebnis:
    """Das vollstaendige Ergebnis eines Verfahrens auf einem Lauf.

    Attributes:
        verfahren: Kurzname des Verfahrens.
        beschreibung: Beschreibung aus dem Adapter.
        lokalisiert_zellen: Uebernommen aus dem Verfahren.
        in_inferenzstatistik: Uebernommen aus dem Verfahren.
        messung: Laufzeit und Speicher.
        meldungen_gesamt: Zeilen des Meldungsrahmens, also Rohtreffer **vor** der
            Vereinigung.
        markierte_zellen: Maechtigkeit der Vereinigungsmenge der markierten Zellen.
            Die Differenz zu ``meldungen_gesamt`` ist die Mehrfachmeldung
            derselben Zelle und selbst ein Befund.
        meldungen_ohne_zeilenbezug: Meldungen mit ``row_id``
            gleich :data:`ROW_ID_OHNE_BEZUG`.
        markierte_zellen_row_id: Markierungen auf der Spalte ``row_id``. Sie sind
            **garantierte** Fehlalarme: ``row_id`` ist nach Architekturregel A3
            niemals Ziel einer Injektion und kann deshalb in keinem Ground Truth
            stehen. Die Zahl wird ausgewiesen, weil sie ein Verfahren trifft, das
            zeilenweise arbeitet und seine Entscheidung auf alle befuellten Zellen
            der Zeile umlegt — B2 markiert damit je anomaler Zeile eine Zelle, die
            per Konstruktion nicht richtig sein kann. Der Anteil gehoert in die
            Arbeit, damit die Zell-Precision von B2 einordbar bleibt.
        auswertungen: Zwei Auswertungen, ``mitgezogen_als_fehler=False`` zuerst.
    """

    verfahren: str
    beschreibung: str
    lokalisiert_zellen: bool
    in_inferenzstatistik: bool
    messung: Laufmessung
    meldungen_gesamt: int
    markierte_zellen: int
    meldungen_ohne_zeilenbezug: int
    markierte_zellen_row_id: int
    auswertungen: tuple[Auswertung, Auswertung]
