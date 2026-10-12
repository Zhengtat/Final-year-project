# CR-015 — Precision Recovery and Nested Boundary Calibration

**Status:** requested by Research, 2026-10-12. This is the implementation CR for approval and handoff to Claude Code.  
**Branch:** `cr-015-precision-boundary-calibration`, created from the final CR-014 state. Merge only after STOP 5 sign-off; tag `cr-015-complete`.  
**Scope:** recover concept-extraction precision after CR-014 by separating boundary selection from concept validity, preserving valid nested mentions, fixing mention-placement suppression, and calibrating verification. The frozen CR-014 U2 proposal universe remains unchanged during the primary CR-015 experiment.  
**Primary production dataset:** Peterson & Davie, *Computer Networks: A Systems Approach*, 6e.  
**Primary research question:** can family-level boundary selection, nested-aware mention placement, and calibrated concept verification recover CR-014's precision loss while preserving its recall improvement?

**Depends on:**
- CR-014 frozen/finalised;
- exact CR-014 U2 proposal definition available;
- exact CR-014 V3 reference implementation/config available;
- current P&D concept evaluation and source-offset infrastructure;
- CR-013/014 trace infrastructure available or reconcilable at STOP 1.

**Does not reopen:**
- proposal-source design as the primary problem;
- proposal-recall architecture;
- canonicalisation semantics;
- relation inventory or relation semantics;
- pair-generation/pair-selection methodology;
- downstream relation architecture;
- graph consolidation;
- misconception semantics;
- historical CR-012/013/014 outputs.

---

## 1. Why

CR-014 changed the failure profile of concept extraction.

The frozen CR-014 V3 system improved mention-level recall and exact F1 over production, but failed the precision adoption gate. CR-015 therefore does **not** reopen proposal recall as the primary research problem.

The remaining failures must be separated into four mechanisms:

```text
BOUNDARY IDENTIFICATION
    Is the proposed span itself correct?

NESTED VALIDITY
    Can both an outer and inner span be valid concepts here?

CONCEPTHOOD
    Is the correctly bounded phrase a standalone technical concept?

MENTION PLACEMENT
    If a concept is valid, does the placement logic actually retain this occurrence?
```

These mechanisms must no longer be collapsed into one opaque `accept/reject` path.

The CR-015 architecture is:

```text
FROZEN CR-014 U2 PROPOSAL UNION
        ↓
EXACT DEDUPLICATION
        ↓
OVERLAP / NESTED SPAN FAMILY CONSTRUCTION
        ↓
BOUNDARY-FAMILY SELECTOR
        ↓
ZERO / ONE / MULTIPLE VALID SPANS
        ↓
INDEPENDENT CONCEPTHOOD VERIFIER
        ↓
OPTIONAL DISAGREEMENT / UNCERTAINTY ADJUDICATION
        ↓
NESTED-AWARE MENTION PLACEMENT
        ↓
FROZEN CANONICALISATION
        ↓
FROZEN DOWNSTREAM KG
```

The core rule is:

> **Boundary validity and concept validity are different questions. A wrong boundary must not automatically become a "not a concept" decision.**

---

## 2. Frozen CR-014 reference

CR-015 must preserve two frozen CR-014 references.

### 2.1 Frozen proposal universe

The proposal source for the primary CR-015 experiment is:

```text
CR-014 U2
```

Implementation must recover its exact repository definition at STOP 1.

CR-015 must not add more LLM samples, a new proposer, a new span model, or new proposal heuristics as part of the primary experiment.

### 2.2 Frozen V3 reference

The exact frozen CR-014 V3 path is the primary reference system.

STOP 1 must recover:

```text
commit / tag
prompt hash
model ID
config hash
temperature / seed / sampling settings
boundary logic
mention-placement logic
verifier logic
pruner behaviour
```

Do not reconstruct V3 from old CR prose.

---

## 3. Research questions

