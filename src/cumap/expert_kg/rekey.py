"""CR-008 §4: re-key a finished run under the R0-R3 merge rules and registry v1.3 ($0, no API call).

Merged nodes collapse into one survivor; every id-bearing record (relation results, selected pairs,
merges, review/taxonomy candidates) is re-keyed to the survivor. Nothing is deleted: pre-merge ids
stay in `merged_from`, merged-away edges stay in the run data (flagged `consolidated_into`, or
rejected with a reason). `equivalent_to` edges are migrated: merged by a rule, retired, or sent to
the owner sheet as an `equivalence_migration` item. Edge consolidation keeps every evidence quote.
"""

from __future__ import annotations

import copy
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from cumap.expert_kg.alias_rules import r1_key, split_embedded_acronym
from cumap.expert_kg.canonical_rules import AliasContext, types_compatible
from cumap.expert_kg.canonicalize import RegisteredConcept
from cumap.expert_kg.mentions import MentionMatcher
from cumap.expert_kg.relations import concept_vocab
from cumap.expert_kg.roles import SectionText, apply_first_occurrence, apply_role_rules
from cumap.schemas.relations import EdgeRef, RelationRegistry

RULE_ORDER = {"R0": 0, "R1": 1, "R2": 2, "R3-strong": 3}


@dataclass
class MergeRecord:
    from_id: str
    into_id: str
    rule_id: str
    surface_forms: tuple[str, str]
    section_id: str | None
    evidence_quote: str

    def to_dict(self) -> dict:
        return {**self.__dict__, "surface_forms": list(self.surface_forms)}


@dataclass
class RekeyResult:
    checkpoint: dict
    report: dict = field(default_factory=dict)
    merge_records: list[MergeRecord] = field(default_factory=list)


# ---------------------------------------------------------------- clustering
def _forms(c: dict) -> list[str]:
    return [c["canonical_name"], *c.get("aliases", [])]


def _candidate_pairs(concepts: list[dict], ctx: AliasContext) -> set[tuple[int, int]]:
    """Index-based candidate generation (no O(n^2) rule calls): pairs sharing any rule key."""
    cfg, lex = ctx.cfg, ctx.lexicon
    idx: dict[str, set[int]] = defaultdict(set)
    keys_of: list[set[str]] = []
    for i, c in enumerate(concepts):
        ks: set[str] = set()
        for f in _forms(c):
            ks.add("k:" + r1_key(f, cfg))
            if (rep := lex.same_set(f)) is not None:
                ks.add("s:" + rep)
            if sp := split_embedded_acronym(f, cfg):
                ks.update("k:" + r1_key(x, cfg) for x in sp)
        keys_of.append(ks)
        for k in ks:
            idx[k].add(i)
    partners: dict[str, set[str]] = defaultdict(set)
    for pair in [*ctx.abbrev, *ctx.strong]:
        for k in pair:
            partners[k].update(x for x in pair if x != k)
    out: set[tuple[int, int]] = set()
    for i, ks in enumerate(keys_of):
        probe = set(ks)
        for k in ks:
            if k.startswith("k:"):
                probe.update("k:" + p for p in partners.get(k[2:], ()))
        for k in probe:
            for j in idx.get(k, ()):
                if j != i:
                    out.add((min(i, j), max(i, j)))
    return out


def plan_merges(
    concepts: list[dict], ctx: AliasContext, chapter_of_concept: dict[str, int]
) -> tuple[dict[str, str], list[MergeRecord], Counter]:
    """-> (concept_id -> cluster representative id, one MergeRecord per merged-away concept, stats)."""
    lex = ctx.lexicon
    stats: Counter = Counter()
    cands: list[tuple[int, str, str, int, int, object]] = []
    for i, j in sorted(_candidate_pairs(concepts, ctx)):
        a, b = concepts[i], concepts[j]
        best = None
        for fa in _forms(a):
            for fb in _forms(b):
                hit = ctx.pair_rule(
                    fa,
                    fb,
                    chapter_of_concept.get(b["concept_id"]),
                    a_type=a["node_type"],
                    b_type=b["node_type"],
                    type_aware=True,
                )
                if hit and (best is None or RULE_ORDER[hit.rule_id] < RULE_ORDER[best.rule_id]):
                    best = hit
        if best:
            cands.append((RULE_ORDER[best.rule_id], a["concept_id"], b["concept_id"], i, j, best))
    cands.sort(key=lambda t: t[:5])

    cluster: dict[str, set[str]] = {c["concept_id"]: {c["concept_id"]} for c in concepts}
    by_id = {c["concept_id"]: c for c in concepts}
    records: list[MergeRecord] = []
    for _, ida, idb, _i, _j, hit in cands:
        ca, cb = cluster[ida], cluster[idb]
        if ca is cb:
            continue
        blocked = any(
            lex.is_different(fa, fb)
            for x in ca
            for y in cb
            for fa in _forms(by_id[x])
            for fb in _forms(by_id[y])
        )
        if blocked:
            stats["blocked_by_lexicon_chain"] += 1
            continue
        into, frm = (ida, idb)
        sec = by_id[frm]["first_introduced"]
        records.append(
            MergeRecord(
                frm, into, hit.rule_id, hit.surface_forms, hit.section_id or sec, hit.evidence_quote
            )
        )
        merged = ca | cb
        for x in merged:
            cluster[x] = merged
    rep: dict[str, str] = {}
    for c in concepts:
        members = cluster[c["concept_id"]]
        rep[c["concept_id"]] = min(members)  # provisional; the survivor is chosen in apply_rekey
    return rep, records, stats


