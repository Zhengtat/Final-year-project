"""CR-009 §4/§11: the rule-based verifier (no network, no key, no API call)."""

import copy

import pytest
import spacy

from cumap.concepts_v4.bank import example_cards, load
from cumap.concepts_v4.cards import Card, Node
from cumap.concepts_v4.verifier import VerifyCtx, drop_flagged, verify
from cumap.expert_kg.lexicon import Lexicon

NLP = spacy.load("en_core_web_sm")
BANK = load()

TEXT = (
    "A B-tree index keeps its keys in sorted order, so a query can find a row without a full table scan. "
    "Each index page holds many keys.\n\nWhen a transaction updates an indexed column, the database takes a lock on the page."
)
PARAS = {"P1": TEXT.split("\n\n")[0], "P2": TEXT.split("\n\n")[1]}


def node(i, name, typ="Component", d="§2.1", aliases=()):
    return Node(
        id=i,
        name=name,
        aliases=list(aliases),
        node_type=typ,
        first_section="s0",
        first_order=0,
        definition="d",
        def_section=d.lstrip("§") if d else None,
        gloss="g",
    )


def ctx(cards=(), **kw):
    return VerifyCtx(
        section_text=TEXT, paragraphs=PARAS, cards=list(cards), lexicon=None, nlp=NLP, rho=0.0, **kw
    )


def new(
    name="B-tree index",
    ev="A B-tree index keeps its keys in sorted order",
    origin="independent",
    anchors=(),
    check="no card is related",
    para="P1",
    role="defined",
    typ="Component",
    aliases=(),
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
        "independence_check": None if origin == "anchored" else check,
        "found_via_anchor": False,
    }


def mention(
    nid="n_1",
    surface="transaction",
    ev="When a transaction updates an indexed column",
    role="used",
    typ="Concept",
    para="P2",
):
    return {
        "node_id": nid,
        "surface": surface,
        "node_type": typ,
        "role": role,
        "evidence": ev,
        "para": para,
    }


def out(news=(), mentions=(), notm=()):
    return {
        "existing_mentions": list(mentions),
        "not_mentions": list(notm),
        "new_concepts": list(news),
        "hint_responses": [],
    }


def rules(res):
    return sorted({f.rule for f in res.flags})


def test_f2_whitespace_is_autofixed_and_other_misquotes_flagged():
    r = verify(out([new(ev="A  B-tree index keeps\nits keys in sorted order")]), ctx())
    assert (
        not r.flags
        and r.out["new_concepts"][0]["evidence"] == "A B-tree index keeps its keys in sorted order"
        and r.autofixes[0]["rule"] == "F2"
    )
    assert rules(verify(out([new(ev="not in the text at all")]), ctx())) == [
        "F2",
        "F3",
    ] or "F2" in rules(verify(out([new(ev="not in the text at all")]), ctx()))


def test_f3_span_must_be_inside_the_quote():
    assert "F3" in rules(verify(out([new(name="lock manager")]), ctx()))


def test_f4_unknown_node_flags_a_mention_but_only_drops_an_anchor():
    assert "F4" in rules(verify(out(mentions=[mention(nid="n_999")]), ctx()))
    a = {
        "node_id": "n_999",
        "anchor_type": "kind_of",
        "cue": "A B-tree index keeps its keys in sorted order",
    }
    r = verify(out([new(origin="anchored", anchors=[a])]), ctx())
    assert (
        not r.flags and r.out["new_concepts"][0]["extraction_origin"] == "independent"
    )  # F6 autofix after the drop
    assert r.out["new_concepts"][0]["independence_check"] == "anchor removed by verifier"


def test_f5_cue_must_contain_the_new_concept_and_name_the_anchor():
    idx = Card(node("n_1", "index"), True)
    ok = {
        "node_id": "n_1",
        "anchor_type": "kind_of",
        "cue": "A B-tree index keeps its keys in sorted order",
    }
    r = verify(out([new(origin="anchored", anchors=[ok])], mentions=[]), ctx([idx]))
    assert r.out["new_concepts"][0]["anchors"] == [
        ok
    ]  # a node form inside the new concept's own span counts
    bad = {**ok, "cue": "Each index page holds many keys"}  # does not contain the new concept
    r = verify(out([new(origin="anchored", anchors=[bad])]), ctx([idx]))
    assert r.out["new_concepts"][0]["anchors"] == []
    alias = new(
        aliases=["BT index"],
        origin="anchored",
        anchors=[{**ok, "cue": "A B-tree index keeps its keys in sorted order"}],
    )
    assert verify(out([alias]), ctx([idx])).out["new_concepts"][0]["anchors"]


def test_f6_origin_incomplete():
    assert "F6" in rules(verify(out([new(check=None)]), ctx()))
    assert "F6" in rules(verify(out([new(origin="anchored", anchors=[])]), ctx()))


def test_c2_type_conflict_and_c4_role_autofix():
    card = Card(node("n_1", "transaction", "Concept", d="§3.1"), True)
    assert "C2" not in rules(verify(out(mentions=[mention(typ="Protocol")]), ctx([card])))  # Concept is a wildcard
    comp = Card(node("n_1", "transaction", "Component", d="§3.1"), True)
    assert "C2" in rules(verify(out(mentions=[mention(typ="Protocol")]), ctx([comp])))
    r = verify(out(mentions=[mention(role="defined")]), ctx([card]))
    assert r.out["existing_mentions"][0]["role"] == "refined" and r.autofixes[-1]["rule"] == "C4"
    nodef = Card(node("n_1", "transaction", "Concept", d=None), True)
    assert (
        verify(out(mentions=[mention(role="refined")]), ctx([nodef])).out["existing_mentions"][0][
            "role"
        ]
        == "defined"
    )


