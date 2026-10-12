# CR-013 FINAL: Glass-box process explainability for Expert-KG construction

**CR-013 changes explainability/observability only; it makes no accuracy-improvement claim.** It adds traceability, explanation and failure-localisation tooling around the frozen pipeline and frozen CR-012 evaluation; no prediction, prompt, model, threshold, budget, registry or score was changed.

Written for: Research, the supervisor and the examiners. Evidence: `reports/cr013/` (STOP reports, manifests, checks, screenshots), `data/processed/explainability/` (derived traces, gitignored) and `reports/kg_explorer/index.html` (generated, gitignored because it embeds CC BY-NC SciNLP text).

## 1. What was delivered (STOPs 1-4)

| STOP | outcome | report |
|---|---|---|
| 1 Trace audit ($0) | audited `slice3_c2` and one SciNLP run stage by stage; found that pair rank, the eligible pool, alias provenance, blocked merges, generator-call links and confidence were not retained | `trace_coverage.md` |
| 2 Trace model | `TraceEvent`, lineage DAG, deterministic renderer, `Why not?` localiser, coverage and gap reporting, REPLAYED pair-rank layer (exactly reproduces the retained selection) | `stop2.md` |
| 3 P&D explorer | Pipeline, Explain a section, Why not?, Rejected / lost, Stage snapshots, Debug trace table, Node and Edge journeys inside the existing explorer; three housekeeping gaps resolved without altering history | `stop3.md` |
| 4 Evaluation overlay | opt-in, separate-payload overlay over the frozen CR-012 outputs: failure map, gold comparison, earliest-failure explanations for SciNLP and P&D held-out | `stop4.md` |
| 5 Final | this report, final manifest, accessibility / performance / cross-engine checks, executed demo flow, tests and tag | this file |

## 2. Final trace coverage (production run `slice3_c2`, P&D chapters 1-3)

| CR section 12 metric | target | result |
|---|---|---|
| Final-object trace coverage: concepts | >= 95% | **1243 / 1243 = 100.0%** reach resolvable source evidence |
| Final-object trace coverage: edges | >= 95% | **528 / 528 = 100.0%** |
| Evidence resolvability | 100% | **10569 / 10569 = 100.0%** of evidence locators resolve; 8207 / 8378 (98.0%) quotes are also found in the section text they are attributed to (the rest: 54 verifier-rejected candidates and 117 strings that are verbatim only in other section(s), recorded as section-attribution gaps) |
| Explanation support rate | 100% | **100.0%** of 111936 dynamic values in 42511 sentences equal the trace field they were rendered from (JavaScript renderer equals the Python renderer on all 36,730 events) |
| Unknown honesty | 100% | **100.0%** (6201/6201 unrecorded fields shown as NOT_RECORDED) |
| Replay determinism | 100% | two builds give an identical trace hash: **True**; the replay layer is deterministic: **True** |
| Stage localisation accuracy (fixtures) | 100% | **11 / 11** fixtures (all ten codes plus a recovered edge) |
| Gold isolation | 100% | enforced by tests (section 5) |
| Read-only integrity | 100% | **True**: every audited source artifact is byte-identical before / after each build, now, and against the STOP-1 audit (section 8) |

Stage presence in the lineage of the final objects (% of objects): generator, canonicalisation, pruner, graph commit, organisation 100% for concepts and edges; pair generation / selection 100.0 / 99.6%, relation classification and validation 100% for edges; verifier events attach to a text unit, so they are counted unit-scoped (1243 of 1243 concepts come from a unit with verifier events).

### Known gaps (kept explicit; nothing was invented)

| status | stage | field | what is not retained |
|---|---|---|---|
| NOT_RECORDED | canonicalisation | alias_provenance | alias_provenance and merged_from are empty on every concept (legacy run); the v4-node link is an exact name join |
| NOT_RECORDED | generator | input_hash_link | generator calls are not linked to sections/iterations by input hash in the retained artifacts |
| NOT_RECORDED | relation_classification | confidence | no confidence or score is stored with relation decisions; rejected alternatives are only in the prompt text |
| NOT_RECORDED | canonicalisation | blocked_merges | no retained record of blocked merges (lexicon DIFFERENT veto) in this run |
| INCONSISTENT | graph_commit | edge_commit relrow:MP-3 | relation row 1150 is a misconception-verification edge (retained pair id prefix MP-, created outside pair selection) with outcome 'edge', but no snapshot edge has id MP-3; the reason it was not committed is not recorded |
| NOT_RECORDED | pruner | threshold | the pruner threshold is not stored in the artifact (run recipe: pruner off, tau 0) |

