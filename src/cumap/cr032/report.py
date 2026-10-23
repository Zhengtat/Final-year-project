"""CR-032 report text, generated from the result dict only (no claim that is not a number in it)."""

from __future__ import annotations


def f(x) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def triple(d: dict) -> str:
    return f"{f(d['precision'])} / {f(d['recall'])} / **{f(d['f1'])}** (tp {d['tp']}, fp {d['fp']}, fn {d['fn']})"


def markdown(r: dict) -> str:
    L = [
        "# CR-032 broader Hierarchy F1 (`HIER-T1`, `HIER-T1-SURF-R1`) ($0, no model call)",
        "",
        "Written for: the project owner and Research. New, named scorer variants reported beside the frozen numbers (rule 35); no frozen number is replaced.",
        "",
        f"Hierarchy set, read from the registry (family `classification_structure`, transitive): P&D (v1.3) `{r['hierarchy_set_pd']}` (chains only within a part type: `{r['typed_relations_pd']}`); SciNLP (v1.4) `{r['hierarchy_set_scinlp']}` = SciNLP labels `{r['scinlp_labels']}`.",
        "",
        "## Determinism gate",
        "",
        "| check | result |",
        "|---|---|",
        *[f"| {k} | {'PASS' if v else 'FAIL'} |" for k, v in r["gate"]["checks"].items()],
        "",
        f"**Gate: {'PASSED' if r['gate']['passed'] else 'FAILED, no figure should be used'}.** Source hashes identical before and after: **{r['hashes_unchanged']}** ({r['n_hashed']} files).",
        "",
        "## P&D-E2E (concept-level gold; per-section closure; frozen CR-012 mention-span alignment)",
        "",
        "`frozen is_a` = the CR-017 Ancestor Hierarchy F1. `HIER-T1` pools `is_a` and `part_of` (closed separately; `part_of` per part type). P / R / F1.",
        "",
        "| run | sections | frozen `is_a` | `HIER-T1` | `HIER-T1` direct edges | gold pairs (direct edges) |",
        "|---|---|---|---|---|---|",
    ]
    for k, v in r["pd"].items():
        L.append(
            f"| {k} | {len(v['sections'])} | {triple(v['frozen_is_a_cr017'])} | {triple(v['HIER_T1'])} | {triple(v['HIER_T1_direct_edges'])} | {v['gold_pairs']} ({v['gold_direct_edges']}) |"
        )
    L += [
        "",
        "Per-relation F1 inside `HIER-T1` (pairs of that relation only):",
        "",
        "| run | relation | P / R / F1 |",
        "|---|---|---|",
    ]
    for k, v in r["pd"].items():
        for rel, x in v["HIER_T1_per_relation"].items():
            L.append(f"| {k} | `{rel}` | {triple(x)} |")
    notes = [f"- {k}: cycles {v['cycles']}" for k, v in r["pd"].items() if v["cycles"]] + [
        f"- {k}: `part_of` edges without a part type scored as direct only: gold {v['direct_only_edges']['gold']}, predicted {v['direct_only_edges']['predicted']}"
        for k, v in r["pd"].items()
        if v["direct_only_edges"]["gold"] or v["direct_only_edges"]["predicted"]
    ]
    L += ["", *(notes or ["No cycles and no `part_of` edge without a part type."]), ""]
    L += [
        "## SciNLP test (mention-level gold, no identity gold)",
        "",
        "`HIER-T1-SURF-R1` infers identity from strings (R1 name key plus acronym <-> long form within one paper). It is a labelled cross-check, never a headline. Unplaced predicted edges are false positives in every variant except `FROZEN` (rule 35).",
        "",
        f"Real concept matching (`HIER-T1` with the owner's scoped identity sheet): **{r['real_identity_marks']}**."
        + (
            f" The blind sheet has {r['identity_sheet_rows_written']} rows."
            if r.get("identity_sheet_rows_written")
            else ""
        ),
        "",
    ]
    for lab, s in r["scinlp"].items():
        L += [
            f"### {lab}",
            "",
            f"Documents ({len(s['documents'])}): {', '.join(s['documents'])}.",
            "",
        ]
        L += [
            "| variant | `HIER-T1-SURF-R1` P / R / F1 | direct edges | same set, surface identity (CR-022 A2 rule) | gold pairs (direct) | unplaced as FP |",
            "|---|---|---|---|---|---|",
        ]
        for v, e in s["variants"].items():
            L.append(
                f"| `{v}` | {triple(e['HIER_T1_SURF_R1'])} | {triple(e['HIER_T1_SURF_R1_direct_edges'])} | {triple(e['same_set_surface_identity'])} | {e['gold_pairs']} ({e['gold_direct_edges']}) | {e['unplaced_counted_as_fp']} |"
            )
        first = next(iter(s["variants"].values()))
        L += ["", "Per-label F1 (first variant):", "", "| label | P / R / F1 |", "|---|---|"]
        L += [
            f"| `{lab2}` | {triple(x)} |"
            for lab2, x in first["HIER_T1_SURF_R1_per_relation"].items()
        ]
        if "collisions" in s:
            tot = {
                k: sum(c[k] for c in s["collisions"].values())
                for k in (
                    "gold_mentions",
                    "gold_nodes",
                    "collisions",
                    "nodes_merging_distinct_surfaces",
                )
            }
            ex = [e for c in s["collisions"].values() for e in c["examples"]][:6]
            L += [
                "",
                f"Identity cost (gold): {tot['gold_mentions']} mentions -> {tot['gold_nodes']} pseudo-nodes ({tot['collisions']} collisions); {tot['nodes_merging_distinct_surfaces']} nodes merge more than one distinct surface. Examples of merged surfaces: {ex}.",
            ]
        L.append("")
    L += [
        "## Limits",
        "",
        "- SciNLP identity is inferred from strings in this report; the real-identity figure waits for the owner's scoped identity sheet (hierarchy-relation endpoints only).",
        "- The explorer scorecard does not yet show these variants (not wired in this change).",
        "- P&D pilot has runs for fewer levels than held-out; only existing runs are reported. Small n: no confidence interval is attempted.",
    ]
    return "\n".join(L) + "\n"
