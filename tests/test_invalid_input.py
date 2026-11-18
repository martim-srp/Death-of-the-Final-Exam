"""Trying to break the game on purpose: bad input, damaged saves, a stale tab, a failing AI.

Each test is one way a player (or the model, or the server) can hand the game something
it did not expect. The game must answer with a message or a fallback, never an error page,
and must never show or log a key or a typed password.
"""

import json
import logging
import sqlite3
import tomllib
from pathlib import Path

import httpx2 as httpx  # the HTTP library the openai package uses
import openai
import pytest
from streamlit.testing.v1 import AppTest

import db
from game import ai
from game.engine import Engine, Game, GameError

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "app.py")
FAKE_KEY = "sk-test-0123456789abcdefSECRET"


@pytest.fixture(scope="module")
def engine():
    return Engine()


def store_raw(game_id, state):
    """Write a saved game's state exactly as given, as a damaged or foreign save would be."""
    db.create_game(Engine().new_game(seed=1))  # makes sure the table exists
    with sqlite3.connect(db._path()) as conn:
        conn.execute("INSERT INTO games (id, state, updated_at) VALUES (?, ?, 'x')", (game_id, state))


def open_app(query=None, **state):
    at = AppTest.from_file(APP, default_timeout=15)
    if query:
        at.query_params["game"] = query
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    return at


def chat_text(at):
    return "\n".join(item.value for item in at.markdown)


# ---- Damaged or foreign saved games ---------------------------------------------------


@pytest.mark.parametrize(
    "state",
    ["not json", "[]", '"a string"', "null", "{}", '{"seed": 1}'],
    ids=["not-json", "list", "string", "null", "empty", "missing-fields"],
)
def test_a_damaged_save_loads_as_not_found(state):
    store_raw("d" * 32, state)
    assert db.load_game("d" * 32) is None


def test_a_save_with_a_field_this_version_does_not_know_still_loads(engine):
    game = engine.new_game(seed=4, variant="B")
    state = {**game.to_dict(), "added_in_a_later_version": [1, 2]}
    assert Game.from_dict(state) == game
    store_raw("e" * 32, json.dumps(state))
    assert db.load_game("e" * 32) == game


@pytest.mark.parametrize("state", ["not json", "{}"], ids=["not-json", "empty"])
def test_a_damaged_resume_link_starts_a_new_case_instead_of_crashing(state):
    store_raw("f" * 32, state)
    at = open_app(query="f" * 32)
    assert not at.exception
    assert at.session_state["game"]["status"] == "playing"
    assert at.session_state["game_id"] != "f" * 32
    assert any("not found" in w.value for w in at.warning)


def test_a_save_from_a_variant_the_case_no_longer_has_starts_a_new_case(engine):
    state = {**engine.new_game(seed=1).to_dict(), "variant": "Z"}
    store_raw("g" * 32, json.dumps(state))
    at = open_app(query="g" * 32)
    assert not at.exception
    assert at.session_state["game"]["variant"] in engine.case["variants"]


@pytest.mark.parametrize("bad", ["x' OR '1'='1", "../../etc/passwd", "<script>", "a" * 500])
def test_a_malformed_resume_link_starts_a_new_case(bad):
    at = open_app(query=bad)
    assert not at.exception
    assert at.session_state["game"]["status"] == "playing"


# ---- Two tabs (or a laptop and a phone) on the same resume link -----------------------


def test_a_stale_tab_cannot_undo_a_cold_case(engine):
    """Tab A opens the game; tab B loses it and sees the answer; tab A must not then win."""
    game = engine.new_game(seed=1, variant="A")
    game_id = db.create_game(game)
    tab_a = open_app(query=game_id, intro_done=True)
    assert not tab_a.exception

    # Tab B: three wrong accusations, saved. The finale there shows the solution.
    other = db.load_game(game_id)
    solution = engine.case["variants"]["A"]["solution"]
    wrong = {**solution, "who": next(s for s in engine.case["suspects"] if s != solution["who"])}
    for _ in range(engine.case["max_strikes"]):
        engine.accuse(other, **wrong)
    db.save_game(game_id, other)

    # Back in tab A, with the right answer picked: the game is already cold.
    tab_a.session_state["focus"] = ("accuse", None)
    tab_a.run()
    assert not tab_a.exception
    assert tab_a.session_state["game"]["status"] == "cold"
    assert db.load_game(game_id).status == "cold"
    assert not any(b.key == "accuse_go" for b in tab_a.button)


