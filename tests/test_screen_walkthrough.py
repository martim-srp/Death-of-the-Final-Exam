"""The screen walkthrough is the one onboarding: it explains the interface without making game moves."""

import pytest

from game.engine import Engine
from tests.test_board_game import board_markup, start

STEPS = ("map", "hand", "suspects", "sheet", "accuse")


def test_starting_after_the_welcome_shows_the_five_screen_highlights_and_nothing_else():
    at = start(intro_done=False)
    assert 'class="tour"' not in board_markup(at)
    before = at.session_state["game"]
    next(b for b in at.button if b.label == "Start the investigation").click().run()
    assert not at.exception
    markup = board_markup(at)
    assert 'aria-label="Screen walkthrough"' in markup
    for target in STEPS:
        assert f'data-target="{target}"' in markup
    assert '>Skip</button>' in markup and '>Next</button>' in markup
    assert at.session_state["game"] == before
    assert "Tutorial" not in markup  # the old guided tutorial is gone: one walkthrough only
    assert not any("tutorial" in b.label.lower() for b in at.button)


def test_the_walkthrough_explains_the_notebook():
    markup = board_markup(start())
    assert "<b>Your notebook</b>" in markup
    assert "Cross off what can&#x27;t be" in markup or "Cross off what can't be" in markup


def test_a_new_case_does_not_need_a_second_walkthrough_button():
    at = start(intro_done=False)
    assert not any(b.label == "Show the screen walkthrough" for b in at.button)


def test_replaying_from_the_rules_preserves_an_in_progress_case():
    engine = Engine()
    game = engine.new_game(seed=1, variant="B")
    engine.open_clue(game, "D1")
    at = start(game=game, intro_done=False, tour_done=True)
    before = at.session_state["game"]
    assert 'class="tour"' not in board_markup(at)
    next(b for b in at.button if b.label == "Show the screen walkthrough").click().run()
    assert not at.exception
    assert 'class="tour"' in board_markup(at)
    assert at.session_state["game"] == before
    at.run()
    assert 'class="tour"' in board_markup(at)  # not lost on the next redraw


@pytest.mark.parametrize("mode", ["normal", "hard"])
def test_the_screen_walkthrough_shows_in_every_mode_and_with_calm_mode(mode):
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.set_mode(game, mode)
    markup = board_markup(start(game=game, calm=True))
    assert 'aria-label="Screen walkthrough"' in markup
    assert 'class="calm-on"' in markup


def test_the_tour_is_not_injected_when_reopening_a_progressed_game():
    engine = Engine()
    game = engine.new_game(seed=1, variant="C")
    engine.open_clue(game, "D1")
    at = start(game=game)
    assert 'class="tour"' not in board_markup(at)
    at.run()
    assert 'class="tour"' not in board_markup(at)


def test_finishing_the_tour_leaves_a_plain_board():
    markup = board_markup(start(tour_done=True))
    assert 'class="tour"' not in markup
    assert "Tutorial" not in markup
