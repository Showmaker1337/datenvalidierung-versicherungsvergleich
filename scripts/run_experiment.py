"""Faehrt den Versuchsplan der Phase 6 ab: Injektion, Auswertung, Aggregation.

Aufruf::

    python scripts/run_experiment.py --config config/experiment.yaml
    python scripts/run_experiment.py --nur-teilversuch T3 T6
    python scripts/run_experiment.py --trockenlauf
    python scripts/run_experiment.py --pilot 20

Was das Skript tut
------------------

Es faltet ``config/experiment.yaml`` ueber :mod:`src.evaluation.experimentplan`
zu Einzellaeufen auf, verteilt sie auf Prozesse und schreibt je Lauf dieselben
Artefakte, die ``scripts/inject.py`` und ``scripts/evaluate.py`` von Hand
erzeugen wuerden. Am Ende fasst es alle Langformate zu
``results/metrics_long.parquet`` zusammen.

Warum Injektion und Auswertung in **einem** Prozess laufen
-----------------------------------------------------------

Getrennt aufgerufen erzeugt ``inject.py`` den sauberen Datensatz und
``evaluate.py`` erzeugt ihn ein zweites Mal, um den verfaelschten
wiederherzustellen. Bei rund tausend Laeufen waeren das zweitausend
Datensatzerzeugungen zu je zwoelf Sekunden — knapp sieben Stunden allein dafuer.

Der Runner erzeugt den sauberen Datensatz einmal je Arbeitsprozess und
Faktorkombination ``(n_anfragen, basis_index)``, haelt ihn im Speicher und
verfaelscht ihn je Lauf neu. Der verfaelschte Datensatz geht **direkt** in die
Auswertung, ohne Umweg ueber die Platte.

Der Preis ist eine ehrliche Einschraenkung, die in die Arbeit gehoert: Der
Reproduzierbarkeitsnachweis von ``evaluate.py`` — Hashvergleich zwischen dem
neu hergestellten und dem protokollierten Datensatz — ist hier trivial erfuellt,
weil beide Seiten dasselbe Objekt sind. Er wird deshalb **nicht** als bestandener
Nachweis ausgewiesen, sondern als ``"identitaet"`` gekennzeichnet. Der echte,
prozessuebergreifende Nachweis entsteht durch einen Stichprobenlauf von
``scripts/evaluate.py`` auf einem bereits gerechneten Lauf; ``--stichprobe``
zieht ihn automatisch und schreibt das Ergebnis nach
``results/reproduktionsstichprobe.json``.

Reihenfolgeunabhaengigkeit
--------------------------

Jeder Lauf leitet seine Seeds allein aus seinen Faktorstufen ab
(:func:`src.common.seeding.lauf_seed`), niemals ueber ``SeedSequence.spawn()``.
Das Ergebnis haengt damit nicht davon ab, welcher Prozess welchen Lauf abholt.
``tests/test_determinismus.py`` prueft genau das mit einem und mit vier Prozessen.

``PYTHONHASHSEED`` wird erzwungen, nicht erhofft
------------------------------------------------

Python streut Zeichenketten je Prozess anders. Das Projekt umgeht das an den
Stellen, die zaehlen (``_namensfaktor`` hasht mit SHA-256, es wird nicht ueber
ungeordnete Mengen iteriert) — aber "wir haben aufgepasst" ist kein Nachweis.
Das Skript startet sich deshalb einmalig mit ``PYTHONHASHSEED=0`` neu, wenn die
Variable nicht gesetzt ist, und schreibt den Wert in den Laufbericht.

Fehler brechen die Serie nicht ab
----------------------------------

Ein gescheiterter Einzellauf wird mit Traceback in
``results/failed_runs.json`` protokolliert; die Serie laeuft weiter. Am Ende wird
die Zahl der Fehlschlaege **ausgewiesen** — stillschweigend mit weniger Laeufen
weiterzurechnen waere eine verdeckte Stichprobenreduktion.

Wiederaufnahme
--------------

Ein Lauf gilt als fertig, wenn sein Verzeichnis ``metrics.json`` und
``langformat.parquet`` enthaelt und darin alle angeforderten Verfahren stehen.
Solche Laeufe werden uebersprungen. ``--neu`` erzwingt die Wiederholung.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ermoeglicht den Aufruf "python scripts/run_experiment.py" ohne editierbare
# Installation. Muss vor den Projektimporten stehen.
_WURZEL = Path(__file__).resolve().parents[1]
if str(_WURZEL) not in sys.path:
    sys.path.insert(0, str(_WURZEL))

#: Name der Schutzvariable gegen eine Neustartschleife.
_NEUSTART_MARKE = "BA_HASHSEED_GESETZT"


def _erzwinge_hashseed() -> int | None:
    """Startet das Skript mit ``PYTHONHASHSEED=0`` neu, falls noetig.

    Muss **vor** allen Projektimporten entschieden werden: Die Streuung von
    Zeichenketten steht beim Start des Interpreters fest und laesst sich zur
    Laufzeit nicht mehr aendern.

    Neu gestartet wird ueber einen **Unterprozess** und nicht ueber ``execve``.
    Unter Windows gibt es kein echtes ``exec``; die Bibliotheksfunktion legt
    dort einen neuen Prozess an und beendet den alten sofort. Eine aufrufende
    Schale saehe den Aufruf dann als beendet an, waehrend die Arbeit noch laeuft,
    und verloere die Ausgabe. Der Unterprozess erbt Ein- und Ausgabe und liefert
    seinen Rueckgabewert zurueck.

    Die Schutzvariable :data:`_NEUSTART_MARKE` verhindert eine Endlosschleife,
    falls die Umgebung die Variable nicht durchreicht.

    Returns:
        Den Rueckgabewert des Unterprozesses, oder ``None``, wenn kein Neustart
        noetig war und der aufrufende Prozess selbst weiterarbeiten soll.
    """
    if os.environ.get("PYTHONHASHSEED") == "0" or os.environ.get(_NEUSTART_MARKE) == "1":
        return None
    import subprocess  # noqa: PLC0415 - nur fuer den Neustart gebraucht

    umgebung = dict(os.environ)
    umgebung["PYTHONHASHSEED"] = "0"
    umgebung[_NEUSTART_MARKE] = "1"
    fertig = subprocess.run(  # noqa: S603 - fest verdrahtete Argumente, kein Schalenaufruf
        [sys.executable, *sys.argv],
        env=umgebung,
        check=False,
    )
    return fertig.returncode


if __name__ == "__main__":
    _RUECKGABE = _erzwinge_hashseed()
    if _RUECKGABE is not None:
        raise SystemExit(_RUECKGABE)

import argparse  # noqa: E402
import dataclasses  # noqa: E402
import json  # noqa: E402
import multiprocessing  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
from typing import TYPE_CHECKING, Any, Final  # noqa: E402

import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from scripts.evaluate import (  # noqa: E402
    _LANGFORMAT,
    _baue_verfahren,
    _schreibe_detections,
    _zusatzangaben,
)
from scripts.inject import (  # noqa: E402
    _gewichte,
    _lade_clean,
    _lauf_angaben,
    _manifest,
    _schreibe_json,
    _seed_inject,
)
from src.common.config import als_dict as konfiguration_als_dict  # noqa: E402
from src.common.config import lade_config  # noqa: E402
from src.common.pfade import (  # noqa: E402
    Artefakt,
    experiment_verzeichnis,
    sha256_dataframe,
)
from src.common.serialisierung import ENTITAETEN  # noqa: E402
from src.evaluation.experimentplan import (  # noqa: E402
    HAUPTVERSUCH,
    STANDARD_PLAN,
    Lauf,
    Versuchsplan,
    lade_plan,
    laeufe,
)
from src.evaluation.ground_truth import lade_ground_truth  # noqa: E402
from src.evaluation.langformat import (  # noqa: E402
    baue_langformat,
    baue_metrics,
    schreibe_langformat,
)
from src.evaluation.pipeline import bewerte  # noqa: E402
from src.injector import injiziere  # noqa: E402
from src.rules.modell import baue_kontext  # noqa: E402
from src.verify import pruefe_ground_truth  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    from src.common.config import Config

__all__ = ["Auftrag", "fuehre_lauf_aus", "main"]

#: Dateiname des Langformats eines Einzellaufs im Laufverzeichnis.
LANGFORMAT_JE_LAUF: Final[str] = "langformat.parquet"

#: Dateiname der Fehlerliste unter ``results/``.
FEHLERLISTE: Final[str] = "failed_runs.json"

#: Dateiname des Laufberichts unter ``results/``.
LAUFBERICHT: Final[str] = "experiment_lauf.json"

#: Dateiname der Reproduktionsstichprobe unter ``results/``.
STICHPROBE: Final[str] = "reproduktionsstichprobe.json"

#: Alle Laeufe des gewaehlten Plans, nach ``run_id`` adressierbar.
#:
#: Wird in :func:`main` gefuellt und nur von der Reproduktionsstichprobe gelesen.
#: Die Alternative waere, die vollstaendigen Laeufe durch die Berichte der
#: Arbeitsprozesse zurueckzureichen; das machte den Bericht gross und
#: seine Serialisierung teuer, ohne dass die Angaben sonst gebraucht wuerden.
_lauf_je_run_id: dict[str, Lauf] = {}

#: Kennzeichnung des Reproduzierbarkeitsnachweises im Einprozessbetrieb.
#:
#: Bewusst **nicht** die Zeichenkette, die ``scripts/evaluate.py`` schreibt: Dort
#: ist der Hashvergleich ein echter Nachweis zwischen zwei getrennt
#: hergestellten Datensaetzen, hier waere er eine Tautologie. Zwei verschiedene
#: Sachverhalte duerfen nicht denselben Text tragen.
NACHWEIS_IDENTITAET: Final[str] = (
    "identitaet: Auswertung und Ground Truth liegen im selben Prozess auf demselben "
    "Objekt; der prozessuebergreifende Nachweis entsteht ueber scripts/evaluate.py "
    "(siehe results/reproduktionsstichprobe.json)"
)


@dataclasses.dataclass(frozen=True, slots=True)
class Auftrag:
    """Der Arbeitsauftrag eines Prozesses.

    Muss serialisierbar sein: ``multiprocessing`` arbeitet unter Windows mit
    ``spawn`` und uebertraegt den Auftrag ueber ``pickle``.

    Attributes:
        lauf: Der auszufuehrende Lauf.
        fach_config: Pfad der fachlichen Konfiguration als Zeichenkette, oder
            ``None`` fuer ``config/default.yaml``.
        detections: Legt die Rohmeldungen je Verfahren ab.
    """

    lauf: Lauf
    fach_config: str | None
    detections: bool


#: Zwischenspeicher des sauberen Datensatzes je Arbeitsprozess.
#:
#: Schluessel ist ``(n_anfragen, basis_index)``. Es wird **hoechstens ein**
#: Datensatz gehalten: Bei 100.000 Anfragen belegt er mehrere Gigabyte, und ein
#: zweiter daneben braechte den Rechner bei acht Prozessen an die Grenze.
_ZWISCHENSPEICHER: dict[tuple[int, int], dict[str, pd.DataFrame]] = {}


# ---------------------------------------------------------------------------
# Ein einzelner Lauf
# ---------------------------------------------------------------------------


def _optionen(lauf: Lauf, config_pfad: Path | None) -> argparse.Namespace:
    """Baut die Optionen, die ``scripts/inject.py`` fuer diesen Lauf saehe.

    Bewusst ein :class:`argparse.Namespace` und keine eigene Struktur: Die
    Bausteine aus ``scripts/inject.py`` — ``_seed_inject``, ``_lauf_angaben``,
    ``_manifest`` — werden damit **unveraendert** wiederverwendet. Jede eigene
    Struktur waere eine zweite Fassung derselben Angaben, und zwei Fassungen
    laufen frueher oder spaeter auseinander; das Manifest eines Runnerlaufs saehe
    dann anders aus als das eines Handlaufs, und der Vergleich in
    ``tests/test_experiment.py`` waere nicht mehr moeglich.

    Args:
        lauf: Der auszufuehrende Lauf.
        config_pfad: Pfad der fachlichen Konfiguration, oder ``None``.

    Returns:
        Die Optionen.
    """
    return argparse.Namespace(
        config=config_pfad,
        serie=lauf.serie,
        design=lauf.design,
        modus=lauf.modus,
        klasse=lauf.klasse,
        variante=lauf.variante,
        segment=lauf.segment,
        rate=lauf.fehlerrate,
        wdh=lauf.wiederholung,
        basis_index=lauf.basis_index,
        injektions_index=lauf.injektions_index,
        max_fehler=lauf.max_fehler,
        clean_run=None,
        seed=None,
        n_anfragen=lauf.n_anfragen,
        behalten=False,
        still=True,
    )


def _clean_datensatz(config: Config, lauf: Lauf) -> tuple[dict[str, pd.DataFrame], str]:
    """Beschafft den sauberen Datensatz und haelt hoechstens einen im Speicher.

    Args:
        config: Konfiguration mit bereits gesetztem ``n_anfragen``.
        lauf: Der auszufuehrende Lauf.

    Returns:
        Die Rohschicht und die Herkunftsangabe fuer das Manifest.
    """
    schluessel = (lauf.n_anfragen, lauf.basis_index)
    herkunft = "erzeugt" if lauf.basis_index == 0 else f"erzeugt (basis_index={lauf.basis_index})"
    zwischengespeichert = _ZWISCHENSPEICHER.get(schluessel)
    if zwischengespeichert is not None:
        return zwischengespeichert, herkunft
    _ZWISCHENSPEICHER.clear()
    daten, herkunft = _lade_clean(config, None, basis_index=lauf.basis_index)
    _ZWISCHENSPEICHER[schluessel] = daten
    return daten, herkunft


def _ist_fertig(ziel: Path, lauf: Lauf) -> bool:
    """Entscheidet, ob ein Lauf bereits vollstaendig vorliegt.

    Geprueft wird nicht nur die Existenz der Dateien, sondern auch, ob
    ``metrics.json`` **alle** angeforderten Verfahren enthaelt. Sonst gaelte ein
    Lauf, der beim ersten Durchgang nur mit dem Prototyp gerechnet wurde, auch
    dann als fertig, wenn der Plan inzwischen drei Verfahren verlangt — und die
    fehlenden Zellen verschwaenden lautlos aus der Auswertung.

    Args:
        ziel: Laufverzeichnis.
        lauf: Der Lauf.

    Returns:
        ``True``, wenn nichts mehr zu tun ist.
    """
    metrikdatei = ziel / Artefakt.METRICS.value
    if not metrikdatei.is_file() or not (ziel / LANGFORMAT_JE_LAUF).is_file():
        return False
    try:
        inhalt = json.loads(metrikdatei.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    # ``metrics.json`` fuehrt die Verfahren als Abbildung Name auf Ergebnis, nicht
    # als Liste; die Schluessel sind die gerechneten Verfahren.
    gerechnet = set(inhalt.get("verfahren", {}))
    return set(lauf.verfahren) <= gerechnet


def fuehre_lauf_aus(auftrag: Auftrag) -> dict[str, Any]:
    """Fuehrt einen einzelnen Experimentlauf vollstaendig aus.

    Diese Funktion ist der Arbeitsauftrag eines Prozesses. Sie muss auf oberster
    Modulebene stehen und ein einzelnes, serialisierbares Argument nehmen, weil
    ``multiprocessing`` unter Windows mit ``spawn`` arbeitet und den Auftrag
    ueber ``pickle`` uebertraegt.

    Der Ablauf ist derselbe wie ``inject.py`` gefolgt von ``evaluate.py``, nur
    ohne den Umweg ueber die Platte:

    1. sauberen Datensatz beschaffen (aus dem Zwischenspeicher, falls moeglich),
    2. verfaelschen und den Ground Truth pruefen,
    3. ``error_log``, ``error_log_records``, ``config.yaml`` und
       ``manifest.json`` schreiben,
    4. die Verfahren auf dem verfaelschten Datensatz bewerten,
    5. ``metrics.json`` und ``langformat.parquet`` schreiben.

    Args:
        auftrag: Der Lauf und der Pfad der fachlichen Konfiguration.

    Returns:
        Einen serialisierbaren Bericht mit ``run_id``, ``teilversuch``,
        ``status`` (``"fertig"``, ``"uebersprungen"`` oder ``"fehler"``),
        ``laufzeit_s`` und im Fehlerfall ``fehler`` samt ``traceback``. Eine
        Ausnahme wird **nicht** nach aussen gereicht: Sie wuerde den Pool
        abbrechen und damit die ganze Serie.
    """
    lauf = auftrag.lauf
    beginn = time.perf_counter()
    bericht: dict[str, Any] = {
        "run_id": lauf.run_id,
        "teilversuch": lauf.teilversuch,
        "klasse": lauf.klasse,
        "variante": lauf.variante,
        "fehlerrate": lauf.fehlerrate,
        "wiederholung": lauf.wiederholung,
        "n_anfragen": lauf.n_anfragen,
    }
    config_pfad = None if auftrag.fach_config is None else Path(auftrag.fach_config)
    try:
        config = dataclasses.replace(lade_config(config_pfad), n_anfragen=lauf.n_anfragen)
        ziel = experiment_verzeichnis(
            config,
            lauf.serie,
            lauf.design,
            lauf.segment,
            lauf.fehlerrate,
            lauf.wiederholung,
            anlegen=True,
        )
        optionen = _optionen(lauf, config_pfad)
        _schreibe_lauf(lauf, optionen, config, ziel, detections=auftrag.detections)
    except Exception as fehler:  # noqa: BLE001 - ein Einzelfehler darf die Serie nicht abbrechen
        bericht["status"] = "fehler"
        bericht["fehler"] = f"{type(fehler).__name__}: {fehler}"
        bericht["traceback"] = traceback.format_exc()
    else:
        bericht["status"] = "fertig"
    bericht["laufzeit_s"] = round(time.perf_counter() - beginn, 3)
    return bericht


def _schreibe_lauf(
    lauf: Lauf,
    optionen: argparse.Namespace,
    config: Config,
    ziel: Path,
    *,
    detections: bool,
) -> None:
    """Verfaelscht, bewertet und legt alle Artefakte eines Laufs ab.

    Args:
        lauf: Der auszufuehrende Lauf.
        optionen: Die aus ihm gebauten Optionen.
        config: Konfiguration mit gesetztem ``n_anfragen``.
        ziel: Bereits angelegtes Laufverzeichnis.
        detections: Legt die Rohmeldungen je Verfahren ab.

    Raises:
        RuntimeError: Wenn der unabhaengige Gegencheck des Ground Truth eine
            Abweichung meldet. Der Lauf zaehlt dann als Fehlschlag und landet in
            ``failed_runs.json`` — eine Kennzahl auf einem fehlerhaften Ground
            Truth waere schlimmer als ein fehlender Lauf.
    """
    run_id = lauf.run_id
    daten_clean, herkunft = _clean_datensatz(config, lauf)
    ergebnis = injiziere(
        daten_clean,
        lauf.fehlerrate,
        _gewichte(lauf.klasse),
        _seed_inject(config, optionen),
        run_id,
        config=config,
        nur_varianten=(lauf.variante,) if lauf.variante is not None else None,
        hoechstzahl=lauf.max_fehler,
    )

    pruefung = pruefe_ground_truth(
        daten_clean, ergebnis.df_raw_dirty, ergebnis.error_log, ergebnis.error_log_records
    )
    if not pruefung.sauber:
        raise RuntimeError(
            f"Der unabhaengige Gegencheck meldet fuer {run_id!r} Abweichungen im Ground "
            f"Truth: {json.dumps(pruefung.als_dict(), ensure_ascii=False, sort_keys=True)}"
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
                    "teilversuch": lauf.teilversuch,
                    "verfahren": list(lauf.verfahren),
                },
                "konfiguration": konfiguration_als_dict(config),
            },
            allow_unicode=True,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )
    manifest = _manifest(
        optionen=optionen,
        config=config,
        ergebnis=ergebnis,
        herkunft=herkunft,
        zeilen={name: len(daten_clean[name]) for name in ENTITAETEN},
        hashes_clean=hashes_clean,
        hashes_dirty=hashes_dirty,
        gegencheck_sauber=pruefung.sauber,
    )
    manifest["teilversuch"] = lauf.teilversuch
    _schreibe_json(ziel / Artefakt.MANIFEST.value, manifest)

    wahrheit = lade_ground_truth(
        ergebnis.error_log,
        ergebnis.error_log_records,
        ergebnis.df_raw_dirty,
        run_id=run_id,
        klassen=sorted(manifest["angefordert_je_klasse"]),
        varianten=sorted(manifest["zuteilung_je_variante"]),
    )
    kontext = baue_kontext(config, raw=ergebnis.df_raw_dirty)
    verfahren = _baue_verfahren(lauf.verfahren, config, optionen, wahrheit)
    ergebnisse = bewerte(verfahren, kontext, wahrheit, messe_speicher=lauf.messe_speicher)

    faktorstufen = dict(manifest["faktorstufen"])
    inhalt = baue_metrics(
        run_id, faktorstufen, wahrheit, ergebnisse, zusatz=_zusatzangaben(verfahren)
    )
    inhalt["erzeugt_von"] = "scripts/run_experiment.py"
    inhalt["reproduzierbarkeit"] = {
        "geprueft": NACHWEIS_IDENTITAET,
        "df_clean_entitaeten": len(ENTITAETEN),
        "df_dirty_entitaeten": len(ENTITAETEN),
        "abweichungen": 0,
    }
    inhalt["teilversuch"] = lauf.teilversuch
    _schreibe_json(ziel / Artefakt.METRICS.value, inhalt)
    baue_langformat(run_id, faktorstufen, ergebnisse).to_parquet(
        ziel / LANGFORMAT_JE_LAUF, index=False
    )
    if detections:
        _schreibe_detections(verfahren, kontext, ziel)


# ---------------------------------------------------------------------------
# Serie
# ---------------------------------------------------------------------------


def _offene_laeufe(
    alle: Sequence[Lauf], config: Config, *, neu: bool
) -> tuple[list[Lauf], list[Lauf]]:
    """Trennt die noch offenen Laeufe von den bereits fertigen.

    Args:
        alle: Alle Laeufe des gewaehlten Plans.
        config: Geladene Konfiguration; liefert das Laufverzeichnis.
        neu: Ignoriert vorhandene Ergebnisse und rechnet alles neu.

    Returns:
        Die offenen und die uebersprungenen Laeufe.
    """
    if neu:
        return list(alle), []
    offen: list[Lauf] = []
    fertig: list[Lauf] = []
    for lauf in alle:
        ziel = experiment_verzeichnis(
            config, lauf.serie, lauf.design, lauf.segment, lauf.fehlerrate, lauf.wiederholung
        )
        (fertig if _ist_fertig(ziel, lauf) else offen).append(lauf)
    return offen, fertig


def _sammle_langformat(alle: Sequence[Lauf], config: Config) -> pd.DataFrame:
    """Fasst die Langformate aller Laeufe zu einer Tabelle zusammen.

    Aggregiert wird im **Elternprozess**, nicht in den Arbeitsprozessen: Eine
    gemeinsame Zieldatei, in die acht Prozesse gleichzeitig schreiben, waere ein
    Wettlauf, und der verlorene Schreibvorgang faele erst in der Statistik auf.

    Args:
        alle: Alle Laeufe des gewaehlten Plans.
        config: Geladene Konfiguration.

    Returns:
        Das zusammengefasste Langformat, sortiert. Fehlende Einzeldateien werden
        uebergangen — sie gehoeren zu gescheiterten Laeufen und stehen in
        ``failed_runs.json``.
    """
    teile: list[pd.DataFrame] = []
    for lauf in alle:
        pfad = (
            experiment_verzeichnis(
                config, lauf.serie, lauf.design, lauf.segment, lauf.fehlerrate, lauf.wiederholung
            )
            / LANGFORMAT_JE_LAUF
        )
        if pfad.is_file():
            teile.append(pd.read_parquet(pfad))
    if not teile:
        return pd.DataFrame()
    return pd.concat(teile, ignore_index=True)


def _hochrechnung(dauern: Sequence[float], offen: int, worker: int) -> dict[str, float]:
    """Rechnet aus gemessenen Einzellaufzeiten auf den Rest der Serie hoch.

    Args:
        dauern: Bereits gemessene Laufzeiten in Sekunden.
        offen: Zahl der noch nicht gerechneten Laeufe.
        worker: Zahl der Arbeitsprozesse.

    Returns:
        Mittlere Laufzeit, Restdauer seriell und Restdauer parallel, jeweils in
        Sekunden beziehungsweise Stunden.
    """
    mittel = sum(dauern) / len(dauern) if dauern else 0.0
    seriell = mittel * offen
    return {
        "laeufe_gemessen": float(len(dauern)),
        "mittlere_laufzeit_s": round(mittel, 2),
        "rest_seriell_h": round(seriell / 3600, 2),
        "rest_parallel_h": round(seriell / max(worker, 1) / 3600, 2),
    }


def _zeige_plan(plan: Versuchsplan, alle: Sequence[Lauf], offen: Sequence[Lauf]) -> None:
    """Gibt den Umfang des Plans aus."""
    print(f"Versuchsserie {plan.serie}")
    print(f"  {'Block':<8}{'Design':<8}{'Laeufe':>8}{'Zellen':>8}  Titel")
    for block in plan.bloecke:
        print(
            f"  {block.kennung:<8}{block.design:<8}{block.anzahl_laeufe:>8}"
            f"{block.zellen:>8}  {block.titel}"
        )
    print(f"\n  Laeufe im gewaehlten Plan: {len(alle)}")
    print(f"  davon offen:               {len(offen)}")
    print(f"  davon bereits fertig:      {len(alle) - len(offen)}")


def _argumente() -> argparse.ArgumentParser:
    """Baut den Argumentparser des Skripts."""
    parser = argparse.ArgumentParser(
        description="Faehrt den Versuchsplan der Phase 6 ab und aggregiert die Ergebnisse."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=STANDARD_PLAN,
        help=f"Pfad des Versuchsplans; Vorgabe {STANDARD_PLAN.name}",
    )
    parser.add_argument(
        "--fach-config",
        type=Path,
        default=None,
        dest="fach_config",
        help="Pfad der fachlichen Konfiguration; ohne Angabe config/default.yaml",
    )
    parser.add_argument(
        "--nur-teilversuch",
        nargs="+",
        default=None,
        dest="nur",
        metavar="KENNUNG",
        help=f"Nur diese Bloecke rechnen, etwa {HAUPTVERSUCH} T3 T6",
    )
    parser.add_argument("--worker", type=int, default=None, help="Zahl der Arbeitsprozesse")
    parser.add_argument(
        "--pilot",
        type=int,
        default=None,
        help="Nur so viele Laeufe rechnen und daraus auf den vollen Plan hochrechnen",
    )
    parser.add_argument(
        "--neu",
        action="store_true",
        help="Vorhandene Ergebnisse ignorieren und alles neu rechnen",
    )
    parser.add_argument(
        "--trockenlauf",
        action="store_true",
        help="Nur den Umfang des Plans ausgeben, nichts rechnen",
    )
    parser.add_argument(
        "--detections",
        action="store_true",
        help="Rohmeldungen je Verfahren ablegen; uebersteuert den Plan",
    )
    parser.add_argument(
        "--stichprobe",
        type=int,
        default=0,
        help=(
            "So viele gerechnete Laeufe anschliessend mit scripts/evaluate.py in einem "
            "eigenen Prozess nachrechnen; belegt die Reproduzierbarkeit prozessuebergreifend"
        ),
    )
    return parser


def _reproduktionsstichprobe(
    fertig: Sequence[Lauf],
    optionen: argparse.Namespace,
    ergebnisse: Path,
    *,
    anzahl: int,
) -> None:
    """Rechnet einige Laeufe mit ``scripts/evaluate.py`` nach.

    Der Runner haelt Ground Truth und Auswertung im selben Prozess auf demselben
    Objekt; sein Hashvergleich waere eine Tautologie. ``scripts/evaluate.py``
    stellt den verfaelschten Datensatz dagegen **neu** aus den Seeds her und
    vergleicht ihn Entitaet fuer Entitaet gegen die SHA-256-Werte im
    ``manifest.json``. Erst das ist der Nachweis, den Architekturregel A2
    verlangt — und er kostet nur so viel Rechenzeit, wie die Stichprobe gross ist.

    Ein Fehlschlag wird protokolliert, nicht verschwiegen: Er hiesse, dass der
    Lauf sich nicht wiederherstellen laesst, und das waere ein Befund.

    Gezogen wird aus **allen** vollstaendigen Laeufen des Plans und nicht nur aus
    denen, die dieser Aufruf gerechnet hat. Sonst bliebe die Stichprobe genau dann
    leer, wenn sie am meisten wert waere: bei einer fertigen Serie, die man
    nachtraeglich belegen will.

    Args:
        fertig: Alle vollstaendig vorliegenden Laeufe des Plans.
        optionen: Ausgewertete Kommandozeile.
        ergebnisse: Verzeichnis ``results/``.
        anzahl: Groesse der Stichprobe.
    """
    from scripts import evaluate  # noqa: PLC0415 - Importkosten nur bei Bedarf

    if not fertig:
        print("\nReproduktionsstichprobe: kein vollstaendiger Lauf vorhanden.")
        return
    schritt = max(1, len(fertig) // anzahl)
    auswahl = list(fertig)[::schritt][:anzahl]
    print(f"\nReproduktionsstichprobe: {len(auswahl)} Laeufe werden nachgerechnet.")

    protokoll: list[dict[str, Any]] = []
    for lauf in auswahl:
        argumente = [
            "--serie", lauf.serie,
            "--design", lauf.design,
            "--modus", lauf.modus,
            "--rate", str(lauf.fehlerrate),
            "--wdh", str(lauf.wiederholung),
            "--basis-index", str(lauf.basis_index),
            "--injektions-index", str(lauf.injektions_index),
            "--n-anfragen", str(lauf.n_anfragen),
            "--verfahren", *lauf.verfahren,
            "--kein-speicher",
            "--ohne-detections",
            "--still",
        ]
        if lauf.variante is None:
            argumente += ["--klasse", lauf.klasse]
        else:
            argumente += ["--variante", lauf.variante]
        if optionen.fach_config is not None:
            argumente += ["--config", str(optionen.fach_config)]
        try:
            rueckgabe = evaluate.main(argumente)
        except SystemExit as fehler:
            protokoll.append(
                {"run_id": lauf.run_id, "bestanden": False, "meldung": str(fehler)}
            )
            print(f"  FEHLER {lauf.run_id}: {fehler}")
        else:
            protokoll.append(
                {"run_id": lauf.run_id, "bestanden": rueckgabe == 0, "meldung": None}
            )
            print(f"  ok     {lauf.run_id}")

    _schreibe_json(
        ergebnisse / STICHPROBE,
        {
            "zweck": (
                "prozessuebergreifender Reproduzierbarkeitsnachweis: scripts/evaluate.py "
                "stellt den verfaelschten Datensatz neu aus den Seeds her und vergleicht "
                "ihn je Entitaet gegen die SHA-256-Werte im manifest.json"
            ),
            "geprueft": len(protokoll),
            "bestanden": sum(1 for eintrag in protokoll if eintrag["bestanden"]),
            "laeufe": protokoll,
        },
    )


def _pilotauswahl(offen: Sequence[Lauf], anzahl: int) -> list[Lauf]:
    """Waehlt eine ueber die Bloecke gestreute Pilotstichprobe.

    Die ersten ``n`` Laeufe zu nehmen waere die schlechteste Wahl: Sie gehoeren
    alle zur selben Klasse und zur kleinsten Fehlerrate, und die Hochrechnung
    unterschaetzte die Serie dann systematisch — F1 braucht bei zehn Prozent das
    Sechsfache der Injektionszeit von F3 bei einem Prozent. Gezogen wird deshalb
    in gleichmaessigen Abstaenden ueber die gesamte Liste.

    Args:
        offen: Die offenen Laeufe.
        anzahl: Gewuenschte Stichprobengroesse.

    Returns:
        Die Auswahl in Planreihenfolge.
    """
    if anzahl >= len(offen):
        return list(offen)
    schritt = len(offen) / anzahl
    return [offen[int(nummer * schritt)] for nummer in range(anzahl)]


def main(argumente: Sequence[str] | None = None) -> int:  # noqa: PLR0915 - linearer Ablauf
    """Einstiegspunkt des Skripts.

    Args:
        argumente: Kommandozeilenargumente; ``None`` nimmt ``sys.argv``.

    Returns:
        ``0``, wenn kein Lauf gescheitert ist, sonst ``1``. Die Serie laeuft in
        beiden Faellen zu Ende; der Rueckgabewert ist das Signal an die
        aufrufende Schale, dass ``results/failed_runs.json`` zu lesen ist.
    """
    optionen = _argumente().parse_args(argumente)
    plan = lade_plan(optionen.config)
    config = lade_config(optionen.fach_config)
    worker = optionen.worker if optionen.worker is not None else plan.worker

    alle = laeufe(plan, optionen.nur)
    _lauf_je_run_id.update({lauf.run_id: lauf for lauf in alle})
    offen, uebersprungen = _offene_laeufe(alle, config, neu=optionen.neu)
    _zeige_plan(plan, alle, offen)

    if optionen.trockenlauf:
        print("\nTrockenlauf: es wurde nichts gerechnet.")
        return 0

    if optionen.pilot is not None:
        offen = _pilotauswahl(offen, optionen.pilot)
        print(f"\nPilotserie: {len(offen)} Laeufe, gestreut ueber den Plan.")

    fach_config = None if optionen.fach_config is None else str(optionen.fach_config)
    detections = optionen.detections or plan.schreibe_detections
    auftraege = [Auftrag(lauf, fach_config, detections) for lauf in offen]
    print(f"\nRechne {len(auftraege)} Laeufe mit {worker} Prozessen.\n")

    beginn = time.perf_counter()
    berichte: list[dict[str, Any]] = []
    if auftraege:
        chunk = max(1, len(auftraege) // (worker * 4))
        with multiprocessing.Pool(processes=worker) as pool:
            for nummer, bericht in enumerate(
                pool.imap_unordered(fuehre_lauf_aus, auftraege, chunksize=chunk), start=1
            ):
                berichte.append(bericht)
                marke = "ok " if bericht["status"] == "fertig" else "FEHLER"
                print(
                    f"  [{nummer:>5}/{len(auftraege)}] {marke} {bericht['run_id']:<28}"
                    f"{bericht['laufzeit_s']:>8.1f} s",
                    flush=True,
                )
    dauer = time.perf_counter() - beginn

    gescheitert = [bericht for bericht in berichte if bericht["status"] == "fehler"]
    gelungen = [bericht for bericht in berichte if bericht["status"] == "fertig"]

    ergebnisse = config.pfade.results
    ergebnisse.mkdir(parents=True, exist_ok=True)
    _schreibe_json(
        ergebnisse / FEHLERLISTE,
        {
            "serie": plan.serie,
            "gescheiterte_laeufe": len(gescheitert),
            "gerechnete_laeufe": len(gelungen),
            "laeufe": gescheitert,
        },
    )

    langformat = _sammle_langformat(alle, config)
    langpfad = ergebnisse / _LANGFORMAT
    if not langformat.empty:
        schreibe_langformat(langformat, langpfad)

    hochrechnung = _hochrechnung(
        [bericht["laufzeit_s"] for bericht in gelungen],
        len(alle) - len(uebersprungen) - len(gelungen),
        worker,
    )
    _schreibe_json(
        ergebnisse / LAUFBERICHT,
        {
            "serie": plan.serie,
            "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
            "worker": worker,
            "laeufe_im_plan": len(alle),
            "laeufe_gerechnet": len(gelungen),
            "laeufe_uebersprungen": len(uebersprungen),
            "laeufe_gescheitert": len(gescheitert),
            "wanduhrzeit_s": round(dauer, 1),
            "wanduhrzeit_h": round(dauer / 3600, 2),
            "hochrechnung_rest": hochrechnung,
            "zeilen_langformat": len(langformat),
        },
    )

    print(f"\n  Wanduhrzeit            {dauer / 3600:.2f} h")
    print(f"  Laeufe gerechnet       {len(gelungen)}")
    print(f"  Laeufe uebersprungen   {len(uebersprungen)}")
    print(f"  Laeufe gescheitert     {len(gescheitert)}")
    if hochrechnung["laeufe_gemessen"]:
        print(f"  Mittlere Laufzeit      {hochrechnung['mittlere_laufzeit_s']:.1f} s")
        print(
            f"  Hochrechnung Rest      {hochrechnung['rest_seriell_h']:.2f} h seriell, "
            f"{hochrechnung['rest_parallel_h']:.2f} h mit {worker} Prozessen"
        )
    if not langformat.empty:
        print(f"  Langformat             {len(langformat)} Zeilen in {langpfad}")
    if gescheitert:
        print(f"\n  ACHTUNG: {len(gescheitert)} Laeufe gescheitert.")
        print(f"  Einzelheiten in {ergebnisse / FEHLERLISTE}.")
        print("  Die Zahl gehoert in die Arbeit — weniger Laeufe stillschweigend zu")
        print("  verwenden waere eine verdeckte Stichprobenreduktion.")

    if optionen.stichprobe:
        fertige = [*uebersprungen, *(_lauf_je_run_id[b["run_id"]] for b in gelungen)]
        _reproduktionsstichprobe(
            fertige, optionen, ergebnisse, anzahl=optionen.stichprobe
        )
    return 1 if gescheitert else 0


if __name__ == "__main__":
    raise SystemExit(main())
