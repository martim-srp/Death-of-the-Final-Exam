"""The tour ends with one move to try, so a new player catches a lie in the first minutes.

The tour explained where things are but never led to the game's "aha" (a card breaking a story).
Its last step now suggests one move, in normal mode only (hard mode gives no tips).
"""

import re

import pytest

import board
from game.engine import Engine
from tests.test_board_game import board_markup, start


@pytest.mark.parametrize("variant", ["A", "B", "C"])
def test_the_suggested_move_catches_a_lie_in_every_variant(variant):
    engine = Engine()
    game = engine.new_game(seed=1, variant=variant)
    assert engine.number("L4") == 12 and "Faculty" in board.CARD_NAMES.get("L4", "Faculty")
    assert engine.clue_state(game, "L4") == "available"  # open from the start
    engine.open_clue(game, "L4")
    caught = engine.present(game, "companion", "L4").get("contradictions", [])
    assert [c["suspect"] for c in caught] == ["companion"]


def text(html):
    return re.sub(r"<[^>]+>", "", html)


def test_the_last_tour_step_suggests_it_in_normal_mode():
    assert "search the Faculty, then show card 12 to the Companion." in text(board.tutorial_html())
    assert "show card 12 to the Companion" in text(board_markup(start(intro_done=True)))


def test_hard_mode_keeps_the_tour_without_the_tip():
    assert "card 12" not in board.tutorial_html(hard=True)
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.set_mode(game, "hard")
    markup = board_markup(start(game=game, intro_done=True))
    assert 'class="tour"' in markup and "card 12" not in markup