def test_a_stale_tab_does_not_overwrite_progress_made_elsewhere(engine):
    game = engine.new_game(seed=1, variant="A")
    game_id = db.create_game(game)
    tab_a = open_app(query=game_id, intro_done=True)

    other = db.load_game(game_id)
    engine.open_clue(other, "D1")
    db.save_game(game_id, other)

    tab_a.session_state["focus"] = ("clue", "D2")
    tab_a.run()
    tab_a.button(key="open_D2").click().run()
    assert not tab_a.exception
    saved = db.load_game(game_id)
    assert saved.opened == ["D1", "D2"]
    assert saved.clock == 2 * engine.clock_rules["clue_cost"]


# ---- Repeated taps (a double click sends the same action twice) -----------------------


def test_opening_the_same_clue_twice_charges_once(engine):
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "D1")
    with pytest.raises(GameError, match="already open"):
        engine.open_clue(game, "D1")
    assert game.clock == engine.clock_rules["clue_cost"]


def test_accusing_after_the_case_is_closed_is_refused(engine):
    game = engine.new_game(seed=1, variant="A")
    engine.accuse(game, **engine.case["variants"]["A"]["solution"])
    with pytest.raises(GameError, match="closed"):
        engine.accuse(game, **engine.case["variants"]["A"]["solution"])
    assert game.strikes == 0


def test_a_second_confirm_after_the_accusation_does_nothing(engine):
    at = open_app(game=engine.new_game(seed=1, variant="A").to_dict(), intro_done=True, focus=("accuse", None))
    wrong = {**engine.case["variants"]["A"]["solution"], "who": "exchange"}
    for column, option_id in wrong.items():
        at.pills(key=f"accuse_{column}").set_value(option_id).run()
    at.button(key="accuse_go").click().run()
    at.button(key="confirm_accuse").click().run()
    at.run()  # the second click of a double click arrives after the dialog has closed
    assert not at.exception
    assert at.session_state["game"]["strikes"] == 1


# ---- Typed questions -------------------------------------------------------------------


@pytest.mark.parametrize("question", ["\n\n", "\t \t", "    \n  "])
def test_blank_questions_are_refused_and_cost_nothing(engine, question):
    game = engine.new_game(seed=1, variant="A")
    with pytest.raises(GameError, match="Type a question"):
        ai.ask(engine, game, "professor", question, complete=lambda *_: pytest.fail("reached the model"))
    assert game.clock == 0 and not game.history


def test_a_question_far_over_the_limit_is_refused_before_anything_else(engine):
    game = engine.new_game(seed=1, variant="A")
    with pytest.raises(GameError, match="300 characters"):
        ai.ask(engine, game, "companion", "my password is hunter22 " * 500, complete=lambda *_: pytest.fail("reached the model"))
    assert game.clock == 0 and not game.badges


def test_a_question_to_an_unknown_suspect_is_refused(engine):
    game = engine.new_game(seed=1, variant="A")
    with pytest.raises(GameError, match="no suspect"):
        ai.ask(engine, game, "the_butler", "Where were you?", complete=lambda *_: pytest.fail("reached the model"))


def test_a_question_after_the_case_is_closed_is_refused(engine):
    game = engine.new_game(seed=1, variant="A")
    engine.accuse(game, **engine.case["variants"]["A"]["solution"])
    with pytest.raises(GameError, match="closed"):
        ai.ask(engine, game, "professor", "Where were you?", complete=lambda *_: pytest.fail("reached the model"))


def test_html_in_a_question_is_shown_as_text(engine):
    at = open_app(game=engine.new_game(seed=1, variant="A").to_dict(), intro_done=True, focus=("suspect", "professor"),
                  suspect="professor")
    at.chat_input(key="typed").set_value("<b>bold</b> where were you last night?").run()
    assert not at.exception
    assert "&lt;b&gt;bold&lt;/b&gt;" in chat_text(at)
    assert "<b>bold</b>" not in chat_text(at)


def test_a_typed_password_is_not_shown_back_on_screen(engine, monkeypatch):
    monkeypatch.setattr(ai, "_requesty_answer", lambda *_: pytest.fail("a password reached the model"))
    at = open_app(game=engine.new_game(seed=1, variant="A").to_dict(), intro_done=True, focus=("suspect", "companion"),
                  suspect="companion")
    at.chat_input(key="typed").set_value("my password is Lisboa2026!").run()
    assert not at.exception
    assert "Lisboa2026" not in chat_text(at)
    assert "looked like a password" in chat_text(at)
    assert "Lisboa2026" not in json.dumps(at.session_state["game"])


