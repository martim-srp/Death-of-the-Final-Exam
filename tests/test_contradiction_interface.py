"""Interface for the contradiction detector: the caught moment and the list of contradictions."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from game.engine import Engine

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def start(variant="A", seed=1):
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = Engine().new_game(seed=seed, variant=variant).to_dict()
    at.run()
    assert not at.exception
    return at


def click(at, starts_with):
    next(b for b in at.button if b.label.startswith(starts_with)).click().run()
    assert not at.exception


def show(at, suspect, clue):
    at.selectbox[0].set_value(suspect)
    at.selectbox[2].set_value(clue).run()
    click(at, "Show clue")


def text(at):
    return "\n".join(m.value for m in at.markdown)


def board_label(at):
    return next(e.label for e in at.expander if e.label.startswith("🧩"))


def test_no_contradictions_at_the_start():
    at = start()
    assert "Contradiction!" not in text(at)
    assert board_label(at) == "🧩 Contradictions caught (0)"
    assert any("None yet" in c.value for c in at.caption)


def test_breaking_clue_shows_the_caught_moment_and_lists_it():
    at = start()
    click(at, "Open 📍 L4")
    show(at, "companion", "L4")
    page = text(at)
    assert "Contradiction! The Companion was caught out" in page
    assert "L4" in page and "says otherwise" in page
    assert board_label(at) == "🧩 Contradictions caught (1)"
    assert "Contradictions caught: **1**" in page
    assert at.session_state["game"]["contradictions"] == [["companion", "never_went_to_office_door"]]


def test_irrelevant_clue_shows_no_moment():
    at = start()
    click(at, "Open 📍 L4")
    show(at, "professor", "L4")
    assert "Contradiction!" not in text(at)
    assert board_label(at) == "🧩 Contradictions caught (0)"


def test_showing_the_same_clue_again_does_not_repeat_the_moment():
    at = start()
    click(at, "Open 📍 L4")
    show(at, "companion", "L4")
    show(at, "companion", "L4")
    assert "Contradiction!" not in text(at)
    assert board_label(at) == "🧩 Contradictions caught (1)"


def test_moment_clears_on_the_next_question_but_the_list_stays():
    at = start()
    click(at, "Open 📍 L4")
    show(at, "companion", "L4")
    click(at, "Ask (")
    assert "Contradiction!" not in text(at)
    assert board_label(at) == "🧩 Contradictions caught (1)"


def test_rejected_show_records_nothing():
    at = start()
    click(at, "Open 📍 L4")
    limit = Engine().case["clock"]["limit_minutes"]
    at.session_state["game"] = {**at.session_state["game"], "clock": limit}
    at.run()
    show(at, "companion", "L4")
    assert "Not enough time" in "\n".join(e.value for e in at.error)
    assert "Contradiction!" not in text(at)
    assert board_label(at) == "🧩 Contradictions caught (0)"
