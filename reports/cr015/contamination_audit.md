# CR-015 STOP 1 — contamination audit

All CR-014 material is **development-only** for CR-015. "Labels inspected" = the gold annotation file was read by a person or by analysis code; "predictions inspected" = system output on that section was examined or scored. Exposure was checked three ways: the manifest history, the LLM call log (`data/logs/llm_calls.jsonl` run ids) and the full prompt log (`data/logs/llm_prompts.jsonl`, 134 MB: three 70-character snippets of each candidate section searched across every prompt ever sent).

| dataset / section | usage history | labels inspected | predictions inspected | gold provenance | allowed CR-015 use | held-out eligible |
|---|---|---|---|---|---|---|
| P&D ch1–3 (24 sections) | CR-007…CR-010 owner marks, rules, failure analysis, KG explorer | yes | yes | owner marks (human) | development | no |
| P&D 1.5, 2.6 | CR-012 pilot | yes | yes | CR-012 gold | development | no |
| P&D 4.4, 4.5, 5.4, 6.3, 7.1, 8.2, 9.3 | CR-012 held-out (once), failure analysis, explorer overlay | yes | yes | CR-012 gold | development | no |
| P&D 4.1, 9.2 | CR-014 pilot | yes | yes | MODEL_GENERATED_DIAGNOSTIC (ChatGPT, GPT-5.6 Sol) | development | no |
| P&D 4.2, 5.3, 6.1, 6.4, 7.2, 8.3, 8.4, 8.5 | CR-014 sealed held-out, run once, scored, error-analysed (also in this STOP 1) | yes | yes | MODEL_GENERATED_DIAGNOSTIC | development | no |
| IIR dev (13) / IIR test (70) | CR-009/CR-010 | yes | yes | IIR consensus gold (non-exhaustive) | development / report-only | no |
| IIR FP audit sample (58) | CR-014 diagnostic | labels LLM-generated | yes | LLM-generated | diagnostic only | n/a |
| SciNLP | CR-012 | yes | yes | CR-012 | not used in CR-015 | n/a |
| **P&D 4.3, 5.1, 5.2, 6.2, 6.5, 8.1, 9.1, 9.4** (CR-014 reserve) | never run, never annotated | **no** | **no** | none | candidate pool | **yes, verified** |
| P&D chapter-intro and front-matter units (`4-…` headings, foreword, preface) | not evaluation units | no | no | none | not used | no (not sections) |

Verification of the reserve pool: none of the 8 reserve sections appears in any LLM run id (`_4_3_` … `_9_4_`), none of their text appears in any prompt ever logged (0 hits for each), no gold or interim file names them, and the CR-014 manifest never opened them. The textbook is public CC BY 4.0 and the generating models may have seen it in pre-training; that is uncontrollable and is a stated limitation. Parsed P&D sections cover chapters 1–9 only: the 25 numbered sections in chapters 4–9 are now 7 (CR-012) + 2 (CR-014 pilot) + 8 (CR-014 held-out) + 8 untouched.

## Fresh candidate pool (proposal for Research; not frozen)
| section | words | note |
|---|---|---|
| 4.3 | 5,338 | usable |
| 5.1 | 957 | below the 1,000-word floor used in CR-014 |
| 5.2 | 12,799 | long (annotation burden) |
| 6.2 | 2,619 | usable, smallest annotatable |
| 6.5 | 9,160 | long |
| 8.1 | 662 | below the floor |
| 9.1 | 10,197 | long |
| 9.4 | 9,676 | long |
Usable six = 4.3, 5.2, 6.2, 6.5, 9.1, 9.4 (49.8k words). The spec's preferred split (pilot 1–2, held-out 4–6) can be met only as pilot 1–2 + held-out 4 (e.g. pilot 6.2 and 4.3; held-out four of 5.2, 6.5, 9.1, 9.4 ≈ 41.8k words), and there is no reserve left except the two tiny sections. Selection must be seeded and outcome-blind (chapter and word count only) and frozen before any CR-015 prediction; I have **not** drawn or frozen it.

If Research wants more than 4 held-out sections or a spare reserve, no further untouched section exists in the repository ("STOPPED_NO_FRESH_HELDOUT" does not apply at 4, but would apply above 6).
