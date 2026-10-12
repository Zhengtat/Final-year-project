# CR-014 STOP 1 — contamination audit (exposed vs fresh)

Status: STOP-1 deliverable, $0, read-only. Selection below is a **proposal**, not frozen. No held-out prediction was made.

## Exposure matrix

| Data | Ids | How used | When exposed | CR-014 use allowed | Forbidden |
|---|---|---|---|---|---|
| P&D ch1–3 (24 sections, all) | 1.x–3.x | owner marks (CR-007…CR-010), failure analysis, few-shot/rule design, node-recall diagnostics | CR-007 → CR-010 | development, Stage A/B ablations, threshold choices | any "fresh" or held-out claim |
| CR-012 pilot | 1.5, 2.6 | pilot of end-to-end eval, gold seen | CR-012 STOP 3 | dev only (inside ch1–3) | held-out |
| CR-012 held-out | 4.4, 4.5, 5.4, 6.3, 7.1, 8.2, 9.3 | predictions made once, gold used once, frozen explanations (CR-013 overlay) | CR-012 STOP 4 (2026-10) | **none for tuning**; may be reported only as "previously exposed" | tuning, selection, fresh held-out |
| IIR dev | 13 sections | CR-009/010 development | CR-009 | dev (different domain) | held-out claims |
| IIR test | 70 sections (v3) | CR-010 STOP 2 held-out, run once, inspected | CR-010 | report-only context | tuning |
| SciNLP | CC BY-NC | CR-012 eval | CR-012 | not used in CR-014 | commit/push |
| Lexicon, few-shot bank (7 generic examples), alias rules | – | contain no ch4–9 text beyond generic examples (to be re-verified at STOP 2 by grep) | – | allowed | adding terms from fresh sections |

LLM pretraining exposure to the public CC BY 4.0 textbook cannot be controlled; reported as a limitation.

## Candidate fresh pool

Numeric sections in ch4–9: **25**; minus the 7 CR-012 held-out = **18 candidates** (101,931 words). Earlier estimate of 30 was wrong: ch4–9 contain only 25 numbered sections in `textbook_sections.jsonl`. Chapters 10+ are not in the parsed set.

Outcome-blind features (text only; see `dry_run_candidates.json`): words, emphasised terms, candidate density. Proposed selection rule (needs Research approval before any prediction): stratify by size tercile and chapter; exclude sections <1,000 words (5.1, 8.1); pilot = 2 sections with median size (candidates: 6.4, 8.3); held-out = 6–8 sections picked by seeded draw (seed fixed and logged before any CR-014 prediction) from the remaining ones, at most 2 per chapter. Selection uses no gold and no model output.

Risk: with 18 candidates and 7–10 needed, the held-out is a large share of the pool; a second exposure of any pool section (e.g. as Stage A dev) removes it. Recommend **Stage A/B dev run on ch1–3 (exposed) only**, so the 18 stay fresh.
