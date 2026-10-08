"""CR-010 P3: an eRST-compatible discourse relation graph over the SENTENCES of the P&D slice sections (not a complete
eRST parse: units are sentences, nuclearity is the inventory's, secondary edges are not built). Candidate-pair EVIDENCE
only (`erst.guards`): the graph never creates a domain edge. Every edge carries an exact quote (rule 3) and passes the
STOP 3 schema (`ErstEdge`, fail closed). All LLM calls go through `LLMClient`.

    uv run python -m cumap.erst.graph dry-run
    uv run python -m cumap.erst.graph run --limit 20     # then without --limit; resumable; hard cap --max-usd (default 10)
    uv run python -m cumap.erst.graph freeze             # graph.json + manifest with sha256; nothing changes after this
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ConfigDict, ValidationError, create_model

from cumap.concepts_v4.schema import _Strict
from cumap.config import REPO_ROOT, get_settings, load_demo_slice
from cumap.erst.edges import ErstEdge, ErstSignal
from cumap.erst.registry import ErstRegistry, Nuclearity
from cumap.expert_kg import slice_rerun as sr
from cumap.expert_kg.relations import split_sentences
from cumap.gold.validate import verify_quote
from cumap.llm.client import BudgetExceededError, LLMClient
from cumap.llm.prompts import load_prompt

PROMPT_VERSION = "v1"
WINDOW = 30
STRIDE = 25
OUT = REPO_ROOT / "data/processed/cr010/erst_graph"
RUN_ID = "cr010_erst_graph"
SIGNAL_KINDS = (
    "discourse_marker",
    "graphical",
    "lexical",
    "morphological",
    "numerical",
    "reference",
    "semantic",
    "syntactic",
)
POSITION_WORDS = {
    Nuclearity.SATELLITE_AFTER: "satellite after nucleus",
    Nuclearity.SATELLITE_BEFORE: "satellite before nucleus",
    Nuclearity.SATELLITE_EITHER: "satellite either order",
    Nuclearity.MULTINUCLEAR: "multinuclear",
}


# ---------------------------------------------------------------- units and windows
@dataclass(frozen=True)
class Window:
    window_id: str
    section_id: str
    heading: str
    first: int  # index of the first unit (inclusive)
    units: tuple[str, ...]  # sentence texts

    @property
    def last(self) -> int:
        return self.first + len(self.units) - 1


def section_units(text: str) -> list[str]:
    """The unit segmentation is the pair enumeration's own sentence splitter, so a concept's sentence index means the
    same thing in P0-P2 and in the graph."""
    return split_sentences(text)


def make_windows(sections: list, size: int = WINDOW, stride: int = STRIDE) -> list[Window]:
    out: list[Window] = []
    for s in sections:
        units = section_units(s.text)
        heading = " > ".join(s.heading_path[-1:])
        start = 0
        while True:
            chunk = units[start : start + size]
            out.append(
                Window(f"{s.section_id}@{start}", s.section_id, heading, start, tuple(chunk))
            )
            if start + size >= len(units):
                break
            start += stride
    return out


# ---------------------------------------------------------------- schema (dynamic: label is a true enum)
def build_schema(reg: ErstRegistry):
    label = Literal[tuple(reg.discourse_labels)]  # type: ignore[valid-type]
    signal = create_model(
        "ErstSignalLLM",
        __base__=_Strict,
        kind=(Literal[SIGNAL_KINDS], ...),  # type: ignore[valid-type]
        subtype=(str | None, ...),
        anchor_text=(str | None, ...),
    )
    edge = create_model(
        "ErstEdgeLLM",
        __base__=_Strict,
        label=(label, ...),
        nucleus_units=(list[str], ...),
        satellite_unit=(str | None, ...),
        satellite_position=(Literal["before", "after"] | None, ...),
        evidence=(str, ...),
        signals=(list[signal], ...),  # type: ignore[valid-type]
        confidence=(float, ...),
    )
    return create_model(
        "ErstGraphLLM",
        __config__=ConfigDict(extra="forbid"),
        edges=(list[edge], ...),  # type: ignore[valid-type]
    )


def relation_options(reg: ErstRegistry) -> str:
    return "\n".join(
        f"- {r.label} ({POSITION_WORDS[r.nuclearity]}): {r.definition}"
        for r in reg.relations
        if r.is_true_discourse_relation
    )


def signal_options(reg: ErstRegistry) -> str:
    lines = []
    for kind in SIGNAL_KINDS:
        subs = reg.subtypes(kind)
        lines.append(f"- {kind}: " + ("(no subtype)" if not subs else "; ".join(subs)))
    return "\n".join(lines)


def render(prompt, reg: ErstRegistry, w: Window) -> str:
    return prompt.render(
        relation_options=relation_options(reg),
        signal_options=signal_options(reg),
        section_id=w.section_id,
        heading=w.heading,
        first_unit=f"U{w.first}",
        last_unit=f"U{w.last}",
        units="\n".join(f"[U{w.first + i}] {t}" for i, t in enumerate(w.units)),
    )


# ---------------------------------------------------------------- verification (code, no model)
def convert(raw: dict, w: Window, reg: ErstRegistry) -> tuple[dict | None, str | None]:
    """One LLM edge -> a validated ErstEdge record, or (None, reason). Checks: unit ids inside the window; satellite
    position agrees with the text order; the evidence is an exact substring of the joined unit texts; signal anchors are
    in the text; the STOP 3 schema (label, nuclearity rules). Invalid signals are dropped and counted, not the edge."""
    ids = {f"U{w.first + i}": w.units[i] for i in range(len(w.units))}
    nuc, sat = raw["nucleus_units"], raw["satellite_unit"]
    involved = [*nuc, *([sat] if sat else [])]
    if not involved or any(u not in ids for u in involved):
        return None, "unit_not_in_window"
    if len(set(involved)) != len(involved):
        return None, "repeated_unit"
    num = lambda u: int(u[1:])
    order = sorted(involved, key=num)
    text = " ".join(ids[u] for u in order)
    if not verify_quote(raw["evidence"], text):
        return None, "evidence_not_in_units"
    if sat and raw["satellite_position"]:
        actual = "before" if num(sat) < num(nuc[0]) else "after"
        if actual != raw["satellite_position"]:
            return None, "position_mismatch"
    signals, dropped = [], 0
    for s in raw["signals"]:
        try:
            if s["anchor_text"] and not verify_quote(s["anchor_text"], text):
                raise ValueError("anchor not in units")
            signals.append(ErstSignal(**s))
        except (ValidationError, ValueError):
            dropped += 1
    try:
        edge = ErstEdge(
            edge_kind="primary",
            label=raw["label"],
            evidence=raw["evidence"],
            nucleus_units=list(nuc),
            satellite_unit=sat,
            satellite_position=raw["satellite_position"],
            from_unit=None,
            to_unit=None,
            signals=signals,
            concurrent_labels=[],
        )
    except (ValidationError, ValueError) as e:
        return None, "schema:" + str(e).splitlines()[-1][:80]
    reg.get(edge.label)
    return {
        "section_id": w.section_id,
        "window_id": w.window_id,
        "edge": edge.model_dump(mode="json"),
        "confidence": raw["confidence"],
        "signals_dropped": dropped,
    }, None


# ---------------------------------------------------------------- run
def _sections():
    cfg = load_demo_slice()
    return sr.load_sections(REPO_ROOT / cfg.pd.source_jsonl, list(cfg.pd.chapters))


def _done(path: Path) -> dict[str, dict]:
    return (
        {json.loads(x)["window_id"]: json.loads(x) for x in path.read_text().splitlines() if x}
        if path.exists()
        else {}
    )


def dry_run(max_out_tokens: int = 3000) -> dict:
    s = get_settings()
    reg, prompt = (
        ErstRegistry.load(),
        load_prompt(REPO_ROOT / "prompts", "erst_graph", PROMPT_VERSION),
    )
    wins = make_windows(_sections())
    tier = s.llm.tiers["strong"]
    chars = [len(render(prompt, reg, w)) for w in wins]
    tin = sum(c / 3.5 for c in chars)
    usd = (
        tin / 1e6 * tier.usd_per_1m_input_tokens
        + len(wins) * max_out_tokens / 1e6 * tier.usd_per_1m_output_tokens
    )
    return {
        "windows": len(wins),
        "units": sum(len(w.units) for w in wins),
        "est_input_tokens": int(tin),
        "assumed_output_tokens_per_window": max_out_tokens,
        "est_usd": round(usd, 2),
        "model_tier": "strong (effort low)",
    }


def run(limit: int | None, max_usd: float, run_dir: Path = OUT) -> dict:
    s = get_settings()
    s.llm.stage_budgets_usd["erst"] = max_usd
    client = LLMClient(s, run_id=RUN_ID)
    reg, prompt = (
        ErstRegistry.load(),
        load_prompt(REPO_ROOT / "prompts", "erst_graph", PROMPT_VERSION),
    )
    schema = build_schema(reg)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "windows.jsonl"
    done = _done(path)
    todo = [w for w in make_windows(_sections()) if w.window_id not in done]
    if limit:
        todo = todo[:limit]
    stopped = None
    with path.open("a", encoding="utf-8") as f:
        for w in todo:
            try:
                res = client.parse(
                    task="erst_graph",
                    prompt_version=PROMPT_VERSION,
                    messages=[{"role": "user", "content": render(prompt, reg, w)}],
                    schema=schema,
                    model_tier="strong",
                    fixture_name="default",
                )
            except BudgetExceededError as e:
                stopped = str(e)
                break
            accepted, rejected = [], []
            for raw in res.output.model_dump()["edges"]:
                rec, why = convert(raw, w, reg)
                (accepted if rec else rejected).append(rec or {"reason": why, "raw": raw})
            f.write(
                json.dumps(
                    {
                        "window_id": w.window_id,
                        "section_id": w.section_id,
                        "first": w.first,
                        "n_units": len(w.units),
                        "input_hash": res.input_hash,
                        "usage": res.usage,
                        "accepted": accepted,
                        "rejected": rejected,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            f.flush()
    return {
        "windows_done_now": len(todo) if not stopped else None,
        "windows_total_done": len(_done(path)),
        "spend_usd": round(client.spent_usd, 4),
        "stopped_by_budget": stopped,
    }


def unit_pairs(edge: dict) -> list[tuple[int, int]]:
    """The unit-index pairs an edge links: nucleus-satellite, or every nucleus pair for a multinuclear relation."""
    n = [int(u[1:]) for u in edge["nucleus_units"]]
    if edge["satellite_unit"]:
        return [(x, int(edge["satellite_unit"][1:])) for x in n]
    return [(a, b) for i, a in enumerate(n) for b in n[i + 1 :]]


def freeze(run_dir: Path = OUT) -> dict:
    wins = _done(run_dir / "windows.jsonl")
    expected = {w.window_id for w in make_windows(_sections())}
    if set(wins) != expected:
        raise SystemExit(f"not complete: {len(wins)}/{len(expected)} windows")
    seen, edges, rej = set(), [], {}
    for wid in sorted(wins):
        for r in wins[wid]["accepted"]:
            e = r["edge"]
            key = (r["section_id"], e["label"], tuple(e["nucleus_units"]), e["satellite_unit"])
            if key in seen:  # overlap between windows
                continue
            seen.add(key)
            edges.append(r)
        for r in wins[wid]["rejected"]:
            rej[r["reason"].split(":")[0]] = rej.get(r["reason"].split(":")[0], 0) + 1
    edges.sort(key=lambda r: (r["section_id"], r["edge"]["label"], r["edge"]["nucleus_units"]))
    graph = {
        "kind": "eRST-compatible discourse relation graph (sentence units; not a complete eRST parse)",
        "edges": edges,
    }
    gp = run_dir / "graph.json"
    gp.write_text(json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")
    manifest = {
        "prompt_version": PROMPT_VERSION,
        "window": WINDOW,
        "stride": STRIDE,
        "windows": len(wins),
        "edges": len(edges),
        "rejected_by_reason": rej,
        "edges_by_label": {
            k: sum(r["edge"]["label"] == k for r in edges)
            for k in sorted({r["edge"]["label"] for r in edges})
        },
        "graph_sha256": hashlib.sha256(gp.read_bytes()).hexdigest(),
        "spend_usd": None,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["dry-run", "run", "freeze"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--max-usd", type=float, default=10.0)
    a = ap.parse_args()
    out = {"dry-run": lambda: dry_run(), "run": lambda: run(a.limit, a.max_usd), "freeze": freeze}[
        a.phase
    ]()
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
