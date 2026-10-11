# CR-012 P&D-E2E held-out results

Gold: `data/gold/pd_e2e_test_blind.csv` (7 sections, 426 headline edges). **Inter-annotator agreement: NOT_EVALUABLE_SINGLE_ANNOTATOR.** The LLM prefill was reviewed by the owner and is not a second annotator.

## Headline (E0, the system score)

STRICT_E2E_EDGE precision / recall / F1 = **0.092 / 0.038 / 0.053** (micro-pooled over 7 sections; tp 16).
Section-bootstrap 95% interval for F1: [0.030, 0.076], labelled **DESCRIPTIVE_SMALL_N** / NOT_EVALUABLE_SMALL_N (7 sections; 1716 distinct resamples): not a strong inferential CI.

## Oracle diagnostics (conditional / oracle uplifts; not an additive causal decomposition)

| level | P / R / F1 | pair recall | canonical-node F1 | typed mention F1 |
|---|---|---|---|---|
| E0 (headline) | 0.092 / 0.038 / 0.053 | 53/326 | 0.643 | 0.226 |
| E1 | 0.212 / 0.077 / 0.113 | 92/419 | 0.855 | 0.985 |
| E2 | 0.220 / 0.092 / 0.129 | 109/425 | 0.996 | 0.979 |
| E3 | 0.457 / 0.352 / 0.398 | 425/425 | 0.996 | 0.979 |
| E4 | 0.708 / 0.352 / 0.470 | 425/425 | 0.996 | 0.979 |

## Per section (E0)

| section | P / R / F1 | tp / fp / fn | pair recall | nodes | edges |
|---|---|---|---|---|---|
| 4.4 | 0.130 / 0.048 / 0.070 | 3 / 20 / 60 | 9/49 | 116 | 23 |
| 4.5 | 0.133 / 0.041 / 0.062 | 2 / 13 / 47 | 5/41 | 100 | 15 |
| 5.4 | 0.148 / 0.071 / 0.096 | 4 / 23 / 52 | 8/37 | 122 | 27 |
| 6.3 | 0.000 / 0.000 / 0.000 | 0 / 26 / 47 | 4/34 | 85 | 26 |
| 7.1 | 0.036 / 0.014 / 0.021 | 1 / 27 / 68 | 10/55 | 148 | 28 |
| 8.2 | 0.133 / 0.062 / 0.085 | 4 / 26 / 60 | 9/51 | 88 | 30 |
| 9.3 | 0.080 / 0.026 / 0.039 | 2 / 23 / 76 | 8/59 | 131 | 25 |

## Identity (canonical graph)

E0 pooled canonical-node F1 0.643; macro pairwise identity F1 0.015; macro B-cubed F1 0.322. With gold identity supplied (E2) the node F1 is 0.996.

## Relation stage

Given the gold endpoint pairs (E3), a predicted edge exists for 216 gold pairs; relation correct 152 / 216 = 70.4%; direction correct 150 / 216 = 69.4%. E4 (0.470) is the frozen relation-stage ceiling **under gold endpoint assistance**, not achievable production accuracy.
