"""Das Laden des Ground Truth: zwei harte Zusicherungen und die Duplikatregel.

Der Ground Truth ist heilig (Architekturregel A3). Die Auswertung nimmt die
Zusicherungen des Injektors deshalb nicht an, sondern prueft sie beim Laden gegen
die Datei — und bricht ab, statt zu bereinigen. Ein stiller Fix waere genau die
Sorte Korrektur, die spaeter niemand mehr im Ergebnis sieht.

Geprueft wird hier dreierlei. Erstens die **Doppelinjektion** (Protokollregel 2):
Kaeme dieselbe Zelle zweimal im ``error_log`` vor, waere sie in der Zellmenge
einmal vorhanden, in der Klassenzuordnung aber zweideutig — die Summe der ``n``
je Klasse ueberstiege die Zahl der Wahrheitszellen, und der Fehler faellt erst
Stunden spaeter als unerklaerliche Luecke zwischen Micro- und Macro-Recall auf.
Zweitens ``row_id`` als **Zielspalte**: Sie ist niemals Ziel einer Verfaelschung;
steht sie im Log, ist der Ground Truth selbst beschaedigt. Drittens die
**Duplikatregel**: Beide Partner eines Paares zaehlen als Satzwahrheit.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.common.serialisierung import SPALTEN_JE_ENTITAET
from src.evaluation.ground_truth import (
    ERROR_LOG_PFLICHTSPALTEN,
    RECORDS_PFLICHTSPALTEN,
    lade_ground_truth,
)
from src.evaluation.modell import AuswertungsFehler
from tests.test_evaluation import LAUF_ID, daten, satzlog, wahrheit, zelllog


def test_doppelinjektion_wird_gemeldet() -> None:
    """Dieselbe Zelle zweimal im ``error_log`` bricht die Auswertung ab.

    Die Metrik arbeitet mit Mengen und verlaesst sich auf Protokollregel 2. Ohne
    den Abbruch waere die Zuordnung der Zelle zu einer Fehlerklasse zweideutig,
    und jede gruppenweise Zahl der Arbeit stuende auf einem falschen ``n``.
    """
    daten_dirty = daten(3)

    with pytest.raises(AuswertungsFehler, match="zweimal protokolliert"):
        wahrheit(
            daten_dirty,
            zellen=[
                ("person", 1, "plz", "F2", "F2-a", False),
                ("person", 1, "plz", "F3", "F3-a", False),
            ],
        )


def test_row_id_als_zielspalte_wird_gemeldet() -> None:
    """Eine Logzeile mit ``row_id`` als Zielspalte bricht die Auswertung ab.

    Architekturregel A3 schliesst das aus. Ueber ``row_id`` verbindet der
    Gegencheck sauberen und verfaelschten Datensatz; waere sie verfaelscht, waere
    jede Zuordnung zwischen Ground Truth und Detektion falsch.
    """
    daten_dirty = daten(3)

    with pytest.raises(AuswertungsFehler, match="A3"):
        wahrheit(daten_dirty, zellen=[("person", 1, "row_id", "F2", "F2-a", False)])


def test_duplikatpaar_zaehlt_mit_beiden_partnern() -> None:
    """Beide ``row_id`` eines Duplikatpaares stehen in der Satzwahrheit.

    Keine Regel kann sagen, welche der beiden Zeilen die hinzugefuegte ist — sie
    sind in den fachlichen Feldern gleich, und die neue Kennung vergibt der
    Injektor rein technisch. Wuerde nur eine gefuehrt, produzierte jede korrekt
    arbeitende Duplikatregel je Paar genau ein garantiertes False Positive.
    """
    daten_dirty = daten(4)

    gt = wahrheit(daten_dirty, saetze=[("person", "F6", "F6-a", (2, 3))])

    assert [(eintrag.entitaet, eintrag.row_id) for eintrag in gt.saetze] == [
        ("person", 2),
        ("person", 3),
    ]
    assert set(gt.satzmenge(mitgezogen_als_fehler=False)) == {("person", 2), ("person", 3)}


def test_fehlende_pflichtspalte_wird_gemeldet() -> None:
    """Ein ``error_log`` ohne die Spalte ``mitgezogen`` bricht mit klarer Meldung ab.

    Kein stiller Fallback: Eine aeltere Logdatei ohne diese Spalte liesse sich nur
    auswerten, indem man eine Annahme ueber die mitgezogenen Zellen erfindet.
    """
    daten_dirty = daten(3)
    unvollstaendig = pd.DataFrame(
        columns=[name for name in ERROR_LOG_PFLICHTSPALTEN if name != "mitgezogen"]
    )

    with pytest.raises(AuswertungsFehler, match="fehlen die Spalten"):
        lade_ground_truth(unvollstaendig, satzlog(), daten_dirty, run_id=LAUF_ID)


def test_betroffene_row_ids_muessen_ein_container_sein() -> None:
    """Eine Zeichenkette statt einer Liste in ``betroffene_row_ids`` bricht ab.

    Der Fall entsteht beim Umweg ueber CSV. Stillschweigend zeichenweise zu
    zerlegen ergaebe Zeilenkennungen, die es nicht gibt.
    """
    daten_dirty = daten(3)
    verbogen = pd.DataFrame([("person", "F6", "F6-a", "1,2")], columns=list(RECORDS_PFLICHTSPALTEN))

    with pytest.raises(AuswertungsFehler, match="Liste von Zeilenkennungen"):
        lade_ground_truth(zelllog(), verbogen, daten_dirty, run_id=LAUF_ID)


def test_klassen_und_varianten_aus_dem_manifest_bleiben_sichtbar() -> None:
    """Klassen und Varianten mit Kontingent null werden trotzdem gefuehrt.

    Seit der proportionalen Zuteilung koennen einzelne Varianten bei kleinen
    Fehlerraten das Kontingent 0 erhalten. Eine fehlende Tabellenzeile waere von
    einem Recall 0 nicht zu unterscheiden — deshalb kommen beide Listen aus dem
    ``manifest.json`` und nicht nur aus den Logs.
    """
    daten_dirty = daten(3)

    gt = wahrheit(
        daten_dirty,
        zellen=[("person", 1, "plz", "F2", "F2-a", False)],
        klassen=["F1", "F2"],
        varianten=["F1-a", "F2-a", "F2-b"],
    )

    assert gt.klassen == ("F1", "F2")
    assert gt.varianten == ("F1-a", "F2-a", "F2-b")


def test_zelluniversum_zaehlt_row_id_mit() -> None:
    """Das Zelluniversum ist Zeilen mal Spalten, ``row_id`` eingeschlossen.

    Dieselbe Definition wie im Clean-Baseline-Lauf; nur so duerfen beide
    Fehlalarmraten nebeneinander stehen. ``row_id`` ist niemals Ziel einer
    Injektion und gehoert damit strukturell zu den echten Negativen.
    """
    daten_dirty = daten(3)

    gt = wahrheit(daten_dirty)

    assert gt.universum_zellen == 3 * len(SPALTEN_JE_ENTITAET["person"])
    assert gt.universum_saetze == 3
    assert gt.zeilen_je_entitaet["person"] == 3
    assert gt.zeilen_je_entitaet["angebot"] == 0


def test_zeile_gilt_nur_als_mitgezogen_wenn_alle_ihre_zellen_es_sind() -> None:
    """Eine Zeile mit einer echten und einer nachgefuehrten Zelle bleibt echt betroffen.

    Sonst verschwaende eine tatsaechlich verfaelschte Zeile aus der Satzwahrheit,
    sobald in derselben Zeile zusaetzlich etwas nachgefuehrt wurde — der Recall
    stiege, ohne dass ein Verfahren mehr gefunden haette.
    """
    daten_dirty = daten(4, entitaet="angebot")

    gt = wahrheit(
        daten_dirty,
        zellen=[
            ("angebot", 1, "nettobeitrag_jahr_eur", "F8", "F8-a", False),
            ("angebot", 1, "rang", "F8", "F8-a", True),
            ("angebot", 2, "rang", "F8", "F8-a", True),
        ],
    )
    ohne = gt.satzmenge(mitgezogen_als_fehler=False)
    mit = gt.satzmenge(mitgezogen_als_fehler=True)

    assert set(ohne) == {("angebot", 1)}
    assert set(mit) == {("angebot", 1), ("angebot", 2)}


def test_zellmenge_folgt_dem_schalter() -> None:
    """Ohne Schalter enthaelt die Zellwahrheit nur die echten Verfaelschungen."""
    daten_dirty = daten(4, entitaet="angebot")

    gt = wahrheit(
        daten_dirty,
        zellen=[
            ("angebot", 1, "nettobeitrag_jahr_eur", "F8", "F8-a", False),
            ("angebot", 2, "rang", "F8", "F8-a", True),
        ],
    )

    assert set(gt.zellmenge(mitgezogen_als_fehler=False)) == {
        ("angebot", 1, "nettobeitrag_jahr_eur")
    }
    assert len(gt.zellmenge(mitgezogen_als_fehler=True)) == 2


def test_zellwahrheiten_liegen_in_fester_reihenfolge() -> None:
    """Die Zellwahrheiten sind nach ``(entitaet, row_id, spalte)`` sortiert.

    Die Reihenfolge der Logdatei darf keine Kennzahl beeinflussen; die feste
    Sortierung ist Teil der Reproduzierbarkeit (Architekturregel A2).
    """
    daten_dirty = daten(3)

    gt = wahrheit(
        daten_dirty,
        zellen=[
            ("person", 3, "ort", "F1", "F1-a", False),
            ("person", 1, "plz", "F2", "F2-a", False),
            ("person", 1, "email", "F3", "F3-a", False),
        ],
    )

    assert [eintrag.schluessel for eintrag in gt.zellen] == [
        ("person", 1, "email"),
        ("person", 1, "plz"),
        ("person", 3, "ort"),
    ]
