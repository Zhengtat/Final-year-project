"""CR-035: identity resolver, deterministic part (U0-U4) and the registry search (no network, no key)."""

from types import SimpleNamespace

import numpy as np
import pytest
import yaml
from test_concepts_v4_runner import (
    BANK,
    BF,
    GEN,
    NLP,
    ConceptGeneratorV4LLM,
    ConceptRun,
    LoopConfig,
    gen_out,
    mention,
    new,
)

from cumap.concepts_v4 import cr009_run, pd_run
from cumap.concepts_v4.cards import Node, NodeStore
from cumap.concepts_v4.runner import RunOutput
from cumap.expert_kg import identity as ID
from cumap.expert_kg.alias_rules import AliasConfig
from cumap.expert_kg.canonical_rules import AliasContext
from cumap.expert_kg.canonicalize import (
    CanonicalOverrides,
    ConceptRegistry,
    canonicalize_mention,
)
from cumap.expert_kg.concepts import ConceptMentionCandidate
from cumap.expert_kg.lexicon import Lexicon


def lex(tmp_path, same=(), different=()):
    entries = {
        "version": "t",
        "same": [{"id": f"S{i}", "forms": list(f), "scope": "book:pd6e", "status": "approved", "source": "t"} for i, f in enumerate(same)],
        "different": [{"id": f"D{i}", "forms": list(f), "kind": "confusable", "scope": "book:pd6e", "status": "approved", "source": "t"} for i, f in enumerate(different)],
    }  # fmt: skip
    p = tmp_path / "lex.yaml"
    p.write_text(yaml.safe_dump(entries))
    return Lexicon.load(p, AliasConfig.load())


def ctx(lexicon, text="", forms=()):
    return AliasContext.build(lexicon, {"s1": text}, {"s1": 1}, list(forms), lexicon.cfg)


# ---------------------------------------------------------------- U0-U4, in order
def test_each_rule_fires_and_the_first_one_wins(tmp_path):
    text = (
        "A router, also known as gateway, forwards packets. A hub, sometimes called repeater, repeats bits. "
        "The cyclic redundancy check (CRC) detects errors."
    )
    lx = lex(tmp_path, same=[("flow", "flows")], different=[("gateway", "hub")])
    c = ctx(
        lx,
        text,
        [
            "router",
            "gateway",
            "hub",
            "repeater",
            "cyclic redundancy check",
            "CRC",
            "flow",
            "flows",
            "link",
            "links",
        ],
    )
    d = lambda a, b, **k: ID.resolve_deterministic(c, a, b, chapter=1, **k)
    assert (d("gateway", "hub").decision, d("gateway", "hub").rule_id) == ("keep_apart", "U0")
    assert (
        d("flow", "flows").rule_id == "U1" and d("flow", "flows").legacy_rule_id == "R0"
    )  # U1 beats U2 (same R1 key)
    assert d("links", "link").rule_id == "U2" and d("links", "link").legacy_rule_id == "R1"
    assert d("CRC", "cyclic redundancy check").rule_id == "U3"
    assert (
        d("gateway", "router").rule_id == "U4-strong"
        and "also known as" in d("gateway", "router").evidence_quote
    )
    weak = d("hub", "repeater")
    assert (weak.decision, weak.rule_id) == ("review", "U4-weak")  # never a merge (rule 19)
    assert d("router", "hub").decision == "undecided"


def test_node_types_must_be_compatible_for_u2_to_u4_but_not_for_u0_u1(tmp_path):
    lx = lex(tmp_path, same=[("cat", "feline")], different=[("a", "b")])
    c = ctx(lx, "", ["link", "links"])
    kw = {"chapter": 1, "a_type": "Protocol", "b_type": "Component"}
    assert ID.resolve_deterministic(c, "links", "link", **kw).decision == "undecided"
    assert ID.resolve_deterministic(c, "cat", "feline", **kw).rule_id == "U1"
    assert ID.resolve_deterministic(c, "a", "b", **kw).rule_id == "U0"
    assert (
        ID.resolve_deterministic(
            c, "links", "link", chapter=1, a_type="Concept", b_type="Component"
        ).rule_id
        == "U2"
    )  # generic type is compatible


