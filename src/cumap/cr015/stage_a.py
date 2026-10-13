"""CR-015 Stage A: boundary + placement ablation A0-A3 on DEVELOPMENT (the exposed CR-014 P&D sections, model-generated gold). Report-only extras: the fresh CR-015 pilot.

    uv run python -m cumap.cr015.stage_a local          # A0, A1 ($0): saved frozen-V3 outputs
    uv run python -m cumap.cr015.stage_a select ...     # A2/A3 live (see selector.py)
Scoring is the frozen `scoring.py`; gold is read only here, after every prediction exists."""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import spacy

from cumap.cr014.union import SectionUnion, build_section_union
from cumap.cr015 import placement as PL
from cumap.cr015.dev_data import DevSection, load_dev
from cumap.cr015.scoring import score_mentions
from cumap.eval.stats import paired_bootstrap_delta
from cumap.expert_kg.alias_rules import AliasConfig

ROOT = Path(".")
OUT = ROOT / "data/processed/cr015/stageA"
norm = PL.norm


def unions(dev: list[DevSection]) -> dict[str, SectionUnion]:
    path = OUT / "unions_dev.pkl"
    if path.exists():
        return pickle.loads(path.read_bytes())
    nlp, cfg = spacy.load("en_core_web_sm"), AliasConfig.load()
    us = {}
    for d in dev:
        sec = {
            "section_id": d.sid,
            "text": d.text,
            "heading": d.sid,
            "chapter_num": d.row["chapter_num"],
        }
        us[d.sid] = build_section_union(
            sec, set(d.row.get("emphasized_terms") or []), nlp, cfg, d.u0_raw
        )
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(us))
    return us


def counts_by_section(
    pred: dict[str, list], dev: list[DevSection]
) -> dict[str, tuple[int, int, int]]:
    out = {}
    for d in dev:
        g = {(m.start, m.end) for m in d.gold}
        p = set(pred[d.sid])
        out[d.sid] = (len(g & p), len(p - g), len(g - p))
    return out


def evaluate(arm_spans: dict[str, dict[str, list]], dev: list[DevSection]) -> dict:
    texts = {d.sid: d.text for d in dev}
    gold = [m for d in dev for m in d.gold]
    res = {}
    base = None
    for arm, spans in arm_spans.items():
        r = score_mentions(spans, gold, texts)
        r["by_section_counts"] = counts_by_section(spans, dev)
        res[arm] = r
    return res


def compare(res: dict, ref: str, arm: str) -> dict:
    a, b = (
        {k: tuple(v) for k, v in res[ref]["by_section_counts"].items()},
        {k: tuple(v) for k, v in res[arm]["by_section_counts"].items()},
    )
    return paired_bootstrap_delta(a, b, n=10000, seed=0)


def local_arms(dev: list[DevSection], us: dict[str, SectionUnion]) -> dict[str, dict[str, list]]:
    arms: dict[str, dict[str, list]] = {"U0": {}, "A0": {}, "A0_nested_all_view": {}, "A1": {}}
    for d in dev:
        u = us[d.sid]
        acc = set(d.v3["outcome"]["accepted"])
        arms["U0"][d.sid] = PL.longest_match(d.u0_final, d.text)
        arms["A0"][d.sid] = PL.longest_match(sorted(acc), d.text)
        arms["A0_nested_all_view"][d.sid] = sorted(PL.place(sorted(acc), d.text, nested=True))
        arms["A1"][d.sid] = PL.family_nested_v3(u, acc, d.v3["outcome"]["boundary"])
    return arms


def summarize(res: dict, keys=("U0", "A0", "A1")) -> None:
    for k in keys:
        if k not in res:
            continue
        m = res[k]["mention_span_exact"]
        print(f"{k:22s} P {m['precision']:.3f} R {m['recall']:.3f} F1 {m['f1']:.3f} | nested R {res[k]['nested_gold_recall']['recall']:.3f} | overlong {res[k]['over_long_fp']} underlong {res[k]['under_long_fp']} | distinct P {res[k]['distinct_surface']['precision']:.3f} R {res[k]['distinct_surface']['recall']:.3f} | pred {m['tp'] + m['fp']}")  # fmt: skip


