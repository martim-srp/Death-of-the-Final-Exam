"""The board-game screen: the map board, the evidence hand, the suspects and the side panel."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import board
import db
from game.case import load_case
from game.engine import Engine

APP = str(Path(__file__).resolve().parent.parent / "app.py")
CASE = load_case()
SUSPECTS = list(CASE["suspects"])


def start(variant="A", seed=1, focus=None, intro_done=True, game=None, **state):
    at = AppTest.from_file(APP, default_timeout=15)
    at.session_state["game"] = (game or Engine().new_game(seed=seed, variant=variant)).to_dict()
    if intro_done is not None:
        at.session_state["intro_done"] = intro_done
    if focus:
        at.session_state["focus"] = focus
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception
    return at


def markups(at):
    return [json.loads(c.proto.json) for c in at.get("bidi_component")]


def board_markup(at):
    return next(m for m in markups(at) if 'class="hud' in m)


def suspect_markup(at):
    return next(m for m in markups(at) if m.startswith('<div class="suspects">'))


def page(at):
    return "\n".join(m.value for m in at.markdown)


def click(at, starts_with):
    next(b for b in at.button if b.label.startswith(starts_with)).click().run()
    assert not at.exception


def labels(at):
    return [b.label for b in at.button]


def solution(variant="A"):
    return dict(CASE["variants"][variant]["solution"])


# ---- Taps from the board ---------------------------------------------------------------


@pytest.mark.parametrize(
    "act, expected",
    [
        ("suspect:ta", ("suspect", "ta")),
        ("clue:D2", ("clue", "D2")),
        ("place:L4", ("clue", "L4")),
        ("spot:chiado", ("spot", "chiado")),
        ("accuse", ("accuse", None)),
        ("sheet", ("sheet", None)),
        ("intro", ("intro", None)),
    ],
)
def test_taps_open_the_right_panel(act, expected):
    assert board.parse_act(act, CASE["suspects"], CASE["clues"]) == expected


@pytest.mark.parametrize("act", ["suspect:dean", "clue:Z9", "clue:../../etc", "solve", "", None, "accuse:now"])
def test_unknown_taps_are_ignored(act):
    assert board.parse_act(act, CASE["suspects"], CASE["clues"]) is None


# ---- Status bar ------------------------------------------------------------------------


def test_status_bar_shows_clock_time_left_and_accusations():
    at = start()
    hud = board_markup(at)
    assert "00:00" in hud and "9h 00m to 09:00" in hud
    assert hud.count('class="pip on"') == CASE["max_strikes"]
    assert "Accuse" in hud


def test_the_status_bar_shows_the_players_detective_and_name():
    at = start(player_avatar="he", player_name="Martim")
    hud = board_markup(at)
    assert "Martim" in hud
    assert board.find_picture("detectives", "he") in hud


# ---- The map and the hand --------------------------------------------------------------


def test_map_has_a_pin_per_place_and_chiado():
    markup = board_markup(start())
    for clue_id in board.MAP_PINS:
        assert f'data-act="place:{clue_id}"' in markup
    assert 'data-act="spot:chiado"' in markup


def test_every_clue_is_a_card_in_the_hand():
    markup = board_markup(start())
    for clue_id in CASE["clues"]:
        assert f'data-act="clue:{clue_id}"' in markup


def test_locked_and_unopened_clues_show_no_picture_or_text():
    game = Engine().new_game(seed=1, variant="A")
    markup = board_markup(start(game=game))
    for clue_id in CASE["clues"]:
        picture = board.find_picture("clues", clue_id)
        if picture:
            assert picture not in markup  # nothing is opened yet
    for item in Engine().clue_list(game):
        text = Engine().case["clues"][item["id"]].get("text", "")
        assert text[:40] not in markup


def test_an_opened_clue_shows_its_picture_on_its_card_and_pin():
    game = Engine().new_game(seed=1, variant="A")
    Engine().open_clue(game, "D1")
    markup = board_markup(start(game=game))
    assert markup.count(board.find_picture("clues", "D1")) == 1  # the card
    assert board.find_picture("clues", "L3") not in markup


def test_the_detective_walks_to_the_last_place_searched():
    game = Engine().new_game(seed=1, variant="A")
    assert board.detective_spot(game.opened) == board.GATE
    Engine().open_clue(game, "L4")
    assert board.detective_spot(game.opened) == board.MAP_PINS["L4"][:2]


# ---- Opening clues ---------------------------------------------------------------------


def test_tapping_a_ready_card_offers_to_open_it_and_opening_moves_the_clock():
    at = start(focus=("clue", "D1"))
    assert "🔍 Open it · 30 min" in labels(at)
    click(at, "🔍 Open it")
    assert at.session_state["game"]["clock"] == CASE["clock"]["clue_cost"]
    assert "D1" in at.session_state["game"]["opened"]
    assert board_markup(at).count("00:30") == 1


def test_a_place_is_searched_not_opened():
    at = start(focus=("clue", "L4"))
    assert "🔍 Search it · 30 min" in labels(at)


def test_a_locked_clue_cannot_be_opened_but_can_be_hinted():
    at = start(focus=("clue", "D2"))
    assert not any(label.startswith("🔍") for label in labels(at))
    click(at, "💡 Hint")
    assert at.session_state["game"]["clock"] == Engine().hint_cost()
    assert any("Open D1" in i.value for i in at.info)


def test_an_opened_clue_shows_its_text_and_picture_in_the_panel():
    game = Engine().new_game(seed=1, variant="A")
    Engine().open_clue(game, "D1")
    at = start(game=game, focus=("clue", "D1"))
    clue = Engine().read_clue(game, "D1")
    assert clue["text"][:40] in page(at).replace("&quot;", '"').replace("&#x27;", "'")
    assert board.find_picture("clues", "D1") in page(at)


def test_opening_an_unlocking_clue_pops_up_a_toast():
    at = start(focus=("clue", "L4"))
    click(at, "🔍 Search it")
    assert any("New clue unlocked" in t.value for t in at.toast)


def test_actions_are_saved():
    at = AppTest.from_file(APP, default_timeout=15)
    at.session_state["intro_done"] = True
    at.session_state["focus"] = ("clue", "D1")
    at.run()
    game_id = at.query_params["game"]
    click(at, "🔍 Open it")
    assert db.load_game(game_id).clock == 30


# ---- Interrogation ---------------------------------------------------------------------


def test_tapping_a_suspect_opens_their_interrogation_for_free():
    at = start(focus=("suspect", "professor"), suspect="professor")
    assert "The Professor" in page(at)
    assert "Interrogation" in page(at)
    assert at.session_state["game"]["clock"] == 0


def test_tapping_a_question_asks_it_and_keeps_the_chat():
    at = start(focus=("suspect", "professor"), suspect="professor")
    at.pills(key="ask_topic").set_value("exam").run()
    assert not at.exception
    chat = at.session_state["chats"]["professor"]
    assert [e["who"] for e in chat] == ["you", "them"]
    assert chat[0]["text"] == "What do you know about tomorrow's exam?"
    assert at.session_state["game"]["clock"] == CASE["clock"]["question_cost"]
    assert at.pills(key="ask_topic").value is None  # cleared, so it can be tapped again
    assert 'class="bubble you"' in page(at) and 'class="bubble them"' in page(at)


def test_chats_are_kept_per_suspect():
    at = start(focus=("suspect", "professor"), suspect="professor")
    at.pills(key="ask_topic").set_value("alibi").run()
    at.session_state["focus"] = ("suspect", "companion")
    at.run()
    assert "companion" not in at.session_state["chats"]
    assert "Ask The Companion something" in page(at)


def test_only_opened_cards_can_be_shown_to_a_suspect():
    at = start(focus=("suspect", "companion"), suspect="companion")
    assert not any(p.key == "show_clue" for p in at.get("button_group"))
    game = Engine().new_game(seed=1, variant="A")
    Engine().open_clue(game, "L4")
    at = start(game=game, focus=("suspect", "companion"), suspect="companion")
    assert at.pills(key="show_clue").options == ["L4"]


def test_showing_the_breaking_card_stamps_caught_lying():
    game = Engine().new_game(seed=1, variant="A")
    Engine().open_clue(game, "L4")
    at = start(game=game, focus=("suspect", "companion"), suspect="companion")
    at.pills(key="show_clue").set_value("L4").run()
    assert not at.exception
    assert "Caught lying" in page(at)
    assert len(at.session_state["game"]["contradictions"]) == 1
    assert "⚡1" in suspect_markup(at)


def test_suspect_cards_show_questioned_and_ruled_out():
    at = start(focus=("suspect", "ta"), suspect="ta", sheet_who=["exchange"])
    row = suspect_markup(at)
    assert row.count("<button class=\"sus") == len(SUSPECTS)
    assert row.count("RULED OUT") == 1
    assert "✓" not in row
    at.pills(key="ask_topic").set_value("work").run()
    assert suspect_markup(at).count('class="tick"') == 1


def test_nerves_rise_when_shown_evidence():
    game = Engine().new_game(seed=1, variant="A")
    Engine().open_clue(game, "L4")
    at = start(game=game, focus=("suspect", "companion"), suspect="companion")
    assert "width:10%" in page(at)
    at.pills(key="show_clue").set_value("L4").run()
    assert "width:60%" in page(at)


# ---- Case sheet and accusation -----------------------------------------------------------


def test_case_sheet_lists_every_option_and_never_changes_the_game():
    at = start(focus=("sheet", None))
    before = dict(at.session_state["game"])
    for column in ("who", "how", "where", "why"):
        assert len(at.pills(key=f"sheet_{column}").options) == len(CASE["accusation"][column])
    at.pills(key="sheet_who").set_value(["professor"]).run()
    assert at.session_state["game"] == before
    assert "RULED OUT" in suspect_markup(at)


def pick(at, **choice):
    for column, value in choice.items():
        at.pills(key=f"accuse_{column}").set_value(value)


def test_accusation_options_start_empty():
    at = start(focus=("accuse", None))
    for column in ("who", "how", "where", "why"):
        assert at.pills(key=f"accuse_{column}").value is None


def test_accusing_with_a_part_missing_is_refused_for_free():
    at = start(focus=("accuse", None))
    answer = solution()
    del answer["why"]
    pick(at, **answer)
    click(at, "⚖️ Accuse")
    assert any("Missing: why" in w.value for w in at.warning)
    assert at.session_state["game"]["strikes"] == 0


def test_a_wrong_accusation_shows_which_parts_are_right():
    at = start(focus=("accuse", None))
    pick(at, **{**solution(), "who": "exchange"})
    click(at, "⚖️ Accuse")
    assert at.session_state["game"]["strikes"] == 1
    assert at.session_state["verdict"] == ["how", "where", "why"]
    assert page(at).count('class="ok"') == 3 and page(at).count('class="no"') == 1
    assert any("3 of 4 right" in t.value for t in at.toast)


def test_the_right_accusation_closes_the_case_with_the_reveal():
    at = start(focus=("accuse", None))
    pick(at, **solution())
    click(at, "⚖️ Accuse")
    assert at.session_state["game"]["status"] == "solved"
    assert "GUILTY" in page(at) and "Case closed" in page(at)
    assert board.find_picture("suspects", solution()["who"]) in page(at)
    assert not at.get("bidi_component")  # the board is gone
    assert any(e.label.startswith("📜") for e in at.expander)


def test_a_cold_case_names_the_culprit():
    game = Engine().new_game(seed=1, variant="B")
    game.status = "cold"
    at = start(game=game)
    assert "CASE COLD" in page(at)
    assert "It was The Teaching Assistant all along." in page(at)


def test_new_case_after_the_reveal_starts_over_and_clears_notes():
    game = Engine().new_game(seed=1, variant="A")
    game.status = "cold"
    at = start(game=game, sheet_who=["ta"])
    click(at, "🔁 Play a new case")
    assert at.session_state["game"]["status"] == "playing"
    assert "sheet_who" not in at.session_state


# ---- Start screen and saved games ---------------------------------------------------------


def test_a_new_case_opens_with_the_story_rules_and_detectives():
    at = start(intro_done=None)
    assert "🔍 Start the investigation" in labels(at)
    assert "Semiconductor Valuation" in page(at)
    assert "Play as her" in labels(at) and "Play as him" in labels(at)
    click(at, "Play as him")
    assert at.session_state["player_avatar"] == "he"
    click(at, "🔍 Start the investigation")
    assert "🔍 Start the investigation" not in labels(at)


def test_a_resumed_game_skips_the_intro_and_keeps_its_clock():
    game = Engine().new_game(seed=4, variant="B")
    Engine().open_clue(game, "D1")
    game_id = db.create_game(game)
    at = AppTest.from_file(APP, default_timeout=15)
    at.query_params["game"] = game_id
    at.run()
    assert not at.exception
    assert "🔍 Start the investigation" not in labels(at)
    assert "00:30" in board_markup(at)


def test_unknown_resume_link_starts_a_new_case_with_a_warning():
    at = AppTest.from_file(APP, default_timeout=15)
    at.query_params["game"] = "x" * 32
    at.run()
    assert not at.exception
    assert any("not found" in w.value for w in at.warning)


def test_the_intro_names_the_game_and_can_be_opened_again():
    at = start(intro_done=None)
    assert CASE["title"] in page(at)
    at = start(intro_done=True)
    assert "🔍 Start the investigation" not in labels(at)
    assert 'data-act="intro"' in board_markup(at)


def test_the_intro_shows_the_cover():
    at = start(intro_done=None)
    assert board.data_uri(str(board.ASSETS / "cover.webp")) in page(at)


# ---- Leads and hints (from the difficulty work) ---------------------------------------------


def test_home_panel_shows_a_lead_after_the_print_log():
    game = Engine().new_game(seed=1, variant="A")
    Engine().open_clue(game, "D1")
    Engine().open_clue(game, "D2")
    at = start(game=game)
    assert "Show D2. Print server log to the Teaching Assistant." in page(at)


def test_a_bought_hint_also_shows_in_the_home_panel():
    at = start(focus=("clue", "D3"))
    click(at, "💡 Hint")
    at.session_state["focus"] = ("home", None)
    at.run()
    assert "Ask the Professor about the exam." in page(at)


def test_no_hint_button_on_a_ready_clue():
    at = start(focus=("clue", "D1"))
    assert not any(label.startswith("💡") for label in labels(at))


# ---- Typed questions to the AI ----------------------------------------------------------------


def test_a_typed_question_works_without_a_key(monkeypatch, tmp_path):
    from game import ai

    monkeypatch.delenv("REQUESTY_API_KEY", raising=False)
    monkeypatch.setattr(ai, "ENV_FILE", tmp_path / ".env")

    def unexpected_request(*args):
        pytest.fail("The interface test attempted a live model request")

    monkeypatch.setattr(ai, "_requesty_answer", unexpected_request)
    at = AppTest.from_file(APP, default_timeout=15)
    at.session_state["game"] = Engine().new_game(seed=1, variant="A").to_dict()
    at.session_state["intro_done"] = True
    at.session_state["focus"] = ("suspect", "professor")
    at.session_state["suspect"] = "professor"
    at.secrets["REQUESTY_API_KEY"] = ""
    at.run()
    at.chat_input(key="typed").set_value("What is Question 5?").run()
    assert not at.exception
    assert at.session_state["game"]["clock"] == CASE["clock"]["question_cost"]
    chat = at.session_state["chats"]["professor"]
    assert chat[0]["text"] == "What is Question 5?"
    assert "yesterday" in chat[1]["text"]
    assert "Unlocked: D3" in page(at)


# ---- Evidence details -----------------------------------------------------------------------


def opened_game(*clue_ids, variant="A"):
    game = Engine().new_game(seed=1, variant=variant)
    for clue_id in clue_ids:
        Engine().open_clue(game, clue_id)
    return game


def test_log_search_shows_only_matching_lines_for_free():
    game = opened_game("D1", "D2")
    log = Engine().read_clue(game, "D2")["log"].splitlines()
    word = log[0].split()[0]
    at = start(game=game, focus=("clue", "D2"))
    at.text_input(key="search_D2").set_value(word.upper()).run()
    shown = at.code[0].value.splitlines()
    assert shown == [line for line in log if word.lower() in line.lower()]
    assert at.session_state["game"]["clock"] == game.clock


def test_d4_shows_the_payoff_chart():
    at = start(game=opened_game("D4"), focus=("clue", "D4"))
    assert len(at.get("vega_lite_chart")) == 1


def test_a_cold_case_also_offers_the_confrontation():
    game = Engine().new_game(seed=1, variant="C")
    game.status = "cold"
    at = start(game=game)
    scene = next(e for e in at.expander if e.label.startswith("📜"))
    assert scene.markdown


def test_an_irrelevant_card_catches_no_one():
    at = start(game=opened_game("D1"), focus=("suspect", "exchange"), suspect="exchange")
    at.pills(key="show_clue").set_value("D1").run()
    assert "Caught lying" not in page(at)
    assert at.session_state["game"]["contradictions"] == []


def test_showing_the_same_card_again_does_not_catch_twice():
    at = start(game=opened_game("L4"), focus=("suspect", "companion"), suspect="companion")
    at.pills(key="show_clue").set_value("L4").run()
    at.pills(key="show_clue").set_value("L4").run()
    assert not at.exception
    assert page(at).count("Caught lying") == 1
    assert len(at.session_state["game"]["contradictions"]) == 1
