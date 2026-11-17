"""The suspects' claims (PR #18) match what they actually say, and the two story gaps are filled:
B, the Teaching Assistant's lost card, broken by L2; C, the Companion's laptop, broken by D1."""

import copy

import pytest

from game.case import load_case, resolve_variant
from game.engine import Engine

CASE = load_case()
VARIANTS = sorted(CASE["variants"])


def normalise(text):
    return text.lower().replace('"', "").rstrip(".").strip()


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_claim_is_something_the_suspect_says(variant):
    """A suspect can only be caught on a line from their cover story or one of their reveals."""
    for suspect, s in resolve_variant(CASE, variant)["suspects"].items():
        spoken = normalise(" ".join([s["cover"], *s.get("reveals", {}).values()]))
        for claim in s.get("claims", []):
            assert normalise(claim["text"]) in spoken, (variant, suspect, claim["id"])


def test_b_the_card_claim_is_said_before_it_can_be_broken():
    """L2 only unlocks when D2 is shown to the TA, and that is when the TA says the card went missing."""
    resolved = resolve_variant(CASE, "B")
    claim = next(c for c in resolved["suspects"]["ta"]["claims"] if c["id"] == "card_lost_at_lunch")
    assert claim["broken_by"] == ["L2"]
    assert CASE["clues"]["L2"]["unlock"] == {"present": {"suspect": "ta", "clue": "D2"}}
    assert "went missing at lunch" in resolved["suspects"]["ta"]["reveals"]["D2"]
    assert "Nobody dropped anything" in resolved["clues"]["L2"]["text"]


def test_c_the_laptop_claim_is_broken_by_the_ipad_export():
    resolved = resolve_variant(CASE, "C")
    claim = next(c for c in resolved["suspects"]["companion"]["claims"] if c["id"] == "never_touched_laptop")
    assert claim["broken_by"] == ["D1"]
    assert "iPad ({alias_initials})" in resolved["clues"]["D1"]["text"]
    assert "22:14" in resolved["clues"]["D1"]["text"]


@pytest.mark.parametrize("variant", ["A", "B"])
def test_the_laptop_line_only_exists_where_it_is_a_lie(variant):
    companion = resolve_variant(CASE, variant)["suspects"]["companion"]
    assert "laptop" not in companion["cover"]
    assert all(c["id"] != "never_touched_laptop" for c in companion["claims"])


def play(variant, steps):
    case = copy.deepcopy(CASE)
    case["clock"]["limit_minutes"] = 100_000
    engine = Engine(case)
    game = engine.new_game(seed=5, variant=variant)
    caught = []
    for step in steps:
        if step[0] == "open":
            engine.open_clue(game, step[1])
        else:
            caught += engine.present(game, step[1], step[2]).get("contradictions", [])
    return [c["claim"] for c in caught]


def test_b_showing_l2_to_the_ta_catches_the_lost_card_lie():
    caught = play("B", [("open", "D1"), ("open", "D2"), ("present", "ta", "D2"), ("open", "L2"), ("present", "ta", "L2")])
    assert "card_lost_at_lunch" in caught


def test_a_showing_l2_to_the_ta_catches_nothing_because_the_card_really_was_lost():
    caught = play("A", [("open", "D1"), ("open", "D2"), ("present", "ta", "D2"), ("open", "L2"), ("present", "ta", "L2")])
    assert "card_lost_at_lunch" not in caught


def test_c_showing_d1_to_the_companion_catches_the_laptop_lie():
    assert play("C", [("open", "D1"), ("present", "companion", "D1")]) == ["never_touched_laptop"]
