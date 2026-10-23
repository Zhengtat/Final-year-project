# CR-006 — Knowledge sphere: per-chapter core–periphery organisation

**Status:** approved by owner (Zheng Tat Wong), 2026-09-29
**Purpose:** after each chapter, the graph **reorganises itself**. The most important concepts move towards the centre, and weakly connected ones sit at the edge. Adds a "sphere view" (concentric rings) to the demo report, with the chapter slider.
**Scope:** structure only. **No API calls** in the core of this CR.

**Depends on:**
- CR-005 chapter snapshots (`data/processed/kg/<run_id>/snapshots/ch<N>/`) and the report builder;
- CR-001 registry v1 (families, `diagnostic_prior`).

**Shares code with CR-004:**
- the Leiden community function (§4) and the centrality function used for tiers (§7). Build them here once if they don't exist yet; CR-004 reuses them.

**Numbering note:** the end-to-end skeleton that was once proposed as "CR-006" was never added to the repo. It stays deferred and unnumbered.

**Rationale and sources:** Rumelhart & Norman (1978) name three modes of learning: **accretion** (add facts), **tuning** (refine them) and **restructuring** (reorganise). M5 already does the first two (append + merge, updating descriptions). This CR adds the third, for the organisation only. Method sources are in the running paper list, "Core–periphery ('sphere') organisation":
- Borgatti & Everett 2000 (core–periphery model);
- Seidman 1983 (k-cores);
- Brandes, Kenis & Wagner 2003 (radial centrality layout);
- Misue et al. 1995 (keeping the mental map);
- Palla et al. 2007 and Greene et al. 2010 (tracking communities over time);
- Guimerà & Amaral 2005 (participation coefficient);
- Barabási & Albert 1999 (older nodes collect more links);
- Kojaku & Masuda 2018 (a single core is mostly explained by degree, which shapes the choice of null model);
- Kinchin et al. 2000 (a single hub = a spoke map, typical of novices).

---

## 1. Rules

1. **Reorganise, don't rewrite.**
   - `cumap kg organise` only **reads** content snapshots (nodes, edges, merges).
   - It writes only under `organisation/`.
   - It never changes a concept, an edge or evidence, and never re-runs extraction.
2. **Rings are not tiers.**
   - Rings are a per-chapter, structure-only view.
   - CR-004 tiers (principle / core / detail) stay the authoritative organisation.
   - To avoid a name clash, rings are called **centre / inner / middle / outer** (plus `unlinked` and `background`), never "core".
3. **Outer ≠ remove.** No concept is deleted or demoted because of its ring. A persistently peripheral concept is flagged for review. It may be a detail, or it may be missing edges (an extraction recall gap).
4. **A small centre, not a single node.**
   - The "single point" is a **virtual centre label** (the book title), not a KG node.
   - Concepts earn their distance from it.
   - Forcing one hub would impose a spoke structure (Kinchin et al. 2000).
5. **Principles are never pinned to the centre.**
   - Before CR-004 STOP C there are no principles, only concepts.
   - After STOP C, principles earn their position like any node (§11). A principle that stays outside the centre is a finding, not a bug.
6. **Honest labelling.** Every chart gets a label-source tag. Add two new allowed tags:
   - `Structural metric (no human labels)`;
   - `Owner importance check (n=40)`.

   Report whether a core actually exists (§7) before showing the sphere as if it does.

---

## 2. Order of work and stop points

Commit per step with the prefix `CR-006:`.

1. **⛔ STOP 1:** in ≤ 10 lines:
   - what already exists (snapshot format, graph library in the report, any community/centrality code);
   - what you'll build;
   - libraries to add (`python-igraph`, `leidenalg`);
   - confirm $0 API cost.
2. Build §3–§10 as tested tooling on fixtures. This can happen while CR-005 is still running, once its snapshot writer exists.
3. Run on the CR-005 P&D ch. 1–3 snapshots.
   **⛔ STOP 2:** for each chapter, show:
   - the top-15 concepts by **raw and adjusted** importance, side by side;
   - the background-vocabulary list;
   - the `unlinked` count;
   - core–periphery fit vs null;
   - stability;
   - the 10 biggest movers, with the edges that moved them.

   I choose the radius basis (raw or adjusted) and confirm generic overrides. Record both in DECISIONS.
