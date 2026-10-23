# CR-016 — Cross-Section Associative Memory with HippoRAG

**Status:** implementation specification derived from the CR-016 Research handover, 2026-10-12.  
**Branch:** `cr-016-cross-section-memory`, created from the frozen production state after the active concept-extraction CR is finalised. Merge only after final Research/owner approval; tag `cr-016-complete`.  
**Primary technology under test:** HippoRAG 2.  
**Scope:** evaluate persistent cross-section retrieval memory for prior source evidence, repeated concepts, aliases/acronyms, long-gap recurrence and existing-node linking.  
**Primary comparison:** no memory vs dense prior-passage retrieval vs HippoRAG prior-passage retrieval.  
**Production safety:** HippoRAG is a retrieval memory only. It is not the authoritative CUMAP knowledge graph.

**Depends on:**
- the active production concept extractor being frozen at CR-016 start;
- CR-015 final state being known;
- current source-order and provenance infrastructure;
- current CR-013/014/015 trace infrastructure;
- a reproducible evaluation strategy with causal section ordering.

**Must remain frozen during the primary experiment:**
- concept extractor `E*`;
- CR-008 identity semantics and `DIFFERENT` vetoes;
- canonicalisation semantics;
- relation inventory;
- pair-generation/pair-selection methodology;
- relation classifier semantics;
- graph-consolidation semantics;
- historical CR-012/013/014/015 outputs.

---

## 1. Why

CUMAP processes a technical textbook section by section. A concept may be introduced once, then reappear much later as:

- an acronym;
- a shortened form;
- a one-token reference;
- a different boundary;
- the same phrase in another sense;
- a later mention whose earlier definition would help the verifier.

The current system has persistent graph state, but CR-016 tests whether a dedicated **retrieval memory over prior source evidence** improves these cross-section decisions.

The primary research question is:

> Does persistent retrieval over previously processed sections improve repeated-concept consistency, alias/acronym recovery, existing-node linking and long-gap recall without suppressing new concepts or increasing false links/merges?

The required comparison is:

```text
P0  no cross-section retrieval memory

P1  dense prior-passage retrieval

P2  HippoRAG 2 prior-passage retrieval

P3  optional HippoRAG raw passages + prior frozen CUMAP concept cards
```

P1 is mandatory. HippoRAG must prove benefit beyond ordinary dense retrieval.

---

## 2. Critical architecture boundary

There are two different graphs:

```text
HIPPORAG INTERNAL GRAPH
    retrieval structure
    OpenIE / phrase / passage / similarity / PPR links

CUMAP EXPERT KG
    authoritative semantic graph
    validated concepts + relations
    canonical identity
    provenance
```

They must remain separate.

HippoRAG may:

- retrieve prior evidence;
- rank prior passages;
- expose associative neighbours;
- suggest possible historical concept matches.

HippoRAG may not:

- declare two concepts identical;
- bypass canonicalisation;
- override an approved `DIFFERENT` decision;
- create an Expert-KG edge from an internal OpenIE edge;
- accept/reject a concept solely from memory presence/absence;
- treat PPR connectivity as semantic truth.

---

## 3. Freeze the active extractor

At STOP 1, discover the actual production/adopted concept pipeline:

```text
E* = production concept extractor at CR-016 start
```

If CR-015 was adopted, `E*` is that selected pipeline.

If CR-015 was not adopted, `E*` remains the current production pipeline.

Record:

```text
commit/tag
config hashes
prompt hashes
model IDs
thresholds
sampling settings
candidate/boundary/verifier/pruner configuration
canonicalisation configuration
trace schema version
```

CR-016 compares memory while keeping `E*` frozen.

---

## 4. Primary memory integration point

Insert memory after current-section candidate/boundary formation but before final validity/linking:

```text
CURRENT SECTION
    ↓
FROZEN E* PROPOSAL / BOUNDARY PIPELINE
    ↓
candidate / overlap family
    ↓
MEMORY QUERY BUILT FROM CURRENT RUNTIME INFORMATION ONLY
    ↓
retrieve PRIOR-SECTION evidence
    ↓
frozen verifier / existing-node linker
    ↓
frozen canonicalisation
    ↓
final concepts
    ↓
AFTER SECTION OUTPUT IS FROZEN:
index completed section into memory
```

