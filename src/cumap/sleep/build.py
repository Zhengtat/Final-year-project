"""Shared loader for the STOP 2 pipeline: snapshot, lexicon/alias context, embeddings, candidates (cached on disk)."""

from __future__ import annotations

import pickle
from pathlib import Path

from cumap.config import REPO_ROOT, load_demo_slice
from cumap.expert_kg.cr008_run import build_context
from cumap.expert_kg.lexicon import Lexicon
from cumap.expert_kg.slice_rerun import load_sections
from cumap.sleep import candidates as C
from cumap.sleep.snapshot import Snapshot, load_snapshot

RUN = "slice3_c2"
CACHE = REPO_ROOT / "data/interim/sleep"


def load_all(run: str = RUN, use_cache: bool = True):
    cfg = load_demo_slice()
    sections = load_sections(REPO_ROOT / cfg.pd.source_jsonl, list(cfg.pd.chapters))
    snap = load_snapshot(run, sections)
    lex = Lexicon.load(REPO_ROOT / "configs/term_lexicon.yaml")
    cp_like = {
        "concepts": [{"canonical_name": n.name, "aliases": n.aliases} for n in snap.nodes.values()]
    }
    ctx = build_context(cp_like, sections, lex)
    cache = CACHE / f"vectors_{run}_{snap.sha256[:12]}.pkl"
    if use_cache and cache.exists():
        vec = pickle.loads(cache.read_bytes())
    else:
        vec = C.embed_nodes(snap.nodes)
        CACHE.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(pickle.dumps(vec))
    return sections, snap, lex, ctx, vec


def candidates(snap: Snapshot, vec, ctx) -> C.CandidateSet:
    return C.generate(snap, vec, ctx)


def main() -> None:
    import json

    _sections, snap, _lex, ctx, vec = load_all()
    cs = candidates(snap, vec, ctx)
    out = {"snapshot_sha256": snap.sha256, "nodes": len(snap.nodes), **cs.counts()}
    out["candidates_per_node"] = out["union"] * 2 / len(snap.nodes)
    print(json.dumps(out, indent=1))
    Path("/dev/null")


if __name__ == "__main__":
    main()
