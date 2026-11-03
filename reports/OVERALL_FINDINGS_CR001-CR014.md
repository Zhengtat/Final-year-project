# Overall findings, CR-001 to CR-014

Written for: the project owner, supervisor and examiners. This is a cross-CR summary compiled by hand on 2026-10-13 from the committed reports and logs. It is **not** script-generated, and it adds no new measurements. Every number below is copied from the source named in each section; if a number here disagrees with its source, the source is right. CR-015 (in progress) is out of scope.

**Scope reminder.** On 2026-09-28 the owner limited work to the expert knowledge graph. The student side (M4 silver labels, M6 student extraction, M7 diagnosis, M8) is deferred, so **nothing here measures student diagnosis**. All results concern building the expert KG from Peterson & Davie (P&D), with IIR (FACE) and SciNLP as external benchmarks.

**Label provenance.** Precision figures come from owner (single-annotator) blind spot-checks unless stated otherwise. CR-012's P&D held-out gold is a single-annotator graph built from an owner-reviewed LLM prefill. CR-014's gold is **model-generated** (accepted provisionally by the owner) and is labelled that way wherever it is used. No result has a second human annotator, so inter-annotator agreement is never available.

---

## At a glance

| CR | Topic | Outcome | Headline finding |
|---|---|---|---|
| 001 | Relation registry v1, tiers, escalation | Done | Infrastructure. The relation-agreement sampler fell short (30 of ≥48 items) and was superseded by CR-003 §6. |
| 002 | Calibrated concept confidence | Not implemented | — |
| 003 | Reduce manual labelling | Partly used | Its IIR/FACE benchmark design was carried out inside CR-005 (results there). |
| 004 | Knowledge organisation layer | Not run | — |
| 005 | Expert-KG demo slice (P&D ch2–3) | Done | Edge precision 23/30 = 0.767. IIR test lenient F1 0.568. Merge precision 41/43. Finding: candidate-pair explosion. |
| 006 | Knowledge sphere (core–periphery) | Done (STOP 4 deferred) | A core exists but sits only modestly above hub-heavy random graphs. Most concepts are unlinked. |
| 007 | Extraction v3 | Done | Accepted edges 31.8% → 42.4% of classified pairs; linked share 14% → 38%. Three gated relations dropped (registry v1.1.1). |
| 008 | Merge rules, lexicon, misconception layer | Done | Deterministic alias rules: 0 owner-wrong merges. Textbook misconception cues are rare (2 warnings from 89 candidates). |
| 009 | Concept stage v4 (KG-aware generator, anchors) | Done | Edge precision 27/30 = 0.90. Anchored concepts 93% valid vs independent 36%. Linked share 48%. |
| 010 | Node recall + eRST relations | Closed: DUAL_LAYER | eRST cannot replace domain relations (91.4% mapping loss). Its pair routing is useful (P1 pair recall 77%). |
| 011 | Sleep-phase consolidation | Closed: NO_PRODUCTION_CHANGE | Few residual duplicates (3.75%). Rankers at chance (AUC 0.40–0.55). |
| 012 | End-to-end evaluation | Complete | Strict end-to-end edge F1 is low (P&D 0.053, SciNLP 0.050). The bottleneck is pair/endpoint delivery, not relation classification. |
| 013 | Process explainability | Complete | 100% trace coverage of concepts and edges. Explainability only; no accuracy claim. |
| 014 | Recall-first concept extraction | Scientific success, not adopted | Held-out ΔF1 +0.038, recall +0.107, but precision −0.074 fails the −0.02 floor. Production stays U0. |

### Trajectory of the main owner-checked quality numbers (P&D)

| Metric | CR-005 (`pdcanon2_30e2b4f9`, ch2–3) | CR-007 (`slice3_a1`, ch1–3) | CR-008 (`slice3_b4`) | CR-009 (`slice3_c2`, current production) |
|---|---|---|---|---|
| Strict edge precision (owner, Wilson 95%) | 23/30 = 77% [59, 88] | 29/39 = 74% [59, 85] | — | **27/30 = 90% [74, 97]** |
| Merge precision (owner) | 41/43 = 95% | 23/24 = 96% | 0 owner-wrong auto-merges | — |
| Concepts / accepted edges | 736 / 121 | 982 / 297 | 913 / 294 | 1,243 / 529 |
| Linked share, all / `defined` concepts | 14.1% / 14.9% | 38.4% / 43.5% | 39.5% / 44.9% | **48.1% / 56.2%** |

