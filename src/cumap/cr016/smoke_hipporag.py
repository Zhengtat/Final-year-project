"""CR-016 STOP 1 smoke test of HippoRAG mechanics. Runs ONLY in the isolated environment (`.venv-hipporag/bin/python`), imports nothing from cumap, makes no real LLM call:
a local stub implements the OpenAI chat endpoint (canned NER / triple / fact-filter answers), so this checks the plumbing, not OpenIE quality.

Checks: incremental indexing, persistent reload, source_id/metadata provenance, causal retrieval filter that fails closed, separate arm indexes (HippoRAG vs dense StandardRAG).
    .venv-hipporag/bin/python src/cumap/cr016/smoke_hipporag.py reports/cr016/smoke_test.json"""

from __future__ import annotations

import hashlib
import http.server
import json
import os
import re
import shutil
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "stub-not-a-key")
ROOT = Path(".")
WORK = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/cr016_smoke")  # overridden by caller to the scratchpad
EMB = "Transformers/sentence-transformers/all-MiniLM-L6-v2"
CALLS = {"ner": 0, "triples": 0, "filter": 0, "other": 0}


class Stub(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        msgs = body.get("messages", [])
        system = msgs[0]["content"] if msgs else ""
        last = msgs[-1]["content"] if msgs else ""
        if "extract named entities" in system:
            CALLS["ner"] += 1
            ents = sorted({m for m in re.findall(r"\b[A-Z][A-Za-z\-]{2,}(?: [A-Z][A-Za-z\-]{2,})*\b", last)})[:8] or ["network"]
            out = json.dumps({"named_entities": ents})
        elif "RDF" in system:
            CALLS["triples"] += 1
            ents = re.findall(r'"([^"]+)"', last.split("named_entities")[-1])[:6] or ["network", "link"]
            trip = [[ents[i], "relates to", ents[(i + 1) % len(ents)]] for i in range(len(ents))]
            out = json.dumps({"triples": trip})
        else:
            CALLS["filter"] += 1
            out = '[[ ## fact_after_filter ## ]]\n{"fact": []}\n\n[[ ## completed ## ]]'
        resp = {"id": "stub", "object": "chat.completion", "created": int(time.time()), "model": body.get("model", "stub"), "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": out}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
        data = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class FutureLeak(Exception):
    pass


def causal_retrieve(system, query: str, query_order: int, k: int, section: str):
    """Retrieve, then FAIL CLOSED if any returned chunk is not strictly earlier in source order."""
    sol = system.retrieve(queries=[query], num_to_retrieve=k)[0]
    meta = sol.doc_metadata if getattr(sol, "doc_metadata", None) else [{}] * len(sol.docs)
    rows = []
    for doc, sc, m in zip(sol.docs, sol.doc_scores, meta):
        if m.get("source_order") is None or m["source_order"] >= query_order:
            raise FutureLeak(f"query_section={section} order={query_order} retrieved {m}")
        rows.append({"id": m.get("chunk_id"), "section": m.get("section_id"), "source_order": m["source_order"], "score": float(sc), "text_hash": hashlib.sha256(doc.encode()).hexdigest()[:12]})
    return rows


class DenseArm:
    """M1 dense baseline on the SAME package/embedding/chunk store (StandardRAG). StandardRAG indexes plain strings and keeps no per-chunk metadata, so the adapter keeps a provenance sidecar."""

    def __init__(self, save_dir: str, **kw):
        from hipporag.StandardRAG import StandardRAG  # type: ignore

        self.dir = Path(save_dir)
        self.rag = StandardRAG(save_dir=save_dir, **kw)
        self.side = self.dir / "adapter_chunk_metadata.json"
        self.meta = json.loads(self.side.read_text()) if self.side.exists() else {}

    def index(self, chunks):
        for c in chunks:
            self.meta[hashlib.sha256(c.content.encode()).hexdigest()] = dict(c.metadata, source_id=c.source_id)
        self.rag.index([c.content for c in chunks])
        self.dir.mkdir(parents=True, exist_ok=True)
        self.side.write_text(json.dumps(self.meta, indent=1))

    def retrieve(self, queries, num_to_retrieve):
        sols = self.rag.retrieve(queries=queries, num_to_retrieve=num_to_retrieve)
        for sol in sols:
            sol.doc_metadata = [self.meta.get(hashlib.sha256(d.encode()).hexdigest(), {}) for d in sol.docs]
        return sols


def tree_manifest(d: Path) -> dict:
    return {str(p.relative_to(d)): p.stat().st_size for p in sorted(d.rglob("*")) if p.is_file()}


def main() -> None:
    from hipporag import HippoRAG  # type: ignore
    from hipporag.utils.misc_utils import Chunk  # type: ignore

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/v1"
    secs = [json.loads(line) for line in Path("data/interim/textbook_sections.jsonl").read_text().splitlines()]
    pick = ["1.1", "1.2", "2.1", "2.2", "2.3"]
    order = {s["section_id"]: i for i, s in enumerate(secs)}
    chunks = {}
    for s in secs:
        if s["section_id"] in pick:
            ps = [p.strip() for p in re.split(r"\n\s*\n", s["text"]) if p.strip()][:6]
            chunks[s["section_id"]] = [Chunk(content=p, source_id=f"{s['section_id']}#p{i}", metadata={"chunk_id": f"{s['section_id']}#p{i}", "section_id": s["section_id"], "paragraph": i, "source_order": order[s["section_id"]], "source_hash": hashlib.sha256(p.encode()).hexdigest()[:12]}) for i, p in enumerate(ps)]
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    common = dict(llm_model_name="stub-llm", embedding_model_name=EMB, llm_base_url=base)
    arms = {"P2_hipporag": HippoRAG(save_dir=str(WORK / "P2_hipporag"), **common), "P1_dense": DenseArm(str(WORK / "P1_dense"), **common)}
    res: dict = {"checks": {}, "snapshots": {}, "retrievals": {}}
    t0 = time.time()
    for sid in pick:  # incremental, in source order
        for name, sys_ in arms.items():
            sys_.index(chunks[sid])
            res["snapshots"].setdefault(name, {})[sid] = hashlib.sha256(json.dumps(tree_manifest(WORK / name), sort_keys=True).encode()).hexdigest()[:16]
    res["index_seconds"] = round(time.time() - t0, 1)
    res["stub_calls"] = dict(CALLS)
    query = "How do packets get forwarded from a switch to a router?"
    # causal check: querying section 2.2 may only see sections strictly before 2.2, so retrieve more and require the filter to fail closed on later chunks
    leaks = {}
    for name, sys_ in arms.items():
        try:
            causal_retrieve(sys_, query, order["1.2"], 5, "1.2")  # index also holds 2.x chunks -> must raise
            leaks[name] = "NO_ERROR_UNEXPECTED"
        except FutureLeak as e:
            leaks[name] = "FAILED_CLOSED: " + str(e)[:90]
    res["checks"]["future_retrieval_fails_closed"] = leaks
    # causal index discipline: an index built only from earlier sections never returns a later one
    for name, cls in (("P2_hipporag", lambda d, **kw: HippoRAG(save_dir=d, **kw)), ("P1_dense", DenseArm)):
        s2 = cls(str(WORK / (name + "_causal_1_2")), **common)
        for sid in ("1.1", "1.2"):
            s2.index(chunks[sid])
        rows = causal_retrieve(s2, query, order["2.1"], 4, "2.1")
        res["retrievals"][name] = rows
        res["checks"].setdefault("index_with_only_earlier_sections_passes_causal_filter", {})[name] = all(r["source_order"] < order["2.1"] for r in rows) and len(rows) > 0
    # persistent reload
    before = {n: [r["id"] for r in res["retrievals"][n]] for n in res["retrievals"]}
    reload_ok = {}
    for name, cls in (("P2_hipporag", lambda d, **kw: HippoRAG(save_dir=d, **kw)), ("P1_dense", DenseArm)):
        s3 = cls(str(WORK / (name + "_causal_1_2")), **common)
        rows = causal_retrieve(s3, query, order["2.1"], 4, "2.1")
        reload_ok[name] = [r["id"] for r in rows] == before[name]
    res["checks"]["persistent_reload_same_retrieval"] = reload_ok
    # provenance metadata survives
    meta_files = {"P2_hipporag": any((WORK / "P2_hipporag_causal_1_2").rglob("chunk_metadata.json")), "P1_dense (adapter sidecar)": (WORK / "P1_dense_causal_1_2" / "adapter_chunk_metadata.json").exists()}
    res["checks"]["chunk_metadata_file_persisted"] = meta_files
    res["checks"]["retrieval_rows_have_section_and_source_order"] = all(r["section"] and r["source_order"] is not None and r["id"] for rows in res["retrievals"].values() for r in rows)
    # separate arm indexes
    a, b = set(tree_manifest(WORK / "P2_hipporag")), set(tree_manifest(WORK / "P1_dense"))
    res["checks"]["arm_indexes_are_separate_directories"] = (WORK / "P2_hipporag").resolve() != (WORK / "P1_dense").resolve()
    res["arm_files"] = {"P2_hipporag": sorted(a)[:12], "P1_dense": sorted(b)[:12]}
    res["environment"] = {"python": sys.version.split()[0]}
    import importlib.metadata as md

    for p in ("torch", "transformers", "sentence-transformers", "hipporag", "networkx", "python-igraph", "litellm", "openai", "numpy"):
        try:
            res["environment"][p] = md.version(p)
        except md.PackageNotFoundError:
            res["environment"][p] = None
    Path(sys.argv[1]).write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res["checks"], indent=1, default=str))


if __name__ == "__main__":
    main()
