"""CR-062 $0 sizing of domain-free verifier rules on the 57 SciNLP train / dev papers (profile v11: the v5 runs with span identity A-name
applied in memory). No model call, no training: spaCy `en_core_web_sm` and string rules only; gold is read only to evaluate (rule 9).

(b) recall rules for items the verifier dropped on F2 / F3 (an approximate replay: the corrective-round interplay is not replayed):
  V1 re-anchor: the name occurs verbatim (case-insensitive) in the paper; the new quote is the sentence of the occurrence nearest the
     original quote (exact substring, rule 3); `para` = only inside the original quote's paragraph, `paper` = anywhere;
  V2 F3 tolerance: the name's R1 key equals the R1 key of a word window of the quote.
(c) flag rules on the final concepts:
  V6 sentence role: every evidence quote of the node is a citation / example-list context;
  V7 grammatical role: in every paper sentence containing the name, its head token is only a modifier.

    uv run python -m cumap.cr062.measure"""

from __future__ import annotations

import bisect
import json
import re
from collections import Counter

import spacy

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr019 import variants as V
from cumap.cr043.eval import PRIMARY, pool, prf_d
from cumap.cr043.papers import paper_set
from cumap.cr043.run import run_id
from cumap.cr058.funnel import gold_surface_keys
from cumap.cr058.graphs import key
from cumap.cr060 import span_identity as SI
from cumap.expert_kg.alias_rules import AliasConfig, r1_key

OUT = REPO_ROOT / "reports/cr062"
SETS = (("first", "cr055ballp"), ("rest", "cr057rest"))
VARIANT = "A-name"  # profile v11
_CFG = AliasConfig.load()
CITATION = re.compile(
    r"\(\s*[^()]{0,80}(?:19|20)\d\d[a-z]?\s*\)|\bet al\b|\[\s*\d+(?:\s*[,-]\s*\d+)*\s*\]"
)
EXAMPLE = re.compile(
    r"\b(?:e\s*\.\s*g\s*\.|such as|for example|for instance|i\s*\.\s*e\s*\.)", re.IGNORECASE
)
MODIFIER_DEPS = {"compound", "amod", "nmod", "poss", "appos"}


def _norm(s: str) -> str:
    return " ".join((s or "").split())


def occurrences(name: str, text: str) -> list[tuple[int, int]]:
    toks = [re.escape(t) for t in name.split()]
    if not toks:
        return []
    pat = r"(?<![\w-])" + r"\s+".join(toks) + r"(?![\w-])"
    return [(m.start(), m.end()) for m in re.finditer(pat, text, flags=re.IGNORECASE)]


def quote_pos(quote: str, text: str) -> int | None:
    q = _norm(quote)
    if not q:
        return None
    i = _norm(text).find(q)
    if i < 0:
        return None
    # map the normalised offset back to the raw text (whitespace runs collapse to one space)
    raw, n = 0, 0
    while raw < len(text) and n < i:
        if text[raw].isspace():
            while raw + 1 < len(text) and text[raw + 1].isspace():
                raw += 1
        raw += 1
        n += 1
    return raw


def v2_tolerant(name: str, quote: str) -> bool:
    k, w = r1_key(name, _CFG), quote.split()
    n = len(name.split())
    return bool(k) and any(r1_key(" ".join(w[i : i + j]), _CFG) == k for j in (n - 1, n, n + 1) if j > 0
                           for i in range(len(w) - j + 1))  # fmt: skip


def rescue(
    item: dict, text: str, sents: list[tuple[int, int]], paras: list[int], mode: str
) -> str | None:
    """The re-anchored quote (a sentence of the paper) or None."""
    name = item.get("name") or item.get("surface") or ""
    occ = occurrences(name, text)
    if not occ:
        return None
    qp = quote_pos(item.get("evidence") or "", text)
    if mode == "para":
        if qp is None:
            return None
        pi = bisect.bisect_right(paras, qp) - 1
        lo, hi = paras[pi], paras[pi + 1] if pi + 1 < len(paras) else len(text)
        occ = [o for o in occ if lo <= o[0] < hi]
        if not occ:
            return None
    a = min(occ, key=lambda o: abs(o[0] - (qp if qp is not None else 0)))[0]
    starts = [s for s, _ in sents]
    si = max(bisect.bisect_right(starts, a) - 1, 0)
    q = text[sents[si][0] : sents[si][1]]
    return q if q in text else None


