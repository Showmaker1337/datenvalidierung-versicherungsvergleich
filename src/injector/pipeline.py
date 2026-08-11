"""Orchestrierung der Fehlerinjektion.

Ablauf eines Laufs
------------------

1. Die Rohschicht wird geprueft und in eine lesende Sicht ueberfuehrt
   (:func:`src.injector.modell.baue_kontext`).
2. Je angeforderter Fehlerklasse werden das adressierbare Universum, das
   Kontingent und die Verteilung auf die Varianten bestimmt
   (:mod:`src.injector.auswahl`).
3. Die Varianten arbeiten ihre Kontingente ab. Jede Aenderung durchlaeuft vorher
   die Pruefungen aus ``spec/03``, Abschnitt 5.
4. Die veraenderten Spalten werden zurueck in Datenrahmen gegossen, der Ground
   Truth in seine beiden Logs.

Die vier Pruefungen vor jeder Aenderung
---------------------------------------

* **``row_id`` ist niemals Ziel** (Protokollregel 1). Wird sie es doch, ist das
  ein Programmierfehler und fuehrt zum Abbruch, nicht zu einer Warnung.
* **Keine Doppelinjektion** (Protokollregel 2). Ein Set bereits getroffener
  Tripel aus Entitaet, Zeilenkennung und Spalte verhindert, dass zwei Varianten
  dieselbe Zelle anfassen. Bei einer Kollision wird die gesamte Aenderung
  verworfen und der naechste Kandidat genommen — nicht nur die kollidierende
  Zelle, denn eine halb angewandte Skalierung waere ein anderer Fehler als der
  beabsichtigte.
* **Effektivitaetspruefung** (Protokollregel 3). Erzeugt eine Variante zufaellig
  denselben Wert, wird sie verworfen. Ohne diese Pruefung entstuende eine
  Phantom-Ground-Truth und damit ein garantiertes False Negative — laut
  ``spec/03`` der haeufigste Bug in solchen Aufbauten.
* **Neue Zeilen bekommen neue Zeilenkennungen.** Die Originalzeile bleibt
  unveraendert. Eine wiederverwendete Kennung liesse den Join des
  Diff-Gegenchecks aufblaehen.

Warum ``seed_inject`` eine ``SeedSequence`` ist
-----------------------------------------------

Nicht ``int``: Die Faktorstufen eines Experimentlaufs gehen ueber
:func:`src.common.seeding.lauf_seed` in den Strom ein, und dieser Mechanismus
steht seit Phase 1. Ein roher ``int`` wuerde Architekturregel A2 unterlaufen.

Warum die Konfiguration als Schluesselwortargument hinzukommt
-------------------------------------------------------------

Die Varianten F4-a und F4-b brauchen den ``stichtag``, HO2-a die Referenztabelle
der Postleitzahlen. Beides kommt aus der Konfiguration und **niemals** aus der
Systemzeit oder einem Netzzugriff (Architekturregel A2, CLAUDE.md, Abschnitt 5).
Der Parameter steht bewusst hinter dem Stern: Die fuenf in der Phasenvorgabe
genannten Parameter behalten Name, Reihenfolge und Position.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pandas as pd

from src.common.pfade import pruefe_run_id
from src.common.seeding import generator, seed_als_int, teilstrom, wurzel_seeds
from src.common.serialisierung import ENTITAETEN, SPALTEN_JE_ENTITAET
from src.injector.auswahl import gemischt, plane, quoten
from src.injector.modell import (
    KLASSEN_NUMMER,
    Aenderung,
    Injektionsergebnis,
    InjektionsFehler,
    Zellaenderung,
    Zielart,
    baue_kontext,
)
from src.injector.protokoll import Laufkennung, Protokoll
from src.injector.varianten import VARIANTEN_JE_KLASSE

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping

    from numpy.random import Generator, SeedSequence

    from src.common.config import Config
    from src.injector.auswahl import Klassenplan
    from src.injector.modell import Injektionskontext, Kandidat, Variante

__all__ = ["injiziere"]

#: Hoechstzahl der Umverteilungsrunden je Klasse.
#:
#: Jede Runde verbraucht mindestens einen Kandidaten, das Verfahren terminiert
#: also von selbst. Die Schranke ist eine Notbremse gegen einen Denkfehler, nicht
#: Teil des Verfahrens.
_MAX_RUNDEN: Final[int] = 64

#: Darstellung eines fehlenden Wertes im Log.
#:
#: Die Rohschicht kennt zwei Auspraegungen von "kein Wert": das fehlende Feld
#: (``pd.NA``) und den Leerstring. Im Log stehen beide als Leerstring, weil das
#: Diff des Gegenchecks sie ebenso zusammenfuehrt — sonst meldete er eine
#: Abweichung, die keine ist.
_LEER_IM_LOG: Final[str] = ""


def injiziere(  # noqa: PLR0913 - die Signatur ist in der Phasenvorgabe festgelegt
    daten_raw: Mapping[str, pd.DataFrame],
    fehlerrate: float,
    klassen_gewichte: Mapping[str, float],
    seed_inject: SeedSequence,
    run_id: str,
    *,
    config: Config,
) -> Injektionsergebnis:
    """Verfaelscht die Rohschicht kontrolliert und protokolliert jede Verfaelschung.

    Args:
        daten_raw: Die sieben Datenrahmen der Rohschicht, alle Spalten als
            Zeichenkette. Wird versehentlich ``df_typed`` uebergeben, bricht der
            Aufruf mit klarer Meldung ab; es wird nicht konvertiert.
        fehlerrate: Anteil verfaelschter Einheiten am klassenspezifischen
            adressierbaren Universum (spec/03, Abschnitt 3).
        klassen_gewichte: Gewicht je Fehlerklasse. Ein Lauf des Hauptversuchs
            fuehrt genau eine Klasse mit Gewicht 1,0.
        seed_inject: Zufallsstrom der Injektion, unabhaengig vom Strom des
            Basisdatensatzes.
        run_id: Kennung des Laufs; steht in jeder Protokollzeile.
        config: Geladene Konfiguration.

    Returns:
        Das :class:`~src.injector.modell.Injektionsergebnis` mit den
        verfaelschten Datenrahmen und beiden Ground-Truth-Logs.

    Raises:
        InjektionsFehler: Wenn die Eingabe nicht die Rohschicht ist, eine
            Fehlerklasse unbekannt ist, ein Universum leer ist oder die
            angeforderte Fehlerrate mehr Einheiten verlangt, als das Universum
            hergibt.
    """
    pruefe_run_id(run_id)
    kontext = baue_kontext(config, daten_raw)
    plaene = plane(kontext, fehlerrate, klassen_gewichte)

    werte: dict[str, dict[str, list[str | None]]] = {
        entitaet: {spalte: list(reihe) for spalte, reihe in spalten.items()}
        for entitaet, spalten in kontext.werte.items()
    }
    naechste_row_id = {
        entitaet: (max(kennungen) + 1 if kennungen else 0)
        for entitaet, kennungen in kontext.row_ids.items()
    }
    kennung = Laufkennung(
        run_id=run_id,
        master_seed=config.master_seed,
        seed_base=str(seed_als_int(wurzel_seeds(config.master_seed).basis)),
        seed_inject=str(seed_als_int(seed_inject)),
    )
    protokoll = Protokoll(kennung)
    belegte_zellen: set[tuple[str, int, str]] = set()
    belegte_saetze: set[tuple[str, int]] = set()

    fehler_je_variante: dict[str, int] = {}
    fehler_je_klasse: dict[str, int] = {}
    for plan in plaene:
        erreicht = _fuelle_klasse(
            plan,
            kontext=kontext,
            seed_inject=seed_inject,
            werte=werte,
            naechste_row_id=naechste_row_id,
            protokoll=protokoll,
            belegte_zellen=belegte_zellen,
            belegte_saetze=belegte_saetze,
        )
        fehler_je_variante.update(erreicht)
        fehler_je_klasse[plan.klasse.value] = sum(erreicht.values())

    return Injektionsergebnis(
        run_id=run_id,
        df_raw_dirty=_baue_rahmen(werte),
        error_log=protokoll.error_log(),
        error_log_records=protokoll.error_log_records(),
        universum={plan.klasse.value: plan.universum for plan in plaene},
        einheit_je_klasse={plan.klasse.value: plan.zielart.value for plan in plaene},
        ziel_je_klasse={plan.klasse.value: plan.ziel for plan in plaene},
        fehler_je_klasse=fehler_je_klasse,
        fehler_je_variante=fehler_je_variante,
        mitgezogene_zellen=protokoll.anzahl_zellen - protokoll.anzahl_traeger,
        seeds={
            "master_seed": str(config.master_seed),
            "seed_base": kennung.seed_base,
            "seed_inject": kennung.seed_inject,
        },
    )


def _stroeme(plan: Klassenplan, seed_inject: SeedSequence) -> dict[str, Generator]:
    """Leitet je Variante einen eigenen Zufallsstrom ab."""
    klassenstrom = teilstrom(seed_inject, KLASSEN_NUMMER[plan.klasse])
    return {
        eintrag.variante_id: generator(teilstrom(klassenstrom, position))
        for position, eintrag in enumerate(VARIANTEN_JE_KLASSE[plan.klasse])
    }


def _fuelle_klasse(  # noqa: PLR0913 - der Zustand des Laufs wird ausdruecklich durchgereicht
    plan: Klassenplan,
    *,
    kontext: Injektionskontext,
    seed_inject: SeedSequence,
    werte: dict[str, dict[str, list[str | None]]],
    naechste_row_id: dict[str, int],
    protokoll: Protokoll,
    belegte_zellen: set[tuple[str, int, str]],
    belegte_saetze: set[tuple[str, int]],
) -> dict[str, int]:
    """Arbeitet das Kontingent einer Fehlerklasse ab.

    Returns:
        Die erreichte Zahl der Verfaelschungen je Variante.

    Raises:
        InjektionsFehler: Wenn das Kontingent der Klasse nicht erreicht wird,
            weil die Kandidaten erschoepft sind.
    """
    varianten = VARIANTEN_JE_KLASSE[plan.klasse]
    stroeme = _stroeme(plan, seed_inject)
    reihenfolge = {
        eintrag.variante_id: gemischt(
            plan.kandidaten_je_variante[eintrag.variante_id], stroeme[eintrag.variante_id]
        )
        for eintrag in varianten
    }
    position = {eintrag.variante_id: 0 for eintrag in varianten}
    erreicht = {eintrag.variante_id: 0 for eintrag in varianten}
    quote = dict(plan.quote_je_variante)
    rest = plan.ziel

    for _runde in range(_MAX_RUNDEN):
        for eintrag in varianten:
            kennung = eintrag.variante_id
            while (
                rest > 0
                and erreicht[kennung] < quote[kennung]
                and position[kennung] < len(reihenfolge[kennung])
            ):
                kandidat = reihenfolge[kennung][position[kennung]]
                position[kennung] += 1
                aenderung = _pruefe(
                    kontext, eintrag, kandidat, stroeme[kennung], belegte_zellen, belegte_saetze
                )
                if aenderung is None:
                    continue
                gewicht = _wende_an(
                    aenderung,
                    variante=eintrag,
                    kontext=kontext,
                    werte=werte,
                    naechste_row_id=naechste_row_id,
                    protokoll=protokoll,
                    belegte_zellen=belegte_zellen,
                    belegte_saetze=belegte_saetze,
                )
                erreicht[kennung] += gewicht
                rest -= gewicht
        if rest <= 0:
            return erreicht

        offen = tuple(
            eintrag
            for eintrag in varianten
            if position[eintrag.variante_id] < len(reihenfolge[eintrag.variante_id])
        )
        if not offen:
            raise InjektionsFehler(
                f"Klasse {plan.klasse.value}: Von {plan.ziel} angeforderten "
                f"Verfaelschungen wurden nur {plan.ziel - rest} erreicht; die Kandidaten "
                f"sind erschoepft. Adressierbares Universum: {plan.universum}. "
                "Der Injektor fuellt nicht stillschweigend weniger auf."
            )
        for kennung, zusatz in quoten(rest, offen).items():
            quote[kennung] = erreicht[kennung] + zusatz

    raise InjektionsFehler(
        f"Klasse {plan.klasse.value}: Die Umverteilung kam nach {_MAX_RUNDEN} Runden "
        "nicht zum Ziel. Das ist ein Programmierfehler, kein Datenbefund."
    )


def _pruefe(  # noqa: PLR0911, PLR0913, PLR0917 - Zustand und Abbruchgruende sind explizit
    kontext: Injektionskontext,
    variante: Variante,
    kandidat: Kandidat,
    rng: Generator,
    belegte_zellen: set[tuple[str, int, str]],
    belegte_saetze: set[tuple[str, int]],
) -> Aenderung | None:
    """Wendet eine Variante probeweise an und prueft die Protokollregeln.

    Returns:
        Die bereinigte Aenderung, oder ``None``, wenn der Kandidat nicht
        brauchbar ist. Wirkungslose nachgefuehrte Zellen werden entfernt;
        eine wirkungslose Traegerzelle oder eine Kollision verwirft die
        gesamte Aenderung.

    Raises:
        InjektionsFehler: Wenn eine Variante ``row_id`` treffen will.
    """
    if (
        variante.zielart is Zielart.SATZ
        and (kandidat.entitaet, kandidat.row_id) in belegte_saetze
    ):
        return None
    aenderung = variante.anwenden(kontext, kandidat, rng)
    if aenderung is None:
        return None

    behalten: list[Zellaenderung] = []
    gesehen: set[tuple[str, int, str]] = set()
    for zelle in aenderung.zellen:
        schluessel = (zelle.entitaet, zelle.row_id, zelle.spalte)
        if zelle.spalte == "row_id":
            raise InjektionsFehler(
                f"Variante {variante.variante_id} will row_id verfaelschen "
                "(Architekturregel A3)"
            )
        if schluessel in belegte_zellen or schluessel in gesehen:
            return None
        clean = kontext.wert(zelle.entitaet, zelle.row_id, zelle.spalte)
        if clean == _text(zelle.wert_dirty):
            if zelle.mitgezogen:
                continue
            return None
        gesehen.add(schluessel)
        behalten.append(zelle)

    if variante.zielart is Zielart.ZELLE and not any(
        not zelle.mitgezogen for zelle in behalten
    ):
        return None
    if variante.zielart is Zielart.SATZ and not aenderung.saetze:
        return None
    return Aenderung(
        zellen=tuple(behalten), saetze=aenderung.saetze, befunde=aenderung.befunde
    )


def _wende_an(  # noqa: PLR0913 - der Zustand des Laufs wird ausdruecklich durchgereicht
    aenderung: Aenderung,
    *,
    variante: Variante,
    kontext: Injektionskontext,
    werte: dict[str, dict[str, list[str | None]]],
    naechste_row_id: dict[str, int],
    protokoll: Protokoll,
    belegte_zellen: set[tuple[str, int, str]],
    belegte_saetze: set[tuple[str, int]],
) -> int:
    """Schreibt eine gepruefte Aenderung in die Arbeitsdaten und ins Protokoll.

    Returns:
        Die Zahl der Traegerzellen beziehungsweise der hinzugefuegten Zeilen —
        also das, was auf das Kontingent der Klasse angerechnet wird.
    """
    for zelle in aenderung.zellen:
        index = kontext.zeile[zelle.entitaet][zelle.row_id]
        clean = kontext.wert(zelle.entitaet, zelle.row_id, zelle.spalte)
        werte[zelle.entitaet][zelle.spalte][index] = zelle.wert_dirty
        belegte_zellen.add((zelle.entitaet, zelle.row_id, zelle.spalte))
        protokoll.vermerke_zelle(
            fehlerklasse=variante.fehlerklasse,
            injektor_variante_id=variante.variante_id,
            entitaet=zelle.entitaet,
            row_id=zelle.row_id,
            spalte=zelle.spalte,
            wert_clean=clean,
            wert_dirty=_text(zelle.wert_dirty),
            mitgezogen=zelle.mitgezogen,
        )

    for satz in aenderung.saetze:
        neue_kennung = naechste_row_id[satz.entitaet]
        naechste_row_id[satz.entitaet] = neue_kennung + 1
        _haenge_zeile_an(werte[satz.entitaet], satz.entitaet, satz.werte, neue_kennung)
        belegte_saetze.add((satz.entitaet, satz.referenz_row_id))
        protokoll.vermerke_satz(
            fehlerklasse=variante.fehlerklasse,
            injektor_variante_id=variante.variante_id,
            entitaet=satz.entitaet,
            betroffene_row_ids=(satz.referenz_row_id, neue_kennung),
            referenz_row_id=satz.referenz_row_id,
        )

    for befund in aenderung.befunde:
        protokoll.vermerke_satz(
            fehlerklasse=variante.fehlerklasse,
            injektor_variante_id=variante.variante_id,
            entitaet=befund.entitaet,
            betroffene_row_ids=befund.betroffene_row_ids,
            referenz_row_id=befund.referenz_row_id,
        )

    if variante.zielart is Zielart.SATZ:
        return len(aenderung.saetze)
    return sum(1 for zelle in aenderung.zellen if not zelle.mitgezogen)


def _haenge_zeile_an(
    spalten: dict[str, list[str | None]],
    entitaet: str,
    zeilenwerte: Mapping[str, str],
    row_id: int,
) -> None:
    """Haengt eine neue Zeile an die Arbeitsdaten einer Entitaet an.

    Raises:
        InjektionsFehler: Wenn die neue Zeile nicht zum Schema passt.
    """
    erwartet = tuple(name for name in SPALTEN_JE_ENTITAET[entitaet] if name != "row_id")
    fehlend = [name for name in erwartet if name not in zeilenwerte]
    ueberzaehlig = [name for name in zeilenwerte if name not in erwartet]
    if fehlend or ueberzaehlig:
        raise InjektionsFehler(
            f"Neue Zeile in {entitaet}: fehlende Spalten {fehlend}, "
            f"ueberzaehlige {ueberzaehlig}"
        )
    spalten["row_id"].append(str(row_id))
    for name in erwartet:
        spalten[name].append(zeilenwerte[name])


def _baue_rahmen(werte: Mapping[str, Mapping[str, list[str | None]]]) -> dict[str, pd.DataFrame]:
    """Giesst die Arbeitsdaten zurueck in Datenrahmen der Rohschicht."""
    return {
        entitaet: pd.DataFrame(
            {
                spalte: pd.array(werte[entitaet][spalte], dtype="string")
                for spalte in SPALTEN_JE_ENTITAET[entitaet]
            },
            columns=list(SPALTEN_JE_ENTITAET[entitaet]),
        )
        for entitaet in ENTITAETEN
    }


def _text(wert: str | None) -> str:
    """Bildet einen fehlenden Wert auf seine Darstellung im Log ab."""
    return _LEER_IM_LOG if wert is None else wert
