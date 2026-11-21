"""The map and the portraits are served as static files, cached by the browser; evidence pictures are not.

Before, every redraw re-sent the map and every portrait inside the page as data URIs (about
300 KB a tap). Evidence pictures stay data URIs because a static file can be fetched by
anyone at any time, and a locked card must never reach the browser.
"""

import tomllib
from pathlib import Path

import board

ROOT = Path(__file__).resolve().parent.parent


def test_static_serving_is_switched_on():
    config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert config["server"]["enableStaticServing"] is True


def test_every_static_picture_is_an_exact_copy_of_its_asset():
    served = [p for p in (ROOT / "static").rglob("*") if p.is_file()]
    assert served
    for path in served:
        original = ROOT / "assets" / path.relative_to(ROOT / "static")
        assert original.is_file(), f"{path} has no original in assets/"
        assert path.read_bytes() == original.read_bytes(), f"{path} differs from {original}"


def test_every_portrait_and_the_map_are_served():
    for folder in board.STATIC_FOLDERS:
        for original in (ROOT / "assets" / folder).iterdir():
            assert (ROOT / "static" / folder / original.name).is_file(), original
    assert (ROOT / "static" / "campus-map.webp").is_file()


def test_portraits_are_static_urls():
    assert board.suspect_picture("ta") == "app/static/suspects/ta.webp"
    assert board.suspect_picture("ta", nervous=True) == "app/static/suspects/ta_nervous.webp"
    assert board.find_picture("detectives", "she") == "app/static/detectives/she.webp"
    assert board.static_url("campus-map.webp") == "app/static/campus-map.webp"


def test_evidence_pictures_are_never_static():
    assert not (ROOT / "static" / "clues").exists()
    assert board.find_picture("clues", "D1").startswith("data:image/")
    assert board.static_url("clues/D1.webp") is None


def test_a_missing_picture_is_still_none():
    assert board.find_picture("suspects", "nobody") is None
    assert board.static_url("suspects/nobody.webp") is None
