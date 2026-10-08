"""CR-010 STOP 4: the sampled pair-recall study (Research decision 2026-10-05).

Draw 150 random pairs from each of P0, P1-extra and P2-extra (strict cue), have every one judged by a blind human
(`true_relation_exists`, `relation_if_yes`, `direction_if_yes`, `evidence_supported`, `notes`), and estimate how many true
edges each pool holds. The classifier is run on the P1/P2 samples (P0 already has results) but its output is SEALED until
the annotation is frozen: pair recall (a selection property) and classifier accuracy (a conditional property) stay apart.

    uv run python -m cumap.cr010.pair_recall freeze                     # $0: pools, draw, blind sheet, key, manifest
    uv run python -m cumap.cr010.pair_recall classify --dry-run         # estimate only
    uv run python -m cumap.cr010.pair_recall classify --limit 20        # then the full run (cap $4)
    uv run python -m cumap.cr010.pair_recall validate --sheet data/gold/<marked copy>
    uv run python -m cumap.cr010.pair_recall freeze-annotation --sheet data/gold/<marked copy>
    uv run python -m cumap.cr010.pair_recall analyse --sheet data/gold/<marked copy>   # estimates; --reveal after freezing

Pair recall here is measured against the true edges inside the enumerated universe P2 (same sentence, or adjacent
sentences with a strict cue); edges outside that universe (farther apart, no cue, or no co-mention) are not counted.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import subprocess
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import yaml

from cumap.config import REPO_ROOT, get_settings
from cumap.eval.stats import wilson_ci

OUT = REPO_ROOT / "data/interim/pair_recall"
SEED = 20261008
N_PER_POOL = 150
POOLS = ("P0", "P1_extra", "P2_extra_strict")
HARD_CAP_USD = 4.0
RUN_ID = "cr010_pair_recall"
BLIND_COLUMNS = [
    "pair_id",
    "concept_a",
    "concept_b",
    "evidence_section_id",
    "evidence_text",
    "true_relation_exists",
    "relation_if_yes",
    "direction_if_yes",
    "evidence_supported",
    "notes",
]
PREFILLED = BLIND_COLUMNS[:5]
TRUE_VALUES = {"yes", "no", "unclear"}
DIRECTION_VALUES = {"a_to_b", "b_to_a", "symmetric"}
BOOTSTRAP_B = 10_000
BOOTSTRAP_SEED = 20261009


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key_of(a: str, b: str) -> str:
    return "|".join(sorted((a, b)))


# ---------------------------------------------------------------- drawing
def draw(pools: dict) -> list[dict]:
    """Uniform draws without replacement from each pool (sorted keys, one seeded generator per pool). Nothing about
    classifier outcomes or the frozen ranking is read: P0 is drawn from ALL 1,100 selected pairs."""
    cp, universe0, adj = pools["_cp"], pools["_universe0"], pools["_adj"]
    sets = pools["_sets"]
    names = {c["concept_id"]: c["canonical_name"] for c in cp.concepts}
    items: list[dict] = []

    def entry(pool, x, y, section, text, **extra):
        return {
            "pool": pool,
            "concept_x_id": x,
            "concept_y_id": y,
            "name_x": names[x],
            "name_y": names[y],
            "section_id": section,
            "evidence_text": text,
            **extra,
        }

    p0_by_key = {frozenset((p["concept_x_id"], p["concept_y_id"])): p for p in cp.selected_pairs}
    for pool, keys in (
        ("P0", sets["p0"]),
        ("P1_extra", sets["p1_extra"]),
        ("P2_extra_strict", sets["p2_extra"]),
    ):
        ordered = sorted(keys, key=lambda k: tuple(sorted(k)))
        rng = random.Random(f"{SEED}-{pool}")
        for k in rng.sample(ordered, N_PER_POOL):
            x, y = sorted(k)
            if pool == "P0":
                p = p0_by_key[k]
                items.append(
                    entry(
                        pool,
                        p["concept_x_id"],
                        p["concept_y_id"],
                        p["section_id"],
                        p["sentence"],
                        origin="same_sentence" if k in universe0 else "anchor_derived",
                        source_pair_id=p["pair_id"],
                    )
                )
            elif pool == "P1_extra":
                p = universe0[k]
                items.append(
                    entry(
                        pool,
                        p.concept_x_id,
                        p.concept_y_id,
                        p.section_id,
                        p.sentence,
                        origin="same_sentence",
                        source_pair_id=p.pair_id,
                        in_cr007_random_sample=k in sets["sample"],
                    )
                )
            else:
                sp = adj[k]["spans"][0]
                items.append(
                    entry(
                        pool,
                        x,
                        y,
                        sp["section_id"],
                        sp["text"],
                        origin="adjacent_sentences",
                        source_pair_id=None,
                    )
                )
    return items


def blind_rows(items: list[dict], seed: int = SEED) -> tuple[list[dict], list[dict]]:
    """Shuffle all 450 items together, give opaque ids, randomise the A/B order. Returns (sheet rows, key rows)."""
    rng = random.Random(f"{seed}-sheet")
    order = list(range(len(items)))
    rng.shuffle(order)
    sheet, key = [], []
    for n, i in enumerate(order, 1):
        it = items[i]
        flip = rng.random() < 0.5
        a, b = (it["name_y"], it["name_x"]) if flip else (it["name_x"], it["name_y"])
        pid = f"PR{n:03d}"
        sheet.append(
            {
                "pair_id": pid,
                "concept_a": a,
                "concept_b": b,
                "evidence_section_id": it["section_id"],
                "evidence_text": it["evidence_text"],
                **{c: "" for c in BLIND_COLUMNS[5:]},
            }
        )
        key.append({"pair_id": pid, **it, "shown_a": "y" if flip else "x"})
    return sheet, key


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def freeze() -> dict:
    from cumap.cr010.pair_pools import enumerate_pools
    from cumap.cr010.strict_cues import config_hashes

    pools = enumerate_pools("slice3_c2")
    items = draw(pools)
    sheet, key = blind_rows(items)
    assert len({r["pair_id"] for r in sheet}) == 3 * N_PER_POOL
    assert Counter(k["pool"] for k in key) == {p: N_PER_POOL for p in POOLS}
    for k in key:  # sampled pairs must come from the right pool
        assert k["pool"] in POOLS
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "pair_recall_blind_sheet.csv", sheet, BLIND_COLUMNS)
    key_cols = list(dict.fromkeys(c for r in key for c in r))
    write_csv(OUT / "pair_recall_KEY_DO_NOT_SHARE.csv", key, key_cols)
    sizes = {
        "P0": len(pools["_sets"]["p0"]),
        "P1_extra": len(pools["_sets"]["p1_extra"]),
        "P2_extra_strict": len(pools["_sets"]["p2_extra"]),
    }
    manifest = {
        "frozen_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO_ROOT, check=False
        ).stdout.strip(),
        "run": "slice3_c2",
        "seed": SEED,
        "n_per_pool": N_PER_POOL,
        "population_sizes": sizes,
        "nesting": pools["nesting"],
        "pool_key_hashes": {
            "P0": _sha(sorted(map(sorted, pools["_sets"]["p0"]))),
            "P1_extra": _sha(sorted(map(sorted, pools["_sets"]["p1_extra"]))),
            "P2_extra_strict": _sha(sorted(map(sorted, pools["_sets"]["p2_extra"]))),
        },
        "strict_cue_config": config_hashes(),
        "old_p2_extra_size_prep_v0": pools["pools"]["P2_extra_strict_cue_prep_v0 (superseded)"],
        "p0_sample_origin": dict(Counter(k["origin"] for k in key if k["pool"] == "P0")),
        "p1_sample_includes_cr007_random_sample_pairs": sum(
            bool(k.get("in_cr007_random_sample")) for k in key if k["pool"] == "P1_extra"
        ),
        "existing_random_human_labelled_p0_sample": "none suitable (owner marks cover accepted edges only; REL-MAP-180 is "
        "relation-balanced): 150 random P0 pairs drawn",
        "sample_sha256": _sha([{k: v for k, v in r.items()} for r in key]),
        "blind_sheet_sha256": _sha_file(OUT / "pair_recall_blind_sheet.csv"),
        "truth_definition_primary": "true_relation_exists == yes AND evidence_supported == yes",
        "estimator": "per-pool proportion x pool size; 95% percentile cluster bootstrap over evidence sections "
        f"(B={BOOTSTRAP_B}, seed {BOOTSTRAP_SEED}), resampling sections within each pool",
        "classifier_output": "sealed until the annotation is frozen",
    }
    (OUT / "freeze_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


# ---------------------------------------------------------------- sealed classification
def classify(dry_run: bool, limit: int | None, max_usd: float) -> dict:
    """P1-extra and P2-extra samples only (P0 results already exist in the run checkpoint). Resumable; every result is
    appended to the sealed file. Hard stop before the cap."""
    key = read_csv(OUT / "pair_recall_KEY_DO_NOT_SHARE.csv")
    sealed = OUT / "pair_recall_classifier_SEALED.jsonl"
    done = (
        {json.loads(line)["pair_id"] for line in sealed.read_text().splitlines()}
        if sealed.exists()
        else set()
    )
    todo = [k for k in key if k["pool"] != "P0" and k["pair_id"] not in done]
    if limit:
        todo = todo[:limit]
    est = round(
        len(todo) * 0.0083, 3
    )  # measured on slice3_c2: $9.58 / 1,150 strong-tier classifications
    info = {"todo": len(todo), "already_done": len(done), "est_usd": est, "cap_usd": max_usd}
    if dry_run:
        return {"dry_run": True, **info}
    if est > max_usd:
        raise SystemExit(f"estimate ${est} exceeds the cap ${max_usd}")
    from cumap.expert_kg.mentions import MentionMatcher
    from cumap.expert_kg.pipeline import _restore_concept_registry, load_checkpoint
    from cumap.expert_kg.relations import CandidatePair, concept_vocab
    from cumap.expert_kg.relations_v3 import classify_pair_v3
    from cumap.llm.client import BudgetExceededError, LLMClient
    from cumap.llm.prompts import load_prompt
    from cumap.schemas.relations import RelationRegistry

    settings = get_settings()
    settings.llm.stage_budgets_usd["relations"] = max_usd
    client = LLMClient(settings, run_id=RUN_ID)
    registry = RelationRegistry.from_yaml(REPO_ROOT / settings.relation_registry)
    cp = load_checkpoint(REPO_ROOT / "data/processed/kg/slice3_c2")
    concepts = {c.concept_id: c for c in _restore_concept_registry(cp, lambda t: np.zeros(1)).all()}
    matcher = MentionMatcher(concept_vocab(list(concepts.values())))
    fam, rel, qual = (
        load_prompt(REPO_ROOT / "prompts", t, v)  # the prompts of slice3_c2, unchanged
        for t, v in (
            ("relation_family", "v3"),
            ("relation_choice", "v4"),
            ("relation_qualifiers", "v4"),
        )
    )
    stopped = None
    with sealed.open("a", encoding="utf-8") as f:
        for k in todo:
            pair = CandidatePair(
                pair_id=k["pair_id"],
                section_id=k["section_id"],
                concept_x_id=k["concept_x_id"],
                concept_y_id=k["concept_y_id"],
                sentence=k["evidence_text"],
            )
            try:
                res = classify_pair_v3(
                    client,
                    fam,
                    rel,
                    qual,
                    registry,
                    pair,
                    concepts[k["concept_x_id"]],
                    concepts[k["concept_y_id"]],
                    matcher,
                    # the two-sentence P2 span is the evidence: an endpoint may sit in the other sentence
                    grounding_scope="sentence" if k["pool"] == "P2_extra_strict" else "quote",
                    same_concept=True,
                )
            except BudgetExceededError as e:
                stopped = str(e)
                break
            f.write(
                json.dumps({"pair_id": k["pair_id"], "pool": k["pool"], **res.to_dict()}) + "\n"
            )
            f.flush()
    return {**info, "spend_usd": round(client.spent_usd, 4), "stopped_by_budget": stopped}


# ---------------------------------------------------------------- annotation
def allowed_relations() -> set[str]:
    reg = yaml.safe_load((REPO_ROOT / get_settings().relation_registry).read_text())
    return {r["name"] for r in reg["relations"]} | {"other"}


def validate_sheet(rows: list[dict], expected_ids: list[str], relations: set[str]) -> list[str]:
    problems: list[str] = []
    if sorted(r["pair_id"] for r in rows) != sorted(expected_ids):
        problems.append("pair ids differ from the frozen sheet")
    for r in rows:
        i = r["pair_id"]
        t = r.get("true_relation_exists", "").strip()
        rel, d, ev = (
            r.get(c, "").strip()
            for c in ("relation_if_yes", "direction_if_yes", "evidence_supported")
        )
        if t not in TRUE_VALUES:
            problems.append(f"{i}: true_relation_exists must be one of {sorted(TRUE_VALUES)}")
        elif t == "yes":
            if rel not in relations:
                problems.append(
                    f"{i}: relation_if_yes {rel!r} is not a registry relation or 'other'"
                )
            if d not in DIRECTION_VALUES:
                problems.append(f"{i}: direction_if_yes must be one of {sorted(DIRECTION_VALUES)}")
            if ev not in {"yes", "no"}:
                problems.append(f"{i}: evidence_supported must be yes or no when a relation exists")
        elif rel or d or ev not in {"", "na"}:
            problems.append(
                f"{i}: relation/direction/evidence must be empty when no relation exists"
            )
    return problems


def is_true(row: dict, *, unclear_as_yes: bool = False, ignore_evidence: bool = False) -> bool:
    t = row["true_relation_exists"].strip()
    if t == "unclear" and unclear_as_yes:
        t = "yes"
    if t != "yes":
        return False
    return ignore_evidence or row.get("evidence_supported", "").strip() != "no"


# ---------------------------------------------------------------- estimation
def cluster_bootstrap(
    rows: list[dict], sizes: dict[str, int], *, b: int = BOOTSTRAP_B, seed: int = BOOTSTRAP_SEED
) -> dict:
    """rows: {pool, cluster, true}. Point: p_k = true_k / n_k; T_k = N_k p_k. Interval: percentile bootstrap that resamples
    whole evidence sections (clusters) with replacement WITHIN each pool, so pairs from one section are never treated as
    independent. Pair recall of a pool = share of the universe's true edges that lie in P0 / P0+P1x / P0+P1x+P2x."""
    by = {p: defaultdict(lambda: [0, 0]) for p in POOLS}
    for r in rows:
        c = by[r["pool"]][r["cluster"]]
        c[0] += int(r["true"])
        c[1] += 1
    arr = {p: np.array(list(by[p].values()), dtype=float) for p in POOLS}
    point_p = {p: arr[p][:, 0].sum() / arr[p][:, 1].sum() for p in POOLS}
    rng = np.random.default_rng(seed)
    draws = {p: [] for p in POOLS}
    for p in POOLS:
        m = len(arr[p])
        idx = rng.integers(0, m, size=(b, m))
        s, n = arr[p][idx, 0].sum(axis=1), arr[p][idx, 1].sum(axis=1)
        draws[p] = s / n
    T = {p: sizes[p] * point_p[p] for p in POOLS}
    Td = {p: sizes[p] * draws[p] for p in POOLS}

    def ci(x) -> list[float]:
        return [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]

    total, total_d = sum(T.values()), sum(Td.values())
    cum = {"P0": T["P0"], "P1": T["P0"] + T["P1_extra"], "P2": total}
    cum_d = {"P0": Td["P0"], "P1": Td["P0"] + Td["P1_extra"], "P2": total_d}
    return {
        "prevalence": {
            p: {
                "true": int(arr[p][:, 0].sum()),
                "n": int(arr[p][:, 1].sum()),
                "clusters": len(arr[p]),
                "point": float(point_p[p]),
                "ci95_cluster": ci(draws[p]),
                "wilson95_naive": [
                    wilson_ci(int(arr[p][:, 0].sum()), int(arr[p][:, 1].sum())).low,
                    wilson_ci(int(arr[p][:, 0].sum()), int(arr[p][:, 1].sum())).high,
                ],
            }
            for p in POOLS
        },
        "estimated_true_edges": {
            p: {"point": float(T[p]), "ci95_cluster": ci(Td[p]), "pool_size": sizes[p]}
            for p in POOLS
        },
        "estimated_true_edges_in_universe_P2": {"point": float(total), "ci95_cluster": ci(total_d)},
        "pair_recall_within_universe": {
            k: {"point": float(cum[k] / total), "ci95_cluster": ci(cum_d[k] / total_d)}
            for k in ("P0", "P1", "P2")
        },
        "gain_over_P0": {
            "P1_extra_true_edges_per_P0": float(T["P1_extra"] / T["P0"]) if T["P0"] else None,
            "P2_extra_true_edges_per_P0": float(T["P2_extra_strict"] / T["P0"])
            if T["P0"]
            else None,
        },
        "bootstrap": {"B": b, "seed": seed, "resampled_unit": "evidence_section, within pool"},
    }


