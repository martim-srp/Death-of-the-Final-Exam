"""The detective's rank on the closing screen, and the spoiler-free line to share."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from game.case import load_case
from game.engine import COLD_RANK, RANKS, Engine, GameError

APP = str(Path(__file__).resolve().parents[1] / "app.py")
CASE = load_case()
SOLUTION = {v: CASE["variants"][v]["solution"] for v in "ABC"}
WRONG = {"who": "exchange", "how": "own_card_print", "where": "residence", "why": "cheat"}


@pytest.fixture
def engine():
    return Engine()


def solved_at_once(engine, variant="A"):
    game = engine.new_game(seed=1, variant=variant)
    engine.accuse(game, **SOLUTION[variant])
    return game


# ---- Engine --------------------------------------------------------------------------


def test_no_rank_while_the_case_is_open(engine):
    with pytest.raises(GameError):
        engine.rank(engine.new_game(seed=1, variant="A"))


def test_instant_solve_scores_solving_and_all_the_time(engine):
    rank = engine.rank(solved_at_once(engine))
    assert rank["parts"] == {"solved": 50, "time": 25, "lies": 0, "hints": 0, "wrong": 0}
    assert rank["score"] == 75
    assert rank["title"] == "Inspector"


def test_lies_caught_raise_the_score_up_to_twenty(engine):
    game = solved_at_once(engine)
    game.contradictions = [["class_rep", f"c{i}"] for i in range(3)]
    assert engine.rank(game)["parts"]["lies"] == 15
    game.contradictions = [["class_rep", f"c{i}"] for i in range(9)]
    rank = engine.rank(game)
    assert rank["parts"]["lies"] == 20
    assert rank["score"] == 95 and rank["title"] == "Chief Inspector"


def test_hints_and_wrong_accusations_lower_the_score(engine):
    game = engine.new_game(seed=1, variant="A")
    engine.hint(game, "L2")
    engine.accuse(game, **WRONG)
    engine.accuse(game, **WRONG)
    engine.accuse(game, **SOLUTION["A"])
    parts = engine.rank(game)["parts"]
    assert parts["hints"] == -3 and parts["wrong"] == -20


def test_time_used_lowers_the_score(engine):
    game = solved_at_once(engine)
    game.clock = CASE["clock"]["limit_minutes"]
    assert engine.rank(game)["parts"]["time"] == 0
    game.clock = CASE["clock"]["limit_minutes"] // 2
    assert engine.rank(game)["parts"]["time"] == 12  # half of 25, rounded


def test_score_stays_between_0_and_100(engine):
    game = solved_at_once(engine)
    game.clock, game.strikes, game.hints = CASE["clock"]["limit_minutes"], 2, list("ABCDEFGHIJKL")
    rank = engine.rank(game)
    assert rank["score"] == 0 and rank["title"] == RANKS[-1][1]


@pytest.mark.parametrize("score, title", [(100, "Chief Inspector"), (85, "Chief Inspector"), (84, "Inspector"),
                                          (70, "Inspector"), (69, "Detective Sergeant"), (55, "Detective Sergeant"),
                                          (54, "Detective Constable"), (0, "Detective Constable")])
def test_rank_titles_by_score(score, title):
    assert next(name for lowest, name in RANKS if score >= lowest) == title


def test_cold_case_has_its_own_rank(engine):
    game = engine.new_game(seed=1, variant="A")
    for _ in range(CASE["max_strikes"]):
        engine.accuse(game, **WRONG)
    assert game.status == "cold"
    assert engine.rank(game) == {"title": COLD_RANK, "score": 0, "parts": {}}


def test_rank_is_the_same_in_every_variant(engine):
    ranks = {v: engine.rank(solved_at_once(engine, v)) for v in "ABC"}
    assert ranks["A"] == ranks["B"] == ranks["C"]


# ---- Closing screen ------------------------------------------------------------------


def closed_app(game):
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    at.run()
    assert not at.exception
    return at


def page_text(at):
    return " ".join(m.value for m in at.markdown) + " " + " ".join(c.value for c in at.code)


def test_closing_screen_shows_the_rank_and_score(engine):
    text = page_text(closed_app(solved_at_once(engine)))
    assert "YOUR RANK" in text and "Inspector" in text and "75 / 100" in text


def test_share_line_never_names_the_culprit_or_the_answer(engine):
    for variant in "ABC":
        at = closed_app(solved_at_once(engine, variant))
        assert len(at.code) == 1
        line = at.code[0].value
        assert "Inspector (75/100)" in line and "carcavelos-paper.streamlit.app" in line
        for column, option_id in SOLUTION[variant].items():
            option = next(o for o in CASE["accusation"][column] if o["id"] == option_id)
            assert option["label"].lower() not in line.lower()
        assert CASE["suspects"][SOLUTION[variant]["who"]]["name"].lower() not in line.lower()


def test_cold_case_shows_its_rank_and_a_share_line(engine):
    game = engine.new_game(seed=1, variant="B")
    for _ in range(CASE["max_strikes"]):
        engine.accuse(game, **WRONG)
    at = closed_app(game)
    assert COLD_RANK in page_text(at)
    assert "went cold" in at.code[0].value
    assert "/ 100" not in page_text(at)
