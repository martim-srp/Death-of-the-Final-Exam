"""Keep a long-running Streamlit server on the current game code.

Streamlit Cloud pulls new code from GitHub without restarting the process. Streamlit
re-imports the files that changed, but objects made earlier keep the old code: the
Engine the app caches, and the classes that db.py (Game) and game/ai.py (GameError)
imported. That is how the live site crashed after #20 with "'Engine' object has no
attribute 'contradiction_list'" until the app was rebooted.

app.py caches the engine under source_version(), so a change to the game code or the
case file builds a new Engine. build_engine() then reloads the modules that hold game
classes, so old and new code are never mixed.
"""

import hashlib
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Files whose change must rebuild the engine.
SOURCES = ("game/case.py", "game/engine.py", "game/ai.py", "db.py", "data/case.json", "data/hunches.json", "data/voice.json")

# Reloaded in this order: each one imports from the ones before it.
MODULES = ("game.case", "game.engine", "db", "game.ai")

_built = {"version": None}


def source_version(root=ROOT, sources=SOURCES):
    """A fingerprint of the game code and the case file. Changes when any of them changes."""
    digest = hashlib.sha256()
    for name in sources:
        path = Path(root) / name
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes() if path.exists() else b"")
    return digest.hexdigest()


def build_engine(version):
    """A new Engine for this version of the code.

    The first build in a process uses the modules as imported. A later build for a
    different version reloads them first, so the Engine, Game and GameError all come
    from the same, current code.
    """
    if _built["version"] is not None and _built["version"] != version:
        for name in MODULES:
            if name in sys.modules:
                importlib.reload(sys.modules[name])
    _built["version"] = version
    from game.engine import Engine

    return Engine()
