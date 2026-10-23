# CR-012 STOP 4 results (`pilot`)

P&D-E2E and SciNLP are reported separately; there is no pooled number.

## P&D-E2E (canonical graph, section bootstrap)

| level | sections | strict E2E P / R / F1 (pooled) | 95% section-bootstrap F1 | pair recall | canon node F1 | typed mention F1 | pairwise id F1 | B-cubed F1 | $ |
|---|---|---|---|---|---|---|---|---|---|
| E0 | 1 | 0.074 / 0.051 / 0.061 | [0.061, 0.061] (NOT_EVALUABLE_SMALL_N) | 4/18 | 0.597 | 0.181 | 0.006 | 0.236 | 0.3932 |
| E1 | 1 | 0.091 / 0.051 / 0.066 | [0.066, 0.066] (NOT_EVALUABLE_SMALL_N) | 3/35 | 0.766 | 0.957 | 0.732 | 0.813 | 0.4575 |
| E2 | 1 | 0.400 / 0.205 / 0.271 | [0.271, 0.271] (NOT_EVALUABLE_SMALL_N) | 12/39 | 1.000 | 0.957 | 0.945 | 0.954 | 0.3232 |
| E3 | 1 | 0.583 / 0.538 / 0.560 | [0.560, 0.560] (NOT_EVALUABLE_SMALL_N) | 39/39 | 1.000 | 0.957 | 0.945 | 0.954 | 0.2172 |
| E4 | 1 | 0.840 / 0.538 / 0.656 | [0.656, 0.656] (NOT_EVALUABLE_SMALL_N) | 39/39 | 1.000 | 0.957 | 0.945 | 0.954 | 0.045 |

Earliest-failure attribution (pooled over sections; S0/S1 not applicable):

| level | misses | N0 | N1 | C0 | C1 | P0 | R0 | R1 | R2 | R3 | E0 | recovered |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E0 | 38 | 10 | 6 | 0 | 13 | 7 | 1 | 1 | 0 | 0 | 0 | 2 |
| E1 | 39 | 2 | 0 | 10 | 21 | 6 | 0 | 0 | 0 | 0 | 0 | 1 |
| E2 | 32 | 0 | 0 | 0 | 0 | 28 | 3 | 1 | 0 | 0 | 0 | 8 |
| E3 | 18 | 0 | 0 | 0 | 0 | 0 | 14 | 4 | 0 | 0 | 0 | 22 |
| E4 | 18 | 0 | 0 | 0 | 0 | 0 | 14 | 4 | 0 | 0 | 0 | 22 |

Relation accuracy given correct endpoints (pooled; gold pairs with a predicted edge):

- E0: 3 pairs, relation correct 2, direction correct 2
- E1: 2 pairs, relation correct 2, direction correct 2
- E2: 9 pairs, relation correct 8, direction correct 8
- E3: 25 pairs, relation correct 21, direction correct 21
- E4: 25 pairs, relation correct 21, direction correct 21

Provenance and unsupported rates (E0, pooled over sections):

- unsupported node rate 0.029; unsupported edge rate 0.000; provenance completeness 0.979

