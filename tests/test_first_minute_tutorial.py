"""A new player's first minute: three guided steps that end in a caught lie, then the notebook.

Playtesters with no briefing did not understand what to do. The tutorial teaches the core
loop by doing it: search the faculty corridor, show it to the Companion, see the lie break.
A fourth step lights up the notebook and says what it is for.
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
    assert "Tutorial 1 of 4 · Tap the glowing Faculty pin, then Search it." in markup
    assert "<em>" not in markup.split('class="goal-bar"')[1].split("</button>")[0]  # one sentence, no musing
    assert coach(at) == ""  # the strip says it; the panel only offers to skip
    assert not any("Where to start" in m.value for m in at.markdown)  # the coach card says it once


def test_step_two_points_at_the_companion_then_step_three_explains_the_game():
    at = start(tutorial=True, focus=("clue", "L4"))
    at.button(key="open_L4").click().run()
    markup = board_markup(at)
    assert 'data-act="next:suspect:companion"' in markup and "Tutorial 2 of 4" in markup
    assert "never went to his office door" in markup
    at.pills(key="show_to_L4").set_value("companion").run()
    assert not at.exception
    assert "Caught her lying! That is the game:" in coach(at)
    assert len(coach(at)) < 200  # one line, not a paragraph
    assert "Tutorial 3 of 4 · Lie caught!" in board_markup(at)  # the strip stays on the tutorial
    at.button(key="tutorial_ok").click().run()
    markup = board_markup(at)
    assert "Tutorial 4 of 4" in markup and 'data-act="next:sheet"' in markup
    assert "<em>" not in markup.split('class="goal-bar"')[1].split("</button>")[0]  # no musing: "every card is on the table" would be wrong
    assert '<button class="goal" data-act="sheet" title="Notebook">' in markup  # the notebook button glows
    assert "Your notebook</b> writes down every card" in coach(at)
    at.button(key="tutorial_end").click().run()
    assert coach(at) == ""
    markup = board_markup(at)
    assert 'data-act="next:clue:D1"' in markup  # the usual guide takes over
    assert 'class="goal" data-act="sheet"' not in markup


def test_the_tutorial_can_be_skipped():
    at = start(tutorial=True)
    at.button(key="tutorial_skip").click().run()
    assert coach(at) == ""
    assert 'data-act="next:clue:D1"' in board_markup(at)


def test_no_tutorial_when_not_started():
    assert "Tutorial 1 of 4" not in board_markup(start())


def hard_game():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.set_mode(game, "hard")
    return game


def test_hard_mode_gets_the_whole_tutorial_too():
    at = start(game=hard_game(), tutorial=True, focus=("clue", "L4"))
    assert "Tutorial 1 of 4" in board_markup(at)
    at.button(key="open_L4").click().run()
    assert "Tutorial 2 of 4" in board_markup(at)
    at.pills(key="show_to_L4").set_value("companion").run()
    assert not at.exception
    assert "Caught her lying! That is the game:" in coach(at)
    at.button(key="tutorial_ok").click().run()
    markup = board_markup(at)
    assert "Tutorial 4 of 4" in markup and '<button class="goal" data-act="sheet"' in markup
    at.button(key="tutorial_end").click().run()
    assert coach(at) == ""
    assert 'class="goal-bar"' not in board_markup(at)  # then hard mode's usual: no next step


def test_starting_a_hard_case_starts_the_tutorial():
    at = start(game=hard_game(), intro_done=False)
    next(b for b in at.button if b.label == "Start the investigation").click().run()
    assert not at.exception
    assert at.session_state["tutorial"] is True
    assert "Tutorial 1 of 4" in board_markup(at)


def test_starting_a_new_case_starts_the_tutorial():
    at = start(intro_done=False)
    start_button = next(b for b in at.button if b.label == "Start the investigation")
    start_button.click().run()
    assert not at.exception
    assert at.session_state["tutorial"] is True
    assert "Tutorial 1 of 4" in board_markup(at)


def test_the_story_names_the_four_questions():
    at = start(intro_done=False)
    story = next(m.value for m in at.markdown if 'class="story"' in m.value)
    assert "<b>who</b> leaked it, <b>how</b>, <b>where</b> and <b>why</b>" in story


def test_the_notebook_step_explains_the_notebook_where_it_opens():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "L4")
    engine.present(game, "companion", "L4")
    at = start(game=game, tutorial=True, tutorial_notebook=True, focus=("sheet", None))
    assert "Cross off what can't be: what is left is your accusation." in coach(at)
    assert any("Everything you have found" in m.value for m in at.markdown)  # the notebook itself, under the coach


def test_the_notebook_glow_is_still_in_calm_mode():
    import board
    assert '<button class="goal" data-act="sheet"' in board.hud_html("00:00", 540, 540, 3, 3, 0, None, "Detective", calm=True, goal="sheet")
    assert 'class="goal"' not in board.hud_html("00:00", 540, 540, 3, 3, 0, None, "Detective", goal="search")
