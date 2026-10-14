# CR-018 — Explicit Boundary Verification + HippoRAG Evidence-Aware Identity Linking

**Status:** implementation specification derived from the CR-018 Research handover, 2026-10-14.  
**Branch:** `cr-018-boundary-identity`, created from the frozen repository state after CR-017. Merge only after STOP 7 and Research/owner approval; tag `cr-018-complete`.  
**Scope:** two independent experimental tracks:
1. explicit family-aware boundary verification for precision recovery;
2. HippoRAG-backed evidence-aware identity linking for unresolved cross-section identity decisions.

**Core implementation rule:** Track A and Track B must be implemented, evaluated, and interpreted separately before any combined pipeline is allowed.

**Production safety:**  
- no automatic graph mutation from the new identity verifier during development;  
- no weakening of CR-008 identity rules;  
- no changes to proposal generation while testing Track A;  
- no relation-pipeline changes during the primary CR-018 experiments.

---

## 1. Why

CR-018 addresses two separate bottlenecks already isolated by earlier experiments.

### Track A — Boundary precision

The high-recall concept pipeline can recover many more candidate concepts, but precision collapses because span boundaries remain too permissive.

The failure pattern is:

```text
high-recall candidate pool
→ overlap-family selection
→ many valid concepts recovered
→ many over-long / under-long / invalid nested spans survive
→ concepthood-only verification cannot recover enough precision
```

CR-018 therefore inserts an explicit **boundary-validity stage before concepthood verification**.

### Track B — Identity linking

HippoRAG can retrieve useful historical evidence, especially for long-gap and low-lexical-overlap recurrence, but better retrieval does not automatically produce better identity decisions.

The failure pattern is:

```text
better prior evidence
≠
better canonical identity decision
```

CR-018 therefore introduces an explicit **evidence-aware identity consumer** for unresolved accepted concepts.

---

## 2. Research questions

### Track A

**RQ-A1 — Boundary precision**

> Can an explicit boundary verifier recover precision while preserving the recall gains of the high-recall span pool?

**RQ-A2 — Nested discrimination**

> Can the system distinguish valid outer terms, valid nested terms, valid pairs of nested terms, over-long wrappers, under-long fragments, and invalid nested substrings?

### Track B

**RQ-B1 — Identity evidence**

> Can retrieved prior source evidence improve SAME-vs-NEW-vs-RELATED identity decisions for accepted concepts?

**RQ-B2 — HippoRAG-specific value**

> Does HippoRAG improve identity linking beyond both the current canonicalisation system and an ordinary dense retrieval baseline when all arms use the same identity verifier?

### Combined

**RQ-C — Additivity**

> If both tracks work independently, do the gains survive when combined?

---

## 3. Target architecture

Only if both tracks independently qualify:

```text
CURRENT TEXTBOOK SECTION
        ↓
FROZEN HIGH-RECALL PROPOSAL UNION
        ↓
OVERLAP / NESTED FAMILIES
        ↓
FROZEN HIGH-RECALL FAMILY SELECTOR
        ↓
NEW EXPLICIT BOUNDARY VERIFIER
        ↓
BOUNDARY-VALID SPANS
        ↓
FROZEN CONCEPTHOOD VERIFIER
        ↓
NESTED-AWARE MENTION PLACEMENT
        ↓
DETERMINISTIC IDENTITY RULES
        ↓
UNRESOLVED ACCEPTED CONCEPT
        ↓
PRIOR-EVIDENCE RETRIEVAL
      ┌────────────┴────────────┐
      ↓                         ↓
DENSE MEMORY              HIPPORAG MEMORY
      └────────────┬────────────┘
                   ↓
       NEW EVIDENCE-AWARE
         IDENTITY VERIFIER
                   ↓
SAME_EXISTING / NEW_CONCEPT /
RELATED_NOT_SAME / DIFFERENT /
INSUFFICIENT_EVIDENCE
                   ↓
          HARD IDENTITY GUARDS
                   ↓
             CANONICAL NODE
                   ↓
        FROZEN RELATION PIPELINE
                   ↓
             FREEZE SECTION
                   ↓
        INDEX RAW PRIOR MEMORY
```

