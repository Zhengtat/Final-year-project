# CR-017 — Simplified End-to-End Evaluation Framework

**Status:** implementation specification derived from the approved CR-017 Research handover, 2026-10-13.  
**Branch:** `cr-017-simplified-evaluation`, created from the frozen repository state after the active modelling CR is complete. Merge only after STOP 6 validation and Research/owner approval; tag `cr-017-complete`.  
**Scope:** evaluation and reporting only.  
**Primary objective:** reduce the headline CUMAP evaluation to five interpretable metrics while preserving existing detailed metrics as secondary diagnostics.  
**Production safety:** CR-017 must not change model behaviour, extraction logic, pair-selection logic, relation semantics, canonicalisation, graph organisation, or any frozen historical prediction.

---

## 1. Purpose

CR-017 standardises the main end-to-end CUMAP evaluation around five headline metrics:

1. **Concept F1**
2. **Ancestor Hierarchy F1**
3. **Pair Recall**
4. **Relation Macro F1**
5. **Strict End-to-End Edge F1**

They answer five different questions:

```text
Concept F1
→ Did the system discover the correct concepts?

Ancestor Hierarchy F1
→ Are the concepts placed under the correct broader concepts?

Pair Recall
→ Did true relationships reach relation classification?

Relation Macro F1
→ When a correct pair was considered, was the correct relation type predicted?

Strict E2E Edge F1
→ Did the complete system create the correct final semantic edge?
```

Do not combine these into one weighted score or average.

The final evaluation must distinguish:

```text
NODE STRUCTURE / HIERARCHY
    Concept F1
    Ancestor Hierarchy F1

EDGE SEMANTICS
    Pair Recall
    Relation Macro F1

WHOLE PIPELINE
    Strict E2E Edge F1
```

---

## 2. Non-goals

CR-017 must not:

- change concept extraction;
- change concept proposal;
- change verifier/pruner thresholds;
- change canonicalisation;
- change pair generation/ranking/budget;
- change relation prompts/models;
- change the relation registry;
- change eRST/discourse architecture;
- change graph organisation;
- change principles/communities;
- change held-out predictions;
- generate new model outputs to improve historical scores;
- overwrite historical evaluation artifacts;
- combine the five headline metrics into a single composite score.

CR-017 is a scorer/reporting change only.

---

## 3. Order of work and STOP points

Commit per step with prefix:

```text
CR-017:
```

### ⛔ STOP 1 — Evaluation reconciliation

Inspect the actual repository before implementing any scoring change.

Report:

1. current exact Concept F1 implementation;
2. current canonical identity mapping;
3. current taxonomy/hierarchy relation inventory;
4. whether current gold supports ancestor closure;
5. current Pair Recall implementation;
6. current relation macro/micro scoring;
7. current `STRICT_E2E_EDGE_F1`;
8. existing confidence-interval/bootstrap implementation;
9. existing CR-012 oracle implementation;
10. all reports/UI consuming old metric names.

Return:

```text
reports/cr017/STOP1_RECONCILIATION.md
reports/cr017/hierarchy_gold_audit.md
```

No model/API calls.

Do **not** implement hierarchy scoring until STOP 1 establishes which hierarchy relations and gold are valid.

If the gold does not explicitly support the hierarchy metric, return:

```text
HIERARCHY_GOLD_GAP
→ missing hierarchy information
→ sections/datasets affected
→ additional annotation required
→ RESEARCH DECISION REQUIRED
```

Do not infer hierarchy from predicted output.

### ⛔ STOP 2 — Ancestor Hierarchy F1

Implement only after hierarchy semantics are confirmed.

Build:

```text
hierarchy relation filter
cycle detection/handling
canonical-ID alignment
transitive closure
ancestor-pair generation
hierarchy precision
hierarchy recall
hierarchy F1
```

Run fixture tests first.

Return:

```text
fixture results
cycle-handling result
gold-support status
ancestor-pair examples
```

Do not run models.

### ⛔ STOP 3 — Unified five-metric evaluator

Implement a single evaluation entry point that returns:

