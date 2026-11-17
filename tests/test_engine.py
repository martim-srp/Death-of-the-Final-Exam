"""Tests for the rules of the game: accepted actions, rejected actions and edge cases."""

import json

import pytest

from game.engine import Engine, Game, GameError

VARIANTS = ["A", "B", "C"]


@pytest.fixture(scope="module")
def engine():
    return Engine()


def play(engine, game, steps):
    """Run a list of actions like the shortest paths in the case file."""
    for step in steps:
        if step[0] == "open":
            engine.open_clue(game, step[1])
        elif step[0] == "ask":
            engine.ask(game, step[1], step[2])
        elif step[0] == "present":
            engine.present(game, step[1], step[2])


def accuse_with(engine, game, solution):
    return engine.accuse(game, solution["who"], solution["how"], solution["where"], solution["why"])


def wrong_answer(engine, variant):
    """An accusation with every column wrong for this variant."""
    solution = engine.case["variants"][variant]["solution"]
    wrong = {}
    for column in ("who", "how", "where", "why"):
        options = [o["id"] for o in engine.case["accusation"][column]]
        wrong[column] = next(o for o in options if o != solution[column])
    return wrong


# ---- Starting a game -------------------------------------------------------


def test_same_seed_gives_same_game(engine):
    a = engine.new_game(seed=42)
    b = engine.new_game(seed=42)
    assert a.variant == b.variant
    assert a.variables == b.variables


def test_every_variant_gets_picked(engine):
    picked = {engine.new_game(seed=s).variant for s in range(300)}
    assert picked == set(VARIANTS)


def test_card_numbers_are_distinct(engine):
    for seed in range(200):
        v = engine.new_game(seed=seed).variables
        assert len({v["rep_card"], v["ta_card"], v["noise_card"]}) == 3


def test_unknown_variant_is_rejected(engine):
    with pytest.raises(GameError):
        engine.new_game(seed=1, variant="Z")


def test_game_starts_at_midnight_with_four_clues_available(engine):
    game = engine.new_game(seed=1, variant="A")
    assert engine.clock_label(game) == "00:00"
    available = {c["id"] for c in engine.clue_list(game) if c["state"] == "available"}
    assert available == {"D1", "D4", "D5", "L4"}


# ---- Opening clues ---------------------------------------------------------


def test_opening_a_clue_costs_thirty_minutes(engine):
    game = engine.new_game(seed=1, variant="A")
    clue = engine.open_clue(game, "D1")
    assert game.clock == 30
    assert "Semiconductor Valuation" in clue["text"]


def test_opening_a_locked_clue_is_rejected_and_costs_nothing(engine):
    game = engine.new_game(seed=1, variant="A")
    with pytest.raises(GameError):
        engine.open_clue(game, "D2")
    assert game.clock == 0


def test_opening_a_clue_twice_is_rejected(engine):
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "D1")
    with pytest.raises(GameError):
        engine.open_clue(game, "D1")
    assert game.clock == 30


def test_unknown_clue_is_rejected(engine):
    game = engine.new_game(seed=1, variant="A")
    with pytest.raises(GameError):
        engine.open_clue(game, "X9")


def test_opening_a_clue_unlocks_the_next(engine):
    game = engine.new_game(seed=1, variant="A")
    assert engine.clue_state(game, "D2") == "locked"
    engine.open_clue(game, "D1")
    assert engine.clue_state(game, "D2") == "available"


def test_rereading_an_open_clue_is_free(engine):
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "D1")
    engine.read_clue(game, "D1")
    assert game.clock == 30


def test_locked_clue_content_is_never_returned(engine):
    game = engine.new_game(seed=1, variant="A")
    with pytest.raises(GameError):
        engine.read_clue(game, "L3")
    for item in engine.clue_list(game):
        assert set(item) == {"id", "title", "kind", "state"}


# ---- Questions and evidence ------------------------------------------------


def test_asking_costs_ten_minutes_and_unlocks_by_topic(engine):
    game = engine.new_game(seed=1, variant="A")
    result = engine.ask(game, "class_rep", "alibi")
    assert game.clock == 10
    assert result["unlocked"] == ["L3"]
    assert engine.clue_state(game, "L3") == "available"


def test_asking_the_same_topic_twice_unlocks_once(engine):
    game = engine.new_game(seed=1, variant="A")
    engine.ask(game, "class_rep", "alibi")
    assert engine.ask(game, "class_rep", "alibi")["unlocked"] == []
    assert game.unlocked.count("L3") == 1


