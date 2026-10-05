# CR-009 STOP 3 — P&D ch. 1–3: CR-008 run `slice3_b4` vs CR-009 run `slice3_c2`

All numbers are computed from the saved runs; owner precision figures are pending the owner sheets.

## Concepts and mentions

| Metric | CR-008 run | CR-009 run |
|---|---|---|
| Concepts (nodes) | 913 | 1243 (v4 nodes 1275) |
| Existing mentions by `linked_by` | – | generator 1684, backfill 234 |
| Not-mentions by reason | – | {'inside_longer_term': 238, 'generic_use': 223, 'different_sense': 717} |
| `unconfirmed_mention` | – | 42 |
| Generator links: trivial / non-trivial (G-link) | – | 1668 / 16 |
| Canonicalisation LLM calls (R4) vs the CR-007 run | ≥ 236 (CR-007) | 362 recorded decisions |

## Anchors

- Anchored 733 vs independent 542 (57% anchored); by chapter: ch1: 214 / 226; ch2: 263 / 183; ch3: 256 / 133
- Anchor types: {'kind_of': 288, 'performed_by': 14, 'used_for': 86, 'other': 109, 'property_of': 66, 'part_of': 85, 'acts_on': 18, 'uses': 37, 'compared_with': 24, 'causes': 6, 'instance_of': 12, 'requires': 1}; `found_via_anchor`: 42; anchor records after canonicalisation: 746

## Verifier, backfill, pruner

- Units: 43; iterations histogram {0: 1, 1: 42}; stop reasons {'max_iterations': 42, 'correct': 1}; flags per rule {'F3': 395, 'F2': 146, 'C1': 51, 'C2': 4}; hints added / rejected 266 / 77; restored 198
- Backfill: 69 calls, 234 mentions added, 0 failed calls
- Pruner (P1, IIR-dev rows, out of domain on P&D; tau 0.1): 0 pruned (prune rate 0.0%), `pruned_defined` 0, attributes 0

## Linkage

| Metric | CR-008 run | CR-009 run |
|---|---|---|
| Linked share, all concepts / `defined` concepts | 39.5% / 44.9% | 48.1% / 56.2% |
| Late-counted edges (an endpoint first occurs after the edge's section) | 0 of 294 | 0 of 529 |
| Accepted edges | 294 | 529 |

## Anchor pairs through the relation stage

- Anchor pairs classified: 647; outcomes {'edge': 341, 'other': 102, 'no_relation': 136, 'rejected': 67, 'same_concept': 1}; **anchor → accepted-edge conversion 52.7%**; NO_RELATION rate 21.0%; anchor-type family agreement with the accepted relation's family 281/317 (89%).

## Sphere (ch3)

- Core–periphery: weak core (Δρ 0.043) → weak core (Δρ 0.035); core (centre+inner) name-matched Jaccard 0.19 (72 → 120 nodes); top-15 entered: ['data', 'header', 'link', 'path']

## Misconception layer

- CR-008 run: {'candidates': 89, 'warnings': 2, 'not_warning': 75, 'needs_review': 1, 'needs_correct_edge': 10}; CR-009 run: {'candidates': 89, 'warnings': 4, 'not_warning': 75, 'needs_review': 0, 'needs_correct_edge': 10}

## Cost by task (CR-009 run, non-cached calls from the call log)

| task | USD |
|---|---|
| relation_choice | 2.783 |
| canonicalize | 2.491 |
| relation_family | 2.197 |
| relation_qualifiers | 1.479 |
| misconception_structuring | 0.713 |
| concept_generator | 0.539 |
| concept_backfill | 0.089 |
| **total** | **10.29** |

## Owner marks after the fixes (`slice3_c2`; read from `data/gold/`, split by the hidden keys)

### Concepts (30)

- **Valid complete concept: 22/30 = 73% (Wilson 95% [0.56, 0.86])** (first run, 40 sampled: 25/40 = 62%); verdicts {'valid complete': 22, 'generic': 6, 'partial': 2}

| stratum | n | valid complete |
|---|---|---|
| independent | 11 | 4/11 = 36% (Wilson 95% [0.15, 0.65]) |
| anchored | 14 | 13/14 = 93% (Wilson 95% [0.69, 0.99]) |
| found_via_anchor | 5 | 5/5 = 100% (Wilson 95% [0.57, 1.00]) |

- **Anchor correct: 18/18 = 100% (Wilson 95% [0.82, 1.00])** (first run: 17/21 = 81%)

### Non-trivial generator links (all that remain after the strict rule)

- **Same sense: 16/16 = 100% (Wilson 95% [0.81, 1.00])** (first run: 4/15 = 27%)

### Edges (30: 15 anchor-derived, 15 other)

- **Strict edge precision (relation and direction right): 27/30 = 90% (Wilson 95% [0.74, 0.97])** (CR-007 spot-check: 29/39 = 74%, CR-005: 23/30 = 77%); verdicts {'correct': 27, 'wrong direction': 1, 'not supported': 1, 'wrong relation': 1}
- anchor-derived 15/15 = 100% (Wilson 95% [0.80, 1.00]); other 12/15 = 80% (Wilson 95% [0.55, 0.93])
- errors: wrong direction (has_property); not supported (is_a); wrong relation (part_of)

