"""The game's name comes from data/case.json and is used everywhere."""

from pathlib import Path


from game.case import load_case

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")
TITLE = load_case()["title"]


def test_the_game_is_called_death_of_the_final_exam():
    assert TITLE == "Death of the Final Exam"


def test_the_old_name_is_gone():
    for name in ("app.py", "README.md", "AGENTS.md", "data/case.json", "game/__init__.py"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "Carcavelos Paper" not in text, name
    assert (ROOT / "README.md").read_text(encoding="utf-8").startswith(f"# {TITLE}\n")
