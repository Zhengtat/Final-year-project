"""CR-009 STOP 3 report (§9): the CR-008 run vs the CR-009 run on P&D ch. 1-3, from the saved checkpoints, the v4 run
JSON, the organisation outputs and the call log. $0. `uv run python -m cumap.concepts_v4.stop3_report --before slice3_b4
--after slice3_c1 --org-before org_41ffa694 --org-after <org>`."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from cumap.config import REPO_ROOT, get_settings

KG = REPO_ROOT / "data" / "processed" / "kg"


def _load(run: str) -> dict:
    return json.loads((KG / run / "checkpoint.json").read_text())


def _edges(cp: dict) -> list[dict]:
    from cumap.expert_kg.misconception import expert_edges

    return list(expert_edges(cp["relation_results_v3"]).values())


def _order() -> dict[str, int]:
    rows = [
        json.loads(x)
        for x in (REPO_ROOT / "data/interim/textbook_sections.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if x
    ]
    return {r["section_id"]: r["order_index"] for r in rows}


def _chapter(sid: str) -> int:
    m = re.match(r"(\d+)", sid)
    return int(m.group(1)) if m else 0


def linked(cp: dict) -> tuple[float, float]:
    ends = {e["pair"][k] for e in _edges(cp) for k in ("concept_x_id", "concept_y_id")}
    cs = cp["concepts"]
    defined = [c for c in cs if any(m["role"] == "defined" for m in c["mentions"])]
    return sum(c["concept_id"] in ends for c in cs) / max(len(cs), 1), sum(
        c["concept_id"] in ends for c in defined
    ) / max(len(defined), 1)


def late_edges(cp: dict, order: dict[str, int]) -> tuple[int, int]:
    first = {c["concept_id"]: order.get(c["first_introduced"], 10**9) for c in cp["concepts"]}
    es = _edges(cp)
    late = sum(
        1
        for e in es
        if order.get(e["pair"]["section_id"], 10**9)
        < max(first.get(e["pair"]["concept_x_id"], 0), first.get(e["pair"]["concept_y_id"], 0))
    )
    return late, len(es)


def spend_by_task(run: str) -> dict[str, float]:
    tiers = get_settings().llm.tiers
    out: dict[str, float] = defaultdict(float)
    for line in (REPO_ROOT / "data" / "logs" / "llm_calls.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r.get("run_id") == run and not r["cache_hit"]:
            t, u = tiers[r["model_tier"]], r["usage"]
            out[r["task"]] += (
                u["input_tokens"] / 1e6 * t.usd_per_1m_input_tokens
                + u["output_tokens"] / 1e6 * t.usd_per_1m_output_tokens
            )
    return dict(out)


def org_ch3(run: str, org: str) -> tuple[dict, list[dict]]:
    base = KG / run / "organisation" / org
    man = json.loads((base / "manifest.json").read_text())["chapters"]["3"]
    nodes = [
        json.loads(x) for x in (base / "ch3" / "org_nodes.jsonl").read_text().splitlines() if x
    ]
    return man, nodes


def build(
    before: str, after: str, org_before: str | None, org_after: str | None, out_md: Path
) -> str:
    a, b = _load(before), _load(after)
    v4 = json.loads((KG / after / "v4_concepts.json").read_text())
    order = _order()
    gvp = yaml.safe_load((REPO_ROOT / "configs" / "concept_gvp.yaml").read_text())
    fam_map = gvp["anchor_family_map"]
    nodes = v4["nodes"].values()
    secs = v4["sections"]
    L = [
        f"# CR-009 STOP 3 — P&D ch. 1–3: CR-008 run `{before}` vs CR-009 run `{after}`",
        "",
        "All numbers are computed from the saved runs; owner precision figures are pending the owner sheets.",
        "",
    ]
    # ---- nodes, mentions, rejections
    link = Counter(
        m["linked_by"] for n in nodes for m in n["mentions"] if m["section_id"] is not None
    )
    nm = Counter(x["reason"] for s in secs.values() for x in s["final"]["not_mentions"])
    unconf = sum(len(s["unconfirmed_mentions"]) for s in secs.values())
    n_exist = sum(len(s["final"]["existing_mentions"]) for s in secs.values())
    glinks = [m for m in v4["merges"] if m["rule_id"] == "G-link"]
    L += [
        "## Concepts and mentions",
        "",
        "| Metric | CR-008 run | CR-009 run |",
        "|---|---|---|",
        f"| Concepts (nodes) | {len(a['concepts'])} | {len(b['concepts'])} (v4 nodes {len(v4['nodes'])}) |",
        f"| Existing mentions by `linked_by` | – | generator {n_exist}, backfill {link.get('backfill', 0)} |",
        f"| Not-mentions by reason | – | {dict(nm)} |",
        f"| `unconfirmed_mention` | – | {unconf} |",
        f"| Generator links: trivial / non-trivial (G-link) | – | {max(n_exist - len(glinks), 0)} / {len(glinks)} |",
        f"| Canonicalisation LLM calls (R4) vs the CR-007 run | ≥ 236 (CR-007) | {sum(1 for m in b['merges'] if m.get('llm_called')) + len(b['taxonomy_candidates']) + len(b['merge_review'])} recorded decisions |",
        "",
    ]
    # ---- anchors
    by_origin = Counter(n["extraction_origin"] for n in nodes)
    by_ch: dict[int, Counter] = defaultdict(Counter)
    for n in nodes:
        by_ch[_chapter(n["first_section"])][n["extraction_origin"]] += 1
    atypes = Counter(x["anchor_type"] for x in b["anchors"])
    L += [
        "## Anchors",
        "",
        f"- Anchored {by_origin.get('anchored', 0)} vs independent {by_origin.get('independent', 0)} ({by_origin.get('anchored', 0) / max(len(v4['nodes']), 1):.0%} anchored); by chapter: "
        + "; ".join(
            f"ch{c}: {v['anchored']} / {v['independent']}" for c, v in sorted(by_ch.items())
        ),
        f"- Anchor types: {dict(atypes)}; `found_via_anchor`: {sum(1 for n in nodes if n['found_via_anchor'])}; anchor records after canonicalisation: {len(b['anchors'])}",
        "",
    ]
    # ---- verifier / backfill / pruner
    its = Counter(len(s["iterations"]) - 1 for s in secs.values())
    stops = Counter(s["stop_reason"] for s in secs.values())
    flags = Counter()
    for s in secs.values():
        flags.update(s["flags_by_rule"])
    bf = v4["backfill"]
    pruned_def = sum(1 for p in v4["pruned"] if p.get("pruned_defined"))
    attrs = sum(len(n["attributes"]) for n in nodes)
    L += [
        "## Verifier, backfill, pruner",
        "",
        f"- Units: {len(secs)}; iterations histogram {dict(sorted(its.items()))}; stop reasons {dict(stops)}; flags per rule {dict(flags)}; hints added / rejected {sum(s['hints_added'] for s in secs.values())} / {sum(s['hints_rejected'] for s in secs.values())}; restored {sum(s['restored'] for s in secs.values())}",
        f"- Backfill: {len([x for x in bf if 'error' not in x])} calls, {sum(len(x.get('accepted', [])) for x in bf)} mentions added, {sum(1 for x in bf if 'error' in x)} failed calls",
        f"- Pruner (P1, IIR-dev rows, out of domain on P&D; tau 0.1): {len(v4['pruned'])} pruned (prune rate {len(v4['pruned']) / max(len(v4['pruned']) + len(v4['nodes']), 1):.1%}), `pruned_defined` {pruned_def}, attributes {attrs}",
        "",
    ]
    # ---- linkage
    la, lb = linked(a), linked(b)
    ea, eb = late_edges(a, order), late_edges(b, order)
    L += [
        "## Linkage",
        "",
        "| Metric | CR-008 run | CR-009 run |",
        "|---|---|---|",
        f"| Linked share, all concepts / `defined` concepts | {la[0]:.1%} / {la[1]:.1%} | {lb[0]:.1%} / {lb[1]:.1%} |",
        f"| Late-counted edges (an endpoint first occurs after the edge's section) | {ea[0]} of {ea[1]} | {eb[0]} of {eb[1]} |",
        f"| Accepted edges | {len(_edges(a))} | {len(_edges(b))} |",
        "",
    ]
    # ---- anchor -> edge conversion
    res_by_pair: dict[frozenset, dict] = {}
    for r in b["relation_results_v3"]:
        if r.get("group", "selected") == "selected":
            res_by_pair[frozenset((r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]))] = r
    seen, conv = set(), Counter()
    agree = tot = 0
    for an in b["anchors"]:
        k = frozenset((an["concept_id"], an["anchor_id"]))
        if k in seen or k not in res_by_pair:
            continue
        seen.add(k)
        r = res_by_pair[k]
        conv[r["outcome"]] += 1
        if r["outcome"] == "edge" and fam_map.get(an["anchor_type"]):
            tot += 1
            agree += r["family"] == fam_map[an["anchor_type"]]
    n_anchor_pairs = sum(conv.values())
    L += [
        "## Anchor pairs through the relation stage",
        "",
        (f"- Anchor pairs classified: {n_anchor_pairs}; outcomes {dict(conv)}; **anchor → accepted-edge conversion {conv.get('edge', 0) / max(n_anchor_pairs, 1):.1%}**; "
        f"NO_RELATION rate {(conv.get('no_relation', 0)) / max(n_anchor_pairs, 1):.1%}; anchor-type family agreement with the accepted relation's family {agree}/{tot} ({agree / max(tot, 1):.0%})."),
        "",
    ]
    # ---- sphere
    if org_before and org_after:
        ma, na = org_ch3(before, org_before)
        mb, nb = org_ch3(after, org_after)
        ca = {n["name"] for n in na if n["ring"] in ("centre", "inner")}
        cb = {n["name"] for n in nb if n["ring"] in ("centre", "inner")}
        L += [
            "## Sphere (ch3)",
            "",
            (f"- Core–periphery: {ma['core_periphery']['label']} (Δρ {ma['core_periphery']['primary']['delta_rho']:.3f}) → {mb['core_periphery']['label']} (Δρ {mb['core_periphery']['primary']['delta_rho']:.3f}); "
            f"core (centre+inner) name-matched Jaccard {len(ca & cb) / max(len(ca | cb), 1):.2f} ({len(ca)} → {len(cb)} nodes); "
            f"top-15 entered: {sorted({n['name'] for n in sorted(nb, key=lambda n: -n['importance_adj'])[:15]} - {n['name'] for n in sorted(na, key=lambda n: -n['importance_adj'])[:15]})}"),
            "",
        ]
    # ---- misconception layer and cost
    ms_a, ms_b = (
        a.get("misconceptions", {}).get("stats", {}),
        b.get("misconceptions", {}).get("stats", {}),
    )
    L += [
        "## Misconception layer",
        "",
        f"- CR-008 run: {ms_a}; CR-009 run: {ms_b or 'not run yet'}",
        "",
    ]
    sp = spend_by_task(after)
    L += [
        "## Cost by task (CR-009 run, non-cached calls from the call log)",
        "",
        "| task | USD |",
        "|---|---|",
    ]
    L += [f"| {k} | {v:.3f} |" for k, v in sorted(sp.items(), key=lambda kv: -kv[1])]
    L += [f"| **total** | **{sum(sp.values()):.2f}** |", ""]
    out_md.write_text("\n".join(L) + "\n", encoding="utf-8")
    _ = statistics
    return str(out_md)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default="slice3_b4")
    ap.add_argument("--after", required=True)
    ap.add_argument("--org-before")
    ap.add_argument("--org-after")
    ap.add_argument("--out", default="reports/cr009_stop3.md")
    a = ap.parse_args()
    print(build(a.before, a.after, a.org_before, a.org_after, Path(a.out)))


if __name__ == "__main__":
    main()