Note: the CR-005 run covers ch2–3 only; the rest cover ch1–3. These are spot-check precisions on samples of 30–39 edges, not recall.

### IIR (FACE) concept extraction, exact micro F1 on the full test split (70 sections)

| Version | Exact F1 | Lenient F1 | Source |
|---|---|---|---|
| v2 (CR-005 prompt) | 0.433 | — | `reports/cr009_stop2_dev.md` |
| v3 (CR-007, v2 + propagation) | 0.485 | 0.633 | `reports/cr007_stop2_concepts.md` |
| v4 (CR-009, production U0) | **0.501** | 0.592 | `reports/cr009_stop2_dev.md` |
| v4 + N1 (CR-010, not adopted) | 0.510 | — | `reports/cr010_stop2_test.md` |
| FACE (supervised, different protocol) | 0.76 | — | published |

CR-005's own test figure (lenient 0.568, exact 0.474) covers chapters 4, 6 and 9 only, so it is not comparable with the rows above.

---

## CR-001 — Relation registry v1, edge qualifiers, LLM tiers and escalation

Source: `docs/PROGRESS.md`, `docs/DECISIONS.md`, `reports/migration_v1.md`.

Mostly infrastructure: registry v1, the versioned validator, the migration tool, v2 prompts, and strong/bulk/ceiling tiers with one-step escalation. Findings worth keeping:
- The v2 expert-drafting prompts produced 0 evidence-check rejections on the 5 pilot questions (12 chain links).
- The relation-agreement sampler yielded only 30 stratified items against a target of ≥48. It was superseded by CR-003 §6 rather than fixed.
- `gpt-6-sol` was verified with a real call before it became the strong-tier default. `gpt-6-astra` is opt-in only.

## CR-002 — Calibrated concept confidence

*(No findings. Not implemented; `concept_score` is not stored on graph nodes.)*

## CR-003 — Reduce manual labelling

*(No standalone findings. Its benchmark plan, IIR/FACE concept extraction with borrowed human labels, was run as part of CR-005; see there. The student-side parts are deferred with the scope decision.)*

## CR-004 — Knowledge organisation layer

*(No findings. Not run; its `instantiates` patch is still reserved as registry v1.2. CR-006 built the structural "sphere" view separately.)*

## CR-005 — Expert-KG demo slice

Source: `docs/PROGRESS.md` (M5.0), `docs/DECISIONS.md`. Run `pdcanon2_30e2b4f9`, P&D ch2–3.

1. **Candidate pairs grow far faster than concepts.** Before capping there were 10,012 candidate pairs (about $94 to classify). Section-level candidate generation was not affordable. This led to sentence-level pairing, a 30-per-section cap and run-wide deduplication. An earlier IIR-dev relation run was aborted at $14.03 with zero output: pairs were not deduplicated across sections, and the budget was only checked at chapter boundaries.
2. **Canonicalisation over-merges kinds into categories.** For example HDLC→SDLC, Internet→internetworking, CRC→error-detecting code (3 wrong in a sample of 20). Fixed with the canonicalize v2 rule "kind/instance/part/version is never *same*". Owner check after the fix: **41/43 = 0.953 [0.845, 0.987]**.
3. **Relation extraction:** 121 accepted edges from 381 pairs (32%). 48% of family-cleared pairs ended as `other`, and there were only 2 mechanism_process edges.
4. **Owner spot-check, strict precision 23/30 = 0.767 [0.591, 0.882].** Ignoring direction it was 25/30. The 46% "reversed" flag was a false alarm: the reversal was right in 7 of 8 cases. Failures traced mostly to **concept granularity** ("bit" vs "bit rate", "switch" vs "switching") and to lists of alternatives being read as contrasts.
5. **IIR (FACE) concept extraction:** dev lenient micro F1 0.539 (v1) → 0.612 (v2 prompt). Test (ch4/6/9) lenient 0.568, exact 0.474. The first test figure (0.407) was wrong because the scraped text was wrong (gold-term presence was 53%); it was corrected after a validated re-scrape (98.7% presence).
6. A real bug was found: snapshots ignored an edge's `reversed` direction. After the fix, 27% of edges fail domain/range checks, mostly because nodes are typed with the generic `Concept`.

## CR-006 — Knowledge sphere

Source: `reports/organisation_org_f3c0874b.md`, `docs/PROGRESS.md` (M5.0b).

