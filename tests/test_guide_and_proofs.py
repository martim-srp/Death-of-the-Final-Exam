"""The next-step guide, the living map, the line icons and the options the evidence rules out."""

import copy
import re

import pytest

import board
from game.case import load_case
from game.engine import COLUMNS, Engine
from tests.test_board_game import board_markup, click, labels, markups, page, start, suspect_markup

CASE = load_case()
EMOJI = re.compile("[\U0001F000-\U0001FFFF☀-➿]")


def follow_the_guide(engine, game):
    """Do every next step until only the accusation is left. Returns the steps' texts."""
    texts = []
    while True:
        step = engine.next_step(game)
        texts.append(step["text"])
        if step["do"] == "search":
            engine.open_clue(game, step["clue"])
        elif step["do"] == "show":
            engine.present(game, step["suspect"], step["clue"])
        elif step["do"] == "ask":
            engine.ask(game, step["suspect"], step["topic"])
        else:
            return texts


# ---- The next step ---------------------------------------------------------------------


def test_a_new_case_starts_by_searching_the_first_clue():
    step = Engine().next_step(Engine().new_game(seed=1, variant="A"))
    assert step == {"do": "search", "clue": "D1", "text": "Search D1. The leaked PDF."}


@pytest.mark.parametrize("variant", ["A", "B", "C"])
def test_following_the_guide_finds_every_clue_in_time(variant):
    engine = Engine()
    game = engine.new_game(seed=1, variant=variant)
    texts = follow_the_guide(engine, game)
    assert len(game.opened) == len(CASE["clues"])
    assert engine.time_left(game) > 0
    assert texts[-1].startswith("You have every card")


def test_the_guide_is_the_same_in_every_variant_so_it_never_points_at_the_culprit():
    engine = Engine()
    paths = {v: follow_the_guide(engine, engine.new_game(seed=1, variant=v)) for v in "ABC"}
    assert paths["A"] == paths["B"] == paths["C"]


def test_the_guide_says_to_accuse_when_time_is_short_or_after_a_wrong_guess():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    game.clock = engine.clock_rules["limit_minutes"] - 20
    assert engine.next_step(game)["do"] == "accuse"
    game = engine.new_game(seed=1, variant="A")
    follow_the_guide(engine, game)
    wrong = [o["id"] for o in CASE["accusation"]["who"] if o["id"] != CASE["variants"]["A"]["solution"]["who"]][0]
    engine.accuse(game, wrong, *(CASE["variants"]["A"]["solution"][c] for c in COLUMNS[1:]))
    assert engine.next_step(game)["do"] == "accuse"


def test_no_next_step_once_the_case_is_closed():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.accuse(game, **CASE["variants"]["A"]["solution"])
    assert engine.next_step(game) is None


def test_the_next_step_strip_is_on_the_board_and_lights_up_its_target():
    markup = board_markup(start())
    assert 'class="goal-bar" data-act="next:clue:D1"' in markup
    assert 'class="card available goal"' in markup


def test_tapping_the_next_step_opens_its_target():
    suspects, clues = CASE["suspects"], CASE["clues"]
    assert board.parse_act("next:clue:D1", suspects, clues) == ("clue", "D1")
    assert board.parse_act("next:suspect:ta", suspects, clues) == ("suspect", "ta")
    assert board.parse_act("next:sheet", suspects, clues) == ("sheet", None)
    assert board.parse_act("next:next:clue:D1", suspects, clues) is None
    assert board.parse_act("next:clue:Z9", suspects, clues) is None


def test_a_suggested_question_is_marked_and_asked_ones_are_ticked():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    for clue_id in ("D1", "D2", "D4", "D5", "L1", "L4", "D7"):
        engine.open_clue(game, clue_id)
    engine.present(game, "ta", "D2")
    engine.open_clue(game, "L2")
    assert engine.next_step(game) == {"do": "ask", "suspect": "professor", "topic": "exam",
                                      "text": "Ask the Professor about the exam."}
    at = start(game=game, focus=("suspect", "professor"), suspect="professor")
    assert re.search(r'class="sus[^"]* goal" data-act="suspect:professor"', suspect_markup(at))
    options = at.pills(key="ask_topic").options
    assert "→ The exam" in options and "Last night?" in options
    at.pills(key="ask_topic").set_value("alibi").run()
    assert "✓ Last night?" in at.pills(key="ask_topic").options


# ---- The living map ----------------------------------------------------------------------


def test_locked_places_are_under_fog_and_the_map_has_a_night_sky():
    markup = board_markup(start())
    assert markup.count('class="fog"') == sum(1 for c in ("L1", "L3", "L5") if c in board.MAP_PINS)
    assert 'id="night"' in markup and 'class="mist"' in markup


def test_the_fog_lifts_once_when_a_place_opens_up():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "D1")
    engine.open_clue(game, "D2")
    at = start(game=game, focus=("clue", "L1"))
    click(at, "Search it")
    assert 'class="lift"' in board_markup(at)
    at.run()
    assert 'class="lift"' not in board_markup(at)


# ---- No emoji ----------------------------------------------------------------------------


