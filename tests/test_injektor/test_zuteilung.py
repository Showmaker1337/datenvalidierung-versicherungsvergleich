"""Prueft die proportionale Zuteilung des Kontingents auf die Varianten.

Warum diese Tests den Versuchsplan tragen
-----------------------------------------

Die Fehlerrate ist Faktor UV2 des Experiments. Wuerde sich die Zusammensetzung
einer Fehlerklasse mit der Rate verschieben — weil knappe Varianten frueher an
ihre Decke stossen und ihr Rest an die reichlich vorhandenen ginge —, dann waere
ein gemessener Zusammenhang "hoehere Rate, anderer Recall" teils Ratenwirkung,
teils Mischungsverschiebung. Der Trendtest ueber die Ratenstufen koennte beides
nicht trennen.

:func:`test_anteil_je_variante_ist_ratenunabhaengig` haelt genau das fest: Der
Anteil jeder Variante am Klassenkontingent ist ueber **alle** sechs Ratenstufen
identisch.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING, Final

import pytest

from src.common.pfade import Artefakt
from src.common.seeding import Strom, lauf_seed
from src.injector import injiziere
from src.injector.auswahl import (
    anteile,
    kandidaten_je_variante,
    quoten,
    universum,
    variantenuniversum,
)
from src.injector.modell import Fehlerklasse, baue_kontext
from src.injector.varianten import VARIANTEN_JE_KLASSE
from tests.conftest import WURZEL

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from pathlib import Path

    import pandas as pd

    from src.common.config import Config
    from src.injector.modell import Injektionskontext, Kandidat

#: Die sechs Ratenstufen des Hauptversuchs (spec/03, Abschnitt 3).
RATENSTUFEN: Final[tuple[float, ...]] = (0.005, 0.01, 0.02, 0.05, 0.10, 0.20)

#: Alle Fehlerklassen in fester Reihenfolge.
ALLE_KLASSEN: Final[tuple[Fehlerklasse, ...]] = tuple(Fehlerklasse)

#: Relative Toleranz zwischen zugeteiltem und tatsaechlich erreichtem Anteil.
TOLERANZ: Final[float] = 0.05


@pytest.fixture(scope="module")
def kontext(config_injektor: Config, daten_clean: dict[str, pd.DataFrame]) -> Injektionskontext:
    """Die lesende Sicht des Injektors auf den sauberen Datensatz."""
    return baue_kontext(config_injektor, daten_clean)


@pytest.fixture(scope="module")
def kandidaten(
    kontext: Injektionskontext,
) -> dict[Fehlerklasse, dict[str, tuple[Kandidat, ...]]]:
    """Die Kandidaten aller Varianten, einmal je Klasse berechnet."""
    return {klasse: kandidaten_je_variante(kontext, klasse) for klasse in ALLE_KLASSEN}


@pytest.fixture(scope="module")
def universen(
    kandidaten: dict[Fehlerklasse, dict[str, tuple[Kandidat, ...]]],
) -> dict[Fehlerklasse, dict[str, int]]:
    """Das adressierbare Universum je Variante, einmal je Klasse berechnet."""
    return {
        klasse: {
            eintrag.variante_id: variantenuniversum(
                eintrag, kandidaten[klasse][eintrag.variante_id]
            )
            for eintrag in VARIANTEN_JE_KLASSE[klasse]
        }
        for klasse in ALLE_KLASSEN
    }


# ---------------------------------------------------------------------------
# Der Kern: konstante Anteile ueber die Ratenstufen
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("klasse", ALLE_KLASSEN, ids=lambda wert: wert.value)
def test_anteil_je_variante_ist_ratenunabhaengig(
    universen: dict[Fehlerklasse, dict[str, int]], klasse: Fehlerklasse
) -> None:
    """Der Anteil jeder Variante haengt nicht von der Fehlerrate ab.

    Das ist die Voraussetzung dafuer, dass Faktor UV2 interpretierbar bleibt:
    Ein Unterschied zwischen zwei Ratenstufen ist dann eine Ratenwirkung und
    keine Verschiebung der Variantenmischung.
    """
    erwartet = anteile(universen[klasse])
    assert abs(sum(erwartet.values()) - 1.0) < 1e-9

    for rate in RATENSTUFEN:
        gemessen = anteile(universen[klasse])
        assert gemessen == erwartet, f"Anteile weichen bei Rate {rate} ab"


@pytest.mark.parametrize("klasse", ALLE_KLASSEN, ids=lambda wert: wert.value)
def test_zugeteilte_anteile_bleiben_ueber_die_ratenstufen_stabil(
    kandidaten: dict[Fehlerklasse, dict[str, tuple[Kandidat, ...]]],
    universen: dict[Fehlerklasse, dict[str, int]],
    klasse: Fehlerklasse,
) -> None:
    """Auch die gerundeten Quoten folgen ueber alle Ratenstufen demselben Anteil.

    Gegenprobe zur reinen Anteilsrechnung: Nach der Hare-Niemeyer-Rundung darf
    der realisierte Anteil nur um den Rundungsbetrag abweichen, und dieser
    schrumpft mit steigendem Kontingent.
    """
    gesamt = universum(klasse, kandidaten[klasse])
    erwartet = anteile(universen[klasse])
    varianten = VARIANTEN_JE_KLASSE[klasse]

    for rate in RATENSTUFEN:
        ziel = round(rate * gesamt)
        zugeteilt = quoten(ziel, varianten, universen[klasse])
        assert sum(zugeteilt.values()) == ziel, f"Quoten summieren bei Rate {rate} nicht auf {ziel}"
        for kennung, anteil in erwartet.items():
            abweichung = abs(zugeteilt[kennung] - anteil * ziel)
            assert abweichung <= 1.0, (
                f"{kennung} bei Rate {rate}: {zugeteilt[kennung]} statt {anteil * ziel:.1f}"
            )


@pytest.mark.parametrize("klasse", ALLE_KLASSEN, ids=lambda wert: wert.value)
def test_quote_bleibt_im_eigenen_universum(
    kandidaten: dict[Fehlerklasse, dict[str, tuple[Kandidat, ...]]],
    universen: dict[Fehlerklasse, dict[str, int]],
    klasse: Fehlerklasse,
) -> None:
    """Keine Variante bekommt mehr zugeteilt, als ihr Universum hergibt.

    Die Summe der Variantenuniversen ist wegen Ueberschneidungen nie kleiner als
    das Klassenuniversum; daraus folgt die Schranke rechnerisch. Der Test haelt
    sie fuer alle Ratenstufen bis eins fest.
    """
    gesamt = universum(klasse, kandidaten[klasse])
    assert sum(universen[klasse].values()) >= gesamt

    for rate in (*RATENSTUFEN, 1.0):
        zugeteilt = quoten(round(rate * gesamt), VARIANTEN_JE_KLASSE[klasse], universen[klasse])
        zu_viel = {
            kennung: (wert, universen[klasse][kennung])
            for kennung, wert in zugeteilt.items()
            if wert > universen[klasse][kennung]
        }
        assert not zu_viel, f"Rate {rate}: {zu_viel}"


def test_quoten_folgen_dem_universum_und_nicht_der_gleichverteilung(
    universen: dict[Fehlerklasse, dict[str, int]],
) -> None:
    """Gegenprobe: Die Zuteilung ist wirklich proportional, nicht gleichmaessig.

    Bei F4 ist F4-g um mehr als eine Groessenordnung reichlicher vorhanden als
    F4-f. Eine gleichmaessige Zuteilung gaebe beiden dasselbe.
    """
    klasse = Fehlerklasse.F4
    zugeteilt = quoten(1000, VARIANTEN_JE_KLASSE[klasse], universen[klasse])
    assert zugeteilt["F4-g"] > zugeteilt["F4-f"] * 10
    verhaeltnis_universum = universen[klasse]["F4-g"] / universen[klasse]["F4-f"]
    verhaeltnis_quote = zugeteilt["F4-g"] / zugeteilt["F4-f"]
    assert abs(verhaeltnis_quote - verhaeltnis_universum) / verhaeltnis_universum < 0.1


# ---------------------------------------------------------------------------
# Ausgefuehrte Laeufe
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rate", [0.005, 0.02, 0.10])
@pytest.mark.parametrize("klasse", ["F1", "F2", "F3", "F4", "F6", "F7", "HO1"])
def test_lauf_erreicht_die_quoten_exakt(
    daten_clean: dict[str, pd.DataFrame], config_injektor: Config, klasse: str, rate: float
) -> None:
    """Bei einzelligen Varianten trifft der Lauf die Zuteilung auf die Einheit genau."""
    ergebnis = injiziere(
        daten_clean,
        rate,
        {klasse: 1.0},
        lauf_seed(20260630, Strom.INJEKTION, round(rate * 10000)),
        "test_zuteilung",
        config=config_injektor,
    )
    assert ergebnis.granularitaetsabweichung == 0
    assert ergebnis.fehler_je_variante == dict(ergebnis.quote_je_variante)
    assert sum(ergebnis.quote_je_variante.values()) == ergebnis.ziel_je_klasse[klasse]


@pytest.mark.parametrize("rate", [0.005, 0.02, 0.10])
@pytest.mark.parametrize("klasse", ["F5", "F8", "HO2"])
def test_gruppenvarianten_weichen_nur_um_die_gruppengroesse_ab(
    daten_clean: dict[str, pd.DataFrame], config_injektor: Config, klasse: str, rate: float
) -> None:
    """Bei den Skalierungsklassen bleibt die Abweichung durch die Gruppe beschraenkt.

    Eine kohaerente Skalierung veraendert vier Beitragsfelder auf einmal und laesst
    sich nicht in Teile zerlegen. Zwei Abweichungen sind dadurch moeglich, beide
    durch die Gruppengroesse beschraenkt und beide unabhaengig von der
    Bearbeitungsreihenfolge:

    * **nach unten**, wenn die naechste Aenderung das Kontingent ueberschreiten
      wuerde und die Variante deshalb aufhoert;
    * **nach oben**, wenn das Kontingent kleiner ist als eine einzige Gruppe. Dann
      wird trotzdem eine Aenderung angewandt — eine Variante ohne einen einzigen
      Treffer haette einen undefinierten Recall.
    """
    ergebnis = injiziere(
        daten_clean,
        rate,
        {klasse: 1.0},
        lauf_seed(20260630, Strom.INJEKTION, round(rate * 10000)),
        "test_gruppen",
        config=config_injektor,
    )
    # Groesste Gruppe: F8-e skaliert alle Angebote einer Anfrage, also vier
    # Beitragsfelder je Angebot bei hoechstens zwoelf Angeboten.
    groesste_gruppe = 4 * 12
    for kennung, quote in ergebnis.quote_je_variante.items():
        erreicht = ergebnis.fehler_je_variante[kennung]
        if quote == 0:
            assert erreicht == 0
            continue
        assert erreicht > 0, f"{kennung} bekam keine einzige Injektion"
        assert abs(erreicht - quote) < groesste_gruppe, (
            f"{kennung}: {erreicht} statt {quote}"
        )


@pytest.mark.parametrize("klasse", ALLE_KLASSEN, ids=lambda wert: wert.value)
def test_seltene_varianten_fallen_bei_kleiner_rate_aus(
    kandidaten: dict[Fehlerklasse, dict[str, tuple[Kandidat, ...]]],
    universen: dict[Fehlerklasse, dict[str, int]],
    klasse: Fehlerklasse,
) -> None:
    """Bei kleiner Rate kann eine seltene Variante das Kontingent null bekommen.

    Das ist die **bewusste** Folge der proportionalen Zuteilung und der Grund fuer
    den Teilversuch Variantencharakterisierung: Eine Variante, deren Anteil unter
    einer halben Einheit liegt, kommt im faktoriellen Plan bei kleiner Rate nicht
    vor. Ihr Recall waere dort ohnehin undefiniert.

    Der Test haelt zweierlei fest: dass das bei der obersten Ratenstufe **nicht**
    mehr passiert, und dass die Zahl der ausfallenden Varianten mit der Rate
    monoton faellt — der Ausfall ist also eine Frage des Stichprobenumfangs, keine
    strukturelle Bevorzugung.
    """
    gesamt = universum(klasse, kandidaten[klasse])
    ausfaelle = [
        sum(
            1
            for wert in quoten(
                round(rate * gesamt), VARIANTEN_JE_KLASSE[klasse], universen[klasse]
            ).values()
            if wert == 0
        )
        for rate in RATENSTUFEN
    ]
    assert ausfaelle == sorted(ausfaelle, reverse=True), (
        f"Die Zahl der ausfallenden Varianten faellt nicht monoton: {ausfaelle}"
    )
    assert ausfaelle[-1] == 0, (
        f"Bei der obersten Ratenstufe faellt noch eine Variante aus: {ausfaelle}"
    )


def test_realisierter_anteil_ist_ueber_die_ratenstufen_konstant(
    daten_clean: dict[str, pd.DataFrame], config_injektor: Config
) -> None:
    """Der tatsaechlich erreichte Variantenanteil bleibt ueber die Ratenstufen gleich.

    Das ist der Test, den die Phasenvorgabe verlangt: Er misst nicht die geplante,
    sondern die injizierte Mischung.
    """
    gemessen: dict[float, dict[str, float]] = {}
    for rate in (0.01, 0.05, 0.20):
        ergebnis = injiziere(
            daten_clean,
            rate,
            {"F4": 1.0},
            lauf_seed(20260630, Strom.INJEKTION, round(rate * 10000)),
            "test_anteil",
            config=config_injektor,
        )
        ziel = ergebnis.ziel_je_klasse["F4"]
        gemessen[rate] = {
            kennung: wert / ziel for kennung, wert in ergebnis.fehler_je_variante.items()
        }

    erwartet = gemessen[0.20]
    for rate, anteil_je_variante in gemessen.items():
        for kennung, anteil in anteil_je_variante.items():
            assert abs(anteil - erwartet[kennung]) <= TOLERANZ, (
                f"{kennung} bei Rate {rate}: {anteil:.4f} statt {erwartet[kennung]:.4f}"
            )


# ---------------------------------------------------------------------------
# Variantenmodus
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("variante_id", ["F7-c", "F4-f", "F2-a", "HO1-a"])
def test_variantenmodus_schoepft_das_universum_aus(
    daten_clean: dict[str, pd.DataFrame],
    config_injektor: Config,
    kontext: Injektionskontext,
    variante_id: str,
) -> None:
    """Ein Lauf mit genau einer Variante trifft jede Einheit ihres Universums.

    Genau das leistet die proportionale Zuteilung im faktoriellen Plan bewusst
    nicht — dort bekommt F7-c bei zwei Prozent nur eine einstellige Fallzahl.
    """
    from src.injector.varianten import variante  # noqa: PLC0415

    eintrag = variante(variante_id)
    erwartet = variantenuniversum(eintrag, eintrag.kandidaten(kontext))

    ergebnis = injiziere(
        daten_clean,
        1.0,
        {eintrag.fehlerklasse.value: 1.0},
        lauf_seed(20260630, Strom.INJEKTION, 1),
        "test_variante",
        config=config_injektor,
        nur_varianten=(variante_id,),
    )
    assert ergebnis.universum[eintrag.fehlerklasse.value] == erwartet
    assert ergebnis.fehler_je_variante == {variante_id: erwartet}
    assert set(ergebnis.universum_je_variante) == {variante_id}


def test_hoechstzahl_begrenzt_den_variantenlauf(
    daten_clean: dict[str, pd.DataFrame], config_injektor: Config
) -> None:
    """``hoechstzahl`` deckelt die Zahl der Verfaelschungen."""
    ergebnis = injiziere(
        daten_clean,
        1.0,
        {"F7": 1.0},
        lauf_seed(20260630, Strom.INJEKTION, 1),
        "test_grenze",
        config=config_injektor,
        nur_varianten=("F7-c",),
        hoechstzahl=25,
    )
    assert ergebnis.fehler_je_variante == {"F7-c": 25}


def test_variantenmodus_weist_unbekannte_kennung_zurueck(
    daten_clean: dict[str, pd.DataFrame], config_injektor: Config
) -> None:
    """Ein Tippfehler in der Variantenkennung faellt sofort auf."""
    from src.injector import InjektionsFehler  # noqa: PLC0415

    with pytest.raises(InjektionsFehler, match="Unbekannte injektor_variante_id"):
        injiziere(
            daten_clean,
            1.0,
            {"F7": 1.0},
            lauf_seed(20260630, Strom.INJEKTION, 1),
            "test_tippfehler",
            config=config_injektor,
            nur_varianten=("F7-z",),
        )


def test_variantenmodus_ueber_das_skript(tmp_path: Path, referenzverzeichnis: Path) -> None:
    """``--modus variante`` legt den Lauf unter der Variantenkennung ab."""
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
            "v01",
            "--design",
            "A",
            "--modus",
            "variante",
            "--variante",
            "F7-c",
            "--wdh",
            "0",
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

    ziel = tmp_path / "runs" / "v01" / "A" / "F7-c" / "r10000" / "w00"
    manifest = json.loads((ziel / Artefakt.MANIFEST.value).read_text(encoding="utf-8"))
    assert manifest["run_id"] == "v01_A_F7-c_r10000_w00"
    assert manifest["faktorstufen"]["modus"] == "variante"
    assert manifest["faktorstufen"]["variante"] == "F7-c"
    assert manifest["faktorstufen"]["klasse"] == "F7"
    assert set(manifest["zuteilung_je_variante"]) == {"F7-c"}
    assert manifest["gegencheck_sauber"] is True


def test_klassenmodus_verlangt_eine_klasse(tmp_path: Path) -> None:
    """Ohne ``--klasse`` bricht der Klassenmodus mit klarer Meldung ab."""
    lauf = subprocess.run(
        [
            sys.executable,
            str(WURZEL / "scripts" / "inject.py"),
            "--serie",
            "x",
            "--design",
            "A",
            "--rate",
            "0.02",
            "--wdh",
            "0",
        ],
        cwd=WURZEL,
        capture_output=True,
        text=True,
        check=False,
    )
    assert lauf.returncode != 0
    assert "verlangt --klasse" in lauf.stderr
    assert not (tmp_path / "runs").exists()


# ---------------------------------------------------------------------------
# Zellzahlen
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("klasse", ["F3", "F8", "HO2"])
def test_zellzahlen_werden_getrennt_gefuehrt(
    daten_clean: dict[str, pd.DataFrame], config_injektor: Config, klasse: str
) -> None:
    """Fehlerhafte und geaenderte Zellen sind zwei verschiedene Zahlen.

    Bei den Skalierungsklassen ist der Datensatz an mehr Stellen veraendert, als
    die Fehlerrate nominell angibt: Die nachgefuehrten Rangzellen kommen hinzu.
    Sie sind keine Fehler, veraendern den Datensatz aber sehr wohl.
    """
    ergebnis = injiziere(
        daten_clean,
        0.02,
        {klasse: 1.0},
        lauf_seed(20260630, Strom.INJEKTION, 3),
        "test_zellen",
        config=config_injektor,
    )
    assert ergebnis.zellen_geaendert_gesamt == len(ergebnis.error_log)
    assert ergebnis.zellen_fehlerhaft + ergebnis.mitgezogene_zellen == (
        ergebnis.zellen_geaendert_gesamt
    )
    if klasse == "F3":
        assert ergebnis.mitgezogene_zellen == 0
        assert ergebnis.zellen_fehlerhaft == ergebnis.zellen_geaendert_gesamt
    else:
        assert ergebnis.mitgezogene_zellen > 0
        assert ergebnis.zellen_geaendert_gesamt > ergebnis.zellen_fehlerhaft
