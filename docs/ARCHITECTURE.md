# Architecture — H420020 Conceptual Understanding Mapper

Version 1 · 2026-09-28, updated for CR-001 (relation registry v1, `ChainLink` reasoning layer). This is the reference for data models and diagnosis logic. If the code and this document disagree, fix one of them and log it in `DECISIONS.md`.

---

## 1. Research principles the code must respect

These come from the literature review and are non-negotiable design rules.

1. **A wrong answer is not the same as a misconception.** It may reflect missing, inactive, insufficient or inaccurate knowledge.
2. **A missing relation is not the same as an incorrect relation.** Absence → *incomplete*. Only an explicit contradiction is evidence of a misconception.
3. **Semantic similarity is not conceptual correctness.** Relation type, direction, polarity and conditions can make lexically similar statements opposite. Embeddings may only *propose candidates*; the verdict comes from the stored graph.
4. **One answer's graph is evidence, not a learner model.** Confirming a misconception needs repeated evidence.
5. **Teaching order is not a prerequisite.** Book order is stored as structure (`introduced_in`), never as `prerequisite_of`.
6. **Every expert fact must be traceable** to a textbook quote, a model version and a review status.

---

## 2. Pipeline

```
          ┌──────────── EXPERT SIDE ─────────────┐        ┌──────────── STUDENT SIDE ────────────┐
Textbook (P&D 6e, .rst)                              SAF answers (+ feedback, labels)
   │ parse → Sections (book order)                       │
   │ FACE-style candidates & stats (spaCy, tf-idf)        │ reference answer → Propositions (gold)
   │ per-section Concept LLM (+ registry retrieval)       │ feedback → silver labels (expressed/missing/
   │ canonicalise (merge / is_a / new)                    │            contradicted) → human-verified subset
   │ per-section Relation LLM (+ earlier concepts)        │
   │ prerequisite candidates (defined→used)               │ answer → Student edges (linked to KG concepts,
   │ hierarchy placement                                  │          polarity/modality/conditions/stance)
   │ checks (evidence substring, types, cycles)           │
   │ human review                                         │
   ▼                                                      ▼
Expert KG ── propositions mapped ──► Expected subgraph per question ◄── alignment (rules → LLM fallback)
                                                          │
                                                          ▼
                                   DiagnosisRecord (matched / missing / contradicted / extra,
                                   broken chains, upstream gaps, misconception candidates)
                                                          │
                                   evaluation vs human-verified + silver labels, SAF labels/scores
```

### Graph layers (one set of concept nodes, several edge layers)

| Layer | Edges | Built by |
|---|---|---|
| structure | `introduced_in`, `mentioned_in` (Concept → Section); Section order | parser + concept mentions |
| taxonomy | `is_a`, `part_of` | relation LLM + hierarchy placement |
| prerequisite | `prerequisite_of` | defined→used evidence (+ optional LLM check) |
| semantic | `has_property`, `uses`, `requires`, `triggers`, `causes`, `prevents`, `increases`, `decreases`, `precedes`, `contrasts_with`, `equivalent_to`, `performs`, `has_purpose` | relation LLM |
| reasoning (edge → edge) | `cause`, `purpose`, `condition`, `sequence`, `contrast` | `ChainLink`; expert from textbook/reference answers, student from connectives (CR-001) |
| misconception | `asserts`, `conflicts_with` (Misconception → edge) | mined from SAF feedback, human-curated (M8) |

---

## 3. Node schema

### Concept

| Field | Type | Notes |
|---|---|---|
| `concept_id` | str | `c_` + slug of canonical name; stable |
| `canonical_name` | str | |
| `aliases` | list[str] | acronyms, spelling variants |
| `node_type` | enum | `Protocol`, `Mechanism`, `Component`, `DataUnit`, `Parameter`, `Property`, `Event`, `State`, `Layer`, `Concept` |
| `definition` | str \| None | in the book's own words |
| `first_introduced` | section_id \| None | section where `role=defined` first occurs |
| `mentions` | list[ConceptMention] | {section_id, role: `defined` \| `used` \| `mentioned`, quote} |
| `status` | enum | `candidate` \| `active` \| `deprecated` \| `merged` |
| `merged_into` | concept_id \| None | |
| `confidence` | float | |
| `extracted_by` | {model, prompt_version, run_id} | |
| `validation` | Validation | see below |
| `version` | int | |

