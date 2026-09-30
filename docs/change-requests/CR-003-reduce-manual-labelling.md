# CR-003 — Reduce manual labelling: borrowed human labels, automatic (weak) labels, check-only review

**Status:** approved by owner (Zheng Tat Wong), 2026-09-28
**Depends on:** CR-001 (registry v1, tiers, escalation) and CR-002 (concept scoring). Apply after CR-001. It can be applied before or after CR-002 is finished. If CR-002 is already done, only its training data and calibration set change (§5).
**Supersedes:**
- **CR-001 §7.3** (two-annotator relation-agreement test) → replaced by §6 here.
- **CR-002 §6** (500-item concept-label sheet) → replaced by §5 here.
- **CR-002 §7.1–7.3** training/calibration data → amended by §5.4 here.
- **BUILD_PLAN M3, M4, M5 human tasks** → reduced as listed in §9.

---

## 1. Why

The earlier plan needed about 18 hours of labelling from scratch plus a second annotator. CR-003 uses **human labels that other researchers already published** to evaluate each component, **automatic (weak) labels** for networking-specific training data, and **small, blind, in-domain checks** for calibration and to confirm results carry over to networking.

- LLMs are useful first-pass annotators (Gilardi et al., PNAS 2023: better than crowd workers on 4 of 5 tasks, ~$0.003 per item). They still don't replace human checking (Ziems et al., Computational Linguistics 2024: fair agreement with humans, below fine-tuned models; use them *with* humans).
- Snorkel (Ratner et al., VLDB 2017) combines noisy labelling sources into probabilistic training labels.
- Third-party human labels also answer the obvious examiner question ("who says your labels are right?") better than labels the author made alone.

**Principle:** every accuracy number the FYP reports must come from **human** labels, either borrowed (IIR, SciERC, SemEval-2013, SAF feedback) or checked by the owner (small blind samples). LLM or weak labels are used for **training and pre-filling only**, never as the sole ground truth for a reported metric.

---

## 2. Order of work and stop points

Commit after each step with the prefix `CR-003:`.

1. Loaders for external datasets and resources (§3). No API calls.
2. Mapping tables: SciERC → registry v1; SemEval-2013 5-way → 3-way (§4.2, §4.3).
   **⛔ STOP A:** show me both mapping tables and the dry-run costs for B1 and B2.
3. Benchmarks **B1** (concept extraction on IIR) and **B2** (relation classification on SciERC). Tune prompts on the dev portions only; run the test portions once (§4).
   **⛔ STOP B:** report B1/B2 dev and test results.
4. Automatic labels for networking concepts (§5): labelling functions, label model, training set.
5. Relation-registry agreement by cross-model comparison (§6).
6. Check-only tooling for M3 pilot graphs (§7).
7. Blind check sheets (§8): 120 concepts, 60 relations, 10 student answers annotated blind first.
   **⛔ STOP C:** sheets ready. I fill them in.
8. Calibration and agreement reports using my checked labels (§5.4, §6.3).
   **⛔ STOP D:** show me the reports and the proposed thresholds and relation merges.
9. **B3**: diagnosis on SemEval-2013 with no textbook graph, using reference answers only (§4.3). This can wait until M7.
10. Tests (§10) and docs (§11).

---

## 3. External datasets and resources (loaders)

Put everything under `data/raw/external/<name>/` (gitignored). Record the source URL, version or commit, licence, file hashes and counts in `data/raw/external/<name>/SOURCE.md` and in `DECISIONS.md`. **Check each licence before use. Don't commit third-party data.**

