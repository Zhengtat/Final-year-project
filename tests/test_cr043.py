"""CR-043: SciNLP paper sets, P0 split and the scorecard renderer (no network, no key, test split never used)."""

from types import SimpleNamespace

from cumap.cr012.adapters import SciNLPAdapter
from cumap.cr019.stage_b import SC_DEV
from cumap.cr043 import eval as E
from cumap.cr043.papers import first_set
from cumap.cr043.run import run_id


def test_first_set_is_dev_plus_train_and_deterministic():
    a, b = first_set(), first_set()
    assert a == b and len(a) == 20
    assert [d for s, d in a if s == "dev"] == list(SC_DEV)
    test_docs = {d.doc_key for d in SciNLPAdapter().load_documents("test")}
    assert not test_docs & {d for _, d in a}
    assert {s for s, _ in a} == {"dev", "train"}


def test_run_id_naming():
    assert run_id("P05-1008.grobid") == "cr012_scinlp_cr043base_P05_1008_grobid_E0"


def test_p0_split_by_sentence():
    doc = SimpleNamespace(sentence_ends=[10, 20])
    rel = lambda a, b: SimpleNamespace(src_span=a, tgt_span=b)
    gold = SimpleNamespace(
        relations=[rel((1, 2), (5, 6)), rel((1, 2), (12, 13)), rel((14, 15), (16, 17))]
    )
    out = E.p0_split(doc, gold, ["P0", "P0", "R0"])
    assert out == {"P0_same_sentence": 1, "P0_cross_sentence": 1}


def test_markdown_renders_minimal_result():
    z = {"tp": 1, "fp": 1, "fn": 1, "precision": 0.5, "recall": 0.5, "f1": 0.5}
    v = {
        "concept_entity_strict": z,
        "relation_strict": z,
        "relation_strict_dev": z,
        "relation_strict_train": z,
    }
    r = {"tag": "t", "papers": ["p"], "missing": [], "graph": {}, "variants": {"IDXR1-P1": v},
         "pair_recall_analogue": {"reached": 1, "endpoints_present": 2, "rate": 0.5},
         "relation_macro_f1": {"macro_f1": 0.5, "classes": 1, "population": 2},
         "hierarchy_direction_H2": z, "hierarchy_direct_H2": z, "hierarchy_surface_ancestor_H2": z, "fact_f1_surf_r1": None,
         "earliest_failure": {"N0": 1, "P0": 1}, "p0_split": {"P0_same_sentence": 1},
         "per_paper": {"p": {"split": "dev", "f1": 0.5, "tp": 1, "gold": 2, "edges_predicted": 2}},
         "usage": {"usd": 0.0, "calls": 0}}  # fmt: skip
    md = E.markdown(r)
    assert "IDXR1-P1" in md and "P0 split: same sentence" in md and "| p | dev |" in md
    assert "A1-DIR" in md and "label-strict (A1)" in md
