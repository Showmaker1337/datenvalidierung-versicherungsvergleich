"""Gegenschnitt B3b — dieselben Regelinhalte in Great Expectations.

Warum es dieses Modul gibt
---------------------------

B3 misst das Framework cuallee. Die dort gemessene Diagnoseguete — der Report
nennt Spalte und Verstosszahl, aber weder Zeile noch Ausgangswert — ist eine
Eigenschaft **dieses Werkzeugs**, nicht seiner Gattung. Stuende in der Arbeit
"etablierte Frameworks koennen Fehler nicht auf die Zelle lokalisieren", genuegte
einem Pruefer die Kenntnis von Great Expectations, um die Aussage zu kippen — und
mit ihr die Begruendung des Artefakts.

Dieses Modul nimmt dem Einwand die Spitze, indem es ihn misst. Es legt **neun** Regeln
zusaetzlich in Great Expectations vor — sieben aus G1 und zwei aus G3 — und erhebt
dieselben vier Kennzahlen wie B3. Aus einer Verteidigung gegen einen moeglichen
Einwand wird damit ein eigener Befund ueber den **Gestaltungsraum** der Werkzeuge.

Was dieses Modul **nicht** ist
-------------------------------

Keine dritte Baseline. Es tritt nicht im Evaluator an, taucht in keiner
Konfusionsmatrix auf und traegt wie B3 ``in_inferenzstatistik = False``. Die
Auswahl ist bewusst klein und nach einem Kriterium getroffen, nicht nach
Bequemlichkeit. Aus **G1** sind es die beiden Regeln, an denen cuallee scheitert
(R-004 Pruefziffer, R-009 realer Kalendertag), die Regel mit bedingter Struktur
(R-001) und vier, die cuallee glatt formuliert (R-002, R-010, R-014, R-021) —
damit sind genau die Stellen abgedeckt, an denen sich die beiden Frameworks
unterscheiden koennen.

Aus **G3** kommen R-046 und R-054 hinzu. Sie messen den **strukturellen Kern** der
Grenze, der die Begruendung des Artefakts traegt: eine satzuebergreifende Bedingung
je Gruppe und eine Bedingung gegen ein Aggregat der uebrigen Zeilen derselben
Gruppe. Ohne sie stuende die zentrale Aussage der Arbeit auf einem Formargument
statt auf einer Messung.

Das Ergebnis, und warum es die Hauptaussage praezisiert
-------------------------------------------------------

Auf den sieben G1-Regeln formuliert Great Expectations **sechs**, cuallee **vier**. Die
beiden Unterschiede sind keine Zufaelle, sondern zwei benennbare Faehigkeiten:

* **``row_condition``** (mit ``condition_parser="pandas"``) macht eine Erwartung
  von einem anderen Feld derselben Zeile abhaengig. Damit ist R-001 in seiner
  bedingten Form — ``anrede`` ungleich FIRMA erzwingt ein ``geburtsdatum`` —
  vollstaendig formulierbar. In cuallee ist sie es nicht; dort bleibt nur der
  unbedingte Teil.
* **``ExpectColumnValuesToMatchStrftimeFormat``** parst den Wert wirklich, statt
  ihn gegen ein Muster zu halten. Damit faellt der 31. Februar auf, und R-009 ist
  formulierbar. In cuallee erkennt ``has_pattern`` acht Ziffern, aber keinen
  Kalender.

**Beide scheitern an R-004.** Eine Pruefziffer nach ISO 7064 Mod 97-10 ist ein
Algorithmus, kein Praedikat ueber einen Spaltenwert. Beide Frameworks bieten dafuer
eine Auffangtuer — ``is_custom`` in cuallee, eine eigene Expectation-Klasse in
Great Expectations —, aber wer sie benutzt, schreibt die Pruefung selbst und misst
nur noch, wo er sie hingeschrieben hat.

**Folge fuer die Arbeit, und sie ist unbequem.** Die Kennzahl "Anteil
ausdrueckbarer Regeln" ist damit **nicht** frameworkunabhaengig, wie es der
B3-Befund allein nahelegt. Sie ist fuer cuallee gemessen; Great Expectations liegt
auf denselben Regeln hoeher. Frameworkuebergreifend belastbar ist nur der **Kern**
der Grenze, und der liegt nicht bei den bedingten Regeln, sondern bei drei anderen
Gruppen:

* **relationale Regeln** ueber mehrere Zeilen einer Tabelle — R-043 bis R-048,
  R-052, R-054. **Nachgemessen an R-046 und R-054:** Keines der 57
  GE-Erwartungen und keines der cuallee-Praedikate traegt "Group" oder "Partition"
  im Namen; Aggregate gibt es nur ueber die ganze Spalte beziehungsweise den ganzen
  Batch. Ein Pruefmodell aus zeilen- und spaltenweisen Praedikaten ueber **eine**
  Tabelle kennt keine Gruppierung mit Rueckbezug auf die Gruppe. Die einzige
  Teilausnahme: Great Expectations formuliert mit ``row_condition`` die Haelfte von
  R-046 ("hoechstens ein VN je Anfrage"); die andere Haelfte braucht eine zweite
  Tabelle. R-044 liesse sich nur durch eine eigene Erwartung **je Anfrage**
  nachbilden — zehntausend Erwartungen statt einer Regel, also kein Ausdruecken,
  sondern ein Ausrollen.
* **quellen- und relationsuebergreifende Regeln** — R-049 bis R-051, R-055 bis
  R-058. Sie brauchen zwei Tabellen gleichzeitig.
* **algorithmische Regeln** — R-004.

Das sind 16 der 58 Regeln allein in den Gruppen G3 bis G5, und sie bleiben beiden
Frameworks verschlossen. Die Arbeit soll deshalb die 36,2 Prozent **als fuer
cuallee gemessen** ausweisen und die frameworkunabhaengige Aussage an dieser
Struktur festmachen, nicht an der einen Zahl.

Der Import von Great Expectations und die Warnungsfilter
---------------------------------------------------------

``great_expectations`` gibt beim Import eine ``ChangedInMarshmallow4Warning`` aus,
und das Projekt laesst ``pytest`` mit ``filterwarnings = ["error"]`` laufen. Der
Import steht deshalb in :func:`_lade_gx` unter einem **lokal** begrenzten
Warnungsfilter — nur um die Importanweisung herum, nicht um unseren eigenen Code.
Ein Eintrag in ``pyproject.toml`` waere die schlechtere Loesung: Er wuerde die
Warnungen des gesamten Projekts stummschalten, um eine Warnung eines Fremdpakets
zu unterdruecken.

Der Import ist ausserdem **traege**: ``great_expectations`` zieht siebzehn Pakete
nach und braucht spuerbar Zeit. ``import src.baselines.b3b_great_expectations``
bleibt dadurch billig, und die uebrige Testsuite zahlt nichts fuer ein Modul, das
sie nicht benutzt.
"""

