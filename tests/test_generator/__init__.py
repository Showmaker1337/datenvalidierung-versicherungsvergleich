"""Tests des Datengenerators.

Dieses Verzeichnis ist das einzige Testpaket mit ``__init__.py``. Grund ist die
zweite ``conftest.py``: Ohne Paketkennzeichnung traegt sie denselben Modulnamen
wie ``tests/conftest.py``, und die Typpruefung bricht mit "Duplicate module named
conftest" ab, bevor sie irgendetwas prueft.
"""
