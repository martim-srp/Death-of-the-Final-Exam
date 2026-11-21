"""Proving the accusation: an optional evidence card per answer. Right proofs on a solved case add
to the rank; proofs never change whether the accusation is right."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from game.case import load_case, resolve_variant
from game.engine import COLUMNS, Engine, GameError

APP = str(Path(__file__).resolve().parent.parent / "app.py")
CASE = load_case()
VARIANTS = sorted(CASE["variants"])


def opened_game(variant, *clues):
    engine = Engine()
    game = engine.new_game(seed=1, variant=variant)
    game.opened = list(clues) or list(CASE["clues"])
    return engine, game


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_answer_has_proofs_that_are_real_clues(variant):
    proofs = CASE["variants"][variant]["proofs"]
    assert set(proofs) == set(COLUMNS)
    clues = resolve_variant(CASE, variant)["clues"]
    for column, ids in proofs.items():
        assert ids and all(i in clues for i in ids), (variant, column)


@pytest.mark.parametrize("variant", VARIANTS)
def test_right_proofs_add_five_each_to_the_rank(variant):
    engine, game = opened_game(variant)
    proofs = {c: ids[0] for c, ids in CASE["variants"][variant]["proofs"].items()}
    engine.accuse(game, **CASE["variants"][variant]["solution"], proofs=proofs)
    assert engine.proven(game) == {c: True for c in COLUMNS}
    assert engine.rank(game)["parts"]["proof"] == 20


def test_a_wrong_proof_adds_nothing_and_no_proof_keeps_the_old_rank():
    engine, game = opened_game("A")
    engine.accuse(game, **CASE["variants"]["A"]["solution"], proofs={"who": "D8", "why": "D4"})
    assert engine.proven(game) == {"who": False, "why": True}
    assert engine.rank(game)["parts"]["proof"] == 5
    engine2, plain = opened_game("A")
    engine2.accuse(plain, **CASE["variants"]["A"]["solution"])
    assert "proof" not in engine2.rank(plain)["parts"] and engine2.proven(plain) == {}


def test_proofs_never_change_whether_the_accusation_is_right():
    engine, game = opened_game("A")
    wrong = {"who": "exchange", "how": "own_card_print", "where": "residence", "why": "cheat"}
    result = engine.accuse(game, **wrong, proofs={c: ids[0] for c, ids in CASE["variants"]["A"]["proofs"].items()})
    assert result["correct"] == 0 and game.status == "playing"
    assert engine.proven(game) == {}  # nothing about proofs is told before the case is solved


def test_only_an_opened_card_can_be_a_proof():
    engine, game = opened_game("A", "D1")
    with pytest.raises(GameError):
        engine.accuse(game, **CASE["variants"]["A"]["solution"], proofs={"who": "L1"})
    with pytest.raises(GameError):
        engine.accuse(game, **CASE["variants"]["A"]["solution"], proofs={"when": "D1"})
    assert game.status == "playing" and game.history == []


def test_the_score_never_goes_over_100():
    engine, game = opened_game("C")
    game.contradictions = [["companion", f"c{i}"] for i in range(6)]
    engine.accuse(game, **CASE["variants"]["C"]["solution"], proofs={c: ids[0] for c, ids in CASE["variants"]["C"]["proofs"].items()})
    assert engine.rank(game)["score"] == 100


def test_the_accusation_panel_offers_a_proof_for_each_answer():
    engine, game = opened_game("A", "D1", "D2")
    at = AppTest.from_file(APP, default_timeout=15)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    at.session_state["tour_done"] = True
    at.session_state["focus"] = ("accuse", None)
    at.run()
    assert not at.exception
    boxes = [s for s in at.selectbox if s.key and s.key.startswith("accuse_proof_")]
    assert [s.key for s in boxes] == [f"accuse_proof_{c}" for c in COLUMNS]
    assert boxes[0].options[0] == "No proof" and any(o.startswith("1 · ") for o in boxes[0].options)


def test_accusing_with_a_proof_shows_it_on_the_closing_screen():
    engine, game = opened_game("A", "D1", "D2", "D4")
    at = AppTest.from_file(APP, default_timeout=15)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    at.session_state["tour_done"] = True
    at.session_state["focus"] = ("accuse", None)
    at.run()
    for column, option in CASE["variants"]["A"]["solution"].items():
        at.pills(key=f"accuse_{column}").set_value(option)
    at.selectbox(key="accuse_proof_why").set_value("D4")
    at.selectbox(key="accuse_proof_who").set_value("D1")
    at.run()
    next(b for b in at.button if b.label == "Accuse").click().run()
    next(b for b in at.button if b.label == "Yes, accuse").click().run()
    assert not at.exception
    assert at.session_state["game"]["status"] == "solved"
    captions = " ".join(c.value for c in at.caption)
    assert "Your proofs: Who ✗ · How – · Where – · Why ✓" in captions
