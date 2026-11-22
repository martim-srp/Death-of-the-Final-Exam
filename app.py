"""Death of the Final Exam: Streamlit interface.

Run with:  streamlit run app.py

One screen, laid out like a board game: the campus map is the board, your evidence
cards are your hand, and the five suspects sit across the top. Tapping anything opens
it in the panel on the right (below the board on a phone).

The game state lives in st.session_state on the server. The browser only ever
receives what the engine returns, so locked clues and the solution never reach it.
board.py builds the board's markup from that.
"""

import functools
import html
import re
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import streamlit as st

import board
import db
import reloading
import report
from game.case import load_case

ROOT = Path(__file__).resolve().parent
COVER = ROOT / "assets" / "cover.webp"
CAMPUS_MAP = ROOT / "assets" / "campus-map.webp"
TITLE = load_case()["title"]  # the game's name lives in data/case.json

# The detectives a player can be: assets/detectives/<id>.webp, 4:5 like the suspects. Purely cosmetic.
AVATARS = {"she": "Play as her", "he": "Play as him"}
DEFAULT_AVATAR = "she"
COLUMNS = ("who", "how", "where", "why")
APP_URL = "https://carcavelos-paper.streamlit.app"
COLUMN_ICONS = {"who": ":material/person:", "how": ":material/build:", "where": ":material/location_on:", "why": ":material/psychology_alt:"}
# Shown under a free-text answer when the suspect gave a scripted line instead of the AI's.
# Keys are the reasons game/ai.py records in the game's history.
FALLBACK_NOTES = {
    "no_key": "The AI isn't connected, so this is the suspect's scripted answer.",
    "failed": "The AI didn't answer this time, so this is the suspect's scripted answer.",
    "unreadable": "The AI's answer couldn't be read, so this is the suspect's scripted answer.",
    "limit": "This case has used up its AI questions. Suspects now give their scripted answers.",
}
# Shown in the chat instead of a typed question that looked like a password or key.
HIDDEN_QUESTION = "(Hidden: that looked like a password, so it was not sent.)"
# Shown under the hidden line in the leaked PDF: what that line is, and why it cannot work here.
AI_TRAP_NOTE = (
    "Behind the scenes: this is a prompt injection, text hidden in evidence that tries to give orders to an AI. "
    "The suspects are played by an AI, but it only ever sees its own character, never the evidence, "
    "so a note like this cannot steer it. Only the rules engine decides what is true."
)
# The questions a player can tap, by topic: (button label, what the detective says).
TOPICS = {
    "alibi": ("Last night?", "Where were you last night?"),
    "exam": ("The exam", "What do you know about tomorrow's exam?"),
    "report": ("The report", "Tell me about the report."),
    "work": ("Your job", "What is your job here?"),
    "teaching_assistant": ("The TA", "What can you tell me about the Teaching Assistant?"),
    "leak": ("The leak", "Who leaked the paper?"),
    "other": ("Anything else?", "Is there anything else I should know?"),
}

st.set_page_config(page_title=TITLE, page_icon=":material/search:", layout="wide", initial_sidebar_state="collapsed")


@st.cache_resource(max_entries=1)
def get_engine(version):
    """One Engine per version of the game code and case file (see reloading.py)."""
    return reloading.build_engine(version)


engine = get_engine(reloading.source_version())
case = engine.case

# Imported after get_engine(), which may have just reloaded game.engine.
from game.engine import NERVES_MAX, NERVES_PER_CARD, NERVES_PER_LIE, Game, GameError  # noqa: E402


# ---- Saving and loading --------------------------------------------------------------


def start_new_game():
    """Start a game, save it, and put its private id in the URL as the resume link."""
    game = engine.new_game()
    game_id = db.create_game(game)
    st.session_state.game = game.to_dict()
    st.session_state.game_id = game_id
    st.query_params["game"] = game_id


def current_game():
    if "game" not in st.session_state:
        requested = st.query_params.get("game")
        saved = db.load_game(requested) if requested else None
        if saved is not None and saved.variant not in case["variants"]:
            saved = None  # saved with a variant this case file no longer has
        if saved is not None:
            st.session_state.game = saved.to_dict()
            st.session_state.game_id = requested
        else:
            if requested:
                st.session_state.flash = ("warning", "That saved game was not found, so a new case has started.")
            start_new_game()
    elif "game_id" in st.session_state:
        # The saved game is the truth. Another tab or phone with the same link may have
        # played on, so an old copy in this tab must not undo it (or undo a cold case).
        saved = db.load_game(st.session_state.game_id)
        if saved is not None and saved.variant in case["variants"]:
            st.session_state.game = saved.to_dict()
    return Game.from_dict(st.session_state.game)


def save(game):
    st.session_state.game = game.to_dict()
    if "game_id" in st.session_state:
        db.save_game(st.session_state.game_id, game)


def resume_link(game_id):
    """Build the current case's shareable resume URL without carrying other query values."""
    current_url = st.context.url
    if current_url:
        parts = urlsplit(current_url)
        base = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    else:
        base = APP_URL
    return f"{base}?game={quote(str(game_id), safe='')}"


def save_game_mailto(link):
    """Open the player's own mail app with a resume link, without collecting an address."""
    subject = quote("My Death of the Final Exam case", safe="")
    body = quote(f"Pick up where I left off: {link}", safe="")
    return f"mailto:?subject={subject}&body={body}"


def run(action, *args):
    """Run an engine action, save the game, and turn rule errors into messages.

    Newly unlocked clues pop up as a toast and are dealt into the hand with an animation.
    """
    game = current_game()
    clock_before = game.clock
    locked = {c["id"] for c in engine.clue_list(game) if c["state"] == "locked"}
    known_leads = {lead["clue"] for lead in engine.leads(game)}
    try:
        result = action(game, *args)
    except GameError as error:
        # A pop-up, so the player sees it wherever they are on the page.
        st.session_state.refusal = str(error)
        return None
    save(game)
    unlocked = [c for c in engine.clue_list(game) if c["id"] in locked and c["state"] != "locked"]
    st.session_state.fresh = [c["id"] for c in unlocked]
    if unlocked:
        names = ", ".join(engine.label(c["id"]) for c in unlocked)
        st.session_state.toast = (f"New evidence card unlocked: {names}", ":material/lock_open:")
    elif any(lead["clue"] not in known_leads for lead in engine.leads(game)):
        st.session_state.toast = ("New lead. Tap the magnifier to see it.", ":material/search:")
    # Something happened in the building while the clock moved on: the latest event pops up.
    passed = engine.night_events(game, since=clock_before)
    if passed:
        st.session_state.night_toast = f"{passed[-1]['time']} · {passed[-1]['text']}"
    return result


def calm():
    """Calm mode: no animations and no sounds anywhere, and the next step in one plain line.
    Off by default; switched from the status bar or the start screen."""
    return bool(st.session_state.get("calm"))


def toggle_calm():
    st.session_state.calm = not calm()
    st.session_state.toast = (
        ("Calm mode on: no animations, no sounds." if calm() else "Calm mode off."), ":material/dark_mode:")


def sound(name):
    """Ask the board to play one short sound on the next draw (see board.sfx_html)."""
    st.session_state.sfx = name
    st.session_state.sfx_n = st.session_state.get("sfx_n", 0) + 1


