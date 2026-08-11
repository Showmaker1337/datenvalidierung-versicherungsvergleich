"""F4 — fachlich unmoeglicher, syntaktisch valider Wert (``spec/03``, Abschnitt 2).

Empirische Ursachen:

* **Zahlendreher und Einheitenverwechslung** bei der Erfassung: Aus 50 m²
  Wohnflaeche werden 5.000, aus 80 m² werden 8 (F4-c, F4-d).
* **Vertauschte Datumsstellen** oder ein aus einem Planungssystem uebernommenes
  Wunschdatum, das in der Zukunft liegt (F4-a, F4-b).
* **Verwechslung zweier Betragsfelder**: Der Wiederbeschaffungswert wird mit
  einem Listenpreis inklusive Ausstattung belegt (F4-e).
* **Vorzeichenfehler** aus einer Storno- oder Gutschriftverarbeitung, in der
  Betraege negativ gefuehrt werden (F4-g).

Jeder dieser Werte ist syntaktisch einwandfrei. Er passt in den Feldtyp, laesst
sich parsen und faellt in keiner Formatpruefung auf — nur die Fachlichkeit
verbietet ihn. Genau darin liegt die Schwierigkeit dieser Klasse.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Final

from src.common.datum import datum_plus_jahre
from src.injector.modell import Fehlerklasse, Variante, Zielart
from src.injector.rohwerte import betrag_lesen, betrag_schreiben, ganzzahl_schreiben, tag_schreiben
from src.injector.varianten.bausteine import einzelne_zelle, kandidaten_aus_feldern

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    from numpy.random import Generator

    from src.injector.modell import Aenderung, AnwendungsFunktion, Injektionskontext, Kandidat

__all__ = ["VARIANTEN"]

#: Jahre, um die die Erstzulassung in die Zukunft verschoben wird (Variante F4-a).
_ERSTZULASSUNG_VORAUS_JAHRE: Final[int] = 2
#: Jahre, um die das Baujahr in die Zukunft verschoben wird (Variante F4-b).
_BAUJAHR_VORAUS_JAHRE: Final[int] = 5
#: Wohnflaeche eines Zahlendrehers (Variante F4-c).
_WOHNFLAECHE_ZU_GROSS: Final[int] = 5000
#: Wohnflaeche knapp unterhalb der Plausibilitaetsschwelle (Variante F4-d).
_WOHNFLAECHE_ZU_KLEIN: Final[int] = 8
#: Vielfaches des Neupreises, auf das der Fahrzeugwert gesetzt wird (Variante F4-e).
_FAHRZEUGWERT_FAKTOR: Final[Decimal] = Decimal(3)
#: Deckungssumme unterhalb des gesetzlichen Mindestbetrags (Variante F4-f).
_DECKUNGSSUMME_ZU_NIEDRIG: Final[Decimal] = Decimal("5000000.00")

#: Felder, in denen ein Vorzeichenfehler auftreten kann (Variante F4-g).
#:
#: ``spec/03``, Abschnitt 2 nennt "Beitrag oder Versicherungssumme". Als Beitrag
#: wird der **Nettobeitrag** genommen: Er ist die Ausgangsgroesse der
#: Beitragsrechnung und damit das Feld, das eine Storno- oder
#: Gutschriftverarbeitung negativ fuehrt.
_NEGIERBARE_FELDER: Final[tuple[tuple[str, str], ...]] = (
    ("risiko_hausrat", "versicherungssumme_eur"),
    ("tarif", "deckungssumme_personen_eur"),
    ("tarif", "deckungssumme_sach_eur"),
    ("tarif", "deckungssumme_vermoegen_eur"),
    ("angebot", "nettobeitrag_jahr_eur"),
)


def _kandidaten_erstzulassung(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Alle gefuellten Erstzulassungsdaten."""
    return kandidaten_aus_feldern(kontext, (("risiko_kfz", "erstzulassung"),))


