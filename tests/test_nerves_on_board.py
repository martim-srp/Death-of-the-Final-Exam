"""Each suspect card on the board shows their nerves as a thin bar, so the player sees who is close to cracking."""

import re

import board
from game.engine import Engine
from tests.test_board_game import start, suspect_markup
from tests.test_nerves_crack import all_open, cards_without_lies

SUSPECT = {"id": "ta", "name": "The Teaching Assistant", "questioned": False, "caught": 0, "ruled_out": False}


def bars(markup):
    return re.findall(r'<i class="nv( full)?" title="Nerves (\d+)%"><b style="width:(\d+)%"></b></i>', markup)


def test_a_suspect_card_draws_its_nerves():
    assert bars(board.suspects_html([dict(SUSPECT, nerves=40)])) == [("", "40", "40")]


def test_full_nerves_are_marked():
    assert bars(board.suspects_html([dict(SUSPECT, nerves=100)])) == [(" full", "100", "100")]


def test_nerves_outside_0_to_100_are_clamped():
    assert bars(board.suspects_html([dict(SUSPECT, nerves=250)]))[0][1] == "100"
    assert bars(board.suspects_html([dict(SUSPECT, nerves=-5)]))[0][1] == "0"


def test_a_card_without_nerves_draws_no_bar():
    assert bars(board.suspects_html([SUSPECT])) == []


def test_the_board_shows_every_suspects_nerves_from_the_engine():
    engine = Engine()
    game = all_open("A")
    for clue in cards_without_lies(engine, game, "exchange")[:2]:
        engine.present(game, "exchange", clue)
    found = bars(suspect_markup(start(game=game)))
    assert len(found) == 5
    levels = [int(level) for _, level, _ in found]
    assert sorted(levels) == [10, 10, 10, 10, 40]


def test_a_cracked_suspect_shows_a_full_bar_on_the_board():
    engine = Engine()
    game = all_open("B")
    for clue in cards_without_lies(engine, game, "professor")[:6]:
        engine.present(game, "professor", clue)
    assert game.cracked == ["professor"]
    found = bars(suspect_markup(start(game=game)))
    assert (" full", "100", "100") in found
    assert sum(1 for full, _, _ in found if full) == 1


def test_the_nerves_bar_gives_nothing_away_at_the_start():
    for variant in "ABC":
        found = bars(suspect_markup(start(variant=variant)))
        assert {level for _, level, _ in found} == {"10"}
