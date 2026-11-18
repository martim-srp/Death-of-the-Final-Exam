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


def test_locked_clue_has_no_open_button():
    at = start()
    assert not any(b.label.startswith("Open 📄 D2") for b in at.button)


def pick(at, **choice):
    for column, value in choice.items():
        at.radio(key=f"accuse_{column}").set_value(value)


def variant_a_solution():
    return dict(Engine().case["variants"]["A"]["solution"])


# ---- Saved games ---------------------------------------------------------------


def test_new_visit_creates_a_saved_game_with_a_resume_link():
    import db

    at = AppTest.from_file(APP, default_timeout=10)
    at.run()
    assert not at.exception
    game_id = at.query_params["game"]
    assert db.load_game(game_id) is not None


