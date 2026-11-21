"""Tapped questions (and typed ones when the AI is off) get an answer that fits the question.

Before, a suspect with no scripted line for a topic answered with their whole cover
story, so "What is your job here?" got an alibi back, and the Teaching Assistant gave
the same paragraph to every question.
"""

import pytest

from game import ai
from game.case import load_case
from game.engine import Engine
from tests.test_board_game import page, start

CASE = load_case()
SUSPECTS = list(CASE["suspects"])
VARIANTS = sorted(CASE["variants"])


def brief(variant, suspect):
    engine = Engine()
    return engine.character_brief(engine.new_game(seed=1, variant=variant), suspect)


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("suspect", SUSPECTS)
@pytest.mark.parametrize("topic", sorted(ai.DODGES))
def test_no_question_outside_the_alibi_is_answered_with_the_cover_story(variant, suspect, topic):
    b = brief(variant, suspect)
    reply = ai.scripted_reply(b, topic)
    assert reply
    assert reply != b["cover"]
    assert reply == (b["topic_lines"].get(topic) or ai.DODGES[topic])


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("suspect", SUSPECTS)
def test_alibi_and_other_questions_still_get_the_cover_story(variant, suspect):
    b = brief(variant, suspect)
    for topic in ("alibi", "other"):
        assert ai.scripted_reply(b, topic) == (b["topic_lines"].get(topic) or b["cover"])


def test_a_scripted_line_in_the_case_file_beats_the_dodge():
    assert ai.scripted_reply(brief("A", "professor"), "exam") == brief("A", "professor")["topic_lines"]["exam"]


def test_dodges_cover_only_known_topics_and_name_no_culprit():
    assert set(ai.DODGES) <= set(CASE["topics"]) - {"alibi", "other"}
    for line in ai.DODGES.values():
        for suspect in ("Class Representative", "Exchange Student", "Companion"):
            assert suspect not in line  # the Professor and the TA are named by role only, never accused


def test_typed_question_with_the_ai_off_gets_the_dodge(monkeypatch):
    monkeypatch.delenv("REQUESTY_API_KEY", raising=False)
    monkeypatch.setattr(ai, "ENV_FILE", ai.ENV_FILE.with_name("no-such.env"))
    engine = Engine()
    game = engine.new_game(seed=1, variant="C")
    result = ai.ask(engine, game, "companion", "What is your work, as a consultant?")
    assert result["reply"] == ai.DODGES["work"]
    assert result["unlocked"] == ["D8"]


def test_tapping_your_job_gets_an_answer_about_work_not_the_alibi():
    at = start(variant="C", focus=("suspect", "companion"), suspect="companion")
    at.pills(key="ask_topic").set_value("work").run()
    assert not at.exception
    chat = page(at)
    assert "My work has nothing to do with this." in chat
    assert "dinner with him in Chiado" not in chat  # her cover story


def test_the_ta_is_not_offered_a_question_about_the_ta():
    at = start(variant="A", focus=("suspect", "ta"), suspect="ta")
    assert "The TA" not in at.pills(key="ask_topic").options
    at = start(variant="A", focus=("suspect", "professor"), suspect="professor")
    assert "The TA" in at.pills(key="ask_topic").options
