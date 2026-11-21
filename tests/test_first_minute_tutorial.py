"""A new player's first minute: three guided steps that end in a caught lie.

Playtesters with no briefing did not understand what to do. The tutorial teaches the core
loop by doing it: search the faculty corridor, show it to the Companion, see the lie break.
"""

import pytest

from game.engine import Engine
from tests.test_board_game import board_markup, start


def coach(at):
    return "\n".join(m.value for m in at.markdown if 'class="coach"' in m.value)


@pytest.mark.parametrize("variant", ["A", "B", "C"])
def test_the_tutorial_path_catches_a_lie_in_every_variant(variant):
    engine = Engine()
    game = engine.new_game(seed=1, variant=variant)
    assert engine.clue_state(game, "L4") == "available"
    engine.open_clue(game, "L4")
    result = engine.present(game, "companion", "L4")
    assert [c["claim"] for c in result["contradictions"]] == ["never_went_to_office_door"]


def test_step_one_points_the_guide_at_the_faculty_corridor():
    at = start(tutorial=True)
    markup = board_markup(at)
    assert 'class="goal-bar" data-act="next:clue:L4"' in markup
    assert "Tutorial 1 of 3" in markup
    assert "Tutorial · 1 of 3" in coach(at) and "Search it" in coach(at)


def test_step_two_points_at_the_companion_then_step_three_explains_the_game():
    at = start(tutorial=True, focus=("clue", "L4"))
    at.button(key="open_L4").click().run()
    markup = board_markup(at)
    assert 'data-act="next:suspect:companion"' in markup and "Tutorial 2 of 3" in markup
    assert "I never went to his office door." in coach(at)
    at.pills(key="show_to_L4").set_value("companion").run()
    assert not at.exception
    assert "That is the game" in coach(at)
    assert "A liar is not always the culprit" in coach(at)
    at.button(key="tutorial_ok").click().run()
    assert coach(at) == ""
    assert 'data-act="next:clue:D1"' in board_markup(at)  # the usual guide takes over


def test_the_tutorial_can_be_skipped():
    at = start(tutorial=True)
    at.button(key="tutorial_skip").click().run()
    assert coach(at) == ""
    assert 'data-act="next:clue:D1"' in board_markup(at)


def test_no_tutorial_in_hard_mode_or_when_not_started():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.set_mode(game, "hard")
    assert coach(start(game=game, tutorial=True)) == ""
    assert coach(start()) == ""


def test_starting_a_new_case_starts_the_tutorial_in_place_of_the_tour():
    at = start(intro_done=False)
    start_button = next(b for b in at.button if b.label == "Start the investigation")
    start_button.click().run()
    assert not at.exception
    assert at.session_state["tutorial"] is True and at.session_state["tour_done"] is True
    assert "Tutorial 1 of 3" in board_markup(at)


def test_the_story_names_the_four_questions():
    at = start(intro_done=False)
    story = next(m.value for m in at.markdown if 'class="story"' in m.value)
    assert "<b>who</b> leaked it, <b>how</b>, <b>where</b> and <b>why</b>" in story