4. Add the sphere view and charts to the CR-005 report (§10) and export static figures.
   **⛔ STOP 3:** screenshots of the sphere at the start and at ch. 1, 2 and 3, plus the figures list. Do this before CR-005 STOP 4, so the report ships with the sphere.
5. *(Optional before the meeting)* Build the face-validity sheet (§12).
   **⛔ STOP 4:** the sheet is ready. After I fill it in, report ρ and AUC with CIs.
6. *Later:*
   - **Full book (expert-KG phase 2):** run on every chapter's snapshots;
   - **Principle mode (phase 4):** replay (§11) after CR-004 STOP C and §5.10.

---

## 3. The graph per snapshot

For snapshot ch*N*, build `G_N` from all nodes and edges introduced in chapters ≤ *N*.

- **Layers:** semantic + taxonomy. The prerequisite layer is **excluded** by default: its defined→used candidates are heuristic. It can be included in an ablation.
- **Nodes:**
  - in the slice: concepts that passed the M5 structural checks;
  - once CR-002 exists: anchored concepts only. The others go to the `unlinked` band.
- **Edge weight:** the registry `diagnostic_prior` of the relation's family × `edge.confidence`. Use 1.0 when confidence is absent (the slice has no CR-002 edge confidence). This is the same weighting as CR-004 §4.
- **Typed edges only.** Co-occurrence never counts as an edge.

## 4. Importance score (per node, per snapshot)

Four components, each turned into a **percentile rank within the snapshot**, then combined as a weighted mean. The weights are in config and **fixed before §12**; they are never tuned on the owner's ratings.

| Component | Default weight | Definition | Why |
|---|---|---|---|
| `pagerank` | 0.35 | Weighted PageRank (damping 0.85) on a **directed** projection (below) | What other concepts depend on, belong to or serve |
| `coreness` | 0.20 | k-shell index (Seidman 1983) on the undirected, unweighted projection | Sits inside a densely linked region |
| `spread` | 0.25 | Share of sections in `G_N` where the concept is `defined` or `used` (`mentioned` is ignored) | Recurs across the book |
| `bridging` | 0.20 | Participation coefficient over **fine** communities (Guimerà & Amaral 2005) | Links separate topics (integrative) |

**PageRank direction rule.** Importance flows towards what others depend on, belong to or serve:
- towards the **target** for `is_a`, `part_of`, `requires`, `uses`, `has_purpose`, `instantiates`;
- towards the **source** for `has_property`;
- **both ways** for everything else (e.g. `causes`, `precedes`, `contrasts_with`).

Keep the rule in config, document it in ARCHITECTURE, and ablate it against a fully undirected version.

**Two scores:**
- `importance_raw`: the weighted mean of percentiles.
- `importance_adj`: corrects for **exposure**. Early concepts have had more sections to collect links.
  - Within each snapshot, regress `importance_raw` on `log(1 + sections since first seen)`.
  - `importance_adj` is the percentile rank of the residual.
  - This removes only the *average* age effect: an old concept that is more central than its age predicts stays high.

**Background-vocabulary guard** (generic hub terms such as "data" or "network"):
- **Flag a concept** when all three hold:
  - it appears in ≥ 50% of sections in `G_N`;
  - it is **never** `defined`;
  - its typed edges per appearance fall in the bottom quartile.
- **Handling:**
  - flagged concepts go to the `background` band;
  - they are excluded from the centre and from the core–periphery fit;
  - they are shown in a dotted outer ring, hidden by default.
- **Owner overrides** live in config (`generic_guard.overrides_keep`, `overrides_generic`). Never in `data/gold/`.

## 5. Rings

- Rings are computed over linked, non-background nodes.
- **Default method: quantile bands of the chosen importance basis**, from the centre out:
  - centre 5%;
  - inner 15%;
  - middle 30%;
  - outer 50%.
- **Alternative** (config): k-shells.
- **Extra bands:**
  - `unlinked`: no typed edges. A large count points to relation-extraction recall gaps.
  - `background`: flagged by the §4 guard.
- **Radius** is continuous: `r = r_min + (1 − importance)·(r_max − r_min)`. Ring boundaries are drawn faintly at the band thresholds.

## 6. Communities over time

