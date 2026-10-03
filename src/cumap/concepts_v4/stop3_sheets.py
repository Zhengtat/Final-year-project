"""CR-009 §10 STOP 3 owner sheets (CR-003 rules: blind, in data/interim/checks/, the owner saves marked copies to
data/gold/, no model scores shown). `uv run python -m cumap.concepts_v4.stop3_sheets --run slice3_c1`."""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from pathlib import Path

ROOT = Path(".")
CHECKS = ROOT / "data" / "interim" / "checks"


def _w(path: Path, header: list[str], rows: list[list]) -> None:
    CHECKS.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def _sentence(text: str, form: str) -> str:
    for s in re.split(r"(?<=[.!?])\s+", " ".join(text.split())):
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(form)}", s, re.IGNORECASE):
            return s
    return ""


def build(run: str, seed: int = 9) -> dict:
    d = ROOT / "data/processed/kg" / run
    v4 = json.loads((d / "v4_concepts.json").read_text())
    nodes = list(v4["nodes"].values())
    by_id = v4["nodes"]
    rows = [
        json.loads(x)
        for x in (ROOT / "data/interim/textbook_sections.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if x
    ]
    text_of = {r["section_id"]: r["text"] for r in rows}
    rng = random.Random(seed)

    def orig(sid: str) -> str:
        return sid.split("#")[0]

    # ---- concepts: 12 independent, 12 anchored, 6 found_via_anchor, 10 random
    indep = [n for n in nodes if n["extraction_origin"] == "independent"]
    anch = [n for n in nodes if n["extraction_origin"] == "anchored" and not n["found_via_anchor"]]
    fva = [n for n in nodes if n["found_via_anchor"]]
    pick = (
        rng.sample(indep, min(12, len(indep)))
        + rng.sample(anch, min(12, len(anch)))
        + rng.sample(fva, min(6, len(fva)))
    )
    rest = [n for n in nodes if n not in pick]
    pick += rng.sample(rest, min(10, len(rest)))
    rng.shuffle(pick)
    srows, krows = [], []
    for i, n in enumerate(pick, 1):
        m0 = min(n["mentions"], key=lambda m: m["order"])
        a = n["anchors"][0] if n["anchors"] else None
        an = by_id.get(a["node_id"], {}).get("name", "") if a else ""
        srows.append(
            [
                i,
                n["name"],
                n["node_type"],
                orig(m0["section_id"]),
                m0["evidence"],
                "",
                "",
                an,
                a["cue"] if a else "",
                "" if a else "(none)",
            ]
        )
        krows.append(
            [i, n["extraction_origin"], n["found_via_anchor"], a["anchor_type"] if a else ""]
        )
    _w(
        CHECKS / f"cr009_stop3_concepts_{run}.csv",
        [
            "id",
            "concept",
            "type",
            "section",
            "evidence quote",
            "judgement (valid complete / partial / not a concept / generic)",
            "if partial: the full term",
            "anchored to (known concept)",
            "cue sentence",
            "anchor judgement (correct / wrong / should be independent)",
        ],
        srows,
    )
    _w(
        CHECKS / f"cr009_stop3_concepts_key_{run}.csv",
        ["id", "origin", "found_via_anchor", "anchor_type"],
        krows,
    )

    # ---- non-trivial G-links (<= 15)
    gl = [m for m in v4["merges"] if m["rule_id"] == "G-link"]
    gl = rng.sample(gl, min(15, len(gl)))
    _w(
        CHECKS / f"cr009_stop3_glinks_{run}.csv",
        ["id", "text form", "linked to node", "section", "evidence", "mark (same / not same)"],
        [
            [i, g["surface"], by_id[g["node_id"]]["name"], orig(g["section_id"]), g["evidence"], ""]
            for i, g in enumerate(gl, 1)
        ],
    )

    # ---- pruned: 10 random + every pruned_defined (up to 5 more)
    pdef = [p for p in v4["pruned"] if p.get("pruned_defined")]
    other = [p for p in v4["pruned"] if not p.get("pruned_defined")]
    pk = rng.sample(other, min(10, len(other))) + rng.sample(pdef, min(5, len(pdef)))
    rng.shuffle(pk)
    _w(
        CHECKS / f"cr009_stop3_pruned_{run}.csv",
        ["id", "term", "section", "evidence quote", "mark (correctly pruned / should be a node)"],
        [[i, p["name"], orig(p["section_id"]), p["evidence"], ""] for i, p in enumerate(pk, 1)],
    )
    _w(
        CHECKS / f"cr009_stop3_pruned_key_{run}.csv",
        ["id", "pruned_defined"],
        [[i, bool(p.get("pruned_defined"))] for i, p in enumerate(pk, 1)],
    )

    # ---- not-mentions and backfill rejections (10)
    items = []
    for sid, s in v4["sections"].items():
        for nm in s["final"]["not_mentions"]:
            nd = by_id.get(nm["node_id"])
            if nd:
                sent = _sentence(text_of.get(orig(sid), ""), nd["name"])
                if sent:
                    items.append(("not_mention", nd["name"], orig(sid), sent, nm["reason"]))
    for b in v4["backfill"]:
        for r in b.get("rejected", []):
            nd = None
            m = re.match(r"b(\d+)", r["hint_id"])
            if m and b.get("given"):
                idx = int(m.group(1)) - 1
                nd = by_id.get(b["given"][idx]) if idx < len(b["given"]) else None
            if nd:
                sent = _sentence(text_of.get(orig(b["section_id"]), ""), nd["name"])
                if sent:
                    items.append(
                        ("backfill_rejection", nd["name"], orig(b["section_id"]), sent, r["reason"])
                    )
    pk = rng.sample(items, min(10, len(items)))
    _w(
        CHECKS / f"cr009_stop3_rejections_{run}.csv",
        [
            "id",
            "known concept",
            "section",
            "sentence where the word occurs",
            "mark (correct rejection / actually a mention)",
        ],
        [[i, x[1], x[2], x[3], ""] for i, x in enumerate(pk, 1)],
    )
    _w(
        CHECKS / f"cr009_stop3_rejections_key_{run}.csv",
        ["id", "kind", "reason"],
        [[i, x[0], x[4]] for i, x in enumerate(pk, 1)],
    )

    # ---- verifier flags: 10 from the two busiest rules
    fl = []
    for sid, s in v4["sections"].items():
        it = s["iterations"][0]
        for f in it["flags"]:
            if f["rule"] in {"F3", "F2"} and f["where"] in {"new", "mention"}:
                key = "new_concepts" if f["where"] == "new" else "existing_mentions"
                if f["idx"] < len(it["output"][key]):
                    item = it["output"][key][f["idx"]]
                    fl.append(
                        (
                            f["rule"],
                            item.get("name") or item.get("surface"),
                            orig(sid),
                            item["evidence"],
                        )
                    )
    pk = rng.sample(fl, min(10, len(fl)))
    _w(
        CHECKS / f"cr009_stop3_flags_{run}.csv",
        [
            "id",
            "item the model listed",
            "section",
            "its evidence quote",
            "mark (valid flag = the item really is not supported by the quote / false flag)",
        ],
        [[i, x[1], x[2], x[3], ""] for i, x in enumerate(pk, 1)],
    )
    _w(
        CHECKS / f"cr009_stop3_flags_key_{run}.csv",
        ["id", "rule"],
        [[i, x[0]] for i, x in enumerate(pk, 1)],
    )
    return {
        "concepts": len(pick),
        "glinks": len(gl),
        "pruned": len(pk),
        "rejections": len(items),
        "flags": len(fl),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    print(build(ap.parse_args().run))
