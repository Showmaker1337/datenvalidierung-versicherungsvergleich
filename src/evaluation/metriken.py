"""Konfusionsmatrizen und Kennzahlen auf allen Auswertungsebenen.

Dieses Modul ist der wissenschaftliche Kern der Auswertung. Es rechnet nicht
einfach Precision und Recall aus, sondern legt fest, **worueber** gezaehlt wird —
und jede dieser Festlegungen ist angreifbar, wenn sie nicht begruendet ist. Die
folgenden acht Abschnitte sind deshalb Teil der Abgabe und nicht Kommentar.

1. Vereinigungsmenge statt Summe der Regeltreffer
-------------------------------------------------

``T(D)``, die Menge der markierten Einheiten, ist die **Vereinigungsmenge** der
markierten Zellen und nicht die Summe der Regeltreffer. Markieren R-009 und R-025
dieselbe Zelle, ist das **ein** markiertes Objekt, kein zweifaches.

Der Grund ist keine Bequemlichkeit. Bei summierter Zaehlung erzeugte ein einziger
injizierter Fehler, den zwei Regeln gleichzeitig sehen, einen Treffer und einen
Fehlalarm — die Precision fiele, obwohl der Detektor *besser* wurde, indem er den
Fehler doppelt absicherte. Eine Metrik, die Redundanz im Regelkatalog bestraft,
misst nicht die Erkennungsleistung, sondern die Berichtskonvention. Die Engine
stellt die Vereinigungsmenge deshalb schon in
:attr:`~src.rules.engine.Detektionen.markierte_zellen` bereit; die Auswertung
bildet sie fuer die Baselines genauso.

Die Zahl der Rohtreffer geht dabei nicht verloren: Sie steht als
``meldungen_gesamt`` neben ``markierte_zellen``, und ihre Differenz ist selbst ein
Befund ueber die Redundanz des Katalogs.

2. Keine Doppelinjektion — die Metrik verlaesst sich darauf
-----------------------------------------------------------

Der Injektor verbietet, dieselbe Zelle zweimal zu verfaelschen (``spec/03``,
Abschnitt 5, Protokollregel 2). Diese Zusicherung wird hier nicht angenommen,
sondern in :func:`~src.evaluation.ground_truth.lade_ground_truth` gegen das
``error_log`` geprueft; ein Verstoss bricht ab.

Ohne sie waere die Rechnung nicht mehr wohldefiniert: ``E`` ist eine Menge von
Zellen, jede Zelle traegt genau eine Fehlerklasse und genau eine Variante. Eine
doppelt verfaelschte Zelle haette zwei Klassen — sie zaehlte in der Summe der
klassenweisen ``n`` zweimal, in der Gesamtmenge aber einmal, und Micro- und
Macro-Recall wuerden auseinanderlaufen, ohne dass die Ursache in den Kennzahlen
sichtbar waere.

3. Klassenweise Precision ist nicht definierbar
------------------------------------------------

Recall laesst sich je Fehlerklasse und je Variante bilden: Der Ground Truth weiss
zu jeder Wahrheitseinheit, welcher Klasse sie angehoert, und man kann fragen, wie
viele davon gefunden wurden.

Precision je Klasse gibt es nicht. Ein False Positive ist eine Zelle, in der **gar
kein Fehler** liegt — sie hat keine Fehlerklasse, weil sie kein Fehler ist. Man
koennte sie hoechstens der Klasse zuschlagen, die eine Regel *vermutet* hat, aber
dann maesse man die Absicht der Regel, nicht die Wirklichkeit der Daten.

Ausgewiesen werden deshalb: **Recall je Klasse und je Variante**, **Precision
global und je Regel**. Diese Asymmetrie ist kein Versaeumnis, sondern eine
Eigenschaft des Messproblems, und sie steht so auch in der ``README.md``. In der
Kreuztabelle Regel gegen Fehlerklasse tragen False Positives darum
:data:`~src.evaluation.modell.KEINE_FEHLERKLASSE` und keine erfundene Sammelklasse.

4. Praevalenzabhaengigkeit: MCC statt Accuracy, PR-AUC nur fuer B2
-------------------------------------------------------------------

Die Fehlerraten des Experiments liegen zwischen 0,5 und 10 Prozent, bezogen auf
das adressierbare Zelluniversum sogar deutlich darunter. In diesem Regime ist F1
nur begrenzt aussagekraeftig, weil es die richtig negative Zelle gar nicht
beruecksichtigt. Zusaetzlich berichtet wird deshalb der
Matthews-Korrelationskoeffizient, der alle vier Felder der Matrix verwendet und
bei starkem Klassenungleichgewicht deutlich besser diskriminiert.

**Accuracy wird nirgends berechnet** — auch nicht als Nebenwert. Bei einem Prozent
Fehleranteil erreicht die Strategie "markiere nichts" 99 Prozent Accuracy. Eine
solche Zahl in einer Ergebnistabelle laedt zur Fehlinterpretation ein, und ihre
Abwesenheit ist leichter zu verteidigen als ihre Relativierung. Im Quelltext gibt
es daher bewusst keine Funktion ``accuracy``.

**PR-AUC nur fuer B2.** Eine Precision-Recall-Kurve entsteht, indem man eine
Entscheidungsschwelle ueber einen kontinuierlichen Score schiebt. Der Prototyp, B0
und B3 liefern binaere Entscheidungen: Eine Regel ist verletzt oder nicht. Daraus
ergibt sich genau **ein** Punkt im PR-Raum, keine Kurve und keine Flaeche. Nur
``IsolationForest`` hat mit ``score_samples`` einen echten Score.
:func:`pr_auc` wird deshalb ausschliesslich fuer B2 aufgerufen und gibt fuer alle
uebrigen Verfahren ``None`` zurueck. Ein Pseudo-Score — etwa "Zahl der
verletzenden Regeln" — wird **nicht** erfunden; er waere eine Rangordnung, die das
Verfahren gar nicht behauptet, und die daraus berechnete Flaeche waere eine
Eigenschaft der Erfindung.

5. Micro und Macro — und zwar auf zwei Ebenen
----------------------------------------------

Micro-Averaging ueber alle Zellen entspricht der Literatur und ist die
Primaerzahl. Es wird von den haeufigen Klassen dominiert, deshalb steht daneben
das **Macro-Mittel ueber die Fehlerklassen**, das seltene Klassen sichtbar haelt.

Darueber hinaus wird ein zweites Macro gebildet: **ueber die Varianten innerhalb
einer Klasse**. Seit der proportionalen Zuteilung des Klassenkontingents zum
Variantenuniversum ist die Mischung ueber die Ratenstufen konstant — genau dafuer
wurde sie gebaut —, aber die Klassen sind intern sehr ungleich besetzt: F4 besteht
zu 73,5 Prozent aus F4-g, HO2 zu 90,7 Prozent aus HO2-b, F4-f stellt 0,1 Prozent
seiner Klasse. Der zellgewichtete Klassenrecall ist damit praktisch der Recall
seiner groessten Variante.

Das ist kein Fehler, sondern eine Definitionsfrage mit zwei legitimen Antworten:

* **Zellgewichtet** beantwortet: "Wenn Fehler dieser Klasse gleichverteilt ueber
  alle adressierbaren Zellen auftreten, wie viel findet der Katalog?"
* **Variantengewichtet** beantwortet: "Wie viele der Fehlerbilder dieser Klasse
  findet der Katalog, unabhaengig davon, wie haeufig sie sind?"

Beide Zahlen werden je Klasse berichtet, und ihre **Differenz ist selbst ein
Ergebnis**: Sie zeigt, wie stark der Klassenwert an der Mischung haengt. Zwei
Stellen sind in der Diskussion ausdruecklich anzusprechen. F4-g loest nach dem
Befund aus Phase 4 zwangslaeufig R-021 zusammen mit R-031 beziehungsweise R-024
aus — der Klassenrecall von F4 liegt also nahe eins, weitgehend durch die
Zuteilung. Umgekehrt ist HO2-b die kohaerente Beitragssenkung, die per Konstruktion
unentdeckt bleiben soll — der Klassenrecall von HO2 liegt nahe null, ebenfalls
durch die Zuteilung. Ohne die variantengewichtete Gegenzahl liest sich beides wie
ein inhaltlicher Befund, obwohl es eine Eigenschaft der Gewichtung ist.

6. Mitgezogene Zellen sind ein Schalter, keine stille Festlegung
-----------------------------------------------------------------

Der Injektor markiert im ``error_log`` mit ``mitgezogen``, welche Zellen er nur
zur Wahrung der Satzstimmigkeit nachgefuehrt hat — vor allem die Rangzellen bei
der Skalierung eines Beitragstupels. Diese Zellen sind gegenueber den
verfaelschten Daten **korrekt**: Der nachgefuehrte Rang ist der richtige Rang zum
verfaelschten Beitrag. Ein Verfahren, das sie nicht meldet, macht keinen Fehler,
und sie gehoeren damit nicht in ``E``.

Genau deshalb darf die Entscheidung nicht unsichtbar sein. Sie hebt den Recall von
F8 und HO2 spuerbar — bei F8 stehen 5.362 fehlerhaften Zellen 2.957 mitgezogene
gegenueber. Wer das im Quelltext entdeckt und nicht in der Arbeit, liest es als
"Falsch-Negative wegdefiniert".

Die Beruecksichtigung ist deshalb ein Parameter ``mitgezogen_als_fehler`` mit dem
Standard ``False``, und **beide** Werte werden je Lauf gerechnet und persistiert.
In der Arbeit steht die Hauptauswertung mit ``False``, die Gegenrechnung als
Sensitivitaetszeile im Anhang. Zwei Zahlen nebeneinander beenden die Diskussion,
eine Zahl allein eroeffnet sie.

7. Randfaelle: was bei leerem Zaehler oder leerem Nenner gilt
--------------------------------------------------------------

* **``|T(D)| = 0`` ergibt Precision ``0.0``.** Das ist eine dokumentierte Wahl,
  keine mathematische Notwendigkeit. Ein Verfahren, das nichts meldet, hat keine
  korrekten Meldungen; ``1.0`` waere eine Belohnung fuers Nichtstun und wuerde in
  jeder Aggregation genau die Verfahren nach oben ziehen, die nichts leisten.
  ``nan`` waere in jeder Mittelung ansteckend und muesste an jeder Stelle einzeln
  behandelt werden. Die Wahl ist konservativ und faellt in der Tabelle auf, weil
  ``tp``, ``fp`` und ``fn`` danebenstehen.
* **``|E| = 0`` ergibt Recall ``0.0``** mit derselben Begruendung. Damit die Null
  nicht als "hat nichts gefunden" missverstanden wird, fuehrt **jede** Gruppenzeile
  ihr ``n`` mit; ``n = 0`` ist von einem echten Recall 0 unterscheidbar.
* **F1 ist ``0.0``**, wenn Precision und Recall beide null sind.
* **MCC** ist ``(tp*tn - fp*fn) / sqrt((tp+fp)(tp+fn)(tn+fp)(tn+fn))`` und
  ``0.0``, wenn einer der vier Faktoren des Nenners null ist — die uebliche
  Konvention nach Matthews und Chicco. Ohne ``tn`` (Constraint-Ebene) ist MCC
  ``None``, nicht null. Die Produkte werden als ``int`` gebildet und erst danach
  nach ``float`` gewandelt: Bei rund 60.000 Zeilen und gut 60 Spalten liegt das
  Zelluniversum im Millionenbereich, und ein Viererprodukt daraus sprengt die
  Mantisse eines ``float`` laengst.
* **``fpr_clean``** ist ``fp / (Grundgesamtheit - |E|)``, also die Fehlalarmrate
  auf den **nicht** verfaelschten Einheiten. Der Nenner ist bewusst nicht
  ``fp + tn`` geschrieben, obwohl er dasselbe ist — die Form macht sichtbar, dass
  die Bezugsgroesse dieselbe ist wie im Clean-Baseline-Lauf und beide Zahlen
  nebeneinander stehen duerfen.
* **Clopper-Pearson** ueber ``scipy.stats.beta.ppf``. Das exakte Intervall wird
  dem Normalapproximationsintervall vorgezogen, weil viele Varianten sehr kleine
  ``n`` haben und die Approximation dort Grenzen ausserhalb von ``[0, 1]``
  liefert. Randfaelle: ``k = 0`` hat die untere Grenze ``0.0``, ``k = n`` die
  obere Grenze ``1.0``, ``n = 0`` das voellig uninformative Intervall
  ``(0.0, 1.0)``.

8. Die vier Ebenen
-------------------

**Zellebene**, Einheit ``(entitaet, row_id, spalte)``. Primaermetrik.
``T(D)`` ist die Vereinigungsmenge der markierten Zellen (nur Meldungen mit
``row_id >= 0``), ``E`` die Zellwahrheit je nach Schalterstellung, und
``tn = universum_zellen - tp - fp - fn``.

**Constraint-Ebene**, Einheit der Precision ist die ``verstoss_id``.
``tp`` ist die Zahl der ``verstoss_id``, von denen **mindestens eine** Zelle in
``E`` liegt; ``fp`` die Zahl der uebrigen. ``fn`` bleibt die Zahl der
**Wahrheitszellen**, die in keinem Verstoss vorkommen — dieselbe Zahl wie auf der
Zellebene. ``tn`` ist ``None``, und damit auch MCC und ``fpr_clean``.

Dieser **Einheitenbruch** ist Absicht, und er wird ausdruecklich gemacht statt
verschwiegen: Nur die **Precision** wechselt die Einheit. Genau das repariert ihre
strukturelle Deckelung. R-031 prueft die Beziehung zwischen Brutto, Netto und
Steuer und meldet alle drei Zellen, der Injektor hat aber nur eine verfaelscht:
zellbasiert ein Treffer und zwei Fehlalarme bei perfekter Erkennung, die Precision
strukturell auf ein Drittel gedeckelt. Constraint-basiert ist es ein Treffer.

Der **Recall** bleibt dagegen zellbasiert und ist zahlengleich mit dem der
Zellebene, denn die Frage der Arbeit lautet, ob jeder injizierte Fehler gefunden
wird. Er wird deshalb ueber das eigene Feld
:attr:`~src.evaluation.modell.Konfusion.tp_recall` gefuehrt. Wuerde er aus ``tp``
gebildet, waere er in **beide** Richtungen falsch:

* Ein Verstoss, der zwei Wahrheitszellen zugleich ueberdeckt — bei F8 der Regelfall,
  weil die kohaerente Skalierung mehrere Beitragsfelder trifft und R-031 sie in
  **einem** Verstoss meldet —, zaehlte einmal statt zweimal und druecke den Recall
  unter den Zellrecall.
* Zwei Regeln, die dieselbe eine Wahrheitszelle melden — der Datums-Sentinel loest
  R-009 und R-025 gleichzeitig aus —, zaehlten zweimal statt einmal und hoeben ihn
  darueber. Das waere genau die Doppelzaehlung, die Festlegung 1
  (Vereinigungsmenge statt Summe) ausschliesst.

In beiden Faellen stuenden in **einer** ``metrics.json`` zwei verschiedene Zahlen
unter dem Namen ``recall``: eine in der Konfusionsmatrix der Ebene, eine andere in
ihren Gruppentabellen, die zellweise gebildet werden.

**Der Recall der Constraint-Ebene ist deshalb immer gleich dem der Zellebene, und
das ist kein Fehler, sondern Konstruktion.** Zaehler und Nenner sind auf beiden
Ebenen dieselbe Menge: die injizierten Zellen. Nur die **Precision** unterscheidet
sich, weil in ihrem Nenner Verstoesse stehen statt Zellen — und genau dafuer wurde
die Ebene eingefuehrt. Wer die beiden gleichen Recallwerte in der Ergebnistabelle
sieht und den Satz hier nicht kennt, haelt sie fuer einen Kopierfehler und die
Constraint-Ebene fuer ueberfluessig. Der Satz gehoert deshalb auch in die Arbeit,
nicht nur in diesen Docstring.

Verfahren ohne echte ``verstoss_id``-Semantik werden gleich behandelt — B0 vergibt
je Feldfehler eine eigene Kennung, seine Constraint-Ebene ist deshalb fast
identisch zu seiner Zellebene. Das ist kein Mangel der Behandlung, sondern die
Aussage: B0 kennt keine mehrspaltigen Bedingungen.

**Satzebene**, Einheit ``(entitaet, row_id)``.
``T(D)`` sind die Zeilen mit mindestens einer markierten Zelle **plus** alle
Zeilen aus den satzbezogenen Meldungen des Verfahrens. ``E`` ist die Satzwahrheit,
``tn = universum_saetze - tp - fp - fn``. Dies ist die **einzige** Ebene, auf der
F6 und HO1 auswertbar sind: Dort kommen Zeilen hinzu, und ein zellweises Diff ist
undefiniert (``spec/03``, Abschnitt 4.2).

**Regelebene** ist diagnostisch und **keine** Konfusionsmatrix. Ein Recall je
Regel waere nicht definiert, weil der Ground Truth Fehlerklassen kennt, aber keine
Regel-IDs. Berichtet werden je ``regel_id`` die Zahl der gemeldeten Zellen, davon
die im Ground Truth liegenden, die daraus folgende Precision und der Anteil der
Treffer, bei denen **keine andere Regel** dieselbe Zelle gemeldet hat.
"""

