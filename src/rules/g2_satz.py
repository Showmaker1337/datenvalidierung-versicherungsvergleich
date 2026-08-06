"""G2 — Regeln auf Satzebene (R-026 bis R-042).

Eine G2-Regel prueft eine Beziehung **zwischen Feldern eines Satzes**: Die
Erstzulassung liegt vor der Zulassung auf den Versicherungsnehmer, der
Bruttobeitrag ist die Summe aus Netto und Steuer, ein E-Kennzeichen setzt einen
elektrischen Antrieb voraus. In der Sprache der Literatur sind das Functional
Dependencies (Fan et al.) und Denial Constraints (Chu et al.).

Alle Regeln dieser Gruppe laufen auf der **typisierten Schicht**: Sie rechnen mit
Daten, Betraegen und Zahlen, nicht mit deren Schreibweise.

Zwei Regeln reichen ueber den einzelnen Satz hinaus und brauchen deshalb den vollen
Kontext: R-029 verbindet ``risiko_kfz`` mit dem Alter des Versicherungsnehmers aus
``person``, und die Beitragsregeln R-033, R-035, R-036 und R-041 brauchen Sparte
beziehungsweise Zahlweise aus ``anfrage``. Sie bleiben trotzdem G2 — geprueft wird
eine Bedingung **innerhalb** eines Vergleichsvorgangs, nicht eine Beziehung
zwischen Zeilen derselben Tabelle.

Geld wird ausschliesslich in :class:`~decimal.Decimal` verglichen, niemals in
``float`` (CLAUDE.md, Abschnitt 5). Die Toleranzen kommen aus
``config.schwellen``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any, Final

from src.common import wertebereiche as wb
from src.common.datum import datum_plus_jahre, jahre_zwischen
from src.common.enums import (
    RATENANZAHL_JE_ZAHLWEISE,
    Annahmeentscheidung,
    Antriebsart,
    ArtKennzeichen,
    Rolle,
    Sparte,
    Zahlweise,
    schadenfreie_jahre,
    sf_ordnung,
)
from src.common.geld import runde
from src.common.pfade import Schicht
from src.rules.modell import Befund, Befundsammler, Regel, row_ids, werte, zuordnung

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from src.rules.modell import Kontext

__all__ = ["REGELN"]

#: Beitragsfelder eines Angebots (R-037).
#:
#: Selbstbehalt und Berechnungszeitpunkt gehoeren **nicht** dazu: Sie beschreiben
#: die angefragte Deckung, nicht ihren Preis, und bleiben auch bei einer Ablehnung
#: gefuellt (README, Abschnitt "Getroffene Festlegungen").
_BEITRAGSFELDER: Final[tuple[str, ...]] = (
    "nettobeitrag_jahr_eur",
    "versicherungsteuer_satz",
    "versicherungsteuer_eur",
    "bruttobeitrag_jahr_eur",
    "ratenzahlungszuschlag_prozent",
    "zahlbeitrag_rate_eur",
)

#: Zahlweisen ohne Ratenzahlung (R-035): jaehrlich und Einmalbetrag.
_ZAHLWEISEN_OHNE_RATEN: Final[frozenset[int]] = frozenset(
    {int(Zahlweise.JAEHRLICH), int(Zahlweise.EINMALBETRAG)}
)

#: Antriebsarten, die ein E-Kennzeichen rechtfertigen (R-039, EmoG).
_ELEKTRISCHE_ANTRIEBE: Final[frozenset[str]] = frozenset(
    {Antriebsart.ELEKTRO.value, Antriebsart.HYBRID.value}
)

#: Sparten mit einem Effektivsatz der Versicherungsteuer (R-033, R-034).
#:
#: Jede Sparte ausserhalb dieses Katalogs ist nach Paragraf 4 VersStG steuerfrei.
_STEUERPFLICHTIGE_SPARTEN: Final[frozenset[str]] = frozenset(
    sparte.value for sparte in wb.VERSICHERUNGSTEUER_EFFEKTIVSATZ
)


def _betrag(wert: Any) -> Decimal:  # noqa: ANN401
    """Wandelt einen Wert der typisierten Schicht in ein ``Decimal``.

    Der Umweg ueber ``str`` ist Absicht: Er haelt die exakte Dezimaldarstellung
    auch dann, wenn eine Verarbeitungsstufe einen ``float`` eingeschleust hat.
    """
    return Decimal(str(wert))


def _vn_geburtsdatum_je_anfrage(kontext: Kontext) -> dict[Any, Any]:
    """Bildet die Anfrage auf das Geburtsdatum ihres Versicherungsnehmers ab.

    Grundlage von R-029. Zweite versicherte Personen bleiben aussen vor — die
    Schadenfreiheitsklasse haengt am Versicherungsnehmer.
    """
    person = kontext.rahmen(Schicht.TYPED, "person")
    ergebnis: dict[Any, Any] = {}
    for anfrage_id, rolle, geburtsdatum in zip(
        werte(person, "anfrage_id"),
        werte(person, "rolle"),
        werte(person, "geburtsdatum"),
        strict=True,
    ):
        if anfrage_id is None or rolle is None or str(rolle) != Rolle.VN.value:
            continue
        ergebnis.setdefault(anfrage_id, geburtsdatum)
    return ergebnis


# ---------------------------------------------------------------------------
# R-026 bis R-030 — zeitliche und ordinale Abhaengigkeiten
# ---------------------------------------------------------------------------


def pruefe_r026(kontext: Kontext) -> Befund:
    """``erstzulassung`` liegt nicht nach dem Stichtag.

    Der Stichtag kommt aus der Konfiguration, nicht aus der Systemzeit
    (Architekturregel A2).
    """
    sammler = Befundsammler("R-026")
    rahmen = kontext.rahmen(Schicht.TYPED, "risiko_kfz")
    kennungen = row_ids(rahmen)
    for position, wert in enumerate(werte(rahmen, "erstzulassung")):
        if wert is None or wert <= kontext.stichtag:
            continue
        sammler.melde(
            "risiko_kfz",
            kennungen[position],
            ("erstzulassung",),
            f"erstzulassung={wert} liegt nach dem Stichtag {kontext.stichtag}",
        )
    return sammler.befund()


def pruefe_r027(kontext: Kontext) -> Befund:
    """``erstzulassung`` <= ``zulassung_auf_vn`` <= Stichtag.

    Ein Fahrzeug wird nicht vor seiner Erstzulassung auf den Versicherungsnehmer
    zugelassen. Der erste Teil betrifft **beide** Felder und meldet sie
    gemeinsam — welches der beiden falsch ist, kann die Regel nicht wissen.
    """
    sammler = Befundsammler("R-027")
    rahmen = kontext.rahmen(Schicht.TYPED, "risiko_kfz")
    kennungen = row_ids(rahmen)
    erstzulassungen = werte(rahmen, "erstzulassung")
    zulassungen = werte(rahmen, "zulassung_auf_vn")
    for position, zulassung in enumerate(zulassungen):
        if zulassung is None:
            continue
        erstzulassung = erstzulassungen[position]
        if erstzulassung is not None and zulassung < erstzulassung:
            sammler.melde(
                "risiko_kfz",
                kennungen[position],
                ("erstzulassung", "zulassung_auf_vn"),
                f"zulassung_auf_vn={zulassung} liegt vor der erstzulassung={erstzulassung}",
            )
        if zulassung > kontext.stichtag:
            sammler.melde(
                "risiko_kfz",
                kennungen[position],
                ("zulassung_auf_vn",),
                f"zulassung_auf_vn={zulassung} liegt nach dem Stichtag {kontext.stichtag}",
            )
    return sammler.befund()


def pruefe_r028(kontext: Kontext) -> Befund:
    """``fuehrerschein_datum`` liegt zwischen dem 17. Geburtstag und dem Stichtag.

    Begleitetes Fahren ab 17 ist die Untergrenze (Paragraf 48a FeV). Die
    Jahresaddition laeuft ueber :func:`~src.common.datum.datum_plus_jahre` — am
    29. Februar erreicht die Untergrenze in Nichtschaltjahren den 1. Maerz, nicht
    den 28. Februar.
    """
    sammler = Befundsammler("R-028")
    rahmen = kontext.rahmen(Schicht.TYPED, "person")
    kennungen = row_ids(rahmen)
    geburtstage = werte(rahmen, "geburtsdatum")
    for position, schein in enumerate(werte(rahmen, "fuehrerschein_datum")):
        if schein is None:
            continue
        geburtsdatum = geburtstage[position]
        if geburtsdatum is not None:
            untergrenze = datum_plus_jahre(geburtsdatum, wb.FUEHRERSCHEIN_MINDESTALTER_JAHRE)
            if schein < untergrenze:
                sammler.melde(
                    "person",
                    kennungen[position],
                    ("fuehrerschein_datum", "geburtsdatum"),
                    f"fuehrerschein_datum={schein} liegt vor dem fruehestmoeglichen "
                    f"Erwerbstag {untergrenze} "
                    f"(geburtsdatum={geburtsdatum} plus "
                    f"{wb.FUEHRERSCHEIN_MINDESTALTER_JAHRE} Jahre)",
                )
        if schein > kontext.stichtag:
            sammler.melde(
                "person",
                kennungen[position],
                ("fuehrerschein_datum",),
                f"fuehrerschein_datum={schein} liegt nach dem Stichtag {kontext.stichtag}",
            )
    return sammler.befund()


def pruefe_r029(kontext: Kontext) -> Befund:
    """Die Schadenfreiheitsklasse weist nicht mehr Jahre aus, als moeglich sind.

    ``schadenfreie_jahre(sf_klasse_hp) <= Alter(VN) - 17``. Man kann nicht laenger
    schadenfrei fahren, als man den Fuehrerschein besitzen kann.

    Die Abbildung steht in ``spec/01``, Abschnitt 2.8. Alle vier Sonderklassen
    ergeben null schadenfreie Jahre und erfuellen die Regel trivial — das ist
    fachlich richtig und kein Ausweichen: Wer in der Malusklasse steht, hat gerade
    keine schadenfreie Historie vorzuweisen.
    """
    sammler = Befundsammler("R-029")
    rahmen = kontext.rahmen(Schicht.TYPED, "risiko_kfz")
    kennungen = row_ids(rahmen)
    geburtsdatum_je_anfrage = _vn_geburtsdatum_je_anfrage(kontext)
    anfrage_ids = werte(rahmen, "anfrage_id")
    for position, klasse in enumerate(werte(rahmen, "sf_klasse_hp")):
        if klasse is None:
            continue
        jahre = schadenfreie_jahre(str(klasse))
        if jahre is None:
            # Kein Katalogwert. Das meldet R-013; hier waere es eine Doppelung.
            continue
        geburtsdatum = geburtsdatum_je_anfrage.get(anfrage_ids[position])
        if geburtsdatum is None:
            continue
        obergrenze = (
            jahre_zwischen(geburtsdatum, kontext.stichtag) - wb.FUEHRERSCHEIN_MINDESTALTER_JAHRE
        )
        if jahre > obergrenze:
            sammler.melde(
                "risiko_kfz",
                kennungen[position],
                ("sf_klasse_hp",),
                f"sf_klasse_hp={klasse!r} weist {jahre} schadenfreie Jahre aus, moeglich sind "
                f"hoechstens {obergrenze} (geburtsdatum={geburtsdatum})",
            )
    return sammler.befund()


def pruefe_r030(kontext: Kontext) -> Befund:
    """Die Vollkaskoklasse ist nicht besser eingestuft als die Haftpflichtklasse.

    ``sf_ordnung(sf_klasse_vk) <= sf_ordnung(sf_klasse_hp)`` auf der vollstaendigen
    Ordnung einschliesslich der Sonderklassen (``spec/01``, Abschnitt 2.8). Nur so
    greift die Regel auch dann, wenn eine der beiden Klassen eine Sonderklasse ist,
    statt den Vergleich stillschweigend zu ueberspringen.

    Marktueblich, aber nicht zwingend — deshalb eine **Warnung**.
    """
    sammler = Befundsammler("R-030")
    rahmen = kontext.rahmen(Schicht.TYPED, "risiko_kfz")
    kennungen = row_ids(rahmen)
    haftpflicht = werte(rahmen, "sf_klasse_hp")
    for position, vollkasko in enumerate(werte(rahmen, "sf_klasse_vk")):
        if vollkasko is None or haftpflicht[position] is None:
            continue
        ordnung_vk = sf_ordnung(str(vollkasko))
        ordnung_hp = sf_ordnung(str(haftpflicht[position]))
        if ordnung_vk is None or ordnung_hp is None or ordnung_vk <= ordnung_hp:
            continue
        sammler.melde(
            "risiko_kfz",
            kennungen[position],
            ("sf_klasse_vk", "sf_klasse_hp"),
            f"sf_klasse_vk={vollkasko!r} ist besser eingestuft als "
            f"sf_klasse_hp={haftpflicht[position]!r}",
        )
    return sammler.befund()


# ---------------------------------------------------------------------------
# R-031 bis R-037 — Beitragsarithmetik
# ---------------------------------------------------------------------------


def pruefe_r031(kontext: Kontext) -> Befund:
    """``brutto`` = ``netto`` + ``steuer``, Toleranz aus der Konfiguration.

    **Ein Verstoss ueber drei Spalten.** Welche der drei Zellen falsch ist, kann
    die Regel nicht wissen; sie meldet deshalb alle drei unter **einer**
    ``verstoss_id``. Der Evaluator wertet spaeter beide Sichten aus — streng
    zellbasiert und constraint-basiert (siehe ``src/rules/modell.py``).
    """
    sammler = Befundsammler("R-031")
    rahmen = kontext.rahmen(Schicht.TYPED, "angebot")
    kennungen = row_ids(rahmen)
    toleranz = kontext.schwellen.r031_toleranz_eur
    netto_werte = werte(rahmen, "nettobeitrag_jahr_eur")
    steuer_werte = werte(rahmen, "versicherungsteuer_eur")
    brutto_werte = werte(rahmen, "bruttobeitrag_jahr_eur")
    for position, brutto in enumerate(brutto_werte):
        netto, steuer = netto_werte[position], steuer_werte[position]
        if brutto is None or netto is None or steuer is None:
            continue
        abweichung = _betrag(brutto) - (_betrag(netto) + _betrag(steuer))
        if abs(abweichung) <= toleranz:
            continue
        sammler.melde(
            "angebot",
            kennungen[position],
            ("bruttobeitrag_jahr_eur", "nettobeitrag_jahr_eur", "versicherungsteuer_eur"),
            f"bruttobeitrag_jahr_eur={brutto} weicht um {abweichung} von "
            f"netto={netto} plus steuer={steuer} ab (Toleranz {toleranz})",
        )
    return sammler.befund()


def pruefe_r032(kontext: Kontext) -> Befund:
    """``steuer`` = ROUND_HALF_UP(``netto`` mal ``satz`` / 100, 2).

    Paragraf 6 in Verbindung mit Paragraf 5 VersStG. Gerechnet wird in
    ``Decimal`` mit kaufmaennischer Rundung; die Toleranz ist dieselbe wie bei
    R-031 (``config.schwellen.r031_toleranz_eur``), weil beide Regeln denselben
    Rundungsschritt betreffen.
    """
    sammler = Befundsammler("R-032")
    rahmen = kontext.rahmen(Schicht.TYPED, "angebot")
    kennungen = row_ids(rahmen)
    toleranz = kontext.schwellen.r031_toleranz_eur
    netto_werte = werte(rahmen, "nettobeitrag_jahr_eur")
    satz_werte = werte(rahmen, "versicherungsteuer_satz")
    steuer_werte = werte(rahmen, "versicherungsteuer_eur")
    for position, steuer in enumerate(steuer_werte):
        netto, satz = netto_werte[position], satz_werte[position]
        if steuer is None or netto is None or satz is None:
            continue
        erwartet = runde(_betrag(netto) * _betrag(satz) / Decimal(100))
        abweichung = _betrag(steuer) - erwartet
        if abs(abweichung) <= toleranz:
            continue
        sammler.melde(
            "angebot",
            kennungen[position],
            ("versicherungsteuer_eur", "nettobeitrag_jahr_eur", "versicherungsteuer_satz"),
            f"versicherungsteuer_eur={steuer} weicht um {abweichung} von den aus "
            f"netto={netto} und satz={satz} berechneten {erwartet} ab",
        )
    return sammler.befund()


def pruefe_r033(kontext: Kontext) -> Befund:
    """``versicherungsteuer_satz`` entspricht dem Effektivsatz der Sparte.

    **Das Musterbeispiel einer Conditional Functional Dependency** (Fan et al.):
    Der zulaessige Wert eines Feldes haengt vom Wert eines anderen Feldes ab —
    hier von der Sparte des Vergleichsvorgangs. 19,00 Prozent in den Kfz-Sparten,
    16,15 Prozent im Hausrat.

    Der Unterschied ist kein Rundungsartefakt: 16,15 Prozent ist der
    **Effektivsatz** aus 19 Prozent Nominalsatz auf 85 Prozent Bemessungsgrundlage
    (Paragraf 6 Absatz 2 in Verbindung mit Paragraf 5 Absatz 1 Nummer 3 VersStG).

    Die Sparte kommt aus ``anfrage``, nicht aus ``tarif``: Sie beschreibt den
    angefragten Versicherungsschutz und ist damit die massgebliche Groesse.
    """
    sammler = Befundsammler("R-033")
    rahmen = kontext.rahmen(Schicht.TYPED, "angebot")
    kennungen = row_ids(rahmen)
    sparte_je_anfrage = zuordnung(kontext.rahmen(Schicht.TYPED, "anfrage"), "anfrage_id", "sparte")
    anfrage_ids = werte(rahmen, "anfrage_id")
    for position, satz in enumerate(werte(rahmen, "versicherungsteuer_satz")):
        if satz is None:
            continue
        sparte = sparte_je_anfrage.get(anfrage_ids[position])
        if sparte is None or str(sparte) not in _STEUERPFLICHTIGE_SPARTEN:
            # Unbekannte Sparte meldet R-011, eine fehlende Anfrage meldet R-049.
            continue
        erwartet = wb.VERSICHERUNGSTEUER_EFFEKTIVSATZ[Sparte(str(sparte))]
        if _betrag(satz) == erwartet:
            continue
        sammler.melde(
            "angebot",
            kennungen[position],
            ("versicherungsteuer_satz",),
            f"versicherungsteuer_satz={satz} entspricht nicht dem Effektivsatz {erwartet} "
            f"der Sparte {sparte}",
        )
    return sammler.befund()


def pruefe_r034(kontext: Kontext) -> Befund:
    """Bei steuerfreien Sparten ist ``versicherungsteuer_eur`` gleich null.

    Paragraf 4 VersStG stellt Lebens-, Kranken-, Berufsunfaehigkeits-, Renten- und
    Pflegeversicherungen von der Versicherungsteuer frei.

    **Im aktuellen Datenmodell nicht ausloesbar.** Der Datensatz enthaelt nur die
    Sparten 051, 052, 053 und 130; alle vier sind steuerpflichtig. Die Regel wird
    trotzdem implementiert — das ist ehrlicher, als sie wegzulassen, und die
    Kennzahl "Regeln ohne Treffer" ist ein berichtetes Ergebnis der Arbeit
    (``spec/02``, Abschnitt "Regeln ohne zugehoerige Injektionsvariante").

    Umgesetzt ist sie als Umkehrschluss aus dem Steuersatzkatalog: Jede Sparte
    ohne Effektivsatz gilt als steuerfrei. Damit werden keine GDV-Schluessel
    erfunden, die im Modell nicht belegt sind.
    """
    sammler = Befundsammler("R-034")
    rahmen = kontext.rahmen(Schicht.TYPED, "angebot")
    kennungen = row_ids(rahmen)
    sparte_je_anfrage = zuordnung(kontext.rahmen(Schicht.TYPED, "anfrage"), "anfrage_id", "sparte")
    anfrage_ids = werte(rahmen, "anfrage_id")
    for position, steuer in enumerate(werte(rahmen, "versicherungsteuer_eur")):
        if steuer is None:
            continue
        sparte = sparte_je_anfrage.get(anfrage_ids[position])
        if sparte is None or str(sparte) in _STEUERPFLICHTIGE_SPARTEN:
            continue
        if _betrag(steuer) == 0:
            continue
        sammler.melde(
            "angebot",
            kennungen[position],
            ("versicherungsteuer_eur",),
            f"versicherungsteuer_eur={steuer} ist gesetzt, obwohl die Sparte {sparte} nach "
            "Paragraf 4 VersStG steuerfrei ist",
        )
    return sammler.befund()


def pruefe_r035(kontext: Kontext) -> Befund:
    """Ohne Ratenzahlung gibt es keinen Ratenzuschlag.

    ``zahlweise`` in {1, 6} erzwingt ``ratenzahlungszuschlag_prozent`` = 0. Eine
    weitere Conditional Functional Dependency, diesmal ueber die Entitaetsgrenze
    zwischen ``anfrage`` und ``angebot`` hinweg.
    """
    sammler = Befundsammler("R-035")
    rahmen = kontext.rahmen(Schicht.TYPED, "angebot")
    kennungen = row_ids(rahmen)
    zahlweise_je_anfrage = zuordnung(
        kontext.rahmen(Schicht.TYPED, "anfrage"), "anfrage_id", "zahlweise"
    )
    anfrage_ids = werte(rahmen, "anfrage_id")
    for position, zuschlag in enumerate(werte(rahmen, "ratenzahlungszuschlag_prozent")):
        if zuschlag is None:
            continue
        zahlweise = zahlweise_je_anfrage.get(anfrage_ids[position])
        if zahlweise is None or int(zahlweise) not in _ZAHLWEISEN_OHNE_RATEN:
            continue
        if _betrag(zuschlag) == 0:
            continue
        sammler.melde(
            "angebot",
            kennungen[position],
            ("ratenzahlungszuschlag_prozent",),
            f"ratenzahlungszuschlag_prozent={zuschlag} ist gesetzt, obwohl zahlweise="
            f"{int(zahlweise)} keine Ratenzahlung vorsieht",
        )
    return sammler.befund()


def pruefe_r036(kontext: Kontext) -> Befund:
    """Unterjaehrige Zahlung ist nie guenstiger als jaehrliche.

    ``zahlbeitrag_rate_eur`` mal Ratenanzahl >= ``bruttobeitrag_jahr_eur`` minus
    Toleranz mal Ratenanzahl.

    **Die Toleranz skaliert mit der Ratenanzahl.** Jede Rate wird auf zwei
    Nachkommastellen gerundet; bei zwoelf Raten summiert sich der Rundungsfehler
    auf bis zu 0,06 Euro. Eine feste Toleranz von 0,02 Euro wuerde auf sauberen
    Daten ausloesen — ein Fehlalarm, der nur aus der Berichtskonvention entstuende.
    """
    sammler = Befundsammler("R-036")
    rahmen = kontext.rahmen(Schicht.TYPED, "angebot")
    kennungen = row_ids(rahmen)
    toleranz_je_rate = kontext.schwellen.r036_toleranz_je_rate_eur
    zahlweise_je_anfrage = zuordnung(
        kontext.rahmen(Schicht.TYPED, "anfrage"), "anfrage_id", "zahlweise"
    )
    anfrage_ids = werte(rahmen, "anfrage_id")
    brutto_werte = werte(rahmen, "bruttobeitrag_jahr_eur")
    for position, rate in enumerate(werte(rahmen, "zahlbeitrag_rate_eur")):
        brutto = brutto_werte[position]
        if rate is None or brutto is None:
            continue
        zahlweise = zahlweise_je_anfrage.get(anfrage_ids[position])
        if zahlweise is None or int(zahlweise) not in set(map(int, Zahlweise)):
            # Unbekannte Zahlweise meldet R-010.
            continue
        ratenanzahl = RATENANZAHL_JE_ZAHLWEISE[Zahlweise(int(zahlweise))]
        summe = _betrag(rate) * ratenanzahl
        untergrenze = _betrag(brutto) - toleranz_je_rate * ratenanzahl
        if summe >= untergrenze:
            continue
        sammler.melde(
            "angebot",
            kennungen[position],
            ("zahlbeitrag_rate_eur", "bruttobeitrag_jahr_eur"),
            f"zahlbeitrag_rate_eur={rate} mal {ratenanzahl} Raten ergibt {summe} und "
            f"unterschreitet den Bruttojahresbeitrag {brutto} um mehr als die Toleranz "
            f"{toleranz_je_rate * ratenanzahl}",
        )
    return sammler.befund()


def pruefe_r037(kontext: Kontext) -> Befund:
    """``annahmeentscheidung`` = ABLEHNUNG genau dann, wenn alle Beitragsfelder leer sind.

    Eine Aequivalenz, keine Implikation: Ein abgelehntes Risiko hat keinen Preis,
    und ein Angebot ohne Preis ist keine Annahme. Beide Richtungen werden
    getrennt gemeldet.
    """
    sammler = Befundsammler("R-037")
    rahmen = kontext.rahmen(Schicht.TYPED, "angebot")
    kennungen = row_ids(rahmen)
    entscheidungen = werte(rahmen, "annahmeentscheidung")
    felder = {spalte: werte(rahmen, spalte) for spalte in _BEITRAGSFELDER}
    for position, entscheidung in enumerate(entscheidungen):
        if entscheidung is None:
            continue
        gefuellt = tuple(
            spalte for spalte in _BEITRAGSFELDER if felder[spalte][position] is not None
        )
        abgelehnt = str(entscheidung) == Annahmeentscheidung.ABLEHNUNG.value
        if abgelehnt and gefuellt:
            sammler.melde(
                "angebot",
                kennungen[position],
                ("annahmeentscheidung", *gefuellt),
                f"annahmeentscheidung={entscheidung!r}, aber die Beitragsfelder "
                f"{list(gefuellt)} sind gefuellt",
            )
        elif not abgelehnt and not gefuellt:
            sammler.melde(
                "angebot",
                kennungen[position],
                ("annahmeentscheidung", *_BEITRAGSFELDER),
                f"annahmeentscheidung={entscheidung!r}, aber alle Beitragsfelder sind leer",
            )
    return sammler.befund()


# ---------------------------------------------------------------------------
# R-038 bis R-042 — uebrige Satzbedingungen
# ---------------------------------------------------------------------------


def pruefe_r038(kontext: Kontext) -> Befund:
    """``fahrzeugwert_aktuell`` uebersteigt nicht den ``neupreis_eur``.

    Ein Denial Constraint im Sinne von Chu et al.: Ein Fahrzeug ist nicht mehr
    wert als neu.
    """
    sammler = Befundsammler("R-038")
    rahmen = kontext.rahmen(Schicht.TYPED, "risiko_kfz")
    kennungen = row_ids(rahmen)
    neupreise = werte(rahmen, "neupreis_eur")
    for position, wert in enumerate(werte(rahmen, "fahrzeugwert_aktuell")):
        neupreis = neupreise[position]
        if wert is None or neupreis is None or _betrag(wert) <= _betrag(neupreis):
            continue
        sammler.melde(
            "risiko_kfz",
            kennungen[position],
            ("fahrzeugwert_aktuell", "neupreis_eur"),
            f"fahrzeugwert_aktuell={wert} uebersteigt den neupreis_eur={neupreis}",
        )
    return sammler.befund()


def pruefe_r039(kontext: Kontext) -> Befund:
    """Ein E-Kennzeichen setzt einen elektrischen Antrieb voraus.

    ``art_kennzeichen`` = 54 erzwingt ``antriebsart`` in {ELEKTRO, HYBRID}
    (Elektromobilitaetsgesetz).
    """
    sammler = Befundsammler("R-039")
    rahmen = kontext.rahmen(Schicht.TYPED, "risiko_kfz")
    kennungen = row_ids(rahmen)
    antriebe = werte(rahmen, "antriebsart")
    for position, kennzeichen in enumerate(werte(rahmen, "art_kennzeichen")):
        if kennzeichen is None or str(kennzeichen) != ArtKennzeichen.ELEKTRO.value:
            continue
        antrieb = antriebe[position]
        if antrieb is not None and str(antrieb) in _ELEKTRISCHE_ANTRIEBE:
            continue
        sammler.melde(
            "risiko_kfz",
            kennungen[position],
            ("art_kennzeichen", "antriebsart"),
            f"art_kennzeichen=54 (E-Kennzeichen), aber antriebsart={antrieb!r} ist nicht "
            f"elektrisch",
        )
    return sammler.befund()


def pruefe_r040(kontext: Kontext) -> Befund:
    """Unterversicherungsverzicht setzt eine ausreichende Versicherungssumme voraus.

    ``unterversicherungsverzicht`` erzwingt ``versicherungssumme_eur`` >= 650 Euro
    je Quadratmeter Wohnflaeche.

    Die Faustregel von 650 Euro je Quadratmeter ist branchenueblich, aber kein
    Gesetz — eine **Modellannahme**, und deshalb eine Warnung.
    """
    sammler = Befundsammler("R-040")
    rahmen = kontext.rahmen(Schicht.TYPED, "risiko_hausrat")
    kennungen = row_ids(rahmen)
    summen = werte(rahmen, "versicherungssumme_eur")
    flaechen = werte(rahmen, "wohnflaeche_qm")
    for position, verzicht in enumerate(werte(rahmen, "unterversicherungsverzicht")):
        if verzicht is None or not bool(verzicht):
            continue
        summe, flaeche = summen[position], flaechen[position]
        if summe is None or flaeche is None:
            continue
        grenze = wb.UNTERVERSICHERUNGSVERZICHT_EUR_JE_QM * int(flaeche)
        if _betrag(summe) >= grenze:
            continue
        sammler.melde(
            "risiko_hausrat",
            kennungen[position],
            ("versicherungssumme_eur", "wohnflaeche_qm", "unterversicherungsverzicht"),
            f"versicherungssumme_eur={summe} unterschreitet bei Unterversicherungsverzicht "
            f"die Grenze {grenze} ({wb.UNTERVERSICHERUNGSVERZICHT_EUR_JE_QM} Euro mal "
            f"{flaeche} Quadratmeter)",
        )
    return sammler.befund()


def pruefe_r041(kontext: Kontext) -> Befund:
    """Genau eines der beiden Hausrat-Selbstbehaltsfelder ist gefuellt.

    **Anwendbarkeitsbedingung:** Die Regel greift nur, wenn die Sparte einen
    Hausrat-Selbstbehalt kennt — also in Sparte 130. In den Kfz-Sparten sind beide
    Felder durch Zweckbindung leer, und eine Pruefung dort wuerde jeden
    Kfz-Vergleich melden.

    Die Exklusivitaet ist eine **Modellannahme des Schemas**, kein Domaenenfakt:
    Reale Produkte kennen kombinierte Formen ("10 Prozent, mindestens 500 Euro,
    hoechstens 2.500 Euro"). Deshalb eine Warnung.
    """
    sammler = Befundsammler("R-041")
    rahmen = kontext.rahmen(Schicht.TYPED, "angebot")
    kennungen = row_ids(rahmen)
    sparte_je_anfrage = zuordnung(kontext.rahmen(Schicht.TYPED, "anfrage"), "anfrage_id", "sparte")
    anfrage_ids = werte(rahmen, "anfrage_id")
    prozent_werte = werte(rahmen, "sb_hausrat_prozent")
    euro_werte = werte(rahmen, "sb_hausrat_eur")
    for position, anfrage_id in enumerate(anfrage_ids):
        sparte = sparte_je_anfrage.get(anfrage_id)
        if sparte is None or str(sparte) != Sparte.HAUSRAT.value:
            continue
        gefuellt = sum(
            1 for wert in (prozent_werte[position], euro_werte[position]) if wert is not None
        )
        if gefuellt == 1:
            continue
        zustand = "beide gefuellt" if gefuellt == 2 else "beide leer"  # noqa: PLR2004
        sammler.melde(
            "angebot",
            kennungen[position],
            ("sb_hausrat_prozent", "sb_hausrat_eur"),
            f"Genau eines der Felder sb_hausrat_prozent und sb_hausrat_eur muss gefuellt "
            f"sein, tatsaechlich sind {zustand}",
        )
    return sammler.befund()


def pruefe_r042(kontext: Kontext) -> Befund:
    """Kein Sublimit uebersteigt die Versicherungssumme.

    Ein Denial Constraint: Eine Teilsumme kann die Gesamtsumme nicht ueberschreiten.
    """
    sammler = Befundsammler("R-042")
    rahmen = kontext.rahmen(Schicht.TYPED, "risiko_hausrat")
    kennungen = row_ids(rahmen)
    summen = werte(rahmen, "versicherungssumme_eur")
    for spalte in ("sublimit_fahrrad_eur", "sublimit_wertsachen_eur"):
        for position, sublimit in enumerate(werte(rahmen, spalte)):
            summe = summen[position]
            if sublimit is None or summe is None or _betrag(sublimit) <= _betrag(summe):
                continue
            sammler.melde(
                "risiko_hausrat",
                kennungen[position],
                (spalte, "versicherungssumme_eur"),
                f"{spalte}={sublimit} uebersteigt die versicherungssumme_eur={summe}",
            )
    return sammler.befund()


# ---------------------------------------------------------------------------
# Registrierung
# ---------------------------------------------------------------------------

REGELN: Final[tuple[Regel, ...]] = (
    Regel(
        regel_id="R-026",
        beschreibung="erstzulassung liegt nicht nach dem Stichtag",
        entitaet="risiko_kfz",
        spalten=("erstzulassung",),
        granularitaet="G2",
        fehlerklasse_b="B3",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD", "FAN"),
        fachliche_grundlage="Eine Erstzulassung kann nicht in der Zukunft liegen",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r026,
    ),
    Regel(
        regel_id="R-027",
        beschreibung="erstzulassung <= zulassung_auf_vn <= stichtag",
        entitaet="risiko_kfz",
        spalten=("erstzulassung", "zulassung_auf_vn"),
        granularitaet="G2",
        fehlerklasse_b="B4",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("FAN", "RD"),
        fachliche_grundlage=(
            "Ein Fahrzeug wird nicht vor seiner Erstzulassung auf den Versicherungsnehmer "
            "zugelassen"
        ),
        schicht=Schicht.TYPED,
        pruefe=pruefe_r027,
    ),
    Regel(
        regel_id="R-028",
        beschreibung="fuehrerschein_datum >= geburtsdatum plus 17 Jahre und <= stichtag",
        entitaet="person",
        spalten=("fuehrerschein_datum", "geburtsdatum"),
        granularitaet="G2",
        fehlerklasse_b="B4",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("FAN", "RD"),
        fachliche_grundlage="Begleitetes Fahren ab 17 ist die Untergrenze (Paragraf 48a FeV)",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r028,
    ),
    Regel(
        regel_id="R-029",
        beschreibung="schadenfreie_jahre(sf_klasse_hp) <= Alter(VN) minus 17",
        entitaet="risiko_kfz, person",
        spalten=("sf_klasse_hp",),
        granularitaet="G2",
        fehlerklasse_b="B4",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("FAN", "CHU"),
        fachliche_grundlage=(
            "Man kann nicht laenger schadenfrei fahren, als man den Fuehrerschein besitzt. "
            "Abbildung in spec/01, Abschnitt 2.8"
        ),
        schicht=Schicht.TYPED,
        pruefe=pruefe_r029,
    ),
    Regel(
        regel_id="R-030",
        beschreibung="sf_ordnung(sf_klasse_vk) <= sf_ordnung(sf_klasse_hp)",
        entitaet="risiko_kfz",
        spalten=("sf_klasse_vk", "sf_klasse_hp"),
        granularitaet="G2",
        fehlerklasse_b="B4",
        erkennbarkeit_c="C2",
        schweregrad="WARNUNG",
        literatur=("FAN",),
        fachliche_grundlage="Marktueblich; Ausnahmen existieren, daher Warnung",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r030,
    ),
    Regel(
        regel_id="R-031",
        beschreibung="bruttobeitrag_jahr_eur = nettobeitrag_jahr_eur plus versicherungsteuer_eur",
        entitaet="angebot",
        spalten=(
            "bruttobeitrag_jahr_eur",
            "nettobeitrag_jahr_eur",
            "versicherungsteuer_eur",
        ),
        granularitaet="G2",
        fehlerklasse_b="B4",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("FAN", "CHU", "DAMA"),
        fachliche_grundlage="Beitragsarithmetik; Toleranz aus config.schwellen",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r031,
    ),
    Regel(
        regel_id="R-032",
        beschreibung="versicherungsteuer_eur = ROUND_HALF_UP(netto mal satz / 100, 2)",
        entitaet="angebot",
        spalten=(
            "versicherungsteuer_eur",
            "nettobeitrag_jahr_eur",
            "versicherungsteuer_satz",
        ),
        granularitaet="G2",
        fehlerklasse_b="B4",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("FAN",),
        fachliche_grundlage="Paragraf 6 in Verbindung mit Paragraf 5 VersStG",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r032,
    ),
    Regel(
        regel_id="R-033",
        beschreibung=(
            "versicherungsteuer_satz entspricht dem Effektivsatz der Sparte "
            "(051/052/053 -> 19,00; 130 -> 16,15)"
        ),
        entitaet="angebot, anfrage",
        spalten=("versicherungsteuer_satz",),
        granularitaet="G2",
        fehlerklasse_b="B4",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("FAN",),
        fachliche_grundlage=(
            "Paragraf 6 Absatz 2 in Verbindung mit Paragraf 5 Absatz 1 Nummer 3 VersStG. "
            "Musterbeispiel einer Conditional Functional Dependency"
        ),
        schicht=Schicht.TYPED,
        pruefe=pruefe_r033,
    ),
    Regel(
        regel_id="R-034",
        beschreibung="Bei steuerfreien Sparten ist versicherungsteuer_eur gleich null",
        entitaet="angebot, anfrage",
        spalten=("versicherungsteuer_eur",),
        granularitaet="G2",
        fehlerklasse_b="B4",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("FAN",),
        fachliche_grundlage=(
            "Paragraf 4 VersStG. **Im aktuellen Datenmodell nicht ausloesbar**, da die "
            "steuerfreien Sparten (Leben, Kranken, BU, Rente, Pflege) nicht erzeugt werden — "
            "bewusst implementiert und als solche gekennzeichnet"
        ),
        schicht=Schicht.TYPED,
        pruefe=pruefe_r034,
    ),
    Regel(
        regel_id="R-035",
        beschreibung="zahlweise in {1, 6} erzwingt ratenzahlungszuschlag_prozent = 0",
        entitaet="angebot, anfrage",
        spalten=("ratenzahlungszuschlag_prozent",),
        granularitaet="G2",
        fehlerklasse_b="B4",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("FAN",),
        fachliche_grundlage="Ohne Ratenzahlung kein Ratenzuschlag",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r035,
    ),
    Regel(
        regel_id="R-036",
        beschreibung=(
            "zahlbeitrag_rate_eur mal Ratenanzahl >= bruttobeitrag_jahr_eur minus "
            "Toleranz mal Ratenanzahl"
        ),
        entitaet="angebot, anfrage",
        spalten=("zahlbeitrag_rate_eur", "bruttobeitrag_jahr_eur"),
        granularitaet="G2",
        fehlerklasse_b="B4",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("CHU",),
        fachliche_grundlage=(
            "Unterjaehrige Zahlung ist nie guenstiger als jaehrliche. Die Toleranz skaliert "
            "mit der Ratenanzahl, weil sich der Rundungsfehler je Rate aufsummiert"
        ),
        schicht=Schicht.TYPED,
        pruefe=pruefe_r036,
    ),
    Regel(
        regel_id="R-037",
        beschreibung="annahmeentscheidung = ABLEHNUNG genau dann, wenn alle Beitragsfelder leer",
        entitaet="angebot",
        spalten=("annahmeentscheidung", *_BEITRAGSFELDER),
        granularitaet="G2",
        fehlerklasse_b="B4",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("FAN", "RD"),
        fachliche_grundlage="Ein abgelehntes Risiko hat keinen Beitrag",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r037,
    ),
    Regel(
        regel_id="R-038",
        beschreibung="fahrzeugwert_aktuell <= neupreis_eur",
        entitaet="risiko_kfz",
        spalten=("fahrzeugwert_aktuell", "neupreis_eur"),
        granularitaet="G2",
        fehlerklasse_b="B3",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("CHU",),
        fachliche_grundlage="Ein Fahrzeug ist nicht mehr wert als neu",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r038,
    ),
    Regel(
        regel_id="R-039",
        beschreibung="art_kennzeichen = 54 erzwingt antriebsart in {ELEKTRO, HYBRID}",
        entitaet="risiko_kfz",
        spalten=("art_kennzeichen", "antriebsart"),
        granularitaet="G2",
        fehlerklasse_b="B4",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("FAN",),
        fachliche_grundlage="E-Kennzeichen setzt elektrischen Antrieb voraus (EmoG)",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r039,
    ),
    Regel(
        regel_id="R-040",
        beschreibung=(
            "unterversicherungsverzicht erzwingt versicherungssumme_eur >= 650 mal "
            "wohnflaeche_qm"
        ),
        entitaet="risiko_hausrat",
        spalten=("versicherungssumme_eur", "wohnflaeche_qm", "unterversicherungsverzicht"),
        granularitaet="G2",
        fehlerklasse_b="B4",
        erkennbarkeit_c="C2",
        schweregrad="WARNUNG",
        literatur=("FAN",),
        fachliche_grundlage="Branchenuebliche Faustregel 650 Euro je Quadratmeter, Modellannahme",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r040,
    ),
    Regel(
        regel_id="R-041",
        beschreibung=(
            "Genau eines von sb_hausrat_prozent und sb_hausrat_eur ist gefuellt — nur "
            "anwendbar, wenn die Sparte einen Hausrat-Selbstbehalt kennt"
        ),
        entitaet="angebot, anfrage",
        spalten=("sb_hausrat_prozent", "sb_hausrat_eur"),
        granularitaet="G2",
        fehlerklasse_b="B4",
        erkennbarkeit_c="C2",
        schweregrad="WARNUNG",
        literatur=("RD", "KIM"),
        fachliche_grundlage=(
            "Modellannahme des Schemas, kein Domaenenfakt — reale Produkte kennen "
            "kombinierte Formen"
        ),
        schicht=Schicht.TYPED,
        pruefe=pruefe_r041,
    ),
    Regel(
        regel_id="R-042",
        beschreibung=(
            "sublimit_fahrrad_eur und sublimit_wertsachen_eur <= versicherungssumme_eur"
        ),
        entitaet="risiko_hausrat",
        spalten=("sublimit_fahrrad_eur", "sublimit_wertsachen_eur", "versicherungssumme_eur"),
        granularitaet="G2",
        fehlerklasse_b="B4",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("CHU",),
        fachliche_grundlage="Ein Sublimit kann die Gesamtsumme nicht uebersteigen",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r042,
    ),
)
