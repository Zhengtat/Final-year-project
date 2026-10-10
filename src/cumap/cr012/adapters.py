"""CR-012 benchmark adapters (CR section 5). The workflow architecture is the same everywhere; only the loader, schema / config,
label names, scoring conversion and input formatting differ. External schemas stay external: nothing is translated into networking
labels. SciNLP is read as DATA ONLY (JSON parsing); nothing in the clone is executed."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from cumap.config import REPO_ROOT
from cumap.cr012.types import GoldMention, GoldRelation, UnitGold

SCINLP_DIR = REPO_ROOT / "data/raw/external/scinlp/Dataset"
SCINLP_LABEL = "SciNLP-repo-e78342be"
# paper (v3) definitions with the repository's own label spelling; domain / range follow the paper and are observed in >= 97% of gold
SCINLP_RELATIONS = {
    "UsedFor": {"domain": ["method"], "range": ["task"], "symmetric": False},
    "MeasuredBy": {"domain": ["method"], "range": ["metric"], "symmetric": False},
    "trainedWith": {"domain": ["method"], "range": ["dataset"], "symmetric": False},
    "enhancedBy": {"domain": ["method"], "range": ["method"], "symmetric": False},
    "evaluatedBy": {"domain": ["task"], "range": ["metric"], "symmetric": False},
    "evaluatedOn": {"domain": ["task"], "range": ["dataset"], "symmetric": False},
    "subclassOf": {"domain": ["method"], "range": ["method"], "symmetric": False},
    "subtaskOf": {"domain": ["task"], "range": ["task"], "symmetric": False},
    "partOf": {
        "domain": ["method", "task", "dataset"],
        "range": ["method", "task", "dataset"],
        "symmetric": False,
    },
    "compareWith": {
        "domain": ["method", "task", "dataset", "metric"],
        "range": ["method", "task", "dataset", "metric"],
        "symmetric": True,
    },
    "similarWith": {
        "domain": ["method", "task", "dataset", "metric"],
        "range": ["method", "task", "dataset", "metric"],
        "symmetric": True,
    },
}
SCINLP_ENTITY_TYPES = ["method", "task", "metric", "dataset"]


class BenchmarkAdapter(ABC):
    name: str

    @abstractmethod
    def load_documents(self, split: str) -> list[dict]: ...
    @abstractmethod
    def entity_types(self) -> list[str]: ...
    @abstractmethod
    def relation_registry(self) -> dict: ...
    @abstractmethod
    def gold(self, split: str) -> dict[str, UnitGold]: ...
    def gold_clusters(self, split: str) -> dict[str, list[list[GoldMention]]] | None:
        return None  # optional; SciNLP has none

    def symmetric_relations(self) -> set[str]:
        return {r for r, d in self.relation_registry().items() if d.get("symmetric")}


@dataclass(frozen=True)
class SciNLPDoc:
    doc_key: str
    tokens: list[str]  # document-level token list
    sentence_ends: list[int]  # exclusive end token index of each sentence
    text: str
    token_offsets: list[tuple[int, int]]  # char (start, end) of every token in `text`
    word_count: int

    def span_to_chars(self, span: tuple[int, int]) -> tuple[int, int]:
        s, e = span  # half-open token span
        return self.token_offsets[s][0], self.token_offsets[e - 1][1]

    def chars_to_span(self, start: int, end: int) -> tuple[int, int] | None:
        """Exact token span for a character range, or None when the range does not coincide with token boundaries."""
        ts = [i for i, (a, _b) in enumerate(self.token_offsets) if a == start]
        te = [i for i, (_a, b) in enumerate(self.token_offsets) if b == end]
        if len(ts) != 1 or len(te) != 1 or te[0] < ts[0]:
            return None
        return ts[0], te[0] + 1


def detokenise(
    sentences: list[list[str]], paragraph_every: int | None = None
) -> tuple[str, list[tuple[int, int]], list[int]]:
    """Lossless: tokens joined by single spaces, sentences by a newline (a blank line every `paragraph_every` sentences when set: SciNLP has
    no paragraph structure and the production unit splitter works on paragraphs). Every token keeps an exact character range, so a strict
    token span survives the round trip. (Natural punctuation attachment would lose this exactness, so it is not used.)"""
    parts, offsets, ends, pos, n_tok = [], [], [], 0, 0
    for si, sent in enumerate(sentences):
        for ti, tok in enumerate(sent):
            offsets.append((pos, pos + len(tok)))
            parts.append(tok)
            pos += len(tok)
            if ti < len(sent) - 1:
                parts.append(" ")
                pos += 1
        n_tok += len(sent)
        ends.append(n_tok)
        if si < len(sentences) - 1:
            sep = "\n\n" if paragraph_every and (si + 1) % paragraph_every == 0 else "\n"
            parts.append(sep)
            pos += len(sep)
    return "".join(parts), offsets, ends


class SciNLPAdapter(BenchmarkAdapter):
    name = SCINLP_LABEL

    def __init__(self, root: Path = SCINLP_DIR):
        self.root = root

    def _raw(self, split: str) -> list[dict]:
        assert split in {"train", "dev", "test"}
        text = (self.root / f"{split}.json").read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def load_documents(self, split: str, paragraph_every: int | None = None) -> list[SciNLPDoc]:  # type: ignore[override]
        docs = []
        for d in self._raw(split):
            text, offs, ends = detokenise(d["sentences"], paragraph_every)
            toks = [t for s in d["sentences"] for t in s]
            docs.append(SciNLPDoc(d["doc_key"], toks, ends, text, offs, len(toks)))
        return docs

    def entity_types(self) -> list[str]:
        return list(SCINLP_ENTITY_TYPES)

    def relation_registry(self) -> dict:
        return SCINLP_RELATIONS

    def gold(self, split: str) -> dict[str, UnitGold]:
        out: dict[str, UnitGold] = {}
        for d in self._raw(split):
            g = UnitGold(unit=d["doc_key"])
            types: dict[tuple[int, int], str] = {}
            for sn in d["ner"]:
                for s, e, t in sn:  # the repository's boundaries are inclusive token indices
                    span = (s, e + 1)
                    g.mentions.append(GoldMention(d["doc_key"], span, t))
                    types[span] = t
            for sr in d["relations"]:
                for s1, e1, s2, e2, r in sr:
                    g.relations.append(
                        GoldRelation(d["doc_key"], r, src_span=(s1, e1 + 1), tgt_span=(s2, e2 + 1))
                    )
            out[d["doc_key"]] = g
        return out

    def official_score(self, *a, **k):  # pragma: no cover - there is none
        raise NotImplementedError(
            "the audited SciNLP repository contains no official scorer; use the CR-012 SciNLP strict scorer"
        )
