"""Save game is one round save icon pinned to a corner, on every panel, not a button inside the home panel."""

import re

from tests.test_board_game import page, start
from tests.test_phone_comfort import phone_rules


def save_popovers(at):
    return [p for p in at.get("popover") if p.proto.popover.label == "Save game"]


def test_save_game_is_one_save_icon_outside_the_side_panel():
    at = start(game_id="aBcdEF0123456789_XyZ", tour_done=True)
    popovers = save_popovers(at)
    assert len(popovers) == 1
    assert popovers[0].proto.popover.icon == ":material/save:"
    # It lives in its own corner container, not in the side panel.
    assert ".st-key-save_corner { position: fixed; left: 1rem; bottom: 1rem;" in page(at)


def test_save_icon_stays_on_screen_while_a_suspect_or_a_clue_is_open():
    for focus in (("suspect", "class_rep"), ("clue", "D1"), ("lies", None)):
        at = start(focus=focus, game_id="aBcdEF0123456789_XyZ", tour_done=True)
        assert len(save_popovers(at)) == 1, focus


def test_home_panel_no_longer_has_its_own_save_button_and_points_to_the_corner():
    at = start(game_id="aBcdEF0123456789_XyZ", tour_done=True)
    assert [p.proto.popover.label for p in at.get("popover")].count("Save game") == 1
    assert any("Tap the save icon in the corner to keep the link." in c.value for c in at.caption)
    assert not any("Use Save game to keep the link." in c.value for c in at.caption)


def test_the_icon_is_round_gold_and_hides_its_text_label_only_visually():
    css = page(start(tour_done=True))
    button = re.search(r'\.st-key-save_corner \[data-testid="stPopoverButton"\] \{([^}]*)\}', css).group(1)
    assert "border-radius: 50%" in button and "56px" in button and "var(--gold)" in button
    # The words "Save game" stay in the page for screen readers, clipped rather than removed.
    assert 'stPopoverButton"] [data-testid="stMarkdownContainer"] {' in css
    assert "clip: rect(0 0 0 0)" in css


def test_on_a_phone_the_icon_is_finger_sized_and_hugs_the_corner():
    phone = phone_rules(page(start(tour_done=True)))
    assert ".st-key-save_corner { left: 0.6rem; bottom: 0.6rem; }" in phone
    assert '.st-key-save_corner [data-testid="stPopoverButton"] { width: 52px; height: 52px; }' in phone


def test_during_the_first_play_tour_the_icon_moves_up_out_of_the_tour_card_on_phones():
    lifted = ".st-key-save_corner { bottom: 10.5rem; }"
    assert lifted in page(start())  # a new game: the tour is showing
    assert lifted not in page(start(tour_done=True))


def test_no_save_icon_once_the_case_is_closed():
    at = start(tour_done=True)
    at.session_state["game"] = {**at.session_state["game"], "status": "cold"}
    at.run()
    assert not at.exception
    assert not save_popovers(at)
