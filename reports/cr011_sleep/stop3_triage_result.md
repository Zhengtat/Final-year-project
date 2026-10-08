# CR-011 revised STOP 3 - local review-ranking result (2026-10-09, $0, no paid call)

Definitions: `docs/cr011/STOP3_REVISED_PREREGISTRATION.md` (committed before any score on the dev labels). Dev sets kept separate: SLEEP-240 {'NOT_SAME': 75, 'SAME': 3, 'UNSURE': 2}, SLEEP-POS {'NOT_SAME': 71, 'SAME': 8, 'UNSURE': 1}. MUST_REVIEW = 14 (SAME or UNSURE). Eligible universe = 13394 candidate pairs surviving the hard guards.

## Result against the Research continuation gate

**No configuration reaches ReviewRecall = 1.00. The gate (ReviewReduction >= 25% AND ReviewRecall = 1.00) is NOT passed; per the Research rule CR-011 stops after STOP 3 with NO PRODUCTION CHANGE, and no paid call is made.**

| configuration | ReviewRecall | ReviewReduction (primary, whole eligible universe) | dev-item reduction (secondary) | out-of-fold AUC |
|---|---:|---:|---:|---:|
| single:name_cos | 0.929 | 8.8% | 2.2% | 0.54 |
| single:char_ratio | 0.929 | 40.1% | 5.9% | 0.53 |
| single:token_jaccard | 0.929 | 0.0% | 0.0% | 0.43 |
| single:def_cos | 0.929 | 0.0% | 0.0% | 0.41 |
| single:ev_cos | 0.929 | 46.8% | 5.9% | 0.40 |
| single:max_sim | 0.929 | 15.6% | 0.0% | 0.55 |
| lr_similarity | 0.929 | 4.6% | 14.7% | 0.55 |
| lr_all | 0.929 | 1.0% | 1.5% | 0.41 |
| gb_all | 0.929 | 0.0% | 0.0% | 0.43 |

## Why recall is capped at 13/14 for every configuration

SL080 (SLEEP-240 dev, gold SAME, preferred form "electromagnetic spectrum"): "spectrum" is typed `Parameter`, "electromagnetic spectrum" is typed `Concept`. The frozen type map (Research 2026-10-08) lists Parameter-Property but not Parameter-Concept, so the pair is vetoed by a hard guard before any ranking and can never reach review. No model can fix that; it is a conflict between two Research rulings (type incompatibility is a VETO; all 14 dev MUST_REVIEW items must stay in the queue). The other 13 are in the candidate pool and guard-eligible (13 of 14).

## Diagnostics Research should see before accepting the closure

1. **The rankers do not separate duplicates from related-but-distinct pairs.** Out-of-fold AUC for the target MUST_REVIEW is 0.40-0.55 for all nine configurations (logistic and boosted included); the 13 eligible positives span name similarity from 0.15 and token overlap 0 upward, so a threshold that keeps all of them sits very low.
2. **The larger "reductions" are artefacts.** `single:ev_cos` (46.8%) and `single:char_ratio` (40.1%) have AUC 0.40 and 0.53: their threshold lands above most of the whole pool simply because the dev items were sampled for high similarity, so the lowest positive is high relative to the mostly dissimilar pool. They do not show that duplicates can be told apart. The dev-item reduction (secondary) is 0-15%.
3. **Under a reading that ignores the type-vetoed item (recall over the 13 eligible items),** the maximum primary reduction is `single:ev_cos` at 46.8% with AUC 0.40; applying the literal 25% gate to that would pass a configuration that is no better than chance. This is why the pre-registered continuation gate should not be read as evidence of triage value here.

## Reading

After the online canonicalisation, the CR-008 rules and the CR-009 links, the local features available to sleep (lexical, embedding, type, graph, chapter, eRST context) do not rank the remaining true duplicates above the related-but-distinct pairs well enough to cut human review. Consistent with the earlier STOP-2 finding, the residual duplicates are rare and look like their near neighbours.

## Status and what is outstanding

- STOP 3 outcome: gate not passed. CR-011 stops here under the Research rule; recorded as NO PRODUCTION CHANGE. S-AGG not run. No paid LLM arm was run. No threshold, arm or gate was changed.
- For Research to confirm (one line each): (a) accept closure on the literal rule; or (b) amend the type guard for human-gated review so a type-incompatible pair can be routed to a "type-mismatch review" queue rather than vetoed (a Research change to the type rule that the 2026-10-08 ruling froze); (c) note that diagnostic 2-3 apply to any amended reading.
- If closure is confirmed, the CR-012 handoff records `sleep_adopted = false`. STOP 4 (held-out) and STOP 5 (MergeTransaction/rollback rehearsal) are not run; the held-out sets stay sealed and unopened.
