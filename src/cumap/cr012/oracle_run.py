"""CR-012 oracle runs E1-E4 for ONE P&D-E2E unit, through the unchanged production stages. Each oracle injects information only into the stage it
replaces (see `oracle.py`); the gold relation label and direction never reach the classifier.

    E1  gold mention spans + types as provisional nodes (one per distinct surface, no identity) -> normal canonicalisation, selection, relations
    E2  gold concepts WITH identity (names, aliases, types) -> normal selection, relations (canonicalisation replaced)
    E3  E2 + every gold endpoint pair forced into relation classification, pair order sorted (direction hidden), label hidden
    E4  only the gold endpoint pairs are classified (classifier predicts relation, direction, qualifiers on its own)

Evidence sentence of a forced pair: the sentence where both concepts are mentioned; else the two nearest sentences; else (counted) the sentence
the gold annotator cited. Gold pair evidence is location only, never a label.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import asdict
from pathlib import Path

from cumap.config import REPO_ROOT, get_settings
from cumap.cr012 import oracle as O
from cumap.cr012 import pd_e2e as PD
from cumap.cr012.budget import pair_budget
from cumap.cr012.types import UnitGold
from cumap.cr012.unit_run import prepare
from cumap.expert_kg.canonicalize import Mention, RegisteredConcept, slugify
from cumap.expert_kg.mentions import MentionMatcher
from cumap.expert_kg.pipeline import Checkpoint, _concept_to_dict, save_checkpoint
from cumap.expert_kg.relations import CandidatePair, concept_vocab

KG = REPO_ROOT / "data/processed/kg"


def sentence_of(offsets: list[tuple[int, int]], pos: int) -> int:
    for i, (a, b) in enumerate(offsets):
        if a <= pos < b:
            return i
    return min(
        range(len(offsets)), key=lambda i: min(abs(offsets[i][0] - pos), abs(offsets[i][1] - pos))
    )


def gold_registry(gold: UnitGold, text: str) -> tuple[list[RegisteredConcept], dict[str, str]]:
    """E2 nodes: one concept per gold concept, aliases = every observed surface + the annotator's aliases. -> (concepts, gold id -> registry id)."""
    offs = PD.sentence_offsets(text)
    sents = [text[a:b] for a, b in offs]
    by_c: dict[str, list] = {}
    for m in gold.mentions:
        by_c.setdefault(m.concept_id, []).append(m)
    out, idmap, used = [], {}, set()
    for c in gold.concepts:
        cid = "c_" + slugify(c.concept_id.split(":", 1)[-1])
        while cid in used:
            cid += "_"
        used.add(cid)
        idmap[c.concept_id] = cid
        ms = by_c.get(c.concept_id, [])
        surfaces = sorted({text[m.span[0] : m.span[1]] for m in ms} | set(c.aliases) | {c.name})
        mentions = [
            Mention(gold.unit, "used", sents[sentence_of(offs, m.span[0])], None, "llm") for m in ms
        ]
        out.append(
            RegisteredConcept(
                cid, c.name, c.type, None, gold.unit, [s for s in surfaces if s != c.name], mentions
            )
        )
    return out, idmap


