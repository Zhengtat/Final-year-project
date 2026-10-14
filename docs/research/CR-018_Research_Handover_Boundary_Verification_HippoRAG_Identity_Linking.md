# RESEARCH HANDOVER — CR-018 Explicit Boundary Verification + HippoRAG Evidence-Aware Identity Linking

**Project:** zt FYP / Conceptual Understanding Mapper (CUMAP)  
**From:** Research  
**To:** Implementation chat / `fyi implementation`  
**Date:** 2026-10-14  
**Status:** Research design for implementation  
**Scope:** Two staged, independently attributable changes:
1. explicit boundary verification for precision recovery from the high-recall concept pool;
2. HippoRAG-backed evidence-aware identity linking for unresolved cross-section identity decisions.

> **Core rule:** CR-018 must not bundle the two hypotheses into one opaque pipeline change. Boundary verification and memory-aware identity linking must each be tested independently before any combined arm is allowed.

---

# 0. Executive purpose

CR-015 and CR-016 established two separate bottlenecks.

## CR-015 finding

The high-recall concept pipeline can recover many more valid/nested concepts, but precision collapses because boundary selection remains too permissive.

Observed development pattern:

```text
high-recall candidate pool
    ↓
family-level boundary selection
    ↓
large recall improvement
    ↓
many invalid nested / under-long / over-long spans
    ↓
concepthood-only verifier cannot recover precision
```

The important CR-015 diagnosis was:

> The remaining precision problem is not proposal recall alone and not concepthood verification alone. The system needs an explicit boundary-validity decision before concepthood verification.

## CR-016 finding

HippoRAG 2 retrieved useful prior evidence better than dense retrieval, particularly for:

```text
low lexical overlap
long-gap recurrence
sparse prior evidence
associative retrieval
```

but the frozen production canonicaliser could not use the additional evidence.

The key CR-016 result was:

```text
better retrieval
    ≠
better identity decisions
```

because the current canonicalisation candidate/gating architecture was already saturated for the cases it could act on.

Therefore CR-018 introduces a **new evidence consumer** rather than weakening CR-008 safety gates.

---

# 1. Research questions

## RQ1 — Boundary precision

> Can an explicit, boundary-focused verifier filter a high-recall overlap-family candidate pool so that recall gains are preserved while exact-span precision and distinct-surface precision recover to production-safe levels?

## RQ2 — Nested boundary discrimination

> Can the verifier distinguish:
>
> - a valid outer technical term;
> - a valid inner nested technical term;
> - both independently valid;
> - over-long descriptive wrappers;
> - under-long partial terms;
> - invalid nested substrings?

## RQ3 — Memory-aware identity linking

> Given an already accepted current concept, can retrieved prior textbook evidence improve SAME-vs-NEW-vs-RELATED identity decisions without increasing false merges?

## RQ4 — HippoRAG-specific benefit

> Does HippoRAG evidence improve identity linking beyond:
>
> 1. the frozen production canonicalisation system, and
> 2. ordinary dense prior-passage retrieval
>
> when all arms use the same identity consumer?

## RQ5 — Combined pipeline

> If both components work independently, do they remain beneficial when combined in one causal section-by-section pipeline?

---

# 2. Scientific lineage

```text
CR-008
strict SAME / DIFFERENT identity semantics
        ↓
CR-009
current production concept extraction + canonicalisation
        ↓
CR-014
high-recall multi-proposer concept candidate pool
        ↓
CR-015
nested-aware family selection;
NO_ELIGIBLE_DEVELOPMENT_ARM
        ↓
CR-016
HippoRAG retrieval feasibility;
DEVELOPMENT_ONLY_FEASIBILITY
        ↓
CR-017
simplified evaluation framework
        ↓
CR-018
explicit boundary verification
+
evidence-aware identity linking
```

CR-018 must not rewrite the conclusions of CR-014–016.

Historical outputs remain immutable.

---

# 3. Why CR-018 contains two tracks

The two changes occur at different semantic levels.

```text
TRACK A
candidate span
→ is this the correct boundary?

TRACK B
accepted concept
→ is this the same concept as something already known?
```

These must not be conflated.

A boundary error is not an identity error.

A repeated concept identity error is not a boundary error.

The experimental design must preserve separate attribution.

---

# 4. Target architecture

The proposed final architecture, **only if both tracks pass independently**, is:

