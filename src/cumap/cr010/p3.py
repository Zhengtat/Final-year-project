"""CR-010 P3: pairs suggested by the frozen eRST-compatible discourse graph, and the sampled pair-recall extension.

    P3 = P2 + P3-extra.   P3-extra = concept pairs (x, y) with x mentioned in unit u and y in unit v, u != v, where the
    graph has a DIRECT edge between u and v (satellite-nucleus, or two nuclei of one multinuclear relation), minus every
    pair already in P0, P1 or P2. Mentions are longest-match, as everywhere else. eRST is candidate-pair evidence only:
    the graph never creates a KG edge, and which eRST label linked a pair is never shown to the annotator.

Fixed before the graph was complete: a random 150-pair sample of P3-extra (all pairs if the pool is < 150), every sampled
pair judged blind by a human with the same five fields and the same truth definition as P0-P2, section-clustered
bootstrap, classifier sealed until the annotation is frozen. No full classification.

    uv run python -m cumap.cr010.p3 pool      # $0: size, composition
    uv run python -m cumap.cr010.p3 freeze    # $0: draw, blind sheet, key, manifest
    (classify:  uv run python -m cumap.cr010.pair_recall ... is not used; see `classify` below)
    uv run python -m cumap.cr010.p3 analyse --sheet <marked P3 sheet> [--reveal]
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from cumap.config import REPO_ROOT, load_demo_slice
from cumap.cr010 import pair_recall as PR
from cumap.cr010.pair_pools import enumerate_pools
from cumap.eval.stats import wilson_ci
from cumap.expert_kg import slice_rerun as sr
from cumap.expert_kg.pipeline import _restore_concept_registry
from cumap.expert_kg.relations import sentence_mentions, split_sentences

GRAPH = REPO_ROOT / "data/processed/cr010/erst_graph/graph.json"
POOL = "P3_extra"
POOLS4 = (*PR.POOLS, POOL)
SEED = 20261010
N = 150
RUN_ID = "cr010_p3_recall"
GAP = " [...] "  # shown between two linked sentences that are not adjacent


def linked_pairs(graph: dict, sections, concepts) -> dict[frozenset[str], dict]:
    """Every concept pair in two different, directly eRST-linked units, with the units and the labels that linked it."""
    by_section: dict[str, set[tuple[int, int]]] = defaultdict(set)
    labels: dict[tuple[str, int, int], set[str]] = defaultdict(set)
    from cumap.erst.graph import unit_pairs

    for r in graph["edges"]:
        for a, b in unit_pairs(r["edge"]):
            lo, hi = sorted((a, b))
            if lo != hi:
                by_section[r["section_id"]].add((lo, hi))
                labels[(r["section_id"], lo, hi)].add(r["edge"]["label"])
    out: dict[frozenset[str], dict] = {}
    for s in sections:
        if s.section_id not in by_section:
            continue
        sents = split_sentences(s.text)
        men = sentence_mentions(sents, concepts)
        at: dict[int, set[str]] = defaultdict(set)
        for cid, idxs in men.items():
            for i in idxs:
                at[i].add(cid)
        for lo, hi in sorted(by_section[s.section_id]):
            for x in sorted(at.get(lo, ())):
                for y in sorted(at.get(hi, ())):
                    if x == y:
                        continue
                    k = frozenset((x, y))
                    cur = out.setdefault(k, {"links": []})
                    cur["links"].append(
                        {
                            "section_id": s.section_id,
                            "lo": lo,
                            "hi": hi,
                            "text": sents[lo] + (" " if hi == lo + 1 else GAP) + sents[hi],
                            "labels": sorted(labels[(s.section_id, lo, hi)]),
                        }
                    )
    return out


def build_pool(run: str = "slice3_c2") -> dict:
    graph = json.loads(GRAPH.read_text())
    pools = enumerate_pools(run)
    cfg = load_demo_slice()
    cfg_sections = sr.load_sections(REPO_ROOT / cfg.pd.source_jsonl, list(cfg.pd.chapters))
    cp = pools["_cp"]
    concepts = _restore_concept_registry(cp, lambda t: np.zeros(1)).all()
    linked = linked_pairs(graph, cfg_sections, concepts)
    sets = pools["_sets"]
    earlier = sets["p0"] | sets["p1_extra"] | sets["p2_extra"]
    order = pools["_order"]
    extra = {k: v for k, v in linked.items() if k not in earlier}
    for v in extra.values():
        v["links"].sort(key=lambda link: (order[link["section_id"]], link["lo"], link["hi"]))
    p2 = earlier
    assert not (set(extra) & p2), "P3-extra must exclude P0, P1 and P2"
    return {"extra": extra, "linked_total": len(linked), "pools": pools, "p2": p2}


def composition(extra: dict) -> dict:
    first = [v["links"][0] for v in extra.values()]
    dist = Counter("adjacent" if link["hi"] - link["lo"] == 1 else "farther" for link in first)
    labs = Counter(lab for link in first for lab in link["labels"])
    return {
        "p3_extra": len(extra),
        "first_link_adjacent_vs_farther": dict(dist),
        "pairs_linked_by_label (a pair can have several)": dict(labs.most_common()),
    }


def freeze(run: str = "slice3_c2") -> dict:
    bp = build_pool(run)
    extra = bp["extra"]
    names = {c["concept_id"]: c["canonical_name"] for c in bp["pools"]["_cp"].concepts}
    keys = sorted(extra, key=lambda k: tuple(sorted(k)))
    rng = random.Random(f"{SEED}-{POOL}")
    pick = keys if len(keys) <= N else rng.sample(keys, N)
    items = []
    for k in pick:
        x, y = sorted(k)
        link = extra[k]["links"][0]
        items.append(
            {
                "pool": POOL,
                "concept_x_id": x,
                "concept_y_id": y,
                "name_x": names[x],
                "name_y": names[y],
                "section_id": link["section_id"],
                "evidence_text": link["text"],
                "origin": "erst_linked_adjacent"
                if link["hi"] - link["lo"] == 1
                else "erst_linked_farther",
                "erst_labels": "|".join(link["labels"]),
                "n_links": len(extra[k]["links"]),
            }
        )
    sheet, key = PR.blind_rows(items, seed=SEED)
    for r in sheet:  # ids PQ001.. so the sheets never collide
        r["pair_id"] = "PQ" + r["pair_id"][2:]
    for r in key:
        r["pair_id"] = "PQ" + r["pair_id"][2:]
    PR.write_csv(PR.OUT / "p3_blind_sheet.csv", sheet, PR.BLIND_COLUMNS)
    PR.write_csv(
        PR.OUT / "p3_KEY_DO_NOT_SHARE.csv", key, list(dict.fromkeys(c for r in key for c in r))
    )
    graph_sha = json.loads((GRAPH.parent / "manifest.json").read_text())["graph_sha256"]
    manifest = {
        "frozen_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "seed": SEED,
        "n_requested": N,
        "n_drawn": len(pick),
        "p3_extra_size": len(extra),
        "p2_pool_size": len(bp["p2"]) + 0,
        "eRST_linked_concept_pairs_total": bp["linked_total"],
        "composition": composition(extra),
        "graph_sha256": graph_sha,
        "pool_key_hash": PR._sha(sorted(map(sorted, extra))),
        "sample_sha256": PR._sha(key),
        "blind_sheet_sha256": PR._sha_file(PR.OUT / "p3_blind_sheet.csv"),
        "all_pairs_evaluated": len(extra) <= N,
        "labels_hidden_from_annotator": "eRST labels and links are in the key only",
    }
    (PR.OUT / "p3_freeze_manifest.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8"
    )
    return manifest


# ---------------------------------------------------------------- analysis over all four pools
def nested_bootstrap(
    rows: list[dict],
    sizes: dict[str, int],
    *,
    b: int = PR.BOOTSTRAP_B,
    seed: int = PR.BOOTSTRAP_SEED,
) -> dict:
    """Same estimator as `pair_recall.cluster_bootstrap`, over P0, P1-extra, P2-extra and P3-extra; recall of each cumulative
    pool = share of the P3 universe's true edges it contains."""
    by = {p: defaultdict(lambda: [0, 0]) for p in POOLS4}
    for r in rows:
        c = by[r["pool"]][r["cluster"]]
        c[0] += int(r["true"])
        c[1] += 1
    arr = {p: np.array(list(by[p].values()), dtype=float) for p in POOLS4}
    point = {p: arr[p][:, 0].sum() / arr[p][:, 1].sum() for p in POOLS4}
    rng = np.random.default_rng(seed)
    draws = {}
    for p in POOLS4:
        m = len(arr[p])
        idx = rng.integers(0, m, size=(b, m))
        draws[p] = arr[p][idx, 0].sum(axis=1) / arr[p][idx, 1].sum(axis=1)
    T = {p: sizes[p] * point[p] for p in POOLS4}
    Td = {p: sizes[p] * draws[p] for p in POOLS4}
    ci = lambda x: [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]
    total, total_d = sum(T.values()), sum(Td.values())
    names = ("P0", "P1", "P2", "P3")
    cum, cum_d = 0.0, 0.0
    recall = {}
    for name, p in zip(names, POOLS4, strict=True):
        cum, cum_d = cum + T[p], cum_d + Td[p]
        recall[name] = {"point": float(cum / total), "ci95_cluster": ci(cum_d / total_d)}
    return {
        "prevalence": {
            p: {
                "true": int(arr[p][:, 0].sum()),
                "n": int(arr[p][:, 1].sum()),
                "clusters": len(arr[p]),
                "point": float(point[p]),
                "ci95_cluster": ci(draws[p]),
                "wilson95_naive": [
                    wilson_ci(int(arr[p][:, 0].sum()), int(arr[p][:, 1].sum())).low,
                    wilson_ci(int(arr[p][:, 0].sum()), int(arr[p][:, 1].sum())).high,
                ],
            }
            for p in POOLS4
        },
        "estimated_true_edges": {
            p: {"point": float(T[p]), "ci95_cluster": ci(Td[p]), "pool_size": sizes[p]}
            for p in POOLS4
        },
        "estimated_true_edges_in_universe_P3": {"point": float(total), "ci95_cluster": ci(total_d)},
        "pair_recall_within_universe": recall,
        "bootstrap": {"B": b, "seed": seed, "resampled_unit": "evidence_section, within pool"},
    }


