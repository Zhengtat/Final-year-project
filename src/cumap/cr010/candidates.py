"""CR-010 N1: deterministic candidate hints for residual node recall ($0, no model). A candidate is a HINT only: it
carries its sources and a position, never an item. Sources: noun chunks, technical noun heads, headings/emphasis,
acronym pairs and definitional patterns; the ranking and the per-section cap are frozen in `configs/cr010_node.yaml`."""

from __future__ import annotations

import re
from dataclasses import dataclass

from cumap.concepts_v4.verifier import _DEF_PATTERNS, _nl
from cumap.expert_kg.alias_rules import AliasConfig, find_abbreviations, r1_key

_STRUCTURAL = ("heading", "emphasis", "acronym", "definitional")


@dataclass(frozen=True)
class Candidate:
    cid: str
    term: str  # normalised (lower case, single spaces); the model writes the surface and the quote
    sources: tuple[str, ...]
    count: int  # case-insensitive occurrences in the section text
    first_pos: int
    one_token: bool


def _count(term: str, text_l: str) -> tuple[int, int]:
    pat = re.compile(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])")
    hits = list(pat.finditer(text_l))
    return len(hits), (hits[0].start() if hits else -1)


def trim_stops(term: str, nlp) -> str:
    """Strip stop words (articles, prepositions, auxiliaries) from both ends: 'the postings list' -> 'postings list',
    'a normalizer in' -> 'normalizer'. A term made only of stop words becomes ''."""
    toks = term.split()
    while toks and nlp.vocab[toks[0]].is_stop:
        toks.pop(0)
    while toks and nlp.vocab[toks[-1]].is_stop:
        toks.pop()
    return " ".join(toks)


def recorded_keys(final: dict, cfg: AliasConfig) -> set[str]:
    """R1 keys of every name, alias and surface the generator recorded (exact coverage: a recorded 'inverted index'
    does NOT hide the candidate 'index', which the gold may list on its own)."""
    names = (
        [c["name"] for c in final["new_concepts"]]
        + [a for c in final["new_concepts"] for a in c["aliases"]]
        + [m["surface"] for m in final["existing_mentions"]]
    )
    return {r1_key(n, cfg) for n in names}


def _gather(
    text: str, heading: str, emphasised: set[str], nlp, cfg: AliasConfig, head_min_chars: int
) -> dict[str, set[str]]:
    from cumap.expert_kg.stats import extract_candidate_terms

    found: dict[str, set[str]] = {}

    def add(term: str, src: str) -> None:
        term = trim_stops(_nl(term), nlp)
        if term:
            found.setdefault(term, set()).add(src)

    for t in extract_candidate_terms(text, nlp):
        add(t, "noun_chunk")
    for chunk in nlp(text).noun_chunks:
        root = chunk.root
        if (
            root.pos_ in {"NOUN", "PROPN"}
            and not root.is_stop
            and root.text.isalpha()
            and len(root.text) >= head_min_chars
        ):
            add(root.text, "technical_head")
    for part in re.split(r"\s*>\s*|\s*/\s*", heading or ""):
        add(part, "heading")
    for e in emphasised:
        add(e, "emphasis")
    for ab in find_abbreviations(text, cfg):
        add(ab.long_form, "acronym")
        add(ab.short_form, "acronym")
    for p in _DEF_PATTERNS:
        for m in p.finditer(text):
            add(m.group(1), "definitional")
    return found


def residual_candidates(
    text: str,
    final: dict,
    nlp,
    *,
    heading: str = "",
    emphasised: set[str] | None = None,
    cfg: AliasConfig | None = None,
    chunk_min_count: int = 2,
    max_tokens: int = 4,
    cap: int = 30,
    head_min_chars: int = 3,
    include_one_token: bool = True,
) -> list[Candidate]:
    """Candidates the generator's `final` output does not cover, ranked by (#sources, count, first position)."""
    cfg = cfg or AliasConfig.load()
    text_l = _nl(text)
    have = recorded_keys(final, cfg)
    ranked: list[tuple[tuple, str, set[str], int, int]] = []
    for term, srcs in _gather(text, heading, emphasised or set(), nlp, cfg, head_min_chars).items():
        n_tok = len(term.split())
        if n_tok > max_tokens or (n_tok == 1 and not include_one_token):
            continue
        count, pos = _count(term, text_l)
        if count == 0:
            continue
        if not (srcs & set(_STRUCTURAL)) and count < chunk_min_count:
            continue
        if r1_key(term, cfg) in have:
            continue
        ranked.append(((-len(srcs), -count, pos), term, srcs, count, pos))
    ranked.sort(key=lambda r: (r[0], r[1]))
    return [
        Candidate(f"c{i}", term, tuple(sorted(srcs)), count, pos, len(term.split()) == 1)
        for i, (_k, term, srcs, count, pos) in enumerate(ranked[:cap], 1)
    ]
