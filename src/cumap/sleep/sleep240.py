"""CR-011 §13-14: SLEEP-240 construction. 240 fresh blind pair judgements, 6 strata x 40, split 80 development / 160 held-out by
candidate family (never by random pair). Strata are defined from candidate signals and features only: no scorer output and no
label is used to pick items. Annotator sheets hide source, score, band and arm. Held-out labels stay sealed until STOP 4."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from cumap.expert_kg.alias_rules import AliasConfig, r1_key
from cumap.sleep.snapshot import Node

SEED = 20261009
STRATA = (
    "deterministic_r1_r3",
    "high_similarity_r4",
    "confusables_difficult_negatives",
    "one_token_polysemy",
    "cross_chapter_long_distance",
    "cluster_bridge_transitive_risk",
)
PER_STRATUM = 40
DEV, HELDOUT = 80, 160
MAX_PAIRS_PER_NODE = 2  # keeps families small enough to split 80/160
DET = {"lexicon_same", "r1_key", "token_overlap", "r2_acronym", "r3_strong", "r3_weak"}
BLIND_COLUMNS = [
    "item_id", "name_a", "name_b", "type_a", "type_b", "definition_a", "definition_b",
    "evidence_a_1", "evidence_a_2", "evidence_b_1", "evidence_b_2",
    "decision", "different_kind", "preferred_canonical_form", "evidence_sufficient", "notes",
]  # fmt: skip
MANIFEST_COLUMNS = [
    "item_id", "split", "stratum", "candidate_family_id", "cluster_id", "source_run_id", "section_ids",
    "pair_a_id", "pair_b_id", "double_annotation", "shown_a", "memberships",
]  # fmt: skip


@dataclass
class Item:
    pair: tuple[str, str]
    stratum: str
    memberships: tuple[str, ...]
    family: str = ""
    split: str = ""


def membership(
    a: Node, b: Node, f: dict, signals: set[str], flags: dict, bridges: set[frozenset[str]]
) -> list[str]:
    """Which strata this pair could serve. `flags`: lexicon_different, type_incompatible, taxonomy (LLM broader/narrower)."""
    out = []
    det = bool(signals & DET)
    sim = max(f["name_cos"], f["def_cos"] if not f["def_missing"] else 0.0)
    if det:
        out.append("deterministic_r1_r3")
    if (
        not det
        and not flags["type_incompatible"]
        and not flags["lexicon_different"]
        and sim >= 0.80
    ):
        out.append("high_similarity_r4")
    if (
        flags["lexicon_different"]
        or flags["taxonomy"]
        or (f["containment"] and f["name_cos"] >= 0.70)
    ):
        out.append("confusables_difficult_negatives")
    if f["one_token_any"] and (f["same_surface"] or f["head_equal"] or f["name_cos"] >= 0.75):
        out.append("one_token_polysemy")
    if f["cross_chapter"] and (
        f["name_cos"] >= 0.75
        or "token_overlap" in signals
        or (not f["def_missing"] and f["def_cos"] >= 0.75)
    ):
        out.append("cross_chapter_long_distance")
    if frozenset((a.id, b.id)) in bridges:
        out.append("cluster_bridge_transitive_risk")
    return out


def bridge_pairs(strong: set[frozenset[str]], is_risky) -> set[frozenset[str]]:
    """Pairs (A, C) with a strong chain A-B-C but no strong A-C edge that are risky as a merge (type/lexicon/low similarity):
    the transitive-closure hazard."""
    adj: dict[str, set[str]] = defaultdict(set)
    for p in strong:
        x, y = tuple(p)
        adj[x].add(y)
        adj[y].add(x)
    out: set[frozenset[str]] = set()
    for nb in adj.values():
        nb_sorted = sorted(nb)
        for i, x in enumerate(nb_sorted):
            for y in nb_sorted[i + 1 :]:
                p = frozenset((x, y))
                if p not in strong and is_risky(x, y):
                    out.add(p)
    return out


def allocate(pool: dict[tuple[str, str], list[str]], seed: int = SEED) -> tuple[list[Item], dict]:
    """Fill the scarcest stratum first; each node appears in at most MAX_PAIRS_PER_NODE items; an item serves one stratum."""
    rng = random.Random(seed)
    avail = {s: sorted(p for p, m in pool.items() if s in m) for s in STRATA}
    order = sorted(STRATA, key=lambda s: len(avail[s]))
    used_nodes: Counter = Counter()
    chosen: dict[tuple[str, str], str] = {}
    report = {"available_before_allocation": {s: len(avail[s]) for s in STRATA}, "selected": {}}
    for s in order:
        cands = [p for p in avail[s] if p not in chosen]
        rng.shuffle(cands)
        got = 0
        for p in cands:
            if got >= PER_STRATUM:
                break
            if any(used_nodes[n] >= MAX_PAIRS_PER_NODE for n in p):
                continue
            chosen[p] = s
            for n in p:
                used_nodes[n] += 1
            got += 1
        report["selected"][s] = got
    items = [
        Item(p, s, tuple(pool[p])) for p, s in sorted(chosen.items(), key=lambda kv: (kv[1], kv[0]))
    ]
    report["shortfall"] = {
        s: PER_STRATUM - report["selected"][s]
        for s in STRATA
        if report["selected"][s] < PER_STRATUM
    }
    return items, report


def families(items: list[Item], nodes: dict[str, Node], cfg: AliasConfig) -> None:
    """Candidate family = connected component where two items are linked if they share a node or share a normalised-form key (R1)
    on any form of their nodes, so spelling / plural / hyphen variants of one identity problem stay together."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        parent[find(a)] = find(b)

    for it in items:
        a, b = it.pair
        union(f"item:{a}|{b}", f"node:{a}")
        union(f"item:{a}|{b}", f"node:{b}")
        for nid in it.pair:
            for form in nodes[nid].forms():
                k = r1_key(form, cfg)
                if k:
                    union(f"node:{nid}", f"key:{k}")
    for it in items:
        it.family = (
            "F" + hashlib.sha1(find(f"item:{it.pair[0]}|{it.pair[1]}").encode()).hexdigest()[:8]
        )


