"""CR-035 ($0, no model call except the local sentence-transformers embedder): replay of the deterministic identity resolver on a saved run.

    uv run python -m cumap.cr035.replay [--run slice3_c2]

(1) U0-U4 over the recorded merges: the input B merges (checkpoint `canonicalize_v4` entries) and the input A links (`v4_concepts.json` G-link and
G-link-rejected entries), compared with what was recorded. (2) The registry search, legacy vs the u1 recipe: candidate recall on the owner-marked `same`
pairs of the CR-007 / CR-008 merge sheets, and how many mentions would reach the LLM judge under each. Read-only; writes only `reports/cr035/`.
Thresholds (offer 0.6) are reported as is and not tuned (configs/identity_rules.yaml)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict

import numpy as np

from cumap.concepts_v4 import experiments as X
from cumap.concepts_v4 import pd_run as P
from cumap.config import REPO_ROOT, get_settings, load_demo_slice
from cumap.expert_kg import identity as ID
from cumap.expert_kg import slice_rerun as sr
from cumap.expert_kg.canonical_rules import AliasContext
from cumap.expert_kg.canonicalize import ConceptRegistry, RegisteredConcept
from cumap.expert_kg.lexicon import Lexicon

OUT = REPO_ROOT / "reports/cr035"
KG = REPO_ROOT / "data/processed/kg"
SHEETS = ("cr007_merge_sheet", "cr008_merge_sheet")


def load_units() -> list[dict]:
    sc = load_demo_slice()
    secs = sr.load_sections(REPO_ROOT / sc.pd.source_jsonl, list(sc.pd.chapters))
    raw = [{"section_id": s.section_id, "chapter_num": s.chapter_num, "order_index": i, "text": s.text, "heading_path": s.heading_path} for i, s in enumerate(secs)]  # fmt: skip
    return P.make_units(raw)


# ---------------------------------------------------------------- (1) U0-U4 over recorded decisions
def replay_rules(cp: dict, v4: dict, units: list[dict], lexicon: Lexicon) -> dict:
    nodes = v4["nodes"]
    forms = [f for n in nodes.values() for f in [n["name"], *n["aliases"]]]
    texts, chapter_of = {}, {}
    for u in units:
        texts[u["orig_section"]] = (texts.get(u["orig_section"], "") + "\n\n" + u["text"]).strip()
        chapter_of[u["orig_section"]] = int(u["chapter_num"])
    ctx_b = AliasContext.build(lexicon, texts, chapter_of, forms)
    concepts = {c["concept_id"]: c for c in cp["concepts"]}
    b = Counter()
    b_changes = []
    for m in cp["merges"]:
        if m.get("stage") != "canonicalize_v4":
            continue
        c = concepts[m["concept_id"]]
        rec = m.get("rule_id")
        forms_c = [
            f for f in [c["canonical_name"], *c["aliases"]] if f.lower() != m["alias"].lower()
        ] or [c["canonical_name"]]
        d = ID.resolve_against_forms(ctx_b, m["alias"], forms_c, chapter=chapter_of.get(m["section_id"]), surface_type=c["node_type"], node_type=c["node_type"])  # fmt: skip
        got = d.rule_id or d.decision
        if rec:
            expected = ID.LEGACY_TO_U.get(rec)
            kind = (
                "same rule"
                if got == expected
                else (
                    "merge by a higher-precedence rule (U1 before U2)"
                    if d.decision == "merge"
                    else "not reproduced"
                )
            )
        else:
            kind = (
                "LLM merge, still undecided by U0-U4"
                if d.decision == "undecided"
                else "LLM merge now decided by U0-U4"
            )
        b[(rec or "-", got, kind)] += 1
        if kind in ("not reproduced", "LLM merge now decided by U0-U4"):
            b_changes.append(
                {
                    "alias": m["alias"],
                    "concept": c["canonical_name"],
                    "recorded": rec or "llm",
                    "u1": got,
                }
            )
    unit_ctx: dict[str, AliasContext] = {}
    a = Counter()
    a_changes = []
    for g in v4["merges"]:
        if g["rule_id"] not in ("G-link", "G-link-rejected"):
            continue
        node = nodes.get(g["node_id"])
        u = next((u for u in units if u["section_id"] == g["section_id"]), None)
        if node is None or u is None:
            a[("skipped", g["rule_id"], "no_node_or_unit")] += 1
            continue
        if g["section_id"] not in unit_ctx:
            unit_ctx[g["section_id"]] = AliasContext.build(
                lexicon,
                {g["section_id"]: u["text"]},
                {g["section_id"]: int(u["chapter_num"])},
                forms,
            )
        node_forms = [f for f in [node["name"], *node["aliases"]] if f != g["surface"]]
        d = ID.resolve_against_forms(
            unit_ctx[g["section_id"]],
            g["surface"],
            node_forms,
            chapter=int(u["chapter_num"]),
            surface_type=node["node_type"],
            node_type=node["node_type"],
        )
        a[(g["rule_id"], d.rule_id or d.decision)] += 1
        if (g["rule_id"] == "G-link-rejected" and d.decision in ("merge", "keep_apart")) or (
            g["rule_id"] == "G-link" and d.decision == "keep_apart"
        ):
            a_changes.append(
                {
                    "surface": g["surface"],
                    "node": node["name"],
                    "recorded": g["rule_id"],
                    "u1": d.rule_id,
                    "quote": d.evidence_quote,
                }
            )
    flat = lambda c: {
        " | ".join(map(str, k)): v for k, v in sorted(c.items(), key=lambda kv: str(kv[0]))
    }
    return {
        "input_B": flat(b),
        "input_B_changes": b_changes,
        "input_A": flat(a),
        "input_A_changes": a_changes,
        "stats_b": dict(ctx_b.stats),
    }


# ---------------------------------------------------------------- (2) the search, legacy vs u1 recipe
def marked_same_pairs() -> list[dict]:
    out = []
    for name in SHEETS:
        for r in csv.DictReader((REPO_ROOT / f"data/gold/{name}.csv").open(encoding="utf-8")):
            if r["mark (same/different)"].strip().lower() == "same":
                out.append(
                    {
                        "sheet": name,
                        "id": r["id"],
                        "a": r["name_A"],
                        "b": r["name_B"],
                        "evidence": r["evidence"],
                        "section": r["section"],
                    }
                )
    return out


def _registry(cp: dict, embed, drop: set[str], without: set[str]) -> ConceptRegistry:
    reg = ConceptRegistry(embed)
    cs = []
    for c in cp["concepts"]:
        if c["concept_id"] in drop:
            continue
        rc = RegisteredConcept(c["concept_id"], c["canonical_name"], c["node_type"], c.get("definition"), c.get("first_introduced") or "", [a for a in c["aliases"] if a.lower() not in without])  # fmt: skip
        from cumap.expert_kg.canonicalize import Mention

        rc.mentions = [Mention(m["section_id"], m["role"], m["quote"]) for m in c["mentions"][:1]]
        cs.append(rc)
    reg.restore(cs)
    return reg


def search_recall(cp: dict, embed, threshold: float = 0.6, k: int = 5) -> dict:
    """For each owner-marked `same` pair: the concept holding one form is the target; the other form is the query, removed from the target first (the
    registry as it was before that merge). Recall = target in the top k and similarity >= threshold."""
    pairs = marked_same_pairs()
    rows = []
    by_form = defaultdict(list)
    for c in cp["concepts"]:
        for f in [c["canonical_name"], *c["aliases"]]:
            by_form[f.lower()].append(c)
    for p in pairs:
        a, b = p["a"], p["b"]
        t = next((c for c in by_form.get(b.lower(), []) + by_form.get(a.lower(), [])), None)
        if t is None:
            rows.append({**p, "status": "no_concept"})
            continue
        # the query is the form that is not the target's canonical name
        query = a if t["canonical_name"].lower() == b.lower() else b
        if query.lower() == t["canonical_name"].lower():
            rows.append({**p, "status": "same_name"})
            continue
        quote = p["evidence"]
        reg = _registry(cp, embed, set(), {query.lower()})
        legacy = reg.top_k_similar(query, None, k=k)
        u1 = reg.top_k_similar_forms(query, quote, k=k)
        l_hit = next(
            ((i, s) for i, (c, s) in enumerate(legacy) if c.concept_id == t["concept_id"]), None
        )
        u_hit = next(
            ((i, s, f) for i, (c, s, f) in enumerate(u1) if c.concept_id == t["concept_id"]), None
        )
        rows.append({**p, "status": "ok", "query": query, "target": t["canonical_name"], "legacy_rank": l_hit[0] if l_hit else None, "legacy_sim": l_hit[1] if l_hit else None, "u1_rank": u_hit[0] if u_hit else None, "u1_sim": u_hit[1] if u_hit else None, "u1_form": u_hit[2] if u_hit else None})  # fmt: skip
    ok = [r for r in rows if r["status"] == "ok"]
    rec = lambda key: sum(
        1 for r in ok if r[key + "_rank"] is not None and r[key + "_sim"] >= threshold
    )
    return {
        "pairs_marked_same": len(pairs),
        "evaluated": len(ok),
        "skipped": dict(Counter(r["status"] for r in rows if r["status"] != "ok")),
        "recall_legacy": rec("legacy"),
        "recall_u1": rec("u1"),
        "threshold": threshold,
        "k": k,
        "rows": rows,
    }


def llm_reach(cp: dict, embed, threshold: float = 0.6, k: int = 5) -> dict:
    """In book order, how many concepts find at least one candidate >= threshold in the top k of the earlier concepts, under each search (each one is a
    strong-tier call on the B path). Registry = earlier final concepts as they are in the checkpoint (an approximation of the run-time registry)."""
    cs = sorted(cp["concepts"], key=lambda c: (c.get("first_introduced") or "", c["concept_id"]))
    legacy_n = u1_n = 0
    reg = ConceptRegistry(embed)
    from cumap.expert_kg.canonicalize import Mention

    for c in cs:
        quote = c["mentions"][0]["quote"] if c["mentions"] else None
        if len(reg):
            l = reg.top_k_similar(c["canonical_name"], c.get("definition"), k=k)
            u = reg.top_k_similar_forms(c["canonical_name"], quote, k=k)
            legacy_n += bool(l and l[0][1] >= threshold)
            u1_n += bool(u and u[0][1] >= threshold)
        rc = RegisteredConcept(c["concept_id"], c["canonical_name"], c["node_type"], c.get("definition"), c.get("first_introduced") or "", list(c["aliases"]))  # fmt: skip
        rc.mentions = [Mention(m["section_id"], m["role"], m["quote"]) for m in c["mentions"][:1]]
        reg.restore([rc])
    return {
        "concepts": len(cs),
        "reach_llm_legacy": legacy_n,
        "reach_llm_u1": u1_n,
        "threshold": threshold,
    }


def markdown(run: str, res: dict, unchanged: bool) -> str:
    r1, s = res["rules"], res["search"]
    L = [
        f"# CR-035 identity resolver (deterministic part): $0 replay on `{run}`",
        "",
        f"Generated by `cumap.cr035.replay`. Read-only; source hashes identical before and after: **{unchanged}**. `identity_resolver: u1` is NOT adopted (default `legacy`); no model call; no pre-registered paid measurement was run (it waits for the owner, handoff §7 step 8).",
        "",
        "## U0-U4 over the recorded input B merges (`canonicalize_v4`)",
        "",
        "| outcome | recorded rule | U-rule now | count |",
        "|---|---|---|---|",
        *[
            f"| {k.split(' | ')[2]} | {k.split(' | ')[0]} | {k.split(' | ')[1]} | {v} |"
            for k, v in r1["input_B"].items()
        ],
        "",
        f"Differences from the recorded decision (a deterministic merge U0-U4 cannot reproduce, or an LLM merge that U0-U4 now decide): **{len(r1['input_B_changes'])}**.",
        *[
            f"- {c['alias']} / {c['concept']}: recorded {c['recorded']}, u1 {c['u1']}"
            for c in r1["input_B_changes"][:15]
        ],
        "",
        "## U0-U4 over the recorded input A links (G-link accepted, G-link-rejected)",
        "",
        "| recorded | u1 | count |",
        "|---|---|---|",
        *[f"| {k.split(' | ')[0]} | {k.split(' | ')[1]} | {v} |" for k, v in r1["input_A"].items()],
        "",
        f"Intended changes (a rejected link that U0-U4 now merge or veto, or an accepted link that U0 now vetoes): **{len(r1['input_A_changes'])}**.",
        *[
            f"- {c['surface']} -> {c['node']}: recorded {c['recorded']}, u1 {c['u1']}; “{c['quote']}”"
            for c in r1["input_A_changes"][:20]
        ],
        "",
        "## Registry search, legacy vs u1 recipe (name + gloss, every form)",
        "",
        f"Owner-marked `same` pairs of the CR-007 / CR-008 merge sheets: {s['pairs_marked_same']}; evaluated {s['evaluated']} (skipped: {s['skipped']}). Candidate recall (the true match in the top {s['k']} and similarity >= {s['threshold']}, threshold not tuned): **legacy {s['recall_legacy']} of {s['evaluated']}, u1 {s['recall_u1']} of {s['evaluated']}**.",
        "",
        f"Mentions that would reach the LLM judge (best candidate >= {s['threshold']}, concepts in book order against earlier concepts): legacy **{res['reach']['reach_llm_legacy']}**, u1 **{res['reach']['reach_llm_u1']}** of {res['reach']['concepts']} concepts (each is a strong-tier call).",
        "",
        "Limits: the registry here is the final checkpoint minus the query form, not the exact run-time registry; the owner-marked pairs include pairs the lexicon already covers (they pass U0/U1 trivially); no held-out set is used.",
    ]
    return "\n".join(L) + "\n"


def main(run: str = "slice3_c2") -> dict:
    cp_path, v4_path = KG / run / "checkpoint.json", KG / run / "v4_concepts.json"
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (cp_path, v4_path)}
    cp, v4 = (
        json.loads(cp_path.read_text(encoding="utf-8")),
        json.loads(v4_path.read_text(encoding="utf-8")),
    )
    units, lexicon = load_units(), Lexicon.load()
    embed = X.Embedder(get_settings().embeddings.model)
    res = {
        "rules": replay_rules(cp, v4, units, lexicon),
        "search": search_recall(cp, embed),
        "reach": llm_reach(cp, embed),
    }
    unchanged = before == {
        p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (cp_path, v4_path)
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"identity_replay_{run}.json").write_text(
        json.dumps(res, indent=1, default=str), encoding="utf-8"
    )
    (OUT / f"identity_replay_{run}.md").write_text(markdown(run, res, unchanged), encoding="utf-8")
    print(
        {k: v for k, v in res["search"].items() if k != "rows"},
        res["reach"],
        {k: len(v) for k, v in res["rules"].items() if k.endswith("changes")},
    )
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="slice3_c2")
    np.random.seed(0)
    main(ap.parse_args().run)
