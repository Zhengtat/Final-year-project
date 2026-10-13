"""CR-016 STOP 1: causal source-order manifest of the parsed Peterson & Davie text (book order, sections, textbook paragraphs, hashes) and index-size estimates. $0, local."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(".")
OUT = ROOT / "reports/cr016/source_order_manifest.json"


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def build() -> dict:
    secs = [
        json.loads(line)
        for line in (ROOT / "data/interim/textbook_sections.jsonl").read_text().splitlines()
    ]
    rows, order = [], 0
    for r in secs:
        ps = paragraphs(r["text"])
        rows.append(
            {
                "source_order": order, "section_id": r["section_id"], "chapter": r["chapter_num"], "words": r["word_count"], "paragraphs": len(ps),
                "paragraph_words": [len(p.split()) for p in ps], "source_hash": hashlib.sha256(r["text"].encode()).hexdigest()[:16],
            }
        )  # fmt: skip
        order += 1
    total_words = sum(x["words"] for x in rows)
    all_p = [w for x in rows for w in x["paragraph_words"]]
    for x in rows:
        del x["paragraph_words"]
    man = {
        "sections": rows,
        "n_sections": len(rows),
        "total_words": total_words,
        "total_paragraphs": len(all_p),
        "paragraph_words_mean": sum(all_p) / len(all_p),
        "paragraphs_over_300_words": sum(w > 300 for w in all_p),
    }
    man["manifest_sha256"] = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    return man


if __name__ == "__main__":
    m = build()
    OUT.write_text(json.dumps(m, indent=1))
    print({k: v for k, v in m.items() if k != "sections"})
    print([(x["source_order"], x["section_id"]) for x in m["sections"]][:70])
