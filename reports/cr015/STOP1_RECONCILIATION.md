# CR-015 STOP 1 — repository reconciliation ($0)

Written for: Research. Audit only: **0 paid calls, 0 held-out runs, 0 prompt/model/threshold changes.** Branch `cr-015-precision-boundary-calibration`, created from `main` at `9ced3b4` (merge of CR-014, tag `cr-014-complete`). The merge also brought in the CR-013 explainability commits (CR-013 had never been merged to `main`; its final commit `deb20b3` is tag `cr013-stop5-complete`). Analysis code: `src/cumap/cr015/stop1.py` → `reports/cr015/stop1_analysis.json`. Contamination audit: `contamination_audit.md`.

## 1. CR-014 state
- Outcome (Research): scientific success, production adoption failed; production remains U0. STOP 1–5 complete; final STOP-5 commit `42419fa`; merged `9ced3b4`; tag `cr-014-complete`.
- Frozen V3 tag `cr014-v3-frozen` → `5ad4e10`; `reports/cr014/FREEZE_V3.json` records `git_commit` `879e7be8` (the commit before the freeze file was added) and SHA-256 hashes of every prediction-path file.

## 2. Frozen definitions recovered from the repository (not from prose)
| item | where | value |
|---|---|---|
| **U2 proposal union** | `src/cumap/cr014/union.py::build_section_union` (hash `7d111b7f…`), `proposal.py::u1_registry` (`5a068e30…`) | U1 deterministic subspans (1–4 words of noun/modifier runs ending in a noun or gerund, spaCy noun chunks, heads, headings, emphasis, acronyms, definitional patterns, "X of/to Y" phrases) ∪ the **raw iteration-0** output of the production generator; exact de-duplication; strings absent from the text dropped |
| **Overlap families** | `union.py::build_families` (line 140), `noun_runs` (line 71) | one family = one maximal noun/modifier run in a sentence with all U2 candidates inside it; identical (run text, member set) signatures de-duplicated; candidates outside any run get a singleton family |
| **Boundary stage (V3)** | `src/cumap/cr014/v3_core.py::run_v2` (line 118), prompt `prompts/cr014_boundary_repair/v1.md` (`912d831f…`) | families with ≥2 members go to the LLM (15 per call); decisions KEEP/EXPAND/SHRINK/SPLIT/REJECT with spans validated as verbatim, ≤6 words; single-member families pass through |
| **Verifier (V3)** | `prompts/cr014_concept_verifier/v2.md` (`c6f02918…`), `llm_stage.py` (`3579a3b8…`) | six verdicts per span, 25 per call, one-word candidates carry an evidence column; ACCEPT_NEW / LINK_EXISTING count as accepted |
| **Model / sampling** | `FREEZE_V3.json`, `configs/default.yaml` | bulk tier `gpt-6-luna`, reasoning effort low, **no sampling parameters**, no escalation, 6000-token output caps (runtime), disk cache keyed (model, prompt version, input hash) |
| **Config hash** | `configs/cr014_concept_extraction.yaml` | `b7983910…` |
| **Pruner** | not part of V3 | none (V3 has no pruner stage; the production pruner only appears in the V0 arm) |

