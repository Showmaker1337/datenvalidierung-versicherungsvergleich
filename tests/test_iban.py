"""Prueft ``src/common/iban.py`` gegen bekannte gueltige und ungueltige IBANs.

Die gueltigen Beispiele sind veroeffentlichte Testkonten deutscher Institute; sie
wurden zusaetzlich mit einer unabhaengigen Mod-97-Rechnung nachgeprueft. Die
ungueltigen Beispiele decken die vier praxisrelevanten Fehlerbilder ab, die auch
als Injektionsvarianten F2-c und F2-d vorgesehen sind: geaenderte Ziffer,
falsche Pruefziffer, zu kurz, zu lang.
"""

from __future__ import annotations

import pytest

from src.common.iban import (
    IbanFehler,
    baue_iban,
    berechne_pruefziffer,
    hat_deutsches_format,
    ist_gueltig,
    normalisiere,
)

GUELTIGE_IBANS: tuple[str, ...] = (
    "DE89370400440532013000",
    "DE02120300000000202051",
    "DE02100500000054540402",
    "DE02300209000106531065",
    "DE02701500000000594937",
    "DE12500105170648489890",
    "DE75512108001245126199",
)

UNGUELTIGE_IBANS: tuple[tuple[str, str], ...] = (
    ("DE89370400440532013001", "letzte Ziffer veraendert (F2-c)"),
    ("DE00370400440532013000", "Pruefziffer durch 00 ersetzt"),
    ("DE8937040044053201300", "21 Zeichen statt 22 (F2-d)"),
    ("DE893704004405320130000", "23 Zeichen statt 22 (F2-d)"),
    ("DE8X370400440532013000", "Buchstabe im Ziffernteil"),
    ("DE47370400440532013000", "Pruefziffer eines anderen Kontos"),
)


@pytest.mark.parametrize("iban", GUELTIGE_IBANS)
def test_gueltige_iban_besteht_pruefziffer(iban: str) -> None:
    """Alle bekannten gueltigen IBANs bestehen die Mod-97-Pruefung (R-004)."""
    assert ist_gueltig(iban), f"{iban} sollte gueltig sein"


@pytest.mark.parametrize(("iban", "grund"), UNGUELTIGE_IBANS)
def test_ungueltige_iban_faellt_durch(iban: str, grund: str) -> None:
    """Alle bekannten ungueltigen IBANs fallen durch."""
    assert not ist_gueltig(iban), f"{iban} sollte ungueltig sein ({grund})"


@pytest.mark.parametrize("iban", GUELTIGE_IBANS)
def test_gueltige_iban_hat_deutsches_format(iban: str) -> None:
    """Die Beispiele erfuellen zusaetzlich das Muster aus R-003."""
    assert hat_deutsches_format(iban)


def test_format_und_pruefziffer_sind_getrennte_regeln() -> None:
    """R-003 und R-004 pruefen Verschiedenes und duerfen nicht vermischt werden.

    Eine franzoesische IBAN hat eine korrekte Pruefziffer, aber kein deutsches
    Format. Eine deutsche IBAN mit falscher Pruefziffer ist umgekehrt formal
    einwandfrei.
    """
    franzoesisch = "FR7630006000011234567890189"
    assert ist_gueltig(franzoesisch)
    assert not hat_deutsches_format(franzoesisch)

    deutsch_falsch = "DE89370400440532013001"
    assert hat_deutsches_format(deutsch_falsch)
    assert not ist_gueltig(deutsch_falsch)


def test_normalisierung_toleriert_schreibweise() -> None:
    """Leerzeichen und Kleinbuchstaben stoeren die Pruefziffernpruefung nicht."""
    assert normalisiere("de89 3704 0044 0532 0130 00") == "DE89370400440532013000"
    assert ist_gueltig("de89 3704 0044 0532 0130 00")
    # Fuer die Formatregel sind Leerzeichen sehr wohl ein Verstoss.
    assert not hat_deutsches_format("DE89 3704 0044 0532 0130 00")


def test_leere_und_unsinnige_eingaben_werfen_nicht() -> None:
    """Ein unbrauchbarer Wert ist ein Befund, kein Absturz."""
    for wert in ("", "DE", "!!!", "DE89-3704-0044", "1234"):
        assert ist_gueltig(wert) is False


def test_pruefziffer_reproduziert_bekannte_iban() -> None:
    """Aus Bankleitzahl und Kontonummer entsteht die veroeffentlichte Pruefziffer."""
    assert berechne_pruefziffer("37040044", "0532013000") == "89"
    assert berechne_pruefziffer("12030000", "0000202051") == "02"


def test_kontonummer_wird_links_aufgefuellt() -> None:
    """Eine kurze Kontonummer wird auf zehn Stellen aufgefuellt, nicht abgewiesen."""
    assert berechne_pruefziffer("37040044", "532013000") == "89"
    assert baue_iban("37040044", "532013000") == "DE89370400440532013000"


@pytest.mark.parametrize(
    ("blz", "konto"),
    [
        ("3704004", "0532013000"),  # Bankleitzahl zu kurz
        ("370400444", "0532013000"),  # Bankleitzahl zu lang
        ("3704004X", "0532013000"),  # Buchstabe in der Bankleitzahl
        ("37040044", "05320130001"),  # Kontonummer zu lang
        ("37040044", "05320130X0"),  # Buchstabe in der Kontonummer
        ("37040044", ""),  # leere Kontonummer
    ],
)
def test_unbrauchbare_bestandteile_werfen(blz: str, konto: str) -> None:
    """Fehlerhafte Bestandteile fuehren zum Abbruch, nicht zu einer stillen Notloesung."""
    with pytest.raises(IbanFehler):
        berechne_pruefziffer(blz, konto)


@pytest.mark.parametrize("konto", ["0000000001", "9999999999", "0532013000", "1", "4711"])
def test_erzeugte_ibans_sind_immer_gueltig(konto: str) -> None:
    """Jede erzeugte IBAN erfuellt Format und Pruefziffer — Grundlage des Generators."""
    iban = baue_iban("50010517", konto)
    assert len(iban) == 22
    assert hat_deutsches_format(iban)
    assert ist_gueltig(iban)
