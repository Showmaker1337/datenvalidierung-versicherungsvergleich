"""Prueft die sechs Protokollregeln aus ``spec/03_fehlerklassen.md``, Abschnitt 5.

Jede Regel ist hier als eigener Test umgesetzt:

1. ``row_id`` ist niemals Ziel — :func:`test_row_id_ist_nie_ziel`,
   :func:`test_row_id_spalte_bleibt_unveraendert`.
2. Keine Doppelinjektion — :func:`test_keine_doppelinjektion`.
3. Effektivitaetspruefung — :func:`test_effektivitaetspruefung_haelt`.
4. Unabhaengiger Diff-Gegencheck — :func:`test_gegencheck_ohne_abweichung`.
5. Clean-Baseline-Lauf — in Phase 3 erbracht; hier als Regressionstest, dass der
   **unveraenderte** Datensatz keine Abweichung erzeugt
   (:func:`test_gegencheck_meldet_nichts_ohne_injektion`).
6. Persistenz — :func:`test_lauf_schreibt_alle_artefakte`.

Dazu die Vorgaben der Phase 4 an die Fehlerrate: Bezugsgroesse ist das
klassenspezifische Universum, und eine Rate, die es uebersteigt, fuehrt zum
Abbruch.
"""

from __future__ import annotations

import json
import subprocess
import sys
from decimal import Decimal
from itertools import pairwise
from typing import TYPE_CHECKING

import pandas as pd
import pytest

from src.common.pfade import Artefakt
from src.common.seeding import Strom, lauf_seed
from src.common.serialisierung import ENTITAETEN
from src.injector import InjektionsFehler, injiziere
from src.injector.auswahl import kandidaten_je_variante, universum
from src.injector.modell import Fehlerklasse, Zielart
from src.injector.varianten import VARIANTEN_JE_KLASSE
from src.verify import pruefe_ground_truth
from tests.conftest import WURZEL

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from pathlib import Path

    from numpy.random import SeedSequence

    from src.common.config import Config
    from src.injector import Injektionsergebnis

#: Fehlerraten, ueber die der Gegencheck laufen muss (Vorgabe: mindestens drei).
RATEN = (0.005, 0.02, 0.05)

#: Klassen, deren Kontingent sich ohne mitgezogene Zellen abbildet.
#:
#: Bei den Skalierungsvarianten kommen Rangzellen hinzu; sie sind keine Fehler und
#: gehen nicht in die Rate ein. Fuer den Ratentest werden deshalb die Klassen
#: genommen, bei denen Log- und Traegerzellzahl uebereinstimmen.
KLASSEN_OHNE_NACHFUEHRUNG = ("F1", "F2", "F3", "F4", "F5")

#: Alle Klassen, in fester Reihenfolge.
ALLE_KLASSEN = tuple(klasse.value for klasse in Fehlerklasse)

#: Relative Toleranz zwischen angeforderter und erreichter Fehlerzahl.
TOLERANZ = 0.05


def _seed(nummer: int) -> SeedSequence:
    """Leitet einen Injektionsstrom fuer die Tests ab."""
    return lauf_seed(20260630, Strom.INJEKTION, nummer)


def _injiziere(
    daten_clean: dict[str, pd.DataFrame],
    config: Config,
    klasse: str,
    rate: float,
    nummer: int = 0,
) -> Injektionsergebnis:
    """Fuehrt eine Injektion einer einzelnen Fehlerklasse aus."""
    return injiziere(daten_clean, rate, {klasse: 1.0}, _seed(nummer), "test01", config=config)


@pytest.fixture(scope="module")
def ergebnisse(
    daten_clean: dict[str, pd.DataFrame], config_injektor: Config
) -> dict[str, Injektionsergebnis]:
    """Je Fehlerklasse ein Injektionslauf mit zwei Prozent Fehlerrate."""
    return {
        klasse: _injiziere(daten_clean, config_injektor, klasse, 0.02) for klasse in ALLE_KLASSEN
    }


# ---------------------------------------------------------------------------
# Protokollregel 1 — row_id ist niemals Ziel
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("klasse", ALLE_KLASSEN)
def test_row_id_ist_nie_ziel(ergebnisse: dict[str, Injektionsergebnis], klasse: str) -> None:
    """Keine Protokollzeile nennt ``row_id`` als verfaelschte Spalte."""
    log = ergebnisse[klasse].error_log
    assert not (log["spalte"] == "row_id").any()