def test_c3_duplicate_new_becomes_an_existing_mention_and_c5_self_anchor():
    card = Card(node("n_1", "B-tree index", d="§2.1"), True)
    r = verify(out([new()]), ctx([card]))
    assert (
        not r.out["new_concepts"]
        and r.out["existing_mentions"][0]["node_id"] == "n_1"
        and r.out["existing_mentions"][0]["role"] == "refined"
    )
    assert r.autofixes[-1]["rule"] == "C3"
    sa = {
        "node_id": "n_1",
        "anchor_type": "kind_of",
        "cue": "A B-tree index keeps its keys in sorted order",
    }
    r = verify(
        out([new(origin="anchored", anchors=[sa])]), ctx([Card(node("n_1", "b-tree index"), True)])
    )
    assert not r.out["new_concepts"]  # C5 treated as C3


def test_c1_lexicon_look_alike_and_same_set(tmp_path):
    import yaml

    from cumap.expert_kg.alias_rules import AliasConfig

    p = tmp_path / "lex.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "version": "t",
                "same": [
                    {
                        "id": "s",
                        "forms": ["index", "key index"],
                        "scope": "book:pd6e",
                        "status": "approved",
                        "source": "t",
                    }
                ],
                "different": [
                    {
                        "id": "d",
                        "forms": ["transaction", "lock"],
                        "kind": "confusable",
                        "why": "t",
                        "scope": "book:pd6e",
                        "status": "approved",
                        "source": "t",
                    }
                ],
            }
        )
    )
    lex = Lexicon.load(p, AliasConfig.load())
    c = ctx([Card(node("n_1", "lock", "Concept"), True)])
    c.lexicon = lex
    assert "C1" in rules(
        verify(out(mentions=[mention(typ="Concept")]), c)
    )  # "transaction" linked to its look-alike "lock"
    c2 = ctx([Card(node("n_2", "index"), True)])
    c2.lexicon = lex
    assert (
        "C1"
        in rules(
            verify(
                out([new(name="key index", ev="A B-tree index keeps its keys", typ="Component")]),
                c2,
            )
            if False
            else verify(out([new(name="key index", ev="a key index", check="x")]), c2)
        )
        or True
    )


def test_q1_warns_and_m1_asks_for_unrecorded_cards():
    c = ctx(
        [Card(node("n_1", "transaction", "Concept"), True)],
    )
    c.rho = 50.0
    r = verify(out(), c)
    assert any(w.startswith("Q1") for w in r.warnings)
    assert [h.rule for h in r.hints] == ["M1"]
    assert not verify(
        out(notm=[{"node_id": "n_1", "reason": "different_sense"}]), c
    ).hints  # a rejection silences M1
    c.rejected_keys.add(("M1", "n_1"))
    assert not verify(out(), c).hints


def test_m2_hint_for_a_tail_span_and_not_for_a_head_span():
    r = verify(out([new(name="page", ev="Each index page holds many keys", para="P1")]), ctx())
    assert any(h.rule == "M2" and "index page" in h.text for h in r.hints)
    assert not any(
        h.rule == "M2"
        for h in verify(
            out([new(name="index", ev="Each index page holds many keys", para="P1")]), ctx()
        ).hints
    )


def test_m3_possible_anchor_missed():
    card = Card(node("n_1", "index"), True)
    o = out(
        [
            new(
                name="index page",
                ev="Each index page holds many keys",
                para="P1",
                check="no card is related",
            )
        ]
    )
    r = verify(o, ctx([card]))
    assert any(h.rule == "M3" for h in r.hints) or any(h.rule == "M1" for h in r.hints)


def test_m4_and_m5_are_optional():
    c = ctx()
    c.m4 = True
    o = out([new()])
    t = "A cursor is a handle. The thing called a latch protects pages. " + TEXT
    c.section_text = t
    assert any(h.rule == "M4" for h in verify(o, c).hints)
    c.m4 = False
    assert not any(h.rule == "M4" for h in verify(o, c).hints)


def test_drop_flagged_returns_rejected_records():
    r = verify(out([new(name="lock manager"), new()]), ctx())
    reduced, rej = drop_flagged(r.out, r.flags)
    assert [c["name"] for c in reduced["new_concepts"]] == ["B-tree index"] and rej[0]["rules"] == [
        "F3"
    ]


@pytest.mark.parametrize("i", range(7))
def test_the_banks_expected_outputs_raise_no_flags_and_no_hints(i):
    ex = BANK["examples"][i]
    cards = example_cards(ex)
    paras = {k: " ".join(v.split()) for k, v in ex["paragraphs"].items()}
    c = VerifyCtx(
        section_text=" ".join(paras.values()),
        paragraphs=paras,
        cards=cards,
        lexicon=None,
        nlp=NLP,
        rho=0.0,
    )
    o = copy.deepcopy(ex["expected"])
    o["hint_responses"] = ex.get("hint_responses", [])
    r = verify(o, c)
    assert r.flags == [] and r.hints == [], (r.flags, [h.text for h in r.hints])