def split(items: list[Item], seed: int = SEED) -> dict:
    """Assign whole families to development so that development has exactly 80 items, balancing strata (subset-sum DP, ties
    broken by stratum balance). Returns diagnostics."""
    by_fam: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        by_fam[it.family].append(it)
    fams = sorted(by_fam)
    random.Random(seed).shuffle(fams)
    target_stratum = DEV / len(STRATA)
    # dp over reachable (size) -> best family subset by balance cost, kept as dict size -> (cost, chosen tuple)
    best: dict[int, tuple[float, tuple[str, ...]]] = {0: (0.0, ())}
    for f in fams:
        sz = len(by_fam[f])
        cnt = Counter(it.stratum for it in by_fam[f])
        new = dict(best)
        for size, (_c, chosen) in best.items():
            ns = size + sz
            if ns > DEV:
                continue
            chosen2 = (*chosen, f)
            per = Counter(it.stratum for g in chosen2 for it in by_fam[g])
            cost = sum((per.get(s, 0) - target_stratum) ** 2 for s in STRATA)
            if ns not in new or cost < new[ns][0]:
                new[ns] = (cost, chosen2)
        best = new
        _ = cnt
    if DEV not in best:
        return {"status": "FAILED: no family subset sums to exactly 80", "reachable": sorted(best)}
    dev_f = set(best[DEV][1])
    for it in items:
        it.split = "dev" if it.family in dev_f else "heldout"
    return {
        "status": "ok",
        "families": len(fams),
        "largest_family": max(len(v) for v in by_fam.values()),
        "dev_by_stratum": dict(Counter(it.stratum for it in items if it.split == "dev")),
        "heldout_by_stratum": dict(Counter(it.stratum for it in items if it.split == "heldout")),
    }


def leakage_check(items: list[Item], nodes: dict[str, Node], cfg: AliasConfig) -> dict:
    """No family, node, or normalised-form key shared between development and held-out."""
    keys = {"dev": set(), "heldout": set()}
    nodes_by = {"dev": set(), "heldout": set()}
    fam = {"dev": set(), "heldout": set()}
    for it in items:
        fam[it.split].add(it.family)
        for n in it.pair:
            nodes_by[it.split].add(n)
            keys[it.split].update(r1_key(f, cfg) for f in nodes[n].forms())
    return {
        "shared_families": len(fam["dev"] & fam["heldout"]),
        "shared_nodes": len(nodes_by["dev"] & nodes_by["heldout"]),
        "shared_normalised_keys": len(keys["dev"] & keys["heldout"]),
        "ok": not (fam["dev"] & fam["heldout"])
        and not (nodes_by["dev"] & nodes_by["heldout"])
        and not (keys["dev"] & keys["heldout"]),
    }