```text
concept_f1
ancestor_hierarchy_f1
pair_recall
relation_macro_f1
strict_e2e_edge_f1
```

plus existing diagnostics.

Machine-readable output:

```json
{
  "headline": {
    "concept_f1": {},
    "ancestor_hierarchy_f1": {},
    "pair_recall": {},
    "relation_macro_f1": {},
    "strict_e2e_edge_f1": {}
  },
  "diagnostics": {}
}
```

Do not delete legacy outputs used by existing reports.

### ⛔ STOP 4 — Historical replay

Replay the new evaluator over already-frozen prediction artifacts only.

Do not rerun models.

Purpose:

```text
validate scoring compatibility
verify metric definitions
produce historical five-metric tables
detect report breakage
```

Where hierarchy gold is missing:

```text
ancestor_hierarchy_f1 = NOT_EVALUABLE
```

Do not create pseudo-gold.

Return:

```text
reports/cr017/historical_replay.md
reports/cr017/headline_metrics.json
reports/cr017/diagnostics.json
```

### ⛔ STOP 5 — Report/UI integration

Update evaluation reports and relevant UI surfaces to separate:

```text
HEADLINE
five metrics only

DIAGNOSTICS
detailed component metrics

ORGANISATION
separate graph-analysis/visualisation metrics
```

Do not remove access to old detailed metrics.

### ⛔ STOP 6 — Final validation

Verify:

```text
metric definitions frozen
tests passing
lint clean
historical prediction artifacts unchanged
historical metric outputs reproducible
no model behaviour changed
no old artifact overwritten
headline values reproducible from machine-readable outputs
```

Produce:

```text
reports/cr017/FINAL_DECISION_EVIDENCE.md
```

---

## 4. Headline scorecard

Every full evaluation should expose:

| Category | Metric | Value | 95% CI |
|---|---|---:|---:|
| Node extraction | Concept F1 | | |
| Node organisation | Ancestor Hierarchy F1 | | |
| Edge opportunity | Pair Recall | | |
| Edge semantics | Relation Macro F1 | | |
| Whole pipeline | Strict E2E Edge F1 | | |

Do not create:

```text
average of the five
weighted overall score
single “CUMAP accuracy” percentage
```

Each metric remains independent and interpretable.

---

## 5. Metric 1 — Concept F1

### 5.1 Question

> Did the pipeline identify the correct concepts?

### 5.2 Implementation rule

Reuse the existing frozen concept-scoring semantics.

Report:

```text
exact concept precision
exact concept recall
exact concept F1
```

Let:

```text
C_gold = gold concepts
C_pred = predicted concepts
```

Then:

```text
P_C = |C_pred ∩ C_gold| / |C_pred|
R_C = |C_pred ∩ C_gold| / |C_gold|
F1_C = 2 * P_C * R_C / (P_C + R_C)
```

Use the same canonical/span matching convention already selected by the active benchmark.

CR-017 must not silently redefine concept correctness.

---

## 6. Metric 2 — Ancestor Hierarchy F1

### 6.1 Question

> Are concepts positioned under the correct broader concepts in the taxonomy/abstraction hierarchy?

Direct-parent scoring alone is too brittle.

Example:

```text
Gold:
TCP
 ↓
Transport Protocol
 ↓
Protocol

Prediction:
TCP
 ↓
Protocol
```

The prediction still captures the broader ancestor relation:

```text
(TCP, Protocol)
```

even though it missed the intermediate parent.

### 6.2 Hierarchy relation set

STOP 1 must identify the actual active hierarchy relations.

Expected default:

```text
is_a
taxonomy/subtype relation(s), if present in the active registry
```

Possible relation:

```text
instantiates
```

must remain separate unless Research explicitly approves inclusion.

Do not automatically include:

```text
part_of
requires
uses
causes
prerequisite_of
connected_to
```

because these are not taxonomy/abstraction relations.

Freeze the final hierarchy relation set in config before scoring.

### 6.3 Canonical identity alignment

Before hierarchy comparison:

```text
surface/alias
→ canonical concept ID
```

A hierarchy edge to the wrong canonical concept is incorrect.

Do not award lexical-similarity partial credit.

