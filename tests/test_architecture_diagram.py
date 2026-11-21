"""The README's architecture diagram stays true to the repository."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")


def diagram():
    match = re.search(r"```mermaid\n(.*?)```", README, re.DOTALL)
    assert match, "README has no mermaid diagram"
    return match.group(1)


def test_readme_has_one_architecture_diagram():
    assert README.count("```mermaid") == 1
    assert diagram().startswith("flowchart")


def test_every_file_in_the_diagram_exists():
    files = set(re.findall(r"[\w/]+\.(?:py|json)", diagram()))
    assert files, "the diagram names no files"
    missing = [f for f in files if not (ROOT / f).exists()]
    assert not missing, missing


def test_diagram_shows_the_main_parts_and_the_fallback():
    text = diagram()
    for part in ("app.py", "game/engine.py", "game/ai.py", "db.py", "board.py", "data/case.json"):
        assert part in text, part
    assert "scripted lines" in text


def test_diagram_says_the_model_only_gets_the_brief():
    assert "character_brief only" in diagram()