def excerpts(n: Node, k: int = 2) -> list[str]:
    seen: list[str] = []
    ordered = sorted(
        n.mentions, key=lambda m: (m.get("role") != "defined", m.get("section_id", ""))
    )
    for m in ordered:
        q = (m.get("quote") or "").strip()
        if q and q not in seen:
            seen.append(q)
        if len(seen) == k:
            break
    return seen + [""] * (k - len(seen))


def sheets(
    items: list[Item], nodes: dict[str, Node], run_id: str, out: Path, seed: int = SEED
) -> dict:
    rng = random.Random(seed)
    heldout = [it for it in items if it.split == "heldout"]
    # double-annotation target: 80 of the 160 held-out, balanced over strata
    per = defaultdict(list)
    for it in heldout:
        per[it.stratum].append(it)
    double = set()
    for s in STRATA:
        lst = sorted(per[s], key=lambda it: it.pair)
        rng.shuffle(lst)
        double.update(it.pair for it in lst[: round(80 / len(STRATA))])
    extra = [it for it in sorted(heldout, key=lambda it: it.pair) if it.pair not in double]
    rng.shuffle(extra)
    for it in extra[: 80 - len(double)]:
        double.add(it.pair)
    manifest, written = [], {}
    order = list(items)
    rng.shuffle(order)
    ids = {it.pair: f"SL{n:03d}" for n, it in enumerate(order, 1)}
    for split_name in ("dev", "heldout"):
        rows = []
        for it in order:
            if it.split != split_name:
                continue
            flip = rng.random() < 0.5
            a_id, b_id = (it.pair[1], it.pair[0]) if flip else it.pair
            a, b = nodes[a_id], nodes[b_id]
            ea, eb = excerpts(a), excerpts(b)
            rows.append({
                "item_id": ids[it.pair], "name_a": a.name, "name_b": b.name, "type_a": a.type, "type_b": b.type,
                "definition_a": a.definition or "", "definition_b": b.definition or "",
                "evidence_a_1": ea[0], "evidence_a_2": ea[1], "evidence_b_1": eb[0], "evidence_b_2": eb[1],
                "decision": "", "different_kind": "", "preferred_canonical_form": "", "evidence_sufficient": "", "notes": "",
            })  # fmt: skip
            manifest.append({
                "item_id": ids[it.pair], "split": it.split, "stratum": it.stratum, "candidate_family_id": it.family,
                "cluster_id": it.family, "source_run_id": run_id,
                "section_ids": "|".join(sorted({nodes[n].first_section for n in it.pair})),
                "pair_a_id": a_id, "pair_b_id": b_id, "double_annotation": "yes" if it.pair in double else "no",
                "shown_a": a_id, "memberships": "|".join(it.memberships),
            })  # fmt: skip
        path = out / f"sleep240_{split_name}_blind_sheet.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=BLIND_COLUMNS)
            w.writeheader()
            w.writerows(rows)
        written[split_name] = {
            "path": str(path),
            "rows": len(rows),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    mpath = out / "sleep240_manifest_DO_NOT_SHARE.csv"
    with mpath.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        w.writeheader()
        w.writerows(sorted(manifest, key=lambda r: r["item_id"]))
    written["manifest"] = {
        "path": str(mpath),
        "rows": len(manifest),
        "sha256": hashlib.sha256(mpath.read_bytes()).hexdigest(),
    }
    written["double_annotation_heldout"] = len(double)
    return written


def assert_blind(path: Path) -> None:
    """The annotator sheet has exactly the contract columns and the judgement columns are empty."""
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == BLIND_COLUMNS
    for r in rows:
        assert not any(
            r[c]
            for c in (
                "decision",
                "different_kind",
                "preferred_canonical_form",
                "evidence_sufficient",
                "notes",
            )
        )


def summary(items: list[Item]) -> dict:
    return {
        "total": len(items),
        "by_stratum": dict(Counter(it.stratum for it in items)),
        "by_split": dict(Counter(it.split for it in items)),
        "by_stratum_split": dict(Counter(f"{it.split}/{it.stratum}" for it in items)),
        "multi_membership_items": sum(len(it.memberships) > 1 for it in items),
        "seed": SEED,
        "digest": hashlib.sha256(
            json.dumps([(it.pair, it.stratum, it.split) for it in items]).encode()
        ).hexdigest(),
    }
