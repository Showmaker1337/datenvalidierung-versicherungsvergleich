"""Verfaelscht einen sauberen Datensatz kontrolliert und schreibt den Ground Truth.

Aufruf::

    python scripts/inject.py --serie s01 --design A --klasse F3 --rate 0.02 --wdh 7
    python scripts/inject.py --serie s01 --design A --klasse mix --rate 0.02 --wdh 1
    python scripts/inject.py --serie v01 --design A --modus variante --variante F7-c --wdh 0
    python scripts/inject.py --serie probe --design A --klasse F6 --rate 0.05 --wdh 0 \
        --n-anfragen 500 --behalten

Zwei Modi, zwei Teilversuche
----------------------------

``--modus klasse`` (Standard) ist der **faktorielle Plan**. Injiziert wird eine
ganze Fehlerklasse — oder im Mischmodus alle —, und das Kontingent wird
proportional zum Universum jeder Variante zugeteilt. Der Anteil jeder Variante ist
dadurch ueber alle Ratenstufen konstant; nur so bleibt Faktor UV2 (Fehlerrate)
interpretierbar (siehe :mod:`src.injector.auswahl`).

``--modus variante`` ist der Teilversuch **Variantencharakterisierung**. Injiziert
wird genau eine Variante, und zwar bis an ihr Universum heran. Der Grund: Die
proportionale Zuteilung gibt knappen Varianten wie F7-c im faktoriellen Plan nur
einstellige Fallzahlen. Fuer die klassenweise Auswertung ist das richtig, fuer den
Recall **je Variante** — den empirischen Beleg gegen den Zirkularitaetsvorwurf —
zu wenig. Diese Laeufe gehoeren **nicht** in den faktoriellen Plan.

Pfadschema
----------

Experimentlaeufe landen unter
``data/runs/<serie>/<design>/<klasse>/<rate>/<wdh>/``. In Phase 6 variieren
Fehlerklasse, Fehlerrate, Wiederholung und Varianzdesign; ein Pfad, der nur die
Fehlerrate kodierte, liesse tausende Laeufe einander ueberschreiben. Im
Variantenmodus tritt die Variantenkennung an die Stelle der Klasse, also etwa
``data/runs/v01/A/F7-c/r10000/w00/``.

Die ``run_id`` traegt dieselbe Information als ein Token, etwa
``s01_A_F3_r0200_w07``. Damit bleibt Architekturregel A2 woertlich erfuellt: Der
Lauf ist allein aus ``run_id`` und Konfiguration reproduzierbar. Ad-hoc-Laeufe
ohne Faktorstufen — etwa der Clean-Baseline-Lauf — behalten die flache Form
``data/runs/<run_id>/``.

``--max-fehler`` geht **nicht** in die ``run_id`` ein. Wer die Obergrenze
innerhalb einer Serie variiert, muss deshalb ``--serie`` oder ``--wdh`` mit
variieren, sonst ueberschreiben sich zwei Laeufe. Der Wert steht in ``config.yaml``
und ``manifest.json`` des Laufs.

Was aufbewahrt wird
-------------------

``df_raw_dirty`` wird **nicht** dauerhaft gespeichert. Bei mehreren tausend
Laeufen zu je rund 60.000 Zeilen entstuenden zweistellige Gigabyte, und der
verfaelschte Datensatz ist aus ``seed_basis`` und ``seed_inject`` jederzeit exakt
reproduzierbar. Dauerhaft abgelegt werden ``error_log.parquet``,
``error_log_records.parquet``, ``config.yaml`` und ``manifest.json``; spaeter
kommen ``detections`` und ``metrics.json`` hinzu.

Das Flag ``--behalten`` legt die verfaelschten Daten zusaetzlich je Entitaet unter
``dirty/`` ab. Standard ist aus. Der Gegencheck braucht die Dateien nicht — er
laeuft im selben Prozess auf den Datenrahmen im Speicher.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ermoeglicht den Aufruf "python scripts/inject.py" ohne editierbare
# Installation. Muss vor den Projektimporten stehen.
_WURZEL = Path(__file__).resolve().parents[1]
if str(_WURZEL) not in sys.path:
    sys.path.insert(0, str(_WURZEL))

import argparse  # noqa: E402
import dataclasses  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from typing import TYPE_CHECKING, Any, Final  # noqa: E402

import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from src.common.config import als_dict as konfiguration_als_dict  # noqa: E402
from src.common.config import lade_config  # noqa: E402
from src.common.pfade import (  # noqa: E402
    DIRTY,
    MISCHMODUS,
    Artefakt,
    Schicht,
    entitaet_pfad,
    experiment_run_id,
    experiment_verzeichnis,
    sha256_dataframe,
)
from src.common.seeding import Strom, lauf_seed, wurzel_seeds  # noqa: E402
from src.common.serialisierung import ENTITAETEN, serialisiere  # noqa: E402
from src.generator.pipeline import erzeuge_datensatz  # noqa: E402
from src.injector import Fehlerklasse, InjektionsFehler, injiziere  # noqa: E402
from src.injector.varianten import ALLE_VARIANTEN, variante  # noqa: E402
from src.verify import pruefe_ground_truth, schreibe_bericht  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence

    from numpy.random import SeedSequence

    from src.common.config import Config
    from src.injector import Injektionsergebnis

__all__ = ["main"]

#: Gewichte des praxisnahen Mischmodus (spec/03, Abschnitt 3).
#:
#: Dubletten und Unvollstaendigkeit dominieren die Branchenempirie.
MISCHGEWICHTE: Final[Mapping[str, float]] = {
    "F1": 0.30,
    "F6": 0.30,
    "F5": 0.15,
    "F3": 0.10,
    "F2": 0.05,
    "F8": 0.05,
    "F7": 0.03,
    "F4": 0.02,
}

#: Die beiden Laufmodi.
MODUS_KLASSE: Final[str] = "klasse"
MODUS_VARIANTE: Final[str] = "variante"

#: Fehlerrate des Variantenmodus, wenn keine angegeben wurde: das ganze Universum.
_RATE_ERSCHOEPFEND: Final[float] = 1.0

#: Dateiname des Gegencheckberichts unter ``results/``.
_GEGENCHECK: Final[str] = "ground_truth_check.json"

#: Zahl der Bytes, mit denen ein Name als Faktorstufe kodiert wird.
_NAMENSBYTES: Final[int] = 8

#: Basispunkte einer Rate von 100 Prozent — Kodierung der Rate als Faktorstufe.
_BASISPUNKTE: Final[int] = 10000


def _namensfaktor(name: str) -> int:
    """Kodiert einen Namen reproduzierbar als nicht negative ganze Zahl.

    ``hash()`` waere hier falsch: Python streut Zeichenketten je Prozess anders,
    zwei Laeufe derselben Serie bekaemen verschiedene Seeds (Architekturregel A2).
    SHA-256 ist prozessuebergreifend stabil.

    Args:
        name: Zu kodierender Name, etwa der Serien- oder der Designname.

    Returns:
        Die Kodierung als ganze Zahl.
    """
    verdichtet = hashlib.sha256(name.encode("utf-8")).digest()[:_NAMENSBYTES]
    return int.from_bytes(verdichtet, "big")


def _gewichte(klasse: str) -> dict[str, float]:
    """Bestimmt die Klassengewichte eines Laufs.

    Args:
        klasse: Fehlerklasse oder ``mix``.

    Returns:
        Die Gewichte je Fehlerklasse.

    Raises:
        SystemExit: Bei einer unbekannten Fehlerklasse.
    """
    if klasse == MISCHMODUS:
        return dict(MISCHGEWICHTE)
    bekannt = [eintrag.value for eintrag in Fehlerklasse]
    if klasse not in bekannt:
        raise SystemExit(
            f"Unbekannte Fehlerklasse: {klasse!r}. Bekannt sind: {bekannt} und {MISCHMODUS!r}."
        )
    return {klasse: 1.0}


def _pruefe_modus(optionen: argparse.Namespace) -> None:
    """Prueft die Modusangaben und ergaenzt die abgeleiteten Werte.

    Im Variantenmodus stehen Fehlerklasse und Vorgabewert der Fehlerrate fest,
    sobald die Variante bekannt ist. Beides wird hier in die Optionen
    geschrieben, damit der weitere Ablauf beide Modi gleich behandelt.

    Raises:
        SystemExit: Wenn Modus und Angaben nicht zusammenpassen.
    """
    if optionen.modus == MODUS_VARIANTE:
        if optionen.variante is None:
            raise SystemExit("--modus variante verlangt --variante, etwa --variante F7-c")
        if optionen.klasse is not None:
            raise SystemExit(
                "--klasse und --modus variante schliessen einander aus; die Klasse "
                "ergibt sich aus der Variante"
            )
        try:
            eintrag = variante(optionen.variante)
        except InjektionsFehler as fehler:
            bekannt = [wert.variante_id for wert in ALLE_VARIANTEN]
            raise SystemExit(f"{fehler}\nBekannt sind: {bekannt}") from fehler
        optionen.klasse = eintrag.fehlerklasse.value
        optionen.segment = optionen.variante
        if optionen.rate is None:
            optionen.rate = _RATE_ERSCHOEPFEND
        return

    if optionen.variante is not None:
        raise SystemExit("--variante gilt nur mit --modus variante")
    if optionen.klasse is None:
        raise SystemExit("--modus klasse verlangt --klasse, etwa --klasse F3")
    if optionen.rate is None:
        raise SystemExit("--modus klasse verlangt --rate, etwa --rate 0.02")
    optionen.segment = optionen.klasse


def basis_seed(config: Config, basis_index: int) -> SeedSequence:
    """Waehlt den Basisstrom eines Laufs.

    Der Hauptversuch haelt den Basisdatensatz fest und variiert nur die
    Injektion; der Teilversuch T5 macht es umgekehrt und braucht dafuer mehrere
    Basisdatensaetze. Beide Faelle laufen ueber diese Funktion.

    ``basis_index = 0`` ist der **kanonische** Basisdatensatz aus
    ``wurzel_seeds(master_seed).basis`` — derselbe, den ``scripts/generate.py``
    ohne weitere Angabe erzeugt. Er bleibt damit bitgleich zu allen bisherigen
    Laeufen; die Erweiterung aendert keinen einzigen davon.

    Args:
        config: Geladene Konfiguration.
        basis_index: Nummer des Basisdatensatzes; ``0`` ist der kanonische.

    Returns:
        Die ``SeedSequence`` des Basisstroms.

    Raises:
        SystemExit: Bei einem negativen Index.
    """
    if basis_index < 0:
        raise SystemExit(f"--basis-index muss nicht negativ sein, war {basis_index}")
    if basis_index == 0:
        return wurzel_seeds(config.master_seed).basis
    return lauf_seed(config.master_seed, Strom.BASIS, basis_index)


def _lade_clean(
    config: Config, clean_run: str | None, *, basis_index: int = 0
) -> tuple[dict[str, pd.DataFrame], str]:
    """Beschafft die Rohschicht des sauberen Datensatzes.

    Ohne ``--clean-run`` wird sie im selben Prozess aus dem Basisstrom erzeugt.
    Das ist keine Notloesung, sondern die genauere Variante: Der saubere Datensatz
    haengt allein an ``master_seed``, ``basis_index`` und Konfiguration und muss
    deshalb nicht zwischengespeichert werden.

    Args:
        config: Geladene Konfiguration.
        clean_run: Kennung eines bereits erzeugten Laufs, oder ``None``.
        basis_index: Nummer des Basisdatensatzes; ``0`` ist der kanonische.

    Returns:
        Die sieben Datenrahmen der Rohschicht und die Herkunftsangabe fuer das
        Manifest.

    Raises:
        SystemExit: Wenn eine Entitaetsdatei des angegebenen Laufs fehlt, oder
            wenn ein Basisdatensatz ungleich null zusammen mit ``--clean-run``
            angefordert wird — die beiden Angaben widersprechen einander.
    """
    if clean_run is None:
        typisiert = erzeuge_datensatz(config, basis_seed(config, basis_index))
        herkunft = "erzeugt" if basis_index == 0 else f"erzeugt (basis_index={basis_index})"
        return {name: serialisiere(typisiert[name]) for name in ENTITAETEN}, herkunft

    if basis_index != 0:
        raise SystemExit(
            "--basis-index und --clean-run schliessen einander aus: Der gespeicherte Lauf "
            "traegt seinen eigenen Basisdatensatz."
        )

    daten: dict[str, pd.DataFrame] = {}
    for name in ENTITAETEN:
        pfad = entitaet_pfad(config, clean_run, Schicht.RAW, name)
        if not pfad.is_file():
            raise SystemExit(
                f"Rohschicht des Laufs {clean_run!r} unvollstaendig: {pfad} fehlt. "
                "Zuerst 'python scripts/generate.py --run-id <id>' ausfuehren."
            )
        daten[name] = pd.read_parquet(pfad).astype("string")
    return daten, f"data/runs/{clean_run}/clean/raw"


def injektions_index(optionen: argparse.Namespace) -> int:
    """Gibt die Nummer zurueck, die in ``seed_inject`` und ``seed_modell`` eingeht.

    Im Regelfall ist das die Wiederholungsnummer: Der Basisdatensatz steht fest,
    variiert wird die Injektion. Der Teilversuch T5 (Datenvarianz) dreht das um —
    dort variiert der Basisdatensatz ueber ``--basis-index``, und der
    Injektionsstrom muss **fest** bleiben, sonst maesse T5 die Summe aus beiden
    Streuungen statt der Datenvarianz allein.

    ``None`` heisst "gleich der Wiederholung" und ist kein stiller Ersatzwert,
    sondern die ausdrueckliche Bedeutung des nicht gesetzten Schalters.

    Args:
        optionen: Ausgewertete Kommandozeile.

    Returns:
        Die Nummer.
    """
    if optionen.injektions_index is None:
        return int(optionen.wdh)
    return int(optionen.injektions_index)


def _seed_inject(config: Config, optionen: argparse.Namespace) -> SeedSequence:
    """Leitet den Injektionsstrom aus den Faktorstufen des Laufs ab.

    Alle Faktorstufen gehen ein — Serie, Varianzdesign, Fehlerklasse
    beziehungsweise Variante, Fehlerrate und Wiederholung. Damit ist der Lauf
    allein aus seiner ``run_id`` und der Konfiguration reproduzierbar, unabhaengig
    von Reihenfolge und Parallelitaet (Architekturregel A2).
    """
    return lauf_seed(
        config.master_seed,
        Strom.INJEKTION,
        _namensfaktor(optionen.serie),
        _namensfaktor(optionen.design),
        _namensfaktor(optionen.segment),
        round(optionen.rate * _BASISPUNKTE),
        injektions_index(optionen),
    )


def _lauf_angaben(optionen: argparse.Namespace, ergebnis: Injektionsergebnis) -> dict[str, Any]:
    """Stellt die Faktorstufen und Zuteilungsangaben eines Laufs zusammen."""
    return {
        "modus": optionen.modus,
        "serie": optionen.serie,
        "design": optionen.design,
        "klasse": optionen.klasse,
        "variante": optionen.variante,
        "pfadsegment": optionen.segment,
        "fehlerrate": optionen.rate,
        "wiederholung": optionen.wdh,
        "basis_index": optionen.basis_index,
        "injektions_index": injektions_index(optionen),
        "max_fehler": optionen.max_fehler,
        "klassen_gewichte": dict(sorted(_gewichte(optionen.klasse).items())),
        "seeds": dict(sorted(ergebnis.seeds.items())),
    }


def _manifest(  # noqa: PLR0913 - das Manifest fuehrt alle Angaben des Laufs
    *,
    optionen: argparse.Namespace,
    config: Config,
    ergebnis: Injektionsergebnis,
    herkunft: str,
    zeilen: Mapping[str, int],
    hashes_clean: Mapping[str, str],
    hashes_dirty: Mapping[str, str],
    gegencheck_sauber: bool,
) -> dict[str, Any]:
    """Stellt das Manifest des Laufs zusammen.

    Bewusst **ohne Zeitstempel und ohne Laufzeit**: Derselbe Lauf soll byteweise
    dasselbe Manifest erzeugen (Architekturregel A2).

    Zwei Zellzahlen stehen getrennt darin. ``zellen_fehlerhaft`` sind die
    Traegerzellen — auf sie bezieht sich die Fehlerrate. ``zellen_geaendert_gesamt``
    zaehlt zusaetzlich die nur nachgefuehrten Rangzellen. Bei den
    Skalierungsklassen liegt die zweite Zahl rund die Haelfte hoeher: Der Datensatz
    ist dort an mehr Stellen veraendert, als die Fehlerrate nominell angibt.
    """
    return {
        "run_id": ergebnis.run_id,
        "erzeugt_von": "scripts/inject.py",
        "faktorstufen": _lauf_angaben(optionen, ergebnis),
        "seeds": dict(sorted(ergebnis.seeds.items())),
        "clean_datensatz": {"herkunft": herkunft, "zeilen": dict(sorted(zeilen.items()))},
        "zelluniversum": dict(sorted(ergebnis.universum.items())),
        "einheit_je_klasse": dict(sorted(ergebnis.einheit_je_klasse.items())),
        "angefordert_je_klasse": dict(sorted(ergebnis.ziel_je_klasse.items())),
        "injiziert_je_klasse": dict(sorted(ergebnis.fehler_je_klasse.items())),
        "zuteilung_je_variante": {
            kennung: {
                "universum": groesse,
                "anteil": ergebnis.anteil_je_variante[kennung],
                "angefordert": ergebnis.quote_je_variante[kennung],
                "injiziert": ergebnis.fehler_je_variante[kennung],
            }
            for kennung, groesse in sorted(ergebnis.universum_je_variante.items())
        },
        "granularitaetsabweichung": ergebnis.granularitaetsabweichung,
        "zellen_fehlerhaft": ergebnis.zellen_fehlerhaft,
        "zellen_geaendert_gesamt": ergebnis.zellen_geaendert_gesamt,
        "mitgezogene_zellen": ergebnis.mitgezogene_zellen,
        "logzeilen": {
            "error_log": len(ergebnis.error_log),
            "error_log_records": len(ergebnis.error_log_records),
        },
        "sha256": {
            "df_clean": dict(sorted(hashes_clean.items())),
            "df_dirty": dict(sorted(hashes_dirty.items())),
        },
        "gegencheck_sauber": gegencheck_sauber,
        "konfiguration": konfiguration_als_dict(config),
    }


def _schreibe_json(pfad: Path, inhalt: Mapping[str, Any]) -> None:
    """Schreibt eine JSON-Datei mit fester Formatierung."""
    pfad.write_text(
        json.dumps(inhalt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _argumente() -> argparse.ArgumentParser:
    """Baut den Argumentparser des Skripts."""
    parser = argparse.ArgumentParser(
        description="Verfaelscht einen sauberen Datensatz kontrolliert und protokolliert alles."
    )
    parser.add_argument("--config", type=Path, default=None, help="Pfad zur Konfigurationsdatei")
    parser.add_argument("--serie", required=True, help="Name der Versuchsserie, etwa s01")
    parser.add_argument("--design", required=True, help="Kennbuchstabe des Varianzdesigns")
    parser.add_argument(
        "--modus",
        default=MODUS_KLASSE,
        choices=(MODUS_KLASSE, MODUS_VARIANTE),
        help="klasse: faktorieller Plan. variante: Teilversuch Variantencharakterisierung",
    )
    parser.add_argument(
        "--klasse",
        default=None,
        help=f"Fehlerklasse F1 bis F8, HO1, HO2 oder {MISCHMODUS!r} fuer den Mischmodus",
    )
    parser.add_argument(
        "--variante",
        default=None,
        help="Injektionsvariante, etwa F7-c; nur mit --modus variante",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=None,
        help="Fehlerrate als Anteil; im Variantenmodus standardmaessig 1.0",
    )
    parser.add_argument("--wdh", type=int, required=True, help="Nummer der Wiederholung")
    parser.add_argument(
        "--max-fehler",
        type=int,
        default=None,
        dest="max_fehler",
        help="Absolute Obergrenze der Verfaelschungen; geht nicht in die run_id ein",
    )
    parser.add_argument(
        "--clean-run",
        default=None,
        help="Kennung eines erzeugten Laufs; ohne Angabe wird der saubere Datensatz erzeugt",
    )
    parser.add_argument(
        "--basis-index",
        type=int,
        default=0,
        dest="basis_index",
        help=(
            "Nummer des Basisdatensatzes; 0 ist der kanonische. Nur der Teilversuch T5 "
            "(Datenvarianz) setzt ihn ungleich null. Geht nicht in die run_id ein"
        ),
    )
    parser.add_argument(
        "--injektions-index",
        type=int,
        default=None,
        dest="injektions_index",
        help=(
            "Nummer, die in seed_inject eingeht; ohne Angabe die Wiederholung. Nur der "
            "Teilversuch T5 (Datenvarianz) setzt sie fest, waehrend --basis-index variiert"
        ),
    )
    parser.add_argument("--seed", type=int, default=None, help="Master-Seed uebersteuern")
    parser.add_argument(
        "--n-anfragen", type=int, default=None, help="Anzahl der Anfragen uebersteuern"
    )
    parser.add_argument(
        "--behalten",
        action="store_true",
        help="Legt df_raw_dirty zusaetzlich je Entitaet unter dirty/ ab",
    )
    parser.add_argument("--still", action="store_true", help="Keine Fortschrittsausgabe")
    return parser


def main(argumente: Sequence[str] | None = None) -> int:
    """Einstiegspunkt des Skripts.

    Args:
        argumente: Kommandozeilenargumente; ``None`` nimmt ``sys.argv``.

    Returns:
        ``0``, wenn der Gegencheck sauber durchlief, sonst ``1``. Eine Abweichung
        im Ground Truth ist ein Abbruchgrund, kein Hinweis: Auf ihr beruht jede
        spaeter berichtete Kennzahl.
    """
    optionen = _argumente().parse_args(argumente)
    _pruefe_modus(optionen)

    config = lade_config(optionen.config)
    if optionen.seed is not None:
        config = dataclasses.replace(config, master_seed=optionen.seed)
    if optionen.n_anfragen is not None:
        config = dataclasses.replace(config, n_anfragen=optionen.n_anfragen)

    run_id = experiment_run_id(
        optionen.serie, optionen.design, optionen.segment, optionen.rate, optionen.wdh
    )
    ziel = experiment_verzeichnis(
        config,
        optionen.serie,
        optionen.design,
        optionen.segment,
        optionen.rate,
        optionen.wdh,
        anlegen=True,
    )
    if not optionen.still:
        print(f"Injektion (run_id={run_id}, modus={optionen.modus}, rate={optionen.rate})")

    beginn = time.perf_counter()
    daten_clean, herkunft = _lade_clean(
        config, optionen.clean_run, basis_index=optionen.basis_index
    )
    ergebnis = injiziere(
        daten_clean,
        optionen.rate,
        _gewichte(optionen.klasse),
        _seed_inject(config, optionen),
        run_id,
        config=config,
        nur_varianten=(optionen.variante,) if optionen.variante is not None else None,
        hoechstzahl=optionen.max_fehler,
    )
    dauer = time.perf_counter() - beginn

    bericht = pruefe_ground_truth(
        daten_clean, ergebnis.df_raw_dirty, ergebnis.error_log, ergebnis.error_log_records
    )

    hashes_clean = {name: sha256_dataframe(daten_clean[name]) for name in ENTITAETEN}
    hashes_dirty = {name: sha256_dataframe(ergebnis.df_raw_dirty[name]) for name in ENTITAETEN}

    ergebnis.error_log.to_parquet(ziel / Artefakt.ERROR_LOG.value, index=False)
    ergebnis.error_log_records.to_parquet(ziel / Artefakt.ERROR_LOG_RECORDS.value, index=False)
    (ziel / Artefakt.CONFIG.value).write_text(
        yaml.safe_dump(
            {
                "lauf": {
                    "run_id": run_id,
                    **_lauf_angaben(optionen, ergebnis),
                    "clean_datensatz": herkunft,
                },
                "konfiguration": konfiguration_als_dict(config),
            },
            allow_unicode=True,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )
    _schreibe_json(
        ziel / Artefakt.MANIFEST.value,
        _manifest(
            optionen=optionen,
            config=config,
            ergebnis=ergebnis,
            herkunft=herkunft,
            zeilen={name: len(daten_clean[name]) for name in ENTITAETEN},
            hashes_clean=hashes_clean,
            hashes_dirty=hashes_dirty,
            gegencheck_sauber=bericht.sauber,
        ),
    )

    if optionen.behalten:
        verzeichnis = ziel / DIRTY
        verzeichnis.mkdir(parents=True, exist_ok=True)
        for name in ENTITAETEN:
            ergebnis.df_raw_dirty[name].to_parquet(verzeichnis / f"{name}.parquet", index=False)

    berichtspfad = schreibe_bericht(
        bericht,
        config.pfade.results / _GEGENCHECK,
        run_id=run_id,
        zusatz={
            "modus": optionen.modus,
            "klasse": optionen.klasse,
            "variante": optionen.variante,
            "fehlerrate": optionen.rate,
            "zelluniversum": dict(sorted(ergebnis.universum.items())),
            "zellen_fehlerhaft": ergebnis.zellen_fehlerhaft,
            "zellen_geaendert_gesamt": ergebnis.zellen_geaendert_gesamt,
        },
    )

    if not optionen.still:
        _zeige(ergebnis, dauer, sauber=bericht.sauber)
        print(f"\nArtefakte in {ziel}")
        print(f"Gegencheck in {berichtspfad}")
    return 0 if bericht.sauber else 1


def _zeige(ergebnis: Injektionsergebnis, dauer: float, *, sauber: bool) -> None:
    """Gibt die Kernzahlen des Laufs aus."""
    for klasse, universum in sorted(ergebnis.universum.items()):
        einheit = ergebnis.einheit_je_klasse[klasse]
        print(
            f"  {klasse:<4} Universum {universum:>8} {einheit}n, "
            f"injiziert {ergebnis.fehler_je_klasse.get(klasse, 0):>6}"
        )
    print(f"  Zellen fehlerhaft     {ergebnis.zellen_fehlerhaft}")
    print(f"  Zellen geaendert      {ergebnis.zellen_geaendert_gesamt}")
    print(f"  davon mitgezogen      {ergebnis.mitgezogene_zellen}")
    print(f"  Logzeilen satzbasiert {len(ergebnis.error_log_records)}")
    print(f"  Granularitaetsabw.    {ergebnis.granularitaetsabweichung}")
    print(f"  Laufzeit              {dauer:.1f} s")

    ohne = sorted(
        kennung for kennung, wert in ergebnis.quote_je_variante.items() if wert == 0
    )
    if ohne:
        print(
            f"\nOhne Kontingent bei dieser Rate: {ohne}. Das ist die Kehrseite konstanter "
            "Variantenanteile. Fuer den Recall dieser Varianten den Teilversuch fahren: "
            "--modus variante --variante <kennung>."
        )
    print("\nGegencheck: " + ("ohne Abweichung." if sauber else "ABWEICHUNG — siehe Bericht."))


if __name__ == "__main__":
    raise SystemExit(main())
