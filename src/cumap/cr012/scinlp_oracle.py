"""CR-012 SciNLP mention-level oracles E1, E3-M and E4-M for ONE document (E2 is NOT_SUPPORTED: SciNLP has no identity gold).

The gold is turned into a SURFACE-level pseudo-gold: one pseudo-concept per distinct normalised surface string (no identity beyond identical text),
mention spans converted from token to character offsets, relations between the pseudo-concepts of their endpoints. The injected information is the
same kind as in P&D: E1 = gold mention spans + types as provisional nodes then the normal canonicalisation, selection and relations;
E3-M = surface nodes (canonicalisation replaced) + normal selection + every gold endpoint pair forced (direction hidden, label hidden);
E4-M = surface nodes + only the gold endpoint pairs. E3-M minus E1 is the post-mention / endpoint-delivery loss.

    uv run python -m cumap.cr012.scinlp_oracle E1 --split dev --doc P05-1008.grobid --tag dry --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import yaml

from cumap.cr012.adapters import SciNLPAdapter, SciNLPDoc
from cumap.cr012.scinlp_run import PARAGRAPH_EVERY, PROFILE, prepare
from cumap.cr012.types import GoldConcept, GoldMention, GoldRelation, UnitGold


def surface_key(s: str) -> str:
    return " ".join(s.casefold().split())


def surface_gold(doc: SciNLPDoc, g: UnitGold) -> tuple[UnitGold, dict]:
    """-> (pseudo-gold with character spans and surface-level concepts, stats)."""
    out = UnitGold(unit=g.unit)
    cid_of: dict[str, str] = {}
    span_cid: dict[tuple[int, int], str] = {}
    type_conflicts = 0
    for m in sorted(g.mentions, key=lambda x: x.span):
        a, b = doc.span_to_chars(m.span)
        key = surface_key(doc.text[a:b])
        if key not in cid_of:
            cid_of[key] = f"S{len(cid_of) + 1:04d}"
            out.concepts.append(GoldConcept(cid_of[key], g.unit, doc.text[a:b], m.type))
        elif next(c.type for c in out.concepts if c.concept_id == cid_of[key]) != m.type:
            type_conflicts += 1
        span_cid[m.span] = cid_of[key]
        out.mentions.append(GoldMention(g.unit, (a, b), m.type, cid_of[key]))
    same_node = 0
    for r in g.relations:
        s, t = span_cid.get(r.src_span), span_cid.get(r.tgt_span)
        if s is None or t is None:
            continue
        if s == t:
            same_node += 1  # both ends share one surface: no pair to classify
            continue
        out.relations.append(GoldRelation(g.unit, r.relation, src_concept=s, tgt_concept=t))
    stats = {
        "gold_mentions": len(g.mentions),
        "surface_nodes": len(out.concepts),
        "gold_relations": len(g.relations),
        "relations_between_distinct_surfaces": len(out.relations),
        "relations_with_identical_endpoint_surface": same_node,
        "surface_type_conflicts": type_conflicts,
    }
    return out, stats


def run(split: str, doc_key: str, oracle: str, tag: str, *, dry_run: bool, max_usd: float) -> dict:
    from cumap.config import get_settings
    from cumap.cr012.oracle_run import run_oracle_unit

    ad = SciNLPAdapter()
    doc = next(
        d for d in ad.load_documents(split, paragraph_every=PARAGRAPH_EVERY) if d.doc_key == doc_key
    )
    info = prepare(split, doc)
    prof = yaml.safe_load(PROFILE.read_text())
    os.environ.update(
        {
            "CUMAP_DEMO_SLICE": info["slice_config"],
            "CUMAP_BENCHMARK_PROFILE": str(PROFILE),
            "CUMAP_RELATION_REGISTRY": prof["relation_registry"],
        }
    )
    get_settings.cache_clear()
    pg, stats = surface_gold(doc, ad.gold(split)[doc_key])
    run_id = f"cr012_scinlp_{tag}_{doc_key.replace('.', '_').replace('-', '_')}_{oracle}"
    out = run_oracle_unit(
        oracle,
        doc_key,
        pg,
        doc.text,
        run_id,
        chapter=1,
        dry_run=dry_run,
        max_usd=max_usd,
        empty_lexicon=True,
        sections_path=Path(info["slice_config"]).with_name("sections.jsonl"),
    )
    return {"surface_gold": stats, **out}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("oracle", choices=["E1", "E3", "E4"])
    ap.add_argument("--split", default="dev")
    ap.add_argument("--doc", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-usd", type=float, default=2.0)
    a = ap.parse_args()
    print(
        json.dumps(
            run(a.split, a.doc, a.oracle, a.tag, dry_run=a.dry_run, max_usd=a.max_usd),
            indent=1,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
