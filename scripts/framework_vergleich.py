"""Stellt cuallee und Great Expectations auf denselben Regeln nebeneinander.

Aufruf::

    python scripts/framework_vergleich.py
    python scripts/framework_vergleich.py --n-anfragen 500 --ziel results

Warum dieses Skript getrennt von ``scripts/evaluate.py`` steht
---------------------------------------------------------------

Der Gegenschnitt mit Great Expectations ist **keine dritte Baseline**. Er tritt in
keiner Konfusionsmatrix an, geht nicht in die Inferenzstatistik ein und misst
nicht, wer mehr findet. Er liefert die zweite Spalte einer Tabelle ueber den
**Gestaltungsraum** der Werkzeuge: Wie viel laesst sich ueberhaupt formulieren, was
kostet es an Quelltext, wie lange dauert es, und was sagt der Report ueber einen
Fund aus?

Wuerde das Skript im Evaluator haengen, zahlte jeder der tausenden Laeufe der
Phase 6 den Import von ``great_expectations`` mit — siebzehn Pakete, die dort
nichts zu tun haben.

Was das Ergebnis praezisiert
-----------------------------

Der B3-Befund allein legt nahe, die Kennzahl "Anteil ausdrueckbarer Regeln" sei
frameworkunabhaengig. Sie ist es nicht: Great Expectations formuliert auf denselben
sieben Regeln mehr als cuallee, weil ``row_condition`` bedingte Regeln und
``ExpectColumnValuesToMatchStrftimeFormat`` echtes Datumsparsen erlaubt.
Frameworkuebergreifend belastbar ist der **Kern** der Grenze — die relationalen,
die quellenuebergreifenden und die algorithmischen Regeln. Die Begruendung steht
ausfuehrlich im Modul-Docstring von :mod:`src.baselines.b3b_great_expectations`.

Geschrieben wird ``results/framework_vergleich.json``, bewusst ohne Zeitstempel
(Architekturregel A2).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ermoeglicht den Aufruf "python scripts/framework_vergleich.py" ohne editierbare
# Installation. Muss vor den Projektimporten stehen.
_WURZEL = Path(__file__).resolve().parents[1]
if str(_WURZEL) not in sys.path:
    sys.path.insert(0, str(_WURZEL))

import argparse  # noqa: E402
import dataclasses  # noqa: E402
import json  # noqa: E402
from typing import TYPE_CHECKING, Any, Final  # noqa: E402

from src.baselines.b3_framework import B3Framework  # noqa: E402
from src.baselines.b3b_great_expectations import GE_REGELN, GEVergleich  # noqa: E402
from src.common.config import lade_config  # noqa: E402
from src.common.seeding import Strom, lauf_seed, wurzel_seeds  # noqa: E402
from src.common.serialisierung import ENTITAETEN, serialisiere  # noqa: E402
from src.generator.pipeline import erzeuge_datensatz  # noqa: E402
from src.rules.modell import baue_kontext  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence

    from src.evaluation.modell import Kontext

__all__ = ["main"]

#: Dateiname des Vergleichs unter ``results/``.
_BERICHT: Final[str] = "framework_vergleich.json"

#: Faktorstufe des Vergleichslaufs im Injektionsstrom.
#:
#: Eine eigene, feste Zahl, damit der Vergleichslauf keinen Strom eines
#: Experimentlaufs mitbenutzt und trotzdem reproduzierbar bleibt (A2).
_VERGLEICHSSTUFE: Final[int] = 9001


def _kontext(
    n_anfragen: int | None, config_pfad: Path | None, klasse: str | None, rate: float
) -> Kontext:
    """Erzeugt den Datensatz, auf dem beide Frameworks laufen.

    Drei der vier Kennzahlen — Ausdrueckbarkeit, Aufwand, Laufzeit — braeuchten
    keinen verfaelschten Datensatz. Die vierte schon: Die **Diagnoseguete** laesst
    sich nur an einem echten Fund zeigen, und auf dem sauberen Datensatz gibt es
    keinen (Clean-Baseline-Lauf, null Meldungen). Ohne Verfaelschung bliebe das
    Feld ``beispiel_lokalisierung`` leer, und die Kernaussage des Gegenschnitts
    stuende wieder als Behauptung statt als Messwert da.

    Args:
        n_anfragen: Anzahl der Anfragen; ohne Angabe der Konfigurationswert.
        config_pfad: Pfad zur Konfigurationsdatei.
        klasse: Zu injizierende Fehlerklasse; ``None`` laesst den Datensatz sauber.
        rate: Fehlerrate der Injektion.

    Returns:
        Den Pruefkontext ueber beide Datenschichten.
    """
    config = lade_config(config_pfad)
    if n_anfragen is not None:
        config = dataclasses.replace(config, n_anfragen=n_anfragen)
    typisiert = erzeuge_datensatz(config, wurzel_seeds(config.master_seed).basis)
    roh = {name: serialisiere(typisiert[name]) for name in ENTITAETEN}

    if klasse is not None:
        # scripts/ ist die aeusserste Schicht und darf den Injektor kennen —
        # dieselbe Begruendung wie in scripts/inject.py und scripts/evaluate.py.
        from src.injector import injiziere  # noqa: PLC0415 - nur bei Bedarf

        ergebnis = injiziere(
            roh,
            rate,
            {klasse: 1.0},
            lauf_seed(config.master_seed, Strom.INJEKTION, _VERGLEICHSSTUFE),
            "framework_vergleich",
            config=config,
        )
        roh = ergebnis.df_raw_dirty

    return baue_kontext(config, raw=roh)


def _vergleichstabelle(cuallee: Mapping[str, Any], ge: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Baut die Zeile-fuer-Zeile-Gegenueberstellung der sieben vorgelegten Regeln.

    Args:
        cuallee: Bericht von B3.
        ge: Bericht des Gegenschnitts.

    Returns:
        Je vorgelegter Regel eine Zeile mit beiden Einordnungen und den
        Codezeilen beider Frameworks.
    """
    cuallee_zeilen = cuallee["codezeilen_je_regel"]["framework"]
    ge_zeilen = ge["codezeilen_je_regel"]
    einordnung = ge["cuallee_zum_vergleich"]["einordnung_je_regel"]
    return [
        {
            "regel_id": eintrag.regel_id,
            "cuallee": einordnung[eintrag.regel_id],
            "great_expectations": "ja" if eintrag.ausdruckbar else "nein",
            "codezeilen_cuallee": cuallee_zeilen.get(eintrag.regel_id),
            "codezeilen_great_expectations": ge_zeilen.get(eintrag.regel_id),
        }
        for eintrag in GE_REGELN
    ]


