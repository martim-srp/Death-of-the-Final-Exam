"""Opened clues show their evidence picture, in the case file and on the map; others show none."""

from pathlib import Path

from PIL import Image
from streamlit.testing.v1 import AppTest

from game.case import load_case
from game.engine import Engine

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")


def start(game, pick=None):
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    if pick:
        at.session_state["map_pick"] = pick
    at.run()
    assert not at.exception
    return at


def pictures(at):
    """The images on the page, besides the ones every page has (the logo)."""
    return len(at.get("image")) - BASELINE_IMAGES


BASELINE_IMAGES = 1  # the Nova SBE logo in the header


def test_every_clue_has_a_picture_except_the_chart_and_two_places():
    ids = {c["id"] if isinstance(c, dict) else c for c in load_case()["clues"]}
    with_picture = {p.stem for p in (ROOT / "assets" / "clues").glob("*.webp")}
    assert with_picture <= ids
    assert ids - with_picture == {"D4", "L2", "L4"}


def test_pictures_come_in_two_shapes_and_are_shown_at_one_width():
    shapes = {Image.open(p).size for p in (ROOT / "assets" / "clues").glob("*.webp")}
    assert shapes <= {(640, 360), (640, 480)}
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "st.image(str(picture), width=360)" in source  # same width, own shape: nothing cropped


def test_no_picture_before_any_clue_with_one_is_opened():
    at = start(Engine().new_game(seed=1, variant="A"))
    assert len(at.get("image")) == BASELINE_IMAGES


def test_an_opened_document_shows_its_picture():
    game = Engine().new_game(seed=1, variant="A")
    Engine().open_clue(game, "D1")
    at = start(game)
    assert pictures(at) == 1


def test_an_opened_place_shows_its_picture_on_the_map():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    for clue in ("D1", "D2", "L1"):
        engine.open_clue(game, clue)
    without_pick = pictures(start(game))
    assert pictures(start(game, pick="L1")) == without_pick + 1


def test_a_place_without_a_picture_shows_none():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "L4")
    assert pictures(start(game, pick="L4")) == 0
