"""Hints for locked clues and part-by-part feedback on a wrong accusation."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from game.engine import COLUMNS, HINT_COST, Engine, Game, GameError

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def engine():
    return Engine()


def solution(engine, variant):
    return dict(engine.case["variants"][variant]["solution"])


def other_option(engine, column, value):
    return next(o["id"] for o in engine.case["accusation"][column] if o["id"] != value)


# ---- Engine: accusation feedback ---------------------------------------------------


@pytest.mark.parametrize("variant", ["A", "B", "C"])
@pytest.mark.parametrize("wrong_column", COLUMNS)
def test_wrong_accusation_names_the_right_parts(engine, variant, wrong_column):
    game = engine.new_game(seed=1, variant=variant)
    choice = solution(engine, variant)
    choice[wrong_column] = other_option(engine, wrong_column, choice[wrong_column])
    result = engine.accuse(game, **choice)
    assert result["correct"] == 3
    assert engine.right_parts(game) == [c for c in COLUMNS if c != wrong_column]
    assert result["status"] == "playing"


def test_all_wrong_accusation_has_no_right_parts(engine):
    game = engine.new_game(seed=1, variant="A")
    choice = {c: other_option(engine, c, v) for c, v in solution(engine, "A").items()}
    result = engine.accuse(game, **choice)
    assert result["correct"] == 0
    assert engine.right_parts(game) == []


def test_right_accusation_lists_all_four_parts(engine):
    game = engine.new_game(seed=1, variant="B")
    result = engine.accuse(game, **solution(engine, "B"))
    assert engine.right_parts(game) == list(COLUMNS)
    assert result["status"] == "solved"


def test_right_parts_is_empty_before_any_accusation(engine):
    assert engine.right_parts(engine.new_game(seed=1, variant="A")) == []


def test_right_parts_follows_the_latest_accusation(engine):
    game = engine.new_game(seed=1, variant="A")
    choice = solution(engine, "A")
    first = {**choice, "who": "exchange"}
    engine.accuse(game, **first)
    assert engine.right_parts(game) == ["how", "where", "why"]
    second = {**choice, "why": "cheat", "how": "own_card_print"}
    engine.accuse(game, **second)
    assert engine.right_parts(game) == ["who", "where"]


# ---- Engine: hints -------------------------------------------------------------------


def test_hint_costs_fifteen_minutes(engine):
    game = engine.new_game(seed=1, variant="A")
    engine.hint(game, "L2")
    assert engine.hint_cost() == HINT_COST == 15
    assert game.clock == 15
    assert game.hints == ["L2"]
    assert game.history[-1] == {"action": "hint", "clue": "L2", "clock": 15}


def test_reading_a_hint_again_is_free(engine):
    game = engine.new_game(seed=1, variant="A")
    first = engine.hint(game, "L2")
    second = engine.hint(game, "L2")
    assert first == second
    assert game.clock == 15
    assert game.hints == ["L2"]


@pytest.mark.parametrize(
    "clue_id, text",
    [
        ("D2", "Open Evidence 1. The leaked PDF first."),
        ("D3", "The leaked PDF is version 3 of the exam. Is that really the paper students will sit? Ask the Professor about the exam."),
        ("L2", "Show Evidence 2. Print server log to the Teaching Assistant."),
        ("L3", "The Class Representative is first in the ranking. If the exam is annulled, they win the fellowship. Where were they last night? Ask about their alibi."),
    ],
)
def test_hint_says_how_to_unlock(engine, clue_id, text):
    game = engine.new_game(seed=1, variant="A")
    assert engine.hint(game, clue_id) == text


def test_every_locked_clue_has_a_hint_that_works(engine):
    """Following each hint really unlocks the clue, in every variant."""
    for variant in ("A", "B", "C"):
        for item in engine.clue_list(engine.new_game(seed=1, variant=variant)):
            if item["state"] != "locked":
                continue
            game = engine.new_game(seed=1, variant=variant)
            clue_id = item["id"]
            unlock = engine._clues(game)[clue_id]["unlock"]
            # Open whatever the hint needs first, the way a player would.
            needed = list(unlock.get("requires", []))
            if "present" in unlock:
                needed.append(unlock["present"]["clue"])
            for need in needed:
                for prereq in engine._clues(game)[need]["unlock"].get("requires", []):
                    if prereq not in game.opened:
                        engine.open_clue(game, prereq)
                if need not in game.opened:
                    engine.open_clue(game, need)
            if "topic" in unlock:
                engine.ask(game, unlock["topic"]["suspect"], unlock["topic"]["topic"])
            if "present" in unlock:
                engine.present(game, unlock["present"]["suspect"], unlock["present"]["clue"])
            assert engine.clue_state(game, clue_id) == "available", (variant, clue_id)


def test_hints_are_the_same_in_every_variant(engine):
    """A hint must never give away which variant is being played."""
    texts = []
    for variant in ("A", "B", "C"):
        game = engine.new_game(seed=1, variant=variant)
        locked = [c["id"] for c in engine.clue_list(game) if c["state"] == "locked"]
        texts.append({c: engine._hint_text(game, c) for c in locked})
    assert texts[0] == texts[1] == texts[2]


def test_hint_never_contains_clue_text(engine):
    game = engine.new_game(seed=1, variant="A")
    for item in engine.clue_list(game):
        if item["state"] == "locked":
            text = engine.hint(game, item["id"])
            clue = engine._clues(game)[item["id"]]
            for field in ("text", "log", "hidden_text"):
                if clue.get(field):
                    assert clue[field][:30] not in text


@pytest.mark.parametrize("clue_id", ["D1", "D4"])
def test_hint_for_an_available_clue_is_rejected(engine, clue_id):
    game = engine.new_game(seed=1, variant="A")
    with pytest.raises(GameError):
        engine.hint(game, clue_id)
    assert game.clock == 0


def test_hint_for_an_open_clue_is_rejected(engine):
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "D1")
    with pytest.raises(GameError):
        engine.hint(game, "D1")
    assert game.clock == 30


def test_hint_for_an_unknown_clue_is_rejected(engine):
    game = engine.new_game(seed=1, variant="A")
    with pytest.raises(GameError):
        engine.hint(game, "Z9")


def test_hint_without_enough_time_is_rejected(engine):
    game = engine.new_game(seed=1, variant="A")
    game.clock = engine.clock_rules["limit_minutes"] - 5
    with pytest.raises(GameError):
        engine.hint(game, "L2")
    assert game.hints == []


def test_hint_after_the_case_is_closed_is_rejected(engine):
    game = engine.new_game(seed=1, variant="A")
    engine.accuse(game, **solution(engine, "A"))
    with pytest.raises(GameError):
        engine.hint(game, "L2")


def test_hint_list_drops_clues_once_unlocked(engine):
    game = engine.new_game(seed=1, variant="A")
    engine.hint(game, "D2")
    engine.hint(game, "L2")
    assert set(engine.hint_list(game)) == {"D2", "L2"}
    engine.open_clue(game, "D1")
    assert set(engine.hint_list(game)) == {"L2"}


def test_hints_survive_saving(engine):
    game = engine.new_game(seed=1, variant="A")
    engine.hint(game, "L2")
    again = Game.from_dict(game.to_dict())
    assert again.hints == ["L2"]


def test_old_saves_without_hints_still_load(engine):
    data = engine.new_game(seed=1, variant="A").to_dict()
    del data["hints"]
    assert Game.from_dict(data).hints == []


# ---- Engine: free leads ------------------------------------------------------------


def test_no_leads_at_the_start(engine):
    assert engine.leads(engine.new_game(seed=1, variant="A")) == []


@pytest.mark.parametrize("variant", ["A", "B", "C"])
def test_opening_the_print_log_gives_a_lead_to_the_cafeteria(engine, variant):
    game = engine.new_game(seed=1, variant=variant)
    engine.open_clue(game, "D1")
    engine.open_clue(game, "D2")
    clock = game.clock
    assert engine.leads(game) == [
        {"clue": "L2", "from": "D2", "text": "Show Evidence 2. Print server log to the Teaching Assistant."}
    ]
    assert game.clock == clock  # leads are free


def test_lead_goes_away_once_followed(engine):
    game = engine.new_game(seed=1, variant="B")
    engine.open_clue(game, "D1")
    engine.open_clue(game, "D2")
    engine.present(game, "ta", "D2")
    assert engine.clue_state(game, "L2") == "available"
    assert engine.leads(game) == []


def test_leads_are_the_same_in_every_variant(engine):
    found = []
    for variant in ("A", "B", "C"):
        game = engine.new_game(seed=1, variant=variant)
        for clue_id in ("D1", "D2", "D4", "D5", "L4", "L1", "D7"):
            engine.open_clue(game, clue_id)
        found.append(engine.leads(game))
    assert found[0] == found[1] == found[2]


# ---- App -------------------------------------------------------------------------------


def start(variant="A"):
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = Engine().new_game(seed=1, variant=variant).to_dict()
    at.session_state["intro_done"] = True
    at.run()
    assert not at.exception
    return at


