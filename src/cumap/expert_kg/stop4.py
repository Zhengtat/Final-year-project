# ruff: noqa: ISC004, UP031, BLE001
"""CR-007 STOP 4: CR-005 vs CR-007 comparison report (§7) and blind review sheets (§8).

Read-only on the run; writes reports/cr007_stop4.md and data/interim/checks/*.csv. No API calls.
CR-005 baselines are the numbers measured in reports/cr007_stop1_diagnostics.md (run pdcanon2_30e2b4f9).
"""

from __future__ import annotations

import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from cumap.eval.stats import wilson_ci
from cumap.schemas.relations import RelationRegistry

BASE = {  # CR-005 (ch2-3 slice, 736 concepts, 381 resolved pairs) -- STOP 1 diagnostics (b)
    "pairs": 381,
    "edge": 121,
    "other": 117,
    "no_relation": 143,
    "linked": {"defined": (76, 509), "used": (21, 159), "mentioned": (7, 68), "all": (104, 736)},
    "mechanism_process_edges": 2,
}
ROLE_RANK = ["defined", "refined", "used", "mentioned"]


def _load(run_dir: Path) -> dict:
    return json.loads((run_dir / "checkpoint.json").read_text(encoding="utf-8"))


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _pct(n: int, d: int) -> str:
    return f"{n} / {d} = {100 * n / d:.1f}%" if d else "n/a"


def _ci(n: int, d: int) -> str:
    if not d:
        return "n/a"
    w = wilson_ci(n, d)
    return f"{100 * n / d:.1f}% (95% Wilson {100 * w.low:.1f}-{100 * w.high:.1f}%, n={d})"


def _outcome_bucket(r: dict) -> str:
    return "edge" if r["outcome"] == "edge" else r["outcome"]


