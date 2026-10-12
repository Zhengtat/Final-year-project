# CR-013 — Glass-Box Process Explainability for Expert-KG Construction

**Status:** requested by Research, 2026-10-12. This is the implementation CR for approval and handoff to Claude Code.  
**Branch:** `cr-013-process-explainability`, created from the final CR-012 state. Merge only after STOP 5 sign-off; tag `cr-013-complete`.  
**Scope:** explainability and observability only. Extend the existing offline Knowledge Graph Explorer so accepted, rejected, merged, unlinked, and missing graph objects can be traced through observable pipeline stages back to retained source evidence.  
**Primary surface:** existing `reports/kg_explorer/` experience.  
**Primary production dataset:** Peterson & Davie, *Computer Networks: A Systems Approach*, 6e.  

**Depends on:**
- CR-012 completed and frozen;
- the current P&D Expert KG explorer and SciNLP evaluation explorer;
- retained production/evaluation artifacts needed for trace reconstruction.

**Does not change:**
- prediction architecture;
- prompts or models;
- thresholds;
- pair budgets;
- relation definitions;
- canonicalisation policy;
- held-out CR-012 predictions or scores.

---

## 1. Why

The current explorer already shows the final graph and some evidence, but it does not consistently expose the full construction path that produced each object.

CR-013 should make the pipeline inspectable at the level of:

- source spans;
- concept candidates;
- accepted/rejected concepts;
- canonicalisation events;
- pair generation;
- pair ranking and budget selection;
- relation classification;
- validation;
- final graph commits;
- missing or unlinked objects.

The core product promise is:

> For any node, edge, merge, rejection, unlinked concept, or missing connection, a user should be able to ask **“How did we get here?”** and walk backwards from the final graph to the original retained evidence.

CR-013 has three research questions:

| RQ | Question |
|---|---|
| **RQ1 — Traceability** | Can every final Expert-KG node and edge be traced through observable pipeline events to source evidence? |
| **RQ2 — Faithful explanation** | Can accepted, rejected and absent graph objects be explained using recorded data, rules, rankings, model outputs and evidence without inventing post-hoc reasoning? |
| **RQ3 — Failure localisation** | In evaluation mode, can the explorer identify the earliest observable stage at which a desired graph object was lost? |

---

## 2. Order of work and stop points

Commit per step with the prefix `CR-013:`.

1. **⛔ STOP 1 — Trace audit, $0.**
   - Inspect the actual repository state after CR-012.
   - Inspect the current explorer code and the inputs used to build it.
   - Audit `slice3_c2` and one retained SciNLP evaluation run.
   - Search the underlying run artifacts, not only `index.html`.
   - For every pipeline stage, report whether the retained artifacts contain:
     - input;
     - decision;
     - alternatives;
     - reason;
     - output;
     - evidence;
     - rank/budget where applicable;
     - provenance.
   - Produce:
     - `reports/cr013/trace_coverage.md`;
     - exact artifact paths;
     - a list of `NOT_RECORDED` / unavailable fields;
     - a repository-specific implementation plan.
   - **No UI implementation yet.**
   - **No paid calls.**
   - Return to Research before proceeding.

2. **Build the trace model.**
   - Implement the derived trace/event schema.
   - Implement lineage traversal.
   - Implement deterministic explanation rendering.
   - Implement trace-gap reporting.
   - Implement the core `Why not?` localiser.
   - Add fixture tests and read-only integrity checks.

   **⛔ STOP 2 — Trace model.**
   Return:
   - trace schema;
   - sample node lineage;
   - sample edge lineage;
   - sample pair lineage;
   - trace coverage percentage;
   - deterministic-render tests;
   - source hash-integrity proof.

3. **Extend the P&D explorer.**
   - Add Pipeline.
   - Add Section Walkthrough.
   - Add Node Journey.
   - Add Edge Journey.
   - Add Why Not?.
   - Add Rejected / Lost Items.
   - Add Stage Snapshots.
   - Extend Debug/Audit tables.

   **⛔ STOP 3 — P&D explorer.**
   Return:
   - offline HTML;
   - screenshots;
   - three worked walkthroughs;
   - usability face-check sheet.