Do not let Track B feed back into Track A.

Do not let HippoRAG become the canonical authority.

---

## 4. Frozen substrates

STOP 1 must reconcile exact runnable artifacts for:

```text
high-recall proposal union
high-recall overlap-family selector
concepthood verifier
nested-aware mention placement
production concept baseline
current canonicalisation pipeline
current node registry/evidence storage
CR-016 dense memory
CR-016 HippoRAG memory
current trace schema
current scorer
```

Do not reconstruct historical behavior from old prose if committed artifacts differ.

---

## 5. Order of work and STOP points

Commit with prefix:

```text
CR-018:
```

### ⛔ STOP 1 — Repository reconciliation + feasibility

**No paid calls.**

Reconcile both tracks.

#### Boundary track

Report:

```text
exact frozen proposal-union definition
exact frozen family-selector path
exact frozen concepthood-verifier path
nested-placement path
candidate-family volume
saved outputs available for replay
current concept scorer
current human-boundary-audit tooling
```

#### Identity track

Report:

```text
current canonicalisation path
identity-rule order
current node registry
how historical evidence maps to canonical nodes
dense retrieval implementation
HippoRAG environment/commit
memory adapter
causal index implementation
identity-benchmark feasibility
```

#### Data

Report:

```text
all exposed sections
all untouched sections
frozen source order
gold provenance
identity-gold coverage
```

#### Cost

Estimate:

```text
BA2 / BA3
optional BA4
ID1 / ID2 / ID3
optional combined C0-C3
fresh sequential evaluation
```

Return:

```text
reports/cr018/STOP1_RECONCILIATION.md
```

Then stop.

---

### ⛔ STOP 2 — Boundary convention audit

Before tuning a paid boundary verifier:

1. create the blind 120-family audit sheet;
2. freeze the audit instructions;
3. give the blind sheet to the human owner;
4. do **not** fill it;
5. after human completion, compare human judgments to development benchmark conventions;
6. report disagreement by boundary type.

Return:

```text
reports/cr018/boundary_convention_audit.md
```

If the disagreement is material/systematic:

```text
STOPPED_BOUNDARY_GOLD_AMBIGUOUS
→ return to Research
```

No boundary prompt tuning before this STOP is resolved.

---

### ⛔ STOP 3 — Track A boundary verification

Run on exposed development data only:

```text
BA0
BA1
BA2
BA3
```

Run BA4 only if specifically justified and approved.

Report:

```text
concept exact P/R/F1
distinct-surface P/R/F1
boundary precision/recall
nested-valid recall
over-long FP rate
under-long FP rate
invalid-nested FP rate
descriptive-wrapper FP rate
UNCERTAIN rate
candidate-to-final compression
stage waterfall
section-bootstrap comparisons
runtime/cost
```

Freeze one boundary candidate only if it passes the Track A gates.

If none pass:

```text
BOUNDARY_TRACK_NOT_ELIGIBLE
```

Track B may still continue independently.

---

### ⛔ STOP 4 — Track B identity-consumer ablation

Use accepted development concepts in causal prior-source order.

Run:

```text
ID0
ID1
ID2
ID3
```

Do not mutate the production graph.

Report:

```text
identity link precision/recall/F1
false-new-node rate
false-link rate
false-merge rate
RELATED_NOT_SAME accuracy
DIFFERENT accuracy
INSUFFICIENT rate
recurrence slices
latency/cost
provenance completeness
```

Freeze one identity candidate only if it passes the Track B gates.

If none pass:

```text
IDENTITY_TRACK_NOT_ELIGIBLE
```

---

### ⛔ STOP 5 — Combined 2×2 development ablation

Only if both tracks independently qualify.

Run:

| Arm | Boundary | Identity |
|---|---|---|
| **C0** | production | production |
| **C1** | selected CR-018 boundary | production |
| **C2** | production | selected CR-018 identity |
| **C3** | selected CR-018 boundary | selected CR-018 identity |

This isolates whether the gains are additive or interact negatively.

Do not report only C0 vs C3.

