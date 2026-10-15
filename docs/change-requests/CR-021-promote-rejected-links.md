# CR-021 — Promote a rejected link that names a more specific term

**Status:** name-only rule NOT adopted (STOP 1: correct 25/33, Wilson LB 0.59). Option 1, a measured LLM adjudicator, ADOPTED 2026-10-16 (held-out LBs 0.879 / 0.773; `reports/cr021/adjudicator.md`). See DECISIONS. Runs on `cr-018-boundary-identity`.
**Scope:** concept stage (`concepts_v4/runner.py`). No change to production until the adoption rule in §4 passes.

## 1. Problem
When the generator links a text form to an existing node and the strict G-link check (CR-009) cannot show it is the same node, the form is
dropped: no mention is recorded and no node is created. If the form is a real, different concept ("adapter-tuning" linked to "adapter"),
the concept is lost from the graph, and in SciNLP every one of its occurrences counts as a separate miss (13 + 2 occurrences, 21 relations
in 2021.acl-long.353).

## 2. What the rejected links are (140 in the retained runs)
| dataset | more specific | shortened | different words |
|---|---|---|---|
| P&D production `slice3_c2` | 30 | 26 | 68 |
| SciNLP dev (6 papers) | 2 | 4 | 4 |
| SciNLP test (3 papers) | 1 | 2 | 3 |
Only the more specific kind is safe to promote: "shortened" forms ("summarization" for "text summarization") would split one concept into
two, and "different words" are often generic ("hosts" for "node") or acronyms. Promoting all 140 was rejected for that reason.

## 3. Change (built, off)
`more_specific(surface, node)`: after bracketed parts are removed, the surface's lemma tokens strictly contain every lemma token of one of the
node's forms. When the switch `configs/concept_policy.yaml` `promote_rejected_links` is on, such a rejected link becomes its own node (type
of the node the generator chose; the generator's own mention and evidence, rule 24; logged `G-link-rejected-promoted`), or a mention of the
node that already has that name (`G-link-rejected-rerouted`). The original `G-link-rejected` record is kept. Other rejections are unchanged.

## 4. Adoption rule (pre-registered)
The dev data cannot measure this (P&D development sections have 0 cases, SciNLP dev 2), so adoption rests on an owner review:
- 👤 the owner marks every rule-selected row of `data/interim/suggestions/cr021_rejected_links_review.csv` (33 rows; local only, it contains
  CC BY-NC SciNLP text): is the surface a distinct, real concept? (optional: the 107 unselected rows, to estimate what the rule misses);
- adopt (switch on for new production runs) if the share of "distinct concept" among the 33 has a Wilson 95% lower bound >= 0.70;
- then measure on a paid re-run of the P&D production slice or SciNLP dev under a new run id before any graph replaces an existing one.

## 5. Acceptance (built part)
Switch off by default and every existing test unchanged; unit tests for the rule, the promotion, the reroute and the untouched target.
