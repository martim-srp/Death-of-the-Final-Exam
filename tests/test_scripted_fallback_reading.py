"""Without the AI (no key, the call failed, or the case used its AI questions), a typed question
is matched to a topic by its words. Common ways of asking now find their topic, and a model
reply wrapped in a sentence is still read."""

import pytest

from game import ai
from game.engine import Engine


@pytest.fixture(scope="module")
def engine():
    return Engine()


@pytest.mark.parametrize(
    "question, topic",
    [
        ("What about the TA?", "teaching_assistant"),
        ("Tell me about your TA.", "teaching_assistant"),
        ("What is your job?", "work"),
        ("Were you at the library?", "alibi"),
        ("Did you talk to the TA last night?", "alibi"),  # the longer phrase wins
        ("What was print job 88213?", "other"),  # "job" alone is not about their work
        ("Isn't a printer in the library?", "other"),
    ],
)
def test_common_questions_find_their_topic(engine, question, topic):
    assert ai._scripted_topic(question, engine.topics_for("professor")) == topic


def test_nobody_asks_the_ta_about_the_ta(engine):
    assert ai._scripted_topic("Are you the TA?", engine.topics_for("ta")) == "other"


def test_asking_the_professor_about_the_ta_without_the_ai_counts_as_that_topic(engine):
    game = engine.new_game(seed=1, variant="A")
    ai.ask(engine, game, "professor", "What does your TA do?", complete=lambda *_: None)
    assert game.history[-1]["topic"] == "teaching_assistant"
    assert game.history[-1]["fallback"] == "unreadable"


TOPICS = ["alibi", "exam", "other"]


@pytest.mark.parametrize(
    "raw",
    [
        'Here is my answer: {"reply": "I was home.", "topic": "alibi"}',
        '<think>Stay in character.</think>\n{"reply": "I was home.", "topic": "alibi"}',
        '{"reply": "I was home.", "topic": "alibi"} Hope that helps.',
    ],
)
def test_a_reply_wrapped_in_text_is_still_read(raw):
    assert ai._parse_answer(raw, TOPICS) == ("I was home.", "alibi")


@pytest.mark.parametrize(
    "raw",
    [
        "no object here",
        "Here: {not json}",
        'Here: ["reply", "I was home."]',
        'Here: {"reply": 42, "topic": "alibi"}',
        'Here: {"reply": "  ", "topic": "alibi"}',
        "} backwards {",
    ],
)
def test_wrapped_text_without_a_good_reply_is_still_unreadable(raw):
    assert ai._parse_answer(raw, TOPICS) is None


def test_a_wrapped_reply_still_has_its_topic_checked():
    raw = 'Sure. {"reply": "I was home.", "topic": "solution"}'
    assert ai._parse_answer(raw, TOPICS) == ("I was home.", "other")