| Name | What | Where (verify) | Loader output |
|---|---|---|---|
| `iir_face` | FACE expert concept annotations per section of *Introduction to Information Retrieval* (16 chapters, 86 sections, 1,543 unique concepts) | PAWS Lab GitHub `PAWSLabUniversityOfPittsburgh/Concept-Extraction` (linked from the FACE paper). If section text isn't included, use the free online edition of IIR (Manning, Raghavan & Schütze; nlp.stanford.edu/IR-book) for local research use only; don't redistribute. | `data/interim/external/iir_sections.jsonl` (same `Section` schema as P&D) + `iir_gold_concepts.csv` (section_id, concept) |
| `scierc` | 500 AI abstracts; entities; 7 relation types; relation κ 0.678 | Official SciIE page (nlp.cs.washington.edu/sciIE: raw + processed + **annotation guideline PDF**), or the DyGIE++ download script | `data/interim/external/scierc_{train,dev,test}.jsonl` with sentences, entity spans and typed relation triples. Record the actual split sizes. |
| `semeval2013` | Beetle + SciEntsBank, 5-way labels | Hugging Face `nkazi/Beetle`, `nkazi/SciEntsBank` (CC BY 4.0) | `data/interim/external/semeval2013_{beetle,scientsbank}_{split}.parquet` |
| `cso` | Computer Science Ontology v3.4 (~26K topics; superTopicOf, relatedEquivalent, preferentialEquivalent) | cso.kmi.open.ac.uk (CC BY 4.0), CSV or OWL | `data/interim/external/cso_topics.csv` (label, aliases) + `cso_edges.csv` (source, relation, target) |
| `acm_ccs` | ACM Computing Classification System 2012 (SKOS/XML) | acm.org/publications/class-2012 (check terms of use) | `acm_ccs_concepts.csv` + `acm_ccs_broader.csv` |
| `wikidata` (optional) | Labels and aliases of networking concepts | Only via a cached, rate-limited SPARQL call. Skip if not needed. | cached JSON |

CLI: `cumap external fetch <name>`, `cumap external load <name>`, `cumap external stats`.

---

## 4. Benchmarks on borrowed human labels (no new labelling)

All benchmarks use the **same prompts, registry and code paths** as the networking pipeline. Only a domain string in config changes (e.g. `domain: "information retrieval"`). If a component only works with networking-specific prompt hacks, that's a finding to report.

### B1 — Concept extraction on IIR (FACE benchmark)
- **Split:** dev = 3 chapters (fixed list in config; choose chapters 1–3 unless the loader shows a better choice), test = the remaining 13. Tune prompts on dev only. Run test once per prompt version and record the run_id.
- **Metrics:** micro and macro P/R/F1 with **exact matching** (as FACE did), plus lenient matching (lemma/alias, or embedding ≥ threshold). Report 1-grams to 4-grams separately, since FACE found 1-grams hardest.
- **Comparison:** FACE's published results (Table 3: micro F1 0.76, macro F1 0.60; linguistic-only micro F1 0.65; CopyRNN 0.23; human MTurk 0.39). **Caveat:** FACE used 5-fold CV on the same book with supervised training, whereas ours is zero/few-shot on held-out chapters. State this difference in the report.
- **CR-002 link:** the IIR gold labels become training data for the concept scorer (§5.4).
- **Output:** `reports/b1_iir_concepts.md`.

### B2 — Relation classification on SciERC
- **Setting:** relation *classification given gold entity pairs* (as in QA4RE). Candidate pairs are the gold related pairs **plus** a matched number of unrelated in-sentence pairs (to test `NO_RELATION`). Use `choice_set` (CR-001 §3): family-first multiple choice with reversed options, `NO_RELATION` and `OTHER`.
- **Mapping** SciERC → registry v1. Read the SciERC annotation guideline PDF for argument order, then write the table to `configs/external_mappings.yaml`.
  **⛔ STOP A:** the human approves this table.
  Proposed default:

  | SciERC | Registry v1 (accepted set) | Family |
  |---|---|---|
  | USED-FOR | `has_purpose` (method → task) **or** `uses` (task/system → method, i.e. reversed) | function_means |
  | FEATURE-OF | `has_property` (entity → feature, i.e. reversed) | classification_structure |
  | HYPONYM-OF | `is_a` | classification_structure |
  | PART-OF | `part_of` (any part_type) | classification_structure |
  | COMPARE | `contrasts_with` (or `equivalent_to` counted as family-correct) | comparison |
  | CONJUNCTION, EVALUATE-FOR | not mapped: expected answer `NO_RELATION` or `OTHER` (both correct); reported separately | — |

- **Metrics:**
  - family-level accuracy and macro-F1;
  - relation-level accuracy within the accepted sets;
  - **direction accuracy** for directional relations;
  - `NO_RELATION` precision and recall;
  - confusion matrix at family and relation level.

  Tune on the SciERC dev split; report on test once. Don't compare directly with published end-to-end SciERC F1 (a different task); say so.