def pair_recall_study(sheet_rows: list[dict], key_rows: list[dict], sizes: dict[str, int]) -> dict:
    pool_of = {k["pair_id"]: k["pool"] for k in key_rows}
    out = {}
    variants = {
        "primary (yes and evidence supported)": {},
        "sensitivity: ignore evidence_supported": {"ignore_evidence": True},
        "sensitivity: unclear counted as yes": {"unclear_as_yes": True},
    }
    for name, kw in variants.items():
        rows = [
            {
                "pool": pool_of[r["pair_id"]],
                "cluster": r["evidence_section_id"],
                "true": is_true(r, **kw),
            }
            for r in sheet_rows
        ]
        out[name] = cluster_bootstrap(rows, sizes)
    out["label_counts"] = {
        p: dict(
            Counter(
                r["true_relation_exists"].strip() for r in sheet_rows if pool_of[r["pair_id"]] == p
            )
        )
        for p in POOLS
    }
    return out


# ---------------------------------------------------------------- reveal (after the annotation is frozen)
def freeze_annotation(sheet: Path) -> dict:
    rec = {
        "sheet": str(sheet),
        "sha256": _sha_file(sheet),
        "frozen_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    (OUT / "annotation_frozen.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
    return rec


def reveal(sheet: Path, sheet_rows: list[dict], key_rows: list[dict]) -> dict:
    """Conditional classifier accuracy against the frozen human labels. Refuses unless the annotation was frozen."""
    fz = OUT / "annotation_frozen.json"
    if not fz.exists() or json.loads(fz.read_text())["sha256"] != _sha_file(sheet):
        raise SystemExit("annotation not frozen (or changed since): run freeze-annotation first")
    sealed = {
        json.loads(line)["pair_id"]: json.loads(line)
        for line in (OUT / "pair_recall_classifier_SEALED.jsonl").read_text().splitlines()
    }
    cp = json.loads((REPO_ROOT / "data/processed/kg/slice3_c2/checkpoint.json").read_text())
    p0 = {
        key_of(r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]): r
        for r in cp["relation_results_v3"]
        if r.get("group") == "selected"
    }
    key_by = {k["pair_id"]: k for k in key_rows}
    stats = {p: Counter() for p in POOLS}
    rel_agree = Counter()
    for r in sheet_rows:
        k = key_by[r["pair_id"]]
        res = (
            p0[key_of(k["concept_x_id"], k["concept_y_id"])]
            if k["pool"] == "P0"
            else sealed[r["pair_id"]]
        )
        edge = res["outcome"] == "edge" and not res.get("gated_dropped")
        human = is_true(r)
        c = stats[k["pool"]]
        c["tp" if edge and human else "fn" if human else "fp" if edge else "tn"] += 1
        if edge and human and r["relation_if_yes"].strip():
            rel_agree[(k["pool"], "n")] += 1
            rel_agree[(k["pool"], "same_relation")] += (
                res["relation"] == r["relation_if_yes"].strip()
            )
    out = {}
    for p, c in stats.items():
        tp, fn, fp, tn = c["tp"], c["fn"], c["fp"], c["tn"]

        def w(a: int, n: int) -> list[float]:
            x = wilson_ci(a, n)
            return [x.low, x.high]

        out[p] = {
            "tp": tp,
            "fn": fn,
            "fp": fp,
            "tn": tn,
            "classifier_recall_on_human_true": [tp, tp + fn, w(tp, tp + fn)],
            "classifier_precision_vs_human": [tp, tp + fp, w(tp, tp + fp)],
            "relation_agreement_among_tp": [
                rel_agree[(p, "same_relation")],
                rel_agree[(p, "n")],
            ],
        }
    return out


