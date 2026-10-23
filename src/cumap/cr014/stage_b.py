"""CR-014 Stage B on IIR dev (13 sections): V0-V3 over the frozen U2 proposal union. Development only; no held-out or sealed P&D data.

    uv run python -m cumap.cr014.stage_b preflight
    uv run python -m cumap.cr014.stage_b run --arms V0 V1 V2 V3 [--limit N] --max-usd X
    uv run python -m cumap.cr014.stage_b report

Gold is read only by `ranker_gate_table` and `evaluate` (development scoring). The verifier, boundary repair and ranker never see it."""

from __future__ import annotations

import argparse
import dataclasses
import json
import pickle
import re
import time
from pathlib import Path

import yaml

from cumap.concepts_v4 import experiments as X
from cumap.concepts_v4.cards import split_paragraphs
from cumap.cr010.nodes_exp import (
    SectionContext,
    baseline_run,
    cards_for,
    load_cfg,
    split_data,
)
from cumap.cr014.llm_stage import (
    Usage,
    render_candidates,
    render_families,
    run_verifier,
)
from cumap.cr014.proposal import norm_surface
from cumap.cr014.union import (
    SectionUnion,
    build_section_union,
    iteration0_surfaces,
)
from cumap.expert_kg.alias_rules import AliasConfig
from cumap.expert_kg.face_scorer import GoldConcept
from cumap.llm.prompts import load_prompt

ROOT = Path(".")
OUT = ROOT / "data/processed/cr014/stageB"
CFG = yaml.safe_load((ROOT / "configs/cr014_concept_extraction.yaml").read_text())
SB = CFG["stage_b"]
DOMAIN = "information retrieval"
ACCEPT = {"ACCEPT_NEW", "LINK_EXISTING"}


# ---------------------------------------------------------------- data
def load_dev(limit: int | None = None):
    import spacy

    nlp = spacy.load("en_core_web_sm")
    sections, emph, gold = split_data("dev")
    out0 = baseline_run("dev", load_cfg())
    sections = [s for s in sections if s["section_id"] in out0.sections]
    sections = sections[:limit] if limit else sections
    return nlp, sections, emph, gold, out0


def unions(nlp, sections, emph, out0) -> dict[str, SectionUnion]:
    path = OUT / f"unions_{len(sections)}.pkl"
    if path.exists():
        return pickle.loads(path.read_bytes())
    cfg = AliasConfig.load()
    us = {}
    for s in sections:
        sid = s["section_id"]
        res = dataclasses.asdict(out0.sections[sid])
        us[sid] = build_section_union(s, emph.get(sid, set()), nlp, cfg, iteration0_surfaces(res))
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(us))
    return us


def existing_matches(out0, sid: str) -> dict[str, list[str]]:
    """Deterministic exact-name/alias matches against nodes shown to the baseline in this section (earlier sections only)."""
    m: dict[str, list[str]] = {}
    for nid in out0.section_meta.get(sid, {}).get("cards_shown", []):
        node = out0.store.nodes.get(nid)
        if node is None:
            continue
        for n in [node.name, *node.aliases]:
            m.setdefault(norm_surface(n), []).append(f"{nid}({node.name})")
    return m


from cumap.cr014.v3_core import (
    SectionOutcome,
    onetoken_scores,
)
from cumap.cr014.v3_core import (
    run_v2 as _run_v2,
)


def run_v2(*a, **k):
    """IIR-dev wrapper: the frozen core with this module's domain string."""
    return _run_v2(*a, domain=DOMAIN, **k)


def run_v1(
    client, prompt, u, heading, matches, usage, only: set[str] | None = None
) -> SectionOutcome:
    out = SectionOutcome()
    cs = [c for c in sorted(u.cands.values(), key=lambda c: c.cid) if only is None or c.cid in only]
    out.n_verified = len(cs)
    vs = run_verifier(client, prompt, u, heading, cs, SB, matches, DOMAIN, usage)
    for c in cs:
        v = vs.get(c.cid)
        out.verdicts[c.cid] = {"surface": c.surface, **(v or {"verdict": "NO_ANSWER"})}
        if v and v["verdict"] in ACCEPT:
            out.accepted[c.surface] = {
                "verdict": v["verdict"],
                "source_cids": [c.cid],
                "node_id": v["node_id"],
            }
    return out