Primary-experiment rule:

> Memory supports a current source-grounded candidate. It does not create an exact current-section mention that is absent from the current source.

Memory-guided proposal generation is outside the primary CR-016 experiment.

---

## 5. Strict causal memory rule

This is non-negotiable.

When processing source section `S_n`, the memory index may contain only sections with:

```text
source_order < source_order(S_n)
```

Required processing loop:

```text
create empty arm-specific index

for section in frozen source order:
    query memory using current section/candidate only
    assert every retrieved source is earlier
    run frozen E*
    freeze current section output
    index current section
    persist index snapshot/hash
```

Forbidden:

```text
index the whole textbook first
then evaluate earlier sections
```

That leaks future information.

Every retrieval event must record:

```text
query_section
retrieved_source_section
query_source_order
retrieved_source_order
future_section_check
```

Any future-section retrieval must fail closed.

---

## 6. Memory arms

### 6.1 M0 / P0 — no memory

Use frozen `E*` unchanged.

This is the reference.

### 6.2 M1 / P1 — dense prior-passage memory

Index prior raw source passages.

Retrieve with a frozen dense embedding family.

Purpose:

> Determine whether ordinary retrieval already supplies the useful historical evidence.

### 6.3 M2 / P2 — HippoRAG 2 raw-source memory

Index the same prior raw source material as M1.

HippoRAG internal OpenIE/graph/PPR structures are retrieval-only.

Do not index CUMAP predictions into M2.

Each passage should retain:

```text
document_id
chapter_id
section_id
paragraph/sentence locator
source_order
source_hash
chunk_id
```

### 6.4 M3 / P3 — optional hybrid memory

Run only if P2 demonstrates useful benefit.

Index:

```text
prior raw passages
+
prior frozen CUMAP concept/evidence cards
```

Concept cards are created only after the originating section output is frozen.

They remain retrieval aids, not gold.

---

## 7. Dependency isolation

Do not install HippoRAG into the main CUMAP environment during STOP 1.

Preferred options:

```text
.venv-hipporag/
```

or:

```text
CUMAP
  ↓ local adapter/API
isolated HippoRAG service
```

Pin:

```text
exact official HippoRAG git commit
package version
Python version
dependency lock
embedding model/revision
OpenIE model/provider/revision
vector-store backend
HippoRAG config
```

If the memory environment cannot be isolated reproducibly, return to Research.

---

## 8. Chunking parity

M1 and M2 must index equivalent raw source units.

STOP 1 should assess:

```text
sentence
small paragraph
textbook paragraph
fixed-token chunk preserving sentence boundaries
```

Preferred first implementation:

```text
textbook paragraph
+ section/sentence provenance
```

Do not compare M1 paragraphs against M2 semantically different source units without declaring chunking as another experimental variable.

Freeze chunking before held-out evaluation.

---

## 9. Memory query contract

Queries may use only current runtime-visible information:

```text
candidate span
overlap-family spans
current source sentence
section heading
node-type hypothesis
current alias/acronym surface
current existing-node search target
```

Forbidden:

```text
gold concept label
held-out canonical answer
future source text
human test annotation
held-out failure label
```

The same query should be byte-identical for M1/M2 where the backend interfaces permit.

---

## 10. Memory evidence packet

The verifier/linker should receive a compact bounded packet:

```text
CURRENT SOURCE
<current sentence/context>

CURRENT CANDIDATE
<candidate>

PRIOR MEMORY EVIDENCE

[1]
section_id:
source_locator:
retrieval_score:
retrieval_backend:
text:

[2]
...

RULES
- Prior memory is supporting evidence only.
- Current-source support remains mandatory.
- Memory presence does not prove identity.
- Memory absence does not prove invalidity.
- CR-008 DIFFERENT remains a hard veto.
```

`top_k` is a development-selected parameter and must be frozen before held-out evaluation.

Do not dump unbounded retrieval context into the verifier.

