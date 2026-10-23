# CR-023 — Lower-cost strong tier (o4-mini) and a before/after comparison

**Status:** profile built and verified (2026-10-22, owner instruction). The paid comparison run is NOT started; it waits for owner approval of the estimate below.
**Branch:** `cr-023-lower-cost-model` from `main`. Archive: branch `archive/cr023-models-pre-change`, tag `cr023-models-pre-change` (the exact pre-change commit).

## 1. Change
- New model profile `configs/models_cr023.yaml`, switched on by `CUMAP_MODELS_CONFIG=configs/models_cr023.yaml` (set in the local `.env`; commented in `.env.example`). It sets the **strong** tier to `o4-mini` (medium effort, $1.10 / $4.40 per 1M tokens, third-party list price, confirm on OpenAI's page).
- **Bulk stays `gpt-6-luna`** ($0.10 / $0.50): it is already about 11x cheaper than o4-mini, so moving it would raise cost. Ceiling unchanged (opt-in).
- `configs/default.yaml` is untouched because the closed CR-011 handoff pins its hash; unsetting the variable restores the baseline exactly. Tests force the baseline (`tests/conftest.py`).
- Verified with one real call through `LLMClient` (o4-mini, structured output, 42 in / 66 out tokens).
- Escalation (bulk -> strong) still works; it now escalates to o4-mini.

## 2. Saved baseline (nothing is overwritten; new runs use new run ids)
- Git: branch/tag above.
- Local archive (gitignored, `dataset_snapshots/`): `cr023-baseline-results-pre-model-change.tar.gz`, SHA-256 `7715f8f3788f34e8fdfbb6ae230bd13ca7e5305bc6e56921c88b9fa78300a98d`, 167 entries (file list in `cr023-baseline-files.txt`): P&D runs `slice3_c2` (production) and `slice3_c3`, SciNLP E0 runs `heldout`, `cr019dev`, `cr021dev`, `cr021test`, and `reports/cr012` frozen results, `cr017`, `cr019`, `cr021`, `cr022`. Redistribution: the SciNLP-derived runs follow that dataset's licence; do not push the archive.
- Key hashes: `slice3_c2/checkpoint.json` 54eb0f19..., `slice3_c3/checkpoint.json` fa17ee99....

## 3. Proposed comparison (not run)
Re-run with the profile under new run ids: P&D chapters 1-3 as `slice3_o4m` (the `slice3_c3` recipe: tau 0, strict G-links, pair budget 1100 + 50-pair sample) and the SciNLP dev and test E0 rebuilds, then score with the same scorers (five metrics, IDX-P1 / IDXR1-P1) beside `slice3_c3` / `cr021*`.
- **Estimate from logged tokens** (re-priced, $0): `slice3_c3` was $7.05 (strong 1.59M in / 0.35M out; bulk 1.20M / 0.50M); at o4-mini prices about $3.66. SciNLP rebuilds were $1.21, about $0.61. **Total about $4.3** (vs $8.26 at gpt-6-sol), within `max_usd_per_command` 15. Token use will differ with a different model (reasoning tokens), so expect +-30%.
- Rule 7: dry run, `--limit 20`, then full. Reading rule fixed now: descriptive; the report shows the five metrics and cost for both models side by side and names every difference; run-to-run variation is not separated (a same-model repeat would be needed, as noted in CR-021).
