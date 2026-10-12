# CR-014 — Recall-First Multi-Proposer Concept Extraction

**Status:** requested by Research, 2026-10-12. This is the implementation CR for approval and handoff to Claude Code.  
**Branch:** `cr-014-recall-first-concepts`, created from the final CR-013 state. Merge only after STOP 5 sign-off; tag `cr-014-complete`.  
**Scope:** redesign the concept-candidate stage to maximise proposal recall before verification and pruning, while keeping downstream canonicalisation, relation extraction, consolidation and evaluation definitions frozen during the primary experiment.  
**Primary production dataset:** Peterson & Davie, *Computer Networks: A Systems Approach*, 6e.  
**Primary research question:** can a recall-first multi-proposer concept architecture improve exact concept recall/F1 on fresh P&D sections without unacceptable precision loss or downstream graph degradation?

**Depends on:**
- CR-012 completed and frozen;
- CR-013 completed or sufficiently stable for trace compatibility;
- the actual selected production concept pipeline discovered at STOP 1;
- current P&D source parsing and concept-evaluation infrastructure.

**Does not change in the primary experiment:**
- identity/canonicalisation semantics;
- relation inventory or relation semantics;
- pair-selection methodology;
- discourse/eRST architecture;
- graph-consolidation semantics;
- misconception semantics;
- CR-012 scoring definitions.

---

## 1. Why

The current concept pipeline appears to lose many valid concepts before downstream verification and pruning have a chance to evaluate them.

The problem is architectural:

```text
candidate absent
→ verifier never sees it
→ pruner never sees it
→ canonicalisation never sees it
→ relation extraction never sees it
→ final graph cannot recover it
```

CR-014 therefore tests a **recall-first proposal/classification architecture**:

```text
RAW TECHNICAL TEXT
        |
        +--> current production LLM generator
        +--> deterministic noun / noun-phrase candidates
        +--> textbook-structure candidates
        +--> acronym / long-form candidates
        +--> existing KG names and aliases
        +--> optional compact span proposer
        +--> independent LLM samples
        |
        v
HIGH-RECALL CANDIDATE UNION
        |
        v
OVERLAP / BOUNDARY REPAIR
        |
        v
INDEPENDENT CONCEPT VERIFIER
        |
        v
PRUNER
        |
        v
FROZEN DOWNSTREAM PIPELINE
```

The core principle is:

> False-positive candidates can be removed later. Missing candidates cannot be recovered later.

CR-014 is an incremental redesign of the concept stage only. It is not a replacement of the overall CUM architecture.

---

## 2. Research questions

CR-014 must answer:

| RQ | Question |
|---|---|
| **RQ1 — Proposal recall** | Can a multi-proposer union substantially increase the proportion of gold concepts that appear somewhere in the candidate universe? |
| **RQ2 — Precision recovery** | Once proposal recall is raised, can verification and pruning recover enough precision to improve final exact F1? |
| **RQ3 — Boundary quality** | Can overlap-aware boundary repair reduce partial-span errors and improve exact-match F1? |
| **RQ4 — One-token concepts** | Can valid one-token concepts be retained without letting unigram candidates dominate verification cost? |
| **RQ5 — Generalisation** | Does the selected concept architecture improve a fresh P&D concept set that has not been exposed during earlier CRs? |
| **RQ6 — Downstream compatibility** | Does higher concept recall avoid catastrophic downstream precision, pair-budget, or graph-quality regression? |

---

## 3. Scope

CR-014 may change:

- concept candidate generation;
- candidate-union logic;
- candidate provenance;
- deduplication before semantic verification;
- overlap-family grouping;
- boundary repair;
- one-token prioritisation/ranking;
- concept-verification prompts or models, if development ablation selects them;
- concept-stage pruner behaviour, if explicitly tested;
- concept-stage tracing needed for CR-013 compatibility.

CR-014 must not change during the primary experiment:

- canonicalisation semantics;
- relation-label inventory;
- relation-label definitions;
- pair-selection methodology;
- downstream relation architecture;
- graph-consolidation semantics;
- misconception semantics;
- CR-012 scoring definitions.

A no-production-change outcome is valid.

---

## 4. Order of work and stop points

Commit per step with the prefix `CR-014:`.