def forced_pairs(
    gold: UnitGold, text: str, concepts: list[RegisteredConcept], idmap: dict[str, str]
) -> tuple[list[dict], dict]:
    """The E3 / E4 endpoint pairs as CandidatePair dicts: sorted order (direction hidden), no relation label anywhere."""
    offs = PD.sentence_offsets(text)
    sents = [text[a:b] for a, b in offs]
    matcher = MentionMatcher(concept_vocab(concepts))
    where: dict[str, set[int]] = {}
    for m in matcher.find(text):
        where.setdefault(m.concept_id, set()).add(sentence_of(offs, m.start))
    cited = {}
    for r in gold.relations:
        cited.setdefault(frozenset((r.src_concept, r.tgt_concept)), None)
    seen, pairs, stats = (
        set(),
        [],
        {"same_sentence": 0, "adjacent_sentences": 0, "gold_cited_sentence": 0},
    )
    sid_of = {c.concept_id: idmap[c.concept_id] for c in gold.concepts}
    ev_by_pair = _gold_evidence_ids(gold)
    for r in gold.relations:
        key = frozenset((r.src_concept, r.tgt_concept))
        if key in seen:
            continue
        seen.add(key)
        a, b = sorted((sid_of[r.src_concept], sid_of[r.tgt_concept]))
        sa, sb = where.get(a, set()), where.get(b, set())
        both = sorted(sa & sb)
        near = sorted((min(x, y), max(x, y)) for x in sa for y in sb if abs(x - y) == 1)
        if both:
            sentence, kind = sents[both[0]], "same_sentence"
        elif near:
            sentence, kind = " ".join(sents[near[0][0] : near[0][1] + 1]), "adjacent_sentences"
        else:
            ids = ev_by_pair.get(key) or [0]
            sentence, kind = " ".join(sents[i] for i in ids[:2]), "gold_cited_sentence"
        stats[kind] += 1
        pairs.append(
            asdict(
                CandidatePair(
                    pair_id=f"RP-{gold.unit}-g{len(pairs)}",
                    section_id=gold.unit,
                    concept_x_id=a,
                    concept_y_id=b,
                    sentence=sentence,
                    cooccurrence_count=1,
                    cue_score=0,
                )
            )
        )
    return pairs, stats


def _gold_evidence_ids(gold: UnitGold) -> dict:
    """Sentence indices the annotator cited for each concept pair (used only to LOCATE evidence when the two concepts never meet in the text)."""
    out: dict = {}
    for r in gold.relations:
        out.setdefault(
            frozenset((r.src_concept, r.tgt_concept)),
            [int(e[1:]) - 1 for e in r.evidence if e[1:].isdigit()],
        )
    return out


def checkpoint_for(
    oracle: str, sid: str, gold: UnitGold, text: str, run_id: str
) -> tuple[Checkpoint, dict]:
    concepts, idmap = gold_registry(gold, text)
    cp = Checkpoint(run_id=run_id, stage="pairs_enumerated")
    cp.concepts = [_concept_to_dict(c) for c in concepts]
    info: dict = {"concepts": len(concepts), "mentions": len(gold.mentions)}
    if oracle in {"E3", "E4"}:
        pairs, stats = forced_pairs(gold, text, concepts, idmap)
        info["forced_pairs"], info["evidence_for_forced_pairs"] = len(pairs), stats
        info["_forced"] = pairs
    return cp, info


def assert_no_leak(pairs: list[dict], gold: UnitGold) -> None:
    for p in pairs:
        assert not (set(p) & O.FORBIDDEN_VISIBLE_KEYS), p
        assert all(r.relation not in json.dumps(p) for r in gold.relations), (
            "a gold relation label is visible in a forced pair"
        )


def run_oracle(
    oracle: str, sid: str, pilot_sheet: Path, *, dry_run: bool, max_usd: float, tag: str = "pilot"
) -> dict:
    info = prepare(sid)
    os.environ["CUMAP_DEMO_SLICE"] = info["slice_config"]
    secs = {r["section_id"]: r["text"] for r in PD.load_sections()}
    gold, problems = PD.load_gold(pilot_sheet, secs, PD.registry())
    assert not problems, problems[:3]
    return run_oracle_unit(
        oracle,
        sid,
        gold[sid],
        secs[sid],
        f"cr012_{tag}_{sid.replace('.', '_')}_{oracle}",
        chapter=int(sid.split(".")[0]),
        dry_run=dry_run,
        max_usd=max_usd,
    )


