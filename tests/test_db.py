"""Tests for saved games."""

import pytest

import db
from game.engine import Engine


@pytest.fixture(scope="module")
def engine():
    return Engine()


def test_a_saved_game_loads_back_identical(engine):
    game = engine.new_game(seed=3, variant="C")
    engine.open_clue(game, "D1")
    game_id = db.create_game(game)
    assert db.load_game(game_id) == game


def test_saving_updates_the_stored_game(engine):
    game = engine.new_game(seed=3, variant="A")
    game_id = db.create_game(game)
    engine.open_clue(game, "D1")
    db.save_game(game_id, game)
    assert db.load_game(game_id).clock == 30


def test_ids_are_unguessable_and_unique(engine):
    game = engine.new_game(seed=1)
    ids = {db.create_game(game) for _ in range(50)}
    assert len(ids) == 50
    assert all(len(i) >= 32 and db.valid_id(i) for i in ids)


def test_unknown_id_returns_nothing():
    assert db.load_game("a" * 32) is None


@pytest.mark.parametrize("bad", ["", "short", "x' OR '1'='1", "../../etc/passwd", None, 42, "a" * 65])
def test_malformed_ids_are_rejected(bad):
    assert db.load_game(bad) is None


def test_saving_with_a_malformed_id_is_rejected(engine):
    with pytest.raises(ValueError):
        db.save_game("x' OR '1'='1", engine.new_game(seed=1))


def test_old_saves_without_badges_still_load(engine):
    """Games saved before badges existed must still load."""
    import json
    import sqlite3

    game = engine.new_game(seed=2, variant="A")
    game_id = db.create_game(game)
    state = game.to_dict()
    del state["badges"]
    conn = sqlite3.connect(db._path())
    with conn:
        conn.execute("UPDATE games SET state = ? WHERE id = ?", (json.dumps(state), game_id))
    assert db.load_game(game_id).badges == []
