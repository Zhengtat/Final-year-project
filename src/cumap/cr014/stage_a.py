"""CR-014 Stage A: proposal-universe ablation U0-U5 on IIR dev (13 sections). Proposal recall only; no verifier tuning.

    uv run python -m cumap.cr014.stage_a dry-run
    uv run python -m cumap.cr014.stage_a sample --max-usd 1.0        # U3 independent samples (paid, bulk tier)
    uv run python -m cumap.cr014.stage_a evaluate                     # $0, local

Gold is read only by `evaluate`, after every candidate set is built."""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import statistics
import sys
import time
from pathlib import Path

from cumap.concepts_v4 import experiments as X
from cumap.concepts_v4 import runner as R
from cumap.concepts_v4.bank import load as load_bank
from cumap.concepts_v4.cards import split_paragraphs
from cumap.concepts_v4.loop import SectionRunner
from cumap.cr010.nodes_exp import SectionContext, baseline_run, cards_for, load_cfg, split_data
from cumap.cr014.proposal import Registry, add, definitional_hits, norm_surface, u1_registry
from cumap.expert_kg.alias_rules import AliasConfig
from cumap.expert_kg.face_scorer import GoldConcept, normalize
from cumap.llm.prompts import load_prompt

ROOT = Path(".")
OUT = ROOT / "data/processed/cr014/stageA"
SAMPLE_LABELS = (
    "cr014s1",
    "cr014s2",
    "cr014s3",
)  # pre-registered: distinct cache keys, same prompt text
GLINER_JSON = OUT / "gliner_dev_t010.json"
DOMAIN = "information retrieval"


# ---------------------------------------------------------------- LLM source extraction
def llm_surfaces(output: dict) -> list[str]:
    names = []
    for c in output.get("new_concepts", []):
        names += [c["name"], *c.get("aliases", [])]
    names += [m["surface"] for m in output.get("existing_mentions", [])]
    return names


def raw_surfaces(res: dict) -> list[str]:
    """Everything the generator proposed in any iteration, before any rule, pruner or G-link decision."""
    out = []
    for it in res.get("iterations", []):
        out += llm_surfaces(it["output"])
    out += llm_surfaces(res.get("iteration0") or {})
    return out


def final_surfaces(res: dict) -> list[str]:
    return llm_surfaces(res["final"])


# ---------------------------------------------------------------- sampling (paid)
def sample_path(label: str) -> Path:
    return OUT / f"{label}.json"


def run_samples(max_usd: float, limit: int | None, labels: tuple[str, ...]) -> None:
    import spacy

    from cumap.config import get_settings
    from cumap.llm.client import LLMClient

    settings, nlp = get_settings(), spacy.load("en_core_web_sm")
    cfg = load_cfg()
    sections, emph, _ = split_data("dev")
    sections = sections[:limit] if limit else sections
    out0 = baseline_run("dev", cfg)
    ctx = SectionContext(sections, emph, nlp)
    base = load_prompt(ROOT / "prompts", "concept_generator", "v4")
    spent_total = 0.0
    for label in labels:
        client = LLMClient(settings, run_id=f"cr014_stageA_{label}")
        variant = dataclasses.replace(base, version=f"{base.version}-{label}")
        # raw generator call only (no verifier loop, no repair wording): a proposal sample, not a finished run
        runner = SectionRunner(
            client, variant, load_bank(), X.loop_config("G1", 0, use_verifier=False), domain=DOMAIN
        )
        res_all: dict[str, dict] = {}
        t0 = time.time()
        for sec in sections:
            sid = sec["section_id"]
            if sid not in out0.sections:
                continue
            paras = split_paragraphs(sec["text"])
            cards = cards_for(out0, sid, sec["text"])
            res = runner.run(
                {**sec, "heading": sec.get("heading") or sid},
                paras,
                cards,
                None,
                ctx.vctx(sec, paras, cards),
            )
            res_all[sid] = {"output": res.final, "calls": res.calls, "error": res.error}
            if getattr(client, "spent_usd", 0.0) + spent_total > max_usd:
                raise SystemExit(f"stopped: over --max-usd {max_usd}")
        cost = round(getattr(client, "spent_usd", 0.0), 4)
        spent_total += cost
        meta = {
            "label": label,
            "seconds": round(time.time() - t0, 1),
            "cost_usd": cost,
            "prompt": variant.version,
        }
        sample_path(label).write_text(json.dumps({"meta": meta, "sections": res_all}))
        print(meta)


