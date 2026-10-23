# CR-022 Part A: SciNLP hierarchy and relation scoring ($0, no model call)

Written for: the project owner and Research. Part A only (Part B is not approved and was not run).

Dataset release `SciNLP-repo-e78342be`. Scorer: frozen CR-012 strict mention-level scorer (`cumap.cr012.scoring.score_scinlp_unit`), CR-017 `ancestor_closure` and `macro_from_rows`, CR-019 occurrence index; new code in `src/cumap/cr022/`. Every figure names its grounding variant; none replaces a frozen number.

Grounding variants: `FROZEN` = frozen CR-012 grounding; unplaced edges excluded (as in the frozen number); `FROZEN-UNPLACED-FP` = frozen grounding; each unplaced edge counts as a false positive; `IDX-P1` = CR-019 occurrence index, own-evidence-sentence placement (primary); unplaced = FP; `IDXR1-P1` = as IDX-P1 with CR-020 R1-key matching (the mode the CR-021 rebuild ran under); unplaced = FP.

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

**Gate: PASSED.** Source hashes identical before and after: **True** (20 files).

Hierarchy label sets (owner decision at STOP 1, both shown): `H2 {subclassOf, subtaskOf}` is the spec default; `H1 {subclassOf}` only. `partOf` is excluded from both, as CR-017 uses `{is_a}` only.

Reading note: the frozen SciNLP strict relation number is mention level and the occurrence index changes only which mentions a node owns; no number here is an official SciNLP score.

## TEST · frozen CR-012 STOP 4 (token matching)

Documents (3): 2021.acl-long.353, 2024.acl-long.108-1-9.grobid, P17-1058.grobid.

### Frozen / CR-019 reference: strict relation P / R / F1, all labels

| variant | P / R / F1 |
|---|---|
| `FROZEN` | 0.364 / 0.027 / **0.050** (tp 8, fp 14, fn 287) |
| `FROZEN-UNPLACED-FP` | 0.071 / 0.027 / **0.039** (tp 8, fp 105, fn 287) |
| `IDX-P1` | 0.348 / 0.136 / **0.195** (tp 40, fp 75, fn 255) |

### A1 HIER-DIRECT, H2 {subclassOf, subtaskOf}: direct hierarchy edge P / R / F1 (gold relations in set: 46)

| variant | P / R / F1 |
|---|---|
| `FROZEN` | 0.125 / 0.022 / **0.037** (tp 1, fp 7, fn 45) |
| `FROZEN-UNPLACED-FP` | 0.043 / 0.022 / **0.029** (tp 1, fp 22, fn 45) |
| `IDX-P1` | 0.167 / 0.087 / **0.114** (tp 4, fp 20, fn 42) |

### A2 HIER-ANC-SURF, H2 {subclassOf, subtaskOf}: ancestor hierarchy on surface pseudo-nodes (labelled variant, infers identity from strings; not a headline)

| variant | P / R / F1 | gold direct edges -> closure pairs | pred direct -> closure | gold mentions -> surface nodes | unplaced as FP |
|---|---|---|---|---|---|
| `FROZEN` | 0.125 / 0.026 / **0.043** (tp 1, fp 7, fn 38) | 38 -> 39 (+1) | 8 -> 8 | 765 -> 238 (collisions 527) | 0 |
| `FROZEN-UNPLACED-FP` | 0.043 / 0.026 / **0.032** (tp 1, fp 22, fn 38) | 38 -> 39 (+1) | 8 -> 8 | 765 -> 238 (collisions 527) | 15 |
| `IDX-P1` | 0.208 / 0.128 / **0.159** (tp 5, fp 19, fn 34) | 38 -> 39 (+1) | 22 -> 22 | 765 -> 238 (collisions 527) | 2 |

Cycles detected: none.

### A1 HIER-DIRECT, H1 {subclassOf}: direct hierarchy edge P / R / F1 (gold relations in set: 31)

