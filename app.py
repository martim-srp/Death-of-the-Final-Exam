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
from game.engine import Game, GameError  # noqa: E402


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


def run(action, *args):
    """Run an engine action, save the game, and turn rule errors into messages.

    Newly unlocked clues pop up as a toast and are dealt into the hand with an animation.
    """
    game = current_game()
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
    return result


def sound(name):
    """Ask the board to play one short sound on the next draw (see board.sfx_html)."""
    st.session_state.sfx = name
    st.session_state.sfx_n = st.session_state.get("sfx_n", 0) + 1


def new_case():
    start_new_game()
    for key in [k for k in st.session_state if str(k).startswith(("sheet_", "accuse_"))]:
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
    mine = list(st.session_state.get(f"sheet_{column}") or [])
    return mine + [o for o in proven_out(column) if o not in mine]


def ruled_out(suspect):
    return suspect in crossed("who")


def focus():
    """What the side panel shows: ("home"), ("suspect", id), ("clue", id), ("spot", id), ("sheet") or ("accuse")."""
    return st.session_state.get("focus") or ("home", None)


def set_focus(kind, value=None):
    st.session_state.focus = (kind, value)
    if kind == "suspect":
        st.session_state.suspect = value


def go_next():
    """The phone's next-step button: open what the next step points at."""
    step = engine.next_step(current_game())
    parsed = board.parse_act(board.goal_act(step), case["suspects"], case["clues"]) if step else None
    if parsed:
        set_focus(*parsed)


def next_step_button(game):
    """On phones the strip above the map scrolls out of sight, so the panel ends with the next step too."""
    step = engine.next_step(game)
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
    elif kind == "tour_done":
        st.session_state.tour_done = True
    else:
        set_focus(kind, value)


# ---- The D4 chart --------------------------------------------------------------------

def denouement(game):
    """The closing scene of this game's variant. Only once the case is closed."""
    engine.solution(game)  # raises GameError while the game is still running
    text = case["variants"][game.variant].get("denouement", "")
    return text.format_map(game.variables)


# ---- Page style ----------------------------------------------------------------------

