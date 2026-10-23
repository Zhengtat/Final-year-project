"""CR-012 D3 (Research 2026-10-09): linear production-budget scaling of the relation-pair budget.
B(u) = min(candidate_pool_size, max(1, ceil(14.2 * word_count / 1000))); evaluation units: SciNLP document, P&D-E2E section.
The existing frozen candidate ranking / coverage policy is untouched; there is no benchmark-specific pair ranking."""

from __future__ import annotations

import math
from dataclasses import dataclass

PAIRS_PER_1000_WORDS = 14.2


def pair_budget(word_count: int, candidate_pool_size: int) -> int:
    return min(candidate_pool_size, max(1, math.ceil(PAIRS_PER_1000_WORDS * word_count / 1000)))


@dataclass(frozen=True)
class BudgetRecord:
    unit: str
    word_count: int
    eligible_candidate_pairs: int
    budget: int
    selected_pairs: int
    budget_saturated: bool
    gold_edge_pair_recall: float | None

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def budget_record(
    unit: str, word_count: int, eligible: int, selected: int, gold_edge_pair_recall: float | None
) -> BudgetRecord:
    b = pair_budget(word_count, eligible)
    return BudgetRecord(
        unit, word_count, eligible, b, selected, selected >= b, gold_edge_pair_recall
    )
