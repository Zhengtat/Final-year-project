"""CR-010 STOP 4: the REL-MAP-180 mapping benchmark, built from a finished relation run ($0, no model).

180 items = 120 accepted current concept edges + 30 current NO_RELATION hard negatives + 30 OTHER / near-miss pairs,
grouped by evidence section BEFORE the 60 development / 120 held-out split. The blind sheet shows only the evidence
sentence and the two concepts (in a random order); the manifest holds every model-side field and is never shared with
an annotator. The NOT-GOLD current->eRST mapping table is never read here.

    uv run python -m cumap.cr010.relmap build --run slice3_c2
    uv run python -m cumap.cr010.relmap validate --sheet data/gold/cr010_relmap180_blind_sheet_annotator1.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from cumap.config import REPO_ROOT

CHECKS = REPO_ROOT / "data" / "interim" / "checks"
KG = REPO_ROOT / "data" / "processed" / "kg"
BLIND_COLUMNS = [
    "item_id",
    "evidence_section_id",
    "evidence_text",
    "concept_a",
    "concept_b",
    "annotator_id",
    "current_semantic_relation_judgement",
    "erst_applies_yes_no",
    "erst_relation_1",
    "erst_relation_2_optional",
    "direction_judgement",
    "nuclearity_judgement_if_relevant",
    "machine_useful_meaning_survives_yes_no",
    "loss_taxonomy",
    "loss_part_whole_composition",
    "loss_mechanism",
    "loss_network_topology",
    "loss_identifier_semantics",
    "loss_encapsulation_payload_semantics",
    "loss_causal_sign_direction",
    "loss_technical_dependency",
    "loss_tradeoff_semantics",
    "loss_pedagogical_prerequisite",
    "loss_principle_instance_organisation",
    "other_loss_notes",
    "annotator_notes",
]
LOSS_COLUMNS = [c for c in BLIND_COLUMNS if c.startswith("loss_")]
# (development, held-out test) counts per pool kind; stratum totals 120 / 30 / 30, split 60 / 120
KINDS = {
    "edge": (40, 80),
    "no_relation": (10, 20),
    "other": (8, 16),
    "near_miss": (2, 4),  # a relation was proposed but broke the registry's domain/range rule
}
STRATUM = {
    "edge": "ACCEPTED_EDGE",
    "no_relation": "NO_RELATION",
    "other": "OTHER_NEAR_MISS",
    "near_miss": "OTHER_NEAR_MISS",
}
DIRECTION_VALUES = {"a_to_b", "b_to_a", "symmetric", "not_applicable"}
NUCLEARITY_VALUES = {"nucleus_a", "nucleus_b", "both_nuclei", "either", "not_applicable"}
YES_NO = {"yes", "no"}


# ---------------------------------------------------------------- pools
def pools_from_checkpoint(cp: dict) -> dict[str, list[dict]]:
    """Selected results only (the 50 unselected-sample pairs are a different instrument). Accepted edges are the primary
    expert edges (never consolidated duplicates, gated ones or misconception-layer items)."""
    from cumap.expert_kg.misconception import expert_edges

    rr = cp["relation_results_v3"]
    sel = [r for r in rr if r.get("group", "selected") == "selected"]
    return {
        "edge": sorted(expert_edges(rr).values(), key=lambda r: r["pair"]["pair_id"]),
        "no_relation": sorted(
            (r for r in sel if r["outcome"] == "no_relation"), key=lambda r: r["pair"]["pair_id"]
        ),
        "other": sorted(
            (r for r in sel if r["outcome"] == "other"), key=lambda r: r["pair"]["pair_id"]
        ),
        "near_miss": sorted(
            (r for r in sel if r["outcome"] == "rejected" and r.get("reason") == "domain_range"),
            key=lambda r: r["pair"]["pair_id"],
        ),
    }


def _capacity(pools: dict[str, list[dict]]) -> dict[str, Counter]:
    cap: dict[str, Counter] = defaultdict(Counter)
    for kind, items in pools.items():
        for r in items:
            cap[r["pair"]["section_id"]][kind] += 1
    return cap


def assign_sections(
    pools: dict[str, list[dict]], seed: int, margin_dev: float = 1.5, margin_test: float = 1.2
) -> tuple[set[str], set[str], int]:
    """Whole evidence sections go to one side. Shuffle sections with the seed; fill development until it holds about a third of the sections AND
    `margin_dev` x the items it needs in every pool kind, while the rest still holds `margin_test` x what the test needs.
    Returns (dev sections, test sections, seed used); later seeds are tried when a draw is infeasible."""
    cap = _capacity(pools)
    sections = sorted(cap)
    for attempt in range(200):
        rng = random.Random(seed + attempt)
        order = sections[:]
        rng.shuffle(order)
        dev: set[str] = set()
        have: Counter = Counter()
        target = round(len(sections) / 3)  # development gets about a third of the evidence sections
        for s in order:
            if len(dev) >= target and all(have[k] >= margin_dev * KINDS[k][0] for k in KINDS):
                break
            dev.add(s)
            have.update(cap[s])
        test = set(sections) - dev
        test_have = Counter()
        for s in test:
            test_have.update(cap[s])
        if all(have[k] >= KINDS[k][0] for k in KINDS) and all(
            test_have[k] >= margin_test * KINDS[k][1] for k in KINDS
        ):
            return dev, test, seed + attempt
    raise RuntimeError("no feasible section split for the pool sizes")


def pick(items: list[dict], n: int, rng: random.Random, group_of, sections: set[str]) -> list[dict]:
    """Round-robin over groups (rarest first) so every group is represented; a per-section cap spreads the evidence."""
    pool = [r for r in items if r["pair"]["section_id"] in sections]
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in pool:
        groups[group_of(r)].append(r)
    for g in groups.values():
        rng.shuffle(g)
    cap = max(2, math.ceil(1.5 * n / max(len(sections), 1)))
    used: Counter = Counter()
    picked: list[dict] = []
    for pass_cap in (cap, 10**6):  # second pass relaxes the cap if the first cannot fill
        progress = True
        while len(picked) < n and progress:
            progress = False
            for g in sorted(groups, key=lambda k: (len(groups[k]), k)):
                if len(picked) >= n:
                    break
                while groups[g]:
                    r = groups[g].pop()
                    sid = r["pair"]["section_id"]
                    if used[sid] >= pass_cap:
                        groups[g].insert(0, r)
                        break
                    used[sid] += 1
                    picked.append(r)
                    progress = True
                    break
    if len(picked) < n:
        raise RuntimeError(f"only {len(picked)} of {n} items available")
    return picked


# ---------------------------------------------------------------- build
def build_items(cp: dict, seed: int) -> tuple[list[dict], dict]:
    pools = pools_from_checkpoint(cp)
    dev_secs, test_secs, used_seed = assign_sections(pools, seed)
    rng = random.Random(seed)
    names = {c["concept_id"]: c["canonical_name"] for c in cp["concepts"]}
    chosen: list[tuple[str, str, dict]] = []  # (split, kind, result)
    taken_pairs: set[frozenset[str]] = set()
    for split, secs, idx in (("dev", dev_secs, 0), ("test", test_secs, 1)):
        for kind, counts in KINDS.items():
            group_of = (
                (lambda r: r["relation"]) if kind == "edge" else (lambda r: r["pair"]["section_id"])
            )
            pool = [
                r
                for r in pools[kind]
                if frozenset((r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]))
                not in taken_pairs
            ]
            for r in pick(pool, counts[idx], rng, group_of, secs):
                taken_pairs.add(frozenset((r["pair"]["concept_x_id"], r["pair"]["concept_y_id"])))
                chosen.append((split, kind, r))
    rng.shuffle(chosen)  # blind item ids carry no order information
    items = []
    for i, (split, kind, r) in enumerate(chosen, 1):
        p = r["pair"]
        flip = rng.random() < 0.5  # which concept is shown first
        a_id, b_id = (
            (p["concept_y_id"], p["concept_x_id"])
            if flip
            else (p["concept_x_id"], p["concept_y_id"])
        )
        items.append(
            {
                "item_id": f"RM{i:03d}",
                "split": split,
                "stratum": STRATUM[kind],
                "kind": kind,
                "pair_id": p["pair_id"],
                "section_id": p["section_id"],
                "concept_x_id": p["concept_x_id"],
                "concept_y_id": p["concept_y_id"],
                "name_x": names[p["concept_x_id"]],
                "name_y": names[p["concept_y_id"]],
                "shown_a": "y" if flip else "x",
                "concept_a": names[a_id],
                "concept_b": names[b_id],
                "sentence": p["sentence"],
                "current_outcome": r["outcome"],
                "current_family": r.get("family"),
                "current_relation": r.get("relation"),
                "current_direction": r.get("direction"),
                "current_qualifiers": json.dumps(r.get("qualifiers") or {}, sort_keys=True),
                "current_reason": r.get("reason"),
                "other_suggested_label": r.get("other_suggested_label"),
            }
        )
    meta = {
        "seed": seed,
        "split_seed_used": used_seed,
        "dev_sections": sorted(dev_secs),
        "test_sections": sorted(test_secs),
    }
    return items, meta


# ---------------------------------------------------------------- checks
def leakage_check(items: list[dict]) -> dict:
    """The blind-split guard: no evidence section and no unordered concept pair on both sides of the split."""
    secs = {s: {i["section_id"] for i in items if i["split"] == s} for s in ("dev", "test")}
    pairs = {
        s: {frozenset((i["concept_x_id"], i["concept_y_id"])) for i in items if i["split"] == s}
        for s in ("dev", "test")
    }
    ids = [i["item_id"] for i in items]
    return {
        "shared_evidence_sections": sorted(secs["dev"] & secs["test"]),
        "shared_concept_pairs": len(pairs["dev"] & pairs["test"]),
        "duplicate_item_ids": len(ids) - len(set(ids)),
        "duplicate_pair_ids": len(items) - len({i["pair_id"] for i in items}),
        "ok": not (secs["dev"] & secs["test"])
        and not (pairs["dev"] & pairs["test"])
        and len(ids) == len(set(ids))
        and len(items) == len({i["pair_id"] for i in items}),
    }


def composition(items: list[dict]) -> dict:
    return {
        "total": len(items),
        "by_split": dict(Counter(i["split"] for i in items)),
        "by_stratum": dict(Counter(i["stratum"] for i in items)),
        "by_split_stratum": {
            f"{s}/{t}": n
            for (s, t), n in sorted(Counter((i["split"], i["stratum"]) for i in items).items())
        },
        "accepted_edge_relations": dict(
            Counter(
                i["current_relation"] for i in items if i["stratum"] == "ACCEPTED_EDGE"
            ).most_common()
        ),
        "evidence_sections": len({i["section_id"] for i in items}),
    }


PREFILLED = ("item_id", "evidence_section_id", "evidence_text", "concept_a", "concept_b")


def blind_rows(items: list[dict], headings: dict[str, str]) -> list[dict]:
    rows = []
    for i in sorted(items, key=lambda x: x["item_id"]):
        row = dict.fromkeys(BLIND_COLUMNS, "")
        row.update(
            {
                "item_id": i["item_id"],
                "evidence_section_id": i["section_id"],
                "evidence_text": f"[{headings.get(i['section_id'], i['section_id'])}] {i['sentence']}",
                "concept_a": i["concept_a"],
                "concept_b": i["concept_b"],
            }
        )
        rows.append(row)
    return rows


def assert_blind(rows: list[dict]) -> None:
    """The blind sheet has exactly the template columns, and only the five evidence fields are filled."""
    assert list(rows[0]) == BLIND_COLUMNS, "blind sheet columns differ from the template"
    for r in rows:
        assert all(not r[c] for c in BLIND_COLUMNS if c not in PREFILLED), (
            "a judgement column is pre-filled"
        )


# ---------------------------------------------------------------- annotation validation
def allowed_values(relation_names: list[str], erst_labels: list[str]) -> dict[str, set[str]]:
    return {
        "current_semantic_relation_judgement": {*relation_names, "none", "other"},
        "erst_applies_yes_no": YES_NO,
        "erst_relation_1": set(erst_labels),
        "erst_relation_2_optional": set(erst_labels),
        "direction_judgement": DIRECTION_VALUES,
        "nuclearity_judgement_if_relevant": NUCLEARITY_VALUES,
        "machine_useful_meaning_survives_yes_no": YES_NO,
        **{c: YES_NO for c in LOSS_COLUMNS},
    }


def validate_sheet(
    rows: list[dict], expected_ids: list[str], allowed: dict[str, set[str]]
) -> list[str]:
    problems: list[str] = []
    ids = [r["item_id"] for r in rows]
    if sorted(ids) != sorted(expected_ids):
        problems.append("item ids differ from the frozen sheet")
    for r in rows:
        iid = r["item_id"]
        if not r.get("annotator_id", "").strip():
            problems.append(f"{iid}: annotator_id is empty")
        for col, ok in allowed.items():
            v = r.get(col, "").strip()
            if v and v not in ok:
                problems.append(f"{iid}: {col}={v!r} is not an allowed value")
        for col in (
            "current_semantic_relation_judgement",
            "erst_applies_yes_no",
            "machine_useful_meaning_survives_yes_no",
        ):
            if not r.get(col, "").strip():
                problems.append(f"{iid}: {col} is required")
        if (
            r.get("erst_applies_yes_no", "").strip() == "yes"
            and not r.get("erst_relation_1", "").strip()
        ):
            problems.append(f"{iid}: erst applies but erst_relation_1 is empty")
        if r.get("erst_applies_yes_no", "").strip() == "no" and (
            r.get("erst_relation_1", "").strip() or r.get("erst_relation_2_optional", "").strip()
        ):
            problems.append(f"{iid}: erst does not apply but a relation is given")
    return problems


# ---------------------------------------------------------------- files
def _sha(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def guide_markdown(relations: list[dict], erst: list[dict]) -> str:
    L = [
        "# REL-MAP-180 annotation guide (blind)",
        "",
        "You see 180 short evidence passages, each with two concepts (A, B). Judge what the TEXT says. You are not shown any",
        "system output; do not look for it. Work on a copy saved as `data/gold/cr010_relmap180_blind_sheet_annotator1.csv`.",
        "",
        "## Columns to fill",
        "",
        "| column | allowed values |",
        "|---|---|",
        "| annotator_id | your id (every row) |",
        "| current_semantic_relation_judgement | one relation name from the list below, or `none` (the text states no relation between A and B), or `other` (a relation the list lacks; say which in notes) |",
        "| direction_judgement | `a_to_b` (A is the first term of the relation as written in its template), `b_to_a`, `symmetric`, `not_applicable` |",
        "| erst_applies_yes_no | `yes` if the two concepts sit in different discourse units that stand in one of the discourse relations below; `no` if both are in one unit or no discourse relation links them |",
        "| erst_relation_1 / erst_relation_2_optional | an eRST label below (the second only for a concurrent relation); leave blank when erst_applies is `no` |",
        "| nuclearity_judgement_if_relevant | `nucleus_a`, `nucleus_b` (the unit holding that concept is the nucleus), `both_nuclei` (multinuclear), `either`, `not_applicable` |",
        "| machine_useful_meaning_survives_yes_no | `yes` if the eRST judgement alone would still let a program recover what you wrote in the semantic-relation column (kind, part, mechanism, direction, ...); `no` if something useful is lost |",
        "| loss_* (11 columns) | `yes` only for the kinds of information that would be lost; otherwise leave blank |",
        "| other_loss_notes, annotator_notes | free text |",
        "",
        "Loss kinds: taxonomy; part/whole composition; mechanism; network topology; identifier semantics; encapsulation/payload semantics; causal sign/direction; technical dependency; trade-off semantics; pedagogical prerequisite; principle-instance organisation.",
        "",
        "## Semantic relations (registry v1.3)",
        "",
        "| name | definition | template |",
        "|---|---|---|",
    ]
    L += [
        f"| {r['name']} | {' '.join(str(r.get('definition', '')).split())} | {r.get('template', '')} |"
        for r in relations
    ]
    L += [
        "",
        "## eRST discourse relations (31; `SAME-UNIT` is a technical label and is never used)",
        "",
        "Nuclearity: `→←` satellite relation in either direction; `Λ` multinuclear; `←` the nucleus comes first and the satellite after; `→` the satellite comes first.",
        "",
        "| label | nuclearity | definition |",
        "|---|---|---|",
    ]
    L += [
        f"| {r['label']} | {r['primary_nuclearity_symbol']} | {' '.join(r['definition'].split())} |"
        for r in erst
        if r["is_true_discourse_relation"]
    ]
    L += [
        "",
        "Do not skip rows. A row you cannot judge: `none` / `no` and say why in annotator_notes.",
        "",
    ]
    return "\n".join(L)


def build(run: str, seed: int) -> dict:
    from cumap.config import get_settings, load_demo_slice
    from cumap.expert_kg import slice_rerun as sr

    cp = json.loads((KG / run / "checkpoint.json").read_text())
    items, meta = build_items(cp, seed)
    leak = leakage_check(items)
    if not leak["ok"]:
        raise RuntimeError(f"split leakage: {leak}")
    comp = composition(items)
    assert comp["total"] == 180 and comp["by_split"] == {"dev": 60, "test": 120}
    assert {k: v for k, v in comp["by_stratum"].items()} == {
        "ACCEPTED_EDGE": 120,
        "NO_RELATION": 30,
        "OTHER_NEAR_MISS": 30,
    }
    slice_cfg = load_demo_slice()
    heads = {
        s.section_id: f"§{s.section_id} " + " > ".join(s.heading_path[-1:])
        for s in sr.load_sections(
            REPO_ROOT / slice_cfg.pd.source_jsonl, list(slice_cfg.pd.chapters)
        )
    }
    brows = blind_rows(items, heads)
    assert_blind(brows)
    key_cols = list(items[0])
    write_csv(CHECKS / "cr010_relmap180_blind_sheet.csv", brows, BLIND_COLUMNS)
    write_csv(
        CHECKS / "cr010_relmap180_MANIFEST_KEY_DO_NOT_SHARE.csv",
        sorted(items, key=lambda x: x["item_id"]),
        key_cols,
    )
    registry = yaml.safe_load((REPO_ROOT / get_settings().relation_registry).read_text())
    erst = yaml.safe_load((REPO_ROOT / "configs/erst_relations.yaml").read_text())["relations"]
    guide = guide_markdown(registry["relations"], erst)
    (REPO_ROOT / "docs/cr010/RELMAP180_ANNOTATION_GUIDE.md").write_text(guide, encoding="utf-8")
    manifest = {
        "benchmark": "REL-MAP-180",
        "built_from_run": run,
        "registry": str(get_settings().relation_registry),
        **meta,
        "composition": comp,
        "leakage_check": leak,
        "blind_sheet_sha256": _sha(brows),
        "manifest_sha256": _sha(sorted(items, key=lambda x: x["item_id"])),
        "double_annotation": "not available (no second annotator): kappa is not measured",
        "not_read": ["cr010_current_to_erst_mapping_NOT_GOLD.csv"],
    }
    (CHECKS / "cr010_relmap180_manifest.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8"
    )
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["build", "validate"])
    ap.add_argument("--run", default="slice3_c2")
    ap.add_argument("--seed", type=int, default=20261005)
    ap.add_argument("--sheet")
    a = ap.parse_args()
    if a.phase == "build":
        print(json.dumps(build(a.run, a.seed), indent=1))
        return
    from cumap.config import get_settings

    registry = yaml.safe_load((REPO_ROOT / get_settings().relation_registry).read_text())
    erst = yaml.safe_load((REPO_ROOT / "configs/erst_relations.yaml").read_text())["relations"]
    allowed = allowed_values(
        [r["name"] for r in registry["relations"]],
        [r["label"] for r in erst if r["is_true_discourse_relation"]],
    )
    with (CHECKS / "cr010_relmap180_blind_sheet.csv").open(encoding="utf-8") as f:
        expected = [r["item_id"] for r in csv.DictReader(f)]
    with Path(a.sheet).open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    problems = validate_sheet(rows, expected, allowed)
    print(f"{len(rows)} rows, {len(problems)} problems")
    for p in problems[:50]:
        print(" -", p)


if __name__ == "__main__":
    main()
