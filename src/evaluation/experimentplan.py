"""Der Versuchsplan der Phase 6: Faktorstufen, Teilversuche, Einzellaeufe.

Dieses Modul liest ``config/experiment.yaml`` und faltet es zu einer flachen,
geordneten Liste von :class:`Lauf`. Es fuehrt **keinen** Lauf aus und importiert
nichts, was das koennte — insbesondere nichts aus ``src.injector`` und nichts aus
``src.generator``. Die Ausfuehrung steht in ``scripts/run_experiment.py``, weil
sie den Injektor braucht und ``scripts/`` die aeusserste Schicht ist.

Warum der Plan ein eigenes Modul ist und nicht im Runner steht
---------------------------------------------------------------

Der Plan ist die Stelle, an der die Zahl der Laeufe entsteht. Steht er im Runner,
ist er nur ueber einen vollstaendigen Lauf pruefbar; als eigenes Modul ist er in
Millisekunden testbar — und die Frage "wie viele Laeufe sind das eigentlich, und
sind ihre Kennungen alle verschieden?" wird beantwortet, **bevor** Stunden
Rechenzeit vergehen. :func:`laeufe` prueft die Eindeutigkeit der ``run_id``
deshalb hart: Zwei Laeufe mit derselben Kennung wuerden einander im
Laufverzeichnis ueberschreiben, und der zweite saehe aus wie eine Wiederholung
des ersten.

Zwei Varianzquellen, zwei Indizes
----------------------------------

Der Hauptversuch haelt den Basisdatensatz fest und variiert nur den
Injektionsstrom — er misst die **Injektionsvarianz**. Der Teilversuch T5 macht es
umgekehrt: fester Injektionsstrom, zwanzig verschiedene Basisdatensaetze —
**Datenvarianz**. Beides in einer einzigen Wiederholungsnummer zu fuehren, waere
ein Fehler: Variierten beide zugleich, maesse T5 die Summe aus beidem und der
Vergleich der beiden Streuungen (Abbildung 8) verlore seinen Sinn.

Der Plan traegt deshalb zwei getrennte Indizes:

``injektions_index``
    Geht in ``seed_inject`` ein. Ist im Regelfall gleich der Wiederholungsnummer.
``basis_index``
    Waehlt den Basisdatensatz. ``0`` ist der kanonische Datensatz aus
    ``wurzel_seeds(master_seed).basis`` — derselbe, den ``scripts/generate.py``
    und ``scripts/inject.py`` ohne weitere Angabe erzeugen. Nur T5 setzt ihn
    ungleich null.

Der Regelfall ``basis_index = 0`` ist damit **byteweise** derselbe Lauf, den
``python scripts/inject.py --serie ... --klasse ... --rate ... --wdh ...`` von
Hand erzeugt. Genau das prueft ``tests/test_experiment.py`` und genau darauf
beruht die Aussage, dass jeder Einzellauf des Experiments unabhaengig
nachvollziehbar ist.

Was nicht in der ``run_id`` steht
----------------------------------

``n_anfragen``, ``max_fehler`` und die Liste der Verfahren gehen **nicht** in die
Kennung ein — das Schema aus Phase 4b kennt nur Serie, Design, Segment, Rate und
Wiederholung. Wer eine dieser drei Groessen variiert, muss deshalb das Design
mitvariieren, sonst ueberschreiben sich zwei Laeufe. Der Teilversuch T4
(Skalierung) tut das: Seine drei Datensatzgroessen sind drei Eintraege mit den
Designkennungen ``N1``, ``N2`` und ``N3``. :func:`laeufe` faengt einen Verstoss
gegen diese Regel ueber die Eindeutigkeitspruefung ab.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import yaml

from src.common.pfade import MISCHMODUS, experiment_run_id
from src.evaluation.modell import AuswertungsFehler
from src.evaluation.varianten import ALLE_VARIANTEN_IDS, klasse_je_variante

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping, Sequence

__all__ = [
    "ALLE_VARIANTEN",
    "HAUPTVERSUCH",
    "MODUS_KLASSE",
    "MODUS_VARIANTE",
    "STANDARD_PLAN",
    "Lauf",
    "PlanFehler",
    "Statistikvorgaben",
    "Teilversuch",
    "Versuchsplan",
    "lade_plan",
    "laeufe",
]

#: Kennung des Hauptversuchs in Ergebnisdateien und in ``--nur-teilversuch``.
HAUPTVERSUCH: Final[str] = "haupt"

#: Die beiden Laufmodi. Wortgleich mit ``scripts/inject.py``.
#:
#: Bewusst hier noch einmal festgelegt und nicht importiert: ``src/`` darf nicht
#: aus ``scripts/`` importieren, das waere die falsche Richtung. Ein Test
#: (``tests/test_experiment.py``) haelt beide Seiten aneinander.
MODUS_KLASSE: Final[str] = "klasse"
MODUS_VARIANTE: Final[str] = "variante"

#: Platzhalter in ``gruppen``, der alle sechzig Injektionsvarianten meint.
ALLE_VARIANTEN: Final[str] = "alle"

#: Pfad des ausgelieferten Versuchsplans.
STANDARD_PLAN: Final[Path] = Path(__file__).resolve().parents[2] / "config" / "experiment.yaml"

#: Pflichtschluessel eines Teilversuchseintrags.
_TEILVERSUCH_SCHLUESSEL: Final[frozenset[str]] = frozenset(
    {
        "kennung",
        "titel",
        "design",
        "modus",
        "gruppen",
        "raten",
        "verfahren",
        "wiederholungen",
        "n_anfragen",
        "basis_variiert",
        "max_fehler",
        "messe_speicher",
    }
)

#: Pflichtschluessel des Abschnitts ``statistik``.
_STATISTIK_SCHLUESSEL: Final[frozenset[str]] = frozenset(
    {"alpha", "bootstrap_resamples", "seed_bootstrap"}
)

#: Pflichtschluessel der obersten Ebene.
_PLAN_SCHLUESSEL: Final[frozenset[str]] = frozenset(
    {
        "serie",
        "worker",
        "schreibe_detections",
        "statistik",
        "hauptversuch",
        "teilversuche",
    }
)


class PlanFehler(AuswertungsFehler):
    """Der Versuchsplan ist unvollstaendig, widerspruechlich oder unbekannt.

    Erbt bewusst von :class:`~src.evaluation.modell.AuswertungsFehler`: Ein
    fehlerhafter Plan ist ein Fehler der Auswertung und keine gesonderte
    Kategorie. Wer die Auswertung als Ganzes absichert, faengt ihn mit.
    """


@dataclass(frozen=True, slots=True)
class Lauf:
    """Ein einzelner Experimentlauf mit allen seinen Faktorstufen.

    Attributes:
        teilversuch: :data:`HAUPTVERSUCH` oder die Kennung eines Teilversuchs.
        serie: Name der Versuchsserie; erstes Pfadsegment.
        design: Kennbuchstabe des Varianzdesigns; zweites Pfadsegment.
        modus: :data:`MODUS_KLASSE` oder :data:`MODUS_VARIANTE`.
        klasse: Fehlerklasse oder ``"mix"``.
        variante: Injektionsvariante im Variantenmodus, sonst ``None``.
        fehlerrate: Fehlerrate als Anteil.
        wiederholung: Nummer der Wiederholung; drittes Pfadsegment.
        basis_index: Auswahl des Basisdatensatzes; ``0`` ist der kanonische.
        injektions_index: Geht in ``seed_inject`` ein.
        verfahren: Auszuwertende Verfahren in Berichtsreihenfolge.
        n_anfragen: Groesse des Basisdatensatzes.
        max_fehler: Absolute Obergrenze der Verfaelschungen, oder ``None``.
        messe_speicher: Schaltet die ``tracemalloc``-Messung ein.
    """

    teilversuch: str
    serie: str
    design: str
    modus: str
    klasse: str
    variante: str | None
    fehlerrate: float
    wiederholung: int
    basis_index: int
    injektions_index: int
    verfahren: tuple[str, ...]
    n_anfragen: int
    max_fehler: int | None
    messe_speicher: bool

    @property
    def segment(self) -> str:
        """Gibt das dritte Pfadsegment zurueck: Variante oder Klasse.

        Returns:
            Die Variantenkennung im Variantenmodus, sonst die Fehlerklasse.
        """
        return self.klasse if self.variante is None else self.variante

    @property
    def run_id(self) -> str:
        """Gibt die Kennung des Laufs nach dem Schema aus Phase 4b zurueck.

        Returns:
            Die Kennung, zum Beispiel ``"s01_A_F3_r0200_w07"``.
        """
        return experiment_run_id(
            self.serie, self.design, self.segment, self.fehlerrate, self.wiederholung
        )


@dataclass(frozen=True, slots=True)
class Teilversuch:
    """Ein vollfaktorieller Block des Versuchsplans.

    Der Hauptversuch ist selbst einer — er unterscheidet sich nur durch seine
    Kennung. Ein zweiter Typ fuer "den grossen Block" haette dieselben Felder und
    dieselbe Entfaltung; er waere eine Verdopplung ohne Gegenwert.

    Attributes:
        kennung: Kurzkennung, etwa ``"T3"`` oder :data:`HAUPTVERSUCH`.
        titel: Ein Satz fuer die Fortschrittsausgabe und ``t7_teilversuche``.
        design: Kennbuchstabe des Varianzdesigns.
        modus: :data:`MODUS_KLASSE` oder :data:`MODUS_VARIANTE`.
        gruppen: Fehlerklassen beziehungsweise Injektionsvarianten.
        raten: Fehlerraten als Anteile.
        verfahren: Auszuwertende Verfahren.
        wiederholungen: Zahl der Wiederholungen je Zelle.
        n_anfragen: Groesse des Basisdatensatzes.
        basis_variiert: Variiert der Basisdatensatz statt des Injektionsstroms?
        max_fehler: Absolute Obergrenze der Verfaelschungen, oder ``None``.
        messe_speicher: Schaltet die ``tracemalloc``-Messung ein. Sie verlangsamt
            jeden Lauf spuerbar und ist deshalb nur dort eingeschaltet, wo der
            Speicherbedarf berichtet wird — im Teilversuch T4.
    """

    kennung: str
    titel: str
    design: str
    modus: str
    gruppen: tuple[str, ...]
    raten: tuple[float, ...]
    verfahren: tuple[str, ...]
    wiederholungen: int
    n_anfragen: int
    basis_variiert: bool
    max_fehler: int | None
    messe_speicher: bool

    @property
    def zellen(self) -> int:
        """Gibt die Zahl der Zellen zurueck: Gruppen mal Raten mal Verfahren.

        Returns:
            Die Zellzahl im Sinne des Versuchsplans. Sie ist **nicht** die Zahl
            der Laeufe: Ein Lauf wertet alle Verfahren auf demselben
            verfaelschten Datensatz aus.
        """
        return len(self.gruppen) * len(self.raten) * len(self.verfahren)

    @property
    def anzahl_laeufe(self) -> int:
        """Gibt die Zahl der tatsaechlich auszufuehrenden Laeufe zurueck.

        Returns:
            Gruppen mal Raten mal Wiederholungen.
        """
        return len(self.gruppen) * len(self.raten) * self.wiederholungen


@dataclass(frozen=True, slots=True)
class Statistikvorgaben:
    """Vorgaben der Inferenzstatistik.

    Attributes:
        alpha: Irrtumswahrscheinlichkeit, ``0.05`` fuer das 95-Prozent-Niveau.
        bootstrap_resamples: Zahl der Bootstrap-Ziehungen.
        seed_bootstrap: Nummer des Zufallsstroms der Bootstrap-Ziehungen. Ohne
            festen Seed waere das Konfidenzintervall bei jedem Aufruf ein anderes
            (Architekturregel A2).
    """

    alpha: float
    bootstrap_resamples: int
    seed_bootstrap: int


@dataclass(frozen=True, slots=True)
class Versuchsplan:
    """Der vollstaendige Plan aus ``config/experiment.yaml``.

    Attributes:
        serie: Name der Versuchsserie; erstes Pfadsegment aller Laeufe.
        worker: Vorgabewert der Prozesszahl; die Kommandozeile darf ihn
            uebersteuern.
        schreibe_detections: Legt die Rohmeldungen je Verfahren ab.
        statistik: Vorgaben der Inferenzstatistik.
        hauptversuch: Der vollfaktorielle Hauptversuch.
        teilversuche: Die Teilversuche in Ausfuehrungsreihenfolge.
    """

    serie: str
    worker: int
    schreibe_detections: bool
    statistik: Statistikvorgaben
    hauptversuch: Teilversuch
    teilversuche: tuple[Teilversuch, ...]

    @property
    def bloecke(self) -> tuple[Teilversuch, ...]:
        """Gibt Hauptversuch und Teilversuche in Ausfuehrungsreihenfolge zurueck.

        Returns:
            Den Hauptversuch zuerst, dann die Teilversuche.
        """
        return (self.hauptversuch, *self.teilversuche)


# ---------------------------------------------------------------------------
# Einlesen
# ---------------------------------------------------------------------------


def _pruefe_schluessel(abschnitt: Mapping[str, Any], erwartet: frozenset[str], wo: str) -> None:
    """Prueft einen Abschnitt auf genau die erwarteten Schluessel.

    Weder fehlende noch unbekannte Schluessel werden geduldet — dieselbe
    Strenge wie in :mod:`src.common.config`. Ein Tippfehler im Versuchsplan soll
    auffallen und nicht wirkungslos bleiben; ein wirkungsloser ``wiederholungen``
    -Schluessel waere eine stillschweigende Stichprobenreduktion.

    Args:
        abschnitt: Der eingelesene Abschnitt.
        erwartet: Die Pflichtschluessel.
        wo: Bezeichnung des Abschnitts fuer die Fehlermeldung.

    Raises:
        PlanFehler: Bei fehlenden oder unbekannten Schluesseln.
    """
    vorhanden = set(abschnitt)
    fehlend = sorted(erwartet - vorhanden)
    unbekannt = sorted(vorhanden - erwartet)
    if fehlend or unbekannt:
        teile = []
        if fehlend:
            teile.append(f"fehlend: {fehlend}")
        if unbekannt:
            teile.append(f"unbekannt: {unbekannt}")
        raise PlanFehler(
            f"Der Abschnitt {wo} des Versuchsplans ist fehlerhaft — {'; '.join(teile)}."
        )


def _abschnitt(inhalt: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    """Liest einen Abschnitt und stellt sicher, dass er eine Abbildung ist."""
    wert = inhalt.get(name)
    if not isinstance(wert, dict):
        raise PlanFehler(f"Der Versuchsplan braucht den Abschnitt {name!r} als Abbildung.")
    return wert


def _gruppen(eintrag: Mapping[str, Any], modus: str, wo: str) -> tuple[str, ...]:
    """Loest die Gruppenangabe eines Teilversuchs auf.

    Args:
        eintrag: Der Teilversuchseintrag.
        modus: Laufmodus des Teilversuchs.
        wo: Bezeichnung fuer die Fehlermeldung.

    Returns:
        Die Fehlerklassen beziehungsweise Injektionsvarianten.

    Raises:
        PlanFehler: Wenn die Angabe leer ist, keine Liste, oder im
            Variantenmodus eine unbekannte Variante nennt.
    """
    roh = eintrag["gruppen"]
    if roh == ALLE_VARIANTEN:
        if modus != MODUS_VARIANTE:
            raise PlanFehler(
                f"{wo}: gruppen: {ALLE_VARIANTEN!r} gilt nur mit modus: {MODUS_VARIANTE!r}."
            )
        return ALLE_VARIANTEN_IDS
    if not isinstance(roh, list) or not roh or not all(isinstance(wert, str) for wert in roh):
        raise PlanFehler(f"{wo}: 'gruppen' muss eine nicht leere Liste von Namen sein.")
    gruppen = tuple(str(wert) for wert in roh)
    if modus == MODUS_VARIANTE:
        unbekannt = sorted(set(gruppen) - set(ALLE_VARIANTEN_IDS))
        if unbekannt:
            raise PlanFehler(f"{wo}: unbekannte Injektionsvarianten {unbekannt}.")
    return gruppen


def _zahlenliste(eintrag: Mapping[str, Any], name: str, wo: str) -> tuple[float, ...]:
    """Liest eine nicht leere Liste positiver Zahlen."""
    roh = eintrag[name]
    if not isinstance(roh, list) or not roh:
        raise PlanFehler(f"{wo}: {name!r} muss eine nicht leere Liste sein.")
    werte = []
    for wert in roh:
        if not isinstance(wert, (int, float)) or isinstance(wert, bool) or wert <= 0:
            raise PlanFehler(f"{wo}: {name!r} enthaelt den unzulaessigen Wert {wert!r}.")
        werte.append(float(wert))
    return tuple(werte)


def _namensliste(eintrag: Mapping[str, Any], name: str, wo: str) -> tuple[str, ...]:
    """Liest eine nicht leere Liste von Namen."""
    roh = eintrag[name]
    if not isinstance(roh, list) or not roh or not all(isinstance(wert, str) for wert in roh):
        raise PlanFehler(f"{wo}: {name!r} muss eine nicht leere Liste von Namen sein.")
    return tuple(str(wert) for wert in roh)


def _ganzzahl(eintrag: Mapping[str, Any], name: str, wo: str, *, mindestens: int) -> int:
    """Liest eine ganze Zahl mit Untergrenze."""
    wert = eintrag[name]
    if not isinstance(wert, int) or isinstance(wert, bool) or wert < mindestens:
        raise PlanFehler(f"{wo}: {name!r} muss eine ganze Zahl >= {mindestens} sein, war {wert!r}.")
    return wert


def _wahrheitswert(eintrag: Mapping[str, Any], name: str, wo: str) -> bool:
    """Liest einen Wahrheitswert."""
    wert = eintrag[name]
    if not isinstance(wert, bool):
        raise PlanFehler(f"{wo}: {name!r} muss true oder false sein, war {wert!r}.")
    return wert


def _teilversuch(eintrag: Mapping[str, Any], wo: str) -> Teilversuch:
    """Baut einen Teilversuch aus seinem Eintrag im Versuchsplan.

    Args:
        eintrag: Der eingelesene Eintrag.
        wo: Bezeichnung fuer die Fehlermeldung.

    Returns:
        Den Teilversuch.

    Raises:
        PlanFehler: Bei jeder Unstimmigkeit im Eintrag.
    """
    _pruefe_schluessel(eintrag, _TEILVERSUCH_SCHLUESSEL, wo)
    modus = str(eintrag["modus"])
    if modus not in (MODUS_KLASSE, MODUS_VARIANTE):
        raise PlanFehler(f"{wo}: 'modus' muss {MODUS_KLASSE!r} oder {MODUS_VARIANTE!r} sein.")
    max_fehler = eintrag["max_fehler"]
    if max_fehler is not None and (not isinstance(max_fehler, int) or max_fehler < 1):
        raise PlanFehler(f"{wo}: 'max_fehler' muss null oder eine positive ganze Zahl sein.")
    return Teilversuch(
        kennung=str(eintrag["kennung"]),
        titel=str(eintrag["titel"]),
        design=str(eintrag["design"]),
        modus=modus,
        gruppen=_gruppen(eintrag, modus, wo),
        raten=_zahlenliste(eintrag, "raten", wo),
        verfahren=_namensliste(eintrag, "verfahren", wo),
        wiederholungen=_ganzzahl(eintrag, "wiederholungen", wo, mindestens=1),
        n_anfragen=_ganzzahl(eintrag, "n_anfragen", wo, mindestens=1),
        basis_variiert=_wahrheitswert(eintrag, "basis_variiert", wo),
        max_fehler=None if max_fehler is None else int(max_fehler),
        messe_speicher=_wahrheitswert(eintrag, "messe_speicher", wo),
    )


def lade_plan(pfad: Path | None = None) -> Versuchsplan:
    """Liest den Versuchsplan.

    Args:
        pfad: Pfad der Plandatei; ``None`` nimmt :data:`STANDARD_PLAN`.

    Returns:
        Den geprueften Plan.

    Raises:
        PlanFehler: Wenn die Datei fehlt, kein Woerterbuch enthaelt oder ein
            Abschnitt unvollstaendig ist. Bewusst keine Vorgabewerte: Ein
            fehlender Schluessel ``wiederholungen`` waere sonst eine
            stillschweigende Stichprobenreduktion.
    """
    quelle = STANDARD_PLAN if pfad is None else pfad
    if not quelle.is_file():
        raise PlanFehler(
            f"Versuchsplan nicht gefunden: {quelle}. Der ausgelieferte Plan liegt unter "
            f"{STANDARD_PLAN.relative_to(STANDARD_PLAN.parents[1])}."
        )
    inhalt = yaml.safe_load(quelle.read_text(encoding="utf-8"))
    if not isinstance(inhalt, dict):
        raise PlanFehler(f"Der Versuchsplan {quelle} enthaelt kein Woerterbuch.")
    _pruefe_schluessel(inhalt, _PLAN_SCHLUESSEL, "oberste Ebene")

    statistik_roh = _abschnitt(inhalt, "statistik")
    _pruefe_schluessel(statistik_roh, _STATISTIK_SCHLUESSEL, "statistik")
    alpha = statistik_roh["alpha"]
    if not isinstance(alpha, float) or not 0.0 < alpha < 1.0:
        raise PlanFehler(f"statistik: 'alpha' muss zwischen 0 und 1 liegen, war {alpha!r}.")

    teilversuche_roh = inhalt["teilversuche"]
    if not isinstance(teilversuche_roh, list):
        raise PlanFehler(
            "Der Versuchsplan braucht den Schluessel 'teilversuche' als Liste. Eine **leere**"
            " Liste ist zulaessig — ein Plan darf aus dem Hauptversuch allein bestehen —, ein"
            " fehlender Schluessel dagegen nicht: Er waere von einem vergessenen Teilversuch"
            " nicht zu unterscheiden."
        )

    plan = Versuchsplan(
        serie=str(inhalt["serie"]),
        worker=_ganzzahl(inhalt, "worker", "oberste Ebene", mindestens=1),
        schreibe_detections=_wahrheitswert(inhalt, "schreibe_detections", "oberste Ebene"),
        statistik=Statistikvorgaben(
            alpha=float(alpha),
            bootstrap_resamples=_ganzzahl(
                statistik_roh, "bootstrap_resamples", "statistik", mindestens=100
            ),
            seed_bootstrap=_ganzzahl(statistik_roh, "seed_bootstrap", "statistik", mindestens=0),
        ),
        hauptversuch=_teilversuch(_abschnitt(inhalt, "hauptversuch"), "hauptversuch"),
        teilversuche=tuple(
            _teilversuch(eintrag, f"teilversuche[{nummer}]")
            for nummer, eintrag in enumerate(teilversuche_roh)
        ),
    )
    _pruefe_designs(plan)
    return plan


def _pruefe_designs(plan: Versuchsplan) -> None:
    """Prueft, dass jeder Block eine eigene Designkennung traegt.

    Die Auswertung ordnet eine Ergebniszeile ueber ihr Varianzdesign einem Block
    zu (:func:`src.evaluation.ergebnisse.lade_ergebnisse`) — das Langformat kennt
    keine Blockkennung, weil der Injektor nichts von Teilversuchen weiss. Zwei
    Bloecke mit derselben Designkennung machten diese Zuordnung mehrdeutig, und
    die Ergebnisse zweier Teilversuche landeten in derselben Tabellenzeile.

    Args:
        plan: Der eingelesene Plan.

    Raises:
        PlanFehler: Wenn eine Designkennung mehrfach vorkommt.
    """
    gesehen: dict[str, str] = {}
    for block in plan.bloecke:
        vorher = gesehen.get(block.design)
        if vorher is not None:
            raise PlanFehler(
                f"Die Designkennung {block.design!r} wird von zwei Bloecken benutzt: "
                f"{vorher} und {block.kennung}. Die Auswertung ordnet eine Ergebniszeile "
                "ueber ihr Design einem Block zu; zwei Bloecke mit demselben Design waeren "
                "nicht mehr auseinanderzuhalten."
            )
        gesehen[block.design] = block.kennung


# ---------------------------------------------------------------------------
# Entfaltung
# ---------------------------------------------------------------------------


def _laeufe_eines_blocks(plan: Versuchsplan, block: Teilversuch) -> list[Lauf]:
    """Faltet einen Block zu seinen Einzellaeufen auf.

    Die Reihenfolge ist Gruppe, dann Rate, dann Wiederholung — dieselbe, in der
    ein Mensch die Tabelle lesen wuerde. Sie hat auf das Ergebnis keinen
    Einfluss: Jeder Lauf leitet seinen Seed allein aus seinen Faktorstufen ab
    (:func:`~src.common.seeding.lauf_seed`).

    Args:
        plan: Der Versuchsplan; liefert Serie und Modus.
        block: Der aufzufaltende Block.

    Returns:
        Die Einzellaeufe des Blocks.
    """
    zuordnung = klasse_je_variante()
    im_variantenmodus = block.modus == MODUS_VARIANTE
    gebaut: list[Lauf] = []
    for gruppe in block.gruppen:
        klasse = zuordnung[gruppe] if im_variantenmodus else gruppe
        variante = gruppe if im_variantenmodus else None
        gebaut.extend(
            Lauf(
                teilversuch=block.kennung,
                serie=plan.serie,
                design=block.design,
                modus=block.modus,
                klasse=klasse,
                variante=variante,
                fehlerrate=rate,
                wiederholung=wiederholung,
                basis_index=wiederholung + 1 if block.basis_variiert else 0,
                injektions_index=0 if block.basis_variiert else wiederholung,
                verfahren=block.verfahren,
                n_anfragen=block.n_anfragen,
                max_fehler=block.max_fehler,
                messe_speicher=block.messe_speicher,
            )
            for rate in block.raten
            for wiederholung in range(block.wiederholungen)
        )
    return gebaut


def laeufe(plan: Versuchsplan, nur: Sequence[str] | None = None) -> tuple[Lauf, ...]:
    """Faltet den Versuchsplan zu seinen Einzellaeufen auf.

    Args:
        plan: Der geprueste Versuchsplan.
        nur: Kennungen der auszufuehrenden Bloecke, oder ``None`` fuer alle.
            :data:`HAUPTVERSUCH` waehlt den Hauptversuch.

    Returns:
        Alle Einzellaeufe in Ausfuehrungsreihenfolge.

    Raises:
        PlanFehler: Wenn eine angeforderte Kennung nicht existiert, oder wenn
            zwei Laeufe dieselbe ``run_id`` traegen. Der zweite Fall waere
            besonders heimtueckisch: Beide schrieben in dasselbe
            Laufverzeichnis, und der zweite saehe aus wie eine Wiederholung des
            ersten statt wie eine eigene Messung.
    """
    bekannt = {block.kennung: block for block in plan.bloecke}
    if nur is None:
        gewaehlt = list(plan.bloecke)
    else:
        unbekannt = sorted(set(nur) - set(bekannt))
        if unbekannt:
            raise PlanFehler(
                f"Unbekannte Teilversuche: {unbekannt}. Bekannt sind: {sorted(bekannt)}."
            )
        gewaehlt = [block for block in plan.bloecke if block.kennung in set(nur)]

    gebaut = [lauf for block in gewaehlt for lauf in _laeufe_eines_blocks(plan, block)]

    gesehen: dict[str, Lauf] = {}
    for lauf in gebaut:
        vorher = gesehen.get(lauf.run_id)
        if vorher is not None:
            raise PlanFehler(
                f"Zwei Laeufe tragen die Kennung {lauf.run_id!r}: {vorher.teilversuch} und "
                f"{lauf.teilversuch}. Die run_id kodiert weder n_anfragen noch max_fehler noch "
                "die Verfahrensliste; wer eine davon variiert, muss das Design mitvariieren."
            )
        gesehen[lauf.run_id] = lauf
    return tuple(gebaut)


def klassen_des_hauptversuchs(plan: Versuchsplan) -> tuple[str, ...]:
    """Gibt die Fehlerklassen des Hauptversuchs zurueck.

    Args:
        plan: Der Versuchsplan.

    Returns:
        Die Klassen in Planreihenfolge; ``"mix"`` und Varianten kommen im
        Hauptversuch nicht vor.
    """
    return tuple(
        gruppe for gruppe in plan.hauptversuch.gruppen if gruppe != MISCHMODUS
    )
