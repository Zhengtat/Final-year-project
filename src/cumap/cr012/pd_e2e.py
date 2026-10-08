"""CR-012 P&D-E2E: section selection, blind annotation sheets, gold loader and validator.

Selection is label-blind and prediction-blind: it uses only chapter, length and structure, fixed with a seed BEFORE any final CUM
prediction exists. Pilot = 2 already-developed sections (chapters 1-3), used only to debug annotation / scoring and never part of
held-out scores. Held-out = 7 sections from chapters 4-9, which no CR-005..011 run touched. Humans own the gold: this module never
writes under the gold folder; the annotator saves the marked sheet there. LLMs may not be the sole ground truth."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from pathlib import Path

from cumap.config import REPO_ROOT, get_settings
from cumap.cr012.types import GoldConcept, GoldMention, GoldRelation, UnitGold
from cumap.expert_kg.relations import split_sentences
from cumap.schemas.relations import RelationRegistry

SEED = 20261011
SYSTEM_QUALIFIERS = {
    "polarity",
    "modality",
}  # attached to every system edge; gold asks only for the relation-specific ones
SECTIONS = REPO_ROOT / "data/interim/textbook_sections.jsonl"
CHECKS = REPO_ROOT / "data/interim/checks/cr012"
PILOT_CHAPTERS = (1, 2, 3)
HELDOUT_CHAPTERS = (4, 5, 6, 7, 8, 9)
MIN_WORDS = 1200
MAX_WORDS = 5500  # keeps exhaustive annotation tractable; a first cap of 4500 left chapters 5, 7 and 9 empty (6-8 sections needed)
N_PILOT, N_HELDOUT = 2, 7
DOUBLE_ANNOTATED = 2  # 2 of 7 held-out sections (about 29%), within the 25-30% target
COLUMNS = [
    "section_id", "row_type", "row_id", "sentence_id", "text", "span_text", "occurrence", "concept_id", "canonical_name",
    "node_type", "aliases", "relation", "source_concept_id", "target_concept_id", "qualifiers", "evidence_sentence_ids",
    "not_same_concept_id", "annotator_id", "notes",
]  # fmt: skip
ROW_TYPES = {"SECTION", "SENTENCE", "MENTION", "CONCEPT", "RELATION", "NOT_SAME"}


def load_sections() -> list[dict]:
    return [json.loads(line) for line in SECTIONS.read_text().splitlines() if line.strip()]


def _words(r: dict) -> int:
    return len(r["text"].split())


def _eligible(rows: list[dict], chapters: tuple[int, ...]) -> list[dict]:
    return [r for r in rows if r["chapter_num"] in chapters and MIN_WORDS <= _words(r) <= MAX_WORDS]


def select(rows: list[dict], seed: int = SEED) -> dict:
    """Pilot: 2 sections from chapters 1-3 (different chapters when possible). Held-out: one section per chapter 4-9, plus a seventh
    from the chapter with the most eligible sections left (ties to the lowest chapter). Seeded draws only; no prediction, label or
    outcome is read."""
    rng = random.Random(seed)
    pil_pool = _eligible(rows, PILOT_CHAPTERS)
    pil, used = [], set()
    for ch in sorted({r["chapter_num"] for r in pil_pool}):
        if len(pil) >= N_PILOT:
            break
        cands = sorted(
            (r for r in pil_pool if r["chapter_num"] == ch), key=lambda r: r["section_id"]
        )
        pil.append(rng.choice(cands))
        used.add(ch)
    held = []
    pool = _eligible(rows, HELDOUT_CHAPTERS)
    for ch in HELDOUT_CHAPTERS:
        cands = sorted((r for r in pool if r["chapter_num"] == ch), key=lambda r: r["section_id"])
        if cands:
            held.append(rng.choice(cands))
    left = [r for r in pool if r["section_id"] not in {h["section_id"] for h in held}]
    counts = {ch: sum(r["chapter_num"] == ch for r in left) for ch in HELDOUT_CHAPTERS}
    if len(held) < N_HELDOUT and left:
        ch = min(c for c in counts if counts[c] == max(counts.values()))
        held.append(
            rng.choice(
                sorted((r for r in left if r["chapter_num"] == ch), key=lambda r: r["section_id"])
            )
        )
    double = sorted(rng.sample([h["section_id"] for h in held], DOUBLE_ANNOTATED))
    # stability subset (CR section 13): the two SHORTEST held-out sections (a length rule, blind to any outcome)
    stab = [h["section_id"] for h in sorted(held, key=lambda r: (_words(r), r["section_id"]))[:2]]

    def rec(r: dict) -> dict:
        return {
            "section_id": r["section_id"], "chapter": r["chapter_num"], "heading": " > ".join(r["heading_path"][-2:]),
            "words": _words(r), "sentences": len(split_sentences(r["text"])), "text_sha256": hashlib.sha256(r["text"].encode()).hexdigest(),
        }  # fmt: skip

    return {
        "seed": SEED if seed == SEED else seed,
        "rule": f"eligible = {MIN_WORDS}-{MAX_WORDS} words; pilot from chapters {PILOT_CHAPTERS}; held-out from chapters {HELDOUT_CHAPTERS}",
        "frozen_before_any_final_cum_prediction_was_viewed": True,
        "pilot": [rec(r) for r in pil],
        "heldout": [rec(r) for r in held],
        "double_annotated_heldout_sections": double,
        "stability_subset_pd_sections": stab,
        "eligible_pool": {"pilot": len(pil_pool), "heldout": len(pool)},
        "totals": {
            "pilot_words": sum(_words(r) for r in pil),
            "heldout_words": sum(_words(r) for r in held),
        },
    }


def sentence_offsets(text: str) -> list[tuple[int, int]]:
    """Character range of every sentence (the pipeline's own splitter) inside the section text."""
    out, cur = [], 0
    for s in split_sentences(text):
        i = text.find(s, cur)
        if i < 0:  # the splitter only strips whitespace, so this should not happen
            raise ValueError(f"sentence not found in section text: {s[:40]!r}")
        out.append((i, i + len(s)))
        cur = i + len(s)
    return out


def blind_sheet(rows: list[dict], section_ids: list[str], path: Path) -> dict:
    by = {r["section_id"]: r for r in rows}
    n = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for sid in section_ids:
            r = by[sid]
            w.writerow(
                {
                    "section_id": sid,
                    "row_type": "SECTION",
                    "row_id": sid,
                    "text": " > ".join(r["heading_path"][-2:]),
                }
            )
            for i, s in enumerate(split_sentences(r["text"]), 1):
                w.writerow(
                    {
                        "section_id": sid,
                        "row_type": "SENTENCE",
                        "row_id": f"S{i:03d}",
                        "sentence_id": f"S{i:03d}",
                        "text": s,
                    }
                )
                n += 1
    return {
        "path": str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path),
        "sentences": n,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


# ---------------------------------------------------------------- gold loading and validation
def _parse_kv(s: str) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(tuple(p.split("=", 1)) for p in s.split("|") if "=" in p))  # type: ignore[misc]