```text
CURRENT TEXTBOOK SECTION
        ↓
FROZEN HIGH-RECALL PROPOSAL UNION
        ↓
OVERLAP / NESTED FAMILIES
        ↓
HIGH-RECALL FAMILY SELECTOR
        ↓
EXPLICIT BOUNDARY VERIFIER
        ↓
BOUNDARY-VALID SPANS
        ↓
CONCEPTHOOD VERIFIER
        ↓
NESTED-AWARE MENTION PLACEMENT
        ↓
DETERMINISTIC CR-008 IDENTITY RULES
        ↓
UNRESOLVED ACCEPTED CONCEPT
        ↓
PRIOR-EVIDENCE RETRIEVAL
    ┌──────────────┴──────────────┐
    ↓                             ↓
DENSE MEMORY                 HIPPORAG MEMORY
    └──────────────┬──────────────┘
                   ↓
        EVIDENCE-AWARE IDENTITY VERIFIER
                   ↓
    SAME_EXISTING / NEW_CONCEPT /
    RELATED_NOT_SAME / DIFFERENT /
    INSUFFICIENT_EVIDENCE
                   ↓
          CR-008 SAFETY GUARDS
                   ↓
             CANONICAL NODE
                   ↓
          FROZEN RELATION PIPELINE
                   ↓
            FREEZE SECTION
                   ↓
      INDEX RAW SECTION INTO MEMORY
```

HippoRAG is **not** the Expert KG and never becomes identity authority.

---

# 5. Literature review — boundary precision / candidate filtering

CR-018's boundary track should be implemented using the following principles from the literature.

The target task is **technical concept / terminology extraction**, not conventional NER, so these papers provide design guidance rather than a claim that CUMAP is solving the same benchmark.

## 5.1 DiFiNet — compare neighbouring spans and explicitly filter boundary noise

Cai et al., ACL 2024, **DiFiNet: Boundary-Aware Semantic Differentiation and Filtration Network for Nested Named Entity Recognition**.

Source:
https://aclanthology.org/2024.acl-long.349/

Relevant finding:

- exhaustive span methods produce many neighbouring candidate spans;
- small boundary differences are difficult to discriminate;
- explicit semantic differentiation between nearby spans is useful;
- a dedicated boundary filtration component is used to suppress non-entity noise.

### CR-018 translation

Do **not** verify candidate spans independently with no knowledge of their overlap family.

For a selected span, expose nearby family alternatives:

```text
routing
routing protocol
interdomain routing protocol
the interdomain routing protocol
```

The boundary verifier must reason comparatively:

```text
which spans are complete boundaries?
can multiple spans independently survive?
which are wrappers / fragments?
```

This is the primary design principle.

---

## 5.2 Locate and Label — proposal first, boundary filtering/refinement before semantic labelling

Shen et al., ACL 2021, **Locate and Label: A Two-stage Identifier for Nested Named Entity Recognition**.

Source:
https://aclanthology.org/2021.acl-long.216/

The paper separates:

```text
span proposal / filtering / boundary adjustment
        ↓
semantic label prediction
```

rather than treating boundary discovery and type classification as one decision.

### CR-018 translation

CUMAP should keep:

```text
BOUNDARY VALIDATION
```

separate from:

```text
CONCEPTHOOD
```

The boundary verifier must not answer:

```text
"is this an important technical concept?"
```

It answers only whether the **exact selected surface is a valid complete boundary**.

The later concepthood verifier decides whether a correctly bounded phrase deserves entry as a technical concept.

---

## 5.3 Boundary Smoothing — boundary labels are ambiguous and confidence can be overconfident

Zhu & Li, ACL 2022, **Boundary Smoothing for Named Entity Recognition**.

Source:
https://aclanthology.org/2022.acl-long.490/

Relevant finding:

- boundary annotation is genuinely ambiguous;
- span models can become overconfident;
- improving calibration around neighbouring spans improves robustness.

### CR-018 translation

Do not force every ambiguous overlap family into a confident binary decision.

The boundary verifier must support:

```text
UNCERTAIN
```

and CR-018 must measure uncertainty / review coverage.

Do not interpret raw LLM self-reported confidence as calibrated probability unless calibration is demonstrated on development data.

---

## 5.4 BOPN — make boundary error explicit rather than treating every near miss as unrelated negative

Tang et al., Findings of EMNLP 2023, **A Boundary Offset Prediction Network for Named Entity Recognition**.

Source:
https://aclanthology.org/2023.findings-emnlp.989/

Relevant idea:

Candidate spans near the correct span contain useful boundary information. Treating all of them simply as unrelated negatives wastes structure.

### CR-018 translation

Boundary errors must be classified explicitly:

```text
OVERLONG
UNDERLONG
INVALID_NESTED
VALID_NESTED
EXACT
```

Do not collapse all of:

```text
"routing protocol"
"the routing protocol"
"protocol"
```

into a generic `REJECT`.

The error label itself is useful for analysis and hard-negative retrieval.

---

## 5.5 BANER — boundary-aware contrastive learning / near-boundary contrasts

Guo et al., COLING 2025, **BANER: Boundary-Aware LLMs for Few-Shot Named Entity Recognition**.

Source:
https://aclanthology.org/2025.coling-main.691/

