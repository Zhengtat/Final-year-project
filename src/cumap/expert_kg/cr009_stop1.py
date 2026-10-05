"""CR-009 STOP 1: $0 diagnostics (a)-(e), (h) and the two owner sheets. No API call.

Reads the CR-007/CR-008 runs, the IIR dev outputs/gold and the drafted bank; writes only `reports/` and
`data/interim/checks/`. Run: `uv run python -m cumap.expert_kg.cr009_stop1`.
"""

from __future__ import annotations

import csv
import json
import random
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import spacy

from cumap.expert_kg.alias_rules import r1_key
from cumap.expert_kg.fewshot_bank import load_bank, validate_bank
from cumap.expert_kg.lexicon import Lexicon
from cumap.expert_kg.mentions import MentionMatcher
from cumap.expert_kg.partial_span import chunk_counts, find_partial_spans, noun_form_lexicon
from cumap.expert_kg.stats import extract_candidate_terms

ROOT = Path(".")
KG = ROOT / "data" / "processed" / "kg"
CHECKS = ROOT / "data" / "interim" / "checks"
REPORT = ROOT / "reports" / "cr009_stop1.md"
SCRATCH_SEED = 7
WORDS_TO_TOKENS = 1.3


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


# ---------------------------------------------------------------- (a) partial-span baseline
def partial_rate(
    items_by_section: dict[str, list[dict]],
    texts: dict[str, str],
    chapter_of: dict[str, str],
    known_before: dict[str, set[str]],
    emph: dict[str, set[str]],
    nlp,
    label: str,
):
    by_ch: dict[str, list[str]] = defaultdict(list)
    for sid, t in texts.items():
        by_ch[chapter_of[sid]].append(t)
    rec = {ch: chunk_counts(ts, nlp) for ch, ts in by_ch.items()}
    nouns = {ch: noun_form_lexicon(ts, nlp) for ch, ts in by_ch.items()}
    n_items = n_found = 0
    flags = []
    for sid, items in items_by_section.items():
        ch = chapter_of[sid]
        all_names = [it["canonical_name"] for it in items]
        for it in items:
            spans = [it["canonical_name"], *it.get("aliases", [])]
            quote = it.get("evidence_quote") or ""
            n_items += 1
            if not any(_norm(s) in _norm(quote) for s in spans):
                continue
            n_found += 1
            fl = find_partial_spans(
                spans,
                quote,
                nlp,
                all_items=all_names,
                known_forms=known_before.get(sid, ()),
                emphasised=emph.get(sid, ()),
                recurring=rec[ch],
                noun_forms=nouns[ch],
            )
            if fl:
                flags.append(
                    {
                        "section": sid,
                        "item": it["canonical_name"],
                        "longer": fl[0].longer,
                        "why": fl[0].why,
                        "quote": quote[:200],
                        "source": it.get("source", "llm"),
                    }
                )
    return {
        "label": label,
        "items": n_items,
        "with_span_in_quote": n_found,
        "flagged": len(flags),
        "rate": len(flags) / max(n_found, 1),
        "flags": flags,
    }


# ---------------------------------------------------------------- (b) propagation audit
def _form_map(concepts: list[dict]) -> dict[str, dict]:
    m: dict[str, dict] = {}
    for c in concepts:
        for f in (c["canonical_name"], *c.get("aliases", [])):
            m.setdefault(f.lower(), c)
    return m


def propagation_audit(cp: dict, order: dict[str, int], seed: int = SCRATCH_SEED):
    """From the RAW per-section mentions (`mentions_by_section`), where `source` is intact: the concept
    records mislabel a node's creating mention as `llm` (ConceptRegistry.add_new dropped the source)."""
    fm = _form_map(cp["concepts"])
    llm_first: dict[str, int] = {}
    for sid, ms in cp["mentions_by_section"].items():
        for m in ms:
            if m["source"] == "llm" and (c := fm.get(m["canonical_name"].lower())):
                llm_first[c["concept_id"]] = min(llm_first.get(c["concept_id"], 10**9), order[sid])
    rows = []
    for sid, ms in cp["mentions_by_section"].items():
        for m in ms:
            if m["source"] != "propagation" or not (c := fm.get(m["canonical_name"].lower())):
                continue
            origin = llm_first.get(c["concept_id"])
            if origin is None:
                continue
            o = order[sid]
            kind = "forward" if o > origin else "backward" if o < origin else "same_section"
            rows.append(
                {
                    "concept": c["canonical_name"],
                    "type": c["node_type"],
                    "definition": c.get("definition"),
                    "section": sid,
                    "quote": m["evidence_quote"],
                    "kind": kind,
                }
            )
    cnt = Counter(r["kind"] for r in rows)
    rng = random.Random(seed)
    fwd = [r for r in rows if r["kind"] == "forward"]
    bwd = [r for r in rows if r["kind"] == "backward"]
    n_b = min(10, len(bwd))
    pick = rng.sample(fwd, min(20 - n_b, len(fwd))) + rng.sample(bwd, n_b)
    rng.shuffle(pick)
    return rows, cnt, pick


