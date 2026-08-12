"""Baseline B3 — dieselben Regelinhalte in der Check-API von cuallee.

B3 beantwortet eine andere Frage als B0 und B2. Dort geht es um die untere
Schranke (reine Schemavalidierung) und um einen ganz anderen Ansatz
(Anomalieerkennung). Hier geht es um den direkten Konkurrenten: Ein etabliertes
Datenqualitaets-Framework bekommt **denselben fachlichen Regelinhalt** vorgelegt
wie der eigene Prototyp — nur die G1-Regeln R-001 bis R-025, also die
Attributwertebene. Gemessen wird nicht, wer mehr findet, sondern **was das
Framework ueber einen Fund sagen kann**, wie viel Quelltext es dafuer braucht und
welche Regeln es ueberhaupt formulieren kann.

Der Regelinhalt ist hier **neu formuliert**, nicht uebernommen: Dieses Modul
importiert nichts aus ``src.rules``. Die fachlichen Konstanten (Kataloge,
Grenzen, Feldlaengen) stammen aus ``src.common`` — sie sind die gemeinsame
Definition des Datenmodells und gehoeren keinem der beiden Verfahren.

Der zentrale Befund: cuallee nennt keine Zeile
----------------------------------------------

``cuallee.pandas_validation.summary`` berechnet je Regel **eine einzige Zahl** —
die Zahl der Zeilen, die das Praedikat erfuellen — und leitet daraus die Zahl der
Verstoesse und eine Bestehensquote ab. Der Report traegt Spalte, Regelname, Wert
des Praedikats, Zeilenzahl, Verstosszahl und Status. Er traegt **keine Zeile und
keinen Ausgangswert**.

Damit ist eine Konfusionsmatrix auf Zell-, Constraint- oder Satzebene nicht
bildbar: Es gibt keine Einheit, die man mit dem Ground Truth schneiden koennte.
:meth:`B3Framework.erkenne` gibt seine Meldungen deshalb mit ``row_id`` gleich
:data:`~src.evaluation.modell.ROW_ID_OHNE_BEZUG` zurueck, und das Verfahren traegt
``lokalisiert_zellen = False``.

**Das ist das Messergebnis der Kennzahl Diagnoseguete, kein Implementierungsmangel
und kein fehlender Wert.** Ein Framework, das "in Spalte ``plz`` sind 412 Werte
falsch" meldet, hat einen Datenqualitaetsbefund geliefert; ein Sachbearbeiter, der
die 412 Faelle korrigieren soll, hat ihn nicht. Genau diese Luecke ist eines der
Ergebnisse der Arbeit, und sie darf in der Auswertung nicht als Null erscheinen,
sondern als "auf dieser Ebene nicht messbar". Wuerde man die Verstosszahlen
irgendeiner Zeile zuschlagen, um doch eine Matrix zu bekommen, misst man die
Zuordnungsheuristik und nicht mehr das Framework.

Aus demselben Grund steht ``in_inferenzstatistik = False``: Ein Wilcoxon-Test
zwischen dem Prototyp und einem Verfahren, das inhaltlich dieselben Regeln
ausfuehrt, pruefte eine Nullhypothese, von der man vorher weiss, dass sie gilt.
Der Vergleich mit B3 ist qualitativ (Ausdrueckbarkeit, Aufwand, Diagnoseguete),
nicht inferenzstatistisch.

Zwei Sichten auf dieselben Daten
--------------------------------

Wie der Prototyp arbeitet auch B3 auf zwei Schichten (``spec/01``, Abschnitt 6):

* Die **Rohsicht** traegt alle Spalten als Zeichenkette. Nur hier sind Muster,
  Sentinels und Kataloge pruefbar; auf der typisierten Schicht sind sie per
  Konstruktion nicht verletzbar.
* Die **numerische Sicht** entsteht aus der typisierten Schicht und traegt die
  Zahlenfelder als ``float``. cuallee vergleicht ueber ``Series.between`` und
  ``Series.ge``; ein ``Decimal`` ist dort kein zulaessiger Typ, und
  ``validate_data_types`` verlangt ausdruecklich ``select_dtypes("number")``.

Die Wandlung ``Decimal`` nach ``float`` ist **Framework-Reibung** und wird als
solche gezaehlt: Das Projekt fuehrt Geld nach CLAUDE.md, Abschnitt 5 grundsaetzlich
als ``Decimal``, weil Betragsvergleiche sonst von Binaerdarstellungen abhaengen. Fuer
B3 muss diese Festlegung aufgegeben werden. Bei den hier gepruefte Groessen
(Mindestdeckungen, Nichtnegativitaet) ist der Genauigkeitsverlust folgenlos; die
Aussage ist, dass das Framework die Festlegung erzwingt, nicht dass sie hier weh
tut.

Der Leerwert muss in jede einzelne Regel eingebaut werden
---------------------------------------------------------

Im Datenmodell ist der Leerstring auf der Rohschicht ein **regulaer leerer** Wert
(``spec/01``, Abschnitt 6). Format- und Katalogregeln duerfen ihn nicht melden;
dafuer sind die Pflichtfeldregeln zustaendig. Der Prototyp erledigt das an einer
Stelle (``_leer`` in ``src/rules/g1_attribut.py``), das Framework kennt einen
solchen Begriff nicht. In cuallee muss die Ausnahme deshalb in **jede** Regel
hineingeschrieben werden:

* jede Musterpruefung bekommt ``^$|`` vorangestellt (:func:`_mit_leer`),
* jede Katalogpruefung bekommt den Leerstring in die erlaubte Menge
  (:func:`_mit_leerwert`),
* jede numerische Pruefung bekommt einen **neutralen Ersatzwert** fuer leere
  Zellen (:func:`_neutralwerte`), weil ``NaN`` bei ``between`` und ``ge`` immer
  ``False`` ergibt und ein planmaessig leeres Feld sonst als Verstoss zaehlte.

Das ist Framework-Reibung und geht in die Aufwandskennzahl ein. Es ist zugleich
eine Fehlerquelle: Wer die Ausnahme in einer von fuenfundzwanzig Regeln vergisst,
bekommt einen Fehlalarm auf jedem planmaessig leeren Feld — im Clean-Baseline-Lauf
waeren das Zehntausende.

Eine Pruefung je Regel und Entitaet
-----------------------------------

``Check.validate`` ist an **genau einen** Datenrahmen gebunden, das Datenmodell hat
aber sieben Entitaeten. Zudem identifiziert der Report eine Regel nur ueber
Methodenname, Spalte und Praedikatwert — nicht ueber unsere Regelkennung. Beides
zusammen fuehrt zu der Entscheidung, je Kombination aus Regel, Entitaet und Sicht
**einen eigenen** :class:`~cuallee.Check` zu bauen. Dann ist die Zuordnung
Reportzeile auf ``regel_id`` exakt und ohne Namensraten, und der Geltungsbereich
einer Regel laesst sich je Entitaet genau festlegen
(:attr:`B3Regel.spalten_je_entitaet`). Der Preis sind rund dreissig
``validate``-Aufrufe statt zweier; gemessen wird er in ``laufzeit_s``.

Der Geltungsbereich je Entitaet ist noetig, weil Spaltennamen mehrfach vorkommen:
``anfrage_id`` steht in sechs Entitaeten, R-001 verlangt es aber nur in
``anfrage``. Eine Filterung allein nach "Spalte vorhanden" wuerde die Regel still
verbreitern.

Was cuallee nicht ausdruecken kann
----------------------------------

Zwei Regeln sind **gar nicht** deklarativ formulierbar:

* **R-004** (IBAN-Pruefziffer nach ISO 7064 Mod 97-10) braucht eine eigene
  Python-Funktion. cuallee bietet dafuer den Ausstieg ``is_custom``; damit wird die
  Regel aber nicht mehr vom Framework formuliert, sondern nur noch von ihm
  aufgerufen. Als "vom Framework ausdrueckbar" zaehlt das nicht.
* **R-009** (jedes Datumsfeld ist ein existierender Kalendertag). Ein Muster
  erkennt acht Ziffern, aber nicht den 31. Februar. Die Datumspraedikate von
  cuallee setzen bereits einen Datumstyp voraus — genau den gibt es auf der
  Rohschicht nicht, und auf der typisierten Schicht ist die Regel nicht mehr
  verletzbar.

Zwei weitere sind **teilweise** ausdrueckbar und zaehlen in der Kennzahl
ausdruecklich **nicht** als ausdrueckbar:

* **R-001**: Der unbedingte Teil (sechs Kernpflichtfelder sind belegt) geht; der
  bedingte Teil ("``anrede`` ungleich FIRMA erzwingt ein ``geburtsdatum``") ist eine
  bedingte funktionale Abhaengigkeit und in einer spaltenweisen Check-API nicht
  formulierbar.
* **R-025**: Die Sentinel-Liste geht; die Feldausnahmen gehen nicht. In
  ``jahresfahrleistung_km`` und in den Sublimit-Feldern ist ``9999`` ein legitimer
  Wert. Weil cuallee diese Ausnahme nicht kennt, bleiben die **numerischen**
  Sentinels hier ganz aussen vor — die Alternative waeren Fehlalarme auf jedem
  legitimen ``9999``. Geprueft werden nur die Text- und Datumssentinels.
  Ausgenommen bleibt ausserdem ``row_id``: Sie ist niemals Ziel einer Injektion
  (Architekturregel A3).

Kein Zeitstempel
----------------

Der cuallee-Report traegt eine Spalte ``timestamp`` mit der Ausfuehrungszeit. Sie
wird verworfen (:data:`_VERWORFENE_SPALTEN`). Ein Zeitstempel in einem
Laufartefakt widerspricht Architekturregel A2: Zwei Laeufe mit demselben Seed
muessen bitgleiche Ausgaben erzeugen, und eine Uhrzeit tut das nie.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from functools import partial
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

import pandas as pd
from cuallee import Check, CheckLevel

from src.baselines.codezeilen import (
    DATEI_B3,
    DATEI_PROTOTYP_G1,
    MUSTER_B3,
    MUSTER_PROTOTYP,
    codezeilen_je_regel,
)
from src.common import wertebereiche as wb
from src.common.enums import (
    BAUARTKLASSEN,
    SF_KLASSEN,
    WAEHRUNG_STANDARD,
    Anfragestatus,
    ArtKennzeichen,
    Nutzungsart,
    Sparte,
    Zahlweise,
)
from src.common.pfade import Schicht
from src.common.serialisierung import (
    ENTITAETEN,
    LEER_ROH,
    SPALTEN_JE_ENTITAET,
)
from src.evaluation.modell import ROW_ID_OHNE_BEZUG, VERSTOSS_SPALTEN

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Callable, Mapping, Sequence
    from decimal import Decimal

    from src.evaluation.modell import Kontext

__all__ = [
    "DIAGNOSEGUETE",
    "REGELN_G1",
    "REGELN_KATALOG",
    "SICHT_KEINE",
    "SICHT_NUMERISCH",
    "SICHT_RAW",
    "B3Bericht",
    "B3Fehler",
    "B3Framework",
    "B3Regel",
    "Pruefung",
    "b3_katalog",
]

#: Ein ``Check`` aus cuallee.
#:
#: cuallee liefert keine Typstubs und traegt keine ``py.typed``-Marke; unter
#: ``disallow_any_unimported`` wuerde jede Annotation mit ``Check`` von mypy
#: beanstandet. Der Alias haelt die Absicht im Quelltext fest — an diesen Stellen
#: steht ein cuallee-``Check`` —, waehrend die Typpruefung ``Any`` sieht. Ein
#: fehlender Stub eines Fremdpakets soll nicht dazu fuehren, dass die Datei
#: unannotiert bleibt.
type Pruefung = Any

#: Bezeichner der Rohsicht (alle Spalten als Zeichenkette).
SICHT_RAW: Final[str] = "raw"

#: Bezeichner der numerischen Sicht (Zahlenfelder als ``float``).
SICHT_NUMERISCH: Final[str] = "numerisch"

#: Bezeichner fuer Regeln, die in cuallee gar nicht formulierbar sind.
SICHT_KEINE: Final[str] = "-"

#: Zahl der Regeln des vollstaendigen Katalogs (``spec/02_regelkatalog.md``).
#:
#: Bewusst eine Konstante und **kein** Import aus ``src.rules``: B3 darf den
#: Regelkatalog nicht kennen. Die Zahl stammt aus der Spezifikation, die nach dem
#: Git-Tag ``freeze-regelkatalog`` unveraendert bleibt (Architekturregel A4).
REGELN_KATALOG: Final[int] = 58

#: Zahl der Regeln der Gruppe G1 (R-001 bis R-025), die B3 vorgelegt bekommt.
REGELN_G1: Final[int] = 25

#: Was der Report von cuallee ueber einen Fund aussagt.
#:
#: Die Kennzahl "Diagnoseguete" der Arbeit in ihrer knappsten Form. ``zeile`` und
#: ``ausgangswert`` sind ``False`` — siehe Modul-Docstring.
DIAGNOSEGUETE: Final[Mapping[str, bool]] = MappingProxyType(
    {
        "zeile": False,
        "spalte": True,
        "ausgangswert": False,
        "regel": True,
        "anzahl_verstoesse": True,
    }
)

#: Spalten des cuallee-Reports, die verworfen werden.
_VERWORFENE_SPALTEN: Final[tuple[str, ...]] = ("timestamp",)

#: Leerer Geltungsbereich; Vorgabe fuer nicht ausdrueckbare Regeln.
_KEIN_GELTUNGSBEREICH: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType({})

#: Ausdrueckbarkeit je Regel, unabhaengig vom Lauf.
#:
#: Bewusst getrennt von :func:`b3_katalog` gefuehrt: Die Registry braucht einen
#: Kontext (Waehrungskatalog, Schwellen, Stichtag), die Ausdrueckbarkeit ist
#: dagegen eine Eigenschaft des Frameworks und gilt fuer jeden Lauf gleich. So
#: bleibt :meth:`B3Framework.bericht` auch ohne geladene Referenzdaten
#: auskunftsfaehig. Die Begruendungen stehen an den Regeln in
#: :func:`_katalog_rohsicht` und :func:`_katalog_numerisch`; beide Quellen sind
#: deckungsgleich zu halten.
_AUSDRUECKBARKEIT: Final[Mapping[str, str]] = MappingProxyType(
    {
        "R-001": "teilweise",
        "R-002": "ja",
        "R-003": "ja",
        "R-004": "nein",
        "R-005": "ja",
        "R-006": "ja",
        "R-007": "ja",
        "R-008": "ja",
        "R-009": "nein",
        "R-010": "ja",
        "R-011": "ja",
        "R-012": "ja",
        "R-013": "ja",
        "R-014": "ja",
        "R-015": "ja",
        "R-016": "ja",
        "R-017": "ja",
        "R-018": "ja",
        "R-019": "ja",
        "R-020": "ja",
        "R-021": "ja",
        "R-022": "ja",
        "R-023": "ja",
        "R-024": "ja",
        "R-025": "teilweise",
    }
)


class B3Fehler(RuntimeError):
    """Die Baseline B3 ist nicht ausfuehrbar oder wurde falsch benutzt.

    Bewusst eine Ausnahme und kein Ersatzwert: Ein leerer Bericht oder eine Null
    in der Aufwandstabelle waere von einem echten Messergebnis nicht zu
    unterscheiden.
    """


# ---------------------------------------------------------------------------
# Bausteine der Regelformulierung
# ---------------------------------------------------------------------------


def _mit_leer(muster: str) -> str:
    """Erlaubt zusaetzlich den leeren Wert in einer Musterpruefung.

    Auf der Rohschicht ist der Leerstring die Darstellung eines regulaer leeren
    Wertes (``spec/01``, Abschnitt 6). Ohne diese Erweiterung meldete jede
    Formatregel jedes planmaessig leere Feld.

    Args:
        muster: Regulaerausdruck, der mit ``^`` beginnt und mit ``$`` endet.

    Returns:
        Den um die leere Alternative erweiterten Ausdruck.
    """
    return f"^$|{muster}"


def _mit_leerwert(katalog: Sequence[str]) -> tuple[str, ...]:
    """Nimmt den leeren Wert in einen Wertekatalog auf.

    Das Gegenstueck zu :func:`_mit_leer` fuer Katalogpruefungen.

    Args:
        katalog: Zulaessige Werte.

    Returns:
        Den Katalog mit vorangestelltem Leerstring, in fester Reihenfolge.
    """
    return (LEER_ROH, *katalog)


#: Postleitzahl: genau fuenf Ziffern, fuehrende Null eingeschlossen (R-002).
_MUSTER_PLZ: Final[str] = rf"^\d{{{wb.PLZ_LAENGE}}}$"

#: Deutsche IBAN: Laenderkennung und zwanzig Ziffern (R-003).
_MUSTER_IBAN: Final[str] = rf"^DE\d{{{wb.IBAN_LAENGE_DE - 2}}}$"

#: BIC: acht **oder** elf Zeichen; neun und zehn existieren nicht (R-005).
_MUSTER_BIC: Final[str] = rf"^.{{{wb.BIC_LAENGEN[0]}}}$|^.{{{wb.BIC_LAENGEN[1]}}}$"

#: Vereinfachtes RFC-5322-Muster (R-006).
#:
#: Bewusst eigenstaendig formuliert und nicht aus dem Prototyp uebernommen: Der
#: Vergleich soll zeigen, wie dieselbe *fachliche* Anforderung im Framework
#: aussieht. Geprueft wird die praxisuebliche Form ``lokalteil@domaene.tld``.
_MUSTER_EMAIL: Final[str] = (
    r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+@[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*\.[A-Za-z]{2,}$"
)

#: Herstellerschluesselnummer: genau vier Ziffern (R-007).
_MUSTER_HSN: Final[str] = rf"^\d{{{wb.HSN_LAENGE}}}$"

#: Typschluesselnummer: drei Grossbuchstaben oder Ziffern (R-008).
_MUSTER_TSN: Final[str] = rf"^[A-Z0-9]{{{wb.TSN_LAENGE}}}$"

#: Belegtes Feld: mindestens ein Zeichen (R-001).
_MUSTER_BELEGT: Final[str] = r"^.+$"

#: Kernpflichtfelder aus R-001 in fester Reihenfolge.
_KERNPFLICHTFELDER: Final[tuple[str, ...]] = (
    "anfrage_id",
    "sparte",
    "eingangszeitpunkt",
    "vn_person_id",
    "nachname",
    "plz",
)

#: Beitrags- und Summenfelder je Entitaet (R-021).
_BEITRAGSFELDER: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "angebot": (
            "nettobeitrag_jahr_eur",
            "versicherungsteuer_satz",
            "versicherungsteuer_eur",
            "bruttobeitrag_jahr_eur",
            "ratenzahlungszuschlag_prozent",
            "zahlbeitrag_rate_eur",
            "sb_tk_eur",
            "sb_vk_eur",
            "sb_hausrat_prozent",
            "sb_hausrat_eur",
        ),
        "risiko_hausrat": (
            "versicherungssumme_eur",
            "sublimit_fahrrad_eur",
            "sublimit_wertsachen_eur",
        ),
        "tarif": (
            "deckungssumme_personen_eur",
            "deckungssumme_sach_eur",
            "deckungssumme_vermoegen_eur",
        ),
    }
)

#: Gesetzliche Mindestdeckungen nach PflVG, Anlage zu Paragraph 4 Absatz 2 (R-024).
_MINDESTDECKUNG: Final[Mapping[str, Decimal]] = MappingProxyType(
    {
        "deckungssumme_personen_eur": wb.PFLVG_MINDESTDECKUNG_PERSONEN_EUR,
        "deckungssumme_sach_eur": wb.PFLVG_MINDESTDECKUNG_SACH_EUR,
        "deckungssumme_vermoegen_eur": wb.PFLVG_MINDESTDECKUNG_VERMOEGEN_EUR,
    }
)

#: Typklassenbereiche des GDV-Typklassenverzeichnisses (R-014).
_TYPKLASSEN: Final[Mapping[str, tuple[int, int]]] = MappingProxyType(
    {
        "typklasse_hp": wb.TYPKLASSE_HP,
        "typklasse_tk": wb.TYPKLASSE_TK,
        "typklasse_vk": wb.TYPKLASSE_VK,
    }
)

#: Regionalklassenbereiche des GDV-Regionalklassenverzeichnisses (R-015).
_REGIONALKLASSEN: Final[Mapping[str, tuple[int, int]]] = MappingProxyType(
    {
        "regionalklasse_hp": wb.REGIONALKLASSE_HP,
        "regionalklasse_tk": wb.REGIONALKLASSE_TK,
        "regionalklasse_vk": wb.REGIONALKLASSE_VK,
    }
)

#: Implizite Fehlwerte, die B3 prueft (R-025, Textteil und Datumsteil).
#:
#: Ohne die numerischen Sentinels: ``9999`` ist in ``jahresfahrleistung_km`` und
#: in den Sublimit-Feldern ein legitimer Wert, und diese Feldausnahme laesst sich
#: in cuallee nicht formulieren (siehe Modul-Docstring).
_SENTINELS: Final[tuple[str, ...]] = (
    *wb.SENTINEL_TEXT_ROHSCHICHT,
    *wb.SENTINEL_DATUM,
)


# ---------------------------------------------------------------------------
# Die Regeln in der Check-API von cuallee
#
# Jede Regel ist eine eigene kleine Funktion. Das ist keine Formfrage: Nur so
# kann src/baselines/codezeilen.py ihren Aufwand ueber den Syntaxbaum objektiv
# messen und dem gleichnamigen ``pruefe_r0xx`` des Prototyps gegenueberstellen.
# ---------------------------------------------------------------------------


def _r001(pruefung: Pruefung) -> Pruefung:
    """Kernpflichtfelder sind belegt (unbedingter Teil von R-001)."""
    for spalte in _KERNPFLICHTFELDER:
        pruefung.has_pattern(spalte, _MUSTER_BELEGT)
    return pruefung


def _r002(pruefung: Pruefung) -> Pruefung:
    """``plz`` besteht aus genau fuenf Ziffern (R-002)."""
    return pruefung.has_pattern("plz", _mit_leer(_MUSTER_PLZ))


def _r003(pruefung: Pruefung) -> Pruefung:
    """``iban`` hat das deutsche Format nach ISO 13616 (R-003)."""
    return pruefung.has_pattern("iban", _mit_leer(_MUSTER_IBAN))


def _r005(pruefung: Pruefung) -> Pruefung:
    """``bic`` hat acht oder elf Zeichen nach ISO 9362 (R-005)."""
    return pruefung.has_pattern("bic", _mit_leer(_MUSTER_BIC))


def _r006(pruefung: Pruefung) -> Pruefung:
    """``email`` erfuellt das vereinfachte RFC-5322-Muster (R-006)."""
    return pruefung.has_pattern("email", _mit_leer(_MUSTER_EMAIL))


def _r007(pruefung: Pruefung) -> Pruefung:
    """``hsn`` besteht aus genau vier Ziffern (R-007)."""
    return pruefung.has_pattern("hsn", _mit_leer(_MUSTER_HSN))


def _r008(pruefung: Pruefung) -> Pruefung:
    """``tsn`` besteht aus drei Grossbuchstaben oder Ziffern (R-008)."""
    return pruefung.has_pattern("tsn", _mit_leer(_MUSTER_TSN))


def _r010(pruefung: Pruefung) -> Pruefung:
    """``zahlweise`` steht im Katalog der GDV-Anlage 14 (R-010).

    Als Katalog- und nicht als Bereichspruefung: Die Schluessel 3 und 7 gibt es
    nicht, ein Intervall von 1 bis 9 liesse sie durch.
    """
    katalog = tuple(str(int(wert)) for wert in Zahlweise)
    return pruefung.is_contained_in("zahlweise", _mit_leerwert(katalog))


def _r011(pruefung: Pruefung) -> Pruefung:
    """``sparte`` steht im Spartenverzeichnis der GDV-Anlage 1 (R-011)."""
    katalog = tuple(wert.value for wert in Sparte)
    return pruefung.is_contained_in("sparte", _mit_leerwert(katalog))


def _r012(pruefung: Pruefung, *, iso_katalog: Sequence[str]) -> Pruefung:
    """``waehrung`` ist ein ISO-4217-Code und im Modell ``EUR`` (R-012).

    Zwei getrennte Pruefungen fuer die zwei Stufen: syntaktische Gueltigkeit
    gegen den Katalog, danach fachliche Zulaessigkeit im Modell.
    """
    pruefung.is_contained_in("waehrung", _mit_leerwert(tuple(iso_katalog)))
    return pruefung.is_contained_in("waehrung", _mit_leerwert((WAEHRUNG_STANDARD,)))


def _r013(pruefung: Pruefung) -> Pruefung:
    """``sf_klasse_hp`` und ``sf_klasse_vk`` stehen im Katalog (R-013)."""
    for spalte in ("sf_klasse_hp", "sf_klasse_vk"):
        pruefung.is_contained_in(spalte, _mit_leerwert(SF_KLASSEN))
    return pruefung


def _r014(pruefung: Pruefung) -> Pruefung:
    """Die Typklassen liegen in den Grenzen des GDV-Verzeichnisses (R-014)."""
    for spalte, (unten, oben) in _TYPKLASSEN.items():
        pruefung.is_between(spalte, (float(unten), float(oben)))
    return pruefung


def _r015(pruefung: Pruefung) -> Pruefung:
    """Die Regionalklassen liegen in den Grenzen des GDV-Verzeichnisses (R-015)."""
    for spalte, (unten, oben) in _REGIONALKLASSEN.items():
        pruefung.is_between(spalte, (float(unten), float(oben)))
    return pruefung


def _r016(pruefung: Pruefung) -> Pruefung:
    """``zuers_zone`` steht in den ZUERS-Gefaehrdungsklassen (R-016)."""
    katalog = tuple(str(zone) for zone in wb.ZUERS_ZONEN)
    return pruefung.is_contained_in("zuers_zone", _mit_leerwert(katalog))


def _r017(pruefung: Pruefung) -> Pruefung:
    """``bauartklasse`` steht in der GDV-Anlage 12 (R-017)."""
    return pruefung.is_contained_in("bauartklasse", _mit_leerwert(BAUARTKLASSEN))


def _r018(pruefung: Pruefung) -> Pruefung:
    """``anfrage_status`` steht im definierten Enum (R-018)."""
    katalog = tuple(wert.value for wert in Anfragestatus)
    return pruefung.is_contained_in("anfrage_status", _mit_leerwert(katalog))


def _r019(pruefung: Pruefung) -> Pruefung:
    """``nutzungsart`` steht im Katalog der GDV-Satzart 0210.050 (R-019)."""
    katalog = tuple(wert.value for wert in Nutzungsart)
    return pruefung.is_contained_in("nutzungsart", _mit_leerwert(katalog))


def _r020(pruefung: Pruefung) -> Pruefung:
    """``art_kennzeichen`` steht im Katalog der GDV-Satzart 0210.050 (R-020)."""
    katalog = tuple(wert.value for wert in ArtKennzeichen)
    return pruefung.is_contained_in("art_kennzeichen", _mit_leerwert(katalog))


def _r021(pruefung: Pruefung) -> Pruefung:
    """Alle Beitrags- und Summenfelder sind nicht negativ (R-021)."""
    for spalten in _BEITRAGSFELDER.values():
        for spalte in spalten:
            pruefung.is_greater_or_equal_than(spalte, 0.0)
    return pruefung


def _r022(pruefung: Pruefung, *, grenzen: tuple[int, int]) -> Pruefung:
    """``wohnflaeche_qm`` liegt im plausiblen Korridor (R-022)."""
    return pruefung.is_between("wohnflaeche_qm", (float(grenzen[0]), float(grenzen[1])))


def _r023(pruefung: Pruefung, *, jahr: int) -> Pruefung:
    """``baujahr`` liegt zwischen 1500 und dem Jahr des Stichtags (R-023)."""
    untergrenze = float(wb.BAUJAHR_UNTERGRENZE_REGEL)
    return pruefung.is_between("baujahr", (untergrenze, float(jahr)))


def _r024(pruefung: Pruefung) -> Pruefung:
    """Die Deckungssummen erreichen die gesetzliche Mindestdeckung (R-024)."""
    for spalte, grenze in _MINDESTDECKUNG.items():
        pruefung.is_greater_or_equal_than(spalte, float(grenze))
    return pruefung


def _r025(pruefung: Pruefung, *, spalten: Sequence[str]) -> Pruefung:
    """Kein Feld traegt einen impliziten Fehlwert (Textteil von R-025)."""
    for spalte in spalten:
        pruefung.not_contained_in(spalte, _SENTINELS)
    return pruefung


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class B3Regel:
    """Eine G1-Regel und ihr Schicksal in der Check-API von cuallee.

    Attributes:
        regel_id: Kennung der Regel, zum Beispiel ``"R-014"``.
        ausdruckbar: ``True`` nur, wenn die Regel **vollstaendig** deklarativ
            formulierbar ist. Teilweise ausdrueckbare Regeln tragen ``False`` und
            werden in :class:`B3Bericht` getrennt ausgewiesen.
        sicht: :data:`SICHT_RAW`, :data:`SICHT_NUMERISCH` oder
            :data:`SICHT_KEINE`.
        begruendung: Warum die Regel nicht oder nur teilweise ausdrueckbar ist,
            beziehungsweise welche Framework-Reibung sie kostet.
        ergaenze: Fuegt die Regel einer Pruefung hinzu; ``None``, wenn sie gar
            nicht formulierbar ist.
        spalten_je_entitaet: Geltungsbereich je Entitaet. Noetig, weil
            Spaltennamen mehrfach vorkommen und eine Filterung nach blosser
            Spaltenexistenz eine Regel still verbreitern wuerde.
    """

    regel_id: str
    ausdruckbar: bool
    sicht: str
    begruendung: str
    ergaenze: Callable[[Pruefung], Pruefung] | None
    spalten_je_entitaet: Mapping[str, tuple[str, ...]] = field(default=_KEIN_GELTUNGSBEREICH)

    @property
    def teilweise(self) -> bool:
        """Gibt zurueck, ob die Regel nur teilweise ausdrueckbar ist."""
        return not self.ausdruckbar and self.ergaenze is not None


def _alle_fachspalten() -> Mapping[str, tuple[str, ...]]:
    """Gibt je Entitaet alle Spalten ausser ``row_id`` zurueck (Geltung von R-025).

    ``row_id`` bleibt aussen vor: Sie ist niemals Ziel einer Verfaelschung
    (Architekturregel A3) und traegt keine fachliche Aussage.
    """
    return {
        entitaet: tuple(spalte for spalte in spalten if spalte != "row_id")
        for entitaet, spalten in SPALTEN_JE_ENTITAET.items()
    }


def _fachspalten_gesamt() -> tuple[str, ...]:
    """Gibt alle fachlichen Spaltennamen des Datenmodells sortiert zurueck.

    Der Geltungsbereich von R-025 vor der Einschraenkung auf eine Entitaet. Die
    Sortierung haelt die Reihenfolge der Regeln in der Pruefung fest und damit
    die Reihenfolge der Meldungen (Architekturregel A2).
    """
    return tuple(sorted({spalte for spalten in _alle_fachspalten().values() for spalte in spalten}))


def _katalog_rohsicht(iso_katalog: Sequence[str]) -> tuple[B3Regel, ...]:
    """Baut die Regeln, die auf der Rohsicht laufen.

    Args:
        iso_katalog: Waehrungscodes aus ``waehrungen.csv`` (R-012).

    Returns:
        Die Regeln in Katalogreihenfolge.
    """
    return (
        B3Regel(
            regel_id="R-001",
            ausdruckbar=False,
            sicht=SICHT_RAW,
            begruendung=(
                "Der unbedingte Teil ist als Musterpruefung formulierbar. Der bedingte Teil "
                "'anrede ungleich FIRMA erzwingt ein geburtsdatum' ist eine bedingte "
                "funktionale Abhaengigkeit; eine spaltenweise Check-API kann keine "
                "Bedingung ueber eine zweite Spalte ausdruecken."
            ),
            ergaenze=_r001,
            spalten_je_entitaet={
                "anfrage": ("anfrage_id", "sparte", "eingangszeitpunkt", "vn_person_id"),
                "person": ("nachname", "plz"),
            },
        ),
        B3Regel(
            regel_id="R-002",
            ausdruckbar=True,
            sicht=SICHT_RAW,
            begruendung=(
                "Als Muster formulierbar. Der Typteil der Regel — 'als Zeichenkette "
                "gefuehrt' — ist auf der Rohsicht per Konstruktion erfuellt und faellt "
                "damit weg."
            ),
            ergaenze=_r002,
            spalten_je_entitaet={"person": ("plz",)},
        ),
        B3Regel(
            regel_id="R-003",
            ausdruckbar=True,
            sicht=SICHT_RAW,
            begruendung="Als Muster formulierbar.",
            ergaenze=_r003,
            spalten_je_entitaet={"zahlung": ("iban",)},
        ),
        B3Regel(
            regel_id="R-004",
            ausdruckbar=False,
            sicht=SICHT_KEINE,
            begruendung=(
                "Die Pruefziffer nach ISO 7064 Mod 97-10 braucht eine Berechnung ueber den "
                "Wert. cuallee bietet dafuer nur den Ausstieg is_custom beziehungsweise "
                "satisfies mit eigener Python-Funktion — dann formuliert nicht mehr das "
                "Framework die Regel, sondern es ruft sie nur auf."
            ),
            ergaenze=None,
        ),
        B3Regel(
            regel_id="R-005",
            ausdruckbar=True,
            sicht=SICHT_RAW,
            begruendung=(
                "Als Laengenmenge und nicht als Aufbaumuster formuliert: Geprueft ist nach "
                "ISO 9362 die Laenge, nicht die Zeichenklasse."
            ),
            ergaenze=_r005,
            spalten_je_entitaet={"zahlung": ("bic",)},
        ),
        B3Regel(
            regel_id="R-006",
            ausdruckbar=True,
            sicht=SICHT_RAW,
            begruendung="Als Muster formulierbar.",
            ergaenze=_r006,
            spalten_je_entitaet={"person": ("email",)},
        ),
        B3Regel(
            regel_id="R-007",
            ausdruckbar=True,
            sicht=SICHT_RAW,
            begruendung="Als Muster formulierbar.",
            ergaenze=_r007,
            spalten_je_entitaet={"risiko_kfz": ("hsn",)},
        ),
        B3Regel(
            regel_id="R-008",
            ausdruckbar=True,
            sicht=SICHT_RAW,
            begruendung="Als Muster formulierbar.",
            ergaenze=_r008,
            spalten_je_entitaet={"risiko_kfz": ("tsn",)},
        ),
        B3Regel(
            regel_id="R-009",
            ausdruckbar=False,
            sicht=SICHT_KEINE,
            begruendung=(
                "Ein Muster erkennt acht Ziffern, aber nicht den 31. Februar. Die "
                "Datumspraedikate von cuallee setzen einen Datumstyp voraus; den gibt es "
                "auf der Rohsicht nicht, und auf der typisierten Schicht ist die Regel "
                "nicht mehr verletzbar."
            ),
            ergaenze=None,
        ),
        B3Regel(
            regel_id="R-010",
            ausdruckbar=True,
            sicht=SICHT_RAW,
            begruendung="Als Katalogpruefung formulierbar.",
            ergaenze=_r010,
            spalten_je_entitaet={"anfrage": ("zahlweise",)},
        ),
        B3Regel(
            regel_id="R-011",
            ausdruckbar=True,
            sicht=SICHT_RAW,
            begruendung="Als Katalogpruefung formulierbar, in beiden Entitaeten.",
            ergaenze=_r011,
            spalten_je_entitaet={"anfrage": ("sparte",), "tarif": ("sparte",)},
        ),
        B3Regel(
            regel_id="R-012",
            ausdruckbar=True,
            sicht=SICHT_RAW,
            begruendung=(
                "Beide Stufen sind Katalogpruefungen. Dass sie getrennt gemeldet werden, "
                "ergibt sich hier von selbst: cuallee fuehrt jede Pruefung als eigene Regel."
            ),
            ergaenze=partial(_r012, iso_katalog=tuple(iso_katalog)),
            spalten_je_entitaet={"anfrage": ("waehrung",)},
        ),
        B3Regel(
            regel_id="R-013",
            ausdruckbar=True,
            sicht=SICHT_RAW,
            begruendung=("Als Katalogpruefung formulierbar. Der Typteil entfaellt wie bei R-002."),
            ergaenze=_r013,
            spalten_je_entitaet={"risiko_kfz": ("sf_klasse_hp", "sf_klasse_vk")},
        ),
        B3Regel(
            regel_id="R-016",
            ausdruckbar=True,
            sicht=SICHT_RAW,
            begruendung=(
                "Als Katalogpruefung auf der Rohsicht formuliert und nicht als "
                "Zahlenbereich: Vier Zonen sind ein Katalog, kein Intervall."
            ),
            ergaenze=_r016,
            spalten_je_entitaet={"risiko_hausrat": ("zuers_zone",)},
        ),
        B3Regel(
            regel_id="R-017",
            ausdruckbar=True,
            sicht=SICHT_RAW,
            begruendung="Als Katalogpruefung formulierbar.",
            ergaenze=_r017,
            spalten_je_entitaet={"risiko_hausrat": ("bauartklasse",)},
        ),
        B3Regel(
            regel_id="R-018",
            ausdruckbar=True,
            sicht=SICHT_RAW,
            begruendung="Als Katalogpruefung formulierbar.",
            ergaenze=_r018,
            spalten_je_entitaet={"anfrage": ("anfrage_status",)},
        ),
        B3Regel(
            regel_id="R-019",
            ausdruckbar=True,
            sicht=SICHT_RAW,
            begruendung="Als Katalogpruefung formulierbar.",
            ergaenze=_r019,
            spalten_je_entitaet={"risiko_kfz": ("nutzungsart",)},
        ),
        B3Regel(
            regel_id="R-020",
            ausdruckbar=True,
            sicht=SICHT_RAW,
            begruendung="Als Katalogpruefung formulierbar.",
            ergaenze=_r020,
            spalten_je_entitaet={"risiko_kfz": ("art_kennzeichen",)},
        ),
        B3Regel(
            regel_id="R-025",
            ausdruckbar=False,
            sicht=SICHT_RAW,
            begruendung=(
                "Die Sentinel-Liste ist als Ausschlusskatalog formulierbar, die "
                "Feldausnahmen sind es nicht: In jahresfahrleistung_km und in den "
                "Sublimit-Feldern ist 9999 ein legitimer Wert. Die numerischen Sentinels "
                "bleiben deshalb ganz aussen vor; geprueft werden Text- und "
                "Datumssentinels."
            ),
            ergaenze=partial(_r025, spalten=_fachspalten_gesamt()),
            spalten_je_entitaet=_alle_fachspalten(),
        ),
    )


def _katalog_numerisch(*, wohnflaeche: tuple[int, int], stichtagsjahr: int) -> tuple[B3Regel, ...]:
    """Baut die Regeln, die auf der numerischen Sicht laufen.

    Args:
        wohnflaeche: Plausibler Korridor der Wohnflaeche (R-022).
        stichtagsjahr: Jahr des Stichtags aus der Konfiguration (R-023).

    Returns:
        Die Regeln in Katalogreihenfolge.
    """
    reibung = (
        "Als Bereichspruefung formulierbar, aber nur auf einer numerischen Sicht: "
        "cuallee verlangt fuer Zahlenpraedikate select_dtypes('number'), das Projekt "
        "fuehrt Betraege als Decimal. Die Wandlung nach float ist Framework-Reibung."
    )
    return (
        B3Regel(
            regel_id="R-014",
            ausdruckbar=True,
            sicht=SICHT_NUMERISCH,
            begruendung=reibung,
            ergaenze=_r014,
            spalten_je_entitaet={"risiko_kfz": tuple(_TYPKLASSEN)},
        ),
        B3Regel(
            regel_id="R-015",
            ausdruckbar=True,
            sicht=SICHT_NUMERISCH,
            begruendung=reibung,
            ergaenze=_r015,
            spalten_je_entitaet={"risiko_kfz": tuple(_REGIONALKLASSEN)},
        ),
        B3Regel(
            regel_id="R-021",
            ausdruckbar=True,
            sicht=SICHT_NUMERISCH,
            begruendung=reibung,
            ergaenze=_r021,
            spalten_je_entitaet=dict(_BEITRAGSFELDER),
        ),
        B3Regel(
            regel_id="R-022",
            ausdruckbar=True,
            sicht=SICHT_NUMERISCH,
            begruendung=reibung,
            ergaenze=partial(_r022, grenzen=wohnflaeche),
            spalten_je_entitaet={"risiko_hausrat": ("wohnflaeche_qm",)},
        ),
        B3Regel(
            regel_id="R-023",
            ausdruckbar=True,
            sicht=SICHT_NUMERISCH,
            begruendung=(
                reibung + " Die Obergrenze kommt aus dem Stichtag der Konfiguration, "
                "nicht aus der Systemzeit (Architekturregel A2)."
            ),
            ergaenze=partial(_r023, jahr=stichtagsjahr),
            spalten_je_entitaet={"risiko_hausrat": ("baujahr",)},
        ),
        B3Regel(
            regel_id="R-024",
            ausdruckbar=True,
            sicht=SICHT_NUMERISCH,
            begruendung=reibung,
            ergaenze=_r024,
            spalten_je_entitaet={"tarif": tuple(_MINDESTDECKUNG)},
        ),
    )


def b3_katalog(kontext: Kontext) -> tuple[B3Regel, ...]:
    """Baut die Registry der fuenfundzwanzig G1-Regeln in Katalogreihenfolge.

    Drei Regeln brauchen Werte, die erst zur Laufzeit feststehen: R-012 den
    ISO-4217-Katalog aus ``waehrungen.csv``, R-022 den Korridor aus den
    Schwellenwerten und R-023 das Jahr des Stichtags. Sie werden ueber
    :func:`functools.partial` gebunden, damit die Regelfunktionen selbst die
    einheitliche Signatur behalten und ``codezeilen.py`` sie messen kann.

    Args:
        kontext: Pruefkontext ueber beide Datenschichten und die Referenztabellen.

    Returns:
        Alle fuenfundzwanzig Regeln, aufsteigend nach ``regel_id``.

    Raises:
        B3Fehler: Wenn die Registry nicht genau :data:`REGELN_G1` Regeln enthaelt.
            Eine vergessene Regel wuerde den Anteil ausdrueckbarer Regeln
            stillschweigend beschoenigen.
    """
    iso_katalog = tuple(str(wert) for wert in kontext.referenztabelle("waehrungen")["code"])
    regeln = (
        *_katalog_rohsicht(iso_katalog),
        *_katalog_numerisch(
            wohnflaeche=kontext.schwellen.r022_wohnflaeche,
            stichtagsjahr=kontext.stichtag.year,
        ),
    )
    if len(regeln) != REGELN_G1:
        raise B3Fehler(
            f"Die B3-Registry fuehrt {len(regeln)} Regeln, erwartet sind {REGELN_G1} "
            "(R-001 bis R-025 aus spec/02_regelkatalog.md)."
        )
    return tuple(sorted(regeln, key=lambda regel: regel.regel_id))


# ---------------------------------------------------------------------------
# Die beiden Sichten
# ---------------------------------------------------------------------------


def _rohsicht(kontext: Kontext, entitaet: str) -> pd.DataFrame:
    """Baut die Rohsicht einer Entitaet fuer cuallee.

    Die Rohschicht des Projekts traegt den pandas-Dtype ``string``. cuallee
    prueft in ``validate_data_types`` gegen ``select_dtypes("object")`` und
    weist ``string`` zurueck; ausserdem verlangt ``has_pattern`` Werte, auf denen
    ``Series.str.match`` arbeitet. Die Sicht wird deshalb elementweise als
    Objektspalte aus Zeichenketten aufgebaut. Fehlwerte werden zum Leerstring —
    das ist die Darstellung eines leeren Wertes auf der Rohschicht (``spec/01``,
    Abschnitt 6) und nicht ein stiller Ersatz.

    Args:
        kontext: Pruefkontext.
        entitaet: Name der Entitaet.

    Returns:
        Einen Datenrahmen mit denselben Spalten, alle als ``object``.
    """
    rahmen = kontext.rahmen(Schicht.RAW, entitaet)
    spalten = {
        name: pd.Series(
            [LEER_ROH if wert is None or pd.isna(wert) else str(wert) for wert in rahmen[name]],
            dtype=object,
        )
        for name in rahmen.columns
    }
    return pd.DataFrame(spalten)


def _neutralwerte(kontext: Kontext) -> Mapping[str, float]:
    """Gibt je numerischer Spalte den Ersatzwert fuer eine leere Zelle zurueck.

    Das numerische Gegenstueck zu :func:`_mit_leer`. ``NaN`` ergibt bei
    ``Series.between`` und ``Series.ge`` immer ``False``; ohne Ersatzwert zaehlte
    cuallee jedes planmaessig leere Feld als Verstoss, und B3 saehe im
    Clean-Baseline-Lauf schlechter aus, als es ist. Der Ersatzwert ist je Spalte
    ein Wert, der die Regel dieser Spalte per Konstruktion erfuellt — er
    entscheidet also nichts, er haelt die leere Zelle nur aus der Wertung heraus.

    Die Menge der hier gefuehrten Spalten ist zugleich die Definition der
    numerischen Sicht: Was hier nicht steht, kommt dort nicht vor.

    Args:
        kontext: Pruefkontext; liefert den Wohnflaechenkorridor.

    Returns:
        Eine Abbildung Spaltenname auf Ersatzwert.
    """
    neutral: dict[str, float] = {}
    for spalte, (unten, _) in _TYPKLASSEN.items():
        neutral[spalte] = float(unten)
    for spalte, (unten, _) in _REGIONALKLASSEN.items():
        neutral[spalte] = float(unten)
    for spalten in _BEITRAGSFELDER.values():
        for spalte in spalten:
            neutral[spalte] = 0.0
    for spalte, grenze in _MINDESTDECKUNG.items():
        neutral[spalte] = float(grenze)
    neutral["wohnflaeche_qm"] = float(kontext.schwellen.r022_wohnflaeche[0])
    neutral["baujahr"] = float(wb.BAUJAHR_UNTERGRENZE_REGEL)
    return neutral


def _als_gleitkomma(wert: Any, neutral: float) -> float:  # noqa: ANN401
    """Wandelt einen typisierten Wert in ``float``; leere Zellen bekommen den Ersatzwert."""
    if wert is None or pd.isna(wert):
        return neutral
    return float(wert)


def _numerische_sicht(
    kontext: Kontext, entitaet: str, neutral: Mapping[str, float]
) -> pd.DataFrame:
    """Baut die numerische Sicht einer Entitaet aus der typisierten Schicht.

    Args:
        kontext: Pruefkontext.
        entitaet: Name der Entitaet.
        neutral: Ersatzwerte aus :func:`_neutralwerte`.

    Returns:
        Einen Datenrahmen mit den numerischen Spalten dieser Entitaet als
        ``float``. Hat die Entitaet keine, ist er leer.
    """
    rahmen = kontext.rahmen(Schicht.TYPED, entitaet)
    spalten = [name for name in SPALTEN_JE_ENTITAET[entitaet] if name in neutral]
    if not spalten:
        return pd.DataFrame()
    return pd.DataFrame(
        {
            name: pd.Series(
                [_als_gleitkomma(wert, neutral[name]) for wert in rahmen[name]],
                dtype=float,
            )
            for name in spalten
        }
    )


# ---------------------------------------------------------------------------
# Der Bericht
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class B3Bericht:
    """Die vier Kennzahlen des B3-Vergleichs.

    Attributes:
        ausdrueckbar: Regeln, die cuallee **vollstaendig** formulieren kann.
        teilweise: Regeln, von denen nur ein Teil formulierbar ist. Sie zaehlen
            in :attr:`anteil_ausdrueckbar_g1` **nicht** mit — eine halbe Regel ist
            keine Regel, und die Gegenrechnung bleibt trotzdem sichtbar.
        nicht_ausdrueckbar: Regeln, die gar nicht formulierbar sind.
        anteil_ausdrueckbar_g1: Anteil bezogen auf die :data:`REGELN_G1` Regeln
            der Gruppe G1, die B3 vorgelegt bekommt.
        anteil_ausdrueckbar_katalog: Anteil bezogen auf alle
            :data:`REGELN_KATALOG` Regeln des Katalogs. Die Regeln der Gruppen G2
            bis G5 wurden B3 nicht vorgelegt und zaehlen als nicht ausdrueckbar —
            das ist keine Unterstellung, sondern die Folge daraus, dass eine
            spaltenweise Check-API keine Beziehung zwischen Feldern, Zeilen oder
            Tabellen formulieren kann.
        codezeilen_prototyp: Anweisungszeilen je Regel im Prototyp.
        codezeilen_framework: Anweisungszeilen je Regel in diesem Modul. Bei
            R-001 und R-025 steht dem kuerzeren Framework-Quelltext eine
            **unvollstaendige** Regel gegenueber; der Aufwandsvergleich ist dort
            nur zusammen mit :attr:`teilweise` zu lesen. Beide Kennzahlen stehen
            deshalb nebeneinander im selben Bericht.
        laufzeit_s: Laufzeit des letzten ``erkenne``-Aufrufs in Sekunden.
        diagnoseguete: Was der Report ueber einen Fund aussagt; siehe
            :data:`DIAGNOSEGUETE`.
    """

    ausdrueckbar: tuple[str, ...]
    teilweise: tuple[str, ...]
    nicht_ausdrueckbar: tuple[str, ...]
    anteil_ausdrueckbar_g1: float
    anteil_ausdrueckbar_katalog: float
    codezeilen_prototyp: Mapping[str, int]
    codezeilen_framework: Mapping[str, int]
    laufzeit_s: float
    diagnoseguete: Mapping[str, bool]

    def als_dict(self) -> dict[str, Any]:
        """Baut die JSON-taugliche Form fuer ``results/b3_framework.json``.

        Returns:
            Ein Woerterbuch aus reinen Grundtypen, ohne Zeitstempel
            (Architekturregel A2).
        """
        gemeinsam = sorted(set(self.codezeilen_prototyp) & set(self.codezeilen_framework))
        vollstaendig = [regel_id for regel_id in gemeinsam if regel_id not in set(self.teilweise)]
        return {
            "anteil_ausdrueckbarer_regeln": {
                "g1": round(self.anteil_ausdrueckbar_g1, 6),
                "katalog": round(self.anteil_ausdrueckbar_katalog, 6),
                "regeln_g1": REGELN_G1,
                "regeln_katalog": REGELN_KATALOG,
            },
            "ausdrueckbar": list(self.ausdrueckbar),
            "codezeilen_je_regel": {
                "framework": dict(self.codezeilen_framework),
                "prototyp": dict(self.codezeilen_prototyp),
                "summe_framework": sum(self.codezeilen_framework[key] for key in gemeinsam),
                "summe_prototyp": sum(self.codezeilen_prototyp[key] for key in gemeinsam),
                "verglichene_regeln": gemeinsam,
                # Dieselbe Summe ohne die nur teilweise ausdrueckbaren Regeln.
                # Sie ist die ehrlichere Zahl fuer die Arbeit: R-001 und R-025
                # gehen sonst mit ihren **verkuerzten** Framework-Zeilen gegen die
                # **vollstaendigen** Prototypzeilen in den Vergleich ein und
                # schmeicheln dem Framework. Beide Summen stehen nebeneinander,
                # damit die Differenz sichtbar bleibt statt gewaehlt zu werden.
                "summe_framework_nur_vollstaendig": sum(
                    self.codezeilen_framework[key] for key in vollstaendig
                ),
                "summe_prototyp_nur_vollstaendig": sum(
                    self.codezeilen_prototyp[key] for key in vollstaendig
                ),
                "verglichene_regeln_nur_vollstaendig": vollstaendig,
            },
            "diagnoseguete": dict(self.diagnoseguete),
            "laufzeit_s": round(self.laufzeit_s, 6),
            "nicht_ausdrueckbar": list(self.nicht_ausdrueckbar),
            "teilweise_ausdrueckbar": list(self.teilweise),
        }


# ---------------------------------------------------------------------------
# Das Verfahren
# ---------------------------------------------------------------------------


def _beschraenke(pruefung: Pruefung, spalten: Sequence[str]) -> None:
    """Entfernt aus einer Pruefung alle Regeln ausserhalb des Geltungsbereichs.

    Args:
        pruefung: Die Pruefung.
        spalten: Zulaessige Spalten dieser Regel in dieser Entitaet.
    """
    erlaubt = set(spalten)
    zu_loeschen = [regel.key for regel in pruefung.rules if str(regel.column) not in erlaubt]
    if zu_loeschen:
        pruefung.delete_rule_by_key(zu_loeschen)


class B3Framework:
    """Baseline B3 — die G1-Regeln, formuliert in der Check-API von cuallee.

    Erfuellt das Protokoll :class:`~src.evaluation.modell.Verfahren`. Das
    Zusatzprotokoll ``MitSatzmeldungen`` erfuellt es nicht: Satzbezogene Befunde
    setzen einen Zeilenbezug voraus, den cuallee nicht liefert.

    Attributes:
        name: Kurzname im Bericht.
        beschreibung: Ein Satz fuer den Anhang.
        lokalisiert_zellen: ``False`` — siehe Modul-Docstring.
        in_inferenzstatistik: ``False`` — siehe Modul-Docstring.
    """

    name: str = "B3"
    beschreibung: str = (
        "cuallee 0.15, dieselben Regelinhalte der Gruppe G1 (R-001 bis R-025) in einer "
        "deklarativen Check-API"
    )
    lokalisiert_zellen: bool = False
    in_inferenzstatistik: bool = False

    def __init__(self) -> None:
        """Legt das Verfahren an; der Katalog entsteht erst mit dem Kontext."""
        self._laufzeit_s: float | None = None

    def erkenne(self, kontext: Kontext) -> pd.DataFrame:
        """Fuehrt alle formulierbaren G1-Regeln aus und meldet die Verstoesse.

        **Die Meldungen tragen keinen Zeilenbezug.** Jede Zeile des Ergebnisses
        steht fuer eine Regel auf einer Spalte einer Entitaet und nennt in ihrer
        Meldung die Zahl der betroffenen Zeilen; ``row_id`` ist
        :data:`~src.evaluation.modell.ROW_ID_OHNE_BEZUG`. Das ist der gemessene
        Befund zur Diagnoseguete (siehe Modul-Docstring).

        Entitaeten ohne Zeilen werden uebersprungen: cuallee dividiert in
        ``summary`` durch die Zeilenzahl.

        Args:
            kontext: Pruefkontext ueber beide Datenschichten des verfaelschten
                Datensatzes.

        Returns:
            Einen Datenrahmen mit den Spalten
            :data:`~src.evaluation.modell.VERSTOSS_SPALTEN`.
        """
        beginn = time.perf_counter()
        katalog = b3_katalog(kontext)
        neutral = _neutralwerte(kontext)
        laufend: dict[str, int] = {}
        zeilen: list[tuple[str, int, str, str, str, str]] = []

        for entitaet in ENTITAETEN:
            sichten = {
                SICHT_RAW: _rohsicht(kontext, entitaet),
                SICHT_NUMERISCH: _numerische_sicht(kontext, entitaet, neutral),
            }
            for regel in katalog:
                spalten = regel.spalten_je_entitaet.get(entitaet)
                if regel.ergaenze is None or not spalten:
                    continue
                rahmen = sichten[regel.sicht]
                if rahmen.empty:
                    continue
                zeilen.extend(self._pruefe(regel, entitaet, rahmen, spalten, laufend))

        self._laufzeit_s = time.perf_counter() - beginn
        return pd.DataFrame(zeilen, columns=list(VERSTOSS_SPALTEN))

    def _pruefe(
        self,
        regel: B3Regel,
        entitaet: str,
        rahmen: pd.DataFrame,
        spalten: Sequence[str],
        laufend: dict[str, int],
    ) -> list[tuple[str, int, str, str, str, str]]:
        """Fuehrt eine Regel auf einer Entitaet aus und uebersetzt den Report.

        Args:
            regel: Die auszufuehrende Regel.
            entitaet: Name der Entitaet.
            rahmen: Die passende Sicht auf die Daten.
            spalten: Geltungsbereich der Regel in dieser Entitaet.
            laufend: Zaehler je ``regel_id`` fuer die ``verstoss_id``.

        Returns:
            Je verletzter Spalte eine Meldungszeile in der Form
            :data:`~src.evaluation.modell.VERSTOSS_SPALTEN`.

        Raises:
            B3Fehler: Wenn cuallee die Regel nicht ausfuehren kann, etwa weil eine
                Spalte den erwarteten Dtype nicht hat.
        """
        if regel.ergaenze is None:
            raise B3Fehler(
                f"{regel.regel_id} ist in cuallee nicht formulierbar und darf nicht "
                "ausgefuehrt werden."
            )
        pruefung = Check(CheckLevel.ERROR, f"B3-{entitaet}-{regel.regel_id}")
        regel.ergaenze(pruefung)
        _beschraenke(pruefung, spalten)
        if pruefung.empty:
            return []

        try:
            bericht = pruefung.validate(rahmen)
        except (AssertionError, ValueError, TypeError, KeyError) as fehler:
            raise B3Fehler(
                f"cuallee kann {regel.regel_id} auf {entitaet} nicht ausfuehren: {fehler}"
            ) from fehler
        # Der Zeitstempel des Frameworks widerspricht Architekturregel A2.
        bericht = bericht.drop(columns=list(_VERWORFENE_SPALTEN))

        meldungen: list[tuple[str, int, str, str, str, str]] = []
        for _, zeile in bericht.iterrows():
            verstoesse = int(zeile["violations"])
            if verstoesse <= 0:
                continue
            laufend[regel.regel_id] = laufend.get(regel.regel_id, 0) + 1
            meldungen.append(
                (
                    entitaet,
                    ROW_ID_OHNE_BEZUG,
                    str(zeile["column"]),
                    regel.regel_id,
                    f"{regel.regel_id}#{laufend[regel.regel_id]:06d}",
                    (
                        f"cuallee {zeile['rule']}({zeile['value']}) auf "
                        f"{entitaet}.{zeile['column']}: {verstoesse} von {int(zeile['rows'])} "
                        f"Zeilen verletzen {regel.regel_id}. Der Report nennt weder die Zeile "
                        f"noch den Ausgangswert."
                    ),
                )
            )
        return meldungen

    def bericht(self) -> B3Bericht:
        """Stellt die vier Kennzahlen des B3-Vergleichs zusammen.

        Returns:
            Den :class:`B3Bericht`.

        Raises:
            B3Fehler: Wenn noch kein ``erkenne``-Aufruf stattgefunden hat. Ohne
                Lauf gibt es keine Laufzeit, und eine Null waere von einer
                gemessenen Null nicht zu unterscheiden.
        """
        if self._laufzeit_s is None:
            raise B3Fehler(
                "bericht() braucht eine gemessene Laufzeit. Zuerst erkenne(kontext) aufrufen."
            )
        ausdrueckbar: list[str] = []
        teilweise: list[str] = []
        nicht: list[str] = []
        for regel_id, zustand in _AUSDRUECKBARKEIT.items():
            ziel = {"ja": ausdrueckbar, "teilweise": teilweise, "nein": nicht}[zustand]
            ziel.append(regel_id)

        return B3Bericht(
            ausdrueckbar=tuple(ausdrueckbar),
            teilweise=tuple(teilweise),
            nicht_ausdrueckbar=tuple(nicht),
            anteil_ausdrueckbar_g1=len(ausdrueckbar) / REGELN_G1,
            anteil_ausdrueckbar_katalog=len(ausdrueckbar) / REGELN_KATALOG,
            codezeilen_prototyp=codezeilen_je_regel(DATEI_PROTOTYP_G1, MUSTER_PROTOTYP),
            codezeilen_framework=codezeilen_je_regel(DATEI_B3, MUSTER_B3),
            laufzeit_s=self._laufzeit_s,
            diagnoseguete=DIAGNOSEGUETE,
        )
