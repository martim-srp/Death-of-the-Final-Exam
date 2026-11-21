"""Events during the night: story only, the same in every variant, shown as the clock passes them."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from game.case import load_case
from game.engine import Engine

APP = str(Path(__file__).resolve().parent.parent / "app.py")
CASE = load_case()
EVENTS = CASE["night_events"]
NAMES = {word for s in CASE["suspects"].values() for word in s["name"].replace("The ", "").split()}


def test_events_are_inside_the_night_in_order_and_name_nobody():
    times = [e["at"] for e in EVENTS]
    assert times == sorted(times) and len(set(times)) == len(times)
    assert all(0 < t < CASE["clock"]["limit_minutes"] for t in times)
    for event in EVENTS:
        assert not any(name in event["text"] for name in NAMES - {"Student"}), event["text"]


def test_only_events_the_clock_has_passed_are_returned():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    assert engine.night_events(game) == []
    game.clock = 59
    assert engine.night_events(game) == []
    game.clock = 60
    assert [e["time"] for e in engine.night_events(game)] == ["01:00"]
    game.clock = 400
    assert [e["time"] for e in engine.night_events(game, since=60)] == ["03:00", "05:00", "06:00"]


def test_the_night_is_the_same_in_every_variant():
    engine = Engine()
    nights = set()
    for variant in CASE["variants"]:
        game = engine.new_game(seed=1, variant=variant)
        game.clock = CASE["clock"]["limit_minutes"]
        nights.add(tuple(e["text"] for e in engine.night_events(game)))
    assert len(nights) == 1


def test_events_change_no_rule():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    before = game.to_dict()
    game.clock = 500
    engine.night_events(game)
    after = game.to_dict()
    after["clock"] = before["clock"]
    assert after == before


def test_passing_an_event_pops_it_up_and_lists_it_on_the_home_panel():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "D1")  # 00:30
    at = AppTest.from_file(APP, default_timeout=15)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    at.session_state["tour_done"] = True
    at.session_state["focus"] = ("clue", "D4")
    at.run()
    next(b for b in at.button if b.label.startswith("Open it")).click().run()  # 00:30 -> 01:00
    assert not at.exception
    assert any(t.value.startswith("01:00 · The storm") for t in at.toast)
    at.session_state["focus"] = ("home", None)
    at.run()
    page = "\n".join(m.value for m in at.markdown)
    assert "The night so far" in page and "The storm takes out the lights" in page