# ---------------------------------------------------------------- merging nodes
def _to_reg(d: dict) -> RegisteredConcept:
    from cumap.expert_kg.pipeline import _concept_from_dict

    return _concept_from_dict(d)


def _from_reg(c: RegisteredConcept) -> dict:
    from cumap.expert_kg.pipeline import _concept_to_dict

    return _concept_to_dict(c)


def _survivor(members: list[dict], order: dict[str, int]) -> dict:
    def key(c: dict):
        defined = [
            order.get(m["section_id"], 10**9) for m in c["mentions"] if m["role"] == "defined"
        ]
        return (
            min(defined) if defined else 10**9,
            -len(c["mentions"]),
            order.get(c["first_introduced"], 10**9),
            c["concept_id"],
        )

    return min(members, key=key)


def merge_nodes(
    concepts: list[dict],
    groups: list[list[str]],
    records: list[MergeRecord],
    order: dict[str, int],
    ctx: AliasContext,
) -> tuple[list[dict], dict[str, str]]:
    """Collapse each group into its survivor. Returns (concepts, old id -> surviving id)."""
    by_id = {c["concept_id"]: c for c in concepts}
    rec_for = {r.from_id: r for r in records}
    id_map = {c["concept_id"]: c["concept_id"] for c in concepts}
    out: list[dict] = []
    in_group = {cid for g in groups for cid in g}
    for g in groups:
        members = [by_id[i] for i in g]
        s = copy.deepcopy(_survivor(members, order))
        merged_from, alias_prov = [], {}
        for m in members:
            if m["concept_id"] == s["concept_id"]:
                continue
            merged_from.append(m["concept_id"])
            id_map[m["concept_id"]] = s["concept_id"]
            rec = rec_for.get(m["concept_id"]) or next(
                (r for r in records if m["concept_id"] in (r.from_id, r.into_id)), None
            )
            for f in _forms(m):
                alias_prov.setdefault(
                    f,
                    {
                        "form": f,
                        "rule_id": rec.rule_id if rec else "R1",
                        "section_id": rec.section_id if rec else m["first_introduced"],
                        "evidence_quote": rec.evidence_quote if rec else f,
                        "from_id": m["concept_id"],
                    },
                )
            s["mentions"] = [*s["mentions"], *copy.deepcopy(m["mentions"])]
            s["description_history"] = [
                *s.get("description_history", []),
                *m.get("description_history", []),
            ]
            if not s.get("definition") and m.get("definition"):
                s["definition"] = m["definition"]
        # R2: the survivor's own name may embed an acronym ("X (SF)"): canonical = long form
        if sp := split_embedded_acronym(s["canonical_name"], ctx.cfg):
            alias_prov.setdefault(
                sp[1],
                {
                    "form": sp[1],
                    "rule_id": "R2",
                    "section_id": s["first_introduced"],
                    "evidence_quote": s["canonical_name"],
                    "from_id": s["concept_id"],
                },
            )
            s["canonical_name"] = sp[0]
        forms: list[str] = []
        for f in [*s.get("aliases", []), *alias_prov]:
            if sp := split_embedded_acronym(f, ctx.cfg):
                alias_prov.setdefault(
                    sp[1],
                    {
                        "form": sp[1],
                        "rule_id": "R2",
                        "section_id": s["first_introduced"],
                        "evidence_quote": f,
                        "from_id": s["concept_id"],
                    },
                )
                f = sp[0]
            if f != s["canonical_name"] and f not in forms:
                forms.append(f)
        for f in list(alias_prov):
            if f not in forms and f != s["canonical_name"]:
                forms.append(f)
        # dedupe mentions
        seen, ms = set(), []
        for m in s["mentions"]:
            k = (m["section_id"], m["quote"], m["role"])
            if k not in seen:
                seen.add(k)
                ms.append(m)
        s["mentions"], s["aliases"] = ms, [f for f in forms if f != s["canonical_name"]]
        s["merged_from"], s["alias_provenance"] = merged_from, list(alias_prov.values())
        reg = _to_reg(s)
        apply_role_rules(reg, order)
        d = _from_reg(reg)
        d["merged_from"], d["alias_provenance"] = merged_from, list(alias_prov.values())
        out.append(d)
    for c in concepts:
        if c["concept_id"] not in in_group:
            out.append(c)
    return out, id_map