---

## 11. Existing-node linking

Memory may propose historical matches:

```text
current candidate: BGP
retrieved history: Border Gateway Protocol
```

The final decision still belongs to the frozen CUMAP concept/linking path:

```text
LINK_EXISTING
ACCEPT_NEW
REJECT
```

HippoRAG similarity alone is never proof of `SAME`.

For same-surface/different-sense cases, current source context has priority.

---

## 12. Stage A — retrieval-only benchmark

Before changing extraction behaviour, determine whether useful historical evidence is actually retrieved.

Use development/exposed material only.

Construct cases where:

```text
current runtime-visible query
→ valid prior source evidence exists
```

Do not put target/gold wording into the runtime query.

Compare:

```text
M1 dense
M2 HippoRAG raw
```

Report:

```text
Recall@1
Recall@3
Recall@5
MRR
nDCG@k if already supported/useful
evidence precision@k
mean latency
indexing cost
query cost
```

Required slices:

```text
exact-surface recurrence
alias recurrence
acronym recurrence
one-token recurrence
boundary-variant recurrence
long-gap recurrence
short-gap recurrence
associative/multi-hop recurrence
same-surface-different-sense hard cases
```

### 12.1 Retrieval gate

M2 proceeds as the primary memory backend only if it provides meaningful evidence over M1.

Eligible if one of:

```text
Recall@5 >= M1 + 0.05 absolute
```

or:

```text
paired bootstrap 95% lower bound for ΔRecall@5 or ΔMRR > 0
```

or:

```text
preregistered difficult slice >= +0.10
AND overall Recall@5 regression <= 0.03
```

Also require:

```text
future-section retrieval violations = 0
retrieval provenance completeness = 1.00
```

If M2 does not meaningfully beat M1, return to Research before claiming a HippoRAG-specific benefit.

Dense retrieval winning is a valid outcome.

---

## 13. Stage B — pipeline memory ablation

Freeze identical `E*` across all arms.

Run:

| Arm | Memory | Purpose |
|---|---|---|
| **P0** | none | frozen production reference |
| **P1** | dense prior raw passages | generic retrieval benefit |
| **P2** | HippoRAG prior raw passages | associative-memory benefit |

Only the memory evidence supplied to the verifier/linker should differ.

Report the active concept-extraction metrics plus memory-specific metrics.

---

## 14. Stage C — optional hybrid concept-card memory

Only if P2 merits continuation.

Compare:

```text
P2  HippoRAG raw passages
P3  HippoRAG raw passages + prior frozen concept cards
```

Evaluate whether structured historical outputs improve reuse enough to justify feedback risk.

Measure:

```text
memory-induced false links
error persistence
novel-concept suppression
incorrect-card propagation
```

Do not edit cards manually in response to test outcomes.

---

## 15. Recurrence slices

Each current gold concept/mention should be labelled where legitimately evaluable as:

```text
NEW
PREVIOUSLY_SEEN
ALIAS_RECURRENCE
ACRONYM_RECURRENCE
LONG_GAP_RECURRENCE
SAME_SURFACE_DIFFERENT_SENSE
```

The exact long-gap threshold is selected on development and frozen.

These slices are essential because overall F1 can hide whether memory helps the cases it was designed for.

---

## 16. Primary concept metrics

Keep the exact frozen concept metrics used by `E*`.

Where applicable report:

```text
mention-level span-exact precision
mention-level span-exact recall
mention-level span-exact F1
distinct-surface precision
distinct-surface recall
distinct-surface F1
one-token recall
nested recall
boundary error
```

Do not redefine the active scorer inside CR-016.

---

## 17. Memory-specific metrics

Mandatory:

```text
PREVIOUSLY_SEEN recall
NEW recall
alias recurrence recall
acronym recurrence recall
long-gap recurrence recall

existing-node link precision
existing-node link recall
existing-node link F1

false new-node rate for previously seen concepts
false-link rate
false-merge rate
novel-concept suppression rate
```

Define:

```text
novel_concept_suppression_rate
=
baseline-correct NEW concepts that become missed or falsely linked under memory
/
baseline-correct NEW concepts
```