# ---------------------------------------------------------------- (c) retriever dry run + backfill detector
def retriever_dry_run(
    cp: dict, sections: list[dict], lexicon: Lexicon, model, k_sem: int = 30, cap: int = 120
):
    order = {s["section_id"]: i for i, s in enumerate(sections)}
    nodes = []
    fm0 = _form_map(cp["concepts"])
    ext0: dict[str, int] = {}
    for sid, ms in cp["mentions_by_section"].items():
        for m in ms:
            if m["source"] == "llm" and (c := fm0.get(m["canonical_name"].lower())):
                ext0[c["concept_id"]] = min(ext0.get(c["concept_id"], 10**9), order[sid])
    for c in cp["concepts"]:
        if c["concept_id"] in ext0:
            nodes.append({**c, "ext": ext0[c["concept_id"]]})
    emb_text = [f"{n['canonical_name']}. {n.get('definition') or ''}" for n in nodes]
    emb = model.encode(emb_text, normalize_embeddings=True, show_progress_bar=False)
    stats = []
    for t, sec in enumerate(sections):
        elig = [i for i, n in enumerate(nodes) if n["ext"] < t]
        if not elig:
            stats.append(
                {
                    "section": sec["section_id"],
                    "cards": 0,
                    "string": 0,
                    "semantic": 0,
                    "partners": 0,
                    "tokens": 0,
                }
            )
            continue
        vocab: dict[str, str] = {}
        for i in elig:
            n = nodes[i]
            forms = {
                n["canonical_name"],
                *n.get("aliases", []),
                *lexicon.same_forms(n["canonical_name"]),
            }
            for f in forms:
                vocab.setdefault(f.lower(), str(i))
        hits = {int(m.concept_id) for m in MentionMatcher(vocab).find(sec["text"])}
        paras = [p for p in re.split(r"\n\s*\n", sec["text"]) if p.strip()]
        pe = model.encode(paras, normalize_embeddings=True, show_progress_bar=False)
        sims = pe @ emb[elig].T  # paragraphs x eligible
        best = sims.max(axis=0)
        sem_rank = [elig[j] for j in np.argsort(-best) if elig[j] not in hits][:k_sem]
        # lexicon `different` partners of any hit, when they are eligible nodes
        key_to = {
            r1_key(f, lexicon.cfg): i
            for i in elig
            for f in (nodes[i]["canonical_name"], *nodes[i].get("aliases", []))
        }
        partners = set()
        for i in hits:
            for p in lexicon.different_partners(nodes[i]["canonical_name"]):
                j = key_to.get(r1_key(p, lexicon.cfg))
                if j is not None and j not in hits:
                    partners.add(j)
        cards = (sorted(hits) + [i for i in sem_rank if i not in partners] + sorted(partners))[:cap]
        words = 0
        for i in cards:
            n = nodes[i]
            gloss = " ".join((n.get("definition") or "").split()[:25])
            words += len(
                f"n_{i:04d} | {n['canonical_name']} | aka: {', '.join(n.get('aliases', [])[:3]) or '-'} | {n['node_type']} | def | in_text | {gloss}".split()
            )
        stats.append(
            {
                "section": sec["section_id"],
                "cards": len(cards),
                "string": len(hits),
                "semantic": len(sem_rank),
                "partners": len(partners),
                "tokens": int(words * WORDS_TO_TOKENS),
            }
        )
    # backfill detector: forms of nodes first created in chapter c that occur, unrecorded, in EARLIER sections
    chap = {s["section_id"]: s["chapter_num"] for s in sections}
    fm = _form_map(cp["concepts"])
    recorded = defaultdict(
        set
    )  # raw LLM mentions only: propagation-written mentions are deleted by CR-009
    for sid, ms in cp["mentions_by_section"].items():
        for m in ms:
            if m["source"] == "llm" and (c := fm.get(m["canonical_name"].lower())):
                recorded[sid].add(c["concept_id"])
    full_vocab = {}
    for i, n in enumerate(nodes):
        for f in {
            n["canonical_name"],
            *n.get("aliases", []),
            *lexicon.same_forms(n["canonical_name"]),
        }:
            full_vocab.setdefault(f.lower(), str(i))
    matcher = MentionMatcher(full_vocab)
    occ = {s["section_id"]: {int(m.concept_id) for m in matcher.find(s["text"])} for s in sections}
    calls = set()
    mentions_added = 0
    for i, n in enumerate(nodes):
        origin_sec = sections[n["ext"]]["section_id"]
        for s in sections[: n["ext"]]:
            if i in occ[s["section_id"]] and n["concept_id"] not in recorded[s["section_id"]]:
                calls.add((chap[origin_sec], s["section_id"]))
                mentions_added += 1
    return stats, {"backfill_calls": len(calls), "backfill_candidate_mentions": mentions_added}


