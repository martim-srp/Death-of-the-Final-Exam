"""The noir look: suspect portraits, the row of suspect cards and the detective's notebook."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from game.case import load_case
from game.engine import Engine

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")
PORTRAITS = ROOT / "assets" / "suspects"
SUSPECTS = list(load_case()["suspects"])


def start(variant="A", seed=1):
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = Engine().new_game(seed=seed, variant=variant).to_dict()
    at.run()
    assert not at.exception
    return at


def click(at, starts_with):
    next(b for b in at.button if b.label.startswith(starts_with)).click().run()
    assert not at.exception


def page(at):
    return "\n".join(m.value for m in at.markdown)


def cards(at):
    """The HTML of the suspect card row."""
    return next(m.value for m in at.markdown if 'class="suspect-row"' in m.value)


def notebook_box(at, label):
    return next(c for c in at.sidebar.checkbox if c.label == label)


PORTRAIT_TYPES = (".png", ".jpg", ".jpeg", ".webp", ".svg")


@pytest.mark.parametrize("suspect", SUSPECTS)
def test_every_suspect_has_one_small_portrait(suspect):
    found = [PORTRAITS / f"{suspect}{ext}" for ext in PORTRAIT_TYPES if (PORTRAITS / f"{suspect}{ext}").exists()]
    assert found, f"no portrait for {suspect} in assets/suspects"
    for path in found:
        assert path.stat().st_size < 300_000, f"{path.name} is too big for a phone; shrink it"


@pytest.mark.parametrize("suspect", SUSPECTS)
def test_picture_portraits_are_portrait_shaped(suspect):
    from PIL import Image  # installed with streamlit

    for ext in PORTRAIT_TYPES[:-1]:
        path = PORTRAITS / f"{suspect}{ext}"
        if path.exists():
            with Image.open(path) as picture:
                width, height = picture.size
            assert abs(width / height - 0.8) < 0.02, f"{path.name} should be 4:5, like the cards"


def test_no_cards_or_notebook_once_the_case_is_closed():
    game = Engine().new_game(seed=1, variant="A")
    game.status = "cold"
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = game.to_dict()
    at.run()
    assert not at.exception
    assert not any('class="suspect-row"' in m.value for m in at.markdown)
    assert not any(e.label.startswith("📓") for e in at.sidebar.expander)