Memory absence must never count against a new concept.

---

## 18. Overall Knowledge-Graph Accuracy Diagnostic

**This section is added to explicitly answer whether HippoRAG improves the accuracy of the final CUMAP Expert KG, not merely concept recurrence.**

This is a **diagnostic extension** of CR-016. It must reuse the project's already-frozen end-to-end KG evaluator where available. Do not invent a new headline KG metric or adoption threshold without Research approval.

### 18.1 Question

> After using the selected memory system during concept processing, is the final Expert KG more accurate than the same frozen pipeline with no memory?

### 18.2 Controlled comparison

After STOP 5 results are frozen, build two end-to-end KGs using identical downstream methods:

```text
KG0
P0 no-memory concepts
→ frozen canonicalisation
→ frozen pair generation/selection
→ frozen relation classification
→ frozen consolidation
→ final Expert KG

KG1
selected CR-016 memory concepts
→ SAME frozen canonicalisation
→ SAME frozen pair generation/selection
→ SAME frozen relation classification
→ SAME frozen consolidation
→ final Expert KG
```

The only causal difference should be the memory condition used upstream.

### 18.3 Preferred evaluation

At STOP 1, locate the frozen CR-012 end-to-end KG scorer/evaluation contract.

If it can be validly applied to the fresh CR-016 evaluation data, reuse it unchanged.

Report the repository's actual strict end-to-end metrics, including where supported:

```text
strict final-node precision / recall / F1
strict final-edge precision / recall / F1
relation-label accuracy conditional on valid endpoints
endpoint/linking accuracy
unsupported-edge / evidence-grounding rate
false merge / false split counts
graph provenance completeness
```

The implementation report must use the exact metric names produced by the frozen scorer rather than inventing renamed equivalents.

### 18.4 Primary KG-accuracy comparison

Report:

```text
Δ strict end-to-end edge F1 = KG1 - KG0
Δ edge precision
Δ edge recall
Δ node F1
Δ unsupported/evidence-weak edges
Δ false merges
Δ false splits
```

Use paired section/document bootstrap confidence intervals if compatible with the existing evaluator.

This directly distinguishes:

```text
memory improves concept recurrence
```

from:

```text
memory improves the final knowledge graph
```

### 18.5 Interpretation

Possible outcomes:

```text
A. concept metrics improve AND strict KG accuracy improves
   → evidence that memory benefits the final KG

B. concept recurrence improves but KG accuracy is unchanged
   → memory helps extraction but downstream bottlenecks absorb the gain

C. concept recall improves but edge precision/F1 worsens
   → extra/link-biased concepts create downstream graph noise

D. dense retrieval matches/exceeds HippoRAG
   → retrieval memory may help, but HippoRAG is not justified

E. no valid relation-level gold exists
   → overall KG accuracy is NOT_EVALUABLE from automatic scoring
```

### 18.6 If no fresh relation-level gold exists

Do **not** label downstream counts as "KG accuracy."

Instead:

1. report observable diagnostics:
   ```text
   node growth
   pair-candidate growth
   selected-pair growth
   relation growth
   evidence/provenance completeness
   false-link/false-merge diagnostics
   ```
2. optionally create a **blind human edge audit** on a frozen sample;
3. report sampled edge precision with confidence intervals;
4. state explicitly that whole-KG recall/F1 remains `NOT_EVALUABLE`.

A sampled edge audit cannot by itself establish complete KG recall.

### 18.7 Research boundary

The overall-KG diagnostic may inform the final decision.

If the project wants to make a new strict KG-accuracy delta a formal CR-016 adoption gate, return:

```text
RESEARCH DECISION REQUIRED
```

unless that gate already exists in the frozen project evaluation policy.

---

## 19. Retrieval-quality metrics

Mandatory:

```text
Recall@k
MRR
evidence precision@k
retrieved source distance
retrieved source diversity
retrieval latency
```

Also record:

```text
top_k
backend
index snapshot
embedding/model identity
```

---

## 20. Identity and novelty safety

Memory creates a false-link risk:

```text
historically similar concept
→ retrieval bias
→ false LINK_EXISTING
```

Report:

```text
DIFFERENT violations
same-surface-different-sense false links
compatible-name false merges
memory-induced canonicalisation changes
```

Required:

```text
DIFFERENT violations = 0
```

Novelty control:

```text
NEW concept recall
novel_concept_suppression_rate
```

Absence from memory may never force rejection.

---

## 21. Memory error taxonomy

Use earliest applicable memory failure:

```text
MR0 useful prior evidence existed but was not retrieved
MR1 future-section evidence retrieved
MR2 irrelevant memory displaced relevant evidence
MR3 generic hub over-centralisation

ML0 memory caused false LINK_EXISTING
ML1 memory caused false ACCEPT_NEW suppression
ML2 baseline-correct NEW concept became missed
ML3 incorrect concept card propagated through memory
ML4 same-surface/different-sense confusion
ML5 memory evidence used without current-source support
```

Do not double count downstream consequences.

---

## 22. Development selection rule

A memory arm is eligible for freezing only if all safety rules pass and cross-section benefit is material.

Recommended gates:

1. overall exact concept F1 regression no worse than **−0.01** from P0;
2. overall precision regression no worse than **−0.02**;
3. `PREVIOUSLY_SEEN` recall improves by **+0.05 absolute** OR paired bootstrap lower bound > 0;
4. existing-node link F1 improves by **+0.05 absolute** where evaluable;
5. `NEW` recall regression no worse than **−0.02**;
6. novel-concept suppression rate **<= 0.02**;
7. `DIFFERENT` violations = **0**;
8. future-section retrieval violations = **0**;
9. accepted memory evidence provenance completeness = **1.00**.

If P1/P2 are within:

```text
0.02 overall F1
and
0.03 memory-specific recall
```

prefer:

1. fewer false links;
2. lower indexing/retrieval cost;
3. simpler architecture.

Do not select HippoRAG merely because it is more sophisticated.

---

## 23. Hybrid-memory gate

P3 must outperform P2 on a memory-specific target.

Eligible only if:

```text
existing-node link F1 >= P2 + 0.03
```

or:

```text
alias/acronym recurrence recall >= P2 + 0.05
```

and all:

```text
overall precision delta vs P2 >= -0.01
NEW recall delta vs P2 >= -0.01
false-link rate increase <= 0.01
DIFFERENT violations = 0
concept-card provenance = 1.00
```

Otherwise prefer raw-source HippoRAG, dense memory, or no memory.

---

## 24. Fresh evaluation policy

Audit all exposure from CR-001 through CR-015.

Preferred:

```text
genuinely untouched source sections/documents
in frozen source order
```

If insufficient untouched P&D material remains, do not fabricate a fresh held-out claim.

Return to Research with:

```text
A. second permitted networking source/corpus
B. untouched chapter/source reserve if still methodologically clean
C. development-only feasibility; production adoption NOT_EVALUABLE
```

Every evaluation set records gold provenance:

```text
HUMAN_PRIMARY
HUMAN_DUAL
HUMAN_REVIEWED_MODEL_DRAFT
MODEL_GENERATED_DIAGNOSTIC
```

Model-generated benchmark results must not be described as human-validated accuracy.

---

## 25. Index reproducibility

Record:

```text
HippoRAG repository commit
package version
Python version
dependency lock hash
OpenIE provider/model
embedding model
OpenIE config
chunking policy
vector store
index identity
save-dir manifest hash
source-order manifest hash
```

If index identity changes, rebuild from source.

Do not fabricate/copy manifests to make incompatible indexes load.

Each arm must use an independent index namespace.

---

## 26. Trace extension

Reuse existing CUMAP tracing.

CR-016 may add:

```text
memory_query
memory_retrieval
memory_consume
memory_update
memory_card_create
```

Every retrieval event records:

```text
query_id
query_section
query_object_id
backend
index_snapshot_id
retrieved_item_ids
retrieved_source_sections
scores
ranks
top_k
model/embedding identity
config_hash
source_locators
future_section_check
```

Every memory-influenced decision must be traceable:

```text
current candidate
→ query
→ prior evidence
→ verifier/link decision
→ canonicalisation
```

No chain-of-thought is required.

---

## 27. Operational metrics

Report:

```text
offline indexing cost
incremental indexing cost/section
retrieval cost/section
verifier token increase
wall-clock latency
index size
passage/entity/fact counts
API calls
```

Also monitor index growth over source order.

---

## 28. Cost contract

Planning limits:

```text
STOP 1 reconciliation / tiny smoke test   <= $2
STOP 2 retrieval-only development          <= $8
STOP 3 pipeline memory ablation            <= $15
STOP 4 optional hybrid memory              <= $8
STOP 5 fresh held-out                      <= $12

warning threshold                          $30 cumulative
hard cap                                   $45 cumulative
```

Replace with repository-active pricing during STOP 1.

No expensive indexing run before preflight.

---

## 29. STOP sequence

### STOP 1 — repository + memory feasibility reconciliation

Do not run a large experiment.

Report:

```text
actual E*
CR-015 final/adoption state
current existing-node/canonicalisation mechanisms
all exposed sections
fresh evaluation availability
source-order manifest
current trace schema
memory integration point
exact HippoRAG commit/version
license confirmation
dependency conflict audit
isolated environment plan
chunking candidates
dense baseline design
estimated index sizes
estimated OpenIE calls/tokens/cost
expected retrieval calls
privacy/API constraints
frozen CR-012 end-to-end KG scorer availability
```

Run only a tiny smoke test proving:

```text
incremental indexing
persistent reload
source_id/metadata provenance
causal retrieval filter
separate arm indexes
```

STOP and return to Research if:

```text
future-section isolation cannot be guaranteed
index provenance cannot be recovered
HippoRAG cannot be isolated reproducibly
no valid evaluation strategy exists
```

### STOP 2 — retrieval-only benchmark

Run M1 vs M2 on development.

No concept-extraction changes.

Apply the retrieval gate.

If M2 does not meaningfully beat dense retrieval, return to Research before HippoRAG pipeline integration.

### STOP 3 — pipeline memory ablation

Run:

```text
P0 no memory
P1 dense raw memory
P2 HippoRAG raw memory
```

with identical frozen `E*`.

Select:

```text
no memory
dense memory
HippoRAG raw memory
```

according to gates.

### STOP 4 — optional hybrid memory

Only if P2 merits continuation.

Run P3.

Evaluate feedback/error propagation.

Freeze at most one memory design.

### STOP 5 — fresh sequential held-out evaluation

Preconditions:

```text
fresh set verified
source order frozen
gold frozen
gold provenance recorded
backend frozen
top_k frozen
query template frozen
chunking frozen
index identity frozen
code/config/model hashes frozen
```

Run:

```text
P0
selected memory arm
```

exactly once in causal order.

No quality retries.
No post-result tuning.
No manual fixes.

### STOP 6 — downstream KG impact + final decision

After STOP 5 is frozen:

1. run the identical frozen downstream KG pipeline for P0 and the selected memory arm;
2. run the Overall Knowledge-Graph Accuracy Diagnostic in §18 where valid;
3. measure node/pair/edge pressure;
4. verify false-link/merge safety;
5. verify provenance/trace continuity;
6. report index/storage/lifecycle requirements;
7. create migration/rollback plan.

No production migration without Research/owner approval.

---

## 30. Held-out adoption gates

The selected memory arm is eligible for migration analysis only if:

| Gate | Requirement |
|---|---:|
| overall exact concept F1 | >= P0 - 0.01 |
| overall precision | >= P0 - 0.02 |
| PREVIOUSLY_SEEN recall | >= P0 + 0.05 |
| existing-node link F1 | >= P0 + 0.05 where evaluable |
| NEW recall | >= P0 - 0.02 |
| novel-concept suppression | <= 0.02 |
| DIFFERENT violations | 0 |
| future-section retrieval violations | 0 |
| accepted-memory evidence provenance | 1.00 |
| test-time manual fixes | 0 |

If HippoRAG is preferred over dense retrieval, the final report must explicitly show why.

