"""CR-009 §7.1: the comparison arms, re-implemented on OUR benchmark (same IIR sections, gold, scorer, exact micro
F1). All are `selection_eligible: false`: reported, never selected. SAC-KG-style and PiVe-style arms are NOT
reproductions: PiVe's verifier is a trained model (ours gives rule hints) and SAC-KG extracts triples around a root
entity (only its checks and pruner are carried over here).

  C-SAC       v3 prompt, no cards; SAC-KG's own checks only (Q1, F2/F3 format): <= 3 flagged items are deleted,
              more -> regenerate ONCE with error-type instructions; no coverage hints, no loop; P1 label at tau 0.5
              (P2 is not built), leave-one-chapter-out.
  C-PiVe      v3 prompt, no cards; missing-item hints only (M2 longer spans, M4 missed candidates; M1 needs cards);
              the given items are ADDED OUTRIGHT (the generator cannot reject them) and accumulate; regenerate,
              <= 3 iterations, stop when no hints remain.
  C-PiVe-off  the same hints applied OFFLINE (added to iteration 0's output, no re-prompt): a $0 replay.
  C-ConExion  ConExion's published best setup (few-shot 1-random): their prompt, one random IIR DEV section with its
              FACE labels as the example (fixed seed, never the section itself), our bulk model, and their filter
              that keeps only concepts present in the text. Structured output (a list) replaces comma text."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict

from cumap.concepts_v4.pruner import norm
from cumap.concepts_v4.verifier import span_in_quote
from cumap.expert_kg.alias_rules import AliasConfig, find_abbreviations
from cumap.expert_kg.concepts import extract_concepts_for_section
from cumap.expert_kg.stats import extract_candidate_terms
from cumap.llm.client import BudgetExceededError, LLMClient
from cumap.llm.prompts import PromptTemplate, load_prompt
from cumap.schemas.relations import RelationRegistry

SELECTION_ELIGIBLE = False
CORRECTION_TMPL = {
    "Q1": "Your list looks too short for this text. Read the section again and add every further domain concept it names.",
    "F3": "These items' names are not inside their evidence quotes: {items}. Use a quote that contains the name, or correct the name.",
}


class KeyphrasesLLM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keyphrases: list[str]


def derived_prompt(base: PromptTemplate) -> PromptTemplate:
    """The v3 (v2-file) prompt with an optional trailing {corrections} block, so a corrective round can be added
    without editing the frozen prompt file (a distinct version label keeps the cache keys apart)."""
    return PromptTemplate(
        base.task, base.version + "+corr", base.schema, base.notes, base.body + "\n\n{corrections}"
    )


@dataclass
class ArmSection:
    section_id: str
    items: list[dict] = field(default_factory=list)
    iteration0: list[dict] = field(default_factory=list)
    hints: list[dict] = field(default_factory=list)
    calls: int = 0
    note: str = ""


def _gen(
    client, prompt, registry, nlp, sec: dict, corrections: str = "", fixture: str = "default"
) -> list[dict]:
    out = extract_concepts_for_section(
        client,
        prompt,
        None,
        registry,
        section_id=sec["section_id"],
        section_text=sec["text"],
        heading_path=[sec.get("heading") or sec["section_id"]],
        candidate_terms=extract_candidate_terms(sec["text"], nlp),
        domain="information retrieval",
        fixture_name=fixture,
        include_gleaning=False,
        extra_vars={"corrections": corrections},
    )
    return [
        {
            "canonical_name": m.canonical_name,
            "node_type": m.node_type,
            "role": m.role,
            "evidence_quote": m.evidence_quote,
            "definition": m.definition,
            "source": "llm",
        }
        for m in out.mentions
    ]


# ---------------------------------------------------------------- C-SAC
def sac_flags(items: list[dict], text: str, rho: float = 1.5) -> tuple[list[int], bool]:
    """SAC-KG-style checks only: quantity (Q1) and format (the name inside its quote; verbatim quotes are
    already enforced by the extractor). Returns (flagged item indexes, quantity_insufficient)."""
    bad = [
        i
        for i, it in enumerate(items)
        if not span_in_quote(it["canonical_name"], it["evidence_quote"])
    ]
    return bad, len(items) < max(3, rho * len(text.split()) / 100)


def run_c_sac(
    client: LLMClient,
    base: PromptTemplate,
    registry: RelationRegistry,
    nlp,
    sections: list[dict],
    pruner_for=None,
    tau: float = 0.5,
    progress=print,
) -> list[ArmSection]:
    prompt, res = derived_prompt(base), []
    for sec in sections:
        s = ArmSection(sec["section_id"])
        items = _gen(client, prompt, registry, nlp, sec)
        s.calls, s.iteration0 = 1, list(items)
        bad, q1 = sac_flags(items, sec["text"])
        if (
            len(bad) > 3 or q1
        ):  # more than the threshold -> regenerate once with the error-type instructions
            lines = []
            if q1:
                lines.append(CORRECTION_TMPL["Q1"])
            if bad:
                lines.append(
                    CORRECTION_TMPL["F3"].format(
                        items="; ".join(items[i]["canonical_name"] for i in bad[:6])
                    )
                )
            items = _gen(
                client, prompt, registry, nlp, sec, corrections="CORRECTIONS: " + " ".join(lines)
            )
            s.calls += 1
            bad, _ = sac_flags(items, sec["text"])
        items = [
            it for i, it in enumerate(items) if i not in set(bad)
        ]  # fewer than the threshold -> delete
        if pruner_for is not None:
            pr = pruner_for(sec["chapter_num"])
            items = [it for it in items if pr(it["canonical_name"]) >= tau]
        s.items = items
        res.append(s)
        progress(f"C-SAC {sec['section_id']}: {s.calls} calls, {len(items)} items")
    return res


# ---------------------------------------------------------------- C-PiVe / C-PiVe-off
def pive_hints(items: list[dict], sec: dict, recurring=None, nlp=None) -> list[dict]:
    """Missing-item hints available WITHOUT cards: M2 longer spans (a term-like longer candidate) and M4 missed
    candidates (an R2 long form or a definition pattern no item covers). M1 needs cards, so it does not apply."""
    from cumap.concepts_v4.verifier import _DEF_PATTERNS, _covered
    from cumap.expert_kg.partial_span import find_partial_spans

    cfg, text, hints, names = (
        AliasConfig.load(),
        sec["text"],
        [],
        [it["canonical_name"] for it in items],
    )
    for it in items:
        for fl in find_partial_spans(
            [it["canonical_name"]], it["evidence_quote"], nlp, all_items=names, recurring=recurring
        ):
            hints.append({"kind": "longer_span", "text": fl.longer, "quote": it["evidence_quote"]})
    out = {"new_concepts": [{"name": n, "aliases": []} for n in names], "existing_mentions": []}
    cands = {}
    for p in _DEF_PATTERNS:
        for m in p.finditer(text):
            cands.setdefault(" ".join(m.group(1).lower().split()), m.group(0))
    for ab in find_abbreviations(text, cfg):
        cands.setdefault(" ".join(ab.long_form.lower().split()), ab.sentence)
    for term, ev in cands.items():
        if len(term.split()) <= 4 and not _covered(term, out, cfg):
            hints.append({"kind": "missed_candidate", "text": term, "quote": ev})
    seen, uniq = set(), []
    for h in hints:
        if (h["kind"], norm(h["text"])) not in seen:
            seen.add((h["kind"], norm(h["text"])))
            uniq.append(h)
    return uniq


def _add_outright(items: list[dict], hints: list[dict], text: str) -> list[dict]:
    out = list(items)
    have = {norm(i["canonical_name"]) for i in out}
    for h in hints:
        if norm(h["text"]) in have:
            continue
        ev = (
            h["quote"]
            if h["quote"] in text
            else next(
                (s for s in re.split(r"(?<=[.!?])\s+", text) if norm(h["text"]) in norm(s)), ""
            )
        )
        if not ev:
            continue
        out.append(
            {
                "canonical_name": h["text"],
                "node_type": "Concept",
                "role": "used",
                "evidence_quote": ev,
                "definition": None,
                "source": "hint",
            }
        )
        have.add(norm(h["text"]))
    return out


def run_c_pive(
    client: LLMClient,
    base: PromptTemplate,
    registry,
    nlp,
    sections: list[dict],
    recurring_by_chapter=None,
    max_iterations: int = 3,
    progress=print,
) -> tuple[list[ArmSection], list[ArmSection]]:
    """Returns (C-PiVe online, C-PiVe-off offline). The offline arm reuses iteration 0 ($0)."""
    prompt, online, offline = derived_prompt(base), [], []
    for sec in sections:
        rec = (recurring_by_chapter or {}).get(str(sec["chapter_num"]))
        items0 = _gen(client, prompt, registry, nlp, sec)
        s_on, s_off = (
            ArmSection(sec["section_id"], iteration0=list(items0), calls=1),
            ArmSection(sec["section_id"], iteration0=list(items0), calls=1),
        )
        hints = pive_hints(items0, sec, rec, nlp)
        s_off.items, s_off.hints = _add_outright(items0, hints, sec["text"]), list(hints)
        given: dict[tuple[str, str], dict] = {}
        items = items0
        for _it in range(max_iterations):
            new = [
                h
                for h in pive_hints(items, sec, rec, nlp)
                if (h["kind"], norm(h["text"])) not in given
            ]
            if not new:
                break
            for h in new:
                given[(h["kind"], norm(h["text"]))] = h
            block = (
                "CORRECTIONS: Extract the concepts again, and also add the given items:\n"
                + "\n".join(f"- {h['text']} ({h['kind']})" for h in given.values())
            )
            items = _gen(client, prompt, registry, nlp, sec, corrections=block)
            s_on.calls += 1
        s_on.items, s_on.hints = (
            _add_outright(items, list(given.values()), sec["text"]),
            list(given.values()),
        )
        online.append(s_on)
        offline.append(s_off)
        progress(
            f"C-PiVe {sec['section_id']}: {s_on.calls} calls, {len(s_on.items)} items (offline {len(s_off.items)})"
        )
    return online, offline


# ---------------------------------------------------------------- C-ConExion
CONEXION_USER = "I have the following document:\n{doc}\n\nPlease give me the keyphrases that are present in this document and separate them with commas:"


def pick_example(sections: list[dict], target: dict, seed: int = 11) -> dict:
    """A random IIR DEV section, fixed seed, never the section being extracted (and never a test section)."""
    pool = [s for s in sections if s["section_id"] != target["section_id"]]
    return random.Random(f"{seed}:{target['section_id']}").choice(pool)


def conexion_filter(raw: list[str], text: str) -> list[str]:
    """ConExion's post-processing: split on delimiters, keep only concepts present in the document (exact lexical match)."""
    parts = []
    for r in raw:
        parts += [p.strip(" *-\t") for p in re.split(r"[,;*\n]", r)]
    low = " ".join(text.lower().split())
    seen, out = set(), []
    for p in parts:
        k = " ".join(p.lower().split())
        if k and k in low and k not in seen:
            seen.add(k)
            out.append(p)
    return out


