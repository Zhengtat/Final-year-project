# Overnight handoff (2026-10-21 to 2026-10-22)

Written for: the project owner. $0 API spend; no model call; no merge, push or `*-complete` tag; nothing under `data/gold/` touched.

## Done

| # | Task | Branch · commit | Result |
|---|---|---|---|
| 1 | Concept-count funnel, right-hand panel of the KG explorer | `cr-018-boundary-identity` · `2c461ac` | Collapsible "How the concept count shrinks" above the details, on every P&D tab; follows the section chosen in the Pipeline tab; both graphs (`slice3_c2`, `slice3_c3`); SciNLP per paper from `v4_concepts.json`. Python reference `explain/funnel.py` equals the browser values for the whole book and all sections (parity test). Screenshots (local, the folder is gitignored): `reports/kg_explorer/node_funnel_light.png`, `node_funnel_dark.png`. |
| 2 | CR-022 Part A (SciNLP hierarchy and relation scoring) | `cr-022-scinlp-hierarchy-scoring` (from `cr-018-boundary-identity` after the funnel) · spec commit, `3e13b12`, `f83a402` | Gate PASSED (frozen test E0: concept F1 0.352, pair-recall analogue 0.545, strict edge F1 0.050, IDX-P1 0.195; per-document equality with the CR-019 scorer). 20 source files hash-identical before and after. Report `reports/cr022/part_a.md` (+ `.json`). Draft mapping `data/interim/suggestions/cr022_scinlp_to_v13_map.yaml` (all `draft`). Extra: labelled A1-A3 table in the explorer scorecard's CR-019 view. |
| 3 | Housekeeping | `cr-022-scinlp-hierarchy-scoring` | Full suite **869 passed**; repo-wide ruff **12 findings, identical to before** (CR-014/015/016 code and `tests/test_cr014_isolation.py`; untouched). Changed files are ruff-clean. PROGRESS has sections for CR-018 to CR-022 and the funnel; they were already accurate. |

### Funnel numbers (`slice3_c2`)
1,393 candidates -> 1,275 after checks (-118 rejected new concepts) -> 1,275 after filter (0 pruned recorded) -> 1,243 after merging (-32) -> 1,243 final -> 598 with at least one relation (-645). `slice3_c3`: 1,523 -> 1,401 -> 1,401 -> 1,352 -> 1,351 (**1 unaccounted**, shown in the panel) -> 600; 3 nodes there have no recorded mapping and are counted as their own concepts. Rejected *existing-mention* candidates (155 in `slice3_c2`) are mentions, not concepts, so they are not in the funnel.

### CR-022 Part A headline (SciNLP test, frozen run; FROZEN / IDX-P1)
Direct hierarchy F1 (H2) 0.037 / 0.114; surface-ancestor F1 (H2) 0.043 / 0.159 (H1: 0.053 / 0.204); relation macro F1 0.333 / 0.317 (8 and 10 classes; `partOf` low support). All hierarchy numbers are very small (4 to 5 true positives of 39 to 46 gold), so read them as direction, not as precision.

## Failed, skipped or reverted
- Nothing reverted. One test needed a guard exemption: `tests/test_cr012_stop1.py` now exempts `src/cumap/cr022` (as earlier CRs did for their evaluation code).
- **Not done:** CR-022 rescoring of E1 / E3-M / E4-M runs (spec lists them; their prediction path differs and was not wired; only E0 is covered). A3 cannot tell "never reached the classifier" from "classified none" at mention level (stated in the report).
- Playwright is not a project dependency; screenshots were taken with `uv run --no-project --with playwright`.

## Blocked: owner decisions needed (recommendations)
1. **CR-018 STOP 2** (human boundary annotation of the frozen 120-family sheet, `AWAITING_HUMAN_ANNOTATOR`) and **STOP 1 decisions D1 to D6** (`reports/cr018/STOP1_RECONCILIATION.md` section 8). STOP 3 must not start without them; Track B (STOP 4) also needs D4 (who labels cross-section identity gold, about 150 to 250 cases) and D5 (the $8 development cap). Recommendation: D1 option (iii) (V3 verifier and B1 concepthood-only, primary = B1), D5 approve $8, D4 option (i) unless you want to label.
2. **CR-021 follow-up:** should `slice3_c3` replace `slice3_c2` as production? The rebuild mixes the setting change with run-to-run variation (test down 0.195 -> 0.147, dev up). Recommendation: keep `slice3_c2` as production until a same-settings re-run (about $8, needs your approval) separates the two.
3. **CR-022 STOP 1:** (a) hierarchy set, `H2 {subclassOf, subtaskOf}` (spec default) or `H1 {subclassOf}` only; both are in the report. Recommendation: H2, with H1 reported beside it. (b) Run Part B? (paid, dev cap $10, test needs separate approval). Recommendation: decide after reading the Part A report; only about 60% of test relations are mappable. (c) Approve or edit the mapping draft into `configs/scinlp_to_v13_map.yaml` (`status: approved` per entry); `subtaskOf` and `enhancedBy` need your choice.
4. **Merge path:** CR-018 is incomplete but carries CR-019 to CR-021 and now the funnel and CR-022. Options: wait for CR-018; or cherry-pick CR-019 to CR-022 and the explorer commits onto `main` as their own CRs. Recommendation: the second, so CR-018 can stay paused without blocking the finished work.
5. **CR-017 lint policy:** the 12 pre-existing ruff findings remain. Recommendation: fix them in one small housekeeping commit, or add a per-file ignore.
