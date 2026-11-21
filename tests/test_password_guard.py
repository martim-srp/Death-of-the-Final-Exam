"""The password trap catches a password the player says outright, however weak it looks.

Before, "my password is hunter2" was caught but "Password is: hunter2", "the password is cat"
and "my pin is 1234" reached the model. Once a player says what their password IS, the value
counts. Ordinary questions about passwords must still get through.
"""

import pytest

from game import ai
from game.engine import Engine, looks_like_secret


@pytest.fixture(scope="module")
def vocabulary():
    return Engine()._vocabulary


@pytest.mark.parametrize(
    "text",
    [
        "my password is hunter2",
        "Password is: hunter2",
        "password: abc",
        "the password is cat",
        "My password was 1234",
        "pw = x9",
        "my pin is 1234",
        "PIN: 0000",
        "my passphrase is open sesame",
        'my password is "cat"',
        "a minha senha é gato",
        "a palavra-passe era benfica",
        "my password hunter2",
        "my password is Benfica2026!",
    ],
)
def test_a_password_said_outright_is_caught_however_weak(text, vocabulary):
    assert looks_like_secret(text, vocabulary)


@pytest.mark.parametrize(
    "text",
    [
        "I forgot my password",
        "What is your password?",
        "What was the password?",
        "the password is in the safe",
        "Is the password written somewhere?",
        "the password for the printer",
        "Was the pin changed?",
        "Your password is?",
        "Did you pass the exam?",
        "the pass is valid until 2027",
        "Where were you at 18:52?",
    ],
)
def test_questions_about_passwords_are_not_secrets(text, vocabulary):
    assert not looks_like_secret(text, vocabulary)


def test_a_weak_password_never_reaches_the_model():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    answer = ai.ask(engine, game, "companion", "Password is: cat", complete=lambda *_: pytest.fail("reached the model"))
    assert answer["blocked"] is True
    assert game.badges == ["spy_password"]