| RQ | Question |
|---|---|
| **RQ1 — Boundary selection** | Can family-level span decisions reduce over-long and under-long errors relative to frozen CR-014 V3? |
| **RQ2 — Nested preservation** | Can valid nested concepts survive without simply retaining every overlapping substring? |
| **RQ3 — Precision recovery** | Can a concepthood verifier recover mention-level and distinct-surface precision without giving back CR-014's recall gain? |
| **RQ4 — Mention placement** | Does current longest-match placement suppress already-valid concepts after verification? |
| **RQ5 — Calibration** | Do contrastive development examples and selective adjudication improve verifier decisions enough to pass frozen gates? |
| **RQ6 — KG compatibility** | If concept gates pass, does the selected CR-015 system avoid unacceptable unique-node, pair-budget, and downstream graph pressure? |

---

## 4. Scope

CR-015 may change:

- overlap-family construction;
- boundary-family selection;
- nested-span retention;
- mention-placement policy;
- verifier prompt/model;
- separation of boundary and concepthood decisions;
- development-only hard-negative generation;
- development-only retrieved contrastive demonstrations;
- selective second-verifier/adjudication logic;
- concept-stage prioritisation/ranking if needed for cost;
- trace fields/stages needed to explain CR-015 decisions.

CR-015 must not change during the primary experiment:

- frozen CR-014 U2 proposal-source definition;
- canonicalisation semantics;
- identity guard semantics;
- relation inventory;
- pair-generation methodology;
- pair-selection methodology;
- relation classifier semantics;
- graph-consolidation semantics;
- historical evaluation outputs;
- held-out scoring definitions after freeze.

A `NO_PRODUCTION_CHANGE` result is valid.

---

## 5. Order of work and stop points

Commit each implementation step with the prefix `CR-015:`.

1. **⛔ STOP 1 — Repository reconciliation + contamination audit — $0**
   - Reconcile the frozen CR-014 U2 proposal definition.
   - Reconcile the frozen CR-014 V3 prompt/model/config/hash.
   - Reconcile longest-match and nested-placement code paths.
   - Reconcile current boundary-family handling.
   - Reconcile current verifier path.
   - Reproduce committed CR-014 error counts from artifacts.
   - Identify exactly where nested mentions are suppressed, over-long spans are introduced, boundary validity and concepthood are conflated, and mention placement loses accepted concepts.
   - Enumerate all P&D sections exposed through CR-014.
   - Determine whether a genuinely fresh CR-015 held-out set exists.
   - Reconcile gold provenance.
   - Reconcile trace stages.
   - Estimate family counts/runtime/cost.
   - **No paid calls.**
   - If no genuinely fresh held-out set can be established, STOP and return to Research.

2. **Stage A — Boundary + placement ablation.**
   - Run A0–A3 on development only.
   - Select one boundary/placement configuration.

   **⛔ STOP 2 — Boundary + placement result.**
   Return A0–A3 metrics, nested/non-nested metrics, over-long/under-long errors, boundary-family confusion matrix, mention-placement loss, distinct-surface P/R/F1, family volume, runtime and cost.

3. **Stage B — Verifier precision recovery.**
   - Run B0–B3 as applicable.
   - Do not run B3 automatically.
   - Freeze one eligible candidate.

   **⛔ STOP 3 — Verifier selection.**
   Return B0–B3 metrics as applicable, mention P/R/F1, distinct-surface P/R/F1, conditional verifier metrics, valid-rejection rate, invalid-acceptance rate, hard-negative slice, retrieval-example slice, disagreement rate, bootstrap ΔF1 and cost.

4. **Fresh held-out evaluation.**
   - Freeze fresh section IDs, gold provenance/hash and implementation hashes.
   - Block prediction code from gold.
   - Run U0 frozen production, frozen CR-014 V3 and frozen CR-015 candidate.
   - Exactly once each.
   - No retries for quality.
   - No manual test fixes.
   - No threshold changes after results.

   **⛔ STOP 4 — Held-out evidence.**
   Return frozen results to Research for adoption decision.

5. **Downstream compatibility + final decision.**
   - Run U0 and selected CR-015 concepts through the same frozen downstream pipeline.
   - Quantify graph pressure.
   - Check identity safety.
   - Verify trace continuity.
   - Create migration/rollback plan.

   **⛔ STOP 5 — Final evidence.**
   Return the full evidence package to Research/owner.