from __future__ import annotations

import time
import warnings
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

import pandas as pd

from src.baselines.codezeilen import codezeilen_je_regel
from src.common import wertebereiche as wb
from src.common.enums import Anrede, Zahlweise
from src.common.serialisierung import LEER_ROH

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping
    from pathlib import Path

    from src.evaluation.modell import Kontext

__all__ = [
    "DATEI_B3B",
    "DIAGNOSEGUETE_GE",
    "G1_REGELN",
    "GE_REGELN",
    "MUSTER_B3B",
    "GEBericht",
    "GEFehler",
    "GEVergleich",
    "GeprueftRegel",
    "ge_katalog",
]


class GEFehler(RuntimeError):
    """Der Gegenschnitt ist nicht durchfuehrbar."""


#: Quelldatei dieses Moduls — Bezugspunkt der Aufwandsmessung.
DATEI_B3B: Final[str] = "src/baselines/b3b_great_expectations.py"

#: Namensmuster der Regelfunktionen dieses Moduls, zum Beispiel ``_r009``.
MUSTER_B3B: Final[str] = r"^_r(\d{3})$"

#: Was der Report von Great Expectations ueber einen Fund aussagt.
#:
#: Gegenstueck zu :data:`src.baselines.b3_framework.DIAGNOSEGUETE`. Der
#: Unterschied in den Zeilen ``zeile`` und ``ausgangswert`` ist der eigentliche
#: Gegenschnitt: Mit ``result_format: COMPLETE`` und
#: ``unexpected_index_column_names`` liefert ``unexpected_index_list`` je
#: fehlgeschlagener Zeile ein Woerterbuch aus Zeilenkennung und fehlerhaftem Wert,
#: dazu ``unexpected_index_query`` als nachvollziehbare Abfrage.
DIAGNOSEGUETE_GE: Final[Mapping[str, bool]] = MappingProxyType(
    {
        "zeile": True,
        "spalte": True,
        "ausgangswert": True,
        "regel": True,
        "anzahl_verstoesse": True,
    }
)

