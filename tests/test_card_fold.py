"""Less reading on an open card: the "In short" line and the detective's thought come first,
and the whole card (picture, text, log search, "Look closer") waits behind one tap."""

from game.engine import Engine
from tests.test_board_game import page, start


def opened(clue_id, mode="normal"):
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.set_mode(game, mode)
    engine.open_clue(game, clue_id)
    return start(game=game, focus=("clue", clue_id))


def test_an_open_card_shows_its_short_line_and_folds_the_rest():
    at = opened("D1")
    assert "In short" in page(at)
    assert [e.label for e in at.expander] == ["Read the whole card"]
    fold = at.expander[0]
    assert any('class="evidence"' in m.value for m in fold.markdown)  # the card's text is inside the fold
    assert fold.toggle(key="hidden_D1") is not None  # and so is "Look closer"


def test_the_short_line_comes_before_the_fold():
    text = page(opened("L4"))
    assert text.index("In short") < text.index('class="evidence"')


def test_hard_mode_shows_the_whole_card_without_a_fold():
    at = opened("D1", mode="hard")
    assert "In short" not in page(at)
    assert not at.expander
    assert 'class="evidence"' in page(at)
