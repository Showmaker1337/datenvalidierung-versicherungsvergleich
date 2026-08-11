"""Ground Truth: das zell- und das satzbasierte Log (``spec/03``, Abschnitt 4).

Zwei Ebenen, weil eine nicht reicht
-----------------------------------

Das **zellbasierte** Log fuehrt eine Zeile je verfaelschter Zelle. Es deckt alle
Klassen ab, die bestehende Werte veraendern.

Das **satzbasierte** Log fuehrt eine Zeile je satzbezogenem Fehler. Es ist noetig
fuer die Duplikatklassen und fuer die Gueltigkeitsverletzung auf Tarifebene. Eine
hinzugefuegte Duplikatzeile hat keinen sauberen Vorgaengerwert, und ``df_dirty``
hat dann mehr Zeilen als ``df_clean`` — ein zellweises Diff ist dort undefiniert.
Ohne diese zweite Ebene braeche die Auswertung genau bei der Fehlerklasse, die
laut Branchenempirie die haeufigste ist.

Zwei Praezisierungen gegenueber ``spec/03``, Abschnitt 4.1
----------------------------------------------------------

* ``seed_base`` und ``seed_inject`` werden als **Zeichenkette** gefuehrt.
  :func:`src.common.seeding.seed_als_int` liefert einen 128-Bit-Wert; er passt in
  keine ``int64``-Parquetspalte. Ihn abzuschneiden waere genau die Art stiller
  Ungenauigkeit, die Architekturregel A2 ausschliesst.
* Die Spalte ``mitgezogen`` trennt Traegerzellen von Zellen, die nur der
  Satzstimmigkeit wegen nachgefuehrt wurden. Die Begruendung steht im Docstring
  von :mod:`src.injector.modell`.

Beide Praezisierungen sind in ``spec/03`` nachgetragen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd

from src.injector.modell import ERROR_LOG_RECORDS_SPALTEN, ERROR_LOG_SPALTEN

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    from src.injector.modell import Fehlerklasse

__all__ = ["Laufkennung", "Protokoll"]


@dataclass(frozen=True, slots=True)
class Laufkennung:
    """Die Laufangaben, die jede Protokollzeile mitfuehrt.

    Attributes:
        run_id: Kennung des Laufs.
        master_seed: Master-Seed aus der Konfiguration.
        seed_base: Seed des Basisdatensatzes als Dezimalzeichenkette.
        seed_inject: Seed der Injektion als Dezimalzeichenkette.
    """

    run_id: str
    master_seed: int
    seed_base: str
    seed_inject: str


@dataclass(frozen=True, slots=True)
class _Zelleintrag:
    """Eine Zeile des zellbasierten Logs."""

    entitaet: str
    row_id: int
    spalte: str
    fehlerklasse: str
    injektor_variante_id: str
    wert_clean: str
    wert_dirty: str
    mitgezogen: bool


@dataclass(frozen=True, slots=True)
class _Satzeintrag:
    """Eine Zeile des satzbasierten Logs."""

    entitaet: str
    fehlerklasse: str
    injektor_variante_id: str
    betroffene_row_ids: tuple[int, ...]
    referenz_row_id: int | None


class Protokoll:
    """Sammelt den Ground Truth eines Injektionslaufs.

    Die Eintraege werden in der Reihenfolge ihrer Entstehung gesammelt und beim
    Erzeugen der Datenrahmen fest sortiert. Die Sortierung ist Teil der
    Reproduzierbarkeit: Sie geht in den SHA-256-Hashwert des Logs ein.
    """

    __slots__ = ("_kennung", "_saetze", "_zellen")

    def __init__(self, kennung: Laufkennung) -> None:
        """Legt ein leeres Protokoll an.

        Args:
            kennung: Laufangaben, die jede Zeile mitfuehrt.
        """
        self._kennung = kennung
        self._zellen: list[_Zelleintrag] = []
        self._saetze: list[_Satzeintrag] = []

    def vermerke_zelle(  # noqa: PLR0913 - die Log-Zeile hat nun einmal diese Felder
        self,
        *,
        fehlerklasse: Fehlerklasse,
        injektor_variante_id: str,
        entitaet: str,
        row_id: int,
        spalte: str,
        wert_clean: str,
        wert_dirty: str,
        mitgezogen: bool,
    ) -> None:
        """Vermerkt eine verfaelschte Zelle.

        Args:
            fehlerklasse: Fehlerklasse der Variante.
            injektor_variante_id: Kennung der Variante.
            entitaet: Name der Entitaet.
            row_id: Zeilenkennung.
            spalte: Spaltenname.
            wert_clean: Serialisierter Ausgangswert.
            wert_dirty: Serialisierter verfaelschter Wert.
            mitgezogen: ``True`` bei einer nur nachgefuehrten Zelle.

        Raises:
            ValueError: Wenn ``row_id`` das Ziel waere (Architekturregel A3) oder
                die Effektivitaetspruefung verletzt ist (Protokollregel 3).
        """
        if spalte == "row_id":
            raise ValueError("row_id ist niemals Ziel einer Injektion (Architekturregel A3)")
        if wert_clean == wert_dirty:
            raise ValueError(
                f"Effektivitaetspruefung verletzt: {entitaet}.{spalte} in Zeile {row_id} "
                f"haette den unveraenderten Wert {wert_clean!r} bekommen"
            )
        self._zellen.append(
            _Zelleintrag(
                entitaet=entitaet,
                row_id=row_id,
                spalte=spalte,
                fehlerklasse=fehlerklasse.value,
                injektor_variante_id=injektor_variante_id,
                wert_clean=wert_clean,
                wert_dirty=wert_dirty,
                mitgezogen=mitgezogen,
            )
        )

    def vermerke_satz(
        self,
        *,
        fehlerklasse: Fehlerklasse,
        injektor_variante_id: str,
        entitaet: str,
        betroffene_row_ids: Sequence[int],
        referenz_row_id: int | None,
    ) -> None:
        """Vermerkt einen satzbezogenen Fehler.

        Args:
            fehlerklasse: Fehlerklasse der Variante.
            injektor_variante_id: Kennung der Variante.
            entitaet: Name der Entitaet.
            betroffene_row_ids: Alle beteiligten Zeilen.
            referenz_row_id: Ursprungszeile einer Duplizierung, sonst ``None``.
        """
        self._saetze.append(
            _Satzeintrag(
                entitaet=entitaet,
                fehlerklasse=fehlerklasse.value,
                injektor_variante_id=injektor_variante_id,
                betroffene_row_ids=tuple(betroffene_row_ids),
                referenz_row_id=referenz_row_id,
            )
        )

    @property
    def anzahl_zellen(self) -> int:
        """Zahl der protokollierten Zellen, einschliesslich der nachgefuehrten."""
        return len(self._zellen)

    @property
    def anzahl_traeger(self) -> int:
        """Zahl der protokollierten Traegerzellen."""
        return sum(1 for eintrag in self._zellen if not eintrag.mitgezogen)

    @property
    def anzahl_saetze(self) -> int:
        """Zahl der protokollierten satzbezogenen Fehler."""
        return len(self._saetze)

    def error_log(self) -> pd.DataFrame:
        """Baut das zellbasierte Log.

        Returns:
            Einen Datenrahmen mit den Spalten
            :data:`src.injector.modell.ERROR_LOG_SPALTEN` in fester Sortierung.
        """
        geordnet = sorted(
            self._zellen,
            key=lambda eintrag: (
                eintrag.fehlerklasse,
                eintrag.injektor_variante_id,
                eintrag.entitaet,
                eintrag.row_id,
                eintrag.spalte,
            ),
        )
        spalten: dict[str, object] = {
            "run_id": pd.array([self._kennung.run_id] * len(geordnet), dtype="string"),
            "master_seed": pd.array(
                [self._kennung.master_seed] * len(geordnet), dtype="int64"
            ),
            "seed_base": pd.array([self._kennung.seed_base] * len(geordnet), dtype="string"),
            "seed_inject": pd.array(
                [self._kennung.seed_inject] * len(geordnet), dtype="string"
            ),
            "entitaet": pd.array([eintrag.entitaet for eintrag in geordnet], dtype="string"),
            "row_id": pd.array([eintrag.row_id for eintrag in geordnet], dtype="int64"),
            "spalte": pd.array([eintrag.spalte for eintrag in geordnet], dtype="string"),
            "fehlerklasse": pd.array(
                [eintrag.fehlerklasse for eintrag in geordnet], dtype="string"
            ),
            "injektor_variante_id": pd.array(
                [eintrag.injektor_variante_id for eintrag in geordnet], dtype="string"
            ),
            "wert_clean": pd.array([eintrag.wert_clean for eintrag in geordnet], dtype="string"),
            "wert_dirty": pd.array([eintrag.wert_dirty for eintrag in geordnet], dtype="string"),
            "mitgezogen": pd.array([eintrag.mitgezogen for eintrag in geordnet], dtype="boolean"),
        }
        return pd.DataFrame(spalten, columns=list(ERROR_LOG_SPALTEN))

    def error_log_records(self) -> pd.DataFrame:
        """Baut das satzbasierte Log.

        Returns:
            Einen Datenrahmen mit den Spalten
            :data:`src.injector.modell.ERROR_LOG_RECORDS_SPALTEN` in fester
            Sortierung. ``betroffene_row_ids`` ist eine Liste je Zeile.
        """
        geordnet = sorted(
            self._saetze,
            key=lambda eintrag: (
                eintrag.fehlerklasse,
                eintrag.injektor_variante_id,
                eintrag.entitaet,
                eintrag.betroffene_row_ids,
            ),
        )
        spalten: dict[str, object] = {
            "run_id": pd.array([self._kennung.run_id] * len(geordnet), dtype="string"),
            "master_seed": pd.array(
                [self._kennung.master_seed] * len(geordnet), dtype="int64"
            ),
            "seed_base": pd.array([self._kennung.seed_base] * len(geordnet), dtype="string"),
            "seed_inject": pd.array(
                [self._kennung.seed_inject] * len(geordnet), dtype="string"
            ),
            "entitaet": pd.array([eintrag.entitaet for eintrag in geordnet], dtype="string"),
            "fehlerklasse": pd.array(
                [eintrag.fehlerklasse for eintrag in geordnet], dtype="string"
            ),
            "injektor_variante_id": pd.array(
                [eintrag.injektor_variante_id for eintrag in geordnet], dtype="string"
            ),
            "betroffene_row_ids": pd.Series(
                [list(eintrag.betroffene_row_ids) for eintrag in geordnet], dtype=object
            ),
            "referenz_row_id": pd.array(
                [eintrag.referenz_row_id for eintrag in geordnet], dtype="Int64"
            ),
        }
        return pd.DataFrame(spalten, columns=list(ERROR_LOG_RECORDS_SPALTEN))
