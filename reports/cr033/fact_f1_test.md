# CR-033 SciNLP concept-level fact F1 (`FACT-C1-SURF-R1`), test split ($0, no model call)

Definition pre-registered in `docs/DECISIONS.md` (2026-10-23, CR-033) before any test figure. **`FACT-C1-SURF-R1` infers concept identity from strings (R1 name key plus acronym <-> long form within a paper).** It is a labelled companion score, not a headline candidate; `IDX-P1` strict relation F1 stays the headline and `IDX-P3` the upper bound.

## Determinism gate

| check | result |
|---|---|
| A1_all_labels_equals_cr019_per_document_for_all_three_variants | PASS |
| frozen_strict_relation_micro_equals_cr012_json | PASS |
| idx_p1_micro_equals_cr019_stage_a_json | PASS |
| frozen_concept_f1_0.352 | PASS |
| frozen_pair_recall_0.545 | PASS |
| frozen_strict_edge_f1_0.050 | PASS |
| idx_p1_f1_0.195 | PASS |

**Gate: PASSED.** Source hashes identical before and after: **True** (15 files).

## frozen CR-012 STOP 4 E0 (token matching)

Documents (3): 2021.acl-long.353, 2024.acl-long.108-1-9.grobid, P17-1058.grobid.

| variant | fact P / R / F1 | gold facts (mention-level relations) | predicted facts (synthetic concept) | unplaced as FP | TP facts whose own quote also matches a gold mention relation | strict mention-level relation F1 (beside) |
|---|---|---|---|---|---|---|
| `FROZEN` | 0.429 / 0.043 / **0.078** (tp 9, fp 12, fn 202) | 211 (295) | 21 (5) | 0 | 8 of 9 (0.889) | 0.050 (tp 8, fp 14, fn 287) |
| `IDX-P1` | 0.473 / 0.251 / **0.328** (tp 53, fp 59, fn 158) | 211 (295) | 108 (29) | 4 | 40 of 53 (0.755) | 0.195 (tp 40, fp 75, fn 255) |
| `IDX-P3` | 0.478 / 0.261 / **0.337** (tp 55, fp 60, fn 156) | 211 (295) | 110 (29) | 5 | 53 of 55 (0.964) | 0.332 (tp 91, fp 162, fn 204) |

## CR-021 rebuild `cr021test` E0 (r1key matching)

Documents (3): 2021.acl-long.353, 2024.acl-long.108-1-9.grobid, P17-1058.grobid.

| variant | fact P / R / F1 | gold facts (mention-level relations) | predicted facts (synthetic concept) | unplaced as FP | TP facts whose own quote also matches a gold mention relation | strict mention-level relation F1 (beside) |
|---|---|---|---|---|---|---|
| `FROZEN` | 0.304 / 0.033 / **0.060** (tp 7, fp 16, fn 204) | 211 (295) | 23 (8) | 0 | 7 of 7 (1.000) | 0.044 (tp 7, fp 17, fn 288) |
| `IDX-P1` | 0.376 / 0.194 / **0.256** (tp 41, fp 68, fn 170) | 211 (295) | 101 (33) | 8 | 29 of 41 (0.707) | 0.143 (tp 29, fp 83, fn 266) |
| `IDXR1-P1` | 0.385 / 0.199 / **0.263** (tp 42, fp 67, fn 169) | 211 (295) | 106 (33) | 3 | 30 of 42 (0.714) | 0.147 (tp 30, fp 83, fn 265) |

## frozen CR-012 oracle E1 (token matching)

Documents (3): 2021.acl-long.353, 2024.acl-long.108-1-9.grobid, P17-1058.grobid.

| variant | fact P / R / F1 | gold facts (mention-level relations) | predicted facts (synthetic concept) | unplaced as FP | TP facts whose own quote also matches a gold mention relation | strict mention-level relation F1 (beside) |
|---|---|---|---|---|---|---|
| `FROZEN` | 0.789 / 0.265 / **0.397** (tp 56, fp 15, fn 155) | 211 (295) | 71 (0) | 0 | 47 of 56 (0.839) | 0.255 (tp 47, fp 27, fn 248) |
| `IDX-P1` | 0.630 / 0.299 / **0.405** (tp 63, fp 37, fn 148) | 211 (295) | 99 (0) | 1 | 47 of 63 (0.746) | 0.236 (tp 47, fp 56, fn 248) |

## frozen CR-012 oracle E3-M (token matching)

Documents (3): 2021.acl-long.353, 2024.acl-long.108-1-9.grobid, P17-1058.grobid.

| variant | fact P / R / F1 | gold facts (mention-level relations) | predicted facts (synthetic concept) | unplaced as FP | TP facts whose own quote also matches a gold mention relation | strict mention-level relation F1 (beside) |
|---|---|---|---|---|---|---|
| `FROZEN` | 0.872 / 0.517 / **0.649** (tp 109, fp 16, fn 102) | 211 (295) | 125 (0) | 0 | 96 of 109 (0.881) | 0.463 (tp 100, fp 37, fn 195) |
| `IDX-P1` | 0.742 / 0.531 / **0.619** (tp 112, fp 39, fn 99) | 211 (295) | 144 (0) | 7 | 96 of 112 (0.857) | 0.433 (tp 100, fp 67, fn 195) |

## frozen CR-012 oracle E4-M (token matching)

Documents (3): 2021.acl-long.353, 2024.acl-long.108-1-9.grobid, P17-1058.grobid.

| variant | fact P / R / F1 | gold facts (mention-level relations) | predicted facts (synthetic concept) | unplaced as FP | TP facts whose own quote also matches a gold mention relation | strict mention-level relation F1 (beside) |
|---|---|---|---|---|---|---|
| `FROZEN` | 0.893 / 0.512 / **0.651** (tp 108, fp 13, fn 103) | 211 (295) | 121 (0) | 0 | 96 of 108 (0.889) | 0.473 (tp 100, fp 28, fn 195) |
| `IDX-P1` | 0.868 / 0.531 / **0.659** (tp 112, fp 17, fn 99) | 211 (295) | 127 (0) | 2 | 96 of 112 (0.857) | 0.462 (tp 100, fp 38, fn 195) |

## Limits

- Identity is inferred from strings: two different concepts with one R1 key collapse; one concept written two ways that R1 / acronym rules miss stays two nodes. Only the `SURF-R1` version exists (no identity sheet, owner decision).
- Predicted facts come from the placed mention-level relations, so an edge whose evidence quote cannot be placed is a false positive (rule 35) except in `FROZEN`.
- Dev has 6 and test 3 documents; no confidence interval is attempted. Dev and test are never pooled.
- The explorer scorecard and the presentation's metric definitions are not updated in this change.
