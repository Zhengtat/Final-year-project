# CR-012 scorer validation (STOP 3, $0) - SciNLP train/dev and the P&D pilot only

The SciNLP test split and the P&D held-out sections were never loaded. A perfect prediction must score exactly 1.0 and every corruption must move the score by a value fixed by construction. Raw numbers: `reports/cr012/scorer_validation.json`.

## SciNLP strict scorer (train 51 documents, dev 6 documents)
| check | train | dev | expected |
|---|---|---|---|
| gold as prediction: entity strict / typed, Rel, Rel+ F1 | 1.000 | 1.000 | 1.0 |
| node edges projected to evidence-grounded mentions: entity, Rel, Rel+ F1 | 1.000 | 1.000 | 1.0 |
| drop every 10th relation: recall / precision | 0.884 / 1.000 | 0.894 / 1.000 | about 0.9 / 1.0 |
| every span one token too long: strict entity F1 | 0.0014 | 0.0015 | about 0 (only coincidental nesting matches) |
| random wrong relation for directional gold: precision = recall | 0.2095 | 0.2179 | symmetric share (0.2102 / 0.2179) |
| all relations reversed: recall | 0.2095 | 0.2179 | symmetric share (0.2102 / 0.2179) |

Reversed directional relations fail and reversed symmetric ones pass; a wrong endpoint type fails Rel+ only.

## P&D canonical-graph scorer (owner-reviewed pilot gold, sections 1.5 and 2.6)
| check | 1.5 | 2.6 |
|---|---|---|
| unique headline edges / relation rows | 39 / 40 | 79 / 82 |
| gold as prediction: strict F1, canonical F1, pairwise identity F1, B-cubed F1, pair recall | 1.000, 1.000, 1.000, 1.000, 1.000 | 1.000, 1.000, 1.000, 1.000, 1.000 |
| drop 10% of edges: recall (expected) | 0.9231 (0.9231) | 0.9114 (0.9114) |
| all edges reversed: recall (symmetric share) | 0.0513 (0.0513) | 0.1013 (0.1013) |
| one concept split into two nodes: canonical-node precision falls, strict F1 unchanged | -0.018, True | -0.011, True |
| two concepts merged into one node: flagged false merge, strict recall falls | ['merged'], 0.923 | ['merged'], 0.709 |

Qualifier variants of one (source, target, relation) (for example `acts_on` with different action types) are one headline edge by the CR's definition; their qualifier values are scored separately as `qualifier_accuracy` (secondary, feeding the R3 attribution).

## Rehearsal: the existing production graph against the pilot gold (development only, not a result)
The finished run `slice3_c2` already processed sections 1.5 and 2.6 inside the 3-chapter slice. Converting its nodes (longest-match mentions) and accepted edges (evidence-quote positions) and scoring them exercises the whole scoring path: strict E2E edge F1 0.12 (1.5) and 0.10 (2.6); canonical-node F1 0.57 / 0.63; pairwise identity F1 0.76 / 0.79; pair recall 0.21 / 0.14. These come from a run under a different pair budget (1,100 pairs for 77k words, anchors first) and are NOT the E0 result: E0 will run each unit on its own with the D3 budget.

## Pilot gold provenance (`pilot_gold_provenance.json`, sha256 `7dd929da4e9c4f5a...`)
All annotation rows carry `annotator_id = chatgpt_research_prefill` (an LLM research-tool prefill). The owner states that every row was reviewed (2026-10-10); this is a self-attestation. The pilot gold is therefore used only for debugging annotation and scoring (as the CR prescribes); it is not independently double-annotated, and prefill-derived agreement may be inflated. It never enters held-out scores.
