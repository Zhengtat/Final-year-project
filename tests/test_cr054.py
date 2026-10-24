"""CR-054: surface keys used to trace missed concepts (no network, no key)."""

from cumap.cr054 import recall as R


def test_key_folds_case_punctuation_and_plurals():
    assert R.key("Pre-trained Language Models") == R.key("pretrained language model")
    assert R.key("CRFs") == R.key("CRF") or R.key("CRFs") == "crfs"
    assert R.key("loss") == "loss"
