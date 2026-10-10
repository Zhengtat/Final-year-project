# CR-012 STOP 4 results (`rehearsal`)

P&D-E2E and SciNLP are reported separately; there is no pooled number.

## SciNLP (mention level, 3 test documents, CI_status NOT_EVALUABLE_SMALL_N)

| level | relation strict micro P / R / F1 | per-document F1 | macro F1 | min / max doc F1 | entity strict micro F1 | entity typed micro F1 | $ |
|---|---|---|---|---|---|---|---|
| E0 | 0.200 / 0.167 / 0.182 | P02-1004=0.182 | 0.182 | 0.182 / 0.182 | 0.241 | 0.241 | 0.4693 |
| E1 | 0.800 / 0.667 / 0.727 | P02-1004=0.727 | 0.727 | 0.727 / 0.727 | 1.000 | 1.000 | 0.044 |
| E3 | 0.800 / 0.667 / 0.727 | P02-1004=0.727 | 0.727 | 0.727 / 0.727 | 1.000 | 1.000 | 0.0098 |
| E4 | 0.800 / 0.667 / 0.727 | P02-1004=0.727 | 0.727 | 0.727 / 0.727 | 1.000 | 1.000 | 0.0 |

Mention-level earliest-failure attribution over gold relations (C0 / C1 not applicable: no identity gold):

| level | misses | N0 | N1 | C0 | C1 | P0 | R0 | R1 | R2 | R3 | E0 | recovered |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E0 | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| E1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 5 |
| E3 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 5 |
| E4 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 5 |

Identity metrics (canonical-node F1, pairwise, B-cubed, E2): NOT_SUPPORTED. No bootstrap over entities or edges; the diagnostic document bootstrap is DESCRIPTIVE_SMALL_N_ONLY and is not reported as a CI.

