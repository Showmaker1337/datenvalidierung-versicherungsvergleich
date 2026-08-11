"""Prueft Architekturregel A1 am Importgraphen.

Die Regel lautet (CLAUDE.md, Abschnitt 2)::

    src/generator/   darf NICHT aus src/rules/ oder src/injector/ importieren
    src/injector/    darf NICHT aus src/rules/ oder src/generator/ importieren
    src/rules/       darf NICHT aus src/generator/ oder src/injector/ importieren
    src/verify/      darf NICHT aus src/injector/ importieren

Geprueft wird **am Quelltext** (``ast``), nicht zur Laufzeit. Ein Laufzeitimport
wuerde nur zeigen, was zufaellig ausgefuehrt wurde; die Verletzung soll aber
schon dann auffallen, wenn sie im Quelltext steht — auch in einem Zweig, der
selten laeuft.

Geprueft wird **transitiv**. Ein Umweg ueber ein drittes Paket ist dieselbe
Abhaengigkeit, nur schwerer zu sehen.

Der Test enthaelt eine **Negativkontrolle**: Er legt dem Pruefmechanismus einen
kuenstlichen Importgraphen mit einer verbotenen Kante vor und erwartet, dass er
sie meldet. Ein Test, der nicht fehlschlagen kann, belegt nichts — und dieser
Test traegt in der Arbeit die Aussage, dass Injektor und Regelwerk unabhaengig
sind. Solange ``src/injector`` nur eine leere ``__init__.py`` enthielt, war die
A1-Pruefung **trivial gruen**: Es gab keinen Import, den sie haette finden
koennen. Seit Phase 4 prueft sie echten Code.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]

#: Verbotene Kanten des Paketgraphen, jeweils (Quelle, Ziel).
VERBOTEN: tuple[tuple[str, str], ...] = (
    ("src.generator", "src.rules"),
    ("src.generator", "src.injector"),
    ("src.injector", "src.rules"),
    ("src.injector", "src.generator"),
    ("src.rules", "src.generator"),
    ("src.rules", "src.injector"),
    ("src.verify", "src.injector"),
)


# ---------------------------------------------------------------------------
# Analyse
# ---------------------------------------------------------------------------


def sammle_pakete(wurzel: Path, oberpaket: str) -> set[str]:
    """Sammelt alle Pakete unterhalb eines Wurzelverzeichnisses.

    Args:
        wurzel: Verzeichnis, das das Oberpaket enthaelt.
        oberpaket: Name des Oberpakets, zum Beispiel ``"src"``.

    Returns:
        Die gepunkteten Namen aller Verzeichnisse mit ``__init__.py``.
    """
    basis = wurzel / oberpaket
    pakete = {oberpaket}
    for init in basis.rglob("__init__.py"):
        relativ = init.parent.relative_to(wurzel)
        pakete.add(".".join(relativ.parts))
    return pakete


def _modulname(datei: Path, wurzel: Path) -> str:
    """Bildet einen Dateipfad auf seinen gepunkteten Modulnamen ab."""
    relativ = datei.relative_to(wurzel)
    teile = list(relativ.parts)
    teile[-1] = teile[-1].removesuffix(".py")
    if teile[-1] == "__init__":
        teile.pop()
    return ".".join(teile)


def _paketpfad(datei: Path, wurzel: Path) -> str:
    """Gibt das Paket zurueck, in dem eine Datei liegt — Grundlage relativer Importe."""
    modul = _modulname(datei, wurzel)
    if datei.name == "__init__.py":
        return modul
    return modul.rpartition(".")[0]


def _zuordnen(modul: str, pakete: set[str]) -> str | None:
    """Ordnet einen Modulnamen dem laengsten passenden Paket zu."""
    teile = modul.split(".")
    for laenge in range(len(teile), 0, -1):
        kandidat = ".".join(teile[:laenge])
        if kandidat in pakete:
            return kandidat
    return None


def _importierte_module(baum: ast.Module, paketpfad: str) -> set[str]:
    """Sammelt alle importierten Modulnamen einer Datei, absolut aufgeloest."""
    module: set[str] = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            module.update(alias.name for alias in knoten.names)
        elif isinstance(knoten, ast.ImportFrom):
            if knoten.level == 0:
                basis = knoten.module or ""
            else:
                teile = paketpfad.split(".")
                if knoten.level > 1:
                    teile = teile[: -(knoten.level - 1)]
                basis = ".".join([*teile, knoten.module] if knoten.module else teile)
            if not basis:
                continue
            module.add(basis)
            # "from src import rules" importiert ebenfalls src.rules.
            module.update(f"{basis}.{alias.name}" for alias in knoten.names)
    return module


def paketgraph(wurzel: Path, oberpaket: str) -> dict[str, set[str]]:
    """Baut den gerichteten Importgraphen auf Paketebene.

    Args:
        wurzel: Verzeichnis, das das Oberpaket enthaelt.
        oberpaket: Name des Oberpakets.

    Returns:
        Eine Abbildung Paket auf die Menge der direkt importierten Pakete.
        Selbstkanten sind entfernt.
    """
    pakete = sammle_pakete(wurzel, oberpaket)
    graph: dict[str, set[str]] = {paket: set() for paket in pakete}
    for datei in sorted((wurzel / oberpaket).rglob("*.py")):
        quelle = _paketpfad(datei, wurzel)
        baum = ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))
        for modul in sorted(_importierte_module(baum, quelle)):
            ziel = _zuordnen(modul, pakete)
            if ziel is not None and ziel != quelle:
                graph[quelle].add(ziel)
    return graph


def erreichbar(graph: dict[str, set[str]], start: str) -> set[str]:
    """Bestimmt alle transitiv erreichbaren Pakete (Tiefensuche).

    Args:
        graph: Ergebnis von :func:`paketgraph`.
        start: Ausgangspaket.

    Returns:
        Alle von ``start`` aus erreichbaren Pakete, ohne ``start`` selbst.
    """
    gesehen: set[str] = set()
    stapel = sorted(graph.get(start, set()))
    while stapel:
        knoten = stapel.pop()
        if knoten in gesehen:
            continue
        gesehen.add(knoten)
        stapel.extend(sorted(graph.get(knoten, set())))
    gesehen.discard(start)
    return gesehen


def _pfad_suchen(graph: dict[str, set[str]], start: str, ziel: str) -> list[str] | None:
    """Sucht einen konkreten Importpfad, damit die Fehlermeldung brauchbar ist."""
    stapel: list[list[str]] = [[start]]
    gesehen: set[str] = set()
    while stapel:
        pfad = stapel.pop(0)
        knoten = pfad[-1]
        if knoten == ziel and len(pfad) > 1:
            return pfad
        if knoten in gesehen:
            continue
        gesehen.add(knoten)
        stapel.extend([*pfad, nachbar] for nachbar in sorted(graph.get(knoten, set())))
    return None


def verstoesse(
    graph: dict[str, set[str]], verboten: tuple[tuple[str, str], ...]
) -> list[tuple[str, str, list[str]]]:
    """Findet alle verbotenen Kanten eines Importgraphen, direkt und transitiv.

    Dies ist **der** Pruefmechanismus, auf den sich die Arbeit beruft. Er steht
    als eigene Funktion da, damit ihn sowohl die Pruefung des echten Projekts als
    auch die Negativkontrolle aufrufen koennen — sonst pruefte die
    Negativkontrolle etwas anderes als der eigentliche Test.

    Args:
        graph: Ergebnis von :func:`paketgraph`.
        verboten: Verbotene Kanten als Paare (Quelle, Ziel).

    Returns:
        Je gefundener Verletzung ein Tripel aus Quelle, Ziel und dem konkreten
        Importpfad. Eine leere Liste bedeutet: keine Verletzung.
    """
    gefunden: list[tuple[str, str, list[str]]] = []
    for quelle, ziel in verboten:
        if ziel not in erreichbar(graph, quelle):
            continue
        pfad = _pfad_suchen(graph, quelle, ziel) or [quelle, ziel]
        gefunden.append((quelle, ziel, pfad))
    return gefunden


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def graph() -> dict[str, set[str]]:
    """Der Importgraph des Projekts auf Paketebene."""
    return paketgraph(WURZEL, "src")


def test_alle_pakete_vorhanden(graph: dict[str, set[str]]) -> None:
    """Die in CLAUDE.md, Abschnitt 3, genannten Pakete existieren."""
    erwartet = {
        "src",
        "src.common",
        "src.generator",
        "src.rules",
        "src.injector",
        "src.verify",
        "src.baselines",
        "src.evaluation",
    }
    assert erwartet <= set(graph), f"Es fehlen Pakete: {sorted(erwartet - set(graph))}"


@pytest.mark.parametrize(("quelle", "ziel"), VERBOTEN)
def test_keine_verbotene_abhaengigkeit(
    graph: dict[str, set[str]], quelle: str, ziel: str
) -> None:
    """Weder direkt noch ueber Umwege darf die verbotene Kante bestehen."""
    gefunden = verstoesse(graph, ((quelle, ziel),))
    if gefunden:
        _, _, pfad = gefunden[0]
        pytest.fail(f"Architekturregel A1 verletzt: {' -> '.join(pfad)}")


def test_injektor_und_regelwerk_sind_unabhaengig(graph: dict[str, set[str]]) -> None:
    """Die zentrale Aussage der Arbeit, an ihrem Beleg geprueft.

    Der Injektor darf den Regelkatalog nicht kennen — weder die Regeln noch ihre
    Konstanten noch ihre Hilfsfunktionen (``spec/03_fehlerklassen.md``,
    Abschnitt 6). Und der Gegencheck darf den Injektor nicht kennen, sonst prueft
    er nichts. Beides wird hier zusammen und ausdruecklich geprueft, weil genau
    diese beiden Kanten in der Arbeit zitiert werden.
    """
    kern = (
        ("src.injector", "src.rules"),
        ("src.injector", "src.generator"),
        ("src.verify", "src.injector"),
    )
    gefunden = verstoesse(graph, kern)
    assert not gefunden, "\n".join(
        f"{quelle} erreicht {ziel} ueber {' -> '.join(pfad)}"
        for quelle, ziel, pfad in gefunden
    )


def test_injektor_enthaelt_pruefbaren_code() -> None:
    """Die A1-Pruefung darf nicht deshalb gruen sein, weil sie nichts sieht.

    Solange ``src/injector`` nur eine leere ``__init__.py`` enthielt, war die
    Pruefung trivial erfuellt. Dieser Test haelt fest, dass dort inzwischen
    echter Code steht — sonst waere die Aussage des Architekturtests wertlos.
    """
    for paket, mindestdateien, mindestzeilen in (("injector", 8, 500), ("verify", 2, 200)):
        dateien = sorted((WURZEL / "src" / paket).rglob("*.py"))
        assert len(dateien) >= mindestdateien, (
            f"src/{paket} enthaelt nur {len(dateien)} Moduldateien; "
            "die Architekturpruefung haette dort nichts zu pruefen"
        )
        zeilen = sum(
            len(datei.read_text(encoding="utf-8").splitlines()) for datei in dateien
        )
        assert zeilen > mindestzeilen, f"src/{paket} enthaelt nur {zeilen} Zeilen"


def test_negativkontrolle_meldet_verbotene_kante(tmp_path: Path) -> None:
    """Der Pruefmechanismus meldet eine verbotene Kante, die es wirklich gibt.

    **Ohne diesen Test belegt der Architekturtest nichts.** Er koennte gruen
    sein, weil keine Verletzung existiert — oder weil der Mechanismus keine
    finden kann. Hier bekommt derselbe Mechanismus einen kuenstlichen Baum
    vorgelegt, in dem die verbotene Kante ausdruecklich enthalten ist, und muss
    sie melden.
    """
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").write_text("", encoding="utf-8")
    for name, inhalt in (
        ("common", ""),
        ("rules", "WERT = 1\n"),
        ("umweg", "from src.rules import WERT\n"),
        ("injector", "from src.umweg import WERT\n"),
    ):
        (tmp_path / "src" / name).mkdir()
        (tmp_path / "src" / name / "__init__.py").write_text(inhalt, encoding="utf-8")

    kuenstlich = paketgraph(tmp_path, "src")
    gefunden = verstoesse(kuenstlich, (("src.injector", "src.rules"),))

    assert gefunden, "Der Pruefmechanismus hat eine eingebaute Verletzung nicht gefunden"
    quelle, ziel, pfad = gefunden[0]
    assert (quelle, ziel) == ("src.injector", "src.rules")
    assert pfad == ["src.injector", "src.umweg", "src.rules"], (
        f"Der gemeldete Importpfad ist nicht der eingebaute: {pfad}"
    )


def test_negativkontrolle_meldet_saubere_kante_nicht(tmp_path: Path) -> None:
    """Gegenprobe zur Negativkontrolle: ohne verbotene Kante meldet der Mechanismus nichts.

    Ein Pruefmechanismus, der immer meldet, waere ebenso wertlos wie einer, der
    nie meldet.
    """
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").write_text("", encoding="utf-8")
    for name, inhalt in (
        ("common", "WERT = 1\n"),
        ("rules", "from src.common import WERT\n"),
        ("injector", "from src.common import WERT\n"),
    ):
        (tmp_path / "src" / name).mkdir()
        (tmp_path / "src" / name / "__init__.py").write_text(inhalt, encoding="utf-8")

    kuenstlich = paketgraph(tmp_path, "src")
    assert not verstoesse(kuenstlich, (("src.injector", "src.rules"),))


@pytest.mark.parametrize("paket", ["src.generator", "src.rules", "src.injector"])
def test_nur_common_wird_geteilt(graph: dict[str, set[str]], paket: str) -> None:
    """Generator, Regel-Engine und Injektor teilen ausschliesslich ``src.common``.

    CLAUDE.md, Abschnitt 2: "Alle drei Pakete duerfen aus ``src/common/``
    importieren, sonst nichts voneinander." Diese Fassung ist strenger als die
    Aufzaehlung in A1 und schliesst auch kuenftige Pakete als Umweg aus.

    Eigene Unterpakete sind kein Umweg: ``src.injector.varianten`` gehoert zum
    Injektor. Die Regel richtet sich gegen Abhaengigkeiten **zwischen** den drei
    Paketen, nicht gegen deren innere Gliederung.
    """
    erlaubt = {"src", "src.common", paket}
    fremde = sorted(
        eintrag
        for eintrag in erreichbar(graph, paket) - erlaubt
        if not eintrag.startswith(f"{paket}.")
    )
    assert not fremde, (
        f"{paket} erreicht projektinterne Pakete ausserhalb von src.common: {fremde}"
    )


def test_selbstpruefung_erkennt_transitiven_verstoss(tmp_path: Path) -> None:
    """Die Analyse findet eine Verletzung, die ueber ein drittes Paket laeuft.

    Ohne diese Pruefung bliebe der Architekturtest gruen, weil er nichts sieht —
    nicht, weil nichts da ist.
    """
    (tmp_path / "beispiel").mkdir()
    (tmp_path / "beispiel" / "__init__.py").write_text("", encoding="utf-8")
    for name, inhalt in (
        ("a", "from beispiel.b import etwas\n"),
        ("b", "from beispiel import c\n"),
        ("c", "WERT = 1\n"),
    ):
        (tmp_path / "beispiel" / name).mkdir()
        (tmp_path / "beispiel" / name / "__init__.py").write_text(inhalt, encoding="utf-8")

    gebaut = paketgraph(tmp_path, "beispiel")
    assert "beispiel.b" in gebaut["beispiel.a"], "Direkter Import wurde nicht erkannt"
    assert "beispiel.c" in gebaut["beispiel.b"], (
        "'from paket import unterpaket' wurde nicht erkannt"
    )
    assert "beispiel.c" in erreichbar(gebaut, "beispiel.a"), (
        "Transitive Abhaengigkeit wurde nicht erkannt"
    )


def test_selbstpruefung_erkennt_relativen_import(tmp_path: Path) -> None:
    """Auch relative Importe (``from ..paket import x``) landen im Graphen."""
    (tmp_path / "beispiel").mkdir()
    (tmp_path / "beispiel" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "beispiel" / "a").mkdir()
    (tmp_path / "beispiel" / "a" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "beispiel" / "a" / "modul.py").write_text(
        "from ..b import etwas\n", encoding="utf-8"
    )
    (tmp_path / "beispiel" / "b").mkdir()
    (tmp_path / "beispiel" / "b" / "__init__.py").write_text("etwas = 1\n", encoding="utf-8")

    gebaut = paketgraph(tmp_path, "beispiel")
    assert "beispiel.b" in gebaut["beispiel.a"], "Relativer Import wurde nicht erkannt"
