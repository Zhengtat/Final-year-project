# RESEARCH HANDOVER — CR-017 Simplified End-to-End Evaluation Framework

**Project:** zt FYP / Conceptual Understanding Mapper (CUMAP)  
**From:** Research  
**To:** Implementation chat / `fyi implementation`  
**Date:** 2026-10-13  
**Status:** Approved research direction for implementation  
**Scope:** Evaluation and reporting only  
**Primary objective:** Reduce the main evaluation framework to five interpretable metrics while preserving the existing detailed metrics as secondary diagnostics.

> **CR-017 must not change model behaviour, extraction logic, pair-selection logic, relation semantics, canonicalisation rules, graph organisation, or any frozen historical result.**

---

# 0. Purpose

The current CUMAP evaluation framework contains many useful metrics, but the number of reported metrics makes it difficult to communicate the quality of the final system clearly.

CR-017 simplifies the **headline evaluation** to five metrics:

1. **Concept F1**
2. **Ancestor Hierarchy F1**
3. **Pair Recall**
4. **Relation Macro F1**
5. **Strict End-to-End Edge F1**

These five metrics correspond to five distinct questions:

```text
Concept F1
    ↓
Did the system discover the correct concepts?

Ancestor Hierarchy F1
    ↓
Are the concepts placed in the correct conceptual hierarchy?

Pair Recall
    ↓
Did true relationships reach the relation classifier?

Relation Macro F1
    ↓
When a correct pair was considered, was the correct relation type predicted?

Strict E2E Edge F1
    ↓
Did the entire system produce the correct final semantic edge?
```

The goal is to make the final thesis evaluation easier to interpret while preserving the detailed diagnostic metrics already implemented in CR-008–CR-016.

---

# 1. Research principle

The final evaluation should distinguish two broad dimensions:

```text
A. NODE STRUCTURE / HIERARCHY
B. EDGE SEMANTICS
```

with one final integration metric.

## A. Node Structure / Hierarchy

```text
Concept F1
Ancestor Hierarchy F1
```

## B. Edge Semantics

```text
Pair Recall
Relation Macro F1
```

## Integrated Pipeline

```text
Strict E2E Edge F1
```

No weighted composite score should be created.

Each metric should remain interpretable on its own.

---

# 2. Relationship to previous CRs

CR-017 does not replace earlier evaluation logic.

It consolidates existing metrics from:

```text
CR-008   canonical identity
CR-010   pair recall / relation architecture
CR-011   consolidation diagnostics
CR-012   end-to-end evaluation
CR-013   traceability
CR-014+  concept extraction improvements
```

The existing detailed metrics remain available for failure analysis.

CR-017 changes only:

```text
which metrics are presented as headline results
how the final evaluation report is structured
how hierarchy quality is measured
```

---

# 3. Metric 1 — Concept F1

## 3.1 Question

> Did the pipeline identify the correct concepts?

## 3.2 Definition

Use the existing frozen concept evaluation semantics.

Primary form:

```text
exact concept precision
exact concept recall
exact concept F1
```

Formally:

\[
P_C =
rac{|\hat{C} \cap C|}
{|\hat{C}|}
\]

\[
R_C =
rac{|\hat{C} \cap C|}
{|C|}
\]

\[
F1_C =
rac{2P_CR_C}{P_C + R_C}
\]

where:

```text
C      = gold concepts
Ĉ      = predicted concepts
```

Use the same canonical matching / span matching convention already selected by the active benchmark.

Do not silently change the definition of concept correctness inside CR-017.

---

# 4. Metric 2 — Ancestor Hierarchy F1

## 4.1 Question

> Are concepts positioned under the correct broader concepts in the hierarchy?

Direct-parent accuracy is too brittle as the primary hierarchy metric.

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

The prediction misses the immediate parent, but still captures a correct broader hierarchical relationship.

Therefore CR-017 uses **ancestor relationships**.

## 4.2 Hierarchical edges included

STOP 1 must reconcile which active relations define the hierarchy.

Expected candidates include:

