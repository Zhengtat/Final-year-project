"""CR-008 §8: lexicon (R0), guards, rule order and provenance in canonicalisation (no network)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

from cumap.expert_kg.alias_rules import AliasConfig
from cumap.expert_kg.canonical_rules import AliasContext
from cumap.expert_kg.canonicalize import ConceptRegistry, canonicalize_mention
from cumap.expert_kg.concepts import ConceptMentionCandidate
from cumap.expert_kg.lexicon import Lexicon, LexiconError
from cumap.llm.prompts import load_prompt

REPO = Path(__file__).parents[1]


def _lex(tmp_path, same=(), different=()):
    path = tmp_path / "lex.yaml"
    path.write_text(
        yaml.safe_dump({"version": "t", "same": list(same), "different": list(different)})
    )
    return Lexicon.load(path, AliasConfig.load())


def _same(i, forms, status="approved", scope="book:pd6e"):
    return {"id": i, "forms": forms, "scope": scope, "status": status, "source": "test"}


def _diff(i, forms, status="approved", scope="book:pd6e"):
    return {
        "id": i,
        "forms": forms,
        "kind": "confusable",
        "why": "t",
        "scope": scope,
        "status": status,
        "source": "test",
    }


def _mention(name, typ="Component", section="s1"):
    return ConceptMentionCandidate(name, typ, "used", None, "q", section)


class _NoLLM:
    def parse(self, **kw):  # any LLM call fails the test
        raise AssertionError("LLM called")


def _canon(reg, m, ctx, **kw):
    return canonicalize_mention(
        _NoLLM(),
        load_prompt(REPO / "prompts", "canonicalize", "v2"),
        reg,
        m,
        alias_ctx=ctx,
        type_aware=True,
        **kw,
    )


def _registry(*items):
    reg = ConceptRegistry(lambda t: np.zeros(3))
    for name, typ in items:
        reg.add_new(_mention(name, typ))
    return reg


def _ctx(lex, texts=None):
    texts = texts or {"s1": ""}
    return AliasContext.build(lex, texts, {k: 1 for k in texts}, [], lex.cfg)


def test_r0_same_set_merges_without_llm(tmp_path):
    ctx = _ctx(_lex(tmp_path, same=[_same("s1", ["ARP table", "ARP cache"])]))
    reg = _registry(("ARP cache", "Component"))
    out = _canon(reg, _mention("ARP table"), ctx)
    assert (out.decision, out.rule_id, out.llm_called) == ("same", "R0", False)


def test_proposed_entries_are_ignored(tmp_path):
    ctx = _ctx(_lex(tmp_path, same=[_same("s1", ["ARP table", "ARP cache"], status="proposed")]))
    reg = _registry(("ARP cache", "Component"))
    assert ctx.find_merge(reg.all(), "ARP table", "Component", "s1") is None


def test_different_pair_blocks_r1_and_r2_and_candidates(tmp_path):
    lex = _lex(tmp_path, different=[_diff("d1", ["routing table", "routing tables x"])])
    assert lex.is_different("Routing Table", "routing tables x")
    lex2 = _lex(tmp_path, different=[_diff("d1", ["CRC", "cyclic redundancy check"])])
    ctx = _ctx(lex2)
    reg = _registry(("cyclic redundancy check", "Mechanism"))
    assert ctx.find_merge(reg.all(), "CRC", "Mechanism", "s1") is None  # R2 pair, but guarded
    assert ctx.stats["blocked_by_lexicon"] >= 1
    # R1 variant is guarded as well
    lex3 = _lex(tmp_path, different=[_diff("d2", ["frame", "frames of x"])])
    assert (
        _ctx(lex3).find_merge(
            _registry(("frame", "DataUnit")).all(), "Frames of X", "DataUnit", "s1"
        )
        is None
    )


def test_validator_rejects_pair_in_both_lists_and_unsourced(tmp_path):
    with pytest.raises(LexiconError, match="both lists"):
        _lex(tmp_path, same=[_same("s1", ["a b", "c d"])], different=[_diff("d1", ["c d", "a b"])])
    bad = _same("s2", ["x y", "z w"])
    bad["source"] = ""
    with pytest.raises(LexiconError, match="no source"):
        _lex(tmp_path, same=[bad])
    with pytest.raises(LexiconError, match="scope"):
        _lex(tmp_path, same=[_same("s3", ["x y", "z w"], scope="chapter:x")])


def test_chapter_scope_is_respected(tmp_path):
    lex = _lex(tmp_path, different=[_diff("d1", ["bandwidth", "data rate"], scope="chapter:2")])
    assert lex.is_different("bandwidth", "data rate", chapter=2)
    assert not lex.is_different("bandwidth", "data rate", chapter=1)


def test_r1_r2_and_provenance(tmp_path):
    ctx = _ctx(_lex(tmp_path))
    reg = _registry(("frequency hopping", "Mechanism"), ("cyclic redundancy check", "Mechanism"))
    r1 = _canon(reg, _mention("frequency-hopping", "Mechanism"), ctx)
    assert (r1.rule_id, r1.llm_called) == ("R1", False) and r1.evidence_quote
    r2 = _canon(reg, _mention("cyclic redundancy check (CRC)", "Mechanism"), ctx)
    assert r2.rule_id == "R2"
    c = reg.get(r2.concept_id)
    assert c.canonical_name == "cyclic redundancy check" and "CRC" in c.aliases


def test_type_check_blocks_rule_merges(tmp_path):
    ctx = _ctx(_lex(tmp_path))
    reg = _registry(("frequency hopping", "Mechanism"))
    assert ctx.find_merge(reg.all(), "frequency-hopping", "Protocol", "s1") is None


def test_r3_strong_merges_but_weak_does_not(tmp_path):
    texts = {
        "s1": "We measure latency (also called delay) here. Last-mile links (or alternatively, access networks) exist."
    }
    lex = _lex(tmp_path)
    ctx = AliasContext.build(
        lex, texts, {"s1": 1}, ["latency", "delay", "last-mile link", "access network"], lex.cfg
    )
    reg = _registry(("latency", "Property"), ("last-mile link", "Component"))
    assert ctx.find_merge(reg.all(), "delay", "Property", "s1")[1].rule_id == "R3-strong"
    assert ctx.find_merge(reg.all(), "access network", "Component", "s1") is None
    assert ctx.weak_hints("access network", "last-mile link")


def test_ambiguous_acronym_is_scoped_not_global(tmp_path):
    texts = {
        "a": "The media access control (MAC) protocol.",
        "b": "A message authentication code (MAC) is added.",
    }
    lex = _lex(tmp_path)
    ctx = AliasContext.build(lex, texts, {"a": 2, "b": 8}, [], lex.cfg)
    reg = _registry(("media access control", "Mechanism"))
    assert ctx.find_merge(reg.all(), "MAC", "Mechanism", "a") is not None
    assert ctx.find_merge(reg.all(), "MAC", "Mechanism", "b") is None
