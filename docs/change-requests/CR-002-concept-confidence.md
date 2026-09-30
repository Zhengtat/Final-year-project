# CR-002 — Calibrated concept confidence scores

**Status:** approved by owner (Zheng Tat Wong), 2026-09-28
**Depends on:** CR-001 (registry v1, LLM tiers and escalation). Apply after CR-001 is complete.
**When:** steps 1–4 can run during M3. Steps 5–8 are needed before the M5 full run; step 9 plugs into M6/M7.

---

## 1. Why

Every extracted concept gets a **calibrated `concept_score`**: the estimated probability that the term is a real domain concept under the project's definition. The pipeline then uses that score to make decisions. A number the LLM just states isn't enough.

Evidence:
- **FACE** (Chau et al., IJAIED 2021): a logistic-regression concept probability let the authors trade precision against recall, from about 98% precision at 19% recall to about 97% recall at 37% precision (AUC 0.94). Different downstream tasks need different operating points.
- LLMs' **stated confidence is overconfident**, especially on specialist knowledge. **Agreement across several responses** and better aggregation reduce this (Xiong et al., ICLR 2024).
- For chat-tuned models, stated confidence can be better calibrated than token probabilities (Tian et al., EMNLP 2023). It is one useful signal, not the answer.
- **Agreement across repeated runs** is a strong, black-box signal for unsupported content (SelfCheckGPT, Manakul et al., EMNLP 2023).

What changes in behaviour:
1. **Two thresholds for two jobs.**
   - A *low* threshold decides which concepts student wording can be linked to (high recall).
   - A *high* threshold, or human acceptance, decides which concepts can anchor *expected* knowledge (high precision).
   - Noise in the expert graph must not turn into "the student is missing X".
2. **Review bands:** accept automatically / send to human review / reject automatically, with an audit sample from the automatic bands.
3. **Edge confidence** is capped by its weaker endpoint.
4. **Pruning and merge** decisions use the score.

**Keep three scores separate. Never merge them:**
- `concept_score`: is this a concept at all? (new)
- `criticality` / question weight: how much does it matter for a question? (existing)
- `link_confidence`: does this student phrase refer to this concept? (existing)

---

## 2. Order of work and stop points

Commit after each step with the prefix `CR-002:`.

1. Schema additions (§3)
2. Varied repeated extraction runs and vote counting (§4)
3. Feature extraction (§5)
4. Concept-label annotation sheet (§6)
   **⛔ STOP A:** the human labels the candidates.
5. Scorer training, calibration and report (§7)
   **⛔ STOP B:** the human approves thresholds and the model version.
6. Bands, review queue, audit sample (§8)
7. Edge confidence, merge and prune rules (§8)
8. Tests (§10) and docs (§11)
9. M6/M7 integration: two thresholds, `expert_uncertain` flag, ablation (§9)

No API calls are needed for steps 1, 3, 4 (except reusing cached extractions), 5 and 6. Step 2 makes the extra runs: dry-run first and tell me the estimated cost.

---

## 3. Schema additions

**`Concept`** (in `schemas/nodes.py`):

| Field | Type | Notes |
|---|---|---|
| `concept_score` | `float \| None` | Calibrated probability from the scorer. None until scored. |
| `score_components` | `dict[str, float \| bool \| int]` | The feature values used; kept so every score can be audited |
| `score_model` | `str \| None` | e.g. `concept_scorer_v1@<git-sha>` |
| `band` | `Literal["accept","review","reject"] \| None` | Set from the thresholds (§8). A human `validation.status` always overrides it. |
| `confidence` | *existing* | Keep for backward compatibility; set it equal to `concept_score` and mark it deprecated in the docstring. Log in DECISIONS. |

