# CR-007 — Extraction v3: relation recall, registry v1.1, granularity, concept extraction v3

**Status:** approved by owner (Zheng Tat Wong), 2026-09-30
**Branch:** `cr-007-extraction-v3`, from `main` at `cr-006-complete`. Merge with `--no-ff` and tag `cr-007-complete`.
**Purpose:** fix what the CR-005 slice and the CR-006 sphere exposed, *before* paying for the full-book run.
**Scope:** P&D **ch. 1–3** (ch. 1 is added back) + IIR benchmark. Expert KG only.
**Depends on:**
- CR-005 pipeline and report;
- CR-006 organisation tooling;
- the CR-005 relation coverage audit (`reports/talking_points_facts.md` §5; `docs/DECISIONS.md`);
- the owner's merge marks (`data/gold/merges/`).

**Sources:**
- `docs/research/concept-extraction-llm-research.md` (add from the project if missing): multi-sample aggregation (Mohan et al. 2025), corpus consistency (DiSTER 2025), guideline-in-prompt (GoLLIE), hybrid/few-shot prompting (Kang & Shin 2025; ConExion 2025);
- `neuroscience-knowledge-research.md` ideas 1, 2, 6, 8, 9;
- QA4RE (filled option templates).

---

## 1. Why

| Evidence (CR-005/006) | Likely cause | Fix in this CR |
|---|---|---|
| 86% of concepts have no typed edge; the sphere covers 15–17% | OTHER and NO_RELATION outcomes; pair cap; missed mentions | §5 registry + prompt fixes; §4 mention matching; pair-cap review |
| 114 of 361 pairs → OTHER; 56 from the mechanism family; only 2 mechanism edges | The registry has no "actor handles thing" relation (27 cases), no topology relation (22), no encapsulation (part of 13) | §5 `acts_on`, `connected_to` (+ gated `identifies`, `encapsulates`, `trades_off_with`) |
| 8 OTHER were negated dependencies | The model avoids choosing a relation that the sentence negates | §5 prompt rule: choose the relation, and let the polarity qualifier record the negation |
| 8 OTHER were lists or scoping | OTHER was used where NO_RELATION fits | §5 prompt rule |
| The report shows filled options; the real prompt shows literal `{X}`/`{Y}` | The prompt departs from QA4RE's filled-template design | §5 fill templates in the prompt; §6 render report examples from logged prompts |
| Spot-check failures were mostly granularity (bit / bit rate / bit stream; switch / switching) | Probably substring matching ("bit" inside "bit rate") and type-blind merging | §4 longest-match mentions; type-aware merging; endpoint grounding check |
| 15 of 87 ch2 edges counted "late"; ch3 re-definitions tagged `defined` | Concepts are missed where they occur; the role is not aware of book order | §4 first-occurrence rule; `defined` → `refined` |
| Wrong merges were "similar but not the same" | Moderate-similarity band (SLIMM prediction) | §4 congruence-aware routing, checked against the owner's merge marks |
| IIR: recall is the weak spot (test lenient R 0.469); 1-gram recall 0.326 | LLM conservatism; labelling conventions | §3 concept extraction v3 experiments |

---

## 2. Order of work and stop points

Commit per step with the prefix `CR-007:`.

1. **⛔ STOP 1 — plan + $0 diagnostics.** In ≤ 10 lines:
   - the plan;
   - dry-run costs for §3 and §6.

   Plus these diagnostics (no API calls):
   - (a) for each CR-005 spot-check failure, whether an endpoint's surface form sat inside a longer concept mention in the evidence sentence ("bit" in "bit rate");
   - (b) CR-005 baselines:
     - linked share by role (defined / used / mentioned);
     - the OTHER and NO_RELATION shares;
     - how many sections hit the pair cap, and how many pairs were dropped;
   - (c) owner merge errors plotted against embedding similarity (the 43 marks).
2. **Scraper into `src/`** with tests and a gold-presence gate (§3.1).
3. **Concept extraction v3 on IIR** (§3).
   **⛔ STOP 2:** the dev ablation table, the version chosen by the pre-registered rule, then v2 and v3 each run **once** on the full IIR test split.
