"""The four questions, always in sight: WHO, HOW, WHERE, WHY, with what is still possible.

Playtesters lost track of what they were solving. The strip under the next step counts the
options left in each question (crossed off by the player or ruled out by the evidence),
names the answer once one is left, and opens the notebook when tapped.
"""

import board
from game.engine import Engine
from tests.test_board_game import board_markup, start


def strip(at):
    markup = board_markup(at)
    return markup[markup.index('<div class="case-strip"'):].split("</div>")[0]


def test_a_new_case_shows_the_four_questions_with_every_option_open():
    html = strip(start())
    for column, noun in (("WHO", "suspects"), ("HOW", "methods"), ("WHERE", "places"), ("WHY", "motives")):
        assert f"<small>{column}</small><b>5 {noun} left</b>" in html
    assert html.count('data-act="sheet"') == 4


def test_tapping_the_strip_opens_the_notebook():
    assert board.parse_act("sheet", {}, {}) == ("sheet", None)


def test_crossing_off_in_the_notebook_counts_down_and_survives_closing_it():
    at = start(focus=("sheet", None))
    at.pills(key="sheet_who").set_value(["professor", "companion", "exchange", "ta"]).run()
    at.session_state["focus"] = ("home", None)
    at.run()
    at.run()  # Streamlit drops a closed widget's value after a run without it
    assert "<small>WHO</small><b>Class Representative</b>" in strip(at)
    assert 'class="cq solved"' in strip(at)
    at.session_state["focus"] = ("sheet", None)
    at.run()
    assert set(at.pills(key="sheet_who").value) == {"professor", "companion", "exchange", "ta"}


def test_options_proven_wrong_count_too():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.accuse(game, "professor", "photographed_desk", "beach_cafe", "sell_paper")  # wrong everywhere
    assert len(engine.eliminated(game)) == 4
    html = strip(start(game=game))
    for column, noun in (("WHO", "suspects"), ("HOW", "methods"), ("WHERE", "places"), ("WHY", "motives")):
        assert f"<small>{column}</small><b>4 {noun} left</b>" in html


def test_a_new_case_clears_the_cross_offs():
    at = start(focus=("sheet", None))
    at.pills(key="sheet_why").set_value([at.pills(key="sheet_why").options[0]]).run()
    assert at.session_state["crossed_why"]
    at.session_state["focus"] = ("home", None)
    at.run()
    at.button(key="new_case").click().run()
    assert "crossed_why" not in at.session_state


def test_the_strip_text_wraps_to_two_lines_instead_of_cutting_words_and_is_smaller_on_phones():
    css = board.BOARD_CSS
    rule = css[css.index(".case-strip .cq b {"):].split("}")[0]
    assert "-webkit-line-clamp: 2" in rule and "nowrap" not in rule
    phone = css[css.rindex("@media (max-width: 640px) {"):]
    assert ".case-strip .cq { padding: 4px 6px; font-size: 12px; }" in phone
