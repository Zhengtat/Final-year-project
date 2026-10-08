# CR-010 STOP 5 - architecture evaluation (evidence for Research; no architecture is selected here)

Definitions: `docs/cr010/STOP5_PREREGISTRATION.md` (committed before any STOP-5 call). Single annotator (annotator 1); REL-MAP-180 is relation-balanced, so rates are not natural prevalence. Gates use the 120 held-out items; the dev column is for information.

## 1. eRST expressibility, 2. semantic preservation (separate blocks)

| metric (valid-relation items) | dev | held-out |
|---|---|---|
| eRST expressibility | 14/48 = 29.2% | 22/81 = 27.2% |
| Semantic preservation | 2/48 = 4.2% | 7/81 = 8.6% |
| Mapping-loss rate | 46/48 = 95.8% | 74/81 = 91.4% |
| Critical-loss rate (survives = no and a loss category named) | 38/48 = 79.2% | 67/81 = 82.7% |
| Critical-loss Wilson 95% upper | 88.3% | 89.4% |
| Silent loss (survives = no, no category named) | 8/48 = 16.7% | 7/81 = 8.6% |
| Relation-collision rate (among expressible) | 2/14 = 14.3% | 3/22 = 13.6% |

Valid-relation items: dev 48, held-out 81; `other` judgements outside the gates: dev 3, held-out 10.

### Loss by category (held-out valid-relation items)

| category | count | rate | examples |
|---|---|---|---|
| taxonomy | 12 | 14.8% | RM006: is_a (low-speed terrestrial link / link); RM031: is_a (X.25 / virtual circuit) |
| part_whole_composition | 17 | 21.0% | RM002: part_of (teleconferencing / audio stream); RM004: part_of (edge cluster / edge presence) |
| mechanism | 27 | 33.3% | RM003: acts_on (message / request/reply protocol); RM027: has_purpose (throughput rate / ASIC) |
| network_topology | 5 | 6.2% | RM020: connected_to (Broadband Network Gateway / Internet); RM070: connected_to (peer / link) |
| identifier_semantics | 0 | 0.0% |  |
| encapsulation_payload_semantics | 0 | 0.0% |  |
| causal_sign_direction | 5 | 6.2% | RM005: causes (star topology / switch); RM011: causes (abstraction / virtual memory) |
| technical_dependency | 0 | 0.0% |  |
| tradeoff_semantics | 1 | 1.2% | RM098: contrasts_with (detection / correction) |
| pedagogical_prerequisite | 0 | 0.0% |  |
| principle_instance_organisation | 0 | 0.0% |  |

## 3. Reverse recoverability

Recovery table frozen from the 60 dev items (sha256 `a63935dee5208326...`) before use; applied once to held-out. **Macro F1 = 0.043** over 81 valid-relation items.

| relation | n | recovered | recall | status |
|---|---|---|---|---|
| part_of | 17 | 0 | 0.0% | FAIL |
| uses | 15 | 6 | 40.0% | FAIL |
| is_a | 12 | 0 | 0.0% | FAIL |
| has_purpose | 10 | 0 | 0.0% | FAIL |
| acts_on | 6 | 0 | 0.0% | FAIL |
| has_property | 6 | 6 | 100.0% | PASS |
| connected_to | 5 | 0 | 0.0% | FAIL |
| causes | 4 | 0 | 0.0% | INSUFFICIENT_SUPPORT |
| performs | 2 | 0 | 0.0% | INSUFFICIENT_SUPPORT |
| contrasts_with | 1 | 0 | 0.0% | INSUFFICIENT_SUPPORT |
| precedes | 1 | 0 | 0.0% | INSUFFICIENT_SUPPORT |
| decreases | 1 | 0 | 0.0% | INSUFFICIENT_SUPPORT |
| increases | 1 | 0 | 0.0% | INSUFFICIENT_SUPPORT |

## 4. Direct edge quality and architecture results (held-out 120 items)

| architecture | precision | recall | F1 | TP/FP/FN | cost | notes |
|---|---|---|---|---|---|---|
| current | 0.863 | 0.758 | 0.807 | 69/11/22 | stored run ($0 now) | frozen CR-009 outcome |
| erst_direct | 0.763 | 0.495 | 0.600 | 45/14/46 | $0.67 | outcomes {'edge': 59, 'no_erst_relation': 61} |
| dual | = current | = current | = current | = current | graph $3.13 + P3 sample $0.91 | concept layer unchanged by construction; discourse graph 2,024 edges (sha256 41cc5e7b...) |

Descriptive: erst_direct agrees with annotator 1 on applicability for 84/120; same label when both apply 21/27.

## 5. P3 candidate-routing utility (separate; from `reports/cr010_p3.md`)

P3-extra 2,547 pairs, 63/150 = 42.0% human-true (CI 33.3-49.7), about 1,070 true edges; eRST-linked units are a useful candidate-discovery signal. The conditional classifier on those pairs (recall 23/63, precision 23/32) is a classifier finding, not a representation failure. Recall is within the enumerated candidate universe only.

## 6. Full-replacement gate table (section 9)

| gate | threshold | observed | status |
|---|---|---|---|
| eRST expressibility | >= 0.90 | 27.2% | FAIL |
| Semantic preservation | >= 0.90 | 8.6% | FAIL |
| Mapping-loss rate | <= 0.10 | 91.4% | FAIL |
| Critical-loss Wilson 95% upper | <= 0.15 | 89.4% | FAIL |
| Reverse-mapping macro F1 | >= 0.90 | 4.3% | FAIL |
| Represented-relation recall (min over n>=5 relations) | >= 0.75 | 0.0% | FAIL (per-relation numerators in the report) |
| eRST-direct edge-F1 difference | >= -0.05 | -20.7% | FAIL |
| eRST-direct precision difference | >= -0.05 | -10.0% | FAIL |
| Mapping agreement kappa | >= 0.67 | None | NOT_EVALUABLE (NOT_EVALUABLE: no second human annotator) |
| Organisation/pedagogical information (vacuous: REL-MAP-180 has no pedagogical item) | no silent loss | {'silent': 0, 'flags': 0, 'items': 0} | PASS |

Mechanical eligibility under section 9 (all gates PASS): **NOT ELIGIBLE**. IAA gate: NOT_EVALUABLE (no second human annotator); FULL_ERST_REPLACEMENT is ineligible regardless.

## 7. Cost (this stage)

- erst_direct on 120 held-out items: $0.67. CR-010 totals: pair-recall sample $1.81, eRST graph $3.13, P3 classification $0.91.

## 8. Limitations and ambiguities for Research

- Single annotator; adjudicated = annotator 1; no kappa. The annotator marginals (applicability, survival) were seen before the metrics were defined; no per-split metric was.
- 'Critical loss' was not defined by the CR; the pre-registered reading is survives = no plus a named loss category. Silent losses are reported alongside; treating them as critical would raise the critical-loss rate to the mapping-loss rate.
- REL-MAP items are mostly single sentences; eRST relates discourse units, so low applicability is partly a property of the sampled evidence (same-sentence pairs from P0), not only of the inventory. P3 shows eRST structure is informative across sentences.
- erst_direct is run once, prompt frozen; no retuning. The gate difference compares presence of a discourse relation with presence of a concept relation, as the CR specifies for a direct-replacement test.
- Relations with n < 5 held-out valid instances are INSUFFICIENT_SUPPORT. 'other' judgements (relations the registry lacks) are outside every gate denominator.

Decision form for Research: `reports/cr010_decision_report_template.md` (unselected).
