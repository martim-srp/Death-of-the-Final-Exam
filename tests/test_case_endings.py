"""All six outcomes: solved confrontations, or unsolved stories with a player-only answer."""

from html import unescape
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import board
import report
from game.case import load_case
from game.engine import Engine, GameError

APP = str(Path(__file__).resolve().parents[1] / "app.py")
CASE = load_case()
VARIANTS = sorted(CASE["variants"])


def close_case(variant, status):
    engine = Engine()
    game = engine.new_game(seed=7, variant=variant)
    if status == "solved":
        engine.accuse(game, **CASE["variants"][variant]["solution"])
    else:
        for _ in range(CASE["max_strikes"]):
            engine.accuse(game, "exchange", "photographed_desk", "beach_cafe", "sell_paper")
    assert game.status == status
    return engine, game


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("status", ["solved", "cold"])
def test_all_six_endings_on_screen_and_in_the_report(variant, status):
    engine, game = close_case(variant, status)
    at = AppTest.from_file(APP, default_timeout=15)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    at.session_state["tour_done"] = True
    at.run()
    assert not at.exception

    page = "\n".join(m.value for m in at.markdown)
    text = report.build(engine, game)
    scene = report.closing_scene(engine, game)
    if status == "solved":
        confrontation = next(e for e in at.expander if e.label == "Read the confrontation")
        assert confrontation.proto.expanded
        assert "Campus security arrives" in page and "Campus security arrives" in text
        culprit = CASE["variants"][variant]["solution"]["who"]
        name = CASE["suspects"][culprit]["name"]
        assert f"identifies the {name.removeprefix('The ')} as the culprit" in scene
        assert "escort" in scene and "out of the boardroom" in scene
        assert board.find_picture("suspects", culprit) in page
        assert 'class="facts"' in page
        assert "exam will go ahead at 09:00 using version 4" in page
        assert "Separately," in page  # The Professor's responsibility follows the solved theft.
        assert "Half past seven" not in text
        assert "not in any directory" not in text
    else:
        assert "The case remains unsolved. The exam is cancelled." in page
        assert "the Dean cancels the exam" in page and "The Dean cancels the exam" in text
        assert "culprit remains unidentified" in page and "culprit remains unidentified" in text
        assert not any(e.label == "Read the confrontation" for e in at.expander)
        assert 'class="facts"' in page
        assert any(h.value == "#### The correct solution" for h in at.markdown)
        assert "## The correct solution (for the player)" in text
        for suspect in CASE["suspects"]:
            assert board.find_picture("suspects", suspect) not in page
        for output in (page, text):
            assert "Campus security arrives" not in output
            assert "exam will go ahead" not in output

    solution = engine.solution(game)
    for column in report.COLUMNS:
        name = next(o["label"] for o in CASE["accusation"][column] if o["id"] == solution[column])
        assert name in unescape(page)
        assert f"- **{column.capitalize()}:** {report._plain(name)}" in text

    assert "Share the game" in [c.value for c in at.caption]
    assert len(at.get("download_button")) == 1
    assert any(b.label == "Play a new case" for b in at.button)
    assert len(at.metric) == 5
    for paragraph in scene.split("\n\n"):
        assert report._plain(paragraph) in text


@pytest.mark.parametrize("variant", VARIANTS)
def test_cold_story_does_not_discover_the_culprit_but_the_player_gets_the_answer(variant, monkeypatch):
    engine, game = close_case(variant, "cold")

    def unexpected_solution(*args, **kwargs):
        pytest.fail("The cold story must not discover the culprit")

    with monkeypatch.context() as story_only:
        story_only.setattr(Engine, "solution", unexpected_solution)
        assert report.closing_scene(engine, game) == CASE["cold_ending"]
    assert "case remains unsolved" in report.build(engine, game)
    at = AppTest.from_file(APP, default_timeout=15)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    at.run()
    assert not at.exception


@pytest.mark.parametrize("variant", VARIANTS)
def test_an_open_case_cannot_reveal_any_ending(variant):
    engine = Engine()
    game = engine.new_game(seed=7, variant=variant)
    with pytest.raises(GameError):
        report.closing_scene(engine, game)
    with pytest.raises(GameError):
        report.build(engine, game)


def test_representatives_early_email_is_a_draft_rather_than_a_sent_report():
    scene = CASE["variants"]["A"]["denouement"]
    assert "sent your report to the Dean at 23:52" in scene
    assert "saved a draft at 21:15" in scene
    assert "reported the crime" not in scene


def test_companions_theft_and_cover_story_are_explained_separately():
    scene = CASE["variants"]["C"]["denouement"]
    assert "sell its secrets to a foreign power" in scene
    assert "drawing attention away from your theft of the full financial model" in scene
    assert "The bag stayed on the chair. But the Professor left the table." in scene
