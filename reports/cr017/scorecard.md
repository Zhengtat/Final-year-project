# CR-017 scorecard

Scorer `cr017-1` · model calls 0 · no composite score · Section-bootstrap intervals are descriptive when fewer than 10 units. † = descriptive interval (fewer than 10 sections); none is shown for fewer than 3.

## HEADLINE — five metrics only

### P&D-E2E held-out (7 sections, headline)

| Level | Concept F1 | Ancestor Hierarchy F1 | Pair Recall | Relation Macro F1 ⚠ | Strict E2E Edge F1 |
|---|---|---|---|---|---|
| E0 | 0.643 [0.589, 0.698]† | 0.114 [0.077, 0.156]† | 0.163 [0.139, 0.186]† | 0.484 [0.302, 0.632]† | 0.053 [0.030, 0.076]† |
| E1 | 0.855 [0.828, 0.884]† | 0.213 [0.112, 0.320]† | 0.220 [0.181, 0.260]† | 0.447 [0.337, 0.570]† | 0.113 [0.080, 0.152]† |
| E2 | 0.996 [0.991, 1.000]† | 0.141 [0.103, 0.197]† | 0.256 [0.211, 0.293]† | 0.390 [0.341, 0.485]† | 0.129 [0.105, 0.153]† |
| E3 | 0.996 [0.991, 1.000]† | 0.619 [0.507, 0.692]† | 1.000 [1.000, 1.000]† | 0.342 [0.295, 0.388]† | 0.398 [0.324, 0.452]† |
| E4 | 0.996 [0.991, 1.000]† | 0.699 [0.594, 0.766]† | 1.000 [1.000, 1.000]† | 0.342 [0.295, 0.388]† | 0.470 [0.396, 0.522]† |

### P&D-E2E pilot (development)

| Level | Concept F1 | Ancestor Hierarchy F1 | Pair Recall | Relation Macro F1 ⚠ | Strict E2E Edge F1 |
|---|---|---|---|---|---|
| E0 | 0.630 | 0.133 | 0.212 | 0.600 | 0.086 |
| E1 | 0.766 | NOT_EVALUABLE | 0.086 | 0.833 | 0.066 |
| E2 | 1.000 | NOT_EVALUABLE | 0.308 | 0.571 | 0.271 |
| E3 | 1.000 | NOT_EVALUABLE | 1.000 | 0.646 | 0.560 |
| E4 | 1.000 | NOT_EVALUABLE | 1.000 | 0.646 | 0.656 |

### SciNLP held-out (3 documents; separate benchmark)

> Mention-level benchmark without identity gold: Concept F1 is the entity-strict analogue and Pair Recall the endpoints-present analogue; hierarchy is not evaluable; Relation Macro F1 is not computed. Never pooled with P&D.

| Level | Concept F1 | Ancestor Hierarchy F1 | Pair Recall | Relation Macro F1 ⚠ | Strict E2E Edge F1 |
|---|---|---|---|---|---|
| E0 | 0.352 | NOT_EVALUABLE | 0.545 | NOT_COMPUTED | 0.050 |
| E1 | 0.979 | NOT_EVALUABLE | 0.606 | NOT_COMPUTED | 0.255 |
| E3 | 0.983 | NOT_EVALUABLE | 0.997 | NOT_COMPUTED | 0.463 |
| E4 | 0.983 | NOT_EVALUABLE | 0.997 | NOT_COMPUTED | 0.473 |

⚠ Relation Macro F1 is read with its per-class support table; classes with support <=3 are flagged.

## DIAGNOSTICS — detailed components

Legacy detailed metrics (typed canonical node, typed mentions, identity, relation confusion, qualifiers, alignment) remain in diagnostics.json.

### Relation classes (P&D held-out, E0)

| relation | support | tp | fp | fn | F1 | low support |
|---|---|---|---|---|---|---|
| acts_on | 12 | 4 | 0 | 8 | 0.500 |  |
| connected_to | 1 | 0 | 0 | 1 | 0.000 | yes |
| contrasts_with | 7 | 1 | 0 | 6 | 0.250 |  |
| decreases | 1 | 1 | 0 | 0 | 1.000 | yes |
| has_property | 1 | 1 | 0 | 0 | 1.000 | yes |
| has_purpose | 6 | 1 | 0 | 5 | 0.286 |  |
| increases | 1 | 0 | 0 | 1 | 0.000 | yes |
| is_a | 8 | 7 | 2 | 1 | 0.824 |  |
| part_of | 3 | 1 | 2 | 2 | 0.333 | yes |
| performs | 1 | 1 | 2 | 0 | 0.500 | yes |
| requires | 0 | 0 | 2 | 0 | n/a | excluded (no gold) |
| uses | 12 | 6 | 1 | 6 | 0.632 |  |

Micro P/R/F1 0.719/0.434/0.541; direction accuracy 0.957; no-prediction outcomes {'other': 8, 'no_relation': 6, 'rejected': 7}.

## AUDIT

Per-item traces, confusion matrices, provenance and hashes: `diagnostics.json`, `historical_replay.md`, and the explorer's Failure map / Gold relations tabs.

## ORGANISATION — structural view, not accuracy

Organisation metrics describe how the graph is arranged. They are not accuracy metrics and never enter a headline card.

- community modularity and stability
- centrality / PageRank / k-core
- centre / inner / middle / outer rings
- principle / core / detail distribution
- chapter importance trajectories
