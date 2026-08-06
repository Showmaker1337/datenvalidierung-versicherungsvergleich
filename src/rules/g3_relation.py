"""G3 — Regeln auf Relationsebene (R-043 bis R-048).

Eine G3-Regel prueft eine Bedingung **zwischen Zeilen derselben Tabelle**: Ist die
Rangfolge eines Vergleichs vollstaendig, erscheint ein Tarif zweimal, gibt es genau
einen Versicherungsnehmer? Das sind Uniqueness- und Ordnungsbedingungen im Sinne
von Rahm und Do sowie DAMA UK.

Zwei Rueckgabekanaele
---------------------

Vier Regeln dieser Gruppe (R-043, R-045, R-046, R-047) melden neben den Zellen
zusaetzlich einen **satzbezogenen** Verstoss mit allen beteiligten ``row_id`` —
analog zum satzbasierten Ground Truth aus ``spec/03``, Abschnitt 4.2. Eine
doppelte Angebotszeile ist ein Verstoss ueber ein Zeilenpaar, nicht ueber eine
Zelle.

Zwei Regeln ausserhalb der Zellmetrik
-------------------------------------

R-047 und R-048 tragen ``in_zellmetrik=False``. R-047 weiss nicht, welches der n
Angebote das falsche ist; R-048 prueft eine Verteilung ueber den Gesamtdatensatz
und hat ueberhaupt keine verursachende Zelle. Beide werden als
**Diagnosekennzahl** gefuehrt. Wuerden sie in die Zellmetrik eingehen, muessten
sie entweder alle Zeilen einer Anfrage markieren — und die Precision
verschlechtern, ohne einen Detektionsfehler zu belegen — oder eine Zelle raten.
"""

from __future__ import annotations

from decimal import Decimal
from itertools import pairwise
from typing import TYPE_CHECKING, Any, Final

from src.common import wertebereiche as wb
from src.common.enums import Annahmeentscheidung, Rolle
from src.common.pfade import Schicht
from src.rules.modell import Befund, Befundsammler, Regel, gruppen, row_ids, werte

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    from src.rules.modell import Kontext

__all__ = ["REGELN"]


def _betrag(wert: Any) -> Decimal:  # noqa: ANN401
    """Wandelt einen Wert der typisierten Schicht in ein ``Decimal``."""
    return Decimal(str(wert))


# ---------------------------------------------------------------------------
# R-043 bis R-046 — Rangfolge, Duplikate, Rollen
# ---------------------------------------------------------------------------


def pruefe_r043(kontext: Kontext) -> Befund:
    """``rang`` je ``anfrage_id`` ist lueckenlos 1..n und eindeutig.

    ``n`` ist die Zahl der **bepreisten** Angebote. Ein abgelehntes Risiko hat
    keinen Preis und gehoert damit in keine Preisrangfolge; es traegt keinen Rang
    (README, Abschnitt "Getroffene Festlegungen").

    Drei Pruefungen decken die Bedingung vollstaendig ab: Sind alle n bepreisten
    Angebote geranged, sind die Raenge eindeutig und liegen sie in [1, n], dann
    ist die Folge zwangslaeufig eine Permutation von 1..n.
    """
    sammler = Befundsammler("R-043")
    rahmen = kontext.rahmen(Schicht.TYPED, "angebot")
    kennungen = row_ids(rahmen)
    raenge = werte(rahmen, "rang")
    entscheidungen = werte(rahmen, "annahmeentscheidung")

    for anfrage_id, positionen in gruppen(werte(rahmen, "anfrage_id")).items():
        anzahl = sum(1 for position in positionen if not _abgelehnt(entscheidungen[position]))
        auffaellig = _melde_einzelraenge(
            sammler,
            positionen=positionen,
            kennungen=kennungen,
            raenge=raenge,
            entscheidungen=entscheidungen,
            anzahl=anzahl,
        )
        auffaellig |= _melde_doppelte_raenge(
            sammler,
            anfrage_id=anfrage_id,
            positionen=positionen,
            kennungen=kennungen,
            raenge=raenge,
        )
        if auffaellig:
            sammler.melde_satz(
                "angebot",
                [kennungen[position] for position in positionen],
                f"Die Rangfolge der Anfrage {anfrage_id} ist nicht lueckenlos 1..{anzahl}",
            )
    return sammler.befund()