@pytest.mark.parametrize("klasse", ALLE_KLASSEN)
def test_row_id_spalte_bleibt_unveraendert(
    daten_clean: dict[str, pd.DataFrame],
    ergebnisse: dict[str, Injektionsergebnis],
    klasse: str,
) -> None:
    """Die bestehenden Zeilenkennungen stehen unveraendert am selben Platz.

    Wichtiger als es aussieht: Ueber ``row_id`` joint der Gegencheck ``df_clean``
    und ``df_dirty``. Verschoebe sie sich, waere jede spaetere Zuordnung zwischen
    Ground Truth und Detektion falsch.
    """
    dirty = ergebnisse[klasse].df_raw_dirty
    for entitaet in ENTITAETEN:
        vorher = list(daten_clean[entitaet]["row_id"])
        nachher = list(dirty[entitaet]["row_id"])
        assert nachher[: len(vorher)] == vorher, entitaet


@pytest.mark.parametrize("klasse", ["F6", "HO1"])
def test_neue_zeilen_bekommen_neue_row_ids(
    daten_clean: dict[str, pd.DataFrame],
    ergebnisse: dict[str, Injektionsergebnis],
    klasse: str,
) -> None:
    """Duplizierte Zeilen bekommen eine im Datensatz noch nicht vergebene Kennung."""
    ergebnis = ergebnisse[klasse]
    assert len(ergebnis.error_log_records) > 0
    for entitaet in ENTITAETEN:
        vorher = {int(wert) for wert in daten_clean[entitaet]["row_id"]}
        nachher = [int(wert) for wert in ergebnis.df_raw_dirty[entitaet]["row_id"]]
        assert len(nachher) == len(set(nachher)), f"{entitaet}: row_id doppelt vergeben"
        neue = set(nachher) - vorher
        assert not (neue & vorher)


def test_referenzzeile_bleibt_unveraendert(
    daten_clean: dict[str, pd.DataFrame], ergebnisse: dict[str, Injektionsergebnis]
) -> None:
    """Die Originalzeile einer Duplizierung wird nicht angefasst."""
    ergebnis = ergebnisse["F6"]
    for entitaet, referenz in zip(
        ergebnis.error_log_records["entitaet"],
        ergebnis.error_log_records["referenz_row_id"],
        strict=True,
    ):
        clean = daten_clean[str(entitaet)]
        dirty = ergebnis.df_raw_dirty[str(entitaet)]
        position = list(clean["row_id"]).index(str(int(referenz)))
        assert list(clean.iloc[position]) == list(dirty.iloc[position])


# ---------------------------------------------------------------------------
# Protokollregel 2 — keine Doppelinjektion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("klasse", ALLE_KLASSEN)
def test_keine_doppelinjektion(ergebnisse: dict[str, Injektionsergebnis], klasse: str) -> None:
    """Kein Tripel aus Entitaet, Zeile und Spalte kommt zweimal vor."""
    log = ergebnisse[klasse].error_log
    tripel = list(zip(log["entitaet"], log["row_id"], log["spalte"], strict=True))
    assert len(tripel) == len(set(tripel))


def test_keine_doppelinjektion_im_mischmodus(
    daten_clean: dict[str, pd.DataFrame], config_injektor: Config
) -> None:
    """Auch klassenuebergreifend faellt keine Zelle zweimal.

    Im Mischmodus laufen alle Klassen in einem Lauf; erst dort kann eine Zelle
    ueberhaupt von zwei verschiedenen Klassen getroffen werden.
    """
    gewichte = {
        "F1": 0.30,
        "F6": 0.30,
        "F5": 0.15,
        "F3": 0.10,
        "F2": 0.05,
        "F8": 0.05,
        "F7": 0.03,
        "F4": 0.02,
    }
    ergebnis = injiziere(daten_clean, 0.02, gewichte, _seed(11), "test_mix", config=config_injektor)
    log = ergebnis.error_log
    tripel = list(zip(log["entitaet"], log["row_id"], log["spalte"], strict=True))
    assert len(tripel) == len(set(tripel))
    assert set(ergebnis.fehler_je_klasse) == set(gewichte)


