"""CR-056: why gold concept mentions are still missed under the highest-recall concept settings (default `cr055b`) ($0, read-only).

Adds to the CR-054 stage trace: (1) recall by position inside the generator's unit (a unit is up to 2,500 words, `pd_run.make_units`);
(2) skipped paragraphs: paragraphs holding gold mentions where the generator produced no item at all in any iteration; (3) the span
misses split by whether the CR-052 placement rules would fix them.

    uv run python -m cumap.cr056.misses [--tag cr055b] [--control cr053v5]    # reports/cr056/misses.{json,md}
Train / dev papers only (rule 9)."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter

from cumap.concepts_v4.pd_run import make_units
from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr019 import variants as V
from cumap.cr043.papers import first_set
from cumap.cr043.run import run_id
from cumap.cr052 import extend as X
from cumap.cr054 import recall as R54

OUT = REPO_ROOT / "reports" / "cr056"


def paragraphs(doc) -> list[tuple[str, int, int, int]]:
    """(unit id, paragraph number in the unit, char start, char end) for every paragraph, in text order, with the production units."""
    units = make_units(
        [
            {
                "section_id": doc.doc_key,
                "order_index": 0,
                "text": doc.text,
                "heading_path": [doc.doc_key],
            }
        ]
    )
    out, pos = [], 0
    for u in units:
        for k, p in enumerate([p for p in re.split(r"\n\s*\n", u["text"]) if p.strip()], 1):
            a = doc.text.index(p, pos)
            out.append((u["section_id"], k, a, a + len(p)))
            pos = a + len(p)
    return out


def items_by_para(rid: str) -> Counter:
    v = json.loads((PG.run_path(rid) / "v4_concepts.json").read_text())
    c: Counter = Counter()
    for sid, s in v["sections"].items():
        for it in s.get("iterations") or []:
            o = it.get("output") or {}
            for k in ("new_concepts", "existing_mentions"):
                for x in o.get(k) or []:
                    c[(sid, x.get("para"))] += 1
    return c


def analyse(tag: str, control: str) -> dict:
    ad = SciNLPAdapter()
    papers = first_set()
    gold = {s: ad.gold(s) for s in {s for s, _ in papers}}
    docs = {
        s: {d.doc_key: d for d in ad.load_documents(s, paragraph_every=SR.PARAGRAPH_EVERY)}
        for s in gold
    }
    pos = {t: Counter() for t in (tag, control)}
    hit = {t: Counter() for t in (tag, control)}
    para_rows, skipped, span_fix = [], Counter(), Counter()
    for s, d in papers:
        doc, g = docs[s][d], gold[s][d]
        paras = paragraphs(doc)
        ulen = Counter()
        for u, _k, a, b in paras:
            ulen[u] += b - a
        ustart = {}
        for u, _k, a, _b in paras:
            ustart.setdefault(u, a)
        found = {}
        for t in (tag, control):
            cp = json.loads((PG.run_path(run_id(d, t)) / "checkpoint.json").read_text())
            found[t] = {
                m for n in V.sc_predict_indexed(doc, cp, "r1key")["nodes"] for m in n.mentions
            }
            if t == tag:
                ext = {X.extend(doc.tokens, m, ("X-acr", "X-head")) for m in found[t]}
        ibp = items_by_para(run_id(d, tag))
        per_para = Counter()
        miss_para = Counter()
        for m in g.mentions:
            c0 = doc.span_to_chars(m.span)[0]
            u, k, a, b = next(p for p in paras if p[2] <= c0 < p[3] + 2)
            q = min(
                4,
                int(
                    5
                    * (c0 - ustart[u])
                    / max(1, ulen[u] + 2 * len([p for p in paras if p[0] == u]))
                ),
            )
            for t in (tag, control):
                pos[t][q] += 1
                hit[t][q] += m.span in found[t]
            per_para[(u, k)] += 1
            if m.span not in found[tag]:
                miss_para[(u, k)] += 1
                if any(x[0] < m.span[1] and m.span[0] < x[1] for x in found[tag]):
                    span_fix["fixed_by_X_rules" if m.span in ext else "not_fixed_by_X_rules"] += 1
        for (u, k), n in per_para.items():
            gen = ibp.get((u, f"P{k}"), 0)
            para_rows.append(
                {
                    "paper": d,
                    "unit": u,
                    "para": k,
                    "gold": n,
                    "missed": miss_para[(u, k)],
                    "generator_items": gen,
                }
            )
            if gen == 0:
                skipped["paragraphs"] += 1
                skipped["gold_mentions"] += n
                skipped["missed"] += miss_para[(u, k)]
    rec = {
        t: [round(hit[t][q] / pos[t][q], 3) if pos[t][q] else None for q in range(5)] for t in pos
    }
    stages = R54.analyse(tag)["rows"]
    return {
        "tag": tag, "control": control,
        "recall_by_unit_position_quintile": rec, "mentions_by_quintile": [pos[tag][q] for q in range(5)],
        "skipped_paragraphs": dict(skipped), "paragraphs_with_gold": len(para_rows),
        "span_misses": dict(span_fix),
        "stage": dict(Counter(x["stage"] for x in stages)),
        "never": R54.describe_never(stages),
        "rows": stages, "para_rows": para_rows,
    }  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="cr055b")
    ap.add_argument("--control", default="cr053v5")
    a = ap.parse_args()
    r = analyse(a.tag, a.control)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "misses.json").write_text(
        json.dumps(
            {k: v for k, v in r.items() if k not in ("rows", "para_rows")}, indent=1, default=str
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {k: v for k, v in r.items() if k not in ("rows", "para_rows", "never")},
            indent=1,
            default=str,
        )
    )
    print(json.dumps(r["never"]["classes"]), json.dumps(r["never"]["by_type"]))
    print(json.dumps(r["never"]["top_surfaces"]))


if __name__ == "__main__":
    main()
