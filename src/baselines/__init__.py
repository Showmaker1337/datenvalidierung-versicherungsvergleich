"""Der Prototyp-Adapter und die drei Vergleichsverfahren B0, B2 und B3.

Dieses Paket enthaelt vier Adapter auf das Protokoll
:class:`src.evaluation.modell.Verfahren` und die Werkzeuge, mit denen der
Aufwandsvergleich objektiv gemessen wird. Es enthaelt **keine** Kennzahl — die
steht in ``src/evaluation`` — und **keine** eigene Fachlogik ausser der, die ein
Vergleichsverfahren ausmacht.

Nur ``prototyp`` darf den Regelkatalog kennen
---------------------------------------------

``b0_schema``, ``b2_isolation_forest`` und ``b3_framework`` importieren **nichts**
aus ``src.rules``. Sie sind die Vergleichsverfahren; ein Blick in den eigenen
Katalog waere genau der Zirkelschluss, den die Arbeit ausschliessen will —
gemessen wuerde dann nicht die Erkennungsleistung, sondern die Frage, ob dieselbe
Bedingung zweimal geschrieben wurde. ``prototyp`` ist kein Vergleich, sondern der
Gegenstand der Messung; sein Adapter ist der einzige Baustein hier, der aus
``src.rules`` importiert. Ein Test haelt die Trennung am Importgraphen fest, so
wie ``tests/test_architecture.py`` es fuer die Architekturregel A1 tut.

Ein Wort zu den Importkosten
----------------------------

Dieses Modul zieht ``pydantic``, ``scikit-learn`` und ``cuallee`` in den Prozess.
Das ist gewollt: Wer ``src.baselines`` importiert, will vergleichen, und ein
Vergleich, bei dem ein Verfahren wegen eines fehlenden Pakets stillschweigend
ausfaellt, waere kein Vergleich. Ein fehlendes Paket faellt hier sofort auf,
statt sich spaeter als leere Ergebniszeile zu tarnen.

Module
------

``prototyp``
    Adapter des eigenen Regelkatalogs.
``b0_schema``
    B0: Typ-, Nullable- und Laengenpruefung mit ``pydantic`` v2.
``b2_isolation_forest``
    B2: unueberwachte Anomalieerkennung, sieben Schwellen auf einem Fit.
``b3_framework``
    B3: die G1-Regeln in der deklarativen Check-API von ``cuallee``.
``codezeilen``
    Objektive Messung "Codezeilen je Regel" ueber den AST.
"""

from __future__ import annotations

from src.baselines.b0_schema import B0Schema
from src.baselines.b2_isolation_forest import (
    CONTAMINATION_STUFEN,
    STANDARD_CONTAMINATION,
    IsolationForestBaseline,
    Sweepstufe,
)
from src.baselines.b3_framework import B3Bericht, B3Fehler, B3Framework, B3Regel
from src.baselines.codezeilen import (
    CodezeilenFehler,
    codezeilen_der_funktion,
    codezeilen_je_regel,
)
from src.baselines.prototyp import Prototyp

__all__ = [
    "CONTAMINATION_STUFEN",
    "STANDARD_CONTAMINATION",
    "B0Schema",
    "B3Bericht",
    "B3Fehler",
    "B3Framework",
    "B3Regel",
    "CodezeilenFehler",
    "IsolationForestBaseline",
    "Prototyp",
    "Sweepstufe",
    "codezeilen_der_funktion",
    "codezeilen_je_regel",
]
