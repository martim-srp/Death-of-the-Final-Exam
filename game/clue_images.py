"""Find the evidence picture for a clue, if it has one.

Pictures live in assets/clues/<clue id>.webp. Only some clues have one, so the
interface shows the picture when this returns a path and skips it otherwise.
The pictures hold no times, card numbers or names, so the same picture fits
every variant. Show a clue's picture only once the clue is unlocked.
"""

import re
from pathlib import Path

CLUE_IMAGES_DIR = Path(__file__).resolve().parent.parent / "assets" / "clues"

# Clue ids look like D1 or L3. Anything else is refused, so a crafted id can
# never point outside the pictures folder.
_CLUE_ID = re.compile(r"^[A-Z][0-9]{1,2}$")


def clue_image_path(clue_id, folder=CLUE_IMAGES_DIR):
    """Return the path of the clue's picture, or None if it has none."""
    if not isinstance(clue_id, str) or not _CLUE_ID.match(clue_id):
        return None
    path = Path(folder) / f"{clue_id}.webp"
    return path if path.is_file() else None