def _kandidaten_baujahr(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Alle gefuellten Baujahre."""
    return kandidaten_aus_feldern(kontext, (("risiko_hausrat", "baujahr"),))


def _kandidaten_wohnflaeche(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Alle gefuellten Wohnflaechen."""
    return kandidaten_aus_feldern(kontext, (("risiko_hausrat", "wohnflaeche_qm"),))


def _kandidaten_fahrzeugwert(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Fahrzeugwerte, zu denen auch ein Neupreis vorliegt."""
    return kandidaten_aus_feldern(
        kontext,
        (("risiko_kfz", "fahrzeugwert_aktuell"),),
        zeilenbedingung=_hat_neupreis,
    )


def _hat_neupreis(kontext: Injektionskontext, entitaet: str, row_id: int) -> bool:
    """Trifft zu, wenn die Kfz-Zeile einen lesbaren Neupreis traegt."""
    return betrag_lesen(kontext.wert(entitaet, row_id, "neupreis_eur")) is not None


def _kandidaten_deckungssumme(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Alle gefuellten Personendeckungssummen."""
    return kandidaten_aus_feldern(kontext, (("tarif", "deckungssumme_personen_eur"),))


def _kandidaten_negierbar(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Alle positiven Betragsfelder, in denen ein Vorzeichenfehler auftreten kann."""
    return kandidaten_aus_feldern(kontext, _NEGIERBARE_FELDER, wertbedingung=_ist_positiv)


def _ist_positiv(wert: str) -> bool:
    """Trifft auf lesbare, positive Geldbetraege zu."""
    betrag = betrag_lesen(wert)
    return betrag is not None and betrag > 0


def _fester_text(wert: str) -> AnwendungsFunktion:
    """Baut eine Anwendungsfunktion, die immer denselben Rohwert schreibt.

    Args:
        wert: Zu schreibender Rohwert.

    Returns:
        Die Anwendungsfunktion der Variante.
    """

    def anwenden(
        _kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
    ) -> Aenderung | None:
        return einzelne_zelle(kandidat, wert)

    return anwenden


def _erstzulassung_in_der_zukunft(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F4-a: Erstzulassung zwei Jahre nach dem Stichtag."""
    ziel = datum_plus_jahre(kontext.config.stichtag, _ERSTZULASSUNG_VORAUS_JAHRE)
    return einzelne_zelle(kandidat, tag_schreiben(ziel))


def _baujahr_in_der_zukunft(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F4-b: Baujahr fuenf Jahre nach dem Stichtag."""
    return einzelne_zelle(
        kandidat, ganzzahl_schreiben(kontext.config.stichtag.year + _BAUJAHR_VORAUS_JAHRE)
    )


def _fahrzeugwert_ueber_neupreis(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F4-e: Fahrzeugwert auf das Dreifache des Neupreises."""
    neupreis = betrag_lesen(kontext.wert(kandidat.entitaet, kandidat.row_id, "neupreis_eur"))
    if neupreis is None:
        return None
    return einzelne_zelle(kandidat, betrag_schreiben(neupreis * _FAHRZEUGWERT_FAKTOR))


def _vorzeichen_gedreht(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F4-g: Beitrag oder Versicherungssumme negativ."""
    if kandidat.spalte is None:
        return None
    betrag = betrag_lesen(kontext.wert(kandidat.entitaet, kandidat.row_id, kandidat.spalte))
    if betrag is None:
        return None
    return einzelne_zelle(kandidat, betrag_schreiben(-betrag))


VARIANTEN: Sequence[Variante] = (
    Variante(
        variante_id="F4-a",
        fehlerklasse=Fehlerklasse.F4,
        zielart=Zielart.ZELLE,
        beschreibung="Erstzulassung zwei Jahre nach dem Stichtag",
        ursache="Vertauschte Datumsstellen oder uebernommenes Wunschdatum aus der Planung",
        kandidaten=_kandidaten_erstzulassung,
        anwenden=_erstzulassung_in_der_zukunft,
    ),
    Variante(
        variante_id="F4-b",
        fehlerklasse=Fehlerklasse.F4,
        zielart=Zielart.ZELLE,
        beschreibung="Baujahr fuenf Jahre nach dem Stichtag",
        ursache="Geplantes Fertigstellungsjahr statt des tatsaechlichen Baujahrs erfasst",
        kandidaten=_kandidaten_baujahr,
        anwenden=_baujahr_in_der_zukunft,
    ),
    Variante(
        variante_id="F4-c",
        fehlerklasse=Fehlerklasse.F4,
        zielart=Zielart.ZELLE,
        beschreibung="Wohnflaeche auf 5.000 Quadratmeter",
        ursache="Zahlendreher oder Grundstuecks- statt Wohnflaeche erfasst",
        kandidaten=_kandidaten_wohnflaeche,
        anwenden=_fester_text(ganzzahl_schreiben(_WOHNFLAECHE_ZU_GROSS)),
    ),
    Variante(
        variante_id="F4-d",
        fehlerklasse=Fehlerklasse.F4,
        zielart=Zielart.ZELLE,
        beschreibung="Wohnflaeche auf 8 Quadratmeter",
        ursache="Abgeschnittene Eingabe; nur die erste Ziffer kam an",
        kandidaten=_kandidaten_wohnflaeche,
        anwenden=_fester_text(ganzzahl_schreiben(_WOHNFLAECHE_ZU_KLEIN)),
    ),
    Variante(
        variante_id="F4-e",
        fehlerklasse=Fehlerklasse.F4,
        zielart=Zielart.ZELLE,
        beschreibung="Fahrzeugwert auf das Dreifache des Neupreises",
        ursache="Verwechslung zweier Betragsfelder, etwa Listenpreis mit Ausstattung",
        kandidaten=_kandidaten_fahrzeugwert,
        anwenden=_fahrzeugwert_ueber_neupreis,
    ),
    Variante(
        variante_id="F4-f",
        fehlerklasse=Fehlerklasse.F4,
        zielart=Zielart.ZELLE,
        beschreibung="Deckungssumme Personen auf 5.000.000 Euro",
        ursache="Veraltete Mindestdeckung aus einer aelteren Tarifgeneration uebernommen",
        kandidaten=_kandidaten_deckungssumme,
        anwenden=_fester_text(betrag_schreiben(_DECKUNGSSUMME_ZU_NIEDRIG)),
    ),
    Variante(
        variante_id="F4-g",
        fehlerklasse=Fehlerklasse.F4,
        zielart=Zielart.ZELLE,
        beschreibung="Beitrag oder Versicherungssumme negativ",
        ursache="Vorzeichenfehler aus einer Storno- oder Gutschriftverarbeitung",
        kandidaten=_kandidaten_negierbar,
        anwenden=_vorzeichen_gedreht,
    ),
)
