"""CR-009 §7.1: run the comparison arms (C-SAC, C-PiVe, C-PiVe-off, C-ConExion) on a split and score them.
`uv run python -m cumap.concepts_v4.arms_dev --split dev --run-id dev1`. The test split is run ONCE, after STOP 2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import spacy

from cumap.concepts_v4 import arms as A
from cumap.concepts_v4 import experiments as X
from cumap.expert_kg.face_scorer import load_gold_concepts
from cumap.llm.prompts import load_prompt
from cumap.schemas.relations import RelationRegistry

ROOT = Path(".")


def load_split(split: str) -> tuple[list[dict], Path]:
    if split == "dev":
        secs, _ = X.load_dev()
        return secs, X.DEV_GOLD
    secs = [
        json.loads(x)
        for x in (ROOT / "data/interim/external/iir_test_sections_v3.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if x
    ]
    for s in secs:
        s["order_index"] = int(s["order_index"])
        s["chapter_num"] = str(s["chapter_num"])
        s["heading"] = str(s.get("heading_path") or s["section_id"])
    return sorted(
        secs, key=lambda s: s["order_index"]
    ), ROOT / "data/interim/external/iir_test_gold_concepts_v3.csv"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--run-id", default="dev1")
    ap.add_argument("--arms", nargs="+", default=["C-SAC", "C-PiVe", "C-ConExion"])
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    from cumap.config import get_settings
    from cumap.llm.client import LLMClient

    settings = get_settings()
    nlp = spacy.load("en_core_web_sm")
    embed = X.Embedder(settings.embeddings.model)
    sections, gold_path = load_split(a.split)
    dev_secs, _ = X.load_dev()
    sections = sections[: a.limit] if a.limit else sections
    gold = load_gold_concepts(gold_path)
    gnm_all = {}
    for g in load_gold_concepts(X.DEV_GOLD):
        gnm_all.setdefault(g.section_id, []).append(g.concept)
    registry = RelationRegistry.from_yaml(ROOT / settings.relation_registry)
    base = load_prompt(ROOT / "prompts", "concept_extraction", "v2")
    pruners = X.loco_pruners(dev_secs, nlp, embed)
    pf = lambda ch: pruners[str(ch)].p_growing if str(ch) in pruners else pruners["all"].p_growing
    client = LLMClient(settings, run_id=f"cr009_arms_{a.split}")
    out_dir = X.OUT / a.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    scores = {}
    texts = {s["section_id"]: s["text"] for s in sections}
    from cumap.expert_kg.partial_span import chunk_counts

    by_ch: dict[str, list[str]] = {}
    for s in sections:
        by_ch.setdefault(str(s["chapter_num"]), []).append(s["text"])
    rec = {ch: chunk_counts(ts, nlp) for ch, ts in by_ch.items()}

    def keep(name, arm):
        finals = A.finals_of(arm)
        sc = X.score(finals, gold, sections, nlp, embed)
        sc["calls"] = sum(s.calls for s in arm)
        scores[name] = sc
        (out_dir / f"{name}_{a.split}.json").write_text(
            json.dumps(
                {"scores": sc, "sections": [s.__dict__ for s in arm]}, indent=1, default=str
            ),
            encoding="utf-8",
        )
        e = sc["exact_micro"]
        print(
            f"{name}: pred {sc['n_predicted']} exact P/R/F1 {e['precision']:.3f}/{e['recall']:.3f}/{e['f1']:.3f} lenient {sc['lenient_micro']['f1']:.3f} calls {sc['calls']}"
        )

    if "C-SAC" in a.arms:
        keep("C-SAC", A.run_c_sac(client, base, registry, nlp, sections, pruner_for=pf, tau=0.5))
    if "C-PiVe" in a.arms:
        on, off = A.run_c_pive(client, base, registry, nlp, sections, recurring_by_chapter=rec)
        keep("C-PiVe", on)
        keep("C-PiVe-off", off)
    if "C-ConExion" in a.arms:
        keep("C-ConExion", A.run_c_conexion(client, sections, gnm_all))
    print(f"spend ${client.spent_usd:.4f}")
    (out_dir / f"arms_{a.split}_scores.json").write_text(
        json.dumps(scores, indent=1, default=str), encoding="utf-8"
    )
    del texts


if __name__ == "__main__":
    main()