def run_oracle_unit(
    oracle: str,
    sid: str,
    g: UnitGold,
    text: str,
    run_id: str,
    *,
    chapter: int,
    dry_run: bool,
    max_usd: float,
    empty_lexicon: bool = False,
    sections_path: Path | None = None,
) -> dict:
    """The oracle body for any unit whose slice file is already active (`CUMAP_DEMO_SLICE`). `empty_lexicon` is the SciNLP profile (no identity
    lexicon, no canonical overrides)."""
    from cumap.concepts_v4 import cr009_run as R
    from cumap.concepts_v4 import experiments as X
    from cumap.expert_kg import slice_rerun as sr
    from cumap.llm.cost import spend_from_log
    from cumap.schemas.relations import RelationRegistry

    settings = get_settings()
    sections = sr.load_sections(
        sections_path or REPO_ROOT / "data/interim/cr012/units" / sid / "sections.jsonl", [chapter]
    )
    out: dict = {"run_id": run_id, "oracle": oracle, "section": sid}
    if oracle == "E1":
        out.update(
            e1(
                sid, g, text, run_id, sections, dry_run=dry_run, max_usd=max_usd,
                chapter=chapter, empty_lexicon=empty_lexicon,
            )
        )  # fmt: skip
        if dry_run:
            return out
    else:
        cp, info2 = checkpoint_for(oracle, sid, g, text, run_id)
        forced = info2.pop("_forced", [])
        out.update(info2)
        embed = X.Embedder(settings.embeddings.model)
        sr.finish_concepts(cp, sections, embed)
        registry = RelationRegistry.from_yaml(REPO_ROOT / settings.relation_registry)
        words = len(text.split())
        if oracle == "E4":
            cp.selected_pairs, cp.sample_pairs = forced, []
            cp.selection_stats = {"oracle": "E4 gold endpoint pairs only"}
        else:
            stats = sr.select_stage(
                cp,
                sections,
                registry,
                embed,
                budget=math.ceil(14.2 * words / 1000),
                sample=0,
                use_anchors=True,
            )
            b = pair_budget(words, stats["unique_candidate_pairs"])
            out["budget_record"] = {
                "word_count": words,
                "eligible_candidate_pairs": stats["unique_candidate_pairs"],
                "budget": b,
                "selected_pairs": stats["selected"],
            }
            if oracle == "E3":
                have = {
                    frozenset((p["concept_x_id"], p["concept_y_id"])) for p in cp.selected_pairs
                }
                extra = [
                    p
                    for p in forced
                    if frozenset((p["concept_x_id"], p["concept_y_id"])) not in have
                ]
                out["forced_already_selected"], out["forced_added"] = (
                    len(forced) - len(extra),
                    len(extra),
                )
                cp.selected_pairs = [*cp.selected_pairs, *extra]
        if forced:
            assert_no_leak(forced, g)
        cp.stage = "relations"
        run_dir = KG / run_id
        save_checkpoint(cp, run_dir)
        out["pairs_to_classify"] = len(cp.selected_pairs)
        pre = sr.preflight_relations(cp)
        out["preflight"] = pre
        if dry_run:
            return out
        out["relations"] = R.stage_relations(run_id, dry_run=False, max_usd=max_usd)
    out["spend_usd"] = round(spend_from_log(settings, run_id), 4)
    return out