# ---------------------------------------------------------------- candidate sets per arm
def llm_registry(sec: dict, surfaces: list[str], source: str, reg: Registry) -> None:
    text_l = re.sub(r"\s+", " ", sec["text"].lower())
    for s in surfaces:
        add(reg, sec["section_id"], s, source, text_l)


def build_sources(sections, emph, out0, nlp) -> dict[str, dict[str, Registry]]:
    """source -> section -> registry. Sources: u1 sub-sources are tags inside the u1 registry."""
    cfg = AliasConfig.load()
    gnm: dict[str, set[str]] = {}
    preds0 = R.predictions(out0, sections, gnm)
    src: dict[str, dict[str, Registry]] = {k: {} for k in ("U1", "L0final", "L0raw", "P0pred")}
    for sec in sections:
        sid = sec["section_id"]
        if sid not in out0.sections:
            continue
        src["U1"][sid] = u1_registry(sec, emph.get(sid, set()), nlp, cfg)
        res = dataclasses.asdict(out0.sections[sid])
        r1: Registry = {}
        llm_registry(sec, final_surfaces(res), "L0final", r1)
        src["L0final"][sid] = r1
        r2: Registry = {}
        llm_registry(sec, raw_surfaces(res) + final_surfaces(res), "L0raw", r2)
        src["L0raw"][sid] = r2
        r3: Registry = {}
        llm_registry(sec, [p["canonical_name"] for p in preds0.get(sid, [])], "P0pred", r3)
        src["P0pred"][sid] = r3
    for label in SAMPLE_LABELS:
        if not sample_path(label).exists():
            continue
        d = json.loads(sample_path(label).read_text())["sections"]
        src[label] = {}
        for sec in sections:
            sid = sec["section_id"]
            r: Registry = {}
            if sid in d:
                llm_registry(sec, llm_surfaces(d[sid]["output"]), label, r)
            src[label][sid] = r
    if GLINER_JSON.exists():
        d = json.loads(GLINER_JSON.read_text())["sections"]
        src["GLiNER"] = {}
        for sec in sections:
            sid = sec["section_id"]
            r = {}
            text_l = re.sub(r"\s+", " ", sec["text"].lower())
            for e in d.get(sid, []):
                add(r, sid, e["surface"], "GLiNER", text_l, e["score"])
            src["GLiNER"][sid] = r
    return src


def union(parts: list[dict[str, Registry]], sids: list[str]) -> dict[str, set[str]]:
    return {sid: {k for p in parts for k in p.get(sid, {})} for sid in sids}


# ---------------------------------------------------------------- scoring
def toks(s: str) -> list[str]:
    return s.split()


def contains(a: list[str], b: list[str]) -> bool:
    """b is a contiguous token subsequence of a."""
    return any(a[i : i + len(b)] == b for i in range(len(a) - len(b) + 1))


def overlap_match(cands: set[str], names: set[str], stop: set[str]) -> bool:
    for n in names:
        nt = toks(n)
        for c in cands:
            ct = toks(c)
            if (contains(ct, nt) or contains(nt, ct)) and not (len(ct) == 1 and ct[0] in stop):
                return True
    return False


def gold_features(gold: list[GoldConcept], sections: list[dict], emph) -> list[dict]:
    order = {s["section_id"]: i for i, s in enumerate(sections)}
    seen: set[str] = set()
    rows = []
    for g in sorted(gold, key=lambda g: order.get(g.section_id, 0)):
        sec = next(s for s in sections if s["section_id"] == g.section_id)
        text_l = re.sub(r"\s+", " ", sec["text"].lower())
        names = g.names()
        in_text = any(re.search(rf"(?<!\w){re.escape(n)}(?!\w)", text_l) for n in names)
        defs = definitional_hits(sec["text"])
        cues = []
        if names & {norm_surface(e) for e in emph.get(g.section_id, set())}:
            cues.append("emphasis")
        if names & defs:
            cues.append("definitional")
        rows.append(
            {
                "section_id": g.section_id,
                "names": names,
                "canonical": normalize(g.concept),
                "n_tok": min(len(normalize(g.concept).split()), 4),
                "in_text": in_text,
                "known": bool(names & seen),
                "cues": cues or ["none"],
            }
        )
        seen |= names
    return rows


