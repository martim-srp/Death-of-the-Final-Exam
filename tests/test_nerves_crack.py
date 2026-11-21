"""Nerves: at 100 a suspect cracks. The culprit lets their motive slip; an innocent swears
they did not do it (and is ruled out) and says where the paper really left from.

Checked in every variant, so the lines always fit the variant's solution and never give
the whole answer away."""

import json

import pytest

import reloading
from game.case import load_case, load_cracks
from game.engine import Engine, GameError, Game
from tests.test_board_game import page, start, suspect_markup

CASE = load_case()
CRACKS = load_cracks()
VARIANTS = sorted(CASE["variants"])
SUSPECTS = list(CASE["suspects"])
NAMES = {word for s in CASE["suspects"].values() for word in s["name"].replace("The ", "").split()} - {"Student"}


def all_open(variant):
    """A game where every clue is open, so any card can be shown."""
    game = Engine().new_game(seed=7, variant=variant)
    game.opened = list(CASE["clues"])
    return game


def cards_without_lies(engine, game, suspect):
    """Clues that break none of this suspect's claims, so each one shown adds exactly 15."""
    claims = engine._suspects(game)[suspect].get("claims", [])
    breakers = {clue for claim in claims for clue in claim["broken_by"]}
    return [c for c in CASE["clues"] if c not in breakers]


def push_to_the_edge(engine, game, suspect):
    """Show two plain cards: nerves 70, one card short of cracking. Returns the next card."""
    cards = cards_without_lies(engine, game, suspect)
    for clue in cards[:2]:
        assert "cracked" not in engine.present(game, suspect, clue)
    assert engine.nerves(game, suspect) == 70
    return cards[2]


def culprit(variant):
    return CASE["variants"][variant]["solution"]["who"]


# ---- Nerves ----------------------------------------------------------------------------


def test_nerves_start_at_ten_for_everyone():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    assert {engine.nerves(game, s) for s in SUSPECTS} == {10}


def test_showing_the_same_card_twice_adds_nothing():
    engine = Engine()
    game = all_open("A")
    engine.present(game, "exchange", "D3")
    engine.present(game, "exchange", "D3")
    assert engine.nerves(game, "exchange") == 40


def test_a_caught_lie_adds_more_than_a_card():
    engine = Engine()
    game = all_open("A")
    engine.present(game, "companion", "L4")  # breaks never_went_to_office_door
    assert engine.nerves(game, "companion") == 10 + 30 + 20


def test_nerves_for_an_unknown_suspect_are_refused():
    engine = Engine()
    with pytest.raises(GameError):
        engine.nerves(engine.new_game(seed=1, variant="A"), "dean")


# ---- Cracking --------------------------------------------------------------------------


@pytest.mark.parametrize("variant", VARIANTS)
def test_nobody_cracks_below_full_nerves(variant):
    engine = Engine()
    game = all_open(variant)
    for suspect in SUSPECTS:
        push_to_the_edge(engine, game, suspect)
    assert game.cracked == []
    assert not any(e["by"] == "crack" for e in engine.eliminated(game))


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_suspect_cracks_the_same_way_and_says_where(variant):
    # Guilty or not, a suspect who cracks swears they did not do it and says where the
    # paper left from. Same line, nobody ruled out: a crack never shows who is guilty.
    engine = Engine()
    where = CASE["variants"][variant]["solution"]["where"]
    for suspect in SUSPECTS:
        game = all_open(variant)
        last = push_to_the_edge(engine, game, suspect)
        result = engine.present(game, suspect, last)
        assert result["cracked"] == {"suspect": suspect, "line": CRACKS["where"][where]}
        assert engine.nerves(game, suspect) == 100
        assert game.cracked == [suspect]
        assert game.history[-1]["cracked"] is True
        assert engine.eliminated(game) == [e for e in engine.eliminated(game) if e["by"] != "crack"]
        assert not any(e["column"] == "who" for e in engine.eliminated(game) if e["by"] not in CASE["clues"])


@pytest.mark.parametrize("variant", VARIANTS)
def test_the_culprit_and_an_innocent_crack_identically(variant):
    engine = Engine()
    who = culprit(variant)
    innocent = next(s for s in SUSPECTS if s != who)
    lines = []
    for suspect in (who, innocent):
        game = all_open(variant)
        last = push_to_the_edge(engine, game, suspect)
        lines.append({k: v for k, v in engine.present(game, suspect, last)["cracked"].items() if k != "suspect"})
    assert lines[0] == lines[1]


@pytest.mark.parametrize("variant", VARIANTS)
def test_cracking_everyone_rules_nobody_out(variant):
    engine = Engine()
    game = all_open(variant)
    for suspect in SUSPECTS:
        for clue in cards_without_lies(engine, game, suspect)[:6]:
            engine.present(game, suspect, clue)
    assert sorted(game.cracked) == sorted(SUSPECTS)
    assert not any(e["column"] == "who" and e["by"] not in CASE["clues"] for e in engine.eliminated(game))


def test_a_suspect_cracks_only_once():
    engine = Engine()
    game = all_open("A")
    cards = cards_without_lies(engine, game, "exchange")
    for clue in cards[:6]:
        engine.present(game, "exchange", clue)
    assert game.cracked == ["exchange"]
    again = engine.present(game, "exchange", cards[6])
    assert "cracked" not in again
    assert game.cracked == ["exchange"]
    assert sum(1 for e in game.history if e.get("cracked")) == 1


