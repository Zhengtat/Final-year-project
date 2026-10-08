# CR-011 — Sleep-Phase Node Consolidation and Reversible Knowledge Restructuring

**Status:** IMPLEMENTATION PACKAGE DRAFT. **STOP 1 is not passed in this chat.** The Research handover assumes CR-010 is complete, but the live repository state, active CR-010 branch/tag, final canonicalisation path, and current rollback behaviour have not been reconciled here.

**Scope:** Expert KG only; node identity, canonicalisation, consolidation, reversible restructuring, and post-consolidation replay of all available derived organisation views affected by canonical identity.

**Research authority:** the latest CR-011 Research handover supplied by the owner. Implementation may encode the approved design but must not change identity semantics, metrics, thresholds, gates, split construction, gold-label policy, experiment arms, or adoption rules.

## 1. Objective

CR-011 turns the project's existing canonicalisation machinery into an explicit **sleep / consolidation phase**: a versioned post-extraction transaction that revisits accumulated evidence across sections and chapters, decides whether provisional nodes genuinely denote the same concept, detects suspected historical over-merges, consolidates aliases/evidence/history, and produces a cleaner canonical graph **without destroying the pre-sleep graph**.

"Sleep" is a project metaphor only. It must not be presented as a biological claim.

The target pipeline is:

```text
CR-009 / CR-010 extraction
        ↓
provisional nodes + accumulated evidence
        ↓
immutable pre-sleep snapshot
        ↓
multi-signal candidate generation
        ↓
CR-008 hard SAME/DIFFERENT guards
        ↓
calibrated merge_probability
        ↓
selective LLM / human adjudication
        ↓
cluster-consistency validation
        ↓
transactional merge
        ↓
evidence-preserving re-key
        ↓
rollback round-trip verification
        ↓
canonical KG version
        ↓
organisation replay (CR-006 + CR-004 derived views if available)
```

The central research question is whether periodic accumulated-evidence consolidation can reduce duplicate/split concept identities and human review burden while maintaining very high merge precision, preserving node-extraction performance, and guaranteeing provenance-complete rollback.

## 2. Non-goals and inherited semantic contract

CR-011 **does not**:

- replace CR-008 R0–R4 with unconstrained clustering;
- equate semantic relatedness with identity;
- use graph communities/coarsening as proof of sameness;
- create new textbook facts or unsupported semantic relations;
- rescue nodes intentionally removed by the selected CR-009 generator → verifier → pruner path;
- rewrite CR-009 existing-node retrieval/backfill semantics;
- let CR-006 organisation feed back as proof of equivalence;
- allow misconception objects to participate in ordinary semantic consolidation;
- make human gold writable by pipeline code;
- treat a model's confidence statement as the merge threshold;
- evaluate the accuracy of the complete Expert-KG construction workflow. SLEEP-240 and CR-011 held-out evaluation are consolidation-stage experiments only. End-to-end raw-text → final-graph accuracy is owned by CR-012.

The CR-008 identity rule remains absolute:

> Merge only when two representations refer to the **same concept**. Broader/narrower, kind-of, instance-of, part-of, predecessor/version, process-vs-entity, field/value, confusable, related-but-distinct, or same-surface-different-sense cases remain separate.

`equivalent_to` remains a node/canonicalisation property, not a KG relation edge.

## 3. Identity probabilities remain separate

Maintain three semantically distinct quantities:

```text
concept_score
  = P(this extracted item deserves to be a concept)

merge_probability(A, B)
  = P(A and B denote the same concept)

relation_confidence(A, r, B)
  = P(the relation is supported)
```

`concept_score` may be an input feature or review-priority signal, but **may not decide identity by itself**.

If the repository still contains the provisional CR-007 `< 0.70` similarity review heuristic, do not silently preserve it as the CR-011 decision boundary. CR-011 uses development-calibrated identity thresholds.

## 4. Sleep events and triggers