No automatic production migration is permitted.

---

## 6. STOP 1 reconciliation details

STOP 1 is an audit, not a model upgrade.

Required reconciliation:

```text
CR-014 final commit/status
CR-014 STOP 5 completion state

frozen U2 proposal definition
frozen V3 prompt
frozen V3 model ID
frozen V3 config hash
frozen V3 sampling settings

current overlap-family code
current boundary code
current nested-placement code
current longest-match code
current verifier code
current pruner code

current trace schema/stages
current source offsets
current scoring implementation
current cost estimator
current cache behaviour
```

Also reproduce from committed artifacts:

```text
mention-level precision / recall / F1
distinct-surface precision / recall
not-proposed count
verifier-rejected valid count
boundary-loss count
over-long false-positive count
```

Any mismatch between repository evidence and the Research handover must be reported.

---

## 7. Contamination audit

All exposed CR-014 material is development-only for CR-015.

At minimum treat as exposed:

- previously inspected IIR data/results;
- CR-014 pilot sections;
- CR-014 held-out sections;
- CR-014 error analyses;
- CR-014 model-generated gold;
- CR-014 false-positive audits.

Create:

```text
reports/cr015/contamination_audit.md
```

For each dataset/section record:

```text
ID
usage history
whether labels were inspected
whether predictions were inspected
gold provenance
allowed CR-015 use
held-out eligibility
```

The prior CR-014 reserve list is only a candidate pool. STOP 1 must verify actual exposure before declaring any section fresh.

If insufficient untouched sections remain:

```text
STOPPED_NO_FRESH_HELDOUT
```

Return to Research.

---

## 8. Fresh CR-015 benchmark

Preferred split:

```text
development: all exposed CR-014 data
pilot:       1–2 genuinely untouched sections, if available
held-out:    4–6 genuinely untouched sections
reserve:     remaining untouched sections
```

Freeze held-out section IDs before CR-015 predictions.

Selection must not depend on observed model success/failure.

### 8.1 Gold provenance

Every gold record/set must carry one of:

```text
HUMAN_PRIMARY
HUMAN_DUAL
HUMAN_REVIEWED_MODEL_DRAFT
MODEL_GENERATED_DIAGNOSTIC
```

Model-generated gold may support development diagnostics. Results against model-generated gold must be described as `agreement with frozen benchmark`, not `human-validated accuracy`.

Human/owner-reviewed fresh held-out gold is preferred for adoption evidence.

---

## 9. Overlap-family construction

Group overlapping proposal spans within the same sentence into one family.

Example:

```text
control
congestion control
TCP congestion control
TCP congestion control algorithm
```

A family must allow:

```text
zero accepted spans
one accepted span
multiple accepted nested spans
```

Do not impose `choose exactly one`.

### 9.1 Required family fields

```yaml
family_id: str
document_id: str
section_id: str
sentence_id: str | int
source_sentence: str

candidate_spans: []
start_offsets: []
end_offsets: []
token_lengths: []

proposal_sources_by_span: {}
existing_node_matches_by_span: {}
node_type_hypotheses: {}
definition_signals: {}
heading_signals: {}
frequency_features: {}
anchor_features: {}

trace_ids: []
```

Preserve repeated surface occurrences as distinct mentions via offsets.

---

## 10. Boundary-family selector

The boundary selector decides which source-grounded spans are valid boundaries.

Recommended labels:

```text
KEEP_PRIMARY
KEEP_NESTED
EXPAND_TO
SHRINK_TO
REJECT_DESCRIPTIVE
REJECT_GENERIC
REJECT_UNSUPPORTED
```

For `EXPAND_TO` / `SHRINK_TO`, the target must be an exact character range from source text.

The selector must not generate text not found in source.

### 10.1 Boundary output schema

```yaml
family_id: str

decisions:
  - candidate_id: str
    input_start: int
    input_end: int
    input_surface: str

    decision: KEEP_PRIMARY | KEEP_NESTED | EXPAND_TO | SHRINK_TO |
              REJECT_DESCRIPTIVE | REJECT_GENERIC | REJECT_UNSUPPORTED

    output_start: int | null
    output_end: int | null
    output_surface: str | null

    reason_code: str
    evidence_refs: [str]
    model_id: str | null
    prompt_version: str | null
    config_hash: str | null
```

