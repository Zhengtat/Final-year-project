from cumap.expert_kg.canonicalize import Mention, RegisteredConcept
from cumap.expert_kg.roles import (
    SectionText,
    apply_first_occurrence,
    apply_role_rules,
    first_occurrences,
)

ORDER = {"1.1": 0, "2.1": 1, "3.3": 2, "3.4": 3}


def concept(mentions, definition=None, cid="c_network", name="network", aliases=()):
    return RegisteredConcept(cid, name, "Concept", definition, "3.3", list(aliases), mentions)


def test_defined_is_kept_only_on_the_first_definition_in_book_order_and_later_ones_become_refined():
    c = concept(
        [
            Mention("3.3", "defined", "we use network to mean", "a switched network"),
            Mention("1.1", "defined", "a network consists of nodes", "nodes joined by links"),
            Mention("2.1", "used", "the network"),
            Mention("3.4", "defined", "a network is also", "again"),
        ]
    )
    apply_role_rules(c, ORDER)
    assert [(m.section_id, m.role) for m in c.mentions] == [
        ("1.1", "defined"),
        ("2.1", "used"),
        ("3.3", "refined"),
        ("3.4", "refined"),
    ]
    assert (
        c.definition == "nodes joined by links"
    )  # first definition becomes the canonical description
    assert [h["section_id"] for h in c.description_history] == ["3.3", "3.4"]
    assert c.mentions[2].quote == "we use network to mean"  # evidence kept


def test_description_history_is_append_only_and_idempotent():
    c = concept(
        [Mention("1.1", "defined", "q1", "d1"), Mention("3.3", "defined", "q2", "d2")],
        definition="original",
    )
    apply_role_rules(c, ORDER)
    apply_role_rules(c, ORDER)  # running twice must not duplicate or overwrite
    assert (
        c.definition == "original"
        and len(c.description_history) == 1
        and c.mentions[1].role == "refined"
    )
    c.mentions.append(Mention("3.4", "defined", "q3", "d3"))
    apply_role_rules(c, ORDER)
    assert [h["definition"] for h in c.description_history] == ["d2", "d3"]


def test_first_occurrence_is_the_first_longest_match_section_not_the_first_extraction():
    rate = RegisteredConcept("c_rate", "bit rate", "Parameter", None, "3.3", [], [])
    bit = RegisteredConcept("c_bit", "bit", "Concept", None, "3.3", [], [])
    secs = [
        SectionText("3.3", 3, 2, "A bit is one binary digit."),
        SectionText("2.1", 2, 1, "The bit rate is half the baud rate."),
        SectionText("1.1", 1, 0, "Nothing relevant here."),
    ]
    found = first_occurrences([rate, bit], secs)
    assert found["c_rate"].section_id == "2.1"
    assert (
        found["c_bit"].section_id == "3.3"
    )  # 'bit' inside 'bit rate' (2.1) does not count as a mention of 'bit'
    chapters = apply_first_occurrence([rate, bit], secs)
    assert chapters == {"c_rate": 2, "c_bit": 3} and rate.first_introduced == "2.1"
