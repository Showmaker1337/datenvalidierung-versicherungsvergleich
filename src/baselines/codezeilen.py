"""Objektive Messung der Codezeilen je Regel ueber den abstrakten Syntaxbaum.

Die Arbeit vergleicht den eigenen Regelkatalog mit einem Framework (B3, cuallee)
unter anderem in der Kennzahl **Aufwand**: Wie viel Quelltext kostet dieselbe
fachliche Bedingung hier und dort? Dieses Modul liefert die Zahl.

Warum gemessen und nicht geschaetzt wird
----------------------------------------

"Etwa fuenf Zeilen" ist keine Kennzahl, sondern ein Eindruck. Eine geschaetzte
Zahl laesst sich weder pruefen noch reproduzieren, und sie faellt genau in dem
Moment auseinander, in dem jemand nachzaehlt. Gemessen wird deshalb am
abstrakten Syntaxbaum der Quelldatei: Der Zaehler liest dieselbe Datei, die
ausgefuehrt wird, und das Ergebnis aendert sich automatisch mit, wenn eine Regel
umgeschrieben wird. Zusammen mit dem Git-Tag ``freeze-regelkatalog`` ist die Zahl
damit an einen bestimmten Stand gebunden und im Anhang belegbar.

Was genau gezaehlt wird
-----------------------

Gezaehlt werden die **Anweisungszeilen des Funktionsrumpfes ohne Docstring**, je
Anweisung ``end_lineno - lineno + 1``. Das ist bewusst nicht "alle Zeilen der
Funktion":

* Die Signatur zaehlt nicht mit — sie ist bei beiden Verfahren durch das jeweilige
  Protokoll vorgegeben und traegt keine fachliche Aussage.
* Der Docstring zaehlt nicht mit. Sonst wuerde ausgerechnet das Projekt bestraft,
  das seine Regeln begruendet, und die Kennzahl misst die Begruendungsdichte statt
  den Implementierungsaufwand.
* Leerzeilen und reine Kommentarzeilen zaehlen nicht mit, weil sie im
  Syntaxbaum nicht vorkommen. Eine mehrzeilig formatierte Anweisung zaehlt dagegen
  vollstaendig — sie ist eine Anweisung, die eben so viel Platz braucht.

Die Zahlen sind **nur innerhalb dieses Vergleichs** aussagekraeftig. Sie haengen
am Formatierungsstil (hier: ruff format, Zeilenlaenge 100) und daran, wie viel
gemeinsame Mechanik in Hilfsfunktionen ausgelagert ist. Beide Seiten teilen sich
Hilfsfunktionen (``_pruefe_spalten`` im Prototyp, ``_mit_leerwert`` in B3), die in
keiner Regelzahl auftauchen. Ein Vergleich mit Zahlen aus anderen Projekten waere
deshalb unzulaessig; der Vergleich Prototyp gegen Framework auf **derselben**
Regelmenge ist es nicht.

Warum das kein Import ist
-------------------------

Gemessen wird ``src/rules/g1_attribut.py`` als **Datei**, nicht als Modul. Der
Zaehler liest den Quelltext und baut daraus einen Syntaxbaum; er importiert
nichts. Das ist wesentlich, weil ``src/baselines/b3_framework.py`` nach dem
Phasenkontrakt nichts aus ``src.rules`` importieren darf — ein Blick in den
Regelkatalog waere genau der Zirkelschluss, den der Vergleich ausschliessen soll.
Eine Zeilenzahl aus einer Textdatei ist kein solcher Blick.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping

__all__ = [
    "DATEI_B3",
    "DATEI_PROTOTYP_G1",
    "MUSTER_B3",
    "MUSTER_PROTOTYP",
    "CodezeilenFehler",
    "codezeilen_der_funktion",
    "codezeilen_je_regel",
]

#: Wurzelverzeichnis des Repositories, aus der Lage dieser Datei abgeleitet.
_WURZEL: Final[Path] = Path(__file__).resolve().parents[2]

#: Quelldatei der G1-Regeln des Prototyps.
DATEI_PROTOTYP_G1: Final[Path] = _WURZEL / "src" / "rules" / "g1_attribut.py"

#: Quelldatei der G1-Regeln in der Check-API von cuallee.
DATEI_B3: Final[Path] = _WURZEL / "src" / "baselines" / "b3_framework.py"

#: Namensmuster der Regelfunktionen des Prototyps, zum Beispiel ``pruefe_r014``.
MUSTER_PROTOTYP: Final[str] = r"^pruefe_r(\d{3})$"

#: Namensmuster der Regelfunktionen von B3, zum Beispiel ``_r014``.
MUSTER_B3: Final[str] = r"^_r(\d{3})$"


class CodezeilenFehler(RuntimeError):
    """Eine Quelldatei oder eine Funktion darin ist nicht messbar.

    Bewusst eine Ausnahme und kein Ersatzwert: Eine Null in der Aufwandstabelle
    liest sich wie "kostet keinen Quelltext" und nicht wie "wurde nicht
    gefunden". Ein Tippfehler im Funktionsnamen soll auffallen, nicht als
    Messergebnis erscheinen.
    """


def _funktionen(datei: Path) -> dict[str, ast.FunctionDef]:
    """Liest eine Quelldatei und gibt ihre Funktionsdefinitionen je Name zurueck.

    Betrachtet werden ausschliesslich Funktionen auf **Modulebene**. Verschachtelte
    Funktionen — etwa die Praedikate, die eine Fabrikfunktion zurueckgibt — sind
    Teil ihrer aeusseren Funktion und werden ueber deren ``end_lineno`` bereits
    mitgezaehlt. Wuerde man sie zusaetzlich als eigene Eintraege fuehren, kaeme
    derselbe Name mehrfach vor (``erfuellt`` in ``src/rules/g1_attribut.py``) und
    die Zeilen zaehlten doppelt.

    Args:
        datei: Pfad der Quelldatei.

    Returns:
        Eine Abbildung Funktionsname auf den Knoten der Definition.

    Raises:
        CodezeilenFehler: Wenn die Datei fehlt, nicht lesbar ist, sich nicht
            parsen laesst oder denselben Funktionsnamen zweimal auf Modulebene
            definiert.
    """
    if not datei.is_file():
        raise CodezeilenFehler(
            f"Die Quelldatei {datei} fehlt. Der Pfad steht in "
            "src/baselines/codezeilen.py und wird relativ zum Repositoriumswurzel"
            "verzeichnis gebildet."
        )
    quelltext = datei.read_text(encoding="utf-8")
    try:
        baum = ast.parse(quelltext, filename=str(datei))
    except SyntaxError as fehler:  # pragma: no cover - nur bei defekter Quelldatei
        raise CodezeilenFehler(f"Die Quelldatei {datei} laesst sich nicht parsen: {fehler}") from (
            fehler
        )

    gefunden: dict[str, ast.FunctionDef] = {}
    for knoten in baum.body:
        if not isinstance(knoten, ast.FunctionDef):
            continue
        if knoten.name in gefunden:
            raise CodezeilenFehler(
                f"{datei}: Der Funktionsname {knoten.name!r} kommt auf Modulebene mehrfach "
                "vor. Die Zuordnung Funktion auf Regel waere dann nicht eindeutig."
            )
        gefunden[knoten.name] = knoten
    return gefunden


def _ist_docstring(anweisung: ast.stmt) -> bool:
    """Gibt zurueck, ob eine Anweisung der Docstring ihres Rumpfes ist."""
    return (
        isinstance(anweisung, ast.Expr)
        and isinstance(anweisung.value, ast.Constant)
        and isinstance(anweisung.value.value, str)
    )


def _rumpfzeilen(knoten: ast.FunctionDef) -> int:
    """Zaehlt die Anweisungszeilen eines Funktionsrumpfes ohne Docstring.

    Args:
        knoten: Knoten der Funktionsdefinition.

    Returns:
        Die Zahl der Zeilen. Eine Funktion, die nur aus einem Docstring besteht,
        hat null Zeilen — das ist ein zulaessiges Messergebnis und keine Stoerung.
    """
    rumpf = list(knoten.body)
    if rumpf and _ist_docstring(rumpf[0]):
        rumpf = rumpf[1:]
    return sum(
        (anweisung.end_lineno if anweisung.end_lineno is not None else anweisung.lineno)
        - anweisung.lineno
        + 1
        for anweisung in rumpf
    )


def codezeilen_der_funktion(datei: Path, name: str) -> int:
    """Misst die Anweisungszeilen einer einzelnen Funktion.

    Args:
        datei: Quelldatei, in der die Funktion steht.
        name: Name der Funktion, zum Beispiel ``"pruefe_r014"``.

    Returns:
        Die Zahl der Anweisungszeilen des Rumpfes ohne Docstring.

    Raises:
        CodezeilenFehler: Wenn die Datei oder die Funktion nicht gefunden wird.
    """
    gefunden = _funktionen(datei)
    knoten = gefunden.get(name)
    if knoten is None:
        raise CodezeilenFehler(
            f"{datei} enthaelt keine Funktion {name!r}. Vorhanden sind: {sorted(gefunden)}"
        )
    return _rumpfzeilen(knoten)


def codezeilen_je_regel(datei: Path, muster: str) -> Mapping[str, int]:
    """Misst die Anweisungszeilen aller Regelfunktionen einer Quelldatei.

    Der Regulaerausdruck muss **genau eine** Gruppe enthalten; sie liefert die
    dreistellige Nummer der Regel. Daraus entsteht die Kennung ``R-0xx``. Die
    Kopplung ueber ein Namensmuster ist Absicht: Sie zwingt beide Seiten des
    Vergleichs zu derselben Namenskonvention und macht die Zuordnung
    Funktion auf Regel nachpruefbar, statt sie in einer Tabelle zu pflegen, die
    veralten kann.

    Args:
        datei: Quelldatei mit den Regelfunktionen.
        muster: Namensmuster mit einer Gruppe, zum Beispiel
            :data:`MUSTER_PROTOTYP`.

    Returns:
        Eine nach Regelkennung sortierte Abbildung Regelkennung auf Zeilenzahl.
        Die Sortierung ist Teil der Reproduzierbarkeit (Architekturregel A2).

    Raises:
        CodezeilenFehler: Wenn das Muster nicht genau eine Gruppe hat, sich nicht
            uebersetzen laesst, keine Funktion trifft oder zwei Funktionen auf
            dieselbe Regelkennung fuehren.
    """
    try:
        uebersetzt = re.compile(muster)
    except re.error as fehler:
        raise CodezeilenFehler(f"Das Namensmuster {muster!r} ist ungueltig: {fehler}") from fehler
    if uebersetzt.groups != 1:
        raise CodezeilenFehler(
            f"Das Namensmuster {muster!r} braucht genau eine Gruppe fuer die Regelnummer, "
            f"hat aber {uebersetzt.groups}."
        )

    ergebnis: dict[str, int] = {}
    for name, knoten in _funktionen(datei).items():
        treffer = uebersetzt.match(name)
        if treffer is None:
            continue
        regel_id = f"R-{treffer.group(1)}"
        if regel_id in ergebnis:
            raise CodezeilenFehler(
                f"{datei}: Zwei Funktionen fuehren auf die Regel {regel_id}. "
                "Je Regel ist genau eine Funktion vorgesehen."
            )
        ergebnis[regel_id] = _rumpfzeilen(knoten)

    if not ergebnis:
        raise CodezeilenFehler(
            f"{datei} enthaelt keine Funktion, die auf das Muster {muster!r} passt. "
            "Ohne Treffer waere die Aufwandskennzahl leer statt null."
        )
    return dict(sorted(ergebnis.items()))
