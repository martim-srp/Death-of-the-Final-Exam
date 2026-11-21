"""Phone comfort: pop-ups at the bottom so they never cover the game, finger-sized buttons."""

import re

import board
from tests.test_board_game import page, start


def phone_rules(css, width=640):
    """The CSS inside the first @media (max-width: <width>px) block."""
    start_at = css.index(f"@media (max-width: {width}px)")
    depth, i = 0, css.index("{", start_at)
    for j in range(i, len(css)):
        depth += {"{": 1, "}": -1}.get(css[j], 0)
        if depth == 0:
            return css[i:j]
    raise AssertionError("unclosed @media block")


def test_pop_ups_slide_in_at_the_bottom_not_over_the_top_of_the_game():
    css = page(start())
    rule = re.search(r'\[data-testid="stToastContainer"\] \{([^}]*)\}', css).group(1)
    assert "top: auto !important" in rule and "bottom:" in rule


def test_on_a_phone_pop_ups_span_the_screen_and_pills_are_easy_to_tap():
    phone = phone_rules(page(start()))
    assert '[data-testid="stToastContainer"] { left: 0.5rem; right: 0.5rem; bottom: 0.5rem; }' in phone
    assert '[data-testid="stButtonGroup"] button { min-height: 40px; }' in phone


def test_status_bar_buttons_are_44_px_on_narrow_boards():
    narrow = board.BOARD_CSS[board.BOARD_CSS.index("@container (max-width: 700px)"):]
    narrow = narrow[: narrow.index("\n}\n")]
    assert ".tools button { flex-basis: 44px; height: 44px; }" in narrow
    # Desktop keeps the compact 38 px row.
    assert ".tools button { background: #2b221d; border: 1px solid #4a3a31; border-radius: 10px; width: 38px; height: 38px;" in board.BOARD_CSS


def test_the_mode_choice_is_roomy_and_says_just_normal_or_hard():
    at = start(intro_done=False)
    picker = at.segmented_control(key="mode_choice")
    assert [picker.format_func(o) for o in ("normal", "hard")] == ["Normal", "Hard"]
    css = page(at)
    assert ".st-key-mode_pick { gap: 0.8rem; margin: 0.5rem 0 1.4rem; }" in css
    assert '.st-key-mode_pick [data-testid="stButtonGroup"] button { min-height: 48px;' in css
    # On a phone the two buttons share the full width, so neither label is cut.
    phone = phone_rules(css)
    assert '.st-key-mode_pick [data-testid="stButtonGroup"] button { flex: 1 1 0;' in phone
    assert "max-width: none !important" in phone
