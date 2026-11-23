"""A save missing variables required by the current case must be treated as damaged."""

import json
import sqlite3
from pathlib import Path

from streamlit.testing.v1 import AppTest

import db
from game.engine import Engine

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_resume_with_a_missing_case_variable_starts_a_fresh_case():
    game = Engine().new_game(seed=1, variant="A")
    game_id = db.create_game(game)
    state = game.to_dict()
    del state["variables"]["alias_initials"]
    with sqlite3.connect(db._path()) as conn:
        conn.execute("UPDATE games SET state = ? WHERE id = ?", (json.dumps(state), game_id))

    at = AppTest.from_file(APP, default_timeout=15)
    at.query_params["game"] = game_id
    at.run()

    assert not at.exception
    assert at.session_state["game"]["status"] == "playing"
    assert at.session_state["game_id"] != game_id
    assert "alias_initials" in at.session_state["game"]["variables"]
    assert any("not found" in warning.value for warning in at.warning)