def new_case():
    start_new_game()
    for key in [k for k in st.session_state if str(k).startswith(("sheet_", "crossed_", "accuse_"))]:
        del st.session_state[key]
    for key in ("chats", "focus", "suspect", "verdict", "fresh", "sfx"):
        st.session_state.pop(key, None)


# ---- Small helpers --------------------------------------------------------------------


def label(column, option_id):
    return next(o["label"] for o in case["accusation"][column] if o["id"] == option_id)


_MARKDOWN_SPECIAL = re.compile(r"([\\`*_\[\]<>#$~|])")


def plain(text):
    """Escape Markdown so story text is shown exactly as written."""
    return _MARKDOWN_SPECIAL.sub(r"\\\1", text)


def mid_sentence(name):
    """A suspect's name inside a sentence: "The Professor" becomes "the Professor"."""
    return "the" + name[3:] if name.startswith("The ") else name


def esc(text):
    return html.escape(str(text), quote=True)


def search_log(log, query):
    """The log lines that contain the query (case-insensitive), and the total line count."""
    lines = log.splitlines()
    needle = query.strip().lower()
    if not needle:
        return lines, len(lines)
    return [line for line in lines if needle in line.lower()], len(lines)


def player_avatar():
    """The chosen detective's id, falling back to the first one."""
    choice = st.session_state.get("player_avatar")
    return choice if choice in AVATARS else DEFAULT_AVATAR


def player_name():
    return (st.session_state.get("player_name") or "").strip() or "Detective"


def proven_out(column):
    """Options the evidence has ruled out in one column, as {option id: what ruled it out}."""
    if "game" not in st.session_state:
        return {}
    game = Game.from_dict(st.session_state.game)
    return {e["option"]: e["by"] for e in engine.eliminated(game) if e["column"] == column}


def crossed(column):
    """The options crossed off: the player's own notes, plus what the evidence has ruled out."""
    # Kept under its own key: Streamlit drops a widget's value once the notebook is closed.
    live = st.session_state.get(f"sheet_{column}")
    mine = list(live if live is not None else st.session_state.get(f"crossed_{column}") or [])
    return mine + [o for o in proven_out(column) if o not in mine]


def case_columns():
    """For the case strip: each question, how many options are still possible, and the answer once one is left."""
    columns = []
    for column in COLUMNS:
        options = [o["id"] for o in case["accusation"][column]]
        left = [o for o in options if o not in crossed(column)]
        only = label(column, left[0]).removeprefix("The ") if len(left) == 1 else None
        columns.append((column, len(left), len(options), only))
    return columns


def keep_crossed(column):
    """Save the notebook's cross-offs where they outlive the notebook panel."""
    st.session_state[f"crossed_{column}"] = list(st.session_state.get(f"sheet_{column}") or [])


def ruled_out(suspect):
    return suspect in crossed("who")


def focus():
    """What the side panel shows: ("home"), ("suspect", id), ("clue", id), ("spot", id), ("sheet") or ("accuse")."""
    return st.session_state.get("focus") or ("home", None)


def set_focus(kind, value=None):
    st.session_state.focus = (kind, value)
    if kind == "suspect":
        st.session_state.suspect = value


# ---- The first-minute tutorial ----------------------------------------------------------
# A new player's first case (normal mode) starts with three guided steps that end in a caught
# lie: search the faculty corridor, show it to the Companion, see the lie break. The same in
# every variant, and a caught lie is not a confession, so it never points at the culprit.

TUTORIAL_CLUE, TUTORIAL_SUSPECT = "L4", "companion"


def tutorial_step(game):
    """1: search Evidence 12. 2: show it to the Companion. 3: a lie is caught. None once over or off."""
    if not st.session_state.get("tutorial") or st.session_state.get("tutorial_done"):
        return None
    if engine.hard(game) or game.status != "playing":
        return None
    if game.contradictions:
        return 3
    if TUTORIAL_CLUE not in game.opened:
        ready = engine.clue_state(game, TUTORIAL_CLUE) == "available" and engine.can_afford(game, case["clock"]["clue_cost"])
        return 1 if ready else None
    shown = any(e.get("action") == "present" and e.get("suspect") == TUTORIAL_SUSPECT and e.get("clue") == TUTORIAL_CLUE
                for e in game.history)
    return None if shown or not engine.can_afford(game, case["clock"]["question_cost"]) else 2


def guide(game):
    """The next step the board points at: the tutorial's while it runs, then the engine's."""
    number = tutorial_step(game)
    if number == 1:
        return {"do": "search", "clue": TUTORIAL_CLUE, "text": "Tutorial 1 of 3 · Tap the glowing Faculty pin, then Search it."}
    if number == 2:
        return {"do": "show", "clue": TUTORIAL_CLUE, "suspect": TUTORIAL_SUSPECT,
                "text": "Tutorial 2 of 3 · Show card 12 to the Companion. She says she never went to his office door."}
    return engine.next_step(game)


def end_tutorial():
    st.session_state.tutorial_done = True


def coach_card(game):
    """The tutorial in the side panel: a skip link while it runs (the guide strip says what to tap),
    then one line once the lie is caught."""
    number = tutorial_step(game)
    if not number:
        return
    with st.container(key="coach"):
        if number == 3:
            st.markdown('<div class="coach"><p><b>Caught her lying! That is the game:</b> '
                        "find the card that breaks each story.</p></div>", unsafe_allow_html=True)
            st.button("Got it", key="tutorial_ok", type="primary", icon=":material/check:",
                      on_click=end_tutorial, use_container_width=True)
        else:
            st.button("Skip the tutorial", key="tutorial_skip", type="tertiary", on_click=end_tutorial)


def go_next():
    """The phone's next-step button: open what the next step points at."""
    step = guide(current_game())
    parsed = board.parse_act(board.goal_act(step), case["suspects"], case["clues"]) if step else None
    if parsed:
        set_focus(*parsed)


def next_step_button(game):
    """On phones the strip above the map scrolls out of sight, so the panel ends with the next step too."""
    step = guide(game)
    if step:
        st.button(step["text"], key="next_phone", icon=":material/arrow_forward:", on_click=go_next, use_container_width=True)


def on_act(key):
    """A tap on the board: open what was tapped in the side panel. Free; it never changes the game."""
    state = st.session_state.get(key) or {}
    act = state.get("act") if hasattr(state, "get") else getattr(state, "act", None)
    parsed = board.parse_act(act, case["suspects"], case["clues"])
    if parsed is None:
        return
    kind, value = parsed
    if kind == "intro":
        st.session_state.intro_done = False
    elif kind == "calm":
        toggle_calm()
    else:
        set_focus(kind, value)


# ---- The ending scene ---------------------------------------------------------------

def denouement(game):
    """The confrontation if solved, or the unsolved outcome if cold."""
    return report.closing_scene(engine, game)


# ---- Page style ----------------------------------------------------------------------

# The page's look lives in assets/style.css; this file keeps the game's logic.
PAGE_CSS = "\n<style>\n" + (ROOT / "assets" / "style.css").read_text(encoding="utf-8") + "</style>\n"

# Calm mode on the page itself: chat bubbles, stamps and the finale appear at once instead of animating.
CALM_CSS = """<style>
body *, body *::before, body *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
</style>"""