# ---------------------------------------------------------------- (d) pruner training data
def pruner_data(gold_rows: list[dict], sections: list[dict], nlp):
    gold_by_sec: dict[str, set[str]] = defaultdict(set)
    for r in gold_rows:
        if r["is_gold"] == "True":
            forms = {r["concept"], *eval(r["aliases"])}
            gold_by_sec[r["section_id"]] |= {_norm(f) for f in forms}
    gold_terms = set().union(*gold_by_sec.values())
    cand_by_sec = {
        s["section_id"]: {_norm(t) for t in extract_candidate_terms(s["text"], nlp)}
        for s in sections
    }
    cand_terms = set().union(*cand_by_sec.values())
    pruned = cand_terms - gold_terms
    conflicts = {
        t
        for t in cand_terms & gold_terms
        if any(t in cand_by_sec[s] and t not in gold_by_sec[s] for s in cand_by_sec)
    }
    per_ch = {}
    for ch in ("1", "2", "3"):
        secs = [s["section_id"] for s in sections if str(s["chapter_num"]) == ch]
        g = set().union(*(gold_by_sec[s] for s in secs)) if secs else set()
        c = set().union(*(cand_by_sec[s] for s in secs)) if secs else set()
        per_ch[ch] = {"growing": len(g), "pruned_candidates": len(c - g)}
    return {
        "growing": len(gold_terms),
        "pruned": len(pruned),
        "candidate_terms": len(cand_terms),
        "conflicts_resolved_as_growing": len(conflicts),
        "per_chapter": per_ch,
    }


# ---------------------------------------------------------------- (e) quantity floor
def density(gold_rows: list[dict], sections: list[dict]):
    per = []
    for s in sections:
        n = len(
            {
                r["concept"]
                for r in gold_rows
                if r["section_id"] == s["section_id"] and r["is_gold"] == "True"
            }
        )
        w = len(s["text"].split())
        per.append((s["section_id"], n, w, 100 * n / w))
    d = [x[3] for x in per]
    return per, {
        "median": statistics.median(d),
        "min": min(d),
        "p25": float(np.percentile(d, 25)),
        "mean": statistics.mean(d),
    }


