# Architecture — H420020 Conceptual Understanding Mapper

Version 1 · 2026-09-28. This is the reference for data models and diagnosis logic. If the code and this document disagree, fix one of them and log it in `DECISIONS.md`.

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
| semantic | `has_property`, `uses`, `requires`, `triggers`, `causes`, `prevents`, `increases`, `decreases`, `precedes`, `contrasts_with`, `equivalent_to` | relation LLM |
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

**Design rule:** expert edges and student edges share the same **core fields** — `source_id`, `relation`, `target_id`, `polarity`, `modality`, `conditions` — so they can be compared field by field. Every other field exists to support a specific diagnosis.

### 4a. Relation registry (`configs/relations_v0.yaml`)

| Field | Diagnostic purpose |
|---|---|
| `name`, `layer`, `definition`, `examples` | Shared vocabulary for the LLM prompts and reviewers |
| `domain_types`, `range_types` | Detects wrong entity type / category errors |
| `directional` | A reversal only counts as an error if the relation is directional |
| `symmetric`, `transitive`, `inverse_of` | Normalises "B has_part A" = "A part_of B"; enables chain inference |
| `conflicts_with` | Separates contradicting relations (`increases` vs `decreases`) from harmless near-synonyms |
| `compatible_with` | `{relation: full \| partial}`: credit for paraphrased relation types |

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
| `match_type` | `exact` \| `paraphrase` \| `partial_relation` \| `reversed` \| `polarity_flip` \| `substituted_concept` \| `modality_error` \| `condition_error` \| `wrong_type` \| `unsupported_extra` \| `valid_extra` | |
| `verdict` | `correct` \| `inaccurate` \| `contradictory` \| `irrelevant` | edge-level judgement |
| `misconception_candidates` | list[{misconception_id, evidence_strength}] | candidates only |

**match_type → verdict mapping (default):**
- exact, paraphrase, valid_extra → `correct`
- partial_relation, modality_error (weaker claim) → `inaccurate`
- polarity_flip, reversed, substituted_concept, condition_error, wrong_type, modality_error (over-generalisation) → `contradictory`
- unsupported_extra → `inaccurate`, or `contradictory` if it conflicts with a KG edge

### 4d. DiagnosisRecord (per answer; missing edges live here)

| Field | Notes |
|---|---|
| `answer_id`, `question_id`, `run_id` | |
| `matched`, `missing`, `contradicted`, `extra` | lists of edge IDs, each with criticality and weight |
| `required_coverage` | weighted share of required edges matched |
| `broken_chains` | chain_ids with a missing or contradicted middle link |
| `upstream_gaps` | missing edges whose `depends_on_edges` are also missing |
| `misconception_candidates` | [{misconception_id, evidence_strength, supporting_edge_ids}] |
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
