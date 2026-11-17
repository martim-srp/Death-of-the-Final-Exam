"""Checks the closing scene (denouement) of each variant and the suspects' lines against the clues.

These run against data/case.json, like tests/test_case_data.py.
"""

import pytest

from game.case import load_case, resolve_variant
from game.engine import Engine

CASE = load_case()
VARIANTS = sorted(CASE["variants"])


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_variant_has_a_non_empty_denouement(variant):
    text = CASE["variants"][variant].get("denouement")
    assert isinstance(text, str) and text.strip()
    paragraphs = text.split("\n\n")
    assert len(paragraphs) > 1, "paragraphs are separated by blank lines"
    assert all(p.strip() for p in paragraphs), "no empty paragraphs"


@pytest.mark.parametrize("variant", VARIANTS)
def test_denouement_placeholders_are_filled_for_100_seeds(variant):
    engine = Engine()
    text = CASE["variants"][variant]["denouement"]
    for seed in range(100):
        game = engine.new_game(seed=seed, variant=variant)
        filled = engine._fill(game, text)  # raises KeyError on an unknown placeholder
        assert "{" not in filled and "}" not in filled


@pytest.mark.parametrize("variant", VARIANTS)
def test_denouement_names_the_culprit(variant):
    culprit = CASE["variants"][variant]["solution"]["who"]
    name = CASE["suspects"][culprit]["name"]
    assert name.lower() in CASE["variants"][variant]["denouement"].lower()


@pytest.mark.parametrize("variant", VARIANTS)
def test_class_rep_does_not_admit_picking_up_a_card_nobody_dropped(variant):
    """If the Cashier says nothing was dropped, the Class Representative cannot
    answer the cafeteria clue by saying they meant to hand it in."""
    resolved = resolve_variant(CASE, variant)
    cashier = resolved["clues"]["L2"]["text"]
    reveal = resolved["suspects"]["class_rep"]["reveals"].get("L2", "")
    if "Nobody dropped anything" in cashier:
        assert "hand it in" not in reveal
