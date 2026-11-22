"""The countdown keeps the absolute night time available without showing a second clock."""

import board


def test_night_clock_is_available_as_a_label_without_a_second_visible_clock():
    hud = board.hud_html("00:40", 500, 540, 3, 3, 0, None, "Detective")

    assert 'aria-label="8 hours and 20 minutes left. Night clock: 00:40. The case closes at 09:00."' in hud
    assert 'title="Night clock: 00:40. The case closes at 09:00."' in hud
    assert "<b>00:40</b>" not in hud
