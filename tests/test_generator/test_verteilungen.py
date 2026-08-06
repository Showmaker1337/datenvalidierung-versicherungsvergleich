"""Prueft die Verteilungen des erzeugten Datensatzes gegen ihre Sollwerte.

Geprueft werden die Groessen, die in ``docs/verteilungsquellen.md`` belegt sind —
ZUERS-Zonen, Altersstruktur, Spartenanteile — sowie die Form der Angebotszahl.

Der Test dient zwei Zwecken: Er belegt, dass die dokumentierten Annahmen im Code
angekommen sind, und er faellt auf, wenn eine spaetere Aenderung die Struktur des
Datensatzes stillschweigend verschiebt.
"""

from __future__ import annotations

import statistics
from collections import Counter
from typing import TYPE_CHECKING

import pytest

from src.common import wertebereiche as wb
from src.common.enums import Quellschnittstelle
from src.common.pflichtfelder import (
    BLANKO_WAHRSCHEINLICHKEIT,
    ist_pflicht,
    profil_des_kanals,
)
from src.generator.verteilungen import jahre_zwischen

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    import pandas as pd

    from src.common.config import Config

#: Toleranz der Spartenanteile. Die Anteile werden exakt aufgeteilt; die Toleranz
#: faengt nur die ganzzahlige Rundung ab.
SPARTEN_TOLERANZ = 0.002

#: Modus der Angebotszahl (spec/01, Abschnitt 1).
ERWARTETER_MODUS = 5


def test_zuers_anteile_treffen_die_gdv_verteilung(
    datensatz: dict[str, pd.DataFrame], testkonfiguration: Config
) -> None:
    """Die ZUERS-Anteile halten die relative Toleranz von R-048 ein."""
    toleranz = testkonfiguration.schwellen.r048_zuers_toleranz_relativ
    zonen = Counter(int(wert) for wert in datensatz["risiko_hausrat"]["zuers_zone"])
    gesamt = sum(zonen.values())
    for index, sollanteil in enumerate(wb.ZUERS_ANTEILE_GDV, start=1):
        istanteil = zonen[index] / gesamt
        abweichung = abs(istanteil - sollanteil) / sollanteil
        assert abweichung <= toleranz, (
            f"Zone {index}: {istanteil:.4f} statt {sollanteil:.4f} "
            f"(relative Abweichung {abweichung:.1%})"
        )


def test_alle_zuers_zonen_kommen_vor(datensatz: dict[str, pd.DataFrame]) -> None:
    """Auch die seltenste Zone ist besetzt — sonst waere R-048 nicht pruefbar."""
    zonen = {int(wert) for wert in datensatz["risiko_hausrat"]["zuers_zone"]}
    assert zonen == set(wb.ZUERS_ZONEN)


def test_spartenanteile_entsprechen_der_konfiguration(
    datensatz: dict[str, pd.DataFrame], testkonfiguration: Config
) -> None:
    """Die Spartenanteile werden exakt aufgeteilt, nicht nur im Erwartungswert."""
    anteile = Counter(str(wert) for wert in datensatz["anfrage"]["sparte"])
    gesamt = sum(anteile.values())
    for sparte, sollanteil in testkonfiguration.sparten_verteilung.items():
        assert abs(anteile[sparte] / gesamt - sollanteil) <= SPARTEN_TOLERANZ


def test_altersverteilung_folgt_der_zensusstruktur(
    datensatz: dict[str, pd.DataFrame], testkonfiguration: Config
) -> None:
    """Median und Randbereiche der Altersverteilung passen zur Zensusstruktur.

    Eine Gleichverteilung ueber 18 bis 95 haette den Median bei rund 56 und je
    ein Viertel der Personen unter 37 und ueber 76. Die Zensusstruktur liegt
    deutlich davon entfernt; genau das prueft der Test.
    """
    stichtag = testkonfiguration.stichtag
    alter = sorted(
        jahre_zwischen(geburtsdatum, stichtag)
        for geburtsdatum in datensatz["person"]["geburtsdatum"]
        if geburtsdatum is not None
    )
    assert len(alter) > 1000
    median = statistics.median(alter)
    assert 46 <= median <= 58, f"Medianalter {median} ausserhalb des erwarteten Bereichs"

    anteil_jung = sum(1 for wert in alter if wert < 30) / len(alter)
    anteil_alt = sum(1 for wert in alter if wert >= 75) / len(alter)
    assert 0.12 <= anteil_jung <= 0.22, f"Anteil unter 30: {anteil_jung:.1%}"
    assert 0.09 <= anteil_alt <= 0.20, f"Anteil ab 75: {anteil_alt:.1%}"
    assert alter[0] >= wb.ALTER_VN[0]
    assert alter[-1] <= wb.ALTER_VN[1]


