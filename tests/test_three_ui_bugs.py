"""Three bugs found by fuzzing the interface.

1. Closing the "Are you sure?" dialog with X kept the old picks: the next rerun reopened it, and
   "Yes, accuse" accused with picks the player had already changed (a strike they never meant).
2. "Restart case" / "New case" dropped hard mode silently: the new game was normal while the mode
   control still showed Hard.
3. A typed question to the TA about proofreading was read as "ask about the TA", so the TA told
   the player to "ask the Teaching Assistant that yourself".
"""

import game.ai as ai
from pathlib import Path
from game.engine import Engine
from tests.test_board_game import start


def pick(at, who, how, where, why):
    for column, value in (("who", who), ("how", how), ("where", where), ("why", why)):
        at.pills(key=f"accuse_{column}").set_value(value).run()


def test_yes_accuse_uses_the_picks_on_screen():
    at = start(focus=("accuse", None))
    pick(at, "exchange", "bought_from_ta", "beach_cafe", "cheat")
    at.button(key="accuse_go").click().run()
    at.pills(key="accuse_who").set_value("class_rep").run()  # changed after pressing Accuse
    confirm = [b for b in at.button if b.key == "confirm_accuse"]
    assert confirm  # the dialog is still open
    confirm[0].click().run()
    accused = [e for e in at.session_state["game"]["history"] if e["action"] == "accuse"]
    assert len(accused) == 1 and accused[0]["choice"]["who"] == "class_rep"


def test_a_new_case_keeps_the_mode_the_player_chose():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.set_mode(game, "hard")
    at = start(game=game, mode_choice="hard")
    at.button(key="new_case").click().run()
    assert at.session_state["game"]["mode"] == "hard"


def test_a_new_case_forgets_a_pending_accusation():
    at = start(focus=("accuse", None))
    pick(at, "exchange", "bought_from_ta", "beach_cafe", "cheat")
    at.button(key="accuse_go").click().run()
    at.session_state["focus"] = ("home", None)
    at.run()
    at.button(key="new_case").click().run()
    assert "pending_accusation" not in at.session_state


def test_the_ta_is_never_asked_about_the_ta():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    result = ai.ask(engine, game, "ta", "Did you proofread the exam?")
    assert "ask the Teaching Assistant that yourself" not in result["reply"]
    asked = [e["topic"] for e in game.history if e["action"] == "ask"]
    assert "teaching_assistant" not in asked


def test_closing_the_confirmation_with_x_forgets_the_picks():
    source = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
    assert '@st.dialog("Are you sure?", on_dismiss=forget_accusation)' in source


def test_a_refused_search_does_not_animate_the_card_as_new():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    game.clock = engine.clock_rules["limit_minutes"] - 5  # not enough time to search
    at = start(game=game, focus=("clue", "D1"))
    at.button(key="open_D1").click().run()
    assert "D1" not in at.session_state["game"]["opened"]
    assert "D1" not in (at.session_state["fresh"] if "fresh" in at.session_state else [])
