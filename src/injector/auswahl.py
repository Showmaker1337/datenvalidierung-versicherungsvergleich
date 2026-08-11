"""Auswahl der zu verfaelschenden Zellen und Saetze.

Die Bezugsgroesse der Fehlerrate
--------------------------------

``spec/03_fehlerklassen.md``, Abschnitt 3 legt verbindlich fest:

    Die Fehlerrate ist der Anteil verfaelschter Zellen am **klassenspezifischen
    adressierbaren Zelluniversum** — also an der Menge aller Zellen, die von
    mindestens einer Variante dieser Fehlerklasse ueberhaupt getroffen werden
    koennen.

Der Grund ist rechnerisch zwingend: Jede Klasse adressiert nur einen Teil des
Datensatzes. Bezoege man die Rate auf alle befuellten Zellen, waeren die oberen
Ratenstufen fuer die meisten Klassen unerreichbar, und der Injektor schluege
erst nach Stunden Laufzeit fehl.

Zwei Praezisierungen, die diese Umsetzung hinzufuegt:

* **Gezaehlt werden Traegerzellen.** Zellen, die nur der Satzstimmigkeit wegen
  nachgefuehrt werden — die Rangfolge bei den Skalierungsvarianten —, gehen weder
  in das Universum noch in die Rate ein. Sie sind keine Fehler.
* **Bei den satzbasierten Klassen ist die Einheit die Zeile.** F6 und HO1 fuegen
  Zeilen hinzu; sie haben keine Zielzelle. Das Universum ist dort die Menge der
  duplizierbaren Zeilen, und die Rate bezieht sich darauf.

Verteilung auf die Varianten — proportional zum eigenen Universum
------------------------------------------------------------------

Das Kontingent einer Klasse wird **proportional zum adressierbaren Universum
jeder Variante** zugeteilt::

    n_i = rate · |Klassenuniversum| · universum_i / Σ_j universum_j

**Warum nicht gleichmaessig.** Eine gleichmaessige Zuteilung sieht fairer aus,
erzeugt aber einen Confounder im Kern des Versuchsplans: Varianten mit kleinem
Universum — F4-f, F7-c und F7-d wirken auf der Entitaet ``tarif`` mit nur 231
Zeilen — stossen mit steigender Fehlerrate an ihre Decke. Der nicht ausgeschoepfte
Rest ginge an die reichlich vorhandenen Varianten, und **die Zusammensetzung der
Klasse verschoebe sich mit der Fehlerrate**. Fehlerrate ist aber Faktor UV2 des
Experiments: Ein gemessener Zusammenhang "hoehere Rate, anderer Recall" waere
teils Ratenwirkung, teils Verschiebung der Variantenmischung, und der Trendtest
ueber die Ratenstufen koennte beides nicht trennen.

Bei proportionaler Zuteilung ist der Anteil jeder Variante am Klassenkontingent
**ueber alle Ratenstufen konstant**. Das ist die Voraussetzung dafuer, dass UV2
interpretierbar bleibt.

**Warum nichts ueberlaeuft.** Die Summe der Variantenuniversen ist wegen
Ueberschneidungen — F4-c und F4-d treffen beide ``wohnflaeche_qm`` — nie kleiner
als das Klassenuniversum. Damit gilt fuer jede Rate bis 1::

    n_i = rate · |U_Klasse| · u_i / Σu  ≤  Σu · u_i / Σu  =  u_i

Jede Variante bleibt also innerhalb ihres eigenen Universums.

**Der Preis, und was ihn ausgleicht.** F7-c bekommt bei zwei Prozent nur noch eine
einstellige Zahl an Injektionen. Fuer die klassenweise Auswertung ist das richtig,
fuer den Recall **je Variante** — den empirischen Beleg gegen den
Zirkularitaetsvorwurf — zu wenig. Dafuer gibt es den Variantenmodus: ein Lauf, der
nur eine einzige Variante injiziert, und zwar bis an ihr Universum heran
(:func:`plane` mit ``nur_varianten``). Diese Laeufe gehoeren in den Teilversuch
"Variantencharakterisierung", nicht in den faktoriellen Plan.

Es wird nicht umverteilt
------------------------

Erreicht eine Variante ihr Kontingent nicht, weil ihre Kandidaten erschoepft sind,
bricht der Injektor ab. Er verteilt den Rest **nicht** an die uebrigen Varianten —
das waere genau die Mischungsverschiebung, gegen die die proportionale Zuteilung
gebaut ist. Rechnerisch kann der Fall bis zur Rate eins nicht eintreten; praktisch
koennten zwei Varianten, die dieselben Zellen adressieren, einander Kandidaten
wegnehmen, und dann ist ein Abbruch die richtige Antwort.

Zwei Nebenwirkungen, die dokumentiert gehoeren
----------------------------------------------

* **Seltene Varianten koennen bei kleiner Rate ausfallen.** Liegt der Anteil einer
  Variante unter einer halben Einheit, bekommt sie das Kontingent null. Das ist
  kein Fehler, sondern die Kehrseite konstanter Anteile — und der Grund fuer den
  Variantenmodus. Bei der obersten Ratenstufe faellt keine Variante mehr aus.
* **Gruppengranularitaet.** Eine kohaerente Skalierung veraendert vier
  Beitragsfelder auf einmal und laesst sich nicht teilen. Die erreichte Zahl
  weicht deshalb um weniger als eine Gruppengroesse von der zugeteilten ab. Die
  Abweichung haengt nicht von der Bearbeitungsreihenfolge ab und wird im Manifest
  je Variante ausgewiesen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.injector.modell import Fehlerklasse, InjektionsFehler, Zielart
from src.injector.varianten import VARIANTEN_JE_KLASSE, variante

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence

    from numpy.random import Generator

    from src.injector.modell import Injektionskontext, Kandidat, Variante

__all__ = [
    "Klassenplan",
    "anteile",
    "gemischt",
    "kandidaten_je_variante",
    "plane",
    "quoten",
    "universum",
    "variantenuniversum",
]


def _varianten_der_klasse(
    klasse: Fehlerklasse, nur_varianten: Sequence[str] | None
) -> tuple[Variante, ...]:
    """Gibt die zu injizierenden Varianten einer Klasse zurueck.

    Args:
        klasse: Fehlerklasse.
        nur_varianten: Einschraenkung auf bestimmte Varianten, oder ``None`` fuer
            alle Varianten der Klasse.

    Returns:
        Die Varianten in fester Reihenfolge.
    """
    if nur_varianten is None:
        return VARIANTEN_JE_KLASSE[klasse]
    gewaehlt = set(nur_varianten)
    return tuple(
        eintrag for eintrag in VARIANTEN_JE_KLASSE[klasse] if eintrag.variante_id in gewaehlt
    )


def kandidaten_je_variante(
    kontext: Injektionskontext,
    klasse: Fehlerklasse,
    nur_varianten: Sequence[str] | None = None,
) -> dict[str, tuple[Kandidat, ...]]:
    """Bestimmt die Kandidaten der zu injizierenden Varianten einer Klasse.

    Args:
        kontext: Lesende Sicht auf den sauberen Datensatz.
        klasse: Fehlerklasse.
        nur_varianten: Einschraenkung auf bestimmte Varianten.

    Returns:
        Eine Abbildung Variantenkennung auf ihre Kandidaten, in der Reihenfolge
        der Varianten.
    """
    return {
        eintrag.variante_id: eintrag.kandidaten(kontext)
        for eintrag in _varianten_der_klasse(klasse, nur_varianten)
    }


def _zielart(varianten: Sequence[Variante], klasse: Fehlerklasse) -> Zielart:
    """Gibt die einheitliche Zielart einer Variantenmenge zurueck.

    Raises:
        InjektionsFehler: Wenn zell- und satzbasierte Varianten gemischt werden.
            Die Bezugsgroesse der Fehlerrate waere dann nicht definiert.
    """
    arten = {eintrag.zielart for eintrag in varianten}
    if len(arten) != 1:
        raise InjektionsFehler(
            f"Klasse {klasse.value} mischt Zielarten {sorted(art.value for art in arten)}; "
            "die Bezugsgroesse der Fehlerrate waere nicht definiert"
        )
    return arten.pop()


def variantenuniversum(eintrag: Variante, kandidaten: Sequence[Kandidat]) -> int:
    """Berechnet das adressierbare Universum einer einzelnen Variante.

    Args:
        eintrag: Die Variante.
        kandidaten: Ihre Kandidaten.

    Returns:
        Die Zahl der Traegerzellen beziehungsweise Zeilen, die sie treffen kann.
    """
    if eintrag.zielart is Zielart.SATZ:
        return len({(kandidat.entitaet, kandidat.row_id) for kandidat in kandidaten})

    zellen: set[tuple[str, int, str]] = set()
    for kandidat in kandidaten:
        if kandidat.spalte is None:
            continue
        zellen.add((kandidat.entitaet, kandidat.row_id, kandidat.spalte))
        zellen.update(
            (kandidat.entitaet, kandidat.row_id, zusatz) for zusatz in eintrag.zusatzspalten
        )
    return len(zellen)


def universum(
    klasse: Fehlerklasse,
    kandidaten: Mapping[str, tuple[Kandidat, ...]],
    nur_varianten: Sequence[str] | None = None,
) -> int:
    """Berechnet das adressierbare Universum einer Klasse.

    Anders als die Summe der Variantenuniversen zaehlt diese Groesse jede Zelle
    genau einmal, auch wenn mehrere Varianten sie treffen koennen.

    Args:
        klasse: Fehlerklasse.
        kandidaten: Ergebnis von :func:`kandidaten_je_variante`.
        nur_varianten: Einschraenkung auf bestimmte Varianten.

    Returns:
        Die Zahl der adressierbaren Traegerzellen beziehungsweise Zeilen.
    """
    varianten = _varianten_der_klasse(klasse, nur_varianten)
    if _zielart(varianten, klasse) is Zielart.SATZ:
        zeilen = {
            (kandidat.entitaet, kandidat.row_id)
            for eintrag in varianten
            for kandidat in kandidaten[eintrag.variante_id]
        }
        return len(zeilen)

    zellen: set[tuple[str, int, str]] = set()
    for eintrag in varianten:
        for kandidat in kandidaten[eintrag.variante_id]:
            if kandidat.spalte is None:
                continue
            zellen.add((kandidat.entitaet, kandidat.row_id, kandidat.spalte))
            zellen.update(
                (kandidat.entitaet, kandidat.row_id, zusatz)
                for zusatz in eintrag.zusatzspalten
            )
    return len(zellen)


def anteile(universum_je_variante: Mapping[str, int]) -> dict[str, float]:
    """Berechnet den Anteil jeder Variante am Klassenkontingent.

    Der Anteil haengt **nicht** von der Fehlerrate ab — genau darin liegt der
    Zweck der proportionalen Zuteilung (siehe Modul-Docstring).

    Args:
        universum_je_variante: Universumsgroesse je Variantenkennung.

    Returns:
        Den Anteil je Variantenkennung; die Werte summieren auf 1.

    Raises:
        InjektionsFehler: Wenn die Summe der Universen null ist.
    """
    gesamt = sum(universum_je_variante.values())
    if gesamt <= 0:
        raise InjektionsFehler(
            "Die Summe der Variantenuniversen ist null; es gibt nichts zu verteilen"
        )
    return {kennung: groesse / gesamt for kennung, groesse in universum_je_variante.items()}


def quoten(
    ziel: int,
    varianten: Sequence[Variante],
    universum_je_variante: Mapping[str, int],
) -> dict[str, int]:
    """Verteilt ein Kontingent proportional zum Universum jeder Variante.

    Gerundet wird nach dem Hare-Niemeyer-Verfahren: erst abrunden, dann die
    verbleibenden Einheiten in der Reihenfolge des groessten Restes vergeben. Damit
    summieren die Quoten **exakt** auf das Klassenkontingent, statt es durch
    Rundung zu verfehlen. Bei gleichem Rest entscheidet die feste Reihenfolge der
    Varianten, nicht der Zufall.

    Args:
        ziel: Zu verteilendes Kontingent.
        varianten: Varianten der Klasse in fester Reihenfolge.
        universum_je_variante: Universumsgroesse je Variantenkennung.

    Returns:
        Eine Abbildung Variantenkennung auf ihr Kontingent.

    Raises:
        InjektionsFehler: Wenn die Summe der Universen null ist.
    """
    if not varianten:
        return {}
    gesamt = sum(universum_je_variante[eintrag.variante_id] for eintrag in varianten)
    if gesamt <= 0:
        raise InjektionsFehler(
            "Die Summe der Variantenuniversen ist null; es gibt nichts zu verteilen"
        )

    exakt = {
        eintrag.variante_id: ziel * universum_je_variante[eintrag.variante_id] / gesamt
        for eintrag in varianten
    }
    zugeteilt = {kennung: int(wert) for kennung, wert in exakt.items()}
    offen = ziel - sum(zugeteilt.values())
    reihenfolge = sorted(
        enumerate(varianten),
        key=lambda paar: (-(exakt[paar[1].variante_id] % 1), paar[0]),
    )
    for position in range(offen):
        zugeteilt[reihenfolge[position % len(reihenfolge)][1].variante_id] += 1
    return zugeteilt


@dataclass(frozen=True, slots=True)
class Klassenplan:
    """Der Injektionsplan einer Fehlerklasse.

    Attributes:
        klasse: Fehlerklasse.
        zielart: Bezugseinheit — Zelle oder Satz.
        varianten: Die zu injizierenden Varianten in fester Reihenfolge.
        universum: Groesse des adressierbaren Klassenuniversums.
        universum_je_variante: Groesse des Universums je Variante.
        anteil_je_variante: Anteil je Variante am Klassenkontingent; von der
            Fehlerrate unabhaengig.
        ziel: Angeforderte Zahl der Verfaelschungen.
        quote_je_variante: Kontingent je Variante.
        kandidaten_je_variante: Kandidaten je Variante in fester Reihenfolge.
    """

    klasse: Fehlerklasse
    zielart: Zielart
    varianten: tuple[Variante, ...]
    universum: int
    universum_je_variante: Mapping[str, int]
    anteil_je_variante: Mapping[str, float]
    ziel: int
    quote_je_variante: Mapping[str, int]
    kandidaten_je_variante: Mapping[str, tuple[Kandidat, ...]]


def _pruefe_vorgaben(
    fehlerrate: float,
    klassen_gewichte: Mapping[str, float],
    nur_varianten: Sequence[str] | None,
) -> None:
    """Prueft Fehlerrate, Klassengewichte und Variantenauswahl.

    Raises:
        InjektionsFehler: Bei unzulaessiger Rate, leerer oder unbekannter
            Klassenangabe, nicht positivem Gewicht oder unbekannter Variante.
    """
    if fehlerrate <= 0:
        raise InjektionsFehler(f"Die Fehlerrate muss groesser als null sein, war {fehlerrate}")
    if not klassen_gewichte:
        raise InjektionsFehler("Es wurde keine Fehlerklasse angefordert")

    bekannt = {klasse.value for klasse in Fehlerklasse}
    unbekannt = sorted(set(klassen_gewichte) - bekannt)
    if unbekannt:
        raise InjektionsFehler(
            f"Unbekannte Fehlerklassen: {unbekannt}. Bekannt sind: {sorted(bekannt)}"
        )
    unzulaessig = sorted(name for name, wert in klassen_gewichte.items() if wert <= 0)
    if unzulaessig:
        raise InjektionsFehler(f"Klassengewichte muessen groesser als null sein: {unzulaessig}")

    if nur_varianten is None:
        return
    if not nur_varianten:
        raise InjektionsFehler("Die Variantenauswahl ist leer")
    for kennung in nur_varianten:
        eintrag = variante(kennung)
        if eintrag.fehlerklasse.value not in klassen_gewichte:
            raise InjektionsFehler(
                f"Variante {kennung} gehoert zur Klasse {eintrag.fehlerklasse.value}, "
                f"die nicht angefordert wurde: {sorted(klassen_gewichte)}"
            )


def plane(
    kontext: Injektionskontext,
    fehlerrate: float,
    klassen_gewichte: Mapping[str, float],
    *,
    nur_varianten: Sequence[str] | None = None,
    hoechstzahl: int | None = None,
) -> tuple[Klassenplan, ...]:
    """Stellt den Injektionsplan aller angeforderten Klassen auf.

    Args:
        kontext: Lesende Sicht auf den sauberen Datensatz.
        fehlerrate: Anteil verfaelschter Einheiten am adressierbaren Universum.
        klassen_gewichte: Gewicht je Fehlerklasse. Ein Lauf des Hauptversuchs
            hat genau eine Klasse mit dem Gewicht 1,0; der Mischmodus verteilt
            die Gewichte nach ``spec/03``, Abschnitt 3.
        nur_varianten: Einschraenkung auf bestimmte Varianten. Das Universum und
            damit die Bezugsgroesse der Fehlerrate ist dann das Universum
            **dieser** Varianten, nicht das der ganzen Klasse. Grundlage des
            Teilversuchs "Variantencharakterisierung".
        hoechstzahl: Absolute Obergrenze der Verfaelschungen je Klasse. Begrenzt
            die Laufzeit erschoepfender Variantenlaeufe.

    Returns:
        Je angeforderter Klasse einen :class:`Klassenplan`, in der Reihenfolge
        von :class:`src.injector.modell.Fehlerklasse`.

    Raises:
        InjektionsFehler: Wenn die Fehlerrate oder ein Gewicht unzulaessig ist,
            eine Klasse oder Variante unbekannt ist, ein Universum leer ist oder
            die angeforderte Zahl das Universum uebersteigt. Im letzten Fall wird
            **nicht** stillschweigend weniger aufgefuellt (spec/03, Abschnitt 3).
    """
    _pruefe_vorgaben(fehlerrate, klassen_gewichte, nur_varianten)

    plaene: list[Klassenplan] = []
    for klasse in Fehlerklasse:
        gewicht = klassen_gewichte.get(klasse.value)
        if gewicht is None:
            continue
        varianten = _varianten_der_klasse(klasse, nur_varianten)
        if not varianten:
            continue
        kandidaten = kandidaten_je_variante(kontext, klasse, nur_varianten)
        groesse = universum(klasse, kandidaten, nur_varianten)
        if groesse == 0:
            raise InjektionsFehler(
                f"Klasse {klasse.value}: Das adressierbare Universum ist leer. "
                "Auf diesem Datensatz kann die Auswahl nicht injiziert werden."
            )
        ziel = round(fehlerrate * gewicht * groesse)
        if hoechstzahl is not None:
            ziel = min(ziel, hoechstzahl)
        if ziel > groesse:
            raise InjektionsFehler(
                f"Klasse {klasse.value}: Die angeforderte Fehlerrate {fehlerrate} bei "
                f"Gewicht {gewicht} verlangt {ziel} Verfaelschungen, das adressierbare "
                f"Universum umfasst aber nur {groesse} "
                f"{'Zeilen' if _zielart(varianten, klasse) is Zielart.SATZ else 'Zellen'}. "
                "Der Injektor fuellt nicht stillschweigend weniger auf "
                "(spec/03_fehlerklassen.md, Abschnitt 3)."
            )
        universen = {
            eintrag.variante_id: variantenuniversum(eintrag, kandidaten[eintrag.variante_id])
            for eintrag in varianten
        }
        leer = sorted(kennung for kennung, groesse_i in universen.items() if groesse_i == 0)
        if leer:
            raise InjektionsFehler(
                f"Klasse {klasse.value}: Diese Varianten finden auf dem Datensatz keinen "
                f"Kandidaten: {leer}. Ihr Anteil waere null, und ihr Recall bliebe undefiniert."
            )
        plaene.append(
            Klassenplan(
                klasse=klasse,
                zielart=_zielart(varianten, klasse),
                varianten=varianten,
                universum=groesse,
                universum_je_variante=universen,
                anteil_je_variante=anteile(universen),
                ziel=ziel,
                quote_je_variante=quoten(ziel, varianten, universen),
                kandidaten_je_variante=kandidaten,
            )
        )
    return tuple(plaene)


def gemischt(kandidaten: tuple[Kandidat, ...], rng: Generator) -> tuple[Kandidat, ...]:
    """Mischt eine Kandidatenliste reproduzierbar.

    Gemischt wird ueber eine Permutation der Positionen, nicht ueber ein
    wiederholtes Ziehen mit Verwerfen. Damit steht die Zahl der Zufallsziehungen
    vorab fest und haengt nicht davon ab, wie viele Kandidaten sich als
    unbrauchbar erweisen — sonst verschoebe sich der Strom, sobald eine Variante
    einen Kandidaten zurueckweist.

    Args:
        kandidaten: Zu mischende Kandidaten.
        rng: Zufallsstrom der Variante.

    Returns:
        Die gemischten Kandidaten.
    """
    if not kandidaten:
        return ()
    reihenfolge = rng.permutation(len(kandidaten))
    return tuple(kandidaten[int(position)] for position in reihenfolge)
