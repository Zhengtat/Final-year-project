"""CR-060 Part B: noun-phrase candidates for the concept generator, ranked by how related they are to their sentences, to the paper and to
the paper's other noun phrases. Gold-free and model-free (spaCy + the local sentence embedder); the ranking only orders HINTS, the generator
adds or rejects each (rule 24), and similarity never decides on its own (rule 1).

Candidates: every spaCy noun chunk, trimmed of determiners / quantifiers / numerals / possessives (`partial_span._strip`), and each suffix of
it ending at the chunk head ("pre-trained BERT model" -> "BERT model", "model"), at most MAX_TOKENS tokens. Features (pre-registered,
2026-10-30), each turned into a percentile rank among the paper's candidates and averaged with EQUAL weights:
  freq      occurrences in the paper (as a chunk or chunk suffix);
  cvalue    C-value termhood: log2(n_tokens + 1) * (freq - mean freq of the longer candidates that contain it);
  central   PageRank in the paper's co-occurrence graph (candidates from different chunks of one sentence are linked);
  sent_sim  mean cosine similarity to the sentences it occurs in (at most 3);
  doc_sim   cosine similarity to the paper (the mean of its sentence embeddings)."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

import networkx as nx
import numpy as np

from cumap.expert_kg.alias_rules import AliasConfig, r1_key
from cumap.expert_kg.partial_span import _strip

MAX_TOKENS = 6
FEATURES = ("freq", "cvalue", "central", "sent_sim", "doc_sim")
_CFG = AliasConfig.load()
_SKIP_POS = {"PRON", "NUM", "PUNCT", "SYM", "X", "SPACE", "DET", "CCONJ", "ADP", "PART"}


@dataclass
class Cand:
    key: str
    text: str
    n_tokens: int
    freq: int = 0
    units: Counter = field(default_factory=Counter)
    sentences: list[int] = field(default_factory=list)
    features: dict[str, float] = field(default_factory=dict)
    score: float = 0.0


def _ok(toks) -> bool:
    if not toks or toks[0].pos_ in _SKIP_POS or toks[-1].pos_ in _SKIP_POS:
        return False
    s = " ".join(t.text for t in toks)
    return bool(re.search(r"[A-Za-z]{2}", s)) and not (len(toks) == 1 and toks[0].is_stop)


def extract(units: dict[str, str], nlp) -> tuple[dict[str, Cand], list[str], list[list[set[str]]]]:
    """-> (candidates by R1 key, the paper's sentences, per sentence the candidate-key sets of its chunks)."""
    cands: dict[str, Cand] = {}
    sents: list[str] = []
    chunks_by_sent: list[list[set[str]]] = []
    for uid, text in units.items():
        doc = nlp(text)
        for s in doc.sents:
            si = len(sents)
            sents.append(s.text.strip())
            groups: list[set[str]] = []
            for ch in s.noun_chunks:
                toks = [t for t in _strip(ch) if not t.is_punct]
                group: set[str] = set()
                for i in range(max(0, len(toks) - MAX_TOKENS), len(toks)):
                    sub = toks[i:]
                    if not _ok(sub):
                        continue
                    surf = " ".join(t.text for t in sub)
                    k = r1_key(surf, _CFG)
                    if not k:
                        continue
                    c = cands.setdefault(k, Cand(k, surf, len(sub)))
                    c.freq += 1
                    c.units[uid] += 1
                    if len(c.sentences) < 3 and c.sentences[-1:] != [si]:
                        c.sentences.append(si)
                    group.add(k)
                if group:
                    groups.append(group)
            chunks_by_sent.append(groups)
    return cands, sents, chunks_by_sent


def _cvalue(cands: dict[str, Cand]) -> dict[str, float]:
    longer: dict[str, list[int]] = defaultdict(list)
    texts = {k: " " + " ".join(c.text.lower().split()) + " " for k, c in cands.items()}
    by_len = sorted(cands, key=lambda k: cands[k].n_tokens)
    for i, a in enumerate(by_len):
        for b in by_len[i + 1 :]:
            if cands[b].n_tokens > cands[a].n_tokens and texts[a] in texts[b]:
                longer[a].append(cands[b].freq)
    out = {}
    for k, c in cands.items():
        nest = (sum(longer[k]) / len(longer[k])) if longer[k] else 0.0
        out[k] = math.log2(c.n_tokens + 1) * (c.freq - nest)
    return out


def _central(cands: dict[str, Cand], chunks_by_sent: list[list[set[str]]]) -> dict[str, float]:
    g = nx.Graph()
    g.add_nodes_from(cands)
    w: Counter = Counter()
    for groups in chunks_by_sent:
        for i, a in enumerate(groups):
            for b in groups[i + 1 :]:
                for x in a:
                    for y in b:
                        if x != y:
                            w[tuple(sorted((x, y)))] += 1
    g.add_weighted_edges_from((x, y, n) for (x, y), n in w.items())
    return nx.pagerank(g, weight="weight") if g.number_of_edges() else {k: 0.0 for k in cands}


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    d = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(a @ b) / d if d else 0.0


def _pct(vals: dict[str, float]) -> dict[str, float]:
    """Percentile rank in [0, 1]; ties share their mean rank."""
    order = sorted(vals, key=lambda k: vals[k])
    n, out, i = len(order), {}, 0
    while i < n:
        j = i
        while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        r = (i + j) / 2 / (n - 1) if n > 1 else 1.0
        for k in order[i : j + 1]:
            out[k] = r
        i = j + 1
    return out


def rank(
    units: dict[str, str], nlp, embed_fn: Callable[[str], np.ndarray]
) -> dict[str, list[Cand]]:
    """-> {unit id: candidates occurring in that unit, best first}. Deterministic for a fixed embedder."""
    cands, sents, chunks = extract(units, nlp)
    if not cands:
        return {u: [] for u in units}
    s_emb = [embed_fn(s) for s in sents]
    centroid = np.mean(s_emb, axis=0)
    raw = {f: {} for f in FEATURES}
    cv, pr = _cvalue(cands), _central(cands, chunks)
    for k, c in cands.items():
        e = embed_fn(c.text)
        raw["freq"][k] = float(c.freq)
        raw["cvalue"][k] = cv[k]
        raw["central"][k] = pr.get(k, 0.0)
        raw["sent_sim"][k] = float(np.mean([_cos(e, s_emb[i]) for i in c.sentences[:3]]))
        raw["doc_sim"][k] = _cos(e, centroid)
    pct = {f: _pct(raw[f]) for f in FEATURES}
    for k, c in cands.items():
        c.features = {f: round(raw[f][k], 4) for f in FEATURES}
        c.score = sum(pct[f][k] for f in FEATURES) / len(FEATURES)
    out: dict[str, list[Cand]] = {}
    for u in units:
        here = [c for c in cands.values() if c.units[u]]
        out[u] = sorted(here, key=lambda c: (-c.score, c.key))
    return out