- **Leiden** (fixed seed) on each `G_N`, at the coarse and fine resolutions from CR-004 §4's config. Use placeholders if that config doesn't exist yet.
- **Matching across consecutive snapshots:** by Jaccard overlap of members, matched if ≥ 0.3 (Greene et al. 2010). This gives **persistent community IDs**.
- **Events** (Palla et al. 2007):
  - `continue`, `grow`, `shrink`, `merge`, `split`, `birth`, `death`;
  - a continuing community counts as **changed** when Jaccard < 0.7.
- **Labels:** the top 3 concepts by importance. No LLM calls.
  - CR-004 §4 summaries come later. Regenerate summaries only for communities that were born or changed.

## 7. Is there really a core? (run before trusting the picture)

- **Fit per snapshot:**
  - use the discrete Borgatti–Everett fit;
  - it is the Pearson correlation between the observed unweighted adjacency and the ideal pattern (core–core = 1, periphery–periphery = 0, core–periphery pairs ignored);
  - core = centre ∪ inner.
- **Two null models** (200 samples each). On every sample, recompute the core by the same importance procedure, holding `spread` fixed since it isn't structural.
  1. **Primary: same-density random graphs** (G(n, m), same node and edge counts). Question: *is there a core at all?*
  2. **Secondary: degree-preserving rewires.** Question: *is the core more than a few hubs?* Expect this to be small. Kojaku & Masuda (2018) show a single core is largely explained by the degree sequence. Report it, but don't gate on it.
- **Report** for each null: ρ_obs, null mean ± SD, z and the **effect size Δρ = ρ_obs − null mean**.
- **Labels, gated on the primary null.** Null SDs are tiny, so z alone overstates weak structure; hence the Δρ threshold.
  - z ≥ 2 **and** Δρ ≥ 0.10 → "core–periphery structure present";
  - z ≥ 2 but Δρ < 0.10 → "weak core" (a banner saying so);
  - otherwise → the banner **"No clear core at this chapter: ring positions are weakly supported."**
- **Prototype check** (toy graphs, 300 nodes, primary null):
  - a planted core gave Δρ ≈ 0.48;
  - a random graph gave Δρ ≈ 0;
  - a hub-dominated (Barabási–Albert) graph gave Δρ ≈ 0.09 with z ≈ 14, which the thresholds label a weak core.

  Under the degree-preserving null, even the planted core gave Δρ ≈ 0.002, hence "report, don't gate".

## 8. Restructuring events ("why did it move?")

Write `events.jsonl` per chapter. Each event carries **the new edge IDs and section IDs** that caused it.

- **Node events:**
  - `node_new`;
  - `ring_in` / `ring_out` (moved ≥ 1 ring);
  - `enter_centre` / `leave_centre`.
- **Trajectory events:**
  - `late_centraliser`: introduced in ch *k*, reaches centre or inner only at ch ≥ *k* + gap (gap = 1 for the 3-chapter slice, 2 for the full book);
  - `fading`: was centre or inner, now outer.
- **Community events** from §6.
- **Flag `persistent_periphery`:** outer or unlinked for ≥ 2 consecutive snapshots with ≤ 1 typed edge. It is a review flag and feeds CR-004 §7 tiers as a feature. It never deletes anything.
- **Stability per chapter:**
  - Jaccard of (centre ∪ inner) vs the previous chapter;
  - Kendall τ of importance over shared nodes;
  - mean layout displacement of existing nodes (§9).

## 9. Layout (the sphere view)

- **Shape:** 2D concentric rings, i.e. a disc. It reads better on slides than 3D. 3D is a non-goal.
- **Radius:** from §5.
- **Angle** = the coarse community's **sector**:
  - a sector's centre angle is fixed once the community is born;
  - new communities are inserted between the neighbours they share the most edge weight with;
  - sector widths scale with size.
- **Stability** (Misue et al. 1995):
  - an existing node keeps its previous angle while it stays in the same community;
  - a new node starts at its strongest neighbour's angle;
  - after that, a light angular relaxation, capped at 20° per chapter;
  - report the mean displacement.
- **Slider:**
  - position **0 = start**: only the centre label (the book) is shown, which is the "single point";
  - positions 1…N add each chapter;
  - positions are **precomputed per chapter** and animated between.
- **Library:** use whatever graph library CR-005 chose, with preset positions (physics off). The report stays a single offline file.

## 10. Report additions (CR-005 Tab 3)

