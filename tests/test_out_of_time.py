"""At 09:00 the board offers only what the engine still allows: the accusation.

Before, a player at 09:00 still saw the question pills, the evidence pills, the chat box,
"Show this card to" and "Open it", and every tap ended in a refusal.
"""

import pytest

from game.case import load_case
from game.engine import Engine, GameError
from tests.test_board_game import page, start

CASE = load_case()
LIMIT = CASE["clock"]["limit_minutes"]
QUESTION = CASE["clock"]["question_cost"]
SEARCH = CASE["clock"]["clue_cost"]


def game_at(minutes_left, *opened):
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    for clue_id in opened:
        engine.open_clue(game, clue_id)
    game.clock = LIMIT - minutes_left
    return game


def pill_keys(at):
    return {p.key for p in at.get("button_group")}


# ---- Engine -----------------------------------------------------------------------------


def test_out_of_time_once_not_even_a_question_fits():
    engine = Engine()
    assert not engine.out_of_time(game_at(QUESTION))
    assert engine.out_of_time(game_at(QUESTION - 1))
    assert engine.out_of_time(game_at(0))


def test_can_afford_follows_the_clock_and_the_case_status():
    engine = Engine()
    game = game_at(SEARCH - 1)
    assert engine.can_afford(game, QUESTION) and not engine.can_afford(game, SEARCH)
    engine.accuse(game, **CASE["variants"]["A"]["solution"])
    assert not engine.can_afford(game, 0)  # a closed case allows nothing


def test_the_engine_still_refuses_a_question_after_nine():
    engine = Engine()
    game = game_at(0)
    with pytest.raises(GameError, match="09:00"):
        engine.ask(game, "ta", "alibi")


def test_the_guide_says_time_is_up_not_nearly_up_at_nine():
    engine = Engine()
    step = engine.next_step(game_at(0))
    assert step["do"] == "accuse" and step["text"] == "Time is up. Make your accusation."
    assert engine.next_step(game_at(20))["text"] == "Time is nearly up. Make your accusation."
    assert engine.thought(game_at(0), step).startswith("Nine o'clock.")


def test_hard_mode_has_no_guide_even_at_nine():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.set_mode(game, "hard")
    game.clock = LIMIT
    assert engine.next_step(game) is None


# ---- Interface --------------------------------------------------------------------------
# The controls stay (a tap still gets the engine's "Not enough time" pop-up, see
# test_visible_refusals.py), but the panel now says up front that it is 09:00.


def test_at_nine_the_suspect_panel_says_only_the_accusation_is_left():
    at = start(game=game_at(0, "D1"), focus=("suspect", "ta"))
    assert any("It is 09:00" in w.value for w in at.warning)


def test_with_a_question_left_the_suspect_panel_has_no_time_up_note():
    at = start(game=game_at(QUESTION, "D1"), focus=("suspect", "ta"))
    assert not any("It is 09:00" in w.value for w in at.warning)
    assert {"ask_topic", "show_clue"} <= pill_keys(at)


def test_at_nine_an_open_card_says_so_above_show_this_card_to():
    at = start(game=game_at(0, "D1"), focus=("clue", "D1"))
    assert any("It is 09:00" in c.value for c in at.caption)
    at = start(game=game_at(QUESTION, "D1"), focus=("clue", "D1"))
    assert not any("It is 09:00" in c.value for c in at.caption)


def test_with_too_little_time_to_search_a_card_says_so_before_the_button():
    at = start(game=game_at(SEARCH - 10), focus=("clue", "D1"))
    assert any("Not enough time left to open it before 09:00" in c.value for c in at.caption)
    at = start(game=game_at(SEARCH), focus=("clue", "D1"))
    assert not any("Not enough time left" in c.value for c in at.caption)
