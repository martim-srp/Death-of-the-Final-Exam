"""The player is told when a suspect gives a scripted answer because the AI did not.

game/ai.py records why in the game's history (`fallback`), and app.py shows a short note
under the answer. Tests use fake completions only.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from game import ai
from game.engine import Engine

APP = str(Path(__file__).resolve().parents[1] / "app.py")
GOOD = '{"reply": "I was at dinner.", "topic": "alibi"}'


@pytest.fixture
def case():
    engine = Engine()
    return engine, engine.new_game(seed=1, variant="A")


@pytest.fixture
def no_key(monkeypatch, tmp_path):
    monkeypatch.delenv("REQUESTY_API_KEY", raising=False)
    monkeypatch.setattr(ai, "ENV_FILE", tmp_path / ".env")


def boom(*_):
    raise RuntimeError("provider down")


# ---- What game/ai.py records ------------------------------------------------------


def test_a_model_answer_records_no_fallback(case):
    engine, game = case
    ai.ask(engine, game, "professor", "Where were you?", complete=lambda *_: GOOD)
    assert "fallback" not in game.history[-1]


def test_no_key_is_recorded(case, no_key):
    engine, game = case
    ai.ask(engine, game, "professor", "Where were you?")
    assert game.history[-1]["fallback"] == "no_key"


def test_a_failed_call_is_recorded(case):
    engine, game = case
    ai.ask(engine, game, "professor", "Where were you?", complete=boom)
    assert game.history[-1]["fallback"] == "failed"


@pytest.mark.parametrize("raw", ["not json", "[]", '{"reply": ""}', None])
def test_an_unreadable_reply_is_recorded(case, raw):
    engine, game = case
    ai.ask(engine, game, "professor", "Where were you?", complete=lambda *_: raw)
    assert game.history[-1]["fallback"] == "unreadable"


def test_reaching_the_call_limit_is_recorded(case, monkeypatch):
    engine, game = case
    monkeypatch.setattr(ai, "MAX_AI_CALLS", 1)
    ai.ask(engine, game, "professor", "Where were you?", complete=lambda *_: GOOD)
    ai.ask(engine, game, "professor", "And after that?", complete=lambda *_: GOOD)
    assert "fallback" not in game.history[-2]
    assert game.history[-1]["fallback"] == "limit"


def test_the_password_trap_is_not_a_fallback(case):
    engine, game = case
    ai.ask(engine, game, "companion", "my password is hunter22", complete=lambda *_: GOOD)
    assert "fallback" not in game.history[-1]


def test_the_reason_survives_a_resume_link(case, no_key):
    from game.engine import Game

    engine, game = case
    ai.ask(engine, game, "professor", "Where were you?")
    assert Game.from_dict(game.to_dict()).history[-1]["fallback"] == "no_key"


# ---- What the player sees ---------------------------------------------------------


def ask_in_app(game, question="What is Question 5?"):
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    at.session_state["focus"] = ("suspect", "professor")
    at.session_state["suspect"] = "professor"
    at.secrets["REQUESTY_API_KEY"] = ""
    at.run()
    at.chat_input(key="typed").set_value(question).run()
    assert not at.exception
    return at


def chat(at):
    return "\n".join(m.value for m in at.markdown if 'class="chat"' in m.value)


def test_the_player_is_told_when_the_ai_is_not_connected(case, no_key, monkeypatch):
    engine, game = case
    monkeypatch.setattr(ai, "_requesty_answer", lambda *_: pytest.fail("no live model calls in tests"))
    at = ask_in_app(game)
    assert "isn&#x27;t connected" in chat(at)
    assert "yesterday" in chat(at)  # the scripted line is still shown


def test_no_note_when_the_ai_answers(case, monkeypatch):
    engine, game = case
    monkeypatch.setenv("REQUESTY_API_KEY", "fake-test-key")
    monkeypatch.setattr(ai, "_requesty_answer", lambda *_: GOOD)
    at = ask_in_app(game)
    assert "I was at dinner." in chat(at)
    assert "scripted answer" not in chat(at)


def test_every_reason_has_a_note():
    text = Path(APP).read_text(encoding="utf-8")
    for reason in ("no_key", "failed", "unreadable", "limit"):
        assert f'"{reason}":' in text, reason