4. **Add the evaluation overlay.**
   - Keep it strictly separated from production mode.
   - Add frozen gold comparison.
   - Add earliest-failure explanation.
   - Add aggregate failure map linked to examples.

   **⛔ STOP 4 — Evaluation overlay.**
   Return:
   - evaluation-mode screenshots;
   - gold-isolation tests;
   - failure-localisation fixture results.

5. **Finalise.**
   - Produce final report and trace manifest.
   - Run tests/lint.
   - Run accessibility/responsive checks.
   - Produce supervisor/examiner demonstration script.

   **⛔ STOP 5 — Final sign-off.**
   Return:
   - `reports/cr013/FINAL_EXPLAINABILITY.md`;
   - completion report;
   - final trace manifest;
   - tests/lint output;
   - final explorer build;
   - final commit/tag proposal.

At any STOP, if a requested explanation would require changing the prediction method, rerunning held-out evaluation, inferring an unrecorded decision, or generating a new model rationale, stop and return:

```text
Problem
→ why the approved design cannot be implemented
→ alternatives
→ methodological consequences
→ RESEARCH DECISION REQUIRED
```

---

## 3. Preserve and extend the current explorer

Do not build a second disconnected viewer.

Keep the existing:

- P&D Expert KG / SciNLP Evaluation Graph switch;
- Review / Debug modes;
- interactive graph;
- search and filters;
- chapter/document selectors;
- layouts and colouring;
- right-hand node/edge detail panel;
- guided views;
- SciNLP source-text comparison;
- debug tables;
- explicit unavailable-data behaviour;
- offline operation;
- responsive / dark-mode / reduced-motion behaviour.

CR-013 should extend the current visual language and interaction model.

The final graph remains the normal graph view. Intermediate candidates and trace layers are opt-in.

---

## 4. Explainability pipeline

Expose the construction process as an observable sequence:

```text
SOURCE TEXT
    ↓
CONCEPT GENERATOR
    ↓
VERIFIER / CORRECTIVE ITERATION
    ↓
PRUNER
    ↓
CANONICALISATION / ALIASING
    ↓
PAIR GENERATION
    ↓
PAIR RANKING + BUDGET SELECTION
    ↓
RELATION CLASSIFICATION + DIRECTION + QUALIFIERS
    ↓
VALIDATION / GROUNDING / TYPE CHECKS
    ↓
FINAL SEMANTIC KG
    ↓
ORGANISATION / KNOWLEDGE SPHERE (READ-ONLY)
```

For every stage, the UI must answer:

1. **What does this stage do?**  
   A plain-language description of the method.

2. **What happened here?**  
   Section/object-specific counts, transformations and decisions.

3. **Why does it matter?**  
   What downstream stages depend on this stage and what failure occurs if an object is lost here.

---

## 5. Unified trace model

Do not make the UI reverse-engineer explanations directly from the final graph.

First normalise retained artifacts into a common, derived trace representation.

### 5.1 TraceEvent

Implement a schema equivalent to:

```yaml
TraceEvent:
  event_id: str
  run_id: str
  dataset_mode: pd | scinlp | other
  document_id: str
  section_id: str | null

  stage: source | generator | verifier | correction | pruner |
         canonicalisation | pair_generation | pair_selection |
         relation_classification | validation | graph_commit |
         organisation

  object_type: span | mention | concept | pair | edge | organisation_record
  object_id: str

  input_refs: [str]
  output_refs: [str]

  action: str
  outcome: accepted | corrected | rejected | merged | blocked |
           selected | not_selected | no_relation | emitted | not_recorded

  reason_code: str | null
  rule_id: str | null

  evidence_refs: [str]

  score: float | null
  threshold: float | null
  rank: int | null
  eligible_count: int | null
  budget: int | null

  model_id: str | null
  prompt_version: str | null
  config_hash: str | null
  registry_version: str | null

  authority: RULE | MODEL | SCORE | HUMAN | STRUCTURAL | UNKNOWN

  source_artifact: str
  source_locator: str | null
```

