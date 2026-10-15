# CR-019 — Occurrence index and grounding-consistent evaluation

**Status:** specification approved by the owner 2026-10-15 ("yes, and then execute it"). Stage A ($0) executed in this CR; Stage B (paid pilot) stops for approval.
**Branch:** `cr-018-boundary-identity` (owner decision 2026-10-15: CR-018 is marked INCOMPLETE, paused at STOP 2 awaiting a human annotator; CR-019 runs on the same branch). Tag `cr-019-complete` when merged.
**Scope:** evaluation, reporting and the explorer. Stage A changes no model behaviour, extraction, pair selection, relation semantics or canonicalisation, and no frozen artefact.

---

## 1. Problem (investigation of 2026-10-15)

The production pipeline and the CR-012 scorer use two different answers to "where does a concept appear in the text?":

| component | where a concept appears |
|---|---|
| production pair generation (`expert_kg/relations.py:enumerate_candidates`) | every longest-match occurrence of its names (rule 17), same sentence |
| production endpoint grounding (`relations_v3.py`) | longest-match occurrence inside the evidence quote |
| CR-012 scorer (`cr012/production_graph.grounded_spans`, used by SciNLP and P&D scoring, attribution, CR-017, the explorer) | only occurrences inside the evidence windows of the mentions the **concept generator recorded** (about one per concept per text chunk) |

Measured effect on the frozen SciNLP held-out E0 runs (3 papers):

1. **90 of 111 predicted edges (81%) are excluded from scoring** (`project_edges_to_mentions` finds no recorded mention of one endpoint inside the edge's evidence span). They count neither as TP nor FP, so frozen strict precision 0.364 rests on 21 edges. Counting them as FP gives P 0.071 / R 0.027 / F1 0.039 (frozen 0.050).
2. **39 of the 90 excluded edges match an answer-key relation at concept level** (same two concepts by name, same relation), e.g. `infix-tuning compareWith prefix-tuning`; 48 of 111 predicted edges and 103 of 295 answer-key relations match at concept level.
3. **166 of 255 N0 codes (65%) have both endpoint concepts in the graph** (same name or alias); only the occurrence was not recorded. The frozen N0 text ("not a node of the final graph") is wrong for these, and CR-012's "concept extraction is the main SciNLP bottleneck (89.8%)" is overstated.
4. SciNLP Concept F1 (entity-strict analogue) counts only recorded mentions, so concept recall is understated.
5. P&D: the scorer aligns nodes to gold concepts through the same recorded-window spans; exposure is unmeasured.
6. The explorer shows excluded edges as "not in the answer key" and draws one grey copy of a concept per unrecorded occurrence.
7. Minor: edge evidence is located with `text.find(quote)` (first occurrence).

The evidence-window restriction exists for a reason (CR-012 `invalid_runs.md`): one global string table made two senses sharing a surface ("bandwidth") look like a false merge. Any fix must keep that.

## 2. Evidence for the design ($0, train/dev only; `reports/cr019/stage0_*`)

- SciNLP answer-key relations are **100% intra-sentence** (train 1,175 / dev 179; median endpoint distance 8 / 10 tokens). When an annotated surface pair co-occurs in a sentence it is annotated there 88% (train) / 97% (dev) of the time.
- Ceiling of each projection rule (a perfect concept-level graph built from the answer key, projected back, strict mention-level scoring):

| rule | train F1 | dev F1 |
|---|---|---|
| P1 one evidence sentence, every occurrence of both concepts in it | 0.903 | 0.955 |
| P2 every co-occurring sentence, all pairs | 0.865 | 0.968 |
| P3 every co-occurring sentence, nearest pair | 0.900 | 0.967 |
| P4 window ±1 sentence | 0.649 | 0.767 |
| P5 window ±3 sentences | 0.471 | 0.612 |

Paragraph-sized windows are rejected. Literature: DocRED keeps evidence sentences per relation; entity-level RE scores relations between entity clusters (Eberts & Ulges 2021); co-occurrence windows trade precision for recall (Quirk & Poon 2017).

## 3. Design

### O1 Occurrence index (gold-free, `src/cumap/cr019/occurrences.py`)
For a run and a text unit: every longest-match occurrence (rule 17, `expert_kg.mentions.MentionMatcher`) of every name and alias of every node that has a recorded mention in that unit, with a **position marker** (unit, paragraph, sentence, character span). Ownership of a surface shared by two or more nodes: the node whose recorded evidence windows contain the occurrence if exactly one does (the CR-012 rule), otherwise the occurrence is **ambiguous and assigned to no node** (counted). The index is a separate layer: it never writes mentions, never changes a node, never adds an alias (rule 24 unchanged).

### O2 Grounding-consistent evaluation (`src/cumap/cr019/variants.py`)
Node mention spans = recorded spans ∪ indexed occurrences. Edge evidence spans are located at the occurrence of the quote that contains both endpoints (first occurrence only if none does). The frozen scorers (`cr012.scoring`, `cr012.attribution`, `cr017.headline`) are reused unchanged; only their inputs change.

**Pre-registered (fixed before any test scoring, from §2 only):**
- **Primary SciNLP variant `IDX-P1`**: index + the edge's own evidence sentence (rule P1); every predicted edge that cannot be placed counts as **one false positive**.
- Secondary diagnostics: `FROZEN-UNPLACED-FP` (frozen projection, unplaced edges counted FP), `IDX-P3` (index + every co-occurring sentence, nearest pair; unplaced FP). P1 and P3 tie on train/dev ceilings (within 0.02), so the simpler, evidence-preserving P1 is primary.
- **P&D variant `IDX`**: the CR-017 five metrics with indexed node spans (the P&D scorer already counts every edge).
- **N0 split**: `N0-absent` (no node has the endpoint's surface) vs `N0-unrecorded` (a node has it; the occurrence was not recorded). Frozen codes are never overwritten; the split is an added field.
- No setting is tuned on the test papers or held-out sections.

### O3 Reporting
`reports/cr019/` (JSON + markdown), every number labelled with its variant and dataset snapshot; the frozen CR-012/CR-017 numbers are printed beside each variant and must reproduce exactly (`frozen_check`). Source artefacts are hashed before and after (read-only proof).

### O4 Scorecard and explorer
The CR-017 scorecard gains a variant switch (`frozen` | `CR-019 grounding-consistent`); frozen stays the default. The SciNLP graph labels edges the frozen scorer could not place as "not scored", and missed answer-key relations attach to the predicted node that owns the occurrence (index) instead of a grey duplicate.

### Stage B (paid, stops for approval)
Multi-sentence evidence for relation classification: the classifier sees every indexed co-occurrence sentence of the pair (capped), not only the first. Needs a new prompt version, E0 runs on SciNLP **dev** (6 papers) and P&D development sections, a dry-run cost estimate and owner approval (rule 7) before any call.

## 4. Stop points
- **STOP 1** (this CR, $0): Stage A results + Research decision on adopting `IDX-P1` as the reported SciNLP protocol (frozen numbers stay frozen).
- **STOP 2**: Stage B dry-run estimate → owner approval.
- **STOP 3**: Stage B pilot results.

## 5. Acceptance checks (Stage A)
1. `FROZEN` variant reproduces the frozen CR-012 SciNLP and CR-017 P&D numbers exactly.
2. Occurrence index unit tests: longest match, shared surface resolved by evidence window, ambiguous occurrence unassigned, no mention written.
3. Every predicted edge is accounted for in every variant (placed or counted FP); counts reconcile to 111 (SciNLP).
4. Source artefact hashes identical before and after.
5. All tests pass, no network, ruff clean.
