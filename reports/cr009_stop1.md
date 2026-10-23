# CR-009 STOP 1 — $0 diagnostics and drafts

No API calls were made. Branch `cr-009-concept-gvp` (from `main` at `cr-008-complete`).

## (a) Partial-span baseline (rule M2, $0)

| set | items | span found in its quote | flagged | rate |
|---|---|---|---|---|
| P&D ch1-3, CR-007 run (LLM-extracted mentions) | 1269 | 988 | 12 | 1.2% |
| IIR dev ch1-3, v3 outputs (LLM-extracted items) | 404 | 326 | 2 | 0.6% |

**Bank check:** the 7 bank examples' expected outputs raise **0** flags from any of F2-F6, C3, M1, M2 (required: none).

20 examples (10 per set; `item` → the longer candidate M2 would offer):

- [2.4] “remainder” → “nonzero remainder” (compound) — …the receiver will obtain a nonzero remainder implying that an error has occurred.…
- [1.3] “Device driver” → “network device driver” (compound) — …a network device driver…
- [2.5] “Sequence number” → “bit sequence number” (compound) — …the header for a stop-and-wait protocol usually includes a 1-bit sequence number…
- [1-problem-building-a-network] “communication service” → “effective communication service” (compound) — …What available technologies would serve as the underlying building blocks, and what kind of software architecture would you design to integr…
- [1.2] “resource sharing” → “Effective Resource Sharing” (compound) — …Cost-Effective Resource Sharing…
- [2.7] “chipping code” → “bit chipping code” (compound) — …The transmitted values, known as an n-bit chipping code…
- [1-perspective-feature-velocity] “hardware upgrades” → “modulo hardware upgrades” (compound) — …modulo hardware upgrades so users can enjoy the benefits of the latest performance improvements…
- [2.6] “jamming sequence” → “bit jamming sequence” (compound) — …it first makes sure to transmit a 32-bit jamming sequence and then stops the transmission.…
- [2-perspective-race-to-the-edge] “HERD” → “acronym HERD” (compound) — …resulting in the acronym HERD…
- [1.5] “propagation delay” → “term propagation delay” (compound) — …When we are referring to the specific amount of time it takes a signal to propagate from one end of a link to another, we use the term propa…
- [iir_1_1] “grep” → “Unix command grep” (compound) — …after the Unix command grep, which performs this process.…
- [iir_3_4] “reduced form” → “character reduced form” (compound) — …Turn every term to be indexed into a 4-character reduced form.…

### How much of the real partial-span problem the detectors see (IIR dev, measured against gold)

54 of 404 LLM items (13%) are a strict sub-span of a gold term in their section. **M2 as specified catches 0 of them** (it only looks inside the evidence quote, and the quote almost never contains the longer gold term); M2 on the whole paragraph catches 0. A candidate extra rule **M5** (a noun chunk that recurs >= 2 times in the chapter, contains the item, and is not already an item) flags 24 items, of which 10 (42%) offer a longer chunk that is a gold term, recovering 10 of the 54 gold partials. The complete-span prompt rules and the few-shot bank are therefore the main lever; M2 stays as a cheap precision-first hint, and M5 is proposed for your decision (it is not in the CR).

## (b) Propagation audit (CR-007 run `slice3_a1`, E3 adopted)

