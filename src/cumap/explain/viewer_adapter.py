"""CR-013 viewer adapter: the BUILT derived trace -> one compact JSON payload for the offline KG explorer (`DATA.trace`). Read-only; production payload only
(no gold, no scorer output). The explorer renders text from the same templates (`render.T`) in JavaScript, and a parity test proves the JS text equals the Python text.

Replayed pool pairs are not stored as events: they are stored as arrays and the explorer synthesises the same two events from them (`pool_event_fields`)."""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

from cumap.config import REPO_ROOT
from cumap.explain import render as R
from cumap.explain.lineage import Lineage, resolve
from cumap.explain.trace import STAGES, TraceStore
from cumap.explain.why_not import (
    CHECK_LABELS,
    CODE_TEXT,
    RANK_SENTENCE,
    REASON_SENTENCE,
    pair_index,
    why_not,
)

ROOT = REPO_ROOT / "data/processed/explainability"
STAGE_ORDER = {s: i for i, s in enumerate(STAGES)}
POOL_ACTIONS = {"pool_pair_replayed", "rank_replayed"}
STAGE_MATTERS = {
    "source": "Everything downstream is read from this text; a concept or relation the text does not support cannot enter the graph.",
    "generator": "A concept the generator never proposes cannot reach any later stage (failure code N0 in evaluation).",
    "verifier": "Candidates rejected here never reach canonicalisation or pairing; corrections here change what later stages see.",
    "correction": "Repairs keep a candidate alive; a failed repair removes it.",
    "pruner": "A pruned candidate is never shown to later stages. In this run nothing was pruned.",
    "canonicalisation": "Merging decides which names are one concept, so it decides which pairs exist; a wrong merge or split changes the graph downstream.",
    "pair_generation": "Only eligible pairs can be classified; a concept pair that is not eligible can never become an edge.",
    "pair_selection": "Only selected pairs are sent to the classifier; an eligible pair left out is a loss at this stage (failure code P0 in evaluation).",
    "relation_classification": "The classifier decides whether the sentence states a registry relation and in which direction; no accepted relation means no edge.",
    "validation": "Validation can still reject a proposed relation (grounding, domain/range); only validated relations become edges.",
    "graph_commit": "Only committed concepts and edges appear in the final graph.",
    "organisation": "Organisation is a structural view of the finished graph; it never changes which edges exist.",
}


def latest(run: str = "slice3_c2") -> Path | None:
    ms = list((ROOT / run).glob("*/manifest.json"))
    return max(ms, key=lambda p: p.stat().st_mtime).parent if ms else None


def pool_event_fields(row: list, sec_ids: list[str], eligible: int, budget: int, kind: str) -> dict:
    """Event dict (same keys as `TraceEvent.get` paths) for a replayed pool pair row [pair_id, x, y, rank, selected, section_idx, cue, cooc, sec_rank, sec_pool]. Used by the
    adapter's tests and mirrored in JS."""
    pid, x, y, rank, sel, si, cue, cooc, sr, sp = row
    base = {
        "stage": "pair_generation" if kind == "gen" else "pair_selection",
        "object_id": f"pair:{pid}",
        "section_id": sec_ids[si],
        "layer": "REPLAYED",
        "authority": "SCORE",
        "score": float(cue),
        "eligible_count": eligible,
        "budget": budget,
    }
    if kind == "gen":
        return {
            **base,
            "action": "pool_pair_replayed",
            "outcome": "emitted",
            "attrs": {"cooccurrence_count": cooc, "section_pool": sp, "section_rank": sr},
        }
    return {
        **base,
        "action": "rank_replayed",
        "outcome": "selected" if sel else "not_selected",
        "rank": rank,
        "input_refs": [f"concept:{x}", f"concept:{y}"],
        "attrs": {"section_rank": sr, "section_pool": sp},
    }


def _pool_eid(store: TraceStore, pair_id: str, stage: str, action: str) -> str:
    for e in store.for_object(f"pair:{pair_id}", stage, "REPLAYED"):
        if e.action == action:
            return e.event_id[3:]
    return ""


