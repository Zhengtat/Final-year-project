from __future__ import annotations

from cumap.data.ids import answer_id, question_id


def test_question_id_stable_across_calls():
    q = "What is the difference between TCP and UDP?"
    assert question_id(q) == question_id(q)


def test_question_id_ignores_incidental_whitespace_and_case():
    a = "What is   the difference\nbetween TCP and UDP?  "
    b = "what is the difference between tcp and udp?"
    assert question_id(a) == question_id(b)


def test_question_id_differs_for_different_questions():
    assert question_id("Question A?") != question_id("Question B?")


def test_question_id_format():
    qid = question_id("Some question?")
    assert qid.startswith("q_")
    assert len(qid) == len("q_") + 8


def test_answer_id_stable_and_scoped_to_question():
    qid = question_id("Some question?")
    a1 = answer_id(qid, "My answer.")
    a2 = answer_id(qid, "My answer.")
    assert a1 == a2
    assert a1.startswith("a_")
    assert len(a1) == len("a_") + 10


def test_answer_id_differs_across_questions_for_same_answer_text():
    q1 = question_id("Question A?")
    q2 = question_id("Question B?")
    assert answer_id(q1, "same text") != answer_id(q2, "same text")