```text
is_a
taxonomy / subtype relations
```

Potential inclusion of:

```text
instantiates
```

must be treated separately unless Research confirms that it belongs in the same ancestor hierarchy.

Do NOT automatically include:

```text
part_of
requires
uses
causes
prerequisite
connected_to
```

because these represent different semantic structures.

The default hierarchy should therefore be the **taxonomy / abstraction hierarchy**, not every directed edge in the KG.

## 4.3 Ancestor-pair construction

For each graph:

1. take the frozen set of hierarchy relations;
2. compute transitive closure;
3. convert the hierarchy into ancestor pairs:

```text
(descendant, ancestor)
```

Example:

```text
TCP → Transport Protocol
Transport Protocol → Protocol
```

produces:

```text
(TCP, Transport Protocol)
(TCP, Protocol)
(Transport Protocol, Protocol)
```

Do this for both gold and predicted graphs.

## 4.4 Metric

Let:

```text
A_gold = gold ancestor pairs
A_pred = predicted ancestor pairs
```

Then:

\[
P_H =
rac{|A_{pred} \cap A_{gold}|}
{|A_{pred}|}
\]

\[
R_H =
rac{|A_{pred} \cap A_{gold}|}
{|A_{gold}|}
\]

\[
F1_H =
rac{2P_HR_H}
{P_H + R_H}
\]

Report:

```text
Ancestor Hierarchy Precision
Ancestor Hierarchy Recall
Ancestor Hierarchy F1
```

Only **Ancestor Hierarchy F1** appears in the main five-metric table.

## 4.5 Identity handling

Hierarchy scoring requires correct concept identity.

Before comparing ancestor pairs:

```text
map mentions / aliases to canonical concept IDs
```

A hierarchy link to the wrong canonical concept is incorrect.

Do not award partial credit purely for lexical similarity.

## 4.6 Missing concepts

If a gold concept is not extracted:

```text
all ancestor relationships involving that concept are missed
```

This is intentional.

The hierarchy metric therefore evaluates the hierarchy of the actual constructed graph, not an oracle-node hierarchy.

Optionally retain an **oracle-node hierarchy F1** as a diagnostic, but it must not replace the headline metric.

---

# 5. Metric 3 — Pair Recall

## 5.1 Question

> Given that both endpoint concepts exist, did the system send their pair to relation classification?

This metric isolates pair-selection failures from relation-classifier failures.

## 5.2 Definition

Denominator:

```text
gold semantic edges whose two canonical endpoint nodes
exist in the predicted node set
```

Numerator:

```text
those gold endpoint pairs that reached
the relation-classification stage
```

Therefore:

\[
R_{pair} =
rac{
	ext{gold-related endpoint pairs delivered to classifier}
}{
	ext{gold-related endpoint pairs whose predicted endpoints exist}
}
\]

Pair Recall is not:

```text
relation recall
classifier recall
edge recall
```

It only evaluates **delivery to classification**.

## 5.3 Pair orientation

For a gold relation:

```text
A → B
```

pair recall normally asks whether the unordered endpoint pair:

```text
{A, B}
```

reached relation classification.

Direction is evaluated later.

If the production pair selector explicitly treats orientation as part of eligibility, report that separately as a diagnostic rather than changing the primary pair-recall definition.

## 5.4 Trace requirement

Every pair must be traceable as:

```text
generated
eligible
ranked
selected / not selected
classifier reached / not reached
```

CR-013 trace fields should be reused.

---

# 6. Metric 4 — Relation Macro F1

## 6.1 Question

> For candidate pairs with correct endpoint concepts, how well does the classifier identify relation types across the ontology?

Macro F1 is selected over micro F1 for the headline metric because common relation classes must not dominate the evaluation.

## 6.2 Evaluation population

Evaluate relation classification **conditional on correct gold endpoints being available to the classifier**.

This separates:

```text
pair-selection failure
```

from:

```text
relation-classification failure
```

If a pair never reaches the classifier, it belongs to Pair Recall, not the conditional relation-classifier score.

