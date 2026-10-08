"""CR-010 STOP 4 preparation report, generated from the frozen REL-MAP-180 manifest and the pair-pool summary ($0).
uv run python -m cumap.cr010.stop4_report"""

from __future__ import annotations

import csv
import json
from collections import Counter

from cumap.config import REPO_ROOT

CHECKS = REPO_ROOT / "data/interim/checks"


def main() -> None:
    man = json.loads((CHECKS / "cr010_relmap180_manifest.json").read_text())
    pools = json.loads((CHECKS / "cr010_pair_pools_summary.json").read_text())
    with (CHECKS / "cr010_relmap180_MANIFEST_KEY_DO_NOT_SHARE.csv").open(encoding="utf-8") as f:
        key = list(csv.DictReader(f))
    comp, leak = man["composition"], man["leakage_check"]
    edge = [r for r in key if r["stratum"] == "ACCEPTED_EDGE"]
    rel = {
        s: Counter(r["current_relation"] for r in edge if r["split"] == s) for s in ("dev", "test")
    }
    names = sorted(
        set(rel["dev"]) | set(rel["test"]), key=lambda n: -(rel["test"][n] + rel["dev"][n])
    )
    p = pools["pools"]
    mi = pools["p0_miss_indication"]
    L = [
        "# CR-010 STOP 4 — preparation (REL-MAP-180 frozen, pair pools enumerated; $0, no model call)",
        "",
        f"## REL-MAP-180 (built from run `{man['built_from_run']}`, registry `{man['registry']}`)",
        "",
        "| split | accepted edges | NO_RELATION | OTHER / near-miss | total | evidence sections |",
        "|---|---|---|---|---|---|",
    ]
    for s, secs in (("dev", man["dev_sections"]), ("test", man["test_sections"])):
        g = lambda t, s=s: comp["by_split_stratum"].get(f"{s}/{t}", 0)
        L.append(
            f"| {s} | {g('ACCEPTED_EDGE')} | {g('NO_RELATION')} | {g('OTHER_NEAR_MISS')} | {comp['by_split'][s]} | {len(secs)} |"
        )
    L += [
        "",
        f"- Split by whole evidence section (seed {man['seed']}, split seed used {man['split_seed_used']}); **leakage check: {'PASS' if leak['ok'] else 'FAIL'}** (shared evidence sections {len(leak['shared_evidence_sections'])}, shared concept pairs {leak['shared_concept_pairs']}, duplicate item ids {leak['duplicate_item_ids']}).",
        "- OTHER / near-miss = `other` outcomes (24) plus registry domain/range rejections (6); `endpoint_not_grounded` rejections are extraction defects and are not used.",
        f"- Frozen: blind sheet sha256 `{man['blind_sheet_sha256'][:16]}`, manifest sha256 `{man['manifest_sha256'][:16]}`. The manifest (model fields, split, concept order) is `{'cr010_relmap180_MANIFEST_KEY_DO_NOT_SHARE.csv'}` and is not shown to an annotator; the NOT-GOLD mapping table was not read.",
        "- Item order and the order of concept A/B are randomised; strata and split are not recoverable from the sheet.",
        f"- Double annotation: {man['double_annotation']}.",
        "",
        "### Accepted edges per relation (the pool is relation-balanced, not proportional)",
        "",
        "| relation | dev | test |",
        "|---|---|---|",
    ]
    L += [f"| {n} | {rel['dev'][n]} | {rel['test'][n]} |" for n in names]
    L += [
        "",
        "## Pair pools (P0-P2 enumerated; P3 needs the eRST graph)",
        "",
        "| pool | pairs | note |",
        "|---|---|---|",
        f"| P0 (frozen CR-009 selection) | {p['P0']} | reproduces the recorded {pools['frozen_selection_reproduced']['unique_window0_pairs_recorded']} same-sentence candidates exactly; {pools['frozen_selection_reproduced']['p0_pairs_outside_the_same_sentence_universe']} P0 pairs are anchor-derived and outside the same-sentence universe |",
        f"| P1 extra (same-sentence pairs the budget left out) | {p['P1_extra_same_sentence']} | classifying all of them would cost about ${pools['full_classification_cost_usd']['P1_extra']} |",
        f"| P2 extra, strict cue (proposed) | {p['P2_extra_strict_cue_FROZEN']} | adjacent-sentence pairs with a relation-bearing cue; about ${pools['full_classification_cost_usd']['P2_extra']} in full |",
        f"| P2 extra, loose cue (the frozen substring cue) | {p['P2_extra_loose_cue (the frozen substring cue; not selective)']} | not selective, shown for reference |",
        f"| adjacent-sentence pairs in all | {p['adjacent_sentence_pairs_not_in_the_same_sentence_universe']} | |",
        "",
        "### Indication of P0's pair recall (unvalidated, from the CR-007 random sample of unselected pairs)",
        "",
        f"- Of {mi['sample_size']} randomly sampled UNSELECTED same-sentence pairs, {mi['sample_accepted_edges']} were accepted as edges by the classifier: yield {mi['unselected_yield']['point']:.0%} (Wilson 95% [{mi['unselected_yield']['wilson95'][0]:.0%}, {mi['unselected_yield']['wilson95'][1]:.0%}]), against {mi['selected_accepted_edges']} accepted edges among the {pools['frozen_selection_reproduced']['p0_pairs']} selected pairs.",
        f"- Projected onto the {mi['unselected_pairs']} unselected pairs: about {mi['projected_unselected_accepted_edges']['point']} further classifier-accepted edges (range {mi['projected_unselected_accepted_edges']['range'][0]}-{mi['projected_unselected_accepted_edges']['range'][1]}), i.e. P0 would reach about **{mi['classifier_accepted_pair_recall_of_p0']['point']:.0%}** (range {mi['classifier_accepted_pair_recall_of_p0']['range'][0]:.0%}-{mi['classifier_accepted_pair_recall_of_p0']['range'][1]:.0%}) of the classifier-accepted same-sentence edges.",
        "- **Caveats:** n = 50; classifier-accepted, not owner-validated (the selected set's owner-measured edge precision was about 90%; the unselected share has not been checked); same-sentence pairs only.",
        "",
        "## Points Research needs to settle (not implementation choices)",
        "",
        "1. **P1 definition.** The same-sentence enumeration is already complete, so I read P1 as 'P0 plus the same-sentence pairs the budget left out'. If P1 meant a different enumeration (clause-level co-mentions, mentions via unrecorded aliases), it needs a definition.",
        "2. **P2 'high-confidence' cue.** The frozen cue test is a substring match, so 'for' fires inside 'information' and 'so' inside 'also': 71.7% of all P&D sentences count as cue sentences (54.0% with word boundaries). I propose word-boundary matching with function words removed (list in `data/interim/checks/cr010_pair_pools_summary.json`); P0 itself is not changed.",
        f"3. **'Sufficiently represented' relation** (gate: recall >= 0.75 per relation). With a relation-balanced test sample, {sum(1 for n in names if rel['test'][n] >= 5)} of {len(names)} relations have at least 5 test items; a threshold is needed.",
        "",
        "## Human steps",
        "",
        "1. **Annotate the 180 rows** in `data/interim/checks/cr010_relmap180_blind_sheet.csv` following `docs/cr010/RELMAP180_ANNOTATION_GUIDE.md`; save your copy to `data/gold/cr010_relmap180_blind_sheet_annotator1.csv` (code never writes there). Check it with `uv run python -m cumap.cr010.relmap validate --sheet <your file>`.",
        "2. **Approve the pair-recall sampling** (below), then validate the accepted edges the extra pools produce.",
        "",
    ]
    out = REPO_ROOT / "reports/cr010_stop4_prep.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