Relevant finding:

The work explicitly targets over-detected and under-detected spans and uses boundary-aware contrastive learning to make LLM representations sensitive to span boundaries.

### CR-018 translation

Few-shot demonstrations should be **contrastive**, not isolated:

```text
VALID:
congestion control algorithm

INVALID OVERLONG:
operation of the congestion control algorithm

VALID NESTED:
congestion control

INVALID UNDERLONG:
algorithm
```

The verifier should see why one member of a family survives and another does not.

---

## 5.6 Negative sampling — use hard/ambiguous negatives carefully

Li et al., ACL 2022, **Rethinking Negative Sampling for Handling Missing Entity Annotations**.

Source:
https://aclanthology.org/2022.acl-long.497/

Relevant finding:

Negative sampling is useful, but false negatives / missampling matter. Informative uncertain negatives are valuable only when they are not actually missing positives.

### CR-018 translation

Use high-value boundary hard negatives such as:

```text
±1 token expansion
±2 token expansion
truncated head
truncated modifier
sibling span in same overlap family
descriptive wrapper around gold-like term
```

But **never automatically label an inner span negative because a longer span is valid**.

Hard negatives derived from model-generated development gold must remain development diagnostics unless human-reviewed.

---

## 5.7 Selective prediction — abstention is preferable to low-confidence forced decisions

Xin et al., ACL-IJCNLP 2021, **The Art of Abstention: Selective Prediction and Error Regularization for Natural Language Processing**.

Source:
https://aclanthology.org/2021.acl-long.84/

Relevant finding:

Selective prediction allows low-confidence examples to be withheld rather than forcing a potentially wrong decision.

### CR-018 translation

Support:

```text
UNCERTAIN_BOUNDARY
```

and optionally route only uncertain families to a second verifier / review.

Do not automatically run an expensive consensus arm on all candidates.

---

## 5.8 Technical term extraction — ranking/filtering is a natural stage

Fusco et al., EMNLP Industry 2022, **Unsupervised Term Extraction for Highly Technical Domains**.

Source:
https://aclanthology.org/2022.emnlp-industry.1/

Hazem et al., CompuTerm 2020, **TermEval 2020: TALN-LS2N System for Automatic Term Extraction**.

Source:
https://aclanthology.org/2020.computerm-1.13/

These works reinforce that technical term extraction commonly separates:

```text
candidate acquisition
→ scoring / filtering
→ final terms
```

and uses lexical, morphological, context and technicality evidence.

### CR-018 translation

The high-recall U2/A2-style pool should be treated as a **candidate universe**, not final output.

Precision recovery belongs in a dedicated filtering layer.

---

## 5.9 Exact-boundary evaluation itself has ambiguity

Rigouts Terryn, LREC 2026, **Large Language Models Are Good Term Extractors: A Systematic Evaluation**.

Source:
https://aclanthology.org/2026.lrec-1.605/

The study reports that some apparent automatic-term-extraction errors are defensible boundary judgements and that annotation/evaluation methodology can misrepresent model capability.

### CR-018 translation

Before tuning the new boundary validator, CR-018 requires a small blind **human boundary-convention audit** on exposed development examples.

Do not tune a verifier to model-generated inner-vs-outer conventions without first checking whether those conventions are defensible.

---

# 6. Boundary-verifier design principles

The primary implementation should follow these rules.

## 6.1 Input is family-aware

A verifier call receives:

```text
source sentence
limited local paragraph context
section heading

target selected span
all overlapping family spans

proposal provenance
span offsets
token length

optional development-only contrastive demonstrations
```

Do not expose:

```text
gold label
gold span
held-out annotation
arm outcome
previous scorer verdict
```

The verifier should not be told which span the historical system preferred.

---

## 6.2 Output is boundary-only

Required structured outputs:

```text
VALID_EXACT
VALID_NESTED
REJECT_OVERLONG
REJECT_UNDERLONG
REJECT_INVALID_NESTED
REJECT_DESCRIPTIVE_WRAPPER
UNCERTAIN
```

Optional machine-readable fields:

```text
selected_span_id
boundary_relation_to_family
evidence_locator
decision_code
```

Do not require free-form hidden reasoning.

A short rationale may be stored only if useful for audit; it is not needed for scoring.

---

## 6.3 Zero / one / multiple spans may survive

A family may produce:

```text
0 valid spans
1 valid span
multiple independently valid nested spans
```

The verifier must not impose longest-match.

Example:

```text
TCP congestion control
congestion control
```

may both survive if both are independently valid technical terms in context.

---

## 6.4 Hard-negative bank

Build only from **exposed development material**.

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

Store:

```text
source span
transformation
family ID
source section
human/model provenance
final validation status
```

Never create hard negatives from fresh held-out gold.

Do not treat generated variants as known negatives unless their status is validated.

