# CR-004 — Knowledge organisation layer: big ideas, knowledge types, levels, progression, structural diagnosis

**Status:** approved by owner (Zheng Tat Wong), 2026-09-28
**Depends on:** CR-001 (registry v1, tiers, family-first choice), CR-002 (concept scores, `t_anchor` / `t_link`), CR-003 (external loaders, blind check sheets, Wilson CIs).
**Timing:**
- **Build the tooling now.** Everything is testable on fixtures without network access.
- **Run** each step once its inputs exist:
  - §4–§8 need an M5 KG run (the pilot chapters are enough to start);
  - §10 needs M6/M7 outputs;
  - §5.5 needs M4 silver labels.

**Rationale and sources:** `docs/research/kg-organisation-research.md` (add it to the repo from the project), especially §4 (recommendation) and §5 (how big ideas are determined).

---

## 1. Why

Learning research says experts organise knowledge around **big ideas** and **conditionalised core concepts**, while novices hold sparse, surface-level fragments:
- Ausubel;
- *How People Learn* (2000);
- Chi, Feltovich & Glaser (1981);
- Ambrose et al. (2010), ch. 2.

Kinds of knowledge (factual, conceptual, procedural) need different feedback (revised Bloom; KLI). Understanding shows in **how connected** an answer is (SOLO; Lister et al. 2006).

The KG so far has content and a book order, but **no big-idea level, no knowledge types and no structural diagnosis**. CR-004 adds them.

**Build rules:**
- **Principles are sentences, not labels.**
  - They're proposed by the LLM from authoritative documents.
  - They're measured on the KG.
  - They're pre-screened by a diverse LLM panel.
  - They're **decided by a human Delphi**.
- An LLM panel is an adjunct only: in a medical Delphi simulation, LLMs agreed with each other *more* than human experts did (93.3% vs 81.5%), with 78.5% concordance.
- Student data (troublesomeness) is used to **flag threshold concepts**, never to decide what a big idea is.

---

## 2. Order of work and stop points

Commit per step with the prefix `CR-004:`. Build steps 1–10 as tested tooling first, then run them as inputs become available.

1. Registry patch + schema additions (§3)
2. Communities + recursive summaries (§4)
3. Principle candidates, KG breadth, LLM panel, shortlist (§5.1–5.7)
   **⛔ STOP A:** show the shortlist with metrics and LLM-panel agreement.
4. Human Delphi sheets (§5.8)
   **⛔ STOP B:** sheets ready; the humans rate them.
5. Final principles, agreement, LLM-vs-human comparison, external validity (§5.8–5.9)
   **⛔ STOP C:** show the results; I approve the final list.
6. Final `instantiates` links + threshold flags (§5.10)
7. Knowledge type per concept and per edge (§6)
8. Tiers (§7) and per-question mini-maps (§8)
9. Blind check sheets: `instantiates` (40), knowledge type (60), mini-maps (pilot questions)
   **⛔ STOP D:** sheets ready.
10. Misconception perturbation model (§9)
11. New diagnostic outputs + SOLO blind coding sheet (60 answers) + evaluation (§10)
    **⛔ STOP E:** coding sheet ready; later, results.
12. Optional structure audit (§11); tests (§12); docs (§13)

---

## 3. Registry patch and schemas

### 3.1 Registry patch
Apply `configs/registry-patches/CR-004-instantiates.yaml` as the **next minor registry version**:
- `relations_v1.1.yaml`, or `v1.2` if CR-003's agreement test already produced v1.1.

The patch adds:
- the node type `Principle`;
- the layer `principle`;
- the family `organisation` (**excluded** from the normal family-first choice set);
- the relation `instantiates` (core concept → principle).

`instantiates` is only produced by the principle-linking step (§5.3, §5.10), never by general relation extraction. Log it in DECISIONS.

### 3.2 Schema additions
**`Concept`** gains:

| Field | Type | Notes |
|---|---|---|
| `knowledge_type` | `Literal["factual","conceptual","procedural"] \| None` | §6 |
| `tier` | `Literal["principle","core","detail"] \| None` | §7 |
| `is_threshold` | `bool` | §5.10 (human-confirmed) |
| `community_ids` | `list[str]` | §4 (one per hierarchy level) |

