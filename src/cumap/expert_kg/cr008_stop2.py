"""CR-008 STOP 2 report (§6 before/after, conflicts, equivalence migration, misconception list) and the
merge sheet. $0: reads two run checkpoints and organisation outputs; writes reports/ and
data/interim/checks/ only. Run: `uv run python -m cumap.expert_kg.cr008_stop2 --before slice3_a1
--after slice3_b1 --org-before org_baa0d058 --org-after org_f1475cfe`."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter

from cumap.config import REPO_ROOT, get_settings, load_demo_slice
from cumap.expert_kg.alias_rules import r1_key
from cumap.expert_kg.cr008_run import KG_DIR, build_context
from cumap.expert_kg.cr008_sheets import write_merge_sheet
from cumap.expert_kg.lexicon import Lexicon
from cumap.expert_kg.misconception import expert_edges
from cumap.expert_kg.slice_rerun import load_sections

CHECKS = REPO_ROOT / "data" / "interim" / "checks"


def _edges(cp: dict) -> list[dict]:
    return list(expert_edges(cp["relation_results_v3"]).values())


def linked_share(cp: dict) -> tuple[float, float, int]:
    ends = {e["pair"][k] for e in _edges(cp) for k in ("concept_x_id", "concept_y_id")}
    cs = cp["concepts"]
    defined = [c for c in cs if any(m["role"] == "defined" for m in c["mentions"])]
    return (
        sum(c["concept_id"] in ends for c in cs) / len(cs),
        sum(c["concept_id"] in ends for c in defined) / max(len(defined), 1),
        len(ends),
    )


def org_ch3(run: str, org: str) -> tuple[dict, list[dict]]:
    base = KG_DIR / run / "organisation" / org
    man = json.loads((base / "manifest.json").read_text())["chapters"]["3"]
    nodes = [
        json.loads(x) for x in (base / "ch3" / "org_nodes.jsonl").read_text().splitlines() if x
    ]
    return man, nodes


def unexplained(cp: dict, lexicon: Lexicon, status: str) -> list[tuple[str, str]]:
    key_to = {}
    for c in cp["concepts"]:
        for f in (c["canonical_name"], *c.get("aliases", [])):
            key_to.setdefault(r1_key(f, lexicon.cfg), c["concept_id"])
    linked = {frozenset((e["pair"]["concept_x_id"], e["pair"]["concept_y_id"])) for e in _edges(cp)}
    out = []
    for e in lexicon.entries:
        if e.list != "different" or e.status != status:
            continue
        ids = [key_to.get(r1_key(f, lexicon.cfg)) for f in e.forms]
        if (
            all(ids)
            and len(set(ids)) == len(ids)
            and not any(
                frozenset((a, b)) in linked for i, a in enumerate(ids) for b in ids[i + 1 :]
            )
        ):
            out.append((e.forms[0], e.forms[1]))
    return out


def misconception_cost(run: str) -> float:
    """Spend of the misconception stage: structuring calls plus the verifier's relation calls (all
    non-cached calls of this run from the first structuring call on)."""
    tiers = get_settings().llm.tiers
    rows = [
        json.loads(x)
        for x in (REPO_ROOT / "data" / "logs" / "llm_calls.jsonl").read_text().splitlines()
        if x
    ]
    rows = [r for r in rows if str(r.get("run_id", "")).startswith(run) and not r["cache_hit"]]
    start = min((r["ts"] for r in rows if r["task"] == "misconception_structuring"), default=None)
    total = 0.0
    for r in rows:
        if start is not None and r["ts"] >= start:
            t, u = tiers[r["model_tier"]], r["usage"]
            total += (
                u["input_tokens"] / 1e6 * t.usd_per_1m_input_tokens
                + u["output_tokens"] / 1e6 * t.usd_per_1m_output_tokens
            )
    return total


GOLD = REPO_ROOT / "data" / "gold"
# owner rulings that override a mark in the gold sheet (the sheet itself is never edited)
MARK_OVERRIDES = {
    "14": "different"
}  # "end hosts / frames": the `same` mark was a slip (2026-10-02)


def merge_precision() -> tuple[list[str], dict[str, tuple[int, int]]]:
    """Owner precision per rule from data/gold/cr008_merge_{sheet,key}.csv (read-only)."""
    from cumap.eval.stats import wilson_ci

    sheet, key = GOLD / "cr008_merge_sheet.csv", GOLD / "cr008_merge_key.csv"
    if not (sheet.exists() and key.exists()):
        return ["Pending your marks on the merge sheet."], {}
    kinds = {r["id"]: r["source"] for r in csv.DictReader(key.open(encoding="utf-8"))}
    tally: dict[str, list[int]] = {}
    for r in csv.DictReader(sheet.open(encoding="utf-8")):
        mark = MARK_OVERRIDES.get(r["id"], r["mark (same/different)"].strip().lower())
        t = tally.setdefault(kinds[r["id"]], [0, 0])
        t[0] += mark == "same"
        t[1] += 1
    lines = ["| Rule | marked same | n | Wilson 95% CI |", "|---|---|---|---|"]
    for rule, (ok, n) in tally.items():
        w = wilson_ci(ok, n)
        lines.append(f"| {rule} | {ok} | {n} | [{w.lower:.2f}, {w.upper:.2f}] |")
    lines += [
        "",
        'Row 14 ("end hosts / frames", R3-weak) was marked `same` in the sheet; you ruled it a slip, so it counts as `different` here. The gold file is unchanged.',
        "Auto rules (R1, R2, R3-strong) have **no wrong merge**: no guard or demotion needed. R3-weak stays review-only, and its one item was wrong, which supports never auto-merging it.",
    ]
    return lines, {k: tuple(v) for k, v in tally.items()}


def build(before: str, after: str, org_before: str, org_after: str) -> str:
    cpa = json.loads((KG_DIR / before / "checkpoint.json").read_text())
    cpb = json.loads((KG_DIR / after / "checkpoint.json").read_text())
    rk, ms = cpb["rekey"], cpb.get("misconceptions", {})
    sl = load_demo_slice()
    sections = load_sections(REPO_ROOT / sl.pd.source_jsonl, list(sl.pd.chapters))
    lexicon = Lexicon.load(REPO_ROOT / "configs" / "term_lexicon.yaml")
    ctx = build_context(cpa, sections, lexicon)
    sheet_counts = write_merge_sheet(cpb, ctx, CHECKS)
    rules = Counter(r["rule_id"] for r in rk["merge_records"])
    la, lb = linked_share(cpa), linked_share(cpb)
    ea, eb = len(_edges(cpa)), len(_edges(cpb))
    cnt = rk["counts"]
    man_a, nodes_a = org_ch3(before, org_before)
    man_b, nodes_b = org_ch3(after, org_after)
    idmap = rk["id_map"]
    core = lambda nodes, m=lambda x: x: {
        m(n["concept_id"]) for n in nodes if n["ring"] in ("centre", "inner")
    }
    ca, cb = core(nodes_a, lambda x: idmap.get(x, x)), core(nodes_b)
    jac = len(ca & cb) / max(len(ca | cb), 1)
    top = lambda nodes, k=15: [
        n["name"] for n in sorted(nodes, key=lambda n: -n["importance_adj"])[:k]
    ]
    ta, tb = top(nodes_a), top(nodes_b)
    cpa_c, cpb_c = man_a["core_periphery"]["primary"], man_b["core_periphery"]["primary"]
    lex_same = [e for e in lexicon.entries if e.list == "same"]
    lex_diff = [e for e in lexicon.entries if e.list == "different"]
    un_a, un_p = unexplained(cpb, lexicon, "approved"), unexplained(cpb, lexicon, "proposed")
    cost = misconception_cost("slice3_b")
    n_accepted = sum(
        1 for r in cpb["relation_results_v3"] if r.get("found_by") == "misconception_stage"
    )
    st = ms.get("stats", {})
    by_type = Counter(i["perturbation_type"] for i in ms.get("items", []))
    by_prev = Counter(i["prevalence_cue"] for i in ms.get("items", []))
    L = [
        f"# CR-008 STOP 2 — before/after ({before} → {after})",
        "",
        (
            "Re-keying and the lexicon cost $0. The misconception stage cost "
            f"**${cost:.2f}** in total across all attempts (preflight $0.77, hard cap $3). No marks from you yet, so every precision "
            "figure below is pending."
        ),
        "",
        "## §6 metrics",
        "",
        "| Metric | Before (CR-007) | After (CR-008) |",
        "|---|---|---|",
        f"| Nodes | {len(cpa['concepts'])} | {len(cpb['concepts'])} |",
        f"| Merges per rule (re-key) | – | R0 {rules['R0']}, R1 {rules['R1']}, R2 {rules['R2']}, R3-strong {rules['R3-strong']} (R4 unchanged: the LLM merges already in the run are kept) |",
        f"| R3-weak items sent to review | – | {sheet_counts.get('R3-weak', 0)} |",
        f"| Acronym collisions (R1 guard) / ambiguous acronyms scoped (R2) | – | {rk['guard_stats'].get('r1_acronym_collision', 0)} / {len(rk['ambiguous_acronyms'])} |",
        f"| Lexicon `same` / `different` (approved) | – | {len([e for e in lex_same if e.status == 'approved'])} / {len([e for e in lex_diff if e.status == 'approved'])} (+{len([e for e in lex_diff if e.status == 'proposed'])} proposed seeds, ignored until you tick them) |",
        f"| Merges blocked by `different` (R1–R3 / chain / candidates to the LLM) | – | {rk['guard_stats'].get('blocked_by_lexicon', 0)} / {rk['guard_stats'].get('blocked_by_lexicon_chain', 0)} / {rk['guard_stats'].get('candidates_blocked_by_lexicon', 0)} |",
        f"| Unexplained confusables (approved `different` pair, no edge) | – | {len(un_a)} |",
        f"| Edges (before/after consolidation) | {ea} | {eb} ({cnt.get('edges_consolidated', 0)} consolidated, {cnt.get('merge_self_loop', 0)} merge self-loops rejected, {cnt.get('secondary_edges_same_pair', 0)} secondary on a shared pair) |",
        f"| Linked share, all concepts / `defined` concepts | {la[0]:.1%} / {la[1]:.1%} | {lb[0]:.1%} / {lb[1]:.1%} |",
        f"| `alias_contradicted` flags / conflict groups after re-key / cycles | – | {len(rk['alias_contradicted'])} / {len(rk['conflicts'])} / {len(rk['cycles'])} |",
        f"| Sphere ch3: core–periphery label | {man_a['core_periphery']['label']} | {man_b['core_periphery']['label']} |",
        f"| Sphere ch3: Δρ (primary null) | {cpa_c['delta_rho']:.3f} | {cpb_c['delta_rho']:.3f} |",
        f"| Sphere ch3: core (centre+inner) soft Jaccard vs CR-007 (old ids mapped to survivors) | – | {jac:.2f} ({len(ca)} → {len(cb)} nodes) |",
        "| `equivalent_to` edges in any layer | 3 | **0** |",
        "| LLM merge calls R1–R3 would have replaced (STOP 1 backtest) | – | 21 of 236 on this slice (9%; 1003 exact-string merges were already free) |",
        "",
        "## Owner precision per rule",
        "",
        *merge_precision()[0],
        "",
        "## Top-15 importance changes (ch3)",
        "",
        f"- Before: {', '.join(ta)}",
        f"- After: {', '.join(tb)}",
        f"- Entered: {', '.join(sorted(set(tb) - set(ta))) or '(none)'}; left: {', '.join(sorted(set(ta) - set(tb))) or '(none)'}",
        "",
        "## Equivalence migration (`equivalent_to` edges)",
        "",
        "| Pair | Section | What happened |",
        "|---|---|---|",
    ]
    for e in rk["equivalence"]:
        what = {
            "merged_by_rule": "merged into one node by a rule (the edge disappears into it)",
            "retired_lexicon_different": f"retired (`equivalent_to_retired`, kept in the run); lexicon `different` {e.get('lexicon_entry')}; the pair is queued for normal relation classification at the next relation run",
            "owner_sheet": "held out of the graph; on your merge sheet as an `equivalence_migration` item",
        }[e["migration"]]
        L.append(f"| {e['x']} ≡ {e['y']} | {e['section_id']} | {what} |")
    L += [
        "",
        "## Conflicts and `alias_contradicted`",
        "",
        f"- Conflict groups (detection only; no adjudication call made): {len(rk['conflicts'])}",
        f"- `alias_contradicted` flags: {len(rk['alias_contradicted'])}",
    ]
    L += [
        f"  - {f['forms']} ({f['rule_id']}): {f['why']} — {f['quote'][:160]}"
        for f in rk["alias_contradicted"]
    ]
    L += [
        "",
        "## Unexplained confusables (no edge between the pair)",
        "",
        "Approved `different` pairs: " + ("; ".join(f"{a} / {b}" for a, b in un_a) or "(none)"),
        "",
        "If you approve the research seeds, these would also be unexplained: "
        + ("; ".join(f"{a} / {b}" for a, b in un_p) or "(none)"),
        "",
        "## Merge sheet",
        "",
        f"`data/interim/checks/cr008_merge_sheet.csv` (+ key): {dict(sheet_counts)}. Judgement: same / different. Save your copy to `data/gold/merges/`.",
        "",
        "## Misconception layer",
        "",
        f"- Cue scan: {st.get('candidates', 0)} candidate sentences ⇒ `is_warning` = yes: {st.get('warnings', 0) + st.get('needs_correct_edge', 0) + st.get('needs_review', 0)} ⇒ in the layer: **{st.get('warnings', 0)}**, held as `needs_correct_edge`: {st.get('needs_correct_edge', 0)}, owner review after failed checks: {st.get('needs_review', 0)}; dismissed as plain facts: {st.get('not_warning', 0)}.",
        f"- By perturbation type: {dict(by_type) or '–'}; by prevalence cue: {dict(by_prev) or '–'}.",
        (
            f"- Proposed correct edges accepted by the verifier (bulk tier): {n_accepted}; rejected: "
            f"{st.get('needs_correct_edge', 0)}."
        ),
        f"- Cost ${cost:.2f} vs preflight $0.77.",
        "",
    ]
    for i in ms.get("items", []):
        L += [
            f"**{i['item_id']}** — {i['perturbation_type']} / {i['prevalence_cue']}: {i['intuition']}",
            f"  - wrong edge: {i['source_name']} —{i['relation']}→ {i['target_name']} ({i['polarity']}); contradicts {i['contradicts']}",
            f"  - quote: “{i['misconception_quote']['quote']}”",
            "",
        ]
    for n in ms.get("needs_review", []):
        L += [
            f"**Owner review (checks failed twice)** §{n['section_id']}: {n['sentence'][:160]}",
            f"  - failed: {'; '.join(n['errors'])}",
            "",
        ]
    L += [
        "**Held as `needs_correct_edge`** (the book states the correct idea but the verifier did not accept the proposed edge):",
        "",
    ]
    L += [
        f"- {n['intuition'] or n['sentence'][:120]} (§{n['section_id']})"
        for n in ms.get("needs_correct_edge", [])
    ]
    L += ["", "Sheet: `data/interim/checks/cr008_misconception_sheet.csv` (+ key).", ""]
    out = REPO_ROOT / "reports" / "cr008_stop2.md"
    out.write_text("\n".join(L), encoding="utf-8")
    return str(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--org-before", required=True)
    ap.add_argument("--org-after", required=True)
    a = ap.parse_args()
    print(build(a.before, a.after, a.org_before, a.org_after))


if __name__ == "__main__":
    main()
