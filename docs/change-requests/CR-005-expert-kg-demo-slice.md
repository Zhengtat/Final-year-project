# CR-005 — Expert-KG demo slice for the supervisor meeting

**Status:** approved by owner (Zheng Tat Wong), 2026-09-28
**Purpose:** show real, honest progress on **building the expert knowledge graph**. No student answers.
**Scope:** a thin vertical slice of M5 plus CR-003's B1 benchmark, and one self-contained visual report. Three stories:
1. **Concept extraction, validated against the FACE dataset** (IIR textbook, borrowed human labels)
2. **Relation extraction** (registry v1, family-first multiple choice)
3. **How the graph grows chapter by chapter** (P&D chapters 1–3)

**Depends on:**
- CR-001 steps 1–3 (registry v1 + schemas + validator), plus the `choice_set` function from CR-001 §3;
- the CR-003 §3 loader for `iir_face` only.

It does **not** need CR-002 scoring, CR-003's other steps or CR-004. Anything built here must be the same code M5 will use later. This is an early slice of M5, not throwaway demo code.

---

## 1. Slice definition (in `configs/demo_slice.yaml`)
- **FACE/IIR:** the B1 dev chapters (3 chapters, as in CR-003 §4 B1). Optional: 3 more chapters from the test split, run **once**, if time and budget allow.
- **P&D:** chapters **1–3** (Foundation, Direct Links, Internetworking). They cover the pilot topics: encoding, sliding window/piggybacking, CSMA/CD, bridges/spanning tree. Process them **in book order, one chapter at a time**, saving a snapshot after each chapter.
- **Models:** bulk tier for concepts (with the 3 varied runs if CR-002 §4 exists; otherwise 1 run); strong tier for relations. Dry run first; show me the cost.

## 2. Pipeline pieces to build now (the M5 subset)
1. Candidate terms and stats per section (M5 task 1).
2. Concept extraction per section with the roles **defined / used / mentioned** and verified evidence quotes (M5 task 2). Same prompt family for IIR and P&D; only the domain string changes.
3. Canonicalisation against the growing global registry (M5 task 3), logging every merge decision (`same` / `broader` / `narrower` / `different`) with the candidates considered.
4. Relation extraction (M5 task 4, CR-001 method):
   - Stage A: candidate pairs with evidence;
   - Stage B: family-first multiple choice with reversed options, `NO_RELATION` and `OTHER`;
   - then the qualifier pass.
   - Earlier-chapter concepts mentioned in the section are included in the pairs, which is how cross-chapter edges arise.
5. Prerequisite candidates from **defined → used later** (M5 task 5).
6. Structural checks (M5 task 7): evidence substring, domain/range, cycles. Keep rejected items with reasons.
7. **Chapter snapshots:** after each P&D chapter, save `data/processed/kg/<run_id>/snapshots/ch<N>/{nodes,edges,merges,rejected}.jsonl` + `manifest.json`.

## 3. Metrics to compute