#: Spaltenname der Zeilenkennung, die Great Expectations mitfuehren soll.
_ROW_ID: Final[str] = "row_id"

#: Ausgabeformat, das den Zeilen- und Wertbezug ueberhaupt erst erzeugt.
#:
#: Ohne ``result_format: COMPLETE`` liefert Great Expectations nur eine
#: Teilliste der auffaelligen Werte und **keine** Zeilenkennung; ohne
#: ``unexpected_index_column_names`` faellt der Bezug auf den Positionsindex
#: zurueck, der nach einer Filterung nicht mehr stabil ist.
_ERGEBNISFORMAT: Final[Mapping[str, Any]] = MappingProxyType(
    {"result_format": "COMPLETE", "unexpected_index_column_names": [_ROW_ID]}
)

#: Die vorgelegten Regeln der Gruppe G1 (Attributwertebene).
#:
#: Die uebrigen stammen aus G3 und messen den strukturellen Kern der Grenze.
G1_REGELN: Final[frozenset[str]] = frozenset(
    {"R-001", "R-002", "R-004", "R-009", "R-010", "R-014", "R-021"}
)

#: Rohform eines leeren Wertes als regulaerer Ausdruck.
_LEER_MUSTER: Final[str] = "^$"


def _lade_gx() -> Any:  # noqa: ANN401 - great_expectations liefert keine Typstubs
    """Importiert ``great_expectations`` unter einem lokal begrenzten Warnungsfilter.

    Returns:
        Das Modul ``great_expectations``.

    Raises:
        GEFehler: Wenn das Paket fehlt. Bewusst mit Installationshinweis statt mit
            einem stillen Ueberspringen: Ein fehlendes Vergleichsframework soll in
            der Ergebnistabelle nicht wie ein Messergebnis aussehen.
    """
    with warnings.catch_warnings():
        # Nur um die Importanweisung herum (siehe Modul-Docstring): great_expectations
        # meldet beim Import eine Marshmallow-Deprecation, und das Projekt laesst
        # pytest mit filterwarnings = ["error"] laufen.
        warnings.simplefilter("ignore")
        try:
            import great_expectations as gx  # noqa: PLC0415 - traege und gefiltert
        except ImportError as fehler:  # pragma: no cover - nur ohne installiertes Paket
            raise GEFehler(
                "great_expectations ist nicht installiert. Der Gegenschnitt B3b braucht "
                "es: python -m pip install great_expectations==1.20.0"
            ) from fehler
    return gx


def _fortschritt_aus() -> Any:  # noqa: ANN401 - great_expectations liefert keine Typstubs
    """Baut die Konfiguration, die die Fortschrittsbalken abschaltet.

    Setzt :func:`_lade_gx` voraus: Der Import hier laeuft ohne eigenen
    Warnungsfilter und darf deshalb erst laufen, wenn das Paket schon geladen ist.

    Returns:
        Eine ``ProgressBarsConfig``, die alle Balken abschaltet.
    """
    from great_expectations.data_context.types.base import (  # noqa: PLC0415 - traege
        ProgressBarsConfig,
    )

    return ProgressBarsConfig(globally=False, metric_calculations=False)


# ---------------------------------------------------------------------------
# Die sieben Regeln
# ---------------------------------------------------------------------------


def _r001(gx: Any) -> list[Any]:  # noqa: ANN401
    """Kernpflichtfelder belegt, und bedingt ein ``geburtsdatum`` (R-001)."""
    erwartungen = [
        gx.expectations.ExpectColumnValuesToNotMatchRegex(column=spalte, regex=_LEER_MUSTER)
        for spalte in ("nachname", "plz")
    ]
    erwartungen.append(
        gx.expectations.ExpectColumnValuesToNotMatchRegex(
            column="geburtsdatum",
            regex=_LEER_MUSTER,
            row_condition=f'anrede != "{Anrede.FIRMA.value}"',
            condition_parser="pandas",
        )
    )
    return erwartungen


