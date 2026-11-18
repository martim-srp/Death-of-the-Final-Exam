"""The closing screen sums up the player's case: time, clues, questions, lies caught, wrong guesses, badges."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from game.case import load_case
from game.engine import Engine

APP = str(Path(__file__).resolve().parents[1] / "app.py")
CASE = load_case()


def closed_app(game):
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    at.run()
    assert not at.exception
    return at


def metrics(at):
    return {m.label: m.value for m in at.metric}


def played_and_solved():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "D1")
    engine.open_clue(game, "L4")
    engine.ask(game, "class_rep", "alibi")
    engine.present(game, "companion", "L4")  # catches "I never went to his office door"
    engine.accuse(game, "exchange", "own_card_print", "residence", "cheat")  # one wrong guess
    engine.accuse(game, **CASE["variants"]["A"]["solution"])
    return game


def test_solved_case_shows_the_summary():
    game = played_and_solved()
    shown = metrics(closed_app(game))
    assert shown["Time used"] == "1h 20m"  # two clues (60) and two questions (20)
    assert shown["Clues opened"] == f"2 of {len(CASE['clues'])}"
    assert shown["Questions asked"] == "2"
    assert shown["Lies caught"] == "1"
    assert shown["Wrong accusations"] == "1"


def test_a_cold_case_also_shows_the_summary():
    engine = Engine()
    game = engine.new_game(seed=2, variant="B")
    for _ in range(CASE["max_strikes"]):
        engine.accuse(game, "exchange", "photographed_desk", "beach_cafe", "sell_paper")
    at = closed_app(game)
    assert any("gone cold" in e.value for e in at.error)
    shown = metrics(at)
    assert shown["Wrong accusations"] == str(CASE["max_strikes"])
    assert shown["Time used"] == "0h 00m"


def test_badges_earned_are_listed():
    engine = Engine()
    game = engine.new_game(seed=3, variant="A")
    engine.accuse(game, **CASE["variants"]["A"]["solution"])  # solved at 00:00: the Hedge fund badge
    at = closed_app(game)
    assert any("Hedge fund" in m.value for m in at.markdown)


def test_no_summary_while_the_case_is_open():
    engine = Engine()
    game = engine.new_game(seed=4, variant="C")
    at = closed_app(game)
    assert "Lies caught" not in metrics(at)
