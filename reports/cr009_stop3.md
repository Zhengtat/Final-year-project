# CR-009 STOP 3 — P&D ch. 1–3: CR-008 run `slice3_b4` vs CR-009 run `slice3_c1`

All numbers are computed from the saved runs; owner precision figures are pending the owner sheets.

## Concepts and mentions

| Metric | CR-008 run | CR-009 run |
|---|---|---|
| Concepts (nodes) | 913 | 1180 (v4 nodes 1230) |
| Existing mentions by `linked_by` | – | generator 1674, backfill 228 |
| Not-mentions by reason | – | {'different_sense': 736, 'inside_longer_term': 189, 'generic_use': 339} |
| `unconfirmed_mention` | – | 48 |
| Generator links: trivial / non-trivial (G-link) | – | 1460 / 214 |
| Canonicalisation LLM calls (R4) vs the CR-007 run | ≥ 236 (CR-007) | 315 recorded decisions |

## Anchors

- Anchored 706 vs independent 524 (57% anchored); by chapter: ch1: 182 / 206; ch2: 292 / 188; ch3: 232 / 130
- Anchor types: {'part_of': 63, 'used_for': 98, 'other': 91, 'property_of': 58, 'kind_of': 290, 'instance_of': 20, 'uses': 29, 'performed_by': 7, 'compared_with': 25, 'acts_on': 27, 'causes': 2, 'requires': 3}; `found_via_anchor`: 31; anchor records after canonicalisation: 713

## Verifier, backfill, pruner

- Units: 43; iterations histogram {0: 2, 1: 41}; stop reasons {'max_iterations': 41, 'correct': 2}; flags per rule {'F3': 385, 'C1': 43, 'F2': 171, 'C2': 1}; hints added / rejected 198 / 82; restored 224
- Backfill: 70 calls, 228 mentions added, 0 failed calls
- Pruner (P1, IIR-dev rows, out of domain on P&D; tau 0.1): 159 pruned (prune rate 11.4%), `pruned_defined` 31, attributes 0

## Linkage

| Metric | CR-008 run | CR-009 run |
|---|---|---|
| Linked share, all concepts / `defined` concepts | 39.5% / 44.9% | 28.6% / 40.6% |
| Late-counted edges (an endpoint first occurs after the edge's section) | 0 of 294 | 0 of 277 |
| Accepted edges | 294 | 277 |

## Anchor pairs through the relation stage

- Anchor pairs classified: 623; outcomes {'edge': 133, 'other': 95, 'no_relation': 192, 'rejected': 202, 'same_concept': 1}; **anchor → accepted-edge conversion 21.3%**; NO_RELATION rate 30.8%; anchor-type family agreement with the accepted relation's family 92/127 (72%).

## Sphere (ch3)

- Core–periphery: weak core (Δρ 0.043) → weak core (Δρ 0.032); core (centre+inner) name-matched Jaccard 0.19 (72 → 67 nodes); top-15 entered: ['bridge', 'data', 'device', 'header', 'link', 'path', 'sender']

## Misconception layer

- CR-008 run: {'candidates': 89, 'warnings': 2, 'not_warning': 75, 'needs_review': 1, 'needs_correct_edge': 10}; CR-009 run: {'candidates': 89, 'warnings': 3, 'not_warning': 77, 'needs_review': 0, 'needs_correct_edge': 9}

## Cost by task (CR-009 run, non-cached calls from the call log)

| task | USD |
|---|---|
| relation_choice | 2.814 |
| relation_family | 2.649 |
| canonicalize | 1.419 |
| relation_qualifiers | 0.900 |
| misconception_structuring | 0.689 |
| concept_generator | 0.296 |
| concept_backfill | 0.046 |
| **total** | **8.81** |