1. **A core–periphery structure exists, but it is weak.** On ch2 Δρ = 0.179 (z 4.6) and on ch3 Δρ = 0.160 (z 7.5). A hub-heavy Barabási–Albert reference gives Δρ 0.08–0.14, and a degree-preserving null explains most of the signal (residual 0.040 / 0.005). Later runs fall to a "weak core": Δρ 0.030–0.043 in CR-008 and CR-009.
2. **Most concepts have no typed edge.** On ch3, 632 of 736 are unlinked, with 344 flagged as persistently unlinked. This is a relation-recall signal, not a sign of unimportant concepts, and it motivated CR-007.
3. **The core is fairly stable between chapters:** ch2→ch3 core Jaccard 0.62, Kendall τ 0.73.
4. **Late-counted edges:** 15 of 87 ch2 edges were counted in ch3 because ch2 extraction missed concepts present in its text. CR-007 fixed this by setting first occurrence through longest-match.

## CR-007 — Extraction v3

Source: `reports/cr007_stop4.md`, `reports/cr007_stop5.md`, `reports/cr007_stop2_concepts.md`. Run `slice3_a1`, P&D ch1–3.

1. **Coverage-aware pair selection and longest-match mentions fixed most of the linkage gap.** Accepted edges rose to 297 of 700 classified pairs (42.4% vs 31.8%). The linked share of all concepts went from 14.1% to 38.4%. mechanism_process edges went from 2 to 42. Late-counted edges fell from 15 to 0.
2. **The OTHER share fell (30.7% → 20.9%) but missed the ≤15% target.** The missed-relation estimate is 28% (Wilson 17.5–41.7%, n=50).
3. **Precision held:** edges 29/39 = 74% [59, 85]; merges 23/24 = 96%. By family, cause_effect and dependency are weakest (1/3 each); comparison and function_means were correct in every sampled case.
4. **The pre-registered relation gate removed three relations.** `identifies` scored 5/8 = 62% (< 80%), and `encapsulates` and `trades_off_with` had too few instances. The result is registry v1.1.1. Of the new relations, `acts_on` (35 instances, 5/5) and `connected_to` (10, 4/5) were kept.
5. **IIR full test, exact micro F1 0.485** (v2 0.433). It came from free consistency propagation (E3), which won the dev ablation (lenient 0.656 vs 0.612). CR-009 later removed E3.
6. **The `corrects_intuition` flag is unreliable when set by the model.** About 3 of 4 flags were genuine. The prompt's cue list ("note that … does not") fires on ordinary caveats.

## CR-008 — Merge rules, lexicon, equivalence, misconception layer

Source: `reports/cr008_stop1.md`, `reports/cr008_stop2.md`, `docs/PROGRESS.md` (M5.0d). Final run `slice3_b4`.

1. **Deterministic alias rules are safe.** The backtest against both owner merge sheets (83 rows) merged 37 owner-"same" pairs and **0 owner-wrong** pairs. Applied precision was R1 1/1, R2 10/10 and R3-strong 2/2.
2. **Treating equivalence as a node property costs almost nothing.** Nodes went from 982 to 913 and edges from 297 to 294. All 3 `equivalent_to` edges were migrated (2 merged, 1 retired), leaving 0 self-loops, conflicts or cycles.
3. **Explicit misconception warnings are rare in a textbook.** 89 cue candidates gave 2 warnings, 1 item for review, 10 needing a correct edge, and 75 plain facts. The owner judged 4/5 correct (Wilson [0.38, 0.96]). Cue recall was not measured because the recall sheet was not marked.
4. The lexicon matches only exact surface forms (bare "HDLC"/"SDLC" are not recognised); the CR-010 audit found this.

## CR-009 — Concept stage v4 (KG-aware generator, rule verifier, anchors)

Source: `reports/cr009_stop3_c2.md`, `reports/cr009_stop2_dev.md`, `docs/DECISIONS.md`. Run `slice3_c2`, **the current production graph**.