## 6.3 Per-relation metrics

For each relation type \(r\):

\[
P_r =
rac{TP_r}{TP_r + FP_r}
\]

\[
R_r =
rac{TP_r}{TP_r + FN_r}
\]

\[
F1_r =
rac{2P_rR_r}{P_r + R_r}
\]

Then:

\[
MacroF1_R =
rac{1}{|R|}
\sum_{r \in R} F1_r
\]

where \(R\) is the set of evaluable relation classes.

## 6.4 Rare classes

STOP 1 must report how relation classes with zero or very low gold support are currently handled.

Preferred reporting:

```text
Macro F1 across relation classes represented in gold
```

Also report support count per class.

Do not silently remove poorly performing classes simply because they are rare.

If a minimum-support rule is needed for a secondary stable-macro diagnostic, define it separately and do not replace the full macro score.

## 6.5 Direction

Primary Relation Macro F1 evaluates the **semantic relation label**.

Direction Accuracy remains a diagnostic.

However, if the registry represents reverse directions as distinct labels, STOP 1 must reconcile the current scoring implementation before changing anything.

Do not silently double-count direction.

---

# 7. Metric 5 — Strict End-to-End Edge F1

## 7.1 Question

> Did the complete pipeline construct the correct final semantic graph edges?

Retain the existing CR-012 `STRICT_E2E_EDGE_F1`.

A predicted directional edge is correct only if:

```text
correct canonical source concept
AND
correct canonical target concept
AND
correct semantic relation
AND
correct direction
AND
required endpoint/type/qualifier constraints where applicable
```

For symmetric relations, endpoint orientation is ignored.

## 7.2 Definition

\[
P_{E2E} =
rac{
	ext{correct final predicted edges}
}{
	ext{all final predicted edges}
}
\]

\[
R_{E2E} =
rac{
	ext{correct final predicted edges}
}{
	ext{all gold edges}
}
\]

\[
F1_{E2E} =
rac{
2P_{E2E}R_{E2E}
}{
P_{E2E}+R_{E2E}
}
\]

This remains the main **integrated** system metric.

---

# 8. Final headline scorecard

Every end-to-end experiment should produce this table:

| Category | Metric | Value |
|---|---|---:|
| Node extraction | Concept F1 | |
| Node organisation | Ancestor Hierarchy F1 | |
| Edge opportunity | Pair Recall | |
| Edge semantics | Relation Macro F1 | |
| Whole pipeline | Strict E2E Edge F1 | |

Where useful also report 95% confidence intervals.

Do not create:

```text
average of five metrics
weighted overall score
single percentage "CUMAP accuracy"
```

The five metrics answer different questions and should remain separate.

---

# 9. Secondary diagnostics

The following metrics remain available but are removed from the headline scorecard.

## 9.1 Node / identity diagnostics

```text
concept precision
concept recall
canonical-node P/R/F1
pairwise identity P/R/F1
B³ cluster P/R/F1
concept type accuracy
```

## 9.2 Hierarchy diagnostics

```text
direct-parent accuracy / F1
tier accuracy / macro F1
cycle violation rate
orphan count
oracle-node ancestor F1
```

## 9.3 Pair-selection diagnostics

```text
candidate-pair volume
selection rate
pair precision estimate where sampled
rank distribution
budget cutoff
missed-relation sample
```

## 9.4 Relation diagnostics

```text
relation micro F1
per-relation precision / recall / F1
relation confusion matrix
direction accuracy
qualifier accuracy
NO_RELATION rate
OTHER rate
```

## 9.5 Grounding / safety diagnostics

```text
unsupported node rate
unsupported edge rate
resolvable evidence rate
type/domain/range violation rate
provenance completeness
```

## 9.6 Organisation diagnostics

Do not mix these with semantic accuracy:

```text
community modularity
community stability
centrality / PageRank
k-core
centre / inner / middle / outer rings
principle/core/detail distribution
chapter-specific importance trajectories
```

These remain organisation/analysis views.

---

# 10. Organisation is not a sixth accuracy metric

