"""Load the case file and build the version of it that applies to one variant.

The case file (data/case.json) holds the shared story. Each variant only lists
what differs from it, so this module merges the variant's overrides on top.
"""

import copy
import json
from pathlib import Path

CASE_PATH = Path(__file__).resolve().parent.parent / "data" / "case.json"
HUNCHES_PATH = CASE_PATH.parent / "hunches.json"
VOICE_PATH = CASE_PATH.parent / "voice.json"
CRACKS_PATH = CASE_PATH.parent / "cracks.json"
KEYFACTS_PATH = CASE_PATH.parent / "keyfacts.json"


def load_hunches(path=HUNCHES_PATH):
    """Read the detective's inner-voice lines for clues that break a story (data/hunches.json)."""
    with open(path, encoding="utf-8") as f:
        return {key: value for key, value in json.load(f).items() if not key.startswith("_")}


def load_voice(path=VOICE_PATH):
    """Read the detective's other lines: thoughts on clues, reactions to replies, the next step (data/voice.json)."""
    with open(path, encoding="utf-8") as f:
        return {key: value for key, value in json.load(f).items() if not key.startswith("_")}


def load_cracks(path=CRACKS_PATH):
    """Read what a suspect blurts out when their nerves break (data/cracks.json)."""
    with open(path, encoding="utf-8") as f:
        return {key: value for key, value in json.load(f).items() if not key.startswith("_")}


def load_keyfacts(path=KEYFACTS_PATH):
    """Read the one-line summary of each evidence card, shared and per variant (data/keyfacts.json)."""
    with open(path, encoding="utf-8") as f:
        return {key: value for key, value in json.load(f).items() if not key.startswith("_")}


def load_case(path=CASE_PATH):
    """Read the case file from disk."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def deep_merge(base, override):
    """Return a copy of base with override applied. Nested dicts merge key by key."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def resolve_variant(case, variant):
    """Return the clues and suspects as they are in one variant."""
    if variant not in case["variants"]:
        raise KeyError(f"Unknown variant: {variant}")
    v = case["variants"][variant]
    return {
        "clues": deep_merge(case["clues"], v.get("clues", {})),
        "suspects": deep_merge(case["suspects"], v.get("suspects", {})),
        "solution": dict(v["solution"]),
    }


def option_ids(case, column):
    """The ids allowed in one accusation column (who, how, where or why)."""
    return [option["id"] for option in case["accusation"][column]]