### Section
See `BUILD_PLAN.md` M1 task 4.

### Misconception (M8)

| Field | Notes |
|---|---|
| `misconception_id` | e.g. `M-TCP-phase-swap` |
| `name`, `description` | |
| `asserted_edges` | the wrong triples the misconception implies (same core fields as an edge) |
| `conflicts_with` | expert edge IDs it contradicts |
| `evidence` | example answer IDs + feedback quotes |
| `source` | `mined_from_feedback` \| `literature` \| `manual` |
| `validation` | |

---

## 4. Edge schema (built for diagnosis)

**Design rule:** expert edges and student edges share the same **core fields** — `source_id`, `relation`, `target_id`, `polarity`, `modality`, `conditions`, and (CR-001) `part_type`, `dimension`, `surface_phrase`, `relation_family`, `registry_version` — so they can be compared field by field. Every other field exists to support a specific diagnosis.

| CR-001 core field | Type | Diagnostic purpose |
|---|---|---|
| `part_type` | `component \| member \| phase \| None` | Required iff `relation == part_of`; catches `part_type_error` (right endpoints, wrong part-whole type — transitivity fails across types, Winston/Chaffin/Herrmann 1987) |
| `dimension` | str \| None | Only on `contrasts_with`; names what differs (e.g. "cwnd growth rate") |
| `surface_phrase` | str \| None | The linking words as written; required on `StudentEdge` and on LLM-extracted `ExpertEdge`; preserves partial knowledge even after canonicalisation (Yin et al. 2005) |
| `relation_family` | str | Derived from the registry; a correct family with the wrong fine relation earns partial credit (`family_match`) instead of zero |
| `registry_version` | int \| None | Stamped by code that writes the edge; `None`/missing on a file means v0 (pre-CR-001) |

### 4a. Relation registry (`configs/relations_v1.yaml`, CR-001; `relations_v0.yaml` kept loadable for history)

| Field | Diagnostic purpose |
|---|---|
| `name`, `layer`, `definition`, `examples` | Shared vocabulary for the LLM prompts and reviewers |
| `domain_types`, `range_types` | Detects wrong entity type / category errors |
| `directional` | A reversal only counts as an error if the relation is directional |
| `symmetric`, `transitive`, `inverse_of` | Normalises "B has_part A" = "A part_of B"; enables chain inference. `transitive` may be `true`/`false` or the literal `"within_same_part_type"` (`part_of` only chains within the same `part_type`) |
| `conflicts_with` | Separates contradicting relations (`increases` vs `decreases`) from harmless near-synonyms |
| `compatible_with` | `{relation: full \| partial}`: credit for paraphrased relation types |
| `family` | One of the 6 semantic families + `pedagogical` (`registry.families`); drives family-level partial credit and family-first multiple-choice verification (§6) |
| `template` | Plain-language template (`"{X} causes {Y}"`) filled by `template_for`/`choice_set` for LLM verification prompts |
| `near_misses` | list[{relation, example, why}]: the annotation-guideline negatives that make choice-based extraction reliable (QA4RE 2023; GoLLIE 2024) |
| `qualifiers` (registry-level, not per-relation) | `part_type` (required on `part_of`), `dimension` (recommended on `contrasts_with`), `surface_phrase`, `polarity`, `modality`, `conditions` — which relations each applies to and whether it's required |
| `chain_link_types` (registry-level) | `{name, template, cues}` for the 5 `ChainLink` types (§4e), modelled on PDTB-3's top-level senses |

### 4a-bis. Registry v1.1 and extraction v3 (CR-007)