---

## 11. Nested validity

Nested spans survive only when each retained span is independently meaningful under the concept codebook.

Potential valid pair:

```text
TCP congestion control
congestion control
```

Potential invalid wrapper:

```text
effective congestion control
congestion control
```

Do not implement nested handling as `keep all substrings` or `keep only longest span`.

The family selector must explicitly decide nested validity.

---

## 12. Mention placement

Mention placement occurs after a span has survived boundary and concepthood decisions.

CR-015 must test whether current longest-match logic erases already-valid nested concepts.

Rules:

- independently valid overlapping concepts may both be placed;
- invalid substrings must not survive merely because they are nested;
- mention placement must preserve exact source offsets;
- repeated occurrences of the same surface are separate mention records;
- mention-placement loss must be measured explicitly.

Recommended output:

```yaml
mention_id: str
concept_candidate_id: str
document_id: str
section_id: str
sentence_id: str | int
start_offset: int
end_offset: int
surface: str
placement: PLACED | SUPPRESSED | NOT_APPLICABLE
reason_code: str | null
trace_ids: []
```

---

## 13. Development hard-negative bank

Generate boundary-specific negatives from **development gold only**.

Permitted transformations:

```text
gold span ± 1 token
gold span ± 2 tokens
head-only span
modifier-only span
parent noun phrase
child noun phrase
same head + wrong modifier
descriptive wrapper around gold
process/entity near-pair where relevant
```

Required provenance:

```yaml
hard_negative_id: str
source_gold_id: str
transformation: str
source_sentence: str
span: str
start_offset: int
end_offset: int
reason_expected_negative: str
```

Uses:

- boundary demonstrations;
- boundary evaluation;
- optional local ranker;
- verifier calibration.

Never generate the bank from fresh held-out gold.

---

## 14. Independent concepthood verifier

After boundary selection, the verifier answers only:

> **Is this correctly bounded phrase an independently valid technical concept in this context?**

Allowed outputs:

```text
ACCEPT_NEW
LINK_EXISTING
REJECT_NOT_CONCEPT
REJECT_GENERIC
REJECT_WRONG_SENSE
INSUFFICIENT_EVIDENCE
```

The verifier must not repair the boundary in the same decision.

### 14.1 Allowed inputs

- exact selected span;
- source sentence;
- limited local paragraph context;
- section title;
- concept codebook;
- boundary-family metadata;
- proposal provenance;
- legitimate existing-node matches;
- selected development-only demonstrations.

### 14.2 Forbidden inputs

- held-out gold;
- hidden benchmark IDs encoding gold;
- previous held-out errors;
- final answer from another verifier when independence is claimed;
- held-out examples in retrieval bank.

---

## 15. Retrieved contrastive demonstrations

If B2 is implemented, retrieve demonstrations only from the frozen development bank.

Retrieval priority:

1. similar overlap-family structure;
2. same/similar syntactic head;
3. similar token length;
4. same node-type family where available;
5. similar surrounding syntax;
6. contextual similarity.

Prefer paired positive/negative contrasts.

Example:

```text
VALID:
distance-vector routing protocol

VALID:
link-state routing protocol

INVALID / descriptive:
operation of the routing protocol

INVALID / over-long:
choice of a routing protocol for the network
```

Every retrieval record must preserve:

```text
query example ID
retrieved example IDs
ranking features
scores
bank hash
```

Fresh held-out annotations must never enter the retrieval bank.

---

## 16. Selective consensus / adjudication

B3 is optional.

Do not make two-verifier consensus the default.

Architecture:

```text
Verifier A
Verifier B

A accept + B accept
    → accept

A reject + B reject
    → reject

disagreement
    → adjudication
```

Requirements:

- A and B are independent when independence is claimed;
- neither sees the other's decision;
- unanimous outcomes do not trigger adjudication;
- disagreement triggers a third call only in B3;
- adjudicator receives family/codebook context;
- all calls preserve provenance.

