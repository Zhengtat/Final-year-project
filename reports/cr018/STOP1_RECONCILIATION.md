# CR-018 STOP 1 — repository reconciliation + feasibility ($0)

Written for: Research (decision-maker) and the project owner. **0 paid calls, 0 model calls, no fresh section consumed, no proposal/selector/verifier/canonicalisation code modified, no boundary audit run.** Branch `cr-018-boundary-identity`, created from `main` at `9337cec` (merge of CR-017, tag `cr-017-complete`). The spec and handover were copied to `docs/change-requests/` and `docs/research/` (they lived only in `~/Downloads`). Analysis code, new, under `src/cumap/cr018/` (`stop1_audit.py`, `stop1_replay.py`); test `tests/test_cr018_stop1.py`.

## 1. Answers to the two STOP-1 questions
**Boundary — YES, with one Research decision.** The frozen A2 selector output is a dict `family id → set(selected surfaces)` (`selector.SelectorOutcome.selected`, saved in `data/processed/cr015/stageA/A2_<sec>.json`). `selector.verify_selected(client, prompt_v, u, heading, selected, usage)` is the seam: a new boundary validator can filter that dict and the surviving spans go into the frozen verifier and `placement.family_grounded` **without touching proposal, families or selector**. Proven on saved artefacts: `family_grounded(selected, accepted)` reproduces the saved A2 spans **exactly** for all 10 development sections (10,675 spans) and the CR-015 A2 numbers (P 0.665 / R 0.785 / F1 0.720). Open: *which* verifier is "the frozen concepthood verifier" (§8, D1).

**Identity — YES for mechanics, NO for the statistical aim as specified.** An accepted concept plus retrieved prior evidence can be passed to a new verifier without weakening identity safety: the existing guard chain (exact → R0 lexicon → R1 key → R2 acronym → R3-strong → lexicon-`different` filter → `never_merge`/`force_merge` overrides → type check → embedding gate 0.6 / review band 0.70) runs *before* any new consumer, and `different` flags can be passed in as a hard veto. Dense and HippoRAG are already interchangeable behind one runner (§3). But the available identity cases are too few for the specified precision gate to be supportable (§5, D4).

## 2. Track A — boundary: reconciled definitions (from committed artefacts, not prose)
| item | exact location | state |
|---|---|---|
| Proposal union (U2) | `cr014/union.py::build_section_union` (sha `7d111b7f…`), `cr014/proposal.py` (`5a068e30…`) | frozen, tag `cr014-v3-frozen` (`FREEZE_V3.json`: 43 hashes re-checked now, 0 mismatch) |
| Overlap families | `union.py::build_families` / `noun_runs` | frozen |
| High-recall family selector | `cr015/selector.py::run_selector`, prompt `prompts/cr015_boundary_family/v1.md` (`f39dbb64…`), bulk `gpt-6-luna`, 15 families/call | frozen, tag `cr015-a2-frozen` (`FREEZE_A2.json`: 24 hashes re-checked, 0 mismatch) |
| Concepthood verifier | **two candidates**: (a) CR-014 V3 verifier, `prompts/cr014_concept_verifier/v2.md` (`c6f02918…`), carries a boundary verdict `REJECT_PARTIAL_OR_WRONG_BOUNDARY`; (b) CR-015 B1 concepthood-only verifier `cr015/validity.py` (design frozen, tag `cr015-stageb-design-frozen`; **not adopted**: failed its gates) | see D1 |
| Nested-aware placement | `cr015/placement.py::family_grounded` (A2 policy, frozen); reference `longest_match` | frozen |
| Production baseline U0 | saved `u0_final` per section (`cr015/dev_data.py`) | replayed |
| Scorer | `cr015/scoring.py` (tag `cr015-scorer-frozen`, 5 hashes re-checked) | frozen; CR-017 five-metric framework is the downstream headline, not used for span scoring |
| Human boundary-audit tooling | `cr015/audit_sample.py` (blind sheet, hidden key), `data/interim/checks/cr015/boundary_audit_blind*.csv`, `reports/cr015/boundary_audit_result.md` | tooling exists; the only filled sheet is **model-filled** (diagnostic only) |

**Saved outputs available for replay ($0):** per development section `A2_*`, `A3_*`, `B1_*`, `B2_*` (selected spans, decisions, accepted, verdicts, spans), `unions_dev.pkl`, CR-014 `V3_*` outcomes, U0 outputs, `hardneg_bank_meta.json`. Development = 10 exposed CR-014 sections, 50,523 words, 9,050 gold mentions, **model-generated gold**.