def build(
    run_dir: Path,
    sections_jsonl: Path,
    registry: RelationRegistry,
    out_md: Path,
    checks_dir: Path,
    org_dir: Path | None = None,
    seed: int = 42,
) -> dict:
    cp = _load(run_dir)
    sec_ch = {r["section_id"]: r["chapter_num"] for r in _jsonl(sections_jsonl)}
    res = cp["relation_results_v3"]
    sel = [r for r in res if r["group"] == "selected"]
    smp = [r for r in res if r["group"] == "sample"]
    concepts = {c["concept_id"]: c for c in cp["concepts"]}

    lines: list[str] = ["# CR-007 STOP 4: CR-005 vs CR-007 on P&D ch1-3", ""]
    lines.append(
        f"Generated read-only from run `{cp['run_id']}`; no API calls. CR-005 numbers are the "
        "STOP 1 diagnostics (b) baselines (ch2-3 slice).\n"
    )

    # ---- outcomes
    oc = Counter(_outcome_bucket(r) for r in sel)
    n = len(sel)
    lines += [
        "## 1. Relation outcomes of the pairs classified",
        "",
        "| outcome | CR-005 (381 pairs, ch2-3) | CR-007 (%d pairs, ch1-3) |" % n,
        "|---|---|---|",
        f"| edge accepted | {_pct(BASE['edge'], BASE['pairs'])} | {_pct(oc['edge'], n)} |",
        f"| OTHER | {_pct(BASE['other'], BASE['pairs'])} | {_pct(oc['other'], n)} |",
        f"| NO_RELATION | {_pct(BASE['no_relation'], BASE['pairs'])} | {_pct(oc['no_relation'], n)} |",
        f"| rejected by a check | - | {_pct(oc['rejected'], n)} |",
        "",
    ]
    rej = Counter(r["reason"] for r in sel if r["outcome"] == "rejected")
    classified = n - oc["rejected"]
    lines.append(
        f"Rejection reasons: {dict(rej)}. OTHER share among pairs that passed the checks: "
        f"{_pct(oc['other'], classified)}."
    )
    lines.append(
        f"Target in the CR: OTHER <= 15%. Measured {100 * oc['other'] / n:.1f}% of all pairs "
        f"({100 * oc['other'] / classified:.1f}% of pairs not rejected).\n"
    )

    # ---- selection vs classifier effect
    attempted = set()
    for r in sel:
        attempted.add(r["pair"]["concept_x_id"])
        attempted.add(r["pair"]["concept_y_id"])
    core = [
        c
        for c in concepts.values()
        if any(m["role"] in ("defined", "refined", "used") for m in c["mentions"])
    ]
    core_att = [c for c in core if c["concept_id"] in attempted]
    lines += [
        "## 2. Selection effect vs classifier effect",
        "",
        f"- **Selection effect (attempted coverage):** concepts with >=1 classified pair: "
        f"{len(attempted)} of {len(concepts)} concepts (CR-005: 152 of 736). Defined/used concepts "
        f"attempted: {_pct(len(core_att), len(core))}.",
        f"- **Classifier effect (accepted rate among attempted pairs):** {_pct(oc['edge'], n)} "
        f"(CR-005 {_pct(BASE['edge'], BASE['pairs'])}).",
        "",
    ]

    # ---- by chapter (ch2-3 vs ch1-3 reported separately)
    lines += [
        "### By chapter of the evidence section",
        "",
        "| chapters | pairs | edges | OTHER | NO_RELATION | rejected |",
        "|---|---|---|---|---|---|",
    ]
    for label, chs in (("ch2-3 only", {2, 3}), ("ch1-3", {1, 2, 3}), ("ch1 only", {1})):
        sub = [r for r in sel if sec_ch.get(r["pair"]["section_id"]) in chs]
        c = Counter(_outcome_bucket(r) for r in sub)
        lines.append(
            f"| {label} | {len(sub)} | {c['edge']} | {c['other']} | {c['no_relation']} | {c['rejected']} |"
        )
    lines.append("")

    # ---- missed relation rate
    se = sum(1 for r in smp if r["outcome"] == "edge")
    lines += [
        "## 3. Estimated missed-relation rate (unselected sample)",
        "",
        f"{se} of {len(smp)} randomly drawn unselected candidate pairs classify as accepted edges: "
        f"**{_ci(se, len(smp))}**. Applied to {cp['selection_stats'].get('unique_candidate_pairs', '?')} "
        f"unique candidates minus {n} selected, this is an estimate of edges the pair budget leaves out "
        "(sample outcomes are not in the graph).",
        "",
    ]

    # ---- relations
    ec = Counter(r["relation"] for r in sel if r["outcome"] == "edge")
    fam = Counter(r["family"] for r in sel if r["outcome"] == "edge")
    dr = Counter(
        r["relation"] for r in sel if r["outcome"] == "rejected" and r["reason"] == "domain_range"
    )
    gate = {r.name: getattr(r, "gate", None) or "legacy" for r in registry.all_relations()}
    lines += [
        "## 4. Edges and domain/range rejections per relation",
        "",
        "| relation | gate | accepted edges | domain/range rejections |",
        "|---|---|---|---|",
    ]
    for rel in sorted(set(ec) | set(dr), key=lambda k: -ec[k]):
        lines.append(f"| {rel} | {gate.get(rel, '')} | {ec[rel]} | {dr[rel]} |")
    lines += [
        "",
        f"By family: {dict(fam)}. **mechanism_process edges: {fam['mechanism_process']}** "
        f"(CR-005: {BASE['mechanism_process_edges']}; target >= 20).",
        f"Endpoint-grounding rejections: {rej.get('endpoint_not_grounded', 0)}. "
        f"Domain/range rejections: {rej.get('domain_range', 0)}.",
        "",
    ]
    lines.append(
        "Generic `Concept` is a wildcard in the domain/range check (owner decision, 2026-10-01); "
        "the rejections above are specific wrong types only.\n"
    )

    # ---- linked share
    edges = [
        e for ch in (1, 2, 3) for e in _jsonl(run_dir / "snapshots" / f"ch{ch}" / "edges.jsonl")
    ]
    linked_ids = {e["source_concept_id"] for e in edges} | {e["target_concept_id"] for e in edges}
    by_role: dict[str, list[str]] = defaultdict(list)
    for cid, c in concepts.items():
        roles = {m["role"] for m in c["mentions"]}
        for role in ROLE_RANK:
            if role in roles:
                by_role[role].append(cid)
                break
    lines += [
        "## 5. Linked share by strongest role (concept has >=1 typed edge)",
        "",
        "| role | CR-005 | CR-007 |",
        "|---|---|---|",
    ]
    for role in ROLE_RANK:
        ids = by_role.get(role, [])
        base = BASE["linked"].get(role)
        lines.append(
            f"| {role} | {_pct(*base) if base else '-'} | "
            f"{_pct(sum(i in linked_ids for i in ids), len(ids))} |"
        )
    lines.append(
        f"| all | {_pct(*BASE['linked']['all'])} | "
        f"{_pct(sum(i in linked_ids for i in concepts), len(concepts))} |"
    )
    lines.append("")

    # ---- late counted
    late = 0
    for e in edges:
        ch = sec_ch.get(e["section_id"], 0)
        fcs = cp["concept_first_chapter"]
        fc = max(fcs.get(e["source_concept_id"], 0), fcs.get(e["target_concept_id"], 0))
        late += fc > ch > 0
    lines += [
        "## 6. Late-counted edges",
        "",
        f"Edges whose evidence section is in an earlier chapter than an endpoint's first chapter: "
        f"{late} of {len(edges)} (CR-005: 15 of 87 in ch2; target ~0).",
        "",
    ]

    # ---- corrects_intuition
    ci = [r for r in sel if r["outcome"] == "edge" and r["qualifiers"].get("corrects_intuition")]
    lines += ["## 7. corrects_intuition edges", ""]
    for r in ci:
        p = r["pair"]
        lines.append(
            f"- {p['section_id']}: {concepts[p['concept_x_id']]['canonical_name']} "
            f"-[{r['relation']}]-> {concepts[p['concept_y_id']]['canonical_name']}; "
            f'intuition: {r["qualifiers"].get("intuition")}; quote: "{r["evidence_quote"]}"'
        )
    if not ci:
        lines.append("None.")
    lines.append("")

    # ---- merges
    mrg = [m for m in cp["merges"] if m.get("llm_called") and not m.get("overridden")]
    lines += [
        "## 8. Merges",
        "",
        f"{len(cp['merges'])} merge records; {len(mrg)} needed an LLM call (non-trivial); "
        f"{len(cp['merge_review'])} routed to review (similarity < 0.70, not merged); "
        f"{len(cp['related_candidates'])} different-type near-duplicates kept as `related`. "
        "Merge precision awaits the owner sheet.",
        "",
    ]

    # ---- core-periphery
    if org_dir and (org_dir / "manifest.json").exists():
        lines += ["## 9. Core-periphery (CR-006 check on the new graph)", ""]
        chs = json.loads((org_dir / "manifest.json").read_text())["chapters"]
        for ch in (1, 2, 3):
            if str(ch) in chs:
                cpr = chs[str(ch)]["core_periphery"]
                prim = cpr["primary"]
                sec = cpr.get("secondary") or {}
                lines.append(
                    f"- ch{ch}: {cpr['label']}, rho {cpr['rho_obs']:.3f}; primary null delta "
                    f"{prim['delta_rho']:.3f} (z {prim['z']:.1f})"
                    + (
                        f"; second null delta {sec['delta_rho']:.3f} (z {sec['z']:.1f})"
                        if sec
                        else ""
                    )
                )
        lines.append("")

    lines += [
        "## 10. Concept extraction (IIR, from STOP 2)",
        "",
        "v2: lenient micro F1 0.433/0.444 (two executions of the test split); v3 (v2 + E3): 0.485 "
        "(see `reports/cr007_stop2_concepts.md`).",
        "",
    ]

    out_md.write_text("\n".join(lines), encoding="utf-8")

    sheets = write_sheets(cp, sel, concepts, registry, edges, checks_dir, seed)
    return {"report": str(out_md), **sheets}