Run B3 only if B0–B2 do not satisfy development gates and there remains a justified precision-recovery hypothesis.

---

## 17. Optional local span ranker

A local ranker may be tested only if runtime/cost becomes materially problematic.

Possible features:

- span start/end representation;
- token length;
- POS / NP structure;
- definition cue;
- heading cue;
- recurrence;
- multi-source agreement;
- existing-KG match;
- local contextual embeddings;
- boundary-neighbour features.

Arms:

| Arm | Design |
|---|---|
| **C0** | selected B arm, no gating |
| **C1** | ranker for prioritisation only |
| **C2** | ranker with development-selected gate |

Hard rule:

> A ranker must not silently create a new recall ceiling.

If C2 gates candidates, report recall before and after the threshold, including one-token and nested slices.

---

## 18. Stage A experiment — boundary and placement

| Arm | Change from frozen CR-014 V3 | Purpose |
|---|---|---|
| **A0** | exact frozen V3 | reference |
| **A1** | nested-aware placement only | isolate longest-match suppression |
| **A2** | family-level boundary selector + nested-aware placement | test family selection |
| **A3** | A2 + development hard-negative contrastive examples | reduce over-long spans |

Do not change verifier design while comparing A0–A3.

Select one boundary/placement configuration before Stage B.

---

## 19. Stage B experiment — precision recovery

Use the selected Stage-A configuration.

| Arm | Verifier design | Purpose |
|---|---|---|
| **B0** | current frozen CR-014 verifier | boundary-only comparison |
| **B1** | separate concepthood verifier | separate boundary from validity |
| **B2** | B1 + retrieved contrastive development demonstrations | guideline/example effect |
| **B3** | B2 + selective independent second-verifier adjudication | consensus effect |

B3 is optional.

Do not automatically spend on B3 if B1/B2 already pass development gates.

---

## 20. Primary metrics

### 20.1 Mention-level metrics

Primary:

```text
span-exact micro precision
span-exact micro recall
span-exact micro F1
```

Also report:

- macro section F1;
- one-token P/R/F1;
- multi-token P/R/F1;
- nested-mention recall;
- non-nested recall;
- boundary error rate;
- over-long FP rate;
- under-long/partial rate.

### 20.2 Distinct-surface / graph-entry metrics

Mandatory:

```text
distinct-surface precision
distinct-surface recall
distinct-surface F1
new unique accepted surfaces
candidate-to-final compression ratio
```

Do not treat these as optional diagnostics.

### 20.3 Stage-conditional metrics

```text
proposal recall
boundary-selector exact recovery rate
boundary-selector nested recovery rate
valid-concept rejection rate
invalid-concept acceptance rate
verifier recall conditional on correct boundary
mention-placement loss after acceptance
adjudication disagreement rate
```

### 20.4 System metrics

```text
API calls
input/output tokens
wall-clock runtime
cost
cost per correct unique concept
cost per correct mention
candidate families per section
average family size
```

---

## 21. Error taxonomy

Each gold miss receives one earliest applicable category:

```text
P0  not proposed by frozen U2
B0  correct concept represented only by wrong boundary
B1  family selector chose over-long boundary
B2  family selector chose under-long boundary
B3  valid nested concept suppressed
V0  correctly bounded valid concept rejected by verifier
V1  valid new concept incorrectly linked to existing concept
M0  accepted valid concept not placed at this mention
R0  later concept-stage pruning removed valid concept
C0  canonicalisation split / identity failure
C1  false merge
E0  evidence / locator failure
```

False positives:

```text
F0  generic noun / non-concept
F1  descriptive wrapper around valid concept
F2  over-long technical span
F3  under-long / partial span
F4  invalid nested substring
F5  duplicate alias treated as new concept
F6  wrong sense / polysemy
F7  unsupported / hallucinated concept
F8  type / ontology incompatibility
```

Use earliest-causal attribution and do not double-count downstream consequences.

---

## 22. Development selection gates

A CR-015 arm is eligible for freeze only if, on development:

1. mention exact F1 is at least **+0.02 absolute over U0** **OR** paired section-level bootstrap 95% lower bound for ΔF1 vs U0 is > 0;
2. mention precision is **>= U0 − 0.02**;
3. mention recall is **>= U0 + 0.05**;
4. one-token recall is **>= U0 − 0.02**;
5. distinct-surface precision is **>= U0 − 0.05**;
6. distinct-surface recall is **>= U0 + 0.05** **OR** does not fall more than 0.03 below frozen CR-014 V3;
7. over-long FP rate is reduced by at least **25% relative to frozen CR-014 V3**;
8. no identity/provenance violation is introduced;
9. no gold leakage is detected.

If multiple eligible arms are within 0.02 mention F1:

1. prefer higher distinct-surface precision;
2. then higher mention recall;
3. then lower cost/fewer calls;
4. then simpler architecture.

Freeze before held-out:

```text
code revision
prompt hashes
model IDs
temperature / seed / sampling
boundary rules
retrieval bank hash
hard-negative bank hash
thresholds
trace schema version
```

---

## 23. Fresh held-out adoption gates

Run exactly once:

```text
U0 frozen production
CR-014 V3 frozen reference
CR-015 selected candidate
```

on fresh CR-015 held-out.

CR-015 is eligible for downstream migration analysis only if:

| Gate | Requirement |
|---|---:|
| Mention exact F1 | >= U0 + 0.02 OR paired bootstrap lower bound > 0 |
| Mention precision | >= U0 - 0.02 |
| Mention recall | >= U0 + 0.05 |
| One-token recall | >= U0 - 0.02 |
| Distinct-surface precision | >= U0 - 0.05 |
| Distinct-surface recall | >= U0 + 0.05 |
| Over-long FP rate | >=25% lower than frozen CR-014 V3 |
| Gold leakage | 0 |
| Evidence/provenance completeness | 1.00 for accepted predictions |
| Identity-guard violations caused by concept stage | 0 |
| Test-time manual fixes | 0 |

Passing these gates does **not** automatically migrate production.

If a gate fails:

```text
NOT_ADOPTED
```

Do not tune and rerun the same held-out set.

---

## 24. Downstream compatibility

Only after STOP 4 is frozen, run:

```text
U0 concepts
selected CR-015 concepts
```

through the same downstream pipeline.

Report:

```text
node count
unique node growth
pair-candidate growth
pair-budget saturation
selected-pair count
relation count
unsupported/evidence-weak edge indicators
identity-guard violations
canonicalisation merge/split changes
trace coverage
cost
```

If independent relation gold does not exist, do not claim a measured false-edge rate.

Use observable downstream diagnostics or an explicitly blind human edge audit.

Production adoption requires Research/owner approval after this stage.

---

## 25. Trace extension

Reuse the existing trace schema.

CR-015 may add stages:

```text
boundary_family
concept_validity
mention_placement
adjudication
```

Do not rename or rewrite historical stages.

Every new event must preserve at least:

```text
event_id
run_id
dataset_mode
document_id
section_id
stage
object_type
object_id
input_refs
output_refs
action
outcome
reason_code
evidence_refs
score / threshold where recorded
model_id
prompt_version
config_hash
authority
source_artifact
source_locator
```

The trace should answer:

```text
Why was this longer span chosen?
Why was this shorter nested concept suppressed?
Why was this proposed valid concept rejected?
Was the rejection boundary-based or concepthood-based?
Which verifier(s) disagreed?
Why was this mention not placed after acceptance?
```

Do not generate free-form post-hoc reasoning.

---

## 26. Cost contract

Planning limits:

```text
STOP 1 reconciliation / local analysis      $0 API
STOP 2 boundary / placement pilot           <= $5 soft target
STOP 3 verifier precision ablations         <= $15 soft target
STOP 4 fresh held-out                       <= $10 soft target
STOP 5 downstream compatibility             <= $5 soft target

warning threshold                           $25 cumulative
hard cap before new approval                $35 cumulative
```

STOP 1 must replace rough estimates with active repository pricing.

Do not run B3 merely because budget remains.

---

## 27. Required repository artifacts

Create at least:

```text
docs/change-requests/
    CR-015-precision-recovery-boundary-calibration.md

PROMPT-CR-015.md

configs/
    cr015_concept_precision.yaml
    cr015_manifest.yaml

prompts/
    cr015_boundary_family_v1.md
    cr015_concept_verifier_v1.md
    cr015_adjudicator_v1.md

docs/annotation/
    cr015_boundary_annotation_delta.md

data/interim/checks/cr015/
    hard_negative_bank.*
    retrieved_demo_bank.*
    boundary_family_audit_blind.csv
    fresh_pilot_blind.csv
    fresh_test_blind.csv

reports/cr015/
    STOP1_RECONCILIATION.md
    contamination_audit.md
    boundary_ablation.md
    nested_placement_analysis.md
    hard_negative_analysis.md
    verifier_ablation.md
    retrieval_analysis.md
    consensus_analysis.md
    cost.md
    heldout_results.md
    downstream_compatibility.md
    FINAL_DECISION_EVIDENCE.md

tests/fixtures/cr015/
    ...
```

Useful machine-readable outputs:

```text
span_families.jsonl
boundary_decisions.jsonl
concept_validity_decisions.jsonl
mention_placement.jsonl
adjudication_decisions.jsonl
trace_manifest.json
```

Reconcile exact paths with repository conventions at STOP 1.

---

## 28. Minimum tests

### Boundary family

- overlapping spans form one family;
- non-overlapping spans do not;
- offsets are exact;
- family supports zero/one/multiple accepted spans;
- descriptive wrapper can be rejected while inner concept survives;
- outer and inner concepts can both survive;
- repeated surface occurrences keep distinct offsets.

### Boundary / concepthood separation

- wrong boundary is not silently converted to `REJECT_NOT_CONCEPT`;
- boundary repair cannot create absent source text;
- concepthood verifier receives an already-selected span;
- boundary output remains traceable to proposal input.

### Nested placement

- two independently valid overlapping concepts can both be placed;
- invalid nested substring is not automatically accepted;
- longest-match logic cannot erase a boundary-approved valid nested concept;
- mention-placement loss is measured.

### Hard negatives

- generated only from development gold;
- transformation provenance stored;
- fresh held-out gold cannot enter bank;
- ±1/±2 token variants deterministic.

### Retrieval

- retrieval restricted to development bank;
- held-out examples cannot be retrieved;
- retrieval stores source IDs and ranking features.

### Consensus

- independent verifier calls do not see each other's decisions;
- disagreement invokes adjudication only in B3;
- unanimous outcomes do not trigger third call.

### Leakage

- held-out gold cannot be read by prediction code;
- held-out IDs cannot leak into few-shot banks;
- `data/gold` remains read-only to pipeline code;
- model-generated labels are never represented as human labels.

### Frozen downstream

- canonicalisation semantics unchanged;
- relation registry unchanged;
- pair-selection config unchanged during concept experiment;
- historical evaluation snapshots immutable.

### Traceability

- every accepted/rejected span has proposal → family → boundary → validity → placement lineage;
- missing fields remain explicit null / `NOT_RECORDED`;
- no chain-of-thought field exists.

---

## 29. Required visualisations

Generate only from frozen result files.

1. **Precision / recall / F1 comparison**
   - U0;
   - CR-014 V3;
   - CR-015 arms.

2. **Error waterfall**
   ```text
   proposal
   → boundary
   → verifier
   → mention placement
   → canonicalisation
   ```

3. **Boundary-family outcome matrix**
   - exact keep;
   - nested keep;
   - expand;
   - shrink;
   - reject.

4. **Over-long FP counts**
   - U0;
   - V3;
   - selected CR-015.

5. **Mention vs distinct-surface precision**
   - display together.

6. **Nested vs non-nested recall**

7. **Cost vs correct distinct concepts**

Do not fabricate charts before results exist.

---

## 30. Interpretation rules

Reports must distinguish:

```text
proposal recall
boundary accuracy
concept-validity precision
mention placement
unique-node precision
downstream graph effects
```

Do not claim higher nested recall means higher KG quality without downstream evidence.

