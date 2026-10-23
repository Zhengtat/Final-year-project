from itertools import pairwise

from cumap.expert_kg.mentions import MentionMatcher, build_vocab, default_lemma, tokenize

VOCAB = {
    "bit": "c_bit",
    "bit rate": "c_bit_rate",
    "bit stream": "c_bit_stream",
    "baud rate": "c_baud",
    "switch": "c_switch",
    "switching": "c_switching",
    "frame": "c_frame",
    "ip": "c_ip",
    "internet protocol": "c_ip",
    "query": "c_query",
}


def spans(text, vocab=VOCAB):
    return [(m.surface, m.concept_id) for m in MentionMatcher(vocab).find(text)]


def test_longest_match_beats_the_shorter_concept_and_never_overlaps():
    assert spans("The bit rate is half the baud rate.") == [
        ("bit rate", "c_bit_rate"),
        ("baud rate", "c_baud"),
    ]
    assert spans("A single bit and a bit stream differ.") == [
        ("bit", "c_bit"),
        ("bit stream", "c_bit_stream"),
    ]
    found = MentionMatcher(VOCAB).find("bit rate of the bit stream")
    assert all(a.end <= b.start for a, b in pairwise(found))  # non-overlapping
    assert [m.surface for m in found].count(
        "bit"
    ) == 0  # 'bit' is not also matched inside the longer spans


def test_token_boundaries_case_and_plurals():
    assert spans("An orbit and a rabbit are not a bit.") == [
        ("bit", "c_bit")
    ]  # not inside 'orbit' / 'rabbit'
    assert spans("BIT RATE and Frames and SWITCHES") == [
        ("BIT RATE", "c_bit_rate"),
        ("Frames", "c_frame"),
        ("SWITCHES", "c_switch"),
    ]
    assert spans("Both queries were slow.") == [("queries", "c_query")]
    assert spans("switching is not a switch") == [
        ("switching", "c_switching"),
        ("switch", "c_switch"),
    ]  # device vs process kept apart


def test_aliases_and_punctuation():
    assert spans("the Internet Protocol (IP) header") == [
        ("Internet Protocol", "c_ip"),
        ("IP", "c_ip"),
    ]
    assert spans("(query, frame) pairs") == [("query", "c_query"), ("frame", "c_frame")]


def test_build_vocab_and_lemma_and_tokenizer():
    vocab = build_vocab(
        [{"concept_id": "c1", "canonical_name": "Bit Rate", "aliases": ["bitrate"]}]
    )
    assert vocab == {"bit rate": "c1", "bitrate": "c1"}
    assert [
        default_lemma(w) for w in ["queries", "switches", "frames", "class", "status", "is"]
    ] == ["query", "switch", "frame", "class", "status", "is"]
    assert [t for _, _, t in tokenize("Manchester-encoded bits")] == ["manchester-encoded", "bit"]
