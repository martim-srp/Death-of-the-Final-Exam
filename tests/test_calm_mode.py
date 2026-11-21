"""Calm mode: for players who find motion, blinking and sound distracting.

When it is on, nothing on the board moves or plays a sound, the next step is one plain line,
and the page itself stops animating. It never changes the game.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import board
from game.case import load_case
from game.engine import Engine

APP = str(Path(__file__).resolve().parent.parent / "app.py")
CASE = load_case()


def start(intro_done=True, **state):
    at = AppTest.from_file(APP, default_timeout=15)
    at.session_state["game"] = Engine().new_game(seed=1, variant="A").to_dict()
    at.session_state["intro_done"] = intro_done
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception
    return at


def markups(at):
    import json

    return [json.loads(c.proto.json) for c in at.get("bidi_component")]


def board_markup(at):
    return next(m for m in markups(at) if 'class="hud' in m)


def suspect_markup(at):
    return next(m for m in markups(at) if m.startswith('<div class="suspects">'))


# ---- The button and the tap --------------------------------------------------------------


def test_the_status_bar_has_a_calm_button_that_is_off_by_default():
    hud = board.hud_html("00:00", 540, 540, 3, 3, 0, None, "Detective")
    assert 'data-act="calm"' in hud
    assert 'aria-pressed="false"' in hud
    assert "calmbtn on" not in hud


def test_the_calm_button_shows_when_it_is_on():
    hud = board.hud_html("00:00", 540, 540, 3, 3, 0, None, "Detective", calm=True)
    assert "calmbtn on" in hud
    assert 'aria-pressed="true"' in hud


def test_the_calm_button_uses_a_line_icon_not_an_emoji():
    hud = board.hud_html("00:00", 540, 540, 3, 3, 0, None, "Detective")
    button = hud.split('data-act="calm"')[1].split("</button>")[0]
    assert "<svg" in button
    assert all(ord(ch) < 0x2000 for ch in button)


def test_tapping_calm_is_understood():
    assert board.parse_act("calm", CASE["suspects"], CASE["clues"]) == ("calm", None)


@pytest.mark.parametrize("act", ["calm:on", "calm:../x", "calmly", "CALM"])
def test_odd_calm_taps_are_ignored(act):
    assert board.parse_act(act, CASE["suspects"], CASE["clues"]) is None


def test_calm_marker_only_when_on():
    assert board.calm_html(True) == '<i class="calm-on" hidden></i>'
    assert board.calm_html(False) == ""


# ---- The board in calm mode ----------------------------------------------------------------


def test_calm_mode_is_off_on_a_new_game():
    at = start()
    assert 'class="calm-on"' not in board_markup(at)
    assert "calmbtn on" not in board_markup(at)


def test_calm_mode_marks_the_board_and_the_suspect_row():
    at = start(calm=True)
    assert 'class="calm-on"' in board_markup(at)
    assert "calmbtn on" in board_markup(at)
    assert 'class="calm-on"' in suspect_markup(at)


def test_calm_mode_plays_no_sound():
    noisy = start(sfx="flip", sfx_n=3)
    assert 'data-sfx="flip"' in board_markup(noisy)
    quiet = start(calm=True, sfx="flip", sfx_n=3)
    assert "data-sfx" not in board_markup(quiet)


def test_calm_mode_shows_the_next_step_as_one_plain_line():
    game = Engine().new_game(seed=1, variant="A")
    step = Engine().next_step(game)
    at = start(calm=True)
    bar = board_markup(at).split('class="goal-bar"')[1].split("</button>")[0]
    assert "<small>Next step</small>" in bar
    assert board.esc(step["text"]) in bar
    assert "<em>" not in bar  # no musing line under it


def test_calm_mode_stops_the_page_animations():
    assert "animation: none !important" not in "\n".join(m.value for m in start().markdown)
    page = "\n".join(m.value for m in start(calm=True).markdown)
    assert "animation: none !important" in page


def test_calm_mode_does_not_change_the_game():
    plain, calm = start(), start(calm=True)
    assert plain.session_state["game"] == calm.session_state["game"]


def test_the_board_switches_off_motion_and_sound_in_calm_mode():
    assert 'root.classList.toggle("calm", calm)' in board.BOARD_JS
    assert "if (!calm) play(sfx.dataset.sfx)" in board.BOARD_JS
    assert ".deck.calm *" in board.BOARD_CSS and "animation: none !important" in board.BOARD_CSS


# ---- The start screen ---------------------------------------------------------------------------


def test_the_start_screen_offers_calm_mode():
    at = start(intro_done=False)
    switch = at.toggle(key="calm_switch")
    assert switch.value is False
    switch.set_value(True).run()
    assert not at.exception
    assert at.session_state["calm"] is True


def test_the_start_screen_switch_can_turn_calm_mode_off_again():
    at = start(intro_done=False, calm=True)
    switch = at.toggle(key="calm_switch")
    assert switch.value is True
    switch.set_value(False).run()
    assert at.session_state["calm"] is False
