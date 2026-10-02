"""CR-008 §3: deterministic alias rules R1-R3 (pure, $0, no LLM).

R1 normalisation key, R2 acronym-expansion pairs (Schwartz & Hearst 2003), R3 textbook alias
statements (Hearst-style cue patterns, strong vs weak). Rules only *propose* a merge with its
evidence; the term lexicon (R0) and type checks are applied by the caller (canonicalisation).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from cumap.expert_kg.mentions import MentionMatcher, default_lemma

CONFIG_PATH = Path("configs/alias_rules.yaml")
_DASHES = re.compile(r"[‐-―−]")
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
_PLURAL_ACRONYM = re.compile(r"\b([A-Z]{2,})s\b")  # BBUs -> BBU (the lemmatiser skips "-us")
_ARTICLE = re.compile(r"^(?:the|a|an)\s+", re.IGNORECASE)


@dataclass(frozen=True)
class AliasConfig:
    common_words: frozenset[str]
    spelling: dict[str, str]
    example_cues: tuple[str, ...]
    r3_strong: tuple[tuple[str, re.Pattern], ...]
    r3_weak: tuple[tuple[str, re.Pattern], ...]

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> AliasConfig:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))

        def pats(items: list[dict]) -> tuple[tuple[str, re.Pattern], ...]:
            return tuple((p["id"], re.compile(p["cue"], re.IGNORECASE)) for p in items)

        return cls(
            common_words=frozenset(w.lower() for w in raw["common_words"]),
            spelling=dict(raw["spelling"]),
            example_cues=tuple(raw["r2_example_cues"]),
            r3_strong=pats(raw["r3"]["strong"]),
            r3_weak=pats(raw["r3"]["weak"]),
        )


# ---------------------------------------------------------------- R1
def r1_key(name: str, cfg: AliasConfig) -> str:
    """NFKC + casefold, dashes/quotes unified, article stripped, spelling map, head singularised,
    and hyphen/space/punctuation variants collapsed (so 'multi-access' == 'multiaccess')."""
    s = unicodedata.normalize("NFKC", name).translate(_QUOTES)
    s = _PLURAL_ACRONYM.sub(r"\1", _DASHES.sub("-", s)).casefold().strip()
    s = _ARTICLE.sub("", s)
    toks = re.findall(r"[a-z0-9]+", s.replace("-", " "))
    if not toks:
        return ""
    toks = [cfg.spelling.get(t, t) for t in toks]
    toks[-1] = default_lemma(toks[-1])
    return "".join(toks)


def acronym_collision(a: str, b: str, cfg: AliasConfig) -> bool:
    """R1 guard: an all-caps acronym (>= 2 letters) vs its lower-case common-word twin."""
    for x, y in ((a, b), (b, a)):
        x, y = x.strip(), y.strip()
        if len(x) >= 2 and x.isalpha() and x.isupper() and y.islower() and y in cfg.common_words:
            return True
    return False


# ---------------------------------------------------------------- R2
@dataclass(frozen=True)
class AbbrevPair:
    long_form: str
    short_form: str
    sentence: str


def _best_long_form(short: str, candidate: str) -> str | None:
    """Schwartz & Hearst's backward character match: the shortest suffix of `candidate` that
    contains the short form's characters in order, anchored at a word start."""
    s_i, l_i = len(short) - 1, len(candidate) - 1
    while s_i >= 0:
        c = short[s_i].lower()
        if not c.isalnum():
            s_i -= 1
            continue
        while l_i >= 0 and (
            candidate[l_i].lower() != c or (s_i == 0 and l_i > 0 and candidate[l_i - 1].isalnum())
        ):
            l_i -= 1
        if l_i < 0:
            return None
        l_i -= 1
        s_i -= 1
    return candidate[l_i + 1 :].strip()


def _valid_short(s: str) -> bool:
    """An acronym-like token: 2-10 chars, no spaces, at least two upper-case letters or one
    upper-case letter plus a digit/slash (CRC, CSMA/CD, eNodeB, 4B/5B); never a plain word."""
    if not (2 <= len(s) <= 10) or " " in s or not s[0].isalnum():
        return False
    return sum(c.isupper() for c in s) >= 2 or (
        any(c.isupper() for c in s) and any(c.isdigit() for c in s)
    )


def _ordered_subsequence(short: str, long_form: str) -> bool:
    it = iter(long_form.lower())
    return all(ch in it for ch in short.lower() if ch.isalnum())


