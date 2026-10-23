"""CR-032 SciNLP side of `HIER-T1` ($0, no model call): identity builders, the unit scorer and the scoped owner identity sheet.

SciNLP gold relations link mention spans and carry no concept clusters, so closure needs an identity step:
* `surface` (the CR-022 A2 rule, kept only as the determinism gate): one pseudo-node per case-folded, whitespace-normalised surface;
* `surf_r1` (`HIER-T1-SURF-R1`): the CR-008 R1 name key ("prefix-tuning" = "prefixtuning") plus acronym <-> long form pairs found in the same paper
  (an ambiguous short form is not merged). Identity inferred from strings: a labelled cross-check, never a headline;
* `sheet` (`HIER-T1`): the owner's scoped identity sheet (hierarchy-relation endpoints only). Gold mentions on the sheet take the owner's group;
  every other span is its own node. Code writes the blind sheet to `data/interim/suggestions/` and only reads the marked copy (rule 2)."""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from cumap.cr012.scinlp_oracle import surface_key
from cumap.cr012.types import Span, UnitGold
from cumap.cr032 import hier_t1 as H
from cumap.expert_kg.alias_rules import AliasConfig, find_abbreviations, r1_key

Ident = Callable[[Span], str]
SHEET_COLUMNS = ["row_id", "paper", "mention_text", "span", "sentence", "concept_group", "note"]


def _text(doc, sp: Span) -> str:
    a, b = doc.span_to_chars(sp)
    return doc.text[a:b]


def surface_identity(doc) -> Ident:
    return lambda sp: "s:" + surface_key(_text(doc, sp))


def r1_identity(doc, cfg: AliasConfig | None = None) -> tuple[Ident, dict]:
    """(identity function, stats). Union-find over R1 keys with unambiguous acronym <-> long-form pairs from the paper's own text."""
    cfg = cfg or AliasConfig.load()
    parent: dict[str, str] = {}

    def find(k: str) -> str:
        parent.setdefault(k, k)
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    longs: dict[str, set[str]] = defaultdict(set)
    for p in find_abbreviations(doc.text, cfg):
        sk, lk = r1_key(p.short_form, cfg), r1_key(p.long_form, cfg)
        if sk and lk and sk != lk:
            longs[sk].add(lk)
    merged_acronyms = 0
    for sk, lks in longs.items():
        if len(lks) == 1:  # an ambiguous short form is not merged
            parent[find(sk)] = find(next(iter(lks)))
            merged_acronyms += 1

    def ident(sp: Span) -> str:
        t = _text(doc, sp)
        k = r1_key(t, cfg)
        return "r1:" + find(k) if k else "s:" + surface_key(t)

    return ident, {"acronym_pairs_merged": merged_acronyms}


def collision_report(doc, gold: UnitGold, ident: Ident, examples: int = 5) -> dict:
    """Gold mentions -> pseudo-nodes; `merged_surfaces` = distinct case-folded surfaces that share a node (what R1 / acronym rules added)."""
    nodes: dict[str, set[str]] = defaultdict(set)
    for m in gold.mentions:
        nodes[ident(m.span)].add(surface_key(_text(doc, m.span)))
    multi = sorted((sorted(v) for v in nodes.values() if len(v) > 1), key=lambda v: (-len(v), v))
    return {
        "gold_mentions": len(gold.mentions),
        "gold_nodes": len(nodes),
        "collisions": len(gold.mentions) - len(nodes),
        "nodes_merging_distinct_surfaces": len(multi),
        "examples": multi[:examples],
    }


def scinlp_unit(
    gold: UnitGold,
    rels: list[tuple],
    unplaced_by_label: dict[str, int],
    variant: str,
    labels: frozenset[str],
    ident: Ident,
    typed: frozenset[str] = frozenset(),
) -> dict:
    """`rels`: placed predicted relations (src_span, tgt_span, label, ...). Gold edges: the unit's mention-level relations in `labels`. In every variant
    but FROZEN each unplaced predicted edge of a label in the set is one false positive (rule 35). SciNLP has no part types, so every relation chains as
    one (`typed` is empty unless a caller says otherwise)."""
    g = {
        (r.relation, None, ident(r.src_span), ident(r.tgt_span))
        for r in gold.relations
        if r.relation in labels
    }
    p = {(r[2], None, ident(r[0]), ident(r[1])) for r in rels if r[2] in labels}  # fmt: skip
    extra = (
        0
        if variant == "FROZEN"
        else sum(n for lab, n in unplaced_by_label.items() if lab in labels)
    )
    return H.score_edges(g, p, typed, extra_fp=extra)


# ---------------------------------------------------------------- scoped owner identity sheet
def hierarchy_endpoints(gold: UnitGold, labels: frozenset[str]) -> list[Span]:
    seen: dict[Span, None] = {}
    for r in gold.relations:
        if r.relation in labels:
            seen.setdefault(r.src_span, None)
            seen.setdefault(r.tgt_span, None)
    return sorted(seen)


def sentence_of(doc, sp: Span) -> str:
    import bisect

    k = bisect.bisect_right(doc.sentence_ends, sp[0])
    start = doc.sentence_ends[k - 1] if k else 0
    return " ".join(doc.tokens[start : doc.sentence_ends[k]])


def write_identity_sheet(docs: dict, golds: dict, labels: frozenset[str], out: Path) -> int:
    """Blind sheet: paper, mention text, span, sentence, an empty concept_group column. No system output, no model call. Never overwrites and
    never writes under data/gold/ (rule 2)."""
    if "gold" in out.parts:
        raise ValueError("code never writes under data/gold/ (rule 2)")
    if out.exists():
        raise FileExistsError(f"{out.name} already exists; every sheet is a new file")
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(SHEET_COLUMNS)
        for dk in sorted(docs):
            for sp in hierarchy_endpoints(golds[dk], labels):
                n += 1
                w.writerow(
                    [
                        n,
                        dk,
                        _text(docs[dk], sp),
                        f"{sp[0]}-{sp[1]}",
                        sentence_of(docs[dk], sp),
                        "",
                        "",
                    ]
                )
    return n


def load_identity_marks(path: Path) -> dict[str, dict[Span, str]]:
    """{paper: {span: group}} from the owner's marked copy; rows with an empty group are ignored. Read-only."""
    out: dict[str, dict[Span, str]] = defaultdict(dict)
    with path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            g = (r.get("concept_group") or "").strip()
            if g:
                a, b = r["span"].split("-")
                out[r["paper"]][(int(a), int(b))] = g
    return dict(out)


def sheet_identity(paper: str, marks: dict[str, dict[Span, str]]) -> Ident:
    m = marks.get(paper, {})
    return lambda sp: ("g:" + m[sp]) if sp in m else f"span:{sp[0]}-{sp[1]}"
