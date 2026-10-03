"""CR-009 §4: the rule-based concept verifier (SAC-KG style): code, parameter-free, $0, never reads a rationale.

`verify(out, ctx)` takes one generator output (a dict shaped like ConceptGeneratorV4LLM) and returns the
output after AUTO-FIXES, the FLAGS (F/C/Q: precision and format; they drop or re-prompt) and the HINTS
(M: coverage; they always trigger a corrective round, because missing items cannot be fixed by deleting).
"Correct" = after auto-fixes, no Q, F, C or M rule fires. All M rules skip anything the generator has
already rejected with a reason, so "Correct" is always reachable."""

from __future__ import annotations

import copy
import re
from collections import Counter
from dataclasses import dataclass, field

from cumap.concepts_v4.cards import Card
from cumap.expert_kg.alias_rules import AliasConfig, find_abbreviations, r1_key
from cumap.expert_kg.canonical_rules import types_compatible
from cumap.expert_kg.lexicon import Lexicon
from cumap.expert_kg.partial_span import find_partial_spans

_CFG = None


def _cfg() -> AliasConfig:
    global _CFG
    if _CFG is None:
        _CFG = AliasConfig.load()
    return _CFG


def _n(s: str) -> str:
    return " ".join((s or "").split())


def _nl(s: str) -> str:
    return _n(s).lower()


@dataclass
class Flag:
    rule: str
    where: str  # mention | new | anchor | section
    idx: int
    detail: str
    sub: int | None = None  # anchor index inside a new concept


@dataclass
class Hint:
    rule: str  # M1..M5
    type: str  # missed_existing_mention | longer_span | possible_anchor_missed | missed_candidate
    text: str
    detail: str
    key: tuple[str, str]
    hint_id: str = ""


@dataclass
class VerifyCtx:
    section_text: str
    paragraphs: dict[str, str]
    cards: list[Card]
    lexicon: Lexicon | None
    nlp: object
    rho: float = 1.5
    recurring: Counter = field(default_factory=Counter)
    noun_forms: set[str] = field(default_factory=set)
    emphasised: set[str] = field(default_factory=set)
    rejected_keys: set[tuple[str, str]] = field(default_factory=set)
    m4: bool = False
    m5: bool = False
    chapter: int | None = None

    @property
    def words(self) -> int:
        return len(self.section_text.split())

    def card_by_id(self) -> dict[str, Card]:
        return {c.node.id: c for c in self.cards}


@dataclass
class VerifyResult:
    out: dict
    flags: list[Flag] = field(default_factory=list)
    hints: list[Hint] = field(default_factory=list)
    autofixes: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def correct(self) -> bool:
        return (
            not self.flags and not self.hints and not any(w.startswith("Q1") for w in self.warnings)
        )


# ---------------------------------------------------------------- helpers
def _find_exact(quote: str, text: str) -> str | None:
    """The exact substring of `text` equal to `quote` up to whitespace, else None."""
    if quote and quote in text:
        return quote
    toks = quote.split()
    if not toks:
        return None
    m = re.search(r"\s+".join(re.escape(t) for t in toks), text)
    return m.group(0) if m else None


def _para_of(quote: str, paras: dict[str, str]) -> str | None:
    for k, p in paras.items():
        if _nl(quote) in _nl(p):
            return k
    return None


def _contains(hay: str, needle: str) -> bool:
    return _nl(needle) in _nl(hay)


def _sentence_of(quote: str, text: str) -> str:
    for s in re.split(r"(?<=[.!?])\s+", _n(text)):
        if _nl(quote) in _nl(s):
            return s
    return quote


def _head(name: str) -> str:
    w = re.findall(r"[a-z0-9]+", name.lower())
    return w[-1].rstrip("s") if w else ""


