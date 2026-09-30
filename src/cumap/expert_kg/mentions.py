"""CR-007 §4.1: longest-match concept mentions.

Concept mentions in text are found as **longest, non-overlapping spans at token boundaries**
(case-insensitive, light lemma normalisation) over all canonical names and aliases, so "bit rate"
wins over "bit" and "bit" is not also matched inside it. Used by candidate-pair enumeration,
consistency propagation (E3), spread counts and first occurrence (CLAUDE.md rule: concept
mentions use longest-match spans).

Tokens are runs of word characters (hyphen/apostrophe joined); every other character is a
separator, so "(query, document)" tokenises to query / document. Normalisation is a small
deterministic plural/lemma rule (no spaCy needed); a caller may pass `lemma` to override it.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

_TOKEN = re.compile(r"[A-Za-z0-9]+(?:[-'’][A-Za-z0-9]+)*")


@dataclass(frozen=True)
class Mention:
    start: int
    end: int
    surface: str  # the text as written
    concept_id: str
    matched: str  # the vocabulary surface that matched (lower-case)


def default_lemma(token: str) -> str:
    """Lower-case + a conservative plural rule: queries->query, switches->switch, frames->frame."""
    t = token.lower()
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 4 and t.endswith(("ches", "shes", "sses", "xes", "zes")):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith(("ss", "us", "is")):
        return t[:-1]
    return t


def tokenize(text: str, lemma: Callable[[str], str] = default_lemma) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), lemma(m.group())) for m in _TOKEN.finditer(text)]


class MentionMatcher:
    """Longest-match matcher over a vocabulary {surface: concept_id}."""

    def __init__(self, vocab: dict[str, str], lemma: Callable[[str], str] = default_lemma):
        self._lemma = lemma
        self._trie: dict = {}
        for surface, cid in vocab.items():
            toks = [t for _, _, t in tokenize(surface, lemma)]
            if not toks:
                continue
            node = self._trie
            for t in toks:
                node = node.setdefault(t, {})
            node.setdefault("\0", (cid, surface.lower()))  # first vocabulary entry wins

    def find(self, text: str) -> list[Mention]:
        toks = tokenize(text, self._lemma)
        out: list[Mention] = []
        i = 0
        while i < len(toks):
            node, best, j = self._trie, None, i
            while j < len(toks) and toks[j][2] in node:
                node = node[toks[j][2]]
                j += 1
                if "\0" in node:
                    best = (j, node["\0"])
            if best is None:
                i += 1
                continue
            end_tok, (cid, matched) = best
            start, end = toks[i][0], toks[end_tok - 1][1]
            out.append(Mention(start, end, text[start:end], cid, matched))
            i = end_tok
        return out


def build_vocab(concepts: list[dict]) -> dict[str, str]:
    """{surface(lower): concept_id} from concept dicts with concept_id, canonical_name, aliases."""
    vocab: dict[str, str] = {}
    for c in concepts:
        for s in [c["canonical_name"], *c.get("aliases", [])]:
            vocab.setdefault(s.lower(), c["concept_id"])
    return vocab
