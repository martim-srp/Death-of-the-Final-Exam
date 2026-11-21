"""Fixes from a first-time playthrough: the detective's reaction to an answer, a tour that
survives redraws, the confrontation shown first at the end, and visible accusation picks."""

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

import board
from game.case import load_case
from game.engine import Engine

ROOT = Path(__file__).resolve().parent.parent
CASE = load_case()
VOICE = json.loads((ROOT / "data" / "voice.json").read_text(encoding="utf-8"))
APP = str(ROOT / "app.py")


def start(game, **state):
    at = AppTest.from_file(APP, default_timeout=15)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    at.session_state["tour_done"] = True
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception
    return at


# ---- 1. A suspect who answers a card is never "the wrong card" ---------------------------


def test_a_card_that_gets_an_answer_is_not_called_the_wrong_card():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    assert engine.reaction(game, shown=True, reacted=True) in VOICE["replies"]["reacted"]
    assert engine.reaction(game, shown=True) in VOICE["replies"]["shown"]
    assert not any("wrong card" in line for line in VOICE["replies"]["reacted"])


def test_the_class_reps_cafeteria_answer_gets_a_reacted_thought():
    # Variant A: the Class Representative answers the cafeteria card ("I meant to hand it in")
    # without a lie being caught. The thought must not say it was the wrong card.
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    game.opened = ["L2"]
    at = start(game, focus=("suspect", "class_rep"), suspect="class_rep")
    at.pills(key="show_clue").set_value("L2").run()
    assert not at.exception
    chat = at.session_state["chats"]["class_rep"]
    assert "hand it in" in chat[1]["text"]
    assert chat[-1]["think"] in VOICE["replies"]["reacted"]


# ---- 2. The tour resumes after a redraw, and its ring follows the target ------------------


def test_the_tour_keeps_its_step_across_redraws_and_tracks_its_target():
    assert "window.__dfeTourStep" in board.BOARD_JS
    assert "requestAnimationFrame(place)" in board.BOARD_JS
    assert "}, 350);" not in board.BOARD_JS.split("function tour", 1)[1].split("function revealPanel", 1)[0]


# ---- 3. The confrontation comes first and starts open -----------------------------------


def test_the_confrontation_is_open_and_above_the_rank():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.accuse(game, **CASE["variants"]["A"]["solution"])
    at = start(game)
    scene = next(e for e in at.expander if e.label.startswith("Half past seven"))
    assert scene.proto.expanded
    source = (ROOT / "app.py").read_text(encoding="utf-8").split("def finale", 1)[1]
    assert source.index("scene = denouement(game)") < source.index("rank_card(game)")


# ---- 4. Chosen accusation options are filled ---------------------------------------------


def test_chosen_accusation_options_are_filled():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    for column in ("who", "how", "where", "why"):
        assert f'.st-key-accuse_{column} button[aria-checked="true"]' in source  # how Streamlit marks a chosen pill