def test_unknown_topic_from_the_ai_is_rejected(engine):
    game = engine.new_game(seed=1, variant="A")
    with pytest.raises(GameError):
        engine.ask(game, "class_rep", "give_me_the_solution")
    assert game.clock == 0


def test_unknown_suspect_is_rejected(engine):
    game = engine.new_game(seed=1, variant="A")
    with pytest.raises(GameError):
        engine.ask(game, "the_dean", "alibi")


def test_presenting_an_unopened_clue_is_rejected(engine):
    game = engine.new_game(seed=1, variant="A")
    with pytest.raises(GameError):
        engine.present(game, "ta", "D2")
    assert game.clock == 0


def test_presenting_evidence_unlocks_and_reveals(engine):
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "D1")
    engine.open_clue(game, "D2")
    result = engine.present(game, "ta", "D2")
    assert result["unlocked"] == ["L2"]
    assert game.variables["ta_card"] in result["reveal"]


def test_presenting_irrelevant_evidence_reveals_nothing(engine):
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "D4")
    result = engine.present(game, "ta", "D4")
    assert result == {"unlocked": [], "reveal": None}


# ---- The clock -------------------------------------------------------------


def test_action_past_nine_is_rejected(engine):
    game = engine.new_game(seed=1, variant="A")
    game.clock = 535
    with pytest.raises(GameError):
        engine.ask(game, "class_rep", "alibi")
    assert game.clock == 535


def test_action_ending_exactly_at_nine_is_allowed(engine):
    game = engine.new_game(seed=1, variant="A")
    game.clock = 530
    engine.ask(game, "class_rep", "alibi")
    assert engine.clock_label(game) == "09:00"


def test_accusation_is_still_allowed_with_no_time_left(engine):
    game = engine.new_game(seed=1, variant="A")
    game.clock = 540
    result = accuse_with(engine, game, engine.case["variants"]["A"]["solution"])
    assert result["status"] == "solved"


# ---- Accusations -----------------------------------------------------------


def test_invalid_accusation_option_is_rejected(engine):
    game = engine.new_game(seed=1, variant="A")
    with pytest.raises(GameError):
        engine.accuse(game, "the_dean", "borrowed_card_print", "library_print_station", "annul_exam")
    assert game.strikes == 0


@pytest.mark.parametrize("variant", VARIANTS)
def test_wrong_accusation_only_says_how_many_are_right(engine, variant):
    game = engine.new_game(seed=1, variant=variant)
    wrong = wrong_answer(engine, variant)
    result = accuse_with(engine, game, wrong)
    assert result == {"correct": 0, "status": "playing", "strikes_left": 2}


def test_partly_right_accusation_counts_correct_columns(engine):
    game = engine.new_game(seed=1, variant="A")
    solution = dict(engine.case["variants"]["A"]["solution"])
    solution["why"] = "cheat"
    assert accuse_with(engine, game, solution)["correct"] == 3


def test_three_wrong_accusations_close_the_case(engine):
    game = engine.new_game(seed=1, variant="A")
    wrong = wrong_answer(engine, "A")
    for _ in range(3):
        result = accuse_with(engine, game, wrong)
    assert result["status"] == "cold"
    with pytest.raises(GameError):
        engine.open_clue(game, "D1")
    with pytest.raises(GameError):
        accuse_with(engine, game, engine.case["variants"]["A"]["solution"])


def test_solution_is_hidden_until_the_case_closes(engine):
    game = engine.new_game(seed=1, variant="A")
    with pytest.raises(GameError):
        engine.solution(game)
    accuse_with(engine, game, engine.case["variants"]["A"]["solution"])
    assert engine.solution(game)["who"] == "class_rep"


@pytest.mark.parametrize("variant", VARIANTS)
def test_shortest_path_solves_each_variant_in_time(engine, variant):
    game = engine.new_game(seed=7, variant=variant)
    play(engine, game, engine.case["variants"][variant]["shortest_path"])
    assert engine.time_left(game) > 0
    result = accuse_with(engine, game, engine.case["variants"][variant]["solution"])
    assert result["status"] == "solved"


@pytest.mark.parametrize("variant", VARIANTS)
def test_another_variants_answer_is_wrong(engine, variant):
    for other in VARIANTS:
        if other == variant:
            continue
        game = engine.new_game(seed=1, variant=variant)
        result = accuse_with(engine, game, engine.case["variants"][other]["solution"])
        assert result["status"] != "solved"