A sleep event is:

> A versioned, post-extraction consolidation transaction that uses accumulated evidence from multiple sections or chapters to reconsider node identity, aliases and canonical representation without introducing new textbook facts.

### Light sleep

Runs at chapter boundaries and is mostly deterministic/local:

- R0–R3 replay;
- candidate retrieval;
- pair scoring;
- hard-veto checks;
- conflict/sense-risk detection.

### Deep sleep

May open the LLM/review path when any configured trigger fires:

- uncertain duplicate candidates;
- accumulated `same_concept` outcomes;
- repeated/recurring alias candidates;
- alias contradiction;
- type/context/sense drift;
- inconsistent identity-cluster bridge;
- final-book request;
- development-selected recurrence/new-node trigger values.

A final whole-book sleep always runs.

All trigger count thresholds marked `DEV_SELECT` are selected on development data only.

## 5. STOP 1 — repository reconciliation / $0 preflight

Before coding or paid calls, inspect the live checkout and fill `STOP1_RECONCILIATION.md`.

At minimum reconcile:

- actual CR-010 completion state, branch/tag and merge convention;
- actual canonicalisation/merge modules and call order;
- all current sleep/global-sweep/chapter/final-book triggers;
- active R0–R4 versions and exact alias config;
- R0 `same` precedence and `different` absolute veto at every merge point;
- R1 transformations actually implemented;
- R2 acronym scoping/collision handling;
- R3 strong/weak textbook alias behaviour and contradiction handling;
- R4 prompt/model/config/context;
- any active fixed similarity threshold and its use;
- any interaction where low `concept_score` currently makes merging more likely;
- type compatibility map loaded from config;
- one-token/same-surface cross-context behaviour;
- current transitive-clustering behaviour;
- existing over-merge/split detection, if any;
- alias provenance coverage;
- absorbed-node lineage/`merged_from`;
- edge re-keying/deduplication/self-loop handling;
- description-history preservation;
- evidence retention;
- current rollback mechanism and whether it actually reconstructs the pre-merge graph;
- current `same_concept` queue;
- CR-010-introduced alias/merge hooks;
- current node/alias/merge counts, including one-token and cross-chapter merges;
- current model-price table and dry-run call/token/cost estimates.

**No paid call before owner approval.**

If the actual repository requires changing method, threshold, gate, split, identity semantics, gold policy, or experiment arms, mark **RESEARCH DECISION REQUIRED** and stop.

## 6. Multi-signal candidate generation

Candidate generation should maximise recall cheaply and avoid an O(n²) LLM search.

Union and deduplicate candidates from:

| Signal | Required role |
|---|---|
| R1 normalised name equality / token overlap | candidate + deterministic rule where already approved |
| R2 acronym evidence | candidate / approved alias path |
| R3 strong/weak textbook alias cue | candidate / approved alias path |
| name embedding | retrieval only |
| definition embedding | retrieval only |
| evidence/refinement embedding | retrieval only |
| type compatibility / type consistency | feature / veto where incompatible |
| graph-neighbour overlap | secondary feature / retrieval only |
| incoming/outgoing relation signature | feature |
| first definition / description history | feature |
| cross-chapter recurrence | feature |
| explicit distinction / contradiction | negative evidence / veto where approved |
| CR-008 term lexicon | authoritative SAME/DIFFERENT |
| CR-010/eRST metadata | contextual evidence only; never identity by itself |

Every candidate source and count must be logged separately.

## 7. Hard guards

Before any ML/LLM decision:

1. `term_lexicon.different` cross-pair → **VETO**.
2. Incompatible node types → **VETO**.
3. Explicit textbook distinction meeting the approved contradiction rule → **VETO**.
4. Misconception-layer objects → exclude from ordinary consolidation.
5. Gold/evaluation labels → never become hidden runtime rules.
6. No lower-priority component may override an approved CR-008 `different`.