| variant | P / R / F1 |
|---|---|
| `FROZEN` | 0.125 / 0.032 / **0.051** (tp 1, fp 7, fn 30) |
| `FROZEN-UNPLACED-FP` | 0.056 / 0.032 / **0.041** (tp 1, fp 17, fn 30) |
| `IDX-P1` | 0.211 / 0.129 / **0.160** (tp 4, fp 15, fn 27) |

### A2 HIER-ANC-SURF, H1 {subclassOf}: ancestor hierarchy on surface pseudo-nodes (labelled variant, infers identity from strings; not a headline)

| variant | P / R / F1 | gold direct edges -> closure pairs | pred direct -> closure | gold mentions -> surface nodes | unplaced as FP |
|---|---|---|---|---|---|
| `FROZEN` | 0.125 / 0.033 / **0.053** (tp 1, fp 7, fn 29) | 29 -> 30 (+1) | 8 -> 8 | 765 -> 238 (collisions 527) | 0 |
| `FROZEN-UNPLACED-FP` | 0.056 / 0.033 / **0.042** (tp 1, fp 17, fn 29) | 29 -> 30 (+1) | 8 -> 8 | 765 -> 238 (collisions 527) | 10 |
| `IDX-P1` | 0.263 / 0.167 / **0.204** (tp 5, fp 14, fn 25) | 29 -> 30 (+1) | 17 -> 17 | 765 -> 238 (collisions 527) | 2 |

Cycles detected: none.

### A3 REL-MACRO-SCINLP: relation macro F1 (gold relations whose two endpoints are predicted mentions)

| variant | macro F1 | classes in macro | population | micro F1 | direction accuracy given correct label | no edge at pair |
|---|---|---|---|---|---|---|
| `FROZEN` | **0.333** | 8 | 33 | 0.364 | 1.000 | 22 |
| `FROZEN-UNPLACED-FP` | **0.333** | 8 | 33 | 0.364 | 1.000 | 22 |
| `IDX-P1` | **0.317** | 10 | 184 | 0.349 | 1.000 | 139 |

Per-class support (variant `IDX-P1`; `low` = support of 3 or fewer):

| label | support | tp | fp | fn | P | R | F1 | low |
|---|---|---|---|---|---|---|---|---|
| MeasuredBy | 8 | 3 | 0 | 5 | 1.000 | 0.375 | 0.545 |  |
| UsedFor | 46 | 14 | 0 | 32 | 1.000 | 0.304 | 0.467 |  |
| compareWith | 29 | 5 | 1 | 24 | 0.833 | 0.172 | 0.286 |  |
| enhancedBy | 33 | 7 | 0 | 26 | 1.000 | 0.212 | 0.350 |  |
| evaluatedBy | 6 | 3 | 0 | 3 | 1.000 | 0.500 | 0.667 |  |
| evaluatedOn | 15 | 3 | 0 | 12 | 1.000 | 0.200 | 0.333 |  |
| partOf | 2 | 0 | 1 | 2 | 0.000 | 0.000 | 0.000 | low |
| similarWith | 12 | 0 | 0 | 12 | n/a | 0.000 | 0.000 |  |
| subclassOf | 27 | 4 | 3 | 23 | 0.571 | 0.148 | 0.235 |  |
| trainedWith | 6 | 1 | 0 | 5 | 1.000 | 0.167 | 0.286 |  |

## TEST · CR-021 rebuild `cr021test` (r1key matching)

Documents (3): 2021.acl-long.353, 2024.acl-long.108-1-9.grobid, P17-1058.grobid.

### Frozen / CR-019 reference: strict relation P / R / F1, all labels

| variant | P / R / F1 |
|---|---|
| `FROZEN` | 0.292 / 0.024 / **0.044** (tp 7, fp 17, fn 288) |
| `FROZEN-UNPLACED-FP` | 0.064 / 0.024 / **0.035** (tp 7, fp 102, fn 288) |
| `IDX-P1` | 0.259 / 0.098 / **0.143** (tp 29, fp 83, fn 266) |
| `IDXR1-P1` | 0.265 / 0.102 / **0.147** (tp 30, fp 83, fn 265) |

