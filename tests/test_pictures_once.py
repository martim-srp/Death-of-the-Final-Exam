"""Each open evidence picture travels to the browser once per redraw, not twice.

A place card is drawn both as a card in the hand and as a round thumbnail on its map pin. Both
now draw the same single copy (an SVG <symbol> sent with the hand), so late in the game the
board weighs about a quarter less on a phone connection.
"""

import re

import board
from game.engine import Engine
from tests.test_board_game import board_markup, start

CASE = Engine().case


def late_game(variant="A"):
    engine = Engine()
    game = engine.new_game(seed=1, variant=variant)
    game.opened = list(CASE["clues"])  # every card open, as at the end of a long game
    return game


def test_every_open_picture_is_sent_once_even_when_it_has_a_map_pin():
    markup = board_markup(start(game=late_game()))
    pinned = [clue_id for clue_id in CASE["clues"] if clue_id in board.MAP_PINS]
    assert pinned  # the places really are both a pin and a card
    for clue_id in CASE["clues"]:
        picture = board.find_picture("clues", clue_id)
        if picture:
            assert markup.count(picture) == 1, clue_id


def test_a_pin_and_its_card_both_draw_the_same_copy():
    markup = board_markup(start(game=late_game()))
    for clue_id in board.MAP_PINS:
        if board.find_picture("clues", clue_id):
            assert markup.count(f'id="{board.picture_id(clue_id)}"') == 1
            assert markup.count(f'href="#{board.picture_id(clue_id)}"') == 2  # the pin and the card


def test_every_drawn_picture_has_its_copy_on_the_board():
    markup = board_markup(start(game=late_game("C")))
    used = set(re.findall(r'href="#(pic-[A-Z0-9]+)"', markup))
    defined = set(re.findall(r'<symbol id="(pic-[A-Z0-9]+)"', markup))
    assert used and used == defined


def test_no_copy_is_sent_for_a_card_that_is_not_open():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "D1")
    markup = board_markup(start(game=game))
    assert re.findall(r'<symbol id="(pic-[A-Z0-9]+)"', markup) == ["pic-D1"]
    assert "pic-L4" not in markup and board.find_picture("clues", "L4") not in markup


def test_no_open_card_means_no_picture_block():
    clues = Engine().clue_list(Engine().new_game(seed=1, variant="A"))
    assert board.pictures_html(clues) == ""
    assert "<symbol" not in board.hand_html(clues)
