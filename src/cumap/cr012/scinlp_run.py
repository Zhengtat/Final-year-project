"""CR-012 E0 for ONE SciNLP document through the unchanged production stages under the frozen benchmark-local profile
(`configs/cr012_scinlp_schema.yaml`: four literal entity types, eleven relations, zero-shot, empty lexicon, no overrides, pruner off, strict G-links).
Full documents, never abstracts or selected sentences. The pair budget is the approved D3 rule. Only train / dev documents may be run here until the
final freeze; the test split is refused by `run_doc`.

    uv run python -m cumap.cr012.scinlp_run run --split dev --doc P05-1008.grobid --dry-run
"""

from __future__ import annotations

import argparse
import json
import math
import os

import yaml

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scoring as S
from cumap.cr012.adapters import SciNLPAdapter, SciNLPDoc
from cumap.cr012.budget import pair_budget
from cumap.cr012.types import PredEdge, PredNode

PROFILE = REPO_ROOT / "configs/cr012_scinlp_schema.yaml"
UNITS = REPO_ROOT / "data/interim/cr012/scinlp_units"
PARAGRAPH_EVERY = 10  # sentences per paragraph (SciNLP has no paragraph structure)
ALLOWED_SPLITS = {
    "train",
    "dev",
}  # the test split is opened only by the authorised STOP-4 execution (CUMAP_CR012_STOP4=1)


def split_allowed(split: str) -> bool:
    return split in ALLOWED_SPLITS or (
        split == "test" and os.environ.get("CUMAP_CR012_STOP4") == "1"
    )


def prepare(split: str, doc: SciNLPDoc) -> dict:
    assert split_allowed(split), (
        "the SciNLP test split may not be run through a model before the final freeze and Research approval"
    )
    d = UNITS / split / doc.doc_key
    d.mkdir(parents=True, exist_ok=True)
    row = {
        "section_id": doc.doc_key,
        "chapter_num": 1,
        "chapter_title": doc.doc_key,
        "section_title": doc.doc_key,
        "heading_path": [doc.doc_key],
        "order_index": 0,
        "text": doc.text,
        "emphasized_terms": [],
        "word_count": len(doc.text.split()),
    }
    src = d / "sections.jsonl"
    src.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    base = yaml.safe_load((REPO_ROOT / "configs/demo_slice.yaml").read_text())
    base["pd"]["source_jsonl"] = str(src.relative_to(REPO_ROOT))
    base["pd"]["chapters"] = [1]
    cfg = d / "slice.yaml"
    cfg.write_text(yaml.safe_dump(base, sort_keys=False), encoding="utf-8")
    return {"slice_config": str(cfg), "words": len(doc.text.split()), "tokens": len(doc.tokens)}


def run_doc(split: str, doc_key: str, tag: str, *, dry_run: bool, max_usd: float) -> dict:
    from cumap.concepts_v4 import cr009_run as R

    ad = SciNLPAdapter()
    docs = {d.doc_key: d for d in ad.load_documents(split, paragraph_every=PARAGRAPH_EVERY)}
    doc = docs[doc_key]
    info = prepare(split, doc)
    prof = yaml.safe_load(PROFILE.read_text())
    os.environ.update(
        {
            "CUMAP_DEMO_SLICE": info["slice_config"],
            "CUMAP_BENCHMARK_PROFILE": str(PROFILE),
            "CUMAP_RELATION_REGISTRY": prof["relation_registry"],
        }
    )
    from cumap.config import get_settings

    get_settings.cache_clear()
    run_id = f"cr012_scinlp_{tag}_{doc_key.replace('.', '_').replace('-', '_')}_E0"
    out = {"run_id": run_id, "split": split, "doc": doc_key, **info}
    out["concepts"] = R.stage_concepts(
        run_id,
        dry_run=dry_run,
        limit_units=None,
        max_usd=max_usd,
        tau=float(prof["pruner"]["tau"]),
        strict_g_links=bool(prof["strict_g_links"]),
    )
    if dry_run:
        out["pair_budget_if_pool_unbounded"] = math.ceil(14.2 * info["words"] / 1000)
        return out
    from cumap.cr012.unit_run import select_without_sample

    budget = math.ceil(14.2 * info["words"] / 1000)
    sel = select_without_sample(run_id, budget)
    pool = sel.get("unique_candidate_pairs", 0)
    b = pair_budget(info["words"], pool)
    if b != budget:
        sel = select_without_sample(run_id, b)
    out["budget_record"] = {
        "word_count": info["words"],
        "eligible_candidate_pairs": pool,
        "budget": b,
        "selected_pairs": sel.get("selected"),
        "budget_saturated": (sel.get("selected") or 0) >= b,
    }
    out["relations"] = R.stage_relations(run_id, dry_run=False, max_usd=max_usd)
    return out