1. **⛔ STOP 1 — Repository reconciliation + contamination audit — $0**
   - Discover the actual production concept pipeline.
   - Reconcile current generator/verifier/pruner modules and selected CR-010 node outcome.
   - Reconcile current prompts, model IDs, thresholds and configs.
   - Audit whether generator rejection currently blocks later coverage checks.
   - Reconcile exposed historical datasets/splits.
   - Enumerate P&D sections already used for:
     - development;
     - owner-rule creation;
     - gold creation;
     - held-out evaluation;
     - failure analysis.
   - Enumerate candidate fresh P&D sections.
   - Reconcile CR-013 trace schema.
   - Reconcile working node statistics from the Research handover.
   - Dry-run candidate counts and cost.
   - **No paid calls.**
   - Return to Research.

2. **Stage A: proposal-universe ablation.**
   - Implement proposal sources U0–U5.
   - Evaluate proposal recall only.
   - Do not tune verifier behaviour here.

   **⛔ STOP 2 — Proposal-universe result.**
   Return:
   - exact proposal recall;
   - overlap proposal recall;
   - candidate volume;
   - incremental recall by source;
   - n-gram slices;
   - one-token slice;
   - source-overlap matrix;
   - runtime/cost;
   - proposal-gate decision.

   If the proposal gate fails, stop and return to Research before verifier redesign.

3. **Stage B: verifier / boundary / one-token ablations.**
   - Freeze selected proposal union from Stage A.
   - Run V0–V4 as applicable.

   **⛔ STOP 3 — Development selection.**
   Return:
   - exact P/R/F1;
   - conditional verifier metrics;
   - boundary metrics;
   - one-token metrics;
   - failure taxonomy;
   - paired bootstrap ΔF1;
   - cost;
   - selected candidate configuration.

   Freeze:
   - code revision;
   - prompts;
   - model IDs;
   - thresholds;
   - random/deterministic settings.

4. **Fresh held-out evaluation.**
   - Run frozen production baseline once.
   - Run frozen selected CR-014 system once.
   - Do not tune after seeing results.

   **⛔ STOP 4 — Held-out evidence.**
   Return all primary/slice/conditional/cost/provenance metrics and adoption-gate status.

5. **Downstream compatibility + migration rehearsal.**
   - Feed baseline concepts and CR-014 concepts through the same frozen downstream graph stages.
   - Measure graph changes and pair-budget pressure.
   - Verify provenance and traceability.
   - Create migration/rollback plan.
   - Do not overwrite historical runs.

   **⛔ STOP 5 — Production decision evidence.**
   Return the full frozen evidence to Research/owner.

Production migration requires explicit Research/owner approval.

---

## 5. STOP 1 reconciliation details

STOP 1 must report the actual repository state rather than assuming old CR prose still matches code.

Required reconciliation:

```text
actual CR-012 status
actual CR-013 status
active production concept pipeline
selected CR-010 node outcome
generator module(s)
verifier module(s)
pruner module(s)
active concept prompts
active model/provider IDs
active thresholds
candidate-coverage rules
coverage veto behaviour
term/alias state
current source parsing and offsets
current formatting metadata
current cache behaviour
current cost estimator
current trace schema
```

Also reconcile the working diagnostics from Research:

```text
baseline precision / recall / exact F1
N1 / N3 historical results
historical miss count
rescue candidate coverage
recovered misses
one-token candidate share
anchored-vs-independent audit findings
```

Any mismatch must be reported.

---

## 6. Data contamination audit

CR-014 must distinguish exposed data from fresh evaluation data.

Treat as **development / diagnostic only** any dataset or split whose labels or final results have already been inspected.

At minimum this includes:

- prior IIR/FACE development data;
- prior IIR/FACE test outputs already inspected;
- CR-012 held-out P&D sections once inspected;
- CR-012 failure-analysis examples;
- any section used to create prompts, owner rules, lexicon entries, or error-specific heuristics.

Create:

```text
reports/cr014/contamination_audit.md
```

The audit should include:

```text
dataset/split
section/document IDs
how it was used
when it became exposed
allowed CR-014 use
forbidden CR-014 use
```

A section cannot be called CR-014 held-out if its labels/results informed design.

---

## 7. Fresh CR-014 P&D benchmark

Create a new concept-only benchmark.

### 7.1 Pilot

Select:

```text
2 sections
```

Purpose:

- debug annotation rules;
- validate source offsets;
- validate scorer;
- validate candidate/proposal accounting;
- estimate annotation time.

Pilot sections are development data and cannot contribute to held-out results.

### 7.2 Held-out

Select approximately:

```text
6–8 sections
```

Selection must occur before running final CR-014 predictions.

Selection may stratify by:

- chapter;
- section length;
- technical density;
- one-token concept density;
- definition density;
- acronym density.

Selection must not use observed CR-014 success/failure.

### 7.3 Annotation

Use the existing P&D concept annotation semantics as the base.

Create only a delta guide where needed for:

- nested concepts;
- boundary families;
- ambiguous span selection;
- proposal-vs-final-concept distinctions.

Required gold fields:

```text
exact surface span
canonical concept label where applicable
concept type if needed
nested-valid flag
boundary notes
```

Gold must be exhaustive at section level.

If a second human annotator is available, dual-annotate a frozen subset and report agreement.

If no second human is available:

```text
IAA = NOT_EVALUABLE
```

Do not substitute an LLM as the second human.

---

## 8. Candidate representation

Every proposal must retain:

```yaml
candidate_id: str
document_id: str
section_id: str
surface: str
start_offset: int
end_offset: int
token_length: int
sentence_id: str | int | null

proposal_sources: [str]
source_specific_scores: {}
existing_node_matches: []
anchor_candidates: []

definition_pattern: str | null
heading_or_emphasis_signal: bool | str | null
frequency_features: {}
overlap_family_id: str | null
trace_ids: []
```

Rules:

- same span from multiple proposers becomes one candidate with unioned provenance;
- proposer agreement is retained as a feature;
- no proposer may erase another proposer's candidate;
- proposal provenance must remain available through final verification.

---

## 9. Independence rule

A negative or missing result from one proposer is not a global rejection.

Specifically:

```text
LLM omitted candidate      != reject
LLM rejected candidate     != reject
span model omitted         != reject
NP parser omitted          != reject
structure proposer omitted != reject
```

Final rejection occurs only in the explicit verifier/pruner stages selected during development.

Any code path where one proposer can permanently remove a candidate before independent verification must be identified and removed for the CR-014 arms.

---

## 10. Proposal sources

### 10.1 U0 — Frozen baseline

Use the actual production concept pipeline discovered at STOP 1.

Do not reconstruct a historical draft.

### 10.2 U1 — Deterministic high-recall sources

Generate local candidates from:

- noun spans;
- noun phrases;
- plausible 1–4 token spans;
- noun+noun compounds;
- adjective+noun technical phrases;
- headings/subheadings;
- emphasis/bold/italic where available;
- glossary/index terms when legitimately available;
- definitional patterns;
- acronym/long-form pairs;
- explicitly introduced protocol/mechanism/property/component names;
- recurrent technical phrases.

This arm is allowed to be noisy.

### 10.3 U2 — Deterministic + current LLM

Union:

```text
U1 + current production LLM proposals
```

### 10.4 U3 — Independent LLM multi-sample union

Add up to three independent extraction samples.

Rules:

- each sample sees the same source/codebook/schema;
- samples do not see one another;
- no repair wording;
- sampling variation is pre-registered;
- deduplicate only after all samples finish.

### 10.5 U4 — Compact span proposer

Optionally add a compact span model such as GLiNER or repository-compatible equivalent.

Requirements:

- proposer only;
- recall-oriented threshold;
- no direct final concept authority;
- runtime/licence/dependency reconciled at STOP 1.

### 10.6 U5 — Selected full union

Combine development-useful sources.

Do not assume more proposers are always better.

Stage-A ablation must measure each source's incremental gold coverage.

---

## 11. Proposal-stage evaluation

Proposal evaluation occurs **before** verifier decisions.

Define:

\[
R_{proposal}
=
\frac{\text{gold concepts represented by at least one acceptable candidate span}}
{\text{all gold concepts}}
\]

Report:

### Exact proposal recall
An exact gold span exists.

### Overlap proposal recall
At least one overlapping span exists that could plausibly be repaired.

Also report:

- candidate count per section;
- candidates per 1,000 source tokens;
- candidate/gold ratio;
- unique candidates by source;
- source-overlap matrix;
- incremental gold coverage by source;
- proposal recall for 1-, 2-, 3-, 4+ token concepts;
- previously known vs genuinely new concepts;
- definition-introduced vs ordinary mentions.

