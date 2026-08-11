"""Unabhaengiger Diff-Gegencheck des Ground Truth (Protokollregel 4).

``spec/03_fehlerklassen.md``, Abschnitt 5 verlangt:

    Nach der Injektion wird ein zellweises Diff zwischen ``df_clean`` und
    ``df_dirty`` ueber ``row_id`` berechnet und gegen ``error_log`` abgeglichen.
    Die Mengen muessen identisch sein. **Dieser Check ist unabhaengig vom
    Injektorcode zu implementieren** — er deckt Protokollierungsluecken auf, die
    der Injektor selbst nicht sehen kann.

Warum dieses Modul ausserhalb von ``src/injector`` liegt
--------------------------------------------------------

Ein Gegencheck, der die Logik des Geprueften teilt, prueft nichts. Wuerde er
dieselbe Funktion aufrufen, die den Wert geschrieben hat, bestaetigte er nur,
dass diese Funktion mit sich selbst uebereinstimmt. ``tests/test_architecture.py``
prueft am Importgraphen, dass ``src/verify`` nichts aus ``src/injector``
importiert — auch nicht ueber einen Umweg.

Dieses Modul kennt deshalb weder die Variantendefinitionen noch die
Log-Schemakonstanten des Injektors. Die Spaltennamen, gegen die es prueft, stehen
hier ausgeschrieben; sie stammen aus ``spec/03``, Abschnitt 4, nicht aus dem
Quelltext des Injektors.

Was geprueft wird
-----------------

1. Jede im Diff gefundene Abweichung steht im ``error_log``.
2. Jede ``error_log``-Zeile taucht im Diff auf, mit denselben Werten.
3. Zeilen, die nur in ``df_dirty`` existieren, stehen im ``error_log_records``.
4. Zeilen, die nur in ``df_clean`` existieren, ebenso.
5. ``row_id`` ist nirgends Ziel, und keine Zelle ist doppelt protokolliert.
6. Fuer jede Log-Zeile gilt ``wert_clean != wert_dirty`` — die
   Effektivitaetspruefung, hier ein zweites Mal und aus unabhaengiger Quelle.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

import pandas as pd

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Iterable, Mapping, Sequence
    from pathlib import Path

__all__ = [
    "Gegencheckfehler",
    "GroundTruthBericht",
    "pruefe_ground_truth",
    "schreibe_bericht",
]


class Gegencheckfehler(RuntimeError):
    """Der Gegencheck ist nicht durchfuehrbar."""


#: Spaltenname der stabilen Zeilenkennung (spec/01, Abschnitt 3).
_ROW_ID: Final[str] = "row_id"

#: Spalten des zellbasierten Logs, die der Gegencheck braucht (spec/03, Abschnitt 4.1).
_LOG_SPALTEN: Final[tuple[str, ...]] = (
    "entitaet",
    "row_id",
    "spalte",
    "wert_clean",
    "wert_dirty",
)

#: Spalten des satzbasierten Logs, die der Gegencheck braucht (spec/03, Abschnitt 4.2).
_RECORD_SPALTEN: Final[tuple[str, ...]] = ("entitaet", "betroffene_row_ids")

#: Hoechstzahl der Beispiele je Abweichungsart im Bericht.
_BEISPIELE: Final[int] = 20


@dataclass(frozen=True, slots=True)
class GroundTruthBericht:
    """Ergebnis des Gegenchecks.

    Attributes:
        sauber: ``True``, wenn keine Abweichung gefunden wurde.
        zellen_im_diff: Zahl der zellweisen Abweichungen zwischen den
            gemeinsamen Zeilen von ``df_clean`` und ``df_dirty``.
        zellen_im_log: Zahl der Zeilen im ``error_log``.
        zeilen_nur_dirty: Zahl der Zeilen, die nur in ``df_dirty`` stehen.
        zeilen_nur_clean: Zahl der Zeilen, die nur in ``df_clean`` stehen.
        saetze_im_log: Zahl der Zeilen im ``error_log_records``.
        diff_ohne_log: Abweichungen ohne Protokolleintrag.
        log_ohne_diff: Protokolleintraege ohne Abweichung.
        wertabweichungen: Eintraege, deren protokollierte Werte nicht zum Diff
            passen.
        doppelte_logzeilen: Zellen, die mehrfach protokolliert sind.
        row_id_als_ziel: Protokolleintraege, die ``row_id`` als Ziel nennen.
        wirkungslose_eintraege: Protokolleintraege mit gleichem Ausgangs- und
            verfaelschtem Wert.
        neue_zeilen_ohne_log: Zeilen nur in ``df_dirty`` ohne satzbasierten
            Eintrag.
        entfallene_zeilen_ohne_log: Zeilen nur in ``df_clean`` ohne
            satzbasierten Eintrag.
        doppelte_row_ids: Entitaeten mit mehrfach vergebener ``row_id``.
    """

    sauber: bool
    zellen_im_diff: int
    zellen_im_log: int
    zeilen_nur_dirty: int
    zeilen_nur_clean: int
    saetze_im_log: int
    diff_ohne_log: tuple[tuple[str, int, str], ...] = ()
    log_ohne_diff: tuple[tuple[str, int, str], ...] = ()
    wertabweichungen: tuple[tuple[str, int, str], ...] = ()
    doppelte_logzeilen: tuple[tuple[str, int, str], ...] = ()
    row_id_als_ziel: tuple[tuple[str, int, str], ...] = ()
    wirkungslose_eintraege: tuple[tuple[str, int, str], ...] = ()
    neue_zeilen_ohne_log: tuple[tuple[str, int], ...] = ()
    entfallene_zeilen_ohne_log: tuple[tuple[str, int], ...] = ()
    doppelte_row_ids: tuple[str, ...] = field(default=())

    def als_dict(self) -> dict[str, Any]:
        """Bildet den Bericht auf JSON-faehige Werte ab.

        Returns:
            Eine Abbildung mit den Kennzahlen und hoechstens
            :data:`_BEISPIELE` Beispielen je Abweichungsart.
        """
        return {
            "sauber": self.sauber,
            "zellen_im_diff": self.zellen_im_diff,
            "zellen_im_log": self.zellen_im_log,
            "zeilen_nur_dirty": self.zeilen_nur_dirty,
            "zeilen_nur_clean": self.zeilen_nur_clean,
            "saetze_im_log": self.saetze_im_log,
            "abweichungen": {
                "diff_ohne_log": len(self.diff_ohne_log),
                "log_ohne_diff": len(self.log_ohne_diff),
                "wertabweichungen": len(self.wertabweichungen),
                "doppelte_logzeilen": len(self.doppelte_logzeilen),
                "row_id_als_ziel": len(self.row_id_als_ziel),
                "wirkungslose_eintraege": len(self.wirkungslose_eintraege),
                "neue_zeilen_ohne_log": len(self.neue_zeilen_ohne_log),
                "entfallene_zeilen_ohne_log": len(self.entfallene_zeilen_ohne_log),
                "doppelte_row_ids": len(self.doppelte_row_ids),
            },
            "beispiele": {
                "diff_ohne_log": _beispiele(self.diff_ohne_log),
                "log_ohne_diff": _beispiele(self.log_ohne_diff),
                "wertabweichungen": _beispiele(self.wertabweichungen),
                "doppelte_logzeilen": _beispiele(self.doppelte_logzeilen),
                "row_id_als_ziel": _beispiele(self.row_id_als_ziel),
                "wirkungslose_eintraege": _beispiele(self.wirkungslose_eintraege),
                "neue_zeilen_ohne_log": _beispiele(self.neue_zeilen_ohne_log),
                "entfallene_zeilen_ohne_log": _beispiele(self.entfallene_zeilen_ohne_log),
                "doppelte_row_ids": list(self.doppelte_row_ids[:_BEISPIELE]),
            },
        }


def _beispiele(eintraege: Sequence[tuple[Any, ...]]) -> list[list[Any]]:
    """Kuerzt eine Abweichungsliste auf die ersten Beispiele."""
    return [list(eintrag) for eintrag in eintraege[:_BEISPIELE]]


def _text(wert: Any) -> str:  # noqa: ANN401 - liest beliebige Zellinhalte
    """Bildet einen Zellinhalt auf seine Textform ab.

    Ein fehlender Wert und der Leerstring werden zusammengefuehrt. Auf der
    Rohschicht bedeuten beide dasselbe, naemlich "kein Wert"
    (``spec/01_datenmodell.md``, Abschnitt 6); haelte der Gegencheck sie
    auseinander, meldete er eine Abweichung, die keine ist.
    """
    if wert is None or (not isinstance(wert, str) and pd.isna(wert)):
        return ""
    return str(wert)


def _pruefe_spalten(rahmen: pd.DataFrame, spalten: Iterable[str], name: str) -> None:
    """Bricht ab, wenn einem Log die noetigen Spalten fehlen."""
    fehlend = [spalte for spalte in spalten if spalte not in rahmen.columns]
    if fehlend:
        raise Gegencheckfehler(f"{name} fehlen die Spalten {fehlend}")


def _zeilenindex(rahmen: pd.DataFrame, entitaet: str) -> dict[int, int]:
    """Bildet ``row_id`` auf die Zeilenposition ab.

    Raises:
        Gegencheckfehler: Wenn ``row_id`` fehlt oder mehrfach vergeben ist.
    """
    if _ROW_ID not in rahmen.columns:
        raise Gegencheckfehler(f"Entitaet {entitaet}: Spalte row_id fehlt")
    kennungen = [int(_text(wert)) for wert in rahmen[_ROW_ID]]
    index = {kennung: position for position, kennung in enumerate(kennungen)}
    if len(index) != len(kennungen):
        raise Gegencheckfehler(
            f"Entitaet {entitaet}: row_id ist mehrfach vergeben — der Join des "
            "Gegenchecks waere nicht eindeutig"
        )
    return index


def _diff_der_entitaet(
    clean: pd.DataFrame, dirty: pd.DataFrame, entitaet: str
) -> dict[tuple[str, int, str], tuple[str, str]]:
    """Berechnet das zellweise Diff einer Entitaet ueber die gemeinsamen Zeilen."""
    index_clean = _zeilenindex(clean, entitaet)
    index_dirty = _zeilenindex(dirty, entitaet)
    gemeinsam = sorted(set(index_clean) & set(index_dirty))
    spalten = [str(name) for name in clean.columns if name in set(dirty.columns)]

    abweichungen: dict[tuple[str, int, str], tuple[str, str]] = {}
    for spalte in spalten:
        werte_clean = [_text(wert) for wert in clean[spalte]]
        werte_dirty = [_text(wert) for wert in dirty[spalte]]
        for kennung in gemeinsam:
            links = werte_clean[index_clean[kennung]]
            rechts = werte_dirty[index_dirty[kennung]]
            if links != rechts:
                abweichungen[(entitaet, kennung, spalte)] = (links, rechts)
    return abweichungen


def _log_als_abbildung(
    error_log: pd.DataFrame,
) -> tuple[dict[tuple[str, int, str], tuple[str, str]], list[tuple[str, int, str]]]:
    """Liest das zellbasierte Log als Abbildung und sammelt doppelte Eintraege."""
    abbildung: dict[tuple[str, int, str], tuple[str, str]] = {}
    doppelt: list[tuple[str, int, str]] = []
    for entitaet, row_id, spalte, wert_clean, wert_dirty in zip(
        error_log["entitaet"],
        error_log["row_id"],
        error_log["spalte"],
        error_log["wert_clean"],
        error_log["wert_dirty"],
        strict=True,
    ):
        schluessel = (str(entitaet), int(row_id), str(spalte))
        if schluessel in abbildung:
            doppelt.append(schluessel)
            continue
        abbildung[schluessel] = (_text(wert_clean), _text(wert_dirty))
    return abbildung, doppelt


def _protokollierte_zeilen(error_log_records: pd.DataFrame) -> set[tuple[str, int]]:
    """Liest alle im satzbasierten Log genannten Zeilen."""
    genannt: set[tuple[str, int]] = set()
    for entitaet, kennungen in zip(
        error_log_records["entitaet"], error_log_records["betroffene_row_ids"], strict=True
    ):
        for kennung in _als_liste(kennungen):
            genannt.add((str(entitaet), int(kennung)))
    return genannt


def _als_liste(wert: Any) -> list[Any]:  # noqa: ANN401 - Parquet liefert Liste oder Feld
    """Bringt eine Listenspalte aus Parquet in eine gewoehnliche Liste."""
    if wert is None:
        return []
    if isinstance(wert, list):
        return wert
    return list(wert)


def pruefe_ground_truth(
    daten_clean: Mapping[str, pd.DataFrame],
    daten_dirty: Mapping[str, pd.DataFrame],
    error_log: pd.DataFrame,
    error_log_records: pd.DataFrame,
) -> GroundTruthBericht:
    """Gleicht ein zellweises Diff gegen die beiden Ground-Truth-Logs ab.

    Args:
        daten_clean: Die sauberen Datenrahmen der Rohschicht.
        daten_dirty: Die verfaelschten Datenrahmen derselben Entitaeten.
        error_log: Zellbasierter Ground Truth.
        error_log_records: Satzbasierter Ground Truth.

    Returns:
        Den :class:`GroundTruthBericht`.

    Raises:
        Gegencheckfehler: Wenn die Entitaetsmengen nicht uebereinstimmen, eine
            ``row_id`` fehlt oder mehrfach vergeben ist oder einem Log Spalten
            fehlen. Das sind Fehler des Aufbaus, keine Befunde ueber die Daten.
    """
    _pruefe_spalten(error_log, _LOG_SPALTEN, "error_log")
    _pruefe_spalten(error_log_records, _RECORD_SPALTEN, "error_log_records")

    fehlend = sorted(set(daten_clean) ^ set(daten_dirty))
    if fehlend:
        raise Gegencheckfehler(
            f"Die Entitaetsmengen stimmen nicht ueberein; verschieden sind: {fehlend}"
        )

    diff: dict[tuple[str, int, str], tuple[str, str]] = {}
    nur_dirty: list[tuple[str, int]] = []
    nur_clean: list[tuple[str, int]] = []
    for entitaet in sorted(daten_clean):
        clean = daten_clean[entitaet]
        dirty = daten_dirty[entitaet]
        diff.update(_diff_der_entitaet(clean, dirty, entitaet))
        kennungen_clean = {int(_text(wert)) for wert in clean[_ROW_ID]}
        kennungen_dirty = {int(_text(wert)) for wert in dirty[_ROW_ID]}
        nur_dirty.extend(
            (entitaet, kennung) for kennung in sorted(kennungen_dirty - kennungen_clean)
        )
        nur_clean.extend(
            (entitaet, kennung) for kennung in sorted(kennungen_clean - kennungen_dirty)
        )

    protokolliert, doppelt = _log_als_abbildung(error_log)
    genannt = _protokollierte_zeilen(error_log_records)

    diff_ohne_log = tuple(sorted(set(diff) - set(protokolliert)))
    log_ohne_diff = tuple(sorted(set(protokolliert) - set(diff)))
    wertabweichungen = tuple(
        sorted(
            schluessel
            for schluessel, werte in protokolliert.items()
            if schluessel in diff and diff[schluessel] != werte
        )
    )
    row_id_als_ziel = tuple(
        sorted(schluessel for schluessel in protokolliert if schluessel[2] == _ROW_ID)
    )
    wirkungslos = tuple(
        sorted(
            schluessel
            for schluessel, (links, rechts) in protokolliert.items()
            if links == rechts
        )
    )
    neue_ohne_log = tuple(eintrag for eintrag in nur_dirty if eintrag not in genannt)
    entfallene_ohne_log = tuple(eintrag for eintrag in nur_clean if eintrag not in genannt)

    abweichungen = (
        diff_ohne_log,
        log_ohne_diff,
        wertabweichungen,
        tuple(doppelt),
        row_id_als_ziel,
        wirkungslos,
        neue_ohne_log,
        entfallene_ohne_log,
    )
    return GroundTruthBericht(
        sauber=not any(abweichungen),
        zellen_im_diff=len(diff),
        zellen_im_log=len(error_log),
        zeilen_nur_dirty=len(nur_dirty),
        zeilen_nur_clean=len(nur_clean),
        saetze_im_log=len(error_log_records),
        diff_ohne_log=diff_ohne_log,
        log_ohne_diff=log_ohne_diff,
        wertabweichungen=wertabweichungen,
        doppelte_logzeilen=tuple(doppelt),
        row_id_als_ziel=row_id_als_ziel,
        wirkungslose_eintraege=wirkungslos,
        neue_zeilen_ohne_log=neue_ohne_log,
        entfallene_zeilen_ohne_log=entfallene_ohne_log,
    )


def schreibe_bericht(
    bericht: GroundTruthBericht,
    pfad: Path,
    *,
    run_id: str,
    zusatz: Mapping[str, Any] | None = None,
) -> Path:
    """Traegt den Bericht eines Laufs in die Sammeldatei ein.

    Die Datei **sammelt** die Ergebnisse aller Laeufe unter ihrer ``run_id``,
    statt sie zu ueberschreiben. Sie gehoert in den Anhang der Arbeit, und dort
    ist der Nachweis ueber alle Fehlerklassen mehr wert als der ueber den zuletzt
    gelaufenen.

    Bewusst **ohne Zeitstempel**: Dieselben Laeufe sollen byteweise denselben
    Bericht erzeugen (Architekturregel A2).

    Args:
        bericht: Ergebnis von :func:`pruefe_ground_truth`.
        pfad: Zieldatei, ueblicherweise ``results/ground_truth_check.json``.
        run_id: Kennung des Laufs; sie ist der Schluessel des Eintrags.
        zusatz: Weitere Angaben zum Lauf, etwa Fehlerklasse und Fehlerrate.

    Returns:
        Den geschriebenen Pfad.
    """
    eintrag: dict[str, Any] = dict(zusatz or {})
    eintrag.update(bericht.als_dict())

    laeufe: dict[str, Any] = {}
    if pfad.is_file():
        bestand = json.loads(pfad.read_text(encoding="utf-8"))
        if isinstance(bestand, dict) and isinstance(bestand.get("laeufe"), dict):
            laeufe = dict(bestand["laeufe"])
    laeufe[run_id] = eintrag

    inhalt = {
        "alle_sauber": all(einzeln["sauber"] for einzeln in laeufe.values()),
        "laeufe_gesamt": len(laeufe),
        "laeufe": dict(sorted(laeufe.items())),
    }
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(
        json.dumps(inhalt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return pfad