Approved R0 `same` remains authoritative, but the repository audit must still confirm that its current provenance and scope are safe.

## 8. Dedicated pair scorer and development-calibrated thresholds

Recommended initial scorer:

```text
logistic regression
    ↓
probability calibration
    ↓
three-way operating policy
```

Required features include lexical similarity, definition similarity, context/evidence similarity, type compatibility, alias evidence, relation-signature similarity, graph-neighbour overlap, chapter/section features, concept scores, one-token flags and negative evidence.

Also evaluate a gradient-boosted scorer as the specified development ablation; it does not become production by default.

Use historical owner merge decisions for development/training. Fresh SLEEP-240 test items are evaluation data and must not become runtime rules.

### `t_auto`

On development, choose the **smallest calibrated threshold** satisfying:

- merge precision ≥ 0.98; and
- 95% Wilson lower bound ≥ 0.95 when sample size permits.

If no threshold satisfies the safety criterion, ML auto-merge is disabled; the scorer becomes review ranking only.

### `t_review`

Choose on development to recover useful SAME cases while keeping the review queue manageable.

Policy:

```text
score >= t_auto       → eligible for automatic path, still subject to guards/cluster validation
t_review <= score < t_auto → review-band path
score < t_review      → KEEP_SEPARATE
```

Thresholds are frozen before held-out evaluation.

## 9. LLM adjudicator

The LLM is used only where the selected arm permits it, normally the review band.

It receives node names, aliases, type, definition, selected evidence excerpts and selected relation-neighbourhood context.

It **must not** see:

- merge_probability;
- scorer threshold/band;
- current model merge prediction;
- gold decision;
- held-out annotations.

Allowed decisions:

- `SAME`
- `RELATED_NOT_SAME`
- `DIFFERENT`
- `INSUFFICIENT_EVIDENCE`

A model `SAME` is a proposal until all hard guards and cluster-consistency checks pass.

The exact prompt contract lives in `prompts/sleep_merge_adjudicator_v1.md`.

## 10. One-token and polysemy guard

One-token terms are a required diagnostic stratum and special safety case.

Rules:

- embedding-only one-token auto-merge: **forbidden**;
- exact same surface across chapters: require context/sense check;
- type mismatch: veto;
- approved acronym pair: defer to R2;
- approved `different`: veto;
- distinct definitions or incompatible relation signatures: review or suspected split.

CR-011 also emits `suspected_splits.jsonl` for already-consolidated nodes whose mentions/evidence divide into incompatible sense clusters. This **does not automatically split production nodes**. It creates a human-review candidate.

## 11. Cluster-consistency guard

Naïve pairwise transitive closure is forbidden.

Before joining clusters C1 and C2:

```text
cluster_merge_allowed(C1, C2) =
    no CR-008 DIFFERENT cross-pair
    AND no type-incompatible cross-pair
    AND no explicit textbook distinction
    AND no high-confidence semantic contradiction
    AND minimum required pair support passes
```

For small clusters, inspect all material cross-pairs.

For larger clusters, at minimum inspect:

- every member ↔ proposed canonical medoid;
- every known negative/contradiction pair;
- lowest-scoring cross-pairs;
- any bridge edge whose removal disconnects the proposed equivalence cluster.

Fixture `A=B, B=C, A≠C` must prove that all three do not collapse.

## 12. Conservative, balanced and aggressive modes

| Behaviour | Conservative production | Balanced candidate | Aggressive research-only |
|---|---|---|---|
| R0 SAME | Auto | Auto | Auto |
| R0 DIFFERENT | Veto | Veto | Veto |
| R1–R3 safe rules | Auto with sense guard | Same | Same |
| ML high confidence | Auto only above safety gate | Auto | Auto |
| ML review band | Human/LLM review | LLM then guard | LLM auto |
| LLM SAME | Proposal; cluster guard required | May merge after guard | Merge after guard |
| one-token uncertain | Human | Human/LLM | LLM |
| direct broad cluster proposal | No | No | Yes |
| known contradiction | Veto | Veto | Veto |
| production eligibility | Yes | only if held-out gates pass | No by default |

