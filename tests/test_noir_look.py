"""The noir look: suspect portraits, the row of suspect cards and the detective's notebook."""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from game.case import load_case
from game.engine import Engine

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")
PORTRAITS = ROOT / "assets" / "suspects"
SUSPECTS = list(load_case()["suspects"])


def start(variant="A", seed=1):
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = Engine().new_game(seed=seed, variant=variant).to_dict()
    at.run()
    assert not at.exception
    return at


def click(at, starts_with):
    next(b for b in at.button if b.label.startswith(starts_with)).click().run()
    assert not at.exception


def page(at):
    return "\n".join(m.value for m in at.markdown)


def cards(at):
    """The HTML of the suspect card row."""
    return next(m.value for m in at.markdown if 'class="suspect-row"' in m.value)


def notebook_box(at, label):
    return next(c for c in at.sidebar.checkbox if c.label == label)


@pytest.mark.parametrize("suspect", SUSPECTS)
def test_every_suspect_has_a_small_portrait_with_a_title(suspect):
    path = PORTRAITS / f"{suspect}.svg"
    assert path.exists()
    assert path.stat().st_size < 20_000
    root = ET.parse(path).getroot()
    assert root.tag.endswith("svg")
    assert root.find("{http://www.w3.org/2000/svg}title").text == load_case()["suspects"][suspect]["name"]


def test_portraits_are_not_extra_images():
    # The cover stays the only st.image; portraits are inline, so the start screen is unchanged.
    at = start()
    assert len(at.get("image")) == 1


def test_cards_show_every_suspect_not_questioned_at_the_start():
    at = start()
    row = cards(at)
    assert row.count('class="suspect-card') == len(SUSPECTS)
    assert row.count("Not questioned yet") == len(SUSPECTS)
    assert row.count("data:image/svg+xml;base64,") == len(SUSPECTS)
    assert "RULED OUT" not in row


def test_questioning_a_suspect_marks_their_card():
    at = start()
    at.selectbox[0].set_value("professor")
    at.selectbox[1].set_value("exam").run()
    click(at, "Ask (")
    row = cards(at)
    assert row.count("Not questioned yet") == len(SUSPECTS) - 1
    assert "Questioned" in row


def test_a_caught_contradiction_shows_on_the_card():
    at = start()
    click(at, "Open 📍 L4")
    at.selectbox[0].set_value("companion")
    at.selectbox[2].set_value("L4").run()
    click(at, "Show clue")
    assert "⚡ 1 caught" in cards(at)


def test_question_tab_shows_the_selected_suspects_portrait():
    at = start()
    at.selectbox[0].set_value("ta").run()
    assert 'class="suspect-portrait"' in page(at)
    assert 'alt="The Teaching Assistant"' in page(at)


def test_ruling_out_in_the_notebook_stamps_the_card_and_leaves_the_game_alone():
    at = start()
    before = dict(at.session_state["game"])
    notebook_box(at, "The Exchange Student").check().run()
    assert not at.exception
    row = cards(at)
    assert row.count("RULED OUT") == 1
    assert 'class="suspect-card ruled-out"' in row
    assert at.session_state["game"] == before  # notes never change the clock or the case


def test_notebook_lists_only_opened_clues():
    at = start()
    labels = [c.label for c in at.sidebar.checkbox]
    assert labels == [load_case()["suspects"][s]["name"] for s in SUSPECTS]
    assert any("Open a clue in the case file" in c.value for c in at.sidebar.caption)
    click(at, "Open 📍 L4")
    labels = [c.label for c in at.sidebar.checkbox]
    assert any(label.startswith("L4. ") for label in labels)
    assert not any(label.startswith("D2. ") for label in labels)  # not opened, so not listed


def test_new_case_clears_the_notebook():
    at = start()
    notebook_box(at, "The Professor").check().run()
    at.sidebar.text_area[0].input("The bag never left his chair?").run()
    click(at, "New case")
    assert not notebook_box(at, "The Professor").value
    assert at.sidebar.text_area[0].value == ""
    assert "RULED OUT" not in cards(at)


def test_no_cards_or_notebook_once_the_case_is_closed():
    game = Engine().new_game(seed=1, variant="A")
    game.status = "cold"
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = game.to_dict()
    at.run()
    assert not at.exception
    assert not any('class="suspect-row"' in m.value for m in at.markdown)
    assert not any(e.label.startswith("📓") for e in at.sidebar.expander)