PAGE_CSS = """
<style>
@import url("https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Special+Elite&display=swap");
/* One look everywhere: Playfair for titles, a serif for in-world text, a typewriter for labels, the app font for controls. */
:root { --display: "Playfair Display", Georgia, serif; --prose: Georgia, "Times New Roman", serif;
  --label: "Special Elite", "Courier New", monospace; --ink: #efe6d8; --gold: #e8c27a; --red: #c0392b;
  --paper: #1c1613; --line: #3a2e28; }
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none; }
[data-testid="stMainBlockContainer"] { padding: 1rem 1.2rem 1.5rem; max-width: 1480px; }
.stApp { font-variant-numeric: lining-nums; }
header[data-testid="stHeader"] { display: none; }
[data-testid="stElementToolbar"] { display: none; }  /* chart download/fullscreen buttons floated over the detective's line */
.st-key-next_phone { display: none; }  /* the game is full screen; Streamlit's bar covered the status bar */
.st-key-panel h3, .finale .title, [data-testid="stDialog"] h2 { font-family: var(--display) !important; }
.st-key-panel { background: #1c1613; border: 1px solid #3a2e28; border-radius: 14px; padding: 0.9rem 1rem 1rem; gap: 0.6rem; }
.st-key-panel h3 { margin: 0 0 0.55rem !important; padding: 0.1rem 0 0.1rem; font-size: 1.35rem; line-height: 1.35; }
.kicker { font: 600 0.72rem var(--label); letter-spacing: 0.18em; text-transform: uppercase; color: #e8c27a; }
.who-head { padding-bottom: 0.9rem; display: flex; gap: 0.8rem; align-items: center; }
.st-key-chat_log { margin-top: 0.5rem; }
.who-head img { width: 64px; height: 80px; object-fit: cover; border-radius: 10px; border: 2px solid #c0392b; }
.nerves { display: flex; align-items: center; gap: 0.4rem; font: 600 0.68rem var(--label); letter-spacing: 0.12em;
  text-transform: uppercase; opacity: 0.85; margin-top: 0.25rem; }
.nerves i { width: 110px; height: 6px; background: #3a2e28; border-radius: 3px; overflow: hidden; display: inline-block; }
.nerves b { display: block; height: 100%; background: linear-gradient(90deg, #e8c27a, #e0645a); transition: width 0.6s; }
.who-head .line { font-size: 0.85rem; opacity: 0.75; line-height: 1.3; }
.chat { display: flex; flex-direction: column; gap: 0.55rem; padding: 0.2rem 0.1rem; }
.bubble { display: flex; gap: 0.5rem; align-items: flex-end; max-width: 92%; animation: rise 0.35s ease-out both; }
.bubble img { width: 30px; height: 30px; border-radius: 50%; object-fit: cover; object-position: top; flex: none; }
.bubble .say { padding: 0.5rem 0.75rem; border-radius: 16px; font-family: var(--prose); font-size: 0.95rem; line-height: 1.35; }
.bubble.them .say { background: #2b221d; border: 1px solid #3f322b; border-bottom-left-radius: 4px; }
.bubble.you { margin-left: auto; flex-direction: row-reverse; }
.bubble.you .say { background: #5a1d16; border: 1px solid #7a2c22; border-bottom-right-radius: 4px; }
.bubble.think { margin-left: auto; flex-direction: row-reverse; max-width: 86%; }
.bubble.think img { width: 24px; height: 24px; opacity: 0.85; }
.bubble.think .say { background: transparent; border: 0; border-right: 2px solid var(--gold); border-radius: 0; padding: 0.15rem 0.6rem;
  font: italic 0.88rem/1.35 var(--display); color: #cdbfa8; text-align: right; }
.bubble.you .say.act { font-style: italic; background: #2a2a1e; border-color: #4a4a30; }
.bubble .note { display: block; margin-top: 0.35rem; font-size: 0.72rem; opacity: 0.6; font-family: inherit; }
.bubble .unlock { display: block; margin-top: 0.35rem; font: 600 0.75rem var(--label); color: #e8c27a; }
.caught { margin: 0.2rem auto 0.3rem; text-align: center; animation: slam 0.5s cubic-bezier(.2,1.6,.4,1) both; }
.caught b { display: inline-block; border: 3px solid #e0645a; color: #e0645a; padding: 0.1rem 0.6rem; transform: rotate(-4deg);
  font: 800 1.15rem var(--label); letter-spacing: 0.12em; text-transform: uppercase; }
.caught.cracked b { border-color: #e8c27a; color: #e8c27a; transform: rotate(3deg); }
.nerves.broke { color: #e0645a; }
.caught small { display: block; font-size: 0.8rem; opacity: 0.8; margin-top: 0.3rem; }
.empty-chat { text-align: center; opacity: 0.6; padding: 1.6rem 0.5rem; font-size: 0.9rem; }
.evidence { position: relative; box-sizing: border-box; width: 100%; max-width: 100%; border-radius: 12px; overflow: hidden;
  background: #1c1613; color: #efe6d8; border: 1px solid #3a2e28; margin-bottom: 0.9rem;
  box-shadow: 0 8px 24px rgba(0,0,0,0.45); animation: flip 0.55s ease-out both; }
.evidence .body ul { margin: 0; padding-left: 1.1rem; }
.evidence .body li { margin: 0 0 0.35rem; }
.evidence .body p { margin: 0 0 0.5rem; }
.evidence img { width: 100%; display: block; max-height: 260px; object-fit: cover; }
.evidence .body { padding: 0.85rem 1rem 1rem; font-family: var(--prose); font-size: 0.95rem; line-height: 1.5;
  overflow-wrap: anywhere; white-space: normal; border-left: 3px solid #8a2a1f; }
.facedown { box-sizing: border-box; border-radius: 12px; height: 150px; display: flex; align-items: center; justify-content: center;
  font: 700 2.6rem var(--display); border: 1px solid #7a2c22; margin-bottom: 0.9rem;  /* room before the button under it */
  background: repeating-linear-gradient(45deg, #5a1d16 0 10px, #6e241b 10px 20px); color: #f4d9a0; }
.facedown.locked { background: repeating-linear-gradient(45deg, #2a221e 0 10px, #332924 10px 20px); border-color: var(--line); color: #8a7a6a; }
.lead { display: flex; gap: 0.6rem; align-items: flex-start; background: #241c18; border-left: 3px solid #e8c27a; border-radius: 8px;
  padding: 0.5rem 0.7rem; margin-bottom: 0.4rem; font-size: 0.92rem; }
.lead b { font-family: var(--label); color: #e8c27a; }
.tips { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; margin-bottom: 0.9rem; }
.tips div { background: #241c18; border-radius: 10px; padding: 0.6rem; text-align: center; font-size: 0.85rem; line-height: 1.25; }
.tips div span { display: block; font-size: 1.6rem; }
.lie { background: #2a1714; border: 1px solid #5a2a22; border-radius: 10px; padding: 0.45rem 0.7rem; margin-bottom: 0.4rem; font-size: 0.88rem; }
.lie b { color: #e0645a; }
.verdict { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.4rem; animation: shake 0.5s; margin-bottom: 0.6rem; }
.verdict div { text-align: center; border-radius: 10px; padding: 0.5rem 0.2rem; font: 700 0.8rem var(--label); letter-spacing: 0.08em; }
.verdict .ok { background: #1f3a24; color: #8be09a; border: 2px solid #3d7a48; }
.verdict .no { background: #3a1714; color: #ff8a7a; border: 2px solid #7a2c22; }
.verdict span { display: block; font-size: 1.5rem; }
.st-key-panel [data-testid="stButtonGroup"] button { font-size: 0.85rem; height: auto; min-height: 2rem; max-width: 100%; }
.st-key-panel [data-testid="stButtonGroup"] button * { white-space: normal !important; overflow: visible !important;
  text-overflow: clip !important; text-align: left; }
[class*="st-key-sheet_"] button[kind="pillsActive"], [class*="st-key-sheet_"] button[aria-checked="true"] {
  text-decoration: line-through; text-decoration-color: #e0645a; text-decoration-thickness: 2px; opacity: 0.6;
  background: #2a1714 !important; border-color: #5a2a22 !important; color: #efe6d8 !important; }
/* The accusation: a chosen option is filled, so the four picks stand out before you accuse. */
.st-key-accuse_who button[aria-checked="true"], .st-key-accuse_how button[aria-checked="true"],
.st-key-accuse_where button[aria-checked="true"], .st-key-accuse_why button[aria-checked="true"] {
  background: #c0392b !important; border-color: #e8c27a !important; color: #fff !important; font-weight: 700; }
.st-key-accuse_who button[aria-checked="true"] *, .st-key-accuse_how button[aria-checked="true"] *,
.st-key-accuse_where button[aria-checked="true"] *, .st-key-accuse_why button[aria-checked="true"] * { color: #fff !important; }
.st-key-case_summary [data-testid="stMetricValue"] { font-size: 1.4rem; }
.st-key-accuse_go button, .st-key-to_accuse button { padding: 0.7rem; }
.st-key-to_accuse { margin-top: 0.6rem; }
.st-key-accuse_go button p, .st-key-to_accuse button p { font: 700 1.05rem var(--label); letter-spacing: 0.08em; text-transform: uppercase; }
/* The finale */
.finale { text-align: center; padding: 0.5rem 0 0.2rem; }
.finale .mug { position: relative; width: 220px; margin: 0 auto; }
.finale .mug img { width: 220px; aspect-ratio: 4 / 5; object-fit: cover; border-radius: 14px; border: 3px solid #3a2e28;
  box-shadow: 0 16px 40px rgba(0,0,0,0.6); animation: rise 0.8s ease-out both; }
.finale .slam { position: absolute; left: 50%; top: 55%; transform: translate(-50%, -50%) rotate(-14deg); border: 5px solid #e0645a;
  color: #e0645a; background: rgba(20,16,14,0.78); padding: 0.1rem 0.8rem; font: 900 2.2rem var(--label);
  letter-spacing: 0.15em; animation: stamp 0.6s 0.6s cubic-bezier(.2,1.6,.4,1) both; white-space: nowrap; }
.finale.cold .slam { border-color: #9aa7b3; color: #9aa7b3; }
.finale .title { font-size: 2.6rem; font-weight: 700; line-height: 1.2; margin: 1.1rem 0 0.3rem; animation: rise 0.6s 1s ease-out both; }
.finale .sub { opacity: 0.75; animation: rise 0.6s 1.1s ease-out both; }
.facts { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.6rem; margin: 1.2rem 0 0.4rem; }
.facts div { background: var(--paper); color: var(--ink); border: 1px solid var(--line); border-top: 3px solid #8a2a1f;
  border-radius: 10px; padding: 0.7rem 0.6rem; font-family: var(--prose);
  font-size: 0.92rem; line-height: 1.3; animation: deal 0.5s ease-out both; }
.facts div:nth-child(1) { animation-delay: 1.3s; } .facts div:nth-child(2) { animation-delay: 1.5s; }
.facts div:nth-child(3) { animation-delay: 1.7s; } .facts div:nth-child(4) { animation-delay: 1.9s; }
.facts small { display: block; font: 700 0.7rem var(--label); letter-spacing: 0.15em; color: var(--gold); margin-bottom: 0.25rem; }
.rank { text-align: center; margin: 0.4rem auto 0.3rem; animation: rise 0.6s 2.1s ease-out both; }
.rank small { display: block; font: 700 0.7rem var(--label); letter-spacing: 0.15em; color: var(--gold); }
.rank b { display: inline-block; border: 3px solid var(--gold); color: var(--gold); padding: 0.15rem 0.9rem; margin: 0.3rem 0;
  animation: slam 0.5s 2.4s cubic-bezier(.2,1.6,.4,1) both; font: 800 1.5rem var(--label); letter-spacing: 0.1em; text-transform: uppercase; }
.rank .score { display: block; font: 700 1.1rem var(--display); opacity: 0.85; }
.rank.cold b { border-color: #9aa7b3; color: #9aa7b3; }
.medals { margin-top: 0.8rem; display: flex; gap: 0.5rem; justify-content: center; flex-wrap: wrap; }
.medals span { background: #2b221d; border: 1px solid #e8c27a; color: #e8c27a; border-radius: 20px; padding: 0.2rem 0.7rem; font-size: 0.85rem; }
.cover-art { width: 100%; aspect-ratio: 800 / 731; background-size: cover; background-position: center; border-radius: 14px;
  -webkit-mask-image: radial-gradient(closest-side at 50% 50%, #000 62%, transparent 100%);
  mask-image: radial-gradient(closest-side at 50% 50%, #000 62%, transparent 100%); animation: rise 0.8s ease-out; }
.story { font-family: var(--display); font-size: 1.12rem; line-height: 1.5; margin: 0.2rem 0 0.9rem; color: #efe6d8; }
.whos-who { list-style: none; margin: 0.3rem 0 0.9rem; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 0.45rem 0.9rem; }
.whos-who li { display: flex; align-items: center; gap: 0.55rem; margin: 0; font-size: 0.8rem; line-height: 1.25; color: #cdbfa8; }
.whos-who img { width: 34px; height: 34px; border-radius: 50%; object-fit: cover; object-position: top; flex: 0 0 auto; border: 1px solid #3a2e28; }
.whos-who b { display: block; font-family: var(--display); font-size: 0.9rem; color: #efe6d8; }
.clock-rule { display: flex; flex-direction: column; gap: 0.3rem; margin: 0 0 0.9rem; padding: 0.75rem 0.9rem; border: 2px solid #e8c27a; border-radius: 10px; background: rgba(232, 194, 122, 0.1); font-size: 1.05rem; line-height: 1.45; }
.clock-rule .headline { font-family: var(--display); font-size: 1.2rem; color: #e8c27a; }
.how-to { list-style: none; margin: 0 0 1rem; padding: 0; border-top: 1px solid #3a2e28; }
.how-to li { display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0.1rem; border-bottom: 1px solid #3a2e28; font-size: 0.92rem; margin: 0; }
.how-to li .ic { width: 20px; height: 20px; color: #e8c27a; flex: 0 0 auto; }
.how-to li span { flex: 1 1 auto; }
.how-to li em { font: 0.75rem var(--label); font-style: normal; color: #a89a88; white-space: nowrap; }
.ic { width: 1.15em; height: 1.15em; display: inline-block; vertical-align: -0.2em; }
.evidence mark { background: rgba(232, 194, 122, 0.22); color: #ffe2a8; border-bottom: 2px solid #e8c27a; padding: 0 0.1em; border-radius: 2px; }
.hunch { display: flex; gap: 0.7rem; align-items: flex-start; margin: 0 0 0.8rem; padding: 0.65rem 0.8rem; border-left: 3px solid #e8c27a;
  background: rgba(232, 194, 122, 0.07); border-radius: 0 10px 10px 0; animation: rise 0.5s ease-out both; animation-delay: 0.2s; }
.hunch img { width: 34px; height: 34px; border-radius: 50%; object-fit: cover; object-position: top; border: 2px solid #e8c27a; flex: 0 0 auto; }
.hunch p { margin: 0; font-family: var(--display); font-style: italic; font-size: 0.98rem; line-height: 1.4; color: #efe6d8; }
.hunch code { display: block; margin-top: 0.4rem; font-size: 0.75rem; background: #1c1613; color: #cdbfa8; padding: 0.3rem 0.45rem; border-radius: 6px; white-space: pre-wrap; }
.hunch mark { background: rgba(232, 194, 122, 0.25); color: #ffe2a8; padding: 0 0.1em; border-radius: 3px; }
.st-key-panel h4 { font: 600 0.72rem var(--label) !important; letter-spacing: 0.16em; text-transform: uppercase;
  color: #e8c27a !important; margin: 0.6rem 0 0.2rem !important; padding: 0 !important; }
.st-key-panel [class*="st-key-note_"] button { width: 100%; justify-content: flex-start; text-align: left; padding: 0.15rem 0; min-height: 0; }
.st-key-panel [class*="st-key-note_"] button > div, .st-key-panel [class*="st-key-note_"] button [data-testid="stMarkdownContainer"] { justify-content: flex-start; text-align: left; width: 100%; }
.st-key-panel [class*="st-key-note_"] button p { font-size: 0.88rem; }
.st-key-panel [class*="st-key-note_"] button strong { font-family: var(--label); color: #e8c27a; margin-right: 0.3rem; }
.story-note { display: flex; flex-direction: column; gap: 0.15rem; padding: 0.45rem 0; border-bottom: 1px solid #3a2e28; font-size: 0.86rem; }
.story-note b { font-family: var(--display); font-size: 0.95rem; }
.story-note span { color: #cdbfa8; }
.story-note .lie-note { color: #ff8a7a; font-size: 0.8rem; }
.story-note .lie-note .ic { width: 12px; height: 12px; }
.story-note em { font-style: normal; font: 0.72rem var(--label); color: #e8c27a; }
.proof { display: flex; flex-direction: column; gap: 0.15rem; margin: -0.4rem 0 0.7rem; font-size: 0.8rem; color: #a89a88; }
.proof .ic { color: #e8c27a; width: 13px; height: 13px; }
.proof em { font-style: normal; font: 0.72rem var(--label); color: #e8c27a; }
.tips div span .ic { width: 26px; height: 26px; color: #e8c27a; }
.facedown.locked .ic { width: 40px; height: 40px; }
.medals span .ic { width: 15px; height: 15px; }
.chat .unlock .ic, .chat .caught b .ic { width: 14px; height: 14px; }
/* Detective pick: the portraits are the buttons. The chosen one wears the red ring, the other waits dimmed. */
.st-key-pick_buttons { margin: 0.7rem 0 0.6rem; }
.st-key-pick_buttons [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 1rem; }
.st-key-pick_buttons [data-testid="stColumn"] { min-width: 0 !important; width: 50% !important; flex: 1 1 0 !important;
  display: flex; justify-content: center; }
.st-key-pick_buttons [data-testid="stColumn"] > div { align-items: center; }
.st-key-pick_buttons button { width: 120px; height: 150px; min-height: 0; padding: 0; border-radius: 12px;
  border: 3px solid transparent; background-color: #241c18; background-size: cover; background-position: center top;
  filter: grayscale(0.55) brightness(0.7); transition: filter .2s, border-color .2s, box-shadow .2s, transform .2s; }
.st-key-pick_buttons button:hover { filter: none; border-color: var(--gold); transform: translateY(-2px); }
.st-key-pick_buttons button:focus-visible { outline: 3px solid var(--gold); outline-offset: 3px; }
.st-key-pick_buttons button[kind="primary"] { filter: none; border-color: var(--red); box-shadow: 0 0 0 3px rgba(192, 57, 43, 0.35); }
.st-key-pick_buttons button p { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
@keyframes rise { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: none; } }
@keyframes slam { from { opacity: 0; transform: scale(2.2); } to { opacity: 1; transform: scale(1); } }
@keyframes stamp { from { opacity: 0; transform: translate(-50%, -50%) rotate(-14deg) scale(3); } to { opacity: 1; transform: translate(-50%, -50%) rotate(-14deg) scale(1); } }
@keyframes flip { from { opacity: 0; transform: perspective(800px) rotateY(80deg); } to { opacity: 1; transform: none; } }
@keyframes deal { from { opacity: 0; transform: translateY(-30px) rotate(-6deg); } to { opacity: 1; transform: none; } }
@keyframes shake { 0%, 100% { transform: none; } 20%, 60% { transform: translateX(-8px); } 40%, 80% { transform: translateX(8px); } }
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding: 0.6rem 0.6rem 1rem; }
  .evidence img { max-height: 170px; }
  .st-key-next_phone { display: block; margin-top: 0.4rem; }
  .st-key-case_summary [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: 0.4rem 0.8rem; }
  .st-key-case_summary [data-testid="stColumn"] { min-width: 28% !important; width: 28% !important; flex: 1 1 28% !important; }
  .st-key-next_phone button { border-color: #e8c27a; color: #e8c27a; }
  .tips { grid-template-columns: 1fr; }
  .st-key-suspect_row { display: none; }
  [data-testid="stDialog"] [data-testid="stColumn"]:has(.cover-art) { display: none; }
  .story { font-size: 1rem; }
  .facts { grid-template-columns: repeat(2, 1fr); }
  .finale .mug, .finale .mug img { width: 160px; }
  .finale h1 { font-size: 2rem; }
  .st-key-pick_buttons button { width: 110px; height: 138px; }
}
</style>
"""

