"""Prueft die Beitragsarithmetik einschliesslich der Rundung.

Nachgerechnet wird von unten nach oben, in derselben Reihenfolge wie in
``spec/01_datenmodell.md``, Abschnitt 3.6, aber mit eigenstaendig formulierten
Bedingungen — der Test importiert nichts aus dem Generator ausser den
gemeinsamen Bausteinen in ``src/common``.

Alle Vergleiche laufen in :class:`~decimal.Decimal`. Ein Vergleich in ``float``
wuerde genau den Rundungsfehler verdecken, den dieser Test finden soll.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any

import pytest

from src.common import wertebereiche as wb
from src.common.enums import (
    RATENANZAHL_JE_ZAHLWEISE,
    ZAHLWEISEN_IM_GENERATOR,
    Sparte,
    Zahlweise,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    import pandas as pd

    from src.common.config import Config

#: Mindestzahl der Stichproben je Sparte (Vorgabe des Phasenprompts).
STICHPROBEN_JE_SPARTE = 10

#: Zahlweisen ohne Ratenzahlung; dort ist der Ratenzuschlag null (spaeter R-035).
_OHNE_RATEN = (Zahlweise.JAEHRLICH, Zahlweise.EINMALBETRAG)

#: Zahlweisen, die im Datensatz vorkommen (spec/01, Abschnitt 3.1).
_ZAHLWEISEN_IM_DATENSATZ = tuple(int(wert) for wert in ZAHLWEISEN_IM_GENERATOR)


def _angebote_mit_kontext(datensatz: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Verbindet die Angebote mit Sparte und Zahlweise ihrer Anfrage."""
    anfragen = datensatz["anfrage"][["anfrage_id", "sparte", "zahlweise"]]
    verbunden = datensatz["angebot"].merge(anfragen, on="anfrage_id", how="left", validate="m:1")
    return verbunden.dropna(subset=["nettobeitrag_jahr_eur"])