### Proposal research gate

Proceed to verifier redesign only if a development proposal arm reaches either:

```text
exact proposal recall >= 0.80
```

or:

```text
absolute proposal-recall gain >= +0.15 over U0
```

Preferred target:

```text
exact proposal recall >= 0.85
```

If no arm passes, return to Research.

Candidate volume alone is not sufficient reason to reject a high-recall proposer.

---

## 12. Overlap families and boundary repair

Do not verify every overlapping span independently.

Group nested/overlapping candidates into a family.

Example:

```text
control
congestion control
TCP congestion control
TCP congestion control algorithm
```

The boundary stage receives:

- source sentence;
- local paragraph context where needed;
- section title;
- all overlapping candidates;
- proposal-source metadata;
- concept annotation codebook;
- legitimate existing-node matches.

Output:

```text
zero, one, or multiple valid standalone concepts
```

Boundary repair must distinguish:

- valid short concept;
- partial span needing expansion;
- overlong descriptive phrase;
- genuinely nested concepts where both are valid.

Boundary quality is measured separately from proposal recall.

---

## 13. Boundary-repair output

Recommended structured output:

```yaml
overlap_family_id: str
members:
  - candidate_id: str

decisions:
  - span_start: int
    span_end: int
    surface: str
    decision: KEEP | EXPAND | SHRINK | SPLIT | REJECT
    source_candidate_ids: [str]
    evidence_refs: [str]
    reason_code: str
```

If LLM-based boundary repair is used, store model/prompt/config provenance.

Do not expose held-out gold.

---

## 14. Independent concept verifier

The verifier is the precision-recovery stage.

For each candidate or repaired family, return one of:

```text
ACCEPT_NEW
LINK_EXISTING
REJECT_NOT_CONCEPT
REJECT_GENERIC
REJECT_PARTIAL_OR_WRONG_BOUNDARY
INSUFFICIENT_EVIDENCE
```

The verifier may use:

- sentence;
- local context;
- section heading;
- concept codebook;
- candidate provenance;
- anchor evidence;
- existing-node cards;
- candidate type hypothesis.

The verifier must not see:

- gold labels;
- held-out keys;
- hidden manifests;
- test-derived concept lists;
- a previous verifier final answer in arms intended to be independent.

Proposal-source rejection is evidence, not authority.

---

## 15. One-token concepts

One-token terms remain valid.

CR-014 must not globally remove them.

Because they can dominate proposal volume, build a ranking/prioritisation score using development-only features such as:

- definition-pattern evidence;
- heading presence;
- allowed glossary/index evidence;
- acronym evidence;
- recurrence;
- technical POS/context;
- existing-node/alias match;
- anchor support;
- multi-proposer agreement;
- already-available technical-vs-general frequency signals;
- occurrence in relation-bearing technical sentences.

The ranker is a **prioritisation mechanism**, not automatically a concept classifier.

Requirements:

- report one-token proposal recall before ranking;
- report one-token proposal recall after any gate;
- report verification load reduction;
- do not create an invisible recall ceiling;
- adopted system one-token final recall may not regress by more than 0.02 absolute from baseline.

---

## 16. Anchors and consistency signals

Anchors may be used as evidence/features.

They are not:

- mandatory for acceptance;
- automatic edges;
- proof of concept validity.

Absence of an anchor must not reject a concept.

Cross-section consistency may propose additional mentions but must remain sense-aware.

Same string across chapters is not automatically the same concept.

---

## 17. Stage A experimental arms

| Arm | Proposal sources | Purpose |
|---|---|---|
| **U0** | frozen production baseline | reference |
| **U1** | deterministic high-recall sources | classical proposal coverage |
| **U2** | U1 + current LLM | hybrid proposal baseline |
| **U3** | U2 + independent LLM samples | sampling gain |
| **U4** | U2 + compact span proposer | complementary span gain |
| **U5** | U2 + useful U3/U4 sources | selected full union |

Primary Stage-A metric:

```text
proposal recall
```

Do not tune verifier behaviour during Stage A.

---

## 18. Stage B experimental arms

Use the selected proposal union from Stage A.

