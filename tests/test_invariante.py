"""Property-based Test der Kern-Invariante.

**Die Invariante lautet: Schemakonforme Daten erzeugen null Meldungen.** Sie ist
die Grundannahme der gesamten Auswertung. Traegt sie nicht, ist jede spaeter
berichtete Precision wertlos, denn dann meldet der Detektor Fehler, die keine sind.

Der Clean-Baseline-Lauf prueft dieselbe Aussage an **einem** Datensatz. Dieser Test
prueft sie an zweihundert zufaellig gezogenen — und zwar mit einer Strategie, die
den Generator **nicht** kennt. Ein Generatorfehler, der sich in beiden Richtungen
gleich auswirkt, faellt hier auf und dort nicht.

Warum die Invariante auf G1 und G2 beschraenkt ist
--------------------------------------------------

Fuer G3 bis G5 waere sie **falsch**, nicht bloss unvollstaendig:

* G3 prueft Bedingungen zwischen Zeilen. Eine einzelne, fuer sich schemakonforme
  Zeile kann eine Rangfolge oder eine Verteilung gar nicht erfuellen — R-048
  vergleicht gegen eine Verteilung ueber den Gesamtdatensatz.
* G4 prueft referenzielle Integritaet gegen Referenztabellen. Eine zufaellig
  gezogene, schemakonforme Postleitzahl steht mit hoher Wahrscheinlichkeit nicht
  in ``plz_ort.csv`` — der Verstoss waere ein Artefakt der Strategie.
* G5 prueft quellenuebergreifende Bedingungen ueber mehrere Angebote hinweg.

Eine hypothesis-Strategie, die einen referenziell konsistenten
Mehrtabellen-Graphen erzeugt, wuerde im Kern den Generator nachbauen — und damit
gegen sich selbst testen. Die Einschraenkung ist deshalb methodisch sauber; sie
muss aber, und genau dafuer steht dieser Docstring, ausdruecklich benannt werden.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.common import wertebereiche as wb
from src.common.datum import datum_plus_jahre, jahre_zwischen
from src.common.enums import (
    BAUARTKLASSEN,
    RATENANZAHL_JE_ZAHLWEISE,
    SF_KLASSEN,
    ZAHLWEISEN_IM_GENERATOR,
    Abstellplatz,
    Anfragestatus,
    Anrede,
    Antriebsart,
    ArtKennzeichen,
    Eigentumsverhaeltnis,
    Familienstand,
    Gebaeudeart,
    Kanal,
    Nutzerkreis,
    Nutzungsart,
    Quellschnittstelle,
    Sparte,
    Zahlweise,
    ist_kfz_sparte,
    schadenfreie_jahre,
    sf_ordnung,
)
from src.common.geld import runde
from src.common.iban import baue_iban
from src.rules.engine import pruefe_alles
from src.rules.katalog import REGELN_JE_GRUPPE
from tests.test_regeln.bausteine import REFERENZ, baue

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    from src.common.config import Config

#: Zahl der Beispiele. Jedes Beispiel enthaelt **eine Zeile je Entitaet**, damit
#: sind alle sieben Entitaeten mit mindestens so vielen Beispielen abgedeckt.
BEISPIELE = 200

#: Die geprueften Regelgruppen (siehe Modul-Docstring).
GEPRUEFTE_GRUPPEN = ("G1", "G2")

#: Sentinelwoerter, die eine zufaellig gezogene Zeichenkette nicht treffen darf.
#:
#: Ein zufaellig erzeugter Nachname "Unbekannt" waere fuer R-025 ein impliziter
#: Fehlwert — und der Testfehler laege dann an der Strategie, nicht an der Regel.
_VERBOTENE_WOERTER = {wert.casefold() for wert in wb.SENTINEL_TEXT}


def _wort(mindestens: int = 2, hoechstens: int = 12) -> st.SearchStrategy[str]:
    """Zieht ein Wort aus Buchstaben, das kein Sentinelwort ist."""
    return st.from_regex(
        rf"[A-Z][a-z]{{{mindestens - 1},{hoechstens - 1}}}", fullmatch=True
    ).filter(lambda wert: wert.casefold() not in _VERBOTENE_WOERTER)


def _betrag(unten: int, oben: int, schritt: int = 1) -> st.SearchStrategy[Decimal]:
    """Zieht einen Geldbetrag in vollen Euro; Sentinelwerte sind ausgeschlossen.

    Die Rasterung haelt 9999 und 99999999 zuverlaessig aus dem Wertevorrat: Bei
    einer Schrittweite von 100 ist 9999 nicht darstellbar. Andernfalls koennte ein
    zufaellig getroffener Sentinelwert R-025 ausloesen — ein Artefakt der
    Strategie, kein Regelfehler.
    """
    return st.integers(unten // schritt, oben // schritt).map(
        lambda wert: Decimal(wert * schritt)
    )


@st.composite
def _vorgang(zeichnung: st.DrawFn, stichtag: dt.date) -> dict[str, list[dict[str, Any]]]:
    """Zieht einen vollstaendigen, schemakonformen Vergleichsvorgang.

    Die Strategie kennt den Generator nicht. Sie kennt **das Datenmodell**: Sie
    haelt die Abhaengigkeiten aus ``spec/01_datenmodell.md`` ein — Datumsketten,
    Beitragsarithmetik, Zweckbindung — und zieht alles Uebrige frei.

    Args:
        zeichnung: Ziehungsfunktion von hypothesis.
        stichtag: Referenzdatum aus der Konfiguration.

    Returns:
        Je Entitaet eine Zeile, als Abweichung von der Standardzeile aus
        ``tests/test_regeln/bausteine.py``.
    """
    sparte = zeichnung(st.sampled_from([wert.value for wert in Sparte]))
    ist_kfz = ist_kfz_sparte(sparte)

    # --- Person -----------------------------------------------------------
    firma = zeichnung(st.booleans()) and not ist_kfz
    alter = zeichnung(st.integers(*wb.ALTER_VN))
    geburtsdatum = zeichnung(
        st.dates(
            min_value=datum_plus_jahre(stichtag, -(alter + 1)) + dt.timedelta(days=1),
            max_value=datum_plus_jahre(stichtag, -alter),
        )
    )
    tatsaechliches_alter = jahre_zwischen(geburtsdatum, stichtag)
    erwerbsalter = zeichnung(
        st.integers(wb.FUEHRERSCHEIN_MINDESTALTER_JAHRE, max(tatsaechliches_alter, 17))
    )
    fuehrerschein = min(datum_plus_jahre(geburtsdatum, erwerbsalter), stichtag)
    vorname = zeichnung(_wort())
    nachname = zeichnung(_wort())

    person: dict[str, Any] = {
        "anrede": Anrede.FIRMA.value if firma else zeichnung(
            st.sampled_from([Anrede.HERR.value, Anrede.FRAU.value, Anrede.DIVERS.value])
        ),
        "vorname": None if firma else vorname,
        "nachname": nachname,
        "geburtsdatum": None if firma else geburtsdatum,
        "familienstand": None if firma else zeichnung(
            st.sampled_from([wert.value for wert in Familienstand])
        ),
        "plz": zeichnung(st.from_regex(r"\d{5}", fullmatch=True)),
        "ort": zeichnung(_wort()),
        "strasse": zeichnung(_wort()),
        "hausnummer": zeichnung(st.from_regex(r"[1-9][0-9]{0,2}[a-d]?", fullmatch=True)),
        "email": f"{vorname.lower()}.{nachname.lower()}@beispielmail.de",
        "wohneigentum": zeichnung(st.booleans()),
        "fuehrerschein_datum": fuehrerschein if ist_kfz and not firma else None,
    }

    # --- Anfrage ----------------------------------------------------------
    zahlweise = zeichnung(st.sampled_from([int(wert) for wert in ZAHLWEISEN_IM_GENERATOR]))
    ratenanzahl = RATENANZAHL_JE_ZAHLWEISE[Zahlweise(zahlweise)]
    anfrage: dict[str, Any] = {
        "sparte": sparte,
        "kanal": zeichnung(st.sampled_from([wert.value for wert in Kanal])),
        "zahlweise": zahlweise,
        "anfrage_status": zeichnung(st.sampled_from([wert.value for wert in Anfragestatus])),
    }

    # --- Angebot: Beitragsarithmetik strikt von unten nach oben ------------
    netto = zeichnung(_betrag(20, 5000))
    satz = wb.VERSICHERUNGSTEUER_EFFEKTIVSATZ[Sparte(sparte)]
    steuer = runde(netto * satz / Decimal(100))
    brutto = netto + steuer
    zuschlag = (
        Decimal(0)
        if ratenanzahl == 1
        else zeichnung(st.integers(1, 800).map(lambda wert: Decimal(wert) / Decimal(100)))
    )
    rate = runde(brutto * (Decimal(1) + zuschlag / Decimal(100)) / ratenanzahl)
    abgelehnt = zeichnung(st.booleans())

    beitragsfelder: dict[str, Any] = (
        {
            "nettobeitrag_jahr_eur": None,
            "versicherungsteuer_satz": None,
            "versicherungsteuer_eur": None,
            "bruttobeitrag_jahr_eur": None,
            "ratenzahlungszuschlag_prozent": None,
            "zahlbeitrag_rate_eur": None,
            "rang": None,
        }
        if abgelehnt
        else {
            "nettobeitrag_jahr_eur": netto,
            "versicherungsteuer_satz": satz,
            "versicherungsteuer_eur": steuer,
            "bruttobeitrag_jahr_eur": brutto,
            "ratenzahlungszuschlag_prozent": runde(zuschlag),
            "zahlbeitrag_rate_eur": rate,
            "rang": 1,
        }
    )
    angebot: dict[str, Any] = {
        **beitragsfelder,
        "annahmeentscheidung": "ABLEHNUNG" if abgelehnt else "ANNAHME",
        "quell_schnittstelle": zeichnung(
            st.sampled_from([wert.value for wert in Quellschnittstelle])
        ),
        **_selbstbehalte(zeichnung, sparte),
    }

    # --- Tarif ------------------------------------------------------------
    tarif: dict[str, Any] = {
        "sparte": sparte,
        "deckungssumme_personen_eur": zeichnung(
            _betrag(7_500_000, 50_000_000, schritt=100_000)
        ),
        "deckungssumme_sach_eur": zeichnung(_betrag(1_300_000, 50_000_000, schritt=100_000)),
        "deckungssumme_vermoegen_eur": zeichnung(_betrag(50_000, 5_000_000, schritt=10_000)),
        "werkstattbindung": zeichnung(st.booleans()),
    }

    zeilen: dict[str, list[dict[str, Any]]] = {
        "anfrage": [anfrage],
        "person": [person],
        "tarif": [tarif],
        "angebot": [angebot],
        "zahlung": [_zahlung(zeichnung)],
    }
    if ist_kfz:
        zeilen["risiko_kfz"] = [
            _risiko_kfz(zeichnung, sparte=sparte, alter=tatsaechliches_alter, stichtag=stichtag)
        ]
    else:
        zeilen["risiko_hausrat"] = [_risiko_hausrat(zeichnung, stichtag=stichtag)]
    return zeilen


def _selbstbehalte(zeichnung: st.DrawFn, sparte: str) -> dict[str, Any]:
    """Zieht die Selbstbehalte gemaess Zweckbindung und Exklusivitaet (R-041)."""
    if sparte == Sparte.HAUSRAT.value:
        in_prozent = zeichnung(st.booleans())
        return {
            "sb_tk_eur": None,
            "sb_vk_eur": None,
            "sb_hausrat_prozent": (
                zeichnung(st.sampled_from([Decimal("0.00"), Decimal("10.00")]))
                if in_prozent
                else None
            ),
            "sb_hausrat_eur": (
                None if in_prozent else zeichnung(st.sampled_from(list(wb.SB_HAUSRAT_EUR_STUFEN)))
            ),
        }
    if sparte == Sparte.KFZ_HAFTPFLICHT.value:
        return {
            "sb_tk_eur": None,
            "sb_vk_eur": None,
            "sb_hausrat_prozent": None,
            "sb_hausrat_eur": None,
        }
    sb_vk = (
        zeichnung(st.sampled_from(list(wb.SB_VK_EUR_STUFEN)))
        if sparte == Sparte.KFZ_VOLLKASKO.value
        else None
    )
    moegliche_tk = [
        stufe for stufe in wb.SB_TK_EUR_STUFEN if sb_vk is None or stufe <= sb_vk
    ]
    return {
        "sb_tk_eur": zeichnung(st.sampled_from(moegliche_tk)),
        "sb_vk_eur": sb_vk,
        "sb_hausrat_prozent": None,
        "sb_hausrat_eur": None,
    }


def _risiko_kfz(
    zeichnung: st.DrawFn, *, sparte: str, alter: int, stichtag: dt.date
) -> dict[str, Any]:
    """Zieht ein schemakonformes Kfz-Risiko mit gueltiger Datums- und SF-Kette."""
    erstzulassung = zeichnung(
        st.dates(min_value=wb.ERSTZULASSUNG_FRUEHESTENS, max_value=stichtag)
    )
    zulassung = zeichnung(st.dates(min_value=erstzulassung, max_value=stichtag))
    neupreis = zeichnung(_betrag(10_000, 250_000, schritt=100))
    antrieb = zeichnung(st.sampled_from([wert.value for wert in Antriebsart]))
    elektrisch = antrieb in {Antriebsart.ELEKTRO.value, Antriebsart.HYBRID.value}
    kennzeichen = zeichnung(
        st.sampled_from(
            [ArtKennzeichen.NORMAL.value, ArtKennzeichen.SAISON.value]
            + ([ArtKennzeichen.ELEKTRO.value] if elektrisch else [])
        )
    )

    obergrenze = min(alter - wb.FUEHRERSCHEIN_MINDESTALTER_JAHRE, len(SF_KLASSEN))
    zulaessig = [
        klasse
        for klasse in SF_KLASSEN
        if (schadenfreie_jahre(klasse) or 0) <= max(obergrenze, 0)
    ]
    sf_hp = zeichnung(st.sampled_from(zulaessig))
    ordnung_hp = sf_ordnung(sf_hp)
    sf_vk = (
        zeichnung(
            st.sampled_from(
                [
                    klasse
                    for klasse in zulaessig
                    if (sf_ordnung(klasse) or 0) <= (ordnung_hp if ordnung_hp is not None else 0)
                ]
            )
        )
        if sparte == Sparte.KFZ_VOLLKASKO.value
        else None
    )
    kasko = sparte in {Sparte.KFZ_VOLLKASKO.value, Sparte.KFZ_TEILKASKO.value}

    return {
        "hsn": zeichnung(st.from_regex(r"\d{4}", fullmatch=True)),
        "tsn": zeichnung(st.from_regex(r"[A-Z0-9]{3}", fullmatch=True)),
        "erstzulassung": erstzulassung,
        "zulassung_auf_vn": zulassung,
        "leistung_kw": zeichnung(st.integers(*wb.GENERATOR_LEISTUNG_KW)),
        "antriebsart": antrieb,
        "neupreis_eur": neupreis,
        "fahrzeugwert_aktuell": zeichnung(
            st.integers(0, int(neupreis) // 100).map(lambda wert: Decimal(wert * 100))
        ),
        "art_kennzeichen": kennzeichen,
        "jahresfahrleistung_km": zeichnung(
            st.integers(*wb.GENERATOR_JAHRESFAHRLEISTUNG_KM)
        ),
        "nutzungsart": zeichnung(st.sampled_from([wert.value for wert in Nutzungsart])),
        "eigentumsverhaeltnis": zeichnung(
            st.sampled_from([wert.value for wert in Eigentumsverhaeltnis])
        ),
        "nutzerkreis": zeichnung(st.sampled_from([wert.value for wert in Nutzerkreis])),
        "alter_juengster_fahrer": zeichnung(
            st.integers(wb.ALTER_JUENGSTER_FAHRER[0], max(alter, wb.ALTER_JUENGSTER_FAHRER[0]))
        ),
        "abstellplatz": zeichnung(st.sampled_from([wert.value for wert in Abstellplatz])),
        "sf_klasse_hp": sf_hp,
        "sf_klasse_vk": sf_vk,
        "schaeden_letzte_5j": zeichnung(st.integers(0, 5)),
        "typklasse_hp": zeichnung(st.integers(*wb.TYPKLASSE_HP)),
        "typklasse_tk": zeichnung(st.integers(*wb.TYPKLASSE_TK)) if kasko else None,
        "typklasse_vk": (
            zeichnung(st.integers(*wb.TYPKLASSE_VK))
            if sparte == Sparte.KFZ_VOLLKASKO.value
            else None
        ),
        "regionalklasse_hp": zeichnung(st.integers(*wb.REGIONALKLASSE_HP)),
        "regionalklasse_tk": zeichnung(st.integers(*wb.REGIONALKLASSE_TK)),
        "regionalklasse_vk": zeichnung(st.integers(*wb.REGIONALKLASSE_VK)),
    }


def _risiko_hausrat(zeichnung: st.DrawFn, *, stichtag: dt.date) -> dict[str, Any]:
    """Zieht ein schemakonformes Hausratrisiko."""
    wohnflaeche = zeichnung(st.integers(*wb.GENERATOR_WOHNFLAECHE_QM))
    summe = zeichnung(_betrag(10_000, 800_000, schritt=1_000))
    grenze = wb.UNTERVERSICHERUNGSVERZICHT_EUR_JE_QM * wohnflaeche
    gebaeudeart = zeichnung(st.sampled_from([wert.value for wert in Gebaeudeart]))
    return {
        "wohnflaeche_qm": wohnflaeche,
        "versicherungssumme_eur": summe,
        "unterversicherungsverzicht": (
            zeichnung(st.booleans()) if summe >= grenze else False
        ),
        "bauartklasse": zeichnung(st.sampled_from(list(BAUARTKLASSEN))),
        "baujahr": zeichnung(st.integers(wb.BAUJAHR_UNTERGRENZE_REGEL, stichtag.year)),
        "gebaeudeart": gebaeudeart,
        "stockwerk": zeichnung(st.integers(*wb.STOCKWERK)),
        "zuers_zone": zeichnung(st.sampled_from(list(wb.ZUERS_ZONEN))),
        "elementar_eingeschlossen": zeichnung(st.booleans()),
        "sublimit_fahrrad_eur": zeichnung(
            st.integers(0, min(10_000, int(summe)) // 100).map(
                lambda wert: Decimal(wert * 100)
            )
        ),
        "sublimit_wertsachen_eur": zeichnung(
            st.integers(0, int(summe * wb.WERTSACHEN_ANTEIL_MAX) // 100).map(
                lambda wert: Decimal(wert * 100)
            )
        ),
    }


def _zahlung(zeichnung: st.DrawFn) -> dict[str, Any]:
    """Zieht eine Bankverbindung mit gueltiger IBAN-Pruefziffer."""
    blz = zeichnung(st.integers(10_000_000, 99_999_999))
    konto = zeichnung(st.integers(0, 9_999_999_999))
    lang = zeichnung(st.booleans())
    kennung = zeichnung(st.from_regex(r"[A-Z]{4}DE[A-Z0-9]{2}", fullmatch=True))
    return {
        "iban": baue_iban(f"{blz:08d}", f"{konto:010d}"),
        "bic": kennung + zeichnung(st.from_regex(r"[A-Z0-9]{3}", fullmatch=True))
        if lang
        else kennung,
        "kontoinhaber": zeichnung(_wort()),
    }


def _geprueft() -> Sequence[Any]:
    """Gibt die Regeln der Gruppen G1 und G2 zurueck."""
    return [regel for gruppe in GEPRUEFTE_GRUPPEN for regel in REGELN_JE_GRUPPE[gruppe]]


@pytest.fixture(scope="session")
def stichtag(config: Config) -> dt.date:
    """Referenzdatum aus der Konfiguration."""
    return config.stichtag


@given(daten=st.data())
@settings(
    max_examples=BEISPIELE,
    # Jedes Beispiel fuehrt zweiundvierzig Regeln aus; die Vorgabefrist von
    # 200 Millisekunden je Beispiel misst hier die Katalogausfuehrung, nicht die
    # Strategie, und ist deshalb keine sinnvolle Schranke.
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_schemakonforme_daten_erzeugen_null_meldungen(
    config: Config, stichtag: dt.date, daten: st.DataObject
) -> None:
    """Die Kern-Invariante: G1 und G2 schweigen auf schemakonformen Daten.

    Schlaegt dieser Test fehl, gibt hypothesis den kleinsten ausloesenden Vorgang
    aus. Er ist dann entweder ein Regelfehler — die Regel ist zu streng — oder ein
    Fehler der Strategie, die das Datenmodell verletzt. Beides gehoert vor dem
    Freeze geklaert.
    """
    zeilen = daten.draw(_vorgang(stichtag))
    kontext = baue(config, zeilen, referenz=REFERENZ)
    detektionen = pruefe_alles(kontext, _geprueft())

    assert detektionen.anzahl_meldungen == 0, (
        "Schemakonforme Daten haben Meldungen erzeugt: "
        + "; ".join(
            f"{zeile.regel_id} {zeile.entitaet}.{zeile.spalte}: {zeile.meldung}"
            for zeile in detektionen.verstoesse.itertuples()
        )
    )


def test_gruppenabgrenzung_ist_vollstaendig() -> None:
    """Die Invariante deckt genau G1 und G2 ab — die Abgrenzung steht im Docstring."""
    geprueft = {regel.regel_id for regel in _geprueft()}
    uebrig = {
        regel.regel_id
        for gruppe in ("G3", "G4", "G5")
        for regel in REGELN_JE_GRUPPE[gruppe]
    }
    assert geprueft & uebrig == set()
    assert len(geprueft) + len(uebrig) == 58


def test_die_einschraenkung_ist_nicht_kosmetisch(config: Config) -> None:
    """Belegt, warum G4 nicht in die Invariante gehoert.

    Eine fuer sich schemakonforme Postleitzahl — fuenf Ziffern, als Zeichenkette
    gefuehrt — steht deshalb noch lange nicht in ``plz_ort.csv``. G1 und G2
    schweigen dazu voellig zu Recht, R-050 meldet ebenso zu Recht. Ohne die
    Einschraenkung waere dieser Fall ein Fehlschlag der Invariante, obwohl weder
    Regel noch Daten falsch sind.
    """
    zeilen: dict[str, list[dict[str, Any]]] = {
        "anfrage": [{}],
        "person": [{"plz": "54321", "ort": "Nirgendwo"}],
        "risiko_kfz": [{}],
        "tarif": [{}],
        "angebot": [{}],
        "zahlung": [{}],
    }
    kontext = baue(config, zeilen, referenz=REFERENZ)

    assert pruefe_alles(kontext, _geprueft()).anzahl_meldungen == 0
    aus_g4 = pruefe_alles(kontext, list(REGELN_JE_GRUPPE["G4"]))
    assert aus_g4.anzahl_meldungen > 0, "R-050 muss die unbekannte Postleitzahl melden"
