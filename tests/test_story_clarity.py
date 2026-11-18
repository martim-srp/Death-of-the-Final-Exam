"""A first-time player can tell who is who and follow the clue wording."""

from html import escape as html_escape
from pathlib import Path

import pytest

from game.case import load_case, resolve_variant

CASE = load_case()
APP = Path(__file__).resolve().parent.parent / "app.py"


def test_every_suspect_has_a_short_role_for_the_whos_who():
    for sid, suspect in CASE["suspects"].items():
        role = suspect.get("role")
        assert isinstance(role, str) and role.strip(), sid
        assert len(role.split()) <= 7, sid  # light text: a few words, never a paragraph


def test_a_role_never_names_another_suspect_or_gives_the_answer():
    names = [s["name"].removeprefix("The ") for s in CASE["suspects"].values()]
    for sid, suspect in CASE["suspects"].items():
        own = suspect["name"].removeprefix("The ")
        for name in names:
            if name not in (own, "Professor"):  # the Companion's role says whose date she is
                assert name not in suspect["role"], (sid, name)
        for word in ("leaked", "stole", "guilty", "culprit"):
            assert word not in suspect["role"].lower(), sid


@pytest.mark.parametrize("variant", sorted(CASE["variants"]))
def test_clue_text_has_no_programmer_jargon(variant):
    resolved = resolve_variant(CASE, variant)
    for clue_id, clue in resolved["clues"].items():
        text = clue.get("text", "") + clue.get("log", "")
        for word in ("commit ", "text layer", "File properties"):
            assert word not in text, (variant, clue_id, word)


@pytest.mark.parametrize("variant", sorted(CASE["variants"]))
def test_the_anonymous_number_posts_the_paper_at_the_time_the_intro_gives(variant):
    d5 = resolve_variant(CASE, variant)["clues"]["D5"]["text"]
    assert "posted the paper at 23:47" in d5
    assert "23:47" in APP.read_text(encoding="utf-8")


def test_the_start_screen_shows_the_whos_who():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=30).run()
    html = " ".join(m.value for m in at.markdown)
    assert "whos-who" in html
    for suspect in CASE["suspects"].values():
        assert html_escape(suspect["role"]) in html
