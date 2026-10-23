# CR-012 STOP 4 results (`heldout`)

P&D-E2E and SciNLP are reported separately; there is no pooled number.

## P&D-E2E (canonical graph, section bootstrap)

| level | sections | strict E2E P / R / F1 (pooled) | 95% section-bootstrap F1 | pair recall | canon node F1 | typed mention F1 | pairwise id F1 | B-cubed F1 | $ |
|---|---|---|---|---|---|---|---|---|---|
| E0 | 7 | 0.092 / 0.038 / 0.053 | [0.030, 0.076] (NOT_EVALUABLE_SMALL_N) | 53/326 | 0.643 | 0.226 | 0.015 | 0.322 | 3.7736 |
| E1 | 7 | 0.212 / 0.077 / 0.113 | [0.080, 0.152] (NOT_EVALUABLE_SMALL_N) | 92/419 | 0.855 | 0.985 | 0.878 | 0.897 | 3.7082 |
| E2 | 7 | 0.220 / 0.092 / 0.129 | [0.105, 0.153] (NOT_EVALUABLE_SMALL_N) | 109/425 | 0.996 | 0.979 | 0.975 | 0.978 | 2.2822 |
| E3 | 7 | 0.457 / 0.352 / 0.398 | [0.324, 0.452] (NOT_EVALUABLE_SMALL_N) | 425/425 | 0.996 | 0.979 | 0.975 | 0.978 | 2.2166 |
| E4 | 7 | 0.708 / 0.352 / 0.470 | [0.396, 0.522] (NOT_EVALUABLE_SMALL_N) | 425/425 | 0.996 | 0.979 | 0.975 | 0.978 | 0.0 |

Earliest-failure attribution (pooled over sections; S0/S1 not applicable):

| level | misses | N0 | N1 | C0 | C1 | P0 | R0 | R1 | R2 | R3 | E0 | recovered |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E0 | 416 | 67 | 34 | 79 | 1 | 206 | 16 | 6 | 1 | 6 | 0 | 16 |
| E1 | 397 | 5 | 1 | 206 | 23 | 143 | 12 | 7 | 0 | 0 | 0 | 35 |
| E2 | 391 | 0 | 1 | 0 | 0 | 319 | 47 | 23 | 1 | 0 | 0 | 41 |
| E3 | 279 | 0 | 1 | 0 | 0 | 0 | 211 | 65 | 2 | 0 | 0 | 153 |
| E4 | 279 | 0 | 1 | 0 | 0 | 0 | 211 | 65 | 2 | 0 | 0 | 153 |

Relation accuracy given correct endpoints (pooled; gold pairs with a predicted edge):

- E0: 32 pairs, relation correct 23, direction correct 22
- E1: 52 pairs, relation correct 33, direction correct 33
- E2: 62 pairs, relation correct 40, direction correct 39
- E3: 216 pairs, relation correct 152, direction correct 150
- E4: 216 pairs, relation correct 152, direction correct 150

Provenance and unsupported rates (E0, pooled over sections):

- unsupported node rate 0.029; unsupported edge rate 0.000; provenance completeness 0.976

## SciNLP (mention level, 3 test documents, CI_status NOT_EVALUABLE_SMALL_N)

| level | relation strict micro P / R / F1 | per-document F1 | macro F1 | min / max doc F1 | entity strict micro F1 | entity typed micro F1 | $ |
|---|---|---|---|---|---|---|---|
| E0 | 0.364 / 0.027 / 0.050 | 2021=0.046, 2024=0.057, P17-1058=0.000 | 0.034 | 0.000 / 0.057 | 0.352 | 0.342 | 1.9315 |
| E1 | 0.635 / 0.159 / 0.255 | 2021=0.232, 2024=0.284, P17-1058=0.000 | 0.172 | 0.000 / 0.284 | 0.979 | 0.975 | 1.1904 |
| E3 | 0.730 / 0.339 / 0.463 | 2021=0.494, 2024=0.429, P17-1058=0.000 | 0.308 | 0.000 / 0.494 | 0.983 | 0.979 | 1.2727 |
| E4 | 0.781 / 0.339 / 0.473 | 2021=0.498, 2024=0.446, P17-1058=0.000 | 0.315 | 0.000 / 0.498 | 0.983 | 0.979 | 0.0 |

Mention-level earliest-failure attribution over gold relations (C0 / C1 not applicable: no identity gold):

| level | misses | N0 | N1 | C0 | C1 | P0 | R0 | R1 | R2 | R3 | E0 | recovered |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E0 | 284 | 255 | 7 | 0 | 0 | 15 | 2 | 5 | 0 | 0 | 0 | 11 |
| E1 | 173 | 2 | 4 | 0 | 0 | 114 | 38 | 15 | 0 | 0 | 0 | 122 |
| E3 | 126 | 2 | 4 | 0 | 0 | 1 | 99 | 20 | 0 | 0 | 0 | 169 |
| E4 | 126 | 2 | 4 | 0 | 0 | 1 | 99 | 20 | 0 | 0 | 0 | 169 |

Identity metrics (canonical-node F1, pairwise, B-cubed, E2): NOT_SUPPORTED. No bootstrap over entities or edges; the diagnostic document bootstrap is DESCRIPTIVE_SMALL_N_ONLY and is not reported as a CI.

