"""Datenmodell einer Regel, Pruefkontext und Ergebnistypen.

Dieses Modul definiert, **was** eine Regel ist. Die Regeln selbst stehen in
``g1_attribut.py`` bis ``g5_quellen.py``, ihre Ausfuehrung in ``engine.py``.

Drei Entwurfsentscheidungen tragen dieses Modul.

Der Kontext haelt beide Datenschichten
--------------------------------------

``spec/01_datenmodell.md``, Abschnitt 6 fuehrt ``df_raw`` (alle Spalten als
Zeichenkette) und ``df_typed`` (geparst) ein. Format-, Typ- und Sentinel-Regeln
laufen zwingend auf der Rohschicht — auf der typisierten Schicht sind sie per
Konstruktion nicht verletzbar. Jede Regel deklariert ihre Schicht deshalb in den
Metadaten (:attr:`Regel.schicht`), und der :class:`Kontext` haelt beide Schichten
zugleich bereit. Regeln ueber mehrere Tabellen (R-029, R-049 bis R-051, R-055)
brauchen ohnehin den vollen Kontext.

Die ``verstoss_id`` verhindert eine Metrikfalle
-----------------------------------------------

Verletzt eine Regel eine Beziehung zwischen mehreren Feldern — etwa R-031 ueber
Brutto, Netto und Steuer —, meldet sie **alle** beteiligten Spalten. Der Injektor
verfaelscht aber typischerweise nur eine dieser Zellen. Bei streng zellbasierter
Metrik ergaebe das einen Treffer und zwei Fehlalarme bei perfekter Erkennung; die
Precision waere strukturell auf etwa ein Drittel gedeckelt — als Artefakt der
Berichtskonvention, nicht des Detektors.

Jede Verstosszeile traegt deshalb zusaetzlich eine :attr:`Zellverstoss.verstoss_id`:
eine Kennung je erkanntem Constraint-Verstoss, gemeinsam fuer alle beteiligten
Zellen. Der Evaluator wertet spaeter beide Sichten aus — streng zellbasiert und
constraint-basiert.

Zwei Rueckgabekanaele statt einem
---------------------------------

Satzbezogene Regeln (R-043, R-045, R-046, R-048, R-055) melden keinen einzelnen
Zellwert, sondern eine Menge beteiligter Zeilen — analog zum satzbasierten Ground
Truth aus ``spec/03_fehlerklassen.md``, Abschnitt 4.2. Eine Pruefung gibt deshalb
einen :class:`Befund` mit zwei Kanaelen zurueck und nicht nur einen Datenrahmen
der Zellverstoesse. Die Umwandlung in die Berichtsform uebernimmt
:meth:`Befund.als_rahmen`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

import pandas as pd

from src.common.pfade import Schicht
from src.common.referenz import lade_alle
from src.common.serialisierung import (
    ENTITAETEN,
    SPALTEN_JE_ENTITAET,
    parse,
    serialisiere,
    typisierter_rahmen,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    import datetime as dt
    from collections.abc import Callable, Iterable, Mapping, Sequence

    from src.common.config import Config, Schwellen

__all__ = [
    "ERKENNBARKEITEN",
    "FEHLERKLASSEN",
    "GRANULARITAETEN",
    "SATZ_SPALTEN",
    "SCHWEREGRADE",
    "VERSTOSS_SPALTEN",
    "Befund",
    "Befundsammler",
    "Kontext",
    "Regel",
    "RegelFehler",
    "Satzverstoss",
    "Schicht",
    "Zellverstoss",
    "baue_kontext",
    "gruppen",
    "leerer_befund",
    "row_ids",
    "text",
    "werte",
    "zuordnung",
]

#: Spalten des zellbasierten Verstossprotokolls (``detections.parquet``).
VERSTOSS_SPALTEN: Final[tuple[str, ...]] = (
    "entitaet",
    "row_id",
    "spalte",
    "regel_id",
    "verstoss_id",
    "meldung",
)

#: Spalten des satzbezogenen Verstossprotokolls.
SATZ_SPALTEN: Final[tuple[str, ...]] = (
    "entitaet",
    "regel_id",
    "verstoss_id",
    "betroffene_row_ids",
    "meldung",
)

#: Zulaessige Werte der Achse A (Pruefgranularitaet).
GRANULARITAETEN: Final[tuple[str, ...]] = ("G1", "G2", "G3", "G4", "G5")

#: Zulaessige Werte der Achse B (Fehlerklasse).
FEHLERKLASSEN: Final[tuple[str, ...]] = ("B1", "B2", "B3", "B4", "B5", "B6", "B7")

#: Zulaessige Werte der Achse C (Erkennbarkeitsgrad).
ERKENNBARKEITEN: Final[tuple[str, ...]] = ("C1", "C2", "C3", "C4")

#: Zulaessige Schweregrade.
SCHWEREGRADE: Final[tuple[str, ...]] = ("HART", "WARNUNG")


class RegelFehler(RuntimeError):
    """Eine Regel oder ihr Kontext ist nicht verwendbar.

    Bewusst eine Ausnahme und kein stiller Ersatzwert: Eine fehlende Entitaet
    oder eine unbekannte Spalte ist ein Programmierfehler, kein Datenbefund.
    """


# ---------------------------------------------------------------------------
# Ergebnistypen
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Zellverstoss:
    """Eine verletzte Zelle.

    Attributes:
        entitaet: Tabellenname.
        row_id: Betroffene Zeile.
        spalte: Betroffenes Feld.
        verstoss_id: Kennung des Constraint-Verstosses; mehrere Zellen desselben
            Verstosses teilen sie sich.
        meldung: Menschenlesbare Begruendung mit dem konkreten Wert.
    """

    entitaet: str
    row_id: int
    spalte: str
    verstoss_id: str
    meldung: str


@dataclass(frozen=True, slots=True)
class Satzverstoss:
    """Ein satzbezogener Verstoss ueber mehrere Zeilen.

    Attributes:
        entitaet: Tabellenname.
        verstoss_id: Kennung des Constraint-Verstosses.
        betroffene_row_ids: Alle beteiligten Zeilen.
        meldung: Menschenlesbare Begruendung.
    """

    entitaet: str
    verstoss_id: str
    betroffene_row_ids: tuple[int, ...]
    meldung: str


@dataclass(frozen=True, slots=True)
class Befund:
    """Ergebnis einer Regelpruefung.

    Attributes:
        zellen: Zellbezogene Verstoesse, eine Zeile je verletzter Zelle.
        saetze: Satzbezogene Verstoesse; nur die Regeln R-043, R-045, R-046,
            R-047, R-048 und R-055 fuellen diesen Kanal.
    """

    zellen: tuple[Zellverstoss, ...] = ()
    saetze: tuple[Satzverstoss, ...] = ()

    def __bool__(self) -> bool:
        """Gibt zurueck, ob ueberhaupt ein Verstoss vorliegt."""
        return bool(self.zellen or self.saetze)

    def als_rahmen(self, regel_id: str) -> pd.DataFrame:
        """Baut den Datenrahmen der Zellverstoesse in der Berichtsform.

        Args:
            regel_id: Kennung der meldenden Regel.

        Returns:
            Einen Datenrahmen mit den Spalten :data:`VERSTOSS_SPALTEN`.
        """
        return pd.DataFrame(
            [
                (
                    verstoss.entitaet,
                    verstoss.row_id,
                    verstoss.spalte,
                    regel_id,
                    verstoss.verstoss_id,
                    verstoss.meldung,
                )
                for verstoss in self.zellen
            ],
            columns=list(VERSTOSS_SPALTEN),
        )

    def als_satzrahmen(self, regel_id: str) -> pd.DataFrame:
        """Baut den Datenrahmen der satzbezogenen Verstoesse.

        Args:
            regel_id: Kennung der meldenden Regel.

        Returns:
            Einen Datenrahmen mit den Spalten :data:`SATZ_SPALTEN`.
        """
        return pd.DataFrame(
            [
                (
                    verstoss.entitaet,
                    regel_id,
                    verstoss.verstoss_id,
                    list(verstoss.betroffene_row_ids),
                    verstoss.meldung,
                )
                for verstoss in self.saetze
            ],
            columns=list(SATZ_SPALTEN),
        )


def leerer_befund() -> Befund:
    """Gibt einen Befund ohne Verstoesse zurueck."""
    return Befund()


class Befundsammler:
    """Sammelt die Verstoesse einer Regel und vergibt die ``verstoss_id``.

    Der Sammler ist die einzige Stelle, an der eine ``verstoss_id`` entsteht.
    Damit ist sichergestellt, dass alle Zellen **eines** Constraint-Verstosses
    dieselbe Kennung tragen — die Voraussetzung der constraint-basierten Sicht in
    der Auswertung (siehe Modul-Docstring).

    Die Kennung ist ``<regel_id>#<laufende Nummer>``. Sie haengt nur an der
    Reihenfolge der Meldungen innerhalb der Regel und ist damit bei gleichem
    Eingabedatensatz reproduzierbar (Architekturregel A2).
    """

    __slots__ = ("_laufend", "_regel_id", "_saetze", "_zellen")

    def __init__(self, regel_id: str) -> None:
        """Legt einen Sammler fuer eine Regel an.

        Args:
            regel_id: Kennung der Regel, zum Beispiel ``"R-031"``.
        """
        self._regel_id = regel_id
        self._laufend = 0
        self._zellen: list[Zellverstoss] = []
        self._saetze: list[Satzverstoss] = []

    def naechste_id(self) -> str:
        """Vergibt die naechste ``verstoss_id`` dieser Regel."""
        self._laufend += 1
        return f"{self._regel_id}#{self._laufend:06d}"

    def melde(
        self,
        entitaet: str,
        row_id: int,
        spalten: Sequence[str],
        meldung: str,
    ) -> str:
        """Meldet einen Verstoss ueber eine oder mehrere Spalten **einer** Zeile.

        Args:
            entitaet: Tabellenname.
            row_id: Betroffene Zeile.
            spalten: Alle an der Verletzung beteiligten Felder.
            meldung: Begruendung mit dem konkreten Wert.

        Returns:
            Die vergebene ``verstoss_id``.
        """
        verstoss_id = self.naechste_id()
        self._zellen.extend(
            Zellverstoss(entitaet, row_id, spalte, verstoss_id, meldung) for spalte in spalten
        )
        return verstoss_id

    def melde_zellen(
        self,
        entitaet: str,
        zellen: Sequence[tuple[int, str]],
        meldung: str,
    ) -> str:
        """Meldet einen Verstoss ueber Zellen **mehrerer** Zeilen.

        Gebraucht von den Relationsregeln: Ein doppelter Rang betrifft zwei
        Zeilen, ist aber **ein** Constraint-Verstoss.

        Args:
            entitaet: Tabellenname.
            zellen: Paare aus Zeile und Feldname.
            meldung: Begruendung.

        Returns:
            Die vergebene ``verstoss_id``.
        """
        verstoss_id = self.naechste_id()
        self._zellen.extend(
            Zellverstoss(entitaet, row_id, spalte, verstoss_id, meldung)
            for row_id, spalte in zellen
        )
        return verstoss_id

    def melde_satz(
        self,
        entitaet: str,
        betroffene_row_ids: Iterable[int],
        meldung: str,
        *,
        verstoss_id: str | None = None,
    ) -> str:
        """Meldet einen satzbezogenen Verstoss.

        Args:
            entitaet: Tabellenname.
            betroffene_row_ids: Alle beteiligten Zeilen.
            meldung: Begruendung.
            verstoss_id: Bereits vergebene Kennung, wenn der Satzverstoss zu
                denselben Zellen gehoert wie eine vorherige Meldung. Ohne Angabe
                wird eine neue Kennung vergeben.

        Returns:
            Die verwendete ``verstoss_id``.
        """
        kennung = verstoss_id if verstoss_id is not None else self.naechste_id()
        self._saetze.append(
            Satzverstoss(entitaet, kennung, tuple(betroffene_row_ids), meldung)
        )
        return kennung

    def befund(self) -> Befund:
        """Gibt den gesammelten Befund zurueck."""
        return Befund(zellen=tuple(self._zellen), saetze=tuple(self._saetze))


# ---------------------------------------------------------------------------
# Pruefkontext
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Kontext:
    """Alles, was eine Regel zum Pruefen braucht.

    Attributes:
        config: Geladene Konfiguration; liefert Stichtag und Schwellenwerte.
        typed: Typisierte Schicht je Entitaet.
        raw: Rohschicht je Entitaet, alle Spalten als Zeichenkette.
        referenz: Referenztabellen aus ``data/reference``.
    """

    config: Config
    typed: Mapping[str, pd.DataFrame]
    raw: Mapping[str, pd.DataFrame]
    referenz: Mapping[str, pd.DataFrame]

    @property
    def stichtag(self) -> dt.date:
        """Referenzdatum aller Altersberechnungen (Architekturregel A2)."""
        return self.config.stichtag

    @property
    def schwellen(self) -> Schwellen:
        """Schwellenwerte der heuristischen Regeln (C2)."""
        return self.config.schwellen

    def rahmen(self, schicht: Schicht, entitaet: str) -> pd.DataFrame:
        """Gibt den Datenrahmen einer Entitaet in der gewuenschten Schicht zurueck.

        Args:
            schicht: Typisierte Schicht oder Rohschicht.
            entitaet: Name der Entitaet.

        Returns:
            Den Datenrahmen.

        Raises:
            RegelFehler: Wenn die Entitaet im Kontext fehlt.
        """
        quelle = self.typed if schicht is Schicht.TYPED else self.raw
        if entitaet not in quelle:
            raise RegelFehler(
                f"Entitaet {entitaet!r} fehlt in der Schicht {schicht.value}. "
                f"Vorhanden sind: {sorted(quelle)}"
            )
        return quelle[entitaet]

    def referenztabelle(self, name: str) -> pd.DataFrame:
        """Gibt eine Referenztabelle zurueck.

        Args:
            name: Tabellenname ohne Endung, zum Beispiel ``"plz_ort"``.

        Returns:
            Den Datenrahmen.

        Raises:
            RegelFehler: Wenn die Tabelle im Kontext fehlt.
        """
        if name not in self.referenz:
            raise RegelFehler(
                f"Referenztabelle {name!r} fehlt im Kontext. Vorhanden: {sorted(self.referenz)}"
            )
        return self.referenz[name]


def _leerer_rahmen(entitaet: str) -> pd.DataFrame:
    """Baut einen leeren typisierten Datenrahmen mit dem Schema der Entitaet."""
    return typisierter_rahmen({name: [] for name in SPALTEN_JE_ENTITAET[entitaet]}, entitaet)


def _vervollstaendige(
    vorgabe: Mapping[str, pd.DataFrame] | None,
) -> dict[str, pd.DataFrame]:
    """Ergaenzt fehlende Entitaeten durch leere Datenrahmen.

    Das ist der Grund, warum ein Regeltest nur die Tabelle bauen muss, um die es
    geht: Alle uebrigen Entitaeten existieren dann leer und schemakonform.
    """
    gegeben = dict(vorgabe or {})
    unbekannt = sorted(set(gegeben) - set(ENTITAETEN))
    if unbekannt:
        raise RegelFehler(f"Unbekannte Entitaeten im Kontext: {unbekannt}")
    return {
        name: (
            gegeben[name].reset_index(drop=True) if name in gegeben else _leerer_rahmen(name)
        )
        for name in ENTITAETEN
    }


def baue_kontext(
    config: Config,
    *,
    typed: Mapping[str, pd.DataFrame] | None = None,
    raw: Mapping[str, pd.DataFrame] | None = None,
    referenz: Mapping[str, pd.DataFrame] | None = None,
) -> Kontext:
    """Baut einen Pruefkontext aus einer oder beiden Datenschichten.

    Wird nur eine Schicht uebergeben, entsteht die andere ueber
    :func:`~src.common.serialisierung.serialisiere` beziehungsweise
    :func:`~src.common.serialisierung.parse`. Das ist der uebliche Fall im Test:
    Fuer eine Regel auf der Rohschicht wird ``raw`` von Hand gebaut, fuer eine
    fachliche Regel ``typed``.

    **Parsefehler werden hier nicht gemeldet.** Ein nicht parsebarer Rohwert wird
    in der typisierten Schicht zu ``pd.NA``; der Befund dazu entsteht in den
    Regeln R-009 und R-025, nicht im Kontextaufbau.

    Args:
        config: Geladene Konfiguration.
        typed: Typisierte Datenrahmen je Entitaet.
        raw: Rohe Datenrahmen je Entitaet.
        referenz: Referenztabellen; ohne Angabe werden sie aus
            ``config.pfade.reference`` geladen.

    Returns:
        Den :class:`Kontext`.

    Raises:
        RegelFehler: Wenn weder ``typed`` noch ``raw`` uebergeben wurde oder eine
            unbekannte Entitaet auftaucht.
    """
    if typed is None and raw is None:
        raise RegelFehler("Der Kontext braucht mindestens eine der beiden Datenschichten")

    if raw is None:
        typisiert = _vervollstaendige(typed)
        roh = {name: serialisiere(rahmen) for name, rahmen in typisiert.items()}
    elif typed is None:
        roh = _vervollstaendige_roh(raw)
        typisiert = {name: parse(rahmen, name)[0] for name, rahmen in roh.items()}
    else:
        typisiert = _vervollstaendige(typed)
        roh = _vervollstaendige_roh(raw)

    return Kontext(
        config=config,
        typed=typisiert,
        raw=roh,
        referenz=dict(referenz) if referenz is not None else lade_alle(config),
    )


def _vervollstaendige_roh(vorgabe: Mapping[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Ergaenzt fehlende Entitaeten der Rohschicht durch leere Datenrahmen."""
    gegeben = dict(vorgabe)
    unbekannt = sorted(set(gegeben) - set(ENTITAETEN))
    if unbekannt:
        raise RegelFehler(f"Unbekannte Entitaeten im Kontext: {unbekannt}")
    return {
        name: (
            gegeben[name].reset_index(drop=True)
            if name in gegeben
            else serialisiere(_leerer_rahmen(name))
        )
        for name in ENTITAETEN
    }


