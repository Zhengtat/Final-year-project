"""CR-009 §4.1 rule M2 `partial_span`: an item whose span is the FINAL word(s) of a TERM-LIKE longer
candidate in the same evidence quote ("handler" inside "signal handler"). Pure code, $0.

A span counts as partial only when ALL hold:
  1. it is the final word(s) (head end) of the longer candidate, compared on surface tokens;
  2. the longer candidate is not already an item;
  3. the short form does not also occur on its own elsewhere in the same quote.
The longer candidate (after stripping determiners, quantifiers, numerals and possessives) must be
term-like: a noun-noun compound, an R2 long form, an emphasised term, a known card/lexicon form, or an
adjective+noun chunk that recurs >= 2 times in the chapter. Ordinary modifiers ("each incoming frame",
"a tiny capacitor") and a modifier-first span ("DRAM" in "DRAM cell") never fire.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from cumap.expert_kg.alias_rules import AliasConfig, find_abbreviations

_STRIP_POS = {"DET", "NUM", "PRON"}
_QUANT = {
    "each",
    "every",
    "several",
    "many",
    "some",
    "any",
    "all",
    "both",
    "few",
    "most",
    "no",
    "another",
}


@dataclass(frozen=True)
class PartialFlag:
    span: str
    longer: str
    why: str  # compound | r2_long_form | emphasised | known_form | recurring_adj_noun


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def _words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:[-'][a-z0-9]+)*", s.lower())


def _strip(tokens) -> list:
    """Drop leading determiners, quantifiers, numerals, possessives from a chunk's tokens."""
    toks = list(tokens)
    while toks and (
        toks[0].pos_ in _STRIP_POS
        or toks[0].lower_ in _QUANT
        or toks[0].tag_ in {"PRP$", "POS", "WP$"}
    ):
        toks = toks[1:]
    return [t for t in toks if t.tag_ != "POS"]


def noun_form_lexicon(texts: Iterable[str], nlp) -> set[str]:
    """Lower-cased words the tagger labels NOUN/PROPN somewhere in the chapter (the small model sometimes
    tags a nominal modifier such as "signal" as ADJ in one sentence)."""
    return {t.lower_ for text in texts for t in nlp(text) if t.pos_ in {"NOUN", "PROPN"}}


def chunk_counts(texts: Iterable[str], nlp) -> Counter:
    """Normalised noun-chunk strings (stripped) over a chapter's text, for the adjective+noun rule."""
    c: Counter = Counter()
    for text in texts:
        for ch in nlp(text).noun_chunks:
            toks = _strip(ch)
            if len(toks) >= 2:
                c[_norm(" ".join(t.text for t in toks))] += 1
    return c


def find_partial_spans(
    item_spans: list[str],
    quote: str,
    nlp,
    *,
    all_items: Iterable[str] = (),
    known_forms: Iterable[str] = (),
    emphasised: Iterable[str] = (),
    recurring: Counter | None = None,
    noun_forms: Iterable[str] = (),
    cfg: AliasConfig | None = None,
) -> list[PartialFlag]:
    """Flags for one item (its name and aliases in `item_spans`) against its evidence `quote`."""
    items = {_norm(i) for i in all_items} | {_norm(s) for s in item_spans}
    known = {_norm(k) for k in known_forms}
    emph = {_norm(e) for e in emphasised}
    nouns = {
        w.lower() for w in noun_forms
    }  # words the tagger sees as nouns elsewhere in the chapter
    long_forms = {_norm(p.long_form) for p in find_abbreviations(quote, cfg or AliasConfig.load())}
    doc = nlp(quote)
    flags: list[PartialFlag] = []
    for span_text in item_spans:
        sw = _words(span_text)
        if not sw:
            continue
        if _norm(span_text) in known:
            continue  # the span is itself a known whole term (a card / lexicon form), not a partial one
        found = _occurrences(doc, sw)
        for a, b in found:
            nxt = doc[b] if b < len(doc) else None
            if nxt is not None and nxt.tag_ in {"NN", "NNP"} and nxt.pos_ in {"NOUN", "PROPN"}:
                continue  # (1) the span is a modifier of a following noun ("DRAM" in "DRAM cell")
            # the contiguous nominal tokens to the left of the span form the candidate's modifiers
            k = a
            while k > 0 and _nominal_modifier(doc[k - 1], nouns):
                k -= 1
            why, longer, best_why = None, "", None
            for j in range(
                a - 1, k - 1, -1
            ):  # nearest candidate first: "time slice" before "fixed time slice"
                pre = list(doc[j:a])
                why = None
                cand = " ".join(t.text for t in doc[j:b])
                if _norm(cand) in items:
                    continue  # (2) the longer candidate is already an item
                outside = " ".join(t.text for t in doc if not (j <= t.i < b))
                if re.search(
                    rf"(?<![a-z0-9]){re.escape(' '.join(sw))}(?![a-z0-9])", outside.lower()
                ):
                    continue  # (3) the short form also occurs on its own in the same quote
                if all(
                    t.pos_ in {"NOUN", "PROPN"} or t.dep_ == "compound" or t.lower_ in nouns
                    for t in pre
                ):
                    why = "compound"
                elif _norm(cand) in long_forms:
                    why = "r2_long_form"
                elif _norm(cand) in emph:
                    why = "emphasised"
                elif _norm(cand) in known:
                    why = "known_form"
                elif (
                    recurring is not None
                    and recurring.get(_norm(cand), 0) >= 2
                    and any(t.pos_ == "ADJ" for t in pre)
                ):
                    why = "recurring_adj_noun"
                if why:
                    longer, best_why = cand, why
            why = best_why if longer else None
            if why:
                flags.append(PartialFlag(span_text, longer, why))
                break
        if flags and flags[-1].span == span_text:
            continue
    return flags


_MOD_DEPS = {"compound", "amod", "nmod", "nummod"}


def _nominal_modifier(tok, nouns: set[str]) -> bool:
    """Can `tok` be a modifier inside a noun term to the span's left? Clause-level verbs (a ROOT, relative
    clause or object-taking verb) never are: "impact network performance", "uses CRC-32"."""
    if tok.is_punct or tok.tag_ == "POS" or tok.dep_ not in _MOD_DEPS:
        return False
    if tok.pos_ in {"NOUN", "PROPN", "ADJ"}:
        return True
    return tok.pos_ == "VERB" and (tok.tag_ in {"VBG", "VBN"} or tok.lower_ in nouns)


def _occurrences(doc, sw: list[str]) -> list[tuple[int, int]]:
    """Token index ranges [a, b) whose lower-cased words equal `sw` (surface tokens, not lemmas)."""
    toks = [t.lower_ for t in doc]
    n = len(sw)
    return [
        (a, a + n)
        for a in range(len(toks) - n + 1)
        if [re.sub(r"[^a-z0-9'-]", "", x) for x in toks[a : a + n]] == sw
    ]
