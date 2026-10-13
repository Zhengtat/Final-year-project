"""CR-016 STOP 2 runner (isolated environment only; imports nothing from cumap). Strictly causal loop over the exposed book-order units:

    for each unit in source order:
        answer this unit's queries with M1 (dense) and M2 (HippoRAG) against the index of EARLIER units only
        then index the unit into both arms and record the index snapshot id

The runner never sees relevance labels (only query text, section and source order). Every retrieved item is checked: source_order must be strictly earlier than the query's, or the run FAILS CLOSED.

    .venv-hipporag/bin/python src/cumap/cr016/run_retrieval.py --stage2 data/processed/cr016/stage2 --work <dir> --out <dir> --llm-base-url http://127.0.0.1:18765/v1 [--max-order N]"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "shim-not-a-key")
EMB = "Transformers/sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 10
LLM_LABEL = "gpt-6-luna-via-shim"


class FutureLeak(Exception):
    pass


class DenseArm:
    """M1: HippoRAG's own StandardRAG (same package, same embedder, same chunk store) + a provenance sidecar (StandardRAG keeps no per-chunk metadata)."""

    def __init__(self, save_dir: str, base: str):
        from hipporag.StandardRAG import StandardRAG  # type: ignore

        self.dir = Path(save_dir)
        self.rag = StandardRAG(
            save_dir=save_dir, llm_model_name=LLM_LABEL, embedding_model_name=EMB, llm_base_url=base
        )
        self.side = self.dir / "adapter_chunk_metadata.json"
        self.meta = json.loads(self.side.read_text()) if self.side.exists() else {}

    def index(self, chunks):
        for c in chunks:
            self.meta[hashlib.sha256(c.content.encode()).hexdigest()] = dict(
                c.metadata, source_id=c.source_id
            )
        self.rag.index([c.content for c in chunks])
        self.side.write_text(json.dumps(self.meta))

    def retrieve(self, q: str, k: int):
        sol = self.rag.retrieve(queries=[q], num_to_retrieve=k)[0]
        return (
            sol.docs,
            sol.doc_scores,
            [self.meta.get(hashlib.sha256(d.encode()).hexdigest(), {}) for d in sol.docs],
        )


class GraphArm:
    """M2: HippoRAG 2 (OpenIE + fact retrieval + recognition memory + PPR)."""

    def __init__(self, save_dir: str, base: str):
        from hipporag import HippoRAG  # type: ignore
        from hipporag.utils.config_utils import BaseConfig  # type: ignore

        cfg = BaseConfig(
            temperature=None,
            retrieval_top_k=TOP_K,
            save_dir=save_dir,
            llm_name=LLM_LABEL,
            llm_base_url=base,
            embedding_model_name=EMB,
        )
        self.rag = HippoRAG(
            global_config=cfg,
            save_dir=save_dir,
            llm_model_name=LLM_LABEL,
            embedding_model_name=EMB,
            llm_base_url=base,
        )
        self.dir = Path(save_dir)

    def index(self, chunks):
        self.rag.index(chunks)

    def retrieve(self, q: str, k: int):
        sol = self.rag.retrieve(queries=[q], num_to_retrieve=k)[0]
        return sol.docs, sol.doc_scores, (sol.doc_metadata or [{}] * len(sol.docs))


