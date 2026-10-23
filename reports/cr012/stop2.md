# CR-012 STOP 2 - evaluation infrastructure and P&D gold freeze ($0, no model evaluation)

Research rulings D1-D4 (2026-10-09) are implemented as stated. No SciNLP test document and no P&D held-out section was run through any model; the SciNLP test gold was read once, as data, for the string-isolation scan only.

## 1. What was built (`src/cumap/cr012/`, 45 new tests)

| module | content |
|---|---|
| `adapters.py` | `BenchmarkAdapter` interface; `SciNLPAdapter` (release label `SciNLP-repo-e78342be`): loader, lossless detokenisation with exact token-to-character offsets, gold mentions / relations (inclusive source boundaries converted to half-open spans), the paper's domain / range, symmetric set {compareWith, similarWith}, no gold clusters, no official scorer (`official_score` raises) |
| `scoring.py` | the **CR-012 SciNLP strict scorer** (entity span / typed; Rel; Rel+; symmetric orientation-free; node edges projected to the mentions inside their own evidence span, ungrounded edges counted not guessed; D1 aggregation: micro, per document, macro mean, min / max F1, `CI_status = NOT_EVALUABLE_SMALL_N`) and the **P&D canonical-graph scorer** (headline `STRICT_E2E_EDGE_F1`, canonical-node, mention, pairwise identity and B-cubed, pair recall with the endpoint-exists denominator, conditional relation / direction and confusion) |
| `oracle.py` | E1 (gold spans + types only), E2 (adds identity; raises `NOT_SUPPORTED_NO_IDENTITY_GOLD` for SciNLP), E3 / E3-M (endpoint pairs, relation and direction hidden: pairs are handed over unordered), E4 / E4-M; leakage guard; whole-token leakage scan |
| `attribution.py` | earliest-failure codes N0, N1, C0, C1, P0, R0, R1, R2, R3, E0 with the stated precedence; S0 / S1 not applicable; trace builder and distribution |
| `bootstrap.py` | grouping-aware percentile bootstrap (units = documents or sections, never edges), paired delta on the same units, fixed seed, `DESCRIPTIVE_SMALL_N_ONLY` for fewer than 10 units |
| `stability.py` | run store (never overwritten), `assert_independent` (distinct ids and cache namespaces), node-set / edge-set Jaccard, canonicalisation and relation disagreement, no best-run field, per-run private LLM cache (`client_for_run`) |
| `budget.py` | D3: `B(u) = min(pool, max(1, ceil(14.2 * words / 1000)))` and the per-unit log record (words, eligible pairs, budget, selected, saturation, gold-edge pair recall) |
| `pd_e2e.py` | label-blind section selection, blind annotation sheets, gold loader / validator (character spans, registry relations, relation-specific qualifiers, evidence sentences), codebook generator |
| `isolation.py`, `cost.py` | isolation scan against all prompts / configs; cost preflight |

Scoring rules that the CR leaves open (fixed here, tested): predicted items are de-duplicated by match key; every extra predicted item that maps to an already matched gold item is a false positive (a split canonical node costs precision); a gold item is recalled at most once; a node whose mentions hit two gold concepts is a false merge and matches nothing; identity is never inferred from strings.

## 2. P&D-E2E selection (frozen before any final CUM prediction exists; `data/interim/checks/cr012/pd_e2e_selection.json`, sha256 `85d09ec9fc2866fa...`)

- Rule: eligible = 1,200-5,500 words; pilot from chapters 1-3 (already developed), held-out from chapters 4-9 (no CR-005..011 run touched them); seed 20261011; a seeded draw per chapter plus a seventh from the chapter with most eligible sections left. Chapter, length and structure only.
- **Pilot (2):** 1.5 (1, 3643 words, 135 sentences), 2.6 (2, 2921 words, 124 sentences).
- **Held-out (7):** 4.4 (4, 4091 words, 175 sentences), 5.4 (5, 4597 words, 181 sentences), 6.3 (6, 4108 words, 173 sentences), 7.1 (7, 4799 words, 223 sentences), 8.2 (8, 4110 words, 174 sentences), 9.3 (9, 5093 words, 217 sentences), 4.5 (4, 3255 words, 131 sentences); 30053 words in all.
- Double annotation (about 29%): 4.4, 9.3, when a second human exists (an LLM does not count).
- Stability subset (length rule: the two shortest): P&D 4.5, 4.4; SciNLP test documents `P17-1058.grobid`, `2021.acl-long.353`.
- Process note: the first cap of 4,500 words left chapters 5, 7 and 9 without an eligible section (4 held-out sections); it was widened to 5,500 before the freeze to meet the required 6-8 sections. No prediction or label existed at that point.
- Blind sheets: `pd_e2e_pilot_blind.csv` (259 sentences, sha256 `9928071b155603f9...`) and `pd_e2e_test_blind.csv` (1274 sentences, `7aafea45acb17817...`): section and sentence rows only, nothing from any model. Codebook: `docs/annotation/pd_e2e_codebook.md` (generated from the registry). Gold qualifiers asked of annotators are the relation-specific ones (part_type, action_type, ...); polarity and modality are optional because the system attaches them to every edge.
- Annotation load for the owner: pilot about 6.6k words; held-out about 30k words (1,274 sentences). The pilot is needed for STOP 3; the held-out can be annotated in parallel.

## 3. Isolation

`reports/cr012/isolation_scan.json`: 59 development artefacts (all prompts and configs, including few-shot banks, lexicon and cues) scanned; 122 multi-token SciNLP test surfaces and every 8-gram of the 7 held-out sections: verdict **CLEAN** (no hits). A hit would be reported, not ignored.

## 4. Cost preflight refresh (D4: soft $40, hard cap $50, mandatory scope)

Upper (no cache sharing) **$44.81**, lower (byte-identical calls reused) **$36.93**: pilot $6.94, P&D held-out $18.78-14.35, SciNLP held-out $10.26-7.29, stability $8.83 (never shared). Below the hard cap; the upper figure is above the soft warning. P&D gold-edge density is an assumption until the pilot gold exists. Refreshed again with measured numbers after STOP 3; STOP 4 does not start if the projection exceeds $50.

## 5. Choices made inside the approved design (for visibility; none changes a ruling)

- SciNLP projection of canonical-node edges to mentions uses the mentions inside the edge's evidence span only.
- P&D matching counts duplicates as stated in section 1; endpoint types are part of the headline match (typed).
- Stability subset chosen by length; the SciNLP pair comes from the test split (it is a stability repetition of the frozen workflow, not tuning).
- SciNLP text is rebuilt by joining tokens with single spaces (lossless offsets), which differs from natural punctuation spacing; the same text is fed to the pipeline and to the scorer.

## 6. Status and next step

STOP 2 is complete; nothing here needs a Research decision. **Needed from the owner for STOP 3:** annotate the 2 pilot sections (`pd_e2e_pilot_blind.csv`, codebook above) and save the marked copy to the gold folder; the held-out sheet can follow in parallel and stays unopened by any pipeline code. STOP 3 then validates the scorers on SciNLP train / dev and the pilot, runs the cost-measuring rehearsal and freezes `configs/cr012_e2e_eval.yaml`.