def run_c_conexion(
    client: LLMClient,
    sections: list[dict],
    gold_names_by_section: dict[str, list[str]],
    progress=print,
) -> list[ArmSection]:
    res = []
    for sec in sections:
        ex = pick_example(sections, sec)
        messages = [
            {"role": "user", "content": CONEXION_USER.format(doc=ex["text"])},
            {
                "role": "assistant",
                "content": ", ".join(gold_names_by_section.get(ex["section_id"], [])),
            },
            {"role": "user", "content": CONEXION_USER.format(doc=sec["text"])},
        ]
        r = client.parse(
            task="conexion_baseline",
            prompt_version="conexion-fs1r",
            messages=messages,
            schema=KeyphrasesLLM,
            model_tier="bulk",
            allow_escalation=False,
        )
        kept = conexion_filter(r.output.keyphrases, sec["text"])
        s = ArmSection(
            sec["section_id"],
            calls=1,
            items=[
                {
                    "canonical_name": k,
                    "role": "used",
                    "node_type": "Concept",
                    "evidence_quote": "",
                    "source": "conexion",
                }
                for k in kept
            ],
        )
        res.append(s)
        progress(
            f"C-ConExion {sec['section_id']}: {len(r.output.keyphrases)} raw, {len(kept)} kept"
        )
    return res


def conexion_prf(keyphrases: list[str], references: list[str]) -> tuple[float, float, float]:
    """ConExion's own scorer (`evaluate_p_r_f` in their repo): exact set intersection, per document."""
    k, r = set(keyphrases), set(references)
    p = len(k & r) / len(k) if k else 0.0
    rc = len(k & r) / len(r) if r else 0.0
    f = 2 * p * rc / (p + rc) if p + rc > 0 else 0.0
    return p, rc, f


def finals_of(arm: list[ArmSection]) -> dict[str, list[dict]]:
    return {s.section_id: s.items for s in arm}


__all__ = ["BudgetExceededError", "load_prompt"]
