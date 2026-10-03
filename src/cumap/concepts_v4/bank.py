"""CR-009 §3.5: render the approved few-shot bank into the EXAMPLES block.

Modes: `full` (G1 and Pass B: the full expected output); `pass_a` (Pass A has no cards, so every item is shown as
a NEW independent concept and `refined` becomes `defined`); corrective rounds add example 7 (GIVEN ITEMS + the
hint_responses it earns). Order is fixed (Lu et al. 2022)."""

from __future__ import annotations

import json
from pathlib import Path

from cumap.expert_kg.fewshot_bank import load_bank

BANK_PATH = Path("configs/fewshot/concepts_v4_draft.yaml")


def _n(s: str) -> str:
    return " ".join(s.split())


def card_line(c: dict) -> str:
    """`n_0142 | cyclic redundancy check | aka: CRC | Mechanism | def §2.4 | in_text: yes | "gloss"`."""
    aka = ", ".join(c.get("aliases", [])) or "-"
    d = c.get("def") or "—"
    return f'{c["id"]} | {c["name"]} | aka: {aka} | {c["type"]} | def {d} | in_text: {"yes" if c["in_text"] else "no"} | "{c["gloss"]}"'


def _output_json(ex: dict, mode: str) -> dict:
    e = ex["expected"]
    if mode == "pass_a":
        new = [
            {
                **c,
                "extraction_origin": "independent",
                "anchors": [],
                "found_via_anchor": False,
                "independence_check": "No existing nodes were given, so nothing can be related to it.",
            }
            for c in e["new_concepts"]
        ]
        for m in e["existing_mentions"]:
            new.append(
                {
                    "name": m["surface"],
                    "aliases": [],
                    "node_type": m["node_type"],
                    "role": "defined" if m["role"] == "refined" else m["role"],
                    "evidence": m["evidence"],
                    "para": m["para"],
                    "extraction_origin": "independent",
                    "anchors": [],
                    "found_via_anchor": False,
                    "independence_check": "No existing nodes were given, so nothing can be related to it.",
                }
            )
        return {
            "existing_mentions": [],
            "not_mentions": [],
            "new_concepts": new,
            "hint_responses": [],
        }
    return {
        "existing_mentions": e["existing_mentions"],
        "not_mentions": e["not_mentions"],
        "new_concepts": e["new_concepts"],
        "hint_responses": ex.get("hint_responses", []),
    }


def render_examples(bank: dict, mode: str = "full", corrective: bool = False) -> str:
    out = []
    k = 0
    for ex in bank["examples"]:
        if ex.get("corrective") and not (corrective and mode == "full"):
            continue
        k += 1
        lines = [f"--- Example {k} ({ex['domain']}) ---"]
        if mode == "full":
            lines.append(
                "EXISTING NODES:\n"
                + ("\n".join(card_line(c) for c in ex["cards"]) or "(none: no known nodes yet)")
            )
            if ex.get("look_alikes"):
                lines.append(
                    "LOOK-ALIKES (never the same):\n"
                    + "\n".join(f"{a['a']} / {a['b']}: {a['why']}" for a in ex["look_alikes"])
                )
        lines.append("TEXT:\n" + "\n".join(f"{p}: {_n(t)}" for p, t in ex["paragraphs"].items()))
        if ex.get("corrective"):
            lines.append(
                "CORRECTIONS (GIVEN ITEMS):\n"
                + "\n".join(
                    f"{g['hint_id']} | {g['type']} | {g['text']} | {g['detail']}"
                    for g in ex["given_items"]
                )
            )
        lines.append("OUTPUT:\n" + json.dumps(_output_json(ex, mode), ensure_ascii=False))
        out.append("\n".join(lines))
    return "\n\n".join(out)


def load(path: Path = BANK_PATH) -> dict:
    return load_bank(path)


def example_cards(ex: dict):
    """Bank example cards as Card objects (for running the verifier over the bank's own outputs)."""
    from cumap.concepts_v4.cards import Card, Node

    cards = []
    for c in ex["cards"]:
        d = c.get("def")
        n = Node(
            id=c["id"],
            name=c["name"],
            aliases=list(c.get("aliases", [])),
            node_type=c["type"],
            first_section="x",
            first_order=0,
            definition=c["gloss"],
            def_section=None if d in (None, "—") else d.lstrip("§"),
            gloss=c["gloss"],
        )
        cards.append(Card(n, bool(c["in_text"])))
    return cards
