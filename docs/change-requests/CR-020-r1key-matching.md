# CR-020 — One name equivalence for text matching (R1-key matching)

**Status:** done 2026-10-15 — ADOPT_R1KEY by the pre-registered rule ($0.11; `reports/cr020/results.md`). Runs on `cr-018-boundary-identity` (owner precedent of CR-019).
**Scope:** production text matching (rule 17). Adoption is decided by the pre-registered rule in §4; until then the default stays `token`.

## 1. Problem
The canonicalisation R1 key (`alias_rules.r1_key`) and the text matcher (`MentionMatcher`, rule 17) disagree on when two spellings are one name.
R1 collapses case, hyphens and spaces ("prefix-tuning" = "prefixtuning" = "Prefix tuning"); the matcher compares lemma tokens, so the
variants are invisible to pair generation, endpoint grounding, the scorers and the explorer. In SciNLP the variants are mostly GROBID
de-hyphenation artefacts ("prefix-\ntuning" -> "prefixtuning": 11 times in 2021.acl-long.353). Node merging is not affected (CR-019
follow-up diagnostic, DECISIONS 2026-10-15).

## 2. Change
`MentionMatcher(mode=...)`: `token` (unchanged) or `r1key` — a window of text tokens matches a form when both have the same R1 key; the window
never starts with an article; keys shorter than 4 characters must match a form token-for-token; the R1 acronym guard applies; longest match
and first-vocabulary-entry-wins are kept. The process-wide mode comes from `CUMAP_MATCHING` (default `DEFAULT_MATCHING = "token"`). The frozen
CR-012 scorer (`production_graph.grounded_spans`), the CR-019 token index and the Stage B passages pin `token`.

## 3. Experiment ($, dev data only)
Arms on the same concepts (the concept stage is not re-run):
- `TOKEN` = the existing E0 runs (SciNLP dev `cr012_scinlp_cr019dev_*_E0`, P&D development `cr012_pilot_1_5_E0`, `cr012_pilot_2_6_E0`).
- `R1KEY` = a copy of each (`cr020_r1key_<base>`) with pair generation, selection (same D3 budget rule `pair_budget(words, pool)`) and the
  production relation stage re-run under `CUMAP_MATCHING=r1key`.
A `TOKEN` re-selection on a copy must reproduce the base selected pairs exactly (determinism check, $0) before any paid call.
Cost: rule 7 (dry run, `--limit 20`, full); CR cap **$10**.

## 4. Pre-registered adoption rule (fixed before any R1KEY run)
Primary: SciNLP dev strict relation F1 under the CR-019 `IDXR1-P1` scorer (the same scorer for both arms, so only the production change
differs). Secondary: SciNLP dev pair-recall analogue and concept F1; P&D development Strict E2E Edge F1, Pair Recall and Relation Macro F1.
This is a consistency fix, so the rule is **non-inferiority**: adopt `r1key` as the production default if SciNLP dev IDXR1-P1 F1 does not fall
by more than 0.005 and P&D development Strict E2E Edge F1 does not fall by more than 0.01. Otherwise keep `token`. Test papers and P&D held-out
sections are not run. Adoption also amends rule 17 in CLAUDE.md and logs DECISIONS.

## 5. Acceptance
`token` mode bit-identical to before (all existing tests; CR-019 Stage A report unchanged); determinism check passes; spend within the cap;
the report names the arms, data and scorer.
