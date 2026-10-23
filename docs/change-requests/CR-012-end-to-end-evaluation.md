# CR-012 — End-to-End Expert Knowledge Graph Evaluation and Error Attribution

**Status:** IMPLEMENTATION PACKAGE DRAFT. CR-012 production baseline is **not yet frozen**. CR-010 must first have a final architecture decision, then CR-011 must complete through STOP 5 and emit `CR012_EVAL_HANDOFF.json`.

**Scope:** Evaluation only. CR-012 measures the complete frozen Expert-KG workflow from raw technical text to the final canonical typed graph and attributes error to the earliest causal pipeline stage.

**Research authority:** the 2026-10-08 Research handover. Research owns benchmarks, sampling, gold policy, headline metric, oracle definitions, error-attribution semantics, confidence-interval units, stability protocol, held-out execution rules, benchmark-adapter restrictions and cost caps. Implementation may resolve repository/file/CLI/schema details only where experiment semantics do not change.

## 1. Objective

Headline question:

> Given raw technical text, how close is the final CUM knowledge graph to an independently annotated gold knowledge graph?

Evaluate whatever architecture was actually selected after CR-010 and CR-011. Do not reconstruct an idealised pipeline from old CR documents.

Scientific sequence:

```text
CR-009  concept extraction / Generator → Verifier → Pruner
  ↓
CR-010  node recall + relation architecture + pair recall
  ↓
CR-011  global graph consolidation / reorganisation
  ↓
CR-012  end-to-end evaluation of the frozen workflow
```

CR-011 changes the graph. CR-012 asks whether the resulting graph is correct.

## 2. Evaluation-only contract

CR-012 must not silently improve the system after held-out results are inspected.

Allowed before/while validating evaluation infrastructure:

- fix a scorer implementation bug where expected behaviour is already specified;
- correct an external dataset loader;
- log missing metadata;
- fix a deterministic implementation defect without changing methodology.

Not allowed after held-out results are inspected:

- prompt tuning;
- threshold changes;
- relation-registry edits;
- term-lexicon edits;
- cue additions;
- merge-guard changes;
- model reselection;
- benchmark-specific algorithm changes.

Any improvement proposal discovered from held-out errors goes into `CR012_FAILURE_ANALYSIS.md` and may become CR-013 or later.

## 3. Frozen research questions

**RQ1 — End-to-end accuracy.** How accurately does the complete CUM pipeline reconstruct a gold knowledge graph from raw technical text?

**RQ2 — Error attribution.** How much final error is introduced by concept extraction, canonicalisation, candidate-pair generation, relation classification and graph consolidation?

**RQ3 — Generalisation.** Does the workflow generalise beyond Peterson & Davie networking text to independently annotated technical/scientific documents?

**RQ4 — CR-011 contribution.** Does CR-011 consolidation improve, preserve or damage the final graph when the same pre-sleep extraction is evaluated before and after consolidation?

## 4. Benchmark strategy

Two primary tracks are required.

### 4.1 Primary external benchmark — SciNLP

Role:

```text
raw technical full text
→ concept/entity extraction
→ typed relations
→ strict end-to-end evaluation
```

SciNLP is the main external generalisation benchmark.

At STOP 1, audit the exact repository/release instead of assuming paper counts. Record source, version/commit, document/entity/relation counts, split, relation and type inventories, licence, file hashes and official scorer version. If paper and repository counts differ, report both and evaluate against the exact frozen repository version used.

### 4.2 Primary in-domain benchmark — P&D-E2E

Create a new exhaustive held-out gold set from Peterson & Davie raw text.

Role:

```text
raw networking textbook text
→ complete frozen CUM workflow
→ final graph
→ exhaustive networking gold comparison
```

Pilot: exactly 2 already-developed sections, used only to debug annotation/scoring and estimate effort. Pilot data cannot contribute to final held-out scores.

Held-out: approximately 6–8 sections from chapters not used for CR-005–011 tuning where feasible. Freeze section selection **before viewing final CUM predictions**. Selection may stratify by chapter, length, subsection structure or technical density, never observed model success/failure.

### 4.3 Secondary diagnostics

Use if practical, but do not block CR-012 completion:

- SciERC — canonicalisation/coreference diagnostic;
- SciER — full-text robustness/OOD diagnostic;
- OSKGC or Text2KGBench — ontology/schema-conformance diagnostic.

Minimum valid CR-012 = SciNLP + P&D-E2E.

## 5. Benchmark adapter contract

Do not force external data into the networking ontology. Implement an adapter abstraction equivalent to:

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

SciNLP receives its own frozen schema; P&D-E2E receives the CUM registry. The **workflow architecture remains the same**.

