"""CR-015 Stage B: the independent concepthood verifier (B1) and its demonstration-augmented variant (B2), on top of the frozen A2 selector outputs.

Design is frozen in `docs/cr015/STAGE_B_DESIGN.md` (tag cr015-stageb-design-frozen). The verifier answers only 'is this correctly bounded phrase an independently valid technical concept
in context' and never repairs a boundary. The A2 selector is NOT re-run: its saved selected spans are reused, so B arms differ only in the verifier.

    uv run python -m cumap.cr015.validity B1 [--limit N] [--max-usd X]
    uv run python -m cumap.cr015.validity B2 ..."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Literal

from cumap.concepts_v4.schema import _Strict
from cumap.cr014 import v3_core
from cumap.cr014.llm_stage import Usage, candidate_context
from cumap.cr014.union import Cand, SectionUnion
from cumap.cr015 import placement as PL
from cumap.cr015.dev_data import DevSection, load_dev
from cumap.cr015.stage_a import OUT, unions

Verdict = Literal[
    "ACCEPT_NEW",
    "LINK_EXISTING",
    "REJECT_NOT_CONCEPT",
    "REJECT_GENERIC",
    "REJECT_WRONG_SENSE",
    "INSUFFICIENT_EVIDENCE",
]
Reason = Literal["valid_technical_term", "existing_node", "generic_word", "descriptive_phrase", "value_or_example", "discourse_phrase", "wrong_sense", "fragment_or_clause", "unclear_context"]  # fmt: skip
ACCEPT = {"ACCEPT_NEW", "LINK_EXISTING"}
BATCH = 25
DOMAIN = "computer networking"
ROOT = Path(".")
norm = PL.norm


class VerdictLLM(_Strict):
    candidate_id: str
    verdict: Verdict
    node_id: str | None
    reason_code: Reason


class ValidityBatchLLM(_Strict):
    verdicts: list[VerdictLLM]


def build_bank(dev: list[DevSection], us: dict[str, SectionUnion]) -> dict:
    """Development demonstration bank: gold spans the frozen A2 verifier accepted (positives); candidate spans that overlap no gold span and the A2 verifier rejected (negatives)."""
    import hashlib

    pos, neg = [], []
    for d in dev:
        u = us[d.sid]
        a2 = json.loads((OUT / f"A2_{d.sid}.json").read_text())
        gold = [(m.start, m.end) for m in d.gold]
        accepted = set(a2["accepted"])
        verd = {s: v.get("verdict", "") for s, v in a2["verdicts"].items()}
        for s, e in sorted(set(gold)):
            surf = norm(d.text[s:e])
            if surf in accepted and len(pos) < 100000:
                si = next((i for i, (a, b) in enumerate(u.sents) if a <= s < b), None)
                if si is not None:
                    pos.append(
                        {
                            "section": d.sid,
                            "surface": surf,
                            "start": s,
                            "end": e,
                            "sentence_idx": si,
                            "head": surf.split()[-1],
                            "n": len(surf.split()),
                        }
                    )
        for surf, v in verd.items():
            if not v.startswith("REJECT"):
                continue
            c = u.cands.get(surf)
            if c is None or not c.occurrences:
                continue
            if any(a < ge and gs < b for a, b, _ in c.occurrences for gs, ge in gold):
                continue
            a, b, si = c.occurrences[0]
            neg.append(
                {
                    "section": d.sid,
                    "surface": surf,
                    "start": a,
                    "end": b,
                    "sentence_idx": si,
                    "head": surf.split()[-1],
                    "n": len(surf.split()),
                    "verdict": v,
                }
            )
    bank = {"positives": pos, "negatives": neg}
    bank["sha256"] = hashlib.sha256(json.dumps([pos, neg], sort_keys=True).encode()).hexdigest()
    return bank


def _demo_line(u_by_sec: dict[str, SectionUnion], e: dict, label: str) -> str:
    u = u_by_sec[e["section"]]
    s0, s1 = u.sents[e["sentence_idx"]]
    t = u.text
    sent = re.sub(
        r"\s+", " ", t[s0 : e["start"]] + "<<" + t[e["start"] : e["end"]] + ">>" + t[e["end"] : s1]
    )
    return f"- {sent[:360]}\n  -> {label}"


def demonstrations(
    bank: dict, u_by_sec, section: str, spans: list[Cand], key: str, rec: dict, per_side: int = 5
) -> str:
    want = {(c.surface.split()[-1], c.token_length) for c in spans[:60]}
    picked: list[tuple[str, dict]] = []
    seen = set()
    for side, label in (("positives", "VALID technical concept"), ("negatives", None)):
        got = []
        for head, n in sorted(want):
            best = sorted(
                (e for e in bank[side] if e["section"] != section),
                key=lambda e: (
                    -(2 * (e["head"] == head) + 1.5 * (e["n"] == n) - 0.25 * abs(e["n"] - n)),
                    e["surface"],
                    e["start"],
                ),
            )[:1]
            for e in best:
                k = (side, e["section"], e["start"])
                if k not in seen:
                    seen.add(k)
                    got.append(e)
        for e in got[:per_side]:
            picked.append((label or f"NOT a concept ({e['verdict']})", e))
    rec[key] = [
        {"section": e["section"], "surface": e["surface"], "start": e["start"], "label": lab}
        for lab, e in picked
    ]
    return "\n".join(_demo_line(u_by_sec, e, lab) for lab, e in picked) or "(none)"


def render(
    u: SectionUnion,
    spans: list[Cand],
    fam_info: dict[str, list[str]],
    extra: dict[str, str],
    cfg: dict,
) -> str:
    ctx = cfg["context"]
    lines = []
    for c in spans:
        co = "; ".join(fam_info.get(c.surface, [])[:6]) or "none"
        text = candidate_context(
            u, c, ctx["max_sentences_per_candidate"], ctx["max_chars_per_sentence"]
        )
        lines.append(f"{c.cid} | {c.surface} | {co} | none | {extra[c.cid]} | {text}")
    return "\n".join(lines)


def run(arm: str, limit: int | None, max_usd: float) -> None:
    from cumap.config import get_settings
    from cumap.llm.client import LLMClient
    from cumap.llm.prompts import load_prompt

    dev = load_dev()
    us = unions(dev)
    prompt = load_prompt(ROOT / "prompts", "cr015_concept_validity", "v2" if arm == "B2" else "v1")
    bank = build_bank(dev, us) if arm == "B2" else None
    if bank:
        (OUT / "validity_bank_meta.json").write_text(
            json.dumps(
                {
                    "sha256": bank["sha256"],
                    "positives": len(bank["positives"]),
                    "negatives": len(bank["negatives"]),
                }
            )
        )
    client = LLMClient(get_settings(), run_id=f"cr015_stageB_{arm}")
    client._settings.llm.max_output_tokens["cr015_concept_validity"] = 6000
    cfg = v3_core.SB
    spent, t_all = 0.0, time.time()
    for d in dev[:limit] if limit else dev:
        path = OUT / f"{arm}_{d.sid}.json"
        if path.exists():
            continue
        u = us[d.sid]
        a2 = json.loads((OUT / f"A2_{d.sid}.json").read_text())
        selected = {k: set(v) for k, v in a2["selected"].items()}
        fam_info: dict[str, list[str]] = {}
        spans: dict[str, Cand] = {}
        n_new = 0
        for fid in sorted(selected):
            for s in sorted(selected[fid]):
                fam_info.setdefault(s, [x for x in sorted(selected[fid]) if x != s])
                if s not in spans:
                    c = v3_core.new_span_cand(u, s, n_new)
                    if c is None:
                        continue
                    if "#s" in c.cid:
                        n_new += 1
                    spans[s] = c
        fe, sc = v3_core.onetoken_features(u, d.sid), v3_core.onetoken_scores(u, d.sid)
        cs = sorted(spans.values(), key=lambda c: (c.token_length != 1, -sc.get(c.cid, 0.0), c.cid))
        extra = {
            c.cid: (
                v3_core.evidence_text(c, fe[c.cid]) if c.cid in fe else "evidence: n/a (multi-word)"
            )
            for c in cs
        }
        usage, t0, c0, verdicts, rec = Usage(), time.time(), client.spent_usd, {}, {}
        for i in range(0, len(cs), BATCH):
            batch = cs[i : i + BATCH]
            kw = {
                "domain": DOMAIN,
                "heading_path": d.sid,
                "candidates": render(u, batch, fam_info, extra, cfg),
            }
            if bank is not None:
                kw["demonstrations"] = demonstrations(
                    bank, {x.sid: us[x.sid] for x in dev}, d.sid, batch, f"{d.sid}[{i}]", rec
                )
            try:
                r = client.parse(task=prompt.task, prompt_version=prompt.version, messages=[{"role": "user", "content": prompt.render(**kw)}], schema=ValidityBatchLLM, model_tier="bulk", allow_escalation=False)  # fmt: skip
            except Exception as e:  # noqa: BLE001
                usage.errors.append(f"{d.sid}[{i}]: {type(e).__name__}: {str(e)[:140]}")
                continue
            usage.calls += 1
            known = {c.cid: c.surface for c in batch}
            for v in r.output.verdicts:
                if v.candidate_id in known and known[v.candidate_id] not in verdicts:
                    verdicts[known[v.candidate_id]] = v.model_dump()
        accepted = {s for s, v in verdicts.items() if v["verdict"] in ACCEPT}
        placed = PL.family_grounded(u, selected, accepted)
        meta = {"section": d.sid, "calls": usage.calls, "errors": usage.errors, "cost_usd": round(client.spent_usd - c0, 4), "seconds": round(time.time() - t0, 1), "spans_verified": len(cs), "prompt": prompt.version, "bank_sha256": bank["sha256"] if bank else None}  # fmt: skip
        path.write_text(
            json.dumps(
                {
                    "meta": meta,
                    "selected": {k: sorted(v) for k, v in selected.items()},
                    "decisions": {},
                    "accepted": sorted(accepted),
                    "verdicts": verdicts,
                    "spans": placed,
                    "invalid_targets": [],
                    "unanswered": [s for s in spans if s not in verdicts],
                    "retrieval": rec,
                }
            )
        )
        spent += meta["cost_usd"]
        print(arm, d.sid, meta["calls"], meta["cost_usd"], meta["seconds"], flush=True)
        if spent > max_usd:
            raise SystemExit(f"stopped: ${spent:.2f} over --max-usd {max_usd}")
    print("done", arm, round(spent, 3), round(time.time() - t_all), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("arm", choices=["B1", "B2"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--max-usd", type=float, default=2.0)
    a = ap.parse_args()
    run(a.arm, a.limit, a.max_usd)
