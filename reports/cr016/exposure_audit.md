# CR-016 STOP 1 — exposure audit (CR-001 to CR-015) and fresh-evaluation availability

"Labels inspected" = a gold annotation of the section was read or reviewed; "predictions inspected" = system output on it was examined or scored. The textbook is public (CC BY 4.0) and the models may have seen it in pre-training (uncontrollable, stated limitation). Memory indexes contain **raw text only**, never labels or predictions, so raw-text exposure of earlier sections to a memory is not itself contamination; the evaluation sections need untouched labels and predictions.

| sections | usage | labels inspected | predictions inspected | gold provenance |
|---|---|---|---|---|
| P&D ch1–3 (24 sections) | CR-005…CR-010 owner marks, rules, explorer, failure analysis; the production graph `slice3_c2` | yes | yes | owner marks (human) |
| 1.5, 2.6 | CR-012 pilot | yes | yes | CR-012 gold |
| 4.4, 4.5, 5.4, 6.3, 7.1, 8.2, 9.3 | CR-012 held-out (once), failure analysis, explorer overlay | yes | yes | CR-012 gold (single annotator, owner-reviewed LLM prefill) |
| 4.1, 9.2 | CR-014 pilot; CR-015 development | yes | yes | MODEL_GENERATED_DIAGNOSTIC |
| 4.2, 5.3, 6.1, 6.4, 7.2, 8.3, 8.4, 8.5 | CR-014 held-out (once); CR-015 development | yes | yes | MODEL_GENERATED_DIAGNOSTIC |
| 4.3, 6.2 | CR-015 fresh pilot: gold drafted by a model and edited by a non-human process; **no prediction ever run** | yes (model-generated) | no | MODEL_GENERATED_DIAGNOSTIC |
| **5.2, 6.5, 9.1, 9.4** | CR-015 sealed held-out: never annotated, never predicted | **no** | **no** | none |
| 5.1, 8.1 | untouched, below 1,000 words | no | no | none |
| chapter-intro "perspective" units and front matter (≈ 20 units) | not evaluation units | no | no | none |
| IIR dev (13) / test (70), IIR FP audit (58) | CR-009/010, CR-014 | yes | yes | IIR consensus gold (non-exhaustive); audit LLM-generated |
| SciNLP | CR-012 | yes | yes | CR-012 |

## What a fresh sequential evaluation can use
- **Truly fresh (no labels, no predictions): 5.2, 6.5, 9.1, 9.4** (41,832 words) plus the two tiny sections. Their gold does not exist; producing it raises the same provenance question as CR-015 (model-generated, unless a human annotates ~41.8k words).
- **Never predicted but label-exposed: 4.3, 6.2** (7,957 words, model-generated gold already exists).
- **Everything else is exposed** and can serve as development material or a clearly labelled feasibility set.
- Causal order: the P&D sections are in book order in the parsed text (`source_order_manifest.json`, sha256 `eee8789f…`: 64 units, 2,654 paragraphs, 216,451 words). A causal memory for the fresh sections would hold the raw text of every earlier unit: 5.2 (source order 36): 36 earlier units, 1,232 paragraphs, 100,739 words; 6.5 (source order 45): 45 earlier units, 1,737 paragraphs, 141,430 words; 9.1 (source order 59): 59 earlier units, 2,276 paragraphs, 185,461 words; 9.4 (source order 62): 62 earlier units, 2,541 paragraphs, 206,184 words.

## Recurrence available in existing gold (development feasibility; model-generated gold)
Over the three gold sets (CR-014 held-out 8 sections, CR-014 pilot 2, CR-015 pilot 2): 10,891 gold mentions; **7,862 (72%)** have the same surface somewhere in earlier book text; **3,308** belong to a concept already annotated in an earlier section of the same gold set; **264 (2.4%)** are alias or variant-surface recurrences (a concept first seen under a different surface); 7,700 mentions are one-token. So exact-surface and one-token recurrence slices are large; **alias / acronym recurrence is small** (a few hundred mentions, acronyms fewer still) and the same-surface-different-sense slice has no gold. Long-gap definition is not yet fixed.
