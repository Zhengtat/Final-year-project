# CR-026 — gpt-6-luna as the default, gpt-6-sol only on escalation

**Status:** done 2026-10-22 (owner instruction after CR-025). Branch `cr-026-luna-default`.

- **Profile:** `configs/models_luna_default.yaml`: `strong` and `bulk` = gpt-6-luna (efforts as before: medium / low), new tier `escalate` = gpt-6-sol, escalation from `[strong, bulk]` to `escalate` (triggers unchanged: schema error, confidence < 0.6, failed evidence check; one retry). `ceiling` (gpt-6-astra, opt-in) untouched.
- **Environment:** local `.env`: `OPENAI_MODEL_STRONG=gpt-6-luna`, `CUMAP_MODELS_CONFIG=configs/models_luna_default.yaml` (env model variables win over a profile, so both are set). `.env.example` documents it. The o4-mini profile of CR-023 is no longer selected.
- **Code:** `EscalationConfig.from_tier` may be a list; the client escalates a call whose tier is in it. Tests force the baseline models whatever `.env` says.
- **Limits:** calls that already opt out of escalation (concept loop, CR-014/015 stages, rescue) stay on luna; the strong-tier work of the pipeline (canonicalisation, relation classification) now runs on luna first. Evidence: CR-025 (luna both tiers relation F1 0.114 at $0.18 vs sol 0.154 at $3.63, single run, 6 dev papers). Results made under this profile are not comparable with earlier runs unless the profile is named.
- **Baseline restore:** remove `CUMAP_MODELS_CONFIG` and set `OPENAI_MODEL_STRONG=gpt-6-sol`.
