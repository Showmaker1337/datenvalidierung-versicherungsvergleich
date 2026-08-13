# t4_varianten

> **Trefferkategorien** aus der Kreuztabelle `regel_id` gegen Variante — keine Umetikettierung, sondern eine Messung: Die Regel-ID steht im Ergebnis und wird nicht neu vergeben.
>
> - **A: erkannt durch die zugeordnete Regel**: 44
> - **B: erkannt durch eine andere Regel**: 5
> - **C: nicht erkannt**: 5
> - **S: satzbasiert, zellbasierte Zuordnung nicht definiert**: 6
>
> Kategorie B (5: ['F2-h', 'F2-i', 'F2-k', 'F3-g', 'F8-e']) ist der inhaltlich staerkste Einzelbefund: **Eine Variante, die von einer Regel gefangen wird, die nicht gegen sie entworfen wurde, ist das Gegenteil von Zirkularitaet.** Der Katalog hat dort eine Deckung, die ueber seine eigene Herleitung hinausreicht.

> **Trefferquote der Vorab-Zuordnung: 45 von 60.** Die Spalte `spiegelt_regel_exakt` stammt aus `spec/03`, Abschnitt 2 und wurde **vor** der Messung festgelegt; sie ist damit eine falsifizierbare Erwartung. Ueberschaetzt wurde bei ['F1-a', 'F8-a', 'F8-c', 'F8-d'] (eine greifende Regel erwartet, Variante bleibt trotzdem unentdeckt), unterschaetzt bei ['F1-c', 'F1-d', 'F1-e', 'F1-f', 'F2-a', 'F2-h', 'F2-i', 'F2-k', 'F3-g', 'HO1-a', 'HO1-b'] (keine Regel erwartet, Variante wird trotzdem gefunden). Geprueft wird gegen einen Recall von 0,5; bei der Einstufung 'teilweise' gegen einen Wert echt zwischen 0 und 1.