### 6.4 Ancestor-pair construction

For both gold and prediction:

1. filter to the frozen hierarchy relation set;
2. detect cycles;
3. compute transitive closure only under the approved cycle policy;
4. emit:

```text
(descendant_id, ancestor_id)
```

Example:

```text
A → B
B → C
```

produces:

```text
(A, B)
(A, C)
(B, C)
```

### 6.5 Metric

Let:

```text
A_gold = gold ancestor pairs
A_pred = predicted ancestor pairs
```

Then:

```text
P_H = |A_pred ∩ A_gold| / |A_pred|
R_H = |A_pred ∩ A_gold| / |A_gold|
F1_H = 2 * P_H * R_H / (P_H + R_H)
```

Report:

```text
ancestor_hierarchy_precision
ancestor_hierarchy_recall
ancestor_hierarchy_f1
```

Only `ancestor_hierarchy_f1` appears in the five-metric headline table.

### 6.6 Missing concepts

If a gold concept is absent from prediction:

```text
all gold ancestor pairs involving that concept are missed
```

This is intentional.

The headline hierarchy score evaluates the hierarchy of the graph actually constructed.

An oracle-node hierarchy score may exist as a diagnostic only.

### 6.7 Cycle handling

STOP 1/2 must define deterministic cycle handling based on repository semantics.

Requirements:

- cycles are explicitly detected;
- cycle violations are reported;
- closure must not silently expand indefinitely;
- cycle handling must be deterministic and tested.

If current Research semantics do not determine a valid policy:

```text
RESEARCH DECISION REQUIRED
```

---

## 7. Metric 3 — Pair Recall

### 7.1 Question

> Given that both endpoint concepts exist, did their pair reach relation classification?

This isolates pair-selection loss from concept-extraction loss and relation-classifier loss.

### 7.2 Denominator

Use:

```text
gold semantic edges
whose two canonical endpoint nodes
exist in the predicted node set
```

### 7.3 Numerator

Use:

```text
gold-related endpoint pairs
that reached relation classification
```

Therefore:

```text
Pair Recall
=
gold-related endpoint pairs delivered to classifier
/
gold-related endpoint pairs whose predicted endpoints exist
```

### 7.4 Pair orientation

Primary Pair Recall is based on the unordered endpoint pair:

```text
{A, B}
```

Direction is evaluated later.

If production selection explicitly treats orientation as part of eligibility, expose that as a diagnostic rather than silently changing the primary Pair Recall definition.

### 7.5 Trace requirement

Every pair should be traceable through:

```text
generated
eligible
ranked
selected/not-selected
classifier reached/not reached
```

Reuse existing trace fields where available.

---

## 8. Metric 4 — Relation Macro F1

### 8.1 Question

> For gold endpoint pairs that reached the classifier, how well does the classifier predict semantic relation types across the ontology?

### 8.2 Evaluation population

Evaluate only where:

```text
correct gold endpoint concepts exist
AND
their pair reached relation classification
```

If the pair never reaches classification, that is a Pair Recall failure.

### 8.3 Per-class scoring

For each evaluable relation class `r`:

```text
P_r = TP_r / (TP_r + FP_r)
R_r = TP_r / (TP_r + FN_r)
F1_r = 2 * P_r * R_r / (P_r + R_r)
```

Then:

```text
Relation Macro F1
=
mean(F1_r over evaluable relation classes)
```

### 8.4 Rare classes

Preferred headline definition:

```text
macro F1 across relation classes represented in gold
```

Also report support per relation.

Do not remove rare/poorly performing classes merely because their scores are low.

If a stable minimum-support macro is useful, expose it as a secondary diagnostic only.

### 8.5 Direction

Primary Relation Macro F1 measures semantic relation label.

Direction Accuracy remains diagnostic unless the active registry encodes direction through separate labels.

STOP 1 must reconcile current scorer behaviour to avoid double-counting direction.

### 8.6 NO_RELATION / OTHER

STOP 1 must record the current scorer semantics for:

```text
NO_RELATION
OTHER
```

Do not change their handling inside CR-017 without Research approval.

---

## 9. Metric 5 — Strict End-to-End Edge F1