# ---------------------------------------------------------------- edges
def _edge_key(r: dict, registry: RelationRegistry, x: str, y: str) -> tuple:
    src, tgt = (y, x) if r["direction"] == "reversed" else (x, y)
    ref = registry.normalise(EdgeRef(src, r["relation"], tgt))
    rel = registry.get(ref.relation)
    pair = (
        tuple(sorted((ref.source_id, ref.target_id)))
        if rel.symmetric
        else (ref.source_id, ref.target_id)
    )
    return (ref.relation, *pair)


def rekey_results(
    cp: dict,
    id_map: dict[str, str],
    by_new: dict[str, dict],
    registry: RelationRegistry,
    ctx: AliasContext,
    merged_pairs: dict[frozenset[str], str],
) -> dict:
    """Re-key selected pairs and relation results; consolidate edges; migrate equivalent_to."""
    log: dict = defaultdict(list)
    cnt: Counter = Counter()
    for key in ("selected_pairs", "sample_pairs"):
        for p in cp[key]:
            p["concept_x_id"], p["concept_y_id"] = (
                id_map.get(p["concept_x_id"], p["concept_x_id"]),
                id_map.get(p["concept_y_id"], p["concept_y_id"]),
            )
    results = cp["relation_results_v3"]
    for r in results:
        pr = r["pair"]
        pr["concept_x_id"], pr["concept_y_id"] = (
            id_map.get(pr["concept_x_id"], pr["concept_x_id"]),
            id_map.get(pr["concept_y_id"], pr["concept_y_id"]),
        )
    primary: dict[tuple, dict] = {}
    for r in results:
        x, y = r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]
        if r["outcome"] == "edge" and r.get("gated_dropped"):
            continue
        if x == y:
            if r["outcome"] == "edge" and r["relation"] == "equivalent_to":
                cnt["equivalent_to_seen"] += 1
                cnt["equiv_merged_by_rule"] += 1
                name = by_new[x]["canonical_name"]
                log["equivalence"].append(
                    {
                        "pair_id": r["pair"]["pair_id"],
                        "x": name,
                        "y": name,
                        "x_id": x,
                        "y_id": x,
                        "section_id": r["pair"]["section_id"],
                        "quote": r["evidence_quote"],
                        "migration": "merged_by_rule",
                    }
                )
                r["outcome"], r["reason"] = "rejected", "equivalent_to_merged"
            elif r["outcome"] == "edge":
                cnt["merge_self_loop"] += 1
                log["self_loops"].append(
                    {
                        "pair_id": r["pair"]["pair_id"],
                        "relation": r["relation"],
                        "node": x,
                        "quote": r["evidence_quote"],
                    }
                )
                r["outcome"], r["reason"] = "rejected", "merge_self_loop"
                r["merge_self_loop_relation"] = r["relation"]
            r["self_pair"] = True
            continue
        if r["outcome"] != "edge":
            continue
        if r["relation"] == "equivalent_to":
            cnt["equivalent_to_seen"] += 1
            nx, ny = by_new[x]["canonical_name"], by_new[y]["canonical_name"]
            item = {
                "pair_id": r["pair"]["pair_id"],
                "x": nx,
                "y": ny,
                "x_id": x,
                "y_id": y,
                "section_id": r["pair"]["section_id"],
                "quote": r["evidence_quote"],
            }
            if lexicon_diff := ctx.lexicon.different_entry(nx, ny):
                item["migration"] = "retired_lexicon_different"
                item["lexicon_entry"] = lexicon_diff.id
                cnt["equiv_retired"] += 1
            else:
                item["migration"] = "owner_sheet"
                cnt["equiv_owner_sheet"] += 1
            r["outcome"], r["reason"] = (
                "rejected",
                "equivalent_to_retired"
                if item["migration"].startswith("retired")
                else "equivalent_to_pending_owner",
            )
            log["equivalence"].append(item)
            continue
        k = _edge_key(r, registry, x, y)
        if k in primary:
            p = primary[k]
            p.setdefault(
                "evidence_all",
                [
                    {
                        "pair_id": p["pair"]["pair_id"],
                        "section_id": p["pair"]["section_id"],
                        "quote": p["evidence_quote"],
                    }
                ],
            ).append(
                {
                    "pair_id": r["pair"]["pair_id"],
                    "section_id": r["pair"]["section_id"],
                    "quote": r["evidence_quote"],
                }
            )
            r["consolidated_into"] = p["pair"]["pair_id"]
            cnt["edges_consolidated"] += 1
        else:
            primary[k] = r
    # one snapshot edge per node pair: further, different edges on the same pair are secondary
    seen_pair: dict[frozenset[str], tuple] = {}
    for k, r in primary.items():
        pk = frozenset((r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]))
        if pk in seen_pair:
            r["snapshot_secondary"] = True
            cnt["secondary_edges_same_pair"] += 1
            log["multi_relation"].append(
                {"pair": sorted(pk), "relations": [seen_pair[pk][0], k[0]]}
            )
        else:
            seen_pair[pk] = k
    log["edge_pairs"] = [[*k] for k in primary]
    cp["relation_results_v3"] = results
    return {"log": dict(log), "counts": dict(cnt), "primary": primary}