- **Registry v1.1** (`configs/relations_v1.1.yaml`, generated from v1 + `configs/registry-patches/CR-007-relations-v1.1.yaml`; a superset of v1, now the default): adds `acts_on` (source acts on a data unit; requires the `action_type` qualifier: send, receive, forward, transform, check, store, drop, generate, other), `connected_to` (symmetric topology), and the **gated** `identifies`, `encapsulates`, `trades_off_with` (kept only if the re-run yields >= 5 instances and >= 80% of the sampled instances are owner-marked correct; outcome in DECISIONS). New node type `Identifier`; new qualifiers `action_type`, `corrects_intuition`, `intuition`; `dimension` now also applies to `trades_off_with`. v1.2 stays reserved for CR-004 `instantiates`.
- **Generic type:** the node type `Concept` is a wildcard in the domain/range check (`RelationRegistry.check_types`): extraction types are coarse, specific wrong types are still rejected.
- **Mention matching:** `expert_kg/mentions.py` finds concept mentions by longest-match, non-overlapping spans at token boundaries over all names and aliases ("bit rate" beats "bit"). Candidate pairs, propagation, spread and first occurrence all use it.
- **First occurrence and roles:** `first_chapter` is the first longest-match occurrence in book order, not the first extraction. `defined` marks only the first definition; later `defined` tags become `refined` (evidence kept in the append-only `description_history`).
- **Concept extraction "v3"** = prompt v2 + consistency propagation (a concept accepted in any section is tagged `mentioned`, source `propagation`, wherever it occurs as a longest-match mention).
- **Canonicalisation v2:** type-aware (different node types are never `same`; logged as `related` candidates) with a review band: an LLM "same" with similarity < 0.70 is not merged and goes to the merge review sheet (provisional).
- **Relation classification v3:** family step, then a filled-option relation step (every option rendered with the two concept names; includes no_relation and other with a description and suggested label), then checks: comparison relations need a `dimension` grounded in the sentence; the evidence quote must be a substring of the sentence; **endpoint grounding** (each endpoint must be a longest-match mention inside the evidence quote, else `endpoint_not_grounded`); domain/range; then the qualifier step.
- **Pair selection:** a global budget (~700 pairs for ch1-3) with a per-section minimum; defined/used concepts' best-cue pair first, mentioned-only concepts only in the fill phase; a random sample of unselected pairs is classified but kept out of the graph, to estimate the missed-relation rate.

### 4b. ExpertEdge

| Group | Field | Type / values | Diagnostic purpose |
|---|---|---|---|
| Identity | `edge_id` | str | |
| | `source_id`, `target_id` | concept_id | |
| | `relation` | registry name | |
| | `layer` | `structure` \| `taxonomy` \| `prerequisite` \| `semantic` \| `misconception` | keeps teaching order apart from semantic truth |
| Truth conditions | `polarity` | `affirmed` \| `negated` | a stored *negated* fact makes a student's affirmed version an explicit contradiction |
| | `modality` | `necessary` \| `always` \| `typically` \| `possible` \| `never` | catches over-generalisation |
| | `conditions` | list[concept_id \| str] | catches claims true only under other conditions (timeout vs 3 duplicate ACKs) |
| | `statement` | str | canonical sentence for the judge and for feedback |
| Diagnostic weight | `criticality` | `core` \| `supporting` \| `peripheral` | missing core = incomplete; missing peripheral = minor |
| | `question_links` | list[{question_id, role: `required` \| `bonus`, weight, source: `reference_answer` \| `feedback_rubric` \| `textbook`}] | per-question expected subgraph |
| | `learning_objective_ids`, `cognitive_level` | list[str], str \| None | report per learning objective (optional in v1) |
| | `chain_id`, `chain_position` | str \| None, int \| None | broken reasoning chains (missing middle link) |
| | `depends_on_edges` | list[edge_id] | upstream-gap diagnosis |
| | `introduced_in` | section_id | |
| Misconception hooks | `confusable_with` | list[{ref_id, ref_kind: `edge` \| `concept`, type: `substitution` \| `reversal` \| `type_swap` \| `condition_swap`}] | systematic confusions → misconception candidates |
| | `contradicted_by_misconceptions` | list[misconception_id] | name the misconception |
| | `diagnostic_power` | float \| None | learned in M7: how well this edge separates correct from incorrect answers |
| Provenance & trust | `evidence` | list[{source, section_id, quote}] | quote **must** be a verified substring |
| | `extracted_by` | {model, prompt_version, run_id} \| None | reproducibility (None for human-authored) |
| | `confidence` | float | |
| | `validation` | {status: `unreviewed` \| `accepted` \| `edited` \| `rejected`, reviewer, date, note} | only validated edges count as strong evidence |
| | `status`, `version`, `superseded_by` | `candidate` \| `active` \| `deprecated` \| `merged` | soft delete, history |
| | `origin` | `textbook` \| `reference_answer` \| `manual` | question-specific edges from reference answers are flagged as textbook coverage gaps |

