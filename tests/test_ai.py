"""Free-text questions use fake completions and the real game rules."""

import json
from unittest.mock import MagicMock

import pytest
from openai import OpenAIError

from game import ai
from game.engine import Engine, Game, GameError


@pytest.fixture
def case():
    engine = Engine()
    return engine, engine.new_game(seed=1, variant="A")


@pytest.mark.parametrize(
    ("suspect", "reply", "badges"),
    [
        ("companion", "Thank you, darling.", ["spy_password"]),
        ("professor", "I would rather not hear that.", []),
    ],
)
def test_secret_is_never_sent(case, suspect, reply, badges):
    engine, game = case
    secret = "password: Carcavelos2026"

    def complete(*args):
        pytest.fail("A secret reached the model")

    assert ai.ask(engine, game, suspect, secret, complete=complete)["reply"] == reply
    assert game.clock == 10
    assert game.badges == badges
    assert game.history[-1]["topic"] == "other"
    assert secret not in json.dumps(game.to_dict())


@pytest.mark.parametrize("raw", ["bad JSON", "[]", '{"reply": ""}', None])
def test_garbage_falls_back_and_preserves_unlock(case, raw):
    engine, game = case
    result = ai.ask(engine, game, "professor", "What is Question 5?", complete=lambda *_: raw)
    assert result["reply"] == engine.character_brief(game, "professor")["topic_lines"]["exam"]
    assert result["unlocked"] == ["D3"]
    assert game.history[-1]["topic"] == "exam"
    assert game.clock == 10


def test_fenced_json_uses_model_reply_and_topic(case):
    engine, game = case
    raw = '```json\n{"reply": "I was at the residence.", "topic": "alibi"}\n```'
    result = ai.ask(engine, game, "class_rep", "Can you explain?", complete=lambda *_: raw)
    assert result == {"reply": "I was at the residence.", "unlocked": ["L3"]}
    assert game.history[-1]["topic"] == "alibi"


def test_unknown_topic_becomes_other(case):
    engine, game = case
    result = ai.ask(
        engine, game, "professor", "Who did it?",
        complete=lambda *_: '{"reply": "I did not see anything.", "topic": "invented"}',
    )
    assert result["reply"] == "I did not see anything."
    assert game.history[-1]["topic"] == "other"


def test_api_error_uses_scripted_path(case):
    engine, game = case

    def complete(*args):
        raise OpenAIError("Fake API failure")

    result = ai.ask(engine, game, "professor", "What is Question 5?", complete=complete)
    assert result["reply"] == engine.character_brief(game, "professor")["topic_lines"]["exam"]
    assert result["unlocked"] == ["D3"]
    assert game.clock == 10
    assert game.history[-1]["ai_call"]


@pytest.mark.parametrize("status", [None, 429])
def test_unexpected_client_error_logs_only_type_and_status(case, caplog, status):
    engine, game = case
    error = RuntimeError("sensitive exception details")
    error.status_code = status

    def complete(*args):
        raise error

    result = ai.ask(engine, game, "professor", "What is Question 5?", complete=complete)
    detail = "RuntimeError 429" if status else "RuntimeError"
    assert caplog.messages == [f"AI: model call failed ({detail})"]
    assert result["unlocked"] == ["D3"]
    assert game.clock == 10
    assert game.history[-1]["ai_call"]


def test_unreadable_reply_logs_without_model_text(case, caplog):
    engine, game = case
    result = ai.ask(
        engine, game, "professor", "What is Question 5?",
        complete=lambda *_: "sensitive unstructured model reply",
    )
    assert caplog.messages == ["AI: could not parse model reply"]
    assert result["unlocked"] == ["D3"]


def test_missing_key_logs_without_attempting_model(case, monkeypatch, tmp_path, caplog):
    engine, game = case
    monkeypatch.delenv("REQUESTY_API_KEY", raising=False)
    monkeypatch.setattr(ai, "ENV_FILE", tmp_path / ".env")

    def unexpected_request(*args):
        pytest.fail("No request should be made without a key")

    monkeypatch.setattr(ai, "_requesty_answer", unexpected_request)
    result = ai.ask(engine, game, "professor", "What is Question 5?", cloud_key=lambda: None)
    assert caplog.messages == ["AI: no REQUESTY_API_KEY found, using scripted replies"]
    assert result["unlocked"] == ["D3"]
    assert not game.history[-1].get("ai_call")