def test_a_veto_against_any_form_wins_over_a_merge_on_another_form(tmp_path):
    lx = lex(tmp_path, different=[("hub", "switch")])
    c = ctx(lx, "", ["hub", "switch", "hubs"])
    r = ID.resolve_against_forms(c, "switch", ["hubs", "hub"], chapter=1)
    assert (r.decision, r.rule_id) == ("keep_apart", "U0")


def test_legacy_id_map_matches_the_rules_file_and_the_canonicalize_copy():
    from cumap.expert_kg.canonicalize import _LEGACY_TO_U

    rules = ID.load_rules()
    assert rules["legacy_rule_ids"] == ID.LEGACY_TO_U == _LEGACY_TO_U
    assert (
        rules["order"][0] == "U0"
        and rules["search"]["offer_threshold"] == 0.6
        and rules["search"]["review_band_below"] == 0.70
    )


# ---------------------------------------------------------------- input A (generator link)
S1 = {
    "section_id": "s1",
    "chapter_num": 1,
    "order_index": 0,
    "text": "A dictionary maps each term to its postings.",
}
S2 = {
    "section_id": "s2",
    "chapter_num": 1,
    "order_index": 1,
    "text": "A dictionary, also known as lookup table, is stored on disk.",
}


def _run_a(resolver, lexicon, policy="off"):
    calls = []

    def parse(**kw):
        text = kw["messages"][0]["content"]
        calls.append(kw["task"])
        if kw["task"] == "concept_generator":
            tail = text.split("Section text (numbered paragraphs):")[-1]
            if "lookup table" in tail:
                o = gen_out(
                    mentions=[
                        mention(
                            "n_0001",
                            "lookup table",
                            "also known as lookup table",
                            typ="Component",
                        )
                    ]
                )
            else:
                o = gen_out(
                    [
                        new(
                            "dictionary",
                            "A dictionary maps each term to its postings",
                            role="defined",
                        )
                    ]
                )
            return SimpleNamespace(output=ConceptGeneratorV4LLM.model_validate(o))
        raise AssertionError(
            f"unexpected LLM task {kw['task']}"
        )  # no adjudicator call may happen in these cases

    out = ConceptRun(
        SimpleNamespace(parse=parse), GEN, BANK, LoopConfig(form="G1", instructions={}, max_iterations=0),
        nlp=NLP, embed_fn=lambda t: np.zeros(4), lexicon=lexicon, domain="databases", backfill_prompt=BF, rho=0.0,
        strict_g_links=True, rejected_link_policy=policy, identity_resolver=resolver,
    ).run([S1, S2], backfill=False)  # fmt: skip
    return out, calls


def test_a_strong_alias_statement_links_under_u1_and_is_rejected_under_legacy(tmp_path):
    lx = lex(tmp_path)
    legacy, _ = _run_a("legacy", lx)
    u1, _ = _run_a("u1", lx)
    assert [m["rule_id"] for m in legacy.merges] == ["G-link-rejected"]
    assert [(m["rule_id"], m.get("identity_rule")) for m in u1.merges] == [
        ("U4-strong", "U4-strong")
    ]
    assert (
        "lookup table" in u1.store.nodes["n_0001"].aliases
        and "lookup table" not in legacy.store.nodes["n_0001"].aliases
    )


def test_u0_vetoes_a_link_and_no_adjudicator_call_is_made(tmp_path):
    lx = lex(tmp_path, different=[("dictionary", "lookup table")])
    u1, calls = _run_a(
        "u1", lx, policy="adjudicate"
    )  # a call to the adjudicator would raise AssertionError
    # the verifier's C1 guard (also the lexicon `different` list) may drop the link before it reaches the resolver; either way it is not linked
    assert "rejected_link_adjudicator" not in calls
    assert (
        "lookup table" not in u1.store.nodes["n_0001"].aliases
        and not u1.store.nodes["n_0001"].mentions[1:]
    )
    assert all(m["rule_id"] in ("G-link-rejected",) for m in u1.merges)