deck = st.components.v2.component("deck", js=board.BOARD_JS, css=board.BOARD_CSS)


@st.cache_data
def map_picture():
    """The map picture as a data URI, with its size in pixels."""
    from PIL import Image  # installed with streamlit

    with Image.open(CAMPUS_MAP) as picture:
        size = picture.size
    return board.data_uri(str(CAMPUS_MAP)), size


def suspect_status(game):
    """For each suspect: whether you have questioned them, how many lies you caught, and their nerves."""
    questioned = {event["suspect"] for event in game.history if "suspect" in event}
    caught = {}
    for suspect, _claim in game.contradictions:
        caught[suspect] = caught.get(suspect, 0) + 1
    return [
        {"id": s, "name": d["name"], "questioned": s in questioned, "caught": caught.get(s, 0), "ruled_out": ruled_out(s),
         "nerves": engine.nerves(game, s)}
        for s, d in case["suspects"].items()
    ]


def draw_board(game, clues, fresh):
    """The status bar, the campus map and the evidence hand, as one tappable component."""
    kind, value = focus()
    picked = value if kind == "clue" else None
    avatar = board.find_picture("detectives", player_avatar())
    map_uri, size = map_picture()
    step = engine.next_step(game)
    goal = board.goal_target(step)
    markup = (
        board.hud_html(
            engine.clock_label(game), engine.time_left(game), case["clock"]["limit_minutes"],
            case["max_strikes"] - game.strikes, case["max_strikes"], len(game.contradictions), avatar, player_name(),
        )
        + board.goal_html(step, engine.thought(game, step))
        + '<div class="phone-only">' + board.suspects_html(suspect_status(game), focus()[1] if kind == "suspect" else None, goal) + "</div>"
        + board.map_html(map_uri, size, board.map_points(clues), game.opened, picked, avatar, fresh, goal)
        + board.hand_html(clues, picked, fresh, goal)
        + pending_sound()
        + (board.tutorial_html() if show_tour(game) else "")
    )
    deck(data=markup, key="board", on_act_change=functools.partial(on_act, "board"))


