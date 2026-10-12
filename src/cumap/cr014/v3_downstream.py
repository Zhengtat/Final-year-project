"""CR-014 STOP 5: put the baseline (U0) and the frozen V3 concepts through the SAME frozen downstream stages (canonicalisation v2, anchor-first pair
selection with the D3 pair budget, relation stage) and measure the consequences. Nothing here changes V3 or U0 and nothing overwrites a historical run.

V3 emits accepted surfaces, not graph nodes. The adapter (a) assigns a node type with the frozen `cr014_node_typing` v1 prompt (types only; it never rejects a concept),
(b) sets role by the production definitional pattern (defined) else used, (c) attaches the first-occurrence sentence as evidence, (d) lets a V3 node inherit
the anchors of a U0 node that has the same surface (anchors only set pair priority, rule 27). Everything else is the production code path.

    uv run python -m cumap.cr014.v3_downstream type --section 4.2
    uv run python -m cumap.cr014.v3_downstream build --section 4.2 --max-usd 1
    uv run python -m cumap.cr014.v3_downstream downstream --arm U0|V3 --section 4.2 [--dry-run] --max-usd 3"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Literal

from cumap.concepts_v4.schema import NODE_TYPES, _Strict

ROOT = Path(".")
HELD = ROOT / "data/processed/cr014/heldout"
NodeTypeL = Literal[*NODE_TYPES]


class TypeItemLLM(_Strict):
    item_id: str
    node_type: NodeTypeL


class NodeTypingBatchLLM(_Strict):
    items: list[TypeItemLLM]


def section_row(sid: str) -> dict:
    for line in (ROOT / "data/interim/textbook_sections.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["section_id"] == sid:
            return r
    raise KeyError(sid)


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def v3_items(sid: str) -> list[dict]:
    """Accepted V3 surfaces with a first-occurrence sentence (evidence), in text order."""
    import spacy

    from cumap.cr014.union import surface_regex

    nlp = spacy.load("en_core_web_sm")
    text = section_row(sid)["text"]
    sents = [(s.start_char, s.end_char) for s in nlp(text).sents]
    acc = json.loads((HELD / f"V3_{sid}.json").read_text())["outcome"]["accepted"]
    items = []
    for surf in acc:
        m = surface_regex(surf).search(text)
        if not m:
            continue
        s0, s1 = next((a, b) for a, b in sents if a <= m.start() < b)
        items.append(
            {
                "surface": surf,
                "start": m.start(),
                "end": m.end(),
                "sent": (s0, s1),
                "evidence": _ws(text[s0:s1]),
            }
        )
    items.sort(key=lambda x: (x["start"], x["surface"]))
    for i, it in enumerate(items):
        it["item_id"] = f"{sid}#t{i:05d}"
    return items


def type_nodes(sid: str, client, batch: int = 40) -> dict[str, str]:
    from cumap.llm.prompts import load_prompt

    text = section_row(sid)["text"]
    prompt = load_prompt(ROOT / "prompts", "cr014_node_typing", "v1")
    items = v3_items(sid)
    heading = " > ".join(section_row(sid)["heading_path"] or []) or sid
    out: dict[str, str] = {}
    for i in range(0, len(items), batch):
        chunk = items[i : i + batch]
        lines = []
        for it in chunk:
            s0, s1 = it["sent"]
            sent = (
                text[s0 : it["start"]]
                + "<<"
                + text[it["start"] : it["end"]]
                + ">>"
                + text[it["end"] : s1]
            )
            lines.append(f"{it['item_id']} | {it['surface']} | {_ws(sent)[:400]}")
        r = client.parse(
            task=prompt.task, prompt_version=prompt.version,
            messages=[{"role": "user", "content": prompt.render(domain="computer networking", heading_path=heading, items="\n".join(lines))}],
            schema=NodeTypingBatchLLM, model_tier="bulk", allow_escalation=False,
        )  # fmt: skip
        known = {it["item_id"] for it in chunk}
        for t in r.output.items:
            if t.item_id in known and t.item_id not in out:
                out[t.item_id] = t.node_type
    (HELD / f"typing_{sid}.json").write_text(
        json.dumps({"types": out, "n_items": len(items), "answered": len(out)})
    )
    return out


def build_v3_checkpoint(sid: str, max_usd: float) -> dict:
    """V3 surfaces -> v4 nodes -> production canonicalisation -> checkpoint `cr014_heldout_<sid>_V3` (stage pairs_enumerated)."""
    from cumap.concepts_v4 import experiments as X
    from cumap.concepts_v4 import pd_run as P
    from cumap.concepts_v4.cards import Node, NodeStore, split_paragraphs
    from cumap.concepts_v4.runner import RunOutput
    from cumap.config import get_settings, load_demo_slice
    from cumap.cr012.unit_run import prepare
    from cumap.cr014.proposal import definitional_hits
    from cumap.expert_kg import slice_rerun as sr
    from cumap.expert_kg.lexicon import Lexicon
    from cumap.expert_kg.pipeline import save_checkpoint
    from cumap.llm.client import LLMClient
    from cumap.llm.prompts import load_prompt

    info = prepare(sid)
    os.environ["CUMAP_DEMO_SLICE"] = info["slice_config"]
    settings = get_settings()
    cfg = load_demo_slice()
    sections = sr.load_sections(ROOT / cfg.pd.source_jsonl, list(cfg.pd.chapters))
    raw = [
        {
            "section_id": s.section_id,
            "chapter_num": s.chapter_num,
            "order_index": i,
            "text": s.text,
            "heading_path": s.heading_path,
        }
        for i, s in enumerate(sections)
    ]
    units = P.make_units(raw)
    text = section_row(sid)["text"]
    client = LLMClient(settings, run_id=f"cr014_heldout_{sid.replace('.', '_')}_V3_build")
    types = (
        json.loads((HELD / f"typing_{sid}.json").read_text())["types"]
        if (HELD / f"typing_{sid}.json").exists()
        else type_nodes(sid, client)
    )
    defs = definitional_hits(text)
    u0 = json.loads(
        (
            ROOT / f"data/processed/kg/cr014_heldout_{sid.replace('.', '_')}_U0/v4_concepts.json"
        ).read_text()
    )
    u0_by_form: dict[str, dict] = {}
    for n in u0["nodes"].values():
        for f in [n["name"], *n["aliases"]]:
            u0_by_form.setdefault(" ".join(f.lower().split()), n)
    store = NodeStore()
    items = v3_items(sid)
    by_surface: dict[str, str] = {}
    for i, it in enumerate(items):
        ev = it["evidence"]
        unit = next((u for u in units if ev in _ws(u["text"])), units[0])
        paras = split_paragraphs(unit["text"])
        para = next((k for k, v in paras.items() if ev in _ws(v)), "P1")
        nid = f"v3_{i:05d}"
        role = "defined" if it["surface"].lower() in defs else "used"
        node = Node(
            id=nid, name=it["surface"], aliases=[], node_type=types.get(it["item_id"], "Concept"),
            first_section=unit["section_id"], first_order=unit["order_index"], gloss=ev[:160],
            definition=ev if role == "defined" else None, def_section=unit["section_id"] if role == "defined" else None,
            mentions=[{"section_id": unit["section_id"], "order": i, "role": role, "para": para, "evidence": ev, "surface": it["surface"], "linked_by": "generator"}],
        )  # fmt: skip
        store.nodes[nid] = node
        by_surface[" ".join(it["surface"].lower().split())] = nid
    n_inherited = 0
    for nid, node in store.nodes.items():
        src = u0_by_form.get(" ".join(node.name.lower().split()))
        for a in (src or {}).get("anchors", []):
            tgt = u0["nodes"].get(a["node_id"])
            tid = by_surface.get(" ".join(tgt["name"].lower().split())) if tgt else None
            if tid and tid != nid:
                node.anchors.append({**a, "node_id": tid})
                n_inherited += 1
    out = RunOutput(store=store)
    lexicon = Lexicon.load(ROOT / "configs/term_lexicon.yaml")
    embed = X.Embedder(settings.embeddings.model)
    from cumap.expert_kg.canonicalize import CanonicalOverrides

    overrides = CanonicalOverrides.load(ROOT / "configs/canonical_overrides.yaml")
    res = P.canonicalise(
        out,
        units,
        lexicon,
        client,
        load_prompt(ROOT / "prompts", "canonicalize", "v2"),
        embed,
        overrides,
    )
    texts = {}
    for u in units:
        texts[u["orig_section"]] = (texts.get(u["orig_section"], "") + "\n\n" + u["text"]).strip()
    cp = P.build_checkpoint(f"cr014_heldout_{sid.replace('.', '_')}_V3", out, res, units, texts)
    sr.finish_concepts(cp, sections, embed)
    cp.stage = "pairs_enumerated"
    save_checkpoint(cp, ROOT / "data/processed/kg" / cp.run_id)
    return {"section": sid, "v3_nodes": len(store.nodes), "concepts": len(cp.concepts), "anchors": len(cp.anchors), "anchors_inherited": n_inherited, "canonicalise_llm_calls": res.llm_calls, "spend_usd": round(client.spent_usd, 4)}  # fmt: skip


def downstream(arm: str, sid: str, dry_run: bool, max_usd: float) -> dict:
    """The CR-012 E0 downstream half, on an existing checkpoint: D3 pair budget, anchor-first selection (no unselected sample), relation stage."""
    import math

    from cumap.concepts_v4 import cr009_run as R
    from cumap.cr012.budget import pair_budget
    from cumap.cr012.unit_run import prepare, select_without_sample

    info = prepare(sid)
    os.environ["CUMAP_DEMO_SLICE"] = info["slice_config"]
    run_id = f"cr014_heldout_{sid.replace('.', '_')}_{arm}"
    budget = math.ceil(14.2 * info["words"] / 1000)
    sel = select_without_sample(run_id, budget)
    pool = sel.get("unique_candidate_pairs", 0)
    b = pair_budget(info["words"], pool)
    if b != budget:
        sel = select_without_sample(run_id, b)
    rec = {
        "run_id": run_id,
        "words": info["words"],
        "budget": b,
        "eligible_pool": pool,
        "selected": sel.get("selected"),
        "selection": sel,
    }
    if dry_run:
        rec["relations"] = R.stage_relations(run_id, dry_run=True, max_usd=max_usd)
        return rec
    rec["relations"] = R.stage_relations(run_id, dry_run=False, max_usd=max_usd)
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["type", "build", "downstream"])
    ap.add_argument("--section", required=True)
    ap.add_argument("--arm", choices=["U0", "V3"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-usd", type=float, default=2.0)
    a = ap.parse_args()
    if a.phase == "type":
        from cumap.config import get_settings
        from cumap.llm.client import LLMClient

        c = LLMClient(
            get_settings(), run_id=f"cr014_heldout_{a.section.replace('.', '_')}_V3_typing"
        )
        t = type_nodes(a.section, c)
        print({"answered": len(t), "spend_usd": round(c.spent_usd, 4)})
    elif a.phase == "build":
        print(json.dumps(build_v3_checkpoint(a.section, a.max_usd), indent=1))
    else:
        print(
            json.dumps(downstream(a.arm, a.section, a.dry_run, a.max_usd), indent=1, default=str)[
                :3000
            ]
        )


if __name__ == "__main__":
    main()
