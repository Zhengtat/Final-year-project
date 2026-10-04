"""CR-009: run the concept stage (generator -> verifier -> pruner, backfill at each chapter end) over sections in
book order. Cards come only from this run's own growing nodes of earlier sections (never gold). Mentions are
written only by the generator (main pass or backfill), with evidence; string matching only produces hints.
Pruned items are never cards and never paired."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from cumap.concepts_v4.cards import (
    Card,
    Node,
    NodeStore,
    make_gloss,
    select_cards,
    split_paragraphs,
)
from cumap.concepts_v4.loop import LoopConfig, SectionResult, SectionRunner, render_paragraphs
from cumap.concepts_v4.pruner import is_value_like, norm
from cumap.concepts_v4.schema import BackfillLLM
from cumap.concepts_v4.verifier import VerifyCtx, drop_flagged, verify
from cumap.expert_kg.alias_rules import AliasConfig, r1_key
from cumap.expert_kg.lexicon import Lexicon
from cumap.expert_kg.mentions import MentionMatcher
from cumap.expert_kg.partial_span import chunk_counts, noun_form_lexicon
from cumap.llm.client import BudgetExceededError, LLMClient
from cumap.llm.prompts import PromptTemplate


@dataclass
class ChapterCtx:
    recurring: Counter
    noun_forms: set[str]


@dataclass
class RunOutput:
    store: NodeStore
    sections: dict[str, SectionResult] = field(default_factory=dict)
    section_meta: dict[str, dict] = field(
        default_factory=dict
    )  # cards shown, p-values, pruned, attributes
    pruned: list[dict] = field(default_factory=list)
    merges: list[dict] = field(default_factory=list)  # G-link provenance
    backfill: list[dict] = field(default_factory=list)
    cost_usd: float = 0.0


def g_link_ok(
    surface: str, node: Node, text: str, lexicon: Lexicon | None, cfg: AliasConfig
) -> bool:
    """Strict G-link: a text form may be recorded as a mention of a node with a different name only when a rule shows it is
    the same node: the lexicon `same` set, an acronym and its long form (in the text), or the same words up to plural."""
    from cumap.expert_kg.alias_rules import find_abbreviations, split_embedded_acronym
    from cumap.expert_kg.mentions import default_lemma

    ks, nk = r1_key(surface, cfg), {r1_key(f, cfg) for f in node.forms()}
    if (
        lexicon is not None
        and (rep := lexicon.same_set(surface)) is not None
        and any(lexicon.same_set(f) == rep for f in node.forms())
    ):
        return True
    for ab in find_abbreviations(text, cfg):
        pair = {r1_key(ab.long_form, cfg), r1_key(ab.short_form, cfg)}
        if ks in pair and (pair - {ks}) & nk:
            return True
    if (sp := split_embedded_acronym(surface, cfg)) and {
        r1_key(sp[0], cfg),
        r1_key(sp[1], cfg),
    } & nk:
        return True
    lem = lambda f: [default_lemma(t) for t in re.findall(r"[a-z0-9]+", f.lower())]
    return any(lem(surface) == lem(f) for f in node.forms())


class ConceptRun:
    def __init__(
        self,
        client: LLMClient,
        prompt: PromptTemplate,
        bank: dict,
        cfg: LoopConfig,
        *,
        nlp,
        embed_fn: Callable[[str], np.ndarray] | None,
        lexicon: Lexicon | None,
        domain: str,
        backfill_prompt: PromptTemplate | None = None,
        pruner_for: Callable[[int | str], Callable[[str], float] | None] | None = None,
        tau: float = 0.0,
        rho: float = 1.5,
        m4: bool = False,
        m5: bool = False,
        strict_g_links: bool = False,
        emphasised: dict[str, set[str]] | None = None,
        retriever_k: int = 30,
        card_cap: int = 120,
        fixture: str = "default",
        progress: Callable[[str], None] | None = None,
    ):
        self.__dict__.update(locals())
        self.runner = SectionRunner(client, prompt, bank, cfg, domain=domain, fixture=fixture)
        self.alias_cfg = lexicon.cfg if lexicon else AliasConfig.load()

    # ---------------------------------------------------------------- chapter contexts
    def _chapter_ctx(self, sections: list[dict]) -> dict[str, ChapterCtx]:
        by: dict[str, list[str]] = defaultdict(list)
        for s in sections:
            by[str(s["chapter_num"])].append(s["text"])
        return {
            ch: ChapterCtx(chunk_counts(ts, self.nlp), noun_form_lexicon(ts, self.nlp))
            for ch, ts in by.items()
        }

    # ---------------------------------------------------------------- the run
    def run(
        self,
        sections: list[dict],
        *,
        backfill: bool = True,
        store: NodeStore | None = None,
        order_offset: int = 0,
    ) -> RunOutput:
        """`store` + `order_offset` continue a finished run (CR-009 §7: the test run starts from the final dev run's state)."""
        sections = sorted(sections, key=lambda s: int(s["order_index"]))
        order = {s["section_id"]: i + order_offset for i, s in enumerate(sections)}
        chap = self._chapter_ctx(sections)
        out = RunOutput(store or NodeStore())
        n_sec = len(sections)
        for i, sec in enumerate(sections):
            paras = split_paragraphs(sec["text"])
            cards = select_cards(
                paras,
                out.store,
                i + order_offset,
                self.lexicon,
                self.embed_fn,
                k=self.retriever_k,
                cap=self.card_cap,
            )
            cc = chap[str(sec["chapter_num"])]
            vctx = VerifyCtx(
                section_text=" ".join(paras.values()),
                paragraphs=paras,
                cards=cards,
                lexicon=self.lexicon,
                nlp=self.nlp,
                rho=self.rho,
                recurring=cc.recurring,
                noun_forms=cc.noun_forms,
                emphasised=(self.emphasised or {}).get(sec["section_id"], set()),
                m4=self.m4,
                m5=self.m5,
                chapter=sec.get("chapter_num") if isinstance(sec.get("chapter_num"), int) else None,
            )
            sec = {
                **sec,
                "heading": sec.get("heading") or sec.get("heading_path") or sec["section_id"],
            }
            res = self.runner.run(sec, paras, cards, self.lexicon, vctx)
            out.sections[sec["section_id"]] = res
            self._apply(out, sec, i + order_offset, res, cards, paras)
            if self.progress:
                self.progress(
                    f"section {i + 1}/{n_sec} {sec['section_id']}: {res.calls} calls, stop={res.stop_reason}, nodes={len(out.store.nodes)}"
                )
            last_of_chapter = i + 1 == n_sec or sections[i + 1]["chapter_num"] != sec["chapter_num"]
            if backfill and last_of_chapter and self.backfill_prompt is not None:
                self._backfill(out, sections, order, i, order_offset)
        return out

    # ---------------------------------------------------------------- apply one section to the store
    def _apply(
        self,
        out: RunOutput,
        sec: dict,
        order: int,
        res: SectionResult,
        cards: list[Card],
        paras: dict[str, str],
    ) -> None:
        sid = sec["section_id"]
        meta = {
            "cards_shown": [c.node.id for c in cards],
            "p": [],
            "pruned": [],
            "attributes": [],
            "mentions": [],
            "new_nodes": [],
        }
        by_id = {c.node.id: c.node for c in cards}
        final = res.final
        for m in final["existing_mentions"]:
            node = by_id.get(m["node_id"])
            if node is None:
                continue
            nontrivial = r1_key(m["surface"], self.alias_cfg) not in {
                r1_key(f, self.alias_cfg) for f in node.forms()
            }
            if (
                nontrivial
                and self.strict_g_links
                and not g_link_ok(
                    m["surface"], node, " ".join(paras.values()), self.lexicon, self.alias_cfg
                )
            ):
                # CR-009 STOP 3 (owner marks: 4/15 non-trivial links were the same sense): a link the rules cannot
                # show to be the same node is NOT recorded, and the form is not added as an alias
                out.merges.append(
                    {
                        "rule_id": "G-link-rejected",
                        "node_id": node.id,
                        "surface": m["surface"],
                        "section_id": sid,
                        "evidence": m["evidence"],
                        "trivial": False,
                    }
                )
                continue
            node.mentions.append(
                {
                    "section_id": sid,
                    "order": order,
                    "role": m["role"],
                    "para": m["para"],
                    "evidence": m["evidence"],
                    "surface": m["surface"],
                    "linked_by": "generator",
                }
            )
            meta["mentions"].append(m["node_id"])
            if r1_key(m["surface"], self.alias_cfg) not in {
                r1_key(f, self.alias_cfg) for f in node.forms()
            }:  # G-link
                out.merges.append(
                    {
                        "rule_id": "G-link",
                        "node_id": node.id,
                        "surface": m["surface"],
                        "section_id": sid,
                        "evidence": m["evidence"],
                        "trivial": False,
                    }
                )
                if m["surface"] not in node.aliases:
                    node.aliases.append(m["surface"])
            if m["role"] == "refined" and node.definition is None:
                node.definition = m["evidence"]
        pr = self.pruner_for(sec.get("chapter_num")) if self.pruner_for else None
        seen_keys: set[str] = set()
        for c in final["new_concepts"]:
            key = r1_key(c["name"], self.alias_cfg)
            if key in seen_keys:
                continue  # the same term twice in one section
            seen_keys.add(key)
            p = pr(c["name"]) if pr else 1.0
            meta["p"].append({"name": c["name"], "p": p, "role": c["role"]})
            lex_same = bool(self.lexicon and self.lexicon.same_set(c["name"]) is not None)
            keep = lex_same or p >= self.tau  # guard 1: a lexicon `same` form is always growing
            if (
                not keep
                and self.lexicon is not None
                and any(self.lexicon.is_different(c["name"], b.node.name) for b in cards)
            ):
                keep = True  # guard 4: the `different` guard applies
            if keep:
                node = Node(
                    id=out.store.new_id(),
                    name=c["name"],
                    aliases=list(c["aliases"]),
                    node_type=c["node_type"],
                    first_section=sid,
                    first_order=order,
                    definition=c["evidence"] if c["role"] == "defined" else None,
                    def_section=sid if c["role"] == "defined" else None,
                    gloss=make_gloss(c["evidence"]),
                    extraction_origin=c["extraction_origin"],
                    found_via_anchor=c["found_via_anchor"],
                    anchors=[{**a, "section_id": sid} for a in c["anchors"]],
                )
                node.mentions.append(
                    {
                        "section_id": sid,
                        "order": order,
                        "role": c["role"],
                        "para": c["para"],
                        "evidence": c["evidence"],
                        "surface": c["name"],
                        "linked_by": "generator",
                    }
                )
                out.store.add(node)
                meta["new_nodes"].append(node.id)
                continue
            rec = {
                "name": c["name"],
                "p": p,
                "section_id": sid,
                "role": c["role"],
                "evidence": c["evidence"],
                "node_type": c["node_type"],
            }
            if c["role"] == "defined":
                rec["pruned_defined"] = True  # guard 2: always listed on the owner sheet
            target = next(
                (
                    by_id[a["node_id"]]
                    for a in c["anchors"]
                    if a["node_id"] in by_id
                    and by_id[a["node_id"]].node_type in {"Parameter", "Property"}
                ),
                None,
            )
            if is_value_like(c["name"]) and target is not None:
                target.attributes.append(
                    {"value": c["name"], "evidence": c["evidence"], "section_id": sid}
                )
                meta["attributes"].append(c["name"])
            else:
                out.pruned.append(rec)
                meta["pruned"].append(c["name"])
        out.section_meta[sid] = meta

    # ---------------------------------------------------------------- backfill (CR-009 §3.7)
    def _backfill(
        self,
        out: RunOutput,
        sections: list[dict],
        order: dict[str, int],
        last_idx: int,
        order_offset: int = 0,
    ) -> None:
        chapter = sections[last_idx]["chapter_num"]
        first_in_chapter = min(
            (i for i, s in enumerate(sections) if s["chapter_num"] == chapter), default=last_idx
        )
        new_nodes = [
            n
            for n in out.store.nodes.values()
            if n.growing
            and first_in_chapter + order_offset <= n.first_order <= last_idx + order_offset
        ]
        if not new_nodes:
            return
        vocab: dict[str, str] = {}
        for n in new_nodes:
            for f in {*n.forms(), *(self.lexicon.same_forms(n.name) if self.lexicon else set())}:
                vocab.setdefault(f.lower(), n.id)
        matcher = MentionMatcher(vocab)
        recorded: dict[str, set[str]] = defaultdict(set)
        for n in out.store.nodes.values():
            for m in n.mentions:
                recorded[m["section_id"]].add(n.id)
        todo: dict[str, list[Node]] = {}
        for s in sections[:first_in_chapter] + [
            s for s in sections[first_in_chapter : last_idx + 1]
        ]:
            o = order[s["section_id"]]
            hits = {h.concept_id for h in matcher.find(s["text"])}
            for nid in hits:
                n = out.store.nodes[nid]
                if o < n.first_order and nid not in recorded[s["section_id"]]:
                    todo.setdefault(s["section_id"], []).append(n)
        by_sec = {s["section_id"]: s for s in sections}
        for sid, nodes in todo.items():
            paras = split_paragraphs(by_sec[sid]["text"])
            given = "\n".join(
                f"b{j} | {n.id} | {n.name} | {', '.join(n.aliases) or '-'} | {n.node_type} | def {('§' + n.def_section) if n.def_section else '—'} | {n.gloss}"
                for j, n in enumerate(nodes, 1)
            )
            rendered = self.backfill_prompt.render(
                domain=self.domain,
                heading_path=str(by_sec[sid].get("heading") or sid),
                given_nodes=given,
                section_paragraphs=render_paragraphs(paras),
            )
            try:
                res = self.client.parse(
                    task="concept_backfill",
                    prompt_version=self.backfill_prompt.version,
                    messages=[{"role": "user", "content": rendered}],
                    schema=BackfillLLM,
                    model_tier=self.cfg.model_tier,
                    fixture_name=self.fixture,
                    allow_escalation=False,
                )
            except BudgetExceededError:
                raise
            except Exception as e:  # noqa: BLE001  # a failed backfill call adds nothing
                out.backfill.append(
                    {
                        "section_id": sid,
                        "error": f"{type(e).__name__}",
                        "given": [n.id for n in nodes],
                    }
                )
                continue
            bo = res.output.model_dump()
            vctx = VerifyCtx(
                section_text=" ".join(paras.values()),
                paragraphs=paras,
                cards=[Card(n, True) for n in nodes],
                lexicon=self.lexicon,
                nlp=self.nlp,
                rho=0.0,
            )
            vr = verify(
                {
                    "existing_mentions": bo["existing_mentions"],
                    "not_mentions": [],
                    "new_concepts": [],
                    "hint_responses": [],
                },
                vctx,
            )
            kept, dropped = drop_flagged(
                vr.out, vr.flags
            )  # F2/F3/C1/C2 run on the output; no corrective round
            accepted = []
            for m in kept["existing_mentions"]:
                n = out.store.nodes.get(m["node_id"])
                if n is None:
                    continue
                n.mentions.append(
                    {
                        "section_id": sid,
                        "order": order[sid],
                        "role": m["role"],
                        "para": m["para"],
                        "evidence": m["evidence"],
                        "surface": m["surface"],
                        "linked_by": "backfill",
                    }
                )
                if order[sid] < n.first_order:
                    n.first_section, n.first_order = sid, order[sid]
                accepted.append(m["node_id"])
            out.backfill.append(
                {
                    "section_id": sid,
                    "chapter_end": chapter,
                    "given": [n.id for n in nodes],
                    "accepted": accepted,
                    "dropped": [d["rules"] for d in dropped],
                    "rejected": [r for r in bo["hint_responses"] if r["decision"] == "rejected"],
                }
            )


# ---------------------------------------------------------------- scoring adapter (CR-009 §7)
def predictions(
    out: RunOutput,
    sections: list[dict],
    gold_names: dict[str, set[str]],
    *,
    finals: dict[str, dict] | None = None,
    tau: float | None = None,
    replay: bool = False,
) -> dict[str, list[dict]]:
    """Per section: the NEW concepts that became nodes (pruned items and unconfirmed mentions are not predictions)
    plus existing mentions, scored like new concepts on the surface form PLUS the node's name and aliases: the
    form that matches gold is used when one does (a mention is not scored more strictly than a new concept).
    `finals` replays another output per section; with `replay`, `tau` re-applies the pruner to the recorded
    p(growing) values (None = no pruning)."""
    result: dict[str, list[dict]] = {}
    for s in sections:
        sid = s["section_id"]
        res = out.sections.get(sid)
        if res is None:
            continue
        meta = out.section_meta.get(sid, {})
        fin = (finals or {}).get(sid, res.final)
        if replay:
            pruned_names = {
                norm(x["name"]) for x in meta.get("p", []) if tau is not None and x["p"] < tau
            }
        else:
            pruned_names = {norm(x) for x in meta.get("pruned", [])} | {
                norm(x) for x in meta.get("attributes", [])
            }
        items: list[dict] = []
        for c in fin["new_concepts"]:
            if norm(c["name"]) in pruned_names:
                continue
            items.append(
                {
                    "canonical_name": c["name"],
                    "role": c["role"],
                    "node_type": c["node_type"],
                    "evidence_quote": c["evidence"],
                    "source": "llm",
                    "aliases": c["aliases"],
                }
            )
        for m in fin["existing_mentions"]:
            node = out.store.nodes.get(m["node_id"])
            forms = [m["surface"], *([node.name, *node.aliases] if node else [])]
            pick = next((f for f in forms if norm(f) in gold_names.get(sid, set())), m["surface"])
            role = "defined" if m["role"] in {"refined", "defined"} else m["role"]
            items.append(
                {
                    "canonical_name": pick,
                    "role": role,
                    "node_type": m["node_type"],
                    "evidence_quote": m["evidence"],
                    "source": "llm",
                }
            )
        for b in out.backfill:
            if b.get("section_id") == sid:
                for nid in b.get("accepted", []):
                    node = out.store.nodes[nid]
                    pick = next(
                        (f for f in node.forms() if norm(f) in gold_names.get(sid, set())),
                        node.name,
                    )
                    items.append(
                        {
                            "canonical_name": pick,
                            "role": "mentioned",
                            "node_type": node.node_type,
                            "evidence_quote": "",
                            "source": "backfill",
                        }
                    )
        result[sid] = items
    return result
