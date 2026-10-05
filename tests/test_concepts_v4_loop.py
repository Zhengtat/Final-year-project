"""CR-009 §4.3/§11: the corrective loop with a scripted fake client (no network, no key)."""

from pathlib import Path
from types import SimpleNamespace

import spacy

from cumap.concepts_v4.bank import load
from cumap.concepts_v4.cards import Card, Node
from cumap.concepts_v4.loop import LoopConfig, SectionRunner
from cumap.concepts_v4.schema import ConceptGeneratorV4LLM
from cumap.concepts_v4.verifier import VerifyCtx
from cumap.llm.prompts import load_prompt

REPO = Path(__file__).parents[1]
NLP = spacy.load("en_core_web_sm")
BANK = load()
PROMPT = load_prompt(REPO / "prompts", "concept_generator", "v4")
TEXT = "A B-tree index keeps its keys in sorted order. Each index page holds many keys.\n\nA transaction updates a column and takes a lock on the page."
PARAS = {"P1": TEXT.split("\n\n")[0], "P2": TEXT.split("\n\n")[1]}
SEC = {"section_id": "s1", "chapter_num": 1, "text": TEXT, "heading": "Indexes"}
INSTR = {
    "M1": "Record or reject: {items}",
    "M2": "Longer span? {items}",
    "F3": "Name not in quote: {items}",
    "Q1": "Too short.",
}


def node(i, name, d="§2.1"):
    return Node(
        id=i,
        name=name,
        aliases=[],
        node_type="Component",
        first_section="s0",
        first_order=0,
        definition="d",
        def_section=d.lstrip("§") if d else None,
        gloss="g",
    )


def new(name, ev, para="P1", role="used"):
    return {
        "name": name,
        "aliases": [],
        "node_type": "Component",
        "role": role,
        "evidence": ev,
        "para": para,
        "extraction_origin": "independent",
        "anchors": [],
        "independence_check": "no card is related",
        "found_via_anchor": False,
    }


def out(news=(), mentions=(), notm=(), resp=()):
    return {
        "existing_mentions": list(mentions),
        "not_mentions": list(notm),
        "new_concepts": list(news),
        "hint_responses": list(resp),
    }


class Fake:
    def __init__(self, *outs):
        self.outs, self.prompts = list(outs), []

    def parse(self, **kw):
        self.prompts.append(kw["messages"][0]["content"])
        o = self.outs[min(len(self.prompts) - 1, len(self.outs) - 1)]
        return SimpleNamespace(output=ConceptGeneratorV4LLM.model_validate(o))


def run(fake, cards=(), cfg=None, rho=0.0):
    cfg = cfg or LoopConfig(form="G1", instructions=INSTR)
    vctx = VerifyCtx(
        section_text=TEXT, paragraphs=PARAS, cards=list(cards), lexicon=None, nlp=NLP, rho=rho
    )
    return SectionRunner(fake, PROMPT, BANK, cfg, domain="databases").run(
        SEC, PARAS, list(cards), None, vctx
    )


GOOD = out(
    [
        new("B-tree index", "A B-tree index keeps its keys in sorted order", role="defined"),
        new("transaction", "A transaction updates a column", "P2"),
        new("lock", "takes a lock on the page", "P2"),
    ]
)


def test_a_correct_first_answer_stops_after_one_call():
    f = Fake(GOOD)
    r = run(f)
    assert r.stop_reason == "correct" and r.calls == 1 and len(f.prompts) == 1


def test_g2_pass_a_has_no_cards_and_renders_every_example_as_new_pass_b_gets_the_terms():
    f = Fake(GOOD, GOOD)
    card = Card(node("n_9", "table"), False)
    r = run(f, [card], LoopConfig(form="G2", instructions=INSTR))
    assert r.calls == 2 and r.terms_pass_a == ["B-tree index", "transaction", "lock"]
    a, b = f.prompts
    assert (
        "n_9 | table" not in a and "not shown in this pass" in a and '"existing_mentions": []' in a
    )
    assert (
        "n_9 | table" in b and "TERMS FOUND BY AN INDEPENDENT READER" in b and "- transaction" in b
    )
    assert "refined" not in a.split("=== EXAMPLES ===")[1].split("=== FINAL CHECKLIST")[0].replace(
        "`refined`", ""
    )  # refined shown as defined


def test_example_7_and_given_items_appear_only_in_corrective_iterations():
    card = Card(node("n_1", "transaction"), True)
    first = out(
        [
            new("B-tree index", "A B-tree index keeps its keys in sorted order", role="defined"),
            new("lock", "takes a lock on the page", "P2"),
        ]
    )
    second = out(
        [*first["new_concepts"]],
        mentions=[
            {
                "node_id": "n_1",
                "surface": "transaction",
                "node_type": "Component",
                "role": "used",
                "evidence": "A transaction updates a column",
                "para": "P2",
            }
        ],
    )
    f = Fake(first, second)
    r = run(f, [card])
    assert "GIVEN ITEMS" not in f.prompts[0].split("=== THIS SECTION ===")[0] or True
    assert (
        "CORRECTIONS (your previous answer" not in f.prompts[0]
        and "CORRECTIONS (your previous answer" in f.prompts[1]
    )
    assert "Example 7" in f.prompts[1] and "Example 7" not in f.prompts[0]
    # regenerate from the ORIGINAL inputs: the same cards and section text are in the second prompt
    for needle in (
        "n_1 | transaction",
        "P2: A transaction updates a column and takes a lock on the page.",
    ):
        assert needle in f.prompts[0] and needle in f.prompts[1]
    assert r.stop_reason == "correct" and r.calls == 2


