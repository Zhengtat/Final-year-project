"""CR-013 lineage: a DAG over object ids (child -> parents toward the source evidence), locator resolution, and walking back from a final object.

Many mentions -> one concept and many evidence records -> one edge are ordinary DAG fan-in. Nothing is re-keyed: object ids keep the production ids behind a
namespace prefix (`concept:`, `v4node:`, `mention:`, `pair:`, `relrow:`, `edge:`, `unit:`)."""

from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from functools import lru_cache

from cumap.config import REPO_ROOT

TOKEN = re.compile(r"\.?([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]|\['([^']*)'\]")


def parse_locator(locator: str) -> list[str | int]:
    out: list[str | int] = []
    pos = 0
    while pos < len(locator):
        m = TOKEN.match(locator, pos)
        if not m:
            raise ValueError(f"bad locator {locator!r} at {pos}")
        out.append(
            m.group(1)
            if m.group(1)
            else (int(m.group(2)) if m.group(2) is not None else m.group(3))
        )
        pos = m.end()
    return out


@lru_cache(maxsize=16)
def _load(path: str):
    p = REPO_ROOT / path
    if path.endswith(".jsonl"):
        return {
            "line": [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
        }
    return json.loads(p.read_text(encoding="utf-8"))


def resolve(ref: str):
    """`"<artifact>::<locator>"` -> the stored value (or None when the locator does not resolve)."""
    path, _, locator = ref.partition("::")
    try:
        cur = _load(path)
        for tok in parse_locator(locator):
            cur = cur[tok]
        return cur
    except (KeyError, IndexError, TypeError, FileNotFoundError, ValueError):
        return None


def norm(s: str) -> str:
    return " ".join(str(s).split()).lower()


class Lineage:
    def __init__(self, links: list[dict], finals: dict[str, str], evidence: dict[str, list[str]]):
        self.parents: dict[str, list[dict]] = defaultdict(list)
        for ln in links:
            self.parents[ln["child"]].append(ln)
        self.finals, self.evidence = finals, evidence

    def trace_back(self, object_id: str, max_nodes: int = 5000) -> dict:
        """Breadth-first walk toward the sources: -> {"nodes": [ids in visit order], "links": [...], "evidence": [refs]} (deterministic)."""
        seen, order, links, ev = {object_id}, [], [], []
        q = deque([object_id])
        while q and len(order) < max_nodes:
            cur = q.popleft()
            order.append(cur)
            ev += [r for r in self.evidence.get(cur, []) if r not in ev]
            for ln in sorted(self.parents.get(cur, []), key=lambda x: (x["parent"], x["link"])):
                links.append(ln)
                if ln["parent"] not in seen:
                    seen.add(ln["parent"])
                    q.append(ln["parent"])
        return {"nodes": order, "links": links, "evidence": ev}

    def records(self, store) -> list[dict]:
        ids = (
            set(self.parents)
            | set(self.evidence)
            | set(self.finals)
            | {p["parent"] for ls in self.parents.values() for p in ls}
        )
        out = []
        for oid in sorted(ids):
            out.append({
                "object_id": oid, "object_type": self.finals.get(oid) or oid.split(":", 1)[0], "final": oid in self.finals,
                "parents": [{"id": p["parent"], "link": p["link"], "layer": p["layer"], "join": p["join"]} for p in sorted(self.parents.get(oid, []), key=lambda x: (x["parent"], x["link"]))],
                "evidence_refs": self.evidence.get(oid, []), "event_ids": sorted(store.by_object.get(oid, [])),
            })  # fmt: skip
        return out