CR-017 explicitly separates:

```text
semantic graph correctness
```

from:

```text
graph organisation / visualisation
```

Communities, centre-periphery rings, chapter trajectories and structural importance are useful views of the graph, but they do not directly tell us whether extracted facts are true.

Therefore they must not enter:

```text
Concept F1
Hierarchy F1
Pair Recall
Relation Macro F1
Strict E2E Edge F1
```

The only organisation structure currently promoted into the main accuracy framework is the **explicit taxonomy/ancestor hierarchy**, because that represents semantic conceptual organisation rather than structural centrality.

---

# 11. Evaluation levels

CR-017 reports three levels:

```text
LEVEL 1 — HEADLINE
five metrics only

LEVEL 2 — DIAGNOSTIC
component-specific metrics

LEVEL 3 — AUDIT
per-item errors, traces, confusion matrices, provenance
```

This should be reflected in generated reports and, where applicable, the UI.

---

# 12. Required stage-loss interpretation

The five metrics should be interpreted sequentially:

```text
Low Concept F1
    → extraction problem

Good Concept F1
but low Ancestor Hierarchy F1
    → taxonomy / hierarchy placement problem

Good concepts
but low Pair Recall
    → candidate pair selection / budget problem

Good Pair Recall
but low Relation Macro F1
    → relation classifier problem

Good component metrics
but low Strict E2E Edge F1
    → compounded identity / direction / validation / integration losses
```

Reports should explicitly use this interpretation.

---

# 13. Relationship to CR-012 oracle waterfall

Keep the CR-012 oracle matrix as a diagnostic experiment:

```text
E0 full workflow

E1 oracle concepts

E2 oracle canonicalisation

E3 oracle pair coverage

E4 relation-classification ceiling
```

CR-017 does not remove it.

Instead:

```text
five headline metrics
    = what the final system achieves

oracle waterfall
    = why the final system loses performance
```

---

# 14. Error taxonomy

Continue using earliest-failure attribution where available:

```text
N0 concept absent
N1 wrong/incomplete concept span

C0 canonicalisation split
C1 false merge

H0 hierarchy parent/ancestor missing
H1 hierarchy false ancestor
H2 hierarchy cycle / structural violation

P0 pair not delivered

R0 classifier predicts NO_RELATION
R1 wrong relation
R2 wrong direction
R3 qualifier/type failure

E0 evidence/provenance failure
```

`H0–H2` are the only new CR-017 error categories.

Do not double count a downstream failure when an earlier failure already explains it.

---

# 15. Gold requirements

CR-017 requires gold support for:

## Concept F1

```text
concept mentions / canonical concepts
```

## Ancestor Hierarchy F1

```text
taxonomy hierarchy / parent relationships
```

## Pair Recall

```text
gold semantic relations
```

## Relation Macro F1

```text
gold relation labels
```

## Strict E2E Edge F1

```text
canonical endpoints
relation
direction
required qualifiers/types
```

STOP 1 must audit whether the current P&D-E2E gold has enough explicit taxonomy/hierarchy information for `Ancestor Hierarchy F1`.

If not, do not infer a gold hierarchy from predicted output.

Return to Research with:

```text
HIERARCHY_GOLD_GAP
```

and describe what additional annotation would be needed.

---

# 16. Hierarchy annotation policy if additional gold is needed

If the current benchmark does not contain a sufficient hierarchy:

Annotate only the taxonomy/abstraction structure needed for this metric.

Suggested schema:

```text
child_concept_id
parent_concept_id
relation
evidence_sentence_ids
notes
```

Allowed relation initially:

```text
is_a
```

Additional hierarchy relations require Research approval.

Do not use:

```text
book chapter order
graph centrality
community membership
principle/core/detail tier
embedding similarity
```

as substitute gold.

---

# 17. Confidence intervals

Where sample size permits, report uncertainty for the five headline metrics.

Preferred:

```text
section-level bootstrap
```

for full P&D evaluation, because mentions/edges within one section are not independent.

Record:

