"""Tests for the accusation confirmation dialog."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from game.engine import Engine

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_accusation_waits_for_confirmation_and_shows_attempts_left():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    at = AppTest.from_file(APP, default_timeout=15)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    at.session_state["focus"] = ("accuse", None)
    at.run()
    assert not at.exception

    solution = engine.case["variants"]["A"]["solution"]
    for column, option_id in solution.items():
        at.pills(key=f"accuse_{column}").set_value(option_id).run()
        assert not at.exception

    at.button(key="accuse_go").click().run()
    assert not at.exception
    assert "3 tries left" in "\n".join(item.value for item in at.markdown)
    assert at.session_state["game"]["status"] == "playing"
    assert at.session_state["game"]["strikes"] == 0

    at.button(key="confirm_accuse").click().run()
    assert not at.exception
    assert at.session_state["game"]["status"] == "solved"


def test_going_back_cancels_the_accusation_and_spends_nothing():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    at = AppTest.from_file(APP, default_timeout=15)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    at.session_state["focus"] = ("accuse", None)
    at.run()
    wrong = {**engine.case["variants"]["A"]["solution"], "who": "exchange"}
    for column, option_id in wrong.items():
        at.pills(key=f"accuse_{column}").set_value(option_id).run()
    at.button(key="accuse_go").click().run()
    at.button(key="cancel_accuse").click().run()
    assert not at.exception
    assert at.session_state["game"]["strikes"] == 0
    assert at.session_state["game"]["status"] == "playing"
    assert "pending_accusation" not in at.session_state
