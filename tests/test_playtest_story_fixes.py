"""Story details a blind playtest tripped on (21 Nov): proofs that should count, times that
should match the cards, and a detective line that miscounted lies."""

import json
import re
from pathlib import Path

import pytest

from game.case import load_case, resolve_variant
from game.engine import Engine

CASE = load_case()
VOICE = json.loads((Path(__file__).resolve().parent.parent / "data" / "voice.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("variant", ["A", "B"])
def test_the_library_gate_log_proves_the_library_whenever_the_paper_was_printed_there(variant):
    """In both printed variants the gate log puts the culprit's card in the library while the job
    was released, and both endings cite it. Variant A refused it as proof; B accepted it."""
    solution = CASE["variants"][variant]["solution"]
    assert solution["where"] == "library_print_station"
    engine = Engine()
    game = engine.new_game(seed=1, variant=variant)
    game.opened = list(CASE["clues"])
    engine.accuse(game, **solution, proofs={"where": "L1"})
    assert engine.proven(game) == {"where": True}


def test_the_gate_log_still_proves_nothing_about_chiado():
    engine = Engine()
    game = engine.new_game(seed=1, variant="C")
    game.opened = list(CASE["clues"])
    engine.accuse(game, **CASE["variants"]["C"]["solution"], proofs={"where": "L1"})
    assert engine.proven(game) == {"where": False}


def test_every_time_the_ending_gives_for_the_kiosk_matches_the_anonymous_number_card():
    """The card says the SIM was sold at twenty past eight and switched on at 20:21."""
    card = resolve_variant(CASE, "B")["clues"]["D5"]["text"]
    assert "At twenty past, someone young" in card and "activated Thursday 20:21" in card
    ending = CASE["variants"]["B"]["denouement"]
    assert "At 20:20, someone young" in ending and "switched on at 20:21" in ending
    assert not re.search(r"At 20:21, someone young", ending)


def test_the_caught_lines_never_count_the_lies():
    """A line said after every lie caught cannot say 'one lie': it rotates, so it also follows the second."""
    for line in VOICE["replies"]["caught"]:
        assert not re.search(r"\b(one|first|two|second) lie", line, re.I), line
