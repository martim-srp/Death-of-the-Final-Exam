"""Restart case is a round icon above the save icon; the old case-summary button in the status bar is gone."""

from game.engine import Engine
from tests.test_board_game import board_markup, page, start


def restart_popovers(at):
    return [p for p in at.get("popover") if p.proto.popover.label == "Restart case"]


def test_restart_is_one_round_icon_on_every_panel():
    for focus in (None, ("suspect", "class_rep"), ("clue", "D1"), ("sheet", None), ("lies", None)):
        at = start(focus=focus, tour_done=True)
        popovers = restart_popovers(at)
        assert len(popovers) == 1, focus
        assert popovers[0].proto.popover.icon == ":material/restart_alt:"


def test_restart_sits_just_above_the_save_icon():
    css = page(start(tour_done=True))
    assert ".st-key-restart_corner { position: fixed; left: 1rem; bottom: calc(1rem + 66px);" in css
    assert "@media (min-width: 641px) { .st-key-restart_corner { left: auto; right: 1rem; } }" in css


def test_restart_asks_before_wiping_the_case():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "D1")
    at = start(game=game, tour_done=True)
    assert at.session_state["game"]["history"]  # one tap on the icon only opens the question
    at.button(key="new_case").click().run()
    assert not at.exception
    assert not at.session_state["game"]["history"]


def test_the_status_bar_has_no_case_summary_button():
    hud = board_markup(start(tour_done=True))
    assert 'data-act="home"' not in hud


def test_the_notebook_keeps_the_leads_and_the_night_so_far():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    for clue in ("D1", "D2"):
        engine.open_clue(game, clue)  # past 01:00, when the storm takes out the lights
    text = page(start(game=game, focus=("sheet", None), tour_done=True))
    assert "The night so far" in text and "The storm takes out the lights" in text
