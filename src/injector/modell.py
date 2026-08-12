"""Datenmodell des Fehlerinjektors: Varianten, Aenderungen und Log-Schemata.

Dieses Modul definiert, **was** eine Injektionsvariante ist, und stellt den
Kontext bereit, aus dem die Varianten lesen. Die Varianten selbst liegen in
``src/injector/varianten/``.

Der Injektor importiert nichts aus ``src.rules``
-----------------------------------------------

Weder Regeln noch ihre Konstanten noch ihre Hilfsfunktionen (Architekturregel A1,
``spec/03_fehlerklassen.md``, Abschnitt 6). Er bildet **empirische
Fehlerursachen** ab — Erfassungsfehler, Schnittstellenkonvertierung,
Legacy-Migration, Freitexteingabe —, nicht die Komplemente der Pruefbedingungen.
Die Zuordnung Variante auf Regel entsteht erst in der Auswertung.

Zwei Arten von Zellen in einer Aenderung
----------------------------------------

Eine Verfaelschung besteht aus einer oder mehreren Zellaenderungen. Sie zerfallen
in zwei Arten:

* **Traegerzellen** (``mitgezogen = False``) tragen den Fehler. Sie bilden den
  Ground Truth im engeren Sinn und gehen in die Fehlerrate ein.
* **Mitgezogene Zellen** (``mitgezogen = True``) werden nur veraendert, damit der
  Satz in sich stimmig bleibt. Das betrifft ausschliesslich ``angebot.rang``:
  Wird ein Beitragstupel skaliert, verschiebt sich die Preisrangfolge der
  Anfrage. ``spec/03``, Abschnitt 2 verlangt, die Rangfolge mitzuziehen, weil
  sonst zusaetzlich die Rangregel auslaest und die Zuordnung Variante auf Regel
  falsch wuerde.

**Warum die Unterscheidung im Log stehen muss.** Eine mitgezogene Zelle ist nach
der Skalierung *richtig*, nicht falsch — sie traegt den korrekten Rang zum
verfaelschten Beitrag. Wuerde sie ununterscheidbar als injizierter Fehler
protokolliert, waere sie ein garantiertes False Negative und der gemessene Recall
fiele, ohne dass ein Detektor etwas uebersehen haette. Das ist genau die
Phantom-Ground-Truth, vor der Protokollregel 3 warnt, nur in anderer Gestalt.
Zugleich **muss** die Zelle im Log stehen, sonst faende der Diff-Gegencheck eine
Abweichung ohne Protokolleintrag.

Die Rohschicht ist Pflicht
--------------------------

:func:`pruefe_rohschicht` bricht ab, wenn ein Datenrahmen typisierte Spalten hat.
Eine stille Konvertierung waere hier besonders schaedlich: Der halbe Katalog der
Varianten ist auf typisierten Spalten gar nicht schreibbar (``spec/01``,
Abschnitt 6), und der Fehler faellt erst Stunden spaeter in der Auswertung auf.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

import pandas as pd
from numpy.random import Generator

from src.common.datum import jahre_zwischen
from src.common.enums import Rolle
from src.common.serialisierung import ENTITAETEN, SPALTEN_JE_ENTITAET
from src.injector.rohwerte import LEER, betrag_lesen, tag_lesen

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    import datetime as dt
    from decimal import Decimal

    from src.common.config import Config

__all__ = [
    "ERROR_LOG_RECORDS_SPALTEN",
    "ERROR_LOG_SPALTEN",
    "KLASSEN_NUMMER",
    "SCHLUESSELSPALTEN",
    "Aenderung",
    "Fehlerklasse",
    "InjektionsFehler",
    "Injektionsergebnis",
    "Injektionskontext",
    "Kandidat",
    "Satzaenderung",
    "Satzbefund",
    "Variante",
    "Zellaenderung",
    "Zielart",
    "baue_kontext",
    "pruefe_rohschicht",
]


class InjektionsFehler(RuntimeError):
    """Die Injektion ist nicht durchfuehrbar oder ihre Vorgaben widersprechen sich."""


class Fehlerklasse(StrEnum):
    """Die acht Fehlerklassen und die beiden Held-out-Klassen (spec/03, Abschnitt 1)."""

    F1 = "F1"
    """Fehlender Wert, explizit und implizit."""

    F2 = "F2"
    """Format- und Syntaxverletzung."""

    F3 = "F3"
    """Wertebereichs- und Katalogverletzung."""

    F4 = "F4"
    """Fachlich unmoeglicher, syntaktisch valider Wert."""

    F5 = "F5"
    """Intra-Record-Inkonsistenz einschliesslich Beitragsarithmetik."""

    F6 = "F6"
    """Exaktes Duplikat mit Konfliktwerten."""

    F7 = "F7"
    """Veralteter Tarifstand, Gueltigkeitsverletzung."""

    F8 = "F8"
    """Einheiten- und Repraesentationsfehler zwischen Quellen."""

    HO1 = "HO1"
    """Held-out: semantische Duplikate."""

    HO2 = "HO2"
    """Held-out: semantisch falsche, formal gueltige Werte."""


#: Nummer je Fehlerklasse — geht als Faktorstufe in den Zufallsstrom ein.
#:
#: Die Zahlen sind Teil der Reproduzierbarkeit und duerfen nachtraeglich nicht
#: mehr geaendert werden (Architekturregel A2, gleiche Begruendung wie bei
#: :class:`src.common.seeding.Strom`).
KLASSEN_NUMMER: Final[Mapping[Fehlerklasse, int]] = MappingProxyType(
    {klasse: nummer for nummer, klasse in enumerate(Fehlerklasse, start=1)}
)


class Zielart(StrEnum):
    """Auf welcher Ebene eine Variante wirkt."""

    ZELLE = "zelle"
    """Verfaelscht bestehende Zellen; wird zellbasiert protokolliert."""

    SATZ = "satz"
    """Fuegt Zeilen hinzu; wird ausschliesslich satzbasiert protokolliert."""


#: Schluesselspalten je Entitaet — niemals Ziel einer zellbasierten Verfaelschung.
#:
#: ``row_id`` steht ueberall an erster Stelle und ist nach Architekturregel A3
#: unantastbar: Ueber sie laeuft die Zuordnung zwischen Ground Truth und
#: Detektion, und ueber sie joint der Diff-Gegencheck ``df_clean`` und
#: ``df_dirty``.
#:
#: Die uebrigen Eintraege sind Primaer- und Fremdschluessel. Sie bleiben aus einem
#: fachlichen Grund aussen vor: Ein verlorener oder verbogener Schluessel ist eine
#: **referentielle** Stoerung und damit eine andere Fehlerart als die hier
#: modellierten. Die einzige Ausnahme ist F7-a — dort ist das Umbiegen des
#: Tarifschluessels genau der Fehler, um den es geht — und die Duplikatklassen F6
#: und HO1, die neue Schluesselwerte fuer **neue** Zeilen vergeben.
SCHLUESSELSPALTEN: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "anfrage": ("row_id", "anfrage_id", "vn_person_id", "vorversicherer_vu_nr"),
        "person": ("row_id", "person_id", "anfrage_id"),
        "risiko_kfz": ("row_id", "risiko_id", "anfrage_id"),
        "risiko_hausrat": ("row_id", "risiko_id", "anfrage_id"),
        "tarif": ("row_id", "tarif_id", "vu_nummer"),
        "angebot": ("row_id", "angebot_id", "anfrage_id", "tarif_id"),
        "zahlung": ("row_id", "zahlung_id", "anfrage_id"),
    }
)

#: Spalten des zellbasierten Logs (spec/03, Abschnitt 4.1).
#:
#: Zwei Praezisierungen gegenueber der Tabelle dort, beide in ``spec/03``
#: nachgetragen:
#:
#: * ``seed_base`` und ``seed_inject`` sind Zeichenketten, keine ``int``.
#:   :func:`src.common.seeding.seed_als_int` liefert einen 128-Bit-Wert; er passt
#:   in keine ``int64``-Parquetspalte, und ein Abschneiden waere genau die Art
#:   stiller Ungenauigkeit, die A2 ausschliesst.
#: * ``mitgezogen`` unterscheidet Traegerzellen von Zellen, die nur der
#:   Satzstimmigkeit wegen nachgefuehrt wurden (siehe Modul-Docstring).
ERROR_LOG_SPALTEN: Final[tuple[str, ...]] = (
    "run_id",
    "master_seed",
    "seed_base",
    "seed_inject",
    "entitaet",
    "row_id",
    "spalte",
    "fehlerklasse",
    "injektor_variante_id",
    "wert_clean",
    "wert_dirty",
    "mitgezogen",
)

#: Spalten des satzbasierten Logs (spec/03, Abschnitt 4.2).
#:
#: ``referenz_row_id`` ist leer, wenn nichts dupliziert wurde. Das betrifft F7-c:
#: Die Variante fuegt keine Zeile hinzu, wird aber laut ``spec/03``, Abschnitt 4.2
#: satzbasiert gefuehrt, weil sie den Gueltigkeitszeitraum einer Tarifzeile als
#: Ganzes verletzt.
ERROR_LOG_RECORDS_SPALTEN: Final[tuple[str, ...]] = (
    "run_id",
    "master_seed",
    "seed_base",
    "seed_inject",
    "entitaet",
    "fehlerklasse",
    "injektor_variante_id",
    "betroffene_row_ids",
    "referenz_row_id",
)


@dataclass(frozen=True, slots=True)
class Kandidat:
    """Ein moeglicher Angriffspunkt einer Variante.

    Attributes:
        entitaet: Name der Entitaet.
        row_id: Zeilenkennung innerhalb der Entitaet.
        spalte: Ankerspalte bei zellbasierten Varianten, ``None`` bei
            satzbasierten. Varianten, die mehrere Spalten oder mehrere Zeilen
            gemeinsam veraendern, tragen hier ihre **Ankerspalte**; welche Zellen
            tatsaechlich fallen, entscheidet erst :attr:`Variante.anwenden`.
    """

    entitaet: str
    row_id: int
    spalte: str | None


@dataclass(frozen=True, slots=True)
class Zellaenderung:
    """Eine einzelne veraenderte Zelle.

    Attributes:
        entitaet: Name der Entitaet.
        row_id: Zeilenkennung.
        spalte: Spaltenname; niemals ``row_id``.
        wert_dirty: Neuer Rohwert. ``None`` steht fuer einen **fehlenden** Wert
            (``pd.NA`` in der Rohschicht) und ist von einem eingeschleusten
            Leerstring auf der Speicherebene unterscheidbar, nach dem Parsen
            jedoch nicht mehr — siehe Variante F1-a.
        mitgezogen: ``True``, wenn die Zelle nur der Satzstimmigkeit wegen
            nachgefuehrt wurde (siehe Modul-Docstring).
    """

    entitaet: str
    row_id: int
    spalte: str
    wert_dirty: str | None
    mitgezogen: bool = False


@dataclass(frozen=True, slots=True)
class Satzaenderung:
    """Eine hinzuzufuegende Zeile.

    Attributes:
        entitaet: Name der Entitaet.
        referenz_row_id: Zeile, aus der dupliziert wurde. Sie bleibt unveraendert.
        werte: Vollstaendige Rohwerte der neuen Zeile **ohne** ``row_id``; die
            vergibt die Pipeline aus dem noch nicht benutzten Zahlenraum.
    """

    entitaet: str
    referenz_row_id: int
    werte: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class Satzbefund:
    """Ein satzbezogener Protokolleintrag ohne neue Zeile.

    Attributes:
        entitaet: Name der Entitaet.
        betroffene_row_ids: Alle beteiligten Zeilen.
        referenz_row_id: Ursprungszeile einer Duplizierung, sonst ``None``.
    """

    entitaet: str
    betroffene_row_ids: tuple[int, ...]
    referenz_row_id: int | None


@dataclass(frozen=True, slots=True)
class Aenderung:
    """Das vollstaendige Ergebnis einer angewandten Variante.

    Attributes:
        zellen: Veraenderte Zellen bestehender Zeilen.
        saetze: Hinzuzufuegende Zeilen.
        befunde: Satzbezogene Protokolleintraege ohne neue Zeile.
    """

    zellen: tuple[Zellaenderung, ...] = ()
    saetze: tuple[Satzaenderung, ...] = ()
    befunde: tuple[Satzbefund, ...] = ()


# ---------------------------------------------------------------------------
# Kontext
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Injektionskontext:
    """Lesende Sicht auf den sauberen Datensatz.

    Alle Varianten lesen ausschliesslich hierueber. Der Kontext bleibt waehrend
    der gesamten Injektion unveraendert — er zeigt immer den **sauberen** Stand.
    Das ist zulaessig, weil keine Zelle zweimal getroffen wird (Protokollregel 2)
    und der aktuelle Stand einer noch nicht getroffenen Zelle deshalb ihr
    sauberer Stand ist.

    Attributes:
        config: Geladene Konfiguration; liefert insbesondere den ``stichtag``.
        werte: Rohwerte je Entitaet und Spalte in Zeilenreihenfolge.
        row_ids: Zeilenkennungen je Entitaet in Zeilenreihenfolge.
        zeile: Abbildung Zeilenkennung auf Zeilenindex je Entitaet.
        anschriften: Paare aus Postleitzahl und Ort aus der Referenztabelle
            ``plz_ort`` — Grundlage der Variante HO2-a.
        angebote_je_anfrage: Zeilenkennungen der Angebote je Anfrage.
        personen_je_anfrage: Zeilenkennungen der Personensaetze je Anfrage.
        sparte_je_anfrage: Spartenschluessel je Anfrage.
        zahlweise_je_anfrage: Zahlweise je Anfrage.
        vn_alter_je_anfrage: Alter des Versicherungsnehmers zum Stichtag.
        versicherungssumme_je_anfrage: Hausrat-Versicherungssumme je Anfrage.
        tarif_zeile_je_id: Zeilenindex je ``tarif_id``.
        tarife_je_anbieter: Zeilenkennungen der Tarife je Anbieter und Sparte,
            aufsteigend nach ``gueltig_ab``.
    """

    config: Config
    werte: Mapping[str, Mapping[str, tuple[str, ...]]]
    row_ids: Mapping[str, tuple[int, ...]]
    zeile: Mapping[str, Mapping[int, int]]
    anschriften: tuple[tuple[str, str], ...]
    angebote_je_anfrage: Mapping[str, tuple[int, ...]]
    personen_je_anfrage: Mapping[str, tuple[int, ...]]
    sparte_je_anfrage: Mapping[str, str]
    zahlweise_je_anfrage: Mapping[str, str]
    vn_alter_je_anfrage: Mapping[str, int]
    versicherungssumme_je_anfrage: Mapping[str, Decimal]
    tarif_zeile_je_id: Mapping[str, int]
    tarife_je_anbieter: Mapping[tuple[str, str], tuple[int, ...]]

    def wert(self, entitaet: str, row_id: int, spalte: str) -> str:
        """Gibt den sauberen Rohwert einer Zelle zurueck.

        Args:
            entitaet: Name der Entitaet.
            row_id: Zeilenkennung.
            spalte: Spaltenname.

        Returns:
            Den Zellinhalt; der Leerstring steht fuer einen leeren Wert.
        """
        return self.werte[entitaet][spalte][self.zeile[entitaet][row_id]]

    def spalte(self, entitaet: str, spalte: str) -> tuple[str, ...]:
        """Gibt eine vollstaendige Rohspalte in Zeilenreihenfolge zurueck.

        Args:
            entitaet: Name der Entitaet.
            spalte: Spaltenname.

        Returns:
            Die Werte der Spalte.
        """
        return self.werte[entitaet][spalte]

    def zeilenwerte(self, entitaet: str, row_id: int) -> dict[str, str]:
        """Gibt eine vollstaendige Zeile als Abbildung Spalte auf Wert zurueck.

        Args:
            entitaet: Name der Entitaet.
            row_id: Zeilenkennung.

        Returns:
            Eine neue Abbildung; Aenderungen daran wirken nicht zurueck.
        """
        index = self.zeile[entitaet][row_id]
        return {name: werte[index] for name, werte in self.werte[entitaet].items()}


def pruefe_rohschicht(daten_raw: Mapping[str, pd.DataFrame]) -> None:
    """Prueft, dass die uebergebenen Datenrahmen die Rohschicht sind.

    Args:
        daten_raw: Abbildung Entitaetsname auf Datenrahmen.

    Raises:
        InjektionsFehler: Wenn eine Entitaet fehlt, eine Spalte nicht zum Schema
            passt oder eine Spalte nicht als Zeichenkette gefuehrt wird. Der
            letzte Fall bedeutet in aller Regel, dass versehentlich ``df_typed``
            uebergeben wurde. Es wird **nicht** stillschweigend konvertiert:
            Format-, Typ- und Sentinel-Verfaelschungen sind auf typisierten
            Spalten nicht schreibbar (spec/01, Abschnitt 6), die Injektion waere
            also nur scheinbar gelaufen.
    """
    fehlend = [name for name in ENTITAETEN if name not in daten_raw]
    if fehlend:
        raise InjektionsFehler(f"Im Datensatz fehlen die Entitaeten: {fehlend}")

    for entitaet in ENTITAETEN:
        rahmen = daten_raw[entitaet]
        erwartet = SPALTEN_JE_ENTITAET[entitaet]
        if tuple(rahmen.columns) != erwartet:
            raise InjektionsFehler(
                f"Entitaet {entitaet}: Spalten passen nicht zum Schema. "
                f"Erwartet {list(erwartet)}, erhalten {list(rahmen.columns)}."
            )
        untypisiert = [
            str(name)
            for name in rahmen.columns
            if not isinstance(rahmen[name].dtype, pd.StringDtype)
        ]
        if untypisiert:
            raise InjektionsFehler(
                f"Entitaet {entitaet}: Der Injektor arbeitet ausschliesslich auf der "
                f"Rohschicht df_raw, alle Spalten als Zeichenkette. Nicht als "
                f"Zeichenkette gefuehrt sind: {untypisiert}. Vermutlich wurde df_typed "
                "uebergeben — es wird bewusst nicht konvertiert, weil Format-, Typ- und "
                "Sentinel-Verfaelschungen auf typisierten Spalten nicht schreibbar sind "
                "(spec/01_datenmodell.md, Abschnitt 6)."
            )


def _rohwerte(rahmen: pd.DataFrame) -> dict[str, tuple[str, ...]]:
    """Liest einen Rohdatenrahmen als Spaltenabbildung reiner Zeichenketten."""
    return {
        str(name): tuple(
            LEER if wert is None or pd.isna(wert) else str(wert) for wert in rahmen[name]
        )
        for name in rahmen.columns
    }


def _gruppiere(schluessel: Sequence[str], row_ids: Sequence[int]) -> dict[str, tuple[int, ...]]:
    """Gruppiert Zeilenkennungen nach einem Schluessel; die Reihenfolge bleibt erhalten."""
    gruppen: dict[str, list[int]] = {}
    for wert, row_id in zip(schluessel, row_ids, strict=True):
        gruppen.setdefault(wert, []).append(row_id)
    return {wert: tuple(kennungen) for wert, kennungen in gruppen.items()}


def _vn_alter(
    werte: Mapping[str, Mapping[str, tuple[str, ...]]], stichtag: dt.date
) -> dict[str, int]:
    """Bestimmt das Alter des Versicherungsnehmers je Anfrage zum Stichtag."""
    person = werte["person"]
    alter: dict[str, int] = {}
    for anfrage_id, rolle, geburtsdatum in zip(
        person["anfrage_id"], person["rolle"], person["geburtsdatum"], strict=True
    ):
        if rolle != Rolle.VN.value:
            continue
        tag = tag_lesen(geburtsdatum)
        if tag is not None:
            alter[anfrage_id] = jahre_zwischen(tag, stichtag)
    return alter


def _versicherungssummen(
    werte: Mapping[str, Mapping[str, tuple[str, ...]]],
) -> dict[str, Decimal]:
    """Liest die Hausrat-Versicherungssumme je Anfrage."""
    hausrat = werte["risiko_hausrat"]
    summen: dict[str, Decimal] = {}
    for anfrage_id, roh in zip(
        hausrat["anfrage_id"], hausrat["versicherungssumme_eur"], strict=True
    ):
        betrag = betrag_lesen(roh)
        if betrag is not None:
            summen[anfrage_id] = betrag
    return summen


def _tarife_je_anbieter(
    werte: Mapping[str, Mapping[str, tuple[str, ...]]], row_ids: Sequence[int]
) -> dict[tuple[str, str], tuple[int, ...]]:
    """Ordnet die Tarifzeilen je Anbieter und Sparte, aufsteigend nach ``gueltig_ab``."""
    tarif = werte["tarif"]
    gruppen: dict[tuple[str, str], list[tuple[dt.date, int]]] = {}
    for vu_nummer, sparte, gueltig_ab, row_id in zip(
        tarif["vu_nummer"], tarif["sparte"], tarif["gueltig_ab"], row_ids, strict=True
    ):
        beginn = tag_lesen(gueltig_ab)
        if beginn is None:
            continue
        gruppen.setdefault((vu_nummer, sparte), []).append((beginn, row_id))
    return {
        schluessel: tuple(row_id for _, row_id in sorted(eintraege))
        for schluessel, eintraege in gruppen.items()
    }


def baue_kontext(config: Config, daten_raw: Mapping[str, pd.DataFrame]) -> Injektionskontext:
    """Baut die lesende Sicht auf den sauberen Datensatz.

    Args:
        config: Geladene Konfiguration.
        daten_raw: Die sieben Datenrahmen der Rohschicht.

    Returns:
        Den :class:`Injektionskontext` samt aller vorberechneten Zuordnungen.

    Raises:
        InjektionsFehler: Wenn die Datenrahmen nicht die Rohschicht sind
            (siehe :func:`pruefe_rohschicht`).
    """
    pruefe_rohschicht(daten_raw)
    from src.common import referenz  # noqa: PLC0415  (Importkosten nur bei Bedarf)

    plz_ort = referenz.lade_plz_ort(config)
    werte = {name: _rohwerte(daten_raw[name]) for name in ENTITAETEN}
    row_ids = {
        name: tuple(int(wert) for wert in werte[name]["row_id"]) for name in ENTITAETEN
    }
    zeile = {
        name: {row_id: index for index, row_id in enumerate(kennungen)}
        for name, kennungen in row_ids.items()
    }
    for name, kennungen in row_ids.items():
        if len(set(kennungen)) != len(kennungen):
            raise InjektionsFehler(f"Entitaet {name}: row_id ist nicht eindeutig")

    return Injektionskontext(
        config=config,
        werte=werte,
        row_ids=row_ids,
        zeile=zeile,
        anschriften=tuple(
            (str(plz), str(ort))
            for plz, ort in zip(plz_ort["plz"], plz_ort["ort"], strict=True)
        ),
        angebote_je_anfrage=_gruppiere(werte["angebot"]["anfrage_id"], row_ids["angebot"]),
        personen_je_anfrage=_gruppiere(werte["person"]["anfrage_id"], row_ids["person"]),
        sparte_je_anfrage=dict(
            zip(werte["anfrage"]["anfrage_id"], werte["anfrage"]["sparte"], strict=True)
        ),
        zahlweise_je_anfrage=dict(
            zip(werte["anfrage"]["anfrage_id"], werte["anfrage"]["zahlweise"], strict=True)
        ),
        vn_alter_je_anfrage=_vn_alter(werte, config.stichtag),
        versicherungssumme_je_anfrage=_versicherungssummen(werte),
        tarif_zeile_je_id={
            tarif_id: index for index, tarif_id in enumerate(werte["tarif"]["tarif_id"])
        },
        tarife_je_anbieter=_tarife_je_anbieter(werte, row_ids["tarif"]),
    )


# ---------------------------------------------------------------------------
# Variante
# ---------------------------------------------------------------------------

#: Signatur der Kandidatenfunktion einer Variante.
KandidatenFunktion = Callable[[Injektionskontext], tuple[Kandidat, ...]]

#: Signatur der Anwendungsfunktion einer Variante.
#:
#: Gibt ``None`` zurueck, wenn die Variante auf diesen Kandidaten doch nicht
#: anwendbar ist. Das ist kein Fehler, sondern der Normalfall bei Varianten mit
#: einer Bedingung, die erst beim Anwenden feststeht.
AnwendungsFunktion = Callable[[Injektionskontext, Kandidat, Generator], "Aenderung | None"]


@dataclass(frozen=True, slots=True)
class Variante:
    """Eine Injektionsvariante aus ``spec/03_fehlerklassen.md``, Abschnitt 2.

    Attributes:
        variante_id: Stabile Kennung, zum Beispiel ``F3-d``. Sie steht im Ground
            Truth und ist die Achse, entlang derer der Recall berichtet wird.
        fehlerklasse: Klasse, zu der die Variante gehoert.
        zielart: Zell- oder satzbasiert.
        beschreibung: Fachliche Kurzbeschreibung der Verfaelschung.
        ursache: Empirische Ursache, die die Variante nachbildet. Sie ist der
            Grund, warum die Variante so und nicht anders aussieht — der Injektor
            bildet Fehlerursachen ab, nicht Regelkomplemente.
        kandidaten: Liefert alle Zellen beziehungsweise Zeilen, an denen die
            Variante ansetzen kann, in fester Reihenfolge.
        anwenden: Erzeugt die Aenderung zu einem Kandidaten.
        zusatzspalten: Weitere Spalten derselben Zeile, die die Variante als
            Traegerzellen mitveraendert. Sie gehen in das adressierbare
            Zelluniversum ein; ``angebot.rang`` steht hier bewusst **nicht**,
            weil es mitgezogen und nicht Traeger ist.
        zieht_rang_nach: ``True`` bei den Varianten, die ein Beitragstupel
            skalieren und deren Anfrage deshalb am Ende des Laufs eine
            nachgefuehrte Preisrangfolge braucht (F8-b bis F8-e, HO2-b).

            Die Variante fuehrt die Rangfolge **nicht selbst** nach. Sie meldet
            mit diesem Merkmal nur an, dass ihre Anfrage betroffen ist; das
            Nachfuehren erledigt :mod:`src.injector.pipeline` einmalig am Ende
            gegen den Endstand. Die Begruendung steht dort im Modul-Docstring —
            kurz: Kohaerenz je Verfaelschung gegen den **sauberen** Ausgangsstand
            herzustellen haelt nicht, sobald zwei Verfaelschungen dieselbe
            Bezugsgruppe treffen.
    """

    variante_id: str
    fehlerklasse: Fehlerklasse
    zielart: Zielart
    beschreibung: str
    ursache: str
    kandidaten: KandidatenFunktion
    anwenden: AnwendungsFunktion
    zusatzspalten: tuple[str, ...] = ()
    zieht_rang_nach: bool = False


# ---------------------------------------------------------------------------
# Ergebnis
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Injektionsergebnis:
    """Ergebnis eines Injektionslaufs.

    Attributes:
        run_id: Kennung des Laufs.
        df_raw_dirty: Die sieben verfaelschten Datenrahmen der Rohschicht.
        error_log: Zellbasierter Ground Truth (spec/03, Abschnitt 4.1).
        error_log_records: Satzbasierter Ground Truth (Abschnitt 4.2).
        universum: Groesse des adressierbaren Zelluniversums je Fehlerklasse.
        einheit_je_klasse: Bezugseinheit des Universums je Klasse — ``zelle``
            oder ``satz``.
        ziel_je_klasse: Rechnerisch angeforderte Zahl der Verfaelschungen.
        fehler_je_klasse: Erreichte Zahl der Traegerzellen beziehungsweise Saetze.
        fehler_je_variante: Dieselbe Zahl je Injektionsvariante.
        universum_je_variante: Adressierbares Universum je Injektionsvariante.
        anteil_je_variante: Anteil jeder Variante am Klassenkontingent. Er ist
            **von der Fehlerrate unabhaengig** — das ist der Zweck der
            proportionalen Zuteilung (:mod:`src.injector.auswahl`).
        quote_je_variante: Zugeteilte Zahl je Variante vor der Ausfuehrung.
        granularitaetsabweichung: Summe der Betraege, um die die erreichte Zahl
            von der zugeteilten abweicht. Sie entsteht ausschliesslich daraus,
            dass eine kohaerente Skalierung vier Beitragsfelder auf einmal
            veraendert und sich nicht in Teile zerlegen laesst. Bei Klassen mit
            ausschliesslich einzelligen Varianten ist sie null. Umverteilt wird
            **nichts** — das wuerde die Variantenmischung mit der Fehlerrate
            verschieben (:mod:`src.injector.auswahl`).
        zellen_fehlerhaft: Zahl der **fehlerhaften** Zellen — die Traegerzellen.
        zellen_geaendert_gesamt: Zahl **aller** veraenderten Zellen, also
            einschliesslich der nur nachgefuehrten. Der Datensatz ist an so vielen
            Stellen veraendert; die Fehlerrate bezieht sich auf die erste Zahl.
        mitgezogene_zellen: Differenz beider Zahlen.
        seeds: Seeds des Laufs als Zeichenketten.
    """

    run_id: str
    df_raw_dirty: dict[str, pd.DataFrame]
    error_log: pd.DataFrame
    error_log_records: pd.DataFrame
    universum: Mapping[str, int]
    einheit_je_klasse: Mapping[str, str]
    ziel_je_klasse: Mapping[str, int]
    fehler_je_klasse: Mapping[str, int]
    fehler_je_variante: Mapping[str, int]
    universum_je_variante: Mapping[str, int]
    anteil_je_variante: Mapping[str, float]
    quote_je_variante: Mapping[str, int]
    granularitaetsabweichung: int
    zellen_fehlerhaft: int
    zellen_geaendert_gesamt: int
    mitgezogene_zellen: int
    seeds: Mapping[str, str]
