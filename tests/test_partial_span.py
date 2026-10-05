"""CR-009 §4.1 / §11: rule M2 `partial_span` (no network, no key)."""

from collections import Counter

import spacy

from cumap.expert_kg.partial_span import find_partial_spans

NLP = spacy.load("en_core_web_sm")


def flags(span, quote, **kw):
    return find_partial_spans([span], quote, NLP, **kw)


def test_fires_on_handler_inside_signal_handler():
    f = flags(
        "handler",
        "The kernel invokes the signal handler when the interrupt arrives.",
        noun_forms=["signal"],
    )
    assert f and f[0].longer.lower() == "signal handler" and f[0].why == "compound"


def test_fires_on_a_plain_noun_noun_compound():
    f = flags("driver", "The kernel loads the network device driver at boot.")
    assert f and f[0].longer.lower() == "network device driver"


def test_does_not_fire_on_ordinary_modifiers():
    assert not flags("frame", "The switch examines each incoming frame before forwarding it.")
    assert not flags("capacitor", "Each cell stores one bit in a tiny capacitor that leaks charge.")


def test_does_not_fire_when_the_span_is_the_modifier_not_the_head():
    assert not flags("DRAM", "Each DRAM cell stores one bit in a capacitor.")
    assert not flags("Ethernet", "An Ethernet frame carries a 14-byte header.")


def test_does_not_fire_when_the_longer_candidate_is_already_an_item():
    assert not flags(
        "handler", "The kernel invokes the signal handler.", all_items=["signal handler"]
    )


def test_does_not_fire_when_the_short_form_also_occurs_alone_in_the_quote():
    assert not flags("handler", "A handler runs; the signal handler is installed first.")


def test_different_tokens_do_not_count():
    assert not flags("lock", "Databases use two-phase locking to serialise access.")


def test_r2_long_form_and_known_form_and_recurring_adjective_noun():
    q = "A cyclic redundancy check (CRC) detects errors."
    assert flags("redundancy check", q)[0].why in {"compound", "r2_long_form"}
    assert flags("table", "A forwarding table maps prefixes.", known_forms=["forwarding table"])[
        0
    ].why in {"compound", "known_form"}
    rec = Counter({"large page": 3})
    assert (
        flags("page", "The system uses a large page here.", recurring=rec)[0].why
        == "recurring_adj_noun"
    )
    assert not flags(
        "page", "The system uses a large page here.", recurring=Counter({"large page": 1})
    )


def test_clause_verbs_and_known_whole_terms_do_not_fire():
    assert not flags(
        "network performance",
        "It is important to understand factors that impact network performance.",
    )
    assert not flags(
        "CRC-32", "A 32-bit CRC code is commonly expressed as uses CRC-32.", noun_forms=["uses"]
    )
    assert not flags(
        "frame", "Each Ethernet frame is defined by the format.", known_forms=["frame"]
    )