def find_abbreviations(text: str, cfg: AliasConfig | None = None) -> list[AbbrevPair]:
    """'long form (SF)' and 'SF (long form)' pairs, after Schwartz & Hearst (2003)."""
    cfg = cfg or AliasConfig.load()
    out: list[AbbrevPair] = []
    for sent in re.split(r"(?<=[.!?])\s+|\n\n", text):
        for m in re.finditer(r"\(([^()]{2,80})\)", sent):
            inner, before = m.group(1).strip(), sent[: m.start()].strip()
            if any(cue in inner.lower() for cue in cfg.example_cues):
                continue
            inner = inner.split(";")[0].split(",")[0].strip()
            if _valid_short(inner) and before:
                words = before.split()
                n_max = min(len(words), len(re.sub(r"\W", "", inner)) * 2 + 5)
                lf = _best_long_form(inner, " ".join(words[-n_max:]))
                if (
                    lf
                    and len(lf.split()) <= len(re.sub(r"\W", "", inner)) + 5
                    and len(lf) > len(inner)
                    and not re.search(r"[=\d—]", lf)
                ):
                    out.append(AbbrevPair(lf, inner, sent))
                    continue
            # reverse: SF (long form)
            after_words = before.split()
            if after_words and _valid_short(after_words[-1]) and len(inner.split()) >= 2:
                lf = _best_long_form(after_words[-1], inner)
                if lf == inner and len(lf) > len(after_words[-1]) and not re.search(r"[=\d—]", lf):
                    out.append(AbbrevPair(lf, after_words[-1], sent))
    return out


def split_embedded_acronym(name: str, cfg: AliasConfig) -> tuple[str, str] | None:
    """'cyclic redundancy check (CRC)' -> ('cyclic redundancy check', 'CRC'); examples excluded."""
    m = re.fullmatch(r"(.+?)\s*\(([^()]+)\)", name.strip())
    if not m or any(cue in m.group(2).lower() for cue in cfg.example_cues):
        return None
    long_form, short = m.group(1).strip(), m.group(2).strip()
    if _valid_short(short) and _ordered_subsequence(short, long_form):
        return long_form, short
    return None


# ---------------------------------------------------------------- R3
@dataclass(frozen=True)
class AliasStatement:
    rule: str  # pattern id
    strength: str  # strong | weak
    x_id: str
    y_id: str
    x_surface: str
    y_surface: str
    quote: str


_NP_POS = {"NOUN", "PROPN", "ADJ", "NUM"}


@lru_cache(maxsize=1)
def _nlp():
    import spacy

    return spacy.load("en_core_web_sm", disable=["ner", "lemmatizer"])


def _is_full_np_left(left: str, start: int) -> bool:
    """X must begin its noun phrase: the token before it is not a noun/adjective/number."""
    prev = [
        t for t in _nlp()(left) if t.idx + len(t) <= start and not t.is_punct and not t.is_space
    ]
    return not prev or prev[-1].pos_ not in _NP_POS


def _is_full_np_right(right: str, end: int) -> bool:
    """Y must end its noun phrase: the next token is not a noun/proper noun/number."""
    nxt = [t for t in _nlp()(right) if t.idx >= end and not t.is_punct and not t.is_space]
    return not nxt or nxt[0].pos_ not in {"NOUN", "PROPN", "NUM"}


_TRAIL = re.compile(r"[\s,(\"'*]+$")
_LEAD = re.compile(r"^[\s,)\"'*]+(?:the |a |an )?", re.IGNORECASE)


def alias_statements(
    text: str, vocab: dict[str, str], cfg: AliasConfig, window: int = 90
) -> list[AliasStatement]:
    """Alias statements whose two sides resolve to known (different) concepts: the longest vocab
    surface ending just before the cue is X, the longest starting just after it is Y."""
    matcher = MentionMatcher(vocab)
    out: list[AliasStatement] = []
    for strength, patterns in (("strong", cfg.r3_strong), ("weak", cfg.r3_weak)):
        for pid, pat in patterns:
            for m in pat.finditer(text):
                left = text[max(0, m.start() - window) : m.start()]
                right = text[m.end() : m.end() + window]
                lm = [
                    x
                    for x in matcher.find(_TRAIL.sub("", left))
                    if x.end >= len(_TRAIL.sub("", left)) - 1
                ]
                rtext = _LEAD.sub("", right) if right[:1] in " ,)\"'*" else right
                rm = [x for x in matcher.find(rtext) if x.start <= 1]
                if not lm or not rm:
                    continue
                x, y = lm[-1], rm[0]
                if x.concept_id == y.concept_id:
                    continue
                if not _is_full_np_left(_TRAIL.sub("", left), x.start) or not _is_full_np_right(
                    rtext, y.end
                ):
                    continue
                s0, e0 = max(0, m.start() - window), m.end() + window
                quote = " ".join(text[s0:e0].split())
                out.append(
                    AliasStatement(
                        pid, strength, x.concept_id, y.concept_id, x.surface, y.surface, quote
                    )
                )
    return out
