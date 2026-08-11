"""F5 — Intra-Record-Inkonsistenz einschliesslich Beitragsarithmetik.

Empirische Ursachen:

* **Feldvertauschung** in einer Zuordnungstabelle: Brutto und Netto landen im
  jeweils anderen Feld (F5-a).
* **Falsch parametrierte Steuerrechnung**: Der Kfz-Satz wird auf einen
  Hausratvertrag angewandt, oder der Satz einer anderen Sparte wird uebernommen
  (F5-b, F5-c).
* **Rundungs- und Uebertragungsfehler** in der Beitragsermittlung (F5-d, F5-e).
* **Uebernommene Altangaben**, die zum Rest des Satzes nicht mehr passen: eine
  Schadenfreiheitsklasse aus einem Vorvertrag (F5-f), ein Kennzeichen aus einem
  Fahrzeugwechsel (F5-g).
* **Nicht nachgezogene Abhaengigkeiten** nach einer Aenderung: ein Sublimit
  bleibt stehen, obwohl die Versicherungssumme gesenkt wurde (F5-h); ein
  Ratenzuschlag bleibt stehen, obwohl auf jaehrliche Zahlweise gewechselt wurde
  (F5-i).

F5-d und F5-e sind **Senkungen**, nicht Erhoehungen
---------------------------------------------------

``spec/03``, Abschnitt 2 laesst die Richtung offen ("um 0,50 Euro / 0,01 Euro
veraendern"). Umgesetzt ist beides als **Verringerung** des Bruttobeitrags. Der
Grund liegt in der Ratenpruefung: Bei jaehrlicher Zahlweise ist die Ratenanzahl
eins und der Ratenzuschlag null, auf sauberen Daten gilt dort also
``Rate = Brutto`` — die Ungleichung "Rate mal Ratenanzahl mindestens Brutto
abzueglich einer Toleranz je Rate" ist exakt ausgeschoepft.

* Eine **Erhoehung** um 0,50 Euro verletzt dort zusaetzlich die Ratenpruefung.
  F5-d wuerde von zwei Regeln gemeldet, und die Zuordnung Variante auf Regel in
  der Ergebnistabelle waere falsch.
* Eine **Erhoehung** um 0,01 Euro landet bei jaehrlicher Zahlweise exakt auf der
  Grenze. Sie besteht die Pruefung zwar, aber eine als unentdeckt erwartete
  Variante darf nicht auf einer Grenzgleichheit balancieren.
* Eine **Senkung** ist in beiden Faellen eindeutig: Die Ratenpruefung bekommt
  zusaetzlichen Spielraum, ueber die Variante entscheidet allein die
  Beitragsarithmetik.

Als Fehlerbild ist die Senkung ebenso realistisch wie die Erhoehung — ein
Rundungs- oder Uebertragungsfehler kennt keine Vorzugsrichtung. Die
Praezisierung ist in ``spec/03`` nachgetragen.

F5-e soll **nicht** erkannt werden. Sie prueft, ob die Toleranzgrenze korrekt
implementiert ist, und liefert einen erklaerbaren False Negative — ein Befund,
kein Fehler.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Final

from src.common.enums import SF_MAX_NUMERISCH, Antriebsart, ArtKennzeichen, Sparte, Zahlweise
from src.common.wertebereiche import (
    FUEHRERSCHEIN_MINDESTALTER_JAHRE,
    VERSICHERUNGSTEUER_EFFEKTIVSATZ,
    VERSICHERUNGSTEUER_NOMINALSATZ,
)
from src.injector.modell import Aenderung, Fehlerklasse, Variante, Zellaenderung, Zielart
from src.injector.rohwerte import betrag_lesen, betrag_schreiben
from src.injector.varianten.bausteine import einzelne_zelle, kandidaten_aus_feldern

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    from numpy.random import Generator

    from src.injector.modell import AnwendungsFunktion, Injektionskontext, Kandidat

__all__ = ["VARIANTEN"]

#: Hundert Prozent — Nenner der Steuerrechnung.
_PROZENT: Final[Decimal] = Decimal(100)
#: Effektivsatz der Versicherungsteuer fuer Hausrat.
_SATZ_HAUSRAT: Final[Decimal] = VERSICHERUNGSTEUER_EFFEKTIVSATZ[Sparte.HAUSRAT]
#: Betrag, um den der Bruttobeitrag oberhalb der Toleranz gesenkt wird (Variante F5-d).
_ABWEICHUNG_GROB: Final[Decimal] = Decimal("0.50")
#: Betrag, um den der Bruttobeitrag innerhalb der Toleranz gesenkt wird (Variante F5-e).
_ABWEICHUNG_FEIN: Final[Decimal] = Decimal("0.01")
#: Stufen, um die die Schadenfreiheitsklasse ueber das moegliche Mass steigt (Variante F5-f).
_SF_UEBERSCHUSS: Final[int] = 1
#: Faktor, mit dem ein Sublimit ueber die Versicherungssumme gehoben wird (Variante F5-h).
_SUBLIMIT_FAKTOR: Final[Decimal] = Decimal("1.5")
#: Ratenzuschlag, der bei jaehrlicher Zahlweise nicht vorkommen kann (Variante F5-i).
_RATENZUSCHLAG: Final[Decimal] = Decimal("3.50")


# ---------------------------------------------------------------------------
# Beitragsarithmetik
# ---------------------------------------------------------------------------


def _kandidaten_brutto(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Bepreiste Angebote mit lesbarem Brutto- und Nettobeitrag."""
    return kandidaten_aus_feldern(
        kontext,
        (("angebot", "bruttobeitrag_jahr_eur"),),
        zeilenbedingung=_hat_beitragspaar,
    )


