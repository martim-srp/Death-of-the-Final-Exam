"""A time or a range of times in a typed question is an alibi question, not a password.

"Where were you between 11pm-1am?" used to be hidden as a password: "11pm-1am" mixes
letters and digits and has 8 characters. The question was not sent and still cost minutes.
"""

import pytest

from game import ai
from game.engine import Engine, looks_like_secret


@pytest.fixture(scope="module")
def engine():
    return Engine()


@pytest.mark.parametrize(
    "question",
    [
        "Where were you between 11pm-1am?",
        "What did you do from 10pm-2am last night?",
        "Were you at the library at 23h00-23h30?",
        "Were you there at 23h47min?",
        "Where were you from 11:30pm-12:15am?",
        "Were you in the cafeteria at 23.47h?",
        "Were you out between 11PM-1AM?",
    ],
)
def test_a_time_range_is_not_a_password(engine, question):
    assert not looks_like_secret(question, engine._vocabulary)


@pytest.mark.parametrize(
    "question",
    [
        "my password is 11pm-1am",  # once someone says what their password is, any value counts
        "Try hunter2024 on the printer",
        "The code is Lisboa2026, right?",
        "Is it 11pm-abc12345?",
        "Use sk-live-abcdefghijklmnop",
    ],
)
def test_passwords_are_still_caught(engine, question):
    assert looks_like_secret(question, engine._vocabulary)


def test_a_time_range_question_reaches_the_suspect(engine):
    game = engine.new_game(seed=1, variant="A")
    seen = []

    def fake(prompt, text):
        seen.append(text)
        return '{"reply": "I was in my room.", "topic": "alibi"}'

    result = ai.ask(engine, game, "class_rep", "Where were you between 11pm-1am?", complete=fake)
    assert seen == ["Where were you between 11pm-1am?"]
    assert "blocked" not in result
    assert result["reply"] == "I was in my room."