### 4c. StudentEdge (same core fields, plus these)

| Field | Values | Diagnostic purpose |
|---|---|---|
| `response_id` (= answer_id), `student_id` (None for SAF), `question_id` | | aggregation |
| `evidence_span` | {start, end, text} char offsets | shows exactly which words caused the diagnosis; verified |
| `stance` | `asserted` \| `hedged` \| `questioned` \| `quoted` | hedged claims are weaker evidence |
| `extraction_confidence`, `link_confidence` | 0–1 | low link confidence → keep `unlinked:<surface>` rather than forcing a match |
| `alignment` | {expert_edge_id \| None, match_type, decided_by: `rule` \| `llm`, rationale} | |
| `match_type` | `exact` \| `paraphrase` \| `partial_relation` \| `reversed` \| `polarity_flip` \| `substituted_concept` \| `modality_error` \| `condition_error` \| `wrong_type` \| `unsupported_extra` \| `valid_extra` \| `family_match` \| `part_type_error` (CR-001) | |
| `verdict` | `correct` \| `inaccurate` \| `contradictory` \| `irrelevant` | edge-level judgement |
| `misconception_candidates` | list[{misconception_id, evidence_strength}] | candidates only |

**match_type → verdict mapping (default):**
- exact, paraphrase, valid_extra → `correct`
- partial_relation, modality_error (weaker claim), **family_match**, **part_type_error** → `inaccurate`
- polarity_flip, reversed, substituted_concept, condition_error, wrong_type, modality_error (over-generalisation) → `contradictory`
- unsupported_extra → `inaccurate`, or `contradictory` if it conflicts with a KG edge

CR-001 additions: `family_match` = same endpoints/family, a different relation that isn't `compatible` (e.g. `causes` where the expert says `prevents` — wrong specific relation, right ballpark). `part_type_error` = `part_of` with the right endpoints but the wrong `part_type`.

### 4e. ChainLink (edge → edge reasoning layer, CR-001)

A `ChainLink` says *how* one edge supports another — the concept-level graph alone can't express "the student knows A and B but links them with the wrong reason," a key misconception pattern (PDTB-3 top-level senses: cause, purpose, condition, sequence, contrast). Lives at a gold file's **top level** (a `chain_links:` list sibling to `concepts:`/`edges:`), not nested inside individual edges — expert links in `data/gold/expert_pilot/<qid>.yaml`, student links in the student graph file.

| Field | Type | Notes |
|---|---|---|
| `link_id` | str | |
| `from_edge_id`, `to_edge_id` | edge_id (or, for student links, a synthetic `SE-<index>` position — `StudentEdge` has no id of its own) | `from` is the *supported* proposition, `to` is the *supporting* one |
| `type` | `cause` \| `purpose` \| `condition` \| `sequence` \| `contrast` | |
| `statement` | str | e.g. "cwnd is reset to 1 MSS because a timeout signals severe congestion" |
| `surface_phrase` | str \| None | the connective as written ("because", "so that", ...) |
| `evidence` | list[Evidence] | expert: textbook/reference answer; student: answer span |
| `origin` | `textbook` \| `reference_answer` \| `manual` \| `student` | |
| `question_ids` | list[str] | expert links: questions where this link is expected |
| `validation` | Validation \| None | |

### 4f. ChainLinkAlignment (diagnosis verdict on a student's chain link, CR-001)

| Field | Notes |
|---|---|
| `expert_link_id`, `student_from_edge_id`, `student_to_edge_id` | |
| `match_type` | `exact` (same link type, same edges) \| `wrong_link_type` (same edges, different type, e.g. cause vs purpose) \| `reversed_link` (from/to swapped for cause/purpose/condition) \| `missing_link` (both edges present, link not stated) \| `unsupported_link` (student links two edges with no expert link) |
| `verdict` | `wrong_link_type`/`reversed_link` → `contradictory` (a reasoning-misconception candidate); `missing_link`/`unsupported_link` → `inaccurate`; `exact` → `correct` |
| `rationale` | str |

