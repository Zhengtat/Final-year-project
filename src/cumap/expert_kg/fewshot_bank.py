"""CR-009 §3.5 / §11: the few-shot bank and its validator. The bank's expected outputs must pass the same
checks the generator's output will face (F2 F3 F4 F5 F6 C3 M1 M2), so they never teach a flagged pattern."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from cumap.expert_kg.alias_rules import AliasConfig, r1_key
from cumap.expert_kg.partial_span import find_partial_spans, noun_form_lexicon

BANK_PATH = Path("configs/fewshot/concepts_v4_draft.yaml")
ROLES_NEW = {"defined", "used", "mentioned"}
ROLES_EXISTING = {"used", "mentioned", "refined", "defined"}
NOT_MENTION_REASONS = {"different_sense", "generic_use", "inside_longer_term"}
HINT_REASONS = {
    "different_sense",
    "generic_use",
    "inside_longer_term",
    "not_a_concept",
    "not_related_here",
}


def _n(s: str) -> str:
    return " ".join(s.split())


def load_bank(path: Path = BANK_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Problem:
    example: str
    rule: str
    detail: str


def _in(needle: str, hay: str) -> bool:
    return _n(needle).lower() in _n(hay).lower()


def validate_example(
    ex: dict, bank: dict, nlp, noun_forms: set[str], cfg: AliasConfig
) -> list[Problem]:
    P: list[Problem] = []
    eid = ex["id"]
    paras = {k: _n(v) for k, v in ex["paragraphs"].items()}
    order = list(paras)
    text = " ".join(paras.values())
    cards = {c["id"]: c for c in ex["cards"]}

    def card_forms(c: dict) -> list[str]:
        return [c["name"], *c.get("aliases", [])]

    exp = ex["expected"]
    anchor_types = set(bank["anchor_types"])
    items: list[tuple[str, list[str], str]] = []  # (label, spans, evidence)
    for m in exp["existing_mentions"]:
        c = cards.get(m["node_id"])
        if c is None:
            P.append(Problem(eid, "F4", f"existing mention of unknown node {m['node_id']}"))
            continue
        if m["surface"].lower() not in [f.lower() for f in card_forms(c)]:
            P.append(Problem(eid, "F4", f"surface {m['surface']!r} is not a form of {c['name']}"))
        if m["role"] == "defined" and c.get("def") not in (None, "—"):
            P.append(
                Problem(
                    eid,
                    "C4",
                    f"{c['name']} already has a definition ({c['def']}): role must be refined",
                )
            )
        if m["role"] not in ROLES_EXISTING:
            P.append(Problem(eid, "F1", f"bad role {m['role']}"))
        if m["para"] not in paras or not _in(m["evidence"], paras[m["para"]]):
            P.append(Problem(eid, "F2", f"evidence not verbatim in {m['para']}: {m['evidence']!r}"))
        if not _in(m["surface"], m["evidence"]):
            P.append(Problem(eid, "F3", f"surface {m['surface']!r} not in its evidence"))
        items.append((m["surface"], [m["surface"]], m["evidence"]))
    for nm in exp["not_mentions"]:
        if nm["node_id"] not in cards:
            P.append(Problem(eid, "F4", f"not-mention of unknown node {nm['node_id']}"))
        if nm["reason"] not in NOT_MENTION_REASONS:
            P.append(Problem(eid, "F1", f"bad not-mention reason {nm['reason']}"))
    recorded = {m["node_id"] for m in exp["existing_mentions"]} | {
        n["node_id"] for n in exp["not_mentions"]
    }
    for c in ex["cards"]:
        if c["in_text"] and c["id"] not in recorded:
            P.append(
                Problem(
                    eid, "M1", f"card {c['name']} is in the text but neither recorded nor rejected"
                )
            )
        if not c["in_text"] and c["id"] in {m["node_id"] for m in exp["existing_mentions"]}:
            P.append(
                Problem(
                    eid, "M1", f"card {c['name']} is marked not in text but recorded as a mention"
                )
            )
    for nc in exp["new_concepts"]:
        names = [nc["name"], *nc.get("aliases", [])]
        if nc["role"] not in ROLES_NEW:
            P.append(Problem(eid, "F1", f"bad role {nc['role']} for {nc['name']}"))
        if nc["para"] not in paras or not _in(nc["evidence"], paras[nc["para"]]):
            P.append(
                Problem(eid, "F2", f"evidence not verbatim in {nc['para']}: {nc['evidence']!r}")
            )
        if not any(_in(x, nc["evidence"]) for x in names):
            P.append(Problem(eid, "F3", f"{nc['name']} (or an alias) not inside its evidence"))
        for c in ex["cards"]:
            if r1_key(nc["name"], cfg) in {r1_key(f, cfg) for f in card_forms(c)}:
                P.append(
                    Problem(eid, "C3", f"new concept {nc['name']} duplicates card {c['name']}")
                )
        if nc["extraction_origin"] == "anchored":
            if not nc["anchors"]:
                P.append(Problem(eid, "F6", f"{nc['name']}: anchored without anchors"))
        elif nc["anchors"] or not nc.get("independence_check"):
            P.append(
                Problem(
                    eid, "F6", f"{nc['name']}: independent needs independence_check and no anchors"
                )
            )
        for a in nc["anchors"]:
            c = cards.get(a["node_id"])
            if c is None:
                P.append(Problem(eid, "F4", f"{nc['name']}: anchor to unknown node {a['node_id']}"))
                continue
            if a["anchor_type"] not in anchor_types:
                P.append(Problem(eid, "F1", f"bad anchor type {a['anchor_type']}"))
            if not _in(a["cue"], text):
                P.append(Problem(eid, "F2", f"{nc['name']}: cue not verbatim: {a['cue']!r}"))
            if not any(_in(x, a["cue"]) for x in names):
                P.append(Problem(eid, "F5", f"{nc['name']}: cue does not contain the new concept"))
            # the anchor node must be named in the cue, its paragraph, the paragraph before, or the new span
            pi = order.index(nc["para"]) if nc["para"] in order else 0
            scope = " ".join(paras[k] for k in order[max(0, pi - 1) : pi + 1]) + " " + nc["name"]
            if not any(_in(f, scope) or _in(f, a["cue"]) for f in card_forms(c)):
                P.append(
                    Problem(
                        eid,
                        "F5",
                        f"{nc['name']}: anchor node {c['name']} is not named near the cue",
                    )
                )
        items.append((nc["name"], names, nc["evidence"]))
    # M2: no item may be a partial span of a term-like longer candidate in its own evidence
    all_names = [x for _, spans, _ in items for x in spans]
    known = [f for c in ex["cards"] for f in card_forms(c)]
    for label, spans, ev in items:
        for fl in find_partial_spans(
            spans, ev, nlp, all_items=all_names, known_forms=known, noun_forms=noun_forms, cfg=cfg
        ):
            P.append(
                Problem(eid, "M2", f"{label!r} looks like the tail of {fl.longer!r} ({fl.why})")
            )
    if ex.get("corrective"):
        given = {g["hint_id"] for g in ex["given_items"]}
        resp = {r["hint_id"]: r for r in ex["hint_responses"]}
        if given != set(resp):
            P.append(Problem(eid, "F1", "every given item needs exactly one hint_response"))
        for r in resp.values():
            if r["decision"] == "rejected" and r["reason"] not in HINT_REASONS:
                P.append(Problem(eid, "F1", f"bad hint rejection reason {r['reason']}"))
    return P


def validate_bank(bank: dict, nlp, cfg: AliasConfig | None = None) -> list[Problem]:
    cfg = cfg or AliasConfig.load()
    noun_forms = noun_form_lexicon(
        [_n(v) for ex in bank["examples"] for v in ex["paragraphs"].values()], nlp
    )
    out: list[Problem] = []
    for ex in bank["examples"]:
        out += validate_example(ex, bank, nlp, noun_forms, cfg)
    return out


def passages(bank: dict) -> list[str]:
    return [_n(v) for ex in bank["examples"] for v in ex["paragraphs"].values()]


def overlaps_text(bank: dict, texts: list[str], n: int = 8) -> list[tuple[str, str]]:
    """Example passages sharing any run of `n` consecutive words with a section text (must be none)."""

    def grams(s: str) -> set[tuple[str, ...]]:
        w = re.findall(r"[a-z0-9]+", s.lower())
        return {tuple(w[i : i + n]) for i in range(len(w) - n + 1)}

    sec = [(i, grams(t)) for i, t in enumerate(texts)]
    hits = []
    for ex in bank["examples"]:
        for k, v in ex["paragraphs"].items():
            g = grams(_n(v))
            if any(g & sg for _, sg in sec):
                hits.append((ex["id"], k))
    return hits