4. **Mention matching + canonicalisation v2** (§4), built and tested on fixtures.
5. **Registry v1.1 + relation prompt v2** (§5).
   **⛔ STOP 3:**
   - the final registry YAML and prompt diff for owner approval;
   - a pilot re-classification of the 114 CR-005 OTHER pairs (≤ $2, pre-approved), showing where each lands.
6. **Slice re-run, ch. 1–3** (§6): concepts v3 → canonicalisation v2 → relations v1.1 → snapshots → `kg organise` ($0) → report refresh.
   **⛔ STOP 4:**
   - the CR-005 vs CR-007 comparison (§7);
   - the blind sheets ready (§8).
7. After the owner's marks: precision with CIs and gate decisions for the gated relations.
   **⛔ STOP 5:**
   - the final registry version;
   - the report rebuilt;
   - CR-006 STOP 4 (face-validity sheet) offered.

---

## 3. Concept extraction v3 (IIR benchmark; tune on dev, test once)

### 3.1 Scraper
- Move the IIR scraper into `src/` (section-tree walk, intro-to-N.1 rule) with tests:
  - sections come from the tree, not the Next chain;
  - a fixture with subsection pages merges correctly.
- **Gold-presence gate:** a section below 90% gold presence is excluded and listed. It is never scored silently.
- Text stays local (gitignored). The report never quotes IIR beyond short snippets.

### 3.2 Experiments (dev: IIR ch. 1–3; prompts from v2)

| ID | Change | Notes |
|---|---|---|
| E1 | **Guideline in prompt:** a condensed version of FACE's annotation guideline (Wang et al. 2020, arXiv 2005.11422), written in our own words, with no gold terms | Tests the convention hypothesis |
| E2 | **Multi-sample aggregation:** 3 deliberately varied runs; report union and ≥2-of-3 vote | Feeds CR-002 §4 later: store the per-run outputs |
| E3 | **Consistency propagation:** a concept accepted in any section is also tagged in every other section where its surface form or alias occurs as a longest-match mention (§4.1). The propagated role is `mentioned`, source `propagation` | $0; post-processing |
| E4 | **1–3 few-shot examples** from dev sections other than the one being processed | Leave-one-section-out on dev |
| E5 | **node_type assignment + granularity rule** in the prompt: keep compound terms whole ("bit rate", "bit stream"); a device and its process are separate concepts ("switch" = Component, "switching" = Mechanism) | Needed by §4 anyway |

- **Combinations:** test E1–E5 singly on top of v2, then the best combination.
- **Selection rule (fixed now):** the highest **lenient micro F1 on dev**. If two are within 0.02, take the simpler one (fewer calls). Report exact micro, lenient micro and macro, recall by n-gram length, and precision by role.
- **Test:** run **v2 and v3 once each** on the full IIR test split (all chapters that pass the gate). v2 has not yet been run on chapters other than 4, 6 and 9, so this is its first run there.
- **Headline:** v3 exact micro F1 on the full test split, compared exact-to-exact with FACE.

---

## 4. Mention matching and canonicalisation v2 (no new API calls except merge decisions)

### 4.1 Longest-match mentions
- **Mention matching:**
  - concept mentions in text are found as **longest, non-overlapping spans at token boundaries** (case-insensitive, lemma-aware), over all canonical names + aliases;
  - "bit rate" wins over "bit", so "bit" is not also matched inside it.
- **Used by:** candidate-pair enumeration, consistency propagation, spread counts and first occurrence.

### 4.2 First occurrence and roles
- **`first_section` / `first_chapter`** = the first section, in book order, containing a longest-match mention with evidence. This replaces "first extracted", which fixes the late-edge effect.
- **`defined`** is kept only on the **first** definition in book order. Later `defined` tags become **`refined`**, with their evidence kept.
- **Description history:** the canonical description = the first definition plus an append-only `description_history` of refinements (section, quote). Nothing is overwritten.