Object-level section-attribution gaps: 76 `SECTION_ATTRIBUTION_MISMATCH` and 2 `SECTION_ATTRIBUTION_AMBIGUOUS` (the retained section id of a pair differs from the section that contains its cited sentence; nothing was re-attributed). Anchor pairs (`AP-`) and misconception-verification pairs (`MP-`) carry no pool rank and say so. The per-pair selection phase, the model's rejected relation alternatives and any confidence were never retained.

## 3. Provenance classes

Every event carries a `layer`: **RECORDED** (17493 events) is read directly from a retained artifact with its source artifact and JSON locator; **REPLAYED** (17208 events) is recomputed by the frozen deterministic selection code (no model call) and is used only because it reproduces the retained selected pairs, their order, the retained 50-pair sample and the retained selection statistics exactly (an invalid replay would emit no ranks); replayed ranks are always described as *not originally recorded*; **JOINED** (2029 events) is an exact, run-scoped, deterministic join with its method and key stored. Join methods in use: `anchor_index_from_pair_id` (226), `equal_pair_id_unique` (528), `exact_name_or_alias_unique` (1275). Ambiguous or unresolved joins are not made; they are `AMBIGUOUS_JOIN` / `UNRESOLVED` gaps.

## 4. The explorer

Review (story and evidence depth) and Debug (audit depth) views over one offline page. New in CR-013 for the production P&D graph: Pipeline (11-stage ribbon, funnel, what each stage does / what happened / why it matters), Explain a section (10 steps from source text to the local final graph), Node and Edge journeys, Why not? (ordered checks, earliest observable failure, never a claim that a relation *should* exist), Rejected / lost items, Stage snapshots, and a Debug trace table with the audit fields of CR section 8.8.

## 5. Production / evaluation isolation

The production views and payload contain no gold, scorer output or frozen-run data. The evaluation overlay is a separate, opt-in mode with its own payload (`eval-gz`), its own JavaScript and its own Python module; it is not decoded until the user opens it, is banner-labelled *EVALUATION OUTPUT, gold-derived, NOT the production Expert KG*, and is dataset scoped (SciNLP held-out and P&D held-out are never pooled). Tests enforce: only `eval_adapter`, `why_not_eval` and `eval_report` read gold or import `cumap.cr012`; the production payload and trace JavaScript contain no overlay or gold symbol; the two blobs are separate; the overlay is undecoded until opt-in and leaves no evaluation text in production views.

**How the overlay must be read.** The overlay contains gold-derived evaluation observations, not ground truth about why the system reasoned incorrectly. Each code is CR-012's frozen attribution of an earliest observed failure location. For example, **P0** means that CR-012's frozen attribution determined that both endpoints existed but the relevant pair did not reach the required downstream stage. It is an earliest observed failure location, not an explanation of internal model intent, and it is not a decision rule for the production pipeline. Frozen headlines shown there: SciNLP E0 strict relation F1 0.050 (CI status NOT_EVALUABLE_SMALL_N, 3 documents); P&D held-out E0 strict F1 0.053 (descriptive small n, single annotator). CR-011 pre/post: NOT_APPLICABLE_NO_ADOPTED_TRANSFORMATION.

## 6. Verification