# ---------------------------------------------------------------------------
# Protokollregel 3 — Effektivitaetspruefung
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("klasse", ALLE_KLASSEN)
def test_effektivitaetspruefung_haelt(
    ergebnisse: dict[str, Injektionsergebnis], klasse: str
) -> None:
    """Fuer jede Log-Zeile gilt ``wert_clean != wert_dirty``.

    Ohne diese Pruefung entstuende eine Phantom-Ground-Truth: ein
    protokollierter Fehler, den es im Datensatz gar nicht gibt, und damit ein
    garantiertes False Negative.
    """
    log = ergebnisse[klasse].error_log
    gleich = [
        (entitaet, row_id, spalte)
        for entitaet, row_id, spalte, links, rechts in zip(
            log["entitaet"],
            log["row_id"],
            log["spalte"],
            log["wert_clean"],
            log["wert_dirty"],
            strict=True,
        )
        if links == rechts
    ]
    assert not gleich


@pytest.mark.parametrize("klasse", ALLE_KLASSEN)
def test_log_gibt_den_tatsaechlichen_wert_wieder(
    ergebnisse: dict[str, Injektionsergebnis], klasse: str
) -> None:
    """Der protokollierte verfaelschte Wert steht so auch im Datensatz."""
    ergebnis = ergebnisse[klasse]
    for entitaet, row_id, spalte, wert_dirty in zip(
        ergebnis.error_log["entitaet"],
        ergebnis.error_log["row_id"],
        ergebnis.error_log["spalte"],
        ergebnis.error_log["wert_dirty"],
        strict=True,
    ):
        rahmen = ergebnis.df_raw_dirty[str(entitaet)]
        position = list(rahmen["row_id"]).index(str(int(row_id)))
        tatsaechlich = rahmen[str(spalte)].iloc[position]
        gelesen = "" if pd.isna(tatsaechlich) else str(tatsaechlich)
        assert gelesen == str(wert_dirty)


# ---------------------------------------------------------------------------
# Protokollregel 4 — unabhaengiger Diff-Gegencheck
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rate", RATEN)
@pytest.mark.parametrize("klasse", ALLE_KLASSEN)
def test_gegencheck_ohne_abweichung(
    daten_clean: dict[str, pd.DataFrame], config_injektor: Config, klasse: str, rate: float
) -> None:
    """Diff und Ground Truth stimmen ueberein — fuer jede Klasse und drei Fehlerraten."""
    ergebnis = _injiziere(daten_clean, config_injektor, klasse, rate, nummer=int(rate * 10000))
    bericht = pruefe_ground_truth(
        daten_clean, ergebnis.df_raw_dirty, ergebnis.error_log, ergebnis.error_log_records
    )
    assert bericht.sauber, bericht.als_dict()


def test_gegencheck_meldet_nichts_ohne_injektion(
    daten_clean: dict[str, pd.DataFrame], ergebnisse: dict[str, Injektionsergebnis]
) -> None:
    """Regressionstest zur Clean-Baseline: Ohne Verfaelschung meldet der Check nichts."""
    leer = ergebnisse["F3"].error_log.iloc[:0]
    leere_saetze = ergebnisse["F3"].error_log_records.iloc[:0]
    bericht = pruefe_ground_truth(daten_clean, daten_clean, leer, leere_saetze)
    assert bericht.sauber
    assert bericht.zellen_im_diff == 0


def test_gegencheck_findet_eine_luecke(
    daten_clean: dict[str, pd.DataFrame], ergebnisse: dict[str, Injektionsergebnis]
) -> None:
    """Gegenprobe: Faellt eine Log-Zeile weg, meldet der Gegencheck sie.

    Ein Gegencheck, der nicht fehlschlagen kann, belegt nichts.
    """
    ergebnis = ergebnisse["F3"]
    verkuerzt = ergebnis.error_log.iloc[1:]
    bericht = pruefe_ground_truth(
        daten_clean, ergebnis.df_raw_dirty, verkuerzt, ergebnis.error_log_records
    )
    assert not bericht.sauber
    assert len(bericht.diff_ohne_log) == 1


def test_gegencheck_findet_fehlende_satzmeldung(
    daten_clean: dict[str, pd.DataFrame], ergebnisse: dict[str, Injektionsergebnis]
) -> None:
    """Gegenprobe: Eine hinzugefuegte Zeile ohne satzbasierten Eintrag faellt auf."""
    ergebnis = ergebnisse["F6"]
    bericht = pruefe_ground_truth(
        daten_clean,
        ergebnis.df_raw_dirty,
        ergebnis.error_log,
        ergebnis.error_log_records.iloc[1:],
    )
    assert not bericht.sauber
    assert bericht.neue_zeilen_ohne_log