def part_b(papers, docs, golds, sym) -> dict:
    arms = ("control", "V2", "V1-para + V2", "V1-paper + V2")
    acc = {a: [] for a in arms}
    counts = {a: Counter() for a in arms}
    for set_name, tag, s, d in papers:
        doc, g = docs[d], golds[d]
        rid = run_id(d, tag)
        cp0 = json.loads((PG.run_path(rid) / "checkpoint.json").read_text())
        cp0, _ = SI.apply(cp0, doc.text, SI.load_variant(VARIANT), symmetric=frozenset(sym))
        v4p = PG.run_path(rid) / "v4_concepts.json"
        v4 = json.loads(v4p.read_text()) if v4p.exists() else {"sections": {}}
        gk = gold_surface_keys(doc, g)
        final = {
            key(f)
            for c in cp0["concepts"]
            for f in [c["canonical_name"], *(c.get("aliases") or [])]
        }
        text = doc.text
        sents = V.sc_sentences(doc)
        paras = [0] + [m.end() for m in re.finditer(r"\n\s*\n", text)]
        dropped = [r for sec in v4["sections"].values() for r in sec.get("rejected") or []
                   if set(r.get("rules") or []) <= {"F2", "F3"} and r.get("rules")]  # fmt: skip
        for a in arms:
            cp = json.loads(json.dumps(cp0))
            seen = set(final)
            for r in dropped if a != "control" else []:
                it = r.get("item") or {}
                name = it.get("name") or it.get("surface") or ""
                k = key(name)
                if not name or k in seen:
                    counts[a]["already_in_graph"] += 1
                    continue
                q = None
                if (
                    "F3" in r["rules"]
                    and "F2" not in r["rules"]
                    and v2_tolerant(name, it.get("evidence") or "")
                ):
                    q = _norm(it.get("evidence"))
                    q = q if q in _norm(text) else None
                if q is None and a.startswith("V1"):
                    q = rescue(it, text, sents, paras, "para" if "para" in a else "paper")
                if q is None:
                    counts[a]["still_dropped"] += 1
                    continue
                if q not in text:  # the stored quote must be an exact substring (rule 3)
                    hit = occurrences(name, text)
                    if not hit:
                        counts[a]["still_dropped"] += 1
                        continue
                    starts = [x for x, _ in sents]
                    si = max(bisect.bisect_right(starts, hit[0][0]) - 1, 0)
                    q = text[sents[si][0] : sents[si][1]]
                seen.add(k)
                counts[a]["rescued_gold" if k in gk else "rescued_non_gold"] += 1
                cp["concepts"].append({"concept_id": f"cr062_{len(cp['concepts'])}", "canonical_name": name, "aliases": [],
                                       "node_type": "Concept", "mentions": [{"section_id": d, "quote": q, "surface": name}]})  # fmt: skip
            acc[a].append(V.sc_score(doc, g, cp, set(sym), PRIMARY)["scores"]["entity_strict"])
    out = {}
    for a in arms:
        out[a] = {"concept": prf_d(pool(acc[a])), "counts": dict(counts[a])}
    c0 = out["control"]["concept"]
    for a in arms[1:]:
        out[a]["recall_delta"] = round(out[a]["concept"]["recall"] - c0["recall"], 4)
        out[a]["f2_delta"] = round(out[a]["concept"]["f2"] - c0["f2"], 4)
    return out


def head_is_modifier_only(name: str, text: str, nlp, sents: list[tuple[int, int]]) -> bool | None:
    """True when every occurrence's head token is a modifier; None when the name never occurs."""
    occ = occurrences(name, text)
    if not occ:
        return None
    starts = [s for s, _ in sents]
    seen_roles = []
    for a, b in occ[:8]:
        si = max(bisect.bisect_right(starts, a) - 1, 0)
        s0, s1 = sents[si]
        sp = nlp(text[s0:s1])
        span = sp.char_span(a - s0, b - s0, alignment_mode="expand")
        if span is None:
            continue
        seen_roles.append(span.root.dep_)
    return bool(seen_roles) and all(r in MODIFIER_DEPS for r in seen_roles)