# ---------------------------------------------------------------- the rules
def verify(out_in: dict, ctx: VerifyCtx) -> VerifyResult:
    out = copy.deepcopy(out_in)
    res = VerifyResult(out)
    cards = ctx.card_by_id()
    paras = ctx.paragraphs
    text = ctx.section_text
    cfg = _cfg()
    mentions, news = out["existing_mentions"], out["new_concepts"]

    # F2 quote verbatim (auto-fix whitespace), F3 span in quote
    for i, m in enumerate(mentions):
        if (exact := _find_exact(m["evidence"], text)) is None:
            res.flags.append(
                Flag("F2", "mention", i, f"evidence not verbatim: {m['evidence'][:60]!r}")
            )
        elif exact != m["evidence"]:
            res.autofixes.append({"rule": "F2", "what": "whitespace", "where": f"mention {i}"})
            m["evidence"] = exact
        elif _nl(m["surface"]) not in _nl(m["evidence"]):
            res.flags.append(
                Flag("F3", "mention", i, f"surface {m['surface']!r} not inside its evidence")
            )
        if _nl(m["surface"]) not in _nl(m["evidence"]) and not any(
            f.rule == "F3" and f.where == "mention" and f.idx == i for f in res.flags
        ):
            res.flags.append(
                Flag("F3", "mention", i, f"surface {m['surface']!r} not inside its evidence")
            )
    for i, c in enumerate(news):
        if (exact := _find_exact(c["evidence"], text)) is None:
            res.flags.append(Flag("F2", "new", i, f"evidence not verbatim: {c['evidence'][:60]!r}"))
        elif exact != c["evidence"]:
            res.autofixes.append({"rule": "F2", "what": "whitespace", "where": f"new {i}"})
            c["evidence"] = exact
        if not any(_nl(x) in _nl(c["evidence"]) for x in [c["name"], *c["aliases"]]):
            res.flags.append(
                Flag("F3", "new", i, f"{c['name']!r} (or an alias) not inside its evidence")
            )

    # F4 / F2 / F5: anchors (an anchor error drops only the anchor)
    for i, c in enumerate(news):
        kept = []
        pk = list(paras).index(c["para"]) if c["para"] in paras else 0
        scope = " ".join(list(paras.values())[max(0, pk - 1) : pk + 1]) + " " + c["name"]
        for j, a in enumerate(c["anchors"]):
            card = cards.get(a["node_id"])
            if card is None:
                res.autofixes.append(
                    {"rule": "F4", "what": "drop_anchor", "where": f"new {i} anchor {j}"}
                )
                continue
            if (exact := _find_exact(a["cue"], text)) is None:
                res.autofixes.append(
                    {"rule": "F2", "what": "drop_anchor", "where": f"new {i} anchor {j}"}
                )
                continue
            a["cue"] = exact
            names_ok = any(_nl(x) in _nl(exact) for x in [c["name"], *c["aliases"]])
            node_ok = any(_contains(exact, f) or _contains(scope, f) for f in card.node.forms())
            if not (names_ok and node_ok):
                res.autofixes.append(
                    {"rule": "F5", "what": "drop_anchor", "where": f"new {i} anchor {j}"}
                )
                continue
            kept.append(a)
        had = len(c["anchors"])
        c["anchors"] = kept
        # F6 origin consistency
        if c["extraction_origin"] == "anchored" and not kept:
            if had:
                c["extraction_origin"], c["independence_check"] = (
                    "independent",
                    "anchor removed by verifier",
                )
                res.autofixes.append({"rule": "F6", "what": "to_independent", "where": f"new {i}"})
            else:
                res.flags.append(Flag("F6", "new", i, "anchored without anchors"))
        elif (
            c["extraction_origin"] == "independent"
            and not (c.get("independence_check") or "").strip()
        ):
            res.flags.append(Flag("F6", "new", i, "independent without independence_check"))
        elif c["extraction_origin"] == "independent" and kept:
            c["extraction_origin"], c["independence_check"] = "anchored", None
            res.autofixes.append({"rule": "F6", "what": "to_anchored", "where": f"new {i}"})

    # F4 on mentions; C2 type; C4 role; C1 lexicon
    for i, m in enumerate(mentions):
        card = cards.get(m["node_id"])
        if card is None:
            res.flags.append(Flag("F4", "mention", i, f"unknown node {m['node_id']}"))
            continue
        if not types_compatible(m["node_type"], card.node.node_type):
            res.flags.append(
                Flag("C2", "mention", i, f"{m['node_type']} vs card {card.node.node_type}")
            )
        has_def = card.node.def_section is not None
        if m["role"] == "defined" and has_def:
            m["role"] = "refined"
            res.autofixes.append(
                {"rule": "C4", "what": "defined->refined", "where": f"mention {i}"}
            )
        elif m["role"] == "refined" and not has_def:
            m["role"] = "defined"
            res.autofixes.append(
                {"rule": "C4", "what": "refined->defined", "where": f"mention {i}"}
            )
        if ctx.lexicon is not None and ctx.lexicon.is_different(
            m["surface"], card.node.name, ctx.chapter
        ):
            res.flags.append(
                Flag(
                    "C1",
                    "mention",
                    i,
                    f"{m['surface']!r} is a listed look-alike of {card.node.name!r}",
                )
            )

    # C3 / C5: a NEW concept (or an anchor) that is the same as a shown node -> existing mention
    key_card = {}
    for c in cards.values():
        for f in c.node.forms():
            key_card.setdefault(r1_key(f, cfg), c)
    convert = []
    for i, c in enumerate(news):
        forms = [c["name"], *c["aliases"]]
        hit = next((key_card[r1_key(f, cfg)] for f in forms if r1_key(f, cfg) in key_card), None)
        if hit is None:
            hit = next(
                (
                    cards[a["node_id"]]
                    for a in c["anchors"]
                    if a["node_id"] in cards
                    and r1_key(cards[a["node_id"]].node.name, cfg) == r1_key(c["name"], cfg)
                ),
                None,
            )  # C5
        if hit is not None:
            convert.append((i, hit))
        elif ctx.lexicon is not None:
            for card in cards.values():
                if any(
                    ctx.lexicon.same_set(f) is not None
                    and ctx.lexicon.same_set(f) == ctx.lexicon.same_set(card.node.name)
                    for f in forms
                ):
                    res.flags.append(
                        Flag(
                            "C1",
                            "new",
                            i,
                            f"{c['name']!r} is in the same lexicon set as {card.node.name!r}",
                        )
                    )
                    break
    for i, card in reversed(convert):
        c = news.pop(i)
        role = c["role"]
        if role == "defined" and card.node.def_section is not None:
            role = "refined"
        mentions.append(
            {
                "node_id": card.node.id,
                "surface": c["name"],
                "node_type": card.node.node_type
                if types_compatible(c["node_type"], card.node.node_type)
                else c["node_type"],
                "role": role,
                "evidence": c["evidence"],
                "para": c["para"],
            }
        )
        res.autofixes.append(
            {"rule": "C3", "what": "new->existing_mention", "where": f"new {i} -> {card.node.id}"}
        )
        for f in res.flags:  # re-index flags of later new concepts
            if f.where == "new" and f.idx > i:
                f.idx -= 1
            elif f.where == "new" and f.idx == i:
                f.where, f.idx = "mention", len(mentions) - 1

    # Q1 quantity
    n_items = len(news) + len(mentions)
    floor = max(3, ctx.rho * ctx.words / 100)
    if n_items < floor:
        res.warnings.append(f"Q1: {n_items} items < floor {floor:.1f}")

    # ---- coverage hints (M): skip anything the generator already rejected with a reason
    recorded = {m["node_id"] for m in mentions} | {n["node_id"] for n in out["not_mentions"]}
    for c in cards.values():
        if c.in_text and c.node.id not in recorded and ("M1", c.node.id) not in ctx.rejected_keys:
            res.hints.append(
                Hint(
                    "M1",
                    "missed_existing_mention",
                    c.node.name,
                    f"card {c.node.id} appears in the text and was neither recorded nor rejected",
                    ("M1", c.node.id),
                )
            )
    all_names = [c["name"] for c in news] + [m["surface"] for m in mentions]
    known = [f for c in cards.values() for f in c.node.forms()]
    seen_m2: set[str] = set()
    for label, spans, quote in [
        (c["name"], [c["name"], *c["aliases"]], c["evidence"]) for c in news
    ] + [(m["surface"], [m["surface"]], m["evidence"]) for m in mentions]:
        for fl in find_partial_spans(
            spans,
            quote,
            ctx.nlp,
            all_items=all_names,
            known_forms=known,
            emphasised=ctx.emphasised,
            recurring=ctx.recurring,
            noun_forms=ctx.noun_forms,
            cfg=cfg,
        ):
            key = ("M2", _nl(fl.span))
            if key not in ctx.rejected_keys and key[1] not in seen_m2:
                seen_m2.add(key[1])
                res.hints.append(
                    Hint(
                        "M2",
                        "longer_span",
                        fl.longer,
                        f"the item {fl.span!r} may be the tail of {fl.longer!r}",
                        key,
                    )
                )
    for i, c in enumerate(news):
        if c["extraction_origin"] != "independent":
            continue
        # a card named only INSIDE the new concept's own span is an inside_longer_term case, not a relation
        sent = re.sub(
            re.escape(c["name"]), " ", _sentence_of(c["evidence"], text), flags=re.IGNORECASE
        )
        toks = {t for t in re.findall(r"[a-z0-9]+", c["name"].lower()) if len(t) > 2}
        for card in cards.values():
            if not any(_contains(sent, f) for f in card.node.forms()):
                continue
            ct = {t for t in re.findall(r"[a-z0-9]+", card.node.name.lower()) if len(t) > 2}
            if (_head(c["name"]) and _head(c["name"]) == _head(card.node.name)) or (toks & ct):
                key = ("M3", f"{_nl(c['name'])}|{card.node.id}")
                if key not in ctx.rejected_keys:
                    res.hints.append(
                        Hint(
                            "M3",
                            "possible_anchor_missed",
                            c["name"],
                            f"{c['name']!r} shares a word with listed node {card.node.name!r} named in the same sentence",
                            key,
                        )
                    )
    if ctx.m4:
        res.hints += _m4(out, ctx)
    if ctx.m5:
        res.hints += _m5(out, ctx)
    return res


