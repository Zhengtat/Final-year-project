# CR-032 broader Hierarchy F1 (`HIER-T1`, `HIER-T1-SURF-R1`) ($0, no model call)

Written for: the project owner and Research. New, named scorer variants reported beside the frozen numbers (rule 35); no frozen number is replaced.

Hierarchy set, read from the registry (family `classification_structure`, transitive): P&D (v1.3) `['is_a', 'part_of']` (chains only within a part type: `['part_of']`); SciNLP (v1.4) `['is_a', 'part_of', 'subtask_of']` = SciNLP labels `['partOf', 'subclassOf', 'subtaskOf']`.

## Determinism gate

| check | result |
|---|---|
| pd_heldout_E0_generic_equals_frozen_per_section | PASS |
| pd_heldout_E0_equals_cr017_headline_json | PASS |
| pd_heldout_E1_generic_equals_frozen_per_section | PASS |
| pd_heldout_E1_equals_cr017_headline_json | PASS |
| pd_heldout_E2_generic_equals_frozen_per_section | PASS |
| pd_heldout_E2_equals_cr017_headline_json | PASS |
| pd_heldout_E3_generic_equals_frozen_per_section | PASS |
| pd_heldout_E3_equals_cr017_headline_json | PASS |
| pd_heldout_E4_generic_equals_frozen_per_section | PASS |
| pd_heldout_E4_equals_cr017_headline_json | PASS |
| pd_pilot_E0_generic_equals_frozen_per_section | PASS |
| pd_pilot_E0_equals_cr017_headline_json | PASS |
| pd_pilot_E1_generic_equals_frozen_per_section | PASS |
| pd_pilot_E2_generic_equals_frozen_per_section | PASS |
| pd_pilot_E3_generic_equals_frozen_per_section | PASS |
| pd_pilot_E4_generic_equals_frozen_per_section | PASS |
| scinlp_test_frozen_FROZEN_surface_H2_equals_cr022_part_a | PASS |
| scinlp_test_frozen_IDX-P1_surface_H2_equals_cr022_part_a | PASS |

**Gate: PASSED.** Source hashes identical before and after: **True** (49 files).

## P&D-E2E (concept-level gold; per-section closure; frozen CR-012 mention-span alignment)

`frozen is_a` = the CR-017 Ancestor Hierarchy F1. `HIER-T1` pools `is_a` and `part_of` (closed separately; `part_of` per part type). P / R / F1.

| run | sections | frozen `is_a` | `HIER-T1` | `HIER-T1` direct edges | gold pairs (direct edges) |
|---|---|---|---|---|---|
| heldout/E0 | 7 | 0.146 / 0.093 / **0.114** (tp 7, fp 41, fn 68) | 0.101 / 0.067 / **0.081** (tp 8, fp 71, fn 111) | 0.108 / 0.076 / **0.089** (tp 8, fp 66, fn 97) | 119 (105) |
| heldout/E1 | 7 | 0.526 / 0.133 / **0.213** (tp 10, fp 9, fn 65) | 0.311 / 0.118 / **0.171** (tp 14, fp 31, fn 105) | 0.289 / 0.124 / **0.173** (tp 13, fp 32, fn 92) | 119 (105) |
| heldout/E2 | 7 | 0.292 / 0.093 / **0.141** (tp 7, fp 17, fn 68) | 0.237 / 0.118 / **0.157** (tp 14, fp 45, fn 105) | 0.237 / 0.133 / **0.171** (tp 14, fp 45, fn 91) | 119 (105) |
| heldout/E3 | 7 | 0.672 / 0.573 / **0.619** (tp 43, fp 21, fn 32) | 0.492 / 0.513 / **0.502** (tp 61, fp 63, fn 58) | 0.487 / 0.543 / **0.514** (tp 57, fp 60, fn 48) | 119 (105) |
| heldout/E4 | 7 | 0.896 / 0.573 / **0.699** (tp 43, fp 5, fn 32) | 0.753 / 0.513 / **0.610** (tp 61, fp 20, fn 58) | 0.740 / 0.543 / **0.626** (tp 57, fp 20, fn 48) | 119 (105) |
| pilot/E0 | 2 | 0.667 / 0.074 / **0.133** (tp 2, fp 1, fn 25) | 0.333 / 0.061 / **0.103** (tp 3, fp 6, fn 46) | 0.333 / 0.091 / **0.143** (tp 3, fp 6, fn 30) | 49 (33) |
| pilot/E1 | 1 | 0.000 / 0.000 / **0.000** (tp 0, fp 1, fn 0) | 0.000 / 0.000 / **0.000** (tp 0, fp 3, fn 4) | 0.000 / 0.000 / **0.000** (tp 0, fp 3, fn 4) | 4 (4) |
| pilot/E2 | 1 | 0.000 / 0.000 / **0.000** (tp 0, fp 0, fn 0) | 0.000 / 0.000 / **0.000** (tp 0, fp 3, fn 4) | 0.000 / 0.000 / **0.000** (tp 0, fp 3, fn 4) | 4 (4) |
| pilot/E3 | 1 | 0.000 / 0.000 / **0.000** (tp 0, fp 2, fn 0) | 0.286 / 0.500 / **0.364** (tp 2, fp 5, fn 2) | 0.286 / 0.500 / **0.364** (tp 2, fp 5, fn 2) | 4 (4) |
| pilot/E4 | 1 | 0.000 / 0.000 / **0.000** (tp 0, fp 2, fn 0) | 0.500 / 0.500 / **0.500** (tp 2, fp 2, fn 2) | 0.500 / 0.500 / **0.500** (tp 2, fp 2, fn 2) | 4 (4) |