# ---------------------------------------------------------------- guide
def guide_markdown(relations: list[dict]) -> str:
    rel = "\n".join(
        f"- `{r['name']}` — {str(r.get('template', '')).strip()} ({str(r.get('definition', '')).strip()})"
        for r in relations
    )
    return f"""# Pair-recall annotation guide (CR-010 STOP 4, 450 pairs)

You will see 450 concept pairs with the text they were found in. For each pair decide, **from the text shown**, whether
that text states a relation between concept A and concept B. You are not told where a pair came from or what any system
decided. Do not look at model output.

Fill exactly these columns (the first five are pre-filled):

| column | values |
|---|---|
| `true_relation_exists` | `yes` — the shown text states or clearly implies a relation between A and B that a knowledge graph of this textbook should hold; `no` — they merely co-occur, are listed together, or are unrelated; `unclear` — you cannot decide (use rarely, say why in `notes`) |
| `relation_if_yes` | one relation name from the list below, or `other` (say what in `notes`). Leave empty if `no`/`unclear` |
| `direction_if_yes` | `a_to_b` — the relation reads "A *relation* B"; `b_to_a` — reads "B *relation* A"; `symmetric`. Empty if no relation |
| `evidence_supported` | `yes` — the shown text itself supports the relation; `no` — it is true only from your own knowledge or from text not shown. Empty (or `na`) if no relation |
| `notes` | free text, optional |

Rules: judge the relation between **these two concepts**, not between words near them. A list ("TCP, UDP and IP") is not a
relation. A pair whose evidence is two sentences may relate across the sentences. Concepts are judged as named; if a name is
a clearly wrong match for the words in the text, answer `no` and say so in `notes`.

Relations (registry):

{rel}

Save your marked copy to `data/gold/` (the code never writes there) and check it with
`uv run python -m cumap.cr010.pair_recall validate --sheet <your file>`.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "phase", choices=["freeze", "classify", "validate", "freeze-annotation", "analyse"]
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--max-usd", type=float, default=HARD_CAP_USD)
    ap.add_argument("--sheet")
    ap.add_argument("--reveal", action="store_true")
    a = ap.parse_args()
    if a.phase == "freeze":
        m = freeze()
        reg = yaml.safe_load((REPO_ROOT / get_settings().relation_registry).read_text())
        (REPO_ROOT / "docs/cr010/PAIR_RECALL_ANNOTATION_GUIDE.md").write_text(
            guide_markdown(reg["relations"]), encoding="utf-8"
        )
        print(json.dumps(m, indent=1))
        return
    if a.phase == "classify":
        print(json.dumps(classify(a.dry_run, a.limit, min(a.max_usd, HARD_CAP_USD)), indent=1))
        return
    key = read_csv(OUT / "pair_recall_KEY_DO_NOT_SHARE.csv")
    sheet = Path(a.sheet)
    rows = read_csv(sheet)
    if a.phase == "validate":
        problems = validate_sheet(rows, [k["pair_id"] for k in key], allowed_relations())
        print(f"{len(rows)} rows, {len(problems)} problems")
        for p in problems[:50]:
            print(" -", p)
        return
    if a.phase == "freeze-annotation":
        problems = validate_sheet(rows, [k["pair_id"] for k in key], allowed_relations())
        if problems:
            raise SystemExit(f"{len(problems)} problems; not frozen")
        print(json.dumps(freeze_annotation(sheet), indent=1))
        return
    problems = validate_sheet(rows, [k["pair_id"] for k in key], allowed_relations())
    if problems:
        raise SystemExit(f"{len(problems)} annotation problems; run validate")
    sizes = json.loads((OUT / "freeze_manifest.json").read_text())["population_sizes"]
    res = {"estimates": pair_recall_study(rows, key, sizes)}
    if a.reveal:
        res["classifier_conditional"] = reveal(sheet, rows, key)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
