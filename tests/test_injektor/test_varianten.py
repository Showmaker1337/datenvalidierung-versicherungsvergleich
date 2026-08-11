"""Je Injektionsvariante ein Test auf die beabsichtigte Form der Verfaelschung.

``spec/03_fehlerklassen.md``, Abschnitt 2 beschreibt sechzig Varianten. Dass sie
**irgendetwas** veraendern, prueft schon der Ground-Truth-Test. Hier wird
geprueft, dass jede Variante genau das tut, was ihre Zeile in der Spezifikation
sagt — dass F3-d also tatsaechlich ``zahlweise = 3`` setzt und nicht bloss
irgendeinen anderen Wert.

Der Aufbau ist bewusst tabellarisch: :data:`PRUEFUNGEN` ordnet jeder
Variantenkennung ihre Formpruefung zu, und :func:`test_jede_variante_hat_eine_pruefung`
haelt fest, dass keine Variante ohne Pruefung bleibt. Eine neu hinzugefuegte
Variante ohne Test faellt damit sofort auf.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import TYPE_CHECKING, Final

import pytest

from src.common.datum import datum_plus_jahre
from src.common.enums import Antriebsart, ArtKennzeichen, Zahlweise
from src.common.seeding import Strom, generator, lauf_seed
from src.common.serialisierung import FELDTYP_JE_SPALTE, Feldtyp
from src.common.wertebereiche import (
    BIC_LAENGEN,
    FUEHRERSCHEIN_MINDESTALTER_JAHRE,
    IBAN_LAENGE_DE,
    REGIONALKLASSE_HP,
    REGIONALKLASSE_TK,
    REGIONALKLASSE_VK,
    VERSICHERUNGSTEUER_NOMINALSATZ,
)
from src.injector.modell import baue_kontext
from src.injector.rohwerte import (
    betrag_lesen,
    excel_serial,
    ganzzahl_lesen,
    monate_verschieben,
    tag_lesen,
    zeitpunkt_lesen,
)
from src.injector.varianten import ALLE_VARIANTEN, variante

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Callable, Mapping

    import pandas as pd
    from numpy.random import Generator

    from src.common.config import Config
    from src.injector.modell import (
        Aenderung,
        Injektionskontext,
        Kandidat,
        Variante,
        Zellaenderung,
    )

#: Toleranz beim Vergleich skalierter Betraege — eine Rundungsstelle.
_RUNDUNG: Final[Decimal] = Decimal("0.01")

#: Obergrenze je Regionalklassenfeld (GDV-Regionalklassenverzeichnis).
_REGIONALKLASSEN_OBERGRENZE: Final[Mapping[str, int]] = {
    "regionalklasse_hp": REGIONALKLASSE_HP[1],
    "regionalklasse_tk": REGIONALKLASSE_TK[1],
    "regionalklasse_vk": REGIONALKLASSE_VK[1],
}

#: Das Beitragstupel, das die Skalierungsvarianten gemeinsam veraendern.
_BEITRAGSSPALTEN: Final[tuple[str, ...]] = (
    "nettobeitrag_jahr_eur",
    "versicherungsteuer_eur",
    "bruttobeitrag_jahr_eur",
    "zahlbeitrag_rate_eur",
)


@pytest.fixture(scope="module")
def kontext(config_injektor: Config, daten_clean: dict[str, pd.DataFrame]) -> Injektionskontext:
    """Die lesende Sicht des Injektors auf den sauberen Datensatz."""
    return baue_kontext(config_injektor, daten_clean)


def _rng(variante_id: str) -> Generator:
    """Baut einen festen, je Variante verschiedenen Zufallsstrom."""
    return generator(
        lauf_seed(20260630, Strom.INJEKTION, len(variante_id), ord(variante_id[-1]))
    )


def _anwenden(kontext: Injektionskontext, eintrag: Variante) -> tuple[Kandidat, Aenderung]:
    """Wendet eine Variante auf den ersten brauchbaren Kandidaten an."""
    rng = _rng(eintrag.variante_id)
    for kandidat in eintrag.kandidaten(kontext):
        aenderung = eintrag.anwenden(kontext, kandidat, rng)
        if aenderung is not None and (aenderung.zellen or aenderung.saetze):
            return kandidat, aenderung
    pytest.fail(f"Variante {eintrag.variante_id} findet keinen brauchbaren Kandidaten")


def _traeger(aenderung: Aenderung) -> tuple[Zellaenderung, ...]:
    """Gibt die Traegerzellen einer Aenderung zurueck."""
    return tuple(zelle for zelle in aenderung.zellen if not zelle.mitgezogen)


def _mitgezogen(aenderung: Aenderung) -> tuple[Zellaenderung, ...]:
    """Gibt die nur nachgefuehrten Zellen einer Aenderung zurueck."""
    return tuple(zelle for zelle in aenderung.zellen if zelle.mitgezogen)


def _eine(aenderung: Aenderung) -> Zellaenderung:
    """Gibt die einzige Traegerzelle zurueck."""
    zellen = _traeger(aenderung)
    assert len(zellen) == 1, f"Erwartet wurde genau eine Traegerzelle, es waren {len(zellen)}"
    return zellen[0]


def _clean(kontext: Injektionskontext, zelle: Zellaenderung) -> str:
    """Liest den sauberen Wert einer veraenderten Zelle."""
    return kontext.wert(zelle.entitaet, zelle.row_id, zelle.spalte)


def _je_spalte(aenderung: Aenderung, row_id: int) -> dict[str, str | None]:
    """Sammelt die neuen Werte einer Zeile je Spalte."""
    return {
        zelle.spalte: zelle.wert_dirty for zelle in aenderung.zellen if zelle.row_id == row_id
    }


def _neue_zeile(aenderung: Aenderung) -> Mapping[str, str]:
    """Gibt die Werte der einzigen hinzugefuegten Zeile zurueck."""
    assert len(aenderung.saetze) == 1
    return aenderung.saetze[0].werte


# ---------------------------------------------------------------------------
# F1 — fehlender Wert
# ---------------------------------------------------------------------------


def _pruefe_f1a(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F1-a setzt den Wert auf fehlend, nicht auf den Leerstring."""
    zelle = _eine(aenderung)
    assert zelle.wert_dirty is None
    assert _clean(kontext, zelle) != ""


