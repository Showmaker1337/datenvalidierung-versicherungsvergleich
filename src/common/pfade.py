"""Laufverzeichnisse, Artefaktnamen und Hashwerte.

Die Namen der Laufartefakte sind hier zentral festgelegt, damit Generator,
Injektor, Regel-Engine und Auswertung dieselbe Datei meinen (spec/03, Abschnitt
5, Protokollregel 6).

Die Hashfunktionen dienen dem Nachweis der Reproduzierbarkeit: Zwei Laeufe mit
demselben Seed muessen bitgleiche Artefakte erzeugen (Architekturregel A2).
"""

from __future__ import annotations

import hashlib
import io
import re
from enum import StrEnum
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from pathlib import Path

    import pandas as pd

    from src.common.config import Config

__all__ = [
    "CLEAN_MANIFEST",
    "DIRTY",
    "MISCHMODUS",
    "REFERENZ_DATEIEN",
    "Artefakt",
    "PfadFehler",
    "Schicht",
    "artefakt_pfad",
    "clean_verzeichnis",
    "entitaet_pfad",
    "experiment_run_id",
    "experiment_verzeichnis",
    "lauf_verzeichnis",
    "pruefe_run_id",
    "raten_token",
    "sha256_bytes",
    "sha256_dataframe",
    "sha256_datei",
    "sha256_verzeichnis",
    "wiederholungs_token",
]

#: Blockgroesse beim Einlesen grosser Dateien.
_BLOCKGROESSE: Final[int] = 1 << 20

#: Zulaessiges Muster einer ``run_id``.
#:
#: Bewusst eng gefasst: Die ``run_id`` wird zu einem Verzeichnisnamen. Punkte,
#: Schraegstriche und Leerzeichen sind ausgeschlossen, damit kein Lauf ausserhalb
#: von ``data/runs`` schreiben kann.
_MUSTER_RUN_ID: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

#: Dateinamen der versionierten Referenztabellen (spec/01, Abschnitt 2).
REFERENZ_DATEIEN: Final[tuple[str, ...]] = (
    "plz_ort.csv",
    "regionalklassen.csv",
    "typklassen.csv",
    "vu_stammdaten.csv",
    "zuers_zonen.csv",
    "sf_beitragssatz.csv",
    "waehrungen.csv",
)


class PfadFehler(ValueError):
    """Ein Pfad oder eine Lauf-Kennung ist nicht verwendbar."""


class Artefakt(StrEnum):
    """Dateinamen der Artefakte eines Laufs unter ``data/runs/<run_id>/``."""

    CONFIG = "config.yaml"
    """Vollstaendige Konfiguration des Laufs inklusive aller Faktorstufen und Seeds."""

    MANIFEST = "manifest.json"
    """Groesse des adressierbaren Zelluniversums je Fehlerklasse und Laufmetadaten."""

    DF_TYPED_CLEAN = "df_typed_clean.parquet"
    """Typisierte Innenansicht des sauberen Datensatzes."""

    DF_RAW_CLEAN = "df_raw_clean.parquet"
    """Rohschicht des sauberen Datensatzes, alle Spalten als String."""

    DF_RAW_DIRTY = "df_raw_dirty.parquet"
    """Rohschicht nach der Injektion."""

    ERROR_LOG = "error_log.parquet"
    """Zellbasierter Ground Truth."""

    ERROR_LOG_RECORDS = "error_log_records.parquet"
    """Satzbasierter Ground Truth fuer Duplikate und hinzugefuegte Zeilen."""

    DETECTIONS = "detections.parquet"
    """Meldungen der Regel-Engine und der Vergleichsverfahren."""

    METRICS = "metrics.json"
    """Kennzahlen des Laufs."""

    HASHES = "hashes.json"
    """SHA-256-Hashwerte der erzeugten Datenrahmen."""


class Schicht(StrEnum):
    """Die beiden Datenschichten aus spec/01, Abschnitt 6."""

    TYPED = "typed"
    """Typisierte Innenansicht: ``date``, ``Decimal``, ``int``, ``bool``."""

    RAW = "raw"
    """Rohschicht, alle Spalten als Zeichenkette."""


#: Verzeichnis des sauberen Datensatzes unterhalb des Laufverzeichnisses.
_CLEAN: Final[str] = "clean"