### 9.1 Question

> Did the complete system construct the correct final semantic graph edge?

Reuse the existing frozen CR-012 strict scorer.

A directional predicted edge is correct only if required fields match:

```text
canonical source
canonical target
semantic relation
direction
required endpoint/type constraints
required qualifiers
```

For symmetric relations, orientation is ignored according to the frozen scorer.

### 9.2 Metric

```text
P_E2E = correct final predicted edges / all final predicted edges
R_E2E = correct final predicted edges / all gold edges
F1_E2E = 2 * P_E2E * R_E2E / (P_E2E + R_E2E)
```

CR-017 must return the same strict E2E result as the pre-existing scorer for the same frozen inputs.

---

## 10. Three evaluation levels

Generated outputs should expose:

### LEVEL 1 — Headline

Exactly the five main metrics.

### LEVEL 2 — Diagnostics

Detailed stage/component metrics.

### LEVEL 3 — Audit

Per-item traces, confusion matrices, failure attribution, provenance, hashes, and scorer configuration.

The report/UI should make these levels visually distinct.

---

## 11. Secondary diagnostics

Keep existing detailed metrics accessible.

### Node / identity

```text
concept precision
concept recall
canonical-node P/R/F1
pairwise identity P/R/F1
B³ cluster P/R/F1
concept type accuracy
```

### Hierarchy

```text
direct-parent accuracy/F1
tier accuracy/macro F1
cycle violation rate
orphan count
oracle-node ancestor F1
```

### Pair selection

```text
candidate-pair volume
selection rate
pair precision estimate where sampled
rank distribution
budget cutoff
missed-relation sample
```

### Relation

```text
relation micro F1
per-relation precision/recall/F1
relation confusion matrix
direction accuracy
qualifier accuracy
NO_RELATION rate
OTHER rate
```

### Grounding / safety

```text
unsupported node rate
unsupported edge rate
resolvable evidence rate
type/domain/range violation rate
provenance completeness
```

### Organisation

Keep separate from accuracy:

```text
community modularity
community stability
centrality/PageRank
k-core
centre/inner/middle/outer rings
principle/core/detail distribution
chapter importance trajectories
```

Organisation metrics must not enter the five headline semantic-accuracy metrics.

---

## 12. Stage-loss interpretation

Reports should interpret the headline metrics sequentially:

```text
Low Concept F1
→ extraction problem

Good Concept F1
but low Ancestor Hierarchy F1
→ hierarchy/taxonomy placement problem

Good concepts
but low Pair Recall
→ pair generation/selection/budget problem

Good Pair Recall
but low Relation Macro F1
→ relation classifier problem

Good components
but low Strict E2E Edge F1
→ compounded identity/direction/validation/integration problem
```

Use these as interpretive cues, not as proof of hidden model reasoning.

---

## 13. CR-012 oracle waterfall

Keep the existing oracle waterfall as a diagnostic:

```text
E0 full workflow
E1 oracle concepts
E2 oracle canonicalisation
E3 oracle pair coverage
E4 relation-classification ceiling
```

Interpretation:

```text
five headline metrics
= what the final system achieves

oracle waterfall
= why the final system loses performance
```

Do not replace or remove the oracle evaluation.

---

## 14. Error taxonomy

Continue earliest-causal attribution:

```text
N0 concept absent
N1 wrong/incomplete span

C0 canonicalisation split
C1 false merge

H0 hierarchy parent/ancestor missing
H1 false hierarchy ancestor
H2 hierarchy cycle/structural violation

P0 pair not delivered

R0 classifier predicts NO_RELATION
R1 wrong relation
R2 wrong direction
R3 qualifier/type failure

E0 evidence/provenance failure
```

`H0–H2` are the CR-017 additions.

Do not double-count downstream effects when an earlier failure already explains the error.

---

## 15. Gold requirements

The evaluator must verify that gold supports each headline metric.

### Concept F1

Requires:

```text
concept mentions / canonical concepts
```

### Ancestor Hierarchy F1

Requires:

```text
explicit taxonomy/hierarchy relationships
```

### Pair Recall

Requires:

```text
gold semantic relations
```

### Relation Macro F1

Requires:

```text
gold relation labels
```

### Strict E2E Edge F1

Requires:

```text
canonical endpoints
relation
direction
required types/qualifiers
```

STOP 1 must explicitly audit whether current P&D-E2E gold is sufficient for ancestor closure.

If not:

```text
ancestor_hierarchy_f1 = NOT_EVALUABLE
```

and return:

```text
HIERARCHY_GOLD_GAP
```

Do not infer gold hierarchy from predicted graph structure.

---

## 16. Hierarchy annotation delta, if required

Only if Research approves additional hierarchy gold.

Suggested fields:

```text
child_concept_id
parent_concept_id
relation
evidence_sentence_ids
notes
```

Initially allowed relation:

```text
is_a
```

Additional hierarchy relations require Research approval.

Do not derive gold from:

```text
chapter order
graph centrality
community membership
principle/core/detail tier
embedding similarity
predicted hierarchy
```

Human gold remains human-owned.

---

## 17. Confidence intervals

Where sample size permits, report 95% uncertainty for each headline metric.

Preferred bootstrap unit:

```text
section
```

Record:

```text
point estimate
CI lower
CI upper
bootstrap unit
number of resamples
seed
```

Mentions/edges within one section must not be treated as independent bootstrap observations.

If only a small number of sections exists, mark the interval as descriptive.

---

## 18. Historical/system comparisons

When comparing systems A and B, use:

| Metric | A | B | Δ |
|---|---:|---:|---:|
| Concept F1 | | | |
| Ancestor Hierarchy F1 | | | |
| Pair Recall | | | |
| Relation Macro F1 | | | |
| Strict E2E Edge F1 | | | |

Use identical gold and scorer definitions.

Do not compare values across incompatible benchmarks without explicit qualification.

---

## 19. Machine-readable output contract

Recommended output:

```json
{
  "schema_version": "cr017-v1",
  "run_id": "...",
  "prediction_artifact": "...",
  "gold_artifact": "...",
  "scorer_version": "...",
  "headline": {
    "concept_f1": {
      "precision": null,
      "recall": null,
      "f1": null,
      "ci95": null
    },
    "ancestor_hierarchy_f1": {
      "precision": null,
      "recall": null,
      "f1": null,
      "ci95": null,
      "status": "OK"
    },
    "pair_recall": {
      "recall": null,
      "ci95": null
    },
    "relation_macro_f1": {
      "f1": null,
      "ci95": null,
      "classes": {}
    },
    "strict_e2e_edge_f1": {
      "precision": null,
      "recall": null,
      "f1": null,
      "ci95": null
    }
  },
  "diagnostics": {},
  "provenance": {
    "prediction_hash": "...",
    "gold_hash": "...",
    "config_hash": "...",
    "code_revision": "..."
  }
}
```

If hierarchy gold is absent:

```json
{
  "status": "NOT_EVALUABLE",
  "reason": "HIERARCHY_GOLD_GAP"
}
```

Do not substitute zero for not-evaluable metrics.

---

## 20. Config contract

Create a CR-017 config containing at least:

```yaml
version: 1

headline:
  concept_f1: true
  ancestor_hierarchy_f1: true
  pair_recall: true
  relation_macro_f1: true
  strict_e2e_edge_f1: true

hierarchy:
  relations: STOP1_DISCOVER
  include_instantiates: false
  cycle_policy: STOP1_DISCOVER
  canonical_alignment: true

relation_macro:
  class_population: represented_in_gold
  direction_handling: STOP1_DISCOVER
  no_relation_handling: STOP1_DISCOVER
  other_handling: STOP1_DISCOVER

bootstrap:
  enabled: true
  unit: section
  resamples: STOP1_RECONCILE
  seed: STOP1_RECONCILE

compatibility:
  retain_legacy_outputs: true
  rerun_models: false
  overwrite_historical_artifacts: false
```

Do not fill `STOP1_DISCOVER` values from assumptions.

---

## 21. Report layout

### Main Results

