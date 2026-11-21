"""A suspect caught lying (or who cracks) shows their nervous portrait; until then, the calm one."""

from pathlib import Path

from PIL import Image

import board
from game.case import load_case
from game.engine import Engine
from tests.test_board_game import page, start, suspect_markup

CASE = load_case()
ASSETS = Path(__file__).resolve().parent.parent / "assets" / "suspects"


def test_every_suspect_has_a_nervous_portrait_the_same_size_as_the_calm_one():
    for suspect in CASE["suspects"]:
        calm, nervous = ASSETS / f"{suspect}.webp", ASSETS / f"{suspect}_nervous.webp"
        assert nervous.exists(), suspect
        assert Image.open(nervous).size == Image.open(calm).size


def test_the_nervous_picture_is_used_only_when_asked_for():
    calm = board.find_picture("suspects", "companion")
    nervous = board.find_picture("suspects", "companion_nervous")
    assert calm != nervous
    assert board.suspect_picture("companion") == calm
    assert board.suspect_picture("companion", nervous=True) == nervous


def test_a_suspect_turns_nervous_once_caught_lying():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "L4")
    nervous = board.find_picture("suspects", "companion_nervous")
    at = start(game=game, focus=("suspect", "companion"), suspect="companion")
    assert nervous not in suspect_markup(at) and nervous not in page(at)
    at.pills(key="show_clue").set_value("L4").run()  # breaks "I never went to his office door"
    assert not at.exception
    assert nervous in suspect_markup(at)
    assert nervous in page(at)  # the interrogation header and the chat
    assert board.find_picture("suspects", "class_rep_nervous") not in suspect_markup(at)  # only the liar
