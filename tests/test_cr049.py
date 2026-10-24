"""CR-049: context packs, v2 prompt rendering, row selection (no network, no key)."""

from cumap.cr049 import measure as M
from cumap.expert_kg import identity_judge as IJ


def test_context_pack_puts_the_own_sentence_first_and_matches_whole_words():
    sents = [
        "A routing table lists routes.",
        "Rerouting tables is odd.",
        "The routing table grows.",
        "routing table x",
        "routing table y",
    ]
    pack = IJ.context_pack(sents, ["routing table"], first="Our routing table.", k=3)
    assert pack == [
        "Our routing table.",
        "A routing table lists routes.",
        "The routing table grows.",
    ]
    assert IJ.context_pack(
        sents, ["routing table"], exclude="A routing table lists routes.", k=1
    ) == ["The routing table grows."]


def test_v2_prompt_renders_both_packs_and_v1_is_unchanged():
    v2 = IJ.load_judge_prompt("v2")
    text = v2.render(domain="d", surface="s", target_name="t", target_aliases="none", target_type="T", target_gloss="none",
                     term_context=IJ.render_pack(["one."]), concept_context=IJ.render_pack([]))  # fmt: skip
    assert "- one." in text and "(no other sentence uses it)" in text and "TERM pack" in text
    assert IJ.load_judge_prompt().version == "v1" and IJ.JUDGE_MODES == ("off", "v1")


def test_rows_leave_out_scinlp_test_and_keep_the_fixed_split():
    dev, held = M.rows("dev"), M.rows("heldout")
    assert all(r["dataset"] != "scinlp_test" for r in dev + held)
    assert not {r["key"] for r in dev} & {r["key"] for r in held}
    assert (len(dev), len(held)) == (69, 65)
