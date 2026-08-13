"""Zuordnung Injektionsvariante auf Regel — die Quelle fuer Abbildung 5 und t4.

Diese Tabelle ist **die** Antwort auf den Zirkularitaetsvorwurf, und sie steht
deshalb genau hier und nirgends sonst.

Warum sie nicht aus ``src.injector`` kommt
-------------------------------------------

``spec/03_fehlerklassen.md``, Abschnitt 6 verlangt es woertlich: "Die Zuordnung
Variante auf Regel entsteht erst in der **Auswertung**, nicht in der Erzeugung."
Der Injektor kennt keine Regel-IDs; wuerde er die erwartete Regel mitfuehren,
maesse das Experiment nur noch, ob dieselbe Bedingung zweimal geschrieben wurde.
Die Angaben hier sind aus der Variantentabelle in ``spec/03``, Abschnitt 2
uebertragen — aus der **Spezifikation**, nicht aus dem Quelltext des Injektors.
``src.evaluation`` importiert entsprechend nichts aus ``src.injector``.

Der Preis dieser Trennung ist eine Abschrift, die auseinanderlaufen kann. Er wird
mit einem Test bezahlt: ``tests/test_evaluation/test_varianten.py`` gleicht die
Kennungen hier gegen ``src.injector.varianten.ALLE_VARIANTEN`` und die Regel-IDs
gegen ``src.rules.katalog.KATALOG`` ab. Ein Test darf beide Seiten kennen; der
Produktivcode darf es nicht.

Die drei Einstufungen und warum es drei sind
---------------------------------------------

``spec/03`` unterscheidet "ja", "teilweise" und "nein". Eine binaere Einstufung
waere bequemer und falsch: F2-a (fuehrende Null der Postleitzahl geht verloren)
verletzt die Laengenbedingung von R-002 **manchmal** — naemlich nur bei
Postleitzahlen, die mit einer Null beginnen —, und F2-k (TSN in Kleinbuchstaben)
trifft eine Musterbedingung, die Kleinbuchstaben nicht ausdruecklich ausschliesst.
Beide als "spiegelt exakt" zu fuehren, wuerde den Beleg gegen die Zirkularitaet
schwaechen; beide als "spiegelt nicht" zu fuehren, waere geschoent in die andere
Richtung.

``erwartet_unentdeckt`` ist keine vierte Stufe, sondern eine unabhaengige
Eigenschaft: F5-e, F7-d und F8-e sind **absichtlich** so gebaut, dass der Katalog
sie nicht findet, und die beiden Held-out-Klassen ohnehin. Ein Recall nahe null
ist dort das Konstruktionsziel und kein Defizit — in Abbildung 5 und in
``t4_varianten.csv`` wird das ausgewiesen, damit die Balken nicht als Schwaeche
gelesen werden.

Die Spalte ``erwartete_regeln`` ist eine Erwartung, keine Messung
-----------------------------------------------------------------

Sie sagt, welche Regel laut Spezifikation greifen **soll**. Ob sie es tut, steht
in der Kreuztabelle ``regel_id`` gegen ``fehlerklasse`` (Abbildung 6) und wird
dort gemessen. Die beiden Angaben nebeneinander sind der eigentliche Ertrag: Wo
sie auseinanderfallen, hat der Katalog etwas anderes gefunden als gedacht — bei
HO2 zum Beispiel eine Nebenwirkung statt des Fehlers (siehe
``docs/iteration_log.md``, Aufraeumpunkt "Fehler erkannt ist nicht Nebenwirkung
erkannt").
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping

__all__ = [
    "ALLE_VARIANTEN_IDS",
    "VARIANTENTABELLE",
    "VARIANTE_JE_ID",
    "Spiegelung",
    "Variantenbezug",
    "klasse_je_variante",
    "variantenbezug",
]


class Spiegelung(StrEnum):
    """Wie genau eine Injektionsvariante die Bedingung ihrer Regel trifft.

    Die Werte erscheinen so in ``t4_varianten.csv`` und in der Beschriftung von
    Abbildung 5; sie sind Teil des Ausgabeformats.
    """

    JA = "ja"
    """Die Verfaelschung verletzt genau die Bedingung, die die Regel prueft."""

    TEILWEISE = "teilweise"
    """Die Bedingung wird nur unter zusaetzlichen Umstaenden verletzt."""

    NEIN = "nein"
    """Keine Regel des Katalogs prueft diese Bedingung unmittelbar."""


@dataclass(frozen=True, slots=True)
class Variantenbezug:
    """Der Bezug einer Injektionsvariante zum Regelkatalog.

    Attributes:
        variante_id: Kennung aus ``spec/03``, Abschnitt 2, zum Beispiel ``"F3-d"``.
        fehlerklasse: Klasse, zu der die Variante gehoert.
        spiegelung: Einstufung nach der Spalte "Spiegelt Regel exakt?".
        erwartete_regeln: Regeln, die laut Spezifikation greifen sollen; leer,
            wo keine greifen soll.
        erwartet_unentdeckt: ``True``, wenn die Variante absichtlich so gebaut
            ist, dass der Katalog sie nicht findet.
        anmerkung: Ein Satz Begruendung, sobald die Einstufung nicht "ja" ist.
            Er steht in ``t4_varianten.csv`` und macht die Tabelle ohne den
            Spezifikationstext lesbar.
    """

    variante_id: str
    fehlerklasse: str
    spiegelung: Spiegelung
    erwartete_regeln: tuple[str, ...]
    erwartet_unentdeckt: bool
    anmerkung: str


def _eintrag(
    variante_id: str,
    spiegelung: Spiegelung,
    regeln: tuple[str, ...] = (),
    *,
    unentdeckt: bool = False,
    anmerkung: str = "",
) -> Variantenbezug:
    """Baut einen Tabelleneintrag und leitet die Fehlerklasse aus der Kennung ab.

    Args:
        variante_id: Kennung der Variante, etwa ``"F3-d"``.
        spiegelung: Einstufung nach ``spec/03``, Abschnitt 2.
        regeln: Erwartete Regeln.
        unentdeckt: Ob die Variante absichtlich unentdeckt bleiben soll.
        anmerkung: Begruendung, wenn die Einstufung nicht "ja" ist.

    Returns:
        Den Eintrag.
    """
    return Variantenbezug(
        variante_id=variante_id,
        fehlerklasse=variante_id.partition("-")[0],
        spiegelung=spiegelung,
        erwartete_regeln=regeln,
        erwartet_unentdeckt=unentdeckt,
        anmerkung=anmerkung,
    )


#: Die sechzig Injektionsvarianten mit ihrem Regelbezug (spec/03, Abschnitt 2).
#:
#: Reihenfolge wie in der Spezifikation: Klassen aufsteigend, darin die Varianten
#: nach ihrer Kennung. Sie ist die Reihenfolge der Balken in Abbildung 5.
VARIANTENTABELLE: Final[tuple[Variantenbezug, ...]] = (
    # --- F1: Fehlender Wert -------------------------------------------------
    _eintrag("F1-a", Spiegelung.JA, ("R-001",)),
    _eintrag(
        "F1-b",
        Spiegelung.NEIN,
        ("R-001", "R-057"),
        anmerkung=(
            "Der Leerstring ist auf der Rohschicht nicht von einem planmaessig leeren Feld "
            "zu unterscheiden; R-025 meldet ihn deshalb nicht. Erkennbar nur ueber die "
            "Pflichtfeldregeln. Informationsverlust der Serialisierung, kein Mangel."
        ),
    ),
    _eintrag(
        "F1-c",
        Spiegelung.NEIN,
        ("R-025",),
        anmerkung="Sentinelwert; R-025 prueft eine Platzhalterliste, nicht das Fehlen selbst.",
    ),
    _eintrag(
        "F1-d",
        Spiegelung.NEIN,
        ("R-025",),
        anmerkung="Sentinelwert; R-025 prueft eine Platzhalterliste, nicht das Fehlen selbst.",
    ),
    _eintrag(
        "F1-e",
        Spiegelung.NEIN,
        ("R-025",),
        anmerkung="Numerisches Sentinel; nur auffindbar, wenn es in der Platzhalterliste steht.",
    ),
    _eintrag(
        "F1-f",
        Spiegelung.NEIN,
        ("R-025",),
        anmerkung="Datums-Sentinel; nur auffindbar, wenn es in der Platzhalterliste steht.",
    ),
    # --- F2: Format und Syntax ---------------------------------------------
    _eintrag(
        "F2-a",
        Spiegelung.TEILWEISE,
        ("R-002",),
        anmerkung=(
            "Die Laengenbedingung von R-002 wird nur verletzt, wenn die Postleitzahl mit "
            "einer Null beginnt; sonst bleibt der Wert formal gueltig."
        ),
    ),
    _eintrag("F2-b", Spiegelung.JA, ("R-002",)),
    _eintrag("F2-c", Spiegelung.JA, ("R-004",)),
    _eintrag("F2-d", Spiegelung.JA, ("R-003",)),
    _eintrag("F2-e", Spiegelung.JA, ("R-005",)),
    _eintrag("F2-f", Spiegelung.JA, ("R-009",)),
    _eintrag("F2-g", Spiegelung.JA, ("R-009",)),
    _eintrag(
        "F2-h",
        Spiegelung.NEIN,
        ("R-008",),
        anmerkung="Fremdformat aus einer anderen Schnittstelle; keine Regel zielt darauf.",
    ),
    _eintrag(
        "F2-i",
        Spiegelung.NEIN,
        ("R-008",),
        anmerkung="Excel-Serial; keine Regel zielt auf diese Darstellung.",
    ),
    _eintrag("F2-j", Spiegelung.JA, ("R-007",)),
    _eintrag(
        "F2-k",
        Spiegelung.TEILWEISE,
        ("R-007",),
        anmerkung=(
            "Kleinbuchstaben in der TSN; die Musterbedingung schliesst sie nicht "
            "ausdruecklich aus, sondern nur ueber die Zeichenklasse."
        ),
    ),
    _eintrag("F2-l", Spiegelung.JA, ("R-006",)),
    # --- F3: Wertebereich und Katalog --------------------------------------
    _eintrag("F3-a", Spiegelung.JA, ("R-014",)),
    _eintrag("F3-b", Spiegelung.JA, ("R-014",)),
    _eintrag(
        "F3-c",
        Spiegelung.NEIN,
        ("R-013",),
        anmerkung="Typfehler statt Bereichsfehler; die Bereichsregel greift nicht.",
    ),
    _eintrag("F3-d", Spiegelung.JA, ("R-010",)),
    _eintrag("F3-e", Spiegelung.JA, ("R-010",)),
    _eintrag("F3-f", Spiegelung.JA, ("R-016",)),
    _eintrag(
        "F3-g",
        Spiegelung.NEIN,
        ("R-011",),
        anmerkung="Darstellungswechsel der SF-Klasse; keine Bereichsregel zielt darauf.",
    ),
    _eintrag("F3-h", Spiegelung.JA, ("R-017",)),
    _eintrag("F3-i", Spiegelung.JA, ("R-015",)),
    # --- F4: Fachlich unmoeglich -------------------------------------------
    _eintrag("F4-a", Spiegelung.JA, ("R-026",)),
    _eintrag("F4-b", Spiegelung.JA, ("R-023",)),
    _eintrag("F4-c", Spiegelung.JA, ("R-022",)),
    _eintrag(
        "F4-d",
        Spiegelung.JA,
        ("R-022",),
        anmerkung="Grenzfall knapp unterhalb der Schwelle.",
    ),
    _eintrag("F4-e", Spiegelung.JA, ("R-038",)),
    _eintrag("F4-f", Spiegelung.JA, ("R-024",)),
    _eintrag("F4-g", Spiegelung.JA, ("R-021",)),
    # --- F5: Intra-Record-Inkonsistenz -------------------------------------
    _eintrag("F5-a", Spiegelung.JA, ("R-031",)),
    _eintrag("F5-b", Spiegelung.JA, ("R-032", "R-033")),
    _eintrag("F5-c", Spiegelung.JA, ("R-033",)),
    _eintrag(
        "F5-d",
        Spiegelung.JA,
        ("R-031",),
        anmerkung="Grenzfall knapp oberhalb der Toleranz von R-031.",
    ),
    _eintrag(
        "F5-e",
        Spiegelung.NEIN,
        (),
        unentdeckt=True,
        anmerkung=(
            "Liegt innerhalb der Toleranz von R-031 und soll unentdeckt bleiben; die "
            "Variante prueft, ob die Toleranzgrenze korrekt implementiert ist."
        ),
    ),
    _eintrag("F5-f", Spiegelung.JA, ("R-029",)),
    _eintrag("F5-g", Spiegelung.JA, ("R-039",)),
    _eintrag("F5-h", Spiegelung.JA, ("R-042",)),
    _eintrag("F5-i", Spiegelung.JA, ("R-035",)),
    # --- F6: Exakte Duplikate ----------------------------------------------
    _eintrag("F6-a", Spiegelung.JA, ("R-043", "R-045")),
    _eintrag("F6-b", Spiegelung.JA, ("R-043",)),
    _eintrag("F6-c", Spiegelung.JA, ("R-045",)),
    _eintrag("F6-d", Spiegelung.JA, ("R-046",)),
    # --- F7: Aktualitaet ----------------------------------------------------
    _eintrag("F7-a", Spiegelung.JA, ("R-055",)),
    _eintrag("F7-b", Spiegelung.JA, ("R-055",)),
    _eintrag("F7-c", Spiegelung.JA, ("R-056",)),
    _eintrag(
        "F7-d",
        Spiegelung.NEIN,
        (),
        unentdeckt=True,
        anmerkung="Das Feld tarifgeneration wird von keiner Regel geprueft; erwartet unentdeckt.",
    ),
    # --- F8: Einheiten und Repraesentation ---------------------------------
    _eintrag("F8-a", Spiegelung.JA, ("R-052",)),
    _eintrag("F8-b", Spiegelung.JA, ("R-053",)),
    _eintrag("F8-c", Spiegelung.JA, ("R-053",)),
    _eintrag("F8-d", Spiegelung.JA, ("R-054",)),
    _eintrag(
        "F8-e",
        Spiegelung.NEIN,
        (),
        unentdeckt=True,
        anmerkung=(
            "R-054 prueft gegen den Median der uebrigen Angebote; skaliert man alle "
            "Angebote einer Anfrage, wandert der Median mit. Strukturelle Grenze "
            "relationaler Plausibilitaetspruefung, erwartet unentdeckt."
        ),
    ),
    # --- HO1 / HO2: Held-out ------------------------------------------------
    _eintrag(
        "HO1-a",
        Spiegelung.NEIN,
        (),
        unentdeckt=True,
        anmerkung="Held-out: unscharfe Dublette; der Katalog kennt nur exakte Duplikate.",
    ),
    _eintrag(
        "HO1-b",
        Spiegelung.NEIN,
        (),
        unentdeckt=True,
        anmerkung="Held-out: Tippfehler im Vornamen; keine Regel prueft Namensaehnlichkeit.",
    ),
    _eintrag(
        "HO2-a",
        Spiegelung.NEIN,
        (),
        unentdeckt=True,
        anmerkung=(
            "Held-out: die ersetzte Postleitzahl existiert und der Ort wird mitgezogen; "
            "der Datensatz bleibt in sich stimmig."
        ),
    ),
    _eintrag(
        "HO2-b",
        Spiegelung.NEIN,
        (),
        unentdeckt=True,
        anmerkung=(
            "Held-out: kohaerente Senkung um 15 Prozent; R-031, R-032 und R-036 bleiben "
            "erfuellt, der Wert bleibt im plausiblen Korridor."
        ),
    ),
)

#: Kennungen aller Varianten in der Reihenfolge der Spezifikation.
ALLE_VARIANTEN_IDS: Final[tuple[str, ...]] = tuple(
    eintrag.variante_id for eintrag in VARIANTENTABELLE
)

#: Die Tabelle nach Kennung adressierbar.
VARIANTE_JE_ID: Final[Mapping[str, Variantenbezug]] = MappingProxyType(
    {eintrag.variante_id: eintrag for eintrag in VARIANTENTABELLE}
)


def variantenbezug(variante_id: str) -> Variantenbezug:
    """Gibt den Regelbezug einer Injektionsvariante zurueck.

    Args:
        variante_id: Kennung der Variante, etwa ``"F7-c"``.

    Returns:
        Den Eintrag der Variantentabelle.

    Raises:
        KeyError: Bei einer unbekannten Kennung. Bewusst kein Ersatzeintrag: Eine
            Variante ohne Regelbezug erschiene in Abbildung 5 als "spiegelt
            nicht" und waere dort von einem echten Befund nicht zu unterscheiden.
    """
    if variante_id not in VARIANTE_JE_ID:
        raise KeyError(
            f"Unbekannte injektor_variante_id: {variante_id!r}. Bekannt sind die "
            f"{len(ALLE_VARIANTEN_IDS)} Varianten aus spec/03, Abschnitt 2."
        )
    return VARIANTE_JE_ID[variante_id]


def klasse_je_variante() -> Mapping[str, str]:
    """Gibt je Variantenkennung ihre Fehlerklasse zurueck.

    Returns:
        Die Abbildung Variante auf Klasse, zum Beispiel ``"F3-d"`` auf ``"F3"``.
    """
    return MappingProxyType(
        {eintrag.variante_id: eintrag.fehlerklasse for eintrag in VARIANTENTABELLE}
    )
