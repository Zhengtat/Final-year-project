"""CR-064 ($0): why Pair Recall is below 1 on SciNLP, on the CR-058 development sources (v5: `cr055ballp` 20 papers, `cr057rest` 37 papers),
strict `IDXR1-P1`, matching `r1key` (the mode the runs recorded). No model call.

Pair Recall = gold relations whose two endpoints are present (attribution code not N0 / N1) whose pair reached the classifier. Every candidate
pair the run built was classified (no budget saturation), so a gold relation that does not reach it is one the candidate builder never produced.
Each such relation (code P0) falls in exactly one cause:
1. `splitter_abbreviation`: the run's sentence splitter (`split_sentences`, a cut after every . ! ?) cuts inside the SciNLP sentence, after
   "et al.", "e.g.", "i.e.", "vs." (also written "et al ."); the abbreviation-aware splitter (`split_sentences_abbrev`, CR-064 A2) keeps it whole.
2. `splitter_other`: cut inside the SciNLP sentence that the abbreviation-aware splitter does not undo.
3. `same_concept`: both gold mentions resolve to one concept in the built graph, so there is no pair of two concepts to classify.
4. `distinct_concepts_not_built`: two different concepts, both in the same pipeline sentence or not matched there, and no candidate in the
   checkpoint (the final concept list is not the registry the pairs were built from: 119 of 4,977 pairs differ in a rebuild).
5. `no_owner`: an endpoint is a predicted mention that no concept owns at that position.

    CUMAP_MATCHING=r1key uv run python -m cumap.cr064.pair_loss"""

from __future__ import annotations

import json
from collections import Counter

from cumap.config import REPO_ROOT
from cumap.cr012 import production_graph as PG
from cumap.cr012 import scinlp_run as SR
from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr012.stop4_score import sc_attribution
from cumap.cr019 import variants as V
from cumap.cr043.papers import paper_set
from cumap.cr043.run import run_id
from cumap.expert_kg import relations as R

OUT = REPO_ROOT / "reports/cr064"
SOURCES = (("first", "cr055ballp"), ("rest", "cr057rest"))
VARIANT = "IDXR1-P1"
CAUSES = {
    "splitter_abbreviation": "the sentence splitter cuts the sentence after an abbreviation (et al., e.g., i.e., vs.); the abbreviation-aware splitter joins it",
    "splitter_other": "the sentence splitter cuts inside the sentence; not an abbreviation",
    "same_concept": "both gold mentions are the same concept in the built graph (no pair of two concepts exists)",
    "distinct_concepts_not_built": "two different concepts, no candidate built (concept list changed after pair building)",
    "no_owner": "an endpoint is a predicted mention that no concept owns at that position",
}


def sentence_offsets(text: str, sentences: list[str]) -> list[tuple[int, int]]:
    out, pos = [], 0
    for s in sentences:
        i = text.find(s, pos)
        out.append((i, i + len(s)))
        pos = i + len(s)
    return out


def sentence_index(offsets: list[tuple[int, int]], ch: int) -> int | None:
    return next((i for i, (a, b) in enumerate(offsets) if a <= ch < b), None)


def cause(text: str, a: int, b: int, owners_a: set, owners_b: set) -> str:
    """Cause of one P0 relation from the character starts of its two gold mentions and the concepts owning them."""
    plain = sentence_offsets(text, R.split_sentences(text))
    if sentence_index(plain, a) != sentence_index(plain, b):
        abbrev = sentence_offsets(text, R.split_sentences_abbrev(text))
        return (
            "splitter_abbreviation"
            if sentence_index(abbrev, a) == sentence_index(abbrev, b)
            else "splitter_other"
        )
    if not owners_a or not owners_b:
        return "no_owner"
    if owners_a == owners_b and len(owners_a) == 1:
        return "same_concept"
    return "distinct_concepts_not_built"


def collect() -> dict:
    ad = SciNLPAdapter()
    sym = ad.symmetric_relations()
    causes: Counter = Counter()
    n: Counter = Counter()
    for st, tag in SOURCES:
        papers = paper_set(st)
        golds = {s: ad.gold(s) for s in {s for s, _ in papers}}
        docs = {
            s: {d.doc_key: d for d in ad.load_documents(s, paragraph_every=SR.PARAGRAPH_EVERY)}
            for s in golds
        }
        for s, d in papers:
            cp = json.loads((PG.run_path(run_id(d, tag)) / "checkpoint.json").read_text())
            doc, g = docs[s][d], golds[s][d]
            pred = V.sc_score(doc, g, cp, sym, VARIANT)["pred"]
            owner: dict = {}
            for node in pred["nodes"]:
                for sp in node.mentions:
                    owner.setdefault(sp, set()).add(node.node_id)
            stats = cp.get("selection_stats") or {}
            n["papers"] += 1
            n["budget_saturated_papers"] += len(cp["selected_pairs"]) < (
                stats.get("unique_candidate_pairs") or 0
            )
            n["candidate_pairs"] += stats.get("unique_candidate_pairs") or 0
            n["classified_pairs"] += len(cp["selected_pairs"])
            for rel, code in zip(g.relations, sc_attribution(doc, g, pred, cp, sym), strict=True):
                if code in ("N0", "N1"):
                    continue
                n["endpoints_present"] += 1
                if code != "P0":
                    continue
                a, b = doc.span_to_chars(rel.src_span)[0], doc.span_to_chars(rel.tgt_span)[0]
                causes[
                    cause(
                        doc.text,
                        a,
                        b,
                        owner.get(rel.src_span, set()),
                        owner.get(rel.tgt_span, set()),
                    )
                ] += 1
    lost = sum(causes.values())
    return {
        "sources": dict(SOURCES),
        "variant": VARIANT,
        **n,
        "reached": n["endpoints_present"] - lost,
        "lost": lost,
        "causes": dict(causes),
    }


def markdown(r: dict) -> str:
    e, lost = r["endpoints_present"], r["lost"]
    elig = e - r["causes"].get("same_concept", 0)
    rows = [
        f"| {k} | {r['causes'].get(k, 0)} | {r['causes'].get(k, 0) / lost:.0%} | {CAUSES[k]} |"
        for k in CAUSES
    ]
    return "\n".join(
        [
            "# CR-064 Pair Recall: where the missing pairs are lost",
            "",
            (
                f"Sources: {', '.join(f'`{t}` ({s})' for s, t in r['sources'].items())}; {r['papers']} papers; `{r['variant']}`, matching `r1key`; no model call. "
                "Generated by `CUMAP_MATCHING=r1key uv run python -m cumap.cr064.pair_loss`."
            ),
            "",
            (
                f"- Candidate pairs built: {r['candidate_pairs']}; classified: {r['classified_pairs']}; papers where the budget cut candidates: {r['budget_saturated_papers']}. "
                "Every pair the run built was classified."
            ),
            f"- Pair Recall (Table 4 definition): {r['reached']} / {e} = **{r['reached'] / e:.3f}** pooled; {lost} gold relations did not reach the classifier.",
            f"- Without the `same_concept` relations (no pair exists): {r['reached']} / {elig} = **{r['reached'] / elig:.3f}**.",
            "",
            "| cause | n | share | meaning |",
            "|---|---|---|---|",
            *rows,
            "",
        ]
    )


def main() -> None:
    r = collect()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pair_loss.json").write_text(json.dumps(r, indent=1), encoding="utf-8")
    (OUT / "pair_loss.md").write_text(markdown(r), encoding="utf-8")
    print(markdown(r))


if __name__ == "__main__":
    main()