| variante | fehlerklasse | ebene | spiegelt_regel_exakt | erwartet_unentdeckt | erwartete_regeln | anmerkung | treffende_regeln | meldende_regeln | trefferkategorie | n | tp | recall | ci_unten | ci_oben | wiederholungen | erwartung_eingetroffen | abweichungsrichtung |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F1-a | F1 | zellebene | ja | nein | R-001 |  | R-057, R-043, R-001, R-041, R-039 | R-057, R-043, R-001, R-041, R-039 | A: erkannt durch die zugeordnete Regel | 3000 | 657 | 0,2190 | 0,2043 | 0,2342 | 5 | nein | ueberschaetzt |
| F1-b | F1 | zellebene | nein | nein | R-001, R-057 | Der Leerstring ist auf der Rohschicht nicht von einem planmaessig leeren Feld zu unterscheiden; R-025 meldet ihn deshalb nicht. Erkennbar nur ueber die Pflichtfeldregeln. Informationsverlust der Serialisierung, kein Mangel. | R-057, R-043, R-001, R-041, R-039 | R-057, R-001, R-043, R-041, R-039 | A: erkannt durch die zugeordnete Regel | 3000 | 646 | 0,2153 | 0,2007 | 0,2305 | 5 | ja |  |
| F1-c | F1 | zellebene | nein | nein | R-025 | Sentinelwert; R-025 prueft eine Platzhalterliste, nicht das Fehlen selbst. | R-025, R-009, R-043, R-057, R-050, R-001, R-051, R-041, R-002, R-003, R-004, R-006, R-013, R-012, R-011, R-018, R-020, R-019, R-005, R-008, R-058, R-007, R-017, R-037, R-039 | R-025, R-043, R-009, R-057, R-034, R-051, R-050, R-001, R-041, R-037, R-002, R-003, R-004, R-006, R-013, R-012, R-011, R-018, R-020, R-019, R-005, R-008, R-058, R-007, R-017, R-053, R-039 | A: erkannt durch die zugeordnete Regel | 3000 | 1588 | 0,5293 | 0,5113 | 0,5473 | 5 | nein | unterschaetzt |
| F1-d | F1 | zellebene | nein | nein | R-025 | Sentinelwert; R-025 prueft eine Platzhalterliste, nicht das Fehlen selbst. | R-025, R-043, R-009, R-057, R-001, R-050, R-051, R-041, R-018, R-002, R-006, R-012, R-003, R-004, R-005, R-013, R-011, R-008, R-020, R-058, R-019, R-007, R-017, R-037, R-039 | R-025, R-043, R-009, R-057, R-051, R-034, R-041, R-001, R-050, R-018, R-037, R-002, R-006, R-012, R-003, R-004, R-005, R-013, R-011, R-008, R-020, R-058, R-019, R-007, R-053, R-017, R-039 | A: erkannt durch die zugeordnete Regel | 3000 | 1588 | 0,5293 | 0,5113 | 0,5473 | 5 | nein | unterschaetzt |
| F1-e | F1 | zellebene | nein | nein | R-025 | Numerisches Sentinel; nur auffindbar, wenn es in der Platzhalterliste steht. | R-025, R-031, R-032, R-044, R-043, R-053, R-036, R-033, R-035, R-015, R-058, R-051, R-014, R-010, R-038, R-042, R-023, R-016, R-022, R-040 | R-025, R-031, R-032, R-044, R-036, R-043, R-053, R-033, R-051, R-058, R-035, R-015, R-038, R-014, R-042, R-010, R-023, R-040, R-016, R-022 | A: erkannt durch die zugeordnete Regel | 3000 | 2968 | 0,9893 | 0,9850 | 0,9927 | 5 | nein | unterschaetzt |
| F1-f | F1 | zellebene | nein | nein | R-025 | Datums-Sentinel; nur auffindbar, wenn es in der Platzhalterliste steht. | R-025, R-028, R-027, R-056 | R-055, R-025, R-028, R-027, R-056 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | nein | unterschaetzt |
| F2-a | F2 | zellebene | teilweise | nein | R-002 | Die Laengenbedingung von R-002 wird nur verletzt, wenn die Postleitzahl mit einer Null beginnt; sonst bleibt der Wert formal gueltig. | R-002, R-050 | R-002, R-050 | A: erkannt durch die zugeordnete Regel | 1124 | 1124 | 1,0000 | 0,9967 | 1,0000 | 5 | nein | unterschaetzt |
| F2-b | F2 | zellebene | ja | nein | R-002 |  | R-002, R-050 | R-002, R-050 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F2-c | F2 | zellebene | ja | nein | R-004 |  | R-004 | R-004 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F2-d | F2 | zellebene | ja | nein | R-003 |  | R-003, R-004 | R-003, R-004 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F2-e | F2 | zellebene | ja | nein | R-005 |  | R-005 | R-005 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F2-f | F2 | zellebene | ja | nein | R-009 |  | R-009, R-001 | R-009, R-001 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F2-g | F2 | zellebene | ja | nein | R-009 |  | R-009, R-001 | R-009, R-001 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F2-h | F2 | zellebene | nein | nein | R-008 | Fremdformat aus einer anderen Schnittstelle; keine Regel zielt darauf. | R-009, R-001 | R-009, R-001 | B: erkannt durch eine andere Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | nein | unterschaetzt |
| F2-i | F2 | zellebene | nein | nein | R-008 | Excel-Serial; keine Regel zielt auf diese Darstellung. | R-009, R-001 | R-009, R-001 | B: erkannt durch eine andere Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | nein | unterschaetzt |
| F2-j | F2 | zellebene | ja | nein | R-007 |  | R-007, R-051 | R-051, R-007 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F2-k | F2 | zellebene | teilweise | nein | R-007 | Kleinbuchstaben in der TSN; die Musterbedingung schliesst sie nicht ausdruecklich aus, sondern nur ueber die Zeichenklasse. | R-008, R-051 | R-051, R-008 | B: erkannt durch eine andere Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | nein | unterschaetzt |
| F2-l | F2 | zellebene | ja | nein | R-006 |  | R-006 | R-006 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F3-a | F3 | zellebene | ja | nein | R-014 |  | R-014, R-051 | R-051, R-014 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F3-b | F3 | zellebene | ja | nein | R-014 |  | R-014, R-051 | R-051, R-014 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F3-c | F3 | zellebene | nein | nein | R-013 | Typfehler statt Bereichsfehler; die Bereichsregel greift nicht. |  |  | C: nicht erkannt | 3000 | 0 | 0,0000 | 0,0000 | 0,0012 | 5 | ja |  |
| F3-d | F3 | zellebene | ja | nein | R-010 |  | R-010 | R-010 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F3-e | F3 | zellebene | ja | nein | R-010 |  | R-010 | R-010 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F3-f | F3 | zellebene | ja | nein | R-016 |  | R-016 | R-016 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F3-g | F3 | zellebene | nein | nein | R-011 | Darstellungswechsel der SF-Klasse; keine Bereichsregel zielt darauf. | R-013 | R-013 | B: erkannt durch eine andere Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | nein | unterschaetzt |
| F3-h | F3 | zellebene | ja | nein | R-017 |  | R-017 | R-017 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F3-i | F3 | zellebene | ja | nein | R-015 |  | R-015, R-058 | R-058, R-015 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F4-a | F4 | zellebene | ja | nein | R-026 |  | R-026, R-027 | R-027, R-026 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F4-b | F4 | zellebene | ja | nein | R-023 |  | R-023 | R-023 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F4-c | F4 | zellebene | ja | nein | R-022 |  | R-022, R-040 | R-040, R-022 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F4-d | F4 | zellebene | ja | nein | R-022 | Grenzfall knapp unterhalb der Schwelle. | R-022 | R-022 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F4-e | F4 | zellebene | ja | nein | R-038 |  | R-038 | R-038 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F4-f | F4 | zellebene | ja | nein | R-024 |  | R-024 | R-024 | A: erkannt durch die zugeordnete Regel | 57 | 57 | 1,0000 | 0,9373 | 1,0000 | 5 | ja |  |
| F4-g | F4 | zellebene | ja | nein | R-021 |  | R-021, R-031, R-032, R-042, R-040, R-024 | R-031, R-032, R-021, R-042, R-040, R-024 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F5-a | F5 | zellebene | ja | nein | R-031 |  | R-031, R-032 | R-031, R-032 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F5-b | F5 | zellebene | ja | nein | R-032, R-033 |  | R-031, R-032 | R-031, R-032 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F5-c | F5 | zellebene | ja | nein | R-033 |  | R-032, R-033 | R-032, R-033 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F5-d | F5 | zellebene | ja | nein | R-031 | Grenzfall knapp oberhalb der Toleranz von R-031. | R-031 | R-031 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F5-e | F5 | zellebene | nein | ja |  | Liegt innerhalb der Toleranz von R-031 und soll unentdeckt bleiben; die Variante prueft, ob die Toleranzgrenze korrekt implementiert ist. |  |  | C: nicht erkannt | 3000 | 0 | 0,0000 | 0,0000 | 0,0012 | 5 | ja |  |
| F5-f | F5 | zellebene | ja | nein | R-029 |  | R-029 | R-029 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F5-g | F5 | zellebene | ja | nein | R-039 |  | R-039 | R-039 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F5-h | F5 | zellebene | ja | nein | R-042 |  | R-042 | R-042 | A: erkannt durch die zugeordnete Regel | 2691 | 2691 | 1,0000 | 0,9986 | 1,0000 | 5 | ja |  |
| F5-i | F5 | zellebene | ja | nein | R-035 |  | R-035 | R-035 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F6-a | F6 | satzebene | ja | nein | R-043, R-045 |  |  | R-045, R-043 | S: satzbasiert, zellbasierte Zuordnung nicht definiert | 6000 | 6000 | 1,0000 | 0,9994 | 1,0000 | 5 | ja |  |
| F6-b | F6 | satzebene | ja | nein | R-043 |  |  | R-045, R-044, R-043 | S: satzbasiert, zellbasierte Zuordnung nicht definiert | 6000 | 6000 | 1,0000 | 0,9994 | 1,0000 | 5 | ja |  |
| F6-c | F6 | satzebene | ja | nein | R-045 |  |  | R-045, R-043, R-044 | S: satzbasiert, zellbasierte Zuordnung nicht definiert | 6000 | 6000 | 1,0000 | 0,9994 | 1,0000 | 5 | ja |  |
| F6-d | F6 | satzebene | ja | nein | R-046 |  |  | R-046 | S: satzbasiert, zellbasierte Zuordnung nicht definiert | 6000 | 5407 | 0,9012 | 0,8933 | 0,9086 | 5 | ja |  |
| F7-a | F7 | zellebene | ja | nein | R-055 |  | R-055 | R-055 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F7-b | F7 | zellebene | ja | nein | R-055 |  | R-055 | R-055 | A: erkannt durch die zugeordnete Regel | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F7-c | F7 | zellebene | ja | nein | R-056 |  | R-056 | R-055, R-056 | A: erkannt durch die zugeordnete Regel | 231 | 231 | 1,0000 | 0,9842 | 1,0000 | 5 | ja |  |
| F7-d | F7 | zellebene | nein | ja |  | Das Feld tarifgeneration wird von keiner Regel geprueft; erwartet unentdeckt. |  |  | C: nicht erkannt | 231 | 0 | 0,0000 | 0,0000 | 0,0158 | 5 | ja |  |
| F8-a | F8 | zellebene | ja | nein | R-052 |  | R-052 | R-052 | A: erkannt durch die zugeordnete Regel | 2998 | 984 | 0,3282 | 0,3114 | 0,3454 | 5 | nein | ueberschaetzt |
| F8-b | F8 | zellebene | ja | nein | R-053 |  | R-032, R-053, R-025 | R-032, R-053, R-025 | A: erkannt durch die zugeordnete Regel | 3000 | 2169 | 0,7230 | 0,7066 | 0,7390 | 5 | ja |  |
| F8-c | F8 | zellebene | ja | nein | R-053 |  | R-053 | R-053 | A: erkannt durch die zugeordnete Regel | 3000 | 747 | 0,2490 | 0,2336 | 0,2649 | 5 | nein | ueberschaetzt |
| F8-d | F8 | zellebene | ja | nein | R-054 |  | R-053, R-054 | R-053, R-054 | A: erkannt durch die zugeordnete Regel | 3000 | 406 | 0,1353 | 0,1233 | 0,1481 | 5 | nein | ueberschaetzt |
| F8-e | F8 | zellebene | nein | ja |  | R-054 prueft gegen den Median der uebrigen Angebote; skaliert man alle Angebote einer Anfrage, wandert der Median mit. Strukturelle Grenze relationaler Plausibilitaetspruefung, erwartet unentdeckt. | R-053 | R-053 | B: erkannt durch eine andere Regel | 2989 | 362 | 0,1211 | 0,1096 | 0,1333 | 5 | ja |  |
| HO1-a | HO1 | satzebene | nein | ja |  | Held-out: unscharfe Dublette; der Katalog kennt nur exakte Duplikate. |  | R-046 | S: satzbasiert, zellbasierte Zuordnung nicht definiert | 6000 | 4794 | 0,7990 | 0,7886 | 0,8091 | 5 | nein | unterschaetzt |
| HO1-b | HO1 | satzebene | nein | ja |  | Held-out: Tippfehler im Vornamen; keine Regel prueft Namensaehnlichkeit. |  | R-046 | S: satzbasiert, zellbasierte Zuordnung nicht definiert | 6000 | 4791 | 0,7985 | 0,7881 | 0,8086 | 5 | nein | unterschaetzt |
| HO2-a | HO2 | zellebene | nein | ja |  | Held-out: die ersetzte Postleitzahl existiert und der Ort wird mitgezogen; der Datensatz bleibt in sich stimmig. |  |  | C: nicht erkannt | 3000 | 0 | 0,0000 | 0,0000 | 0,0012 | 5 | ja |  |
| HO2-b | HO2 | zellebene | nein | ja |  | Held-out: kohaerente Senkung um 15 Prozent; R-031, R-032 und R-036 bleiben erfuellt, der Wert bleibt im plausiblen Korridor. |  |  | C: nicht erkannt | 3000 | 0 | 0,0000 | 0,0000 | 0,0012 | 5 | ja |  |