- **Tests:** full suite `769 passed in 39.33s`; lint clean on all CR-013 files.
- **Parity:** the JavaScript renderer equals the Python renderer on all 36,730 events; the JavaScript `Why not?` equals the Python localiser on 230 probed pairs.
- **Accessibility (automated):** axe-core WCAG 2.0 A/AA over 10 light-mode states (graph, all trace tabs, edge journey, Debug views, evaluation map) and 7 dark-mode states: **0 violations** after fixes made in this STOP (unlabelled filters, keyboard-unreachable scroll regions, three low-contrast colours). Also: header / main / aside landmarks, no unnamed buttons, no unlabelled inputs, no horizontal page scroll at a 200%-zoom viewport and at 390 px, reduced-motion respected, first Tab reaches an interactive element. Automated checks find only a subset of problems; no manual screen-reader audit was done, and the graph itself is a canvas (the detail panel, search and tables are its text alternatives).
- **Performance (headless Chromium, this machine):** page ready in 126 ms (5.96 MB file); first trace tab incl. decoding 19522 events: 314 ms; later tab renders 38-141 ms; five canvas redraws 104 ms; JS heap 12.7 MB.
- **Browsers:** full testing (behaviour checks, screenshots, axe, performance) was done in **headless Chromium 153 only** (14 / 14 production and 16 / 16 evaluation behaviour checks pass). A smoke test of the same main flows also passed in the Playwright **Firefox 155.0** and **WebKit 26.6** builds (page load, trace decoding, keyboard navigation, walkthrough, Why not?, journeys, canvas drawing, evaluation overlay, SciNLP mode). This is a smoke test of those builds; **we do not claim compatibility with released Safari or Firefox versions**. The page needs `DecompressionStream`, which these builds provide; browsers without it show a message and cannot open the trace tabs.

## 7. Demonstration and usability

- **Demonstration flow, executed once end to end through the real UI** (`tests/js/demo_and_tasks.py`, 13 steps, all asserted, 12.7 s scripted, screenshots `reports/cr013/demo/`): source section 3.3 -> generator -> verification -> pruning -> canonicalisation -> eligible pairs -> budget boundary -> relation decisions and one edge journey -> validation -> local graph -> Why not? -> global graph -> optional evaluation overlay. The talk track is `DEMO_SCRIPT.md`.
- **Descriptive usability face check: NOT_EVALUATED.** No 2-3 readers could be recruited within this work, so no responses exist and none were fabricated. `usability_face_check.csv` is the ready, blank sheet (10 tasks). Separately, a *scripted feasibility* run confirmed that the information each of the 10 tasks asks for is reachable in the UI (10 / 10); that is not evidence about how people experience the page, and no inferential statistics or accuracy metric is derived from it.

## 8. Read-only integrity manifest

`reports/cr013/final_trace_manifest.json` records: source run ids (slice3_c2, cr012_scinlp_heldout_P17_1058_grobid_E0); the SHA-256 of every source artifact (before and after each build, now, and as recorded by the STOP-1 audit: 9 + 3 artifacts compared); CR-013 code and configuration hashes (34 files, combined `ba89107c4c3c8e04…`); derived-trace hashes (`slice3_c2` trace `a6f2e2006142`, SciNLP trace `e2a0d92f8a6a`); the explorer hash (`d1e609fe824b1d1e…`, two builds identical: True); and the hashes of the read-only inputs of the evaluation overlay (unchanged: True). **All audited source artifacts remain byte-identical: True.**

## 9. Known limitations

1. **Crowded labels.** Dense regions of the main graph can still show overlapping labels. A purely visual mitigation was added (labels are placed greedily by importance and skipped when they would overlap), but selected, searched and hovered labels are always drawn, so overlaps remain around a selected hub. Graph semantics are unchanged; use search, filters or the tables when a region is dense.
2. Legacy-run limits (section 2): pair rank and the eligible pool exist only as a labelled replay for enumerated pool pairs; alias provenance, blocked merges, generator-call links, confidence and rejected alternatives were never recorded.
3. The SciNLP trace is partial (no snapshots, organisation or pair registry in the retained run) and contains CC BY-NC text, so derived SciNLP artifacts and the generated page stay local.
4. The overlay covers E0 only; P&D held-out gold has a single human annotator; SciNLP C0 / C1 are not applicable.
5. Descriptive usability face check not performed (section 7); cross-engine testing is smoke-level (section 6).

## 10. Reproduce

```
uv run python -m cumap.explain.build --run slice3_c2            # derived trace + replay
uv run python -m cumap.report.kg_explorer                       # offline explorer (reports/kg_explorer/index.html)
uv run python -m cumap.explain.final_manifest                   # integrity manifest
uv run pytest -q                                                 # tests (no network, no key)
```

## 11. What CR-013 does not claim

CR-013 changes explainability/observability only; it makes no accuracy-improvement claim. It does not claim that the Expert KG is accurate or validated, that any explanation reflects model intent, that the explorer is accessible beyond the automated checks reported, or that it works in browsers other than those tested.
