# CR-017 STOP 1 — hierarchy gold audit (can the current gold support Ancestor Hierarchy F1 without inventing labels?)

Written for: Research. $0, no model call, no scorer change. Gold read: the frozen CR-012 P&D-E2E sheets `data/gold/pd_e2e_pilot_blind.csv` (sections 1.5, 2.6) and `pd_e2e_test_blind.csv` (4.4, 4.5, 5.4, 6.3, 7.1, 8.2, 9.3) through the CR-012 loader. Nothing was inferred from predicted graphs, chapter order, centrality, communities, tiers or embeddings. Script `src/cumap/cr017/stop1_audit.py`, data `reports/cr017/stop1_audit.json`.

## Verdict
**The gold explicitly contains hierarchy: 79 human-owned `is_a` edges in 8 of 9 sections, so Ancestor Hierarchy F1 is evaluable on P&D-E2E without any invented label. `HIERARCHY_GOLD_GAP` does not apply to P&D-E2E.** It does apply to SciNLP (see below). The metric is, however, *thin*: the evidence it can give is much weaker than the other four metrics (limits below).

## Relation inventory (registry v1.3)
`is_a` ("Source is a kind/subtype of target") is the only subsumption relation. The other `classification_structure` relations are `part_of`, `has_property` and `connected_to` (excluded by the spec). `instantiates` is **not** in the active registry (CR-004's patch was reserved and never applied). Canonicalisation's "narrower/broader" decisions (336 candidates in the production run) are review candidates, not edges, and are not part of any gold. Frozen hierarchy relation set proposed for CR-017: `{is_a}`.

## What the gold contains
| section | set | gold concepts | gold relation rows | is_a edges | ancestor pairs after closure | added by closure | max chain depth | cycle | example chain |
|---|---|---|---|---|---|---|---|---|---|
| 1.5 | pilot | 56 | 40 | 0 | 0 | 0 | 0 | False | – |
| 2.6 | pilot | 92 | 82 | 15 | 27 | 12 | 2 | False | Ethernet standard -> Ethernet -> bit-oriented framing protocol |
| 4.4 | heldout | 97 | 64 | 7 | 7 | 0 | 1 | False | – |
| 4.5 | heldout | 64 | 49 | 7 | 7 | 0 | 1 | False | – |
| 5.4 | heldout | 76 | 58 | 6 | 6 | 0 | 1 | False | – |
| 6.3 | heldout | 56 | 49 | 1 | 1 | 0 | 1 | False | – |
| 7.1 | heldout | 89 | 69 | 16 | 19 | 3 | 2 | False | structure -> flat type -> data type |
| 8.2 | heldout | 69 | 64 | 14 | 17 | 3 | 2 | False | SHA-3 -> Secure Hash Algorithm -> cryptographic hash |
| 9.3 | heldout | 88 | 79 | 13 | 18 | 5 | 2 | False | Domain Name System -> name service -> middleware |
| **total** | | 687 | 554 | **79** | **102** | 23 | | 0 | |

- Hierarchy gold exists in 8 of 9 sections (1.5 has none, 6.3 has one edge); `is_a` is 14% of the 554 gold relation rows and touches 122 of 687 gold concepts.
- **Transitive closure adds only 23 pairs** (29% over the direct edges); chains of depth ≥ 2 occur in 4 sections. So the ancestor formulation changes the score little on this gold, but it is well defined.
- **No cycles** in the gold. Predicted graphs can contain cycles; the cycle policy is therefore needed on the prediction side only (proposal: detect cycles, report each cycle, compute closure with a visited set so it cannot expand indefinitely, and leave the cycle's pairs in the prediction so they are judged against gold).
- Concept ids are **section-local**: hierarchy is only annotated inside a section; no cross-section ancestry exists, and closure is computed per section.
- The annotation instruction is "every relation the text supports". `is_a` is gold only when the section states it; true taxonomy that the text does not state (or states in another section) is unannotated. Consequence: **ancestor precision is understated** (a correct but unannotated ancestor counts as a false positive); recall against gold is unaffected.

## The predicted side (E0 runs; counts only, no hierarchy score computed)
| section | predicted edges | predicted is_a | …both endpoints mapped to gold concepts | gold is_a edges | …both endpoint nodes present | …pair reached the classifier |
|---|---|---|---|---|---|---|
| 1.5 | 27 | 0 | 0 | 0 | 0 | 0 |
| 2.6 | 17 | 3 | 2 | 15 | 13 | 3 |
| 4.4 | 23 | 8 | 6 | 7 | 5 | 1 |
| 4.5 | 15 | 4 | 2 | 7 | 7 | 1 |
| 5.4 | 27 | 5 | 2 | 6 | 5 | 1 |
| 6.3 | 26 | 8 | 5 | 1 | 1 | 0 |
| 7.1 | 28 | 7 | 2 | 16 | 13 | 1 |
| 8.2 | 30 | 6 | 6 | 14 | 14 | 2 |
| 9.3 | 25 | 9 | 5 | 13 | 9 | 2 |
| **total** | 218 | 50 | 30 | 79 | 67 | 11 |

At the frozen E0 workflow only 11 of 79 gold `is_a` edges (67 with both endpoint nodes present) even reach relation classification, so an E0 Ancestor Hierarchy F1 would be near zero and dominated by pair delivery, as the other relations are. The CR-012 oracle levels (E3/E4) are where the metric would separate classification quality from delivery.

## Statistical power
79 direct edges / 102 ancestor pairs over 9 sections (7 held-out sections only if the CR-012 held-out convention is kept: the held-out alone has 64 edges / 75 pairs). With fewer than 10 sections the section bootstrap is `NOT_EVALUABLE_SMALL_N` (CR-012 rule `MIN_UNITS_FOR_CI = 10`) and any interval is descriptive.

## SciNLP
SciNLP has `subclassOf` and `subtaskOf` relations but its gold is mention-level with **no identity clusters**, so there is no canonical concept to compute ancestors over: `ancestor_hierarchy_f1 = NOT_SUPPORTED_NO_IDENTITY_GOLD`, consistent with how CR-012 handled E2 on SciNLP. Hierarchy relations were not otherwise audited.

## RESEARCH DECISION REQUIRED
1. Approve `{is_a}` as the frozen hierarchy relation set (`instantiates` stays out; no other relation added).
2. Approve the cycle policy above, and per-section closure (concept ids are section-local).
3. Accept that Ancestor Hierarchy F1 is evaluable but descriptive-only (≤ 9 sections) and precision-biased by unannotated true ancestors; or order an optional, human-owned hierarchy annotation delta (child, parent, `is_a`, evidence sentence ids) to complete ancestry for existing gold concepts — not required to run the metric.
4. State whether the headline population is the 7 held-out sections only (CR-012 convention) or all 9 annotated sections; the 2 pilot sections are development data.