`aggressive_experimental` must never overwrite the production namespace.

## 13. SLEEP-240 evaluation set

Create exactly **240 fresh blind pair judgements**:

| Stratum | N |
|---|---:|
| R1–R3 deterministic candidates | 40 |
| high semantic-similarity / R4 candidates | 40 |
| CR-008 confusables / difficult negatives | 40 |
| one-token / same-surface / possible polysemy | 40 |
| cross-chapter / long-distance candidates | 40 |
| cluster-bridge / transitive-risk pairs | 40 |
| **Total** | **240** |

Freeze:

- **Development: 80**
- **Held-out test: 160**

Split by **candidate cluster / normalised-form family**, not random pair, so variants of one identity problem cannot leak across splits.

If a second annotator is available, at least **80 held-out items** receive independent double annotation. Report Cohen's κ on binary `SAME` vs `NOT_SAME`; report `UNSURE` separately.

Historical owner labels may be used for model development/training, but fresh held-out SLEEP-240 labels remain sealed.

**Scope clarification:** SLEEP-240 asks whether CR-011 consolidated identity correctly. It is not an end-to-end Expert-KG benchmark and must remain in CR-011 rather than being moved to CR-012.

## 14. Blind annotation contract

The blind sheet must hide:

- model/rule source;
- embedding score;
- merge_probability;
- confidence band;
- LLM output;
- proposed action;
- architecture/arm.

Columns:

```text
item_id
name_a
name_b
type_a
type_b
definition_a
definition_b
evidence_a_1
evidence_a_2
evidence_b_1
evidence_b_2
decision
different_kind
preferred_canonical_form
evidence_sufficient
notes
```

Allowed `decision` values:

- `SAME`
- `NOT_SAME`
- `UNSURE`

For `NOT_SAME`, `different_kind` is one of:

- `broader_narrower`
- `kind_of`
- `instance_of`
- `part_of`
- `field_or_value`
- `predecessor_or_version`
- `process_vs_entity`
- `same_surface_different_sense`
- `confusable`
- `related_other`
- `unrelated`

`UNSURE` becomes mandatory review, not an automatic negative.

Pair order is randomised; A/B orientation is independently randomised. Disagreements are adjudicated only after both annotator sheets are frozen. Test examples may not enter prompts, rules or the lexicon until after test reporting.

## 15. Metrics

CR-011 principal outcomes are merge precision, merge recall, distinct-pair violation, cluster quality, review burden, provenance retention and rollback correctness. Whole-workflow accuracy is deferred to CR-012.


### Section-level concept non-regression

Project canonical nodes back to section-level concept predictions and report these as **safety / non-regression checks**, not as the headline measurement of the complete CUM system:

- exact micro precision / recall / F1;
- macro F1;
- existing lenient metric.

### Consolidation metrics

Merge precision:

```text
P_merge =
accepted SAME decisions that are gold SAME
/
all accepted SAME decisions
```

Merge recall:

```text
R_merge =
gold SAME pairs successfully co-clustered
/
all gold SAME pairs
```

Also report:

- `FMR_accepted = 1 - P_merge`;
- `Violation_different = gold NOT_SAME pairs ending in same canonical cluster / all gold NOT_SAME pairs`;
- pairwise cluster F1;
- B-cubed cluster precision/recall/F1 where cluster gold is available;
- one-token merge precision/recall;
- cross-chapter merge precision;
- per-origin precision for R0/R1/R2/R3/R4/ML/LLM;
- auto-merge rate;
- human-review rate;
- mean candidates/node;
- candidate recall;
- nodes before/after;
- edges before/after;
- duplicate edges collapsed;
- merge-created self-loops;
- known-different violations;
- alias-provenance completeness;
- evidence-retention rate;
- LLM calls/tokens/spend;
- annotation minutes.

