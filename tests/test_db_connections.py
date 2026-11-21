"""Every database call closes its connection, and a failed write leaves the save untouched."""

import sqlite3

import pytest

import db
from game.engine import Engine


@pytest.fixture
def tracked(monkeypatch):
    opened = []
    real = sqlite3.connect

    def connect(*args, **kwargs):
        conn = real(*args, **kwargs)
        opened.append(conn)
        return conn

    monkeypatch.setattr(db.sqlite3, "connect", connect)
    return opened


def is_closed(conn):
    try:
        conn.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return True
    return False


def test_create_save_and_load_close_their_connections(tracked):
    game = Engine().new_game(seed=1)
    game_id = db.create_game(game)
    db.save_game(game_id, game)
    assert db.load_game(game_id) is not None
    assert db.load_game("x" * 30) is None
    assert len(tracked) == 4
    assert all(is_closed(conn) for conn in tracked)


def test_a_failed_write_rolls_back_and_still_closes(tracked):
    engine = Engine()
    game = engine.new_game(seed=3)
    game_id = db.create_game(game)
    with pytest.raises(RuntimeError):
        with db._connect() as conn:
            conn.execute("UPDATE games SET state = '{}' WHERE id = ?", (game_id,))
            raise RuntimeError("boom")
    assert all(is_closed(conn) for conn in tracked)
    assert db.load_game(game_id).seed == 3  # the half-done write was rolled back