def evaluate_arm(cands: dict[str, set[str]], grows: list[dict], stop: set[str], sections) -> dict:
    exact = [bool(g["names"] & cands.get(g["section_id"], set())) for g in grows]
    over = [
        e or overlap_match(cands.get(g["section_id"], set()), g["names"], stop)
        for e, g in zip(exact, grows)
    ]
    n = len(grows)
    wc = {s["section_id"]: len(s["text"].split()) for s in sections}
    vol = {sid: len(c) for sid, c in cands.items()}
    words = sum(wc[sid] for sid in cands)

    def rate(flags, sel):
        idx = [i for i, g in enumerate(grows) if sel(g)]
        return (sum(flags[i] for i in idx) / len(idx), len(idx)) if idx else (float("nan"), 0)

    sl = {}
    for k in (1, 2, 3, 4):
        sl[f"{k}{'+' if k == 4 else ''}-token"] = rate(exact, lambda g, k=k: g["n_tok"] == k)
    sl["known"] = rate(exact, lambda g: g["known"])
    sl["new"] = rate(exact, lambda g: not g["known"])
    for cue in ("emphasis", "definitional", "none"):
        sl[f"cue:{cue}"] = rate(exact, lambda g, cue=cue: cue in g["cues"])
    return {
        "exact_recall": sum(exact) / n,
        "overlap_recall": sum(over) / n,
        "candidates": sum(vol.values()),
        "candidates_per_section_median": statistics.median(vol.values()),
        "candidates_per_1k_words": 1000 * sum(vol.values()) / words,
        "candidate_gold_ratio": sum(vol.values()) / n,
        "slices": {k: {"recall": v[0], "n": v[1]} for k, v in sl.items()},
        "exact_flags": exact,
    }


