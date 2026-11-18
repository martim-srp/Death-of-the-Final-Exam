"""Death of the Final Exam: Streamlit interface.

Run with:  streamlit run app.py

The game state lives in st.session_state on the server. The browser only ever
receives what the engine returns, so locked clues and the solution never reach it.
"""

import base64
import html
import re
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import db
import reloading
from game.case import load_case

COVER = Path(__file__).resolve().parent / "assets" / "cover.webp"
# The campus map picture. To swap it, replace the file (any size, WebP/PNG/JPG) and
# move the pins below: each is (x, y) as a fraction of the picture's width and height,
# at the centre of the round head of the pin drawn on the picture. Only the places
# drawn on the picture get a pin; the cafeteria (L2) is not on it, so it stays in the case file.
CAMPUS_MAP = Path(__file__).resolve().parent / "assets" / "campus-map.webp"
MAP_PINS = {
    "L1": (0.365, 0.440, "Library gate"),  # the printer pin, library print station
    "L3": (0.317, 0.731, "Residence"),  # the house pin
    "L4": (0.537, 0.550, "Faculty corridor"),  # the graduation cap pin, Professor's office
    "L5": (0.672, 0.115, "Beach café"),  # the coffee cup pin
}
# Optional evidence pictures, one <clue id>.<png|jpg|webp> each (D1.webp, L4.png…), shown inside an opened clue.
CLUE_PICTURES = Path(__file__).resolve().parent / "assets" / "clues"
PORTRAITS = Path(__file__).resolve().parent / "assets" / "suspects"  # one <suspect id>.<png|jpg|webp|svg> each
# File types a portrait may have, in order of preference: a picture someone supplies
# (PNG, JPG or WebP) wins over the drawn SVG of the same suspect.
PORTRAIT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}
TITLE = load_case()["title"]  # the game's name lives in data/case.json