def conflicts_after_rekey(
    primary: dict, registry: RelationRegistry, by_new: dict[str, dict]
) -> list[dict]:
    """CR-007 §5.6b detection ($0): node pairs whose consolidated edges carry conflicting relations."""
    by_pair: dict[frozenset[str], list[tuple]] = defaultdict(list)
    for k, r in primary.items():
        by_pair[frozenset((r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]))].append((k[0], r))
    out = []
    for pk, items in by_pair.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                if registry.conflicts(items[i][0], items[j][0]):
                    out.append(
                        {
                            "nodes": [by_new[n]["canonical_name"] for n in sorted(pk)],
                            "relations": [items[i][0], items[j][0]],
                            "quotes": [
                                items[i][1]["evidence_quote"],
                                items[j][1]["evidence_quote"],
                            ],
                        }
                    )
    return out


def structural_cycles(primary: dict, registry: RelationRegistry) -> list[list[str]]:
    refs = [EdgeRef(k[1], k[0], k[2]) for k in primary]
    cycles: list[list[str]] = []
    for rel in ("is_a", "part_of", "encapsulates", "prerequisite_of"):
        if rel in registry:
            cycles.extend(registry.find_cycles(refs, rel))
    return cycles


_DISTINGUISH = re.compile(
    r"\b(unlike|whereas|differs?|different from|not the same|in contrast|distinct\w*|distinguish\w*)\b",
    re.IGNORECASE,
)


def alias_contradictions(
    records: list[MergeRecord],
    id_map: dict[str, str],
    self_loops: list[dict],
    sections: list[SectionText],
) -> list[dict]:
    """CR-008 §3.3: an R3 merge whose two forms the book LATER distinguishes (a `contrasts_with` edge
    that became a self-loop, or a sentence naming both forms with a distinguishing cue)."""
    flags: list[dict] = []
    contrasted = {l["node"] for l in self_loops if l["relation"] == "contrasts_with"}
    for r in records:
        if not r.rule_id.startswith("R3"):
            continue
        node = id_map.get(r.into_id, r.into_id)
        why = None
        if node in contrasted:
            why = "a contrasts_with edge between the two forms became a self-loop"
        a, b = (re.escape(f) for f in r.surface_forms)
        for sec in sections:
            for sent in re.split(r"(?<=[.!?])\s+", sec.text):
                if (
                    re.search(a, sent, re.IGNORECASE)
                    and re.search(b, sent, re.IGNORECASE)
                    and _DISTINGUISH.search(sent)
                    and " ".join(sent.split()) not in r.evidence_quote
                ):
                    why = why or "a sentence names both forms with a distinguishing cue"
                    flags.append(
                        {
                            "forms": list(r.surface_forms),
                            "rule_id": r.rule_id,
                            "why": why,
                            "section_id": sec.section_id,
                            "quote": " ".join(sent.split()),
                        }
                    )
                    break
        if why and not any(f["forms"] == list(r.surface_forms) for f in flags):
            flags.append(
                {
                    "forms": list(r.surface_forms),
                    "rule_id": r.rule_id,
                    "why": why,
                    "section_id": None,
                    "quote": r.evidence_quote,
                }
            )
    return flags


