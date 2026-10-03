"""CR-008 §3: the deterministic merge layer that runs before any embedding or LLM merge call.

Order R0 (lexicon `same`) -> R1 (normalisation key) -> R2 (acronym-expansion) -> R3-strong
(textbook alias statement). The first match applies. The lexicon `different` list is a guard on
every rule; the R1 acronym guard and the CR-007 type check apply to R1-R3. Every hit carries a
rule id and evidence, so a merge is auditable and reversible (add a lexicon `different` entry).
R3-weak statements never merge; they are exposed for the review sheet.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from cumap.expert_kg.alias_rules import (
    AliasConfig,
    AliasStatement,
    acronym_collision,
    alias_statements,
    find_abbreviations,
    r1_key,
    split_embedded_acronym,
)
from cumap.expert_kg.lexicon import Lexicon

GENERIC_TYPE = "Concept"


@dataclass(frozen=True)
class RuleHit:
    rule_id: str  # R0 | R1 | R2 | R3-strong
    evidence_quote: str
    surface_forms: tuple[str, str]
    section_id: str | None = None


def types_compatible(a: str, b: str) -> bool:
    return a == b or GENERIC_TYPE in (a, b)


@dataclass
class AliasContext:
    lexicon: Lexicon
    cfg: AliasConfig
    chapter_of: dict[str, int]
    # (short_key, long_key) -> (quote, section_id, chapters it is defined in)
    abbrev: dict[frozenset[str], tuple[str, str, set[int]]] = field(default_factory=dict)
    ambiguous_shorts: dict[str, set[str]] = field(default_factory=dict)
    strong: dict[frozenset[str], AliasStatement] = field(default_factory=dict)
    weak: dict[frozenset[str], list[AliasStatement]] = field(default_factory=dict)
    stats: Counter = field(default_factory=Counter)

    @classmethod
    def build(
        cls,
        lexicon: Lexicon,
        section_texts: dict[str, str],
        chapter_of: dict[str, int],
        surface_forms: Iterable[str],
        cfg: AliasConfig | None = None,
    ) -> AliasContext:
        cfg = cfg or lexicon.cfg
        ctx = cls(lexicon, cfg, chapter_of)
        vocab = {f.lower(): r1_key(f, cfg) for f in surface_forms if r1_key(f, cfg)}
        shorts: dict[str, set[str]] = defaultdict(set)
        for sid, text in section_texts.items():
            for p in find_abbreviations(text, cfg):
                lk, sk = r1_key(p.long_form, cfg), r1_key(p.short_form, cfg)
                shorts[sk].add(lk)
                quote = " ".join(p.sentence.split())
                _q, _s, chs = ctx.abbrev.get(frozenset((lk, sk)), (quote, sid, set()))
                chs.add(chapter_of.get(sid, -1))
                ctx.abbrev[frozenset((lk, sk))] = (_q, _s, chs)
            for st in alias_statements(text, vocab, cfg):
                key = frozenset((st.x_id, st.y_id))
                if st.strength == "strong":
                    ctx.strong.setdefault(key, st)
                else:
                    ctx.weak.setdefault(key, []).append(st)
        ctx.ambiguous_shorts = {k: v for k, v in shorts.items() if len(v) >= 2}
        return ctx

    # ---------------------------------------------------------------- one pair of forms
    def pair_rule(
        self, a: str, b: str, chapter: int | None, *, a_type: str, b_type: str, type_aware: bool
    ) -> RuleHit | None:
        """The first of R0-R3-strong that merges forms a and b, or None. Counts what a guard blocked."""
        cfg, lex = self.cfg, self.lexicon
        if lex.is_different(a, b, chapter):
            self.stats["blocked_by_lexicon"] += 1
            return None
        if e := lex.same_decision(a, b, chapter):
            return RuleHit("R0", e.quote or e.source, (a, b), None)
        if type_aware and not types_compatible(a_type, b_type):
            return None
        ka, kb = r1_key(a, cfg), r1_key(b, cfg)
        if ka and ka == kb:
            if acronym_collision(a, b, cfg):
                self.stats["r1_acronym_collision"] += 1
                return None
            return RuleHit("R1", f"{a} = {b} (same normalisation key)", (a, b))
        for x, y, ky in ((a, b, kb), (b, a, ka)):
            sp = split_embedded_acronym(x, cfg)
            if sp and ky in (r1_key(sp[0], cfg), r1_key(sp[1], cfg)):
                return RuleHit("R2", x, (a, b))
        hit = self.abbrev.get(frozenset((ka, kb)))
        if hit:
            quote, sid, chapters = hit
            short_key = min((ka, kb), key=len)
            if short_key in self.ambiguous_shorts and chapter not in chapters:
                self.stats["r2_ambiguous_scoped_out"] += 1
                return None
            return RuleHit("R2", quote, (a, b), sid)
        if (st := self.strong.get(frozenset((ka, kb)))) is not None:
            return RuleHit("R3-strong", st.quote, (a, b))
        return None

    # ---------------------------------------------------------------- against a registry
    def find_merge(
        self, concepts, name: str, node_type: str, section_id: str, *, type_aware: bool = True
    ) -> tuple[object, RuleHit] | None:
        """(registry concept, hit) for the best rule over all concepts (R0 before R1 before R2...)."""
        chapter = self.chapter_of.get(section_id)
        order = {"R0": 0, "R1": 1, "R2": 2, "R3-strong": 3}
        best: tuple[int, object, RuleHit] | None = None
        for c in concepts:
            for form in (c.canonical_name, *c.aliases):
                hit = self.pair_rule(
                    name, form, chapter, a_type=node_type, b_type=c.node_type, type_aware=type_aware
                )
                if hit and (best is None or order[hit.rule_id] < best[0]):
                    best = (order[hit.rule_id], c, hit)
                    if best[0] == 0:
                        return best[1], best[2]
        return (best[1], best[2]) if best else None

    def weak_hints(self, name: str, other: str) -> list[AliasStatement]:
        return self.weak.get(frozenset((r1_key(name, self.cfg), r1_key(other, self.cfg))), [])
