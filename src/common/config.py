"""Laden und Pruefen der Konfiguration.

``config/default.yaml`` wird ausschliesslich hier gelesen. Jede andere Komponente
bekommt das erzeugte :class:`Config`-Objekt uebergeben und liest **nie** selbst
YAML (CLAUDE.md, Abschnitt 2).

Es gibt keine stillen Defaultwerte: Ein fehlender Schluessel fuehrt ebenso zum
Abbruch wie ein unbekannter. Ein Tippfehler in der Konfiguration soll auffallen,
nicht wirkungslos bleiben.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

import yaml

from src.common.enums import Sparte
from src.common.wertebereiche import ZUERS_ZONEN

__all__ = [
    "STANDARD_KONFIGURATION",
    "AngeboteJeAnfrage",
    "Config",
    "KonfigurationsFehler",
    "Pfade",
    "Referenzdaten",
    "Schwellen",
    "als_dict",
    "lade_config",
    "projekt_wurzel",
]

#: Toleranz, mit der die Spartenverteilung auf 1 summieren muss.
_SUMMEN_TOLERANZ: Final[float] = 1e-9

#: Laenge eines Intervalls in der Konfiguration: Untergrenze und Obergrenze.
_INTERVALL_LAENGE: Final[int] = 2


class KonfigurationsFehler(RuntimeError):
    """Die Konfiguration ist unvollstaendig, widerspruechlich oder unbekannt."""


def projekt_wurzel() -> Path:
    """Gibt das Wurzelverzeichnis des Repositories zurueck.

    Returns:
        Den Ordner, der ``config/``, ``src/`` und ``data/`` enthaelt.
    """
    return Path(__file__).resolve().parents[2]


#: Pfad der ausgelieferten Konfiguration.
STANDARD_KONFIGURATION: Final[Path] = projekt_wurzel() / "config" / "default.yaml"


@dataclass(frozen=True, slots=True)
class Pfade:
    """Verzeichnisse des Projekts, absolut aufgeloest.

    Attributes:
        wurzel: Wurzelverzeichnis des Repositories.
        reference: Versionierte Referenztabellen.
        runs: Laufartefakte (nicht versioniert).
        results: Tabellen und Abbildungen fuer die Arbeit.
    """

    wurzel: Path
    reference: Path
    runs: Path
    results: Path


@dataclass(frozen=True, slots=True)
class AngeboteJeAnfrage:
    """Spanne der Angebotszeilen je Vergleichsanfrage.

    Attributes:
        minimum: Kleinste Anzahl Angebote.
        maximum: Groesste Anzahl Angebote.
    """

    minimum: int
    maximum: int


@dataclass(frozen=True, slots=True)
class Schwellen:
    """Schwellenwerte der heuristischen Regeln (Erkennbarkeitsgrad C2).

    Sie stehen in der Konfiguration und nicht im Quelltext, weil sie in der
    Arbeit diskutiert und variiert werden.

    Attributes:
        r022_wohnflaeche: Plausibler Korridor der Wohnflaeche in Quadratmetern.
        r031_toleranz_eur: Toleranz der Beitragsarithmetik.
        r036_toleranz_je_rate_eur: Toleranz je Rate; skaliert mit der Ratenanzahl.
        r047_spreizung_max: Hoechstverhaeltnis groesster zu kleinster Rate je Anfrage.
        r048_zuers_toleranz_relativ: Relative Abweichung der ZUERS-Verteilung.
        r053_korridor_kfz_eur: Plausibler Jahresbeitragskorridor Kfz.
        r053_korridor_hausrat_eur: Plausibler Jahresbeitragskorridor Hausrat.
        r054_faktor: Verdachtsfaktor fuer Monats- statt Jahresbeitrag.
        r054_toleranz_relativ: Relative Toleranz um diesen Faktor.
    """

    r022_wohnflaeche: tuple[int, int]
    r031_toleranz_eur: Decimal
    r036_toleranz_je_rate_eur: Decimal
    r047_spreizung_max: float
    r048_zuers_toleranz_relativ: float
    r053_korridor_kfz_eur: tuple[Decimal, Decimal]
    r053_korridor_hausrat_eur: tuple[Decimal, Decimal]
    r054_faktor: float
    r054_toleranz_relativ: float


@dataclass(frozen=True, slots=True)
class Referenzdaten:
    """Umfang der einmalig erzeugten Referenztabellen.

    Attributes:
        n_plz: Anzahl der Postleitzahlen in ``plz_ort.csv``.
        n_zulassungsbezirke: Anzahl der Zulassungsbezirke.
        n_typklassen: Anzahl der HSN/TSN-Kombinationen.
        n_hersteller: Anzahl der Hersteller (bestimmt die Zahl der HSN).
        n_vu: Anzahl der Versicherungsunternehmen.
        zuers_anteile: Anteile der ZUERS-Zonen 1 bis 4.
    """

    n_plz: int
    n_zulassungsbezirke: int
    n_typklassen: int
    n_hersteller: int
    n_vu: int
    zuers_anteile: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class Config:
    """Vollstaendige, eingefrorene Konfiguration eines Laufs.

    Attributes:
        stichtag: Referenzdatum aller Altersberechnungen. Ersetzt die Systemzeit
            in jeder fachlichen Berechnung (Architekturregel A2).
        master_seed: Wurzel des hierarchischen Seedings.
        n_anfragen: Anzahl der Vergleichsanfragen je Lauf.
        angebote_je_anfrage: Spanne der Angebotszeilen je Anfrage.
        sparten_verteilung: Ziehungsgewichte je Sparte, aufsteigend nach
            Spartenschluessel geordnet.
        pfade: Absolut aufgeloeste Verzeichnisse.
        schwellen: Schwellenwerte der heuristischen Regeln.
        referenzdaten: Umfang der Referenztabellen.
        quelldatei: Datei, aus der diese Konfiguration geladen wurde.
    """

    stichtag: date
    master_seed: int
    n_anfragen: int
    angebote_je_anfrage: AngeboteJeAnfrage
    sparten_verteilung: Mapping[str, float]
    pfade: Pfade
    schwellen: Schwellen
    referenzdaten: Referenzdaten
    quelldatei: Path


# ---------------------------------------------------------------------------
# Hilfsfunktionen zum strikten Auslesen
# ---------------------------------------------------------------------------


def _abschnitt(rohdaten: Mapping[str, Any], schluessel: str, kontext: str) -> Mapping[str, Any]:
    """Liest einen verschachtelten Abschnitt und prueft seinen Typ."""
    wert = _pflichtwert(rohdaten, schluessel, kontext)
    if not isinstance(wert, Mapping):
        raise KonfigurationsFehler(f"{kontext}{schluessel} muss ein Abschnitt sein, war {wert!r}")
    return wert


def _pflichtwert(rohdaten: Mapping[str, Any], schluessel: str, kontext: str) -> Any:  # noqa: ANN401
    """Liest einen Pflichtschluessel; fehlt er, bricht der Ladevorgang ab."""
    if schluessel not in rohdaten:
        raise KonfigurationsFehler(
            f"Pflichtschluessel {kontext}{schluessel} fehlt in der Konfiguration"
        )
    return rohdaten[schluessel]


def _pruefe_schluessel(rohdaten: Mapping[str, Any], erlaubt: Sequence[str], kontext: str) -> None:
    """Bricht ab, wenn unbekannte Schluessel vorhanden sind."""
    unbekannt = sorted(set(rohdaten) - set(erlaubt))
    if unbekannt:
        raise KonfigurationsFehler(
            f"Unbekannte Schluessel in {kontext or 'der Konfiguration'}: {unbekannt}. "
            f"Erlaubt sind: {sorted(erlaubt)}"
        )


def _als_int(wert: Any, name: str, *, mindestens: int | None = None) -> int:  # noqa: ANN401
    """Wandelt einen Wert in ``int`` um und prueft eine optionale Untergrenze."""
    if isinstance(wert, bool) or not isinstance(wert, int):
        raise KonfigurationsFehler(f"{name} muss eine ganze Zahl sein, war {wert!r}")
    if mindestens is not None and wert < mindestens:
        raise KonfigurationsFehler(f"{name} muss mindestens {mindestens} sein, war {wert}")
    return wert


def _als_float(wert: Any, name: str, *, groesser_null: bool = False) -> float:  # noqa: ANN401
    """Wandelt einen Wert in ``float`` um."""
    if isinstance(wert, bool) or not isinstance(wert, int | float):
        raise KonfigurationsFehler(f"{name} muss eine Zahl sein, war {wert!r}")
    zahl = float(wert)
    if groesser_null and zahl <= 0:
        raise KonfigurationsFehler(f"{name} muss groesser als null sein, war {zahl}")
    return zahl


def _als_decimal(wert: Any, name: str) -> Decimal:  # noqa: ANN401
    """Wandelt einen Wert ueber seine Zeichenkettendarstellung in ``Decimal`` um.

    Der Umweg ueber ``str`` ist Absicht: ``Decimal(0.02)`` traegt die
    Binaerentwicklung des ``float`` mit, ``Decimal("0.02")`` nicht.
    """
    if isinstance(wert, bool) or not isinstance(wert, int | float | str):
        raise KonfigurationsFehler(f"{name} muss eine Zahl sein, war {wert!r}")
    try:
        return Decimal(str(wert))
    except ArithmeticError as fehler:
        raise KonfigurationsFehler(f"{name} ist kein gueltiger Dezimalwert: {wert!r}") from fehler


def _als_paar_int(wert: Any, name: str) -> tuple[int, int]:  # noqa: ANN401
    """Liest ein zweielementiges Intervall aus ganzen Zahlen."""
    unten, oben = _paar(wert, name)
    grenzen = (_als_int(unten, f"{name}[0]"), _als_int(oben, f"{name}[1]"))
    if grenzen[0] >= grenzen[1]:
        raise KonfigurationsFehler(f"{name} muss aufsteigend sein, war {grenzen}")
    return grenzen


def _als_paar_decimal(wert: Any, name: str) -> tuple[Decimal, Decimal]:  # noqa: ANN401
    """Liest ein zweielementiges Intervall aus Dezimalwerten."""
    unten, oben = _paar(wert, name)
    grenzen = (_als_decimal(unten, f"{name}[0]"), _als_decimal(oben, f"{name}[1]"))
    if grenzen[0] >= grenzen[1]:
        raise KonfigurationsFehler(f"{name} muss aufsteigend sein, war {grenzen}")
    return grenzen


def _paar(wert: Any, name: str) -> tuple[Any, Any]:  # noqa: ANN401
    """Prueft, dass ein Wert eine Folge aus genau zwei Elementen ist."""
    if isinstance(wert, str) or not isinstance(wert, Sequence) or len(wert) != _INTERVALL_LAENGE:
        raise KonfigurationsFehler(f"{name} muss aus genau zwei Werten bestehen, war {wert!r}")
    return wert[0], wert[1]


# ---------------------------------------------------------------------------
# Abschnittsweises Einlesen
# ---------------------------------------------------------------------------


def _lies_stichtag(rohdaten: Mapping[str, Any]) -> date:
    """Liest den Stichtag und laesst nur ein reines Datum zu."""
    wert = _pflichtwert(rohdaten, "stichtag", "")
    if isinstance(wert, date):
        return wert
    if isinstance(wert, str):
        try:
            return date.fromisoformat(wert)
        except ValueError as fehler:
            raise KonfigurationsFehler(
                f"stichtag muss im Format JJJJ-MM-TT stehen, war {wert!r}"
            ) from fehler
    raise KonfigurationsFehler(f"stichtag muss ein Datum sein, war {wert!r}")


def _lies_pfade(rohdaten: Mapping[str, Any], wurzel: Path) -> Pfade:
    """Liest den Abschnitt ``pfade`` und loest ihn gegen das Wurzelverzeichnis auf."""
    abschnitt = _abschnitt(rohdaten, "pfade", "")
    erlaubt = ("reference", "runs", "results")
    _pruefe_schluessel(abschnitt, erlaubt, "pfade: ")

    def aufloesen(schluessel: str) -> Path:
        wert = _pflichtwert(abschnitt, schluessel, "pfade.")
        if not isinstance(wert, str) or not wert:
            raise KonfigurationsFehler(f"pfade.{schluessel} muss ein Pfad sein, war {wert!r}")
        kandidat = Path(wert)
        return kandidat if kandidat.is_absolute() else (wurzel / kandidat)

    return Pfade(
        wurzel=wurzel,
        reference=aufloesen("reference"),
        runs=aufloesen("runs"),
        results=aufloesen("results"),
    )


def _lies_angebote(rohdaten: Mapping[str, Any]) -> AngeboteJeAnfrage:
    """Liest den Abschnitt ``angebote_je_anfrage``."""
    abschnitt = _abschnitt(rohdaten, "angebote_je_anfrage", "")
    _pruefe_schluessel(abschnitt, ("min", "max"), "angebote_je_anfrage: ")
    minimum = _als_int(
        _pflichtwert(abschnitt, "min", "angebote_je_anfrage."),
        "angebote_je_anfrage.min",
        mindestens=1,
    )
    maximum = _als_int(
        _pflichtwert(abschnitt, "max", "angebote_je_anfrage."),
        "angebote_je_anfrage.max",
        mindestens=1,
    )
    if minimum > maximum:
        raise KonfigurationsFehler(
            f"angebote_je_anfrage.min ({minimum}) darf nicht groesser sein als max ({maximum})"
        )
    return AngeboteJeAnfrage(minimum=minimum, maximum=maximum)


def _lies_sparten(rohdaten: Mapping[str, Any]) -> Mapping[str, float]:
    """Liest die Spartenverteilung und prueft Katalog und Summe.

    Die Rueckgabe ist nach Spartenschluessel aufsteigend geordnet. Damit haengt
    keine spaetere Ziehung an der Reihenfolge in der YAML-Datei
    (Architekturregel A2).
    """
    abschnitt = _abschnitt(rohdaten, "sparten_verteilung", "")
    bekannt = {sparte.value for sparte in Sparte}
    unbekannt = sorted(set(map(str, abschnitt)) - bekannt)
    if unbekannt:
        raise KonfigurationsFehler(
            f"sparten_verteilung enthaelt unbekannte Sparten: {unbekannt}. "
            f"Bekannt sind: {sorted(bekannt)}"
        )
    fehlend = sorted(bekannt - set(map(str, abschnitt)))
    if fehlend:
        raise KonfigurationsFehler(f"sparten_verteilung ist unvollstaendig, es fehlen: {fehlend}")

    gewichte = {
        str(schluessel): _als_float(wert, f"sparten_verteilung.{schluessel}")
        for schluessel, wert in abschnitt.items()
    }
    negativ = sorted(name for name, wert in gewichte.items() if wert < 0)
    if negativ:
        raise KonfigurationsFehler(f"sparten_verteilung darf nicht negativ sein: {negativ}")
    summe = sum(gewichte.values())
    if abs(summe - 1.0) > _SUMMEN_TOLERANZ:
        raise KonfigurationsFehler(f"sparten_verteilung muss auf 1 summieren, war {summe}")
    return MappingProxyType(dict(sorted(gewichte.items())))


def _lies_schwellen(rohdaten: Mapping[str, Any]) -> Schwellen:
    """Liest den Abschnitt ``schwellen``."""
    abschnitt = _abschnitt(rohdaten, "schwellen", "")
    erlaubt = (
        "r022_wohnflaeche",
        "r031_toleranz_eur",
        "r036_toleranz_je_rate_eur",
        "r047_spreizung_max",
        "r048_zuers_toleranz_relativ",
        "r053_korridor_kfz_eur",
        "r053_korridor_hausrat_eur",
        "r054_faktor",
        "r054_toleranz_relativ",
    )
    _pruefe_schluessel(abschnitt, erlaubt, "schwellen: ")

    def hole(name: str) -> Any:  # noqa: ANN401
        return _pflichtwert(abschnitt, name, "schwellen.")

    return Schwellen(
        r022_wohnflaeche=_als_paar_int(hole("r022_wohnflaeche"), "schwellen.r022_wohnflaeche"),
        r031_toleranz_eur=_als_decimal(hole("r031_toleranz_eur"), "schwellen.r031_toleranz_eur"),
        r036_toleranz_je_rate_eur=_als_decimal(
            hole("r036_toleranz_je_rate_eur"), "schwellen.r036_toleranz_je_rate_eur"
        ),
        r047_spreizung_max=_als_float(
            hole("r047_spreizung_max"), "schwellen.r047_spreizung_max", groesser_null=True
        ),
        r048_zuers_toleranz_relativ=_als_float(
            hole("r048_zuers_toleranz_relativ"),
            "schwellen.r048_zuers_toleranz_relativ",
            groesser_null=True,
        ),
        r053_korridor_kfz_eur=_als_paar_decimal(
            hole("r053_korridor_kfz_eur"), "schwellen.r053_korridor_kfz_eur"
        ),
        r053_korridor_hausrat_eur=_als_paar_decimal(
            hole("r053_korridor_hausrat_eur"), "schwellen.r053_korridor_hausrat_eur"
        ),
        r054_faktor=_als_float(hole("r054_faktor"), "schwellen.r054_faktor", groesser_null=True),
        r054_toleranz_relativ=_als_float(
            hole("r054_toleranz_relativ"), "schwellen.r054_toleranz_relativ", groesser_null=True
        ),
    )


def _lies_referenzdaten(rohdaten: Mapping[str, Any]) -> Referenzdaten:
    """Liest den Abschnitt ``referenzdaten``."""
    abschnitt = _abschnitt(rohdaten, "referenzdaten", "")
    anzahlen = ("n_plz", "n_zulassungsbezirke", "n_typklassen", "n_hersteller", "n_vu")
    erlaubt = (*anzahlen, "zuers_anteile")
    _pruefe_schluessel(abschnitt, erlaubt, "referenzdaten: ")
    zahlen = {
        name: _als_int(
            _pflichtwert(abschnitt, name, "referenzdaten."),
            f"referenzdaten.{name}",
            mindestens=1,
        )
        for name in anzahlen
    }
    if zahlen["n_zulassungsbezirke"] > zahlen["n_plz"]:
        raise KonfigurationsFehler(
            "referenzdaten.n_zulassungsbezirke darf nicht groesser sein als n_plz "
            f"({zahlen['n_zulassungsbezirke']} > {zahlen['n_plz']})"
        )
    if zahlen["n_hersteller"] > zahlen["n_typklassen"]:
        raise KonfigurationsFehler(
            "referenzdaten.n_hersteller darf nicht groesser sein als n_typklassen "
            f"({zahlen['n_hersteller']} > {zahlen['n_typklassen']})"
        )

    roh_anteile = _pflichtwert(abschnitt, "zuers_anteile", "referenzdaten.")
    if isinstance(roh_anteile, str) or not isinstance(roh_anteile, Sequence):
        raise KonfigurationsFehler(
            f"referenzdaten.zuers_anteile muss eine Liste sein, war {roh_anteile!r}"
        )
    if len(roh_anteile) != len(ZUERS_ZONEN):
        raise KonfigurationsFehler(
            f"referenzdaten.zuers_anteile braucht genau {len(ZUERS_ZONEN)} Werte, "
            f"hatte {len(roh_anteile)}"
        )
    anteile = tuple(
        _als_float(wert, f"referenzdaten.zuers_anteile[{i}]", groesser_null=True)
        for i, wert in enumerate(roh_anteile)
    )
    if abs(sum(anteile) - 1.0) > _SUMMEN_TOLERANZ:
        raise KonfigurationsFehler(
            f"referenzdaten.zuers_anteile muss auf 1 summieren, war {sum(anteile)}"
        )
    return Referenzdaten(
        n_plz=zahlen["n_plz"],
        n_zulassungsbezirke=zahlen["n_zulassungsbezirke"],
        n_typklassen=zahlen["n_typklassen"],
        n_hersteller=zahlen["n_hersteller"],
        n_vu=zahlen["n_vu"],
        zuers_anteile=(anteile[0], anteile[1], anteile[2], anteile[3]),
    )


def lade_config(pfad: Path | None = None) -> Config:
    """Laedt die Konfiguration und prueft sie vollstaendig.

    Args:
        pfad: Pfad zur YAML-Datei. Ohne Angabe wird
            :data:`STANDARD_KONFIGURATION` geladen.

    Returns:
        Die eingefrorene :class:`Config`.

    Raises:
        KonfigurationsFehler: Wenn die Datei fehlt, kein Abbildungsdokument
            enthaelt, Pflichtschluessel fehlen, unbekannte Schluessel auftauchen
            oder ein Wert ausserhalb seines zulaessigen Bereichs liegt.
    """
    quelle = (pfad or STANDARD_KONFIGURATION).resolve()
    if not quelle.is_file():
        raise KonfigurationsFehler(f"Konfigurationsdatei nicht gefunden: {quelle}")
    try:
        rohdaten = yaml.safe_load(quelle.read_text(encoding="utf-8"))
    except yaml.YAMLError as fehler:
        raise KonfigurationsFehler(f"Konfiguration ist kein gueltiges YAML: {quelle}") from fehler
    if not isinstance(rohdaten, Mapping):
        raise KonfigurationsFehler(
            f"Konfiguration muss ein Abbildungsdokument sein, war {type(rohdaten).__name__}"
        )

    erlaubt = (
        "stichtag",
        "master_seed",
        "n_anfragen",
        "angebote_je_anfrage",
        "sparten_verteilung",
        "pfade",
        "schwellen",
        "referenzdaten",
    )
    _pruefe_schluessel(rohdaten, erlaubt, "")

    return _baue(rohdaten, quelle)


def _baue(rohdaten: Mapping[str, Any], quelle: Path) -> Config:
    """Setzt die geprueften Abschnitte zur Konfiguration zusammen."""
    return Config(
        stichtag=_lies_stichtag(rohdaten),
        master_seed=_als_int(
            _pflichtwert(rohdaten, "master_seed", ""), "master_seed", mindestens=0
        ),
        n_anfragen=_als_int(_pflichtwert(rohdaten, "n_anfragen", ""), "n_anfragen", mindestens=1),
        angebote_je_anfrage=_lies_angebote(rohdaten),
        sparten_verteilung=_lies_sparten(rohdaten),
        pfade=_lies_pfade(rohdaten, projekt_wurzel()),
        schwellen=_lies_schwellen(rohdaten),
        referenzdaten=_lies_referenzdaten(rohdaten),
        quelldatei=quelle,
    )


def als_dict(config: Config) -> dict[str, Any]:
    """Bildet die Konfiguration auf JSON- und YAML-faehige Werte ab.

    Pfade werden **relativ zum Projektwurzelverzeichnis** abgelegt. Absolute
    Pfade waeren rechnerabhaengig und wuerden den Hashwert eines Manifests von
    der Arbeitsumgebung abhaengig machen (Architekturregel A2). Geldbetraege
    werden als Zeichenkette gefuehrt, damit die ``Decimal``-Darstellung nicht
    ueber einen ``float`` laeuft.

    Args:
        config: Geladene Konfiguration.

    Returns:
        Eine Abbildung mit denselben Schluesseln wie ``config/default.yaml``.
    """

    def relativ(pfad: Path) -> str:
        try:
            return pfad.relative_to(config.pfade.wurzel).as_posix()
        except ValueError:
            return pfad.name

    schwellen = config.schwellen
    return {
        "stichtag": config.stichtag.isoformat(),
        "master_seed": config.master_seed,
        "n_anfragen": config.n_anfragen,
        "angebote_je_anfrage": {
            "min": config.angebote_je_anfrage.minimum,
            "max": config.angebote_je_anfrage.maximum,
        },
        "sparten_verteilung": dict(config.sparten_verteilung),
        "pfade": {
            "reference": relativ(config.pfade.reference),
            "runs": relativ(config.pfade.runs),
            "results": relativ(config.pfade.results),
        },
        "schwellen": {
            "r022_wohnflaeche": list(schwellen.r022_wohnflaeche),
            "r031_toleranz_eur": str(schwellen.r031_toleranz_eur),
            "r036_toleranz_je_rate_eur": str(schwellen.r036_toleranz_je_rate_eur),
            "r047_spreizung_max": schwellen.r047_spreizung_max,
            "r048_zuers_toleranz_relativ": schwellen.r048_zuers_toleranz_relativ,
            "r053_korridor_kfz_eur": [str(wert) for wert in schwellen.r053_korridor_kfz_eur],
            "r053_korridor_hausrat_eur": [
                str(wert) for wert in schwellen.r053_korridor_hausrat_eur
            ],
            "r054_faktor": schwellen.r054_faktor,
            "r054_toleranz_relativ": schwellen.r054_toleranz_relativ,
        },
        "referenzdaten": {
            "n_plz": config.referenzdaten.n_plz,
            "n_zulassungsbezirke": config.referenzdaten.n_zulassungsbezirke,
            "n_typklassen": config.referenzdaten.n_typklassen,
            "n_hersteller": config.referenzdaten.n_hersteller,
            "n_vu": config.referenzdaten.n_vu,
            "zuers_anteile": list(config.referenzdaten.zuers_anteile),
        },
    }