def partial_vs_gold(e3: dict, gold_rows: list[dict], sections: list[dict], nlp) -> dict:
    """How much of the real partial-span problem (an LLM item that is a strict sub-span of a gold term in
    the same section) each detector sees: M2 on the evidence quote, M2 on the paragraph, and a candidate
    extra rule M5 (a noun chunk that recurs >= 2 times in the chapter, contains the item, is not an item)."""

    def tok(s: str) -> tuple[str, ...]:
        return tuple(re.findall(r"[a-z0-9]+", s.lower()))

    def sub(a, b) -> bool:
        return any(b[i : i + len(a)] == a for i in range(len(b) - len(a) + 1))

    sec_by = {s["section_id"]: s for s in sections}
    chap: dict[str, list[dict]] = defaultdict(list)
    for s_ in sections:
        chap[s_["chapter_num"]].append(s_)
    cc = {ch: chunk_counts([x["text"] for x in ss], nlp) for ch, ss in chap.items()}
    gold_all = {tok(r["concept"]) for r in gold_rows if r["is_gold"] == "True"}
    out = {
        "items": 0,
        "partials": 0,
        "m2_quote": 0,
        "m2_para": 0,
        "m5_flags": 0,
        "m5_valid": 0,
        "m5_partials_recovered": 0,
    }
    for sid, its in e3["final"].items():
        sec = sec_by[sid]
        gs = [
            tok(r["concept"])
            for r in gold_rows
            if r["section_id"] == sid and r["is_gold"] == "True"
        ]
        names = [i["canonical_name"] for i in its]
        textl = " ".join(sec["text"].lower().split())
        for it in its:
            if it.get("source") != "llm":
                continue
            out["items"] += 1
            t = tok(it["canonical_name"])
            is_partial = any(len(x) > len(t) and sub(t, x) for x in gs)
            out["partials"] += is_partial
            q = it.get("evidence_quote") or ""
            para = next(
                (
                    p
                    for p in re.split(r"\n\s*\n", sec["text"])
                    if " ".join(q.split())[:60].lower() in " ".join(p.split()).lower()
                ),
                q,
            )
            if is_partial and find_partial_spans([it["canonical_name"]], q, nlp, all_items=names):
                out["m2_quote"] += 1
            if is_partial and find_partial_spans(
                [it["canonical_name"]], para, nlp, all_items=names
            ):
                out["m2_para"] += 1
            best = None
            for c, n in cc[sec["chapter_num"]].items():
                ct = tok(c)
                if (
                    n >= 2
                    and len(t) < len(ct) <= 4
                    and sub(t, ct)
                    and ct not in {tok(x) for x in names}
                    and c in textl
                ):
                    best = best if best and best[1] >= n else (c, n)
            if best:
                ok = tok(best[0]) in gold_all
                out["m5_flags"] += 1
                out["m5_valid"] += ok
                out["m5_partials_recovered"] += ok and is_partial
    return out


