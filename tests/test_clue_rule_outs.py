"""The "rules_out" list on each clue: what finding that clue crosses off the case sheet by itself.

Every option a clue rules out must follow from that clue (and the clues it needs to unlock),
must never be the answer, and must never settle a column on its own.
"""

import pytest

from game.case import load_case, option_ids, resolve_variant
from game.engine import COLUMNS, Engine

CASE = load_case()
VARIANTS = sorted(CASE["variants"])


def rules(variant):
    """{clue id: rules_out} for every clue that has one in this variant."""
    clues = resolve_variant(CASE, variant)["clues"]
    return {clue_id: clue["rules_out"] for clue_id, clue in clues.items() if clue.get("rules_out")}


def by(entries, clue_id):
    """The (column, option) pairs one clue crossed off."""
    return {(e["column"], e["option"]) for e in entries if e["by"] == clue_id}


def open_path(variant, *clue_ids):
    engine = Engine()
    game = engine.new_game(seed=1, variant=variant)
    for clue_id in clue_ids:
        engine.open_clue(game, clue_id)
    return engine, game


# ---- The data ----------------------------------------------------------------------------


def test_every_variant_has_clues_that_rule_something_out():
    for variant in VARIANTS:
        assert rules(variant), variant


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_rule_out_names_a_real_column_and_option(variant):
    for clue_id, rule in rules(variant).items():
        for column, options in rule.items():
            assert column in COLUMNS, (variant, clue_id, column)
            assert isinstance(options, list), (variant, clue_id, column)
            for option in options:
                assert option in option_ids(CASE, column), (variant, clue_id, option)


@pytest.mark.parametrize("variant", VARIANTS)
def test_no_clue_rules_out_the_answer(variant):
    answer = CASE["variants"][variant]["solution"]
    for clue_id, rule in rules(variant).items():
        for column, options in rule.items():
            assert answer[column] not in options, (variant, clue_id, column)


@pytest.mark.parametrize("variant", VARIANTS)
def test_no_single_clue_settles_a_column(variant):
    for clue_id, rule in rules(variant).items():
        for column, options in rule.items():
            left = len(option_ids(CASE, column)) - len(set(options))
            assert left >= 2, (variant, clue_id, column, left)


@pytest.mark.parametrize("variant", VARIANTS)
def test_even_all_the_evidence_together_leaves_the_player_a_choice(variant):
    # eliminated() only reads the history, so open every clue at once without walking the unlocks.
    engine = Engine()
    game = engine.new_game(seed=1, variant=variant)
    game.history.extend({"action": "open", "clue": clue_id, "clock": 0} for clue_id in CASE["clues"])
    out = engine.eliminated(game)
    for column in COLUMNS:
        crossed = {e["option"] for e in out if e["column"] == column}
        assert len(option_ids(CASE, column)) - len(crossed) >= 2, (variant, column)
        assert CASE["variants"][variant]["solution"][column] not in crossed
    assert len({e["option"] for e in out if e["column"] == "who"}) <= 1  # suspects stay the player's work


# ---- In play -----------------------------------------------------------------------------


@pytest.mark.parametrize("variant", VARIANTS)
def test_nothing_is_crossed_off_before_a_clue_is_opened(variant):
    engine = Engine()
    assert engine.eliminated(engine.new_game(seed=1, variant=variant)) == []


def test_in_variant_a_the_gate_log_crosses_off_the_companion_and_the_own_card():
    engine, game = open_path("A", "D1", "D2", "L1")
    out = engine.eliminated(game)
    assert by(out, "D1") == {("how", "copied_laptop_dinner")}
    assert by(out, "D2") == {("how", "photographed_desk"), ("where", "professor_office"), ("where", "chiado_restaurant")}
    assert by(out, "L1") == {("who", "companion"), ("how", "own_card_print")}


@pytest.mark.parametrize("variant", ["B", "C"])
def test_the_gate_log_crosses_off_nothing_outside_variant_a(variant):
    engine, game = open_path(variant, "D1", "D2", "L1")
    assert by(engine.eliminated(game), "L1") == set()


def test_in_variant_c_the_unprinted_pdf_crosses_off_the_printer():
    engine, game = open_path("C", "D1")
    assert by(engine.eliminated(game), "D1") == {
        ("how", "borrowed_card_print"), ("how", "own_card_print"), ("how", "photographed_desk"),
        ("where", "library_print_station"),
    }


def test_an_option_is_credited_to_the_first_clue_that_ruled_it_out():
    engine, game = open_path("C", "D1", "D2")
    out = engine.eliminated(game)
    assert by(out, "D2") == set()  # D2 only repeats what D1 already proved
    assert len(out) == len({(e["column"], e["option"]) for e in out})


def test_the_corridor_crosses_off_the_professors_office_in_every_variant():
    for variant in VARIANTS:
        engine, game = open_path(variant, "L4")
        assert by(engine.eliminated(game), "L4") == {("how", "photographed_desk"), ("where", "professor_office")}