def _r002(gx: Any) -> list[Any]:  # noqa: ANN401
    """``plz`` besteht aus genau fuenf Ziffern (R-002)."""
    return [gx.expectations.ExpectColumnValuesToMatchRegex(column="plz", regex=r"^$|^\d{5}$")]


def _r009(gx: Any) -> list[Any]:  # noqa: ANN401
    """``geburtsdatum`` ist ein existierender Kalendertag (R-009)."""
    return [
        gx.expectations.ExpectColumnValuesToMatchStrftimeFormat(
            column="geburtsdatum",
            strftime_format="%d%m%Y",
            row_condition='geburtsdatum != ""',
            condition_parser="pandas",
        )
    ]


def _r010(gx: Any) -> list[Any]:  # noqa: ANN401
    """``zahlweise`` steht im Katalog der GDV-Anlage 14 (R-010)."""
    katalog = [LEER_ROH, *(str(int(wert)) for wert in Zahlweise)]
    return [gx.expectations.ExpectColumnValuesToBeInSet(column="zahlweise", value_set=katalog)]


def _r014(gx: Any) -> list[Any]:  # noqa: ANN401
    """Die Typklassen liegen in den Grenzen des GDV-Verzeichnisses (R-014)."""
    grenzen = {
        "typklasse_hp": wb.TYPKLASSE_HP,
        "typklasse_tk": wb.TYPKLASSE_TK,
        "typklasse_vk": wb.TYPKLASSE_VK,
    }
    return [
        gx.expectations.ExpectColumnValuesToBeBetween(
            column=spalte, min_value=float(unten), max_value=float(oben)
        )
        for spalte, (unten, oben) in grenzen.items()
    ]


def _r021(gx: Any) -> list[Any]:  # noqa: ANN401
    """Beitrags- und Summenfelder sind nicht negativ (R-021)."""
    return [
        gx.expectations.ExpectColumnValuesToBeBetween(column=spalte, min_value=0.0)
        for spalte in ("nettobeitrag_jahr_eur", "bruttobeitrag_jahr_eur")
    ]


@dataclass(frozen=True, slots=True)
class GeprueftRegel:
    """Eine der sieben vorgelegten Regeln.

    Attributes:
        regel_id: Kennung, zum Beispiel ``"R-009"``.
        entitaet: Entitaet, auf der die Erwartungen laufen.
        sicht: ``"raw"`` oder ``"numerisch"``.
        spalten: Die geprueften Spalten. Sie stehen hier, weil die numerische
            Sicht **nur** diese Spalten nach ``float`` wandeln darf — ein
            entitaetsweiter Wandlungsversuch scheiterte an den UUID-Schluesseln.
        ausdruckbar: Ob Great Expectations die Regel **vollstaendig** formuliert.
        begruendung: Warum sie es tut oder nicht tut.
        cuallee_ausdruckbar: Wie B3 dieselbe Regel einordnet — die zweite Spalte
            der Vergleichstabelle.
        erwartungen: Baut die Erwartungen; ``None``, wenn nicht formulierbar.
    """

    regel_id: str
    entitaet: str
    sicht: str
    spalten: tuple[str, ...]
    ausdruckbar: bool
    begruendung: str
    cuallee_ausdruckbar: str
    erwartungen: Any = None