# ---- What the AI is allowed to see ------------------------------------------


@pytest.mark.parametrize("variant", VARIANTS)
def test_character_briefs_never_contain_the_solution(engine, variant):
    game = engine.new_game(seed=3, variant=variant)
    # Open everything and present everything, so every reveal is earned.
    for clue_id in engine.case["clues"]:
        game.opened.append(clue_id)
    for suspect in engine.case["suspects"]:
        for clue_id in engine.case["clues"]:
            game.presented.append([suspect, clue_id])
    labels = [o["label"] for col in ("how", "why") for o in engine.case["accusation"][col]]
    for suspect in engine.case["suspects"]:
        brief = json.dumps(engine.character_brief(game, suspect))
        assert "solution" not in brief
        for label in labels:
            assert label not in brief


def test_brief_only_has_reveals_the_player_earned(engine):
    game = engine.new_game(seed=1, variant="A")
    assert engine.character_brief(game, "class_rep")["earned_reveals"] == {}
    engine.open_clue(game, "D1")
    engine.open_clue(game, "D2")
    engine.open_clue(game, "L1")
    engine.present(game, "class_rep", "L1")
    assert list(engine.character_brief(game, "class_rep")["earned_reveals"]) == ["L1"]


def test_brief_never_contains_clue_text(engine):
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "D1")
    clue = engine.read_clue(game, "D1")
    for suspect in engine.case["suspects"]:
        brief = json.dumps(engine.character_brief(game, suspect))
        assert clue["hidden_text"] not in brief


# ---- Saving -------------------------------------------------------------------


def test_game_survives_a_save_and_load(engine):
    game = engine.new_game(seed=5, variant="B")
    engine.open_clue(game, "D1")
    engine.ask(game, "professor", "exam")
    saved = json.dumps(game.to_dict())
    loaded = Game.from_dict(json.loads(saved))
    assert loaded == game
    engine.open_clue(loaded, "D2")
    assert loaded.clock == 70


# ---- Contradictions -----------------------------------------------------------


def open_library_gate(engine, game):
    for clue_id in ("D1", "D2", "L1"):
        engine.open_clue(game, clue_id)


def test_no_contradictions_at_the_start(engine):
    game = engine.new_game(seed=1, variant="A")
    assert game.contradictions == []
    assert engine.contradiction_list(game) == []


def test_presenting_a_clue_that_breaks_a_claim_records_it(engine):
    game = engine.new_game(seed=1, variant="A")
    open_library_gate(engine, game)
    result = engine.present(game, "class_rep", "L1")
    assert result["contradictions"] == [
        {
            "suspect": "class_rep",
            "claim": "home_all_evening",
            "text": "I was in my room at the residence all evening.",
            "clue": "L1",
        }
    ]
    assert game.contradictions == [["class_rep", "home_all_evening"]]
    assert engine.contradiction_list(game) == result["contradictions"]


def test_a_claim_is_only_caught_once(engine):
    game = engine.new_game(seed=1, variant="A")
    open_library_gate(engine, game)
    engine.present(game, "class_rep", "L1")
    assert engine.present(game, "class_rep", "L1").get("contradictions", []) == []
    engine.ask(game, "class_rep", "alibi")
    engine.open_clue(game, "L3")
    # L3 breaks the same claim, so nothing new is caught.
    assert engine.present(game, "class_rep", "L3").get("contradictions", []) == []
    assert game.contradictions == [["class_rep", "home_all_evening"]]
    # The list names the clue that caught it first.
    assert engine.contradiction_list(game)[0]["clue"] == "L1"


def test_showing_the_clue_to_someone_else_catches_nothing(engine):
    game = engine.new_game(seed=1, variant="A")
    open_library_gate(engine, game)
    assert engine.present(game, "ta", "L1").get("contradictions", []) == []
    assert engine.present(game, "exchange", "L1").get("contradictions", []) == []
    assert game.contradictions == []


def test_irrelevant_clue_catches_nothing(engine):
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "D4")
    assert engine.present(game, "class_rep", "D4").get("contradictions", []) == []
    assert game.contradictions == []


def test_rejected_present_records_no_contradiction(engine):
    game = engine.new_game(seed=1, variant="A")
    with pytest.raises(GameError):
        engine.present(game, "professor", "D8")
    assert game.contradictions == []