## 16. Engineering reverse-recoverability

Starting from snapshot S:

1. run sleep → S′;
2. apply the generated inverse migration → S″;
3. serialise S and S″ canonically;
4. content hashes must match, excluding explicitly volatile metadata such as timestamps.

Required 100% recovery:

- node IDs;
- edge IDs or explicit edge mapping;
- aliases;
- evidence records;
- description histories;
- validation state;
- relation qualifiers;
- provenance.

`merged_from` alone is not sufficient proof.

## 17. Experiment arms

| Arm | Candidate generation | Calibrated scorer | LLM | Cluster guard | Special guards | Purpose |
|---|---|---|---|---|---|---|
| S0 | Current CR-010/CR-008 | Current | Current | Current | Current | frozen baseline |
| S1 | Multi-signal | No | Current | no new guard | CR-008 only | candidate-recall effect |
| S2 | Multi-signal | Yes | No | Yes | Standard | cheap hybrid |
| S3 | Multi-signal | Yes | Review band | Yes | Standard | main hybrid |
| S4 | Multi-signal | Yes | Review band | Yes | + one-token sense guard | short-term protection |
| S5 | Multi-signal | Yes | Review band | Yes | + temporal/section features | full balanced candidate |
| S5-OT | Same as S5 | Yes | Yes | Yes | remove one-token guard | one-token ablation |
| S5-TIME | Same as S5 | Yes | Yes | Yes | remove temporal features | temporal ablation |
| S-AGG | Direct broad candidates | Yes | LLM cluster decisions | guard retained | relaxed review threshold | aggressive research arm |

Only S0 and the development-selected candidate run once on sealed held-out test. S-AGG may run held-out only if competitive on development **and** separately approved for spend.

## 18. Development selection rule

Reject any arm that:

- merges an approved CR-008 `different` pair;
- fails evidence retention, alias provenance or rollback;
- has merge precision < 0.98;
- regresses exact micro F1 by > 0.01 absolute.

Among remaining arms, prefer highest merge recall. If recall differs by < 0.02, prefer fewer LLM calls and less human review.

Freeze configuration before held-out evaluation.

## 19. Production adoption gates

CR-011 replaces current production sleep/canonicalisation behaviour only if held-out evaluation satisfies all required safety gates:

| Gate | Requirement |
|---|---:|
| known CR-008 different pairs merged | 0 |
| merge precision | ≥ 0.98 |
| 95% Wilson lower bound for merge precision | ≥ 0.95 when evaluation N permits |
| held-out distinct-pair violation | ≤ 0.02 |
| exact micro F1 Δ | ≥ −0.01 |
| evidence retention | 1.00 |
| alias-provenance completeness | 1.00 |
| rollback round trip | 1.00 |
| one-token critical false merges on designated hard cases | 0 |
| benefit | +0.05 merge recall **or** −25% review load at comparable precision |

These are project decision gates, not literature-derived thresholds.

If safety fails, keep the current CR-010/CR-008 production path and retain CR-011 only as a review-ranking/research tool. **No change is a valid outcome.**

## 20. Required real-data visualisations

Do not fabricate charts before experiment data exists. Generate from frozen metric outputs only:

1. merge precision–recall curve;
2. distinct-pair violation vs node-reduction percentage;
3. merge recall vs human-reviewed pairs;
4. merge F1 / exact node F1 vs measured API spend;
5. one-token diagnostic grouped bars for multi-token / one-token / acronym / same-surface-different-sense slices.

Annotate actual operating points for baseline, conservative, balanced and aggressive modes where applicable.

## 20A. CR-012 benchmark isolation

