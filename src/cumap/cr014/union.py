"""CR-014 Stage B input: the frozen U2 union (deterministic U1 + RAW iteration-0 current-LLM proposals), exact de-duplication,
character-offset occurrences and overlap families. Pure and local; gold is never read here. Nothing in this module rejects a
candidate: a proposer's omission or rejection is evidence, not authority (CR-014 §9)."""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field

from cumap.cr014.proposal import MAX_WORDS, _units, norm_surface, u1_registry
from cumap.expert_kg.alias_rules import AliasConfig

_MODIFIER = {"NOUN", "PROPN", "ADJ"}
MAX_OCC = 40


@dataclass
class Cand:
    cid: str
    surface: str  # normalised
    section_id: str
    token_length: int
    sources: set[str] = field(default_factory=set)
    occurrences: list[tuple[int, int, int]] = field(
        default_factory=list
    )  # (start, end, sentence index) in the ORIGINAL text
    count: int = 0
    structural: set[str] = field(default_factory=set)
    existing_matches: list[str] = field(default_factory=list)

    @property
    def start_offset(self) -> int | None:
        return self.occurrences[0][0] if self.occurrences else None

    @property
    def end_offset(self) -> int | None:
        return self.occurrences[0][1] if self.occurrences else None


@dataclass
class Family:
    fid: str
    section_id: str
    run_text: str
    members: list[str]  # candidate ids
    occurrences: list[tuple[int, int, int]]  # run occurrences (start, end, sentence)
    count: int = 0


@dataclass
class SectionUnion:
    section_id: str
    text: str
    sent_starts: list[int]
    sents: list[tuple[int, int]]
    cands: dict[str, Cand]  # key = normalised surface
    families: list[Family]
    raw_llm_only: int = 0


def surface_regex(surface: str) -> re.Pattern:
    words = [re.escape(w) for w in surface.split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)", re.IGNORECASE)


def sent_index(starts: list[int], pos: int) -> int:
    return max(bisect.bisect_right(starts, pos) - 1, 0)


def noun_runs(doc) -> list[tuple[int, int]]:
    """Maximal modifier/noun runs as character spans (the units a family is built from)."""
    units = _units(doc)
    runs, i = [], 0
    while i < len(units):
        if units[i][2] not in _MODIFIER and units[i][3] not in {"VBG", "VBN"}:
            i += 1
            continue
        j = i
        while j + 1 < len(units) and (
            units[j + 1][2] in _MODIFIER or units[j + 1][3] in {"VBG", "VBN"}
        ):
            j += 1
        runs.append((units[i][0], units[j][1]))
        i = j + 1
    return runs


def iteration0_surfaces(res: dict) -> list[str]:
    """Raw generator output of iteration 0 only: before any rule, hint, pruner or G-link decision."""
    out = res.get("iteration0") or (res["iterations"][0]["output"] if res.get("iterations") else {})
    names = []
    for c in out.get("new_concepts", []):
        names += [c["name"], *c.get("aliases", [])]
    names += [m["surface"] for m in out.get("existing_mentions", [])]
    return names


def build_section_union(
    sec: dict, emphasised: set[str], nlp, cfg: AliasConfig, llm_surfaces: list[str]
) -> SectionUnion:
    sid, text = sec["section_id"], sec["text"]
    doc = nlp(text)
    reg = u1_registry(sec, emphasised, nlp, cfg)
    cands: dict[str, Cand] = {}
    for key, c in reg.items():
        cands[key] = Cand(
            "", key, sid, c.token_length, set(c.proposal_sources), structural=set(c.structural)
        )
    llm_only = 0
    for s in llm_surfaces:
        key = norm_surface(s)
        if not key or len(key.split()) > MAX_WORDS:
            continue
        if key not in cands:
            cands[key] = Cand("", key, sid, len(key.split()))
            llm_only += 1
        cands[key].sources.add("llm_iter0")
    sents = [(s.start_char, s.end_char) for s in doc.sents]
    starts = [a for a, _ in sents]
    keep: dict[str, Cand] = {}
    for key, c in sorted(cands.items()):
        occ = [
            (m.start(), m.end(), sent_index(starts, m.start()))
            for m in surface_regex(key).finditer(text)
        ]
        if not occ:  # a proposal whose string is not in the source text can never be evidenced
            continue
        c.count, c.occurrences = len(occ), occ[:MAX_OCC]
        if c.token_length >= 2 and c.count >= 2:
            c.sources.add("recurrent")
        keep[key] = c
    for n, key in enumerate(sorted(keep)):
        keep[key].cid = f"{sid}#c{n:05d}"
    return SectionUnion(
        sid, text, starts, sents, keep, build_families(sid, text, doc, keep), llm_only
    )


def build_families(sid: str, text: str, doc, cands: dict[str, Cand]) -> list[Family]:
    runs = noun_runs(doc)
    run_starts = [a for a, _ in runs]
    by_run: dict[tuple[int, int], set[str]] = {}
    solo: list[Cand] = []
    for c in cands.values():
        placed = False
        for a, b, _ in c.occurrences:
            k = bisect.bisect_right(run_starts, a) - 1
            if k >= 0 and runs[k][0] <= a and b <= runs[k][1]:
                by_run.setdefault(runs[k], set()).add(c.cid)
                placed = True
        if not placed:
            solo.append(c)
    starts = [s.start_char for s in doc.sents]
    sig: dict[tuple, Family] = {}
    for (a, b), mem in sorted(by_run.items()):
        run_text = norm_surface(text[a:b])
        key = (run_text, tuple(sorted(mem)))
        if key in sig:
            sig[key].occurrences.append((a, b, sent_index(starts, a)))
            sig[key].count += 1
        else:
            sig[key] = Family("", sid, run_text, sorted(mem), [(a, b, sent_index(starts, a))], 1)
    fams = list(sig.values())
    for c in solo:  # candidates outside any noun run (e.g. LLM-only phrases): their own family
        a, b, s = c.occurrences[0]
        fams.append(Family("", sid, c.surface, [c.cid], [(a, b, s)], c.count))
    for n, f in enumerate(fams):
        f.fid = f"{sid}#f{n:05d}"
    return fams
