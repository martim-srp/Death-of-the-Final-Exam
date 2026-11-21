"""Small fixes found playing on a tablet held upright (768px wide)."""

import board


def test_suspect_names_shrink_in_a_very_narrow_side_column():
    css = board.BOARD_CSS
    rule = css[css.index("@container (max-width: 300px) {"):]
    assert ".sus .nm { font-size: 8px;" in rule
    # It comes after the 560px rule, so it wins there; phones (a 340px+ row) keep 10px.
    assert css.index("@container (max-width: 300px) {") > css.index("@container (max-width: 560px) {")