Allowed benchmark-specific differences: loader, schema/config, label names, official-score conversion, required input formatting.

Forbidden: benchmark-specific extraction algorithm, test-tuned prompt, special pair strategy for test examples, or manual translation into networking labels.

## 6. Benchmark isolation

CR-012 held-out data must not have influenced CR-011 development. Seal from CR-011 feature/rule/threshold/arm/prompt/lexicon decisions if used as held-out:

- SciNLP test;
- SciERC evaluation;
- SciER evaluation;
- OSKGC/Text2KGBench test;
- P&D-E2E held-out.

At STOP 1/2 record the manifests and hashes used to enforce isolation.

## 7. P&D-E2E annotation schema

For every selected held-out section, exhaustively annotate:

### Concepts

- exact surface span;
- canonical concept ID;
- canonical name;
- aliases / mention group;
- node type;
- evidence location.

### Relations

- source canonical concept;
- target canonical concept;
- relation;
- direction;
- required qualifier(s);
- supporting evidence span.

### Canonicalisation

- mentions/names belonging to the same concept;
- explicit `NOT_SAME` where needed for ambiguous/confusable cases.

Do not enumerate every possible `NO_RELATION` pair. Negative pairs may be sampled separately for diagnostics.

Human gold is authoritative. LLMs may prefill/suggest/highlight/triage but cannot be the sole ground truth. Code never writes automatically to `data/gold`.

If possible, independently double-annotate approximately 25–30% of concepts and 25–30% of relations. Report concept, relation, direction and identity SAME/NOT_SAME agreement. If a second human is unavailable, report the limitation; an LLM is not a second human.

## 8. Headline metric — `STRICT_E2E_EDGE_F1`

A predicted directional edge is correct only when all required components are correct:

```text
correct source canonical concept
AND correct target canonical concept
AND correct endpoint types where required
AND correct semantic relation
AND correct direction
```

For symmetric relations, endpoint orientation is ignored.

```text
P_E2E = correct final predicted edges / all final predicted edges
R_E2E = correct final predicted edges / all gold edges
F1_E2E = 2 * P_E2E * R_E2E / (P_E2E + R_E2E)
```

This is the main CR-012 result. Do not replace it with a weighted composite of component scores.

## 9. Secondary whole-graph diagnostics

Report:

**Node / concept:** exact concept P/R/F1, concept type accuracy, canonical-node P/R/F1 where defined.

**Identity:** pairwise identity P/R/F1, B³ cluster P/R/F1 where suitable gold clusters exist.

**Pair selection:** pair recall among gold edges whose endpoint nodes exist.

**Relation:** relation P/R/F1 conditional on correct gold endpoints, direction accuracy, per-relation confusion.

**Grounding:** unsupported node rate, unsupported edge rate.

**Ontology / validation:** type-constraint violation rate, invalid relation/domain-range rate.

**Provenance:** provenance completeness, resolvable evidence rate.

**System:** API spend, runtime, cost per correct final edge.

These diagnose the headline score; they do not replace it.

## 10. Earliest-failure taxonomy

Assign each end-to-end gold miss, where possible, exactly one **primary earliest causal failure**:

| Code | Meaning |
|---|---|
| N0 | concept not extracted |
| N1 | concept extracted with wrong/incomplete span |
| C0 | canonicalisation split: one real concept became multiple nodes |
| C1 | canonicalisation false merge: different concepts became one node |
| P0 | both nodes exist but pair never proposed |
| R0 | pair proposed but classifier chose NO_RELATION |
| R1 | wrong relation |
| R2 | wrong relation direction |
| R3 | qualifier/type failure |
| S0 | correct pre-sleep structure damaged by CR-011 |
| S1 | CR-011 failed to repair a duplicate/split it was expected to repair |
| E0 | evidence/provenance invalid |

Do not double count downstream consequences of an earlier failure.

## 11. Frozen oracle matrix

Freeze oracle implementation before held-out evaluation.

### E0 — full workflow

```text
raw text → frozen production pipeline → CR-011 → final graph
```

Headline system.

### E1 — oracle concepts

Inject gold concept mentions/types only, then run normal canonicalisation, pair selection, relation classification and consolidation. Approximate loss due to concept extraction = `E1 - E0`.

### E2 — oracle canonicalisation

Inject gold concept mentions plus gold canonical identity clusters, then run pair selection, relations and downstream processing. Approximate canonicalisation contribution = `E2 - E1`. Use only where benchmark gold supports it; P&D-E2E should.

### E3 — oracle pair coverage

Provide gold nodes/canonicalisation and force all gold endpoint pairs to reach relation classification. **Do not expose the gold relation label.** Approximate pair-selection loss = `E3 - E2`.