If only one track passes, skip the 2×2 and carry that track alone to prospective evaluation.

Return to Research before fresh evaluation.

---

### ⛔ STOP 6 — Fresh sequential evaluation

Preconditions:

```text
selected architecture frozen
fresh section IDs frozen
gold provenance frozen
gold hashes frozen
prompt hashes frozen
model IDs frozen
config hashes frozen
boundary rules frozen
identity rules frozen
memory config frozen
query template frozen
top_k frozen
source order frozen
prediction code blocked from gold
```

Run:

```text
production baseline
eligible CR-018 candidate(s)
```

exactly once.

No tuning after outputs are inspected.
No quality retries.
No manual test fixes.

---

### ⛔ STOP 7 — Downstream compatibility + final decision

Only after a candidate passes fresh concept/identity gates.

Report:

```text
canonical node count
duplicate-node reduction
false-merge indicators
pair-candidate growth
pair-budget saturation
relation count
trace completeness
identity-safety violations
memory/index requirements
runtime/cost
rollback/rebuild plan
```

If CR-017 headline evaluation is valid on the split, also report:

```text
Concept F1
Ancestor Hierarchy F1
Pair Recall
Relation Macro F1
Strict E2E Edge F1
```

Do not run the final full-textbook production rebuild until Research approves migration.

---

# TRACK A — Explicit Boundary Verification

## 6. Track A purpose

Track A must answer only:

> Is this exact proposed surface a valid complete boundary in context?

It must not answer:

> Is this an important concept overall?

That is the later concepthood stage.

Boundary and concepthood must remain separate in code, traces, prompts, and error attribution.

---

## 7. Boundary verifier input

One verifier call receives:

```text
source sentence
limited local paragraph context
section heading

target span
all overlapping family spans

span offsets
token lengths
proposal provenance

optional development-only contrastive demonstrations
```

Forbidden:

```text
gold label
gold span
held-out annotation
arm outcome
historical scorer verdict
historical system preference
```

The verifier should not be told which family member an earlier system preferred.

---

## 8. Boundary verifier output

Required structured labels:

```text
VALID_EXACT
VALID_NESTED
REJECT_OVERLONG
REJECT_UNDERLONG
REJECT_INVALID_NESTED
REJECT_DESCRIPTIVE_WRAPPER
UNCERTAIN
```

Recommended schema:

```yaml
family_id: str
target_span_id: str
decision: VALID_EXACT | VALID_NESTED | REJECT_OVERLONG |
          REJECT_UNDERLONG | REJECT_INVALID_NESTED |
          REJECT_DESCRIPTIVE_WRAPPER | UNCERTAIN
evidence_locator: str | null
boundary_relation_to_family: str | null
model_id: str | null
prompt_version: str | null
config_hash: str | null
```

Do not require hidden reasoning.

A short audit rationale is optional but not required for scoring.

---

## 9. Multiple valid spans

A family may return:

```text
0 valid spans
1 valid span
multiple independently valid nested spans
```

Do not impose:

```text
longest match wins
```

Example:

```text
TCP congestion control
congestion control
```

may both survive if both are independently valid.

---

## 10. Boundary hard-negative bank

Use only exposed development material.

Candidate transformations:

```text
+1 left token
+1 right token
+2 wrapper tokens
-1 left token
-1 right token
head-only truncation
modifier-only truncation
sibling overlap span
nested substring
descriptive NP wrapper
```

Required provenance:

```yaml
example_id: str
source_span: str
transformation: str
family_id: str
source_section: str
annotation_provenance: HUMAN_PRIMARY | HUMAN_REVIEWED | MODEL_DIAGNOSTIC
validation_status: str
```

Do not create hard negatives from fresh held-out gold.

Do not assume every generated variant is truly negative until validated.

---

## 11. Contrastive demonstration retrieval

BA3 may retrieve family-level demonstrations from development only.

Prefer retrieval by:

```text
family shape
token length
syntactic head
boundary error type
local phrase pattern
technical context
```

Example:

```text
SOURCE:
...

FAMILY:
1. congestion control
2. congestion control algorithm
3. operation of the congestion control algorithm

VALID:
1, 2

INVALID:
3 = descriptive wrapper
```