### 5.2 Trace rules

- Backfill traces only from data that actually exists.
- Do not infer an unrecorded decision.
- Every event must point to its source artifact.
- Every event should include a locator where available.
- Missing values remain null or explicitly unavailable.
- Preserve original object IDs.
- Derived trace IDs may be added, but production IDs must not be silently re-keyed.
- Lineage must support a DAG, not only a linear list.
- Multiple mentions may contribute to one final concept.
- Multiple evidence/validation records may contribute to one final edge.
- Add a manifest containing source run IDs, source hashes, code version and coverage statistics.

---

## 6. Trace outputs

Recommended output namespace:

```text
data/processed/explainability/<source_run_id>/<explain_id>/
    manifest.json
    trace_events.jsonl
    object_lineage.jsonl
    trace_gaps.jsonl
    explanation_index.jsonl
```

`manifest.json` should include:

```text
source_run_id
dataset_mode
source artifact paths
source artifact hashes
code version
trace schema version
renderer version
coverage statistics
known trace gaps
```

These are derived artifacts. They must not mutate the source run.

---

## 7. Deterministic explanation renderer

Normal human-readable explanation text must be rendered from structured trace fields.

Do not use another LLM to generate explanations.

Example template:

```text
{source} and {target} formed an eligible candidate pair.
The pair ranked {rank} out of {eligible_count} candidates.
The section budget selected the top {budget} pairs.
Because rank {rank} was outside that boundary, this pair was not
sent to relation classification.
```

Rules:

- A stored structured rationale may be shown as **recorded model reason**.
- If no rationale exists, say that no separate rationale was recorded.
- If a confidence/score was not recorded, show `NOT_AVAILABLE` / `NOT_RECORDED`.
- Do not invent qualitative confidence labels.
- Every factual explanation sentence must be supportable by trace fields.
- Audit mode must expose supporting trace references.
- Show an authority badge where possible:
  - `RULE`
  - `MODEL`
  - `SCORE`
  - `HUMAN`
  - `STRUCTURAL`
  - `UNKNOWN`

---

## 8. Required explorer changes

### 8.1 Pipeline tab

Add a first-class **Pipeline** tab.

Show:

- the complete stage ribbon;
- section-level funnel;
- stage inputs/outputs;
- counts;
- decisions;
- losses/rejections where available;
- stage explanation text.

Clicking a stage should update the centre panel to that stage.

### 8.2 Section Walkthrough

Add **Explain this section**.

The default walkthrough should move from source text to the local final graph.

Recommended sequence:

```text
source
→ concepts proposed
→ verification/correction
→ pruning
→ canonicalisation
→ eligible pairs
→ pair budget boundary
→ relation decision
→ validation
→ local graph
```

This should be the main supervisor/examiner demonstration path.

### 8.3 Node Journey

Extend node detail with a chronological journey.

Show where retained:

- source mentions;
- proposal;
- verification/correction;
- pruning outcome;
- canonicalisation;
- aliases;
- graph commit;
- later mentions;
- organisation/ring history.

Missing intermediate stages must be labelled as unavailable rather than reconstructed.

### 8.4 Edge Journey

Show where retained:

- endpoint lineage;
- candidate-pair creation;
- pair rank;
- eligible-pool size;
- section budget;
- selected/not-selected;
- relation alternatives;
- selected relation;
- direction;
- qualifiers;
- recorded structured reason;
- grounding;
- validation;
- final edge commit;
- provenance.

### 8.5 Why Not?

Make **Why not?** a first-class interaction.

A user may select two concepts, or an evaluation-mode missing gold edge.

The explorer should inspect stages in order and stop at the earliest observable loss.

Example:

```text
Concept A extracted?                 yes
Concept B extracted?                 yes
Canonical identities valid?          yes
Eligible pair generated?             yes
Pair rank                             67 / 187
Section budget                        42
Selected for classifier?              no

Earliest observable failure:
P0 — pair not delivered
```

Explanation:

> The pair was eligible but was outside the recorded selection boundary, so it was not sent to relation classification. The classifier therefore did not have an opportunity to decide whether a semantic relation exists.

