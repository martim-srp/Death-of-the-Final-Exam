"""Progress counters: how much of each suspect you have covered, a clear sign when there is
nothing left to ask."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import board
from game.case import load_case
from game.engine import Engine, GameError

APP = str(Path(__file__).resolve().parent.parent / "app.py")
CASE = load_case()
SUSPECTS = list(CASE["suspects"])


def everything_asked(engine, game, suspect):
    for topic in engine.topics_for(suspect):
        engine.ask(game, suspect, topic)


def first_open_card(engine, game):
    clue = next(c["id"] for c in engine.clue_list(game) if c["state"] == "available")
    engine.open_clue(game, clue)
    return clue


# ---- Engine.topics_for --------------------------------------------------------------------


def test_every_suspect_can_be_asked_every_topic_but_the_ta_about_the_ta():
    engine = Engine()
    for suspect in SUSPECTS:
        expected = [t for t in CASE["topics"] if not (suspect == "ta" and t == "teaching_assistant")]
        assert engine.topics_for(suspect) == expected


def test_topics_for_an_unknown_suspect_is_refused():
    with pytest.raises(GameError):
        Engine().topics_for("dean")


# ---- Engine.suspect_progress ---------------------------------------------------------------


def test_a_new_game_starts_with_nothing_covered():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    for suspect in SUSPECTS:
        progress = engine.suspect_progress(game, suspect)
        assert progress["asked"] == 0 and progress["shown"] == 0 and progress["cards"] == 0
        assert progress["questions"] == len(engine.topics_for(suspect))
        assert progress["done"] is False


def test_asking_the_same_question_twice_counts_once():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.ask(game, "professor", "alibi")
    engine.ask(game, "professor", "alibi")
    assert engine.suspect_progress(game, "professor")["asked"] == 1


def test_questions_count_only_for_the_suspect_asked():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.ask(game, "professor", "alibi")
    assert engine.suspect_progress(game, "ta")["asked"] == 0


def test_every_question_and_no_cards_means_nothing_left_to_ask():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    everything_asked(engine, game, "exchange")
    assert engine.suspect_progress(game, "exchange")["done"] is True


def test_a_new_card_means_there_is_something_to_show_again():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    everything_asked(engine, game, "exchange")
    clue = first_open_card(engine, game)
    progress = engine.suspect_progress(game, "exchange")
    assert progress["cards"] == 1 and progress["shown"] == 0 and progress["done"] is False
    engine.present(game, "exchange", clue)
    assert engine.suspect_progress(game, "exchange")["done"] is True


def test_progress_is_the_same_in_every_variant_for_the_same_moves():
    """It comes from the player's moves, never from who is guilty."""
    engine = Engine()
    results = []
    for variant in CASE["variants"]:
        game = engine.new_game(seed=1, variant=variant)
        everything_asked(engine, game, "professor")
        results.append({s: engine.suspect_progress(game, s) for s in SUSPECTS})
    assert all(r == results[0] for r in results)


def test_progress_for_an_unknown_suspect_is_refused():
    engine = Engine()
    with pytest.raises(GameError):
        engine.suspect_progress(engine.new_game(seed=1, variant="A"), "dean")


def test_progress_does_not_change_the_game():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    before = json.dumps(game.to_dict(), sort_keys=True)
    for suspect in SUSPECTS:
        engine.suspect_progress(game, suspect)
    assert json.dumps(game.to_dict(), sort_keys=True) == before


# ---- On the screen --------------------------------------------------------------------------


def start(game, **state):
    at = AppTest.from_file(APP, default_timeout=15)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception
    return at


def page(at):
    return "\n".join(m.value for m in at.markdown)


def suspect_markup(at):
    markups = [json.loads(c.proto.json) for c in at.get("bidi_component")]
    return next(m for m in markups if m.startswith('<div class="suspects">'))


def test_the_interrogation_shows_how_much_is_asked():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.ask(game, "professor", "alibi")
    text = page(start(game, focus=("suspect", "professor"), suspect="professor"))
    assert f"Questions asked <b>1 of {len(engine.topics_for('professor'))}</b>" in text
    assert "Evidence shown <b>none found yet</b>" in text
    assert "Nothing left to ask" not in text


def test_the_interrogation_says_when_there_is_nothing_left_to_ask():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    everything_asked(engine, game, "exchange")
    text = page(start(game, focus=("suspect", "exchange"), suspect="exchange"))
    assert "Nothing left to ask" in text


def test_the_suspect_card_marks_a_suspect_with_nothing_left_to_ask():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    everything_asked(engine, game, "exchange")
    engine.ask(game, "professor", "alibi")
    row = suspect_markup(start(game))
    exchange = row.split('data-act="suspect:exchange"')[1].split("</button>")[0]
    professor = row.split('data-act="suspect:professor"')[1].split("</button>")[0]
    assert 'title="Nothing left to ask"' in exchange
    assert 'title="Nothing left to ask"' not in professor and 'title="Questioned"' in professor


def test_the_home_panel_does_not_repeat_the_counters():
    # The status bar, the evidence hand and the WHO/HOW/WHERE/WHY strip already count these:
    # the home panel keeps only what to do next.
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    first_open_card(engine, game)
    everything_asked(engine, game, "exchange")
    text = page(start(game, focus=("home", None)))
    assert "The case so far" not in text
    assert "evidence cards found" not in text and "suspects with nothing left to ask" not in text


def test_no_recap_before_the_first_move():
    text = page(start(Engine().new_game(seed=1, variant="A"), focus=("home", None)))
    assert "The case so far" not in text
    assert "Where to start" in text


def test_the_done_mark_is_a_line_icon():
    markup = board.suspects_html([{"id": "ta", "name": "The TA", "questioned": True, "caught": 0, "ruled_out": False, "done": True}])
    assert 'class="tick all"' in markup and "<svg" in markup
