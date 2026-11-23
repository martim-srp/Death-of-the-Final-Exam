"""The README and AGENTS.md say what the game really does (fixes from an outside audit)."""

from pathlib import Path

from game.engine import Engine

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")


def test_the_docs_no_longer_say_you_must_accuse_before_0900():
    assert "accuse before\n09:00" not in README and "accuse before 09:00" not in README
    assert "accuses someone before 09:00" not in AGENTS
    assert "At 09:00 you can no longer search or ask, but you can still accuse." in README


def test_an_accusation_really_is_allowed_at_0900():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    game.clock = engine.clock_rules["limit_minutes"]
    result = engine.accuse(game, **engine.case["variants"]["A"]["solution"])
    assert result["correct"]


def test_every_member_has_their_main_work_in_both_team_tables():
    for name in ("Duarte", "Lúcia", "Martim", "Salvador"):
        row = next(line for line in README.splitlines() if line.startswith(f"| {name} |"))
        assert row.split("|")[2].strip(), row
    for login in ("@martim-srp", "@lucia123-456", "@Salvador-ai19", "@DuarteFurtado"):
        row = next(line for line in AGENTS.splitlines() if line.startswith(f"| {login} |"))
        assert row.split("|")[2].strip(), row