deck = st.components.v2.component("deck", js=board.BOARD_JS, css=board.BOARD_CSS)


@st.cache_data
def map_picture():
    """The map picture as a data URI, with its size in pixels."""
    from PIL import Image  # installed with streamlit

    with Image.open(CAMPUS_MAP) as picture:
        size = picture.size
    return board.static_url(CAMPUS_MAP.name) or board.data_uri(str(CAMPUS_MAP)), size


def rattled(game, suspect):
    """Caught in a lie, or cracked: from then on the suspect shows their nervous portrait."""
    return any(s == suspect for s, _claim in game.contradictions) or suspect in game.cracked


def suspect_status(game):
    """For each suspect: whether you have questioned them, how many lies you caught, and their nerves."""
    questioned = {event["suspect"] for event in game.history if "suspect" in event}
    caught = {}
    for suspect, _claim in game.contradictions:
        caught[suspect] = caught.get(suspect, 0) + 1
    return [
        {"id": s, "name": d["name"], "questioned": s in questioned, "caught": caught.get(s, 0), "ruled_out": ruled_out(s),
         "nerves": engine.nerves(game, s), "done": engine.suspect_progress(game, s)["done"], "nervous": rattled(game, s)}
        for s, d in case["suspects"].items()
    ]


def draw_board(game, clues, fresh):
    """The status bar, the campus map and the evidence hand, as one tappable component."""
    kind, value = focus()
    picked = value if kind == "clue" else None
    avatar = board.find_picture("detectives", player_avatar())
    map_uri, size = map_picture()
    step = guide(game)
    goal = board.goal_target(step)
    markup = (
        board.hud_html(
            engine.clock_label(game), engine.time_left(game), case["clock"]["limit_minutes"],
            case["max_strikes"] - game.strikes, case["max_strikes"], len(game.contradictions), avatar, player_name(),
            calm=calm(),
        )
        # In calm mode the next step is one plain line, without the detective's musing.
        + board.goal_html(step, None if calm() or tutorial_step(game) in (1, 2) else engine.thought(game, step))
        + board.case_html(case_columns())
        + '<div class="phone-only">' + board.suspects_html(suspect_status(game), focus()[1] if kind == "suspect" else None, goal) + "</div>"
        + board.map_html(map_uri, size, board.map_points(clues), game.opened, picked, avatar, fresh, goal)
        + board.hand_html(clues, picked, fresh, goal)
        + pending_sound()
        + board.calm_html(calm())
    )
    deck(data=markup, key="board", on_act_change=functools.partial(on_act, "board"))


def pending_sound():
    """The sound asked for by the last action, once. None in calm mode."""
    name = st.session_state.pop("sfx", None)
    if calm():
        return ""
    return board.sfx_html(name, st.session_state.get("sfx_n", 0)) if name else ""


def draw_suspects(game):
    kind, value = focus()
    picked = value if kind == "suspect" else None
    goal = board.goal_target(guide(game))
    deck(data=board.suspects_html(suspect_status(game), picked, goal) + board.calm_html(calm()), key="suspect_row",
         on_act_change=functools.partial(on_act, "suspect_row"))


# ---- Panel: home (leads, the night so far) ------------------------------------------------


def panel_home(game):
    st.markdown('<div class="kicker">Your move</div>', unsafe_allow_html=True)
    leads = engine.leads(game) + [{"clue": c, "text": t} for c, t in engine.hint_list(game).items()]
    if leads:
        st.markdown("### Leads")
        st.markdown(
            "".join(f'<div class="lead"><b>Evidence {engine.number(lead["clue"])}</b><span>{esc(lead["text"])}</span></div>' for lead in leads),
            unsafe_allow_html=True,
        )
    elif game.history:
        step = engine.next_step(game)
        if step:
            st.markdown(f"### {step['text']}")  # the next step, once the first move is made
    elif not tutorial_step(game):  # the tutorial's coach card already says where to start
        st.markdown("### Where to start")
        st.markdown(
            f'<div class="tips"><div><span>{board.icon("search")}</span>Tap a red evidence card or pin to search it</div>'
            f'<div><span>{board.icon("ask")}</span>Tap a face to interrogate</div>'
            f'<div><span>{board.icon("bolt")}</span>Show a suspect the evidence card that breaks their story</div></div>',
            unsafe_allow_html=True,
        )
    night = engine.night_events(game)
    if night:
        st.markdown("### The night so far")
        st.markdown("".join(f'<div class="lead"><b>{e["time"]}</b><span>{esc(e["text"])}</span></div>' for e in night),
                    unsafe_allow_html=True)
    badges = engine.badge_list(game)
    if badges:
        st.markdown('<div class="medals">' + "".join(f'<span title="{esc(b["description"])}">{board.icon("medal")} {esc(b["title"])}</span>' for b in badges) + "</div>",
                    unsafe_allow_html=True)
    st.caption(
        f"Searching costs {case['clock']['clue_cost']} min, a question {case['clock']['question_cost']} min. "
        "Your case saves itself. Tap the save icon in the corner to keep the link."
    )
    with st.popover("New case", icon=":material/refresh:"):
        st.write("Start over with a new culprit? This case will be lost.")
        if st.button("Yes, new case", type="primary", key="new_case"):
            new_case()
            st.rerun()


def save_corner():
    """Save game: a round save icon pinned to the bottom-left corner, on every panel, desktop and phone."""
    with st.container(key="save_corner"):
        with st.popover("Save game", icon=":material/save:"):
            st.write("Your case saves itself after every move. Keep this link to come back to it.")
            game_id = st.session_state.get("game_id")
            if game_id:
                link = resume_link(game_id)
                st.code(link, language=None)
                st.link_button("Send to my email", save_game_mailto(link), icon=":material/mail:",
                               use_container_width=True)
            else:
                st.caption("Saving is not available for this case.")
            st.caption("Anyone with this link can open this case. The free server can restart and clear saved games.")


# ---- Panel: lies caught (the lightning in the status bar) ---------------------------------


LIE_RULES = [
    ("card", "You catch a lie when you show a suspect the evidence card that breaks something they told you."),
    ("bolt", f"Their nerves go up by {NERVES_PER_LIE}, on top of the {NERVES_PER_CARD} every new card adds. "
             f"At {NERVES_MAX} they crack and let something slip."),
    ("sheet", "The lie is written in your notebook, under that suspect's story."),
    ("medal", "Every lie caught raises your detective rank at the end."),
    ("scale", "A lie is not proof of guilt. People lie to hide other things too."),
]