def pending_sound():
    """The sound asked for by the last action, once."""
    name = st.session_state.pop("sfx", None)
    return board.sfx_html(name, st.session_state.get("sfx_n", 0)) if name else ""


def show_tour(game):
    """The first-play tour: once, after the intro, before the first move."""
    return bool(st.session_state.get("intro_done")) and not st.session_state.get("tour_done") and not game.history


def draw_suspects(game):
    kind, value = focus()
    picked = value if kind == "suspect" else None
    goal = board.goal_target(engine.next_step(game))
    deck(data=board.suspects_html(suspect_status(game), picked, goal), key="suspect_row",
         on_act_change=functools.partial(on_act, "suspect_row"))


# ---- Panel: home (leads, lies caught) ---------------------------------------------------


def panel_home(game):
    st.markdown('<div class="kicker">Your move</div>', unsafe_allow_html=True)
    leads = engine.leads(game) + [{"clue": c, "text": t} for c, t in engine.hint_list(game).items()]
    if leads:
        st.markdown("### Leads")
        st.markdown(
            "".join(f'<div class="lead"><b>{esc(lead["clue"])}</b><span>{esc(lead["text"])}</span></div>' for lead in leads),
            unsafe_allow_html=True,
        )
    elif game.history:
        step = engine.next_step(game)
        if step:
            st.markdown(f"### {step['text']}")  # the next step, once the first move is made
    else:
        st.markdown("### Where to start")
        st.markdown(
            f'<div class="tips"><div><span>{board.icon("search")}</span>Tap a red evidence card or pin to search it</div>'
            f'<div><span>{board.icon("ask")}</span>Tap a face to interrogate</div>'
            f'<div><span>{board.icon("bolt")}</span>Show a suspect the evidence card that breaks their story</div></div>',
            unsafe_allow_html=True,
        )
    caught = engine.contradiction_list(game)
    if caught:
        st.markdown(f"### Lies caught · {len(caught)}")
        st.markdown(
            "".join(
                f'<div class="lie"><b>{esc(board.short_name(case["suspects"][c["suspect"]]["name"]))}</b> said '
                f'“{esc(c["text"])}” · broken by <b>{esc(c["clue"] or "a clue")}</b></div>'
                for c in caught
            ),
            unsafe_allow_html=True,
        )
    badges = engine.badge_list(game)
    if badges:
        st.markdown('<div class="medals">' + "".join(f'<span title="{esc(b["description"])}">{board.icon("medal")} {esc(b["title"])}</span>' for b in badges) + "</div>",
                    unsafe_allow_html=True)
    st.caption(
        f"Searching costs {case['clock']['clue_cost']} min, a question {case['clock']['question_cost']} min. "
        "Bookmark this page to come back to this case."
    )
    with st.popover("New case", icon=":material/refresh:"):
        st.write("Start over with a new culprit? This case will be lost.")
        if st.button("Yes, new case", type="primary", key="new_case"):
            new_case()
            st.rerun()


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
        brief = engine.character_brief(current_game(), suspect)
        say(suspect, {"who": "you", "text": TOPICS[topic][1]})
        say(suspect, {"who": "them", "text": result["line"] or brief["cover"], "unlocked": result["unlocked"]})
        think(suspect, engine.reaction(current_game(), topic=topic, unlocked=bool(result["unlocked"])))