def load_gold(
    path: Path, sections: dict[str, str], registry: RelationRegistry
) -> tuple[dict[str, UnitGold], list[str]]:
    """-> (gold per section with CHARACTER spans in the section text, problems). Problems make the sheet unusable."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    problems: list[str] = []
    out: dict[str, UnitGold] = {}
    types = set(registry.node_types)
    for sid in sorted({r["section_id"] for r in rows}):
        text = sections.get(sid)
        if text is None:
            problems.append(f"{sid}: unknown section")
            continue
        offs = sentence_offsets(text)
        sent = {f"S{i + 1:03d}": (a, b) for i, (a, b) in enumerate(offs)}
        g = UnitGold(unit=sid)
        mine = [r for r in rows if r["section_id"] == sid]
        for r in (x for x in mine if x["row_type"] == "CONCEPT"):
            if r["node_type"] not in types:
                problems.append(
                    f"{sid} {r['concept_id']}: node_type {r['node_type']!r} not in the registry"
                )
            g.concepts.append(
                GoldConcept(
                    r["concept_id"],
                    sid,
                    r["canonical_name"],
                    r["node_type"],
                    tuple(a for a in r["aliases"].split("|") if a),
                )
            )
        cids = {c.concept_id for c in g.concepts}
        ctype = {c.concept_id: c.type for c in g.concepts}
        if len(cids) != len(g.concepts):
            problems.append(f"{sid}: duplicate concept ids")
        for r in (x for x in mine if x["row_type"] == "MENTION"):
            if r["sentence_id"] not in sent or r["concept_id"] not in cids:
                problems.append(
                    f"{sid}: mention {r['span_text']!r} has an unknown sentence or concept"
                )
                continue
            a, b = sent[r["sentence_id"]]
            sentence = text[a:b]
            occ, start, pos = int(r["occurrence"] or 1), -1, 0
            for _ in range(occ):
                start = sentence.find(r["span_text"], pos)
                pos = start + 1
                if start < 0:
                    break
            if start < 0:
                problems.append(
                    f"{sid} {r['sentence_id']}: span {r['span_text']!r} (occurrence {occ}) is not in the sentence"
                )
                continue
            g.mentions.append(
                GoldMention(
                    sid,
                    (a + start, a + start + len(r["span_text"])),
                    ctype[r["concept_id"]],
                    r["concept_id"],
                )
            )
        for r in (x for x in mine if x["row_type"] == "RELATION"):
            rel = r["relation"]
            if rel not in registry:
                problems.append(f"{sid}: relation {rel!r} is not in the registry")
                continue
            if (
                r["source_concept_id"] not in cids
                or r["target_concept_id"] not in cids
                or r["source_concept_id"] == r["target_concept_id"]
            ):
                problems.append(f"{sid}: relation {rel} has an unknown or identical endpoint")
                continue
            q = dict(_parse_kv(r["qualifiers"]))
            missing = registry.required_qualifiers(rel) - SYSTEM_QUALIFIERS - set(q)
            if missing:
                problems.append(
                    f"{sid}: relation {rel} {r['source_concept_id']}->{r['target_concept_id']} lacks required qualifier(s) {sorted(missing)}"
                )
            for ev in (e for e in r["evidence_sentence_ids"].split("|") if e):
                if ev not in sent:
                    problems.append(f"{sid}: evidence sentence {ev!r} does not exist")
            if not r["evidence_sentence_ids"]:
                problems.append(f"{sid}: relation {rel} has no evidence sentence")
            g.relations.append(
                GoldRelation(
                    sid,
                    rel,
                    src_concept=r["source_concept_id"],
                    tgt_concept=r["target_concept_id"],
                    qualifiers=_parse_kv(r["qualifiers"]),
                )
            )
        for r in (x for x in mine if x["row_type"] == "NOT_SAME"):
            if r["concept_id"] in cids and r["not_same_concept_id"] in cids:
                g.not_same.append((r["concept_id"], r["not_same_concept_id"]))
            else:
                problems.append(f"{sid}: NOT_SAME refers to an unknown concept")
        for c in g.concepts:
            if not any(m.concept_id == c.concept_id for m in g.mentions):
                problems.append(f"{sid}: concept {c.concept_id} has no mention")
        out[sid] = g
    return out, problems


def registry() -> RelationRegistry:
    return RelationRegistry.from_yaml(REPO_ROOT / get_settings().relation_registry)


def codebook(reg: RelationRegistry, sel: dict) -> str:
    rels = "\n".join(
        f"| `{r.name}` | {getattr(r, 'definition', '').strip()} | {getattr(r, 'template', '')} | {', '.join(sorted(reg.required_qualifiers(r.name) - SYSTEM_QUALIFIERS)) or '-'} |"
        for r in reg.all_relations()
    )
    pil = ", ".join(f"{x['section_id']} ({x['words']} words)" for x in sel["pilot"])
    held = ", ".join(f"{x['section_id']} ({x['words']} words)" for x in sel["heldout"])
    return f"""# P&D-E2E annotation codebook (CR-012)

