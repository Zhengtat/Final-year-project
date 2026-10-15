# Rebuild with the current production settings (2026-10-16)

R1-key matching (CR-020) + rejected-link adjudicator (CR-021), new run ids; frozen results unchanged and shown as `before`. SciNLP test: owner-approved final-reporting run (DECISIONS 2026-10-16).

## SciNLP test (3 papers)

| scorer | before P / R / F1 | rebuild P / R / F1 |
|---|---|---|
| strict relation `FROZEN` | 0.364 / 0.027 / **0.050** | 0.292 / 0.024 / **0.044** |
| strict relation `FROZEN-UNPLACED-FP` | 0.071 / 0.027 / **0.039** | 0.064 / 0.024 / **0.035** |
| strict relation `IDX-P1` | 0.348 / 0.136 / **0.195** | 0.259 / 0.098 / **0.143** |
| strict relation `IDXR1-P1` | 0.345 / 0.136 / **0.195** | 0.265 / 0.102 / **0.147** |
| strict relation `IDXR1-P3` | 0.381 / 0.346 / **0.362** | 0.337 / 0.329 / **0.333** |
| concept (entity strict) `FROZEN` | 0.525 / 0.265 / 0.352 | 0.535 / 0.261 / 0.351 |
| concept (entity strict) `IDXR1-P1` | 0.498 / 0.826 / 0.622 | 0.538 / 0.834 / 0.654 |

Graphs before: {'concepts': 228, 'aliases': 41, 'edges': 112, 'selected_pairs': 292, 'rejected_links': 6, 'spend_usd': 1.9315000000000002}
Graphs rebuilt: {'concepts': 215, 'aliases': 46, 'edges': 109, 'selected_pairs': 292, 'rejected_links': 6, 'spend_usd': 0.5831999999999999, 'adjudicated:same_as_target': 4, 'adjudicated:new_concept': 2}

## SciNLP dev (6 papers)

| scorer | before P / R / F1 | rebuild P / R / F1 |
|---|---|---|
| strict relation `FROZEN` | 0.154 / 0.045 / **0.069** | 0.125 / 0.034 / **0.053** |
| strict relation `FROZEN-UNPLACED-FP` | 0.061 / 0.045 / **0.052** | 0.045 / 0.034 / **0.039** |
| strict relation `IDX-P1` | 0.114 / 0.084 / **0.096** | 0.097 / 0.073 / **0.083** |
| strict relation `IDXR1-P1` | 0.114 / 0.084 / **0.096** | 0.128 / 0.095 / **0.109** |
| strict relation `IDXR1-P3` | 0.114 / 0.112 / **0.113** | 0.122 / 0.123 / **0.122** |
| concept (entity strict) `FROZEN` | 0.332 / 0.307 / 0.319 | 0.326 / 0.316 / 0.321 |
| concept (entity strict) `IDXR1-P1` | 0.326 / 0.645 / 0.433 | 0.306 / 0.668 / 0.420 |

Graphs before: {'concepts': 423, 'aliases': 39, 'edges': 132, 'selected_pairs': 456, 'rejected_links': 10, 'spend_usd': 2.438}
Graphs rebuilt: {'concepts': 439, 'aliases': 47, 'edges': 132, 'selected_pairs': 446, 'rejected_links': 9, 'spend_usd': 0.6312000000000001, 'adjudicated:same_as_target': 5, 'adjudicated:new_concept': 4}

## P&D chapters 1-3: `slice3_c2` (production) vs `slice3_c3` (rebuild)

- slice3_c2: {'concepts': 1243, 'aliases': 188, 'edges': 529, 'selected_pairs': 1100, 'rejected_links': 124, 'adjudicated': {}, 'matching_mode': 'token', 'spend_usd': 10.2899}
- slice3_c3: {'concepts': 1351, 'aliases': 239, 'edges': 518, 'selected_pairs': 1100, 'rejected_links': 147, 'adjudicated': {'new_concept': 77, 'same_as_target': 27, 'not_a_concept': 43}, 'matching_mode': 'r1key', 'spend_usd': 7.0455}

Five metrics on the P&D development answer key (sections 1.5, 2.6), each whole-slice graph restricted to those sections:

| run | Concept F1 | Ancestor Hierarchy F1 | Pair Recall | Relation Macro F1 | Strict E2E Edge F1 |
|---|---|---|---|---|---|
| slice3_c2 | 0.552 | 0.227 | 0.227 | 0.726 | 0.129 |
| slice3_c3 | 0.548 | 0.200 | 0.257 | 0.538 | 0.140 |

Total rebuild spend: **$8.26**
