"""The README meets the submission rules and answers the repository walkthrough's questions.

The course requires the deployed URL, every member's name and student number, and the commands to run
the app and its tests. The teaching staff reviews the repository on its own, so the README also has to
say where the data is stored, what happens when the AI is down, and what the tests do and do not cover.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")


def section(title):
    """The text under a ## or ### heading, up to the next heading."""
    match = re.search(rf"^#{{2,3}} {re.escape(title)}\n(.*?)(?=^#{{2,3}} |\Z)", README, re.MULTILINE | re.DOTALL)
    assert match, f"README has no '{title}' section"
    return match.group(1)


def test_deployed_url():
    assert re.search(r"https://\S+\.streamlit\.app", README)


def test_every_member_has_a_name_and_student_number():
    rows = re.findall(r"^\| ([A-Z][^|]+?) \| (\d{5,}) \|$", section("Team"), re.MULTILINE)
    assert len(rows) >= 3


def test_run_and_test_commands():
    assert "streamlit run app.py" in section("Run it locally")
    assert "python -m pip install -r requirements.txt" in section("Run it locally")
    assert "python -m pytest" in section("Run the tests")


def test_answers_the_walkthrough_questions():
    assert "SQLite" in section("Where the data is stored")
    assert "scripted lines" in section("What happens when the AI is unavailable")
    assert "Not covered" in section("What the tests cover, and what they do not")


def test_every_file_the_readme_names_exists():
    named = set(re.findall(r"`([\w./-]+\.(?:py|json))`", README))
    # A bare name refers to the folder it lives in: tests/test_x.py, data/case.json.
    missing = [n for n in named if not any((ROOT / d / n).exists() for d in ("", "tests", "data"))]
    assert not missing, missing


def test_env_example_has_only_a_placeholder():
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"^REQUESTY_API_KEY=your-", example, re.MULTILINE)
    assert "rqsty-sk-" not in example and "sk-" not in example.replace("your-requesty-key-here", "")


def test_secret_files_are_ignored_but_the_example_is_not():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in ignored
    assert ".streamlit/secrets.toml" in ignored
    assert ".env.example" not in ignored
