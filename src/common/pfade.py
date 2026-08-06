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
    "REFERENZ_DATEIEN",
    "Artefakt",
    "PfadFehler",
    "artefakt_pfad",
    "lauf_verzeichnis",
    "pruefe_run_id",
    "sha256_bytes",
    "sha256_dataframe",
    "sha256_datei",
    "sha256_verzeichnis",
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
