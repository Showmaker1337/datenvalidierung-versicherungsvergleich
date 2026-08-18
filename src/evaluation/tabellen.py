"""Die zehn Ergebnistabellen der Arbeit, je als CSV und als Markdown.

Jede Tabelle entsteht aus ``results/metrics_long.parquet`` — ausser
``t5_frameworkvergleich``, die aus ``results/framework_vergleich.json`` stammt,
weil der Frameworkvergleich kein Experimentlauf ist und nicht in die
Inferenzstatistik eingeht.

Drei Festlegungen, die in jeder Tabelle sichtbar werden
--------------------------------------------------------

**Regeln ohne Treffer bleiben stehen.** ``t3_regeldiagnose`` fuehrt alle Regeln
des Katalogs, auch die, die in keinem Lauf gemeldet haben. Sie sind kein
Darstellungsproblem, sondern das Ergebnis: eine Regel ohne Treffer ist
Ueberdeckung des Katalogs gegenueber der Fehlertaxonomie. Wer sie herausfiltert,
loescht einen Befund. Wie viele es sind, steht nicht vorab fest — es wird
gezaehlt.

**Konfidenzintervalle tragen ihre Herkunft.** Jede Tabelle mit Intervall hat eine
Spalte ``ci_art``. Bei den Held-out-Klassen steht dort ``clopper-pearson``, weil
der Bootstrap dort entartet; das ist der Erwartungsfall und keine Panne.

**Der Schalter ``mitgezogen_als_fehler`` wird nirgends pauschal beschrieben.**
``t10_mitgezogen`` stellt beide Schalterstellungen nebeneinander. Die Richtung
des Effekts ist klassenabhaengig: Bei F8 senkt der Schalter den Recall, bei HO2
hob er ihn vor der Korrektur aus dem dritten Nachtrag der Phase 5. Ein Satz wie
"der Schalter senkt den Recall" waere deshalb falsch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import pandas as pd

from src.evaluation.ergebnisse import (
    GRUPPE_FEHLERKLASSE,
    GRUPPE_GESAMT,
    GRUPPE_REGEL,
    GRUPPE_VARIANTE,
    KREUZ_TRENNER,
    SPALTE_TEILVERSUCH,
    auswahl,
    kreuztabelle_lang,
    mittel_je_wiederholung,
)
from src.evaluation.metriken import clopper_pearson
from src.evaluation.modell import KEINE_FEHLERKLASSE, AuswertungsFehler, Ebene
from src.evaluation.statistik import Intervall, bootstrap_ci
from src.evaluation.varianten import VARIANTENTABELLE, Spiegelung
from src.rules.katalog import KATALOG

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence
    from collections.abc import Set as AbstractSet
    from pathlib import Path

    from src.evaluation.experimentplan import Versuchsplan

__all__ = [
    "TABELLENNAMEN",
    "baue_alle",
    "klassenbloecke",
    "schreibe_tabelle",
]

#: Namen aller Ergebnistabellen in Berichtsreihenfolge.
TABELLENNAMEN: Final[tuple[str, ...]] = (
    "t1_hauptergebnis",
    "t2_fehlerraten",
    "t3_regeldiagnose",
    "t4_varianten",
    "t5_frameworkvergleich",
    "t6_laufzeit",
    "t7_teilversuche",
    "t8_metrikvergleich",
    "t9_gewichtung",
    "t10_mitgezogen",
    "t11_satzebene_hauptversuch",
)

#: Kennungen der Bloecke, wie sie ``config/experiment.yaml`` vergibt.
_HAUPT: Final[str] = "haupt"
_DUPLIKATE: Final[str] = "T1"
_HELDOUT: Final[str] = "T2"
_MISCHUNG: Final[str] = "T3"
_SKALIERUNG: Final[str] = "T4"
_DATENVARIANZ: Final[str] = "T5"
_VARIANTEN: Final[str] = "T6"

#: Das Verfahren, dessen Diagnose berichtet wird.
_PROTOTYP: Final[str] = "prototyp"

#: Kennung einer Regel, die ueber mehrere Entitaeten hinweg prueft.
_ALLE_ENTITAETEN: Final[str] = "alle"

#: Recall, ab dem eine Variante als "ueberwiegend gefunden" gilt.
#:
#: Die Schwelle uebersetzt die **qualitative** Vorabangabe aus ``spec/03``
#: ("spiegelt Regel exakt: ja / teilweise / nein") in eine pruefbare Erwartung an
#: den gemessenen Recall. Die Haelfte ist die einzige Schwelle, die sich ohne
#: Blick auf die Daten begruenden laesst: Sie trennt "ueberwiegend gefunden" von
#: "ueberwiegend uebersehen". Jede andere Zahl waere im Nachhinein gewaehlt.
_SPIEGELUNGSSCHWELLE: Final[float] = 0.5

#: Die beiden Richtungen, in denen die Vorabangabe danebenliegen kann.
#:
#: Sie sind nicht gleichwertig. "Ueberschaetzt" heisst: Die Spezifikation
#: erwartete eine greifende Regel, und der Katalog findet die Variante trotzdem
#: nicht — das schwaecht die Aussage ueber den Katalog. "Unterschaetzt" heisst:
#: Der Katalog findet mehr, als die Taxonomie ihm zutraut; er verallgemeinert
#: ueber die Vorabzuordnung hinaus, und der Kontrast zwischen spiegelnden und
#: nicht spiegelnden Varianten faellt entsprechend kleiner aus.
_UEBERSCHAETZT: Final[str] = "ueberschaetzt"
_UNTERSCHAETZT: Final[str] = "unterschaetzt"

#: Die drei Trefferkategorien einer Injektionsvariante.
#:
#: Die Vorabeinteilung "spiegelt Regel exakt" ist binaer, das Ergebnis ist es
#: nicht. Die Kreuztabelle ``regel_id`` gegen Variante enthaelt bereits, **welche**
#: Regel getroffen hat; daraus folgt eine dritte Kategorie, ohne dass ein
#: einziger Lauf hinzukaeme. Das ist keine Umetikettierung, sondern eine Messung
#: — die Regel-ID steht im Ergebnis und wird nicht neu vergeben.
#:
#: Kategorie B ist der inhaltlich staerkste Einzelbefund, den die Arbeit machen
#: kann: **Eine Variante, die von einer Regel gefangen wird, die nicht gegen sie
#: entworfen wurde, ist das Gegenteil von Zirkularitaet.**
KATEGORIE_A: Final[str] = "A: erkannt durch die zugeordnete Regel"
KATEGORIE_B: Final[str] = "B: erkannt durch eine andere Regel"
KATEGORIE_C: Final[str] = "C: nicht erkannt"

#: Vierte Auspraegung: satzbasierte Varianten sind zellbasiert nicht zuordenbar.
#:
#: F6 und HO1 erzeugen zusaetzliche **Zeilen**; ihr Ground Truth ist satzbasiert,
#: und die Kreuztabelle ``regel_id`` gegen Fehlerklasse ist zellbasiert
#: definiert. Auf der Zellebene hat eine solche Variante keine einzige
#: Wahrheitszelle — jede Meldung dort ist ein Fehlalarm, und die Zuordnung
#: "welche Regel hat den Fehler gefunden" ist schlicht nicht gestellt.
#:
#: Sie deshalb nach C zu sortieren waere **falsch**: F6-a bis F6-c erreichen
#: satzbasiert einen Recall von 1,000. Eine vierte, ausdruecklich benannte
#: Auspraegung ist die einzige ehrliche Darstellung; die Spalte
#: ``meldende_regeln`` nennt dort, welche Regeln in diesen Laeufen ueberhaupt
#: gemeldet haben — eine schwaechere Aussage als "hat den Fehler gefunden", und
#: sie wird als solche gekennzeichnet.
KATEGORIE_SATZ: Final[str] = "S: satzbasiert, zellbasierte Zuordnung nicht definiert"

#: Fehlerklassen, deren Ground Truth satzbasiert ist (spec/03, Abschnitt 4.2).
_SATZBASIERTE_KLASSEN: Final[frozenset[str]] = frozenset({"F6", "HO1"})

#: Die beiden Gruende, aus denen eine Regel in keinem Lauf melden kann.
#:
#: Sie sind **zwei verschiedene Aussagen**: Die erste ist ein Ergebnis ueber das
#: Verhaeltnis von Katalog und Fehlertaxonomie, die zweite eine Limitation des
#: Versuchsaufbaus. Sie in einer Zahl zusammenzufassen waere der haeufigste
#: Fehler bei dieser Kennzahl.
UEBERDECKUNG: Final[str] = (
    "Ueberdeckung: Keine Injektionsvariante zielt auf diese Regel, ihre Felder wurden in "
    "der Serie aber verfaelscht — ohne ihre Bedingung zu verletzen. Der Katalog deckt "
    "mehr ab, als die Fehlertaxonomie adressiert."
)
NICHT_PRUEFBAR: Final[str] = (
    "In diesem Aufbau nicht pruefbar: Die Felder dieser Regel werden von keiner "
    "Injektionsvariante getroffen. Ueber die Regel sagt die Serie nichts — das ist eine "
    "Limitation des Aufbaus und kein Befund ueber den Katalog."
)

#: Spalten von ``t6_laufzeit``.
#:
#: Ausdruecklich aufgezaehlt, damit die Tabelle auch dann ihr Schema traegt, wenn
#: der Teilversuch T4 nicht gerechnet wurde. Ein leerer Datenrahmen ohne Spalten
#: liesse jede darauf aufbauende Abbildung mit einem ``KeyError`` scheitern statt
#: mit der Aussage "dieser Teilversuch fehlt".
_LAUFZEITSPALTEN: Final[tuple[str, ...]] = (
    "verfahren",
    "n_anfragen",
    "zeilen_gesamt",
    "wiederholungen",
    "laufzeit_s",
    "laufzeit_s_je_1000_zeilen",
    "speicher_mb",
    "speicher_mb_je_1000_zeilen",
)


# ---------------------------------------------------------------------------
# Gemeinsame Bausteine
# ---------------------------------------------------------------------------


def _intervall(
    lang: pd.DataFrame,
    plan: Versuchsplan,
    *,
    kennung: str,
    anteil: tuple[int, int] | None = None,
) -> Intervall:
    """Bildet Mittelwert und Konfidenzintervall einer bereits gefilterten Auswahl.

    Args:
        lang: Auf eine Kennzahl, ein Verfahren und eine Gruppe gefilterte Auswahl.
        plan: Der Versuchsplan; liefert alpha, Resamples und Bootstrap-Seed.
        kennung: Bezeichnung der Gruppe; geht in den Zufallsstrom ein.
        anteil: ``(Treffer, Versuche)`` fuer den Ausweichweg bei entartetem
            Bootstrap.

    Returns:
        Das Intervall samt Herkunftsangabe.
    """
    werte = mittel_je_wiederholung(lang)
    return bootstrap_ci(
        [float(wert) for wert in werte],
        alpha=plan.statistik.alpha,
        resamples=plan.statistik.bootstrap_resamples,
        seed=plan.statistik.seed_bootstrap,
        gruppe=kennung,
        anteil=anteil,
    )


def _anteilszahlen(
    lang: pd.DataFrame, *, verfahren: str, klasse: str, teilversuch: str, ebene: Ebene
) -> tuple[int, int] | None:
    """Summiert Treffer und Wahrheitsmenge einer Klasse ueber alle Laeufe.

    Gebraucht wird das nur im Entartungsfall des Bootstrap — dann aber zwingend:
    Ohne diese Zahlen bliebe bei den Held-out-Klassen ein Punkt statt eines
    Intervalls stehen, und genau dort beantwortet das Intervall die
    Forschungsfrage.

    Args:
        lang: Das Langformat.
        verfahren: Das Verfahren.
        klasse: Die Fehlerklasse.
        teilversuch: Die Blockkennung.
        ebene: Die Auswertungsebene.

    Returns:
        ``(tp, tp + fn)``, oder ``None``, wenn die Rohwerte fehlen.
    """
    zahlen: dict[str, float] = {}
    for name in ("tp", "fn"):
        gefiltert = auswahl(
            lang,
            metrik=name,
            verfahren=verfahren,
            ebene=ebene,
            gruppe_art=GRUPPE_GESAMT,
            klasse=klasse,
            teilversuch=teilversuch,
        )
        if gefiltert.empty or gefiltert["wert"].isna().any():
            return None
        zahlen[name] = float(gefiltert["wert"].sum())
    treffer = round(zahlen["tp"])
    versuche = round(zahlen["tp"] + zahlen["fn"])
    if versuche <= 0:
        return None
    return (treffer, versuche)


def _kennzahl_mit_intervall(  # noqa: PLR0913 - jede Angabe waehlt eine eigene Dimension
    lang: pd.DataFrame,
    plan: Versuchsplan,
    *,
    metrik: str,
    verfahren: str,
    klasse: str,
    teilversuch: str,
    ebene: Ebene = Ebene.ZELLE,
    mitgezogen: bool = False,
) -> dict[str, Any]:
    """Bildet eine Kennzahl samt Intervall als flaches Woerterbuch.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.
        metrik: Die Kennzahl.
        verfahren: Das Verfahren.
        klasse: Die Fehlerklasse.
        teilversuch: Die Blockkennung.
        ebene: Die Auswertungsebene.
        mitgezogen: Schalterstellung.

    Returns:
        Die Spalten ``<metrik>``, ``<metrik>_ci_unten``, ``<metrik>_ci_oben`` und
        ``<metrik>_ci_art``; durchgehend ``None``, wenn keine Zeilen vorliegen.
    """
    gefiltert = auswahl(
        lang,
        metrik=metrik,
        verfahren=verfahren,
        ebene=ebene,
        gruppe_art=GRUPPE_GESAMT,
        klasse=klasse,
        teilversuch=teilversuch,
        mitgezogen=mitgezogen,
    )
    if gefiltert.empty or gefiltert["wert"].isna().all():
        return {
            metrik: None,
            f"{metrik}_ci_unten": None,
            f"{metrik}_ci_oben": None,
            f"{metrik}_ci_art": "nicht auswertbar",
        }
    anteil = (
        _anteilszahlen(
            lang, verfahren=verfahren, klasse=klasse, teilversuch=teilversuch, ebene=ebene
        )
        if metrik == "recall"
        else None
    )
    intervall = _intervall(
        gefiltert, plan, kennung=f"{verfahren}|{klasse}|{metrik}|{ebene}", anteil=anteil
    )
    return {
        metrik: intervall.punkt,
        f"{metrik}_ci_unten": intervall.unten,
        f"{metrik}_ci_oben": intervall.oben,
        f"{metrik}_ci_art": intervall.art.value,
    }


def _bloecke_je_klasse(plan: Versuchsplan) -> list[tuple[str, str, Ebene]]:
    """Listet die Klassen der Ergebnistabellen mit ihrem Block und ihrer Ebene.

    F6 und HO1 sind **satzbasiert**: Beide erzeugen zusaetzliche Zeilen, und ein
    zellbasierter Ground Truth ist dort undefiniert (``spec/03``, Abschnitt 4.2).
    Ihre Kennzahlen stehen deshalb auf der Satzebene, und die Tabelle weist die
    Ebene je Zeile aus, statt zwei verschiedene Einheiten stillschweigend
    untereinander zu schreiben.

    Args:
        plan: Der Versuchsplan.

    Returns:
        Je Klasse ein Tripel aus Klasse, Blockkennung und Ebene.
    """
    eintraege: list[tuple[str, str, Ebene]] = [
        (klasse, _HAUPT, Ebene.ZELLE) for klasse in plan.hauptversuch.gruppen
    ]
    for block in plan.teilversuche:
        if block.kennung == _DUPLIKATE:
            eintraege += [(klasse, block.kennung, Ebene.SATZ) for klasse in block.gruppen]
        elif block.kennung == _HELDOUT:
            eintraege += [
                (klasse, block.kennung, Ebene.SATZ if klasse == "HO1" else Ebene.ZELLE)
                for klasse in block.gruppen
            ]
    return eintraege


# ---------------------------------------------------------------------------
# t1 bis t10
# ---------------------------------------------------------------------------


def t1_hauptergebnis(lang: pd.DataFrame, plan: Versuchsplan) -> pd.DataFrame:
    """Baut ``t1_hauptergebnis``: Precision, Recall und F1 je Verfahren und Klasse.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Eine Zeile je Verfahren und Fehlerklasse.
    """
    zeilen: list[dict[str, Any]] = []
    for klasse, block, ebene in _bloecke_je_klasse(plan):
        for verfahren in _verfahren_des_blocks(plan, block):
            zeile: dict[str, Any] = {
                "verfahren": verfahren,
                "fehlerklasse": klasse,
                "teilversuch": block,
                "ebene": ebene.value,
            }
            for metrik in ("precision", "recall", "f1"):
                zeile.update(
                    _kennzahl_mit_intervall(
                        lang,
                        plan,
                        metrik=metrik,
                        verfahren=verfahren,
                        klasse=klasse,
                        teilversuch=block,
                        ebene=ebene,
                    )
                )
            zeilen.append(zeile)
    return pd.DataFrame(zeilen)


def _verfahren_des_blocks(plan: Versuchsplan, kennung: str) -> tuple[str, ...]:
    """Gibt die Verfahren eines Blocks zurueck."""
    for block in plan.bloecke:
        if block.kennung == kennung:
            return block.verfahren
    raise AuswertungsFehler(f"Unbekannter Block: {kennung!r}.")


def t2_fehlerraten(lang: pd.DataFrame, plan: Versuchsplan) -> pd.DataFrame:
    """Baut ``t2_fehlerraten``: F1, MCC und Precision ueber die Ratenstufen.

    Die Precision steht **zweimal** darin, einmal je Metrikebene. Das ist der
    Kern der Antwort auf HYP3: Auf der Zellebene erzeugt jede Injektion ueber
    mehrspaltige Regeln zusaetzliche Scheinfehlalarme, deren Zahl mit der
    Injektionszahl waechst; auf der Constraint-Ebene zaehlt dieselbe Meldung
    einmal. Ein Trend, der nur auf der Zellebene besteht, ist ein Effekt der
    Berichtskonvention und keiner des Verfahrens — und das sieht man erst, wenn
    beide Spalten nebeneinander stehen.

    Die PR-AUC steht nur bei B2, und das ist kein Versehen: Der Prototyp, B0 und
    B3 liefern binaere Entscheidungen und damit genau **einen** Punkt im PR-Raum.
    Fuer sie wird kein Pseudo-Score erfunden.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Eine Zeile je Verfahren und Fehlerrate.
    """
    zeilen: list[dict[str, Any]] = []
    for verfahren in plan.hauptversuch.verfahren:
        for rate in sorted(plan.hauptversuch.raten):
            zeile: dict[str, Any] = {"verfahren": verfahren, "fehlerrate": rate}
            for metrik in ("f1", "mcc", "pr_auc"):
                zeile.update(
                    _rate_kennzahl(lang, plan, metrik=metrik, verfahren=verfahren, rate=rate)
                )
            for ebene, kuerzel in ((Ebene.ZELLE, "zelle"), (Ebene.CONSTRAINT, "constraint")):
                werte = _rate_kennzahl(
                    lang, plan, metrik="precision", verfahren=verfahren, rate=rate, ebene=ebene
                )
                for name, wert in werte.items():
                    zeile[name.replace("precision", f"precision_{kuerzel}")] = wert
            zelle = zeile.get("precision_zelle")
            constraint = zeile.get("precision_constraint")
            zeile["precision_differenz"] = (
                None if zelle is None or constraint is None else constraint - zelle
            )
            zeilen.append(zeile)
    return pd.DataFrame(zeilen)


def _rate_kennzahl(  # noqa: PLR0913 - jede Angabe waehlt eine eigene Dimension
    lang: pd.DataFrame,
    plan: Versuchsplan,
    *,
    metrik: str,
    verfahren: str,
    rate: float,
    ebene: Ebene = Ebene.ZELLE,
) -> dict[str, Any]:
    """Bildet eine Kennzahl je Ratenstufe samt Intervall.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.
        metrik: Die Kennzahl.
        verfahren: Das Verfahren.
        rate: Die Fehlerrate.
        ebene: Die Auswertungsebene.

    Returns:
        Die Spalten ``<metrik>``, ``<metrik>_ci_unten`` und ``<metrik>_ci_oben``.
    """
    gefiltert = auswahl(
        lang,
        metrik=metrik,
        verfahren=verfahren,
        ebene=ebene,
        gruppe_art=GRUPPE_GESAMT,
        fehlerrate=rate,
        teilversuch=_HAUPT,
    )
    gefiltert = gefiltert[gefiltert["wert"].notna()]
    if gefiltert.empty:
        return {metrik: None, f"{metrik}_ci_unten": None, f"{metrik}_ci_oben": None}
    intervall = _intervall(
        gefiltert, plan, kennung=f"{verfahren}|rate{rate}|{metrik}|{ebene.value}"
    )
    return {
        metrik: intervall.punkt,
        f"{metrik}_ci_unten": intervall.unten,
        f"{metrik}_ci_oben": intervall.oben,
    }


def klassenbloecke(plan: Versuchsplan) -> tuple[str, ...]:
    """Gibt die Bloecke zurueck, die eine ganze Fehlerklasse injizieren.

    Die Regeldiagnose und die Kreuztabelle Regel gegen Fehlerklasse beziehen sich
    auf diese Bloecke: Hauptversuch, Duplikate, Held-out und Praxismix. **Nicht**
    dabei sind der Skalierungsversuch T4 — er variiert die Datensatzgroesse und
    haette dieselbe Klasse mit anderem Gewicht in der Summe — und die
    Variantencharakterisierung T6, die je Lauf nur **eine** Variante injiziert und
    damit die Trefferverteilung ueber die Regeln systematisch verschoebe.

    Args:
        plan: Der Versuchsplan.

    Returns:
        Die Blockkennungen, jede genau einmal, in Planreihenfolge.
    """
    gewuenscht = (_HAUPT, _DUPLIKATE, _HELDOUT, _MISCHUNG)
    return tuple(
        kennung for kennung in gewuenscht if any(b.kennung == kennung for b in plan.bloecke)
    )


def t3_regeldiagnose(
    lang: pd.DataFrame, plan: Versuchsplan, *, injizierte_spalten: AbstractSet[tuple[str, str]]
) -> pd.DataFrame:
    """Baut ``t3_regeldiagnose``: Treffer, Precision und Alleinstellung je Regel.

    **Alle** Regeln des Katalogs stehen in der Tabelle, auch die ohne einen
    einzigen Treffer. Eine Regel ohne Treffer ist Ueberdeckung des Katalogs
    gegenueber der Fehlertaxonomie und damit ein Ergebnis; wer sie herausfiltert,
    loescht es. Wie viele es sind, wird gezaehlt und nicht vorab behauptet.

    Eine Regel ohne Treffer bekommt einen **Grund**, und die beiden moeglichen
    Gruende sind zwei verschiedene Aussagen:

    ``Ueberdeckung``
        Keine Injektionsvariante zielt auf die Regel, und ihre Felder wurden in
        der Serie trotzdem verfaelscht — ohne dass ihre Bedingung verletzt wurde.
        Der Katalog deckt damit mehr ab, als die Fehlertaxonomie adressiert. Das
        ist ein **Ergebnis** ueber das Verhaeltnis von Katalog und Taxonomie.
    ``in diesem Aufbau nicht pruefbar``
        Die Felder der Regel werden von **keiner** Injektion getroffen. Ueber die
        Regel sagt die Serie dann nichts — sie ist eine **Limitation** des
        Aufbaus und kein Befund ueber den Katalog.

    Die Unterscheidung wird nicht behauptet, sondern aus den Ground-Truth-Logs
    abgeleitet: ``injizierte_spalten`` enthaelt jedes ``(entitaet, spalte)``-Paar,
    das in irgendeinem Lauf der Serie verfaelscht wurde.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.
        injizierte_spalten: Alle in der Serie verfaelschten ``(entitaet,
            spalte)``-Paare, aus den ``error_log``-Dateien gesammelt.

    Returns:
        Eine Zeile je Regel des Katalogs.
    """
    gezielt = {
        regel_id for bezug in VARIANTENTABELLE for regel_id in bezug.erwartete_regeln
    }
    diagnose = auswahl(
        lang,
        verfahren=_PROTOTYP,
        ebene=Ebene.ZELLE,
        gruppe_art=GRUPPE_REGEL,
        metrik=("meldungen", "tp", "precision", "anteil_einzige_regel"),
        teilversuch=klassenbloecke(plan),
    )
    diagnose = diagnose[~diagnose["gruppe"].str.contains(KREUZ_TRENNER, regex=False)]

    summen = (
        diagnose[diagnose["metrik"].isin(["meldungen", "tp"])]
        .pivot_table(index="gruppe", columns="metrik", values="wert", aggfunc="sum")
        .reindex(columns=["meldungen", "tp"])
        .fillna(0.0)
    )
    mittel = (
        diagnose[diagnose["metrik"] == "anteil_einzige_regel"]
        .groupby("gruppe", observed=True)["wert"]
        .mean()
    )
    laeufe = (
        diagnose[diagnose["metrik"] == "meldungen"]
        .groupby("gruppe", observed=True)["run_id"]
        .nunique()
    )

    zeilen: list[dict[str, Any]] = []
    for regel in KATALOG:
        meldungen = float(summen["meldungen"].get(regel.regel_id, 0.0))
        treffer = float(summen["tp"].get(regel.regel_id, 0.0))
        zielt = regel.regel_id in gezielt
        getroffen = _felder_verfaelscht(regel, injizierte_spalten)
        zeilen.append(
            {
                "regel_id": regel.regel_id,
                "gruppe": regel.regel_id[:3],
                "entitaet": regel.entitaet,
                "laeufe_mit_meldung": int(laeufe.get(regel.regel_id, 0)),
                "meldungen_gesamt": int(meldungen),
                "treffer_gesamt": int(treffer),
                "precision": (treffer / meldungen) if meldungen else None,
                "anteil_einzige_regel": (
                    float(mittel[regel.regel_id]) if regel.regel_id in mittel.index else None
                ),
                "ohne_treffer": meldungen == 0,
                "zielt_eine_variante_darauf": zielt,
                "felder_wurden_verfaelscht": getroffen,
                "grund_ohne_treffer": _grund_ohne_treffer(
                    stumm=meldungen == 0, zielt=zielt, getroffen=getroffen
                ),
            }
        )
    tabelle = pd.DataFrame(zeilen)
    stumm = tabelle["ohne_treffer"]
    tabelle.attrs["regeln_ohne_meldung"] = int(stumm.sum())
    tabelle.attrs["regeln_gesamt"] = len(KATALOG)
    tabelle.attrs["ueberdeckung"] = sorted(
        tabelle.loc[stumm & (tabelle["grund_ohne_treffer"] == UEBERDECKUNG), "regel_id"]
    )
    tabelle.attrs["nicht_pruefbar"] = sorted(
        tabelle.loc[stumm & (tabelle["grund_ohne_treffer"] == NICHT_PRUEFBAR), "regel_id"]
    )
    return tabelle


def _felder_verfaelscht(
    regel: object, injizierte_spalten: AbstractSet[tuple[str, str]]
) -> bool:
    """Prueft, ob mindestens ein Feld einer Regel in der Serie verfaelscht wurde.

    Regeln ueber mehrere Entitaeten tragen ``entitaet = "alle"``; fuer sie wird
    geprueft, ob die Spalte in **irgendeiner** Entitaet getroffen wurde.

    Args:
        regel: Die Regel des Katalogs.
        injizierte_spalten: Alle verfaelschten ``(entitaet, spalte)``-Paare.

    Returns:
        ``True``, wenn mindestens ein Feld der Regel getroffen wurde.
    """
    entitaet = str(getattr(regel, "entitaet", ""))
    spalten = tuple(getattr(regel, "spalten", ()))
    if entitaet == _ALLE_ENTITAETEN:
        getroffene_spalten = {spalte for _, spalte in injizierte_spalten}
        return any(spalte in getroffene_spalten for spalte in spalten)
    return any((entitaet, spalte) in injizierte_spalten for spalte in spalten)


def _grund_ohne_treffer(*, stumm: bool, zielt: bool, getroffen: bool) -> str:
    """Benennt, warum eine Regel in keinem Lauf gemeldet hat.

    Args:
        stumm: Ob die Regel ueberhaupt keine Meldung abgegeben hat.
        zielt: Ob eine Injektionsvariante auf sie zielt.
        getroffen: Ob mindestens eines ihrer Felder verfaelscht wurde.

    Returns:
        Den Grund als Text; leer, wenn die Regel gemeldet hat.
    """
    if not stumm:
        return ""
    if zielt:
        return (
            "Eine Injektionsvariante zielt auf diese Regel, und sie meldet dennoch nicht. "
            "Das ist weder Ueberdeckung noch Limitation, sondern ein Befund, der zu "
            "pruefen ist."
        )
    if getroffen:
        return UEBERDECKUNG
    return NICHT_PRUEFBAR


def t4_varianten(lang: pd.DataFrame, plan: Versuchsplan) -> pd.DataFrame:
    """Baut ``t4_varianten``: Recall je Injektionsvariante aus dem Teilversuch T6.

    **Nicht** aus dem faktoriellen Plan. Dort gibt die proportionale Zuteilung
    knappen Varianten einstellige Fallzahlen — F4-f bekommt bei zwei Prozent eine
    einzige Injektion. Ein Recall aus n = 1 gehoert in keine Tabelle. Im
    Variantenmodus schoepft jede Variante ihr Universum aus (gedeckelt durch
    ``max_fehler``), und das Clopper-Pearson-Intervall wird belastbar.

    Die fuenf Wiederholungen sind **Replikate**, keine Vergroesserung der
    Stichprobe: Bei Varianten, deren Universum unterhalb der Deckelung liegt,
    injizieren alle fuenf dieselben Zellen. Berichtet wird deshalb das Mittel
    ueber die Wiederholungen und nicht ihre Summe — sonst waere ``n`` bei diesen
    Varianten fuenfmal zu gross und das Intervall entsprechend zu eng.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Eine Zeile je Injektionsvariante.
    """
    quelle = auswahl(
        lang,
        verfahren=_PROTOTYP,
        gruppe_art=GRUPPE_VARIANTE,
        metrik=("recall", "tp"),
        teilversuch=_VARIANTEN,
    )
    treffende_regeln = _treffende_regeln(lang, nur_treffer=True)
    meldende_regeln = _treffende_regeln(lang, nur_treffer=False)
    zeilen: list[dict[str, Any]] = []
    for bezug in VARIANTENTABELLE:
        ebene = Ebene.SATZ if bezug.fehlerklasse in ("F6", "HO1") else Ebene.ZELLE
        eigene = quelle[
            (quelle["gruppe"] == bezug.variante_id) & (quelle["ebene"] == ebene.value)
        ]
        treffer = eigene[eigene["metrik"] == "tp"]
        zeile: dict[str, Any] = {
            "variante": bezug.variante_id,
            "fehlerklasse": bezug.fehlerklasse,
            "ebene": ebene.value,
            "spiegelt_regel_exakt": bezug.spiegelung.value,
            "erwartet_unentdeckt": bezug.erwartet_unentdeckt,
            "erwartete_regeln": ", ".join(bezug.erwartete_regeln),
            "anmerkung": bezug.anmerkung,
        }
        if treffer.empty:
            zeile.update(
                {
                    "n": 0,
                    "tp": 0,
                    "recall": None,
                    "ci_unten": None,
                    "ci_oben": None,
                    "wiederholungen": 0,
                    "erwartung_eingetroffen": None,
                    "abweichungsrichtung": "",
                    "treffende_regeln": "",
                    "meldende_regeln": "",
                    "trefferkategorie": "",
                }
            )
        else:
            wiederholungen = int(treffer["run_id"].nunique())
            fallzahl = round(float(treffer["n"].fillna(0).mean()))
            gefunden = round(float(treffer["wert"].mean()))
            unten, oben = clopper_pearson(gefunden, fallzahl, alpha=plan.statistik.alpha)
            recall = (gefunden / fallzahl) if fallzahl else None
            eingetroffen, richtung = _erwartung_geprueft(bezug.spiegelung, recall)
            satzbasiert = bezug.fehlerklasse in _SATZBASIERTE_KLASSEN
            getroffen = treffende_regeln.get(bezug.variante_id, ())
            zeile["treffende_regeln"] = ", ".join(getroffen)
            zeile["meldende_regeln"] = ", ".join(meldende_regeln.get(bezug.variante_id, ()))
            zeile["trefferkategorie"] = _trefferkategorie(
                erwartete=bezug.erwartete_regeln,
                getroffene=getroffen,
                treffer=gefunden,
                satzbasiert=satzbasiert,
            )
            zeile.update(
                {
                    "n": fallzahl,
                    "tp": gefunden,
                    "recall": recall,
                    "ci_unten": unten,
                    "ci_oben": oben,
                    "wiederholungen": wiederholungen,
                    "erwartung_eingetroffen": eingetroffen,
                    "abweichungsrichtung": richtung,
                }
            )
        zeilen.append(zeile)
    tabelle = pd.DataFrame(zeilen)
    geprueft = tabelle[tabelle["erwartung_eingetroffen"].notna()]
    tabelle.attrs["vorab_geprueft"] = len(geprueft)
    tabelle.attrs["vorab_eingetroffen"] = int(geprueft["erwartung_eingetroffen"].sum())
    tabelle.attrs["vorab_ueberschaetzt"] = sorted(
        geprueft.loc[geprueft["abweichungsrichtung"] == _UEBERSCHAETZT, "variante"]
    )
    tabelle.attrs["vorab_unterschaetzt"] = sorted(
        geprueft.loc[geprueft["abweichungsrichtung"] == _UNTERSCHAETZT, "variante"]
    )
    tabelle.attrs["trefferkategorien"] = {
        kategorie: int((geprueft["trefferkategorie"] == kategorie).sum())
        for kategorie in (KATEGORIE_A, KATEGORIE_B, KATEGORIE_C, KATEGORIE_SATZ)
    }
    tabelle.attrs["kategorie_b_varianten"] = sorted(
        geprueft.loc[geprueft["trefferkategorie"] == KATEGORIE_B, "variante"]
    )
    return tabelle


def _treffende_regeln(lang: pd.DataFrame, *, nur_treffer: bool) -> dict[str, tuple[str, ...]]:
    """Liest je Injektionsvariante die Regeln, die auf ihr gemeldet haben.

    Quelle ist die Kreuztabelle ``regel_id`` gegen Fehlerklasse aus dem
    Teilversuch T6. Dort injiziert jeder Lauf genau **eine** Variante; eine
    Kreuztabellenzeile mit einer echten Fehlerklasse ist damit ein Treffer auf
    genau dieser Variante.

    Args:
        lang: Das Langformat.
        nur_treffer: ``True`` zaehlt nur Zeilen mit einer echten Fehlerklasse —
            also **Treffer**. ``False`` zaehlt jede Meldung, auch die mit
            :data:`~src.evaluation.modell.KEINE_FEHLERKLASSE`. Der zweite Fall
            wird nur fuer die satzbasierten Varianten gebraucht: Dort hat die
            Zellebene keine Wahrheitszelle, jede Zellmeldung ist zellbasiert ein
            Fehlalarm, und trotzdem ist es genau diese Regel, die den Satzfehler
            findet. Die schwaechere Aussage "hat gemeldet" wird deshalb getrennt
            gefuehrt und in der Tabelle auch so benannt.

    Returns:
        Je Variantenkennung die Regeln, nach Trefferzahl absteigend.
    """
    kreuz = kreuztabelle_lang(lang)
    kreuz = kreuz[
        (kreuz["verfahren"] == _PROTOTYP)
        & (kreuz[SPALTE_TEILVERSUCH] == _VARIANTEN)
        & (kreuz["treffer"] > 0)
        & kreuz["variante"].notna()
    ]
    if nur_treffer:
        kreuz = kreuz[kreuz["fehlerklasse"] != KEINE_FEHLERKLASSE]
    if kreuz.empty:
        return {}
    verdichtet = (
        kreuz.groupby(["variante", "regel_id"], observed=True)["treffer"].sum().reset_index()
    )
    verdichtet = verdichtet.sort_values(["variante", "treffer"], ascending=[True, False])
    return {
        str(variante): tuple(str(regel) for regel in gruppe["regel_id"])
        for variante, gruppe in verdichtet.groupby("variante", observed=True)
    }


def _trefferkategorie(
    *,
    erwartete: Sequence[str],
    getroffene: Sequence[str],
    treffer: int,
    satzbasiert: bool,
) -> str:
    """Ordnet eine Variante einer der vier Trefferkategorien zu.

    Args:
        erwartete: Regeln, die ``spec/03`` der Variante zuordnet.
        getroffene: Regeln, die auf ihr tatsaechlich getroffen haben.
        treffer: Zahl der gefundenen Wahrheitseinheiten.
        satzbasiert: Ob die Fehlerklasse satzbasiert ausgewertet wird.

    Returns:
        :data:`KATEGORIE_A`, :data:`KATEGORIE_B`, :data:`KATEGORIE_C` oder
        :data:`KATEGORIE_SATZ`.
    """
    if satzbasiert:
        return KATEGORIE_SATZ
    if treffer <= 0 or not getroffene:
        return KATEGORIE_C
    if set(erwartete) & set(getroffene):
        return KATEGORIE_A
    return KATEGORIE_B


def _erwartung_geprueft(
    spiegelung: Spiegelung, recall: float | None
) -> tuple[bool | None, str]:
    """Prueft die Vorabangabe aus ``spec/03`` gegen den gemessenen Recall.

    Die Angabe "spiegelt Regel exakt" wurde **vor** der Messung formuliert. Sie
    ist damit eine falsifizierbare Erwartung und keine Beschreibung der Daten —
    und genau deshalb ist ihre Trefferquote eine Guetezahl der Methode und kein
    Makel der Spezifikation, wo sie danebenliegt.

    Uebersetzt wird sie ueber :data:`_SPIEGELUNGSSCHWELLE`:

    ``ja``
        erwartet einen ueberwiegend gefundenen Fehler.
    ``nein``
        erwartet einen ueberwiegend uebersehenen Fehler.
    ``teilweise``
        erwartet einen Zwischenwert — weder vollstaendig gefunden noch gar nicht.

    Args:
        spiegelung: Die Vorabeinstufung.
        recall: Der gemessene Recall; ``None`` ohne Messung.

    Returns:
        Ob die Erwartung eingetroffen ist, und in welche Richtung sie sonst
        danebenlag.
    """
    if recall is None:
        return (None, "")
    if spiegelung is Spiegelung.JA:
        return (True, "") if recall >= _SPIEGELUNGSSCHWELLE else (False, _UEBERSCHAETZT)
    if spiegelung is Spiegelung.NEIN:
        return (True, "") if recall < _SPIEGELUNGSSCHWELLE else (False, _UNTERSCHAETZT)
    if 0.0 < recall < 1.0:
        return (True, "")
    return (False, _UNTERSCHAETZT if recall >= 1.0 else _UEBERSCHAETZT)


def t5_frameworkvergleich(pfad: Path) -> pd.DataFrame:
    """Baut ``t5_frameworkvergleich`` aus ``results/framework_vergleich.json``.

    Beide Frameworks gehen **nicht** in die Inferenzstatistik ein: B3 fuehrt
    inhaltlich dieselben Regeln aus wie der Prototyp, ein Test dagegen pruefte
    eine Nullhypothese, von der man weiss, dass sie gilt. Verglichen werden
    Ausdrueckbarkeit, Codezeilen, Laufzeit und Diagnoseguete.

    Die Lokalisierungsaussage ist eine **cuallee**-Eigenschaft und keine der
    Gattung: Great Expectations liefert mit ``unexpected_index_list`` Zeile und
    Ausgangswert. Die Tabelle fuehrt beide Frameworks deshalb als eigene Spalten.

    Args:
        pfad: Pfad von ``results/framework_vergleich.json``.

    Returns:
        Eine Zeile je Vergleichsmerkmal.

    Raises:
        AuswertungsFehler: Wenn die Datei fehlt.
    """
    import json  # noqa: PLC0415 - Importkosten nur bei Bedarf

    if not pfad.is_file():
        raise AuswertungsFehler(
            f"Der Frameworkvergleich fehlt: {pfad}. Er entsteht mit "
            "'python scripts/framework_vergleich.py'."
        )
    inhalt = json.loads(pfad.read_text(encoding="utf-8"))
    cuallee = inhalt["cuallee"]
    great = inhalt["great_expectations"]
    diagnose = inhalt["diagnoseguete"]

    def _guete(framework: str, merkmal: str) -> str:
        return "ja" if diagnose[framework][merkmal] else "nein"

    zeilen = [
        {
            "merkmal": "Anteil ausdrueckbarer Regeln (G1, vorgelegte Auswahl)",
            "cuallee": cuallee["anteil_ausdrueckbarer_regeln"]["g1"],
            "great_expectations": great["anteil_ausdrueckbar_g1"],
            "einheit": "Anteil",
        },
        {
            "merkmal": "Anteil ausdrueckbarer Regeln (ganzer Katalog)",
            "cuallee": cuallee["anteil_ausdrueckbarer_regeln"]["katalog"],
            "great_expectations": None,
            "einheit": "Anteil",
        },
        {
            "merkmal": "Anteil ausdrueckbarer Regeln (G3, relational)",
            "cuallee": inhalt["anteil_ausdrueckbar"]["cuallee_auf_den_g3_regeln"],
            "great_expectations": great["anteil_ausdrueckbar_g3"],
            "einheit": "Anteil",
        },
        {
            "merkmal": "Codezeilen je Regel, Summe ueber die verglichenen Regeln",
            "cuallee": cuallee["codezeilen_je_regel"]["summe_framework"],
            "great_expectations": great["codezeilen_summe"],
            "einheit": "Zeilen",
        },
        {
            "merkmal": "Codezeilen je Regel, Prototyp zum Vergleich",
            "cuallee": cuallee["codezeilen_je_regel"]["summe_prototyp"],
            "great_expectations": None,
            "einheit": "Zeilen",
        },
        {
            "merkmal": "Laufzeit",
            "cuallee": cuallee["laufzeit_s"],
            "great_expectations": great["laufzeit_s"],
            "einheit": "Sekunden",
        },
        *[
            {
                "merkmal": f"Diagnoseguete: {merkmal}",
                "cuallee": _guete("cuallee", merkmal),
                "great_expectations": _guete("great_expectations", merkmal),
                "einheit": "ja/nein",
            }
            for merkmal in ("regel", "spalte", "zeile", "ausgangswert", "anzahl_verstoesse")
        ],
        {
            "merkmal": "geht in die Inferenzstatistik ein",
            "cuallee": "nein",
            "great_expectations": "nein",
            "einheit": "ja/nein",
        },
    ]
    tabelle = pd.DataFrame(zeilen)
    tabelle.attrs["lesehinweis"] = inhalt["lesehinweis"]
    return tabelle


def t6_laufzeit(lang: pd.DataFrame, plan: Versuchsplan) -> pd.DataFrame:
    """Baut ``t6_laufzeit``: Laufzeit und Speicher, normiert auf 1.000 Zeilen.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Eine Zeile je Verfahren und Datensatzgroesse.
    """
    groessen = {
        block.design: block.n_anfragen
        for block in plan.teilversuche
        if block.kennung == _SKALIERUNG
    }
    quelle = auswahl(
        lang,
        gruppe_art=GRUPPE_GESAMT,
        metrik=(
            "laufzeit_s",
            "laufzeit_s_je_1000_zeilen",
            "speicher_mb",
            "speicher_mb_je_1000_zeilen",
        ),
        mitgezogen=None,
        teilversuch=_SKALIERUNG,
    )
    zeilen: list[dict[str, Any]] = []
    for design, anfragen in sorted(groessen.items(), key=lambda eintrag: eintrag[1]):
        eigene = quelle[quelle["design"] == design]
        for verfahren in sorted(eigene["verfahren"].dropna().unique()):
            teil = eigene[eigene["verfahren"] == verfahren]
            zeile: dict[str, Any] = {
                "verfahren": verfahren,
                "n_anfragen": anfragen,
                "zeilen_gesamt": int(teil["n"].dropna().max()) if teil["n"].notna().any() else None,
                "wiederholungen": int(teil["run_id"].nunique()),
            }
            for metrik in (
                "laufzeit_s",
                "laufzeit_s_je_1000_zeilen",
                "speicher_mb",
                "speicher_mb_je_1000_zeilen",
            ):
                werte = teil.loc[teil["metrik"] == metrik, "wert"].dropna()
                zeile[metrik] = float(werte.mean()) if not werte.empty else None
            zeilen.append(zeile)
    return pd.DataFrame(zeilen, columns=_LAUFZEITSPALTEN)


def t7_teilversuche(lang: pd.DataFrame, plan: Versuchsplan) -> pd.DataFrame:
    """Baut ``t7_teilversuche``: Ergebnisse aus T1 bis T5 im Ueberblick.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Eine Zeile je Teilversuch und Gruppe.
    """
    ebenen = {
        _DUPLIKATE: Ebene.SATZ,
        _HELDOUT: Ebene.ZELLE,
        _MISCHUNG: Ebene.ZELLE,
        _DATENVARIANZ: Ebene.ZELLE,
    }
    zeilen: list[dict[str, Any]] = []
    for block in plan.teilversuche:
        if block.kennung not in ebenen:
            continue
        for gruppe in block.gruppen:
            ebene = Ebene.SATZ if gruppe == "HO1" else ebenen[block.kennung]
            for verfahren in block.verfahren:
                zeile: dict[str, Any] = {
                    "teilversuch": block.kennung,
                    "titel": block.titel,
                    "gruppe": gruppe,
                    "verfahren": verfahren,
                    "ebene": ebene.value,
                    "wiederholungen": block.wiederholungen,
                }
                for metrik in ("precision", "recall", "f1"):
                    zeile.update(
                        _kennzahl_mit_intervall(
                            lang,
                            plan,
                            metrik=metrik,
                            verfahren=verfahren,
                            klasse=gruppe,
                            teilversuch=block.kennung,
                            ebene=ebene,
                        )
                    )
                zeilen.append(zeile)
    return pd.DataFrame(zeilen)


def t8_metrikvergleich(lang: pd.DataFrame, plan: Versuchsplan) -> pd.DataFrame:
    """Baut ``t8_metrikvergleich``: Zellmetrik gegen Constraint-Metrik.

    Auf der Constraint-Ebene ist die Einheit ein gemeldeter Verstoss statt einer
    Zelle. Der Unterschied betrifft **nur die Precision**: Ein Verstoss ueber
    mehrere Spalten zaehlt zellbasiert mehrfach als Fehlalarm, constraintbasiert
    einmal. Der Recall bleibt in beiden Sichten zellbasiert und damit gleich —
    genau deshalb stehen beide Zahlen nebeneinander.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Eine Zeile je Verfahren und Fehlerklasse.
    """
    zeilen: list[dict[str, Any]] = []
    for klasse in plan.hauptversuch.gruppen:
        for verfahren in plan.hauptversuch.verfahren:
            zeile: dict[str, Any] = {"verfahren": verfahren, "fehlerklasse": klasse}
            for ebene, kuerzel in ((Ebene.ZELLE, "zelle"), (Ebene.CONSTRAINT, "constraint")):
                for metrik in ("precision", "recall"):
                    werte = _kennzahl_mit_intervall(
                        lang,
                        plan,
                        metrik=metrik,
                        verfahren=verfahren,
                        klasse=klasse,
                        teilversuch=_HAUPT,
                        ebene=ebene,
                    )
                    zeile[f"{metrik}_{kuerzel}"] = werte[metrik]
            precision_zelle = zeile.get("precision_zelle")
            precision_constraint = zeile.get("precision_constraint")
            zeile["precision_differenz"] = (
                None
                if precision_zelle is None or precision_constraint is None
                else precision_constraint - precision_zelle
            )
            zeilen.append(zeile)
    return pd.DataFrame(zeilen)


def t9_gewichtung(lang: pd.DataFrame, plan: Versuchsplan) -> pd.DataFrame:
    """Baut ``t9_gewichtung``: Klassen-Recall zellgewichtet gegen variantengewichtet.

    Der zellgewichtete Klassenrecall zaehlt jede verfaelschte Zelle gleich; er
    wird damit von den haeufigen Varianten beherrscht. Der variantengewichtete
    mittelt ueber die Varianten und gibt jeder dasselbe Gewicht. Die Differenz
    zeigt, wie stark der Klassenwert von der Zusammensetzung abhaengt — und damit,
    wie vorsichtig ein Klassenrecall zu lesen ist.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Eine Zeile je Fehlerklasse.
    """
    zeilen: list[dict[str, Any]] = []
    for klasse in plan.hauptversuch.gruppen:
        zellgewichtet = auswahl(
            lang,
            metrik="recall",
            verfahren=_PROTOTYP,
            ebene=Ebene.ZELLE,
            gruppe_art=GRUPPE_FEHLERKLASSE,
            gruppe=klasse,
            teilversuch=_HAUPT,
        )
        variantengewichtet = auswahl(
            lang,
            metrik="recall_variantengewichtet",
            verfahren=_PROTOTYP,
            ebene=Ebene.ZELLE,
            gruppe_art=GRUPPE_FEHLERKLASSE,
            gruppe=klasse,
            teilversuch=_HAUPT,
        )
        zell_werte = zellgewichtet["wert"].dropna()
        erster = float(zell_werte.mean()) if not zell_werte.empty else None
        zweiter = (
            float(variantengewichtet["wert"].mean())
            if not variantengewichtet["wert"].dropna().empty
            else None
        )
        zeilen.append(
            {
                "fehlerklasse": klasse,
                "recall_zellgewichtet": erster,
                "recall_variantengewichtet": zweiter,
                "differenz": None if erster is None or zweiter is None else zweiter - erster,
                "varianten_der_klasse": sum(
                    1 for bezug in VARIANTENTABELLE if bezug.fehlerklasse == klasse
                ),
            }
        )
    return pd.DataFrame(zeilen)


def t10_mitgezogen(lang: pd.DataFrame, plan: Versuchsplan) -> pd.DataFrame:
    """Baut ``t10_mitgezogen``: Sensitivitaetsrechnung ueber beide Schalterstellungen.

    Die Richtung des Effekts ist **klassenabhaengig** und wird deshalb nirgends
    pauschal beschrieben: Bei F8 senkt der Schalter den Recall, bei HO2 hob er ihn
    vor der Korrektur aus dem dritten Nachtrag der Phase 5. Die Tabelle zeigt die
    Differenz je Klasse und ueberlaesst die Deutung dem Text.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Eine Zeile je Verfahren und Fehlerklasse.
    """
    zeilen: list[dict[str, Any]] = []
    for klasse, block, ebene in _bloecke_je_klasse(plan):
        for verfahren in _verfahren_des_blocks(plan, block):
            zeile: dict[str, Any] = {
                "verfahren": verfahren,
                "fehlerklasse": klasse,
                "teilversuch": block,
                "ebene": ebene.value,
            }
            for metrik in ("precision", "recall", "f1"):
                for schalter, kuerzel in ((False, "ohne"), (True, "mit")):
                    werte = _kennzahl_mit_intervall(
                        lang,
                        plan,
                        metrik=metrik,
                        verfahren=verfahren,
                        klasse=klasse,
                        teilversuch=block,
                        ebene=ebene,
                        mitgezogen=schalter,
                    )
                    zeile[f"{metrik}_{kuerzel}_mitgezogen"] = werte[metrik]
                ohne = zeile[f"{metrik}_ohne_mitgezogen"]
                mit = zeile[f"{metrik}_mit_mitgezogen"]
                zeile[f"{metrik}_differenz"] = (
                    None if ohne is None or mit is None else mit - ohne
                )
            zeilen.append(zeile)
    return pd.DataFrame(zeilen)


def t11_satzebene_hauptversuch(lang: pd.DataFrame, plan: Versuchsplan) -> pd.DataFrame:
    """Baut ``t11_satzebene_hauptversuch``: dieselben Kennzahlen wie ``t1``, auf der Satzebene.

    Warum es diese Tabelle geben muss
    ----------------------------------

    Die Satzebene ist der **Primaervergleich fuer B2** (Phase 5, Abschnitt 5.3):
    B2 markiert ganze Zeilen, und die Umrechnung "markierte Zeile markiert alle
    ihre befuellten Zellen" deckelt seine Zell-Precision auf etwa den Kehrwert der
    Spaltenzahl. Ein Zellvergleich misst dort zu einem grossen Teil die
    Umrechnung und nicht das Verfahren.

    :func:`t1_hauptergebnis` fuehrt die Satzebene aber nur fuer die Teilversuche
    T1 und T2, weil :func:`_bloecke_je_klasse` sie genau den beiden satzbasierten
    Klassen F6 und HO1 zuordnet. Fuer die sieben Klassen des Hauptversuchs steht
    dort ausschliesslich die Zellebene. Die zentrale Vergleichsaussage der Arbeit
    — B2 liegt auf seiner eigenen Primaerebene in keiner Fehlerklasse vorn — war
    damit in keiner Ergebnistabelle belegt. Diese Tabelle schliesst die Luecke.

    Es wird dafuer **kein Lauf neu gerechnet**: Die Satzebenenwerte des
    Hauptversuchs stehen vollstaendig im Langformat und werden hier nur
    aggregiert. Spalten und Zahlenformat sind mit ``t1_hauptergebnis`` identisch,
    damit beide Tabellen nebeneinander lesbar sind.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Eine Zeile je Verfahren und Fehlerklasse des Hauptversuchs. Die Attribute
        ``f1_mittel`` und ``fuehrend`` tragen die beiden Zusatzangaben, die
        :func:`schreibe_tabelle` als Lesehinweis ausgibt.
    """
    zeilen: list[dict[str, Any]] = []
    for klasse in plan.hauptversuch.gruppen:
        for verfahren in plan.hauptversuch.verfahren:
            zeile: dict[str, Any] = {
                "verfahren": verfahren,
                "fehlerklasse": klasse,
                "teilversuch": _HAUPT,
                "ebene": Ebene.SATZ.value,
            }
            for metrik in ("precision", "recall", "f1"):
                zeile.update(
                    _kennzahl_mit_intervall(
                        lang,
                        plan,
                        metrik=metrik,
                        verfahren=verfahren,
                        klasse=klasse,
                        teilversuch=_HAUPT,
                        ebene=Ebene.SATZ,
                    )
                )
            zeilen.append(zeile)

    tabelle = pd.DataFrame(zeilen)
    # Die Zusatzangaben nur, wenn ueberhaupt ein Wert vorliegt: Eine Bilanz
    # "fuehrt in 0 von 0 Klassen" saehe aus wie ein Ergebnis und waere keines.
    if not tabelle.empty and bool(tabelle["f1"].notna().any()):
        tabelle.attrs["f1_mittel"] = _ungewichtetes_f1_mittel(tabelle)
        tabelle.attrs["fuehrend"] = _fuehrendes_verfahren(tabelle)
        tabelle.attrs["lesehinweis"] = (
            "Satzebene des **Hauptversuchs**, aggregiert ueber die vier Ratenstufen und "
            "zwanzig Wiederholungen. Sie ist der Primaervergleich fuer B2 (Phase 5, "
            "Abschnitt 5.3); `t1_hauptergebnis` fuehrt fuer diese sieben Klassen nur die "
            "Zellebene. Es wurde kein Lauf neu gerechnet — die Werte standen bereits im "
            "Langformat und werden hier nur aggregiert."
        )
    return tabelle


def _ungewichtetes_f1_mittel(tabelle: pd.DataFrame) -> dict[str, float | None]:
    """Bildet je Verfahren das ungewichtete Mittel des F1 ueber die Fehlerklassen.

    Ungewichtet heisst: jede Fehlerklasse zaehlt gleich viel, unabhaengig davon,
    wie viele Zellen oder Saetze sie im Ground Truth belegt. Ein
    fallzahlgewichtetes Mittel liesse die haeufigste Klasse das Ergebnis
    bestimmen, und die Fehlertaxonomie ist kein Haeufigkeitsmodell.

    Args:
        tabelle: Die Tabelle mit einer Zeile je Verfahren und Klasse.

    Returns:
        Je Verfahren das Mittel; ``None``, wenn eine Klasse keinen Wert traegt —
        ein Mittel ueber die uebrigen waere eine andere Groesse mit demselben
        Namen.
    """
    mittel: dict[str, float | None] = {}
    for verfahren, teil in tabelle.groupby("verfahren", sort=False):
        werte = teil["f1"]
        mittel[str(verfahren)] = None if werte.isna().any() else float(werte.mean())
    return mittel


def _fuehrendes_verfahren(tabelle: pd.DataFrame) -> dict[str, tuple[str, float]]:
    """Nennt je Fehlerklasse das Verfahren mit dem hoechsten F1.

    Die Angabe macht die Aussage "B2 liegt in keiner Klasse vorn" gegen die
    Tabelle pruefbar, ohne dass jemand siebenmal drei Zeilen vergleichen muss.
    Sie ist eine **Ablesung** und kein Test; welche Unterschiede statistisch
    gesichert sind, steht in der Familie ``HYP4-paarweise-Satz``.

    Args:
        tabelle: Die Tabelle mit einer Zeile je Verfahren und Klasse.

    Returns:
        Je Fehlerklasse das fuehrende Verfahren und sein F1. Klassen ohne
        auswertbaren Wert fehlen.
    """
    fuehrend: dict[str, tuple[str, float]] = {}
    for klasse, teil in tabelle.groupby("fehlerklasse", sort=False):
        gueltig = teil[teil["f1"].notna()]
        if gueltig.empty:
            continue
        beste = gueltig.loc[gueltig["f1"].idxmax()]
        fuehrend[str(klasse)] = (str(beste["verfahren"]), float(str(beste["f1"])))
    return fuehrend


# ---------------------------------------------------------------------------
# Ausgabe
# ---------------------------------------------------------------------------


def _zelle(wert: Any) -> str:  # noqa: ANN401 - eine Tabellenzelle traegt jeden Grundtyp
    """Formatiert einen Wert fuer die Markdown-Fassung.

    Gleitkommazahlen bekommen vier Nachkommastellen und ein deutsches
    Dezimalkomma; fehlende Werte einen Gedankenstrich. Ein leeres Feld waere von
    einer Null nicht zu unterscheiden, und genau diese Unterscheidung traegt in
    den Ergebnistabellen Bedeutung: "nicht auswertbar" ist etwas anderes als
    "null gefunden".

    Args:
        wert: Der Zellwert.

    Returns:
        Die Zeichenkette fuer die Markdown-Zelle.
    """
    if wert is None or (not isinstance(wert, str) and pd.isna(wert)):
        return "—"
    if isinstance(wert, bool):
        return "ja" if wert else "nein"
    if isinstance(wert, float):
        return f"{wert:.4f}".replace(".", ",")
    return str(wert).replace("|", "\\|")


def _als_markdown(tabelle: pd.DataFrame) -> str:
    """Formatiert eine Tabelle als Markdown.

    Bewusst von Hand und nicht ueber ``DataFrame.to_markdown``: Letzteres
    verlangt das Zusatzpaket ``tabulate``, und eine weitere gepinnte
    Abhaengigkeit nur fuer die Formatierung einer Tabelle waere ein schlechter
    Tausch — Architekturregel A2 verlangt gepinnte Versionen fuer **jede**
    Abhaengigkeit, und jede zusaetzliche vergroessert das
    Reproduzierbarkeitspaket. Nebenbei bekommt die Ausgabe damit das deutsche
    Dezimalkomma, das ``to_markdown`` nicht kennt.

    Args:
        tabelle: Die zu formatierende Tabelle.

    Returns:
        Die Markdown-Darstellung.
    """
    spalten = list(tabelle.columns)
    zeilen = [
        "| " + " | ".join(str(spalte) for spalte in spalten) + " |",
        "|" + "|".join("---" for _ in spalten) + "|",
    ]
    zeilen.extend(
        "| " + " | ".join(_zelle(zeile[spalte]) for spalte in spalten) + " |"
        for _, zeile in tabelle.iterrows()
    )
    return "\n".join(zeilen)


def schreibe_tabelle(tabelle: pd.DataFrame, verzeichnis: Path, name: str) -> tuple[Path, Path]:
    """Schreibt eine Tabelle als CSV und als Markdown.

    Das CSV benutzt Punkt als Dezimaltrenner und Komma als Feldtrenner — es ist
    die maschinenlesbare Fassung. Das Markdown ist die Fassung, die in die Arbeit
    kopiert wird; dort stehen gerundete Werte, weil sechs Nachkommastellen in
    einer gedruckten Tabelle nur Platz kosten.

    Args:
        tabelle: Die zu schreibende Tabelle.
        verzeichnis: Zielverzeichnis, ueblicherweise ``results/tables``.
        name: Name ohne Endung, zum Beispiel ``"t1_hauptergebnis"``.

    Returns:
        Die Pfade der beiden geschriebenen Dateien.
    """
    verzeichnis.mkdir(parents=True, exist_ok=True)
    csv_pfad = verzeichnis / f"{name}.csv"
    md_pfad = verzeichnis / f"{name}.md"
    tabelle.to_csv(csv_pfad, index=False, encoding="utf-8", lineterminator="\n")

    gerundet = tabelle.copy()
    for spalte in gerundet.columns:
        if pd.api.types.is_float_dtype(gerundet[spalte]):
            gerundet[spalte] = gerundet[spalte].round(4)
    kopf = [f"# {name}", ""]
    if "lesehinweis" in tabelle.attrs:
        kopf += [f"> {tabelle.attrs['lesehinweis']}", ""]
    if "regeln_ohne_meldung" in tabelle.attrs:
        ueberdeckung = tabelle.attrs["ueberdeckung"]
        nicht_pruefbar = tabelle.attrs["nicht_pruefbar"]
        kopf += [
            (
                f"> Von {tabelle.attrs['regeln_gesamt']} Regeln des Katalogs haben "
                f"{tabelle.attrs['regeln_ohne_meldung']} in keinem Lauf gemeldet. Sie bleiben "
                "in der Tabelle, und ihr Grund steht in der Spalte `grund_ohne_treffer` — "
                "die beiden moeglichen Gruende sind **zwei verschiedene Aussagen**."
            ),
            ">",
            (
                f"> **Ueberdeckung ({len(ueberdeckung)}): {ueberdeckung}** — keine "
                "Injektionsvariante zielt darauf, ihre Felder wurden in der Serie aber "
                "verfaelscht, ohne die Bedingung zu verletzen. Der Katalog deckt mehr ab, "
                "als die Fehlertaxonomie adressiert. Das ist ein Ergebnis."
            ),
            ">",
            (
                f"> **In diesem Aufbau nicht pruefbar ({len(nicht_pruefbar)}): "
                f"{nicht_pruefbar}** — die Felder dieser Regeln werden von keiner "
                "Injektion getroffen. Ueber sie sagt die Serie nichts. Das ist eine "
                "Limitation."
            ),
            "",
        ]
    if "trefferkategorien" in tabelle.attrs:
        verteilung = tabelle.attrs["trefferkategorien"]
        kategorie_b = tabelle.attrs["kategorie_b_varianten"]
        kopf += [
            (
                "> **Trefferkategorien** aus der Kreuztabelle `regel_id` gegen Variante — "
                "keine Umetikettierung, sondern eine Messung: Die Regel-ID steht im "
                "Ergebnis und wird nicht neu vergeben."
            ),
            ">",
            *[f"> - **{kategorie}**: {anzahl}" for kategorie, anzahl in verteilung.items()],
            ">",
            (
                f"> Kategorie B ({len(kategorie_b)}: {kategorie_b}) ist der inhaltlich "
                "staerkste Einzelbefund: **Eine Variante, die von einer Regel gefangen "
                "wird, die nicht gegen sie entworfen wurde, ist das Gegenteil von "
                "Zirkularitaet.** Der Katalog hat dort eine Deckung, die ueber seine "
                "eigene Herleitung hinausreicht."
            ),
            "",
        ]
    if "f1_mittel" in tabelle.attrs:
        mittel = tabelle.attrs["f1_mittel"]
        fuehrend = tabelle.attrs["fuehrend"]
        gewinne: dict[str, int] = {}
        for verfahren, _ in fuehrend.values():
            gewinne[verfahren] = gewinne.get(verfahren, 0) + 1
        kopf += [
            (
                "> **Ungewichtetes Mittel des F1 ueber die Fehlerklassen** (jede Klasse zaehlt "
                "gleich viel): "
                + "; ".join(
                    f"{name} = {'—' if wert is None else _zelle(wert)}"
                    for name, wert in mittel.items()
                )
                + "."
            ),
            ">",
            (
                "> **Fuehrendes Verfahren je Fehlerklasse** (Ablesung des hoechsten F1, kein "
                "Test — welche Unterschiede gesichert sind, steht in der Familie "
                "`HYP4-paarweise-Satz`): "
                + "; ".join(
                    f"{klasse}: {name} ({_zelle(wert)})"
                    for klasse, (name, wert) in fuehrend.items()
                )
                + "."
            ),
            ">",
            (
                "> Bilanz: "
                + ", ".join(
                    f"{name} fuehrt in {anzahl} von {len(fuehrend)} Klassen"
                    for name, anzahl in sorted(gewinne.items(), key=lambda paar: -paar[1])
                )
                + "."
            ),
            "",
        ]
    if "vorab_eingetroffen" in tabelle.attrs:
        kopf += [
            (
                f"> **Trefferquote der Vorab-Zuordnung: {tabelle.attrs['vorab_eingetroffen']} "
                f"von {tabelle.attrs['vorab_geprueft']}.** Die Spalte "
                "`spiegelt_regel_exakt` stammt aus `spec/03`, Abschnitt 2 und wurde "
                "**vor** der Messung festgelegt; sie ist damit eine falsifizierbare "
                "Erwartung. Ueberschaetzt wurde bei "
                f"{tabelle.attrs['vorab_ueberschaetzt']} (eine greifende Regel erwartet, "
                "Variante bleibt trotzdem unentdeckt), unterschaetzt bei "
                f"{tabelle.attrs['vorab_unterschaetzt']} (keine Regel erwartet, Variante "
                "wird trotzdem gefunden). Geprueft wird gegen einen Recall von 0,5; bei "
                "der Einstufung 'teilweise' gegen einen Wert echt zwischen 0 und 1."
            ),
            "",
        ]
    md_pfad.write_text(
        "\n".join([*kopf, _als_markdown(tabelle), ""]),
        encoding="utf-8",
        newline="\n",
    )
    return (csv_pfad, md_pfad)


def baue_alle(
    lang: pd.DataFrame,
    plan: Versuchsplan,
    *,
    frameworkvergleich: Path,
    injizierte_spalten: AbstractSet[tuple[str, str]],
) -> dict[str, pd.DataFrame]:
    """Baut alle Ergebnistabellen aus :data:`TABELLENNAMEN`.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.
        frameworkvergleich: Pfad von ``results/framework_vergleich.json``.
        injizierte_spalten: Alle in der Serie verfaelschten ``(entitaet,
            spalte)``-Paare; sie unterscheiden in ``t3`` Ueberdeckung von
            Nichtpruefbarkeit.

    Returns:
        Je Tabellenname die Tabelle, in Berichtsreihenfolge.
    """
    return {
        "t1_hauptergebnis": t1_hauptergebnis(lang, plan),
        "t2_fehlerraten": t2_fehlerraten(lang, plan),
        "t3_regeldiagnose": t3_regeldiagnose(
            lang, plan, injizierte_spalten=injizierte_spalten
        ),
        "t4_varianten": t4_varianten(lang, plan),
        "t5_frameworkvergleich": t5_frameworkvergleich(frameworkvergleich),
        "t6_laufzeit": t6_laufzeit(lang, plan),
        "t7_teilversuche": t7_teilversuche(lang, plan),
        "t8_metrikvergleich": t8_metrikvergleich(lang, plan),
        "t9_gewichtung": t9_gewichtung(lang, plan),
        "t10_mitgezogen": t10_mitgezogen(lang, plan),
        "t11_satzebene_hauptversuch": t11_satzebene_hauptversuch(lang, plan),
    }
