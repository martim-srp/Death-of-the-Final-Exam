"""The cover image and the theme that matches it."""

import tomllib
from pathlib import Path



ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")
COVER = ROOT / "assets" / "cover.webp"


def test_cover_image_is_in_the_repo_and_small():
    assert COVER.exists()
    assert COVER.stat().st_size < 1_000_000


def test_theme_is_dark_with_the_cover_colours():
    config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert config["theme"]["base"] == "dark"
    assert config["theme"]["primaryColor"].startswith("#")


def test_streamlit_secrets_are_never_committed():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".streamlit/secrets.toml" in ignored
