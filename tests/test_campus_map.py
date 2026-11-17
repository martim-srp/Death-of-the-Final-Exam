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


def test_map_shows_the_picture_with_the_pins_on_top():
    markup = map_markup(start())
    assert '<image href="data:image/' in markup
    assert markup.index("<image") < markup.index("data-place=")


def test_campus_map_is_the_first_tab():
    at = start()
    assert at.tabs[0].label == "🗺️ Campus map"


def test_every_location_has_a_pin_on_the_map():
    markup = map_markup(start())
    for clue_id in LOCATIONS:
        assert f'data-place="{clue_id}"' in markup


def test_pins_show_each_locations_state():
    markup = map_markup(start())
    assert "Faculty corridor: Not searched yet" in markup  # L4 can be searched from the start
    assert "Library gate: Locked" in markup


def test_map_never_carries_locked_clue_text():
    markup = map_markup(start())
    for clue_id in LOCATIONS:
        text = load_case()["clues"][clue_id]["text"]
        assert text[:40] not in markup


def test_nothing_is_picked_at_first():
    at = start()
    assert any("Tap a pin on the map" in c.value for c in at.caption)
    assert not search_buttons(at)


def test_searching_an_available_place_opens_its_clue_and_costs_time():
    at = start(pick="L4")
    assert any("The faculty corridor" in m.value for m in at.markdown)
    search_buttons(at)[0].click().run()
    assert not at.exception
    game = at.session_state["game"]
    assert "L4" in game["opened"]
    assert game["clock"] == load_case()["clock"]["clue_cost"]
    assert "Searched" in map_markup(at)
    assert not search_buttons(at)  # already searched: its notes show instead
    assert any("Cleaner" in m.value for m in at.markdown)


def test_a_locked_place_cannot_be_searched():
    at = start(pick="L1")
    assert any("Locked" in m.value for m in at.markdown)
    assert not search_buttons(at)
    assert at.session_state["game"]["clock"] == 0
