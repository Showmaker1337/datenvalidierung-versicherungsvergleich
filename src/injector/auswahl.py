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

Verteilung auf die Varianten
----------------------------

Das Kontingent einer Klasse wird **gleichmaessig auf ihre Varianten** verteilt.
Das ist kein Detail: ``spec/03``, Abschnitt 2 verlangt, den Recall **je Variante**
zu berichten. Zoege man die Zellen einfach aus dem Klassenuniversum, bekaemen
Varianten mit kleiner Kandidatenmenge — etwa F2-a, das eine fuehrende Null
voraussetzt — so wenige Treffer, dass ihr Recall nicht mehr aussagekraeftig
waere.

Kann eine Variante ihr Kontingent nicht fuellen, geht der Rest an die uebrigen
Varianten derselben Klasse. Reicht auch das nicht, bricht der Injektor ab — er
fuellt **nicht** stillschweigend weniger auf.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.injector.modell import Fehlerklasse, InjektionsFehler, Zielart
from src.injector.varianten import VARIANTEN_JE_KLASSE

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping

    from numpy.random import Generator

    from src.injector.modell import Injektionskontext, Kandidat, Variante

__all__ = [
    "Klassenplan",
    "gemischt",
    "kandidaten_je_variante",
    "plane",
    "quoten",
    "universum",
]


def kandidaten_je_variante(
    kontext: Injektionskontext, klasse: Fehlerklasse
) -> dict[str, tuple[Kandidat, ...]]:
    """Bestimmt die Kandidaten aller Varianten einer Klasse.

    Args:
        kontext: Lesende Sicht auf den sauberen Datensatz.
        klasse: Fehlerklasse.

    Returns:
        Eine Abbildung Variantenkennung auf ihre Kandidaten, in der Reihenfolge
        der Varianten.
    """
    return {
        eintrag.variante_id: eintrag.kandidaten(kontext)
        for eintrag in VARIANTEN_JE_KLASSE[klasse]
    }


def _zielart(klasse: Fehlerklasse) -> Zielart:
    """Gibt die einheitliche Zielart einer Klasse zurueck.

    Raises:
        InjektionsFehler: Wenn eine Klasse zell- und satzbasierte Varianten
            mischt. Die Bezugsgroesse der Fehlerrate waere dann nicht definiert.
    """
    arten = {eintrag.zielart for eintrag in VARIANTEN_JE_KLASSE[klasse]}
    if len(arten) != 1:
        raise InjektionsFehler(
            f"Klasse {klasse.value} mischt Zielarten {sorted(art.value for art in arten)}; "
            "die Bezugsgroesse der Fehlerrate waere nicht definiert"
        )
    return arten.pop()


def universum(
    klasse: Fehlerklasse,
    kandidaten: Mapping[str, tuple[Kandidat, ...]],
) -> int:
    """Berechnet das adressierbare Universum einer Klasse.

    Args:
        klasse: Fehlerklasse.
        kandidaten: Ergebnis von :func:`kandidaten_je_variante`.

    Returns:
        Die Zahl der adressierbaren Traegerzellen beziehungsweise Zeilen.
    """
    if _zielart(klasse) is Zielart.SATZ:
        zeilen = {
            (kandidat.entitaet, kandidat.row_id)
            for eintrag in VARIANTEN_JE_KLASSE[klasse]
            for kandidat in kandidaten[eintrag.variante_id]
        }
        return len(zeilen)

    zellen: set[tuple[str, int, str]] = set()
    for eintrag in VARIANTEN_JE_KLASSE[klasse]:
        for kandidat in kandidaten[eintrag.variante_id]:
            if kandidat.spalte is None:
                continue
            zellen.add((kandidat.entitaet, kandidat.row_id, kandidat.spalte))
            zellen.update(
                (kandidat.entitaet, kandidat.row_id, zusatz)
                for zusatz in eintrag.zusatzspalten
            )
    return len(zellen)