### E4 — relation-classification ceiling

Provide correct endpoint pairs; classifier independently predicts relation, direction and required qualifiers.

### Oracle leakage rule

Oracle information is injected only into the stage it replaces. Test concepts may not become few-shot examples. E3 exposes endpoint identity, never the gold relation. Add explicit leakage tests.

## 12. CR-011 pre/post comparison

Use the exact immutable handoff from CR-011 STOP 5. For each eligible P&D-E2E section:

```text
same frozen extraction
      ├── PRE-SLEEP graph → score
      └── CR-011 → POST-SLEEP graph → score
```

Do not rerun extraction to manufacture either graph.

Report:

```text
DeltaF1_sleep = F1_post - F1_pre
```

Also report true duplicate merges, false merges, duplicate identities repaired, correct split warnings, valid nodes/relations damaged, relations preserved through re-key, provenance retained, and node/edge count changes.

This does not replace SLEEP-240.

## 13. Stability experiment

Before held-out results are viewed, freeze a small subset:

- 2 SciNLP documents;
- 2 P&D-E2E sections.

Run E0 **three independent times** under the same frozen configuration. Retain all runs; never select the best.

Report mean and standard deviation of `STRICT_E2E_EDGE_F1`, node-set Jaccard, edge-set Jaccard, canonicalisation disagreement rate and relation disagreement rate.

For edges:

```text
J(E_i, E_j) = |E_i ∩ E_j| / |E_i ∪ E_j|
```

## 14. Confidence intervals

Use the natural grouping unit:

- SciNLP: bootstrap by document;
- P&D-E2E: bootstrap by section;
- pre/post sleep: paired bootstrap by the same section.

Do not bootstrap individual edges as independent observations. Report 95% intervals.

## 15. Unsupported-fact evaluation

```text
UnsupportedNodeRate = predicted canonical nodes without adequate source support / all predicted canonical nodes
UnsupportedEdgeRate = predicted edges without adequate source support / all predicted edges
```

For P&D-E2E use human gold/evidence spans. Plausible but unsupported facts are errors; graph density is not rewarded.

## 16. Provenance evaluation

For final predicted graph objects validate all required provenance. For edges this includes source document, section, supporting evidence, `run_id`, relation-registry version, model/prompt/config provenance, source/target canonical lineage, and CR-011 merge/re-key lineage if applicable.

```text
ProvenanceCompleteness = objects with all required provenance / all evaluated graph objects
```

Target = `1.00`. This is a structural quality requirement, not the headline accuracy score.

## 17. External baseline policy

Where an external benchmark has published systems, report them separately as:

```text
Published benchmark baseline
CUM result
```

Do not imply a strict leaderboard comparison unless dataset version, split, evaluation script and scoring definition have all been verified identical. STOP 1 must check those conditions.

## 18. STOP sequence

### STOP 1 — repository + benchmark reconciliation — $0

Report:

- final CR-010 architecture;
- final CR-011 state/tag/config;
- production concept, relation, canonicalisation and sleep configs;
- availability/integrity of CR-011 `CR012_EVAL_HANDOFF.json`;
- exact SciNLP source/version/commit, actual counts, split, schema inventories, official scorer, licence and hashes;
- optional benchmark versions if enabled;
- expected documents, calls, tokens and spend.

No paid evaluation. Return to Research if benchmark facts materially contradict the specification.

### STOP 2 — evaluation infrastructure + P&D gold freeze

Implement benchmark adapters, SciNLP and P&D-E2E adapters, official-compatible scoring, oracle injection, pre/post-sleep comparison, failure attribution, clustered bootstrap and stability runner.

Freeze 2 P&D pilot sections and 6–8 held-out sections before final predictions are viewed. Generate blind annotation sheets/codebook. Humans complete gold. No held-out pipeline evaluation yet.

### STOP 3 — scorer validation + development rehearsal

Use only SciNLP train/dev and P&D-E2E pilot. Validate span/type/alias/cluster/relation/direction/symmetry/qualifier scoring, pair denominator, oracle isolation, failure attribution, pre/post identity, bootstrap and cost estimation. Freeze evaluation code/config afterwards.

### STOP 4 — held-out end-to-end evaluation

Run held-out **once** under the freeze. Required: E0, E1, E2 where supported, E3 and E4 on SciNLP test and P&D-E2E held-out. Do not tune from results.

Report strict E2E edge P/R/F1, node, identity, pair, conditional relation, unsupported-fact, provenance, oracle decomposition, 95% CIs and cost.

### STOP 5 — CR-011 contribution + stability + final analysis

