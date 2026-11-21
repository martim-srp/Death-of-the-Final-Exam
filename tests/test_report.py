"""The honour council report the player downloads when the case closes (report.py)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import report
from game.case import load_case
from game.engine import Engine, GameError

APP = str(Path(__file__).resolve().parents[1] / "app.py")
CASE = load_case()


def solved_game(variant="A", seed=1):
    engine = Engine()
    game = engine.new_game(seed=seed, variant=variant)
    engine.open_clue(game, "D1")
    engine.open_clue(game, "L4")
    engine.present(game, "companion", "L4")  # catches "I never went to his office door"
    engine.accuse(game, "exchange", "own_card_print", "residence", "cheat")  # one wrong guess
    engine.accuse(game, **CASE["variants"][variant]["solution"])
    return engine, game


def test_no_report_while_the_case_is_open():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    with pytest.raises(GameError):
        report.build(engine, game)


def test_report_sums_up_the_investigation():
    engine, game = solved_game()
    text = report.build(engine, game, "Lúcia")
    assert text.startswith(f"# Honour council report: {CASE['title']}")
    assert "Examiner: **Lúcia**" in text
    assert "**Case solved** at 01:10" in text
    assert "- Evidence examined: 2 of" in text
    assert "- Evidence 1. The leaked PDF" in text
    assert "- Wrong accusations: 1 of 3" in text
    assert "I never went to his office door." in text and "Broken by evidence 12." in text


@pytest.mark.parametrize("variant", sorted(CASE["variants"]))
def test_report_gives_the_answer_and_the_scene_of_that_variant(variant):
    engine, game = solved_game(variant)
    text = report.build(engine, game)
    solution = CASE["variants"][variant]["solution"]
    for column, option in solution.items():
        name = next(o["label"] for o in CASE["accusation"][column] if o["id"] == option)
        assert name.replace("'", "'") in text.replace("\\", "")
    assert "## The boardroom confrontation" in text
    assert "{" not in text  # every placeholder is filled


def test_report_never_contains_unopened_clue_text():
    engine, game = solved_game()
    text = report.build(engine, game)
    opened = set(game.opened)
    for clue_id, clue in engine._clues(game).items():
        if clue_id not in opened and clue.get("text"):
            snippet = clue["text"][:60]
            assert snippet not in text, clue_id


def test_cold_case_report():
    engine = Engine()
    game = engine.new_game(seed=2, variant="B")
    for _ in range(CASE["max_strikes"]):
        engine.accuse(game, "exchange", "photographed_desk", "beach_cafe", "sell_paper")
    text = report.build(engine, game)
    assert "The case went cold" in text
    assert "- Evidence examined: 0 of" in text
    assert "## Evidence examined\n\n- None." in text


def test_odd_names_cannot_break_the_file():
    engine, game = solved_game()
    text = report.build(engine, game, "<b>*Bold*</b> " + "x" * 100)
    assert "<b>" not in text and "*Bold*" not in text
    examiner_line = next(line for line in text.splitlines() if line.startswith("Examiner:"))
    assert len(examiner_line) < 80


def test_the_finale_offers_the_report_download():
    engine, game = solved_game()
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    at.run()
    assert not at.exception
    buttons = at.get("download_button")
    assert len(buttons) == 1
    assert "honour council report" in buttons[0].proto.label.lower()


def test_no_download_while_playing():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    at.run()
    assert not at.exception
    assert not at.get("download_button")
