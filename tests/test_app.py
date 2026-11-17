"""Smoke tests for the Streamlit interface, using Streamlit's built-in test runner."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from game.engine import Engine

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def start(variant="A", seed=1):
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = Engine().new_game(seed=seed, variant=variant).to_dict()
    at.run()
    assert not at.exception
    return at


def button(at, starts_with):
    return next(b for b in at.button if b.label.startswith(starts_with))


def test_app_starts_at_midnight():
    at = start()
    assert at.metric[0].value == "00:00"


def test_opening_a_clue_moves_the_clock():
    at = start()
    button(at, "Open 📄 D1").click().run()
    assert not at.exception
    assert at.metric[0].value == "00:30"


def test_locked_clue_has_no_open_button():
    at = start()
    assert not any(b.label.startswith("Open 📄 D2") for b in at.button)


def test_wrong_accusation_shows_how_many_are_right():
    at = start()
    at.radio(key="accuse_who").set_value("exchange")
    button(at, "Make the accusation").click().run()
    assert not at.exception
    assert any("of 4 are right" in w.value for w in at.warning)


def test_right_accusation_closes_the_case():
    at = start()
    button(at, "Make the accusation").click().run()  # defaults are variant A's answer
    assert any("Case solved" in s.value for s in at.success)


# ---- Saved games ---------------------------------------------------------------


def test_new_visit_creates_a_saved_game_with_a_resume_link():
    import db

    at = AppTest.from_file(APP, default_timeout=10)
    at.run()
    assert not at.exception
    game_id = at.query_params["game"]
    assert db.load_game(game_id) is not None


def test_resume_link_restores_the_game():
    import db

    game = Engine().new_game(seed=4, variant="B")
    Engine().open_clue(game, "D1")
    game_id = db.create_game(game)
    at = AppTest.from_file(APP, default_timeout=10)
    at.query_params["game"] = game_id
    at.run()
    assert not at.exception
    assert at.metric[0].value == "00:30"


def test_actions_are_saved():
    import db

    at = AppTest.from_file(APP, default_timeout=10)
    at.run()
    game_id = at.query_params["game"]
    button(at, "Open 📄 D1").click().run()
    assert db.load_game(game_id).clock == 30


def test_unknown_resume_link_starts_a_new_case_with_a_warning():
    at = AppTest.from_file(APP, default_timeout=10)
    at.query_params["game"] = "x" * 32
    at.run()
    assert not at.exception
    assert any("not found" in w.value for w in at.warning)
    assert at.metric[0].value == "00:00"
