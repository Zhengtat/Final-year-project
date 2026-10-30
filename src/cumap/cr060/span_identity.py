"""CR-060 Part A: head-variant identity, a deterministic alias rule applied at assembly (after relation classification).

- `R-head`: a node form F (name or alias) that the paper writes directly followed by a generic head H ("GloVe model") gains the alias
  "F H"; another node named "F H" (same R1 key) is the same concept and merges into F's node.
- `R-acr`: F written directly followed by "( ACRONYM )" gains the alias "F ( ACRONYM )".

Every alias and merge records its rule and evidence (an exact substring of the paper, rule 3 / rule 19); a term-lexicon `different` pair is
never merged (rule 20). Merged nodes' edges are remapped; a duplicate edge or a self-loop made by a merge is marked `consolidated_into` (the
frozen scorers skip it) with the reason. Because the step runs after relation classification, applying it to a saved checkpoint equals
running it. Pure function: the input checkpoint is never modified."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from cumap.config import REPO_ROOT
from cumap.expert_kg.alias_rules import AliasConfig, r1_key

CONFIG = REPO_ROOT / "configs/span_identity.yaml"
SYMMETRIC_DEFAULT: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Variant:
    name: str
    r_head: str  # "name_like" | "all" | "off"
    r_acr: bool
    heads: frozenset[str]


def load_variant(name: str, path: Path = CONFIG) -> Variant:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    v = raw["variants"][name]
    return Variant(name, v["r_head"], bool(v["r_acr"]), frozenset(h.lower() for h in raw["heads"]))


def name_like(form: str) -> bool:
    return any(c.isupper() or c.isdigit() for c in form)


def _acronym_like(t: str) -> bool:  # the CR-052 X-acr test
    return bool(re.fullmatch(r"[A-Za-z0-9\-\.]{1,10}", t)) and sum(c.isupper() for c in t) >= 2


def _occurrences(form: str, text: str) -> list[re.Match]:
    pat = r"(?<![\w-])" + r"\s+".join(re.escape(t) for t in form.split()) + r"(?![\w-])"
    return list(re.finditer(pat, text, flags=re.IGNORECASE))


def variant_aliases(form: str, text: str, v: Variant) -> list[tuple[str, str, str]]:
    """[(alias, rule, evidence)] for one form: the extended surface as the paper writes it."""
    out: dict[str, tuple[str, str, str]] = {}
    head_ok = v.r_head == "all" or (v.r_head == "name_like" and name_like(form))
    for m in _occurrences(form, text):
        rest = text[m.end() :]
        if head_ok:
            h = re.match(r"\s+([A-Za-z]+)(?![\w-])", rest)
            if h and h.group(1).lower() in v.heads:
                ev = text[m.start() : m.end() + h.end()]
                out.setdefault(r1_key(ev, _CFG), (" ".join(ev.split()), "R-head", ev))
        if v.r_acr:
            a = re.match(r"\s*\(\s*([^\s()]+)\s*\)", rest)
            if a and _acronym_like(a.group(1)):
                ev = text[m.start() : m.end() + a.end()]
                out.setdefault("acr:" + ev.lower(), (" ".join(ev.split()), "R-acr", ev))
    return list(out.values())


_CFG = AliasConfig.load()


def apply(cp: dict, text: str, v: Variant, *, different: set[frozenset[str]] | None = None,
          symmetric: frozenset[str] = SYMMETRIC_DEFAULT) -> tuple[dict, dict]:  # fmt: skip
    """-> (new checkpoint, record {aliases: [...], merges: [...], edges_dropped: [...]})."""
    cp = copy.deepcopy(cp)
    different = different or set()
    concepts = cp["concepts"]
    by_key: dict[str, str] = {}
    for c in concepts:
        for f in [c["canonical_name"], *(c.get("aliases") or [])]:
            by_key.setdefault(r1_key(f, _CFG), c["concept_id"])
    by_id = {c["concept_id"]: c for c in concepts}
    rec: dict = {"variant": v.name, "aliases": [], "merges": [], "edges_dropped": [], "vetoed": []}
    into: dict[str, str] = {}

    def root(cid: str) -> str:
        while cid in into:
            cid = into[cid]
        return cid

    for c in concepts:
        if c["concept_id"] in into:
            continue
        forms = [c["canonical_name"], *(c.get("aliases") or [])]
        for f in forms:
            for alias, rule, ev in variant_aliases(f, text, v):
                k = r1_key(alias, _CFG)
                owner = root(by_key.get(k, c["concept_id"]))
                tgt = root(c["concept_id"])
                if owner != tgt:
                    names = {
                        by_id[owner]["canonical_name"].lower(),
                        by_id[tgt]["canonical_name"].lower(),
                    }
                    if frozenset(names) in different:
                        rec["vetoed"].append(
                            {"keep": tgt, "other": owner, "rule": rule, "evidence": ev}
                        )
                        continue
                    o, t = by_id[owner], by_id[tgt]
                    t["aliases"] = [
                        *(t.get("aliases") or []),
                        o["canonical_name"],
                        *(o.get("aliases") or []),
                    ]
                    t["mentions"] = [*t.get("mentions", []), *o.get("mentions", [])]
                    into[owner] = tgt
                    rec["merges"].append({"into": tgt, "merged": owner, "merged_name": o["canonical_name"],
                                          "rule": rule, "evidence": ev})  # fmt: skip
                    for kk, vv in list(by_key.items()):
                        if vv == owner:
                            by_key[kk] = tgt
                t = by_id[tgt]
                have = {r1_key(x, _CFG) for x in [t["canonical_name"], *(t.get("aliases") or [])]}
                if rule == "R-acr":
                    have = {x.lower() for x in [t["canonical_name"], *(t.get("aliases") or [])]}
                    k = alias.lower()
                if k not in have:
                    t["aliases"] = [*(t.get("aliases") or []), alias]
                    by_key.setdefault(r1_key(alias, _CFG), tgt)
                    rec["aliases"].append(
                        {"node": tgt, "alias": alias, "rule": rule, "evidence": ev}
                    )
    cp["concepts"] = [c for c in concepts if c["concept_id"] not in into]
    for c in cp["concepts"]:  # aliases unique, never the node's own name
        seen, keep = {c["canonical_name"].lower()}, []
        for a in c.get("aliases") or []:
            if a.lower() not in seen:
                seen.add(a.lower())
                keep.append(a)
        c["aliases"] = keep
    if into:
        _remap_edges(cp, root, into, symmetric, rec)
    cp.setdefault("selection_stats", {})["span_identity"] = {
        "variant": v.name, "aliases": len(rec["aliases"]), "merges": len(rec["merges"]),
        "edges_dropped": len(rec["edges_dropped"]),
    }  # fmt: skip
    return cp, rec


def _remap_edges(cp: dict, root, into: dict, symmetric: frozenset[str], rec: dict) -> None:
    """Only what a merge creates is dropped: a pre-existing duplicate or self-loop stays as it was."""
    seen: dict[tuple, int] = {}
    orig_key: dict[int, tuple] = {}

    def ekey(s: str, t: str, rel: str) -> tuple:
        return (*sorted((s, t)), rel) if rel in symmetric else (s, t, rel)

    for i, r in enumerate(cp.get("relation_results_v3") or []):
        p = r["pair"]
        moved = p["concept_x_id"] in into or p["concept_y_id"] in into
        x0, y0 = p["concept_x_id"], p["concept_y_id"]
        for side in ("concept_x_id", "concept_y_id"):
            if p[side] in into:
                p[side] = root(p[side])
        if (
            r.get("outcome") != "edge"
            or r.get("group", "selected") != "selected"
            or r.get("consolidated_into")
        ):
            continue
        x, y = p["concept_x_id"], p["concept_y_id"]
        s, t = (y, x) if r.get("direction") == "reversed" else (x, y)
        s0, t0 = (y0, x0) if r.get("direction") == "reversed" else (x0, y0)
        orig_key[i] = ekey(s0, t0, r["relation"])
        if s == t and moved:
            r["consolidated_into"] = "cr060:self_loop_after_merge"
            rec["edges_dropped"].append({"row": i, "reason": "self_loop_after_merge"})
            continue
        key = ekey(s, t, r["relation"])
        if key in seen and orig_key[seen[key]] != orig_key[i]:
            r["consolidated_into"] = f"cr060:duplicate_of_row_{seen[key]}"
            rec["edges_dropped"].append({"row": i, "reason": "duplicate_after_merge"})
            continue
        seen[key] = i
    for side in ("selected_pairs",):
        for p in cp.get(side) or []:
            if isinstance(p, dict):
                for k in ("concept_x_id", "concept_y_id"):
                    if p.get(k) in into:
                        p[k] = root(p[k])
