"""F7 — veralteter Tarifstand und Gueltigkeitsverletzung (``spec/03``, Abschnitt 2).

Empirische Ursachen: Ein Vergleichsrechner arbeitet nach einem Releasewechsel
noch mit dem alten Tarifstand weiter, weil ein Zwischenspeicher nicht geleert
wurde (F7-a). Eine Nachverarbeitung traegt den Zeitpunkt des urspruenglichen
Antrags statt den der Neuberechnung ein (F7-b). Bei der Pflege der
Tarifstammdaten werden Beginn und Ende vertauscht (F7-c) oder die
Generationsbezeichnung wird zurueckgesetzt, ohne die Gueltigkeit anzupassen
(F7-d).

F7-a ist die einzige Variante, die einen Fremdschluessel anfasst
----------------------------------------------------------------

Sonst bleiben Schluesselspalten aussen vor, weil eine gestoerte Referenz eine
andere Fehlerart waere. Hier **ist** das Umbiegen des Tarifschluessels genau der
modellierte Fehler: Der Schluessel bleibt gueltig und aufloesbar, er zeigt nur auf
eine Generation, deren Gueltigkeit vor dem Berechnungszeitpunkt endete.

F7-c wird zusaetzlich satzbasiert gefuehrt
------------------------------------------

``spec/03``, Abschnitt 4.2 nennt F7-c ausdruecklich als Fall des satzbasierten
Logs, weil die Verletzung den Gueltigkeitszeitraum einer Tarifzeile als Ganzes
betrifft. Die Variante veraendert trotzdem eine konkrete Zelle, und die **muss**
im zellbasierten Log stehen, sonst faende der Diff-Gegencheck eine Abweichung
ohne Protokolleintrag. Sie erscheint deshalb in **beiden** Logs; im satzbasierten
ohne ``referenz_row_id``, weil nichts dupliziert wurde. Praezisierung in
``spec/03`` nachgetragen.

F7-d soll **nicht** erkannt werden — das Feld ``tarifgeneration`` wird nicht
geprueft. Das ist ein Befund, kein Fehler.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Final

from src.injector.modell import (
    Aenderung,
    Fehlerklasse,
    Satzbefund,
    Variante,
    Zellaenderung,
    Zielart,
)
from src.injector.rohwerte import (
    monate_verschieben,
    tag_lesen,
    tag_schreiben,
    zeitpunkt_lesen,
    zeitpunkt_schreiben,
)
from src.injector.varianten.bausteine import einzelne_zelle, kandidaten_aus_feldern

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    from numpy.random import Generator

    from src.injector.modell import Injektionskontext, Kandidat

__all__ = ["VARIANTEN"]

#: Monate, um die der Berechnungszeitpunkt zurueckdatiert wird (Variante F7-b).
_RUECKDATIERUNG_MONATE: Final[int] = 18
#: Laenge der Generationsbezeichnung ``JJJJ-MM``.
_GENERATION_LAENGE: Final[int] = 7
#: Erster Tag eines Monats — Hilfsgroesse fuer die Generationsrechnung.
_ERSTER: Final[int] = 1


# ---------------------------------------------------------------------------
# F7-a — veralteter Tarifstand
# ---------------------------------------------------------------------------


def _kandidaten_tarifbezug(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Angebote, zu denen eine aeltere, bereits abgelaufene Tarifgeneration existiert."""
    return kandidaten_aus_feldern(
        kontext,
        (("angebot", "tarif_id"),),
        zeilenbedingung=lambda ktx, entitaet, row_id: bool(
            _abgelaufene_generationen(ktx, entitaet, row_id)
        ),
        schluessel_erlaubt=True,
    )


def _abgelaufene_generationen(
    kontext: Injektionskontext, entitaet: str, row_id: int
) -> tuple[str, ...]:
    """Bestimmt die Tarifkennungen desselben Anbieters, deren Gueltigkeit bereits endete."""
    tarif_id = kontext.wert(entitaet, row_id, "tarif_id")
    index = kontext.tarif_zeile_je_id.get(tarif_id)
    zeitpunkt = zeitpunkt_lesen(kontext.wert(entitaet, row_id, "berechnungszeitpunkt"))
    if index is None or zeitpunkt is None:
        return ()

    vu_nummer = kontext.spalte("tarif", "vu_nummer")[index]
    sparte = kontext.spalte("tarif", "sparte")[index]
    stichtag = zeitpunkt.date()

    aeltere: list[str] = []
    for kandidat_row_id in kontext.tarife_je_anbieter.get((vu_nummer, sparte), ()):
        kandidat_index = kontext.zeile["tarif"][kandidat_row_id]
        kandidat_id = kontext.spalte("tarif", "tarif_id")[kandidat_index]
        if kandidat_id == tarif_id:
            continue
        ende = tag_lesen(kontext.spalte("tarif", "gueltig_bis")[kandidat_index])
        if ende is not None and ende < stichtag:
            aeltere.append(kandidat_id)
    return tuple(aeltere)


def _alte_generation(
    kontext: Injektionskontext, kandidat: Kandidat, rng: Generator
) -> Aenderung | None:
    """F7-a: Das Angebot verweist auf eine bereits abgelaufene Tarifgeneration."""
    aeltere = _abgelaufene_generationen(kontext, kandidat.entitaet, kandidat.row_id)
    if not aeltere:
        return None
    return einzelne_zelle(kandidat, aeltere[int(rng.integers(0, len(aeltere)))])


# ---------------------------------------------------------------------------
# F7-b — zurueckdatierter Berechnungszeitpunkt
# ---------------------------------------------------------------------------


