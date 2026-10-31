"""CR-064: background context for the relation choice (profile key `choice_context`).

The relation choice normally sees only the two concept names and the one sentence they share. Two opt-in modes add a short background
line per concept, used only to judge what the concept is (its role); the relation must still be stated in the sentence and the
evidence quote must still come from it (the code checks stay unchanged):

- `origin`: the sentence the concept was first introduced in (its first `defined` mention, expanded to the whole sentence).
- `neighbours`: the concept's other relations in a graph built earlier (a frozen first pass over the same document), one hop, each
  written with the registry template. The pair's own edge is left out so the model never sees its earlier answer. Needs a
  `choice_context_graph.json` sidecar in the run directory (written by `cumap.cr064.arm_relations`).

No gold, no node types and no model call here; the default (`none`) leaves every earlier run unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

from cumap.expert_kg.canonicalize import RegisteredConcept
from cumap.expert_kg.relations import split_sentences
from cumap.schemas.relations import RelationRegistry

CONTEXTS = ("none", "origin", "neighbours")
PROMPT_FOR = {"origin": "v11", "neighbours": "v12"}  # relation_choice version each mode needs
GRAPH_FILE = "choice_context_graph.json"
MAX_NEIGHBOURS = 8
MAX_CHARS = 500
NONE_TEXT = "(none available)"


def resolve_choice_context(value: str | None = None) -> str:
    """Explicit value, else the active benchmark profile's `choice_context`, else `none`."""
    if value is None:
        from cumap.cr012.schema_profile import active_profile

        p = active_profile()
        value = (p.raw.get("choice_context") if p else None) or "none"
    if value not in CONTEXTS:
        raise ValueError(f"choice_context must be one of {CONTEXTS}, not {value!r}")
    return value


def _norm(s: str) -> str:
    return " ".join(s.split())


def _clip(s: str) -> str:
    return s if len(s) <= MAX_CHARS else s[: MAX_CHARS - 1].rstrip() + "…"


_ABBREV = ("et al.", "e.g.", "i.e.", "vs.", "Fig.", "Eq.", "Sec.")


def _context_sentences(text: str) -> list[str]:
    """`split_sentences`, with a piece that ends in a common abbreviation joined to the next one (the plain splitter cuts at "et al.")."""
    out: list[str] = []
    for s in split_sentences(text):
        if out and out[-1].endswith(_ABBREV):
            out[-1] = f"{out[-1]} {s}"
        else:
            out.append(s)
    return out


def origin_sentence(concept: RegisteredConcept, sections: dict[str, str]) -> str | None:
    """The sentence of the concept's first `defined` mention (else its first model-written mention); the quote itself if it spans sentences."""
    own = [m for m in concept.mentions if m.source == "llm" and m.quote]
    if not own:
        return None
    m = next((x for x in own if x.role == "defined"), own[0])
    q = _norm(m.quote)
    for s in _context_sentences(sections.get(m.section_id, "")):
        if q in _norm(s):
            return _clip(_norm(s))
    return _clip(q)


def graph_from_results(results: list[dict]) -> list[dict]:
    """Edges of a finished relation stage as {src, relation, tgt} (concept ids), from its selected pairs that became edges."""
    out = []
    for r in results:
        if r.get("outcome") != "edge" or r.get("group", "selected") != "selected":
            continue
        x, y = r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]
        src, tgt = (y, x) if r.get("direction") == "reversed" else (x, y)
        out.append({"src": src, "relation": r["relation"], "tgt": tgt})
    return out


def load_graph(run_dir: Path) -> list[dict]:
    p = run_dir / GRAPH_FILE
    if not p.exists():
        raise FileNotFoundError(
            f"choice_context neighbours needs {p} (write it from a finished first pass)"
        )
    return json.loads(p.read_text(encoding="utf-8"))["edges"]


def neighbour_lines(
    concept_id: str,
    partner_id: str,
    edges: list[dict],
    names: dict[str, str],
    templates: dict[str, str],
) -> list[str]:
    """One-hop readings of the concept's other edges (not the edge to its partner), sorted, deduplicated and capped."""
    lines = set()
    for e in edges:
        a, b = e["src"], e["tgt"]
        if concept_id not in (a, b) or partner_id in (a, b) or a not in names or b not in names:
            continue
        tpl = templates.get(e["relation"], "{X} " + e["relation"] + " {Y}")
        lines.add(tpl.replace("{X}", names[a]).replace("{Y}", names[b]))
    return sorted(lines)[:MAX_NEIGHBOURS]


def build_context_fn(
    mode: str,
    concepts: dict[str, RegisteredConcept],
    registry: RelationRegistry,
    *,
    sections: dict[str, str] | None = None,
    edges: list[dict] | None = None,
):
    """pair -> {"context_x": ..., "context_y": ...} for the prompt, or None when the mode is `none`."""
    if mode == "none":
        return None
    names = {cid: c.canonical_name for cid, c in concepts.items()}
    templates = {r.name: r.template for r in registry.all_relations()}

    def one(cid: str, partner: str, sentence: str) -> str:
        if mode == "origin":
            s = origin_sentence(concepts[cid], sections or {})
            if not s:
                return NONE_TEXT
            return "(introduced in the sentence above)" if _norm(s) == _norm(sentence) else s
        lines = neighbour_lines(cid, partner, edges or [], names, templates)
        return "\n".join(f"  - {x}" for x in lines) if lines else NONE_TEXT

    def fn(pair) -> dict[str, str]:
        x, y = pair.concept_x_id, pair.concept_y_id
        return {"context_x": one(x, y, pair.sentence), "context_y": one(y, x, pair.sentence)}

    return fn