def test_lies_caught_count_toward_cracking():
    engine = Engine()
    game = all_open("A")
    # Class Representative, variant A: L1 and D6 each break a claim (10 + 2 x (30 + 20) = 110).
    engine.present(game, "class_rep", "L1")
    result = engine.present(game, "class_rep", "D6")
    assert result["contradictions"]
    assert result["cracked"]["suspect"] == "class_rep"


def test_questions_alone_never_crack_anyone():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    for _ in range(10):
        engine.ask(game, "class_rep", "alibi")
    assert engine.nerves(game, "class_rep") == 10
    assert game.cracked == []


def test_cracked_suspects_survive_saving_and_old_saves_still_load():
    engine = Engine()
    game = all_open("B")
    for clue in cards_without_lies(engine, game, "exchange")[:6]:
        engine.present(game, "exchange", clue)
    loaded = Game.from_dict(json.loads(json.dumps(game.to_dict())))
    assert loaded.cracked == ["exchange"]
    old = game.to_dict()
    del old["cracked"]
    assert Game.from_dict(old).cracked == []


# ---- The lines -------------------------------------------------------------------------


def test_every_place_has_a_line():
    assert set(CRACKS) == {"where"}  # one kind of line for everyone, so a crack never shows guilt
    assert set(CRACKS["where"]) == {o["id"] for o in CASE["accusation"]["where"]}


def test_no_crack_line_names_a_suspect():
    for line in CRACKS["where"].values():
        assert not any(name in line for name in NAMES), line


def test_no_crack_line_says_how_it_was_done():
    words = ("card", "laptop", "photograph", "bought", "copied", "{")
    for line in CRACKS["where"].values():
        assert not any(word in line.lower() for word in words), line


@pytest.mark.parametrize("variant", VARIANTS)
def test_after_cracking_the_ai_knows_what_they_blurted_out(variant):
    engine = Engine()
    for suspect in SUSPECTS:
        game = all_open(variant)
        assert engine.character_brief(game, suspect)["broke_down"] is None
        for clue in cards_without_lies(engine, game, suspect)[:3]:
            result = engine.present(game, suspect, clue)
        assert engine.character_brief(game, suspect)["broke_down"] == result["cracked"]["line"]
        others = [s for s in SUSPECTS if s != suspect]
        assert all(engine.character_brief(game, s)["broke_down"] is None for s in others)


@pytest.mark.parametrize("variant", VARIANTS)
def test_the_brief_after_cracking_holds_no_more_of_the_solution(variant):
    engine = Engine()
    game = all_open(variant)
    solution = CASE["variants"][variant]["solution"]
    for suspect in SUSPECTS:
        for clue in cards_without_lies(engine, game, suspect)[:6]:
            engine.present(game, suspect, clue)
    for suspect in SUSPECTS:
        brief = json.dumps(engine.character_brief(game, suspect), ensure_ascii=False)
        assert "solution" not in brief
        for column in ("how", "why", "where"):
            for option in CASE["accusation"][column]:
                assert option["label"] not in brief


def test_the_prompt_tells_the_ai_not_to_deny_the_crack():
    from game import ai

    engine = Engine()
    game = all_open("C")
    for clue in cards_without_lies(engine, game, "companion")[:6]:
        engine.present(game, "companion", clue)
    prompt = ai.system_prompt(engine.character_brief(game, "companion"), CASE["topics"])
    assert "Never deny it" in prompt
    character = json.loads(prompt.split("Character brief: ", 1)[1])
    assert character["broke_down"] == CRACKS["where"]["chiado_restaurant"]
    calm = ai.system_prompt(engine.character_brief(game, "professor"), CASE["topics"])
    assert "Never deny it" not in calm


def test_a_resumed_game_keeps_the_crack_in_the_brief():
    engine = Engine()
    game = all_open("B")
    for clue in cards_without_lies(engine, game, "ta")[:6]:
        engine.present(game, "ta", clue)
    resumed = Game.from_dict(json.loads(json.dumps(game.to_dict())))
    assert engine.character_brief(resumed, "ta")["broke_down"] == CRACKS["where"]["library_print_station"]


def test_a_change_to_the_crack_lines_rebuilds_the_engine():
    assert "data/cracks.json" in reloading.SOURCES


# ---- In the app ------------------------------------------------------------------------


def test_the_app_shows_the_crack_and_rules_nobody_out():
    engine = Engine()
    game = all_open("A")
    last = push_to_the_edge(engine, game, "exchange")
    at = start(game=game, focus=("suspect", "exchange"), suspect="exchange")
    assert "width:70%" in page(at)
    assert "Cracked" not in page(at)
    at.pills(key="show_clue").set_value(last).run()
    assert not at.exception
    text = page(at)
    assert "width:100%" in text
    assert "Cracked" in text and "Their story broke." in text
    assert "I did not touch that paper" in text
    assert at.session_state["game"]["cracked"] == ["exchange"]
    assert "RULED OUT" not in suspect_markup(at)


def test_the_app_shows_the_culprit_cracking_like_anyone_else():
    engine = Engine()
    game = all_open("A")
    last = push_to_the_edge(engine, game, "class_rep")
    at = start(game=game, focus=("suspect", "class_rep"), suspect="class_rep")
    at.pills(key="show_clue").set_value(last).run()
    assert not at.exception
    text = page(at)
    assert "Their story broke." in text
    assert "I did not touch that paper" in text  # the culprit swears it too
    assert "RULED OUT" not in suspect_markup(at)