def part_c(papers, docs, golds, sym, nlp) -> dict:
    res = {r: Counter() for r in ("V6", "V7", "V6 or V7")}
    examples: dict[str, list] = {r: [] for r in res}
    total = Counter()
    for set_name, tag, s, d in papers:
        doc, g = docs[d], golds[d]
        cp = json.loads((PG.run_path(run_id(d, tag)) / "checkpoint.json").read_text())
        cp, _ = SI.apply(cp, doc.text, SI.load_variant(VARIANT), symmetric=frozenset(sym))
        gk = gold_surface_keys(doc, g)
        gm = Counter(key(" ".join(doc.tokens[m.span[0] : m.span[1]])) for m in g.mentions)
        sents = V.sc_sentences(doc)
        for c in cp["concepts"]:
            forms = {key(f) for f in [c["canonical_name"], *(c.get("aliases") or [])]}
            is_gold = bool(forms & gk)
            total["gold" if is_gold else "non_gold"] += 1
            quotes = [m.get("quote") or "" for m in c.get("mentions") or []]
            v6 = bool(quotes) and all(CITATION.search(q) or EXAMPLE.search(q) for q in quotes)
            v7 = head_is_modifier_only(c["canonical_name"], doc.text, nlp, sents) is True
            for rule, hit in (("V6", v6), ("V7", v7), ("V6 or V7", v6 or v7)):
                if hit:
                    res[rule]["gold" if is_gold else "non_gold"] += 1
                    res[rule]["gold_mentions_at_risk"] += sum(gm[f] for f in forms)
                    if len(examples[rule]) < 30:
                        examples[rule].append(
                            f"{c['canonical_name']}{' [GOLD]' if is_gold else ''}"
                        )
    out = {"nodes": dict(total)}
    for rule, x in res.items():
        out[rule] = {**dict(x), "non_gold_per_gold": round(x["non_gold"] / x["gold"], 2) if x["gold"] else None,
                     "examples": examples[rule]}  # fmt: skip
    return out


def markdown(r: dict) -> str:
    L = ["# CR-062 $0 sizing: domain-free verifier rules (57 SciNLP train / dev papers, profile v11, `IDXR1-P1`)", "",
         "Gold only evaluates; no rule is trained (owner constraint). Part (b) is an approximate replay (corrective round not replayed).", "",
         "## (b) Rescuing items the verifier dropped on F2 / F3", "",
         "| arm | rescued gold | rescued non-gold | concept P / R / F2 (F1) | recall Δ | F2 Δ |", "|---|---|---|---|---|---|"]  # fmt: skip
    for a, x in r["b"].items():
        c, n = x["concept"], x["counts"]
        L.append(f"| {a} | {n.get('rescued_gold', 0)} | {n.get('rescued_non_gold', 0)} | {c['precision']:.3f} / {c['recall']:.3f} / "
                 f"**{c['f2']:.3f}** ({c['f1']:.3f}) | {x.get('recall_delta', 0):+.4f} | {x.get('f2_delta', 0):+.4f} |")  # fmt: skip
    L += ["", "## (c) Flag rules on the final concepts", "", f"Nodes: {r['c']['nodes']}.", "",
          "| rule | non-gold flagged | gold flagged | non-gold per gold | gold mentions at risk |", "|---|---|---|---|---|"]  # fmt: skip
    for rule in ("V6", "V7", "V6 or V7"):
        x = r["c"][rule]
        L.append(
            f"| {rule} | {x.get('non_gold', 0)} | {x.get('gold', 0)} | {x.get('non_gold_per_gold')} | {x.get('gold_mentions_at_risk', 0)} |"
        )
    L += [
        "",
        f"**Paid arm (pre-registered trigger: (b) recall >= +0.005 or (c) >= 3 non-gold per gold): {r['trigger']}**",
    ]
    return "\n".join(L) + "\n"


def main() -> None:
    ad = SciNLPAdapter()
    sym = ad.symmetric_relations()
    docs, golds = {}, {}
    for s in ("train", "dev"):
        docs.update(
            {x.doc_key: x for x in ad.load_documents(s, paragraph_every=SR.PARAGRAPH_EVERY)}
        )
        golds.update(ad.gold(s))
    papers = [(sn, tag, s, d) for sn, tag in SETS for s, d in paper_set(sn)]
    nlp = spacy.load("en_core_web_sm", disable=["ner", "lemmatizer"])
    r = {"b": part_b(papers, docs, golds, sym), "c": part_c(papers, docs, golds, sym, nlp)}
    best_b = max(x.get("recall_delta", 0) for x in r["b"].values())
    best_c = max((r["c"][k].get("non_gold_per_gold") or 0) for k in ("V6", "V7", "V6 or V7"))
    r["trigger"] = bool(best_b >= 0.005 or best_c >= 3)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sizing.json").write_text(json.dumps(r, indent=1), encoding="utf-8")
    (OUT / "sizing.md").write_text(markdown(r), encoding="utf-8")
    print(markdown(r))
    for rule in ("V6", "V7"):
        print(rule, "examples:", r["c"][rule]["examples"][:20])


if __name__ == "__main__":
    main()
