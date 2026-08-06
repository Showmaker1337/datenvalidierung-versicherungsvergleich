"""Testsuite des Prototyps.

Das Verzeichnis ist seit Phase 3 ein Paket. Grund: ``tests/test_regeln/bausteine.py``
haelt die Minimaldatensaetze, die mehrere Testmodule gemeinsam nutzen. Ohne
Paketwurzel faende mypy dieselbe Datei unter zwei Modulnamen
(``test_regeln.bausteine`` und ``tests.test_regeln.bausteine``) und braeche ab.
"""
