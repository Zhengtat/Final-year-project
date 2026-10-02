"""CR-008 step 3: re-key a finished run ($0) and write snapshots. Usage:
`uv run python -m cumap.expert_kg.cr008_run --run slice3_a1 --new-run slice3_b1`."""

from __future__ import annotations

import argparse
import json

import numpy as np

from cumap.config import REPO_ROOT, get_settings, load_demo_slice
from cumap.expert_kg.canonical_rules import AliasContext
from cumap.expert_kg.lexicon import Lexicon
from cumap.expert_kg.pipeline import Checkpoint, save_checkpoint
from cumap.expert_kg.rekey import RekeyResult, rekey_run
from cumap.expert_kg.roles import SectionText
from cumap.expert_kg.slice_rerun import load_sections, snapshots_stage
from cumap.schemas.relations import RelationRegistry

KG_DIR = REPO_ROOT / "data" / "processed" / "kg"


def build_context(cp: dict, sections, lexicon: Lexicon) -> AliasContext:
    forms = [f for c in cp["concepts"] for f in (c["canonical_name"], *c.get("aliases", []))]
    return AliasContext.build(
        lexicon,
        {s.section_id: s.text for s in sections},
        {s.section_id: s.chapter_num for s in sections},
        forms,
    )


def rekey_stage(src_run: str, new_run: str, *, snapshots: bool = True) -> tuple[RekeyResult, dict]:
    settings = get_settings()
    slice_cfg = load_demo_slice()
    sections = load_sections(REPO_ROOT / slice_cfg.pd.source_jsonl, list(slice_cfg.pd.chapters))
    cp_in = json.loads((KG_DIR / src_run / "checkpoint.json").read_text())
    registry = RelationRegistry.from_yaml(REPO_ROOT / settings.relation_registry)
    ctx = build_context(cp_in, sections, Lexicon.load(REPO_ROOT / "configs" / "term_lexicon.yaml"))
    texts = [SectionText(s.section_id, s.chapter_num, i, s.text) for i, s in enumerate(sections)]
    result = rekey_run(cp_in, ctx, registry, texts, new_run)
    run_dir = KG_DIR / new_run
    cp = Checkpoint(**result.checkpoint)
    cp.stage = "snapshots"
    save_checkpoint(cp, run_dir)
    snap = {}
    if snapshots:
        out = snapshots_stage(cp, run_dir, sections, registry, lambda t: np.zeros(1))
        save_checkpoint(cp, run_dir)
        snap = {"chapters": len(out)}
    return result, snap


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--new-run", required=True)
    a = ap.parse_args()
    result, _ = rekey_stage(a.run, a.new_run)
    print(json.dumps(result.report, indent=2, default=str))


if __name__ == "__main__":
    main()
