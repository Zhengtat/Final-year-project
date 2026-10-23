# CR-014 STOP 3B — diagnostic extension: status and what is needed from the human

Written for: the project owner (annotation steps) and Research (status). Plan from the Research decision, in order:

| step | status |
|---|---|
| 1. human-audit the blind FP sample | **WAITING ON HUMAN** — `data/interim/checks/cr014/iir_fp_audit_blind.csv` (58 items; fill `valid_concept_yes_no_unsure`; arms are hidden and order shuffled) |
| 2. redraw/freeze the fresh manifest once | **DONE** — `configs/cr014_manifest.yaml` (cr014-manifest-2, sha256 `a61f559e…`), supersedes v1 (`7462e305…`). Redrawn once, before any prediction on any pool section; reason: v1 held-out was ≈54k words. Pilot carried over unchanged (4.1, 9.2); sealed held-out 4.2, 5.3, 6.1, 6.4, 7.2, 8.3, 8.4, 8.5 (≈40k words, ≤8200 words each, ≤3 per chapter); reserve 4.3, 5.1, 5.2, 6.2, 6.5, 8.1, 9.1, 9.4. No further redraw is permitted. |
| 3. exhaustively annotate the 2 P&D pilot sections blind | **WAITING ON HUMAN** — read `docs/annotation/cr014_concept_annotation_delta.md` (+ base `pd_e2e_codebook.md`), annotate from `data/interim/checks/cr014/pd_concept_pilot_text.txt` into `data/interim/checks/cr014/pd_concept_pilot_blind.csv`, then freeze a copy into `data/gold/` yourself (code never writes there). Do not look at any system output first. ≈10.5k words (4.1: 5,032; 9.2: 5,433). |
| 4. run frozen U0 and current V3 on the pilot sections | **READY, NOT RUN** — deliberately held until the pilot gold is frozen so annotation stays blind to system output. Scorer `src/cumap/cr014/pilot_score.py` (span-exact mention P/R/F1, one-token, boundary categories) is tested on a synthetic fixture. |
| 5. report span-exact P/R/F1 and boundary/error taxonomy | after 4 |

## Plan for step 4 (needs no further decision unless a deviation is noted)
- **V3 (current):** unchanged code/prompts (`cr014_concept_verifier` v2, `cr014_boundary_repair` v1, bulk tier gpt-6-luna, config `cr014-stageB-1`) on U2 = U1 ∪ raw iteration-0 LLM proposals for 4.1 and 9.2. The raw LLM source needs a generator pass on those sections; I will use the production generator prompt (`concept_generator` v4, G1) with cards from the earlier-section node store, as the production run does. Estimated cost ≈ $0.05–0.10 generator + ≈ $0.10–0.15 V3 per ≈10.5k words (IIR dev measured $0.09 for V3 and $0.003/1k words for generation); well under the $5 pilot target. Preflight and `--max-usd` caps apply.
- **U0 (frozen production baseline):** the production P&D recipe (`slice3_c2`: pruner tau 0, strict G-links) on the same two sections through the CR-012 per-unit runner, with spans grounded from recorded evidence (`cr012/production_graph.py`). Needs the production node store state for earlier chapters; I will check this reproduces the recorded CR-012 procedure before spending anything and report if it cannot.
- **Caveats to be reported with the numbers:** two sections only; single run per arm; the P&D metric is mention-level span-exact and is reported separately from the IIR normalised-name metric.

## Decision still open from STOP 3
Eligible-arm question and options (strong-tier probe, two-sample verifier, close as NO_PRODUCTION_CHANGE) stay with Research; STOP 3B is diagnostic only and changes no gate.
