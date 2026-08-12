"""Gegenschnitt B3b: Great Expectations lokalisiert, wo cuallee es nicht tut.

Diese Datei belegt die **eine** Aussage, wegen der es das Modul gibt: Der Befund
"der Report nennt keine Zeile" ist eine Eigenschaft von cuallee und nicht der
Gattung. Waere er eine Gattungseigenschaft, genuegte einem Pruefer die Kenntnis
von Great Expectations, um ihn zu kippen — und mit ihm die Begruendung des
Artefakts.

Die Tests laufen auf einem **Miniaturrahmen von Hand**, nicht auf einem erzeugten
Datensatz. Sie pruefen die Faehigkeiten des Frameworks, nicht die Erkennungsleistung
auf den Projektdaten; dafuer ist ein Rahmen mit vier Zeilen aussagekraeftiger als
einer mit sechzigtausend, weil die erwarteten Treffer im Test stehen.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from src.baselines.b3_framework import DIAGNOSEGUETE
from src.baselines.b3b_great_expectations import (
    DIAGNOSEGUETE_GE,
    GE_REGELN,
    GEVergleich,
    ge_katalog,
)

gx = pytest.importorskip(
    "great_expectations",
    reason="Der Gegenschnitt B3b braucht great_expectations; siehe requirements.txt.",
)


def _batch(rahmen: pd.DataFrame, name: str) -> Any:  # noqa: ANN401 - GE liefert keine Stubs
    """Baut einen Great-Expectations-Stapel ueber einen Datenrahmen."""
    kontext = gx.get_context(mode="ephemeral")
    quelle = kontext.data_sources.add_pandas(name)
    asset = quelle.add_dataframe_asset(name)
    return asset.add_batch_definition_whole_dataframe("ganz").get_batch(
        batch_parameters={"dataframe": rahmen}
    )


#: Ausgabeformat, das den Zeilen- und Wertbezug erzeugt.
FORMAT = {"result_format": "COMPLETE", "unexpected_index_column_names": ["row_id"]}


@pytest.mark.filterwarnings("ignore")
def test_great_expectations_nennt_zeile_und_ausgangswert() -> None:
    """Der Report liefert je fehlgeschlagener Zeile Kennung **und** Wert.

    Das ist der Gegenschnitt in einem Satz. cuallee liefert an derselben Stelle
    nur die Zahl der Verstoesse; die Kennzahl Diagnoseguete unterscheidet die
    beiden Werkzeuge, nicht die Gattung.
    """
    rahmen = pd.DataFrame({"row_id": ["0", "1", "2"], "plz": ["10115", "1011", "ABCDE"]})
    erwartung = gx.expectations.ExpectColumnValuesToMatchRegex(column="plz", regex=r"^\d{5}$")

    ergebnis = _batch(rahmen, "person").validate(erwartung, result_format=FORMAT)["result"]

    assert ergebnis["unexpected_count"] == 2
    assert ergebnis["unexpected_index_list"] == [
        {"plz": "1011", "row_id": "1"},
        {"plz": "ABCDE", "row_id": "2"},
    ]
    assert ergebnis["unexpected_index_query"]


@pytest.mark.filterwarnings("ignore")
def test_bedingte_regel_ist_formulierbar() -> None:
    """R-001 ist mit ``row_condition`` vollstaendig formulierbar.

    Der bedingte Teil — ``anrede`` ungleich FIRMA erzwingt ein ``geburtsdatum`` —
    ist eine bedingte funktionale Abhaengigkeit. cuallee kann sie nicht ausdruecken
    und fuehrt R-001 deshalb als nur teilweise ausdrueckbar. Die Firmenzeile darf
    **nicht** als Verstoss gelten, sonst waere die Bedingung wirkungslos.
    """
    rahmen = pd.DataFrame(
        {
            "row_id": ["0", "1", "2"],
            "anrede": ["FIRMA", "HERR", "FRAU"],
            "geburtsdatum": ["", "01011990", ""],
        }
    )
    erwartung = gx.expectations.ExpectColumnValuesToNotMatchRegex(
        column="geburtsdatum",
        regex="^$",
        row_condition='anrede != "FIRMA"',
        condition_parser="pandas",
    )

    ergebnis = _batch(rahmen, "person").validate(erwartung, result_format=FORMAT)["result"]

    assert ergebnis["unexpected_count"] == 1
    assert ergebnis["unexpected_index_list"] == [{"geburtsdatum": "", "row_id": "2"}]


@pytest.mark.filterwarnings("ignore")
def test_kalendertag_ist_formulierbar() -> None:
    """R-009 faellt ueber ``ExpectColumnValuesToMatchStrftimeFormat`` auf.

    Die Erwartung parst den Wert wirklich, statt ihn gegen ein Muster zu halten;
    der 31. Februar hat acht Ziffern und ist trotzdem kein Kalendertag. cuallee
    fuehrt R-009 aus genau diesem Grund als nicht ausdrueckbar.
    """
    rahmen = pd.DataFrame({"row_id": ["0", "1", "2"], "geburtsdatum": ["01011990", "31022026", ""]})
    erwartung = gx.expectations.ExpectColumnValuesToMatchStrftimeFormat(
        column="geburtsdatum",
        strftime_format="%d%m%Y",
        row_condition='geburtsdatum != ""',
        condition_parser="pandas",
    )

    ergebnis = _batch(rahmen, "person").validate(erwartung, result_format=FORMAT)["result"]

    assert ergebnis["unexpected_count"] == 1
    assert ergebnis["unexpected_index_list"] == [{"geburtsdatum": "31022026", "row_id": "1"}]


def test_diagnoseguete_unterscheidet_die_beiden_frameworks() -> None:
    """Die beiden Kennzahlentabellen widersprechen sich genau in zwei Zeilen.

    Ohne diesen Test koennte eine spaetere Aenderung eine der beiden Tabellen
    angleichen, und die Aussage des Gegenschnitts verschwaende lautlos.
    """
    assert DIAGNOSEGUETE["zeile"] is False
    assert DIAGNOSEGUETE["ausgangswert"] is False
    assert DIAGNOSEGUETE_GE["zeile"] is True
    assert DIAGNOSEGUETE_GE["ausgangswert"] is True
    gleich = {name for name in DIAGNOSEGUETE if DIAGNOSEGUETE[name] == DIAGNOSEGUETE_GE[name]}
    assert gleich == {"spalte", "regel", "anzahl_verstoesse"}


def test_katalog_enthaelt_die_entscheidenden_regeln() -> None:
    """Die Auswahl deckt die Stellen ab, an denen sich die Frameworks trennen.

    Sie ist nach einem Kriterium getroffen und nicht nach Bequemlichkeit: die
    beiden Regeln, an denen cuallee scheitert, die Regel mit bedingter Struktur
    und vier, die cuallee glatt formuliert.
    """
    kennungen = {eintrag.regel_id for eintrag in ge_katalog()}
    assert {"R-001", "R-004", "R-009"} <= kennungen
    assert len(GE_REGELN) == 7

    einordnung = {e.regel_id: (e.ausdruckbar, e.cuallee_ausdruckbar) for e in GE_REGELN}
    # Die beiden Regeln, an denen sich die Frameworks unterscheiden.
    assert einordnung["R-001"] == (True, "teilweise")
    assert einordnung["R-009"] == (True, "nein")
    # Die algorithmische Regel, an der beide scheitern.
    assert einordnung["R-004"] == (False, "nein")


def test_vergleich_ist_kein_verfahren_des_evaluators() -> None:
    """``GEVergleich`` tritt nicht als Verfahren an und geht nicht in die Statistik.

    Der Gegenschnitt ist eine zweite Spalte der Frameworkvergleichstabelle, keine
    dritte Baseline. Ein ``erkenne``-Verfahren waere im Evaluator anschlussfaehig
    und wuerde genau die Verwechslung nahelegen, die dieser Test ausschliesst.
    """
    assert GEVergleich.in_inferenzstatistik is False
    assert not hasattr(GEVergleich, "erkenne")