def test_angebotszahl_ist_rechtsschief_mit_modus_fuenf(
    datensatz: dict[str, pd.DataFrame], testkonfiguration: Config
) -> None:
    """Die Angebotszahl haelt Spanne, Modus und Rechtsschiefe ein (spec/01, Abschnitt 1)."""
    je_anfrage = Counter(str(wert) for wert in datensatz["angebot"]["anfrage_id"])
    haeufigkeit = Counter(je_anfrage.values())
    minimum = testkonfiguration.angebote_je_anfrage.minimum
    maximum = testkonfiguration.angebote_je_anfrage.maximum

    assert min(haeufigkeit) >= minimum
    assert max(haeufigkeit) <= maximum
    assert haeufigkeit.most_common(1)[0][0] == ERWARTETER_MODUS

    werte = list(je_anfrage.values())
    mittelwert = statistics.mean(werte)
    assert mittelwert > ERWARTETER_MODUS, "Rechtsschiefe verlangt Mittelwert ueber dem Modus"
    assert 5.8 <= mittelwert <= 6.8, f"Mittelwert {mittelwert:.2f} verfehlt rund 60.000 Zeilen"


def test_wohnflaeche_und_baujahr_folgen_dem_zensus(
    datensatz: dict[str, pd.DataFrame],
) -> None:
    """Wohnflaeche und Baujahr sind nicht gleichverteilt, sondern zensusnah."""
    flaechen = sorted(int(wert) for wert in datensatz["risiko_hausrat"]["wohnflaeche_qm"])
    median = statistics.median(flaechen)
    assert 70 <= median <= 100, f"Medianwohnflaeche {median}"
    # Gleichverteilung ueber 20 bis 350 haette den Median bei 185.
    assert median < 150

    baujahre = sorted(int(wert) for wert in datensatz["risiko_hausrat"]["baujahr"])
    vor_1979 = sum(1 for jahr in baujahre if jahr < 1979) / len(baujahre)
    assert 0.45 <= vor_1979 <= 0.65, f"Anteil Baujahr vor 1979: {vor_1979:.1%}"


def test_jahresfahrleistung_liegt_um_zwoelftausend(
    datensatz: dict[str, pd.DataFrame],
) -> None:
    """Die Fahrleistung ist log-normal um 12.000 km verteilt."""
    werte = sorted(int(wert) for wert in datensatz["risiko_kfz"]["jahresfahrleistung_km"].dropna())
    median = statistics.median(werte)
    assert 10_500 <= median <= 13_500, f"Medianfahrleistung {median}"
    assert werte[0] >= wb.GENERATOR_JAHRESFAHRLEISTUNG_KM[0]
    assert werte[-1] <= wb.GENERATOR_JAHRESFAHRLEISTUNG_KM[1]
    assert statistics.mean(werte) > median, "Log-normal verlangt Mittelwert ueber dem Median"


def test_schaeden_sind_stark_rechtsschief(datensatz: dict[str, pd.DataFrame]) -> None:
    """Die grosse Mehrheit hat keinen Schaden in fuenf Jahren."""
    werte = [int(wert) for wert in datensatz["risiko_kfz"]["schaeden_letzte_5j"]]
    assert sum(1 for wert in werte if wert == 0) / len(werte) >= 0.60
    assert max(werte) <= 5