| Arm | Verification | Boundary | One-token handling |
|---|---|---|---|
| **V0** | current verifier/pruner | current | current |
| **V1** | independent verifier | current | current |
| **V2** | independent verifier | overlap-family repair | current |
| **V3** | V2 | V2 | evidence-based one-token prioritisation |
| **V4** | V3 + selected syntactically retrieved few-shot examples | V2 | V3 |

V4 is optional and development-only unless preflight justifies it.

---

## 19. Stage C downstream compatibility

After held-out concept evaluation is frozen, compare:

```text
baseline concepts
vs
selected CR-014 concepts
```

through the same frozen downstream graph pipeline.

Do not use downstream held-out results to retune the concept extractor.

Report:

- nodes before/after;
- edges before/after;
- false-edge growth;
- pair-budget pressure;
- relation-classifier call growth;
- provenance completeness;
- trace coverage;
- identity-guard violations;
- runtime/cost.

---

## 20. Primary metrics

### 20.1 Proposal metrics

- exact proposal recall;
- overlap proposal recall;
- candidate volume;
- candidates / 1,000 tokens;
- candidate/gold ratio;
- incremental coverage by proposer;
- source overlap;
- n-gram recall;
- known-vs-new recall;
- structural-cue recall.

### 20.2 Final concept metrics

Primary:

```text
exact micro precision
exact micro recall
exact micro F1
```

Secondary:

- lenient/overlap F1;
- macro section F1;
- semantic-similarity diagnostic at a frozen threshold if implemented;
- one-token P/R/F1;
- multi-token P/R/F1;
- concept type accuracy;
- boundary-error rate;
- false-positive categories.

### 20.3 Conditional metrics

- verifier recall given proposal hit;
- verifier precision;
- pruner false-prune rate;
- existing-mention recall;
- boundary-repair success among overlap-only hits.

### 20.4 System metrics

- API calls;
- input/output tokens;
- wall-clock runtime;
- candidate count;
- cost per correct final concept;
- stability across frozen repeats where nondeterminism remains.

---

## 21. Error taxonomy

Each gold miss should receive one earliest primary category where possible:

```text
P0  not proposed by any source
P1  only unusable/non-overlapping proposal
B0  boundary repair chose wrong span
V0  verifier rejected valid proposal
V1  verifier linked valid new concept incorrectly
R0  pruner removed valid accepted concept
C0  canonicalisation split / identity miss
C1  canonicalisation false merge
E0  evidence/source-location failure
```

Each false positive should receive one primary category:

```text
F0  generic noun / non-concept
F1  descriptive phrase, not standalone concept
F2  partial / overlong boundary
F3  duplicate alias treated as new node
F4  wrong sense / polysemy
F5  unsupported / hallucinated concept
F6  type / ontology incompatibility
```

Do not double-count downstream consequences when an earlier error explains the miss.

---

## 22. Development selection rule

All source combinations, thresholds, prompts and ranking rules are selected on development only.

An arm is eligible only if:

1. exact micro F1 improves by at least **+0.02 absolute** over baseline  
   **OR** paired section-level bootstrap 95% lower bound for ΔF1 is > 0;
2. precision drop is no worse than **−0.02 absolute**;
3. final recall improves by at least **+0.05 absolute**;
4. one-token recall regression is no worse than **−0.02 absolute**;
5. no leakage or provenance failure occurs.

If eligible arms are within 0.02 F1:

1. prefer higher recall;
2. then lower paid-call count/cost;
3. then simpler architecture.

Freeze everything before held-out evaluation.

---

## 23. Held-out adoption rule

Run exactly once:

```text
frozen production baseline
frozen selected CR-014 system
```

on the fresh held-out set.

CR-014 is eligible for production adoption only if:

| Gate | Requirement |
|---|---:|
| Exact micro F1 | development-selected rule still passes on held-out |
| Exact recall | baseline + at least 0.05 absolute |
| Precision delta | at least −0.02 absolute |
| One-token recall delta | at least −0.02 absolute |
| Gold leakage | 0 |
| Evidence/provenance completeness | 1.00 for accepted predictions |
| Identity-guard violations caused by concept stage | 0 |
| Test-time manual fixes | 0 |

If held-out evidence is ambiguous:

- freeze the result;
- return it to Research;
- do not retune and rerun the same held-out set.

---

## 24. Semantic evaluation rule

Exact match remains primary.

Lenient/semantic metrics are diagnostic only.

Do not use semantic similarity to hide proposal-stage failures.

