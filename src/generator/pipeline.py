"""Orchestrierung des Datengenerators.

Die Reihenfolge der Schritte ist die Abhaengigkeitskette aus spec/01: Erst die
Tarifstammdaten, dann Anfragerahmen und Anschrift, dann Person, Risiko, Angebot
und Zahlung. Nichts wird unabhaengig je Feld gezogen, wo die Domaene eine
Abhaengigkeit vorgibt.

Zwei Schritte verdienen eine eigene Begruendung.

**Postleitzahl und ZUERS-Zone.** Fuer die Hausrat-Anfragen wird die Postleitzahl
nach ZUERS-Zone geschichtet gezogen: Die Zellzahlen je Zone stehen vorab fest,
gezogen wird nur die Postleitzahl innerhalb der Zone. Grund ist Zone 4 mit einem
Anteil von 0,4 Prozent. Bei 3.000 Hausrat-Zeilen sind das zwoelf erwartete Faelle
bei einer Streuung von rund 3,5 — eine gewoehnliche Ziehung verfehlt die von
R-048 geforderte relative Toleranz von 30 Prozent in etwa jedem dritten Lauf. Die
Randverteilung bleibt die belegte des GDV; nur die Stichprobenstreuung entfaellt.

**Pflichtfeldprofil.** Zum Schluss werden Felder geleert, die fuer die jeweilige
Quellschnittstelle als optional gelten (spec/01, Abschnitt 5). Das ist Teil des
**sauberen** Datensatzes und kein Fehler: Ohne diesen Schritt waere jedes Feld
ueberall gefuellt, der Datensatz unrealistisch homogen und R-057 ohne Gegenstand.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import TYPE_CHECKING, Final

from src.common import referenz
from src.common.enums import Quellschnittstelle, ist_kfz_sparte, schadenfreie_jahre
from src.common.pfade import (
    CLEAN_MANIFEST,
    REFERENZ_DATEIEN,
    Schicht,
    clean_verzeichnis,
    entitaet_pfad,
    pruefe_run_id,
    sha256_dataframe,
    sha256_datei,
)
from src.common.pflichtfelder import (
    BLANKO_WAHRSCHEINLICHKEIT,
    optionale_felder,
    profil_des_kanals,
)
from src.common.seeding import faker_instanz, generator, seed_als_int, teilstrom
from src.common.serialisierung import ENTITAETEN, leere_zellen, serialisiere
from src.generator import anfrage as anfrage_modul
from src.generator import angebot as angebot_modul
from src.generator import person as person_modul
from src.generator import risiko_hausrat as hausrat_modul
from src.generator import risiko_kfz as kfz_modul
from src.generator import tarif as tarif_modul
from src.generator import zahlung as zahlung_modul
from src.generator.verteilungen import exakte_aufteilung

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    import pandas as pd
    from numpy.random import Generator, SeedSequence

    from src.common.config import Config

__all__ = ["erzeuge_datensatz", "schreibe_datensatz"]

# ---------------------------------------------------------------------------
# Teilstroeme
#
# Feste Nummern: Eine neue Ziehung bekommt eine neue Nummer, damit die uebrigen
# Stroeme unveraendert bleiben (Architekturregel A2, siehe src/common/seeding.py).
# ---------------------------------------------------------------------------
_STROM_TARIF: Final[int] = 0
_STROM_ANFRAGE: Final[int] = 1
_STROM_ANSCHRIFT: Final[int] = 2
_STROM_PERSON: Final[int] = 3
_STROM_RISIKO_KFZ: Final[int] = 4
_STROM_RISIKO_HAUSRAT: Final[int] = 5
_STROM_ANGEBOT: Final[int] = 6
_STROM_ZAHLUNG: Final[int] = 7
_STROM_PFLICHTFELDER: Final[int] = 8
_STROM_FAKER_PERSON: Final[int] = 9
_STROM_FAKER_ZAHLUNG: Final[int] = 10
_STROM_ANFRAGE_ABHAENGIG: Final[int] = 11

#: Entitaeten, deren Profilfelder am Eingangskanal der Anfrage haengen.
#:
#: ``angebot`` fehlt hier bewusst: Dort gilt die Quellschnittstelle des liefernden
#: Anbieters, und die steht als Spalte in der Zeile selbst.
_ANFRAGESEITIGE_ENTITAETEN: Final[tuple[str, ...]] = (
    "person",
    "risiko_kfz",
    "risiko_hausrat",
    "zahlung",
)


def _pflichtalter(alter: int | None, index: int) -> int:
    """Gibt das Alter des Versicherungsnehmers zurueck; in den Kfz-Sparten ist es Pflicht.

    Raises:
        ValueError: Wenn das Alter fehlt. Das kann nur eintreten, wenn eine
            juristische Person in eine Kfz-Sparte geraten ist — ausgeschlossen
            durch :mod:`src.generator.person`, hier aber trotzdem geprueft.
    """
    if alter is None:
        raise ValueError(
            f"Anfrage {index}: Kfz-Sparte ohne Alter des Versicherungsnehmers. "
            "Juristische Personen sind in den Kfz-Sparten ausgeschlossen."
        )
    return alter


def _anschriften(
    rng: Generator,
    *,
    sparten: Sequence[str],
    plz_ort: pd.DataFrame,
    zuers_zonen: pd.DataFrame,
) -> tuple[list[str], list[str], list[str], list[int]]:
    """Ordnet jeder Anfrage eine Postleitzahl samt abgeleiteten Merkmalen zu.

    Fuer die Hausrat-Anfragen wird nach ZUERS-Zone geschichtet gezogen (siehe
    Modul-Docstring), fuer die uebrigen gleichverteilt ueber alle Postleitzahlen.

    Args:
        rng: Zufallsgenerator des Teilstroms "Anschrift".
        sparten: Spartenschluessel je Anfrage.
        plz_ort: Referenztabelle ``plz_ort``.
        zuers_zonen: Referenztabelle ``zuers_zonen``.

    Returns:
        Vier Folgen je Anfrage: Postleitzahl, Ortsname, Zulassungsbezirk und
        ZUERS-Zone.

    Raises:
        ValueError: Wenn eine Postleitzahl in ``zuers_zonen.csv`` fehlt.
    """
    plz_liste = [str(wert) for wert in plz_ort["plz"]]
    ort_je_plz = dict(zip(plz_liste, (str(wert) for wert in plz_ort["ort"]), strict=True))
    bezirk_je_plz = dict(
        zip(plz_liste, (str(wert) for wert in plz_ort["zulassungsbezirk"]), strict=True)
    )
    zone_je_plz = {
        str(wert): int(zone)
        for wert, zone in zip(zuers_zonen["plz"], zuers_zonen["zuers_zone"], strict=True)
    }
    fehlend = [wert for wert in plz_liste if wert not in zone_je_plz]
    if fehlend:
        raise ValueError(f"Postleitzahlen fehlen in zuers_zonen.csv: {fehlend[:5]}")

    zonen = sorted({zone_je_plz[wert] for wert in plz_liste})
    plz_je_zone = {
        zone: [wert for wert in plz_liste if zone_je_plz[wert] == zone] for zone in zonen
    }

    hausrat = [index for index, sparte in enumerate(sparten) if not ist_kfz_sparte(sparte)]
    zonenwahl = exakte_aufteilung(rng, len(hausrat), [len(plz_je_zone[zone]) for zone in zonen])
    innerhalb = rng.random(len(hausrat))
    gleichverteilt = rng.integers(0, len(plz_liste), size=len(sparten))

    zugeordnet = [plz_liste[int(wert)] for wert in gleichverteilt]
    for laufende, index in enumerate(hausrat):
        kandidaten = plz_je_zone[zonen[int(zonenwahl[laufende])]]
        zugeordnet[index] = kandidaten[int(float(innerhalb[laufende]) * len(kandidaten))]

    return (
        zugeordnet,
        [ort_je_plz[wert] for wert in zugeordnet],
        [bezirk_je_plz[wert] for wert in zugeordnet],
        [zone_je_plz[wert] for wert in zugeordnet],
    )


def _beitragssatz_je_sf_klasse(sf_beitragssatz: pd.DataFrame) -> dict[str, Decimal]:
    """Liest die Beitragssatztabelle als Abbildung SF-Klasse auf Prozentsatz."""
    return {
        str(klasse): Decimal(int(satz))
        for klasse, satz in zip(
            sf_beitragssatz["sf_klasse"], sf_beitragssatz["beitragssatz_prozent"], strict=True
        )
    }


def _baue_profile(  # noqa: PLR0913 - zwei Risikoentitaeten und ihre Zuordnung gehen ein
    *,
    sparten: Sequence[str],
    kfz_positionen: Sequence[int],
    hausrat_positionen: Sequence[int],
    risiko_kfz: kfz_modul.RisikoKfz,
    risiko_hausrat: hausrat_modul.RisikoHausrat,
    beitragssatz: Mapping[str, Decimal],
) -> list[angebot_modul.Risikoprofil]:
    """Stellt je Anfrage das Risikoprofil zusammen, das in den Beitrag eingeht.

    Raises:
        ValueError: Wenn eine Anfrage weder ein Kfz- noch ein Hausratrisiko hat.
    """
    profile: list[angebot_modul.Risikoprofil | None] = [None] * len(sparten)
    for laufende, index in enumerate(kfz_positionen):
        klasse = risiko_kfz.beitrags_sf_klasse[laufende]
        profile[index] = angebot_modul.Risikoprofil(
            sparte=sparten[index],
            typklasse=risiko_kfz.typklasse[laufende],
            regionalklasse=risiko_kfz.regionalklasse[laufende],
            sf_beitragssatz=beitragssatz[klasse] if klasse is not None else None,
            jahresfahrleistung_km=risiko_kfz.jahresfahrleistung_km[laufende],
        )
    for laufende, index in enumerate(hausrat_positionen):
        profile[index] = angebot_modul.Risikoprofil(
            sparte=sparten[index],
            versicherungssumme_eur=risiko_hausrat.versicherungssumme_eur[laufende],
            zuers_zone=risiko_hausrat.zuers_zone[laufende],
            bauartklasse=risiko_hausrat.bauartklasse[laufende],
            elementar_eingeschlossen=risiko_hausrat.elementar_eingeschlossen[laufende],
        )
    fehlend = [index for index, profil in enumerate(profile) if profil is None]
    if fehlend:
        raise ValueError(f"Anfragen ohne Risikoprofil: {fehlend[:5]}")
    return [profil for profil in profile if profil is not None]


def _blankomasken(
    rng: Generator,
    rahmen: pd.DataFrame,
    entitaet: str,
    optional_je_zeile: Sequence[tuple[str, ...]],
) -> dict[str, list[bool]]:
    """Bestimmt je Spalte, welche Zellen als optionales Profilfeld geleert werden."""
    masken: dict[str, list[bool]] = {}
    for spalte in rahmen.columns:
        feld = f"{entitaet}.{spalte}"
        zufall = rng.random(len(rahmen))
        maske = [
            feld in optional_je_zeile[zeile] and float(zufall[zeile]) < BLANKO_WAHRSCHEINLICHKEIT
            for zeile in range(len(rahmen))
        ]
        if any(maske):
            masken[spalte] = maske
    return masken


def _wende_pflichtfeldprofil_an(
    rng: Generator,
    datensatz: Mapping[str, pd.DataFrame],
    kanaele: Sequence[str],
    anfrage_ids: Sequence[str],
) -> dict[str, pd.DataFrame]:
    """Leert optionale Profilfelder mit :data:`BLANKO_WAHRSCHEINLICHKEIT`.

    Die anfrageseitigen Entitaeten folgen dem Profil des Eingangskanals, die
    Angebotszeilen dem Profil der Quellschnittstelle ihres Anbieters. Die
    Begruendung dieser Zweiteilung steht in ``src/common/pflichtfelder.py``.

    Args:
        rng: Zufallsgenerator des Teilstroms "Pflichtfelder".
        datensatz: Die sieben typisierten Datenrahmen.
        kanaele: Eingangskanal je Anfrage.
        anfrage_ids: Kennung je Anfrage, in derselben Reihenfolge wie ``kanaele``.

    Returns:
        Eine neue Abbildung mit den geleerten Zellen.
    """
    index_je_anfrage = {kennung: position for position, kennung in enumerate(anfrage_ids)}
    profil_je_anfrage = [profil_des_kanals(kanal) for kanal in kanaele]

    ergebnis = dict(datensatz)
    for entitaet in _ANFRAGESEITIGE_ENTITAETEN:
        rahmen = ergebnis[entitaet]
        optional_je_zeile = [
            optionale_felder(profil_je_anfrage[index_je_anfrage[str(kennung)]])
            for kennung in rahmen["anfrage_id"]
        ]
        ergebnis[entitaet] = leere_zellen(
            rahmen, _blankomasken(rng, rahmen, entitaet, optional_je_zeile)
        )

    angebote = ergebnis["angebot"]
    optional_je_angebot = [
        optionale_felder(Quellschnittstelle(str(wert)))
        for wert in angebote["quell_schnittstelle"]
    ]
    ergebnis["angebot"] = leere_zellen(
        angebote, _blankomasken(rng, angebote, "angebot", optional_je_angebot)
    )
    return ergebnis


def erzeuge_datensatz(config: Config, seed_basis: SeedSequence) -> dict[str, pd.DataFrame]:
    """Erzeugt den vollstaendig regelkonformen, sauberen Datensatz.

    Args:
        config: Geladene Konfiguration.
        seed_basis: Wurzel des Basisstroms, ueblicherweise ``wurzel_seeds(...).basis``.

    Returns:
        Eine Abbildung Entitaetsname auf den typisierten Datenrahmen, mit den
        Schluesseln ``anfrage``, ``person``, ``risiko_kfz``, ``risiko_hausrat``,
        ``tarif``, ``angebot`` und ``zahlung``.
    """
    plz_ort = referenz.lade_plz_ort(config)
    zuers = referenz.lade_zuers_zonen(config)
    typklassen = referenz.lade_typklassen(config)
    regionalklassen = referenz.lade_regionalklassen(config)
    vu_stammdaten = referenz.lade_vu_stammdaten(config)
    beitragssatz = _beitragssatz_je_sf_klasse(referenz.lade_sf_beitragssatz(config))

    tarifstamm = tarif_modul.erzeuge_tarife(
        config, generator(teilstrom(seed_basis, _STROM_TARIF)), vu_stammdaten
    )
    rahmen = anfrage_modul.erzeuge_rahmen(config, generator(teilstrom(seed_basis, _STROM_ANFRAGE)))
    plz_werte, ortsnamen, bezirke, zonen = _anschriften(
        generator(teilstrom(seed_basis, _STROM_ANSCHRIFT)),
        sparten=rahmen.sparte,
        plz_ort=plz_ort,
        zuers_zonen=zuers,
    )

    personen = person_modul.erzeuge_personen(
        config,
        generator(teilstrom(seed_basis, _STROM_PERSON)),
        faker_instanz(teilstrom(seed_basis, _STROM_FAKER_PERSON)),
        anfrage_ids=rahmen.anfrage_id,
        sparten=rahmen.sparte,
        plz_werte=plz_werte,
        ortsnamen=ortsnamen,
    )

    kfz_positionen = [index for index, wert in enumerate(rahmen.sparte) if ist_kfz_sparte(wert)]
    hausrat_positionen = [
        index for index, wert in enumerate(rahmen.sparte) if not ist_kfz_sparte(wert)
    ]

    risiko_kfz = kfz_modul.erzeuge_risiko_kfz(
        config,
        generator(teilstrom(seed_basis, _STROM_RISIKO_KFZ)),
        anfrage_ids=[rahmen.anfrage_id[index] for index in kfz_positionen],
        sparten=[rahmen.sparte[index] for index in kfz_positionen],
        zulassungsbezirke=[bezirke[index] for index in kfz_positionen],
        vn_alter=[_pflichtalter(personen.vn_alter[index], index) for index in kfz_positionen],
        vn_geburtsdatum=[personen.vn_geburtsdatum[index] for index in kfz_positionen],
        vn_fuehrerschein=[personen.vn_fuehrerschein[index] for index in kfz_positionen],
        typklassen=typklassen,
        regionalklassen=regionalklassen,
    )
    risiko_hausrat = hausrat_modul.erzeuge_risiko_hausrat(
        config,
        generator(teilstrom(seed_basis, _STROM_RISIKO_HAUSRAT)),
        anfrage_ids=[rahmen.anfrage_id[index] for index in hausrat_positionen],
        zuers_zonen=[zonen[index] for index in hausrat_positionen],
    )

    profile = _baue_profile(
        sparten=rahmen.sparte,
        kfz_positionen=kfz_positionen,
        hausrat_positionen=hausrat_positionen,
        risiko_kfz=risiko_kfz,
        risiko_hausrat=risiko_hausrat,
        beitragssatz=beitragssatz,
    )
    angebote = angebot_modul.erzeuge_angebote(
        config,
        generator(teilstrom(seed_basis, _STROM_ANGEBOT)),
        anfrage_ids=rahmen.anfrage_id,
        profile=profile,
        eingangszeitpunkte=rahmen.eingangszeitpunkt,
        tarifstamm=tarifstamm,
        vu_stammdaten=vu_stammdaten,
    )

    # Weist die Schadenfreiheitsklasse schadenfreie Jahre aus, setzt die Domaene
    # einen Vorvertrag voraus (spec/01, Abschnitt 3.1).
    vorvertrag_zwingend = [False] * len(rahmen.anfrage_id)
    for laufende, index in enumerate(kfz_positionen):
        jahre = schadenfreie_jahre(risiko_kfz.sf_klasse_hp[laufende])
        vorvertrag_zwingend[index] = jahre is not None and jahre > 0

    anfragen = anfrage_modul.baue_anfragen(
        generator(teilstrom(seed_basis, _STROM_ANFRAGE_ABHAENGIG)),
        rahmen,
        vn_person_id=personen.vn_person_id,
        zahlweise=angebote.zahlweise,
        vorvertrag_zwingend=vorvertrag_zwingend,
        vu_nummern=[str(wert) for wert in vu_stammdaten["vu_nummer"]],
        marktanteile=[float(wert) for wert in vu_stammdaten["marktanteil"]],
    )
    zahlungen = zahlung_modul.erzeuge_zahlungen(
        generator(teilstrom(seed_basis, _STROM_ZAHLUNG)),
        faker_instanz(teilstrom(seed_basis, _STROM_FAKER_ZAHLUNG)),
        anfrage_ids=rahmen.anfrage_id,
        eingangszeitpunkte=rahmen.eingangszeitpunkt,
        versicherungsbeginn=rahmen.versicherungsbeginn,
        vn_namen=personen.vn_name,
    )

    datensatz = {
        "anfrage": anfragen,
        "person": personen.rahmen,
        "risiko_kfz": risiko_kfz.rahmen,
        "risiko_hausrat": risiko_hausrat.rahmen,
        "tarif": tarifstamm.rahmen,
        "angebot": angebote.rahmen,
        "zahlung": zahlungen,
    }
    return _wende_pflichtfeldprofil_an(
        generator(teilstrom(seed_basis, _STROM_PFLICHTFELDER)),
        datensatz,
        rahmen.kanal,
        rahmen.anfrage_id,
    )


def _konfiguration_als_dict(config: Config) -> dict[str, object]:
    """Bildet die Konfiguration auf JSON-faehige Werte ab.

    Pfade werden **relativ zum Projektwurzelverzeichnis** abgelegt. Absolute Pfade
    waeren rechnerabhaengig und wuerden den Hashwert des Manifests von der
    Arbeitsumgebung abhaengig machen.
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


