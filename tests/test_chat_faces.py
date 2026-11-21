"""Chat faces are sent once per chat, not once per bubble, so a long interrogation stays light on a phone."""

import board
from tests.test_board_game import page, start


def test_each_face_appears_once_however_long_the_chat():
    at = start(focus=("suspect", "professor"), suspect="professor")
    for topic in ("alibi", "exam", "report"):
        at.pills(key="ask_topic").set_value(topic).run()
    assert not at.exception
    html = page(at)
    assert html.count('class="bubble you"') == 3 and html.count('class="bubble them"') == 3
    them = board.suspect_picture("professor")
    you = board.find_picture("detectives", at.session_state.get("avatar", "she")) or board.find_picture("detectives", "he")
    chat = html[html.index('<div class="chat">'):]
    assert chat.count(them) == 1  # once, in the chat's style; the six bubbles point at a CSS class
    assert f'.chat .face.them {{ background-image: url("{them}"); }}' in chat
    assert '<i class="face them"></i>' in chat and '<i class="face you"></i>' in chat
    assert you  # the detective's face exists, so the "you" class has a picture
