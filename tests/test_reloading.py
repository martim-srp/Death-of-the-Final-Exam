"""The live server picks up new game code without a reboot (reloading.py).

The reload tests run in a separate Python process: reloading modules inside pytest
would swap the classes under the other test files.
"""

import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import reloading

ROOT = Path(__file__).resolve().parent.parent


def copy_sources(tmp_path):
    for name in reloading.SOURCES:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / name, target)
    return tmp_path


def test_version_is_stable_while_nothing_changes(tmp_path):
    root = copy_sources(tmp_path)
    assert reloading.source_version(root) == reloading.source_version(root)


def test_version_changes_when_any_source_changes(tmp_path):
    root = copy_sources(tmp_path)
    seen = {reloading.source_version(root)}
    for name in reloading.SOURCES:
        with open(root / name, "a", encoding="utf-8") as f:
            f.write("\n")
        seen.add(reloading.source_version(root))
    assert len(seen) == len(reloading.SOURCES) + 1


def test_the_story_file_is_watched():
    assert "data/case.json" in reloading.SOURCES
    assert "game/engine.py" in reloading.SOURCES


def run_isolated(code):
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_first_build_does_not_reload():
    out = run_isolated(
        """
        import sys; sys.path.insert(0, ".")
        import db, game.engine, reloading
        before = game.engine.Engine
        engine = reloading.build_engine("v1")
        print(type(engine) is before, game.engine.Engine is before)
        """
    )
    assert out.split() == ["True", "True"]


def test_a_new_version_rebuilds_with_matching_classes():
    """After an update, the Engine, db's Game and ai's GameError all come from the same code."""
    out = run_isolated(
        """
        import sys; sys.path.insert(0, ".")
        import db, game.ai, game.engine, reloading
        old_engine_class = game.engine.Engine
        reloading.build_engine("v1")
        engine = reloading.build_engine("v2")
        current = sys.modules["game.engine"]
        print(
            type(engine) is current.Engine,
            current.Engine is not old_engine_class,
            db.Game is current.Game,
            game.ai.GameError is current.GameError,
            hasattr(engine, "contradiction_list"),
        )
        """
    )
    assert out.split() == ["True"] * 5
