# CR-011 STOP 1 — Repository Reconciliation / $0 Preflight

**Executed:** 2026-10-08 on branch `cr-011-sleep-consolidation` (created from `main` at `089c895`, the CR-010 merge). No paid call was made, no production data was mutated, no gold file was touched. The only run touched was read in memory (a probe of the existing re-key code on `slice3_c2`; nothing was written to `data/processed`).

**Authority used:** `docs/change-requests/CR-011-sleep-consolidation.md` is the amended CR (`CR-011-sleep-consolidation-2.md` in the package, with the CR-012 benchmark-isolation and handoff additions). Package artifacts were copied unchanged into `configs/`, `prompts/`, `docs/annotation/`, `tests/fixtures/sleep/`, `data/interim/checks/cr011/`, `reports/cr011_sleep/` and `docs/cr011/`.

**Production node baseline:** CR-009's final run `slice3_c2` (P&D chapters 1-3). CR-010 closed with `DUAL_LAYER`: its node arms (N1-N3) were not adopted and its eRST graph is a separate candidate-routing layer, so CR-010 did not change node identity.

| Check | Repository evidence | Result | Pass? |
|---|---|---|---|
| Current branch / clean status | `git branch`, `git status` | `cr-011-sleep-consolidation`, clean except the untracked editor workspace file and the new package files | yes |
| CR-010 merged? | `git log` | merge commit `089c895` on `main` | yes |
| `cr-010-complete` tag | `git tag` | present (also `cr-009-complete`, `cr-008-complete`, ...) | yes |
| Actual CR-010 production node configuration | `configs/cr010_node.yaml`, DECISIONS | no CR-010 arm adopted; production nodes = CR-009 (`configs/concept_gvp.yaml`, run `slice3_c2`) | yes |
| Canonicalisation entry point(s) | `expert_kg/canonicalize.py` `canonicalize_mention`; CR-009 caller `concepts_v4/pd_run.py` (stage `canonicalize_v4`); CR-007/008 caller `expert_kg/pipeline.py` `run_canonicalize_stage` | **online, per mention, in book order**: a new mention is compared with the growing registry; "merge" = attach the mention and its name as an alias to an existing node (`merge_alias`). Two existing nodes are never merged by this path | yes |
| Merge/global-sweep entry point(s) | `expert_kg/rekey.py` `rekey_run` / `plan_merges` / `merge_nodes`; CLI `cumap kg rekey` | the only node-to-node merge. A finished run is re-keyed under R0-R3 into a NEW run id | yes |
| Chapter-boundary trigger(s) | none found | no sleep/consolidation trigger exists at chapter boundaries | n/a (new) |
| Final-book trigger(s) | none found | no whole-book trigger; production covers ch1-3 only (24 sections) | n/a (new) |
| Any CR-010-added alias/merge hook | `erst/guards.py` | `same_concept_candidate` effect exists, routed "through the lexicon-guarded merge"; no merge code | yes |
| Active term lexicon file/version | `configs/term_lexicon.yaml` | version 0.3: 77 `same` + 21 `different` entries, all `approved` | yes |
| R0 SAME precedence | `canonical_rules.pair_rule` | order: `different` veto first, then R0 `same`, then type check, R1, R2, R3-strong | yes |
| R0 DIFFERENT absolute veto | `canonical_rules.pair_rule`, `canonicalize._canonicalize`, `rekey.plan_merges` | enforced in rule path, in the candidate list shown to the LLM, and as a clique check on cross-cluster pairs in `plan_merges`. **Not enforced** on the LLM `same` path in `canonicalize_mention` for a candidate the lexicon did not list as a pair (by design) and not on exact-string auto-merge (only `canonical_overrides.never_merge` guards it) | partial |
| R1 exact transformations | `alias_rules.r1_key` | NFKC + casefold, dash/quote unification, article strip, spelling map, head-token lemma, hyphen/space collapse | yes |
| R2 acronym scoping/collision behaviour | `alias_rules`, `canonical_rules` | Schwartz-Hearst pairs; ambiguous short forms are scoped to the chapters they are defined in; R1 acronym vs common-word guard (`common_words`) | yes |
| R3 strong/weak alias behaviour | `configs/alias_rules.yaml` (v0.1-draft) | strong cues merge with evidence; weak cues go to the review sheet only | yes |
| R3 contradiction detection | `rekey.alias_contradictions` | flags a merged alias pair that later co-occurs in a self-loop; not a pre-merge veto | partial |
| R4 prompt/model/config/context | `prompts/canonicalize/v2.md`, strong tier (gpt-6-sol), top-5 candidates, name+definition+evidence | same / broader / narrower / different | yes |
| Fixed 0.70 similarity threshold still active? | `pipeline.py:314`, `pd_run.py:126` (`review_below=0.70`), `canonicalize.py:36` (`DEFAULT_SIMILARITY_THRESHOLD = 0.6`) | **yes**: a 0.6 retrieval floor and a 0.70 review band (provisional, CR-007) are both active in production | yes (S0 baseline keeps them; sleep must not) |
| Other active identity thresholds | `canonicalize.py` | top-k = 5; nothing else numeric | yes |
| `concept_score` affects merge probability? | grep | no `concept_score` exists in the canonicalisation path; no interaction | yes |
| Type compatibility config | `canonical_rules.types_compatible` | **hard-coded**, not loaded from config: equal types, or either side is the generic `Concept` (a wildcard) | **no** (see Decision 2) |
| One-token same-surface auto-collapse possible? | `canonicalize.find_exact_match`, `rekey` R1 key | **yes**: exact (case-insensitive) string match auto-merges with no context or sense check; R1 key equality merges one-token forms | yes (risk) |
| Current transitive clustering behaviour | `rekey.plan_merges` + union-find in `rekey_run` | pairwise rule hits are unioned (transitive closure). Guard on a cluster join: no `different` lexicon entry between any form of the two clusters. **No** type, contradiction, or support check across a cluster | yes (gap) |
| Existing split/over-merge detector | grep | none | n/a (new) |
| Alias provenance completeness | `slice3_c2` checkpoint | **0 of 188 aliases carry an `alias_provenance` record** (field empty); 43 of 187 distinct alias strings match the `alias` of a logged merge event (23%); re-key on the current run raises it to only 2 of 188 | **no** (see Decision 1) |
| Absorbed IDs / `merged_from` lineage | `rekey.merge_nodes` | written by re-key; empty in the production run (0 nodes have `merged_from`) because merges happened online | partial |
| Edge re-keying implementation | `rekey.rekey_results` | pair ids rewritten through `id_map`, `pair_orig` kept; edges keyed by (relation, source, target) | yes |
| Duplicate-edge evidence union | `rekey_results` | duplicates flagged `consolidated_into` with `evidence_all` listing every quote | yes |
| Merge-created self-loop handling | `rekey_results` | rejected with reason `merge_self_loop`, logged in `rekey.self_loops` | yes |
| Description history append-only | `merge_nodes` | survivor history + absorbed history concatenated | yes |
| Evidence retention mapping | `merge_nodes`, `rekey_results` | mentions de-duplicated by (section, quote, role); relation results keep their evidence quotes; no explicit pre-to-post evidence-id map is written | partial |
| Current rollback mechanism | `cumap kg rekey` | re-key writes a NEW run id and never overwrites; rollback = keep using the source run. **No inverse operations are generated** | partial |
| Exact rollback round-trip proven? | in-memory probe of `rekey_run` on `slice3_c2`; code reading | **No.** The post-merge checkpoint alone cannot reconstruct the pre-merge one: absorbed node records are dropped (only ids remain, and only if `merged_from` was set), the survivor's `first_introduced` is recomputed (probe: differs for the one merged node), mentions are de-duplicated, `concepts_before` is deleted. There is no canonical-hash round-trip test. `merged_from` is not sufficient | no (to build in STOP 5) |
| `same_concept` queue | `relations_v3.py:286` | a relation result with outcome `same_concept`, reason `queued_for_merge`: 1 in `slice3_c2`. **Nothing consumes the queue** | partial |
| Misconception layer excluded from normal merge | `rekey.py` | not merged (items sit in `checkpoint.misconceptions`), **but re-key never rewrites their `source_id` / `target_id` / `contradicts` ids**, so merging nodes would leave them dangling | partial (STOP 5 must re-key them) |
| `data/gold` write protection | `tests/test_cr010_nodes.py::test_cr010_code_never_touches_gold_or_the_network`, `tests/test_gold_validate.py`, `test_report.py` | tests exist for `cr010/` and the report builder; no CR-011 module yet | yes |
| CR-006 organisation replay entry point | `cumap kg organise --run <id>` -> `organisation/pipeline.run_organisation` | reads snapshots, writes only under `organisation/<org_id>/`; $0. CR-004 organisation is **not implemented** | yes |
| Current node count | `slice3_c2` | **1,243** nodes | yes |
| Current alias count | `slice3_c2` | **188** aliases on 173 nodes | yes |
| Historical merge event count | `checkpoint.merges` | **172** (generator G-links 140; canonicalisation 32: exact 11, R0 5, LLM 16); 10 rows in `merge_review` | yes |
| One-token merge count | merges where the alias or the node name is one token | **119** of 172 (G-link 105, exact 8, LLM 4, R0 2) | yes |
| Cross-chapter merge count | merge section's chapter != node's first chapter | **81** of 172 (G-link 74, LLM 5, exact 2) | yes |
| Historical owner merge labels available | `data/gold/cr007_merge_sheet.csv` 40 (38 same / 2 different), `cr008_merge_sheet.csv` 15 (15 same), G-link marks `cr009_stop3_glinks_slice3_c1.csv` 15 (4 same / 11 not same) and `cr009_stop3b_..._c2.csv` 16 (16 same); `term_lexicon` 21 approved `different`; CR-005 owner check (41/43, in DECISIONS) | **86 labelled pairs, 15 negatives** (+21 lexicon negatives). Strongly positive-skewed | yes (thin negatives) |
| Current model-price table | `configs/default.yaml` `llm.tiers` | strong (gpt-6-sol) $2.00 in / $10.00 out per 1M tokens; bulk (gpt-6-luna) $0.10 / $0.50; ceiling has no price | yes |
| Current run/snapshot namespace | `data/processed/kg/<run_id>/` | every run writes a new run id; no `sleep/<sleep_id>/` namespace yet (CR-011 §22) | n/a (new) |
| Existing tests relevant to CR-011 | `test_rekey.py`, `test_canonical_rules.py`, `test_alias_rules.py`, `test_expert_kg_canonicalize.py`, `test_expert_kg_pipeline.py`; full suite 616 pass | no cluster-consistency, round-trip, split-leakage or one-token sense tests yet | yes |