Production mode must never claim that a missing edge **should** exist.

Evaluation mode may attach the frozen CR-012 earliest-failure label.

### 8.6 Rejected / Lost Items

Add section-scoped lists for:

- rejected concepts;
- corrected concepts;
- pruned concepts;
- blocked merges;
- pairs outside budget;
- `NO_RELATION` pairs;
- validation-rejected edges;
- objects with missing trace data.

### 8.7 Stage Snapshots

Add a stage timeline/slider for the local state after:

```text
extraction
canonicalisation
pair selection
relation classification
validation
```

Do not overload the normal graph view with all intermediate candidates.

### 8.8 Debug / Audit tables

Add trace-linked fields:

```text
trace_event_id
stage
outcome
authority
reason_code
rule_id
source_artifact
source_locator
evidence_refs
score
threshold
rank
eligible_count
budget
model_id
prompt_version
config_hash
registry_version
```

---

## 9. Stage-by-stage explanation requirements

### 9.1 Source text

Show:

- document/chapter/section;
- sentence boundaries where retained;
- source evidence;
- selected-object spans.

Clicking a node/edge should jump to its evidence where possible.

Do not expose unavailable/licence-restricted source text beyond current policy.

### 9.2 Concept generator

For a proposed mention, show:

- surface span;
- proposed type/role;
- evidence;
- new-vs-existing status if recorded;
- generator output status.

Suggested text:

> The generator proposed this phrase as a candidate concept; it was not yet a final KG node.

### 9.3 Verifier / correction

Show each actually retained verifier/correction event.

Example:

```text
proposal
→ issue detected
→ corrected proposal
→ pass
```

If intermediate rounds are not retained:

```text
NOT_RECORDED_IN_CURRENT_RUN
```

### 9.4 Pruner

Show:

- KEEP / PRUNE;
- recorded score/features/reason if available;
- the downstream consequence.

Do not retrospectively rescue a pruned concept in the explanation layer.

### 9.5 Canonicalisation

Show a before/after identity view.

Where retained, show:

- names/mentions;
- surviving node;
- aliases;
- merge source;
- blocked merge;
- evidence;
- original IDs.

Clearly distinguish identity/canonicalisation from semantic relations.

### 9.6 Pair generation

Show how candidate partners were generated, but only where that mechanism is recorded.

Also show eligible candidate count where available.

### 9.7 Pair ranking and budget

This is a priority feature.

Show:

```text
rank
eligible_count
budget
selection boundary
selected / not selected
recorded ranking feature/reason
```

If ranking features were not retained, do not recreate them.

### 9.8 Relation classification

Where retained, show:

- choice set;
- reverse-direction alternatives;
- `NO_RELATION`;
- `OTHER` if applicable;
- chosen relation;
- direction;
- qualifiers;
- structured reason;
- model/prompt/config provenance.

### 9.9 Validation / grounding

Show:

- evidence checks;
- endpoint grounding;
- domain/range/type checks;
- qualifier checks;
- rejection reason;
- whether the edge reached the graph.

### 9.10 Graph commit

Show:

- final source/target IDs;
- relation;
- evidence list;
- provenance;
- first section/chapter;
- evidence union where retained.

### 9.11 Organisation / knowledge sphere

Keep this visibly separate from semantic extraction.

Suggested explanation:

> This stage reorganises the already-created graph for structural importance or community analysis; it does not determine whether a semantic fact is true.

Show ring/community/importance history only from recorded data.

---

## 10. Audience modes

Preserve the current Review / Debug interaction, but support three conceptual depths:

| Level | Audience | Display |
|---|---|---|
| **Story** | supervisor / examiner / student | plain-language stage purpose, concise source evidence, minimal IDs |
| **Evidence** | research review | scores, ranks, budget, alternatives, authority, before/after state |
| **Audit** | developer / reproducibility | raw IDs, JSON, paths, hashes, prompt/config/registry versions, trace references |

Implementation may map:

```text
Story + Evidence → Review
Audit            → Debug
```