#: Verzeichnis des verfaelschten Datensatzes unterhalb des Laufverzeichnisses.
#:
#: Es entsteht nur, wenn ``scripts/inject.py`` mit ``--behalten`` aufgerufen wird.
#: Regulaer wird ``df_raw_dirty`` **nicht** dauerhaft gespeichert: Bei mehreren
#: tausend Laeufen zu je rund 60.000 Zeilen entstuenden zweistellige Gigabyte, und
#: der verfaelschte Datensatz ist aus ``seed_basis`` und ``seed_inject`` jederzeit
#: exakt reproduzierbar.
DIRTY: Final[str] = "dirty"

#: Manifest des sauberen Datensatzes: Zeilenzahlen, Hashwerte, Seeds, Konfiguration.
CLEAN_MANIFEST: Final[str] = "manifest.json"

#: Pfadsegment und Klassenkuerzel des Mischmodus-Teilversuchs (spec/03, Abschnitt 3).
MISCHMODUS: Final[str] = "mix"

#: Zulaessiges Muster eines Serien- und eines Designnamens.
_MUSTER_SEGMENT: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")

#: Basispunkte einer Fehlerrate von 100 Prozent — Nenner der Ratenkodierung.
_BASISPUNKTE: Final[int] = 10000

#: Stellenzahl der Rate in Basispunkten im Pfad und in der ``run_id``.
_RATEN_STELLEN: Final[int] = 4

#: Stellenzahl der Wiederholungsnummer im Pfad und in der ``run_id``.
_WIEDERHOLUNGS_STELLEN: Final[int] = 2


def pruefe_run_id(run_id: str) -> str:
    """Prueft eine Lauf-Kennung auf Verwendbarkeit als Verzeichnisname.

    Args:
        run_id: Kennung des Laufs.

    Returns:
        Die unveraenderte Kennung.

    Raises:
        PfadFehler: Wenn die Kennung leer ist oder Zeichen ausserhalb von
            Buchstaben, Ziffern, Bindestrich und Unterstrich enthaelt.
    """
    if not _MUSTER_RUN_ID.match(run_id):
        raise PfadFehler(
            f"Unzulaessige run_id: {run_id!r}. Erlaubt sind Buchstaben, Ziffern, "
            "Bindestrich und Unterstrich, hoechstens 64 Zeichen."
        )
    return run_id


def lauf_verzeichnis(config: Config, run_id: str, *, anlegen: bool = False) -> Path:
    """Gibt das Verzeichnis eines Laufs zurueck.

    Args:
        config: Geladene Konfiguration.
        run_id: Kennung des Laufs.
        anlegen: Legt das Verzeichnis samt Elternverzeichnissen an.

    Returns:
        ``data/runs/<run_id>`` als absoluten Pfad.

    Raises:
        PfadFehler: Bei einer unzulaessigen ``run_id``.
    """
    verzeichnis = config.pfade.runs / pruefe_run_id(run_id)
    if anlegen:
        verzeichnis.mkdir(parents=True, exist_ok=True)
    return verzeichnis


def artefakt_pfad(config: Config, run_id: str, artefakt: Artefakt) -> Path:
    """Gibt den Pfad eines Laufartefakts zurueck.

    Args:
        config: Geladene Konfiguration.
        run_id: Kennung des Laufs.
        artefakt: Gewuenschtes Artefakt.

    Returns:
        Den vollstaendigen Pfad der Artefaktdatei.
    """
    return lauf_verzeichnis(config, run_id) / artefakt.value


def clean_verzeichnis(config: Config, run_id: str, *, anlegen: bool = False) -> Path:
    """Gibt das Verzeichnis des sauberen Datensatzes eines Laufs zurueck.

    Args:
        config: Geladene Konfiguration.
        run_id: Kennung des Laufs.
        anlegen: Legt das Verzeichnis samt beider Schichten an.

    Returns:
        ``data/runs/<run_id>/clean`` als absoluten Pfad.
    """
    verzeichnis = lauf_verzeichnis(config, run_id) / _CLEAN
    if anlegen:
        for schicht in Schicht:
            (verzeichnis / schicht.value).mkdir(parents=True, exist_ok=True)
    return verzeichnis


