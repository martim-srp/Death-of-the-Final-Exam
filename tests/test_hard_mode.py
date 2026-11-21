"""Normal and hard mode. Hard mode is the same case with no tips: no next step, no leads, no
hints, no highlighted details, and evidence crosses nothing off for you. Chosen before the first move."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from game.case import load_case
from game.engine import Engine, Game, GameError

APP = str(Path(__file__).resolve().parent.parent / "app.py")
CASE = load_case()
WRONG = {"who": "exchange", "how": "own_card_print", "where": "residence", "why": "cheat"}


def hard_game(variant="A"):
    engine = Engine()
    game = engine.new_game(seed=1, variant=variant)
    engine.set_mode(game, "hard")
    return engine, game


# ---- Choosing the mode --------------------------------------------------------------------


def test_a_new_game_is_normal():
    assert Engine().new_game(seed=1, variant="A").mode == "normal"


def test_the_mode_is_chosen_before_the_first_move():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.set_mode(game, "hard")
    engine.set_mode(game, "normal")
    engine.open_clue(game, "D1")
    with pytest.raises(GameError):
        engine.set_mode(game, "hard")
    assert game.mode == "normal"


def test_an_unknown_mode_is_refused():
    engine = Engine()
    with pytest.raises(GameError):
        engine.set_mode(engine.new_game(seed=1, variant="A"), "easy")


def test_the_mode_is_saved_and_old_saves_load_as_normal():
    _, game = hard_game()
    assert Game.from_dict(json.loads(json.dumps(game.to_dict()))).mode == "hard"
    old = game.to_dict()
    del old["mode"]
    assert Game.from_dict(old).mode == "normal"


# ---- No tips in hard mode ------------------------------------------------------------------


@pytest.mark.parametrize("variant", sorted(CASE["variants"]))
def test_hard_mode_gives_no_tips(variant):
    engine, game = hard_game(variant)
    for clue in ("D1", "D2", "L4"):
        engine.open_clue(game, clue)
    assert engine.next_step(game) is None
    assert engine.leads(game) == []
    assert engine.hint_list(game) == {}
    assert all(engine.hunches(game, c) == [] and engine.musing(game, c) is None for c in ("D1", "D2", "L4"))
    with pytest.raises(GameError):
        engine.hint(game, "D3")


def test_normal_mode_keeps_every_tip():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    for clue in ("D1", "D2"):
        engine.open_clue(game, clue)
    assert engine.next_step(game) is not None
    assert engine.leads(game)
    assert engine.hunches(game, "D2") or engine.musing(game, "D2")


def test_hard_mode_crosses_off_only_what_your_own_wrong_accusation_proved():
    engine, game = hard_game()
    for clue in ("D1", "D2", "L4"):
        engine.open_clue(game, clue)
    assert engine.eliminated(game) == []  # the evidence crosses nothing off by itself
    engine.accuse(game, **WRONG)
    out = engine.eliminated(game)
    assert out and all(e["by"] == "accusation" for e in out)


def test_a_breakdown_does_not_cross_off_a_suspect_in_hard_mode():
    engine, game = hard_game("A")  # The Exchange Student is innocent in variant A.
    game.opened = list(CASE["clues"])
    for clue in CASE["clues"]:
        result = engine.present(game, "exchange", clue)
        if result.get("cracked"):
            break
    assert "exchange" in game.cracked
    assert not any(e["option"] == "exchange" and e["by"] == "crack" for e in engine.eliminated(game))


def test_the_rules_are_the_same_in_both_modes():
    normal = Engine()
    hard_engine, hard = hard_game()
    plain = normal.new_game(seed=1, variant="A")
    for engine, game in ((normal, plain), (hard_engine, hard)):
        engine.open_clue(game, "D1")
        engine.open_clue(game, "D2")
        engine.present(game, "ta", "D2")
    assert plain.clock == hard.clock and plain.unlocked == hard.unlocked and plain.contradictions == hard.contradictions


# ---- On screen -----------------------------------------------------------------------------


def run_app(game, **state):
    at = AppTest.from_file(APP, default_timeout=15)
    at.session_state["game"] = game.to_dict()
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception
    return at


def page(at):
    return "\n".join(m.value for m in at.markdown) + "\n".join(c.value for c in at.caption)


def test_the_start_screen_offers_both_modes_and_explains_hard():
    at = run_app(Engine().new_game(seed=1, variant="A"))
    assert "Choose your mode" in page(at)
    assert "Hard mode is the same case with one difference: no tips." in page(at)
    at.segmented_control(key="mode_choice").set_value("hard").run()
    assert at.session_state["game"]["mode"] == "hard"


def test_hard_mode_board_has_no_next_step_and_locked_clues_have_no_hint():
    _, game = hard_game()
    at = run_app(game, intro_done=True, tour_done=True, focus=("clue", "D2"))
    from tests.test_board_game import board_markup

    assert 'class="goal-bar' not in board_markup(at)
    assert "Hard mode: no hints" in page(at)
    assert not any(b.label.startswith("Hint") for b in at.button)


def test_the_share_line_says_hard_mode():
    engine, game = hard_game()
    engine.accuse(game, **CASE["variants"]["A"]["solution"])
    at = run_app(game, intro_done=True)
    assert "in hard mode" in at.code[0].value