def test_legacy_resolver_is_the_default_and_the_policy_file_says_so():
    assert (
        cr009_run._identity_resolver() == "legacy" and cr009_run._identity_resolver({}) == "legacy"
    )
    assert cr009_run._identity_resolver({"identity_resolver": "u1"}) == "u1"
    with pytest.raises(ValueError):
        cr009_run._identity_resolver({"identity_resolver": "u2"})


# ---------------------------------------------------------------- input B (registry search)
class StubEmbed:
    """Records every text it embeds; the vector depends on which keyword the text starts with."""

    KEYS = ("router", "gateway", "hub", "switch")

    def __init__(self):
        self.texts: list[str] = []

    def __call__(self, text):
        self.texts.append(text)
        v = np.zeros(len(self.KEYS) + 1)
        for i, k in enumerate(self.KEYS):
            if text.lower().startswith(k):
                v[i] = 1.0
        v[-1] = 0.01
        return v


def cand(name, quote, typ="Component", sid="s1"):
    return ConceptMentionCandidate(
        canonical_name=name,
        node_type=typ,
        role="used",
        definition=None,
        evidence_quote=quote,
        section_id=sid,
    )


NO_LLM = SimpleNamespace(
    parse=lambda **kw: (_ for _ in ()).throw(AssertionError("no LLM call expected")),
    backend_call_count=0,
)


def test_search_uses_one_text_recipe_on_both_sides_finds_a_concept_through_an_alias_and_logs_the_form():
    emb = StubEmbed()
    reg = ConceptRegistry(emb)
    c = reg.add_new(
        cand("router", "A router forwards packets between networks across the internet today")
    )
    c.aliases.append("gateway")
    quote = "A gateway links two networks"
    r = reg.top_k_similar_forms("gateway", quote, k=5)
    assert r[0][0] is c and r[0][2] == "gateway" and r[0][1] > 0.9
    gloss = " ".join(
        [
            "A",
            "router",
            "forwards",
            "packets",
            "between",
            "networks",
            "across",
            "the",
            "internet",
            "today",
        ][:25]
    )
    assert (
        "router. " + gloss in emb.texts and "gateway. " + gloss in emb.texts
    )  # every form is "form. gloss" with the SAME gloss
    assert (
        "gateway. A gateway links two networks" in emb.texts
    )  # the query side uses the same recipe with its own quote
    n = len(emb.texts)
    reg.top_k_similar_forms("gateway", quote, k=5)
    assert len(emb.texts) == n + 1  # only the query is embedded again: the forms are cached
    c.aliases.append(
        "hub"
    )  # a merge added an alias: the new form is embedded, the old vectors stay valid
    reg.top_k_similar_forms("hub", "A hub repeats bits", k=5)
    assert any(t.startswith("hub. ") for t in emb.texts[n + 1 :])


def test_u1_merges_through_the_same_rule_as_input_a_and_logs_u_ids(tmp_path):
    lx = lex(tmp_path)
    c = ctx(lx, "A router, also known as gateway, forwards packets.", ["router", "gateway"])
    reg = ConceptRegistry(StubEmbed())
    reg.add_new(cand("router", "A router, also known as gateway, forwards packets"))
    a = ID.resolve_against_forms(c, "gateway", ["router"], chapter=1)
    o = canonicalize_mention(
        NO_LLM,
        None,
        reg,
        cand("gateway", "also known as a gateway"),
        type_aware=True,
        review_below=0.7,
        alias_ctx=c,
        identity_resolver="u1",
    )
    assert (
        a.rule_id == "U4-strong" == o.rule_id
        and o.legacy_rule_id == "R3-strong"
        and o.decision == "same"
    )
    legacy = canonicalize_mention(
        NO_LLM, None, ConceptRegistry(StubEmbed()), cand("x", "q"), alias_ctx=c
    )
    assert (
        legacy.legacy_rule_id is None and legacy.matched_form is None and legacy.weak_cue_ids == []
    )


