"""Key-word emphasis for easier scanning: the words a sentence turns on are shown in bold.

The bold is added when the HTML is built (board.emphasize), so the story data stays plain text,
nothing extra reaches the AI, and every piece of text is still escaped.
"""

import html
import re

import pytest

import board
from game import ai
from game.case import load_case
from game.engine import Engine
from tests.test_board_game import page, start

CASE = load_case()
TAG = re.compile(r"</?(?:strong|mark)[^>]*>")


def plain(markup):
    """What the player reads: the markup without the emphasis tags, unescaped."""
    return html.unescape(TAG.sub("", markup))


def bold(markup):
    return re.findall(r'<strong class="kw">(.*?)</strong>', markup)


def test_key_words_are_bold():
    markup = board.emphasize("The Cashier saw the Teaching Assistant pay at 13:05.")
    assert bold(markup) == ["Cashier", "Teaching Assistant", "13:05"]


def test_text_is_escaped_before_it_is_wrapped():
    markup = board.emphasize('<script>alert(1)</script> at 19:40 & "the library"')
    assert "<script>" not in markup
    assert "&lt;script&gt;" in markup and "&amp;" in markup and "&quot;" in markup
    assert bold(markup) == ["19:40", "library"]


def test_at_most_three_per_sentence_and_the_count_starts_again_each_sentence():
    text = "At 18:00, 18:31, 18:52 and 19:05 cards were used. Then 19:20 and 19:25."
    markup = board.emphasize(text)
    assert bold(markup) == ["18:00", "18:31", "18:52", "19:20", "19:25"]


def test_a_word_is_bold_only_the_first_time():
    assert bold(board.emphasize("The Professor left. The Professor came back.")) == ["Professor"]


def test_a_hunch_detail_is_marked_and_wins_over_a_key_word():
    markup = board.emphasize("At 19:40 the Cleaner saw someone trying the handle.", ["the Cleaner saw"])
    assert "<mark>the Cleaner saw</mark>" in markup
    assert bold(markup) == ["19:40"]


def test_only_whole_words_and_ta_only_in_capitals():
    assert bold(board.emphasize("Data from the stack: ta, TA, libraryish, 123:456.")) == ["TA"]


def test_emphasis_never_changes_the_words():
    """Every clue, "In short" line and thought reads exactly as written, in every variant."""
    engine = Engine()
    texts = []
    for variant in CASE["variants"]:
        game = engine.new_game(seed=3, variant=variant)
        for clue_id in CASE["clues"]:
            texts.append(engine._fill(game, CASE["clues"][clue_id]["text"]))
            texts += [engine.key_fact(game, clue_id) or "", engine.musing(game, clue_id) or ""]
        for suspect in CASE["suspects"]:
            texts.append(engine.character_brief(game, suspect)["cover"])
    for text in texts:
        assert plain(board.emphasize(text)) == text
    assert any(bold(board.emphasize(text)) for text in texts)


def test_the_ai_prompt_has_no_emphasis():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    for suspect in CASE["suspects"]:
        prompt = ai.system_prompt(engine.character_brief(game, suspect), CASE["topics"])
        assert "<strong" not in prompt and 'class="kw"' not in prompt


def test_an_open_card_shows_key_words_in_bold_and_keeps_the_hunch_mark():
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "L4")
    markup = page(start(game=game, focus=("clue", "L4")))
    assert '<small>In short</small>At <strong class="kw">19:40</strong>' in markup
    assert "<mark>trying the handle</mark>" in markup
    assert '<strong class="kw">Cleaner</strong>' in markup


def test_the_walkthrough_and_next_step_have_key_words_in_bold():
    assert '<strong class="kw">30 minutes</strong>' in board.tutorial_html()
    step = {"do": "ask", "suspect": "professor", "text": "Ask the Professor about the exam."}
    assert '<strong class="kw">Professor</strong>' in board.goal_html(step)


@pytest.mark.parametrize("kind", ["cover", "lead"])
def test_notebook_stories_and_leads_have_key_words_in_bold(kind):
    engine = Engine()
    game = engine.new_game(seed=1, variant="A")
    engine.open_clue(game, "D1")
    engine.open_clue(game, "D2")
    engine.ask(game, "professor", "exam")
    markup = page(start(game=game, focus=("sheet", None)))
    if kind == "cover":
        assert "Lisbon</strong>" in markup or "16:10</strong>" in markup
    else:
        assert 'Teaching Assistant</strong>' in markup
