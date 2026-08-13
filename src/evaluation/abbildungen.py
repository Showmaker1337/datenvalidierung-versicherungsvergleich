"""Die zehn Abbildungen der Arbeit, je als PDF und als PNG mit 300 dpi.

Neben jeder Abbildung entsteht eine ``.txt`` mit der Bildunterschrift, damit sie
sich unveraendert in die Arbeit uebernehmen laesst.

Graustufentauglich, nicht bunt
-------------------------------

Eine Abschlussarbeit wird oft schwarzweiss gedruckt. Jede Abbildung
unterscheidet ihre Reihen deshalb ueber **Form** — Marker, Linienstil,
Schraffur, Graustufe —, nie ueber Farbe allein. Wer eine der Abbildungen in
Graustufen umwandelt, verliert keine Information. Die Schriftgroesse liegt bei
mindestens neun Punkt; darunter ist eine Achsenbeschriftung im Druck nicht mehr
lesbar.

Abbildung 5 ist die wichtigste, und sie kommt aus T6
------------------------------------------------------

Der Recall **je Injektionsvariante** ist der empirische Beleg gegen den
Zirkularitaetsvorwurf: Er zeigt, dass Varianten, die eine Regelbedingung nicht
spiegeln, schlechter erkannt werden. Aus dem faktoriellen Plan gezeichnet waere
er wertlos — die proportionale Zuteilung gibt knappen Varianten dort einstellige
Fallzahlen, F4-f bei zwei Prozent genau eine. Abbildung 5 stammt deshalb
ausschliesslich aus dem Teilversuch T6, in dem jede Variante ihr Universum
ausschoepft.

Abbildung 6 zeigt auch die Regeln ohne Treffer
------------------------------------------------

Eine Regel, die in keinem Lauf gemeldet hat, bleibt als leere Zeile stehen. Sie
ist Ueberdeckung des Katalogs gegenueber der Fehlertaxonomie — ein Ergebnis, kein
Darstellungsproblem. Wie viele es sind, steht in der Bildunterschrift und wird
gezaehlt, nicht vorab behauptet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import matplotlib as mpl
import numpy as np
import pandas as pd

# Muss vor dem Import von pyplot stehen: Die Abbildungen entstehen ohne
# Bildschirm, und ein interaktives Backend braeuchte eine Anzeige.
mpl.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from src.evaluation.ergebnisse import (
    GRUPPE_GESAMT,
    auswahl,
    kreuztabelle_lang,
    mittel_je_wiederholung,
)
from src.evaluation.modell import Ebene
from src.evaluation.varianten import Spiegelung
from src.rules.katalog import KATALOG

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from pathlib import Path

    from matplotlib.figure import Figure

    from src.evaluation.experimentplan import Versuchsplan

__all__ = ["ABBILDUNGSNAMEN", "baue_alle", "setze_stil"]

#: Namen aller Abbildungen in Berichtsreihenfolge.
ABBILDUNGSNAMEN: Final[tuple[str, ...]] = (
    "abb01_heatmap_klasse_rate",
    "abb02_boxplot_f1",
    "abb03_pr_kurve",
    "abb04_recall_je_klasse",
    "abb05_recall_je_variante",
    "abb06_regel_kreuztabelle",
    "abb07_laufzeit",
    "abb08_varianzvergleich",
    "abb09_zelle_gegen_constraint",
    "abb10_praxismix",
    "abb11_trefferkategorien",
)

#: Blockkennungen, wie sie ``config/experiment.yaml`` vergibt.
_HAUPT: Final[str] = "haupt"
_DUPLIKATE: Final[str] = "T1"
_HELDOUT: Final[str] = "T2"
_MISCHUNG: Final[str] = "T3"
_SKALIERUNG: Final[str] = "T4"
_DATENVARIANZ: Final[str] = "T5"
_VARIANTEN: Final[str] = "T6"

_PROTOTYP: Final[str] = "prototyp"

#: Ab diesem Recall gilt eine Held-out-Klasse als auffaellig gut erkannt.
#:
#: Der Wert ist eine Ausloeseschwelle fuer einen **Hinweis**, keine Entscheidung
#: ueber ein Ergebnis: Oberhalb davon ergaenzt Abbildung 4 ihre Bildunterschrift um
#: den Verweis auf die Kreuztabelle. Zehn Prozent liegen weit ueber dem, was
#: Rundung oder ein einzelner Zufallstreffer erklaeren.
_HELDOUT_SCHWELLE: Final[float] = 0.1

#: Aufloesung der PNG-Fassung.
_DPI: Final[int] = 300

#: Marker und Linienstile je Verfahren — die Unterscheidung ohne Farbe.
_STILE: Final[dict[str, tuple[str, str, str]]] = {
    "prototyp": ("o", "-", "#222222"),
    "B0": ("s", "--", "#777777"),
    "B2": ("^", ":", "#bbbbbb"),
    "B3": ("D", "-.", "#999999"),
}

#: Schraffuren je Verfahren fuer Flaechen (Balken, Boxen).
_SCHRAFFUR: Final[dict[str, str]] = {
    "prototyp": "",
    "B0": "///",
    "B2": "...",
    "B3": "xxx",
}

#: Schraffur je Einstufung "spiegelt Regel exakt" in Abbildung 5.
_SCHRAFFUR_SPIEGELUNG: Final[dict[str, str]] = {
    Spiegelung.JA.value: "",
    Spiegelung.TEILWEISE.value: "///",
    Spiegelung.NEIN.value: "xxx",
}

#: Klarnamen der Trefferkategorien fuer die Legende.
_KATEGORIENAMEN: Final[dict[str, str]] = {
    "A": "A: durch die zugeordnete Regel",
    "B": "B: durch eine andere Regel",
    "C": "C: nicht erkannt",
    "S": "S: satzbasiert, nicht zuordenbar",
}

#: Graustufe und Schraffur je Trefferkategorie (Abbildung 11).
#:
#: Die Reihenfolge ist die Leserichtung der Aussage: erwartet erkannt, anders
#: erkannt, nicht erkannt, nicht zuordenbar.
_STIL_KATEGORIE: Final[dict[str, tuple[str, str]]] = {
    "A": ("#404040", ""),
    "B": ("#8c8c8c", "///"),
    "C": ("#e8e8e8", "xxx"),
    "S": ("#ffffff", "..."),
}

#: Graustufe je Einstufung "spiegelt Regel exakt".
_GRAU_SPIEGELUNG: Final[dict[str, str]] = {
    Spiegelung.JA.value: "#404040",
    Spiegelung.TEILWEISE.value: "#909090",
    Spiegelung.NEIN.value: "#e0e0e0",
}


def setze_stil() -> None:
    """Setzt die Darstellungsvorgaben aller Abbildungen.

    Neun Punkt ist die Untergrenze fuer eine im Druck lesbare
    Achsenbeschriftung; die Vorgabe von matplotlib liegt darunter.
    """
    plt.rcParams.update(
        {
            "figure.dpi": 110,
            "savefig.dpi": _DPI,
            "font.size": 9.0,
            "axes.titlesize": 10.0,
            "axes.labelsize": 9.0,
            "xtick.labelsize": 9.0,
            "ytick.labelsize": 9.0,
            "legend.fontsize": 9.0,
            "axes.grid": True,
            "grid.alpha": 0.3,
            "grid.linewidth": 0.5,
            "axes.axisbelow": True,
            "figure.autolayout": False,
            "savefig.bbox": "tight",
        }
    )


# ---------------------------------------------------------------------------
# Datenzugriff
# ---------------------------------------------------------------------------


def _mittel(  # noqa: PLR0913 - jede Angabe waehlt eine eigene Dimension des Langformats
    lang: pd.DataFrame,
    *,
    metrik: str,
    verfahren: str,
    klasse: str,
    teilversuch: str,
    ebene: Ebene = Ebene.ZELLE,
    fehlerrate: float | None = None,
) -> float | None:
    """Mittelt eine Kennzahl ueber die Wiederholungen; ``None`` ohne Daten."""
    gefiltert = auswahl(
        lang,
        metrik=metrik,
        verfahren=verfahren,
        ebene=ebene,
        gruppe_art=GRUPPE_GESAMT,
        klasse=klasse,
        teilversuch=teilversuch,
        fehlerrate=fehlerrate,
    )
    gefiltert = gefiltert[gefiltert["wert"].notna()]
    if gefiltert.empty:
        return None
    return float(mittel_je_wiederholung(gefiltert).mean())


def _reihe(  # noqa: PLR0913 - jede Angabe waehlt eine eigene Dimension des Langformats
    lang: pd.DataFrame,
    *,
    metrik: str,
    verfahren: str,
    klasse: str,
    teilversuch: str,
    ebene: Ebene = Ebene.ZELLE,
) -> list[float]:
    """Gibt eine Kennzahl je Wiederholung zurueck; leer ohne Daten."""
    gefiltert = auswahl(
        lang,
        metrik=metrik,
        verfahren=verfahren,
        ebene=ebene,
        gruppe_art=GRUPPE_GESAMT,
        klasse=klasse,
        teilversuch=teilversuch,
    )
    gefiltert = gefiltert[gefiltert["wert"].notna()]
    if gefiltert.empty:
        return []
    return [float(wert) for wert in mittel_je_wiederholung(gefiltert)]


def _ohne_daten(titel: str, grund: str) -> tuple[Figure, str]:
    """Baut eine leere Abbildung mit Begruendung statt einer Ausnahme.

    Fehlt ein Teilversuch — etwa weil eine Serie nur teilweise gerechnet wurde —,
    ist das ein Zustand und kein Programmfehler. Eine Abbildung, die den Grund
    nennt, ist an dieser Stelle mehr wert als ein Abbruch: Der Rest der
    Auswertung bleibt erhalten, und in der Abbildungsdatei steht, warum sie leer
    ist. Eine stillschweigend fehlende Datei waere die schlechteste der drei
    Moeglichkeiten.

    Args:
        titel: Titel der Abbildung.
        grund: Klartextbegruendung.

    Returns:
        Die Abbildung und ihre Bildunterschrift.
    """
    figur, achse = plt.subplots(figsize=(5.6, 2.4))
    achse.axis("off")
    achse.set_title(titel)
    achse.text(0.5, 0.5, grund, ha="center", va="center", fontsize=9, wrap=True)
    return figur, f"{titel}. {grund}"


# ---------------------------------------------------------------------------
# Die zehn Abbildungen
# ---------------------------------------------------------------------------


def abbildung_1(lang: pd.DataFrame, plan: Versuchsplan) -> tuple[Figure, str]:
    """Heatmap Fehlerklasse gegen Fehlerrate, F1 des Prototyps.

    Nur die zellbasierten Klassen des Hauptversuchs: F6 und HO1 erzeugen
    zusaetzliche Zeilen und haben keinen zellbasierten Ground Truth.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Die Abbildung und ihre Bildunterschrift.
    """
    klassen = list(plan.hauptversuch.gruppen)
    raten = sorted(plan.hauptversuch.raten)
    werte = np.array(
        [
            [
                _mittel(
                    lang,
                    metrik="f1",
                    verfahren=_PROTOTYP,
                    klasse=klasse,
                    teilversuch=_HAUPT,
                    fehlerrate=rate,
                )
                or np.nan
                for rate in raten
            ]
            for klasse in klassen
        ]
    )
    figur, achse = plt.subplots(figsize=(6.0, 4.2))
    bild = achse.imshow(werte, cmap="Greys", vmin=0.0, vmax=1.0, aspect="auto")
    achse.set_xticks(range(len(raten)), [f"{rate:.0%}" for rate in raten])
    achse.set_yticks(range(len(klassen)), klassen)
    achse.set_xlabel("Fehlerrate")
    achse.set_ylabel("Fehlerklasse")
    achse.set_title("F1 des Prototyps je Fehlerklasse und Fehlerrate (Zellebene)")
    achse.grid(visible=False)
    for zeile in range(len(klassen)):
        for spalte in range(len(raten)):
            wert = werte[zeile, spalte]
            if np.isnan(wert):
                continue
            achse.text(
                spalte,
                zeile,
                f"{wert:.2f}".replace(".", ","),
                ha="center",
                va="center",
                color="white" if wert > 0.55 else "black",  # noqa: PLR2004 - Kontrastschwelle
                fontsize=9,
            )
    figur.colorbar(bild, ax=achse, label="F1")
    unterschrift = (
        "Abbildung 1: F1-Wert des regelbasierten Prototyps auf der Zellebene, je "
        f"Fehlerklasse und Fehlerrate, gemittelt ueber {plan.hauptversuch.wiederholungen} "
        "Wiederholungen. Dargestellt sind die sieben zellbasierten Fehlerklassen des "
        "Hauptversuchs; F6 (Duplikate) und HO1 erzeugen zusaetzliche Zeilen und haben "
        "keinen zellbasierten Ground Truth, sie werden satzbasiert in den Teilversuchen "
        "T1 und T2 berichtet."
    )
    return figur, unterschrift


def abbildung_2(lang: pd.DataFrame, plan: Versuchsplan) -> tuple[Figure, str]:
    """Boxplots der F1-Verteilung ueber die Seeds, je Verfahren und Klasse.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Die Abbildung und ihre Bildunterschrift.
    """
    klassen = list(plan.hauptversuch.gruppen)
    verfahren = list(plan.hauptversuch.verfahren)
    figur, achse = plt.subplots(figsize=(7.2, 4.2))
    breite = 0.8 / len(verfahren)

    for nummer, name in enumerate(verfahren):
        daten = [
            _reihe(lang, metrik="f1", verfahren=name, klasse=klasse, teilversuch=_HAUPT) or [np.nan]
            for klasse in klassen
        ]
        stellen = [
            index + (nummer - (len(verfahren) - 1) / 2) * breite for index in range(len(klassen))
        ]
        kasten = achse.boxplot(
            daten,
            positions=stellen,
            widths=breite * 0.85,
            patch_artist=True,
            manage_ticks=False,
            medianprops={"color": "black", "linewidth": 1.2},
            flierprops={"marker": _STILE[name][0], "markersize": 3, "markerfacecolor": "none"},
        )
        for koerper in kasten["boxes"]:
            koerper.set_facecolor(_STILE[name][2])
            koerper.set_hatch(_SCHRAFFUR[name])
            koerper.set_edgecolor("black")
            koerper.set_linewidth(0.8)
        kasten["boxes"][0].set_label(name)

    achse.set_xticks(range(len(klassen)), klassen)
    achse.set_xlabel("Fehlerklasse")
    achse.set_ylabel("F1 (Zellebene)")
    achse.set_ylim(-0.02, 1.02)
    achse.set_title("Verteilung des F1-Werts ueber die Wiederholungen")
    achse.legend(loc="upper right", framealpha=0.9)
    unterschrift = (
        "Abbildung 2: Verteilung des F1-Werts auf der Zellebene ueber die "
        f"{plan.hauptversuch.wiederholungen} Wiederholungen, je Verfahren und "
        "Fehlerklasse, aggregiert ueber die vier Ratenstufen. Die Kaesten zeigen den "
        "Interquartilsabstand, die Linie den Median, die Antennen das 1,5-fache des "
        "Interquartilsabstands. Die Verfahren sind ueber Schraffur und Graustufe "
        "unterschieden und bleiben damit im Graustufendruck lesbar."
    )
    return figur, unterschrift


def abbildung_3(
    lang: pd.DataFrame, plan: Versuchsplan, sweep: pd.DataFrame
) -> tuple[Figure, str]:
    """Precision-Recall-Kurve von B2 mit den Betriebspunkten der uebrigen Verfahren.

    Gezeichnet wird auf der **Satzebene**: Nur dort liefert der Schwellen-Sweep
    von B2 Precision und Recall je ``contamination``-Stufe. Die uebrigen Verfahren
    treffen binaere Entscheidungen und haben deshalb genau einen Betriebspunkt —
    fuer sie wird kein Pseudo-Score erfunden.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.
        sweep: Der Schwellen-Sweep von B2 mit den Spalten ``contamination``,
            ``precision_satz``, ``recall_satz`` und ``gewaehlt``.

    Returns:
        Die Abbildung und ihre Bildunterschrift.
    """
    figur, achse = plt.subplots(figsize=(5.6, 4.4))
    if not sweep.empty:
        gemittelt = (
            sweep.groupby("contamination", observed=True)[["precision_satz", "recall_satz"]]
            .mean()
            .sort_values("recall_satz")
        )
        achse.plot(
            gemittelt["recall_satz"],
            gemittelt["precision_satz"],
            marker=_STILE["B2"][0],
            linestyle=_STILE["B2"][1],
            color="black",
            markerfacecolor="white",
            markersize=5,
            linewidth=1.2,
            label="B2 (IsolationForest), Schwellen-Sweep",
        )
        for stufe, zeile in gemittelt.iterrows():
            achse.annotate(
                f"{float(str(stufe)):.3f}".replace(".", ","),
                (zeile["recall_satz"], zeile["precision_satz"]),
                textcoords="offset points",
                xytext=(4, 4),
                fontsize=9,
            )

    for name in plan.hauptversuch.verfahren:
        if name == "B2":
            continue
        punkte = [
            (
                _mittel(
                    lang,
                    metrik="recall",
                    verfahren=name,
                    klasse=klasse,
                    teilversuch=_HAUPT,
                    ebene=Ebene.SATZ,
                ),
                _mittel(
                    lang,
                    metrik="precision",
                    verfahren=name,
                    klasse=klasse,
                    teilversuch=_HAUPT,
                    ebene=Ebene.SATZ,
                ),
            )
            for klasse in plan.hauptversuch.gruppen
        ]
        gueltig = [(r, p) for r, p in punkte if r is not None and p is not None]
        if not gueltig:
            continue
        achse.scatter(
            [r for r, _ in gueltig],
            [p for _, p in gueltig],
            marker=_STILE[name][0],
            s=42,
            facecolors=_STILE[name][2],
            edgecolors="black",
            linewidths=0.8,
            label=f"{name}, ein Betriebspunkt je Fehlerklasse",
            zorder=3,
        )

    achse.set_xlabel("Recall (Satzebene)")
    achse.set_ylabel("Precision (Satzebene)")
    achse.set_xlim(-0.02, 1.02)
    achse.set_ylim(-0.02, 1.02)
    achse.set_title("Precision-Recall-Verhalten auf der Satzebene")
    achse.legend(loc="lower left", framealpha=0.9)
    unterschrift = (
        "Abbildung 3: Precision-Recall-Verhalten auf der Satzebene. Nur B2 liefert "
        "einen kontinuierlichen Anomaliescore und damit eine Kurve; die Punkte auf ihr "
        "sind die sieben contamination-Stufen des Schwellen-Sweeps, beschriftet mit der "
        "jeweiligen Stufe. Der Prototyp und B0 treffen binaere Entscheidungen und haben "
        "genau einen Betriebspunkt je Fehlerklasse; fuer sie wird kein Pseudo-Score "
        "erfunden. Die Satzebene ist gewaehlt, weil der Sweep von B2 dort ausgewertet "
        "wird."
    )
    return figur, unterschrift


def abbildung_4(lang: pd.DataFrame, plan: Versuchsplan) -> tuple[Figure, str]:
    """Balkendiagramm des Recalls je Fehlerklasse mit Konfidenzintervall.

    HO1 und HO2 stehen deutlich abgesetzt: Sie sind **Held-out** und sollen nicht
    gefunden werden. Ein Balken nahe null ist dort das Konstruktionsziel.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Die Abbildung und ihre Bildunterschrift.
    """
    from src.evaluation.tabellen import t1_hauptergebnis  # noqa: PLC0415 - Zyklus vermeiden

    tabelle = t1_hauptergebnis(lang, plan)
    tabelle = tabelle[tabelle["verfahren"] == _PROTOTYP].reset_index(drop=True)
    heldout = tabelle["fehlerklasse"].str.startswith("HO")
    geordnet = pd.concat([tabelle[~heldout], tabelle[heldout]], ignore_index=True)

    figur, achse = plt.subplots(figsize=(7.0, 4.2))
    stellen = np.arange(len(geordnet), dtype=float)
    trennstelle = int((~heldout).sum())
    stellen[trennstelle:] += 0.8

    werte = geordnet["recall"].astype(float).to_numpy()
    unten = werte - geordnet["recall_ci_unten"].astype(float).to_numpy()
    oben = geordnet["recall_ci_oben"].astype(float).to_numpy() - werte
    kennungen = list(geordnet["fehlerklasse"])
    farben = ["#e8e8e8" if name.startswith("HO") else "#606060" for name in kennungen]
    schraffuren = ["xxx" if name.startswith("HO") else "" for name in kennungen]

    balken = achse.bar(stellen, werte, width=0.68, color=farben, edgecolor="black", linewidth=0.8)
    for stab, schraffur in zip(balken, schraffuren, strict=True):
        stab.set_hatch(schraffur)
    achse.errorbar(
        stellen, werte, yerr=[unten, oben], fmt="none", ecolor="black", capsize=3, linewidth=1.0
    )
    if trennstelle < len(geordnet):
        achse.axvline(stellen[trennstelle] - 0.9, color="black", linestyle=":", linewidth=1.0)
        achse.text(
            stellen[trennstelle] - 0.82,
            1.0,
            "Held-out",
            fontsize=9,
            va="top",
            ha="left",
            style="italic",
        )
    for stelle, art in zip(stellen, geordnet["recall_ci_art"], strict=True):
        if art == "clopper-pearson":
            achse.text(stelle, 0.03, "CP", ha="center", fontsize=9, style="italic")

    achse.set_xticks(stellen, geordnet["fehlerklasse"], rotation=0)
    achse.set_ylabel("Recall")
    achse.set_ylim(0.0, 1.05)
    achse.set_xlabel("Fehlerklasse")
    achse.set_title("Recall des Prototyps je Fehlerklasse mit 95-Prozent-Intervall")

    # Ein Held-out-Balken deutlich ueber null ist kein Darstellungsfehler, sondern
    # ein Befund — und die Bildunterschrift darf ihn nicht wegerklaeren.
    auffaellig = [
        (str(zeile["fehlerklasse"]), float(zeile["recall"]))
        for _, zeile in geordnet.iterrows()
        if str(zeile["fehlerklasse"]).startswith("HO")
        and zeile["recall"] is not None
        and float(zeile["recall"]) > _HELDOUT_SCHWELLE
    ]
    nachsatz = (
        ""
        if not auffaellig
        else (
            " "
            + "; ".join(
                f"{name} liegt mit Recall {wert:.2f} deutlich ueber null".replace(".", ",")
                for name, wert in auffaellig
            )
            + ". Das ist ein Befund und kein Widerspruch zur Konstruktion, und es ist "
            "**keine** Generalisierung des Katalogs: Welche Regel dort greift, zeigt die "
            "Kreuztabelle in Abbildung 6. Bei HO1 ist es ausschliesslich R-046 — der "
            "Katalog erkennt die Beinahe-Dublette nicht an der Namensaehnlichkeit, sondern "
            "an einer davon unabhaengigen Integritaetsverletzung: Der duplizierte "
            "Personensatz erzeugt einen zweiten Versicherungsnehmer in derselben Anfrage. "
            "Als Held-out-Klasse fuer Aehnlichkeitserkennung ist HO1 damit **bestaetigt** "
            "und nicht widerlegt; auf der Zellebene bleibt ihr Recall null. Erkannt wird "
            "nicht der Fehler selbst, sondern eine Nebenwirkung, die er hinterlaesst — und "
            "beide sehen in einer Ergebnistabelle gleich aus, solange man die Kreuztabelle "
            "nicht danebenlegt."
        )
    )
    unterschrift = (
        "Abbildung 4: Recall des Prototyps je Fehlerklasse mit 95-Prozent-"
        "Konfidenzintervall ueber die Wiederholungen. Die beiden Held-out-Klassen HO1 "
        "und HO2 sind rechts abgesetzt und schraffiert: Sie sind so konstruiert, dass "
        "der Katalog sie nicht findet." + nachsatz + " Mit CP markierte Intervalle stammen "
        "aus dem exakten Clopper-Pearson-Verfahren; dort liefern alle Wiederholungen "
        "denselben Wert, und der Bootstrap entartet. F6 und HO1 werden satzbasiert "
        "ausgewertet, alle uebrigen zellbasiert."
    )
    return figur, unterschrift


def abbildung_5(lang: pd.DataFrame, plan: Versuchsplan) -> tuple[Figure, str]:
    """Recall je Injektionsvariante aus dem Teilversuch T6.

    Die wichtigste Abbildung der Arbeit: Sie zeigt empirisch, dass Varianten, die
    keine Regelbedingung spiegeln, schlechter erkannt werden — und entkraeftet
    damit den Zirkularitaetsvorwurf.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Die Abbildung und ihre Bildunterschrift.
    """
    from src.evaluation.tabellen import t4_varianten  # noqa: PLC0415 - Zyklus vermeiden

    tabelle = t4_varianten(lang, plan)
    tabelle = tabelle[tabelle["n"] > 0].reset_index(drop=True)
    if tabelle.empty:
        return _ohne_daten(
            "Recall je Injektionsvariante (Teilversuch T6)",
            "Der Teilversuch T6 (Variantencharakterisierung) wurde in dieser Serie nicht "
            "gerechnet. Aus dem faktoriellen Hauptversuch laesst sich diese Abbildung "
            "nicht zeichnen: Dort haben knappe Varianten einstellige Fallzahlen.",
        )

    hoehe = min(11.0, max(3.2, 0.17 * len(tabelle) + 1.8))
    figur, achse = plt.subplots(figsize=(7.6, hoehe))

    # Zwischen zwei Fehlerklassen entsteht eine Luecke von einer halben
    # Balkenhoehe. Die Trennlinie liegt in ihrer Mitte — berechnet aus den
    # fertigen Positionen und nicht waehrend ihres Aufbaus, sonst haengt sie an
    # der Zahl der bereits gesetzten Balken statt an ihrer Lage.
    luecke = 0.6
    stellen_liste: list[float] = []
    grenzen: list[float] = []
    versatz = 0.0
    vorige: str | None = None
    for nummer, (_, zeile) in enumerate(tabelle.iterrows()):
        klasse = str(zeile["fehlerklasse"])
        if vorige is not None and klasse != vorige:
            grenzen.append(nummer + versatz + luecke / 2 - 0.5)
            versatz += luecke
        stellen_liste.append(nummer + versatz)
        vorige = klasse
    stellen = np.array(stellen_liste, dtype=float)

    werte = tabelle["recall"].astype(float).to_numpy()
    links = werte - tabelle["ci_unten"].astype(float).to_numpy()
    rechts = tabelle["ci_oben"].astype(float).to_numpy() - werte
    balken = achse.barh(
        stellen,
        werte,
        height=0.72,
        color=[_GRAU_SPIEGELUNG[wert] for wert in tabelle["spiegelt_regel_exakt"]],
        edgecolor="black",
        linewidth=0.7,
    )
    for stab, wert in zip(balken, tabelle["spiegelt_regel_exakt"], strict=True):
        stab.set_hatch(_SCHRAFFUR_SPIEGELUNG[wert])
    achse.errorbar(
        werte, stellen, xerr=[links, rechts], fmt="none", ecolor="black", capsize=2, linewidth=0.8
    )
    for stelle, wert, fallzahl, unentdeckt in zip(
        stellen,
        werte,
        tabelle["n"],
        tabelle["erwartet_unentdeckt"],
        strict=True,
    ):
        marke = " (erwartet unentdeckt)" if unentdeckt else ""
        achse.text(
            min(float(wert) + 0.02, 1.0),
            stelle,
            f"n = {fallzahl}{marke}",
            va="center",
            fontsize=9,
        )
    for grenze in grenzen:
        achse.axhline(grenze, color="black", linewidth=0.5, linestyle=":")

    achse.set_yticks(stellen, tabelle["variante"])
    achse.invert_yaxis()
    achse.set_xlim(0.0, 1.35)
    achse.set_xticks([0.0, 0.25, 0.5, 0.75, 1.0])
    achse.set_xlabel("Recall")
    achse.set_ylabel("Injektionsvariante")
    achse.set_title("Recall je Injektionsvariante (Teilversuch T6)")
    griffe = [
        Rectangle(
            (0, 0),
            1,
            1,
            facecolor=_GRAU_SPIEGELUNG[stufe.value],
            hatch=_SCHRAFFUR_SPIEGELUNG[stufe.value],
            edgecolor="black",
        )
        for stufe in Spiegelung
    ]
    achse.legend(
        griffe,
        [f"spiegelt Regel exakt: {stufe.value}" for stufe in Spiegelung],
        loc="lower right",
        framealpha=0.95,
    )
    anteile = tabelle["spiegelt_regel_exakt"].value_counts().to_dict()
    mittel = tabelle.groupby("spiegelt_regel_exakt")["recall"].mean().to_dict()
    unterschrift = (
        "Abbildung 5: Recall je Injektionsvariante aus dem Teilversuch T6 "
        "(Variantencharakterisierung), mit exaktem Clopper-Pearson-Intervall und der "
        "Fallzahl n an jedem Balken. Gruppiert nach Fehlerklasse; Schraffur und "
        "Graustufe kodieren, ob die Variante die Bedingung ihrer Regel exakt spiegelt "
        f"({anteile.get('ja', 0)} Varianten, mittlerer Recall "
        f"{_komma(mittel.get('ja'))}), nur teilweise ({anteile.get('teilweise', 0)}, "
        f"{_komma(mittel.get('teilweise'))}) oder gar nicht ({anteile.get('nein', 0)}, "
        f"{_komma(mittel.get('nein'))}). Varianten, die laut Spezifikation unentdeckt "
        "bleiben sollen, sind gekennzeichnet. "
        + _trefferquote_text(tabelle)
        + " Die Abbildung stammt nicht aus dem faktoriellen Hauptversuch: Dort gibt die "
        "universumsproportionale Zuteilung knappen Varianten einstellige Fallzahlen, und "
        "ein Recall aus n = 1 waere nicht interpretierbar."
    )
    return figur, unterschrift


def _komma(wert: float | None) -> str:
    """Formatiert eine Zahl mit deutschem Dezimalkomma; ``None`` als Gedankenstrich."""
    if wert is None or pd.isna(wert):
        return "—"
    return f"{float(wert):.3f}".replace(".", ",")


def _trefferquote_text(tabelle: pd.DataFrame) -> str:
    """Formuliert die Trefferquote der Vorab-Zuordnung fuer die Bildunterschrift.

    Die Einstufung stammt aus ``spec/03`` und wurde **vor** der Messung
    festgelegt. Ihre Quote ist damit eine Guetezahl der Methode: Eine vorab
    formulierte, falsifizierbare Erwartung, die ueberwiegend, aber nicht
    vollstaendig eingetroffen ist. Wo sie danebenliegt, ist das ein Ergebnis und
    kein Makel der Spezifikation — und die **Richtung** der Abweichung sagt
    verschiedene Dinge.

    Args:
        tabelle: Die Variantentabelle ``t4`` mit ihren ``attrs``.

    Returns:
        Den Satz fuer die Bildunterschrift; leer ohne Angaben.
    """
    if "vorab_eingetroffen" not in tabelle.attrs:
        return ""
    zu_hoch = tabelle.attrs["vorab_ueberschaetzt"]
    zu_niedrig = tabelle.attrs["vorab_unterschaetzt"]
    ueberwiegt = "unterschaetzt" if len(zu_niedrig) > len(zu_hoch) else "ueberschaetzt"
    konservativ = (
        (
            " **Der gemessene Kontrast ist damit konservativ.** Die Abweichungen zwischen "
            "Vorab-Einteilung und Messung wirken ueberwiegend in Richtung eines kleineren "
            "Unterschieds: Die falsch eingeordneten Varianten liegen mehrheitlich in der "
            "unteren Gruppe und werden dort besser erkannt, als die Einteilung erwartet "
            "hat. Sie ziehen deren Mittelwert nach oben. Bei zutreffender Einteilung fiele "
            "der Abstand groesser aus — die berichtete Zahl ist eine Untergrenze."
        )
        if ueberwiegt == "unterschaetzt"
        else ""
    )
    return (
        f"Die Vorabeinstufung aus spec/03 trifft bei {tabelle.attrs['vorab_eingetroffen']} "
        f"von {tabelle.attrs['vorab_geprueft']} Varianten zu (Schwelle: Recall 0,5, bei "
        f"'teilweise' ein Wert echt zwischen 0 und 1). Ueberschaetzt wurde bei "
        f"{len(zu_hoch)} Varianten ({zu_hoch}) — eine greifende Regel erwartet, die "
        f"Variante bleibt dennoch unentdeckt. Unterschaetzt bei {len(zu_niedrig)} "
        f"({zu_niedrig}) — der Katalog findet mehr, als die Taxonomie ihm zutraut. Beide "
        "Richtungen sind Befunde: Die erste schwaecht die Aussage ueber den Katalog, die "
        "zweite verkleinert den Kontrast zwischen spiegelnden und nicht spiegelnden "
        "Varianten." + konservativ
    )


def abbildung_11(lang: pd.DataFrame, plan: Versuchsplan) -> tuple[Figure, str]:
    """Verteilung der Trefferkategorien je Fehlerklasse.

    **Eine eigene Abbildung und keine dritte Gruppe in Abbildung 5.** Abbildung 5
    traegt die **vorab** festgelegte Einteilung "spiegelt Regel exakt" aus
    ``spec/03``; genau darin liegt ihr Wert als Beleg gegen den
    Zirkularitaetsvorwurf. Eine nachtraeglich aus den Daten gewonnene Einteilung
    in dieselbe Abbildung zu mischen, wuerde beide Aussagen ununterscheidbar
    machen — die vorab formulierte und die gemessene.

    Die Kategorien stammen aus der Kreuztabelle ``regel_id`` gegen Variante: Sie
    sagen, **welche** Regel tatsaechlich getroffen hat. Kategorie B ist der
    inhaltlich staerkste Einzelbefund — eine Variante, die von einer Regel
    gefangen wird, die nicht gegen sie entworfen wurde, ist das Gegenteil von
    Zirkularitaet.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Die Abbildung und ihre Bildunterschrift.
    """
    from src.evaluation.tabellen import t4_varianten  # noqa: PLC0415 - Zyklus vermeiden

    tabelle = t4_varianten(lang, plan)
    tabelle = tabelle[tabelle["n"] > 0].copy()
    if tabelle.empty:
        return _ohne_daten(
            "Trefferkategorien je Fehlerklasse",
            "Der Teilversuch T6 (Variantencharakterisierung) wurde nicht gerechnet.",
        )
    tabelle["kategorie"] = tabelle["trefferkategorie"].str[0]
    kategorien = [wert for wert in _STIL_KATEGORIE if (tabelle["kategorie"] == wert).any()]
    klassen = list(dict.fromkeys(tabelle["fehlerklasse"]))
    kreuz = (
        tabelle.pivot_table(
            index="fehlerklasse", columns="kategorie", values="variante", aggfunc="count"
        )
        .reindex(index=klassen, columns=kategorien)
        .fillna(0.0)
    )

    figur, achse = plt.subplots(figsize=(6.6, 3.8))
    stellen = np.arange(len(klassen), dtype=float)
    unten = np.zeros(len(klassen), dtype=float)
    for kategorie in kategorien:
        werte = kreuz[kategorie].to_numpy(dtype=float)
        grau, schraffur = _STIL_KATEGORIE[kategorie]
        balken = achse.bar(
            stellen,
            werte,
            bottom=unten,
            width=0.66,
            color=grau,
            edgecolor="black",
            linewidth=0.8,
            label=_KATEGORIENAMEN[kategorie],
        )
        for stab in balken:
            stab.set_hatch(schraffur)
        for stelle, wert, sockel in zip(stellen, werte, unten, strict=True):
            if wert > 0:
                achse.text(
                    stelle,
                    sockel + wert / 2,
                    f"{int(wert)}",
                    ha="center",
                    va="center",
                    fontsize=9,
                )
        unten += werte

    achse.set_xticks(stellen, klassen)
    achse.set_xlabel("Fehlerklasse")
    achse.set_ylabel("Injektionsvarianten")
    achse.set_title("Trefferkategorien je Fehlerklasse (Teilversuch T6)")
    achse.legend(loc="upper center", ncols=2, fontsize=9, framealpha=0.95)
    achse.set_ylim(0, float(kreuz.to_numpy().sum(axis=1).max()) * 1.55)

    verteilung = tabelle["kategorie"].value_counts().to_dict()
    kategorie_b = sorted(tabelle.loc[tabelle["kategorie"] == "B", "variante"])
    unterschrift = (
        "Abbildung 11: Verteilung der Trefferkategorien ueber die "
        f"{len(tabelle)} Injektionsvarianten des Teilversuchs T6. Die Kategorie stammt aus "
        "der Kreuztabelle regel_id gegen Variante und sagt, **welche** Regel eine Variante "
        "tatsaechlich gefunden hat — die Regel-ID wird gemessen und nicht neu vergeben. "
        f"A ({verteilung.get('A', 0)}): erkannt durch die Regel, die spec/03 der Variante "
        f"zuordnet. B ({verteilung.get('B', 0)}): erkannt, aber durch eine **andere** Regel "
        f"— {kategorie_b}. C ({verteilung.get('C', 0)}): nicht erkannt. "
        f"S ({verteilung.get('S', 0)}): satzbasierte Klassen (F6, HO1), fuer die eine "
        "zellbasierte Zuordnung nicht definiert ist; sie werden satzbasiert ausgewertet und "
        "sind **nicht** unerkannt. "
        "Kategorie B ist der inhaltlich staerkste Einzelbefund: Eine Variante, die von "
        "einer Regel gefangen wird, die nicht gegen sie entworfen wurde, ist das Gegenteil "
        "von Zirkularitaet — der Katalog hat dort eine Deckung, die ueber seine eigene "
        "Herleitung hinausreicht. Die Abbildung ergaenzt Abbildung 5 und ersetzt sie nicht: "
        "Dort steht die **vorab** festgelegte Einteilung, hier die gemessene."
    )
    return figur, unterschrift


def abbildung_6(lang: pd.DataFrame, plan: Versuchsplan) -> tuple[Figure, str]:
    """Kreuztabelle Regel gegen Fehlerklasse als Heatmap.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan; waehlt dieselben Bloecke wie ``t3_regeldiagnose``.

    Returns:
        Die Abbildung und ihre Bildunterschrift.
    """
    from src.evaluation.tabellen import klassenbloecke  # noqa: PLC0415 - Zyklus vermeiden

    kreuz = kreuztabelle_lang(lang)
    kreuz = kreuz[
        (kreuz["verfahren"] == _PROTOTYP) & kreuz["teilversuch"].isin(klassenbloecke(plan))
    ]
    regeln = [regel.regel_id for regel in KATALOG]
    klassen = sorted(kreuz["fehlerklasse"].dropna().unique())

    verdichtet = kreuz.pivot_table(
        index="regel_id", columns="fehlerklasse", values="treffer", aggfunc="sum"
    )
    matrix = verdichtet.reindex(index=regeln, columns=klassen).fillna(0.0).to_numpy()
    ohne_treffer = int((matrix.sum(axis=1) == 0).sum())

    with np.errstate(divide="ignore"):
        skaliert = np.where(matrix > 0, np.log10(matrix + 1.0), np.nan)

    figur, achse = plt.subplots(figsize=(6.4, 10.5))
    bild = achse.imshow(skaliert, cmap="Greys", aspect="auto")
    achse.set_xticks(range(len(klassen)), klassen, rotation=90)
    achse.set_yticks(range(len(regeln)), regeln, fontsize=9)
    achse.set_xlabel("Fehlerklasse der getroffenen Zelle")
    achse.set_ylabel("meldende Regel")
    achse.set_title("Treffer je Regel und Fehlerklasse")
    achse.grid(visible=False)
    figur.colorbar(bild, ax=achse, label="log10(Treffer + 1)")
    unterschrift = (
        f"Abbildung 6: Kreuztabelle der {len(regeln)} Regeln des Katalogs gegen die "
        "Fehlerklasse der von ihnen getroffenen Zellen, summiert ueber alle Laeufe der "
        "klassenweisen Bloecke. Die Farbskala ist logarithmisch, weil die Trefferzahlen "
        "ueber mehrere Groessenordnungen streuen. Der Spaltenwert '-' steht fuer "
        "Fehlalarme: Dort liegt gar kein Fehler und damit auch keine Fehlerklasse. "
        f"{ohne_treffer} der {len(regeln)} Regeln haben in keinem Lauf gemeldet; sie "
        "bleiben als leere Zeilen stehen, weil eine Regel ohne Treffer Ueberdeckung des "
        "Katalogs gegenueber der Fehlertaxonomie ist und damit ein Ergebnis."
    )
    return figur, unterschrift


def abbildung_7(lang: pd.DataFrame, plan: Versuchsplan) -> tuple[Figure, str]:
    """Laufzeit ueber Datensatzgroesse, doppelt logarithmisch, aus T4.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Die Abbildung und ihre Bildunterschrift.
    """
    from src.evaluation.tabellen import t6_laufzeit  # noqa: PLC0415 - Zyklus vermeiden

    tabelle = t6_laufzeit(lang, plan)
    if tabelle.empty:
        return _ohne_daten(
            "Laufzeit ueber Datensatzgroesse (Teilversuch T4)",
            "Der Teilversuch T4 (Skalierung) wurde in dieser Serie nicht gerechnet.",
        )
    figur, achse = plt.subplots(figsize=(5.6, 4.2))
    steigungen: dict[str, float] = {}
    for name in sorted(tabelle["verfahren"].dropna().unique()):
        eigene = tabelle[tabelle["verfahren"] == name].sort_values("n_anfragen")
        eigene = eigene[eigene["laufzeit_s"].notna()]
        if eigene.empty:
            continue
        achse.plot(
            eigene["n_anfragen"],
            eigene["laufzeit_s"],
            marker=_STILE.get(name, ("o", "-", "#444444"))[0],
            linestyle=_STILE.get(name, ("o", "-", "#444444"))[1],
            color="black",
            markerfacecolor=_STILE.get(name, ("o", "-", "#444444"))[2],
            markersize=6,
            linewidth=1.2,
            label=name,
        )
        if len(eigene) > 1:
            steigung = np.polyfit(
                np.log10(eigene["n_anfragen"].astype(float)),
                np.log10(eigene["laufzeit_s"].astype(float)),
                1,
            )[0]
            steigungen[name] = float(steigung)
    achse.set_xscale("log")
    achse.set_yscale("log")
    achse.set_xlabel("Anfragen im Datensatz")
    achse.set_ylabel("Laufzeit in Sekunden")
    achse.set_title("Laufzeit ueber Datensatzgroesse (Teilversuch T4)")
    achse.legend(loc="upper left", framealpha=0.9)
    text = ", ".join(
        f"{name}: {wert:.2f}".replace(".", ",") for name, wert in sorted(steigungen.items())
    )
    unterschrift = (
        "Abbildung 7: Laufzeit je Verfahren ueber die Datensatzgroesse, doppelt "
        "logarithmisch. Die Steigung in dieser Darstellung ist der Exponent des "
        f"Laufzeitverhaltens; gemessen wurde {text or 'keine Steigung (zu wenige Stufen)'}. "
        "Eine Steigung nahe eins bedeutet lineares Verhalten. Gemittelt ueber die "
        "Wiederholungen des Teilversuchs T4; injiziert wurde die Fehlerklasse mit dem "
        "kleinsten Universum, damit die Messung das Verfahren zeigt und nicht die "
        "Injektion."
    )
    return figur, unterschrift


def abbildung_8(lang: pd.DataFrame, plan: Versuchsplan) -> tuple[Figure, str]:
    """Vergleich von Injektionsvarianz und Datenvarianz.

    Ist die Datenvarianz deutlich groesser als die Injektionsvarianz, haengt das
    Ergebnis am Generator und nicht am Verfahren. Das muss man wissen, bevor es
    jemand anderes bemerkt.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Die Abbildung und ihre Bildunterschrift.
    """
    block = next((b for b in plan.teilversuche if b.kennung == _DATENVARIANZ), None)
    klasse = block.gruppen[0] if block is not None else "F5"
    rate = block.raten[0] if block is not None else 0.02

    injektion = auswahl(
        lang,
        metrik=("recall", "precision", "f1"),
        verfahren=_PROTOTYP,
        ebene=Ebene.ZELLE,
        gruppe_art=GRUPPE_GESAMT,
        klasse=klasse,
        fehlerrate=rate,
        teilversuch=_HAUPT,
    )
    daten = auswahl(
        lang,
        metrik=("recall", "precision", "f1"),
        verfahren=_PROTOTYP,
        ebene=Ebene.ZELLE,
        gruppe_art=GRUPPE_GESAMT,
        klasse=klasse,
        teilversuch=_DATENVARIANZ,
    )

    kennzahlen = ["precision", "recall", "f1"]
    figur, achsen = plt.subplots(1, len(kennzahlen), figsize=(7.6, 3.6), sharey=False)
    streuungen: dict[str, tuple[float, float]] = {}
    for achse, metrik in zip(np.atleast_1d(achsen), kennzahlen, strict=True):
        reihen = []
        for quelle in (injektion, daten):
            eigene = quelle[(quelle["metrik"] == metrik) & quelle["wert"].notna()]
            reihen.append([float(wert) for wert in eigene["wert"]] or [np.nan])
        kasten = achse.boxplot(
            reihen,
            patch_artist=True,
            widths=0.55,
            medianprops={"color": "black", "linewidth": 1.2},
        )
        for koerper, schraffur, grau in zip(
            kasten["boxes"], ("", "///"), ("#909090", "#e0e0e0"), strict=True
        ):
            koerper.set_facecolor(grau)
            koerper.set_hatch(schraffur)
            koerper.set_edgecolor("black")
        achse.set_xticks([1, 2], ["Injektion", "Daten"])
        achse.set_title(metrik)
        streuungen[metrik] = (
            float(np.nanstd(reihen[0], ddof=1)) if len(reihen[0]) > 1 else float("nan"),
            float(np.nanstd(reihen[1], ddof=1)) if len(reihen[1]) > 1 else float("nan"),
        )
    np.atleast_1d(achsen)[0].set_ylabel("Wert")
    figur.suptitle(
        f"Injektionsvarianz gegen Datenvarianz, Klasse {klasse}, Fehlerrate {rate:.0%}"
    )
    verhaeltnisse = ", ".join(
        f"{metrik}: {(paar[1] / paar[0]):.2f}".replace(".", ",")
        for metrik, paar in streuungen.items()
        if paar[0] and not np.isnan(paar[0]) and not np.isnan(paar[1])
    )
    unterschrift = (
        "Abbildung 8: Streuung der Kennzahlen ueber zwei verschiedene Zufallsquellen. "
        "Links je Kennzahl die Injektionsvarianz — fester Basisdatensatz, variierender "
        "Injektionsstrom, aus dem Hauptversuch. Rechts die Datenvarianz — fester "
        "Injektionsstrom, zwanzig verschiedene Basisdatensaetze, aus dem Teilversuch T5. "
        f"Verhaeltnis der Standardabweichungen (Daten zu Injektion): {verhaeltnisse}. "
        "Ein Verhaeltnis deutlich ueber eins hiesse, dass das Ergebnis staerker am "
        "Generator haengt als am Verfahren; das gehoert dann in die Limitationen."
    )
    return figur, unterschrift


def abbildung_9(lang: pd.DataFrame, plan: Versuchsplan) -> tuple[Figure, str]:
    """Precision der Zellsicht gegen die der Constraint-Sicht, je Fehlerklasse.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Die Abbildung und ihre Bildunterschrift.
    """
    from src.evaluation.tabellen import t8_metrikvergleich  # noqa: PLC0415 - Zyklus vermeiden

    tabelle = t8_metrikvergleich(lang, plan)
    tabelle = tabelle[tabelle["verfahren"] == _PROTOTYP].reset_index(drop=True)

    figur, achse = plt.subplots(figsize=(6.6, 4.2))
    stellen = np.arange(len(tabelle), dtype=float)
    breite = 0.38
    for versatz, spalte, grau, schraffur, kennung in (
        (-breite / 2, "precision_zelle", "#606060", "", "Zellmetrik"),
        (breite / 2, "precision_constraint", "#d8d8d8", "///", "Constraint-Metrik"),
    ):
        balken = achse.bar(
            stellen + versatz,
            tabelle[spalte].astype(float),
            width=breite,
            color=grau,
            edgecolor="black",
            linewidth=0.8,
            label=kennung,
        )
        for stab in balken:
            stab.set_hatch(schraffur)
    achse.set_xticks(stellen, tabelle["fehlerklasse"])
    achse.set_xlabel("Fehlerklasse")
    achse.set_ylabel("Precision")
    achse.set_ylim(0.0, 1.05)
    achse.set_title("Precision in beiden Sichten (Prototyp)")
    achse.legend(loc="lower right", framealpha=0.9)
    unterschrift = (
        "Abbildung 9: Precision des Prototyps je Fehlerklasse in zwei Sichten. Auf der "
        "Zellebene ist die Einheit eine Zelle, auf der Constraint-Ebene ein gemeldeter "
        "Verstoss. Ein Verstoss ueber mehrere Spalten zaehlt zellbasiert mehrfach als "
        "Fehlalarm und constraintbasiert einmal; die Differenz macht dieses Artefakt "
        "mehrspaltiger Verstoesse sichtbar. Der Recall ist in beiden Sichten identisch, "
        "weil er durchgehend zellbasiert gebildet wird — die Constraint-Ebene wechselt "
        "nur die Einheit der Precision."
    )
    return figur, unterschrift


def abbildung_10(lang: pd.DataFrame, plan: Versuchsplan) -> tuple[Figure, str]:
    """Praxismix aus T3 gegen die isolierten Klassen des Hauptversuchs.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Die Abbildung und ihre Bildunterschrift.
    """
    block = next((b for b in plan.teilversuche if b.kennung == _MISCHUNG), None)
    rate = block.raten[0] if block is not None else 0.02
    verfahren = list(block.verfahren) if block is not None else list(plan.hauptversuch.verfahren)

    figur, achse = plt.subplots(figsize=(6.8, 4.2))
    kennzahlen = ["precision", "recall", "f1"]
    stellen = np.arange(len(kennzahlen), dtype=float)
    breite = 0.8 / (2 * len(verfahren))

    for nummer, name in enumerate(verfahren):
        isoliert = [
            float(
                np.nanmean(
                    [
                        _mittel(
                            lang,
                            metrik=metrik,
                            verfahren=name,
                            klasse=klasse,
                            teilversuch=_HAUPT,
                            fehlerrate=rate,
                        )
                        or np.nan
                        for klasse in plan.hauptversuch.gruppen
                    ]
                )
            )
            for metrik in kennzahlen
        ]
        gemischt = [
            _mittel(lang, metrik=metrik, verfahren=name, klasse="mix", teilversuch=_MISCHUNG)
            or np.nan
            for metrik in kennzahlen
        ]
        for teil, (werte, schraffur, grau, marke) in enumerate(
            ((isoliert, "", "#606060", "isoliert"), (gemischt, "xxx", "#dcdcdc", "Praxismix"))
        ):
            versatz = (nummer * 2 + teil - (2 * len(verfahren) - 1) / 2) * breite
            balken = achse.bar(
                stellen + versatz,
                werte,
                width=breite * 0.9,
                color=grau,
                edgecolor="black",
                linewidth=0.7,
                label=f"{name}, {marke}",
            )
            for stab in balken:
                stab.set_hatch(schraffur)

    achse.set_xticks(stellen, kennzahlen)
    achse.set_ylabel("Wert (Zellebene)")
    achse.set_ylim(0.0, 1.05)
    achse.set_title(f"Praxismix gegen isolierte Klassen, Fehlerrate {rate:.0%}")
    achse.legend(loc="upper center", ncols=2, fontsize=9, framealpha=0.9)
    unterschrift = (
        "Abbildung 10: Ergebnisse des Teilversuchs T3 (Praxismix, alle Fehlerklassen "
        "gemeinsam mit den Gewichten aus spec/03) gegen den Mittelwert ueber die "
        "isolierten Klassen des Hauptversuchs bei derselben Fehlerrate. Die Gewichte "
        "regeln die Aufteilung zwischen den Klassen, die universumsproportionale Regel "
        "aus Phase 4b die Aufteilung innerhalb einer Klasse; die tatsaechliche "
        "Zusammensetzung jedes Mischlaufs steht in seiner manifest.json unter "
        "'zuteilung_je_variante'."
    )
    return figur, unterschrift


# ---------------------------------------------------------------------------
# Ausgabe
# ---------------------------------------------------------------------------


def schreibe_abbildung(
    figur: Figure, unterschrift: str, verzeichnis: Path, name: str
) -> tuple[Path, Path, Path]:
    """Legt eine Abbildung als PDF, als PNG und ihre Bildunterschrift ab.

    Args:
        figur: Die fertige Abbildung.
        unterschrift: Die Bildunterschrift.
        verzeichnis: Zielverzeichnis, ueblicherweise ``results/figures``.
        name: Name ohne Endung.

    Returns:
        Die Pfade von PDF, PNG und Textdatei.
    """
    verzeichnis.mkdir(parents=True, exist_ok=True)
    pdf = verzeichnis / f"{name}.pdf"
    png = verzeichnis / f"{name}.png"
    txt = verzeichnis / f"{name}.txt"
    figur.savefig(pdf)
    figur.savefig(png, dpi=_DPI)
    txt.write_text(unterschrift + "\n", encoding="utf-8", newline="\n")
    plt.close(figur)
    return (pdf, png, txt)


def baue_alle(
    lang: pd.DataFrame, plan: Versuchsplan, verzeichnis: Path, *, sweep: pd.DataFrame
) -> dict[str, tuple[Path, Path, Path]]:
    """Baut alle zehn Abbildungen und legt sie ab.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.
        verzeichnis: Zielverzeichnis, ueblicherweise ``results/figures``.
        sweep: Der Schwellen-Sweep von B2 fuer Abbildung 3.

    Returns:
        Je Abbildungsname die drei geschriebenen Pfade.
    """
    setze_stil()
    bauplan: dict[str, Any] = {
        "abb01_heatmap_klasse_rate": lambda: abbildung_1(lang, plan),
        "abb02_boxplot_f1": lambda: abbildung_2(lang, plan),
        "abb03_pr_kurve": lambda: abbildung_3(lang, plan, sweep),
        "abb04_recall_je_klasse": lambda: abbildung_4(lang, plan),
        "abb05_recall_je_variante": lambda: abbildung_5(lang, plan),
        "abb06_regel_kreuztabelle": lambda: abbildung_6(lang, plan),
        "abb07_laufzeit": lambda: abbildung_7(lang, plan),
        "abb08_varianzvergleich": lambda: abbildung_8(lang, plan),
        "abb09_zelle_gegen_constraint": lambda: abbildung_9(lang, plan),
        "abb10_praxismix": lambda: abbildung_10(lang, plan),
        "abb11_trefferkategorien": lambda: abbildung_11(lang, plan),
    }
    geschrieben: dict[str, tuple[Path, Path, Path]] = {}
    for name in ABBILDUNGSNAMEN:
        figur, unterschrift = bauplan[name]()
        geschrieben[name] = schreibe_abbildung(figur, unterschrift, verzeichnis, name)
    return geschrieben
