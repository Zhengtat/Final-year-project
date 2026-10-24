"""CR-052: span-difference classes and the gold-free extension rules (no network, no key)."""

from cumap.cr052 import extend as X
from cumap.cr052 import spans as S


def test_extension_rules_absorb_acronym_and_generic_head_only():
    t = [
        "word",
        "sense",
        "disambiguation",
        "(",
        "WSD",
        ")",
        "uses",
        "the",
        "GPT-3",
        "model",
        "and",
        "(",
        "a",
        ")",
        "list",
    ]
    assert X.extend(t, (0, 3), ("X-acr",)) == (0, 6)
    assert X.extend(t, (8, 9), ("X-head",)) == (8, 10)
    assert X.extend(t, (8, 9), ("X-acr",)) == (8, 9)
    assert X.extend(t, (11, 12), ("X-acr", "X-head")) == (11, 12)  # "( a )" is not an acronym


def test_diff_kinds():
    assert S.diff_kind(["the"], "extra") == "determiner"
    assert S.diff_kind(["(", "WSD", ")"], "missing") == "parenthetical_or_acronym"
    assert S.diff_kind(["of", "language", "models"], "missing") == "prepositional_tail"
    assert S.diff_kind(["standard"], "missing") == "modifier_missing"
