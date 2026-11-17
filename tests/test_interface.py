"""Interface features from issue #3: log search, the D4 payoff chart and the denouement screen."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from game.case import load_case
from game.engine import Engine

APP = str(Path(__file__).resolve().parent.parent / "app.py")
CASE = load_case()


def start(variant="A", seed=1):
    at = AppTest.from_file(APP, default_timeout=10)
    at.session_state["game"] = Engine().new_game(seed=seed, variant=variant).to_dict()
    at.run()
    assert not at.exception
    return at


def click(at, starts_with):
    next(b for b in at.button if b.label.startswith(starts_with)).click().run()
    assert not at.exception


def page_text(at):
    return "\n".join(m.value for m in at.markdown)


# ---- Log search ------------------------------------------------------------------


def test_log_search_shows_only_matching_lines():
    at = start()
    click(at, "Open 📄 D1")
    click(at, "Open 📄 D2")
    full = at.code[0].value.splitlines()
    assert len(full) == 3

    at.text_input(key="search_D2").set_value("88213").run()
    shown = at.code[0].value.splitlines()
    assert shown and all("88213" in line for line in shown)
    assert len(shown) < len(full)
    assert any("2 of 3 lines match" in c.value for c in at.caption)


def test_log_search_is_case_insensitive_and_free():
    at = start()
    click(at, "Open 📄 D1")
    click(at, "Open 📄 D2")
    clock = at.metric[0].value
    at.text_input(key="search_D2").set_value("release").run()
    assert len(at.code[0].value.splitlines()) == 2
    assert at.metric[0].value == clock


def test_log_search_with_no_match_says_so():
    at = start()
    click(at, "Open 📄 D1")
    click(at, "Open 📄 D2")
    at.text_input(key="search_D2").set_value("nothing-like-this").run()
    assert not at.code
    assert any("0 of 3 lines match" in c.value for c in at.caption)


# ---- Payoff chart ----------------------------------------------------------------


def test_d4_shows_the_payoff_chart():
    at = start()
    assert not at.get("vega_lite_chart")
    click(at, "Open 📄 D4")
    assert len(at.get("vega_lite_chart")) == 1


def test_payoff_chart_data_matches_the_standings_in_d4():
    spec = CASE["charts"]["payoff"]
    d4 = CASE["clues"]["D4"]["text"]
    assert CASE["clues"]["D4"]["chart"] == "payoff"
    assert f"{spec['prize']:,}" in d4
    assert "Mock finals: Exchange Student " + ", ".join(map(str, spec["rival_mocks"])) in d4
    assert "Class Representative " + ", ".join(map(str, spec["subject_mocks"])) in d4


# ---- Denouement ------------------------------------------------------------------


def test_denouement_is_hidden_while_the_case_is_open():
    at = start()
    assert "Half past seven" not in "\n".join(s.value for s in at.subheader)
    assert "You close the folder" not in page_text(at)


@pytest.mark.parametrize("variant", sorted(CASE["variants"]))
def test_solving_the_case_shows_that_variants_denouement(variant):
    at = start(variant=variant, seed=7)
    solution = CASE["variants"][variant]["solution"]
    for column, value in solution.items():
        at.radio(key=f"accuse_{column}").set_value(value)
    click(at, "Make the accusation")
    assert any("Case solved" in s.value for s in at.success)
    assert any("Half past seven" in s.value for s in at.subheader)
    text = page_text(at)
    first_line = CASE["variants"][variant]["denouement"].split("\n\n")[1]
    assert first_line.replace("\\", "")[:40] in text.replace("\\", "")
    assert "{" not in text.replace("\\{", "")


def test_a_cold_case_also_shows_the_denouement():
    at = start()
    wrong = {**CASE["variants"]["A"]["solution"], "who": "exchange"}
    for column, value in wrong.items():
        at.radio(key=f"accuse_{column}").set_value(value)
    for _ in range(CASE["max_strikes"]):
        click(at, "Make the accusation")
    assert any("gone cold" in e.value for e in at.error)
    assert any("Half past seven" in s.value for s in at.subheader)