### A1 HIER-DIRECT, H2 {subclassOf, subtaskOf}: direct hierarchy edge P / R / F1 (gold relations in set: 46)

| variant | P / R / F1 |
|---|---|
| `FROZEN` | 0.000 / 0.000 / **0.000** (tp 0, fp 7, fn 46) |
| `FROZEN-UNPLACED-FP` | 0.000 / 0.000 / **0.000** (tp 0, fp 19, fn 46) |
| `IDX-P1` | 0.050 / 0.022 / **0.030** (tp 1, fp 19, fn 45) |
| `IDXR1-P1` | 0.095 / 0.043 / **0.060** (tp 2, fp 19, fn 44) |

### A2 HIER-ANC-SURF, H2 {subclassOf, subtaskOf}: ancestor hierarchy on surface pseudo-nodes (labelled variant, infers identity from strings; not a headline)

| variant | P / R / F1 | gold direct edges -> closure pairs | pred direct -> closure | gold mentions -> surface nodes | unplaced as FP |
|---|---|---|---|---|---|
| `FROZEN` | 0.000 / 0.000 / **0.000** (tp 0, fp 7, fn 39) | 38 -> 39 (+1) | 7 -> 7 | 765 -> 238 (collisions 527) | 0 |
| `FROZEN-UNPLACED-FP` | 0.000 / 0.000 / **0.000** (tp 0, fp 19, fn 39) | 38 -> 39 (+1) | 7 -> 7 | 765 -> 238 (collisions 527) | 12 |
| `IDX-P1` | 0.100 / 0.051 / **0.068** (tp 2, fp 18, fn 37) | 38 -> 39 (+1) | 18 -> 18 | 765 -> 238 (collisions 527) | 2 |
| `IDXR1-P1` | 0.143 / 0.077 / **0.100** (tp 3, fp 18, fn 36) | 38 -> 39 (+1) | 21 -> 21 | 765 -> 238 (collisions 527) | 0 |

Cycles detected: none.

### A1 HIER-DIRECT, H1 {subclassOf}: direct hierarchy edge P / R / F1 (gold relations in set: 31)

| variant | P / R / F1 |
|---|---|
| `FROZEN` | 0.000 / 0.000 / **0.000** (tp 0, fp 7, fn 31) |
| `FROZEN-UNPLACED-FP` | 0.000 / 0.000 / **0.000** (tp 0, fp 14, fn 31) |
| `IDX-P1` | 0.067 / 0.032 / **0.043** (tp 1, fp 14, fn 30) |
| `IDXR1-P1` | 0.125 / 0.065 / **0.085** (tp 2, fp 14, fn 29) |

### A2 HIER-ANC-SURF, H1 {subclassOf}: ancestor hierarchy on surface pseudo-nodes (labelled variant, infers identity from strings; not a headline)

| variant | P / R / F1 | gold direct edges -> closure pairs | pred direct -> closure | gold mentions -> surface nodes | unplaced as FP |
|---|---|---|---|---|---|
| `FROZEN` | 0.000 / 0.000 / **0.000** (tp 0, fp 7, fn 30) | 29 -> 30 (+1) | 7 -> 7 | 765 -> 238 (collisions 527) | 0 |
| `FROZEN-UNPLACED-FP` | 0.000 / 0.000 / **0.000** (tp 0, fp 14, fn 30) | 29 -> 30 (+1) | 7 -> 7 | 765 -> 238 (collisions 527) | 7 |
| `IDX-P1` | 0.133 / 0.067 / **0.089** (tp 2, fp 13, fn 28) | 29 -> 30 (+1) | 13 -> 13 | 765 -> 238 (collisions 527) | 2 |
| `IDXR1-P1` | 0.188 / 0.100 / **0.130** (tp 3, fp 13, fn 27) | 29 -> 30 (+1) | 16 -> 16 | 765 -> 238 (collisions 527) | 0 |

