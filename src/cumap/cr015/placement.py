"""CR-015 mention-placement policies. A policy turns accepted surfaces (+ the family structure) into mention spans; scoring is separate (frozen `scoring.py`).

- `longest_match`: CR-014's rule 17 (reference).
- `family_nested_v3(…)` (A1): longest-match plus, inside each family occurrence, every accepted surface that frozen V3's own boundary stage kept for that family
  (>= 2 accepted surfaces in one family = nested_both_valid); no new model call.
- `family_grounded(…)` (A2/A3): a surface is placed only inside family occurrences whose selector decision kept it (explicit nested validity)."""

from __future__ import annotations

import re

from cumap.cr014.pilot_score import Span, place
from cumap.cr014.union import SectionUnion, surface_regex

norm = lambda s: " ".join(s.lower().split())


def spans_inside_occurrence(u: SectionUnion, surface: str, occ: tuple[int, int, int]) -> list[Span]:
    """Occurrences of `surface` in the sentence of a run occurrence that overlap the run (so an expanded span may extend past the run)."""
    a, b, si = occ
    s0, s1 = u.sents[si]
    out = []
    for m in surface_regex(surface).finditer(u.text[s0:s1]):
        x, y = s0 + m.start(), s0 + m.end()
        if x < b and a < y:
            out.append((x, y))
    return out


def longest_match(accepted: list[str], text: str) -> list[Span]:
    return place(accepted, text)


def family_nested_v3(
    u: SectionUnion, accepted: set[str], boundary: dict[str, list[dict]]
) -> list[Span]:
    spans = set(place(sorted(accepted), u.text))
    by_fid = {f.fid: f for f in u.families}
    for fid, decs in boundary.items():
        f = by_fid.get(fid)
        if f is None:
            continue
        kept = {
            norm(d["surface"])
            for d in decs
            if d["surface"] and d["decision"] != "REJECT" and norm(d["surface"]) in accepted
        }
        if len(kept) < 2:
            continue
        for occ in f.occurrences:
            for s in kept:
                spans.update(spans_inside_occurrence(u, s, occ))
    return sorted(spans)


def family_grounded(
    u: SectionUnion, selected: dict[str, set[str]], accepted: set[str]
) -> list[Span]:
    """`selected[fid]` = surfaces the family selector kept for that family. Place a kept surface at every occurrence of the family's run, if the verifier accepted it."""
    spans: set[Span] = set()
    for f in u.families:
        for s in selected.get(f.fid, ()):
            if s not in accepted:
                continue
            for occ in f.occurrences:
                spans.update(spans_inside_occurrence(u, s, occ))
    return sorted(spans)


__all__ = ["family_grounded", "family_nested_v3", "longest_match", "re", "spans_inside_occurrence"]
