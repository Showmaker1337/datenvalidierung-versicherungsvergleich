"""Prueft die beiden selbst auferlegten Importregeln der Phase 5 am Quelltext.

Architekturregel A1 aus ``CLAUDE.md`` betrifft ``generator``, ``injector``,
``rules`` und ``verify``. Die beiden neuen Pakete ``evaluation`` und ``baselines``
stehen ausserhalb dieser Verbote — sie duerfen den Regelkatalog kennen, sonst
liesse sich der Prototyp gar nicht ausfuehren. Damit der Vergleich trotzdem
etwas misst, gelten zwei zusaetzliche Regeln, und die stehen hier:

1. ``src/evaluation/`` erreicht **nichts** aus ``src/injector/`` und nichts aus
   ``src/generator/``. Alles, was die Auswertung ueber Fehlerklassen und
   Varianten wissen muss, steht im ``error_log``, im ``error_log_records`` und im
   ``manifest.json`` des Laufs. Die Zuordnung Variante auf Regel entsteht laut
   ``spec/03_fehlerklassen.md``, Abschnitt 6 erst in der Auswertung; stammte sie
   aus dem Quelltext des Injektors, waere sie keine Auswertung mehr, sondern eine
   zweite Niederschrift derselben Absicht.
2. ``b0_schema.py``, ``b2_isolation_forest.py`` und ``b3_framework.py``
   importieren **nichts** aus ``src/rules/``. Sie sind die Vergleichsverfahren;
   ein Blick in den eigenen Katalog waere genau der Zirkelschluss, den die Arbeit
   ausschliessen will. Nur ``prototyp.py`` — der Adapter des eigenen Verfahrens —
   darf ``src/rules/`` importieren.

Zwei Regeln, zwei Mechanismen
-----------------------------

Regel 1 wird **transitiv auf Paketebene** geprueft und benutzt dafuer denselben
Mechanismus wie ``tests/test_architecture.py``: :func:`~tests.test_architecture.paketgraph`,
:func:`~tests.test_architecture.erreichbar` und :func:`~tests.test_architecture.verstoesse`.
Ein Umweg ueber ein drittes Paket ist dieselbe Abhaengigkeit, nur schwerer zu
sehen. Die Funktionen werden importiert und nicht abgeschrieben — zwei Kopien
desselben Pruefmechanismus geraten frueher oder spaeter auseinander, und dann
prueft die eine etwas anderes als die andere.

Regel 2 wird dagegen **nur auf direkte Importe** derselben drei Dateien geprueft,
und das ist kein Nachlassen, sondern die einzig sinnvolle Fassung. Alle drei
Module importieren :mod:`src.evaluation.modell`, weil dort das Berichtsformat
steht; und :mod:`src.evaluation.modell` re-exportiert
:class:`~src.rules.modell.Kontext` aus ``src.rules``, weil der Pruefkontext ein
reiner Datenbehaelter ueber beide Datenschichten ist und kein zweites Mal gebaut
werden soll. Transitiv erreicht damit **jedes** Baseline-Modul ``src.rules``, und
eine transitive Pruefung waere entweder immer rot oder muesste den Umweg
ausnehmen — womit sie nichts mehr pruefte. Verboten ist, was die Regel meint:
dass eine Baseline in den Regelkatalog **hineinsieht**. Genau das steht im
Quelltext als ``import`` und nirgends sonst.

Geprueft wird am Quelltext (``ast``), nicht zur Laufzeit. Ein Laufzeitimport
zeigte nur, was zufaellig ausgefuehrt wurde; die Verletzung soll schon dann
auffallen, wenn sie im Quelltext steht — auch in einem selten durchlaufenen
Zweig.

Negativkontrollen
-----------------

Beide Mechanismen bekommen einen kuenstlichen Baum mit einer **eingebauten**
verbotenen Kante vorgelegt und muessen sie melden, und je einen sauberen Baum,
bei dem sie schweigen muessen. Ein Test, der nicht fehlschlagen kann, belegt
nichts — und diese beiden Aussagen werden in der Arbeit zitiert.

Dazu kommt eine Kontrolle am echten Projekt: ``prototyp.py`` liegt im selben
Verzeichnis wie die drei Vergleichsverfahren und importiert ``src.rules``
tatsaechlich. Findet der Mechanismus diesen Import, dann kann er Importe dieser
Art im echten Baum sehen — und sein Schweigen bei den drei anderen Dateien ist
eine Aussage ueber die Dateien, nicht ueber den Mechanismus.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Final

import pytest

from tests.test_architecture import (
    WURZEL,
    _importierte_module,
    _paketpfad,
    erreichbar,
    paketgraph,
    verstoesse,
)

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from pathlib import Path

#: Verzeichnis der Vergleichsverfahren.
BASELINES = WURZEL / "src" / "baselines"

#: Die drei Vergleichsverfahren, die den Regelkatalog nicht kennen duerfen.
VERGLEICHSVERFAHREN: Final[tuple[str, ...]] = (
    "b0_schema.py",
    "b2_isolation_forest.py",
    "b3_framework.py",
)

#: Das Paket, das den drei Vergleichsverfahren verschlossen ist.
VERSCHLOSSEN: Final[str] = "src.rules"

#: Verbotene Kanten des Auswertungspakets, jeweils (Quelle, Ziel).
VERBOTEN_EVALUATION: Final[tuple[tuple[str, str], ...]] = (
    ("src.evaluation", "src.generator"),
    ("src.evaluation", "src.injector"),
)

#: Projektinterne Pakete, die ``src.evaluation`` erreichen darf.
ERLAUBT_EVALUATION: Final[frozenset[str]] = frozenset(
    {"src", "src.common", "src.evaluation", "src.rules"}
)


# ---------------------------------------------------------------------------
# Der Pruefmechanismus fuer direkte Importe einer einzelnen Datei
# ---------------------------------------------------------------------------


def direkte_importe(datei: Path, wurzel: Path) -> set[str]:
    """Sammelt die im Quelltext einer Datei unmittelbar importierten Module.

    Benutzt dieselbe Auswertung des Syntaxbaums wie
    :func:`~tests.test_architecture.paketgraph`, nur ohne den Schritt, der
    Modulnamen auf Pakete zusammenfasst — hier ist gerade die einzelne Datei die
    Einheit der Aussage.

    Args:
        datei: Zu untersuchende Quelldatei.
        wurzel: Verzeichnis, gegen das der Modulname gebildet wird.

    Returns:
        Die absolut aufgeloesten Namen aller direkt importierten Module.
    """
    baum = ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))
    return _importierte_module(baum, _paketpfad(datei, wurzel))


def fremdimporte(datei: Path, wurzel: Path, verschlossen: str) -> list[str]:
    """Findet die direkten Importe einer Datei aus einem verschlossenen Paket.

    Dies ist **der** Pruefmechanismus fuer die zweite Importregel. Er steht als
    eigene Funktion da, damit ihn sowohl die Pruefung des echten Projekts als auch
    die Negativkontrolle aufrufen koennen — sonst pruefte die Negativkontrolle
    etwas anderes als der eigentliche Test.

    Args:
        datei: Zu untersuchende Quelldatei.
        wurzel: Verzeichnis, gegen das der Modulname gebildet wird.
        verschlossen: Gepunkteter Name des verbotenen Pakets, etwa ``"src.rules"``.

    Returns:
        Die gefundenen Importe, sortiert. Eine leere Liste bedeutet: keine
        Verletzung.
    """
    return sorted(
        modul
        for modul in direkte_importe(datei, wurzel)
        if modul == verschlossen or modul.startswith(f"{verschlossen}.")
    )


def _schreibe_baum(wurzel: Path, dateien: dict[str, str]) -> None:
    """Legt einen kuenstlichen Quelltextbaum an.

    Args:
        wurzel: Verzeichnis, unter dem der Baum entsteht.
        dateien: Pfad relativ zu ``wurzel`` auf Dateiinhalt. Fehlende
            Zwischenverzeichnisse werden angelegt.
    """
    for pfad, inhalt in dateien.items():
        ziel = wurzel / pfad
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(inhalt, encoding="utf-8")


# ---------------------------------------------------------------------------
# Regel 2: die drei Vergleichsverfahren kennen den Regelkatalog nicht
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dateiname", VERGLEICHSVERFAHREN)
def test_vergleichsverfahren_kennt_den_regelkatalog_nicht(dateiname: str) -> None:
    """Kein Vergleichsverfahren importiert etwas aus ``src.rules``.

    Das ist die Bedingung, unter der der Vergleich ueberhaupt etwas misst: Sieht
    eine Baseline in den Katalog, misst das Experiment nicht mehr ihre
    Erkennungsleistung, sondern nur noch, ob dieselbe Bedingung zweimal
    geschrieben wurde.
    """
    gefunden = fremdimporte(BASELINES / dateiname, WURZEL, VERSCHLOSSEN)
    assert not gefunden, (
        f"src/baselines/{dateiname} importiert aus dem Regelkatalog: {gefunden}. "
        "Nur src/baselines/prototyp.py darf das."
    )


def test_prototyp_importiert_den_regelkatalog() -> None:
    """Kontrolle am echten Baum: Der Adapter des eigenen Verfahrens sieht hinein.

    Ohne diesen Test bliebe offen, ob das Schweigen bei den drei
    Vergleichsverfahren eine Aussage ueber die Dateien ist oder ueber einen
    Mechanismus, der im echten Projekt gar nichts findet. ``prototyp.py`` liegt
    im selben Verzeichnis, ist nach Abschnitt 1 des Kontrakts ausdruecklich
    erlaubt — und wird gefunden.
    """
    gefunden = fremdimporte(BASELINES / "prototyp.py", WURZEL, VERSCHLOSSEN)
    assert gefunden, (
        "Der Pruefmechanismus findet im Prototyp-Adapter keinen Import aus "
        "src.rules. Dann ist auch sein Schweigen bei B0, B2 und B3 wertlos."
    )


def test_vergleichsverfahren_enthalten_pruefbaren_code() -> None:
    """Die Importpruefung darf nicht gruen sein, weil sie nichts sieht.

    Eine leere oder fast leere Datei erfuellt jede Importregel. Dieser Test haelt
    fest, dass in allen drei Vergleichsverfahren echter Code steht — sonst waere
    die Aussage des Unabhaengigkeitstests wertlos, so wie die A1-Pruefung wertlos
    war, solange ``src/injector`` nur eine leere ``__init__.py`` enthielt.
    """
    mindestzeilen = 200
    for dateiname in VERGLEICHSVERFAHREN:
        zeilen = len((BASELINES / dateiname).read_text(encoding="utf-8").splitlines())
        assert zeilen > mindestzeilen, (
            f"src/baselines/{dateiname} enthaelt nur {zeilen} Zeilen; "
            "die Unabhaengigkeitspruefung haette dort nichts zu pruefen"
        )


def test_negativkontrolle_meldet_verbotenen_direktimport(tmp_path: Path) -> None:
    """Der Mechanismus meldet einen Katalogimport, den es wirklich gibt.

    **Ohne diesen Test belegt die Importpruefung nichts.** Sie koennte gruen sein,
    weil keine Verletzung existiert — oder weil der Mechanismus keine finden kann.
    Hier bekommt dieselbe Funktion eine Datei vorgelegt, in der der verbotene
    Import ausdruecklich steht, und muss ihn melden.
    """
    _schreibe_baum(
        tmp_path,
        {
            "src/__init__.py": "",
            "src/rules/__init__.py": "",
            "src/rules/katalog.py": "def regel(kennung: str) -> str:\n    return kennung\n",
            "src/baselines/__init__.py": "",
            "src/baselines/b0_schema.py": "from src.rules.katalog import regel\n",
        },
    )

    gefunden = fremdimporte(tmp_path / "src" / "baselines" / "b0_schema.py", tmp_path, VERSCHLOSSEN)

    assert gefunden, "Der Pruefmechanismus hat einen eingebauten Katalogimport nicht gefunden"
    assert "src.rules.katalog" in gefunden, (
        f"Der gemeldete Import ist nicht der eingebaute: {gefunden}"
    )


def test_negativkontrolle_meldet_erlaubten_direktimport_nicht(tmp_path: Path) -> None:
    """Gegenprobe: Ein erlaubter Import wird nicht gemeldet.

    Ein Pruefmechanismus, der immer meldet, waere ebenso wertlos wie einer, der
    nie meldet. Der Import aus ``src.common`` steht in allen drei
    Vergleichsverfahren und muss folgenlos bleiben.
    """
    _schreibe_baum(
        tmp_path,
        {
            "src/__init__.py": "",
            "src/common/__init__.py": "",
            "src/common/serialisierung.py": "ENTITAETEN = ('person',)\n",
            "src/baselines/__init__.py": "",
            "src/baselines/b0_schema.py": (
                "from src.common.serialisierung import ENTITAETEN\n"
                "from ..common import serialisierung\n"
            ),
        },
    )

    gefunden = fremdimporte(tmp_path / "src" / "baselines" / "b0_schema.py", tmp_path, VERSCHLOSSEN)

    assert not gefunden, f"Der Pruefmechanismus meldet einen erlaubten Import: {gefunden}"


# ---------------------------------------------------------------------------
# Regel 1: die Auswertung kennt weder Injektor noch Generator
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def graph() -> dict[str, set[str]]:
    """Der Importgraph des Projekts auf Paketebene."""
    return paketgraph(WURZEL, "src")


@pytest.mark.parametrize(("quelle", "ziel"), VERBOTEN_EVALUATION)
def test_auswertung_erreicht_weder_injektor_noch_generator(
    graph: dict[str, set[str]], quelle: str, ziel: str
) -> None:
    """Weder direkt noch ueber Umwege darf die Auswertung diese Pakete erreichen.

    Wuesste die Auswertung, wie der Injektor verfaelscht, waere die Zuordnung
    Variante auf Regel keine Auswertung mehr, sondern eine Abschrift der
    Injektionsabsicht — und der gemessene Recall keine Messung.
    """
    gefunden = verstoesse(graph, ((quelle, ziel),))
    if gefunden:
        _, _, pfad = gefunden[0]
        pytest.fail(f"Importregel der Phase 5 verletzt: {' -> '.join(pfad)}")


def test_auswertung_teilt_nur_common_und_regelkatalog(graph: dict[str, set[str]]) -> None:
    """Schaerfere Fassung: ``src.evaluation`` erreicht genau zwei fremde Pakete.

    ``src.common`` fuer Schema, Pfade und Konfiguration, ``src.rules`` fuer den
    Pruefkontext und das Berichtsformat. Diese Aufzaehlung schliesst auch kuenftige
    Pakete als Umweg aus, waehrend die Kantenliste
    :data:`VERBOTEN_EVALUATION` nur die beiden heute bekannten Ziele nennt.
    """
    fremde = sorted(
        eintrag
        for eintrag in erreichbar(graph, "src.evaluation")
        if eintrag not in ERLAUBT_EVALUATION and not eintrag.startswith("src.evaluation.")
    )
    assert not fremde, f"src.evaluation erreicht unerwartete Pakete: {fremde}"


def test_negativkontrolle_meldet_verbotene_auswertungskante(tmp_path: Path) -> None:
    """Der Paketmechanismus meldet eine Kante Auswertung auf Injektor.

    Gebaut wird der Umweg ueber ein drittes Paket: Genau so entstuende die
    Abhaengigkeit im Ernstfall — niemand schreibt ``from src.injector import ...``
    in ein Auswertungsmodul, aber ein Hilfsmodul, das beide kennt, ist schnell
    geschrieben.
    """
    _schreibe_baum(
        tmp_path,
        {
            "src/__init__.py": "",
            "src/common/__init__.py": "WERT = 1\n",
            "src/injector/__init__.py": "VARIANTEN = ()\n",
            "src/umweg/__init__.py": "from src.injector import VARIANTEN\n",
            "src/evaluation/__init__.py": "from src.umweg import VARIANTEN\n",
        },
    )

    kuenstlich = paketgraph(tmp_path, "src")
    gefunden = verstoesse(kuenstlich, (("src.evaluation", "src.injector"),))

    assert gefunden, "Der Pruefmechanismus hat eine eingebaute Verletzung nicht gefunden"
    quelle, ziel, pfad = gefunden[0]
    assert (quelle, ziel) == ("src.evaluation", "src.injector")
    assert pfad == ["src.evaluation", "src.umweg", "src.injector"], (
        f"Der gemeldete Importpfad ist nicht der eingebaute: {pfad}"
    )


def test_negativkontrolle_meldet_saubere_auswertungskante_nicht(tmp_path: Path) -> None:
    """Gegenprobe: Ohne verbotene Kante meldet der Paketmechanismus nichts."""
    _schreibe_baum(
        tmp_path,
        {
            "src/__init__.py": "",
            "src/common/__init__.py": "WERT = 1\n",
            "src/injector/__init__.py": "from src.common import WERT\n",
            "src/evaluation/__init__.py": "from src.common import WERT\n",
        },
    )

    kuenstlich = paketgraph(tmp_path, "src")

    assert not verstoesse(kuenstlich, (("src.evaluation", "src.injector"),))
