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

import altair as alt
import pandas as pd
import streamlit as st

import board
import db
import reloading
from game.case import load_case

ROOT = Path(__file__).resolve().parent
COVER = ROOT / "assets" / "cover.webp"
CAMPUS_MAP = ROOT / "assets" / "campus-map.webp"
TITLE = load_case()["title"]  # the game's name lives in data/case.json

# The detectives a player can be: assets/detectives/<id>.webp, 4:5 like the suspects. Purely cosmetic.
AVATARS = {"she": "Play as her", "he": "Play as him"}
DEFAULT_AVATAR = "she"
COLUMNS = ("who", "how", "where", "why")
COLUMN_ICONS = {"who": "👤", "how": "🔧", "where": "📍", "why": "💭"}
# The questions a player can tap, by topic: (button label, what the detective says).
TOPICS = {
    "alibi": ("📍 Last night?", "Where were you last night?"),
    "exam": ("📝 The exam", "What do you know about tomorrow's exam?"),
    "report": ("📄 The report", "Tell me about the report."),
    "work": ("💼 Your job", "What is your job here?"),
    "teaching_assistant": ("🎓 The TA", "What can you tell me about the Teaching Assistant?"),
    "leak": ("💥 The leak", "Who leaked the paper?"),
    "other": ("❓ Anything else?", "Is there anything else I should know?"),
}

st.set_page_config(page_title=TITLE, page_icon="🕵️", layout="wide", initial_sidebar_state="collapsed")


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
        if saved is not None:
            st.session_state.game = saved.to_dict()
            st.session_state.game_id = requested
        else:
            if requested:
                st.session_state.flash = ("warning", "That saved game was not found, so a new case has started.")
            start_new_game()
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
        st.session_state.flash = ("error", str(error))
        return None
    save(game)
    unlocked = [c for c in engine.clue_list(game) if c["id"] in locked and c["state"] != "locked"]
    st.session_state.fresh = [c["id"] for c in unlocked]
    if unlocked:
        names = ", ".join(f"{c['id']}. {c['title']}" for c in unlocked)
        st.session_state.toast = (f"New clue unlocked: {names}", "🔓")
    elif any(lead["clue"] not in known_leads for lead in engine.leads(game)):
        st.session_state.toast = ("New lead. Tap 🔎 to see it.", "🔎")
    return result


def new_case():
    start_new_game()
    for key in [k for k in st.session_state if str(k).startswith(("sheet_", "accuse_"))]:
        del st.session_state[key]
    for key in ("chats", "focus", "suspect", "verdict", "fresh"):
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


def crossed(column):
    """The options the player has crossed off on their case sheet. Their own notes; never the game."""
    return list(st.session_state.get(f"sheet_{column}") or [])


def ruled_out(suspect):
    return suspect in crossed("who")


def focus():
    """What the side panel shows: ("home"), ("suspect", id), ("clue", id), ("spot", id), ("sheet") or ("accuse")."""
    return st.session_state.get("focus") or ("home", None)


def set_focus(kind, value=None):
    st.session_state.focus = (kind, value)
    if kind == "suspect":
        st.session_state.suspect = value


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
    else:
        set_focus(kind, value)


# ---- The D4 chart --------------------------------------------------------------------

# Categorical slots 1 and 2 of the validated chart palette (blue, orange).
SERIES_COLORS = ["#2a78d6", "#eb6834"]