@pytest.mark.parametrize(
    ("entitaet", "spalte"),
    [
        ("person", "email"),
        ("person", "strasse"),
        ("person", "familienstand"),
        ("risiko_kfz", "abstellplatz"),
        ("risiko_hausrat", "sublimit_fahrrad_eur"),
        ("zahlung", "bic"),
        ("zahlung", "kontoinhaber"),
    ],
)
def test_pflichtfelder_bleiben_gefuellt_und_optionale_werden_geleert(
    datensatz: dict[str, pd.DataFrame], entitaet: str, spalte: str
) -> None:
    """Ein Profilfeld ist leer nur dort, wo das Profil des Kanals es zulaesst (spaeter R-057).

    Zusaetzlich wird geprueft, dass die Leerquote **ueberhaupt** entsteht: Ohne
    sie waere der Datensatz unrealistisch homogen und R-057 ohne Gegenstand.

    Ausgenommen sind juristische Personen: Bei ``anrede`` = FIRMA ist der
    Familienstand fachlich nicht anwendbar und bleibt unabhaengig vom Profil leer.
    """
    feld = f"{entitaet}.{spalte}"
    kanal_je_anfrage = {
        str(kennung): str(kanal)
        for kennung, kanal in zip(
            datensatz["anfrage"]["anfrage_id"], datensatz["anfrage"]["kanal"], strict=True
        )
    }
    rahmen = datensatz[entitaet]
    if entitaet == "person" and "anrede" in rahmen.columns:
        rahmen = rahmen[rahmen["anrede"] != "FIRMA"]

    leerwerte = rahmen[spalte].isna().tolist()
    schnittstellen = [
        profil_des_kanals(kanal_je_anfrage[str(kennung)]) for kennung in rahmen["anfrage_id"]
    ]

    paare = list(zip(leerwerte, schnittstellen, strict=True))
    pflicht_leer = sum(leer for leer, quelle in paare if ist_pflicht(feld, quelle))
    optional = [leer for leer, quelle in paare if not ist_pflicht(feld, quelle)]

    assert pflicht_leer == 0, f"{feld}: {pflicht_leer} Pflichtfelder sind leer"
    assert optional, f"{feld}: keine Zeile mit optionalem Profil"
    quote = sum(optional) / len(optional)
    assert 0.5 * BLANKO_WAHRSCHEINLICHKEIT <= quote <= 1.5 * BLANKO_WAHRSCHEINLICHKEIT, (
        f"{feld}: Leerquote {quote:.1%} weicht zu stark von {BLANKO_WAHRSCHEINLICHKEIT:.0%} ab"
    )


def test_angebotsfelder_folgen_der_quellschnittstelle(
    datensatz: dict[str, pd.DataFrame],
) -> None:
    """Die Selbstbehaltfelder des Angebots haengen an der Schnittstelle des Anbieters.

    Geprueft wird nur dort, wo das Feld fachlich vorkommt: ``sb_tk_eur`` gibt es
    ausschliesslich in Teil- und Vollkasko.
    """
    sparte_je_anfrage = {
        str(kennung): str(sparte)
        for kennung, sparte in zip(
            datensatz["anfrage"]["anfrage_id"], datensatz["anfrage"]["sparte"], strict=True
        )
    }
    kasko = {"052", "053"}
    angebote = datensatz["angebot"]
    anwendbar = angebote[
        angebote["anfrage_id"].map(lambda kennung: sparte_je_anfrage[str(kennung)]).isin(kasko)
    ]
    assert len(anwendbar) > 0

    pflicht_leer = 0
    optional: list[bool] = []
    for quelle, wert in zip(anwendbar["quell_schnittstelle"], anwendbar["sb_tk_eur"], strict=True):
        leer = wert is None
        if ist_pflicht("angebot.sb_tk_eur", Quellschnittstelle(str(quelle))):
            pflicht_leer += int(leer)
        else:
            optional.append(leer)

    assert pflicht_leer == 0
    assert optional
    quote = sum(optional) / len(optional)
    assert 0.5 * BLANKO_WAHRSCHEINLICHKEIT <= quote <= 1.5 * BLANKO_WAHRSCHEINLICHKEIT