Per-relation F1 inside `HIER-T1` (pairs of that relation only):

| run | relation | P / R / F1 |
|---|---|---|
| heldout/E0 | `is_a` | 0.146 / 0.093 / **0.114** (tp 7, fp 41, fn 68) |
| heldout/E0 | `part_of` | 0.032 / 0.023 / **0.027** (tp 1, fp 30, fn 43) |
| heldout/E1 | `is_a` | 0.526 / 0.133 / **0.213** (tp 10, fp 9, fn 65) |
| heldout/E1 | `part_of` | 0.154 / 0.091 / **0.114** (tp 4, fp 22, fn 40) |
| heldout/E2 | `is_a` | 0.292 / 0.093 / **0.141** (tp 7, fp 17, fn 68) |
| heldout/E2 | `part_of` | 0.200 / 0.159 / **0.177** (tp 7, fp 28, fn 37) |
| heldout/E3 | `is_a` | 0.672 / 0.573 / **0.619** (tp 43, fp 21, fn 32) |
| heldout/E3 | `part_of` | 0.300 / 0.409 / **0.346** (tp 18, fp 42, fn 26) |
| heldout/E4 | `is_a` | 0.896 / 0.573 / **0.699** (tp 43, fp 5, fn 32) |
| heldout/E4 | `part_of` | 0.545 / 0.409 / **0.468** (tp 18, fp 15, fn 26) |
| pilot/E0 | `is_a` | 0.667 / 0.074 / **0.133** (tp 2, fp 1, fn 25) |
| pilot/E0 | `part_of` | 0.167 / 0.045 / **0.071** (tp 1, fp 5, fn 21) |
| pilot/E1 | `is_a` | 0.000 / 0.000 / **0.000** (tp 0, fp 1, fn 0) |
| pilot/E1 | `part_of` | 0.000 / 0.000 / **0.000** (tp 0, fp 2, fn 4) |
| pilot/E2 | `part_of` | 0.000 / 0.000 / **0.000** (tp 0, fp 3, fn 4) |
| pilot/E3 | `is_a` | 0.000 / 0.000 / **0.000** (tp 0, fp 2, fn 0) |
| pilot/E3 | `part_of` | 0.400 / 0.500 / **0.444** (tp 2, fp 3, fn 2) |
| pilot/E4 | `is_a` | 0.000 / 0.000 / **0.000** (tp 0, fp 2, fn 0) |
| pilot/E4 | `part_of` | 1.000 / 0.500 / **0.667** (tp 2, fp 0, fn 2) |

No cycles and no `part_of` edge without a part type.

## SciNLP test (mention-level gold, no identity gold)

`HIER-T1-SURF-R1` infers identity from strings (R1 name key plus acronym <-> long form within one paper). It is a labelled cross-check, never a headline. Unplaced predicted edges are false positives in every variant except `FROZEN` (rule 35).