1. **Anchoring concepts to the growing graph is the strongest quality lever found so far.** Owner marks: anchored concepts 13/14 = 93% valid vs **independent 4/11 = 36%** (mostly generic words). Anchors were correct in 18/18, and non-trivial generator links in 16/16.
2. **Strict edge precision 27/30 = 90% [74, 97]**, the best of any run. Anchor-derived edges scored 15/15 and others 12/15. 53% of anchor pairs became accepted edges.
3. **Linkage improved:** 1,243 concepts and 529 edges (vs 913 and 294). The linked share went from 39.5% to 48.1% (defined concepts 56.2%).
4. **IIR full test exact micro F1 0.501** (v3 0.485). It leads every comparison arm (C-PiVe 0.458, C-SAC 0.399, C-ConExion 0.378), but no paired interval was computed, so the gain over v3 is within noise. Lenient F1 is lower than v3 (0.592 vs 0.633).
5. **The corrective verifier loop adds recall but loses precision on dev** (recall 0.497 → 0.526, precision 0.490 → 0.438). Depth 1 was chosen.
6. The pruner is out of domain on P&D (trained on IIR dev rows) and is off in production.
7. **Live runs are not deterministic.** The same frozen configuration moves by about 0.03 F1 between live runs, which is larger than many arm-to-arm differences. This was found in CR-010 STOP 2.

## CR-010 — Residual node recall and eRST relation evaluation

Source: `reports/cr010_decision_report.md`, `reports/cr010_stop2_test.md`, `reports/cr010_stop4a.md`, `reports/cr010_p3.md`, `reports/cr010_stop5.md`. Research decision: **DUAL_LAYER**.

1. **Node-recall post-passes help only slightly.** On IIR test (held out, run once), N1 scored 0.510 vs frozen N0 0.501 (+0.009, bootstrap [+0.005, +0.014]). A fresh N0 replication scored 0.486 (−0.015), so the gain is smaller than run-to-run variance. Nothing was adopted.
2. **eRST cannot replace the domain relation layer.** On 81 held-out REL-MAP items: expressibility 27.2%, semantic preservation 8.6%, total mapping loss 91.4%. Losses fall mainly on mechanism (33%), part/whole (21%) and taxonomy (15%). The claim is limited to this evidence, which is mostly single-sentence.
3. **eRST is useful for routing candidate pairs.** Pair recall within the P2 universe was P0 (current) **14.9%** [12.6, 17.6] and through P1 **77.4%** [70.4, 83.9]. In the P3 universe the figures were P0 12.5%, P1 64.9% and P2 83.8%. eRST-linked P3-extra pairs were 42.0% human-true, about 1,070 estimated true edges.
4. **Candidate discovery and relation classification are separate bottlenecks.** Classifier recall on human-true P3-extra pairs was 37% (precision 72%).
5. These recall figures are **within the enumerated candidate universe**, not global textbook recall. IAA was not evaluable (no second annotator).

## CR-011 — Sleep-phase identity consolidation

Source: `reports/cr011_sleep/final_report.md`. Research decision: **NO_PRODUCTION_CHANGE**. $0 API.

1. **Few duplicates remain after canonicalisation.** SLEEP-240 dev had SAME 3/80 = 3.75% [1.3, 10.4]. Even the positively enriched SLEEP-POS dev had only 8/80 SAME, which failed the ≥20 viability gate.
2. **Most high-similarity residual pairs are related but distinct** (59 of 71 negatives were related_other, kind_of or confusable).
3. **Local rankers could not separate duplicates from related concepts.** Out-of-fold AUC was 0.40–0.55 across 9 configurations.
4. **A hard type guard can veto a genuine duplicate.** "spectrum" (Parameter) vs "electromagnetic spectrum" (Concept) was vetoed, which capped review recall at 13/14. Node-type noise makes hard identity guards risky; a soft-conflict → review design is proposed for any future CR.
5. Held-out sets remain sealed; no held-out result exists.

## CR-012 — End-to-end evaluation

Source: `reports/cr012/FINAL_EVALUATION.md`, `reports/cr012/oracle_error_attribution.md`. One frozen held-out execution (`cr012-stop4-complete`). $25.93.

1. **Strict end-to-end accuracy is low.** P&D (7 held-out sections) STRICT_E2E_EDGE P/R/F1 = 0.092 / 0.038 / **0.053** [0.030, 0.076]. SciNLP (3 docs) strict relation P/R/F1 = 0.364 / 0.027 / **0.050**. The schemas differ, so these two numbers are not comparable. The expert KG must not be described as validated or high-accuracy.
2. **The P&D bottleneck is pair and endpoint delivery.** 73.8% of the earliest E0 misses are extraction or pair delivery, and pair recall at E0 is 16.3% (53/326). The biggest oracle uplift is E2 → E3, from 0.129 to 0.398.
3. **Relation classification is much better than E0 implies:** 70.4% of relations and 69.4% of directions are correct on oracle (E3) pairs. E4 at 0.470 is a ceiling that assumes gold endpoints.
4. **Canonicalisation is not the dominant held-out bottleneck** (E1 0.113 → E2 0.129). The dev pilot suggested otherwise; the held-out result takes priority.
5. **The SciNLP bottleneck is entity extraction:** 89.8% of E0 misses (E0 0.050 → E1 0.255).
6. Stability across three repeats is modest; P&D section 4.4 ranges from 0.022 to 0.072 F1. The pair budget (14.2 pairs per 1k words) was saturated in all 10 held-out units, so the pair-delivery findings are specific to that budget.