**New `PrincipleMeta`** (one per `Concept` with `node_type = Principle`, stored in `principles.jsonl`):
```text
principle_id, short_name, statement (full declarative sentence),
sources: [{source, locator, quote}]            # quotes verified as substrings
kg_breadth: {n_concepts, n_chapters, n_communities, n_questions}
panel: {round: int, ratings: {panellist: {criterion: 1..5}}, median: {criterion: float}, iqr: {criterion: float}}
human_delphi: {round: int, ratings: {rater_id: {criterion: 1..5, decision: keep|drop|merge|edit}}, median, iqr}
troublesomeness: float | None                  # train/val SAF only
is_threshold: bool
approval: {status: candidate|shortlisted|approved|rejected|merged, approvers: [..], date, merged_into}
version: int
```

**New `Community`:** `community_id, level, member_concept_ids, summary, summary_evidence [{section_id, quote}], source_sections`.

**New `QuestionMiniMap`:** `question_id, target_concepts, target_edges, proximal_precursors, distal_precursors, successors` (all concept or edge IDs, with a reason for each).

**`Misconception`** (reframed, §9) gains:
- `perturbs_edges` (expert edge IDs);
- `perturbation_type ∈ {substitution, reversal, overgeneralisation, wrong_category, missing_condition, wrong_link_type}`;
- `asserted_edges` (1–4 core-field triples);
- `question_ids`;
- `recurs_across_questions: bool`;
- `principle_ids`.

**`DiagnosisRecord`** gains:
- `solo_level`;
- `solo_evidence` (the components and coverage used);
- `knowledge_type_profile: {factual|conceptual|procedural: {missing_w, contradicted_w}}`;
- `integration_score`;
- `progression_flags: [{edge_id, missing_precursor_ids}]`;
- `principle_links: [edge_id]`.

---

## 4. Communities and recursive summaries (GraphRAG / RAPTOR style)

1. **Communities:**
   - Leiden (`leidenalg` + `python-igraph`, or `graspologic`) on an undirected projection of the **semantic + taxonomy** layers;
   - only anchored concepts (`concept_score ≥ t_anchor` or human-accepted);
   - edge weight = `edge.confidence × family diagnostic_prior`.
   - Two resolution levels (coarse and fine; resolution values in config). Fixed seed; report modularity.
2. **Community summaries** (strong tier): 3–5 sentences per community from its member concepts, edges and the top evidence quotes. Every claim needs a `summary_evidence` quote (verified substring).
3. **Recursive text summaries:** section summaries (bulk tier) → chapter summaries (strong tier) → book summary (strong tier). Store them with provenance.
4. **Outputs:**
   - `data/processed/kg/<run_id>/communities.jsonl`
   - `summaries_{section,chapter,book}.jsonl`
   - `reports/cr004_communities.md` (sizes, modularity, the top concepts per community, and how well communities line up with chapters)

---

## 5. Principle (big idea) pipeline

**Criteria used throughout** (1–5 Likert), adapted from the NRC Framework (2012) and Wiggins & McTighe (UbD):

| Code | Criterion |
|---|---|
| C1 | A key organising idea of networking (not just a topic) |
| C2 | A tool for understanding more complex ideas and solving problems |
| C3 | Relevant to practice and to students' experience |
| C4 | Teachable at increasing depth across a course or curriculum |
| C5 | Requires "uncoverage": abstract or commonly misunderstood |
| C6 | Enduring value beyond this course |

### 5.1 Source documents (loaders as in CR-003 §3; record licence and terms)
- P&D **Foundation** chapter + all chapter summaries (§4)
- Community summaries (§4)
- **CS2023** Networking & Communication knowledge area (ACM; check the terms)
- **RFC 1958**, *Architectural Principles of the Internet* (IETF; RFC text is freely reusable; record it)
- Optional: Saltzer, Reed & Clark (1984) end-to-end paper (summary only, if accessible); Denning's *Great Principles* (summary only)

### 5.2 Candidate generation (strong tier, prompt `principle_candidates/v1`)
- Output **20–30 candidates**. Each has:
  - `short_name`;
  - `statement`: one declarative sentence expressing a generalisation, not a topic label;
  - ≥ 1 source citation with a verified quote;
  - a one-line rationale.
- Deduplicate with embeddings + an LLM merge decision.
- Reject statements that name a single mechanism only (e.g. "slow start doubles cwnd") or are vacuous ("networks transmit data").

### 5.3 KG breadth: provisional `instantiates` linking
- For each anchored **core-candidate** concept (not yet tiered; use all anchored concepts): a multiple choice over the candidate statements + `NONE`, allowing up to 2 picks.
- Each pick needs a justification and, where possible, a supporting quote from one of the concept's sections.
- Bulk tier, escalating to strong on low confidence.
- Metrics per candidate:
  - `n_concepts` (instantiating concepts);
  - `n_chapters` (distinct chapters of those concepts);
  - `n_communities`;
  - `n_questions` (SAF questions whose expected subgraph contains an instantiating concept).

