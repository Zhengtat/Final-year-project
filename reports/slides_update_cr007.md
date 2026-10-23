# Slides update: CR-006 sphere and CR-007 results (P&D, expert graph only)

Read-only, $0, no API calls. Run `slice3_a1`, organisation `org_baa0d058`, registry `relations_v1.1.1`. Wilson = 95% Wilson interval. **PENDING** = the stage does not exist yet or was not computed; nothing there is estimated.

Definitions used for the like-for-like column: "ch2-3" counts pairs by the chapter of the evidence section; linked share counts concepts with at least one mention in a ch2-3 section (strongest role taken from those mentions) that have a typed edge whose evidence section is in ch2-3. CR-005's baseline concept set was built from ch2-3 only, so concept counts are not identical populations.

Source key: [S4] `reports/cr007_stop4.md` · [S5] `reports/cr007_stop5.md` · [CK] `data/processed/kg/slice3_a1/checkpoint.json` (relation_results_v3, concepts, merges) · [SN] `data/processed/kg/slice3_a1/snapshots/ch*/edges.jsonl` and `manifest.json` · [OM] `data/processed/kg/slice3_a1/organisation/org_baa0d058/manifest.json` · [ON] `.../org_baa0d058/ch*/org_nodes.jsonl` · [G] `data/gold/cr007_*` (owner sheets) · [S1] `reports/cr007_stop1_diagnostics.md` · [S2] `reports/cr007_stop2_concepts.md` · [D] `docs/DECISIONS.md` · [P] `docs/PROGRESS.md` · [LOG] `data/logs/llm_calls.jsonl` priced with `configs/default.yaml` tiers. Figures [F] = `reports/demo/figures/`.

## 1. CR-005 vs CR-007