def panel_lies(game):
    """What the lightning in the status bar counts, what a caught lie changes, and the ones caught so far.

    Lists only lies already caught, so it never tells which card breaks a story you have not broken yet."""
    caught = engine.contradiction_list(game)
    count = f"{len(caught)} {'lie' if len(caught) == 1 else 'lies'} caught" if caught else "No lies caught yet"
    st.markdown(f'<div class="kicker">{board.icon("bolt")} Lies caught</div><h3>{count}</h3>', unsafe_allow_html=True)
    st.markdown('<div class="lie-rules">' + "".join(f"<div>{board.icon(i)}<span>{esc(t)}</span></div>" for i, t in LIE_RULES)
                + "</div>", unsafe_allow_html=True)
    if not caught:
        st.caption("Open evidence cards. When a detail does not fit someone's story, tap their face and show them that card.")
        return
    for item in caught:
        name = board.short_name(case["suspects"][item["suspect"]]["name"])
        broke = " · cracked" if item["suspect"] in game.cracked else ""
        st.markdown(
            f'<div class="lie"><b>{esc(name)}</b> said “{esc(item["text"].rstrip("."))}” · broken by '
            f'<b>{esc(proof_name(item["clue"]) if item["clue"] else "a clue")}</b>'
            f'{lie_meaning_html(item)}'
            f'<span class="nerves-mini">Nerves {engine.nerves(game, item["suspect"])} of {NERVES_MAX}{broke}</span></div>',
            unsafe_allow_html=True,
        )
    for suspect in dict.fromkeys(item["suspect"] for item in caught):
        name = board.short_name(case["suspects"][suspect]["name"])
        st.button(f"Question {name} again", key=f"lies_to_{suspect}", icon=":material/forum:", use_container_width=True,
                  on_click=set_focus, args=("suspect", suspect))


# ---- Panel: interrogation -----------------------------------------------------------


def say(suspect, entry):
    st.session_state.setdefault("chats", {}).setdefault(suspect, []).append(entry)


def think(suspect, line):
    """The detective's own thought after an answer: a scripted line, no AI call.

    Kept on the answer it reacts to, so the chat stays one question, one answer."""
    log = st.session_state.get("chats", {}).get(suspect)
    if line and log and log[-1]["who"] == "them":
        log[-1]["think"] = line


def ask_topic():
    """Tapping a question: ask it at once, then clear the pick so it can be tapped again."""
    topic = st.session_state.get("ask_topic")
    st.session_state.ask_topic = None
    suspect = st.session_state.get("suspect")
    if topic not in TOPICS or suspect not in case["suspects"]:
        return
    result = run(engine.ask, suspect, topic)
    if result:
        sound("tick")
        from game import ai

        brief = engine.character_brief(current_game(), suspect)
        say(suspect, {"who": "you", "text": TOPICS[topic][1]})
        say(suspect, {"who": "them", "text": ai.scripted_reply(brief, topic), "unlocked": result["unlocked"]})
        think(suspect, engine.reaction(current_game(), topic=topic, unlocked=bool(result["unlocked"])))


def show_evidence():
    """Tapping one of your cards in the interrogation: slide it across the table."""
    clue_id = st.session_state.get("show_clue")
    st.session_state.show_clue = None
    present_card(st.session_state.get("suspect"), clue_id)


def show_to(clue_id):
    """Tapping a suspect under an open evidence card: show it to them, then go to their interrogation
    so the answer is on screen."""
    key = f"show_to_{clue_id}"
    suspect = st.session_state.get(key)
    st.session_state[key] = None
    if suspect in case["suspects"] and present_card(suspect, clue_id):
        set_focus("suspect", suspect)


def present_card(suspect, clue_id):
    """Show one evidence card to one suspect and write the exchange in their chat. Returns the engine's result."""
    if not clue_id or suspect not in case["suspects"]:
        return None
    result = run(engine.present, suspect, clue_id)
    if result:
        sound("stamp" if result.get("contradictions") or result.get("cracked") else "tick")
        say(suspect, {"who": "you", "text": f"You slide {engine.label(clue_id)} across the table.", "act": True})
        say(suspect, {
            "who": "them", "text": result["reveal"] or "They look at it and shrug.",
            "unlocked": result["unlocked"], "caught": result.get("contradictions", []),
        })
        if result.get("cracked"):
            say(suspect, {"who": "them", "text": result["cracked"]["line"], "cracked": result["cracked"]})
        think(suspect, engine.reaction(current_game(), caught=bool(result.get("contradictions")),
                                       unlocked=bool(result["unlocked"]), shown=True, reacted=bool(result["reveal"])))
    return result


def cloud_key():
    from streamlit.errors import StreamlitSecretNotFoundError

    try:
        return st.secrets.get("REQUESTY_API_KEY")
    except StreamlitSecretNotFoundError:
        return None


def lie_meaning_html(item):
    """Under a caught lie: what it tells you, so the stamp leads somewhere."""
    meaning = engine.lie_meaning(current_game(), item.get("claim"))
    return f'<span class="means"><b>What it means:</b> {esc(meaning)}</span>' if meaning else ""


def chat_html(log, suspect):
    """The conversation as speech bubbles: the suspect on the left, you on the right."""
    them = board.suspect_picture(suspect, rattled(current_game(), suspect)) or ""
    you = board.find_picture("detectives", player_avatar()) or ""
    # Each face is sent once, as a CSS background, not once per bubble: a long chat stays light on a phone.
    rows = [f'<style>.chat .face.them {{ background-image: url("{them}"); }} .chat .face.you {{ background-image: url("{you}"); }}</style>']
    for number, entry in enumerate(log):
        style = "" if number >= len(log) - 2 else ' style="animation:none"'  # only the newest lines animate
        if entry["who"] == "you":
            act = " act" if entry.get("act") else ""
            rows.append(f'<div class="bubble you"{style}><i class="face you"></i><div class="say{act}">{esc(entry["text"])}</div></div>')
            continue
        unlock = ""
        if entry.get("unlocked"):
            unlock = '<span class="unlock">' + board.icon("unlock") + " Unlocked: " + esc(", ".join(engine.label(i) for i in entry["unlocked"])) + "</span>"
        note = FALLBACK_NOTES.get(entry.get("fallback"))
        note = f'<span class="note">{esc(note)}</span>' if note else ""
        rows.append(f'<div class="bubble them"{style}><i class="face them"></i><div class="say">{esc(entry["text"])}{unlock}{note}</div></div>')
        for item in entry.get("caught", []):
            rows.append(
                f'<div class="caught"{style}><b>{board.icon("bolt")} Caught lying</b><small>They said “{esc(item["text"].rstrip("."))}”. '
                f'{esc(proof_name(item["clue"]).capitalize() if item["clue"] else "Your evidence")} says otherwise.</small>'
                f'{lie_meaning_html(item)}</div>'
            )
        if entry.get("cracked"):
            after = "Their story broke. Write down what slipped out."
            rows.append(f'<div class="caught cracked"{style}><b>{board.icon("bolt")} Cracked</b><small>{after}</small></div>')
        if entry.get("think"):
            rows.append(f'<div class="bubble think"{style}><i class="face you"></i><div class="say">{esc(entry["think"])}</div></div>')
    return '<div class="chat">' + "".join(rows) + "</div>"


def topic_label(topic, asked, tip=None):
    """A question's button: an arrow on the suggested next step, ✓ once asked."""
    label = TOPICS[topic][0]
    if topic == tip:
        return f"→ {label}"
    return f"✓ {label}" if topic in asked else label


def card_label(clue_id, shown, tip=None):
    """An evidence card to show, by number and name: an arrow on the suggested next step, ✓ once shown to this suspect."""
    name = board.CARD_NAMES.get(clue_id)
    number = engine.number(clue_id)
    label = f"{number} · {name}" if name else str(number)
    if clue_id == tip:
        return f"→ {label}"
    return f"✓ {label}" if clue_id in shown else label


