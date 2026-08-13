# t7_teilversuche

| teilversuch | titel | gruppe | verfahren | ebene | wiederholungen | precision | precision_ci_unten | precision_ci_oben | precision_ci_art | recall | recall_ci_unten | recall_ci_oben | recall_ci_art | f1 | f1_ci_unten | f1_ci_oben | f1_ci_art |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | Duplikate: satzbasierte Metrik fuer F6 | F6 | prototyp | satzebene | 20 | 0,2978 | 0,2973 | 0,2984 | bca | 0,9936 | 0,9933 | 0,9939 | bca | 0,4574 | 0,4568 | 0,4581 | bca |
| T1 | Duplikate: satzbasierte Metrik fuer F6 | F6 | B0 | satzebene | 20 | 0,0000 | 0,0000 | 0,0000 | entartet | 0,0000 | 0,0000 | 0,0000 | clopper-pearson | 0,0000 | 0,0000 | 0,0000 | entartet |
| T1 | Duplikate: satzbasierte Metrik fuer F6 | F6 | B2 | satzebene | 20 | 0,0568 | 0,0563 | 0,0573 | bca | 0,1905 | 0,1885 | 0,1924 | bca | 0,0791 | 0,0785 | 0,0798 | bca |
| T2 | Held-out: erwarteter Recall nahe null | HO1 | prototyp | satzebene | 20 | 1,0000 | 1,0000 | 1,0000 | entartet | 0,7946 | 0,7804 | 0,8060 | bca | 0,8852 | 0,8760 | 0,8923 | bca |
| T2 | Held-out: erwarteter Recall nahe null | HO2 | prototyp | zellebene | 20 | 0,0000 | 0,0000 | 0,0000 | entartet | 0,0000 | 0,0000 | 0,0000 | clopper-pearson | 0,0000 | 0,0000 | 0,0000 | entartet |
| T3 | Praxismix: alle Klassen gemeinsam mit den Gewichten aus spec/03 | mix | prototyp | zellebene | 20 | 0,4105 | 0,3947 | 0,4148 | bca | 0,4994 | 0,4971 | 0,5015 | bca | 0,4504 | 0,4404 | 0,4535 | bca |
| T3 | Praxismix: alle Klassen gemeinsam mit den Gewichten aus spec/03 | mix | B0 | zellebene | 20 | 1,0000 | 1,0000 | 1,0000 | entartet | 0,2972 | 0,2956 | 0,2985 | bca | 0,4582 | 0,4563 | 0,4598 | bca |
| T3 | Praxismix: alle Klassen gemeinsam mit den Gewichten aus spec/03 | mix | B2 | zellebene | 20 | 0,0073 | 0,0072 | 0,0075 | bca | 0,2673 | 0,2609 | 0,2725 | bca | 0,0143 | 0,0140 | 0,0146 | bca |
| T5 | Datenvarianz: 20 verschiedene Basisdatensaetze | F5 | prototyp | zellebene | 20 | 0,4126 | 0,4122 | 0,4130 | bca | 0,8292 | 0,8290 | 0,8294 | bca | 0,5510 | 0,5507 | 0,5514 | bca |
