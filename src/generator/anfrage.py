"""Anfragen — der Anker des Sternschemas.

Die Entitaet entsteht in zwei Schritten. Zuerst der Rahmen: Sparte, Kanal,
Eingangs- und Beginnzeitpunkt. Er wird gebraucht, bevor Person, Risiko und
Angebot erzeugt werden koennen. Erst danach kommen die Felder hinzu, die von den
nachgelagerten Entitaeten abhaengen:

* ``vn_person_id`` steht erst fest, wenn die Personen erzeugt sind.
* ``vorvertrag_vorhanden`` muss in den Kfz-Sparten ``True`` sein, sobald die
  Schadenfreiheitsklasse schadenfreie Jahre ausweist (spec/01, Abschnitt 3.1).
* ``zahlweise`` haengt an der Beitragshoehe, weil die Rate im plausiblen Korridor
  bleiben muss (siehe :mod:`src.generator.angebot`).

Die Spartenanteile werden **exakt** getroffen und nicht nur im Erwartungswert
gezogen. Die Auswertung berichtet Kennzahlen je Sparte; Stichprobenrauschen in den
Gruppengroessen waere dort eine vermeidbare Stoerquelle.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from src.common.enums import WAEHRUNG_STANDARD, Anfragestatus, Kanal
from src.common.serialisierung import SPALTEN_JE_ENTITAET, typisierter_rahmen
from src.generator.verteilungen import (
    erzeuge_uuids,
    exakte_aufteilung,
    waehle_index,
    ziehe_datum,
    ziehe_ganzzahl_lognormal,
    ziehe_wahrheit,
    ziehe_zeitpunkt,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    import pandas as pd
    from numpy.random import Generator

    from src.common.config import Config

__all__ = ["Anfragerahmen", "baue_anfragen", "erzeuge_rahmen"]

#: Zeitfenster, in dem Anfragen eingehen (spec/01, Abschnitt 3.1).
_ANFRAGEFENSTER_TAGE: Final[int] = 730

#: Eingangskanal mit Gewichten (Modellannahme).
_KANAL_GEWICHTE: Final[tuple[tuple[Kanal, float], ...]] = (
    (Kanal.WEB, 0.42),
    (Kanal.MAKLER, 0.24),
    (Kanal.APP, 0.14),
    (Kanal.API_BIPRO, 0.12),
    (Kanal.TELEFON, 0.08),
)

#: Tagesgang der Anfragen, ein Gewicht je Stunde (Modellannahme).
#:
#: Ohne Tagesgang laegen die Eingangszeitpunkte gleichverteilt ueber die Nacht.
#: Das ist fuer keine Regel von Belang, faellt aber bei jeder Sichtprobe auf.
_STUNDENGEWICHTE: Final[tuple[float, ...]] = (
    0.004, 0.003, 0.002, 0.002, 0.003, 0.007,
    0.017, 0.032, 0.052, 0.068, 0.074, 0.070,
    0.060, 0.062, 0.070, 0.072, 0.070, 0.066,
    0.060, 0.052, 0.043, 0.032, 0.021, 0.011,
)  # fmt: skip

#: Vorlauf bis zum Versicherungsbeginn: log-normal um 20 Tage, hoechstens ein Jahr.
_BEGINN_MEDIAN_TAGE: Final[float] = 20.0
_BEGINN_SIGMA: Final[float] = 1.10
_BEGINN_MAX_TAGE: Final[int] = 365

#: Anfragestatus mit Gewichten (Modellannahme).
_STATUS_GEWICHTE: Final[tuple[tuple[Anfragestatus, float], ...]] = (
    (Anfragestatus.NEU, 0.05),
    (Anfragestatus.TARIFIERT, 0.18),
    (Anfragestatus.ANGEBOT, 0.45),
    (Anfragestatus.ANTRAG, 0.25),
    (Anfragestatus.STORNIERT, 0.07),
)

#: Wahrscheinlichkeit eines Vorvertrags, wenn er nicht ohnehin zwingend ist.
_P_VORVERTRAG: Final[float] = 0.55


@dataclass(frozen=True, slots=True)
class Anfragerahmen:
    """Die Felder der Anfrage, die vor allen anderen Entitaeten feststehen.

    Attributes:
        anfrage_id: Kennung je Anfrage.
        sparte: Spartenschluessel je Anfrage.
        kanal: Eingangskanal je Anfrage.
        eingangszeitpunkt: Eingangszeitpunkt je Anfrage.
        versicherungsbeginn: Gewuenschter Versicherungsbeginn je Anfrage.
        anfrage_status: Status je Anfrage.
    """

    anfrage_id: tuple[str, ...]
    sparte: tuple[str, ...]
    kanal: tuple[str, ...]
    eingangszeitpunkt: tuple[dt.datetime, ...]
    versicherungsbeginn: tuple[dt.date, ...]
    anfrage_status: tuple[str, ...]


def erzeuge_rahmen(config: Config, rng: Generator) -> Anfragerahmen:
    """Erzeugt Sparte, Kanal, Eingangszeitpunkt, Beginn und Status je Anfrage.

    Args:
        config: Geladene Konfiguration; liefert Stichtag, Anfragezahl und
            Spartenverteilung.
        rng: Zufallsgenerator des Teilstroms "Anfrage".

    Returns:
        Den :class:`Anfragerahmen`.
    """
    anzahl = config.n_anfragen
    sparten_schluessel = list(config.sparten_verteilung)
    sparten_index = exakte_aufteilung(
        rng, anzahl, [config.sparten_verteilung[name] for name in sparten_schluessel]
    )
    kanal_index = waehle_index(rng, anzahl, [gewicht for _, gewicht in _KANAL_GEWICHTE])
    status_index = waehle_index(rng, anzahl, [gewicht for _, gewicht in _STATUS_GEWICHTE])

    tage = ziehe_datum(
        rng,
        anzahl,
        config.stichtag - dt.timedelta(days=_ANFRAGEFENSTER_TAGE),
        config.stichtag,
    )
    eingang = ziehe_zeitpunkt(rng, tage, stundengewichte=list(_STUNDENGEWICHTE))
    vorlauf = ziehe_ganzzahl_lognormal(
        rng,
        anzahl,
        median=_BEGINN_MEDIAN_TAGE,
        sigma=_BEGINN_SIGMA,
        unten=0,
        oben=_BEGINN_MAX_TAGE,
    )

    return Anfragerahmen(
        anfrage_id=tuple(erzeuge_uuids(rng, anzahl)),
        sparte=tuple(sparten_schluessel[int(index)] for index in sparten_index),
        kanal=tuple(_KANAL_GEWICHTE[int(index)][0].value for index in kanal_index),
        eingangszeitpunkt=tuple(eingang),
        versicherungsbeginn=tuple(
            eingang[index].date() + dt.timedelta(days=int(vorlauf[index]))
            for index in range(anzahl)
        ),
        anfrage_status=tuple(_STATUS_GEWICHTE[int(index)][0].value for index in status_index),
    )


def baue_anfragen(  # noqa: PLR0913 - die Anfrage buendelt Werte aus vier Entitaeten
    rng: Generator,
    rahmen: Anfragerahmen,
    *,
    sparten: Sequence[str],
    vn_person_id: Sequence[str],
    zahlweise: Sequence[int],
    vorvertrag_zwingend: Sequence[bool],
    vu_nummern: Sequence[str],
    marktanteile: Sequence[float],
) -> pd.DataFrame:
    """Vervollstaendigt die Anfragen um die abhaengigen Felder.

    Args:
        rng: Zufallsgenerator des Teilstroms "Anfrage".
        rahmen: Ergebnis von :func:`erzeuge_rahmen`.
        sparten: **Wirksame** Sparte je Anfrage. Sie kann von ``rahmen.sparte``
            abweichen: In den Kaskosparten werden Malus- und Schadenklasse nicht
            angenommen, solche Anfragen werden als Haftpflichtanfrage gefuehrt
            (``src/generator/risiko_kfz.py``, ``_wirksame_sparte``).
        vn_person_id: Kennung des Versicherungsnehmers je Anfrage.
        zahlweise: Gezogene Zahlweise je Anfrage.
        vorvertrag_zwingend: ``True``, wo ein Vorvertrag fachlich zwingend ist —
            in den Kfz-Sparten, sobald die Schadenfreiheitsklasse schadenfreie
            Jahre ausweist.
        vu_nummern: Anbieter, aus denen der Vorversicherer gezogen wird.
        marktanteile: Gewichte der Anbieter.

    Returns:
        Die Entitaet ``anfrage``.
    """
    anzahl = len(rahmen.anfrage_id)
    freiwillig = ziehe_wahrheit(rng, [_P_VORVERTRAG] * anzahl)
    vorversicherer = waehle_index(rng, anzahl, list(marktanteile))

    spalten: dict[str, list[object]] = {name: [] for name in SPALTEN_JE_ENTITAET["anfrage"]}
    for index in range(anzahl):
        vorvertrag = bool(vorvertrag_zwingend[index] or freiwillig[index])
        spalten["row_id"].append(index + 1)
        spalten["anfrage_id"].append(rahmen.anfrage_id[index])
        spalten["eingangszeitpunkt"].append(rahmen.eingangszeitpunkt[index])
        spalten["kanal"].append(rahmen.kanal[index])
        spalten["sparte"].append(sparten[index])
        spalten["vn_person_id"].append(vn_person_id[index])
        spalten["versicherungsbeginn"].append(rahmen.versicherungsbeginn[index])
        spalten["vorvertrag_vorhanden"].append(vorvertrag)
        spalten["vorversicherer_vu_nr"].append(
            vu_nummern[int(vorversicherer[index])] if vorvertrag else None
        )
        spalten["zahlweise"].append(int(zahlweise[index]))
        spalten["waehrung"].append(WAEHRUNG_STANDARD)
        spalten["anfrage_status"].append(rahmen.anfrage_status[index])

    return typisierter_rahmen(spalten, "anfrage")


def _pruefe_kataloge() -> None:
    """Selbstpruefung: Kanaele und Status decken ihre Enums vollstaendig ab."""
    if {wert for wert, _ in _KANAL_GEWICHTE} != set(Kanal):
        raise ValueError("Die Gewichte der Eingangskanaele decken den Katalog nicht ab")
    if {wert for wert, _ in _STATUS_GEWICHTE} != set(Anfragestatus):
        raise ValueError("Die Gewichte der Anfragestatus decken den Katalog nicht ab")


_pruefe_kataloge()
