# Prompt to paste into Claude Code (CR-006)

Put these into the repo first:
- `docs/change-requests/CR-006-knowledge-sphere.md`
- `configs/organisation.yaml`

Then paste the text below. It slots into CR-005: build the tooling any time after the CR-005 snapshot writer exists, and run it after CR-005 STOP 3.

---

We're applying CR-006 (knowledge sphere). After each chapter, the graph reorganises so that important concepts move to the centre. This adds a sphere view to the CR-005 demo report. It is structure only, with no API calls. Read these in full first:
- `docs/change-requests/CR-006-knowledge-sphere.md`
- `configs/organisation.yaml`
- `CLAUDE.md`, `docs/DECISIONS.md`, `docs/PROGRESS.md`
- CR-005 (snapshot format, report builder, label-source tags) and CR-004 §4 and §7 (the community and centrality code to share)

Then:

1. **⛔ STOP 1:** in 10 lines or fewer, tell me:
   - what already exists (snapshot format, graph library in the report, any community/centrality code);
   - what you'll build;
   - the libraries you'll add;
   - confirmation that this makes no API calls.

   Wait for my OK.
2. Build §3–§10 as tested tooling on fixtures. One commit per step, prefix `CR-006:`. Don't let this delay CR-005's STOP 2 or STOP 3.
3. After CR-005 STOP 3, run `cumap kg organise` on the P&D ch. 1–3 snapshots → **⛔ STOP 2**:
   - top-15 per chapter (raw vs adjusted, side by side);
   - the background-vocabulary list and the unlinked count;
   - core–periphery fit vs null;
   - stability;
   - the 10 biggest movers, with the edges that moved them.

   I'll choose the radius basis and any overrides.
4. Add the sphere view and charts to the demo report, plus static figures → **⛔ STOP 3**: screenshots of the sphere at the start and at ch. 1, 2 and 3. Do this before CR-005 STOP 4.
5. Optional, if time allows: the 40-concept face-validity sheet → **⛔ STOP 4**.

Rules:
- `kg organise` never modifies content snapshots.
- Rings are not tiers; never delete or demote a concept because of its ring.
- Principles are never pinned to the centre.
- Weights are fixed before the face-validity check and never tuned on it.
- Every chart carries provenance and a label-source tag. Always show the "no clear core" banner when the null check fails.
- Never write to `data/gold/`.
- If time is short, follow §18. Principle mode (§11) waits for CR-004 STOP C.