Store demonstration IDs and retrieval provenance.

Fresh held-out examples must never enter the demo bank.

---

## 12. Boundary uncertainty

The primary boundary verifier may return:

```text
UNCERTAIN
```

For auto-adoption evaluation:

```text
UNCERTAIN
→ not silently accepted
```

Possible policy:

```text
treat as reject
```

or:

```text
route only uncertain cases to BA4
```

The policy must be frozen before held-out evaluation.

Do not interpret self-reported LLM confidence as calibrated probability unless calibrated on development.

---

## 13. Optional boundary ranker

A local ranker may be tested only for triage/efficiency after the primary verifier is evaluated.

Possible features:

```text
span length
POS / NP structure
left/right boundary tokens
heading signal
definition cue
recurrence
multi-proposer agreement
family position
local embeddings
selector provenance
```

Hard rule:

> No ranker threshold may silently create a new recall ceiling.

Always report:

```text
candidate recall before ranker
candidate recall after ranker
candidate recall after boundary verifier
candidate recall after concepthood verifier
```

---

## 14. Track A arms

### BA0 — Production baseline

Use the current production concept stage.

Purpose:

```text
precision/recall reference
```

### BA1 — Frozen high-recall reference

Use:

```text
frozen proposal union
→ frozen overlap-family selector
→ nested placement
```

No new calls if saved artifacts exist.

### BA2 — Explicit boundary verifier

Use:

```text
frozen selected spans
→ new boundary verifier
→ frozen concepthood verifier
→ nested placement
```

Purpose:

> Test whether explicit boundary filtration makes the high-recall pool precise enough to be viable.

### BA3 — Contrastive boundary verifier

Use:

```text
BA2
+ retrieved contrastive demonstrations
+ validated development hard negatives
```

### BA4 — Optional selective second verifier

Only if BA2/BA3 are close to eligibility but miss the precision requirement.

Use:

```text
BA3
→ UNCERTAIN only
→ independent second verifier/adjudication
```

Do not run automatically.

---

## 15. Track A metrics

Primary:

```text
span-exact micro precision
span-exact micro recall
span-exact micro F1

distinct-surface precision
distinct-surface recall
distinct-surface F1
```

Boundary metrics:

```text
boundary-validator precision
boundary-validator recall
exact-boundary recovery
nested-valid recall
non-nested recall
over-long FP count/rate
under-long FP count/rate
invalid-nested FP count/rate
descriptive-wrapper FP count/rate
UNCERTAIN rate
accepted-after-boundary count
candidate-to-final compression
```

Waterfall:

```text
proposed
→ first-pass selected
→ boundary accepted
→ concepthood accepted
→ placed
→ canonicalised
```

Report each loss separately.

---

## 16. Track A development gates

STOP 1 must reconcile the exact current baselines before using these values.

Unless Research amends them, use:

```text
exact F1:
    >= U0 + 0.02
    OR paired section-bootstrap lower bound > 0

exact precision:
    >= U0 - 0.02

exact recall:
    >= U0 + 0.05

distinct-surface precision:
    >= U0 - 0.05

distinct-surface recall:
    >= U0 + 0.05
    OR no material regression from frozen high-recall reference

over-long FP rate:
    >= 25% lower than frozen CR-014 V3

identity-safety violations:
    0

gold leakage:
    0
```

Also report nested recall.

Do not change the gates after viewing outcomes without Research amendment.

---

# TRACK B — Evidence-Aware Identity Linking

## 17. Track B purpose

Track B starts only after a concept is already accepted.

It answers:

> Is this current accepted concept the same canonical concept as something already known?

It does not decide:

- whether the current boundary is valid;
- whether the phrase is a concept;
- whether HippoRAG retrieval itself proves identity.

---

## 18. Identity linking flow