def show_evidence():
    """Tapping one of your cards in the interrogation: slide it across the table."""
    clue_id = st.session_state.get("show_clue")
    st.session_state.show_clue = None
    suspect = st.session_state.get("suspect")
    if not clue_id or suspect not in case["suspects"]:
        return
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


def cloud_key():
    from streamlit.errors import StreamlitSecretNotFoundError

    try:
        return st.secrets.get("REQUESTY_API_KEY")
    except StreamlitSecretNotFoundError:
        return None


def chat_html(log, suspect):
    """The conversation as speech bubbles: the suspect on the left, you on the right."""
    them = board.find_picture("suspects", suspect) or ""
    you = board.find_picture("detectives", player_avatar()) or ""
    rows = []
    for number, entry in enumerate(log):
        style = "" if number >= len(log) - 2 else ' style="animation:none"'  # only the newest lines animate
        if entry["who"] == "you":
            act = " act" if entry.get("act") else ""
            rows.append(f'<div class="bubble you"{style}><img src="{you}" alt=""><div class="say{act}">{esc(entry["text"])}</div></div>')
            continue
        unlock = ""
        if entry.get("unlocked"):
            unlock = '<span class="unlock">' + board.icon("unlock") + " Unlocked: " + esc(", ".join(engine.label(i) for i in entry["unlocked"])) + "</span>"
        note = FALLBACK_NOTES.get(entry.get("fallback"))
        note = f'<span class="note">{esc(note)}</span>' if note else ""
        rows.append(f'<div class="bubble them"{style}><img src="{them}" alt=""><div class="say">{esc(entry["text"])}{unlock}{note}</div></div>')
        for item in entry.get("caught", []):
            rows.append(
                f'<div class="caught"{style}><b>{board.icon("bolt")} Caught lying</b><small>They said “{esc(item["text"].rstrip("."))}”. '
                f'{esc(proof_name(item["clue"]).capitalize() if item["clue"] else "Your evidence")} says otherwise.</small></div>'
            )
        if entry.get("cracked"):
            after = "They are off your list." if entry["cracked"]["cleared"] else "That was not meant to come out."
            rows.append(f'<div class="caught cracked"{style}><b>{board.icon("bolt")} Cracked</b><small>{after}</small></div>')
        if entry.get("think"):
            rows.append(f'<div class="bubble think"{style}><img src="{you}" alt=""><div class="say">{esc(entry["think"])}</div></div>')
    return '<div class="chat">' + "".join(rows) + "</div>"