def test_u0_blocks_the_candidate_on_the_b_path_and_no_llm_call_is_made(tmp_path):
    lx = lex(tmp_path, different=[("hub", "switch")])
    c = ctx(lx, "", ["hub", "switch"])
    reg = ConceptRegistry(StubEmbed())
    reg.add_new(cand("hub", "A hub repeats bits"))
    o = canonicalize_mention(
        NO_LLM,
        None,
        reg,
        cand("switch", "A switch forwards frames"),
        type_aware=True,
        review_below=0.7,
        alias_ctx=c,
        identity_resolver="u1",
    )
    assert o.decision == "different" and o.llm_called is False and len(reg) == 2


def test_a_weak_cue_is_recorded_for_review_and_never_merges(tmp_path):
    lx = lex(tmp_path)
    c = ctx(lx, "A hub, sometimes called repeater, repeats bits.", ["hub", "repeater"])
    reg = ConceptRegistry(StubEmbed())
    reg.add_new(cand("hub", "A hub, sometimes called repeater, repeats bits"))
    o = canonicalize_mention(
        NO_LLM,
        None,
        reg,
        cand("repeater", "a repeater"),
        type_aware=True,
        review_below=0.7,
        alias_ctx=c,
        identity_resolver="u1",
    )
    assert o.decision == "different" and o.weak_cue_ids == ["c_hub"]


# ---------------------------------------------------------------- merge log
def _canon(resolver):
    store = NodeStore()
    store.nodes["n_1"] = Node("n_1", "dictionary", [], "Component", "s1", 0, mentions=[{"section_id": "s1", "order": 0, "role": "defined", "para": "P1", "evidence": "A dictionary", "linked_by": "generator"}])  # fmt: skip
    out = RunOutput(store)
    out.merges = [
        {
            "rule_id": "G-link-rejected",
            "node_id": "n_1",
            "surface": "lookup table",
            "section_id": "s1",
            "evidence": "q",
            "trivial": False,
        }
    ]
    units = [{"section_id": "s1", "orig_section": "s1", "chapter_num": 1, "text": "A dictionary."}]
    return pd_run.canonicalise(
        out,
        units,
        None,
        NO_LLM,
        None,
        StubEmbed(),
        CanonicalOverrides(),
        progress=lambda *a: None,
        identity_resolver=resolver,
    )


def test_merge_log_keeps_each_entrys_own_rule_id_under_u1_and_relabels_under_legacy():
    legacy = [m for m in _canon("legacy").merges if m["stage"] == "generator"]
    u1 = [m for m in _canon("u1").merges if m["stage"] == "generator"]
    assert [m["rule_id"] for m in legacy] == ["G-link"] and "legacy_rule_id" not in legacy[0]
    assert [(m["rule_id"], m["legacy_rule_id"]) for m in u1] == [("G-link-rejected", "G-link")]


def test_replay_search_recall_counts_hits_for_both_searches(monkeypatch):
    from cumap.cr035 import replay as RP

    monkeypatch.setattr(
        RP,
        "marked_same_pairs",
        lambda: [
            {
                "sheet": "t",
                "id": "1",
                "a": "gateway",
                "b": "router",
                "evidence": "A router is also known as gateway",
                "section": "1.1",
            }
        ],
    )
    cp = {"concepts": [
        {"concept_id": "c_router", "canonical_name": "router", "node_type": "Component", "definition": None, "first_introduced": "1.1", "aliases": ["gateway"],
         "mentions": [{"section_id": "1.1", "role": "used", "quote": "A router is also known as gateway"}]},
        {"concept_id": "c_hub", "canonical_name": "hub", "node_type": "Component", "definition": None, "first_introduced": "1.1", "aliases": [],
         "mentions": [{"section_id": "1.1", "role": "used", "quote": "A hub repeats bits"}]},
    ]}  # fmt: skip

    def emb(text):  # "router" and "gateway" texts are one direction, "hub" another
        return (
            np.array([1.0, 0.0])
            if ("router" in text or "gateway" in text)
            else np.array([0.0, 1.0])
        )

    r = RP.search_recall(cp, emb)
    assert (
        r["evaluated"] == 1 and r["recall_u1"] == 1
    )  # the query is removed from the target first; its own name still matches
    assert RP.llm_reach(cp, emb)["concepts"] == 2
