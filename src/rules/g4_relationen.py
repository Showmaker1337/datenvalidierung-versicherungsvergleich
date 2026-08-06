"""G4 — relationsuebergreifende Regeln (R-049 bis R-051).

Eine G4-Regel prueft eine Bedingung **zwischen Tabellen**: Loest ein Fremdschluessel
auf, passt der Ort zur Postleitzahl, stimmen die aus dem Fahrzeugkatalog
abgeleiteten Merkmale mit dem Referenzeintrag ueberein?

R-050 und R-051 sind die beiden Regeln des Erkennbarkeitsgrads **C3**: Sie sind ohne
externe Referenzdaten nicht pruefbar. Genau daran zeigt sich der Unterschied zu C1 —
eine Musterpruefung braucht nur den Wert, ein Referenzabgleich braucht die Welt
ausserhalb des Datensatzes. Beide Referenztabellen liegen versioniert unter
``data/reference``; zur Laufzeit wird nichts nachgeladen (CLAUDE.md, Abschnitt 5).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from src.common.pfade import Schicht
from src.rules.modell import Befund, Befundsammler, Regel, row_ids, werte

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from src.rules.modell import Kontext

__all__ = ["REGELN"]

#: Alle Fremdschluesselbeziehungen des Sternschemas (R-049).
#:
#: Aufbau je Eintrag: Quellentitaet, Quellspalte, Zielentitaet, Zielspalte. Die
#: Aufzaehlung folgt ``spec/02``, R-049 und entspricht der GDV-Referenzlogik
#: (Satzart 0220 auf 0210 ueber die Referenznummer, auf 0100 ueber die
#: Personennummer).
_FREMDSCHLUESSEL: Final[tuple[tuple[str, str, str, str], ...]] = (
    ("angebot", "anfrage_id", "anfrage", "anfrage_id"),
    ("angebot", "tarif_id", "tarif", "tarif_id"),
    ("anfrage", "vn_person_id", "person", "person_id"),
    ("risiko_kfz", "anfrage_id", "anfrage", "anfrage_id"),
    ("risiko_hausrat", "anfrage_id", "anfrage", "anfrage_id"),
    ("zahlung", "anfrage_id", "anfrage", "anfrage_id"),
)

#: Aus dem Fahrzeugkatalog abgeleitete Felder (R-051).
#:
#: ``typklasse_tk`` und ``typklasse_vk`` sind ausserhalb der Kasko durch
#: Zweckbindung leer (``spec/01``, Abschnitt 3.3); leere Felder werden deshalb
#: uebergangen.
_ABGELEITETE_FAHRZEUGFELDER: Final[tuple[str, ...]] = (
    "leistung_kw",
    "antriebsart",
    "typklasse_hp",
    "typklasse_tk",
    "typklasse_vk",
)

def _vergleichbar(wert: Any, referenz: Any) -> bool:  # noqa: ANN401
    """Vergleicht einen Datenwert mit seinem Referenzeintrag typunabhaengig.

    Der Vergleich laeuft ueber die Zeichenkettendarstellung. Grund: Die
    Referenztabellen fuehren die Typklassen als ``int64``, der Datensatz als
    ``Int64``; ein direkter Vergleich haenge damit an der pandas-Typisierung statt
    am Inhalt.
    """
    return str(wert) == str(referenz)


def pruefe_r049(kontext: Kontext) -> Befund:
    """Alle Fremdschluessel loesen auf.

    Referential Integrity Violation im Sinne von Rahm und Do. Geprueft werden die
    sechs Beziehungen aus :data:`_FREMDSCHLUESSEL`.

    Ein **leerer** Fremdschluessel wird nicht gemeldet: Das ist ein fehlender Wert
    und damit Sache von R-001 beziehungsweise R-057. Diese Regel prueft, ob ein
    gesetzter Verweis ins Leere zeigt.
    """
    sammler = Befundsammler("R-049")
    for quelle, quellspalte, ziel, zielspalte in _FREMDSCHLUESSEL:
        zielrahmen = kontext.rahmen(Schicht.TYPED, ziel)
        bekannt = {wert for wert in werte(zielrahmen, zielspalte) if wert is not None}
        quellrahmen = kontext.rahmen(Schicht.TYPED, quelle)
        kennungen = row_ids(quellrahmen)
        for position, wert in enumerate(werte(quellrahmen, quellspalte)):
            if wert is None or wert in bekannt:
                continue
            sammler.melde(
                quelle,
                kennungen[position],
                (quellspalte,),
                f"{quelle}.{quellspalte}={wert!r} loest in {ziel}.{zielspalte} nicht auf",
            )
    return sammler.befund()


def pruefe_r050(kontext: Kontext) -> Befund:
    """``plz`` existiert in ``plz_ort`` und ``ort`` stimmt mit dem Referenzeintrag ueberein.

    Das klassische CFD-Beispiel: Land bestimmt Postleitzahl bestimmt Ort. Zugleich
    eine Regel des Erkennbarkeitsgrads C3 — ohne die Referenztabelle ist die
    Bedingung nicht pruefbar.

    Ein abweichender Ort meldet **beide** Felder unter einer ``verstoss_id``:
    Ob die Postleitzahl oder der Ort verfaelscht wurde, ist von aussen nicht
    entscheidbar.
    """
    sammler = Befundsammler("R-050")
    referenz = kontext.referenztabelle("plz_ort")
    ort_je_plz = {
        str(plz): str(ort)
        for plz, ort in zip(referenz["plz"], referenz["ort"], strict=True)
    }
    rahmen = kontext.rahmen(Schicht.TYPED, "person")
    kennungen = row_ids(rahmen)
    orte = werte(rahmen, "ort")
    for position, plz in enumerate(werte(rahmen, "plz")):
        if plz is None:
            continue
        erwartet = ort_je_plz.get(str(plz))
        if erwartet is None:
            sammler.melde(
                "person",
                kennungen[position],
                ("plz",),
                f"plz={plz!r} existiert nicht in der Referenztabelle plz_ort",
            )
            continue
        ort = orte[position]
        if ort is None or _vergleichbar(ort, erwartet):
            continue
        sammler.melde(
            "person",
            kennungen[position],
            ("ort", "plz"),
            f"ort={ort!r} passt nicht zur plz={plz!r}; die Referenz nennt {erwartet!r}",
        )
    return sammler.befund()


def pruefe_r051(kontext: Kontext) -> Befund:
    """(``hsn``, ``tsn``) existiert in ``typklassen`` und die abgeleiteten Felder stimmen.

    Abgeglichen werden ``leistung_kw``, ``antriebsart`` und die drei Typklassen.
    Eine Abweichung deutet auf einen Mappingfehler zwischen Schnittstelle und
    Fahrzeugkatalog hin — der Fahrzeugschluessel sagt etwas anderes als die
    daneben gelieferten Merkmale.

    Leere abgeleitete Felder werden uebergangen: ``typklasse_tk`` und
    ``typklasse_vk`` sind ausserhalb der Kaskosparten durch Zweckbindung leer.
    """
    sammler = Befundsammler("R-051")
    referenz = kontext.referenztabelle("typklassen")
    eintraege = {
        (str(hsn), str(tsn)): zeile
        for hsn, tsn, zeile in zip(
            referenz["hsn"],
            referenz["tsn"],
            referenz.to_dict(orient="records"),
            strict=True,
        )
    }
    rahmen = kontext.rahmen(Schicht.TYPED, "risiko_kfz")
    kennungen = row_ids(rahmen)
    tsn_werte = werte(rahmen, "tsn")
    abgeleitet = {spalte: werte(rahmen, spalte) for spalte in _ABGELEITETE_FAHRZEUGFELDER}
    for position, hsn in enumerate(werte(rahmen, "hsn")):
        tsn = tsn_werte[position]
        if hsn is None or tsn is None:
            continue
        eintrag = eintraege.get((str(hsn), str(tsn)))
        if eintrag is None:
            sammler.melde(
                "risiko_kfz",
                kennungen[position],
                ("hsn", "tsn"),
                f"(hsn, tsn) = ({hsn!r}, {tsn!r}) existiert nicht im Fahrzeugkatalog",
            )
            continue
        for spalte in _ABGELEITETE_FAHRZEUGFELDER:
            wert = abgeleitet[spalte][position]
            if wert is None or _vergleichbar(wert, eintrag[spalte]):
                continue
            sammler.melde(
                "risiko_kfz",
                kennungen[position],
                (spalte, "hsn", "tsn"),
                f"{spalte}={wert!r} weicht vom Fahrzeugkatalog ab; zu "
                f"(hsn, tsn) = ({hsn!r}, {tsn!r}) gehoert {eintrag[spalte]!r}",
            )
    return sammler.befund()


# ---------------------------------------------------------------------------
# Registrierung
# ---------------------------------------------------------------------------

REGELN: Final[tuple[Regel, ...]] = (
    Regel(
        regel_id="R-049",
        beschreibung=(
            "Alle Fremdschluessel sind aufloesbar: angebot.anfrage_id, angebot.tarif_id, "
            "anfrage.vn_person_id, risiko_*.anfrage_id, zahlung.anfrage_id"
        ),
        entitaet="alle",
        spalten=("anfrage_id", "tarif_id", "vn_person_id"),
        granularitaet="G4",
        fehlerklasse_b="B4",
        erkennbarkeit_c="C1",
        schweregrad="HART",
        literatur=("RD", "OLI"),
        fachliche_grundlage=(
            "GDV-Referenzlogik: Satzart 0220 auf 0210 ueber die Referenznummer, auf 0100 "
            "ueber die Personennummer"
        ),
        schicht=Schicht.TYPED,
        pruefe=pruefe_r049,
    ),
    Regel(
        regel_id="R-050",
        beschreibung="plz existiert in plz_ort und ort stimmt mit dem Referenzeintrag ueberein",
        entitaet="person",
        spalten=("plz", "ort"),
        granularitaet="G4",
        fehlerklasse_b="B3",
        erkennbarkeit_c="C3",
        schweregrad="HART",
        literatur=("RD", "FAN", "ISO"),
        fachliche_grundlage="Klassisches CFD-Beispiel: Land bestimmt PLZ bestimmt Ort",
        schicht=Schicht.TYPED,
        pruefe=pruefe_r050,
    ),
    Regel(
        regel_id="R-051",
        beschreibung=(
            "(hsn, tsn) existiert in typklassen und die abgeleiteten Felder leistung_kw, "
            "antriebsart und typklasse_* stimmen mit dem Referenzeintrag ueberein"
        ),
        entitaet="risiko_kfz",
        spalten=("hsn", "tsn", *_ABGELEITETE_FAHRZEUGFELDER),
        granularitaet="G4",
        fehlerklasse_b="B4",
        erkennbarkeit_c="C3",
        schweregrad="HART",
        literatur=("RD", "FAN"),
        fachliche_grundlage=(
            "Eine Abweichung deutet auf einen Mappingfehler zwischen Schnittstelle und "
            "Fahrzeugkatalog hin"
        ),
        schicht=Schicht.TYPED,
        pruefe=pruefe_r051,
    ),
)