def run_live(arm: str, limit: int | None, max_usd: float) -> None:
    """A2 (selector v1) or A3 (selector v2 + hard-negative demonstrations) on the development sections; the frozen V3 verifier is unchanged."""
    import time

    from cumap.config import get_settings
    from cumap.cr014.llm_stage import Usage
    from cumap.cr015 import hardneg, selector
    from cumap.llm.client import LLMClient
    from cumap.llm.prompts import load_prompt

    dev = load_dev()
    us = unions(dev)
    dev_run = dev[:limit] if limit else dev
    prompt_s = load_prompt(ROOT / "prompts", "cr015_boundary_family", "v2" if arm == "A3" else "v1")
    prompt_v = load_prompt(ROOT / "prompts", "cr014_concept_verifier", "v2")
    bank = None
    if arm == "A3":
        bank = hardneg.build_bank(dev)
        (OUT / "hardneg_bank_meta.json").write_text(
            json.dumps(
                {
                    "sha256": bank["sha256"],
                    "groups": bank["n_groups"],
                    "negatives": bank["n_negatives"],
                }
            )
        )
    settings = get_settings()
    client = LLMClient(settings, run_id=f"cr015_stageA_{arm}")
    spent0, t_all = 0.0, time.time()
    for d in dev_run:
        path = OUT / f"{arm}_{d.sid}.json"
        if path.exists():
            continue
        u = us[d.sid]
        by_id = {c.cid: c for c in u.cands.values()}
        usage, t0, c0 = Usage(), time.time(), client.spent_usd
        need = [f for f in u.families if len(f.members) >= 2]
        sel = selector.run_selector(client, prompt_s, u, d.sid, need, by_id, usage, bank=bank)
        for f in u.families:
            if len(f.members) == 1:
                sel.selected[f.fid] = {by_id[f.members[0]].surface}
        accepted, verdicts = selector.verify_selected(
            client, prompt_v, u, d.sid, sel.selected, usage
        )
        spans = PL.family_grounded(u, sel.selected, accepted)
        meta = {"section": d.sid, "calls": usage.calls, "errors": usage.errors, "cost_usd": round(client.spent_usd - c0, 4), "seconds": round(time.time() - t0, 1), "families": len(u.families), "families_llm": len(need), "selector_prompt": prompt_s.version, "verifier_prompt": prompt_v.version, "bank_sha256": bank["sha256"] if bank else None}  # fmt: skip
        path.write_text(
            json.dumps(
                {
                    "meta": meta,
                    "selected": {k: sorted(v) for k, v in sel.selected.items()},
                    "decisions": sel.decisions,
                    "accepted": sorted(accepted),
                    "verdicts": verdicts,
                    "spans": spans,
                    "invalid_targets": sel.invalid_targets,
                    "unanswered": sel.unanswered,
                    "retrieval": sel.retrieval,
                }
            )
        )
        spent0 += meta["cost_usd"]
        print(arm, d.sid, meta["calls"], meta["cost_usd"], meta["seconds"], flush=True)
        if spent0 > max_usd:
            raise SystemExit(f"stopped: ${spent0:.2f} over --max-usd {max_usd}")
    print("done", arm, round(spent0, 3), round(time.time() - t_all))


def saved_arm(arm: str, dev: list[DevSection]) -> dict[str, list]:
    return {
        d.sid: [tuple(x) for x in json.loads((OUT / f"{arm}_{d.sid}.json").read_text())["spans"]]
        for d in dev
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] in ("A2", "A3"):
        run_live(
            sys.argv[1],
            (int(sys.argv[2]) or None) if len(sys.argv) > 2 else None,
            float(sys.argv[3]) if len(sys.argv) > 3 else 3.0,
        )
        raise SystemExit(0)
    dev = load_dev()
    us = unions(dev)
    arms = local_arms(dev, us)
    res = evaluate(arms, dev)
    summarize(res, tuple(arms))
    print(
        "dev sections",
        len(dev),
        "gold mentions",
        sum(len(d.gold) for d in dev),
        "words",
        sum(d.words for d in dev),
    )
    Path(OUT / "stageA_local.json").write_text(
        json.dumps(
            {k: {x: y for x, y in v.items() if x != "by_section_counts"} for k, v in res.items()},
            indent=1,
            default=str,
        )
    )
    print(
        "A1 vs A0 dF1",
        {
            k: round(v, 3)
            for k, v in compare(res, "A0", "A1").items()
            if k in ("delta", "lo95", "hi95")
        },
    )