You are building an independent GOLD knowledge graph for whole textbook sections. Annotate EXHAUSTIVELY what the text states: every
concept mention, which mentions are the same concept, and every relation the text supports. You are not shown any system output
and must not look at any. A language model may suggest, but you are the ground truth; nothing here is written for you.

Sheets: `data/interim/checks/cr012/pd_e2e_pilot_blind.csv` (pilot: {pil}) and `pd_e2e_test_blind.csv` (held-out: {held}).
Held-out sections {", ".join(sel["double_annotated_heldout_sections"])} are annotated independently by two people when a second human exists
(an LLM is not a second human). Save your marked copy in the human-owned gold folder; code never writes there.

## How the sheet works
The sheet has one `SECTION` row and one `SENTENCE` row per sentence (pre-filled). ADD rows of these types (any order, same file):

| row_type | fill these columns |
|---|---|
| `CONCEPT` | `concept_id` (your own id, e.g. C001), `canonical_name`, `node_type`, `aliases` (separated by `|`) |
| `MENTION` | `sentence_id`, `span_text` (copied EXACTLY from that sentence), `occurrence` (1 for the first occurrence of that text in the sentence, 2 for the second...), `concept_id` |
| `RELATION` | `source_concept_id`, `relation`, `target_concept_id`, `qualifiers` (`name=value` separated by `|`), `evidence_sentence_ids` (separated by `|`) |
| `NOT_SAME` | `concept_id`, `not_same_concept_id` (two concepts that look alike but are different, where this could be confused) |