def test_a_blocked_question_says_so(engine):
    game = engine.new_game(seed=1, variant="A")
    result = ai.ask(engine, game, "professor", "my key is sk-live-abcdefghijklmnop")
    assert result["blocked"] is True


def test_a_very_long_player_name_is_cut_and_escaped(engine):
    import report

    game = engine.new_game(seed=1, variant="A")
    engine.accuse(game, **engine.case["variants"]["A"]["solution"])
    text = report.build(engine, game, "<script>alert(1)</script>" * 10)
    assert "<script>" not in text


# ---- The AI misbehaving ------------------------------------------------------------------


def test_a_timeout_gives_the_scripted_answer(engine, caplog):
    game = engine.new_game(seed=1, variant="A")

    def complete(*_):
        raise openai.APITimeoutError(request=httpx.Request("POST", "https://router.requesty.ai/v1/chat/completions"))

    result = ai.ask(engine, game, "professor", "What is Question 5?", complete=complete)
    assert result["reply"] == engine.character_brief(game, "professor")["topic_lines"]["exam"]
    assert game.history[-1]["fallback"] == "failed"
    assert caplog.messages == ["AI: model call failed (APITimeoutError)"]


def test_a_rejected_key_gives_the_scripted_answer_and_never_logs_the_key(engine, caplog, monkeypatch):
    """Even if the server echoes the key back in its error, it is not logged or shown."""
    monkeypatch.setenv("REQUESTY_API_KEY", FAKE_KEY)
    game = engine.new_game(seed=1, variant="A")

    def rejected(api_key, prompt, text):
        assert api_key == FAKE_KEY
        assert FAKE_KEY not in prompt
        response = httpx.Response(401, request=httpx.Request("POST", "https://router.requesty.ai/v1"))
        raise openai.AuthenticationError(f"Invalid key {api_key}", response=response, body=None)

    monkeypatch.setattr(ai, "_requesty_answer", rejected)
    with caplog.at_level(logging.DEBUG):
        result = ai.ask(engine, game, "professor", "Where were you last night?")
    assert caplog.messages == ["AI: model call failed (AuthenticationError 401)"]
    assert FAKE_KEY not in caplog.text
    assert FAKE_KEY not in result["reply"]
    assert FAKE_KEY not in json.dumps(game.to_dict())


def test_an_overlong_model_reply_is_cut(engine):
    game = engine.new_game(seed=1, variant="A")
    rambling = "I was at dinner. " * 200
    raw = json.dumps({"reply": rambling, "topic": "alibi"})
    result = ai.ask(engine, game, "professor", "Where were you?", complete=lambda *_: raw)
    assert len(result["reply"]) <= ai.MAX_REPLY_LENGTH
    assert result["reply"].endswith("I was at dinner.")


def test_an_overlong_reply_without_sentences_is_cut_at_a_word():
    reply = ai._shorten("word " * 400)
    assert len(reply) <= ai.MAX_REPLY_LENGTH and reply.endswith("word…")


@pytest.mark.parametrize(
    "raw",
    ['{"reply": 42, "topic": "alibi"}', '{"reply": ["a"], "topic": "alibi"}', '{"reply": "   "}', "[]", "", None],
)
def test_a_reply_of_the_wrong_shape_gives_the_scripted_answer(engine, raw):
    game = engine.new_game(seed=1, variant="A")
    result = ai.ask(engine, game, "professor", "What is Question 5?", complete=lambda *_: raw)
    assert result["reply"] == engine.character_brief(game, "professor")["topic_lines"]["exam"]
    assert game.history[-1]["fallback"] == "unreadable"


# ---- What players can see when something goes wrong ------------------------------------


def test_players_never_see_error_details():
    config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert config["client"]["showErrorDetails"] == "type"


def test_secrets_files_are_ignored_by_git():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").split()
    assert ".env" in ignored and ".streamlit/secrets.toml" in ignored


# ---- Small fixes found while play-testing -----------------------------------------------


def test_editing_the_hunches_rebuilds_the_engine_on_the_live_site():
    import reloading

    assert "data/hunches.json" in reloading.SOURCES


def test_no_hunch_ends_a_sentence_with_two_dots(engine):
    """Initials such as I.A. already end with a dot."""
    for variant in engine.case["variants"]:
        game = engine.new_game(seed=1, variant=variant)
        for line in engine.hunch_lines.values():
            text = engine._fill(game, line["line"])
            assert ".." not in text.replace("...", ""), text
