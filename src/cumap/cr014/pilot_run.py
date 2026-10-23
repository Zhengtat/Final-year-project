"""CR-014 STOP 3B step 4: frozen U0 and current V3 on the two P&D pilot sections, scored span-exact against the owner's pilot gold.

    uv run python -m cumap.cr014.pilot_run v3 --max-usd 1.0     # paid V3 (bulk tier); U0 runs are produced by cumap.cr012.unit_run-style stage_concepts
    uv run python -m cumap.cr014.pilot_run score

U0 = the production concept stage on a one-section slice (tau 0, strict G-links) as CR-012 ran it; its RAW iteration-0 output is also V3's LLM proposal source.
Gold is read only by `score`."""

from __future__ import annotations

import argparse
import dataclasses
import json
import time
from pathlib import Path

import yaml

from cumap.cr014 import v3_core
from cumap.cr014.pilot_score import load_gold, place, score
from cumap.cr014.union import build_section_union
from cumap.expert_kg.alias_rules import AliasConfig
from cumap.llm.prompts import load_prompt

ROOT = Path(".")
OUT = ROOT / "data/processed/cr014/pilot"
MAN = yaml.safe_load((ROOT / "configs/cr014_manifest.yaml").read_text())
DOMAIN = "computer networking"
GOLD = ROOT / "data/gold/pd_concept_pilot_blind.csv"
SENT = ROOT / "data/interim/checks/cr014/pd_concept_pilot_sentences.csv"