def _bericht(cuallee: Mapping[str, Any], ge: Mapping[str, Any]) -> dict[str, Any]:
    """Stellt den Vergleichsbericht zusammen."""
    return {
        "erzeugt_von": "scripts/framework_vergleich.py",
        "vorgelegte_regeln": [eintrag.regel_id for eintrag in GE_REGELN],
        "je_regel": _vergleichstabelle(cuallee, ge),
        "diagnoseguete": {
            "cuallee": cuallee["diagnoseguete"],
            "great_expectations": ge["diagnoseguete"],
        },
        "beispiel_lokalisierung_great_expectations": ge["beispiel_lokalisierung"],
        "laufzeit_s": {
            "cuallee_alle_g1_regeln": cuallee["laufzeit_s"],
            "great_expectations_sieben_regeln": ge["laufzeit_s"],
        },
        "anteil_ausdrueckbar": {
            "cuallee_auf_g1": cuallee["anteil_ausdrueckbarer_regeln"]["g1"],
            "cuallee_auf_katalog": cuallee["anteil_ausdrueckbarer_regeln"]["katalog"],
            "cuallee_auf_den_sieben": ge["cuallee_zum_vergleich"]["anteil_vollstaendig"],
            "great_expectations_auf_den_sieben": ge["anteil_ausdrueckbar"],
        },
        "lesehinweis": (
            "Die Kennzahl 'Anteil ausdrueckbarer Regeln' ist NICHT "
            "frameworkunabhaengig. Great Expectations formuliert auf denselben "
            "sieben Regeln mehr als cuallee: row_condition deckt bedingte Regeln "
            "ab (R-001), ExpectColumnValuesToMatchStrftimeFormat echtes "
            "Datumsparsen (R-009). Frameworkuebergreifend belastbar ist der Kern "
            "der Grenze — die relationalen Regeln R-043 bis R-048, R-052 und "
            "R-054, die quellenuebergreifenden R-049 bis R-051 und R-055 bis "
            "R-058 sowie die algorithmische R-004. An R-004 scheitern beide."
        ),
        "cuallee": dict(cuallee),
        "great_expectations": dict(ge),
    }