- **Output:** `reports/b2_scierc_relations.md`.

### B3 — Diagnosis on SemEval-2013, reference answers only (M7)
- **Mapping 5-way → project 3-way:** `correct` → correct; `partially_correct_incomplete` → incomplete; `contradictory` → contradictory. `irrelevant` and `non_domain` are excluded from the main table and reported separately.
- **KG-free mode** (`--kg none`): the expected subgraph is built only from the reference-answer propositions (propositions step → student extraction → alignment → diagnosis). No textbook KG. This isolates the student-side and alignment components and tests them on human gold labels outside networking.
- Use Beetle's "best" reference answers; SciEntsBank's single reference answer. Report on the test splits (unseen answers; unseen questions; unseen domains for SciEntsBank).
- **Output:** `reports/b3_semeval2013_diagnosis.md`.

---

## 5. Automatic (weak) labels for networking concepts (replaces CR-002 §6)

### 5.1 Candidate pool
As in CR-002 §6: LLM-extracted concepts from the varied runs, plus spaCy noun-chunk candidates, taken from **all** P&D sections, not only the pilot ones.

### 5.2 Labelling functions (`expert_kg/weak_labels.py`)
Each returns `CONCEPT`, `NOT_CONCEPT` or `ABSTAIN`.

| LF | Rule | Vote |
|---|---|---|
| `lf_cso_match` | normalised term or alias equals a CSO topic label | CONCEPT |
| `lf_acm_match` | matches an ACM CCS concept label | CONCEPT |
| `lf_emphasized` | emphasised (bold/italic/term) in P&D | CONCEPT |
| `lf_definition_pattern` | appears as X in "X is/are (a/an/the) …", "called X", "known as X", "referred to as X", "X, which is …" | CONCEPT |
| `lf_in_heading` | appears in a section heading | CONCEPT |
| `lf_acronym_pair` | appears as "long form (ACRONYM)" | CONCEPT |
| `lf_generic_head` | head noun in a generic list (approach, way, case, number, example, thing, problem, issue, time, part, kind, type, amount, result…) with no domain modifier | NOT_CONCEPT |
| `lf_stop_modifier` | starts with many/such/certain/various/several/other/same/new | NOT_CONCEPT |
| `lf_rare_unmarked` | `book_freq == 1` and not emphasised, defined or matched in CSO/ACM | NOT_CONCEPT |
| `lf_llm_consensus` | strong **and** ceiling tiers independently say concept (both yes → CONCEPT; both no → NOT_CONCEPT; split → ABSTAIN). Run it only on candidates where the other LFs conflict or abstain, to keep cost down. | ± |

### 5.3 Label model
- Use `snorkel`'s `LabelModel`. If the dependency is a problem, use a weighted majority with weights from LF accuracy on IIR, and log the choice in DECISIONS.
- Report per-LF **coverage, overlap and conflict**. After STOP C, also report each LF's **empirical accuracy** on the 120 checked items.
- Output: `data/processed/weak_labels/concepts_<run_id>.parquet` (term, section_id, p_concept, lf_votes).
- Don't use these as evaluation labels.

### 5.4 Concept scorer training (amends CR-002 §7)
- **Training data:** IIR gold labels (positives = gold concepts; negatives = IIR candidates not in gold) **plus** networking weak labels with p ≥ 0.8 or ≤ 0.2 (confident items only). Add a feature `source_domain ∈ {iir, networking}` only if it improves dev metrics; log the decision.
- **Calibration and evaluation set:** only the **120 human-checked networking items** (§8.1). Use cross-validated Platt/isotonic calibration on these 120 (`CalibratedClassifierCV(cv=5)` on a frozen base model). Report ECE and Brier with bootstrap 95% CIs.
- **Thresholds** `t_anchor` / `t_link` are chosen on the 120 checked items (cross-validated predictions). Report Wilson 95% CIs for precision at `t_anchor` and recall at `t_link`.
- Also report IIR test-chapter AUC, as a check that the model works on a second textbook.

---

## 6. Relation-registry agreement without a second human (replaces CR-001 §7.3)