Mentions written by propagation (raw per-section data, `slice3_b4` inherits `slice3_a1`'s mentions): **735** of 2009 raw mentions: forward 575, backward 144, same section 16. Forward = later than the node's first LLM extraction; backward = earlier.

20 sampled for you to mark `same sense` / `different sense`: `data/interim/checks/cr009_propagation_audit_sheet.csv` (forward and backward mixed and shuffled when both exist; the key holds which is which).

## (c) Retriever dry run (P&D ch1-3 in book order, final CR-008 nodes `slice3_b4`, every node treated as growing)

Cards per section: median **68**, max **120** (cap 120); string hits median 35, semantic median 30, lexicon look-alike partners added in 20 sections. Prompt tokens the cards add: median **2056**, max 3848.

Backfill detector (§3.7): **35 calls** predicted (one per (chapter end, earlier section) pair) for 145 unrecorded node occurrences in earlier sections.

## (d) Pruner training data (IIR dev only, after term-level dedup)

- **growing** (gold in any dev section): **368** distinct terms
- **pruned** (candidate noun phrases that are gold in no dev section): **2259** distinct terms (of 2446 candidates)
- conflicts resolved as growing (gold in one section, a non-gold candidate in another): 19
- per dev chapter (for leave-one-chapter-out): {'1': {'growing': 117, 'pruned_candidates': 649}, '2': {'growing': 188, 'pruned_candidates': 1171}, '3': {'growing': 134, 'pruned_candidates': 727}}

## (e) Quantity floor ρ (rule Q1: items < max(3, ρ × words / 100))

Gold concepts per 100 words on the 13 dev sections: iir_1 3.1, iir_1_1 2.9, iir_1_2 4.8, iir_1_3 2.8, iir_1_4 3.0, iir_2_1 3.4, iir_2_2 1.9, iir_2_3 3.0, iir_2_4 2.6, iir_3_1 3.8, iir_3_2 2.7, iir_3_3 2.0, iir_3_4 3.8.
Median 3.0, lower quartile 2.7, minimum 1.9. **Proposed ρ = 1.5** (half the median density, so the floor catches only clearly thin outputs). Check: with ρ = 1.5, Q1 would fire on gold counts in 0 of 13 sections.


## (f) Drafts for your approval

- **Prompt v4** (`prompts/concept_generator_v4.md`, ≈ 960 words before the bank): the fixed skeleton ROLE → TASK → DEFINITIONS → INPUTS → PROCEDURE → OUTPUT SCHEMA → EXAMPLES → FINAL CHECKLIST. Against v3 (`prompts/concept_extraction/v2.md` + propagation) it adds EXISTING NODES and LOOK-ALIKES, the six-step procedure, the complete-span rules and the strict “same” rule, numbered paragraphs and an anchor/independence output; it drops the noun-chunk candidate-term hints. v3's definition of a concept, the exclusion list and the “a term, never a clause” rule are carried over unchanged. The full diff is not committed; the old file is unchanged.
- **Corrective-instruction table:** `configs/concept_gvp.yaml` → `verifier.corrective_instructions` (16 rules, one instruction each, wording in config), with the PiVe-style prefix “Extract the concepts again, and also review the given items…”.
- **Few-shot bank:** `configs/fewshot/concepts_v4_draft.yaml`: 6 worked examples + 1 corrective-round example (operating systems, databases, computer architecture; networking and IR are absent), all validated by code (F2–F6, C3, M1, M2 raise nothing; no 8-gram overlap with any P&D or IIR section). Approval sheet: `data/interim/checks/cr009_bank_approval_sheet.csv` (7 rows, ~10 min).
- **Configuration:** `configs/concept_gvp.yaml`: the rule repository (16 rules), retriever caps, verifier loop limits, pruner settings and the comparison arms (all `selection_eligible: false`).

## (g) Comparison set-up (ConExion, checked 2026-10-03)

- **Repository:** `github.com/ISE-FIZKarlsruhe/concept_extraction` (MIT licence), cloned read-only into the scratchpad (not into the project). It contains the code (`conexion/models/prompts.py`, `conexion/evaluation/evaluator.py`, dataset loaders) and 38 aggregate result CSVs.
- **Prompt/setup:** the paper describes “few-shot 1-Random”: one training example chosen at random per test document, base prompt “I have the following document: [DOCUMENT] Please give me the keyphrases that are present in this document and separate them with commas”, output split on commas/semicolons/newlines and **filtered to concepts present in the text by exact lexical match** (arXiv 2504.12915).
- **Scorer:** `evaluate_p_r_f` is set-intersection P/R/F1 on the exact strings per document (stemming only for the @k scores); published F1: Inspec 0.451, SemEval-2017 0.311 (Llama-3-70B, few-shot 1-random). Test sets: Inspec 486 documents, SemEval-2017 100.
- **Datasets:** the code loads `midas/inspec` (revision 9617780) and `midas/semeval2017` (revision d0e6006) from Hugging Face. **I could not confirm the dataset licences:** the pages I could read did not state one, so please check them before the data are downloaded; nothing has been downloaded, and the data will stay local and uncommitted.
- **Validity gate: cannot be run as specified.** The repository releases **no per-document predictions** and none for the 70B few-shot setup: only 38 aggregate CSVs for Llama-2-7B/13B and Llama-3-8B, all on Inspec, zero-shot. So their scorer cannot be re-run on released outputs to reproduce the published 0.451/0.311. Per §7.2 the fallback applies: re-run their prompt with our model and report like-for-like rows only (their published 70B numbers are shown as context, not as a comparison). The scorer code itself is 10 lines and exact-match, so I can port it with a fixture test.

## (h) Preflight for STOP 2 (estimates from measured prompt sizes; bulk tier $0.10 / $0.50 per 1M tokens, strong $2 / $10)

Measured: prompt skeleton ≈ 1435 tokens, bank ≈ 4395 tokens, cards median ≈ 2055 tokens (P&D; 40 assumed on IIR dev, 90 on IIR test), output ≈ 35 items × 75 tokens + 400 reasoning. Iterations: expected 2 per section, worst case 4 (iteration 0 + 3 corrective).

| item | expected | worst case |
|---|---|---|
| IIR dev, arm G1 (live, 13 sections) | $0.06 | $0.12 |
| IIR dev, arm G2 (live) | $0.08 | $0.16 |
| IIR dev, ± M4 (live) | $0.06 | $0.12 |
| IIR dev, ± V2 concept verifier (strong tier, 13 calls) | $0.22 | $0.22 |
| IIR dev, final end-to-end run of the chosen configuration | $0.06 | $0.12 |
| IIR test, v4 once (70 sections) | $0.35 | $0.71 |
| Comparison arms on dev + test: C-SAC, C-PiVe (C-PiVe-off is a replay) | $0.66 | $1.13 |
| Comparison arm C-ConExion (dev + test, one call per section) | $0.03 | $0.03 |
| External check: 3 systems on Inspec + SemEval-2017 test (586 abstracts) | $1.06 | $1.60 |
| P&D ch1-3 concepts (24 sections) + backfill | $0.14 | $0.27 |
| P&D canonicalisation R4, relations + verifier + expansion, prerequisites, fusion (CR §13 estimate; cache hits for unchanged prompts) | $4.40 | $10.50 |
| **Total** | **$7.14** | **$14.99** |

CR-009 §13 estimated ≈ $7–16 with a hard cap of $18. The cache makes byte-identical prompts free, and every command supports `--dry-run`, `--limit 20` before the full run (CLAUDE.md rule 7).