Put your id in `annotator_id` on every row you add. Use `notes` freely.

## Concepts and mentions
- One CONCEPT per real concept in the section; every mention of it (full forms, short forms, abbreviations, plurals) is a MENTION row of the same `concept_id`.
- Annotate the whole noun phrase, dropping purely general adjectives; split coordinations; abbreviations in brackets are mentions of the same concept.
- Different senses, kinds, parts, versions, predecessors, or process-versus-entity are DIFFERENT concepts (CR-008 identity rule). When two things could be confused, add a NOT_SAME row.
- `node_type` is one of: {", ".join(reg.node_types)}.

## Relations
- A RELATION says what the text supports between two concepts, source then target as in the template below. Direction matters except for symmetric relations.
- Give the relation-specific qualifiers in the last column (for example part_type for part_of); polarity and modality are optional notes. Give at least one evidence sentence. Do not enumerate absence of relation: no NO_RELATION rows.
- Annotate only relations the text states or clearly implies. A list or co-mention is not a relation.

| relation | definition | template | required qualifiers |
|---|---|---|---|
{rels}

## Agreement
If a second human annotates the same sections independently, we report concept, relation, direction and SAME / NOT_SAME agreement. Disagreements are adjudicated only after both sheets are frozen.
"""


def build() -> dict:
    rows = load_sections()
    sel = select(rows)
    CHECKS.mkdir(parents=True, exist_ok=True)
    pil = blind_sheet(
        rows, [s["section_id"] for s in sel["pilot"]], CHECKS / "pd_e2e_pilot_blind.csv"
    )
    held = blind_sheet(
        rows, [s["section_id"] for s in sel["heldout"]], CHECKS / "pd_e2e_test_blind.csv"
    )
    sel["sheets"] = {"pilot": pil, "heldout": held}
    (CHECKS / "pd_e2e_selection.json").write_text(json.dumps(sel, indent=1), encoding="utf-8")
    (REPO_ROOT / "docs/annotation/pd_e2e_codebook.md").write_text(
        codebook(registry(), sel), encoding="utf-8"
    )
    return sel


if __name__ == "__main__":
    print(json.dumps(build(), indent=1)[:3000])
