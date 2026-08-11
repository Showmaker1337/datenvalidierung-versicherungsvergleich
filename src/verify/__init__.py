"""Unabhaengiger Gegencheck des Ground Truth.

Dieses Paket importiert **nichts** aus ``src.injector`` — sonst prueft es nichts
(Architekturregel A1, ``spec/03_fehlerklassen.md``, Abschnitt 5,
Protokollregel 4). Ein Gegencheck, der die Logik des Geprueften teilt,
bestaetigt nur, dass diese Logik mit sich selbst uebereinstimmt.

``diff_check``
    Zellweises Diff zwischen ``df_clean`` und ``df_dirty`` ueber ``row_id``,
    abgeglichen gegen ``error_log`` und ``error_log_records``.
"""

from __future__ import annotations

from src.verify.diff_check import (
    Gegencheckfehler,
    GroundTruthBericht,
    pruefe_ground_truth,
    schreibe_bericht,
)

__all__ = [
    "Gegencheckfehler",
    "GroundTruthBericht",
    "pruefe_ground_truth",
    "schreibe_bericht",
]