def main(argumente: Sequence[str] | None = None) -> int:
    """Einstiegspunkt des Skripts.

    Args:
        argumente: Kommandozeilenargumente; ``None`` nimmt ``sys.argv``.

    Returns:
        ``0``, wenn der Vergleich durchlief.
    """
    parser = argparse.ArgumentParser(
        description="Stellt cuallee und Great Expectations auf denselben Regeln nebeneinander."
    )
    parser.add_argument("--config", type=Path, default=None, help="Pfad zur Konfigurationsdatei")
    parser.add_argument(
        "--n-anfragen", type=int, default=None, help="Anzahl der Anfragen uebersteuern"
    )
    parser.add_argument("--ziel", type=Path, default=None, help="Zielverzeichnis des Berichts")
    parser.add_argument(
        "--klasse",
        default="F2",
        help="Fehlerklasse, die vor dem Vergleich injiziert wird; "
        "'keine' laesst den Datensatz sauber",
    )
    parser.add_argument("--rate", type=float, default=0.02, help="Fehlerrate der Injektion")
    parser.add_argument("--still", action="store_true", help="Keine Fortschrittsausgabe")
    optionen = parser.parse_args(argumente)

    if not optionen.still:
        print("Frameworkvergleich: cuallee gegen Great Expectations auf denselben Regeln")

    klasse = None if optionen.klasse == "keine" else optionen.klasse
    kontext = _kontext(optionen.n_anfragen, optionen.config, klasse, optionen.rate)

    b3 = B3Framework()
    b3.erkenne(kontext)
    cuallee_bericht = b3.bericht().als_dict()
    ge_bericht = GEVergleich().pruefe(kontext).als_dict()
    inhalt = _bericht(cuallee_bericht, ge_bericht)

    ziel = optionen.ziel if optionen.ziel is not None else kontext.config.pfade.results
    ziel.mkdir(parents=True, exist_ok=True)
    pfad = ziel / _BERICHT
    pfad.write_text(
        json.dumps(inhalt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    if not optionen.still:
        _zeige(inhalt)
        print(f"\nBericht in {pfad}")
    return 0


def _zeige(inhalt: Mapping[str, Any]) -> None:
    """Gibt die Vergleichstabelle aus."""
    print("\n  Regel   cuallee      Great Expectations   Zeilen cua / GE")
    for zeile in inhalt["je_regel"]:
        cua = zeile["codezeilen_cuallee"]
        ge = zeile["codezeilen_great_expectations"]
        print(
            f"  {zeile['regel_id']}   {zeile['cuallee']:<12} "
            f"{zeile['great_expectations']:<20} "
            f"{'-' if cua is None else cua:>4} / {'-' if ge is None else ge}"
        )
    anteile = inhalt["anteil_ausdrueckbar"]
    print(
        f"\n  Auf den sieben vorgelegten Regeln: cuallee "
        f"{anteile['cuallee_auf_den_sieben']:.0%}, Great Expectations "
        f"{anteile['great_expectations_auf_den_sieben']:.0%}"
    )
    print("\n  Diagnoseguete:")
    for name, werte in inhalt["diagnoseguete"].items():
        gut = ", ".join(sorted(schluessel for schluessel, wert in werte.items() if wert))
        fehlt = ", ".join(sorted(schluessel for schluessel, wert in werte.items() if not wert))
        print(f"    {name:<20} liefert: {gut or '-'} | fehlt: {fehlt or '-'}")
    beispiel = inhalt["beispiel_lokalisierung_great_expectations"]
    if beispiel is not None:
        print(f"\n  Beispiel Great Expectations ({beispiel['regel_id']}): {beispiel['eintrag']}")


if __name__ == "__main__":
    raise SystemExit(main())