## What the audit means for the design

- Merging in production is **online mention attachment** (172 events, 91% G-link, exact-string or rule-based). A sleep phase that merges two **existing** nodes is a new capability; `rekey` is the only precedent and it is rule-only, lexicon-only-guarded and not invertible.
- The current re-key finds just **1** further merge (R0) on `slice3_c2`: the deterministic layers have already done their work online, so most sleep gain must come from candidates R0-R3 do not catch.
- **R0 `different` veto and exact-string auto-merge**: exact same-surface merges across chapters are unguarded by context (119 one-token and 81 cross-chapter merge events exist today). The one-token/same-surface guard (CR §10) is therefore a real change from S0, as the CR expects.

## Dry-run budget (no paid calls; prices from `configs/default.yaml`)

Formula: Cost = sum over calls of (input tokens x $2.00/1M + output tokens x $10.00/1M), strong tier. Measured reference: CR-005 canonicalisation averaged $1.38 / 429 calls = $0.0032 per call (about 450 in, 130 out). The sleep adjudicator prompt carries names, aliases, types, definitions, two evidence excerpts per side and relation context, so I budget 1,300 input / 500 output tokens = about $0.0076 per call.

| Stage | Candidate / call count | Input tokens | Output tokens | Price source | Estimated cost |
|---|---:|---:|---:|---|---:|
| STOP 2 local candidate/scorer | all local (candidate pairs over 1,243 nodes; embeddings cached or local) | 0 | 0 | none | $0 |
| STOP 3 LLM review band (S3, S4, S5, S5-OT, S5-TIME on dev; dev review band target <= 250 calls per CR, assume 250 per LLM arm across 5 arms with cache sharing ~60%) | up to about 500 fresh calls | 650,000 | 250,000 | strong tier | about $3.80 |
| STOP 3 S-AGG (LLM cluster decisions, larger prompts) | up to 100 calls | 300,000 | 100,000 | strong tier | about $1.60 |
| STOP 4 held-out selected arm (target <= 150 calls) + S0 baseline replay (cached, $0) | up to 150 calls | 195,000 | 75,000 | strong tier | about $1.14 |
| STOP 5 migration/rollback | 0 | 0 | 0 | none | $0 |
| **Total (upper planning figure)** | up to about 750 calls | about 1.15M | about 0.43M | | **about $6.5** |

