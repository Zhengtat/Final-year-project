"""CR-008 §5: the textbook misconception layer.

Refutation passages ("a common mistake is...", "X is not Y", "should not be confused with") become
WRONG edges in a separate `misconception` layer, each linked to the correct expert edge it
contradicts, with verbatim quotes. The layer is never mixed into the expert graph: it is stored in
`checkpoint.misconceptions`, never in `relation_results_v3`, so expert-edge precision, importance,
pair selection, prerequisites, fusion and expected subgraphs cannot see it. The only exception is a
*proposed correct edge* that passes the relation verifier: it enters the expert layer as an
ordinary textbook edge (`found_by: misconception_stage`).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, create_model

from cumap.expert_kg.alias_rules import r1_key
from cumap.expert_kg.canonicalize import RegisteredConcept
from cumap.expert_kg.lexicon import Lexicon
from cumap.expert_kg.mentions import MentionMatcher
from cumap.expert_kg.relations import CandidatePair, concept_vocab
from cumap.gold.validate import verify_quote
from cumap.llm.client import LLMClient
from cumap.llm.prompts import PromptTemplate
from cumap.schemas.relations import RelationRegistry

CUES_PATH = Path("configs/misconception_cues.yaml")
CONFLATED = "conflated_with"  # misconception layer only
PERTURBATIONS = (
    "polarity_flip",
    "reversed",
    "substituted_concept",
    "conflation",
    "wrong_category",
    "wrong_relation",
    "condition_error",
    "modality_error",
)
PREVALENCE = ("stated_common", "stated_possible", "none")
FAMILIES = ("explicit_error", "tempting_belief", "confusion", "negated_identity")


# ---------------------------------------------------------------- 5.2 cue scan ($0)
@dataclass
class Candidate:
    section_id: str
    sentence: str
    paragraph: str
    families: list[str] = field(default_factory=list)
    lexicon_pair: tuple[str, str] | None = None


def _sentences(par: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", par) if s.strip()]


def scan_cues(
    sections: list[tuple[str, str]], lexicon: Lexicon | None = None, cues_path: Path = CUES_PATH
) -> list[Candidate]:
    """Families 1-4 by regex, plus family 5 (approved lexicon `different` pairs co-mentioned in one
    sentence). `sections` = [(section_id, text)]. One Candidate per distinct sentence."""
    cues = {
        f: [re.compile(p, re.IGNORECASE) for p in ps]
        for f, ps in yaml.safe_load(cues_path.read_text())["families"].items()
    }
    pairs = []
    if lexicon is not None:
        for e in lexicon.approved("different"):
            fs = list(e.forms)
            pairs += [(a, b) for i, a in enumerate(fs) for b in fs[i + 1 :]]
    out: dict[tuple[str, str], Candidate] = {}
    for sid, text in sections:
        for par in re.split(r"\n\s*\n", text):
            for sent in _sentences(par):
                fams = [f for f, pats in cues.items() if any(p.search(sent) for p in pats)]
                lp = next(
                    (
                        (a, b)
                        for a, b in pairs
                        if re.search(
                            rf"(?<![A-Za-z0-9]){re.escape(a)}s?(?![A-Za-z0-9])", sent, re.I
                        )
                        and re.search(
                            rf"(?<![A-Za-z0-9]){re.escape(b)}s?(?![A-Za-z0-9])", sent, re.I
                        )
                    ),
                    None,
                )
                if lp:
                    fams.append("lexicon_different")
                if fams:
                    key = (sid, " ".join(sent.split()))
                    cand = out.setdefault(key, Candidate(sid, sent, " ".join(par.split()), [], lp))
                    cand.families = sorted({*cand.families, *fams})
    return list(out.values())


# ---------------------------------------------------------------- LLM schema (rule 12: closed choice)
def build_misconception_llm(registry: RelationRegistry) -> type[BaseModel]:
    rels = tuple(r.name for r in registry.all_relations()) + (CONFLATED,)
    return create_model(
        "MisconceptionLLM",
        __config__=ConfigDict(extra="forbid"),
        is_warning=(bool, ...),
        reason=(str, ...),
        intuition=(str | None, ...),
        wrong_source=(str | None, ...),
        wrong_relation=(Literal[*rels] | None, ...),
        wrong_target=(str | None, ...),
        wrong_polarity=(Literal["affirmed", "negated"] | None, ...),
        wrong_modality=(
            Literal["necessary", "always", "typically", "possible", "never"] | None,
            ...,
        ),
        wrong_conditions=(list[str], ...),
        perturbation_type=(Literal[*PERTURBATIONS] | None, ...),
        prevalence_cue=(Literal[*PREVALENCE], ...),
        misconception_quote=(str | None, ...),
        correction_quote=(str | None, ...),
        contradicts=(list[str], ...),
        proposed_correct=(bool, ...),
        pce_source=(str | None, ...),
        pce_relation=(Literal[*rels] | None, ...),
        pce_target=(str | None, ...),
        pce_polarity=(Literal["affirmed", "negated"] | None, ...),
        pce_quote=(str | None, ...),
    )


# ---------------------------------------------------------------- prompt context
def edge_id(pair_id: str) -> str:
    return f"E:{pair_id}"


def expert_edges(results: list[dict]) -> dict[str, dict]:
    """Primary expert edges only (never consolidated duplicates, rejected or gated ones)."""
    out: dict[str, dict] = {}
    for r in results:
        if (
            r["outcome"] == "edge"
            and not r.get("gated_dropped")
            and not r.get("consolidated_into")
            and r.get("group", "selected") == "selected"
        ):
            out[edge_id(r["pair"]["pair_id"])] = r
    return out


def _edge_triple(r: dict) -> tuple[str, str, str, str]:
    x, y = r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]
    src, tgt = (y, x) if r["direction"] == "reversed" else (x, y)
    return src, r["relation"], tgt, (r.get("qualifiers") or {}).get("polarity", "affirmed")


def build_context(
    cand: Candidate,
    concepts: list[dict],
    matcher: MentionMatcher,
    edges: dict[str, dict],
    registry: RelationRegistry,
    lexicon: Lexicon | None,
    max_edges: int = 25,
) -> dict:
    by_id = {c["concept_id"]: c for c in concepts}
    ids = {m.concept_id for m in matcher.find(cand.paragraph)}
    cards = [by_id[i] for i in sorted(ids) if i in by_id]
    shown = {c["concept_id"] for c in cards}
    para_l = cand.paragraph.lower()
    sel = {}
    for eid, r in edges.items():
        s, _rel, t, _p = _edge_triple(r)
        in_par = " ".join(r["evidence_quote"].split()).lower() in para_l
        if in_par or (s in shown and t in shown):
            sel[eid] = r
    # fall back to edges touching any shown node when nothing else qualifies
    if not sel:
        sel = {e: r for e, r in edges.items() if {_edge_triple(r)[0], _edge_triple(r)[2]} & shown}
    sel = dict(list(sel.items())[:max_edges])
    for r in sel.values():  # endpoints of shown edges are shown too
        for i in (_edge_triple(r)[0], _edge_triple(r)[2]):
            if i in by_id and i not in shown:
                cards.append(by_id[i])
                shown.add(i)
    return {
        "cards": cards,
        "shown": shown,
        "edges": sel,
        "by_id": by_id,
        "lex": _lexicon_links(cards, lexicon),
    }


def _lexicon_links(cards: list[dict], lexicon: Lexicon | None) -> dict[str, dict]:
    """Approved `different` entries whose two sides are both shown nodes: a conflation can contradict
    one of these (CR-008 §5.4). id `L:<entry id>`; nodes = the two node ids."""
    if lexicon is None:
        return {}
    key_to: dict[str, str] = {}
    for c in cards:
        for f in (c["canonical_name"], *c.get("aliases", [])):
            key_to.setdefault(r1_key(f, lexicon.cfg), c["concept_id"])
    out: dict[str, dict] = {}
    for e in lexicon.approved("different"):
        ids = [key_to.get(r1_key(f, lexicon.cfg)) for f in e.forms]
        if len(e.forms) == 2 and all(ids) and ids[0] != ids[1]:
            out[f"L:{e.id}"] = {"entry": e, "nodes": (ids[0], ids[1])}
    return out


def _render_cards(cards: list[dict]) -> str:
    return (
        "\n".join(
            f"{c['concept_id']} | {c['canonical_name']} | {c['node_type']} | "
            f"{', '.join(c.get('aliases', [])) or '-'} | {(c.get('definition') or '-')[:140]}"
            for c in cards
        )
        or "(none)"
    )


def _render_edges(edges: dict[str, dict], by_id: dict[str, dict], lex: dict | None = None) -> str:
    lines = []
    for lid, v in (lex or {}).items():
        e = v["entry"]
        lines.append(
            f"{lid} | {e.forms[0]} / {e.forms[1]} are DIFFERENT things | {e.kind} | {e.why}"
        )
    for eid, r in edges.items():
        s, rel, t, pol = _edge_triple(r)
        lines.append(
            f"{eid} | {by_id[s]['canonical_name']} ({s}) -> {rel} -> {by_id[t]['canonical_name']} ({t}) | {pol} | {r['statement']}"
        )
    return "\n".join(lines) or "(none)"


def relation_templates(registry: RelationRegistry) -> str:
    lines = [
        f"- {r.name}: {registry.template_for(r.name, 'X', 'Y')}" for r in registry.all_relations()
    ]
    lines.append(
        f"- {CONFLATED}: X and Y are believed to be the same thing (misconception layer only)"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------- 5.4 checks ($0)
def _same_triple(a: tuple, b: tuple, symmetric: bool) -> bool:
    return a[1] == b[1] and (
        (a[0], a[2]) == (b[0], b[2]) or (symmetric and (a[0], a[2]) == (b[2], b[0]))
    )


def consistent(
    ptype: str,
    wrong: dict,
    ce: dict,
    registry: RelationRegistry,
    lexicon: Lexicon | None,
    names: dict[str, str],
) -> bool:
    """Is `wrong` a `ptype` perturbation of the correct edge `ce`? Both: {src, rel, tgt, pol, mod, cond}."""
    sym = ce["rel"] in registry and registry.get(ce["rel"]).symmetric
    same_t = _same_triple(
        (wrong["src"], wrong["rel"], wrong["tgt"]), (ce["src"], ce["rel"], ce["tgt"]), sym
    )
    if ptype == "polarity_flip":
        return same_t and wrong["pol"] != ce["pol"]
    if ptype == "reversed":
        directional = ce["rel"] in registry and registry.get(ce["rel"]).directional
        return (
            directional
            and wrong["rel"] == ce["rel"]
            and (wrong["src"], wrong["tgt"]) == (ce["tgt"], ce["src"])
        )
    if ptype == "substituted_concept":
        return (
            wrong["rel"] == ce["rel"]
            and not same_t
            and ((wrong["src"] == ce["src"]) != (wrong["tgt"] == ce["tgt"]))
        )
    if ptype == "conflation":
        if wrong["rel"] != CONFLATED:
            return False
        ends = {wrong["src"], wrong["tgt"]}
        if ce["rel"] == "contrasts_with" and {ce["src"], ce["tgt"]} == ends:
            return True
        return bool(lexicon and lexicon.is_different(names[wrong["src"]], names[wrong["tgt"]]))
    if ptype == "wrong_category":
        return (
            wrong["rel"] == ce["rel"] == "is_a"
            and wrong["src"] == ce["src"]
            and wrong["tgt"] != ce["tgt"]
        )
    if ptype == "wrong_relation":
        return {wrong["src"], wrong["tgt"]} == {ce["src"], ce["tgt"]} and wrong["rel"] != ce["rel"]
    if ptype == "condition_error":
        return same_t and sorted(wrong["cond"]) != sorted(ce["cond"])
    if ptype == "modality_error":
        return same_t and wrong["mod"] != ce["mod"]
    return False


def check_item(
    out, ctx: dict, text_by_section: str, registry: RelationRegistry, lexicon: Lexicon | None
) -> list[str]:
    """Basics + perturbation consistency. Returns a list of failure messages (empty = pass)."""
    errs: list[str] = []
    shown, edges, by_id = ctx["shown"], ctx["edges"], ctx["by_id"]
    for fld in ("misconception_quote", "correction_quote"):
        q = getattr(out, fld)
        if not q or not verify_quote(q, text_by_section):
            errs.append(f"{fld} is not a verbatim substring of the section")
    for fld in ("wrong_source", "wrong_target"):
        if getattr(out, fld) not in shown:
            errs.append(f"{fld} is not one of the shown expert nodes")
    if not (out.wrong_relation and out.perturbation_type and out.wrong_polarity):
        errs.append("wrong_relation, wrong_polarity and perturbation_type are required")
    if out.wrong_relation == CONFLATED and out.perturbation_type != "conflation":
        errs.append("conflated_with is only valid for perturbation_type conflation")
    if out.perturbation_type == "conflation" and out.wrong_relation != CONFLATED:
        errs.append("a conflation uses the relation conflated_with")
    if not out.contradicts and not out.proposed_correct:
        errs.append("contradicts is required (or propose the correct edge)")
    lex = ctx.get("lex", {})
    bad = [e for e in out.contradicts if e not in edges and e not in lex]
    if bad:
        errs.append(f"contradicts names edges that were not shown: {bad}")
    if errs or not out.contradicts:
        return errs
    wrong = {
        "src": out.wrong_source,
        "rel": out.wrong_relation,
        "tgt": out.wrong_target,
        "pol": out.wrong_polarity,
        "mod": out.wrong_modality,
        "cond": out.wrong_conditions,
    }
    names = {i: c["canonical_name"] for i, c in by_id.items()}
    oks, same_as = [], []
    for eid in out.contradicts:
        if (
            eid in lex
        ):  # a lexicon `different` entry only supports a conflation of exactly its two nodes
            oks.append(
                out.perturbation_type == "conflation"
                and {wrong["src"], wrong["tgt"]} == set(lex[eid]["nodes"])
            )
            continue
        r = edges[eid]
        s, rel, t, pol = _edge_triple(r)
        q = r.get("qualifiers") or {}
        ce = {
            "src": s,
            "rel": rel,
            "tgt": t,
            "pol": pol,
            "mod": q.get("modality"),
            "cond": q.get("conditions") or [],
        }
        if (
            wrong["src"],
            wrong["rel"],
            wrong["tgt"],
            wrong["pol"],
            wrong["mod"],
            sorted(wrong["cond"]),
        ) == (ce["src"], ce["rel"], ce["tgt"], ce["pol"], ce["mod"], sorted(ce["cond"])):
            same_as.append(eid)
        oks.append(consistent(out.perturbation_type, wrong, ce, registry, lexicon, names))
    if same_as:
        errs.append(f"the wrong edge is identical to the edge it contradicts: {same_as}")
    if not any(oks):
        errs.append(f"the wrong edge is not a {out.perturbation_type} of any contradicted edge")
    return errs


# ---------------------------------------------------------------- stage
USD_PER_CALL = (3500 * 2.0 + 1500 * 10.0) / 1e6


def preflight(cands: list[Candidate]) -> dict:
    return {"candidates": len(cands), "est_usd": round(len(cands) * USD_PER_CALL, 3)}


def _item(out, cand: Candidate, run_text: str, ctx: dict) -> dict:
    return {
        "item_id": f"M-{cand.section_id}-{int(hashlib.sha1(cand.sentence.encode()).hexdigest(), 16) % 10**6:06d}",
        "layer": "misconception",
        "origin": "textbook_warning",
        "status": "proposed",
        "section_id": cand.section_id,
        "cue_families": cand.families,
        "source_id": out.wrong_source,
        "relation": out.wrong_relation,
        "target_id": out.wrong_target,
        "polarity": out.wrong_polarity,
        "modality": out.wrong_modality,
        "conditions": out.wrong_conditions,
        "perturbation_type": out.perturbation_type,
        "contradicts": list(out.contradicts),
        "intuition": out.intuition,
        "prevalence_cue": out.prevalence_cue,
        "misconception_quote": {"section_id": cand.section_id, "quote": out.misconception_quote},
        "correction_quote": {"section_id": cand.section_id, "quote": out.correction_quote},
        "source_name": ctx["by_id"][out.wrong_source]["canonical_name"],
        "target_name": ctx["by_id"][out.wrong_target]["canonical_name"],
    }


def run_stage(
    client: LLMClient,
    prompt: PromptTemplate,
    registry: RelationRegistry,
    cp: dict,
    sections: list[tuple[str, str]],
    lexicon: Lexicon | None,
    *,
    limit: int | None = None,
    fixture: str = "default",
    verify=None,  # callable(pce dict, candidate) -> result dict | None (the relation verifier)
) -> dict:
    """Run the stage on a checkpoint dict; returns and stores the layer in cp['misconceptions']."""
    # idempotent: edges this stage added in an earlier run are re-derived, never accumulated
    cp["relation_results_v3"] = [
        r for r in cp["relation_results_v3"] if r.get("found_by") != "misconception_stage"
    ]
    cands = scan_cues(sections, lexicon)
    if limit is not None:
        cands = cands[:limit]
    text_by = dict(sections)
    concepts = cp["concepts"]
    matcher = MentionMatcher(
        concept_vocab(
            [
                RegisteredConcept(
                    c["concept_id"],
                    c["canonical_name"],
                    c["node_type"],
                    None,
                    "",
                    list(c.get("aliases", [])),
                )
                for c in concepts
            ]
        )
    )
    edges = expert_edges(cp["relation_results_v3"])
    schema = build_misconception_llm(registry)
    layer = {
        "items": [],
        "not_warning": [],
        "needs_review": [],
        "needs_correct_edge": [],
        "proposed_lexicon": [],
        "stats": {"candidates": len(cands)},
    }
    templates = relation_templates(registry)

    def call(cand: Candidate, ctx: dict, extra: str = ""):
        lp = (
            (
                f"Look-alike pair from the term lexicon: {cand.lexicon_pair[0]} / {cand.lexicon_pair[1]} "
                "(students confuse these)\n"
            )
            if cand.lexicon_pair
            else ""
        )
        rendered = (
            prompt.render(
                relation_templates=templates,
                section_id=cand.section_id,
                lexicon_pairs=lp,
                paragraph=cand.paragraph,
                cue_families=", ".join(cand.families),
                sentence=cand.sentence,
                cards=_render_cards(ctx["cards"]),
                edges=_render_edges(ctx["edges"], ctx["by_id"], ctx.get("lex")),
            )
            + extra
        )
        return client.parse(
            task="misconception_structuring",
            prompt_version=prompt.version,
            messages=[{"role": "user", "content": rendered}],
            schema=schema,
            model_tier="strong",
            fixture_name=fixture,
        )

    for cand in cands:
        ctx = build_context(cand, concepts, matcher, edges, registry, lexicon)
        try:
            out = call(cand, ctx).output
        except ValidationError as e:
            layer["needs_review"].append(
                {
                    "section_id": cand.section_id,
                    "sentence": cand.sentence,
                    "errors": [f"schema: {e.errors()[0]['msg']}"],
                }
            )
            continue
        if not out.is_warning:
            layer["not_warning"].append(
                {
                    "section_id": cand.section_id,
                    "sentence": cand.sentence,
                    "reason": out.reason,
                    "families": cand.families,
                }
            )
            continue
        errs = (
            check_item(out, ctx, text_by[cand.section_id], registry, lexicon)
            if not out.proposed_correct
            else _check_proposed(out, ctx, text_by[cand.section_id])
        )
        if errs:  # one corrective re-prompt (CR-009 §4.3 style), then to the owner unchanged
            fix = (
                "\n\nYour previous answer failed these checks; answer again and fix them:\n- "
                + "\n- ".join(errs)
            )
            try:
                out2 = call(cand, ctx, fix).output
                errs2 = (
                    check_item(out2, ctx, text_by[cand.section_id], registry, lexicon)
                    if not out2.proposed_correct
                    else _check_proposed(out2, ctx, text_by[cand.section_id])
                )
            except ValidationError:
                out2, errs2 = out, errs
            if errs2 or not out2.is_warning:
                layer["needs_review"].append(
                    {
                        "section_id": cand.section_id,
                        "sentence": cand.sentence,
                        "errors": errs2 or ["second answer: not a warning"],
                        "first_answer": out.model_dump(),
                    }
                )
                continue
            out = out2
        if out.proposed_correct:
            accepted = verify(out, cand) if verify else None
            if not accepted:
                layer["needs_correct_edge"].append(
                    {
                        "section_id": cand.section_id,
                        "sentence": cand.sentence,
                        "intuition": out.intuition,
                        "proposed": out.model_dump(),
                    }
                )
                continue
            new_id = edge_id(accepted["pair"]["pair_id"])
            out.contradicts = [new_id]
            ctx = build_context(
                cand, concepts, matcher, {**edges, new_id: accepted}, registry, lexicon
            )
            errs3 = check_item(out, ctx, text_by[cand.section_id], registry, lexicon)
            if errs3:  # the edge enters the expert layer only together with a passing layer item
                layer["needs_review"].append(
                    {"section_id": cand.section_id, "sentence": cand.sentence, "errors": errs3}
                )
                continue
            cp["relation_results_v3"].append(accepted)
            edges[new_id] = accepted
        item = _item(out, cand, text_by[cand.section_id], ctx)
        twin = next(
            (
                i
                for i in layer["items"]
                if (i["source_id"], i["relation"], i["target_id"], i["polarity"])
                == (item["source_id"], item["relation"], item["target_id"], item["polarity"])
            ),
            None,
        )
        if twin:  # the same wrong edge from another passage: keep one item, add the evidence
            twin.setdefault("additional_quotes", []).append(
                {
                    "section_id": cand.section_id,
                    "misconception_quote": out.misconception_quote,
                    "correction_quote": out.correction_quote,
                }
            )
            continue
        layer["items"].append(item)
        if out.perturbation_type == "conflation":
            layer["proposed_lexicon"].append(
                {
                    "forms": [item["source_name"], item["target_name"]],
                    "kind": "confusable",
                    "status": "proposed",
                    "source": f"misconception stage {item['item_id']}",
                    "quote": out.misconception_quote,
                    "section": cand.section_id,
                }
            )
    layer["stats"].update(
        {
            "warnings": len(layer["items"]),
            "not_warning": len(layer["not_warning"]),
            "needs_review": len(layer["needs_review"]),
            "needs_correct_edge": len(layer["needs_correct_edge"]),
        }
    )
    cp["misconceptions"] = layer
    return layer


def _check_proposed(out, ctx: dict, text: str) -> list[str]:
    errs = []
    for fld in ("misconception_quote", "correction_quote", "pce_quote"):
        q = getattr(out, fld)
        if not q or not verify_quote(q, text):
            errs.append(f"{fld} is not a verbatim substring of the section")
    for fld in ("wrong_source", "wrong_target", "pce_source", "pce_target"):
        if getattr(out, fld) not in ctx["shown"]:
            errs.append(f"{fld} is not one of the shown expert nodes")
    if not (out.pce_relation and out.pce_polarity):
        errs.append("a proposed correct edge needs pce_relation and pce_polarity")
    return errs
