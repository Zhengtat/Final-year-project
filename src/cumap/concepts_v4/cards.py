"""CR-009 §3.2: the node store and the retriever that shows the generator the relevant EXISTING NODES.

Main pass: only GROWING nodes from EARLIER sections of the SAME run, in book order; never gold. Selection:
string hits (longest-match on name, alias or lexicon `same` form) marked in_text: yes; the top-k semantic hits
(in_text: no); the lexicon `different` partners of any hit. Cap 120 (string hits first)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from cumap.expert_kg.alias_rules import r1_key
from cumap.expert_kg.lexicon import Lexicon
from cumap.expert_kg.mentions import MentionMatcher


@dataclass
class Node:
    id: str
    name: str
    aliases: list[str]
    node_type: str
    first_section: str
    first_order: int
    definition: str | None = None
    def_section: str | None = None
    gloss: str = ""
    growing: bool = True
    mentions: list[dict] = field(default_factory=list)
    anchors: list[dict] = field(default_factory=list)
    extraction_origin: str = "independent"
    found_via_anchor: bool = False
    added_via_hint: str | None = None
    attributes: list[dict] = field(default_factory=list)
    embedding: np.ndarray | None = field(default=None, repr=False)

    def forms(self) -> list[str]:
        return [self.name, *self.aliases]

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "embedding"}
        return d


@dataclass
class Card:
    node: Node
    in_text: bool

    def to_bank_card(self) -> dict:
        n = self.node
        return {
            "id": n.id,
            "name": n.name,
            "aliases": n.aliases,
            "type": n.node_type,
            "def": f"§{n.def_section}" if n.def_section else "—",
            "in_text": self.in_text,
            "gloss": n.gloss,
        }


class NodeStore:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self._seq = 0

    def new_id(self) -> str:
        self._seq += 1
        return f"n_{self._seq:04d}"

    def add(self, node: Node) -> Node:
        self.nodes[node.id] = node
        return node

    def growing_before(self, order: int) -> list[Node]:
        return [n for n in self.nodes.values() if n.growing and n.first_order < order]


def make_gloss(text: str | None, words: int = 25) -> str:
    return " ".join((text or "").replace('"', "'").split()[:words])


def select_cards(
    paragraphs: dict[str, str],
    store: NodeStore,
    order: int,
    lexicon: Lexicon | None,
    embed_fn: Callable[[str], np.ndarray] | None,
    *,
    k: int = 30,
    cap: int = 120,
) -> list[Card]:
    eligible = store.growing_before(order)
    if not eligible:
        return []
    text = " ".join(paragraphs.values())
    vocab: dict[str, str] = {}
    for n in eligible:
        forms = set(n.forms())
        if lexicon is not None:
            forms |= lexicon.same_forms(n.name)
        for f in forms:
            vocab.setdefault(f.lower(), n.id)
    by_first: dict[str, int] = {}
    for h in MentionMatcher(vocab).find(text):
        by_first.setdefault(h.concept_id, h.start)
    string_ids = sorted(by_first, key=by_first.get)
    chosen = list(string_ids)
    partners: list[str] = []
    if lexicon is not None:
        key_to = {r1_key(f, lexicon.cfg): n.id for n in eligible for f in n.forms()}
        for nid in string_ids:
            for p in lexicon.different_partners(store.nodes[nid].name):
                pid = key_to.get(r1_key(p, lexicon.cfg))
                if pid and pid not in chosen and pid not in partners:
                    partners.append(pid)
    chosen += partners
    semantic: list[str] = []
    if embed_fn is not None and k > 0:
        for n in eligible:
            if n.embedding is None:
                n.embedding = np.asarray(embed_fn(f"{n.name}. {n.gloss}"), dtype=float)
        mat = np.stack([n.embedding for n in eligible])
        mat = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
        best = np.full(len(eligible), -1.0)
        for para in paragraphs.values():
            q = np.asarray(embed_fn(para), dtype=float)
            best = np.maximum(best, mat @ (q / (np.linalg.norm(q) + 1e-9)))
        taken = set(chosen)
        semantic = [eligible[i].id for i in np.argsort(-best) if eligible[i].id not in taken][:k]
    chosen += semantic
    in_text = set(string_ids)
    return [Card(store.nodes[i], i in in_text) for i in chosen[:cap]]


def split_paragraphs(text: str) -> dict[str, str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return {f"P{i}": p for i, p in enumerate(paras, 1)}