### 4d. DiagnosisRecord (per answer; missing edges live here)

| Field | Notes |
|---|---|
| `answer_id`, `question_id`, `run_id` | |
| `matched`, `missing`, `contradicted`, `extra` | lists of edge IDs, each with criticality and weight |
| `required_coverage` | weighted share of required edges matched |
| `broken_chains` | chain_ids with a missing or contradicted middle link |
| `upstream_gaps` | missing edges whose `depends_on_edges` are also missing |
| `misconception_candidates` | [{misconception_id, evidence_strength, supporting_edge_ids}] |
| `chain_link_results` (CR-001) | list[ChainLinkAlignment] (§4f) |
| `reasoning_errors` (CR-001) | list[link_id] — links with `wrong_link_type` or `reversed_link` |
| `family_coverage` (CR-001) | dict[family, float] — weighted coverage of required edges, per relation family |
| `label_3way` | `correct` \| `incomplete` \| `contradictory` |
| `saf_label_pred`, `score_pred` | for comparison with SAF |

**Rules**
- An answer with only missing edges can never be `contradictory`.
- A misconception *candidate* needs an explicit contradiction of a core edge or a confusable substitution.
- A misconception is *confirmed* only with repeated evidence across responses. SAF has no student IDs, so confirmation is out of scope for SAF.

---

## 5. Worked example (TCP congestion control, P&D §6.3)

```yaml
edge_id: E-TCP-014
source_id: c_slow_start
relation: has_property
target_id: c_exponential_cwnd_growth
layer: semantic
polarity: affirmed
modality: always
conditions: [c_cwnd_below_ssthresh]
statement: "During slow start, cwnd roughly doubles every RTT (exponential growth) while cwnd < ssthresh."
criticality: core
question_links: [{question_id: q_xxxxxxxx, role: required, weight: 0.25, source: reference_answer}]
chain_id: CH-tcp-cc-phases
chain_position: 1
confusable_with: [{ref_id: E-TCP-015, ref_kind: edge, type: substitution}]   # congestion_avoidance has_property linear_cwnd_growth
contradicted_by_misconceptions: [M-TCP-phase-swap]
evidence: [{source: "Peterson & Davie 6e", section_id: "6.3", quote: "..."}]
validation: {status: accepted, reviewer: ZT}
status: active
version: 1
origin: textbook
```

- "In slow start the window grows linearly" → `c_slow_start has_property c_linear_cwnd_growth` → **substituted_concept** (the target was swapped with its confusable sibling's) → `contradictory`, candidate `M-TCP-phase-swap`.
- "On a timeout the congestion window is halved" → matches the triple-duplicate-ACK edge with the wrong trigger → **condition_error** → `contradictory`.
- Describes slow start correctly but never mentions ssthresh → the `c_ssthresh` edges are **missing** → `incomplete`, not a misconception.

---

## 6. Relation extraction method (M5/M6, CR-001)

Plain-prompted relation extraction underperforms; turning it into **multiple-choice over plain-language templates** closes most of the gap to fine-tuned models (QA4RE 2023; Sainz et al. 2021 EMNLP). The extraction pipeline is four passes, not one:

1. **Stage A — candidate pairs + evidence.** The concept LLM (or co-occurrence heuristics) proposes concept pairs worth checking, each with a supporting quote.
2. **Stage B — family-first multiple-choice verification.** `RelationRegistry.choice_set(x, y, families=...)` builds the option list: every relation's filled template (optionally restricted to a family shortlist first, then the fine relation within it — PDTB's coarse-to-fine pattern), **the reversed template for directional relations**, `NO_RELATION`, and `OTHER`. The LLM picks one. Direction and "no relation" are checked in the same step this way, rather than assumed.
3. **Qualifier pass (separate).** Polarity, modality, conditions, `part_type`/`dimension`/`surface_phrase` are extracted in their own pass, targeting the well-documented LLM weakness on negation (García-Ferrero et al. 2023) — a single extraction pass tends to get affirmative cases right and miss negated ones.
4. **Chain-link pass.** Given two already-accepted edges, ask whether the source text connects them with a reason (cause/purpose/condition/sequence/contrast) and with what connective.
5. **`other`-relation review.** Anything routed to `OTHER` is logged and reviewed each run — cluster and decide whether it becomes a new registry relation (a new version + `DECISIONS.md` entry) or maps onto an existing one.