### 4.3 Type-aware, congruence-aware merging
- **Different `node_type` → never `same`.** Log such pairs as `related` candidates for the taxonomy layer.
- **Congruence routing:**
  - use the STOP 1 plot of owner merge errors against embedding similarity;
  - if errors concentrate in a similarity band, candidates in that band never auto-merge; they go to the review sheet;
  - the band and its evidence go in DECISIONS;
  - with few errors, set the band conservatively and say so.
- **Unchanged:** the strict "same" rule, exact-string auto-merge and the `never_merge` / `force_merge` overrides.

---

## 5. Relations: registry v1.1 + relation prompt v2

### 5.1 Registry v1.1
- **Source:** apply `configs/registry-patches/CR-007-relations-v1.1.yaml` to create `relations_v1.1.yaml`. CR-004's `instantiates` patch becomes v1.2.
- **Core:**
  - `acts_on` (mechanism_process), with the qualifier `action_type` ∈ {send, receive, forward, transform, check, store, drop, generate, other};
  - `connected_to` (classification_structure; symmetric).
- **Gated:** `identifies`, `encapsulates`, `trades_off_with`. Keep only if the §6 re-run gives ≥ 5 instances **and** the owner marks ≥ 80% of up to 8 sampled instances correct. Otherwise remove them in the next version.
- **New node type:** `Identifier`.
- **New qualifiers:**
  - `corrects_intuition` (bool);
  - `intuition` (text). The qualifier pass sets these only when the text explicitly warns against a belief. This seeds the misconception layer from the textbook.

### 5.2 Prompt v2 (relation choice)
1. **Filled options.** Every option is the template filled with the actual concept names, in both directions for directional relations, plus NO_RELATION and OTHER (QA4RE-faithful). Log the exact prompt text per call.
2. **Negation rule.** "If the sentence states or denies a relation, choose that relation; the polarity qualifier records denial."
3. **Lists rule.** "If the two concepts are only listed or co-mentioned, choose NO_RELATION."
4. **OTHER needs text.** OTHER requires `other_description` and `other_suggested_label` (new schema fields, `X | None`).
5. **Family step.** Show each family with a one-line gloss and its relation names, so "handles a thing" routes to mechanism_process → `acts_on`.

### 5.3 Checks
- **Endpoint grounding.** Each endpoint must match a longest-match mention inside the evidence quote. Otherwise reject with the reason `endpoint_not_grounded`.
- **Domain/range** from v1.1. Report rejections per relation, so over-strict types are visible.
- **Pair cap.** Using the STOP 1 diagnostic: if the cap of 30 dropped pairs in many sections, raise it to 40, provided the §6 preflight stays within budget.

---

## 6. Slice re-run (P&D ch. 1–3)

- **Pipeline:** concepts v3 → canonicalisation v2 → pair enumeration (longest-match) → relations v1.1 / prompt v2 → structural checks → chapter snapshots ch1, ch2, ch3 → `cumap kg organise` (CR-006 config unchanged; radius basis adjusted).
- **Batch API** where the timeline allows. Preflight the exact relation cost as in CR-005 §9 before any relation call.
- **Report refresh:**
  - CR-005 tabs + CR-006 sphere on the new run;
  - the slider now starts at ch1;
  - worked relation examples are **rendered from logged prompts**, never re-rendered;
  - a new **"CR-005 vs CR-007"** panel (§7).
- **Old runs are kept.** New `run_id` and `org_id`.

---

## 7. Metrics: CR-005 baseline vs CR-007 (same sections for the comparison)

For CR-005 the comparison uses ch2–3 only; the ch1–3 figures are reported separately.

| Metric | Expectation (not a gate) |
|---|---|
| OTHER share of relation outcomes | ≤ 15% (from ~32%) |
| NO_RELATION share | Reported |
| mechanism_process edges | ≥ 20 (from 2) |
| Linked share of `defined` concepts | Reported; should rise clearly |
| Linked share overall (sphere coverage) | Reported (from 14%) |
| Edges per new relation; domain/range rejections per relation | Reported |
| Endpoint-grounding rejections | Reported (a direct measure of the granularity fix) |
| Late-counted edges | ≈ 0 after §4.2 |
| Spot-check precision (Wilson 95% CI) | Not worse than CR-005 |
| Merge precision (owner check, Wilson CI) | Reported |
| Core–periphery Δρ (both nulls), sphere stability | Reported |
| `corrects_intuition` edges | Count + list (seed for the misconception layer) |
| IIR full-test exact / lenient micro F1 (v2 vs v3) | Reported; v3 is the headline |

