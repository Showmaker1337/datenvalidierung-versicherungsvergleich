"""Gemeinsame Bausteine der Injektionsvarianten.

Hier stehen die Hilfsmittel, die mehrere Varianten brauchen: der Aufbau von
Kandidatenlisten, die kohaerente Skalierung eines Beitragstupels und das
Nachfuehren der Preisrangfolge.

Kohaerente Skalierung — der Grund, warum sie hier zentral steht
---------------------------------------------------------------

``spec/03_fehlerklassen.md``, Abschnitt 2 verlangt fuer F8-b bis F8-e und HO2-b,
dass **das gesamte Beitragstupel** mit demselben Faktor skaliert wird:
``nettobeitrag_jahr_eur``, ``versicherungsteuer_eur``, ``bruttobeitrag_jahr_eur``
und ``zahlbeitrag_rate_eur`` gemeinsam. Wuerde nur der Zahlbeitrag skaliert,
braeche die Beitragsarithmetik des Satzes und die Varianten waeren garantiert
erkannt — von den falschen Regeln. F8-e, laut Konzept der wertvollste Einzelfall
des Injektors, waere wertlos.

Aus demselben Grund wird die **Rangfolge mitgezogen**: Ein skaliertes Angebot
wandert innerhalb seiner Anfrage an eine andere Preisposition. Bliebe ``rang``
stehen, loeste zusaetzlich die Rangregel aus. Die nachgefuehrten Rangzellen sind
``mitgezogen`` und keine Traegerzellen — die Begruendung steht im Docstring von
:mod:`src.injector.modell`.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Final

from src.common.serialisierung import ENTITAETEN, SPALTEN_JE_ENTITAET
from src.injector.modell import (
    SCHLUESSELSPALTEN,
    Aenderung,
    Kandidat,
    Zellaenderung,
)
from src.injector.rohwerte import (
    betrag_lesen,
    betrag_schreiben,
    ganzzahl_lesen,
    ganzzahl_schreiben,
    ist_leer,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Callable, Mapping, Sequence
    from decimal import Decimal

    from numpy.random import Generator

    from src.injector.modell import Injektionskontext

__all__ = [
    "BEITRAGSSPALTEN",
    "einzelne_zelle",
    "felder_ohne_schluessel",
    "kandidaten_aus_feldern",
    "kopiere_zeile",
    "neue_raenge",
    "neue_uuid",
    "satz_kandidaten",
    "skaliere_beitraege",
]

#: Laenge einer UUID in Bytes.
_UUID_BYTES: Final[int] = 16

#: Das Beitragstupel einer Angebotszeile (spec/03, Abschnitt 2, "Kohaerente Skalierung").
BEITRAGSSPALTEN: Final[tuple[str, ...]] = (
    "nettobeitrag_jahr_eur",
    "versicherungsteuer_eur",
    "bruttobeitrag_jahr_eur",
    "zahlbeitrag_rate_eur",
)


def felder_ohne_schluessel() -> tuple[tuple[str, str], ...]:
    """Gibt alle Felder zurueck, die eine zellbasierte Variante treffen darf.

    Ausgenommen sind ``row_id`` sowie Primaer- und Fremdschluessel
    (:data:`src.injector.modell.SCHLUESSELSPALTEN`).

    Returns:
        Paare aus Entitaets- und Spaltenname in Schemareihenfolge.
    """
    return tuple(
        (entitaet, spalte)
        for entitaet in ENTITAETEN
        for spalte in SPALTEN_JE_ENTITAET[entitaet]
        if spalte not in SCHLUESSELSPALTEN[entitaet]
    )


def kandidaten_aus_feldern(
    kontext: Injektionskontext,
    felder: Sequence[tuple[str, str]],
    *,
    wertbedingung: Callable[[str], bool] | None = None,
    zeilenbedingung: Callable[[Injektionskontext, str, int], bool] | None = None,
    schluessel_erlaubt: bool = False,
) -> tuple[Kandidat, ...]:
    """Baut die Kandidatenliste einer zellbasierten Variante.

    Die Reihenfolge ist fest: Entitaeten in Schemareihenfolge, darin Spalten in
    Schemareihenfolge, darin Zeilen in Datenreihenfolge. Die Reihenfolge ist Teil
    der Reproduzierbarkeit — gemischt wird erst spaeter, mit einem benannten
    Zufallsstrom.

    Args:
        kontext: Lesende Sicht auf den sauberen Datensatz.
        felder: Paare aus Entitaets- und Spaltenname.
        wertbedingung: Zusaetzliche Bedingung an den Zellinhalt. Ohne Angabe gilt
            "nicht leer" — eine leere Zelle laesst sich nicht verfaelschen, ohne
            dass die Verfaelschung ein Setzen waere.
        zeilenbedingung: Zusaetzliche Bedingung an die Zeile, etwa "die Anfrage
            hat jaehrliche Zahlweise".
        schluessel_erlaubt: Laesst Fremdschluesselspalten ausdruecklich zu. Nur
            die Variante F7-a nutzt das: Dort **ist** das Umbiegen des
            Tarifschluessels der modellierte Fehler. ``row_id`` bleibt auch dann
            ausgeschlossen (Architekturregel A3).

    Returns:
        Die Kandidaten in fester Reihenfolge.

    Raises:
        ValueError: Wenn ein Feld eine Schluesselspalte ist und
            ``schluessel_erlaubt`` nicht gesetzt wurde, oder wenn es ``row_id``
            ist. Das waere ein Programmierfehler und wuerde Architekturregel A3
            verletzen.
    """
    pruefe = wertbedingung if wertbedingung is not None else _nicht_leer
    gefunden: list[Kandidat] = []
    for entitaet, spalte in felder:
        if spalte == "row_id":
            raise ValueError("row_id ist niemals Ziel einer Injektion (Architekturregel A3)")
        if not schluessel_erlaubt and spalte in SCHLUESSELSPALTEN[entitaet]:
            raise ValueError(f"{entitaet}.{spalte} ist eine Schluesselspalte und kein Ziel")
        werte = kontext.spalte(entitaet, spalte)
        for row_id, wert in zip(kontext.row_ids[entitaet], werte, strict=True):
            if not pruefe(wert):
                continue
            if zeilenbedingung is not None and not zeilenbedingung(kontext, entitaet, row_id):
                continue
            gefunden.append(Kandidat(entitaet=entitaet, row_id=row_id, spalte=spalte))
    return tuple(gefunden)


def satz_kandidaten(
    kontext: Injektionskontext,
    entitaet: str,
    *,
    zeilenbedingung: Callable[[Injektionskontext, str, int], bool] | None = None,
) -> tuple[Kandidat, ...]:
    """Baut die Kandidatenliste einer satzbasierten Variante.

    Args:
        kontext: Lesende Sicht auf den sauberen Datensatz.
        entitaet: Entitaet, deren Zeilen dupliziert werden.
        zeilenbedingung: Zusaetzliche Bedingung an die Zeile.

    Returns:
        Die Kandidaten in Datenreihenfolge; ``spalte`` ist ``None``.
    """
    return tuple(
        Kandidat(entitaet=entitaet, row_id=row_id, spalte=None)
        for row_id in kontext.row_ids[entitaet]
        if zeilenbedingung is None or zeilenbedingung(kontext, entitaet, row_id)
    )


def einzelne_zelle(kandidat: Kandidat, wert_dirty: str | None) -> Aenderung:
    """Baut die Aenderung einer Variante, die genau eine Zelle setzt.

    Args:
        kandidat: Getroffener Kandidat; ``spalte`` muss gesetzt sein.
        wert_dirty: Neuer Rohwert, ``None`` fuer einen fehlenden Wert.

    Returns:
        Die Aenderung mit einer Traegerzelle.

    Raises:
        ValueError: Wenn der Kandidat keine Spalte traegt.
    """
    if kandidat.spalte is None:
        raise ValueError("Zellbasierte Variante ohne Spalte im Kandidaten")
    return Aenderung(
        zellen=(
            Zellaenderung(
                entitaet=kandidat.entitaet,
                row_id=kandidat.row_id,
                spalte=kandidat.spalte,
                wert_dirty=wert_dirty,
            ),
        )
    )


def neue_raenge(
    kontext: Injektionskontext,
    anfrage_id: str,
    neue_raten: Mapping[int, Decimal],
) -> tuple[Zellaenderung, ...] | None:
    """Fuehrt die Preisrangfolge einer Anfrage nach.

    Gerankt werden die **bepreisten** Angebote, also die mit gesetztem ``rang``.
    Bei gleichem Zahlbeitrag entscheidet der bisherige Rang; ohne diese
    Nebenordnung koennte eine unveraenderte Anfrage eine andere Rangfolge
    bekommen als der Generator sie vergeben hat, und der Injektor erzeugte
    Abweichungen, die keine Verfaelschung sind.

    Args:
        kontext: Lesende Sicht auf den sauberen Datensatz.
        anfrage_id: Anfrage, deren Rangfolge nachgefuehrt wird.
        neue_raten: Neuer Zahlbeitrag je veraenderter Angebotszeile.

    Returns:
        Die nachzufuehrenden Rangzellen, oder ``None``, wenn ein Zahlbeitrag
        nicht lesbar ist und die Rangfolge deshalb nicht bestimmbar waere.
    """
    eintraege: list[tuple[Decimal, int, int]] = []
    for row_id in kontext.angebote_je_anfrage.get(anfrage_id, ()):
        rang = ganzzahl_lesen(kontext.wert("angebot", row_id, "rang"))
        if rang is None:
            continue
        rate = neue_raten.get(row_id)
        if rate is None:
            rate = betrag_lesen(kontext.wert("angebot", row_id, "zahlbeitrag_rate_eur"))
        if rate is None:
            return None
        eintraege.append((rate, rang, row_id))

    eintraege.sort()
    return tuple(
        Zellaenderung(
            entitaet="angebot",
            row_id=row_id,
            spalte="rang",
            wert_dirty=ganzzahl_schreiben(neuer_rang),
            mitgezogen=True,
        )
        for neuer_rang, (_, alter_rang, row_id) in enumerate(eintraege, start=1)
        if neuer_rang != alter_rang
    )


def skaliere_beitraege(
    kontext: Injektionskontext,
    anfrage_id: str,
    angebote: Sequence[int],
    faktor: Decimal,
) -> Aenderung | None:
    """Skaliert das Beitragstupel mehrerer Angebote kohaerent und fuehrt die Raenge nach.

    Args:
        kontext: Lesende Sicht auf den sauberen Datensatz.
        anfrage_id: Anfrage, zu der die Angebote gehoeren.
        angebote: Zeilenkennungen der zu skalierenden Angebote.
        faktor: Skalierungsfaktor; die vier Beitragsfelder werden gemeinsam
            damit multipliziert und kaufmaennisch auf zwei Nachkommastellen
            gerundet.

    Returns:
        Die Aenderung, oder ``None``, wenn ein Beitragsfeld leer oder nicht
        lesbar ist oder die Skalierung an einer Stelle nichts veraendern wuerde.
    """
    zellen: list[Zellaenderung] = []
    neue_raten: dict[int, Decimal] = {}
    for row_id in angebote:
        skaliert = _skaliere_zeile(kontext, row_id, faktor)
        if skaliert is None:
            return None
        zeilenzellen, neue_rate = skaliert
        zellen.extend(zeilenzellen)
        neue_raten[row_id] = neue_rate

    raenge = neue_raenge(kontext, anfrage_id, neue_raten)
    if raenge is None:
        return None
    return Aenderung(zellen=(*zellen, *raenge))


def _skaliere_zeile(
    kontext: Injektionskontext, row_id: int, faktor: Decimal
) -> tuple[list[Zellaenderung], Decimal] | None:
    """Skaliert das Beitragstupel einer einzelnen Angebotszeile."""
    zellen: list[Zellaenderung] = []
    neue_rate: Decimal | None = None
    for spalte in BEITRAGSSPALTEN:
        roh = kontext.wert("angebot", row_id, spalte)
        betrag = betrag_lesen(roh)
        if betrag is None:
            return None
        neuer_wert = betrag_schreiben(betrag * faktor)
        if neuer_wert == roh:
            return None
        zellen.append(
            Zellaenderung(entitaet="angebot", row_id=row_id, spalte=spalte, wert_dirty=neuer_wert)
        )
        if spalte == "zahlbeitrag_rate_eur":
            neue_rate = betrag_lesen(neuer_wert)
    if neue_rate is None:
        return None
    return zellen, neue_rate


def neue_uuid(rng: Generator) -> str:
    """Erzeugt eine UUID der Version 4 aus dem uebergebenen Zufallsstrom.

    ``uuid.uuid4()`` waere hier falsch: Es zieht aus der Entropiequelle des
    Betriebssystems und waere damit nicht reproduzierbar (Architekturregel A2).
    Die Bytes kommen deshalb aus dem geseedeten Generator; Versions- und
    Variantenbits werden anschliessend nach RFC 4122 gesetzt, damit die Kennung
    formal eine UUID4 ist wie alle uebrigen Schluessel des Datenmodells.

    Args:
        rng: Zufallsstrom der Variante.

    Returns:
        Die Kennung in der ueblichen Schreibweise mit Bindestrichen.
    """
    rohbytes = bytearray(rng.bytes(_UUID_BYTES))
    rohbytes[6] = (rohbytes[6] & 0x0F) | 0x40
    rohbytes[8] = (rohbytes[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(rohbytes)))


def kopiere_zeile(kontext: Injektionskontext, entitaet: str, row_id: int) -> dict[str, str]:
    """Kopiert eine Zeile ohne ihre ``row_id``.

    Args:
        kontext: Lesende Sicht auf den sauberen Datensatz.
        entitaet: Name der Entitaet.
        row_id: Zu kopierende Zeile.

    Returns:
        Die Rohwerte der Zeile; ``row_id`` fehlt, weil die Pipeline sie neu
        vergibt (spec/03, Abschnitt 5, Protokollregel 1).
    """
    werte = kontext.zeilenwerte(entitaet, row_id)
    werte.pop("row_id", None)
    return werte


def _nicht_leer(wert: str) -> bool:
    """Standardbedingung der Kandidatenauswahl: die Zelle ist gefuellt."""
    return not ist_leer(wert)