**Evaluation additions:** ontology conformance rate (domain/range respected), unsupported-by-text rate (Text2KGBench-style hallucination check), direction accuracy, polarity accuracy — reported separately, not folded into one aggregate F1, since each targets a distinct known LLM failure mode (reversal curse; negation).


## Organisation snapshots (CR-006): per-chapter core-periphery view

`cumap kg organise` reorganises the *presentation* of a chapter snapshot; it never rewrites content (rules 13-15 in CLAUDE.md). Code: `src/cumap/organisation/`; config: `configs/organisation.yaml`; outputs under `data/processed/kg/<run_id>/organisation/<org_id>/ch<N>/{org_nodes,communities,events}.jsonl` + `manifest.json`; `org_id = "org_" + sha1(kg_run_id | mode | config_hash | code_version)[:8]`.

**Graph G_N** = nodes and typed edges of chapters <= N (an edge exists only once both endpoints do; semantic + taxonomy layers, prerequisite layer excluded). Edge weight = registry `diagnostic_prior` of the family x edge confidence (1.0 while absent). Co-occurrence never counts.

**Importance** (each component becomes a percentile rank among the *eligible* nodes, i.e. linked and not background; weighted mean; weights fixed in config, 0.35 / 0.20 / 0.25 / 0.20):
`pagerank` (weighted, damping 0.85, on a directed projection), `coreness` (k-shell on the undirected unweighted projection), `spread` (share of the snapshot's sections where the concept is `defined` or `used`), `bridging` (participation coefficient over fine Leiden communities).
*PageRank direction rule* (importance flows to what others depend on, belong to or serve): toward the target for `is_a, part_of, requires, uses, has_purpose, instantiates`; toward the source for `has_property`; both ways otherwise.
`importance_raw` = the weighted mean; `importance_adj` = percentile of the residual of `importance_raw ~ log1p(sections since first seen)` within the snapshot (removes only the average age effect).
*Background-vocabulary guard*: appears in >= 50% of sections, never `defined`, and typed edges per appearance in the bottom quartile -> `background` band (excluded from rings and the core fit); owner overrides live in config.

**Rings** are quantile bands of the chosen basis over eligible nodes (centre 5%, inner 15%, middle 30%, outer 50%), plus `unlinked` (no typed edges; a large count points to relation-extraction recall gaps) and `background`. **Rings are not CR-004 tiers.** Radius = r_min + (1 - importance)(r_max - r_min) with importance the percentile rank of the chosen basis.

**Is there really a core?** Borgatti-Everett discrete fit on the eligible subgraph (core = centre + inner) against (1) same-density random graphs (gates the label: z >= 2 and delta-rho >= 0.10 -> present; z >= 2 only -> weak core; else the banner "No clear core at this chapter: ring positions are weakly supported.") and (2) degree-preserving rewires (reported, not gated: a single core is largely explained by degrees). 200 samples each, seeds fixed; every sample recomputes the core with the same importance procedure, holding `spread` and exposure fixed.

**Communities** (Leiden, fixed seed, coarse 0.5 / fine 1.0) get persistent IDs by Jaccard >= 0.3 matching across snapshots and lifecycle events (continue, grow, shrink, merge, split, birth, death; "changed" below Jaccard 0.7). **Events** (`ring_in/out`, `enter/leave_centre`, `late_centraliser`, `fading`, `node_new`) carry the new edge and section IDs behind them; `persistent_periphery` is a review flag only. **Layout**: 2D disc, angle = coarse-community sector (centres fixed once born, an existing node keeps its angle while in the same community, relaxation capped at 20 degrees per chapter). Principle mode (replay with approved principles) waits for CR-004 STOP C.
