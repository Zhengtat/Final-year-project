"""CR-052: why gold relation endpoints are missed at the concept stage (codes N0 / N1, `IDXR1-P1`) in the CR-043 baseline ($0, no model
call, read-only). For every distinct gold endpoint mention of a lost relation that no predicted mention matches exactly:
- N1 (`partial`): the overlapping predicted mention is longer, shorter, crossing or split; the token difference is classified
  (determiner, parenthetical / acronym, prepositional tail, coordination, modifier, plural / inflection, punctuation);
- N0 (`absent`): whether a predicted node already has that surface (name, alias, or the same R1 key: an occurrence the index did not
  place) or no node has it (the concept was never extracted), with the gold type.

    uv run python -m cumap.cr052.spans [--tag cr043base]      # reports/cr052/span_analysis.{json,md}
Train / dev papers only (rule 9)."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.stop4_score import sc_attribution
from cumap.cr019 import variants as V
from cumap.cr043.papers import first_set
from cumap.cr043.run import TAG, run_id

OUT = REPO_ROOT / "reports" / "cr052"
VARIANT = "IDXR1-P1"
DET = {
    "the",
    "a",
    "an",
    "our",
    "this",
    "these",
    "that",
    "those",
    "its",
    "their",
    "his",
    "her",
    "my",
    "your",
    "we",
    "each",
    "such",
    "both",
    "all",
}
PREP = {"of", "for", "in", "on", "with", "to", "from", "by", "over", "via", "at", "as"}
COORD = {"and", "or", "/", "&", "nor"}


def r1(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def stem(t: str) -> str:
    t = t.lower()
    for suf in ("ies", "es", "s"):
        if t.endswith(suf) and len(t) > len(suf) + 2:
            return t[: -len(suf)]
    return t


def diff_kind(extra: list[str], where: str) -> str:
    """Class of the token difference between a predicted and a gold span (`extra` = tokens only one side has)."""
    low = [t.lower() for t in extra]
    if not low:
        return "inflection_only"
    if all(not re.search(r"[a-z0-9]", t) for t in low):
        return "punctuation"
    if "(" in low or ")" in low or "[" in low:
        return "parenthetical_or_acronym"
    if low[0] in DET or all(t in DET for t in low):
        return "determiner"
    if any(t in COORD for t in low):
        return "coordination"
    if low[0] in PREP or any(t in PREP for t in low):
        return "prepositional_tail"
    if all(re.fullmatch(r"[0-9.,%-]+", t) for t in low):
        return "number"
    return f"modifier_{where}"


def endpoint_rows(doc, g, pred) -> list[dict]:
    spans = {}
    for n in pred["nodes"]:
        for s in n.mentions:
            spans.setdefault(s, n)
    names = {}
    for n in pred["nodes"]:
        for f in {n.name, *getattr(n, "aliases", [])}:
            if f:
                names.setdefault(r1(f), n)
    gtype = {m.span: m.type for m in g.mentions}
    tok = doc.tokens
    out = []
    for sp in sorted({s for r in g.relations for s in (r.src_span, r.tgt_span)}):
        if sp in spans:
            continue
        text = " ".join(tok[sp[0] : sp[1]])
        over = [(a, spans[a]) for a in spans if a[0] < sp[1] and sp[0] < a[1]]
        row = {"span": sp, "text": text, "gold_type": gtype.get(sp), "tokens": sp[1] - sp[0]}
        if not over:
            node = names.get(r1(text))
            row |= {
                "status": "absent",
                "absent_kind": "node_has_surface" if node else "no_node",
                "node": node.name if node else None,
            }
        else:
            a, n = max(over, key=lambda x: min(x[0][1], sp[1]) - max(x[0][0], sp[0]))
            g_t, p_t = tok[sp[0] : sp[1]], tok[a[0] : a[1]]
            if len(over) > 1 and all(sp[0] <= o[0][0] and o[0][1] <= sp[1] for o in over):
                shape, extra = "split", []
            elif a[0] <= sp[0] and sp[1] <= a[1]:
                shape, extra = "pred_longer", tok[a[0] : sp[0]] + tok[sp[1] : a[1]]
            elif sp[0] <= a[0] and a[1] <= sp[1]:
                shape, extra = "pred_shorter", tok[sp[0] : a[0]] + tok[a[1] : sp[1]]
            else:
                shape, extra = (
                    "crossing",
                    tok[min(a[0], sp[0]) : max(a[0], sp[0])]
                    + tok[min(a[1], sp[1]) : max(a[1], sp[1])],
                )
            same_words = [stem(t) for t in g_t] == [stem(t) for t in p_t]
            row |= {"status": "partial", "shape": shape, "pred_text": " ".join(p_t), "pred_type": n.type, "node": n.name,
                    "kind": "inflection_only" if same_words else ("split" if shape == "split" else diff_kind(extra, "extra" if shape == "pred_longer" else "missing")),
                    "extra_tokens": extra, "type_agrees": (n.type or "").lower() == (row["gold_type"] or "").lower()}  # fmt: skip
        out.append(row)
    return out


def analyse(tag: str) -> dict:
    ad = SciNLPAdapter()
    sym = ad.symmetric_relations()
    papers = first_set()
    gold = {s: ad.gold(s) for s in {s for s, _ in papers}}
    docs = {
        s: {d.doc_key: d for d in ad.load_documents(s, paragraph_every=SR.PARAGRAPH_EVERY)}
        for s in gold
    }
    rows, codes = [], Counter()
    for s, d in papers:
        f = PG.run_path(run_id(d, tag)) / "checkpoint.json"
        if not f.exists():
            continue
        cp = json.loads(f.read_text())
        doc, g = docs[s][d], gold[s][d]
        r = V.sc_score(doc, g, cp, sym, VARIANT)
        cs = sc_attribution(doc, g, r["pred"], cp, sym)
        codes.update(c or "recovered" for c in cs)
        lost = {
            sp
            for rel, c in zip(g.relations, cs, strict=True)
            if c in ("N0", "N1")
            for sp in (rel.src_span, rel.tgt_span)
        }
        n_rel = Counter(
            sp
            for rel, c in zip(g.relations, cs, strict=True)
            if c in ("N0", "N1")
            for sp in (rel.src_span, rel.tgt_span)
        )
        for row in endpoint_rows(doc, g, r["pred"]):
            if row["span"] in lost:
                rows.append({"paper": d, "split": s, "relations_lost": n_rel[row["span"]], **row})
    part = [x for x in rows if x["status"] == "partial"]
    absn = [x for x in rows if x["status"] == "absent"]
    w = lambda xs, k: dict(Counter(x[k] for x in xs).most_common())
    wr = lambda xs, k: dict(
        Counter(
            {v: sum(x["relations_lost"] for x in xs if x[k] == v) for v in {x[k] for x in xs}}
        ).most_common()
    )
    return {
        "tag": tag, "variant": VARIANT, "codes": dict(codes), "endpoints": len(rows),
        "partial": {"endpoints": len(part), "shape": w(part, "shape"), "kind": w(part, "kind"), "kind_weighted_by_relations": wr(part, "kind"),
                    "type_agrees": w(part, "type_agrees"), "by_split": w(part, "split")},
        "absent": {"endpoints": len(absn), "absent_kind": w(absn, "absent_kind"), "gold_type": w(absn, "gold_type"),
                   "kind_weighted_by_relations": wr(absn, "absent_kind"), "tokens": w(absn, "tokens"), "by_split": w(absn, "split")},
        "rows": rows,
    }  # fmt: skip


def markdown(r: dict) -> str:
    p, a = r["partial"], r["absent"]

    def tbl(d: dict, head: str) -> list[str]:
        tot = sum(d.values()) or 1
        return [
            f"| {head} | count | share |",
            "|---|---|---|",
            *[f"| {k} | {v} | {v / tot:.0%} |" for k, v in d.items()],
            "",
        ]

    ex = lambda k: [x for x in r["rows"] if x.get("kind") == k][:4]
    L = [
        "# CR-052: why concept endpoints are missed (N0 / N1) in the CR-043 baseline",
        "",
        (f"Generated by `cumap.cr052.spans` ($0, read-only). Run tag `{r['tag']}` (20 papers: 6 dev + 14 train), grounding `{r['variant']}`. "
         f"Unit: a distinct gold endpoint mention of a relation lost at N0 / N1 (one endpoint can block several relations). Earliest-failure codes: {r['codes']}."),
        "",
        f"## N1: a predicted mention overlaps but the span differs ({p['endpoints']} endpoints)",
        "",
        *tbl(p["shape"], "shape (predicted vs gold)"),
        *tbl(p["kind"], "token difference"),
        "Weighted by relations lost: " + json.dumps(p["kind_weighted_by_relations"]),
        "",
        f"Predicted node type agrees with the gold type: {p['type_agrees']}.",
        "",
        "Examples (gold -> predicted):",
        *[f"- {k}: " + "; ".join(f"'{x['text']}' -> '{x['pred_text']}'" for x in ex(k)) for k in p["kind"]],
        "",
        f"## N0: no predicted mention overlaps ({a['endpoints']} endpoints)",
        "",
        *tbl(a["absent_kind"], "kind"),
        *tbl(a["gold_type"], "gold type"),
        *tbl(a["tokens"], "gold span length (tokens)"),
        "Examples, no node: " + "; ".join(f"'{x['text']}' ({x['gold_type']})" for x in [x for x in r["rows"] if x.get("absent_kind") == "no_node"][:12]),
        "",
        "Examples, a node has the surface: " + "; ".join(f"'{x['text']}' (node '{x['node']}')" for x in [x for x in r["rows"] if x.get("absent_kind") == "node_has_surface"][:8]),
        "",
    ]  # fmt: skip
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=TAG)
    a = ap.parse_args()
    r = analyse(a.tag)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "span_analysis.json").write_text(
        json.dumps({k: v for k, v in r.items() if k != "rows"}, indent=1, default=str),
        encoding="utf-8",
    )
    (OUT / "span_analysis.md").write_text(markdown(r), encoding="utf-8")
    print(json.dumps({k: v for k, v in r.items() if k not in ("rows",)}, indent=1, default=str))


if __name__ == "__main__":
    main()
