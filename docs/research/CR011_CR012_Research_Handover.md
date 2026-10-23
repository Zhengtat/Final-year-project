# RESEARCH HANDOVER — CR-011 Amendments + CR-012 End-to-End Evaluation

**Project:** H420020 — Conceptual Understanding Mapper  
**From:** Research chat  
**To:** `fyi implementation`  
**Date:** 2026-10-08  
**Authority:** Research defines method, metrics, evaluation design, experiment arms, thresholds/gates, benchmark use, and interpretation. Implementation may make editorial/repository-level changes only.

---

## 0. Purpose of this handover

The owner has made the following scope decision:

> **CR-011 remains the graph reorganisation / sleep-consolidation CR.**  
> **CR-012 becomes the end-to-end evaluation CR for the complete Expert-KG workflow.**

Do **not** merge CR-011 and CR-012.

The scientific sequence is:

```text
CR-009
Concept extraction / Generator → Verifier → Pruner
        ↓
CR-010
Node recall + relation architecture + pair recall
        ↓
CR-011
Global graph consolidation / reorganisation ("sleep")
        ↓
CR-012
End-to-end evaluation of the entire frozen workflow
```

CR-011 changes the graph.

CR-012 asks whether the resulting graph is actually correct.

---

# PART A — REQUIRED AMENDMENTS TO CR-011

The current CR-011 draft is fundamentally approved. Its central architecture remains:

```text
CR-009 / CR-010 extraction
        ↓
provisional nodes + accumulated evidence
        ↓
immutable pre-sleep snapshot
        ↓
multi-signal identity candidates
        ↓
CR-008 SAME / DIFFERENT guards
        ↓
calibrated identity scoring
        ↓
selective adjudication
        ↓
cluster-consistency validation
        ↓
transactional merge / re-key
        ↓
rollback verification
        ↓
new canonical graph version
        ↓
organisation replay
```

CR-011 is therefore still a **graph reorganisation / evidence-grounded consolidation** CR, not an end-to-end evaluation CR.

## A1. Clarify CR-011's evaluation scope

Add explicitly under **Non-goals**:

> **CR-011 does not evaluate the accuracy of the complete Expert-KG construction workflow.**
>
> SLEEP-240 and the CR-011 held-out study evaluate only the correctness, safety and benefit of the consolidation/reorganisation stage.
>
> End-to-end accuracy from raw text → concepts → canonical nodes → candidate pairs → typed relations → consolidated graph is owned by CR-012.

Do **not** remove CR-011 evaluation. CR-011 still needs its own experiment because it must prove that consolidation does not create false identities.

## A2. Keep SLEEP-240 unchanged

Do not move SLEEP-240 into CR-012.

SLEEP-240 remains the consolidation benchmark:

```text
40  R1–R3 deterministic candidates
40  semantic/R4 candidates
40  difficult confusables
40  one-token/polysemy
40  cross-chapter/long-distance
40  cluster-bridge/transitive-risk
---
240 total

80 development
160 held-out
```

The split remains grouped by candidate cluster / normalised-form family rather than random pair.

Interpretation:

```text
SLEEP-240 asks:
"Did CR-011 merge/reorganise identity correctly?"

CR-012 asks:
"Is the final knowledge graph correct?"
```

These are complementary, not duplicate experiments.

## A3. Reframe concept F1 in CR-011 as a non-regression metric

Keep the CR-011 projection of canonical nodes back onto section-level concept predictions and continue reporting:

```text
exact micro P/R/F1
macro F1
lenient F1
```

However, change the interpretation. For CR-011 these scores are **safety / non-regression checks**, not the headline measurement of CUM's overall accuracy.

CR-011's principal outcomes remain:

```text
merge precision
merge recall
distinct-pair violation
cluster quality
review burden
provenance retention
rollback correctness
```

## A4. Broaden the post-sleep organisation replay

After consolidation, recompute all **available derived organisation views** whose inputs are affected by canonical node identity.

At minimum:

```text
CR-006:
- sphere
- centre / inner / middle / outer assignments
- structural review flags

CR-004, if implemented at this stage:
- communities
- node breadth
- centrality-based organisation inputs
- tier/principle-support statistics that depend on canonical graph identity
```

