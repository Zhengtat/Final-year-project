# CR-007 STOP 4: CR-005 vs CR-007 on P&D ch1-3

Generated read-only from run `slice3_a1`; no API calls. CR-005 numbers are the STOP 1 diagnostics (b) baselines (ch2-3 slice).

## 1. Relation outcomes of the pairs classified

| outcome | CR-005 (381 pairs, ch2-3) | CR-007 (700 pairs, ch1-3) |
|---|---|---|
| edge accepted | 121 / 381 = 31.8% | 252 / 700 = 36.0% |
| OTHER | 117 / 381 = 30.7% | 146 / 700 = 20.9% |
| NO_RELATION | 143 / 381 = 37.5% | 176 / 700 = 25.1% |
| rejected by a check | - | 126 / 700 = 18.0% |

Rejection reasons: {'domain_range': 106, 'endpoint_not_grounded': 20}. OTHER share among pairs that passed the checks: 146 / 574 = 25.4%.
Target in the CR: OTHER <= 15%. Measured 20.9% of all pairs (25.4% of pairs not rejected).

## 2. Selection effect vs classifier effect

- **Selection effect (attempted coverage):** concepts with >=1 classified pair: 805 of 982 concepts (CR-005: 152 of 736). Defined/used concepts attempted: 786 / 876 = 89.7%.
- **Classifier effect (accepted rate among attempted pairs):** 252 / 700 = 36.0% (CR-005 121 / 381 = 31.8%).

### By chapter of the evidence section

| chapters | pairs | edges | OTHER | NO_RELATION | rejected |
|---|---|---|---|---|---|
| ch2-3 only | 542 | 208 | 115 | 133 | 86 |
| ch1-3 | 700 | 252 | 146 | 176 | 126 |
| ch1 only | 158 | 44 | 31 | 43 | 40 |

## 3. Estimated missed-relation rate (unselected sample)

13 of 50 randomly drawn unselected candidate pairs classify as accepted edges: **26.0% (95% Wilson 15.9-39.6%, n=50)**. Applied to 5215 unique candidates minus 700 selected, this is an estimate of edges the pair budget leaves out (sample outcomes are not in the graph).

## 4. Edges and domain/range rejections per relation

| relation | gate | accepted edges | domain/range rejections |
|---|---|---|---|
| part_of | legacy | 68 | 0 |
| is_a | legacy | 52 | 0 |
| requires | legacy | 28 | 0 |
| uses | legacy | 26 | 17 |
| acts_on | core | 24 | 15 |
| has_property | legacy | 15 | 9 |
| connected_to | core | 10 | 0 |
| has_purpose | legacy | 10 | 25 |
| identifies | gated | 5 | 17 |
| contrasts_with | legacy | 3 | 0 |
| equivalent_to | legacy | 3 | 0 |
| causes | legacy | 2 | 9 |
| increases | legacy | 2 | 3 |
| prevents | legacy | 1 | 0 |
| performs | legacy | 1 | 6 |
| encapsulates | gated | 1 | 1 |
| trades_off_with | gated | 1 | 0 |
| decreases | legacy | 0 | 1 |
| triggers | legacy | 0 | 2 |
| precedes | legacy | 0 | 1 |

By family: {'classification_structure': 151, 'mechanism_process': 25, 'function_means': 36, 'dependency': 28, 'comparison': 7, 'cause_effect': 5}. **mechanism_process edges: 25** (CR-005: 2; target >= 20).
Endpoint-grounding rejections: 20. Domain/range rejections: 106.

Finding: 76 of 106 domain/range rejections have an endpoint typed generic `Concept`, which most v1.1 domains/ranges exclude. Owner decision needed (see STOP 4 questions), not changed here.

## 5. Linked share by strongest role (concept has >=1 typed edge)

| role | CR-005 | CR-007 |
|---|---|---|
| defined | 76 / 509 = 14.9% | 259 / 665 = 38.9% |
| refined | - | n/a |
| used | 21 / 159 = 13.2% | 63 / 211 = 29.9% |
| mentioned | 7 / 68 = 10.3% | 8 / 106 = 7.5% |
| all | 104 / 736 = 14.1% | 330 / 982 = 33.6% |

## 6. Late-counted edges

Edges whose evidence section is in an earlier chapter than an endpoint's first chapter: 0 of 252 (CR-005: 15 of 87 in ch2; target ~0).

## 7. corrects_intuition edges

- 3.3: network -[has_property]-> maximum transmission unit; intuition: The maximum transmission unit is the largest packet size on the network.; quote: "every network type has a maximum transmission unit (MTU)"

## 8. Merges

1027 merge records; 24 needed an LLM call (non-trivial); 16 routed to review (similarity < 0.70, not merged); 521 different-type near-duplicates kept as `related`. Merge precision awaits the owner sheet.

## 9. Core-periphery (CR-006 check on the new graph)

- ch1: no clear core, rho 0.070; primary null delta -0.064 (z -1.4); second null delta -0.004 (z -0.2)
- ch2: no clear core, rho 0.072; primary null delta -0.014 (z -0.9); second null delta 0.004 (z 0.4)
- ch3: weak core, rho 0.098; primary null delta 0.026 (z 3.2); second null delta 0.013 (z 2.3)

## 10. Concept extraction (IIR, from STOP 2)

v2: lenient micro F1 0.433/0.444 (two executions of the test split); v3 (v2 + E3): 0.485 (see `reports/cr007_stop2_concepts.md`).