| Metric | Score | 95% CI |
|---|---:|---:|
| Concept F1 | | |
| Ancestor Hierarchy F1 | | |
| Pair Recall | | |
| Relation Macro F1 | | |
| Strict E2E Edge F1 | | |

Then one concise interpretation paragraph.

### Error Analysis

Use:

- diagnostics;
- failure taxonomy;
- oracle waterfall;
- confusion matrices;
- per-stage misses.

### Knowledge Organisation

Keep separate:

```text
communities
principle/core/detail
structural importance
chapter evolution
rings/centrality
```

Organisation belongs in explanatory/structural analysis, not in the headline semantic scorecard.

---

## 22. Required repository artifacts

Expected semantics; reconcile exact paths at STOP 1.

```text
docs/change-requests/
    CR-017-simplified-evaluation-framework.md

configs/
    cr017_evaluation.yaml

src/cumap/evaluation/
    hierarchy.py
    headline_metrics.py

reports/cr017/
    STOP1_RECONCILIATION.md
    hierarchy_gold_audit.md
    historical_replay.md
    headline_metrics.json
    diagnostics.json
    FINAL_DECISION_EVIDENCE.md

tests/fixtures/cr017/
    hierarchy/
    pair_recall/
    relation_macro/
    e2e/
```

Do not create duplicate infrastructure if equivalent modules already exist.

---

## 23. Minimum test contract

### Concept F1

- existing scorer behaviour unchanged;
- exact-match fixture;
- alias/canonical mapping fixture;
- missing concept → FN;
- extra concept → FP.

### Ancestor Hierarchy F1

#### Exact hierarchy

Gold:

```text
A → B → C
```

Prediction identical.

Expected:

```text
P = 1
R = 1
F1 = 1
```

#### Skipped direct parent

Gold:

```text
A → B → C
```

Prediction:

```text
A → C
```

Expected:

```text
(A, C) gets ancestor credit
(A, B) is missed
```

#### False ancestor

Prediction adds:

```text
A → D
```

Expected false-positive ancestor pair.

#### Missing node

Gold node absent from prediction → hierarchy recall loss.

#### Alias identity

Predicted alias resolves to correct canonical node before hierarchy comparison.

#### Cycle

Prediction:

```text
A → B
B → A
```

Expected:

```text
cycle violation recorded
closure handled deterministically
```

#### Non-hierarchy relation

```text
A uses B
```

must not create an ancestor pair.

### Pair Recall

- endpoints exist + pair selected → counted as delivered;
- endpoints exist + pair not selected → miss;
- missing endpoint excluded from denominator;
- duplicate directional pair does not inflate recall;
- trace exposes selected/not-selected state.

### Relation Macro F1

- balanced multi-label fixture;
- frequent class does not dominate macro score;
- unsupported/zero-support handling deterministic;
- NO_RELATION semantics match current scorer;
- direction not double-counted unless relation encoding requires it.

### Strict E2E Edge F1

- all existing CR-012 tests remain valid;
- compatibility fixture proves CR-017 returns exactly the same strict E2E score on identical artifacts.

### Historical safety

- no historical prediction file modified;
- no model inference invoked;
- historical replay consumes saved artifacts only;
- legacy report fields remain available;
- machine-readable headline values reproduce rendered report values.

---

## 24. UI/report integration

Where a UI exists, expose:

```text
HEADLINE
five metric cards/table

DIAGNOSTICS
expandable detailed metrics

AUDIT
per-item traces/provenance

ORGANISATION
separate graph-analysis panel
```

Do not visually imply that organisation metrics are additional accuracy metrics.

Do not remove legacy detailed data required for debugging.

---

## 25. Required visualisations

Generate only from real evaluator outputs.

Recommended:

1. **Five-metric scorecard**.
2. **Cross-system five-metric comparison**.
3. **Stage-loss waterfall**:
   ```text
   concepts
   → hierarchy
   → pair delivery
   → relation classification
   → strict final edges
   ```
4. **Relation-class macro breakdown**.
5. **Hierarchy error breakdown**:
   ```text
   H0 missing ancestor
   H1 false ancestor
   H2 cycle
   ```
6. **Oracle waterfall**, kept as diagnostic.

