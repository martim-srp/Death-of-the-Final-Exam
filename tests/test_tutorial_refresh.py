"""The learn-as-you-play hints and the guide players can reopen from the book button."""

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

import board
from game.engine import Engine

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")


def start(*, focus=None, intro_done=True, guide_open=False, game=None):
    at = AppTest.from_file(APP, default_timeout=15)
    at.session_state["game"] = (game or Engine().new_game(seed=1, variant="A")).to_dict()
    at.session_state["intro_done"] = intro_done
    at.session_state["guide_open"] = guide_open
    if focus:
        at.session_state["focus"] = focus
    at.run()
    assert not at.exception
    return at


def page(at):
    return "\n".join(item.value for item in at.markdown)


def board_markup(at):
    for component in at.get("bidi_component"):
        markup = json.loads(component.proto.json)
        if 'class="hud' in markup:
            return markup
    raise AssertionError("The game board was not rendered")


def test_first_move_hint_is_inline_and_the_dimming_tour_is_gone():
    at = start()
    assert "Start with the glowing card in Evidence" in page(at)
    assert "D1. The leaked PDF" in page(at)
    assert 'class="tour"' not in board_markup(at)


def test_clue_hint_appears_beside_its_open_button():
    at = start(focus=("clue", "D1"))
    assert "Tap the button to reveal this clue" in page(at)
    assert any(button.label.startswith("Open it") for button in at.button)


def test_suspect_hint_explains_questions_and_showing_a_card():
    at = start(focus=("suspect", "professor"))
    assert "Choose a suggested question below" in page(at)
    assert any(pill.label.startswith("Ask") for pill in at.pills)


def test_accusation_hint_sits_with_the_accusation_choices():
    at = start(focus=("accuse", None))
    assert "Choose one answer in each row" in page(at)
    assert "Who did it, how, where and why?" in page(at)


def test_intro_keeps_the_briefing_and_leaves_the_rules_for_the_quick_guide():
    at = start(intro_done=False)
    assert "Semiconductor Valuation" in page(at)
    assert "You’ll get short hints as you play" in page(at)
    assert "Search</b> places and documents" not in page(at)


def test_quick_guide_opens_and_closes_without_restarting_the_intro():
    at = start(guide_open=True)
    assert "before 09:00" in page(at)
    assert "Search" in page(at) and "Show" in page(at) and "Accuse" in page(at)
    assert any(button.label == "Back to the case" for button in at.button)
    next(button for button in at.button if button.label == "Back to the case").click().run()
    assert not at.exception
    assert at.session_state["intro_done"] is True
    assert at.session_state["guide_open"] is False


def test_book_button_is_labeled_and_routes_to_the_quick_guide():
    at = start()
    assert 'data-act="intro" title="Quick guide"' in board_markup(at)
    assert board.parse_act("intro", Engine().case["suspects"], Engine().case["clues"]) == ("intro", None)