def test_the_board_and_the_panel_use_line_icons_not_emoji():
    at = start(focus=("suspect", "companion"))
    for markup in markups(at):
        assert not EMOJI.search(markup)
    assert not any(EMOJI.search(label) for label in labels(at))
    assert not EMOJI.search(page(at))
    assert "<svg class=\"ic\"" in board_markup(at)


def test_an_unknown_icon_draws_nothing():
    assert board.icon("nope") == ""
    assert board.icon("lock").startswith('<svg class="ic"')


# ---- Ruled out by the evidence ------------------------------------------------------------


def wrong_who(variant="A"):
    answer = CASE["variants"][variant]["solution"]
    return next(o["id"] for o in CASE["accusation"]["who"] if o["id"] != answer["who"])


def test_a_wrong_accusation_rules_out_only_its_wrong_parts():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    answer = CASE["variants"]["A"]["solution"]
    engine.accuse(game, wrong_who(), answer["how"], answer["where"], answer["why"])
    assert engine.eliminated(game) == [{"column": "who", "option": wrong_who(), "by": "accusation"}]


def test_a_clue_rules_out_options_from_the_case_file_but_never_the_answer():
    case = copy.deepcopy(CASE)
    answer = case["variants"]["A"]["solution"]
    case["clues"]["D4"]["rules_out"] = {"who": [wrong_who(), answer["who"]], "why": ["foreign_power"]}
    engine = Engine(case)
    game = engine.new_game(seed=1, variant="A")
    assert engine.eliminated(game) == []  # nothing before the clue is opened
    engine.open_clue(game, "D4")
    out = engine.eliminated(game)
    assert {"column": "who", "option": wrong_who(), "by": "D4"} in out
    assert all(e["option"] != answer[e["column"]] for e in out)


def test_no_clue_in_the_case_file_rules_out_the_answer():
    for variant, data in CASE["variants"].items():
        engine = Engine()
        clues = engine._resolved[variant]["clues"]
        for clue_id, clue in clues.items():
            for column, options in clue.get("rules_out", {}).items():
                assert data["solution"][column] not in options, (variant, clue_id, column)


def test_the_case_sheet_crosses_off_what_a_wrong_accusation_proved():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    answer = CASE["variants"]["A"]["solution"]
    engine.accuse(game, wrong_who(), answer["how"], answer["where"], answer["why"])
    at = start(game=game, focus=("sheet", None))
    assert wrong_who() in at.pills(key="sheet_who").value
    assert "ruled out by your accusation" in page(at)
    assert 'class="sus out' in suspect_markup(at)


# ---- The detective's hunches ---------------------------------------------------------------

from game.case import load_hunches  # noqa: E402

HUNCHES = load_hunches()


def broken_pairs():
    """(variant, clue, 'suspect.claim') for every clue that breaks a story in each variant."""
    engine = Engine()
    for variant in CASE["variants"]:
        for suspect, data in engine._resolved[variant]["suspects"].items():
            for claim in data.get("claims", []):
                for clue_id in claim["broken_by"]:
                    yield variant, clue_id, f"{suspect}.{claim['id']}"


def test_every_clue_that_breaks_a_story_has_a_hunch_and_every_hunch_is_used():
    keys = {f"{clue}|{claim}" for _variant, clue, claim in broken_pairs()}
    assert keys == set(HUNCHES)


@pytest.mark.parametrize("variant,clue_id,claim", sorted(set(broken_pairs())))
def test_each_hunch_highlights_a_detail_that_is_really_in_that_clue(variant, clue_id, claim):
    engine = Engine()
    game = engine.new_game(seed=3, variant=variant)
    clue = engine._resolved[variant]["clues"][clue_id]
    shown = engine._fill(game, clue.get("text", "")) + "\n" + engine._fill(game, clue.get("log") or "")
    mark = engine._fill(game, HUNCHES[f"{clue_id}|{claim}"]["mark"])
    assert mark and mark in shown


def test_a_hunch_never_names_a_suspect():
    names = {word for s in CASE["suspects"].values() for word in s["name"].replace("The ", "").split()}
    names -= {"Student"}  # "student card" is a thing on the cards, not the Exchange Student
    for key, hunch in HUNCHES.items():
        assert not any(name in hunch["line"] for name in names), key


def test_a_hunch_shows_on_an_opened_clue_until_that_lie_is_caught():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    assert engine.hunches(game, "L4") == []  # not opened yet
    engine.open_clue(game, "L4")
    assert [h["mark"] for h in engine.hunches(game, "L4")] == ["trying the handle"]
    engine.present(game, "companion", "L4")
    assert engine.hunches(game, "L4") == []


def test_a_clue_that_breaks_no_story_has_no_hunch():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "D4")
    assert engine.hunches(game, "D4") == []


def test_the_panel_shows_the_hunch_and_highlights_the_detail():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "L4")
    at = start(game=game, focus=("clue", "L4"))
    assert 'class="hunch"' in page(at)
    assert "<mark>trying the handle</mark>" in page(at)
    engine.open_clue(game, "D1")
    engine.open_clue(game, "D2")
    at = start(game=game, focus=("clue", "D2"))
    assert "<mark>owner=STAFF-" in page(at)  # quoted from the log
