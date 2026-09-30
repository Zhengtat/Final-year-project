from cumap.organisation.communities import jaccard, track_communities
from cumap.organisation.config import load_config

CFG = load_config().communities


def fs(*xs):
    return frozenset(f"c{x}" for x in xs)


def _track(prev, groups, counter=None, prefix="k"):
    return track_communities(prev, groups, counter if counter is not None else [0], prefix, CFG)


def _types(res):
    return sorted((e.type, tuple(e.subject_ids)) for e in res.events)


def test_first_snapshot_is_all_births_with_stable_ids():
    a, b = fs(*range(1, 7)), fs(*range(7, 13))
    r = _track(None, [b, a])
    assert set(r.state.values()) == {a, b} and {e.type for e in r.events} == {"community_birth"}
    assert r.state["k1"] == a  # larger (then lexicographic) community gets the first id


def test_continue_grow_shrink_and_changed_flag():
    counter = [0]
    s1 = _track(None, [fs(*range(1, 11)), fs(*range(11, 21)), fs(*range(21, 31))], counter).state
    a, b, c = list(s1)
    r = _track(
        s1,
        [fs(*range(1, 11)) | fs(31), fs(*range(11, 21)) | fs(*range(31, 39)), fs(*range(21, 26))],
        counter,
    )
    kinds = {tuple(e.subject_ids): e.type for e in r.events}
    assert kinds[(a,)] == "community_continue"  # +10% only
    assert kinds[(b,)] == "community_grow"  # +80%
    assert kinds[(c,)] == "community_shrink"  # -50%
    assert jaccard(s1[a], r.state[a]) > 0.7 and a not in r.changed
    assert b in r.changed  # jaccard 10/18 < 0.7


def test_merge_split_birth_death_over_three_snapshots():
    counter = [0]
    s1 = _track(
        None, [fs(*range(1, 9)), fs(*range(9, 17)), fs(*range(17, 25)), fs(*range(25, 33))], counter
    ).state
    a, b, c, d = list(s1)
    # snapshot 2: b and c merge; a splits into a1 / a2; d disappears; e is born
    a1, a2 = fs(1, 2, 3, 4), fs(5, 6, 7, 8)
    bc = fs(*range(9, 25))
    e = fs(*range(40, 46))
    r2 = _track(s1, [a1, a2, bc, e], counter)
    types = {t for t, _ in _types(r2)}
    assert {"community_merge", "community_split", "community_birth", "community_death"} <= types
    merge = next(x for x in r2.events if x.type == "community_merge")
    assert set(merge.subject_ids[1:]) == {b, c}
    split = next(x for x in r2.events if x.type == "community_split")
    assert split.subject_ids[0] == a and len(split.subject_ids) == 3
    assert next(x for x in r2.events if x.type == "community_death").subject_ids == [d]
    birth = next(x for x in r2.events if x.type == "community_birth")
    assert r2.state[birth.subject_ids[0]] == e
    # snapshot 3: everything continues unchanged -> ids persist
    r3 = _track(r2.state, list(r2.state.values()), counter)
    assert r3.state == r2.state and {x.type for x in r3.events} == {"community_continue"}
    assert r3.changed == set()
