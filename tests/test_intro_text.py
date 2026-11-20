"""The start screen says plainly how time works, and the tour and map use the team's wording."""

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

import board
from game.engine import Engine

ROOT = Path(__file__).resolve().parent.parent
CASE = json.loads((ROOT / "data" / "case.json").read_text(encoding="utf-8"))


def intro_page():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15)
    at.session_state["game"] = Engine().new_game(seed=1, variant="A").to_dict()
    at.run()
    assert not at.exception
    return "\n".join(m.value for m in at.markdown)


def test_the_exam_is_the_investments_exam_everywhere():
    text = (ROOT / "data" / "case.json").read_text(encoding="utf-8") + (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Semiconductor Valuation" not in text and "SV_Final" not in text
    assert "Investments exam" in intro_page()


def test_the_start_screen_explains_that_time_runs_out():
    page = intro_page()
    hours = CASE["clock"]["limit_minutes"] // 60
    assert f"You have <b>{hours} hours</b>" in page
    assert "Every search and every question moves the clock forward" in page
    assert f'−{CASE["clock"]["clue_cost"]} min' in page and f'−{CASE["clock"]["question_cost"]} min' in page
    assert f'no time · {CASE["max_strikes"]} tries' in page


def test_the_tour_uses_the_new_wording():
    tour = board.tutorial_html()
    assert "To search a new area, click on the red circle." in tour
    assert "Tap a face to question them, or show them an evidence card." in tour
