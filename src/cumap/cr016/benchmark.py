"""CR-016 STOP 2: retrieval-only benchmark construction on EXPOSED material (strictly causal order; fresh allocation untouched).

Outputs (data/processed/cr016/stage2/):
  corpus.jsonl     paragraph chunks of the exposed units in book order, with provenance (this is what the memories index)
  queries.jsonl    RUNTIME-VISIBLE query inputs only (id, section, source order, surface, source sentence, query text); no gold, no answers
  key.jsonl        the answer key (relevant paragraph ids, slice flags, support); read only by scoring
Relevance of an earlier paragraph to a query concept K = it contains a gold MENTION of K (gold-linked) OR a word-bounded occurrence of a surface of K (lexical), where the surfaces of
K are its gold canonical name, aliases and mention surfaces. Same-surface-different-sense cases restrict relevance to K-specific evidence. Concept identity across sections = normalised
canonical name (the gold sets do not annotate cross-set identity). Gold is exposed development material; the fresh allocation (4.3, 6.2, 5.2, 6.5, 9.1, 9.4, and untouched 5.1, 8.1) is excluded."""

from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(".")
OUT = ROOT / "data/processed/cr016/stage2"
CFG = yaml.safe_load((ROOT / "configs/cr016_stage2.yaml").read_text())
FRESH = set(CFG["fresh_excluded"])
norm = lambda s: " ".join(s.lower().split())


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def load_corpus() -> tuple[list[dict], dict[str, int]]:
    secs = [
        json.loads(line)
        for line in (ROOT / "data/interim/textbook_sections.jsonl").read_text().splitlines()
    ]
    order = {s["section_id"]: i for i, s in enumerate(secs)}
    chunks = []
    for s in secs:
        if s["section_id"] in FRESH:
            continue
        for i, p in enumerate(paragraphs(s["text"])):
            chunks.append(
                {
                    "chunk_id": f"{s['section_id']}#p{i}",
                    "section_id": s["section_id"],
                    "paragraph": i,
                    "source_order": order[s["section_id"]],
                    "text": p,
                    "source_hash": hashlib.sha256(p.encode()).hexdigest()[:12],
                }
            )
    return chunks, order


def _para_of(chunks_by_sec: dict[str, list[dict]], sid: str, sentence: str) -> str | None:
    s = norm(sentence)
    for c in chunks_by_sec.get(sid, []):
        if s in norm(c["text"]):
            return c["chunk_id"]
    probe = s[:60]
    for c in chunks_by_sec.get(sid, []):
        if probe and probe in norm(c["text"]):
            return c["chunk_id"]
    return None


def load_gold() -> list[dict]:
    """Mention-level gold records: {section, set, concept_key, surface, sentence, canonical, aliases}."""
    out = []
    # CR-014 / CR-015-style sheets (CONCEPT / MENTION rows + a separate sentence file)
    for name, sheet, sents in (
        (
            "cr014_heldout",
            "data/gold/pd_concept_test_blind.csv",
            "data/interim/checks/cr014/pd_concept_test_sentences.csv",
        ),
        (
            "cr014_pilot",
            "data/gold/pd_concept_pilot_blind.csv",
            "data/interim/checks/cr014/pd_concept_pilot_sentences.csv",
        ),
    ):
        st = {r["sentence_id"]: r for r in csv.DictReader((ROOT / sents).open(encoding="utf-8"))}
        rows = list(csv.DictReader((ROOT / sheet).open(encoding="utf-8-sig")))
        canon = {
            r["concept_id"]: (
                r["canonical_name"],
                [a for a in (r["aliases"] or "").split("|") if a],
            )
            for r in rows
            if r["row_type"] == "CONCEPT"
        }
        for r in rows:
            if r["row_type"] != "MENTION":
                continue
            cn, al = canon.get(r["concept_id"], (r["span_text"], []))
            s = st[r["sentence_id"]]
            out.append(
                {
                    "set": name,
                    "section": s["section_id"],
                    "concept_id": r["concept_id"],
                    "key": norm(cn),
                    "canonical": cn,
                    "aliases": al,
                    "surface": r["span_text"].strip(),
                    "sentence": s["sentence_text"],
                }
            )
    # CR-012 sheets (self-contained SENTENCE / CONCEPT / MENTION rows)
    for name, sheet in (
        ("cr012_pilot", "data/gold/pd_e2e_pilot_blind.csv"),
        ("cr012_heldout", "data/gold/pd_e2e_test_blind.csv"),
    ):
        rows = list(csv.DictReader((ROOT / sheet).open(encoding="utf-8-sig")))
        sent = {
            (r["section_id"], r["sentence_id"]): r["text"]
            for r in rows
            if r["row_type"] == "SENTENCE"
        }
        canon = {
            (r["section_id"], r["concept_id"]): (
                r["canonical_name"],
                [a for a in (r["aliases"] or "").split("|") if a],
            )
            for r in rows
            if r["row_type"] == "CONCEPT"
        }
        for r in rows:
            if r["row_type"] != "MENTION":
                continue
            cn, al = canon.get((r["section_id"], r["concept_id"]), (r["span_text"], []))
            out.append(
                {
                    "set": name,
                    "section": r["section_id"],
                    "concept_id": f"{r['section_id']}:{r['concept_id']}",
                    "key": norm(cn),
                    "canonical": cn,
                    "aliases": al,
                    "surface": r["span_text"].strip(),
                    "sentence": sent.get((r["section_id"], r["sentence_id"]), ""),
                }
            )
    return [g for g in out if g["section"] not in FRESH and g["sentence"]]