**Candidate-family volume (development, measured):** 10,761 candidates, 8,327 families (3,699 multi-member), 7,320 distinct selected surfaces, 3,160 distinct accepted, 10,675 placed (A2). Per 1,000 words ≈ 213 candidates / 165 families / 73 multi-member families.

**Replay of the baselines (no call; `reports/cr018/stop1_replay.json`, reproduces CR-015):**
| arm | P | R | F1 | nested-gold R | over-long FP |
|---|---|---|---|---|---|
| BA0 = U0 (production) | 0.764 | 0.513 | 0.614 | 0.224 | 207 |
| frozen V3 (A0, longest-match) | 0.699 | 0.624 | 0.659 | 0.077 | 553 |
| **BA1 = selector only, placed (no verifier)** — newly computed, $0 | 0.439 | 0.849 | 0.579 | 0.763 | 1,679 |
| A2 = selector + V3 verifier + placement (best prior; failed precision gates) | 0.665 | 0.785 | 0.720 | 0.703 | 695 |
Gate thresholds from §16 against these baselines: precision ≥ **0.744**, recall ≥ **0.563**, F1 ≥ 0.634 (or paired-bootstrap lower bound > 0), distinct-surface precision ≥ **0.697** (A2: 0.560), over-long FP ≤ **415** (25% below V3's 553; A2: 695).

**Reach of a boundary-only filter (feasibility ceiling, from the committed FP taxonomy):** A2 has 3,574 FPs: 1,750 no-overlap with gold (generic/descriptive/unsupported — *concepthood*, not boundary), 913 invalid-nested, 695 over-long, 216 under-long. Boundary-class FPs = 1,824 (51%). If a boundary verifier removed **all** of them at no loss of true positives, precision would be 7,101 / (7,101 + 1,750) = **0.802**. Reaching 0.744 needs it to remove ≥ ~1,130 of the 1,824 (≈ 62%) while keeping ~all TPs; and to meet the over-long gate it must remove ≥ 280 of 695 (40%). Feasible only if the remaining 1,750 non-boundary FPs are handled by the (frozen) concepthood verifier — this is the stage that, in CR-015, *lost* precision when told to ignore boundaries. Also: the model-filled audit judged ~31% of gold-unmarked spans valid, so development precision against this gold is probably understated (convention risk, STOP 2).

## 3. Track B — identity / memory: reconciled definitions
| item | location / state |
|---|---|
| Canonicalisation path | `expert_kg/canonicalize.py::canonicalize_mention` → `_canonicalize`. Order: exact-string (no LLM) → **R0 lexicon `same` → R1 normalisation key → R2 acronym-expansion → R3-strong alias statement** (`canonical_rules.py`, first match wins; lexicon `different` guards all; type check) → lexicon-`different` filter on candidates → `force_merge` → top-5 embedding candidates (MiniLM, name+definition), **similarity gate 0.6**, `never_merge`, LLM `same/broader/narrower/different` (prompt canonicalize/v2), **review band 0.70** (a `same` below it goes to review, not merged). |
| Node registry | `ConceptRegistry`/`RegisteredConcept`: `concept_id`, `canonical_name`, `node_type`, `definition`, `first_introduced`, `aliases`, `mentions` (section, role, **quote**, definition), `description_history`, `merged_from`, `alias_provenance` (rule id + evidence). Evidence storage = mention quotes with section ids → a retrieved paragraph maps to nodes whose mention quote lies in it (deterministic, exact-substring); unannotated paragraphs give no node (CR-016 caveat). |
| Dense retrieval | HippoRAG's `StandardRAG` in the isolated env (`.venv-hipporag/`, Python 3.11, hipporag `2.0.0a5` at pinned commit `d5c8329422e0a0b834a15874545cb6a74b4f9b26`, torch 2.5.1, transformers 4.45.2, sentence-transformers 5.7.0, MiniLM-L6-v2 cached locally); no per-chunk metadata → provenance sidecar (CR-016). |
| HippoRAG memory | same env; HippoRAG model calls routed through the project client by `cr016/llm_shim.py` (rule 4: cache + call log); OpenIE graph retrieval-only. |
| Memory adapter / causal index | `cr016/run_retrieval.py` (imports nothing from `cumap`): loop over units in source order, queries answered against earlier units only, then the unit is indexed into **both arms with separate index state**; every retrieved item checked (`source_order` strictly earlier) or the run **fails closed**; verified 0 future-retrieval violations in CR-016. Dense and HippoRAG already share corpus chunks, query text, top-k, embedder. |
| Identity benchmark (existing) | CR-016 STOP-2: 1,140 cases / 17 exposed sections / 2,071 paragraphs (sha256 corpus `c9861ad8…`, queries `15326e74…`, key `115e4fe1…`, all re-verified now). |

**Identity-case volumes (from CR-016 STOP 2B, development proxy):** of 1,140 cases, 621 have a registered target; **563 are decided by deterministic rules** (exact/R1/R2) before any candidate list exists; only **58 are residual** (embedding + LLM path): low-lexical-overlap 27, acronym 25, alias 13. Query-level slices: alias 58, acronym 34, different-boundary 20, low-overlap 109, same-surface-different-sense 116, long-gap 381. In the full production run (ch.1–3, 70,295 words) 1,108 of 1,275 nodes reach the LLM stage (≈ 16 per 1,000 words), but ≈ 97.7% of those end in different/narrower/broader — the decision surface where a better link could matter is ≈ 26 same-type decisions.

**Identity-gold coverage — the central Track B limit.** The P&D gold annotates concept identity **within a section only** (681 concept ids over the 9 E2E sections; 61 `NOT_SAME` rows, all within-section). Cross-section identity is not annotated; CR-016 used "normalised canonical name" as the identity proxy (41 names recur across the 9 E2E sections). So *correct historical canonical node*, *alias/acronym recurrence* and *same-surface-different-sense* gold do not exist; they would have to be created (§29 lists them as required fresh gold).

## 4. Data exposure state (contamination audit repeated across CR-001…CR-017; `contamination_audit.json`)
| group | sections | state |
|---|---|---|
| Exposed (labels and predictions inspected) | P&D 1.1–3.5 (ch1–3, 24); 1.5, 2.6 (CR-012 pilot); 4.4, 4.5, 5.4, 6.3, 7.1, 8.2, 9.3 (CR-012 held-out); 4.1, 9.2 (CR-014 pilot); 4.2, 5.3, 6.1, 6.4, 7.2, 8.3, 8.4, 8.5 (CR-014 held-out, run once and error-analysed) | development only |
| **Gold drafted, never predicted or scored** | **4.3, 6.2** (CR-015 pilot): `data/gold/cr015_pd_pilot_gold_draft.csv` (2,179 rows, 338 concepts, 1,841 mentions; `MODEL_GENERATED_DIAGNOSTIC`, sha `d4a42290…`) | text sent to the gold-drafting model (`cr015_gold_draft` v1; 2 snippet hits for 4.3, 1 for 6.2 in the 31,187 logged prompts); **no extraction, selector or verifier output exists for them**. Not "untouched" in the strict sense; usable as pilot/development, not as a held-out |
| **Untouched, no gold, no prediction** | **5.2** (12,799 w), **6.5** (9,160), **9.1** (10,197), **9.4** (9,676) = 41,832 words; plus tiny **5.1** (957), **8.1** (662) | 0 prompt-snippet hits, in no gold sheet, no CR-016 corpus/query file (CR-016 files list none of the 8), no output keyed by their ids, `heldout_sealed`/reserve in `cr015_manifest.yaml` (sha `0c55ce26…`) |
Textbook text is public (CC BY 4.0) and may have been seen by models in pre-training — uncontrollable, stated limitation. Frozen source order = book order (chapter, section); words before each fresh target in that order: 5.2 → 92.7k, 6.5 → 132.2k, 9.1 → 171.9k, 9.4 → 192.6k (total ch.1–9: 202,279). Fresh data allowed budget: **at most the 4 held-out + 2 tiny**; there is no further untouched text, so no replacement exists if one is spoiled.
Gold provenance everywhere in P&D ch.4–9 is `MODEL_GENERATED_DIAGNOSTIC`; the one filled boundary-audit sheet is model-filled. Results are *agreement with frozen benchmarks*, not human-validated accuracy, unless Research/owner supply human review (§29 preferred `HUMAN_REVIEWED_MODEL_DRAFT`).

## 5. Feasibility of the Track B statistical design
- Auto-link gate: SAME_EXISTING precision ≥ 0.98 **and** Wilson lower bound ≥ 0.95. With zero errors the Wilson bound reaches 0.95 only at **n ≥ 73** link predictions; at n = 58 (the whole residual dev population) even a perfect run gives 0.938, and one error gives 0.909. Because most true links are already made by deterministic rules (563 of 621), the *verifier's* qualifying links number far fewer than 73 in development; in the 4 fresh sections an estimated ~14 residual cases (58 per 17 sections). **Automatic linking cannot be supported by data in this CR**; per §26 the arm can still qualify as review/ranking assistance, and mutation stays disabled (§21).
- ID2-vs-ID3 (+0.03 F1 / +0.05 low-overlap recall) on a few dozen cases is not detectable; CR-016's retrieval gain was +0.026 Recall@5 on 1,140 cases. Honest outcome space: "no detectable difference → prefer dense" (already the §26 rule).
- Fresh causal evaluation needs a **cumulative book-order run** (never done; CR-016 STOP 3 was not run): every arm processes all earlier sections to build its own registry and memory (≈ 192k words before 9.4). Mechanically feasible; expensive in time (≈ 1–1.5 h per 40k words per LLM arm, sequential).

## 6. Integration points, trace changes, test plan
- **Integration (new code only, under `src/cumap/cr018/`; no frozen file edited):** `boundary_validator` (family-aware, filters `selected`), BA2 pipeline = `selector outcome → validator → verify_selected (unchanged) → family_grounded`; `identity_consumer` + `identity_evidence_packet` after the existing guard chain, writing prediction/review records only; `causal_identity_memory` = adapter over `cr016/run_retrieval.py` records with dense/HippoRAG parity.
- **Trace:** `explain/trace.py` `Stage` already has `proposal`, `boundary_repair`, `boundary_family`, `concept_validity`, `mention_placement`, `adjudication`. Additive CR-018 stages needed: `boundary_validate`, `memory_query`, `memory_retrieval`, `identity_candidate`, `identity_verify`, `identity_decision`, `memory_update`; every model event stores model id, prompt version, config hash, input/output refs, locators, decision code (no reasoning text).
- **Test plan:** the §36 contract maps to `tests/test_cr018_*.py` with fixtures in `tests/fixtures/cr018/{boundary,identity,memory,combined}`: offsets exact, family alternatives visible, no invented text, nested survival not suppressed by longest-match, UNCERTAIN never silently accepted, held-out never reaches demo retrieval; boundary rejection never reported as `REJECT_NOT_CONCEPT`; identity safety (DIFFERENT vetoes SAME, RELATED never merges, same-surface-different-sense stays separate, target must be in the packet, no production mutation); causal memory (section n cannot retrieve n or later, independent index per arm, index only after freeze, future retrieval hard-fails); dense/HippoRAG parity; reproducibility pins (code revision, model ids, prompt/config/source-order hashes, HippoRAG commit, seeds). Tests use `CUMAP_LLM_BACKEND=mock`; none touch network.
- **Human boundary-audit plan (STOP 2, not run):** reuse `audit_sample.py` to draw ~120 exposed families blind (no gold, no selector output, no verdict), key hidden, **filled by the owner (human)**; if time is short, a 30-family subset is enough to measure whether the existing model-filled labels can be trusted (agreement/κ). Output decides the inner-vs-outer convention before any BA2 prompt is written. Fresh sections are not used.

## 7. Cost preflight (estimates from measured rates; no call made)
Measured: A2 (selector+V3 verifier, 50.5k words) $0.581 / 550 calls; A3 $0.584; B1 $0.244 / 299 calls; U0 ≈ $1.1 per 40k words; canonicalisation ≈ $0.0165 per 1k words; HippoRAG indexing $0.43 for the 2,071-paragraph CR-016 corpus (165k words) and query filtering $0.38 per 1,140 queries; CR-016 total $0.81.
| step | basis | estimate |
|---|---|---|
| BA1 | saved artefacts, replayed | **$0** (done) |
| BA2 (validator + frozen verifier rerun on approved spans) | dev 50.5k words, ≈ A2-sized selector-like stage + verifier | ≈ $0.6–0.9 (≈ 15–25 min per 10k words, sequential) |
| BA3 (+ contrastive demonstrations, hard-negative bank reused) | A3 ≈ A2 cost | ≈ $0.7–1.0 |
| BA4 (optional, UNCERTAIN only) | small subset | ≤ $0.2, only if justified |
| ID1 / ID2 / ID3 development | ≤ a few hundred verifier calls ×3 arms (bulk tier ≈ $0.0003/call); CR-016 index reusable from cache | ≈ $0.2–0.8 per arm; HippoRAG re-index $0–0.5 |
| Optional combined C0–C3 | 4 cells on dev | ≈ $2–4 |
| **Development total (both tracks)** | | **≈ $3–7** |
| Fresh Track A (4 held-out 41.8k w + pilot 8k w): BA0 + BA1 + BA2/BA3 + verifier | | ≈ $4–6 |
| Fresh causal identity (3 arms × cumulative run to 9.4: shared extraction ≈ $5.3 + per-arm canonicalisation ≈ $3 + verifier + HippoRAG index/filter) | 192k words | ≈ $14–20, ≈ 12–18 h wall-clock |
| **Overall envelope** | | **≈ $20–30** if everything runs; fresh stages only after a development pass |
Suggested cap: **$8 for development (STOPs 2–5)**; fresh stages need a separate approval with their own cap (≤ $25 as in CR-016). No call has been or will be made before approval.

## 8. Technical blockers and flags (no method substituted)
1. **Which concepthood verifier is "frozen" (D1).** V3's verifier already contains a boundary verdict (rejected 226 exact-gold surfaces as `REJECT_PARTIAL_OR_WRONG_BOUNDARY` in CR-014); B1 removed it and lost precision (0.665 → 0.587). Stacking a new boundary validator before V3 gives two boundary checks; before B1 it is the first dedicated one (the design CR-015 aimed at). Both are mechanically supported.
2. **Gold convention and provenance.** Model-generated gold under-marks nested/independent terms (~31% of unmarked candidate spans judged valid); gates are agreement with this gold. Human audit is a STOP 2 prerequisite for credible tuning.
3. **Fresh data is nearly exhausted:** exactly 4 untouched held-out sections (+2 tiny) with no gold; pilot sections 4.3/6.2 have model-drafted gold. A held-out gold for 41.8k words needs an annotation pipeline and (preferably) owner review.
4. **Track B statistical power and missing identity gold (§3, §5).** Needs new cross-section identity labels; auto-link gate unsupportable by sample size.
5. **HippoRAG is alpha and slow** (query latency 2.28 s vs 9 ms; model call per query; 25 min indexing for 2,071 paragraphs); runs only in `.venv-hipporag` (gitignored; recipe in CR-016 reconciliation) — reproducible but not committed.
6. **CR-016 STOP 2B result stands:** under the frozen canonicalisation memory changes 0 decisions; Track B therefore deliberately uses a *new* consumer, which is exactly the "alternative consumer" CR-016 deferred.
7. Pre-existing lint findings (12, CR-014/015/016 files) and the SciNLP Relation Macro question from CR-017 remain open; neither blocks CR-018.

## RESEARCH DECISION REQUIRED
- **D1 Verifier for BA2/BA3:** (i) V3 verifier (frozen tag), (ii) B1 concepthood-only (design-frozen, not adopted), or (iii) both as BA2a/BA2b with one declared primary before any call (my recommendation: (iii), primary = (ii) because it is the CR's stated separation; extra cost ≈ $0.2).
- **D2 Human audit:** confirm the owner will label the blind sample (120 families, or a 30-family subset) before BA2 prompt design; if not, state that BA2/BA3 results are agreement with the model-generated convention only.
- **D3 Fresh allocation:** approve pilot = 4.3 + 6.2 (model-drafted gold exists, no predictions ever run; treated as development-level, not fresh), held-out = 5.2, 6.5, 9.1, 9.4, reserve = 5.1, 8.1 (tiny, unusable as held-out); and who produces/reviews held-out gold (model draft + owner review, labelled `HUMAN_REVIEWED_MODEL_DRAFT` only if the owner truly reviews every annotation).
- **D4 Track B scope:** (i) accept that auto-link cannot be supported and Track B can at most qualify as review/ranking assistance, (ii) approve building development identity cases from the CR-016 residual/alias/acronym/low-overlap slices with cross-section gold labels (≈ 150–250 cases; who labels, model or owner), or (iii) widen the case pool (e.g. a cumulative run over ch.1–3 with the real registry) before STOP 4.
- **D5 Budget:** approve a $8 development cap (STOPs 2–5); fresh-stage budgets to be requested after a development pass.
- **D6 Sequencing:** proceed to STOP 2 (boundary convention audit: human sheet only, $0) once D2 is settled; STOP 3 is not started.

## Artefacts and hashes
`reports/cr018/contamination_audit.json`, `reports/cr018/stop1_replay.json` (sha `1a080c7d…`), this report. Freeze hashes re-verified today: `FREEZE_V3` (43), `FREEZE_A2` (24), `FREEZE_SCORER` (5), `FREEZE_STAGEB_DESIGN` (3), all matching; CR-016 stage-2 corpus/queries/key hashes match `benchmark_stats.json`; `reports/cr015/stage_ab_results.json` sha `48cb50fd…`.