### 5.4 Simulated panel (Delphi style, adjunct only)
- **Panellists (diverse by design):**
  - strong tier as a networking researcher;
  - ceiling tier as a university networking instructor;
  - strong tier as a curriculum designer;
  - bulk tier as a final-year student.
- **Round 1:** each rates C1–C6 with a one-line reason per criterion, plus keep / drop / merge / edit.
- **Round 2:** each sees the anonymised medians, IQRs and reasons, and may revise.
- **Stop** after round 2, or earlier once all IQRs are ≤ 1.
- **Report:**
  - Kendall's W across panellists;
  - % of items at consensus (IQR ≤ 1);
  - changes between rounds.
- **Flag** "false consensus risk" if W > 0.8 in round 1. A panel that agrees too easily is suspect.

### 5.5 Troublesomeness (for threshold flags only)
- From M4 silver labels on **train + validation only**: the weighted rate of missing or contradicted propositions whose edges involve concepts instantiating each candidate.
- **Not** used in the ranking.

### 5.6 Granularity and overlap checks (thresholds in config)
- **Too narrow:** `n_concepts < 5` or `n_chapters < 2`.
- **Too broad:** instantiating concepts are > 40% of all anchored concepts.
- **Overlap:** Jaccard of instantiating-concept sets ≥ 0.6 → a merge proposal.

### 5.7 Ranking → shortlist of 12–15
- `score = w1·z(breadth) + w2·z(panel median of C1–C6) + w3·z(n_independent_sources)`. Default weights 0.4 / 0.4 / 0.2 (in config); breadth = mean z of `n_concepts`, `n_chapters`, `n_communities`.
- **Output:** `reports/cr004_principle_shortlist.md`. For each candidate: statement, sources, breadth metrics, panel medians/IQRs, flags, rank.

**⛔ STOP A.**

### 5.8 Human Delphi (the decision)
- **Raters:** the owner + supervisor (+ a networking lecturer if available). Sheets go in `data/interim/checks/principles_round{1,2}_<rater>.csv`; the humans save them to `data/gold/principles/`.
- **Round 1:** blind. The sheets show the statement and sources only: **no** LLM panel ratings, no breadth metrics, no rank. Raters score C1–C6 (1–5) and keep / drop / merge / edit, with free-text edits.
- **Round 2:** each rater sees the **human** group medians/IQRs and anonymised comments (still not the LLM panel), then revises.
- **Final list:** 8–12 principles with median C1 ≥ 4 and at least 2 of C2–C6 with median ≥ 4, plus owner approval for edits and merges.
- **Report** (`reports/cr004_principles_final.md`):
  - human agreement: Kendall's W, and IQR per item;
  - **LLM panel vs humans:** Spearman ρ of rankings, keep/drop concordance, and the items where they diverged with both sides' reasons. This is a reportable research finding.

**⛔ STOP B** (sheets ready) and **⛔ STOP C** (results; the owner approves).

### 5.9 External validity
- **Reference list:** a human-approved mapping of RFC 1958 principles + CS2023 NC introduction-level principles to short reference items, in `data/gold/principles/reference_items.csv`.
- **Recall:** the share of reference items covered by at least one final principle (LLM-judged, human spot-check).
- **Precision:** the share of final principles traceable to a reference item **or** meeting the breadth thresholds.

Report both, with Wilson CIs.

### 5.10 Final links and threshold flags
- Re-run `instantiates` against the **approved** principles only. A core concept may link to 1–2 principles.
- **Threshold-concept proposals** (the human confirms each): principles or core concepts with troublesomeness in the top tertile **and** integrative reach (`n_communities ≥ 2`). Meyer & Land criteria: transformative, integrative, troublesome.
- **Blind check:** 40 `instantiates` edges, stratified by principle (CR-003 sheet rules). Report precision with a Wilson CI.

---

## 6. Knowledge type (concepts and edges)
- **Concept:** bulk-tier multiple choice between {factual, conceptual, procedural}, using Anderson & Krathwohl's definitions in the guideline block:
  - factual = terminology or specific details/values;
  - conceptual = classifications, principles, models;
  - procedural = algorithms, steps, methods.

  A `node_type` prior goes into the prompt (Parameter/Property → factual; Mechanism/Event/State in a process → procedural; Concept/Protocol → conceptual). The prompt output wins; log disagreements with the prior.