def progress_html(progress):
    """How much of this suspect you have covered, and a clear sign once there is nothing left to ask."""
    cards = f'{progress["shown"]} of {progress["cards"]}' if progress["cards"] else "none found yet"
    line = (f'<div class="progress-line"><span>Questions asked <b>{progress["asked"]} of {progress["questions"]}</b></span>'
            f'<span>Evidence shown <b>{cards}</b></span></div>')
    if progress["done"]:
        line += (f'<div class="all-asked">{board.icon("check")} Nothing left to ask. '
                 "Find a new evidence card, then come back.</div>")
    return line


OUT_OF_TIME = "It is 09:00. No more questions or searches: make your accusation."


def panel_suspect(game, suspect):
    from game import ai

    brief = engine.character_brief(game, suspect)
    uri = board.suspect_picture(suspect, rattled(game, suspect)) or ""
    persona = brief["persona"].split(";")[0].split(". ")[0].rstrip(".") + "."
    nerves = engine.nerves(game, suspect)  # 0 to 100, decided by the engine; at 100 they crack
    broke = " broke" if suspect in game.cracked else ""
    st.markdown(
        f'<div class="who-head"><img src="{uri}" alt="{esc(brief["name"])}"><div>'
        f'<div class="kicker">Interrogation</div><h3>{esc(brief["name"])}</h3><div class="line">{esc(persona)}</div>'
        f'<div class="nerves{broke}" title="Show them different evidence and catch their lies. At full nerves they crack.">'
        f'Nerves <i><b style="width:{nerves}%"></b></i>{" Cracked" if broke else ""}</div>'
        "</div></div>",
        unsafe_allow_html=True,
    )
    log = st.session_state.get("chats", {}).get(suspect, [])
    with st.container(key="chat_log", height=260 if log else "content", autoscroll=True):
        if log:
            st.markdown(chat_html(log, suspect), unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="empty-chat">Ask {esc(brief["name"])} something, or show them an evidence card.</div>',
                        unsafe_allow_html=True)
    cost = case["clock"]["question_cost"]
    step = guide(game) or {}
    tip = step if step.get("suspect") == suspect else {}
    asked = {e["topic"] for e in game.history if e.get("action") == "ask" and e.get("suspect") == suspect}
    st.markdown(progress_html(engine.suspect_progress(game, suspect)), unsafe_allow_html=True)
    if engine.out_of_time(game):  # every question would be refused now: say so before the pills
        st.warning(OUT_OF_TIME, icon=":material/gavel:")
    # Nobody asks the Teaching Assistant about the Teaching Assistant.
    topics = [t for t in TOPICS if t in engine.topics_for(suspect)]
    st.pills(f"Ask · {cost} min", topics, format_func=lambda t: topic_label(t, asked, tip.get("topic")),
             key="ask_topic", on_change=ask_topic)
    opened = [c["id"] for c in engine.clue_list(game) if c["state"] == "open"]
    if opened:
        shown = {e["clue"] for e in game.history if e.get("action") == "present" and e.get("suspect") == suspect}
        show_tip = tip.get("clue") if tip.get("do") == "show" else None
        st.pills(f"Show an evidence card · {cost} min", opened, format_func=lambda i: card_label(i, shown, show_tip),
                 key="show_clue", on_change=show_evidence, help="Show them evidence. The right card breaks a lie.")
    question = st.chat_input(f"Or type your own question · {cost} min", max_chars=ai.MAX_QUESTION_LENGTH, key="typed")
    if question:

        def ask_and_note_fallback(game):
            answer = ai.ask(engine, game, suspect, question, cloud_key=cloud_key)
            return answer, game.history[-1].get("fallback")

        with st.spinner(f"{brief['name']} is thinking…"):
            result = run(ask_and_note_fallback)
        if result:
            answer, fallback = result
            sound("tick")
            say(suspect, {"who": "you", "text": HIDDEN_QUESTION if answer.get("blocked") else question})
            say(suspect, {"who": "them", "text": answer["reply"], "unlocked": answer["unlocked"], "fallback": fallback})
            if not answer.get("blocked"):
                think(suspect, engine.reaction(current_game(), unlocked=bool(answer["unlocked"])))
        st.rerun()


# ---- Panel: one clue ------------------------------------------------------------------


def hunch_html(hunches, log):
    """The detective's inner voice: a line per broken story, quoting the log line that caught their eye."""
    face = board.find_picture("detectives", player_avatar()) or ""
    rows = []
    for hunch in hunches:
        quote = ""
        line = next((x for x in (log or "").splitlines() if hunch["mark"] and hunch["mark"] in x), None)
        if line:
            marked = esc(line.strip()).replace(esc(hunch["mark"]), f'<mark>{esc(hunch["mark"])}</mark>', 1)
            quote = f"<code>{marked}</code>"
        rows.append(f'<div class="hunch"><img src="{face}" alt=""><div><p>"{esc(hunch["line"])}"</p>{quote}</div></div>')
    return "".join(rows)


def clue_body_html(text):
    """A clue's text as HTML: lines starting with "- " become a bulleted list, other lines paragraphs."""
    parts, points = [], []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("- "):
            points.append(f"<li>{esc(line[2:])}</li>")
            continue
        if points:
            parts.append("<ul>" + "".join(points) + "</ul>")
            points = []
        if line:
            parts.append(f"<p>{esc(line)}</p>")
    if points:
        parts.append("<ul>" + "".join(points) + "</ul>")
    return "".join(parts)


