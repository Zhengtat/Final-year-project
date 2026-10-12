"""CR-014 STOP 1 ($0): text-only dry-run candidate counts and cost projections for the candidate fresh P&D sections. No gold, no LLM call, no prediction."""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

import spacy

from cumap.concepts_v4.verifier import _nl
from cumap.cr010.candidates import _count, _gather
from cumap.expert_kg.alias_rules import AliasConfig

HELD_OUT_CR012 = {"4.4", "4.5", "5.4", "6.3", "7.1", "8.2", "9.3"}
PILOT_CR012 = {"1.5", "2.6"}
SECTION_RE = re.compile(r"^\d+\.\d+$")
# measured rates (docs/PROGRESS.md): concepts ~$0.0033 / 1k words per generator pass; canonicalisation ~$0.0165 / 1k words
GEN_PER_1K = 0.0033
CANON_PER_1K = 0.0165
OUT = Path("reports/cr014")


def main() -> None:
    nlp = spacy.load("en_core_web_sm")
    cfg = AliasConfig.load()
    secs = [json.loads(line) for line in open("data/interim/textbook_sections.jsonl")]
    rows = []
    for s in secs:
        sid = s["section_id"]
        if not SECTION_RE.match(sid) or (s["chapter_num"] or 0) < 4:
            continue
        text = s["text"]
        heading = " > ".join(s.get("heading_path") or [])
        emph = set(s.get("emphasized_terms") or [])
        found = _gather(text, heading, emph, nlp, cfg, 3)
        text_l = _nl(text)
        by_src: dict[str, int] = {}
        kept = 0
        one = 0
        for term, srcs in found.items():
            n_tok = len(term.split())
            if n_tok > 4:
                continue
            count, _ = _count(term, text_l)
            if count == 0:
                continue
            for src in srcs:
                by_src[src] = by_src.get(src, 0) + 1
            kept += 1
            one += n_tok == 1
        wc = s["word_count"]
        rows.append(
            {
                "section_id": sid,
                "chapter": s["chapter_num"],
                "words": wc,
                "emphasized": len(emph),
                "cand_total": kept,
                "cand_one_token": one,
                "cand_per_1k_words": round(1000 * kept / wc, 1),
                "by_source": by_src,
                "cr012_heldout": sid in HELD_OUT_CR012,
                "cr012_pilot": sid in PILOT_CR012,
            }
        )
    fresh = [r for r in rows if not r["cr012_heldout"]]
    words = [r["words"] for r in fresh]
    summary = {
        "n_sections_ch4_9": len(rows),
        "n_candidate_fresh": len(fresh),
        "words_fresh_total": sum(words),
        "words_median": statistics.median(words),
        "gen_pass_usd_per_section_median": round(statistics.median(words) / 1000 * GEN_PER_1K, 4),
        "canon_usd_per_section_median": round(statistics.median(words) / 1000 * CANON_PER_1K, 4),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "dry_run_candidates.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=1)
    )
    print(json.dumps(summary, indent=1))
    for r in rows:
        print(
            r["section_id"],
            r["words"],
            r["emphasized"],
            r["cand_total"],
            r["cand_per_1k_words"],
            "HELD" if r["cr012_heldout"] else "",
        )


if __name__ == "__main__":
    main()
