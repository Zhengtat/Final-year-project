# Kick-off prompt for Claude Code

Open a terminal in this folder, start Claude Code, and paste the prompt below. Put your OpenAI key in `.env` (copy `.env.example`) before M1; M0 doesn't need it.

---

You're starting the implementation of my final-year project. Before writing any code, read these files in full: `CLAUDE.md`, `docs/BUILD_PLAN.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/PROGRESS.md` and `configs/relations_v0.yaml`.

Then:

1. In 10 lines or fewer, summarise what the system does and the 5 rules from CLAUDE.md you think are most likely to be broken by accident. This checks you've understood the constraints.
2. Propose your plan for **Milestone M0** (files, packages, the LLM wrapper design including the mock backend and cache, the CLI layout). Wait for my OK.
3. Implement M0. Check the OpenAI SDK you install: confirm `client.responses.parse(..., text_format=...)` exists and how reasoning effort is passed; if anything differs from CLAUDE.md, adapt and log it in `docs/DECISIONS.md`. Run M0's acceptance checks, update `docs/PROGRESS.md`, and commit.
4. Continue with **Milestone M1** up to its 👤 HUMAN step:
   - download SAF and record the real split names and counts;
   - clone and pin the textbook repo, then parse it into sections;
   - generate the EDA report and the question→section coverage suggestions.
   Then stop and tell me exactly what to review: the coverage CSV and a shortlist of 5–7 candidate pilot questions with reasons.
5. While I review, you may do **Milestone M2** (schemas + registry logic + `cumap gold validate`), but treat `configs/relations_v0.yaml` as a draft until I approve it.

Ground rules:
- Never write to `data/gold/`.
- Tests must pass without network access or an API key.
- Use `--dry-run` and `--limit` before any real LLM run, and tell me the estimated cost before running anything that calls the API on more than 20 items.
- If something in the plan looks wrong or underspecified, raise it with me; don't quietly change direction.