def quoten(ziel: int, varianten: tuple[Variante, ...]) -> dict[str, int]:
    """Verteilt ein Kontingent gleichmaessig auf die Varianten einer Klasse.

    Der Rest der ganzzahligen Teilung geht an die ersten Varianten in fester
    Reihenfolge. Damit haengt die Verteilung nicht vom Zufall ab.

    Args:
        ziel: Zu verteilendes Kontingent.
        varianten: Varianten der Klasse in fester Reihenfolge.

    Returns:
        Eine Abbildung Variantenkennung auf ihr Kontingent.
    """
    if not varianten:
        return {}
    grund, rest = divmod(ziel, len(varianten))
    return {
        eintrag.variante_id: grund + (1 if position < rest else 0)
        for position, eintrag in enumerate(varianten)
    }


@dataclass(frozen=True, slots=True)
class Klassenplan:
    """Der Injektionsplan einer Fehlerklasse.

    Attributes:
        klasse: Fehlerklasse.
        zielart: Bezugseinheit — Zelle oder Satz.
        universum: Groesse des adressierbaren Universums.
        ziel: Angeforderte Zahl der Verfaelschungen.
        quote_je_variante: Kontingent je Variante.
        kandidaten_je_variante: Kandidaten je Variante in fester Reihenfolge.
    """

    klasse: Fehlerklasse
    zielart: Zielart
    universum: int
    ziel: int
    quote_je_variante: Mapping[str, int]
    kandidaten_je_variante: Mapping[str, tuple[Kandidat, ...]]


def plane(
    kontext: Injektionskontext,
    fehlerrate: float,
    klassen_gewichte: Mapping[str, float],
) -> tuple[Klassenplan, ...]:
    """Stellt den Injektionsplan aller angeforderten Klassen auf.

    Args:
        kontext: Lesende Sicht auf den sauberen Datensatz.
        fehlerrate: Anteil verfaelschter Einheiten am klassenspezifischen
            Universum.
        klassen_gewichte: Gewicht je Fehlerklasse. Ein Lauf des Hauptversuchs
            hat genau eine Klasse mit dem Gewicht 1,0; der Mischmodus verteilt
            die Gewichte nach ``spec/03``, Abschnitt 3.

    Returns:
        Je angeforderter Klasse einen :class:`Klassenplan`, in der Reihenfolge
        von :class:`src.injector.modell.Fehlerklasse`.

    Raises:
        InjektionsFehler: Wenn die Fehlerrate oder ein Gewicht unzulaessig ist,
            eine Klasse unbekannt ist, ein Universum leer ist oder die
            angeforderte Zahl das Universum uebersteigt. Im letzten Fall wird
            **nicht** stillschweigend weniger aufgefuellt (spec/03, Abschnitt 3).
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

    plaene: list[Klassenplan] = []
    for klasse in Fehlerklasse:
        gewicht = klassen_gewichte.get(klasse.value)
        if gewicht is None:
            continue
        kandidaten = kandidaten_je_variante(kontext, klasse)
        groesse = universum(klasse, kandidaten)
        if groesse == 0:
            raise InjektionsFehler(
                f"Klasse {klasse.value}: Das adressierbare Universum ist leer. "
                "Auf diesem Datensatz kann die Klasse nicht injiziert werden."
            )
        ziel = round(fehlerrate * gewicht * groesse)
        if ziel > groesse:
            raise InjektionsFehler(
                f"Klasse {klasse.value}: Die angeforderte Fehlerrate {fehlerrate} bei "
                f"Gewicht {gewicht} verlangt {ziel} Verfaelschungen, das adressierbare "
                f"Universum umfasst aber nur {groesse} "
                f"{'Zeilen' if _zielart(klasse) is Zielart.SATZ else 'Zellen'}. "
                "Der Injektor fuellt nicht stillschweigend weniger auf "
                "(spec/03_fehlerklassen.md, Abschnitt 3)."
            )
        plaene.append(
            Klassenplan(
                klasse=klasse,
                zielart=_zielart(klasse),
                universum=groesse,
                ziel=ziel,
                quote_je_variante=quoten(ziel, VARIANTEN_JE_KLASSE[klasse]),
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