### 3.1 Concepts vs FACE (IIR)
- Micro and macro P/R/F1 with **exact** match (FACE's protocol) and **lenient** match (lemma/alias/embedding ≥ threshold). Report both.
- Breakdown by n-gram length (1–4) and by role.
- Comparison table against FACE's published results (micro F1 0.76, macro F1 0.60; linguistic-only micro F1 0.65; CopyRNN 0.23; MTurk humans 0.39), with the caveat written on the same slide/section: *FACE was supervised with 5-fold CV on the same book; ours is zero/few-shot on held-out chapters.*
- **Error analysis:** 10 false positives and 10 false negatives with context, grouped by likely cause (unigram, partial match, generic term, missed definition).

### 3.2 Relations (P&D ch. 1–3)
- Counts by relation, family and layer; share of `NO_RELATION` and `OTHER`; direction chosen as reversed (how often); qualifier use (negated, conditions, part_type).
- Check pass rates: evidence substring, domain/range, cycles. Show how many edges were rejected and why.
- **Validation (label clearly):**
  - *Preferred:* a quick blind owner spot-check of **30 edges**, stratified by family (sheet rules as in CR-003 §8: no model labels shown beyond the triple being judged; judge correct / incorrect / wrong-direction). Report precision with a Wilson 95% CI.
  - *If B2 (SciERC) is ready:* also report the dev-split family-level accuracy.
  - *If neither is available:* mark all relation numbers **"unvalidated LLM output"**.

### 3.3 Growth through chapters (P&D ch. 1→3)
Per chapter snapshot:
- concepts total / new / **reused from earlier chapters**;
- merges (aliases added);
- edges total / new;
- **cross-chapter edges** (endpoints first introduced in different chapters);
- prerequisite candidates (defined in an earlier chapter → used in this one);
- **forward references** (used before defined), as a sanity metric;
- the share of edges per relation family.

## 4. The visual report (the meeting artefact)
Command: `cumap demo build --run <run_id>` → `reports/demo/index.html`.

**Requirements:**
- **A single self-contained HTML file that works offline:** inline all JS/CSS (e.g. pyvis with `cdn_resources="in_line"`, or vendored Cytoscape.js/vis-network; charts via Plotly with the JS embedded).
- Also export **static PNG/SVG figures** to `reports/demo/figures/` for slides (matplotlib), one per chart and one per graph view.
- **Every chart and graph carries a provenance footer:** run_id, prompt versions, model tier, date, and a label source tag: `Borrowed human labels (FACE)`, `Owner spot-check (n=30)`, or `Unvalidated LLM output`.
- A header banner: **"Preliminary slice: P&D ch. 1–3 + IIR dev chapters. Not final results."**

**Tab 1 — Concept extraction & FACE validation**
- Metrics table + a bar chart of P/R/F1 (exact vs lenient) next to FACE's published numbers, with the caveat text.
- An n-gram breakdown chart.
- **Section viewer:** pick an IIR section, see its text with concepts highlighted (green = matched gold, amber = extra/false positive, red underline = missed gold). Hover shows the role and evidence.
- The same viewer for a P&D section (no gold), colouring by role (defined / used / mentioned).
- The error-analysis table.

**Tab 2 — Relation extraction**
- **Worked example panel** for 3 chosen sections: the sentence → the candidate pair → the multiple-choice options shown to the model (filled templates, reversed, none, other) → the chosen answer + qualifiers + evidence quote → the resulting edge. This makes the method visible.
- **Section graph:** concepts + edges for one section, edge colour by family, dashed for negated polarity, arrow for direction; click an edge to see its evidence and statement.
- Charts: edges by family/relation; check pass/reject reasons; spot-check precision with its CI (or the "unvalidated" label).

**Tab 3 — Growth through chapters**
- **Interactive graph with a chapter slider (1 → 2 → 3):**
  - node colour = chapter of first introduction;
  - node size = number of sections that mention it;
  - cross-chapter edges highlighted;
  - merged concepts show their alias count;
  - prerequisite candidates drawn as a separate toggleable layer.
- Line or bar charts per chapter: cumulative concepts; new vs reused; cross-chapter edges; merges; prerequisite candidates.
- A **concept timeline** for ~15 key concepts: first *defined* section vs later *used* sections (a dot plot along book order).
- Default filter: anchored/high-confidence nodes only (or top-N by mentions) to avoid a hairball. A toggle shows everything.

## 5. Stop points
- **⛔ STOP 1:** the plan (what exists, what's built new) + dry-run cost for the IIR dev chapters and P&D ch. 1–3.
- **⛔ STOP 2:** after the IIR dev run, show the concept metrics and the FP/FN examples. I may ask for one prompt revision (dev only).
- **⛔ STOP 3:** the 30-edge spot-check sheet is ready (if we're doing it).
- **⛔ STOP 4:** the report is built. Show me a screenshot of each tab and the figures list.

## 6. Tests (no network, no key)
- Snapshot writer/loader round-trip; the growth metrics give known values on a 2-chapter fixture (including a cross-chapter edge, a merge and a forward reference).
- The FACE scorer's exact and lenient matching on fixtures.
- The HTML builder produces a file with no external `http(s)://` script or style references (offline guarantee).
- Every chart function requires a label-source tag; missing tags raise an error.
- Nothing writes to `data/gold/`.

## 7. Docs
- **`BUILD_PLAN.md`:** add "**M5.0 — Demo slice (CR-005)**" before M5, noting it reuses the M5 code paths.
- **`PROGRESS.md`:** a CR-005 row with the FACE metrics, relation stats (and spot-check CI) and growth numbers, plus the run_id.
- **`DECISIONS.md`:** the slice definition and the chosen visualisation libraries.

## 8. Cost and time (estimate; confirm with dry runs)
- IIR dev chapters, concepts (bulk): < $2; optional 3 test chapters: ~$2–4.
- P&D ch. 1–3 concepts (bulk): ~$1–3.
- Relations (strong, family-first; the main cost): ~$10–20.
- **Total ≈ $15–30.**

Owner time: ~20 min spot-check, plus reviewing the report.