# ---------------------------------------------------------------------------
# Zugriffshilfen fuer die Regeln
# ---------------------------------------------------------------------------


def werte(rahmen: pd.DataFrame, spalte: str) -> list[Any]:
    """Liest eine Spalte der typisierten Schicht als Liste von Python-Werten.

    Fehlwerte werden einheitlich zu ``None``. Das erspart jeder Regel die
    Unterscheidung zwischen ``None``, ``pd.NA``, ``NaN`` und ``NaT``.

    Args:
        rahmen: Datenrahmen.
        spalte: Spaltenname.

    Returns:
        Die Werte in Zeilenreihenfolge.

    Raises:
        RegelFehler: Wenn die Spalte fehlt.
    """
    if spalte not in rahmen.columns:
        raise RegelFehler(f"Spalte {spalte!r} fehlt im Datenrahmen: {list(rahmen.columns)}")
    return [None if wert is None or pd.isna(wert) else wert for wert in rahmen[spalte]]


def text(rahmen: pd.DataFrame, spalte: str) -> list[str]:
    """Liest eine Spalte der Rohschicht als Liste von Zeichenketten.

    Fehlwerte werden zum leeren String — der Darstellung eines leeren Wertes in
    der Rohschicht (``spec/01``, Abschnitt 6).

    Args:
        rahmen: Datenrahmen der Rohschicht.
        spalte: Spaltenname.

    Returns:
        Die Werte in Zeilenreihenfolge.

    Raises:
        RegelFehler: Wenn die Spalte fehlt.
    """
    if spalte not in rahmen.columns:
        raise RegelFehler(f"Spalte {spalte!r} fehlt im Datenrahmen: {list(rahmen.columns)}")
    return ["" if wert is None or pd.isna(wert) else str(wert) for wert in rahmen[spalte]]