Cycles detected: none.

### A3 REL-MACRO-SCINLP: relation macro F1 (gold relations whose two endpoints are predicted mentions)

| variant | macro F1 | classes in macro | population | micro F1 | direction accuracy given correct label | no edge at pair |
|---|---|---|---|---|---|---|
| `FROZEN` | **0.276** | 8 | 37 | 0.298 | 1.000 | 27 |
| `FROZEN-UNPLACED-FP` | **0.276** | 8 | 37 | 0.298 | 1.000 | 27 |
| `IDX-P1` | **0.259** | 10 | 189 | 0.259 | 1.000 | 154 |
| `IDXR1-P1` | **0.232** | 10 | 209 | 0.243 | 1.000 | 171 |

Per-class support (variant `IDX-P1`; `low` = support of 3 or fewer):

| label | support | tp | fp | fn | P | R | F1 | low |
|---|---|---|---|---|---|---|---|---|
| MeasuredBy | 8 | 2 | 0 | 6 | 1.000 | 0.250 | 0.400 |  |
| UsedFor | 52 | 13 | 0 | 39 | 1.000 | 0.250 | 0.400 |  |
| compareWith | 34 | 5 | 1 | 29 | 0.833 | 0.147 | 0.250 |  |
| enhancedBy | 33 | 2 | 0 | 31 | 1.000 | 0.061 | 0.114 |  |
| evaluatedBy | 6 | 3 | 0 | 3 | 1.000 | 0.500 | 0.667 |  |
| evaluatedOn | 12 | 2 | 0 | 10 | 1.000 | 0.167 | 0.286 |  |
| partOf | 2 | 0 | 2 | 2 | 0.000 | 0.000 | 0.000 | low |
| similarWith | 13 | 0 | 0 | 13 | n/a | 0.000 | 0.000 |  |
| subclassOf | 25 | 1 | 3 | 24 | 0.250 | 0.040 | 0.069 |  |
| trainedWith | 4 | 1 | 0 | 3 | 1.000 | 0.250 | 0.400 |  |

## DEV · CR-019 dev runs `cr019dev` (token matching)

Documents (6): 2021.acl-long.295, 2024.acl-long.144-1-9.grobid, P05-1008.grobid, P16-1007.grobid, P02-1004.grobid, P03-1014.grobid.

### Frozen / CR-019 reference: strict relation P / R / F1, all labels

| variant | P / R / F1 |
|---|---|
| `FROZEN` | 0.154 / 0.045 / **0.069** (tp 8, fp 44, fn 171) |
| `FROZEN-UNPLACED-FP` | 0.061 / 0.045 / **0.052** (tp 8, fp 123, fn 171) |
| `IDX-P1` | 0.114 / 0.084 / **0.096** (tp 15, fp 117, fn 164) |

### A1 HIER-DIRECT, H2 {subclassOf, subtaskOf}: direct hierarchy edge P / R / F1 (gold relations in set: 20)

| variant | P / R / F1 |
|---|---|
| `FROZEN` | 0.000 / 0.000 / **0.000** (tp 0, fp 8, fn 20) |
| `FROZEN-UNPLACED-FP` | 0.000 / 0.000 / **0.000** (tp 0, fp 18, fn 20) |
| `IDX-P1` | 0.000 / 0.000 / **0.000** (tp 0, fp 18, fn 20) |

### A2 HIER-ANC-SURF, H2 {subclassOf, subtaskOf}: ancestor hierarchy on surface pseudo-nodes (labelled variant, infers identity from strings; not a headline)