def _stichprobe(rahmen: pd.DataFrame, sparte: str) -> pd.DataFrame:
    """Waehlt die ersten Zeilen einer Sparte; die Auswahl ist deterministisch."""
    gefiltert = rahmen[rahmen["sparte"] == sparte]
    assert len(gefiltert) >= STICHPROBEN_JE_SPARTE, f"Zu wenige Angebote der Sparte {sparte}"
    return gefiltert.head(max(STICHPROBEN_JE_SPARTE, len(gefiltert) // 20))

def _zeilen(rahmen: pd.DataFrame) -> list[dict[str, Any]]:
    """Gibt die Zeilen eines Datenrahmens als Abbildungen Spalte auf Wert zurueck.

    Bewusst statt ``itertuples``: Die pandas-Typstubs beschreiben jedes Feld eines
    Namenstupels als grosse Vereinigung ueber alle denkbaren Skalartypen. Jeder
    Vergleich und jede Rechnung darauf scheitert dann in der strikten
    Typpruefung, obwohl der Wert zur Laufzeit eindeutig ist.
    """
    return [
        {str(name): wert for name, wert in eintrag.items()}
        for eintrag in rahmen.to_dict("records")
    ]



@pytest.mark.parametrize("sparte", [eintrag.value for eintrag in Sparte])
def test_steuersatz_entspricht_dem_effektivsatz(
    datensatz: dict[str, pd.DataFrame], sparte: str
) -> None:
    """``versicherungsteuer_satz`` ist der Effektivsatz der Sparte (spaeter R-033)."""
    erwartet = wb.VERSICHERUNGSTEUER_EFFEKTIVSATZ[Sparte(sparte)]
    stichprobe = _stichprobe(_angebote_mit_kontext(datensatz), sparte)
    for zeile in _zeilen(stichprobe):
        assert zeile["versicherungsteuer_satz"] == erwartet


@pytest.mark.parametrize("sparte", [eintrag.value for eintrag in Sparte])
def test_steuerbetrag_ist_kaufmaennisch_gerundet(
    datensatz: dict[str, pd.DataFrame], sparte: str
) -> None:
    """``versicherungsteuer_eur`` = ROUND_HALF_UP(netto * satz / 100) (spaeter R-032)."""
    stichprobe = _stichprobe(_angebote_mit_kontext(datensatz), sparte)
    for zeile in _zeilen(stichprobe):
        roh = zeile["nettobeitrag_jahr_eur"] * zeile["versicherungsteuer_satz"] / 100
        erwartet = roh.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert zeile["versicherungsteuer_eur"] == erwartet


@pytest.mark.parametrize("sparte", [eintrag.value for eintrag in Sparte])
def test_bruttobeitrag_ist_die_summe(datensatz: dict[str, pd.DataFrame], sparte: str) -> None:
    """``brutto`` = ``netto`` + ``steuer``, exakt und ohne Toleranz (spaeter R-031)."""
    stichprobe = _stichprobe(_angebote_mit_kontext(datensatz), sparte)
    for zeile in _zeilen(stichprobe):
        assert (
            zeile["bruttobeitrag_jahr_eur"]
            == zeile["nettobeitrag_jahr_eur"] + zeile["versicherungsteuer_eur"]
        )


@pytest.mark.parametrize("sparte", [eintrag.value for eintrag in Sparte])
def test_rate_folgt_aus_brutto_zuschlag_und_ratenanzahl(
    datensatz: dict[str, pd.DataFrame], sparte: str
) -> None:
    """``zahlbeitrag_rate_eur`` = ROUND_HALF_UP(brutto * (1 + rzz/100) / Ratenanzahl)."""
    stichprobe = _stichprobe(_angebote_mit_kontext(datensatz), sparte)
    for zeile in _zeilen(stichprobe):
        ratenanzahl = RATENANZAHL_JE_ZAHLWEISE[Zahlweise(int(zeile["zahlweise"]))]
        aufschlag = Decimal(1) + zeile["ratenzahlungszuschlag_prozent"] / Decimal(100)
        erwartet = (zeile["bruttobeitrag_jahr_eur"] * aufschlag / ratenanzahl).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        assert zeile["zahlbeitrag_rate_eur"] == erwartet


def test_ratenzuschlag_nur_bei_unterjaehriger_zahlung(
    datensatz: dict[str, pd.DataFrame],
) -> None:
    """Bei Ratenanzahl eins ist der Zuschlag null, sonst positiv (spaeter R-035)."""
    rahmen = _angebote_mit_kontext(datensatz)
    for zeile in _zeilen(rahmen):
        zahlweise = Zahlweise(int(zeile["zahlweise"]))
        if zahlweise in _OHNE_RATEN:
            assert zeile["ratenzahlungszuschlag_prozent"] == Decimal("0.00")
        else:
            unten, oben = wb.RATENZAHLUNGSZUSCHLAG_PROZENT
            assert unten < zeile["ratenzahlungszuschlag_prozent"] <= oben


def test_unterjaehrige_zahlung_ist_nie_guenstiger(
    datensatz: dict[str, pd.DataFrame], testkonfiguration: Config
) -> None:
    """Rate mal Ratenanzahl deckt den Jahresbeitrag (spaeter R-036).

    Die Toleranz skaliert mit der Ratenanzahl, weil sich der Rundungsfehler je
    Rate aufsummiert — genau die Begruendung, die R-036 mitfuehrt.
    """
    toleranz_je_rate = testkonfiguration.schwellen.r036_toleranz_je_rate_eur
    for zeile in _zeilen(_angebote_mit_kontext(datensatz)):
        ratenanzahl = RATENANZAHL_JE_ZAHLWEISE[Zahlweise(int(zeile["zahlweise"]))]
        summe = zeile["zahlbeitrag_rate_eur"] * ratenanzahl
        assert summe >= zeile["bruttobeitrag_jahr_eur"] - toleranz_je_rate * ratenanzahl


def test_alle_beitragsfelder_sind_nicht_negativ(datensatz: dict[str, pd.DataFrame]) -> None:
    """Kein Beitrags- oder Summenfeld ist negativ (spaeter R-021)."""
    felder = (
        "nettobeitrag_jahr_eur",
        "versicherungsteuer_eur",
        "bruttobeitrag_jahr_eur",
        "ratenzahlungszuschlag_prozent",
        "zahlbeitrag_rate_eur",
        "sb_tk_eur",
        "sb_vk_eur",
        "sb_hausrat_prozent",
        "sb_hausrat_eur",
    )
    for feld in felder:
        werte = datensatz["angebot"][feld].dropna()
        assert all(wert >= Decimal(0) for wert in werte), f"{feld} enthaelt negative Werte"
    assert all(wert > Decimal(0) for wert in datensatz["angebot"]["nettobeitrag_jahr_eur"].dropna())


def test_beitraege_haben_genau_zwei_nachkommastellen(
    datensatz: dict[str, pd.DataFrame],
) -> None:
    """Jeder Geldbetrag ist auf zwei Nachkommastellen quantisiert."""
    felder = ("nettobeitrag_jahr_eur", "versicherungsteuer_eur", "zahlbeitrag_rate_eur")
    for feld in felder:
        for wert in datensatz["angebot"][feld].dropna():
            assert -wert.as_tuple().exponent == 2, f"{feld}: {wert} hat keine zwei Nachkommastellen"


def test_ratenanzahl_und_zahlweise_passen_zusammen(datensatz: dict[str, pd.DataFrame]) -> None:
    """Nur die im Generator vorgesehenen Zahlweisen kommen vor (spec/01, Abschnitt 3.1)."""
    gezogen = {int(wert) for wert in datensatz["anfrage"]["zahlweise"]}
    assert gezogen <= {int(eintrag) for eintrag in Zahlweise}
    assert int(Zahlweise.SONSTIGES) not in gezogen
    assert int(Zahlweise.BEITRAGSFREI) not in gezogen


def test_jahresbeitrag_liegt_im_plausiblen_korridor(
    datensatz: dict[str, pd.DataFrame], testkonfiguration: Config
) -> None:
    """Der **Bruttojahresbeitrag** bleibt im Korridor von R-053.

    R-053 prueft ausdruecklich ``bruttobeitrag_jahr_eur`` und nicht die Rate: Bei
    monatlicher Zahlweise ist die Rate ein Zwoelftel und laege systematisch
    unterhalb des Korridors.

    Der Generator kappt nicht an diesem Korridor — er haelt ihn ein, weil das
    Beitragsmodell so kalibriert ist. Schlaegt dieser Test fehl, ist entweder das
    Modell oder der Schwellenwert zu pruefen, **nicht** eine Kappung einzubauen.
    """
    korridore = {
        Sparte.HAUSRAT.value: testkonfiguration.schwellen.r053_korridor_hausrat_eur,
    }
    standard = testkonfiguration.schwellen.r053_korridor_kfz_eur
    for zeile in _zeilen(_angebote_mit_kontext(datensatz)):
        unten, oben = korridore.get(str(zeile["sparte"]), standard)
        beitrag = zeile["bruttobeitrag_jahr_eur"]
        assert unten <= beitrag <= oben, (
            f"Sparte {zeile['sparte']}: Jahresbeitrag {beitrag} ausserhalb [{unten}, {oben}]"
        )


def test_zahlweise_haengt_nicht_an_der_beitragshoehe(
    datensatz: dict[str, pd.DataFrame],
) -> None:
    """Die Zahlweise wird unabhaengig vom Beitrag gezogen.

    Eine frühere Fassung koppelte beides, um die Rate in einem Korridor zu halten.
    Diese kuenstliche Abhaengigkeit haette die Auswertung beeinflussen koennen,
    ohne dass ihre Ursache im Datensatz sichtbar gewesen waere. Geprueft wird
    ueber den mittleren Bruttojahresbeitrag je Zahlweise: Er darf zwischen den
    Zahlweisen nur zufaellig streuen.
    """
    beitraege: dict[int, list[float]] = {}
    for zeile in _zeilen(_angebote_mit_kontext(datensatz)):
        zahlweise = int(zeile["zahlweise"])
        beitraege.setdefault(zahlweise, []).append(float(zeile["bruttobeitrag_jahr_eur"]))

    mittelwerte: dict[int, float] = {}
    for zahlweise, werte in sorted(beitraege.items()):
        assert len(werte) >= 100, f"Zahlweise {zahlweise} ist zu schwach besetzt"
        mittelwerte[zahlweise] = sum(werte) / len(werte)

    assert len(mittelwerte) == len(_ZAHLWEISEN_IM_DATENSATZ), (
        f"Es fehlen Zahlweisen: {sorted(set(_ZAHLWEISEN_IM_DATENSATZ) - set(mittelwerte))}"
    )
    spanne = max(mittelwerte.values()) / min(mittelwerte.values())
    assert spanne <= 1.25, (
        f"Der mittlere Jahresbeitrag unterscheidet sich zu stark je Zahlweise: {mittelwerte}"
    )
