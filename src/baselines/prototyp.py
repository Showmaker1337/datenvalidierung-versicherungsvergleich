"""Adapter des eigenen Regelkatalogs auf das Verfahren-Protokoll.

Dieses Modul uebersetzt das Ergebnis von :func:`src.rules.engine.pruefe_alles` in
die Form, die :class:`src.evaluation.modell.Verfahren` erwartet. Es enthaelt
selbst **keine** Pruefbedingung und **keine** Kennzahl. Alles Fachliche steht im
Katalog, alles Metrische in ``src/evaluation`` — hier liegt nur die Uebersetzung
dazwischen.

Das einzige Baseline-Modul mit Zugriff auf ``src.rules``
--------------------------------------------------------

B0 (``pydantic``), B2 (``IsolationForest``) und B3 (``cuallee``) duerfen den
Regelkatalog nicht kennen. Sie sind die Vergleichsverfahren; ein Blick in den
eigenen Katalog waere genau der Zirkelschluss, den die Arbeit ausschliessen will —
gemessen wuerde dann nicht mehr die Erkennungsleistung, sondern die Frage, ob
dieselbe Bedingung zweimal geschrieben wurde. Der Prototyp ist kein Vergleich,
sondern der Gegenstand der Messung. Sein Adapter ist deshalb der einzige Baustein
in ``src/baselines/``, der aus ``src.rules`` importiert; ein Test haelt diese
Trennung am Importgraphen fest, so wie ``tests/test_architecture.py`` es fuer die
Architekturregel A1 tut.

R-047 und R-048 verlassen den Zellkanal, nicht die Auswertung
-------------------------------------------------------------

:attr:`src.rules.engine.Detektionen.verstoesse` ist die **Diagnosesicht**: jede
Zellmeldung jeder Regel, ungefiltert. Die Engine wendet ``in_zellmetrik`` nur auf
ihre Vereinigungsmenge ``markierte_zellen`` an, nicht auf ``verstoesse``. Wer den
Rohtrefferrahmen unbesehen als Meldungsmenge nimmt, bekommt die Zellmetrik der
Engine also nicht.

Betroffen sind R-047 und R-048. R-047 meldet eine extreme Beitragsspreizung
innerhalb einer Anfrage, weiss aber nicht, welches der n Angebote das falsche
ist; R-048 prueft die Verteilung von ``zuers_zone`` ueber den Gesamtdatensatz und
hat ueberhaupt keine verursachende Zelle (``src/rules/g3_relation.py``,
Kopfabschnitt). Der Adapter filtert ihre Meldungen deshalb ueber
``src.rules.katalog.regel(regel_id).in_zellmetrik`` aus :meth:`Prototyp.erkenne`
heraus — **dieselbe** Bedingung, mit der die Engine ihre ``markierte_zellen``
bildet. Ohne diese Wiederholung waere die Zellmetrik der Auswertung eine andere
als die der Engine, und zwar still. Fuer die Kennzahlen haette das eine klare
Richtung: Beide Regeln markierten alle Angebotszeilen einer Anfrage
beziehungsweise alle Zeilen einer Zonenauspraegung, ohne dass ein einziger
Detektionsfehler belegt waere. Die Precision fiele, die Fehlalarmrate stiege — als
Artefakt der Berichtskonvention, nicht des Detektors.

**Stand des eingefrorenen Katalogs.** Beide Regeln benutzen heute ausschliesslich
``Befundsammler.melde_satz`` und fuellen den Zellkanal gar nicht; der Filter
entfernt in der Praxis also nichts. Er bleibt trotzdem stehen, und zwar als
Zusicherung an der Modulgrenze: Die Aussage "``erkenne`` liefert genau die
zellmetrischen Meldungen" darf nicht davon abhaengen, welche Kanaele eine Regel
innen benutzt. Sobald eine Regel ausserhalb der Zellmetrik zusaetzlich Zellen
benennt — R-047 koennte das mit einer Heuristik ueber den Ausreisser —, greift der
Filter, ohne dass der Adapter angefasst werden muss. Der Katalog ist eingefroren
(Architekturregel A4), die Zusicherung darf es auch sein.

Ihre **Satzbefunde** bleiben dagegen stehen. :meth:`Prototyp.satzmeldungen` gibt
den Satzkanal ungefiltert zurueck, denn dort ist die Einheit
``(entitaet, row_id)``, und genau diese Menge benennen beide Regeln korrekt: die
Zeilen der auffaelligen Anfrage, die Zeilen der auffaelligen Zone. Eine Meldung,
die auf einer Ebene nicht zuordenbar ist, ist auf der naechstgroeberen sehr wohl
auswertbar — sie zu verwerfen, statt sie umzuhaengen, waere ein
Informationsverlust ohne Gegenwert.

Gefiltert wird ``verstoesse``, statt ``markierte_zellen`` zu uebernehmen
------------------------------------------------------------------------

Die Engine liefert die Vereinigungsmenge der Tripel bereits fertig. Sie ist hier
trotzdem nicht brauchbar: ``markierte_zellen`` traegt nur
``(entitaet, row_id, spalte)`` und hat ``regel_id`` und ``verstoss_id`` unterwegs
verloren — ohne die erste gibt es keine Regeldiagnose und keine Kreuztabelle, ohne
die zweite keine Constraint-Ebene. Der Adapter gibt deshalb die **Rohtreffer** der
zellmetrischen Regeln zurueck und ueberlaesst die Vereinigung der Auswertung. Dort
gehoert sie auch hin: Sie ist fuer alle vier Verfahren dieselbe Operation und darf
nicht in vier Adaptern je einmal implementiert sein.

Ein Zwischenspeicher fuer genau einen Kontext
---------------------------------------------

:meth:`Prototyp.erkenne`, :meth:`Prototyp.satzmeldungen` und
:meth:`Prototyp.laufzeiten_je_regel` beantworten drei Fragen an **einen**
Katalogdurchlauf. Ohne Zwischenspeicher liefe der volle Katalog dreimal ueber
denselben Datensatz — bei mehreren tausend Laeufen der Phase 6 der Unterschied
zwischen Stunden und Tagen, und die gemessene Laufzeit des Verfahrens waere je
nach Aufrufreihenfolge eine andere.

Schluessel ist die **Objektidentitaet** des Kontexts (``is``), nicht sein Inhalt.
Ein inhaltlicher Vergleich zweier Kontexte hiesse, zwei vollstaendige Datensaetze
Zelle fuer Zelle zu vergleichen — teurer als der Katalogdurchlauf selbst. Ein
Hashwert scheidet ebenfalls aus: :class:`~src.rules.modell.Kontext` haelt
``Mapping``-Felder und ist damit nicht hashbar. Der Zwischenspeicher haelt den
Kontext deshalb als starke Referenz neben dem Ergebnis. Auch das ist Absicht: Nur
so kann keine freigegebene Objektadresse neu vergeben und ein fremdes Ergebnis
ausgeliefert werden. Gehalten wird immer nur **ein** Eintrag; der naechste Kontext
ersetzt ihn samt Datensatz.

Der Adapter ist damit an einen Lauf gebunden, nicht an eine Sitzung. Wer zwei
Laeufe auswerten will, ruft ihn mit zwei Kontexten auf und bekommt zwei
Ergebnisse — nur eben nie beide gleichzeitig aus dem Speicher.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

import pandas as pd

from src.evaluation.modell import SATZ_SPALTEN, VERSTOSS_SPALTEN, AuswertungsFehler
from src.rules.engine import pruefe_alles
from src.rules.katalog import regel

if TYPE_CHECKING:  # pragma: no cover - nur fuer die Typpruefung
    from collections.abc import Mapping

    from src.evaluation.modell import Kontext
    from src.rules.engine import Detektionen

__all__ = ["Prototyp"]


class Prototyp:
    """Das eigene regelbasierte Verfahren als :class:`~src.evaluation.modell.Verfahren`.

    Attributes:
        name: Kurzname in allen Ergebnistabellen.
        beschreibung: Ein Satz fuer den Anhang.
        lokalisiert_zellen: ``True`` — jede Zellmeldung nennt Entitaet, Zeile und
            Feld. Damit sind alle drei Ebenen auswertbar.
        in_inferenzstatistik: ``True`` — der Prototyp ist die Referenz, gegen die
            die Baselines in Phase 6 getestet werden.
    """

    name: str = "prototyp"
    beschreibung: str = "Regelbasierter Prototyp, 58 Regeln aus spec/02_regelkatalog.md"
    lokalisiert_zellen: bool = True
    in_inferenzstatistik: bool = True

    def __init__(self) -> None:
        """Legt den Adapter mit leerem Zwischenspeicher an."""
        self._zwischenspeicher: tuple[Kontext, Detektionen] | None = None

    def erkenne(self, kontext: Kontext) -> pd.DataFrame:
        """Meldet die vom Regelkatalog beanstandeten Zellen.

        Zurueckgegeben werden die **Rohtreffer** aller Regeln mit
        ``in_zellmetrik=True``, also eine Zeile je gemeldeter Zelle und Regel. Die
        Vereinigung mehrfach gemeldeter Zellen findet in der Auswertung statt; die
        Meldungen von R-047 und R-048 sind herausgefiltert (siehe
        Modul-Docstring).

        Args:
            kontext: Pruefkontext ueber beide Datenschichten des verfaelschten
                Datensatzes.

        Returns:
            Einen Datenrahmen mit den Spalten
            :data:`~src.evaluation.modell.VERSTOSS_SPALTEN`, in
            Katalogreihenfolge.
        """
        verstoesse = self._detektionen(kontext).verstoesse
        if verstoesse.empty:
            return pd.DataFrame(columns=list(VERSTOSS_SPALTEN))

        # ``unique`` haelt die Reihenfolge des ersten Auftretens fest; eine Menge
        # waere hier eine ungeordnete Iteration und damit ein A2-Risiko.
        zellmetrisch = [
            str(kennung)
            for kennung in verstoesse["regel_id"].unique()
            if regel(str(kennung)).in_zellmetrik
        ]
        gefiltert = verstoesse[verstoesse["regel_id"].isin(zellmetrisch)]
        return gefiltert.reset_index(drop=True)

    def satzmeldungen(self, kontext: Kontext) -> pd.DataFrame:
        """Meldet die satzbezogenen Befunde des Regelkatalogs.

        Der Kanal bleibt **ungefiltert**: Auch R-047 und R-048 nennen hier eine
        wohldefinierte Zeilenmenge, obwohl sie keine verursachende Zelle benennen
        koennen.

        Args:
            kontext: Pruefkontext ueber beide Datenschichten.

        Returns:
            Einen Datenrahmen mit den Spalten
            :data:`~src.evaluation.modell.SATZ_SPALTEN`.
        """
        saetze = self._detektionen(kontext).saetze
        if saetze.empty:
            return pd.DataFrame(columns=list(SATZ_SPALTEN))
        return saetze.reset_index(drop=True)

    def laufzeiten_je_regel(self) -> Mapping[str, float]:
        """Gibt die Laufzeit je Regel des zuletzt geprueften Kontexts zurueck.

        Die Zahlen stammen aus der Messung der Engine (``time.perf_counter``) und
        gehen als Diagnosekennzahl in den Anhang ein: Sie zeigen, welche Regeln
        die Laufzeit des Katalogs tragen.

        Returns:
            Laufzeit in Sekunden je Regelkennung, in Katalogreihenfolge und
            schreibgeschuetzt.

        Raises:
            AuswertungsFehler: Wenn noch kein Kontext geprueft wurde. Bewusst eine
                Ausnahme statt einer leeren Abbildung: Null Sekunden je Regel
                waere eine Messung, die es nicht gibt.
        """
        if self._zwischenspeicher is None:
            raise AuswertungsFehler(
                "Fuer den Prototyp liegt noch keine Laufzeitmessung vor. Vor "
                "'laufzeiten_je_regel' muss 'erkenne' oder 'satzmeldungen' mit einem "
                "Kontext aufgerufen worden sein."
            )
        return MappingProxyType(dict(self._zwischenspeicher[1].laufzeiten))

    def _detektionen(self, kontext: Kontext) -> Detektionen:
        """Fuehrt den Katalog aus oder gibt das gespeicherte Ergebnis zurueck.

        Args:
            kontext: Pruefkontext ueber beide Datenschichten.

        Returns:
            Das Ergebnis des Katalogdurchlaufs zu genau diesem Kontextobjekt.
        """
        gespeichert = self._zwischenspeicher
        if gespeichert is not None and gespeichert[0] is kontext:
            return gespeichert[1]

        detektionen = pruefe_alles(kontext)
        self._zwischenspeicher = (kontext, detektionen)
        return detektionen
