"""The walkthrough is graded on explaining how, why, the limits and how it could change.

Each design decision in the README says its limit and how it could change, and How to play
matches what the game does now.
"""

import re
from pathlib import Path

README = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")


def section(title):
    match = re.search(rf"^#{{2,3}} {re.escape(title)}\n(.*?)(?=^#{{2,3}} |\Z)", README, re.MULTILINE | re.DOTALL)
    assert match, f"README has no '{title}' section"
    return match.group(1)


def test_each_design_decision_names_a_limit_and_how_it_could_change():
    for title in ("The engine decides, the AI only acts", "What happens when the AI is unavailable",
                  "Where the data is stored", "Security"):
        text = section(title)
        assert "**Limit" in text, title
        assert "**How it could change:**" in text, title


def test_how_to_play_says_09_00_leaves_only_the_accusation():
    text = section("How to play")
    assert "At 09:00 you can no longer search or ask" in text
    assert "or at 09:00, the case goes cold" not in text


def test_how_to_play_says_a_cold_case_shows_the_player_the_answer():
    assert "shows you, the\nplayer, the correct answer" in section("How to play")


def test_how_to_play_names_calm_mode_and_the_save_link():
    text = section("How to play")
    assert "calm mode" in text
    assert "save icon" in text


def test_the_simulated_players_are_listed_as_covered():
    assert "tests/test_random_players.py" in section("What the tests cover, and what they do not")
