"""CR-014 STOP 4: run the frozen production baseline (U0) and the frozen V3 exactly once on the sealed held-out sections of `configs/cr014_manifest.yaml`.

    uv run python -m cumap.cr014.heldout_run --dry-run
    uv run python -m cumap.cr014.heldout_run run --max-usd 6

Isolation: this module never reads gold. An audit hook refuses any file open under `data/gold/` or of a `pd_concept_*_blind.csv` / `heldout_gold*` file for the whole
process, and the run refuses to start unless (a) `reports/cr014/FREEZE_V3.json` matches the current code/prompt/config hashes and (b) the held-out gold hash manifest
exists (the gold FILE is not opened). A section that already has a completed output is never re-run (no retries for quality, no best-run selection)."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(".")
OUT = ROOT / "data/processed/cr014/heldout"
FREEZE = ROOT / "reports/cr014/FREEZE_V3.json"
GOLD_MANIFEST = ROOT / "reports/cr014/gold_manifest_heldout.json"
DOMAIN = "computer networking"
_FORBIDDEN = ("data/gold", "pd_concept_test_blind", "pd_concept_pilot_blind", "heldout_gold")


def install_gold_guard() -> None:
    def hook(event: str, args: tuple) -> None:
        if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
            p = os.fsdecode(args[0]).replace("\\", "/")
            if any(f in p for f in _FORBIDDEN):
                raise PermissionError(f"CR-014 held-out prediction code may not open gold: {p}")

    sys.addaudithook(hook)


def check_preconditions() -> dict:
    from cumap.cr014.freeze import current_hashes

    if not FREEZE.exists():
        raise SystemExit("no FREEZE_V3.json: V3 is not frozen")
    frozen = json.loads(FREEZE.read_text())
    now = current_hashes()
    bad = [k for k, v in frozen["hashes"].items() if now.get(k) != v]
    if bad:
        raise SystemExit(f"frozen artefacts changed since the freeze: {bad[:5]}")
    if not GOLD_MANIFEST.exists():
        raise SystemExit(
            "held-out gold is not frozen (no gold_manifest_heldout.json hash manifest)"
        )
    return {
        "freeze_commit": frozen["git_commit"],
        "gold_sha256": json.loads(GOLD_MANIFEST.read_text())["sha256"],
    }


def section_row(sid: str) -> dict:
    for line in (ROOT / "data/interim/textbook_sections.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["section_id"] == sid:
            return r
    raise KeyError(sid)


def u0_run_id(sid: str) -> str:
    return f"cr014_heldout_{sid.replace('.', '_')}_U0"


def run_u0(sid: str, dry_run: bool, max_usd: float) -> dict:
    """The frozen production concept stage (tau 0, strict G-links) on a one-section slice, as CR-012 ran it."""
    from cumap.concepts_v4 import cr009_run as R
    from cumap.cr012.unit_run import RECIPE, prepare

    info = prepare(sid)
    os.environ["CUMAP_DEMO_SLICE"] = info["slice_config"]
    return R.stage_concepts(
        u0_run_id(sid),
        dry_run=dry_run,
        limit_units=None,
        max_usd=max_usd,
        tau=RECIPE["tau"],
        strict_g_links=RECIPE["strict_g_links"],
    )


def u0_surfaces(sid: str) -> tuple[list[str], list[str]]:
    d = json.loads((ROOT / f"data/processed/kg/{u0_run_id(sid)}/v4_concepts.json").read_text())
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


def run_v3(sid: str, max_usd: float) -> dict:
    import spacy

    from cumap.config import get_settings
    from cumap.cr014 import v3_core
    from cumap.cr014.llm_stage import Usage
    from cumap.cr014.union import build_section_union
    from cumap.expert_kg.alias_rules import AliasConfig
    from cumap.llm.client import LLMClient
    from cumap.llm.prompts import load_prompt

    nlp, cfg = spacy.load("en_core_web_sm"), AliasConfig.load()
    pv = load_prompt(ROOT / "prompts", "cr014_concept_verifier", "v2")
    pb = load_prompt(ROOT / "prompts", "cr014_boundary_repair", "v1")
    row = section_row(sid)
    sec = {
        "section_id": sid,
        "text": row["text"],
        "heading": " > ".join(row["heading_path"] or []) or sid,
        "chapter_num": row["chapter_num"],
    }
    _final, raw = u0_surfaces(sid)
    u = build_section_union(sec, set(row.get("emphasized_terms") or []), nlp, cfg, raw)
    client = LLMClient(get_settings(), run_id=f"cr014_heldout_V3_{sid.replace('.', '_')}")
    usage, t0 = Usage(), time.time()
    res = v3_core.run_v2(
        client, pv, pb, u, sec["heading"], {}, usage, None, evidence=True, domain=DOMAIN
    )
    cost = round(getattr(client, "spent_usd", 0.0), 4)
    meta = {"section": sid, "candidates": len(u.cands), "families": len(u.families), "calls": usage.calls, "errors": usage.errors, "cost_usd": cost, "seconds": round(time.time() - t0, 1), "prompt_v": pv.version, "prompt_b": pb.version, "tier": "bulk"}  # fmt: skip
    return {"meta": meta, "outcome": dataclasses.asdict(res)}


def main() -> None:
    install_gold_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", nargs="?", default="run", choices=["run"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-usd", type=float, default=6.0)
    a = ap.parse_args()
    man = yaml.safe_load((ROOT / "configs/cr014_manifest.yaml").read_text())
    sections = man["heldout_sealed"]
    if a.dry_run:
        words = {s: len(section_row(s)["text"].split()) for s in sections}
        out = {"sections": sections, "words": words, "total_words": sum(words.values())}
        out["u0_dry_run"] = {s: run_u0(s, True, 1.0) for s in sections}
        out["est_usd"] = {
            "u0": round(sum(words.values()) / 1000 * 0.027, 2),
            "v3": round(sum(words.values()) / 1000 * 0.0165, 2),
            "note": "measured pilot rates incl. canonicalisation; cap --max-usd",
        }
        print(json.dumps(out, indent=1, default=str))
        return
    pre = check_preconditions()
    OUT.mkdir(parents=True, exist_ok=True)
    lock = OUT / "RUN_STARTED.json"
    if not lock.exists():
        lock.write_text(json.dumps({"started": time.strftime("%Y-%m-%d %H:%M:%S"), **pre}))
    spent = 0.0
    for sid in sections:
        done = OUT / f"V3_{sid}.json"
        if done.exists():
            print(sid, "already finished, not repeated")
            continue
        u0 = run_u0(sid, False, a.max_usd)
        spent += float(u0.get("spend_usd", 0))
        v3 = run_v3(sid, a.max_usd)
        spent += v3["meta"]["cost_usd"]
        v3["meta"]["u0_spend_usd"] = u0.get("spend_usd")
        done.write_text(json.dumps(v3))
        print(sid, v3["meta"], "cumulative", round(spent, 3))
        if spent > a.max_usd:
            raise SystemExit(f"stopped: ${spent:.2f} over --max-usd {a.max_usd}")


if __name__ == "__main__":
    main()
