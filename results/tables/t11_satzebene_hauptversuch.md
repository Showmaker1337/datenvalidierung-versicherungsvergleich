# t11_satzebene_hauptversuch

> Satzebene des **Hauptversuchs**, aggregiert ueber die vier Ratenstufen und zwanzig Wiederholungen. Sie ist der Primaervergleich fuer B2 (Phase 5, Abschnitt 5.3); `t1_hauptergebnis` fuehrt fuer diese sieben Klassen nur die Zellebene. Es wurde kein Lauf neu gerechnet — die Werte standen bereits im Langformat und werden hier nur aggregiert.

> **Ungewichtetes Mittel des F1 ueber die Fehlerklassen** (jede Klasse zaehlt gleich viel): prototyp = 0,7957; B0 = 0,2523; B2 = 0,1589.
>
> **Fuehrendes Verfahren je Fehlerklasse** (Ablesung des hoechsten F1, kein Test — welche Unterschiede gesichert sind, steht in der Familie `HYP4-paarweise-Satz`): F1: prototyp (0,6284); F2: prototyp (1,0000); F3: prototyp (0,9374); F4: prototyp (1,0000); F5: prototyp (0,8861); F7: prototyp (0,8049); F8: prototyp (0,3130).
>
> Bilanz: prototyp fuehrt in 7 von 7 Klassen.

| verfahren | fehlerklasse | teilversuch | ebene | precision | precision_ci_unten | precision_ci_oben | precision_ci_art | recall | recall_ci_unten | recall_ci_oben | recall_ci_art | f1 | f1_ci_unten | f1_ci_oben | f1_ci_art |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| prototyp | F1 | haupt | satzebene | 0,6557 | 0,6543 | 0,6570 | bca | 0,6033 | 0,6025 | 0,6041 | bca | 0,6284 | 0,6278 | 0,6289 | bca |
| B0 | F1 | haupt | satzebene | 1,0000 | 1,0000 | 1,0000 | entartet | 0,3938 | 0,3934 | 0,3942 | bca | 0,5637 | 0,5632 | 0,5641 | bca |
| B2 | F1 | haupt | satzebene | 0,6399 | 0,6378 | 0,6424 | bca | 0,4480 | 0,4450 | 0,4516 | bca | 0,4730 | 0,4708 | 0,4761 | bca |
| prototyp | F2 | haupt | satzebene | 1,0000 | 1,0000 | 1,0000 | entartet | 1,0000 | 1,0000 | 1,0000 | clopper-pearson | 1,0000 | 1,0000 | 1,0000 | entartet |
| B0 | F2 | haupt | satzebene | 1,0000 | 1,0000 | 1,0000 | entartet | 0,9103 | 0,9100 | 0,9108 | bca | 0,9530 | 0,9528 | 0,9533 | bca |
| B2 | F2 | haupt | satzebene | 0,1159 | 0,1136 | 0,1180 | bca | 0,3117 | 0,3024 | 0,3200 | bca | 0,1659 | 0,1632 | 0,1680 | bca |
| prototyp | F3 | haupt | satzebene | 1,0000 | 1,0000 | 1,0000 | entartet | 0,8822 | 0,8817 | 0,8826 | bca | 0,9374 | 0,9370 | 0,9376 | bca |
| B0 | F3 | haupt | satzebene | 1,0000 | 1,0000 | 1,0000 | entartet | 0,1427 | 0,1424 | 0,1429 | bca | 0,2496 | 0,2492 | 0,2500 | bca |
| B2 | F3 | haupt | satzebene | 0,0371 | 0,0365 | 0,0380 | bca | 0,2152 | 0,2040 | 0,2274 | bca | 0,0622 | 0,0615 | 0,0629 | bca |
| prototyp | F4 | haupt | satzebene | 1,0000 | 1,0000 | 1,0000 | entartet | 1,0000 | 1,0000 | 1,0000 | clopper-pearson | 1,0000 | 1,0000 | 1,0000 | entartet |
| B0 | F4 | haupt | satzebene | 0,0000 | 0,0000 | 0,0000 | entartet | 0,0000 | 0,0000 | 0,0000 | clopper-pearson | 0,0000 | 0,0000 | 0,0000 | entartet |
| B2 | F4 | haupt | satzebene | 0,0484 | 0,0475 | 0,0493 | bca | 0,2730 | 0,2617 | 0,2792 | bca | 0,0766 | 0,0753 | 0,0780 | bca |
| prototyp | F5 | haupt | satzebene | 1,0000 | 1,0000 | 1,0000 | entartet | 0,7955 | 0,7953 | 0,7957 | bca | 0,8861 | 0,8860 | 0,8862 | bca |
| B0 | F5 | haupt | satzebene | 0,0000 | 0,0000 | 0,0000 | entartet | 0,0000 | 0,0000 | 0,0000 | clopper-pearson | 0,0000 | 0,0000 | 0,0000 | entartet |
| B2 | F5 | haupt | satzebene | 0,0786 | 0,0781 | 0,0791 | bca | 0,2024 | 0,2013 | 0,2035 | bca | 0,1011 | 0,1005 | 0,1018 | bca |
| prototyp | F7 | haupt | satzebene | 0,6820 | 0,6662 | 0,7003 | bca | 0,9921 | 0,9919 | 0,9923 | bca | 0,8049 | 0,7936 | 0,8176 | bca |
| B0 | F7 | haupt | satzebene | 0,0000 | 0,0000 | 0,0000 | entartet | 0,0000 | 0,0000 | 0,0000 | clopper-pearson | 0,0000 | 0,0000 | 0,0000 | entartet |
| B2 | F7 | haupt | satzebene | 0,0602 | 0,0596 | 0,0607 | bca | 0,2393 | 0,2310 | 0,2448 | bca | 0,0883 | 0,0873 | 0,0890 | bca |
| prototyp | F8 | haupt | satzebene | 0,1913 | 0,1906 | 0,1921 | bca | 0,8664 | 0,8636 | 0,8693 | bca | 0,3130 | 0,3119 | 0,3142 | bca |
| B0 | F8 | haupt | satzebene | 0,0000 | 0,0000 | 0,0000 | entartet | 0,0000 | 0,0000 | 0,0000 | clopper-pearson | 0,0000 | 0,0000 | 0,0000 | entartet |
| B2 | F8 | haupt | satzebene | 0,1142 | 0,1106 | 0,1254 | bca | 0,2467 | 0,2397 | 0,2519 | bca | 0,1450 | 0,1434 | 0,1478 | bca |