A dense-memory win is valid.

A no-memory win is valid.

---

## 31. Production lifecycle requirements

Any production proposal must specify:

```text
index lifecycle
index rebuild procedure
source deletion
version migration
rollback
backup
storage
model/config identity checks
failure behaviour
```

Recommended fail-safe:

```text
memory unavailable
→ fall back to frozen no-memory E*
```

Memory failure must never corrupt the authoritative Expert KG.

---

## 32. Required repository artifacts

Expected semantics:

```text
docs/change-requests/
    CR-016-cross-section-associative-memory.md

PROMPT-CR-016.md

configs/
    cr016_memory.yaml
    cr016_manifest.yaml

prompts/
    cr016_memory_consumer_v1.md

src/cumap/cr016/
    memory_adapter.*
    dense_memory.*
    hipporag_memory.*
    causal_index.*
    concept_cards.*

data/interim/checks/cr016/
    retrieval_benchmark.*
    memory_query_audit.*
    fresh_pilot_blind.csv
    fresh_test_blind.csv

reports/cr016/
    STOP1_RECONCILIATION.md
    contamination_audit.md
    hipporag_feasibility.md
    retrieval_ablation.md
    retrieval_slices.md
    pipeline_memory_ablation.md
    hybrid_memory_ablation.md
    kg_accuracy_diagnostic.md
    cost.md
    heldout_results.md
    downstream_compatibility.md
    FINAL_DECISION_EVIDENCE.md

tests/fixtures/cr016/
```

Machine-readable outputs:

```text
memory_queries.jsonl
memory_retrievals.jsonl
memory_updates.jsonl
index_snapshots.jsonl
concept_cards.jsonl
memory_decisions.jsonl
kg_accuracy_results.json
trace_manifest.json
```

Exact paths may be reconciled at STOP 1.

---

## 33. Minimum tests

### Causal isolation

- section `n` cannot retrieve section `n` or later;
- source order immutable within a run;
- future-source result hard-fails;
- each arm starts with independent empty index;
- index update occurs only after section output freezes.

### Provenance

- every indexed passage has source locator;
- every concept card maps to frozen prior concept/evidence;
- every retrieved item preserves source ID/section;
- every memory-influenced decision links to retrieval event.

### Retrieval parity

- M1/M2 index equivalent source material;
- top-k differences are explicit;
- query bytes are identical where interface allows.

### Gold safety

- query contains no gold field;
- held-out gold inaccessible to prediction code;
- gold cannot enter HippoRAG index;
- annotations cannot enter OpenIE input.

### Identity safety

- memory cannot bypass `DIFFERENT`;
- same-surface/different-sense fixture does not auto-link;
- internal similarity never implies SAME;
- no memory result can force REJECT.

### Novelty safety

- genuinely new concept can be accepted with empty/no useful memory;
- retrieval is not prerequisite for concepthood;
- NEW recall always produced.

### Error propagation

- concept card cannot overwrite raw source;
- card provenance includes generating run;
- card index rebuild deterministic;
- P3 can fall back to P2.

### KG-accuracy diagnostic

- P0 and selected-memory KG runs use identical downstream config hashes;
- final KG scorer is the frozen project scorer;
- memory condition is the only intended upstream difference;
- no relation gold is exposed to prediction;
- if relation-level gold is unavailable, status becomes `KG_ACCURACY_NOT_EVALUABLE`;
- downstream counts alone are never labelled accuracy.

### Reproducibility

- exact HippoRAG commit recorded;
- index identity recorded;
- incompatible identity fails closed;
- rebuild reproduces equivalent source inventory.

### Fallback

- memory failure leaves Expert KG untouched;
- no-memory `E*` path remains runnable.

---

## 34. Required visualisations

Generate only from real frozen outputs.

1. Dense vs HippoRAG retrieval Recall@k / MRR.
2. Recall by recurrence type.
3. Memory benefit vs section distance.
4. Existing-node link precision/recall/F1.
5. NEW-concept recall by arm.
6. False-link / false-merge counts.
7. Cost/latency by arm.
8. Index growth over source order.
9. **Overall KG accuracy comparison**, where end-to-end gold/scorer is valid:
   ```text
   P0 final KG
   selected memory final KG

   node F1
   strict edge F1
   edge precision
   edge recall
   unsupported/evidence-weak edge rate
   ```
