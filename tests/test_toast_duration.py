"""Pop-ups stay on screen long enough to read, on desktop and phone."""

from game.case import load_case
from game.engine import Engine
from tests.test_board_game import click, start

CASE = load_case()
SECONDS = 9  # app.TOAST_SECONDS; Streamlit's default "short" is 4 seconds


def test_a_new_card_pop_up_stays_nine_seconds():
    at = start(focus=("clue", "D1"))
    click(at, "Open it")
    assert at.toast and all(t.proto.duration == SECONDS for t in at.toast)


def test_a_refusal_pop_up_stays_nine_seconds_too():
    game = Engine().new_game(seed=1, variant="A")
    game.clock = CASE["clock"]["limit_minutes"] - 5  # too late to search
    at = start(game=game, focus=("clue", "D1"))
    click(at, "Open it")
    assert at.toast and all(t.proto.duration == SECONDS for t in at.toast)


def test_every_pop_up_in_the_app_uses_the_same_duration():
    source = open("app.py", encoding="utf-8").read()
    assert f"TOAST_SECONDS = {SECONDS}" in source
    calls = [line for line in source.splitlines() if "st.toast(" in line]
    assert calls and all("duration=TOAST_SECONDS" in line for line in calls)