def panel_clue(game, clue_id, fresh):
    item = next(c for c in engine.clue_list(game) if c["id"] == clue_id)
    verb = "Search it" if item["kind"] == "location" else "Open it"
    st.markdown(f'<div class="kicker">{board.icon(board.KIND_ICON[item["kind"]])} Evidence {item["number"]}</div><h3>{esc(item["title"])}</h3>',
                unsafe_allow_html=True)
    if item["state"] == "locked":
        st.markdown(f'<div class="facedown locked">{board.icon("lock")}</div>', unsafe_allow_html=True)
        hints = engine.hint_list(game)
        if engine.hard(game):
            st.caption("Locked. Hard mode: no hints. Question suspects and show them evidence cards to unlock it.")
        elif clue_id in hints:
            st.info(hints[clue_id], icon=":material/lightbulb:")
        else:
            st.caption("Locked. Question suspects and show them evidence cards to unlock it.")
            if st.button(f"Hint · {engine.hint_cost()} min", key=f"hint_{clue_id}", icon=":material/lightbulb:", use_container_width=True):
                run(engine.hint, clue_id)
                st.rerun()
        return
    if item["state"] == "available":
        st.markdown('<div class="facedown">?</div>', unsafe_allow_html=True)
        if not engine.can_afford(game, case["clock"]["clue_cost"]):
            st.caption(f"Not enough time left to {verb.lower()} before 09:00. Make your accusation.")
        if st.button(f"{verb} · {case['clock']['clue_cost']} min", key=f"open_{clue_id}", type="primary", icon=":material/search:",
                     use_container_width=True):
            if run(engine.open_clue, clue_id):
                sound("flip")
            st.session_state.fresh = st.session_state.get("fresh", []) + [clue_id]
            st.rerun()
        return
    clue = engine.read_clue(game, clue_id)
    picture = board.find_picture("clues", clue_id)
    art = f'<img src="{picture}" alt="">' if picture else ""  # no placeholder: the words are the evidence
    style = "" if clue_id in fresh else ' style="animation:none"'
    hunches = engine.hunches(game, clue_id)
    body = clue_body_html(clue["text"])
    for hunch in hunches:
        if hunch["mark"] and hunch["mark"] in clue["text"]:
            body = body.replace(esc(hunch["mark"]), f'<mark>{esc(hunch["mark"])}</mark>', 1)
    fact = engine.key_fact(game, clue_id)
    if fact:
        st.markdown(f'<div class="keyfact"><small>In short</small>{esc(fact)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="evidence"{style}>{art}<div class="body">{body}</div></div>', unsafe_allow_html=True)
    if hunches:
        st.markdown(hunch_html(hunches, clue["log"]), unsafe_allow_html=True)
    else:
        musing = engine.musing(game, clue_id)
        if musing:
            st.markdown(hunch_html([{"line": musing, "mark": ""}], ""), unsafe_allow_html=True)
    if clue["log"]:
        query = st.text_input("Search the log", key=f"search_{clue_id}", placeholder="A card number, a name, a time…")
        matches, total = search_log(clue["log"], query)
        if query.strip():
            st.caption(f"{len(matches)} of {total} lines match.")
        if matches:
            st.code("\n".join(matches), language=None, wrap_lines=True)
    if clue["hidden_text"] and st.toggle("Look closer", key=f"hidden_{clue_id}"):
        st.warning(clue["hidden_text"])
        st.caption(AI_TRAP_NOTE)
    if engine.out_of_time(game):
        st.caption(OUT_OF_TIME)
    shown = {e["suspect"] for e in game.history if e.get("action") == "present" and e.get("clue") == clue_id}
    st.pills(
        f"Show this card to · {case['clock']['question_cost']} min", list(case["suspects"]),
        format_func=lambda s: ("✓ " if s in shown else "") + board.short_name(case["suspects"][s]["name"]),
        key=f"show_to_{clue_id}", on_change=show_to, args=(clue_id,),
        help="The right card breaks a lie. Their answer opens in their interrogation.",
    )


# ---- Panel: case sheet and accusation ----------------------------------------------------


def clue_fact(game, clue_id):
    """One line to remember a clue by: the detail that stood out, or the clue's first sentence."""
    for hunch in engine.hunches(game, clue_id, include_caught=True):
        if hunch["mark"]:
            return hunch["mark"]
    text = engine.read_clue(game, clue_id)["text"].strip().splitlines()[0].removeprefix("- ")
    first = re.split(r"(?<=[a-z0-9)\"'][.!?])\s", text, maxsplit=1)[0]
    return first if len(first) <= 90 else first[:87].rstrip() + "…"


def notebook_notes(game):
    """The automatic half of the notebook: every card found, every story told, every lie.

    What the evidence rules out is shown once, on the Cross off tab, beside the answers it crosses off."""
    opened = [e["clue"] for e in game.history if e.get("action") == "open"]
    if not opened and not game.history:
        st.caption("Empty for now. Everything you find and hear is written down here by itself.")
        return
    st.markdown(f"#### Evidence · {len(opened)}")
    for clue_id in opened:
        name = board.CARD_NAMES.get(clue_id, case["clues"][clue_id]["title"])
        st.button(f"**{engine.number(clue_id)}** {plain(name)} · {plain(clue_fact(game, clue_id))}", key=f"note_{clue_id}", type="tertiary",
                  on_click=set_focus, args=("clue", clue_id), use_container_width=True)
    questioned = []
    for event in game.history:
        if event.get("suspect") in case["suspects"] and event["suspect"] not in questioned:
            questioned.append(event["suspect"])
    if questioned:
        caught = {}
        for item in engine.contradiction_list(game):
            caught.setdefault(item["suspect"], []).append(item)
        st.markdown(f"#### Their stories · {len(questioned)}")
        rows = []
        for suspect in questioned:
            brief = engine.character_brief(game, suspect)
            lies = "".join(
                f'<span class="lie-note">{board.icon("bolt")} “{esc(item["text"].rstrip("."))}” <em>broken by {esc(proof_name(item["clue"]) if item["clue"] else "a clue")}</em></span>'
                for item in caught.get(suspect, [])
            )
            rows.append(f'<div class="story-note"><b>{esc(board.short_name(brief["name"]))}</b>'
                        f'<span>“{esc(brief["cover"].strip())}”</span>{lies}</div>')  # whole story: a cut could hide the line a card breaks
        st.markdown("".join(rows), unsafe_allow_html=True)


def panel_sheet():
    game = current_game()
    st.markdown('<div class="kicker">Notebook</div><h3>Everything you have found</h3>', unsafe_allow_html=True)
    notes, sheet = st.tabs(["Notes", "Cross off"])
    with notes:
        notebook_notes(game)
    with sheet:
        st.caption("Cross off what can't be. Proven ones are crossed off for you. What is left is your accusation.")
        for column in COLUMNS:
            options = case["accusation"][column]
            proven = proven_out(column)
            st.session_state[f"sheet_{column}"] = crossed(column)  # proven ones stay crossed off
            left = len(options) - len(crossed(column))
            st.pills(f"{COLUMN_ICONS[column]} {column.capitalize()} · {left} left", [o["id"] for o in options],
                     format_func=lambda o, c=column: label(c, o), selection_mode="multi", key=f"sheet_{column}",
                     on_change=keep_crossed, args=(column,))
            if proven:
                st.markdown(
                    '<div class="proof">' + "".join(
                        f"<span>{board.icon('check')} {esc(label(column, o))} <em>ruled out by {esc(proof_name(by))}</em></span>"
                        for o, by in proven.items()
                    ) + "</div>",
                    unsafe_allow_html=True,
                )
    if st.button("Accuse", type="primary", icon=":material/balance:", use_container_width=True, key="to_accuse"):
        set_focus("accuse")
        st.rerun()


def proof_name(by):
    """How a ruling-out is credited: an evidence card, or your own wrong accusation."""
    return "your accusation" if by == "accusation" else f"evidence {engine.number(by)}"


def verdict_html(right):
    return '<div class="verdict">' + "".join(
        f'<div class="{"ok" if c in right else "no"}"><span>{"✓" if c in right else "✗"}</span>{c.upper()}</div>' for c in COLUMNS
    ) + "</div>"


@st.dialog("Are you sure?")
def accusation_confirmation():
    choice = st.session_state.get("pending_accusation")
    if not choice:
        return
    strikes_left = case["max_strikes"] - current_game().strikes
    tries = "try" if strikes_left == 1 else "tries"
    st.write(f"{strikes_left} {tries} left. A wrong accusation costs one. Accuse?")
    if st.button("Yes, accuse", type="primary", key="confirm_accuse", icon=":material/gavel:"):
        st.session_state.pop("pending_accusation", None)
        proofs = {c: st.session_state.get(f"accuse_proof_{c}") for c in COLUMNS}
        result = run(engine.accuse, *(choice[c] for c in COLUMNS), {c: v for c, v in proofs.items() if v})
        if result:
            sound("thud" if result["status"] == "playing" else "stamp")
        if result and result["status"] == "playing":
            st.session_state.verdict = engine.right_parts(current_game())
        st.rerun()
    if st.button("Back", key="cancel_accuse", icon=":material/arrow_back:"):
        st.session_state.pop("pending_accusation", None)
        st.rerun()


