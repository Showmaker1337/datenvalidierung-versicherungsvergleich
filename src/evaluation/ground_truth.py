"""Aufbereitung der beiden Ground-Truth-Logs zu Wahrheitsmengen.

Der Injektor legt je Lauf zwei Protokolle ab (``spec/03_fehlerklassen.md``,
Abschnitt 4): ``error_log.parquet`` mit einer Zeile je verfaelschter **Zelle** und
``error_log_records.parquet`` mit einer Zeile je satzbezogener Verfaelschung.
Dieses Modul liest beide und baut daraus die Mengen, gegen die jedes Verfahren
gemessen wird. Es kennt weder den Injektorquelltext noch die Variantendefinitionen
— die Spaltennamen stammen aus der Spezifikation, nicht aus einem Import
(Architekturregel A1 sinngemaess, Abschnitt 1 des Phasenkontrakts).

Warum beide Partner eines Duplikatpaares zaehlen
-------------------------------------------------

Bei F6 (exaktes Duplikat mit Konfliktwerten) und HO1 (semantisches Duplikat) fuegt
der Injektor eine Zeile hinzu. Ein zellweises Diff ist dort undefiniert: Es gibt
keine saubere Vorgaengerzelle, gegen die man vergleichen koennte (``spec/03``,
Abschnitt 4.2). Der Fehler ist eine Eigenschaft des **Paares**.

Als Satzwahrheit werden deshalb **beide** ``row_id`` des Paares gefuehrt. Der
Grund ist keine Grosszuegigkeit, sondern Messbarkeit: Keine Regel kann sagen,
welche der beiden Zeilen die hinzugefuegte ist — sie sind ja in den fachlichen
Feldern gleich. Der Injektor vergibt der neuen Zeile eine neue ``row_id``
ausschliesslich technisch, und diese technische Reihenfolge duerfte nicht darueber
entscheiden, ob ein Duplikatbefund als Treffer oder als Fehlalarm zaehlt. Wuerde
nur eine der beiden Zeilen als Wahrheit gefuehrt, produzierte jede korrekt
arbeitende Duplikatregel je Paar genau ein garantiertes False Positive.

Das Zelluniversum wird auf dem verfaelschten Datensatz gezaehlt
---------------------------------------------------------------

``universum_zellen`` ist ``sum(len(rahmen) * len(rahmen.columns))`` ueber alle
Entitaeten von ``df_raw_dirty`` — dieselbe Definition wie in
``scripts/validate.py::_zelluniversum``. Nur so bleibt die gemessene
False-Positive-Rate mit der des Clean-Baseline-Laufs vergleichbar; zwei
verschiedene Bezugsgroessen ergaeben zwei Zahlen, die man nicht nebeneinander
stellen darf.

Gezaehlt wird auf dem **verfaelschten** Datensatz, weil F6 und HO1 Zeilen
hinzufuegen: Ein Verfahren kann nur die Zellen melden, die es sieht, und darf nur
gegen die Zellen bewertet werden, die es sehen konnte.

``row_id`` wird dabei ausdruecklich **mitgezaehlt**. Die Spalte ist niemals Ziel
einer Injektion (Architekturregel A3); sie gehoert damit strukturell zu den echten
Negativen. Sie aus dem Nenner zu nehmen wuerde die False-Positive-Rate um rund ein
Zehntel bis ein Fuenfzehntel anheben, ohne dass sich an den Meldungen etwas
aenderte — eine Kosmetik, die in die falsche Richtung zeigt.

Zwei Assertionen, auf die sich die Metrik verlaesst
----------------------------------------------------

1. **Keine Doppelinjektion (Protokollregel 2).** Kommt das Tripel
   ``(entitaet, row_id, spalte)`` im ``error_log`` zweimal vor, wird
   :class:`~src.evaluation.modell.AuswertungsFehler` geworfen. Die
   Konfusionsmatrix arbeitet mit Mengen; eine doppelt protokollierte Zelle waere
   in der Menge einmal vorhanden, in der Klassenzuordnung aber zweideutig, und
   ``n`` je Klasse wuerde die Summe der Klassen ueber die Zahl der Wahrheitszellen
   heben. Der Fehler faellt dann als unerklaerliche Abweichung zwischen Micro- und
   Macro-Recall auf, Stunden spaeter und an der falschen Stelle.
2. **``row_id`` ist niemals Zielspalte (Architekturregel A3).** Eine Logzeile mit
   ``spalte == "row_id"`` bedeutet, dass der Ground Truth selbst beschaedigt ist;
   dann ist jede darauf gerechnete Kennzahl wertlos.

Beide Pruefungen brechen ab, statt zu bereinigen. Ein stiller Fix an dieser Stelle
waere genau die Sorte Korrektur, die spaeter niemand mehr im Ergebnis sieht.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from src.evaluation.modell import AuswertungsFehler

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence

    import pandas as pd

__all__ = [
    "ERROR_LOG_PFLICHTSPALTEN",
    "RECORDS_PFLICHTSPALTEN",
    "GroundTruth",
    "Satzwahrheit",
    "Zellwahrheit",
    "lade_ground_truth",
]

#: Spalten, die dieses Modul im ``error_log`` erwartet (spec/03, Abschnitt 4.1).
#:
#: Bewusst hier ausgeschrieben und **nicht** aus ``src.injector.modell``
#: importiert: Die Auswertung liest ein Dateiformat, sie teilt keinen Quelltext
#: mit dem Erzeuger.
ERROR_LOG_PFLICHTSPALTEN: tuple[str, ...] = (
    "entitaet",
    "row_id",
    "spalte",
    "fehlerklasse",
    "injektor_variante_id",
    "mitgezogen",
)

#: Spalten, die dieses Modul im ``error_log_records`` erwartet (Abschnitt 4.2).
RECORDS_PFLICHTSPALTEN: tuple[str, ...] = (
    "entitaet",
    "fehlerklasse",
    "injektor_variante_id",
    "betroffene_row_ids",
)

#: Name der Spalte, die niemals Ziel einer Verfaelschung sein darf (A3).
_GESCHUETZTE_SPALTE: str = "row_id"


@dataclass(frozen=True, slots=True)
class Zellwahrheit:
    """Eine tatsaechlich verfaelschte Zelle.

    Attributes:
        entitaet: Tabellenname.
        row_id: Zeilenkennung.
        spalte: Feldname.
        fehlerklasse: Klasse aus ``spec/03``, Abschnitt 1, zum Beispiel ``"F3"``.
        injektor_variante_id: Variante, zum Beispiel ``"F3-b"``.
        mitgezogen: ``True``, wenn die Zelle nur der Satzstimmigkeit wegen
            nachgefuehrt wurde und gegenueber den verfaelschten Daten damit
            **korrekt** ist.
    """

    entitaet: str
    row_id: int
    spalte: str
    fehlerklasse: str
    injektor_variante_id: str
    mitgezogen: bool

    @property
    def schluessel(self) -> tuple[str, int, str]:
        """Gibt das Tripel ``(entitaet, row_id, spalte)`` zurueck."""
        return (self.entitaet, self.row_id, self.spalte)


@dataclass(frozen=True, slots=True)
class Satzwahrheit:
    """Eine Zeile, die von einer Verfaelschung betroffen ist.

    Attributes:
        entitaet: Tabellenname.
        row_id: Zeilenkennung.
        fehlerklasse: Klasse der Verfaelschung.
        injektor_variante_id: Variante der Verfaelschung.
        mitgezogen: ``True``, wenn die Zeile ihren Eintrag **ausschliesslich**
            mitgezogenen Zellen verdankt. Eine solche Zeile ist gegenueber den
            verfaelschten Daten in Ordnung; ein Verfahren, das sie nicht meldet,
            macht keinen Fehler.
    """

    entitaet: str
    row_id: int
    fehlerklasse: str
    injektor_variante_id: str
    mitgezogen: bool

    @property
    def schluessel(self) -> tuple[str, int]:
        """Gibt das Paar ``(entitaet, row_id)`` zurueck."""
        return (self.entitaet, self.row_id)


@dataclass(frozen=True, slots=True)
class GroundTruth:
    """Die vollstaendige Wahrheit eines Laufs, aufbereitet fuer die Metrik.

    Attributes:
        run_id: Kennung des Laufs; traegt in der verschachtelten Form alle
            Faktorstufen (CLAUDE.md, Abschnitt 3).
        zellen: Alle protokollierten Zellverfaelschungen, sortiert nach
            ``(entitaet, row_id, spalte)``.
        saetze: Alle betroffenen Zeilen, sortiert nach
            ``(entitaet, row_id, fehlerklasse, injektor_variante_id)``.
        klassen: Alle Fehlerklassen des Laufs, sortiert. Enthaelt auch Klassen mit
            ``n = 0``, wenn sie beim Laden mitgegeben wurden.
        varianten: Alle Injektionsvarianten des Laufs, sortiert; ebenfalls
            einschliesslich der Varianten mit Kontingent 0.
        universum_zellen: Zellen des **verfaelschten** Datensatzes, ``row_id``
            eingeschlossen.
        universum_saetze: Zeilen des verfaelschten Datensatzes.
        zeilen_je_entitaet: Zeilenzahl je Entitaet, fuer Diagnose und Normierung.
    """

    run_id: str
    zellen: tuple[Zellwahrheit, ...]
    saetze: tuple[Satzwahrheit, ...]
    klassen: tuple[str, ...]
    varianten: tuple[str, ...]
    universum_zellen: int
    universum_saetze: int
    zeilen_je_entitaet: Mapping[str, int]

    def zellmenge(self, *, mitgezogen_als_fehler: bool) -> dict[tuple[str, int, str], Zellwahrheit]:
        """Baut die Wahrheitsmenge der Zellebene.

        Args:
            mitgezogen_als_fehler: Wenn ``False``, bleiben mitgezogene Zellen
                aussen vor. Das ist die Hauptauswertung: Eine nachgefuehrte
                Rangzelle traegt den korrekten Rang zum verfaelschten Beitrag und
                ist damit kein Datenqualitaetsmangel.

        Returns:
            Eine Abbildung ``(entitaet, row_id, spalte)`` auf die
            :class:`Zellwahrheit`, in der Reihenfolge von :attr:`zellen`.
        """
        return {
            eintrag.schluessel: eintrag
            for eintrag in self.zellen
            if mitgezogen_als_fehler or not eintrag.mitgezogen
        }

    def satzmenge(
        self, *, mitgezogen_als_fehler: bool
    ) -> dict[tuple[str, int], tuple[Satzwahrheit, ...]]:
        """Baut die Wahrheitsmenge der Satzebene.

        Eine Zeile kann mehrere Eintraege tragen — im Mischmodus etwa je einen aus
        zwei Fehlerklassen. Deshalb ein Tupel je Zeile und nicht ein einzelner
        Eintrag; der gruppenweise Recall braucht alle Zuordnungen.

        Args:
            mitgezogen_als_fehler: Wenn ``False``, entfallen Eintraege, die eine
                Zeile nur mitgezogenen Zellen verdankt. Zeilen, von denen dann
                kein Eintrag uebrig bleibt, entfallen ganz.

        Returns:
            Eine Abbildung ``(entitaet, row_id)`` auf die zugehoerigen
            :class:`Satzwahrheit`-Eintraege.
        """
        ergebnis: dict[tuple[str, int], tuple[Satzwahrheit, ...]] = {}
        for eintrag in self.saetze:
            if not mitgezogen_als_fehler and eintrag.mitgezogen:
                continue
            ergebnis[eintrag.schluessel] = (*ergebnis.get(eintrag.schluessel, ()), eintrag)
        return ergebnis


# ---------------------------------------------------------------------------
# Laden
# ---------------------------------------------------------------------------


def lade_ground_truth(  # noqa: PLR0913 - beide Logs, die Daten und drei Kennungen gehen ein
    error_log: pd.DataFrame,
    error_log_records: pd.DataFrame,
    daten_dirty: Mapping[str, pd.DataFrame],
    *,
    run_id: str,
    klassen: Sequence[str] | None = None,
    varianten: Sequence[str] | None = None,
) -> GroundTruth:
    """Baut den :class:`GroundTruth` eines Laufs aus beiden Logs.

    Args:
        error_log: Zellbasiertes Protokoll des Injektors.
        error_log_records: Satzbasiertes Protokoll des Injektors.
        daten_dirty: Rohschicht des **verfaelschten** Datensatzes je Entitaet.
            Bestimmt Zell- und Satzuniversum.
        run_id: Kennung des Laufs.
        klassen: Alle im Lauf vorgesehenen Fehlerklassen, ueblicherweise aus dem
            ``manifest.json``. Ohne Angabe werden nur die tatsaechlich
            protokollierten Klassen gefuehrt; mit Angabe bleiben auch Klassen mit
            ``n = 0`` in den Tabellen sichtbar, statt stillschweigend zu fehlen.
        varianten: Ebenso fuer die Injektionsvarianten. Gerade hier wichtig: Seit
            der proportionalen Zuteilung koennen einzelne Varianten bei kleinen
            Fehlerraten das Kontingent 0 erhalten, und eine fehlende Zeile in der
            Ergebnistabelle waere von einem Recall 0 nicht zu unterscheiden.

    Returns:
        Den aufbereiteten :class:`GroundTruth`.

    Raises:
        AuswertungsFehler: Wenn eine Pflichtspalte fehlt, eine Zelle doppelt
            protokolliert ist (Protokollregel 2) oder ``row_id`` als Zielspalte
            auftaucht (Architekturregel A3).
    """
    zellen = _lies_zellen(error_log)
    saetze = _baue_saetze(zellen, _lies_records(error_log_records))

    beobachtete_klassen = {eintrag.fehlerklasse for eintrag in zellen}
    beobachtete_klassen |= {eintrag.fehlerklasse for eintrag in saetze}
    beobachtete_varianten = {eintrag.injektor_variante_id for eintrag in zellen}
    beobachtete_varianten |= {eintrag.injektor_variante_id for eintrag in saetze}

    zeilen_je_entitaet = {name: len(daten_dirty[name]) for name in sorted(daten_dirty)}
    universum_zellen = sum(
        int(len(daten_dirty[name]) * len(daten_dirty[name].columns)) for name in sorted(daten_dirty)
    )

    return GroundTruth(
        run_id=run_id,
        zellen=zellen,
        saetze=saetze,
        klassen=_vereinige(beobachtete_klassen, klassen),
        varianten=_vereinige(beobachtete_varianten, varianten),
        universum_zellen=universum_zellen,
        universum_saetze=sum(zeilen_je_entitaet.values()),
        zeilen_je_entitaet=zeilen_je_entitaet,
    )


def _vereinige(beobachtet: set[str], vorgabe: Sequence[str] | None) -> tuple[str, ...]:
    """Vereinigt beobachtete und vorgegebene Gruppenkennungen zu einem sortierten Tupel.

    Sortiert wird explizit; eine Iteration ueber die Menge waere von Lauf zu Lauf
    verschieden und damit ein Verstoss gegen Architekturregel A2.

    Args:
        beobachtet: In den Logs vorgefundene Kennungen.
        vorgabe: Zusaetzliche Kennungen aus dem Manifest, oder ``None``.

    Returns:
        Die sortierte Vereinigung.
    """
    if vorgabe is not None:
        beobachtet = beobachtet | set(vorgabe)
    return tuple(sorted(beobachtet))


def _pruefe_spalten(rahmen: pd.DataFrame, pflicht: Sequence[str], name: str) -> None:
    """Stellt sicher, dass ein Log alle erwarteten Spalten hat.

    Args:
        rahmen: Der gelesene Datenrahmen.
        pflicht: Erwartete Spaltennamen.
        name: Bezeichnung des Logs fuer die Fehlermeldung.

    Raises:
        AuswertungsFehler: Wenn eine Spalte fehlt.
    """
    fehlend = [spalte for spalte in pflicht if spalte not in rahmen.columns]
    if fehlend:
        raise AuswertungsFehler(
            f"Dem {name} fehlen die Spalten {fehlend}. Vorhanden sind "
            f"{list(rahmen.columns)}. Das Log entsteht mit 'python scripts/inject.py'; "
            "eine aeltere Datei muss neu erzeugt werden."
        )


def _lies_zellen(error_log: pd.DataFrame) -> tuple[Zellwahrheit, ...]:
    """Liest das zellbasierte Log und prueft die beiden harten Zusicherungen.

    Args:
        error_log: Zellbasiertes Protokoll des Injektors.

    Returns:
        Die Zellwahrheiten, sortiert nach ``(entitaet, row_id, spalte)``.

    Raises:
        AuswertungsFehler: Bei fehlender Spalte, bei ``row_id`` als Zielspalte
            oder bei einer doppelt protokollierten Zelle.
    """
    _pruefe_spalten(error_log, ERROR_LOG_PFLICHTSPALTEN, "error_log")

    gesehen: dict[tuple[str, int, str], str] = {}
    eintraege: list[Zellwahrheit] = []
    for zeile in error_log[list(ERROR_LOG_PFLICHTSPALTEN)].itertuples(index=False, name=None):
        entitaet, row_id, spalte, klasse, variante, mitgezogen = zeile
        eintrag = Zellwahrheit(
            entitaet=str(entitaet),
            row_id=int(row_id),
            spalte=str(spalte),
            fehlerklasse=str(klasse),
            injektor_variante_id=str(variante),
            mitgezogen=bool(mitgezogen),
        )
        if eintrag.spalte == _GESCHUETZTE_SPALTE:
            raise AuswertungsFehler(
                f"Das error_log nennt {_GESCHUETZTE_SPALTE!r} als Zielspalte "
                f"({eintrag.entitaet}, row_id={eintrag.row_id}, "
                f"Variante {eintrag.injektor_variante_id}). Architekturregel A3 schliesst "
                "das aus; der Ground Truth dieses Laufs ist unbrauchbar und muss neu "
                "erzeugt werden."
            )
        vorher = gesehen.get(eintrag.schluessel)
        if vorher is not None:
            raise AuswertungsFehler(
                f"Die Zelle {eintrag.schluessel} ist zweimal protokolliert "
                f"(Varianten {vorher} und {eintrag.injektor_variante_id}). Protokollregel 2 "
                "verbietet die Doppelinjektion, und die Metrik verlaesst sich darauf: "
                "Zellmengen sind Mengen, die Klassenzuordnung waere zweideutig."
            )
        gesehen[eintrag.schluessel] = eintrag.injektor_variante_id
        eintraege.append(eintrag)

    return tuple(sorted(eintraege, key=lambda eintrag: eintrag.schluessel))


def _lies_records(error_log_records: pd.DataFrame) -> tuple[Satzwahrheit, ...]:
    """Liest das satzbasierte Log und faltet ``betroffene_row_ids`` auseinander.

    Jede betroffene Zeile wird zu einem eigenen :class:`Satzwahrheit`-Eintrag —
    einschliesslich **beider** Partner eines Duplikatpaares (siehe
    Modul-Docstring).

    Args:
        error_log_records: Satzbasiertes Protokoll des Injektors.

    Returns:
        Die Satzwahrheiten in Logreihenfolge; ``mitgezogen`` ist stets ``False``,
        denn eine satzbezogene Verfaelschung wird nie nur nachgefuehrt.

    Raises:
        AuswertungsFehler: Wenn eine Pflichtspalte fehlt.
    """
    _pruefe_spalten(error_log_records, RECORDS_PFLICHTSPALTEN, "error_log_records")

    eintraege: list[Satzwahrheit] = []
    for zeile in error_log_records[list(RECORDS_PFLICHTSPALTEN)].itertuples(index=False, name=None):
        entitaet, klasse, variante, betroffene = zeile
        eintraege.extend(
            Satzwahrheit(
                entitaet=str(entitaet),
                row_id=row_id,
                fehlerklasse=str(klasse),
                injektor_variante_id=str(variante),
                mitgezogen=False,
            )
            for row_id in _row_ids(betroffene)
        )
    return tuple(eintraege)


def _row_ids(betroffene: Any) -> list[int]:  # noqa: ANN401 - Parquet liefert Liste oder ndarray
    """Wandelt den Listenwert einer ``betroffene_row_ids``-Zelle in ganze Zahlen.

    Args:
        betroffene: Der aus Parquet gelesene Wert; je nach Leseweg eine Liste, ein
            ``numpy``-Array oder ein fehlender Wert.

    Returns:
        Die Zeilenkennungen in unveraenderter Reihenfolge; eine leere Liste, wenn
        die Zelle leer ist.

    Raises:
        AuswertungsFehler: Wenn der Wert kein iterierbarer Container ist.
    """
    if betroffene is None:
        return []
    if isinstance(betroffene, str) or not isinstance(betroffene, Iterable):
        raise AuswertungsFehler(
            f"'betroffene_row_ids' muss eine Liste von Zeilenkennungen sein, gelesen "
            f"wurde {betroffene!r} vom Typ {type(betroffene).__name__}."
        )
    return [int(wert) for wert in betroffene]


def _baue_saetze(
    zellen: Sequence[Zellwahrheit],
    aus_records: Sequence[Satzwahrheit],
) -> tuple[Satzwahrheit, ...]:
    """Bildet die Satzwahrheit als Vereinigung beider Quellen.

    Die Satzwahrheit ist die Vereinigung aus

    * allen Zeilen mit mindestens einer Zelle im ``error_log`` — je Kombination
      aus Zeile, Fehlerklasse und Variante ein Eintrag, dessen ``mitgezogen`` nur
      dann ``True`` ist, wenn **alle** zugehoerigen Logzellen mitgezogen sind, und
    * allen Zeilen aus ``betroffene_row_ids`` des ``error_log_records``.

    Trifft dieselbe Kombination aus beiden Quellen ein, gewinnt ``mitgezogen =
    False``: Sobald **eine** Quelle die Zeile als echt betroffen fuehrt, ist sie
    es. Eine Vereinigung darf keinen Eintrag schwaechen.

    Args:
        zellen: Zellwahrheiten aus dem ``error_log``.
        aus_records: Satzwahrheiten aus dem ``error_log_records``.

    Returns:
        Die Satzwahrheiten, sortiert nach
        ``(entitaet, row_id, fehlerklasse, injektor_variante_id)``.
    """
    gesammelt: dict[tuple[str, int, str, str], bool] = {}

    for zelle in zellen:
        schluessel = (
            zelle.entitaet,
            zelle.row_id,
            zelle.fehlerklasse,
            zelle.injektor_variante_id,
        )
        vorher = gesammelt.get(schluessel, True)
        gesammelt[schluessel] = vorher and zelle.mitgezogen

    for satz in aus_records:
        schluessel = (satz.entitaet, satz.row_id, satz.fehlerklasse, satz.injektor_variante_id)
        gesammelt[schluessel] = False

    return tuple(
        Satzwahrheit(
            entitaet=entitaet,
            row_id=row_id,
            fehlerklasse=klasse,
            injektor_variante_id=variante,
            mitgezogen=mitgezogen,
        )
        for (entitaet, row_id, klasse, variante), mitgezogen in sorted(gesammelt.items())
    )
