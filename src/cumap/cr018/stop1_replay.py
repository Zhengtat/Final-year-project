"""CR-018 STOP 1 ($0, no model call): replay the frozen Track A substrate from saved CR-015 artefacts.

Checks (1) the saved A2 spans are exactly `family_grounded(selected, accepted)` (the seam a new boundary validator would plug into), (2) A2/A0/U0 development scores
reproduce the committed CR-015 numbers, (3) BA1 (selector output placed with no verifier) is computable without a call, and (4) the candidate-to-final waterfall volumes.
Development material only (10 exposed CR-014 sections, model-generated gold).

uv run python -m cumap.cr018.stop1_replay"""

from __future__ import annotations

import json
from pathlib import Path

from cumap.cr015 import placement as PL
from cumap.cr015.dev_data import load_dev
from cumap.cr015.stage_a import OUT, evaluate, unions

REPORT = Path("reports/cr018")


def main() -> dict:
    dev = load_dev()
    us = unions(dev)
    arms: dict[str, dict] = {
        "U0": {},
        "A0": {},
        "A2_saved": {},
        "A2_replayed": {},
        "BA1_selector_only": {},
    }
    vol = {
        "words": 0,
        "candidates": 0,
        "families": 0,
        "multi_member_families": 0,
        "selected_distinct": 0,
        "accepted_distinct": 0,
        "placed_A2": 0,
        "placed_BA1": 0,
    }
    identical = True
    for d in dev:
        s = json.loads((OUT / f"A2_{d.sid}.json").read_text())
        u = us[d.sid]
        selected = {k: set(v) for k, v in s["selected"].items()}
        accepted = set(s["accepted"])
        a2 = PL.family_grounded(u, selected, accepted)
        saved = sorted(tuple(x) for x in s["spans"])
        identical &= sorted(a2) == saved
        all_sel = set().union(*selected.values()) if selected else set()
        ba1 = PL.family_grounded(u, selected, all_sel)
        acc0 = set(d.v3["outcome"]["accepted"])
        arms["U0"][d.sid] = PL.longest_match(d.u0_final, d.text)
        arms["A0"][d.sid] = PL.longest_match(sorted(acc0), d.text)
        arms["A2_saved"][d.sid] = saved
        arms["A2_replayed"][d.sid] = a2
        arms["BA1_selector_only"][d.sid] = ba1
        vol["words"] += d.words
        vol["candidates"] += len(u.cands)
        vol["families"] += len(u.families)
        vol["multi_member_families"] += sum(1 for f in u.families if len(f.members) >= 2)
        vol["selected_distinct"] += len(all_sel)
        vol["accepted_distinct"] += len(accepted)
        vol["placed_A2"] += len(saved)
        vol["placed_BA1"] += len(ba1)
    res = evaluate(arms, dev)
    summary = {}
    for k, v in res.items():
        m = v["mention_span_exact"]
        summary[k] = {
            "P": round(m["precision"], 3), "R": round(m["recall"], 3), "F1": round(m["f1"], 3),
            "nested_gold_recall": round(v["nested_gold_recall"]["recall"], 3),
            "over_long_fp": v["over_long_fp"], "predicted": m.get("predicted"),
        }  # fmt: skip
    out = {"sections": [d.sid for d in dev], "gold_mentions": sum(len(d.gold) for d in dev),
           "a2_spans_equal_family_grounded_replay": identical, "scores": summary, "volumes": vol}  # fmt: skip
    (REPORT / "stop1_replay.json").write_text(json.dumps(out, indent=1, default=str))
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str))