## 8. Blind sheets (STOP 4)

All sheets follow the CR-003 sheet rules and go in `data/interim/checks/`. The owner saves the filled copies to `data/gold/`.

- **Merges:** every non-trivial "same" merge, plus the band routed by §4.3.
- **Relations** (≤ 50 edges, about 25 min):
  - 20 edges stratified by family, as in CR-005;
  - 5 each of `acts_on` and `connected_to`;
  - up to 8 each of the gated relations;
  - hub-first: within each stratum, sample half from edges touching centre/inner-ring concepts.
- **Judgement per edge:** correct / incorrect / wrong-direction / wrong-granularity.
- **Rules:** no model labels shown beyond the triple being judged. Claude may pre-fill only if the sheet is labelled that way.

## 9. Tests (no network, no key)

- **Longest-match:** "bit rate" beats "bit"; no overlapping mentions; aliases are matched.
- **First occurrence and roles:** fixtures for first occurrence, `defined` → `refined`, and append-only `description_history`.
- **Merging:** a type mismatch never yields `same`; the congruence band routes to review.
- **Consistency propagation:** it tags later occurrences with role `mentioned` and source `propagation`.
- **Registry v1.1:** it loads and validates; `acts_on` requires `action_type`; symmetric relations are stored canonically; `encapsulates` conflicts with `part_of`.
- **Prompt v2:**
  - options are filled with concept names in both directions;
  - OTHER without `other_description` fails validation;
  - a negated sentence fixture expects relation + polarity = negated.
- **Endpoint grounding** rejects an edge whose endpoint appears only inside a longer mention.
- **Report:** the worked example is byte-identical to the logged prompt.
- **Scraper:** the tree walk and the gold-presence gate.
- **Hygiene:** nothing writes to `data/gold/`; the HTML stays offline.

## 10. Docs

- **`ARCHITECTURE.md`:** registry v1.1 (new relations, `action_type`, `corrects_intuition`, `Identifier`); mention matching; first-occurrence and role rules; description history; endpoint grounding.
- **`BUILD_PLAN.md`:** add **M5.0c — Extraction v3 (CR-007)**; note that the full-book run (M5) uses the v3 pipeline.
- **`DECISIONS.md`:** the registry bump (v1.1, and v1.2 for CR-004); gated-relation outcomes; the selection rule and the chosen concept prompt; the congruence band; the pair cap; the ch1 re-inclusion.
- **`CLAUDE.md`**, new rules:
  - "Report examples are rendered from logged prompts."
  - "Concept mentions use longest-match spans."
  - "`defined` marks only the first definition in book order."
- **`PROGRESS.md`:** a CR-007 row with the §7 table and the run and org IDs.

## 11. Cost and time (estimate; confirm with dry runs)

| Item | Estimate |
|---|---|
| IIR dev ablation (~6 variants, some 3-run) + full test split v2 and v3 | < $1 |
| STOP 3 pilot on the 114 OTHER pairs | ≤ $2 |
| P&D ch1–3 concepts v3 (24 sections; 3 runs if E2 wins) + canonicalisation | $2–4 |
| P&D ch1–3 relations (≈ 600–900 pairs × 3 calls, strong tier) | $8–13, or ~$4–7 with batch |
| **Total** | **≈ $8–18; hard cap $20** (per-call budget check as in CR-005 §9) |

**Owner time:**
- STOP reviews: ~30 min;
- merge sheet: ~10 min;
- relation sheet: ~25 min;
- optional CR-006 face-validity sheet: ~10 min.

## 12. If time is short
Drop things in this order:
1. E4 few-shot;
2. the gated `trades_off_with`;
3. the STOP 3 pilot (go straight to the re-run);
4. hub-first sampling.

**Never drop:** longest-match mentions, filled options, the endpoint grounding check, the preflight cost check, or the provenance labels.