```text
point estimate
95% interval
bootstrap unit
number of resamples
seed
```

If only a small number of sections is available, mark the interval as descriptive.

---

# 18. Comparisons across CRs

When comparing two systems:

```text
System A
System B
```

report:

| Metric | A | B | Δ |
|---|---:|---:|---:|
| Concept F1 | | | |
| Ancestor Hierarchy F1 | | | |
| Pair Recall | | | |
| Relation Macro F1 | | | |
| Strict E2E Edge F1 | | | |

Use the same gold and scoring definitions.

Do not compare metrics across benchmarks with incompatible gold without explicit qualification.

---

# 19. STOP sequence

## STOP 1 — Evaluation reconciliation

Implementation must inspect the repository and report:

1. current exact implementation of concept F1;
2. current canonical identity mapping;
3. current taxonomy / hierarchy relation inventory;
4. whether current gold supports ancestor closure;
5. current pair-recall implementation;
6. current relation macro/micro scoring;
7. current `STRICT_E2E_EDGE_F1`;
8. existing confidence interval/bootstrap code;
9. existing CR-012 oracle implementation;
10. current reports/UI consuming old metric names.

No model/API calls.

Return:

```text
reports/cr017/STOP1_RECONCILIATION.md
```

Do not implement scoring changes before STOP 1 confirms hierarchy semantics.

## STOP 2 — Implement Ancestor Hierarchy F1

Build and test:

```text
hierarchy relation filter
cycle handling
transitive closure
ancestor pair generation
canonical ID alignment
P/R/F1 scorer
```

Use fixtures only first.

Required tests are listed below.

Return the fixture results and any hierarchy-gold limitation to Research.

## STOP 3 — Unified five-metric evaluator

Implement one evaluation entry point producing:

```text
concept_f1
ancestor_hierarchy_f1
pair_recall
relation_macro_f1
strict_e2e_edge_f1
```

plus the detailed diagnostics.

Machine-readable output should contain both headline and diagnostic sections.

Example:

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

Do not delete old metric outputs if other reports depend on them.

## STOP 4 — Historical replay

Replay the evaluator on existing frozen results where gold supports all five metrics.

Do not rerun models.

Use saved predictions/artifacts only.

Purpose:

```text
validate scorer
check compatibility
create historical five-metric table
```

If hierarchy gold is absent for historical runs, mark:

```text
NOT_EVALUABLE
```

Do not generate pseudo-gold.

## STOP 5 — Report/UI integration

Update final evaluation outputs to show:

```text
HEADLINE SCORECARD
five metrics

DIAGNOSTICS
expandable / appendix

ORGANISATION
separate visualisation section
```

Do not remove access to older detailed metrics.

## STOP 6 — Final validation

Verify:

```text
metric definitions frozen
tests passing
lint clean
historical results unchanged
no model behaviour changed
no old artifacts overwritten
headline values reproducible from machine-readable outputs
```

Produce:

```text
reports/cr017/FINAL_DECISION_EVIDENCE.md
```

---

# 20. Minimum test contract

## Concept F1

- existing scorer behavior unchanged;
- exact match fixture;
- alias/canonical mapping fixture;
- missing concept produces FN;
- extra concept produces FP.

## Ancestor Hierarchy F1

### Exact hierarchy

Gold:

```text
A → B → C
```

Prediction identical.

Expected:

```text
P = R = F1 = 1.0
```