CR-012 evaluation data must not influence CR-011 development. If later used as CR-012 held-out evaluation, the following are prohibited as CR-011 design/tuning inputs: SciNLP test, SciERC evaluation, SciER evaluation, OSKGC/Text2KGBench test data, and P&D-E2E held-out annotations. They may not drive features, candidate rules, thresholds, arm selection, LLM prompts, term-lexicon additions, merge guards, or manual exceptions. CR-011 may continue using historical development labels and SLEEP-240 development only.

## 21. Cost contract

Most CR-011 work should be local/deterministic.

Planning targets:

- repository audit: $0 API;
- R0–R3 replay: $0 API;
- candidate generation: $0 incremental when embeddings are cached;
- feature extraction / local models / historical replay: $0 API;
- LLM adjudicator dev: review-band only, target ≤ 250 calls;
- held-out selected system: test once, target ≤ 150 calls;
- migration/rollback: $0 API.

At STOP 1 compute current pricing from the repository price table:

```text
Cost = Σ_m N_m × (T_in,m R_in,m + T_out,m R_out,m)
```

Budget:

- soft warning: **$15**
- hard CR-011 cap before further owner approval: **$25**

No paid call until preflight reports candidate counts, predicted LLM calls, token estimates and current configured prices.

## 22. Transactional migration model

Every accepted merge becomes a `MergeTransaction` containing at minimum:

- `merge_id`, `sleep_id`;
- all source node IDs;
- survivor node ID;
- decision origin (`R0|R1|R2|R3|ML|LLM|HUMAN`);
- merge probability if applicable;
- model/prompt/config version;
- supporting evidence/section/rule IDs;
- before-state node hashes, edge IDs, alias records, description records;
- alias additions, edge re-keys, edge deduplications, self-loop rejections, node tombstones;
- explicit inverse operations;
- validation flags for lexicon guards, cluster consistency, evidence retention and rollback test.

Raw source node records are never physically destroyed. The current canonical view may expose a survivor ID, but lineage must retain all absorbed records.

Recommended namespace:

```text
data/processed/kg/<run_id>/
    snapshots/
    sleep/
        <sleep_id>/
            manifest.json
            candidate_pairs.jsonl
            pair_features.parquet
            pair_scores.jsonl
            merge_plan.jsonl
            merge_transactions.jsonl
            id_map.jsonl
            edge_rewrites.jsonl
            rejected_merges.jsonl
            suspected_splits.jsonl
            review_sheet.csv
            metrics.json
            rollback/
                inverse_patch.jsonl
                roundtrip_report.json
```

Do not mutate the original run directory.

When duplicate edges collapse after re-keying, preserve the union of all evidence references. Every pre-sleep evidence ID must map to a post-sleep edge/evidence record or an explicit rejection record. Aliases remain evidence-bearing provenance records, not plain strings.

## 23. STOP sequence

### STOP 1 — repository reconciliation / $0
Fill the reconciliation sheet and cost preflight. No paid calls.

### STOP 2 — offline candidate and scorer experiment
Build candidate generation/features; report historical candidate recall, candidates/node, feature ablations, scorer calibration, proposed `t_auto`/`t_review`, one-token slice and predicted review count. Freeze SLEEP-240 split and blind annotation sheets.

### STOP 3 — development ablations
Run S0–S5 and the specified ablations on development only. Report the full arm table, PR curve, false-merge/compression chart, API/human-effort trade-off, and selected configuration. Do not inspect held-out results for selection.

### STOP 4 — held-out evaluation
Run frozen S0 and selected candidate exactly once. Report all primary metrics, Wilson intervals, per-stratum results, agreement, exact micro F1, merge precision/recall, distinct-pair violations, one-token errors and actual spend. Research/owner decides whether production migration is permitted.

### STOP 5 — migration, rollback rehearsal and CR-012 handoff
Run migration only on a copy/new `sleep_id`. Require before/after counts, transaction list, evidence-retention report, alias-provenance audit, CR-008 lexicon violations = 0, and round-trip rollback = 100%.

