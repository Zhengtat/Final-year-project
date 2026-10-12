"""CR-015 fresh split manifest (outcome-blind): pilot + sealed held-out drawn from the 8 sections verified untouched at STOP 1.

Inputs are chapter and word count only; no gold, no model output. The constraints leave no free choice (only 6 sections are >= 1000 words; the pilot window fits exactly two),
so the draw is deterministic and the seed is recorded for completeness.
    uv run python -m cumap.cr015.manifest"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import yaml

SEED = "cr015-manifest-v1"
UNTOUCHED = [
    "4.3",
    "5.1",
    "5.2",
    "6.2",
    "6.5",
    "8.1",
    "9.1",
    "9.4",
]  # CR-014 reserve, verified untouched (reports/cr015/contamination_audit.md)
TINY = 1000
PILOT_WORDS = (2500, 6600)
N_PILOT = 2
OUT = Path("configs/cr015_manifest.yaml")


def build() -> dict:
    rows = {}
    for line in Path("data/interim/textbook_sections.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["section_id"] in UNTOUCHED:
            rows[r["section_id"]] = {"words": r["word_count"], "chapter": r["chapter_num"]}
    usable = [s for s in UNTOUCHED if rows[s]["words"] >= TINY]
    cand = [s for s in usable if PILOT_WORDS[0] <= rows[s]["words"] <= PILOT_WORDS[1]]
    rng = random.Random(SEED)
    pilot = sorted(
        rng.sample(cand, min(N_PILOT, len(cand))), key=lambda s: [int(x) for x in s.split(".")]
    )
    held = [s for s in usable if s not in pilot]
    reserve = [s for s in UNTOUCHED if s not in pilot and s not in held]
    body = {
        "version": "cr015-manifest-1", "seed": SEED,
        "rule": "pool = the 8 CR-014 reserve sections verified untouched; sections < 1000 words are reserve-only; pilot = the (up to) 2 sections of 2500-6600 words; held-out = every other usable section. Inputs: chapter + word count only.",
        "words": {s: rows[s]["words"] for s in UNTOUCHED}, "pilot": pilot, "heldout_sealed": held, "reserve": reserve,
        "heldout_words": sum(rows[s]["words"] for s in held), "pilot_words": sum(rows[s]["words"] for s in pilot),
        "replacement_rule": "a section may be replaced only for a predeclared source/data-quality reason, never for model performance; log it here before any prediction",
        "no_redraw": "this manifest is frozen once; no redraw",
    }  # fmt: skip
    body["sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    return body


if __name__ == "__main__":
    m = build()
    OUT.write_text(yaml.safe_dump(m, sort_keys=False))
    print(yaml.safe_dump(m, sort_keys=False))