def row_ids(rahmen: pd.DataFrame) -> list[int]:
    """Liest die Spalte ``row_id`` als Liste ganzer Zahlen.

    Args:
        rahmen: Datenrahmen beliebiger Schicht.

    Returns:
        Die Zeilenkennungen. Eine fehlende oder nicht ganzzahlige Kennung wird zu
        ``-1``; sie kann nur aus einer beschaedigten Datei stammen, denn
        ``row_id`` ist niemals Ziel einer Injektion (Architekturregel A3).
    """
    ergebnis: list[int] = []
    for wert in rahmen["row_id"]:
        if wert is None or pd.isna(wert):
            ergebnis.append(-1)
            continue
        try:
            ergebnis.append(int(wert))
        except (TypeError, ValueError):
            ergebnis.append(-1)
    return ergebnis


def zuordnung(rahmen: pd.DataFrame, schluessel: str, wert: str) -> dict[Any, Any]:
    """Baut eine Abbildung von einer Schluesselspalte auf eine Wertspalte.

    Bei mehrfach vorkommendem Schluessel gewinnt der **erste** Eintrag. Die
    Reihenfolge ist damit fest und das Ergebnis reproduzierbar (Architekturregel
    A2). Zeilen mit leerem Schluessel entfallen.

    Args:
        rahmen: Quelldatenrahmen.
        schluessel: Name der Schluesselspalte.
        wert: Name der Wertspalte.

    Returns:
        Die Abbildung.
    """
    ergebnis: dict[Any, Any] = {}
    for kennung, inhalt in zip(werte(rahmen, schluessel), werte(rahmen, wert), strict=True):
        if kennung is None:
            continue
        ergebnis.setdefault(kennung, inhalt)
    return ergebnis


