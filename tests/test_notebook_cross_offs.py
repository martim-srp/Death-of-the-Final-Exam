"""The notebook's cross-offs: they outlive the notebook panel and a new case clears them.

(The WHO/HOW/WHERE/WHY strip above the map that counted them was removed to simplify the
board; the notebook keeps the count on each row.)"""

from tests.test_board_game import board_markup, start


def test_there_is_no_case_strip_on_the_board():
    assert 'class="case-strip"' not in board_markup(start())


def test_crossing_off_in_the_notebook_survives_closing_it():
    at = start(focus=("sheet", None))
    at.pills(key="sheet_who").set_value(["professor", "companion", "exchange", "ta"]).run()
    at.session_state["focus"] = ("home", None)
    at.run()
    at.run()  # Streamlit drops a closed widget's value after a run without it
    at.session_state["focus"] = ("sheet", None)
    at.run()
    assert set(at.pills(key="sheet_who").value) == {"professor", "companion", "exchange", "ta"}


def test_a_new_case_clears_the_cross_offs():
    at = start(focus=("sheet", None))
    at.pills(key="sheet_why").set_value([at.pills(key="sheet_why").options[0]]).run()
    assert at.session_state["crossed_why"]
    at.session_state["focus"] = ("home", None)
    at.run()
    at.button(key="new_case").click().run()
    assert "crossed_why" not in at.session_state
