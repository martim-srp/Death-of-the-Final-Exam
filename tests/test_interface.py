"""Interface features from issue #3: log search, the D4 payoff chart and the denouement screen."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from game.case import load_case
from game.engine import Engine

APP = str(Path(__file__).resolve().parent.parent / "app.py")
CASE = load_case()


def start(variant="A", seed=1):
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = Engine().new_game(seed=seed, variant=variant).to_dict()
    at.run()
    assert not at.exception
    return at


def click(at, starts_with):
    next(b for b in at.button if b.label.startswith(starts_with)).click().run()
    assert not at.exception


def page_text(at):
    return "\n".join(m.value for m in at.markdown)


# ---- Log search ------------------------------------------------------------------


# ---- Denouement ------------------------------------------------------------------


def test_denouement_is_hidden_while_the_case_is_open():
    at = start()
    assert "Half past seven" not in "\n".join(s.value for s in at.subheader)
    assert "You close the folder" not in page_text(at)
