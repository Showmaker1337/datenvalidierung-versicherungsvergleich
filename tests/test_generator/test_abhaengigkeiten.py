"""Prueft jede fachliche Abhaengigkeit des sauberen Datensatzes.

Dieser Test ist **bewusst redundant** zur spaeteren Regel-Engine. Er darf sie
nicht importieren (Architekturregel A1) und formuliert die Bedingungen deshalb
eigenstaendig. Genau darin liegt sein Wert: Waere er eine Kopie der Regeln, wuerde
er nur pruefen, ob dieselbe Bedingung zweimal gleich implementiert wurde.

Die Kommentare nennen die spaetere Regel-ID, damit die Zuordnung nachvollziehbar
bleibt — der Test haengt aber an keiner Zeile Regelcode.
"""

from __future__ import annotations

import itertools
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pandas as pd
import pytest

from src.common import wertebereiche as wb
from src.common.enums import (
    BAUARTKLASSEN,
    SF_KLASSEN,
    WAGNISKENNZIFFER_PKW,
    Antriebsart,
    ArtKennzeichen,
    Gebaeudeart,
    Sparte,
    ist_kfz_sparte,
    schadenfreie_jahre,
    sf_ordnung,
)
from src.common.iban import hat_deutsches_format, ist_gueltig
from src.generator.verteilungen import datum_plus_jahre, jahre_zwischen

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    import datetime as dt

    from src.common.config import Config


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _sparte_je_anfrage(datensatz: dict[str, pd.DataFrame]) -> dict[str, str]:
    """Bildet Anfragekennung auf Spartenschluessel ab."""
    anfragen = datensatz["anfrage"]
    return {
        str(kennung): str(sparte)
        for kennung, sparte in zip(anfragen["anfrage_id"], anfragen["sparte"], strict=True)
    }


