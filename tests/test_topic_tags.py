"""The model's topic tag is matched however it is capitalised or spaced, so a question never loses its unlock."""

import pytest

from game import ai
from game.case import load_case
from game.engine import Engine

TOPICS = load_case()["topics"]


def parse(topic):
    raw = '{"reply": "hi", "topic": %s}' % topic
    return ai._parse_answer(raw, TOPICS)


@pytest.mark.parametrize("tag", ['"Alibi"', '" alibi "', '"ALIBI"', '"alibi\\n"'])
def test_capitals_and_spaces_still_match_the_topic(tag):
    assert parse(tag) == ("hi", "alibi")


@pytest.mark.parametrize("tag", ['"the_weather"', '"Al ibi"', '""', "5", "null", '["alibi"]'])
def test_anything_else_is_other(tag):
    assert parse(tag) == ("hi", "other")


def test_an_uppercase_tag_from_the_model_still_unlocks_the_clue():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    reply = '{"reply": "I was in my room all evening.", "topic": "Alibi"}'
    # The question has no alibi keyword, so only the model's tag can unlock L3.
    result = ai.ask(engine, game, "class_rep", "Tell me about yourself.", complete=lambda *_: reply)
    assert result["reply"] == "I was in my room all evening."
    assert result["unlocked"] == ["L3"]
    assert game.history[-1]["topic"] == "alibi"