Do not describe benchmark agreement against model-generated gold as human-validated accuracy.

Do not claim that one model "reasoned better" based only on outputs.

Do not describe reconstructed/replayed metadata as if it were originally recorded.

---

## 31. Final decision states

`FINAL_DECISION_EVIDENCE.md` must end with exactly one of:

```text
ADOPTABLE_PENDING_MIGRATION_APPROVAL
NOT_ADOPTED
NO_ELIGIBLE_DEVELOPMENT_ARM
STOPPED_NO_FRESH_HELDOUT
```

The report must separately answer:

1. Did family-level boundary selection reduce over-long errors?
2. Did nested-aware placement recover valid nested mentions?
3. Did concepthood verification improve precision without sacrificing recall?
4. Did contrastive demonstrations help?
5. Was consensus/adjudication necessary?
6. Did distinct-surface precision recover sufficiently?
7. Did CR-015 increase or reduce unique-node inflation?
8. What downstream pair/edge pressure resulted?
9. Should production remain unchanged or proceed to migration review?

Do not collapse these into one composite score.

---

## 32. Definition of done

CR-015 is complete only when:

- frozen CR-014 U2 proposal generation remained unchanged;
- frozen CR-014 V3 reference was reconciled;
- boundary and concept validity were experimentally separated;
- nested-aware placement was explicitly tested;
- hard-negative boundary evidence was tested on development;
- mention-level and distinct-surface metrics were both reported;
- genuinely fresh held-out data was established, or Research explicitly stopped the CR;
- one development arm was frozen before held-out, if eligible;
- held-out ran once;
- no test-time quality retries occurred;
- no manual held-out fixes occurred;
- precision-recovery gates were evaluated prospectively;
- downstream node/pair pressure was measured before migration;
- identity protections remained intact;
- trace provenance remained complete;
- costs were reported;
- Research/owner received the final frozen evidence.

**No automatic production migration is permitted.**

---

## 33. Immediate coding-agent instruction

Read this CR and the CR-015 Research handover before changing code.

Execute **STOP 1 only** first.

Do not start by building a stronger verifier.

Your first task is to determine from the actual repository:

1. the exact frozen CR-014 U2/V3 implementation;
2. where nested mentions are currently suppressed;
3. where over-long spans are introduced;
4. whether boundary and concepthood are currently conflated;
5. where accepted concepts can be lost during mention placement;
6. which CR-014 data is now development-only;
7. whether genuinely untouched P&D sections remain;
8. expected overlap-family volume;
9. expected call/runtime/cost.

Return:

```text
reports/cr015/STOP1_RECONCILIATION.md
reports/cr015/contamination_audit.md
```

plus the exact repository paths and any methodological blocker.

Make:

```text
0 paid calls
0 held-out runs
0 prompt/model/threshold changes
```

before Research approves STOP 1.

If repository reality prevents faithful execution, return:

```text
Problem
→ why the approved design cannot be implemented
→ available alternatives
→ methodological consequences
→ RESEARCH DECISION REQUIRED
```

Do not silently substitute another method.

---

## 34. Items log

| # | Item | Status |
|---|---|---|
| 1 | STOP-1 CR-014 U2/V3 reconciliation | Requested |
| 2 | CR-015 contamination audit + fresh split feasibility | Requested |
| 3 | Overlap/nested span-family representation | Requested |
| 4 | Family-level boundary selector | Requested |
| 5 | Nested-aware mention placement | Requested |
| 6 | Development hard-negative bank | Requested |
| 7 | Separate concepthood verifier | Requested |
| 8 | Retrieved contrastive demonstration arm | Requested |
| 9 | Selective consensus/adjudication arm | Requested, optional |
| 10 | Optional local span ranker | Requested only if cost/runtime warrants |
| 11 | Stage-A A0–A3 boundary/placement ablation | Requested |
| 12 | Stage-B B0–B3 verifier ablation | Requested |
| 13 | Fresh held-out U0/V3/CR-015 comparison | Requested |
| 14 | Downstream compatibility analysis | Requested |
| 15 | CR-015 trace extension | Requested |
| 16 | Migration/rollback evidence package | Requested |
