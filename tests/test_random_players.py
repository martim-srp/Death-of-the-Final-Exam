"""Simulated players: thousands of random actions, right and wrong, against the rules.

Each simulated player picks actions at random, including actions the rules must reject: unknown
clues, suspects and topics, locked clues, cards not yet found, bad accusation options, actions after
the case is closed and hints for clues that are not locked. After every action the tests check that:

- only GameError is ever raised, and a rejected action changes nothing in the game;
- the clock only moves forward and never passes 09:00;
- the case closes only by a right accusation (solved) or by the last strike (cold), and stays closed;
- locked clue content can never be read, and the AI brief never holds locked clue text;
- the game saves and loads back unchanged.

The seeds are fixed, so a failure is the same on every run.
"""

import copy
import json
import random

import pytest

from game.engine import COLUMNS, Engine, Game, GameError

ENGINE = Engine()
CASE = ENGINE.case
CLUES = list(CASE["clues"])
SUSPECTS = list(CASE["suspects"])
TOPICS = list(CASE["topics"])
OPTIONS = {column: [option["id"] for option in CASE["accusation"][column]] for column in COLUMNS}
LIMIT = ENGINE.clock_rules["limit_minutes"]
GAMES_PER_VARIANT = 40
ACTIONS_PER_GAME = 120


def random_action(rng, game):
    """One action, as (name, function). About one in four is invalid on purpose."""
    clue = rng.choice(CLUES + ["X9", ""])
    suspect = rng.choice(SUSPECTS + ["dean", ""])
    topic = rng.choice(TOPICS + ["the_weather"])
    opened = game.opened or CLUES
    choices = [
        ("open", lambda: ENGINE.open_clue(game, clue)),
        ("read", lambda: ENGINE.read_clue(game, clue)),
        ("ask", lambda: ENGINE.ask(game, suspect, topic)),
        ("present", lambda: ENGINE.present(game, suspect, rng.choice(opened))),
        ("present_any", lambda: ENGINE.present(game, suspect, clue)),
        ("hint", lambda: ENGINE.hint(game, clue)),
        ("secret", lambda: ENGINE.check_secret(game, suspect, rng.choice(["hunter2!Xy", "where were you?"]))),
    ]
    if rng.random() < 0.08:
        choice = {column: rng.choice(OPTIONS[column]) for column in COLUMNS}
        if rng.random() < 0.2:
            choice[rng.choice(COLUMNS)] = "nobody"
        choices.append(("accuse", lambda: ENGINE.accuse(game, **choice)))
    return rng.choice(choices)


def locked_texts(game):
    """The text of every clue still locked, long enough to be recognised."""
    texts = []
    for clue in ENGINE.clue_list(game):
        if clue["state"] == "locked":
            body = ENGINE._clues(game)[clue["id"]]
            for key in ("text", "log", "hidden_text"):
                value = ENGINE._fill(game, body.get(key))
                if value and len(value) > 40:
                    texts.append(value)
    return texts


def check_invariants(game, before):
    assert 0 <= game.clock <= LIMIT
    assert game.clock >= before.clock
    assert game.status in ("playing", "solved", "cold")
    assert 0 <= game.strikes <= CASE["max_strikes"]
    if before.status != "playing":
        assert game.status == before.status
    if game.status == "cold":
        assert game.strikes == CASE["max_strikes"]
    if game.status == "playing":
        with pytest.raises(GameError):
            ENGINE.solution(game)
    for clue in ENGINE.clue_list(game):
        if clue["state"] != "open":
            with pytest.raises(GameError):
                ENGINE.read_clue(game, clue["id"])
    assert Game.from_dict(json.loads(json.dumps(game.to_dict()))) == game


def play(variant, seed):
    rng = random.Random(f"{variant}-{seed}")
    game = ENGINE.new_game(seed=seed, variant=variant)
    rejected = 0
    for _ in range(ACTIONS_PER_GAME):
        before = copy.deepcopy(game)
        _, action = random_action(rng, game)
        try:
            action()
        except GameError as error:
            rejected += 1
            assert str(error), "a rejection must say why"
            assert game == before, "a rejected action changed the game"
        check_invariants(game, before)
    return game, rejected


@pytest.mark.parametrize("variant", ["A", "B", "C"])
def test_random_players_never_break_the_rules(variant):
    results = [play(variant, seed) for seed in range(GAMES_PER_VARIANT)]
    statuses = {game.status for game, _ in results}
    # The simulation really reaches the edge cases: rejections, cold cases and running out of time.
    assert sum(rejected for _, rejected in results) > GAMES_PER_VARIANT * 10
    assert "cold" in statuses
    assert any(ENGINE.time_left(game) < ENGINE.clock_rules["clue_cost"] for game, _ in results)


@pytest.mark.parametrize("variant", ["A", "B", "C"])
def test_the_ai_brief_never_holds_locked_clue_text_during_random_play(variant):
    for seed in range(10):
        rng = random.Random(f"brief-{variant}-{seed}")
        game = ENGINE.new_game(seed=seed, variant=variant)
        for _ in range(60):
            try:
                random_action(rng, game)[1]()
            except GameError:
                pass
            hidden = locked_texts(game)
            for suspect in SUSPECTS:
                brief = json.dumps(ENGINE.character_brief(game, suspect), ensure_ascii=False)
                assert not any(text in brief for text in hidden)


def test_actions_after_the_case_is_closed_are_all_rejected():
    for variant in "ABC":
        game = ENGINE.new_game(seed=1, variant=variant)
        ENGINE.accuse(game, **ENGINE._resolved[variant]["solution"])
        assert game.status == "solved"
        before = copy.deepcopy(game)
        rng = random.Random(variant)
        for _ in range(50):
            name, action = random_action(rng, game)
            if name in ("read", "secret"):
                continue  # reading an opened card and the password check stay allowed
            with pytest.raises(GameError):
                action()
        assert game == before
