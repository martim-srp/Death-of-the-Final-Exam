"""A file name from the case, typed without its extension, is game data, not a password.

Found while playing: "Did you print INV_Final_v3?" (Evidence 1's file name, no ".pdf") was
hidden as a password, cost the question, and earned the password badge from the Companion.
"""

import pytest

from game.case import load_case
from game.engine import Engine, case_vocabulary, looks_like_secret


@pytest.fixture(scope="module")
def engine():
    return Engine()


def test_the_vocabulary_has_file_names_with_and_without_their_extension():
    words = case_vocabulary(load_case())
    assert "inv_final_v3.pdf" in words
    assert "inv_final_v3" in words


@pytest.mark.parametrize("text", ["Did you print INV_Final_v3?", "Who sent inv_final_v3 to the group?"])
def test_the_leaked_file_name_without_pdf_is_not_a_secret(engine, text):
    game = engine.new_game(seed=1, variant="A")
    assert engine.check_secret(game, "companion", text) is False
    assert game.badges == []


@pytest.mark.parametrize("text", ["my_final_v9", "Lisboa2026", "INV_Final_v3x9"])
def test_other_file_like_words_are_still_checked(engine, text):
    assert looks_like_secret(text, case_vocabulary(load_case()))