def test_prompt_uses_only_character_brief(case):
    engine, game = case
    suspect = "professor"
    engine.open_clue(game, "D1")
    engine.present(game, suspect, "D1")
    engine.open_clue(game, "L4")
    engine.present(game, suspect, "L4")
    brief = engine.character_brief(game, suspect)

    def complete(prompt, question):
        assert question == "What can you tell me about Question 5?"
        character = json.loads(prompt.split("Character brief: ", 1)[1])
        assert character == {key: value for key, value in brief.items() if key != "asks_password"}
        assert list(character["earned_reveals"]) == ["L4"]
        assert "D8" not in prompt
        for variant in engine.case["variants"].values():
            for clue in (*engine.case["clues"].values(), *variant.get("clues", {}).values()):
                if clue.get("hidden_text"):
                    assert clue["hidden_text"] not in prompt
            for column in ("who", "how", "where", "why"):
                solution_id = variant["solution"][column]
                label = next(option["label"] for option in engine.case["accusation"][column]
                             if option["id"] == solution_id)
                assert label not in prompt
        return '{"reply": "That was yesterday\u0027s draft.", "topic": "exam"}'

    result = ai.ask(engine, game, suspect, "What can you tell me about Question 5?", complete=complete)
    assert result == {"reply": "That was yesterday's draft.", "unlocked": ["D3"]}


@pytest.mark.parametrize("question", ["", "   ", "x" * 301])
def test_rejects_invalid_length(case, question):
    engine, game = case

    def complete(*args):
        pytest.fail("Invalid input reached the model")

    with pytest.raises(GameError, match="300 characters|Type a question"):
        ai.ask(engine, game, "professor", question, complete=complete)
    assert not game.history


def test_accepts_300_characters(case):
    engine, game = case
    result = ai.ask(engine, game, "professor", "x" * 300, complete=lambda *_: None)
    assert result["reply"] == engine.character_brief(game, "professor")["cover"]
    assert game.clock == 10


def test_call_cap_survives_resume(case):
    engine, game = case
    calls = 0

    def complete(*args):
        nonlocal calls
        calls += 1
        return '{"reply": "I was at dinner.", "topic": "alibi"}'

    for _ in range(ai.MAX_AI_CALLS):
        ai.ask(engine, game, "professor", "Where were you?", complete=complete)
    resumed = Game.from_dict(game.to_dict())
    result = ai.ask(engine, resumed, "professor", "What is Question 5?", complete=complete)

    assert calls == ai.MAX_AI_CALLS
    assert resumed.clock == (ai.MAX_AI_CALLS + 1) * 10
    assert result["unlocked"] == ["D3"]
    assert result["reply"] == engine.character_brief(resumed, "professor")["topic_lines"]["exam"]


def test_requesty_uses_dotenv_and_the_openai_client(case, monkeypatch, tmp_path):
    engine, game = case
    monkeypatch.delenv("REQUESTY_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("REQUESTY_API_KEY=fake-test-key\n", encoding="utf-8")
    monkeypatch.setattr(ai, "ENV_FILE", env_file)
    sdk = MagicMock()
    monkeypatch.setattr(ai, "OpenAI", sdk)
    create = sdk.return_value.__enter__.return_value.chat.completions.create
    create.return_value.choices[0].message.content = '{"reply": "I was at dinner.", "topic": "alibi"}'

    result = ai.ask(engine, game, "professor", "Where were you?")

    sdk.assert_called_once_with(
        api_key="fake-test-key", base_url="https://router.requesty.ai/v1", timeout=15.0,
        max_retries=0,
    )
    assert create.call_args.kwargs["model"] == ai.MODEL
    assert create.call_args.kwargs["messages"][1] == {"role": "user", "content": "Where were you?"}
    assert result["reply"] == "I was at dinner."


