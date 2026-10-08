"""CR-011 STOP 2: historical owner merge labels, replayed for candidate recall and scorer development. Read-only: this module
never writes under the gold folder. Paths are passed in by the caller. SLEEP-240 labels are NOT historical labels and never
enter here."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

from cumap.expert_kg.alias_rules import AliasConfig, r1_key
from cumap.expert_kg.lexicon import Lexicon
from cumap.sleep.features import UNKNOWN_TYPE
from cumap.sleep.snapshot import Node, Snapshot

SOURCES = {
    # file stem -> (column a, column b, mark column, evidence column | None, positive word)
    "cr007_merge_sheet": ("name_A", "name_B", "mark (same/different)", "evidence", "same"),
    "cr008_merge_sheet": ("name_A", "name_B", "mark (same/different)", "evidence", "same"),
    "cr009_stop3_glinks_slice3_c1": (
        "text form",
        "linked to node",
        "mark (same / not same)",
        "evidence",
        "same",
    ),
    "cr009_stop3b_glinks_slice3_c2": (
        "text form",
        "linked to node",
        "mark (same / not same)",
        "evidence",
        "same",
    ),
}


@dataclass
class Labelled:
    source: str
    a: str
    b: str
    label: int  # 1 = SAME, 0 = NOT_SAME
    evidence: str = ""
    resolution: str = ""  # distinct_nodes | same_node | partial | strings
    node_a: Node | None = None
    node_b: Node | None = None
    group: str = ""
    meta: dict = field(default_factory=dict)


def load_historical(gold_dir: Path) -> list[Labelled]:
    out: list[Labelled] = []
    for stem, (ca, cb, cm, ce, pos) in SOURCES.items():
        path = gold_dir / f"{stem}.csv"
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                mark = r[cm].strip().lower()
                if not mark:
                    continue
                out.append(
                    Labelled(
                        stem,
                        r[ca].strip(),
                        r[cb].strip(),
                        int(mark == pos),
                        (r.get(ce) or "").strip(),
                    )
                )
    return out


def lexicon_pairs(lex: Lexicon) -> tuple[list[Labelled], list[Labelled]]:
    """(negatives from approved `different` entries, authoritative R0 positives from approved `same` entries)."""
    neg, pos = [], []
    for e in lex.approved("different"):
        for x, y in combinations(e.forms, 2):
            neg.append(Labelled(f"lexicon:{e.id}", x, y, 0, e.quote or ""))
    for e in lex.approved("same"):
        for x, y in combinations(e.forms, 2):
            pos.append(Labelled(f"lexicon:{e.id}", x, y, 1, e.quote or ""))
    return neg, pos


def pseudo_node(text: str, evidence: str = "") -> Node:
    return Node(
        id=f"label:{text}",
        name=text,
        aliases=[],
        type=UNKNOWN_TYPE,
        definition=None,
        first_section="",
        mentions=[{"quote": evidence}] if evidence else [],
        description_history=[],
        chapter=-1,
    )


def resolve(items: list[Labelled], snap: Snapshot, cfg: AliasConfig) -> None:
    """Map each side to a snapshot node by R1 key over names and aliases. Both sides in different nodes = a real candidate pair;
    both in one node = the baseline already co-clustered them; otherwise string-level pseudo nodes."""
    idx: dict[str, set[str]] = {}
    for n in snap.nodes.values():
        for f in n.forms():
            k = r1_key(f, cfg)
            if k:
                idx.setdefault(k, set()).add(n.id)
    for it in items:
        ia, ib = idx.get(r1_key(it.a, cfg), set()), idx.get(r1_key(it.b, cfg), set())
        if len(ia) == 1 and len(ib) == 1:
            na, nb = next(iter(ia)), next(iter(ib))
            if na != nb:
                it.resolution, it.node_a, it.node_b = (
                    "distinct_nodes",
                    snap.nodes[na],
                    snap.nodes[nb],
                )
                continue
            it.resolution = "same_node"
        elif ia or ib:
            it.resolution = "partial"
        else:
            it.resolution = "strings"
        a = snap.nodes[next(iter(ia))] if len(ia) == 1 else None
        b = snap.nodes[next(iter(ib))] if len(ib) == 1 else None
        # keep the richer side real when only one side is a distinct node; the other side stays a string pseudo-node
        if a and not b:
            it.node_a, it.node_b = a, pseudo_node(it.b, it.evidence)
        elif b and not a:
            it.node_a, it.node_b = pseudo_node(it.a, it.evidence), b
        else:
            it.node_a, it.node_b = pseudo_node(it.a, it.evidence), pseudo_node(it.b)


def groups(items: list[Labelled], cfg: AliasConfig) -> None:
    """Normalised-form family for cross-validation: items sharing an R1 key on either side share a group."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for it in items:
        ka, kb = f"k:{r1_key(it.a, cfg)}", f"k:{r1_key(it.b, cfg)}"
        parent[find(ka)] = find(kb)
    for it in items:
        it.group = find(f"k:{r1_key(it.a, cfg)}")