def _hat_beitragspaar(kontext: Injektionskontext, entitaet: str, row_id: int) -> bool:
    """Trifft zu, wenn Brutto und Netto lesbar und verschieden sind."""
    brutto = betrag_lesen(kontext.wert(entitaet, row_id, "bruttobeitrag_jahr_eur"))
    netto = betrag_lesen(kontext.wert(entitaet, row_id, "nettobeitrag_jahr_eur"))
    return brutto is not None and netto is not None and brutto != netto


def _brutto_netto_vertauscht(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F5-a: Brutto und Netto stehen im jeweils anderen Feld."""
    brutto = kontext.wert(kandidat.entitaet, kandidat.row_id, "bruttobeitrag_jahr_eur")
    netto = kontext.wert(kandidat.entitaet, kandidat.row_id, "nettobeitrag_jahr_eur")
    return Aenderung(
        zellen=(
            Zellaenderung(kandidat.entitaet, kandidat.row_id, "bruttobeitrag_jahr_eur", netto),
            Zellaenderung(kandidat.entitaet, kandidat.row_id, "nettobeitrag_jahr_eur", brutto),
        )
    )


def _brutto_gesenkt(abweichung: Decimal) -> AnwendungsFunktion:
    """Baut eine Anwendungsfunktion, die den Bruttobeitrag um einen festen Betrag senkt.

    Args:
        abweichung: Betrag, um den gesenkt wird.

    Returns:
        Die Anwendungsfunktion der Variante.
    """

    def anwenden(
        kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
    ) -> Aenderung | None:
        if kandidat.spalte is None:
            return None
        brutto = betrag_lesen(kontext.wert(kandidat.entitaet, kandidat.row_id, kandidat.spalte))
        if brutto is None:
            return None
        return einzelne_zelle(kandidat, betrag_schreiben(brutto - abweichung))

    return anwenden


# ---------------------------------------------------------------------------
# Versicherungsteuer
# ---------------------------------------------------------------------------


def _kandidaten_steuerbetrag(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Angebote, deren Steuersatz nicht der Nominalsatz ist — im Modell die Hausratzeilen."""
    return kandidaten_aus_feldern(
        kontext,
        (("angebot", "versicherungsteuer_eur"),),
        zeilenbedingung=_traegt_ermaessigten_satz,
    )


def _traegt_ermaessigten_satz(kontext: Injektionskontext, entitaet: str, row_id: int) -> bool:
    """Trifft zu, wenn Steuersatz und Nettobeitrag lesbar sind und der Satz ermaessigt ist."""
    satz = betrag_lesen(kontext.wert(entitaet, row_id, "versicherungsteuer_satz"))
    netto = betrag_lesen(kontext.wert(entitaet, row_id, "nettobeitrag_jahr_eur"))
    return satz is not None and netto is not None and satz != VERSICHERUNGSTEUER_NOMINALSATZ


def _steuer_mit_nominalsatz(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F5-b: Der Steuerbetrag ist mit dem vollen Nominalsatz gerechnet."""
    netto = betrag_lesen(kontext.wert(kandidat.entitaet, kandidat.row_id, "nettobeitrag_jahr_eur"))
    if netto is None:
        return None
    return einzelne_zelle(
        kandidat, betrag_schreiben(netto * VERSICHERUNGSTEUER_NOMINALSATZ / _PROZENT)
    )


def _kandidaten_steuersatz(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Angebote mit lesbarem Steuersatz."""
    return kandidaten_aus_feldern(
        kontext, (("angebot", "versicherungsteuer_satz"),), wertbedingung=_ist_bekannter_satz
    )


def _ist_bekannter_satz(wert: str) -> bool:
    """Trifft auf die beiden im Modell vorkommenden Effektivsaetze zu."""
    satz = betrag_lesen(wert)
    return satz in {VERSICHERUNGSTEUER_NOMINALSATZ, _SATZ_HAUSRAT}


def _steuersatz_der_falschen_sparte(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F5-c: Der Steuersatz stammt aus der jeweils anderen Sparte."""
    if kandidat.spalte is None:
        return None
    satz = betrag_lesen(kontext.wert(kandidat.entitaet, kandidat.row_id, kandidat.spalte))
    if satz is None:
        return None
    ist_nominal = satz == VERSICHERUNGSTEUER_NOMINALSATZ
    anderer = _SATZ_HAUSRAT if ist_nominal else VERSICHERUNGSTEUER_NOMINALSATZ
    return einzelne_zelle(kandidat, betrag_schreiben(anderer))


# ---------------------------------------------------------------------------
# Risikoangaben
# ---------------------------------------------------------------------------


def _kandidaten_sf_klasse(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Kfz-Zeilen, in denen sich eine zu hohe Schadenfreiheitsklasse bilden laesst."""
    return kandidaten_aus_feldern(
        kontext, (("risiko_kfz", "sf_klasse_hp"),), zeilenbedingung=_sf_ueberhoehbar
    )


def _hoechste_sf_klasse(kontext: Injektionskontext, entitaet: str, row_id: int) -> str | None:
    """Bestimmt die Klasse, die knapp ueber der Fahrpraxis des Versicherungsnehmers liegt."""
    anfrage_id = kontext.wert(entitaet, row_id, "anfrage_id")
    alter = kontext.vn_alter_je_anfrage.get(anfrage_id)
    if alter is None:
        return None
    stufe = alter - FUEHRERSCHEIN_MINDESTALTER_JAHRE + _SF_UEBERSCHUSS
    if not 1 <= stufe <= SF_MAX_NUMERISCH:
        return None
    return f"SF{stufe}"


def _sf_ueberhoehbar(kontext: Injektionskontext, entitaet: str, row_id: int) -> bool:
    """Trifft zu, wenn eine solche Klasse existiert und von der bisherigen abweicht."""
    klasse = _hoechste_sf_klasse(kontext, entitaet, row_id)
    return klasse is not None and klasse != kontext.wert(entitaet, row_id, "sf_klasse_hp")


def _sf_klasse_zu_hoch(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F5-f: Die Schadenfreiheitsklasse uebersteigt die moegliche Fahrpraxis."""
    klasse = _hoechste_sf_klasse(kontext, kandidat.entitaet, kandidat.row_id)
    if klasse is None:
        return None
    return einzelne_zelle(kandidat, klasse)


def _kandidaten_kennzeichen(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Kfz-Zeilen mit Verbrennerantrieb und ohne E-Kennzeichen."""
    return kandidaten_aus_feldern(
        kontext, (("risiko_kfz", "art_kennzeichen"),), zeilenbedingung=_faehrt_benzin
    )


def _faehrt_benzin(kontext: Injektionskontext, entitaet: str, row_id: int) -> bool:
    """Trifft auf Fahrzeuge mit Benzinantrieb zu."""
    return kontext.wert(entitaet, row_id, "antriebsart") == Antriebsart.BENZIN.value


def _e_kennzeichen_ohne_elektroantrieb(
    _kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F5-g: E-Kennzeichen bei Benzinantrieb."""
    return einzelne_zelle(kandidat, ArtKennzeichen.ELEKTRO.value)


def _kandidaten_sublimit(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Gefuellte Fahrradsublimits, zu denen eine Versicherungssumme vorliegt."""
    return kandidaten_aus_feldern(
        kontext,
        (("risiko_hausrat", "sublimit_fahrrad_eur"),),
        zeilenbedingung=_hat_versicherungssumme,
    )


def _hat_versicherungssumme(kontext: Injektionskontext, entitaet: str, row_id: int) -> bool:
    """Trifft zu, wenn die Hausratzeile eine lesbare Versicherungssumme traegt."""
    return betrag_lesen(kontext.wert(entitaet, row_id, "versicherungssumme_eur")) is not None


def _sublimit_ueber_versicherungssumme(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F5-h: Das Sublimit liegt ueber der Versicherungssumme."""
    summe = betrag_lesen(
        kontext.wert(kandidat.entitaet, kandidat.row_id, "versicherungssumme_eur")
    )
    if summe is None:
        return None
    return einzelne_zelle(kandidat, betrag_schreiben(summe * _SUBLIMIT_FAKTOR))


def _kandidaten_ratenzuschlag(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Angebote zu Anfragen mit jaehrlicher Zahlweise."""
    return kandidaten_aus_feldern(
        kontext,
        (("angebot", "ratenzahlungszuschlag_prozent"),),
        zeilenbedingung=_zahlt_jaehrlich,
    )


def _zahlt_jaehrlich(kontext: Injektionskontext, entitaet: str, row_id: int) -> bool:
    """Trifft zu, wenn die Anfrage jaehrliche Zahlweise hat."""
    anfrage_id = kontext.wert(entitaet, row_id, "anfrage_id")
    zahlweise = kontext.zahlweise_je_anfrage.get(anfrage_id)
    return zahlweise == str(Zahlweise.JAEHRLICH.value)


def _ratenzuschlag_ohne_raten(
    _kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F5-i: Ratenzuschlag groesser null bei jaehrlicher Zahlweise."""
    return einzelne_zelle(kandidat, betrag_schreiben(_RATENZUSCHLAG))


VARIANTEN: Sequence[Variante] = (
    Variante(
        variante_id="F5-a",
        fehlerklasse=Fehlerklasse.F5,
        zielart=Zielart.ZELLE,
        beschreibung="Brutto- und Nettobeitrag vertauscht",
        ursache="Feldvertauschung in einer Zuordnungstabelle beim Import",
        kandidaten=_kandidaten_brutto,
        anwenden=_brutto_netto_vertauscht,
        zusatzspalten=("nettobeitrag_jahr_eur",),
    ),
    Variante(
        variante_id="F5-b",
        fehlerklasse=Fehlerklasse.F5,
        zielart=Zielart.ZELLE,
        beschreibung="Steuerbetrag mit dem vollen Nominalsatz statt dem Effektivsatz gerechnet",
        ursache="Steuerrechnung ohne spartenabhaengige Bemessungsgrundlage parametriert",
        kandidaten=_kandidaten_steuerbetrag,
        anwenden=_steuer_mit_nominalsatz,
    ),
    Variante(
        variante_id="F5-c",
        fehlerklasse=Fehlerklasse.F5,
        zielart=Zielart.ZELLE,
        beschreibung="Steuersatz der jeweils anderen Sparte eingetragen",
        ursache="Satz aus einer Nachbarsparte uebernommen",
        kandidaten=_kandidaten_steuersatz,
        anwenden=_steuersatz_der_falschen_sparte,
    ),
    Variante(
        variante_id="F5-d",
        fehlerklasse=Fehlerklasse.F5,
        zielart=Zielart.ZELLE,
        beschreibung="Bruttobeitrag um 0,50 Euro gesenkt — oberhalb der Toleranz",
        ursache="Uebertragungsfehler in der Beitragsermittlung",
        kandidaten=_kandidaten_brutto,
        anwenden=_brutto_gesenkt(_ABWEICHUNG_GROB),
    ),
    Variante(
        variante_id="F5-e",
        fehlerklasse=Fehlerklasse.F5,
        zielart=Zielart.ZELLE,
        beschreibung="Bruttobeitrag um 0,01 Euro gesenkt — innerhalb der Toleranz",
        ursache="Rundungsdifferenz zwischen zwei Rechenwegen",
        kandidaten=_kandidaten_brutto,
        anwenden=_brutto_gesenkt(_ABWEICHUNG_FEIN),
    ),
    Variante(
        variante_id="F5-f",
        fehlerklasse=Fehlerklasse.F5,
        zielart=Zielart.ZELLE,
        beschreibung="Schadenfreiheitsklasse ueber der moeglichen Fahrpraxis",
        ursache="Einstufung aus einem Vorvertrag uebernommen, ohne sie zu pruefen",
        kandidaten=_kandidaten_sf_klasse,
        anwenden=_sf_klasse_zu_hoch,
    ),
    Variante(
        variante_id="F5-g",
        fehlerklasse=Fehlerklasse.F5,
        zielart=Zielart.ZELLE,
        beschreibung="E-Kennzeichen bei Benzinantrieb",
        ursache="Kennzeichenangabe aus einem Fahrzeugwechsel nicht nachgezogen",
        kandidaten=_kandidaten_kennzeichen,
        anwenden=_e_kennzeichen_ohne_elektroantrieb,
    ),
    Variante(
        variante_id="F5-h",
        fehlerklasse=Fehlerklasse.F5,
        zielart=Zielart.ZELLE,
        beschreibung="Sublimit ueber die Versicherungssumme gehoben",
        ursache="Versicherungssumme gesenkt, das Sublimit blieb stehen",
        kandidaten=_kandidaten_sublimit,
        anwenden=_sublimit_ueber_versicherungssumme,
    ),
    Variante(
        variante_id="F5-i",
        fehlerklasse=Fehlerklasse.F5,
        zielart=Zielart.ZELLE,
        beschreibung="Ratenzuschlag groesser null bei jaehrlicher Zahlweise",
        ursache="Wechsel auf jaehrliche Zahlweise ohne Nachfuehren des Zuschlags",
        kandidaten=_kandidaten_ratenzuschlag,
        anwenden=_ratenzuschlag_ohne_raten,
    ),
)
