# CR-014 STOP 5 — downstream compatibility (baseline U0 vs frozen V3), 8 sealed P&D sections

Written for: Research. CR-014 outcome is already decided (V3 not adopted; production remains U0). This stage only quantifies what V3's extra concepts do downstream, so CR-015 knows what to target. Same frozen downstream stages for both arms: canonicalisation (prompt `canonicalize` v2, type-aware), D3 pair budget B(u)=min(pool, ceil(14.2·words/1000)), anchor-first pair selection, relation stage (family v3 / choice v4 / qualifiers v4, registry v1.3). Each section is a one-section slice (as CR-012 E0). Nothing in U0, V3, the manifest, or any historical run was changed; all outputs are new run ids `cr014_heldout_<sec>_{U0,V3}`.

**Gold caveat.** Gold = the model-generated annotation (not human); there is **no relation gold** for these sections, so true false-edge growth is not measurable. "Gold-supported" below means a concept/edge endpoint whose name or alias equals a surface annotated in that section — a proxy for validity, not a precision measurement.

## V3 adapter (needed because V3 emits accepted surfaces, not graph nodes)
Node type assigned by a small LLM step (`cr014_node_typing` v1, bulk tier, frozen before use, sha256 `41a9f01c…`; types only, never rejects a concept); role = `defined` if the surface matches a production definitional pattern, else `used`; evidence = the first-occurrence sentence; anchors inherited only where a U0 node has the same surface (246 vs U0's 287). Everything else is the production code path. The adapter is the main confound: V3 and U0 differ in how nodes were produced, so downstream differences mix the concept set and the adapter.

## Results (totals over the 8 sections)
| measure | U0 | V3 | change |
|---|---|---|---|
| concepts after canonicalisation | 1,146 | 1,905 | +66% |
| of which gold-supported (surface in gold) / not | 694 / 452 | 1,055 / 850 | supported share 60.6% → 55.4% |
| canonical merges (stage ≠ generator) | 18 | 361 | ×20 |
| merge-review queue / taxonomy candidates | 2 / 204 | 24 / 582 | +22 / ×2.9 |
| candidate pairs (pool) | 4,600 | 8,868 | +93% |
| pair budget / pairs selected | 573 / 573 | 573 / 573 | budget saturated in both |
| concepts appearing in any candidate pair / covered by a selected pair | 1,073 / 761 (71%) | 1,793 / 867 (48%) | coverage share −23 pts |
| relation calls: family / choice / qualifiers | 573 / 444 / 213 | 573 / 458 / 231 | +0% / +3% / +8% |
| relation outcomes: edge / other / no_relation / rejected | 212 / 139 / 138 / 84 | 231 / 127 / 129 / 86 | edges +9% |
| edges with both endpoints gold-supported / one / none | 111 / 90 / 11 | 116 / 83 / 32 | none-supported ×2.9 |
| edges with an evidence quote | 212/212 | 231/231 | 100% both |
| concepts with full provenance (mention + quote) | 1,146/1,146 | 1,905/1,905 | 100% both |
| identity: merges checked against gold concept ids → false merges | 13 → 10 | 215 → 34 | see note |
| identity: merges violating a lexicon DIFFERENT entry | 0 | 0 | none |

Per section (concepts / merges / pool / edges, U0 → V3): 4.2 134→181 / 2→25 / 473→726 / 17→22; 5.3 216→330 / 4→71 / 1067→1734 / 36→38; 6.1 101→172 / 1→22 / 288→785 / 20→26; 6.4 111→203 / 4→36 / 473→886 / 29→27; 7.2 208→392 / 5→62 / 751→2038 / 41→48; 8.3 73→115 / 1→35 / 279→445 / 14→18; 8.4 48→83 / 0→24 / 130→278 / 14→15; 8.5 255→429 / 1→86 / 1139→1976 / 41→37. Edge-type mix is similar (is_a 60/62, part_of 41/40, requires 25/30, uses 29/28, has_property 12/21).

Notes on the identity row: the numbers are small for U0 (13 checkable merges) and the gold's concept identities are model-generated, so 10/13 vs 34/215 is not a reliable comparison; it only shows V3 triggers far more merge decisions (the extra surfaces are largely plural/alias variants of one concept, which canonicalisation must fold). The CR-008 lexicon DIFFERENT veto held in both arms (0 violations).

## Cost and runtime (this stage only; log-derived, bulk/strong tiers as configured)
| arm | components | USD |
|---|---|---|
| U0 | concept stage 0.16 + canonicalisation 1.13 + relations 3.76 | **5.05** |
| V3 | proposals (boundary 0.17 + verifier 0.18) 0.34 + typing 0.04 + canonicalisation 2.82 + relations 3.49 | **6.69** (+0.16 for the shared U0 generator that supplies the raw proposals = 6.85) |
Canonicalisation calls 377 → 1,031 (cost ×2.5); relation cost is flat because the budget is word-count based. Stage total ≈ $11.7 (U0 5.05 + V3 6.69), above my pre-run estimate of $8–10 because of canonicalisation; cumulative CR-014 spend ≈ $14.9 against the $30 cap. Cache hits: 196 calls (re-run after the incidents below).

## What this says
- **Relation-classifier load does not grow**: the word-count budget caps selected pairs, so call count and cost stay flat (+3–8%). Edge count rises 9%.
- **Pair-budget pressure does grow**: the candidate pool doubles while the budget is unchanged, so each concept has a lower chance of being paired (coverage of concepts by selected pairs 71% → 48%). More concepts means a given relation is less likely to be examined.
- **Canonicalisation is the cost and identity driver**: 20× the merge decisions, 2.9× the taxonomy candidates, 12× the review queue; V3's recall gain is partly the same concepts under several surfaces.
- **Edge-endpoint validity (proxy) does not clearly worsen**: edges with both endpoints supported 52.4% → 50.2%; edges with no supported endpoint 11 → 32 (small numbers).
- **No provenance regression** (100% evidence for concepts and edges) and no lexicon-veto violation.

## Incidents and deviations (all infrastructure, none changes a result)
- One DNS failure (`APIConnectionError`) killed the run during 5.3's V3 canonicalisation; restarted from 5.3 (4.2 untouched, finished calls came from the cache).
- Node-typing batch for 8.5 exceeded the 1000-token default output cap; raised to 4000 for that task at runtime (prompt unchanged, earlier sections' cached calls unaffected).
- Held-out trace events (`proposal`, `boundary_repair`, verifier) were **not** emitted for these sections (the trace builder exists for the IIR dev arms and reads the same saved outcome fields); provenance fields are complete (every accepted surface carries source candidate ids and a verbatim occurrence), but a CR-013-style trace file for the held-out run was not generated. Marked NOT DONE.

## Migration and rollback plan (for a future adoptable candidate; nothing is migrated now)
- **Current state:** no migration. Production remains the CR-009 concept stage (U0). CR-014 code lives under `cumap.cr014`, prompts under `prompts/cr014_*`, runs under `cr014_*` run ids; no production path imports them.
- **If CR-015 yields an adoptable system:** (1) freeze and tag it; (2) run it behind a switch that selects the concept-stage implementation, default off; (3) write to new run ids only, never over a historical run; (4) require the adapter to be part of the system (node typing, roles, evidence), or have the proposal system emit production-format nodes directly; (5) re-run this STOP-5 comparison on its output before the switch is turned on.
- **Rollback:** turn the switch off; production output is unchanged because CR-014 never wrote into production runs. Historical runs are untouched (hash-checked against `FREEZE_V3.json`).

## Items for Research (no decisions taken here)
1. The V3 node growth is mostly surface variants (361 merges) plus low-support concepts (850 unsupported vs 452); CR-015 may want de-duplication before canonicalisation and a precision-recovery step, as already planned.
2. Pair-budget pressure is a design question for any recall-first system: scale the budget with concept count, rank pairs differently, or accept lower pair coverage. Not tested here.
3. True false-edge growth needs relation gold for these sections; none exists.