```text
ACCEPTED CURRENT CONCEPT
        ↓
DETERMINISTIC IDENTITY RULES
        ↓
if unresolved
        ↓
CURRENT-ONLY RETRIEVAL QUERY
        ↓
PRIOR SOURCE EVIDENCE
        ↓
MAP PRIOR EVIDENCE TO HISTORICAL NODES
        ↓
IDENTITY VERIFIER
        ↓
SAME_EXISTING
NEW_CONCEPT
RELATED_NOT_SAME
DIFFERENT
INSUFFICIENT_EVIDENCE
        ↓
HARD IDENTITY SAFETY GUARDS
        ↓
prediction/review decision
```

HippoRAG retrieval score is never the identity decision.

---

## 19. Identity verifier input

For each current concept / historical candidate pair:

```text
CURRENT
- exact current span
- sentence
- limited paragraph
- section heading
- current/proposed type

HISTORICAL CANDIDATE
- canonical node name
- aliases
- node type
- first accepted evidence
- selected prior evidence

MEMORY EVIDENCE
- top-k prior passages
- source sections
- locators
- retrieval backend
- rank/score

SAFETY
- existing curated identity decision
- explicit DIFFERENT flags
```

Forbidden:

```text
gold identity
future section evidence
held-out identity labels
historical human test answer
```

---

## 20. Identity verifier output

Strict outputs:

```text
SAME_EXISTING
NEW_CONCEPT
RELATED_NOT_SAME
DIFFERENT
INSUFFICIENT_EVIDENCE
```

If:

```text
SAME_EXISTING
```

also return:

```text
target_node_id
current_evidence_locator
prior_evidence_locator
```

No chain-of-thought.

---

## 21. Mutation policy

During development:

```text
memory-supported SAME_EXISTING
→ prediction/review record only
→ no authoritative production merge
```

Do not mutate the authoritative graph during Track B development.

Automatic identity mutation remains disabled until the precision gate and sample-size requirement pass and Research approves migration.

A curated `DIFFERENT` decision always vetoes verifier SAME.

---

## 22. Track B arms

### ID0 — Frozen current canonicalisation

Current deterministic/production identity logic.

### ID1 — New identity verifier, no cross-section retrieval

Input:

```text
current concept/context
+
existing frozen canonical-node information
```

Purpose:

> Determine whether the new identity consumer itself improves identity decisions.

### ID2 — Dense prior evidence

Use:

```text
same identity verifier
+
dense prior-passage retrieval
```

### ID3 — HippoRAG prior evidence

Use:

```text
same identity verifier
+
HippoRAG prior-passage retrieval
```

Critical comparison rule:

```text
ID2 and ID3 use the same:
identity prompt
identity model
top_k
evidence-packet size
decision schema
canonical-node mapping
query generation
source corpus/chunks
```

Only the retrieval backend should differ.

---

## 23. HippoRAG invariants

Reuse the pinned CR-016 environment unless STOP 1 identifies a reproducibility issue.

Preserve:

```text
causal source order
future-section retrieval impossible
raw prior paragraphs first
same corpus for dense/HippoRAG
same embedding family where architecture permits
project adapter/logging
retrieval provenance
independent arm indexes
```

HippoRAG OpenIE graph remains retrieval-only.

---

## 24. Causal memory indexing

When processing section `S_n`:

```text
memory before S_n
=
raw source from S_1 ... S_(n-1)
```

After section output is frozen:

```text
freeze section
→ index raw paragraphs
→ continue
```

Forbidden:

```text
pre-index full textbook
index current section before current identity decisions
retrieve future section
```

Future retrieval must hard-fail.

---

## 25. Track B metrics

Primary:

```text
existing-node link precision
existing-node link recall
existing-node link F1
```

Safety/error:

```text
false-new-node rate
false-link rate
false-merge rate
RELATED_NOT_SAME accuracy
DIFFERENT accuracy
INSUFFICIENT rate
identity-safety violations
```

Recurrence slices:

```text
exact-surface recurrence
alias recurrence
acronym recurrence
different-boundary recurrence
low lexical overlap
short-gap
long-gap
same-surface-different-sense
```

Operational:

```text
retrieval latency
identity-verifier calls
cost
memory size
provenance completeness
```

Always show raw support counts for thin slices.

---

## 26. Track B development gates

### Auto-link safety

Require:

```text
SAME_EXISTING precision >= 0.98
```

and where sample size supports it:

```text
Wilson lower bound >= 0.95
```

If the lower bound is not supportable due to insufficient sample size:

```text
automatic linking remains disabled
```

The arm may still qualify as review/ranking assistance.

### Additional safety

```text
identity-safety violations = 0

false-link regression vs ID0 <= 0.01 absolute

NEW-concept false-link/suppression:
no material regression

provenance completeness = 1.00
```

### Benefit versus ID0

Require either:

```text
existing-node link F1 >= ID0 + 0.05
```

or:

```text
false-new-node rate reduced by >= 25%
```

### HippoRAG-specific benefit versus dense ID2

Require either:

```text
existing-node link F1 >= ID2 + 0.03
```

or:

```text
low-overlap/long-gap identity recall >= ID2 + 0.05
```

with:

```text
precision delta vs ID2 >= -0.01
identity-safety violations = 0
```

If dense performs equivalently, prefer dense retrieval.

---

## 27. Track separation

Possible independent outcomes:

```text
Track A passes, Track B fails
→ boundary-only candidate

Track A fails, Track B passes
→ identity-only candidate

Both pass
→ combined 2×2 candidate

Both fail
→ no CR-018 production candidate
```

Do not let Track A success justify Track B.

Do not let Track B success justify Track A.

---

## 28. Fresh-data policy

At STOP 1, repeat the contamination audit across all earlier CRs.

Previously reserved section IDs are only **candidates** for freshness until verified.

No fresh section may be consumed for:

```text
prompt design
hard negatives
contrastive examples
development error analysis
```

before the split is frozen.

Do not consume fresh sections until at least one track passes development.

---

## 29. Fresh gold requirements

### Concept/boundary gold

Preferred final provenance:

```text
HUMAN_REVIEWED_MODEL_DRAFT
```

Workflow:

```text
model draft
→ owner reviews every annotation
→ corrections allowed
→ freeze
→ hash
→ block prediction code from gold
```

### Identity gold

Where applicable, include:

```text
current concept ID
PREVIOUSLY_SEEN vs NEW
correct historical canonical node
alias/acronym recurrence
same-surface-different-sense
prior supporting occurrence
```

Model-only labels remain:

```text
MODEL_GENERATED_DIAGNOSTIC
```

and cannot support a human-validated production claim.

---

## 30. Fresh causal evaluation

For identity/memory arms:

```text
start clean arm-specific state
process sections in identical frozen source order
maintain independent node registry
maintain independent memory index
score only designated held-out sections
freeze section before indexing it
```

Intervening sections may provide unscored runtime context.

Do not evaluate held-out target sections against an empty historical registry.

---

## 31. Error taxonomy

Reuse existing earliest-failure codes and add:

### Boundary

```text
BV0 valid span rejected
BV1 over-long span accepted
BV2 under-long span accepted
BV3 invalid nested span accepted
BV4 valid nested span rejected
BV5 descriptive wrapper accepted
BV6 uncertainty forced incorrectly
```

### Identity

```text
ID0 correct historical node not retrieved
ID1 correct node retrieved but verifier says NEW
ID2 wrong historical node linked
ID3 RELATED_NOT_SAME collapsed to SAME
ID4 SAME incorrectly left NEW
ID5 hard DIFFERENT attempted
ID6 wrong-sense evidence dominated decision
ID7 memory provenance incomplete
```

Use earliest-failure attribution.

Do not double-count downstream consequences.

---

## 32. Trace contract

Required stages:

```text
boundary_family
boundary_validate
concept_validity
mention_placement

memory_query
memory_retrieval
identity_candidate
identity_verify
identity_decision
memory_update
```

Required trace chain:

```text
proposal
→ family
→ first-pass selection
→ explicit boundary verdict
→ concepthood verdict
→ placement
→ identity rules
→ memory query if unresolved
→ retrieved evidence
→ identity verifier
→ canonical node
```

Every model-influenced event stores:

```text
model_id
prompt_version
config_hash
input_refs
output_refs
source_locators
decision_code
```

No chain-of-thought field.

---