If a gold concept is absent from every candidate source, classify it as a proposal miss even if another predicted term is semantically related.

If semantic scoring is implemented, freeze:

- embedding model;
- threshold;
- normalization rules;

on development before held-out evaluation.

---

## 25. Cost contract

STOP 1 must produce repository-specific cost estimates.

Report:

- expected candidate count per section;
- expected compact-span-model runtime;
- expected LLM verifier calls;
- expected multi-sample LLM calls;
- cache hits;
- configured model prices;
- projected cost by STOP.

Planning limits:

```text
STOP 1 reconciliation                  $0
local proposal ablations               $0 API
pilot / prompt validation              soft target <= $5
development paid ablations             soft target <= $15
fresh held-out evaluation              soft target <= $10
hard CR-014 cap before new approval    $30
```

No paid call before preflight.

Do not hard-code vendor prices in the CR.

---

## 26. Traceability

CR-014 must emit enough trace data for each candidate to follow:

```text
proposed
→ deduplicated
→ overlap-grouped
→ boundary decision
→ verified/rejected
→ pruned/kept
→ canonicalised
```

Trace must include:

- proposal source(s);
- candidate ID;
- source offsets;
- source scores;
- overlap family;
- verifier decision;
- pruner decision;
- final concept ID if kept;
- reason codes;
- evidence refs;
- model/prompt/config IDs where applicable.

Do not store or require chain-of-thought.

---

## 27. Required repository artifacts

Create at least:

```text
docs/change-requests/
    CR-014-recall-first-concept-extraction.md

PROMPT-CR-014.md

configs/
    cr014_concept_extraction.yaml

configs/fewshot/
    cr014_concept_verifier.yaml

prompts/
    cr014_concept_verifier_v1.md
    cr014_boundary_repair_v1.md

docs/annotation/
    cr014_concept_annotation_delta.md

data/interim/checks/cr014/
    pd_concept_pilot_blind.csv
    pd_concept_test_blind.csv

reports/cr014/
    STOP1_RECONCILIATION.md
    contamination_audit.md
    proposal_ablation.md
    proposal_metrics.json
    verifier_ablation.md
    boundary_analysis.md
    one_token_analysis.md
    failure_analysis.md
    cost.md
    heldout_results.md
    downstream_compatibility.md
    FINAL_DECISION_EVIDENCE.md

tests/fixtures/cr014/
    ...
```

Where useful, also persist:

```text
candidate_proposals.jsonl
candidate_source_features.parquet
overlap_families.jsonl
verification_decisions.jsonl
boundary_decisions.jsonl
trace_manifest.json
```

Paths may be adjusted to repository conventions after STOP 1.

Artifact semantics may not change.

---

## 28. Minimum tests

### Candidate generation

- deterministic NP candidate appears;
- one-token technical candidate appears;
- four-token technical phrase appears;
- definitional candidate appears;
- acronym/long-form candidate appears;
- heading candidate appears when formatting metadata exists;
- candidate omitted/rejected by one proposer survives if proposed by another;
- candidate provenance unions multiple sources without duplication.

### Boundary handling

- partial head expands to full concept when appropriate;
- short concept and compound can both survive when both are valid;
- overlong descriptive phrase is rejected;
- nested valid concepts are preserved;
- offsets map exactly to source text.

### Verifier

- valid new concept → `ACCEPT_NEW`;
- existing alias → `LINK_EXISTING`;
- generic noun → `REJECT_GENERIC`;
- partial span routes to boundary decision rather than silent loss;
- unsupported hallucinated span → reject;
- no gold/test fields enter verifier prompt.

### One-token safety

- one-token concept can pass without anchor;
- generic high-frequency noun is not automatically accepted;
- ranker cannot hide candidates from evaluation accounting;
- one-token recall metric is always produced.

### Isolation / leakage

- historical exposed splits cannot be marked held-out;
- held-out gold is inaccessible to prediction code;
- `data/gold` remains read-only;
- held-out terms cannot enter lexicon/few-shot assets.

### Frozen downstream

- relation registry unchanged during primary experiment;
- pair-selection config unchanged;
- historical evaluation snapshots unchanged.

### Traceability

- every proposal has proposer provenance;
- every final concept maps to proposal + verification trace;
- every rejected candidate has an observable rejection stage;
- no chain-of-thought field is required or stored.

---

## 29. Required visualisations