def is_acronym(s: str) -> bool:
    t = s.strip()
    return 2 <= len(t) <= 8 and t.replace("-", "").isalpha() and t.upper() == t


def initials_match(acr: str, long: str) -> bool:
    words = [w for w in re.split(r"[\s\-]+", long) if w]
    a = acr.replace("-", "").upper()
    return len(words) >= 2 and "".join(w[0].upper() for w in words) == a


def _lex(surface: str) -> re.Pattern:
    return re.compile(
        r"(?<!\w)" + r"\s+".join(re.escape(w) for w in surface.split()) + r"(?!\w)", re.IGNORECASE
    )


def build() -> dict:
    chunks, order = load_corpus()
    by_sec: dict[str, list[dict]] = defaultdict(list)
    for c in chunks:
        by_sec[c["section_id"]].append(c)
    gold = load_gold()
    # concept surfaces and gold-linked paragraphs per key
    surfaces: dict[str, set[str]] = defaultdict(set)
    glinked: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )  # key -> section -> {chunk ids}
    surf_keys: dict[str, set[str]] = defaultdict(
        set
    )  # normalised surface -> concept keys that use it
    for g in gold:
        k = g["key"]
        surfaces[k] |= {norm(g["canonical"]), norm(g["surface"]), *(norm(a) for a in g["aliases"])}
        pid = _para_of(by_sec, g["section"], g["sentence"])
        if pid:
            glinked[k][g["section"]].add(pid)
        surf_keys[norm(g["surface"])].add(k)
        surf_keys[norm(g["canonical"])].add(k)
    text_n = {c["chunk_id"]: norm(c["text"]) for c in chunks}
    sec_of = {c["chunk_id"]: c["source_order"] for c in chunks}
    pats: dict[str, re.Pattern] = {}
    lex_cache: dict[str, set[str]] = {}

    def lex_hits(surface: str) -> set[str]:
        if surface not in lex_cache:
            p = pats.setdefault(surface, _lex(surface))
            lex_cache[surface] = {cid for cid, t in text_n.items() if p.search(t)}
        return lex_cache[surface]

    cases = []
    seen = set()
    for g in sorted(gold, key=lambda x: (order[x["section"]], x["key"])):
        sec, k, s = g["section"], g["key"], norm(g["surface"])
        if (sec, k) in seen or not s:
            continue
        seen.add((sec, k))
        n = order[sec]
        earlier = {c["chunk_id"] for c in chunks if c["source_order"] < n}
        ks = surfaces[k]
        sense_hard = len(surf_keys[s]) > 1
        rel_lex: set[str] = set()
        for sf in ks:
            if sense_hard and sf == s:
                continue  # the shared surface alone cannot establish the target sense
            rel_lex |= lex_hits(sf) & earlier
        rel_g = {cid for sec2, ids in glinked[k].items() if order[sec2] < n for cid in ids}
        rel = rel_lex | rel_g
        if not rel:
            continue
        exact_ids = lex_hits(s) & earlier
        alias_surfs = [x for x in ks if x != s and norm(x).rstrip("s") != s.rstrip("s")]
        alias_ids = (
            set().union(*(lex_hits(x) & earlier for x in alias_surfs)) if alias_surfs else set()
        )
        acr = (
            is_acronym(g["surface"]) and any(initials_match(g["surface"], x) for x in ks)
        ) or any(is_acronym(x) and initials_match(x, g["surface"]) for x in ks)
        toks = s.split()
        boundary = False
        if len(toks) >= 2 and not exact_ids:
            for x in ks:
                xt = x.split()
                if (
                    x != s
                    and (_contains(xt, toks) or _contains(toks, xt))
                    and lex_hits(x) & earlier
                ):
                    boundary = True
        gap = min(n - sec_of[cid] for cid in rel)
        flags = {
            "exact_surface": bool(exact_ids), "alias": bool(alias_ids) and not exact_ids, "acronym": bool(acr), "one_token": len(toks) == 1, "different_boundary": boundary,
            "short_gap": gap <= CFG["gap"]["short_max_units"], "long_gap": gap >= CFG["gap"]["long_min_units"], "associative_low_lexical_overlap": not bool(exact_ids & rel), "same_surface_different_sense": sense_hard,
        }  # fmt: skip
        flags["alias"] = (
            bool(alias_ids) and not bool(exact_ids & rel) or (bool(alias_ids) and not exact_ids)
        )
        size = len(rel)
        flags["support_rare_le5"], flags["support_medium_6_30"], flags["support_common_gt30"] = (
            size <= 5,
            6 <= size <= 30,
            size > 30,
        )
        cases.append(
            {
                "set": g["set"],
                "section": sec,
                "source_order": n,
                "key": k,
                "surface": g["surface"],
                "sentence": g["sentence"],
                "relevant": sorted(rel),
                "n_relevant": size,
                "gap": gap,
                "flags": flags,
            }
        )
    return {"chunks": chunks, "cases": cases, "order": order}


