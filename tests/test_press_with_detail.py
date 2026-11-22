"""Typed questions matter: quoting a card's detail presses a suspect, and the AI reacts to the evidence.

Engine.press catches a lie when a typed question quotes a detail (data/hunches.json "press")
of an opened card that breaks that suspect's story, as if the card were shown, with extra
nerves. Engine.character_brief tells the AI which cards were shown, which lies were caught
and how rattled the suspect is. Tests use fake completions only.
"""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from game import ai
from game.case import load_case, load_hunches
from game.engine import NERVES_PER_PRESS, Engine, Game

APP = str(Path(__file__).resolve().parents[1] / "app.py")
CASE = load_case()
HUNCHES = load_hunches()
VARIANTS = sorted(CASE["variants"])
GOOD = '{"reply": "That proves nothing.", "topic": "alibi"}'


@pytest.fixture
def no_key(monkeypatch, tmp_path):
    monkeypatch.delenv("REQUESTY_API_KEY", raising=False)
    monkeypatch.setattr(ai, "ENV_FILE", tmp_path / ".env")


def game_with(variant, *clues, seed=1):
    engine = Engine()
    game = engine.new_game(seed=seed, variant=variant)
    game.opened.extend(clues)
    return engine, game


def broken_stories(engine, game):
    """Every (suspect, claim, clue) where the clue breaks the claim in this variant."""
    return [
        (suspect, claim, clue)
        for suspect, data in engine._suspects(game).items()
        for claim in data.get("claims", [])
        for clue in claim["broken_by"]
    ]


# ---- The data -----------------------------------------------------------------------


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_broken_story_can_be_pressed_with_a_detail_on_its_card(variant):
    engine, game = game_with(variant)
    for suspect, claim, clue_id in broken_stories(engine, game):
        details = HUNCHES[f"{clue_id}|{suspect}.{claim['id']}"].get("press")
        assert details, f"{clue_id}|{suspect}.{claim['id']} has no press details"
        clue = engine._clues(game)[clue_id]
        text = " ".join(engine._fill(game, clue.get(k) or "") for k in ("title", "text", "log")).casefold()
        for detail in details:
            assert engine._fill(game, detail).casefold() in text, (variant, clue_id, detail)


def test_press_details_are_never_common_words():
    """A detail must be specific to its card, so an ordinary question never presses by accident."""
    for key, hunch in HUNCHES.items():
        for detail in hunch.get("press", []):
            assert len(detail) >= 4 or detail.startswith("{"), (key, detail)
            assert detail.casefold() not in {"alibi", "exam", "report", "work", "leak", "where were you"}


# ---- The rule -----------------------------------------------------------------------


def test_quoting_a_detail_catches_the_lie_like_showing_the_card():
    engine, game = game_with("A", "D1", "D2", "L1")
    card = game.variables["rep_card"]
    result = engine.press(game, "class_rep", f"Why did card {card} enter the library?")
    assert result["clue"] == "L1"
    assert [c["claim"] for c in result["contradictions"]] == ["home_all_evening"]
    assert ["class_rep", "home_all_evening"] in game.contradictions
    assert ["class_rep", "L1"] in game.presented
    assert result["reveal"] == engine.character_brief(game, "class_rep")["earned_reveals"]["L1"]
    assert game.history[-1]["action"] == "press"


def test_pressing_rattles_more_than_showing_the_card():
    engine, shown = game_with("A", "D1", "D2", "L1")
    engine.present(shown, "class_rep", "L1")
    _, pressed = game_with("A", "D1", "D2", "L1")
    engine.press(pressed, "class_rep", "You were at the library gate at 18:31.")
    assert engine.nerves(pressed, "class_rep") == engine.nerves(shown, "class_rep") + NERVES_PER_PRESS


def test_pressing_is_free_the_question_pays():
    engine, game = game_with("A", "D1", "D2", "L1")
    clock = game.clock
    engine.press(game, "class_rep", "18:31?")
    assert game.clock == clock


def test_a_detail_from_an_unopened_card_does_nothing():
    engine, game = game_with("A", "D1", "D2")
    assert engine.press(game, "class_rep", "You were at the library at 18:31.") is None
    assert game.contradictions == []


def test_a_question_without_a_detail_does_nothing():
    engine, game = game_with("A", "D1", "D2", "L1")
    assert engine.press(game, "class_rep", "Where were you last night?") is None
    assert game.history == []


def test_a_detail_must_be_whole():
    engine, game = game_with("A", "D1", "D2", "L1")
    assert engine.press(game, "class_rep", "Was it 118:315 or so?") is None
    assert engine.press(game, "ta", "Job 882130?") is None


def test_the_detail_must_break_this_suspects_story():
    engine, game = game_with("A", "D1", "D2", "L1")
    assert engine.press(game, "professor", "Someone was at the library at 18:31.") is None


def test_a_lie_is_pressed_only_once():
    engine, game = game_with("A", "D1", "D2", "L1")
    engine.press(game, "class_rep", "18:31")
    assert engine.press(game, "class_rep", "18:31 again") is None
    assert game.pressed == [["class_rep", "L1"]]


def test_pressing_works_on_an_innocent_too():
    """The same rule for every story, so a caught lie never points at the culprit."""
    engine, game = game_with("A", "L4")  # the culprit in A is the Class Representative
    result = engine.press(game, "companion", "The Cleaner saw you trying the handle.")
    assert result["contradictions"][0]["claim"] == "never_went_to_office_door"