Do not fabricate metric values.

---

## 26. Interpretation rules

Implementation-generated prose must not overstate what the metrics prove.

Allowed:

```text
Pair Recall is lower than Concept F1, indicating additional loss before relation classification.
```

Avoid unsupported claims such as:

```text
the LLM failed to reason
```

unless the diagnostic evidence supports them.

The five metrics should answer:

1. Were the concepts correct?
2. Was their taxonomy correct?
3. Were relation opportunities delivered?
4. Were relation labels correct?
5. Was the final graph edge correct?

Do not merge these into one “accuracy” claim.

---

## 27. Historical replay rules

Historical replay is scorer-only.

Allowed:

```text
load frozen prediction artifact
load compatible gold
run CR-017 evaluator
write new CR-017 report
```

Forbidden:

```text
rerun extraction
rerun relation classification
modify predictions
repair old outputs
fill missing hierarchy from predictions
```

If one metric is unsupported for a historical benchmark:

```text
NOT_EVALUABLE
```

rather than fabricated or inferred data.

---

## 28. Final decision evidence

`FINAL_DECISION_EVIDENCE.md` should answer:

1. Are all five headline metrics implemented?
2. Is Concept F1 definition-compatible with the prior scorer?
3. Which relation set defines the hierarchy?
4. Does the current benchmark provide valid hierarchy gold?
5. Does Pair Recall exclude missing-endpoint cases correctly?
6. Is Relation Macro F1 conditional on delivered gold endpoint pairs?
7. Does strict E2E remain identical to CR-012?
8. Are legacy diagnostics still accessible?
9. Are organisation metrics separated from semantic accuracy?
10. Can every headline value be reproduced from frozen artifacts?

Final status should be one of:

```text
CR017_COMPLETE
CR017_COMPLETE_WITH_HIERARCHY_NOT_EVALUABLE
RESEARCH_DECISION_REQUIRED
```

---

## 29. Definition of done

CR-017 is complete only when:

- the five headline metrics exist;
- Concept F1 remains compatible with the frozen concept scorer;
- Ancestor Hierarchy F1 uses an explicit frozen hierarchy relation set;
- missing hierarchy gold produces `NOT_EVALUABLE`, not pseudo-gold;
- Pair Recall excludes missing-node failures from its denominator;
- Relation Macro F1 is conditional on correct endpoint pairs reaching classification;
- Strict E2E Edge F1 remains compatible with CR-012;
- detailed legacy metrics remain accessible;
- organisation metrics are clearly separated from accuracy;
- historical replay changes no model outputs;
- no historical prediction artifact is overwritten;
- all metric outputs preserve prediction/gold/config/code provenance;
- headline report values are reproducible from machine-readable files;
- tests pass;
- lint is clean.

---

## 30. Immediate coding-agent instruction

Read this CR and the CR-017 Research handover before modifying evaluation code.

Execute **STOP 1 only** first.

Your first task is to answer:

> **Does the current gold benchmark contain an explicit enough taxonomy hierarchy to compute Ancestor Hierarchy F1 without inventing hierarchy labels?**

Return:

```text
reports/cr017/STOP1_RECONCILIATION.md
reports/cr017/hierarchy_gold_audit.md
```

containing:

1. current Concept F1 scorer path/definition;
2. current canonical-ID alignment code;
3. current hierarchy relation inventory;
4. hierarchy gold coverage;
5. current Pair Recall implementation;
6. current relation macro/micro scorer;
7. current strict E2E scorer;
8. current bootstrap/CI implementation;
9. current CR-012 oracle code;
10. affected reports/UI;
11. proposed repository-native implementation paths.

Before Research approval:

```text
do not implement hierarchy closure
do not change metric definitions
do not rerun models
do not generate new gold
do not infer hierarchy from predictions
do not overwrite historical outputs
```

If hierarchy semantics or gold are insufficient:

```text
HIERARCHY_GOLD_GAP
→ repository evidence
→ what is missing
→ minimum additional annotation required
→ affected metrics/reports
→ RESEARCH DECISION REQUIRED
```

Once Research confirms the hierarchy semantics, proceed to STOP 2.
