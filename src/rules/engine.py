"""Ausfuehrung des Regelkatalogs und Aggregation der Ergebnisse.

Die Engine fuehrt alle Regeln aus, sammelt ihre Verstoesse und legt sie in **zwei
Sichten** ab. Diese Doppelung ist keine Bequemlichkeit, sondern eine
Metrikentscheidung.

Rohtreffer und Vereinigungsmenge
--------------------------------

``verstoesse`` haelt jede Meldung jeder Regel — die Diagnosesicht. Wer wissen will,
welche Regel wie oft ausgeloest hat, schaut hier.

``markierte_zellen`` ist die **Vereinigungsmenge** der Tripel
``(entitaet, row_id, spalte)``. Markieren mehrere Regeln dieselbe Zelle, zaehlt sie
**einmal**. Ohne diese Dedup zaehlte die Auswertung eine Zelle, die von R-009 und
R-025 gleichzeitig gemeldet wird, als zwei Treffer — bei einem einzigen injizierten
Fehler. Die Precision fiele damit, ohne dass der Detektor schlechter waere.

Was nicht in die Zellmetrik eingeht
-----------------------------------

Regeln mit ``in_zellmetrik=False`` (R-047, R-048) sind aus ``markierte_zellen``
ausgenommen. Sie benennen keine verursachende Zelle und werden als
Diagnosekennzahl gefuehrt.

Laufzeit
--------

Je Regel wird die Laufzeit gemessen und in ``rule_timing.json`` abgelegt. Gemessen
wird mit :func:`time.perf_counter`; das ist eine Messgroesse ueber den Lauf, keine
fachliche Berechnung, und beruehrt Architekturregel A2 nicht.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import pandas as pd

from src.common.pfade import Schicht, lauf_verzeichnis
from src.common.serialisierung import ENTITAETEN
from src.rules.katalog import alle_regeln
from src.rules.modell import (
    SATZ_SPALTEN,
    VERSTOSS_SPALTEN,
    Kontext,
    baue_kontext,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from src.common.config import Config
    from src.rules.modell import Regel

__all__ = [
    "DETEKTIONEN_DATEI",
    "MARKIERTE_ZELLEN_DATEI",
    "SATZBEFUNDE_DATEI",
    "TIMING_DATEI",
    "ZELL_SPALTEN",
    "Detektionen",
    "lade_kontext",
    "pruefe_alles",
    "schreibe_detektionen",
]

#: Spalten der Vereinigungsmenge markierter Zellen.
ZELL_SPALTEN: Final[tuple[str, ...]] = ("entitaet", "row_id", "spalte")

#: Dateiname der Rohtreffer je Regel.
DETEKTIONEN_DATEI: Final[str] = "detections.parquet"

#: Dateiname der Vereinigungsmenge markierter Zellen.
MARKIERTE_ZELLEN_DATEI: Final[str] = "markierte_zellen.parquet"

#: Dateiname der satzbezogenen Befunde.
SATZBEFUNDE_DATEI: Final[str] = "detections_records.parquet"

#: Dateiname der Laufzeitmessung je Regel.
TIMING_DATEI: Final[str] = "rule_timing.json"


@dataclass(frozen=True, slots=True)
class Detektionen:
    """Ergebnis eines vollstaendigen Katalogdurchlaufs.

    Attributes:
        verstoesse: Rohtreffer je Regel, eine Zeile je gemeldeter Zelle.
        saetze: Satzbezogene Befunde mit den beteiligten ``row_id``.
        markierte_zellen: Vereinigungsmenge der Tripel
            ``(entitaet, row_id, spalte)`` ueber alle Regeln mit
            ``in_zellmetrik=True``.
        laufzeiten: Laufzeit je Regel in Sekunden, in Katalogreihenfolge.
        meldungen_je_regel: Zahl der Zellmeldungen je Regel, in Katalogreihenfolge.
        saetze_je_regel: Zahl der Satzmeldungen je Regel, in Katalogreihenfolge.
    """

    verstoesse: pd.DataFrame
    saetze: pd.DataFrame
    markierte_zellen: pd.DataFrame
    laufzeiten: Mapping[str, float]
    meldungen_je_regel: Mapping[str, int]
    saetze_je_regel: Mapping[str, int]

    @property
    def anzahl_meldungen(self) -> int:
        """Gesamtzahl der Zellmeldungen ueber alle Regeln."""
        return len(self.verstoesse)

    @property
    def anzahl_saetze(self) -> int:
        """Gesamtzahl der satzbezogenen Befunde."""
        return len(self.saetze)


def pruefe_alles(kontext: Kontext, regeln: Sequence[Regel] | None = None) -> Detektionen:
    """Fuehrt den Regelkatalog aus und aggregiert die Ergebnisse.

    Die Regeln laufen in Katalogreihenfolge. Das ist Teil der Reproduzierbarkeit:
    Die ``verstoss_id`` haengt an der Reihenfolge der Meldungen innerhalb einer
    Regel, und die Zeilenreihenfolge des Ergebnisrahmens an der Reihenfolge der
    Regeln (Architekturregel A2).

    Args:
        kontext: Pruefkontext ueber beide Datenschichten.
        regeln: Auszufuehrende Regeln. Ohne Angabe der vollstaendige Katalog.

    Returns:
        Die :class:`Detektionen`.
    """
    auswahl = tuple(regeln) if regeln is not None else alle_regeln()

    zellrahmen: list[pd.DataFrame] = []
    satzrahmen: list[pd.DataFrame] = []
    laufzeiten: dict[str, float] = {}
    meldungen: dict[str, int] = {}
    saetze: dict[str, int] = {}
    markiert: list[tuple[str, int, str]] = []
    gesehen: set[tuple[str, int, str]] = set()

    for eintrag in auswahl:
        beginn = time.perf_counter()
        befund = eintrag.pruefe(kontext)
        laufzeiten[eintrag.regel_id] = time.perf_counter() - beginn

        meldungen[eintrag.regel_id] = len(befund.zellen)
        saetze[eintrag.regel_id] = len(befund.saetze)
        if befund.zellen:
            zellrahmen.append(befund.als_rahmen(eintrag.regel_id))
        if befund.saetze:
            satzrahmen.append(befund.als_satzrahmen(eintrag.regel_id))

        if not eintrag.in_zellmetrik:
            continue
        for verstoss in befund.zellen:
            tripel = (verstoss.entitaet, verstoss.row_id, verstoss.spalte)
            if tripel in gesehen:
                continue
            gesehen.add(tripel)
            markiert.append(tripel)

    return Detektionen(
        verstoesse=_verbinde(zellrahmen, VERSTOSS_SPALTEN),
        saetze=_verbinde(satzrahmen, SATZ_SPALTEN),
        markierte_zellen=pd.DataFrame(markiert, columns=list(ZELL_SPALTEN)),
        laufzeiten=laufzeiten,
        meldungen_je_regel=meldungen,
        saetze_je_regel=saetze,
    )


def _verbinde(rahmen: Sequence[pd.DataFrame], spalten: Sequence[str]) -> pd.DataFrame:
    """Haengt Teilrahmen aneinander und gibt bei leerer Eingabe das leere Schema zurueck."""
    if not rahmen:
        return pd.DataFrame(columns=list(spalten))
    return pd.concat(rahmen, ignore_index=True)


def lade_kontext(config: Config, run_id: str) -> Kontext:
    """Laedt beide Datenschichten eines Laufs von der Platte.

    Args:
        config: Geladene Konfiguration.
        run_id: Kennung des Laufs.

    Returns:
        Den Pruefkontext.

    Raises:
        FileNotFoundError: Wenn eine Entitaetsdatei fehlt. Bewusst kein stiller
            Ersatz durch einen leeren Rahmen — ein unvollstaendiger Datensatz
            wuerde stumm zu einem unvollstaendigen Messergebnis fuehren.
    """
    from src.common.pfade import entitaet_pfad  # noqa: PLC0415 - vermeidet Zyklus im Modulkopf

    schichten: dict[Schicht, dict[str, pd.DataFrame]] = {Schicht.TYPED: {}, Schicht.RAW: {}}
    for schicht in (Schicht.TYPED, Schicht.RAW):
        for entitaet in ENTITAETEN:
            pfad = entitaet_pfad(config, run_id, schicht, entitaet)
            if not pfad.is_file():
                raise FileNotFoundError(
                    f"Der Lauf {run_id} hat keine Datei {pfad}. Der saubere Datensatz wird "
                    "mit 'python scripts/generate.py --run-id <id>' erzeugt."
                )
            schichten[schicht][entitaet] = pd.read_parquet(pfad).reset_index(drop=True)

    return baue_kontext(
        config, typed=schichten[Schicht.TYPED], raw=schichten[Schicht.RAW]
    )


def schreibe_detektionen(
    config: Config,
    run_id: str,
    detektionen: Detektionen,
    *,
    unterordner: str | None = None,
) -> Path:
    """Legt Rohtreffer, Vereinigungsmenge, Satzbefunde und Laufzeiten ab.

    Args:
        config: Geladene Konfiguration.
        run_id: Kennung des Laufs.
        detektionen: Ergebnis von :func:`pruefe_alles`.
        unterordner: Unterverzeichnis unterhalb des Laufverzeichnisses, zum
            Beispiel ``"clean"``. Ohne Angabe wird direkt in das Laufverzeichnis
            geschrieben.

    Returns:
        Das Verzeichnis, in das geschrieben wurde.
    """
    ziel = lauf_verzeichnis(config, run_id)
    if unterordner is not None:
        ziel = ziel / unterordner
    ziel.mkdir(parents=True, exist_ok=True)

    detektionen.verstoesse.to_parquet(ziel / DETEKTIONEN_DATEI, index=False)
    detektionen.markierte_zellen.to_parquet(ziel / MARKIERTE_ZELLEN_DATEI, index=False)
    detektionen.saetze.to_parquet(ziel / SATZBEFUNDE_DATEI, index=False)
    (ziel / TIMING_DATEI).write_text(
        json.dumps(
            {
                "run_id": run_id,
                "laufzeit_sekunden_je_regel": {
                    regel_id: round(dauer, 6)
                    for regel_id, dauer in detektionen.laufzeiten.items()
                },
                "laufzeit_sekunden_gesamt": round(sum(detektionen.laufzeiten.values()), 6),
            },
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return ziel
