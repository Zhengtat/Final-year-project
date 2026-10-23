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

import os
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


DEFAULT_MATCHING = "token"  # CR-020: "token" (rule 17 as of CR-007) | "r1key" (spelling variants share the CR-008 R1 key)
_ARTICLES = {"a", "an", "the"}


def matching_mode() -> str:
    """Process-wide matching mode: CUMAP_MATCHING, else DEFAULT_MATCHING. Frozen scorers pin `token` explicitly."""
    mode = os.environ.get("CUMAP_MATCHING", DEFAULT_MATCHING)
    if mode not in ("token", "r1key"):
        raise ValueError(f"CUMAP_MATCHING must be token or r1key, not {mode!r}")
    return mode


def use_production_matching() -> str:
    """CR-020: production stages match text with `configs/matching.yaml` `production_mode` unless CUMAP_MATCHING is already set."""
    import yaml

    from cumap.config import REPO_ROOT

    mode = yaml.safe_load((REPO_ROOT / "configs/matching.yaml").read_text())["production_mode"]
    os.environ.setdefault("CUMAP_MATCHING", mode)
    return matching_mode()


class MentionMatcher:
    """Longest-match matcher over a vocabulary {surface: concept_id}.

    mode "token": token-sequence match after the light lemma (CR-007). mode "r1key" (CR-020): a window of text tokens matches a form when both
    have the same CR-008 R1 key (casefold, hyphen / space / punctuation collapsed, spelling map, head singularised), so "prefixtuning",
    "Prefix tuning" and "prefix-tuning" are one surface; a window never starts with an article, keys shorter than 4 characters must match a
    form token-for-token, and the R1 acronym guard applies. Longest match and first-vocabulary-entry-wins hold in both modes."""

    def __init__(
        self,
        vocab: dict[str, str],
        lemma: Callable[[str], str] = default_lemma,
        mode: str | None = None,
    ):
        self.mode = mode or matching_mode()
        self._lemma = lemma
        self._trie: dict = {}
        if self.mode == "r1key":
            self._init_r1(vocab)
        for surface, cid in vocab.items():
            toks = [t for _, _, t in tokenize(surface, lemma)]
            if not toks:
                continue
            node = self._trie
            for t in toks:
                node = node.setdefault(t, {})
            node.setdefault("\0", (cid, surface.lower()))  # first vocabulary entry wins

    def _init_r1(self, vocab: dict[str, str], min_key: int = 4, extra_tokens: int = 1) -> None:
        from cumap.expert_kg.alias_rules import AliasConfig, r1_key

        self._cfg, self._r1, self._min = AliasConfig.load(), r1_key, min_key
        self._by_key: dict[str, tuple[str, str]] = {}
        self._exact: dict[str, set[tuple[str, ...]]] = {}
        self._max = 1
        for surface, cid in vocab.items():
            k = r1_key(surface, self._cfg)
            if not k:
                continue
            self._by_key.setdefault(k, (cid, surface))
            self._exact.setdefault(k, set()).add(
                tuple(t for _, _, t in tokenize(surface, self._lemma))
            )
            self._max = max(self._max, len(tokenize(surface, self._lemma)) + extra_tokens)

    def _find_r1(self, text: str) -> list[Mention]:
        from cumap.expert_kg.alias_rules import acronym_collision

        toks = tokenize(text, self._lemma)
        out: list[Mention] = []
        i = 0
        while i < len(toks):
            best = None
            if (
                toks[i][2] not in _ARTICLES
            ):  # r1_key strips a leading article; a span never starts with one
                for j in range(min(len(toks), i + self._max), i, -1):
                    a, b = toks[i][0], toks[j - 1][1]
                    span = text[a:b]
                    key = self._r1(span, self._cfg)
                    hit = self._by_key.get(key)
                    if hit is None:
                        continue
                    if (
                        len(key) < self._min
                        and tuple(t for _, _, t in toks[i:j]) not in self._exact[key]
                    ):
                        continue
                    if acronym_collision(hit[1], span, self._cfg):
                        continue
                    best = (j, Mention(a, b, span, hit[0], hit[1].lower()))
                    break
            if best is None:
                i += 1
                continue
            out.append(best[1])
            i = best[0]
        return out

    def find(self, text: str) -> list[Mention]:
        if self.mode == "r1key":
            return self._find_r1(text)
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
