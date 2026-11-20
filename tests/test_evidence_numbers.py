"""Evidence is numbered 1 to 13 for the player, every card is in the evidence grid, and clues read as short points."""

import re

import board
from game.case import load_case, resolve_variant
from game.engine import Engine

CASE = load_case()


def test_evidence_is_numbered_1_to_13_in_case_file_order():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    numbers = [item["number"] for item in engine.clue_list(game)]
    assert numbers == list(range(1, len(CASE["clues"]) + 1))
    assert engine.label("L4") == "Evidence 12. The faculty corridor"


def test_the_evidence_grid_shows_every_card_with_a_number_and_no_letter_codes():
    engine = Engine()
    hand = board.hand_html(engine.clue_list(engine.new_game(seed=1, variant="A")))
    assert hand.count('data-act="clue:') == len(CASE["clues"])
    labels = re.findall(r'<div class="lbl"><b>([^<]*)</b>', hand)
    assert labels == [str(n) for n in range(1, len(CASE["clues"]) + 1)]
    assert not re.search(r'title="[DL]\d', hand)


def test_every_clue_reads_as_short_points_in_every_variant():
    for variant in CASE["variants"]:
        for clue_id, clue in resolve_variant(CASE, variant)["clues"].items():
            lines = clue["text"].splitlines()
            assert lines and all(line.startswith("- ") for line in lines), (variant, clue_id)
            assert all(len(line) <= 220 for line in lines), (variant, clue_id)


def test_no_clue_keeps_the_old_exam_name_or_the_payoff_chart():
    for variant in CASE["variants"]:
        for clue in resolve_variant(CASE, variant)["clues"].values():
            assert "Semiconductor" not in clue["text"]
            assert "chart" not in clue
    assert "charts" not in CASE


def test_every_question_that_opens_a_clue_says_why_it_is_worth_asking():
    for clue_id, clue in CASE["clues"].items():
        rule = clue["unlock"].get("topic")
        if rule:
            assert "Ask" in rule.get("why", ""), clue_id
