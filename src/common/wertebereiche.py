"""Numerische Grenzen und fachliche Konstanten des Datenmodells.

Jede Konstante traegt ihre Quelle im Kommentar. Zwei Arten von Grenzen werden
konsequent getrennt:

* **Katalog- und Gesetzesgrenzen** (Praefix ohne Zusatz) — sie sind fachlich hart
  und Grundlage der Regeln, zum Beispiel :data:`TYPKLASSE_HP`.
* **Ziehungsbereiche des Generators** (Praefix ``GENERATOR_``) — sie sind enger
  als die Katalogrenzen, damit sauber erzeugte Daten nicht am Rand des
  Zulaessigen liegen.

Schwellenwerte der heuristischen Regeln (C2) stehen bewusst **nicht** hier,
sondern in ``config/default.yaml``, weil sie in der Arbeit variiert werden.

Dieses Modul ist bewusst frei von projektinternen Abhaengigkeiten ausser
:mod:`src.common.enums` (Architekturregel A1).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from src.common.enums import Sparte

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping

__all__ = [
    "ALTER_JUENGSTER_FAHRER",
    "ALTER_VN",
    "BAUJAHR_UNTERGRENZE_REGEL",
    "BEMESSUNGSGRUNDLAGE_HAUSRAT",
    "BERECHNUNG_DELTA_MAX_SEKUNDEN",
    "BIC_LAENGEN",
    "ERSTZULASSUNG_FRUEHESTENS",
    "FUEHRERSCHEIN_MINDESTALTER_JAHRE",
    "GENERATOR_BAUJAHR_UNTERGRENZE",
    "GENERATOR_JAHRESFAHRLEISTUNG_KM",
    "GENERATOR_LEISTUNG_KW",
    "GENERATOR_NEUPREIS_EUR",
    "GENERATOR_WOHNFLAECHE_QM",
    "HSN_LAENGE",
    "IBAN_LAENGE_DE",
    "LEISTUNG_KW",
    "PFLVG_MINDESTDECKUNG_PERSONEN_EUR",
    "PFLVG_MINDESTDECKUNG_SACH_EUR",
    "PFLVG_MINDESTDECKUNG_VERMOEGEN_EUR",
    "PLZ_LAENGE",
    "RATENZAHLUNGSZUSCHLAG_PROZENT",
    "REGIONALKLASSE_HP",
    "REGIONALKLASSE_TK",
    "REGIONALKLASSE_VK",
    "SB_HAUSRAT_EUR_STUFEN",
    "SB_TK_EUR_STUFEN",
    "SB_VK_EUR_STUFEN",
    "SENTINEL_AUSNAHMEFELDER",
    "SENTINEL_DATUM",
    "SENTINEL_NUMERISCH",
    "SENTINEL_TEXT",
    "STOCKWERK",
    "SUBLIMIT_FAHRRAD_EUR",
    "TSN_LAENGE",
    "TYPKLASSE_HP",
    "TYPKLASSE_TK",
    "TYPKLASSE_VK",
    "UNTERVERSICHERUNGSVERZICHT_EUR_JE_QM",
    "VERSICHERUNGSSUMME_HAUSRAT_EUR",
    "VERSICHERUNGSTEUER_EFFEKTIVSATZ",
    "VERSICHERUNGSTEUER_NOMINALSATZ",
    "VU_NUMMER_LAENGE",
    "WERTSACHEN_ANTEIL_MAX",
    "ZUERS_ANTEILE_GDV",
    "ZUERS_ZONEN",
]

# ---------------------------------------------------------------------------
# Typklassen — GDV-Typklassenverzeichnis, 16 / 24 / 25 Klassen (R-014)
# ---------------------------------------------------------------------------

#: Typklasse Kfz-Haftpflicht: 16 Klassen.
TYPKLASSE_HP: Final[tuple[int, int]] = (10, 25)
#: Typklasse Teilkasko: 24 Klassen.
TYPKLASSE_TK: Final[tuple[int, int]] = (10, 33)
#: Typklasse Vollkasko: 25 Klassen.
TYPKLASSE_VK: Final[tuple[int, int]] = (10, 34)

# ---------------------------------------------------------------------------
# Regionalklassen — GDV-Regionalklassenverzeichnis, 12 / 16 / 9 Stufen (R-015)
# ---------------------------------------------------------------------------

#: Regionalklasse Kfz-Haftpflicht.
REGIONALKLASSE_HP: Final[tuple[int, int]] = (1, 12)
#: Regionalklasse Teilkasko.
REGIONALKLASSE_TK: Final[tuple[int, int]] = (1, 16)
#: Regionalklasse Vollkasko.
REGIONALKLASSE_VK: Final[tuple[int, int]] = (1, 9)

# ---------------------------------------------------------------------------
# ZUERS — Gefaehrdungsklassen des GDV-Naturgefahren-Datenservice (R-016)
# ---------------------------------------------------------------------------

#: Gueltige ZUERS-Zonen.
ZUERS_ZONEN: Final[tuple[int, ...]] = (1, 2, 3, 4)

#: Vom GDV publizierte Anteile der ZUERS-Zonen 1 bis 4.
#:
#: Referenzverteilung fuer R-048. Die Toleranz ist relativ und steht in der
#: Konfiguration (``schwellen.r048_zuers_toleranz_relativ``).
ZUERS_ANTEILE_GDV: Final[tuple[float, float, float, float]] = (0.924, 0.061, 0.011, 0.004)

# ---------------------------------------------------------------------------
# Hausrat
# ---------------------------------------------------------------------------

#: Ziehungsbereich der Wohnflaeche (spec/01, Abschnitt 3.4, Zensus 2022).
#:
#: Die Regelgrenze von R-022 ist weiter und steht in der Konfiguration
#: (``schwellen.r022_wohnflaeche``).
GENERATOR_WOHNFLAECHE_QM: Final[tuple[int, int]] = (20, 350)

#: Untergrenze des Baujahrs im Generator (spec/01, Abschnitt 3.4).
GENERATOR_BAUJAHR_UNTERGRENZE: Final[int] = 1850

#: Untergrenze des Baujahrs in der Regel R-023.
#:
#: Bewusst weiter als der Ziehungsbereich des Generators: Die Regel soll ein
#: unmoegliches Baujahr erkennen, nicht ein ungewoehnliches.
BAUJAHR_UNTERGRENZE_REGEL: Final[int] = 1500

#: Versicherungssumme Hausrat (spec/01, Abschnitt 3.4).
VERSICHERUNGSSUMME_HAUSRAT_EUR: Final[tuple[Decimal, Decimal]] = (
    Decimal("10000.00"),
    Decimal("800000.00"),
)

#: Branchenuebliche Faustregel fuer den Unterversicherungsverzicht (R-040).
#: Modellannahme, in der Arbeit als solche zu kennzeichnen.
UNTERVERSICHERUNGSVERZICHT_EUR_JE_QM: Final[Decimal] = Decimal(650)

#: Obergrenze des Sublimits fuer Fahrraeder (spec/01, Abschnitt 3.4).
SUBLIMIT_FAHRRAD_EUR: Final[tuple[Decimal, Decimal]] = (Decimal("0.00"), Decimal("10000.00"))

#: Hoechstanteil des Wertsachen-Sublimits an der Versicherungssumme.
WERTSACHEN_ANTEIL_MAX: Final[Decimal] = Decimal("0.30")

#: Stockwerk (spec/01, Abschnitt 3.4).
STOCKWERK: Final[tuple[int, int]] = (-1, 25)

# ---------------------------------------------------------------------------
# Kfz
# ---------------------------------------------------------------------------

#: Motorleistung laut Referenztabelle ``typklassen.csv``.
LEISTUNG_KW: Final[tuple[int, int]] = (1, 1500)

#: Ziehungsbereich der Motorleistung im Referenzdatengenerator.
GENERATOR_LEISTUNG_KW: Final[tuple[int, int]] = (35, 480)

#: Neupreis laut Referenztabelle ``typklassen.csv``.
GENERATOR_NEUPREIS_EUR: Final[tuple[Decimal, Decimal]] = (
    Decimal("8000.00"),
    Decimal("250000.00"),
)

#: Jahresfahrleistung (spec/01, Abschnitt 3.3), log-normal um 12.000 km.
GENERATOR_JAHRESFAHRLEISTUNG_KM: Final[tuple[int, int]] = (1000, 60000)

#: Frueheste Erstzulassung im Datenmodell (spec/01, Abschnitt 3.3).
ERSTZULASSUNG_FRUEHESTENS: Final[date] = date(1990, 1, 1)

#: Alter des Versicherungsnehmers zum Stichtag (spec/01, Abschnitt 3.2).
ALTER_VN: Final[tuple[int, int]] = (18, 95)

#: Alter des juengsten Fahrers (spec/01, Abschnitt 3.3).
ALTER_JUENGSTER_FAHRER: Final[tuple[int, int]] = (17, 95)

#: Mindestalter fuer den Fuehrerscheinerwerb — begleitetes Fahren ab 17 (R-028).
FUEHRERSCHEIN_MINDESTALTER_JAHRE: Final[int] = 17

# ---------------------------------------------------------------------------
# Beitrag, Selbstbehalt, Steuer
# ---------------------------------------------------------------------------

#: Ratenzahlungszuschlag in Prozent (spec/01, Abschnitt 3.6).
RATENZAHLUNGSZUSCHLAG_PROZENT: Final[tuple[Decimal, Decimal]] = (
    Decimal("0.00"),
    Decimal("8.00"),
)

#: Zulaessige Selbstbehaltstufen Teilkasko.
SB_TK_EUR_STUFEN: Final[tuple[Decimal, ...]] = (
    Decimal("0.00"),
    Decimal("150.00"),
    Decimal("300.00"),
    Decimal("500.00"),
    Decimal("1000.00"),
)

#: Zulaessige Selbstbehaltstufen Vollkasko.
SB_VK_EUR_STUFEN: Final[tuple[Decimal, ...]] = (
    Decimal("0.00"),
    Decimal("300.00"),
    Decimal("500.00"),
    Decimal("1000.00"),
    Decimal("2500.00"),
)

#: Zulaessige Selbstbehaltstufen Hausrat (Betragsvariante).
SB_HAUSRAT_EUR_STUFEN: Final[tuple[Decimal, ...]] = (
    Decimal("0.00"),
    Decimal("150.00"),
    Decimal("250.00"),
    Decimal("500.00"),
    Decimal("1000.00"),
)

#: Nominalsatz der Versicherungsteuer nach Paragraf 6 VersStG.
VERSICHERUNGSTEUER_NOMINALSATZ: Final[Decimal] = Decimal("19.00")

#: Bemessungsgrundlage fuer Hausrat inklusive Feuer, Paragraf 5 Absatz 1 Nummer 3 VersStG.
BEMESSUNGSGRUNDLAGE_HAUSRAT: Final[Decimal] = Decimal("0.85")

#: Effektivsatz der Versicherungsteuer je Sparte (R-033).
#:
#: 19,00 Prozent fuer Kfz (voller Nominalsatz auf voller Bemessungsgrundlage),
#: 16,15 Prozent fuer Hausrat (19 Prozent auf 85 Prozent der Bemessungsgrundlage).
#: Die verbreitete Angabe "Hausrat 16,15 Prozent" ist ein Effektiv-, kein
#: Nominalsatz — Paragraf 6 Absatz 2 in Verbindung mit Paragraf 5 Absatz 1
#: Nummer 3 VersStG.
VERSICHERUNGSTEUER_EFFEKTIVSATZ: Final[Mapping[Sparte, Decimal]] = MappingProxyType(
    {
        Sparte.KFZ_HAFTPFLICHT: Decimal("19.00"),
        Sparte.KFZ_VOLLKASKO: Decimal("19.00"),
        Sparte.KFZ_TEILKASKO: Decimal("19.00"),
        Sparte.HAUSRAT: Decimal("16.15"),
    }
)

#: Hoechstabstand zwischen Eingangs- und Berechnungszeitpunkt (spec/01, Abschnitt 3.6).
BERECHNUNG_DELTA_MAX_SEKUNDEN: Final[int] = 60

# ---------------------------------------------------------------------------
# Gesetzliche Mindestdeckungssummen — PflVG, Anlage zu Paragraf 4 Absatz 2 (R-024)
# ---------------------------------------------------------------------------

#: Mindestdeckung Personenschaeden.
PFLVG_MINDESTDECKUNG_PERSONEN_EUR: Final[Decimal] = Decimal("7500000.00")
#: Mindestdeckung Sachschaeden.
PFLVG_MINDESTDECKUNG_SACH_EUR: Final[Decimal] = Decimal("1300000.00")
#: Mindestdeckung Vermoegensschaeden.
PFLVG_MINDESTDECKUNG_VERMOEGEN_EUR: Final[Decimal] = Decimal("50000.00")

# ---------------------------------------------------------------------------
# Feldlaengen
# ---------------------------------------------------------------------------

#: Laenge der Postleitzahl (R-002).
PLZ_LAENGE: Final[int] = 5
#: Laenge der Herstellerschluesselnummer (R-007).
HSN_LAENGE: Final[int] = 4
#: Laenge der Typschluesselnummer (R-008).
TSN_LAENGE: Final[int] = 3
#: Laenge der deutschen IBAN nach ISO 13616 (R-003).
IBAN_LAENGE_DE: Final[int] = 22
#: Zulaessige BIC-Laengen nach ISO 9362 — 9 und 10 Zeichen existieren nicht (R-005).
BIC_LAENGEN: Final[tuple[int, int]] = (8, 11)
#: Laenge der VU-Nummer.
VU_NUMMER_LAENGE: Final[int] = 5

# ---------------------------------------------------------------------------
# Implizite Fehlwerte — Grundlage von R-025 und der Injektionsvarianten F1-b bis F1-f
# ---------------------------------------------------------------------------

#: Implizite Fehlwerte in Textfeldern (R-025).
#:
#: Der Leerstring ist in diesem Projekt ein *Fehlerwert*, kein Fehlwert; "leer"
#: bedeutet immer ``pd.NA`` beziehungsweise ``None`` (CLAUDE.md, Abschnitt 5).
SENTINEL_TEXT: Final[tuple[str, ...]] = ("", "-", "k.A.", "n/a", "unbekannt")

#: Implizite Fehlwerte in Datumsfeldern (R-025).
#:
#: Zwei Schreibweisen je Sentinel, weil R-025 auf der **Rohschicht** arbeitet: Dort
#: stehen Datumswerte im GDV-Format ``TTMMJJJJ`` (spec/01, Abschnitt 6). Die
#: ISO-Schreibweise bleibt in der Liste, weil eine Injektion sie einschleusen kann —
#: erkannt werden soll der Sentinel, nicht eine bestimmte Notation.
#:
#: ``00000000`` ist in diesem Modell ausdruecklich ein **Fehlwert, kein Leerwert**:
#: Leer ist der Leerstring. Waere ``00000000`` der regulaere Leerwert, koennte R-025
#: es nicht mehr als impliziten Fehlwert melden und R-009 muesste es als
#: Nicht-Kalendertag ausnehmen — beide Regeln verloeren ihre Schaerfe (spec/01,
#: Abschnitt 6, Tabelle "Zuordnung").
SENTINEL_DATUM: Final[tuple[str, ...]] = (
    "00000000",
    "01011900",
    "0000-00-00",
    "1900-01-01",
)

#: Implizite Fehlwerte in numerischen Feldern (R-025).
SENTINEL_NUMERISCH: Final[tuple[int, ...]] = (9999, 99999999)

#: Felder, in denen ein numerisches Sentinel ein legitimer Wert ist (R-025).
#:
#: Die Ausnahmeliste ist selbst ein Diskussionspunkt der Arbeit: Sie zeigt die
#: Grenze von Sentinel-Heuristiken, sobald der Sentinel im fachlich zulaessigen
#: Wertebereich liegt.
SENTINEL_AUSNAHMEFELDER: Final[tuple[str, ...]] = (
    "risiko_hausrat.sublimit_fahrrad_eur",
    "risiko_hausrat.sublimit_wertsachen_eur",
    "risiko_kfz.jahresfahrleistung_km",
)