1. **Borrowed human evidence:** B2's confusion matrix shows whether our method separates the 5 relations SciERC covers (`has_purpose`/`uses`, `has_property`, `is_a`, `part_of`, `contrasts_with`), measured against SciERC's human labels.
2. **Cross-model agreement on networking text:**
   - Sample 150 P&D sentences that mention ≥ 2 concepts, stratified to over-represent relations SciERC doesn't cover: `performs`, `triggers`, `precedes`, `causes`, `prevents`, `increases`, `decreases`, `requires`, `equivalent_to`.
   - The strong and ceiling tiers label them independently using the registry guideline block and `choice_set`.
   - Report Cohen's κ between models (relation and family level), the confusion matrix, and pairs confused in > 20% of cases.
3. **Human anchor (small, blind):** the owner labels 60 of the 150 items (stratified, no model labels shown).
   - Report human–strong and human–ceiling κ alongside model–model κ.
   - **Reading:** if human–model κ is similar to model–model κ and ≥ 0.6 at family level, the registry is usable. Relations below 0.6, or confused > 20%, become **merge/split proposals** for the owner to decide (candidates: triggers/causes, uses/requires, has_purpose/uses).
4. Output: `reports/cr003_relation_agreement.md`.
5. **Honest framing for the write-up:** this measures whether annotators (one human + two models) apply the registry consistently. It doesn't replace a multi-human agreement study; say so in limitations.

---

## 7. M3 pilot graphs in check-only mode

1. **Expert pilot subgraphs:**
   - Drafts are built from P&D sections **plus** the M4 gold propositions (the SAF reference answers were written by course staff).
   - Strong tier drafts; ceiling tier gives a second opinion on each edge (agree / disagree + reason).
   - Automatic checks: evidence substring; domain/range; `is_a` / `part_of` edges against CSO `superTopicOf` / ACM `broader` paths, flagged `external_support: yes | conflict | unknown`.
   - Output: suggestions YAML with `draft_status: both_agree | disagree | external_conflict`.
2. **Student pilot graphs (50):**
   - Strong-tier extraction.
   - For missing required edges, show a pre-suggested list from M4 silver labels (missing / contradicted propositions).
   - Show the SAF feedback **next to** the draft in the editor (the owner can see it; the diagnosis pipeline never does).
3. **Gold editor in check mode:**
   - per item: accept / edit / reject;
   - a mandatory "**anything missing?**" field per graph;
   - disagreements and `external_conflict` items first.

   The owner still saves to `data/gold/` (the agent never writes there).
4. **Measuring draft quality for free:** log each decision (accepted unchanged / edited / rejected / added). From these, report the **precision of the drafts** and the edit rate: `reports/m3_draft_quality.md`, with Wilson CIs.
5. **Recall check (automation bias guard):** checking drafts only catches wrong items, not missing ones. So **before** seeing any drafts, the owner annotates **10 student answers from scratch** (2 per pilot question, blind). The drafts for those 10 are then scored against the blind gold to estimate **draft recall**.

---

## 8. Blind check sheets (the only from-scratch human work)

The sheets show **no** model labels, scores or run provenance. Seeded, stratified sampling; saved templates go to `data/interim/checks/`; the owner saves completed sheets to `data/gold/checks/`.

