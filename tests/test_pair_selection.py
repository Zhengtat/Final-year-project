from cumap.expert_kg.pair_selection import dedupe, select_pairs
from cumap.expert_kg.relations import CandidatePair


def cp(pid, sec, x, y, cue=0, count=1):
    return CandidatePair(pid, sec, x, y, "s", count, cue)


def scene():
    pairs = {
        "A": [
            cp("A1", "A", "h1", "h2", 1, 5),
            cp("A2", "A", "h1", "h3", 1, 4),
            cp("A3", "A", "h2", "h3", 0, 3),
        ],
        "B": [
            cp("B1", "B", "h1", "h2", 1, 9),  # duplicate of A1: dedup keeps the higher-ranked one
            cp("B2", "B", "m1", "m2", 1, 8),  # mentioned-only concepts, strong cue
            cp("B3", "B", "d1", "h4", 0, 1),
        ],  # rare defined concept d1 with a weak pair
    }
    roles = {
        "h1": "defined",
        "h2": "used",
        "h3": "used",
        "h4": "used",
        "d1": "defined",
        "m1": "mentioned",
        "m2": "mentioned",
    }
    return pairs, roles


def test_dedupe_keeps_one_entry_per_concept_pair_with_its_best_rank():
    pairs, _ = scene()
    pool = dedupe(pairs)
    assert len(pool) == 5 and {
        p.pair_id for p in pool if {p.concept_x_id, p.concept_y_id} == {"h1", "h2"}
    } == {"B1"}


def test_budget_is_respected_and_defined_used_concepts_are_covered_before_the_fill():
    pairs, roles = scene()
    sel = select_pairs(pairs, roles, budget=3, min_per_section=0, sample_unselected=10)
    assert len(sel.selected) == 3
    covered = {c for p in sel.selected for c in (p.concept_x_id, p.concept_y_id)}
    assert {"h1", "h2", "h3", "h4", "d1"} <= covered  # every defined/used concept covered first
    assert (
        "m1" not in covered
    )  # the strong-cue mentioned-only pair loses to coverage under a tight budget
    assert sel.stats["phase1_coverage"] == 3 and sel.stats["core_concepts_covered"] == 5


def test_mentioned_only_concepts_are_covered_in_the_fill_phase_by_cue_score():
    pairs, roles = scene()
    sel = select_pairs(pairs, roles, budget=5, min_per_section=0)
    ids = {p.pair_id for p in sel.selected}
    assert "B2" in ids and sel.stats["phase2_fill"] >= 1


def test_per_section_minimum_selects_each_sections_best_pairs_first():
    pairs, roles = scene()
    sel = select_pairs(pairs, roles, budget=4, min_per_section=1)
    assert {"A2", "B1"} & {p.pair_id for p in sel.selected} and sel.stats[
        "phase0_min_per_section"
    ] == 2


def test_unselected_sample_is_random_but_seeded_and_disjoint_from_selected():
    pairs = {"S": [cp(f"P{i}", "S", f"a{i}", f"b{i}", 0, 1) for i in range(30)]}
    roles = {}
    a = select_pairs(pairs, roles, budget=10, min_per_section=0, sample_unselected=8, seed=1)
    b = select_pairs(pairs, roles, budget=10, min_per_section=0, sample_unselected=8, seed=1)
    c = select_pairs(pairs, roles, budget=10, min_per_section=0, sample_unselected=8, seed=2)
    ids = lambda s: [p.pair_id for p in s.unselected_sample]
    assert ids(a) == ids(b) != ids(c) and len(ids(a)) == 8
    assert not set(ids(a)) & {p.pair_id for p in a.selected}
