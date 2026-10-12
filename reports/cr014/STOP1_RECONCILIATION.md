# CR-014 STOP 1 — reconciliation report (for Research)

Branch `cr-014-recall-first-concepts` from tag `cr013-stop5-complete`. $0 spent, no LLM call, no held-out prediction, no change to research gates. Dry-run script: `src/cumap/cr014/stop1.py` → `reports/cr014/dry_run_candidates.json`. See also `contamination_audit.md`.

## 1. Repository state
- CR-012: closed, merged to `main` (21ffffa, tag `cr-012-complete`). CR-013: explainability only, final commit `deb20b3`, 769 tests, ruff clean; merge/push pending owner.
- Production concept pipeline (concepts_v4): generator G1 (`prompts/concept_generator/v4`, bulk tier gpt-6-luna) → rule verifier (Q1, F1–F6, C1–C5, M1–M4; max_iterations 1; ≤3 flagged items dropped without reprompt; per-section call budget 5) → pruner → canonicalisation → relations. Config `configs/concept_gvp.yaml` (`frozen-1`).
- **Discrepancy:** `frozen-1` pruner tau = 0.1 and no strict G-links; the P&D `slice3_c2` recipe runs tau 0 with strict G-links (rule `G-link-rejected`). U0 must name one; proposal: U0 = the exact recipe used for the CR-012 held-out (slice3_c2) with a hash of config.
- Selected CR-010 node outcome (docs/DECISIONS.md l.153–155): N1 (deterministic candidate-hint rescue, `cr010/candidates.py` + `concept_rescue/v1`; caps 20 one-token / 10 multi-token) is the sole confirmatory arm.
- Source text: `data/interim/textbook_sections.jsonl`, 64 sections, 216,451 words, 62 with `emphasized_terms` (1,206). No character offsets stored beyond section text; spans are recovered by longest-match (`expert_kg/mentions.py`).
- Cache: diskcache `data/cache/llm/cache.db` keyed (model, prompt_version, input hash). Cost estimator `llm/cost.py`; prices (`configs/default.yaml`): bulk $0.10/$0.50 per 1M in/out, strong $2/$10; ceiling unpriced.
- Trace schema (CR-013 `explain/trace.py`): Stage literal has no proposal/boundary stages; extension needed for CR-014 (see decisions).

## 2. Node-recall evidence (repo-recorded, IIR test 70 sections, CR-010 STOP 2)
| arm | P / R / F1 | one-token recall (exact) |
|---|---|---|
| N0 | 0.447 / 0.569 / 0.501 | 0.696 |
| N1 | 0.444 / 0.599 / 0.510 (+0.009, CI [+0.005,+0.014]) | 0.741 |
| N3 | 0.451 / 0.591 / 0.512 | 0.697 |
| N2 | 0.442 / 0.583 / 0.503 | 0.706 |
| N0 replication | 0.433 / 0.553 / 0.486 | 0.712 |
N1 rescue precision 126/270 exact. Gain is small: rescue recovers a minority of misses.

**Could not reconcile Research's quoted working diagnostics** (historical miss count, rescue candidate coverage, recovered misses, one-token share, anchored-vs-independent audit): the file `CR-014_Research_Handover_Recall_First_Concept_Extraction.md` is no longer in the package folder (searched). Please resend; the values above are repo-recorded only.

## 3. Coverage-veto audit (CR-014 §9 independence)
Mechanisms that can suppress a proposal after the generator: `not_mentions` suppress M1 hints (`verifier.py` ~349); rejected hints go to `rejected_keys` and are never re-offered (`loop.py` ~343–357); strict G-link rejection drops a mention without adding alias or concept (`runner.py` ~205–230; slice3_c2: 124 rejected vs 16 linked); ≤3 flagged items dropped without reprompt. Stage A proposers must therefore run **before and independent of** these vetoes; trace must log each veto.

## 4. Candidate mechanisms available ($0)
spaCy noun chunks, technical heads, headings, emphasised terms, acronym pairs, definitional patterns (`cr010/candidates._gather`). Not available: a compact span model. GLiNER feasibility is **not verified** (no install/network performed); treat U-arms needing it as not faithfully implementable until Research approves a dependency.

## 5. Dry-run counts and cost (fresh pool, 18 sections, 101,931 words)
- Deterministic candidates: 139–1,387 per section, ≈105–210 per 1k words (median ≈135); uncapped, 1–4 tokens.
- Generator pass ≈ $0.0033/1k words → whole pool ≈ **$0.34 per pass**; median section $0.018. A K-sample proposer over the 10-section pilot+held-out (~50k words) at K=5 ≈ $0.8; verifier/boundary LLM checks on bulk tier of the same order. Canonicalisation (not needed for node recall) ≈ $0.0874/section.
- Projected totals sit far below limits (pilot ≤$5, dev ≤$15, held-out ≤$10, hard cap $30); estimates are from measured rates, not a priced dry-run of the U-arms (their prompts do not exist yet).

## 6. RESEARCH DECISION REQUIRED
1. Resend the handover working numbers (item 2).
2. Define U0: slice3_c2 recipe (tau 0, strict G-links) vs `frozen-1` (tau 0.1).
3. Approve the fresh-pool correction (18 candidates, not 30) and the selection rule in `contamination_audit.md`; consider keeping Stage A/B dev on ch1–3 only.
4. Approve extending the CR-013 trace Stage literal (proposal, boundary) — observability only.
5. Decide whether GLiNER (new dependency, licence/runtime unchecked) is in scope.
