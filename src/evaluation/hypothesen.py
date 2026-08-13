"""Die vier Hypothesen HYP1 bis HYP4, je mit dem zu ihnen passenden Test.

Dieses Modul entscheidet, welches Verfahren welche Hypothese prueft. Gerechnet
wird in :mod:`src.evaluation.statistik`, gelesen ueber
:mod:`src.evaluation.ergebnisse`.

Vier Hypothesen, vier verschiedene Testverfahren — und das ist kein Zufall
---------------------------------------------------------------------------

HYP1 vergleicht zwei Verfahren auf denselben Laeufen: gepaarter
Wilcoxon-Vorzeichen-Rangtest. HYP2 vergleicht sieben Gruppen auf denselben
Bloecken: Friedman-Test, danach paarweise. HYP3 behauptet einen **Trend** ueber
geordnete Stufen: Page-Trendtest — ein Wilcoxon-Test waere hier schlicht das
falsche Werkzeug, weil er die Ordnung der Ratenstufen ungenutzt liesse. HYP4
behauptet eine **Interaktion**: ART-ANOVA.

Ein t-Test kommt nirgends vor; die Begruendung steht im Modul-Docstring von
:mod:`src.evaluation.statistik`.

Die Namensgebung, weil beides in Ergebnisdateien landet
--------------------------------------------------------

``HYP1`` bis ``HYP4`` sind die **Hypothesen**. ``HO1`` und ``HO2`` sind die
beiden **Held-out-Fehlerklassen**. Sie werden hier konsequent
auseinandergehalten: Die Held-out-Klassen kommen in keiner Hypothese vor — sie
sind der Teilversuch T2 und beantworten das "inwieweit" der Forschungsfrage
deskriptiv, nicht inferenzstatistisch. Eine Hypothese "der Recall ist null" waere
eine Nullhypothese, und die laesst sich nicht bestaetigen.

Warum HYP1 ohne die Precision-Bedingung wertlos waere
-------------------------------------------------------

B0 prueft Typen, Nullable-Bedingungen und Laengen — das ist eine **Teilmenge**
dessen, was der Katalog prueft. Dass der Prototyp mehr findet, ist damit fast
tautologisch. Die Hypothese wird erst dadurch pruefbar, dass sie zugleich
behauptet, die Precision falle nicht: Ein Katalog, der mehr findet, koennte das
mit mehr Fehlalarmen erkaufen. Genau das kann scheitern, und genau deshalb
bestehen beide Familien nebeneinander.

Aggregationsebene und Familien
-------------------------------

Vorab festgelegt: **ueber die Fehlerraten aggregieren, je Klasse testen**. Damit
ergibt sich je Hypothese die Zahl der Vergleiche, und sie wird ausgewiesen:

=============================  ==================================  ============
Familie                        Vergleicht                          Hoechstens
=============================  ==================================  ============
HYP1-Recall                    Prototyp gegen B0, je Klasse                   7
HYP1-Precision                 Prototyp gegen B0, je Klasse                   7
HYP2-paarweise                 Klasse gegen Klasse                           21
HYP3-Trend-Zelle               Trend je Klasse, Zellebene                     7
HYP3-Trend-Constraint          Trend je Klasse, Constraint-Ebene              7
HYP4-paarweise-Satz            Prototyp gegen B2, Satzebene                   7
HYP4-paarweise-Zelle           Prototyp gegen B2, Zellebene                   7
=============================  ==================================  ============

"Hoechstens", weil die tatsaechliche Familiengroesse kleiner sein kann: Ein
Vergleich, der inhaltlich nicht durchfuehrbar ist, zaehlt **nicht** mit. So bei
HYP1-Precision — in den Klassen, in denen B0 gar nichts meldet, ist seine
Precision eine Konvention und keine Messung, und ein Vergleich dagegen prueft
nichts. Die Korrektur laeuft dort ueber die verbleibenden Vergleiche, und die
Familiengroesse steht in jeder Ausgabe neben der Zahl der berichteten Zeilen.
Eine Familiengroesse, die nicht zur Zahl der durchgefuehrten Tests passt,
korrigiert gegen Tests, die es nicht gibt.

Die beiden Familien von HYP1 werden **getrennt** korrigiert. Sie pruefen
verschiedene Kennzahlen, und eine gemeinsame Korrektur ueber alle Vergleiche
waere unnoetig streng: Die Precision-Familie dient der Absicherung, nicht der
Bestaetigung.

Zwei Hypothesen werden auf **zwei Metrikebenen** gerechnet
-----------------------------------------------------------

HYP3 auf der Zell- **und** der Constraint-Precision: Auf der Zellebene erzeugt
jede Injektion ueber mehrspaltige Regeln zusaetzliche Scheinfehlalarme, deren
Zahl mit der Injektionszahl waechst. Ein Trend, der nur dort besteht, ist ein
Effekt der Berichtskonvention und keiner des Verfahrens.

HYP4 auf der Satz- **und** der Zellebene, mit der Satzebene als Primaerebene (so
in Phase 5 festgelegt): B2 markiert ganze Zeilen, und die Umrechnung auf Zellen
deckelt seine Zell-Precision auf etwa den Kehrwert der Spaltenzahl. Ein
Zellvergleich maesse dort zu einem grossen Teil die Umrechnung.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from src.evaluation.ergebnisse import (
    GRUPPE_GESAMT,
    auswahl,
    mittel_je_wiederholung,
)
from src.evaluation.modell import AuswertungsFehler, Ebene
from src.evaluation.statistik import (
    STANDARD_ALPHA,
    Testergebnis,
    art_anova_interaktion,
    friedman,
    holm,
    page_trend,
    spearman,
    wilcoxon_gepaart,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence

    import pandas as pd

    from src.evaluation.experimentplan import Versuchsplan

__all__ = [
    "Familie",
    "Hypothesenergebnis",
    "Vergleich",
    "alle_hypothesen",
    "als_markdown",
    "hypothesen_als_dict",
]

#: Kennung des Prototyps und der beiden statistisch verglichenen Baselines.
_PROTOTYP: Final[str] = "prototyp"
_B0: Final[str] = "B0"
_B2: Final[str] = "B2"

#: Kennung des Hauptversuchs im Langformat.
_HAUPT: Final[str] = "haupt"

#: Begruendung fuer einen Precision-Vergleich, den B0 nicht zulaesst.
_GRUND_OHNE_MELDUNG: Final[str] = (
    "B0 meldet in dieser Klasse keine einzige Zelle. Seine Precision ist "
    "konventionsgemaess 0,0 — das ist eine Festlegung und keine Messung, und ein "
    "Vergleich dagegen prueft nichts."
)

#: Unterhalb dieser Schwelle wird ein p-Wert nicht mehr beziffert.
#:
#: Drei Nachkommastellen sind die Genauigkeit, die in der Arbeit berichtet wird;
#: "p = 0,000" waere eine Behauptung ueber die vierte Stelle, die der Test bei
#: zwanzig Wiederholungen nicht traegt.
_P_SCHWELLE: Final[float] = 0.001


@dataclass(frozen=True, slots=True)
class Vergleich:
    """Ein einzelner Vergleich innerhalb einer Hypothesenfamilie.

    Attributes:
        gruppe: Worauf sich der Vergleich bezieht, meist eine Fehlerklasse.
        test: Das Testergebnis mit unkorrigiertem p-Wert und Effektstaerke;
            ``None``, wenn der Vergleich gar nicht durchgefuehrt wurde.
        p_korrigiert: Der nach Holm-Bonferroni korrigierte p-Wert; ``None`` bei
            einem nicht anwendbaren Vergleich.
        signifikant: Ob ``p_korrigiert`` das Niveau unterschreitet.
        anwendbar: ``False``, wenn der Vergleich inhaltlich nicht durchfuehrbar
            ist — etwa weil das Vergleichsverfahren in dieser Klasse gar nichts
            meldet und seine Precision damit eine Konvention ist und keine
            Messung. Solche Vergleiche zaehlen **nicht** zur Holm-Familie: Eine
            Familiengroesse, die nicht zur Zahl der durchgefuehrten Tests passt,
            korrigiert gegen Tests, die es nicht gibt.
        grund: Klartext, warum ein Vergleich nicht anwendbar ist.
    """

    gruppe: str
    test: Testergebnis | None
    p_korrigiert: float | None
    signifikant: bool
    anwendbar: bool = True
    grund: str = ""


@dataclass(frozen=True, slots=True)
class Familie:
    """Eine Familie von Vergleichen mit gemeinsamer Multiplizitaetskorrektur.

    Attributes:
        kennung: Kurzname, zum Beispiel ``"HYP1-Recall"``.
        beschreibung: Was verglichen wird.
        kennzahl: Die verglichene Kennzahl.
        vergleiche: Die Einzelvergleiche in Gruppenreihenfolge.
    """

    kennung: str
    beschreibung: str
    kennzahl: str
    vergleiche: tuple[Vergleich, ...]

    @property
    def anzahl(self) -> int:
        """Gibt die Groesse der Holm-Familie zurueck: die anwendbaren Vergleiche.

        **Nicht** die Zahl der berichteten Zeilen. Nicht anwendbare Vergleiche
        wurden nicht durchgefuehrt und duerfen deshalb nicht mitkorrigiert
        werden; sie stehen in der Tabelle, damit ihr Fehlen erklaert ist.
        """
        return sum(1 for vergleich in self.vergleiche if vergleich.anwendbar)

    @property
    def berichtet(self) -> int:
        """Gibt die Zahl aller Zeilen der Familie zurueck, anwendbar oder nicht."""
        return len(self.vergleiche)

    @property
    def nicht_anwendbar(self) -> int:
        """Gibt die Zahl der nicht durchgefuehrten Vergleiche zurueck."""
        return sum(1 for vergleich in self.vergleiche if not vergleich.anwendbar)

    @property
    def signifikante(self) -> int:
        """Gibt die Zahl der nach Korrektur signifikanten Vergleiche zurueck."""
        return sum(1 for vergleich in self.vergleiche if vergleich.signifikant)


@dataclass(frozen=True, slots=True)
class Hypothesenergebnis:
    """Das vollstaendige Ergebnis einer Hypothese.

    Attributes:
        kennung: ``"HYP1"`` bis ``"HYP4"``.
        aussage: Die Hypothese im Wortlaut.
        primaertest: Der Test, der ueber die Hypothese entscheidet; ``None``,
            wenn die Entscheidung aus den Familien folgt.
        familien: Die Vergleichsfamilien.
        nebentests: Derselbe Test auf einer **anderen** Metrikebene, je mit
            seiner Bezeichnung. Kein Zusatzmaterial, sondern Teil der Aussage:
            Ein Effekt, der auf der Zellebene besteht und auf der
            Constraint-Ebene verschwindet, ist ein Effekt der Berichtskonvention
            und keiner des Verfahrens.
        entscheidung: ``"gestuetzt"``, ``"nicht gestuetzt"`` oder
            ``"teilweise gestuetzt"``.
        begruendung: Ein Satz, warum die Entscheidung so ausfaellt.
        hinweise: Weitere Anmerkungen, etwa zur Interpretation.
    """

    kennung: str
    aussage: str
    primaertest: Testergebnis | None
    familien: tuple[Familie, ...]
    entscheidung: str
    begruendung: str
    nebentests: tuple[tuple[str, Testergebnis], ...] = ()
    hinweise: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _reihe(  # noqa: PLR0913 - jede Angabe waehlt eine eigene Dimension des Langformats
    lang: pd.DataFrame,
    *,
    metrik: str,
    verfahren: str,
    klasse: str,
    ebene: Ebene = Ebene.ZELLE,
    teilversuch: str = _HAUPT,
) -> list[float]:
    """Liest eine Kennzahl als Reihe ueber die Wiederholungen.

    Gemittelt wird ueber die Fehlerraten — die vorab festgelegte
    Aggregationsebene.

    Args:
        lang: Das Langformat.
        metrik: Die Kennzahl.
        verfahren: Das Verfahren.
        klasse: Die Fehlerklasse.
        ebene: Die Auswertungsebene.
        teilversuch: Die Blockkennung.

    Returns:
        Die Werte in aufsteigender Reihenfolge der Wiederholung.
    """
    gefiltert = auswahl(
        lang,
        metrik=metrik,
        verfahren=verfahren,
        ebene=ebene,
        gruppe_art=GRUPPE_GESAMT,
        klasse=klasse,
        teilversuch=teilversuch,
    )
    return [float(wert) for wert in mittel_je_wiederholung(gefiltert)]


def _familie(  # noqa: PLR0913 - jede Angabe beschreibt einen eigenen Aspekt der Familie
    kennung: str,
    beschreibung: str,
    kennzahl: str,
    ergebnisse: Sequence[tuple[str, Testergebnis]],
    *,
    alpha: float,
    nicht_anwendbar: Mapping[str, str] | None = None,
) -> Familie:
    """Korrigiert eine Folge von Einzeltests nach Holm und baut die Familie.

    Die Holm-Korrektur laeuft **nur ueber die anwendbaren** Vergleiche. Ein
    Vergleich, der gar nicht durchgefuehrt wurde, darf die Familiengroesse nicht
    erhoehen: Die Korrektur wuerde sonst gegen Tests schuetzen, die es nicht
    gibt, und die berichtete Familiengroesse passte nicht zur Zahl der
    berichteten p-Werte. Beides faellt in einem Kolloquium auf.

    Args:
        kennung: Kurzname der Familie.
        beschreibung: Was verglichen wird.
        kennzahl: Die verglichene Kennzahl.
        ergebnisse: Je Gruppe ihr Testergebnis, in Berichtsreihenfolge.
        alpha: Signifikanzniveau.
        nicht_anwendbar: Je nicht anwendbarer Gruppe der Grund. Diese Gruppen
            erscheinen in der Familie, aber ohne Test und ohne p-Wert.

    Returns:
        Die Familie mit korrigierten p-Werten.
    """
    ausgenommen = dict(nicht_anwendbar or {})
    anwendbare = [(gruppe, test) for gruppe, test in ergebnisse if gruppe not in ausgenommen]
    korrigiert = dict(
        zip(
            [gruppe for gruppe, _ in anwendbare],
            holm([test.p_wert for _, test in anwendbare]),
            strict=True,
        )
    )
    vergleiche = []
    for gruppe, test in ergebnisse:
        if gruppe in ausgenommen:
            vergleiche.append(
                Vergleich(
                    gruppe=gruppe,
                    test=None,
                    p_korrigiert=None,
                    signifikant=False,
                    anwendbar=False,
                    grund=ausgenommen[gruppe],
                )
            )
            continue
        wert = korrigiert[gruppe]
        vergleiche.append(
            Vergleich(gruppe=gruppe, test=test, p_korrigiert=wert, signifikant=wert < alpha)
        )
    return Familie(
        kennung=kennung,
        beschreibung=beschreibung,
        kennzahl=kennzahl,
        vergleiche=tuple(vergleiche),
    )


def _klassen(plan: Versuchsplan) -> tuple[str, ...]:
    """Gibt die Fehlerklassen des Hauptversuchs in Planreihenfolge zurueck."""
    return tuple(plan.hauptversuch.gruppen)


def _klassen_ohne_meldung(
    lang: pd.DataFrame, *, verfahren: str, klassen: Sequence[str]
) -> tuple[str, ...]:
    """Findet die Klassen, in denen ein Verfahren ueberhaupt nichts gemeldet hat.

    Wichtig fuer die Deutung der Precision: Sie ist bei leerer Meldungsmenge
    konventionsgemaess ``0.0`` (siehe
    :class:`~src.evaluation.modell.Kennzahlen`). Das ist etwas **anderes** als
    "alle Meldungen waren falsch" — es heisst "es gab keine Meldung". Ein
    Precision-Vergleich gegen diese Null vergleicht eine Messung mit einer
    Festlegung, und wer das nicht weiss, liest aus einem gestiegenen Wert einen
    Vorteil heraus, den die Zahl nicht trägt.

    Args:
        lang: Das Langformat.
        verfahren: Das zu pruefende Verfahren.
        klassen: Die zu pruefenden Fehlerklassen.

    Returns:
        Die Klassen ohne eine einzige Meldung, in Eingabereihenfolge.
    """
    ohne: list[str] = []
    for klasse in klassen:
        gemeldet = 0.0
        for metrik in ("tp", "fp"):
            gefiltert = auswahl(
                lang,
                metrik=metrik,
                verfahren=verfahren,
                ebene=Ebene.ZELLE,
                gruppe_art=GRUPPE_GESAMT,
                klasse=klasse,
                teilversuch=_HAUPT,
            )
            gemeldet += float(gefiltert["wert"].fillna(0.0).sum())
        if gemeldet == 0.0:
            ohne.append(klasse)
    return tuple(ohne)


# ---------------------------------------------------------------------------
# Die vier Hypothesen
# ---------------------------------------------------------------------------


def pruefe_hyp1(lang: pd.DataFrame, plan: Versuchsplan) -> Hypothesenergebnis:
    """Prueft HYP1: hoeherer Recall als B0, ohne dass die Precision faellt.

    Der Recall wird **einseitig** getestet (Alternative: Prototyp groesser) —
    die Hypothese ist gerichtet, und ein zweiseitiger Test verschenkte hier
    Trennschaerfe ohne Gegenwert. Die Precision wird **zweiseitig** getestet: Ein
    einseitiger Test in Richtung "faellt nicht" koennte einen Anstieg nicht von
    Gleichheit unterscheiden, und beides ist fuer die Deutung wichtig.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Das Hypothesenergebnis mit zwei Familien.
    """
    alpha = plan.statistik.alpha
    klassen = _klassen(plan)

    recall: list[tuple[str, Testergebnis]] = []
    precision: list[tuple[str, Testergebnis]] = []
    for klasse in klassen:
        proto_r = _reihe(lang, metrik="recall", verfahren=_PROTOTYP, klasse=klasse)
        b0_r = _reihe(lang, metrik="recall", verfahren=_B0, klasse=klasse)
        recall.append((klasse, wilcoxon_gepaart(proto_r, b0_r, seitig="einseitig")))
        proto_p = _reihe(lang, metrik="precision", verfahren=_PROTOTYP, klasse=klasse)
        b0_p = _reihe(lang, metrik="precision", verfahren=_B0, klasse=klasse)
        precision.append((klasse, wilcoxon_gepaart(proto_p, b0_p, seitig="zweiseitig")))

    ohne_meldung = _klassen_ohne_meldung(lang, verfahren=_B0, klassen=klassen)
    familie_recall = _familie(
        "HYP1-Recall",
        "Recall des Prototyps gegen B0, je Fehlerklasse, einseitig",
        "recall",
        recall,
        alpha=alpha,
    )
    familie_precision = _familie(
        "HYP1-Precision",
        "Precision des Prototyps gegen B0, je Fehlerklasse, zweiseitig",
        "precision",
        precision,
        alpha=alpha,
        nicht_anwendbar=dict.fromkeys(ohne_meldung, _GRUND_OHNE_MELDUNG),
    )

    gefallen = [
        vergleich.gruppe
        for vergleich in familie_precision.vergleiche
        if vergleich.signifikant
        and vergleich.test is not None
        and (vergleich.test.effekt or 0.0) < 0
    ]
    erfuellt = [
        vergleich.gruppe
        for vergleich in familie_recall.vergleiche
        if vergleich.signifikant and vergleich.gruppe not in gefallen
    ]
    if len(erfuellt) == len(klassen):
        entscheidung = "gestuetzt"
    elif erfuellt:
        entscheidung = "teilweise gestuetzt"
    else:
        entscheidung = "nicht gestuetzt"

    return Hypothesenergebnis(
        kennung="HYP1",
        aussage=(
            "Der Prototyp erreicht einen hoeheren Recall als B0, ohne dass die Precision "
            "signifikant faellt."
        ),
        primaertest=None,
        familien=(familie_recall, familie_precision),
        entscheidung=entscheidung,
        begruendung=(
            f"Der Recall ist in {familie_recall.signifikante} von {familie_recall.anzahl} "
            "Fehlerklassen signifikant hoeher. Die Precision-Bedingung ist nur in "
            f"{familie_precision.anzahl} Klassen ueberhaupt pruefbar — in "
            f"{list(ohne_meldung)} meldet B0 nichts. "
            + (
                f"In {len(gefallen)} der {familie_precision.anzahl} pruefbaren Klassen "
                f"faellt die Precision signifikant: {gefallen}."
                if gefallen
                else "In keiner pruefbaren Klasse faellt die Precision signifikant."
            )
            + f" Beide Bedingungen zusammen erfuellen {len(erfuellt)} von {len(klassen)} "
            "Klassen."
        ),
        hinweise=(
            (
                "Der Recall-Teil allein waere nahezu tautologisch: B0 prueft eine Teilmenge "
                "der Bedingungen des Katalogs. Erst die Precision-Bedingung macht daraus eine "
                "Hypothese, die scheitern kann."
            ),
            (
                "Die beiden Familien werden getrennt nach Holm korrigiert; eine gemeinsame "
                "Korrektur ueber alle Vergleiche waere unnoetig streng, weil die "
                "Precision-Familie der Absicherung dient und nicht der Bestaetigung."
            ),
            _hinweis_ohne_meldung(ohne_meldung),
        ),
    )


def _hinweis_ohne_meldung(ohne_meldung: Sequence[str]) -> str:
    """Formuliert den Vorbehalt zum Precision-Vergleich gegen eine leere Meldungsmenge.

    Args:
        ohne_meldung: Klassen, in denen B0 nichts gemeldet hat.

    Returns:
        Den Hinweistext.
    """
    if not ohne_meldung:
        return (
            "B0 meldet in jeder Fehlerklasse mindestens eine Zelle; die Precision-Vergleiche "
            "stellen damit durchgehend zwei Messungen nebeneinander."
        )
    return (
        f"ACHTUNG bei der Deutung der Precision: In den Klassen {list(ohne_meldung)} meldet "
        "B0 ueberhaupt nichts. Seine Precision ist dort konventionsgemaess 0,0 — das heisst "
        "'keine Meldung' und nicht 'alle Meldungen falsch'. Ein Precision-Vergleich gegen "
        "diese Null stellt eine Messung neben eine Festlegung; die Precision-Bedingung von "
        "HYP1 ist nur in den uebrigen Klassen inhaltlich geprueft."
    )


def pruefe_hyp2(lang: pd.DataFrame, plan: Versuchsplan) -> Hypothesenergebnis:
    """Prueft HYP2: Der Recall des Prototyps unterscheidet sich zwischen den Klassen.

    Primaertest ist der Friedman-Test ueber alle sieben Klassen auf denselben
    Bloecken (Wiederholungen). Erst wenn er signifikant ist, sind die
    einundzwanzig paarweisen Vergleiche interpretierbar — sonst waeren sie ein
    Fischzug.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Das Hypothesenergebnis.
    """
    alpha = plan.statistik.alpha
    klassen = _klassen(plan)
    je_klasse = {
        klasse: _reihe(lang, metrik="recall", verfahren=_PROTOTYP, klasse=klasse)
        for klasse in klassen
    }
    laengen = {len(werte) for werte in je_klasse.values()}
    if len(laengen) != 1:
        raise AuswertungsFehler(
            f"Die Klassen haben verschieden viele Wiederholungen: {laengen}. Der "
            "Friedman-Test setzt vollstaendige Bloecke voraus."
        )
    matrix = [
        [je_klasse[klasse][block] for klasse in klassen] for block in range(next(iter(laengen)))
    ]
    primaer = friedman(matrix)

    paarweise: list[tuple[str, Testergebnis]] = []
    for erste in range(len(klassen)):
        for zweite in range(erste + 1, len(klassen)):
            a, b = klassen[erste], klassen[zweite]
            paarweise.append((f"{a} gegen {b}", wilcoxon_gepaart(je_klasse[a], je_klasse[b])))

    familie = _familie(
        "HYP2-paarweise",
        "paarweise Klassenvergleiche des Prototyp-Recalls, zweiseitig",
        "recall",
        paarweise,
        alpha=alpha,
    )
    return Hypothesenergebnis(
        kennung="HYP2",
        aussage=(
            "Der Recall des Prototyps unterscheidet sich signifikant zwischen den "
            "Fehlerklassen."
        ),
        primaertest=primaer,
        familien=(familie,),
        entscheidung="gestuetzt" if primaer.p_wert < alpha else "nicht gestuetzt",
        begruendung=(
            f"Friedman-Test ueber {len(klassen)} Klassen und {primaer.n} Bloecke: "
            f"chi2 = {primaer.statistik:.3f}, p = {primaer.p_wert:.3g}, Kendalls W = "
            f"{primaer.effekt:.3f}. Nach Holm-Korrektur sind {familie.signifikante} der "
            f"{familie.anzahl} paarweisen Vergleiche signifikant."
        ),
        hinweise=(
            (
                "Die paarweisen Vergleiche sind nur unter einem signifikanten Friedman-Test "
                "interpretierbar; sonst waeren sie ein Fischzug ueber 21 Kombinationen."
            ),
        ),
    )


def pruefe_hyp3(lang: pd.DataFrame, plan: Versuchsplan) -> Hypothesenergebnis:
    """Prueft HYP3: Die Precision steigt mit der Fehlerrate (Praevalenzeffekt).

    Gerechnet wird auf **beiden** Metrikebenen, und das ist keine Zugabe, sondern
    der Kern der Aussage.

    Auf der **Zellebene** erzeugt jede Injektion ueber mehrspaltige Regeln
    zusaetzliche Zellmeldungen: Eine Regel meldet alle an einem Verstoss
    beteiligten Felder, verfaelscht wurde aber nur eines. Die Zahl dieser
    Scheinfehlalarme waechst mit der Zahl der Injektionen — die Precision steigt
    dadurch **kaum**, obwohl sie es bei konstanter Fehlalarmzahl deutlich
    muesste. Ein gemessener Trend auf dieser Ebene kann damit ebenso gut die
    Berichtskonvention abbilden wie einen Praevalenzeffekt des Verfahrens.

    Auf der **Constraint-Ebene** ist die Einheit der gemeldete Verstoss statt der
    Zelle; die mehrspaltige Meldung zaehlt dort einmal. Bleibt der Trend hier
    bestehen, ist er ein Effekt des Verfahrens. Verschwindet er, war er einer der
    Konvention. Beide Ergebnisse stehen deshalb nebeneinander.

    Primaertest ist ein Page-Trendtest ueber **alle** Bloecke: Ein Block ist ein
    Paar aus Fehlerklasse und Wiederholung, die Ratenstufen bilden die geordneten
    Spalten. Ein Wilcoxon-Test waere hier falsch — er verglicht zwei Stufen ohne
    Ordnung.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Das Hypothesenergebnis.

    Raises:
        AuswertungsFehler: Wenn eine Zelle des Plans fehlt.
    """
    alpha = plan.statistik.alpha
    klassen = _klassen(plan)
    raten = sorted(plan.hauptversuch.raten)

    je_ebene: dict[Ebene, tuple[Testergebnis, Testergebnis, list[tuple[str, Testergebnis]]]] = {}
    for ebene in (Ebene.ZELLE, Ebene.CONSTRAINT):
        gepoolt: list[list[float]] = []
        einzeln: list[tuple[str, Testergebnis]] = []
        rate_werte: list[float] = []
        precision_werte: list[float] = []
        for klasse in klassen:
            bloecke = _bloecke_ueber_raten(
                lang, klasse=klasse, raten=raten, ebene=ebene, rate_werte=rate_werte,
                precision_werte=precision_werte,
            )
            gepoolt.extend(bloecke)
            einzeln.append((klasse, page_trend(bloecke)))
        je_ebene[ebene] = (
            page_trend(gepoolt),
            spearman(rate_werte, precision_werte),
            einzeln,
        )

    primaer, korrelation, einzeln_zelle = je_ebene[Ebene.ZELLE]
    constraint, korrelation_constraint, einzeln_constraint = je_ebene[Ebene.CONSTRAINT]

    familien = (
        _familie(
            "HYP3-Trend-Zelle",
            "Page-Trendtest der Zell-Precision ueber die geordneten Ratenstufen, je Klasse",
            "precision (Zellebene)",
            einzeln_zelle,
            alpha=alpha,
        ),
        _familie(
            "HYP3-Trend-Constraint",
            "Page-Trendtest der Constraint-Precision ueber die geordneten Ratenstufen, "
            "je Klasse",
            "precision (Constraint-Ebene)",
            einzeln_constraint,
            alpha=alpha,
        ),
    )

    auf_zelle = primaer.p_wert < alpha
    auf_constraint = constraint.p_wert < alpha
    if auf_zelle and auf_constraint:
        entscheidung = "gestuetzt"
        deutung = (
            "Der Trend besteht auf beiden Metrikebenen. Er ist damit ein Effekt des "
            "Verfahrens und nicht der Berichtskonvention."
        )
    elif auf_zelle:
        entscheidung = "teilweise gestuetzt"
        deutung = (
            "Der Trend besteht auf der Zellebene und **nicht** auf der Constraint-Ebene. "
            "Damit ist er kein Praevalenzeffekt des Verfahrens, sondern ein Effekt der "
            "Berichtskonvention: Auf der Zellebene erzeugt jede Injektion ueber "
            "mehrspaltige Regeln zusaetzliche Scheinfehlalarme, deren Zahl mit der "
            "Injektionszahl waechst. Auf der Constraint-Ebene, wo dieselbe Meldung einmal "
            "zaehlt, verschwindet er. Das ist eine praezisere Antwort als ein kleines rho."
        )
    else:
        entscheidung = "nicht gestuetzt"
        deutung = "Auf keiner der beiden Metrikebenen besteht ein signifikanter Trend."

    return Hypothesenergebnis(
        kennung="HYP3",
        aussage="Die Precision steigt mit steigender Fehlerrate (Praevalenzeffekt).",
        primaertest=primaer,
        nebentests=(("Constraint-Ebene", constraint),),
        familien=familien,
        entscheidung=entscheidung,
        begruendung=(
            f"Zellebene: Page-Trendtest ueber {primaer.n} Bloecke (Klasse x Wiederholung) "
            f"und {len(raten)} geordnete Ratenstufen, L = {primaer.statistik:.1f}, "
            f"p = {primaer.p_wert:.3g}, Spearman rho = {_zahl(korrelation.effekt)}. "
            f"Constraint-Ebene: L = {constraint.statistik:.1f}, p = {constraint.p_wert:.3g}, "
            f"Spearman rho = {_zahl(korrelation_constraint.effekt)}. Einzeln signifikant "
            f"sind {familien[0].signifikante} von {familien[0].anzahl} Klassen auf der "
            f"Zellebene und {familien[1].signifikante} von {familien[1].anzahl} auf der "
            f"Constraint-Ebene. {deutung}"
        ),
        hinweise=(
            (
                "Wo die Constraint-Precision bereits 1,000 betraegt, kann kein "
                "Praevalenzeffekt mehr entstehen — der Trend ist dort nicht klein, sondern "
                "durch die Obergrenze ausgeschlossen. Das betrifft mehrere Klassen und ist "
                "der Grund, die beiden Ebenen nebeneinanderzustellen statt nur die eine zu "
                "berichten."
            ),
            (
                "UV2 ist erst seit Phase 4b sauber testbar: Das Klassenkontingent wird "
                "proportional zum Universum jeder Variante verteilt, die Variantenmischung "
                "ist damit ueber alle Ratenstufen identisch. Vorher haette ein Trend ueber "
                "die Ratenstufen teils die Rate gemessen und teils eine Verschiebung der "
                "Variantenmischung; HYP3 ist erst dadurch eine Hypothese ueber die "
                "Fehlerrate (docs/iteration_log.md, Phase 4, Befund 4)."
            ),
            (
                "Ein zweiter Confounder derselben Bauart wurde in Phase 5 gefunden und "
                "beseitigt: Kohaerenz, die je Verfaelschung gegen den Ausgangszustand "
                "hergestellt wird, bricht bei Ueberlagerung innerhalb derselben "
                "Bezugsgruppe und waere als scheinbarer Sachtrend von HO2 ueber UV2 "
                "aufgetaucht (docs/iteration_log.md, Befund 14)."
            ),
            (
                "Ein Wilcoxon-Test waere hier das falsche Werkzeug: Er verglicht zwei "
                "Stufen ohne Ordnung und liesse die Information ungenutzt, dass die Stufen "
                "aufsteigend sind."
            ),
        ),
    )


def _bloecke_ueber_raten(  # noqa: PLR0913 - jede Angabe waehlt eine Dimension
    lang: pd.DataFrame,
    *,
    klasse: str,
    raten: Sequence[float],
    ebene: Ebene,
    rate_werte: list[float],
    precision_werte: list[float],
) -> list[list[float]]:
    """Baut die Bloecke einer Klasse ueber die geordneten Ratenstufen.

    Args:
        lang: Das Langformat.
        klasse: Die Fehlerklasse.
        raten: Die Ratenstufen in aufsteigender Reihenfolge.
        ebene: Die Auswertungsebene.
        rate_werte: Sammelliste der Raten fuer die Spearman-Korrelation.
        precision_werte: Sammelliste der Werte fuer die Spearman-Korrelation.

    Returns:
        Je Wiederholung eine Zeile mit einem Wert je Ratenstufe.

    Raises:
        AuswertungsFehler: Wenn die Ratenstufen verschieden viele Wiederholungen
            haben; der Page-Trendtest setzt vollstaendige Bloecke voraus.
    """
    spalten: list[list[float]] = []
    for rate in raten:
        gefiltert = auswahl(
            lang,
            metrik="precision",
            verfahren=_PROTOTYP,
            ebene=ebene,
            gruppe_art=GRUPPE_GESAMT,
            klasse=klasse,
            fehlerrate=rate,
            teilversuch=_HAUPT,
        )
        werte = [float(wert) for wert in mittel_je_wiederholung(gefiltert)]
        spalten.append(werte)
        rate_werte.extend([rate] * len(werte))
        precision_werte.extend(werte)
    laengen = {len(spalte) for spalte in spalten}
    if len(laengen) != 1:
        raise AuswertungsFehler(
            f"Klasse {klasse}, Ebene {ebene.value}: Die Ratenstufen haben verschieden "
            f"viele Wiederholungen ({laengen}); der Page-Trendtest setzt vollstaendige "
            "Bloecke voraus."
        )
    return [
        [spalten[stufe][block] for stufe in range(len(raten))]
        for block in range(next(iter(laengen)))
    ]


def pruefe_hyp4(lang: pd.DataFrame, plan: Versuchsplan) -> Hypothesenergebnis:
    """Prueft HYP4: Der Unterschied zwischen Prototyp und B2 ist klassenabhaengig.

    Primaerebene ist die **Satzebene**, so in Phase 5 festgelegt. Der Grund ist
    nicht Geschmack: B2 markiert ganze Zeilen, und die Umrechnung "markierte
    Zeile markiert alle ihre befuellten Zellen" deckelt seine Zell-Precision auf
    etwa den Kehrwert der Spaltenzahl. Ein Zellvergleich maesse dort zu einem
    grossen Teil die Umrechnung und nicht das Verfahren. Die Zellebene steht als
    Nebentest daneben.

    Das ist eine **Interaktions**hypothese, kein Mittelwertvergleich.
    Primaertest ist deshalb eine ART-ANOVA (Aligned Rank Transform) auf dem
    F1-Wert mit den Faktoren Verfahren und Fehlerklasse; die paarweisen
    Vergleiche je Klasse stehen als Familie daneben und zeigen, **wo** der
    Unterschied liegt.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Das Hypothesenergebnis.
    """
    alpha = plan.statistik.alpha
    klassen = _klassen(plan)

    ergebnisse: dict[Ebene, tuple[Testergebnis, Familie, list[str], list[str]]] = {}
    for ebene, kennung in ((Ebene.SATZ, "Satz"), (Ebene.ZELLE, "Zelle")):
        werte: list[float] = []
        faktor_verfahren: list[str] = []
        faktor_klasse: list[str] = []
        paarweise: list[tuple[str, Testergebnis]] = []
        for klasse in klassen:
            proto = _reihe(lang, metrik="f1", verfahren=_PROTOTYP, klasse=klasse, ebene=ebene)
            baseline = _reihe(lang, metrik="f1", verfahren=_B2, klasse=klasse, ebene=ebene)
            paarweise.append((klasse, wilcoxon_gepaart(proto, baseline)))
            werte.extend(proto)
            faktor_verfahren.extend([_PROTOTYP] * len(proto))
            faktor_klasse.extend([klasse] * len(proto))
            werte.extend(baseline)
            faktor_verfahren.extend([_B2] * len(baseline))
            faktor_klasse.extend([klasse] * len(baseline))

        familie = _familie(
            f"HYP4-paarweise-{kennung}",
            f"F1 des Prototyps gegen B2, je Fehlerklasse, zweiseitig ({kennung}ebene)",
            f"f1 ({kennung}ebene)",
            paarweise,
            alpha=alpha,
        )
        richtungen = {
            vergleich.gruppe: (vergleich.test.effekt or 0.0)
            for vergleich in familie.vergleiche
            if vergleich.signifikant and vergleich.test is not None
        }
        ergebnisse[ebene] = (
            art_anova_interaktion(werte, faktor_verfahren, faktor_klasse),
            familie,
            sorted(name for name, effekt in richtungen.items() if effekt > 0),
            sorted(name for name, effekt in richtungen.items() if effekt < 0),
        )

    primaer, familie_satz, proto_satz, b2_satz = ergebnisse[Ebene.SATZ]
    zelle, familie_zelle, proto_zelle, b2_zelle = ergebnisse[Ebene.ZELLE]

    # Die Hypothese behauptet zweierlei: eine Interaktion **und** eine Richtung
    # ("statistisch gewinnt bei Ausreissern"). Der Test prueft nur das erste.
    # Gewinnt B2 auf der Primaerebene in keiner Klasse, ist die Richtungsaussage
    # widerlegt — und ein blosses "gestuetzt" waere dann die halbe Wahrheit.
    if primaer.p_wert >= alpha:
        entscheidung = "nicht gestuetzt"
    elif b2_satz:
        entscheidung = "gestuetzt"
    else:
        entscheidung = "teilweise gestuetzt"

    return Hypothesenergebnis(
        kennung="HYP4",
        aussage=(
            "Der Unterschied zwischen Prototyp und B2 ist fehlerklassenabhaengig: "
            "regelbasiert gewinnt bei Format- und Regelverletzungen, statistisch bei "
            "Ausreissern."
        ),
        primaertest=primaer,
        nebentests=(("Zellebene", zelle),),
        familien=(familie_satz, familie_zelle),
        entscheidung=entscheidung,
        begruendung=(
            f"ART-ANOVA auf der **Satzebene** (Primaerebene laut Phase 5), Interaktion "
            f"Verfahren x Fehlerklasse auf F1: {primaer.hinweis}, F = {primaer.statistik:.2f}, "
            f"p = {primaer.p_wert:.3g}, partielles Eta-Quadrat = {primaer.effekt:.3f}. "
            f"Nach Holm-Korrektur gewinnt der Prototyp in {len(proto_satz)} Klassen "
            f"({proto_satz}), B2 in {len(b2_satz)} Klassen ({b2_satz}). Zur Kontrolle die "
            f"Zellebene: F = {zelle.statistik:.2f}, p = {zelle.p_wert:.3g}; dort gewinnt "
            f"der Prototyp in {len(proto_zelle)} und B2 in {len(b2_zelle)} Klassen."
            + (
                ""
                if b2_satz
                else (
                    " Die Hypothese behauptet zweierlei: eine Interaktion und eine "
                    "Richtung. Die Interaktion ist belegt — der Abstand zwischen den "
                    "Verfahren haengt deutlich von der Fehlerklasse ab. Die "
                    "Richtungsaussage 'statistisch gewinnt bei Ausreissern' ist es "
                    "**nicht**: B2 liegt auch auf der Satzebene in keiner einzigen Klasse "
                    "vorn. Deshalb 'teilweise gestuetzt' und nicht 'gestuetzt'."
                )
            )
        ),
        hinweise=(
            (
                "Die Satzebene ist die Primaerebene des B2-Vergleichs, so in Phase 5 "
                "festgelegt. B2 markiert ganze Zeilen; die Umrechnung 'markierte Zeile "
                "markiert alle ihre befuellten Zellen' deckelt seine Zell-Precision auf "
                "etwa den Kehrwert der Spaltenzahl. Ein Zellvergleich maesse dort zu einem "
                "grossen Teil die Umrechnung und nicht das Verfahren. Genau deshalb steht "
                "die Zellebene hier als Nebentest und nicht als Ergebnis."
            ),
            (
                "B2 waehlt seine contamination-Stufe ueber die beste F1 der Satzebene und "
                "bekommt dafuer den Ground Truth zu sehen. Das ist eine bewusst "
                "optimistische Einstellung **zugunsten der Baseline**; der Prototyp bekommt "
                "keine vergleichbare Anpassung. Ein Verfahren, das trotz dieses Vorteils "
                "auf seiner eigenen Primaerebene in keiner Klasse gewinnt, verliert "
                "ueberzeugend."
            ),
            (
                "Die ART-ANOVA prueft die Interaktion auf Raengen der um beide "
                "Haupteffekte bereinigten Werte; sie setzt keine Normalitaet voraus. Der "
                "p-Wert bezieht sich ausschliesslich auf den Interaktionsterm."
            ),
        ),
    )


def alle_hypothesen(lang: pd.DataFrame, plan: Versuchsplan) -> tuple[Hypothesenergebnis, ...]:
    """Prueft alle vier Hypothesen.

    Args:
        lang: Das Langformat.
        plan: Der Versuchsplan.

    Returns:
        Die vier Ergebnisse in der Reihenfolge HYP1 bis HYP4.
    """
    return (
        pruefe_hyp1(lang, plan),
        pruefe_hyp2(lang, plan),
        pruefe_hyp3(lang, plan),
        pruefe_hyp4(lang, plan),
    )


# ---------------------------------------------------------------------------
# Ausgabe
# ---------------------------------------------------------------------------


def _test_als_dict(test: Testergebnis) -> dict[str, Any]:
    """Wandelt ein Testergebnis in ein JSON-faehiges Woerterbuch."""
    return {
        "test": test.test,
        "statistik": round(test.statistik, 6),
        "p_wert": test.p_wert,
        "effekt": None if test.effekt is None else round(test.effekt, 6),
        "effektmass": test.effektmass,
        "n": test.n,
        "seitig": test.seitig,
        "hinweis": test.hinweis,
    }


def hypothesen_als_dict(
    ergebnisse: Sequence[Hypothesenergebnis], *, alpha: float = STANDARD_ALPHA, warnung: str = ""
) -> dict[str, Any]:
    """Stellt die Hypothesenergebnisse fuer ``results/hypothesen.json`` zusammen.

    Args:
        ergebnisse: Die Hypothesenergebnisse.
        alpha: Das verwendete Signifikanzniveau.
        warnung: Warnung zur Stichprobengroesse; leer, wenn keine noetig ist.

    Returns:
        Das JSON-faehige Woerterbuch.
    """
    return {
        "alpha": alpha,
        "korrektur": "Holm-Bonferroni je Familie",
        "aggregationsebene": "ueber die Fehlerraten aggregiert, je Fehlerklasse getestet",
        "warnung_stichprobengroesse": warnung,
        "hypothesen": [
            {
                "kennung": ergebnis.kennung,
                "aussage": ergebnis.aussage,
                "entscheidung": ergebnis.entscheidung,
                "begruendung": ergebnis.begruendung,
                "primaertest": (
                    None if ergebnis.primaertest is None else _test_als_dict(ergebnis.primaertest)
                ),
                "nebentests": [
                    {"bezeichnung": bezeichnung, **_test_als_dict(test)}
                    for bezeichnung, test in ergebnis.nebentests
                ],
                "familien": [
                    {
                        "kennung": familie.kennung,
                        "beschreibung": familie.beschreibung,
                        "kennzahl": familie.kennzahl,
                        "vergleiche_in_der_familie": familie.anzahl,
                        "berichtete_zeilen": familie.berichtet,
                        "nicht_anwendbar": familie.nicht_anwendbar,
                        "davon_signifikant": familie.signifikante,
                        "hinweis_familiengroesse": (
                            "Die Holm-Korrektur laeuft ueber die anwendbaren Vergleiche; "
                            "nicht durchgefuehrte Tests erhoehen die Familiengroesse nicht."
                        ),
                        "vergleiche": [
                            {
                                "gruppe": vergleich.gruppe,
                                "anwendbar": vergleich.anwendbar,
                                "grund": vergleich.grund,
                                "p_korrigiert": vergleich.p_korrigiert,
                                "signifikant": vergleich.signifikant,
                                **(
                                    _test_als_dict(vergleich.test)
                                    if vergleich.test is not None
                                    else {}
                                ),
                            }
                            for vergleich in familie.vergleiche
                        ],
                    }
                    for familie in ergebnis.familien
                ],
                "hinweise": list(ergebnis.hinweise),
            }
            for ergebnis in ergebnisse
        ],
    }


def _p_text(wert: float | None) -> str:
    """Formatiert einen p-Wert lesbar und ohne falsche Genauigkeit.

    ``None`` heisst "nicht durchgefuehrt" und bekommt einen Gedankenstrich. Eine
    Null waere hier das schlechteste aller Zeichen: Sie liest sich wie ein
    hochsignifikantes Ergebnis.
    """
    if wert is None:
        return "—"
    if wert < _P_SCHWELLE:
        return "< 0,001"
    return f"{wert:.3f}".replace(".", ",")


def _zahl(wert: float | None, stellen: int = 3) -> str:
    """Formatiert eine Zahl mit deutschem Dezimalkomma."""
    if wert is None:
        return "—"
    return f"{wert:.{stellen}f}".replace(".", ",")


def als_markdown(  # noqa: C901, PLR0912 - eine Verzweigung je Ausgabeteil, alle flach
    ergebnisse: Sequence[Hypothesenergebnis], *, alpha: float = STANDARD_ALPHA, warnung: str = ""
) -> str:
    """Formatiert die Hypothesenergebnisse als Markdown-Tabellen.

    Args:
        ergebnisse: Die Hypothesenergebnisse.
        alpha: Das verwendete Signifikanzniveau.
        warnung: Warnung zur Stichprobengroesse; leer, wenn keine noetig ist.

    Returns:
        Den vollstaendigen Inhalt von ``results/hypothesen.md``.
    """
    zeilen = [
        "# Hypothesen HYP1 bis HYP4",
        "",
        "Erzeugt von `scripts/analyze.py`. Jede Zahl stammt aus",
        "`results/metrics_long.parquet`; jede Zeile dort traegt eine `run_id`, die alle",
        "Faktorstufen ihres Laufs kodiert.",
        "",
        f"- Signifikanzniveau: alpha = {_zahl(alpha, 2)}",
        "- Multiplizitaetskorrektur: Holm-Bonferroni, **je Familie getrennt**",
        "- Aggregationsebene: ueber die Fehlerraten aggregiert, je Fehlerklasse getestet",
        "- Kein t-Test: F1-Verteilungen sind nach oben beschraenkt und nicht normalverteilt.",
        "",
        "**Namensgebung.** HYP1 bis HYP4 sind die Hypothesen, HO1 und HO2 die beiden",
        "Held-out-Fehlerklassen. Die Held-out-Klassen kommen in keiner Hypothese vor —",
        "sie sind der Teilversuch T2 und werden deskriptiv berichtet. Eine Hypothese",
        "„der Recall ist null“ waere eine Nullhypothese, und die laesst sich nicht",
        "bestaetigen.",
        "",
    ]
    if warnung:
        zeilen += [
            "> **Warnung zur Stichprobengroesse**",
            ">",
            *[f"> {zeile}" for zeile in warnung.splitlines()],
            "",
        ]

    zeilen += [
        "## Ueberblick",
        "",
        "| Hypothese | Primaertest | p | Effektstaerke | Entscheidung |",
        "|---|---|---|---|---|",
    ]
    for ergebnis in ergebnisse:
        test = ergebnis.primaertest
        if test is None:
            zeilen.append(
                f"| {ergebnis.kennung} | zwei Familien gepaarter Wilcoxon-Tests | — | — | "
                f"{ergebnis.entscheidung} |"
            )
        else:
            zeilen.append(
                f"| {ergebnis.kennung} | {test.test} | {_p_text(test.p_wert)} | "
                f"{test.effektmass} = {_zahl(test.effekt)} | {ergebnis.entscheidung} |"
            )
    zeilen.append("")

    for ergebnis in ergebnisse:
        zeilen += [f"## {ergebnis.kennung}", "", f"> {ergebnis.aussage}", ""]
        if ergebnis.primaertest is not None:
            test = ergebnis.primaertest
            zeilen += [
                f"**Primaertest:** {test.test} ({test.seitig}), n = {test.n}.",
                "",
                f"- Teststatistik: {_zahl(test.statistik)}",
                f"- p (unkorrigiert): {_p_text(test.p_wert)}",
                f"- {test.effektmass}: {_zahl(test.effekt)}",
            ]
            if test.hinweis:
                zeilen.append(f"- Hinweis: {test.hinweis}")
            zeilen.append("")
        if ergebnis.nebentests:
            zeilen += [
                "**Dieselbe Hypothese auf der anderen Metrikebene.** Kein Zusatzmaterial:",
                "Ein Effekt, der auf der einen Ebene besteht und auf der anderen",
                "verschwindet, ist ein Effekt der Berichtskonvention und keiner des",
                "Verfahrens.",
                "",
                "| Ebene | Test | Statistik | p | Effektstaerke |",
                "|---|---|---|---|---|",
            ]
            zeilen += [
                (
                    f"| {bezeichnung} | {test.test} | {_zahl(test.statistik, 1)} | "
                    f"{_p_text(test.p_wert)} | {test.effektmass} = {_zahl(test.effekt)} |"
                )
                for bezeichnung, test in ergebnis.nebentests
            ]
            zeilen.append("")
        zeilen += [f"**Entscheidung: {ergebnis.entscheidung}.** {ergebnis.begruendung}", ""]

        for familie in ergebnis.familien:
            zeilen += [
                f"### Familie {familie.kennung} — {familie.anzahl} Vergleiche",
                "",
                f"{familie.beschreibung}. Kennzahl: `{familie.kennzahl}`.",
                "",
                (
                    f"- **Groesse der Holm-Familie: {familie.anzahl}** — so viele Vergleiche "
                    "wurden tatsaechlich durchgefuehrt, und ueber genau diese laeuft die "
                    "Korrektur."
                ),
                (
                    f"- Berichtete Zeilen: {familie.berichtet}, davon nicht anwendbar: "
                    f"{familie.nicht_anwendbar}."
                ),
                (
                    f"- Nach Holm-Korrektur signifikant: {familie.signifikante} von "
                    f"{familie.anzahl}."
                ),
                "",
                "| Gruppe | n | Statistik | p roh | p korrigiert | Effektstaerke | signifikant |",
                "|---|---|---|---|---|---|---|",
            ]
            for vergleich in familie.vergleiche:
                test = vergleich.test
                if test is None:
                    zeilen.append(
                        f"| {vergleich.gruppe} | — | — | — | — | — | **nicht anwendbar** |"
                    )
                    continue
                zeilen.append(
                    f"| {vergleich.gruppe} | {test.n} | {_zahl(test.statistik, 1)} | "
                    f"{_p_text(test.p_wert)} | {_p_text(vergleich.p_korrigiert)} | "
                    f"{test.effektmass} = {_zahl(test.effekt)} | "
                    f"{'ja' if vergleich.signifikant else 'nein'} |"
                )
            zeilen.append("")
            nicht_anwendbare = [
                vergleich for vergleich in familie.vergleiche if not vergleich.anwendbar
            ]
            if nicht_anwendbare:
                zeilen += [
                    "Nicht anwendbar und deshalb **nicht** Teil der Holm-Familie:",
                    "",
                    *[
                        f"- **{vergleich.gruppe}**: {vergleich.grund}"
                        for vergleich in nicht_anwendbare
                    ],
                    "",
                ]

        if ergebnis.hinweise:
            zeilen.append("**Zur Einordnung.**")
            zeilen.append("")
            zeilen += [f"- {hinweis}" for hinweis in ergebnis.hinweise]
            zeilen.append("")

    return "\n".join(zeilen) + "\n"