def _covered(term: str, out: dict, cfg: AliasConfig) -> bool:
    k = r1_key(term, cfg)
    names = (
        [c["name"] for c in out["new_concepts"]]
        + [a for c in out["new_concepts"] for a in c["aliases"]]
        + [m["surface"] for m in out["existing_mentions"]]
    )
    return any(_nl(term) in _nl(x) or _nl(x) in _nl(term) or r1_key(x, cfg) == k for x in names)


_DEF_PATTERNS = (
    re.compile(
        r"(?:called|known as|termed|named|referred to as)\s+(?:the\s+)?([A-Za-z][\w-]*(?:\s+[A-Za-z][\w-]*){0,2})"
    ),
    re.compile(r"\b([A-Z][\w-]*(?:\s+[a-z][\w-]*){0,2})\s+(?:is|are)\s+(?:a|an)\s"),
)


def _m4(out: dict, ctx: VerifyCtx) -> list[Hint]:
    """Optional: a definition-pattern term, an R2 long form or an emphasised term that no item covers."""
    cfg = _cfg()
    cand: dict[str, str] = {}
    for p in _DEF_PATTERNS:
        for m in p.finditer(ctx.section_text):
            cand.setdefault(_nl(m.group(1)), "defined by a pattern")
    for ab in find_abbreviations(ctx.section_text, cfg):
        cand.setdefault(_nl(ab.long_form), "an acronym's long form")
    for e in ctx.emphasised:
        cand.setdefault(_nl(e), "an emphasised term")
    hints = []
    for term, why in cand.items():
        if (
            len(term.split()) <= 4
            and not _covered(term, out, cfg)
            and ("M4", term) not in ctx.rejected_keys
        ):
            hints.append(
                Hint(
                    "M4",
                    "missed_candidate",
                    term,
                    f"{term!r} looks like a concept ({why}) that no item covers",
                    ("M4", term),
                )
            )
    return hints