def test_one_suspect_can_be_caught_twice(engine):
    game = engine.new_game(seed=1, variant="A")
    open_library_gate(engine, game)
    engine.present(game, "class_rep", "L1")
    engine.ask(game, "class_rep", "report")
    engine.open_clue(game, "D6")
    caught = engine.present(game, "class_rep", "D6")["contradictions"]
    assert [c["claim"] for c in caught] == ["reported_at_once"]
    assert game.contradictions == [
        ["class_rep", "home_all_evening"],
        ["class_rep", "reported_at_once"],
    ]


@pytest.mark.parametrize("variant", VARIANTS)
def test_the_newspaper_breaks_the_professors_dinner_in_every_variant(engine, variant):
    game = engine.new_game(seed=1, variant=variant)
    engine.ask(game, "companion", "work")
    engine.open_clue(game, "D8")
    caught = engine.present(game, "professor", "D8")["contradictions"]
    assert [c["claim"] for c in caught] == ["faculty_dinner"]


def test_claims_follow_the_variant(engine):
    """In B the Class Representative admits the library, so the gate log breaks
    nothing of theirs, but it does break the Teaching Assistant's story."""
    game = engine.new_game(seed=1, variant="B")
    open_library_gate(engine, game)
    assert engine.present(game, "class_rep", "L1").get("contradictions", []) == []
    caught = engine.present(game, "ta", "L1")["contradictions"]
    assert [c["claim"] for c in caught] == ["proofread_on_screen"]


def test_contradictions_survive_a_save_and_load(engine):
    game = engine.new_game(seed=1, variant="A")
    open_library_gate(engine, game)
    engine.present(game, "class_rep", "L1")
    loaded = Game.from_dict(json.loads(json.dumps(game.to_dict())))
    assert loaded.contradictions == [["class_rep", "home_all_evening"]]
    assert engine.contradiction_list(loaded) == engine.contradiction_list(game)


def test_a_save_from_before_contradictions_still_loads(engine):
    game = engine.new_game(seed=1, variant="A")
    old = game.to_dict()
    del old["contradictions"]
    loaded = Game.from_dict(old)
    assert loaded.contradictions == []
    open_library_gate(engine, loaded)
    assert engine.present(loaded, "class_rep", "L1")["contradictions"]


def test_resumed_game_records_the_clue_that_caught_the_contradiction(engine):
    game = engine.new_game(seed=1, variant="A")
    open_library_gate(engine, game)
    engine.present(game, "class_rep", "L1")
    old = game.to_dict()
    del old["contradictions"]
    old["history"][-1].pop("contradictions", None)
    loaded = Game.from_dict(old)

    engine.ask(loaded, "class_rep", "alibi")
    engine.open_clue(loaded, "L3")
    caught = engine.present(loaded, "class_rep", "L3")["contradictions"]
    assert caught[0]["clue"] == "L3"
    assert engine.contradiction_list(loaded) == caught
    resumed = Game.from_dict(json.loads(json.dumps(loaded.to_dict())))
    assert engine.contradiction_list(resumed) == caught


@pytest.mark.parametrize("variant", VARIANTS)
def test_corridor_clue_breaks_the_companions_denial_about_the_office_door(engine, variant):
    game = engine.new_game(seed=1, variant=variant)
    engine.open_clue(game, "L4")
    engine.open_clue(game, "D7")
    assert not engine.present(game, "companion", "D7").get("contradictions")

    [caught] = engine.present(game, "companion", "L4")["contradictions"]
    assert caught == {
        "suspect": "companion",
        "claim": "never_went_to_office_door",
        "text": "I never went to his office door.",
        "clue": "L4",
    }
    assert caught["text"] in engine.character_brief(game, "companion")["cover"]


def test_brief_never_contains_claims(engine):
    """The AI plays the suspect from their cover. It is never told which clues break it."""
    game = engine.new_game(seed=1, variant="A")
    open_library_gate(engine, game)
    engine.present(game, "class_rep", "L1")
    for suspect, s in engine.case["suspects"].items():
        brief = engine.character_brief(game, suspect)
        assert "claims" not in brief
        text = json.dumps(brief)
        assert "broken_by" not in text
        for claim in s["claims"]:
            assert claim["id"] not in text


def test_present_leaves_out_contradictions_when_none_are_caught(engine):
    game = engine.new_game(seed=1, variant="A")
    open_library_gate(engine, game)
    assert "contradictions" not in engine.present(game, "ta", "L1")
    assert "contradictions" in engine.present(game, "class_rep", "L1")