### Skipped direct parent

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
(A, C) receives ancestor credit
(A, B) is missed
```

### False ancestor

Prediction adds:

```text
A → D
```

Expected false-positive ancestor pair(s).

### Missing node

Gold node absent from prediction.

Expected hierarchy recall loss.

### Alias identity

Predicted alias maps to correct canonical node before hierarchy comparison.

### Cycle

Prediction:

```text
A → B
B → A
```

Must not silently produce unrestricted closure.

Expected:

```text
cycle violation recorded
```

Define deterministic handling in STOP 1/2.

### Non-hierarchy relation

```text
A uses B
```

must not create ancestor relationship.

## Pair Recall

- both endpoints exist + pair selected → TP opportunity;
- endpoints exist + pair not selected → miss;
- missing endpoint excluded from pair-recall denominator;
- duplicate directional pair does not inflate recall;
- trace shows selected/not-selected state.

## Relation Macro F1

- balanced fixture across multiple relation labels;
- frequent class does not dominate macro F1;
- unsupported class handling deterministic;
- NO_RELATION handling reconciled with existing scorer;
- direction does not get double-counted unless encoded as label.

## Strict E2E Edge F1

Existing CR-012 tests remain valid.

Add compatibility test proving CR-017 returns the same strict E2E score as the existing scorer.

---

# 21. Required artifacts

Expected paths; adapt to repository conventions where needed.

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
    FINAL_DECISION_EVIDENCE.md

tests/fixtures/cr017/
    hierarchy/
    pair_recall/
    relation_macro/
    e2e/
```

Machine-readable:

```text
reports/cr017/headline_metrics.json
reports/cr017/diagnostics.json
```

---

# 22. Recommended final report layout

## Main Results

| Metric | Score | 95% CI |
|---|---:|---:|
| Concept F1 | | |
| Ancestor Hierarchy F1 | | |
| Pair Recall | | |
| Relation Macro F1 | | |
| Strict E2E Edge F1 | | |

Then one short interpretation paragraph.

Example structure:

```text
Concept extraction achieved ...
Hierarchy F1 indicates ...
Pair recall shows ...
Conditional relation classification achieved ...
The integrated strict edge score was ...
```

## Error Analysis

Use detailed metrics and earliest-failure taxonomy.

Do not repeat every diagnostic metric in the main table.

## Knowledge Organisation

Report separately:

```text
communities
principle/core/detail
structural importance
chapter evolution
```

These are explanatory/organisational views, not headline semantic-accuracy scores.

---

# 23. What is deliberately removed from the headline evaluation

The following are **not deleted**; they are demoted to diagnostics:

```text
canonical-node F1
direct-parent F1
tier macro F1
prerequisite F1
cycle violation rate
relation micro F1
direction accuracy
qualifier accuracy
unsupported-edge rate
community modularity
centrality metrics
ring distribution
```

Reason:

```text
they are useful for explaining failures,
but are not necessary to communicate the main quality
of the Expert-KG construction pipeline.
```

---

# 24. Non-goals

CR-017 must not:

- change concept extraction;
- change concept proposal;
- change verifier/pruner thresholds;
- change canonicalisation;
- change pair ranking;
- change pair budget;
- change relation prompts/models;
- change relation registry;
- change eRST architecture;
- change principles/communities;
- modify held-out predictions;
- generate new model outputs to improve historical scores;
- combine the five metrics into one score.

---

# 25. Definition of done

CR-017 is complete when:

```text
the five headline metrics are implemented;

Concept F1 remains definition-compatible
with existing evaluation;

Ancestor Hierarchy F1 is defined over an explicit,
frozen hierarchy relation set;

Pair Recall remains isolated from missing-node errors;

Relation Macro F1 is conditional on correct endpoint pairs
reaching classification;

Strict E2E Edge F1 remains definition-compatible
with CR-012;

old detailed metrics remain accessible as diagnostics;

organisation metrics are clearly separated from accuracy;

historical replay does not alter historical model outputs;

all scores have provenance to frozen prediction and gold artifacts;

tests pass and lint is clean.
```

---

# 26. Immediate instruction to Implementation

Start with **STOP 1 only**.

The most important question to resolve before implementation is:

> **Does the current gold benchmark contain an explicit enough taxonomy hierarchy to compute Ancestor Hierarchy F1 without inventing hierarchy labels?**

Return the answer together with:

```text
current hierarchy relations
gold coverage
current scoring code
affected reports
proposed implementation paths
```

Do not infer hierarchy from communities, PageRank, chapter order, principle tiers, or predicted graph structure.

Once Research confirms the hierarchy semantics, proceed to STOP 2.
