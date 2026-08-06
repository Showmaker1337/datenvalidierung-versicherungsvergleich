"""Datengenerator — erzeugt den sauberen Datensatz in beiden Schichten.

Der Generator kennt den Regelkatalog nicht und darf nicht aus ``src.rules`` oder
``src.injector`` importieren (Architekturregel A1). Er erfuellt die fachlichen
Abhaengigkeiten, weil sie in der Domaene gelten — nicht, weil eine Regel sie
prueft.

Oeffentliche Schnittstelle::

    from src.generator import erzeuge_datensatz, schreibe_datensatz
"""

from src.generator.pipeline import erzeuge_datensatz, schreibe_datensatz

__all__ = ["erzeuge_datensatz", "schreibe_datensatz"]