- **Edge (derived by rule, documented in ARCHITECTURE):**
  - procedural if the relation ∈ {precedes, triggers, performs} or the chain-link type is `sequence`;
  - factual if the relation = `has_property` with a Parameter/Property target;
  - otherwise conceptual.
- **Blind check:** 60 concepts, stratified. Report κ.

## 7. Tiers
- **principle:** approved principles.
- **core:** anchored concepts with an `instantiates` edge (confidence ≥ config threshold) **or** in the top-k central concepts of their fine community (k and centrality measure in config).
- **detail:** all other anchored concepts. Concepts below the anchor stay untiered.
- **Sanity report:**
  - tier distribution;
  - % of core concepts with ≥ 1 principle link;
  - % of detail concepts within 2 hops of a core concept;
  - a list of orphan details.

## 8. Per-question mini-maps (Dynamic Learning Maps style)
For each question:
- **targets:** concepts and edges in its expected subgraph (M6);
- **proximal precursors:** 1-hop `prerequisite_of` parents plus the endpoints of `depends_on_edges`;
- **distal precursors:** 2 hops;
- **successors:** 1-hop `prerequisite_of` children.

Anchored concepts only, with a reason for each entry. Render it in the review app. **Blind check** for the pilot questions: the owner marks each precursor/successor as *valid / invalid / missing*.

## 9. Misconceptions as perturbations (reframes M8)
- M8 mining clusters contradicted items, then assigns a `perturbation_type` from the dominant `match_type` / chain-link match type:
  - substitution ← substituted_concept;
  - reversal ← reversed / reversed_link;
  - over-generalisation ← modality_error;
  - missing condition ← condition_error;
  - wrong category ← wrong_type involving `is_a` / node type;
  - wrong link type ← wrong_link_type.
- Store `asserted_edges` (the student-side triples) and `perturbs_edges` (the expert ones).
- `recurs_across_questions = true` if the same perturbation pattern (same perturbed concepts + type) appears in ≥ 2 questions. These are candidate "intuitive fragments".
- Link each misconception to the principle(s) of the concepts it perturbs.

## 10. New diagnostic outputs (M7)

### 10.1 SOLO-style level (deterministic; algorithm documented in ARCHITECTURE)
Definitions:
- `R` = the question's required edges (with weights).
- **Relevant expressed edges** `E` = student alignments with verdict `correct`, or `inaccurate` with match_type ∈ {partial_relation, family_match, part_type_error}.
- `G` = the graph formed by `E`, connected via shared concepts **and** correctly matched chain links.

