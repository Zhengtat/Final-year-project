"""CR-021: owner review sheet of every rejected G-link in the retained runs ($0, no model). Writes a DRAFT to data/interim/suggestions/
(never data/gold/). The sheet contains source text (SciNLP is CC BY-NC), so it stays local and is not committed.

    uv run python -m cumap.cr021.review"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter

from cumap.concepts_v4.cards import Node
from cumap.concepts_v4.runner import more_specific
from cumap.config import REPO_ROOT
from cumap.expert_kg.mentions import default_lemma

OUT = REPO_ROOT / "data/interim/suggestions/cr021_rejected_links_review.csv"
RUNS = {
    "pd_production": ["slice3_c2"],
    "scinlp_dev": [f"cr012_scinlp_cr019dev_{d}_E0" for d in ("2021_acl_long_295", "2024_acl_long_144_1_9_grobid", "P05_1008_grobid", "P16_1007_grobid", "P02_1004_grobid", "P03_1014_grobid")],
    "scinlp_test": [f"cr012_scinlp_heldout_{d}_E0" for d in ("2021_acl_long_353", "2024_acl_long_108_1_9_grobid", "P17_1058_grobid")],
}  # fmt: skip
COLUMNS = ["row", "dataset", "run_id", "section_id", "surface", "rejected_target", "target_type", "rule_kind", "rule_promotes", "evidence",
           "MARK_distinct_concept (yes/no)", "MARK_same_as_target (yes/no)", "MARK_note"]  # fmt: skip


def kind(surface: str, target: Node) -> str:
    if more_specific(surface, target):
        return "more_specific"
    lem = lambda f: {default_lemma(t) for t in re.findall(r"[a-z0-9]+", f.lower())}
    s = lem(surface)
    return "shortened" if any(s and s < lem(f) for f in target.forms()) else "different_words"


def rows() -> list[dict]:
    out = []
    for ds, rids in RUNS.items():
        for rid in rids:
            path = REPO_ROOT / "data/processed/kg" / rid / "v4_concepts.json"
            if not path.exists():
                continue
            v = json.loads(path.read_text())
            nodes = v["nodes"] if isinstance(v["nodes"], list) else list(v["nodes"].values())
            by = {n["id"]: Node(n["id"], n["name"], n.get("aliases", []), n["node_type"], n["first_section"], n["first_order"]) for n in nodes}  # fmt: skip
            for m in v["merges"]:
                if m["rule_id"] != "G-link-rejected":
                    continue
                t = by[m["node_id"]]
                k = kind(m["surface"], t)
                out.append({"dataset": ds, "run_id": rid, "section_id": m["section_id"], "surface": m["surface"], "rejected_target": t.name,
                            "target_type": t.node_type, "rule_kind": k, "rule_promotes": "yes" if k == "more_specific" else "no", "evidence": m["evidence"]})  # fmt: skip
    out.sort(
        key=lambda r: (r["rule_promotes"] != "yes", r["dataset"], r["run_id"], r["surface"].lower())
    )
    for i, r in enumerate(out, 1):
        r["row"] = i
    return out


def main() -> dict:
    rs = rows()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rs:
            w.writerow({**{c: "" for c in COLUMNS}, **r})
    return {
        "sheet": str(OUT.relative_to(REPO_ROOT)),
        "rows": len(rs),
        "by_kind": {
            f"{d}:{k}": n
            for (d, k), n in Counter((r["dataset"], r["rule_kind"]) for r in rs).items()
        },
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