def evaluate() -> None:
    import spacy

    nlp = spacy.load("en_core_web_sm")
    cfg = load_cfg()
    sections, emph, gold = split_data("dev")
    out0 = baseline_run("dev", cfg)
    sids = [s["section_id"] for s in sections if s["section_id"] in out0.sections]
    secs = [s for s in sections if s["section_id"] in sids]
    gold = [g for g in gold if g.section_id in sids]
    src = build_sources(secs, emph, out0, nlp)
    stop = {w for w in nlp.Defaults.stop_words}
    grows = gold_features(gold, secs, emph)
    have = [k for k in ("GLiNER", *SAMPLE_LABELS) if k in src]
    samples = [src[k] for k in SAMPLE_LABELS if k in src]
    arms: dict[str, list[dict[str, Registry]]] = {
        "U0 (production final)": [src["P0pred"]],
        "U1 deterministic": [src["U1"]],
        "U2f U1 + production final": [src["U1"], src["L0final"]],
        "U2 U1 + current LLM (raw)": [src["U1"], src["L0raw"], src["L0final"]],
    }
    if samples:
        arms["L-only: current LLM raw"] = [src["L0raw"], src["L0final"]]
        arms["L-only: raw + 3 samples"] = [src["L0raw"], src["L0final"], *samples]
        for i in range(1, len(samples) + 1):
            arms[f"U3 U2 + {i} sample(s)"] = [src["U1"], src["L0raw"], src["L0final"], *samples[:i]]
    if "GLiNER" in src:
        arms["U4 U2 + GLiNER"] = [src["U1"], src["L0raw"], src["L0final"], src["GLiNER"]]
        arms["GLiNER only"] = [src["GLiNER"]]
    if samples and "GLiNER" in src:
        arms["U5 U2 + samples + GLiNER"] = [
            src["U1"],
            src["L0raw"],
            src["L0final"],
            *samples,
            src["GLiNER"],
        ]
    res = {
        name: evaluate_arm(union(parts, sids), grows, stop, secs) for name, parts in arms.items()
    }
    ceiling = sum(g["in_text"] for g in grows) / len(grows)
    # incremental recall by source: gold covered ONLY by that source (within the full union) and leave-one-out drop
    full_parts = {
        "u1": src["U1"],
        "llm_raw": src["L0raw"],
        "llm_final": src["L0final"],
        **{k: src[k] for k in have},
    }
    full = union(list(full_parts.values()), sids)
    full_rec = evaluate_arm(full, grows, stop, secs)["exact_recall"]
    incr = {}
    for name, part in full_parts.items():
        others = union([p for k, p in full_parts.items() if k != name], sids)
        only = evaluate_arm(others, grows, stop, secs)["exact_recall"]
        incr[name] = {
            "alone": evaluate_arm(union([part], sids), grows, stop, secs)["exact_recall"],
            "leave_one_out_drop": full_rec - only,
        }
    # internal U1 sub-sources
    sub = {}
    tags = sorted(
        {t for reg in src["U1"].values() for c in reg.values() for t in c.proposal_sources}
    )
    for t in tags:
        cs = {
            sid: {k for k, c in src["U1"][sid].items() if t in c.proposal_sources} for sid in sids
        }
        e = evaluate_arm(cs, grows, stop, secs)
        sub[t] = {"exact_recall": e["exact_recall"], "candidates": e["candidates"]}
    # source-overlap matrix: Jaccard of candidate sets and of covered-gold sets
    names = list(full_parts)
    cand_sets = {n: {(sid, k) for sid in sids for k in full_parts[n].get(sid, {})} for n in names}
    cov = {}
    for n in names:
        fl = evaluate_arm(union([full_parts[n]], sids), grows, stop, secs)["exact_flags"]
        cov[n] = {i for i, f in enumerate(fl) if f}
    jac = lambda a, b: len(a & b) / len(a | b) if a | b else 0.0
    matrix = {
        "candidate_jaccard": {
            a: {b: jac(cand_sets[a], cand_sets[b]) for b in names} for a in names
        },
        "gold_covered_jaccard": {a: {b: jac(cov[a], cov[b]) for b in names} for a in names},
        "gold_covered_n": {a: len(cov[a]) for a in names},
    }
    out = {
        "n_gold": len(grows),
        "n_sections": len(sids),
        "words": sum(len(s["text"].split()) for s in secs),
        "gold_in_text_ceiling": ceiling,
        "arms": res,
        "incremental": incr,
        "u1_subsources": sub,
        "matrix": matrix,
        "gliner_meta": json.loads(GLINER_JSON.read_text())["meta"]
        if GLINER_JSON.exists()
        else None,
        "sample_meta": [
            json.loads(sample_path(k).read_text())["meta"] for k in SAMPLE_LABELS if k in src
        ],
    }
    for a in out["arms"].values():
        a.pop("exact_flags")
    (OUT / "stage_a_results.json").write_text(json.dumps(out, indent=1))
    print(
        json.dumps(
            {
                k: (round(v["exact_recall"], 3), round(v["overlap_recall"], 3), v["candidates"])
                for k, v in res.items()
            },
            indent=1,
        )
    )
    print("gold-in-text ceiling", round(ceiling, 3), "n_gold", len(grows))


def dry_run() -> None:
    sections, _, _ = split_data("dev")
    words = sum(len(s["text"].split()) for s in sections)
    est = round(words / 1000 * 0.0033, 4)
    print(
        json.dumps(
            {
                "sections": len(sections),
                "words": words,
                "est_usd_per_sample": est,
                "est_usd_three_samples": round(3 * est, 4),
                "note": "raw generator call only, bulk tier (gpt-6-luna), 1 call/section; measured rate $0.0033/1k words includes verifier reprompts so this is an upper estimate",
            },
            indent=1,
        )
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["dry-run", "sample", "evaluate"])
    ap.add_argument("--max-usd", type=float, default=1.0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--labels", nargs="+", default=list(SAMPLE_LABELS))
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    {"dry-run": dry_run, "evaluate": evaluate}.get(
        a.phase, lambda: run_samples(a.max_usd, a.limit, tuple(a.labels))
    )()


if __name__ == "__main__":
    sys.exit(main())