def main() -> None:
    nlp = spacy.load("en_core_web_sm")
    lexicon = Lexicon.load()
    out = [
        "# CR-009 STOP 1 — $0 diagnostics and drafts",
        "",
        "No API calls were made. Branch `cr-009-concept-gvp` (from `main` at `cr-008-complete`).",
        "",
    ]

    # ---- data
    pd_secs = [
        json.loads(x)
        for x in (ROOT / "data/interim/textbook_sections.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if x
    ]
    cp_a = json.loads((KG / "slice3_a1" / "checkpoint.json").read_text())
    cp_b = json.loads((KG / "slice3_b4" / "checkpoint.json").read_text())
    pd_slice = [s for s in pd_secs if s["section_id"] in cp_a["mentions_by_section"]]
    pd_slice.sort(key=lambda s: s["order_index"])
    order = {s["section_id"]: i for i, s in enumerate(pd_slice)}
    iir = [
        json.loads(x)
        for x in (ROOT / "data/interim/external/iir_sections.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if x
    ]
    iir.sort(key=lambda s: int(s["order_index"]))
    gold_rows = list(
        csv.DictReader(
            (ROOT / "data/interim/external/iir_gold_concepts.csv").open(encoding="utf-8")
        )
    )
    e3 = json.loads((ROOT / "data/processed/ablation/abl_20de9701/E3.json").read_text())

    # ---- (a)
    texts_pd = {s["section_id"]: s["text"] for s in pd_slice}
    chap_pd = {s["section_id"]: str(s["chapter_num"]) for s in pd_slice}

    # the cards a generator would see: names of items extracted in EARLIER sections (book order)
    def earlier(items_by: dict[str, list[dict]], ordr: dict[str, int]) -> dict[str, set[str]]:
        return {
            sid: {
                it["canonical_name"]
                for s2, its in items_by.items()
                if ordr[s2] < ordr[sid]
                for it in its
            }
            for sid in items_by
        }

    items_pd = {
        sid: [
            {
                "canonical_name": m["canonical_name"],
                "evidence_quote": m["evidence_quote"],
                "source": m["source"],
            }
            for m in ms
            if m["source"] == "llm"
        ]
        for sid, ms in cp_a["mentions_by_section"].items()
    }
    ra = partial_rate(
        items_pd,
        texts_pd,
        chap_pd,
        earlier(items_pd, order),
        {},
        nlp,
        "P&D ch1-3, CR-007 run (LLM-extracted mentions)",
    )
    texts_iir = {s["section_id"]: s["text"] for s in iir}
    chap_iir = {s["section_id"]: str(s["chapter_num"]) for s in iir}
    order_iir = {s["section_id"]: i for i, s in enumerate(iir)}
    emph_iir = {
        s["section_id"]: set(
            eval(s["emphasized_terms"])
            if isinstance(s["emphasized_terms"], str)
            else s["emphasized_terms"]
        )
        for s in iir
    }
    items_iir_llm = {
        sid: [it for it in its if it.get("source") == "llm"] for sid, its in e3["final"].items()
    }
    rb = partial_rate(
        items_iir_llm,
        texts_iir,
        chap_iir,
        earlier(items_iir_llm, order_iir),
        emph_iir,
        nlp,
        "IIR dev ch1-3, v3 outputs (LLM-extracted items)",
    )
    bank = load_bank()
    bank_problems = validate_bank(bank, nlp)
    out += [
        "## (a) Partial-span baseline (rule M2, $0)",
        "",
        "| set | items | span found in its quote | flagged | rate |",
        "|---|---|---|---|---|",
    ]
    for r in (ra, rb):
        out.append(
            f"| {r['label']} | {r['items']} | {r['with_span_in_quote']} | {r['flagged']} | {r['rate']:.1%} |"
        )
    out += [
        "",
        f"**Bank check:** the 7 bank examples' expected outputs raise **{len(bank_problems)}** flags from any of F2-F6, C3, M1, M2"
        + (
            ": " + "; ".join(f"{p.example} {p.rule} {p.detail}" for p in bank_problems)
            if bank_problems
            else " (required: none)."
        ),
        "",
    ]
    rng = random.Random(SCRATCH_SEED)
    ex = rng.sample(ra["flags"], min(10, len(ra["flags"]))) + rng.sample(
        rb["flags"], min(10, len(rb["flags"]))
    )
    out += ["20 examples (10 per set; `item` → the longer candidate M2 would offer):", ""]
    for f in ex:
        out.append(
            f"- [{f['section']}] “{f['item']}” → “{f['longer']}” ({f['why']}) — …{f['quote'][:140]}…"
        )
    out.append("")

    pvg = partial_vs_gold(e3, gold_rows, iir, nlp)
    out += [
        "### How much of the real partial-span problem the detectors see (IIR dev, measured against gold)",
        "",
        (
            f"{pvg['partials']} of {pvg['items']} LLM items ({pvg['partials'] / pvg['items']:.0%}) are a strict sub-span of a gold term in their section. "
            f"**M2 as specified catches {pvg['m2_quote']} of them** (it only looks inside the evidence quote, and the quote almost never contains the longer gold term); "
            f"M2 on the whole paragraph catches {pvg['m2_para']}. A candidate extra rule **M5** (a noun chunk that recurs >= 2 times in the chapter, contains the item, and is not already an item) "
            f"flags {pvg['m5_flags']} items, of which {pvg['m5_valid']} ({pvg['m5_valid'] / max(pvg['m5_flags'], 1):.0%}) offer a longer chunk that is a gold term, "
            f"recovering {pvg['m5_partials_recovered']} of the {pvg['partials']} gold partials. The complete-span prompt rules and the few-shot bank are therefore the main lever; "
            "M2 stays as a cheap precision-first hint, and M5 is proposed for your decision (it is not in the CR)."
        ),
        "",
    ]

    # ---- (b)
    rows, cnt, pick = propagation_audit(cp_b, order)
    out += [
        "## (b) Propagation audit (CR-007 run `slice3_a1`, E3 adopted)",
        "",
        (
            f"Mentions written by propagation (raw per-section data, `slice3_b4` inherits `slice3_a1`'s mentions): **{len(rows)}** of {sum(len(v) for v in cp_b['mentions_by_section'].values())} raw mentions: "
            f"forward {cnt['forward']}, backward {cnt['backward']}, same section {cnt['same_section']}. "
            "Forward = later than the node's first LLM extraction; backward = earlier."
        ),
        "",
        "20 sampled for you to mark `same sense` / `different sense`: `data/interim/checks/cr009_propagation_audit_sheet.csv` (forward and backward mixed and shuffled when both exist; the key holds which is which).",
        "",
    ]
    CHECKS.mkdir(parents=True, exist_ok=True)
    with (CHECKS / "cr009_propagation_audit_sheet.csv").open(
        "w", newline="", encoding="utf-8"
    ) as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "id",
                "concept",
                "type",
                "what the node means (definition)",
                "section",
                "where it was tagged (quote)",
                "mark (same sense / different sense)",
                "note",
            ]
        )
        for i, r in enumerate(pick, 1):
            w.writerow(
                [
                    i,
                    r["concept"],
                    r["type"],
                    r["definition"] or "",
                    r["section"],
                    r["quote"],
                    "",
                    "",
                ]
            )
    with (CHECKS / "cr009_propagation_audit_key.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "direction"])
        for i, r in enumerate(pick, 1):
            w.writerow([i, r["kind"]])

    # ---- (c)
    from sentence_transformers import SentenceTransformer

    from cumap.config import get_settings

    model = SentenceTransformer(get_settings().embeddings.model)
    stats, bf = retriever_dry_run(cp_b, pd_slice, lexicon, model)
    cards = [s["cards"] for s in stats]
    toks = [s["tokens"] for s in stats]
    out += [
        "## (c) Retriever dry run (P&D ch1-3 in book order, final CR-008 nodes `slice3_b4`, every node treated as growing)",
        "",
        (
            f"Cards per section: median **{statistics.median(cards):.0f}**, max **{max(cards)}** (cap 120); string hits median {statistics.median([s['string'] for s in stats]):.0f}, "
            f"semantic median {statistics.median([s['semantic'] for s in stats]):.0f}, lexicon look-alike partners added in {sum(1 for s in stats if s['partners'])} sections. "
            f"Prompt tokens the cards add: median **{statistics.median(toks):.0f}**, max {max(toks)}."
        ),
        "",
        (
            f"Backfill detector (§3.7): **{bf['backfill_calls']} calls** predicted (one per (chapter end, earlier section) pair) for "
            f"{bf['backfill_candidate_mentions']} unrecorded node occurrences in earlier sections."
        ),
        "",
    ]

    # ---- (d)
    iir_dev = [s for s in iir]
    pd_ = pruner_data(gold_rows, iir_dev, nlp)
    out += [
        "## (d) Pruner training data (IIR dev only, after term-level dedup)",
        "",
        f"- **growing** (gold in any dev section): **{pd_['growing']}** distinct terms",
        f"- **pruned** (candidate noun phrases that are gold in no dev section): **{pd_['pruned']}** distinct terms (of {pd_['candidate_terms']} candidates)",
        f"- conflicts resolved as growing (gold in one section, a non-gold candidate in another): {pd_['conflicts_resolved_as_growing']}",
        f"- per dev chapter (for leave-one-chapter-out): {pd_['per_chapter']}",
        "",
    ]

    # ---- (e)
    per, dstat = density(gold_rows, iir_dev)
    rho = round(0.5 * dstat["median"], 1)
    out += [
        "## (e) Quantity floor ρ (rule Q1: items < max(3, ρ × words / 100))",
        "",
        "Gold concepts per 100 words on the 13 dev sections: "
        + ", ".join(f"{sid} {d:.1f}" for sid, _n, _w, d in per)
        + ".",
        (
            f"Median {dstat['median']:.1f}, lower quartile {dstat['p25']:.1f}, minimum {dstat['min']:.1f}. "
            f"**Proposed ρ = {rho}** (half the median density, so the floor catches only clearly thin outputs). "
            f"Check: with ρ = {rho}, Q1 would fire on gold counts in "
            f"{sum(1 for _s, n, w, _d in per if n < max(3, rho * w / 100))} of 13 sections."
        ),
        "",
    ]
    REPORT.write_text("\n".join(out) + "\n", encoding="utf-8")
    (ROOT / "reports" / "cr009_stop1_numbers.json").write_text(
        json.dumps(
            {
                "rho": rho,
                "cards_median": statistics.median(cards),
                "cards_max": max(cards),
                "card_tokens_median": statistics.median(toks),
                "backfill_calls": bf["backfill_calls"],
                "pd_items": ra["items"],
                "partial_rate_pd": ra["rate"],
                "partial_rate_iir": rb["rate"],
                "pd_sections": len(pd_slice),
                "pd_words": sum(len(s["text"].split()) for s in pd_slice),
                "pruner": pd_,
                "partial_vs_gold": pvg,
            },
            indent=1,
        )
    )
    print("wrote", REPORT)


if __name__ == "__main__":
    main()
