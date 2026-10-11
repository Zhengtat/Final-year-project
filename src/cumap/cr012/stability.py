"""CR-012 stability experiment (CR section 13). The frozen E0 workflow runs three INDEPENDENT times on a frozen subset; every run is
stored separately and the report never selects a best run. Independence of model outputs requires a separate LLM cache namespace per
run (D4: stability repeats must not reuse model outputs)."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from statistics import mean, pstdev

from cumap.cr012.types import PredEdge, PredNode


@dataclass(frozen=True)
class RunGraph:
    run_id: str
    nodes: tuple[PredNode, ...]
    edges: tuple[PredEdge, ...]
    strict_e2e_f1: float | None
    cache_namespace: str


def node_key(n: PredNode) -> tuple:
    return (n.unit, n.name.casefold(), n.type)


def edge_keys(run: RunGraph) -> set[tuple]:
    by = {n.node_id: node_key(n) for n in run.nodes}
    return {(by[e.src], e.relation, by[e.tgt]) for e in run.edges if e.src in by and e.tgt in by}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


def _same_node_pairs(run: RunGraph) -> dict[frozenset, bool]:
    owner = {}
    for n in run.nodes:
        for s in n.mentions:
            owner.setdefault((n.unit, s), n.node_id)
    keys = sorted(owner)
    return {
        frozenset((a, b)): owner[a] == owner[b] for a, b in combinations(keys, 2) if a[0] == b[0]
    }


def canonicalisation_disagreement(a: RunGraph, b: RunGraph) -> float:
    pa, pb = _same_node_pairs(a), _same_node_pairs(b)
    common = set(pa) & set(pb)
    return sum(pa[k] != pb[k] for k in common) / len(common) if common else 0.0


def relation_disagreement(a: RunGraph, b: RunGraph) -> float:
    def by_pair(r: RunGraph) -> dict:
        by = {n.node_id: node_key(n) for n in r.nodes}
        out = {}
        for e in r.edges:
            if e.src in by and e.tgt in by:
                out.setdefault(frozenset((by[e.src], by[e.tgt])), set()).add(e.relation)
        return out

    ra, rb = by_pair(a), by_pair(b)
    common = set(ra) & set(rb)
    return sum(ra[k] != rb[k] for k in common) / len(common) if common else 0.0


def assert_independent(runs: list[RunGraph]) -> None:
    assert len({r.run_id for r in runs}) == len(runs), "stability runs must have distinct run ids"
    assert len({r.cache_namespace for r in runs}) == len(runs), (
        "stability runs may not share an LLM cache namespace"
    )


def stability_report(runs: list[RunGraph]) -> dict:
    """Mean and standard deviation of STRICT_E2E_EDGE_F1, pairwise node-set / edge-set Jaccard, canonicalisation and relation
    disagreement rates. All runs are listed; there is no best-run field by design."""
    assert_independent(runs)
    pairs = list(combinations(runs, 2))
    f1s = [r.strict_e2e_f1 for r in runs if r.strict_e2e_f1 is not None]
    return {
        "runs": len(runs),
        "per_run": [
            {
                "run_id": r.run_id,
                "strict_e2e_f1": r.strict_e2e_f1,
                "nodes": len(r.nodes),
                "edges": len(r.edges),
            }
            for r in runs
        ],
        "strict_e2e_f1_mean": mean(f1s) if f1s else None,
        "strict_e2e_f1_sd": pstdev(f1s) if len(f1s) > 1 else None,
        "node_set_jaccard_mean": mean(
            jaccard({node_key(n) for n in a.nodes}, {node_key(n) for n in b.nodes})
            for a, b in pairs
        ),
        "edge_set_jaccard_mean": mean(jaccard(edge_keys(a), edge_keys(b)) for a, b in pairs),
        "canonicalisation_disagreement_rate_mean": mean(
            canonicalisation_disagreement(a, b) for a, b in pairs
        ),
        "relation_disagreement_rate_mean": mean(relation_disagreement(a, b) for a, b in pairs),
        "selection": "none: all runs are retained and reported",
    }


def save_run(run: RunGraph, root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    p = root / f"{run.run_id}.json"
    assert not p.exists(), "a stored stability run is never overwritten"
    p.write_text(
        json.dumps(
            {
                "run_id": run.run_id,
                "cache_namespace": run.cache_namespace,
                "strict_e2e_f1": run.strict_e2e_f1,
                "nodes": [
                    n.__dict__ | {"mentions": [list(m) for m in n.mentions]} for n in run.nodes
                ],
                "edges": [
                    e.__dict__
                    | {
                        "evidence_span": list(e.evidence_span) if e.evidence_span else None,
                        "qualifiers": [list(q) for q in e.qualifiers],
                    }
                    for e in run.edges
                ],
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    return p


def client_for_run(index: int, root: str = "data/cache/cr012_stability"):
    """An LLMClient whose disk cache is private to stability run `index` (so no model output is reused across repeats)."""
    from cumap.config import get_settings
    from cumap.llm.client import LLMClient

    s = get_settings().model_copy(deep=True)
    s.paths.data_cache = Path(root) / f"run_{index}"
    return LLMClient(s, run_id=f"cr012_stability_run_{index}"), str(s.paths.data_cache)


def counts_by_unit(run: RunGraph) -> Counter:
    return Counter(n.unit for n in run.nodes)