The upper figure is below the **$15 soft warning** and the **$25 hard cap**. The review-band size is not known until STOP 2 (it depends on the scorer's `t_review`); the CR's own targets (<= 250 dev, <= 150 held-out) bound it. The adjudicator output has no reasoning-heavy requirement beyond the schema, but reasoning tokens bill as output, so I used 500 per call (STOP 2 will replace this with a measured dry run on 20 real dev pairs, after approval).

## Reconciliation decision

- [x] **PASS (2026-10-08) after the Research rulings below were recorded** (see CR section 28)
- [ ] BLOCKED - implementation/path issue only.
- [ ] RESEARCH DECISION REQUIRED (resolved below) - two points where repository reality meets a gate or an identity rule the CR fixes.

### Decision 1 - alias-provenance completeness gate (CR §19: required 1.00)

**Problem.** Today 0 of 188 aliases in the production run have a provenance record, and only 43 of 187 alias strings can be traced to a logged merge event (the rest came from the generator's own alias lists or from de-duplicated mentions). The gate "alias-provenance completeness = 1.00" cannot be met by consolidation unless every pre-existing alias also has a record.
**Why the approved design cannot be implemented as written.** Sleep can only guarantee provenance for aliases it creates or moves; for legacy aliases it would have to invent provenance, which the CR forbids (no new facts).
**Alternatives.** (A) Gate scope = aliases created or moved by sleep, plus a `legacy_unrecorded` provenance class for the 144 untraceable pre-existing aliases that is reported but not counted against the gate. (B) Require a pre-sleep backfill that attaches the mention evidence where it exists (43 now, more via the mention list), and count the rest as failures, so the gate cannot pass on this data. (C) Drop the legacy aliases from the gate denominator and report them separately.
**Consequences.** (B) makes the production-adoption gate unreachable on the current run; (A)/(C) change the gate's denominator.
**Decision needed from Research:** which denominator the 1.00 applies to, and whether a `legacy_unrecorded` class is allowed.

### Decision 2 - `Concept` as a type wildcard in identity checks

**Problem.** `types_compatible` treats the generic type `Concept` (250 of 1,243 nodes) as compatible with every type. CR §7 says incompatible types are a VETO and the cluster guard needs "no type-incompatible cross-pair", with the compatibility map loaded from config. With the wildcard, a generic `Concept` node can bridge two nodes of different specific types into one cluster (pairwise compatible, cluster incompatible). The audit found no such bridge today (0 clusters in the re-key probe) but the rule would permit it.
**Alternatives.** (A) Keep the wildcard for pairwise checks and add a cluster-level check that all non-`Concept` members share one type. (B) Treat `Concept` as compatible only with the types listed in a config map that Research approves. (C) Treat `Concept` as incompatible with everything for sleep merges (drops many legitimate merges, since the extraction fallback type is common).
**Decision needed from Research:** the compatibility map (identity semantics), including the status of `Concept`.

### Items that are implementation placement only (no decision needed)

- Misconception items must be re-keyed on merge (they reference node ids) while staying out of the merge itself.
- The `same_concept` queue needs a consumer that routes into the lexicon-guarded sleep candidates.
- Exact-string cross-chapter merges become candidates under the one-token/same-surface guard in S4/S5 only; S0 keeps today's behaviour as the frozen baseline.
- CR-004 organisation is not implemented, so the organisation replay covers CR-006 only.
- The scorer has few negatives (15 owner negatives + 21 lexicon `different` pairs). `t_auto` may end up disabled by the CR's own "if no threshold satisfies the safety criterion" rule; that is an allowed outcome, noted here so it is not a surprise at STOP 2.

**No paid call has been made and none will be made until the owner approves this preflight and Research answers the two decisions.**


## Research rulings (2026-10-08) - recorded; STOP 1 PASS

Full text in `docs/change-requests/CR-011-sleep-consolidation.md` section 28 and `configs/sleep_consolidation_v1.yaml` (`type_compatibility`, `alias_provenance`).

1. **Alias provenance:** three classes (`legacy_reconstructed`, `legacy_unrecorded`, `cr011_native`); completeness = valid structured provenance envelope / all (node, alias) entries in the post-sleep view, required 1.00; legacy origin traceability descriptive only; new CR-011 aliases fully traceable; `legacy_unrecorded` never establishes SAME alone; no snapshot mutation (sidecar registry).
2. **Type compatibility:** `Concept` is generic, not a wildcard; approved cross-type pairs Protocol-Mechanism, Component-Concept, DataUnit-Concept, Parameter-Property, Identifier-Parameter; everything else incompatible; non-transitive; cluster guard checks the whole cluster.
3. Budget about $6.5 approved (soft $15, hard $25). Other findings: build rollback; consume `same_concept` as a candidate source; re-key misconception references; no 0.70 identity threshold; transitive closure and exact-string cross-chapter merges are S0-only behaviour.