---

## 6.5 Contrastive demonstrations

Prefer demonstrations containing family contrasts.

Example format:

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

Retrieve demonstrations using:

```text
family shape
token length
syntactic head
boundary error type
local phrase pattern
technical domain context
```

Do not retrieve from fresh held-out annotations.

---

## 6.6 Selective uncertainty

The primary verifier may output:

```text
UNCERTAIN
```

Options for uncertain spans:

```text
REJECT for auto-adoption evaluation
OR
route to selective second verifier
```

Do not silently treat uncertainty as acceptance.

A second-verifier/adjudication arm is optional and only justified after the single-verifier result is known.

---

## 6.7 Threshold / ranker rule

A local ranker may be explored only as an optional efficiency/triage layer.

It may use:

```text
span length
POS / noun phrase features
left/right boundary tokens
heading occurrence
definition cue
recurrence
multi-proposer agreement
A2 selector confidence / provenance
local embeddings
family position
```

Hard rule:

> No ranker threshold may silently create a new recall ceiling.

Always report candidate recall:

```text
before ranker
after ranker
after boundary verifier
after concepthood verifier
```

---

# 7. Boundary convention audit — required before tuning

Before paid boundary-verifier tuning, prepare a blind human sheet using exposed CR-014/015 development material.

Recommended sample:

```text
120 overlap families
```

stratified approximately across:

```text
30 over-long cases
30 under-long / partial cases
30 invalid-nested cases
30 nested-valid / ambiguous cases
```

The human reviewer sees:

```text
source sentence
limited paragraph context
candidate family spans
annotation guideline
```

The human reviewer must NOT see:

```text
gold
system arm
FP/FN category
model decision
historical score
```

Questions per span:

```text
1. Is this an exact complete term boundary in this context?
2. If nested inside another valid term, is it independently meaningful?
3. Boundary label:
   VALID_EXACT
   VALID_NESTED
   OVERLONG
   UNDERLONG
   INVALID_NESTED
   DESCRIPTIVE_WRAPPER
   UNCERTAIN
```

Provenance:

```text
owner/human completion
→ HUMAN_PRIMARY for this audit

model-filled sheet
→ invalid for the purpose of this audit
```

Implementation prepares the blind sheet and scorer.

**Implementation must not fill the human sheet.**

If disagreement between human review and model-generated development gold is systematic, STOP and return to Research before training/tuning against that gold.

---

# 8. Track A — explicit boundary verification experiment

## 8.1 Frozen substrate

STOP 1 must reconcile exact runnable artifacts for:

```text
CR-014 U2 high-recall proposal union
CR-015 A2 family selector
CR-015 B2 concepthood verifier
nested-aware placement
current U0 production baseline
```

Primary boundary experiment starts from the high-recall A2-selected span set.

The A2 selector remains a **high-recall first pass**.

The new explicit verifier is a second precision-oriented pass.

---

## 8.2 Arms

### BA0 — production baseline

```text
current CR-009 production concept stage
```

Purpose:

```text
production precision / recall reference
```

### BA1 — frozen CR-015 A2 reference

```text
U2 proposals
→ overlap families
→ frozen A2 family selector
→ nested placement
```

Purpose:

```text
high-recall reference
```

No new calls if saved artifacts exist.

### BA2 — explicit boundary verification

```text
frozen A2 selected spans
→ NEW boundary verifier
→ frozen CR-015 B2 concepthood verifier
→ nested placement
```

Purpose:

> Test whether explicit boundary filtration makes the previously over-permissive concepthood verifier viable.

### BA3 — contrastive boundary verification

```text
BA2
+
retrieved boundary-family contrastive demonstrations
+
validated development hard negatives
```

Purpose:

> Test literature-inspired family contrast / hard-negative precision recovery.

### BA4 — selective uncertainty / second verifier

Optional only if BA2/BA3 are close to eligibility but still miss precision.

```text
BA3
→ UNCERTAIN only
→ independent second boundary verifier / adjudication
```

Do not run automatically.

---

# 9. Track A metrics

Primary concept metrics:

```text
span-exact micro precision
span-exact micro recall
span-exact micro F1
distinct-surface precision / recall / F1
```

Boundary-specific metrics:

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

Stage waterfall:

```text
proposed
→ A2 selected
→ boundary accepted
→ concepthood accepted
→ placed
→ canonicalised
```

Report all losses separately.

---

# 10. Track A development eligibility

STOP 1 must reconcile exact baseline values before using numerical gates.

Unless Research changes them after reconciliation, inherit the core CR-015 safety philosophy:

