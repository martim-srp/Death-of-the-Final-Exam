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
    """Show five plain cards: nerves 85, one card short of cracking. Returns the next card."""
    cards = cards_without_lies(engine, game, suspect)
    for clue in cards[:5]:
        assert "cracked" not in engine.present(game, suspect, clue)
    assert engine.nerves(game, suspect) == 85
    return cards[5]


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
    assert engine.nerves(game, "exchange") == 25


def test_a_caught_lie_adds_more_than_a_card():
    engine = Engine()
    game = all_open("A")
    engine.present(game, "companion", "L4")  # breaks never_went_to_office_door
    assert engine.nerves(game, "companion") == 10 + 15 + 35


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
def test_the_culprit_cracks_and_lets_their_motive_slip(variant):
    engine = Engine()
    game = all_open(variant)
    who = culprit(variant)
    last = push_to_the_edge(engine, game, who)
    result = engine.present(game, who, last)
    why = CASE["variants"][variant]["solution"]["why"]
    assert result["cracked"] == {"suspect": who, "line": CRACKS["guilty"][why], "cleared": False}
    assert engine.nerves(game, who) == 100
    assert game.cracked == [who]
    assert game.history[-1]["cracked"] is True
    assert not any(e["option"] == who for e in engine.eliminated(game))


@pytest.mark.parametrize("variant", VARIANTS)
def test_an_innocent_cracks_is_ruled_out_and_says_where(variant):
    engine = Engine()
    where = CASE["variants"][variant]["solution"]["where"]
    for suspect in SUSPECTS:
        if suspect == culprit(variant):
            continue
        game = all_open(variant)
        last = push_to_the_edge(engine, game, suspect)
        result = engine.present(game, suspect, last)
        assert result["cracked"] == {"suspect": suspect, "line": CRACKS["innocent"][where], "cleared": True}
        assert {"column": "who", "option": suspect, "by": "crack"} in engine.eliminated(game)


@pytest.mark.parametrize("variant", VARIANTS)
def test_cracking_never_rules_out_the_answer(variant):
    engine = Engine()
    game = all_open(variant)
    for suspect in SUSPECTS:
        for clue in cards_without_lies(engine, game, suspect)[:6]:
            engine.present(game, suspect, clue)
    assert sorted(game.cracked) == sorted(SUSPECTS)
    solution = CASE["variants"][variant]["solution"]
    out = engine.eliminated(game)
    assert all(e["option"] != solution[e["column"]] for e in out)
    assert sorted(e["option"] for e in out if e["by"] == "crack") == sorted(s for s in SUSPECTS if s != solution["who"])


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
    # Class Representative, variant A: L1 and D6 each break a claim (10 + 2 x (15 + 35) = 110).
    engine.present(game, "class_rep", "L1")
    result = engine.present(game, "class_rep", "D6")
    assert result["contradictions"]
    assert result["cracked"]["cleared"] is False


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


def test_every_motive_and_place_has_a_line():
    assert set(CRACKS["guilty"]) == {o["id"] for o in CASE["accusation"]["why"]}
    assert set(CRACKS["innocent"]) == {o["id"] for o in CASE["accusation"]["where"]}


def test_no_crack_line_names_a_suspect():
    for line in list(CRACKS["guilty"].values()) + list(CRACKS["innocent"].values()):
        assert not any(name in line for name in NAMES), line


def test_no_crack_line_says_how_it_was_done():
    words = ("card", "laptop", "photograph", "bought", "copied", "{")
    for line in list(CRACKS["guilty"].values()) + list(CRACKS["innocent"].values()):
        assert not any(word in line.lower() for word in words), line


@pytest.mark.parametrize("variant", VARIANTS)
def test_the_ai_never_sees_the_crack_line(variant):
    engine = Engine()
    game = all_open(variant)
    who = culprit(variant)
    for clue in cards_without_lies(engine, game, who)[:6]:
        result = engine.present(game, who, clue)
    line = result["cracked"]["line"]
    assert line not in json.dumps(engine.character_brief(game, who), ensure_ascii=False)


def test_a_change_to_the_crack_lines_rebuilds_the_engine():
    assert "data/cracks.json" in reloading.SOURCES


# ---- In the app ------------------------------------------------------------------------


def test_the_app_shows_the_crack_and_rules_the_innocent_out():
    engine = Engine()
    game = all_open("A")
    last = push_to_the_edge(engine, game, "exchange")
    at = start(game=game, focus=("suspect", "exchange"), suspect="exchange")
    assert "width:85%" in page(at)
    assert "Cracked" not in page(at)
    at.pills(key="show_clue").set_value(last).run()
    assert not at.exception
    text = page(at)
    assert "width:100%" in text
    assert "Cracked" in text and "They are off your list." in text
    assert "I did not touch that paper" in text
    assert at.session_state["game"]["cracked"] == ["exchange"]
    assert "RULED OUT" in suspect_markup(at)


def test_the_app_shows_the_culprit_cracking_without_ruling_them_out():
    engine = Engine()
    game = all_open("A")
    last = push_to_the_edge(engine, game, "class_rep")
    at = start(game=game, focus=("suspect", "class_rep"), suspect="class_rep")
    at.pills(key="show_clue").set_value(last).run()
    assert not at.exception
    text = page(at)
    assert "That was not meant to come out." in text
    assert "Nobody should sit that exam" in text
    assert "RULED OUT" not in suspect_markup(at)
