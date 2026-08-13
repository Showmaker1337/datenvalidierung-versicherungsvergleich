# t4_varianten

> **Trefferquote der Vorab-Zuordnung: 45 von 60.** Die Spalte `spiegelt_regel_exakt` stammt aus `spec/03`, Abschnitt 2 und wurde **vor** der Messung festgelegt; sie ist damit eine falsifizierbare Erwartung. Ueberschaetzt wurde bei ['F1-a', 'F8-a', 'F8-c', 'F8-d'] (eine greifende Regel erwartet, Variante bleibt trotzdem unentdeckt), unterschaetzt bei ['F1-c', 'F1-d', 'F1-e', 'F1-f', 'F2-a', 'F2-h', 'F2-i', 'F2-k', 'F3-g', 'HO1-a', 'HO1-b'] (keine Regel erwartet, Variante wird trotzdem gefunden). Geprueft wird gegen einen Recall von 0,5; bei der Einstufung 'teilweise' gegen einen Wert echt zwischen 0 und 1.

| variante | fehlerklasse | ebene | spiegelt_regel_exakt | erwartet_unentdeckt | erwartete_regeln | anmerkung | n | tp | recall | ci_unten | ci_oben | wiederholungen | erwartung_eingetroffen | abweichungsrichtung |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F1-a | F1 | zellebene | ja | nein | R-001 |  | 3000 | 657 | 0,2190 | 0,2043 | 0,2342 | 5 | nein | ueberschaetzt |
| F1-b | F1 | zellebene | nein | nein | R-001, R-057 | Der Leerstring ist auf der Rohschicht nicht von einem planmaessig leeren Feld zu unterscheiden; R-025 meldet ihn deshalb nicht. Erkennbar nur ueber die Pflichtfeldregeln. Informationsverlust der Serialisierung, kein Mangel. | 3000 | 646 | 0,2153 | 0,2007 | 0,2305 | 5 | ja |  |
| F1-c | F1 | zellebene | nein | nein | R-025 | Sentinelwert; R-025 prueft eine Platzhalterliste, nicht das Fehlen selbst. | 3000 | 1588 | 0,5293 | 0,5113 | 0,5473 | 5 | nein | unterschaetzt |
| F1-d | F1 | zellebene | nein | nein | R-025 | Sentinelwert; R-025 prueft eine Platzhalterliste, nicht das Fehlen selbst. | 3000 | 1588 | 0,5293 | 0,5113 | 0,5473 | 5 | nein | unterschaetzt |
| F1-e | F1 | zellebene | nein | nein | R-025 | Numerisches Sentinel; nur auffindbar, wenn es in der Platzhalterliste steht. | 3000 | 2968 | 0,9893 | 0,9850 | 0,9927 | 5 | nein | unterschaetzt |
| F1-f | F1 | zellebene | nein | nein | R-025 | Datums-Sentinel; nur auffindbar, wenn es in der Platzhalterliste steht. | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | nein | unterschaetzt |
| F2-a | F2 | zellebene | teilweise | nein | R-002 | Die Laengenbedingung von R-002 wird nur verletzt, wenn die Postleitzahl mit einer Null beginnt; sonst bleibt der Wert formal gueltig. | 1124 | 1124 | 1,0000 | 0,9967 | 1,0000 | 5 | nein | unterschaetzt |
| F2-b | F2 | zellebene | ja | nein | R-002 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F2-c | F2 | zellebene | ja | nein | R-004 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F2-d | F2 | zellebene | ja | nein | R-003 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F2-e | F2 | zellebene | ja | nein | R-005 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F2-f | F2 | zellebene | ja | nein | R-009 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F2-g | F2 | zellebene | ja | nein | R-009 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F2-h | F2 | zellebene | nein | nein | R-008 | Fremdformat aus einer anderen Schnittstelle; keine Regel zielt darauf. | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | nein | unterschaetzt |
| F2-i | F2 | zellebene | nein | nein | R-008 | Excel-Serial; keine Regel zielt auf diese Darstellung. | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | nein | unterschaetzt |
| F2-j | F2 | zellebene | ja | nein | R-007 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F2-k | F2 | zellebene | teilweise | nein | R-007 | Kleinbuchstaben in der TSN; die Musterbedingung schliesst sie nicht ausdruecklich aus, sondern nur ueber die Zeichenklasse. | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | nein | unterschaetzt |
| F2-l | F2 | zellebene | ja | nein | R-006 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F3-a | F3 | zellebene | ja | nein | R-014 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F3-b | F3 | zellebene | ja | nein | R-014 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F3-c | F3 | zellebene | nein | nein | R-013 | Typfehler statt Bereichsfehler; die Bereichsregel greift nicht. | 3000 | 0 | 0,0000 | 0,0000 | 0,0012 | 5 | ja |  |
| F3-d | F3 | zellebene | ja | nein | R-010 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F3-e | F3 | zellebene | ja | nein | R-010 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F3-f | F3 | zellebene | ja | nein | R-016 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F3-g | F3 | zellebene | nein | nein | R-011 | Darstellungswechsel der SF-Klasse; keine Bereichsregel zielt darauf. | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | nein | unterschaetzt |
| F3-h | F3 | zellebene | ja | nein | R-017 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F3-i | F3 | zellebene | ja | nein | R-015 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F4-a | F4 | zellebene | ja | nein | R-026 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F4-b | F4 | zellebene | ja | nein | R-023 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F4-c | F4 | zellebene | ja | nein | R-022 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F4-d | F4 | zellebene | ja | nein | R-022 | Grenzfall knapp unterhalb der Schwelle. | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F4-e | F4 | zellebene | ja | nein | R-038 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F4-f | F4 | zellebene | ja | nein | R-024 |  | 57 | 57 | 1,0000 | 0,9373 | 1,0000 | 5 | ja |  |
| F4-g | F4 | zellebene | ja | nein | R-021 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F5-a | F5 | zellebene | ja | nein | R-031 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F5-b | F5 | zellebene | ja | nein | R-032, R-033 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F5-c | F5 | zellebene | ja | nein | R-033 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F5-d | F5 | zellebene | ja | nein | R-031 | Grenzfall knapp oberhalb der Toleranz von R-031. | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F5-e | F5 | zellebene | nein | ja |  | Liegt innerhalb der Toleranz von R-031 und soll unentdeckt bleiben; die Variante prueft, ob die Toleranzgrenze korrekt implementiert ist. | 3000 | 0 | 0,0000 | 0,0000 | 0,0012 | 5 | ja |  |
| F5-f | F5 | zellebene | ja | nein | R-029 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F5-g | F5 | zellebene | ja | nein | R-039 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F5-h | F5 | zellebene | ja | nein | R-042 |  | 2691 | 2691 | 1,0000 | 0,9986 | 1,0000 | 5 | ja |  |
| F5-i | F5 | zellebene | ja | nein | R-035 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F6-a | F6 | satzebene | ja | nein | R-043, R-045 |  | 6000 | 6000 | 1,0000 | 0,9994 | 1,0000 | 5 | ja |  |
| F6-b | F6 | satzebene | ja | nein | R-043 |  | 6000 | 6000 | 1,0000 | 0,9994 | 1,0000 | 5 | ja |  |
| F6-c | F6 | satzebene | ja | nein | R-045 |  | 6000 | 6000 | 1,0000 | 0,9994 | 1,0000 | 5 | ja |  |
| F6-d | F6 | satzebene | ja | nein | R-046 |  | 6000 | 5407 | 0,9012 | 0,8933 | 0,9086 | 5 | ja |  |
| F7-a | F7 | zellebene | ja | nein | R-055 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F7-b | F7 | zellebene | ja | nein | R-055 |  | 3000 | 3000 | 1,0000 | 0,9988 | 1,0000 | 5 | ja |  |
| F7-c | F7 | zellebene | ja | nein | R-056 |  | 231 | 231 | 1,0000 | 0,9842 | 1,0000 | 5 | ja |  |
| F7-d | F7 | zellebene | nein | ja |  | Das Feld tarifgeneration wird von keiner Regel geprueft; erwartet unentdeckt. | 231 | 0 | 0,0000 | 0,0000 | 0,0158 | 5 | ja |  |
| F8-a | F8 | zellebene | ja | nein | R-052 |  | 2998 | 984 | 0,3282 | 0,3114 | 0,3454 | 5 | nein | ueberschaetzt |
| F8-b | F8 | zellebene | ja | nein | R-053 |  | 3000 | 2169 | 0,7230 | 0,7066 | 0,7390 | 5 | ja |  |
| F8-c | F8 | zellebene | ja | nein | R-053 |  | 3000 | 747 | 0,2490 | 0,2336 | 0,2649 | 5 | nein | ueberschaetzt |
| F8-d | F8 | zellebene | ja | nein | R-054 |  | 3000 | 406 | 0,1353 | 0,1233 | 0,1481 | 5 | nein | ueberschaetzt |
| F8-e | F8 | zellebene | nein | ja |  | R-054 prueft gegen den Median der uebrigen Angebote; skaliert man alle Angebote einer Anfrage, wandert der Median mit. Strukturelle Grenze relationaler Plausibilitaetspruefung, erwartet unentdeckt. | 2989 | 362 | 0,1211 | 0,1096 | 0,1333 | 5 | ja |  |
| HO1-a | HO1 | satzebene | nein | ja |  | Held-out: unscharfe Dublette; der Katalog kennt nur exakte Duplikate. | 6000 | 4794 | 0,7990 | 0,7886 | 0,8091 | 5 | nein | unterschaetzt |
| HO1-b | HO1 | satzebene | nein | ja |  | Held-out: Tippfehler im Vornamen; keine Regel prueft Namensaehnlichkeit. | 6000 | 4791 | 0,7985 | 0,7881 | 0,8086 | 5 | nein | unterschaetzt |
| HO2-a | HO2 | zellebene | nein | ja |  | Held-out: die ersetzte Postleitzahl existiert und der Ort wird mitgezogen; der Datensatz bleibt in sich stimmig. | 3000 | 0 | 0,0000 | 0,0000 | 0,0012 | 5 | ja |  |
| HO2-b | HO2 | zellebene | nein | ja |  | Held-out: kohaerente Senkung um 15 Prozent; R-031, R-032 und R-036 bleiben erfuellt, der Wert bleibt im plausiblen Korridor. | 3000 | 0 | 0,0000 | 0,0000 | 0,0012 | 5 | ja |  |