#: Die sieben vorgelegten Regeln, in Kennungsreihenfolge.
GE_REGELN: Final[tuple[GeprueftRegel, ...]] = (
    GeprueftRegel(
        regel_id="R-001",
        entitaet="person",
        sicht="raw",
        spalten=("nachname", "plz", "geburtsdatum", "anrede"),
        ausdruckbar=True,
        begruendung=(
            "Vollstaendig formulierbar. row_condition mit condition_parser='pandas' macht "
            "die Erwartung vom Wert eines anderen Feldes derselben Zeile abhaengig; damit "
            "ist auch der bedingte Teil (anrede ungleich FIRMA erzwingt ein geburtsdatum) "
            "abgedeckt. Genau das kann cuallee nicht."
        ),
        cuallee_ausdruckbar="teilweise",
        erwartungen=_r001,
    ),
    GeprueftRegel(
        regel_id="R-002",
        entitaet="person",
        sicht="raw",
        spalten=("plz",),
        ausdruckbar=True,
        begruendung="Musterpruefung ueber ExpectColumnValuesToMatchRegex; in beiden glatt.",
        cuallee_ausdruckbar="ja",
        erwartungen=_r002,
    ),
    GeprueftRegel(
        regel_id="R-004",
        entitaet="zahlung",
        sicht="raw",
        spalten=("iban",),
        ausdruckbar=False,
        begruendung=(
            "Nicht formulierbar. Die Pruefziffer nach ISO 7064 Mod 97-10 ist ein "
            "Algorithmus ueber den Wert, kein Praedikat aus dem Vorrat der Erwartungen. "
            "Eine eigene Expectation-Klasse waere die Auffangtuer — dann misst man aber "
            "die selbst geschriebene Pruefung und nicht mehr das Framework. cuallee "
            "scheitert mit is_custom an derselben Stelle."
        ),
        cuallee_ausdruckbar="nein",
    ),
    GeprueftRegel(
        regel_id="R-009",
        entitaet="person",
        sicht="raw",
        spalten=("geburtsdatum",),
        ausdruckbar=True,
        begruendung=(
            "Vollstaendig formulierbar. ExpectColumnValuesToMatchStrftimeFormat parst den "
            "Wert wirklich, statt ihn gegen ein Muster zu halten; der 31. Februar faellt "
            "damit auf. In cuallee erkennt has_pattern acht Ziffern, aber keinen Kalender."
        ),
        cuallee_ausdruckbar="nein",
        erwartungen=_r009,
    ),
    GeprueftRegel(
        regel_id="R-010",
        entitaet="anfrage",
        sicht="raw",
        spalten=("zahlweise",),
        ausdruckbar=True,
        begruendung="Katalogpruefung ueber ExpectColumnValuesToBeInSet; in beiden glatt.",
        cuallee_ausdruckbar="ja",
        erwartungen=_r010,
    ),
    GeprueftRegel(
        regel_id="R-014",
        entitaet="risiko_kfz",
        sicht="numerisch",
        spalten=("typklasse_hp", "typklasse_tk", "typklasse_vk"),
        ausdruckbar=True,
        begruendung=(
            "Bereichspruefung ueber ExpectColumnValuesToBeBetween. Wie cuallee verlangt "
            "auch Great Expectations dafuer Zahlenspalten; die Wandlung Decimal nach float "
            "ist in beiden Frameworks dieselbe Reibung."
        ),
        cuallee_ausdruckbar="ja",
        erwartungen=_r014,
    ),
    GeprueftRegel(
        regel_id="R-021",
        entitaet="angebot",
        sicht="numerisch",
        spalten=("nettobeitrag_jahr_eur", "bruttobeitrag_jahr_eur"),
        ausdruckbar=True,
        begruendung="Untergrenze ueber ExpectColumnValuesToBeBetween; in beiden glatt.",
        cuallee_ausdruckbar="ja",
        erwartungen=_r021,
    ),
    # --- Der strukturelle Kern: zwei Regeln aus G3 mit Gruppenbezug ----------
    GeprueftRegel(
        regel_id="R-046",
        entitaet="person",
        sicht="raw",
        spalten=("anfrage_id", "rolle"),
        ausdruckbar=False,
        begruendung=(
            "Nur zur Haelfte formulierbar, und deshalb hier als nicht ausdrueckbar "
            "gefuehrt. 'Hoechstens ein VN je Anfrage' geht in Great Expectations ueber "
            "row_condition='rolle == \"VN\"' plus ExpectColumnValuesToBeUnique auf "
            "anfrage_id — nachgemessen. 'Mindestens einer' braucht dagegen die Tabelle "
            "anfrage und damit einen zweiten Batch; eine Erwartung sieht immer nur einen. "
            "cuallee kennt keine row_condition und schafft auch die erste Haelfte nicht: "
            "is_unique('anfrage_id') prueft die Spalte als Ganzes, nicht die auf VN "
            "gefilterte Teilmenge."
        ),
        cuallee_ausdruckbar="nein",
    ),
    GeprueftRegel(
        regel_id="R-054",
        entitaet="angebot",
        sicht="numerisch",
        spalten=("zahlbeitrag_rate_eur",),
        ausdruckbar=False,
        begruendung=(
            "In keinem der beiden Frameworks formulierbar, und das ist der Kern der "
            "Grenze. Die Regel vergleicht einen Wert mit dem Median der **uebrigen** "
            "Angebote **derselben Anfrage**. Beide Werkzeuge kennen Aggregate nur ueber "
            "die ganze Spalte beziehungsweise den ganzen Batch — cuallee has_percentile, "
            "Great Expectations ExpectColumnMedianToBeBetween. Keines von 57 "
            "GE-Erwartungen und keines der cuallee-Praedikate traegt 'Group' oder "
            "'Partition' im Namen. Ein Pruefmodell aus zeilen- und spaltenweisen "
            "Praedikaten ueber eine Tabelle kennt keine Gruppierung mit Rueckbezug auf "
            "die Gruppe."
        ),
        cuallee_ausdruckbar="nein",
    ),
)


