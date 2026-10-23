"""CR-012 isolation evidence ($0): do any benchmark held-out surfaces appear in development artefacts (prompts, few-shot banks, lexicon,
cues, configs)? The SciNLP test gold is read here only to SEARCH for its strings; nothing from it is written anywhere except a count.

    uv run python -m cumap.cr012.isolation
"""

from __future__ import annotations

import hashlib
import json
import re

from cumap.config import REPO_ROOT
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.oracle import leakage_scan
from cumap.cr012.pd_e2e import load_sections, select

OUT = REPO_ROOT / "reports/cr012/isolation_scan.json"
ARTEFACT_GLOBS = ["prompts/**/*.md", "configs/**/*.yaml", "configs/**/*.yml"]


def artefacts() -> dict[str, str]:
    out = {}
    for g in ARTEFACT_GLOBS:
        for p in sorted(REPO_ROOT.glob(g)):
            out[str(p.relative_to(REPO_ROOT))] = p.read_text(encoding="utf-8", errors="ignore")
    return out


def shingles(text: str, n: int = 8) -> set[str]:
    toks = re.findall(r"[a-z0-9]+", text.lower())
    return {" ".join(toks[i : i + n]) for i in range(len(toks) - n + 1)}


def run() -> dict:
    arts = artefacts()
    ad = SciNLPAdapter()
    docs = {d.doc_key: d for d in ad.load_documents("test")}
    surfaces = []
    for key, g in ad.gold("test").items():
        surfaces += [" ".join(docs[key].tokens[m.span[0] : m.span[1]]) for m in g.mentions]
    sci = leakage_scan(arts, surfaces)
    rows = load_sections()
    sel = select(rows)
    held = {s["section_id"] for s in sel["heldout"]}
    held_shingles: set[str] = set()
    for r in rows:
        if r["section_id"] in held:
            held_shingles |= shingles(r["text"])
    pd_hits = {name: len(shingles(t) & held_shingles) for name, t in arts.items()}
    pd_hits = {k: v for k, v in pd_hits.items() if v}
    res = {
        "artefacts_scanned": len(arts),
        "artefacts_sha256": hashlib.sha256(
            json.dumps(
                {k: hashlib.sha256(v.encode()).hexdigest() for k, v in arts.items()}, sort_keys=True
            ).encode()
        ).hexdigest(),
        "scinlp_test_multi_token_surfaces_checked": len(
            {s.lower() for s in surfaces if len(s.split()) >= 2}
        ),
        "scinlp_test_surfaces_found_in_development_artefacts": {
            k: sorted(v)[:20] for k, v in sci.items()
        },
        "pd_heldout_8gram_overlap_with_artefacts": pd_hits,
        "verdict": "CLEAN" if not sci and not pd_hits else "HITS_TO_REVIEW",
    }
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    print(json.dumps(run(), indent=1)[:2500])
