"""`cumap gold sample-relation-items --n 100 --seed <seed>`: CR-001 §7.3 relation-set
agreement test. Picks textbook text that mentions >= 2 drafted pilot concepts,
stratified so each of the 6 semantic families appears >= 8 times, and writes two
blank annotation sheets. No LLM call: the "LLM suggestions" that pick items are the
already-drafted concepts/edges from `cumap gold suggest-expert`, used only to know
which concepts to look for and which family a candidate pair probably belongs to for
stratification — never to pre-fill the answer sheets.

Note on the matching unit: CR-001's text says "sentences", but with only 5 pilot-
question sections to draw from, single-sentence co-occurrence turned out far too
sparse (5 candidates total on the real data — nowhere near the >=48 needed for 6
families x 8). Widened to *paragraphs* (the section text's own "\n\n"-separated
units from the parser), which is still a short, coherent, readable context for an
annotator and recovers enough candidates in practice. Logged in DECISIONS.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from cumap.schemas.relations import RelationRegistry

PEDAGOGICAL_FAMILY = "pedagogical"
_PARENTHETICAL_RE = re.compile(r"\s*\([^)]*\)\s*$")


@dataclass
class RelationItem:
    item_id: str
    question_id: str
    section_id: str
    sentence: str
    concept_x: str
    concept_y: str
    predicted_family: str | None  # for stratification only; never shown to annotators


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def _strip_trailing_parenthetical(name: str) -> str:
    """"congestion avoidance (additive increase)" -> "congestion avoidance". LLM-drafted
    concept names sometimes append a clarifying gloss that never appears verbatim in the
    source text; matching should look for the core term, not the LLM's annotation of it.
    """
    return _PARENTHETICAL_RE.sub("", name).strip()


def find_concept_mentions(text: str, concepts: list[dict]) -> list[str]:
    """Concept ids whose canonical_name (or an alias, or the name with a trailing
    parenthetical gloss stripped) appears in `text`, case-insensitive.
    """
    text_lower = text.lower()
    found = []
    for c in concepts:
        names = {c["canonical_name"], _strip_trailing_parenthetical(c["canonical_name"]), *c.get("aliases", [])}
        if any(name and name.lower() in text_lower for name in names):
            found.append(c["concept_id"])
    return found


def predicted_family(concept_x: str, concept_y: str, draft_edges: list[dict], registry: RelationRegistry) -> str | None:
    for edge in draft_edges:
        if {edge["source_id"], edge["target_id"]} == {concept_x, concept_y} and edge["relation"] in registry:
            return registry.family_of(edge["relation"])
    return None


def find_candidate_items(
    question_id: str,
    section_texts: dict[str, str],
    concepts: list[dict],
    draft_edges: list[dict],
    registry: RelationRegistry,
) -> list[RelationItem]:
    items = []
    for section_id, text in section_texts.items():
        for paragraph in split_paragraphs(text):
            mentioned = find_concept_mentions(paragraph, concepts)
            if len(mentioned) < 2:
                continue
            concept_by_id = {c["concept_id"]: c["canonical_name"] for c in concepts}
            for i in range(len(mentioned)):
                for j in range(i + 1, len(mentioned)):
                    cx, cy = mentioned[i], mentioned[j]
                    items.append(
                        RelationItem(
                            item_id=f"RI-{question_id[2:10]}-{section_id}-{i}-{j}-{len(items)}",
                            question_id=question_id,
                            section_id=section_id,
                            sentence=paragraph,
                            concept_x=concept_by_id[cx],
                            concept_y=concept_by_id[cy],
                            predicted_family=predicted_family(cx, cy, draft_edges, registry),
                        )
                    )
    return items


def stratified_sample(
    candidates: list[RelationItem],
    registry: RelationRegistry,
    *,
    n: int,
    seed: int,
    min_per_family: int = 8,
) -> list[RelationItem]:
    """Fills each of the 6 semantic families (all except "pedagogical") to at least
    `min_per_family` where candidates exist, then fills the remainder (including
    unknown-family items) up to `n`, deterministically for a given seed.
    """
    import random

    rng = random.Random(seed)
    by_family: dict[str, list[RelationItem]] = {}
    unknown: list[RelationItem] = []
    for item in candidates:
        if item.predicted_family and item.predicted_family != PEDAGOGICAL_FAMILY:
            by_family.setdefault(item.predicted_family, []).append(item)
        else:
            unknown.append(item)

    for pool in by_family.values():
        rng.shuffle(pool)
    rng.shuffle(unknown)

    semantic_families = [f for f in registry.families if f != PEDAGOGICAL_FAMILY]
    selected: list[RelationItem] = []
    selected_ids: set[str] = set()

    for family in semantic_families:
        pool = by_family.get(family, [])
        for item in pool[:min_per_family]:
            selected.append(item)
            selected_ids.add(item.item_id)

    remaining_pool = [item for item in candidates if item.item_id not in selected_ids]
    rng.shuffle(remaining_pool)
    for item in remaining_pool:
        if len(selected) >= n:
            break
        selected.append(item)
        selected_ids.add(item.item_id)

    rng.shuffle(selected)
    return selected[:n]


def write_relation_agreement_files(items: list[RelationItem], out_dir: Path, registry: RelationRegistry) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)

    items_df = pd.DataFrame(
        [
            {
                "item_id": i.item_id,
                "section_id": i.section_id,
                "sentence": i.sentence,
                "concept_x": i.concept_x,
                "concept_y": i.concept_y,
            }
            for i in items
        ]
    )
    items_path = out_dir / "items.csv"
    items_df.to_csv(items_path, index=False)

    relation_options = [r.name for r in registry.all_relations() if r.family] + ["no_relation", "other"]
    blank_sheet = items_df.copy()
    for col in ["relation", "direction", "part_type", "dimension", "other_phrase"]:
        blank_sheet[col] = ""
    blank_sheet.attrs["relation_options"] = relation_options  # documentation only; CSV has no attrs on disk

    paths = {"items": items_path}
    for annotator in ("A", "B"):
        sheet_path = out_dir / f"annotator_{annotator}.csv"
        blank_sheet.to_csv(sheet_path, index=False)
        paths[f"annotator_{annotator}"] = sheet_path

    return paths
