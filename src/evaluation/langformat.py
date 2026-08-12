"""Die beiden Ausgabeformate der Auswertung: ``metrics.json`` und das Langformat.

Dieses Modul enthaelt keine einzige Kennzahl. Es uebersetzt die Ergebnistypen aus
:mod:`src.evaluation.modell` in die zwei Formen, in denen sie den Prozess
verlassen — und diese Uebersetzung ist eine Entwurfsentscheidung, keine
Formalitaet.

Zwei Formate, weil zwei Leser
-----------------------------

``metrics.json`` ist die **vollstaendige, verschachtelte** Fassung eines einzelnen
Laufs. Sie steht neben den Ground-Truth-Logs im Laufverzeichnis, ist von Hand
lesbar und beantwortet die Frage "was ist in diesem Lauf passiert?". Dort stehen
auch die Angaben, die sich nicht in eine Tabellenzeile pressen lassen: der Grund,
warum eine Ebene nicht auswertbar war, der Schwellen-Sweep von B2, der
Ausdrueckbarkeitsbericht von B3.

``results/metrics_long.parquet`` ist die **flache, laufuebergreifende** Fassung.
Eine Zeile ist genau ein gemessener Wert, und die Faktorstufen stehen als Spalten
daneben. Genau diese Form braucht Phase 6: Ein Wilcoxon-Test ueber tausend Laeufe
ist darauf eine Gruppierung, waehrend er auf tausend verschachtelten JSON-Dateien
ein Parserproblem waere. Das Langformat ist bewusst redundant zu ``metrics.json``
— es ist eine Projektion, keine zweite Quelle.

Warum das Langformat und nicht eine breite Tabelle
--------------------------------------------------

Eine Spalte je Kennzahl waere kompakter zu lesen, aber sie muesste bei jeder neuen
Kennzahl geaendert werden, und sie kann Kennzahlen mit unterschiedlichem
Bezugsobjekt nicht nebeneinander tragen: Precision bezieht sich auf einen Lauf,
Recall zusaetzlich auf eine Fehlerklasse, ``anteil_einzige_regel`` auf eine Regel.
Im Langformat tragen ``gruppe_art`` und ``gruppe`` diesen Bezug, und eine neue
Kennzahl ist eine neue Auspraegung von ``metrik`` statt einer Schemaaenderung.

Der Preis ist eine Konvention fuer Zeilen ohne Bezug: ``gruppe`` ist dort der
**leere String**, nicht ``NA``. Dasselbe gilt fuer ``ebene`` bei Kennzahlen, die
gar keine Ebene haben — Laufzeit und Speicherbedarf messen das Verfahren, nicht
eine Auswertungsebene. ``mitgezogen_als_fehler`` ist bei ihnen dagegen ``NA``:
Der Schalter ist dort nicht "aus", sondern **nicht anwendbar**, und diese beiden
Zustaende duerfen nicht dasselbe Zeichen tragen.

Die Kreuztabelle traegt einen zusammengesetzten Gruppenschluessel
------------------------------------------------------------------

Die Kreuztabelle Regel gegen Fehlerklasse braucht zwei Kennungen, das Langformat
hat aber genau eine Spalte ``gruppe``. Ihre Eintraege stehen deshalb unter
``gruppe_art = "regel"`` mit dem zusammengesetzten Schluessel
``<regel_id>|<fehlerklasse>`` (:data:`KREUZ_TRENNER`). Verwechslungsgefahr besteht
nicht: Die Kreuzeintraege sind die einzigen Zeilen mit ``metrik = "treffer"``, und
weder eine ``regel_id`` noch eine Fehlerklasse enthaelt einen senkrechten Strich.
Eine fuenfte Auspraegung von ``gruppe_art`` waere die sauberere Modellierung
gewesen, haette aber das vereinbarte Vokabular der Spalte aufgeweicht — und ein
Vokabular, das mit jeder Tabelle waechst, ist keins.

Nicht bildbare Kennzahlen bekommen eine Zeile mit fehlendem Wert
-----------------------------------------------------------------

B3 (``cuallee``) nennt keine Zeile; auf keiner Ebene ist eine Konfusionsmatrix
bildbar. Das gilt fuer dieses Werkzeug und nicht fuer die Gattung — Great
Expectations liefert den Zeilenbezug (siehe
:mod:`src.baselines.b3b_great_expectations`). Es waere
naheliegend, fuer B3 einfach keine Zeilen zu schreiben. Das Langformat tut das
Gegenteil: Es schreibt die vollstaendige Zeilenmenge mit ``wert = NA``. Eine
fehlende Zeile waere in der Auswertung von "das Verfahren lief nicht" nicht zu
unterscheiden, ein fehlender Wert ist genau die Aussage, die gemeint ist — und
die Begruendung dazu steht als ``nicht_auswertbar_grund`` in ``metrics.json``.
Aus demselben Grund sind ``wert`` und ``n`` nullable Typen (``Float64``,
``Int64``) und keine ``float``- beziehungsweise ``int``-Spalten.

Das Langformat sammelt ueber Laeufe hinweg
-------------------------------------------

:func:`schreibe_langformat` ueberschreibt die Zieldatei nicht, sondern liest sie
ein, entfernt alle Zeilen der neu geschriebenen ``run_id`` und haengt die neuen
an. Dieselbe Begruendung wie bei
:func:`src.verify.diff_check.schreibe_bericht`: Die Datei gehoert in den Anhang
der Arbeit, und dort ist der Nachweis ueber alle Laeufe mehr wert als der ueber
den zuletzt gelaufenen. Das Entfernen der gleichnamigen ``run_id`` macht eine
Wiederholung idempotent — ein zweiter Aufruf desselben Laufs veraendert die Datei
nicht, statt sie zu verdoppeln.

Sortiert wird anschliessend ueber **alle** Schluesselspalten. Ohne diese Sortierung
haenge der Dateiinhalt an der Reihenfolge, in der die Laeufe abgearbeitet wurden;
bei parallelen Laeufen in Phase 6 waere das ein Verstoss gegen Architekturregel
A2. Einen Zeitstempel traegt weder die JSON- noch die Parquet-Datei.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final

import pandas as pd

from src.evaluation.modell import AuswertungsFehler, Ebene

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from src.evaluation.ground_truth import GroundTruth
    from src.evaluation.modell import (
        Auswertung,
        Ebenenauswertung,
        Gruppenrecall,
        Kennzahlen,
        Konfusion,
        Laufmessung,
        Verfahrensergebnis,
    )

__all__ = [
    "FAKTORSPALTEN",
    "GRUPPE_FEHLERKLASSE",
    "GRUPPE_GESAMT",
    "GRUPPE_REGEL",
    "GRUPPE_VARIANTE",
    "KREUZ_TRENNER",
    "METRICS_LONG_SPALTEN",
    "OHNE_BEZUG",
    "SPALTENTYPEN",
    "baue_langformat",
    "baue_metrics",
    "schreibe_langformat",
    "schreibe_metrics",
]

#: Spalten des Langformats, in dieser Reihenfolge.
METRICS_LONG_SPALTEN: Final[tuple[str, ...]] = (
    "run_id",
    "serie",
    "design",
    "modus",
    "klasse",
    "variante",
    "fehlerrate",
    "wiederholung",
    "verfahren",
    "ebene",
    "mitgezogen_als_fehler",
    "gruppe_art",
    "gruppe",
    "metrik",
    "wert",
    "n",
)

#: Datentyp je Spalte des Langformats.
#:
#: ``wert`` und ``n`` sind bewusst nullable: Eine nicht bildbare Kennzahl bekommt
#: eine Zeile mit fehlendem Wert und nicht gar keine Zeile (siehe Modul-Docstring).
#: ``mitgezogen_als_fehler`` ist aus demselben Grund ``boolean`` und nicht ``bool``.
SPALTENTYPEN: Final[Mapping[str, str]] = {
    "run_id": "string",
    "serie": "string",
    "design": "string",
    "modus": "string",
    "klasse": "string",
    "variante": "string",
    "fehlerrate": "Float64",
    "wiederholung": "Int64",
    "verfahren": "string",
    "ebene": "string",
    "mitgezogen_als_fehler": "boolean",
    "gruppe_art": "string",
    "gruppe": "string",
    "metrik": "string",
    "wert": "Float64",
    "n": "Int64",
}

#: Schluessel, die :func:`baue_langformat` in den Faktorstufen des Laufs erwartet.
#:
#: Sie stammen aus ``manifest.json``, Abschnitt ``faktorstufen``, und werden hier
#: **nicht** mit Vorgabewerten ergaenzt: Eine fehlende Faktorstufe ist ein
#: unvollstaendiges Manifest und keine Kennzahl mit unbekanntem Bezug.
FAKTORSPALTEN: Final[tuple[str, ...]] = (
    "serie",
    "design",
    "modus",
    "klasse",
    "variante",
    "fehlerrate",
    "wiederholung",
)

#: Auspraegungen der Spalte ``gruppe_art``.
GRUPPE_GESAMT: Final[str] = "gesamt"
GRUPPE_FEHLERKLASSE: Final[str] = "fehlerklasse"
GRUPPE_VARIANTE: Final[str] = "injektor_variante"
GRUPPE_REGEL: Final[str] = "regel"

#: Fuellwert der Spalten ``ebene`` und ``gruppe``, wenn es keinen Bezug gibt.
OHNE_BEZUG: Final[str] = ""

#: Trennzeichen des zusammengesetzten Gruppenschluessels der Kreuztabelle.
KREUZ_TRENNER: Final[str] = "|"

#: Stellen, auf die jeder Gleitkommawert in ``metrics.json`` gerundet wird.
#:
#: Ohne Rundung schriebe dieselbe Rechnung auf verschiedenen Rechnern Dateien, die
#: sich in der letzten Binaerstelle unterscheiden. Sechs Stellen liegen weit
#: unterhalb jeder berichteten Genauigkeit und machen den Byte-Vergleich zweier
#: Laeufe trotzdem moeglich (Architekturregel A2). Das **Langformat** rundet
#: dagegen nicht: Es ist Rechengrundlage der Inferenzstatistik, kein Bericht.
_NACHKOMMASTELLEN: Final[int] = 6

#: Spalten, ueber die das Langformat sortiert wird — alle ausser den Messwerten.
_SCHLUESSEL_SPALTEN: Final[tuple[str, ...]] = tuple(
    spalte for spalte in METRICS_LONG_SPALTEN if spalte not in {"wert", "n"}
)

#: Kennzahlen der Konfusionsmatrix, in Ausgabereihenfolge.
#:
#: ``tp_recall`` steht mit dabei, obwohl es nur die Constraint-Ebene setzt: Ohne
#: diesen Wert waere der dort berichtete Recall aus den abgelegten Rohwerten nicht
#: nachrechenbar, weil ``tp`` dort Verstoesse zaehlt und ``fn`` Wahrheitszellen
#: (:class:`~src.evaluation.modell.Konfusion`). Auf allen uebrigen Ebenen ist er
#: ``None`` und der Recall folgt wie gewohnt aus ``tp`` und ``fn``.
_KONFUSIONSFELDER: Final[tuple[str, ...]] = ("tp", "fp", "fn", "tn", "tp_recall")

#: Abgeleitete Kennzahlen, in Ausgabereihenfolge.
_KENNZAHLFELDER: Final[tuple[str, ...]] = (
    "precision",
    "recall",
    "f1",
    "mcc",
    "fpr_clean",
    "pr_auc",
)

#: Diagnostische Kennzahlen je Regel, in Ausgabereihenfolge.
_REGELFELDER: Final[tuple[str, ...]] = ("meldungen", "tp", "precision", "anteil_einzige_regel")

#: Kennzahlen der Laufmessung, in Ausgabereihenfolge.
_MESSFELDER: Final[tuple[str, ...]] = (
    "laufzeit_s",
    "laufzeit_s_je_1000_zeilen",
    "speicher_mb",
    "speicher_mb_je_1000_zeilen",
)


# ---------------------------------------------------------------------------
# Langformat
# ---------------------------------------------------------------------------


def _grundwerte(run_id: str, faktorstufen: Mapping[str, Any]) -> dict[str, Any]:
    """Baut die laufweiten Spaltenwerte jeder Langformatzeile.

    Args:
        run_id: Kennung des Laufs.
        faktorstufen: Abschnitt ``faktorstufen`` aus ``manifest.json``.

    Returns:
        Die Werte der Spalten ``run_id`` und :data:`FAKTORSPALTEN`.

    Raises:
        AuswertungsFehler: Wenn eine Faktorstufe fehlt. Bewusst kein Vorgabewert:
            Eine Zeile mit unbekannter Fehlerrate waere in Phase 6 nicht
            zuzuordnen und wuerde die Gruppierung stillschweigend verfaelschen.
    """
    fehlend = [name for name in FAKTORSPALTEN if name not in faktorstufen]
    if fehlend:
        raise AuswertungsFehler(
            f"Den Faktorstufen des Laufs {run_id!r} fehlen die Angaben {fehlend}. Sie stehen "
            "im Abschnitt 'faktorstufen' der manifest.json, die 'python scripts/inject.py' "
            "schreibt."
        )
    werte: dict[str, Any] = {"run_id": run_id}
    werte.update({name: faktorstufen[name] for name in FAKTORSPALTEN})
    return werte


def _zeile(  # noqa: PLR0913 - eine Langformatzeile ist genau diese Kombination
    grund: Mapping[str, Any],
    *,
    verfahren: str,
    ebene: str,
    mitgezogen: bool | None,
    gruppe_art: str,
    gruppe: str,
    metrik: str,
    wert: float | None,
    n: int | None = None,
) -> dict[str, Any]:
    """Baut eine einzelne Zeile des Langformats.

    Args:
        grund: Ergebnis von :func:`_grundwerte`.
        verfahren: Kurzname des Verfahrens.
        ebene: Wert von :class:`~src.evaluation.modell.Ebene` oder
            :data:`OHNE_BEZUG`.
        mitgezogen: Schalterstellung, oder ``None``, wenn der Schalter auf diese
            Kennzahl nicht anwendbar ist.
        gruppe_art: Bezugsobjekt der Kennzahl.
        gruppe: Kennung des Bezugsobjekts, oder :data:`OHNE_BEZUG`.
        metrik: Name der Kennzahl.
        wert: Gemessener Wert, oder ``None``, wenn er nicht bildbar ist.
        n: Fallzahl der Gruppe, wo es eine gibt.

    Returns:
        Die Zeile als Abbildung ueber :data:`METRICS_LONG_SPALTEN`.
    """
    return {
        **grund,
        "verfahren": verfahren,
        "ebene": ebene,
        "mitgezogen_als_fehler": mitgezogen,
        "gruppe_art": gruppe_art,
        "gruppe": gruppe,
        "metrik": metrik,
        "wert": None if wert is None else float(wert),
        "n": n,
    }


def _kennzahlwerte(kennzahlen: Kennzahlen | None) -> dict[str, float | None]:
    """Liest alle Kennzahlen einer Ebene als flache Abbildung.

    Args:
        kennzahlen: Die Kennzahlen der Ebene, oder ``None``, wenn auf ihr keine
            Konfusionsmatrix bildbar ist.

    Returns:
        Je Kennzahlname den Wert; durchgehend ``None``, wenn die Ebene nicht
        auswertbar ist. Die Namen bleiben auch dann vollstaendig — die Zeilen
        entstehen, ihr Wert fehlt (siehe Modul-Docstring).
    """
    namen = (*_KONFUSIONSFELDER, *_KENNZAHLFELDER)
    if kennzahlen is None:
        return dict.fromkeys(namen)
    werte: dict[str, float | None] = {
        name: getattr(kennzahlen.konfusion, name) for name in _KONFUSIONSFELDER
    }
    werte.update({name: getattr(kennzahlen, name) for name in _KENNZAHLFELDER})
    return werte


def _gruppenzeilen(  # noqa: PLR0913 - der Bezug einer Zeile besteht aus genau diesen Angaben
    grund: Mapping[str, Any],
    *,
    verfahren: str,
    ebene: Ebene,
    mitgezogen: bool,
    gruppe_art: str,
    eintraege: Sequence[Gruppenrecall],
) -> list[dict[str, Any]]:
    """Baut die Zeilen eines gruppenweisen Recalls samt Konfidenzintervall.

    Args:
        grund: Ergebnis von :func:`_grundwerte`.
        verfahren: Kurzname des Verfahrens.
        ebene: Ausgewertete Ebene.
        mitgezogen: Schalterstellung.
        gruppe_art: :data:`GRUPPE_FEHLERKLASSE` oder :data:`GRUPPE_VARIANTE`.
        eintraege: Die Gruppenrecalls dieser Ebene.

    Returns:
        Je Gruppe vier Zeilen: ``tp``, ``recall`` und die beiden Grenzen. ``n``
        steht in **jeder** davon — ein Recall ohne seine Fallzahl ist in einer
        Tabelle mit sechzig Varianten nicht interpretierbar.
    """
    zeilen: list[dict[str, Any]] = []
    for eintrag in eintraege:
        for metrik, wert in (
            ("tp", float(eintrag.tp)),
            ("recall", eintrag.recall),
            ("recall_ci_unten", eintrag.ci_unten),
            ("recall_ci_oben", eintrag.ci_oben),
        ):
            zeilen.append(
                _zeile(
                    grund,
                    verfahren=verfahren,
                    ebene=ebene.value,
                    mitgezogen=mitgezogen,
                    gruppe_art=gruppe_art,
                    gruppe=eintrag.gruppe,
                    metrik=metrik,
                    wert=wert,
                    n=eintrag.n,
                )
            )
    return zeilen


def _ebenenzeilen(
    grund: Mapping[str, Any],
    *,
    verfahren: str,
    mitgezogen: bool,
    auswertung: Ebenenauswertung,
) -> list[dict[str, Any]]:
    """Baut alle Zeilen einer Auswertungsebene.

    Args:
        grund: Ergebnis von :func:`_grundwerte`.
        verfahren: Kurzname des Verfahrens.
        mitgezogen: Schalterstellung.
        auswertung: Die Ebenenauswertung.

    Returns:
        Die Zeilen der Konfusionsmatrix, der beiden gruppenweisen Recalls, des
        variantengewichteten Klassenrecalls und der beiden Macro-Mittel.
    """
    ebene = auswertung.ebene
    zeilen = [
        _zeile(
            grund,
            verfahren=verfahren,
            ebene=ebene.value,
            mitgezogen=mitgezogen,
            gruppe_art=GRUPPE_GESAMT,
            gruppe=OHNE_BEZUG,
            metrik=metrik,
            wert=wert,
        )
        for metrik, wert in _kennzahlwerte(auswertung.kennzahlen).items()
    ]
    zeilen.extend(
        _gruppenzeilen(
            grund,
            verfahren=verfahren,
            ebene=ebene,
            mitgezogen=mitgezogen,
            gruppe_art=GRUPPE_FEHLERKLASSE,
            eintraege=auswertung.recall_je_klasse,
        )
    )
    zeilen.extend(
        _gruppenzeilen(
            grund,
            verfahren=verfahren,
            ebene=ebene,
            mitgezogen=mitgezogen,
            gruppe_art=GRUPPE_VARIANTE,
            eintraege=auswertung.recall_je_variante,
        )
    )
    zeilen.extend(
        _zeile(
            grund,
            verfahren=verfahren,
            ebene=ebene.value,
            mitgezogen=mitgezogen,
            gruppe_art=GRUPPE_FEHLERKLASSE,
            gruppe=klasse,
            metrik="recall_variantengewichtet",
            wert=wert,
        )
        for klasse, wert in sorted(auswertung.recall_variantengewichtet_je_klasse.items())
    )
    zeilen.extend(
        _zeile(
            grund,
            verfahren=verfahren,
            ebene=ebene.value,
            mitgezogen=mitgezogen,
            gruppe_art=GRUPPE_GESAMT,
            gruppe=OHNE_BEZUG,
            metrik=metrik,
            wert=wert,
        )
        for metrik, wert in (
            ("macro_recall_klassen", auswertung.macro_recall_klassen),
            ("macro_recall_varianten", auswertung.macro_recall_varianten),
        )
    )
    return zeilen


def _regelzeilen(
    grund: Mapping[str, Any],
    *,
    verfahren: str,
    auswertung: Auswertung,
) -> list[dict[str, Any]]:
    """Baut die Zeilen der Regeldiagnose und der Kreuztabelle.

    Beide sind ausschliesslich zellbasiert definiert und tragen deshalb die Ebene
    :attr:`~src.evaluation.modell.Ebene.ZELLE`.

    Args:
        grund: Ergebnis von :func:`_grundwerte`.
        verfahren: Kurzname des Verfahrens.
        auswertung: Die Auswertung einer Schalterstellung.

    Returns:
        Je Regel vier Diagnosezeilen und je besetzter Kreuztabellenzelle eine
        Zeile mit dem zusammengesetzten Schluessel ``<regel_id>|<fehlerklasse>``.
    """
    mitgezogen = auswertung.mitgezogen_als_fehler
    zeilen = [
        _zeile(
            grund,
            verfahren=verfahren,
            ebene=Ebene.ZELLE.value,
            mitgezogen=mitgezogen,
            gruppe_art=GRUPPE_REGEL,
            gruppe=diagnose.regel_id,
            metrik=metrik,
            wert=float(getattr(diagnose, metrik)),
            n=diagnose.meldungen,
        )
        for diagnose in auswertung.regeldiagnose
        for metrik in _REGELFELDER
    ]
    zeilen.extend(
        _zeile(
            grund,
            verfahren=verfahren,
            ebene=Ebene.ZELLE.value,
            mitgezogen=mitgezogen,
            gruppe_art=GRUPPE_REGEL,
            gruppe=f"{eintrag.regel_id}{KREUZ_TRENNER}{eintrag.fehlerklasse}",
            metrik="treffer",
            wert=float(eintrag.treffer),
        )
        for eintrag in auswertung.kreuztabelle
    )
    return zeilen


def _messzeilen(
    grund: Mapping[str, Any],
    *,
    verfahren: str,
    messung: Laufmessung,
) -> list[dict[str, Any]]:
    """Baut die Zeilen der Laufzeit- und Speichermessung.

    Sie tragen weder eine Ebene noch eine Schalterstellung: Gemessen wird das
    Verfahren auf dem Lauf, nicht eine Auswertungsebene. ``ebene`` ist deshalb
    :data:`OHNE_BEZUG` und ``mitgezogen_als_fehler`` fehlend.

    Args:
        grund: Ergebnis von :func:`_grundwerte`.
        verfahren: Kurzname des Verfahrens.
        messung: Die Laufmessung.

    Returns:
        Vier Zeilen; die beiden Speicherzeilen tragen einen fehlenden Wert, wenn
        die Messung abgeschaltet war.
    """
    return [
        _zeile(
            grund,
            verfahren=verfahren,
            ebene=OHNE_BEZUG,
            mitgezogen=None,
            gruppe_art=GRUPPE_GESAMT,
            gruppe=OHNE_BEZUG,
            metrik=metrik,
            wert=getattr(messung, metrik),
            n=messung.zeilen_gesamt,
        )
        for metrik in _MESSFELDER
    ]


def baue_langformat(
    run_id: str,
    faktorstufen: Mapping[str, Any],
    ergebnisse: Sequence[Verfahrensergebnis],
) -> pd.DataFrame:
    """Baut das Langformat eines Laufs.

    Args:
        run_id: Kennung des Laufs.
        faktorstufen: Abschnitt ``faktorstufen`` aus dem ``manifest.json`` des
            Laufs; muss :data:`FAKTORSPALTEN` vollstaendig enthalten.
        ergebnisse: Die Verfahrensergebnisse, ueblicherweise das Ergebnis von
            :func:`src.evaluation.pipeline.bewerte`.

    Returns:
        Einen nach :data:`_SCHLUESSEL_SPALTEN` sortierten Datenrahmen mit den
        Spalten :data:`METRICS_LONG_SPALTEN` und den Typen aus
        :data:`SPALTENTYPEN`.

    Raises:
        AuswertungsFehler: Wenn eine Faktorstufe fehlt.
    """
    grund = _grundwerte(run_id, faktorstufen)
    zeilen: list[dict[str, Any]] = []
    for ergebnis in ergebnisse:
        zeilen.extend(_messzeilen(grund, verfahren=ergebnis.verfahren, messung=ergebnis.messung))
        for auswertung in ergebnis.auswertungen:
            for ebene in Ebene:
                zeilen.extend(
                    _ebenenzeilen(
                        grund,
                        verfahren=ergebnis.verfahren,
                        mitgezogen=auswertung.mitgezogen_als_fehler,
                        auswertung=auswertung.ebenen[ebene],
                    )
                )
            zeilen.extend(_regelzeilen(grund, verfahren=ergebnis.verfahren, auswertung=auswertung))
    return _sortiere(_mit_schema(pd.DataFrame(zeilen, columns=list(METRICS_LONG_SPALTEN))))


def _mit_schema(rahmen: pd.DataFrame) -> pd.DataFrame:
    """Bringt einen Datenrahmen auf Spaltenmenge und Typen des Langformats.

    Args:
        rahmen: Zu pruefender Datenrahmen.

    Returns:
        Den Datenrahmen mit den Spalten in der Reihenfolge von
        :data:`METRICS_LONG_SPALTEN` und den Typen aus :data:`SPALTENTYPEN`.

    Raises:
        AuswertungsFehler: Wenn eine Spalte fehlt oder eine unbekannte hinzukommt.
            Eine ueberzaehlige Spalte in der Sammeldatei stammt aus einer aelteren
            Fassung dieses Moduls; sie stillschweigend zu verwerfen hiesse, zwei
            unvereinbare Formate in einer Datei zu mischen.
    """
    fehlend = [spalte for spalte in METRICS_LONG_SPALTEN if spalte not in rahmen.columns]
    ueberzaehlig = [spalte for spalte in rahmen.columns if spalte not in METRICS_LONG_SPALTEN]
    if fehlend or ueberzaehlig:
        raise AuswertungsFehler(
            f"Das Langformat erwartet genau die Spalten {list(METRICS_LONG_SPALTEN)}. "
            f"Fehlend: {fehlend}. Ueberzaehlig: {ueberzaehlig}."
        )
    return rahmen[list(METRICS_LONG_SPALTEN)].astype(dict(SPALTENTYPEN))


def _sortiere(rahmen: pd.DataFrame) -> pd.DataFrame:
    """Sortiert das Langformat deterministisch ueber alle Schluesselspalten.

    Args:
        rahmen: Das Langformat.

    Returns:
        Den sortierten Rahmen mit neuem, fortlaufendem Index. Ohne diese
        Sortierung haenge der Dateiinhalt an der Abarbeitungsreihenfolge der
        Laeufe (Architekturregel A2).
    """
    return rahmen.sort_values(
        by=list(_SCHLUESSEL_SPALTEN), kind="stable", na_position="last"
    ).reset_index(drop=True)


def schreibe_langformat(rahmen: pd.DataFrame, pfad: Path) -> Path:
    """Traegt das Langformat eines Laufs in die Sammeldatei ein.

    Vorhandene Zeilen mit einer der neu geschriebenen ``run_id`` werden ersetzt,
    alle uebrigen bleiben stehen. Ein zweiter Aufruf desselben Laufs veraendert
    die Datei damit nicht — die Ergebnisdatei ist idempotent fortschreibbar.

    Args:
        rahmen: Ergebnis von :func:`baue_langformat`.
        pfad: Zieldatei, ueblicherweise ``results/metrics_long.parquet``.

    Returns:
        Den geschriebenen Pfad.

    Raises:
        AuswertungsFehler: Wenn der neue Rahmen oder die vorhandene Datei nicht
            dem Schema entspricht.
    """
    neu = _mit_schema(rahmen)
    kennungen = set(neu["run_id"].dropna().unique())

    if pfad.is_file():
        bestand = _mit_schema(pd.read_parquet(pfad))
        behalten = bestand[~bestand["run_id"].isin(kennungen)]
        neu = pd.concat([behalten, neu], ignore_index=True) if len(behalten) else neu

    gesamt = _sortiere(_mit_schema(neu))
    pfad.parent.mkdir(parents=True, exist_ok=True)
    gesamt.to_parquet(pfad, index=False)
    return pfad


# ---------------------------------------------------------------------------
# metrics.json
# ---------------------------------------------------------------------------


def _rund(wert: float | None) -> float | None:
    """Rundet einen Gleitkommawert fuer die JSON-Ausgabe.

    Args:
        wert: Der Wert, oder ``None``.

    Returns:
        Den gerundeten Wert, oder ``None``. Siehe :data:`_NACHKOMMASTELLEN` zur
        Begruendung der Rundung.
    """
    return None if wert is None else round(float(wert), _NACHKOMMASTELLEN)


def _konfusion_als_dict(konfusion: Konfusion) -> dict[str, int | None]:
    """Baut die JSON-Form einer Konfusionsmatrix."""
    return {
        "tp": konfusion.tp,
        "fp": konfusion.fp,
        "fn": konfusion.fn,
        "tn": konfusion.tn,
        "grundgesamtheit": konfusion.grundgesamtheit,
        "tp_recall": konfusion.tp_recall,
    }


def _kennzahlen_als_dict(kennzahlen: Kennzahlen | None) -> dict[str, Any] | None:
    """Baut die JSON-Form der Kennzahlen einer Ebene.

    Args:
        kennzahlen: Die Kennzahlen, oder ``None``.

    Returns:
        Die Kennzahlen samt Rohwerten, oder ``None``. Die Rohwerte stehen
        ausdruecklich mit dabei: Aus abgelegten ``tp``, ``fp``, ``fn`` und ``tn``
        ist eine weitere Kennzahl spaeter in einer Sekunde nachgerechnet, ein
        wiederholter Lauf kostet Stunden.
    """
    if kennzahlen is None:
        return None
    werte: dict[str, Any] = {"konfusion": _konfusion_als_dict(kennzahlen.konfusion)}
    werte.update({name: _rund(getattr(kennzahlen, name)) for name in _KENNZAHLFELDER})
    return werte


def _gruppen_als_liste(eintraege: Sequence[Gruppenrecall]) -> list[dict[str, Any]]:
    """Baut die JSON-Form einer Folge von Gruppenrecalls."""
    return [
        {
            "gruppe": eintrag.gruppe,
            "n": eintrag.n,
            "tp": eintrag.tp,
            "recall": _rund(eintrag.recall),
            "ci_unten": _rund(eintrag.ci_unten),
            "ci_oben": _rund(eintrag.ci_oben),
        }
        for eintrag in eintraege
    ]


def _ebene_als_dict(auswertung: Ebenenauswertung) -> dict[str, Any]:
    """Baut die JSON-Form einer Ebenenauswertung."""
    return {
        "kennzahlen": _kennzahlen_als_dict(auswertung.kennzahlen),
        "nicht_auswertbar_grund": auswertung.nicht_auswertbar_grund,
        "recall_je_klasse": _gruppen_als_liste(auswertung.recall_je_klasse),
        "recall_je_variante": _gruppen_als_liste(auswertung.recall_je_variante),
        "recall_variantengewichtet_je_klasse": {
            klasse: _rund(wert)
            for klasse, wert in sorted(auswertung.recall_variantengewichtet_je_klasse.items())
        },
        "macro_recall_klassen": _rund(auswertung.macro_recall_klassen),
        "macro_recall_varianten": _rund(auswertung.macro_recall_varianten),
    }


def _auswertung_als_dict(auswertung: Auswertung) -> dict[str, Any]:
    """Baut die JSON-Form einer Auswertung samt Regeldiagnose und Kreuztabelle."""
    return {
        "mitgezogen_als_fehler": auswertung.mitgezogen_als_fehler,
        "ebenen": {ebene.value: _ebene_als_dict(auswertung.ebenen[ebene]) for ebene in Ebene},
        "regeldiagnose": [
            {
                "regel_id": diagnose.regel_id,
                "meldungen": diagnose.meldungen,
                "tp": diagnose.tp,
                "precision": _rund(diagnose.precision),
                "anteil_einzige_regel": _rund(diagnose.anteil_einzige_regel),
            }
            for diagnose in auswertung.regeldiagnose
        ],
        "kreuztabelle": [
            {
                "regel_id": eintrag.regel_id,
                "fehlerklasse": eintrag.fehlerklasse,
                "treffer": eintrag.treffer,
            }
            for eintrag in auswertung.kreuztabelle
        ],
    }


def _ergebnis_als_dict(ergebnis: Verfahrensergebnis) -> dict[str, Any]:
    """Baut die JSON-Form eines Verfahrensergebnisses."""
    return {
        "beschreibung": ergebnis.beschreibung,
        "lokalisiert_zellen": ergebnis.lokalisiert_zellen,
        "in_inferenzstatistik": ergebnis.in_inferenzstatistik,
        "messung": {
            "zeilen_gesamt": ergebnis.messung.zeilen_gesamt,
            **{name: _rund(getattr(ergebnis.messung, name)) for name in _MESSFELDER},
        },
        "meldungen_gesamt": ergebnis.meldungen_gesamt,
        "markierte_zellen": ergebnis.markierte_zellen,
        "meldungen_ohne_zeilenbezug": ergebnis.meldungen_ohne_zeilenbezug,
        "markierte_zellen_row_id": ergebnis.markierte_zellen_row_id,
        "auswertungen": [_auswertung_als_dict(auswertung) for auswertung in ergebnis.auswertungen],
    }


def _wahrheit_als_dict(wahrheit: GroundTruth) -> dict[str, Any]:
    """Baut die JSON-Form des Ground Truth eines Laufs.

    Die Fallzahlen je Klasse und Variante stehen hier **einmal** und gelten fuer
    alle Verfahren; sie sind eine Eigenschaft des Laufs, nicht der Messung. Ohne
    sie waere jeder gruppenweise Recall in der Ergebnisdatei nicht einzuordnen.
    """
    zellen_je_klasse: dict[str, int] = {}
    zellen_je_variante: dict[str, int] = {}
    for zelle in wahrheit.zellen:
        if zelle.mitgezogen:
            continue
        zellen_je_klasse[zelle.fehlerklasse] = zellen_je_klasse.get(zelle.fehlerklasse, 0) + 1
        kennung = zelle.injektor_variante_id
        zellen_je_variante[kennung] = zellen_je_variante.get(kennung, 0) + 1

    return {
        "klassen": list(wahrheit.klassen),
        "varianten": list(wahrheit.varianten),
        "zellen_gesamt": len(wahrheit.zellen),
        "zellen_mitgezogen": sum(1 for zelle in wahrheit.zellen if zelle.mitgezogen),
        "zellen_je_klasse": dict(sorted(zellen_je_klasse.items())),
        "zellen_je_variante": dict(sorted(zellen_je_variante.items())),
        "saetze_gesamt": len(wahrheit.satzmenge(mitgezogen_als_fehler=True)),
        "saetze_ohne_mitgezogen": len(wahrheit.satzmenge(mitgezogen_als_fehler=False)),
        "universum_zellen": wahrheit.universum_zellen,
        "universum_saetze": wahrheit.universum_saetze,
        "zeilen_je_entitaet": dict(sorted(wahrheit.zeilen_je_entitaet.items())),
    }


def baue_metrics(
    run_id: str,
    faktorstufen: Mapping[str, Any],
    wahrheit: GroundTruth,
    ergebnisse: Sequence[Verfahrensergebnis],
    *,
    zusatz: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Baut den vollstaendigen Inhalt der ``metrics.json`` eines Laufs.

    Args:
        run_id: Kennung des Laufs.
        faktorstufen: Abschnitt ``faktorstufen`` aus dem ``manifest.json``.
        wahrheit: Ground Truth des Laufs.
        ergebnisse: Die Verfahrensergebnisse.
        zusatz: Je Verfahrensnamen weitere Angaben, die nur dieses Verfahren
            kennt — der Schwellen-Sweep von B2, der Ausdrueckbarkeitsbericht von
            B3. Sie stehen bewusst **nicht** im gemeinsamen Ergebnistyp: Ein Feld
            ``sweep``, das bei drei von vier Verfahren leer bleibt, waere ein
            Formatschaden zugunsten eines Sonderfalls.

    Returns:
        Ein JSON-faehiges Woerterbuch aus reinen Grundtypen, ohne Zeitstempel
        (Architekturregel A2).

    Raises:
        AuswertungsFehler: Wenn ``zusatz`` ein Verfahren nennt, das gar nicht
            ausgewertet wurde. Ein stillschweigend verworfener Zusatz waere ein
            Ergebnis, das niemand vermisst.
    """
    verfahren = {ergebnis.verfahren: _ergebnis_als_dict(ergebnis) for ergebnis in ergebnisse}
    for name, angaben in sorted((zusatz or {}).items()):
        if name not in verfahren:
            raise AuswertungsFehler(
                f"Zusatzangaben zu {name!r}, aber dieses Verfahren wurde nicht ausgewertet. "
                f"Ausgewertet wurden: {sorted(verfahren)}."
            )
        verfahren[name] = {**verfahren[name], **dict(angaben)}

    return {
        "run_id": run_id,
        "erzeugt_von": "scripts/evaluate.py",
        "faktorstufen": dict(sorted(faktorstufen.items())),
        "ground_truth": _wahrheit_als_dict(wahrheit),
        "verfahren": dict(sorted(verfahren.items())),
    }


def schreibe_metrics(inhalt: Mapping[str, Any], pfad: Path) -> Path:
    """Schreibt die ``metrics.json`` eines Laufs.

    Args:
        inhalt: Ergebnis von :func:`baue_metrics`.
        pfad: Zieldatei, ueblicherweise ``<laufverzeichnis>/metrics.json``.

    Returns:
        Den geschriebenen Pfad.
    """
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(
        json.dumps(dict(inhalt), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return pfad
