"""A tap shows what it opened: the panel is brought into view, and cards to show have names."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

import board
from game.case import load_case
from game.engine import Engine

ROOT = Path(__file__).resolve().parent.parent


def test_every_clue_has_a_short_card_name():
    ids = {c["id"] if isinstance(c, dict) else c for c in load_case()["clues"]}
    assert ids <= set(board.CARD_NAMES)


def test_cards_to_show_are_labelled_with_their_name():
    game = Engine().new_game(seed=1, variant="A")
    Engine().open_clue(game, "L4")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=10)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    at.session_state["tour_done"] = True
    at.session_state["focus"] = ("suspect", "companion")
    at.run()
    assert not at.exception
    assert at.pills(key="show_clue").options == ["12 · Faculty"]


def test_a_tap_brings_the_panel_into_view_at_any_width():
    script = board.BOARD_JS
    assert "scrollIntoView" in script and ".st-key-panel" in script
    assert 'matchMedia("(max-width: 640px)").matches' not in script