# ---------------------------------------------------------------------------
# Fehlerrate und Bezugsgroesse
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rate", RATEN)
@pytest.mark.parametrize("klasse", KLASSEN_OHNE_NACHFUEHRUNG)
def test_fehlerzahl_entspricht_der_rate(
    daten_clean: dict[str, pd.DataFrame], config_injektor: Config, klasse: str, rate: float
) -> None:
    """Die Zahl der Log-Zeilen entspricht der Rate, bezogen auf das Klassenuniversum."""
    ergebnis = _injiziere(daten_clean, config_injektor, klasse, rate, nummer=int(rate * 10000))
    erwartet = rate * ergebnis.universum[klasse]
    assert len(ergebnis.error_log) == ergebnis.fehler_je_klasse[klasse]
    assert abs(len(ergebnis.error_log) - erwartet) <= TOLERANZ * erwartet


@pytest.mark.parametrize("klasse", ["F6", "HO1"])
def test_satzbasierte_fehlerzahl_entspricht_der_rate(
    ergebnisse: dict[str, Injektionsergebnis], klasse: str
) -> None:
    """Bei den satzbasierten Klassen ist die Bezugseinheit die duplizierbare Zeile."""
    ergebnis = ergebnisse[klasse]
    erwartet = 0.02 * ergebnis.universum[klasse]
    assert len(ergebnis.error_log_records) == ergebnis.fehler_je_klasse[klasse]
    assert abs(len(ergebnis.error_log_records) - erwartet) <= TOLERANZ * erwartet


@pytest.mark.parametrize("klasse", ALLE_KLASSEN)
def test_universum_ist_klassenspezifisch(
    daten_clean: dict[str, pd.DataFrame], config_injektor: Config, klasse: str
) -> None:
    """Das Universum ist die Menge der von der Klasse ueberhaupt treffbaren Einheiten."""
    from src.injector.modell import baue_kontext  # noqa: PLC0415

    kontext = baue_kontext(config_injektor, daten_clean)
    eintrag = Fehlerklasse(klasse)
    kandidaten = kandidaten_je_variante(kontext, eintrag)
    groesse = universum(eintrag, kandidaten)

    assert groesse > 0
    for variante in VARIANTEN_JE_KLASSE[eintrag]:
        assert kandidaten[variante.variante_id], (
            f"Variante {variante.variante_id} findet auf diesem Datensatz keinen Kandidaten"
        )
    zellen = sum(len(werte) for werte in kandidaten.values())
    if VARIANTEN_JE_KLASSE[eintrag][0].zielart is Zielart.SATZ:
        assert groesse <= zellen
    else:
        assert groesse <= zellen * (
            1 + max(len(variante.zusatzspalten) for variante in VARIANTEN_JE_KLASSE[eintrag])
        )


def test_zu_hohe_rate_bricht_ab(
    daten_clean: dict[str, pd.DataFrame], config_injektor: Config
) -> None:
    """Eine Rate ueber dem Universum fuehrt zum Abbruch, nicht zu weniger Fehlern."""
    with pytest.raises(InjektionsFehler, match="Universum umfasst aber nur"):
        _injiziere(daten_clean, config_injektor, "F3", 2.0)


def test_unbekannte_klasse_bricht_ab(
    daten_clean: dict[str, pd.DataFrame], config_injektor: Config
) -> None:
    """Ein Tippfehler in der Klassenangabe faellt sofort auf."""
    with pytest.raises(InjektionsFehler, match="Unbekannte Fehlerklassen"):
        injiziere(daten_clean, 0.02, {"F9": 1.0}, _seed(0), "test01", config=config_injektor)


def test_typisierte_daten_werden_zurueckgewiesen(
    config_injektor: Config, daten_clean: dict[str, pd.DataFrame]
) -> None:
    """Wird versehentlich ``df_typed`` uebergeben, bricht der Injektor ab.

    Es wird ausdruecklich **nicht** konvertiert: Format-, Typ- und
    Sentinel-Verfaelschungen sind auf typisierten Spalten nicht schreibbar.
    """
    from src.common.serialisierung import parse  # noqa: PLC0415

    typisiert = {name: parse(daten_clean[name], name)[0] for name in ENTITAETEN}
    with pytest.raises(InjektionsFehler, match="Rohschicht"):
        injiziere(typisiert, 0.02, {"F3": 1.0}, _seed(0), "test01", config=config_injektor)


# ---------------------------------------------------------------------------
# Protokollregel 6 — Persistenz
# ---------------------------------------------------------------------------


