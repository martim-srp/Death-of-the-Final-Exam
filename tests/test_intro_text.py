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
    box = page[page.find('<div class="clock-rule">'):]
    box = box[:box.find("</div>")]
    assert f"{hours} hours" in box and box.count("hours") == 1  # said once, in the headline
    assert "every search and every question moves it forward" in box
    assert f'−{CASE["clock"]["clue_cost"]} min' in page and f'−{CASE["clock"]["question_cost"]} min' in page
    assert f'no time · {CASE["max_strikes"]} tries' in page


def test_the_tour_uses_the_new_wording():
    tour = board.tutorial_html()
    assert "To search a new area, click on the red circle." in tour
    assert "Tap a face to question them, or show them an evidence card." in tour


def test_the_status_bar_names_its_counters_without_hovering():
    hud = board.hud_html("00:00", 540, 540, 3, 3, 0, None, "Detective")
    assert "tries left</small>" in hud and "0</b><small>lies caught</small>" in hud
    assert "1</b><small>lie caught</small>" in board.hud_html("01:00", 480, 540, 2, 3, 1, None, "Detective")


def test_the_time_box_comes_first_right_after_the_story():
    page = intro_page()
    hours = CASE["clock"]["limit_minutes"] // 60
    assert f"Every action costs time. Use your {hours} hours well." in page
    story, box, whos_who = page.find("class=\"story\""), page.find('<div class="clock-rule">'), page.find("Who's who")
    assert -1 < story < box < whos_who


def test_look_closer_explains_the_ai_trap():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "D1")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    at.session_state["tour_done"] = True
    at.session_state["focus"] = ("clue", "D1")
    at.run()
    at.toggle(key="hidden_D1").set_value(True).run()
    assert not at.exception
    captions = " ".join(c.value for c in at.caption)
    assert "prompt injection" in captions and "never the evidence" in captions
