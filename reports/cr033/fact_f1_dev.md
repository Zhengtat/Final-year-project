# CR-033 SciNLP concept-level fact F1 (`FACT-C1-SURF-R1`), dev split ($0, no model call)

Definition pre-registered in `docs/DECISIONS.md` (2026-10-23, CR-033) before any test figure. **`FACT-C1-SURF-R1` infers concept identity from strings (R1 name key plus acronym <-> long form within a paper).** It is a labelled companion score, not a headline candidate; `IDX-P1` strict relation F1 stays the headline and `IDX-P3` the upper bound.

## Determinism gate

| check | result |
|---|---|
| placed_path_equals_cr019_sc_score_per_document | PASS |

**Gate: PASSED.** Source hashes identical before and after: **True** (12 files).

## CR-019 dev runs `cr019dev` E0 (token matching)

Documents (6): 2021.acl-long.295, 2024.acl-long.144-1-9.grobid, P05-1008.grobid, P16-1007.grobid, P02-1004.grobid, P03-1014.grobid.

| variant | fact P / R / F1 | gold facts (mention-level relations) | predicted facts (synthetic concept) | unplaced as FP | TP facts whose own quote also matches a gold mention relation | strict mention-level relation F1 (beside) |
|---|---|---|---|---|---|---|
| `FROZEN` | 0.154 / 0.049 / **0.074** (tp 8, fp 44, fn 155) | 163 (179) | 52 (30) | 0 | 8 of 8 (1.000) | 0.069 (tp 8, fp 44, fn 171) |
| `IDX-P1` | 0.122 / 0.098 / **0.109** (tp 16, fp 115, fn 147) | 163 (179) | 125 (76) | 6 | 15 of 16 (0.938) | 0.096 (tp 15, fp 117, fn 164) |

## CR-021 dev rebuild `cr021dev` E0 (r1key matching)

Documents (6): 2021.acl-long.295, 2024.acl-long.144-1-9.grobid, P05-1008.grobid, P16-1007.grobid, P02-1004.grobid, P03-1014.grobid.

| variant | fact P / R / F1 | gold facts (mention-level relations) | predicted facts (synthetic concept) | unplaced as FP | TP facts whose own quote also matches a gold mention relation | strict mention-level relation F1 (beside) |
|---|---|---|---|---|---|---|
| `FROZEN` | 0.125 / 0.037 / **0.057** (tp 6, fp 42, fn 157) | 163 (179) | 48 (26) | 0 | 6 of 6 (1.000) | 0.053 (tp 6, fp 42, fn 173) |
| `IDX-P1` | 0.106 / 0.086 / **0.095** (tp 14, fp 118, fn 149) | 163 (179) | 120 (76) | 12 | 13 of 14 (0.929) | 0.083 (tp 13, fp 121, fn 166) |
| `IDXR1-P1` | 0.136 / 0.110 / **0.122** (tp 18, fp 114, fn 145) | 163 (179) | 126 (76) | 6 | 17 of 18 (0.944) | 0.109 (tp 17, fp 116, fn 162) |

## Limits

- Identity is inferred from strings: two different concepts with one R1 key collapse; one concept written two ways that R1 / acronym rules miss stays two nodes. Only the `SURF-R1` version exists (no identity sheet, owner decision).
- Predicted facts come from the placed mention-level relations, so an edge whose evidence quote cannot be placed is a false positive (rule 35) except in `FROZEN`.
- Dev has 6 and test 3 documents; no confidence interval is attempted. Dev and test are never pooled.
- The explorer scorecard and the presentation's metric definitions are not updated in this change.