def panel_accuse(game):
    strikes_left = case["max_strikes"] - game.strikes
    st.markdown(f'<div class="kicker">The accusation · {strikes_left} {"try" if strikes_left == 1 else "tries"} left</div>'
                "<h3>Who did it, how, where and why?</h3>", unsafe_allow_html=True)
    verdict = st.session_state.get("verdict")
    if verdict is not None:
        st.markdown(verdict_html(verdict), unsafe_allow_html=True)
        st.caption(f"{len(verdict)} of 4 right. Keep the ✓ parts and rethink the ✗ ones." if verdict
                   else "0 of 4 right. Nothing to keep: rethink all four.")
    opened = [c["id"] for c in engine.clue_list(game) if c["state"] == "open"]
    for column in COLUMNS:
        out = set(crossed(column))
        st.pills(f"{COLUMN_ICONS[column]} {column.capitalize()}", [o["id"] for o in case["accusation"][column]],
                 format_func=lambda o, c=column, out=out: label(c, o) + (" ✗" if o in out else ""), key=f"accuse_{column}")
        if opened:
            st.selectbox("Proof (optional)", [None] + opened, key=f"accuse_proof_{column}",
                         format_func=lambda i: "No proof" if i is None else f"{engine.number(i)} · {board.CARD_NAMES.get(i, case['clues'][i]['title'])}",
                         help="The evidence card that proves this answer. A right proof adds 5 to your rank if you solve the case.")
    if st.button("Accuse", type="primary", icon=":material/balance:", use_container_width=True, key="accuse_go"):
        choice = {c: st.session_state.get(f"accuse_{c}") for c in COLUMNS}
        missing = [c for c in COLUMNS if choice[c] is None]
        if missing:
            st.warning(f"Pick one in each row first. Missing: {', '.join(missing)}.")
            return
        st.session_state.pending_accusation = choice
    if st.session_state.get("pending_accusation"):
        accusation_confirmation()


# ---- The finale ------------------------------------------------------------------------


def case_summary(game):
    """How the player did: time, clues, questions, lies caught and wrong accusations."""
    clues = engine.clue_list(game)
    opened = sum(1 for c in clues if c["state"] == "open")
    questions = sum(1 for event in game.history if event.get("action") in ("ask", "present"))
    limit = case["clock"]["limit_minutes"]
    hours, minutes = divmod(game.clock, 60)
    with st.container(border=True, key="case_summary"):
        time_col, clue_col, question_col, caught_col, wrong_col = st.columns(5)
        time_col.metric("Time used", f"{hours}h {minutes:02d}m", help=f"Out of {limit // 60} hours, before 09:00.")
        clue_col.metric("Evidence found", f"{opened} of {len(clues)}")
        question_col.metric("Questions asked", questions)
        caught_col.metric("Lies caught", len(game.contradictions))
        wrong_col.metric("Wrong accusations", game.strikes)


def share_text(game, rank):
    """A spoiler-free line to paste in a chat: rank, time and lies caught, never the culprit."""
    lies = len(game.contradictions)
    lies_text = f"{lies} {'lie' if lies == 1 else 'lies'} caught"
    if game.status != "solved":
        return f"The trail went cold on me in Death of the Final Exam ({lies_text}). Can you name who leaked the exam? {APP_URL}"
    wrong = f", {game.strikes} wrong {'guess' if game.strikes == 1 else 'guesses'}" if game.strikes else ""
    mode = " in hard mode" if engine.hard(game) else ""
    return (f"I solved Death of the Final Exam{mode} at {engine.clock_label(game)} as {rank['title']} "
            f"({rank['score']}/100), {lies_text}{wrong}. Can you beat it? {APP_URL}")


def rank_card(game):
    rank = engine.rank(game)
    solved = game.status == "solved"
    score = f'<span class="score">{rank["score"]} / 100</span>' if solved else ""
    st.markdown(f'<div class="rank{"" if solved else " cold"}"><small>YOUR RANK</small><b>{esc(rank["title"])}</b>{score}</div>',
                unsafe_allow_html=True)
    if solved:
        st.caption("50 for solving, up to 25 for time left, 5 per lie caught (up to 20), 5 per answer proved "
                   "with the right evidence (up to 20); minus 3 per hint and 10 per wrong accusation.")
        proven = engine.proven(game)
        if proven:
            st.caption("Your proofs: " + " · ".join(
                f"{c.capitalize()} {'✓' if proven[c] else '✗'}" if c in proven else f"{c.capitalize()} –" for c in COLUMNS))
    st.caption("Share the game")
    st.code(share_text(game, rank), language=None, wrap_lines=True)


def finale(game):
    scene = denouement(game)
    solution = engine.solution(game)
    solved = game.status == "solved"
    heading = "Case closed" if solved else "The trail went cold"
    lies = len(game.contradictions)
    facts = '<div class="facts">' + "".join(
        f"<div><small>{c.upper()}</small>{esc(label(c, solution[c]))}</div>" for c in COLUMNS
    ) + "</div>"
    if solved:
        uri = board.find_picture("suspects", solution["who"]) or ""
        portrait = f'<div class="mug"><img src="{uri}" alt=""><span class="slam">GUILTY</span></div>'
        sub = f"Solved at {engine.clock_label(game)} · {lies} {'lie' if lies == 1 else 'lies'} caught"
    else:
        portrait = '<div class="cold-stamp">CASE COLD</div>'
        sub = "The case remains unsolved. The exam is cancelled."
    medals = "".join(f"<span>{board.icon('medal')} {esc(b['title'])}</span>" for b in engine.badge_list(game))
    _, middle, _ = st.columns([1, 3, 1])
    middle.markdown(
        f'<div class="finale{"" if solved else " cold"}">{portrait}'
        f'<div class="title">{heading}</div><div class="sub">{esc(sub)}</div>{facts if solved else ""}'
        f'{f"<div class=medals>{medals}</div>" if medals else ""}</div>',
        unsafe_allow_html=True,
    )
    marker = pending_sound()
    if marker:
        deck(data=marker, key="finale_sound", height=1)
    with middle:
        # A cold case stays unsolved in the story; its answer is shown separately to the player.
        if scene:
            scene_label = "Read the confrontation" if solved else "The case remains unsolved"
            with st.expander(scene_label, icon=":material/history_edu:",
                             expanded=True):
                for paragraph in scene.split("\n\n"):
                    st.markdown(plain(paragraph))
        if not solved:
            st.markdown("#### The correct solution")
            st.caption("For you, the player: the investigation itself remained unsolved.")
            st.markdown(facts, unsafe_allow_html=True)
        rank_card(game)
        case_summary(game)
        st.download_button(
            "Download the honour council report",
            data=report.build(engine, game, st.session_state.get("player_name") or "Detective"),
            file_name="honour-council-report.md",
            mime="text/markdown",
            icon=":material/description:",
            use_container_width=True,
        )
        if st.button("Play a new case", type="primary", icon=":material/refresh:", use_container_width=True):
            new_case()
            st.rerun()


# ---- The start screen ------------------------------------------------------------------

STORY_HTML = (
    "Thursday, 23:47, a storm over Carcavelos. An anonymous number posts tomorrow's <b>Investments exam</b> "
    "in the class group chat, to all 212 students. The exam is at <b>09:00</b>. Before then, find out <b>who</b> leaked it, <b>how</b>, <b>where</b> and <b>why</b>."
)


