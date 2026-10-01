# CR-007 STOP 4: CR-005 vs CR-007 on P&D ch1-3

Generated read-only from run `slice3_a1`; no API calls. CR-005 numbers are the STOP 1 diagnostics (b) baselines (ch2-3 slice).

## 1. Relation outcomes of the pairs classified

| outcome | CR-005 (381 pairs, ch2-3) | CR-007 (700 pairs, ch1-3) |
|---|---|---|
| edge accepted | 121 / 381 = 31.8% | 297 / 700 = 42.4% |
| OTHER | 117 / 381 = 30.7% | 146 / 700 = 20.9% |
| NO_RELATION | 143 / 381 = 37.5% | 176 / 700 = 25.1% |
| rejected by a check | - | 65 / 700 = 9.3% |
| edge of a relation dropped at its gate (`gated_dropped`: kept in run data, not in the graph) | - | 16 / 700 = 2.3% |

Rejection reasons: {'endpoint_not_grounded': 20, 'domain_range': 45}. OTHER share among pairs that passed the checks: 146 / 635 = 23.0%.
Target in the CR: OTHER <= 15%. Measured 20.9% of all pairs (23.0% of pairs not rejected).

## 2. Selection effect vs classifier effect

- **Selection effect (attempted coverage):** concepts with >=1 classified pair: 805 of 982 concepts (CR-005: 152 of 736). Defined/used concepts attempted: 786 / 876 = 89.7%.
- **Classifier effect (accepted rate among attempted pairs):** 297 / 700 = 42.4% (CR-005 121 / 381 = 31.8%).

### By chapter of the evidence section

| chapters | pairs | edges | OTHER | NO_RELATION | rejected |
|---|---|---|---|---|---|
| ch2-3 only | 542 | 238 | 115 | 133 | 46 |
| ch1-3 | 700 | 297 | 146 | 176 | 65 |
| ch1 only | 158 | 59 | 31 | 43 | 19 |

## 3. Estimated missed-relation rate (unselected sample)

14 of 50 randomly drawn unselected candidate pairs classify as accepted edges: **28.0% (95% Wilson 17.5-41.7%, n=50)**. Applied to 5215 unique candidates minus 700 selected, this is an estimate of edges the pair budget leaves out (sample outcomes are not in the graph).

## 4. Edges and domain/range rejections per relation

| relation | gate | accepted edges | domain/range rejections |
|---|---|---|---|
| part_of | legacy | 68 | 0 |
| is_a | legacy | 52 | 0 |
| uses | legacy | 41 | 2 |
| acts_on | core | 35 | 4 |
| requires | legacy | 28 | 0 |
| has_property | legacy | 19 | 5 |
| has_purpose | legacy | 17 | 18 |
| connected_to | core | 10 | 0 |
| causes | legacy | 9 | 2 |
| performs | legacy | 7 | 0 |
| increases | legacy | 4 | 1 |
| contrasts_with | legacy | 3 | 0 |
| equivalent_to | legacy | 3 | 0 |
| prevents | legacy | 1 | 0 |
| triggers | legacy | 0 | 2 |
| decreases | legacy | 0 | 1 |
| precedes | legacy | 0 | 1 |
| identifies |  | 0 | 9 |

By family: {'classification_structure': 149, 'mechanism_process': 42, 'function_means': 58, 'dependency': 28, 'comparison': 6, 'cause_effect': 14}. **mechanism_process edges: 42** (CR-005: 2; target >= 20).
Endpoint-grounding rejections: 20. Domain/range rejections: 45.

Generic `Concept` is a wildcard in the domain/range check (owner decision, 2026-10-01); the rejections above are specific wrong types only.

## 5. Linked share by strongest role (concept has >=1 typed edge)

| role | CR-005 | CR-007 |
|---|---|---|
| defined | 76 / 509 = 14.9% | 289 / 665 = 43.5% |
| refined | - | n/a |
| used | 21 / 159 = 13.2% | 78 / 211 = 37.0% |
| mentioned | 7 / 68 = 10.3% | 10 / 106 = 9.4% |
| all | 104 / 736 = 14.1% | 377 / 982 = 38.4% |

## 6. Late-counted edges

Edges whose evidence section is in an earlier chapter than an endpoint's first chapter: 0 of 297 (CR-005: 15 of 87 in ch2; target ~0).

## 7. Merges

1027 merge records; 24 needed an LLM call (non-trivial); 16 routed to review (similarity < 0.70, not merged); 521 different-type near-duplicates kept as `related`. Merge precision awaits the owner sheet.

## 8. Core-periphery (CR-006 check on the new graph)

- ch1: no clear core, rho 0.195; primary null delta 0.059 (z 1.6); second null delta 0.075 (z 2.4)
- ch2: no clear core, rho 0.091; primary null delta 0.005 (z 0.4); second null delta 0.011 (z 1.5)
- ch3: weak core, rho 0.096; primary null delta 0.030 (z 4.5); second null delta 0.012 (z 2.4)

## 9. Concept extraction (IIR, from STOP 2)

v2: lenient micro F1 0.433/0.444 (two executions of the test split); v3 (v2 + E3): 0.485 (see `reports/cr007_stop2_concepts.md`).