1. **Concepts, 120 items:** stratified by current scorer band (40 low / 40 middle / 40 high; if scores don't exist yet, stratify by weak-label probability). Labels: concept / not_concept / unsure. Same codebook as CR-002 §6.
2. **Relations, 60 items:** from §6.3.
3. **Student answers, 10 blind:** from §7.5.
4. **M4 check, reduced to 120 answers** (from 150–200): stratified by question × SAF label, including both test splits. This remains the **primary in-domain evaluation set**. Checking against the written feedback is fast.
5. **M5 edge review, reduced to 60 semantic edges** (from 100): stratified by family. Taxonomy edges are checked automatically against CSO/ACM, and only conflicts go to human review.

Estimated owner time: 120 concepts ≈ 35 min; 60 relations ≈ 45 min; 10 blind answers ≈ 1 h; M3 checking ≈ 2.5 h; M4 check of 120 ≈ 2 h; M5 60 edges ≈ 45 min. **Total ≈ 7–8 h.**

**Sample-size note (for the report):** with ~100–120 items, a precision around 0.85 is estimated to about ±7 points (95% Wilson interval). Always report the interval.

---

## 9. Changes to the BUILD_PLAN human tasks

| Milestone | Before | After (CR-003) |
|---|---|---|
| M3 expert gold | Build 5 subgraphs from scratch | Check drafts built by two models with external taxonomy checks |
| M3 student gold | Annotate 50 graphs from scratch | 10 blind + 40 checked drafts (with feedback shown to the owner) |
| M3 relation agreement | 2 annotators × 100 | Cross-model 150 + human 60 + SciERC B2 |
| CR-002 concept labels | 500 from scratch | IIR gold + weak labels for training; 120 blind human items for calibration and evaluation |
| M4 check | 150–200 | 120 |
| M5 edge review | 100 mixed | 60 semantic (taxonomy checked automatically) |
| M7 evaluation | SAF only (+ optional Beetle) | SAF (primary) + **B3 SemEval-2013 KG-free** + B1/B2 component benchmarks |

---

## 10. Tests (no network, no key)
- Loaders parse small fixtures for IIR, SciERC, SemEval-2013, CSO and ACM into the documented schemas.
- The SciERC mapping handles direction (USED-FOR, FEATURE-OF reversal) and unmapped types correctly.
- Each labelling function has unit tests with positive, negative and abstain cases; the label model runs on a toy matrix.
- The benchmark runner guarantees dev/test separation (it refuses to tune on test; a test run is logged once per prompt version).
- Blind sheets contain no scores, model labels or provenance columns.
- Stratified samplers are deterministic with a seed and hit their quotas.
- The Wilson CI and bootstrap functions return known values on fixtures.
- Nothing writes to `data/gold/` (reuse the CR-001 guard).

## 11. Docs
- **`BUILD_PLAN.md`:** add a milestone **M2.3 — CR-003** (after M2.1/CR-001 and M2.2/CR-002); update M3/M4/M5/M7 per §9; add B1/B2 to the M5 evaluation and B3 to the M7 evaluation.
- **`ARCHITECTURE.md`:** new §8 "Evaluation data provenance": for every metric, whether its labels are *borrowed human*, *checked by the owner*, or *silver*. Only the first two may appear as headline results.
- **`CLAUDE.md`**, new rule: **"Reported accuracy numbers must come from human labels (borrowed or owner-checked). Weak or LLM labels are for training and pre-filling only."** Also: "Blind sheets must never show model outputs."
- **`DECISIONS.md`:** external sources and licences; the SciERC and SemEval-2013 mapping tables; the label-model choice; the reduced sample sizes and their CIs.
- **`PROGRESS.md`:** a CR-003 row with the B1/B2 numbers, LF stats and agreement results.

## 12. Acceptance checks
- All tests pass without network access or a key; `ruff` is clean.
- `reports/b1_iir_concepts.md` and `reports/b2_scierc_relations.md` exist, with dev tuning and a single test run, and caveats about comparability.
- A weak-label report exists (LF coverage/overlap/conflict, plus accuracy on the checked items after STOP C).
- The concept scorer is calibrated on the 120 checked items, with ECE/Brier CIs and thresholds with Wilson CIs.
- `reports/cr003_relation_agreement.md` has model–model and human–model κ and merge proposals.
- `reports/m3_draft_quality.md` reports draft precision and recall (from the 10 blind answers).
- The docs are updated as in §11.

## 13. Cost guard
Rough API cost at the list prices in CR-001 (my estimate; confirm with dry runs):

| Item | Estimate |
|---|---|
| B1 (~86 IIR sections × up to 3 varied runs, bulk tier) | ≈ $2–6 |
| B2 (SciERC dev + test, ~2–3K candidate pairs, strong tier) | ≈ $20–30 |
| Cross-model 150 items (strong + ceiling) | ≈ $10 |
| LLM-consensus labelling function on conflicting candidates (ceiling tier) | ≈ $10–25, depending on how many candidates conflict |
| M3 drafts with second opinions | ≈ $5 |
| **Total** | **≈ $45–75** |

Ways to reduce it:
- **`--batch` roughly halves the cost.**
- Run B2 on a 20-abstract dev subset first.
- Cap the LLM-consensus labelling function with `--limit`.
- For every step, run `--dry-run` and show me the estimate before a real run.