```text
exact F1:
    >= U0 + 0.02
    OR paired section-bootstrap 95% lower bound for ΔF1 > 0

exact precision:
    >= U0 - 0.02

exact recall:
    >= U0 + 0.05

distinct-surface precision:
    >= U0 - 0.05

distinct-surface recall:
    >= U0 + 0.05
    OR no material regression from the high-recall reference

over-long FP rate:
    >= 25% lower than frozen CR-014 V3

CR-008 violations:
    0

gold leakage:
    0
```

Also report nested recall explicitly.

Do not change gates after inspecting development outcomes without a documented Research amendment.

---

# 11. Track B — HippoRAG evidence-aware identity linking

CR-016 established that HippoRAG retrieval can outperform dense retrieval, but injecting more candidates into the old canonicaliser changes no decisions.

CR-018 therefore creates a new **identity evidence consumer**.

---

# 12. Identity-linking architecture

Only concepts already accepted by the concept/boundary stage may enter Track B.

Flow:

```text
ACCEPTED CURRENT CONCEPT
        ↓
DETERMINISTIC CR-008 / CR-009 RULES
exact / normalized key / acronym / curated SAME-DIFFERENT
        ↓
if unresolved
        ↓
construct current-only retrieval query
        ↓
retrieve PRIOR source evidence
        ↓
map prior passages to historical canonical nodes
        ↓
EVIDENCE-AWARE IDENTITY VERIFIER
        ↓
SAME_EXISTING
NEW_CONCEPT
RELATED_NOT_SAME
DIFFERENT
INSUFFICIENT_EVIDENCE
        ↓
CR-008 DIFFERENT HARD VETO
        ↓
canonicalisation action / review
```

HippoRAG retrieval scores never become identity decisions.

---

# 13. Identity verifier input

For each current concept / historical candidate pair, provide:

```text
CURRENT
- exact current span
- source sentence
- limited paragraph
- section heading
- proposed/current type where available

HISTORICAL CANDIDATE
- canonical node name
- aliases
- node type
- first accepted evidence
- selected prior evidence

RETRIEVED MEMORY EVIDENCE
- top-k bounded prior passages
- source sections
- source locators
- retrieval backend
- retrieval rank / score

SAFETY
- CR-008 lexicon decision if any
- explicit DIFFERENT flags
```

Do not expose:

```text
gold identity
future section evidence
test labels
historical human answer
```

---

# 14. Identity verifier output

Strict schema:

```text
SAME_EXISTING
NEW_CONCEPT
RELATED_NOT_SAME
DIFFERENT
INSUFFICIENT_EVIDENCE
```

If `SAME_EXISTING`:

```text
target_node_id
current_evidence_locator
prior_evidence_locator
```

No free-form chain-of-thought.

---

# 15. Initial mutation policy

During development:

```text
memory-supported SAME_EXISTING
    → prediction / review record
    → DO NOT mutate authoritative production graph
```

Only after precision gates are met may Research approve automatic identity mutation.

CR-008 `DIFFERENT` always overrides a verifier SAME prediction.

---

# 16. Track B arms

To separate **new consumer quality** from **retrieval quality**, run all necessary baselines.

### ID0 — frozen current canonicalisation

```text
production CR-008/009 identity logic
```

### ID1 — new identity verifier, no cross-section retrieval

Use:

```text
current context
+
existing frozen canonical node information available without RAG
```

Purpose:

> Measure whether the new verifier itself improves identity decisions.

### ID2 — dense evidence

```text
same identity verifier
+
dense prior-passage retrieval
```

### ID3 — HippoRAG evidence

```text
same identity verifier
+
HippoRAG prior-passage retrieval
```

Critical rule:

```text
ID2 and ID3 must use the same:
identity prompt
model
top_k
evidence packet size
decision schema
canonical node mapping
```

Only retrieval backend differs.

---

# 17. HippoRAG invariants inherited from CR-016

Reuse the CR-016 isolated environment and exact pinned implementation unless STOP 1 finds a reproducibility problem.

Preserve:

```text
causal source order
future-section retrieval = impossible
raw prior paragraphs first
same source corpus for dense and HippoRAG
same embedding backbone where architecture permits
project client adapter / logging
retrieval provenance
independent arm indexes
```

HippoRAG's internal OpenIE graph remains retrieval-only.

---

# 18. Memory indexing rule

When processing section `S_n`:

```text
memory before S_n
=
raw text from S_1 ... S_(n-1)
```

After final section output is frozen:

```text
freeze section
→ index raw paragraphs
→ continue
```

Do not index current/future text before current decisions.

No full-book pre-indexing during causal evaluation.

---

# 19. Track B metrics

Primary identity metrics:

```text
existing-node link precision
existing-node link recall
existing-node link F1
```

Safety / error metrics:

```text
false-new-node rate
false-link rate
false-merge rate
RELATED_NOT_SAME accuracy
DIFFERENT accuracy
INSUFFICIENT rate
CR-008 DIFFERENT violations
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

System metrics:

```text
retrieval latency
identity-verifier calls
cost
memory size
provenance completeness
```

Always report raw support counts for thin slices.

---

# 20. Track B development eligibility

Primary safety priority is **identity precision**.

For auto-link eligibility:

```text
SAME_EXISTING precision >= 0.98
```

and, where sample size is sufficient:

```text
Wilson lower bound >= 0.95
```

If the lower-bound criterion is not statistically supportable due to sample size:

```text
automatic linking remains disabled
```

and the system may only qualify as a review/ranking aid.

Additional gates:

```text
CR-008 DIFFERENT violations = 0

false-link rate:
    no > 0.01 absolute regression vs ID0

NEW concept false-link / suppression:
    no material regression

provenance completeness:
    1.00
```

Benefit gate versus ID0:

```text
existing-node link F1 >= ID0 + 0.05
OR
false-new-node rate reduced by >= 25%
```

HippoRAG-specific gate versus dense ID2:

```text
existing-node link F1 >= ID2 + 0.03
OR
low-overlap / long-gap identity recall >= ID2 + 0.05
```

with:

```text
precision delta vs ID2 >= -0.01
CR-008 violations = 0
```

If dense retrieval performs equivalently, prefer dense.

---

# 21. Track separation and combined experiment

Do not combine tracks until both have completed their own development decision.

Possible outcomes:

```text
Track A passes, Track B fails
    → boundary-only candidate

Track A fails, Track B passes
    → identity-only candidate using production concept extractor

both pass
    → combined candidate may be tested

both fail
    → no CR-018 production candidate
