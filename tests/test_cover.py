"""The cover image and the theme that matches it."""

import tomllib
from pathlib import Path

from streamlit.testing.v1 import AppTest

from game.engine import Engine

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")
COVER = ROOT / "assets" / "cover.webp"


def test_cover_image_is_in_the_repo_and_small():
    assert COVER.exists()
    assert COVER.stat().st_size < 1_000_000


def test_start_screen_shows_the_cover():
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = Engine().new_game(seed=1, variant="A").to_dict()
    at.run()
    assert not at.exception
    assert len(at.get("image")) == 1


def test_theme_is_dark_with_the_cover_colours():
    config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert config["theme"]["base"] == "dark"
    assert config["theme"]["primaryColor"].startswith("#")


def test_streamlit_secrets_are_never_committed():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".streamlit/secrets.toml" in ignored
