# CR-056: why gold concepts are still missed (arm `cr055b`, the highest-recall concept settings; 20 papers)

Generated from `cumap.cr056.misses` and `cumap.cr056.nested` ($0, read-only; numbers in `misses.json`). Concept recall `IDXR1-P1` 0.751
(1527 of 2032 gold mentions); 505 missed.

| stage (earliest loss) | misses |
|---|---|
| span (a prediction overlaps, the span differs) | 313 |
| never proposed by the generator | 164 |
| proposed, then lost | 20 |
| node exists, occurrence not placed | 7 |
| verifier hint rejected | 1 |

**Span (313).** The CR-052 placement rules (head noun, "( ACRONYM )") fix 102. Of the rest, the prediction is now more often LONGER than the
gold (127) than shorter (88): the v5 / v6 modifier rule and the acronym rule give "language understanding tasks", "pre-trained language
model", "standard finetuning", "masked language modeling ( MLM )" where the gold marks "language understanding", "language model",
"finetuning", "masked language modeling". In 83 of these the predicted surface is itself marked as gold elsewhere in the same paper: the
gold is inconsistent about span length. Others: split by a coordination or parenthetical (17), punctuation (8), coordination (7).

**Never proposed (164).** method 88, task 47, metric 17, dataset 12. Short method / component phrases ("graph-based consensus",
"copying mechanism", "discriminative ranker", "convolutional filter", "attention mechanisms", "topological parse / tree"), PDF artefacts
("nystro ¨ m", 13), "confidence" (9), dataset codes (TDT4, IWSLT), long task descriptions the gold marks (15).

**Position inside a unit** (units are up to 2,500 words): recall by fifth of the unit 0.751 / 0.759 / 0.728 / 0.807 / 0.703 (control
0.701 / 0.678 / 0.700 / 0.763 / 0.646): a small drop in the last fifth only. Paragraphs with gold mentions and no generator item at all: 28
of 338 (98 gold mentions, 16 of them missed): skipping is not the main loss.

**Nested placement (`IDXR1N-P1`, $0):** inside every placed mention, also place every other node name it contains ("language model" inside
"pre-trained language model"). Concept recall 0.792 -> **0.828** (precision 0.375 -> 0.315, F1 0.509 -> 0.456); relation recall
0.116 -> 0.118. A recall-first reporting choice, reported beside `IDXR1-P1`.

| concept settings | grounding | concept P / R / F1 | relation P / R / F1 |
|---|---|---|---|
| `cr053v5` (v3, D3 budget) | `IDXR1-P1` | 0.371 / 0.701 / 0.485 | 0.172 / 0.112 / 0.136 |
| `cr055ballp` (v5: arm B + all pairs) | `IDXR1-P1` | 0.356 / 0.751 / 0.483 | 0.157 / 0.149 / 0.153 |
| `cr055ballp` | `IDXR1X-P1` | 0.375 / 0.792 / 0.509 | 0.178 / 0.169 / 0.173 |
| `cr055ballp` | `IDXR1N-P1` | 0.315 / 0.828 / 0.456 | 0.133 / 0.173 / 0.150 |
