# CR-016 STOP 2B — full consumer-impact audit of memory-assisted candidate retrieval ($0)

Written for: Research. Per the STOP-2 decision: similarity gate and review band **unchanged**; alternative consumers deferred to a future CR; STOP 3 on hold. No model call, no new retrieval, no fresh section: this audit reuses the committed STOP-2 retrieval records and local code. Code `src/cumap/cr016/consumer_audit.py`, data `reports/cr016/consumer_impact_audit.json`.

## A. What canonicalisation actually does in the production graph (slice3_c2, the current production run)
| step | count |
|---|---|
| v4 nodes entering canonicalisation | 1,275 |
| concepts after canonicalisation | 1,243 (only **32** nodes collapsed) |
| collapsed by exact-string rule / R0 lexicon / LLM "same" | 11 / 5 / 16 |
| generator links to existing nodes, before canonicalisation (rule 23 growing nodes) | 140 |
| canonicalisation LLM calls (candidate lists shown) | 1,108 |
| outcome of those calls: same / same-but-routed-to-review-band / narrower or broader / different | 16 / 10 / 336 / ≈ 746 |
So the whole decision surface where a better candidate list could help is the **26 same-type decisions out of 1,108 LLM calls (≈ 2.3%)**; the other 97.7% of calls end in different, narrower or broader. In every one-section evaluation slice (CR-012, CR-014, CR-015) the registry starts empty, so memory has no node to point at.

## B. Candidate generators on the 1,140 benchmark cases, frozen gate (best candidate similarity ≥ 0.6) and review band (matched similarity ≥ 0.70) applied unchanged
Cases = benchmark queries whose target concept already has a registered node (registry proxy: 1,722 gold concepts, canonical names, first annotated earlier; a retrieved paragraph maps to the nodes with a gold mention in it). Candidate list size 5 for every generator; memory-derived nodes are the nodes of the top-5 retrieved paragraphs, ordered by name similarity to the query surface.
| subset | cases (target registered) | embedding top-5 holds target | actionable under frozen gate+band (embedding only) | M1 memory holds target | M2 memory holds target | memory ADDS target (M1 / M2) | …and is actionable under frozen semantics | non-target nodes injected (M1 / M2) | injected non-targets above merge band (M1 / M2) | injected lexicon-DIFFERENT conflicts (M1 / M2) |
|---|---|---|---|---|---|---|---|---|---|---|
| all cases | 621 | 594 | 565 | 221 | 254 | 2 / 4 | **0 / 0** | 1543 / 1798 | 27 / 38 | 5 / 4 |
|   handled by exact / R1 / R2-type rules (no embedding or LLM needed) | 563 | 544 | 536 | 213 | 242 | 2 / 4 | **0 / 0** | 1389 / 1622 | 27 / 38 | 5 / 4 |
|   **residual: needs embedding + LLM** | 58 | 50 | 29 | 8 | 12 | 0 / 0 | **0 / 0** | 154 / 176 | 0 / 0 | 0 / 0 |
| low-lexical-overlap / associative | 27 | 26 | 26 | 9 | 10 | 0 / 0 | **0 / 0** | 88 / 82 | 0 / 0 | 0 / 0 |
| acronym | 25 | 6 | 0 | 4 | 8 | 2 / 4 | **0 / 0** | 53 / 77 | 0 / 0 | 0 / 0 |
| alias | 13 | 12 | 12 | 6 | 5 | 0 / 0 | **0 / 0** | 43 / 37 | 0 / 0 | 0 / 0 |
| one-token | 395 | 370 | 342 | 123 | 140 | 2 / 4 | **0 / 0** | 986 / 1186 | 14 / 22 | 1 / 1 |
Reading it:
- Of **621 cases** with a registered target, **563** are decided by the deterministic exact-string / R1 key / acronym rules before any candidate list exists (these rules are approximated here; acronyms are only partly covered). Only **58 residual cases** need the embedding-plus-LLM path.
- In those 58, the frozen embedding top-5 already contains the target in 50 (86%) and the frozen gate+band make 29 actionable. **Memory adds the target to the candidate list in 0 of 58**, so memory changes **0** outcomes.
- Across all 621 cases memory adds the target to the list in only 2 (M1) / 4 (M2) cases, all acronyms whose name similarity is below the merge band, so **0 are actionable under the frozen semantics**.
- On its own (without the embedding list) memory holds the target for only 36% (M1) / 41% (M2) of cases vs 96% for the embedding top-5. This **understates** memory: a retrieved paragraph only yields nodes where it was gold-annotated (821 of 2,071 paragraphs), so evidence in unannotated sections contributes no node.

## C. Identity hazard of injection
Memory injects 1,543 (M1) / 1,798 (M2) non-target nodes over 621 cases (≈ 2.5 / 2.9 per case), of which 27 / 38 have name similarity at or above the merge band (false-merge exposure for the LLM) and 5 / 4 are look-alikes the term lexicon marks DIFFERENT (the existing guard would filter those before the LLM). Gain under frozen semantics: 0; added exposure: small but non-zero.

## Conclusion (diagnostic, for Research)
- The approved consumer is **inert and slightly hazardous under the frozen canonicalisation**: it cannot change a decision that the embedding list plus the frozen gate and band do not already allow. This is not a retrieval failure: HippoRAG's retrieval advantage (STOP 2) is real but sits in cases (alias/acronym/associative) that the frozen gate cannot act on.
- The production graph offers little room anyway: ≈ 2.3% of canonicalisation LLM calls are same-type decisions.
- Consistent with the Research instruction I changed no gate or band and built no alternative consumer. Pipeline integration (STOP 3) stays on hold; a different consumer would be a future CR.

## Caveats
Registry proxy and node mapping come from exposed gold, not a real run's node store; the deterministic-rule approximation over-counts "handled" acronyms; 1,140 benchmark cases are a sample of exposed material, not an unbiased sample of the book. One embedding backbone (MiniLM).
