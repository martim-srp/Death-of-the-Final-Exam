"""Tests for badges and the Companion's password trap."""

import pytest

from game.engine import Engine, looks_like_secret


@pytest.fixture(scope="module")
def engine():
    return Engine()


# ---- What counts as a secret ---------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "my password is hunter2",
        "Password: Lisboa2026",
        "a minha senha é benfica99",
        "sure, it's Carcavelos2026!",
        "here: sk-abc123def456ghi789",
        "ghp_1234567890abcdefXYZ",
        "pwd=qwerty12",
    ],
)
def test_passwords_and_keys_are_caught(text):
    assert looks_like_secret(text)


@pytest.mark.parametrize(
    "text",
    [
        "Where were you at 18:52?",
        "Card STU-2291 entered the library at 18:31.",
        "What about staff-0417?",
        "I am not giving you my password.",
        "Tell me about Project Lantern",
        "",
    ],
)
def test_ordinary_questions_are_not_secrets(text):
    assert not looks_like_secret(text)


# ---- The password trap -----------------------------------------------------------------


def test_giving_the_companion_a_password_earns_the_badge(engine):
    game = engine.new_game(seed=1, variant="A")
    assert engine.check_secret(game, "companion", "ok, it's Carcavelos2026") is True
    assert [b["id"] for b in engine.badge_list(game)] == ["spy_password"]


def test_password_to_another_suspect_is_blocked_but_earns_nothing(engine):
    game = engine.new_game(seed=1, variant="A")
    assert engine.check_secret(game, "professor", "my password is hunter2") is True
    assert game.badges == []


def test_ordinary_question_is_not_blocked(engine):
    game = engine.new_game(seed=1, variant="A")
    assert engine.check_secret(game, "companion", "Where were you at nine?") is False
    assert game.badges == []


def test_badge_is_awarded_once(engine):
    game = engine.new_game(seed=1, variant="A")
    engine.check_secret(game, "companion", "password: hunter22")
    engine.check_secret(game, "companion", "password: hunter33")
    assert game.badges == ["spy_password"]


# ---- Honey trap and hedge fund ----------------------------------------------------------


def test_showing_the_clipping_to_the_professor_earns_honey_trap(engine):
    game = engine.new_game(seed=1, variant="A")
    engine.ask(game, "companion", "work")
    engine.open_clue(game, "D8")
    engine.present(game, "companion", "D8")
    assert game.badges == []
    engine.present(game, "professor", "D8")
    assert game.badges == ["honey_trap"]


@pytest.mark.parametrize("variant", ["A", "B", "C"])
def test_fast_solve_earns_hedge_fund(engine, variant):
    game = engine.new_game(seed=1, variant=variant)
    for step in engine.case["variants"][variant]["shortest_path"]:
        getattr(engine, {"open": "open_clue", "ask": "ask", "present": "present"}[step[0]])(game, *step[1:])
    s = engine.case["variants"][variant]["solution"]
    engine.accuse(game, s["who"], s["how"], s["where"], s["why"])
    assert "hedge_fund" in game.badges


def test_slow_solve_earns_no_hedge_fund(engine):
    game = engine.new_game(seed=1, variant="A")
    game.clock = 300
    s = engine.case["variants"]["A"]["solution"]
    engine.accuse(game, s["who"], s["how"], s["where"], s["why"])
    assert game.status == "solved"
    assert "hedge_fund" not in game.badges


# ---- Game data is never a secret (false positives reported in the review of #7) ----------


@pytest.mark.parametrize(
    "text",
    [
        "Did you post SV_Final_v3.pdf?",
        "What is job=88213?",
        "Was card=STU-2291 yours?",
        "Why was staff=STAFF-0417 at LIB-1?",
        "Who has the file report_final2.docx?",
    ],
)
def test_game_data_in_a_question_is_not_a_secret(engine, text):
    game = engine.new_game(seed=1, variant="A")
    assert engine.check_secret(game, "companion", text) is False
    assert game.badges == []


@pytest.mark.parametrize("variant", ["A", "B", "C"])
def test_no_word_from_any_clue_or_log_counts_as_a_secret(engine, variant):
    """Players copy words from clues into their questions. None of them may trip the trap."""
    for seed in range(20):
        game = engine.new_game(seed=seed, variant=variant)
        for clue_id in engine.case["clues"]:
            game.opened.append(clue_id)
        for clue_id in engine.case["clues"]:
            clue = engine.read_clue(game, clue_id)
            for key in ("text", "log", "hidden_text"):
                if clue[key]:
                    for line in clue[key].splitlines():
                        assert not engine.check_secret(game, "companion", line), line


def test_a_real_password_mixed_with_game_data_is_still_caught(engine):
    game = engine.new_game(seed=1, variant="A")
    assert engine.check_secret(game, "companion", "card=STU-2291, and my login is Carcavelos2026")
    assert game.badges == ["spy_password"]