def snapshot_id(arm_dir: Path, label: str) -> str:
    files = {
        str(p.relative_to(arm_dir)): p.stat().st_size
        for p in sorted(arm_dir.rglob("*"))
        if p.is_file() and "llm_cache" not in p.parts and p.suffix != ".lock"
    }
    return f"{label}@{hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:16]}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage2", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--llm-base-url", required=True)
    ap.add_argument("--max-order", type=int, default=10**9)
    ap.add_argument("--config-hash", default="")
    a = ap.parse_args()
    from hipporag.utils.misc_utils import Chunk  # type: ignore

    s2, work, out = Path(a.stage2), Path(a.work), Path(a.out)
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    chunks = [json.loads(x) for x in (s2 / "corpus.jsonl").read_text().splitlines() if x]
    queries = [json.loads(x) for x in (s2 / "queries.jsonl").read_text().splitlines() if x]
    by_unit: dict[int, list[dict]] = defaultdict(list)
    for c in chunks:
        by_unit[c["source_order"]].append(c)
    q_by_unit: dict[int, list[dict]] = defaultdict(list)
    for q in queries:
        q_by_unit[q["source_order"]].append(q)
    arms = {
        "M1_dense": DenseArm(str(work / "M1_dense"), a.llm_base_url),
        "M2_hipporag": GraphArm(str(work / "M2_hipporag"), a.llm_base_url),
    }
    rec_path = out / "retrieval_records.jsonl"
    rec_path.write_text("")
    last_indexed = {n: None for n in arms}
    snap = {n: "empty" for n in arms}
    timings = defaultdict(float)
    counts = defaultdict(int)
    manifest = {
        "units": [],
        "embedding": EMB,
        "llm_via": "LLMClient shim",
        "top_k": TOP_K,
        "config_hash": a.config_hash,
    }
    t_start = time.time()
    for order in sorted(by_unit):
        if order > a.max_order:
            break
        sid = by_unit[order][0]["section_id"]
        for q in q_by_unit.get(order, []):
            for name, arm in arms.items():
                if last_indexed[name] is None:
                    continue  # nothing indexed yet: no earlier evidence exists
                t0 = time.perf_counter()
                docs, scores, metas = arm.retrieve(q["query_text"], TOP_K)
                dt = time.perf_counter() - t0
                timings[name] += dt
                counts[name] += 1
                items = []
                for rank, (d, sc, m) in enumerate(zip(docs, scores, metas), 1):
                    so = m.get("source_order")
                    if so is None or so >= q["source_order"]:
                        raise FutureLeak(f"{q['query_id']} {name} retrieved {m}")
                    items.append(
                        {
                            "rank": rank,
                            "chunk_id": m.get("chunk_id"),
                            "source_section": m.get("section_id"),
                            "source_order": so,
                            "score": float(sc),
                            "source_locator": f"{m.get('section_id')}#p{m.get('paragraph')}",
                            "future_section_check": "ok",
                        }
                    )
                rec = {"query_id": q["query_id"], "query_section": q["query_section"], "query_source_order": q["source_order"], "backend": name, "index_snapshot_id": snap[name], "latency_s": round(dt, 4),
                       "retrieved": items, "embedding": EMB, "config_hash": a.config_hash, "top_k": TOP_K}  # fmt: skip
                with rec_path.open("a") as f:
                    f.write(json.dumps(rec) + "\n")
        t0 = time.time()
        cks = [
            Chunk(
                content=c["text"],
                source_id=c["chunk_id"],
                metadata={
                    "chunk_id": c["chunk_id"],
                    "section_id": c["section_id"],
                    "paragraph": c["paragraph"],
                    "source_order": c["source_order"],
                    "source_hash": c["source_hash"],
                },
            )
            for c in by_unit[order]
        ]
        for name, arm in arms.items():
            t1 = time.time()
            arm.index(cks)
            timings["index_" + name] += time.time() - t1
            last_indexed[name] = sid
            snap[name] = snapshot_id(arm.dir, f"{name}:{sid}")
        manifest["units"].append(
            {
                "source_order": order,
                "section_id": sid,
                "paragraphs": len(cks),
                "snapshots": dict(snap),
                "seconds": round(time.time() - t0, 1),
            }
        )
        print(
            f"indexed {sid} (order {order}) {len(cks)} paragraphs, {round(time.time() - t0, 1)}s; queries so far {dict(counts)}",
            flush=True,
        )
    manifest["timings_s"] = {k: round(v, 2) for k, v in timings.items()}
    manifest["query_counts"] = dict(counts)
    manifest["wall_seconds"] = round(time.time() - t_start, 1)
    manifest["final_snapshots"] = dict(snap)
    import importlib.metadata as md

    manifest["environment"] = {
        p: md.version(p)
        for p in (
            "hipporag",
            "torch",
            "transformers",
            "sentence-transformers",
            "networkx",
            "python-igraph",
            "litellm",
            "openai",
        )
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=1))
    print(
        json.dumps({"done": True, "wall": manifest["wall_seconds"], "queries": dict(counts)}),
        flush=True,
    )


if __name__ == "__main__":
    sys.exit(main())
