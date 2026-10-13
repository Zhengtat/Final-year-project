# CR-015 Stage B — frozen codebook and design (written after the Stage-A decision and the boundary audit; frozen before any Stage-B call)

Decisions this rests on: Research STOP-2 decision (A2 is the Stage-B base; over-long gate retained; fresh pilot sealed); owner acceptance (2026-10-13) of the **model-filled** boundary audit as diagnostic evidence, waiving the human-audit requirement. The gold convention is **not changed**: Stage-B development is still scored against the model-generated gold with the frozen scorer; the audit is reported as a side diagnostic, never as a gate.

## Pipeline per arm (development, 10 exposed sections)
`frozen U2 → frozen A2 family selector (saved selected spans, reused unchanged) → concepthood verifier (arm-specific) → family-grounded placement (frozen A2 policy) → frozen scorer`.
The selector is not re-run: B arms differ only in the verifier, so the comparison isolates precision recovery. **B0 = A2 as frozen** (selector + CR-014 V3 verifier).

## Verifier input (CR §14.1) and what it never sees (§14.2)
Per distinct selected span: the exact span; source sentence(s) (≤ 2, span marked); section heading; co-selected spans of the same family (boundary-family metadata); proposal source tags; deterministic exact-name matches against existing nodes (none in the one-section slices); one-word term evidence (the CR-014 ranker features, identical to V3); for B2 only: retrieved development demonstrations. It never sees: any gold, held-out or fresh-pilot material, any other verifier's answer, the selector's free text, or this audit's labels.

## Output
Verdicts (CR §14): ACCEPT_NEW, LINK_EXISTING, REJECT_NOT_CONCEPT, REJECT_GENERIC, REJECT_WRONG_SENSE, INSUFFICIENT_EVIDENCE; reason codes as in the prompt. The verifier **never repairs a boundary**. Accepted = ACCEPT_NEW or LINK_EXISTING; INSUFFICIENT_EVIDENCE and every REJECT_* are not accepted. Separating boundary from concepthood: a wrong boundary is decided upstream (selector); the verifier's only boundary-related behaviour is rejecting a phrase that merely wraps a shorter co-selected span with description (REJECT_NOT_CONCEPT, reason `descriptive_phrase`). That is the pre-declared path for the retained over-long gate.

## Arms
| arm | verifier | extra |
|---|---|---|
| B0 | CR-014 V3 verifier (prompt `cr014_concept_verifier` v2) | = frozen A2 |
| B1 | `prompts/cr015_concept_validity/v1.md` | separate concepthood question; co-selected-span context |
| B2 | `prompts/cr015_concept_validity/v2.md` | B1 + retrieved contrastive demonstrations |
| B3 | not run unless B1/B2 fail the gates and a precision-recovery hypothesis remains | A/B independent verifiers, third call only on disagreement |
Model: bulk tier `gpt-6-luna`, reasoning effort low, no sampling parameters, no escalation, 25 spans per call, output cap 6000 (runtime). C-arms (local span ranker) are not planned.

## B2 demonstration bank (development only, frozen with its hash before the run)
- Positives: gold spans of the 10 development sections that the frozen A2 verifier also accepted (agreement of benchmark and model).
- Negatives: U2 candidate spans with **no overlap with any gold span** in their section AND rejected by the frozen A2 verifier (agreement again), so gold omissions that the model also accepted are excluded. The bank is a development bank only; the model-filled audit rows are not in it.
- Retrieval: leave-one-section-out (a query section never sees its own gold); rank by same head word, same token length, one-word flag; 5 positive + 5 negative demonstrations per batch at most; retrieved ids and scores saved per batch; bank hash recorded.

## Development gates (CR §22, unchanged) and reporting
All §22 gates incl. precision ≥ U0 − 0.02, distinct-surface precision ≥ U0 − 0.05 and over-long FP reduction ≥ 25% vs frozen V3 (553 → ≤ 415). Report: mention and distinct-surface P/R/F1, one-token and nested slices, valid-concept rejection rate and invalid-concept acceptance rate (against the model-generated gold and, separately, the model-filled audit sample), verifier recall given a correct boundary, hard-negative slice, retrieval-example slice, disagreement rate vs B0, bootstrap ΔF1, cost, calls, runtime; earliest-cause taxonomy as in Stage A.

## Not allowed after this freeze
No change to prompts, verdict set, bank rule, retrieval ranking, model, batch size or gates. The fresh pilot (4.3, 6.2) stays sealed until a candidate is selected and frozen.
