"""Regeltests der Gruppe G4 (R-049 bis R-051).

G4 prueft Bedingungen zwischen Tabellen. R-050 und R-051 sind die beiden
C3-Regeln des Katalogs: Ohne Referenzdaten sind sie nicht pruefbar. Ihre Faelle
laufen gegen die kleine Referenztabelle aus ``bausteine``, nicht gegen die
achttausendzeilige Produktivdatei — ein Testfall soll am gesetzten Wert scheitern,
nicht an einer CSV.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.test_regeln.bausteine import VORGANG_KFZ, Fall, kennungen, pruefe_fall

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from src.common.config import Config

_SAUBER = VORGANG_KFZ


FAELLE: tuple[Fall, ...] = (
    # --- R-049 Referenzielle Integritaet ------------------------------------
    Fall("R-049", "alle-schluessel-loesen-auf", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-049",
        "leerer-fremdschluessel-ist-kein-verstoss",
        verletzt=False,
        zeilen={**_SAUBER, "anfrage": [{"vorversicherer_vu_nr": None}]},
    ),
    Fall(
        "R-049",
        "tarif-verweis-ins-leere",
        verletzt=True,
        zeilen={**_SAUBER, "angebot": [{"tarif_id": "T9"}]},
        spalten=("tarif_id",),
    ),
    Fall(
        "R-049",
        "anfrage-verweis-ins-leere",
        verletzt=True,
        zeilen={**_SAUBER, "zahlung": [{"anfrage_id": "A9"}]},
        spalten=("anfrage_id",),
    ),
    Fall(
        "R-049",
        "versicherungsnehmer-verweis-ins-leere",
        verletzt=True,
        zeilen={**_SAUBER, "anfrage": [{"vn_person_id": "P9"}]},
        spalten=("vn_person_id",),
    ),
    # --- R-050 Postleitzahl und Ort -----------------------------------------
    Fall("R-050", "ort-passt-zur-plz", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-050",
        "plz-nicht-in-der-referenz",
        verletzt=True,
        zeilen={**_SAUBER, "person": [{"plz": "99999"}]},
        spalten=("plz",),
    ),
    Fall(
        "R-050",
        "ort-passt-nicht",
        verletzt=True,
        zeilen={**_SAUBER, "person": [{"ort": "Falschstadt"}]},
        spalten=("ort", "plz"),
    ),
    # --- R-051 Fahrzeugkatalog ----------------------------------------------
    Fall("R-051", "merkmale-stimmen", verletzt=False, zeilen=_SAUBER),
    Fall(
        "R-051",
        "leere-typklassen-werden-uebergangen",
        verletzt=False,
        zeilen={**_SAUBER, "risiko_kfz": [{"typklasse_tk": None, "typklasse_vk": None}]},
    ),
    Fall(
        "R-051",
        "kombination-nicht-im-katalog",
        verletzt=True,
        zeilen={**_SAUBER, "risiko_kfz": [{"hsn": "9999"}]},
        spalten=("hsn", "tsn"),
    ),
    Fall(
        "R-051",
        "leistung-weicht-vom-katalog-ab",
        verletzt=True,
        zeilen={**_SAUBER, "risiko_kfz": [{"leistung_kw": 200}]},
        spalten=("leistung_kw",),
    ),
    Fall(
        "R-051",
        "antriebsart-weicht-vom-katalog-ab",
        verletzt=True,
        zeilen={**_SAUBER, "risiko_kfz": [{"antriebsart": "DIESEL"}]},
        spalten=("antriebsart",),
    ),
)


@pytest.mark.parametrize("fall", FAELLE, ids=kennungen(FAELLE))
def test_regel(config: Config, fall: Fall) -> None:
    """Jede G4-Regel meldet den Verstoss und schweigt auf regelkonformen Daten."""
    pruefe_fall(config, fall)