def nerve_level(game, suspect):
    """How rattled a suspect looks, 0 to 100. The engine decides it (Engine.nerves); at 100 they crack."""
    return engine.nerves(game, suspect)


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


def panel_suspect(game, suspect):
    from game import ai

    brief = engine.character_brief(game, suspect)
    uri = board.find_picture("suspects", suspect) or ""
    persona = brief["persona"].split(";")[0].split(". ")[0].rstrip(".") + "."
    nerves = nerve_level(game, suspect)
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
    step = engine.next_step(game) or {}
    tip = step if step.get("suspect") == suspect else {}
    asked = {e["topic"] for e in game.history if e.get("action") == "ask" and e.get("suspect") == suspect}
    st.pills(f"Ask · {cost} min", list(TOPICS), format_func=lambda t: topic_label(t, asked, tip.get("topic")),
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
        if clue_id in hints:
            st.info(hints[clue_id], icon=":material/lightbulb:")
        else:
            st.caption("Locked. Question suspects and show them evidence cards to unlock it.")
            if st.button(f"Hint · {engine.hint_cost()} min", key=f"hint_{clue_id}", icon=":material/lightbulb:", use_container_width=True):
                run(engine.hint, clue_id)
                st.rerun()
        return
    if item["state"] == "available":
        st.markdown('<div class="facedown">?</div>', unsafe_allow_html=True)
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
    st.caption("Tap a suspect's face, then show them this evidence card.")


# ---- Panel: case sheet and accusation ----------------------------------------------------


def clue_fact(game, clue_id):
    """One line to remember a clue by: the detail that stood out, or the clue's first sentence."""
    for hunch in engine.hunches(game, clue_id, include_caught=True):
        if hunch["mark"]:
            return hunch["mark"]
    text = engine.read_clue(game, clue_id)["text"].strip().splitlines()[0].removeprefix("- ")
    first = re.split(r"(?<=[a-z0-9)\"'][.!?])\s", text, maxsplit=1)[0]
    return first if len(first) <= 90 else first[:87].rstrip() + "…"


def first_sentences(text, count=2):
    return " ".join(re.split(r"(?<=[a-z0-9)\"'][.!?])\s", text.strip())[:count])


def notebook_notes(game):
    """The automatic half of the notebook: every card found, every story told, every lie and proof."""
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
                        f'<span>“{esc(first_sentences(brief["cover"]))}”</span>{lies}</div>')
        st.markdown("".join(rows), unsafe_allow_html=True)
    proven = engine.eliminated(game)
    if proven:
        st.markdown(f"#### Ruled out · {len(proven)}")
        st.markdown(
            '<div class="proof">' + "".join(
                f"<span>{board.icon('check')} {esc(label(e['column'], e['option']))} <em>ruled out by {esc(proof_name(e['by']))}</em></span>"
                for e in proven
            ) + "</div>",
            unsafe_allow_html=True,
        )


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
                     format_func=lambda o, c=column: label(c, o), selection_mode="multi", key=f"sheet_{column}")
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
    if by == "crack":
        return "their breakdown"
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
        result = run(engine.accuse, *(choice[c] for c in COLUMNS))
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
        st.caption(f"{len(verdict)} of 4 right. Keep the ✓ parts and rethink the ✗ ones.")
    for column in COLUMNS:
        out = set(crossed(column))
        st.pills(f"{COLUMN_ICONS[column]} {column.capitalize()}", [o["id"] for o in case["accusation"][column]],
                 format_func=lambda o, c=column, out=out: label(c, o) + (" ✗" if o in out else ""), key=f"accuse_{column}")
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
    return (f"I solved Death of the Final Exam at {engine.clock_label(game)} as {rank['title']} "
            f"({rank['score']}/100), {lies_text}{wrong}. Can you beat it? {APP_URL}")


