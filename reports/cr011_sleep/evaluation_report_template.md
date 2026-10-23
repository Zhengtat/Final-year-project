# CR-011 Sleep Consolidation Evaluation Report

**Run / sleep ID:**  
**Source snapshot:**  
**Config version:**  
**STOP:**  
**Date:**  

## 1. Repository / data state

- CR-010 baseline:
- active term lexicon:
- baseline merge behaviour:
- SLEEP-240 manifest hash:
- dev/test grouping validation:

## 2. Candidate generation

| Arm/source | Candidate recall | Mean candidates/node | One-token recall | Cross-chapter recall |
|---|---:|---:|---:|---:|
| baseline | | | | |
| multi-signal | | | | |

## 3. Scorer calibration

- model:
- calibration:
- `t_auto`:
- `t_review`:
- dev precision at `t_auto`:
- 95% Wilson lower bound:
- predicted review volume:

## 4. Development arms

| Arm | Merge P | Merge R | Pair cluster F1 | Violation_different | Exact micro F1 | Human reviewed | LLM calls | Cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S0 | | | | | | | | |
| S1 | | | | | | | | |
| S2 | | | | | | | | |
| S3 | | | | | | | | |
| S4 | | | | | | | | |
| S5 | | | | | | | | |
| S5-OT | | | | | | | | |
| S5-TIME | | | | | | | | |
| S-AGG | | | | | | | | |

Selected development candidate:  
Selection rationale under pre-registered rule:  

## 5. Held-out results

Only frozen S0 and selected candidate belong here unless S-AGG was separately approved.

| Metric | S0 | Selected | Δ |
|---|---:|---:|---:|
| merge precision | | | |
| merge recall | | | |
| FMR accepted | | | |
| distinct-pair violation | | | |
| exact micro precision | | | |
| exact micro recall | | | |
| exact micro F1 | | | |
| macro F1 | | | |
| lenient metric | | | |
| one-token merge precision | | | |
| one-token merge recall | | | |
| cross-chapter merge precision | | | |
| auto-merge rate | | | |
| human-review rate | | | |
| candidate recall | | | |

## 6. SLEEP-240 strata

| Stratum | N | Merge P | Merge R | Distinct violations | Notes |
|---|---:|---:|---:|---:|---|
| R1–R3 deterministic | | | | | |
| high-similarity / R4 | | | | | |
| confusables / difficult negatives | | | | | |
| one-token / polysemy | | | | | |
| cross-chapter | | | | | |
| cluster-bridge / transitive-risk | | | | | |

## 7. Annotation agreement

- double-annotated held-out N:
- Cohen κ on SAME vs NOT_SAME:
- UNSURE count:
- adjudicated disagreements:

## 8. Provenance and reversibility

| Gate | Result |
|---|---:|
| known different violations | |
| evidence retention | |
| alias provenance completeness | |
| rollback round trip | |
| one-token critical false merges | |

Pre-sleep canonical hash:  
Post-rollback canonical hash:  
Match:  

## 9. Graph effects

- nodes before / after:
- edges before / after:
- duplicate edges collapsed:
- merge-created self-loops:
- suspected splits:
- CR-006 organisation replay diff:

## 10. Cost / effort

- LLM calls:
- input tokens:
- output tokens:
- API spend:
- annotation minutes:

## 11. Required plots

Attach generated files for:

- merge precision–recall curve;
- distinct-pair violation vs node reduction;
- merge recall vs human-reviewed pairs;
- quality vs API cost;
- one-token diagnostic.

## 12. Adoption gates

| Gate | Requirement | Observed | Pass? |
|---|---:|---:|---|
| known different violations | 0 | | |
| merge precision | ≥ 0.98 | | |
| Wilson lower bound | ≥ 0.95 when N permits | | |
| distinct-pair violation | ≤ 0.02 | | |
| exact micro F1 Δ | ≥ −0.01 | | |
| evidence retention | 1.00 | | |
| alias provenance | 1.00 | | |
| rollback round trip | 1.00 | | |
| one-token critical false merges | 0 | | |
| benefit | +0.05 recall OR −25% review load | | |

## 13. Result handoff

Do **not** silently promote a new production canonicalisation path. Report one of:

- `GATES_PASS — PRODUCTION MIGRATION ELIGIBLE, RESEARCH/OWNER APPROVAL REQUIRED`
- `GATES_FAIL — KEEP CURRENT PRODUCTION PATH`
- `AMBIGUOUS — RESEARCH DECISION REQUIRED`
