"""The code must run on Python 3.11, the version in the dev container (.devcontainer).

Python 3.12 lets an f-string reuse its own quote inside a {...} expression
(f"{"a" if x else "b"}"). Python 3.11 rejects the whole file with a SyntaxError,
so the app would not even start there. These tests find that pattern with the
tokenizer, so they work on the 3.13 used by CI.
"""

import sys
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SOURCES = sorted(p for p in ROOT.rglob("*.py") if ".git" not in p.parts and "site-packages" not in p.parts)


def reused_quotes(path):
    """Lines where a string inside an f-string's {...} uses that f-string's own quote."""
    found = []
    stack = []  # the quote of each f-string we are inside
    with open(path, "rb") as f:
        for token in tokenize.tokenize(f.readline):
            name = tokenize.tok_name[token.type]
            if name == "FSTRING_START":
                if stack and stack[-1] in token.string:
                    found.append(token.start[0])
                stack.append(token.string.lstrip("rRfFbBuU"))
            elif name == "FSTRING_END":
                stack.pop()
            elif name == "STRING" and stack:
                quote = token.string.lstrip("rRbBuU")
                if quote.startswith(stack[-1]):
                    found.append(token.start[0])
    return found


@pytest.mark.skipif(sys.version_info < (3, 12), reason="the 3.12 tokenizer splits f-strings into parts")
@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_f_string_reuses_its_own_quote(path):
    assert reused_quotes(path) == []


@pytest.mark.skipif(sys.version_info < (3, 12), reason="the 3.12 tokenizer splits f-strings into parts")
def test_the_check_catches_the_3_12_only_pattern(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text('n = 1\ntext = f"{n} {"lie" if n == 1 else "lies"}"\n', encoding="utf-8")
    good = tmp_path / "good.py"
    good.write_text("n = 1\ntext = f\"{n} {'lie' if n == 1 else 'lies'}\"\n", encoding="utf-8")
    assert reused_quotes(bad) == [2, 2]
    assert reused_quotes(good) == []


def test_the_dev_container_is_python_3_11():
    """If the dev container moves to a newer Python, this file can be relaxed."""
    config = (ROOT / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8")
    assert "python:1-3.11" in config
