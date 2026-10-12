"""CR-014 fresh P&D benchmark manifest (outcome-blind): 2 pilot + 8 sealed held-out + 8 reserve from the 18 fresh sections.

Uses only chapter and word count from the parsed textbook; no gold, no model output, no prediction. Seeded and deterministic.
    uv run python -m cumap.cr014.manifest   # writes configs/cr014_manifest.yaml"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import yaml

SEED = "cr014-manifest-v1"
CR012_HELD_OUT = {"4.4", "4.5", "5.4", "6.3", "7.1", "8.2", "9.3"}
TINY_WORDS = 1000  # sections below this are reserve-only (too short to be a useful held-out unit)
PILOT_WORDS = (2500, 6600)  # an exhaustive span annotation must be feasible
N_PILOT, N_HELD, MAX_PER_CHAPTER = 2, 8, 2
SRC = Path("data/interim/textbook_sections.jsonl")
OUT = Path("configs/cr014_manifest.yaml")


def pool() -> list[dict]:
    rows = [json.loads(x) for x in SRC.read_text().splitlines()]
    return [
        {"section_id": r["section_id"], "chapter": r["chapter_num"], "words": r["word_count"]}
        for r in rows
        if r["section_id"].count(".") == 1
        and r["section_id"][0].isdigit()
        and (r["chapter_num"] or 0) >= 4
        and r["section_id"] not in CR012_HELD_OUT
    ]


def build() -> dict:
    rng = random.Random(SEED)
    sections = sorted(pool(), key=lambda r: [int(p) for p in r["section_id"].split(".")])
    normal = [r for r in sections if r["words"] >= TINY_WORDS]
    pilot_pool = [r for r in normal if PILOT_WORDS[0] <= r["words"] <= PILOT_WORDS[1]]
    pilot: list[dict] = []
    for r in rng.sample(pilot_pool, len(pilot_pool)):
        if len(pilot) < N_PILOT and all(p["chapter"] != r["chapter"] for p in pilot):
            pilot.append(r)
    rest = [r for r in normal if r not in pilot]
    held: list[dict] = []
    per_ch: dict[int, int] = {}
    for r in rng.sample(rest, len(rest)):
        if len(held) < N_HELD and per_ch.get(r["chapter"], 0) < MAX_PER_CHAPTER:
            held.append(r)
            per_ch[r["chapter"]] = per_ch.get(r["chapter"], 0) + 1
    reserve = [r for r in sections if r not in pilot and r not in held]
    ids = lambda xs: sorted(
        (x["section_id"] for x in xs), key=lambda s: [int(p) for p in s.split(".")]
    )
    body = {
        "version": "cr014-manifest-1",
        "seed": SEED,
        "rule": "pool = ch4-9 numbered sections minus the 7 CR-012 held-out; tiny (<1000 words) reserve-only; pilot 2 from 2500-6600 words, different chapters; held-out 8, at most 2 per chapter; rest reserve. Inputs: chapter + word count only.",
        "pilot": ids(pilot),
        "heldout_sealed": ids(held),
        "reserve": ids(reserve),
        "reserve_replacement_rule": "a reserve section may replace a held-out or pilot section ONLY for a predeclared source/data-quality reason (parse defect, missing text), never for model performance; log the reason here before any prediction.",
    }
    body["sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    return body


if __name__ == "__main__":
    m = build()
    OUT.write_text(yaml.safe_dump(m, sort_keys=False))
    print(yaml.safe_dump(m, sort_keys=False))
