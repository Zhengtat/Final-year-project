"""CR-048 scoring ($0): the misconception family on the slice3_c2 cue sentences (recall of the legacy items, false positives on the
legacy not-a-warning sentences) and on the P&D development pairs (ordinary relations against `cr046_amend_*`). Applies the rule
pre-registered in docs/DECISIONS.md. Writes reports/cr048/misconception_family.{json,md}."""

from __future__ import annotations

import json
from collections import Counter

from cumap.config import REPO_ROOT
from cumap.cr012 import pd_e2e as PD
from cumap.cr012 import production_graph as PG
from cumap.cr017 import headline as HL
from cumap.cr017 import run as R17
from cumap.cr019 import stage_b as SB
from cumap.cr046 import run as R46
from cumap.cr048 import run as R

OUT = REPO_ROOT / "reports" / "cr048"
LIMIT = 0.01


def sentence_flags(cp: dict) -> dict[str, list[dict]]:
    by: dict[str, list[dict]] = {}
    for r in cp["relation_results_v3"]:
        by.setdefault(r["pair"]["sentence"], []).append(r)
    return by


def cue_scores(cp: dict, src_cp: dict) -> dict:
    by = sentence_flags(cp)
    log = src_cp["misconceptions"]["candidate_log"]
    items = src_cp["misconceptions"]["items"]
    flagged = {s for s, rows in by.items() if any(r["outcome"] == "misconception" for r in rows)}
    groups: dict[str, dict] = {}
    for g in ("items", "needs_correct_edge", "not_warning"):
        sents = [c["sentence"] for c in log if c["outcome"] == g]
        groups[g] = {
            "sentences": len(sents),
            "classifiable": sum(1 for s in sents if s in by),
            "flagged": sum(1 for s in sents if s in flagged),
        }
    item_sents = [c for c in log if c["outcome"] == "items"]
    endpoint_hits = []
    for it in items:
        ends = {it["source_id"], it["target_id"]}
        hit = any(
            r["outcome"] == "misconception"
            and {r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]} == ends
            for c in item_sents
            for r in by.get(c["sentence"], [])
        )
        endpoint_hits.append(
            {
                "item": f"{it['source_name']} {it['relation']} {it['target_name']}",
                "endpoint_pair_flagged": hit,
            }
        )
    outcomes = Counter(
        r["outcome"] if r["outcome"] != "rejected" else f"rejected:{r.get('reason')}"
        for r in cp["relation_results_v3"]
    )
    mis = [r for r in cp["relation_results_v3"] if r["outcome"] == "misconception"]
    return {
        "groups": groups,
        "item_endpoints": endpoint_hits,
        "outcomes": dict(outcomes),
        "misconception_results": len(mis),
        "perturbations": dict(Counter((r.get("misconception") or {}).get("perturbation_type") for r in mis)),
        "flagged_not_warning_examples": [
            {"sentence": c["sentence"], "answers": [(r["pair"]["concept_x_id"], r["pair"]["concept_y_id"], (r.get("misconception") or {}).get("perturbation_type")) for r in by[c["sentence"]] if r["outcome"] == "misconception"]}
            for c in log if c["outcome"] == "not_warning" and c["sentence"] in flagged
        ],
    }  # fmt: skip


def layer_stats(cp: dict) -> dict:
    """The code-checked layer built from the classification results (legacy checks, no model call; correct edges not verified)."""
    from cumap.config import load_demo_slice
    from cumap.expert_kg import misconception as mc
    from cumap.expert_kg.lexicon import Lexicon, production_lexicon_path
    from cumap.expert_kg.slice_rerun import load_sections
    from cumap.schemas.relations import RelationRegistry

    sl = load_demo_slice()
    secs = [
        (s.section_id, s.text)
        for s in load_sections(REPO_ROOT / sl.pd.source_jsonl, list(sl.pd.chapters))
    ]
    layer = mc.layer_from_classification(cp, RelationRegistry.from_yaml(REPO_ROOT / R.REGISTRY), secs, Lexicon.load(production_lexicon_path()), verify=None)  # fmt: skip
    return {
        **layer["stats"],
        "items": [f"{i.get('source_name')} {i.get('relation')} {i.get('target_name')} ({i.get('perturbation_type')})" for i in layer["items"]],
    }  # fmt: skip


def pd_scores() -> dict:
    secs = {r["section_id"]: r["text"] for r in PD.load_sections()}
    sheet, _ = R17.SHEETS["pilot"]
    reg = PD.registry()
    gold, problems = PD.load_gold(R17.ROOT / sheet, secs, reg)
    assert not problems, problems[:2]
    sym = {r.name for r in reg.all_relations() if r.symmetric}
    out = {}
    for arm, rid in (("AMEND", lambda s: R46.arm_id(s, "AMEND")), ("PDMISC", R.pd_id)):
        units, outc = {}, Counter()
        for sid in SB.PD_DEV:
            cp = PG.load_run(rid(sid))
            outc.update(r["outcome"] for r in cp["relation_results_v3"])
            g = PG.graph_for_sections(cp, {sid: secs[sid]})[sid]
            units[sid] = HL.UnitInput(gold[sid], g["nodes"], g["edges"], PG.proposed_pairs(cp, sid), HL.classifier_from_checkpoint(cp, sid))  # fmt: skip
        out[arm] = {
            "headline": HL.evaluate(units, sym, boot=False)["headline"],
            "outcomes": dict(outc),
        }
    return out