def test_lauf_schreibt_alle_artefakte(tmp_path: Path, referenzverzeichnis: Path) -> None:
    """``scripts/inject.py`` legt Logs, Konfiguration und Manifest ab."""
    assert referenzverzeichnis.is_dir()
    import yaml  # noqa: PLC0415

    rohdaten = yaml.safe_load((WURZEL / "config" / "default.yaml").read_text(encoding="utf-8"))
    rohdaten["pfade"]["runs"] = str(tmp_path / "runs")
    rohdaten["pfade"]["results"] = str(tmp_path / "results")
    konfiguration = tmp_path / "config.yaml"
    konfiguration.write_text(yaml.safe_dump(rohdaten, allow_unicode=True), encoding="utf-8")

    lauf = subprocess.run(
        [
            sys.executable,
            str(WURZEL / "scripts" / "inject.py"),
            "--config",
            str(konfiguration),
            "--serie",
            "t01",
            "--design",
            "A",
            "--klasse",
            "F3",
            "--rate",
            "0.02",
            "--wdh",
            "3",
            "--n-anfragen",
            "200",
            "--still",
        ],
        cwd=WURZEL,
        capture_output=True,
        text=True,
        check=False,
    )
    assert lauf.returncode == 0, lauf.stderr

    ziel = tmp_path / "runs" / "t01" / "A" / "F3" / "r0200" / "w03"
    for artefakt in (
        Artefakt.ERROR_LOG,
        Artefakt.ERROR_LOG_RECORDS,
        Artefakt.CONFIG,
        Artefakt.MANIFEST,
    ):
        assert (ziel / artefakt.value).is_file(), artefakt.value
    assert not (ziel / "dirty").exists(), "df_raw_dirty wird ohne --behalten nicht abgelegt"

    manifest = json.loads((ziel / Artefakt.MANIFEST.value).read_text(encoding="utf-8"))
    assert manifest["run_id"] == "t01_A_F3_r0200_w03"
    assert manifest["gegencheck_sauber"] is True
    assert manifest["zelluniversum"]["F3"] > 0
    assert set(manifest["sha256"]) == {"df_clean", "df_dirty"}
    assert set(manifest["seeds"]) == {"master_seed", "seed_base", "seed_inject"}
    assert set(manifest["sha256"]["df_clean"]) == set(ENTITAETEN)

    bericht = json.loads(
        (tmp_path / "results" / "ground_truth_check.json").read_text(encoding="utf-8")
    )
    assert bericht["alle_sauber"] is True
    assert bericht["laeufe"]["t01_A_F3_r0200_w03"]["sauber"] is True


def test_behalten_legt_die_verfaelschten_daten_ab(
    tmp_path: Path, referenzverzeichnis: Path
) -> None:
    """Mit ``--behalten`` entsteht zusaetzlich ein Verzeichnis ``dirty``."""
    assert referenzverzeichnis.is_dir()
    import yaml  # noqa: PLC0415

    rohdaten = yaml.safe_load((WURZEL / "config" / "default.yaml").read_text(encoding="utf-8"))
    rohdaten["pfade"]["runs"] = str(tmp_path / "runs")
    rohdaten["pfade"]["results"] = str(tmp_path / "results")
    konfiguration = tmp_path / "config.yaml"
    konfiguration.write_text(yaml.safe_dump(rohdaten, allow_unicode=True), encoding="utf-8")

    lauf = subprocess.run(
        [
            sys.executable,
            str(WURZEL / "scripts" / "inject.py"),
            "--config",
            str(konfiguration),
            "--serie",
            "t02",
            "--design",
            "B",
            "--klasse",
            "F6",
            "--rate",
            "0.01",
            "--wdh",
            "0",
            "--n-anfragen",
            "200",
            "--behalten",
            "--still",
        ],
        cwd=WURZEL,
        capture_output=True,
        text=True,
        check=False,
    )
    assert lauf.returncode == 0, lauf.stderr

    dirty = tmp_path / "runs" / "t02" / "B" / "F6" / "r0100" / "w00" / "dirty"
    for entitaet in ENTITAETEN:
        assert (dirty / f"{entitaet}.parquet").is_file(), entitaet


# ---------------------------------------------------------------------------
# Kohaerenzschritt — nachgelagert, und nur wo er hingehoert
# ---------------------------------------------------------------------------