if this produces a cleaner UI.

---

## 11. Production vs evaluation isolation

### Production mode

Allowed inputs:

```text
source text
pipeline trace
predictions
deterministic rules
evidence
production metadata
```

Purpose:

> Explain why the system produced or did not produce an object.

Do not expose gold-only data.

### Evaluation mode

May additionally use:

```text
frozen gold
scorer outputs
frozen earliest-failure labels
```

Purpose:

> Explain why a frozen benchmark object was correct/missed and where the loss occurred.

Gold-derived UI must be:

- visually marked;
- dataset scoped;
- unreachable in the production P&D view unless the user explicitly switches to an evaluation view.

---

## 12. Explainability metrics

CR-013 must report measurable success criteria.

| Metric | Definition | Target |
|---|---|---:|
| **Final-object trace coverage** | final nodes/edges with lineage or an explicit documented trace gap | ≥95% initially; 100% for newly instrumented future runs |
| **Evidence resolvability** | evidence-backed claims whose locators resolve | 100% |
| **Explanation support rate** | factual explanation sentences supported by trace fields | 100% |
| **Stage localisation accuracy** | deterministic fixtures attributed to intended stage | 100% |
| **Unknown honesty** | unavailable fields shown as unavailable rather than guessed | 100% |
| **Replay determinism** | same trace + renderer version gives identical payload | 100% |
| **Gold isolation** | production mode cannot access/display gold-only fields | 100% |
| **Read-only integrity** | source artifact hashes unchanged by explainability build | 100% |

A small human usability face-check is descriptive only and must not be reported as model accuracy.

---

## 13. Legacy runs and future instrumentation

### 13.1 Legacy runs

For `slice3_c2` and existing CR-012 outputs:

- build the best truthful trace from retained artifacts;
- expect incomplete coverage;
- expose gaps explicitly;
- never invent missing history.

### 13.2 Future runs

Add runtime instrumentation so future outputs can emit TraceEvent-compatible records directly.

Instrumentation may add logging only.

It must not change:

- model-visible inputs;
- candidate ordering;
- thresholds;
- randomness;
- pair budgets;
- acceptance decisions.

Add regression tests showing predictions are unchanged with tracing enabled.

---

## 14. Required repository artifacts

Create at least:

```text
docs/change-requests/
    CR-013-process-explainability.md

PROMPT-CR-013.md

configs/
    cr013_explainability.yaml

src/cumap/explain/
    trace.py
    lineage.py
    render.py
    why_not.py
    coverage.py
    viewer_adapter.py

data/processed/explainability/<source_run_id>/<explain_id>/
    manifest.json
    trace_events.jsonl
    object_lineage.jsonl
    trace_gaps.jsonl
    explanation_index.jsonl

reports/cr013/
    trace_coverage.md
    explanation_validation.md
    failure_examples.md
    usability_face_check.csv
    FINAL_EXPLAINABILITY.md

reports/kg_explorer/
    index.html

tests/fixtures/cr013/
    ...
```

Exact module/file names may follow the repository's existing package layout. Do not create a parallel architecture unnecessarily.

---

## 15. Minimum tests

Implement at least:

- source artifact hashes identical before/after trace build;
- TraceEvent round-trip preserves IDs, stage, outcome, evidence and provenance;
- lineage traversal reaches evidence for fixture final nodes;
- lineage traversal reaches evidence for fixture final edges;
- DAG lineage handles many mentions → one concept;
- DAG lineage handles multiple evidence records → one edge;
- deterministic renderer produces stable identical output;
- missing reason/score/confidence renders `NOT_RECORDED`;
- pair rank above/below selection boundary produces correct explanation;
- blocked merge fixture remains separate and explains the recorded guard;
- relation fixture renders choice set, direction, qualifiers and validation only from stored fields;
- Why-not correctly localises `N0`, `C0`, `C1`, `P0`, `R0`, `R1`, `R2`, `R3`, `E0` where trace data exists;
- production payload excludes gold-only fields;
- evaluation overlay is opt-in and dataset scoped;
- no free-form post-hoc LLM explanation is generated;
- no private chain-of-thought is exposed;
- offline HTML has no required external network resources;
- keyboard navigation works for stage controls;
- reduced-motion support remains;
- explanation panels remain usable at narrow widths;
- existing dataset switch, Review/Debug, search/filter and graph views still work;
- tracing on/off leaves prediction output unchanged for future instrumentation fixtures.