def section_row(sid: str) -> dict:
    for line in (ROOT / "data/interim/textbook_sections.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["section_id"] == sid:
            return r
    raise KeyError(sid)


def u0_surfaces(sid: str) -> tuple[list[str], list[str]]:
    """(final surfaces = names + aliases + existing-mention surfaces of kept concepts, raw iteration-0 surfaces) over the section's units."""
    d = json.loads(
        (
            ROOT / f"data/processed/kg/cr014_pilot_{sid.replace('.', '_')}_U0/v4_concepts.json"
        ).read_text()
    )
    final, raw = [], []
    for uid, res in d["sections"].items():
        meta = d["section_meta"].get(uid, {})
        pruned = {" ".join(x.lower().split()) for x in meta.get("pruned", [])} | {
            " ".join(x.lower().split()) for x in meta.get("attributes", [])
        }
        for c in res["final"]["new_concepts"]:
            if " ".join(c["name"].lower().split()) not in pruned:
                final += [c["name"], *c["aliases"]]
        final += [m["surface"] for m in res["final"]["existing_mentions"]]
        it0 = res.get("iteration0") or res["iterations"][0]["output"]
        for c in it0.get("new_concepts", []):
            raw += [c["name"], *c.get("aliases", [])]
        raw += [m["surface"] for m in it0.get("existing_mentions", [])]
    return final, raw


def run_v3(max_usd: float) -> None:
    import spacy

    from cumap.config import get_settings
    from cumap.cr014.llm_stage import Usage
    from cumap.llm.client import LLMClient

    nlp, cfg = spacy.load("en_core_web_sm"), AliasConfig.load()
    pv = load_prompt(ROOT / "prompts", "cr014_concept_verifier", "v2")
    pb = load_prompt(ROOT / "prompts", "cr014_boundary_repair", "v1")
    OUT.mkdir(parents=True, exist_ok=True)
    spent = 0.0
    for sid in MAN["pilot"]:
        row = section_row(sid)
        sec = {
            "section_id": sid,
            "text": row["text"],
            "heading": " > ".join(row["heading_path"] or []) or sid,
            "chapter_num": row["chapter_num"],
        }
        _final, raw = u0_surfaces(sid)
        u = build_section_union(sec, set(row.get("emphasized_terms") or []), nlp, cfg, raw)
        client = LLMClient(get_settings(), run_id=f"cr014_pilot_V3_{sid.replace('.', '_')}")
        usage, t0 = Usage(), time.time()
        res = v3_core.run_v2(
            client, pv, pb, u, sec["heading"], {}, usage, None, evidence=True, domain=DOMAIN
        )
        cost = round(getattr(client, "spent_usd", 0.0), 4)
        spent += cost
        meta = {"section": sid, "candidates": len(u.cands), "families": len(u.families), "calls": usage.calls, "errors": usage.errors, "cost_usd": cost, "seconds": round(time.time() - t0, 1), "prompt_v": pv.version, "prompt_b": pb.version, "tier": "bulk"}  # fmt: skip
        (OUT / f"V3_{sid}.json").write_text(
            json.dumps({"meta": meta, "outcome": dataclasses.asdict(res)})
        )
        print(meta)
        if spent > max_usd:
            raise SystemExit(f"stopped: ${spent} over --max-usd {max_usd}")


def analysis(gold, texts, arms) -> dict:
    """Span-level proposal recall and earliest-failure taxonomy for V3 misses; sentence-clustered paired bootstrap of the mention F1 difference."""
    import random

    import spacy

    nlp, cfg = spacy.load("en_core_web_sm"), AliasConfig.load()
    norm = lambda s: " ".join(s.lower().split())
    tax = {
        "proposal_exact_hit": 0,
        "P0_no_overlapping_candidate": 0,
        "P1_overlap_only": 0,
        "V_verifier_rejected": 0,
        "B0_lost_at_boundary_stage": 0,
        "placement_or_other": 0,
    }
    prop_hit = n = 0
    for sid in MAN["pilot"]:
        row = section_row(sid)
        sec = {
            "section_id": sid,
            "text": row["text"],
            "heading": sid,
            "chapter_num": row["chapter_num"],
        }
        u = build_section_union(
            sec, set(row.get("emphasized_terms") or []), nlp, cfg, u0_surfaces(sid)[1]
        )
        v3 = json.loads((OUT / f"V3_{sid}.json").read_text())["outcome"]
        verified = {v.get("surface") for v in v3["verdicts"].values()}
        pred = set(arms["V3"][sid])
        occ = [(c.surface, a, b) for c in u.cands.values() for a, b, _ in c.occurrences]
        for m in (g for g in gold if g.section_id == sid):
            n += 1
            surf = norm(texts[sid][m.start : m.end])
            hit = surf in u.cands
            prop_hit += hit
            if (m.start, m.end) in pred:
                tax["proposal_exact_hit"] += 0
                continue
            if not hit:
                ov = any(a < m.end and m.start < b for _, a, b in occ)
                tax["P1_overlap_only" if ov else "P0_no_overlapping_candidate"] += 1
            elif surf in v3["accepted"]:
                tax["placement_or_other"] += 1
            elif surf in verified:
                tax["V_verifier_rejected"] += 1
            else:
                tax["B0_lost_at_boundary_stage"] += 1
    sents = list(__import__("csv").DictReader(SENT.open(encoding="utf-8")))
    bounds = {
        r["sentence_id"]: (int(r["char_start"]), int(r["char_end"]), r["section_id"]) for r in sents
    }
    per = {}
    for sid_, (a0, b0, sec_id) in bounds.items():
        g = {(m.start, m.end) for m in gold if m.section_id == sec_id and a0 <= m.start < b0}
        c = []
        for arm in ("U0", "V3"):
            p = {x for x in arms[arm][sec_id] if a0 <= x[0] < b0}
            c.append((len(g & p), len(p - g), len(g - p)))
        per[sid_] = c
    keys = sorted(per)
    f1 = lambda t: 2 * t[0] / (2 * t[0] + t[1] + t[2]) if t[0] else 0.0
    rng, deltas = random.Random(0), []
    for _ in range(4000):
        samp = [per[rng.choice(keys)] for _ in keys]
        t = [tuple(sum(x[i][j] for x in samp) for j in range(3)) for i in (0, 1)]
        deltas.append(f1(t[1]) - f1(t[0]))
    deltas.sort()
    return {
        "span_level_proposal_recall_U2": prop_hit / n,
        "v3_miss_taxonomy": tax,
        "bootstrap_delta_f1_sentence_clustered": {
            "mean": sum(deltas) / len(deltas),
            "lo95": deltas[100],
            "hi95": deltas[3899],
            "n_sentences": len(keys),
        },
    }


def run_score() -> dict:
    gold = load_gold(GOLD, SENT)
    texts = {sid: section_row(sid)["text"] for sid in MAN["pilot"]}
    arms: dict[str, dict[str, list]] = {"U0": {}, "V3": {}}
    for sid in MAN["pilot"]:
        final, _raw = u0_surfaces(sid)
        arms["U0"][sid] = place(final, texts[sid])
        v3 = json.loads((OUT / f"V3_{sid}.json").read_text())
        arms["V3"][sid] = place(sorted(v3["outcome"]["accepted"]), texts[sid])
    res = {
        "n_gold_mentions": len(gold),
        "n_gold_concepts": len({m.concept_id for m in gold}),
        "by_section": {},
        "arms": {},
    }
    for arm in ("U0", "V3"):
        res["arms"][arm] = score(arms[arm], gold, texts)
        for sid in MAN["pilot"]:
            res["by_section"].setdefault(arm, {})[sid] = score({sid: arms[arm][sid]}, gold, texts)
    # concept-level (distinct surface) view, comparable in kind to the IIR metric but reported separately
    norm = lambda s: " ".join(s.lower().split())
    gsurf = {
        sid: {norm(texts[sid][m.start : m.end]) for m in gold if m.section_id == sid}
        for sid in MAN["pilot"]
    }
    for arm in ("U0", "V3"):
        tp = fp = fn = 0
        for sid in MAN["pilot"]:
            ps = {norm(texts[sid][a:b]) for a, b in arms[arm][sid]}
            tp += len(ps & gsurf[sid])
            fp += len(ps - gsurf[sid])
            fn += len(gsurf[sid] - ps)
        p, r = tp / (tp + fp), tp / (tp + fn)
        res["arms"][arm]["distinct_surface_view"] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": p,
            "recall": r,
            "f1": 2 * p * r / (p + r),
        }
    res["nested_allowed"] = {}
    for arm in ("U0", "V3"):
        surfaces = {
            sid: u0_surfaces(sid)[0]
            if arm == "U0"
            else sorted(json.loads((OUT / f"V3_{sid}.json").read_text())["outcome"]["accepted"])
            for sid in MAN["pilot"]
        }
        res["nested_allowed"][arm] = score(
            {sid: place(surfaces[sid], texts[sid], nested=True) for sid in MAN["pilot"]},
            gold,
            texts,
        )
    res.update(analysis(gold, texts, arms))
    (OUT / "pilot_results.json").write_text(json.dumps(res, indent=1, default=str))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["v3", "score"])
    ap.add_argument("--max-usd", type=float, default=1.0)
    a = ap.parse_args()
    if a.phase == "v3":
        run_v3(a.max_usd)
    else:
        print(json.dumps(run_score(), indent=1, default=str))
