"""CR-008 §3.0: the curated term lexicon (R0): `same` synonym sets and `different` look-alike pairs.

Only `status: approved` entries take effect. Forms are compared by the R1 key, so case, hyphen and
plural variants of a listed form are covered. A `different` pair is checked through the `same` sets
(if "ARP cache" and "ARP table" are one set, a `different` entry on either blocks both).
The validator refuses to load a lexicon with an unsourced entry, a malformed scope, or one pair in
both lists. Code never writes `data/gold/`; this file lives in `configs/`.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from cumap.expert_kg.alias_rules import AliasConfig, r1_key

LEXICON_PATH = Path("configs/term_lexicon.yaml")
SCOPE = re.compile(r"^(global|book:[A-Za-z0-9_]+|chapter:\d+)$")
STATUSES = {"proposed", "approved"}
DIFFERENT_KINDS = {
    "confusable",
    "kind_of",
    "instance_of",
    "part_of",
    "field_of",
    "predecessor",
    "different_type",
    "book_distinguishes",
}


class LexiconError(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    id: str
    list: str  # same | different
    forms: tuple[str, ...]
    scope: str
    status: str
    source: str
    kind: str | None = None
    why: str | None = None
    quote: str | None = None
    distinction_dimension: str | None = None


def _scope_applies(scope: str, chapter: int | None) -> bool:
    if scope.startswith("chapter:"):
        return chapter is not None and int(scope.split(":")[1]) == chapter
    return True


@dataclass
class Lexicon:
    entries: list[Entry]
    cfg: AliasConfig
    version: str = "0"
    _same: dict[str, str] = field(default_factory=dict, init=False)  # key -> set id
    _scoped: dict[str, list[tuple[str, str]]] = field(default_factory=dict, init=False)

    # ---------------------------------------------------------------- loading
    @classmethod
    def load(cls, path: Path = LEXICON_PATH, cfg: AliasConfig | None = None) -> Lexicon:
        cfg = cfg or AliasConfig.load()
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        entries: list[Entry] = []
        for lst in ("same", "different"):
            for e in raw.get(lst) or []:
                entries.append(
                    Entry(
                        id=str(e.get("id", "")),
                        list=lst,
                        forms=tuple(e.get("forms") or ()),
                        scope=e.get("scope", ""),
                        status=e.get("status", ""),
                        source=(e.get("source") or "").strip(),
                        kind=e.get("kind"),
                        why=e.get("why"),
                        quote=e.get("quote"),
                        distinction_dimension=e.get("distinction_dimension"),
                    )
                )
        lex = cls(entries, cfg, str(raw.get("version", "0")))
        lex.validate()
        return lex

    # ---------------------------------------------------------------- validation
    def validate(self) -> None:
        ids = [e.id for e in self.entries]
        if len(set(ids)) != len(ids):
            raise LexiconError(f"duplicate entry ids: {[i for i in ids if ids.count(i) > 1][:3]}")
        for e in self.entries:
            if not e.id or len(e.forms) < 2:
                raise LexiconError(f"entry {e.id!r}: needs an id and at least two forms")
            if not e.source:
                raise LexiconError(f"entry {e.id}: no source")
            if not SCOPE.match(e.scope):
                raise LexiconError(f"entry {e.id}: malformed scope {e.scope!r}")
            if e.status not in STATUSES:
                raise LexiconError(f"entry {e.id}: status must be one of {sorted(STATUSES)}")
            if e.list == "different" and e.kind not in DIFFERENT_KINDS:
                raise LexiconError(f"entry {e.id}: kind {e.kind!r} is not a known kind")
        same_pairs = self._pairs("same", approved_only=False)
        diff_pairs = self._pairs("different", approved_only=False)
        both = same_pairs & diff_pairs
        if both:
            raise LexiconError(f"pair in both lists: {sorted(sorted(p) for p in both)[:3]}")
        self._index()
        # a different pair that ends up inside one same-set is also a contradiction
        for a, b in (tuple(p) for p in diff_pairs if len(p) == 2):
            if self._same.get(a) and self._same.get(a) == self._same.get(b):
                raise LexiconError(f"a `different` pair is inside one `same` set: {a} / {b}")

    def _pairs(self, lst: str, *, approved_only: bool) -> set[frozenset[str]]:
        out: set[frozenset[str]] = set()
        for e in self.entries:
            if e.list != lst or (approved_only and e.status != "approved"):
                continue
            keys = [r1_key(f, self.cfg) for f in e.forms]
            out.update(frozenset(p) for p in itertools.combinations(keys, 2) if p[0] != p[1])
        return out

    def _index(self) -> None:
        """Union-find over approved `same` entries; `_same[key]` is the set representative."""
        parent: dict[str, str] = {}

        def find(k: str) -> str:
            parent.setdefault(k, k)
            while parent[k] != k:
                parent[k] = parent[parent[k]]
                k = parent[k]
            return k

        for e in self.entries:
            if e.list == "same" and e.status == "approved":
                keys = [r1_key(f, self.cfg) for f in e.forms]
                for k in keys[1:]:
                    parent[find(k)] = find(keys[0])
        self._same = {k: find(k) for k in parent}

    # ---------------------------------------------------------------- queries
    def approved(self, lst: str) -> list[Entry]:
        return [e for e in self.entries if e.list == lst and e.status == "approved"]

    def same_set(self, form: str) -> str | None:
        """Representative key of the approved `same` set containing `form`, if any."""
        return self._same.get(r1_key(form, self.cfg))

    def same_forms(self, form: str) -> set[str]:
        rep = self.same_set(form)
        if rep is None:
            return set()
        return {
            f
            for e in self.approved("same")
            for f in e.forms
            if self._same.get(r1_key(f, self.cfg)) == rep
        }

    def _canon(self, form: str) -> str:
        k = r1_key(form, self.cfg)
        return self._same.get(k, k)

    def different_entry(self, a: str, b: str, chapter: int | None = None) -> Entry | None:
        """The approved `different` entry that forbids treating a and b as one node, if any."""
        ca, cb = self._canon(a), self._canon(b)
        if ca == cb:
            return None
        for e in self.approved("different"):
            if not _scope_applies(e.scope, chapter):
                continue
            keys = {self._canon(f) for f in e.forms}
            if ca in keys and cb in keys:
                return e
        return None

    def is_different(self, a: str, b: str, chapter: int | None = None) -> bool:
        return self.different_entry(a, b, chapter) is not None

    def same_decision(self, a: str, b: str, chapter: int | None = None) -> Entry | None:
        """The approved `same` entry that makes a and b one node (R0), unless a `different` entry
        forbids it (the validator rules that out for approved data, but scopes can differ)."""
        ra, rb = self.same_set(a), self.same_set(b)
        if ra is None or ra != rb or self.is_different(a, b, chapter):
            return None
        for e in self.approved("same"):
            if (
                _scope_applies(e.scope, chapter)
                and self._same.get(r1_key(e.forms[0], self.cfg)) == ra
            ):
                return e
        return None

    def different_partners(self, form: str, chapter: int | None = None) -> set[str]:
        c = self._canon(form)
        out: set[str] = set()
        for e in self.approved("different"):
            if not _scope_applies(e.scope, chapter):
                continue
            if c in {self._canon(f) for f in e.forms}:
                out.update(f for f in e.forms if self._canon(f) != c)
        return out
