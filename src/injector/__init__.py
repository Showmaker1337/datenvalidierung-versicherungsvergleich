"""Fehlerinjektor — erzeugt ``df_raw_dirty`` und den Ground Truth.

Der Injektor verfaelscht die **Rohschicht** eines sauberen Datensatzes
kontrolliert und protokolliert jede einzelne Verfaelschung. Die Spezifikation
steht in ``spec/03_fehlerklassen.md``: acht Fehlerklassen und zwei
Held-out-Klassen mit zusammen sechzig Injektionsvarianten.

Er importiert **nichts** aus ``src.rules`` und nichts aus ``src.generator``
(Architekturregel A1, ``spec/03``, Abschnitt 6). Er kennt weder die Regeln noch
ihre Konstanten noch ihre Hilfsfunktionen; er verwendet auch keine Regel-IDs in
seiner Logik. Die Varianten bilden **empirische Fehlerursachen** ab —
Erfassungsfehler, Schnittstellenkonvertierung, Legacy-Migration,
Freitexteingabe —, nicht die Komplemente der Pruefbedingungen. Die Zuordnung
Variante auf Regel entsteht erst in der Auswertung.

Diese Trennung ist der Kern der methodischen Absicherung gegen den
Zirkularitaetsvorwurf und wird in der Arbeit am Importgraphen belegt
(``tests/test_architecture.py``).

Module
------

``modell``
    Variantendefinition, Kontext, Log-Schemata.
``rohwerte``
    Lesen und Schreiben einzelner Werte der Rohschicht.
``varianten``
    Die sechzig Varianten, gruppiert nach Fehlerklasse.
``auswahl``
    Adressierbares Zelluniversum, Kontingente, Mischung der Kandidaten.
``protokoll``
    Aufbau der beiden Ground-Truth-Logs.
``pipeline``
    Orchestrierung; oeffentlicher Einstiegspunkt :func:`injiziere`.
"""

from __future__ import annotations

from src.injector.modell import Fehlerklasse, Injektionsergebnis, InjektionsFehler
from src.injector.pipeline import injiziere

__all__ = ["Fehlerklasse", "InjektionsFehler", "Injektionsergebnis", "injiziere"]
