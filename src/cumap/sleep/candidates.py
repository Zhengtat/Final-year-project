"""CR-011 §6 multi-signal candidate generation ($0, local). Recall-oriented union of independent sources; every source is
counted separately. Embeddings, graph overlap and eRST context are retrieval/feature signals only: none of them proves
identity, and no candidate is a merge decision."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np

from cumap.expert_kg.alias_rules import AliasConfig, r1_key, split_embedded_acronym
from cumap.expert_kg.canonical_rules import AliasContext
from cumap.expert_kg.mentions import default_lemma
from cumap.sleep.snapshot import Node, Snapshot

SIGNALS = (
    "lexicon_same",
    "r1_key",
    "token_overlap",
    "r2_acronym",
    "r3_strong",
    "r3_weak",
    "name_embedding",
    "definition_embedding",
    "evidence_embedding",
    "graph_neighbours",
    "same_surface",
    "same_concept_queue",
)
TOPK = {
    "name_embedding": 20,
    "definition_embedding": 20,
    "evidence_embedding": 10,
    "graph_neighbours": 10,
}
TOKEN = re.compile(r"[a-z0-9]+")


def pair(a: str, b: str) -> frozenset[str]:
    return frozenset((a, b))


def tokens(name: str) -> frozenset[str]:
    return frozenset(default_lemma(t) for t in TOKEN.findall(name.lower()))


@dataclass
class NodeVectors:
    name: np.ndarray
    definition: np.ndarray  # zero rows where the node has no definition
    evidence: np.ndarray
    has_definition: np.ndarray
    ids: list[str]

    def row(self, node_id: str) -> int:
        return self.ids.index(node_id)


def evidence_text(n: Node, limit: int = 3) -> str:
    quotes = []
    for m in n.mentions:
        q = (m.get("quote") or "").strip()
        if q and q not in quotes:
            quotes.append(q)
        if len(quotes) >= limit:
            break
    return " ".join(quotes)[:500]


def embed_nodes(
    nodes: dict[str, Node], model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
) -> NodeVectors:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    ids = sorted(nodes)

    def enc(texts: list[str]) -> np.ndarray:
        v = np.asarray(model.encode(texts, batch_size=64, show_progress_bar=False), dtype=float)
        n = np.linalg.norm(v, axis=1, keepdims=True)
        return v / np.where(n == 0, 1, n)

    name = enc([nodes[i].name for i in ids])
    has = np.array([bool(nodes[i].definition) for i in ids])
    defs = np.zeros_like(name)
    if has.any():
        defs[has] = enc([nodes[i].definition for i, h in zip(ids, has, strict=True) if h])
    ev = enc([evidence_text(nodes[i]) or nodes[i].name for i in ids])
    return NodeVectors(name, defs, ev, has, ids)


@dataclass
class CandidateSet:
    signals: dict[frozenset[str], set[str]] = field(default_factory=dict)

    def add(self, a: str, b: str, signal: str) -> None:
        if a != b:
            self.signals.setdefault(pair(a, b), set()).add(signal)

    def counts(self) -> dict:
        per = Counter(s for sig in self.signals.values() for s in sig)
        exclusive = Counter(next(iter(sig)) for sig in self.signals.values() if len(sig) == 1)
        return {
            "union": len(self.signals),
            "by_signal": {s: per.get(s, 0) for s in SIGNALS},
            "exclusive_by_signal": {s: exclusive.get(s, 0) for s in SIGNALS},
        }


def _topk_pairs(sim: np.ndarray, k: int, mask: np.ndarray | None = None) -> set[tuple[int, int]]:
    out: set[tuple[int, int]] = set()
    s = sim.copy()
    np.fill_diagonal(s, -np.inf)
    if mask is not None:
        s[~mask, :] = -np.inf
        s[:, ~mask] = -np.inf
    k = min(k, s.shape[0] - 1)
    idx = np.argpartition(-s, k, axis=1)[:, :k]
    for i in range(s.shape[0]):
        for j in idx[i]:
            if np.isfinite(s[i, j]):
                out.add((min(i, int(j)), max(i, int(j))))
    return out


def key_index(nodes: dict[str, Node], cfg: AliasConfig) -> dict[str, set[str]]:
    idx: dict[str, set[str]] = defaultdict(set)
    for n in nodes.values():
        for f in n.forms():
            k = r1_key(f, cfg)
            if k:
                idx[k].add(n.id)
            if sp := split_embedded_acronym(f, cfg):
                for x in sp:
                    idx[r1_key(x, cfg)].add(n.id)
    return idx


def generate(
    snap: Snapshot, vec: NodeVectors, ctx: AliasContext, topk: dict[str, int] | None = None
) -> CandidateSet:
    topk = {**TOPK, **(topk or {})}
    nodes, cfg, lex = snap.nodes, ctx.cfg, ctx.lexicon
    cs = CandidateSet()
    ids = vec.ids
    # lexicon `same` sets (R0 source)
    by_rep: dict[str, list[str]] = defaultdict(list)
    for n in nodes.values():
        for f in n.forms():
            if (rep := lex.same_set(f)) is not None:
                by_rep[rep].append(n.id)
    for members in by_rep.values():
        for a, b in combinations(sorted(set(members)), 2):
            cs.add(a, b, "lexicon_same")
    # R1 key equality and token overlap
    idx = key_index(nodes, cfg)
    for members in idx.values():
        for a, b in combinations(sorted(members), 2):
            cs.add(a, b, "r1_key")
    tok = {i: tokens(nodes[i].name) for i in ids}
    inv: dict[str, set[str]] = defaultdict(set)
    for i, t in tok.items():
        for w in t:
            inv[w].add(i)
    seen: set[frozenset[str]] = set()
    for i in ids:
        if len(tok[i]) < 2:
            continue
        cand = set().union(*(inv[w] for w in tok[i])) - {i}
        for j in cand:
            p = pair(i, j)
            if p in seen or len(tok[j]) < 2:
                continue
            seen.add(p)
            u = len(tok[i] | tok[j])
            if u and len(tok[i] & tok[j]) / u >= 0.5:
                cs.add(i, j, "token_overlap")
    # R2 / R3 from the textbook statements
    for k in ctx.abbrev:
        if len(k) != 2:
            continue
        a, b = sorted(k)
        for x in idx.get(a, ()):
            for y in idx.get(b, ()):
                cs.add(x, y, "r2_acronym")
    for k in ctx.strong:
        if len(k) != 2:
            continue
        a, b = sorted(k)
        for x in idx.get(a, ()):
            for y in idx.get(b, ()):
                cs.add(x, y, "r3_strong")
    for k in ctx.weak:
        if len(k) != 2:
            continue
        a, b = sorted(k)
        for x in idx.get(a, ()):
            for y in idx.get(b, ()):
                cs.add(x, y, "r3_weak")
    # embeddings (retrieval only)
    for sig, mat, k, mask in (
        ("name_embedding", vec.name, topk["name_embedding"], None),
        ("definition_embedding", vec.definition, topk["definition_embedding"], vec.has_definition),
        ("evidence_embedding", vec.evidence, topk["evidence_embedding"], None),
    ):
        for i, j in _topk_pairs(mat @ mat.T, k, mask):
            cs.add(ids[i], ids[j], sig)
    # graph neighbours: shared accepted-edge neighbours, ranked by Jaccard
    nb = {i: nodes[i].neighbours for i in ids}
    for i in ids:
        scored = []
        for j in ids:
            if j <= i or not nb[i] or not nb[j]:
                continue
            inter = len(nb[i] & nb[j])
            if inter:
                scored.append((inter / len(nb[i] | nb[j]), j))
        for _s, j in sorted(scored, reverse=True)[: topk["graph_neighbours"]]:
            cs.add(i, j, "graph_neighbours")
    # same surface (any chapter)
    by_surface: dict[str, set[str]] = defaultdict(set)
    for n in nodes.values():
        for f in n.forms():
            by_surface[f.casefold()].add(n.id)
    for members in by_surface.values():
        for a, b in combinations(sorted(members), 2):
            cs.add(a, b, "same_surface")
    # the accumulated same_concept queue
    for a, b in snap.same_concept_pairs:
        if a in nodes and b in nodes:
            cs.add(a, b, "same_concept_queue")
    return cs