Important invariant:

```text
canonical graph
      ↓
organisation

NOT:

organisation
      ↓
identity merge
```

Organisation may change because CR-011 changed node identity. Organisation must **never become evidence that two nodes are identical**.

## A5. Add a formal CR-012 evaluation handoff

CR-011 STOP 5 must emit an immutable evaluation handoff for CR-012.

Recommended path:

```text
reports/cr011_sleep/CR012_EVAL_HANDOFF.json
```

Required fields:

```text
source_run_id
sleep_id

pre_sleep_snapshot_path
post_sleep_snapshot_path

pre_sleep_graph_hash
post_sleep_graph_hash

cr009_config_id/hash
cr010_config_id/hash
cr011_config_id/hash

relation_registry_version
term_lexicon_version

model identifiers
prompt hashes
random / deterministic settings where applicable

merge_transaction_manifest
id_map
edge_rewrite_manifest
suspected_split_manifest

organisation_pre_path
organisation_post_path

evidence/provenance manifest
```

Purpose: CR-012 must be able to compare the same extraction before and after CR-011 without rerunning extraction.

```text
same extraction
      ↓
pre-sleep graph

versus

same extraction
      ↓
CR-011
      ↓
post-sleep graph
```

This prevents LLM run-to-run stochasticity from contaminating the measured effect of consolidation.

## A6. Seal CR-012 benchmark gold away from CR-011

Add a benchmark-isolation rule:

> CR-012 evaluation data must not influence CR-011 development.

The following must not be used for CR-011 feature design, candidate rules, threshold selection, arm selection, LLM prompts, term-lexicon additions, merge guards, or manual exceptions if they are later used as CR-012 held-out evaluation:

```text
SciNLP test split
SciERC evaluation split
SciER evaluation split
OSKGC/Text2KGBench test data
P&D-E2E held-out annotations
```

CR-011 may continue using its own historical development labels and SLEEP-240 development partition.

## A7. Do not change CR-011 adoption gates

The existing CR-011 safety philosophy remains.

False merge is treated as more dangerous than missed merge for the canonical Expert KG.

Do not relax:

```text
CR-008 `different` veto
cluster-consistency guard
one-token protections
provenance requirements
rollback requirements
```

CR-011 may validly conclude **no production change**.

---

# PART B — CREATE CR-012

## B1. CR title

Create:

> **CR-012 — End-to-End Expert Knowledge Graph Evaluation and Error Attribution**

Suggested repository path:

```text
docs/change-requests/CR-012-end-to-end-evaluation.md
```

The implementation chat owns the actual CR file and companion artifacts.

## B2. CR-012 objective

CR-012 evaluates the complete **frozen** Expert-KG workflow.

The new headline question is:

> **Given raw technical text, how close is the final CUM knowledge graph to an independently annotated gold knowledge graph?**

The evaluated workflow must be whatever architecture was actually selected after CR-010 and CR-011. Do not reconstruct an idealised pipeline from old CR specifications.

Component-level scores remain diagnostic only.

## B3. CR-012 is evaluation-only

CR-012 must not silently improve the system.

Freeze this rule:

> No methodological change may be introduced after held-out results are inspected.

Allowed:

```text
fixing a scorer implementation bug before evaluation
correcting an external dataset loader
logging missing metadata
fixing a deterministic implementation defect where expected behaviour is already specified
```

Not allowed:

```text
changing prompts because test recall is poor
adding a new cue after seeing test errors
changing pair-selection thresholds
adding aliases from held-out gold
changing relation definitions
changing consolidation thresholds
selecting a different model after seeing held-out results
```

Any discovered improvement becomes CR-013 or later.

## B4. Research questions

Freeze four RQs.

### RQ1 — End-to-end accuracy

> How accurately does the complete CUM pipeline reconstruct a gold knowledge graph from raw technical text?

### RQ2 — Error attribution

> How much of the final end-to-end error is introduced by concept extraction, canonicalisation, candidate-pair generation, relation classification and graph consolidation?

### RQ3 — Generalisation

> Does the CUM workflow generalise beyond the Peterson & Davie networking textbook to independently annotated technical/scientific documents?