```

---

# 22. Combined 2×2 development ablation

If both tracks pass, run:

| Arm | Boundary | Identity |
|---|---|---|
| C0 | production | production |
| C1 | selected CR-018 boundary | production |
| C2 | production | selected CR-018 identity |
| C3 | selected CR-018 boundary | selected CR-018 identity |

This is required to test whether the gains remain additive or interact negatively.

Do not skip C1/C2 and report only C0 vs C3.

---

# 23. CR-017 headline metrics

If CR-017 is implemented by the time CR-018 reaches end-to-end evaluation, report the five headline metrics:

```text
Concept F1
Ancestor Hierarchy F1
Pair Recall
Relation Macro F1
Strict E2E Edge F1
```

However:

```text
Track A primary target = Concept F1 / concept precision-recall
Track B primary target = identity diagnostics
```

Do not expect HippoRAG identity linking alone to improve raw span extraction.

If hierarchy/relation gold is unavailable for a split:

```text
NOT_EVALUABLE
```

Do not synthesize gold.

---

# 24. Fresh-data policy

At STOP 1 re-run contamination audit across CR-001–017.

Current known untouched candidates must be verified rather than assumed.

Previously preserved candidates include:

```text
4.3
5.1
5.2
6.2
6.5
8.1
9.1
9.4
```

Do not use these for prompt design, hard negatives, example retrieval or development error analysis before the split is frozen.

**No fresh section is consumed until at least one CR-018 track passes its development gates.**

---

# 25. Fresh gold requirements

Final concept evaluation requires human-reviewed concept/boundary gold.

Preferred provenance:

```text
HUMAN_REVIEWED_MODEL_DRAFT
```

Workflow:

```text
model draft
→ owner reviews every annotation
→ corrections permitted
→ freeze
→ hash
→ prediction code blocked from gold
```

For identity evaluation, fresh gold must also specify where applicable:

```text
current concept ID
PREVIOUSLY_SEEN vs NEW
correct historical canonical node
alias/acronym recurrence
same-surface-different-sense
prior supporting occurrence
```

A model-only annotation remains:

```text
MODEL_GENERATED_DIAGNOSTIC
```

and cannot support a human-validated production claim.

---

# 26. Causal fresh evaluation

If an identity/memory arm is tested fresh, run the book causally.

Do not evaluate target sections with an empty node registry.

For each experimental arm:

```text
start from clean frozen state
process sections in source order
maintain independent node registry
maintain independent memory index
score only designated held-out sections
freeze section before indexing it
```

Intervening sections may be unscored runtime context.

All arms must process the same source sequence.

---

# 27. Error taxonomy additions

Reuse historical codes and add only clear CR-018-specific categories.

## Boundary

```text
BV0 correct span rejected by boundary verifier
BV1 over-long span accepted
BV2 under-long span accepted
BV3 invalid nested span accepted
BV4 valid nested span rejected
BV5 descriptive wrapper accepted
BV6 uncertain span forced incorrectly
```

## Identity / memory

```text
ID0 historical node not retrieved
ID1 correct historical node retrieved but verifier says NEW
ID2 wrong historical node linked
ID3 RELATED_NOT_SAME collapsed to SAME
ID4 SAME incorrectly left as NEW
ID5 CR-008 DIFFERENT attempted
ID6 retrieval evidence from wrong sense dominated decision
ID7 memory provenance incomplete
```

Earliest-failure attribution remains mandatory.

---

# 28. Trace requirements

Add / reuse stages:

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

Every model-influenced decision must retain:

```text
model_id
prompt_version
config_hash
input refs
output refs
source locators
decision code
```

No chain-of-thought field.

---

# 29. Required visualisations

Generate only from real result artifacts.

## Boundary

1. precision / recall / F1 by BA arm;
2. error waterfall;
3. over-long / under-long / invalid-nested FP counts;
4. nested-valid recall;
5. boundary confusion matrix;
6. candidate volume → final volume.

## Identity

7. link precision / recall / F1 by ID arm;
8. false-new-node and false-link rates;
9. dense vs HippoRAG identity benefit by recurrence slice;
10. identity gain vs section distance;
11. memory retrieval success → identity-use waterfall.

## Combined

12. C0–C3 comparison where allowed.

---

# 30. STOP sequence

## STOP 1 — repository reconciliation + implementation feasibility

**No paid calls.**

Implementation must report:

### Boundary track

```text
exact frozen U2 proposal definition
exact frozen A2 selector artifact/code path
exact frozen B2 concepthood verifier
nested-placement path
candidate family volumes
available saved outputs
current scorer
human boundary audit tooling
```

### Identity track

```text
current canonicalisation pipeline
CR-008 rule order
current node registry / evidence storage
how prior passages map to accepted canonical nodes
CR-016 HippoRAG pinned environment
dense baseline
memory adapter
causal index implementation
identity benchmark feasibility
```

### Data

```text
all exposed sections
all untouched sections
source order
available human/model gold provenance
identity-gold coverage
```

### Cost

Produce a paid-call preflight for:

```text
boundary BA2/BA3
optional BA4
identity ID1/ID2/ID3
combined C0-C3
fresh sequential evaluation
```

**Do not make paid calls until Research approves the STOP-1 preflight.**

Return:

```text
reports/cr018/STOP1_RECONCILIATION.md
```

---

## STOP 2 — boundary convention audit

No boundary prompt tuning yet.

Implementation:

1. creates the blind 120-family audit sheet;
2. freezes audit instructions;
3. gives it to the human owner;
4. does not fill it;
5. after owner completion, compares human vs development benchmark;
6. reports disagreement by boundary type.

Return:

```text
reports/cr018/boundary_convention_audit.md
```

STOP and return to Research if annotation convention disagreement is material/systematic.

---

## STOP 3 — Track A explicit boundary verification

Run:

```text
BA0
BA1
BA2
BA3
```

BA4 only with Research approval / if justified.

Use exposed development material only.

Report all Track A metrics and bootstrap comparisons.

Freeze one boundary candidate only if eligible.

If none eligible:

```text
BOUNDARY_TRACK_NOT_ELIGIBLE
```

and continue to Track B independently.

---

## STOP 4 — Track B identity-consumer ablation

Use accepted concepts from exposed material and causal prior-source state.

Run:

```text
ID0
ID1
ID2
ID3
```

Do not mutate production graph.

Report:

```text
identity P/R/F1
false-new-node
false-link
false-merge
DIFFERENT violations
recurrence slices
cost / latency
```

Freeze one identity candidate only if eligible.

If none:

```text
IDENTITY_TRACK_NOT_ELIGIBLE
```

---

## STOP 5 — combined 2×2 development ablation

Only if both tracks have eligible candidates.

Run:

```text
C0
C1
C2
C3
```

If only one track passed, skip the 2×2 and carry that track alone to prospective evaluation.

Return to Research before fresh evaluation.

---

## STOP 6 — fresh held-out sequential evaluation

Preconditions:

```text
selected architecture frozen
fresh section IDs frozen
gold provenance frozen
gold hashes frozen
prompt/model/config hashes frozen
boundary rules frozen
identity rules frozen
memory config frozen
query template frozen
top_k frozen
source order frozen
prediction code blocked from gold
```

Run production baseline and eligible CR-018 candidate(s) exactly once.

No tuning or quality retries after held-out outputs are inspected.

---

## STOP 7 — downstream compatibility + final decision

Only after a candidate passes fresh concept/identity gates.

Measure:

```text
canonical node count
duplicate-node reduction
false-merge indicators
pair-candidate growth
pair-budget saturation
relation count
trace completeness
CR-008 safety
memory/index state requirements
cost
rollback/rebuild plan
```

If CR-017 end-to-end relation/hierarchy gold is evaluable, produce the five headline metrics.

Do not begin the final full-textbook production rebuild until Research approves migration.

---

# 31. Minimum test contract

## Boundary verifier

- target span offsets are exact;
- family alternatives are visible;
- verifier cannot invent text;
- multiple nested spans can survive;
- longest-match cannot suppress a boundary-approved nested span;
- over-long / under-long labels are deterministic in fixture;
- `UNCERTAIN` is not silently accepted;
- held-out examples cannot enter demo retrieval;
- hard-negative provenance is preserved.

## Boundary/concepthood separation

- boundary rejection cannot masquerade as `REJECT_NOT_CONCEPT`;
- concepthood verifier sees only boundary-approved spans;
- concepthood verifier cannot expand/shrink spans;
- every rejection is attributed to earliest stage.

## Identity consumer

- unresolved concept can still become NEW with no memory evidence;
- retrieved passage does not imply SAME;
- CR-008 DIFFERENT always vetoes SAME;
- RELATED_NOT_SAME does not merge;
- same-surface-different-sense fixture remains separate;
- identity verifier cannot link to a node absent from candidate/evidence packet;
- identity prediction can be evaluated without mutating production.

## Causal memory

- section n cannot retrieve section n or later;
- each experimental arm has independent index state;
- current section indexed only after output freeze;
- future retrieval hard-fails;
- index provenance complete.

## Dense / HippoRAG parity

- same source chunks;
- same current query;
- same top_k where feasible;
- same identity prompt/model;
- only retrieval backend differs between ID2/ID3.

## Reproducibility

- exact code commit;
- model IDs;
- prompt hashes;
- configs;
- source-order hash;
- HippoRAG commit/environment identity;
- random seeds where applicable.

---

# 32. Repository artifacts

Expected semantics; reconcile exact paths to repository convention.

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
    cr018_boundary_adjudicator_v1.md       # optional

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

---

# 33. Possible final statuses

CR-018 may end as:

```text
COMBINED_ELIGIBLE_FOR_MIGRATION

