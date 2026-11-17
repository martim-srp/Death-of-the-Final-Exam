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
