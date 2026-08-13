"""Bewertet den Prototyp und die drei Baselines auf einem Experimentlauf.

Aufruf::

    python scripts/evaluate.py --serie s01 --design A --klasse F3 --rate 0.02 --wdh 7
    python scripts/evaluate.py --serie v01 --design A --modus variante --variante F7-c --wdh 0
    python scripts/evaluate.py --serie s01 --design A --klasse F3 --rate 0.02 --wdh 7 \
        --verfahren prototyp B0 --kein-speicher

Das Skript setzt einen Lauf voraus, den ``scripts/inject.py`` mit **denselben**
Faktorstufen bereits erzeugt hat. Es liest dessen ``manifest.json`` und die beiden
Ground-Truth-Logs, stellt den verfaelschten Datensatz wieder her, laesst die
Verfahren darauf laufen und schreibt ``metrics.json`` in das Laufverzeichnis sowie
``results/metrics_long.parquet`` und ``results/b3_framework.json``.

Der verfaelschte Datensatz wird wiederhergestellt, nicht gelesen
----------------------------------------------------------------

``df_raw_dirty`` wird regulaer nicht gespeichert (CLAUDE.md, Abschnitt 3): Bei
mehreren tausend Laeufen zu je rund 60.000 Zeilen entstuenden zweistellige
Gigabyte. Das Skript erzeugt den sauberen Datensatz deshalb neu und wiederholt die
Injektion mit denselben Seeds und denselben Faktorstufen. Es darf ``src.injector``
importieren — ``scripts/`` ist die aeusserste Schicht, und ``scripts/inject.py``
tut dasselbe. Die Architekturregel A1 und der Phasenkontrakt verbieten den Import
in ``src/evaluation``, nicht hier.

Der Reproduzierbarkeitsnachweis ist ein Abbruchgrund
-----------------------------------------------------

Vor jeder Kennzahl werden die SHA-256-Werte des wiederhergestellten ``df_clean``
und ``df_dirty`` gegen das ``manifest.json`` des Laufs geprueft. Weicht **ein**
Wert ab, bricht das Skript ab: Der Ground Truth beschreibt dann einen anderen
Datensatz als den, der gerade bewertet wird, und jede Precision waere auf zwei
verschiedene Datensaetze bezogen. Der Abgleich ist ein Nebenprodukt der
Wiederherstellung und belegt zugleich Architekturregel A2 fuer jeden einzelnen
Lauf; er steht deshalb auch in ``metrics.json`` und gehoert in den Anhang.

Die Seeds werden nicht neu erfunden
------------------------------------

Der Injektionsstrom entsteht ueber :func:`scripts.inject._seed_inject`, der
Modellstrom von B2 mit **denselben** Faktoren ueber
:data:`~src.common.seeding.Strom.MODELL`. Die Kodierung eines Namens als
Faktorstufe (:func:`scripts.inject._namensfaktor`) wird importiert und nicht
kopiert: Zwei Kopien derselben Kodierung waeren ein A2-Risiko, das erst auffiele,
wenn zwei Laeufe derselben Serie verschiedene Datensaetze ergaeben. Ein Skript
darf ein anderes Skript importieren.

Was geschrieben wird
--------------------

``<laufverzeichnis>/metrics.json``
    Die vollstaendige, verschachtelte Auswertung dieses Laufs.
``<laufverzeichnis>/detections_<verfahren>.parquet``
    Die Rohmeldungen je Verfahren, zum Nachsehen. Sie entstehen durch einen
    zweiten ``erkenne``-Aufruf **nach** der Messung — der Prototyp und B2
    beantworten ihn aus ihrem Zwischenspeicher, B0 und B3 laufen dafuer ein
    zweites Mal. Die gemessene Laufzeit bleibt davon unberuehrt; wem der zweite
    Lauf in Phase 6 zu teuer ist, schaltet ihn mit ``--ohne-detections`` ab.
``results/metrics_long.parquet``
    Das laufuebergreifende Langformat; wird fortgeschrieben, nicht ueberschrieben.
``results/b3_framework.json``
    Die vier Kennzahlen des B3-Vergleichs: Anteil ausdrueckbarer Regeln,
    Codezeilen je Regel, Laufzeit und Diagnoseguete.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ermoeglicht den Aufruf "python scripts/evaluate.py" ohne editierbare
# Installation. Muss vor den Projektimporten stehen.
_WURZEL = Path(__file__).resolve().parents[1]
if str(_WURZEL) not in sys.path:
    sys.path.insert(0, str(_WURZEL))

import argparse  # noqa: E402
import dataclasses  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from typing import TYPE_CHECKING, Any, Final  # noqa: E402

import pandas as pd  # noqa: E402

from scripts.inject import (  # noqa: E402
    _BASISPUNKTE,
    MODUS_KLASSE,
    MODUS_VARIANTE,
    _gewichte,
    _lade_clean,
    _namensfaktor,
    _pruefe_modus,
    _schreibe_json,
    _seed_inject,
    injektions_index,
)
from src.baselines import B0Schema, B3Framework, IsolationForestBaseline, Prototyp  # noqa: E402
from src.common.config import lade_config  # noqa: E402
from src.common.pfade import (  # noqa: E402
    Artefakt,
    experiment_run_id,
    experiment_verzeichnis,
    sha256_dataframe,
)
from src.common.seeding import Strom, lauf_seed  # noqa: E402
from src.common.serialisierung import ENTITAETEN  # noqa: E402
from src.evaluation.ground_truth import lade_ground_truth  # noqa: E402
from src.evaluation.langformat import (  # noqa: E402
    baue_langformat,
    baue_metrics,
    schreibe_langformat,
    schreibe_metrics,
)
from src.evaluation.modell import Ebene  # noqa: E402
from src.evaluation.pipeline import bewerte  # noqa: E402
from src.injector import injiziere  # noqa: E402
from src.rules.modell import baue_kontext  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Callable, Mapping, Sequence

    from numpy.random import SeedSequence

    from src.common.config import Config
    from src.evaluation.ground_truth import GroundTruth
    from src.evaluation.modell import Kontext, Verfahren, Verfahrensergebnis

__all__ = ["main"]

#: Die vier vergleichbaren Verfahren, in Berichtsreihenfolge.
VERFAHRENSNAMEN: Final[tuple[str, ...]] = ("prototyp", "B0", "B2", "B3")

#: Dateiname des B3-Berichts unter ``results/``.
_B3_BERICHT: Final[str] = "b3_framework.json"

#: Dateiname des laufuebergreifenden Langformats unter ``results/``.
_LANGFORMAT: Final[str] = "metrics_long.parquet"

#: Namensschema der abgelegten Rohmeldungen je Verfahren.
_DETECTIONS: Final[str] = "detections_{verfahren}.parquet"

#: Faktorstufen, die zwischen Kommandozeile und Manifest uebereinstimmen muessen.
_ABGEGLICHENE_STUFEN: Final[tuple[str, ...]] = (
    "serie",
    "design",
    "modus",
    "klasse",
    "variante",
    "wiederholung",
)


# ---------------------------------------------------------------------------
# Lauf einlesen und wiederherstellen
# ---------------------------------------------------------------------------


def _lies_manifest(ziel: Path, run_id: str) -> dict[str, Any]:
    """Liest das Manifest eines Experimentlaufs.

    Args:
        ziel: Laufverzeichnis.
        run_id: Kennung des Laufs.

    Returns:
        Den Inhalt des Manifests.

    Raises:
        SystemExit: Wenn das Manifest oder eines der beiden Ground-Truth-Logs
            fehlt. Die Meldung nennt den ``inject.py``-Aufruf, der sie erzeugt.
    """
    erwartet = (Artefakt.MANIFEST, Artefakt.ERROR_LOG, Artefakt.ERROR_LOG_RECORDS)
    fehlend = [artefakt.value for artefakt in erwartet if not (ziel / artefakt.value).is_file()]
    if fehlend:
        raise SystemExit(
            f"Dem Lauf {run_id!r} unter {ziel} fehlen die Artefakte {fehlend}. Der Lauf "
            "entsteht mit 'python scripts/inject.py' und denselben Faktorstufen, etwa:\n"
            "  python scripts/inject.py --serie <serie> --design <design> "
            "--klasse <klasse> --rate <rate> --wdh <nr>"
        )
    inhalt = json.loads((ziel / Artefakt.MANIFEST.value).read_text(encoding="utf-8"))
    if not isinstance(inhalt, dict) or "faktorstufen" not in inhalt:
        raise SystemExit(
            f"Das Manifest {ziel / Artefakt.MANIFEST.value} hat keinen Abschnitt "
            "'faktorstufen'. Es stammt aus einer aelteren Fassung von scripts/inject.py "
            "und muss neu erzeugt werden."
        )
    return dict(inhalt)


def _manifestabschnitt(manifest: Mapping[str, Any], name: str, run_id: str) -> Mapping[str, Any]:
    """Liest einen Abschnitt des Manifests, der eine Gruppenliste traegt.

    Bewusst **ohne** Ersatzwert. Aus diesen beiden Abschnitten stammen die Listen
    aller Fehlerklassen und aller Injektionsvarianten des Laufs — einschliesslich
    derer, die bei dieser Fehlerrate das Kontingent null bekommen haben. Faengt
    man den fehlenden Abschnitt mit einer leeren Menge ab, verschwinden genau
    diese Gruppen lautlos aus allen Tabellen. Ein Recall, der fehlt, weil die
    Variante nie gezogen wurde, waere dann nicht mehr von einem Recall zu
    unterscheiden, der null ist, weil kein Verfahren sie gefunden hat — und
    Abnahmekriterium 5 verlangt genau diese Unterscheidung.

    Args:
        manifest: Inhalt des Manifests.
        name: Name des Abschnitts.
        run_id: Kennung des Laufs.

    Returns:
        Den Abschnitt.

    Raises:
        SystemExit: Wenn der Abschnitt fehlt oder kein Woerterbuch ist.
    """
    abschnitt = manifest.get(name)
    if not isinstance(abschnitt, dict):
        raise SystemExit(
            f"Das Manifest des Laufs {run_id!r} enthaelt keinen Abschnitt {name!r}. Ohne ihn "
            "fehlen in jeder Ergebnistabelle genau die Gruppen, die bei dieser Fehlerrate "
            "kein Kontingent bekommen haben — ihr fehlender Recall waere von einem Recall "
            "null nicht zu unterscheiden. Das Manifest stammt aus einer aelteren Fassung "
            "von scripts/inject.py und muss neu erzeugt werden."
        )
    return abschnitt


def _pruefe_faktorstufen(
    optionen: argparse.Namespace, faktorstufen: Mapping[str, Any], run_id: str
) -> None:
    """Gleicht die Kommandozeile mit den Faktorstufen des Manifests ab.

    Der Pfad kodiert nur Serie, Design, Segment, Rate und Wiederholung. Modus,
    Fehlerklasse und Variante stehen ausschliesslich im Manifest; ein
    Variantenlauf und ein Klassenlauf koennen im selben Verzeichnis liegen, wenn
    das Segment gleich heisst. Eine Abweichung wird deshalb gemeldet und nicht
    stillschweigend zugunsten einer der beiden Quellen aufgeloest.

    Args:
        optionen: Ausgewertete Kommandozeile.
        faktorstufen: Abschnitt ``faktorstufen`` des Manifests.
        run_id: Kennung des Laufs.

    Raises:
        SystemExit: Bei jeder Abweichung.
    """
    gefordert = {
        "serie": optionen.serie,
        "design": optionen.design,
        "modus": optionen.modus,
        "klasse": optionen.klasse,
        "variante": optionen.variante,
        "wiederholung": optionen.wdh,
    }
    abweichungen = [
        f"{name}: Kommandozeile {gefordert[name]!r}, Manifest {faktorstufen.get(name)!r}"
        for name in _ABGEGLICHENE_STUFEN
        if faktorstufen.get(name) != gefordert[name]
    ]
    manifest_rate = faktorstufen.get("fehlerrate")
    if manifest_rate is None or round(float(manifest_rate) * _BASISPUNKTE) != round(
        optionen.rate * _BASISPUNKTE
    ):
        abweichungen.append(
            f"fehlerrate: Kommandozeile {optionen.rate!r}, Manifest {manifest_rate!r}"
        )
    if abweichungen:
        raise SystemExit(
            f"Die Faktorstufen des Laufs {run_id!r} widersprechen der Kommandozeile:\n  "
            + "\n  ".join(abweichungen)
            + "\nDie Auswertung muss denselben Lauf beschreiben wie der Ground Truth."
        )


def _pruefe_hashes(
    manifest: Mapping[str, Any],
    daten_clean: Mapping[str, pd.DataFrame],
    daten_dirty: Mapping[str, pd.DataFrame],
    run_id: str,
) -> dict[str, Any]:
    """Prueft die wiederhergestellten Datensaetze gegen die Hashwerte des Manifests.

    Args:
        manifest: Inhalt des Manifests.
        daten_clean: Wiederhergestellte Rohschicht des sauberen Datensatzes.
        daten_dirty: Wiederhergestellte Rohschicht des verfaelschten Datensatzes.
        run_id: Kennung des Laufs.

    Returns:
        Den Nachweis als JSON-faehiges Woerterbuch: je Datensatz die Zahl der
        geprueften Entitaeten. Er gehoert in ``metrics.json`` und belegt
        Architekturregel A2 fuer diesen Lauf.

    Raises:
        SystemExit: Sobald ein Hashwert abweicht oder im Manifest fehlt. Jede
            Kennzahl waere sonst auf einen anderen Datensatz bezogen als der
            Ground Truth.
    """
    hinterlegt = manifest.get("sha256")
    if not isinstance(hinterlegt, dict):
        raise SystemExit(
            f"Das Manifest des Laufs {run_id!r} enthaelt keinen Abschnitt 'sha256'. Ohne ihn "
            "ist nicht nachweisbar, dass die Auswertung auf demselben Datensatz laeuft wie "
            "der Ground Truth."
        )

    abweichungen: list[str] = []
    for bezeichnung, daten in (("df_clean", daten_clean), ("df_dirty", daten_dirty)):
        erwartet = hinterlegt.get(bezeichnung)
        if not isinstance(erwartet, dict):
            raise SystemExit(
                f"Dem Manifest des Laufs {run_id!r} fehlen die Hashwerte fuer {bezeichnung}."
            )
        for name in ENTITAETEN:
            gemessen = sha256_dataframe(daten[name])
            if erwartet.get(name) != gemessen:
                abweichungen.append(
                    f"{bezeichnung}.{name}: Manifest {erwartet.get(name)}, "
                    f"wiederhergestellt {gemessen}"
                )

    if abweichungen:
        raise SystemExit(
            f"Der Reproduzierbarkeitsnachweis des Laufs {run_id!r} schlaegt fehl:\n  "
            + "\n  ".join(abweichungen)
            + "\nDer wiederhergestellte Datensatz ist nicht der, auf dem der Ground Truth "
            "erhoben wurde. Moegliche Ursachen: ein anderer --seed, ein anderes "
            "--n-anfragen, ein anderer --basis-index, ein anderer --clean-run oder eine "
            "geaenderte Konfiguration. "
            "Die Auswertung waere auf einen anderen Datensatz bezogen und wird abgebrochen."
        )
    return {
        "geprueft": "sha256 je Entitaet gegen manifest.json",
        "df_clean_entitaeten": len(ENTITAETEN),
        "df_dirty_entitaeten": len(ENTITAETEN),
        "abweichungen": 0,
    }


def _seed_modell(config: Config, optionen: argparse.Namespace) -> SeedSequence:
    """Leitet den Modellstrom des Laufs aus denselben Faktorstufen ab wie die Injektion.

    Verwendet wird :data:`~src.common.seeding.Strom.MODELL` mit **denselben**
    Faktoren wie :func:`scripts.inject._seed_inject`. Damit ist auch das
    Subsampling von B2 allein aus ``run_id`` und Konfiguration reproduzierbar, und
    zwar unabhaengig davon, wann und in welcher Reihenfolge der Lauf ausgewertet
    wird (Architekturregel A2).

    Args:
        config: Geladene Konfiguration.
        optionen: Ausgewertete Kommandozeile; ``segment`` ist bereits gesetzt.

    Returns:
        Die ``SeedSequence`` des Modellstroms.
    """
    return lauf_seed(
        config.master_seed,
        Strom.MODELL,
        _namensfaktor(optionen.serie),
        _namensfaktor(optionen.design),
        _namensfaktor(optionen.segment),
        round(optionen.rate * _BASISPUNKTE),
        injektions_index(optionen),
    )


def _baue_verfahren(
    namen: Sequence[str],
    config: Config,
    optionen: argparse.Namespace,
    wahrheit: GroundTruth,
) -> tuple[Verfahren, ...]:
    """Instanziiert die angeforderten Verfahren in Berichtsreihenfolge.

    B2 bekommt den Ground Truth: Es waehlt seine ``contamination``-Stufe ueber die
    beste F1 der Satzebene. Das ist eine bewusst **optimistische** Einstellung
    zugunsten der Baseline und im Modul-Docstring von
    :mod:`src.baselines.b2_isolation_forest` als solche ausgewiesen — der
    Prototyp bekommt keine vergleichbare Anpassung.

    Args:
        namen: Gewuenschte Verfahren.
        config: Geladene Konfiguration.
        optionen: Ausgewertete Kommandozeile.
        wahrheit: Ground Truth des Laufs.

    Returns:
        Die Verfahren in der Reihenfolge von :data:`VERFAHRENSNAMEN`.

    Raises:
        SystemExit: Bei einem unbekannten Verfahrensnamen.
    """
    unbekannt = sorted(set(namen) - set(VERFAHRENSNAMEN))
    if unbekannt:
        raise SystemExit(
            f"Unbekannte Verfahren: {unbekannt}. Bekannt sind: {list(VERFAHRENSNAMEN)}."
        )
    gewuenscht = set(namen)
    bauplan: dict[str, Callable[[], Verfahren]] = {
        "prototyp": Prototyp,
        "B0": B0Schema,
        "B2": lambda: IsolationForestBaseline(_seed_modell(config, optionen), wahrheit=wahrheit),
        "B3": B3Framework,
    }
    return tuple(bauplan[name]() for name in VERFAHRENSNAMEN if name in gewuenscht)


# ---------------------------------------------------------------------------
# Ausgabe
# ---------------------------------------------------------------------------


def _zusatzangaben(verfahren: Sequence[Verfahren]) -> dict[str, dict[str, Any]]:
    """Sammelt die verfahrensspezifischen Angaben fuer ``metrics.json``.

    B2 liefert seinen vollstaendigen Schwellen-Sweep, B3 seinen
    Ausdrueckbarkeitsbericht. Beide stehen bewusst nicht im gemeinsamen
    Ergebnistyp: Ein Feld, das bei drei von vier Verfahren leer bleibt, waere ein
    Formatschaden zugunsten eines Sonderfalls.

    Args:
        verfahren: Die bereits ausgefuehrten Verfahren.

    Returns:
        Je Verfahrensnamen die Zusatzangaben.
    """
    zusatz: dict[str, dict[str, Any]] = {}
    for eintrag in verfahren:
        if isinstance(eintrag, IsolationForestBaseline):
            zusatz[eintrag.name] = {
                "contamination": eintrag.gewaehlte_contamination(),
                "stufenwahl": eintrag.stufenwahl(),
                "uebersprungene_entitaeten": dict(
                    sorted(eintrag.uebersprungene_entitaeten().items())
                ),
                "sweep": [dataclasses.asdict(stufe) for stufe in eintrag.sweep()],
            }
        elif isinstance(eintrag, B3Framework):
            zusatz[eintrag.name] = {"b3_bericht": eintrag.bericht().als_dict()}
    return zusatz


def _schreibe_detections(
    verfahren: Sequence[Verfahren],
    kontext: Kontext,
    ziel: Path,
) -> list[Path]:
    """Legt die Rohmeldungen je Verfahren als Parquet ab.

    Der zweite ``erkenne``-Aufruf findet **nach** der Messung statt und
    beeinflusst sie nicht. Der Prototyp und B2 beantworten ihn aus ihrem
    Zwischenspeicher (Schluessel ist die Objektidentitaet des Kontexts), B0 und B3
    laufen dafuer ein zweites Mal.

    Args:
        verfahren: Die bereits ausgefuehrten Verfahren.
        kontext: Derselbe Kontext, mit dem bewertet wurde — nur bei
            Objektgleichheit greifen die Zwischenspeicher.
        ziel: Laufverzeichnis.

    Returns:
        Die geschriebenen Pfade.
    """
    pfade: list[Path] = []
    for eintrag in verfahren:
        pfad = ziel / _DETECTIONS.format(verfahren=eintrag.name)
        eintrag.erkenne(kontext).to_parquet(pfad, index=False)
        pfade.append(pfad)
    return pfade


def _zeige(ergebnisse: Sequence[Verfahrensergebnis], dauer: float) -> None:
    """Gibt die Kernzahlen des Laufs aus.

    Berichtet wird die Hauptauswertung ``mitgezogen_als_fehler=False`` auf der
    Zell- und der Satzebene. Alles Weitere steht in ``metrics.json``.

    Args:
        ergebnisse: Die Verfahrensergebnisse.
        dauer: Gesamtlaufzeit der Auswertung in Sekunden.
    """
    kopf = f"  {'Verfahren':<10}{'Ebene':<16}{'Prec.':>8}{'Recall':>8}{'F1':>8}{'MCC':>8}"
    print(kopf)
    for ergebnis in ergebnisse:
        auswertung = ergebnis.auswertungen[0]
        for ebene in (Ebene.ZELLE, Ebene.SATZ):
            kennzahlen = auswertung.ebenen[ebene].kennzahlen
            if kennzahlen is None:
                print(f"  {ergebnis.verfahren:<10}{ebene.value:<16}  nicht auswertbar")
                continue
            mcc = "-" if kennzahlen.mcc is None else f"{kennzahlen.mcc:8.4f}"
            print(
                f"  {ergebnis.verfahren:<10}{ebene.value:<16}"
                f"{kennzahlen.precision:8.4f}{kennzahlen.recall:8.4f}"
                f"{kennzahlen.f1:8.4f}{mcc:>8}"
            )
    print()
    for ergebnis in ergebnisse:
        speicher = (
            "-" if ergebnis.messung.speicher_mb is None else f"{ergebnis.messung.speicher_mb:.1f}"
        )
        print(
            f"  {ergebnis.verfahren:<10}Laufzeit {ergebnis.messung.laufzeit_s:8.2f} s, "
            f"Speicher {speicher:>8} MiB, Meldungen {ergebnis.meldungen_gesamt:>8}, "
            f"markierte Zellen {ergebnis.markierte_zellen:>8}"
        )
    print(f"\n  Auswertung gesamt     {dauer:.1f} s")


# ---------------------------------------------------------------------------
# Kommandozeile
# ---------------------------------------------------------------------------


def _argumente() -> argparse.ArgumentParser:
    """Baut den Argumentparser des Skripts.

    Die Argumentnamen sind absichtlich dieselben wie in ``scripts/inject.py``:
    Derselbe Lauf wird mit demselben Aufruf erst verfaelscht und dann bewertet.
    """
    parser = argparse.ArgumentParser(
        description="Bewertet den Prototyp und die Baselines auf einem Experimentlauf."
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
    parser.add_argument("--klasse", default=None, help="Fehlerklasse F1 bis F8, HO1, HO2 oder mix")
    parser.add_argument(
        "--variante", default=None, help="Injektionsvariante, etwa F7-c; nur mit --modus variante"
    )
    parser.add_argument("--rate", type=float, default=None, help="Fehlerrate als Anteil")
    parser.add_argument("--wdh", type=int, required=True, help="Nummer der Wiederholung")
    parser.add_argument(
        "--verfahren",
        nargs="+",
        default=list(VERFAHRENSNAMEN),
        help=f"Auszuwertende Verfahren; bekannt sind {list(VERFAHRENSNAMEN)}",
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
            "Nummer des Basisdatensatzes; 0 ist der kanonische. Muss mit der Angabe des "
            "Injektionslaufs uebereinstimmen — ein falscher Wert faellt beim "
            "Reproduzierbarkeitsnachweis auf"
        ),
    )
    parser.add_argument(
        "--injektions-index",
        type=int,
        default=None,
        dest="injektions_index",
        help="Nummer, die in seed_inject eingeht; ohne Angabe die Wiederholung",
    )
    parser.add_argument("--seed", type=int, default=None, help="Master-Seed uebersteuern")
    parser.add_argument(
        "--n-anfragen", type=int, default=None, help="Anzahl der Anfragen uebersteuern"
    )
    parser.add_argument(
        "--kein-speicher",
        action="store_true",
        dest="kein_speicher",
        help="Schaltet die tracemalloc-Messung ab; sie verlangsamt den Lauf spuerbar",
    )
    parser.add_argument(
        "--ohne-detections",
        action="store_true",
        dest="ohne_detections",
        help="Legt die Rohmeldungen je Verfahren nicht ab (spart einen zweiten Lauf von B0)",
    )
    parser.add_argument("--still", action="store_true", help="Keine Fortschrittsausgabe")
    return parser


def main(argumente: Sequence[str] | None = None) -> int:
    """Einstiegspunkt des Skripts.

    Args:
        argumente: Kommandozeilenargumente; ``None`` nimmt ``sys.argv``.

    Returns:
        ``0``, wenn die Auswertung durchlief. Der Rueckgabewert sagt **nichts**
        ueber die Hoehe der Kennzahlen aus — sie stehen in ``metrics.json`` und
        sind dort das Ergebnis. Ein Abbruch entsteht nur, wenn der Lauf fehlt,
        die Faktorstufen widersprechen oder der Reproduzierbarkeitsnachweis
        fehlschlaegt.
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
        config, optionen.serie, optionen.design, optionen.segment, optionen.rate, optionen.wdh
    )
    manifest = _lies_manifest(ziel, run_id)
    faktorstufen = dict(manifest["faktorstufen"])
    _pruefe_faktorstufen(optionen, faktorstufen, run_id)
    optionen.max_fehler = faktorstufen.get("max_fehler")

    if not optionen.still:
        print(f"Auswertung (run_id={run_id}, verfahren={optionen.verfahren})")
        print("Der verfaelschte Datensatz wird aus den Seeds wiederhergestellt.")

    beginn = time.perf_counter()
    daten_clean, _ = _lade_clean(config, optionen.clean_run, basis_index=optionen.basis_index)
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
    nachweis = _pruefe_hashes(manifest, daten_clean, ergebnis.df_raw_dirty, run_id)
    if not optionen.still:
        print("Reproduzierbarkeitsnachweis: alle SHA-256-Werte stimmen mit manifest.json ueberein.")

    wahrheit = lade_ground_truth(
        pd.read_parquet(ziel / Artefakt.ERROR_LOG.value),
        pd.read_parquet(ziel / Artefakt.ERROR_LOG_RECORDS.value),
        ergebnis.df_raw_dirty,
        run_id=run_id,
        klassen=sorted(_manifestabschnitt(manifest, "angefordert_je_klasse", run_id)),
        varianten=sorted(_manifestabschnitt(manifest, "zuteilung_je_variante", run_id)),
    )
    kontext = baue_kontext(config, raw=ergebnis.df_raw_dirty)

    verfahren = _baue_verfahren(optionen.verfahren, config, optionen, wahrheit)
    ergebnisse = bewerte(verfahren, kontext, wahrheit, messe_speicher=not optionen.kein_speicher)
    zusatz = _zusatzangaben(verfahren)
    dauer = time.perf_counter() - beginn

    inhalt = baue_metrics(run_id, faktorstufen, wahrheit, ergebnisse, zusatz=zusatz)
    inhalt["reproduzierbarkeit"] = nachweis
    metrikpfad = schreibe_metrics(inhalt, ziel / Artefakt.METRICS.value)
    langpfad = schreibe_langformat(
        baue_langformat(run_id, faktorstufen, ergebnisse),
        config.pfade.results / _LANGFORMAT,
    )

    b3pfad: Path | None = None
    if B3Framework.name in zusatz:
        b3pfad = config.pfade.results / _B3_BERICHT
        b3pfad.parent.mkdir(parents=True, exist_ok=True)
        _schreibe_json(
            b3pfad,
            {
                "run_id": run_id,
                "verfahren": B3Framework.name,
                **zusatz[B3Framework.name]["b3_bericht"],
            },
        )

    detections = [] if optionen.ohne_detections else _schreibe_detections(verfahren, kontext, ziel)

    if not optionen.still:
        _zeige(ergebnisse, dauer)
        print(f"\nKennzahlen in  {metrikpfad}")
        print(f"Langformat in  {langpfad}")
        if b3pfad is not None:
            print(f"B3-Bericht in  {b3pfad}")
        for pfad in detections:
            print(f"Meldungen in   {pfad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