def _contains(a: list[str], b: list[str]) -> bool:
    return any(a[i : i + len(b)] == b for i in range(len(a) - len(b) + 1))


def sample(cases: list[dict]) -> list[dict]:
    rng = random.Random(CFG["sampling"]["seed"])
    rare_slices = CFG["sampling"]["take_all_if_in"]
    chosen, rest = [], []
    for c in cases:
        (chosen if any(c["flags"][f] for f in rare_slices) else rest).append(c)
    rng.shuffle(rest)
    budget = CFG["sampling"]["max_queries"] - len(chosen)
    return sorted(chosen + rest[: max(budget, 0)], key=lambda c: (c["source_order"], c["key"]))


def main(write: bool = True) -> dict:
    b = build()
    cases = b["cases"]
    picked = sample(cases)
    stats = {"corpus_chunks": len(b["chunks"]), "corpus_sections": len({c["section_id"] for c in b["chunks"]}), "cases_with_valid_earlier_evidence": len(cases), "queries_sampled": len(picked),
             "slice_support_all": {f: sum(c["flags"][f] for c in cases) for f in cases[0]["flags"]}, "slice_support_sampled": {f: sum(c["flags"][f] for c in picked) for f in cases[0]["flags"]},
             "query_sections": sorted({c["section"] for c in picked}, key=lambda s: b["order"][s])}  # fmt: skip
    if write:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "corpus.jsonl").write_text("\n".join(json.dumps(c) for c in b["chunks"]) + "\n")
        tmpl = CFG["query"]["template"]
        qs, ks = [], []
        for i, c in enumerate(picked):
            qid = f"Q{i:05d}"
            qs.append(
                {
                    "query_id": qid,
                    "query_section": c["section"],
                    "source_order": c["source_order"],
                    "surface": c["surface"],
                    "sentence": c["sentence"],
                    "query_text": tmpl.format(surface=c["surface"], sentence=c["sentence"]),
                }
            )
            ks.append({"query_id": qid, **{k: v for k, v in c.items() if k not in ("sentence",)}})
        (OUT / "queries.jsonl").write_text("\n".join(json.dumps(q) for q in qs) + "\n")
        (OUT / "key.jsonl").write_text("\n".join(json.dumps(k) for k in ks) + "\n")
        stats["queries_sha256"] = hashlib.sha256((OUT / "queries.jsonl").read_bytes()).hexdigest()
        stats["corpus_sha256"] = hashlib.sha256((OUT / "corpus.jsonl").read_bytes()).hexdigest()
        stats["key_sha256"] = hashlib.sha256((OUT / "key.jsonl").read_bytes()).hexdigest()
    return stats


if __name__ == "__main__":
    s = main()
    Path("reports/cr016").mkdir(parents=True, exist_ok=True)
    Path("reports/cr016/benchmark_stats.json").write_text(json.dumps(s, indent=1))
    print(json.dumps(s, indent=1))