def analyse(p3_sheet: Path, old_sheet: Path, reveal: bool) -> dict:
    sizes = {**json.loads((PR.OUT / "freeze_manifest.json").read_text())["population_sizes"]}
    fm3 = json.loads((PR.OUT / "p3_freeze_manifest.json").read_text())
    sizes[POOL] = fm3["p3_extra_size"]
    key3 = PR.read_csv(PR.OUT / "p3_KEY_DO_NOT_SHARE.csv")
    key_old = PR.read_csv(PR.OUT / "pair_recall_KEY_DO_NOT_SHARE.csv")
    rows3, rows_old = PR.read_csv(p3_sheet), PR.read_csv(old_sheet)
    problems = PR.validate_sheet(rows3, [k["pair_id"] for k in key3], PR.allowed_relations())
    if problems:
        raise SystemExit(f"{len(problems)} annotation problems; validate first")
    pool_of = {k["pair_id"]: k["pool"] for k in [*key_old, *key3]}
    rows = [
        {"pool": pool_of[r["pair_id"]], "cluster": r["evidence_section_id"], "true": PR.is_true(r)}
        for r in [*rows_old, *rows3]
    ]
    res = {
        "estimates": nested_bootstrap(rows, sizes),
        "label_counts_p3": dict(Counter(r["true_relation_exists"].strip() for r in rows3)),
    }
    if reveal:
        res["classifier_conditional_p3"] = reveal_p3(p3_sheet, rows3, key3)
    return res


