"""CR-016 STOP 2B ($0, no model call): consumer-impact audit of memory-assisted candidate retrieval for the FROZEN canonicalisation.

A. Funnel: what canonicalisation actually does in the production graph (slice3_c2): how many decisions could be 'same'-type at all.
B. Candidate-generator comparison on the 1,140 benchmark cases, using the retrieval records already collected (no new retrieval): frozen embedding top-5 over the registry vs nodes mapped
   from M1 / M2 top-5 paragraphs vs their union, with the frozen gate (best candidate similarity >= 0.6) and review band (matched similarity >= 0.70) applied unchanged.
C. Identity hazard of injected candidates: non-target nodes injected, their similarity, lexicon DIFFERENT conflicts.
Registry proxy: gold concepts (canonical name) first annotated in an earlier section; retrieved paragraph -> nodes = gold concepts with a gold mention in that paragraph (only annotated sections can contribute nodes)."""

from __future__ import annotations

import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from cumap.cr016 import benchmark as B

ROOT = Path(".")
THR, BAND, K5 = 0.6, 0.70, 5


def funnel() -> dict:
    cp = json.loads((ROOT / "data/processed/kg/slice3_c2/checkpoint.json").read_text())
    v4 = json.loads((ROOT / "data/processed/kg/slice3_c2/v4_concepts.json").read_text())
    calls = Counter()
    for line in (ROOT / "data/logs/llm_calls.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["run_id"] == "slice3_c2" and r["task"] == "canonicalize":
            calls["calls"] += 1
            calls["cache_hits"] += bool(r["cache_hit"])
    merges = [m for m in cp["merges"] if m.get("stage") == "canonicalize_v4"]
    by = Counter((m.get("rule_id") or "llm", bool(m.get("llm_called"))) for m in merges)
    n_nodes, n_conc = len(v4["nodes"]), len(cp["concepts"])
    llm_same = sum(1 for m in merges if m.get("llm_called"))
    review, tax = len(cp["merge_review"]), len(cp["taxonomy_candidates"])
    return {"v4_nodes_entering_canonicalisation": n_nodes, "final_concepts": n_conc, "collapsed_by_canonicalisation": n_nodes - n_conc, "merges_by_path": {f"{k[0]}{'+llm' if k[1] else ''}": v for k, v in by.items()},
            "generator_g_links_before_canonicalisation": sum(1 for m in cp["merges"] if m.get("stage") == "generator"), "canonicalise_llm_calls_in_log": calls["calls"], "llm_same_merges": llm_same,
            "llm_same_but_routed_to_review_band": review, "llm_narrower_or_broader_taxonomy_candidates": tax, "implied_llm_different": calls["calls"] - llm_same - review - tax}  # fmt: skip


def main() -> dict:
    from cumap.concepts_v4 import experiments as X
    from cumap.config import get_settings
    from cumap.expert_kg.alias_rules import AliasConfig, r1_key
    from cumap.expert_kg.lexicon import Lexicon

    emb = X.Embedder(get_settings().embeddings.model)
    cfg = AliasConfig.load()
    lex = Lexicon.load(ROOT / "configs/term_lexicon.yaml")
    chunks, order = B.load_corpus()
    by_sec: dict[str, list[dict]] = defaultdict(list)
    for c in chunks:
        by_sec[c["section_id"]].append(c)
    gold = B.load_gold()
    first: dict[str, int] = {}
    canon: dict[str, str] = {}
    nodes_by_para: dict[str, set[str]] = defaultdict(set)
    for g in gold:
        o = order[g["section"]]
        first[g["key"]] = min(first.get(g["key"], 10**9), o)
        canon.setdefault(g["key"], B.norm(g["canonical"]))
        pid = B._para_of(by_sec, g["section"], g["sentence"])
        if pid:
            nodes_by_para[pid].add(g["key"])
    keys = sorted(first)
    kidx = {k: i for i, k in enumerate(keys)}
    mat = np.stack([emb(canon[k]) / (np.linalg.norm(emb(canon[k])) + 1e-9) for k in keys])
    first_arr = np.array([first[k] for k in keys])
    key_rows = [
        json.loads(x) for x in gzip.open(ROOT / "reports/cr016/records/answer_key.jsonl.gz", "rt")
    ]
    qrows = {
        q["query_id"]: q
        for q in (
            json.loads(x) for x in gzip.open(ROOT / "reports/cr016/records/queries.jsonl.gz", "rt")
        )
    }
    recs: dict[str, dict[str, list[str]]] = defaultdict(dict)
    for line in gzip.open(ROOT / "reports/cr016/records/retrieval_records.jsonl.gz", "rt"):
        r = json.loads(line)
        recs[r["backend"]][r["query_id"]] = [x["chunk_id"] for x in r["retrieved"][:5]]
    sl_names = [
        "all",
        "alias",
        "acronym",
        "associative_low_lexical_overlap",
        "one_token",
        "different_boundary",
        "long_gap",
        "same_surface_different_sense",
    ]
    acc: dict[str, Counter] = defaultdict(Counter)
    for kr in key_rows:
        K, n = kr["key"], kr["source_order"]
        if first.get(K, 10**9) >= n:
            continue  # the target concept has no registered node yet
        s = B.norm(kr["surface"])
        q = emb(s)
        q = q / (np.linalg.norm(q) + 1e-9)
        sims = np.where(first_arr < n, mat @ q, -1.0)
        t = kidx[K]
        if (
            s == canon[K]
            or r1_key(s, cfg) == r1_key(canon[K], cfg)
            or (B.is_acronym(kr["surface"]) and B.initials_match(kr["surface"], canon[K]))
        ):
            kind = "handled_by_exact_or_R1_R2_rules"
        else:
            kind = "residual_needs_embedding_and_LLM"
        e5 = list(np.argsort(-sims)[:K5])
        sets = {"embedding_top5": e5}
        for name, b in (("M1", "M1_dense"), ("M2", "M2_hipporag")):
            cand: list[int] = []
            for pid in recs[b][kr["query_id"]]:
                cand += [
                    kidx[k]
                    for k in nodes_by_para.get(pid, ())
                    if first[k] < n and kidx[k] not in cand
                ]
            cand.sort(key=lambda i: -sims[i])
            sets[name + "_nodes"] = cand[:K5]
            sets[name + "_union_embedding"] = list(dict.fromkeys(e5 + cand[:K5]))
        for sl in sl_names:
            if sl != "all" and not kr["flags"].get(sl):
                continue
            for scope in ("all_cases", kind):
                a = acc[f"{sl}|{scope}"]
                a["cases"] += 1
                for name, cs in sets.items():
                    inn = t in cs
                    a[f"{name}:target_in_set"] += inn
                    best = max((sims[i] for i in cs), default=-1)
                    a[f"{name}:actionable_frozen"] += bool(inn and best >= THR and sims[t] >= BAND)
                    if name != "embedding_top5":
                        a[f"{name}:non_target_injected"] += len(
                            [i for i in cs if i != t and i not in e5]
                        )
                        a[f"{name}:non_target_injected_ge_band"] += len(
                            [i for i in cs if i != t and i not in e5 and sims[i] >= BAND]
                        )
                        a[f"{name}:non_target_lexicon_different"] += sum(
                            1
                            for i in cs
                            if i != t and i not in e5 and lex.is_different(s, canon[keys[i]])
                        )
                for m in ("M1_union_embedding", "M2_union_embedding", "M1_nodes", "M2_nodes"):
                    base_set = set(sets["embedding_top5"])
                    gain_target = t in sets[m] and t not in base_set
                    a[f"{m}:memory_adds_target_vs_embedding"] += gain_target
                    a[f"{m}:memory_adds_target_and_actionable_frozen"] += bool(
                        gain_target
                        and sims[t] >= BAND
                        and max((sims[i] for i in sets[m]), default=-1) >= THR
                    )
                    a[f"{m}:memory_adds_target_but_below_band"] += bool(
                        gain_target and sims[t] < BAND
                    )
                a["target_sim_ge_0.6"] += bool(sims[t] >= THR)
                a["target_sim_ge_0.7"] += bool(sims[t] >= BAND)
                a["target_registered"] += 1
    out = {
        "funnel": funnel(),
        "audit": {k: dict(v) for k, v in sorted(acc.items())},
        "registry_proxy": {
            "nodes_total": len(keys),
            "paragraphs_with_nodes": len(nodes_by_para),
            "corpus_paragraphs": len(chunks),
        },
    }
    Path("reports/cr016/consumer_impact_audit.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    o = main()
    print(json.dumps(o["funnel"], indent=1))
    print(o["registry_proxy"])
    for k in (
        "all|all_cases",
        "all|residual_needs_embedding_and_LLM",
        "all|handled_by_exact_or_R1_R2_rules",
        "associative_low_lexical_overlap|all_cases",
        "acronym|all_cases",
        "alias|all_cases",
    ):
        print(k, o["audit"].get(k))
