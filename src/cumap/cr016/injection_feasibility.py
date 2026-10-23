"""CR-016 STOP 2: is injecting memory-retrieved prior nodes into canonicalisation's candidate set possible WITHOUT changing the frozen decision semantics, and could it matter?

Mechanics are read from `expert_kg/canonicalize.py::_canonicalize`: candidates = embedding top-k over the registry; a gate sends a mention straight to 'new concept' with no LLM call unless the best candidate's
similarity >= DEFAULT_SIMILARITY_THRESHOLD (0.6); an LLM 'same' whose matched similarity is below the review band (0.70) is NOT merged but routed to review. This script measures, on the exposed benchmark cases,
how often the prior concept is already in the embedding top-5, and how often its name similarity clears the gate (0.6) and the merge band (0.7); a registry proxy = canonical names of all gold concepts first seen earlier.
$0, local (the project's MiniLM embedder)."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from cumap.cr016.benchmark import load_gold, norm

ROOT = Path(".")
THR, BAND, K = 0.6, 0.7, 5


def main() -> dict:
    from cumap.concepts_v4 import experiments as X
    from cumap.config import get_settings

    emb = X.Embedder(get_settings().embeddings.model)
    gold = load_gold()
    secs = [
        json.loads(line)["section_id"]
        for line in (ROOT / "data/interim/textbook_sections.jsonl").read_text().splitlines()
    ]
    order = {s: i for i, s in enumerate(secs)}
    first: dict[str, int] = {}
    canon: dict[str, str] = {}
    for g in gold:
        o = order[g["section"]]
        if g["key"] not in first or o < first[g["key"]]:
            first[g["key"]] = o
        canon.setdefault(g["key"], norm(g["canonical"]))
    keys = sorted(first)
    vec = {k: emb(canon[k]) for k in keys}
    mat = np.stack([vec[k] / (np.linalg.norm(vec[k]) + 1e-9) for k in keys])
    cases = [
        json.loads(x)
        for x in (ROOT / "data/processed/cr016/stage2/key.jsonl").read_text().splitlines()
    ]
    acc: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for c in cases:
        k = c["key"]
        if first.get(k, 10**9) >= c["source_order"]:
            continue  # the concept is not in the registry yet (first seen in this section)
        if norm(c["surface"]) == canon[k]:
            continue  # same name as the registered concept: the exact-string rule merges it with no LLM call
        q = emb(norm(c["surface"]))
        q = q / (np.linalg.norm(q) + 1e-9)
        avail = np.array([first[x] < c["source_order"] for x in keys])
        sims = np.where(avail, mat @ q, -1.0)
        target = keys.index(k)
        rank = int((sims > sims[target]).sum()) + 1
        row = {
            "top5": rank <= K,
            "gate_ge_0.6": sims[target] >= THR,
            "band_ge_0.7": sims[target] >= BAND,
            "outside_top5_but_ge_0.7": rank > K and sims[target] >= BAND,
            "sim": float(sims[target]),
        }
        for name in [
            "all",
            *[
                f
                for f, v in c["flags"].items()
                if v
                and f
                in (
                    "alias",
                    "acronym",
                    "different_boundary",
                    "associative_low_lexical_overlap",
                    "one_token",
                )
            ],
        ]:
            for m, v in row.items():
                acc[name][m].append(v)
    out = {}
    for name, d in acc.items():
        n = len(d["top5"])
        out[name] = {
            "n": n,
            **{m: (float(np.mean(v)) if m == "sim" else int(sum(v))) for m, v in d.items()},
        }
        for m in ("top5", "gate_ge_0.6", "band_ge_0.7", "outside_top5_but_ge_0.7"):
            out[name][m + "_rate"] = out[name][m] / n if n else None
    Path("reports/cr016/injection_feasibility.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