| variant | P / R / F1 | gold direct edges -> closure pairs | pred direct -> closure | gold mentions -> surface nodes | unplaced as FP |
|---|---|---|---|---|---|
| `FROZEN` | 0.000 / 0.000 / **0.000** (tp 0, fp 8, fn 20) | 20 -> 20 (+0) | 8 -> 8 | 671 -> 310 (collisions 361) | 0 |
| `FROZEN-UNPLACED-FP` | 0.000 / 0.000 / **0.000** (tp 0, fp 18, fn 20) | 20 -> 20 (+0) | 8 -> 8 | 671 -> 310 (collisions 361) | 10 |
| `IDX-P1` | 0.056 / 0.050 / **0.053** (tp 1, fp 17, fn 19) | 20 -> 20 (+0) | 13 -> 13 | 671 -> 310 (collisions 361) | 5 |

Cycles detected: none.

### A1 HIER-DIRECT, H1 {subclassOf}: direct hierarchy edge P / R / F1 (gold relations in set: 8)

| variant | P / R / F1 |
|---|---|
| `FROZEN` | 0.000 / 0.000 / **0.000** (tp 0, fp 8, fn 8) |
| `FROZEN-UNPLACED-FP` | 0.000 / 0.000 / **0.000** (tp 0, fp 16, fn 8) |
| `IDX-P1` | 0.000 / 0.000 / **0.000** (tp 0, fp 16, fn 8) |

### A2 HIER-ANC-SURF, H1 {subclassOf}: ancestor hierarchy on surface pseudo-nodes (labelled variant, infers identity from strings; not a headline)

| variant | P / R / F1 | gold direct edges -> closure pairs | pred direct -> closure | gold mentions -> surface nodes | unplaced as FP |
|---|---|---|---|---|---|
| `FROZEN` | 0.000 / 0.000 / **0.000** (tp 0, fp 8, fn 8) | 8 -> 8 (+0) | 8 -> 8 | 671 -> 310 (collisions 361) | 0 |
| `FROZEN-UNPLACED-FP` | 0.000 / 0.000 / **0.000** (tp 0, fp 16, fn 8) | 8 -> 8 (+0) | 8 -> 8 | 671 -> 310 (collisions 361) | 8 |
| `IDX-P1` | 0.000 / 0.000 / **0.000** (tp 0, fp 16, fn 8) | 8 -> 8 (+0) | 12 -> 12 | 671 -> 310 (collisions 361) | 4 |

Cycles detected: none.

### A3 REL-MACRO-SCINLP: relation macro F1 (gold relations whose two endpoints are predicted mentions)

| variant | macro F1 | classes in macro | population | micro F1 | direction accuracy given correct label | no edge at pair |
|---|---|---|---|---|---|---|
| `FROZEN` | **0.332** | 8 | 24 | 0.410 | 1.000 | 9 |
| `FROZEN-UNPLACED-FP` | **0.332** | 8 | 24 | 0.410 | 1.000 | 9 |
| `IDX-P1` | **0.293** | 11 | 65 | 0.330 | 1.000 | 39 |

Per-class support (variant `IDX-P1`; `low` = support of 3 or fewer):

| label | support | tp | fp | fn | P | R | F1 | low |
|---|---|---|---|---|---|---|---|---|
| MeasuredBy | 12 | 3 | 0 | 9 | 1.000 | 0.250 | 0.400 |  |
| UsedFor | 13 | 2 | 1 | 11 | 0.667 | 0.154 | 0.250 |  |
| compareWith | 13 | 3 | 2 | 10 | 0.600 | 0.231 | 0.333 |  |
| enhancedBy | 5 | 0 | 0 | 5 | n/a | 0.000 | 0.000 |  |
| evaluatedBy | 3 | 2 | 2 | 1 | 0.500 | 0.667 | 0.571 | low |
| evaluatedOn | 2 | 0 | 0 | 2 | n/a | 0.000 | 0.000 | low |
| partOf | 5 | 3 | 1 | 2 | 0.750 | 0.600 | 0.667 |  |
| similarWith | 4 | 0 | 0 | 4 | n/a | 0.000 | 0.000 |  |
| subclassOf | 2 | 0 | 4 | 2 | 0.000 | 0.000 | 0.000 | low |
| subtaskOf | 4 | 0 | 1 | 4 | 0.000 | 0.000 | 0.000 |  |
| trainedWith | 2 | 2 | 0 | 0 | 1.000 | 1.000 | 1.000 | low |