# ---------------------------------------------------------------- orchestration
def rekey_run(
    cp_in: dict,
    ctx: AliasContext,
    registry: RelationRegistry,
    sections: list[SectionText],
    new_run_id: str,
) -> RekeyResult:
    cp = copy.deepcopy(cp_in)
    order = {s.section_id: s.order_index for s in sections}
    chapter_of = {s.section_id: s.chapter_num for s in sections}
    concepts = cp["concepts"]
    chapter_of_concept = {
        c["concept_id"]: chapter_of.get(c["first_introduced"], -1) for c in concepts
    }
    n_before = len(concepts)
    _, records, stats = plan_merges(concepts, ctx, chapter_of_concept)
    # groups = connected components of the accepted merge records
    parent = {c["concept_id"]: c["concept_id"] for c in concepts}

    def find(a: str) -> str:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for r in records:
        parent[find(r.from_id)] = find(r.into_id)
    comp: dict[str, list[str]] = defaultdict(list)
    for cid in parent:
        comp[find(cid)].append(cid)
    groups = [sorted(v) for v in comp.values() if len(v) > 1]
    new_concepts, id_map = merge_nodes(concepts, groups, records, order, ctx)
    by_new = {c["concept_id"]: c for c in new_concepts}

    # first occurrence by longest match (CR-007 §4.2), on the merged vocabulary
    regs = [_to_reg(c) for c in new_concepts]
    chapters = apply_first_occurrence(regs, sections)
    for reg, d in zip(regs, new_concepts, strict=True):
        d["first_introduced"] = reg.first_introduced
    cp["concept_first_chapter"] = {
        **{id_map.get(k, k): v for k, v in cp["concept_first_chapter"].items()},
        **chapters,
    }
    cp["concepts"] = new_concepts

    res = rekey_results(cp, id_map, by_new, registry, ctx, {})
    # merges log: the new rule-based merges, with provenance
    for r in records:
        cp["merges"].append(
            {
                "concept_id": id_map.get(r.into_id, r.into_id),
                "alias": r.surface_forms[1],
                "section_id": r.section_id,
                "llm_called": False,
                "auto_merged": True,
                "overridden": False,
                "reason": None,
                "similarity": None,
                "rule_id": r.rule_id,
                "evidence_quote": r.evidence_quote,
                "stage": "rekey",
            }
        )
    # candidates / review: re-key, drop those that are now one node
    for key, a, b in (
        ("merge_review", "concept_id", "candidate_id"),
        ("taxonomy_candidates", "concept_id", "matched_concept_id"),
        ("related_candidates", "concept_id", "related_concept_id"),
    ):
        kept = []
        for row in cp[key]:
            row[a], row[b] = id_map.get(row[a], row[a]), id_map.get(row[b], row[b])
            if row[a] != row[b]:
                kept.append(row)
        cp[key] = kept
    cp["run_id"] = new_run_id
    alias_flags = alias_contradictions(records, id_map, res["log"].get("self_loops", []), sections)
    conflicts = conflicts_after_rekey(res["primary"], registry, by_new)
    cycles = structural_cycles(res["primary"], registry)
    rule_counts = Counter(r.rule_id for r in records)
    cp_dict = cp
    cp_dict["rekey"] = {
        "source_run": cp_in["run_id"],
        "n_concepts_before": n_before,
        "n_concepts_after": len(new_concepts),
        "merge_records": [r.to_dict() for r in records],
        "id_map": {k: v for k, v in id_map.items() if k != v},
        "guard_stats": {**dict(stats), **dict(ctx.stats)},
        "conflicts": conflicts,
        "cycles": cycles,
        "ambiguous_acronyms": {k: sorted(v) for k, v in ctx.ambiguous_shorts.items()},
        **res["log"],
        "counts": res["counts"],
        "alias_contradicted": alias_flags,
    }
    report = {
        "nodes_before": n_before,
        "nodes_after": len(new_concepts),
        "merges_per_rule": dict(rule_counts),
        "counts": res["counts"],
        "alias_contradicted": len(alias_flags),
        "conflicts": len(conflicts),
        "cycles": len(cycles),
        "guard_stats": cp_dict["rekey"]["guard_stats"],
    }
    return RekeyResult(cp_dict, report, records)


def concept_matcher(concepts: list[dict]) -> MentionMatcher:
    return MentionMatcher(concept_vocab([_to_reg(c) for c in concepts]))


__all__ = ["MergeRecord", "RekeyResult", "rekey_run", "types_compatible"]