def ge_katalog() -> tuple[GeprueftRegel, ...]:
    """Gibt die vorgelegten Regeln zurueck."""
    return GE_REGELN


# ---------------------------------------------------------------------------
# Bericht
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GEBericht:
    """Die vier Kennzahlen des Gegenschnitts.

    Attributes:
        ausdrueckbar: Regeln, die Great Expectations vollstaendig formuliert.
        nicht_ausdrueckbar: Regeln, die es nicht formuliert.
        anteil_ausdrueckbar: Anteil an den vorgelegten **G1**-Regeln.
        anteil_ausdrueckbar_g3: Anteil an den vorgelegten **G3**-Regeln — dem
            strukturellen Kern, an dem beide Frameworks scheitern.
        anteil_cuallee_g3: Dasselbe fuer cuallee.
        cuallee_ausdrueckbar: Dieselben Regeln in der Einordnung von B3.
        anteil_cuallee: Anteil der in cuallee **vollstaendig** formulierbaren.
        codezeilen: Anweisungszeilen je Regel in diesem Modul.
        laufzeit_s: Laufzeit der Validierung.
        diagnoseguete: :data:`DIAGNOSEGUETE_GE`.
        beispiel_lokalisierung: Ein echter Eintrag aus ``unexpected_index_list``.
            Er belegt den Zeilen- und Wertbezug am Messwert statt an der Behauptung.
        verstoesse_je_regel: Zahl der gefundenen Verstoesse je Regel.
    """

    ausdrueckbar: tuple[str, ...]
    nicht_ausdrueckbar: tuple[str, ...]
    anteil_ausdrueckbar: float
    anteil_ausdrueckbar_g3: float
    cuallee_ausdrueckbar: Mapping[str, str]
    anteil_cuallee: float
    anteil_cuallee_g3: float
    codezeilen: Mapping[str, int]
    laufzeit_s: float
    diagnoseguete: Mapping[str, bool]
    beispiel_lokalisierung: Mapping[str, Any] | None
    verstoesse_je_regel: Mapping[str, int]

    def als_dict(self) -> dict[str, Any]:
        """Baut die JSON-taugliche Form, ohne Zeitstempel (Architekturregel A2)."""
        return {
            "vorgelegte_regeln": [eintrag.regel_id for eintrag in GE_REGELN],
            "ausdrueckbar": list(self.ausdrueckbar),
            "nicht_ausdrueckbar": list(self.nicht_ausdrueckbar),
            "anteil_ausdrueckbar_g1": round(self.anteil_ausdrueckbar, 6),
            "anteil_ausdrueckbar_g3": round(self.anteil_ausdrueckbar_g3, 6),
            "cuallee_zum_vergleich": {
                "einordnung_je_regel": dict(self.cuallee_ausdrueckbar),
                "anteil_vollstaendig_g1": round(self.anteil_cuallee, 6),
                "anteil_vollstaendig_g3": round(self.anteil_cuallee_g3, 6),
            },
            "codezeilen_je_regel": dict(self.codezeilen),
            "codezeilen_summe": sum(self.codezeilen.values()),
            "laufzeit_s": round(self.laufzeit_s, 6),
            "diagnoseguete": dict(self.diagnoseguete),
            "beispiel_lokalisierung": (
                dict(self.beispiel_lokalisierung)
                if self.beispiel_lokalisierung is not None
                else None
            ),
            "verstoesse_je_regel": dict(self.verstoesse_je_regel),
            "begruendungen": {eintrag.regel_id: eintrag.begruendung for eintrag in GE_REGELN},
        }


