"""Pflichtfeldprofil je Quellschnittstelle.

Grundlage von R-057 und zugleich Steuertabelle des Generators. Die Tabelle steht
wortgleich in ``spec/01_datenmodell.md``, Abschnitt 5.

Fachlicher Hintergrund: Versicherer befuellen dieselben Felder unterschiedlich
tief. BiPRO-Schnittstellen liefern strukturiert und vollstaendig, klassische
GDV-Lieferungen und manuelle CSV-Importe deutlich lueckenhafter. Genau das ist
ein Multi-Source-Problem im Sinne von Rahm und Do.

**Wichtig fuer die Auswertung:** Dass der Generator ein bei dieser Schnittstelle
als *optional* markiertes Feld leer laesst, ist Teil des **sauberen** Datensatzes
und kein Fehler. R-057 prueft nur, dass ein als *Pflicht* markiertes Feld nicht
leer ist.

Das Modul liegt in ``src/common``, weil Generator und Regel-Engine dieselbe
Tabelle brauchen (Architekturregel A1).
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from src.common.enums import Kanal, Quellschnittstelle

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping

__all__ = [
    "BLANKO_WAHRSCHEINLICHKEIT",
    "KERNPFLICHTFELDER",
    "PFLICHTFELDER_JE_SCHNITTSTELLE",
    "PROFILFELDER",
    "PROFIL_JE_KANAL",
    "ist_pflicht",
    "optionale_felder",
    "profil_des_kanals",
]

_B420: Final = Quellschnittstelle.BIPRO_420
_RNEXT: Final = Quellschnittstelle.BIPRO_RNEXT
_GDV: Final = Quellschnittstelle.GDV
_CSV: Final = Quellschnittstelle.CSV_IMPORT

#: Kernpflichtfelder aus R-001 — unabhaengig von der Schnittstelle immer Pflicht.
#:
#: Der bedingte Teil von R-001 (``anrede`` ungleich FIRMA erzwingt ein
#: ``geburtsdatum``) ist eine Conditional Functional Dependency und steht deshalb
#: nicht in dieser Liste, sondern in der Regel selbst.
KERNPFLICHTFELDER: Final[tuple[str, ...]] = (
    "anfrage.anfrage_id",
    "anfrage.eingangszeitpunkt",
    "anfrage.sparte",
    "anfrage.vn_person_id",
    "person.nachname",
    "person.plz",
)

#: Rohform der Tabelle aus spec/01, Abschnitt 5: Feld auf die Schnittstellen,
#: bei denen es Pflicht ist. Als Tupel gefuehrt, damit die Reihenfolge fest ist.
_PROFIL_ROH: Final[tuple[tuple[str, tuple[Quellschnittstelle, ...]], ...]] = (
    ("person.email", (_B420, _RNEXT)),
    ("person.strasse", (_B420, _RNEXT, _GDV)),
    ("person.hausnummer", (_B420, _RNEXT, _GDV)),
    ("person.familienstand", (_B420, _RNEXT)),
    ("person.wohneigentum", (_B420, _RNEXT)),
    ("risiko_kfz.abstellplatz", (_B420, _RNEXT)),
    ("risiko_kfz.alter_juengster_fahrer", (_B420, _RNEXT, _GDV)),
    ("risiko_kfz.jahresfahrleistung_km", (_B420, _RNEXT, _GDV, _CSV)),
    ("risiko_hausrat.sublimit_fahrrad_eur", (_B420, _RNEXT)),
    ("risiko_hausrat.sublimit_wertsachen_eur", (_B420, _RNEXT)),
    ("angebot.sb_tk_eur", (_B420, _RNEXT, _GDV)),
    ("angebot.sb_vk_eur", (_B420, _RNEXT, _GDV)),
    # Einzige Zeile der Tabelle, die nicht dem Muster "BiPRO strenger als GDV"
    # folgt: Die BIC ist bei BIPRO_RNEXT optional, bei GDV dagegen Pflicht.
    ("zahlung.bic", (_B420, _GDV)),
    ("zahlung.kontoinhaber", (_B420, _RNEXT)),
)

#: Alle Felder, fuer die ein schnittstellenabhaengiges Profil gilt.
PROFILFELDER: Final[tuple[str, ...]] = tuple(feld for feld, _ in _PROFIL_ROH)

#: Pflichtfelder je Schnittstelle, alphabetisch geordnet.
PFLICHTFELDER_JE_SCHNITTSTELLE: Final[Mapping[Quellschnittstelle, tuple[str, ...]]] = (
    MappingProxyType(
        {
            schnittstelle: tuple(
                sorted(feld for feld, pflicht in _PROFIL_ROH if schnittstelle in pflicht)
            )
            for schnittstelle in Quellschnittstelle
        }
    )
)

#: Wahrscheinlichkeit, mit der der Generator ein optionales Feld leer laesst.
#:
#: spec/01, Abschnitt 5: "Der Generator setzt die als optional markierten Felder
#: bei der jeweiligen Schnittstelle mit einer Wahrscheinlichkeit von 30 Prozent
#: auf leer."
BLANKO_WAHRSCHEINLICHKEIT: Final[float] = 0.30


#: Wirksames Pflichtfeldprofil je Eingangskanal (spec/01, Abschnitt 5.1).
#:
#: **Warum diese Abbildung noetig ist.** Die Profiltabelle in spec/01, Abschnitt 5
#: ist nach ``quell_schnittstelle`` geschluesselt. Dieses Feld gehoert aber zur
#: Entitaet ``angebot``: Es beschreibt, ueber welche Schnittstelle **ein
#: Versicherer sein Angebot liefert**. Die meisten Profilfelder liegen dagegen auf
#: der Anfrageseite (``person``, ``risiko_*``, ``zahlung``) — sie werden **einmal
#: je Anfrage** erfasst und an alle Versicherer verschickt. Ihr Befuellungsgrad
#: haengt deshalb nicht am liefernden Versicherer, sondern am Eingangskanal.
#: spec/01, Abschnitt 3.1 sagt zu ``kanal`` genau das: "-> erwartetes
#: Pflichtfeldniveau".
#:
#: Ohne diese Abbildung waere das Profil auf der Anfrageseite nicht anwendbar: Eine
#: Anfrage hat drei bis zwoelf Angebote mit unterschiedlichen Schnittstellen, und
#: das strengste Profil unter ihnen wuerde faktisch immer greifen — dann waere
#: jedes Feld ueberall gefuellt und R-057 haette nichts zu pruefen.
#:
#: Die Zuordnung selbst ist eine **Modellannahme** (docs/verteilungsquellen.md).
#: Sie haelt die Vorgabe aus spec/01, Abschnitt 3.2 ein, dass ``email`` bei den
#: Kanaelen WEB und APP Pflicht ist.
PROFIL_JE_KANAL: Final[Mapping[Kanal, Quellschnittstelle]] = MappingProxyType(
    {
        Kanal.WEB: _RNEXT,
        Kanal.APP: _B420,
        Kanal.API_BIPRO: _B420,
        Kanal.MAKLER: _GDV,
        Kanal.TELEFON: _CSV,
    }
)


def profil_des_kanals(kanal: Kanal | str) -> Quellschnittstelle:
    """Gibt das Pflichtfeldprofil zurueck, das fuer diesen Eingangskanal gilt.

    Args:
        kanal: Wert aus :class:`~src.common.enums.Kanal` oder die zugehoerige
            Zeichenkette.

    Returns:
        Die Quellschnittstelle, deren Profil auf die Felder der Anfrageseite
        angewendet wird.

    Raises:
        KeyError: Bei einem unbekannten Kanal. Bewusst kein stiller Ersatzwert —
            ein neuer Kanal muss hier ausdruecklich eingetragen werden.
    """
    return PROFIL_JE_KANAL[Kanal(kanal)]


def ist_pflicht(feld: str, schnittstelle: Quellschnittstelle) -> bool:
    """Gibt zurueck, ob ein Feld bei dieser Schnittstelle Pflicht ist.

    Args:
        feld: Feld in der Schreibweise ``entitaet.feldname``.
        schnittstelle: Liefernde Schnittstelle.

    Returns:
        ``True`` fuer Kernpflichtfelder aus R-001 und fuer Felder, die das
        Profil bei dieser Schnittstelle als Pflicht ausweist.
    """
    if feld in KERNPFLICHTFELDER:
        return True
    return feld in PFLICHTFELDER_JE_SCHNITTSTELLE[schnittstelle]


def optionale_felder(schnittstelle: Quellschnittstelle) -> tuple[str, ...]:
    """Gibt die Profilfelder zurueck, die bei dieser Schnittstelle optional sind.

    Args:
        schnittstelle: Liefernde Schnittstelle.

    Returns:
        Die alphabetisch geordneten optionalen Felder. Der Generator laesst sie
        mit :data:`BLANKO_WAHRSCHEINLICHKEIT` leer.
    """
    pflicht = set(PFLICHTFELDER_JE_SCHNITTSTELLE[schnittstelle])
    return tuple(feld for feld in sorted(PROFILFELDER) if feld not in pflicht)