Real concept matching (`HIER-T1` with the owner's scoped identity sheet): **AWAITING_OWNER_IDENTITY_SHEET**. The blind sheet has 90 rows.

### frozen CR-012 STOP 4 (token matching)

Documents (3): 2021.acl-long.353, 2024.acl-long.108-1-9.grobid, P17-1058.grobid.

| variant | `HIER-T1-SURF-R1` P / R / F1 | direct edges | same set, surface identity (CR-022 A2 rule) | gold pairs (direct) | unplaced as FP |
|---|---|---|---|---|---|
| `FROZEN` | 0.111 / 0.022 / **0.036** (tp 1, fp 8, fn 45) | 0.111 / 0.022 / **0.037** (tp 1, fp 8, fn 44) | 0.100 / 0.021 / **0.035** (tp 1, fp 9, fn 46) | 46 (45) | 0 |
| `IDX-P1` | 0.158 / 0.130 / **0.143** (tp 6, fp 32, fn 40) | 0.188 / 0.133 / **0.156** (tp 6, fp 26, fn 39) | 0.125 / 0.106 / **0.115** (tp 5, fp 35, fn 42) | 46 (45) | 3 |

Per-label F1 (first variant):

| label | P / R / F1 |
|---|---|
| `partOf` | 0.000 / 0.000 / **0.000** (tp 0, fp 2, fn 8) |
| `subclassOf` | 0.143 / 0.034 / **0.056** (tp 1, fp 6, fn 28) |
| `subtaskOf` | 0.000 / 0.000 / **0.000** (tp 0, fp 0, fn 9) |

Identity cost (gold): 765 mentions -> 209 pseudo-nodes (556 collisions); 24 nodes merge more than one distinct surface. Examples of merged surfaces: [['language models', 'lm', 'lms'], ['p * -tuning', 'p * tuning', 'p-tuning'], ['prefix tuning', 'prefix-tuning', 'prefixtuning'], ['adapter-tuning', 'adaptertuning'], ['embedding-only', 'embeddingonly'], ['large language models', 'llm', 'llms']].

### CR-021 rebuild `cr021test` (r1key matching)

Documents (3): 2021.acl-long.353, 2024.acl-long.108-1-9.grobid, P17-1058.grobid.

| variant | `HIER-T1-SURF-R1` P / R / F1 | direct edges | same set, surface identity (CR-022 A2 rule) | gold pairs (direct) | unplaced as FP |
|---|---|---|---|---|---|
| `FROZEN` | 0.000 / 0.000 / **0.000** (tp 0, fp 8, fn 46) | 0.000 / 0.000 / **0.000** (tp 0, fp 8, fn 45) | 0.000 / 0.000 / **0.000** (tp 0, fp 9, fn 47) | 46 (45) | 0 |
| `IDX-P1` | 0.077 / 0.065 / **0.071** (tp 3, fp 36, fn 43) | 0.094 / 0.067 / **0.078** (tp 3, fp 29, fn 42) | 0.049 / 0.043 / **0.045** (tp 2, fp 39, fn 45) | 46 (45) | 4 |
| `IDXR1-P1` | 0.103 / 0.087 / **0.094** (tp 4, fp 35, fn 42) | 0.118 / 0.089 / **0.101** (tp 4, fp 30, fn 41) | 0.071 / 0.064 / **0.067** (tp 3, fp 39, fn 44) | 46 (45) | 2 |

Per-label F1 (first variant):

| label | P / R / F1 |
|---|---|
| `partOf` | 0.000 / 0.000 / **0.000** (tp 0, fp 2, fn 8) |
| `subclassOf` | 0.000 / 0.000 / **0.000** (tp 0, fp 6, fn 29) |
| `subtaskOf` | 0.000 / 0.000 / **0.000** (tp 0, fp 0, fn 9) |

Identity cost (gold): 765 mentions -> 209 pseudo-nodes (556 collisions); 24 nodes merge more than one distinct surface. Examples of merged surfaces: [['language models', 'lm', 'lms'], ['p * -tuning', 'p * tuning', 'p-tuning'], ['prefix tuning', 'prefix-tuning', 'prefixtuning'], ['adapter-tuning', 'adaptertuning'], ['embedding-only', 'embeddingonly'], ['large language models', 'llm', 'llms']].

## Limits

- SciNLP identity is inferred from strings in this report; the real-identity figure waits for the owner's scoped identity sheet (hierarchy-relation endpoints only).
- The explorer scorecard does not yet show these variants (not wired in this change).
- P&D pilot has runs for fewer levels than held-out; only existing runs are reported. Small n: no confidence interval is attempted.
