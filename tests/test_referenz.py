"""Prueft die Referenztabellen gegen die Wertebereiche aus ``spec/01_datenmodell.md``.

Diese Tests sind der Nachweis, dass die versionierten Referenzdaten die
Zusicherungen einhalten, auf die sich Generator und Regel-Engine spaeter
verlassen. Faellt hier etwas um, ist jede spaetere Messung wertlos.
"""

from __future__ import annotations

import dataclasses
import itertools
import re
from decimal import Decimal
from typing import TYPE_CHECKING

import pycountry
import pytest

from src.common import wertebereiche as wb
from src.common.enums import (
    SF_KLASSEN,
    SF_KLASSEN_NUMERISCH,
    WAEHRUNG_STANDARD,
    Antriebsart,
    Quellschnittstelle,
)
from src.common.pfade import REFERENZ_DATEIEN
from src.common.referenz import (
    ReferenzFehler,
    lade_plz_ort,
    lade_regionalklassen,
    lade_sf_beitragssatz,
    lade_tabelle,
    lade_typklassen,
    lade_vu_stammdaten,
    lade_waehrungen,
    lade_zuers_zonen,
    leere_zwischenspeicher,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from pathlib import Path

    from src.common.config import Config

#: Kuerzel der 16 Bundeslaender.
BUNDESLAENDER: frozenset[str] = frozenset(
    {"BW", "BY", "BE", "BB", "HB", "HH", "HE", "MV", "NI", "NW", "RP", "SL", "SN", "ST", "SH", "TH"}
)

#: Toleranz der ZUERS-Anteile in Prozentpunkten (spec/01, Abschnitt 2.5).
ZUERS_TOLERANZ_PP: float = 0.3


# ---------------------------------------------------------------------------
# Vorhandensein
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dateiname", REFERENZ_DATEIEN)
def test_referenzdatei_ist_versioniert(referenzverzeichnis: Path, dateiname: str) -> None:
    """Alle sieben Referenztabellen liegen im Repository."""
    pfad = referenzverzeichnis / dateiname
    assert pfad.is_file(), f"{pfad} fehlt"
    assert pfad.stat().st_size > 0, f"{pfad} ist leer"


def test_fehlende_tabelle_wirft_aussagekraeftig(config: Config, tmp_path: Path) -> None:
    """Eine fehlende Referenzdatei fuehrt zum Abbruch, nicht zu einem stillen Fallback."""
    ohne_referenzdaten = dataclasses.replace(
        config,
        pfade=dataclasses.replace(config.pfade, reference=tmp_path),
    )
    leere_zwischenspeicher()
    try:
        with pytest.raises(ReferenzFehler, match="plz_ort"):
            lade_plz_ort(ohne_referenzdaten)
    finally:
        leere_zwischenspeicher()


def test_unbekannte_tabelle_wirft(config: Config) -> None:
    """Ein Tippfehler im Tabellennamen faellt sofort auf."""
    with pytest.raises(ReferenzFehler, match="Unbekannte Referenztabelle"):
        lade_tabelle("plz_orte", config)


# ---------------------------------------------------------------------------
# plz_ort.csv
# ---------------------------------------------------------------------------


def test_plz_ort_struktur(config: Config, referenzverzeichnis: Path) -> None:
    """Postleitzahlen sind fuenfstellig, eindeutig und behalten ihre fuehrende Null."""
    assert referenzverzeichnis.is_dir()
    rahmen = lade_plz_ort(config)

    assert len(rahmen) == config.referenzdaten.n_plz
    assert rahmen["plz"].is_unique, "Eine PLZ gehoert zu genau einem Eintrag"
    assert rahmen["plz"].str.fullmatch(r"\d{5}").all(), "PLZ muss fuenf Ziffern haben (R-002)"
    assert (rahmen["plz"].str[0] == "0").any(), (
        "Ohne PLZ mit fuehrender Null waere R-002 nicht pruefbar"
    )


def test_plz_ort_haelt_leitzonensystematik_ein(config: Config) -> None:
    """Jede Leitziffer von 0 bis 9 kommt vor (spec/01, Abschnitt 2.1)."""
    rahmen = lade_plz_ort(config)
    leitziffern = set(rahmen["plz"].str[0])
    assert leitziffern == {str(ziffer) for ziffer in range(10)}
    assert not rahmen["plz"].str.startswith("00").any(), "00000 bis 00999 sind nicht vergeben"


def test_plz_ort_werte(config: Config) -> None:
    """Ortsname, Bundesland und Zulassungsbezirk sind wohlgeformt."""
    rahmen = lade_plz_ort(config)

    orte = rahmen["ort"]
    assert (orte.str.len() > 0).all(), "Kein Ortsname darf leer sein"
    assert (orte.str.len() <= 50).all(), "person.ort ist auf 50 Zeichen begrenzt"
    assert not orte.str.contains(",", regex=False).any(), "Komma wuerde das CSV-Format brechen"

    assert set(rahmen["bundesland"]) <= BUNDESLAENDER

    bezirke = rahmen["zulassungsbezirk"]
    assert bezirke.str.fullmatch(r"[A-Z]{1,3}").all(), (
        "Unterscheidungszeichen: ein bis drei Buchstaben"
    )
    assert bezirke.nunique() == config.referenzdaten.n_zulassungsbezirke


def test_eine_plz_gehoert_zu_genau_einem_bezirk(config: Config) -> None:
    """Vereinfachende Annahme aus spec/01, Abschnitt 2.1 — hier als Zusicherung."""
    rahmen = lade_plz_ort(config)
    je_plz = rahmen.groupby("plz")["zulassungsbezirk"].nunique()
    assert int(je_plz.max()) == 1


def test_ein_bezirk_liegt_in_genau_einem_bundesland(config: Config) -> None:
    """Sonst waere die Zuordnung Bezirk auf Regionalklasse nicht wohldefiniert."""
    rahmen = lade_plz_ort(config)
    je_bezirk = rahmen.groupby("zulassungsbezirk")["bundesland"].nunique()
    assert int(je_bezirk.max()) == 1


# ---------------------------------------------------------------------------
# regionalklassen.csv
# ---------------------------------------------------------------------------


def test_regionalklassen_deckt_alle_bezirke_ab(config: Config) -> None:
    """Jeder Zulassungsbezirk aus ``plz_ort`` hat genau einen Eintrag (Grundlage R-058)."""
    plz_ort = lade_plz_ort(config)
    rahmen = lade_regionalklassen(config)

    assert rahmen["zulassungsbezirk"].is_unique
    assert set(rahmen["zulassungsbezirk"]) == set(plz_ort["zulassungsbezirk"])


@pytest.mark.parametrize(
    ("spalte", "grenzen"),
    [
        ("regionalklasse_hp", wb.REGIONALKLASSE_HP),
        ("regionalklasse_tk", wb.REGIONALKLASSE_TK),
        ("regionalklasse_vk", wb.REGIONALKLASSE_VK),
    ],
)
def test_regionalklassen_liegen_im_wertebereich(
    config: Config, spalte: str, grenzen: tuple[int, int]
) -> None:
    """12 / 16 / 9 Stufen laut GDV-Regionalklassenverzeichnis (R-015)."""
    werte = lade_regionalklassen(config)[spalte]
    unten, oben = grenzen
    assert int(werte.min()) >= unten
    assert int(werte.max()) <= oben


def test_regionalklassen_sind_um_die_mitte_zentriert(config: Config) -> None:
    """spec/01, Abschnitt 2.2: "Verteilung um die Mitte zentriert"."""
    rahmen = lade_regionalklassen(config)
    for spalte, (unten, oben) in (
        ("regionalklasse_hp", wb.REGIONALKLASSE_HP),
        ("regionalklasse_tk", wb.REGIONALKLASSE_TK),
        ("regionalklasse_vk", wb.REGIONALKLASSE_VK),
    ):
        mitte = (unten + oben) / 2
        abstand = abs(float(rahmen[spalte].mean()) - mitte)
        assert abstand <= (oben - unten) * 0.1, f"{spalte} ist nicht um die Mitte zentriert"


# ---------------------------------------------------------------------------
# typklassen.csv
# ---------------------------------------------------------------------------


def test_typklassen_schluessel(config: Config) -> None:
    """HSN ist vierstellig numerisch, TSN dreistellig alphanumerisch (R-007, R-008)."""
    rahmen = lade_typklassen(config)

    assert len(rahmen) == config.referenzdaten.n_typklassen
    assert rahmen["hsn"].str.fullmatch(r"\d{4}").all()
    assert rahmen["tsn"].str.fullmatch(r"[A-Z0-9]{3}").all()
    assert not rahmen.duplicated(["hsn", "tsn"]).any(), "HSN/TSN muss eindeutig sein"
    assert rahmen["hsn"].nunique() == config.referenzdaten.n_hersteller


def test_hsn_behaelt_fuehrende_nullen(config: Config, referenzverzeichnis: Path) -> None:
    """Die Rohdatei fuehrt die HSN als Zeichenkette — sonst ginge die Null verloren."""
    zeilen = (referenzverzeichnis / "typklassen.csv").read_text(encoding="utf-8").splitlines()
    assert all(re.fullmatch(r"\d{4}", zeile.split(",")[0]) for zeile in zeilen[1:])
    rahmen = lade_typklassen(config)
    assert rahmen["hsn"].dtype == "string"


def test_eine_hsn_gehoert_zu_genau_einem_hersteller(config: Config) -> None:
    """Aufbau wie in der Zulassungsbescheinigung Teil I: HSN ist der Hersteller."""
    rahmen = lade_typklassen(config)
    assert int(rahmen.groupby("hsn")["hersteller"].nunique().max()) == 1


@pytest.mark.parametrize(
    ("spalte", "grenzen"),
    [
        ("typklasse_hp", wb.TYPKLASSE_HP),
        ("typklasse_tk", wb.TYPKLASSE_TK),
        ("typklasse_vk", wb.TYPKLASSE_VK),
    ],
)
def test_typklassen_liegen_im_wertebereich(
    config: Config, spalte: str, grenzen: tuple[int, int]
) -> None:
    """16 / 24 / 25 Klassen laut GDV-Typklassenverzeichnis (R-014)."""
    werte = lade_typklassen(config)[spalte]
    unten, oben = grenzen
    assert int(werte.min()) >= unten, f"{spalte} unterschreitet {unten}"
    assert int(werte.max()) <= oben, f"{spalte} ueberschreitet {oben}"


def test_typklassen_fahrzeugmerkmale(config: Config) -> None:
    """Leistung, Antriebsart und Neupreis halten die Vorgaben aus spec/01, Abschnitt 2.3 ein."""
    rahmen = lade_typklassen(config)

    unten_kw, oben_kw = wb.LEISTUNG_KW
    assert int(rahmen["leistung_kw"].min()) >= unten_kw
    assert int(rahmen["leistung_kw"].max()) <= oben_kw

    assert set(rahmen["antriebsart"]) <= {art.value for art in Antriebsart}

    unten_preis, oben_preis = wb.GENERATOR_NEUPREIS_EUR
    preise = list(rahmen["neupreis_eur"])
    assert all(isinstance(preis, Decimal) for preis in preise), "Geld ist niemals float"
    assert min(preise) >= unten_preis
    assert max(preise) <= oben_preis
    assert all(-preis.as_tuple().exponent == 2 for preis in preise), "Genau zwei Nachkommastellen"


# ---------------------------------------------------------------------------
# vu_stammdaten.csv
# ---------------------------------------------------------------------------


def test_vu_stammdaten(config: Config) -> None:
    """12 bis 15 Anbieter, Marktanteile summieren auf 1 (spec/01, Abschnitt 2.4)."""
    rahmen = lade_vu_stammdaten(config)

    assert 12 <= len(rahmen) <= 15
    assert len(rahmen) == config.referenzdaten.n_vu
    assert rahmen["vu_nummer"].str.fullmatch(r"\d{5}").all()
    assert rahmen["vu_nummer"].is_unique
    assert rahmen["vu_name"].is_unique
    assert (rahmen["marktanteil"] > 0).all()
    assert abs(float(rahmen["marktanteil"].sum()) - 1.0) < 1e-9


def test_jede_quellschnittstelle_kommt_vor(config: Config) -> None:
    """Ohne alle vier Schnittstellen waere das Pflichtfeldprofil (R-057) nicht pruefbar."""
    rahmen = lade_vu_stammdaten(config)
    assert set(rahmen["quell_schnittstelle"]) == {
        schnittstelle.value for schnittstelle in Quellschnittstelle
    }


def test_vu_namen_sind_erkennbar_synthetisch(config: Config) -> None:
    """spec/01, Abschnitt 2.4: Fantasienamen, klar als synthetisch erkennbar."""
    rahmen = lade_vu_stammdaten(config)
    assert rahmen["vu_name"].str.contains("Versicherung|Assekuranz", regex=True).all()


# ---------------------------------------------------------------------------
# zuers_zonen.csv
# ---------------------------------------------------------------------------


def test_zuers_deckt_alle_postleitzahlen_ab(config: Config) -> None:
    """Zu jeder PLZ gibt es genau eine Zone."""
    plz_ort = lade_plz_ort(config)
    rahmen = lade_zuers_zonen(config)

    assert rahmen["plz"].is_unique
    assert set(rahmen["plz"]) == set(plz_ort["plz"])


def test_zuers_zonen_liegen_im_katalog(config: Config) -> None:
    """Nur die Zonen 1 bis 4 existieren (R-016)."""
    rahmen = lade_zuers_zonen(config)
    assert set(rahmen["zuers_zone"].astype(int)) <= set(wb.ZUERS_ZONEN)


def test_zuers_verteilung_entspricht_gdv_anteilen(config: Config) -> None:
    """92,4 / 6,1 / 1,1 / 0,4 Prozent, Toleranz 0,3 Prozentpunkte (spec/01, Abschnitt 2.5)."""
    rahmen = lade_zuers_zonen(config)
    anzahl = len(rahmen)
    for zone, erwartet in zip(wb.ZUERS_ZONEN, config.referenzdaten.zuers_anteile, strict=True):
        gemessen = float((rahmen["zuers_zone"].astype(int) == zone).sum()) / anzahl
        abweichung_pp = abs(gemessen - erwartet) * 100
        assert abweichung_pp <= ZUERS_TOLERANZ_PP, (
            f"Zone {zone}: {gemessen * 100:.3f} Prozent statt {erwartet * 100:.3f} Prozent"
        )


# ---------------------------------------------------------------------------
# sf_beitragssatz.csv
# ---------------------------------------------------------------------------


def _sf_saetze(config: Config) -> dict[str, int]:
    """Liest die SF-Tabelle als einfache Abbildung Klasse auf Beitragssatz."""
    rahmen = lade_sf_beitragssatz(config)
    return {
        str(klasse): int(satz)
        for klasse, satz in zip(rahmen["sf_klasse"], rahmen["beitragssatz_prozent"], strict=True)
    }


def test_sf_tabelle_deckt_den_katalog_ab(config: Config) -> None:
    """Alle Klassen aus R-013 kommen genau einmal vor."""
    rahmen = lade_sf_beitragssatz(config)
    assert rahmen["sf_klasse"].is_unique
    assert set(rahmen["sf_klasse"]) == set(SF_KLASSEN)


def test_sf_beitragssatz_ist_nicht_steigend(config: Config) -> None:
    """``satz(SF n+1) <= satz(SF n)`` ueber SF 1 bis SF 50 (spec/01, Abschnitt 2.6).

    Die Spezifikation fordert ausdruecklich einen **nicht-steigenden** Verlauf,
    keinen streng fallenden. Plateaus sind zulaessig und erwuenscht: Reale
    Beitragssatztabellen flachen bei hohen Schadenfreiheitsklassen ab.
    """
    tabelle = _sf_saetze(config)
    saetze = [tabelle[klasse] for klasse in SF_KLASSEN_NUMERISCH]

    differenzen = [spaeter - frueher for frueher, spaeter in itertools.pairwise(saetze)]
    assert all(differenz <= 0 for differenz in differenzen), "Der Beitragssatz darf nie steigen"
    assert saetze[0] > saetze[-1], "Ueber die gesamte Spanne muss der Satz fallen"


def test_sf_plateaus_liegen_bei_hohen_klassen(config: Config) -> None:
    """Wo der Verlauf flach wird, ist fachlich bedeutsam (spec/01, Abschnitt 2.6).

    Plateaus im unteren SF-Bereich waeren ein Modellfehler — dort bringt jedes
    schadenfreie Jahr real noch eine spuerbare Ersparnis.
    """
    tabelle = _sf_saetze(config)
    saetze = [tabelle[klasse] for klasse in SF_KLASSEN_NUMERISCH]
    plateaus = [
        stufe
        for stufe, (frueher, spaeter) in enumerate(itertools.pairwise(saetze), start=1)
        if frueher == spaeter
    ]
    assert plateaus, "Ohne Plateaus waere die Tabelle bei ganzzahligen Prozentwerten unmoeglich"
    assert min(plateaus) >= 20, f"Plateau bereits bei SF {min(plateaus)}"


def test_sf_ankerwerte(config: Config) -> None:
    """SF 1 ungefaehr 58 Prozent, SF 50 ungefaehr 16 Prozent."""
    tabelle = _sf_saetze(config)
    assert tabelle["SF1"] == 58
    assert tabelle["SF50"] == 16


def test_sf_sonderklassen(config: Config) -> None:
    """M = 245, S = 155, 0 = 100, 1/2 = 70 (spec/01, Abschnitt 2.6)."""
    tabelle = _sf_saetze(config)
    for klasse, erwartet in (("M", 245), ("S", 155), ("0", 100), ("1/2", 70)):
        assert tabelle[klasse] == erwartet


def test_sonderklassen_liegen_ueber_den_numerischen(config: Config) -> None:
    """Ein Fahrer in M oder S zahlt mehr als jeder schadenfreie Fahrer."""
    tabelle = _sf_saetze(config)
    hoechster_numerisch = max(tabelle[klasse] for klasse in SF_KLASSEN_NUMERISCH)
    assert tabelle["M"] > hoechster_numerisch
    assert tabelle["S"] > hoechster_numerisch


# ---------------------------------------------------------------------------
# waehrungen.csv
# ---------------------------------------------------------------------------


def test_waehrungskatalog_ist_vollstaendig(config: Config) -> None:
    """Der ISO-4217-Katalog umfasst rund 180 Eintraege (spec/01, Abschnitt 2.7)."""
    rahmen = lade_waehrungen(config)
    assert 150 <= len(rahmen) <= 220, f"{len(rahmen)} Eintraege sind kein ISO-4217-Katalog"


def test_euro_ist_enthalten(config: Config) -> None:
    """Ohne ``EUR`` waere R-012 auf dem gesamten Datensatz verletzt."""
    rahmen = lade_waehrungen(config)
    euro = rahmen[rahmen["code"] == "EUR"]
    assert len(euro) == 1
    assert int(euro["numerisch"].iloc[0]) == 978


def test_waehrung_des_datensatzes_steht_im_katalog(config: Config) -> None:
    """Die beiden Stufen von R-012 greifen ineinander: ``EUR`` ist gueltig *und* zulaessig."""
    rahmen = lade_waehrungen(config)
    assert WAEHRUNG_STANDARD in set(rahmen["code"])


def test_waehrungscodes_sind_wohlgeformt(config: Config) -> None:
    """Dreistellige Grossbuchstaben, eindeutig (ISO 4217)."""
    rahmen = lade_waehrungen(config)
    assert rahmen["code"].str.fullmatch(r"[A-Z]{3}").all()
    assert rahmen["code"].is_unique
    assert (rahmen["name"].str.len() > 0).all()


def test_numerische_waehrungscodes_sind_eindeutig(config: Config) -> None:
    """ISO 4217 vergibt je Waehrung genau eine dreistellige Zahl."""
    rahmen = lade_waehrungen(config)
    assert rahmen["numerisch"].is_unique
    assert int(rahmen["numerisch"].min()) >= 1
    assert int(rahmen["numerisch"].max()) <= 999


def test_waehrungen_sind_nach_code_sortiert(config: Config) -> None:
    """Feste Reihenfolge — sonst waere die Datei nicht reproduzierbar."""
    codes = list(lade_waehrungen(config)["code"])
    assert codes == sorted(codes)


def test_waehrungskatalog_stammt_nicht_aus_dem_gedaechtnis(config: Config) -> None:
    """Die Tabelle stimmt mit ``pycountry`` ueberein (spec/01, Abschnitt 2.7).

    Eine von Hand gepflegte Waehrungsliste faellt niemandem auf, wenn sie falsch
    ist — und macht R-012 wertlos. Dieser Test bindet die Referenzdatei an die
    gepinnte Bibliotheksversion.
    """
    rahmen = lade_waehrungen(config)
    gelesen = {
        str(code): str(name)
        for code, name in zip(rahmen["code"], rahmen["name"], strict=True)
    }
    erwartet = {waehrung.alpha_3: waehrung.name for waehrung in pycountry.currencies}
    assert gelesen == erwartet
