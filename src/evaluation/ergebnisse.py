"""Zugriff auf ``results/metrics_long.parquet`` — eine Quelle fuer alles Weitere.

Hypothesen, Tabellen und Abbildungen lesen **ausschliesslich** ueber dieses
Modul. Der Grund ist nicht Bequemlichkeit, sondern Nachvollziehbarkeit: Jede
Zahl, die in der Arbeit steht, muss auf eine Zeile des Langformats zurueckfuehren
— und das Langformat wiederum auf einen Lauf, dessen ``run_id`` alle Faktorstufen
traegt. Wuerde eine Abbildung ihre Werte aus ``metrics.json`` ziehen und eine
Tabelle aus dem Langformat, saehen zwei Zahlen desselben Sachverhalts frueher
oder spaeter verschieden aus, und niemand koennte sagen, welche stimmt.

Die Spalte ``teilversuch`` entsteht hier
-----------------------------------------

Das Langformat kennt nur Faktorstufen, keine Bloecke — der Injektor weiss nichts
von "Teilversuch T3". Die Zuordnung entsteht ueber das **Varianzdesign**: Jeder
Block des Versuchsplans hat eine eigene Designkennung (``A`` fuer den
Hauptversuch, ``B`` fuer T1, ``V`` fuer T6 und so fort), und
:func:`lade_ergebnisse` bildet sie auf die Blockkennung ab. Deshalb prueft
:func:`~src.evaluation.experimentplan.lade_plan` die Eindeutigkeit der
Designkennungen: Ohne sie waere diese Zuordnung mehrdeutig.

Aggregationsebene der Hauptauswertung
--------------------------------------

Vorab festgelegt und in :func:`mittel_je_wiederholung` umgesetzt: **ueber die
Fehlerraten aggregieren, je Klasse testen**. Eine Wiederholung liefert damit je
Klasse genau einen Wert, und die zwanzig Wiederholungen bilden die gepaarte
Stichprobe. Wer zusaetzlich je Rate testet, vervierfacht die Zahl der Vergleiche;
das ist zulaessig, muss dann aber im Text stehen (siehe
:func:`~src.evaluation.statistik.holm`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import pandas as pd

from src.evaluation.langformat import (
    GRUPPE_FEHLERKLASSE,
    GRUPPE_GESAMT,
    GRUPPE_REGEL,
    GRUPPE_VARIANTE,
    KREUZ_TRENNER,
    METRICS_LONG_SPALTEN,
)
from src.evaluation.modell import AuswertungsFehler, Ebene

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence
    from pathlib import Path

    from src.evaluation.experimentplan import Versuchsplan

__all__ = [
    "GRUPPE_FEHLERKLASSE",
    "GRUPPE_GESAMT",
    "GRUPPE_REGEL",
    "GRUPPE_VARIANTE",
    "KREUZ_TRENNER",
    "SPALTE_TEILVERSUCH",
    "auswahl",
    "kreuztabelle_lang",
    "lade_ergebnisse",
    "mittel_je_wiederholung",
    "summe_je_gruppe",
]

#: Name der abgeleiteten Spalte mit der Blockkennung.
SPALTE_TEILVERSUCH: Final[str] = "teilversuch"


def lade_ergebnisse(pfad: Path, plan: Versuchsplan) -> pd.DataFrame:
    """Liest das Langformat und ergaenzt die Blockkennung.

    Args:
        pfad: Pfad von ``results/metrics_long.parquet``.
        plan: Der Versuchsplan; liefert Serie und Designzuordnung.

    Returns:
        Das Langformat der Serie des Plans, um die Spalte
        :data:`SPALTE_TEILVERSUCH` erweitert.

    Raises:
        AuswertungsFehler: Wenn die Datei fehlt, Spalten fehlen, die Serie des
            Plans nicht enthalten ist oder ein Design keinem Block zuzuordnen
            ist. Der letzte Fall bedeutet, dass Ergebnisse eines aelteren Plans
            in der Datei stehen; sie stillschweigend mitzuzaehlen wuerde die
            Auswertung auf einen anderen Versuchsplan beziehen, als sie behauptet.
    """
    if not pfad.is_file():
        raise AuswertungsFehler(
            f"Das Langformat fehlt: {pfad}. Es entsteht mit "
            "'python scripts/run_experiment.py'."
        )
    lang = pd.read_parquet(pfad)
    fehlend = [spalte for spalte in METRICS_LONG_SPALTEN if spalte not in lang.columns]
    if fehlend:
        raise AuswertungsFehler(f"Dem Langformat {pfad} fehlen die Spalten {fehlend}.")

    eigene = lang[lang["serie"] == plan.serie].copy()
    if eigene.empty:
        vorhanden = sorted(lang["serie"].dropna().unique())
        raise AuswertungsFehler(
            f"Das Langformat {pfad} enthaelt keine Zeilen der Serie {plan.serie!r}. "
            f"Vorhanden sind: {vorhanden}."
        )

    zuordnung = {block.design: block.kennung for block in plan.bloecke}
    unbekannt = sorted(set(eigene["design"].dropna().unique()) - set(zuordnung))
    if unbekannt:
        raise AuswertungsFehler(
            f"Das Langformat enthaelt die Designkennungen {unbekannt}, die im Versuchsplan "
            "nicht vorkommen. Sie stammen aus einer aelteren Fassung des Plans. Entweder "
            "den Plan angleichen oder die Laufverzeichnisse der alten Serie entfernen — "
            "stillschweigend mitzuzaehlen waere eine Auswertung ueber zwei verschiedene "
            "Versuchsplaene."
        )
    eigene[SPALTE_TEILVERSUCH] = eigene["design"].map(zuordnung).astype("string")
    return eigene


def auswahl(  # noqa: PLR0913 - jede Angabe waehlt eine eigene Dimension
    lang: pd.DataFrame,
    *,
    metrik: str | Sequence[str] | None = None,
    verfahren: str | Sequence[str] | None = None,
    ebene: Ebene | str | None = None,
    mitgezogen: bool | None = False,
    gruppe_art: str | None = None,
    gruppe: str | Sequence[str] | None = None,
    klasse: str | Sequence[str] | None = None,
    fehlerrate: float | Sequence[float] | None = None,
    teilversuch: str | Sequence[str] | None = None,
) -> pd.DataFrame:
    """Filtert das Langformat.

    ``mitgezogen`` steht bewusst auf ``False`` statt auf ``None``: Die
    Hauptauswertung der Arbeit rechnet ohne die mitgezogenen Zellen (``spec/03``,
    Abschnitt 5a.2), und wer die Sensitivitaetsrechnung will, muss sie
    ausdruecklich anfordern. Ein Vorgabewert ``None`` lieferte beide
    Schalterstellungen zugleich und damit jede Kennzahl doppelt — ein Mittelwert
    daraus waere lautlos falsch.

    Args:
        lang: Das Langformat aus :func:`lade_ergebnisse`.
        metrik: Kennzahl oder Kennzahlen.
        verfahren: Verfahren oder Verfahren.
        ebene: Auswertungsebene.
        mitgezogen: Schalterstellung; ``None`` waehlt beide.
        gruppe_art: Bezugsobjekt der Kennzahl.
        gruppe: Kennung des Bezugsobjekts.
        klasse: Fehlerklasse oder Fehlerklassen.
        fehlerrate: Fehlerrate oder Fehlerraten.
        teilversuch: Blockkennung oder Blockkennungen.

    Returns:
        Die gefilterten Zeilen als Kopie.
    """
    maske = pd.Series(data=True, index=lang.index)
    for spalte, wert in (
        ("metrik", metrik),
        ("verfahren", verfahren),
        ("gruppe", gruppe),
        ("klasse", klasse),
        ("fehlerrate", fehlerrate),
        (SPALTE_TEILVERSUCH, teilversuch),
    ):
        if wert is None:
            continue
        werte = [wert] if isinstance(wert, (str, float, int)) else list(wert)
        maske &= lang[spalte].isin(werte)
    if ebene is not None:
        maske &= lang["ebene"] == (ebene.value if isinstance(ebene, Ebene) else ebene)
    if gruppe_art is not None:
        maske &= lang["gruppe_art"] == gruppe_art
    if mitgezogen is not None:
        maske &= lang["mitgezogen_als_fehler"] == mitgezogen
    return lang[maske].copy()


def mittel_je_wiederholung(
    lang: pd.DataFrame, *, ueber: str = "fehlerrate"
) -> pd.Series:
    """Mittelt eine bereits gefilterte Auswahl je Wiederholung.

    Das ist die vorab festgelegte Aggregationsebene: **ueber die Fehlerraten
    aggregieren, je Klasse testen**. Eine Wiederholung liefert danach genau einen
    Wert, und die Wiederholungen bilden die gepaarte Stichprobe.

    Args:
        lang: Bereits auf eine Kennzahl, ein Verfahren und eine Klasse gefilterte
            Auswahl.
        ueber: Name der Spalte, ueber die gemittelt wird — nur fuer die
            Fehlermeldung; gruppiert wird immer nach ``wiederholung``.

    Returns:
        Eine nach Wiederholung sortierte Reihe.

    Raises:
        AuswertungsFehler: Wenn die Auswahl leer ist oder fehlende Werte
            enthaelt. Ein fehlender Wert an dieser Stelle waere eine nicht
            gerechnete Zelle; ihn wegzumitteln verkleinerte die Stichprobe
            stillschweigend.
    """
    if lang.empty:
        raise AuswertungsFehler(
            f"Die Auswahl ist leer; ueber {ueber} laesst sich dann nichts mitteln."
        )
    if lang["wert"].isna().any():
        betroffen = sorted(lang.loc[lang["wert"].isna(), "run_id"].unique())
        raise AuswertungsFehler(
            f"Die Auswahl enthaelt {len(betroffen)} Laeufe ohne Wert, darunter "
            f"{betroffen[:3]}. Sie stillschweigend wegzumitteln waere eine verdeckte "
            "Stichprobenreduktion."
        )
    gemittelt = lang.groupby("wiederholung", observed=True)["wert"].mean()
    return gemittelt.astype(float).sort_index()


def summe_je_gruppe(lang: pd.DataFrame, *, spalte: str = "gruppe") -> pd.DataFrame:
    """Summiert Treffer und Fallzahl je Gruppe ueber alle Laeufe.

    Wird fuer den Ausweichweg des Bootstrap gebraucht: Entartet er, weil alle
    Wiederholungen denselben Wert liefern, braucht das Clopper-Pearson-Intervall
    die zugrunde liegenden Anteilszahlen.

    Args:
        lang: Auswahl mit den Kennzahlen ``tp`` und ``recall``; die Spalte ``n``
            traegt die Fallzahl der Gruppe.
        spalte: Spalte, nach der gruppiert wird.

    Returns:
        Je Gruppe die Spalten ``tp`` und ``n``, jeweils ueber die Laeufe summiert.

    Raises:
        AuswertungsFehler: Wenn die Kennzahl ``tp`` fehlt.
    """
    treffer = lang[lang["metrik"] == "tp"]
    if treffer.empty:
        raise AuswertungsFehler(
            "Fuer die Anteilszahlen wird die Kennzahl 'tp' gebraucht; sie fehlt in der "
            "Auswahl."
        )
    verdichtet = treffer.groupby(spalte, observed=True).agg(
        tp=("wert", "sum"), n=("n", "sum")
    )
    verdichtet["tp"] = verdichtet["tp"].round().astype("int64")
    verdichtet["n"] = verdichtet["n"].fillna(0).astype("int64")
    return verdichtet.sort_index()


def kreuztabelle_lang(lang: pd.DataFrame) -> pd.DataFrame:
    """Zerlegt die Kreuztabellenzeilen in Regel und Fehlerklasse.

    Die Kreuztabelle liegt im Langformat als **ein** zusammengesetzter
    Gruppenschluessel ``<regel_id>|<fehlerklasse>`` vor; das Format traegt nur
    eine Gruppenspalte. Hier wird er wieder in zwei Spalten zerlegt.

    Args:
        lang: Das vollstaendige Langformat.

    Returns:
        Die Spalten ``run_id``, ``verfahren``, :data:`SPALTE_TEILVERSUCH`,
        ``klasse``, ``variante``, ``regel_id``, ``fehlerklasse`` und ``treffer``.

        Die Blockkennung bleibt erhalten, damit die Aufrufer dieselbe
        Blockauswahl treffen koennen wie ``t3_regeldiagnose`` — sonst zaehlte die
        Abbildung ueber andere Laeufe als die Tabelle, und zwei Darstellungen
        desselben Sachverhalts zeigten verschiedene Zahlen.

        Die Spalte ``variante`` traegt im Variantenmodus die Kennung der einzigen
        injizierten Variante. Damit sagt die Tabelle dort nicht nur, **welche**
        Regel getroffen hat, sondern auch **worauf** — und das ist die Grundlage
        der Trefferkategorien in ``t4_varianten``: Eine Variante, die von einer
        Regel gefangen wird, die nicht gegen sie entworfen wurde, ist das
        Gegenteil von Zirkularitaet. Die Regel-ID wird dabei **gemessen** und
        nicht neu vergeben.
    """
    kreuz = auswahl(lang, metrik="treffer", gruppe_art=GRUPPE_REGEL)
    geteilt = kreuz["gruppe"].str.split(KREUZ_TRENNER, n=1, expand=True)
    kreuz["regel_id"] = geteilt[0]
    kreuz["fehlerklasse"] = geteilt[1]
    kreuz["treffer"] = kreuz["wert"].astype(float)
    return kreuz[
        [
            "run_id",
            "verfahren",
            SPALTE_TEILVERSUCH,
            "klasse",
            "variante",
            "regel_id",
            "fehlerklasse",
            "treffer",
        ]
    ]


def als_json(wert: Any) -> Any:  # noqa: ANN401, PLR0911 - eine Fallunterscheidung je Typ
    """Wandelt NumPy- und pandas-Skalare in JSON-faehige Grundtypen.

    ``json.dumps`` scheitert an ``numpy.float64`` und an ``pandas.NA``. Die
    Alternative waere ein eigener Encoder; der versteckte die Umwandlung
    allerdings an einer Stelle, an der niemand nachsieht. Hier ist sie sichtbar.

    Args:
        wert: Ein beliebiger Wert.

    Returns:
        Den Wert als ``float``, ``int``, ``bool``, ``str``, ``None``, Liste oder
        Woerterbuch.
    """
    if wert is None or wert is pd.NA:
        return None
    if isinstance(wert, dict):
        return {schluessel: als_json(inhalt) for schluessel, inhalt in wert.items()}
    if isinstance(wert, (list, tuple)):
        return [als_json(inhalt) for inhalt in wert]
    if isinstance(wert, bool):
        return bool(wert)
    if isinstance(wert, (int,)):
        return int(wert)
    if isinstance(wert, float):
        return None if pd.isna(wert) else float(wert)
    if hasattr(wert, "item"):
        return als_json(wert.item())
    return wert
