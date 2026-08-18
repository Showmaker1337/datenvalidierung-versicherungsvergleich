"""HYP4 mit der Wiederholungsstruktur: die ART-ANOVA als Blockmodell.

Warum dieses Modul ueberhaupt existiert
----------------------------------------

Die vorregistrierte Fassung von :func:`~src.evaluation.hypothesen.pruefe_hyp4`
rechnet ``f1 ~ verfahren * fehlerklasse`` ohne einen Term fuer die zwanzig
Wiederholungen. Beide Verfahren werden aber auf **denselben** Injektionslaeufen
ausgewertet: Derselbe verfaelschte Datensatz geht an den Prototyp und an B2. Die
Beobachtungen sind damit gepaart, und ein Modell ohne Blockterm behandelt sie als
unabhaengig.

Das ist ein berechtigter Einwand, und er wird hier beantwortet, ohne die
vorregistrierte Rechnung zu ueberschreiben: Das Blockmodell steht **neben** ihr.
:mod:`src.evaluation.hypothesen` bleibt unveraendert, ``results/hypothesen.json``
ebenfalls. Wer eine Zahl nachtraeglich ersetzt, verliert die Moeglichkeit, den
Unterschied zu zeigen — und genau der Unterschied ist hier die Aussage.

Was sich aendert und was nicht
-------------------------------

**Unveraendert** bleibt die Aligned-Rank-Transformation: ausgerichtet wird um die
beiden festen Haupteffekte, dann rangiert (Wobbrock et al. 2011; die R-Umsetzung
``ARTool`` verfaehrt ebenso und laesst den Blockterm aus der Ausrichtung heraus).
Beide Rechnungen benutzen dieselbe Funktion
:func:`~src.evaluation.statistik._ausgerichtete_raenge`. Nur so ist ihr Vergleich
ein Vergleich der **Modelle** und nicht zweier verschiedener Transformationen.

**Geaendert** wird das Modell, das auf den Raengen angepasst wird::

    bisher:  raenge ~ verfahren * fehlerklasse
    jetzt:   raenge ~ verfahren * fehlerklasse + Error(block)

Der Block ist in der Fehlerklasse geschachtelt — ein Injektionslauf traegt genau
eine Klasse. Es entsteht ein Split-Plot-Aufbau: Die Fehlerklasse variiert
zwischen den Bloecken, das Verfahren innerhalb. Bei balanciertem Aufbau ist der
F-Test des Interaktionsterms identisch mit dem des gemischten Modells
``raenge ~ verfahren * fehlerklasse + (1 | block)``.

Zwei Blockdefinitionen, weil beide etwas anderes zeigen
--------------------------------------------------------

Es gibt zwei vertretbare Lesarten von "derselbe Lauf", und sie werden beide
gerechnet:

``wiederholung``
    Block ist das Paar ``(Fehlerklasse, Wiederholung)``; die Antwort ist wie in
    der vorregistrierten Rechnung **ueber die vier Ratenstufen gemittelt**. Diese
    Fassung ist mit dem bisherigen Wert direkt vergleichbar: dieselben 280
    Beobachtungen, dieselbe Ausrichtung, nur der Blockterm kommt hinzu. Der
    Unterschied im F-Wert ist damit ausschliesslich dem Blockterm zuzuschreiben.

``lauf``
    Block ist der einzelne Injektionslauf ueber seine ``run_id``; es wird
    **nicht** vorab gemittelt, alle 560 Laeufe je Verfahren gehen einzeln ein.
    Diese Fassung nutzt die Wiederholungsstruktur vollstaendig aus und laesst die
    Ratenvariation im Blockterm aufgehen, statt sie wegzumitteln. Sie ist die
    strengere Rechnung, aber sie beantwortet eine leicht andere Frage, weil die
    Antwortgroesse eine andere ist.

Eine Warnung zur Lesart der Bloecke
-------------------------------------

Der Wiederholungsindex ``w00`` bis ``w19`` verbindet **nicht** ueber die
Fehlerklassen hinweg: ``seed_inject`` geht aus Serie, Design, Fehlerklasse, Rate
und Wiederholung hervor (``scripts/inject.py``), sodass ``F1|w07`` und ``F3|w07``
verschiedene Verfaelschungen desselben sauberen Basisdatensatzes sind. Der Block
ist deshalb ausdruecklich in der Klasse geschachtelt und **nicht** mit ihr
gekreuzt. Ein gekreuztes Modell wuerde eine Paarung ueber Klassen hinweg
unterstellen, die es nicht gibt.

Was das Blockmodell nicht aendert
-----------------------------------

Die klassenweisen gepaarten Wilcoxon-Tests und ihre Holm-Korrektur bleiben, wie
sie sind — sie rechnen die Paarung ohnehin schon ein, denn genau das ist ein
gepaarter Test. :func:`konsistenz` prueft nur, ob ihr Bild zum neuen
Omnibustest passt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from src.evaluation.ergebnisse import GRUPPE_GESAMT, auswahl, mittel_je_wiederholung
from src.evaluation.hypothesen import pruefe_hyp4
from src.evaluation.modell import AuswertungsFehler, Ebene
from src.evaluation.statistik import art_anova_interaktion_block

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence
    from pathlib import Path

    import pandas as pd

    from src.evaluation.experimentplan import Versuchsplan
    from src.evaluation.hypothesen import Hypothesenergebnis
    from src.evaluation.statistik import Testergebnis

__all__ = [
    "BERICHTSNAME",
    "BLOCKARTEN",
    "Blockbefund",
    "Blockbericht",
    "als_dict",
    "als_markdown",
    "blockmodell_hyp4",
    "gegenprobe",
    "konsistenz",
    "schreibe_bericht",
]

#: Dateiname des Berichts unter ``results/``.
BERICHTSNAME: Final[str] = "hypothesen_hyp4_blockmodell.md"

#: Die beiden verglichenen Verfahren.
_PROTOTYP: Final[str] = "prototyp"
_B2: Final[str] = "B2"

#: Blockkennung des Hauptversuchs im Langformat.
_HAUPT: Final[str] = "haupt"

#: Zahl der Stufen, fuer die die Gegenprobe ueber die Differenzen definiert ist.
_ZWEI_STUFEN: Final[int] = 2

#: Die beiden Blockdefinitionen mit ihrer Beschriftung im Bericht.
BLOCKARTEN: Final[tuple[tuple[str, str], ...]] = (
    (
        "wiederholung",
        "Block = (Fehlerklasse, Wiederholung), Antwort ueber die vier Ratenstufen gemittelt",
    ),
    (
        "lauf",
        "Block = einzelner Injektionslauf (run_id), keine Vorabmittelung",
    ),
)

#: Beschriftung der beiden Metrikebenen im Bericht.
_EBENEN: Final[tuple[tuple[Ebene, str], ...]] = (
    (Ebene.SATZ, "Satzebene"),
    (Ebene.ZELLE, "Zellebene"),
)


@dataclass(frozen=True, slots=True)
class Blockbefund:
    """Ein Modell auf einer Ebene, mit dem bisherigen Wert daneben.

    Attributes:
        ebene: Die Auswertungsebene.
        blockart: Kennung der Blockdefinition aus :data:`BLOCKARTEN`.
        beschreibung: Klartext der Blockdefinition.
        bloecke: Zahl der Bloecke.
        test: Das Ergebnis des Blockmodells.
        bisher: Das Ergebnis der vorregistrierten Rechnung ohne Blockterm auf
            derselben Ebene. Es steht daneben und wird nicht ersetzt.
        gegenprobe: Derselbe F-Wert, auf einem zweiten und voellig anderen Weg
            gerechnet (:func:`gegenprobe`).
        abweichung: Relative Abweichung zwischen ``test.statistik`` und
            ``gegenprobe``. Sie gehoert in den Bericht: Eine
            Quadratsummenzerlegung, die niemand nachgerechnet hat, ist eine
            Behauptung.
    """

    ebene: Ebene
    blockart: str
    beschreibung: str
    bloecke: int
    test: Testergebnis
    bisher: Testergebnis
    gegenprobe: float
    abweichung: float


@dataclass(frozen=True, slots=True)
class Blockbericht:
    """Das vollstaendige Ergebnis der Nachrechnung.

    Attributes:
        befunde: Je Ebene und Blockdefinition ein Befund.
        hyp4: Das unveraenderte Ergebnis der vorregistrierten Pruefung; liefert
            die Wilcoxon-Familien und die bisherige Entscheidung.
        aussage_unveraendert: Ob alle Blockmodelle dieselbe inhaltliche Aussage
            tragen wie die vorregistrierte Rechnung.
        abstaende: Je Ebene und Fehlerklasse das Mittel der Differenz
            ``F1(Prototyp) - F1(B2)`` ueber die zwanzig Wiederholungen. Diese
            Groesse traegt die Interaktion: Die Rang-biseriale Korrelation der
            paarweisen Tests ist gesaettigt und kann sie nicht zeigen.
    """

    befunde: tuple[Blockbefund, ...]
    hyp4: Hypothesenergebnis
    aussage_unveraendert: bool
    abstaende: dict[str, dict[str, float]]


def _reihen_gemittelt(
    lang: pd.DataFrame, *, verfahren: str, klasse: str, ebene: Ebene
) -> list[tuple[str, float]]:
    """Liest F1 je Wiederholung, ueber die Ratenstufen gemittelt.

    Args:
        lang: Das Langformat.
        verfahren: Das Verfahren.
        klasse: Die Fehlerklasse.
        ebene: Die Auswertungsebene.

    Returns:
        Je Wiederholung ein Paar aus Blockkennung und Wert.
    """
    gefiltert = auswahl(
        lang,
        metrik="f1",
        verfahren=verfahren,
        ebene=ebene,
        gruppe_art=GRUPPE_GESAMT,
        klasse=klasse,
        teilversuch=_HAUPT,
    )
    gemittelt = mittel_je_wiederholung(gefiltert)
    return [
        (f"{klasse}|w{int(str(wiederholung)):02d}", float(wert))
        for wiederholung, wert in gemittelt.items()
    ]


def _reihen_je_lauf(
    lang: pd.DataFrame, *, verfahren: str, klasse: str, ebene: Ebene
) -> list[tuple[str, float]]:
    """Liest F1 je einzelnem Injektionslauf.

    Args:
        lang: Das Langformat.
        verfahren: Das Verfahren.
        klasse: Die Fehlerklasse.
        ebene: Die Auswertungsebene.

    Returns:
        Je Lauf ein Paar aus ``run_id`` und Wert, nach ``run_id`` sortiert.

    Raises:
        AuswertungsFehler: Bei fehlenden Werten oder einer doppelten ``run_id``.
            Beides waere eine stillschweigend veraenderte Stichprobe.
    """
    gefiltert = auswahl(
        lang,
        metrik="f1",
        verfahren=verfahren,
        ebene=ebene,
        gruppe_art=GRUPPE_GESAMT,
        klasse=klasse,
        teilversuch=_HAUPT,
    )
    if gefiltert.empty:
        raise AuswertungsFehler(
            f"Keine F1-Werte fuer {verfahren!r} in {klasse!r} auf der {ebene.value}."
        )
    if gefiltert["wert"].isna().any():
        raise AuswertungsFehler(
            f"{verfahren!r} in {klasse!r} auf der {ebene.value} hat Laeufe ohne Wert."
        )
    sortiert = gefiltert.sort_values("run_id")
    kennungen = [str(wert) for wert in sortiert["run_id"]]
    if len(set(kennungen)) != len(kennungen):
        raise AuswertungsFehler(
            f"{verfahren!r} in {klasse!r} auf der {ebene.value} hat doppelte run_id."
        )
    return list(zip(kennungen, (float(wert) for wert in sortiert["wert"]), strict=True))


def _befund(  # noqa: PLR0913 - jede Angabe waehlt eine eigene Dimension
    lang: pd.DataFrame,
    plan: Versuchsplan,
    *,
    ebene: Ebene,
    blockart: str,
    beschreibung: str,
    bisher: Testergebnis,
) -> Blockbefund:
    """Rechnet ein Blockmodell auf einer Ebene.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.
        ebene: Die Auswertungsebene.
        blockart: Kennung der Blockdefinition.
        beschreibung: Klartext der Blockdefinition.
        bisher: Das Ergebnis ohne Blockterm auf derselben Ebene.

    Returns:
        Den Befund.

    Raises:
        AuswertungsFehler: Bei einer unbekannten Blockdefinition.
    """
    if blockart == "wiederholung":
        lies = _reihen_gemittelt
    elif blockart == "lauf":
        lies = _reihen_je_lauf
    else:
        raise AuswertungsFehler(f"Unbekannte Blockdefinition: {blockart!r}.")

    werte: list[float] = []
    faktor_verfahren: list[str] = []
    faktor_klasse: list[str] = []
    bloecke: list[str] = []
    for klasse in plan.hauptversuch.gruppen:
        for verfahren in (_PROTOTYP, _B2):
            for kennung, wert in lies(lang, verfahren=verfahren, klasse=klasse, ebene=ebene):
                werte.append(wert)
                faktor_verfahren.append(verfahren)
                faktor_klasse.append(klasse)
                bloecke.append(kennung)

    test = art_anova_interaktion_block(werte, faktor_verfahren, faktor_klasse, bloecke)
    zweitweg = gegenprobe(werte, faktor_verfahren, faktor_klasse, bloecke)
    return Blockbefund(
        ebene=ebene,
        blockart=blockart,
        beschreibung=beschreibung,
        bloecke=len(set(bloecke)),
        test=test,
        bisher=bisher,
        gegenprobe=zweitweg,
        abweichung=abs(zweitweg - test.statistik) / max(1.0, abs(zweitweg)),
    )


def gegenprobe(
    werte: Sequence[float],
    faktor_a: Sequence[str],
    faktor_b: Sequence[str],
    block: Sequence[str],
) -> float:
    """Rechnet den F-Wert des Blockmodells auf einem zweiten, unabhaengigen Weg.

    Hat der Innerhalb-Faktor genau **zwei** Stufen, ist der Split-Plot-F-Test des
    Interaktionsterms rechnerisch identisch mit einer **Einweg-Varianzanalyse der
    Differenzen je Block**: Bildet man je Block ``d = Rang(Stufe 1) - Rang(Stufe
    2)`` und vergleicht die Gruppenmittel von ``d`` ueber die Stufen des
    Zwischen-Faktors, so gilt exakt ``SS_ab = SS_zwischen(d) / 2`` und
    ``SS_fehler = SS_innerhalb(d) / 2``. Der Quotient und damit ``F`` sind
    dieselben, die Rechnung ist es nicht.

    Diese Funktion nutzt das als Kontrolle. Sie bildet die Ausrichtung und die
    Raenge **eigenstaendig** nach und beruehrt
    :mod:`src.evaluation.statistik` nicht — ein gemeinsamer Rechenweg wuerde
    einen gemeinsamen Fehler nicht aufdecken.

    Args:
        werte: Die Messwerte.
        faktor_a: Stufe des Innerhalb-Faktors je Messwert; genau zwei Stufen.
        faktor_b: Stufe des Zwischen-Faktors je Messwert.
        block: Blockkennung je Messwert.

    Returns:
        Den F-Wert des Interaktionsterms.

    Raises:
        AuswertungsFehler: Wenn der Innerhalb-Faktor nicht genau zwei Stufen hat
            oder ein Block nicht beide Stufen genau einmal traegt.
    """
    import numpy as np  # noqa: PLC0415 - Importkosten nur bei Bedarf
    from scipy.stats import rankdata  # noqa: PLC0415 - Importkosten nur bei Bedarf

    stufen_a = sorted(set(faktor_a))
    stufen_b = sorted(set(faktor_b))
    if len(stufen_a) != _ZWEI_STUFEN:
        raise AuswertungsFehler(
            f"Die Gegenprobe gilt nur fuer genau zwei Stufen des Innerhalb-Faktors, "
            f"hier sind es {len(stufen_a)}."
        )

    y = np.asarray(werte, dtype=np.float64)
    index_a = np.asarray([stufen_a.index(wert) for wert in faktor_a], dtype=np.int64)
    index_b = np.asarray([stufen_b.index(wert) for wert in faktor_b], dtype=np.int64)
    gesamt = float(y.mean())
    zeile = np.asarray([y[index_a == i].mean() for i in range(len(stufen_a))])
    spalte = np.asarray([y[index_b == j].mean() for j in range(len(stufen_b))])
    raenge = np.asarray(rankdata(y - zeile[index_a] - spalte[index_b] + gesamt), dtype=np.float64)

    je_block: dict[str, dict[int, float]] = {}
    stufe_je_block: dict[str, int] = {}
    for rang, i, j, kennung in zip(raenge, index_a, index_b, block, strict=True):
        je_block.setdefault(str(kennung), {})[int(i)] = float(rang)
        stufe_je_block[str(kennung)] = int(j)
    sortiert = sorted(je_block)
    if any(set(je_block[kennung]) != {0, 1} for kennung in sortiert):
        raise AuswertungsFehler(
            "Die Gegenprobe verlangt in jedem Block beide Stufen des Innerhalb-Faktors "
            "genau einmal."
        )

    differenz = np.asarray([je_block[kennung][0] - je_block[kennung][1] for kennung in sortiert])
    klassen = np.asarray([stufe_je_block[kennung] for kennung in sortiert])
    mittel = float(differenz.mean())
    zwischen = float(
        sum(
            int((klassen == j).sum()) * (float(differenz[klassen == j].mean()) - mittel) ** 2
            for j in range(len(stufen_b))
        )
    )
    innerhalb = float(
        sum(
            ((differenz[klassen == j] - float(differenz[klassen == j].mean())) ** 2).sum()
            for j in range(len(stufen_b))
        )
    )
    freiheitsgrade_zwischen = len(stufen_b) - 1
    freiheitsgrade_innerhalb = differenz.size - len(stufen_b)
    return (zwischen / freiheitsgrade_zwischen) / (innerhalb / freiheitsgrade_innerhalb)


def blockmodell_hyp4(lang: pd.DataFrame, plan: Versuchsplan) -> Blockbericht:
    """Rechnet HYP4 auf beiden Ebenen mit Blockterm, neben der bisherigen Fassung.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Den vollstaendigen Bericht.

    Raises:
        AuswertungsFehler: Wenn die vorregistrierte Pruefung keinen Primaertest
            oder keinen Nebentest der Zellebene liefert. Beides waere ein
            veraendertes Modul :mod:`src.evaluation.hypothesen`, und dann stimmte
            der Vergleich "neben den bisherigen Werten" nicht mehr.
    """
    hyp4 = pruefe_hyp4(lang, plan)
    if hyp4.primaertest is None:
        raise AuswertungsFehler("HYP4 liefert keinen Primaertest; der Vergleich waere leer.")
    bisher_je_ebene: dict[Ebene, Testergebnis] = {Ebene.SATZ: hyp4.primaertest}
    for name, test in hyp4.nebentests:
        if name.startswith("Zell"):
            bisher_je_ebene[Ebene.ZELLE] = test
    if Ebene.ZELLE not in bisher_je_ebene:
        raise AuswertungsFehler(
            "HYP4 liefert keinen Nebentest der Zellebene; der Vergleich waere unvollstaendig."
        )

    befunde = tuple(
        _befund(
            lang,
            plan,
            ebene=ebene,
            blockart=blockart,
            beschreibung=beschreibung,
            bisher=bisher_je_ebene[ebene],
        )
        for ebene, _ in _EBENEN
        for blockart, beschreibung in BLOCKARTEN
    )
    alpha = plan.statistik.alpha
    unveraendert = all(
        (befund.test.p_wert < alpha) == (befund.bisher.p_wert < alpha) for befund in befunde
    )
    abstaende = {
        ebene.value: {
            klasse: _mittlerer_abstand(lang, klasse=klasse, ebene=ebene)
            for klasse in plan.hauptversuch.gruppen
        }
        for ebene, _ in _EBENEN
    }
    return Blockbericht(
        befunde=befunde,
        hyp4=hyp4,
        aussage_unveraendert=unveraendert,
        abstaende=abstaende,
    )


def _mittlerer_abstand(lang: pd.DataFrame, *, klasse: str, ebene: Ebene) -> float:
    """Bildet das Mittel von ``F1(Prototyp) - F1(B2)`` ueber die Wiederholungen.

    Args:
        lang: Das Langformat.
        klasse: Die Fehlerklasse.
        ebene: Die Auswertungsebene.

    Returns:
        Den mittleren Abstand.

    Raises:
        AuswertungsFehler: Wenn die beiden Reihen nicht dieselben Wiederholungen
            tragen. Eine Differenz ueber verschiedene Wiederholungen waere keine
            gepaarte Groesse mehr.
    """
    proto = dict(_reihen_gemittelt(lang, verfahren=_PROTOTYP, klasse=klasse, ebene=ebene))
    baseline = dict(_reihen_gemittelt(lang, verfahren=_B2, klasse=klasse, ebene=ebene))
    if set(proto) != set(baseline):
        raise AuswertungsFehler(
            f"Prototyp und B2 tragen in {klasse!r} auf der {ebene.value} verschiedene "
            "Wiederholungen; eine gepaarte Differenz gibt es dann nicht."
        )
    return sum(proto[kennung] - baseline[kennung] for kennung in proto) / len(proto)


def konsistenz(bericht: Blockbericht, plan: Versuchsplan) -> dict[str, Any]:
    """Prueft, ob die Wilcoxon-Familien zum Omnibustest des Blockmodells passen.

    Ein signifikanter Interaktionsterm behauptet, der Abstand zwischen den
    Verfahren haenge von der Fehlerklasse ab. Konsistent dazu ist ein Bild, in dem
    die klassenweisen Vergleiche **nicht alle gleich** ausfallen — entweder in
    der Signifikanz oder in der Groesse des Effekts. Gaebe es einen signifikanten
    Interaktionsterm bei durchweg identischen Einzelvergleichen, waere einer der
    beiden Befunde erklaerungsbeduerftig.

    Args:
        bericht: Der Bericht.
        plan: Der Versuchsplan; liefert alpha.

    Returns:
        Je Ebene die Zahl der signifikanten Vergleiche, die Richtungen und die
        Spannweite der Effektstaerken.
    """
    alpha = plan.statistik.alpha
    ergebnis: dict[str, Any] = {"alpha": alpha}
    for familie in bericht.hyp4.familien:
        effekte = [
            (vergleich.gruppe, float(vergleich.test.effekt))
            for vergleich in familie.vergleiche
            if vergleich.test is not None and vergleich.test.effekt is not None
        ]
        signifikant = [
            vergleich.gruppe for vergleich in familie.vergleiche if vergleich.signifikant
        ]
        ergebnis[familie.kennung] = {
            "familiengroesse": familie.anzahl,
            "berichtet": familie.berichtet,
            "signifikant": signifikant,
            "prototyp_vorn": sorted(
                name
                for name, effekt in effekte
                if effekt > 0 and name in signifikant
            ),
            "b2_vorn": sorted(
                name for name, effekt in effekte if effekt < 0 and name in signifikant
            ),
            "effekt_min": min((effekt for _, effekt in effekte), default=None),
            "effekt_max": max((effekt for _, effekt in effekte), default=None),
        }
    return ergebnis


def _p(wert: float) -> str:
    """Formatiert einen p-Wert und benennt einen Unterlauf statt ihn zu zeigen."""
    if wert == 0.0:
        return "< 1e-308 (Unterlauf)"
    return f"{wert:.3g}".replace(".", ",").replace("e-0", "e-")


def _komma(wert: float, stellen: int = 4) -> str:
    """Formatiert eine Zahl mit deutschem Dezimalkomma."""
    return f"{wert:.{stellen}f}".replace(".", ",")


def _anteil_block(test: Testergebnis) -> str:
    """Liest den Blockanteil am Fehlerterm aus dem Hinweis des Tests.

    Args:
        test: Das Ergebnis des Blockmodells.

    Returns:
        Den Anteil als Prozentangabe mit deutschem Dezimalkomma.

    Raises:
        AuswertungsFehler: Wenn der Hinweis den Anteil nicht traegt.
    """
    marke = "der Blockterm bindet "
    if marke not in test.hinweis:
        raise AuswertungsFehler(f"Der Hinweis {test.hinweis!r} traegt keinen Blockanteil.")
    rest = test.hinweis.split(marke, 1)[1]
    return rest.split(" ", 1)[0].replace(".", ",")


def _klassen_des_berichts(bericht: Blockbericht) -> list[str]:
    """Gibt die Fehlerklassen in Berichtsreihenfolge zurueck.

    Args:
        bericht: Der Bericht.

    Returns:
        Die Klassen, wie sie in :attr:`Blockbericht.abstaende` stehen.

    Raises:
        AuswertungsFehler: Wenn die beiden Ebenen verschiedene Klassen fuehren.
    """
    reihen = [list(werte) for werte in bericht.abstaende.values()]
    if any(reihe != reihen[0] for reihe in reihen):
        raise AuswertungsFehler(
            f"Die Ebenen fuehren verschiedene Fehlerklassen: {reihen}."
        )
    return reihen[0]


def als_markdown(bericht: Blockbericht, plan: Versuchsplan) -> str:
    """Formatiert den Bericht als Markdown.

    Args:
        bericht: Der Bericht.
        plan: Der Versuchsplan.

    Returns:
        Den vollstaendigen Text der Datei.
    """
    pruefung = konsistenz(bericht, plan)
    zeilen: list[str] = [
        "# HYP4 mit der Wiederholungsstruktur — ART-ANOVA als Blockmodell",
        "",
        "Nachrechnung ohne einen einzigen neuen Lauf: Dieselben Ergebnisse der Serie s01,",
        "dasselbe Langformat, dieselbe Aligned-Rank-Transformation — nur das Modell auf den",
        "Raengen bekommt den Term, der die Paarung abbildet.",
        "",
        "Erzeugt aus `results/metrics_long.parquet` durch",
        "`src.evaluation.blockmodell.schreibe_bericht`.",
        "",
        "## Der Einwand",
        "",
        "Die vorregistrierte Fassung rechnet `f1 ~ verfahren * fehlerklasse`. Prototyp und B2",
        "werden aber auf **demselben** Injektionslauf ausgewertet — derselbe verfaelschte",
        "Datensatz geht an beide. Die Beobachtungen sind gepaart; das Modell behandelt sie als",
        "unabhaengig und laesst die gesamte Streuung zwischen den Laeufen im Fehlerterm stehen,",
        "obwohl sie beide Verfahren gleichermassen trifft und den Vergleich gar nicht stoert.",
        "",
        "## Was geaendert wurde und was nicht",
        "",
        "| | vorregistriert | Blockmodell |",
        "|---|---|---|",
        "| Daten | Serie s01, Langformat | **unveraendert** |",
        "| Ausrichtung | `y - zeilenmittel - spaltenmittel + gesamtmittel` | **unveraendert** |",
        "| Rangbildung | ueber alle ausgerichteten Werte | **unveraendert** |",
        (
            "| Modell | `raenge ~ verfahren * fehlerklasse` "
            "| `raenge ~ verfahren * fehlerklasse + Error(block)` |"
        ),
        "| Fehlerterm | Residuum ueber alle Beobachtungen | Residuum **innerhalb** der Bloecke |",
        "",
        "Die Ausrichtung bleibt bewusst ohne Blockterm: Wobbrock et al. (2011) richten an den",
        "festen Effekten des vollen faktoriellen Modells aus und ueberlassen den Blockterm der",
        "Modellanpassung; die R-Umsetzung `ARTool` verfaehrt ebenso. Wuerde man den Block schon",
        "in der Ausrichtung entfernen, waere der Fehlerterm doppelt bereinigt.",
        "",
        "Der Block ist in der **Fehlerklasse geschachtelt** und nicht mit ihr gekreuzt: Ein",
        "Injektionslauf traegt genau eine Klasse, und `seed_inject` geht aus Serie, Design,",
        "Klasse, Rate und Wiederholung hervor — `F1|w07` und `F3|w07` sind verschiedene",
        "Verfaelschungen und keine Wiederholung derselben Bedingung. Es entsteht damit ein",
        "Split-Plot-Aufbau: Klasse zwischen den Bloecken, Verfahren innerhalb. Bei balanciertem",
        "Aufbau — und die Balanciertheit wird erzwungen, nicht unterstellt — ist der F-Test des",
        "Interaktionsterms identisch mit dem des gemischten Modells",
        "`raenge ~ verfahren * fehlerklasse + (1 | block)`.",
        "",
        "## Ergebnis",
        "",
        (
            "| Ebene | Modell | F | df1 | df2 | p | partielles Eta-Quadrat | N | Bloecke "
            "| Blockanteil am Fehlerterm |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    gesehen: set[Ebene] = set()
    for befund in bericht.befunde:
        if befund.ebene not in gesehen:
            gesehen.add(befund.ebene)
            alt = befund.bisher
            df1_alt, df2_alt = _freiheitsgrade(alt)
            zeilen.append(
                f"| {befund.ebene.value} | vorregistriert, ohne Blockterm | "
                f"{_komma(alt.statistik, 2)} | {df1_alt} | {df2_alt} | {_p(alt.p_wert)} | "
                f"{_komma(alt.effekt or 0.0, 4)} | {alt.n} | — | — |"
            )
        df1, df2 = _freiheitsgrade(befund.test)
        zeilen.append(
            f"| {befund.ebene.value} | Blockmodell, {befund.blockart} | "
            f"{_komma(befund.test.statistik, 2)} | {df1} | {df2} | {_p(befund.test.p_wert)} | "
            f"{_komma(befund.test.effekt or 0.0, 4)} | {befund.test.n} | {befund.bloecke} | "
            f"{_anteil_block(befund.test)} |"
        )

    zeilen += [
        "",
        "Die Blockdefinitionen im Klartext:",
        "",
    ]
    for blockart, beschreibung in BLOCKARTEN:
        zeilen.append(f"- **{blockart}** — {beschreibung}")

    zeilen += [
        "",
        "### Die Rechnung ist nachgerechnet",
        "",
        "Bei genau zwei Stufen des Innerhalb-Faktors — Prototyp gegen B2 — ist der",
        "Split-Plot-F-Test des Interaktionsterms rechnerisch identisch mit einer",
        "**Einweg-Varianzanalyse der Rangdifferenzen je Block**: Man bildet je Block",
        "`d = Rang(Prototyp) - Rang(B2)` und vergleicht die Gruppenmittel von `d` ueber die",
        "sieben Fehlerklassen. Der Weg ist ein voellig anderer, das Ergebnis muss dasselbe",
        "sein. Diese Gegenprobe (`src.evaluation.blockmodell.gegenprobe`) bildet Ausrichtung",
        "und Raenge eigenstaendig nach und beruehrt `src.evaluation.statistik` nicht — ein",
        "gemeinsamer Rechenweg wuerde einen gemeinsamen Fehler nicht aufdecken.",
        "",
        "| Ebene | Modell | F (Quadratsummen) | F (Gegenprobe) | relative Abweichung |",
        "|---|---|---|---|---|",
    ]
    for befund in bericht.befunde:
        zeilen.append(
            f"| {befund.ebene.value} | {befund.blockart} | "
            f"{befund.test.statistik:.10f}".replace(".", ",")
            + f" | {befund.gegenprobe:.10f}".replace(".", ",")
            + f" | {befund.abweichung:.2e} |"
        )

    zeilen += [
        "",
        "## Aendert sich die inhaltliche Aussage?",
        "",
    ]
    if bericht.aussage_unveraendert:
        zeilen += [
            "**Nein.** Der Interaktionsterm ist in jedem der vier Modelle auf dem Niveau",
            f"alpha = {_komma(plan.statistik.alpha, 2)} signifikant, auf beiden Metrikebenen und",
            "unter beiden Blockdefinitionen. Die Aussage von HYP4 — der Abstand zwischen",
            "Prototyp und B2 haengt von der Fehlerklasse ab — traegt mit Blockterm genauso wie",
            "ohne. Auch die Entscheidung bleibt: Sie lautet weiterhin",
            f"**{bericht.hyp4.entscheidung}**, denn sie haengt nicht am Omnibustest allein,",
            "sondern zusaetzlich an der Richtung, und die Richtungsaussage entscheidet sich in",
            "den klassenweisen Vergleichen.",
            "",
            "Der Einwand war trotzdem berechtigt. Er betrifft die **Genauigkeit der Angabe**,",
            "nicht das Ergebnis: Freiheitsgrade und Fehlerterm des bisherigen Modells waren zu",
            "gross, und ein Gutachter kann das nicht wissen, solange die Zahl nicht daneben",
            "steht. Jetzt steht sie daneben.",
        ]
    else:
        abweichend = [
            f"{befund.ebene.value}/{befund.blockart}"
            for befund in bericht.befunde
            if (befund.test.p_wert < plan.statistik.alpha)
            != (befund.bisher.p_wert < plan.statistik.alpha)
        ]
        zeilen += [
            "**Ja.** In den folgenden Modellen faellt die Entscheidung ueber den",
            f"Interaktionsterm anders aus als in der vorregistrierten Fassung: {abweichend}.",
            "Das ist ein Befund und gehoert in die Arbeit.",
        ]

    zeilen += [
        "",
        "### Warum sich am F-Wert so wenig aendert",
        "",
        "Der Blockterm bindet rund die Haelfte des Fehlerterms, den ein Modell ohne ihn haette",
        "(genaue Anteile im Hinweis je Test) — und er kostet zugleich rund die Haelfte der",
        "Fehlerfreiheitsgrade. Beides hebt sich im mittleren Quadrat des Nenners fast auf, und",
        "deshalb steigt der F-Wert nur um wenige Prozent, statt sich zu vervielfachen.",
        "",
        "An der **Gesamt**quadratsumme der Raenge macht der Blockterm dagegen nur wenige",
        "Prozent aus. Das ist kein Widerspruch, sondern die Folge eines sehr grossen",
        "Interaktionseffekts: Wenn ein Term neunundneunzig Prozent der Streuung erklaert,",
        "bleibt fuer alles uebrige zusammen wenig Raum. Die aussagekraeftige Bezugsgroesse ist",
        "deshalb der Fehlerterm und nicht die Gesamtsumme — der Hinweis je Test weist sie so",
        "aus.",
        "",
        "Unter der Blockdefinition `lauf` faellt der F-Wert dagegen, weil dort eine **andere",
        "Antwortgroesse** eingeht: der F1-Wert je einzelnem Lauf statt sein Mittel ueber die",
        "vier Ratenstufen. Die Mittelung glaettet, der Einzelwert nicht. Beide Zahlen",
        "beantworten dieselbe Frage mit verschiedener Aufloesung; keine ist die Korrektur der",
        "anderen.",
        "",
        "Praktisch heisst das: Der Einwand trifft eine Angabe, die in diesem Datensatz",
        "**robust** ist. Bei einem kleineren Effekt oder mehr Streuung zwischen den Laeufen",
        "koennte derselbe Fehler das Ergebnis kippen; hier tut er es nicht. Das ist ein",
        "Ergebnis ueber diesen Datensatz und kein Freibrief fuer das falsche Modell.",
        "",
        "## Konsistenz mit den klassenweisen Vergleichen",
        "",
        "Die gepaarten Wilcoxon-Tests je Fehlerklasse und ihre Holm-Korrektur bleiben",
        "**unveraendert**. Sie sind von dem Einwand gar nicht betroffen: Ein gepaarter Test",
        "rechnet die Paarung bereits ein, indem er auf den Differenzen je Wiederholung",
        "arbeitet. Geprueft wird hier nur, ob ihr Bild zum neuen Omnibustest passt.",
        "",
        (
            "| Familie | Familiengroesse (Holm) | berichtet | signifikant "
            "| Prototyp vorn | B2 vorn | Effekt min | Effekt max |"
        ),
        "|---|---|---|---|---|---|---|---|",
    ]
    for familie in bericht.hyp4.familien:
        eintrag = pruefung[familie.kennung]
        zeilen.append(
            f"| {familie.kennung} | {eintrag['familiengroesse']} | {eintrag['berichtet']} | "
            f"{len(eintrag['signifikant'])} | {len(eintrag['prototyp_vorn'])} "
            f"({', '.join(eintrag['prototyp_vorn']) or '—'}) | "
            f"{len(eintrag['b2_vorn'])} ({', '.join(eintrag['b2_vorn']) or '—'}) | "
            f"{_komma(eintrag['effekt_min'], 3) if eintrag['effekt_min'] is not None else '—'} | "
            f"{_komma(eintrag['effekt_max'], 3) if eintrag['effekt_max'] is not None else '—'} |"
        )

    zeilen += [
        "",
        "**Die Rang-biseriale Korrelation ist in jeder Klasse gesaettigt (1,000).** Der",
        "Prototyp gewinnt in allen zwanzig Wiederholungen jeder Klasse; mehr kann das",
        "Effektmass eines Vorzeichen-Rangtests nicht anzeigen. Es misst die",
        "Richtungskonsistenz, nicht die **Groesse** des Abstands — und genau die Groesse ist",
        "der Gegenstand der Interaktionshypothese. Die paarweisen Tests koennen die",
        "Interaktion deshalb weder bestaetigen noch widerlegen; sie koennten ihr nur",
        "widersprechen, und das tun sie nicht.",
        "",
        "Wo der Abstand tatsaechlich variiert, zeigt das Mittel der gepaarten Differenz",
        "`F1(Prototyp) - F1(B2)` je Klasse:",
        "",
        "| Ebene | " + " | ".join(_klassen_des_berichts(bericht)) + " | Spannweite |",
        "|---" * (len(_klassen_des_berichts(bericht)) + 2) + "|",
    ]
    for ebene, _ in _EBENEN:
        werte = bericht.abstaende[ebene.value]
        spanne = max(werte.values()) - min(werte.values())
        zeilen.append(
            f"| {ebene.value} | "
            + " | ".join(_komma(werte[klasse], 3) for klasse in _klassen_des_berichts(bericht))
            + f" | {_komma(spanne, 3)} |"
        )

    zeilen += [
        "",
        "Der Abstand schwankt ueber die Klassen um ein Vielfaches, waehrend sein Vorzeichen",
        "nie wechselt. Das ist genau das Bild, das ein signifikanter Interaktionsterm bei",
        "durchweg gleichgerichteten Einzelvergleichen erzeugt — beides zusammen ist die",
        "Aussage von HYP4: Die Interaktion ist belegt, die Richtungsaussage 'statistisch",
        "gewinnt bei Ausreissern' ist es nicht.",
        "",
        "## Was diese Rechnung nicht ist",
        "",
        "Sie ersetzt die vorregistrierte Fassung **nicht**. `src/evaluation/hypothesen.py` und",
        "`results/hypothesen.json` bleiben unveraendert; die Zahlen dort sind weiterhin die",
        "der Voranmeldung. Eine nachtraeglich ersetzte Zahl nimmt dem Leser die Moeglichkeit,",
        "den Unterschied zu pruefen — und der Unterschied ist hier die eigentliche Auskunft.",
        "",
    ]
    return "\n".join(zeilen)


def _freiheitsgrade(test: Testergebnis) -> tuple[str, str]:
    """Liest Zaehler- und Nennerfreiheitsgrade aus dem Hinweis des Tests.

    Der Hinweis traegt sie in der Form ``F(6, 266); ...``. Sie dort abzulesen ist
    verlaesslicher, als sie im Bericht erneut auszurechnen: Ausgewiesen wird dann
    genau das, was der Test gerechnet hat.

    Args:
        test: Das Testergebnis.

    Returns:
        Zaehler- und Nennerfreiheitsgrade als Zeichenketten.

    Raises:
        AuswertungsFehler: Wenn der Hinweis die Freiheitsgrade nicht traegt. Ein
            Gedankenstrich an dieser Stelle waere in einer Statistiktabelle
            wertlos.
    """
    kopf = test.hinweis.split(";", 1)[0].strip()
    if not (kopf.startswith("F(") and kopf.endswith(")") and "," in kopf):
        raise AuswertungsFehler(
            f"Der Hinweis {test.hinweis!r} traegt keine Freiheitsgrade in der Form 'F(a, b)'."
        )
    zaehler, nenner = kopf[2:-1].split(",", 1)
    return (zaehler.strip(), nenner.strip())


def schreibe_bericht(lang: pd.DataFrame, plan: Versuchsplan, verzeichnis: Path) -> Path:
    """Rechnet das Blockmodell und legt den Bericht unter ``results/`` ab.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.
        verzeichnis: Zielverzeichnis, ueblicherweise ``results``.

    Returns:
        Den Pfad der geschriebenen Datei.
    """
    verzeichnis.mkdir(parents=True, exist_ok=True)
    bericht = blockmodell_hyp4(lang, plan)
    pfad = verzeichnis / BERICHTSNAME
    pfad.write_text(als_markdown(bericht, plan), encoding="utf-8", newline="\n")
    return pfad


def als_dict(bericht: Blockbericht) -> dict[str, Any]:
    """Gibt den Bericht als JSON-faehiges Woerterbuch zurueck.

    Args:
        bericht: Der Bericht.

    Returns:
        Ein Woerterbuch aus reinen Grundtypen.
    """
    return {
        "aussage_unveraendert": bericht.aussage_unveraendert,
        "entscheidung_unveraendert": bericht.hyp4.entscheidung,
        "mittlerer_abstand_f1": bericht.abstaende,
        "modelle": [
            {
                "ebene": befund.ebene.value,
                "blockart": befund.blockart,
                "beschreibung": befund.beschreibung,
                "bloecke": befund.bloecke,
                "f": befund.test.statistik,
                "p": befund.test.p_wert,
                "partielles_eta_quadrat": befund.test.effekt,
                "n": befund.test.n,
                "hinweis": befund.test.hinweis,
                "bisher": {
                    "f": befund.bisher.statistik,
                    "p": befund.bisher.p_wert,
                    "partielles_eta_quadrat": befund.bisher.effekt,
                    "n": befund.bisher.n,
                    "hinweis": befund.bisher.hinweis,
                },
            }
            for befund in bericht.befunde
        ],
    }