## DEV · CR-021 dev rebuild `cr021dev` (r1key matching)

Documents (6): 2021.acl-long.295, 2024.acl-long.144-1-9.grobid, P05-1008.grobid, P16-1007.grobid, P02-1004.grobid, P03-1014.grobid.

### Frozen / CR-019 reference: strict relation P / R / F1, all labels

| variant | P / R / F1 |
|---|---|
| `FROZEN` | 0.125 / 0.034 / **0.053** (tp 6, fp 42, fn 173) |
| `FROZEN-UNPLACED-FP` | 0.045 / 0.034 / **0.039** (tp 6, fp 126, fn 173) |
| `IDX-P1` | 0.097 / 0.073 / **0.083** (tp 13, fp 121, fn 166) |
| `IDXR1-P1` | 0.128 / 0.095 / **0.109** (tp 17, fp 116, fn 162) |

### A1 HIER-DIRECT, H2 {subclassOf, subtaskOf}: direct hierarchy edge P / R / F1 (gold relations in set: 20)

| variant | P / R / F1 |
|---|---|
| `FROZEN` | 0.000 / 0.000 / **0.000** (tp 0, fp 8, fn 20) |
| `FROZEN-UNPLACED-FP` | 0.000 / 0.000 / **0.000** (tp 0, fp 18, fn 20) |
| `IDX-P1` | 0.000 / 0.000 / **0.000** (tp 0, fp 18, fn 20) |
| `IDXR1-P1` | 0.000 / 0.000 / **0.000** (tp 0, fp 18, fn 20) |

### A2 HIER-ANC-SURF, H2 {subclassOf, subtaskOf}: ancestor hierarchy on surface pseudo-nodes (labelled variant, infers identity from strings; not a headline)

| variant | P / R / F1 | gold direct edges -> closure pairs | pred direct -> closure | gold mentions -> surface nodes | unplaced as FP |
|---|---|---|---|---|---|
| `FROZEN` | 0.000 / 0.000 / **0.000** (tp 0, fp 8, fn 20) | 20 -> 20 (+0) | 8 -> 8 | 671 -> 310 (collisions 361) | 0 |
| `FROZEN-UNPLACED-FP` | 0.000 / 0.000 / **0.000** (tp 0, fp 18, fn 20) | 20 -> 20 (+0) | 8 -> 8 | 671 -> 310 (collisions 361) | 10 |
| `IDX-P1` | 0.056 / 0.050 / **0.053** (tp 1, fp 17, fn 19) | 20 -> 20 (+0) | 13 -> 13 | 671 -> 310 (collisions 361) | 5 |
| `IDXR1-P1` | 0.056 / 0.050 / **0.053** (tp 1, fp 17, fn 19) | 20 -> 20 (+0) | 13 -> 13 | 671 -> 310 (collisions 361) | 5 |

Cycles detected: none.

### A1 HIER-DIRECT, H1 {subclassOf}: direct hierarchy edge P / R / F1 (gold relations in set: 8)

| variant | P / R / F1 |
|---|---|
| `FROZEN` | 0.000 / 0.000 / **0.000** (tp 0, fp 8, fn 8) |
| `FROZEN-UNPLACED-FP` | 0.000 / 0.000 / **0.000** (tp 0, fp 16, fn 8) |
| `IDX-P1` | 0.000 / 0.000 / **0.000** (tp 0, fp 16, fn 8) |
| `IDXR1-P1` | 0.000 / 0.000 / **0.000** (tp 0, fp 16, fn 8) |

### A2 HIER-ANC-SURF, H1 {subclassOf}: ancestor hierarchy on surface pseudo-nodes (labelled variant, infers identity from strings; not a headline)

