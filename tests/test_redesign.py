"""The easier-to-play layout: start screen, tap-to-talk portraits, chat, case board, status bar."""

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from game.case import load_case
from game.engine import Engine

APP = str(Path(__file__).resolve().parent.parent / "app.py")
CASE = load_case()


def start(variant="A", seed=1, intro_done=None, game=None):
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = (game or Engine().new_game(seed=seed, variant=variant)).to_dict()
    if intro_done is not None:
        at.session_state["intro_done"] = intro_done
    at.run()
    assert not at.exception
    return at


def click(at, starts_with):
    next(b for b in at.button if b.label.startswith(starts_with)).click().run()
    assert not at.exception


def page(at):
    return "\n".join(m.value for m in at.markdown)


def labels(at):
    return [b.label for b in at.button]


# ---- Start screen ------------------------------------------------------------------


def test_a_new_case_opens_with_the_story_and_rules():
    at = start()
    assert "Start the investigation" in labels(at)
    assert "How to play" in page(at)
    assert "Semiconductor Valuation" in page(at)


def test_starting_closes_the_intro_and_keeps_name_and_avatar():
    at = start()
    at.text_input(key="player_name").set_value("Martim")
    click(at, "Start the investigation")
    assert "Start the investigation" not in labels(at)
    assert "Martim" in page(at)  # shown in the status bar


def test_a_resumed_game_skips_the_intro():
    game = Engine().new_game(seed=1, variant="A")
    Engine().open_clue(game, "D1")
    at = start(game=game)
    assert "Start the investigation" not in labels(at)


def test_the_intro_can_be_opened_again():
    at = start(intro_done=True)
    click(at, "📖 Story and how to play")
    assert "Start the investigation" in labels(at)


# ---- Status bar --------------------------------------------------------------------


def test_status_bar_shows_time_left_and_accusations():
    at = start(intro_done=True)
    hud = next(m.value for m in at.markdown if 'class="hud"' in m.value)
    assert "9h 00m" in hud
    assert f"{CASE['max_strikes']}" in hud
    click(at, "Open 📄 D1")
    hud = next(m.value for m in at.markdown if 'class="hud"' in m.value)
    assert "8h 30m" in hud


# ---- Tap a portrait to talk -----------------------------------------------------------


def test_tapping_a_portrait_opens_questioning_for_that_suspect():
    at = start(intro_done=True)
    click(at, "Talk to The Professor")
    assert at.session_state["suspect"] == "professor"
    assert at.session_state["view"] == "🗣️ Question suspects"
    assert at.selectbox(key="suspect").value == "professor"
    assert at.session_state["game"]["clock"] == 0  # opening the chat is free


def test_chat_keeps_the_question_and_the_answer():
    at = start(intro_done=True)
    click(at, "Talk to The Professor")
    at.selectbox[1].set_value("alibi").run()
    click(at, "Ask (")
    chat = at.session_state["chats"]["professor"]
    assert [entry["who"] for entry in chat] == ["you", "them"]
    assert chat[0]["text"] == "Where were you last night?"
    click(at, "Ask (")
    assert len(at.session_state["chats"]["professor"]) == 4  # older lines stay


def test_chat_is_kept_per_suspect():
    at = start(intro_done=True)
    click(at, "Talk to The Professor")
    click(at, "Ask (")
    click(at, "Talk to The Companion")
    assert "companion" not in at.session_state["chats"]
    assert any("Ask The Companion anything" in c.value for c in at.caption)


def test_show_clue_list_uses_titles():
    at = start(intro_done=True)
    click(at, "Open 📍 L4")
    options = at.selectbox[2].options
    assert options == ["L4. The faculty corridor"]


def test_an_unlock_pops_up_with_the_clue_title():
    game = Engine().new_game(seed=1, variant="A")
    before = {c["id"] for c in Engine().clue_list(game) if c["state"] == "locked"}
    Engine().open_clue(game, "L4")
    newly = [c for c in Engine().clue_list(game) if c["id"] in before and c["state"] != "locked"]
    assert newly, "opening L4 should unlock a clue in this case"
    at = start(intro_done=True)
    click(at, "Open 📍 L4")
    toasts = "\n".join(t.value for t in at.toast)
    assert f"{newly[0]['id']}. {newly[0]['title']}" in toasts


# ---- Case file ---------------------------------------------------------------------


def test_locked_clues_are_grouped_away_from_the_ready_ones():
    at = start(intro_done=True)
    locked = next(e for e in at.expander if e.label.startswith("🔒 Locked"))
    assert "D2. Print server log" in "\n".join(m.value for m in locked.markdown)
    assert "Ready to open" in page(at)


# ---- Case board --------------------------------------------------------------------


def test_case_board_lists_every_accusation_option():
    at = start(intro_done=True)
    for column in ("who", "how", "where", "why"):
        for option in CASE["accusation"][column]:
            assert at.checkbox(key=f"board_{column}_{option['id']}") is not None


def test_crossing_off_a_suspect_stamps_their_card_and_leaves_the_game_alone():
    at = start(intro_done=True)
    before = dict(at.session_state["game"])
    at.checkbox(key="board_who_professor").check().run()
    assert not at.exception
    assert page(at).count("RULED OUT") == 1
    assert "4 left" in page(at)
    assert at.session_state["game"] == before
    assert "The Professor · ruled out" in at.radio(key="accuse_who").options


def test_new_case_clears_the_case_board():
    at = start(intro_done=True)
    first = CASE["accusation"]["where"][0]["id"]
    at.checkbox(key=f"board_where_{first}").check().run()
    assert at.checkbox(key=f"board_where_{first}").value
    click(at, "New case")
    assert not any(c.value for c in at.checkbox if c.key and c.key.startswith("board_"))


# ---- Map ---------------------------------------------------------------------------


def test_chiado_is_on_the_map_with_nothing_to_search():
    at = start(intro_done=True)
    (component,) = at.get("bidi_component")
    markup = json.loads(component.proto.json)
    assert 'data-spot="chiado"' in markup
    assert markup.count("data-place=") == 4  # still one clickable pin per location clue


def test_tapping_chiado_shows_a_neutral_note():
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = Engine().new_game(seed=1, variant="A").to_dict()
    at.session_state["intro_done"] = True
    at.session_state["map_spot"] = "chiado"
    at.run()
    assert not at.exception
    assert "Nothing to search here tonight" in page(at)
    assert at.session_state["game"]["clock"] == 0