def payoff_chart(spec):
    """The D4 payoff chart: the fellowship against the Class Representative's grade on Friday."""
    low, high = spec["grades"]
    prize = spec["prize"]
    rival = round(sum(spec["rival_mocks"]) / len(spec["rival_mocks"]), 1)
    mocks = spec["subject_mocks"]
    grades = sorted({*range(low, high + 1), rival})
    goes_ahead, annulled = "Exam goes ahead", "Exam annulled"
    rows = [
        {"grade": g, "scenario": s, "payoff": prize if s == annulled or g >= rival else 0}
        for s in (goes_ahead, annulled)
        for g in grades
    ]
    data = pd.DataFrame(rows)
    color = alt.Color(
        "scenario:N",
        title=None,
        scale=alt.Scale(domain=[goes_ahead, annulled], range=SERIES_COLORS),
        legend=alt.Legend(orient="top", direction="vertical", labelLimit=0),
    )
    x_scale = alt.Scale(domain=[low, high], nice=False)
    y_scale = alt.Scale(domain=[0, prize * 1.1], nice=False)
    x = alt.X("grade:Q", title="Class Rep's grade on Friday", scale=x_scale)
    y = alt.Y("payoff:Q", title="Fellowship won (€)", scale=y_scale, axis=alt.Axis(format=",.0f"))

    mock_band = (
        alt.Chart(pd.DataFrame([{"from": min(mocks), "to": max(mocks), "label": "Their mock finals"}]))
        .mark_rect(opacity=0.12, color="gray")
        .encode(x=alt.X("from:Q", scale=x_scale), x2="to:Q", tooltip=[alt.Tooltip("label:N", title="")])
    )

    def note(x_value, y_value, text, align):
        return (
            alt.Chart(pd.DataFrame([{"x": x_value, "y": y_value, "text": text}]))
            .mark_text(fontSize=11, color="gray", align=align)
            .encode(x=alt.X("x:Q", scale=x_scale), y=alt.Y("y:Q", scale=y_scale), text="text:N")
        )

    notes = note((min(mocks) + max(mocks)) / 2, prize * 0.6, "Their mocks", "center") + note(
        rival - 0.15, prize * 0.25, f"Rival: {rival}", "right"
    )
    rival_rule = (
        alt.Chart(pd.DataFrame([{"x": rival, "label": f"Exchange Student's mock average: {rival}"}]))
        .mark_rule(strokeDash=[4, 4], color="gray")
        .encode(x=alt.X("x:Q", scale=x_scale), tooltip=[alt.Tooltip("label:N", title="")])
    )
    lines = (
        alt.Chart(data)
        .mark_line(strokeWidth=2, interpolate="step-after")
        .encode(
            x=x,
            y=y,
            color=color,
            strokeDash=alt.StrokeDash(
                "scenario:N", scale=alt.Scale(domain=[goes_ahead, annulled], range=[[1, 0], [6, 4]]), legend=None
            ),
        )
    )
    hover = (
        alt.Chart(data)
        .mark_point(size=250, opacity=0)
        .encode(
            x=x,
            y=y,
            tooltip=[
                alt.Tooltip("scenario:N", title="If the"),
                alt.Tooltip("grade:Q", title="Grade"),
                alt.Tooltip("payoff:Q", title="Fellowship (€)", format=",.0f"),
            ],
        )
    )
    return (mock_band + notes + rival_rule + lines + hover).properties(title=spec["title"], height=260)


def denouement(game):
    """The closing scene of this game's variant. Only once the case is closed."""
    engine.solution(game)  # raises GameError while the game is still running
    text = case["variants"][game.variant].get("denouement", "")
    return text.format_map(game.variables)


# ---- Page style ----------------------------------------------------------------------