def run_v0(u, sec, ctx, cards, pruner, tau) -> SectionOutcome:
    """V0 = the production rule verifier then the production pruner, applied to the frozen U2 union (candidates cast as generator items
    whose evidence is the first sentence containing them). Reported as a measured arm, not a faithful re-run of the production loop."""
    from cumap.concepts_v4.verifier import drop_flagged, verify

    out = SectionOutcome()
    paras = split_paragraphs(sec["text"])
    items = []
    for c in sorted(u.cands.values(), key=lambda c: c.cid):
        _a, _b, si = c.occurrences[0]
        s0, s1 = u.sents[si]
        evidence = re.sub(r"\s+", " ", u.text[s0:s1]).strip()
        para = next(
            (k for k, v in paras.items() if evidence and evidence in re.sub(r"\s+", " ", v)), None
        )
        if para is None:
            continue
        items.append(
            {"name": c.surface, "aliases": [], "node_type": "Concept", "role": "used", "evidence": evidence,
             "para": para, "extraction_origin": "independent", "anchors": [], "independence_check": "n/a",
             "found_via_anchor": False}
        )  # fmt: skip
    vr = verify(
        {"existing_mentions": [], "not_mentions": [], "new_concepts": items, "hint_responses": []},
        ctx,
    )
    kept, dropped = drop_flagged(vr.out, vr.flags)
    out.n_verified = len(items)
    flagged = (
        {d["name"] for d in dropped if "name" in d}
        if dropped and isinstance(dropped[0], dict)
        else set()
    )
    for it in kept["new_concepts"]:
        p = pruner(it["name"])
        if p >= tau:
            out.accepted[norm_surface(it["name"])] = {
                "verdict": "RULES_AND_PRUNER",
                "p_growing": round(p, 4),
            }
        else:
            out.verdicts[it["name"]] = {"verdict": "PRUNED", "p": round(p, 4)}
    out.verdicts["_rule_flag_counts"] = {
        "flags": dict(__import__("collections").Counter(f.rule for f in vr.flags))
    }
    out.verdicts["_dropped_by_rules"] = {
        "n": len(items) - len(kept["new_concepts"]),
        "flagged_names": sorted(flagged)[:0],
    }
    return out


