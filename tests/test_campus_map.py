"""The campus map: a pin for every location, and going there from the map."""

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from game.case import load_case
from game.engine import Engine

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")
MAP = ROOT / "assets" / "campus-map.webp"
LOCATIONS = [clue_id for clue_id in load_case()["clues"] if clue_id.startswith("L")]


def start(variant="A", seed=1, pick=None):
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = Engine().new_game(seed=seed, variant=variant).to_dict()
    if pick:
        at.session_state["map_pick"] = pick
    at.run()
    assert not at.exception
    return at


def map_markup(at):
    """The SVG markup the app sends to the map component."""
    (component,) = at.get("bidi_component")
    return json.loads(component.proto.json)


def search_buttons(at):
    return [b for b in at.button if b.label.startswith("Search it")]


def test_map_picture_is_in_the_repo_and_small_enough_for_a_phone():
    assert MAP.stat().st_size < 300_000


