"""Kalenderarithmetik ueber ganze Jahre.

Dieses Modul liegt aus demselben Grund in ``src/common`` wie
:mod:`src.common.iban`: Der Generator braucht die Rechnung, um Untergrenzen zu
bilden (Fuehrerscheintag, 18. Geburtstag), die Regel-Engine braucht sie, um
dieselben Grenzen zu pruefen (R-023, R-028, R-029). Zwei getrennte
Implementierungen wuerden am 29. Februar auseinanderlaufen, und die Abweichung
erschiene im Clean-Baseline-Lauf als Fehlalarm, ohne dass ihre Ursache sichtbar
waere. Gemeinsame Definitionen gehoeren nach ``src/common`` — das ist genau der
Fall, den Architekturregel A1 vorsieht, und keine Verletzung.

Die Funktionen kennen keinen Zufall und keine Systemzeit. Das Bezugsdatum wird
immer uebergeben und stammt aus der Konfiguration (``stichtag``), niemals aus
``date.today()`` (Architekturregel A2).
"""

from __future__ import annotations

import datetime as dt

__all__ = ["datum_plus_jahre", "jahre_zwischen"]


def datum_plus_jahre(tag: dt.date, jahre: int) -> dt.date:
    """Addiert ganze Jahre auf ein Datum, den 29. Februar eingeschlossen.

    Am 29. Februar geborene Personen erreichen in Nichtschaltjahren den
    **1. Maerz**, nicht den 28. Februar. Diese Richtung ist wichtig, weil die
    Funktion ueberwiegend **Untergrenzen** bildet: das fruehestmoegliche
    Fuehrerscheindatum (R-028) und den 18. Geburtstag als Untergrenze der
    Zulassung auf den Versicherungsnehmer. Ein Abrunden auf den 28. Februar
    ergaebe eine um einen Tag zu fruehe Untergrenze — und damit einen Wert, den
    eine streng gerechnete Regel als Verstoss meldet.

    Args:
        tag: Ausgangsdatum.
        jahre: Zahl der zu addierenden Jahre; darf negativ sein.

    Returns:
        Das verschobene Datum.
    """
    try:
        return tag.replace(year=tag.year + jahre)
    except ValueError:
        # Nur der 29. Februar kann hier scheitern.
        return dt.date(tag.year + jahre, 3, 1)


def jahre_zwischen(frueher: dt.date, spaeter: dt.date) -> int:
    """Gibt die Zahl der vollendeten Jahre zwischen zwei Daten zurueck.

    Args:
        frueher: Fruehes Datum, zum Beispiel das Geburtsdatum.
        spaeter: Spaetes Datum, zum Beispiel der Stichtag.

    Returns:
        Die vollendeten Jahre; negativ, wenn ``spaeter`` vor ``frueher`` liegt.
    """
    jahre = spaeter.year - frueher.year
    if (spaeter.month, spaeter.day) < (frueher.month, frueher.day):
        jahre -= 1
    return jahre