def reveal_p3(sheet: Path, rows: list[dict], key: list[dict]) -> dict:
    fz = PR.OUT / "p3_annotation_frozen.json"
    if not fz.exists() or json.loads(fz.read_text())["sha256"] != PR._sha_file(sheet):
        raise SystemExit("P3 annotation not frozen (or changed since): run freeze-annotation first")
    sealed = {
        json.loads(x)["pair_id"]: json.loads(x)
        for x in (PR.OUT / "p3_classifier_SEALED.jsonl").read_text().splitlines()
    }
    c = Counter()
    for r in rows:
        res = sealed[r["pair_id"]]
        edge = res["outcome"] == "edge"
        human = PR.is_true(r)
        c["tp" if edge and human else "fn" if human else "fp" if edge else "tn"] += 1
    tp, fn, fp = c["tp"], c["fn"], c["fp"]
    return {
        **c,
        "classifier_recall_on_human_true": [tp, tp + fn],
        "classifier_precision_vs_human": [tp, tp + fp],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "phase", choices=["pool", "freeze", "classify", "validate", "freeze-annotation", "analyse"]
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--max-usd", type=float, default=4.0)
    ap.add_argument("--sheet")
    ap.add_argument("--old-sheet")
    ap.add_argument("--reveal", action="store_true")
    a = ap.parse_args()
    if a.phase == "pool":
        bp = build_pool()
        print(
            json.dumps({"linked_total": bp["linked_total"], **composition(bp["extra"])}, indent=1)
        )
    elif a.phase == "freeze":
        print(json.dumps(freeze(), indent=1))
    elif a.phase == "classify":
        print(
            json.dumps(
                PR.classify(
                    a.dry_run,
                    a.limit,
                    a.max_usd,
                    key_file="p3_KEY_DO_NOT_SHARE.csv",
                    sealed_file="p3_classifier_SEALED.jsonl",
                    run_id=RUN_ID,
                ),
                indent=1,
            )
        )
    else:
        key = PR.read_csv(PR.OUT / "p3_KEY_DO_NOT_SHARE.csv")
        sheet = Path(a.sheet)
        if a.phase == "validate":
            pr = PR.validate_sheet(
                PR.read_csv(sheet), [k["pair_id"] for k in key], PR.allowed_relations()
            )
            print(f"{len(PR.read_csv(sheet))} rows, {len(pr)} problems")
            for p in pr[:30]:
                print(" -", p)
        elif a.phase == "freeze-annotation":
            if PR.validate_sheet(
                PR.read_csv(sheet), [k["pair_id"] for k in key], PR.allowed_relations()
            ):
                raise SystemExit("problems; not frozen")
            rec = {
                "sheet": str(sheet),
                "sha256": PR._sha_file(sheet),
                "frozen_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            }
            (PR.OUT / "p3_annotation_frozen.json").write_text(
                json.dumps(rec, indent=1), encoding="utf-8"
            )
            print(json.dumps(rec, indent=1))
        else:
            print(json.dumps(analyse(sheet, Path(a.old_sheet), a.reveal), indent=1))


if __name__ == "__main__":
    main()