def _pruefe_fester_wert(erwartet: str) -> Callable[..., None]:
    """Baut eine Pruefung auf einen festen Rohwert."""

    def pruefe(
        kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung
    ) -> None:
        zelle = _eine(aenderung)
        assert zelle.wert_dirty == erwartet
        assert _clean(kontext, zelle) != erwartet

    return pruefe


def _pruefe_f1e(_kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F1-e setzt das zum Feldtyp passende numerische Sentinel."""
    zelle = _eine(aenderung)
    feldtyp = FELDTYP_JE_SPALTE[zelle.spalte]
    assert feldtyp in {Feldtyp.GANZZAHL, Feldtyp.DEZIMAL}
    erwartet = "9999" if feldtyp is Feldtyp.GANZZAHL else "99999999.00"
    assert zelle.wert_dirty == erwartet


def _pruefe_f1f(_kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F1-f setzt den 1. Januar 1900 im GDV-Format."""
    zelle = _eine(aenderung)
    assert FELDTYP_JE_SPALTE[zelle.spalte] is Feldtyp.DATUM
    assert zelle.wert_dirty == "01011900"
    assert tag_lesen(str(zelle.wert_dirty)) == dt.date(1900, 1, 1)


# ---------------------------------------------------------------------------
# F2 — Format und Syntax
# ---------------------------------------------------------------------------


def _pruefe_f2a(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F2-a verliert die fuehrende Null der Postleitzahl."""
    zelle = _eine(aenderung)
    clean = _clean(kontext, zelle)
    assert zelle.spalte == "plz"
    assert clean.startswith("0")
    assert zelle.wert_dirty == str(int(clean))
    assert len(str(zelle.wert_dirty)) < len(clean)


def _pruefe_f2b(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F2-b erzeugt eine vier- oder sechsstellige Postleitzahl."""
    zelle = _eine(aenderung)
    dirty = str(zelle.wert_dirty)
    assert zelle.spalte == "plz"
    assert len(_clean(kontext, zelle)) == 5
    assert len(dirty) in {4, 6}
    assert dirty.isdigit()


def _pruefe_f2c(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F2-c aendert genau eine Ziffer; Laenge und Muster bleiben."""
    zelle = _eine(aenderung)
    clean = _clean(kontext, zelle)
    dirty = str(zelle.wert_dirty)
    assert len(dirty) == IBAN_LAENGE_DE
    assert dirty.startswith("DE")
    assert dirty[2:].isdigit()
    abweichend = [i for i in range(IBAN_LAENGE_DE) if clean[i] != dirty[i]]
    assert len(abweichend) == 1


def _pruefe_f2d(_kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F2-d erzeugt eine IBAN mit 21 oder 23 Zeichen."""
    zelle = _eine(aenderung)
    dirty = str(zelle.wert_dirty)
    assert len(dirty) in {IBAN_LAENGE_DE - 1, IBAN_LAENGE_DE + 1}
    assert dirty.startswith("DE")


def _pruefe_f2e(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F2-e erzeugt eine BIC mit 9 oder 10 Zeichen — beide gibt es nicht."""
    zelle = _eine(aenderung)
    assert len(_clean(kontext, zelle)) in BIC_LAENGEN
    assert len(str(zelle.wert_dirty)) in {9, 10}


def _pruefe_f2f(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F2-f erzeugt acht Ziffern, die keinen Kalendertag ergeben."""
    zelle = _eine(aenderung)
    dirty = str(zelle.wert_dirty)
    assert len(dirty) == 8
    assert dirty.isdigit()
    assert dirty[:4] == "3102"
    assert tag_lesen(dirty) is None
    assert tag_lesen(_clean(kontext, zelle)) is not None


def _pruefe_f2g(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F2-g setzt den Monat auf 13."""
    zelle = _eine(aenderung)
    dirty = str(zelle.wert_dirty)
    assert dirty[2:4] == "13"
    assert dirty[:2] == _clean(kontext, zelle)[:2]
    assert tag_lesen(dirty) is None


def _pruefe_f2h(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F2-h schreibt dasselbe Datum im ISO-Format."""
    zelle = _eine(aenderung)
    tag = tag_lesen(_clean(kontext, zelle))
    assert tag is not None
    assert zelle.wert_dirty == tag.isoformat()


def _pruefe_f2i(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F2-i schreibt die Seriennummer einer Tabellenkalkulation."""
    zelle = _eine(aenderung)
    tag = tag_lesen(_clean(kontext, zelle))
    assert tag is not None
    assert zelle.wert_dirty == str(excel_serial(tag))


def _pruefe_f2j(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F2-j kuerzt die HSN auf drei Stellen."""
    zelle = _eine(aenderung)
    assert zelle.spalte == "hsn"
    assert len(_clean(kontext, zelle)) == 4
    assert len(str(zelle.wert_dirty)) == 3


def _pruefe_f2k(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F2-k schreibt die TSN klein."""
    zelle = _eine(aenderung)
    clean = _clean(kontext, zelle)
    assert zelle.spalte == "tsn"
    assert zelle.wert_dirty == clean.lower()
    assert zelle.wert_dirty != clean


def _pruefe_f2l(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F2-l entfernt den Klammeraffen oder den Punkt der Domain."""
    zelle = _eine(aenderung)
    clean = _clean(kontext, zelle)
    dirty = str(zelle.wert_dirty)
    assert zelle.spalte == "email"
    assert len(dirty) == len(clean) - 1
    _, trenner, domain = dirty.partition("@")
    assert not trenner or "." not in domain


# ---------------------------------------------------------------------------
# F3 — Wertebereich und Katalog
# ---------------------------------------------------------------------------


def _pruefe_typklasse(erwartet: str) -> Callable[..., None]:
    """Baut eine Pruefung auf einen festen Typklassenwert."""

    def pruefe(
        _kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung
    ) -> None:
        zelle = _eine(aenderung)
        assert zelle.spalte.startswith("typklasse_")
        assert zelle.wert_dirty == erwartet

    return pruefe


def _pruefe_f3c(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F3-c macht aus der Typklasse einen Text mit Praefix."""
    zelle = _eine(aenderung)
    assert zelle.spalte.startswith("typklasse_")
    assert zelle.wert_dirty == "TK" + _clean(kontext, zelle)
    assert ganzzahl_lesen(str(zelle.wert_dirty)) is None


def _pruefe_zahlweise(erwartet: str) -> Callable[..., None]:
    """Baut eine Pruefung auf einen Zahlweisenschluessel ausserhalb des Katalogs."""

    def pruefe(
        _kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung
    ) -> None:
        zelle = _eine(aenderung)
        assert zelle.entitaet == "anfrage"
        assert zelle.spalte == "zahlweise"
        assert zelle.wert_dirty == erwartet
        assert int(erwartet) not in {stufe.value for stufe in Zahlweise}

    return pruefe


def _pruefe_f3f(_kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F3-f setzt die ZUERS-Zone auf 5."""
    zelle = _eine(aenderung)
    assert zelle.spalte == "zuers_zone"
    assert zelle.wert_dirty == "5"


def _pruefe_f3g(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F3-g nimmt der Schadenfreiheitsklasse ihr Praefix."""
    zelle = _eine(aenderung)
    clean = _clean(kontext, zelle)
    assert zelle.spalte.startswith("sf_klasse_")
    assert clean.startswith("SF")
    assert zelle.wert_dirty == clean.removeprefix("SF")
    assert str(zelle.wert_dirty).isdigit()


def _pruefe_f3h(_kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F3-h setzt die Bauartklasse auf den nicht existierenden Buchstaben J."""
    zelle = _eine(aenderung)
    assert zelle.spalte == "bauartklasse"
    assert zelle.wert_dirty == "J"


def _pruefe_f3i(_kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F3-i setzt die Regionalklasse auf null oder ueber die Obergrenze."""
    zelle = _eine(aenderung)
    obergrenze = _REGIONALKLASSEN_OBERGRENZE[zelle.spalte]
    wert = ganzzahl_lesen(str(zelle.wert_dirty))
    assert wert is not None
    assert wert == 0 or wert > obergrenze


# ---------------------------------------------------------------------------
# F4 — fachlich unmoeglich
# ---------------------------------------------------------------------------


def _pruefe_f4a(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F4-a legt die Erstzulassung zwei Jahre hinter den Stichtag."""
    zelle = _eine(aenderung)
    assert zelle.spalte == "erstzulassung"
    assert tag_lesen(str(zelle.wert_dirty)) == datum_plus_jahre(kontext.config.stichtag, 2)


def _pruefe_f4b(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F4-b legt das Baujahr fuenf Jahre hinter den Stichtag."""
    zelle = _eine(aenderung)
    assert zelle.spalte == "baujahr"
    assert zelle.wert_dirty == str(kontext.config.stichtag.year + 5)


def _pruefe_wohnflaeche(erwartet: str) -> Callable[..., None]:
    """Baut eine Pruefung auf eine feste Wohnflaeche."""

    def pruefe(
        _kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung
    ) -> None:
        zelle = _eine(aenderung)
        assert zelle.spalte == "wohnflaeche_qm"
        assert zelle.wert_dirty == erwartet

    return pruefe


def _pruefe_f4e(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F4-e setzt den Fahrzeugwert auf das Dreifache des Neupreises."""
    zelle = _eine(aenderung)
    neupreis = betrag_lesen(kontext.wert(zelle.entitaet, zelle.row_id, "neupreis_eur"))
    assert neupreis is not None
    assert zelle.spalte == "fahrzeugwert_aktuell"
    assert betrag_lesen(str(zelle.wert_dirty)) == neupreis * 3


def _pruefe_f4f(_kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F4-f setzt die Personendeckungssumme unter das gesetzliche Mindestmass."""
    zelle = _eine(aenderung)
    assert zelle.spalte == "deckungssumme_personen_eur"
    assert zelle.wert_dirty == "5000000.00"


def _pruefe_f4g(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F4-g dreht das Vorzeichen eines Betrags."""
    zelle = _eine(aenderung)
    clean = betrag_lesen(_clean(kontext, zelle))
    dirty = betrag_lesen(str(zelle.wert_dirty))
    assert clean is not None
    assert dirty is not None
    assert clean > 0
    assert dirty == -clean


# ---------------------------------------------------------------------------
# F5 — Intra-Record-Inkonsistenz
# ---------------------------------------------------------------------------


def _pruefe_f5a(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F5-a vertauscht Brutto und Netto."""
    zellen = _traeger(aenderung)
    assert len(zellen) == 2
    werte = _je_spalte(aenderung, zellen[0].row_id)
    brutto = kontext.wert("angebot", zellen[0].row_id, "bruttobeitrag_jahr_eur")
    netto = kontext.wert("angebot", zellen[0].row_id, "nettobeitrag_jahr_eur")
    assert werte["bruttobeitrag_jahr_eur"] == netto
    assert werte["nettobeitrag_jahr_eur"] == brutto


def _pruefe_f5b(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F5-b rechnet die Steuer mit dem vollen Nominalsatz."""
    zelle = _eine(aenderung)
    netto = betrag_lesen(kontext.wert(zelle.entitaet, zelle.row_id, "nettobeitrag_jahr_eur"))
    satz = betrag_lesen(kontext.wert(zelle.entitaet, zelle.row_id, "versicherungsteuer_satz"))
    assert netto is not None
    assert satz is not None
    assert satz != VERSICHERUNGSTEUER_NOMINALSATZ
    erwartet = betrag_lesen(str(zelle.wert_dirty))
    assert erwartet is not None
    assert abs(erwartet - netto * VERSICHERUNGSTEUER_NOMINALSATZ / 100) <= _RUNDUNG


def _pruefe_f5c(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F5-c traegt den Steuersatz der anderen Sparte ein."""
    zelle = _eine(aenderung)
    clean = betrag_lesen(_clean(kontext, zelle))
    dirty = betrag_lesen(str(zelle.wert_dirty))
    assert zelle.spalte == "versicherungsteuer_satz"
    assert {clean, dirty} == {Decimal("19.00"), Decimal("16.15")}


def _pruefe_senkung(abweichung: Decimal) -> Callable[..., None]:
    """Baut eine Pruefung auf eine Senkung des Bruttobeitrags."""

    def pruefe(
        kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung
    ) -> None:
        zelle = _eine(aenderung)
        clean = betrag_lesen(_clean(kontext, zelle))
        dirty = betrag_lesen(str(zelle.wert_dirty))
        assert clean is not None
        assert dirty is not None
        assert zelle.spalte == "bruttobeitrag_jahr_eur"
        assert clean - dirty == abweichung, "F5-d und F5-e sind Senkungen, keine Erhoehungen"

    return pruefe


def _pruefe_f5f(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F5-f setzt die SF-Klasse ueber die moegliche Fahrpraxis."""
    zelle = _eine(aenderung)
    anfrage_id = kontext.wert(zelle.entitaet, zelle.row_id, "anfrage_id")
    alter = kontext.vn_alter_je_anfrage[anfrage_id]
    dirty = str(zelle.wert_dirty)
    assert zelle.spalte == "sf_klasse_hp"
    assert dirty.startswith("SF")
    assert int(dirty.removeprefix("SF")) > alter - FUEHRERSCHEIN_MINDESTALTER_JAHRE


def _pruefe_f5g(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F5-g setzt das E-Kennzeichen bei Benzinantrieb."""
    zelle = _eine(aenderung)
    assert zelle.spalte == "art_kennzeichen"
    assert zelle.wert_dirty == ArtKennzeichen.ELEKTRO.value
    antrieb = kontext.wert(zelle.entitaet, zelle.row_id, "antriebsart")
    assert antrieb == Antriebsart.BENZIN.value


def _pruefe_f5h(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F5-h hebt das Sublimit ueber die Versicherungssumme."""
    zelle = _eine(aenderung)
    summe = betrag_lesen(kontext.wert(zelle.entitaet, zelle.row_id, "versicherungssumme_eur"))
    dirty = betrag_lesen(str(zelle.wert_dirty))
    assert summe is not None
    assert dirty is not None
    assert zelle.spalte == "sublimit_fahrrad_eur"
    assert dirty > summe


def _pruefe_f5i(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F5-i setzt einen Ratenzuschlag bei jaehrlicher Zahlweise."""
    zelle = _eine(aenderung)
    anfrage_id = kontext.wert(zelle.entitaet, zelle.row_id, "anfrage_id")
    zuschlag = betrag_lesen(str(zelle.wert_dirty))
    assert zelle.spalte == "ratenzahlungszuschlag_prozent"
    assert zuschlag is not None
    assert zuschlag > 0
    assert kontext.zahlweise_je_anfrage[anfrage_id] == str(Zahlweise.JAEHRLICH.value)


# ---------------------------------------------------------------------------
# F6 — Duplikate
# ---------------------------------------------------------------------------


def _pruefe_duplikat(kontext: Injektionskontext, aenderung: Aenderung) -> Mapping[str, str]:
    """Gemeinsame Pruefung aller Angebotsduplikate; gibt die neue Zeile zurueck."""
    satz = aenderung.saetze[0]
    assert satz.entitaet == "angebot"
    assert not aenderung.zellen, "Ein Duplikat veraendert keine bestehende Zelle"
    werte = _neue_zeile(aenderung)
    original = kontext.zeilenwerte("angebot", satz.referenz_row_id)
    assert "row_id" not in werte, "Die neue Zeile bekommt ihre row_id von der Pipeline"
    assert werte["angebot_id"] != original["angebot_id"]
    assert werte["anfrage_id"] == original["anfrage_id"]
    assert werte["tarif_id"] == original["tarif_id"]
    return werte


def _pruefe_f6a(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F6-a dupliziert vollstaendig; nur die Kennung ist neu."""
    satz = aenderung.saetze[0]
    werte = _pruefe_duplikat(kontext, aenderung)
    original = kontext.zeilenwerte("angebot", satz.referenz_row_id)
    abweichend = {
        name for name, wert in werte.items() if name != "row_id" and original[name] != wert
    }
    assert abweichend == {"angebot_id"}


def _pruefe_f6b(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F6-b vergibt einen Rang, der eine Luecke erzeugt."""
    satz = aenderung.saetze[0]
    werte = _pruefe_duplikat(kontext, aenderung)
    raenge = [
        rang
        for row_id in kontext.angebote_je_anfrage[werte["anfrage_id"]]
        if (rang := ganzzahl_lesen(kontext.wert("angebot", row_id, "rang"))) is not None
    ]
    neuer_rang = ganzzahl_lesen(werte["rang"])
    assert neuer_rang is not None
    assert neuer_rang > max(raenge) + 1, "Zwischen bisherigem Hoechstrang und Kopie fehlt ein Rang"
    assert satz.referenz_row_id in kontext.angebote_je_anfrage[werte["anfrage_id"]]


def _pruefe_f6c(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F6-c weicht in genau einem Beitragsfeld ab."""
    satz = aenderung.saetze[0]
    werte = _pruefe_duplikat(kontext, aenderung)
    original = kontext.zeilenwerte("angebot", satz.referenz_row_id)
    abweichend = {
        name for name, wert in werte.items() if name != "row_id" and original[name] != wert
    }
    assert abweichend == {"angebot_id", "zahlbeitrag_rate_eur"}
    alt = betrag_lesen(original["zahlbeitrag_rate_eur"])
    neu = betrag_lesen(werte["zahlbeitrag_rate_eur"])
    assert alt is not None
    assert neu is not None
    assert neu - alt == Decimal("0.10")


def _pruefe_f6d(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F6-d legt einen zweiten Personensatz mit der Rolle VN an."""
    satz = aenderung.saetze[0]
    werte = _neue_zeile(aenderung)
    original = kontext.zeilenwerte("person", satz.referenz_row_id)
    assert satz.entitaet == "person"
    assert werte["rolle"] == "VN"
    assert werte["person_id"] != original["person_id"]
    assert werte["anfrage_id"] == original["anfrage_id"]


# ---------------------------------------------------------------------------
# F7 — Aktualitaet
# ---------------------------------------------------------------------------


def _pruefe_f7a(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F7-a biegt den Tarifbezug auf eine abgelaufene Generation um."""
    zelle = _eine(aenderung)
    assert zelle.spalte == "tarif_id"
    clean_index = kontext.tarif_zeile_je_id[_clean(kontext, zelle)]
    neu_index = kontext.tarif_zeile_je_id[str(zelle.wert_dirty)]
    assert clean_index != neu_index
    assert kontext.spalte("tarif", "vu_nummer")[clean_index] == kontext.spalte(
        "tarif", "vu_nummer"
    )[neu_index]
    zeitpunkt = zeitpunkt_lesen(
        kontext.wert(zelle.entitaet, zelle.row_id, "berechnungszeitpunkt")
    )
    ende = tag_lesen(kontext.spalte("tarif", "gueltig_bis")[neu_index])
    assert zeitpunkt is not None
    assert ende is not None
    assert ende < zeitpunkt.date()


def _pruefe_f7b(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F7-b datiert den Berechnungszeitpunkt um achtzehn Monate zurueck."""
    zelle = _eine(aenderung)
    clean = zeitpunkt_lesen(_clean(kontext, zelle))
    assert clean is not None
    assert zelle.spalte == "berechnungszeitpunkt"
    assert zeitpunkt_lesen(str(zelle.wert_dirty)) == monate_verschieben(clean, -18)


def _pruefe_f7c(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F7-c legt das Gueltigkeitsende vor den Beginn und meldet es satzbasiert."""
    zelle = _eine(aenderung)
    beginn = tag_lesen(kontext.wert(zelle.entitaet, zelle.row_id, "gueltig_ab"))
    ende = tag_lesen(str(zelle.wert_dirty))
    assert beginn is not None
    assert ende is not None
    assert zelle.spalte == "gueltig_bis"
    assert ende < beginn
    assert len(aenderung.befunde) == 1
    assert aenderung.befunde[0].betroffene_row_ids == (zelle.row_id,)
    assert aenderung.befunde[0].referenz_row_id is None


def _pruefe_f7d(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F7-d setzt die Generationsbezeichnung eine Stufe zurueck, den Zeitraum nicht."""
    zelle = _eine(aenderung)
    clean = _clean(kontext, zelle)
    dirty = str(zelle.wert_dirty)
    assert zelle.spalte == "tarifgeneration"
    vorher = dt.datetime(int(clean[:4]), int(clean[5:]), 1, tzinfo=dt.UTC)
    erwartet = monate_verschieben(vorher, -1)
    assert dirty == f"{erwartet.year:04d}-{erwartet.month:02d}"
    assert not any(
        andere.spalte in {"gueltig_ab", "gueltig_bis"} for andere in aenderung.zellen
    )


# ---------------------------------------------------------------------------
# F8 — Einheiten und Repraesentation
# ---------------------------------------------------------------------------


def _pruefe_f8a(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """F8-a stellt den Selbstbehalt eines Anbieters von Betrag auf Prozent um."""
    zellen = _traeger(aenderung)
    assert {zelle.spalte for zelle in zellen} == {"sb_hausrat_eur", "sb_hausrat_prozent"}
    schnittstellen = {
        kontext.wert("angebot", zelle.row_id, "quell_schnittstelle") for zelle in zellen
    }
    assert len(schnittstellen) == 1, "Die Umstellung betrifft genau einen Anbieterkanal"
    for zelle in zellen:
        if zelle.spalte == "sb_hausrat_eur":
            assert zelle.wert_dirty == ""
        else:
            assert betrag_lesen(str(zelle.wert_dirty)) is not None


def _pruefe_skalierung(faktor: Decimal, *, ganze_anfrage: bool) -> Callable[..., None]:
    """Baut eine Pruefung auf die kohaerente Skalierung des Beitragstupels."""

    def pruefe(
        kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung
    ) -> None:
        zellen = _traeger(aenderung)
        zeilen = {zelle.row_id for zelle in zellen}
        assert len(zellen) == 4 * len(zeilen), "Skaliert wird das gesamte Beitragstupel"
        for row_id in zeilen:
            werte = _je_spalte(aenderung, row_id)
            for spalte in _BEITRAGSSPALTEN:
                clean = betrag_lesen(kontext.wert("angebot", row_id, spalte))
                dirty = betrag_lesen(str(werte[spalte]))
                assert clean is not None, spalte
                assert dirty is not None, spalte
                assert abs(dirty - clean * faktor) <= _RUNDUNG, spalte

        anfrage_id = kontext.wert("angebot", next(iter(zeilen)), "anfrage_id")
        bepreist = {
            row_id
            for row_id in kontext.angebote_je_anfrage[anfrage_id]
            if ganzzahl_lesen(kontext.wert("angebot", row_id, "rang")) is not None
        }
        if ganze_anfrage:
            assert zeilen == bepreist, "F8-e trifft alle Angebote der Anfrage"
            assert not _mitgezogen(aenderung), (
                "Skaliert die ganze Anfrage gleich, bleibt die Rangfolge unveraendert"
            )
        else:
            assert len(zeilen) == 1
        for zelle in _mitgezogen(aenderung):
            assert zelle.spalte == "rang"
            assert zelle.row_id in bepreist

    return pruefe


# ---------------------------------------------------------------------------
# HO1 und HO2 — Held-out
# ---------------------------------------------------------------------------


def _pruefe_ho1a(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """HO1-a dupliziert die Person in einer Schreibvariante."""
    satz = aenderung.saetze[0]
    werte = _neue_zeile(aenderung)
    original = kontext.zeilenwerte("person", satz.referenz_row_id)
    assert satz.entitaet == "person"
    assert werte["person_id"] != original["person_id"]
    assert (werte["nachname"], werte["strasse"]) != (
        original["nachname"],
        original["strasse"],
    )
    for zeichen in ("ä", "ö", "ü", "ß"):
        assert zeichen not in werte["nachname"]
    assert "straße" not in werte["strasse"].lower()


def _pruefe_ho1b(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """HO1-b dupliziert die Person mit einem Zeichendreher im Vornamen."""
    satz = aenderung.saetze[0]
    werte = _neue_zeile(aenderung)
    original = kontext.zeilenwerte("person", satz.referenz_row_id)
    alt = original["vorname"]
    neu = werte["vorname"]
    assert satz.entitaet == "person"
    assert neu != alt
    assert sorted(neu) == sorted(alt), "Ein Zeichendreher veraendert nur die Reihenfolge"
    abweichend = [i for i in range(len(alt)) if alt[i] != neu[i]]
    assert len(abweichend) == 2
    assert abweichend[1] - abweichend[0] == 1


def _pruefe_ho2a(kontext: Injektionskontext, _kandidat: Kandidat, aenderung: Aenderung) -> None:
    """HO2-a setzt eine andere, ebenfalls existierende Anschrift."""
    zellen = _traeger(aenderung)
    werte = _je_spalte(aenderung, zellen[0].row_id)
    assert set(werte) == {"plz", "ort"}
    assert (werte["plz"], werte["ort"]) in kontext.anschriften
    assert werte["plz"] != kontext.wert("person", zellen[0].row_id, "plz")


# ---------------------------------------------------------------------------
# Zuordnung Variante auf Formpruefung
# ---------------------------------------------------------------------------

PRUEFUNGEN: Final[Mapping[str, Callable[..., None]]] = {
    "F1-a": _pruefe_f1a,
    "F1-b": _pruefe_fester_wert(""),
    "F1-c": _pruefe_fester_wert("-"),
    "F1-d": _pruefe_fester_wert("k.A."),
    "F1-e": _pruefe_f1e,
    "F1-f": _pruefe_f1f,
    "F2-a": _pruefe_f2a,
    "F2-b": _pruefe_f2b,
    "F2-c": _pruefe_f2c,
    "F2-d": _pruefe_f2d,
    "F2-e": _pruefe_f2e,
    "F2-f": _pruefe_f2f,
    "F2-g": _pruefe_f2g,
    "F2-h": _pruefe_f2h,
    "F2-i": _pruefe_f2i,
    "F2-j": _pruefe_f2j,
    "F2-k": _pruefe_f2k,
    "F2-l": _pruefe_f2l,
    "F3-a": _pruefe_typklasse("99"),
    "F3-b": _pruefe_typklasse("9"),
    "F3-c": _pruefe_f3c,
    "F3-d": _pruefe_zahlweise("3"),
    "F3-e": _pruefe_zahlweise("7"),
    "F3-f": _pruefe_f3f,
    "F3-g": _pruefe_f3g,
    "F3-h": _pruefe_f3h,
    "F3-i": _pruefe_f3i,
    "F4-a": _pruefe_f4a,
    "F4-b": _pruefe_f4b,
    "F4-c": _pruefe_wohnflaeche("5000"),
    "F4-d": _pruefe_wohnflaeche("8"),
    "F4-e": _pruefe_f4e,
    "F4-f": _pruefe_f4f,
    "F4-g": _pruefe_f4g,
    "F5-a": _pruefe_f5a,
    "F5-b": _pruefe_f5b,
    "F5-c": _pruefe_f5c,
    "F5-d": _pruefe_senkung(Decimal("0.50")),
    "F5-e": _pruefe_senkung(Decimal("0.01")),
    "F5-f": _pruefe_f5f,
    "F5-g": _pruefe_f5g,
    "F5-h": _pruefe_f5h,
    "F5-i": _pruefe_f5i,
    "F6-a": _pruefe_f6a,
    "F6-b": _pruefe_f6b,
    "F6-c": _pruefe_f6c,
    "F6-d": _pruefe_f6d,
    "F7-a": _pruefe_f7a,
    "F7-b": _pruefe_f7b,
    "F7-c": _pruefe_f7c,
    "F7-d": _pruefe_f7d,
    "F8-a": _pruefe_f8a,
    "F8-b": _pruefe_skalierung(Decimal(100), ganze_anfrage=False),
    "F8-c": _pruefe_skalierung(Decimal(1) / Decimal(100), ganze_anfrage=False),
    "F8-d": _pruefe_skalierung(Decimal(1) / Decimal(12), ganze_anfrage=False),
    "F8-e": _pruefe_skalierung(Decimal(1) / Decimal(12), ganze_anfrage=True),
    "HO1-a": _pruefe_ho1a,
    "HO1-b": _pruefe_ho1b,
    "HO2-a": _pruefe_ho2a,
    "HO2-b": _pruefe_skalierung(Decimal("0.85"), ganze_anfrage=False),
}


def test_jede_variante_hat_eine_pruefung() -> None:
    """Keine der sechzig Varianten bleibt ohne Formpruefung."""
    ohne = sorted(
        eintrag.variante_id for eintrag in ALLE_VARIANTEN if eintrag.variante_id not in PRUEFUNGEN
    )
    assert not ohne, f"Ohne Formpruefung: {ohne}"
    unbekannt = sorted(
        set(PRUEFUNGEN) - {eintrag.variante_id for eintrag in ALLE_VARIANTEN}
    )
    assert not unbekannt, f"Pruefung ohne Variante: {unbekannt}"


@pytest.mark.parametrize(
    "variante_id", [eintrag.variante_id for eintrag in ALLE_VARIANTEN], ids=str
)
def test_variante_hat_die_beabsichtigte_form(
    kontext: Injektionskontext, variante_id: str
) -> None:
    """Die Verfaelschung hat genau die in ``spec/03`` beschriebene Form."""
    eintrag = variante(variante_id)
    kandidat, aenderung = _anwenden(kontext, eintrag)
    PRUEFUNGEN[variante_id](kontext, kandidat, aenderung)


@pytest.mark.parametrize(
    "variante_id", [eintrag.variante_id for eintrag in ALLE_VARIANTEN], ids=str
)
def test_variante_veraendert_wirklich(
    kontext: Injektionskontext, variante_id: str
) -> None:
    """Jede Traegerzelle unterscheidet sich vom sauberen Wert (Protokollregel 3)."""
    eintrag = variante(variante_id)
    _, aenderung = _anwenden(kontext, eintrag)
    for zelle in _traeger(aenderung):
        clean = _clean(kontext, zelle)
        neu = "" if zelle.wert_dirty is None else zelle.wert_dirty
        assert clean != neu, f"{zelle.entitaet}.{zelle.spalte} bliebe unveraendert"


@pytest.mark.parametrize(
    "variante_id", [eintrag.variante_id for eintrag in ALLE_VARIANTEN], ids=str
)
def test_variante_trifft_niemals_row_id(
    kontext: Injektionskontext, variante_id: str
) -> None:
    """Keine Variante fasst ``row_id`` an (Architekturregel A3)."""
    eintrag = variante(variante_id)
    _, aenderung = _anwenden(kontext, eintrag)
    assert all(zelle.spalte != "row_id" for zelle in aenderung.zellen)
    assert all("row_id" not in satz.werte for satz in aenderung.saetze)
