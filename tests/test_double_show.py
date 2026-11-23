"""A double tap on the same evidence card shows it once.

Tapping a "Show an evidence card" pill (or a suspect under an open card) twice before the page
redraws sent two presentations: the suspect answered twice and the clock lost the minutes twice.
Showing the same card to the same suspect straight after it was shown is now ignored, and costs
nothing. Showing it again later, after another move, still works as before.
"""

from game.case import load_case
from game.engine import Engine
from tests.test_board_game import page, start

CASE = load_case()
COST = CASE["clock"]["question_cost"]


def game_with(*clues):
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    for clue in clues:
        engine.open_clue(game, clue)
    return game


def presents(at):
    return [e for e in at.session_state["game"]["history"] if e["action"] == "present"]


def test_a_double_tap_in_the_interrogation_shows_the_card_once():
    at = start(game=game_with("D1", "D2"), focus=("suspect", "ta"), suspect="ta")
    clock = at.session_state["game"]["clock"]
    at.pills(key="show_clue").set_value("D2").run()
    at.pills(key="show_clue").set_value("D2").run()
    assert not at.exception
    assert len(presents(at)) == 1
    assert at.session_state["game"]["clock"] == clock + COST
    assert page(at).count("You slide") == 1


def test_a_double_tap_under_the_card_shows_it_once():
    at = start(game=game_with("D1", "D2"), focus=("clue", "D2"))
    clock = at.session_state["game"]["clock"]
    at.pills(key="show_to_D2").set_value("professor").run()
    at.session_state["focus"] = ("clue", "D2")
    at.run()
    at.pills(key="show_to_D2").set_value("professor").run()
    assert not at.exception
    assert len(presents(at)) == 1
    assert at.session_state["game"]["clock"] == clock + COST


def test_a_different_suspect_or_card_is_still_shown():
    at = start(game=game_with("D1", "D2"), focus=("suspect", "ta"), suspect="ta")
    at.pills(key="show_clue").set_value("D2").run()
    at.pills(key="show_clue").set_value("D1").run()
    assert [e["clue"] for e in presents(at)] == ["D2", "D1"]


def test_the_same_card_can_be_shown_again_after_another_move():
    at = start(game=game_with("D1", "D2"), focus=("suspect", "ta"), suspect="ta")
    at.pills(key="show_clue").set_value("D2").run()
    at.pills(key="show_clue").set_value("D1").run()
    at.pills(key="show_clue").set_value("D2").run()
    assert [e["clue"] for e in presents(at)] == ["D2", "D1", "D2"]