## 33. CR-017 headline evaluation

If CR-017 is available during CR-018 end-to-end evaluation, report:

```text
Concept F1
Ancestor Hierarchy F1
Pair Recall
Relation Macro F1
Strict E2E Edge F1
```

Primary attribution remains:

```text
Track A
→ concept precision/recall/F1

Track B
→ identity-linking diagnostics
```

Do not expect Track B alone to improve raw mention extraction.

If hierarchy/relation gold is not available:

```text
NOT_EVALUABLE
```

Do not synthesize missing gold.

---

## 34. Cost contract

STOP 1 must produce repository-specific estimates.

Suggested preflight categories:

```text
BA2 / BA3
BA4 if justified
ID1
ID2
ID3
combined C0-C3
fresh causal evaluation
```

Do not make paid calls before STOP 1 approval.

Do not run BA4 solely because budget remains.

Do not run expensive HippoRAG identity evaluation before proving the ID1/ID2 comparison infrastructure works.

---

## 35. Required repository artifacts

Expected semantics:

```text
docs/change-requests/
    CR-018-boundary-verification-memory-identity.md

PROMPT-CR-018.md

configs/
    cr018_boundary.yaml
    cr018_identity.yaml
    cr018_manifest.yaml

prompts/
    cr018_boundary_verifier_v1.md
    cr018_boundary_verifier_contrastive_v1.md
    cr018_identity_verifier_v1.md
    cr018_boundary_adjudicator_v1.md

src/cumap/cr018/
    boundary_validator.*
    boundary_demo_retrieval.*
    identity_consumer.*
    identity_evidence_packet.*
    causal_identity_memory.*

data/interim/checks/cr018/
    boundary_audit_blind.csv
    boundary_hard_negative_bank.*
    boundary_demo_bank.*
    identity_dev_cases.*

reports/cr018/
    STOP1_RECONCILIATION.md
    boundary_convention_audit.md
    boundary_ablation.md
    identity_ablation.md
    combined_ablation.md
    cost.md
    heldout_results.md
    downstream_compatibility.md
    FINAL_DECISION_EVIDENCE.md

tests/fixtures/cr018/
    boundary/
    identity/
    memory/
    combined/
```

Machine-readable:

```text
boundary_families.jsonl
boundary_verdicts.jsonl
concept_validity.jsonl
memory_queries.jsonl
memory_retrievals.jsonl
identity_cases.jsonl
identity_verdicts.jsonl
combined_outputs.jsonl
trace_manifest.json
```

Exact file paths may follow repository conventions discovered at STOP 1.

---

## 36. Minimum test contract

### Boundary verifier

- target offsets exactly match source;
- family alternatives are visible;
- verifier cannot invent text;
- multiple valid nested spans can survive;
- longest-match cannot suppress a boundary-approved nested span;
- over-long/under-long fixtures produce deterministic labels;
- `UNCERTAIN` is not silently accepted;
- held-out examples cannot enter demo retrieval;
- hard-negative provenance is retained.

### Boundary / concepthood separation

- boundary rejection cannot be reported as `REJECT_NOT_CONCEPT`;
- concepthood sees only boundary-approved spans;
- concepthood cannot expand/shrink span;
- earliest rejection stage is traceable.

### Identity consumer

- unresolved concept can become NEW without memory support;
- retrieved passage does not imply SAME;
- hard DIFFERENT always vetoes SAME;
- RELATED_NOT_SAME never merges;
- same-surface/different-sense fixture stays separate;
- verifier cannot link to node not present in its candidate/evidence packet;
- development prediction can be scored without mutating production.

### Causal memory

- section `n` cannot retrieve section `n` or later;
- every arm has independent index state;
- current section indexed only after output freeze;
- future retrieval hard-fails;
- provenance complete.

### Dense/HippoRAG parity

- same source chunks;
- same current query;
- same top_k where feasible;
- same identity prompt;
- same identity model;
- only retrieval backend differs.

### Reproducibility

- exact code revision recorded;
- exact model IDs;
- prompt hashes;
- config hashes;
- source-order hash;
- HippoRAG commit/environment identity;
- random seeds where applicable.

