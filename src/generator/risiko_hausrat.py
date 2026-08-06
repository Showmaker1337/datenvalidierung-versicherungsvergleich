"""Hausratrisiko — nur in der Sparte 130.

Die ZUERS-Zone wird ueber die Postleitzahl **aus der Referenz uebernommen**
(spec/01, Abschnitt 3.4). Wohnflaeche und Baujahr folgen der Gebaeude- und
Wohnungszaehlung des Zensus 2022, nicht einer Gleichverteilung.

Die Versicherungssumme haengt an der Wohnflaeche: Sie wird aus der branchen-
ueblichen Faustregel von 650 Euro je Quadratmeter mit Streuung gebildet. Der
Unterversicherungsverzicht wird nur dort gesetzt, wo die Summe diese Grenze
erreicht — sonst waere R-040 schon auf sauberen Daten verletzt.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import TYPE_CHECKING, Final

from src.common import wertebereiche as wb
from src.common.enums import BAUARTKLASSEN, Gebaeudeart
from src.common.geld import runde
from src.common.serialisierung import SPALTEN_JE_ENTITAET, typisierter_rahmen
from src.generator.verteilungen import (
    erzeuge_uuids,
    waehle_index,
    ziehe_ganzzahl_lognormal,
    ziehe_lognormal,
    ziehe_wahrheit,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence

    import pandas as pd
    from numpy.random import Generator

    from src.common.config import Config

__all__ = ["RisikoHausrat", "erzeuge_risiko_hausrat"]

#: Wohnflaeche: log-normal um 85 Quadratmeter.
#:
#: Quelle: Zensus 2022, Gebaeude- und Wohnungszaehlung. Die durchschnittliche
#: Wohnflaeche je Wohnung liegt bei rund 92 Quadratmetern; der Median liegt wegen
#: der Rechtsschiefe darunter.
_WOHNFLAECHE_MEDIAN: Final[float] = 85.0
_WOHNFLAECHE_SIGMA: Final[float] = 0.42

#: Streuung der Versicherungssumme um die Faustregel von 650 Euro je Quadratmeter.
_VS_SIGMA: Final[float] = 0.22

#: Rasterung der Versicherungssumme in Euro.
_VS_SCHRITT: Final[int] = 1_000

#: Wahrscheinlichkeit des Unterversicherungsverzichts, sofern die Summe reicht.
_P_UNTERVERSICHERUNGSVERZICHT: Final[float] = 0.72

#: Baualtersklassen mit Anteilen (Zensus 2022, Gebaeude- und Wohnungszaehlung).
#:
#: Die letzte Klasse endet am Jahr des Stichtags; sie wird zur Laufzeit gesetzt.
_BAUALTER: Final[tuple[tuple[int, int, float], ...]] = (
    (wb.GENERATOR_BAUJAHR_UNTERGRENZE, 1918, 0.12),
    (1919, 1948, 0.12),
    (1949, 1978, 0.32),
    (1979, 1990, 0.13),
    (1991, 2000, 0.12),
    (2001, 2010, 0.08),
    (2011, 2022, 0.09),
    (2023, 0, 0.02),
)

#: Bauartklassen mit Gewichten (GDV Anlage 12). Massivbauweise ueberwiegt deutlich.
#: **Modellannahme.**
_BAUARTKLASSE_GEWICHTE: Final[Mapping[str, float]] = {
    "0": 0.05,
    "1": 0.42,
    "2": 0.18,
    "3": 0.10,
    "4": 0.05,
    "5": 0.04,
    "6": 0.03,
    "7": 0.02,
    "8": 0.02,
    "A": 0.01,
    "B": 0.01,
    "C": 0.01,
    "D": 0.01,
    "E": 0.01,
    "F": 0.01,
    "G": 0.01,
    "H": 0.01,
    "I": 0.01,
}

#: Gebaeudeart mit Gewichten (Modellannahme, an der Zensus-Struktur orientiert).
_GEBAEUDEART_GEWICHTE: Final[tuple[tuple[Gebaeudeart, float], ...]] = (
    (Gebaeudeart.EFH, 0.28),
    (Gebaeudeart.MIETWOHNUNG, 0.22),
    (Gebaeudeart.ETW, 0.18),
    (Gebaeudeart.MFH, 0.16),
    (Gebaeudeart.RH, 0.09),
    (Gebaeudeart.DHH, 0.07),
)

#: Gebaeudearten, bei denen ein Stockwerk gefuellt wird. Bei ETW und MIETWOHNUNG
#: verlangt spec/01, Abschnitt 3.4 das ausdruecklich.
_MIT_STOCKWERK: Final[frozenset[str]] = frozenset(
    {Gebaeudeart.ETW.value, Gebaeudeart.MIETWOHNUNG.value, Gebaeudeart.MFH.value}
)

#: Stockwerke mit Gewichten, beginnend beim Souterrain.
_STOCKWERK_GEWICHTE: Final[tuple[tuple[int, float], ...]] = (
    (-1, 0.03),
    (0, 0.22),
    (1, 0.23),
    (2, 0.20),
    (3, 0.15),
    (4, 0.09),
    (5, 0.05),
    (6, 0.02),
    (7, 0.01),
)

#: Wahrscheinlichkeit des Elementarschutzes je ZUERS-Zone.
#:
#: In Zone 4 ist der Einschluss selten (spec/01, Abschnitt 3.4): Dort ist der
#: Schutz oft nur mit hohen Zuschlaegen oder gar nicht erhaeltlich.
_P_ELEMENTAR_JE_ZONE: Final[Mapping[int, float]] = {1: 0.55, 2: 0.45, 3: 0.30, 4: 0.10}

#: Stufen des Fahrradsublimits mit Gewichten (Modellannahme).
_SUBLIMIT_FAHRRAD: Final[tuple[tuple[Decimal, float], ...]] = (
    (Decimal("0.00"), 0.30),
    (Decimal("500.00"), 0.16),
    (Decimal("1000.00"), 0.18),
    (Decimal("1500.00"), 0.12),
    (Decimal("2000.00"), 0.11),
    (Decimal("3000.00"), 0.07),
    (Decimal("5000.00"), 0.04),
    (Decimal("10000.00"), 0.02),
)

#: Anteile der Versicherungssumme, die als Wertsachensublimit vereinbart werden.
_SUBLIMIT_WERTSACHEN_ANTEILE: Final[tuple[tuple[Decimal, float], ...]] = (
    (Decimal("0.00"), 0.10),
    (Decimal("0.05"), 0.14),
    (Decimal("0.10"), 0.22),
    (Decimal("0.15"), 0.18),
    (Decimal("0.20"), 0.18),
    (Decimal("0.25"), 0.10),
    (Decimal("0.30"), 0.08),
)

#: Rasterung der Sublimits in Euro.
_SUBLIMIT_SCHRITT: Final[Decimal] = Decimal(100)


@dataclass(frozen=True, slots=True)
class RisikoHausrat:
    """Hausratrisiken samt der fuer die Beitragsberechnung gebrauchten Groessen.

    Alle Folgen sind ueber die Position der Hausrat-Anfrage indiziert.

    Attributes:
        rahmen: Die Entitaet ``risiko_hausrat``.
        versicherungssumme_eur: Versicherungssumme je Hausrat-Anfrage.
        zuers_zone: ZUERS-Zone je Hausrat-Anfrage.
        bauartklasse: Bauartklasse je Hausrat-Anfrage.
        elementar_eingeschlossen: Elementarschutz je Hausrat-Anfrage.
    """

    rahmen: pd.DataFrame
    versicherungssumme_eur: tuple[Decimal, ...]
    zuers_zone: tuple[int, ...]
    bauartklasse: tuple[str, ...]
    elementar_eingeschlossen: tuple[bool, ...]


def _ziehe_baujahre(rng: Generator, anzahl: int, stichtagsjahr: int) -> list[int]:
    """Zieht Baujahre aus den Baualtersklassen des Zensus (R-023: nie in der Zukunft)."""
    gruppen = [
        (unten, oben if oben > 0 else stichtagsjahr, anteil) for unten, oben, anteil in _BAUALTER
    ]
    indizes = waehle_index(rng, anzahl, [anteil for _, _, anteil in gruppen])
    anteile = rng.random(anzahl)
    ergebnis: list[int] = []
    for laufende, index in enumerate(indizes):
        unten, oben, _ = gruppen[int(index)]
        oben = max(oben, unten)
        ergebnis.append(unten + int(float(anteile[laufende]) * (oben - unten + 1)))
    return [min(jahr, stichtagsjahr) for jahr in ergebnis]


def _versicherungssummen(rng: Generator, wohnflaechen: Sequence[int]) -> list[Decimal]:
    """Bildet die Versicherungssumme aus der Wohnflaeche mit Streuung."""
    streuung = ziehe_lognormal(rng, len(wohnflaechen), 1.0, _VS_SIGMA)
    unten, oben = wb.VERSICHERUNGSSUMME_HAUSRAT_EUR
    summen: list[Decimal] = []
    for index, flaeche in enumerate(wohnflaechen):
        roh = wb.UNTERVERSICHERUNGSVERZICHT_EUR_JE_QM * flaeche * Decimal(
            repr(float(streuung[index]))
        )
        gerastert = (roh / _VS_SCHRITT).to_integral_value(rounding=ROUND_DOWN) * _VS_SCHRITT
        summen.append(runde(min(max(gerastert, unten), oben)))
    return summen


def _sublimits(
    rng: Generator, versicherungssummen: Sequence[Decimal]
) -> tuple[list[Decimal], list[Decimal]]:
    """Zieht die beiden Sublimits; beide bleiben unter der Versicherungssumme (R-042)."""
    anzahl = len(versicherungssummen)
    fahrrad_index = waehle_index(rng, anzahl, [gewicht for _, gewicht in _SUBLIMIT_FAHRRAD])
    wertsachen_index = waehle_index(
        rng, anzahl, [gewicht for _, gewicht in _SUBLIMIT_WERTSACHEN_ANTEILE]
    )
    fahrrad: list[Decimal] = []
    wertsachen: list[Decimal] = []
    for index, summe in enumerate(versicherungssummen):
        stufe = _SUBLIMIT_FAHRRAD[int(fahrrad_index[index])][0]
        fahrrad.append(runde(min(stufe, summe)))
        anteil = _SUBLIMIT_WERTSACHEN_ANTEILE[int(wertsachen_index[index])][0]
        roh = summe * anteil
        gerastert = (roh / _SUBLIMIT_SCHRITT).to_integral_value(
            rounding=ROUND_DOWN
        ) * _SUBLIMIT_SCHRITT
        wertsachen.append(runde(min(gerastert, summe)))
    return fahrrad, wertsachen


def erzeuge_risiko_hausrat(
    config: Config,
    rng: Generator,
    *,
    anfrage_ids: Sequence[str],
    zuers_zonen: Sequence[int],
) -> RisikoHausrat:
    """Erzeugt die Hausratrisiken der Hausrat-Anfragen.

    Args:
        config: Geladene Konfiguration; liefert den Stichtag.
        rng: Zufallsgenerator des Teilstroms "Risiko Hausrat".
        anfrage_ids: Kennung je Hausrat-Anfrage.
        zuers_zonen: ZUERS-Zone je Hausrat-Anfrage, aus der Postleitzahl abgeleitet.

    Returns:
        Das :class:`RisikoHausrat` mit Datenrahmen und Beitragsgroessen.
    """
    anzahl = len(anfrage_ids)
    wohnflaechen = [
        int(wert)
        for wert in ziehe_ganzzahl_lognormal(
            rng,
            anzahl,
            median=_WOHNFLAECHE_MEDIAN,
            sigma=_WOHNFLAECHE_SIGMA,
            unten=wb.GENERATOR_WOHNFLAECHE_QM[0],
            oben=wb.GENERATOR_WOHNFLAECHE_QM[1],
        )
    ]
    summen = _versicherungssummen(rng, wohnflaechen)
    grenzen = [wb.UNTERVERSICHERUNGSVERZICHT_EUR_JE_QM * flaeche for flaeche in wohnflaechen]
    verzicht = ziehe_wahrheit(
        rng,
        [
            _P_UNTERVERSICHERUNGSVERZICHT if summen[index] >= grenzen[index] else 0.0
            for index in range(anzahl)
        ],
    )

    bauartnamen = tuple(_BAUARTKLASSE_GEWICHTE)
    bauart_index = waehle_index(rng, anzahl, [_BAUARTKLASSE_GEWICHTE[n] for n in bauartnamen])
    bauartklassen = [bauartnamen[int(index)] for index in bauart_index]
    baujahre = _ziehe_baujahre(rng, anzahl, config.stichtag.year)
    gebaeude_index = waehle_index(rng, anzahl, [g for _, g in _GEBAEUDEART_GEWICHTE])
    gebaeudearten = [_GEBAEUDEART_GEWICHTE[int(index)][0].value for index in gebaeude_index]
    stockwerk_index = waehle_index(rng, anzahl, [g for _, g in _STOCKWERK_GEWICHTE])
    elementar = ziehe_wahrheit(rng, [_P_ELEMENTAR_JE_ZONE[int(zone)] for zone in zuers_zonen])
    fahrrad, wertsachen = _sublimits(rng, summen)
    risiko_ids = erzeuge_uuids(rng, anzahl)

    spalten: dict[str, list[object]] = {name: [] for name in SPALTEN_JE_ENTITAET["risiko_hausrat"]}
    for index in range(anzahl):
        gebaeudeart = gebaeudearten[index]
        spalten["row_id"].append(index + 1)
        spalten["risiko_id"].append(risiko_ids[index])
        spalten["anfrage_id"].append(anfrage_ids[index])
        spalten["wohnflaeche_qm"].append(wohnflaechen[index])
        spalten["versicherungssumme_eur"].append(summen[index])
        spalten["unterversicherungsverzicht"].append(bool(verzicht[index]))
        spalten["bauartklasse"].append(bauartklassen[index])
        spalten["baujahr"].append(baujahre[index])
        spalten["gebaeudeart"].append(gebaeudeart)
        spalten["stockwerk"].append(
            _STOCKWERK_GEWICHTE[int(stockwerk_index[index])][0]
            if gebaeudeart in _MIT_STOCKWERK
            else None
        )
        spalten["zuers_zone"].append(int(zuers_zonen[index]))
        spalten["elementar_eingeschlossen"].append(bool(elementar[index]))
        spalten["sublimit_fahrrad_eur"].append(fahrrad[index])
        spalten["sublimit_wertsachen_eur"].append(wertsachen[index])

    return RisikoHausrat(
        rahmen=typisierter_rahmen(spalten, "risiko_hausrat"),
        versicherungssumme_eur=tuple(summen),
        zuers_zone=tuple(int(zone) for zone in zuers_zonen),
        bauartklasse=tuple(bauartklassen),
        elementar_eingeschlossen=tuple(bool(wert) for wert in elementar),
    )


def _pruefe_kataloge() -> None:
    """Selbstpruefung: Bauartklassen und ZUERS-Zonen decken den Katalog vollstaendig ab."""
    if set(_BAUARTKLASSE_GEWICHTE) != set(BAUARTKLASSEN):
        raise ValueError("Die Bauartklassen weichen von GDV Anlage 12 ab")
    if set(_P_ELEMENTAR_JE_ZONE) != set(wb.ZUERS_ZONEN):
        raise ValueError("Die ZUERS-Zonen weichen vom Katalog ab")


_pruefe_kataloge()
