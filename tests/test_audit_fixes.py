"""Fixes from Salvador's audit of the deployed game.

1. On the deployed site, Streamlit's badge sat over the save icon (bottom-right, desktop).
2. "1 to 3 sentences" and "never confess" were only asked in the prompt. A model reply that
   confessed (a false confession misleads the player) or ran long was shown as is.
"""

import json
from pathlib import Path

import pytest

import game.ai as ai
from game.engine import Engine

ROOT = Path(__file__).resolve().parent.parent
CRACKS = json.loads((ROOT / "data" / "cracks.json").read_text(encoding="utf-8"))


def reply(text, topic="alibi"):
    return lambda _prompt, _question: json.dumps({"reply": text, "topic": topic})


def test_the_corner_icons_sit_above_streamlits_badge_on_desktop():
    css = (ROOT / "assets" / "style.css").read_text(encoding="utf-8")
    lift = css[css.index("Lift both icons clear of it on desktop"):]
    assert ".st-key-save_corner { bottom: 4.5rem; }" in lift
    assert ".st-key-restart_corner { bottom: calc(4.5rem + 66px); }" in lift


@pytest.mark.parametrize("text", [
    "Fine. I leaked it. I printed it with the TA's card.",
    "Yes, I posted it.",
    "All right, I did it!",
    "I confess.",
    "It was me.",
    "It was me who leaked it.",
    "I am the culprit.",
])
def test_a_confession_from_the_model_is_never_shown(text):
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    answer = ai.ask(engine, game, "companion", "Where were you last night?", complete=reply(text))
    assert answer["reply"] != text and "leaked it" not in answer["reply"]
    assert game.history[-1]["fallback"] == "off_script"


@pytest.mark.parametrize("text", [
    "I did not leak it.",
    "You think I did it? Please.",
    "It wasn't me, darling.",
    "I went to the library. I lied about that.",
    "I confess I was at the library.",
    "It was me who reported it to the Dean.",
    "I'm guilty of nothing.",
])
def test_denials_and_small_admissions_still_get_through(text):
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    answer = ai.ask(engine, game, "class_rep", "Where were you?", complete=reply(text))
    assert answer["reply"] == text
    assert "fallback" not in game.history[-1]


def test_every_scripted_crack_line_passes_the_check():
    lines = [line for variant in CRACKS["variants"].values() for line in variant.values()]
    assert lines
    for line in lines:
        assert not ai.confesses(line), line


def test_a_long_reply_is_cut_to_three_sentences():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    text = 'One thing. "Two things!" Three things? Four things. Five things.'
    answer = ai.ask(engine, game, "professor", "Tell me everything.", complete=reply(text))
    assert answer["reply"] == 'One thing. "Two things!" Three things?'


def test_the_chat_says_why_a_scripted_answer_replaced_the_model():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "\"off_script\": \"The AI's answer went off script, so this is the suspect's scripted answer.\"" in source
