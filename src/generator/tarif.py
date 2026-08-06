"""Tarifstammdaten — die erste Stufe der Abhaengigkeitskette.

Je Anbieter und Sparte entstehen mehrere aufeinanderfolgende Generationen mit
**lueckenlos aneinandergrenzenden** Gueltigkeitszeitraeumen (spec/01, Abschnitt
3.5). Zwei Gruende:

* Ohne mehrere Generationen ist die Fehlerklasse "veralteter Tarifstand" (R-055)
  spaeter nicht injizierbar — es gaebe schlicht keinen zweiten Stand, auf den ein
  Angebot faelschlich zeigen koennte.
* Ohne Lueckenlosigkeit gaebe es Berechnungszeitpunkte, zu denen ein Anbieter gar
  keinen gueltigen Tarif hat. Die Angebotserzeugung waehlt genau den Tarif, dessen
  Fenster den Berechnungszeitpunkt enthaelt; eine Luecke waere ein Abbruch.

Die Generationen decken den gesamten Zeitraum ab, in dem Anfragen entstehen
koennen (24 Monate vor dem Stichtag), mit Vorlauf davor und Nachlauf danach.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Final

from src.common import wertebereiche as wb
from src.common.enums import KFZ_SPARTEN, Deckungsart, Sparte
from src.common.serialisierung import typisierter_rahmen
from src.generator.verteilungen import verteile_ganzzahlig, waehle_index

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence

    import pandas as pd
    from numpy.random import Generator

    from src.common.config import Config

__all__ = ["Tarifstamm", "erzeuge_tarife"]

#: Vorlauf der Tarifhistorie vor dem fruehesten moeglichen Eingangszeitpunkt.
_VORLAUF_MONATE: Final[int] = 6

#: Nachlauf der Tarifhistorie ueber den Stichtag hinaus.
_NACHLAUF_MONATE: Final[int] = 6

#: Zeitraum, in dem Anfragen entstehen (spec/01, Abschnitt 3.1).
_ANFRAGEFENSTER_MONATE: Final[int] = 24

#: Zahl der Generationen je Anbieter und Sparte, mit ihren Gewichten.
_GENERATIONEN: Final[tuple[tuple[int, float], ...]] = ((3, 0.35), (4, 0.40), (5, 0.25))

#: Kuerzeste Laufzeit einer Generation in Monaten.
_MINDESTLAUFZEIT_MONATE: Final[int] = 4

#: Produktnamensstaemme; die Sparte wird angehaengt (Feldlaenge hoechstens 20).
_PRODUKTSTAEMME: Final[tuple[str, ...]] = (
    "Basis",
    "Classic",
    "Komfort",
    "Premium",
    "Direkt",
    "Smart",
    "Aktiv",
    "Optimal",
)

#: Kurzform der Sparte im Produktnamen.
_PRODUKT_SPARTE: Final[Mapping[str, str]] = {
    Sparte.KFZ_HAFTPFLICHT.value: "Kfz HP",
    Sparte.KFZ_VOLLKASKO.value: "Kfz VK",
    Sparte.KFZ_TEILKASKO.value: "Kfz TK",
    Sparte.HAUSRAT.value: "Hausrat",
}

#: Kurzform der Sparte in der Tarifkennung.
_KENNUNG_SPARTE: Final[Mapping[str, str]] = {
    Sparte.KFZ_HAFTPFLICHT.value: "KFZHP",
    Sparte.KFZ_VOLLKASKO.value: "KFZVK",
    Sparte.KFZ_TEILKASKO.value: "KFZTK",
    Sparte.HAUSRAT.value: "HR",
}

#: Gewichte der Deckungsarten in der Kfz-Haftpflicht (Modellannahme).
_DECKUNGSART_GEWICHTE: Final[tuple[tuple[Deckungsart, float], ...]] = (
    (Deckungsart.UNBEGRENZT, 0.72),
    (Deckungsart.GESETZLICHE_MINDESTDECKUNG, 0.10),
    (Deckungsart.SONSTIGE, 0.18),
)

#: Deckungssummen je Deckungsart: Personen, Sach, Vermoegen.
#:
#: Bei ``13`` (gesetzliche Mindestdeckung) exakt die Werte aus der Anlage zu
#: Paragraf 4 Absatz 2 PflVG. ``11`` (unbegrenzt) wird ueber eine pauschale
#: Hoechstsumme von 100 Millionen Euro abgebildet — "unbegrenzt" ist im
#: Datenmodell kein darstellbarer Wert.
_DECKUNGSSUMMEN: Final[Mapping[Deckungsart, tuple[Decimal, Decimal, Decimal]]] = {
    Deckungsart.UNBEGRENZT: (
        Decimal("100000000.00"),
        Decimal("100000000.00"),
        Decimal("100000000.00"),
    ),
    Deckungsart.GESETZLICHE_MINDESTDECKUNG: (
        wb.PFLVG_MINDESTDECKUNG_PERSONEN_EUR,
        wb.PFLVG_MINDESTDECKUNG_SACH_EUR,
        wb.PFLVG_MINDESTDECKUNG_VERMOEGEN_EUR,
    ),
    Deckungsart.SONSTIGE: (
        Decimal("15000000.00"),
        Decimal("50000000.00"),
        Decimal("100000.00"),
    ),
}

#: Wahrscheinlichkeit einer Werkstattbindung in den Kfz-Sparten (Modellannahme).
_P_WERKSTATTBINDUNG: Final[float] = 0.40

#: Laenge des Anbieterkuerzels in der Tarifkennung.
_KUERZEL_LAENGE: Final[int] = 3


class TarifFehler(RuntimeError):
    """Zu einem Anbieter, einer Sparte und einem Tag gibt es keinen gueltigen Tarif."""


@dataclass(frozen=True, slots=True)
class Tarifstamm:
    """Die Tariftabelle samt Nachschlagestruktur.

    Attributes:
        rahmen: Die Entitaet ``tarif``.
        gueltigkeit: Je Anbieter und Sparte die nach ``gueltig_ab`` sortierten
            Generationen als ``(gueltig_ab, gueltig_bis, tarif_id)``.
    """

    rahmen: pd.DataFrame
    gueltigkeit: Mapping[tuple[str, str], tuple[tuple[dt.date, dt.date, str], ...]]

    def finde(self, vu_nummer: str, sparte: str, tag: dt.date) -> str:
        """Gibt die Tarifkennung zurueck, die an diesem Tag gilt.

        Args:
            vu_nummer: Anbieter.
            sparte: Spartenschluessel.
            tag: Tag des Berechnungszeitpunkts.

        Returns:
            Die Tarifkennung.

        Raises:
            TarifFehler: Wenn es keinen passenden Tarif gibt. Bewusst ein Abbruch
                und kein Ersatzwert: Ein Angebot ohne gueltigen Tarif wuerde
                R-055 schon auf sauberen Daten verletzen.
        """
        for gueltig_ab, gueltig_bis, tarif_id in self.gueltigkeit[vu_nummer, sparte]:
            if gueltig_ab <= tag <= gueltig_bis:
                return tarif_id
        raise TarifFehler(
            f"Kein gueltiger Tarif fuer Anbieter {vu_nummer}, Sparte {sparte} am {tag}"
        )


def _monatsanfang(tag: dt.date, versatz_monate: int) -> dt.date:
    """Gibt den Ersten des um ``versatz_monate`` verschobenen Monats zurueck."""
    gesamt = tag.year * 12 + (tag.month - 1) + versatz_monate
    return dt.date(gesamt // 12, gesamt % 12 + 1, 1)


def _anbieterkuerzel(vu_nummern: Sequence[str], vu_namen: Sequence[str]) -> dict[str, str]:
    """Bildet je Anbieter ein eindeutiges Kuerzel fuer die Tarifkennung.

    Die ersten drei Buchstaben des Namens reichen bei den hinterlegten Anbietern
    aus. Bei einer Kollision wird die VU-Nummer angehaengt — eindeutig und
    deterministisch, statt still eine doppelte Kennung zu erzeugen.
    """
    kuerzel: dict[str, str] = {}
    vergeben: set[str] = set()
    for nummer, name in zip(vu_nummern, vu_namen, strict=True):
        kandidat = "".join(zeichen for zeichen in name if zeichen.isalpha())[
            :_KUERZEL_LAENGE
        ].upper()
        if kandidat in vergeben or len(kandidat) < _KUERZEL_LAENGE:
            kandidat = f"{kandidat}{nummer}"
        vergeben.add(kandidat)
        kuerzel[nummer] = kandidat
    return kuerzel


def _generationsgrenzen(
    rng: Generator, beginn: dt.date, ende: dt.date
) -> list[tuple[dt.date, dt.date]]:
    """Zerlegt den Zeitraum lueckenlos in aufeinanderfolgende Generationen."""
    anzahl = int(_GENERATIONEN[int(waehle_index(rng, 1, [g for _, g in _GENERATIONEN])[0])][0])
    monate_gesamt = (ende.year - beginn.year) * 12 + (ende.month - beginn.month)
    laengen = verteile_ganzzahlig(
        monate_gesamt,
        rng.uniform(0.7, 1.3, size=anzahl).tolist(),
        mindestens=_MINDESTLAUFZEIT_MONATE,
    )

    grenzen: list[tuple[dt.date, dt.date]] = []
    start = beginn
    for laenge in laengen:
        naechster = _monatsanfang(start, laenge)
        grenzen.append((start, naechster - dt.timedelta(days=1)))
        start = naechster
    # Die letzte Generation laeuft bis zum Ende des Nachlaufs weiter.
    letzter_start, _ = grenzen[-1]
    grenzen[-1] = (letzter_start, ende - dt.timedelta(days=1))
    return grenzen


def _kfz_haftpflicht_deckung(
    rng: Generator,
) -> tuple[int | None, Decimal | None, Decimal | None, Decimal | None]:
    """Zieht Deckungsart und Deckungssummen einer Kfz-Haftpflicht-Generation."""
    arten = [art for art, _ in _DECKUNGSART_GEWICHTE]
    index = int(waehle_index(rng, 1, [gewicht for _, gewicht in _DECKUNGSART_GEWICHTE])[0])
    art = arten[index]
    personen, sach, vermoegen = _DECKUNGSSUMMEN[art]
    return int(art), personen, sach, vermoegen


def erzeuge_tarife(config: Config, rng: Generator, vu_stammdaten: pd.DataFrame) -> Tarifstamm:
    """Erzeugt die Tarifstammdaten aller Anbieter und Sparten.

    Args:
        config: Geladene Konfiguration; liefert den Stichtag.
        rng: Zufallsgenerator des Teilstroms "Tarif".
        vu_stammdaten: Referenztabelle der Anbieter.

    Returns:
        Den :class:`Tarifstamm` mit Tariftabelle und Nachschlagestruktur.
    """
    stichtag = config.stichtag
    beginn = _monatsanfang(stichtag, -(_ANFRAGEFENSTER_MONATE + _VORLAUF_MONATE))
    ende = _monatsanfang(stichtag, _NACHLAUF_MONATE + 1)

    vu_nummern = [str(wert) for wert in vu_stammdaten["vu_nummer"]]
    vu_namen = [str(wert) for wert in vu_stammdaten["vu_name"]]
    kuerzel = _anbieterkuerzel(vu_nummern, vu_namen)

    spalten: dict[str, list[object]] = {
        "row_id": [],
        "tarif_id": [],
        "vu_nummer": [],
        "produktname": [],
        "sparte": [],
        "tarifgeneration": [],
        "gueltig_ab": [],
        "gueltig_bis": [],
        "deckungsart": [],
        "deckungssumme_personen_eur": [],
        "deckungssumme_sach_eur": [],
        "deckungssumme_vermoegen_eur": [],
        "werkstattbindung": [],
    }
    gueltigkeit: dict[tuple[str, str], tuple[tuple[dt.date, dt.date, str], ...]] = {}

    kfz_schluessel = {sparte.value for sparte in KFZ_SPARTEN}
    for vu_nummer in vu_nummern:
        for sparte in Sparte:
            stamm = _PRODUKTSTAEMME[int(waehle_index(rng, 1, [1.0] * len(_PRODUKTSTAEMME))[0])]
            produktname = f"{stamm} {_PRODUKT_SPARTE[sparte.value]}"
            fenster: list[tuple[dt.date, dt.date, str]] = []
            for gueltig_ab, gueltig_bis in _generationsgrenzen(rng, beginn, ende):
                generation = f"{gueltig_ab.year:04d}-{gueltig_ab.month:02d}"
                tarif_id = f"{kuerzel[vu_nummer]}-{_KENNUNG_SPARTE[sparte.value]}-{generation}"
                if sparte is Sparte.KFZ_HAFTPFLICHT:
                    deckungsart, personen, sach, vermoegen = _kfz_haftpflicht_deckung(rng)
                else:
                    deckungsart, personen, sach, vermoegen = None, None, None, None
                werkstatt = (
                    bool(rng.random() < _P_WERKSTATTBINDUNG)
                    if sparte.value in kfz_schluessel
                    else None
                )

                spalten["row_id"].append(len(spalten["row_id"]) + 1)
                spalten["tarif_id"].append(tarif_id)
                spalten["vu_nummer"].append(vu_nummer)
                spalten["produktname"].append(produktname)
                spalten["sparte"].append(sparte.value)
                spalten["tarifgeneration"].append(generation)
                spalten["gueltig_ab"].append(gueltig_ab)
                spalten["gueltig_bis"].append(gueltig_bis)
                spalten["deckungsart"].append(deckungsart)
                spalten["deckungssumme_personen_eur"].append(personen)
                spalten["deckungssumme_sach_eur"].append(sach)
                spalten["deckungssumme_vermoegen_eur"].append(vermoegen)
                spalten["werkstattbindung"].append(werkstatt)
                fenster.append((gueltig_ab, gueltig_bis, tarif_id))
            gueltigkeit[vu_nummer, sparte.value] = tuple(fenster)

    return Tarifstamm(rahmen=typisierter_rahmen(spalten, "tarif"), gueltigkeit=gueltigkeit)
