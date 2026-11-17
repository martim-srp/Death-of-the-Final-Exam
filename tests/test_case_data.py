"""Checks that the case file is complete and that each variant's story holds together.

These run against data/case.json, so they catch mistakes made when editing the story.
"""

import copy
import re

import pytest

from game.case import load_case, option_ids, resolve_variant
from game.engine import Engine

CASE = load_case()
VARIANTS = sorted(CASE["variants"])
TIME = re.compile(r"\d{4}-\d{2}-\d{2} (\d{2}):(\d{2})")


def minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def log_lines(engine, game, clue_id):
    """Open a clue regardless of locks and return its log lines."""
    clue = engine._clues(game)[clue_id]
    return engine._fill(game, clue.get("log") or "").splitlines()


def line_time(line):
    h, m = TIME.search(line).groups()
    return int(h) * 60 + int(m)


# ---- Structure -----------------------------------------------------------------


def test_unlock_rules_point_at_things_that_exist():
    for clue_id, clue in CASE["clues"].items():
        unlock = clue["unlock"]
        assert len(unlock) == 1, clue_id
        for required in unlock.get("requires", []):
            assert required in CASE["clues"]
        if "topic" in unlock:
            assert unlock["topic"]["suspect"] in CASE["suspects"]
            assert unlock["topic"]["topic"] in CASE["topics"]
        if "present" in unlock:
            assert unlock["present"]["suspect"] in CASE["suspects"]
            assert unlock["present"]["clue"] in CASE["clues"]


def test_topic_unlocks_match_clue_rules_both_ways():
    from_suspects = {
        (suspect, topic, clue_id)
        for suspect, s in CASE["suspects"].items()
        for topic, clue_id in s.get("topic_unlocks", {}).items()
    }
    from_clues = {
        (c["unlock"]["topic"]["suspect"], c["unlock"]["topic"]["topic"], clue_id)
        for clue_id, c in CASE["clues"].items()
        if "topic" in c["unlock"]
    }
    assert from_suspects == from_clues


@pytest.mark.parametrize("variant", VARIANTS)
def test_variant_overrides_only_touch_existing_clues_and_suspects(variant):
    v = CASE["variants"][variant]
    assert set(v.get("clues", {})) <= set(CASE["clues"])
    assert set(v.get("suspects", {})) <= set(CASE["suspects"])
    for column, value in v["solution"].items():
        assert value in option_ids(CASE, column)


def test_every_variant_has_a_different_culprit():
    culprits = [CASE["variants"][v]["solution"]["who"] for v in VARIANTS]
    assert len(set(culprits)) == len(culprits)


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_clue_can_be_reached_with_unlimited_time(variant):
    case = copy.deepcopy(CASE)
    case["clock"]["limit_minutes"] = 100_000
    engine = Engine(case)
    game = engine.new_game(seed=1, variant=variant)
    for _ in range(len(case["clues"])):
        for suspect in case["suspects"]:
            for topic in case["topics"]:
                engine.ask(game, suspect, topic)
            for clue_id in list(game.opened):
                engine.present(game, suspect, clue_id)
        for item in engine.clue_list(game):
            if item["state"] == "available":
                engine.open_clue(game, item["id"])
    assert sorted(game.opened) == sorted(case["clues"])


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_placeholder_is_filled_for_100_seeds(variant):
    engine = Engine()
    resolved = resolve_variant(CASE, variant)
    for seed in range(100):
        game = engine.new_game(seed=seed, variant=variant)
        for clue in resolved["clues"].values():
            for key in ("text", "log", "hidden_text"):
                filled = engine._fill(game, clue.get(key))
                assert filled is None or "{" not in filled
        for suspect in CASE["suspects"]:
            engine.character_brief(game, suspect)


# ---- The story holds together ------------------------------------------------


@pytest.mark.parametrize("seed", range(20))
def test_variant_a_timeline(seed):
    """The Class Representative is inside the library when the job is released,
    the Teaching Assistant's card never is, and the report was drafted before the leak."""
    engine = Engine()
    game = engine.new_game(seed=seed, variant="A")
    rep, ta = game.variables["rep_card"], game.variables["ta_card"]
    release = next(line_time(l) for l in log_lines(engine, game, "D2") if "job=88213" in l and "RELEASE" in l)
    gate = log_lines(engine, game, "L1")
    rep_in = next(line_time(l) for l in gate if f"IN   card=STU-{rep}" in l)
    rep_out = next(line_time(l) for l in gate if f"OUT  card=STU-{rep}" in l)
    assert rep_in < release < rep_out
    assert not any(ta in l for l in gate)
    first_draft = min(line_time(l) for l in log_lines(engine, game, "D6"))
    assert first_draft < minutes("23:47")
    home = log_lines(engine, game, "L3")
    assert line_time(home[0]) < rep_in and "OUT" in home[0]


@pytest.mark.parametrize("seed", range(20))
def test_variant_b_timeline(seed):
    """The Teaching Assistant's own card is in the library at release time,
    before their 18:00 invigilation, and the report email is innocent."""
    engine = Engine()
    game = engine.new_game(seed=seed, variant="B")
    ta = game.variables["ta_card"]
    release = next(line_time(l) for l in log_lines(engine, game, "D2") if "job=88213" in l and "RELEASE" in l)
    assert release < minutes("18:00")
    gate = log_lines(engine, game, "L1")
    ta_in = next(line_time(l) for l in gate if f"IN   card=STAFF-{ta}" in l)
    ta_out = next(line_time(l) for l in gate if f"OUT  card=STAFF-{ta}" in l)
    assert ta_in < release < ta_out < minutes("18:00")
    first_draft = min(line_time(l) for l in log_lines(engine, game, "D6"))
    assert first_draft > minutes("23:47")


@pytest.mark.parametrize("seed", range(20))
def test_variant_c_timeline(seed):
    """The print job was never released, and the PDF came from the Companion's iPad."""
    engine = Engine()
    game = engine.new_game(seed=seed, variant="C")
    assert not any("RELEASE job=88213" in l for l in log_lines(engine, game, "D2"))
    d1 = engine._fill(game, engine._clues(game)["D1"]["text"])
    d7 = engine._fill(game, engine._clues(game)["D7"]["text"])
    assert f"iPad ({game.variables['alias_initials']})" in d1
    assert game.variables["alias"] in d7
    first_draft = min(line_time(l) for l in log_lines(engine, game, "D6"))
    assert first_draft > minutes("23:47")