def _versicherungsnehmer(datensatz: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Gibt nur die Zeilen der Versicherungsnehmer zurueck."""
    personen = datensatz["person"]
    return personen[personen["rolle"] == "VN"]


def _gefuellt(wert: object) -> bool:
    """Gibt zurueck, ob eine Zelle einen Wert traegt.

    In den Objektspalten steht ``None``, in den Erweiterungstypen ``pd.NA``.
    Beides bedeutet "leer" (CLAUDE.md, Abschnitt 5).
    """
    leer: bool = bool(pd.isna(wert))  # type: ignore[call-overload]
    return not leer

def _zeilen(rahmen: pd.DataFrame) -> list[dict[str, Any]]:
    """Gibt die Zeilen eines Datenrahmens als Abbildungen Spalte auf Wert zurueck.

    Bewusst statt ``itertuples``: Die pandas-Typstubs beschreiben jedes Feld eines
    Namenstupels als grosse Vereinigung ueber alle denkbaren Skalartypen. Jeder
    Vergleich und jede Rechnung darauf scheitert dann in der strikten
    Typpruefung, obwohl der Wert zur Laufzeit eindeutig ist.
    """
    return [
        {str(name): wert for name, wert in eintrag.items()}
        for eintrag in rahmen.to_dict("records")
    ]



# ---------------------------------------------------------------------------
# Schluessel und Beziehungen
# ---------------------------------------------------------------------------


def test_fremdschluessel_sind_aufloesbar(datensatz: dict[str, pd.DataFrame]) -> None:
    """Jeder Fremdschluessel zeigt auf einen vorhandenen Satz (spaeter R-049)."""
    anfragen = set(datensatz["anfrage"]["anfrage_id"])
    for name in ("person", "risiko_kfz", "risiko_hausrat", "angebot", "zahlung"):
        verwaist = set(datensatz[name]["anfrage_id"]) - anfragen
        assert not verwaist, f"{name}: verwaiste anfrage_id {sorted(verwaist)[:3]}"
    assert set(datensatz["angebot"]["tarif_id"]) <= set(datensatz["tarif"]["tarif_id"])
    assert set(datensatz["anfrage"]["vn_person_id"]) <= set(datensatz["person"]["person_id"])


def test_genau_ein_versicherungsnehmer_je_anfrage(datensatz: dict[str, pd.DataFrame]) -> None:
    """Je Anfrage existiert genau eine Person in der Rolle VN (spaeter R-046)."""
    versicherungsnehmer = _versicherungsnehmer(datensatz)
    assert len(versicherungsnehmer) == len(datensatz["anfrage"])
    assert versicherungsnehmer["anfrage_id"].nunique() == len(datensatz["anfrage"])


def test_row_id_ist_je_entitaet_eindeutig_und_lueckenlos(
    datensatz: dict[str, pd.DataFrame],
) -> None:
    """``row_id`` laeuft je Entitaet fortlaufend ab eins."""
    for name, rahmen in datensatz.items():
        werte = [int(wert) for wert in rahmen["row_id"]]
        assert werte == list(range(1, len(rahmen) + 1)), f"{name}: row_id nicht fortlaufend"


def test_risikoentitaet_passt_zur_sparte(datensatz: dict[str, pd.DataFrame]) -> None:
    """Kfz-Anfragen haben genau ein Kfz-Risiko, Hausrat-Anfragen genau ein Hausratrisiko."""
    sparte_je_anfrage = _sparte_je_anfrage(datensatz)
    kfz = list(datensatz["risiko_kfz"]["anfrage_id"])
    hausrat = list(datensatz["risiko_hausrat"]["anfrage_id"])
    assert len(kfz) == len(set(kfz))
    assert len(hausrat) == len(set(hausrat))
    assert all(ist_kfz_sparte(sparte_je_anfrage[str(kennung)]) for kennung in kfz)
    assert all(not ist_kfz_sparte(sparte_je_anfrage[str(kennung)]) for kennung in hausrat)
    assert len(kfz) + len(hausrat) == len(datensatz["anfrage"])


# ---------------------------------------------------------------------------
# Person
# ---------------------------------------------------------------------------


def test_ort_und_zulassungsbezirk_stammen_aus_der_referenz(
    datensatz: dict[str, pd.DataFrame], referenzdaten: dict[str, pd.DataFrame]
) -> None:
    """``ort`` und ``zulassungsbezirk`` sind aus der PLZ abgeleitet (spaeter R-050, R-058)."""
    plz_ort = referenzdaten["plz_ort"]
    ort_je_plz = dict(zip(plz_ort["plz"], plz_ort["ort"], strict=True))
    bezirk_je_plz = dict(zip(plz_ort["plz"], plz_ort["zulassungsbezirk"], strict=True))

    personen = datensatz["person"]
    for plz, ort in zip(personen["plz"], personen["ort"], strict=True):
        assert ort_je_plz[plz] == ort, f"Ort passt nicht zur PLZ {plz}"

    bezirk_je_anfrage = {
        str(kennung): bezirk_je_plz[plz]
        for kennung, plz in zip(
            _versicherungsnehmer(datensatz)["anfrage_id"],
            _versicherungsnehmer(datensatz)["plz"],
            strict=True,
        )
    }
    risiko = datensatz["risiko_kfz"]
    for kennung, bezirk in zip(risiko["anfrage_id"], risiko["zulassungsbezirk"], strict=True):
        assert bezirk_je_anfrage[str(kennung)] == bezirk


def test_alter_liegt_im_zulaessigen_bereich(
    datensatz: dict[str, pd.DataFrame], testkonfiguration: Config
) -> None:
    """Jede natuerliche Person ist zwischen 18 und 95 Jahre alt."""
    unten, oben = wb.ALTER_VN
    for geburtsdatum in datensatz["person"]["geburtsdatum"]:
        if geburtsdatum is None:
            continue
        alter = jahre_zwischen(geburtsdatum, testkonfiguration.stichtag)
        assert unten <= alter <= oben, f"Alter {alter} ausserhalb [{unten}, {oben}]"


def test_juristische_person_hat_kein_geburtsdatum(datensatz: dict[str, pd.DataFrame]) -> None:
    """Bei ``anrede`` = FIRMA bleiben Geburtsdatum und Vorname leer (bedingter Teil von R-001)."""
    personen = datensatz["person"]
    firmen = personen[personen["anrede"] == "FIRMA"]
    assert firmen["geburtsdatum"].isna().all()
    assert firmen["vorname"].isna().all()
    natuerlich = personen[personen["anrede"] != "FIRMA"]
    assert natuerlich["geburtsdatum"].notna().all()
    assert natuerlich["nachname"].notna().all()


def test_fuehrerschein_erfuellt_das_mindestalter(
    datensatz: dict[str, pd.DataFrame], testkonfiguration: Config
) -> None:
    """``fuehrerschein_datum`` liegt fruehestens 17 Jahre nach der Geburt (spaeter R-028)."""
    personen = datensatz["person"].dropna(subset=["fuehrerschein_datum"])
    assert len(personen) > 0
    for geburtsdatum, fuehrerschein in zip(
        personen["geburtsdatum"], personen["fuehrerschein_datum"], strict=True
    ):
        assert geburtsdatum is not None
        untergrenze = datum_plus_jahre(geburtsdatum, wb.FUEHRERSCHEIN_MINDESTALTER_JAHRE)
        assert untergrenze <= fuehrerschein <= testkonfiguration.stichtag


def test_fuehrerschein_nur_in_den_kfz_sparten(datensatz: dict[str, pd.DataFrame]) -> None:
    """Zweckbindung: ausserhalb der Kfz-Sparten bleibt der Fuehrerscheintag leer."""
    sparte_je_anfrage = _sparte_je_anfrage(datensatz)
    personen = datensatz["person"]
    for kennung, fuehrerschein in zip(
        personen["anfrage_id"], personen["fuehrerschein_datum"], strict=True
    ):
        if not ist_kfz_sparte(sparte_je_anfrage[str(kennung)]):
            assert not _gefuellt(fuehrerschein)


# ---------------------------------------------------------------------------
# Kfz-Risiko
# ---------------------------------------------------------------------------


def test_fahrzeugmerkmale_stammen_aus_dem_referenzeintrag(
    datensatz: dict[str, pd.DataFrame], referenzdaten: dict[str, pd.DataFrame]
) -> None:
    """Alle abgeleiteten Fahrzeugfelder stimmen mit (HSN, TSN) ueberein (spaeter R-051)."""
    typklassen = referenzdaten["typklassen"].set_index(["hsn", "tsn"])
    risiko = datensatz["risiko_kfz"]
    for zeile in _zeilen(risiko):
        eintrag = typklassen.loc[(zeile["hsn"], zeile["tsn"])]
        assert int(zeile["leistung_kw"]) == int(eintrag["leistung_kw"])
        assert zeile["antriebsart"] == eintrag["antriebsart"]
        assert zeile["neupreis_eur"] == eintrag["neupreis_eur"]
        assert int(zeile["typklasse_hp"]) == int(eintrag["typklasse_hp"])


def test_regionalklassen_stammen_aus_dem_referenzeintrag(
    datensatz: dict[str, pd.DataFrame], referenzdaten: dict[str, pd.DataFrame]
) -> None:
    """Die drei Regionalklassen passen zum Zulassungsbezirk (spaeter R-058)."""
    regional = referenzdaten["regionalklassen"].set_index("zulassungsbezirk")
    for zeile in _zeilen(datensatz["risiko_kfz"]):
        eintrag = regional.loc[zeile["zulassungsbezirk"]]
        assert int(zeile["regionalklasse_hp"]) == int(eintrag["regionalklasse_hp"])
        assert int(zeile["regionalklasse_tk"]) == int(eintrag["regionalklasse_tk"])
        assert int(zeile["regionalklasse_vk"]) == int(eintrag["regionalklasse_vk"])


def test_zulassungsdaten_sind_geordnet(
    datensatz: dict[str, pd.DataFrame], testkonfiguration: Config
) -> None:
    """``erstzulassung`` <= ``zulassung_auf_vn`` <= Stichtag (spaeter R-026, R-027)."""
    stichtag = testkonfiguration.stichtag
    for erstzulassung, zulassung in zip(
        datensatz["risiko_kfz"]["erstzulassung"],
        datensatz["risiko_kfz"]["zulassung_auf_vn"],
        strict=True,
    ):
        assert wb.ERSTZULASSUNG_FRUEHESTENS <= erstzulassung <= zulassung <= stichtag


def test_zulassung_erst_ab_volljaehrigkeit(datensatz: dict[str, pd.DataFrame]) -> None:
    """Ein Fahrzeug wird nicht vor dem 18. Geburtstag des VN auf ihn zugelassen."""
    geburtsdatum_je_anfrage: dict[str, dt.date] = {
        str(kennung): geburtsdatum
        for kennung, geburtsdatum in zip(
            _versicherungsnehmer(datensatz)["anfrage_id"],
            _versicherungsnehmer(datensatz)["geburtsdatum"],
            strict=True,
        )
        if geburtsdatum is not None
    }
    for kennung, zulassung in zip(
        datensatz["risiko_kfz"]["anfrage_id"],
        datensatz["risiko_kfz"]["zulassung_auf_vn"],
        strict=True,
    ):
        geburtsdatum = geburtsdatum_je_anfrage[str(kennung)]
        assert zulassung >= datum_plus_jahre(geburtsdatum, 18)


def test_schadenfreie_jahre_passen_zum_alter(
    datensatz: dict[str, pd.DataFrame], testkonfiguration: Config
) -> None:
    """``schadenfreie_jahre(sf_klasse_hp)`` <= Alter minus 17 (spaeter R-029)."""
    geburtsdaten = {
        str(kennung): geburtsdatum
        for kennung, geburtsdatum in zip(
            _versicherungsnehmer(datensatz)["anfrage_id"],
            _versicherungsnehmer(datensatz)["geburtsdatum"],
            strict=True,
        )
    }
    for kennung, klasse in zip(
        datensatz["risiko_kfz"]["anfrage_id"],
        datensatz["risiko_kfz"]["sf_klasse_hp"],
        strict=True,
    ):
        geburtsdatum = geburtsdaten[str(kennung)]
        assert geburtsdatum is not None
        alter = jahre_zwischen(geburtsdatum, testkonfiguration.stichtag)
        jahre = schadenfreie_jahre(str(klasse))
        assert jahre is not None
        assert jahre <= alter - wb.FUEHRERSCHEIN_MINDESTALTER_JAHRE


def test_vollkaskoklasse_ist_nie_besser_als_haftpflichtklasse(
    datensatz: dict[str, pd.DataFrame],
) -> None:
    """``sf_ordnung(vk)`` <= ``sf_ordnung(hp)`` (spaeter R-030)."""
    risiko = datensatz["risiko_kfz"].dropna(subset=["sf_klasse_vk"])
    assert len(risiko) > 0
    for haftpflicht, vollkasko in zip(
        risiko["sf_klasse_hp"], risiko["sf_klasse_vk"], strict=True
    ):
        ordnung_hp = sf_ordnung(str(haftpflicht))
        ordnung_vk = sf_ordnung(str(vollkasko))
        assert ordnung_hp is not None
        assert ordnung_vk is not None
        assert ordnung_vk <= ordnung_hp


def test_sf_klassen_stehen_im_katalog(datensatz: dict[str, pd.DataFrame]) -> None:
    """Beide SF-Felder enthalten nur Katalogwerte und sind Zeichenketten (spaeter R-013)."""
    risiko = datensatz["risiko_kfz"]
    for spalte in ("sf_klasse_hp", "sf_klasse_vk"):
        werte = {str(wert) for wert in risiko[spalte].dropna()}
        assert werte <= set(SF_KLASSEN), f"{spalte}: {sorted(werte - set(SF_KLASSEN))}"


def test_fahrzeugwert_ueberschreitet_den_neupreis_nicht(
    datensatz: dict[str, pd.DataFrame],
) -> None:
    """``fahrzeugwert_aktuell`` <= ``neupreis_eur`` und positiv (spaeter R-038)."""
    for neupreis, wert in zip(
        datensatz["risiko_kfz"]["neupreis_eur"],
        datensatz["risiko_kfz"]["fahrzeugwert_aktuell"],
        strict=True,
    ):
        assert Decimal(0) < wert <= neupreis


def test_e_kennzeichen_setzt_elektrischen_antrieb_voraus(
    datensatz: dict[str, pd.DataFrame],
) -> None:
    """``art_kennzeichen`` = 54 nur bei ELEKTRO oder HYBRID (spaeter R-039)."""
    elektrisch = {Antriebsart.ELEKTRO.value, Antriebsart.HYBRID.value}
    for kennzeichen, antrieb in zip(
        datensatz["risiko_kfz"]["art_kennzeichen"],
        datensatz["risiko_kfz"]["antriebsart"],
        strict=True,
    ):
        if kennzeichen == ArtKennzeichen.ELEKTRO.value:
            assert antrieb in elektrisch


def test_juengster_fahrer_ist_nicht_aelter_als_der_vn(
    datensatz: dict[str, pd.DataFrame], testkonfiguration: Config
) -> None:
    """``alter_juengster_fahrer`` liegt zwischen 17 und dem Alter des Versicherungsnehmers."""
    geburtsdaten = {
        str(kennung): geburtsdatum
        for kennung, geburtsdatum in zip(
            _versicherungsnehmer(datensatz)["anfrage_id"],
            _versicherungsnehmer(datensatz)["geburtsdatum"],
            strict=True,
        )
    }
    risiko = datensatz["risiko_kfz"].dropna(subset=["alter_juengster_fahrer"])
    for kennung, alter in zip(risiko["anfrage_id"], risiko["alter_juengster_fahrer"], strict=True):
        geburtsdatum = geburtsdaten[str(kennung)]
        assert geburtsdatum is not None
        alter_vn = jahre_zwischen(geburtsdatum, testkonfiguration.stichtag)
        assert wb.ALTER_JUENGSTER_FAHRER[0] <= int(alter) <= alter_vn


def test_typklassen_sind_zweckgebunden(datensatz: dict[str, pd.DataFrame]) -> None:
    """``typklasse_tk`` nur bei TK/VK, ``typklasse_vk`` und ``sf_klasse_vk`` nur bei VK."""
    sparte_je_anfrage = _sparte_je_anfrage(datensatz)
    risiko = datensatz["risiko_kfz"]
    for zeile in _zeilen(risiko):
        sparte = sparte_je_anfrage[str(zeile["anfrage_id"])]
        ist_vollkasko = sparte == Sparte.KFZ_VOLLKASKO.value
        ist_teilkasko = sparte == Sparte.KFZ_TEILKASKO.value
        assert _gefuellt(zeile["typklasse_vk"]) == ist_vollkasko
        assert _gefuellt(zeile["sf_klasse_vk"]) == ist_vollkasko
        assert _gefuellt(zeile["typklasse_tk"]) == (ist_vollkasko or ist_teilkasko)
        assert zeile["wagniskennziffer"] == WAGNISKENNZIFFER_PKW


# ---------------------------------------------------------------------------
# Hausratrisiko
# ---------------------------------------------------------------------------


def test_zuers_zone_stammt_aus_der_referenz(
    datensatz: dict[str, pd.DataFrame], referenzdaten: dict[str, pd.DataFrame]
) -> None:
    """Die ZUERS-Zone gehoert zur Postleitzahl des Versicherungsnehmers."""
    zonen = dict(
        zip(
            referenzdaten["zuers_zonen"]["plz"],
            referenzdaten["zuers_zonen"]["zuers_zone"],
            strict=True,
        )
    )
    plz_je_anfrage = {
        str(kennung): plz
        for kennung, plz in zip(
            _versicherungsnehmer(datensatz)["anfrage_id"],
            _versicherungsnehmer(datensatz)["plz"],
            strict=True,
        )
    }
    for kennung, zone in zip(
        datensatz["risiko_hausrat"]["anfrage_id"],
        datensatz["risiko_hausrat"]["zuers_zone"],
        strict=True,
    ):
        assert int(zone) == int(zonen[plz_je_anfrage[str(kennung)]])


def test_unterversicherungsverzicht_setzt_die_summe_voraus(
    datensatz: dict[str, pd.DataFrame],
) -> None:
    """Verzicht nur bei mindestens 650 Euro je Quadratmeter (spaeter R-040)."""
    risiko = datensatz["risiko_hausrat"]
    verzicht = risiko[risiko["unterversicherungsverzicht"].fillna(value=False)]
    assert len(verzicht) > 0
    for summe, flaeche in zip(
        verzicht["versicherungssumme_eur"], verzicht["wohnflaeche_qm"], strict=True
    ):
        assert summe >= wb.UNTERVERSICHERUNGSVERZICHT_EUR_JE_QM * int(flaeche)


def test_sublimits_bleiben_unter_der_versicherungssumme(
    datensatz: dict[str, pd.DataFrame],
) -> None:
    """Beide Sublimits ueberschreiten die Versicherungssumme nicht (spaeter R-042)."""
    for zeile in _zeilen(datensatz["risiko_hausrat"]):
        for sublimit in (zeile["sublimit_fahrrad_eur"], zeile["sublimit_wertsachen_eur"]):
            if _gefuellt(sublimit):
                assert Decimal(0) <= sublimit <= zeile["versicherungssumme_eur"]


def test_hausratfelder_liegen_in_ihren_wertebereichen(
    datensatz: dict[str, pd.DataFrame], testkonfiguration: Config
) -> None:
    """Wohnflaeche, Baujahr, Bauartklasse und Stockwerk halten ihre Kataloge ein."""
    risiko = datensatz["risiko_hausrat"]
    unten, oben = wb.GENERATOR_WOHNFLAECHE_QM
    assert all(unten <= int(wert) <= oben for wert in risiko["wohnflaeche_qm"])
    assert all(
        wb.GENERATOR_BAUJAHR_UNTERGRENZE <= int(wert) <= testkonfiguration.stichtag.year
        for wert in risiko["baujahr"]
    )
    assert {str(wert) for wert in risiko["bauartklasse"]} <= set(BAUARTKLASSEN)
    assert {int(wert) for wert in risiko["zuers_zone"]} <= set(wb.ZUERS_ZONEN)
    stockwerke = risiko["stockwerk"].dropna()
    assert all(wb.STOCKWERK[0] <= int(wert) <= wb.STOCKWERK[1] for wert in stockwerke)


def test_stockwerk_ist_bei_wohnungen_gesetzt(datensatz: dict[str, pd.DataFrame]) -> None:
    """ETW und MIETWOHNUNG verlangen ein Stockwerk (spec/01, Abschnitt 3.4)."""
    risiko = datensatz["risiko_hausrat"]
    wohnformen = [Gebaeudeart.ETW.value, Gebaeudeart.MIETWOHNUNG.value]
    wohnungen = risiko[risiko["gebaeudeart"].isin(wohnformen)]
    assert len(wohnungen) > 0
    assert wohnungen["stockwerk"].notna().all()


# ---------------------------------------------------------------------------
# Tarif und Angebot
# ---------------------------------------------------------------------------


def test_tarifgenerationen_sind_lueckenlos(datensatz: dict[str, pd.DataFrame]) -> None:
    """Je Anbieter und Sparte grenzen mindestens drei Generationen lueckenlos aneinander."""
    tarife = datensatz["tarif"]
    for (_, _), gruppe in tarife.groupby(["vu_nummer", "sparte"]):
        geordnet = gruppe.sort_values("gueltig_ab")
        grenzen = list(zip(geordnet["gueltig_ab"], geordnet["gueltig_bis"], strict=True))
        assert len(grenzen) >= 3, "Weniger als drei Tarifgenerationen"
        for ab, bis in grenzen:
            assert ab < bis, "gueltig_bis liegt nicht nach gueltig_ab"
        for (_, voriges_bis), (naechstes_ab, _) in itertools.pairwise(grenzen):
            assert (naechstes_ab - voriges_bis).days == 1, "Luecke oder Ueberlappung"


def test_deckungssummen_erfuellen_die_gesetzliche_mindestdeckung(
    datensatz: dict[str, pd.DataFrame],
) -> None:
    """Wo Deckungssummen gefuehrt werden, erreichen sie die Werte des PflVG (spaeter R-024)."""
    tarife = datensatz["tarif"].dropna(subset=["deckungssumme_personen_eur"])
    assert len(tarife) > 0
    for zeile in _zeilen(tarife):
        assert zeile["deckungssumme_personen_eur"] >= wb.PFLVG_MINDESTDECKUNG_PERSONEN_EUR
        assert zeile["deckungssumme_sach_eur"] >= wb.PFLVG_MINDESTDECKUNG_SACH_EUR
        assert zeile["deckungssumme_vermoegen_eur"] >= wb.PFLVG_MINDESTDECKUNG_VERMOEGEN_EUR


def test_deckungsart_nur_in_der_kfz_haftpflicht(datensatz: dict[str, pd.DataFrame]) -> None:
    """Zweckbindung: Deckungsart und Deckungssummen gibt es nur in Sparte 051."""
    tarife = datensatz["tarif"]
    haftpflicht = tarife["sparte"] == Sparte.KFZ_HAFTPFLICHT.value
    assert tarife[haftpflicht]["deckungsart"].notna().all()
    assert tarife[~haftpflicht]["deckungsart"].isna().all()
    assert tarife[~haftpflicht]["deckungssumme_personen_eur"].isna().all()


def test_berechnungszeitpunkt_liegt_im_gueltigkeitsfenster(
    datensatz: dict[str, pd.DataFrame],
) -> None:
    """Der gewaehlte Tarif gilt zum Berechnungszeitpunkt (spaeter R-055)."""
    fenster = {
        str(zeile["tarif_id"]): (zeile["gueltig_ab"], zeile["gueltig_bis"])
        for zeile in _zeilen(datensatz["tarif"])
    }
    for zeile in _zeilen(datensatz["angebot"]):
        gueltig_ab, gueltig_bis = fenster[str(zeile["tarif_id"])]
        assert gueltig_ab <= zeile["berechnungszeitpunkt"].date() <= gueltig_bis


def test_berechnungszeitpunkt_folgt_dem_eingang(datensatz: dict[str, pd.DataFrame]) -> None:
    """Der Berechnungszeitpunkt liegt hoechstens 60 Sekunden nach dem Eingang."""
    eingang = {
        str(kennung): zeitpunkt
        for kennung, zeitpunkt in zip(
            datensatz["anfrage"]["anfrage_id"],
            datensatz["anfrage"]["eingangszeitpunkt"],
            strict=True,
        )
    }
    for zeile in _zeilen(datensatz["angebot"]):
        eingegangen = eingang[str(zeile["anfrage_id"])]
        abstand = (zeile["berechnungszeitpunkt"] - eingegangen).total_seconds()
        assert 0 <= abstand <= wb.BERECHNUNG_DELTA_MAX_SEKUNDEN


def test_kein_tarif_erscheint_zweimal_in_einer_anfrage(
    datensatz: dict[str, pd.DataFrame],
) -> None:
    """Kein Duplikat ueber (``anfrage_id``, ``tarif_id``) (spaeter R-045)."""
    assert not datensatz["angebot"].duplicated(["anfrage_id", "tarif_id"]).any()


def test_rang_ist_lueckenlos_und_nach_rate_sortiert(datensatz: dict[str, pd.DataFrame]) -> None:
    """Die bepreisten Angebote tragen die Raenge 1..n, aufsteigend nach Rate (R-043, R-044)."""
    for _, gruppe in datensatz["angebot"].groupby("anfrage_id"):
        bepreist = gruppe.dropna(subset=["rang"]).sort_values("rang")
        assert [int(wert) for wert in bepreist["rang"]] == list(range(1, len(bepreist) + 1))
        raten = list(bepreist["zahlbeitrag_rate_eur"])
        assert raten == sorted(raten)
        assert len(bepreist) >= 2, "Zu wenige bepreiste Angebote je Anfrage"


def test_abgelehnte_angebote_haben_keine_beitragsfelder(
    datensatz: dict[str, pd.DataFrame],
) -> None:
    """ABLEHNUNG genau dann, wenn alle Beitragsfelder leer sind (spaeter R-037)."""
    beitragsfelder = (
        "nettobeitrag_jahr_eur",
        "versicherungsteuer_satz",
        "versicherungsteuer_eur",
        "bruttobeitrag_jahr_eur",
        "ratenzahlungszuschlag_prozent",
        "zahlbeitrag_rate_eur",
        "rang",
    )
    angebote = datensatz["angebot"]
    abgelehnt = angebote["annahmeentscheidung"] == "ABLEHNUNG"
    assert abgelehnt.any(), "Der Datensatz enthaelt keine Ablehnung"
    for feld in beitragsfelder:
        assert angebote.loc[abgelehnt, feld].isna().all(), f"{feld} bei ABLEHNUNG gefuellt"
        assert angebote.loc[~abgelehnt, feld].notna().all(), f"{feld} ohne ABLEHNUNG leer"


def test_selbstbehalt_ist_zweckgebunden_und_einheitlich(
    datensatz: dict[str, pd.DataFrame],
) -> None:
    """Kfz-Selbstbehalte nur bei Kasko, Hausrat genau eine Konvention je Anfrage (R-041, R-052)."""
    sparte_je_anfrage = _sparte_je_anfrage(datensatz)
    konvention_je_anfrage: dict[str, set[str]] = {}
    for zeile in _zeilen(datensatz["angebot"]):
        sparte = sparte_je_anfrage[str(zeile["anfrage_id"])]
        if sparte == Sparte.HAUSRAT.value:
            gefuellt = [
                name
                for name, wert in (
                    ("prozent", zeile["sb_hausrat_prozent"]),
                    ("eur", zeile["sb_hausrat_eur"]),
                )
                if _gefuellt(wert)
            ]
            assert len(gefuellt) == 1, "Genau eine Selbstbehaltform muss gefuellt sein"
            konvention_je_anfrage.setdefault(str(zeile["anfrage_id"]), set()).add(gefuellt[0])
            assert not _gefuellt(zeile["sb_tk_eur"])
            assert not _gefuellt(zeile["sb_vk_eur"])
        else:
            assert not _gefuellt(zeile["sb_hausrat_prozent"])
            assert not _gefuellt(zeile["sb_hausrat_eur"])
            if sparte == Sparte.KFZ_HAFTPFLICHT.value:
                assert not _gefuellt(zeile["sb_tk_eur"])
                assert not _gefuellt(zeile["sb_vk_eur"])
            elif sparte == Sparte.KFZ_TEILKASKO.value:
                assert not _gefuellt(zeile["sb_vk_eur"])
            elif _gefuellt(zeile["sb_tk_eur"]) and _gefuellt(zeile["sb_vk_eur"]):
                assert zeile["sb_vk_eur"] >= zeile["sb_tk_eur"]

    assert konvention_je_anfrage
    for kennung, konventionen in konvention_je_anfrage.items():
        assert len(konventionen) == 1, f"Anfrage {kennung} mischt die Selbstbehaltformen"


def test_spreizung_bleibt_unter_dem_schwellenwert(
    datensatz: dict[str, pd.DataFrame], testkonfiguration: Config
) -> None:
    """Die Spreizung je Anfrage bleibt unter dem Schwellenwert von R-047."""
    grenze = testkonfiguration.schwellen.r047_spreizung_max
    bepreist = datensatz["angebot"].dropna(subset=["zahlbeitrag_rate_eur"])
    spanne = bepreist.groupby("anfrage_id")["zahlbeitrag_rate_eur"].agg(["min", "max"])
    for kleinste, groesste in zip(spanne["min"], spanne["max"], strict=True):
        assert float(groesste) / float(kleinste) <= grenze


# ---------------------------------------------------------------------------
# Anfrage und Zahlung
# ---------------------------------------------------------------------------


def test_vorvertrag_bei_schadenfreien_jahren(datensatz: dict[str, pd.DataFrame]) -> None:
    """Weist die SF-Klasse schadenfreie Jahre aus, liegt ein Vorvertrag vor."""
    vorvertrag = {
        str(kennung): bool(wert)
        for kennung, wert in zip(
            datensatz["anfrage"]["anfrage_id"],
            datensatz["anfrage"]["vorvertrag_vorhanden"],
            strict=True,
        )
    }
    for kennung, klasse in zip(
        datensatz["risiko_kfz"]["anfrage_id"],
        datensatz["risiko_kfz"]["sf_klasse_hp"],
        strict=True,
    ):
        jahre = schadenfreie_jahre(str(klasse))
        if jahre is not None and jahre > 0:
            assert vorvertrag[str(kennung)]


def test_vorversicherer_nur_bei_vorvertrag(datensatz: dict[str, pd.DataFrame]) -> None:
    """Ohne Vorvertrag bleibt ``vorversicherer_vu_nr`` leer."""
    anfragen = datensatz["anfrage"]
    ohne = anfragen[~anfragen["vorvertrag_vorhanden"].fillna(value=False)]
    assert ohne["vorversicherer_vu_nr"].isna().all()
    mit = anfragen[anfragen["vorvertrag_vorhanden"].fillna(value=False)]
    assert mit["vorversicherer_vu_nr"].notna().all()


def test_zeitliche_ordnung_der_anfrage(
    datensatz: dict[str, pd.DataFrame], testkonfiguration: Config
) -> None:
    """Eingang vor Stichtag, Beginn nach Eingang, Beginn hoechstens zwoelf Monate spaeter."""
    stichtag = testkonfiguration.stichtag
    for eingang, beginn in zip(
        datensatz["anfrage"]["eingangszeitpunkt"],
        datensatz["anfrage"]["versicherungsbeginn"],
        strict=True,
    ):
        assert eingang.date() <= stichtag
        assert eingang.date() <= beginn <= datum_plus_jahre(eingang.date(), 1)


def test_iban_und_bic_sind_formal_gueltig(datensatz: dict[str, pd.DataFrame]) -> None:
    """Die IBAN besteht Muster und Pruefziffer, die BIC hat acht oder elf Zeichen."""
    zahlungen = datensatz["zahlung"]
    for iban in zahlungen["iban"]:
        assert hat_deutsches_format(str(iban))
        assert ist_gueltig(str(iban))
    for bic in zahlungen["bic"].dropna():
        assert len(str(bic)) in wb.BIC_LAENGEN


def test_mandat_liegt_vor_dem_versicherungsbeginn(datensatz: dict[str, pd.DataFrame]) -> None:
    """``sepa_mandat_datum`` <= ``versicherungsbeginn``."""
    beginn = {
        str(kennung): wert
        for kennung, wert in zip(
            datensatz["anfrage"]["anfrage_id"],
            datensatz["anfrage"]["versicherungsbeginn"],
            strict=True,
        )
    }
    for kennung, mandat in zip(
        datensatz["zahlung"]["anfrage_id"], datensatz["zahlung"]["sepa_mandat_datum"], strict=True
    ):
        assert mandat <= beginn[str(kennung)]


def test_waehrung_ist_durchgaengig_euro(datensatz: dict[str, pd.DataFrame]) -> None:
    """Der Datensatz fuehrt ausschliesslich Euro (spaeter R-012, zweite Stufe)."""
    assert set(datensatz["anfrage"]["waehrung"]) == {"EUR"}


@pytest.mark.parametrize(
    ("entitaet", "spalte"),
    [
        ("anfrage", "anfrage_id"),
        ("person", "person_id"),
        ("risiko_kfz", "risiko_id"),
        ("risiko_hausrat", "risiko_id"),
        ("tarif", "tarif_id"),
        ("angebot", "angebot_id"),
        ("zahlung", "zahlung_id"),
    ],
)
def test_primaerschluessel_sind_eindeutig(
    datensatz: dict[str, pd.DataFrame], entitaet: str, spalte: str
) -> None:
    """Jeder Primaerschluessel ist eindeutig und nicht leer."""
    werte = datensatz[entitaet][spalte]
    assert werte.notna().all()
    assert werte.nunique() == len(werte)
