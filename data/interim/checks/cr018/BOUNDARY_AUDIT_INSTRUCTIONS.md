# CR-018 boundary audit — instructions for the human annotator (frozen)

You will judge the **boundaries** of candidate term spans in short passages from *Computer Networks: A Systems Approach*. You are **not** judging whether something is an important concept, only whether a span has the right start and end as a technical term **in that sentence**. Please do this yourself, without a language model or any automatic help; the audit is only valid as a human judgement.

## What you see (one row per candidate span)
`section_heading`, the sentence before, the **marked sentence** (the target span is wrapped in `<<…>>`), the sentence after, `family_spans` (all the overlapping candidate spans in this spot, for comparison), and `target_span`. You are not shown any earlier annotation, system output or score.

## Fill three columns for every row
1. **q1_exact_complete_boundary** — `yes` / `no` / `unsure`: is the marked span exactly a complete technical term here — not too long, not cut short?
2. **q2_independently_meaningful** — `yes` / `no` / `na`: if the span sits inside a longer valid term, would it still be a meaningful technical term on its own in this context? Use `na` if it is not inside a longer valid term.
3. **boundary_label** — exactly one of:
   - `VALID_EXACT` — a complete term; no longer or shorter span is the real term here.
   - `VALID_NESTED` — a complete term in its own right **and** it sits inside a longer valid term (both are acceptable terms, e.g. "congestion control" inside "TCP congestion control").
   - `OVERLONG` — contains the real term plus extra words that are not part of it (modifiers, articles, verbs, wrappers).
   - `UNDERLONG` — a fragment of a longer term; the real term needs more words (e.g. only "control" where the term is "congestion control").
   - `INVALID_NESTED` — a substring inside a longer term that is **not** a meaningful term by itself.
   - `DESCRIPTIVE_WRAPPER` — a descriptive phrase around a term ("the problem of …", "a way to …") rather than a term.
   - `UNCERTAIN` — you cannot decide; use sparingly and say why in `note`.

Consistency: `VALID_EXACT`/`VALID_NESTED` ⇒ q1 `yes`; `OVERLONG`/`UNDERLONG`/`INVALID_NESTED`/`DESCRIPTIVE_WRAPPER` ⇒ q1 `no`; `UNCERTAIN` ⇒ q1 `unsure`. `VALID_NESTED` ⇒ q2 `yes`.

## Rules of thumb
- Several spans in one family can all be valid (a longer term and a shorter term inside it). Do not pick a single winner.
- Judge the span as it appears in the marked sentence, not in general.
- Case, hyphens and plural endings are not boundary problems.
- Do not judge importance or difficulty; a trivial but complete term is still `VALID_EXACT`.
- The `note` column is optional.

## Return
Save the sheet with the same columns (do not edit any other column) and create `boundary_audit_annotator.json` next to it: `{"annotator_id": "<your id>", "role": "human", "model_assistance": "none", "completed_on": "YYYY-MM-DD"}`.