| Measure | CR-005 (ch2-3) | CR-007 ch2-3 (like-for-like) | CR-007 ch1-3 | Source |
|---|---|---|---|---|
| Pairs classified | 381 | 542 | 700 | [S1] (b); [CK] |
| Accepted edges / pairs classified | 121/381 = 31.8% | 238/542 = 43.9% (Wilson 39.8-48.1%) | 297/700 = 42.4% (Wilson 38.8-46.1%) | [S1]; [CK] |
| OTHER share of pairs | 117/381 = 30.7% | 115/542 = 21.2% (18.0-24.9%) | 146/700 = 20.9% (18.0-24.0%); CR target <= 15% **not met** | [S1]; [CK] |
| NO_RELATION share | 143/381 = 37.5% | 133/542 = 24.5% | 176/700 = 25.1% | [S1]; [CK] |
| Rejected by a check / edges dropped at the gate | n/a | 46/542 rejected; 10 edges `gated_dropped` | 65/700 rejected (45 domain/range, 20 endpoint not grounded); 16 `gated_dropped` | [CK] |
| Linked share, defined concepts | 76/509 = 14.9% | 221/522 = 42.3% (38.2-46.6%) | 289/665 = 43.5% (39.7-47.3%) | [S1] (b); [SN]+[CK] |
| Linked share, all concepts | 104/736 = 14.1% | 310/828 = 37.4% (34.2-40.8%) | 377/982 = 38.4% (35.4-41.5%) | [S1]; [SN]+[CK] |
| `mechanism_process` edges in the graph | 2 | 34 | 42 (CR target >= 20 met) | [S1]; [CK] |
| Missed-relation rate (50-pair unselected sample; edges in graph) | not measured | 11/41 = 26.8% (15.7-41.9%) of the sample pairs from ch2-3 | 13/50 = 26.0% (15.9-39.6%) | [CK] (group = sample) |
| Owner precision of attested edges (strict: wrong-direction counted wrong) | 23/30 = 76.7% (Wilson 59-88%) | 23/31 = 74.2% (56.8-86.3%) | 29/39 = 74.4% (58.9-85.4%) | [S1]/[D] for CR-005; [G] |
| Same, wrong-direction counted right | n/a | 24/31 = 77.4% (60.2-88.6%) | 31/39 = 79.5% (64.5-89.2%) | [G] |
| Owner precision of pipeline merges | 41/43 | not split by chapter | 23/24 = 95.8% (Wilson 80-99%) | [P]; [S5] |
| Verifier accept / correct / reject rates, concepts | PENDING | PENDING | PENDING (no `verifier.jsonl` exists) | n/a |
| Verifier accept / correct / reject rates, relations | PENDING | PENDING | PENDING | n/a |
| Owner-estimated false-rejection rate of the verifier | PENDING | PENDING | PENDING | n/a |
| Expansion round: concepts newly linked | PENDING | PENDING | PENDING (no expansion round has run) | n/a |
| Prerequisites: owner precision, agreement with defined-to-used, cycles broken | PENDING | PENDING | PENDING. Only the rule-based candidate count exists (defined in one section, used later; not verified, book order is not prerequisite truth): 12 + 45 + 33 = 90 across ch1/ch2/ch3 | [SN] manifests |
| Fusion: sweep merges, conflict groups by type and outcome, logic-/LLM-inferred counts, LLM-inferred precision | PENDING | PENDING | PENDING (no `conflicts.jsonl`; the report's inferred layer is a 4-edge transitive closure, no evidence, not owner-checked; 0 conflicting same-pair relations were found). Alias merges in the run: 1,027 records, 24 needed an LLM call, 16 held in the review band | [CK]; [S4] |
| Gated relations | n/a | n/a | `identifies` 5/8 correct (62%) **fail**; `encapsulates` 2 instances **fail**; `trades_off_with` 1 instance **fail**. Final registry **v1.1.1** (v1.1 minus those three); 17 edges flagged `gated_dropped`, kept in run data | [S5]; [D] |
| Report-only relations | n/a | n/a | `acts_on` 35 instances, 5/5 sampled correct; `connected_to` 10 instances, 4/5 | [S5] |
| IIR full-test lenient micro F1 | v2 0.569 | n/a | **v3 0.633** | [S2] section 4 |
| IIR full-test exact micro F1 (headline) | v2 0.433 | n/a | **v3 0.485** | [S2] section 4 |
| Chosen E-config | n/a | n/a | **E3** (consistency propagation on prompt v2; pre-registered rule, dev lenient 0.656) | [S2] section 3 |
| Total API spend | | | CR-007 since its first commit **$7.61** (re-run `slice3_a1` $6.61, pilot $0.79, test split $0.12, ablation $0.10). Since the CR-005 §9 amendment **$12.20**. All time **$27.06** (includes the $14.03 IIR-dev overrun before the amendment). Against the $25 cap: $12.20 is under it; all-time is over it. I could not find the cap's definition in the repo, so it is compared as given | [LOG] |

Notes: the v2 test number is from the reported run; the test split was executed twice by accident (disclosed in [S2] section 5): v3 identical 0.485, v2 0.433 vs 0.444. The sample-pair rate counts pairs the classifier called an edge; one extra sample edge belonged to a dropped relation (ch1-3: 14/50 = 28.0% including it).

## 2. CR-006 sphere on the new run (org `org_baa0d058`, radius basis adjusted, label "Structural metric (no human labels)")

Concepts and edges here are cumulative through that chapter. Unlinked % = unlinked concepts / all concepts. [OM] unless noted.

| Chapter | Concepts | Typed edges | Unlinked | Eligible concepts | Primary null: Δρ, z | Second null: Δρ, z | Label |
|---|---|---|---|---|---|---|---|
| ch1 | 316 | 59 | 235/316 = 74.4% | 81 | +0.059, z 1.6 | +0.075, z 2.4 | no clear core (rho 0.195) |
| ch2 | 698 | 166 | 467/698 = 66.9% | 231 | +0.005, z 0.4 | +0.011, z 1.5 | no clear core (rho 0.091) |
| ch3 | 982 | 297 | 605/982 = 61.6% | 377 | +0.030, z 4.5 | +0.012, z 2.4 | weak core (rho 0.096) |

Core-periphery check: Δρ = observed rho minus the null mean (the CR-006 threshold is 0.10); z is against 200 null graphs per model. Source [OM] `chapters.<n>.core_periphery`. The ch1 and ch2 Δρ are below the 0.10 threshold, ch3 is a "weak core".

Stability (core Jaccard, Kendall tau; exact) [OM] `stability`:

| Chapter | Core Jaccard | Kendall tau | Mean displacement | Shared concepts |
|---|---|---|---|---|
| ch1 | n/a (first chapter) | n/a | n/a | 0 |
| ch2 | 0.319 | 0.891 | 0.105 | 81 |
| ch3 | 0.407 | 0.912 | 0.088 | 231 |

Soft Jaccard / soft tau: **PENDING** (the organisation code computes only the exact versions).

Top-10 centre concepts by adjusted importance [ON] (ch1 has only 4 centre-ring concepts):

- ch1: message, application, Internet, protocol
- ch2: frame, node, protocol, Internet, message, bit, application, physical medium, network, latency
- ch3: node, switch, packet, frame, message, router, host, physical medium, protocol, network

Top-15 overlap across bases [ON]: raw vs adjusted: ch1 13/15, ch2 14/15, ch3 14/15. The `freq_adjusted` basis does not exist in the code, so a three-way overlap is **PENDING**.

## 3. Three short examples (quote < 25 words)

1. **New `acts_on` edge** (owner-marked correct, section 3.1): host -[acts_on]-> packet, action type send. Evidence: "A host can send a packet anywhere at any time" (10 words). Source: [G] edge sheet/key, [CK].
2. **Conflict group:** none to show. No `conflicts.jsonl` exists and the same-pair conflict check found no conflicting relations in this run; the fusion stage is PENDING.
3. **`corrects_intuition` edge:** section 3.3, network -[has_property]-> maximum transmission unit. Evidence: "every network type has a maximum transmission unit (MTU)" (9 words). The model flagged it because the next sentence in the book says "Note that this value is smaller than the largest packet size on that network", but the quote the edge cites is only the first clause, and the owner did not mark this edge. The flag is under review and fires on some caveats that are not warnings, so show it only as an illustration of the idea. Source: [CK].

## 4. Figures

For the new run (all carry the provenance footer and a label-source tag; built by the existing report code, which draws its own SVG rather than matplotlib):

- Sphere: `reports/demo/figures/sphere_ch0.svg`, `sphere_ch1.svg`, `sphere_ch2.svg`, `sphere_ch3.svg`
- Organisation charts: `org-top15-ch1.svg`, `org-top15-ch2.svg`, `org-top15-ch3.svg`, `org-ring-composition-ch1.svg` (and ch2, ch3), `org-core-periphery-fit.svg`, `org-stability.svg`, `org-importance-trajectories.svg`, `org-community-events.svg`
- Growth/relation charts: `growth-graph-through-ch1.svg` (and ch2, ch3, all-chapters), `edges-by-family.svg`, `edges-by-relation.svg`, `pair-outcomes.svg`
- New for this file (tag "Model output, not validated"): `cr005-vs-cr007-shares.svg` (OTHER share, defined-concept linked share, overall linked share; CR-005 ch2-3 vs CR-007 ch2-3 vs CR-007 ch1-3) and `cr005-vs-cr007-mechanism.svg` (mechanism_process edges 2 / 34 / 42, on its own chart because the scale differs).
- Existing charts such as `owner-spotcheck-precision.svg` and `owner-merge-check.svg` show the CR-005 marks (n=30 and n=43), not the CR-007 marks, so do not use them for CR-007.

## 5. Where each number came from

Each table row names its source in the last column; the keys are listed at the top. Numbers I computed for this file (ch2-3 splits, Wilson intervals, linked shares, sample rate) come from [CK], [SN] and [G] with the definitions above; they are not in `cr007_stop4.md`. The IIR numbers, the CR-005 baselines and the gate outcome are copied from [S2], [S1] and [S5].
