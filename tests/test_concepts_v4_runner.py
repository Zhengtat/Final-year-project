"""CR-009 §3.2, §3.7, §5, §11: card eligibility, G-links, pruning, backfill, no-propagation (no network, no key)."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import spacy

from cumap.concepts_v4.bank import load
from cumap.concepts_v4.loop import LoopConfig
from cumap.concepts_v4.runner import ConceptRun, predictions
from cumap.concepts_v4.schema import BackfillLLM, ConceptGeneratorV4LLM
from cumap.llm.prompts import load_prompt

REPO = Path(__file__).parents[1]
NLP = spacy.load("en_core_web_sm")
BANK = load()
GEN = load_prompt(REPO / "prompts", "concept_generator", "v4")
BF = load_prompt(REPO / "prompts", "concept_backfill", "v1")
S1 = {
    "section_id": "s1",
    "chapter_num": 1,
    "order_index": 0,
    "text": "A B-tree index keeps its keys in sorted order. The index speeds up every query.",
}
S2 = {
    "section_id": "s2",
    "chapter_num": 1,
    "order_index": 1,
    "text": "An inverted file also acts as an index. The page size is 4 KB.",
}


def new(
    name, ev, para="P1", role="used", typ="Component", anchors=(), origin="independent", aliases=()
):
    return {
        "name": name,
        "aliases": list(aliases),
        "node_type": typ,
        "role": role,
        "evidence": ev,
        "para": para,
        "extraction_origin": origin,
        "anchors": list(anchors),
        "independence_check": None if origin == "anchored" else "no card is related",
        "found_via_anchor": False,
    }


def mention(nid, surface, ev, role="used", typ="Component", para="P1"):
    return {
        "node_id": nid,
        "surface": surface,
        "node_type": typ,
        "role": role,
        "evidence": ev,
        "para": para,
    }


def gen_out(news=(), mentions=()):
    return {
        "existing_mentions": list(mentions),
        "not_mentions": [],
        "new_concepts": list(news),
        "hint_responses": [],
    }


class Fake:
    def __init__(self, by_section: dict, backfill=None):
        self.by_section, self.backfill, self.calls = by_section, backfill, []

    def parse(self, **kw):
        text = kw["messages"][0]["content"]
        self.calls.append((kw["task"], text))
        if kw["task"] == "concept_backfill":
            return SimpleNamespace(output=BackfillLLM.model_validate(self.backfill(text)))
        tail = text.split("Section text (numbered paragraphs):")[-1]
        sid = "s1" if "keeps its keys" in tail else "s2"
        o = self.by_section[sid]
        return SimpleNamespace(
            output=ConceptGeneratorV4LLM.model_validate(o(text) if callable(o) else o)
        )


def embed(t: str) -> np.ndarray:
    v = np.zeros(8)
    for i, w in enumerate(["index", "query", "key", "page", "file", "size", "order", "tree"]):
        v[i] = float(w in t.lower())
    return v


def run(fake, sections=(S1, S2), **kw):
    cfg = LoopConfig(form="G1", instructions={}, max_iterations=0)
    return ConceptRun(
        fake,
        GEN,
        BANK,
        cfg,
        nlp=NLP,
        embed_fn=embed,
        lexicon=None,
        domain="databases",
        backfill_prompt=BF,
        rho=0.0,
        **kw,
    ).run(list(sections))


S1_OUT = gen_out(
    [
        new("B-tree index", "A B-tree index keeps its keys in sorted order", role="defined"),
        new("query", "speeds up every query"),
    ]
)


def test_cold_start_then_cards_come_only_from_growing_nodes_of_earlier_sections():
    f = Fake(
        {"s1": S1_OUT, "s2": gen_out([new("page size", "The page size is 4 KB", typ="Parameter")])}
    )
    out = run(f)
    p1, p2 = f.calls[0][1], f.calls[1][1]
    assert (
        "(none: no known nodes yet)" in p1.split("=== THIS SECTION ===")[1]
    )  # cold start: the procedure still runs
    assert (
        "B-tree index" in p2.split("=== THIS SECTION ===")[1]
        and out.section_meta["s2"]["cards_shown"]
    )
    assert (
        out.section_meta["s1"]["cards_shown"] == []
    )  # a node is never shown to its own or an earlier section


def test_pruned_items_are_never_cards_and_not_predictions():
    pr = lambda ch: lambda t: 0.1 if t == "query" else 0.9
    f = Fake(
        {"s1": S1_OUT, "s2": gen_out([new("page size", "The page size is 4 KB", typ="Parameter")])}
    )
    out = run(f, pruner_for=pr, tau=0.5)
    assert [r["name"] for r in out.pruned] == ["query"]
    assert "query |" not in f.calls[1][1].split("EXISTING NODES")[-1].split("Section text")[0]
    names = [i["canonical_name"] for i in predictions(out, [S1, S2], {})["s1"]]
    assert names == ["B-tree index"]


def test_pruned_defined_is_flagged_and_a_value_with_an_anchor_becomes_an_attribute():
    pr = lambda ch: lambda t: 0.1
    f = Fake(
        {
            "s1": gen_out(
                [
                    new(
                        "keys",
                        "A B-tree index keeps its keys in sorted order",
                        role="defined",
                        typ="Parameter",
                    )
                ]
            ),
            "s2": gen_out(),
        }
    )
    out = run(f, pruner_for=pr, tau=0.5)
    assert out.pruned[0].get("pruned_defined") is True
    # attribute: s2 prunes "4 KB" which anchors to a Parameter card shown from s1
    s1 = gen_out(
        [
            new("B-tree index", "A B-tree index keeps its keys in sorted order", role="defined"),
            new("query", "speeds up every query", typ="Parameter"),
        ]
    )
    anchor = {"node_id": "n_0002", "anchor_type": "property_of", "cue": "The query size is 4 KB"}
    s2 = gen_out(
        [new("4 KB", "The query size is 4 KB", typ="Property", origin="anchored", anchors=[anchor])]
    )
    pr2 = lambda ch: lambda t: 0.1 if t == "4 KB" else 0.9
    out = run(
        Fake({"s1": s1, "s2": s2}),
        sections=(S1, {**S2, "text": "An inverted file is an index. The query size is 4 KB."}),
        pruner_for=pr2,
        tau=0.5,
    )
    node = out.store.nodes["n_0002"]
    assert node.attributes and node.attributes[0]["value"] == "4 KB" and not out.pruned


def test_a_lexicon_same_form_is_always_growing_and_g_links_are_logged_with_evidence(tmp_path):
    import yaml

    from cumap.expert_kg.alias_rules import AliasConfig
    from cumap.expert_kg.lexicon import Lexicon

    p = tmp_path / "lex.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "version": "t",
                "same": [
                    {
                        "id": "s",
                        "forms": ["query", "search"],
                        "scope": "book:pd6e",
                        "status": "approved",
                        "source": "t",
                    }
                ],
                "different": [],
            }
        )
    )
    lex = Lexicon.load(p, AliasConfig.load())
    f = Fake(
        {
            "s1": S1_OUT,
            "s2": gen_out(
                mentions=[
                    mention("n_0001", "inverted file", "An inverted file also acts as an index")
                ]
            ),
        }
    )
    cfg = LoopConfig(form="G1", instructions={}, max_iterations=0)
    out = ConceptRun(
        f,
        GEN,
        BANK,
        cfg,
        nlp=NLP,
        embed_fn=embed,
        lexicon=lex,
        domain="d",
        backfill_prompt=BF,
        rho=0.0,
        pruner_for=lambda ch: lambda t: 1.0 if t == "B-tree index" else 0.0,
        tau=0.5,
    ).run([S1, S2])
    assert any(
        n.name == "query" for n in out.store.nodes.values()
    )  # guard 1: `same` form kept despite p = 0
    g = [m for m in out.merges if m["rule_id"] == "G-link"]
    assert (
        g
        and g[0]["evidence"] == "An inverted file also acts as an index"
        and "inverted file" in out.store.nodes["n_0001"].aliases
    )


def test_backfill_calls_only_detector_hit_sections_uses_the_mention_check_prompt_and_updates_first_section():
    s1 = {**S1, "text": "Terms are stored in a dictionary. The index speeds up queries."}
    s2 = {**S2, "text": "A dictionary maps each term to its postings."}
    f_s1 = gen_out([new("index", "The index speeds up queries", para="P1")])
    f_s2 = gen_out(
        [new("dictionary", "A dictionary maps each term to its postings", role="defined")]
    )

    def bf(text):
        assert (
            "GIVEN nodes" in text
            and "A dictionary maps" not in text.split("Section text (numbered paragraphs):")[-1]
        )  # the earlier section's text, not the later one
        return {
            "existing_mentions": [
                mention("n_0002", "dictionary", "Terms are stored in a dictionary", typ="Component")
            ],
            "hint_responses": [{"hint_id": "b1", "decision": "added", "reason": "same sense"}],
        }

    f = Fake(
        {"s1": lambda t: f_s1 if "stored in a dictionary" in t else f_s2, "s2": f_s2}, backfill=bf
    )

    # route by section text
    def dispatch(text):
        return (
            f_s1
            if "stored in a dictionary" in text.split("Section text (numbered paragraphs):")[-1]
            else f_s2
        )

    f.by_section = {"s1": dispatch, "s2": dispatch}
    f.parse_orig = f.parse

    def parse(**kw):
        text = kw["messages"][0]["content"]
        if kw["task"] == "concept_generator":
            f.calls.append((kw["task"], text))
            return SimpleNamespace(output=ConceptGeneratorV4LLM.model_validate(dispatch(text)))
        f.calls.append((kw["task"], text))
        return SimpleNamespace(output=BackfillLLM.model_validate(bf(text)))

    f.parse = parse
    out = run(f, sections=(s1, s2))
    bf_calls = [c for c in f.calls if c[0] == "concept_backfill"]
    assert len(bf_calls) == 1 and "Section heading" in bf_calls[0][1]
    node = out.store.nodes["n_0002"]
    assert node.first_section == "s1" and any(
        m["linked_by"] == "backfill" for m in node.mentions
    )  # first_section moved earlier


def test_no_mention_is_written_without_a_generator_or_backfill_decision():
    f = Fake(
        {"s1": S1_OUT, "s2": gen_out([new("page size", "The page size is 4 KB", typ="Parameter")])}
    )
    out = run(f)
    for n in out.store.nodes.values():
        assert n.mentions and all(m["linked_by"] in {"generator", "backfill"} for m in n.mentions)


def test_prompt_sections_appear_in_the_fixed_order():
    f = Fake({"s1": S1_OUT, "s2": gen_out()})
    run(f)
    text = f.calls[0][1]
    heads = [
        "=== ROLE ===",
        "=== TASK ===",
        "=== DEFINITIONS ===",
        "=== PROCEDURE ===",
        "=== OUTPUT SCHEMA ===",
        "=== EXAMPLES ===",
        "=== FINAL CHECKLIST ===",
        "=== THIS SECTION ===",
    ]
    pos = [text.index(h) for h in heads]
    assert pos == sorted(pos)
    assert text.index("EXISTING NODES (id |") > text.index(
        "=== THIS SECTION ==="
    )  # static content first, per-item content last


def test_a_run_can_continue_from_a_finished_runs_state_with_an_order_offset():
    """CR-009 §7: the test run starts from the final dev run's state (nodes keep their dev order, new sections follow)."""
    f = Fake(
        {"s1": S1_OUT, "s2": gen_out([new("page size", "The page size is 4 KB", typ="Parameter")])}
    )
    first = run(f, sections=(S1,))
    s2 = {**S2, "order_index": 0}
    f2 = Fake(
        {"s1": S1_OUT, "s2": gen_out([new("page size", "The page size is 4 KB", typ="Parameter")])}
    )
    cfg = LoopConfig(form="G1", instructions={}, max_iterations=0)
    out = ConceptRun(
        f2,
        GEN,
        BANK,
        cfg,
        nlp=NLP,
        embed_fn=embed,
        lexicon=None,
        domain="d",
        backfill_prompt=BF,
        rho=0.0,
    ).run([s2], store=first.store, order_offset=1)
    assert out.section_meta["s2"][
        "cards_shown"
    ]  # the dev run's nodes are cards for the continued run
    assert out.store.nodes["n_0003"].first_order == 1 and "B-tree index" in f2.calls[0][1]
