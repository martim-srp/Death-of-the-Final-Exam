"""Evidence cards sit in two rows on a wide board, and their names break only between words."""

import re

import board
from game.engine import Engine
from tests.test_board_game import board_markup, start


SOURCE = open(board.__file__, encoding="utf-8").read()


def css_rule(selector):
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", SOURCE)
    assert match, selector
    return match.group(1)


def test_card_names_never_break_inside_a_word():
    rule = css_rule(".card .lbl span")
    assert "overflow-wrap: anywhere" not in rule
    assert "overflow-wrap: normal" in rule and "word-break: normal" in rule


def test_thirteen_cards_make_two_rows_of_seven_and_six():
    assert board.hand_columns(13) == 7


def test_hand_columns_for_any_count():
    assert [board.hand_columns(n) for n in (1, 2, 3, 12, 14)] == [1, 1, 2, 6, 7]


def test_the_hand_uses_two_rows_and_shows_every_card_name():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    game.opened = list(engine.case["clues"])
    markup = board_markup(start(game=game))
    assert 'class="hand" lang="en" style="--n:7"' in markup
    for clue in engine.clue_list(game):
        assert clue["title"].replace("'", "&#x27;") in markup or clue["title"] in markup


def test_phones_keep_five_columns():
    assert re.search(r"@container \(max-width: 520px\) \{\s*\.hand \{ grid-template-columns: repeat\(5,", SOURCE)
