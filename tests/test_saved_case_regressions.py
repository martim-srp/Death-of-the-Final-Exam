import json
from html import escape

import db
from game.case import load_cracks
from game.engine import Engine
from tests.test_board_game import page, start
from tests.test_invalid_input import open_app, store_raw
from tests.test_nerves_crack import all_open, push_to_the_edge


def test_overlapping_actions_cannot_overwrite_saved_progress(monkeypatch):
    engine = Engine()
    game = engine.new_game(variant="A")
    game_id = db.create_game(game)
    app = start(game=game, game_id=game_id, focus=("clue", "D4"))
    save = db.save_game

    def save_after_another_tab(game_id, game, *, expected_state):
        other = db.load_game(game_id)
        engine.open_clue(other, "D1")
        assert save(game_id, other, expected_state=expected_state)
        return save(game_id, game, expected_state=expected_state)

    monkeypatch.setattr(db, "save_game", save_after_another_tab)
    app.button(key="open_D4").click().run()
    assert not app.exception
    assert db.load_game(game_id).opened == ["D1"]
    assert app.session_state["game"]["opened"] == ["D1"]
    assert any("Your last action was not saved" in toast.value for toast in app.toast)


def test_damaged_clock_starts_a_new_case():
    game = Engine().new_game(variant="A").to_dict()
    game["clock"] = None
    game_id = "d" * 32
    store_raw(game_id, json.dumps(game))
    assert db.load_game(game_id) is None
    app = open_app(query=game_id)
    assert not app.exception
    assert app.session_state["game_id"] != game_id


def test_interrogation_dialogue_survives_resuming_in_another_session():
    game = all_open("C")
    suspect = "professor"
    last = push_to_the_edge(Engine(), game, suspect)
    game_id = db.create_game(game)
    app = start(game=game, game_id=game_id, focus=("suspect", suspect), suspect=suspect)
    app.pills(key="ask_topic").set_value("exam").run()
    app.pills(key="show_clue").set_value(last).run()
    assert not app.exception
    resumed = start(game=db.load_game(game_id), game_id=game_id, focus=("suspect", suspect), suspect=suspect)
    assert "What do you know about tomorrow" in page(resumed)
    assert escape(load_cracks()["variants"]["C"][suspect]) in page(resumed)


def test_typed_question_and_model_echo_stay_out_of_the_save(monkeypatch):
    from game import ai

    question = "Was the paper sealed in the blue envelope?"
    monkeypatch.setenv("REQUESTY_API_KEY", "fake-test-key")
    monkeypatch.setattr(ai, "_requesty_answer", lambda *_args: json.dumps({"topic": "exam", "reply": question}))
    game = Engine().new_game(variant="A")
    game_id = db.create_game(game)
    app = start(game=game, game_id=game_id, focus=("suspect", "professor"), suspect="professor")
    app.chat_input(key="typed").set_value(question).run()
    assert not app.exception
    assert [entry["text"] for entry in app.session_state["chats"]["professor"]] == [question, question]
    assert question not in json.dumps(db.load_game(game_id).to_dict())