def rank_card(game):
    rank = engine.rank(game)
    solved = game.status == "solved"
    score = f'<span class="score">{rank["score"]} / 100</span>' if solved else ""
    st.markdown(f'<div class="rank{"" if solved else " cold"}"><small>YOUR RANK</small><b>{esc(rank["title"])}</b>{score}</div>',
                unsafe_allow_html=True)
    if solved:
        st.caption("50 for solving, up to 25 for time left, 5 per lie caught (up to 20); "
                   "minus 3 per hint and 10 per wrong accusation.")
    st.caption("Share it (no spoilers):")
    st.code(share_text(game, rank), language=None, wrap_lines=True)


def finale(game):
    solution = engine.solution(game)
    culprit = solution["who"]
    uri = board.find_picture("suspects", culprit) or ""
    solved = game.status == "solved"
    stamp, heading = ("GUILTY", "Case closed") if solved else ("CASE COLD", "The trail went cold")
    sub = (f"Solved at {engine.clock_label(game)} · {len(game.contradictions)} {"lie" if len(game.contradictions) == 1 else "lies"} caught" if solved
           else f"It was {case['suspects'][culprit]['name']} all along.")
    facts = "".join(f"<div><small>{c.upper()}</small>{esc(label(c, solution[c]))}</div>" for c in COLUMNS)
    medals = "".join(f"<span>{board.icon('medal')} {esc(b['title'])}</span>" for b in engine.badge_list(game))
    _, middle, _ = st.columns([1, 3, 1])
    middle.markdown(
        f'<div class="finale{"" if solved else " cold"}"><div class="mug"><img src="{uri}" alt=""><span class="slam">{stamp}</span></div>'
        f'<div class="title">{heading}</div><div class="sub">{esc(sub)}</div><div class="facts">{facts}</div>'
        f'{f"<div class=medals>{medals}</div>" if medals else ""}</div>',
        unsafe_allow_html=True,
    )
    marker = pending_sound()
    if marker:
        deck(data=marker, key="finale_sound", height=1)
    with middle:
        # The confrontation is the story's payoff, so it comes first and starts open.
        scene = denouement(game)
        if scene:
            with st.expander("Half past seven, the boardroom: read the confrontation", icon=":material/history_edu:",
                             expanded=True):
                for paragraph in scene.split("\n\n"):
                    st.markdown(plain(paragraph))
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
    "in the class group chat, to all 212 students. The exam is at <b>09:00</b>. Find out who leaked it before then."
)


