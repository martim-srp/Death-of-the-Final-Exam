"""The lightning in the status bar: tap it to see what a caught lie means and the lies caught so far."""

import pytest

import board
from game.case import load_case
from game.engine import NERVES_MAX, NERVES_PER_CARD, NERVES_PER_LIE, NERVES_START, Engine
from tests.test_board_game import board_markup, page, start

CASE = load_case()


def game_with_a_lie_caught():
    """Variant A: the TA says they proofread on screen; the print log (D2) says otherwise."""
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "D1")
    engine.open_clue(game, "D2")
    result = engine.present(game, "ta", "D2")
    assert result["contradictions"], "the print log should break the TA's story in variant A"
    return engine, game


def claim_texts(engine, game):
    return [c["text"].rstrip(".") for s in CASE["suspects"].values() for c in s.get("claims", [])]


# ---- The tap ------------------------------------------------------------------------------


def test_the_lies_counter_is_a_button_that_opens_the_lies_panel():
    hud = board_markup(start())
    assert '<button class="stat zapstat" type="button" data-act="lies"' in hud
    assert board.parse_act("lies", CASE["suspects"], CASE["clues"]) == ("lies", None)


@pytest.mark.parametrize("act", ["lies:ta", "lie", "LIES"])
def test_a_malformed_lies_tap_is_ignored(act):
    assert board.parse_act(act, CASE["suspects"], CASE["clues"]) is None


# ---- The panel ----------------------------------------------------------------------------


def test_with_no_lies_caught_it_explains_how_to_catch_one():
    at = start(focus=("lies", None))
    text = page(at)
    assert "No lies caught yet" in text
    assert "show a suspect the evidence card that breaks something they told you" in text
    assert f"Their nerves go up by {NERVES_PER_LIE}" in text and f"At {NERVES_MAX} they crack" in text
    assert "A lie is not proof of guilt" in text
    assert "show them that card" in " ".join(c.value for c in at.caption)
    assert not [b for b in at.button if b.label.startswith("Question ")]


def test_it_never_shows_a_lie_that_has_not_been_caught():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    for clue in ("D1", "D2", "D4", "D5"):
        engine.open_clue(game, clue)
    text = page(start(game=game, focus=("lies", None)))
    for claim in claim_texts(engine, game):
        assert claim not in text


def test_a_caught_lie_is_listed_with_its_card_and_the_suspects_nerves():
    engine, game = game_with_a_lie_caught()
    at = start(game=game, focus=("lies", None))
    text = page(at)
    assert "1 lie caught" in text
    caught = engine.contradiction_list(game)[0]
    assert caught["text"].rstrip(".") in text and "broken by <b>evidence 2</b>" in text
    nerves = NERVES_START + NERVES_PER_CARD + NERVES_PER_LIE
    assert f"Nerves {nerves} of {NERVES_MAX}" in text
    assert "1</b><small>lie caught</small>" in board_markup(at)


def test_question_again_opens_that_suspect():
    _engine, game = game_with_a_lie_caught()
    at = start(game=game, focus=("lies", None))
    button = next(b for b in at.button if b.label.startswith("Question "))
    assert button.label == "Question Teaching Assistant again"
    button.click().run()
    assert not at.exception
    assert at.session_state["focus"] == ("suspect", "ta")
    assert "Interrogation" in page(at)