def main() -> dict:
    src = json.loads((PG.run_path(R.SRC) / "checkpoint.json").read_text())
    cue_cp = json.loads((PG.run_path(R.CUE_RUN) / "checkpoint.json").read_text())
    cue = cue_scores(cue_cp, src)
    pdr = pd_scores()
    g = cue["groups"]
    recall = g["items"]["flagged"]
    fp_rate = g["not_warning"]["flagged"] / g["not_warning"]["sentences"]
    h = {a: pdr[a]["headline"] for a in pdr}
    d_strict = h["PDMISC"]["strict_e2e_edge_f1"]["f1"] - h["AMEND"]["strict_e2e_edge_f1"]["f1"]
    d_macro = h["PDMISC"]["relation_macro_f1"]["f1"] - h["AMEND"]["relation_macro_f1"]["f1"]
    ok = recall >= 3 and fp_rate <= 0.10 and d_strict >= -LIMIT and d_macro >= -LIMIT
    res = {
        "cue": cue,
        "layer": layer_stats(cue_cp),
        "pd": pdr,
        "decision": {
            "status": "ADOPT_CLASSIFICATION" if ok else "KEEP_LEGACY",
            "legacy_item_sentences_flagged": f"{recall} / {g['items']['sentences']}",
            "not_warning_flag_rate": fp_rate,
            "pd_strict_e2e_f1_delta": d_strict,
            "pd_relation_macro_f1_delta": d_macro,
            "rule": "adopt misconception_source classification if >= 3 of the 4 legacy item sentences are flagged, <= 10% of the 75 legacy not-a-warning sentences are flagged, and P&D dev Strict E2E F1 and Relation Macro F1 each fall by <= 0.01 vs cr046 AMEND",
        },
        "spend": R.spend(),
    }  # fmt: skip
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "misconception_family.json").write_text(
        json.dumps(res, indent=1, default=str), encoding="utf-8"
    )
    (OUT / "misconception_family.md").write_text(markdown(res), encoding="utf-8")
    return res["decision"]


def _f(x) -> str:
    return "—" if x is None else f"{x:.3f}"


def markdown(r: dict) -> str:
    d, g = r["decision"], r["cue"]["groups"]
    L = [
        "# CR-048: misconception family (CR-039 drafts) measured",
        "",
        ("Generated by `cumap.cr048.score` ($0). Cue arm: every concept pair co-mentioned in the 89 cue sentences of the `slice3_c2` legacy misconception "
         "stage (registry v1.6, family v5, choice v7, qualifiers v6, luna). The legacy labels (item / needs correct edge / not a warning) come from the "
         "legacy strong-tier structuring call, not from the owner."),
        "",
        (f"**Decision ({d['rule']}): {d['status']}.** Item sentences flagged {d['legacy_item_sentences_flagged']}; not-a-warning flag rate {d['not_warning_flag_rate']:.3f}; "
        f"P&D strict delta {d['pd_strict_e2e_f1_delta']:+.3f}, macro delta {d['pd_relation_macro_f1_delta']:+.3f}."),
        "",
        "| legacy label | sentences | with a classifiable pair | flagged as a misconception |",
        "|---|---|---|---|",
        *[f"| {k} | {v['sentences']} | {v['classifiable']} | {v['flagged']} |" for k, v in g.items()],
        "",
        "Legacy items, endpoint pair flagged in its sentence:",
        *[f"- {x['item']}: {x['endpoint_pair_flagged']}" for x in r["cue"]["item_endpoints"]],
        "",
        f"Cue-arm outcomes: {r['cue']['outcomes']}; perturbations: {r['cue']['perturbations']}.",
        "",
        f"Code-checked layer from these results (no correct-edge verification): {json.dumps({k: v for k, v in r['layer'].items() if k != 'items'})}",
        *[f"- {i}" for i in r["layer"]["items"]],
        "",
        "## P&D development pairs (1.5 + 2.6): ordinary relations",
        "",
        "| arm | relation macro F1 | strict E2E F1 (P / R) | outcomes |",
        "|---|---|---|---|",
        *[f"| {a} | {_f(v['headline']['relation_macro_f1']['f1'])} | {_f(v['headline']['strict_e2e_edge_f1']['f1'])} ({_f(v['headline']['strict_e2e_edge_f1']['precision'])} / {_f(v['headline']['strict_e2e_edge_f1']['recall'])}) | {v['outcomes']} |" for a, v in r["pd"].items()],
        "",
        "## Not-a-warning sentences flagged",
        "",
        *[f"- {x['sentence']} -> {x['answers']}" for x in r["cue"]["flagged_not_warning_examples"]],
        "",
        f"Spend: ${r['spend']['total_usd']} of ${r['spend']['cap_usd']}.",
        "",
    ]  # fmt: skip
    return "\n".join(L)
