"""Readable text on the board (WCAG AA: 4.5:1 for small text), checked with axe-core in a browser
on the board, an interrogation, an open card, the notebook and the accusation."""

import board


def luminance(hex_colour):
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_locked_card_labels_are_readable():
    assert ".card.locked { background: #2a221e; color: #a89a8c;" in board.BOARD_CSS
    assert contrast("#a89a8c", "#2a221e") >= 4.5


def test_the_accuse_button_text_is_white_on_red_even_on_hover():
    css = board.BOARD_CSS
    assert "color: #fff; font: 700 15px var(--type);" in css[css.index(".tools .accuse {"):]
    assert ".tools .accuse:hover { color: #fff;" in css
    assert contrast("#ffffff", "#c0392b") >= 4.5


def test_the_map_is_a_group_of_buttons_not_a_picture():
    # role="img" hides its children from screen readers, but the pins inside are buttons.
    html = board.map_html("", (1200, 900), [], [], None, None, [], None)
    assert '<svg class="map"' in html and 'role="group"' in html.split(">")[0]
