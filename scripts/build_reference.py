"""Erzeugt die sieben Referenztabellen unter ``data/reference`` — deterministisch.

Aufruf::

    python scripts/build_reference.py
    python scripts/build_reference.py --ziel /tmp/ref --seed 20260630

Die Tabellen werden **einmalig** erzeugt und danach versioniert. Zwei Laeufe mit
demselben Seed liefern bitgleiche Dateien; das prueft
``tests/test_reproduzierbarkeit.py``.

Zur Herkunft der Daten
----------------------

Fuer ``plz_ort.csv`` wurde zuerst der reale Bezug versucht (OpenPLZ API,
``openplzapi.org``). Er wurde aus drei Gruenden verworfen; die Begruendung steht
ausfuehrlich in ``docs/verteilungsquellen.md``. Kurz:

1. Die API deckelt ``pageSize`` auf 50 und bietet keinen Massendownload; ein
   vollstaendiger Abzug braeuchte ueber 2.400 Anfragen an einen frei betriebenen
   Dienst.
2. Der Weg ueber Kreise und Gemeinden ist zwar sparsamer, liefert je Gemeinde
   aber nur **eine** Postleitzahl — Grossstaedte waeren mit einer statt fuenfzig
   PLZ vertreten.
3. Das **Unterscheidungszeichen des Zulassungsbezirks** ist ueberhaupt nicht Teil
   der API. Es muesste ohnehin synthetisch erzeugt werden, ebenso wie
   Regionalklassen, Typklassen und SF-Beitragssaetze.

``spec/01_datenmodell.md``, Abschnitt 2.1, sieht diesen Fall ausdruecklich vor.
Der Aufbau haelt die Leitzonen-Systematik ein (erste Ziffer 0 bis 9). Zur
Laufzeit wird **nichts** nachgeladen.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ermoeglicht den Aufruf "python scripts/build_reference.py" ohne editierbare
# Installation. Muss vor den Projektimporten stehen.
_WURZEL = Path(__file__).resolve().parents[1]
if str(_WURZEL) not in sys.path:
    sys.path.insert(0, str(_WURZEL))

import argparse  # noqa: E402
import dataclasses  # noqa: E402
import math  # noqa: E402
from decimal import ROUND_HALF_UP, Decimal  # noqa: E402
from typing import TYPE_CHECKING, Final  # noqa: E402

import numpy as np  # noqa: E402
import numpy.typing as npt  # noqa: E402
import pandas as pd  # noqa: E402

from src.common import wertebereiche as wb  # noqa: E402
from src.common.config import Config, lade_config  # noqa: E402
from src.common.enums import (  # noqa: E402
    SF_KLASSEN_NUMERISCH,
    SF_KLASSEN_SONDER,
    Antriebsart,
    Quellschnittstelle,
)
from src.common.geld import von_float  # noqa: E402
from src.common.referenz import SPALTEN  # noqa: E402
from src.common.seeding import Strom, generator, lauf_seed  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    from numpy.random import Generator

__all__ = ["baue_referenzdaten", "main"]

# ---------------------------------------------------------------------------
# Seed-Stroeme je Tabelle
#
# Feste Zahlen: Eine neue Tabelle bekommt eine neue Nummer, damit die bereits
# erzeugten Tabellen bitgleich bleiben.
# ---------------------------------------------------------------------------
_SEED_PLZ_ORT: Final = 0
_SEED_REGIONALKLASSEN: Final = 1
_SEED_TYPKLASSEN: Final = 2
_SEED_VU_STAMMDATEN: Final = 3
_SEED_ZUERS: Final = 4

# ---------------------------------------------------------------------------
# Leitzonen-Systematik
#
# Je Leitziffer: Anteil an allen Postleitzahlen und die Bundeslaender, die in
# dieser Zone liegen. Naeherung der realen Zuordnung, in der Arbeit als
# Modellannahme zu kennzeichnen (docs/verteilungsquellen.md).
# ---------------------------------------------------------------------------
_LEITZONEN: Final[tuple[tuple[int, float, tuple[tuple[str, float], ...]], ...]] = (
    (0, 0.085, (("SN", 0.55), ("ST", 0.20), ("TH", 0.20), ("BB", 0.05))),
    (1, 0.075, (("BE", 0.35), ("BB", 0.45), ("MV", 0.20))),
    (2, 0.105, (("SH", 0.40), ("NI", 0.30), ("HH", 0.15), ("MV", 0.10), ("HB", 0.05))),
    (3, 0.110, (("NI", 0.55), ("HE", 0.25), ("NW", 0.20))),
    (4, 0.100, (("NW", 1.00),)),
    (5, 0.085, (("NW", 0.55), ("RP", 0.45))),
    (6, 0.100, (("HE", 0.45), ("RP", 0.40), ("SL", 0.15))),
    (7, 0.115, (("BW", 1.00),)),
    (8, 0.110, (("BY", 1.00),)),
    (9, 0.115, (("BY", 0.80), ("TH", 0.20))),
)

#: Kleinste Postleitzahl der Leitzone 0. Die Zahlen 00000 bis 00999 sind nicht vergeben.
_LEITZONE_0_START: Final[int] = 1000

#: Verteilung der Laenge des Unterscheidungszeichens (ein bis drei Buchstaben).
_BEZIRK_LAENGEN_GEWICHTE: Final[tuple[float, float, float]] = (0.05, 0.35, 0.60)

_BESTIMMUNGSWOERTER: Final[tuple[str, ...]] = (
    "Alt", "Neu", "Nord", "Süd", "Ost", "West", "Ober", "Unter", "Groß", "Klein",
    "Hohen", "Nieder", "Rot", "Grün", "Linden", "Eichen", "Buchen", "Birken",
    "Erlen", "Ahorn", "Stein", "Sand", "Kies", "Bruch", "Moor", "Heide", "Wiesen",
    "Feld", "Berg", "Tal", "Reh", "Hirsch", "Falken", "Adler", "Raben", "Fuchs",
    "Wolfs", "Bären", "Königs", "Fürsten", "Bischofs", "Mönchs", "Ritter", "Burg",
    "Schloss", "Markt", "Mühl", "Brücken", "Fähr", "Hafen", "Sonnen", "Mond",
    "Stern", "Nebel", "Winter", "Sommer", "Weiden", "Espen",
)  # fmt: skip

_GRUNDWOERTER: Final[tuple[str, ...]] = (
    "bach", "berg", "burg", "dorf", "feld", "hausen", "heim", "hofen", "ingen",
    "kirchen", "stadt", "stein", "tal", "thal", "wald", "weiler", "brunn",
    "furt", "see", "au", "roda", "hagen", "scheid", "brück",
)  # fmt: skip

_ORTSZUSAETZE: Final[tuple[str, ...]] = (
    " am See", " am Berg", " an der Aue", " im Tal", " an der Ilm", " am Moor",
    " an der Warne", " im Grund", "-Nord", "-Süd", "-West", "-Ost",
)  # fmt: skip

#: Wahrscheinlichkeit fuer den Zusatz beziehungsweise das Praefix "Bad ".
_P_ORTSZUSATZ: Final[float] = 0.25
_P_BAD: Final[float] = 0.03

_HERSTELLER: Final[tuple[str, ...]] = (
    "Aurex", "Baltrum", "Carnex", "Delvo", "Ebertal", "Falkor", "Grimmwerk",
    "Hanselt", "Ivarn", "Jarnvik", "Kestrel", "Lindwurm", "Mardor", "Nordvik",
    "Orinth", "Pravus", "Quarzon", "Rhenus", "Saphir", "Tellur", "Ursin",
    "Vindal", "Wendelin", "Xanthos", "Ymir", "Zephyros", "Arvid", "Borkum",
    "Cimber", "Dorsten", "Elbmark", "Fennek", "Granat", "Hedwin", "Iselin",
    "Jorvik", "Kalmar", "Luvent", "Merlan", "Nevis", "Ostara", "Perlin",
    "Quendel", "Ravik", "Solvar", "Turmalin", "Uvern", "Vardan", "Welkin", "Zorn",
)  # fmt: skip

_MODELLSTAEMME: Final[tuple[str, ...]] = (
    "Aeon", "Bora", "Cirro", "Duna", "Eos", "Fjell", "Garda", "Halo", "Ibis",
    "Juno", "Kite", "Lyra", "Mistral", "Nova", "Onyx", "Pika", "Quest", "Rigel",
    "Sirio", "Tessa", "Ulme", "Vela", "Wega", "Xeno", "Yuka", "Zenit", "Aria",
    "Brise", "Cedro", "Delta", "Elan", "Faro", "Gale", "Horizon", "Iskra",
    "Jade", "Kobalt", "Levante", "Mira", "Nimbus",
)  # fmt: skip

_MODELLVARIANTEN: Final[tuple[str, ...]] = (
    "", " 1.2", " 1.4", " 1.6", " 2.0", " 2.5", " GT", " GTX", " Sport",
    " Comfort", " Avant", " Kombi", " Coupé", " Cross", " Prime",
)  # fmt: skip

_VU_NAMEN: Final[tuple[str, ...]] = (
    "Nordstern Versicherung AG",
    "Alpenwacht Versicherung AG",
    "Hansekrone Assekuranz AG",
    "Rheinlicht Versicherung AG",
    "Elbwacht Versicherung AG",
    "Silberdistel Assekuranz AG",
    "Weserstern Versicherung AG",
    "Taunusfels Versicherung AG",
    "Ostseeanker Assekuranz AG",
    "Schwarzwaldhort Versicherung AG",
    "Donauklar Versicherung AG",
    "Spreelicht Assekuranz AG",
    "Harzquell Versicherung AG",
    "Mainbogen Versicherung AG",
    "Lausitzkranz Versicherung AG",
)

#: Gewichte der Quellschnittstellen bei der Zuordnung zu Anbietern.
_SCHNITTSTELLEN_GEWICHTE: Final[tuple[float, float, float, float]] = (0.35, 0.30, 0.20, 0.15)

#: Ankerwerte der SF-Beitragssaetze (spec/01, Abschnitt 2.6).
_SF_SATZ_SF1: Final[int] = 58
_SF_SATZ_SF50: Final[int] = 16
_SF_KRUEMMUNG: Final[float] = 1.7
_SF_SONDERSAETZE: Final[tuple[tuple[str, int], ...]] = (
    ("M", 245),
    ("S", 155),
    ("0", 100),
    ("1/2", 70),
)

#: Zeichenvorrat der Typschluesselnummer (R-008).
_TSN_ALPHABET: Final[str] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
_BEZIRK_ALPHABET: Final[str] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


# ---------------------------------------------------------------------------
# Allgemeine Hilfsfunktionen
# ---------------------------------------------------------------------------


def _verteile(
    gesamt: int,
    gewichte: Sequence[float],
    *,
    mindestens: int = 0,
    hoechstens: int | None = None,
) -> list[int]:
    """Verteilt eine ganze Zahl proportional auf Gewichte (Hare-Niemeyer).

    Das groesste-Reste-Verfahren ist deterministisch und summiert exakt auf
    ``gesamt``. Grenzen werden nachtraeglich durchgesetzt; der dabei entstehende
    Ueberschuss wird in fester Reihenfolge umverteilt.

    Args:
        gesamt: Zu verteilende Gesamtmenge.
        gewichte: Nicht negative Gewichte.
        mindestens: Untergrenze je Eintrag.
        hoechstens: Obergrenze je Eintrag, ``None`` fuer unbegrenzt.

    Returns:
        Eine Liste ganzer Zahlen, die exakt auf ``gesamt`` summiert.

    Raises:
        ValueError: Wenn die Grenzen die Gesamtmenge nicht zulassen.
    """
    anzahl = len(gewichte)
    grenze = hoechstens if hoechstens is not None else gesamt
    if anzahl * mindestens > gesamt or anzahl * grenze < gesamt:
        raise ValueError(
            f"{gesamt} laesst sich nicht auf {anzahl} Eintraege mit Grenzen "
            f"[{mindestens}, {grenze}] verteilen"
        )
    summe = float(sum(gewichte))
    if summe <= 0:
        raise ValueError("Gewichte muessen in Summe positiv sein")

    roh = [gewicht / summe * gesamt for gewicht in gewichte]
    anteile = [math.floor(wert) for wert in roh]
    reihenfolge = sorted(range(anzahl), key=lambda i: (-(roh[i] - anteile[i]), i))
    for index in reihenfolge[: gesamt - sum(anteile)]:
        anteile[index] += 1

    anteile = [min(max(wert, mindestens), grenze) for wert in anteile]
    differenz = gesamt - sum(anteile)
    while differenz != 0:
        schritt = 1 if differenz > 0 else -1
        veraendert = False
        for index in reihenfolge:
            if differenz == 0:
                break
            neu = anteile[index] + schritt
            if mindestens <= neu <= grenze:
                anteile[index] = neu
                differenz -= schritt
                veraendert = True
        if not veraendert:  # pragma: no cover - durch die Eingangspruefung ausgeschlossen
            raise ValueError("Verteilung mit den gegebenen Grenzen nicht moeglich")
    return anteile


def _quantil_klasse(
    latent: npt.NDArray[np.float64], unten: int, oben: int
) -> npt.NDArray[np.int64]:
    """Bildet standardnormale Werte auf ein ganzzahliges Klassenintervall ab.

    Ergebnis ist eine um die Mitte zentrierte, diskretisierte Normalverteilung
    ueber ``[unten, oben]`` — genau die in ``spec/01``, Abschnitt 2.2 geforderte
    Form.

    Args:
        latent: Standardnormale Werte.
        unten: Kleinste Klasse.
        oben: Groesste Klasse.

    Returns:
        Die Klassen als ganzzahliges Feld.
    """
    stufen = oben - unten + 1
    wahrscheinlichkeit = np.array(
        [0.5 * (1.0 + math.erf(float(wert) / math.sqrt(2.0))) for wert in latent]
    )
    klassen = unten + np.floor(wahrscheinlichkeit * stufen).astype(np.int64)
    ergebnis: npt.NDArray[np.int64] = np.clip(klassen, unten, oben)
    return ergebnis


def _ziehe_ohne_zuruecklegen(
    rng: Generator, obergrenze: int, anzahl: int
) -> npt.NDArray[np.int64]:
    """Zieht ``anzahl`` verschiedene Indizes aus ``range(obergrenze)``, aufsteigend sortiert."""
    if anzahl > obergrenze:
        raise ValueError(f"{anzahl} verschiedene Werte passen nicht in {obergrenze} Moeglichkeiten")
    gezogen: npt.NDArray[np.int64] = np.sort(rng.choice(obergrenze, size=anzahl, replace=False))
    return gezogen


def _basis36(zahl: int, laenge: int, alphabet: str) -> str:
    """Stellt eine Zahl mit festem Alphabet und fester Laenge dar."""
    basis = len(alphabet)
    zeichen = []
    for _ in range(laenge):
        zahl, rest = divmod(zahl, basis)
        zeichen.append(alphabet[rest])
    return "".join(reversed(zeichen))


# ---------------------------------------------------------------------------
# plz_ort.csv
# ---------------------------------------------------------------------------


def baue_plz_ort(config: Config) -> pd.DataFrame:
    """Erzeugt ``plz_ort.csv``.

    Aufbau: Jede Leitzone bekommt einen Anteil der Postleitzahlen und der
    Zulassungsbezirke. Innerhalb einer Zone erhaelt jeder Bezirk einen
    zusammenhaengenden Nummernblock — so wie ein realer Kreis einen
    zusammenhaengenden PLZ-Bereich abdeckt. Eine PLZ gehoert zu genau einem
    Bezirk (vereinfachende Annahme aus spec/01, Abschnitt 2.1).

    Args:
        config: Geladene Konfiguration.

    Returns:
        Den Datenrahmen mit ``plz``, ``ort``, ``bundesland``, ``zulassungsbezirk``.
    """
    rng = generator(lauf_seed(config.master_seed, Strom.REFERENZ, _SEED_PLZ_ORT))
    n_plz = config.referenzdaten.n_plz
    n_bezirke = config.referenzdaten.n_zulassungsbezirke

    zonengewichte = [gewicht for _, gewicht, _ in _LEITZONEN]
    plz_je_zone = _verteile(n_plz, zonengewichte, mindestens=1)
    bezirke_je_zone = _verteile(n_bezirke, zonengewichte, mindestens=1)

    bezirkscodes = _erzeuge_bezirkscodes(rng, n_bezirke)

    plz_werte: list[str] = []
    bezirk_werte: list[str] = []
    land_werte: list[str] = []
    naechster_code = 0

    for (ziffer, _, laender), anzahl_plz, anzahl_bezirke in zip(
        _LEITZONEN, plz_je_zone, bezirke_je_zone, strict=True
    ):
        start = _LEITZONE_0_START if ziffer == 0 else ziffer * 10_000
        ende = ziffer * 10_000 + 9_999
        kapazitaet = ende - start + 1
        blockgroessen = _verteile(kapazitaet, [1.0] * anzahl_bezirke, mindestens=1)

        # Groesse eines Bezirks: log-normal, damit einzelne Bezirke viele
        # Postleitzahlen tragen (Grossstadt) und andere wenige (Landkreis).
        bezirksgewichte = np.exp(rng.normal(0.0, 0.7, size=anzahl_bezirke))
        plz_je_bezirk = _verteile(
            anzahl_plz,
            bezirksgewichte.tolist(),
            mindestens=1,
            hoechstens=min(blockgroessen),
        )

        laendercodes = [code for code, _ in laender]
        laendergewichte = [gewicht for _, gewicht in laender]
        zuordnung = rng.choice(len(laendercodes), size=anzahl_bezirke, p=laendergewichte)

        blockstart = start
        for index in range(anzahl_bezirke):
            code = bezirkscodes[naechster_code + index]
            land = laendercodes[int(zuordnung[index])]
            versatz = _ziehe_ohne_zuruecklegen(rng, blockgroessen[index], plz_je_bezirk[index])
            for schritt in versatz:
                plz_werte.append(f"{blockstart + int(schritt):05d}")
                bezirk_werte.append(code)
                land_werte.append(land)
            blockstart += blockgroessen[index]
        naechster_code += anzahl_bezirke

    reihenfolge = np.argsort(np.array(plz_werte), kind="stable")
    plz_sortiert = [plz_werte[i] for i in reihenfolge]
    orte = _erzeuge_ortsnamen(rng, len(plz_sortiert))

    return pd.DataFrame(
        {
            "plz": plz_sortiert,
            "ort": orte,
            "bundesland": [land_werte[i] for i in reihenfolge],
            "zulassungsbezirk": [bezirk_werte[i] for i in reihenfolge],
        }
    )


def _erzeuge_bezirkscodes(rng: Generator, anzahl: int) -> list[str]:
    """Zieht eindeutige Unterscheidungszeichen aus ein bis drei Grossbuchstaben.

    Die fertige Liste wird gemischt: Sonst laegen alle einbuchstabigen Kennzeichen
    in Leitzone 0. Real sind kurze Kennzeichen ueber das ganze Bundesgebiet
    verteilt (B, K, M, S).
    """
    je_laenge = _verteile(anzahl, list(_BEZIRK_LAENGEN_GEWICHTE), mindestens=1)
    codes: list[str] = []
    for laenge, menge in enumerate(je_laenge, start=1):
        moeglichkeiten = len(_BEZIRK_ALPHABET) ** laenge
        indizes = _ziehe_ohne_zuruecklegen(rng, moeglichkeiten, menge)
        codes.extend(_basis36(int(wert), laenge, _BEZIRK_ALPHABET) for wert in indizes)
    return [codes[i] for i in rng.permutation(len(codes))]


def _erzeuge_ortsnamen(rng: Generator, anzahl: int) -> list[str]:
    """Erzeugt synthetische, deutsch anmutende Ortsnamen."""
    bestimmung = rng.integers(0, len(_BESTIMMUNGSWOERTER), size=anzahl)
    grundwort = rng.integers(0, len(_GRUNDWOERTER), size=anzahl)
    zusatz = rng.integers(0, len(_ORTSZUSAETZE), size=anzahl)
    hat_zusatz = rng.random(anzahl) < _P_ORTSZUSATZ
    hat_bad = rng.random(anzahl) < _P_BAD

    namen: list[str] = []
    for index in range(anzahl):
        name = _BESTIMMUNGSWOERTER[int(bestimmung[index])] + _GRUNDWOERTER[int(grundwort[index])]
        if hat_bad[index]:
            name = f"Bad {name}"
        if hat_zusatz[index]:
            name += _ORTSZUSAETZE[int(zusatz[index])]
        namen.append(name)
    return namen


# ---------------------------------------------------------------------------
# regionalklassen.csv
# ---------------------------------------------------------------------------


def baue_regionalklassen(config: Config, plz_ort: pd.DataFrame) -> pd.DataFrame:
    """Erzeugt ``regionalklassen.csv``.

    Die drei Klassen haengen an einem gemeinsamen latenten Risikoindex je Bezirk
    und sind dadurch untereinander korreliert, ohne identisch zu sein. Das ist
    fachlich richtig — ein Bezirk mit hoher Schadenlast ist es meist in allen
    drei Deckungen — und macht den Referenzabgleich R-058 aussagekraeftig.

    Args:
        config: Geladene Konfiguration.
        plz_ort: Bereits erzeugte Tabelle ``plz_ort``.

    Returns:
        Den Datenrahmen mit einer Zeile je Zulassungsbezirk.
    """
    rng = generator(lauf_seed(config.master_seed, Strom.REFERENZ, _SEED_REGIONALKLASSEN))
    bezirke = sorted(set(plz_ort["zulassungsbezirk"]))
    anzahl = len(bezirke)

    risiko = rng.normal(0.0, 1.0, size=anzahl)
    spalten: dict[str, np.ndarray] = {}
    for name, (unten, oben) in (
        ("regionalklasse_hp", wb.REGIONALKLASSE_HP),
        ("regionalklasse_tk", wb.REGIONALKLASSE_TK),
        ("regionalklasse_vk", wb.REGIONALKLASSE_VK),
    ):
        # Gewichte 0,8 und 0,6 ergeben zusammen wieder Varianz 1.
        latent = 0.8 * risiko + 0.6 * rng.normal(0.0, 1.0, size=anzahl)
        spalten[name] = _quantil_klasse(latent, unten, oben)

    return pd.DataFrame({"zulassungsbezirk": bezirke, **spalten})


# ---------------------------------------------------------------------------
# typklassen.csv
# ---------------------------------------------------------------------------


def baue_typklassen(config: Config) -> pd.DataFrame:
    """Erzeugt ``typklassen.csv``.

    Jeder Hersteller bekommt genau eine HSN, jedes Modell eine innerhalb der HSN
    eindeutige TSN — so ist das Schluesselpaar wie in der Zulassungsbescheinigung
    Teil I aufgebaut. Leistung, Neupreis und die drei Typklassen haengen
    zusammen, damit R-051 (Abgleich der abgeleiteten Felder) nicht gegen
    Zufallsrauschen prueft.

    Args:
        config: Geladene Konfiguration.

    Returns:
        Den Datenrahmen mit einer Zeile je HSN/TSN-Kombination.

    Raises:
        ValueError: Wenn mehr Hersteller angefordert werden, als Namen hinterlegt sind.
    """
    rng = generator(lauf_seed(config.master_seed, Strom.REFERENZ, _SEED_TYPKLASSEN))
    n_zeilen = config.referenzdaten.n_typklassen
    n_hersteller = config.referenzdaten.n_hersteller
    if n_hersteller > len(_HERSTELLER):
        raise ValueError(
            f"Es sind {len(_HERSTELLER)} Herstellernamen hinterlegt, "
            f"angefordert wurden {n_hersteller}"
        )

    hsn_werte = _ziehe_ohne_zuruecklegen(rng, 9_999, n_hersteller) + 1
    namen = list(_HERSTELLER[:n_hersteller])
    modelle_je_hersteller = _verteile(
        n_zeilen, np.exp(rng.normal(0.0, 0.6, size=n_hersteller)).tolist(), mindestens=1
    )

    hsn_spalte: list[str] = []
    tsn_spalte: list[str] = []
    hersteller_spalte: list[str] = []
    for index, anzahl in enumerate(modelle_je_hersteller):
        tsn_indizes = _ziehe_ohne_zuruecklegen(rng, len(_TSN_ALPHABET) ** 3, anzahl)
        hsn_spalte.extend([f"{int(hsn_werte[index]):04d}"] * anzahl)
        tsn_spalte.extend(_basis36(int(wert), 3, _TSN_ALPHABET) for wert in tsn_indizes)
        hersteller_spalte.extend([namen[index]] * anzahl)

    stamm = rng.integers(0, len(_MODELLSTAEMME), size=n_zeilen)
    variante = rng.integers(0, len(_MODELLVARIANTEN), size=n_zeilen)
    modell_spalte = [
        _MODELLSTAEMME[int(stamm[i])] + _MODELLVARIANTEN[int(variante[i])] for i in range(n_zeilen)
    ]

    antriebe = tuple(Antriebsart)
    antrieb_index = rng.choice(len(antriebe), size=n_zeilen, p=[0.45, 0.28, 0.11, 0.13, 0.03])
    antrieb_spalte = [antriebe[int(i)].value for i in antrieb_index]
    ist_elektrisch = np.array(
        [wert in (Antriebsart.ELEKTRO.value, Antriebsart.HYBRID.value) for wert in antrieb_spalte]
    )

    unten_kw, oben_kw = wb.GENERATOR_LEISTUNG_KW
    leistung = np.exp(rng.normal(math.log(105.0), 0.42, size=n_zeilen))
    leistung = np.where(ist_elektrisch, leistung * 1.25, leistung)
    leistung_kw = np.clip(np.rint(leistung), unten_kw, oben_kw).astype(np.int64)

    unten_preis, oben_preis = wb.GENERATOR_NEUPREIS_EUR
    preis_roh = (6_000.0 + 330.0 * leistung_kw) * np.exp(rng.normal(0.0, 0.28, size=n_zeilen))
    preis_gerundet = np.clip(
        np.rint(preis_roh / 10.0) * 10.0, float(unten_preis), float(oben_preis)
    )
    neupreis = [von_float(float(wert)) for wert in preis_gerundet]

    # Latenter Schadenbedarf: Leistung und Preis bestimmen die Typklasse
    # ueberwiegend, ein Rauschterm bildet modellspezifische Unterschiede ab.
    z_leistung = (np.log(leistung_kw) - np.mean(np.log(leistung_kw))) / np.std(np.log(leistung_kw))
    z_preis = (np.log(preis_gerundet) - np.mean(np.log(preis_gerundet))) / np.std(
        np.log(preis_gerundet)
    )
    basis = 0.45 * z_leistung + 0.45 * z_preis
    typklassen: dict[str, np.ndarray] = {}
    for name, (unten, oben) in (
        ("typklasse_hp", wb.TYPKLASSE_HP),
        ("typklasse_tk", wb.TYPKLASSE_TK),
        ("typklasse_vk", wb.TYPKLASSE_VK),
    ):
        latent = basis + 0.55 * rng.normal(0.0, 1.0, size=n_zeilen)
        latent = latent / np.std(latent)
        typklassen[name] = _quantil_klasse(latent, unten, oben)

    rahmen = pd.DataFrame(
        {
            "hsn": hsn_spalte,
            "tsn": tsn_spalte,
            "hersteller": hersteller_spalte,
            "modell": modell_spalte,
            "leistung_kw": leistung_kw,
            "antriebsart": antrieb_spalte,
            **typklassen,
            "neupreis_eur": neupreis,
        }
    )
    return rahmen.sort_values(["hsn", "tsn"], kind="stable").reset_index(drop=True)


# ---------------------------------------------------------------------------
# vu_stammdaten.csv
# ---------------------------------------------------------------------------


def baue_vu_stammdaten(config: Config) -> pd.DataFrame:
    """Erzeugt ``vu_stammdaten.csv``.

    Die Marktanteile summieren nach der Rundung auf sechs Nachkommastellen
    **exakt** auf 1; die Restdifferenz wird dem groessten Anbieter zugeschlagen.
    Die Zuordnung Anbieter auf Quellschnittstelle ist fest und traegt spaeter die
    Multi-Source-Fehlerklasse (spec/01, Abschnitt 2.4).

    Args:
        config: Geladene Konfiguration.

    Returns:
        Den Datenrahmen mit einer Zeile je Anbieter.

    Raises:
        ValueError: Wenn mehr Anbieter angefordert werden, als Namen hinterlegt sind.
    """
    rng = generator(lauf_seed(config.master_seed, Strom.REFERENZ, _SEED_VU_STAMMDATEN))
    anzahl = config.referenzdaten.n_vu
    if anzahl > len(_VU_NAMEN):
        raise ValueError(
            f"Es sind {len(_VU_NAMEN)} Anbieternamen hinterlegt, angefordert wurden {anzahl}"
        )

    nummern = _ziehe_ohne_zuruecklegen(rng, 90_000, anzahl) + 10_000
    namen = list(_VU_NAMEN[:anzahl])

    # Rechtsschiefe Marktanteile: wenige grosse, viele kleine Anbieter.
    roh = np.array([1.0 / (rang + 1.5) ** 1.1 for rang in range(anzahl)])
    roh = roh[rng.permutation(anzahl)]
    anteile = roh / roh.sum()
    gerundet = [Decimal(repr(float(wert))).quantize(Decimal("0.000001")) for wert in anteile]
    rest = Decimal(1) - sum(gerundet)
    groesster = max(range(anzahl), key=lambda i: (gerundet[i], -i))
    gerundet[groesster] += rest

    schnittstellen = tuple(Quellschnittstelle)
    mengen = _verteile(anzahl, list(_SCHNITTSTELLEN_GEWICHTE), mindestens=1)
    zuordnung = [
        schnittstellen[index].value for index, menge in enumerate(mengen) for _ in range(menge)
    ]
    zuordnung = [zuordnung[i] for i in rng.permutation(anzahl)]

    return pd.DataFrame(
        {
            "vu_nummer": [f"{int(wert):05d}" for wert in nummern],
            "vu_name": namen,
            "marktanteil": [f"{wert:f}" for wert in gerundet],
            "quell_schnittstelle": zuordnung,
        }
    )


# ---------------------------------------------------------------------------
# zuers_zonen.csv
# ---------------------------------------------------------------------------


def baue_zuers_zonen(config: Config, plz_ort: pd.DataFrame) -> pd.DataFrame:
    """Erzeugt ``zuers_zonen.csv``.

    Die Zonenanteile werden **exakt** getroffen: Die Zellzahlen je Zone stehen
    vorab fest, die Zuordnung erfolgt ueber die Rangfolge eines latenten
    Gefaehrdungsindex. Dieser Index traegt einen Bezirksanteil, sodass benachbarte
    Postleitzahlen aehnliche Zonen bekommen — Hochwassergefaehrdung ist
    raeumlich geclustert, nicht unabhaengig gestreut.

    Args:
        config: Geladene Konfiguration.
        plz_ort: Bereits erzeugte Tabelle ``plz_ort``.

    Returns:
        Den Datenrahmen mit ``plz`` und ``zuers_zone``.
    """
    rng = generator(lauf_seed(config.master_seed, Strom.REFERENZ, _SEED_ZUERS))
    anteile = config.referenzdaten.zuers_anteile
    plz = list(plz_ort["plz"])
    bezirke = list(plz_ort["zulassungsbezirk"])
    anzahl = len(plz)

    bezirksliste = sorted(set(bezirke))
    bezirkseffekt = dict(
        zip(bezirksliste, rng.normal(0.0, 1.0, size=len(bezirksliste)), strict=True)
    )
    index = np.array([bezirkseffekt[code] for code in bezirke]) + 0.8 * rng.normal(
        0.0, 1.0, size=anzahl
    )

    # Absteigend nach Gefaehrdung; der Sekundaerschluessel haelt die Reihenfolge
    # bei gleichem Index eindeutig.
    reihenfolge = sorted(range(anzahl), key=lambda i: (-float(index[i]), plz[i]))
    mengen = _verteile(anzahl, list(anteile), mindestens=1)

    zonen = [0] * anzahl
    position = 0
    for zone in (4, 3, 2, 1):
        menge = mengen[zone - 1]
        for i in reihenfolge[position : position + menge]:
            zonen[i] = zone
        position += menge

    return pd.DataFrame({"plz": plz, "zuers_zone": zonen})


# ---------------------------------------------------------------------------
# sf_beitragssatz.csv
# ---------------------------------------------------------------------------


def baue_sf_beitragssatz() -> pd.DataFrame:
    """Erzeugt ``sf_beitragssatz.csv``.

    Der Verlauf ueber die numerischen Klassen ist konvex: Die ersten schadenfreien
    Jahre bringen viel, die spaeteren wenig. Verankert an SF 1 mit 58 Prozent und
    SF 50 mit 16 Prozent (spec/01, Abschnitt 2.6).

    **Monotonie:** ``spec/01``, Abschnitt 2.6 fordert einen **nicht-steigenden**
    Verlauf, ``satz(SF n+1) <= satz(SF n)``. Plateaus sind ausdruecklich zulaessig
    und erwuenscht: Reale Beitragssatztabellen flachen bei hohen
    Schadenfreiheitsklassen ab, zwischen SF 40 und SF 45 unterscheidet sich der
    Satz bei vielen Versicherern nicht mehr. Die Plateaus bilden die Realitaet ab.

    ``min(..., letzter)`` setzt die Bedingung durch: Der Satz kann nie steigen,
    auch wenn die Rundung es sonst zuliesse.

    Returns:
        Den Datenrahmen mit ``sf_klasse`` und ``beitragssatz_prozent``.
    """
    sondernamen = tuple(name for name, _ in _SF_SONDERSAETZE)
    if set(sondernamen) != set(SF_KLASSEN_SONDER):
        raise ValueError(
            f"Sonderklassen weichen vom Katalog ab: {sorted(sondernamen)} "
            f"statt {sorted(SF_KLASSEN_SONDER)}"
        )

    klassen: list[str] = [name for name, _ in _SF_SONDERSAETZE]
    saetze: list[int] = [satz for _, satz in _SF_SONDERSAETZE]

    anzahl = len(SF_KLASSEN_NUMERISCH)
    spanne = _SF_SATZ_SF1 - _SF_SATZ_SF50
    letzter = _SF_SATZ_SF1
    for stufe, name in enumerate(SF_KLASSEN_NUMERISCH, start=1):
        anteil = (anzahl - stufe) / (anzahl - 1)
        roh = _SF_SATZ_SF50 + spanne * anteil**_SF_KRUEMMUNG
        satz = min(int(Decimal(repr(roh)).quantize(Decimal(1), rounding=ROUND_HALF_UP)), letzter)
        letzter = satz
        klassen.append(name)
        saetze.append(satz)

    return pd.DataFrame({"sf_klasse": klassen, "beitragssatz_prozent": saetze})


# ---------------------------------------------------------------------------
# waehrungen.csv
# ---------------------------------------------------------------------------


def baue_waehrungen() -> pd.DataFrame:
    """Erzeugt ``waehrungen.csv`` aus dem ISO-4217-Katalog des Pakets ``pycountry``.

    Grundlage der ersten Stufe von R-012 (spec/01, Abschnitt 2.7).

    Die Liste wird **nicht** aus dem Gedaechtnis in den Quelltext geschrieben. Eine
    falsche Waehrungsliste faellt niemandem auf und macht die Regel wertlos: Die
    Regel meldete dann Fehler, wo keine sind, oder — schlimmer — meldete keine, wo
    welche sind. ``pycountry`` fuehrt den offiziellen Katalog mit.

    Die Version von ``pycountry`` ist deshalb in ``requirements.txt`` gepinnt: Sie
    bestimmt den Inhalt der Datei und damit ihren Hashwert. Ein Wechsel der Version
    kann die Tabelle veraendern (ISO 4217 wird fortgeschrieben) und ist wie jede
    andere Aenderung an den Referenzdaten zu behandeln.

    Sortiert nach ``code``, damit die Datei reproduzierbar ist — die Reihenfolge,
    in der ``pycountry`` seine Eintraege liefert, ist keine zugesicherte
    Eigenschaft.

    Returns:
        Den Datenrahmen mit ``code``, ``name`` und ``numerisch``.

    Raises:
        ValueError: Wenn der Katalog leer ist oder ein Eintrag unvollstaendig.
    """
    import pycountry  # noqa: PLC0415  (nur beim Aufbau der Referenzdaten gebraucht)

    zeilen: list[tuple[str, str, int]] = []
    for waehrung in pycountry.currencies:
        code = waehrung.alpha_3
        name = waehrung.name
        numerisch = getattr(waehrung, "numeric", None)
        if not code or not name or not numerisch:
            raise ValueError(f"Unvollstaendiger ISO-4217-Eintrag: {code!r} / {name!r}")
        zeilen.append((code, name, int(numerisch)))

    if not zeilen:
        raise ValueError("pycountry lieferte keinen einzigen Waehrungseintrag")

    zeilen.sort()
    return pd.DataFrame(
        {
            "code": [code for code, _, _ in zeilen],
            "name": [name for _, name, _ in zeilen],
            "numerisch": [numerisch for _, _, numerisch in zeilen],
        }
    )


# ---------------------------------------------------------------------------
# Ablauf
# ---------------------------------------------------------------------------


def baue_referenzdaten(config: Config, ziel: Path, *, still: bool = False) -> dict[str, Path]:
    """Erzeugt alle sieben Referenztabellen und schreibt sie als CSV.

    Args:
        config: Geladene Konfiguration.
        ziel: Zielverzeichnis; wird bei Bedarf angelegt.
        still: Unterdrueckt die Fortschrittsausgabe.

    Returns:
        Eine Abbildung Tabellenname auf geschriebene Datei.
    """
    ziel.mkdir(parents=True, exist_ok=True)

    plz_ort = baue_plz_ort(config)
    tabellen: dict[str, pd.DataFrame] = {
        "plz_ort": plz_ort,
        "regionalklassen": baue_regionalklassen(config, plz_ort),
        "typklassen": baue_typklassen(config),
        "vu_stammdaten": baue_vu_stammdaten(config),
        "zuers_zonen": baue_zuers_zonen(config, plz_ort),
        "sf_beitragssatz": baue_sf_beitragssatz(),
        "waehrungen": baue_waehrungen(),
    }

    geschrieben: dict[str, Path] = {}
    for name in sorted(tabellen):
        rahmen = tabellen[name][list(SPALTEN[name])]
        pfad = ziel / f"{name}.csv"
        rahmen.to_csv(pfad, index=False, lineterminator="\n", encoding="utf-8")
        geschrieben[name] = pfad
        if not still:
            print(f"  {name + '.csv':<24} {len(rahmen):>6} Zeilen")
    return geschrieben


def main(argumente: Sequence[str] | None = None) -> int:
    """Einstiegspunkt des Skripts.

    Args:
        argumente: Kommandozeilenargumente; ``None`` nimmt ``sys.argv``.

    Returns:
        Den Rueckgabewert des Prozesses.
    """
    parser = argparse.ArgumentParser(
        description="Erzeugt die Referenztabellen unter data/reference deterministisch neu."
    )
    parser.add_argument("--config", type=Path, default=None, help="Pfad zur Konfigurationsdatei")
    parser.add_argument(
        "--ziel", type=Path, default=None, help="Zielverzeichnis statt pfade.reference"
    )
    parser.add_argument("--seed", type=int, default=None, help="Master-Seed uebersteuern")
    parser.add_argument("--still", action="store_true", help="Keine Fortschrittsausgabe")
    optionen = parser.parse_args(argumente)

    config = lade_config(optionen.config)
    if optionen.seed is not None:
        config = dataclasses.replace(config, master_seed=optionen.seed)
    ziel = optionen.ziel if optionen.ziel is not None else config.pfade.reference

    if not optionen.still:
        print(f"Referenzdaten werden erzeugt (master_seed={config.master_seed}) nach {ziel}")
    baue_referenzdaten(config, ziel, still=optionen.still)
    if not optionen.still:
        print("Fertig.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
