"""Choosing the screen walkthrough on a fresh case must not start another tour."""

from tests.test_board_game import board_markup, start


def test_choosing_the_screen_walkthrough_does_not_start_the_gameplay_tutorial():
    at = start(intro_done=False)

    next(button for button in at.button if button.label == "Show the screen walkthrough").click().run()

    assert not at.exception
    markup = board_markup(at)
    assert 'aria-label="Screen walkthrough"' in markup
    assert "Tutorial · 1 of 4" not in markup
    assert at.session_state["tutorial_done"] is True
