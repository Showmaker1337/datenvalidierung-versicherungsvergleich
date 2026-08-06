"""Zahlung — Bankverbindung und SEPA-Mandat.

Die IBAN entsteht ueber :mod:`src.common.iban` und traegt deshalb eine **gueltige
Pruefziffer** nach ISO 7064 Mod 97-10 (R-004). Sie hier selbst zu berechnen waere
eine Doppelung der Regel; das Modul liegt genau deshalb in ``src/common``.

Die BIC hat acht oder elf Zeichen — neun oder zehn gibt es nach ISO 9362 nicht
(R-005). Der Mandatstag liegt nie nach dem Versicherungsbeginn.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Final

from src.common.iban import baue_iban
from src.common.serialisierung import SPALTEN_JE_ENTITAET, typisierter_rahmen
from src.generator.verteilungen import erzeuge_uuids, waehle_index, ziehe_wahrheit

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    import pandas as pd
    from faker import Faker
    from numpy.random import Generator

__all__ = ["erzeuge_zahlungen"]

#: Zeichenvorrat der letzten BIC-Stellen (ISO 9362).
_BIC_ALPHABET: Final[str] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

#: Buchstabenvorrat der ersten vier BIC-Stellen (Institutskennung).
_BIC_BUCHSTABEN: Final[str] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

#: Laenge der Institutskennung in der BIC.
_BIC_INSTITUT: Final[int] = 4

#: Laenge der Ortskennung in der BIC.
_BIC_ORT: Final[int] = 2

#: Wahrscheinlichkeit einer elfstelligen BIC (mit Filialkennung).
_P_BIC_ELFSTELLIG: Final[float] = 0.55

#: Laenge der Filialkennung.
_BIC_FILIALE: Final[int] = 3

#: Laendercode der erzeugten Bankverbindungen.
_BIC_LAND: Final[str] = "DE"

#: Zahl der Kontonummernstellen.
_KONTO_STELLEN: Final[int] = 10

#: Kleinste und groesste Bankleitzahl. Die fuehrende Ziffer null kommt in
#: deutschen Bankleitzahlen nicht vor.
_BLZ_UNTEN: Final[int] = 10_000_000
_BLZ_OBEN: Final[int] = 99_999_999

#: Wahrscheinlichkeit, dass der Kontoinhaber der Versicherungsnehmer ist.
_P_KONTOINHABER_IST_VN: Final[float] = 0.92

#: Feldlaenge des Kontoinhabers (spec/01, Abschnitt 3.7).
_MAX_KONTOINHABER: Final[int] = 60


def _bic(rng: Generator, anzahl: int) -> list[str]:
    """Erzeugt BIC-Kennungen mit acht oder elf Zeichen (R-005)."""
    institut = rng.integers(0, len(_BIC_BUCHSTABEN), size=(anzahl, _BIC_INSTITUT))
    ort = rng.integers(0, len(_BIC_ALPHABET), size=(anzahl, _BIC_ORT))
    filiale = rng.integers(0, len(_BIC_ALPHABET), size=(anzahl, _BIC_FILIALE))
    lang = ziehe_wahrheit(rng, [_P_BIC_ELFSTELLIG] * anzahl)

    ergebnis: list[str] = []
    for index in range(anzahl):
        kennung = "".join(_BIC_BUCHSTABEN[int(wert)] for wert in institut[index])
        kennung += _BIC_LAND
        kennung += "".join(_BIC_ALPHABET[int(wert)] for wert in ort[index])
        if lang[index]:
            kennung += "".join(_BIC_ALPHABET[int(wert)] for wert in filiale[index])
        ergebnis.append(kennung)
    return ergebnis


def _mandatstage(
    rng: Generator,
    eingangszeitpunkte: Sequence[dt.datetime],
    versicherungsbeginn: Sequence[dt.date],
) -> list[dt.date]:
    """Zieht den Mandatstag zwischen Anfrageeingang und Versicherungsbeginn.

    Damit gilt ``sepa_mandat_datum <= versicherungsbeginn`` (spec/01, Abschnitt 3.7).
    """
    anteile = rng.random(len(eingangszeitpunkte))
    ergebnis: list[dt.date] = []
    for index, zeitpunkt in enumerate(eingangszeitpunkte):
        untergrenze = zeitpunkt.date()
        spanne = max((versicherungsbeginn[index] - untergrenze).days, 0)
        ergebnis.append(untergrenze + dt.timedelta(days=int(float(anteile[index]) * (spanne + 1))))
    return [min(tag, versicherungsbeginn[index]) for index, tag in enumerate(ergebnis)]


def erzeuge_zahlungen(  # noqa: PLR0913 - Mandat und Kontoinhaber haengen an drei Quellen
    rng: Generator,
    faker: Faker,
    *,
    anfrage_ids: Sequence[str],
    eingangszeitpunkte: Sequence[dt.datetime],
    versicherungsbeginn: Sequence[dt.date],
    vn_namen: Sequence[str],
) -> pd.DataFrame:
    """Erzeugt je Anfrage eine Bankverbindung.

    Args:
        rng: Zufallsgenerator des Teilstroms "Zahlung".
        faker: Geseedete Faker-Instanz fuer abweichende Kontoinhaber.
        anfrage_ids: Kennung je Anfrage.
        eingangszeitpunkte: Eingangszeitpunkt je Anfrage.
        versicherungsbeginn: Versicherungsbeginn je Anfrage.
        vn_namen: Name des Versicherungsnehmers je Anfrage.

    Returns:
        Die Entitaet ``zahlung``.
    """
    anzahl = len(anfrage_ids)
    bankleitzahlen = rng.integers(_BLZ_UNTEN, _BLZ_OBEN + 1, size=anzahl)
    kontonummern = rng.integers(0, 10, size=(anzahl, _KONTO_STELLEN))
    bics = _bic(rng, anzahl)
    mandate = _mandatstage(rng, eingangszeitpunkte, versicherungsbeginn)
    ist_vn = ziehe_wahrheit(rng, [_P_KONTOINHABER_IST_VN] * anzahl)
    # Der Vorrat abweichender Kontoinhaber wird vorab gezogen, damit die Zahl der
    # Faker-Aufrufe nicht von der Ziehung oben abhaengt (Architekturregel A2).
    abweichende = [f"{faker.first_name()} {faker.last_name()}" for _ in range(anzahl)]
    auswahl: Sequence[int] = (
        [int(wert) for wert in waehle_index(rng, anzahl, [1.0] * anzahl)] if anzahl else []
    )
    zahlung_ids = erzeuge_uuids(rng, anzahl)

    spalten: dict[str, list[object]] = {name: [] for name in SPALTEN_JE_ENTITAET["zahlung"]}
    for index in range(anzahl):
        konto = "".join(str(int(ziffer)) for ziffer in kontonummern[index])
        spalten["row_id"].append(index + 1)
        spalten["zahlung_id"].append(zahlung_ids[index])
        spalten["anfrage_id"].append(anfrage_ids[index])
        spalten["iban"].append(baue_iban(f"{int(bankleitzahlen[index]):08d}", konto))
        spalten["bic"].append(bics[index])
        spalten["sepa_mandat_datum"].append(mandate[index])
        spalten["kontoinhaber"].append(
            vn_namen[index][:_MAX_KONTOINHABER]
            if ist_vn[index]
            else abweichende[int(auswahl[index])][:_MAX_KONTOINHABER]
        )

    return typisierter_rahmen(spalten, "zahlung")
