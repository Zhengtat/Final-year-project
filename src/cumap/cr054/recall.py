"""CR-054: where each missed gold concept mention is lost in the concept stage ($0, read-only, no model call).

For the run tag (default `cr053v5`, the adopted SciNLP settings) and the 20 CR-043 papers, every gold mention that no predicted mention matches
exactly (`IDXR1-P1` placement) is traced, earliest loss first:
- `span`: a predicted mention overlaps it (the concept was found; only the span differs; CR-052 classes);
- `node_not_placed`: a final node has this surface as a name or alias, but this occurrence was not placed;
- `lost_after_generator`: the generator proposed the surface in some iteration, but no final node has it (verifier drop with its rule,
  a later iteration leaving it out, identity / adjudicator merge, or pruning);
- `hint_rejected`: the verifier's coverage hint offered it and the generator rejected it (with its reason);
- `never_proposed`: the surface appears in no generator output and no hint.
Surfaces are compared by the R1 key (lower case, letters and digits only) with plural folding.

    uv run python -m cumap.cr054.recall [--tag cr053v5]        # reports/cr054/concept_recall.{json,md}
Train / dev papers only (rule 9)."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr019 import variants as V
from cumap.cr043.papers import first_set
from cumap.cr043.run import run_id

OUT = REPO_ROOT / "reports" / "cr054"
GENERIC = {"parsing", "corpus", "data", "grammar", "rules", "rule", "templates", "template", "prompts", "prompt", "model", "models",
           "neural network", "features", "translation", "training"}  # the v5_scinlp "not on their own" list  # fmt: skip


def key(s: str) -> str:
    toks = [t.lower() for t in re.findall(r"[A-Za-z0-9]+", s or "")]
    toks = [t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t for t in toks]
    return "".join(toks)


def _forms(item: dict) -> set[str]:
    return {
        key(x) for x in [item.get("name"), item.get("surface"), *(item.get("aliases") or [])] if x
    }


def run_trace(rid: str) -> dict:
    """Every surface the generator proposed (any iteration), what the verifier dropped (with rules), hints the generator rejected (with reasons)."""
    v = json.loads((PG.run_path(rid) / "v4_concepts.json").read_text())
    proposed, dropped, hints = set(), defaultdict(set), {}
    for s in v["sections"].values():
        for it in s.get("iterations") or []:
            out = it.get("output") or {}
            for k in ("new_concepts", "existing_mentions"):
                for x in out.get(k) or []:
                    proposed |= _forms(x)
        for r in s.get("rejected") or []:
            for f in _forms(r.get("item") or {}):
                dropped[f] |= set(r.get("rules") or [])
        for h in s.get("rejected_hints") or []:
            hints[key(h.get("text"))] = h.get("reason") or ""
    merged = defaultdict(set)
    for m in v.get("merges") or []:
        merged[key(m.get("surface"))].add(
            m.get("rule_id") + (f":{m['decision']}" if m.get("decision") else "")
        )
    gen_nodes = {
        f for n in v["nodes"].values() for f in {key(n["name"]), *map(key, n.get("aliases") or [])}
    }
    return {
        "proposed": proposed,
        "dropped": dropped,
        "hints": hints,
        "merged": merged,
        "gen_nodes": gen_nodes,
    }


def analyse(tag: str) -> dict:
    ad = SciNLPAdapter()
    papers = first_set()
    gold = {s: ad.gold(s) for s in {s for s, _ in papers}}
    docs = {
        s: {d.doc_key: d for d in ad.load_documents(s, paragraph_every=SR.PARAGRAPH_EVERY)}
        for s in gold
    }
    rows = []
    for s, d in papers:
        rid = run_id(d, tag)
        cp = json.loads((PG.run_path(rid) / "checkpoint.json").read_text())
        doc, g = docs[s][d], gold[s][d]
        pred = V.sc_predict_indexed(doc, cp, "r1key")
        spans = {m for n in pred["nodes"] for m in n.mentions}
        final = {
            f
            for c in cp["concepts"]
            for f in {key(c["canonical_name"]), *map(key, c.get("aliases") or [])}
        }
        tr = run_trace(rid)
        for m in g.mentions:
            if m.span in spans:
                continue
            text = " ".join(doc.tokens[m.span[0] : m.span[1]])
            k = key(text)
            over = [a for a in spans if a[0] < m.span[1] and m.span[0] < a[1]]
            row = {
                "paper": d,
                "split": s,
                "text": text,
                "gold_type": m.type,
                "tokens": m.span[1] - m.span[0],
            }
            if over:
                a = max(over, key=lambda x: min(x[1], m.span[1]) - max(x[0], m.span[0]))
                row |= {"stage": "span", "pred_text": " ".join(doc.tokens[a[0] : a[1]])}
            elif k in final:
                row |= {"stage": "node_not_placed"}
            elif k in tr["proposed"]:
                why = sorted(tr["dropped"].get(k, set())) or sorted(tr["merged"].get(k, set()))
                row |= {
                    "stage": "lost_after_generator",
                    "why": ",".join(why)
                    or (
                        "not_in_final_graph"
                        if k in tr["gen_nodes"]
                        else "dropped_in_later_iteration"
                    ),
                }
            elif k in tr["hints"]:
                row |= {"stage": "hint_rejected", "why": tr["hints"][k]}
            else:
                row |= {"stage": "never_proposed"}
            rows.append(row)
    return {"tag": tag, "missed": len(rows), "rows": rows}


def describe_never(rows: list[dict]) -> dict:
    nv = [x for x in rows if x["stage"] == "never_proposed"]
    acr = lambda t: (
        bool(re.fullmatch(r"[A-Za-z0-9\-\.]{1,10}", t)) and sum(c.isupper() for c in t) >= 2
    )

    def cls(x: dict) -> str:
        t = x["text"]
        if t.lower() in GENERIC:
            return "generic_word_excluded_by_v5"
        if acr(t) or re.fullmatch(r"[A-Z][A-Za-z]*-?[A-Z0-9]+.*", t):
            return "acronym_or_model_name"
        if re.search(r"\d", t):
            return "contains_number_or_version"
        if x["tokens"] == 1:
            return "single_common_word"
        if x["tokens"] >= 4:
            return "long_phrase"
        return "short_phrase"

    c = Counter(cls(x) for x in nv)
    ex = defaultdict(list)
    for x in nv:
        if len(ex[cls(x)]) < 12:
            ex[cls(x)].append(f"{x['text']} ({x['gold_type']})")
    return {"classes": dict(c.most_common()), "examples": dict(ex), "by_type": dict(Counter(x["gold_type"] for x in nv).most_common()),
            "top_surfaces": Counter(x["text"].lower() for x in nv).most_common(25)}  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="cr053v5")
    a = ap.parse_args()
    r = analyse(a.tag)
    rows = r["rows"]
    summ = {
        "tag": r["tag"], "missed": r["missed"],
        "stage": dict(Counter(x["stage"] for x in rows).most_common()),
        "stage_by_type": {t: dict(Counter(x["stage"] for x in rows if x["gold_type"] == t)) for t in ("method", "task", "dataset", "metric")},
        "lost_after_generator_why": dict(Counter(x.get("why") for x in rows if x["stage"] == "lost_after_generator").most_common()),
        "hint_rejected_reasons": [f"{x['text']}: {x['why'][:140]}" for x in rows if x["stage"] == "hint_rejected"][:15],
        "node_not_placed_examples": [x["text"] for x in rows if x["stage"] == "node_not_placed"][:20],
        "lost_examples": [f"{x['text']} ({x.get('why')})" for x in rows if x["stage"] == "lost_after_generator"][:20],
        "span_examples": [f"{x['text']} -> {x['pred_text']}" for x in rows if x["stage"] == "span"][:15],
        "never": describe_never(rows),
    }  # fmt: skip
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "concept_recall.json").write_text(
        json.dumps(summ, indent=1, default=str), encoding="utf-8"
    )
    print(json.dumps(summ, indent=1, default=str))


if __name__ == "__main__":
    main()