# ---------------------------------------------------------------- preflight ($0)
def est_tokens(s: str) -> int:
    return max(1, len(s) // 4)


def preflight(limit: int | None = None) -> dict:
    nlp, sections, emph, _gold, out0 = load_dev(limit)
    us = unions(nlp, sections, emph, out0)
    pv = load_prompt(
        ROOT / "prompts",
        task=SB["verifier_prompt"]["task"],
        version=SB["verifier_prompt"]["version"],
    )
    pb = load_prompt(
        ROOT / "prompts",
        task=SB["boundary_prompt"]["task"],
        version=SB["boundary_prompt"]["version"],
    )
    tin_v = tin_b = nv = nb = 0
    cands = fams = multi = 0
    for sid, u in us.items():
        heading = next(s for s in sections if s["section_id"] == sid).get("heading") or sid
        m = existing_matches(out0, sid)
        cs = sorted(u.cands.values(), key=lambda c: c.cid)
        cands += len(cs)
        fams += len(u.families)
        for i in range(0, len(cs), SB["batch_candidates"]):
            tin_v += est_tokens(
                pv.render(
                    domain=DOMAIN,
                    heading_path=heading,
                    candidates=render_candidates(u, cs[i : i + SB["batch_candidates"]], SB, m),
                )
            )
            nv += 1
        by_id = {c.cid: c for c in cs}
        need = [f for f in u.families if len(f.members) >= 2]
        multi += len(need)
        for i in range(0, len(need), SB["batch_families"]):
            tin_b += est_tokens(
                pb.render(
                    domain=DOMAIN,
                    heading_path=heading,
                    families=render_families(u, need[i : i + SB["batch_families"]], by_id, SB),
                )
            )
            nb += 1
    import yaml as _y

    prices = _y.safe_load(Path("configs/default.yaml").read_text())["llm"]["tiers"]
    out_v = cands * 22  # ~22 output tokens per verdict (json)
    out_b = multi * 60
    res = {
        "sections": len(us), "candidates": cands, "families": fams, "multi_member_families": multi,
        "verifier_calls_V1": nv, "boundary_calls": nb,
        "tokens_in_V1": tin_v, "tokens_out_V1_est": out_v, "tokens_in_boundary": tin_b, "tokens_out_boundary_est": out_b,
    }  # fmt: skip
    for tier in ("bulk", "strong"):
        p = prices[tier]
        cost = lambda ti, to, p=p: (
            ti / 1e6 * p["usd_per_1m_input_tokens"] + to / 1e6 * p["usd_per_1m_output_tokens"]
        )
        v1 = cost(tin_v, out_v)
        v2 = cost(tin_b, out_b) + cost(
            tin_v * 0.6, out_v * 0.6
        )  # repaired spans ~ 60% of candidates (est.)
        res[f"est_usd_{tier}"] = {
            "V1": round(v1, 3),
            "V2": round(v2, 3),
            "V3": round(v2 * 0.8, 3),
            "note": "excludes hidden reasoning tokens (x1-x3 uncertainty)",
        }
    (OUT / "preflight.json").write_text(json.dumps(res, indent=1))
    return res


# ---------------------------------------------------------------- one-token gate table (dev scoring; $0)
def gold_one_token(gold: list[GoldConcept]) -> list[GoldConcept]:
    return [g for g in gold if len(g.concept.split()) == 1]


def ranker_gate_table(us, sections, gold, out0) -> dict:
    heading = {s["section_id"]: s.get("heading") or s["section_id"] for s in sections}
    scores = {sid: onetoken_scores(u, heading[sid]) for sid, u in us.items()}
    g1 = gold_one_token(gold)
    rows = {}
    n_one = sum(1 for u in us.values() for c in u.cands.values() if c.token_length == 1)
    for t in CFG["one_token"]["gate_grid"]:
        thr = None if t == "none" else float(t)
        kept = 0
        hit = 0
        for g in g1:
            u = us[g.section_id]
            cs = [c for c in u.cands.values() if c.surface in g.names()]
            ok = any(
                c.token_length != 1 or thr is None or scores[g.section_id].get(c.cid, 0) >= thr
                for c in cs
            )
            hit += ok
        for sid, u in us.items():
            kept += sum(
                1
                for c in u.cands.values()
                if c.token_length == 1 and (thr is None or scores[sid].get(c.cid, 0) >= thr)
            )
        rows[str(t)] = {
            "one_token_candidates_sent": kept,
            "one_token_candidates_total": n_one,
            "load_reduction": round(1 - kept / n_one, 3),
            "one_token_proposal_recall": round(hit / len(g1), 4),
        }
    return {"n_one_token_gold": len(g1), "rows": rows}


def choose_gate(table: dict) -> str:
    """Pre-registered: the smallest verification load whose one-token proposal-recall loss vs no gate is <= 0.02."""
    base = table["rows"]["none"]["one_token_proposal_recall"]
    ok = [
        (r["one_token_candidates_sent"], k)
        for k, r in table["rows"].items()
        if base - r["one_token_proposal_recall"] <= 0.02
    ]
    return min(ok)[1]


# ---------------------------------------------------------------- run
def run_arms(
    arms: list[str], limit: int | None, max_usd: float, gate: str | None, tag: str, tier: str
) -> None:
    from cumap.config import get_settings
    from cumap.llm.client import LLMClient

    SB["model_tier"] = tier
    nlp, sections, emph, _gold, out0 = load_dev(limit)
    us = unions(nlp, sections, emph, out0)
    pv = load_prompt(
        ROOT / "prompts", SB["verifier_prompt"]["task"], SB["verifier_prompt"]["version"]
    )
    pb = load_prompt(
        ROOT / "prompts", SB["boundary_prompt"]["task"], SB["boundary_prompt"]["version"]
    )
    pv3 = load_prompt(ROOT / "prompts", SB["verifier_prompt"]["task"], "v2")
    settings = get_settings()
    spent_all = 0.0
    for arm in arms:
        t0 = time.time()
        usage = Usage()
        res: dict[str, SectionOutcome] = {}
        client = None if arm == "V0" else LLMClient(settings, run_id=f"cr014_stageB_{arm}{tag}")
        if arm == "V0":
            embed = X.Embedder(settings.embeddings.model)
            pruners = X.loco_pruners(split_data("dev")[0], nlp, embed)
            sctx = SectionContext(sections, emph, nlp)
        for s in sections:
            sid = s["section_id"]
            u = us[sid]
            heading = s.get("heading") or sid
            m = existing_matches(out0, sid)
            only = None
            if arm == "V3" and gate not in (None, "none"):
                sc = onetoken_scores(u, heading)
                only = {
                    c.cid
                    for c in u.cands.values()
                    if c.token_length != 1 or sc.get(c.cid, 0) >= float(gate)
                }
            if arm == "V0":
                paras = split_paragraphs(s["text"])
                cards = cards_for(out0, sid, s["text"])
                pr = pruners.get(str(s["chapter_num"]), pruners["all"]).p_growing
                res[sid] = run_v0(
                    u, s, sctx.vctx(s, paras, cards), cards, pr, CFG["v0"]["pruner_tau"]
                )
            elif arm == "V1":
                res[sid] = run_v1(client, pv, u, heading, m, usage)
            else:
                res[sid] = run_v2(
                    client,
                    pv3 if arm == "V3" else pv,
                    pb,
                    u,
                    heading,
                    m,
                    usage,
                    only,
                    evidence=arm == "V3",
                )
            if client is not None and getattr(client, "spent_usd", 0.0) + spent_all > max_usd:
                raise SystemExit(f"stopped: over --max-usd {max_usd}")
            print(
                arm,
                sid,
                len(res[sid].accepted),
                "accepted",
                f"${getattr(client, 'spent_usd', 0.0):.3f}" if client else "",
            )
        cost = round(getattr(client, "spent_usd", 0.0), 4) if client else 0.0
        spent_all += cost
        meta = {"arm": arm, "tier": tier if arm != "V0" else None, "gate": (gate or "none") if arm == "V3" else None, "calls": usage.calls,
                "errors": usage.errors, "cost_usd": cost, "seconds": round(time.time() - t0, 1), "sections": len(res), "prompt_v": (pv3 if arm == "V3" else pv).version, "prompt_b": pb.version}  # fmt: skip
        (OUT / f"{arm}{tag}.json").write_text(
            json.dumps(
                {"meta": meta, "sections": {k: dataclasses.asdict(v) for k, v in res.items()}}
            )
        )
        print(meta)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["preflight", "gate-table", "run"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--arms", nargs="+", default=["V0", "V1", "V2", "V3"])
    ap.add_argument("--max-usd", type=float, default=1.0)
    ap.add_argument("--gate")
    ap.add_argument("--tag", default="")
    ap.add_argument("--tier", default="bulk")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.phase == "preflight":
        print(json.dumps(preflight(a.limit), indent=1))
    elif a.phase == "gate-table":
        nlp, sections, emph, gold, out0 = load_dev()
        t = ranker_gate_table(unions(nlp, sections, emph, out0), sections, gold, out0)
        t["chosen_gate"] = choose_gate(t)
        (OUT / "gate_table.json").write_text(json.dumps(t, indent=1))
        print(json.dumps(t, indent=1))
    else:
        run_arms(a.arms, a.limit, a.max_usd, a.gate, a.tag, a.tier)
