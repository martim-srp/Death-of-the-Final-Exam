"""The confession check catches the usual ways a suspect could own up to the leak.

Follow-up to tests/test_audit_fixes.py: "I'm guilty", "I stole the exam" and "I was the one who
leaked it" used to get through. A caught reply is replaced by the suspect's scripted answer.
Every line the game itself writes must still pass, or real answers would be thrown away.
"""

import json
from pathlib import Path

import pytest

from game import ai
from game.engine import Engine

ROOT = Path(__file__).resolve().parents[1]


def reply(text):
    return lambda *_: json.dumps({"reply": text, "topic": "alibi"})


CONFESSIONS = [
    "I'm guilty.",
    "I’m guilty, all right.",
    "Fine, I am guilty of the leak.",
    "I stole the exam.",
    "I stole it from his desk.",
    "I was the one who leaked it.",
    "I'm the one who posted it.",
    "I shared the file with the group.",
    "I uploaded the PDF at midnight.",
    "I sold the questions to a student.",
    "I did it for the money.",
    "It was all me.",
    "It was me that leaked it.",
    "I’ve leaked worse.",
    "I am the thief you want.",
    "I'm responsible for the leak.",
]

NOT_CONFESSIONS = [
    "I printed my notes in the library.",
    "I sent it to print. When I went to collect it, my card was gone.",
    "I sent v3 to the Teaching Assistant for proofreading.",
    "Then I took the train to Lisbon.",
    "I'm guilty of nothing.",
    "I am not guilty.",
    "Am I guilty? Of course not.",
    "You think I stole the exam? Please.",
    "I never shared the file with anyone.",
    "I did not leak it.",
    "Whoever stole the exam, it was not me.",
    "I shared a table with the Professor at dinner.",
    "It was me who reported it to the Dean.",
    "I did it at six, the printing, like every week.",
]


@pytest.mark.parametrize("text", CONFESSIONS)
def test_these_confessions_are_caught(text):
    assert ai.confesses(text), text


@pytest.mark.parametrize("text", NOT_CONFESSIONS)
def test_innocent_answers_and_denials_are_not(text):
    assert not ai.confesses(text), text


@pytest.mark.parametrize("text", ["I'm guilty.", "I stole the exam.", "I was the one who leaked it."])
def test_a_caught_confession_falls_back_to_the_scripted_answer(text):
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    answer = ai.ask(engine, game, "companion", "Where were you last night?", complete=reply(text))
    assert answer["reply"] != text
    assert game.history[-1]["fallback"] == "off_script"


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def test_no_suspect_line_in_the_case_files_trips_the_check():
    case = json.loads((ROOT / "data" / "case.json").read_text(encoding="utf-8"))
    texts = list(strings(case["suspects"]))
    for variant in case["variants"].values():
        texts += list(strings(variant.get("suspects", {})))
    texts += list(strings(json.loads((ROOT / "data" / "cracks.json").read_text(encoding="utf-8"))))
    texts += list(ai.DODGES.values())
    assert len(texts) > 50
    for text in texts:
        assert not ai.confesses(text), text
