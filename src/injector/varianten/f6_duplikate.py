"""F6 — exaktes Duplikat mit Konfliktwerten (``spec/03``, Abschnitt 2).

Empirische Ursachen: Ein Lieferpaket wird zweimal eingespielt, ein Nutzer
schickt ein Formular doppelt ab, ein Wiederholungslauf nach einem Abbruch
verarbeitet bereits uebernommene Saetze erneut. Beim zweiten Durchlauf steht der
Preis manchmal minimal anders da — daraus entsteht das Konfliktduplikat (F6-c).

Diese Klasse **fuegt Zeilen hinzu**. Das zellbasierte Ground-Truth-Schema greift
hier nicht: Eine hinzugefuegte Zeile hat keinen sauberen Vorgaengerwert, und ein
zellweises Diff ist dort undefiniert. Protokolliert wird deshalb ausschliesslich
satzbasiert (``spec/03``, Abschnitt 4.2).

Die Kopie bekommt eine **frische** ``row_id``
---------------------------------------------

Die Originalzeile bleibt unveraendert, ihre ``row_id`` wandert als
``referenz_row_id`` ins Log. Das ist keine Formalie: Der Diff-Gegencheck joint
``df_clean`` und ``df_dirty`` ueber ``row_id``; eine wiederverwendete Kennung
liesse den Join aufblaehen und den Check wertlos werden.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Final

from src.common.enums import Rolle
from src.injector.modell import Aenderung, Fehlerklasse, Satzaenderung, Variante, Zielart
from src.injector.rohwerte import betrag_lesen, betrag_schreiben, ganzzahl_lesen, ganzzahl_schreiben
from src.injector.varianten.bausteine import kopiere_zeile, neue_uuid, satz_kandidaten

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    from numpy.random import Generator

    from src.injector.modell import Injektionskontext, Kandidat

__all__ = ["VARIANTEN"]

#: Abstand, mit dem der Rang der Kopie eine Luecke in der Rangfolge erzeugt (Variante F6-b).
_RANGLUECKE: Final[int] = 2
#: Betrag, um den sich das Konfliktduplikat im Zahlbeitrag unterscheidet (Variante F6-c).
_KONFLIKTBETRAG: Final[Decimal] = Decimal("0.10")


def _kandidaten_angebot(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Bepreiste Angebotszeilen — nur sie tragen einen Rang."""
    return satz_kandidaten(kontext, "angebot", zeilenbedingung=_ist_bepreist)


def _ist_bepreist(kontext: Injektionskontext, entitaet: str, row_id: int) -> bool:
    """Trifft auf Angebote mit gesetztem Rang zu."""
    return ganzzahl_lesen(kontext.wert(entitaet, row_id, "rang")) is not None


def _kandidaten_person(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Alle Personensaetze."""
    return satz_kandidaten(kontext, "person")


def _kopie_angebot(
    kontext: Injektionskontext, kandidat: Kandidat, rng: Generator
) -> dict[str, str]:
    """Kopiert eine Angebotszeile und vergibt eine neue Angebotskennung."""
    werte = kopiere_zeile(kontext, kandidat.entitaet, kandidat.row_id)
    werte["angebot_id"] = neue_uuid(rng)
    return werte


def _satz(kandidat: Kandidat, werte: dict[str, str]) -> Aenderung:
    """Verpackt eine kopierte Zeile als Aenderung."""
    return Aenderung(
        saetze=(
            Satzaenderung(
                entitaet=kandidat.entitaet, referenz_row_id=kandidat.row_id, werte=werte
            ),
        )
    )


def _duplikat_gleicher_rang(
    kontext: Injektionskontext, kandidat: Kandidat, rng: Generator
) -> Aenderung | None:
    """F6-a: Vollstaendiges Duplikat mit neuer Kennung und unveraendertem Rang."""
    return _satz(kandidat, _kopie_angebot(kontext, kandidat, rng))


def _duplikat_mit_rangluecke(
    kontext: Injektionskontext, kandidat: Kandidat, rng: Generator
) -> Aenderung | None:
    """F6-b: Duplikat mit neu vergebenem Rang; die Rangfolge bekommt eine Luecke."""
    anfrage_id = kontext.wert(kandidat.entitaet, kandidat.row_id, "anfrage_id")
    raenge = [
        rang
        for row_id in kontext.angebote_je_anfrage.get(anfrage_id, ())
        if (rang := ganzzahl_lesen(kontext.wert("angebot", row_id, "rang"))) is not None
    ]
    if not raenge:
        return None
    werte = _kopie_angebot(kontext, kandidat, rng)
    werte["rang"] = ganzzahl_schreiben(max(raenge) + _RANGLUECKE)
    return _satz(kandidat, werte)


def _konfliktduplikat(
    kontext: Injektionskontext, kandidat: Kandidat, rng: Generator
) -> Aenderung | None:
    """F6-c: Duplikat mit leicht abweichendem Zahlbeitrag."""
    rate = betrag_lesen(kontext.wert(kandidat.entitaet, kandidat.row_id, "zahlbeitrag_rate_eur"))
    if rate is None:
        return None
    werte = _kopie_angebot(kontext, kandidat, rng)
    werte["zahlbeitrag_rate_eur"] = betrag_schreiben(rate + _KONFLIKTBETRAG)
    return _satz(kandidat, werte)


def _zweiter_versicherungsnehmer(
    kontext: Injektionskontext, kandidat: Kandidat, rng: Generator
) -> Aenderung | None:
    """F6-d: Zweiter Personensatz mit der Rolle des Versicherungsnehmers."""
    werte = kopiere_zeile(kontext, kandidat.entitaet, kandidat.row_id)
    werte["person_id"] = neue_uuid(rng)
    werte["rolle"] = Rolle.VN.value
    return _satz(kandidat, werte)


VARIANTEN: Sequence[Variante] = (
    Variante(
        variante_id="F6-a",
        fehlerklasse=Fehlerklasse.F6,
        zielart=Zielart.SATZ,
        beschreibung="Angebotszeile vollstaendig dupliziert, neue Kennung, gleicher Rang",
        ursache="Lieferpaket zweimal eingespielt",
        kandidaten=_kandidaten_angebot,
        anwenden=_duplikat_gleicher_rang,
    ),
    Variante(
        variante_id="F6-b",
        fehlerklasse=Fehlerklasse.F6,
        zielart=Zielart.SATZ,
        beschreibung="Angebotszeile dupliziert, Rang neu vergeben — mit Luecke in der Rangfolge",
        ursache="Wiederholungslauf nach Abbruch vergibt Raenge neu",
        kandidaten=_kandidaten_angebot,
        anwenden=_duplikat_mit_rangluecke,
    ),
    Variante(
        variante_id="F6-c",
        fehlerklasse=Fehlerklasse.F6,
        zielart=Zielart.SATZ,
        beschreibung="Angebotszeile dupliziert, Zahlbeitrag leicht abweichend",
        ursache="Zweite Tarifierung desselben Risikos mit minimal anderem Ergebnis",
        kandidaten=_kandidaten_angebot,
        anwenden=_konfliktduplikat,
    ),
    Variante(
        variante_id="F6-d",
        fehlerklasse=Fehlerklasse.F6,
        zielart=Zielart.SATZ,
        beschreibung="Zweiter Personensatz mit der Rolle Versicherungsnehmer",
        ursache="Formular doppelt abgeschickt; beide Saetze tragen dieselbe Rolle",
        kandidaten=_kandidaten_person,
        anwenden=_zweiter_versicherungsnehmer,
    ),
)