| variant | P / R / F1 | gold direct edges -> closure pairs | pred direct -> closure | gold mentions -> surface nodes | unplaced as FP |
|---|---|---|---|---|---|
| `FROZEN` | 0.000 / 0.000 / **0.000** (tp 0, fp 8, fn 8) | 8 -> 8 (+0) | 8 -> 8 | 671 -> 310 (collisions 361) | 0 |
| `FROZEN-UNPLACED-FP` | 0.000 / 0.000 / **0.000** (tp 0, fp 16, fn 8) | 8 -> 8 (+0) | 8 -> 8 | 671 -> 310 (collisions 361) | 8 |
| `IDX-P1` | 0.000 / 0.000 / **0.000** (tp 0, fp 16, fn 8) | 8 -> 8 (+0) | 12 -> 12 | 671 -> 310 (collisions 361) | 4 |
| `IDXR1-P1` | 0.000 / 0.000 / **0.000** (tp 0, fp 16, fn 8) | 8 -> 8 (+0) | 12 -> 12 | 671 -> 310 (collisions 361) | 4 |

Cycles detected: none.

### A3 REL-MACRO-SCINLP: relation macro F1 (gold relations whose two endpoints are predicted mentions)

| variant | macro F1 | classes in macro | population | micro F1 | direction accuracy given correct label | no edge at pair |
|---|---|---|---|---|---|---|
| `FROZEN` | **0.201** | 9 | 27 | 0.316 | 1.000 | 16 |
| `FROZEN-UNPLACED-FP` | **0.201** | 9 | 27 | 0.316 | 1.000 | 16 |
| `IDX-P1` | **0.236** | 11 | 70 | 0.286 | 1.000 | 49 |
| `IDXR1-P1` | **0.252** | 11 | 75 | 0.337 | 1.000 | 49 |

Per-class support (variant `IDX-P1`; `low` = support of 3 or fewer):

| label | support | tp | fp | fn | P | R | F1 | low |
|---|---|---|---|---|---|---|---|---|
| MeasuredBy | 13 | 2 | 0 | 11 | 1.000 | 0.154 | 0.267 |  |
| UsedFor | 14 | 2 | 0 | 12 | 1.000 | 0.143 | 0.250 |  |
| compareWith | 13 | 5 | 0 | 8 | 1.000 | 0.385 | 0.556 |  |
| enhancedBy | 5 | 0 | 0 | 5 | n/a | 0.000 | 0.000 |  |
| evaluatedBy | 3 | 2 | 2 | 1 | 0.500 | 0.667 | 0.571 | low |
| evaluatedOn | 5 | 0 | 0 | 5 | n/a | 0.000 | 0.000 |  |
| partOf | 5 | 1 | 1 | 4 | 0.500 | 0.200 | 0.286 |  |
| similarWith | 4 | 0 | 0 | 4 | n/a | 0.000 | 0.000 |  |
| subclassOf | 2 | 0 | 4 | 2 | 0.000 | 0.000 | 0.000 | low |
| subtaskOf | 4 | 0 | 1 | 4 | 0.000 | 0.000 | 0.000 |  |
| trainedWith | 2 | 1 | 0 | 1 | 1.000 | 0.500 | 0.667 | low |

## Limits

- E1, E3-M and E4-M runs (named in the spec) are not rescored tonight: their prediction path differs from E0 and was not wired; only E0 runs are covered.
- A3 cannot tell a pair that never reached the classifier from one the classifier answered `no_relation` (the SciNLP run records no per-gold-pair classifier outcome at mention level): both are `no_edge_at_pair` and count as a false negative for the gold class.
- A2 closes the hierarchy on case-folded surface strings: two different concepts with one surface collapse (collisions are counted above), and one concept written two ways stays two nodes.
- Dev has 6 and test 3 documents; per-class F1 on classes with support of 3 or fewer is unstable (flagged). No confidence interval is attempted (`NOT_EVALUABLE_SMALL_N`).
- The CR-021 rebuild runs mix the setting change with run-to-run variation (CR-021 report); they are shown beside, never pooled with, the frozen runs.