---

## 37. Required visualisations

Generate only from real result artifacts.

### Boundary

1. exact P/R/F1 by BA arm;
2. stage waterfall;
3. over-long / under-long / invalid-nested FP counts;
4. nested-valid recall;
5. boundary confusion matrix;
6. candidate-volume → final-volume compression.

### Identity

7. link P/R/F1 by ID arm;
8. false-new-node and false-link rate;
9. dense vs HippoRAG identity gain by recurrence slice;
10. identity gain vs section distance;
11. retrieval success → identity-use waterfall.

### Combined

12. C0–C3 comparison if both tracks qualify.

Do not fabricate plots before metrics exist.

---

## 38. Interpretation rules

If Track A improves precision, report:

```text
explicit family-aware boundary filtration improved the candidate pool
```

Do not claim:

```text
the model understands concepts better
```

If HippoRAG improves identity linking, report:

```text
retrieved prior evidence improved cross-section identity/linking decisions
```

Do not claim:

```text
HippoRAG improved the final Expert KG
```

unless end-to-end graph evaluation supports it.

If dense retrieval performs equivalently:

```text
prefer dense
```

unless HippoRAG has a clearly justified difficult-slice benefit with no safety regression.

Do not describe model-generated benchmark agreement as human accuracy.

---

## 39. Possible final statuses

CR-018 may finish as:

```text
COMBINED_ELIGIBLE_FOR_MIGRATION

BOUNDARY_ONLY_ELIGIBLE_FOR_MIGRATION

IDENTITY_ONLY_ELIGIBLE_FOR_MIGRATION

BOUNDARY_REVIEW_ONLY

IDENTITY_REVIEW_ONLY

NO_ELIGIBLE_CR018_ARM

STOPPED_BOUNDARY_GOLD_AMBIGUOUS

STOPPED_NO_FRESH_HELDOUT
```

Negative results are valid.

---

## 40. Definition of done

CR-018 is complete only when:

- proposal generation remained frozen during Track A;
- boundary validity and concepthood remained separate;
- the human boundary-convention audit was completed by a human rather than a model;
- Track A was evaluated independently;
- Track B used only accepted concepts;
- the new identity consumer was evaluated separately from retrieval quality;
- ID2 and ID3 differed only in retrieval backend;
- hard identity safeguards remained authoritative;
- HippoRAG never acted as identity authority;
- no development identity prediction mutated the authoritative graph;
- causal memory order was enforced;
- fresh data remained sealed until prospective evaluation;
- combined 2×2 was run only if both tracks independently passed;
- no held-out tuning or quality retries occurred;
- CR-017 headline metrics were reported where evaluable;
- trace provenance covered all new stages;
- downstream compatibility was measured before migration;
- rollback/rebuild behavior was documented;
- Research/owner received the final evidence before production changes.

---

## 41. Immediate coding-agent instruction

Read this CR and the CR-018 Research handover before changing code.

Execute **STOP 1 only**.

Do not make paid model calls.

Do not modify proposal generation.

Do not modify canonicalisation authority.

Do not run the boundary audit yourself.

Do not build the combined pipeline yet.

Your STOP-1 task is to answer two implementation questions.

### Boundary

> Can the frozen high-recall family-selected span output be passed through a new independent family-aware boundary validator without changing proposal generation, and can the resulting boundary-approved spans pass unchanged into the frozen concepthood verifier?

### Identity

> Can an accepted current concept plus prior retrieved evidence be passed to a new identity verifier without weakening identity safety rules, while making dense and HippoRAG interchangeable retrieval backends?

Return:

```text
reports/cr018/STOP1_RECONCILIATION.md
```

containing:

```text
exact code paths
artifact paths
hashes
data exposure state
human boundary-audit plan
candidate-family volumes
identity-case volumes
integration points
trace changes
test plan
cost preflight
technical blockers
```

If faithful implementation is not possible:

```text
Problem
→ repository evidence
→ why the approved design cannot be implemented faithfully
→ minimal alternatives
→ methodological consequences
→ RESEARCH DECISION REQUIRED
```

Then stop and return to Research.