### RQ4 — CR-011 contribution

> Does CR-011 consolidation improve, preserve or damage the final graph when the same pre-sleep extraction is evaluated before and after consolidation?

## B5. Benchmark strategy

Use two **primary** evaluation tracks and optional secondary diagnostics.

### Primary external benchmark: SciNLP

Role:

```text
raw technical full text
→ concept/entity extraction
→ typed relations
→ strict end-to-end evaluation
```

SciNLP is the main external generalisation benchmark.

### Primary in-domain benchmark: P&D-E2E

Create a new exhaustive held-out gold set from Peterson & Davie.

Role:

```text
raw networking textbook text
→ complete CUM workflow
→ compare with exhaustive networking gold
```

This is the main evidence that CUM works for its actual intended Expert-KG domain.

### Secondary benchmarks

Use if practical:

```text
SciERC
    canonicalisation / coreference diagnostic

SciER
    full-text scientific robustness / OOD diagnostic

OSKGC or Text2KGBench
    ontology/schema-conformance diagnostic
```

Do not make completion of all optional datasets a prerequisite for CR-012 completion.

Minimum valid CR-012:

```text
SciNLP
+
P&D-E2E
```

## B6. Benchmark adapters

Do not force external datasets into CUM's networking ontology.

Implement a benchmark adapter interface.

Conceptually:

```python
class BenchmarkAdapter:
    def load_documents(...)
    def entity_types(...)
    def relation_registry(...)
    def gold_mentions(...)
    def gold_relations(...)
    def gold_clusters(...)      # optional
    def official_score(...)
```

For SciNLP, the pipeline receives the **SciNLP schema**.

For Peterson & Davie, it receives the **CUM registry**.

The workflow architecture must remain the same.

Allowed benchmark-specific differences:

```text
dataset loader
schema/config
label names
official scoring conversion
input formatting needed by dataset
```

Not allowed:

```text
benchmark-specific extraction algorithm
benchmark-specific prompt tuned on test
special pair strategy for test examples
manual relation translation into networking labels
```

The scientific question is whether the architecture transfers.

## B7. SciNLP version audit

At STOP 1, inspect the exact dataset release rather than assuming paper counts.

Record:

```text
repository / download source
version / commit
document count
entity count
relation count
train/dev/test split
relation inventory
entity-type inventory
licence
file hashes
official scorer version
```

If published-paper counts and repository counts differ:

> report both and evaluate against the exact frozen repository version used.

Do not silently mix paper statistics with a different repository release.

## B8. P&D-E2E construction

Create a new **exhaustive in-domain gold set**.

Existing P&D spot checks mainly estimate the precision of predictions already emitted. They do not measure facts the system completely missed.

P&D-E2E must therefore begin from raw text and annotate all relevant targets.

### Pilot

Select:

```text
2 sections
```

from already-developed material.

Purpose:

```text
debug annotation rules
debug scorer
estimate annotation time
resolve ambiguity
```

Pilot cannot contribute to the final held-out score.

### Held-out P&D-E2E

Select approximately:

```text
6–8 sections
```

from chapters not used for CR-005–011 tuning where feasible.

Section selection must occur **before viewing final CUM predictions**.

Selection may be stratified by chapter, section length, subsection structure, or technical density, but not by observed system success/failure.

## B9. P&D-E2E annotation schema

For every selected held-out section, exhaustively annotate:

```text
CONCEPTS
- exact surface span
- canonical concept ID
- canonical name
- aliases / mention group
- node type
- evidence location

RELATIONS
- source canonical concept
- target canonical concept
- relation
- direction
- required qualifier(s)
- supporting evidence span

CANONICALISATION
- which mentions/names belong to the same concept
- explicit NOT_SAME where needed for ambiguous/confusable cases
```

Do **not** enumerate every possible `NO_RELATION` pair.

Negative pairs should be sampled separately where required for diagnostics.

## B10. Human gold policy

P&D-E2E final gold remains human-owned.

LLMs may prefill, suggest, highlight, or triage, but may not become the sole reported ground truth.

If possible, independently double annotate approximately:

```text
25–30% of concept annotations
25–30% of relation annotations
```

Report:

```text
concept agreement
relation agreement
direction agreement
identity SAME/NOT_SAME agreement
```

If a second human is unavailable, report the limitation.

Do not count an LLM as the second human.

Code never writes automatically into `data/gold`.

## B11. Headline metric

The primary CUM metric is:

> **STRICT_E2E_EDGE_F1**

A predicted edge is correct only when all required components are correct.

For directional relations:

```text
correct source canonical concept
AND
correct target canonical concept
AND
correct endpoint types where required
AND
correct semantic relation
AND
correct direction
```

For symmetric relations, endpoint orientation is ignored.

Formally:

\[
P_{E2E}=\frac{\text{correct final predicted edges}}{\text{all final predicted edges}}
\]

\[
R_{E2E}=\frac{\text{correct final predicted edges}}{\text{all gold edges}}
\]

\[
F1_{E2E}=\frac{2P_{E2E}R_{E2E}}{P_{E2E}+R_{E2E}}
\]

This is the main CR-012 result.

Do not replace it with a weighted combination of component scores.

## B12. Secondary whole-graph metrics

Also report:

```text
NODE / CONCEPT
- exact concept P/R/F1
- concept type accuracy
- canonical node P/R/F1 where defined

IDENTITY
- pairwise identity P/R/F1
- B³ cluster P/R/F1 if suitable gold clusters exist

PAIR SELECTION
- pair recall among gold edges whose endpoints exist

RELATION
- relation P/R/F1 conditional on correct gold endpoints
- direction accuracy
- per-relation confusion

GROUNDING
- unsupported node rate
- unsupported edge rate

ONTOLOGY / VALIDATION
- type-constraint violation rate
- invalid relation/domain-range rate

PROVENANCE
- provenance completeness
- resolvable evidence rate

SYSTEM
- API spend
- runtime
- cost per correct final edge
```

These explain the headline E2E score. They do not replace it.

## B13. Error taxonomy

Every end-to-end gold miss should, where possible, receive exactly one primary earliest-failure category:

```text
N0  concept not extracted

N1  concept extracted with wrong/incomplete span

C0  canonicalisation split
    same real concept became multiple nodes

C1  canonicalisation false merge
    different concepts became one node

P0  both nodes exist but pair never proposed

R0  pair proposed but classifier chose NO_RELATION

R1  wrong relation

R2  wrong relation direction

R3  qualifier/type failure

S0  correct pre-sleep structure damaged by CR-011

S1  CR-011 failed to repair a duplicate/split it was expected to repair

E0  evidence/provenance invalid
```

Use the **earliest causal failure** as the main attribution category.

This prevents one missing concept from being counted again as a pair-recall failure and relation failure.

## B14. Oracle experiment matrix

Freeze the oracle experiment before held-out evaluation.

### E0 — full workflow

```text
raw text
→ frozen production pipeline
→ CR-011
→ final graph
```

Headline system.

### E1 — oracle concepts

Provide gold concept mentions/types.

Then run normal:

```text
canonicalisation
pair selection
relation classification
consolidation
```

Approximate contribution:

\[
E1-E0
\]

= loss caused by concept extraction.

### E2 — oracle canonicalisation

Provide:

```text
gold concept mentions
gold canonical identity clusters
```

Then run:

```text
pair selection
relations
downstream processing
```

Approximate:

\[
E2-E1
\]

= canonicalisation contribution.

Use only where benchmark gold supports this. P&D-E2E should support it.

### E3 — oracle pair coverage

Provide gold nodes/canonicalisation and **force all gold endpoint pairs to reach relation classification**.

Do not reveal the gold relation label.

Difference:

\[
E3-E2
\]

= pair-selection loss.

### E4 — relation-classification ceiling

Provide correct endpoint pairs.

The relation classifier must independently predict:

```text
relation
direction
qualifiers as required
```

This measures relation-classification quality once upstream discovery is perfect.

## B15. Oracle leakage rule

Oracle information is injected **only into the stage it replaces**.

For E3, the gold endpoint pair may be provided, but the gold relation must not be exposed.

Likewise gold test concepts may not appear as few-shot prompt examples.

