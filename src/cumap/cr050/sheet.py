"""CR-050: a FRESH blind owner sheet of rejected generator links for measuring identity judge v1 against the adjudicator ($0, no model).

Source: the `G-link-rejected` entries of runs made after the CR-021 sheet (P&D rebuild `slice3_c3`, CR-043 SciNLP train / dev papers),
minus every item already on the CR-021 sheet (same dataset kind, section / paper, surface and target, case-folded). Blind: no model decision,
reason or rule output is shown. Same columns as the CR-021 sheet. Writes a DRAFT to data/interim/suggestions/ (never data/gold/, rule 2);
the owner marks it and saves it under data/gold/. SciNLP text is CC BY-NC: the sheet stays local.

    uv run python -m cumap.cr050.sheet"""

from __future__ import annotations

import csv
import glob
import hashlib
import json
import re

from cumap.concepts_v4.cards import Node
from cumap.config import REPO_ROOT
from cumap.cr021 import adjudicator as A
from cumap.cr021.review import COLUMNS, kind

OUT = REPO_ROOT / "data/interim/suggestions/cr050_identity_sheet_blind.csv"
KG = REPO_ROOT / "data/processed/kg"


def sources() -> list[tuple[str, str]]:
    pd = [("pd_production", "slice3_c3")]
    sc = sorted(
        ("scinlp_dev_train", p.split("/")[-2])
        for p in glob.glob(str(KG / "cr012_scinlp_cr043base_*" / "v4_concepts.json"))
    )
    return pd + sc


def _seen() -> set[tuple]:
    return {("pd" if r["dataset"] == "pd_production" else "sc", r["section_id"].split("#")[0], r["surface"].lower(), r["rejected_target"].lower()) for r in A.load_rows()}  # fmt: skip


def rows() -> list[dict]:
    seen, out, dup = _seen(), [], set()
    for ds, rid in sources():
        v = json.loads((KG / rid / "v4_concepts.json").read_text())
        nodes = v["nodes"] if isinstance(v["nodes"], list) else list(v["nodes"].values())
        by = {n["id"]: Node(n["id"], n["name"], n.get("aliases", []), n["node_type"], n["first_section"], n["first_order"]) for n in nodes}  # fmt: skip
        for m in v["merges"]:
            if m["rule_id"] != "G-link-rejected":
                continue
            if not re.search(r"[A-Za-z0-9]", m.get("surface") or "") or not re.search(
                r"[A-Za-z0-9]", m.get("evidence") or ""
            ):
                continue  # an empty or dash-only surface / evidence is not a reviewable link
            t = by[m["node_id"]]
            k = (
                "pd" if ds == "pd_production" else "sc",
                m["section_id"].split("#")[0],
                m["surface"].lower(),
                t.name.lower(),
            )
            if k in seen or k in dup:
                continue
            dup.add(k)
            out.append({"dataset": ds, "run_id": rid, "section_id": m["section_id"], "surface": m["surface"], "rejected_target": t.name,
                        "target_type": t.node_type, "rule_kind": kind(m["surface"], t), "evidence": m["evidence"]})  # fmt: skip
    out.sort(
        key=lambda r: hashlib.sha256(
            f"cr050|{r['run_id']}|{r['section_id']}|{r['surface']}|{r['rejected_target']}".encode()
        ).hexdigest()
    )
    for i, r in enumerate(out, 1):
        r["row"] = i
    return out


def main() -> dict:
    rs = rows()
    cols = [c for c in COLUMNS if c != "rule_promotes"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rs:
            w.writerow({**r, **{c: "" for c in cols if c.startswith("MARK_")}})
    from collections import Counter

    return {
        "path": str(OUT.relative_to(REPO_ROOT)),
        "rows": len(rs),
        "by_dataset": dict(Counter(r["dataset"] for r in rs)),
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
