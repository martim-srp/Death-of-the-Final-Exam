"""Smaller evidence cards on a wide board, so both rows fit on screen under the map."""

import re

import board
from game.engine import Engine
from tests.test_board_game import board_markup, start


SOURCE = board.BOARD_CSS


def container_block(query):
    match = re.search(re.escape(query) + r" \{(.*?)\n\}", SOURCE, re.S)
    assert match, query
    return match.group(1)


def test_wide_boards_use_short_16_by_9_cards():
    block = container_block("@container (min-width: 521px)")
    assert ".card .art { aspect-ratio: 16 / 9; }" in block
    assert "flex-direction: row" in block


def test_phones_keep_the_taller_cards():
    # The base rule (used on phones) is still 4:3; only wide boards switch to 16:9.
    assert ".card .art { aspect-ratio: 4 / 3;" in SOURCE
    assert "aspect-ratio: 16 / 9" not in SOURCE.split("@container (min-width: 521px)")[0]


def test_card_names_still_never_break_inside_a_word():
    block = container_block("@container (min-width: 521px)")
    assert "overflow-wrap" not in block and "word-break" not in block


def test_map_leaves_room_for_both_rows_of_cards():
    assert "calc((100vh - 390px) * 1.65)" in SOURCE


def test_cards_have_no_hover_tooltip_but_keep_a_spoken_name():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    markup = board_markup(start(game=game))
    cards = re.findall(r'<button class="card[^"]*"[^>]*>', markup)
    assert len(cards) == len(engine.case["clues"])
    for card in cards:
        assert " title=" not in card
        assert 'aria-label="Evidence ' in card


def test_time_left_note_hides_on_a_medium_board_so_it_never_overlaps():
    block = container_block("@container (max-width: 820px)")
    assert ".hud .clock small { display: none; }" in block
