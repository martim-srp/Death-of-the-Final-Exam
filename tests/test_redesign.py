"""The easier-to-play layout: start screen, tap-to-talk portraits, chat, case board, status bar."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from game.case import load_case
from game.engine import Engine

APP = str(Path(__file__).resolve().parent.parent / "app.py")
CASE = load_case()


def start(variant="A", seed=1, intro_done=None, game=None):
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = (game or Engine().new_game(seed=seed, variant=variant)).to_dict()
    if intro_done is not None:
        at.session_state["intro_done"] = intro_done
    at.run()
    assert not at.exception
    return at


def click(at, starts_with):
    next(b for b in at.button if b.label.startswith(starts_with)).click().run()
    assert not at.exception


def page(at):
    return "\n".join(m.value for m in at.markdown)


def labels(at):
    return [b.label for b in at.button]


# ---- Start screen ------------------------------------------------------------------


def test_a_resumed_game_skips_the_intro():
    game = Engine().new_game(seed=1, variant="A")
    Engine().open_clue(game, "D1")
    at = start(game=game)
    assert "Start the investigation" not in labels(at)


# ---- Status bar --------------------------------------------------------------------


# ---- Tap a portrait to talk -----------------------------------------------------------


# ---- Case file ---------------------------------------------------------------------


# ---- Case board --------------------------------------------------------------------


# ---- Map ---------------------------------------------------------------------------


# ---- Detective portraits -------------------------------------------------------------


DETECTIVES = Path(__file__).resolve().parent.parent / "assets" / "detectives"


def test_each_detective_has_a_small_portrait_shaped_picture():
    from PIL import Image  # installed with streamlit

    for avatar in ("she", "he"):
        path = DETECTIVES / f"{avatar}.webp"
        assert path.stat().st_size < 300_000
        with Image.open(path) as picture:
            width, height = picture.size
        assert abs(width / height - 0.8) < 0.02


