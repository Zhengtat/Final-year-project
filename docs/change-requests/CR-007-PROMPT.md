# Prompt to paste into Claude Code (CR-007)

On `main` (at `cr-006-complete`), create branch `cr-007-extraction-v3`. Put these into the repo:
- `docs/change-requests/CR-007-extraction-v3.md`
- `configs/registry-patches/CR-007-relations-v1.1.yaml`
- `docs/research/concept-extraction-llm-research.md` (from the project; skip it if already present)

Then paste the text below.

---

We're applying CR-007 (extraction v3: relation recall, registry v1.1, granularity, concept extraction v3) on branch `cr-007-extraction-v3`. Read these in full first:
- `docs/change-requests/CR-007-extraction-v3.md`
- `configs/registry-patches/CR-007-relations-v1.1.yaml`
- the CR-005 relation coverage audit (`reports/talking_points_facts.md` §5, and its DECISIONS entry)
- `CLAUDE.md`, `docs/DECISIONS.md`, `docs/PROGRESS.md`
- CR-005 §9 (cost safety) and CR-006 (organisation), since both are reused

Then:

1. **⛔ STOP 1:** in 10 lines or fewer, give me:
   - the plan;
   - the dry-run costs for §3 and §6.

   Also run the $0 diagnostics in §2 step 1:
   - (a) whether CR-005 spot-check failures came from substring mentions;
   - (b) CR-005 baselines: linked share by role, OTHER / NO_RELATION shares, and pairs dropped by the cap;
   - (c) owner merge errors vs embedding similarity.

   Wait for my OK.
2. Build in the order of §2. One commit per step, prefix `CR-007:`. Tests for each piece use fixtures and the mock backend.
3. Stop at:
   - **⛔ STOP 2:** the IIR dev ablation, the v3 chosen by the pre-registered rule, then v2 and v3 once each on the full test split;
   - **⛔ STOP 3:** the final registry v1.1 YAML + prompt diff for my approval, plus the pilot on the 114 OTHER pairs (≤ $2, pre-approved);
   - **⛔ STOP 4:** the ch1–3 re-run with the CR-005 vs CR-007 table (§7) and the blind sheets (§8);
   - **⛔ STOP 5:** precision CIs, gate decisions, the rebuilt report.

Rules:
- A registry change needs a new version and a DECISIONS entry. Nothing is changed in v1 in place.
- Tune only on IIR dev. Each prompt version runs on the IIR test split once.
- Every stage gets a preflight cost check. The budget check runs before every call. The hard cap for the whole CR is $20.
- Report examples are rendered from logged prompts.
- Never write to `data/gold/`.
- New `run_id` and `org_id`; old runs are kept.
- If time is short, follow §12.