Add tests for this.

## B16. CR-011 before/after evaluation

Use the exact handoff produced by CR-011.

For each eligible P&D-E2E section:

```text
same frozen extraction
       │
       ├──── PRE-SLEEP graph → score
       │
       ▼
     CR-011
       │
       ▼
POST-SLEEP graph → score
```

Report:

\[
\Delta F1_{sleep}=F1_{post}-F1_{pre}
\]

Also report CR-011 operations against gold:

```text
true duplicate merges
false merges
duplicate identities repaired
correct split warnings
valid nodes damaged
valid relations damaged
relations preserved through re-key
provenance retained
node-count change
edge-count change
```

This is CR-012's evaluation of CR-011. It does not replace SLEEP-240.

## B17. Stability experiment

CR-010 demonstrated meaningful baseline run-to-run variation, so CR-012 must explicitly quantify stochasticity.

Before held-out results are viewed, freeze a small stability subset.

Recommended:

```text
2 SciNLP documents
2 P&D-E2E sections
```

Run E0 three independent times under the same frozen configuration.

Report:

```text
mean STRICT_E2E_EDGE_F1
standard deviation

node-set Jaccard
edge-set Jaccard

canonicalisation disagreement rate
relation disagreement rate
```

For edge sets:

\[
J(E_i,E_j)=\frac{|E_i\cap E_j|}{|E_i\cup E_j|}
\]

Do not select the best run. All runs must be retained.

## B18. Confidence intervals

Use the natural grouping unit.

```text
SciNLP: bootstrap by document
P&D-E2E: bootstrap by section
pre-sleep/post-sleep: paired bootstrap by the same section
```

Do not bootstrap individual edges as independent observations.

Report 95% intervals.

## B19. Unsupported-fact evaluation

Define:

\[
UnsupportedNodeRate=\frac{\text{predicted canonical nodes without adequate source support}}{\text{all predicted canonical nodes}}
\]

\[
UnsupportedEdgeRate=\frac{\text{predicted edges without adequate source support}}{\text{all predicted edges}}
\]

For P&D-E2E, use human gold/evidence spans.

Do not reward graph density. An edge with plausible semantics but no support in the evaluated text is an error.

## B20. Provenance evaluation

For each final predicted graph object, validate required provenance.

For edges:

```text
source document
section
supporting evidence
run_id
relation registry version
model/prompt/config provenance
source/target canonical lineage
merge/re-key lineage if affected by CR-011
```

Define:

\[
ProvenanceCompleteness=\frac{\text{objects with all required provenance}}{\text{all evaluated graph objects}}
\]

Target:

```text
1.00
```

This is a structural quality requirement rather than the primary accuracy score.

## B21. External baseline policy

Where an external benchmark has official published systems, report them separately.

Format:

```text
Published benchmark baseline
CUM result
```

Do not imply a strict leaderboard comparison unless the same data version, split, evaluation script, and scoring definition have been verified.

CR-012 STOP 1 must specifically check these conditions.

## B22. No benchmark-based redesign

After held-out data has been evaluated:

```text
NO prompt tuning
NO threshold changes
NO relation-registry edits
NO term-lexicon edits
NO candidate-cue additions
NO merge guard changes
```

based on test failures.

Instead produce:

```text
CR012_FAILURE_ANALYSIS.md
```

with proposed future fixes. Those may become CR-013.

## B23. CR-012 STOP sequence

### STOP 1 — repository + benchmark reconciliation — $0

Report:

```text
final CR-010 architecture
final CR-011 state/tag/config
production concept configuration
production relation registry
canonicalisation config
sleep config

CR-011 CR012_EVAL_HANDOFF availability

SciNLP exact release/commit
actual dataset counts
official split
official scorer
licence
hashes

SciERC/SciER/OSKGC versions if enabled

expected documents
expected calls
expected tokens
expected spend
```

No paid evaluation.

Return to Research if benchmark facts materially contradict this specification.

### STOP 2 — evaluation infrastructure + P&D gold freeze

Implement:

```text
benchmark adapter framework
SciNLP adapter
P&D-E2E adapter
official-compatible metric scorer
oracle injection framework
pre/post-sleep comparison
failure-attribution framework
bootstrap implementation
stability runner
```

