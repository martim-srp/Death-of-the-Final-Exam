"""The Save game popover shares a resumable link without collecting personal data."""

import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

from streamlit.testing.v1 import AppTest

import db
from game.engine import Engine


APP = str(Path(__file__).resolve().parent.parent / "app.py")
PUBLIC_URL = "https://carcavelos-paper.streamlit.app"


def start(game=None, game_id=None):
    at = AppTest.from_file(APP, default_timeout=15)
    game = game or Engine().new_game(seed=1, variant="A")
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    if game_id is not None:
        at.session_state["game_id"] = game_id
    at.run()
    assert not at.exception
    return at


def open_save_game(at):
    popover = next(item for item in at.get("popover") if item.proto.popover.label == "Save game")
    popover.proto.popover.open = True
    at.run()
    assert not at.exception
    return at


def link_button_url(at):
    element = at.get("link_button")
    return element[0].proto.url if element else None


def test_home_panel_shows_a_save_game_popover():
    at = start()
    assert any(item.proto.popover.label == "Save game" for item in at.get("popover"))


def test_save_game_popover_shows_the_resume_link_and_email_action():
    game_id = "aBcdEF0123456789_XyZ"
    at = open_save_game(start(game_id=game_id))

    assert at.code[0].value.endswith(f"?game={game_id}")
    assert at.code[0].value.startswith(PUBLIC_URL)
    mailto = link_button_url(at)
    parts = urlsplit(mailto)
    assert parts.scheme == "mailto" and parts.path == ""
    query = dict(item.split("=", 1) for item in parts.query.split("&"))
    assert unquote(query["subject"]) == "My Death of the Final Exam case"
    assert unquote(query["body"]) == f"Pick up where I left off: {at.code[0].value}"


def test_save_game_without_an_id_shows_no_link_or_email_button():
    at = open_save_game(start())

    assert any("Saving is not available for this case." in c.value for c in at.caption)
    assert not at.code
    assert link_button_url(at) is None


def test_resume_link_falls_back_to_the_public_url_when_context_url_is_empty():
    at = open_save_game(start(game_id="aBcdEF0123456789_XyZ"))
    assert at.code[0].value.startswith(PUBLIC_URL)


def test_resume_link_url_encodes_the_game_id():
    at = open_save_game(start(game_id="case id"))
    assert at.code[0].value.endswith("?game=case%20id")


def test_resume_url_opens_the_same_saved_variant_and_clock():
    game = Engine().new_game(seed=2, variant="B")
    Engine().open_clue(game, "D1")
    game_id = db.create_game(game)

    at = AppTest.from_file(APP, default_timeout=15)
    at.query_params["game"] = game_id
    at.run()

    assert not at.exception
    assert at.session_state["game"]["variant"] == "B"
    assert at.session_state["game"]["clock"] == game.clock
    assert at.session_state["game_id"] == game_id


def test_save_email_and_home_page_do_not_expose_solution_or_variant_label():
    game = Engine().new_game(seed=1, variant="A")
    game_id = db.create_game(game)
    at = open_save_game(start(game, game_id))
    mailto = link_button_url(at)
    rendered = "\n".join(
        [*[element.value for element in at.markdown],
         *[element.value for element in at.caption],
         *[element.value for element in at.code],
         mailto or ""]
    )
    solution = json.dumps(Engine().case["variants"]["A"]["solution"])

    assert solution not in rendered
    assert "Variant A" not in rendered
    assert "variant=A" not in (mailto or "")
