"""An open evidence card has a "Show this card to" row: one tap shows it to a suspect and opens their interrogation."""

from game.case import load_case
from game.engine import Engine
from tests.test_board_game import page, start

CASE = load_case()


def game_with(*clues, variant="A"):
    engine = Engine()
    game = engine.new_game(seed=1, variant=variant)
    for clue in clues:
        engine.open_clue(game, clue)
    return game


def test_an_open_card_offers_every_suspect_and_the_cost():
    at = start(game=game_with("D1"), focus=("clue", "D1"))
    pills = at.pills(key="show_to_D1")
    import board

    assert pills.options == [board.short_name(s["name"]) for s in CASE["suspects"].values()]
    assert pills.label == f"Show this card to · {CASE['clock']['question_cost']} min"


def test_a_closed_or_locked_card_has_no_show_row():
    at = start(focus=("clue", "D1"))  # available, not opened yet
    assert not [p for p in at.get("button_group") if p.key == "show_to_D1"]
    at = start(focus=("clue", "D3"))  # locked
    assert not [p for p in at.get("button_group") if p.key == "show_to_D3"]


def test_showing_from_the_card_catches_the_lie_and_opens_the_interrogation():
    at = start(game=game_with("D1", "D2"), focus=("clue", "D2"))
    at.pills(key="show_to_D2").set_value("ta").run()
    assert not at.exception
    assert at.session_state["focus"] == ("suspect", "ta")
    text = page(at)
    assert "Caught lying" in text and "You slide" in text
    saved = at.session_state["game"]
    assert ["ta", "proofread_on_screen"] in saved["contradictions"]
    assert saved["clock"] == 30 + 30 + CASE["clock"]["question_cost"]


def test_a_suspect_already_shown_the_card_is_ticked():
    at = start(game=game_with("D1", "D2"), focus=("clue", "D2"))
    at.pills(key="show_to_D2").set_value("professor").run()
    at.session_state["focus"] = ("clue", "D2")
    at.run()
    labels = at.pills(key="show_to_D2").format_func
    assert labels("professor").startswith("✓ ") and not labels("ta").startswith("✓")


def test_showing_after_nine_is_refused_and_stays_on_the_card():
    game = game_with("D1", "D2")
    game.clock = CASE["clock"]["limit_minutes"]
    at = start(game=game, focus=("clue", "D2"))
    at.pills(key="show_to_D2").set_value("ta").run()
    assert not at.exception
    assert at.session_state["focus"] == ("clue", "D2")
    assert at.session_state["game"]["contradictions"] == []
