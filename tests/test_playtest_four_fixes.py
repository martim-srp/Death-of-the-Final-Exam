"""Four fixes from a newcomer's playtest.

1. The time left was hidden on most screens: it now sits under the clock, everywhere.
2. The Standings card left its logic to the player: it now says who an annulled exam helps.
3. The real exam asked to value a bifana chain: the companies now sound like an Investments exam.
4. Options were crossed off "by evidence 2" with nothing on card 2 saying why: every
   crossed-off option now carries its reason.
"""

import json
from pathlib import Path

import pytest

import board
import reloading
from game.case import load_case, resolve_variant
from game.engine import Engine
from tests.test_board_game import board_markup, page, start

CASE = load_case()
REASONS = json.loads((Path(__file__).resolve().parent.parent / "data" / "ruleouts.json").read_text(encoding="utf-8"))


def test_time_left_sits_under_the_clock_where_no_screen_hides_it():
    hud = board.hud_html("00:40", 500, 540, 3, 3, 0, None, "Detective")
    # One countdown on screen; the night's hour only on hover (Lúcia: show one or the other, not both).
    assert '<span class="time"><b>8h 20m left</b></span>' in hud
    assert 'title="Night clock: 00:40. The case closes at 09:00."' in hud
    assert "<b>00:40</b>" not in hud
    assert '<b>9h 00m left</b>' in board_markup(start())
    for css in board.BOARD_CSS.split("@container")[1:] + board.BOARD_CSS.split("@media")[1:]:
        block = css.split("}\n}")[0]
        assert ".clock .left { display: none" not in block and ".clock .time { display: none" not in block


def test_the_standings_card_says_who_an_annulled_exam_helps():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "D4")
    text = engine.read_clue(game, "D4")["text"]
    assert "If it is annulled, today's ranking decides the fellowship." in text
    assert "Exchange Student will probably finish first" in text
    assert "today's ranking decides the fellowship" in engine.key_fact(game, "D4")


def test_the_real_exam_values_a_serious_company():
    for company in CASE["random"]["pastry"]:
        assert not any(word in company.lower() for word in ("bifana", "pastel", "ginjinha", "shops"))
    engine = Engine()
    for seed in range(6):
        game = engine.new_game(seed=seed, variant="A")
        game.opened.append("D3")
        assert "Bifanas" not in engine.read_clue(game, "D3")["text"]


@pytest.mark.parametrize("variant", ["A", "B", "C"])
def test_every_card_that_crosses_an_option_off_says_why(variant):
    engine = Engine()
    game = engine.new_game(seed=1, variant=variant)
    for clue_id, clue in resolve_variant(CASE, variant)["clues"].items():
        for column in clue.get("rules_out", {}):
            reason = engine.rule_out_reason(game, clue_id, column)
            assert reason and len(reason) <= 140, (variant, clue_id, column)


def test_the_reasons_file_names_only_real_rule_outs():
    for scope, cards in REASONS.items():
        if scope.startswith("_"):
            continue
        variants = ["A", "B", "C"] if scope == "base" else [scope]
        for clue_id, columns in cards.items():
            for column in columns:
                assert any(column in resolve_variant(CASE, v)["clues"][clue_id].get("rules_out", {}) for v in variants), (
                    scope, clue_id, column)


def test_the_sheet_shows_why_card_2_crossed_off_the_photo_on_the_desk():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    game.history.append({"action": "open", "clue": "D2"})
    game.opened.append("D2")
    at = start(game=game, focus=("sheet", None))
    text = page(at)
    assert "Photographed the paper" in text and "ruled out by evidence 2" in text
    assert "Job 88213 is printed on the leaked pages, and the log shows it printed at the library printer." in text


def test_the_story_text_files_are_watched_so_an_edit_shows_without_a_restart(tmp_path):
    for name in ("data/keyfacts.json", "data/lies.json", "data/ruleouts.json"):
        assert name in reloading.SOURCES
    root = Path(__file__).resolve().parent.parent
    for name in reloading.SOURCES:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes((root / name).read_bytes())
    before = reloading.source_version(tmp_path)
    (tmp_path / "data" / "ruleouts.json").write_text("{}", encoding="utf-8")
    assert reloading.source_version(tmp_path) != before


def test_rule_out_reasons_state_only_what_the_card_shows():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    assert engine.rule_out_reason(game, "D3", "why") == "The leak is the old draft, v3. Students will sit version 4, whose Question 5 is different."
    assert engine.rule_out_reason(game, "D5", "why") == "The paper was posted free to all 212 students in the class group."
    for line in (engine.rule_out_reason(game, "D3", "why"), engine.rule_out_reason(game, "D5", "why")):
        assert "nobody" not in line.lower()


def test_the_start_screen_says_09_00_once():
    at = start(intro_done=False)
    text = "\n".join(m.value for m in at.markdown)
    welcome = text[text.find('class="story"'):text.find("Who's who")]
    assert welcome.count("09:00") == 1  # in the story; the time box says it without the hour
    assert "When the time runs out, you can only accuse." in welcome