def raten_token(fehlerrate: float) -> str:
    """Kodiert eine Fehlerrate als vierstellige Basispunktangabe.

    Args:
        fehlerrate: Fehlerrate als Anteil, zum Beispiel ``0.02``.

    Returns:
        Das Token, zum Beispiel ``r0200`` fuer zwei Prozent.

    Raises:
        PfadFehler: Wenn die Rate nicht positiv ist oder mehr als vier Stellen
            in Basispunkten braucht.
    """
    if fehlerrate <= 0:
        raise PfadFehler(f"Die Fehlerrate muss groesser als null sein, war {fehlerrate}")
    basispunkte = round(fehlerrate * _BASISPUNKTE)
    if basispunkte >= _BASISPUNKTE * 10:
        raise PfadFehler(
            f"Die Fehlerrate {fehlerrate} ist in vier Stellen Basispunkten nicht darstellbar"
        )
    return f"r{basispunkte:0{_RATEN_STELLEN}d}"


def wiederholungs_token(wiederholung: int) -> str:
    """Kodiert eine Wiederholungsnummer zweistellig.

    Args:
        wiederholung: Nummer der Wiederholung.

    Returns:
        Das Token, zum Beispiel ``w07``.

    Raises:
        PfadFehler: Wenn die Nummer negativ ist.
    """
    if wiederholung < 0:
        raise PfadFehler(f"Die Wiederholung muss nicht negativ sein, war {wiederholung}")
    return f"w{wiederholung:0{_WIEDERHOLUNGS_STELLEN}d}"


def _pruefe_segment(wert: str, name: str) -> str:
    """Prueft ein Pfadsegment auf Verwendbarkeit als Verzeichnisname."""
    if not _MUSTER_SEGMENT.match(wert):
        raise PfadFehler(
            f"Unzulaessiger Wert fuer {name}: {wert!r}. Erlaubt sind Buchstaben, Ziffern, "
            "Bindestrich und Unterstrich, hoechstens 32 Zeichen."
        )
    return wert


def experiment_run_id(
    serie: str, design: str, klasse: str, fehlerrate: float, wiederholung: int
) -> str:
    """Bildet die Lauf-Kennung eines Experimentlaufs aus seinen Faktorstufen.

    Die Kennung traegt **alle** Faktorstufen als ein Token, zum Beispiel
    ``s01_A_F3_r0200_w07``. Damit bleibt Architekturregel A2 woertlich erfuellt:
    Der Lauf ist allein aus ``run_id`` und Konfiguration reproduzierbar.

    Args:
        serie: Name der Versuchsserie.
        design: Kennbuchstabe des Varianzdesigns.
        klasse: Fehlerklasse oder :data:`MISCHMODUS`.
        fehlerrate: Fehlerrate als Anteil.
        wiederholung: Nummer der Wiederholung.

    Returns:
        Die Kennung.

    Raises:
        PfadFehler: Wenn ein Bestandteil nicht als Verzeichnisname taugt.
    """
    kennung = "_".join(
        (
            _pruefe_segment(serie, "serie"),
            _pruefe_segment(design, "design"),
            _pruefe_segment(klasse, "klasse"),
            raten_token(fehlerrate),
            wiederholungs_token(wiederholung),
        )
    )
    return pruefe_run_id(kennung)


def experiment_verzeichnis(  # noqa: PLR0913, PLR0917 - die Faktorstufen bilden den Pfad
    config: Config,
    serie: str,
    design: str,
    klasse: str,
    fehlerrate: float,
    wiederholung: int,
    *,
    anlegen: bool = False,
) -> Path:
    """Gibt das Verzeichnis eines Experimentlaufs zurueck.

    Das Schema ist ``data/runs/<serie>/<design>/<klasse>/<rate>/<wdh>/``. Ein
    Pfad, der nur die Fehlerrate kodierte, liesse die tausenden Laeufe der
    Phase 6 einander ueberschreiben. Ad-hoc-Laeufe ohne Faktorstufen behalten die
    flache Form :func:`lauf_verzeichnis`.

    Args:
        config: Geladene Konfiguration.
        serie: Name der Versuchsserie.
        design: Kennbuchstabe des Varianzdesigns.
        klasse: Fehlerklasse oder :data:`MISCHMODUS`.
        fehlerrate: Fehlerrate als Anteil.
        wiederholung: Nummer der Wiederholung.
        anlegen: Legt das Verzeichnis samt Elternverzeichnissen an.

    Returns:
        Das Laufverzeichnis als absoluten Pfad.

    Raises:
        PfadFehler: Wenn ein Bestandteil nicht als Verzeichnisname taugt.
    """
    experiment_run_id(serie, design, klasse, fehlerrate, wiederholung)
    verzeichnis = (
        config.pfade.runs
        / serie
        / design
        / klasse
        / raten_token(fehlerrate)
        / wiederholungs_token(wiederholung)
    )
    if anlegen:
        verzeichnis.mkdir(parents=True, exist_ok=True)
    return verzeichnis