Score pre/post sleep on identical extraction outputs. Run frozen stability repetitions. Produce error waterfall, failure taxonomy, sleep delta, stability, external-vs-domain comparison, cost analysis and limitations.

CR-012 ends with analysis only. It never automatically modifies production architecture.

## 19. Cost contract

Initial planning limits:

| Stage | Planning limit |
|---|---:|
| STOP 1 | $0 |
| evaluation infrastructure/local scoring | $0 |
| pilot API work | soft target ≤ $5 |
| held-out runs | soft target ≤ $15 |
| stability repetitions | soft target ≤ $8 |
| warning threshold | $20 |
| hard cap | $30 |

STOP 1 must replace planning estimates with repository-specific preflight numbers. No paid call before preflight.

## 20. Required visualisations

Create only from real frozen results:

1. end-to-end F1 — SciNLP vs P&D;
2. oracle waterfall — E0 → E1 → E2 → E3 → E4;
3. earliest-failure distribution;
4. pre-sleep vs post-sleep P/R/F1;
5. run-to-run stability — F1 + edge Jaccard;
6. cost vs correct final edges.

Do not fabricate data.

## 21. Required artifacts

```text
docs/change-requests/CR-012-end-to-end-evaluation.md
PROMPT-CR-012.md
configs/cr012_e2e_eval.yaml
docs/annotation/pd_e2e_codebook.md
data/interim/checks/cr012/pd_e2e_pilot_blind.csv
data/interim/checks/cr012/pd_e2e_test_blind.csv
reports/cr012/STOP1_BENCHMARK_AUDIT.md
reports/cr012/dataset_manifest.json
reports/cr012/scorer_validation.md
reports/cr012/external_e2e.md
reports/cr012/pd_e2e.md
reports/cr012/oracle_error_attribution.md
reports/cr012/sleep_before_after.md
reports/cr012/stability.md
reports/cr012/unsupported_facts.md
reports/cr012/provenance.md
reports/cr012/cost.md
reports/cr012/FINAL_EVALUATION.md
reports/cr012/CR012_FAILURE_ANALYSIS.md
tests/fixtures/cr012/
```

Actual source module names must follow the repository package layout rather than create a parallel architecture unnecessarily.

## 22. Minimum test contract

Required tests cover:

**Dataset / split isolation:** dataset version/hash recorded; test never appears in development; held-out labels never enter prompts.

**Concept scoring:** exact span passes; partial span fails strict score; wrong type fails strict typed score.

**Canonicalisation:** aliases resolve to same canonical node; known-different concepts cannot match through aliasing; false merge scores as identity error.

**Relations:** correct endpoints+relation pass; wrong relation fails; reversed directional fails; reversed symmetric passes; missing endpoint is node failure, not pair failure.

**Pair recall:** denominator includes only gold edges whose endpoint nodes exist; E3 endpoint oracle does not expose relation labels.

**Oracles:** E1 only concepts; E2 only identity on top of concepts; E3 endpoints not relation; E4 gold relation hidden until scoring.

**CR-011 comparison:** pre/post uses exact same extraction; no rerun substitution; ID mapping respected.

**Provenance:** evidence locators resolve; lineage survives re-key; completeness scored.

**Stability:** repeats stored separately; no best-run selection; bootstrap deterministic under fixed seed.

**Gold safety:** external tests read-only; pipeline code cannot write `data/gold`.

## 23. Final report contract

`FINAL_EVALUATION.md` must answer five questions separately:

1. **How accurate is the whole system?** `STRICT_E2E_EDGE_F1`.
2. **Does it generalise?** external SciNLP vs in-domain P&D-E2E.
3. **Where is accuracy lost?** E0–E4 + earliest-failure attribution.
4. **Did CR-011 help?** same-extraction pre/post comparison.
5. **Is the workflow operationally trustworthy?** unsupported facts, provenance, stability, cost and limitations.

Do not collapse these into one composite score.

## 24. Definition of done

CR-012 completes only when raw text can traverse the frozen production workflow; final graph is compared against independent gold; strict edges require correct concepts+relation+direction; SciNLP is evaluated via a frozen adapter; P&D-E2E has exhaustive held-out gold; component metrics remain diagnostic; E0–E4 isolate error sources; CR-011 is compared on the same extraction; stability, unsupported facts and provenance are measured; benchmark versions/hashes are frozen; held-out labels never improved the pipeline; and no post-test method change was introduced.

Any proposed change to benchmarks, P&D sampling, gold policy, headline metric, oracle definitions, pair denominator, failure semantics, CI grouping, stability protocol, held-out rules, adapter restrictions, isolation or cost cap is **RESEARCH DECISION REQUIRED**.