def _abgelehnt(entscheidung: Any) -> bool:  # noqa: ANN401
    """Gibt zurueck, ob eine Annahmeentscheidung eine Ablehnung ist.

    Eine leere Entscheidung gilt **nicht** als Ablehnung: Ohne Angabe ist das
    Angebot bepreist, und ein fehlender Rang bleibt damit ein Befund. Die leere
    Entscheidung selbst meldet R-057 beziehungsweise R-037.
    """
    return entscheidung is not None and str(entscheidung) == Annahmeentscheidung.ABLEHNUNG.value


def _melde_einzelraenge(  # noqa: PLR0913 - Rang, Entscheidung und Kennung gehen getrennt ein
    sammler: Befundsammler,
    *,
    positionen: Sequence[int],
    kennungen: Sequence[int],
    raenge: Sequence[Any],
    entscheidungen: Sequence[Any],
    anzahl: int,
) -> bool:
    """Meldet Raenge, die fuer sich genommen nicht in die Rangfolge passen."""
    auffaellig = False
    for position in positionen:
        rang = raenge[position]
        abgelehnt = _abgelehnt(entscheidungen[position])
        if abgelehnt and rang is not None:
            meldung = f"Abgelehntes Angebot traegt den Rang {rang}"
        elif not abgelehnt and rang is None:
            meldung = (
                f"Bepreistes Angebot ohne Rang in einer Anfrage mit {anzahl} bepreisten Angeboten"
            )
        elif rang is not None and not 1 <= int(rang) <= anzahl:
            meldung = f"rang={int(rang)} liegt ausserhalb von [1, {anzahl}]"
        else:
            continue
        sammler.melde("angebot", kennungen[position], ("rang",), meldung)
        auffaellig = True
    return auffaellig


def _melde_doppelte_raenge(
    sammler: Befundsammler,
    *,
    anfrage_id: Any,  # noqa: ANN401
    positionen: Sequence[int],
    kennungen: Sequence[int],
    raenge: Sequence[Any],
) -> bool:
    """Meldet mehrfach vergebene Raenge als je einen Verstoss ueber alle Beteiligten."""
    belegung: dict[int, list[int]] = {}
    for position in positionen:
        if raenge[position] is None:
            continue
        belegung.setdefault(int(raenge[position]), []).append(position)

    auffaellig = False
    for rang, beteiligte in belegung.items():
        if len(beteiligte) < 2:  # noqa: PLR2004
            continue
        sammler.melde_zellen(
            "angebot",
            [(kennungen[position], "rang") for position in beteiligte],
            f"rang={rang} ist in der Anfrage {anfrage_id} mehrfach vergeben",
        )
        auffaellig = True
    return auffaellig


def pruefe_r044(kontext: Kontext) -> Befund:
    """``rang`` ist aufsteigend nach ``zahlbeitrag_rate_eur`` sortiert.

    Ein Preisvergleich sortiert nach Preis — ein Denial Constraint im Sinne von
    Chu et al. Gemeldet wird je Inversion **ein** Verstoss ueber beide beteiligten
    Zeilen: Welche der beiden falsch steht, kann die Regel nicht entscheiden.

    Gleiche Raten sind zulaessig; geprueft wird auf nicht fallende, nicht auf
    streng steigende Werte.
    """
    sammler = Befundsammler("R-044")
    rahmen = kontext.rahmen(Schicht.TYPED, "angebot")
    kennungen = row_ids(rahmen)
    raenge = werte(rahmen, "rang")
    raten = werte(rahmen, "zahlbeitrag_rate_eur")

    for positionen in gruppen(werte(rahmen, "anfrage_id")).values():
        geranged = [
            position
            for position in positionen
            if raenge[position] is not None and raten[position] is not None
        ]
        geordnet = sorted(geranged, key=lambda position: int(raenge[position]))
        for vorher, nachher in pairwise(geordnet):
            if _betrag(raten[vorher]) <= _betrag(raten[nachher]):
                continue
            sammler.melde_zellen(
                "angebot",
                [
                    (kennungen[vorher], "rang"),
                    (kennungen[vorher], "zahlbeitrag_rate_eur"),
                    (kennungen[nachher], "rang"),
                    (kennungen[nachher], "zahlbeitrag_rate_eur"),
                ],
                f"rang={int(raenge[vorher])} traegt die Rate {raten[vorher]}, der "
                f"nachfolgende rang={int(raenge[nachher])} die kleinere Rate "
                f"{raten[nachher]}",
            )
    return sammler.befund()


