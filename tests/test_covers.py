"""Cover stories are spoken by the suspect.

When the AI is unavailable, the app shows a suspect's cover as their answer, so every
cover, including the variant overrides, must read as the suspect speaking in the first person.
"""

import re

import pytest

from game.case import load_case, resolve_variant

CASE = load_case()
VARIANTS = sorted(CASE["variants"])
THIRD_PERSON = re.compile(r"\b(their room|their own|he has|with him all evening)\b", re.IGNORECASE)


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("suspect", sorted(CASE["suspects"]))
def test_cover_is_in_the_first_person(variant, suspect):
    cover = resolve_variant(CASE, variant)["suspects"][suspect]["cover"]
    assert cover.startswith("I "), cover
    assert not THIRD_PERSON.search(cover), cover