def whos_who_html():
    """The five suspects, one short line each, so a new player knows who is who."""
    return '<div class="kicker">Who\'s who</div><ul class="whos-who">' + "".join(
        f'<li><img src="{board.find_picture("suspects", sid) or ""}" alt="">'
        f'<span><b>{esc(board.short_name(s["name"]))}</b>{esc(s.get("role", ""))}</span></li>'
        for sid, s in case["suspects"].items()
    ) + "</ul>"


HOURS = case["clock"]["limit_minutes"] // 60
HOW_TO_PLAY = (
    '<ol class="how-to">'
    f'<li>{board.icon("search")}<span><b>Search</b> a new place or document</span><em>−{case["clock"]["clue_cost"]} min</em></li>'
    f'<li>{board.icon("ask")}<span><b>Question</b> the five suspects</span><em>−{case["clock"]["question_cost"]} min</em></li>'
    f'<li>{board.icon("bolt")}<span><b>Show</b> the evidence card that breaks a lie</span><em>−{case["clock"]["question_cost"]} min</em></li>'
    f'<li>{board.icon("scale")}<span><b>Accuse</b> who, how, where and why</span><em>no time · {case["max_strikes"]} tries</em></li>'
    "</ol>"
)
# The rules in one box: how time works, then what each action costs.
CLOCK_RULE = (
    f'<div class="clock-rule"><b class="headline">Every action costs time. Use your {HOURS} hours well.</b>'
    "<span>The clock runs from midnight to 09:00, and every search and every question moves it forward. "
    "At 09:00 you can no longer search or ask: you can only accuse.</span>" + HOW_TO_PLAY + "</div>"
)


MODE_LABELS = {"normal": "Normal", "hard": "Hard"}
MODE_NOTE = "Hard mode is the same case with one difference: no tips."


def pick_mode():
    """Normal or hard, chosen on the start screen before the first move."""
    game = current_game()
    choice = st.session_state.get("mode_choice") or "normal"
    if not game.history and game.mode != choice:
        engine.set_mode(game, choice)
        save(game)


def calm_switch():
    st.session_state.calm = bool(st.session_state.get("calm_switch"))


def pick_detective(avatar):
    st.session_state.player_avatar = avatar


def finish_intro():
    st.session_state.intro_done = True
    game = current_game()
    if not game.history and not engine.hard(game) and "tutorial" not in st.session_state:
        st.session_state.tutorial = True  # the guided first minute teaches by doing


@st.dialog("The exam has leaked", width="large", on_dismiss=finish_intro)
def intro_dialog():
    """The story and the rules in one glance, and who you are, before the first move."""
    cover = board.data_uri(str(COVER))  # beside the briefing (hidden on phones)
    if cover:
        art, brief = st.columns([5, 6], gap="large")
        with art:
            st.markdown(f'<div class="cover-art" style="background-image:url({cover})"></div>', unsafe_allow_html=True)
    else:
        brief = st.container()
    with brief:
        st.markdown(f'<div class="kicker">{esc(TITLE)}</div>', unsafe_allow_html=True)
        st.markdown(f'<p class="story">{STORY_HTML}</p>' + PAGE_CSS + CLOCK_RULE + whos_who_html(), unsafe_allow_html=True)
        st.markdown('<div class="kicker">Choose your mode</div>', unsafe_allow_html=True)
        game = current_game()
        if game.history:
            st.caption(f"{MODE_LABELS[game.mode]} mode. The mode is chosen before the first move.")
        else:
            with st.container(key="mode_pick"):
                st.segmented_control("Mode", list(MODE_LABELS), format_func=MODE_LABELS.get, default=game.mode,
                                     key="mode_choice", on_change=pick_mode, label_visibility="collapsed")
                st.caption(MODE_NOTE)
        st.markdown('<div class="kicker">Choose your detective</div>', unsafe_allow_html=True)
        chosen = player_avatar()
        # Each portrait is its own button (keyboard and screen readers get "Play as her/him").
        st.markdown("<style>" + "".join(
            f'.st-key-pick_{avatar} button {{ background-image: url("{board.find_picture("detectives", avatar) or ""}"); }}'
            for avatar in AVATARS
        ) + "</style>", unsafe_allow_html=True)
        with st.container(key="pick_buttons"):
            for column, (avatar, text) in zip(st.columns(len(AVATARS)), AVATARS.items()):
                with column:
                    st.button(text, key=f"pick_{avatar}", type="primary" if avatar == chosen else "secondary",
                              help=None, on_click=pick_detective, args=(avatar,))
        st.text_input("Your name", key="player_name", placeholder="Detective", max_chars=24)
        st.toggle("Calm mode: no animations, no sounds", value=calm(), key="calm_switch", on_change=calm_switch,
                  help="Nothing moves, blinks or plays. You can switch it any time with the moon button at the top.")
        if st.button("Start the investigation", type="primary", icon=":material/search:", use_container_width=True):
            finish_intro()
            st.rerun()


# ---- The page ---------------------------------------------------------------------------

game = current_game()
st.markdown(PAGE_CSS, unsafe_allow_html=True)
if calm():
    st.markdown(CALM_CSS, unsafe_allow_html=True)

# Pop-ups stay long enough to read (Streamlit's default is 4 seconds); the cross closes them sooner.
TOAST_SECONDS = 9
flash = st.session_state.pop("flash", None)
if flash:
    getattr(st, flash[0])(flash[1])
toast = st.session_state.pop("toast", None)
if toast:
    st.toast(toast[0], icon=toast[1], duration=TOAST_SECONDS)
night = st.session_state.pop("night_toast", None)
if night:
    st.toast(night, icon=":material/thunderstorm:", duration=TOAST_SECONDS)
refusal = st.session_state.pop("refusal", None)
if refusal:
    st.toast(refusal, icon=":material/warning:", duration=TOAST_SECONDS)
fresh = st.session_state.pop("fresh", [])

if game.status != "playing":
    finale(game)
    st.stop()

clues = engine.clue_list(game)
board_column, side_column = st.columns([3, 2], gap="medium")
with board_column:
    draw_board(game, clues, fresh)
with side_column:
    draw_suspects(game)
    with st.container(key="panel"):
        coach_card(game)  # first in the panel, which every tap scrolls into view on phones
        kind, value = focus()
        if kind == "suspect" and value in case["suspects"]:
            panel_suspect(game, value)
        elif kind == "clue" and value in case["clues"]:
            panel_clue(game, value, fresh)
        elif kind == "spot" and value in board.MAP_SPOTS:
            st.markdown(f'<div class="kicker">{board.icon("pin")} Off campus</div><h3>{esc(board.MAP_SPOTS[value][2])}</h3>', unsafe_allow_html=True)
            st.write(board.MAP_SPOTS[value][3])
        elif kind == "lies":
            panel_lies(game)
        elif kind == "sheet":
            panel_sheet()
        elif kind == "accuse":
            panel_accuse(game)
        else:
            panel_home(game)
    next_step_button(game)
save_corner()

# Called last, so the story and rules open over the game on a new case.
if not st.session_state.get("intro_done", bool(game.history)):
    intro_dialog()
