"""A caught lie says what it means: what is now known, and the question it opens.

Playtesters saw CAUGHT LYING and did not know what to do with it. Each claim now has one
line under the stamp and in the lies list. It never says who is guilty.
"""

import json
from pathlib import Path

import pytest

from game.case import load_case, resolve_variant
from game.engine import Engine
from tests.test_board_game import page, start

CASE = load_case()
LIES = json.loads((Path(__file__).resolve().parent.parent / "data" / "lies.json").read_text(encoding="utf-8"))


def claims(variant):
    resolved = resolve_variant(CASE, variant)
    return {claim["id"] for s in resolved["suspects"].values() for claim in s.get("claims", [])}


def test_every_claim_in_every_variant_has_a_meaning():
    every = set().union(*(claims(v) for v in CASE["variants"]))
    assert every == {k for k in LIES if not k.startswith("_")}


def test_a_meaning_asks_a_question_and_names_no_culprit():
    for claim_id, line in LIES.items():
        if claim_id.startswith("_"):
            continue
        assert line.endswith("?"), claim_id
        assert len(line) <= 120, claim_id
        assert "guilty" not in line.lower() and "culprit" not in line.lower(), claim_id


@pytest.mark.parametrize("variant", ["A", "B", "C"])
def test_the_chat_explains_the_caught_lie(variant):
    engine = Engine()
    game = engine.new_game(seed=1, variant=variant)
    engine.open_clue(game, "L4")
    at = start(game=game, focus=("suspect", "companion"), suspect="companion")
    at.pills(key="show_clue").set_value("L4").run()
    assert not at.exception
    text = page(at)
    assert "<b>What it means:</b> The Companion was at the Professor&#x27;s office door at 19:40." in text


def test_the_lies_list_explains_each_lie():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "L4")
    engine.present(game, "companion", "L4")
    text = page(start(game=game, focus=("lies", None)))
    assert "<b>What it means:</b>" in text


def test_no_meaning_in_hard_mode():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.set_mode(game, "hard")
    assert engine.lie_meaning(game, "never_went_to_office_door") is None
    engine.open_clue(game, "L4")
    engine.present(game, "companion", "L4")
    assert "What it means" not in page(start(game=game, focus=("lies", None)))
