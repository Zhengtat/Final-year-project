"""CR-015 development data: the exposed CR-014 P&D sections (pilot 4.1/9.2 + sealed-then-exposed held-out), their model-generated gold, the saved frozen-V3 outputs and the
U0 production outputs. Development-only for CR-015; the fresh CR-015 pilot/held-out are loaded elsewhere."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from cumap.cr014.pilot_score import GoldMention, load_gold

ROOT = Path(".")
M14 = yaml.safe_load((ROOT / "configs/cr014_manifest.yaml").read_text())


@dataclass
class DevSection:
    sid: str
    source: str  # "cr014_pilot" | "cr014_heldout"
    row: dict
    gold: list[GoldMention]
    v3: dict  # saved frozen-V3 outcome
    u0_final: list[str]
    u0_raw: list[str]
    words: int = 0
    extra: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        return self.row["text"]


def _section_row(sid: str) -> dict:
    for line in (ROOT / "data/interim/textbook_sections.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["section_id"] == sid:
            return r
    raise KeyError(sid)


def _u0(run_id: str) -> tuple[list[str], list[str]]:
    d = json.loads((ROOT / f"data/processed/kg/{run_id}/v4_concepts.json").read_text())
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


def load_dev() -> list[DevSection]:
    g_pilot = load_gold(
        ROOT / "data/gold/pd_concept_pilot_blind.csv",
        ROOT / "data/interim/checks/cr014/pd_concept_pilot_sentences.csv",
    )
    g_test = load_gold(
        ROOT / "data/gold/pd_concept_test_blind.csv",
        ROOT / "data/interim/checks/cr014/pd_concept_test_sentences.csv",
    )
    out = []
    for src, secs, gold, v3dir, pat in (
        ("cr014_pilot", M14["pilot"], g_pilot, "data/processed/cr014/pilot", "cr014_pilot_{}_U0"),
        (
            "cr014_heldout",
            M14["heldout_sealed"],
            g_test,
            "data/processed/cr014/heldout",
            "cr014_heldout_{}_U0",
        ),
    ):
        for sid in secs:
            row = _section_row(sid)
            v3 = json.loads((ROOT / v3dir / f"V3_{sid}.json").read_text())
            final, raw = _u0(pat.format(sid.replace(".", "_")))
            out.append(
                DevSection(
                    sid,
                    src,
                    row,
                    [m for m in gold if m.section_id == sid],
                    v3,
                    final,
                    raw,
                    len(row["text"].split()),
                )
            )
    return out