def pruefe_r045(kontext: Kontext) -> Befund:
    """Kein Duplikat ueber (``anfrage_id``, ``tarif_id``).

    Derselbe Tarif erscheint nicht zweimal im selben Vergleich.

    **Abgrenzung zur Held-out-Klasse HO1.** Diese Regel prueft *exakte* Duplikate
    ueber einen definierten Schluessel. Semantische Duplikate — dieselbe Person in
    zwei Schreibweisen — sind ausdruecklich nicht Gegenstand des Katalogs und
    erfordern Fuzzy-Matching (``spec/02``, Abschnitt "Held-out"). Ohne diese
    Abgrenzung wirkte die Hypothese "der Recall unterscheidet sich zwischen
    Fehlerklassen" trivial erfuellt.
    """
    sammler = Befundsammler("R-045")
    rahmen = kontext.rahmen(Schicht.TYPED, "angebot")
    kennungen = row_ids(rahmen)
    anfrage_ids = werte(rahmen, "anfrage_id")
    tarif_ids = werte(rahmen, "tarif_id")
    schluessel = [
        None if anfrage_ids[position] is None or tarif_ids[position] is None
        else (anfrage_ids[position], tarif_ids[position])
        for position in range(len(kennungen))
    ]
    for (anfrage_id, tarif_id), positionen in gruppen(schluessel).items():
        if len(positionen) < 2:  # noqa: PLR2004
            continue
        verstoss_id = sammler.melde_zellen(
            "angebot",
            [
                (kennungen[position], spalte)
                for position in positionen
                for spalte in ("anfrage_id", "tarif_id")
            ],
            f"Der Tarif {tarif_id} erscheint in der Anfrage {anfrage_id} "
            f"{len(positionen)}-mal",
        )
        sammler.melde_satz(
            "angebot",
            [kennungen[position] for position in positionen],
            f"Duplikat ueber (anfrage_id, tarif_id) = ({anfrage_id}, {tarif_id})",
            verstoss_id=verstoss_id,
        )
    return sammler.befund()


def pruefe_r046(kontext: Kontext) -> Befund:
    """Je ``anfrage_id`` existiert genau eine ``person`` mit ``rolle`` = VN.

    Zwei Versicherungsnehmer sind so falsch wie keiner. Fehlt der Satz ganz, kann
    die Regel **keine Zelle benennen** — es gibt keine; sie meldet dann
    ausschliesslich satzbezogen. Das ist kein Mangel der Regel, sondern die
    Eigenart fehlender Zeilen, und genau der Grund fuer den zweiten
    Rueckgabekanal.
    """
    sammler = Befundsammler("R-046")
    anfragen = kontext.rahmen(Schicht.TYPED, "anfrage")
    personen = kontext.rahmen(Schicht.TYPED, "person")
    person_kennungen = row_ids(personen)
    rollen = werte(personen, "rolle")

    vn_je_anfrage: dict[Any, list[int]] = {}
    for position, anfrage_id in enumerate(werte(personen, "anfrage_id")):
        if anfrage_id is None or rollen[position] is None:
            continue
        if str(rollen[position]) == Rolle.VN.value:
            vn_je_anfrage.setdefault(anfrage_id, []).append(position)

    for anfrage_id in werte(anfragen, "anfrage_id"):
        if anfrage_id is None:
            continue
        positionen = vn_je_anfrage.get(anfrage_id, [])
        if len(positionen) == 1:
            continue
        if positionen:
            verstoss_id = sammler.melde_zellen(
                "person",
                [(person_kennungen[position], "rolle") for position in positionen],
                f"Die Anfrage {anfrage_id} hat {len(positionen)} Personen mit rolle=VN",
            )
            sammler.melde_satz(
                "person",
                [person_kennungen[position] for position in positionen],
                f"Die Anfrage {anfrage_id} hat {len(positionen)} Versicherungsnehmer",
                verstoss_id=verstoss_id,
            )
        else:
            sammler.melde_satz(
                "person",
                [],
                f"Die Anfrage {anfrage_id} hat keine Person mit rolle=VN",
            )
    return sammler.befund()


