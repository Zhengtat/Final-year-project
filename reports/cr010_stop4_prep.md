# CR-010 STOP 4 — preparation (REL-MAP-180 frozen, pair pools enumerated; $0, no model call)

## REL-MAP-180 (built from run `slice3_c2`, registry `configs/relations_v1.3.yaml`)

| split | accepted edges | NO_RELATION | OTHER / near-miss | total | evidence sections |
|---|---|---|---|---|---|
| dev | 40 | 10 | 10 | 60 | 8 |
| test | 80 | 20 | 20 | 120 | 16 |

- Split by whole evidence section (seed 20261005, split seed used 20261005); **leakage check: PASS** (shared evidence sections 0, shared concept pairs 0, duplicate item ids 0).
- OTHER / near-miss = `other` outcomes (24) plus registry domain/range rejections (6); `endpoint_not_grounded` rejections are extraction defects and are not used.
- Frozen: blind sheet sha256 `cc93c48edb8d339d`, manifest sha256 `71290f188fc72250`. The manifest (model fields, split, concept order) is `cr010_relmap180_MANIFEST_KEY_DO_NOT_SHARE.csv` and is not shown to an annotator; the NOT-GOLD mapping table was not read.
- Item order and the order of concept A/B are randomised; strata and split are not recoverable from the sheet.
- Double annotation: not available (no second annotator): kappa is not measured.

### Accepted edges per relation (the pool is relation-balanced, not proportional)

| relation | dev | test |
|---|---|---|
| uses | 4 | 10 |
| acts_on | 5 | 8 |
| has_purpose | 3 | 10 |
| requires | 4 | 9 |
| part_of | 4 | 8 |
| is_a | 4 | 7 |
| has_property | 4 | 7 |
| connected_to | 2 | 7 |
| performs | 5 | 3 |
| increases | 2 | 2 |
| causes | 0 | 4 |
| decreases | 1 | 2 |
| precedes | 1 | 1 |
| contrasts_with | 0 | 2 |
| prevents | 1 | 0 |

## Pair pools (P0-P2 enumerated; P3 needs the eRST graph)

| pool | pairs | note |
|---|---|---|
| P0 (frozen CR-009 selection) | 1100 | reproduces the recorded 8604 same-sentence candidates exactly; 226 P0 pairs are anchor-derived and outside the same-sentence universe |
| P1 extra (same-sentence pairs the budget left out) | 7680 | classifying all of them would cost about $63.7 |
| P2 extra, strict cue (proposed) | 2324 | adjacent-sentence pairs with a relation-bearing cue; about $19.3 in full |
| P2 extra, loose cue (the frozen substring cue) | 7460 | not selective, shown for reference |
| adjacent-sentence pairs in all | 7934 | |

### Indication of P0's pair recall (unvalidated, from the CR-007 random sample of unselected pairs)

- Of 50 randomly sampled UNSELECTED same-sentence pairs, 20 were accepted as edges by the classifier: yield 40% (Wilson 95% [28%, 54%]), against 529 accepted edges among the 1100 selected pairs.
- Projected onto the 7504 unselected pairs: about 3002 further classifier-accepted edges (range 2072-4039), i.e. P0 would reach about **15%** (range 12%-20%) of the classifier-accepted same-sentence edges.
- **Caveats:** n = 50; classifier-accepted, not owner-validated (the selected set's owner-measured edge precision was about 90%; the unselected share has not been checked); same-sentence pairs only.

## Points Research needs to settle (not implementation choices)

1. **P1 definition.** The same-sentence enumeration is already complete, so I read P1 as 'P0 plus the same-sentence pairs the budget left out'. If P1 meant a different enumeration (clause-level co-mentions, mentions via unrecorded aliases), it needs a definition.
2. **P2 'high-confidence' cue.** The frozen cue test is a substring match, so 'for' fires inside 'information' and 'so' inside 'also': 71.7% of all P&D sentences count as cue sentences (54.0% with word boundaries). I propose word-boundary matching with function words removed (list in `data/interim/checks/cr010_pair_pools_summary.json`); P0 itself is not changed.
3. **'Sufficiently represented' relation** (gate: recall >= 0.75 per relation). With a relation-balanced test sample, 8 of 15 relations have at least 5 test items; a threshold is needed.

## Human steps

1. **Annotate the 180 rows** in `data/interim/checks/cr010_relmap180_blind_sheet.csv` following `docs/cr010/RELMAP180_ANNOTATION_GUIDE.md`; save your copy to `data/gold/cr010_relmap180_blind_sheet_annotator1.csv` (code never writes there). Check it with `uv run python -m cumap.cr010.relmap validate --sheet <your file>`.
2. **Approve the pair-recall sampling** (below), then validate the accepted edges the extra pools produce.