BOUNDARY_ONLY_ELIGIBLE_FOR_MIGRATION

IDENTITY_ONLY_ELIGIBLE_FOR_MIGRATION

BOUNDARY_REVIEW_ONLY
    boundary verifier useful only for review / no safe auto-filter threshold

IDENTITY_REVIEW_ONLY
    memory-aware identity system useful only for review / ranking

NO_ELIGIBLE_CR018_ARM

STOPPED_BOUNDARY_GOLD_AMBIGUOUS

STOPPED_NO_FRESH_HELDOUT
```

A negative result is acceptable.

---

# 34. Non-goals

CR-018 must not:

- modify the proposal union while evaluating boundary precision;
- relax CR-008 DIFFERENT;
- lower identity similarity thresholds merely to force memory usage;
- treat HippoRAG retrieval score as SAME probability;
- use HippoRAG OpenIE triples as Expert-KG semantic edges;
- index future sections;
- use fresh held-out gold for hard negatives/demonstrations;
- merge nodes automatically before identity precision is validated;
- change relation ontology or relation classifier as part of the primary experiment;
- alter historical CR-014/015/016 results;
- combine the two tracks before independent evidence exists.

---

# 35. Interpretation rules

If boundary verification improves precision:

```text
say:
explicit family-aware boundary filtration improved the candidate pool

do not say:
the model understands concepts better
```

If HippoRAG improves identity linking:

```text
say:
retrieved prior evidence improved identity/linking decisions

do not say:
HippoRAG improved the Expert KG
```

until end-to-end graph evaluation supports that claim.

If dense retrieval matches HippoRAG:

```text
prefer dense
```

unless HippoRAG has a clearly justified difficult-slice benefit with no safety regression.

Do not describe model-generated benchmark agreement as human accuracy.

---

# 36. Immediate instruction to Implementation

Start **CR-018 STOP 1 only**.

Do not make paid model calls.

The two most important questions to answer are:

## Boundary

> Can the frozen CR-015 high-recall A2 span output be passed through a new independent family-aware boundary validator **without changing proposal generation**, and can the result then pass unchanged into the frozen concepthood verifier?

## Identity

> Can an accepted current concept and retrieved prior evidence be presented to a new identity verifier **without weakening CR-008 authority**, while keeping dense and HippoRAG retrieval as interchangeable backends?

Return:

```text
reports/cr018/STOP1_RECONCILIATION.md
```

with:

```text
exact code/artifact paths
hashes
data exposure state
human audit plan
candidate volumes
identity-case volumes
integration points
test plan
cost preflight
technical blockers
```

Then STOP and return to Research.

---

# 37. Research expectation

The primary CR-018 hypothesis is:

> **Precision recovery is most likely to come from explicit family-aware boundary filtration that compares near-overlapping spans before concepthood verification, rather than from another generic concept judge.**

The secondary hypothesis is:

> **HippoRAG is most useful when its retrieved passages are consumed as evidence by an explicit identity verifier for difficult cross-section recurrence, rather than injected as extra candidates into the frozen canonicaliser.**

Both must be tested independently.
