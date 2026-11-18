"""A refused action is shown where the player is looking, not only at the top of the page.

Found by testing the live site: after tapping "Send question" with an empty or too long question,
the message appeared about 1,100 px above the button, off screen, and a too-long question was
wiped from the box. Refusals now also pop up as a toast, and the box stops at 300 characters.
"""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from game import ai
from game.engine import Engine

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def start(game):
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    at.secrets["REQUESTY_API_KEY"] = ""
    at.run()
    assert not at.exception
    return at


def toasts(at):
    return [t.value for t in at.toast]


def new_game():
    return Engine().new_game(seed=1, variant="A")


def test_an_empty_question_pops_up_a_warning():
    at = start(new_game())
    next(b for b in at.button if b.label.startswith("Send question")).click().run()
    assert not at.exception
    assert any("Type a question" in t for t in toasts(at))
    assert at.session_state["game"]["clock"] == 0  # nothing was spent


def test_opening_a_clue_without_enough_time_pops_up_a_warning():
    game = new_game()
    game.clock = 520  # 20 minutes left; a clue costs 30
    at = start(game)
    next(b for b in at.button if b.label.startswith("Open 📄 D1")).click().run()
    assert not at.exception
    assert any("Not enough time" in t for t in toasts(at))
    assert at.session_state["game"]["clock"] == 520


def test_the_question_box_stops_at_the_limit():
    at = start(new_game())
    box = next(w for w in at.text_input if w.label == "Your question")
    assert box.max_chars == ai.MAX_QUESTION_LENGTH == 300


def test_an_accepted_action_shows_no_warning():
    at = start(new_game())
    next(b for b in at.button if b.label.startswith("Open 📄 D1")).click().run()
    assert not any("⚠" in t or "Not enough" in t or "Type a question" in t for t in toasts(at))
    assert at.session_state["game"]["clock"] == 30
