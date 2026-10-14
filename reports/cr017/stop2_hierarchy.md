# CR-017 STOP 2 — Ancestor Hierarchy F1 (scorer only; no model run)

Written for: Research. Implemented in `src/cumap/cr017/hierarchy.py`, configured in `configs/cr017_eval.yaml`, fixtures in `tests/test_cr017_hierarchy.py`, evidence in `reports/cr017/stop2_hierarchy.json` (script `src/cumap/cr017/stop2_report.py`). Nothing in the CR-012 scorer or any historical artefact was changed.

## What was built (all CR §3 STOP-2 items)
| item | implementation |
|---|---|
| hierarchy relation filter | frozen set `{is_a}`; `instantiates` and every other relation excluded; asserted by tests |
| cycle detection / handling | each directed cycle is found once (reported as its smallest-node rotation); closure uses a per-start visited set so it always terminates; pairs inside a cycle stay in the prediction and are judged against gold; self pairs (A, A) are dropped and counted |
| canonical-ID alignment | the frozen CR-012 `align_nodes` (exact mention-span match): a wrong canonical concept is a wrong pair; an unmatched or false-merge predicted node keeps a synthetic id, so every pair involving it can only be a false positive |
| transitive closure / ancestor pairs | per section (concept ids are section-local); pairs are a set, so a split node cannot add duplicates |
| precision / recall / F1 | over the two pair sets, as in CR-017 §6.5; pooled by adding counts; `PRF` type shared with the CR-012 scorer, so `cr012/bootstrap.py` applies unchanged (section unit) |
| diagnostics | direct-parent P/R/F1, gold pairs lost because an endpoint concept has no predicted node, unmapped hierarchy nodes, cycles, self pairs |

## Fixture results: 16 / 16 pass
Exact hierarchy A→B→C (P = R = F1 = 1); skipped parent A→C (pair (A,C) credited, (A,B) and (B,C) missed; direct-parent scoring would have credited nothing); false ancestor A→D (one false positive); missing concept (all its gold pairs are false negatives); wrong canonical concept (no partial credit); only `is_a` counts (part_of, uses, requires, has_property ignored); `instantiates` not in the set; unmapped predicted node → false positive only; false-merged node maps to nothing; split node cannot duplicate pairs; cycle A→B→C→A detected, closure bounded and without (X, X); cycle handling deterministic and each cycle reported once; self-loop dropped and counted; gold without hierarchy; pooling adds counts; real frozen held-out gold has 64 `is_a` edges, 75 ancestor pairs and no cycle.

## Cycle-handling result
Gold: **0 cycles** in all 9 annotated sections. Frozen E0 predictions: **0 cycles** in all 9 runs. Synthetic cycles (A→B→C→A, A⇄B plus C→D→E→C) are detected exactly, reported once each, and the closure terminates with no self pairs.

## Gold-support status
P&D-E2E gold supports the metric: 79 `is_a` edges, 102 ancestor pairs (held-out alone 64 and 75), 8 of 9 sections (details in `hierarchy_gold_audit.md`); SciNLP `NOT_SUPPORTED_NO_IDENTITY_GOLD`. Sanity check on the real gold: scoring a "perfect" prediction (one node per gold concept grounded on its own mentions, edges copied from gold) returns **F1 = 1.0 in all 8 sections that have hierarchy**; section 1.5 has no gold pair, so its per-section F1 is undefined (reported as 0.0 by the zero-division convention; it contributes zero counts to pooled scores and must be shown as "n/a").

## Ancestor-pair examples (from the frozen gold)
- 2.6: *Ethernet standard ⇒ bit-oriented framing protocol*, *Ethernet standard ⇒ local area networking technology*, *Ethernet standard ⇒ multiple-access network*, *multi-access Ethernet ⇒ bit-oriented framing protocol* (pairs added by closure over direct edges such as *Ethernet → bit-oriented framing protocol*).
- 7.1: *structure ⇒ data type*, *array ⇒ data type*, *tree ⇒ data type* (via *flat type → data type*).
- 8.2: *SHA-3 ⇒ cryptographic hash*, *Digital Signature Standard ⇒ authenticator*, *HMAC ⇒ authenticator*.
- 9.3: *Domain Name System ⇒ middleware* (via *name service → middleware*), *A record / NS record / CNAME record / MX record ⇒ name-to-value binding*.

## Code-path run on the frozen CR-012 E0 checkpoints (not a result)
The scorer runs end to end on the real E0 graphs of all 9 sections. Held-out pooled counts: tp 7, fp 41, fn 68 (P 0.146, R 0.093, F1 0.114), 0 cycles. This only proves the plumbing; the historical hierarchy scores, with intervals and oracle levels E1–E4, belong to the STOP-4 replay. The low value is expected: only 11 of 79 gold `is_a` edges even reach the classifier at E0.

## Assumptions I made from the Research rulings (please correct if wrong)
The pasted ruling said "PASS … STOP 2 AUTHORISED … STOP 3 relation scorer semantics FROZEN by the rulings above". I read that as accepting my STOP-1 proposals: relation set `{is_a}`, per-section closure, the cycle policy above, set semantics, descriptive-only intervals, and the CR-012 population convention (7 held-out sections are the headline; the 2 pilot sections are development data). The Concept F1 variant (untyped `canonical_node` 0.643 or typed 0.473) was not named; it is not needed until STOP 3 and stays open.

## RESEARCH DECISION REQUIRED
1. Confirm the assumptions above (especially the cycle policy and the 7-section headline population).
2. Name the headline Concept F1 variant before STOP 3.
