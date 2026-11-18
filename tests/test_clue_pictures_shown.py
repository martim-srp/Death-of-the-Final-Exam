"""Opened clues show their evidence picture, in the case file and on the map; others show none."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from game.case import load_case

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")


def start(game, pick=None):
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    if pick:
        at.session_state["map_pick"] = pick
    at.run()
    assert not at.exception
    return at


def pictures(at):
    """The images on the page, besides the ones every page has (the logo)."""
    return len(at.get("image")) - BASELINE_IMAGES


BASELINE_IMAGES = 1  # the Nova SBE logo in the header


def test_every_clue_has_a_picture_except_the_chart_and_the_corridor():
    ids = {c["id"] if isinstance(c, dict) else c for c in load_case()["clues"]}
    with_picture = {p.stem for p in (ROOT / "assets" / "clues").glob("*.webp")}
    assert with_picture <= ids
    assert ids - with_picture == {"D4", "L4"}


