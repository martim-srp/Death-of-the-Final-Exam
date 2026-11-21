"""Second round of blind playtests (21 Nov): the caption after a wrong accusation, and the notebook
keeping each whole story."""

from tests.test_board_game import CASE, click, pick, solution, start


def all_wrong():
    right = solution()
    return {column: next(o["id"] for o in CASE["accusation"][column] if o["id"] != right[column]) for column in right}


def test_nothing_right_says_to_rethink_all_four():
    at = start(focus=("accuse", None))
    pick(at, **all_wrong())
    click(at, "Accuse")
    click(at, "Yes, accuse")
    assert at.session_state["verdict"] == []
    captions = [c.value for c in at.caption]
    assert any("0 of 4 right. Nothing to keep: rethink all four." in c for c in captions)
    assert not any("Keep the ✓ parts" in c for c in captions)


def test_some_right_still_says_to_keep_the_right_parts():
    at = start(focus=("accuse", None))
    pick(at, **{**solution(), "who": all_wrong()["who"]})
    click(at, "Accuse")
    click(at, "Yes, accuse")
    assert any("3 of 4 right. Keep the ✓ parts" in c.value for c in at.caption)


# ---- The notebook keeps each whole story ------------------------------------------------


def test_the_notebook_keeps_the_whole_story_so_the_line_a_card_breaks_is_there():
    """Variant C: the Companion's claim 'I never touched his laptop' is her last sentence. The
    notebook used to keep only the first two sentences, so the line evidence 1 breaks was missing."""
    from game.engine import Engine
    from tests.test_board_game import page

    engine = Engine()
    game = engine.new_game(seed=1, variant="C")
    engine.ask(game, "companion", "alibi")
    engine.ask(game, "professor", "alibi")
    text = page(start(game=game, variant="C", focus=("sheet", None)))
    assert "I never touched his laptop." in text
    assert "I printed nothing." in text  # the Professor's last sentence too