## CR-013 — Process explainability

Source: `reports/cr013/FINAL_EXPLAINABILITY.md`. Explainability and observability only; **no accuracy claim**.

1. **Full lineage for the production graph:** 1,243/1,243 concepts and 528/528 edges trace back to resolvable source evidence. All 10,569 evidence locators resolve, and 98.0% of quotes are found in the section they are attributed to.
2. **Explanations are faithful to the traces:** 100% of the 111,936 values rendered into explanation text equal their trace field. The JavaScript and Python renderers agree on all 36,730 events.
3. **The legacy run is missing some decision records:** alias provenance, blocked merges, generator-call links, relation confidence and rejected alternatives were never recorded. They are shown as NOT_RECORDED (6,201 fields), not inferred. 76 section-attribution mismatches were found and left as-is.
4. Accessibility: axe WCAG A/AA found 0 violations in 17 states. Usability with real readers was **not evaluated** (no readers were recruited).

## CR-014 — Recall-first concept extraction

Source: `reports/cr014/heldout_results.md`, `reports/cr014/downstream_compatibility.md`, `reports/cr014/fp_audit_result.md`. **Gold is model-generated; every number is agreement with that annotation.**

1. **Recall-first proposal generation improves coverage.** On 8 sealed P&D sections (mention-level, span-exact), U0 scored P/R/F1 0.749/0.508/0.605 and V3 scored 0.675/0.615/**0.643**. ΔF1 was +0.038 (section-bootstrap [+0.010, +0.079]), V3 was better in 7 of 8 sections, and one-token recall rose by 0.068.
2. **It is not adopted because precision falls by 0.074 against a floor of −0.02.** The main error is boundary over-extension: 497 over-specific false positives vs 189 for U0. Other losses: 471 rejected by the verifier and 260 at boundary repair. CR-015 targets these.
3. **Downstream cost:** concepts rose 66% and canonical merges ×20. The candidate pool grew 93% while the pair budget stayed at 573, so the share of concepts covered by a selected pair fell from 71% to 48%. Relation calls are flat (+0–8%) because the budget depends on word count. Provenance stays at 100%, and there were 0 lexicon-veto violations.
4. **The IIR gold appears incomplete.** An LLM-labelled audit found 63% (V1) and 90% (V3) of no-overlap "false positives" were valid concepts. This is diagnostic only and was not used for any gate.

---

## Cross-CR conclusions

1. **Precision of what the pipeline asserts is reasonable and improved:** owner-checked strict edge precision rose from 77% to 90%, and merge precision is about 95%. **Coverage is the weak point.** Under strict end-to-end scoring, edge F1 is about 0.05 (CR-012).
2. **The dominant loss is upstream of relation classification.** CR-006 (unlinked concepts), CR-010 (P0 pair recall about 15%), CR-012 (73.8% of misses at extraction or pair delivery) and CR-014 (budget saturation) all point the same way: the right concept pairs never reach the classifier. Given the right pair, the classifier is right about 70% of the time.
3. **Identity resolution is largely solved for the current graph.** Deterministic rules made 0 wrong merges (CR-008), and few duplicates remain (CR-011, 3.75%). Making identity more aggressive mostly hits related-but-distinct concepts, and hard type guards can veto real duplicates.
4. **Grounding concept extraction in the graph helps more than recall-first extraction.** Anchored concepts were 93% valid vs 36% independent (CR-009). Recall-first extraction gains coverage but loses precision at concept boundaries (CR-014).
5. **Variance and gold quality limit fine-grained claims.** Live runs vary by about 0.03 F1, all gold has a single annotator or is model-generated, and the held-out sets are small. Gains under about 0.02 F1 (CR-009 v4 vs v3, CR-010 N1) should be treated as within noise.
6. **The textbook has a weak core–periphery structure** (CR-006, CR-008, CR-009). Organisation views should be read as structural, not as tiers of importance.
