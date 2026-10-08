"""CR-011 STOP 2 report, generated from the saved STOP 2 outputs ($0). uv run python -m cumap.sleep.stop2_report"""

from __future__ import annotations

import json

from cumap.config import REPO_ROOT

OUT = REPO_ROOT / "data/interim/sleep"


def pct(x) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def main() -> None:
    d = json.loads((OUT / "stop2_scorer.json").read_text())
    z = json.loads((OUT / "stop2_sleep240.json").read_text())
    c, r, op = d["candidates"], d["recall"], d["operating_point_dev_labelled_distribution"]
    cal, pool = d["logistic"]["calibration"], d["candidate_pool"]
    L = [
        "# CR-011 STOP 2 - offline candidates, scorer and SLEEP-240 ($0, no API call)",
        "",
        (
            "Baseline snapshot: `slice3_c2` (1,243 nodes). Research rulings of 2026-10-08 applied (type map in config, `Concept` not a wildcard, "
            "alias-provenance classes). No held-out label exists or was opened; no scorer output or label was used to pick SLEEP-240 items."
        ),
        "",
        "## 1. Candidate generation (each source counted separately)",
        "",
        "| source | pairs | exclusive to this source |",
        "|---|---|---|",
    ]
    for s, n in c["by_signal"].items():
        L.append(f"| {s} | {n} | {c['exclusive_by_signal'][s]} |")
    L += [
        "",
        f"- **Union: {c['union']} candidate pairs, {c['per_node']:.1f} candidates per node** (retrieval floor only; no threshold here is an identity threshold).",
        f"- Hard guards before any scoring: {pool['vetoed_before_scoring']}; **{pool['scored']}** pairs remain scoreable.",
        "- The deterministic sources (R0/R1/R2/R3) add almost nothing: the online canonicalisation already applied them. Most sleep candidates come from embeddings and graph overlap, which are retrieval-only signals.",
        "",
        "## 2. Historical owner labels: replay and candidate recall",
        "",
        f"- {r['labelled_pairs']} labelled pairs ({r['by_label_and_resolution']}).",
        (
            f"- Of the {sum(v for k, v in r['by_label_and_resolution'].items() if k.startswith('SAME'))} SAME pairs, **{r['same_pairs_already_co_clustered_by_baseline']} were already merged online** (baseline successes), "
            f"only **{r['same_pairs_that_are_distinct_nodes']}** exist as two distinct nodes in this snapshot (candidate recall {r['covered']}/{r['same_pairs_that_are_distinct_nodes']}), and the rest name nodes that are not in `slice3_c2`."
        ),
        f"- Name-level replay (the alias string as if it were a separate provisional node, partner aliases excluded): {r['name_level_replay']['same_pairs_replayed']} pairs replayable, retrieved by {r['name_level_replay']['retrieved_by']}; union recall {pct(r['name_level_replay']['union_recall'])} (definition/evidence/graph signals are unavailable for a bare string, so this is a lower bound).",
        f"- Lexicon `different`: {r['lexicon_different_pairs_as_distinct_nodes']} pairs exist as distinct nodes, {r['lexicon_different_pairs_in_candidates']} are among the candidates (all are vetoed before scoring).",
        "- **Consequence:** the historical labels cannot measure sleep's candidate recall on the residual graph; the SLEEP-240 development labels must.",
        "",
        "## 3. Scorer (development = historical owner labels, grouped 5-fold CV, out-of-fold metrics only)",
        "",
        f"- Training set: {d['n_train']} pairs ({d['n_pos']} SAME, {d['n_neg']} NOT_SAME incl. lexicon `different`), {d['groups']} normalised-form families. R0 `same` lexicon entries are deterministic-path positives and are excluded.",
        f"- Logistic regression: AUC {d['logistic']['auc']:.3f}, average precision {d['logistic']['average_precision']:.3f}; Platt calibration Brier {cal['brier']:.3f}, ECE {cal['ece']:.3f} (before calibration ECE {d['logistic']['calibration_before_platt']['ece']:.3f}).",
        f"- Gradient-boosted ablation: AUC {d['boosted_ablation']['auc']:.3f}, average precision {d['boosted_ablation']['average_precision']:.3f} (development ablation only; not production).",
        "- Absent feature: " + "; ".join(d["features_absent"]) + ".",
        "",
        "| feature group | AUC without it | delta | AUC with only it |",
        "|---|---|---|---|",
    ]
    ga = d["group_ablation"]
    for g in [k[len("without_") :] for k in ga if k.startswith("without_")]:
        w, o = ga[f"without_{g}"], ga[f"only_{g}"]
        L.append(f"| {g} | {w['auc']:.3f} | {w['delta_auc']:+.3f} | {o['auc']:.3f} |")
    L += [
        "",
        "Interpretation limit: 107 pairs, mostly name-level strings; differences of a few hundredths of AUC are noise.",
        "",
        "## 4. Operating points (proposed only where supportable)",
        "",
        f"- **`t_auto`: {op['auto_status']}.** Best Wilson lower bound over thresholds on the labelled distribution: {op['detail']}. Under the CR rule ML auto-merge is disabled and the scorer is review-ranking only (a valid outcome).",
        f"- `t_review` (recover 90% of SAME in the labelled distribution): {op['t_review']:.3f}.",
        f"- **Predicted review volume: not forecastable from these labels.** Scoring the {pool['scored']} guard-surviving candidates gives calibrated scores with median {pool['score_quantiles']['0.5']:.2f} and 99.9th percentile {pool['score_quantiles']['0.999']:.2f}, all below `t_review`: the band is empty. The historical positives (online-merged name variants) do not look like the residual pool, and the training prior is {pool['training_prior']:.0%} SAME against an unknown, far lower pool base rate. This is a covariate and prior shift, not a finding about sleep.",
        "- Planning figures that do not depend on the scorer: deterministic-source candidates 212, same-type pairs with name similarity >= 0.80 (not deterministic) 111, bridge-risk pairs 96, `same_concept` queue 1. The CR's call targets bound the LLM review band at <= 250 (development) and <= 150 (held-out).",
        "- **Thresholds are therefore frozen only after the 80 SLEEP-240 development labels exist** (development per the CR = historical labels + SLEEP-240 development). No threshold is set now.",
        "",
        "## 5. One-token diagnostics",
        "",
        f"- {d['one_token']['one_token_nodes']} one-token nodes; {d['one_token']['candidates_with_one_token_node']} candidates involve one; {d['one_token']['one_token_pairs_with_only_embedding_signals']} of those carry only embedding/graph signals (embedding-only one-token auto-merge is forbidden, so they can only reach review).",
        f"- Scorer slice (out-of-fold): one-token pairs {d['slices']['one_token_any']}; multi-token {d['slices']['multi_token']}.",
        "",
        "## 6. SLEEP-240",
        "",
        f"- Status: **{z['status']}**. Strata availability before allocation: {z['strata_availability']['available_before_allocation']}; every stratum filled to 40, shortfall {z['strata_availability']['shortfall'] or 'none'}.",
        f"- Split by candidate family (shared node or normalised-form key): {z['split']['families']} families, largest {z['split']['largest_family']}; development {z['summary']['by_split']['dev']} / held-out {z['summary']['by_split']['heldout']}; leakage check: {z['leakage']}.",
        f"- Development by stratum {z['split']['dev_by_stratum']}; held-out {z['split']['heldout_by_stratum']}.",
        f"- Sheets (contract columns only, A/B and item order randomised, no score/source/band/arm): `data/interim/checks/cr011/sleep240_dev_blind_sheet.csv` (80, sha256 `{z['files']['dev']['sha256'][:16]}...`), `sleep240_heldout_blind_sheet.csv` (160, `{z['files']['heldout']['sha256'][:16]}...`); hidden manifest `sleep240_manifest_DO_NOT_SHARE.csv` (`{z['files']['manifest']['sha256'][:16]}...`) with {z['files']['double_annotation_heldout']} held-out items flagged for double annotation if a second annotator exists. Annotation codebook: `docs/annotation/sleep_merge_codebook.md`.",
        "- Held-out labels stay sealed until STOP 4; held-out items may not enter prompts, rules or the lexicon.",
        "",
        "## 7. Findings and items for Research (none requires a return under the STOP 1 rulings)",
        "",
        "- Historical labels are structurally unlike the residual candidate pool (51 of 73 SAME pairs are already merged online, 1 is two distinct nodes). The scorer can be developed on them only as a name-level model; its calibration on the pool is unknown until the 80 development labels exist. No gate or threshold was changed.",
        "- `concept_score` is not stored on checkpoint nodes; it is not a feature. If Research wants it as a feature, CR-009's pruner output would need to be persisted (a separate decision).",
        "- Type map: 15,077 of 28,487 candidates (53%) are type-incompatible under the frozen map, which is the main driver of the small scoreable pool.",
        "",
        "## 8. Cost",
        "",
        "$0 (local embeddings, scikit-learn, no API call).",
        "",
        "## Next",
        "",
        "Owner: annotate `sleep240_dev_blind_sheet.csv` (80 items) per the codebook and save the marked copy under the gold folder. STOP 3 development ablations need those labels. The 160 held-out items can be annotated later, but must not be opened by any pipeline code before STOP 4.",
        "",
    ]
    out = REPO_ROOT / "reports/cr011_sleep/stop2.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
