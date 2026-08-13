"""Inferenzstatistik der Phase 6: Konfidenzintervalle, Tests, Effektstaerken.

Dieses Modul rechnet, es entscheidet nicht. Welche Hypothese mit welchem Test
geprueft wird, steht in :mod:`src.evaluation.hypothesen`; welche Zahlen in welche
Tabelle kommen, in :mod:`src.evaluation.tabellen`. Hier stehen nur die Verfahren
— und die sechs Festlegungen, die sie tragen.

1. Kein t-Test, nirgends
------------------------

F1-Verteilungen sind nach oben durch 1 beschraenkt, oft linksschief und bei den
Held-out-Klassen auf einen einzigen Wert entartet. Ein t-Test setzte Normalitaet
und unbeschraenkten Traeger voraus; beides ist hier verletzt, und bei zwanzig
Seeds hilft auch der zentrale Grenzwertsatz nicht weiter. Verwendet werden
durchgehend Rangverfahren. REIN (Rekatsinas et al.) tut dasselbe.

2. Gepaart, wo die Paarung existiert
-------------------------------------

Prototyp, B0 und B2 sehen in einem Lauf **denselben** verfaelschten Datensatz.
Ihre Ergebnisse sind damit gepaart, und der gepaarte Wilcoxon-Test ist deutlich
trennschaerfer als der ungepaarte Mann-Whitney-Test. Die Paarung ist kein Detail:
Sie ist der Grund, warum ein Lauf alle Verfahren auf einmal auswertet statt drei
getrennte Laeufe je Zelle zu fahren.

3. Zum Test passende Effektstaerke
-----------------------------------

Zum gepaarten Wilcoxon-Test gehoert die *matched-pairs rank-biserial
correlation* ``r = (W+ - W-) / (W+ + W-)``. Fuer ungepaarte Vergleiche steht
Cliff's Delta daneben.

**Nicht** berichtet wird Vargha-Delaney A12. Es gilt exakt ``delta = 2*A12 - 1``;
beide Masse nebeneinander waeren dieselbe Information in zwei Skalen und fielen
in jedem Kolloquium auf.

4. Der Bootstrap muss entarten duerfen
---------------------------------------

Die BCa-Beschleunigung wird aus einem Jackknife geschaetzt. Sind alle Werte
gleich — bei den Held-out-Klassen mit Recall null der **Erwartungsfall** —, ist
die Jackknife-Streuung null und die Beschleunigung ein Bruch ``0/0``. Ohne
Abfangen bricht ausgerechnet die Abbildung, die das "inwieweit" der
Forschungsfrage beantwortet.

:func:`bootstrap_ci` faengt den Fall ab und weicht auf ein exaktes
Clopper-Pearson-Intervall aus, sobald der Aufrufer die zugrunde liegenden
Anteilszahlen mitgibt. Das Ergebnis sagt in seinem Feld ``verfahren`` immer,
welcher Weg genommen wurde — ein Intervall, dem man nicht ansieht, wie es
entstanden ist, ist in einer Ergebnistabelle wertlos.

5. Holm-Bonferroni je Familie, und die Familie wird benannt
------------------------------------------------------------

:func:`holm` korrigiert eine Familie von p-Werten. Welche Vergleiche eine Familie
bilden, entscheidet der Aufrufer und **schreibt es in den Bericht**. Die
Aggregationsebene ist vorab festgelegt: ueber die Fehlerraten aggregieren, je
Klasse testen. Wird zusaetzlich je Rate getestet, vervierfacht sich die Zahl der
Vergleiche, und das muss dann im Text stehen.

6. Kleine Stichproben werden mit Zahlen gewarnt, nicht mit Stimmung
--------------------------------------------------------------------

:func:`seed_warnung` rechnet die Grenzen des exakten Wilcoxon-Tests fuer die
tatsaechliche Zahl der Wiederholungen aus. Eine pauschale Warnung ("praktisch
kein Spielraum") waere schlicht falsch: Bei zehn Paaren und sieben Vergleichen
sind die beiden kleinsten erreichbaren p-Werte nach Holm-Korrektur immer noch
signifikant; erst bei einundzwanzig Vergleichen wird es eng. Der Unterschied
gehoert in den Bericht, weil der Bericht in die Arbeit wandert.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final

import numpy as np

from src.common.seeding import Strom, generator, lauf_seed
from src.evaluation.metriken import clopper_pearson
from src.evaluation.modell import AuswertungsFehler

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence

    from numpy.typing import NDArray

__all__ = [
    "STANDARD_ALPHA",
    "STANDARD_RESAMPLES",
    "Intervall",
    "Intervallart",
    "Testergebnis",
    "art_anova_interaktion",
    "bootstrap_ci",
    "cliffs_delta",
    "friedman",
    "holm",
    "page_trend",
    "rang_biserial",
    "seed_warnung",
    "spearman",
    "wilcoxon_gepaart",
]

#: Irrtumswahrscheinlichkeit der Konfidenzintervalle und Tests.
STANDARD_ALPHA: Final[float] = 0.05

#: Zahl der Bootstrap-Ziehungen.
STANDARD_RESAMPLES: Final[int] = 10000

#: Ab dieser Zahl von Paaren rechnet der Wilcoxon-Test genaehert statt exakt.
#:
#: Die exakte Verteilung hat ``2**n`` Auspraegungen; oberhalb dieser Grenze ist
#: die Normalapproximation genau genug und deutlich schneller. Der Wert ist der
#: Vorgabewert von SciPy und wird hier nur sichtbar gemacht.
_EXAKT_BIS: Final[int] = 25

#: So viele Gruppen braucht ein Friedman- oder Page-Test mindestens.
_MINDESTGRUPPEN: Final[int] = 3

#: Eine Bloecke-mal-Gruppen-Matrix hat genau zwei Dimensionen.
_MATRIXDIMENSIONEN: Final[int] = 2

#: So viele Stufen braucht ein Faktor der ART-ANOVA mindestens.
_MINDESTSTUFEN: Final[int] = 2

#: Vorgesehene Zahl der Wiederholungen je Zelle (Phasenprompt, Aufgabe 1).
#:
#: Unterhalb dieser Zahl gibt :func:`seed_warnung` eine sichtbare Warnung aus.
_MINDESTWIEDERHOLUNGEN: Final[int] = 20


class Intervallart(StrEnum):
    """Wie ein Konfidenzintervall zustande gekommen ist.

    Steht in jeder Ergebnistabelle neben den Grenzen. Ein Intervall, dem man
    nicht ansieht, aus welchem Verfahren es stammt, laedt zu Fehlschluessen ein —
    besonders dann, wenn zwei Zeilen derselben Tabelle aus verschiedenen
    Verfahren stammen.
    """

    BCA = "bca"
    """Bias-corrected and accelerated Bootstrap ueber die Wiederholungen."""

    CLOPPER_PEARSON = "clopper-pearson"
    """Exaktes Intervall fuer einen Anteil; Ausweichweg bei entartetem Bootstrap."""

    ENTARTET = "entartet"
    """Alle Werte gleich und keine Anteilszahlen bekannt: Punkt statt Intervall."""


@dataclass(frozen=True, slots=True)
class Intervall:
    """Ein Konfidenzintervall samt Herkunft.

    Attributes:
        punkt: Der Schaetzwert selbst.
        unten: Untere Grenze.
        oben: Obere Grenze.
        art: Verfahren, aus dem das Intervall stammt.
        n: Zahl der eingegangenen Beobachtungen.
        hinweis: Klartext, wenn der Ausweichweg genommen wurde; sonst leer.
    """

    punkt: float
    unten: float
    oben: float
    art: Intervallart
    n: int
    hinweis: str = ""


@dataclass(frozen=True, slots=True)
class Testergebnis:
    """Das Ergebnis eines Hypothesentests.

    Attributes:
        test: Name des Verfahrens, zum Beispiel ``"Wilcoxon-Vorzeichen-Rangtest"``.
        statistik: Die Teststatistik.
        p_wert: Der unkorrigierte p-Wert.
        effekt: Die Effektstaerke; ``None``, wo keine definiert ist.
        effektmass: Name der Effektstaerke.
        n: Zahl der Beobachtungen beziehungsweise Bloecke.
        seitig: ``"zweiseitig"`` oder ``"einseitig"``.
        hinweis: Klartext zu Besonderheiten, etwa entarteten Differenzen.
    """

    test: str
    statistik: float
    p_wert: float
    effekt: float | None
    effektmass: str
    n: int
    seitig: str
    hinweis: str = ""


# ---------------------------------------------------------------------------
# Konfidenzintervalle
# ---------------------------------------------------------------------------


def _namensfaktor(name: str) -> int:
    """Kodiert einen Namen prozessuebergreifend stabil als ganze Zahl.

    Dieselbe Begruendung wie in ``scripts/inject.py``: ``hash()`` streut
    Zeichenketten je Prozess anders, SHA-256 nicht. Zwei Auswertungen desselben
    Datenbestands muessen dasselbe Konfidenzintervall liefern.

    Args:
        name: Der zu kodierende Name; die leere Zeichenkette ist zulaessig.

    Returns:
        Die Kodierung als nicht negative ganze Zahl.
    """
    return int.from_bytes(hashlib.sha256(name.encode("utf-8")).digest()[:8], "big")


def _als_array(werte: Sequence[float], name: str) -> NDArray[np.float64]:
    """Wandelt eine Wertefolge in ein Gleitkommaarray und prueft sie.

    Args:
        werte: Die Werte.
        name: Bezeichnung fuer die Fehlermeldung.

    Returns:
        Das Array.

    Raises:
        AuswertungsFehler: Bei leerer Folge oder nicht endlichen Werten.
    """
    array = np.asarray(werte, dtype=np.float64)
    if array.size == 0:
        raise AuswertungsFehler(f"{name} ist leer; eine Statistik braucht Beobachtungen.")
    if not np.all(np.isfinite(array)):
        raise AuswertungsFehler(f"{name} enthaelt nicht endliche Werte: {array.tolist()}")
    return array


def _jackknife_beschleunigung(werte: NDArray[np.float64]) -> float | None:
    """Schaetzt die BCa-Beschleunigung ueber einen Jackknife.

    Args:
        werte: Die Beobachtungen.

    Returns:
        Die Beschleunigung, oder ``None``, wenn die Jackknife-Streuung null ist —
        genau der Entartungsfall, den der Modul-Docstring beschreibt.
    """
    anzahl = werte.size
    summe = werte.sum()
    weglassen = (summe - werte) / (anzahl - 1)
    abweichung = weglassen.mean() - weglassen
    nenner = float((abweichung**2).sum()) ** 1.5
    if nenner == 0.0:
        return None
    return float((abweichung**3).sum() / (6.0 * nenner))


def bootstrap_ci(  # noqa: PLR0913 - jede Angabe steuert einen eigenen Aspekt
    werte: Sequence[float],
    *,
    alpha: float = STANDARD_ALPHA,
    resamples: int = STANDARD_RESAMPLES,
    seed: int = 0,
    gruppe: str = "",
    anteil: tuple[int, int] | None = None,
) -> Intervall:
    """Berechnet ein BCa-Bootstrap-Intervall fuer den Mittelwert.

    Der Zufallsstrom entsteht ueber :func:`~src.common.seeding.lauf_seed` und
    nicht ueber den globalen NumPy-Generator: Zwei Auswertungen desselben
    Datenbestands muessen dasselbe Intervall liefern (Architekturregel A2).

    Entartet der Bootstrap — alle Werte gleich, damit Jackknife-Streuung null und
    die Beschleunigung ``0/0`` —, wird auf ein exaktes Clopper-Pearson-Intervall
    ausgewichen, sofern ``anteil`` die zugrunde liegenden Zahlen liefert. Das ist
    bei den Held-out-Klassen mit Recall null der Regelfall und kein Sonderfall.

    Args:
        werte: Die Beobachtungen, ueblicherweise eine Kennzahl je Wiederholung.
        alpha: Irrtumswahrscheinlichkeit; ``0.05`` ergibt ein 95-Prozent-Intervall.
        resamples: Zahl der Bootstrap-Ziehungen.
        seed: Nummer des Zufallsstroms aus dem Versuchsplan.
        gruppe: Bezeichnung der bootstrappten Gruppe, etwa ``"prototyp|F3|recall"``.
            Sie geht ueber SHA-256 in die Entropie ein, damit nicht alle Gruppen
            dieselben Ziehungsindizes bekommen — bei gleichen Indizes waeren die
            Intervalle benachbarter Gruppen kuenstlich gleichfoermig. ``hash()``
            waere hier falsch: Python streut Zeichenketten je Prozess anders.
        anteil: ``(Treffer, Versuche)`` ueber alle Wiederholungen zusammen. Wird
            nur im Entartungsfall gebraucht; ``None`` fuehrt dort zu einem
            Punktintervall mit Vermerk.

    Returns:
        Das Intervall samt Herkunftsangabe.

    Raises:
        AuswertungsFehler: Bei leerer Wertefolge, nicht endlichen Werten oder
            einem ``alpha`` ausserhalb von ``(0, 1)``.
    """
    from scipy.stats import norm  # noqa: PLC0415 - Importkosten nur bei Bedarf

    array = _als_array(werte, "Die Wertefolge des Bootstrap")
    if not 0.0 < alpha < 1.0:
        raise AuswertungsFehler(f"alpha muss in (0, 1) liegen, erhalten wurde {alpha}.")
    punkt = float(array.mean())
    anzahl = array.size

    beschleunigung = _jackknife_beschleunigung(array) if anzahl > 1 else None
    if beschleunigung is None:
        return _entartet(punkt, anzahl, alpha=alpha, anteil=anteil)

    strom = generator(
        lauf_seed(seed, Strom.STATISTIK, _namensfaktor(gruppe), anzahl, resamples)
    )
    ziehungen = strom.integers(0, anzahl, size=(resamples, anzahl))
    replikate = array[ziehungen].mean(axis=1)

    kleiner = float(np.count_nonzero(replikate < punkt)) / resamples
    if kleiner in (0.0, 1.0):
        return _entartet(punkt, anzahl, alpha=alpha, anteil=anteil)
    z0 = float(norm.ppf(kleiner))

    grenzen = []
    for wahrscheinlichkeit in (alpha / 2, 1 - alpha / 2):
        z = z0 + float(norm.ppf(wahrscheinlichkeit))
        angepasst = z0 + z / (1 - beschleunigung * z)
        grenzen.append(float(np.quantile(replikate, float(norm.cdf(angepasst)))))
    return Intervall(
        punkt=punkt,
        unten=min(grenzen),
        oben=max(grenzen),
        art=Intervallart.BCA,
        n=anzahl,
    )


def _entartet(
    punkt: float, anzahl: int, *, alpha: float, anteil: tuple[int, int] | None
) -> Intervall:
    """Bildet das Intervall, wenn der Bootstrap entartet ist.

    Args:
        punkt: Der Schaetzwert.
        anzahl: Zahl der Beobachtungen.
        alpha: Irrtumswahrscheinlichkeit.
        anteil: ``(Treffer, Versuche)``, oder ``None``.

    Returns:
        Ein Clopper-Pearson-Intervall, wenn die Anteilszahlen vorliegen, sonst
        ein Punktintervall mit Vermerk.
    """
    if anteil is not None:
        treffer, versuche = anteil
        unten, oben = clopper_pearson(treffer, versuche, alpha=alpha)
        return Intervall(
            punkt=punkt,
            unten=unten,
            oben=oben,
            art=Intervallart.CLOPPER_PEARSON,
            n=anzahl,
            hinweis=(
                f"Der Bootstrap entartet — alle {anzahl} Wiederholungen liefern denselben "
                f"Wert. Ausgewichen auf das exakte Clopper-Pearson-Intervall fuer "
                f"{treffer} von {versuche}."
            ),
        )
    return Intervall(
        punkt=punkt,
        unten=punkt,
        oben=punkt,
        art=Intervallart.ENTARTET,
        n=anzahl,
        hinweis=(
            f"Der Bootstrap entartet — alle {anzahl} Wiederholungen liefern denselben Wert, "
            "und es wurden keine Anteilszahlen fuer den Ausweichweg uebergeben."
        ),
    )


# ---------------------------------------------------------------------------
# Gepaarte Verfahren
# ---------------------------------------------------------------------------


def _rangsummen(differenzen: NDArray[np.float64]) -> tuple[float, float]:
    """Bildet die beiden Rangsummen des Vorzeichen-Rangtests.

    Nullwertige Differenzen bleiben aussen vor (Wilcoxons eigenes Verfahren);
    Bindungen bekommen mittlere Raenge.

    Args:
        differenzen: Die paarweisen Differenzen.

    Returns:
        ``(W+, W-)`` — die Rangsumme der positiven und die der negativen
        Differenzen.
    """
    from scipy.stats import rankdata  # noqa: PLC0415 - Importkosten nur bei Bedarf

    ohne_null = differenzen[differenzen != 0]
    if ohne_null.size == 0:
        return (0.0, 0.0)
    raenge = rankdata(np.abs(ohne_null))
    positiv = float(raenge[ohne_null > 0].sum())
    negativ = float(raenge[ohne_null < 0].sum())
    return (positiv, negativ)


def rang_biserial(a: Sequence[float], b: Sequence[float]) -> float:
    """Berechnet die matched-pairs rank-biserial correlation.

    ``r = (W+ - W-) / (W+ + W-)``. Der Wert liegt in ``[-1, 1]``; positiv heisst
    "``a`` liegt ueber ``b``". Das ist die zum gepaarten Wilcoxon-Test **passende**
    Effektstaerke — anders als Cohens d, das eine Standardabweichung voraussetzt,
    die es bei Rangverfahren nicht gibt.

    Args:
        a: Erste Messreihe.
        b: Zweite Messreihe, paarweise zugeordnet.

    Returns:
        Die Effektstaerke; ``0.0``, wenn alle Differenzen null sind.

    Raises:
        AuswertungsFehler: Wenn die Reihen verschieden lang sind.
    """
    erste = _als_array(a, "Die erste Messreihe")
    zweite = _als_array(b, "Die zweite Messreihe")
    if erste.size != zweite.size:
        raise AuswertungsFehler(
            f"Gepaarte Reihen muessen gleich lang sein, waren {erste.size} und {zweite.size}."
        )
    positiv, negativ = _rangsummen(erste - zweite)
    if positiv + negativ == 0:
        return 0.0
    return (positiv - negativ) / (positiv + negativ)


def wilcoxon_gepaart(
    a: Sequence[float], b: Sequence[float], *, seitig: str = "zweiseitig"
) -> Testergebnis:
    """Fuehrt den gepaarten Wilcoxon-Vorzeichen-Rangtest durch.

    Args:
        a: Erste Messreihe, zum Beispiel der Prototyp je Seed.
        b: Zweite Messreihe, zum Beispiel B0 je Seed.
        seitig: ``"zweiseitig"`` oder ``"einseitig"`` (Alternative ``a > b``).

    Returns:
        Das Testergebnis mit ``W+`` als Statistik und der rank-biserial
        correlation als Effektstaerke.

    Raises:
        AuswertungsFehler: Bei verschieden langen Reihen oder unbekannter
            Seitigkeit.
    """
    from scipy.stats import wilcoxon  # noqa: PLC0415 - Importkosten nur bei Bedarf

    erste = _als_array(a, "Die erste Messreihe")
    zweite = _als_array(b, "Die zweite Messreihe")
    if erste.size != zweite.size:
        raise AuswertungsFehler(
            f"Gepaarte Reihen muessen gleich lang sein, waren {erste.size} und {zweite.size}."
        )
    if seitig not in ("zweiseitig", "einseitig"):
        raise AuswertungsFehler(f"Unbekannte Seitigkeit: {seitig!r}.")

    differenzen = erste - zweite
    positiv, negativ = _rangsummen(differenzen)
    paare_ohne_null = int(np.count_nonzero(differenzen))

    if paare_ohne_null == 0:
        return Testergebnis(
            test="Wilcoxon-Vorzeichen-Rangtest",
            statistik=0.0,
            p_wert=1.0,
            effekt=0.0,
            effektmass="rank-biserial r",
            n=erste.size,
            seitig=seitig,
            hinweis=(
                "Alle Differenzen sind null: Die beiden Verfahren liefern auf jedem Seed "
                "denselben Wert. Der Test ist dann nicht anwendbar, und p = 1 ist keine "
                "Messung, sondern die Feststellung, dass es nichts zu messen gibt."
            ),
        )

    alternative = "two-sided" if seitig == "zweiseitig" else "greater"
    methode = "exact" if paare_ohne_null <= _EXAKT_BIS else "approx"
    ergebnis = wilcoxon(
        erste, zweite, alternative=alternative, method=methode, zero_method="wilcox"
    )
    return Testergebnis(
        test="Wilcoxon-Vorzeichen-Rangtest",
        statistik=positiv,
        p_wert=float(ergebnis.pvalue),
        effekt=(positiv - negativ) / (positiv + negativ),
        effektmass="rank-biserial r",
        n=erste.size,
        seitig=seitig,
        hinweis=f"{methode}; {paare_ohne_null} von {erste.size} Paaren mit Differenz ungleich null",
    )


def cliffs_delta(a: Sequence[float], b: Sequence[float]) -> float:
    """Berechnet Cliff's Delta fuer zwei ungepaarte Stichproben.

    ``delta = (#(a > b) - #(a < b)) / (n_a * n_b)``, also die Wahrscheinlichkeit
    der Ueberlegenheit minus die der Unterlegenheit.

    Vargha-Delaney A12 wird bewusst **nicht** zusaetzlich berichtet: Es gilt
    exakt ``delta = 2*A12 - 1``, beide Masse nebeneinander waeren dieselbe
    Information in zwei Skalen.

    Args:
        a: Erste Stichprobe.
        b: Zweite Stichprobe.

    Returns:
        Den Wert in ``[-1, 1]``.
    """
    erste = _als_array(a, "Die erste Stichprobe")
    zweite = _als_array(b, "Die zweite Stichprobe")
    groesser = int(np.count_nonzero(erste[:, None] > zweite[None, :]))
    kleiner = int(np.count_nonzero(erste[:, None] < zweite[None, :]))
    return (groesser - kleiner) / (erste.size * zweite.size)


# ---------------------------------------------------------------------------
# Verfahren ueber mehrere Gruppen
# ---------------------------------------------------------------------------


def _blockmatrix(matrix: Sequence[Sequence[float]], name: str) -> NDArray[np.float64]:
    """Prueft und wandelt eine Bloecke-mal-Gruppen-Matrix.

    Args:
        matrix: Zeilen sind Bloecke (Seeds), Spalten sind Gruppen.
        name: Bezeichnung fuer die Fehlermeldung.

    Returns:
        Die Matrix als Array.

    Raises:
        AuswertungsFehler: Bei ungleich langen Zeilen oder zu wenigen Gruppen.
    """
    laengen = {len(zeile) for zeile in matrix}
    if len(laengen) != 1:
        raise AuswertungsFehler(f"{name}: Alle Bloecke muessen gleich viele Gruppen haben.")
    array = np.asarray(matrix, dtype=np.float64)
    if array.ndim != _MATRIXDIMENSIONEN or array.shape[1] < _MINDESTGRUPPEN:
        raise AuswertungsFehler(
            f"{name} braucht mindestens {_MINDESTGRUPPEN} Gruppen, hatte {array.shape}."
        )
    return array


def friedman(matrix: Sequence[Sequence[float]]) -> Testergebnis:
    """Fuehrt den Friedman-Test ueber mehrere verbundene Gruppen durch.

    Args:
        matrix: Zeilen sind Bloecke (Seeds), Spalten sind Gruppen (Fehlerklassen).

    Returns:
        Das Testergebnis mit Kendalls W als Effektstaerke. ``W`` ist das zum
        Friedman-Test gehoerende Konkordanzmass und liegt in ``[0, 1]``.

    Raises:
        AuswertungsFehler: Bei ungueltiger Matrix.
    """
    from scipy.stats import friedmanchisquare  # noqa: PLC0415 - Importkosten nur bei Bedarf

    array = _blockmatrix(matrix, "Der Friedman-Test")
    bloecke, gruppen = array.shape
    ergebnis = friedmanchisquare(*[array[:, spalte] for spalte in range(gruppen)])
    kendall_w = float(ergebnis.statistic) / (bloecke * (gruppen - 1))
    return Testergebnis(
        test="Friedman-Test",
        statistik=float(ergebnis.statistic),
        p_wert=float(ergebnis.pvalue),
        effekt=kendall_w,
        effektmass="Kendalls W",
        n=bloecke,
        seitig="zweiseitig",
        hinweis=f"{gruppen} Gruppen, {bloecke} Bloecke",
    )


def page_trend(matrix: Sequence[Sequence[float]]) -> Testergebnis:
    """Fuehrt den Page-Trendtest ueber geordnete Stufen durch.

    Geprueft wird die **geordnete** Alternative: Der Median steigt ueber die
    Spalten hinweg monoton. Genau das behauptet HYP3 fuer die Precision ueber die
    Fehlerraten — und genau deshalb waere dort ein Wilcoxon-Test falsch: Er
    verglicht zwei Stufen ohne Ordnung und liesse die Information ungenutzt, dass
    die Stufen aufsteigend sind.

    Gerechnet wird ueber die Normalapproximation::

        L      = sum_j j * R_j
        E[L]   = n * k * (k + 1)^2 / 4
        Var[L] = n * (k^3 - k)^2 / (144 * (k - 1))

    Args:
        matrix: Zeilen sind Bloecke, Spalten sind die Stufen in der **erwarteten
            aufsteigenden** Reihenfolge.

    Returns:
        Das Testergebnis; die Statistik ist ``L``, der p-Wert einseitig. Als
        Effektstaerke steht der standardisierte Wert ``z / sqrt(n)``.

    Raises:
        AuswertungsFehler: Bei ungueltiger Matrix.
    """
    from scipy.stats import norm, rankdata  # noqa: PLC0415 - Importkosten nur bei Bedarf

    array = _blockmatrix(matrix, "Der Page-Trendtest")
    bloecke, stufen = array.shape
    raenge = np.asarray([rankdata(zeile) for zeile in array], dtype=np.float64)
    rangsummen = raenge.sum(axis=0)
    gewichte = np.arange(1, stufen + 1, dtype=np.float64)
    statistik = float((gewichte * rangsummen).sum())

    erwartung = bloecke * stufen * (stufen + 1) ** 2 / 4
    varianz = bloecke * (stufen**3 - stufen) ** 2 / (144 * (stufen - 1))
    z = (statistik - erwartung) / math.sqrt(varianz)
    return Testergebnis(
        test="Page-Trendtest",
        statistik=statistik,
        p_wert=float(norm.sf(z)),
        effekt=z / math.sqrt(bloecke),
        effektmass="z / sqrt(n)",
        n=bloecke,
        seitig="einseitig",
        hinweis=f"{stufen} geordnete Stufen, {bloecke} Bloecke, Normalapproximation, z={z:.3f}",
    )


def spearman(x: Sequence[float], y: Sequence[float]) -> Testergebnis:
    """Berechnet die Spearman-Rangkorrelation.

    Args:
        x: Erste Reihe, zum Beispiel die Fehlerrate.
        y: Zweite Reihe, zum Beispiel die Precision.

    Ist eine der beiden Reihen **konstant**, ist die Korrelation nicht definiert:
    Eine Reihe ohne Streuung kann mit nichts kovariieren. Der Fall ist kein
    Randfall, sondern der Erwartungsfall auf der Constraint-Ebene, wo die
    Precision mehrerer Klassen ueber alle Ratenstufen exakt 1,000 betraegt. Statt
    einer erfundenen Null gibt es dort ``effekt = None`` und einen Hinweis — eine
    Null liesse sich als "gemessen, kein Zusammenhang" lesen, und das waere etwas
    anderes als "nicht messbar".

    Args:
        x: Erste Reihe, zum Beispiel die Fehlerrate.
        y: Zweite Reihe, zum Beispiel die Precision.

    Returns:
        Das Testergebnis; die Statistik **ist** die Effektstaerke ``rho``.

    Raises:
        AuswertungsFehler: Bei verschieden langen Reihen.
    """
    from scipy.stats import spearmanr  # noqa: PLC0415 - Importkosten nur bei Bedarf

    erste = _als_array(x, "Die erste Reihe")
    zweite = _als_array(y, "Die zweite Reihe")
    if erste.size != zweite.size:
        raise AuswertungsFehler(
            f"Die Reihen muessen gleich lang sein, waren {erste.size} und {zweite.size}."
        )
    konstant = [
        name
        for name, reihe in (("x", erste), ("y", zweite))
        if float(reihe.max() - reihe.min()) == 0.0
    ]
    if konstant:
        return Testergebnis(
            test="Spearman-Rangkorrelation",
            statistik=float("nan"),
            p_wert=1.0,
            effekt=None,
            effektmass="Spearmans rho",
            n=erste.size,
            seitig="zweiseitig",
            hinweis=(
                f"Nicht definiert: Die Reihe {konstant} ist konstant. Eine Reihe ohne "
                "Streuung kann mit nichts kovariieren; eine Null waere hier eine Messung "
                "vorgetaeuscht, die es nicht gibt."
            ),
        )
    ergebnis = spearmanr(erste, zweite)
    return Testergebnis(
        test="Spearman-Rangkorrelation",
        statistik=float(ergebnis.statistic),
        p_wert=float(ergebnis.pvalue),
        effekt=float(ergebnis.statistic),
        effektmass="Spearmans rho",
        n=erste.size,
        seitig="zweiseitig",
    )


def art_anova_interaktion(
    werte: Sequence[float], faktor_a: Sequence[str], faktor_b: Sequence[str]
) -> Testergebnis:
    """Prueft den Interaktionseffekt zweier Faktoren ueber eine ART-ANOVA.

    Aligned Rank Transform: Die Antwort wird zunaechst um die beiden
    Haupteffekte bereinigt, dann in Raenge ueberfuehrt, dann varianzanalytisch
    ausgewertet. Der Trick besteht darin, dass die Bereinigung **vor** dem
    Rangieren geschieht — nur dadurch prueft der anschliessende F-Test die
    Interaktion und nicht ein Gemisch aus Interaktion und Haupteffekten::

        ausgerichtet = y - zeilenmittel_i - spaltenmittel_j + gesamtmittel

    Der F-Test laeuft anschliessend auf den Raengen der ausgerichteten Werte. Er
    setzt keine Normalitaet der Ausgangswerte voraus — das ist der Grund, warum
    hier nicht die gewoehnliche zweifaktorielle ANOVA steht.

    Args:
        werte: Die Messwerte, zum Beispiel F1 je Lauf.
        faktor_a: Stufe des ersten Faktors je Messwert, zum Beispiel das Verfahren.
        faktor_b: Stufe des zweiten Faktors je Messwert, zum Beispiel die Klasse.

    Returns:
        Das Testergebnis; die Statistik ist ``F``, die Effektstaerke das
        partielle Eta-Quadrat der Interaktion.

    Raises:
        AuswertungsFehler: Bei verschieden langen Folgen, zu wenigen Stufen oder
            leeren Zellen. Eine leere Zelle macht den Interaktionsterm
            unschaetzbar; ein Ersatzwert waere eine Erfindung.
    """
    from scipy.stats import rankdata  # noqa: PLC0415 - Importkosten nur bei Bedarf

    y = _als_array(werte, "Die Messwerte der ART-ANOVA")
    if not len(faktor_a) == len(faktor_b) == y.size:
        raise AuswertungsFehler(
            f"Werte und Faktoren muessen gleich lang sein, waren {y.size}, "
            f"{len(faktor_a)} und {len(faktor_b)}."
        )
    stufen_a = sorted(set(faktor_a))
    stufen_b = sorted(set(faktor_b))
    if len(stufen_a) < _MINDESTSTUFEN or len(stufen_b) < _MINDESTSTUFEN:
        raise AuswertungsFehler(
            f"Beide Faktoren brauchen mindestens {_MINDESTSTUFEN} Stufen, hatten "
            f"{len(stufen_a)} und {len(stufen_b)}."
        )

    index_a = np.asarray([stufen_a.index(wert) for wert in faktor_a], dtype=np.int64)
    index_b = np.asarray([stufen_b.index(wert) for wert in faktor_b], dtype=np.int64)
    zellbelegung = np.zeros((len(stufen_a), len(stufen_b)), dtype=np.int64)
    np.add.at(zellbelegung, (index_a, index_b), 1)
    if int(zellbelegung.min()) == 0:
        leer = [
            (stufen_a[i], stufen_b[j])
            for i in range(len(stufen_a))
            for j in range(len(stufen_b))
            if zellbelegung[i, j] == 0
        ]
        raise AuswertungsFehler(
            f"Die ART-ANOVA braucht jede Faktorkombination besetzt; leer sind {leer}."
        )

    gesamtmittel = float(y.mean())
    zeilenmittel = np.asarray([y[index_a == i].mean() for i in range(len(stufen_a))])
    spaltenmittel = np.asarray([y[index_b == j].mean() for j in range(len(stufen_b))])
    ausgerichtet = y - zeilenmittel[index_a] - spaltenmittel[index_b] + gesamtmittel
    raenge: NDArray[np.float64] = np.asarray(rankdata(ausgerichtet), dtype=np.float64)

    return _f_test_interaktion(raenge, index_a, index_b, len(stufen_a), len(stufen_b))


def _f_test_interaktion(
    raenge: NDArray[np.float64],
    index_a: NDArray[np.int64],
    index_b: NDArray[np.int64],
    stufen_a: int,
    stufen_b: int,
) -> Testergebnis:
    """Fuehrt den F-Test des Interaktionsterms auf den Raengen durch.

    Args:
        raenge: Raenge der ausgerichteten Werte.
        index_a: Stufenindex des ersten Faktors je Beobachtung.
        index_b: Stufenindex des zweiten Faktors je Beobachtung.
        stufen_a: Zahl der Stufen des ersten Faktors.
        stufen_b: Zahl der Stufen des zweiten Faktors.

    Returns:
        Das Testergebnis.

    Raises:
        AuswertungsFehler: Wenn keine Freiheitsgrade fuer den Fehlerterm bleiben.
    """
    from scipy.stats import f as f_verteilung  # noqa: PLC0415 - Importkosten nur bei Bedarf

    gesamt = float(raenge.mean())
    zeilen = np.asarray([raenge[index_a == i].mean() for i in range(stufen_a)])
    spalten = np.asarray([raenge[index_b == j].mean() for j in range(stufen_b)])

    quadratsumme_interaktion = 0.0
    quadratsumme_fehler = 0.0
    for i in range(stufen_a):
        for j in range(stufen_b):
            maske = (index_a == i) & (index_b == j)
            zelle = raenge[maske]
            zellmittel = float(zelle.mean())
            effekt = zellmittel - zeilen[i] - spalten[j] + gesamt
            quadratsumme_interaktion += zelle.size * effekt**2
            quadratsumme_fehler += float(((zelle - zellmittel) ** 2).sum())

    freiheitsgrade_interaktion = (stufen_a - 1) * (stufen_b - 1)
    freiheitsgrade_fehler = raenge.size - stufen_a * stufen_b
    if freiheitsgrade_fehler <= 0:
        raise AuswertungsFehler(
            "Die ART-ANOVA braucht mehr Beobachtungen als Faktorkombinationen; "
            f"es blieben {freiheitsgrade_fehler} Freiheitsgrade fuer den Fehlerterm."
        )
    if quadratsumme_fehler == 0.0:
        raise AuswertungsFehler(
            "Die Fehlerquadratsumme der ART-ANOVA ist null: Innerhalb jeder "
            "Faktorkombination sind alle Werte gleich. Ein F-Wert waere eine Division "
            "durch null."
        )

    mittleres_quadrat_interaktion = quadratsumme_interaktion / freiheitsgrade_interaktion
    mittleres_quadrat_fehler = quadratsumme_fehler / freiheitsgrade_fehler
    f_wert = mittleres_quadrat_interaktion / mittleres_quadrat_fehler
    p_wert = float(f_verteilung.sf(f_wert, freiheitsgrade_interaktion, freiheitsgrade_fehler))
    partielles_eta = quadratsumme_interaktion / (quadratsumme_interaktion + quadratsumme_fehler)
    return Testergebnis(
        test="ART-ANOVA (Aligned Rank Transform), Interaktion",
        statistik=f_wert,
        p_wert=p_wert,
        effekt=partielles_eta,
        effektmass="partielles Eta-Quadrat",
        n=int(raenge.size),
        seitig="einseitig",
        hinweis=(
            f"F({freiheitsgrade_interaktion}, {freiheitsgrade_fehler}); "
            f"{stufen_a} x {stufen_b} Faktorstufen"
        ),
    )


# ---------------------------------------------------------------------------
# Multiplizitaet und Stichprobengroesse
# ---------------------------------------------------------------------------


def holm(p_werte: Sequence[float]) -> tuple[float, ...]:
    """Korrigiert eine Familie von p-Werten nach Holm-Bonferroni.

    Das Verfahren ist gleichmaessig schaerfer als die einfache
    Bonferroni-Korrektur und setzt — anders als Benjamini-Hochberg — keine
    Unabhaengigkeit der Tests voraus. Das ist hier wichtig: Die sieben
    Klassenvergleiche laufen auf **denselben** zwanzig Seeds und sind damit
    verbunden.

    Args:
        p_werte: Die unkorrigierten p-Werte einer Familie, in beliebiger
            Reihenfolge.

    Returns:
        Die korrigierten Werte in der **Eingabereihenfolge**, jeweils auf ``1.0``
        gedeckelt und monoton gemacht.

    Raises:
        AuswertungsFehler: Bei einem Wert ausserhalb von ``[0, 1]``.
    """
    array = np.asarray(p_werte, dtype=np.float64)
    if array.size == 0:
        return ()
    if np.any(array < 0) or np.any(array > 1):
        raise AuswertungsFehler(f"p-Werte muessen in [0, 1] liegen: {array.tolist()}")

    anzahl = array.size
    reihenfolge = np.argsort(array, kind="stable")
    sortiert = array[reihenfolge]
    faktoren = np.arange(anzahl, 0, -1, dtype=np.float64)
    # Monotonie ueber das laufende Maximum: Ein spaeterer Vergleich darf nie einen
    # kleineren korrigierten p-Wert bekommen als ein frueherer, sonst waere die
    # Testfolge nicht mehr konsistent.
    korrigiert = np.minimum(np.maximum.accumulate(sortiert * faktoren), 1.0)

    ergebnis = np.empty_like(korrigiert)
    ergebnis[reihenfolge] = korrigiert
    return tuple(float(wert) for wert in ergebnis)


def seed_warnung(
    wiederholungen: int, vergleiche_je_familie: Mapping[str, int], *, alpha: float = STANDARD_ALPHA
) -> str:
    """Formuliert die Warnung zur Stichprobengroesse mit den tatsaechlichen Zahlen.

    Der exakte zweiseitige Wilcoxon-Test kann bei ``n`` Paaren mit Differenz
    ungleich null keinen kleineren p-Wert liefern als ``2 / 2**n``; der
    zweitkleinste erreichbare Wert ist ``4 / 2**n``. Unter Holm-Korrektur ueber
    ``m`` Vergleiche werden daraus ``m * 2/2**n`` und ``(m-1) * 4/2**n``.

    Warum das ausgerechnet und nicht behauptet wird: Eine pauschale Aussage wie
    "praktisch kein Spielraum" waere je nach Familiengroesse **falsch**. Bei zehn
    Wiederholungen und sieben Vergleichen sind beide Werte noch signifikant; bei
    einundzwanzig Vergleichen ist es der erste knapp und der zweite nicht mehr.
    Diese Zahlen landen im Bericht und damit potenziell in der Arbeit.

    Args:
        wiederholungen: Zahl der Wiederholungen (Seeds) je Zelle.
        vergleiche_je_familie: Je Hypothesenfamilie die Zahl der Vergleiche.
        alpha: Signifikanzniveau.

    Returns:
        Den Warntext; eine leere Zeichenkette, wenn genug Wiederholungen
        vorliegen.
    """
    if wiederholungen >= _MINDESTWIEDERHOLUNGEN:
        return ""

    kleinster = 2.0 / 2**wiederholungen
    zweitkleinster = 4.0 / 2**wiederholungen
    zeilen = [
        (
            f"WARNUNG: Nur {wiederholungen} Wiederholungen je Zelle "
            f"(vorgesehen sind {_MINDESTWIEDERHOLUNGEN})."
        ),
        (
            f"Der exakte zweiseitige Wilcoxon-Test erreicht bei {wiederholungen} Paaren mit "
            f"Differenz ungleich null hoechstens p = {kleinster:.5f}; der zweitkleinste "
            f"erreichbare Wert ist p = {zweitkleinster:.5f}."
        ),
        "Nach Holm-Korrektur bedeutet das je Familie:",
    ]
    for familie, vergleiche in sorted(vergleiche_je_familie.items()):
        erster = min(vergleiche * kleinster, 1.0)
        zweiter = min(max(vergleiche - 1, 1) * zweitkleinster, 1.0)
        zeilen.append(
            f"  {familie} ({vergleiche} Vergleiche): kleinster korrigierter p-Wert "
            f"{erster:.4f} ({'signifikant' if erster < alpha else 'nicht signifikant'}), "
            f"zweitkleinster {zweiter:.4f} "
            f"({'signifikant' if zweiter < alpha else 'nicht signifikant'})."
        )
    zeilen.append(
        "Eine Familie, in der schon der kleinstmoegliche korrigierte p-Wert das Niveau "
        f"{alpha} verfehlt, kann bei dieser Stichprobengroesse keinen signifikanten Befund "
        "hervorbringen — unabhaengig davon, wie gross der wahre Effekt ist."
    )
    return "\n".join(zeilen)
