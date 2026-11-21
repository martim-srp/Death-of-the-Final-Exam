"""The README's "How to play" names every feature a player meets, so a stranger can play without help."""

import re
from pathlib import Path

README = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
HOW_TO_PLAY = re.search(r"^## How to play\n(.*?)(?=^## )", README, re.MULTILINE | re.DOTALL).group(1)


def test_how_to_play_names_every_feature():
    for feature in ("Hard mode", "nerves", "crack", "lightning", "proof", "goes cold", "Accuse", "hint"):
        assert feature in HOW_TO_PLAY, feature


def test_how_to_play_says_a_crack_and_a_cold_case_never_reveal_the_culprit():
    assert "never shows who is guilty" in HOW_TO_PLAY
    assert "never tells you who did it" in HOW_TO_PLAY
