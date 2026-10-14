# CR-017 — Final decision evidence (STOP 6)

Branch `cr-017-simplified-evaluation`, verified at commit `585ef3e` plus the STOP 6 commit. Model calls in all of CR-017: **0**. Spend: **$0**.

## Verification against the STOP 6 checklist
| Check | Result | Evidence |
|---|---|---|
| Five metric definitions frozen | PASS | `headline.py`, `hierarchy.py`, `configs/cr017_eval.yaml` have an empty diff since the STOP 3 freeze commit `2491018`; SHA-256 pinned in `tests/test_cr017_final.py` (f335336a…, b1523a34…, 41100298…). |
| Tests | PASS | `uv run pytest`: **826 passed, 0 failed** (CR-017 adds 16 hierarchy + 14 headline + 5 scorecard + 5 final = 40 tests; CR-013 explorer tests unchanged). |
| Lint | PASS for CR-017; repo-wide 12 pre-existing | CR-017 files clean on `ruff check` / `ruff format --check`. `ruff check .` = 12 errors, identical to mainline `abd1733` (clean-worktree check), all in CR-014/015/016 files untouched by CR-017. See open item 1. |
| Historical artefacts unchanged | PASS | 118 frozen files (`reports/cr012/**`, both gold sheets, all `cr012_*` run checkpoints) hashed before/after the replay: 0 changed. `git diff abd1733 HEAD` touches no file under `src/cumap/cr012`, `reports/cr012`, `data/gold`, `data/processed`. |
| Historical results reproducible | PASS | Re-running replay + both report generators gave byte-identical `headline_metrics.json`, `diagnostics.json`, `historical_replay.md`, `scorecard.md`. Strict F1, concept F1 and pair recall equal the frozen CR-012 values at E0–E4 (exact); SciNLP entity/relation micro equal at E0/E1/E3/E4. |
| No model behaviour changed | PASS | Changed non-test/non-doc files vs `abd1733`: new `src/cumap/cr017/*`, `configs/cr017_eval.yaml`, and the explorer's presentation files (`kg_explorer.html/.py`, `kg_explorer_eval.js`). No extraction, pair selection, relation, canonicalisation, organisation, prompt, LLM-client or frozen-prediction code. The only existing test edited is the isolation allow-list in `tests/test_cr012_stop1.py` (adds `cr017`, scoring-only; logged in DECISIONS). |
| Headline values reproducible from machine-readable outputs | PASS | `tests/test_cr017_final.py`: pooled per-section counts in `diagnostics.json` equal the headline tp/fp/fn (strict, concept, hierarchy) and pair-recall reached/denominator at all five levels; `scorecard.md` and the explorer payload are generated from the JSON (tests in `test_cr017_scorecard.py`). |
| No composite score; organisation separate | PASS | `composite_score: false`; scorecard sections HEADLINE / DIAGNOSTICS / AUDIT / ORGANISATION; organisation terms absent from headline blocks (tested). |

## Final headline (P&D-E2E held-out, 7 sections; descriptive section-bootstrap intervals)
| Level | Concept F1 | Ancestor Hierarchy F1 | Pair Recall | Relation Macro F1 ⚠ | Strict E2E Edge F1 |
|---|---|---|---|---|---|
| E0 (production-like) | 0.643 [0.589, 0.698] | 0.114 [0.077, 0.156] | 0.163 [0.139, 0.186] | 0.484 [0.302, 0.632] | 0.053 [0.030, 0.076] |
| E4 (oracle) | 0.996 | 0.699 | 1.000 | 0.342 | 0.470 |

Sequential reading (not additive): concepts are found (0.643), loss is large at hierarchy (0.114) and pair delivery (0.163), classification of the pairs that arrive is moderate (0.484 on 53 edges, 6 of 12 classes low-support), and the strict end result is 0.053. Full E0–E4 tables: `historical_replay.md`, `scorecard.md`. Oracle levels are conditional diagnostics.

## Caveats carried into closure
- Gold: P&D-E2E gold is single-annotator (owner-reviewed LLM prefill); hierarchy uses existing `is_a` gold only (no pseudo-gold; pilot section 1.5 NOT_EVALUABLE).
- Intervals over 7 sections are descriptive; none is shown for 1–2 sections.
- Relation Macro F1 is a headline metric with a mandatory low-support warning.
- SciNLP: mention-level analogues only; hierarchy NOT_EVALUABLE; Relation Macro F1 NOT_COMPUTED; never pooled with P&D.
- Scorecard UI verified headlessly (Node DOM stub), not visually in a browser.

## Open items for Research
1. Repo-wide lint: leave the 12 pre-existing CR-014/015/016 findings (recommended; editing frozen code risks hash drift) or lint-only commit with freeze re-verification.
2. SciNLP Relation Macro F1: define at mention level (needs per-class outcomes the frozen scorer does not retain) or keep NOT_COMPUTED.
3. Merge: on approval, `git merge --no-ff cr-017-simplified-evaluation` into `master` (mainline is `master`, not `main`) and tag `cr-017-complete`. Not done. CR-018 stays on hold pending its own STOP 1.

## Status
CR-017: **READY_FOR_CLOSURE** (all STOP 6 checks pass; merge awaits Research).