def schreibe_datensatz(
    config: Config,
    run_id: str,
    datensatz: Mapping[str, pd.DataFrame],
    seed_basis: SeedSequence,
) -> Path:
    """Schreibt beide Datenschichten als Parquet und dazu das Manifest.

    Args:
        config: Geladene Konfiguration.
        run_id: Kennung des Laufs.
        datensatz: Ergebnis von :func:`erzeuge_datensatz`.
        seed_basis: Verwendeter Basisstrom; geht in das Manifest ein.

    Returns:
        Das Verzeichnis ``data/runs/<run_id>/clean``.

    Raises:
        ValueError: Wenn eine Entitaet fehlt.
    """
    pruefe_run_id(run_id)
    fehlend = [name for name in ENTITAETEN if name not in datensatz]
    if fehlend:
        raise ValueError(f"Im Datensatz fehlen die Entitaeten: {fehlend}")
    ziel = clean_verzeichnis(config, run_id, anlegen=True)

    eintraege: dict[str, object] = {}
    for name in ENTITAETEN:
        typisiert = datensatz[name]
        roh = serialisiere(typisiert)
        schichten: dict[str, object] = {}
        for schicht, rahmen in ((Schicht.TYPED, typisiert), (Schicht.RAW, roh)):
            pfad = entitaet_pfad(config, run_id, schicht, name)
            rahmen.to_parquet(pfad, index=False)
            schichten[schicht.value] = {
                "datei": pfad.relative_to(ziel).as_posix(),
                "sha256_datei": sha256_datei(pfad),
                "sha256_rahmen": sha256_dataframe(rahmen),
            }
        eintraege[name] = {
            "zeilen": len(typisiert),
            "spalten": len(typisiert.columns),
            "schichten": schichten,
        }

    manifest = {
        "run_id": run_id,
        "erzeugt_von": "src.generator.pipeline",
        "seeds": {
            "master_seed": config.master_seed,
            "seed_basis": seed_als_int(seed_basis),
        },
        "konfiguration": _konfiguration_als_dict(config),
        "referenzdaten": {
            name: sha256_datei(config.pfade.reference / name) for name in REFERENZ_DATEIEN
        },
        "entitaeten": eintraege,
    }
    (ziel / CLEAN_MANIFEST).write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return ziel