Also:

```text
freeze P&D pilot sections
freeze P&D held-out sections
produce blind annotation sheets/codebook
```

Owner/humans complete P&D gold.

No held-out pipeline evaluation yet.

### STOP 3 — scorer validation + development rehearsal

Use only:

```text
SciNLP train/dev
P&D-E2E pilot
```

Validate:

```text
span matching
entity typing
alias projection
canonical cluster scoring
relation matching
direction matching
symmetric relation handling
qualifiers
pair-recall denominator
oracle isolation
failure attribution
pre/post snapshot identity
bootstrap
cost estimation
```

Freeze evaluation code/config afterward.

### STOP 4 — held-out end-to-end evaluation

Run held-out **once** under the freeze.

Required:

```text
E0
E1
E2 where supported
E3
E4
```

on:

```text
SciNLP test
P&D-E2E held-out
```

Do not tune from results.

Report:

```text
STRICT_E2E_EDGE P/R/F1
node metrics
identity metrics
pair recall
conditional relation metrics
unsupported fact metrics
provenance
oracle decomposition
confidence intervals
cost
```

### STOP 5 — CR-011 contribution + stability + final analysis

Evaluate pre-sleep vs post-sleep on identical extraction outputs.

Run frozen stability repetitions.

Produce:

```text
error waterfall
failure taxonomy
pre/post sleep delta
stability results
external-vs-domain comparison
cost analysis
final limitations
```

CR-012 ends with analysis only.

No automatic architecture modification.

## B24. Suggested visualisations

All charts must be created only after results exist.

Required:

```text
1. End-to-end F1:
   external vs P&D

2. Oracle waterfall:
   E0 → E1 → E2 → E3 → E4

3. Earliest-failure distribution:
   concept / identity / pair / relation / sleep / provenance

4. Pre-sleep vs post-sleep P/R/F1

5. Run-to-run stability:
   F1 + edge Jaccard

6. Cost vs correct final edges
```

Do not invent data.

## B25. Cost contract

CR-012 should maximise offline/local scoring.

Initial planning only:

```text
STOP 1                     $0
evaluation infrastructure  $0
local scoring              $0

pilot API work             soft target ≤ $5
held-out runs              soft target ≤ $15
stability repetitions      soft target ≤ $8

warning threshold          $20
hard cap                   $30
```

These are project planning limits, not literature-derived thresholds.

STOP 1 must replace these rough estimates with repository-specific preflight numbers.

No paid call before preflight.

## B26. Required CR-012 artifacts

Implementation should create at least:

```text
docs/change-requests/
    CR-012-end-to-end-evaluation.md

PROMPT-CR-012.md

configs/
    cr012_e2e_eval.yaml

docs/annotation/
    pd_e2e_codebook.md

data/interim/checks/cr012/
    pd_e2e_pilot_blind.csv
    pd_e2e_test_blind.csv

reports/cr012/
    STOP1_BENCHMARK_AUDIT.md
    dataset_manifest.json
    scorer_validation.md
    external_e2e.md
    pd_e2e.md
    oracle_error_attribution.md
    sleep_before_after.md
    stability.md
    unsupported_facts.md
    provenance.md
    cost.md
    FINAL_EVALUATION.md
    CR012_FAILURE_ANALYSIS.md

tests/fixtures/cr012/
```

Actual source module names should follow the existing repository package layout rather than introducing a parallel architecture unnecessarily.

## B27. Minimum tests

Required test coverage:

```text
DATASET / SPLITS
- dataset hash/version recorded
- test examples cannot appear in development
- held-out labels cannot enter prompts

CONCEPT SCORING
- exact span match passes
- partial span fails strict score
- wrong entity type fails strict typed score

CANONICALISATION
- aliases resolve to same canonical node
- known different concepts cannot match through aliasing
- false merge is scored as identity error

RELATIONS
- correct endpoints + correct relation pass
- wrong relation fails
- reversed directional relation fails
- reversed symmetric relation passes
- missing endpoint becomes node failure, not pair failure

PAIR RECALL
- denominator includes only gold edges whose endpoint nodes exist
- gold pair oracle does not expose relation label

ORACLES
- E1 contains only permitted gold concept information
- E2 contains only permitted identity information
- E3 exposes endpoints, not relation
- E4 relation labels remain hidden until scoring

CR-011
- pre/post comparison uses same source extraction
- no rerun substituted for either graph
- ID mapping respected

PROVENANCE
- evidence locator resolves
- source lineage survives re-key
- required metadata completeness scored

STABILITY
- repeated runs stored separately
- no best-run selection
- deterministic bootstrap under fixed seed

GOLD SAFETY
- external test files read-only
- code cannot write data/gold
```

## B28. Final report structure

`FINAL_EVALUATION.md` should answer five questions clearly.

### 1. How accurate is the whole system?

Report `STRICT_E2E_EDGE_F1`.

### 2. Does it generalise?

Compare external SciNLP with in-domain P&D-E2E.

### 3. Where is accuracy lost?

Use E0–E4 oracle decomposition and earliest-error attribution.

### 4. Did CR-011 help?

Compare pre-sleep vs post-sleep on the same graph snapshot.

### 5. Is the workflow trustworthy operationally?

Report:

```text
unsupported facts
provenance completeness
stability
cost
limitations
```

Do not reduce all five questions into a single composite score.

## B29. Definition of done

CR-012 is complete only when:

```text
raw text can be passed through the frozen production workflow;

the resulting graph can be compared against independent gold;

a strict final edge requires correct concepts + relation + direction;

SciNLP has been evaluated through a frozen benchmark adapter;

P&D-E2E contains exhaustive in-domain held-out gold;

component metrics are diagnostic rather than headline metrics;

E0–E4 isolate major error sources;

CR-011 is evaluated using the exact same pre-sleep extraction;

stochastic stability is measured;

unsupported facts are reported;

provenance completeness is measured;

benchmark versions and hashes are frozen;

held-out labels were never used to improve the pipeline;

and no post-test method change was introduced.
```

---

# PART C — RESEARCH / IMPLEMENTATION AUTHORITY

Implementation may resolve:

```text
module/file locations
CLI naming
internal helper functions
serialization details
schema plumbing
test organisation
report formatting
minor efficiency improvements that do not alter experiment semantics
```

Implementation must return to Research before changing:

```text
CR-011 identity semantics
SLEEP-240 composition
CR-011 gates
CR-012 primary benchmarks
P&D-E2E sampling design
gold annotation policy
headline metric
oracle definitions
pair-recall denominator
error-attribution semantics
confidence-interval unit
stability protocol
held-out execution rules
benchmark-adapter restrictions
test-set isolation
cost caps materially
```

If a required methodological decision is missing, write:

```text
RESEARCH DECISION REQUIRED
```

and ask the narrowest possible question.

Do not invent a replacement.

---

# PART D — DEPENDENCY / ORDERING NOTE

Do **not** implement CR-012 as though CR-010 and CR-011 were already settled.

Required order:

```text
CR-010 final architecture decision
        ↓
CR-011 STOP 1 reconciliation
        ↓
CR-011 experiments + selected production outcome
        ↓
CR-011 STOP 5 + CR012_EVAL_HANDOFF
        ↓
CR-012 STOP 1
```

CR-012 tooling that is architecture-independent may be prepared earlier, but its **production baseline cannot be frozen until CR-011 finishes**.

---

# FINAL RESEARCH DECISION

**CR-011 remains a graph reorganisation / evidence-grounded consolidation CR.**

Its existing design is retained, with four substantive clarifications:

```text
SLEEP-240 remains consolidation-specific;
concept F1 is a non-regression check;
derived organisation is replayed after sleep;
CR-011 emits immutable pre/post snapshots for CR-012.
```

**CR-012 becomes the independent whole-workflow evaluation CR.**

Its central contribution is:

> **For the first time in the project, evaluate the path from raw technical text all the way to the final canonical typed Expert KG against independently annotated graph ground truth, while using oracle experiments to identify exactly where errors enter the pipeline.**

The headline result is **strict end-to-end edge precision/recall/F1**, not an average of component metrics.