Rules, applied in order:
1. **prestructural:** `E` is empty, or only irrelevant material.
2. **unistructural:** `|E| = 1`, or all of `E` touch a single required concept.
3. **multistructural:** `|E| ≥ 2` **and** (`G` has ≥ 2 components, **or** the question has required chain links and none are matched).
4. **relational:** `|E| ≥ 2`, `G` is one component covering ≥ `θ` (default 0.6) of the required weight, and ≥ 1 required chain link is matched where the question has any.
5. **extended_abstract:** relational **and** (≥ 1 correct link to a principle **or** a correct `valid_extra` edge generalising beyond the question's subgraph).

Contradictions don't change the SOLO level. SOLO describes structure; correctness is reported separately in `label_3way`. Store the evidence (components, coverage, which rule fired).

**Evaluation:**
- Spearman ρ between SOLO level and SAF score: tuned on train/validation, reported on the UA/UQ test splits;
- **blind human SOLO coding of 60 answers** (owner; stratified by SAF label; sheet shows the question, reference answer and student answer only) → weighted κ, confusion matrix, error analysis.

### 10.2 Other outputs
- **Knowledge-type profile:** weighted missing and contradicted shares by `knowledge_type`.
- **Integration score:** distinct fine communities (and principles) among correct `E`, divided by those in the question's expected subgraph.
- **Progression flags:** for each expressed target edge whose proximal precursor edges are all missing → flag.
  - Population-level **reversal rate** per question = the share of answers with ≥ 1 flag. Report it as an empirical check of the prerequisite layer (after Thompson & Nash 2022). Questions with high reversal rates point to prerequisite edges to review.
- **Class heatmap data:** per question, per expected edge, counts of expressed / missing / contradicted across all answers, as JSON for the demo (M9).

## 11. Optional: structure audit of the textbook (descriptive)
`cumap audit structure` → `reports/structure_audit_pd.md`:
- concepts **used before defined** (by section order);
- prerequisite pairs taught in reverse order;
- **prerequisite distance** (sections between definition and first use);
- the first appearance of each principle, and how many chapters link back to it;
- cross-chapter links per chapter;
- chapters with no links to other chapters;
- **new-concept load** per section (defined concepts per 1,000 words; spikes);
- **explanation depth** (the share of mechanism / cause / function edges vs taxonomy/property edges per section);
- confusable pairs (from M8) with **no** `contrasts_with` edge in the book;
- **constructive-alignment coverage:** the share of each question's required edges that the book teaches.

Add a caveat in the report: SAF students did not learn from P&D, so the audit can't attribute student errors to P&D. It is descriptive only. Optional validation: owner or supervisor review of 20 flags.

## 12. Tests (no network, no key)
- Registry patch: `instantiates` loads; excluded from `choice_set` for normal extraction; domain/range check (target must be a Principle).
- Leiden runs on a fixture graph with a fixed seed (deterministic).
- Summary evidence quotes are verified.
- Candidate filter rejects label-only or single-mechanism statements (fixtures).
- Breadth metrics, Kendall's W, IQR, and the ranking score give known values on fixtures.
- Human Delphi round-1 sheets contain no LLM ratings, metrics or ranks; round-2 sheets show human medians only.
- Tier assignment and sanity metrics on a fixture.
- Mini-map construction on a fixture prerequisite graph.
- **SOLO rules:** one fixture per level, plus edge cases (contradictions present; no chain links in the question).
- Progression flags and the reversal rate on a fixture.
- Perturbation-type mapping from match types.
- Nothing writes to `data/gold/`.

## 13. Docs
- **`ARCHITECTURE.md`:**
  - layers table: add `principle` (relation `instantiates`);
  - node fields: `knowledge_type`, `tier`, `is_threshold`, `community_ids`;
  - new models: `PrincipleMeta`, `Community`, `QuestionMiniMap`; the reframed `Misconception`;
  - `DiagnosisRecord` additions;
  - the SOLO algorithm (§10.1) and the edge knowledge-type rule (§6).
- **`BUILD_PLAN.md`:**
  - add **M5.5 — Knowledge organisation** (§4–§8) after M5;
  - add the §10 outputs to M7 and the §9 reframing to M8;
  - add the heatmap to M9;
  - list the human steps (Delphi, 3 blind sheets, SOLO coding).
- **`CLAUDE.md`**, new rules:
  - "Principles are created only by the principle pipeline and approved by the human Delphi. Never add a principle by hand in code or prompts."
  - "Troublesomeness flags threshold concepts; it never decides what a principle is."
  - "SOLO level is structural; never let contradictions change it. Correctness lives in `label_3way`."
- **`DECISIONS.md`:** registry patch version; criteria C1–C6 and ranking weights; Delphi protocol; the final principle list with the approval date; SOLO θ; tier thresholds.
- **`PROGRESS.md`:** a CR-004 row with the verified numbers.

## 14. Acceptance checks
- All tests pass without network access or a key; `ruff` is clean.
- Reports exist:
  - `cr004_communities.md`;
  - `cr004_principle_shortlist.md`;
  - `cr004_principles_final.md`, with human W, LLM-vs-human ρ and external recall/precision with CIs.
- Every approved principle has a statement, ≥ 1 verified source quote, breadth metrics and an approval record.
- Tier sanity report: ≥ 90% of core concepts have a principle link (or the gap is explained).
- Blind-check results with Wilson CIs for `instantiates` precision and knowledge-type κ.
- M7 results include the SOLO level (ρ vs SAF score; κ vs the 60 human-coded answers), knowledge-type profiles, integration scores, the progression reversal rate per question, and heatmap JSON.

## 15. Cost and time
**API cost** (estimate at CR-001 list prices; confirm with dry runs):

| Item | Estimate |
|---|---|
| Community summaries (~30–60 communities, strong) | $2–5 |
| Section / chapter / book summaries | $2–5 |
| Candidates | ~$1 |
| Provisional + final `instantiates` linking (~1–2K concepts, bulk with escalation) | $5–15 |
| LLM panel (≈25 items × 4 panellists × 2 rounds, including ceiling) | $5–10 |
| Knowledge type (bulk) | $1–2 |
| **Total** | **≈ $20–40** |

Use `--dry-run` for every step; `--batch` where possible.

**Owner time:**
- Delphi: 2 rounds ≈ 1.5 h (supervisor ≈ 1 h);
- `instantiates` check ≈ 30 min;
- knowledge type ≈ 20 min;
- mini-maps ≈ 30 min;
- SOLO coding of 60 answers ≈ 1.5 h;
- **total ≈ 4–5 h.**
