"""STOP 2 summary (CR-006 §2 step 3), generated from an organisation run directory: per chapter
the top-15 by raw vs adjusted importance side by side, background vocabulary, unlinked count,
core-periphery fit vs both nulls, stability, and the 10 biggest movers with the edges that moved
them. Read-only."""

from __future__ import annotations

import json
from pathlib import Path

from cumap.organisation.inputs import OrgInputs

HIDDEN = ("unlinked", "background")


def _rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _cell(x) -> str:
    return str(x).replace("|", "\\|").replace("\n", " ")


def _num(x, fmt: str = ".2f") -> str:
    return "n/a" if x is None else format(x, fmt)


def _top15_table(rows: list[dict]) -> list[str]:
    ranked = [r for r in rows if r["ring"] not in HIDDEN]
    raw = sorted(ranked, key=lambda r: (-r["importance_raw"], r["name"]))[:15]
    adj = sorted(ranked, key=lambda r: (-r["importance_adj"], r["name"]))[:15]
    out = ["| # | raw: concept | raw | adjusted: concept | adj |", "|---|---|---|---|---|"]
    for i in range(15):
        a = raw[i] if i < len(raw) else None
        b = adj[i] if i < len(adj) else None
        left = f"{_cell(a['name'])} | {a['importance_raw']:.3f}" if a else " | "
        right = f"{_cell(b['name'])} | {b['importance_adj']:.3f}" if b else " | "
        out.append(f"| {i + 1} | {left} | {right} |")
    overlap = len({r["concept_id"] for r in raw} & {r["concept_id"] for r in adj})
    return [*out, "", f"Overlap of the two top-15 lists: {overlap}/15.", ""]


def _null_lines(cp: dict) -> list[str]:
    p, s = cp["primary"], cp["secondary"]
    primary = (
        f"mean {p['mean']:.3f} ± {p['sd']:.4f}, z {p['z']:.1f}, delta-rho {p['delta_rho']:.3f}"
    )
    secondary = (
        f"mean {s['mean']:.3f} ± {s['sd']:.4f}, z {s['z']:.1f}, delta-rho {s['delta_rho']:.3f}"
    )
    out = [
        "| | value |",
        "|---|---|",
        f"| nodes / edges in the fit | {cp['n_nodes']} / {cp['n_edges']} |",
        f"| rho observed | {cp['rho_obs']:.3f} |",
        f"| primary null (same-density random, n={p['n']}) | {primary} |",
        f"| secondary null (degree-preserving; reported, not gated) | {secondary} |",
        f"| **label (gated on the primary null)** | **{cp['label']}** |",
        "",
    ]
    if cp["banner"]:
        out += [f"> {cp['banner']}", ""]
    return out


def build_summary(org_dir: Path, inp: OrgInputs) -> str:
    manifest = json.loads((org_dir / "manifest.json").read_text(encoding="utf-8"))
    chapters = sorted(int(k) for k in manifest["chapters"])
    name = {c: k.name for c, k in inp.concepts.items()}
    edge = {e.edge_id: e for e in inp.edges}
    nodes = {
        ch: {r["concept_id"]: r for r in _rows(org_dir / f"ch{ch}" / "org_nodes.jsonl")}
        for ch in chapters
    }
    events = {ch: _rows(org_dir / f"ch{ch}" / "events.jsonl") for ch in chapters}
    basis_key = "importance_adj" if manifest["radius_basis"] == "adjusted" else "importance_raw"

    out = [
        f"# CR-006 STOP 2: organisation `{manifest['org_id']}`",
        "",
        (
            f"Run `{manifest['kg_run_id']}`, mode {manifest['mode']}, radius basis (config default, "
            f"owner to confirm) **{manifest['radius_basis']}**, config {manifest['config_hash']}, "
            f"code {manifest['code_version']}. Label source: {manifest['label_source']}. No API calls."
        ),
        "",
    ]
    for ch in chapters:
        s = manifest["chapters"][str(ch)]
        unlinked_share = s["n_unlinked"] / max(s["n_nodes"], 1)
        out += [
            f"## Chapter {ch}",
            "",
            (
                f"{s['n_nodes']} concepts, {s['n_edges']} typed edges (semantic + taxonomy); "
                f"eligible for rings {s['n_eligible']}; **unlinked {s['n_unlinked']}** "
                f"({unlinked_share:.0%}); background {s['n_background']}. Modularity coarse "
                f"{s['modularity_coarse']:.3f}, fine {s['modularity_fine']:.3f}."
            ),
            "",
            "### Top 15: raw vs adjusted importance",
            "",
            *_top15_table(list(nodes[ch].values())),
            "### Background vocabulary (generic guard)",
            "",
            ", ".join(sorted(name[c] for c in s["background_ids"])) or "(none flagged)",
            "",
            "### Is there a core? (Borgatti-Everett fit vs nulls)",
            "",
            *_null_lines(s["core_periphery"]),
        ]
        st = s["stability"]
        if st["jaccard_core"] is None:
            out += ["### Stability", "", "n/a (first snapshot).", ""]
        else:
            out += [
                "### Stability vs previous chapter",
                "",
                (
                    f"Core (centre + inner) Jaccard {st['jaccard_core']:.2f}; Kendall tau over "
                    f"{st['n_shared']} shared nodes {_num(st['kendall_tau'])}; mean displacement "
                    f"{_num(st['mean_displacement'], '.3f')} (unit disc)."
                ),
                "",
            ]
        if ch != chapters[0]:
            prev = nodes[chapters[chapters.index(ch) - 1]]
            movers = []
            for c, r in nodes[ch].items():
                p = prev.get(c)
                if p and r["ring"] not in HIDDEN and p["ring"] not in HIDDEN:
                    movers.append((abs(r[basis_key] - p[basis_key]), c, p, r))
            movers.sort(key=lambda t: (-t[0], name[t[1]]))
            out += [
                f"### 10 biggest movers (change in {manifest['radius_basis']} importance percentile)",
                "",
                "| concept | ring | change | new edges behind it |",
                "|---|---|---|---|",
            ]
            for _, c, p, r in movers[:10]:
                ev = next(
                    (e for e in events[ch] if e["subject_ids"] == [c] and e["because_edge_ids"]),
                    None,
                )
                ids = ev["because_edge_ids"] if ev else []
                why = (
                    "; ".join(
                        f"{name[edge[i].source]} -[{edge[i].relation}]-> {name[edge[i].target]} "
                        f"({edge[i].section_id})"
                        for i in ids[:4]
                        if i in edge
                    )
                    or "(neighbourhood shift; no new edge on the concept itself)"
                )
                change = r[basis_key] - p[basis_key]
                out.append(
                    f"| {_cell(name[c])} | {p['ring']} -> {r['ring']} | {change:+.3f} | {_cell(why)} |"
                )
            out.append("")
        flagged = sum(1 for r in nodes[ch].values() if r["persistent_periphery"])
        out += [
            "### Review flags",
            "",
            (
                f"Persistent periphery: {flagged} concepts (outer or unlinked with <= 1 typed edge "
                "for >= 2 snapshots; a flag for review, never a deletion)."
            ),
            "",
        ]
    return "\n".join(out) + "\n"