# ---------------------------------------------------------------------------
# Der Gegenschnitt
# ---------------------------------------------------------------------------


class GEVergleich:
    """Fuehrt die sieben Regeln in Great Expectations aus.

    Kein Verfahren im Sinne des Evaluators: Die Klasse erfuellt das Protokoll
    absichtlich nicht und tritt in keiner Konfusionsmatrix an. Sie liefert die
    zweite Spalte der Frameworkvergleichstabelle.
    """

    #: Wie B3 nicht Teil der Inferenzstatistik (siehe Modul-Docstring).
    in_inferenzstatistik: bool = False

    def __init__(self) -> None:
        """Legt den Gegenschnitt an."""
        self._verstoesse: dict[str, int] = {}
        self._beispiel: dict[str, Any] | None = None

    def _rahmen(self, kontext: Kontext, eintrag: GeprueftRegel) -> pd.DataFrame:
        """Baut die Sicht, auf der eine Regel laeuft.

        Die numerische Sicht wandelt die geprueften Spalten nach ``float``. Das ist
        dieselbe Framework-Reibung wie bei cuallee: Beide Werkzeuge pruefen
        Zahlenpraedikate nur auf Zahlenspalten, das Projekt fuehrt Geld aber als
        ``Decimal`` (CLAUDE.md, Abschnitt 5).

        Args:
            kontext: Pruefkontext ueber beide Datenschichten.
            eintrag: Die auszufuehrende Regel.

        Returns:
            Den Datenrahmen mit ``row_id`` als Zeichenkette.
        """
        from src.common.pfade import Schicht  # noqa: PLC0415 - vermeidet Zyklus im Modulkopf

        if eintrag.sicht == "raw":
            roh = kontext.rahmen(Schicht.RAW, eintrag.entitaet)
            return roh.astype("object").fillna(LEER_ROH).astype(str)

        typisiert = kontext.rahmen(Schicht.TYPED, eintrag.entitaet)
        spalten: dict[str, Any] = {_ROW_ID: [str(wert) for wert in typisiert[_ROW_ID]]}
        # Nur die geprueften Spalten wandeln: Ein entitaetsweiter Versuch scheitert
        # an den UUID-Schluesseln, und eine stille Ausnahmebehandlung wuerde eine
        # nicht wandelbare Zahlenspalte ebenso verschlucken.
        for name in eintrag.spalten:
            if name not in typisiert.columns:
                continue
            spalten[name] = pd.array(
                [
                    None if wert is None or pd.isna(wert) else float(wert)
                    for wert in typisiert[name]
                ],
                dtype="float64",
            )
        return pd.DataFrame(spalten)

    def pruefe(self, kontext: Kontext) -> GEBericht:
        """Fuehrt die sieben Regeln aus und erhebt die vier Kennzahlen.

        Args:
            kontext: Pruefkontext ueber beide Datenschichten des zu pruefenden
                Datensatzes.

        Returns:
            Den :class:`GEBericht`.

        Raises:
            GEFehler: Wenn ``great_expectations`` fehlt.
        """
        gx = _lade_gx()
        self._verstoesse = {}
        self._beispiel = None

        beginn = time.perf_counter()
        with warnings.catch_warnings():
            # Great Expectations meldet waehrend der Validierung Deprecations aus
            # marshmallow und pandas; sie gehoeren dem Fremdpaket, nicht diesem Projekt.
            warnings.simplefilter("ignore")
            for eintrag in GE_REGELN:
                if eintrag.erwartungen is None:
                    continue
                self._verstoesse[eintrag.regel_id] = self._fuehre_aus(gx, kontext, eintrag)
        laufzeit = time.perf_counter() - beginn

        ausdrueckbar = tuple(e.regel_id for e in GE_REGELN if e.ausdruckbar)
        nicht = tuple(e.regel_id for e in GE_REGELN if not e.ausdruckbar)
        # Getrennt nach Regelgruppe: Die G1-Quote misst, wie weit die Werkzeuge auf
        # Attributwertebene auseinanderliegen; die G3-Quote misst den strukturellen
        # Kern, an dem beide scheitern. Eine gemeinsame Quote ueber alle neun Regeln
        # mischte die beiden Aussagen und liesse die zweite verschwinden.
        g1 = tuple(e for e in GE_REGELN if e.regel_id in G1_REGELN)
        g3 = tuple(e for e in GE_REGELN if e.regel_id not in G1_REGELN)

        return GEBericht(
            ausdrueckbar=ausdrueckbar,
            nicht_ausdrueckbar=nicht,
            anteil_ausdrueckbar=sum(e.ausdruckbar for e in g1) / len(g1),
            anteil_ausdrueckbar_g3=sum(e.ausdruckbar for e in g3) / len(g3),
            cuallee_ausdrueckbar={e.regel_id: e.cuallee_ausdruckbar for e in GE_REGELN},
            anteil_cuallee=sum(e.cuallee_ausdruckbar == "ja" for e in g1) / len(g1),
            anteil_cuallee_g3=sum(e.cuallee_ausdruckbar == "ja" for e in g3) / len(g3),
            codezeilen=self.codezeilen(),
            laufzeit_s=laufzeit,
            diagnoseguete=DIAGNOSEGUETE_GE,
            beispiel_lokalisierung=self._beispiel,
            verstoesse_je_regel=dict(sorted(self._verstoesse.items())),
        )

    def _fuehre_aus(self, gx: Any, kontext: Kontext, eintrag: GeprueftRegel) -> int:  # noqa: ANN401
        """Validiert eine Regel und merkt sich das erste lokalisierte Beispiel.

        Args:
            gx: Das Modul ``great_expectations``.
            kontext: Pruefkontext.
            eintrag: Die auszufuehrende Regel.

        Returns:
            Die Zahl der gefundenen Verstoesse ueber alle Erwartungen der Regel.
        """
        rahmen = self._rahmen(kontext, eintrag)
        ctx = gx.get_context(mode="ephemeral")
        # Ohne diese Zeile schreibt Great Expectations je Erwartung einen
        # tqdm-Fortschrittsbalken nach stderr. Bei sieben Regeln ueber sieben
        # Entitaeten uebertoent das die eigentliche Ausgabe des Skripts.
        ctx.variables.progress_bars = _fortschritt_aus()
        quelle = ctx.data_sources.add_pandas(f"b3b_{eintrag.regel_id}")
        asset = quelle.add_dataframe_asset(eintrag.entitaet)
        stapel = asset.add_batch_definition_whole_dataframe("ganz").get_batch(
            batch_parameters={"dataframe": rahmen}
        )

        gefunden = 0
        for erwartung in eintrag.erwartungen(gx):
            if erwartung.column not in rahmen.columns:
                continue
            ergebnis = stapel.validate(erwartung, result_format=dict(_ERGEBNISFORMAT))
            teil = ergebnis["result"]
            gefunden += int(teil.get("unexpected_count") or 0)
            treffer = teil.get("unexpected_index_list") or []
            if self._beispiel is None and treffer:
                self._beispiel = {
                    "regel_id": eintrag.regel_id,
                    "entitaet": eintrag.entitaet,
                    "spalte": erwartung.column,
                    "eintrag": dict(treffer[0]),
                    "abfrage": teil.get("unexpected_index_query"),
                }
        return gefunden

    def codezeilen(self) -> dict[str, int]:
        """Misst die Anweisungszeilen je Regelfunktion dieses Moduls.

        Returns:
            Je Regelkennung die Zahl der Zeilen; nicht formulierbare Regeln
            fehlen, weil es zu ihnen keine Funktion gibt.
        """
        from src.common.config import projekt_wurzel  # noqa: PLC0415 - vermeidet Zyklus

        datei: Path = projekt_wurzel() / DATEI_B3B
        return dict(sorted(codezeilen_je_regel(datei, MUSTER_B3B).items()))
