"""Regelkatalog und Regelausfuehrung.

58 Regeln, gruppiert nach Pruefgranularitaet (``spec/02_regelkatalog.md``):
``g1_attribut`` R-001 bis R-025, ``g2_satz`` R-026 bis R-042, ``g3_relation``
R-043 bis R-048, ``g4_relationen`` R-049 bis R-051, ``g5_quellen`` R-052 bis
R-058. ``katalog`` fuegt sie zusammen und prueft die Zusammenstellung beim
Import, ``engine`` fuehrt sie aus.

Dieses Paket importiert **nichts** aus ``src.generator`` oder ``src.injector``
(Architekturregel A1). Gemeinsame Definitionen kommen ausschliesslich aus
``src.common``.
"""
