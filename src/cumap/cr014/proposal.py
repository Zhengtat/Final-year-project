"""CR-014 Stage A: candidate registry and the deterministic high-recall proposer (U1).

A candidate is one normalised surface per section with unioned provenance (CR-014 §8): no proposer may erase another's candidate
and nothing here rejects. Gold is never read in this module."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from cumap.concepts_v4.verifier import _DEF_PATTERNS, _nl
from cumap.cr010.candidates import _gather
from cumap.expert_kg.alias_rules import AliasConfig

MAX_WORDS = 4
_NOUNISH = {"NOUN", "PROPN"}
_MODIFIER = {"NOUN", "PROPN", "ADJ"}


@dataclass
class Candidate:
    surface: str  # normalised (lower-case, single spaces)
    section_id: str
    start_offset: int | None = None
    end_offset: int | None = None
    token_length: int = 0
    proposal_sources: set[str] = field(default_factory=set)
    source_specific_scores: dict[str, float] = field(default_factory=dict)
    occurrences: int = 0
    structural: set[str] = field(default_factory=set)  # emphasis / heading / definitional / acronym


Registry = dict[str, Candidate]  # key = normalised surface


def norm_surface(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def add(
    reg: Registry, sid: str, surface: str, source: str, text_l: str, score: float | None = None
):
    key = norm_surface(surface)
    if not key or len(key.split()) > MAX_WORDS:
        return
    c = reg.get(key)
    if c is None:
        m = re.search(rf"(?<!\w){re.escape(key)}(?!\w)", text_l)
        c = reg[key] = Candidate(
            key,
            sid,
            m.start() if m else None,
            m.end() if m else None,
            len(key.split()),
            occurrences=len(re.findall(rf"(?<!\w){re.escape(key)}(?!\w)", text_l)),
        )
    c.proposal_sources.add(source)
    if score is not None:
        c.source_specific_scores[source] = max(score, c.source_specific_scores.get(source, 0.0))


def _units(doc) -> list[tuple[int, int, str, str, bool]]:
    """Word units (hyphen-joined tokens merged): (start_char, end_char, pos, tag, is_stop)."""
    units, i, toks = [], 0, list(doc)
    while i < len(toks):
        j = i
        while (
            j + 2 < len(toks)
            and toks[j + 1].text == "-"
            and not toks[j + 1].whitespace_
            and not toks[j].whitespace_
        ):
            j += 2
        t_last = toks[j]
        units.append(
            (
                toks[i].idx,
                t_last.idx + len(t_last.text),
                t_last.pos_,
                t_last.tag_,
                toks[i].is_stop and i == j,
            )
        )
        i = j + 1
    return units


def _span_ok(units, a: int, b: int) -> bool:
    first, last = units[a], units[b]
    return not first[4] and not last[4] and (last[2] in _NOUNISH or last[3] == "VBG")


def u1_spans(doc) -> list[tuple[int, int, str]]:
    """Contiguous 1-4 word subspans of modifier/noun runs that end in a noun (or gerund): (start, end, kind)."""
    units = _units(doc)
    out: list[tuple[int, int, str]] = []
    i = 0
    while i < len(units):
        if units[i][2] not in _MODIFIER and units[i][3] not in {"VBG", "VBN"}:
            i += 1
            continue
        j = i
        while j + 1 < len(units) and (
            units[j + 1][2] in _MODIFIER or units[j + 1][3] in {"VBG", "VBN"}
        ):
            j += 1
        for a in range(i, j + 1):
            for b in range(a, min(j, a + MAX_WORDS - 1) + 1):
                if not _span_ok(units, a, b):
                    continue
                kinds = {units[k][2] for k in range(a, b + 1)}
                kind = "noun_span" if a == b else ("adj_noun" if "ADJ" in kinds else "compound")
                out.append((units[a][0], units[b][1], kind))
        i = j + 1
    # short "X of Y" / "X to Y" technical phrases made of two runs
    for k in range(1, len(units) - 1):
        word = doc.text[units[k][0] : units[k][1]].lower()
        if word in {"of", "to"} and units[k - 1][2] in _NOUNISH and units[k + 1][2] in _NOUNISH:
            a = k - 1
            while a > 0 and units[a - 1][2] in _MODIFIER and k - (a - 1) <= 2:
                a -= 1
            b = k + 1
            if (b - a + 1) <= MAX_WORDS:
                out.append((units[a][0], units[b][1], "of_phrase"))
    return out


def definitional_hits(text: str) -> set[str]:
    return {norm_surface(m.group(1)) for p in _DEF_PATTERNS for m in p.finditer(text)}


def u1_registry(sec: dict, emphasised: set[str], nlp, cfg: AliasConfig) -> Registry:
    """Deterministic high-recall proposals for one section ($0, local, text only)."""
    sid, text = sec["section_id"], sec["text"]
    text_l = _nl(text)
    reg: Registry = {}
    doc = nlp(text)
    for a, b, kind in u1_spans(doc):
        add(reg, sid, text[a:b], kind, text_l)
    gathered = _gather(text, sec.get("heading") or "", emphasised, nlp, cfg, 3)
    for term, srcs in gathered.items():
        for s in srcs:
            add(reg, sid, term, {"noun_chunk": "np", "technical_head": "head"}.get(s, s), text_l)
    for term in definitional_hits(text):
        add(reg, sid, term, "definitional", text_l)
    # recurrent technical phrases: multi-word candidates that occur at least twice
    for c in reg.values():
        if c.token_length >= 2 and c.occurrences >= 2:
            c.proposal_sources.add("recurrent")
    for c in reg.values():
        for s in ("emphasis", "heading", "definitional", "acronym"):
            if s in c.proposal_sources:
                c.structural.add(s)
    return reg