def whos_who_html():
    """The five suspects, one short line each, so a new player knows who is who."""
    return '<div class="kicker">Who\'s who</div><ul class="whos-who">' + "".join(
        f'<li><img src="{board.find_picture("suspects", sid) or ""}" alt="">'
        f'<span><b>{esc(board.short_name(s["name"]))}</b>{esc(s.get("role", ""))}</span></li>'
        for sid, s in case["suspects"].items()
    ) + "</ul>"


HOURS = case["clock"]["limit_minutes"] // 60
CLOCK_RULE = (
    f'<div class="clock-rule"><b class="headline">Every action costs time. Use your {HOURS} hours well.</b>'
    "<span>The clock runs from midnight to 09:00, and every search and every question moves it forward. "
    "At 09:00 you can no longer search or ask: you can only accuse.</span></div>"
)
HOW_TO_PLAY = (
    '<ol class="how-to">'
    f'<li>{board.icon("search")}<span><b>Search</b> a new place or document</span><em>−{case["clock"]["clue_cost"]} min</em></li>'
    f'<li>{board.icon("ask")}<span><b>Question</b> the five suspects</span><em>−{case["clock"]["question_cost"]} min</em></li>'
    f'<li>{board.icon("bolt")}<span><b>Show</b> the evidence card that breaks a lie</span><em>−{case["clock"]["question_cost"]} min</em></li>'
    f'<li>{board.icon("scale")}<span><b>Accuse</b> who, how, where and why</span><em>no time · {case["max_strikes"]} tries</em></li>'
    "</ol>"
)
SHOW_COVER = True  # the cover picture beside the briefing on the start screen (hidden on phones)


def pick_detective(avatar):
    st.session_state.player_avatar = avatar


def finish_intro():
    st.session_state.intro_done = True


@st.dialog("The exam has leaked", width="large", on_dismiss=finish_intro)
def intro_dialog():
    """The story and the rules in one glance, and who you are, before the first move."""
    cover = board.data_uri(str(COVER)) if SHOW_COVER else None
    if cover:
        art, brief = st.columns([5, 6], gap="large")
        with art:
            st.markdown(f'<div class="cover-art" style="background-image:url({cover})"></div>', unsafe_allow_html=True)
    else:
        brief = st.container()
    with brief:
        st.markdown(f'<div class="kicker">{esc(TITLE)}</div>', unsafe_allow_html=True)
        st.markdown(f'<p class="story">{STORY_HTML}</p>' + PAGE_CSS + CLOCK_RULE + whos_who_html() + HOW_TO_PLAY, unsafe_allow_html=True)
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
        if st.button("Start the investigation", type="primary", icon=":material/search:", use_container_width=True):
            finish_intro()
            st.rerun()


# ---- The page ---------------------------------------------------------------------------

game = current_game()
st.markdown(PAGE_CSS, unsafe_allow_html=True)

flash = st.session_state.pop("flash", None)
if flash:
    getattr(st, flash[0])(flash[1])
toast = st.session_state.pop("toast", None)
if toast:
    st.toast(toast[0], icon=toast[1])
refusal = st.session_state.pop("refusal", None)
if refusal:
    st.toast(refusal, icon=":material/warning:")
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
        kind, value = focus()
        if kind == "suspect" and value in case["suspects"]:
            panel_suspect(game, value)
        elif kind == "clue" and value in case["clues"]:
            panel_clue(game, value, fresh)
        elif kind == "spot" and value in board.MAP_SPOTS:
            st.markdown(f'<div class="kicker">{board.icon("pin")} Off campus</div><h3>{esc(board.MAP_SPOTS[value][2])}</h3>', unsafe_allow_html=True)
            st.write(board.MAP_SPOTS[value][3])
        elif kind == "sheet":
            panel_sheet()
        elif kind == "accuse":
            panel_accuse(game)
        else:
            panel_home(game)
    next_step_button(game)

# Called last, so the story and rules open over the game on a new case.
if not st.session_state.get("intro_done", bool(game.history)):
    intro_dialog()