def _template(registry: RelationRegistry, rel: str, a: str, b: str) -> str:
    try:
        t = registry.get(rel).template
        return t.replace("{X}", a).replace("{Y}", b)
    except Exception:
        return f"{a} {rel} {b}"


def write_sheets(
    cp: dict,
    sel: list[dict],
    concepts: dict,
    registry: RelationRegistry,
    edges: list[dict],
    checks_dir: Path,
    seed: int,
) -> dict:
    checks_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)

    # merges: all non-trivial LLM-approved merges + band-routed (blind: names and evidence only)
    mrows = []
    for m in cp["merges"]:
        if not m.get("llm_called") or m.get("overridden"):
            continue
        c = concepts.get(m["concept_id"])
        ev = (
            next((x["quote"] for x in c["mentions"] if x["section_id"] == m["section_id"]), "")
            if c
            else ""
        )
        mrows.append(
            (
                "merged",
                m["alias"],
                c["canonical_name"] if c else m["concept_id"],
                ev,
                m["section_id"],
            )
        )
    for r in cp["merge_review"]:
        c = concepts.get(r["concept_id"])
        mrows.append(("band", r["alias"], r["candidate_name"], r["quote"], r["section_id"]))
    rng.shuffle(mrows)
    with (checks_dir / "cr007_merge_sheet.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            ["id", "section", "name_A", "name_B", "evidence", "mark (same/different)", "note"]
        )
        for i, (_, a, b, q, s) in enumerate(mrows, 1):
            w.writerow([i, s, a, b, q, "", ""])
    with (checks_dir / "cr007_merge_key.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "source"])
        for i, row in enumerate(mrows, 1):
            w.writerow([i, row[0]])

    # relation edges: <=50, stratified; hub-first for half of each stratum
    deg: Counter = Counter()
    for e in edges:
        deg[e["source_concept_id"]] += 1
        deg[e["target_concept_id"]] += 1
    edge_res = [r for r in sel if r["outcome"] == "edge"]
    gated = {r.name for r in registry.all_relations() if getattr(r, "gate", None) == "gated"}
    picked: dict[str, dict] = {}

    def take(pool: list[dict], k: int) -> None:
        pool = [r for r in pool if r["pair"]["pair_id"] not in picked]
        pool.sort(key=lambda r: -(deg[r["pair"]["concept_x_id"]] + deg[r["pair"]["concept_y_id"]]))
        hubs, rest = pool[: (k + 1) // 2], pool[(k + 1) // 2 :]
        rng.shuffle(rest)
        for r in (hubs + rest)[:k]:
            picked[r["pair"]["pair_id"]] = r

    for rel in ("acts_on", "connected_to"):
        take([r for r in edge_res if r["relation"] == rel], 5)
    for rel in sorted(gated):
        take([r for r in edge_res if r["relation"] == rel], 8)
    fams = sorted({r["family"] for r in edge_res})
    per = max(1, 20 // max(1, len(fams)))
    for fm in fams:
        take(
            [
                r
                for r in edge_res
                if r["family"] == fm
                and r["relation"] not in ("acts_on", "connected_to")
                and r["relation"] not in gated
            ],
            per,
        )
    rows = list(picked.values())[:50]
    rng.shuffle(rows)
    with (checks_dir / "cr007_edge_sheet.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "id",
                "source_sentence",
                "triple_to_judge",
                "as_a_sentence",
                "mark (correct/incorrect/wrong-direction/wrong-granularity)",
                "note",
            ]
        )
        for i, r in enumerate(rows, 1):
            p = r["pair"]
            x, y = (
                concepts[p["concept_x_id"]]["canonical_name"],
                concepts[p["concept_y_id"]]["canonical_name"],
            )
            a, b = (y, x) if r["direction"] == "reversed" else (x, y)
            w.writerow(
                [
                    i,
                    p["sentence"],
                    f"{a}  —[{r['relation']}]→  {b}",
                    _template(registry, r["relation"], a, b),
                    "",
                    "",
                ]
            )
    with (checks_dir / "cr007_edge_key.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "pair_id", "section", "family", "relation", "evidence_quote"])
        for i, r in enumerate(rows, 1):
            w.writerow(
                [
                    i,
                    r["pair"]["pair_id"],
                    r["pair"]["section_id"],
                    r["family"],
                    r["relation"],
                    r["evidence_quote"],
                ]
            )
    return {
        "merge_rows": len(mrows),
        "edge_rows": len(rows),
        "edge_rows_by_relation": dict(Counter(r["relation"] for r in rows)),
    }