def gruppen(schluessel: Sequence[Any]) -> dict[Any, list[int]]:
    """Gruppiert Zeilenpositionen nach einem Schluessel.

    Die Reihenfolge der Gruppen folgt dem ersten Auftreten des Schluessels, die
    Reihenfolge innerhalb einer Gruppe der Zeilenreihenfolge. Beides ist fest —
    eine Iteration ueber ein ``set`` waere es nicht (Architekturregel A2).

    Args:
        schluessel: Schluesselwert je Zeile.

    Returns:
        Eine Abbildung Schluessel auf die Positionen seiner Zeilen. Zeilen mit
        leerem Schluessel entfallen.
    """
    ergebnis: dict[Any, list[int]] = {}
    for position, kennung in enumerate(schluessel):
        if kennung is None:
            continue
        ergebnis.setdefault(kennung, []).append(position)
    return ergebnis


# ---------------------------------------------------------------------------
# Die Regel
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Regel:
    """Eine Validierungsregel samt ihrer Herleitung.

    Die Metadaten sind nicht Beiwerk, sondern das Design-Artefakt der Arbeit: Aus
    ihnen entsteht die Mapping-Tabelle im Anhang
    (``scripts/export_katalog.py`` → ``results/regelkatalog.csv``).

    Attributes:
        regel_id: Kennung, zum Beispiel ``"R-014"``.
        beschreibung: Das Praedikat in einem Satz.
        entitaet: Zieltabelle; ``"alle"`` bei entitaetsuebergreifenden Regeln.
        spalten: Betroffene Spalten, Grundlage der Zell-Zuordnung.
        granularitaet: Achse A, ``"G1"`` bis ``"G5"``.
        fehlerklasse_b: Achse B, ``"B1"`` bis ``"B7"``.
        erkennbarkeit_c: Achse C, ``"C1"`` bis ``"C4"``.
        schweregrad: ``"HART"`` oder ``"WARNUNG"``.
        literatur: Belegkuerzel, zum Beispiel ``("RD", "KIM")``.
        fachliche_grundlage: Norm, Gesetz oder Modellannahme.
        schicht: Datenschicht, auf der die Regel arbeitet. Format-, Typ- und
            Sentinel-Regeln laufen zwingend auf :attr:`Schicht.RAW`.
        in_zellmetrik: ``False`` bei Regeln, die keine verursachende Zelle
            benennen koennen (R-047, R-048). Sie werden als Diagnosekennzahl
            gefuehrt und fliessen nicht in die Zellmetrik ein.
        pruefe: Die Pruefung. Bekommt den vollen Kontext und gibt einen
            :class:`Befund` zurueck.
    """

    regel_id: str
    beschreibung: str
    entitaet: str
    spalten: tuple[str, ...]
    granularitaet: str
    fehlerklasse_b: str
    erkennbarkeit_c: str
    schweregrad: str
    literatur: tuple[str, ...]
    fachliche_grundlage: str
    schicht: Schicht
    pruefe: Callable[[Kontext], Befund] = field(compare=False, repr=False)
    in_zellmetrik: bool = True

    def __post_init__(self) -> None:
        """Prueft die Metadaten gegen die zulaessigen Kataloge.

        Raises:
            RegelFehler: Bei einem Wert ausserhalb der Achsenkataloge. Ein
                Tippfehler in den Metadaten soll auffallen, nicht wirkungslos in
                der Anhangstabelle landen.
        """
        pruefungen = (
            ("granularitaet", self.granularitaet, GRANULARITAETEN),
            ("fehlerklasse_b", self.fehlerklasse_b, FEHLERKLASSEN),
            ("erkennbarkeit_c", self.erkennbarkeit_c, ERKENNBARKEITEN),
            ("schweregrad", self.schweregrad, SCHWEREGRADE),
        )
        for name, wert, katalog in pruefungen:
            if wert not in katalog:
                raise RegelFehler(
                    f"{self.regel_id}: {name}={wert!r} steht nicht im Katalog {list(katalog)}"
                )
        if not self.spalten:
            raise RegelFehler(f"{self.regel_id}: mindestens eine betroffene Spalte angeben")