# ---------------------------------------------------------------------------
# R-047 und R-048 — Diagnosekennzahlen ausserhalb der Zellmetrik
# ---------------------------------------------------------------------------


def pruefe_r047(kontext: Kontext) -> Befund:
    """Die Beitragsspreizung je Anfrage ueberschreitet den Schwellenwert nicht.

    ``max(zahlbeitrag_rate_eur) / min(...)`` je Anfrage bleibt unter der Schwelle
    aus ``config.schwellen.r047_spreizung_max``. Eine extreme Spreizung deutet auf
    einen Einheiten- oder Mappingfehler bei einem Anbieter hin.

    **Keine Zellmeldung.** Die Regel weiss nicht, welches der n Angebote das
    falsche ist — der Ausreisser koennte oben oder unten liegen. Sie meldet
    deshalb ausschliesslich satzbezogen und geht nicht in die Zellmetrik ein.
    """
    sammler = Befundsammler("R-047")
    rahmen = kontext.rahmen(Schicht.TYPED, "angebot")
    kennungen = row_ids(rahmen)
    raten = werte(rahmen, "zahlbeitrag_rate_eur")
    schwelle = Decimal(str(kontext.schwellen.r047_spreizung_max))

    for anfrage_id, positionen in gruppen(werte(rahmen, "anfrage_id")).items():
        bepreist = [position for position in positionen if raten[position] is not None]
        if len(bepreist) < 2:  # noqa: PLR2004
            continue
        betraege = [_betrag(raten[position]) for position in bepreist]
        kleinster, groesster = min(betraege), max(betraege)
        if kleinster <= 0 or groesster / kleinster <= schwelle:
            continue
        sammler.melde_satz(
            "angebot",
            [kennungen[position] for position in bepreist],
            f"Die Spreizung der Anfrage {anfrage_id} betraegt {groesster / kleinster:.2f} "
            f"({groesster} zu {kleinster}) und ueberschreitet die Schwelle {schwelle}",
        )
    return sammler.befund()


def pruefe_r048(kontext: Kontext) -> Befund:
    """Die empirische ZUERS-Verteilung weicht je Zone hoechstens relativ ab.

    Verglichen wird gegen die vom GDV publizierten Anteile
    (92,4 / 6,1 / 1,1 / 0,4 Prozent); die zulaessige **relative** Abweichung steht
    in ``config.schwellen.r048_zuers_toleranz_relativ``.

    **Relative statt absoluter Toleranz.** Fuenf Prozentpunkte wuerden Zone 4 einen
    Sprung von 0,4 auf 5,4 Prozent erlauben — Faktor 13,5 — und damit genau den
    Fall nicht fangen, fuer den die Regel gedacht ist.

    Eine Verteilungspruefung im Sinne der Metrik-Constraints von Schelter et al.
    Sie hat keine verursachende Zelle und geht deshalb nicht in die Zellmetrik ein.
    """
    sammler = Befundsammler("R-048")
    rahmen = kontext.rahmen(Schicht.TYPED, "risiko_hausrat")
    kennungen = row_ids(rahmen)
    zonen = werte(rahmen, "zuers_zone")
    vorhanden = [position for position, zone in enumerate(zonen) if zone is not None]
    if not vorhanden:
        return sammler.befund()

    toleranz = kontext.schwellen.r048_zuers_toleranz_relativ
    gesamt = len(vorhanden)
    for index, zone in enumerate(wb.ZUERS_ZONEN):
        erwartet = wb.ZUERS_ANTEILE_GDV[index]
        positionen = [position for position in vorhanden if int(zonen[position]) == zone]
        beobachtet = len(positionen) / gesamt
        abweichung = abs(beobachtet - erwartet) / erwartet
        if abweichung <= toleranz:
            continue
        sammler.melde_satz(
            "risiko_hausrat",
            [kennungen[position] for position in positionen],
            f"Zone {zone} ist mit {beobachtet:.4f} statt {erwartet:.4f} besetzt; die "
            f"relative Abweichung {abweichung:.2%} ueberschreitet die Toleranz "
            f"{toleranz:.2%}",
        )
    return sammler.befund()