10. Concept improvement vs final-edge improvement, to show whether gains survive downstream processing.

Do not fabricate charts.

---

## 35. Interpretation rules

Distinguish:

```text
retrieval success
→ memory evidence consumption
→ concept/link decision
→ canonicalisation
→ final KG effect
```

Do not claim HippoRAG improved the KG solely because retrieval Recall@5 increased.

Do not interpret internal HippoRAG OpenIE triples as Expert-KG relations.

Do not interpret PPR paths as causal reasoning.

Do not hide NEW-concept regressions behind recurrence gains.

Do not call node/edge count growth "accuracy."

Final reporting should explicitly answer:

1. Did HippoRAG retrieve better prior evidence than dense retrieval?
2. Did that evidence improve concept/link decisions?
3. Did it preserve NEW concepts and identity safety?
4. Did the improvement survive into the final Expert KG?
5. Did HippoRAG outperform dense retrieval strongly enough to justify its complexity?
6. What did it cost in indexing, latency, storage and operational state?

---

## 36. Final status

The final report must end with one of:

```text
HIPPORAG_ELIGIBLE_FOR_MIGRATION
DENSE_MEMORY_PREFERRED
NO_MEMORY_PREFERRED
NO_ELIGIBLE_MEMORY_ARM
STOPPED_NO_FRESH_HELDOUT
DEVELOPMENT_ONLY_FEASIBILITY
```

Additionally report:

```text
KG_ACCURACY_IMPROVED
KG_ACCURACY_NOT_IMPROVED
KG_ACCURACY_NOT_EVALUABLE
```

as a separate diagnostic status.

The KG-accuracy status is not automatically a new adoption gate unless Research explicitly makes it one.

---

## 37. Definition of done

CR-016 is complete only when:

- production extractor `E*` is frozen;
- dense retrieval is evaluated as a mandatory baseline;
- HippoRAG is treated as retrieval memory only;
- evaluation is strictly causal in source order;
- future-section leakage is impossible by construction and tested;
- retrieval quality is measured separately from extraction quality;
- PREVIOUSLY_SEEN and NEW performance are both reported;
- existing-node link quality and false-link rate are measured;
- internal HippoRAG similarity never bypasses identity rules;
- raw-source memory is tested before concept-card memory;
- memory-influenced decisions retain provenance;
- fresh held-out evaluation runs once where possible;
- downstream graph effects are measured;
- overall KG accuracy is evaluated with the frozen end-to-end scorer where valid, or explicitly marked NOT_EVALUABLE;
- operational costs/state requirements are reported;
- rollback/fallback is defined;
- Research/owner receives frozen evidence before production migration.

---

## 38. Immediate coding-agent instruction

Start **STOP 1 only**.

Do not:

```text
install HippoRAG into the main CUMAP environment
index the full textbook
build concept-card memory
run a large paid indexing job
change E*
change canonicalisation
change downstream KG methods
```

First establish:

1. actual frozen extractor `E*`;
2. CR-015 final status;
3. full exposure/contamination inventory;
4. genuinely fresh CR-016 evaluation availability;
5. exact frozen source order;
6. mandatory dense baseline;
7. isolated HippoRAG environment pinned to exact official commit;
8. incremental indexing + persistent reload;
9. source provenance;
10. hard future-section prevention;
11. expected indexing/retrieval cost;
12. availability and compatibility of the frozen end-to-end KG scorer needed for §18.

Return:

```text
reports/cr016/STOP1_RECONCILIATION.md
reports/cr016/contamination_audit.md
reports/cr016/hipporag_feasibility.md
```

before proceeding.

If the repository cannot support the approved design faithfully:

```text
Problem
→ repository evidence
→ why the design cannot be implemented faithfully
→ minimal alternatives
→ methodological consequences
→ RESEARCH DECISION REQUIRED
```

Do not silently substitute a different experiment.