**`ConceptMention`** gains `run_index: int` (which varied run found it) and `stated_confidence: float | None` (the LLM's own number, used only as a feature).

**`ExpertEdge`** gains `confidence_components: {relation: float | None, source_concept: float | None, target_concept: float | None}`. The existing `confidence` becomes derived (§8.3).

**`Alignment`** (student side) gains `expert_uncertain: bool`: true when the matched or needed expert concept is below the anchor threshold and not human-accepted (§9).

**LLM-facing concept schema** adds `stated_confidence: float` (0–1), with an instruction to use the full range and reserve > 0.9 for terms that are defined or emphasised in the text.

---

## 4. Varied repeated extraction runs (agreement signal)

GPT-6 reasoning models don't take `temperature`, and our cache would return identical results for identical prompts. So agreement comes from **deliberately varied runs**, each cached under its own key:

- `run_index` 0: prompt `concept_extraction/vN` as is (the normal run).
- `run_index` 1: same prompt with the candidate list **shuffled** (fixed seed) and the section split at a different paragraph boundary (overlapping windows).
- `run_index` 2: a paraphrased instruction variant `concept_extraction/vN-alt` (same schema and same codebook content, different wording and order of instructions).

Add `run_index` to the cache key. Default `k = 3` on the **bulk tier**; configure as `concept_scoring.k_runs`.

**Features from the runs (per canonical concept, after merging duplicates):**
- `vote_share` = the share of runs in which any mention merged into this concept appeared;
- `found_by_gleaning_only` (bool);
- `stated_conf_mean`, `stated_conf_min`.

Rough cost: the concept pass is about $2 per full book pass on Luna, so ×3 ≈ $6. Show the dry-run estimate before running.

---

## 5. Features (`expert_kg/concept_features.py`)

Compute per canonical concept. Group names are used in the ablation (§7).

| Group | Features |
|---|---|
| `llm_stated` | `stated_conf_mean`, `stated_conf_min` |
| `agreement` | `vote_share`, `found_by_gleaning_only` |
| `linguistic` (FACE) | `ngram_len`, `is_unigram`, POS pattern of the head phrase (noun / adj+noun / noun+noun / other: one-hot), `has_acronym_alias` |
| `textual` (FACE) | `in_heading` (any mention), `emphasized` (bold/italic/term role), `defined_here` (any mention with role = defined), `in_glossary_or_index` (only if the textbook source has a glossary or index; otherwise drop the feature and log it), `n_sections_mentioned`, `max_section_freq`, `book_freq`, `max_tfidf` |
| `graph` | `semantic_degree`, `n_relation_families`, `has_taxonomy_parent` (computed **after** the relation pass; for training, use the pilot-section run) |

Use log-transforms for count features. No feature may use test-split SAF data.

---

## 6. Concept-label annotation (training and calibration data)

M3 expert subgraphs only contain *positive* concepts. The scorer needs negatives too.

`cumap gold sample-concept-candidates --sections <pilot sections> --target 500 --seed <seed>`:
- The candidate pool is the union of:
  - (a) every concept the LLM extracted from the pilot-question sections, across all runs;
  - (b) spaCy noun-chunk candidates from the same sections that **no** run extracted. Sample these so they make up about 30% of the sheet, which gives hard negatives and missed positives.
- Writes `data/interim/concept_labels/sheet.csv`. Columns:
  - `cand_id`, `section_id`, `term`, `context_sentence`
  - `label` (blank)
  - `note`

  **Don't show the scores or which run found the term** (to avoid biasing the annotator).
- Write `data/interim/concept_labels/codebook.md` with the definition (FACE's):
  - a concept is a single word or short phrase that represents an essential knowledge element *of the networking domain*, with a specific meaning in the field;
  - labels are `concept` / `not_concept` / `unsure`;
  - include 6 worked examples taken from the pilot sections.

**⛔ STOP A.**
- 👤 The human labels the sheet (about 2–3 hours for 500 items) and saves `data/gold/concept_labels/labels_A.csv`.
- Optionally, a second annotator labels a 100-item subset → `labels_B.csv`, used for Cohen's κ; it's recommended for the write-up.
- Concepts already in `data/gold/expert_pilot/*` are treated as positives automatically, but they're still listed in the sheet so the human can confirm them.

---

## 7. Scorer training and calibration (`expert_kg/concept_scorer.py`)

1. **Model:** scikit-learn `LogisticRegression` (L2, class-balanced) on standardised features. Compare it with FACE-style binned features if time allows. Drop `unsure` labels.
2. **Cross-validation:** 5-fold, **grouped by normalised term** so the same phrase never appears in both train and test (FACE did the same). Also report leave-one-section-out results.
3. **Calibration:**
   - reliability diagram (10 bins), expected calibration error (ECE) and Brier score on out-of-fold predictions;
   - if ECE > 0.05, wrap the model in `CalibratedClassifierCV` (isotonic if there are ≥ 300 labels, else sigmoid/Platt) and report before and after.
4. **Ablation** (table like FACE Table 3): each feature group alone, all minus each group, and all. Headline comparison: **`llm_stated` alone vs `agreement` alone vs all features.** This tests the research claim that stated confidence alone is overconfident and weaker.
5. **Threshold selection** (on out-of-fold predictions):
   - `t_anchor` = the smallest threshold with precision ≥ `target_precision` (default 0.90);
   - `t_link` = the largest threshold with recall ≥ `target_recall` (default 0.95).
   - If `t_link ≥ t_anchor`, report it and ask the human; the band logic assumes `t_link < t_anchor`.
6. **Outputs:**
   - `data/processed/models/concept_scorer_v1.joblib` + `.json` (features, coefficients, thresholds, CV metrics, git sha);
   - `reports/cr002_concept_scorer.md`: precision–recall curve, ROC AUC, PR AUC, ECE, Brier, reliability diagram, the ablation table, top coefficients, 15 hardest errors with context.

**⛔ STOP B.** 👤 The human approves `t_anchor` and `t_link` (or adjusts the targets). Write the approved values to `configs/default.yaml` under `concept_scoring:` and log them in DECISIONS.

---

## 8. Using the score in M5

### 8.1 Bands and review queue
- `band = accept` if `concept_score ≥ t_anchor`; `review` if `t_link ≤ score < t_anchor`; `reject` if `score < t_link`.
- Human `validation.status`: `accepted` → treated as score 1.0 for anchoring; `rejected` → excluded everywhere. The score itself is kept for analysis.
- Review queue in `app/review_app.py`:
  1. `review` band first, sorted by |score − 0.5| ascending (most uncertain first);
  2. plus an **audit sample**: a random 10% of `accept` and 10% of `reject` (at least 10 each).

  Record audit outcomes to estimate the error rate of the automatic bands, and report it in `reports/m5_expert_kg.md`.
- *Optional:* before human review, send `review`-band items to the strong tier for a second opinion. Record it as a feature for the next scorer version, not as a decision.

### 8.2 Canonicalisation and pruning
- When two candidates are near-duplicates and either is below `t_anchor`, prefer **merging** (add as an alias) over creating a new node.
- **Deprecation candidates** go in the M5 report, not auto-deleted:
  - `concept_score < t_link`
  - and `n_sections_mentioned ≤ 1`
  - and `semantic_degree ≤ 1`
  - and not an endpoint of any expected edge.

### 8.3 Edge confidence
- `edge.confidence = min(relation_conf, score(source), score(target))`, where `relation_conf` is the calibrated relation confidence if one exists, else the verification choice's stated confidence.
- Store the three parts in `confidence_components`.
- Human-accepted concepts count as 1.0.

---

## 9. Using the score in M6/M7

- **Expected subgraphs (M6 task 1):** only edges whose *both* endpoints pass the **anchor** rule (score ≥ `t_anchor` or human-accepted) can be `required` or `bonus`.
  - Concepts that appear in the human-reviewed gold propositions (`data/gold/propositions.jsonl`) count as **human-accepted** for anchoring, because the human has already confirmed them.
  - Log any such concept whose score was below `t_anchor` as a **scorer miss**. Report the count, and use these items as extra positives when retraining the scorer.
- **Student linking (M6 task 2):** candidate target concepts for linking = every concept with score ≥ `t_link` (plus human-accepted). This is deliberately wider.
- **Alignment (M7):** if a student edge links to a concept below the anchor rule, or the only matching expert edge involves one, set `alignment.expert_uncertain = true`. It is **never penalised**: it doesn't count as contradicted, missing or unsupported. It is reported separately.
- **Ablation (M7):** `--single-threshold 0.5` (every node treated the same) vs the two-threshold rule. Report:
  - diagnosis macro-F1 (primary set);
  - the **false-missing rate** on M3 gold: required edges diagnosed as missing although the gold student graph expresses them;
  - the number of `expert_uncertain` alignments.

---

## 10. Tests (no network, no key)
- Varied runs produce distinct cache keys; running the same `run_index` twice is a cache hit.
- `vote_share` is computed correctly after merging (a fixture with 3 runs and alias merges).
- Grouped CV never puts one normalised term in both train and test.
- Threshold selection on a synthetic score/label set gives the expected `t_anchor` and `t_link`.
- Band assignment, human-validation override and audit sampling (≥ 10 each from accept and reject).
- The edge confidence min-rule; human-accepted concepts count as 1.0.
- The anchor filter excludes low-score endpoints from required/bonus edges; the link filter includes them.
- `expert_uncertain` alignments contribute zero penalty in `DiagnosisRecord`.
- The candidate sheet never shows scores or run provenance.

---

## 11. Docs
- **`ARCHITECTURE.md`:**
  - §3 Concept table: add `concept_score`, `score_components`, `score_model`, `band`, and mark `confidence` deprecated;
  - §4b: add `confidence_components` and the min-rule;
  - §4c: add `expert_uncertain`;
  - new §7 "Concept confidence": the three-scores rule, the two thresholds, bands, audit.
- **`BUILD_PLAN.md`:**
  - M3: add the concept-label annotation task (STOP A);
  - M5: add scorer training, calibration, bands, review queue, audit, pruning report, and to the evaluation: PR curve, AUC, ECE, audit error rate;
  - M6: anchor/link thresholds;
  - M7: the single- vs two-threshold ablation and the false-missing rate.
- **`CLAUDE.md`**, new rule: **"Never use an LLM's stated confidence directly as a decision threshold. Decisions use the calibrated `concept_score` (or human validation status). Stated confidence is only a feature."**
- **`DECISIONS.md`:** concept scoring approach, thresholds (after STOP B), the `confidence` deprecation.
- **`PROGRESS.md`:** a CR-002 row with the verified numbers (AUC, ECE, thresholds, audit error rate).

---

## 12. Acceptance checks
- All tests pass without network access or a key; `ruff` is clean.
- `reports/cr002_concept_scorer.md` contains PR/ROC AUC, ECE (target ≤ 0.05 after calibration), Brier, the reliability diagram, the ablation table and the chosen thresholds.
- Every concept in a scored KG run has `concept_score`, `band` and `score_components`.
- The M5 report includes the audit error rate for the automatic accept/reject bands.
- In M7, the ablation table includes single- vs two-threshold results and the false-missing rate.