def e1(
    sid: str,
    g: UnitGold,
    text: str,
    run_id: str,
    sections,
    *,
    dry_run: bool,
    max_usd: float,
    chapter: int | None = None,
    empty_lexicon: bool = False,
) -> dict:
    """Gold mentions + types as provisional nodes (one per distinct surface), then the production canonicalisation, selection and relations."""
    from cumap.concepts_v4 import cr009_run as R
    from cumap.concepts_v4 import experiments as X
    from cumap.concepts_v4 import pd_run as P
    from cumap.concepts_v4.cards import Node, NodeStore
    from cumap.concepts_v4.runner import RunOutput
    from cumap.expert_kg import slice_rerun as sr
    from cumap.expert_kg.canonicalize import CanonicalOverrides
    from cumap.expert_kg.lexicon import Lexicon
    from cumap.expert_kg.pipeline import save_checkpoint as save
    from cumap.llm.client import LLMClient
    from cumap.llm.prompts import load_prompt
    from cumap.schemas.relations import RelationRegistry

    settings = get_settings()
    inj = O.oracle_e1(g)  # spans + types only: no concept id, no cluster, no relation
    O.assert_no_label_leak(inj, g)
    offs = PD.sentence_offsets(text)
    sents = [text[a:b] for a, b in offs]
    raw = {
        "section_id": sid,
        "chapter_num": chapter if chapter is not None else int(sid.split(".")[0]),
        "order_index": 0,
        "text": text,
        "heading_path": [sid],
    }
    units = P.make_units([raw])
    uid = units[0]["section_id"]
    store, seen = NodeStore(), {}
    for span, typ in inj.mentions:
        surface = text[span[0] : span[1]]
        key = " ".join(surface.casefold().split())
        mention = {
            "section_id": uid,
            "order": 0,
            "role": "used",
            "evidence": sents[sentence_of(offs, span[0])],
            "para": "P1",
            "linked_by": "generator",
        }
        if key in seen:
            seen[key].mentions.append(mention)
            continue
        n = Node(
            id=store.new_id(),
            name=surface,
            aliases=[],
            node_type=typ,
            first_section=uid,
            first_order=0,
            definition=None,
            gloss="",
            mentions=[mention],
        )
        seen[key] = store.add(n)
    info = {"provisional_nodes": len(store.nodes), "gold_mention_spans": len(inj.mentions)}
    if dry_run:
        info["note"] = (
            "canonicalisation calls are counted at run time (about one LLM call per node that has candidates)"
        )
        return info
    embed = X.Embedder(settings.embeddings.model)
    if empty_lexicon:  # SciNLP profile: no networking identity lexicon, no overrides
        from cumap.expert_kg.alias_rules import AliasConfig

        lexicon, overrides = Lexicon([], AliasConfig.load(), "empty"), CanonicalOverrides()
    else:
        lexicon = Lexicon.load(REPO_ROOT / "configs" / "term_lexicon.yaml")
        overrides = CanonicalOverrides.load(REPO_ROOT / "configs" / "canonical_overrides.yaml")
    client = LLMClient(settings, run_id=run_id)
    settings.llm.stage_budgets_usd["concepts"] = max_usd
    res = P.canonicalise(
        RunOutput(store),
        units,
        lexicon,
        client,
        load_prompt(REPO_ROOT / "prompts", "canonicalize", "v2"),
        embed,
        overrides,
    )
    cp = P.build_checkpoint(run_id, RunOutput(store), res, units, {sid: text})
    sr.finish_concepts(cp, sections, embed)
    registry = RelationRegistry.from_yaml(REPO_ROOT / settings.relation_registry)
    words = len(text.split())
    stats = sr.select_stage(
        cp,
        sections,
        registry,
        embed,
        budget=math.ceil(14.2 * words / 1000),
        sample=0,
        use_anchors=True,
    )
    info["budget_record"] = {
        "word_count": words,
        "eligible_candidate_pairs": stats["unique_candidate_pairs"],
        "budget": pair_budget(words, stats["unique_candidate_pairs"]),
        "selected_pairs": stats["selected"],
    }
    cp.stage = "relations"
    save(cp, KG / run_id)
    info["canonicalisation_llm_calls"] = res.llm_calls
    info["concepts_after_canonicalisation"] = len(cp.concepts)
    info["relations"] = R.stage_relations(run_id, dry_run=False, max_usd=max_usd)
    return info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("oracle", choices=["E1", "E2", "E3", "E4"])
    ap.add_argument("--section", required=True)
    ap.add_argument("--pilot-sheet", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-usd", type=float, default=0.6)
    ap.add_argument("--tag", default="pilot")
    a = ap.parse_args()
    print(
        json.dumps(
            run_oracle(
                a.oracle,
                a.section,
                Path(a.pilot_sheet),
                dry_run=a.dry_run,
                max_usd=a.max_usd,
                tag=a.tag,
            ),
            indent=1,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