# The detectives a player can be. Purely cosmetic: shown on their side of the chat.
AVATARS = {"🕵️": "Inspector", "🕵️‍♀️": "Sleuth", "🦉": "Night owl", "🦊": "Fox", "🐈‍⬛": "Black cat", "🎩": "Gentleman thief"}
DEFAULT_AVATAR = "🕵️"
# A place drawn on the map with no clue behind it: (x, y) as fractions, like MAP_PINS.
# The text stays neutral, because the restaurant is also an answer you can pick under "Where".
MAP_SPOTS = {"chiado": (0.088, 0.663, "Restaurant in Chiado", "Off campus, across Lisbon. Nothing to search here tonight.")}
# The tabs. Their labels are also the tab widget's values, so a portrait can switch to questioning.
MAP_TAB, CASE_TAB, QUESTION_TAB, ACCUSE_TAB = "🗺️ Campus map", "📁 Case file", "🗣️ Question suspects", "⚖️ Accuse"
# What the detective says when they pick a topic instead of typing.
TOPIC_QUESTIONS = {
    "alibi": "Where were you last night?",
    "exam": "What do you know about tomorrow's exam?",
    "report": "Tell me about the report.",
    "work": "What is your job here?",
    "teaching_assistant": "What can you tell me about the Teaching Assistant?",
    "leak": "Who leaked the paper?",
    "other": "Is there anything else I should know?",
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


def label(column, option_id):
    return next(o["label"] for o in case["accusation"][column] if o["id"] == option_id)


_MARKDOWN_SPECIAL = re.compile(r"([\\`*_\[\]<>#$~|])")

# Categorical slots 1 and 2 of the validated chart palette (blue, orange).
SERIES_COLORS = ["#2a78d6", "#eb6834"]


def plain(text):
    """Escape Markdown so story text is shown exactly as written."""
    return _MARKDOWN_SPECIAL.sub(r"\\\1", text)


def search_log(log, query):
    """The log lines that contain the query (case-insensitive), and the total line count."""
    lines = log.splitlines()
    needle = query.strip().lower()
    if not needle:
        return lines, len(lines)
    return [line for line in lines if needle in line.lower()], len(lines)


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
    return (mock_band + notes + rival_rule + lines + hover).properties(title=spec["title"], height=280)


def denouement(game):
    """The closing scene of this game's variant. Only once the case is closed."""
    engine.solution(game)  # raises GameError while the game is still running
    text = case["variants"][game.variant].get("denouement", "")
    return text.format_map(game.variables)


def caught_moment(caught, clue_titles):
    """The moment a suspect is caught contradicting themselves, shown right under the answer."""
    for item in caught:
        name = case["suspects"][item["suspect"]]["name"]
        clue = f"{item['clue']}. {clue_titles.get(item['clue'], '')}".rstrip(". ")
        with st.container(border=True):
            st.markdown(f"#### ⚡ Contradiction! {plain(name)} was caught out")
            st.markdown(f"Earlier they told you: *“{plain(item['text'])}”*")
            st.markdown(f"**{plain(clue)}** says otherwise.")


def contradiction_board(game, clue_titles):
    """Every contradiction caught so far, oldest first."""
    caught = engine.contradiction_list(game)
    with st.expander(f"🧩 Contradictions caught ({len(caught)})", expanded=bool(caught)):
        if not caught:
            st.caption("None yet. Show a suspect a clue that breaks their story to catch them out.")
        for item in caught:
            name = case["suspects"][item["suspect"]]["name"]
            source = f"{item['clue']}. {clue_titles.get(item['clue'], '')}" if item["clue"] else "a clue"
            st.markdown(f"- **{plain(name)}**: “{plain(item['text'])}” Broken by *{plain(source.rstrip('. '))}*.")


# ---- The noir look: portraits, suspect cards and the notebook ----------------------

NOIR_CSS = """
<style>
:root { --card-w: 132px; --img-h: 165px; --card-gap: 12px; }
@media (max-width: 640px) {
  :root { --card-w: calc((100vw - 2rem - 4 * 6px) / 5); --img-h: calc(var(--card-w) * 1.25); --card-gap: 6px; }
}
.suspect-row { display: flex; gap: var(--card-gap); padding: 0 0 0.25rem; }
.suspect-card { flex: 0 0 var(--card-w); width: var(--card-w); text-align: center; position: relative; }
.suspect-card img { width: 100%; height: var(--img-h); object-fit: cover; display: block; border-radius: 10px;
  border: 2px solid transparent; transition: transform 0.15s, border-color 0.15s; }
.suspect-card.active img { border-color: #c0392b; box-shadow: 0 0 0 3px rgba(192, 57, 43, 0.35); }
.suspect-card.ruled-out img { filter: grayscale(1) brightness(0.55); }
.suspect-card .name { font-family: Georgia, serif; font-size: 0.85rem; margin-top: 0.3rem; line-height: 1.2; }
.suspect-card .status { font-size: 0.75rem; opacity: 0.75; }
.suspect-card .caught { color: #e0645a; font-weight: 600; }
.suspect-card .stamp { position: absolute; top: calc(var(--img-h) * 0.45); left: 50%; transform: translate(-50%, -50%) rotate(-14deg);
  border: 2px solid #c0392b; color: #c0392b; background: rgba(20, 16, 14, 0.75); padding: 0 0.35rem;
  font: 700 0.8rem "Courier New", monospace; letter-spacing: 0.08em; white-space: nowrap; }
@media (max-width: 640px) {
  .suspect-card .name { font-size: 0.68rem; }
  .suspect-card .status { font-size: 0.6rem; }
  .suspect-card .stamp { font-size: 0.55rem; }
}
.suspect-portrait { width: 96px; max-width: 30vw; aspect-ratio: 4 / 5; object-fit: cover; border-radius: 10px; }
</style>
"""

# Invisible buttons laid over the portraits, so tapping a face opens the questioning.
GAME_CSS = """
<style>
.st-key-talk_row { display: flex; flex-flow: row nowrap; gap: var(--card-gap); position: relative; z-index: 3;
  height: var(--img-h); margin-bottom: calc(-1 * var(--img-h) - 1rem); }
.st-key-talk_row > div { flex: 0 0 var(--card-w) !important; width: var(--card-w) !important; min-width: 0 !important; }
.st-key-talk_row button { width: 100%; height: var(--img-h); opacity: 0; cursor: pointer; padding: 0; }
div:has(> .st-key-hud) { position: sticky !important; top: 3.75rem; z-index: 5; background: #14100e !important; }
.st-key-hud { padding: 0.35rem 0 0.2rem; background: #14100e; gap: 0.2rem; }
.st-key-hud [data-testid="stProgress"] > div { height: 4px; }
.st-key-map_pick [role="radiogroup"] { flex-wrap: wrap; }
.st-key-case_board { gap: 0.1rem; background: #f1e7d6; color: #2a201b; border-radius: 10px; }
.st-key-case_board p, .st-key-case_board label, .st-key-case_board span { color: #2a201b !important; }
.st-key-case_board [data-testid="stCaptionContainer"] p { color: #6b5a4e !important; }
.st-key-case_board .board-head { margin-top: 0.5rem; padding: 0.15rem 0.5rem; background: #2a201b; color: #f1e7d6;
  border-radius: 4px; font: 600 0.8rem Georgia, serif; letter-spacing: 0.06em; text-transform: uppercase;
  display: flex; justify-content: space-between; }
.st-key-case_board .board-head span { color: #e8b4a8 !important; text-transform: none; letter-spacing: 0; }
.st-key-case_board [data-testid="stCheckbox"] { min-height: 0; }
.st-key-case_board [data-testid="stMarkdownContainer"]:has(.board-head) { margin-bottom: 0.45rem; }
.st-key-case_board [data-testid="stCheckbox"] label { font-size: 0.85rem; line-height: 1.25; padding: 0.1rem 0; }
.st-key-case_board [data-testid="stCheckbox"]:has(input:checked) p { text-decoration: line-through;
  text-decoration-color: #c0392b; text-decoration-thickness: 2px; opacity: 0.55; }
.hud { display: flex; flex-wrap: wrap; gap: 0.4rem 1.1rem; align-items: baseline; font-size: 0.95rem; }
.hud b { font-family: Georgia, serif; font-size: 1.25rem; }
.hud .low { color: #e0645a; }
.hud .muted { opacity: 0.7; font-size: 0.85rem; }
.how-to { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.6rem; margin: 0.4rem 0 0.8rem; }
.how-to div { border: 1px solid #3a2e28; border-radius: 10px; padding: 0.6rem 0.7rem; background: #1c1613; font-size: 0.9rem; }
.how-to b { display: block; font-family: Georgia, serif; font-size: 1rem; margin-bottom: 0.15rem; }
.st-key-chat_log [data-testid="stChatMessage"] { border-radius: 16px; padding: 0.6rem 0.8rem; width: 86%; }
[class*="st-key-msg_them"] [data-testid="stChatMessage"] { background: #241c18; border: 1px solid #3a2e28;
  border-top-left-radius: 4px; }
[class*="st-key-msg_you"] [data-testid="stChatMessage"] { margin-left: auto; background: #3a1d18;
  border: 1px solid #6b2a21; border-top-right-radius: 4px; flex-direction: row-reverse; text-align: right; }
.st-key-chat_log [data-testid="stText"] { font-family: Georgia, serif; font-size: 1rem; }
@media (max-width: 640px) {
  .st-key-cover { display: none; }
  .st-key-header h1 { font-size: 1.9rem; }
  [data-baseweb="tab"] p, [data-baseweb="tab"] [data-testid="stMarkdownContainer"] p { font-size: 0.78rem !important; }
  [data-baseweb="tab-list"] { gap: 0.6rem; }
  div:has(> .st-key-hud) { top: 3.4rem; }
  .hud { font-size: 0.8rem; gap: 0.2rem 0.7rem; }
  .hud .long { display: none; }
  .hud b { font-size: 1.1rem; }
}
</style>
"""


@st.cache_data
def portrait_uri(suspect):
    """The suspect's portrait as a data URI, or None if there is no picture for them."""
    for extension, mime in PORTRAIT_TYPES.items():
        path = PORTRAITS / f"{suspect}{extension}"
        if path.exists():
            return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")
    return None


def suspect_status(game):
    """For each suspect: whether you have questioned them, and how many contradictions you caught."""
    questioned = {event["suspect"] for event in game.history if "suspect" in event}
    caught = {}
    for suspect, _claim in game.contradictions:
        caught[suspect] = caught.get(suspect, 0) + 1
    return {s: {"questioned": s in questioned, "caught": caught.get(s, 0)} for s in case["suspects"]}


def ruled_out(suspect):
    """Whether the player has ticked this suspect off in their notebook or crossed them off the case board."""
    return bool(st.session_state.get(f"note_suspect_{suspect}") or st.session_state.get(f"board_who_{suspect}"))


BOARD_HEADINGS = {"who": "👤 Who", "how": "🔧 How", "where": "📍 Where", "why": "💭 Why"}


def case_board():
    """A deduction grid, like a board game's detective sheet: cross off what it cannot be.

    The player's own notes, kept in this browser session. It never changes the game.
    """
    with st.container(key="case_board", border=True):
        st.markdown("**📋 Case board**")
        st.caption("Cross off what it cannot be. What is left is your accusation.")
        for column, heading in BOARD_HEADINGS.items():
            options = case["accusation"][column]
            crossed = sum(bool(st.session_state.get(f"board_{column}_{o['id']}")) for o in options)
            st.markdown(f'<div class="board-head">{heading} <span>{len(options) - crossed} left</span></div>',
                        unsafe_allow_html=True)
            for option in options:
                st.checkbox(option["label"], key=f"board_{column}_{option['id']}")


def talk_to(suspect):
    """Tapping a portrait: pick that suspect and go to the questioning tab."""
    st.session_state.suspect = suspect
    st.session_state.view = QUESTION_TAB


def suspect_cards(game):
    """A row of portrait cards: who you have questioned, who you caught out, who you ruled out.

    An invisible button sits on each portrait, so tapping a face opens the questioning.
    """
    st.markdown(GAME_CSS, unsafe_allow_html=True)
    with st.container(key="talk_row"):
        for suspect, details in case["suspects"].items():
            st.button(f"Talk to {details['name']}", key=f"talk_{suspect}", on_click=talk_to, args=(suspect,))
    picked = st.session_state.get("suspect")
    cards = []
    for suspect, status in suspect_status(game).items():
        name = html.escape(case["suspects"][suspect]["name"].removeprefix("The "))
        uri = portrait_uri(suspect)
        picture = f'<img src="{uri}" alt="{name}">' if uri else ""
        line = "Questioned" if status["questioned"] else "Not questioned yet"
        if status["caught"]:
            line += f' · <span class="caught">⚡ {status["caught"]} caught</span>'
        out = ruled_out(suspect)
        stamp = '<div class="stamp">RULED OUT</div>' if out else ""
        classes = "suspect-card" + (" ruled-out" if out else "") + (" active" if suspect == picked else "")
        cards.append(
            f'<div class="{classes}">{picture}{stamp}'
            f'<div class="name">{name}</div><div class="status">{line}</div></div>'
        )
    st.markdown(NOIR_CSS + '<div class="suspect-row">' + "".join(cards) + "</div>", unsafe_allow_html=True)
    st.caption("Tap a portrait to question that suspect.")


def hud(game):
    """The status bar above the game: the time, what is left, and who you are."""
    left = engine.time_left(game)
    hours, minutes = divmod(max(left, 0), 60)
    strikes = case["max_strikes"] - game.strikes
    avatar = st.session_state.get("player_avatar") or DEFAULT_AVATAR
    name = html.escape(st.session_state.get("player_name") or "Detective")
    low = ' class="low"' if left <= 120 else ""
    with st.container(key="hud"):
        st.markdown(
            f'<div class="hud"><span>⏱ <b>{engine.clock_label(game)}</b> '
            f"<span{low}>{hours}h {minutes:02d}m<span class=\"long\"> to 09:00</span></span></span>"
            f"<span>⚖️ {strikes}<span class=\"long\"> accusation{'s' if strikes != 1 else ''}</span> left</span>"
            f"<span>⚡ {len(game.contradictions)} caught</span>"
            f'<span class="muted long">{avatar} {name}</span></div>',
            unsafe_allow_html=True,
        )
        st.progress(min(game.clock / case["clock"]["limit_minutes"], 1.0))


def notebook(game):
    """The detective's notebook: tick off suspects and clues, and jot down hunches.

    It is the player's own scratch paper, kept in this browser session only. It never
    changes the game: the engine alone decides what is true.
    """
    with st.expander("📓 Detective's notebook", expanded=True):
        st.markdown("**Suspects I have ruled out**")
        for suspect, details in case["suspects"].items():
            st.checkbox(details["name"], key=f"note_suspect_{suspect}")
        opened = [c for c in engine.clue_list(game) if c["state"] == "open"]
        st.markdown("**Clues I have dealt with**")
        if not opened:
            st.caption("Open a clue in the case file and it will appear here.")
        for clue in opened:
            st.checkbox(f"{clue['id']}. {clue['title']}", key=f"note_clue_{clue['id']}")
        st.text_area("Hunches", key="note_hunches", placeholder="Who was lying, and about what?")


def clear_notebook():
    for key in [k for k in st.session_state if str(k).startswith(("note_", "board_"))]:
        del st.session_state[key]


# ---- The campus map ---------------------------------------------------------------

PIN_COLORS = {"locked": "#5a5048", "available": "#c0392b", "open": "#efe6d8"}
PIN_STATES = {"locked": "Locked", "available": "Not searched yet", "open": "Searched"}


def map_points(game):
    """One pin per location clue on the map, with its state from the engine."""
    points = []
    for item in engine.clue_list(game):
        if item["id"] in MAP_PINS:
            x, y, place = MAP_PINS[item["id"]]
            points.append(
                {"id": item["id"], "x": x, "y": y, "place": place, "title": item["title"],
                 "state": item["state"], "status": PIN_STATES[item["state"]]}
            )
    return points


MAP_JS = """
export default function(component) {
    const { data, setTriggerValue, parentElement } = component;
    let holder = parentElement.querySelector(".campus-map");
    if (!holder) {
        holder = document.createElement("div");
        holder.className = "campus-map";
        parentElement.appendChild(holder);
    }
    holder.innerHTML = data;
    holder.querySelectorAll("[data-place], [data-spot]").forEach((pin) => {
        const go = () => setTriggerValue("place", pin.getAttribute("data-place") || pin.getAttribute("data-spot"));
        pin.addEventListener("click", go);
        pin.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
    });
}
"""

MAP_CSS = """
.campus-map svg { width: 100%; height: auto; display: block; border-radius: 10px; }
.campus-map [data-place], .campus-map [data-spot] { cursor: pointer; }
.campus-map [data-place]:hover circle.pin, .campus-map [data-place]:focus circle.pin,
.campus-map [data-spot]:hover circle.pin, .campus-map [data-spot]:focus circle.pin { stroke-width: 9; }
.campus-map [data-place]:focus, .campus-map [data-spot]:focus { outline: none; }
"""

map_component = st.components.v2.component("campus_map", js=MAP_JS, css=MAP_CSS)


@st.cache_data
def campus_picture():
    """The map picture as a data URI, with its size in pixels."""
    from PIL import Image  # installed with streamlit

    with Image.open(CAMPUS_MAP) as picture:
        size = picture.size
        mime = Image.MIME[picture.format]
    uri = f"data:{mime};base64," + base64.b64encode(CAMPUS_MAP.read_bytes()).decode("ascii")
    return uri, size


def campus_svg(points, picked=None):
    """The map picture, with each pin drawn on it made clickable and ringed in its state's colour.

    All of it is our own trusted markup.
    """
    uri, (width, height) = campus_picture()
    scale = width / 1200  # sizes below are for a 1200-pixel-wide picture
    pins = []
    for p in points:
        x, y = p["x"] * width, p["y"] * height
        color = PIN_COLORS[p["state"]]
        text_color = "#14100e" if p["state"] == "open" else "#efe6d8"
        picked_ring = (
            '<circle r="38" fill="none" stroke="#efe6d8" stroke-width="3" stroke-dasharray="6 5"/>'
            if p["id"] == picked
            else ""
        )
        label = html.escape(f"{p['place']}: {p['status']}")
        pins.append(
            f'<g data-place="{p["id"]}" transform="translate({x:.0f} {y:.0f}) scale({scale:.3f})" '
            f'role="button" tabindex="0" aria-label="{label}">'
            f"<title>{label}</title>{picked_ring}"
            f'<circle class="pin" r="29" fill="none" stroke="{color}" stroke-width="6"/>'
            '<circle r="55" fill="#000" fill-opacity="0"/>'  # a finger-sized target on a phone
            f'<g transform="translate(26 -26)"><circle r="14" fill="{color}" stroke="#14100e" stroke-width="2"/>'
            f'<text y="4.5" text-anchor="middle" font-family="Georgia, serif" font-size="13" font-weight="bold" '
            f'fill="{text_color}">{p["id"]}</text></g></g>'
        )
    for spot, (sx, sy, place, _note) in MAP_SPOTS.items():
        label = html.escape(f"{place}: nothing to search")
        pins.append(
            f'<g data-spot="{spot}" transform="translate({sx * width:.0f} {sy * height:.0f}) scale({scale:.3f})" '
            f'role="button" tabindex="0" aria-label="{label}"><title>{label}</title>'
            '<circle class="pin" r="29" fill="none" stroke="#5a5048" stroke-width="4" stroke-dasharray="5 5"/>'
            '<circle r="55" fill="#000" fill-opacity="0"/></g>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Map of the campus"><image href="{uri}" width="{width}" height="{height}"/>'
        + "".join(pins)
        + "</svg>"
    )


def picked_on_map():
    """Copy a tap on a map pin into the place picker, before the page is drawn again."""
    state = st.session_state.get("campus_map") or {}
    place = state.get("place") if hasattr(state, "get") else getattr(state, "place", None)
    if place in MAP_PINS:
        st.session_state.map_pick = place
        st.session_state.pop("map_spot", None)
    elif place in MAP_SPOTS:
        st.session_state.map_pick = None
        st.session_state.map_spot = place


def campus_map(game):
    """The map tab: tap a pin (or a name below the map) to go there."""
    points = map_points(game)
    by_id = {p["id"]: p for p in points}
    map_column, place_column = st.container(), st.container()
    with map_column:
        map_component(
            data=campus_svg(points, st.session_state.get("map_pick")), key="campus_map",
            on_place_change=picked_on_map,
        )
        st.caption("🔴 not searched yet · ⚪ searched · ⚫ locked")
    with place_column:
        place = st.pills(
            "Go to", list(by_id), key="map_pick", format_func=lambda i: by_id[i]["place"], width="stretch"
        )
        if place is None:
            spot = st.session_state.get("map_spot")
            if spot in MAP_SPOTS:
                st.markdown(f"#### 📍 {MAP_SPOTS[spot][2]}")
                st.markdown(MAP_SPOTS[spot][3])
            st.caption("Tap a pin on the map, or a place above, to go there.")
            return
        st.session_state.pop("map_spot", None)
        point = by_id[place]
        st.markdown(f"#### 📍 {plain(point['title'])}")
        if point["state"] == "locked":
            st.markdown("🔒 Locked. You have no reason to be here yet. Keep investigating.")
        elif point["state"] == "available":
            if st.button(f"Search it ({case['clock']['clue_cost']} min)", key="map_search", type="primary"):
                run(engine.open_clue, place)
                st.rerun()
        else:
            clue = engine.read_clue(game, place)
            st.write(clue["text"])
            if clue["log"]:
                st.caption("Its log is in the 📁 Case file, where you can search it.")


def run(action, *args):
    """Run an engine action, save the game, and turn rule errors into messages."""
    game = current_game()
    locked = {c["id"] for c in engine.clue_list(game) if c["state"] == "locked"}
    try:
        result = action(game, *args)
    except GameError as error:
        st.session_state.flash = ("error", str(error))
        return None
    save(game)
    unlocked = [c for c in engine.clue_list(game) if c["id"] in locked and c["state"] != "locked"]
    if unlocked:
        names = ", ".join(f"{c['id']}. {c['title']}" for c in unlocked)
        st.session_state.toast = f"New clue unlocked: {names}. Find it in the case file or on the map."
    return result


game = current_game()

# ---- Sidebar: the clock -------------------------------------------------------

with st.sidebar:
    st.title(f"🕵️ {TITLE}")
    st.metric("Time", engine.clock_label(game), help="You must accuse before 09:00.")
    st.progress(game.clock / case["clock"]["limit_minutes"])
    st.caption(
        f"Opening a clue costs {case['clock']['clue_cost']} min. "
        f"A question costs {case['clock']['question_cost']} min."
    )
    st.write(f"Wrong accusations left: **{case['max_strikes'] - game.strikes}**")
    st.write(f"Contradictions caught: **{len(game.contradictions)}**")
    badges = engine.badge_list(game)
    if badges:
        st.subheader("Badges")
        for badge in badges:
            st.markdown(f"🏅 **{badge['title']}**", help=badge["description"])
    if game.status == "playing":
        notebook(game)
    if st.button("New case", use_container_width=True):
        start_new_game()
        clear_notebook()
        st.session_state.pop("last_answer", None)
        st.session_state.pop("last_caught", None)
        st.rerun()
    st.caption("Bookmark this page to come back to this case later.")

flash = st.session_state.pop("flash", None)
if flash:
    getattr(st, flash[0])(flash[1])
toast = st.session_state.pop("toast", None)
if toast:
    st.toast(toast, icon="🔓")

# ---- Intro --------------------------------------------------------------------

STORY = (
    "It is a stormy Thursday night on the Carcavelos campus. At 23:47 an anonymous number posted "
    "`SV_Final_v3.pdf`, tomorrow's **Semiconductor Valuation** final, to all 212 students in the "
    "cohort group chat. The Dean has made you examiner for the honour council: "
    "*\"I do not want a scandal. I want a name, and I want it before nine.\"*"
)

HOW_TO_PLAY = f"""<div class="how-to">
<div><b>1. Search</b>Tap places on the 🗺️ map and open documents in the 📁 case file. Each costs {case['clock']['clue_cost']} min.</div>
<div><b>2. Question</b>Tap a suspect's portrait to talk. Ask anything, or show them a clue. Each costs {case['clock']['question_cost']} min.</div>
<div><b>3. Catch lies</b>Show a suspect the clue that breaks their story and you catch them out ⚡. Clues unlock new clues.</div>
<div><b>4. Accuse</b>Cross off what it cannot be on the 📋 case board, then name who, how, where and why before 09:00. You have {case['max_strikes']} tries.</div>
</div>"""


def finish_intro():
    st.session_state.intro_done = True


@st.dialog("Welcome, examiner", width="large", on_dismiss=finish_intro)
def intro_dialog():
    """The story and the rules, and who you are, before the first move."""
    uri = cover_uri()
    if uri:
        st.markdown(
            f'<img src="{uri}" alt="" style="width:100%;max-height:180px;object-fit:cover;object-position:50% 45%;border-radius:10px">',
            unsafe_allow_html=True,
        )
    st.markdown(STORY)
    st.markdown("**How to play**")
    st.markdown(GAME_CSS + HOW_TO_PLAY, unsafe_allow_html=True)
    st.pills(
        "Choose your detective", list(AVATARS), key="player_avatar", default=DEFAULT_AVATAR, required=True,
        format_func=lambda a: f"{a} {AVATARS[a]}",
    )
    st.text_input("Your name", key="player_name", placeholder="Detective", max_chars=24)
    if st.button("Start the investigation", type="primary", use_container_width=True):
        finish_intro()
        st.rerun()


@st.cache_data
def cover_uri():
    if not COVER.exists():
        return None
    return "data:image/webp;base64," + base64.b64encode(COVER.read_bytes()).decode("ascii")


with st.container(key="header"):
    cover_column, intro_column = st.columns([1, 5], vertical_alignment="center", gap="medium")
    with cover_column:
        with st.container(key="cover"):
            if COVER.exists():
                st.image(str(COVER), width=120)
    with intro_column:
        st.title(TITLE)
        st.markdown(
            "An exam has leaked the night before it is sat. Find out **who** leaked it, **how**, "
            "**where** and **why**, before 09:00."
        )
        st.caption(game.variables["weather"])
        if game.status == "playing" and st.button("📖 Story and how to play"):
            st.session_state.intro_done = False

# ---- Case closed ----------------------------------------------------------------

if game.status != "playing":
    solution = engine.solution(game)
    if game.status == "solved":
        st.success(f"Case solved at {engine.clock_label(game)}.")
    else:
        st.error("The case has gone cold.")
    scene = denouement(game)
    if scene:
        with st.container(border=True):
            st.subheader("Half past seven, the boardroom")
            for paragraph in scene.split("\n\n"):
                st.markdown(plain(paragraph))
    st.subheader("What really happened")
    st.write(
        f"**{label('who', solution['who'])}**: {label('how', solution['how']).lower()}, "
        f"at {label('where', solution['where']).lower()}, {label('why', solution['why']).lower()}."
    )
    st.stop()

hud(game)

play_column, board_column = st.columns([5, 2], gap="medium")
with board_column:
    case_board()
with play_column:
    suspect_cards(game)
    map_tab, case_tab, question_tab, accuse_tab = st.tabs(
        [MAP_TAB, CASE_TAB, QUESTION_TAB, ACCUSE_TAB], key="view", on_change="rerun"
    )

with map_tab:
    campus_map(game)

# ---- Case file ------------------------------------------------------------------

def show_clue(item, expanded):
    """An opened clue, in an expander: its text, a log search, a chart, hidden text."""
    icon = "📄" if item["kind"] == "document" else "📍"
    title = f"{icon} {item['id']}. {item['title']}"
    clue = engine.read_clue(game, item["id"])
    with st.expander(title, expanded=expanded):
        picture = next((CLUE_PICTURES / f"{item['id']}{ext}" for ext in (".webp", ".png", ".jpg")
                        if (CLUE_PICTURES / f"{item['id']}{ext}").exists()), None)
        if picture:
            st.image(str(picture), width=360)
        st.write(clue["text"])
        if clue["log"]:
            query = st.text_input(
                "Search this log",
                key=f"search_{item['id']}",
                placeholder="A card number, a job, a time…",
            )
            matches, total = search_log(clue["log"], query)
            if query.strip():
                st.caption(f"{len(matches)} of {total} lines match “{query.strip()}”.")
            if matches:
                st.code("\n".join(matches), language=None, wrap_lines=True)
        if clue["chart"] in case.get("charts", {}):
            spec = case["charts"][clue["chart"]]
            st.altair_chart(payoff_chart(spec), width="stretch")
            st.caption(
                "The fellowship is all or nothing. The flat line is what the Class Representative gets "
                "if the exam is annulled; the step is what they get if it goes ahead, assuming the "
                "Exchange Student scores their mock average."
            )
        if clue["hidden_text"] and st.toggle("Show hidden text", key=f"hidden_{item['id']}"):
            st.warning(clue["hidden_text"])


with case_tab:
    clues = engine.clue_list(game)
    ready = [c for c in clues if c["state"] == "available"]
    opened = [c for c in clues if c["state"] == "open"]
    locked = [c for c in clues if c["state"] == "locked"]
    if ready:
        st.markdown(f"**Ready to open** · {case['clock']['clue_cost']} min each")
        for item in ready:
            icon = "📄" if item["kind"] == "document" else "📍"
            if st.button(
                f"Open {icon} {item['id']}. {item['title']} ({case['clock']['clue_cost']} min)", key=f"open_{item['id']}"
            ):
                run(engine.open_clue, item["id"])
                st.rerun()
    if opened:
        st.markdown(f"**Opened** · {len(opened)}")
        newest = game.opened[-1] if game.opened else None
        for item in opened:
            show_clue(item, expanded=item["id"] == newest)
    if locked:
        with st.expander(f"🔒 Locked · {len(locked)}"):
            st.caption("Question suspects, show them clues and search places to unlock these.")
            for item in locked:
                st.markdown(f"🔒 {item['id']}. {plain(item['title'])}")

# ---- Questioning --------------------------------------------------------------

with question_tab:
    from streamlit.errors import StreamlitSecretNotFoundError

    from game import ai

    def cloud_key():
        try:
            return st.secrets.get("REQUESTY_API_KEY")
        except StreamlitSecretNotFoundError:
            return None

    suspect_ids = list(case["suspects"])
    suspect = st.selectbox(
        "Suspect", suspect_ids, format_func=lambda s: case["suspects"][s]["name"], key="suspect"
    )
    brief = engine.character_brief(game, suspect)
    uri = portrait_uri(suspect)
    if uri:
        portrait_column, persona_column = st.columns([1, 4], vertical_alignment="center")
        with portrait_column:
            st.markdown(
                f'<img class="suspect-portrait" src="{uri}" alt="{html.escape(brief["name"])}">',
                unsafe_allow_html=True,
            )
        with persona_column:
            st.markdown(f"**{plain(brief['name'])}**")
            st.caption(brief["persona"])
    else:
        st.caption(brief["persona"])

    clue_titles = {c["id"]: c["title"] for c in engine.clue_list(game)}
    chats = st.session_state.setdefault("chats", {})

    def say(entry):
        """Add a line to this suspect's conversation."""
        chats.setdefault(suspect, []).append(entry)

    def unlocked_note(ids):
        return "🔓 New clue unlocked: " + ", ".join(f"{i}. {clue_titles.get(i, '')}".rstrip(". ") for i in ids)

    # The conversation so far, as speech bubbles: the detective on the right, the suspect on the left.
    log = chats.get(suspect, [])
    with st.container(key="chat_log", height=380 if log else "content", autoscroll=True):
        if not log:
            st.caption(f"Ask {brief['name']} anything, pick a topic, or show them a clue that breaks their story.")
        for number, entry in enumerate(log):
            if entry["who"] == "you":
                with st.container(key=f"msg_you_{number}"):
                    with st.chat_message("user", avatar=st.session_state.get("player_avatar") or DEFAULT_AVATAR):
                        st.markdown(entry["text"])
                continue
            portrait = PORTRAITS / f"{suspect}.webp"
            with st.container(key=f"msg_them_{number}"):
                with st.chat_message("assistant", avatar=str(portrait) if portrait.exists() else "🗣️"):
                    st.text(entry["text"])
                    if entry.get("unlocked"):
                        st.success(unlocked_note(entry["unlocked"]))
                    latest = number == len(log) - 1
                    for item in entry.get("caught", []):
                        if not latest:  # the newest catch is shown in full just below
                            st.markdown(f"⚡ *Caught out by {plain(item['clue'] or 'a clue')}.*")

    with st.form("suspect_chat", clear_on_submit=True, border=False):
        question = st.text_input(
            "Your question",
            help=f"Up to {ai.MAX_QUESTION_LENGTH} characters.",
            placeholder="Type a question, like: where were you last night?",
        )
        send = st.form_submit_button(f"Send question ({case['clock']['question_cost']} min)", type="primary")
    if send:
        with st.spinner(f"{brief['name']} is thinking…"):
            result = run(lambda game: ai.ask(engine, game, suspect, question, cloud_key=cloud_key))
        if result:
            say({"who": "you", "text": plain(question)})
            say({"who": "them", "text": result["reply"], "unlocked": result["unlocked"]})
            st.session_state.pop("last_caught", None)
        st.rerun()

    left, right = st.columns(2)
    with left:
        topic = st.selectbox(
            "Ask about", case["topics"], format_func=lambda t: t.replace("_", " ").capitalize()
        )
        if st.button(f"Ask ({case['clock']['question_cost']} min)"):
            result = run(engine.ask, suspect, topic)
            if result:
                say({"who": "you", "text": TOPIC_QUESTIONS.get(topic, topic.replace("_", " ").capitalize())})
                say({"who": "them", "text": result["line"] or brief["cover"], "unlocked": result["unlocked"]})
                st.session_state.pop("last_caught", None)
                st.rerun()
    with right:
        opened = [c["id"] for c in engine.clue_list(game) if c["state"] == "open"]
        evidence = st.selectbox(
            "Show them a clue",
            opened or ["(no clues open yet)"],
            format_func=lambda i: f"{i}. {clue_titles[i]}" if i in clue_titles else i,
        )
        if st.button(f"Show clue ({case['clock']['question_cost']} min)", disabled=not opened):
            result = run(engine.present, suspect, evidence)
            if result:
                caught = result.get("contradictions", [])
                say({"who": "you", "text": f"*You slide **{plain(evidence)}. {plain(clue_titles[evidence])}** across the table.*"})
                say({
                    "who": "them",
                    "text": result["reveal"] or "They look at it and shrug.",
                    "unlocked": result["unlocked"],
                    "caught": caught,
                })
                st.session_state.last_caught = caught
                st.rerun()
            elif "flash" in st.session_state:
                # Show the refusal under the button, where it is seen on a phone.
                st.error(st.session_state.pop("flash")[1])

    caught_moment(st.session_state.get("last_caught", []), clue_titles)
    contradiction_board(game, clue_titles)

# ---- Accusation -------------------------------------------------------------------

with accuse_tab:
    st.write("Pick one option in each column. A wrong accusation only tells you how many are right.")
    choice = {}
    columns = st.columns(4)
    for col, column in zip(columns, ("who", "how", "where", "why")):
        with col:
            choice[column] = st.radio(
                column.capitalize(),
                [o["id"] for o in case["accusation"][column]],
                format_func=lambda o, c=column: label(c, o) + (" · ruled out" if c == "who" and ruled_out(o) else ""),
                index=None,  # start empty so a default click can't solve the case
                key=f"accuse_{column}",
            )
    strikes_left = case["max_strikes"] - game.strikes
    st.caption(f"⚖️ {strikes_left} wrong accusation{'s' if strikes_left != 1 else ''} left before the case goes cold.")
    if st.button("Make the accusation", type="primary"):
        missing = [c for c in ("who", "how", "where", "why") if choice[c] is None]
        if missing:
            # Shown right under the button, so a player at the bottom of the tab sees it.
            st.warning(f"Pick one option in each column first. Missing: {', '.join(missing)}.")
        else:
            result = run(engine.accuse, choice["who"], choice["how"], choice["where"], choice["why"])
            if result and result["status"] == "playing":
                st.session_state.flash = (
                    "warning",
                    f"{result['correct']} of 4 are right. Wrong accusations left: {result['strikes_left']}.",
                )
            st.rerun()

# ---- Start screen ---------------------------------------------------------------
# Called last, so the story and rules open over the game on a new case.

if not st.session_state.get("intro_done", bool(game.history)):
    intro_dialog()