Generate only from real result files.

Required:

1. proposal recall by U0–U5;
2. incremental gold coverage by proposer;
3. candidate volume vs proposal recall;
4. exact P/R/F1 by verifier arm;
5. recall by concept length;
6. boundary waterfall:
   ```text
   not proposed
   → overlap only
   → repaired exact
   → accepted
   ```
7. one-token quality vs verification load;
8. cost vs correct final concepts;
9. held-out baseline vs CR-014 exact P/R/F1;
10. earliest-failure distribution.

Do not fabricate charts before metrics exist.

---

## 30. Research-faithfulness checks

Before issuing the implementation:

- proposal recall is measured before verifier decisions;
- no proposer can veto another;
- current LLM rejection is not an unrecoverable coverage veto;
- exhaustive candidates are proposals, not automatic concepts;
- anchors remain evidence only;
- one-token concepts are not globally removed;
- ranking cannot hide recall loss;
- exact F1 remains primary;
- semantic/lenient metrics remain diagnostic;
- fresh held-out data is truly unexposed;
- historical CR-012 results remain unchanged;
- CR-013 remains separate;
- downstream relation/consolidation behaviour stays frozen;
- no held-out-derived prompt/lexicon/few-shot rule is introduced.

Any change requires `RESEARCH DECISION REQUIRED`.

---

## 31. Implementation-consistency checks

Before coding, reconcile:

- branch/tag/commit state;
- actual package layout;
- active model/provider config;
- current trace schema;
- generator/verifier/pruner code paths;
- source parsing and offsets;
- heading/emphasis metadata availability;
- compact span model feasibility;
- cache behaviour;
- cost estimator;
- CI/test constraints.

If an approved arm cannot be implemented faithfully:

```text
Problem
→ why the approved design cannot be implemented
→ available alternatives
→ methodological consequences
→ RESEARCH DECISION REQUIRED
```

Do not silently substitute a different experiment.

---

## 32. Final decision evidence

At completion, `FINAL_DECISION_EVIDENCE.md` must answer separately:

1. Was low concept F1 mainly a proposal-recall problem?
2. Which proposal sources recovered previously unreachable concepts?
3. How much precision could be recovered after increasing candidate recall?
4. How much exact-match loss came from boundary selection rather than discovery?
5. Did one-token handling improve quality or only inflate volume?
6. Did the architecture generalise to fresh P&D sections?
7. Did increased node recall create unacceptable graph noise or pair-budget pressure?
8. Should production:
   - remain unchanged;
   - adopt CR-014;
   - continue research?

Do not collapse these into one composite score.

---

## 33. Definition of done

CR-014 is complete only when:

- CR-014 has its own immutable lineage;
- the actual production baseline is reconciled;
- exposed vs fresh data is documented;
- proposal recall is evaluated independently from final F1;
- proposal-source ablations are complete;
- no proposer has unilateral veto power;
- boundary repair is explicitly tested;
- one-token behaviour is explicitly measured;
- verifier/pruner precision recovery is measured conditionally;
- fresh held-out P&D sections are evaluated once under freeze;
- exact F1 remains the primary concept metric;
- semantic/lenient metrics are diagnostic only;
- downstream compatibility is measured without changing downstream methods;
- provenance/traceability is complete;
- costs are reported;
- no held-out tuning occurs;
- Research receives frozen evidence before any production migration.

**No automatic production migration is permitted from experiment code.**

---

## 34. Items log

| # | Item | Status |
|---|---|---|
| 1 | STOP-1 production-pipeline reconciliation | Requested |
| 2 | Contamination audit and fresh P&D split freeze | Requested |
| 3 | Multi-proposer candidate union | Requested |
| 4 | Candidate provenance schema | Requested |
| 5 | Proposal-source ablations U0–U5 | Requested |
| 6 | Overlap-family / boundary repair | Requested |
| 7 | Independent concept verifier | Requested |
| 8 | One-token ranking/prioritisation | Requested |
| 9 | Verifier/boundary ablations V0–V4 | Requested |
| 10 | Fresh held-out concept evaluation | Requested |
| 11 | Frozen downstream compatibility diagnostic | Requested |
| 12 | CR-013-compatible concept-stage tracing | Requested |
| 13 | Migration/rollback rehearsal | Requested |
| 14 | Final decision evidence report | Requested |