# ---------------------------------------------------------------------------
# Registrierung
# ---------------------------------------------------------------------------

REGELN: Final[tuple[Regel, ...]] = (
    Regel(
        regel_id="R-043",
        beschreibung="rang je anfrage_id ist lueckenlos 1..n und eindeutig",
        entitaet="angebot",
        spalten=("rang",),
        granularitaet="G3",
        fehlerklasse_b="B5",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD", "DAMA"),
        fachliche_grundlage="Ein Vergleichsergebnis hat eine vollstaendige Rangfolge",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r043,
    ),
    Regel(
        regel_id="R-044",
        beschreibung="rang ist aufsteigend nach zahlbeitrag_rate_eur sortiert",
        entitaet="angebot",
        spalten=("rang", "zahlbeitrag_rate_eur"),
        granularitaet="G3",
        fehlerklasse_b="B4",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("CHU",),
        fachliche_grundlage="Ein Preisvergleich sortiert nach Preis",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r044,
    ),
    Regel(
        regel_id="R-045",
        beschreibung="Kein Duplikat ueber (anfrage_id, tarif_id)",
        entitaet="angebot",
        spalten=("anfrage_id", "tarif_id"),
        granularitaet="G3",
        fehlerklasse_b="B5",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD", "ABE", "DAMA"),
        fachliche_grundlage=(
            "Derselbe Tarif erscheint nicht zweimal im selben Vergleich. Abgrenzung zu HO1: "
            "exakte, nicht semantische Duplikate"
        ),
        schicht=Schicht.TYPED,
        pruefe=pruefe_r045,
    ),
    Regel(
        regel_id="R-046",
        beschreibung="Je anfrage_id existiert genau eine person mit rolle = VN",
        entitaet="person, anfrage",
        spalten=("rolle",),
        granularitaet="G3",
        fehlerklasse_b="B5",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD", "OLI"),
        fachliche_grundlage="Ein Vertrag hat genau einen Versicherungsnehmer",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r046,
    ),
    Regel(
        regel_id="R-047",
        beschreibung=(
            "max(zahlbeitrag_rate_eur) / min(...) je anfrage_id bleibt unter der Schwelle"
        ),
        entitaet="angebot",
        spalten=("zahlbeitrag_rate_eur",),
        granularitaet="G3",
        fehlerklasse_b="B3",
        erkennbarkeit_c="C2",
        schweregrad="WARNUNG",
        literatur=("ABE", "FOI"),
        fachliche_grundlage=(
            "Eine extreme Spreizung deutet auf einen Einheiten- oder Mappingfehler hin. "
            "Schwellenwert ist eine Modellannahme. Diagnosekennzahl ohne verursachende Zelle"
        ),
        schicht=Schicht.TYPED,
        pruefe=pruefe_r047,
        in_zellmetrik=False,
    ),
    Regel(
        regel_id="R-048",
        beschreibung=(
            "Die empirische Verteilung von zuers_zone weicht je Zone hoechstens relativ "
            "von (92,4 / 6,1 / 1,1 / 0,4) ab"
        ),
        entitaet="risiko_hausrat",
        spalten=("zuers_zone",),
        granularitaet="G3",
        fehlerklasse_b="B3",
        erkennbarkeit_c="C2",
        schweregrad="WARNUNG",
        literatur=("ABE",),
        fachliche_grundlage=(
            "Verteilungspruefung statt Einzelwertpruefung (Metrik-Constraints nach Schelter "
            "et al.). Relative statt absoluter Toleranz. Diagnosekennzahl ohne Zellbezug"
        ),
        schicht=Schicht.TYPED,
        pruefe=pruefe_r048,
        in_zellmetrik=False,
    ),
)