---

## 16. Required user stories

1. **Supervisor walkthrough**  
   Open a P&D section, choose **Explain this section**, walk from source text to the local final graph.

2. **Explain a node**  
   Open a final node and inspect retained source mentions, processing stages, aliases/canonicalisation, relations and organisation history.

3. **Explain an edge**  
   Inspect evidence, endpoint lineage, candidate-pair status, rank/budget, relation classification, validation and final provenance.

4. **Explain an unlinked concept**  
   Distinguish:
   - no eligible pair;
   - pair not selected;
   - classifier `NO_RELATION`;
   - validation rejection;
   - trace unavailable.

5. **Why not between two concepts?**  
   Follow observable stage checks and stop at the earliest available loss.

6. **Evaluation failure**  
   In evaluation mode only, open a missed gold relation and show the frozen failure category plus trace evidence.

7. **Audit mode**  
   Expose trace IDs, source artifacts, raw values, hashes and configuration identifiers where retained.

8. **Missing-data honesty**  
   Any unavailable reason, score, confidence or intermediate event is labelled unavailable. No guessed rationale appears.

---

## 17. Required final demonstration flow

The final supervisor/examiner demonstration should be concise and should not begin with the global graph.

1. Open a textbook section.
2. Show the original sentence.
3. Highlight generator-proposed concepts.
4. Show one concept that passed and, if available, one that was corrected/rejected.
5. Show canonicalisation/aliases for one concept.
6. Show eligible candidate pairs for the local example.
7. Show the pair-selection budget boundary.
8. Open one selected pair.
9. Show relation choice, direction, evidence and validation.
10. Show the resulting local graph.
11. Use **Why not?** on a pair that did not become an edge.
12. Zoom out to the chapter/global P&D graph.
13. Optionally switch to SciNLP evaluation mode and clearly label it as non-production.

---

## 18. Definition of done

CR-013 is complete only when:

- the current explorer is extended rather than replaced;
- a unified derived trace representation exists;
- trace records point to exact retained source artifacts;
- final P&D nodes/edges can be traced as far back as retained data permits;
- coverage gaps are quantified;
- users can inspect why an object exists;
- users can inspect why a potential/expected object did not appear where trace data permits;
- pair rank/budget is visible where retained;
- production explanations contain no gold data;
- evaluation overlays remain isolated;
- explanation text is deterministic;
- factual explanation text is trace-supported;
- no post-hoc model reasoning is invented;
- unknown fields are shown honestly;
- original graph/evaluation artifacts remain byte-identical/read-only;
- explainability metrics and fixture tests pass;
- future trace instrumentation does not change predictions;
- CR-013 makes no claim of improved accuracy.

---

## 19. Implementation prompt boundary

The coding agent must:

- read this CR before modifying code;
- inspect the actual repository before assuming file paths;
- execute STOP 1 first;
- make no paid calls;
- make no prediction changes;
- return the STOP-1 audit before proceeding.

If the retained artifacts do not support an explanation, record a trace gap. Do not infer or generate the missing decision.

---

## 20. Items log

| # | Item | Status |
|---|---|---|
| 1 | Unified derived TraceEvent / lineage index | Requested |
| 2 | Deterministic explanation renderer | Requested |
| 3 | Pipeline tab and Section Walkthrough | Requested |
| 4 | Node Journey and Edge Journey | Requested |
| 5 | First-class Why Not? interaction | Requested |
| 6 | Rejected / Lost Items and Stage Snapshots | Requested |
| 7 | Strict production/evaluation isolation | Requested |
| 8 | Legacy trace-gap audit | Requested |
| 9 | Future-run trace instrumentation, logging only | Requested |
| 10 | Final supervisor/examiner demonstration flow | Requested |
