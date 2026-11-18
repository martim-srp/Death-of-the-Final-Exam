"""The detective's voice: a thought on every clue, a reaction after every answer, and the
next step told as a thought. All of it must be the same in every variant and for every
suspect, so none of it can point at the culprit."""

import html

import pytest

import reloading
from game.case import load_case, load_voice
from game.engine import Engine
from tests.test_board_game import board_markup, page, start

CASE = load_case()
VOICE = load_voice()
NAMES = {word for s in CASE["suspects"].values() for word in s["name"].replace("The ", "").split()} - {"Student"}


def neutral_lines():
    """Every line that is shown without a suspect in mind (the next-step lines may name the
    suspect the unlock rules point to, which is the same in every variant)."""
    yield from VOICE["clues"].values()
    yield from VOICE["search"].values()
    for lines in VOICE["replies"].values():
        yield from lines


def test_every_clue_has_a_thought_and_a_search_line():
    assert set(VOICE["clues"]) == set(CASE["clues"])
    assert set(VOICE["search"]) == set(CASE["clues"])


def test_no_neutral_line_names_a_suspect():
    for line in neutral_lines():
        assert not any(name in line for name in NAMES), line


def test_lines_are_short_and_have_no_double_dots():
    for line in neutral_lines():
        assert len(line) <= 110, line
        assert ".." not in line, line


def test_the_voice_file_rebuilds_the_engine_on_the_live_site():
    assert "data/voice.json" in reloading.SOURCES


def test_an_opened_clue_with_no_hunch_gets_a_thought():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    assert engine.musing(game, "D4") is None  # not opened yet
    engine.open_clue(game, "D4")
    assert engine.musing(game, "D4") == VOICE["clues"]["D4"]


def test_the_hunch_wins_until_the_lie_is_caught_then_the_thought_shows():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "L4")
    assert engine.hunches(game, "L4") and engine.musing(game, "L4") is None
    engine.present(game, "companion", "L4")
    assert engine.musing(game, "L4") == VOICE["clues"]["L4"]


@pytest.mark.parametrize("variant", ["A", "B", "C"])
def test_every_clue_shows_a_hunch_or_a_thought_once_opened(variant):
    engine = Engine()
    game = engine.new_game(seed=1, variant=variant)
    while True:
        step = engine.next_step(game)
        if step["do"] == "search":
            engine.open_clue(game, step["clue"])
            assert engine.hunches(game, step["clue"]) or engine.musing(game, step["clue"])
        elif step["do"] == "show":
            engine.present(game, step["suspect"], step["clue"])
        elif step["do"] == "ask":
            engine.ask(game, step["suspect"], step["topic"])
        else:
            break


def test_a_reaction_depends_on_what_happened_not_on_who_answered():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    replies = VOICE["replies"]
    assert engine.reaction(game, topic="alibi") in replies["alibi"]
    assert engine.reaction(game, topic="alibi", caught=True) in replies["caught"]
    assert engine.reaction(game, topic="alibi", unlocked=True) in replies["unlocked"]
    assert engine.reaction(game, shown=True) in replies["shown"]
    assert engine.reaction(game) in replies["typed"]
    # Variant changes the culprit, never the line.
    lines = {Engine().reaction(Engine().new_game(seed=1, variant=v), topic="leak") for v in ("A", "B", "C")}
    assert len(lines) == 1


@pytest.mark.parametrize("variant", ["A", "B", "C"])
def test_the_next_step_reads_as_a_thought_in_every_variant(variant):
    engine = Engine()
    game = engine.new_game(seed=1, variant=variant)
    thoughts = []
    for _ in range(40):
        step = engine.next_step(game)
        thought = engine.thought(game, step)
        assert thought and "{" not in thought and thought != step["text"], step
        thoughts.append(thought)
        if step["do"] == "search":
            engine.open_clue(game, step["clue"])
        elif step["do"] == "show":
            engine.present(game, step["suspect"], step["clue"])
        elif step["do"] == "ask":
            engine.ask(game, step["suspect"], step["topic"])
        else:
            break
    assert thoughts[-1] == VOICE["next"]["sheet"]


def test_the_guide_bar_leads_with_the_thought_and_keeps_the_plain_step():
    at = start()
    markup = html.unescape(board_markup(at))
    assert VOICE["search"]["D1"] in markup
    assert "Search D1. The leaked PDF." in markup


def test_asking_a_question_adds_the_detectives_reaction_to_the_chat():
    at = start(focus=("suspect", "professor"), suspect="professor")
    at.pills(key="ask_topic").set_value("leak").run()
    chat = at.session_state["chats"]["professor"]
    assert chat[-1]["think"] in VOICE["replies"]["leak"] + VOICE["replies"]["unlocked"]
    assert 'class="bubble think"' in page(at)


def test_an_opened_clue_panel_shows_the_thought():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "D4")
    at = start(game=game, focus=("clue", "D4"))
    assert 'class="hunch"' in page(at)
    assert html.escape(VOICE["clues"]["D4"], quote=False) in page(at).replace("&#x27;", "'")
