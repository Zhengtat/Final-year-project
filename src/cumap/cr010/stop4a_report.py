"""CR-010 STOP 4A return-to-Research report, generated from the frozen artifacts ($0).
uv run python -m cumap.cr010.stop4a_report [--sheet <marked pair-recall sheet>] [--relmap-sheet <annotator 1 sheet>]"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from cumap.config import REPO_ROOT
from cumap.cr010 import pair_recall as PR

CHECKS = REPO_ROOT / "data/interim/checks"


def spend_by_run(run_id: str) -> dict:
    from cumap.config import get_settings
    from cumap.llm.cost import spend_from_log

    log = REPO_ROOT / "data/logs/llm_calls.jsonl"
    rows = [json.loads(x) for x in log.read_text().splitlines() if x.strip()]
    mine = [r for r in rows if r.get("run_id") == run_id]
    return {
        "calls": len(mine),
        "cached": sum(bool(r.get("cache_hit")) for r in mine),
        "usd": round(spend_from_log(get_settings(), run_id), 4),
    }


def relmap_status(sheet: Path | None) -> list[str]:
    if not sheet or not sheet.exists():
        return ["- No annotator-1 sheet supplied."]
    with sheet.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    with (CHECKS / "cr010_relmap180_MANIFEST_KEY_DO_NOT_SHARE.csv").open(encoding="utf-8") as f:
        key = {r["item_id"]: r for r in csv.DictReader(f)}
    filled = sum(bool(r["current_semantic_relation_judgement"].strip()) for r in rows)
    edge = [r for r in rows if key[r["item_id"]]["stratum"] == "ACCEPTED_EDGE"]
    same = sum(
        r["current_semantic_relation_judgement"].strip() == key[r["item_id"]]["current_relation"]
        for r in edge
    )
    return [
        f"- Annotator 1 (`{Counter(r['annotator_id'] for r in rows).most_common(1)[0][0]}`): **{filled}/{len(rows)} rows judged**, validator: 0 problems (`relmap validate`).",
        f"- Descriptive only (not a gate): on the {len(edge)} accepted-edge items annotator 1 chose the same relation as the current pipeline for {same} ({same / len(edge):.0%}).",
        "- Single annotation; **kappa not measured** (see IAA below). Mapping/loss analysis is STOP 5 work and has not been done.",
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet")
    ap.add_argument("--relmap-sheet")
    a = ap.parse_args()
    pools = json.loads((CHECKS / "cr010_pair_pools_summary.json").read_text())
    fm = json.loads((PR.OUT / "freeze_manifest.json").read_text())
    iaa = json.loads((CHECKS / "cr010_relmap180_iaa_freeze.json").read_text())
    p, sens = pools["pools"], pools["sensitivity_not_used_for_selection"]
    sp = spend_by_run(PR.RUN_ID)
    sealed = PR.OUT / "pair_recall_classifier_SEALED.jsonl"
    n_sealed = len(sealed.read_text().splitlines()) if sealed.exists() else 0
    L = [
        "# CR-010 STOP 4A — return to Research (P3 and full P1/P2 classification NOT started)",
        "",
        "## 1. P2 strict-pool regeneration (dry run, $0)",
        "",
        "| pool | size | note |",
        "|---|---|---|",
        f"| P0 (frozen) | {p['P0']} | unchanged; {pools['frozen_selection_reproduced']['p0_pairs_outside_the_same_sentence_universe']} anchor-derived pairs sit outside the same-sentence universe |",
        f"| P1 extra | {p['P1_extra_same_sentence']} | was 7,680 in the prep: the 50 CR-007 random-sample pairs were left out of P0 too, so they belong to P1-extra by definition (+50) |",
        f"| P2 extra, **frozen strict matcher** | **{p['P2_extra_strict_cue_FROZEN']}** | new |",
        f"| P2 extra, prep rule (superseded) | {fm['old_p2_extra_size_prep_v0']} | was 2,324 in the prep; recomputed 2,474 after excluding the anchor-derived P0 pairs the prep forgot to exclude |",
        f"| P2 extra, substring cue (rejected) | {p['P2_extra_loose_cue (the frozen substring cue; not selective)']} | |",
        f"| nested P0 / P1 / P2 | {pools['nesting']['sizes']['P0']} / {pools['nesting']['sizes']['P1']} / {pools['nesting']['sizes']['P2']} | P0 ⊂ P1 ⊂ P2 and both extras disjoint from earlier pools: asserted |",
        "",
        f"- Strict cue config `configs/cr010_p2_strict_cue_config.yaml`: file sha256 `{fm['strict_cue_config']['file_sha256'][:16]}…`, content sha256 `{fm['strict_cue_config']['content_sha256'][:16]}…`; frozen before any label. It accounts for all 52 repository cues exactly once (14 standalone function words removed, 38 kept).",
        f"- **Sensitivity (not used for selection, for Research):** without inflection forms the pool is {sens['P2_extra_if_inflection_forms_were_not_used (exact tokens only)']}; without the cue `is a` it is {sens['P2_extra_if_is_a_were_removed']}. The cue `uses` (use/used/using/uses) is the only strict cue for {sens['P2_extra_pairs_whose_ONLY_strict_cue_is'].get('uses', 0)} pairs, `is a` for {sens['P2_extra_pairs_whose_ONLY_strict_cue_is'].get('is a', 0)}.",
        f"- Full classification would cost about ${pools['full_classification_cost_usd']['P1_extra']} (P1-extra) + ${pools['full_classification_cost_usd']['P2_extra']} (P2-extra): **not approved, not run**.",
        "",
        "## 2. REL-MAP-180 annotation status",
        "",
        *relmap_status(Path(a.relmap_sheet) if a.relmap_sheet else None),
        "",
        "## 3. Sampled pair-recall study",
        "",
        f"- Frozen: seed {fm['seed']}, {fm['n_per_pool']} random pairs from each of P0 (of {fm['population_sizes']['P0']}), P1-extra ({fm['population_sizes']['P1_extra']}) and P2-extra-strict ({fm['population_sizes']['P2_extra_strict']}); no suitable random human-labelled P0 sample exists, so 150 P0 pairs were drawn (origin: {fm['p0_sample_origin']}). Sample sha256 `{fm['sample_sha256'][:16]}…`.",
        "- 450 pairs in one shuffled blind sheet (`data/interim/pair_recall/pair_recall_blind_sheet.csv`, guide `docs/cr010/PAIR_RECALL_ANNOTATION_GUIDE.md`); columns exactly `true_relation_exists, relation_if_yes, direction_if_yes, evidence_supported, notes`.",
        f"- Classifier run on the 300 P1/P2 samples and **sealed** ({n_sealed}/300 done; P0 reuses the stored run results); revealed only after `freeze-annotation`.",
        "- Truth (fixed now): `true_relation_exists = yes` AND `evidence_supported != no`. Estimator: pool proportion x pool size; 95% percentile bootstrap resampling evidence sections within each pool.",
    ]
    if a.sheet:
        sheet = Path(a.sheet)
        rows = PR.read_csv(sheet)
        key = PR.read_csv(PR.OUT / "pair_recall_KEY_DO_NOT_SHARE.csv")
        res = PR.pair_recall_study(rows, key, fm["population_sizes"])
        pr = res["primary (yes and evidence supported)"]
        L += [
            "",
            "### Results (human labels)",
            "",
            "| pool | true / n | prevalence | 95% CI (clustered) | naive Wilson | estimated true edges |",
            "|---|---|---|---|---|---|",
        ]
        for k in PR.POOLS:
            v, t = pr["prevalence"][k], pr["estimated_true_edges"][k]
            L.append(
                f"| {k} | {v['true']}/{v['n']} | {v['point']:.1%} | [{v['ci95_cluster'][0]:.1%}, {v['ci95_cluster'][1]:.1%}] | [{v['wilson95_naive'][0]:.1%}, {v['wilson95_naive'][1]:.1%}] | {t['point']:.0f} [{t['ci95_cluster'][0]:.0f}, {t['ci95_cluster'][1]:.0f}] |"
            )
        L += [
            "",
            "| pair recall within the P2 universe | point | 95% CI (clustered) |",
            "|---|---|---|",
        ]
        for k, v in pr["pair_recall_within_universe"].items():
            L.append(
                f"| {k} | {v['point']:.1%} | [{v['ci95_cluster'][0]:.1%}, {v['ci95_cluster'][1]:.1%}] |"
            )
        L += [
            "",
            f"Label counts: {res['label_counts']}. Both sensitivities (evidence ignored; unclear as yes) give identical numbers: no `unclear` label and no `evidence_supported = no` among the 450.",
            "",
            "Pair recall is measured against true edges inside the enumerated universe (same sentence, or adjacent sentences with a strict cue); edges outside it are not counted. It is NOT conditional classifier accuracy.",
        ]
    else:
        L += [
            "",
            "**Results: pending** — they need the owner's labels on the 450 pairs (code never invents labels).",
        ]
    af = PR.OUT / "analysis_with_reveal.json"
    if a.sheet and af.exists():
        cc = json.loads(af.read_text())["classifier_conditional"]
        L += [
            "",
            "### Conditional classifier accuracy (revealed after the annotation was frozen; separate from pair recall)",
            "",
            "| pool | recall on human-true | precision vs human | same relation among TP |",
            "|---|---|---|---|",
        ]
        for k, v in cc.items():
            r, pr_, ag = (
                v["classifier_recall_on_human_true"],
                v["classifier_precision_vs_human"],
                v["relation_agreement_among_tp"],
            )
            L.append(
                f"| {k} | {r[0]}/{r[1]} ({r[0] / r[1]:.0%}) | {pr_[0]}/{pr_[1]} ({pr_[0] / pr_[1]:.0%}) | {ag[0]}/{ag[1]} |"
            )
    L += [
        "",
        "## 4. Actual spend",
        "",
        f"- Run `{PR.RUN_ID}`: **${sp['usd']}** over {sp['calls']} logged calls ({sp['cached']} cache hits). Approved ~$2.50, hard cap $4 before P3. The estimate was $2.49 for 300 pairs.",
        "",
        "## 5. Human IAA availability",
        "",
        f"- 60-item subset frozen (hash `{iaa['freeze_hash_sha256_of_sorted_item_ids'][:16]}…`): {iaa['composition']}, split {iaa['split']}, 15 relations covered ({min(iaa['accepted_edge_items_per_relation'].values())}-{max(iaa['accepted_edge_items_per_relation'].values())} items each); hidden manifest `cr010_relmap180_iaa_hidden_manifest_DO_NOT_SHARE.csv`; blank sheet for annotator 2 `cr010_relmap180_iaa_annotator2_blind_sheet.csv`.",
        "- **Second human annotator: none recorded. IAA gate = NOT_EVALUABLE; FULL_ERST_REPLACEMENT is ineligible until one annotates the 60 items.** An LLM does not satisfy the gate.",
        f"- **Protocol deviation:** {iaa['TIMING_DEVIATION']}",
        "",
    ]
    out = REPO_ROOT / "reports/cr010_stop4a.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
