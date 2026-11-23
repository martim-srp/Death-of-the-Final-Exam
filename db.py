"""Saved games, stored in SQLite.

All database code lives in this file. Each game is saved under a random, unguessable id,
which becomes the private resume link (?game=<id>). Anyone with the link can resume the
game; nobody can list or guess other games.

The database file comes from the DATABASE_PATH environment variable, or data/app.db.
On Streamlit Community Cloud the disk is temporary, so saved games are lost when the app
restarts. That is fine for this game: a game lasts minutes, not weeks.
"""

import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from game.engine import Engine, Game

DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "app.db"
GAME_ID = re.compile(r"^[A-Za-z0-9_-]{20,64}$")


@lru_cache(maxsize=1)
def _save_validator():
    """Reuse the current case schema when checking saves at the database boundary."""
    return Engine()


def _path():
    return os.environ.get("DATABASE_PATH", str(DEFAULT_PATH))


@contextmanager
def _connect():
    """A connection that commits on success, rolls back on error, and is always closed.

    sqlite3's own "with conn" only commits; it never closes, so every save left an open
    file handle until garbage collection (Python warns: "unclosed database").
    """
    conn = sqlite3.connect(_path(), timeout=10)
    try:
        with conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS games ("
                " id TEXT PRIMARY KEY,"
                " state TEXT NOT NULL,"
                " updated_at TEXT NOT NULL)"
            )
            yield conn
    finally:
        conn.close()


def _now():
    return datetime.now(timezone.utc).isoformat()


def valid_id(game_id):
    """True if the id has the shape of one we would have issued."""
    return isinstance(game_id, str) and bool(GAME_ID.match(game_id))


def create_game(game):
    """Save a new game and return its private id."""
    game_id = secrets.token_urlsafe(24)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO games (id, state, updated_at) VALUES (?, ?, ?)",
            (game_id, json.dumps(game.to_dict()), _now()),
        )
    return game_id


def save_game(game_id, game, *, expected_state=None):
    """Update a saved game if it still matches the snapshot used for the action."""
    if not valid_id(game_id):
        raise ValueError("Invalid game id.")
    with _connect() as conn:
        params = (json.dumps(game.to_dict()), _now(), game_id)
        if expected_state is None:
            cursor = conn.execute("UPDATE games SET state = ?, updated_at = ? WHERE id = ?", params)
        else:
            cursor = conn.execute(
                "UPDATE games SET state = ?, updated_at = ? WHERE id = ? AND state = ?",
                (*params, expected_state),
            )
        return cursor.rowcount == 1


def load_game(game_id):
    """The saved game, or None if the id is malformed or unknown, or the save is damaged."""
    return load_game_snapshot(game_id)[0]


def load_game_snapshot(game_id):
    """Return the game and the stored state used to guard its next update."""
    if not valid_id(game_id):
        return None, None
    with _connect() as conn:
        row = conn.execute("SELECT state FROM games WHERE id = ?", (game_id,)).fetchone()
    if row is None:
        return None, None
    try:
        game = Game.from_dict(json.loads(row[0]))
        if not _save_validator().valid_saved_game(game):
            return None, None
        return game, row[0]
    except (ValueError, TypeError, AttributeError):
        # Not JSON, not an object, or missing a required field: treat it as not found,
        # so the player gets a new case instead of an error page.
        return None, None
