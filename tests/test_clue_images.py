"""Tests for the clue evidence pictures in assets/clues/."""

from game.case import load_case
from board import ASSETS

CLUE_IMAGES_DIR = ASSETS / "clues"

MAX_BYTES = 100_000


def _pictures():
    return sorted(CLUE_IMAGES_DIR.glob("*"))


def test_there_are_clue_pictures():
    assert _pictures(), "assets/clues/ should hold at least one picture"


def test_every_picture_belongs_to_a_clue():
    clues = load_case()["clues"]
    for path in _pictures():
        assert path.suffix == ".webp", f"{path.name} should be a .webp file"
        assert path.stem in clues, f"{path.name} does not match any clue id"


def test_pictures_are_real_small_webp_files():
    for path in _pictures():
        data = path.read_bytes()
        assert data[:4] == b"RIFF" and data[8:12] == b"WEBP", f"{path.name} is not a WebP image"
        assert len(data) <= MAX_BYTES, f"{path.name} is {len(data)} bytes, over {MAX_BYTES}"