def _raenge_je_anfrage(ergebnis: Injektionsergebnis) -> dict[str, list[tuple[int, str]]]:
    """Liest Rang und Zahlbeitrag je Anfrage aus dem **verfaelschten** Rahmen.

    Gelesen wird die Spalte ``anfrage_id`` des Rahmens selbst und nicht eine
    Zuordnung aus dem sauberen Datensatz: Die Duplikatklassen fuegen Zeilen hinzu,
    und genau die neue Zeile traegt bei F6-b den luckenerzeugenden Rang. Eine
    Zuordnung aus dem sauberen Stand kennt sie nicht und liesse den zu pruefenden
    Fall verschwinden.
    """
    angebot = ergebnis.df_raw_dirty["angebot"]
    je_anfrage: dict[str, list[tuple[int, str]]] = {}
    for anfrage_id, rang, rate in zip(
        angebot["anfrage_id"], angebot["rang"], angebot["zahlbeitrag_rate_eur"], strict=True
    ):
        if pd.isna(rang) or str(rang) in ("", "<NA>"):
            continue
        je_anfrage.setdefault(str(anfrage_id), []).append((int(rang), str(rate)))
    return je_anfrage


def _rangfolge_verletzt(ergebnis: Injektionsergebnis) -> int:
    """Zaehlt die Anfragen, in denen der Rang nicht aufsteigend nach der Rate ist.

    Das ist die Bedingung von R-044, hier bewusst **nachgebaut** statt aus
    ``src.rules`` importiert: Ein Test des Injektors darf nicht davon abhaengen,
    was der Regelkatalog gerade tut (Architekturregel A1).
    """
    verletzt = 0
    for eintraege in _raenge_je_anfrage(ergebnis).values():
        geordnet = sorted(eintraege)
        raten = [Decimal(rate) for _, rate in geordnet if rate not in ("", "<NA>")]
        if any(spaeter < frueher for frueher, spaeter in pairwise(raten)):
            verletzt += 1
    return verletzt


@pytest.mark.parametrize("klasse", ["F8", "HO2"])
def test_rangfolge_bleibt_nach_skalierung_stimmig(
    daten_clean: dict[str, pd.DataFrame],
    config_injektor: Config,
    klasse: str,
) -> None:
    """Nach dem Kohaerenzschritt ist keine Rangfolge mehr verletzt.

    Die Regressionspruefung zu Befund 11. Die erste Fassung fuehrte die Rangfolge
    je Anwendung nach und rechnete dabei gegen den **sauberen** Kontext; sobald
    zwei Angebote derselben Anfrage skaliert wurden, war sie blind fuer die erste
    Skalierung und hinterliess eine verletzte Ordnung. Gemessen wurde das an elf
    Anfragen eines HO2-Laufs — mit steigender Fehlerrate an immer mehr.

    Geprueft wird bei einer **hohen** Rate, weil der Fehler mit der Rate waechst:
    Bei 0,005 trat er auch in der alten Fassung nicht auf.
    """
    ergebnis = _injiziere(daten_clean, config_injektor, klasse, 0.05)

    assert _rangfolge_verletzt(ergebnis) == 0


def test_f6b_luecke_bleibt_bestehen(
    daten_clean: dict[str, pd.DataFrame],
    config_injektor: Config,
) -> None:
    """Der Kohaerenzschritt repariert die Verfaelschung von F6-b **nicht**.

    F6-b dupliziert eine Angebotszeile und vergibt den Rang absichtlich so, dass
    die Rangfolge eine Luecke bekommt — das **ist** die Verfaelschung. Liefe der
    Kohaerenzschritt pauschal ueber alle Anfragen, schloesse er die Luecke
    stillschweigend, und F6-b waere ueber R-043 nicht mehr auffindbar. Das waere
    ein deutlich schwererer Fehler als der, den der Schritt behebt.

    Deshalb fasst er nur Anfragen an, in denen eine **skalierende** Variante
    gewirkt hat, und laesst Anfragen mit hinzugefuegter Angebotszeile aus.
    """
    ergebnis = injiziere(
        daten_clean,
        0.05,
        {"F6": 1.0},
        _seed(0),
        "test01",
        config=config_injektor,
        nur_varianten=("F6-b",),
    )

    # Mindestens eine Anfrage traegt eine Luecke oder einen doppelten Rang.
    unstimmig = [
        anfrage_id
        for anfrage_id, eintraege in _raenge_je_anfrage(ergebnis).items()
        if sorted(rang for rang, _ in eintraege) != list(range(1, len(eintraege) + 1))
    ]
    assert unstimmig, (
        "F6-b hinterlaesst keine unstimmige Rangfolge mehr — der Kohaerenzschritt "
        "hat die Verfaelschung repariert, statt sie stehen zu lassen"
    )