## 3. Code paths asked about (exact locations)
- **Longest-match / nested placement:** `src/cumap/cr014/pilot_score.py::place` (line 53). Surfaces are placed longest-first and a span is kept only if it does not overlap one already placed (`all(b <= x or a >= y …)`, line 62); `nested=True` bypasses the overlap test. This is the pre-specified held-out scoring rule (production rule 17). It lives in the scorer, not in V3's accept/reject path — so what is "lost" is lost at **placement**, after acceptance.
- **Where over-long spans enter:** U2 candidates (`union.py`, up to 4 words) and boundary repair (`v3_core.py` lines 160–170: EXPAND/SHRINK/SPLIT may create spans of up to 6 words not in U2). The verifier then judges the span as given.
- **Boundary vs concepthood conflation:** (a) verifier verdict `REJECT_PARTIAL_OR_WRONG_BOUNDARY` sits in the same single-label output as `REJECT_NOT_CONCEPT` / `REJECT_GENERIC` (`prompts/cr014_concept_verifier/v2.md`, line 25); (b) boundary repair's `REJECT` decision (`reason no_concept`) is itself a concepthood judgement made in the boundary stage (`v3_core.py` line 162).
- **Where accepted concepts are lost at placement:** `place()` only (the verifier's accepted set is complete at that point).
- **Trace stages now present:** `explain/trace.py` `Stage` literal = CR-013 stages + `proposal`, `boundary_repair` (additive; `STAGES` unchanged). CR-015 needs `boundary_family`, `concept_validity`, `mention_placement`, `adjudication` (CR §25): additive, none exists yet.
- **Source offsets / scoring / cost / cache:** offsets are character offsets in the section text (`union.Cand.occurrences`); scorer `pilot_score.score` (mention-level span-exact) plus `heldout_score.py`; cost = `llm/cost.spend_from_log` on `data/logs/llm_calls.jsonl` with `configs/default.yaml` prices; cache = diskcache `data/cache/llm`.

## 4. CR-014 error counts reproduced from the saved artefacts
Re-running `heldout_score` on the stored outputs and the frozen gold reproduces the committed `reports/cr014/heldout_results.json` **exactly** (arms, nested view, taxonomy, bootstrap, gates all identical). Research handover figures match: mention P/R/F1 U0 0.749/0.508/0.605, V3 0.675/0.615/0.643; distinct-surface U0 P 0.715 R 0.472, V3 P 0.570 R 0.727; verifier-rejected 471, boundary-loss 260, over-long false positives 497. No mismatch with the handover found. Not-proposed count: 144 (29 with no overlapping candidate + 115 overlap-only).

## 5. Where the losses come from (new decomposition, CR-014 held-out, now development-only)
**Mention placement (the 1,929 "accepted surface, mention not placed" misses):** 1,925 are suppressed because a longer placed span covers them; 4 partly overlap; 0 unexplained. 1,391 of the 1,929 are mentions the gold marks `nested_valid`, 1,389 of them suppressed by a longer span. With `nested=True` placement V3's recall would be 0.880 (pre-specified nested view), so most of this loss is the placement rule, not the models.

**Verifier rejections of exact gold surfaces (471):** REJECT_PARTIAL_OR_WRONG_BOUNDARY **226**, REJECT_GENERIC 131, REJECT_NOT_CONCEPT 114. Almost half are boundary verdicts, not concepthood verdicts.

**Boundary-stage losses (260):** the gold surface was a U2 candidate but never reached the verifier. 150 were *replaced* by a different span in the same family (137 by a KEEP of another span that listed the candidate as a source, 12 SHRINK, 1 EXPAND) — nested concepts collapsed into one span; 51 were never named by any decision; 26 explicitly REJECTed as `no_concept`; 33 unclassified.

**Over-long false positives (497 placed spans containing a gold span):** lengths: 355 two-word, 105 three-word, 27 four-word, 10 one-word. Origins: 321 KEEP/correct_boundary + 65 KEEP/nested_both_valid (the boundary stage kept them), 95 SHRINK, 7 EXPAND, 87 with no boundary decision (U2 candidates passing through). So **386 of 497 (78%) were endorsed by the boundary stage itself**. Caution: gold is model-generated and often annotates the inner term where V3 keeps the outer one, so some of these may be annotation-convention disagreement rather than model error; this is not separable without human review.

## 6. Family volume, runtime and cost (active pricing: bulk $0.10/$0.50, strong $2/$10 per 1M tokens)
Measured on the CR-014 held-out (40,058 words): 8,615 U2 candidates, 6,663 families, 2,957 multi-member families sent to boundary repair, 421 V3 calls, ≈ $0.34, ≈ 77 min sequential (≈ 215 candidates and 166 families per 1,000 words).

Planned CR-015 development data (all exposed): CR-014 pilot + held-out = 10 P&D sections, 50.5k words (model-generated gold); IIR dev 13 sections, 18.0k words (non-exhaustive gold, secondary). Projected spend (bulk tier, from the above rates; A0 and B0 reuse cached CR-014 V3 outputs at $0):
| step | basis | projected | CR-015 soft target |
|---|---|---|---|
| Stage A (A1 placement-only $0; A2 family selector ≈ $0.45; A3 with hard-negative examples ≈ $0.8) | 50.5k words | ≈ $1.5 | ≤ $5 |
| Stage B (B1 ≈ $0.4; B2 ≈ $0.6; B3 optional ≈ $0.8) | same | ≈ $1.0–1.8 | ≤ $15 |
| Fresh held-out: U0 ($1.1/40k words) + CR-014 V3 ($0.5) + CR-015 candidate (≈ $0.5–1) | 25–40k words | ≈ $2–3.5 | ≤ $10 |
| Downstream STOP 5: two arms measured at $5.05 (U0) and $6.69 (V3) on 40k words | 25–40k words | ≈ **$7–12** | **≤ $5 — conflict, see decisions** |
Cumulative projection ≈ $12–19 against the $25 warning and $35 cap. Runtime is the real cost (sequential calls: ≈ 1–1.5 h per 40k words per LLM arm).

## 7. Methodological blockers / flags (no method substituted)
1. **Fresh held-out set:** 8 untouched sections exist (see `contamination_audit.md`) but two are under 1,000 words; a pilot of 1–2 plus a held-out of 4 (6 usable sections) is feasible and not more. No larger fresh held-out exists in the parsed textbook.
2. **Gold provenance:** all P&D gold so far is `MODEL_GENERATED_DIAGNOSTIC`. The CR prefers human/owner-reviewed fresh held-out gold; nothing in the repository can produce that.
3. **Placement is a scorer rule:** 1,925 of V3's lost mentions are due to the longest-match rule used to score both arms. Any nested-aware placement in CR-015 changes the scoring definition; it must be frozen before the fresh held-out and U0 and V3 must be reported under both rules.
4. **STOP-5 cost contract:** the $5 soft target is lower than the measured U0 arm alone.
5. **Dev-set gold convention:** model-generated gold encodes one annotator's inner-vs-outer convention; tuning boundary behaviour to it risks fitting that convention.

## RESEARCH DECISION REQUIRED
1. Approve a fresh-benchmark plan within the 8 untouched sections (pilot 1–2, held-out 4, outcome-blind seeded draw) or return CR-015 to the owner for more source text. If approved, say who produces the gold and with what provenance (model-generated again, or human/owner-reviewed).
2. Approve scoring both arms under longest-match **and** nested-aware placement, with nested-aware placement frozen before the fresh held-out.
3. Raise the STOP-5 soft target (≈ $7–12 projected) or accept a smaller downstream comparison.
4. Confirm that the CR-014 held-out error analysis may be used for design (it is development-only now).
