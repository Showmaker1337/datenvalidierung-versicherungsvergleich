# t3_regeldiagnose

> Von 58 Regeln des Katalogs haben 4 in keinem Lauf gemeldet. Sie bleiben in der Tabelle, und ihr Grund steht in der Spalte `grund_ohne_treffer` — die beiden moeglichen Gruende sind **zwei verschiedene Aussagen**.
>
> **Ueberdeckung (4): ['R-030', 'R-047', 'R-048', 'R-049']** — keine Injektionsvariante zielt darauf, ihre Felder wurden in der Serie aber verfaelscht, ohne die Bedingung zu verletzen. Der Katalog deckt mehr ab, als die Fehlertaxonomie adressiert. Das ist ein Ergebnis.
>
> **In diesem Aufbau nicht pruefbar (0): []** — die Felder dieser Regeln werden von keiner Injektion getroffen. Ueber sie sagt die Serie nichts. Das ist eine Limitation.

| regel_id | gruppe | entitaet | laeufe_mit_meldung | meldungen_gesamt | treffer_gesamt | precision | anteil_einzige_regel | ohne_treffer | zielt_eine_variante_darauf | felder_wurden_verfaelscht | grund_ohne_treffer |
|---|---|---|---|---|---|---|---|---|---|---|---|
| R-001 | R-0 | anfrage, person | 180 | 307001 | 199556 | 0,6500 | 0,4599 | nein | ja | nein |  |
| R-002 | R-0 | person | 180 | 39613 | 39613 | 1,0000 | 0,0000 | nein | ja | ja |  |
| R-003 | R-0 | zahlung | 180 | 30288 | 30288 | 1,0000 | 0,0050 | nein | ja | ja |  |
| R-004 | R-0 | zahlung | 180 | 44102 | 44102 | 1,0000 | 0,2366 | nein | ja | ja |  |
| R-005 | R-0 | zahlung | 180 | 25552 | 25552 | 1,0000 | 0,4577 | nein | ja | ja |  |
| R-006 | R-0 | person | 180 | 34269 | 34269 | 1,0000 | 0,4589 | nein | ja | ja |  |
| R-007 | R-0 | risiko_kfz | 180 | 21254 | 21254 | 1,0000 | 0,0000 | nein | ja | ja |  |
| R-008 | R-0 | risiko_kfz | 180 | 21033 | 21033 | 1,0000 | 0,0000 | nein | ja | ja |  |
| R-009 | R-0 | alle | 180 | 401247 | 401247 | 1,0000 | 0,7808 | nein | ja | ja |  |
| R-010 | R-0 | anfrage | 180 | 53473 | 53473 | 1,0000 | 0,5182 | nein | ja | ja |  |
| R-011 | R-0 | anfrage, tarif | 100 | 16806 | 16806 | 1,0000 | 0,0000 | nein | ja | nein |  |
| R-012 | R-0 | anfrage | 100 | 16357 | 16357 | 1,0000 | 0,0000 | nein | nein | ja |  |
| R-013 | R-0 | risiko_kfz | 180 | 32770 | 32770 | 1,0000 | 0,4774 | nein | ja | ja |  |
| R-014 | R-0 | risiko_kfz | 180 | 66236 | 66236 | 1,0000 | 0,0006 | nein | ja | ja |  |
| R-015 | R-0 | risiko_kfz | 180 | 64470 | 64470 | 1,0000 | 0,0004 | nein | ja | ja |  |
| R-016 | R-0 | risiko_hausrat | 180 | 9267 | 9267 | 1,0000 | 0,5048 | nein | ja | ja |  |
| R-017 | R-0 | risiko_hausrat | 180 | 11711 | 11711 | 1,0000 | 0,4895 | nein | ja | ja |  |
| R-018 | R-0 | anfrage | 100 | 16380 | 16380 | 1,0000 | 0,0000 | nein | nein | ja |  |
| R-019 | R-0 | risiko_kfz | 100 | 11455 | 11455 | 1,0000 | 0,0000 | nein | nein | ja |  |
| R-020 | R-0 | risiko_kfz | 100 | 11376 | 11376 | 1,0000 | 0,0000 | nein | nein | ja |  |
| R-021 | R-0 | angebot, risiko_hausrat, tarif | 100 | 223000 | 223000 | 1,0000 | 0,0020 | nein | ja | nein |  |
| R-022 | R-0 | risiko_hausrat | 180 | 23394 | 23394 | 1,0000 | 0,3967 | nein | ja | ja |  |
| R-023 | R-0 | risiko_hausrat | 180 | 12938 | 12938 | 1,0000 | 0,4675 | nein | ja | ja |  |
| R-024 | R-0 | tarif | 77 | 815 | 815 | 1,0000 | 0,2054 | nein | ja | ja |  |
| R-025 | R-0 | alle | 104 | 1162727 | 1162727 | 1,0000 | 0,4963 | nein | ja | nein |  |
| R-026 | R-0 | risiko_kfz | 100 | 24380 | 24380 | 1,0000 | 0,0000 | nein | ja | ja |  |
| R-027 | R-0 | risiko_kfz | 180 | 59260 | 29630 | 0,5000 | 0,0000 | nein | nein | ja |  |
| R-028 | R-0 | person | 100 | 13702 | 6957 | 0,5077 | 0,0000 | nein | nein | ja |  |
| R-029 | R-0 | risiko_kfz, person | 100 | 12558 | 12558 | 1,0000 | 1,0000 | nein | ja | nein |  |
| R-030 | R-0 | risiko_kfz | 0 | 0 | 0 | — | — | ja | nein | ja | Ueberdeckung: Keine Injektionsvariante zielt auf diese Regel, ihre Felder wurden in der Serie aber verfaelscht — ohne ihre Bedingung zu verletzen. Der Katalog deckt mehr ab, als die Fehlertaxonomie adressiert. |
| R-031 | R-0 | angebot | 260 | 2021052 | 828086 | 0,4097 | 0,2157 | nein | ja | ja |  |
| R-032 | R-0 | angebot | 340 | 2164059 | 788474 | 0,3643 | 0,2386 | nein | ja | ja |  |
| R-033 | R-0 | angebot, anfrage | 180 | 193012 | 193012 | 1,0000 | 0,0041 | nein | ja | nein |  |
| R-034 | R-0 | angebot, anfrage | 100 | 93773 | 1589 | 0,0169 | 0,0200 | nein | nein | nein |  |
| R-035 | R-0 | angebot, anfrage | 180 | 66734 | 66734 | 1,0000 | 0,5112 | nein | ja | nein |  |
| R-036 | R-0 | angebot, anfrage | 100 | 84656 | 42328 | 0,5000 | 0,0000 | nein | nein | nein |  |
| R-037 | R-0 | angebot | 100 | 22540 | 3220 | 0,1429 | 0,0000 | nein | nein | ja |  |
| R-038 | R-0 | risiko_kfz | 180 | 59070 | 29535 | 0,5000 | 0,4754 | nein | ja | ja |  |
| R-039 | R-0 | risiko_kfz | 180 | 19314 | 9657 | 0,5000 | 0,7470 | nein | ja | ja |  |
| R-040 | R-0 | risiko_hausrat | 177 | 22656 | 8060 | 0,3558 | 0,0000 | nein | nein | ja |  |
| R-041 | R-0 | angebot, anfrage | 100 | 115428 | 57714 | 0,5000 | 1,0000 | nein | nein | nein |  |
| R-042 | R-0 | risiko_hausrat | 260 | 49987 | 20639 | 0,4129 | 0,6844 | nein | ja | ja |  |
| R-043 | R-0 | angebot | 180 | 662319 | 248309 | 0,3749 | 0,4449 | nein | ja | ja |  |
| R-044 | R-0 | angebot | 180 | 566278 | 74271 | 0,1312 | 0,0026 | nein | nein | ja |  |
| R-045 | R-0 | angebot | 100 | 1022220 | 0 | 0,0000 | 0,0000 | nein | ja | ja |  |
| R-046 | R-0 | person, anfrage | 120 | 42749 | 0 | 0,0000 | 0,0000 | nein | ja | nein |  |
| R-047 | R-0 | angebot | 0 | 0 | 0 | — | — | ja | nein | ja | Ueberdeckung: Keine Injektionsvariante zielt auf diese Regel, ihre Felder wurden in der Serie aber verfaelscht — ohne ihre Bedingung zu verletzen. Der Katalog deckt mehr ab, als die Fehlertaxonomie adressiert. |
| R-048 | R-0 | risiko_hausrat | 0 | 0 | 0 | — | — | ja | nein | ja | Ueberdeckung: Keine Injektionsvariante zielt auf diese Regel, ihre Felder wurden in der Serie aber verfaelscht — ohne ihre Bedingung zu verletzen. Der Katalog deckt mehr ab, als die Fehlertaxonomie adressiert. |
| R-049 | R-0 | alle | 0 | 0 | 0 | — | — | ja | nein | ja | Ueberdeckung: Keine Injektionsvariante zielt auf diese Regel, ihre Felder wurden in der Serie aber verfaelscht — ohne ihre Bedingung zu verletzen. Der Katalog deckt mehr ab, als die Fehlertaxonomie adressiert. |
| R-050 | R-0 | person | 180 | 77591 | 58602 | 0,7553 | 0,0000 | nein | nein | ja |  |
| R-051 | R-0 | risiko_kfz | 260 | 315188 | 121643 | 0,3859 | 0,0000 | nein | nein | ja |  |
| R-052 | R-0 | angebot | 100 | 11854 | 8871 | 0,7484 | 0,9900 | nein | ja | ja |  |
| R-053 | R-0 | angebot, anfrage | 180 | 225219 | 221257 | 0,9824 | 0,4755 | nein | ja | nein |  |
| R-054 | R-0 | angebot | 97 | 8020 | 7808 | 0,9736 | 0,5023 | nein | ja | ja |  |
| R-055 | R-0 | angebot, tarif | 159 | 1314266 | 426780 | 0,3247 | 0,6289 | nein | ja | nein |  |
| R-056 | R-0 | tarif | 145 | 2064 | 1033 | 0,5005 | 0,5517 | nein | ja | ja |  |
| R-057 | R-0 | person, risiko_kfz, risiko_hausrat, zahlung, angebot | 100 | 249892 | 249485 | 0,9984 | 1,0000 | nein | ja | nein |  |
| R-058 | R-0 | risiko_kfz | 180 | 136019 | 74908 | 0,5507 | 0,0000 | nein | nein | ja |  |