def _kandidaten_berechnungszeitpunkt(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Alle gefuellten Berechnungszeitpunkte."""
    return kandidaten_aus_feldern(kontext, (("angebot", "berechnungszeitpunkt"),))


def _zurueckdatiert(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F7-b: Der Berechnungszeitpunkt liegt achtzehn Monate zurueck."""
    if kandidat.spalte is None:
        return None
    zeitpunkt = zeitpunkt_lesen(kontext.wert(kandidat.entitaet, kandidat.row_id, kandidat.spalte))
    if zeitpunkt is None:
        return None
    verschoben = monate_verschieben(zeitpunkt, -_RUECKDATIERUNG_MONATE)
    return einzelne_zelle(kandidat, zeitpunkt_schreiben(verschoben))


# ---------------------------------------------------------------------------
# F7-c — verdrehter Gueltigkeitszeitraum
# ---------------------------------------------------------------------------


def _kandidaten_gueltigkeit(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Tarifzeilen mit lesbarem Gueltigkeitsbeginn."""
    return kandidaten_aus_feldern(
        kontext,
        (("tarif", "gueltig_bis"),),
        zeilenbedingung=lambda ktx, entitaet, row_id: tag_lesen(
            ktx.wert(entitaet, row_id, "gueltig_ab")
        )
        is not None,
    )


def _ende_vor_beginn(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F7-c: Das Gueltigkeitsende liegt vor dem Gueltigkeitsbeginn."""
    if kandidat.spalte is None:
        return None
    beginn = tag_lesen(kontext.wert(kandidat.entitaet, kandidat.row_id, "gueltig_ab"))
    if beginn is None:
        return None
    return Aenderung(
        zellen=(
            Zellaenderung(
                entitaet=kandidat.entitaet,
                row_id=kandidat.row_id,
                spalte=kandidat.spalte,
                wert_dirty=tag_schreiben(beginn - dt.timedelta(days=1)),
            ),
        ),
        befunde=(
            Satzbefund(
                entitaet=kandidat.entitaet,
                betroffene_row_ids=(kandidat.row_id,),
                referenz_row_id=None,
            ),
        ),
    )


# ---------------------------------------------------------------------------
# F7-d — zurueckgesetzte Generationsbezeichnung
# ---------------------------------------------------------------------------


def _kandidaten_generation(kontext: Injektionskontext) -> tuple[Kandidat, ...]:
    """Tarifzeilen mit einer Generationsbezeichnung im Format ``JJJJ-MM``."""
    return kandidaten_aus_feldern(
        kontext, (("tarif", "tarifgeneration"),), wertbedingung=_ist_generation
    )


def _ist_generation(wert: str) -> bool:
    """Trifft auf Bezeichnungen der Form ``JJJJ-MM`` zu."""
    if len(wert) != _GENERATION_LAENGE or wert[4] != "-":
        return False
    return wert[:4].isdigit() and wert[5:].isdigit()


def _generation_zurueckgesetzt(
    kontext: Injektionskontext, kandidat: Kandidat, _rng: Generator
) -> Aenderung | None:
    """F7-d: Die Generationsbezeichnung faellt eine Stufe zurueck, die Gueltigkeit bleibt."""
    if kandidat.spalte is None:
        return None
    wert = kontext.wert(kandidat.entitaet, kandidat.row_id, kandidat.spalte)
    stand = dt.datetime(int(wert[:4]), int(wert[5:]), _ERSTER, tzinfo=dt.UTC)
    vorher = monate_verschieben(stand, -1)
    return einzelne_zelle(kandidat, f"{vorher.year:04d}-{vorher.month:02d}")


VARIANTEN: Sequence[Variante] = (
    Variante(
        variante_id="F7-a",
        fehlerklasse=Fehlerklasse.F7,
        zielart=Zielart.ZELLE,
        beschreibung="Angebot verweist auf eine bereits abgelaufene Tarifgeneration",
        ursache="Nicht geleerter Tarifzwischenspeicher nach einem Releasewechsel",
        kandidaten=_kandidaten_tarifbezug,
        anwenden=_alte_generation,
    ),
    Variante(
        variante_id="F7-b",
        fehlerklasse=Fehlerklasse.F7,
        zielart=Zielart.ZELLE,
        beschreibung="Berechnungszeitpunkt um achtzehn Monate zurueckdatiert",
        ursache="Nachverarbeitung uebernimmt den Zeitpunkt des urspruenglichen Antrags",
        kandidaten=_kandidaten_berechnungszeitpunkt,
        anwenden=_zurueckdatiert,
    ),
    Variante(
        variante_id="F7-c",
        fehlerklasse=Fehlerklasse.F7,
        zielart=Zielart.ZELLE,
        beschreibung="Gueltigkeitsende vor dem Gueltigkeitsbeginn",
        ursache="Beginn und Ende bei der Pflege der Tarifstammdaten vertauscht",
        kandidaten=_kandidaten_gueltigkeit,
        anwenden=_ende_vor_beginn,
    ),
    Variante(
        variante_id="F7-d",
        fehlerklasse=Fehlerklasse.F7,
        zielart=Zielart.ZELLE,
        beschreibung="Generationsbezeichnung eine Stufe zurueckgesetzt, Gueltigkeit unveraendert",
        ursache="Manuelle Korrektur der Bezeichnung ohne Anpassung des Zeitraums",
        kandidaten=_kandidaten_generation,
        anwenden=_generation_zurueckgesetzt,
    ),
)
