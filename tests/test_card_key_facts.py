"""Every open evidence card starts with one plain line: the fact that matters.

Playtesters read a paragraph of times and numbers and did not know what it was for. The
"In short" line states what the card shows, never what it means, and fits each variant.
"""

import json
from pathlib import Path

import pytest

from game.case import load_case
from game.engine import Engine
from tests.test_board_game import page, start

CASE = load_case()
FACTS = json.loads((Path(__file__).resolve().parent.parent / "data" / "keyfacts.json").read_text(encoding="utf-8"))


def test_every_card_has_a_short_fact():
    assert set(FACTS["base"]) == set(CASE["clues"])
    for variant in CASE["variants"]:
        assert set(FACTS.get(variant, {})) <= set(CASE["clues"]), variant
    for facts in (FACTS["base"], FACTS["B"], FACTS["C"]):
        for clue_id, fact in facts.items():
            assert 20 < len(fact) <= 120, clue_id
            assert "{" not in fact, clue_id


@pytest.mark.parametrize("variant", ["A", "B", "C"])
def test_the_fact_names_no_culprit_and_matches_the_variant(variant):
    engine = Engine()
    game = engine.new_game(seed=1, variant=variant)
    game.opened.extend(CASE["clues"])
    for clue_id in CASE["clues"]:
        fact = engine.key_fact(game, clue_id)
        assert fact, clue_id
        assert "guilty" not in fact.lower() and "leaked it" not in fact.lower(), clue_id
    times = {"A": "19:20", "B": "17:55", "C": "22:14"}
    assert times[variant] in engine.key_fact(game, "D1")
    assert times[variant] in engine.read_clue(game, "D1")["text"]


def test_no_fact_on_a_closed_card_or_in_hard_mode():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    assert engine.key_fact(game, "D1") is None
    engine.set_mode(game, "hard")
    engine.open_clue(game, "D1")
    assert engine.key_fact(game, "D1") is None


def test_an_open_card_shows_its_fact_first():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "L4")
    text = page(start(game=game, focus=("clue", "L4"))).replace('<strong class="kw">', "").replace("</strong>", "")  # key words are bold
    assert '<div class="keyfact"><small>In short</small>At 19:40 a well-dressed woman' in text
    assert text.index('class="keyfact"') < text.index('class="evidence"')


def test_leads_and_lies_name_cards_by_number_not_by_id():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "L4")
    engine.present(game, "companion", "L4")
    text = page(start(game=game, focus=("lies", None)))  # caught lies are listed on the lightning's panel
    assert "broken by <b>evidence 12</b>" in text
    assert "<b>L4</b>" not in text and "<b>L2</b>" not in text
