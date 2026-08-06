"""G5 — quellenuebergreifende Regeln (R-052 bis R-058).

Diese Gruppe ist der Kern der Domaene. Ein Vergleichssystem bezieht strukturell
gleichartige Sachverhalte ueber Schnittstellen mit unterschiedlicher Semantik,
Kodierung und Aktualitaet — GDV und BiPRO koexistieren. Das ist die
Lehrbuchdefinition eines Multi-Source-Problems nach Rahm und Do.

Vier der sieben Regeln sind schwellenwertbasiert (C2) und tragen deshalb den
Schweregrad WARNUNG: R-052, R-053, R-054 und R-057. Ihre Schwellen stehen in
``config.schwellen`` und nicht im Quelltext — sie werden in der Arbeit diskutiert
und muessen ohne Codeaenderung variierbar sein.

Zwei Regeln verdienen eine Vorbemerkung.

**R-053 prueft den Jahresbeitrag, nicht die Rate.** Die urspruengliche Fassung
zielte auf ``zahlbeitrag_rate_eur``; das war in sich widerspruechlich, weil die
Rate bei monatlicher Zahlweise ein Zwoelftel des Jahresbeitrags ist und damit
systematisch unterhalb eines Jahreskorridors laege. Die Korrektur fand **vor** dem
Freeze statt und ist in ``docs/iteration_log.md`` dokumentiert.

**R-054 vergleicht relational, nicht absolut.** Die Verwechslung von Monats- und
Jahresbeitrag ist ein Faktor 12. Ueber eine absolute Untergrenze ist sie nicht zu
finden — ein guenstiger Jahresbeitrag und ein teurer Monatsbeitrag liegen im selben
Zahlenbereich. Erst der Vergleich mit dem Median der uebrigen Angebote derselben
Anfrage macht den Faktor sichtbar.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Final

from src.common.enums import KFZ_SPARTEN, Anrede, Kanal, Quellschnittstelle, Sparte
from src.common.pfade import Schicht
from src.common.pflichtfelder import PROFILFELDER, ist_pflicht, profil_des_kanals
from src.rules.modell import Befund, Befundsammler, Regel, gruppen, row_ids, werte, zuordnung

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Sequence

    from src.rules.modell import Kontext

__all__ = ["REGELN"]

#: Spartenschluessel der Kfz-Sparten.
_KFZ: Final[frozenset[str]] = frozenset(sparte.value for sparte in KFZ_SPARTEN)

#: Die beiden Einheitenkonventionen des Hausrat-Selbstbehalts (R-052).
_SB_KONVENTIONEN: Final[tuple[tuple[str, str], ...]] = (
    ("sb_hausrat_prozent", "Prozent"),
    ("sb_hausrat_eur", "Betrag"),
)

#: Entitaeten der Anfrageseite; ihr Pflichtfeldprofil haengt am Eingangskanal (R-057).
_ANFRAGESEITIGE_ENTITAETEN: Final[tuple[str, ...]] = (
    "person",
    "risiko_kfz",
    "risiko_hausrat",
    "zahlung",
)

@dataclass(frozen=True, slots=True)
class _Anwendbarkeit:
    """Bedingung, unter der ein Profilfeld ueberhaupt belegt sein kann.

    Attributes:
        begruendung: Warum das Feld sonst leer bleibt — geht in die Meldung nicht
            ein, aber in die Lesbarkeit des Katalogs.
        sparten: Sparten, in denen das Feld vorkommt; ``None`` bedeutet "alle".
        ausschluss: Paar aus Spaltenname und Werten **derselben Zeile**, bei denen
            das Feld fachlich nicht existiert.
    """

    begruendung: str
    sparten: frozenset[str] | None = None
    ausschluss: tuple[str, frozenset[str]] | None = None


#: Anwendbarkeitsbedingung je Profilfeld (``spec/01``, Abschnitt 5.2; R-057).
#:
#: **Ohne diese Tabelle ist R-057 nicht brauchbar.** Ein Feld, das die Zweckbindung
#: ohnehin leer laesst, ist kein fehlender Wert, sondern ein nicht existierender.
#: Die Regel meldete sonst jede Haftpflichtzeile fuer einen Vollkasko-Selbstbehalt,
#: den es dort gar nicht geben kann — ein Fehlalarm, der ausschliesslich aus der
#: Pruefkonvention entstuende.
#:
#: Die Bedingungen selbst stehen im Datenmodell: Selbstbehalte nur in den
#: Kaskosparten (``spec/01``, Abschnitt 3.6), Familienstand nur bei natuerlichen
#: Personen (``spec/01``, Abschnitt 3.2 — eine juristische Person hat keinen).
_ANWENDBARKEIT: Final[dict[str, _Anwendbarkeit]] = {
    "angebot.sb_tk_eur": _Anwendbarkeit(
        begruendung="Teilkasko-Selbstbehalt existiert nur in den Kaskosparten",
        sparten=frozenset({Sparte.KFZ_VOLLKASKO.value, Sparte.KFZ_TEILKASKO.value}),
    ),
    "angebot.sb_vk_eur": _Anwendbarkeit(
        begruendung="Vollkasko-Selbstbehalt existiert nur in der Vollkasko",
        sparten=frozenset({Sparte.KFZ_VOLLKASKO.value}),
    ),
    "person.familienstand": _Anwendbarkeit(
        begruendung="Eine juristische Person hat keinen Familienstand",
        ausschluss=("anrede", frozenset({Anrede.FIRMA.value})),
    ),
}

#: Regionalklassenfelder und ihre Spalte in ``regionalklassen.csv`` (R-058).
_REGIONALKLASSENFELDER: Final[tuple[str, ...]] = (
    "regionalklasse_hp",
    "regionalklasse_tk",
    "regionalklasse_vk",
)


def _betrag(wert: Any) -> Decimal:  # noqa: ANN401
    """Wandelt einen Wert der typisierten Schicht in ein ``Decimal``."""
    return Decimal(str(wert))


def _median(betraege: Sequence[Decimal]) -> Decimal:
    """Berechnet den Median exakt in ``Decimal``.

    Bewusst nicht ueber ``statistics.median``: Das rechnet in ``float`` und
    verletzt die Vorgabe, Geld niemals als Gleitkommazahl zu fuehren
    (CLAUDE.md, Abschnitt 5).
    """
    geordnet = sorted(betraege)
    mitte = len(geordnet) // 2
    if len(geordnet) % 2 == 1:
        return geordnet[mitte]
    return (geordnet[mitte - 1] + geordnet[mitte]) / Decimal(2)


def _anwendbar(feld: str, sparte: str | None, ausschlusswert: Any) -> bool:  # noqa: ANN401
    """Gibt zurueck, ob ein Profilfeld in dieser Zeile ueberhaupt belegt sein kann.

    Args:
        feld: Profilfeld in der Schreibweise ``entitaet.feldname``.
        sparte: Sparte der zugehoerigen Anfrage, oder ``None``.
        ausschlusswert: Wert der Ausschlussspalte in derselben Zeile, oder ``None``,
            wenn das Feld keine Ausschlussbedingung hat.

    Returns:
        ``True``, wenn das Feld in dieser Zeile fachlich existiert.
    """
    bedingung = _ANWENDBARKEIT.get(feld)
    if bedingung is None:
        return True
    if bedingung.sparten is not None and (sparte is None or sparte not in bedingung.sparten):
        return False
    if bedingung.ausschluss is not None and ausschlusswert is not None:
        _, ausgeschlossen = bedingung.ausschluss
        if str(ausschlusswert) in ausgeschlossen:
            return False
    return True


def _ausschlusswerte(
    kontext: Kontext, entitaet: str, felder: Sequence[str]
) -> dict[str, list[Any]]:
    """Liest je Profilfeld die Spalte, ueber die seine Anwendbarkeit entschieden wird."""
    rahmen = kontext.rahmen(Schicht.TYPED, entitaet)
    ergebnis: dict[str, list[Any]] = {}
    for feld in felder:
        bedingung = _ANWENDBARKEIT.get(feld)
        if bedingung is None or bedingung.ausschluss is None:
            continue
        ergebnis[feld] = werte(rahmen, bedingung.ausschluss[0])
    return ergebnis


# ---------------------------------------------------------------------------
# R-052 bis R-054 — Einheiten, Korridore, Skalierung
# ---------------------------------------------------------------------------


def pruefe_r052(kontext: Kontext) -> Befund:
    """Alle Angebote einer Anfrage fuehren den Selbstbehalt in derselben Einheit.

    Anbieter A liefert den Selbstbehalt in Euro, Anbieter B in Prozent — der
    Vergleich wird dadurch unzulaessig. Das ist "Different value representations"
    nach Rahm und Do, die Fehlerklasse B7.

    **Gemeldet wird die Minderheit.** Welche Konvention die richtige ist, sagt
    keine Norm; die Regel nimmt die innerhalb der Anfrage ueberwiegende als
    Bezugspunkt. Bei Gleichstand werden alle beteiligten Angebote gemeldet — dann
    gibt es keine Mehrheit, an der man sich ausrichten koennte. Diese Heuristik
    ist der Grund fuer C2 und WARNUNG.
    """
    sammler = Befundsammler("R-052")
    rahmen = kontext.rahmen(Schicht.TYPED, "angebot")
    kennungen = row_ids(rahmen)
    belegung = {spalte: werte(rahmen, spalte) for spalte, _ in _SB_KONVENTIONEN}

    for anfrage_id, positionen in gruppen(werte(rahmen, "anfrage_id")).items():
        je_konvention: dict[str, list[int]] = {spalte: [] for spalte, _ in _SB_KONVENTIONEN}
        for position in positionen:
            for spalte, _ in _SB_KONVENTIONEN:
                if belegung[spalte][position] is not None:
                    je_konvention[spalte].append(position)
        benutzt = [spalte for spalte, treffer in je_konvention.items() if treffer]
        if len(benutzt) < 2:  # noqa: PLR2004
            continue

        groesste = max(len(je_konvention[spalte]) for spalte in benutzt)
        mehrheitlich = [spalte for spalte in benutzt if len(je_konvention[spalte]) == groesste]
        abweichend = (
            benutzt if len(mehrheitlich) > 1 else [s for s in benutzt if s not in mehrheitlich]
        )
        bezeichnung = dict(_SB_KONVENTIONEN)
        vorherrschend = ", ".join(bezeichnung[spalte] for spalte in mehrheitlich)
        for spalte in abweichend:
            for position in je_konvention[spalte]:
                sammler.melde(
                    "angebot",
                    kennungen[position],
                    (spalte,),
                    f"Der Selbstbehalt ist als {bezeichnung[spalte]} gefuehrt, in der "
                    f"Anfrage {anfrage_id} ueberwiegt aber {vorherrschend}",
                )
    return sammler.befund()


def pruefe_r053(kontext: Kontext) -> Befund:
    """``bruttobeitrag_jahr_eur`` liegt je Sparte im plausiblen Korridor.

    Werte weit ausserhalb deuten auf eine Cent-statt-Euro-Interpretation hin. Die
    Ursache in der Praxis sind implizite Dezimalstellen im GDV-Format: "10,2"
    bedeutet zehn Vor- und zwei Nachkommastellen ohne Trennzeichen.

    **Geprueft wird der Jahresbeitrag, nicht die Rate** — die Rate ist bei
    monatlicher Zahlweise ein Zwoelftel und laege systematisch unterhalb des
    Korridors.

    Die Korridore stehen in ``config.schwellen``. Ihre Breite bestimmt unmittelbar
    die Erkennungsschwelle: Ein Faktor-100-Fehler wird genau dann erkannt, wenn der
    verfaelschte Wert die Obergrenze ueberschreitet. Eine korridorbasierte Regel
    verliert Trennschaerfe genau in dem Mass, in dem der legitime Wertebereich
    breit ist (``docs/iteration_log.md``).
    """
    sammler = Befundsammler("R-053")
    rahmen = kontext.rahmen(Schicht.TYPED, "angebot")
    kennungen = row_ids(rahmen)
    sparte_je_anfrage = zuordnung(kontext.rahmen(Schicht.TYPED, "anfrage"), "anfrage_id", "sparte")
    anfrage_ids = werte(rahmen, "anfrage_id")
    korridore = {
        "Kfz": kontext.schwellen.r053_korridor_kfz_eur,
        "Hausrat": kontext.schwellen.r053_korridor_hausrat_eur,
    }
    for position, brutto in enumerate(werte(rahmen, "bruttobeitrag_jahr_eur")):
        if brutto is None:
            continue
        sparte = sparte_je_anfrage.get(anfrage_ids[position])
        if sparte is None:
            continue
        name = "Kfz" if str(sparte) in _KFZ else "Hausrat"
        unten, oben = korridore[name]
        wert = _betrag(brutto)
        if unten <= wert <= oben:
            continue
        sammler.melde(
            "angebot",
            kennungen[position],
            ("bruttobeitrag_jahr_eur",),
            f"bruttobeitrag_jahr_eur={brutto} liegt ausserhalb des Korridors "
            f"[{unten}, {oben}] der Sparte {sparte} ({name})",
        )
    return sammler.befund()


def pruefe_r054(kontext: Kontext) -> Befund:
    """Kein Angebot weicht um naeherungsweise den Faktor 12 vom Median der uebrigen ab.

    Monats- statt Jahresbeitrag. Verglichen wird gegen den Median der **uebrigen**
    Angebote derselben Anfrage, nicht gegen einen absoluten Wert — sonst waere der
    Fehler bei einem guenstigen Vertrag nicht von einem legitimen Beitrag zu
    unterscheiden.

    Geprueft werden beide Richtungen: ein um Faktor 12 zu kleiner Wert (Monats-
    statt Jahresbeitrag) und ein um Faktor 12 zu grosser (Jahres- statt
    Monatsbeitrag).

    **Mindestens zwei Vergleichsangebote.** Bei nur einem waere der Median dieses
    eine Angebot, und beide Seiten des Paares saehen fuereinander wie der Fehler
    aus; die Regel muesste beide melden und haette bestenfalls eine Precision von
    0,5. Diese Einschraenkung kostet Recall bei Anfragen mit zwei bepreisten
    Angeboten und ist als Modellentscheidung zu berichten.
    """
    sammler = Befundsammler("R-054")
    rahmen = kontext.rahmen(Schicht.TYPED, "angebot")
    kennungen = row_ids(rahmen)
    brutto_werte = werte(rahmen, "bruttobeitrag_jahr_eur")
    faktor = Decimal(str(kontext.schwellen.r054_faktor))
    toleranz = Decimal(str(kontext.schwellen.r054_toleranz_relativ))
    untere_schranke = faktor * (Decimal(1) - toleranz)
    obere_schranke = faktor * (Decimal(1) + toleranz)

    for anfrage_id, positionen in gruppen(werte(rahmen, "anfrage_id")).items():
        bepreist = [position for position in positionen if brutto_werte[position] is not None]
        if len(bepreist) < 3:  # noqa: PLR2004
            continue
        for position in bepreist:
            wert = _betrag(brutto_werte[position])
            uebrige = [_betrag(brutto_werte[andere]) for andere in bepreist if andere != position]
            mittelwert = _median(uebrige)
            if wert <= 0 or mittelwert <= 0:
                continue
            verhaeltnis = mittelwert / wert
            umgekehrt = wert / mittelwert
            if untere_schranke <= verhaeltnis <= obere_schranke:
                richtung = "zu klein (Monats- statt Jahresbeitrag)"
                gemessen = verhaeltnis
            elif untere_schranke <= umgekehrt <= obere_schranke:
                richtung = "zu gross (Jahres- statt Monatsbeitrag)"
                gemessen = umgekehrt
            else:
                continue
            sammler.melde(
                "angebot",
                kennungen[position],
                ("bruttobeitrag_jahr_eur",),
                f"bruttobeitrag_jahr_eur={brutto_werte[position]} ist um den Faktor "
                f"{gemessen:.2f} {richtung}; der Median der uebrigen {len(uebrige)} Angebote "
                f"der Anfrage {anfrage_id} betraegt {mittelwert}",
            )
    return sammler.befund()


# ---------------------------------------------------------------------------
# R-055 bis R-058 — Aktualitaet, Pflichtfelder, Referenzabgleich
# ---------------------------------------------------------------------------


def pruefe_r055(kontext: Kontext) -> Befund:
    """``berechnungszeitpunkt`` liegt im Gueltigkeitsfenster des Tarifs.

    **Veralteter Tarifstand** — die klassische Fehlerklasse von Vergleichsportalen.
    Ursache in der Praxis: GDV-Bestandsdaten werden meist nur monatlich erzeugt,
    Aenderungen kommen mit Wochen Verzug an. Der Vergleich rechnet dann mit einem
    Tarif, der zum Berechnungszeitpunkt nicht mehr galt.

    Verglichen wird der **Kalendertag** des Berechnungszeitpunkts, weil
    ``gueltig_ab`` und ``gueltig_bis`` Datumsfelder sind.

    Die Regel meldet zusaetzlich satzbezogen: Beteiligt sind die Angebotszeile und
    die Tarifzeile, auf die sie zeigt.
    """
    sammler = Befundsammler("R-055")
    tarife = kontext.rahmen(Schicht.TYPED, "tarif")
    fenster = {
        kennung: (ab, bis)
        for kennung, ab, bis in zip(
            werte(tarife, "tarif_id"),
            werte(tarife, "gueltig_ab"),
            werte(tarife, "gueltig_bis"),
            strict=True,
        )
        if kennung is not None
    }
    rahmen = kontext.rahmen(Schicht.TYPED, "angebot")
    kennungen = row_ids(rahmen)
    tarif_ids = werte(rahmen, "tarif_id")
    for position, zeitpunkt in enumerate(werte(rahmen, "berechnungszeitpunkt")):
        tarif_id = tarif_ids[position]
        if zeitpunkt is None or tarif_id is None:
            continue
        grenzen = fenster.get(tarif_id)
        if grenzen is None:
            # Ein nicht aufloesbarer Tarifverweis ist Sache von R-049.
            continue
        gueltig_ab, gueltig_bis = grenzen
        if gueltig_ab is None or gueltig_bis is None:
            continue
        tag = zeitpunkt.date()
        if gueltig_ab <= tag <= gueltig_bis:
            continue
        verstoss_id = sammler.melde(
            "angebot",
            kennungen[position],
            ("berechnungszeitpunkt", "tarif_id"),
            f"berechnungszeitpunkt={zeitpunkt} liegt ausserhalb des Gueltigkeitsfensters "
            f"[{gueltig_ab}, {gueltig_bis}] des Tarifs {tarif_id}",
        )
        sammler.melde_satz(
            "angebot",
            [kennungen[position]],
            f"Veralteter Tarifstand: Angebot zeigt auf den Tarif {tarif_id} mit dem "
            f"Gueltigkeitsfenster [{gueltig_ab}, {gueltig_bis}]",
            verstoss_id=verstoss_id,
        )
    return sammler.befund()


def pruefe_r056(kontext: Kontext) -> Befund:
    """``gueltig_bis`` liegt nach ``gueltig_ab``.

    Ein Gueltigkeitszeitraum, der endet, bevor er beginnt, ist kein Zeitraum.
    """
    sammler = Befundsammler("R-056")
    rahmen = kontext.rahmen(Schicht.TYPED, "tarif")
    kennungen = row_ids(rahmen)
    ab_werte = werte(rahmen, "gueltig_ab")
    for position, bis in enumerate(werte(rahmen, "gueltig_bis")):
        ab = ab_werte[position]
        if bis is None or ab is None or bis > ab:
            continue
        sammler.melde(
            "tarif",
            kennungen[position],
            ("gueltig_bis", "gueltig_ab"),
            f"gueltig_bis={bis} liegt nicht nach gueltig_ab={ab}",
        )
    return sammler.befund()


def _profilverstoesse_anfrageseite(kontext: Kontext, sammler: Befundsammler) -> None:
    """Prueft die Profilfelder von ``person``, ``risiko_*`` und ``zahlung``.

    Diese Felder werden **einmal je Anfrage** erfasst und an alle Versicherer
    verschickt. Ihr Befuellungsgrad haengt deshalb nicht am liefernden Anbieter,
    sondern am Eingangskanal (``spec/01``, Abschnitt 5.1). Ohne diese Zweiteilung
    waere das Profil auf der Anfrageseite nicht anwendbar: Eine Anfrage hat drei
    bis zwoelf Angebote mit verschiedenen Schnittstellen.
    """
    anfragen = kontext.rahmen(Schicht.TYPED, "anfrage")
    kanal_je_anfrage = zuordnung(anfragen, "anfrage_id", "kanal")
    sparte_je_anfrage = zuordnung(anfragen, "anfrage_id", "sparte")

    for entitaet in _ANFRAGESEITIGE_ENTITAETEN:
        felder = [
            feld for feld in PROFILFELDER if feld.partition(".")[0] == entitaet
        ]
        if not felder:
            continue
        rahmen = kontext.rahmen(Schicht.TYPED, entitaet)
        if rahmen.empty:
            continue
        kennungen = row_ids(rahmen)
        belegung = {feld: werte(rahmen, feld.partition(".")[2]) for feld in felder}
        ausschluss = _ausschlusswerte(kontext, entitaet, felder)
        bekannte_kanaele = {wert.value for wert in Kanal}
        for position, anfrage_id in enumerate(werte(rahmen, "anfrage_id")):
            kanal = kanal_je_anfrage.get(anfrage_id)
            if kanal is None or str(kanal) not in bekannte_kanaele:
                continue
            profil = profil_des_kanals(str(kanal))
            sparte = sparte_je_anfrage.get(anfrage_id)
            for feld in felder:
                spalte = feld.partition(".")[2]
                if not ist_pflicht(feld, profil):
                    continue
                spaltenwert = ausschluss.get(feld, [None] * len(kennungen))[position]
                if not _anwendbar(feld, None if sparte is None else str(sparte), spaltenwert):
                    continue
                if belegung[feld][position] is not None:
                    continue
                sammler.melde(
                    entitaet,
                    kennungen[position],
                    (spalte,),
                    f"{feld} ist beim Profil {profil.value} (Kanal {kanal}) Pflicht, "
                    "aber leer",
                )


def _profilverstoesse_angebot(kontext: Kontext, sammler: Befundsammler) -> None:
    """Prueft die Profilfelder von ``angebot`` gegen die Quellschnittstelle der Zeile."""
    felder = [feld for feld in PROFILFELDER if feld.partition(".")[0] == "angebot"]
    if not felder:
        return
    rahmen = kontext.rahmen(Schicht.TYPED, "angebot")
    if rahmen.empty:
        return
    kennungen = row_ids(rahmen)
    sparte_je_anfrage = zuordnung(kontext.rahmen(Schicht.TYPED, "anfrage"), "anfrage_id", "sparte")
    anfrage_ids = werte(rahmen, "anfrage_id")
    belegung = {feld: werte(rahmen, feld.partition(".")[2]) for feld in felder}
    ausschluss = _ausschlusswerte(kontext, "angebot", felder)
    bekannte = {wert.value for wert in Quellschnittstelle}
    for position, schnittstelle in enumerate(werte(rahmen, "quell_schnittstelle")):
        if schnittstelle is None or str(schnittstelle) not in bekannte:
            continue
        profil = Quellschnittstelle(str(schnittstelle))
        sparte = sparte_je_anfrage.get(anfrage_ids[position])
        for feld in felder:
            if not ist_pflicht(feld, profil):
                continue
            spaltenwert = ausschluss.get(feld, [None] * len(kennungen))[position]
            if not _anwendbar(feld, None if sparte is None else str(sparte), spaltenwert):
                continue
            if belegung[feld][position] is not None:
                continue
            sammler.melde(
                "angebot",
                kennungen[position],
                (feld.partition(".")[2],),
                f"{feld} ist bei der Quellschnittstelle {profil.value} Pflicht, aber leer",
            )


def pruefe_r057(kontext: Kontext) -> Befund:
    """Das Pflichtfeldprofil ist eingehalten — zweigeteilt nach Kanal und Schnittstelle.

    Versicherer befuellen dasselbe Feld unterschiedlich tief: BiPRO-Schnittstellen
    liefern strukturiert und vollstaendig, klassische GDV-Lieferungen und manuelle
    CSV-Importe deutlich lueckenhafter. Genau das ist ein Multi-Source-Problem im
    Sinne von Rahm und Do.

    **Die Zweiteilung ist noetig**, weil ``quell_schnittstelle`` ein Feld von
    ``angebot`` ist, die Anfrageseite aber einmal je Anfrage erfasst wird. Die
    Begruendung steht in :func:`_profilverstoesse_anfrageseite`.

    **Die Anwendbarkeitsbedingung ist ebenso noetig:** Ein Feld, das die
    Zweckbindung ohnehin leer laesst, wird nicht geprueft
    (:data:`_ANWENDBARE_SPARTEN`).

    Dass der Generator ein als *optional* markiertes Feld leer laesst, ist Teil des
    **sauberen** Datensatzes und kein Fehler (``spec/01``, Abschnitt 5). Die
    Kernpflichtfelder prueft R-001; hier geht es ausschliesslich um das
    schnittstellenabhaengige Profil.
    """
    sammler = Befundsammler("R-057")
    _profilverstoesse_anfrageseite(kontext, sammler)
    _profilverstoesse_angebot(kontext, sammler)
    return sammler.befund()


def pruefe_r058(kontext: Kontext) -> Befund:
    """Die Regionalklassen stimmen mit dem Eintrag zum ``zulassungsbezirk`` ueberein.

    Referenzabgleich, analog zu R-051 fuer HSN und TSN.

    **Der Schluessel ist der Zulassungsbezirk, nicht die Postleitzahl.**
    PLZ-Gebiete koennen Bezirksgrenzen schneiden; ein Abgleich ueber die PLZ waere
    fachlich falsch. Ein Bezug zum Tarifstand entfaellt — ``risiko_kfz`` hat keinen
    Bezug zu ``tarif``.
    """
    sammler = Befundsammler("R-058")
    referenz = kontext.referenztabelle("regionalklassen")
    eintraege = {
        str(bezirk): zeile
        for bezirk, zeile in zip(
            referenz["zulassungsbezirk"],
            referenz.to_dict(orient="records"),
            strict=True,
        )
    }
    rahmen = kontext.rahmen(Schicht.TYPED, "risiko_kfz")
    kennungen = row_ids(rahmen)
    belegung = {spalte: werte(rahmen, spalte) for spalte in _REGIONALKLASSENFELDER}
    for position, bezirk in enumerate(werte(rahmen, "zulassungsbezirk")):
        if bezirk is None:
            continue
        eintrag = eintraege.get(str(bezirk))
        if eintrag is None:
            sammler.melde(
                "risiko_kfz",
                kennungen[position],
                ("zulassungsbezirk",),
                f"zulassungsbezirk={bezirk!r} existiert nicht in regionalklassen.csv",
            )
            continue
        for spalte in _REGIONALKLASSENFELDER:
            wert = belegung[spalte][position]
            if wert is None or str(wert) == str(eintrag[spalte]):
                continue
            sammler.melde(
                "risiko_kfz",
                kennungen[position],
                (spalte, "zulassungsbezirk"),
                f"{spalte}={wert} weicht vom Regionalklassenverzeichnis ab; zum "
                f"zulassungsbezirk={bezirk!r} gehoert {eintrag[spalte]}",
            )
    return sammler.befund()


# ---------------------------------------------------------------------------
# Registrierung
# ---------------------------------------------------------------------------

REGELN: Final[tuple[Regel, ...]] = (
    Regel(
        regel_id="R-052",
        beschreibung=(
            "Innerhalb einer anfrage_id verwenden alle Angebote dieselbe Einheiten"
            "konvention fuer den Selbstbehalt"
        ),
        entitaet="angebot",
        spalten=("sb_hausrat_prozent", "sb_hausrat_eur"),
        granularitaet="G5",
        fehlerklasse_b="B7",
        erkennbarkeit_c="C2",
        schweregrad="WARNUNG",
        literatur=("RD", "KIM", "FOI", "DAMA"),
        fachliche_grundlage=(
            "Anbieter A liefert den Selbstbehalt in Euro, Anbieter B in Prozent — der "
            "Vergleich wird dadurch unzulaessig"
        ),
        schicht=Schicht.TYPED,
        pruefe=pruefe_r052,
    ),
    Regel(
        regel_id="R-053",
        beschreibung=(
            "bruttobeitrag_jahr_eur liegt je Sparte im plausiblen Korridor "
            "(config.schwellen)"
        ),
        entitaet="angebot, anfrage",
        spalten=("bruttobeitrag_jahr_eur",),
        granularitaet="G5",
        fehlerklasse_b="B3",
        erkennbarkeit_c="C2",
        schweregrad="WARNUNG",
        literatur=("ABE", "FOI"),
        fachliche_grundlage=(
            "Cent-statt-Euro-Interpretation durch implizite Dezimalstellen im GDV-Format. "
            "Geprueft wird der Jahresbeitrag, nicht die Rate"
        ),
        schicht=Schicht.TYPED,
        pruefe=pruefe_r053,
    ),
    Regel(
        regel_id="R-054",
        beschreibung=(
            "Kein Angebot weicht um naeherungsweise den Faktor 12 vom Median der uebrigen "
            "Angebote derselben Anfrage ab"
        ),
        entitaet="angebot",
        spalten=("bruttobeitrag_jahr_eur",),
        granularitaet="G5",
        fehlerklasse_b="B7",
        erkennbarkeit_c="C2",
        schweregrad="WARNUNG",
        literatur=("RD", "FOI"),
        fachliche_grundlage=(
            "Monats- statt Jahresbeitrag. Ein Faktor 12 ist nicht ueber eine absolute "
            "Untergrenze zu finden, sondern nur relational"
        ),
        schicht=Schicht.TYPED,
        pruefe=pruefe_r054,
    ),
    Regel(
        regel_id="R-055",
        beschreibung="berechnungszeitpunkt liegt in [tarif.gueltig_ab, tarif.gueltig_bis]",
        entitaet="angebot, tarif",
        spalten=("berechnungszeitpunkt", "tarif_id"),
        granularitaet="G5",
        fehlerklasse_b="B6",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD", "DAMA", "ISO"),
        fachliche_grundlage=(
            "Veralteter Tarifstand — die klassische Fehlerklasse von Vergleichsportalen. "
            "GDV-Bestandsdaten werden meist nur monatlich erzeugt"
        ),
        schicht=Schicht.TYPED,
        pruefe=pruefe_r055,
    ),
    Regel(
        regel_id="R-056",
        beschreibung="tarif.gueltig_bis liegt nach tarif.gueltig_ab",
        entitaet="tarif",
        spalten=("gueltig_bis", "gueltig_ab"),
        granularitaet="G5",
        fehlerklasse_b="B6",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD",),
        fachliche_grundlage="Ein Zeitraum, der endet, bevor er beginnt, ist kein Zeitraum",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r056,
    ),
    Regel(
        regel_id="R-057",
        beschreibung=(
            "Das Pflichtfeldprofil ist eingehalten, zweigeteilt: Anfrageseite je kanal, "
            "Angebot je quell_schnittstelle; Anwendbarkeitsbedingung beachtet"
        ),
        entitaet="person, risiko_kfz, risiko_hausrat, zahlung, angebot",
        spalten=tuple(feld.partition(".")[2] for feld in PROFILFELDER),
        granularitaet="G5",
        fehlerklasse_b="B1",
        erkennbarkeit_c="C2",
        schweregrad="WARNUNG",
        literatur=("RD", "DAMA"),
        fachliche_grundlage=(
            "Versicherer befuellen dasselbe Feld unterschiedlich tief; das Pflichtfeldprofil "
            "steht in spec/01, Abschnitt 5"
        ),
        schicht=Schicht.TYPED,
        pruefe=pruefe_r057,
    ),
    Regel(
        regel_id="R-058",
        beschreibung=(
            "regionalklasse_hp, _tk und _vk stimmen mit dem Eintrag zu zulassungsbezirk in "
            "regionalklassen.csv ueberein"
        ),
        entitaet="risiko_kfz",
        spalten=("zulassungsbezirk", *_REGIONALKLASSENFELDER),
        granularitaet="G5",
        fehlerklasse_b="B4",
        erkennbarkeit_c="C3",
        schweregrad="HART",
        literatur=("FAN", "CHU"),
        fachliche_grundlage=(
            "Referenzabgleich analog zu R-051. Regionalklassen haengen am Zulassungsbezirk, "
            "nicht an der PLZ — PLZ-Gebiete koennen Bezirksgrenzen schneiden"
        ),
        schicht=Schicht.TYPED,
        pruefe=pruefe_r058,
    ),
)
