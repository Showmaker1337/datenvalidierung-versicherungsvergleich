# t5_frameworkvergleich

> Die Kennzahl 'Anteil ausdrueckbarer Regeln' ist NICHT frameworkunabhaengig. Great Expectations formuliert auf denselben sieben Regeln mehr als cuallee: row_condition deckt bedingte Regeln ab (R-001), ExpectColumnValuesToMatchStrftimeFormat echtes Datumsparsen (R-009). Frameworkuebergreifend belastbar ist der Kern der Grenze — die relationalen Regeln R-043 bis R-048, R-052 und R-054, die quellenuebergreifenden R-049 bis R-051 und R-055 bis R-058 sowie die algorithmische R-004. An R-004 scheitern beide.

| merkmal | cuallee | great_expectations | einheit |
|---|---|---|---|
| Anteil ausdrueckbarer Regeln (G1, vorgelegte Auswahl) | 0,8400 | 0,8571 | Anteil |
| Anteil ausdrueckbarer Regeln (ganzer Katalog) | 0,3621 | — | Anteil |
| Anteil ausdrueckbarer Regeln (G3, relational) | 0,0000 | 0,0000 | Anteil |
| Codezeilen je Regel, Summe ueber die verglichenen Regeln | 46 | 39 | Zeilen |
| Codezeilen je Regel, Prototyp zum Vergleich | 326 | — | Zeilen |
| Laufzeit | 0,3850 | 0,4452 | Sekunden |
| Diagnoseguete: regel | ja | ja | ja/nein |
| Diagnoseguete: spalte | ja | ja | ja/nein |
| Diagnoseguete: zeile | nein | ja | ja/nein |
| Diagnoseguete: ausgangswert | nein | ja | ja/nein |
| Diagnoseguete: anzahl_verstoesse | ja | ja | ja/nein |
| geht in die Inferenzstatistik ein | nein | nein | ja/nein |
