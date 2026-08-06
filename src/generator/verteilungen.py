"""Gekapselte Ziehungsfunktionen des Datengenerators.

Jede Funktion bekommt den Zufallsgenerator **uebergeben**. Es gibt in diesem
Modul keinen Modulzustand, keinen globalen Seed und keine Ziehung, die an der
Systemzeit haengt (Architekturregel A2).

Die Verteilungsannahmen selbst stehen nicht hier, sondern in den Entitaetsmodulen
neben dem Feld, das sie betreffen — und in ``docs/verteilungsquellen.md``. Hier
liegen nur die Ziehungsmechanismen.

Zur Doppelung mit ``scripts/build_reference.py``
------------------------------------------------

Das Referenzskript enthaelt eine gleichwertige private Fassung von
:func:`verteile_ganzzahlig`. Sie wird bewusst **nicht** zusammengelegt: Die
Referenztabellen unter ``data/reference`` sind versionierte Artefakte, deren
Hashwerte in ``tests/test_reproduzierbarkeit.py`` gegen einen frischen Lauf
geprueft werden. Jede Aenderung am Erzeugungsweg des Referenzskripts — auch eine
rein strukturelle — waere ein Risiko ohne Gegenwert.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import TYPE_CHECKING, Final

import numpy as np

from src.common.datum import datum_plus_jahre, jahre_zwischen

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    import numpy.typing as npt
    from numpy.random import Generator

__all__ = [
    "datum_plus_jahre",
    "erzeuge_uuids",
    "exakte_aufteilung",
    "jahre_zwischen",
    "normiere",
    "verteile_ganzzahlig",
    "waehle_index",
    "waehle_ohne_zuruecklegen",
    "ziehe_datum",
    "ziehe_ganzzahl_lognormal",
    "ziehe_lognormal",
    "ziehe_wahrheit",
    "ziehe_zeitpunkt",
]

#: Sekunden eines Tages.
_SEKUNDEN_JE_TAG: Final[int] = 86_400

#: Zahl der Bytes einer UUID.
_UUID_BYTES: Final[int] = 16


def erzeuge_uuids(rng: Generator, anzahl: int) -> list[str]:
    """Erzeugt UUIDs der Version 4 aus dem uebergebenen Zufallsgenerator.

    ``uuid.uuid4()`` waere hier ein Fehler: Es zieht aus ``os.urandom`` und ist
    damit nicht reproduzierbar (Architekturregel A2). Erzeugt werden dieselben
    122 Zufallsbits, nur aus dem geseedeten Generator; Versions- und
    Variantenbits werden nach RFC 4122 gesetzt.

    Args:
        rng: Zufallsgenerator.
        anzahl: Zahl der zu erzeugenden Kennungen.

    Returns:
        Eine Liste von UUIDs in der Schreibweise ``8-4-4-4-12``.
    """
    rohbytes = rng.integers(0, 256, size=(anzahl, _UUID_BYTES), dtype=np.uint8)
    rohbytes[:, 6] = (rohbytes[:, 6] & 0x0F) | 0x40
    rohbytes[:, 8] = (rohbytes[:, 8] & 0x3F) | 0x80
    kennungen: list[str] = []
    for zeile in rohbytes:
        hexform = bytes(zeile.tolist()).hex()
        kennungen.append(
            f"{hexform[0:8]}-{hexform[8:12]}-{hexform[12:16]}-{hexform[16:20]}-{hexform[20:32]}"
        )
    return kennungen


def normiere(gewichte: Sequence[float]) -> npt.NDArray[np.float64]:
    """Normiert Gewichte auf die Summe eins.

    Args:
        gewichte: Nicht negative Gewichte, in Summe groesser als null.

    Returns:
        Die normierten Gewichte.

    Raises:
        ValueError: Bei negativen Gewichten oder einer Summe von null.
    """
    feld = np.asarray(gewichte, dtype=np.float64)
    if feld.size == 0 or np.any(feld < 0.0):
        raise ValueError(f"Gewichte muessen nicht negativ und nicht leer sein: {gewichte!r}")
    summe = float(feld.sum())
    if summe <= 0.0:
        raise ValueError("Gewichte muessen in Summe positiv sein")
    return feld / summe


def verteile_ganzzahlig(
    gesamt: int, gewichte: Sequence[float], *, mindestens: int = 0
) -> list[int]:
    """Verteilt eine ganze Zahl proportional auf Gewichte (groesste Reste).

    Das Verfahren ist deterministisch und summiert exakt auf ``gesamt``. Es wird
    ueberall dort gebraucht, wo ein Anteil **exakt** getroffen werden soll statt
    nur im Erwartungswert.

    Args:
        gesamt: Zu verteilende Gesamtmenge.
        gewichte: Nicht negative Gewichte.
        mindestens: Untergrenze je Eintrag.

    Returns:
        Eine Liste ganzer Zahlen, die exakt auf ``gesamt`` summiert.

    Raises:
        ValueError: Wenn die Untergrenze die Gesamtmenge nicht zulaesst.
    """
    anteile_soll = normiere(gewichte) * gesamt
    anzahl = len(anteile_soll)
    if anzahl * mindestens > gesamt:
        raise ValueError(
            f"{gesamt} laesst sich nicht auf {anzahl} Eintraege mit Untergrenze "
            f"{mindestens} verteilen"
        )

    anteile = [math.floor(wert) for wert in anteile_soll]
    reihenfolge = sorted(range(anzahl), key=lambda i: (-(anteile_soll[i] - anteile[i]), i))
    for index in reihenfolge[: gesamt - sum(anteile)]:
        anteile[index] += 1

    # Untergrenze durchsetzen und den Ueberschuss in fester Reihenfolge abziehen.
    fehlmenge = sum(max(mindestens - wert, 0) for wert in anteile)
    anteile = [max(wert, mindestens) for wert in anteile]
    for index in sorted(range(anzahl), key=lambda i: (-anteile[i], i)):
        if fehlmenge <= 0:
            break
        abzug = min(fehlmenge, anteile[index] - mindestens)
        anteile[index] -= abzug
        fehlmenge -= abzug
    return anteile


def exakte_aufteilung(
    rng: Generator, anzahl: int, gewichte: Sequence[float]
) -> npt.NDArray[np.int64]:
    """Zieht Kategorien so, dass die Anteile **exakt** getroffen werden.

    Die Zellzahlen je Kategorie stehen ueber :func:`verteile_ganzzahlig` vorab
    fest; gezogen wird nur noch ihre Reihenfolge. Gegenueber einer gewoehnlichen
    Ziehung entfaellt damit die Stichprobenstreuung — noetig ueberall dort, wo
    eine kleine Kategorie sonst um ein Vielfaches danebenliegen kann.

    Args:
        rng: Zufallsgenerator.
        anzahl: Zahl der zu ziehenden Werte.
        gewichte: Zielanteile der Kategorien.

    Returns:
        Ein Feld aus Kategorieindizes der Laenge ``anzahl``.
    """
    mengen = verteile_ganzzahlig(anzahl, gewichte)
    indizes = np.repeat(np.arange(len(mengen), dtype=np.int64), mengen)
    ergebnis: npt.NDArray[np.int64] = rng.permutation(indizes)
    return ergebnis


def waehle_index(
    rng: Generator, anzahl: int, gewichte: Sequence[float]
) -> npt.NDArray[np.int64]:
    """Zieht Kategorieindizes mit Zuruecklegen nach Gewichten.

    Args:
        rng: Zufallsgenerator.
        anzahl: Zahl der zu ziehenden Werte.
        gewichte: Gewichte der Kategorien.

    Returns:
        Ein Feld aus Kategorieindizes der Laenge ``anzahl``.
    """
    gezogen: npt.NDArray[np.int64] = rng.choice(
        len(gewichte), size=anzahl, p=normiere(gewichte)
    ).astype(np.int64)
    return gezogen


def waehle_ohne_zuruecklegen(
    rng: Generator, gewichte: Sequence[float], anzahl: int
) -> npt.NDArray[np.int64]:
    """Zieht verschiedene Kategorien ohne Zuruecklegen nach Gewichten.

    Args:
        rng: Zufallsgenerator.
        gewichte: Gewichte der Kategorien.
        anzahl: Zahl der zu ziehenden Kategorien.

    Returns:
        Ein Feld aus verschiedenen Kategorieindizes.

    Raises:
        ValueError: Wenn mehr Kategorien angefordert werden, als es gibt.
    """
    if anzahl > len(gewichte):
        raise ValueError(f"{anzahl} verschiedene Kategorien passen nicht in {len(gewichte)}")
    gezogen: npt.NDArray[np.int64] = rng.choice(
        len(gewichte), size=anzahl, replace=False, p=normiere(gewichte)
    ).astype(np.int64)
    return gezogen


def ziehe_wahrheit(rng: Generator, wahrscheinlichkeiten: Sequence[float]) -> npt.NDArray[np.bool_]:
    """Zieht Wahrheitswerte mit zeilenweise unterschiedlicher Wahrscheinlichkeit.

    Args:
        rng: Zufallsgenerator.
        wahrscheinlichkeiten: Wahrscheinlichkeit fuer ``True`` je Zeile.

    Returns:
        Ein Feld aus Wahrheitswerten.
    """
    schwelle = np.asarray(wahrscheinlichkeiten, dtype=np.float64)
    gezogen: npt.NDArray[np.bool_] = rng.random(schwelle.size) < schwelle
    return gezogen


def ziehe_lognormal(
    rng: Generator, anzahl: int, median: float, sigma: float
) -> npt.NDArray[np.float64]:
    """Zieht lognormalverteilte Werte um einen Median.

    Der Median ist bei der Lognormalverteilung ``exp(mu)``; die Parametrisierung
    ueber den Median ist damit direkt lesbar, anders als ueber den Erwartungswert.

    Args:
        rng: Zufallsgenerator.
        anzahl: Zahl der zu ziehenden Werte.
        median: Median der Verteilung, groesser als null.
        sigma: Streuung auf der logarithmischen Skala.

    Returns:
        Ein Feld aus positiven Werten.

    Raises:
        ValueError: Wenn der Median nicht positiv ist.
    """
    if median <= 0.0:
        raise ValueError(f"Median muss positiv sein, war {median}")
    gezogen: npt.NDArray[np.float64] = np.exp(rng.normal(math.log(median), sigma, size=anzahl))
    return gezogen


def ziehe_ganzzahl_lognormal(  # noqa: PLR0913 - Verteilung und Grenzen sind je Feld verschieden
    rng: Generator,
    anzahl: int,
    *,
    median: float,
    sigma: float,
    unten: int,
    oben: int,
    schrittweite: int = 1,
) -> npt.NDArray[np.int64]:
    """Zieht ganzzahlige lognormalverteilte Werte in einem festen Bereich.

    Args:
        rng: Zufallsgenerator.
        anzahl: Zahl der zu ziehenden Werte.
        median: Median der Verteilung.
        sigma: Streuung auf der logarithmischen Skala.
        unten: Untergrenze (einschliesslich).
        oben: Obergrenze (einschliesslich).
        schrittweite: Rasterung, zum Beispiel 500 fuer die Jahresfahrleistung.

    Returns:
        Ein Feld ganzer Zahlen im Bereich ``[unten, oben]``.
    """
    roh = ziehe_lognormal(rng, anzahl, median, sigma)
    gerastert = np.rint(roh / schrittweite) * schrittweite
    ergebnis: npt.NDArray[np.int64] = np.clip(gerastert, unten, oben).astype(np.int64)
    return ergebnis


def ziehe_datum(
    rng: Generator, anzahl: int, fruehestens: dt.date, spaetestens: dt.date
) -> list[dt.date]:
    """Zieht gleichverteilte Kalendertage aus einem geschlossenen Bereich.

    Args:
        rng: Zufallsgenerator.
        anzahl: Zahl der zu ziehenden Tage.
        fruehestens: Fruehester zulaessiger Tag (einschliesslich).
        spaetestens: Spaetester zulaessiger Tag (einschliesslich).

    Returns:
        Eine Liste von Kalendertagen.

    Raises:
        ValueError: Wenn der Bereich leer ist.
    """
    spanne = (spaetestens - fruehestens).days
    if spanne < 0:
        raise ValueError(f"Leerer Datumsbereich: {fruehestens} bis {spaetestens}")
    versatz = rng.integers(0, spanne + 1, size=anzahl)
    return [fruehestens + dt.timedelta(days=int(tage)) for tage in versatz]


def ziehe_zeitpunkt(
    rng: Generator,
    tage: Sequence[dt.date],
    *,
    stundengewichte: Sequence[float],
) -> list[dt.datetime]:
    """Setzt auf gegebene Kalendertage eine Uhrzeit mit gewichteter Stundenverteilung.

    Die letzten beiden Minuten des Tages bleiben frei. Der Berechnungszeitpunkt
    eines Angebots liegt bis zu 60 Sekunden nach dem Eingangszeitpunkt; ohne
    diesen Abstand koennte er auf den Folgetag rutschen und damit in einen anderen
    Tarifgueltigkeitszeitraum fallen.

    Args:
        rng: Zufallsgenerator.
        tage: Kalendertage, auf die die Uhrzeit gesetzt wird.
        stundengewichte: 24 Gewichte, eines je Stunde.

    Returns:
        Eine Liste von Zeitpunkten.

    Raises:
        ValueError: Wenn nicht genau 24 Stundengewichte uebergeben werden.
    """
    if len(stundengewichte) != 24:  # noqa: PLR2004 - ein Tag hat 24 Stunden
        raise ValueError(f"Es werden 24 Stundengewichte gebraucht, waren {len(stundengewichte)}")
    anzahl = len(tage)
    stunden = waehle_index(rng, anzahl, stundengewichte)
    minuten = rng.integers(0, 60, size=anzahl)
    sekunden = rng.integers(0, 60, size=anzahl)
    zeitpunkte: list[dt.datetime] = []
    for index, tag in enumerate(tage):
        rohsekunde = int(stunden[index]) * 3600 + int(minuten[index]) * 60 + int(sekunden[index])
        sekunde = min(rohsekunde, _SEKUNDEN_JE_TAG - 121)
        zeitpunkte.append(dt.datetime.combine(tag, dt.time()) + dt.timedelta(seconds=sekunde))
    return zeitpunkte


# Die Kalenderarithmetik liegt seit Phase 3 in ``src/common/datum.py``: Die
# Regel-Engine braucht dieselbe Rechnung wie der Generator (R-023, R-028, R-029).
# Zwei Fassungen wuerden am 29. Februar auseinanderlaufen. Die Namen bleiben hier
# ueber ``__all__`` erreichbar, damit die Entitaetsmodule unveraendert bleiben.
