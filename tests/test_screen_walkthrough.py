"""The optional screen walkthrough explains the interface without making game moves."""

import pytest

from game.engine import Engine
from tests.test_board_game import board_markup, start


def test_starting_after_the_welcome_starts_the_tutorial_not_the_screen_tour():
    # One walkthrough at a time: a new case starts with the gameplay tutorial; the screen tour is a button away.
    at = start(intro_done=False)
    before = at.session_state["game"]
    next(b for b in at.button if b.label == "Start the investigation").click().run()
    assert not at.exception
    markup = board_markup(at)
    assert 'class="tour"' not in markup
    assert "Tutorial 1 of 4" in markup
    assert at.session_state["game"] == before


def test_a_new_player_can_ask_for_the_four_screen_highlights_on_the_welcome_screen():
    at = start(intro_done=False)
    next(b for b in at.button if b.label == "Show the screen walkthrough").click().run()
    assert not at.exception
    markup = board_markup(at)
    assert 'aria-label="Screen walkthrough"' in markup
    for target in ("map", "hand", "suspects", "accuse"):
        assert f'data-target="{target}"' in markup
    assert '>Skip</button>' in markup and '>Next</button>' in markup


def test_replaying_from_the_rules_preserves_an_in_progress_case():
    engine = Engine()
    game = engine.new_game(seed=1, variant="B")
    engine.open_clue(game, "D1")
    at = start(game=game, intro_done=False, tour_done=True, tutorial_done=True)
    before = at.session_state["game"]
    assert 'class="tour"' not in board_markup(at)
    next(b for b in at.button if b.label == "Show the screen walkthrough").click().run()
    assert not at.exception
    assert 'class="tour"' in board_markup(at)
    assert at.session_state["game"] == before
    assert at.session_state["tutorial_done"] is True
    at.run()
    assert 'class="tour"' in board_markup(at)  # not lost on the next redraw


@pytest.mark.parametrize("mode", ["normal", "hard"])
def test_the_screen_walkthrough_also_works_without_case_tips_and_with_calm_mode(mode):
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.set_mode(game, mode)
    markup = board_markup(start(game=game, calm=True, tour_active=True))
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


def test_finishing_the_screen_tour_does_not_finish_the_gameplay_tutorial():
    at = start(tour_done=True, tour_active=False, tutorial=True)
    markup = board_markup(at)
    assert 'class="tour"' not in markup
    assert "Tutorial 1 of 4" in markup
    assert any(b.label == "Skip the tutorial" for b in at.button)