def test_pressing_can_unlock_like_showing():
    engine, game = game_with("A", "D1", "D2")
    result = engine.press(game, "ta", "Who released job 88213?")
    assert result["unlocked"] == ["L2"]


def test_pressed_survives_a_resume_link():
    engine, game = game_with("A", "D1", "D2", "L1")
    engine.press(game, "class_rep", "18:31")
    resumed = Game.from_dict(json.loads(json.dumps(game.to_dict())))
    assert resumed.pressed == [["class_rep", "L1"]]
    assert engine.nerves(resumed, "class_rep") == engine.nerves(game, "class_rep")


def test_an_old_save_without_pressed_still_loads():
    engine, game = game_with("A")
    data = game.to_dict()
    del data["pressed"]
    assert Game.from_dict(data).pressed == []


# ---- Through game/ai.py ------------------------------------------------------------


def test_a_typed_question_with_a_detail_catches_the_lie():
    engine, game = game_with("A", "D1", "D2", "L1")
    clock = game.clock
    answer = ai.ask(engine, game, "class_rep", "Your card was at the library at 18:31.", complete=lambda *_: GOOD)
    assert answer["reply"] == "That proves nothing."
    assert answer["pressed"] == "L1"
    assert answer["contradictions"][0]["claim"] == "home_all_evening"
    assert game.clock == clock + CASE["clock"]["question_cost"]  # one question, not two
    assert game.history[-1]["action"] == "ask" and game.history[-1]["ai_call"]


def test_without_the_ai_the_suspect_gives_their_reaction_to_the_card(no_key):
    engine, game = game_with("A", "D1", "D2", "L1")
    answer = ai.ask(engine, game, "class_rep", "What about 18:31?")
    assert answer["reply"] == engine.character_brief(game, "class_rep")["earned_reveals"]["L1"]


def test_the_ai_is_told_it_was_caught_out():
    engine, game = game_with("A", "D1", "D2", "L1")
    prompts = []
    ai.ask(engine, game, "class_rep", "18:31?", complete=lambda prompt, _text: prompts.append(prompt) or GOOD)
    assert "just caught you out" in prompts[0]
    assert "I was in my room at the residence all evening." in prompts[0]
    prompts.clear()
    ai.ask(engine, game, "class_rep", "Anything else?", complete=lambda prompt, _text: prompts.append(prompt) or GOOD)
    assert "just caught you out" not in prompts[0]


def test_a_password_is_never_pressed():
    engine, game = game_with("C", "L4")
    answer = ai.ask(engine, game, "companion", "my password is handle1940", complete=lambda *_: GOOD)
    assert answer["blocked"] and "pressed" not in answer
    assert game.contradictions == []


# ---- What the AI is told ------------------------------------------------------------


def test_the_brief_tells_the_ai_about_the_interrogation():
    engine, game = game_with("A", "D1", "D2", "L1")
    assert engine.character_brief(game, "class_rep")["composure"] == "calm"
    engine.present(game, "class_rep", "L1")
    brief = engine.character_brief(game, "class_rep")
    assert brief["evidence_shown"] == ["Library gate log"]
    assert brief["lies_caught"] == ["I was in my room at the residence all evening."]
    assert brief["composure"] == "rattled"
    assert engine.character_brief(game, "ta")["evidence_shown"] == []


@pytest.mark.parametrize("variant", VARIANTS)
def test_the_brief_never_holds_a_cards_text(variant):
    engine = Engine()
    game = engine.new_game(seed=3, variant=variant)
    game.opened.extend(CASE["clues"])
    for suspect in CASE["suspects"]:
        for clue_id in CASE["clues"]:
            game.clock = 0  # enough time to show every card
            engine.present(game, suspect, clue_id)
    for suspect in CASE["suspects"]:
        brief = json.dumps(engine.character_brief(game, suspect), ensure_ascii=False)
        for clue_id in CASE["clues"]:
            card = engine.read_clue(game, clue_id)
            for line in (card["log"] or "").splitlines() + [card["hidden_text"] or ""]:
                if line.strip():
                    assert line.strip() not in brief, (suspect, clue_id)


def test_the_prompt_passes_the_new_fields():
    engine, game = game_with("A", "D1", "D2", "L1")
    engine.present(game, "class_rep", "L1")
    prompt = ai.system_prompt(engine.character_brief(game, "class_rep"), CASE["topics"])
    for key in ("evidence_shown", "lies_caught", "composure", "Library gate log", "rattled"):
        assert key in prompt


# ---- What the player sees ------------------------------------------------------------


def test_the_player_sees_the_lie_caught_in_the_chat(no_key, monkeypatch):
    monkeypatch.setattr(ai, "_requesty_answer", lambda *_: pytest.fail("no live model calls in tests"))
    engine, game = game_with("A", "D1", "D2", "L1")
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = game.to_dict()
    at.session_state["intro_done"] = True
    at.session_state["focus"] = ("suspect", "class_rep")
    at.session_state["suspect"] = "class_rep"
    at.secrets["REQUESTY_API_KEY"] = ""
    at.run()
    at.chat_input(key="typed").set_value("Why was your card at the library at 18:31?").run()
    assert not at.exception
    chat = "\n".join(m.value for m in at.markdown if 'class="chat"' in m.value)
    assert "Caught lying" in chat
    assert "You press them with a detail from Evidence" in chat