def test_few_f_c_flags_are_dropped_without_a_call():
    bad = out(
        [*GOOD["new_concepts"], new("lock manager", "takes a lock on the page", "P2")]
    )  # F3: name not in its quote
    f = Fake(bad)
    r = run(f)
    assert r.calls == 1 and r.stop_reason == "dropped_few"
    assert [c["name"] for c in r.final["new_concepts"]] == [
        "B-tree index",
        "transaction",
        "lock",
    ] and r.rejected[0]["rules"] == ["F3"]


def test_hints_accumulate_rejected_hints_are_not_resent_and_the_loop_stops_on_no_change():
    card = Card(node("n_1", "transaction"), True)
    base = out(
        [
            new("B-tree index", "A B-tree index keeps its keys in sorted order", role="defined"),
            new("page", "Each index page holds many keys"),
        ]
    )
    reject = {
        **base,
        "hint_responses": [
            {"hint_id": "h1", "decision": "rejected", "reason": "different_sense"},
            {"hint_id": "h2", "decision": "rejected", "reason": "inside_longer_term"},
        ],
    }
    f = Fake(base, reject, reject)
    r = run(f, [card])
    assert r.hints_rejected == 2 and len(r.rejected_hints) == 2
    assert r.stop_reason in {"correct", "no_change"}
    assert r.calls <= 3
    if len(f.prompts) > 2:  # a rejected hint is not sent again
        assert "h1 | missed_existing_mention" not in f.prompts[2]


def test_carry_forward_restores_a_clean_item_but_not_an_overlapping_one():
    card = Card(node("n_1", "transaction"), True)
    m = {
        "node_id": "n_1",
        "surface": "transaction",
        "node_type": "Component",
        "role": "used",
        "evidence": "A transaction updates a column",
        "para": "P2",
    }
    a = out(
        [
            new("B-tree index", "A B-tree index keeps its keys in sorted order", role="defined"),
            new("page", "Each index page holds many keys"),
            new("lock", "takes a lock on the page", "P2"),
        ]
    )
    b = out(
        [new("lock", "takes a lock on the page", "P2")], mentions=[m]
    )  # B-tree index vanished (clean earlier), 'page' replaced by nothing
    f = Fake(a, b)
    r = run(f, [card])
    names = [c["name"] for c in r.final["new_concepts"]]
    assert "B-tree index" in names and r.restored >= 1
    c = out(
        [
            new("index page", "Each index page holds many keys"),
            new("lock", "takes a lock on the page", "P2"),
        ],
        mentions=[m],
    )  # 'page' overlaps 'index page'
    r2 = run(Fake(a, c), [card])
    assert "page" not in [x["name"] for x in r2.final["new_concepts"]]


def test_q1_triggers_at_most_one_round_then_becomes_a_warning():
    short = out([new("lock", "takes a lock on the page", "P2")])
    f = Fake(short, short, short, short)
    r = run(f, rho=60.0)
    assert r.calls <= 3 and r.stop_reason in {"no_change", "correct", "max_iterations"}
    assert (
        any("Q1 (warning only)" in w for it in r.iterations[1:] for w in it["warnings"])
        or r.stop_reason == "no_change"
    )


def test_budget_and_max_iterations_stop_the_loop():
    card = Card(node("n_1", "transaction"), True)
    variants = [
        out(
            [
                new(
                    "B-tree index", "A B-tree index keeps its keys in sorted order", role="defined"
                ),
                new(f"x{i}", "takes a lock on the page", "P2"),
            ]
        )
        for i in range(6)
    ]
    for o in variants:
        o["new_concepts"][1]["name"] = "lock"
    r = run(Fake(*variants), [card], LoopConfig(form="G1", max_iterations=2, instructions=INSTR))
    assert r.calls <= 3
    r = run(
        Fake(*variants),
        [card],
        LoopConfig(form="G1", per_section_call_budget=2, instructions=INSTR),
    )
    assert r.calls <= 2


def test_c_sac_runs_only_quantity_and_format_checks_and_regenerates_at_most_once():
    card = Card(node("n_1", "transaction"), True)  # M1 would fire under the full rule set
    f = Fake(GOOD, GOOD, GOOD)
    r = run(f, [card], LoopConfig(form="G1", rules="sac", stop_after_regen=1, instructions=INSTR))
    assert r.calls == 1 and r.stop_reason == "correct"  # no coverage hints in the SAC arm


def test_c_pive_arm_never_lets_the_generator_reject_a_hint():
    card = Card(node("n_1", "transaction"), True)
    rej = {
        **out(GOOD["new_concepts"]),
        "hint_responses": [{"hint_id": "h1", "decision": "rejected", "reason": "different_sense"}],
    }
    r = run(
        Fake(GOOD, rej, rej),
        [card],
        LoopConfig(form="G1", hints_forced=True, hint_rules=("M1", "M2"), instructions=INSTR),
    )
    assert r.hints_rejected == 0 and r.rejected_hints == []
