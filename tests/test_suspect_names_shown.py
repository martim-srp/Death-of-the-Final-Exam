"""Every suspect card shows a name, in a wide row and in a narrow one.

The narrow-row rule (@container max-width: 560px) hides the long name and shows the
short one. The rule that hides the short name by default must come before it: with the
same specificity, a later rule wins, and the desktop side column (a narrow row) showed
no name at all.
"""

import re

import board

CSS = board.BOARD_CSS


def narrow_block():
    match = re.search(r"@container \(max-width: 560px\) \{(.*?)\n\}", CSS, re.DOTALL)
    assert match, "the narrow suspect row rule is missing"
    return match


def test_a_narrow_row_swaps_the_long_name_for_the_short_one():
    block = narrow_block().group(1)
    assert ".sus .nm .long { display: none; }" in block
    assert ".sus .nm .short { display: inline; }" in block


def test_the_short_name_is_hidden_by_default_before_the_narrow_rule():
    default = CSS.find(".sus .nm .short { display: none; }")
    assert default != -1
    assert default < narrow_block().start()
    assert CSS.count(".sus .nm .short { display: none; }") == 1


def test_every_card_carries_both_names():
    suspects = [{"id": "ta", "name": "The Teaching Assistant", "questioned": False, "caught": 0, "ruled_out": False}]
    markup = board.suspects_html(suspects)
    assert '<span class="long">Teaching Assistant</span>' in markup
    assert '<span class="short">TA</span>' in markup
