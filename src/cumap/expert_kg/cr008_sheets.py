"""CR-008 §7: owner sheets (STOP 2). Sheets go to `data/interim/checks/` (CR-003 rules: blind, no model
scores, pre-fills labelled); the owner saves the filled copy to `data/gold/`. Code never writes gold."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from cumap.expert_kg.alias_rules import r1_key
from cumap.schemas.relations import RelationRegistry


def _write(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def write_merge_sheet(cp: dict, ctx, out_dir: Path, per_rule: int = 10) -> dict:
    """Stratified by rule: <=10 R1, <=10 R2, every R3-strong (or 10), every R3-weak review item, every
    acronym collision, every alias_contradicted flag, every equivalence_migration item for the owner."""
    rk = cp["rekey"]
    rows: list[tuple[str, str, str, str, str]] = []  # (kind, section, a, b, quote)
    by_rule: dict[str, list] = defaultdict(list)
    for r in rk["merge_records"]:
        by_rule[r["rule_id"]].append(r)
    for rule, cap in (("R1", per_rule), ("R2", per_rule), ("R3-strong", per_rule)):
        for r in by_rule.get(rule, [])[:cap]:
            rows.append(
                (
                    rule,
                    r["section_id"] or "",
                    r["surface_forms"][0],
                    r["surface_forms"][1],
                    r["evidence_quote"],
                )
            )
    names = {c["concept_id"]: c["canonical_name"] for c in cp["concepts"]}
    key_to_id = {
        r1_key(f, ctx.cfg): c["concept_id"]
        for c in cp["concepts"]
        for f in (c["canonical_name"], *c.get("aliases", []))
    }
    for pair, stmts in ctx.weak.items():
        a, b = sorted(pair)
        if a in key_to_id and b in key_to_id and key_to_id[a] != key_to_id[b]:
            st = stmts[0]
            rows.append(("R3-weak", "", st.x_surface, st.y_surface, st.quote))
    for f in rk.get("alias_contradicted", []):
        rows.append(
            (
                "alias_contradicted",
                f.get("section_id") or "",
                f["forms"][0],
                f["forms"][1],
                f["quote"],
            )
        )
    for e in rk.get("equivalence", []):
        if e["migration"] == "owner_sheet":
            rows.append(("equivalence_migration", e["section_id"], e["x"], e["y"], e["quote"]))
    sheet = [[i, s, a, b, q, "", ""] for i, (_k, s, a, b, q) in enumerate(rows, 1)]
    key = [[i, k] for i, (k, *_r) in enumerate(rows, 1)]
    _write(
        out_dir / "cr008_merge_sheet.csv",
        ["id", "section", "name_A", "name_B", "evidence", "mark (same/different)", "note"],
        sheet,
    )
    _write(out_dir / "cr008_merge_key.csv", ["id", "source"], key)
    del names
    return dict(Counter(k for k, *_r in rows))


def _plain(item: dict, registry: RelationRegistry) -> str:
    if item["relation"] == "conflated_with":
        text = f"{item['source_name']} and {item['target_name']} are the same thing"
    else:
        text = registry.template_for(item["relation"], item["source_name"], item["target_name"])
    return f"It is NOT the case that {text}" if item["polarity"] == "negated" else text


def write_misconception_sheet(
    cp: dict, registry: RelationRegistry, edges: dict[str, dict], out_dir: Path, cap: int = 40
) -> dict:
    layer = cp["misconceptions"]
    items = layer["items"]
    if len(items) > cap:  # stratified by perturbation type
        buckets: dict[str, list] = defaultdict(list)
        for it in items:
            buckets[it["perturbation_type"]].append(it)
        picked: list[dict] = []
        while len(picked) < cap and any(buckets.values()):
            for b in buckets.values():
                if b and len(picked) < cap:
                    picked.append(b.pop(0))
        items = picked
    rows, key = [], []
    i = 0
    for it in items:
        i += 1
        correct = "; ".join(edges[e]["statement"] for e in it["contradicts"] if e in edges)
        rows.append(
            [
                i,
                it["section_id"],
                it["misconception_quote"]["quote"],
                it["correction_quote"]["quote"],
                _plain(it, registry),
                correct,
                "",
                "",
                "",
                "",
            ]
        )
        key.append([i, it["item_id"], it["perturbation_type"], "item"])
    for n in layer["needs_correct_edge"]:
        i += 1
        rows.append(
            [
                i,
                n["section_id"],
                n["proposed"].get("misconception_quote") or n["sentence"],
                n["proposed"].get("correction_quote") or "",
                n.get("intuition") or "",
                "(no correct edge yet: verifier rejected the proposal)",
                "",
                "",
                "",
                "",
            ]
        )
        key.append([i, "", "", "needs_correct_edge"])
    _write(
        out_dir / "cr008_misconception_sheet.csv",
        [
            "id",
            "section",
            "misconception quote",
            "correction quote",
            "wrong belief (plain)",
            "correct edge (plain)",
            "(a) does the book give this warning? yes/no",
            "(b) wrong edge a faithful version? yes/fix",
            "(b) fix (write it)",
            "(c) linked correct edge the right one? yes/no",
        ],
        rows,
    )
    _write(
        out_dir / "cr008_misconception_key.csv", ["id", "item_id", "perturbation_type", "kind"], key
    )
    return {
        "rows": len(rows),
        "items": len(layer["items"]),
        "needs_correct_edge": len(layer["needs_correct_edge"]),
    }
