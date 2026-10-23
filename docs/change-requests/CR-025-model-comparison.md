# CR-025 — Three models on the SciNLP dev split

**Status:** done 2026-10-22 (owner request: compare o4-mini and gpt-6-luna plus a third at another price point; the third is gpt-6-sol, the previous strong tier). Descriptive; no adoption decision. Branch `cr-025-model-comparison`.

- **Design:** one model for BOTH tiers per arm (luna, o4-mini, sol), SciNLP **dev** split (6 papers), E0, CR-021 recipe with production settings, new run ids `cr012_scinlp_cr025_<arm>_<paper>_E0`, escalation off. Test split not opened (rule 9). One run per arm; run-to-run variation not separated (the CR-019 / CR-021 dev runs are shown as reference rows for the spread).
- **Cost control:** dry run first, then the cheapest arm, then the other two; $2 per-paper cap. My pre-run estimate (about $1.0 for sol) was wrong: running sol on every tier costs $3.63 because the bulk-tier tasks are heavy; total spend about $5.8 (luna 0.18, sol 3.63, o4-mini 1.98 including two failed attempts).
- **o4-mini deviations (stated):** at the production settings it failed twice with truncated answers (hidden reasoning used the output cap: 768 of 800, then 2,368 of 2,400 even at 3x), so its arm uses effort low on both tiers and all output caps x3 (`configs/models_cr025_o4mini.yaml`). "o4-mini at the production recipe" cannot be run.
- **Outputs:** `reports/cr025/comparison.md` / `.json`, run logs, profiles `configs/models_cr025_{sol,o4mini,luna}.yaml`, code `src/cumap/cr025/`.