def entitaet_pfad(config: Config, run_id: str, schicht: Schicht, entitaet: str) -> Path:
    """Gibt den Pfad einer Entitaetsdatei des sauberen Datensatzes zurueck.

    Args:
        config: Geladene Konfiguration.
        run_id: Kennung des Laufs.
        schicht: Typisierte Schicht oder Rohschicht.
        entitaet: Name der Entitaet, zum Beispiel ``"angebot"``.

    Returns:
        ``data/runs/<run_id>/clean/<schicht>/<entitaet>.parquet``.
    """
    return clean_verzeichnis(config, run_id) / schicht.value / f"{entitaet}.parquet"


def sha256_bytes(daten: bytes) -> str:
    """Berechnet den SHA-256-Hashwert eines Bytepuffers.

    Args:
        daten: Zu hashende Bytes.

    Returns:
        Den Hashwert als Hexadezimalzeichenkette.
    """
    return hashlib.sha256(daten).hexdigest()


def sha256_datei(pfad: Path) -> str:
    """Berechnet den SHA-256-Hashwert einer Datei.

    Args:
        pfad: Pfad der Datei.

    Returns:
        Den Hashwert als Hexadezimalzeichenkette.

    Raises:
        PfadFehler: Wenn die Datei nicht existiert.
    """
    if not pfad.is_file():
        raise PfadFehler(f"Datei nicht gefunden: {pfad}")
    hasher = hashlib.sha256()
    with pfad.open("rb") as datei:
        while block := datei.read(_BLOCKGROESSE):
            hasher.update(block)
    return hasher.hexdigest()


def sha256_verzeichnis(verzeichnis: Path, dateinamen: tuple[str, ...]) -> dict[str, str]:
    """Berechnet die Hashwerte mehrerer Dateien eines Verzeichnisses.

    Args:
        verzeichnis: Verzeichnis, in dem die Dateien liegen.
        dateinamen: Namen der zu hashenden Dateien.

    Returns:
        Eine nach Dateinamen sortierte Abbildung Name auf Hashwert. Die feste
        Reihenfolge ist Teil der Reproduzierbarkeit.

    Raises:
        PfadFehler: Wenn eine der Dateien fehlt.
    """
    return {name: sha256_datei(verzeichnis / name) for name in sorted(dateinamen)}


def sha256_dataframe(rahmen: pd.DataFrame) -> str:
    """Berechnet einen stabilen SHA-256-Hashwert eines Datenrahmens.

    Gehasht wird eine kanonische CSV-Darstellung: fester Trenner, feste
    Zeilenenden, fester Platzhalter fuer Fehlwerte und feste Gleitkommaformatierung.
    Spalten- und Zeilenreihenfolge gehen bewusst mit ein — zwei Datenrahmen mit
    denselben Werten in anderer Reihenfolge sind fuer die Reproduzierbarkeit
    nicht gleichwertig.

    ``Decimal``-Werte werden ueber ``str`` exakt dargestellt und verlieren dabei
    nichts.

    Args:
        rahmen: Zu hashender Datenrahmen.

    Returns:
        Den Hashwert als Hexadezimalzeichenkette.

    Note:
        Der Wert haengt an der gepinnten pandas-Version. Er dient dem Vergleich
        zweier Laeufe derselben Umgebung, nicht als versionsuebergreifende
        Pruefsumme.
    """
    puffer = io.StringIO()
    rahmen.to_csv(
        puffer,
        index=True,
        sep=";",
        lineterminator="\n",
        na_rep="<NA>",
        float_format="%.12g",
        encoding="utf-8",
    )
    return sha256_bytes(puffer.getvalue().encode("utf-8"))