PAGE_CSS = """
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none; }
[data-testid="stMainBlockContainer"] { padding: 3.4rem 1.2rem 1.5rem; max-width: 1480px; }
header[data-testid="stHeader"] { background: transparent; }
.st-key-panel { background: #1c1613; border: 1px solid #3a2e28; border-radius: 14px; padding: 0.9rem 1rem 1rem; gap: 0.6rem; }
.st-key-panel h3 { margin: 0 0 0.2rem; padding: 0.1rem 0 0; font-size: 1.35rem; line-height: 1.3; }
.kicker { font: 600 0.72rem "Courier New", monospace; letter-spacing: 0.18em; text-transform: uppercase; color: #e8c27a; }
.who-head { display: flex; gap: 0.8rem; align-items: center; }
.who-head img { width: 64px; height: 80px; object-fit: cover; border-radius: 10px; border: 2px solid #c0392b; }
.nerves { display: flex; align-items: center; gap: 0.4rem; font: 600 0.68rem "Courier New", monospace; letter-spacing: 0.12em;
  text-transform: uppercase; opacity: 0.85; margin-top: 0.25rem; }
.nerves i { width: 110px; height: 6px; background: #3a2e28; border-radius: 3px; overflow: hidden; display: inline-block; }
.nerves b { display: block; height: 100%; background: linear-gradient(90deg, #e8c27a, #e0645a); transition: width 0.6s; }
.who-head .line { font-size: 0.85rem; opacity: 0.75; line-height: 1.3; }
.chat { display: flex; flex-direction: column; gap: 0.55rem; padding: 0.2rem 0.1rem; }
.bubble { display: flex; gap: 0.5rem; align-items: flex-end; max-width: 92%; animation: rise 0.35s ease-out both; }
.bubble img { width: 30px; height: 30px; border-radius: 50%; object-fit: cover; object-position: top; flex: none; }
.bubble .say { padding: 0.5rem 0.75rem; border-radius: 16px; font-family: Georgia, serif; font-size: 0.95rem; line-height: 1.35; }
.bubble.them .say { background: #2b221d; border: 1px solid #3f322b; border-bottom-left-radius: 4px; }
.bubble.you { margin-left: auto; flex-direction: row-reverse; }
.bubble.you .say { background: #5a1d16; border: 1px solid #7a2c22; border-bottom-right-radius: 4px; }
.bubble.you .say.act { font-style: italic; background: #2a2a1e; border-color: #4a4a30; }
.bubble .unlock { display: block; margin-top: 0.35rem; font: 600 0.75rem "Courier New", monospace; color: #e8c27a; }
.caught { margin: 0.2rem auto 0.3rem; text-align: center; animation: slam 0.5s cubic-bezier(.2,1.6,.4,1) both; }
.caught b { display: inline-block; border: 3px solid #e0645a; color: #e0645a; padding: 0.1rem 0.6rem; transform: rotate(-4deg);
  font: 800 1.15rem "Courier New", monospace; letter-spacing: 0.12em; text-transform: uppercase; }
.caught small { display: block; font-size: 0.8rem; opacity: 0.8; margin-top: 0.3rem; }
.empty-chat { text-align: center; opacity: 0.6; padding: 1.6rem 0.5rem; font-size: 0.9rem; }
.evidence { position: relative; border-radius: 12px; overflow: hidden; background: #efe6d8; color: #2a201b;
  box-shadow: 0 8px 24px rgba(0,0,0,0.45); animation: flip 0.55s ease-out both; }
.evidence img { width: 100%; display: block; max-height: 260px; object-fit: cover; }
.evidence .icon { font-size: 4rem; text-align: center; padding: 1.4rem 0 0.4rem; }
.evidence .body { padding: 0.7rem 0.9rem 0.9rem; font-family: Georgia, serif; font-size: 0.95rem; line-height: 1.45; }
.facedown { border-radius: 12px; height: 150px; display: flex; align-items: center; justify-content: center; font-size: 2.6rem;
  background: repeating-linear-gradient(45deg, #5a1d16 0 10px, #6e241b 10px 20px); color: #f4d9a0; }
.facedown.locked { background: repeating-linear-gradient(45deg, #2a221e 0 10px, #332924 10px 20px); }
.lead { display: flex; gap: 0.6rem; align-items: flex-start; background: #241c18; border-left: 3px solid #e8c27a; border-radius: 8px;
  padding: 0.5rem 0.7rem; margin-bottom: 0.4rem; font-size: 0.92rem; }
.lead b { font-family: "Courier New", monospace; color: #e8c27a; }
.tips { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; }
.tips div { background: #241c18; border-radius: 10px; padding: 0.6rem; text-align: center; font-size: 0.85rem; line-height: 1.25; }
.tips div span { display: block; font-size: 1.6rem; }
.lie { background: #2a1714; border: 1px solid #5a2a22; border-radius: 10px; padding: 0.45rem 0.7rem; margin-bottom: 0.4rem; font-size: 0.88rem; }
.lie b { color: #e0645a; }
.verdict { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.4rem; animation: shake 0.5s; }
.verdict div { text-align: center; border-radius: 10px; padding: 0.5rem 0.2rem; font: 700 0.8rem "Courier New", monospace; letter-spacing: 0.08em; }
.verdict .ok { background: #1f3a24; color: #8be09a; border: 2px solid #3d7a48; }
.verdict .no { background: #3a1714; color: #ff8a7a; border: 2px solid #7a2c22; }
.verdict span { display: block; font-size: 1.5rem; }
.st-key-panel [data-testid="stPills"] button { font-size: 0.85rem; }
[class*="st-key-sheet_"] button[kind="pillsActive"] {
  text-decoration: line-through; text-decoration-color: #e0645a; text-decoration-thickness: 2px; opacity: 0.6;
  background: #2a1714 !important; border-color: #5a2a22 !important; color: #efe6d8 !important; }
.st-key-accuse_go button { font-size: 1.15rem; font-weight: 800; letter-spacing: 0.1em; text-transform: uppercase; padding: 0.7rem; }
/* The finale */
.finale { text-align: center; padding: 0.5rem 0 0.2rem; }
.finale .mug { position: relative; width: 220px; margin: 0 auto; }
.finale .mug img { width: 220px; aspect-ratio: 4 / 5; object-fit: cover; border-radius: 14px; border: 3px solid #3a2e28;
  box-shadow: 0 16px 40px rgba(0,0,0,0.6); animation: rise 0.8s ease-out both; }
.finale .slam { position: absolute; left: 50%; top: 55%; transform: translate(-50%, -50%) rotate(-14deg); border: 5px solid #e0645a;
  color: #e0645a; background: rgba(20,16,14,0.78); padding: 0.1rem 0.8rem; font: 900 2.2rem "Courier New", monospace;
  letter-spacing: 0.15em; animation: stamp 0.6s 0.6s cubic-bezier(.2,1.6,.4,1) both; white-space: nowrap; }
.finale.cold .slam { border-color: #9aa7b3; color: #9aa7b3; }
.finale h1 { font-size: 2.6rem; margin: 1.1rem 0 0.1rem; animation: rise 0.6s 1s ease-out both; }
.finale .sub { opacity: 0.75; animation: rise 0.6s 1.1s ease-out both; }
.facts { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.6rem; max-width: 900px; margin: 1.2rem auto 0.4rem; }
.facts div { background: #efe6d8; color: #2a201b; border-radius: 10px; padding: 0.7rem 0.6rem; font-family: Georgia, serif;
  font-size: 0.92rem; line-height: 1.3; animation: deal 0.5s ease-out both; }
.facts div:nth-child(1) { animation-delay: 1.3s; } .facts div:nth-child(2) { animation-delay: 1.5s; }
.facts div:nth-child(3) { animation-delay: 1.7s; } .facts div:nth-child(4) { animation-delay: 1.9s; }
.facts small { display: block; font: 700 0.7rem "Courier New", monospace; letter-spacing: 0.15em; color: #8a2a1f; margin-bottom: 0.2rem; }
.medals { margin-top: 0.8rem; display: flex; gap: 0.5rem; justify-content: center; flex-wrap: wrap; }
.medals span { background: #2b221d; border: 1px solid #e8c27a; color: #e8c27a; border-radius: 20px; padding: 0.2rem 0.7rem; font-size: 0.85rem; }
.how-to { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem; margin: 0.3rem 0 0.6rem; }
.how-to div { border: 1px solid #3a2e28; border-radius: 10px; padding: 0.55rem; background: #1c1613; font-size: 0.82rem; text-align: center; line-height: 1.25; }
.how-to b { display: block; font-size: 1.6rem; }
.detective-pick { width: 140px !important; height: 175px !important; max-width: 100%; object-fit: cover !important; display: block;
  margin: 0 auto 0.4rem; border-radius: 10px; border: 3px solid transparent; }
.detective-pick.picked { border-color: #c0392b; box-shadow: 0 0 0 3px rgba(192, 57, 43, 0.35); }
@keyframes rise { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: none; } }
@keyframes slam { from { opacity: 0; transform: scale(2.2); } to { opacity: 1; transform: scale(1); } }
@keyframes stamp { from { opacity: 0; transform: translate(-50%, -50%) rotate(-14deg) scale(3); } to { opacity: 1; transform: translate(-50%, -50%) rotate(-14deg) scale(1); } }
@keyframes flip { from { opacity: 0; transform: perspective(800px) rotateY(80deg); } to { opacity: 1; transform: none; } }
@keyframes deal { from { opacity: 0; transform: translateY(-30px) rotate(-6deg); } to { opacity: 1; transform: none; } }
@keyframes shake { 0%, 100% { transform: none; } 20%, 60% { transform: translateX(-8px); } 40%, 80% { transform: translateX(8px); } }
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding: 3rem 0.6rem 1rem; }
  .tips { grid-template-columns: 1fr; }
  .st-key-suspect_row { display: none; }
  .how-to { grid-template-columns: repeat(2, 1fr); }
  .facts { grid-template-columns: repeat(2, 1fr); }
  .finale .mug, .finale .mug img { width: 160px; }
  .finale h1 { font-size: 2rem; }
  .detective-pick { width: 110px !important; height: 138px !important; }
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
    """For each suspect: whether you have questioned them, and how many lies you caught."""
    questioned = {event["suspect"] for event in game.history if "suspect" in event}
    caught = {}
    for suspect, _claim in game.contradictions:
        caught[suspect] = caught.get(suspect, 0) + 1
    return [
        {"id": s, "name": d["name"], "questioned": s in questioned, "caught": caught.get(s, 0), "ruled_out": ruled_out(s)}
        for s, d in case["suspects"].items()
    ]


def draw_board(game, clues, fresh):
    """The status bar, the campus map and the evidence hand, as one tappable component."""
    kind, value = focus()
    picked = value if kind == "clue" else None
    avatar = board.find_picture("detectives", player_avatar())
    map_uri, size = map_picture()
    markup = (
        board.hud_html(
            engine.clock_label(game), engine.time_left(game), case["clock"]["limit_minutes"],
            case["max_strikes"] - game.strikes, case["max_strikes"], len(game.contradictions), avatar, player_name(),
        )
        + '<div class="phone-only">' + board.suspects_html(suspect_status(game), focus()[1] if kind == "suspect" else None) + "</div>"
        + board.map_html(map_uri, size, board.map_points(clues), game.opened, picked, avatar, fresh)
        + board.hand_html(clues, picked, fresh)
    )
    deck(data=markup, key="board", on_act_change=functools.partial(on_act, "board"))


def draw_suspects(game):
    kind, value = focus()
    picked = value if kind == "suspect" else None
    deck(data=board.suspects_html(suspect_status(game), picked), key="suspect_row",
         on_act_change=functools.partial(on_act, "suspect_row"))


# ---- Panel: home (leads, lies caught) ---------------------------------------------------


def panel_home(game):
    st.markdown('<div class="kicker">Your move</div>', unsafe_allow_html=True)
    leads = engine.leads(game) + [{"clue": c, "text": t} for c, t in engine.hint_list(game).items()]
    if leads:
        st.markdown("### 🔎 Leads")
        st.markdown(
            "".join(f'<div class="lead"><b>{esc(lead["clue"])}</b><span>{esc(lead["text"])}</span></div>' for lead in leads),
            unsafe_allow_html=True,
        )
    else:
        st.markdown("### Where to start")
        st.markdown(
            '<div class="tips"><div><span>❓</span>Tap a red card or pin to search it</div>'
            "<div><span>🗣️</span>Tap a face to interrogate</div>"
            "<div><span>⚡</span>Show a suspect the clue that breaks their story</div></div>",
            unsafe_allow_html=True,
        )
    caught = engine.contradiction_list(game)
    if caught:
        st.markdown(f"### ⚡ Lies caught · {len(caught)}")
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
        st.markdown('<div class="medals">' + "".join(f'<span title="{esc(b["description"])}">🏅 {esc(b["title"])}</span>' for b in badges) + "</div>",
                    unsafe_allow_html=True)
    st.caption(
        f"Searching costs {case['clock']['clue_cost']} min, a question {case['clock']['question_cost']} min. "
        "Bookmark this page to come back to this case."
    )
    with st.popover("🔁 New case"):
        st.write("Start over with a new culprit? This case will be lost.")
        if st.button("Yes, new case", type="primary", key="new_case"):
            new_case()
            st.rerun()


# ---- Panel: interrogation -----------------------------------------------------------


def say(suspect, entry):
    st.session_state.setdefault("chats", {}).setdefault(suspect, []).append(entry)


def ask_topic():
    """Tapping a question: ask it at once, then clear the pick so it can be tapped again."""
    topic = st.session_state.get("ask_topic")
    st.session_state.ask_topic = None
    suspect = st.session_state.get("suspect")
    if topic not in TOPICS or suspect not in case["suspects"]:
        return
    result = run(engine.ask, suspect, topic)
    if result:
        brief = engine.character_brief(current_game(), suspect)
        say(suspect, {"who": "you", "text": TOPICS[topic][1]})
        say(suspect, {"who": "them", "text": result["line"] or brief["cover"], "unlocked": result["unlocked"]})


def show_evidence():
    """Tapping one of your cards in the interrogation: slide it across the table."""
    clue_id = st.session_state.get("show_clue")
    st.session_state.show_clue = None
    suspect = st.session_state.get("suspect")
    if not clue_id or suspect not in case["suspects"]:
        return
    result = run(engine.present, suspect, clue_id)
    if result:
        title = case["clues"][clue_id]["title"]
        say(suspect, {"who": "you", "text": f"You slide {clue_id}. {title} across the table.", "act": True})
        say(suspect, {
            "who": "them", "text": result["reveal"] or "They look at it and shrug.",
            "unlocked": result["unlocked"], "caught": result.get("contradictions", []),
        })


def cloud_key():
    from streamlit.errors import StreamlitSecretNotFoundError

    try:
        return st.secrets.get("REQUESTY_API_KEY")
    except StreamlitSecretNotFoundError:
        return None


def chat_html(log, suspect, titles):
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
            unlock = '<span class="unlock">🔓 Unlocked: ' + esc(", ".join(f"{i}. {titles.get(i, '')}" for i in entry["unlocked"])) + "</span>"
        rows.append(f'<div class="bubble them"{style}><img src="{them}" alt=""><div class="say">{esc(entry["text"])}{unlock}</div></div>')
        for item in entry.get("caught", []):
            rows.append(
                f'<div class="caught"{style}><b>⚡ Caught lying</b><small>They said “{esc(item["text"].rstrip("."))}”. '
                f'{esc(item["clue"] or "Your clue")} says otherwise.</small></div>'
            )
    return '<div class="chat">' + "".join(rows) + "</div>"


def nerve_level(game, suspect):
    """How rattled a suspect looks, 0 to 100: up with each card shown to them, more with each lie caught.

    Only for show. It comes from what the player has done, never from who is guilty.
    """
    shown = sum(1 for e in game.history if e.get("action") == "present" and e.get("suspect") == suspect)
    caught = sum(1 for s, _claim in game.contradictions if s == suspect)
    return min(100, 10 + 15 * shown + 35 * caught)


def panel_suspect(game, suspect):
    from game import ai

    brief = engine.character_brief(game, suspect)
    uri = board.find_picture("suspects", suspect) or ""
    persona = brief["persona"].split(";")[0].split(". ")[0].rstrip(".") + "."
    nerves = nerve_level(game, suspect)
    st.markdown(
        f'<div class="who-head"><img src="{uri}" alt="{esc(brief["name"])}"><div>'
        f'<div class="kicker">Interrogation</div><h3>{esc(brief["name"])}</h3><div class="line">{esc(persona)}</div>'
        f'<div class="nerves" title="Show them evidence and catch their lies to rattle them">Nerves <i><b style="width:{nerves}%"></b></i></div>'
        "</div></div>",
        unsafe_allow_html=True,
    )
    titles = {c["id"]: c["title"] for c in engine.clue_list(game)}
    log = st.session_state.get("chats", {}).get(suspect, [])
    with st.container(key="chat_log", height=300 if log else "content", autoscroll=True):
        if log:
            st.markdown(chat_html(log, suspect, titles), unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="empty-chat">Ask {esc(brief["name"])} something, or show them a card.</div>',
                        unsafe_allow_html=True)
    cost = case["clock"]["question_cost"]
    st.pills(f"Ask · {cost} min", list(TOPICS), format_func=lambda t: TOPICS[t][0], key="ask_topic", on_change=ask_topic)
    opened = [c["id"] for c in engine.clue_list(game) if c["state"] == "open"]
    if opened:
        st.pills(f"Show a card · {cost} min", opened, format_func=lambda i: f"🃏 {i}", key="show_clue", on_change=show_evidence,
                 help="Show them evidence. The right card breaks a lie.")
    question = st.chat_input(f"Or type your own question ({cost} min)", max_chars=ai.MAX_QUESTION_LENGTH, key="typed")
    if question:
        with st.spinner(f"{brief['name']} is thinking…"):
            result = run(lambda game: ai.ask(engine, game, suspect, question, cloud_key=cloud_key))
        if result:
            say(suspect, {"who": "you", "text": question})
            say(suspect, {"who": "them", "text": result["reply"], "unlocked": result["unlocked"]})
        st.rerun()


# ---- Panel: one clue ------------------------------------------------------------------


def panel_clue(game, clue_id, fresh):
    item = next(c for c in engine.clue_list(game) if c["id"] == clue_id)
    verb = "Search it" if item["kind"] == "location" else "Open it"
    st.markdown(f'<div class="kicker">{board.KIND_ICON[item["kind"]]} Evidence {esc(clue_id)}</div><h3>{esc(item["title"])}</h3>',
                unsafe_allow_html=True)
    if item["state"] == "locked":
        st.markdown('<div class="facedown locked">🔒</div>', unsafe_allow_html=True)
        hints = engine.hint_list(game)
        if clue_id in hints:
            st.info(f"💡 {hints[clue_id]}")
        else:
            st.caption("Locked. Question suspects and show them cards to unlock it.")
            if st.button(f"💡 Hint · {engine.hint_cost()} min", key=f"hint_{clue_id}", use_container_width=True):
                run(engine.hint, clue_id)
                st.rerun()
        return
    if item["state"] == "available":
        st.markdown('<div class="facedown">?</div>', unsafe_allow_html=True)
        if st.button(f"🔍 {verb} · {case['clock']['clue_cost']} min", key=f"open_{clue_id}", type="primary",
                     use_container_width=True):
            run(engine.open_clue, clue_id)
            st.session_state.fresh = st.session_state.get("fresh", []) + [clue_id]
            st.rerun()
        return
    clue = engine.read_clue(game, clue_id)
    picture = board.find_picture("clues", clue_id)
    art = f'<img src="{picture}" alt="">' if picture else f'<div class="icon">{board.CARD_ICON.get(clue_id, "📄")}</div>'
    style = "" if clue_id in fresh else ' style="animation:none"'
    st.markdown(f'<div class="evidence"{style}>{art}<div class="body">{esc(clue["text"])}</div></div>', unsafe_allow_html=True)
    if clue["log"]:
        query = st.text_input("Search the log", key=f"search_{clue_id}", placeholder="A card number, a name, a time…")
        matches, total = search_log(clue["log"], query)
        if query.strip():
            st.caption(f"{len(matches)} of {total} lines match.")
        if matches:
            st.code("\n".join(matches), language=None, wrap_lines=True)
    if clue["chart"] in case.get("charts", {}):
        st.altair_chart(payoff_chart(case["charts"][clue["chart"]]), width="stretch")
        st.caption("All or nothing: the flat line is what the Class Rep gets if the exam is annulled.")
    if clue["hidden_text"] and st.toggle("🔦 Look closer", key=f"hidden_{clue_id}"):
        st.warning(clue["hidden_text"])
    st.caption("Tap a suspect's face, then show them this card.")


# ---- Panel: case sheet and accusation ----------------------------------------------------


def panel_sheet():
    st.markdown('<div class="kicker">Case sheet</div><h3>Cross off what it can’t be</h3>', unsafe_allow_html=True)
    st.caption("Your own notes. What is left is your accusation.")
    for column in COLUMNS:
        options = case["accusation"][column]
        left = len(options) - len(crossed(column))
        st.pills(f"{COLUMN_ICONS[column]} {column.capitalize()} · {left} left", [o["id"] for o in options],
                 format_func=lambda o, c=column: label(c, o), selection_mode="multi", key=f"sheet_{column}")
    if st.button("⚖️ Ready? Accuse", type="primary", use_container_width=True, key="to_accuse"):
        set_focus("accuse")
        st.rerun()


def verdict_html(right):
    return '<div class="verdict">' + "".join(
        f'<div class="{"ok" if c in right else "no"}"><span>{"✓" if c in right else "✗"}</span>{c.upper()}</div>' for c in COLUMNS
    ) + "</div>"


def panel_accuse(game):
    strikes_left = case["max_strikes"] - game.strikes
    st.markdown(f'<div class="kicker">The accusation · {strikes_left} {"try" if strikes_left == 1 else "tries"} left</div>'
                "<h3>Who did it, how, where and why?</h3>", unsafe_allow_html=True)
    verdict = st.session_state.get("verdict")
    if verdict is not None:
        st.markdown(verdict_html(verdict), unsafe_allow_html=True)
        st.caption("Wrong. Keep the ✓ parts and rethink the ✗ ones.")
    for column in COLUMNS:
        out = set(crossed(column))
        st.pills(f"{COLUMN_ICONS[column]} {column.capitalize()}", [o["id"] for o in case["accusation"][column]],
                 format_func=lambda o, c=column, out=out: label(c, o) + (" ✗" if o in out else ""), key=f"accuse_{column}")
    if st.button("⚖️ Accuse", type="primary", use_container_width=True, key="accuse_go"):
        choice = {c: st.session_state.get(f"accuse_{c}") for c in COLUMNS}
        missing = [c for c in COLUMNS if choice[c] is None]
        if missing:
            st.warning(f"Pick one in each row first. Missing: {', '.join(missing)}.")
            return
        result = run(engine.accuse, *(choice[c] for c in COLUMNS))
        if result and result["status"] == "playing":
            st.session_state.verdict = engine.right_parts(current_game())
            st.session_state.toast = (f"{result['correct']} of 4 right. {result['strikes_left']} tries left.", "⚖️")
        st.rerun()


# ---- The finale ------------------------------------------------------------------------


def finale(game):
    solution = engine.solution(game)
    culprit = solution["who"]
    uri = board.find_picture("suspects", culprit) or ""
    solved = game.status == "solved"
    stamp, heading = ("GUILTY", "Case closed") if solved else ("CASE COLD", "The trail went cold")
    sub = (f"Solved at {engine.clock_label(game)} · {len(game.contradictions)} {"lie" if len(game.contradictions) == 1 else "lies"} caught" if solved
           else f"It was {case['suspects'][culprit]['name']} all along.")
    facts = "".join(f"<div><small>{c.upper()}</small>{esc(label(c, solution[c]))}</div>" for c in COLUMNS)
    medals = "".join(f"<span>🏅 {esc(b['title'])}</span>" for b in engine.badge_list(game))
    st.markdown(
        f'<div class="finale{"" if solved else " cold"}"><div class="mug"><img src="{uri}" alt=""><span class="slam">{stamp}</span></div>'
        f'<h1>{heading}</h1><div class="sub">{esc(sub)}</div><div class="facts">{facts}</div>'
        f'{f"<div class=medals>{medals}</div>" if medals else ""}</div>',
        unsafe_allow_html=True,
    )
    _, middle, _ = st.columns([1, 3, 1])
    with middle:
        scene = denouement(game)
        if scene:
            with st.expander("📜 Half past seven, the boardroom: read the confrontation"):
                for paragraph in scene.split("\n\n"):
                    st.markdown(plain(paragraph))
        if st.button("🔁 Play a new case", type="primary", use_container_width=True):
            new_case()
            st.rerun()


# ---- The start screen ------------------------------------------------------------------

STORY = (
    "Thursday, 23:47, a storm over Carcavelos. Tomorrow's **Semiconductor Valuation** final has just leaked "
    "to all 212 students. The Dean wants a name **before 09:00**."
)

HOW_TO_PLAY = f"""<div class="how-to">
<div><b>🗺️</b>Search places and documents · {case['clock']['clue_cost']} min</div>
<div><b>🗣️</b>Tap a face to interrogate · {case['clock']['question_cost']} min</div>
<div><b>⚡</b>Show the card that breaks their lie</div>
<div><b>⚖️</b>Accuse: who, how, where, why · {case['max_strikes']} tries</div>
</div>"""


def pick_detective(avatar):
    st.session_state.player_avatar = avatar


def finish_intro():
    st.session_state.intro_done = True


@st.dialog("The exam has leaked", width="large", on_dismiss=finish_intro)
def intro_dialog():
    """The story and the rules in one glance, and who you are, before the first move."""
    uri = board.data_uri(str(COVER))
    if uri:
        st.markdown(
            f'<img src="{uri}" alt="" style="width:100%;max-height:160px;object-fit:cover;object-position:50% 45%;border-radius:10px">',
            unsafe_allow_html=True,
        )
    st.markdown(f'<div class="kicker">{esc(TITLE)}</div>', unsafe_allow_html=True)
    st.markdown(STORY)
    st.markdown(PAGE_CSS + HOW_TO_PLAY, unsafe_allow_html=True)
    chosen = player_avatar()
    for column, (avatar, text) in zip(st.columns(len(AVATARS)), AVATARS.items()):
        with column:
            uri = board.find_picture("detectives", avatar)
            if uri:
                ring = " picked" if avatar == chosen else ""
                st.markdown(f'<img class="detective-pick{ring}" src="{uri}" alt="">', unsafe_allow_html=True)
            st.button(text, key=f"pick_{avatar}", type="primary" if avatar == chosen else "secondary",
                      use_container_width=True, on_click=pick_detective, args=(avatar,))
    st.text_input("Your name", key="player_name", placeholder="Detective", max_chars=24)
    if st.button("🔍 Start the investigation", type="primary", use_container_width=True):
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
            st.markdown(f'<div class="kicker">📍 Off campus</div><h3>{esc(board.MAP_SPOTS[value][2])}</h3>', unsafe_allow_html=True)
            st.write(board.MAP_SPOTS[value][3])
        elif kind == "sheet":
            panel_sheet()
        elif kind == "accuse":
            panel_accuse(game)
        else:
            panel_home(game)

# Called last, so the story and rules open over the game on a new case.
if not st.session_state.get("intro_done", bool(game.history)):
    intro_dialog()
