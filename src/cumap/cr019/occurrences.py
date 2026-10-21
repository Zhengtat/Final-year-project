"""CR-019 O1: the occurrence index. Gold-free; reads a finished run and its text, writes nothing into the run.

For one text unit it lists every longest-match occurrence (rule 17, `MentionMatcher`) of every name and alias of every node that has a recorded mention
in that unit, with a position marker (unit, paragraph, sentence, character span). A surface shared by two or more nodes is owned by the node whose
recorded evidence windows contain the occurrence if exactly one does (the CR-012 rule that fixed the "bandwidth" false merge, `invalid_runs.md`);
otherwise the occurrence is ambiguous and owned by no node. The index is a separate layer: it never writes a mention, never adds an alias and never
changes a node (rule 24 is unchanged)."""

from __future__ import annotations

import bisect
from collections import Counter
from dataclasses import asdict, dataclass

from cumap.cr012.production_graph import _windows
from cumap.cr012.types import Span
from cumap.expert_kg.mentions import MentionMatcher, default_lemma, tokenize

UNIQUE, WINDOW, AMBIGUOUS = "unique", "evidence_window", "ambiguous"


@dataclass(frozen=True)
class Occurrence:
    unit: str
    concept_id: str | None  # None when ambiguous
    owners: tuple[str, ...]  # every node that has this surface
    surface: str
    start: int  # character span in the unit text
    end: int
    paragraph: int
    sentence: int
    assignment: str  # unique | evidence_window | ambiguous

    def to_dict(self) -> dict:
        return asdict(self)


def paragraph_starts(text: str) -> list[int]:
    """Start offset of every paragraph (blank-line separated)."""
    starts, i = [0], text.find("\n\n")
    while i >= 0:
        starts.append(i + 2)
        i = text.find("\n\n", i + 2)
    return starts


_ARTICLES = {"a", "an", "the"}


class R1KeyMatcher:
    """Longest-match over token windows whose R1 key (`alias_rules.r1_key`: casefold, hyphen / space / punctuation collapsed, spelling map,
    head singularised) equals the R1 key of a vocabulary form, so "prefixtuning", "Prefix tuning" and "prefix-tuning" are one surface. The
    R1 acronym guard applies (an all-caps acronym never matches its lower-case common-word twin); keys shorter than `min_key` characters must
    match a form exactly (case-insensitive) instead. Same `find` contract as `MentionMatcher`."""

    def __init__(self, vocab: dict[str, str], cfg, min_key: int = 4, extra_tokens: int = 1):
        from cumap.expert_kg.alias_rules import r1_key

        self._r1, self._cfg, self._min = r1_key, cfg, min_key
        self._by_key: dict[str, tuple[str, str]] = {}
        self._exact: dict[
            str, set[tuple[str, ...]]
        ] = {}  # key -> lemma-token forms (for short keys)
        self._max = 1
        for surface, cid in vocab.items():
            k = r1_key(surface, cfg)
            if k:
                self._by_key.setdefault(k, (cid, surface))
                self._exact.setdefault(k, set()).add(
                    tuple(t for _, _, t in tokenize(surface, default_lemma))
                )
                self._max = max(self._max, len(tokenize(surface, default_lemma)) + extra_tokens)

    def find(self, text: str) -> list:
        from cumap.expert_kg.alias_rules import acronym_collision
        from cumap.expert_kg.mentions import Mention

        toks = tokenize(text, default_lemma)
        out, i = [], 0
        while i < len(toks):
            best = None
            if (
                toks[i][2] in _ARTICLES
            ):  # r1_key strips a leading article; a span never starts with one
                i += 1
                continue
            for j in range(min(len(toks), i + self._max), i, -1):
                a, b = toks[i][0], toks[j - 1][1]
                span = text[a:b]
                key = self._r1(span, self._cfg)
                hit = self._by_key.get(key)
                if hit is None:
                    continue
                cid, form = hit
                if (
                    len(key) < self._min
                    and tuple(t for _, _, t in toks[i:j]) not in self._exact[key]
                ):
                    continue
                if acronym_collision(form, span, self._cfg):
                    continue
                best = (j, Mention(a, b, span, cid, form.lower()))
                break
            if best is None:
                i += 1
                continue
            out.append(best[1])
            i = best[0]
        return out


def _key(surface: str) -> tuple[str, ...]:
    return tuple(t for _, _, t in tokenize(surface, default_lemma))


def build_index(
    concepts: list[dict], text: str, unit: str, sentences: list[Span], matching: str = "token"
) -> tuple[list[Occurrence], Counter]:
    """-> (occurrences in text order, stats). `sentences` are character ranges of the unit's sentences."""
    stats: Counter = Counter()
    present = [c for c in concepts if any(m["section_id"] == unit for m in c["mentions"])]
    owners: dict[tuple[str, ...], set[str]] = {}
    shown: dict[tuple[str, ...], str] = {}
    for c in present:
        for f in [c["canonical_name"], *c.get("aliases", [])]:
            k = _key(f or "")
            if k:
                owners.setdefault(k, set()).add(c["concept_id"])
                shown.setdefault(k, f)
    group_id = {k: f"g{i}" for i, k in enumerate(sorted(owners))}
    by_group = {group_id[k]: tuple(sorted(v)) for k, v in owners.items()}
    if (
        matching == "r1key"
    ):  # CR-019 follow-up: the canonicalisation R1 key also decides which text spans are a form
        from cumap.expert_kg.alias_rules import AliasConfig, r1_key

        cfg = AliasConfig.load()
        forms = {
            (f, c["concept_id"])
            for c in present
            for f in [c["canonical_name"], *c.get("aliases", [])]
            if f and r1_key(f, cfg)
        }
        rk: dict[str, set[str]] = {}
        for f, cid in forms:
            rk.setdefault(r1_key(f, cfg), set()).add(cid)
        group_id = {r: f"g{i}" for i, r in enumerate(sorted(rk))}
        by_group = {group_id[r]: tuple(sorted(v)) for r, v in rk.items()}
        matcher = R1KeyMatcher({f: group_id[r1_key(f, cfg)] for f, _ in sorted(forms)}, cfg)
    else:
        matcher = MentionMatcher({shown[k].lower(): group_id[k] for k in owners})
    windows = {
        c["concept_id"]: _windows(
            {m["quote"] for m in c["mentions"] if m["section_id"] == unit}, text
        )
        for c in present
    }
    sent_starts = [a for a, _ in sentences]
    para = paragraph_starts(text)
    out: list[Occurrence] = []
    for m in matcher.find(text):
        own = by_group[m.concept_id]
        if len(own) == 1:
            cid, how = own[0], UNIQUE
        else:
            inside = [o for o in own if any(a <= m.start and m.end <= b for a, b in windows[o])]
            cid, how = (inside[0], WINDOW) if len(inside) == 1 else (None, AMBIGUOUS)
        stats[how] += 1
        out.append(
            Occurrence(
                unit,
                cid,
                own,
                m.surface,
                m.start,
                m.end,
                bisect.bisect_right(para, m.start) - 1,
                max(bisect.bisect_right(sent_starts, m.start) - 1, 0),
                how,
            )
        )
    stats["nodes"] = len(present)
    stats["nodes_with_occurrence"] = len({o.concept_id for o in out if o.concept_id})
    return out, stats


def spans_by_node(occ: list[Occurrence]) -> dict[str, list[Span]]:
    out: dict[str, list[Span]] = {}
    for o in occ:
        if o.concept_id:
            out.setdefault(o.concept_id, []).append((o.start, o.end))
    return out
