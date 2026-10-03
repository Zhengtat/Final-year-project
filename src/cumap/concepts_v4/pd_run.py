"""CR-009 §8 (steps 1-2) and §6.1: run the v4 concept stage on P&D, canonicalise, and hand the result to the existing
pipeline as a Checkpoint (concepts with mentions, plus the ANCHORS that set relation-pair priority).

  1. long sections are split into paragraph chunks of <= `max_words` (a 11,700-word section cannot fit one structured
     answer); a chunk is a "unit" with its own order, mentions map back to the real section id;
  2. generator -> verifier -> pruner per unit (backfill at each chapter end), cards from earlier units of this run;
  3. canonicalisation of the growing NEW nodes: R0 lexicon -> R1-R3 -> R4 LLM (CR-008), against the registry built so
     far; a generator link (existing mention) is already a merge and is logged `G-link`;
  4. a Checkpoint the unchanged stages (select, relations, snapshots, organise) can read.
Anchors are never edges and are never shown to the relation generator or verifier."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from cumap.concepts_v4.cards import split_paragraphs
from cumap.concepts_v4.runner import RunOutput
from cumap.expert_kg.canonical_rules import AliasContext
from cumap.expert_kg.canonicalize import (
    CanonicalOverrides,
    ConceptRegistry,
    Mention,
    canonicalize_mention,
)
from cumap.expert_kg.concepts import ConceptMentionCandidate
from cumap.expert_kg.lexicon import Lexicon
from cumap.expert_kg.mentions import MentionMatcher
from cumap.expert_kg.pipeline import Checkpoint, _concept_to_dict
from cumap.llm.client import LLMClient
from cumap.llm.prompts import PromptTemplate


def make_units(sections: list[dict], max_words: int = 2500) -> list[dict]:
    """Sections as processing units; a section longer than `max_words` becomes consecutive paragraph chunks."""
    units: list[dict] = []
    for s in sorted(sections, key=lambda x: x["order_index"]):
        paras = [p for p in re.split(r"\n\s*\n", s["text"]) if p.strip()]
        if len(s["text"].split()) <= max_words:
            groups = [paras]
        else:
            groups, cur, n = [], [], 0
            for p in paras:
                w = len(p.split())
                if cur and n + w > max_words:
                    groups.append(cur)
                    cur, n = [], 0
                cur.append(p)
                n += w
            groups.append(cur)
        for k, g in enumerate(groups, 1):
            sid = s["section_id"] if len(groups) == 1 else f"{s['section_id']}#{k}"
            units.append(
                {
                    **s,
                    "section_id": sid,
                    "orig_section": s["section_id"],
                    "text": "\n\n".join(g),
                    "order_index": len(units),
                    "heading": s.get("heading")
                    or " > ".join(s.get("heading_path") or [s["section_id"]]),
                    "chunk": k,
                    "chunks": len(groups),
                }
            )
    return units


@dataclass
class CanonResult:
    registry: ConceptRegistry
    node_map: dict[str, str]
    merges: list[dict]
    taxonomy: list[dict]
    review: list[dict]
    related: list[dict]
    llm_calls: int


def canonicalise(
    out: RunOutput,
    units: list[dict],
    lexicon: Lexicon | None,
    client: LLMClient,
    prompt: PromptTemplate,
    embed_fn,
    overrides: CanonicalOverrides | None,
    *,
    progress=print,
) -> CanonResult:
    """R0-R4 over the v4 nodes in book order. A node whose first mention merges into an existing concept maps to it."""
    orig = {u["section_id"]: u["orig_section"] for u in units}
    chapter_of = {u["orig_section"]: int(u["chapter_num"]) for u in units}
    texts: dict[str, str] = {}
    for u in units:
        texts[u["orig_section"]] = (texts.get(u["orig_section"], "") + "\n\n" + u["text"]).strip()
    forms = [f for n in out.store.nodes.values() for f in n.forms()]
    ctx = AliasContext.build(lexicon, texts, chapter_of, forms) if lexicon is not None else None
    reg = ConceptRegistry(embed_fn)
    node_map: dict[str, str] = {}
    merges, taxonomy, review, related = [], [], [], []
    calls0 = client.backend_call_count
    for n in sorted(out.store.nodes.values(), key=lambda x: (x.first_order, x.id)):
        first = (
            min(n.mentions, key=lambda m: m["order"])
            if n.mentions
            else {"section_id": n.first_section, "role": "used", "evidence": n.name, "para": "P1"}
        )
        sid = orig.get(first["section_id"], first["section_id"])
        mention = ConceptMentionCandidate(
            canonical_name=n.name,
            node_type=n.node_type,
            role=first["role"] if first["role"] in {"defined", "used", "mentioned"} else "used",
            definition=n.definition,
            evidence_quote=first["evidence"],
            section_id=sid,
        )
        o = canonicalize_mention(
            client,
            prompt,
            reg,
            mention,
            overrides=overrides,
            type_aware=True,
            review_below=0.70,
            alias_ctx=ctx,
        )
        node_map[n.id] = o.concept_id
        concept = reg.get(o.concept_id)
        for a in (
            n.aliases
        ):  # aliases the generator linked (G-links) and aliases it gave the new concept
            if a != concept.canonical_name and a not in concept.aliases:
                concept.aliases.append(a)
        if o.decision == "same":
            merges.append(
                {
                    "concept_id": o.concept_id,
                    "alias": n.name,
                    "section_id": sid,
                    "llm_called": o.llm_called,
                    "auto_merged": o.auto_merged,
                    "overridden": o.overridden,
                    "reason": o.reason,
                    "similarity": o.similarity,
                    "rule_id": o.rule_id,
                    "evidence_quote": o.evidence_quote,
                    "stage": "canonicalize_v4",
                }
            )
        elif o.decision == "review":
            cand = reg.get(o.matched_concept_id)
            review.append(
                {
                    "concept_id": o.concept_id,
                    "candidate_id": cand.concept_id,
                    "candidate_name": cand.canonical_name,
                    "candidate_type": cand.node_type,
                    "candidate_definition": cand.definition,
                    "alias": n.name,
                    "mention_type": n.node_type,
                    "quote": first["evidence"],
                    "section_id": sid,
                    "similarity": o.similarity,
                    "llm_reason": o.reason,
                }
            )
        elif o.decision in ("narrower", "broader") and o.matched_concept_id:
            taxonomy.append(
                {
                    "concept_id": o.concept_id,
                    "matched_concept_id": o.matched_concept_id,
                    "decision": o.decision,
                    "reason": o.reason,
                    "section_id": sid,
                }
            )
        for rid in o.related_ids:
            related.append(
                {"concept_id": o.concept_id, "related_concept_id": rid, "section_id": sid}
            )
    # every later mention (generator links and backfill) goes onto the mapped concept
    for n in out.store.nodes.values():
        concept = reg.get(node_map[n.id])
        firstm = min(n.mentions, key=lambda m: m["order"]) if n.mentions else None
        for m in n.mentions:
            if m is firstm:
                continue
            concept.mentions.append(
                Mention(
                    orig.get(m["section_id"], m["section_id"]),
                    m["role"] if m["role"] != "refined" else "refined",
                    m["evidence"],
                    None,
                    "llm" if m["linked_by"] == "generator" else m["linked_by"],
                )
            )
    for g in out.merges:  # generator links: logged with their evidence
        if g["node_id"] in node_map:
            merges.append(
                {
                    "concept_id": node_map[g["node_id"]],
                    "alias": g["surface"],
                    "section_id": orig.get(g["section_id"], g["section_id"]),
                    "llm_called": False,
                    "auto_merged": False,
                    "overridden": False,
                    "reason": None,
                    "similarity": None,
                    "rule_id": "G-link",
                    "evidence_quote": g["evidence"],
                    "stage": "generator",
                }
            )
    progress(
        f"canonicalised {len(out.store.nodes)} v4 nodes -> {len(reg)} concepts ({client.backend_call_count - calls0} LLM calls)"
    )
    return CanonResult(
        reg, node_map, merges, taxonomy, review, related, client.backend_call_count - calls0
    )


def anchor_records(
    out: RunOutput, res: CanonResult, units: list[dict], reg_texts: dict[str, str]
) -> list[dict]:
    """Anchors of every new node, re-keyed to concept ids, in book order. `both_in_cue`: the cue names both ends."""
    orig = {u["section_id"]: u["orig_section"] for u in units}
    recs = []
    for n in sorted(out.store.nodes.values(), key=lambda x: (x.first_order, x.id)):
        for a in n.anchors:
            x, y = res.node_map[n.id], res.node_map.get(a["node_id"])
            if y is None or x == y:
                continue
            cx, cy = res.registry.get(x), res.registry.get(y)
            cue = a["cue"]
            both = all(
                any(f.lower() in cue.lower() for f in c.aliases + [c.canonical_name])
                for c in (cx, cy)
            )
            recs.append(
                {
                    "concept_id": x,
                    "anchor_id": y,
                    "anchor_type": a["anchor_type"],
                    "cue": cue,
                    "section_id": orig.get(a.get("section_id"), a.get("section_id")),
                    "both_in_cue": both,
                    "found_via_anchor": n.found_via_anchor,
                }
            )
    return recs


def build_checkpoint(
    run_id: str, out: RunOutput, res: CanonResult, units: list[dict], texts_by_orig: dict[str, str]
) -> Checkpoint:
    cp = Checkpoint(run_id=run_id, stage="pairs_enumerated")
    cp.concepts = [_concept_to_dict(c) for c in res.registry.all()]
    cp.merges, cp.taxonomy_candidates, cp.merge_review, cp.related_candidates = (
        res.merges,
        res.taxonomy,
        res.review,
        res.related,
    )
    cp.anchors = anchor_records(out, res, units, texts_by_orig)
    return cp


__all__ = ["MentionMatcher", "Path", "split_paragraphs"]