# ---------------------------------------------------------------- run -> token-level prediction -> score
def char_to_token(doc: SciNLPDoc, start: int, end: int) -> tuple[int, int] | None:
    """Token span covering [start, end) when both ends fall inside tokens; None when the range touches whitespace only."""
    ts = [i for i, (a, b) in enumerate(doc.token_offsets) if a <= start < b]
    te = [i for i, (a, b) in enumerate(doc.token_offsets) if a < end <= b]
    if not ts or not te or te[0] < ts[0]:
        return None
    return ts[0], te[0] + 1


def predict(doc: SciNLPDoc, cp: dict) -> dict:
    by_id = {c["concept_id"]: c for c in cp["concepts"]}
    spans, _gstats = PG.grounded_spans(
        cp["concepts"], doc.text, doc.doc_key
    )  # evidence-grounded (rule 24)
    found: dict[str, set[tuple[int, int]]] = {}
    off_boundary = 0
    for cid, chars in spans.items():
        for a, b in chars:
            span = doc.chars_to_span(a, b)  # exact token boundaries only (strict)
            if span is None:
                off_boundary += 1
                continue
            found.setdefault(cid, set()).add(span)
    nodes = [
        PredNode(
            cid,
            doc.doc_key,
            by_id[cid]["node_type"],
            by_id[cid]["canonical_name"],
            tuple(sorted(sp)),
        )
        for cid, sp in sorted(found.items())
    ]
    ids = {n.node_id for n in nodes}
    edges, negated, ungrounded = [], 0, 0
    for r in cp["relation_results_v3"]:
        if (
            r["outcome"] != "edge"
            or r.get("group", "selected") != "selected"
            or r.get("gated_dropped")
            or r.get("consolidated_into")
        ):
            continue
        if (r.get("qualifiers") or {}).get("polarity") == "negated":
            negated += 1  # a negated benchmark relation is never a positive edge
            continue
        x, y = r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]
        src, tgt = (y, x) if r["direction"] == "reversed" else (x, y)
        q = r.get("evidence_quote") or ""
        i = doc.text.find(q) if q else -1
        ev = char_to_token(doc, i, i + len(q)) if i >= 0 else None
        if src not in ids or tgt not in ids or ev is None:
            ungrounded += 1
            continue
        edges.append(PredEdge(doc.doc_key, src, tgt, r["relation"], ev))
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "negated_dropped": negated,
            "ungrounded_dropped": ungrounded,
            "mentions_off_token_boundary": off_boundary,
        },
    }


def score_doc(split: str, doc_key: str, run_id: str) -> dict:
    ad = SciNLPAdapter()
    doc = next(
        d for d in ad.load_documents(split, paragraph_every=PARAGRAPH_EVERY) if d.doc_key == doc_key
    )
    gold = ad.gold(split)[doc_key]
    cp = json.loads((REPO_ROOT / "data/processed/kg" / run_id / "checkpoint.json").read_text())
    pred = predict(doc, cp)
    rels, _ung = S.project_edges_to_mentions(pred["nodes"], pred["edges"])
    res = S.score_scinlp_unit(
        gold, S.project_nodes_to_mentions(pred["nodes"]), rels, ad.symmetric_relations()
    )
    return {"stats": pred["stats"], "scores": res}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["run", "score"])
    ap.add_argument("--split", default="dev")
    ap.add_argument("--doc", required=True)
    ap.add_argument("--tag", default="rehearsal")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-usd", type=float, default=2.0)
    a = ap.parse_args()
    if a.phase == "run":
        print(
            json.dumps(
                run_doc(a.split, a.doc, a.tag, dry_run=a.dry_run, max_usd=a.max_usd),
                indent=1,
                default=str,
            )
        )
    else:
        res = score_doc(
            a.split, a.doc, f"cr012_scinlp_{a.tag}_{a.doc.replace('.', '_').replace('-', '_')}_E0"
        )
        print(
            json.dumps(
                {"stats": res["stats"], **{k: v.to_dict() for k, v in res["scores"].items()}},
                indent=1,
                default=str,
            )
        )


if __name__ == "__main__":
    main()
