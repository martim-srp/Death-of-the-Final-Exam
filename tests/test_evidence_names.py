"""Renamed evidence stays consistent in cards, clue panels and closed-case reports."""

import re

import pytest

import report
from game.engine import Engine
from tests.test_board_game import board_markup, start


@pytest.mark.parametrize("variant", ["A", "B", "C"])
def test_requested_evidence_names_across_the_game(variant):
    engine = Engine()
    game = engine.new_game(seed=7, variant=variant)
    names = {"D4": "Rules/Standings", "D5": "Mystery number"}
    for clue, name in names.items():
        engine.open_clue(game, clue)
        at = start(game=game, focus=("clue", clue))
        assert any(f"<h3>{name}</h3>" in m.value for m in at.markdown)
        markup = board_markup(at)
        assert f'aria-label="{engine.label(clue)}"' in markup
        assert f"<span>{name}</span>" in re.sub(r"<wbr\s*/?>", "", markup)

    for _ in range(engine.case["max_strikes"]):
        engine.accuse(game, "exchange", "photographed_desk", "beach_cafe", "sell_paper")
    text = report.build(engine, game)
    assert "Evidence 4. Rules/Standings" in text
    assert "Evidence 5. Mystery number" in text