- **A "Sphere view" toggle** next to the existing growth graph, sharing the chapter slider.
  - **Nodes:** colour = chapter of first introduction (as in CR-005); size = importance; halo for new nodes this chapter; arrow marker for `ring_in` / `ring_out`.
  - **Principles** (principle mode only) are drawn as diamonds.
  - **Hover:** the four components, raw/adjusted importance, ring, first chapter, sections.
  - **Click:** "why it moved" (from `events.jsonl`).
  - **Toggles:** raw ↔ adjusted radius; show background / unlinked; show cross-chapter edges only.
  - **Default filter:** centre–middle rings, to avoid a hairball.
- **Charts** (each with the provenance footer + `Structural metric (no human labels)`, unless §12 exists):
  1. top-15 per chapter with Δrank;
  2. ring composition per chapter, stacked by chapter of introduction (do new chapters' concepts reach the centre?);
  3. stability: core Jaccard + Kendall τ per chapter;
  4. core–periphery fit per chapter, with both null bands (mean ± 2 SD) and the §7 label;
  5. community events timeline;
  6. importance trajectories for the ~15 key concepts from CR-005's concept timeline, with `late_centraliser` and `fading` highlighted.
- **Static figures** (matplotlib, PNG + SVG) in `reports/demo/figures/`:
  - `sphere_ch{0,1,2,3}`;
  - one per chart above.

## 11. Principle mode (later, after CR-004 STOP C and §5.10)

- `cumap kg organise --mode principles` **replays** every chapter snapshot with the approved principles and final `instantiates` edges.
  - **Time-aware activation:** an `instantiates` edge is active from max(the concept's first chapter, the chapter of its evidence section).
  - A principle appears once it has ≥ 1 active edge.
- **Outputs:**
  - the **principle trajectory**: the chapter where each principle first enters the centre/inner rings, and the chapters that link back to it. This feeds CR-004 §11 ("first appearance of each principle and how many chapters link back");
  - a **tier–ring disagreement list**:
    - CR-004 core-tier concepts in the outer ring, which usually means missing edges;
    - detail-tier concepts in the centre, which may be a tiering error;
    - this list is for review, not auto-correction.
- The provisional-mode run is kept for comparison under its own `org_id`.

## 12. Validation (optional before the meeting)

- **Face-validity sheet (blind, 40 concepts)** from the final slice snapshot:
  - 20 from centre + inner and 20 from outer, stratified by chapter of introduction, shuffled;
  - each row shows the concept name and its defining evidence quote only: **no** ring, score, chapter or provenance;
  - the owner rates "How central is this concept to understanding chapters 1–3?" on a scale of 1 (peripheral detail), 2 (supporting), 3 (central).
- **Files:**
  - the sheet is written to `data/interim/checks/organisation_face_validity.csv`;
  - the owner saves the filled copy to `data/gold/organisation/`.
- **Metrics:**
  - Spearman ρ between rating and importance (raw and adjusted), with a bootstrap 95% CI (2,000 resamples);
  - AUC of importance for rating 3 vs 1–2, with a bootstrap CI.
- **Tag:** `Owner importance check (n=40)`.
- **Limitation (write it in the report):** the owner has seen the graph, so the rating isn't fully independent. A supervisor rating adds weighted κ.
- **Later (full book):** a descriptive overlap between the final centre and the CS2023 NC core topics / CSO top networking topics. These are weak labels, so it is never reported as accuracy.

## 13. Schemas and outputs

```python
class ImportanceComponents(BaseModel):
    pagerank: float; coreness: int; spread: float; bridging: float
    percentiles: dict[str, float]            # per component, within snapshot

class OrgNodeState(BaseModel):
    org_id: str; chapter: int; concept_id: str
    node_type: Literal["Concept", "Principle"]
    first_chapter: int; exposure_sections: int; n_typed_edges: int
    components: ImportanceComponents
    importance_raw: float; importance_adj: float
    ring: Literal["centre","inner","middle","outer","unlinked","background"]
    radius: float; angle_deg: float
    community_id_coarse: str | None; community_id_fine: str | None   # persistent IDs
    background_flag: bool; persistent_periphery: bool

class RestructureEvent(BaseModel):
    org_id: str; chapter: int
    type: Literal["node_new","ring_in","ring_out","enter_centre","leave_centre",
                  "late_centraliser","fading","community_continue","community_grow",
                  "community_shrink","community_merge","community_split",
                  "community_birth","community_death"]
    subject_ids: list[str]                   # concept or community IDs
    from_state: str | None; to_state: str | None
    delta_importance: float | None
    because_edge_ids: list[str]; because_section_ids: list[str]
```

- **Per-chapter files:** `data/processed/kg/<run_id>/organisation/<org_id>/ch<N>/{org_nodes,communities,events}.jsonl`.
- **Manifest:** `organisation/<org_id>/manifest.json`, containing:
  - `kg_run_id`, mode, config hash, code version, seeds;
  - per chapter: node and edge counts, modularity, core–periphery fit {ρ, and for each null: mean, SD, z, Δρ, label}, stability {Jaccard, τ}, mean displacement, label-source tag.
- `org_id = "org_" + sha1(kg_run_id + mode + config_hash + code_version)[:8]`.
- Content snapshots are never modified.

## 14. CLI and config

- `cumap kg organise --run <run_id> [--mode provisional|principles] [--through-chapter N] [--config configs/organisation.yaml]`. Makes no API calls, so no dry run is needed.
- `cumap demo build --run <run_id> --org <org_id>` adds the sphere view.
- `configs/organisation.yaml` is included in this pack with the defaults above.

## 15. Tests (no network, no key)

- **Importance:** a known ordering on a fixture graph, covering:
  - the direction rule (a parent gains from `is_a`; a concept gains from `has_property`);
  - the percentile combination.
- **Exposure correction:** on a fixture, a young, fast-linking node ranks above an old node with the same degree in `importance_adj`, but not in `importance_raw`.
- **Background guard:** flags a fixture hub term. `overrides_keep` un-flags it.
- **Rings:** band shares match the config; `unlinked` and `background` are excluded from the quantiles.
- **Core–periphery fit** (fixed seeds, primary null):
  - "present" on a planted core–periphery graph;
  - "no clear core" on an Erdős–Rényi graph of the same density;
  - "weak core" on a Barabási–Albert graph.
- **Community tracking** on 3-snapshot fixtures: continue, merge, split, birth, death.
- **Layout:**
  - a node present in consecutive snapshots in the same community moves ≤ the angle cap;
  - sector centres are fixed;
  - output is deterministic with a fixed seed.
- **Events:** `ring_in` carries the edge IDs that caused it; `late_centraliser` fires on a fixture.
- **Principle mode:** time-aware activation of `instantiates` on a fixture.
- **Read-only content:** snapshot `nodes`/`edges`/`merges` files have identical hashes before and after `kg organise`.
- **Report:**
  - chart functions reject a missing label-source tag, and accept the two new tags;
  - the HTML still has no external `http(s)://` references.
- **Face-validity sheet:** contains no ring, score, chapter or provenance columns.
- Nothing writes to `data/gold/`.

## 16. Docs

- **`ARCHITECTURE.md`:**
  - an "Organisation snapshots" section: models, importance formula, direction rule, rings ≠ tiers;
  - the null-model check.
- **`BUILD_PLAN.md`:**
  - add **M5.0b — Knowledge sphere (CR-006)** after M5.0: provisional mode on the slice;
  - note that M5 (full book) reruns it per chapter;
  - note that M5.5 (CR-004) runs principle mode after STOP C.
- **`CLAUDE.md`**, new rules:
  - "`kg organise` never modifies content snapshots; it writes only under `organisation/`."
  - "Rings are a structural view, not tiers. Never delete or demote a concept because of its ring."
  - "Principles are never pinned to the centre."
- **`DECISIONS.md`:**
  - the reorganise-not-rewrite rule;
  - component weights and the direction rule;
  - the radius basis chosen at STOP 2;
  - background-guard thresholds and overrides;
  - ring shares;
  - libraries.
- **`PROGRESS.md`:** a CR-006 row with, per chapter, the core–periphery z, stability, top-5 centre concepts and the `org_id`.

## 17. Cost and time
- **API:** **$0** (graph algorithms only). Optional LLM community labels later: < $1 on the bulk tier, with `--dry-run`.
- **Compute:** seconds to a few minutes. The null models dominate: 2 × 200 samples × 3 chapters.
- **Owner time:**
  - STOP 2 review: ~15 min;
  - face-validity sheet: ~10 min (optional).

## 18. If time is short before the meeting
Drop things in this order:
1. the face-validity sheet (keep the `Structural metric (no human labels)` tag);
2. community sectors (use angle by chapter of introduction instead);
3. the community events chart.

**Never drop** the provenance tags, the core–periphery null check or the "no clear core" banner.