def _m5(out: dict, ctx: VerifyCtx) -> list[Hint]:
    """Optional: a noun chunk recurring >= 2 times in the chapter that contains an item and is not an item."""
    names = {_nl(c["name"]) for c in out["new_concepts"]} | {
        _nl(m["surface"]) for m in out["existing_mentions"]
    }
    textl = _nl(ctx.section_text)
    hints = []
    for it in sorted(names):
        iw = re.findall(r"[a-z0-9]+", it)
        best = None
        for chunk, n in ctx.recurring.items():
            cw = re.findall(r"[a-z0-9]+", chunk)
            if (
                n >= 2
                and len(iw) < len(cw) <= 4
                and any(cw[i : i + len(iw)] == iw for i in range(len(cw) - len(iw) + 1))
                and chunk not in names
                and chunk in textl
            ) and (best is None or n > best[1]):
                best = (chunk, n)
        if best and ("M5", it) not in ctx.rejected_keys:
            hints.append(
                Hint(
                    "M5",
                    "longer_span",
                    best[0],
                    f"the item {it!r} may be part of the recurring term {best[0]!r}",
                    ("M5", it),
                )
            )
    return hints


# ---------------------------------------------------------------- policy helpers
def flagged_items(flags: list[Flag]) -> set[tuple[str, int]]:
    return {(f.where, f.idx) for f in flags if f.where in {"mention", "new"}}


def drop_flagged(out: dict, flags: list[Flag]) -> tuple[dict, list[dict]]:
    """Remove the items that carry F/C flags; returns the reduced output and rejected-record dicts."""
    out = copy.deepcopy(out)
    rejected = []
    for where, key in (("mention", "existing_mentions"), ("new", "new_concepts")):
        idxs = sorted({f.idx for f in flags if f.where == where}, reverse=True)
        for i in idxs:
            if i < len(out[key]):
                item = out[key].pop(i)
                rejected.append(
                    {
                        "kind": key,
                        "rules": sorted({f.rule for f in flags if f.where == where and f.idx == i}),
                        "item": item,
                    }
                )
    return out, rejected