def compact(e, art_idx: dict[str, int]) -> dict:
    d = e.model_dump()
    for k in ("run_id", "dataset_mode", "document_id"):
        d.pop(k)
    d["art"] = art_idx.setdefault(d.pop("source_artifact"), len(art_idx))
    d["loc"] = d.pop("source_locator")
    a = dict(d.get("attrs") or {})
    a.pop("sentence", None)  # the sentence is reachable through the evidence ref
    if "calls" in a:
        a["calls"] = [
            {
                "task": v.get("task"),
                "hash": v.get("hash"),
                "model": v.get("model"),
                "pv": v.get("prompt_version"),
            }
            for v in a["calls"].values()
        ]
    d["attrs"] = a
    return {k: v for k, v in d.items() if v not in (None, [], {})}


def build_trace_payload(explain_dir: Path | None = None, run: str = "slice3_c2") -> dict | None:
    d = explain_dir or latest(run)
    if d is None:
        return None
    store = TraceStore.from_jsonl(d / "trace_events.jsonl")
    man = json.loads((d / "manifest.json").read_text())
    lin_recs = {
        r["object_id"]: r
        for r in (
            json.loads(x)
            for x in (d / "object_lineage.jsonl").read_text().splitlines()
            if x.strip()
        )
    }
    gaps = [json.loads(x) for x in (d / "trace_gaps.jsonl").read_text().splitlines() if x.strip()]
    pool_rows = (
        [json.loads(x) for x in (d / "replay_pool.jsonl").read_text().splitlines() if x.strip()]
        if (d / "replay_pool.jsonl").exists()
        else []
    )
    rep = man["replay"]
    sections_src = REPO_ROOT / "data/interim/textbook_sections.jsonl"
    secs_all = {
        r["section_id"]: r
        for r in (
            json.loads(x)
            for x in sections_src.read_text(encoding="utf-8").splitlines()
            if x.strip()
        )
    }
    base_ids = sorted(
        {
            (e.section_id or "")
            for e in store.events.values()
            if e.section_id and e.section_id in secs_all
        }
    )
    sec_idx = {s: i for i, s in enumerate(base_ids)}
    # ---- events (the replayed pool is stored as arrays, not as events)
    art: dict[str, int] = {}
    events, eidx, by_obj = [], {}, defaultdict(list)
    for eid in sorted(store.events):
        e = store.events[eid]
        if e.action in POOL_ACTIONS:
            continue
        eidx[eid] = len(events)
        events.append(compact(e, art))
        by_obj[e.object_id].append(eidx[eid])
    pool, pool_ids = [], []
    pool_by_pair: dict[str, int] = {}
    concepts_final = {
        o[8:]: r for o, r in lin_recs.items() if r["final"] and r["object_type"] == "concept"
    }
    for r in pool_rows:
        if r["section_id"] not in sec_idx:
            sec_idx[r["section_id"]] = len(sec_idx)
            base_ids.append(r["section_id"])
        pool_by_pair[r["pair_id"]] = len(pool)
        pool_ids.append(
            [
                _pool_eid(store, r["pair_id"], "pair_generation", "pool_pair_replayed"),
                _pool_eid(store, r["pair_id"], "pair_selection", "rank_replayed"),
            ]
        )
        pool.append(
            [
                r["pair_id"],
                r["concept_x_id"],
                r["concept_y_id"],
                r["global_rank"],
                int(r["selected"]),
                sec_idx[r["section_id"]],
                round(r["cue_score"], 3),
                r["cooccurrence_count"],
                r["section_rank"],
                r["section_pool"],
            ]
        )
    # ---- journeys of final objects (walk back to the evidence; events in pipeline order)
    lin = Lineage([], {}, {})
    del lin
    links = []
    for o, r in lin_recs.items():
        for p in r["parents"]:
            links.append(
                {
                    "child": o,
                    "parent": p["id"],
                    "link": p["link"],
                    "layer": p["layer"],
                    "join": p["join"],
                }
            )
    L = Lineage(
        links,
        {o: r["object_type"] for o, r in lin_recs.items() if r["final"]},
        {o: r["evidence_refs"] for o, r in lin_recs.items() if r["evidence_refs"]},
    )
    journeys = {}
    for o, r in lin_recs.items():
        if not r["final"]:
            continue
        tb = L.trace_back(o)
        evs = sorted(
            {i for n in tb["nodes"] for i in by_obj.get(n, [])},
            key=lambda i: (STAGE_ORDER[events[i]["stage"]], i),
        )
        pairs = [n[5:] for n in tb["nodes"] if n.startswith("pair:") and n[5:] in pool_by_pair]
        journeys[o] = {
            "ev": evs,
            "pairs": pairs,
            "evid": [[ref, str(resolve(ref))[:400]] for ref in tb["evidence"][:12]],
            "nodes": len(tb["nodes"]),
        }
    # ---- per-section data
    final_edges = {
        o[5:]: r for o, r in lin_recs.items() if r["final"] and r["object_type"] == "edge"
    }
    sec = {
        s: {
            "id": s,
            "title": secs_all[s].get("section_title", s),
            "chapter": secs_all[s].get("chapter_num"),
            "text": " ".join(secs_all[s]["text"].split()),
            "funnel": Counter(),
            "ev": [],
            "pairs": [],
            "rows": [],
            "concepts": set(),
            "edges": [],
        }
        for s in base_ids
        if s in secs_all
    }
    for i, e in enumerate(events):
        s = (e.get("section_id") or "").split("#")[0]
        if s in sec:
            sec[s]["ev"].append(i)
            st, ac, oc = e["stage"], e["action"].split(":")[0], e["outcome"]
            sec[s]["funnel"][f"{st}|{ac}|{oc}"] += 1
            if st == "generator" and ac == "mention_recorded":
                pass
    # concept membership: concept -> sections through its v4 nodes' mention events
    v4_to_concept = {}
    for o, r in lin_recs.items():
        if o.startswith("concept:"):
            for p in r["parents"]:
                if p["id"].startswith("v4node:") and p["layer"] == "JOINED":
                    v4_to_concept[p["id"]] = o[8:]
    for i, e in enumerate(events):
        if e["stage"] == "generator" and e["action"] == "mention_recorded":
            s = e.get("section_id", "")
            nid = [r for r in e.get("output_refs", []) if r.startswith("v4node:")]
            c = v4_to_concept.get(nid[0]) if nid else None
            if c and s in sec:
                sec[s]["concepts"].add(c)
    for row in pool:
        s = base_ids[row[5]]
        if s in sec:
            sec[s]["pairs"].append(pool_by_pair[row[0]])
    for o, idxs in by_obj.items():
        if o.startswith("relrow:"):
            first = events[idxs[0]]
            s = (first.get("section_id") or "").split("#")[0]
            if s in sec:
                sec[s]["rows"].append(o)
    for eid, r in final_edges.items():
        s = (
            events[by_obj[f"edge:{eid}"][0]].get("section_id")
            if by_obj.get(f"edge:{eid}")
            else None
        )
        if s in sec:
            sec[s]["edges"].append(eid)
    # mentions (with their evidence text), proposed concepts and relation rows per section
    ev_pos = {id(e): i for i, e in enumerate(events)}
    for i, e in enumerate(events):
        s0 = (e.get("section_id") or "").split("#")[0]
        if s0 not in sec:
            continue
        if e["stage"] == "generator" and e["action"] == "mention_recorded":
            nid = [r for r in e.get("output_refs", []) if r.startswith("v4node:")]
            ev_text = resolve(e["evidence_refs"][0]) if e.get("evidence_refs") else None
            sec[s0].setdefault("mentions", []).append(
                [
                    e["attrs"].get("surface"),
                    e["attrs"].get("role"),
                    ev_text,
                    v4_to_concept.get(nid[0]) if nid else None,
                ]
            )
        elif e["stage"] == "generator" and e["action"] == "proposed":
            sec[s0].setdefault("proposed", []).append(
                [
                    e["object_id"][7:],
                    e["attrs"].get("name"),
                    e["attrs"].get("node_type"),
                    e["attrs"].get("recorded_reason"),
                    v4_to_concept.get(e["object_id"]),
                    i,
                ]
            )
    for o, idxs in by_obj.items():
        if not o.startswith("relrow:"):
            continue
        cls = next(
            (events[i] for i in idxs if events[i]["stage"] == "relation_classification"), None
        )
        if not cls:
            continue
        val = next((events[i] for i in idxs if events[i]["stage"] == "validation"), None)
        s0 = (cls.get("section_id") or "").split("#")[0]
        pid = cls["input_refs"][0][5:]
        pe = [
            events[i]
            for i in by_obj.get(f"pair:{pid}", [])
            if len(events[i].get("input_refs", [])) == 2
        ]
        if pid in pool_by_pair:
            x, y = pool[pool_by_pair[pid]][1], pool[pool_by_pair[pid]][2]
        elif pe:
            x, y = pe[0]["input_refs"][0][8:], pe[0]["input_refs"][1][8:]
        else:
            x = y = None
        rec = {"r": o, "p": pid, "x": x, "y": y, "o": cls["outcome"], "rel": cls["attrs"].get("relation"), "d": cls["attrs"].get("direction"), "f": cls["attrs"].get("family"), "rc": cls.get("reason_code"),
               "vo": val["outcome"] if val else None, "vr": val.get("reason_code") if val else None, "ev": ev_pos[id(cls)], "ce": pid if (pid in final_edges and o.endswith(":0")) else None, "g": cls["attrs"].get("group")}  # fmt: skip
        if s0 in sec:
            sec[s0].setdefault("rowrecs", []).append(rec)
    # local layouts: concepts of the section plus endpoints of its rows
    ends: dict[str, set] = defaultdict(set)
    for o in [x for ss in sec.values() for x in ss["rows"]]:
        ev0 = events[by_obj[o][0]]
        refs = [x for x in ev0.get("input_refs", [])]
        pair = refs[0][5:] if refs and refs[0].startswith("pair:") else None
        if pair:
            for ln in lin_recs.get(f"pair:{pair}", {"parents": []})["parents"]:
                if ln["id"].startswith("concept:"):
                    ends[(ev0.get("section_id") or "").split("#")[0]].add(ln["id"][8:])
    layouts = {}
    for s, ss in sec.items():
        nodes = sorted(ss["concepts"] | ends.get(s, set()))
        g = nx.Graph()
        g.add_nodes_from(nodes)
        for o in ss["rows"]:
            ev0 = events[by_obj[o][0]]
            pair = ev0["input_refs"][0][5:] if ev0.get("input_refs") else None
            xy = (
                [
                    ln["id"][8:]
                    for ln in lin_recs.get(f"pair:{pair}", {"parents": []})["parents"]
                    if ln["id"].startswith("concept:")
                ]
                if pair
                else []
            )
            if len(xy) == 2 and all(n in g for n in xy):
                g.add_edge(*xy)
        for pi in ss[
            "pairs"
        ]:  # selected pool pairs also connect nodes (they are what the classifier saw)
            if pool[pi][4] and pool[pi][1] in g and pool[pi][2] in g:
                g.add_edge(pool[pi][1], pool[pi][2])
        linked = [n for n in nodes if g.degree(n) > 0]
        isolated = [n for n in nodes if g.degree(n) == 0]
        core = g.subgraph(linked)
        pos = {}
        comps = sorted(
            (sorted(c) for c in nx.connected_components(core)), key=lambda c: (-len(c), c[0])
        )
        small = comps[1:]
        cols = max(1, math.ceil(math.sqrt(len(small) * 1.6)))
        for ci, comp in enumerate(
            comps
        ):  # the largest component gets its own big tile; the others are tiled beside it
            sub = core.subgraph(comp)
            if len(comp) == 1:
                local = {comp[0]: (0.0, 0.0)}
            elif len(comp) == 2:
                local = {comp[0]: (-0.5, 0.0), comp[1]: (0.5, 0.0)}
            else:
                local = nx.kamada_kawai_layout(sub, scale=1.0)
            if ci == 0:
                cx, cy, sz = 0.0, 0.0, 1.0
            else:
                k = ci - 1
                cx, cy, sz = (
                    3.0 + (k % cols) * 0.95,
                    (k // cols) * 0.95 - (len(small) // cols) * 0.4,
                    0.28,
                )
            for n, (x, y) in local.items():
                pos[n] = (cx + float(x) * sz, cy + float(y) * sz)
        if pos:
            xs, ys = [v[0] for v in pos.values()], [v[1] for v in pos.values()]
            mx, my, sc = (
                (max(xs) + min(xs)) / 2,
                (max(ys) + min(ys)) / 2,
                max(max(xs) - min(xs), max(ys) - min(ys), 1e-9) / 2,
            )
            pos = {n: ((x - mx) / sc * 0.82, (y - my) / sc * 0.82) for n, (x, y) in pos.items()}
        for i, n in enumerate(
            isolated
        ):  # concepts with no pair in this section sit on an outer ring
            ang = 2 * math.pi * i / max(len(isolated), 1)
            pos[n] = (1.0 * math.cos(ang), 1.0 * math.sin(ang))
        layouts[s] = {n: [round(float(p[0]), 3), round(float(p[1]), 3)] for n, p in pos.items()}
        ss["concepts"] = nodes
        ss["funnel"] = dict(ss["funnel"])
    # ---- Why not? for every indexed pair (single source of truth: why_not.py)
    idx = pair_index(store)
    why = {}
    ans = {
        "yes": "y",
        "no": "n",
        "unknown": "u",
        "not_assessed_in_production": "i",
        "relation_proposed": "p",
        "no_relation": "r",
    }
    for key in idx:
        a, b = sorted(key)
        r = why_not(store, a, b, idx)
        last = r["checks"][-1]["fields"] if r["checks"] else {}
        # compact: [earliest code, status, one letter per executed check, rank, eligible_count, budget, rank_layer, reason_code]
        why[f"{a[8:]}|{b[8:]}"] = [
            r["earliest_failure"] or "",
            r["status"],
            "".join(ans[c["answer"]] for c in r["checks"]),
            last.get("rank"),
            last.get("eligible_count"),
            last.get("budget"),
            last.get("rank_layer"),
            last.get("reason_code"),
        ]
    return {
        "meta": {
            "run": man["source_run_id"],
            "explain_id": man["explain_id"],
            "base_commit": man["base_commit"],
            "renderer_version": man["renderer_version"],
            "schema": man["trace_schema_version"],
            "replay": {
                "valid": rep["valid"],
                "deterministic": rep.get("deterministic"),
                "eligible_count": rep.get("eligible_count"),
                "budget": 1100,
            },
            "coverage": {k: v for k, v in man["coverage"].items() if k != "gaps"},
            "counts": man["counts"],
            "source_hashes_unchanged": man["source_hashes_unchanged"],
        },
        "templates": {f"{k[0]}|{k[1]}": v for k, v in R.T.items()},
        "fallback": R.FALLBACK,
        "stage_info": R.STAGE_INFO,
        "stage_matters": STAGE_MATTERS,
        "stages": list(STAGES),
        "code_text": CODE_TEXT,
        "check_labels": CHECK_LABELS,
        "why_sentences": {"rank": RANK_SENTENCE, "reason": REASON_SENTENCE},
        "why_answer_letters": {
            "y": "yes",
            "n": "no",
            "u": "unknown",
            "i": "not_assessed_in_production",
            "p": "relation_proposed",
            "r": "no_relation",
        },
        "artifacts": [a for a, _ in sorted(art.items(), key=lambda kv: kv[1])],
        "events": events,
        "by_obj": {
            k: v
            for k, v in by_obj.items()
            if k.startswith(("concept:", "edge:", "relrow:", "pair:", "v4node:", "community:"))
        },
        "pool": pool,
        "pool_ids": pool_ids,
        "pool_sections": base_ids,
        "journeys": journeys,
        "sections": sec,
        "layouts": layouts,
        "why": why,
        "gaps": gaps,
        "final_concepts": sorted(concepts_final),
        "final_edges": sorted(final_edges),
        "eligible": rep.get("eligible_count"),
    }


def payload_size(p: dict) -> dict:
    return {k: len(json.dumps(v, separators=(",", ":"), default=list)) for k, v in p.items()}


__all__ = ["build_trace_payload", "latest", "payload_size", "pool_event_fields"]
_ = re