from __future__ import annotations

import math
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from src.evaluation.modell import (
    KEINE_FEHLERKLASSE,
    AuswertungsFehler,
    Gruppenrecall,
    Kennzahlen,
    Konfusion,
    Kreuzeintrag,
    Regeldiagnose,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence
    from collections.abc import Set as AbstractSet

__all__ = [
    "STANDARD_ALPHA",
    "clopper_pearson",
    "f1",
    "fpr_clean",
    "gruppenrecall",
    "kennzahlen",
    "konfusion_constraints",
    "konfusion_mengen",
    "konfusion_zellen",
    "kreuztabelle",
    "macro_recall",
    "mcc",
    "pr_auc",
    "precision",
    "recall",
    "regeldiagnose",
    "variantengewichteter_klassenrecall",
]

#: Irrtumswahrscheinlichkeit der Konfidenzintervalle: 95-Prozent-Niveau.
STANDARD_ALPHA: float = 0.05

#: So viele verschiedene Wahrheitswerte braucht eine Precision-Recall-Kurve.
#:
#: Liegen alle Einheiten in derselben Klasse, gibt es keine Kurve — jede Zahl
#: waere dann frei erfunden, und :func:`pr_auc` gibt ``None`` zurueck.
_KLASSEN_FUER_KURVE: Final[int] = 2

# Bewusst gibt es hier **keine** Funktion ``accuracy``. Bei einem Prozent
# Fehleranteil erreicht "markiere nichts" 99 Prozent Accuracy; die Zahl waere in
# jeder Ergebnistabelle irrefuehrend. Siehe Abschnitt 4 des Modul-Docstrings.


# ---------------------------------------------------------------------------
# Konfusionsmatrizen
# ---------------------------------------------------------------------------


def konfusion_mengen[T](
    markiert: AbstractSet[T],
    wahrheit: AbstractSet[T],
    universum: int,
) -> Konfusion:
    """Bildet die Konfusionsmatrix zweier Mengen gegen eine Grundgesamtheit.

    Der mengenbasierte Kern der Zell- und der Satzebene. Beide unterscheiden sich
    nur im Typ ihrer Einheit — ``(entitaet, row_id, spalte)`` gegen
    ``(entitaet, row_id)`` —, nicht in der Rechnung.

    Args:
        markiert: Vom Verfahren markierte Einheiten, bereits dedupliziert.
        wahrheit: Tatsaechlich verfaelschte Einheiten.
        universum: Zahl aller Einheiten der Ebene.

    Returns:
        Die :class:`~src.evaluation.modell.Konfusion` mit besetztem ``tn``.

    Raises:
        AuswertungsFehler: Wenn die Grundgesamtheit kleiner ist als die Zahl der
            beteiligten Einheiten. Ein negatives ``tn`` waere kein Randfall,
            sondern der Beweis, dass Markierungen und Universum aus verschiedenen
            Datensaetzen stammen — etwa aus dem sauberen und dem verfaelschten.
    """
    tp = len(markiert & wahrheit)
    fp = len(markiert - wahrheit)
    fn = len(wahrheit - markiert)
    tn = universum - tp - fp - fn
    if tn < 0:
        raise AuswertungsFehler(
            f"Die Grundgesamtheit {universum} ist kleiner als tp+fp+fn = {tp + fp + fn}. "
            "Markierungen und Universum stammen offenbar aus verschiedenen Datensaetzen; "
            "die Auswertung muss auf dem verfaelschten Datensatz laufen."
        )
    return Konfusion(tp=tp, fp=fp, fn=fn, tn=tn, grundgesamtheit=universum)


def konfusion_zellen(
    markiert: AbstractSet[tuple[str, int, str]],
    wahrheit: AbstractSet[tuple[str, int, str]],
    universum: int,
) -> Konfusion:
    """Bildet die Konfusionsmatrix der Zellebene.

    Args:
        markiert: Vereinigungsmenge der markierten Tripel
            ``(entitaet, row_id, spalte)``. Meldungen ohne Zeilenbezug
            (``row_id`` gleich :data:`~src.evaluation.modell.ROW_ID_OHNE_BEZUG`)
            gehoeren nicht hinein.
        wahrheit: Zellwahrheit je nach Schalterstellung von
            ``mitgezogen_als_fehler``.
        universum: ``universum_zellen`` des Laufs, ``row_id`` eingeschlossen.

    Returns:
        Die Konfusionsmatrix der Zellebene.
    """
    return konfusion_mengen(markiert, wahrheit, universum)


def konfusion_constraints(
    zellen_je_verstoss: Mapping[str, Sequence[tuple[str, int, str]]],
    wahrheit: AbstractSet[tuple[str, int, str]],
    markiert: AbstractSet[tuple[str, int, str]],
) -> Konfusion:
    """Bildet die Konfusionsmatrix der Constraint-Ebene.

    Die Einheit der **Precision** ist die ``verstoss_id``; ein mehrspaltiger
    Verstoss zaehlt als **ein** Treffer, sobald mindestens eine seiner Zellen im
    Ground Truth liegt.

    Der **Recall** bleibt dagegen zellbasiert und ist damit exakt derselbe wie auf
    der Zellebene. Er wird ueber ``tp_recall`` gefuehrt, nicht ueber ``tp``: Aus
    ``tp / (tp + fn)`` entstuende ein Bruch aus Verstoessen im Zaehler und Zellen
    im Nenner, und **beide** Fehlerrichtungen waeren moeglich. Ein Verstoss, der
    zwei Wahrheitszellen zugleich ueberdeckt, senkte den Wert unter den Zellrecall;
    zwei Regeln, die dieselbe eine Wahrheitszelle melden, hoeben ihn darueber — und
    Letzteres waere genau die Doppelzaehlung, die Festlegung 1 (Vereinigungsmenge
    statt Summe) ausschliesst.

    Nur die Precision wechselt also die Einheit, und genau das repariert ihre
    strukturelle Deckelung. Der Einheitenbruch ist im Modul-Docstring, Abschnitt 8,
    ausgeschrieben.

    Args:
        zellen_je_verstoss: Je ``verstoss_id`` die von ihr gemeldeten Zellen.
        wahrheit: Zellwahrheit je nach Schalterstellung.
        markiert: Vereinigungsmenge aller markierten Zellen. Getrennt uebergeben,
            weil sie auch die Zellen der Regeln ohne ``verstoss_id``-Semantik
            enthaelt und ``fn`` gegen die **volle** Markierung gebildet wird.

    Returns:
        Die Konfusionsmatrix mit ``tn = None`` und ``grundgesamtheit = None``: Es
        gibt keine abzaehlbare Menge nicht erkannter Verstoesse, und eine Null an
        dieser Stelle waere eine unbelegbare Behauptung.
    """
    tp = 0
    fp = 0
    for verstoss_id in sorted(zellen_je_verstoss):
        if any(zelle in wahrheit for zelle in zellen_je_verstoss[verstoss_id]):
            tp += 1
        else:
            fp += 1
    return Konfusion(
        tp=tp,
        fp=fp,
        fn=len(wahrheit - markiert),
        tn=None,
        grundgesamtheit=None,
        tp_recall=len(wahrheit & markiert),
    )


# ---------------------------------------------------------------------------
# Kennzahlen
# ---------------------------------------------------------------------------


def precision(k: Konfusion) -> float:
    """Berechnet die Precision ``tp / (tp + fp)``.

    Args:
        k: Die Konfusionsmatrix.

    Returns:
        Die Precision; ``0.0`` bei leerer Meldungsmenge. Diese Wahl ist
        dokumentiert und begruendet (Modul-Docstring, Abschnitt 7): ``1.0`` waere
        eine Belohnung fuers Nichtstun, ``nan`` in jeder Aggregation ansteckend.
    """
    nenner = k.tp + k.fp
    return k.tp / nenner if nenner else 0.0


def recall(k: Konfusion) -> float:
    """Berechnet den Recall ``tp / (tp + fn)``.

    Zaehler ist :attr:`~src.evaluation.modell.Konfusion.tp_recall`, sobald er
    gesetzt ist. Das betrifft ausschliesslich die Constraint-Ebene, auf der ``tp``
    Verstoesse zaehlt und ``fn`` Wahrheitszellen; ohne die Unterscheidung waere der
    Recall dort ein Bruch aus zwei Einheiten (siehe
    :func:`konfusion_constraints`). Nenner ist in beiden Faellen der volle Ground
    Truth der Ebene.

    Args:
        k: Die Konfusionsmatrix.

    Returns:
        Den Recall; ``0.0`` bei leerem Ground Truth. Damit die Null nicht als
        "nichts gefunden" missverstanden wird, fuehrt jede Gruppentabelle ihr
        ``n`` mit.
    """
    zaehler = k.tp if k.tp_recall is None else k.tp_recall
    nenner = zaehler + k.fn
    return zaehler / nenner if nenner else 0.0


def f1(p: float, r: float) -> float:
    """Berechnet das harmonische Mittel aus Precision und Recall.

    Args:
        p: Precision.
        r: Recall.

    Returns:
        Den F1-Wert; ``0.0``, wenn beide Eingaben null sind.
    """
    return 2 * p * r / (p + r) if (p + r) else 0.0


def mcc(k: Konfusion) -> float | None:
    """Berechnet den Matthews-Korrelationskoeffizienten.

    Das Viererprodukt des Nenners wird vollstaendig als ``int`` gebildet und erst
    danach **einmal** nach ``float`` gewandelt. Das Zelluniversum liegt im
    Millionenbereich, das Produkt damit bei rund ``1e36``; der Wertebereich eines
    ``float`` traegt das mit grossem Abstand, seine Mantisse aber nicht mehr
    verlustfrei. Vier Faktoren einzeln in ``float`` zu multiplizieren rundete
    dreimal statt einmal — der Unterschied liegt bei ``1e-16`` und damit weit
    unterhalb jeder berichteten Genauigkeit, kostet aber nichts.

    Args:
        k: Die Konfusionsmatrix.

    Returns:
        Den MCC im Bereich ``[-1, 1]``; ``0.0``, wenn ein Faktor des Nenners null
        ist (Konvention nach Matthews und Chicco); ``None``, wenn ``tn`` fehlt und
        die Kennzahl damit gar nicht gebildet werden kann.
    """
    if k.tn is None:
        return None
    faktoren = (k.tp + k.fp, k.tp + k.fn, k.tn + k.fp, k.tn + k.fn)
    if any(faktor == 0 for faktor in faktoren):
        return 0.0
    zaehler = k.tp * k.tn - k.fp * k.fn
    nenner = math.sqrt(float(faktoren[0] * faktoren[1] * faktoren[2] * faktoren[3]))
    return zaehler / nenner


def fpr_clean(k: Konfusion) -> float | None:
    """Berechnet die Fehlalarmrate auf den nicht verfaelschten Einheiten.

    ``fp / (Grundgesamtheit - |E|)``. Bewusst nicht als ``fp / (fp + tn)``
    geschrieben, obwohl es dasselbe ist: Die gewaehlte Form macht sichtbar, dass
    die Bezugsgroesse dieselbe ist wie im Clean-Baseline-Lauf
    (``scripts/validate.py``) und beide Zahlen nebeneinander stehen duerfen.

    Args:
        k: Die Konfusionsmatrix.

    Returns:
        Die Rate; ``None``, wenn ``tn`` oder die Grundgesamtheit fehlt; ``0.0``,
        wenn jede Einheit der Ebene verfaelscht war und es keine sauberen
        Einheiten gibt.
    """
    if k.tn is None or k.grundgesamtheit is None:
        return None
    nenner = k.grundgesamtheit - (k.tp + k.fn)
    return k.fp / nenner if nenner > 0 else 0.0


def kennzahlen(konfusion: Konfusion, *, pr_auc: float | None = None) -> Kennzahlen:
    """Leitet alle Kennzahlen aus einer Konfusionsmatrix ab.

    Args:
        konfusion: Die Rohwerte.
        pr_auc: Flaeche unter der Precision-Recall-Kurve. Wird **nur** fuer B2
            gefuellt; Verfahren mit binaerer Entscheidung liefern genau einen
            Betriebspunkt, und ein Pseudo-Score wird nicht erfunden.

    Returns:
        Die :class:`~src.evaluation.modell.Kennzahlen` einschliesslich der
        Rohwerte, damit jede weitere Metrik spaeter ohne neuen Lauf nachrechenbar
        bleibt.
    """
    p = precision(konfusion)
    r = recall(konfusion)
    return Kennzahlen(
        konfusion=konfusion,
        precision=p,
        recall=r,
        f1=f1(p, r),
        mcc=mcc(konfusion),
        fpr_clean=fpr_clean(konfusion),
        pr_auc=pr_auc,
    )


# ---------------------------------------------------------------------------
# Konfidenzintervall und PR-AUC
# ---------------------------------------------------------------------------


def clopper_pearson(k: int, n: int, *, alpha: float = STANDARD_ALPHA) -> tuple[float, float]:
    """Berechnet das exakte Clopper-Pearson-Intervall eines Anteilswerts.

    Das exakte Intervall wird der Normalapproximation vorgezogen, weil viele
    Varianten sehr kleine ``n`` haben; die Approximation liefert dort Grenzen
    ausserhalb von ``[0, 1]``.

    Args:
        k: Zahl der Treffer.
        n: Zahl der Versuche.
        alpha: Irrtumswahrscheinlichkeit; ``0.05`` ergibt ein 95-Prozent-Intervall.

    Returns:
        Untere und obere Grenze. Bei ``n = 0`` das uninformative Intervall
        ``(0.0, 1.0)``, bei ``k = 0`` die untere Grenze ``0.0``, bei ``k = n`` die
        obere Grenze ``1.0``.

    Raises:
        AuswertungsFehler: Bei ``n < 0``, ``k < 0``, ``k > n`` oder einem ``alpha``
            ausserhalb von ``(0, 1)``.
    """
    from scipy.stats import beta  # noqa: PLC0415 - Importkosten nur bei Bedarf

    if n < 0 or k < 0 or k > n:
        raise AuswertungsFehler(
            f"Clopper-Pearson braucht 0 <= k <= n, erhalten wurde k={k}, n={n}."
        )
    if not 0.0 < alpha < 1.0:
        raise AuswertungsFehler(f"alpha muss in (0, 1) liegen, erhalten wurde {alpha}.")
    if n == 0:
        return (0.0, 1.0)

    unten = 0.0 if k == 0 else float(beta.ppf(alpha / 2, k, n - k + 1))
    oben = 1.0 if k == n else float(beta.ppf(1 - alpha / 2, k + 1, n - k))
    return (unten, oben)


def pr_auc(scores: Sequence[float], wahr: Sequence[bool]) -> float | None:
    """Berechnet die Flaeche unter der Precision-Recall-Kurve.

    Verwendet ``sklearn.metrics.average_precision_score``, also die
    stufenweise Summation ueber die Betriebspunkte und **nicht** die
    trapezinterpolierte Flaeche; letztere ist bei Precision-Recall-Kurven zu
    optimistisch.

    Aufgerufen wird die Funktion ausschliesslich fuer B2. Der Prototyp, B0 und B3
    liefern binaere Entscheidungen und damit genau einen Punkt im PR-Raum; fuer
    sie wird **kein** Pseudo-Score erfunden, sondern der einzelne Betriebspunkt
    ueber Precision und Recall ausgewiesen.

    Args:
        scores: Anomaliescore je Einheit; hoehere Werte bedeuten "anomaler".
        wahr: Wahrheitswert je Einheit, in derselben Reihenfolge.

    Returns:
        Die Flaeche; ``None``, wenn keine Einheiten vorliegen oder alle
        Wahrheitswerte gleich sind — dann ist die Kurve nicht definiert und eine
        Zahl waere frei erfunden.

    Raises:
        AuswertungsFehler: Wenn beide Folgen verschieden lang sind.
    """
    from sklearn.metrics import average_precision_score  # noqa: PLC0415 - Importkosten

    if len(scores) != len(wahr):
        raise AuswertungsFehler(
            f"Scores und Wahrheitswerte muessen gleich lang sein, erhalten wurden "
            f"{len(scores)} und {len(wahr)}."
        )
    if not scores or len(set(wahr)) < _KLASSEN_FUER_KURVE:
        return None
    return float(average_precision_score(list(wahr), list(scores)))


# ---------------------------------------------------------------------------
# Gruppenweiser Recall
# ---------------------------------------------------------------------------


def gruppenrecall[T](
    einheiten_je_gruppe: Mapping[str, Sequence[T]],
    gefunden: AbstractSet[T],
    *,
    gruppen: Sequence[str] | None = None,
    alpha: float = STANDARD_ALPHA,
) -> tuple[Gruppenrecall, ...]:
    """Berechnet den Recall je Gruppe samt Clopper-Pearson-Intervall.

    Gruppe ist je nach Aufruf die Fehlerklasse oder die ``injektor_variante_id``;
    die Rechnung ist dieselbe, nur die Zuordnung unterscheidet sich. Einheit ist
    je nach Ebene die Zelle oder die Zeile.

    Args:
        einheiten_je_gruppe: Je Gruppe die Wahrheitseinheiten dieser Gruppe.
            Wiederholungen innerhalb einer Gruppe werden entfernt, damit ``n`` die
            Zahl der **verschiedenen** Einheiten ist.
        gefunden: Vom Verfahren gefundene Einheiten der jeweiligen Ebene.
        gruppen: Auszuweisende Gruppen in dieser Reihenfolge. Ohne Angabe die
            sortierten Schluessel der Abbildung. **Mit** Angabe erscheinen auch
            Gruppen mit ``n = 0`` — bei sechzig Varianten und kleinen Fehlerraten
            waere eine fehlende Tabellenzeile sonst nicht von einem Recall 0 zu
            unterscheiden.
        alpha: Irrtumswahrscheinlichkeit des Konfidenzintervalls.

    Returns:
        Je Gruppe einen :class:`~src.evaluation.modell.Gruppenrecall`, in der
        Reihenfolge von ``gruppen``.
    """
    auswahl = list(gruppen) if gruppen is not None else sorted(einheiten_je_gruppe)
    ergebnis: list[Gruppenrecall] = []
    for gruppe in auswahl:
        einheiten = list(dict.fromkeys(einheiten_je_gruppe.get(gruppe, ())))
        anzahl = len(einheiten)
        treffer = sum(1 for einheit in einheiten if einheit in gefunden)
        unten, oben = clopper_pearson(treffer, anzahl, alpha=alpha)
        ergebnis.append(
            Gruppenrecall(
                gruppe=gruppe,
                n=anzahl,
                tp=treffer,
                recall=treffer / anzahl if anzahl else 0.0,
                ci_unten=unten,
                ci_oben=oben,
            )
        )
    return tuple(ergebnis)


def macro_recall(gruppen: Sequence[Gruppenrecall]) -> float | None:
    """Bildet das ungewichtete Mittel der Recalls ueber alle besetzten Gruppen.

    Gruppen mit ``n = 0`` gehen **nicht** ein. Ihr Recall ist definitionsgemaess
    ``0.0`` (siehe Modul-Docstring, Abschnitt 7); waeren sie im Mittel, zoege eine
    Variante ohne Kontingent den Macro-Wert nach unten, ohne dass ein Verfahren
    etwas uebersehen haette.

    Args:
        gruppen: Die Gruppenrecalls einer Ebene.

    Returns:
        Das Mittel; ``None``, wenn keine Gruppe besetzt ist.
    """
    besetzt = [eintrag.recall for eintrag in gruppen if eintrag.n > 0]
    return sum(besetzt) / len(besetzt) if besetzt else None


def variantengewichteter_klassenrecall(
    varianten: Sequence[Gruppenrecall],
    klasse_je_variante: Mapping[str, str],
    *,
    klassen: Sequence[str] | None = None,
) -> Mapping[str, float]:
    """Bildet je Fehlerklasse das ungewichtete Mittel ihrer Variantenrecalls.

    Die Gegenzahl zum zellgewichteten Klassenrecall. Sie beantwortet "wie viele
    der Fehlerbilder dieser Klasse findet der Katalog, unabhaengig davon, wie
    haeufig sie sind?", waehrend der zellgewichtete Wert "wenn Fehler dieser
    Klasse gleichverteilt ueber alle adressierbaren Zellen auftreten, wie viel
    findet der Katalog?" beantwortet. Beide Zahlen werden berichtet; ihre
    Differenz ist selbst ein Ergebnis (Modul-Docstring, Abschnitt 5).

    Die Zuordnung Variante auf Klasse kommt als Abbildung herein und wird **nicht**
    aus der Variantenkennung geparst. Ein ``split`` am Bindestrich waere eine
    zweite, stille Definition derselben Zuordnung; die einzige Quelle ist der
    Ground Truth.

    Args:
        varianten: Recall je ``injektor_variante_id``.
        klasse_je_variante: Fehlerklasse je Variante.
        klassen: Auszuweisende Klassen. Ohne Angabe die sortierten Klassen der
            besetzten Varianten.

    Returns:
        Eine unveraenderliche Abbildung Klasse auf Mittelwert. Klassen ohne eine
        einzige besetzte Variante fehlen — fuer sie gibt es keinen Mittelwert,
        und eine Null waere eine Aussage ueber ein Verfahren statt ueber die
        Zuteilung.

    Raises:
        AuswertungsFehler: Wenn eine Variante in ``klasse_je_variante`` fehlt.
    """
    je_klasse: dict[str, list[float]] = {}
    for eintrag in varianten:
        if eintrag.gruppe not in klasse_je_variante:
            raise AuswertungsFehler(
                f"Zur Variante {eintrag.gruppe!r} ist keine Fehlerklasse bekannt. Die "
                "Zuordnung stammt aus dem Ground Truth des Laufs und muss vollstaendig sein."
            )
        if eintrag.n > 0:
            je_klasse.setdefault(klasse_je_variante[eintrag.gruppe], []).append(eintrag.recall)

    auswahl = list(klassen) if klassen is not None else sorted(je_klasse)
    return MappingProxyType(
        {
            klasse: sum(je_klasse[klasse]) / len(je_klasse[klasse])
            for klasse in auswahl
            if je_klasse.get(klasse)
        }
    )


# ---------------------------------------------------------------------------
# Diagnose auf der Regelebene
# ---------------------------------------------------------------------------


def regeldiagnose(
    meldungen: Mapping[str, Sequence[tuple[str, int, str]]],
    wahrheit: AbstractSet[tuple[str, int, str]],
) -> tuple[Regeldiagnose, ...]:
    """Berechnet die diagnostischen Kennzahlen je Regel.

    Keine Konfusionsmatrix: Ein Recall je Regel waere nicht definiert, weil der
    Ground Truth Fehlerklassen kennt, aber keine Regel-IDs.

    Args:
        meldungen: Je ``regel_id`` die von ihr gemeldeten Zellen. Wiederholungen
            innerhalb einer Regel werden entfernt.
        wahrheit: Zellwahrheit je nach Schalterstellung.

    Returns:
        Je Regel eine :class:`~src.evaluation.modell.Regeldiagnose`, sortiert nach
        ``regel_id``.
    """
    melder_je_zelle: dict[tuple[str, int, str], int] = {}
    zellen_je_regel: dict[str, list[tuple[str, int, str]]] = {}
    for regel_id in sorted(meldungen):
        zellen = list(dict.fromkeys(meldungen[regel_id]))
        zellen_je_regel[regel_id] = zellen
        for zelle in zellen:
            melder_je_zelle[zelle] = melder_je_zelle.get(zelle, 0) + 1

    ergebnis: list[Regeldiagnose] = []
    for regel_id, zellen in zellen_je_regel.items():
        treffer = [zelle for zelle in zellen if zelle in wahrheit]
        allein = sum(1 for zelle in treffer if melder_je_zelle[zelle] == 1)
        ergebnis.append(
            Regeldiagnose(
                regel_id=regel_id,
                meldungen=len(zellen),
                tp=len(treffer),
                precision=len(treffer) / len(zellen) if zellen else 0.0,
                anteil_einzige_regel=allein / len(treffer) if treffer else 0.0,
            )
        )
    return tuple(ergebnis)


def kreuztabelle(
    meldungen: Mapping[str, Sequence[tuple[str, int, str]]],
    fehlerklasse_je_zelle: Mapping[tuple[str, int, str], str],
) -> tuple[Kreuzeintrag, ...]:
    """Zaehlt je Regel, wie viele Zellen welcher Fehlerklasse sie getroffen hat.

    Die Tabelle beantwortet die Frage, welche Regel welches Fehlerbild aufdeckt —
    die Mapping-Tabelle des Anhangs in gemessener statt in geplanter Form.

    False Positives tragen :data:`~src.evaluation.modell.KEINE_FEHLERKLASSE` und
    keine erfundene Sammelklasse: In einer falsch markierten Zelle liegt gar kein
    Fehler, und damit auch keine Klasse (Modul-Docstring, Abschnitt 3).

    Args:
        meldungen: Je ``regel_id`` die von ihr gemeldeten Zellen. Wiederholungen
            innerhalb einer Regel werden entfernt.
        fehlerklasse_je_zelle: Fehlerklasse je Wahrheitszelle; Zellen, die nicht
            darin vorkommen, sind Fehlalarme.

    Returns:
        Die besetzten Eintraege, sortiert nach ``(regel_id, fehlerklasse)``.
        Kombinationen ohne Treffer fehlen — eine vollstaendige Kreuztabelle aus
        58 Regeln und zehn Klassen waere zu 90 Prozent leer.
    """
    gezaehlt: dict[tuple[str, str], int] = {}
    for regel_id in sorted(meldungen):
        for zelle in dict.fromkeys(meldungen[regel_id]):
            klasse = fehlerklasse_je_zelle.get(zelle, KEINE_FEHLERKLASSE)
            gezaehlt[(regel_id, klasse)] = gezaehlt.get((regel_id, klasse), 0) + 1

    return tuple(
        Kreuzeintrag(regel_id=regel_id, fehlerklasse=klasse, treffer=treffer)
        for (regel_id, klasse), treffer in sorted(gezaehlt.items())
    )