After consolidation, replay **all available derived organisation views whose inputs depend on canonical node identity**. At minimum replay CR-006 sphere / centre-inner-middle-outer / structural review outputs. If CR-004 organisation is implemented at this stage, also recompute communities, node breadth, centrality-based organisation inputs, and tier/principle-support statistics that depend on canonical identity. Organisation is downstream only and must never become evidence for identity.

STOP 5 must also emit an immutable `reports/cr011_sleep/CR012_EVAL_HANDOFF.json` containing source/sleep IDs, pre/post snapshot paths and hashes, CR-009/010/011 config IDs+hashes, relation-registry and term-lexicon versions, model identifiers, prompt hashes, deterministic/random settings, merge/id/rewrite/suspected-split manifests, organisation pre/post paths, and evidence/provenance manifest. CR-012 must be able to score the same extraction before and after sleep without rerunning extraction.

Only after approval may the new version become the production canonical view.

## 24. Required tests

At minimum cover the fixtures in `tests/fixtures/sleep/fixtures.yaml`, including:

- R0 approved SAME;
- R0 approved DIFFERENT despite embedding 0.99;
- R2 unambiguous acronym;
- acronym collision across chapters;
- R3 strong alias and later contradiction;
- same spelling + incompatible type;
- one-token same spelling + different context;
- broader/narrower;
- process vs component;
- `A=B, B=C, A≠C`;
- duplicate-edge evidence union;
- merge-created self-loop logging;
- exact merge→rollback hash;
- alias provenance after rollback;
- `data/gold` write protection;
- no-key deterministic stages;
- dry-run zero paid calls;
- candidate-family split leakage prevention;
- LLM prompt contains no scorer/model answer;
- aggressive mode cannot overwrite production namespace;
- CR-012 held-out benchmark data cannot enter CR-011 development;
- CR-012 handoff references the exact same pre/post extraction and resolves all required manifests/hashes.

## 25. Required artifacts

Canonical repository artifacts:

```text
docs/change-requests/CR-011-sleep-consolidation.md
configs/sleep_consolidation_v1.yaml
configs/fewshot/sleep_merge_v1.yaml
prompts/sleep_merge_adjudicator_v1.md
docs/annotation/sleep_merge_codebook.md
PROMPT-CR-011.md
```

Implementation-generated paths:

```text
tests/fixtures/sleep/
reports/cr011_sleep/
data/interim/checks/cr011/
```

This package also provides migration, evaluation, cost and decision templates, plus the CR-012 evaluation-handoff template. Exact integration module names should follow the existing repository abstractions discovered at STOP 1 rather than duplicating them merely to match a suggested filename.

## 26. Mandatory review passes before coding-agent handoff is declared complete

### Review A — Research faithfulness

Confirm:

- strict identity is CR-008 SAME, not semantic relatedness;
- graph communities/coarsening never imply merge;
- `concept_score` cannot decide identity alone;
- fixed 0.70 is not silently retained;
- thresholds are development-selected;
- held-out split remains sealed;
- human labels remain ground truth;
- SLEEP-240, arms and gates match this CR exactly.

### Review B — Implementation consistency

Confirm:

- actual CR-010 state discovered;
- CR-008 lexicon/version preserved;
- CR-009 ordering preserved;
- existing aliases remain readable;
- migration is namespace/version safe;
- old snapshots remain immutable;
- rollback test exists;
- `data/gold` remains protected;
- every paid stage has preflight;
- CR-006 replay is downstream of identity consolidation and cannot feed back as identity evidence.

## 27. Definition of done

CR-011 is implementation-ready only when:

- STOP 1 is reconciled against the actual checkout;
- no identity-semantics conflict remains unresolved;
- all `DEV_SELECT` values remain unset until development selection;
- SLEEP-240 split construction is implemented with family/cluster grouping and leakage tests;
- every merge proposal is guardable and auditable;
- cluster consistency blocks bridge-induced false merges;
- one-token sense safety is testable;
- merge transactions are invertible;
- evidence/alias/history provenance is lossless;
- rollback canonical hash test passes;
- paid-call caps and preflight are implemented;
- both review passes have been completed;
- CR-012 evaluation benchmark gold (SciNLP test, SciERC/SciER evaluation, OSKGC/Text2KGBench test, P&D-E2E held-out) has not influenced CR-011 feature/rule/threshold/arm/prompt/lexicon decisions;
- STOP 5 emits the immutable CR-012 evaluation handoff.

Any change to identity semantics, evaluation thresholds, gold-data policy, split construction, or adoption gates is **RESEARCH DECISION REQUIRED**.


## 28. Research rulings recorded at STOP 1 (2026-10-08)

STOP 1 passed once these rulings were recorded; planning estimate about $6.5 approved (soft warning $15, hard cap $25).

**Ruling 1 - alias provenance.** The 1.00 gate does not require fabricating history the pre-CR-011 pipeline never recorded. Three provenance classes: `legacy_reconstructed`, `legacy_unrecorded` (origin explicitly unknown; record alias value, pre-sleep canonical node id, baseline run/snapshot/hash, `provenance_class`, `historical_origin_status = unknown`, migration/backfill record; never invent a section, quote, rule or merge event) and `cr011_native` (complete evidence/rule/transaction provenance). `AliasProvenanceRecordCompleteness` = aliases with a valid structured provenance envelope / all (canonical node, alias) entries in the post-sleep canonical view; required 1.00. `LegacyOriginTraceability` is descriptive only. `CR011NewAliasSourceTraceability` = 1.00 and no new alias may be `legacy_unrecorded`. A `legacy_unrecorded` alias may be preserved, used for mention matching and candidate retrieval, but may not independently establish SAME or trigger an automatic merge (identity must be revalidated from current source evidence under CR-011 guards). The immutable pre-sleep snapshot is not mutated; a sidecar registry is allowed. Rollback must still reconstruct the original exactly.

**Ruling 2 - type compatibility.** `Concept` is not a wildcard; it is a generic type with zero positive identity evidence. Compatibility moves to config (`type_compatibility` in `configs/sleep_consolidation_v1.yaml`): every type with itself; Protocol-Mechanism, Component-Concept, DataUnit-Concept, Parameter-Property, Identifier-Parameter; all other cross-type pairs incompatible. Compatible only means "no type veto". Compatibility is not transitive (Component-Concept and Concept-DataUnit do not make Component-DataUnit compatible), so the cluster guard checks the material cross-pairs of the whole proposed cluster. The existing node-type resolution policy after a valid merge continues unless STOP 2 exposes a concrete conflict.

**Other findings (no decision needed).** Implement MergeTransaction + explicit inverse + round-trip hash (absence of rollback is a baseline deficiency). The `same_concept` queue is a candidate source, not a merge instruction. Misconception objects stay out of consolidation but their references to canonical nodes are re-keyed on migration (no dangling references). The 0.70 review band is not a CR-011 identity threshold (development-selected `t_auto`/`t_review`); the 0.6 floor may exist only as retrieval machinery, and candidate recall is reported at STOP 2. Current transitive closure and exact-string cross-chapter merges are frozen baseline (S0) behaviour only. 86 owner labels / 15 negatives is no ground to weaken a gate: if development cannot support merge precision >= 0.98 and the Wilson criterion where sample size permits, ML auto-merge is disabled and the scorer becomes review-ranking only (a valid outcome).

**STOP 2 authorised.** No change to SLEEP-240, identity semantics, the CR-008 DIFFERENT veto, the precision requirement, the held-out policy or the adoption gates. Return to Research only for a new methodological ambiguity, inability to construct SLEEP-240 under the frozen design, a required change to identity/gold/gate semantics, or materially unexpected spend.
