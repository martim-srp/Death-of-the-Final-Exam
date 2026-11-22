from html import escape

import pytest

from game.case import load_cracks
from game.engine import Engine, Game
from tests.test_board_game import page, start
from tests.test_nerves_crack import SUSPECTS, all_open, push_to_the_edge


@pytest.mark.parametrize(("variant", "lead"), [
    ("A", "printed at the library printing station"),
    ("B", "printed at the library printing station"),
    ("C", "over dinner at a restaurant in Chiado"),
])
def test_crack_dialogue_matches_suspect_and_variant(variant, lead):
    engine = Engine()
    lines = load_cracks()["variants"][variant]
    assert set(lines) == set(SUSPECTS)
    assert len(set(lines.values())) == len(SUSPECTS)

    for suspect, line in lines.items():
        game = all_open(variant)
        last = push_to_the_edge(engine, game, suspect)
        assert engine.character_brief(game, suspect)["broke_down"] is None
        assert lead in line
        assert engine.present(game, suspect, last)["cracked"]["line"] == line
        resumed = Game.from_dict(game.to_dict())
        assert engine.character_brief(resumed, suspect)["broke_down"] == line


def test_library_variants_use_different_dialogue_for_each_suspect():
    variants = load_cracks()["variants"]
    for suspect in SUSPECTS:
        assert variants["A"][suspect] != variants["B"][suspect]


def test_chiado_dialogue_appears_in_the_interrogation():
    game = all_open("C")
    suspect = "professor"
    last = push_to_the_edge(Engine(), game, suspect)
    app = start(game=game, focus=("suspect", suspect), suspect=suspect)
    app.pills(key="show_clue").set_value(last).run()

    assert not app.exception
    assert escape(load_cracks()["variants"]["C"][suspect]) in page(app)
