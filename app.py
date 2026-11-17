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
from game.case import load_case
from game.engine import Engine, Game, GameError

COVER = Path(__file__).resolve().parent / "assets" / "cover.webp"
PORTRAITS = Path(__file__).resolve().parent / "assets" / "suspects"  # one <suspect id>.svg each
TITLE = load_case()["title"]  # the game's name lives in data/case.json

st.set_page_config(page_title=TITLE, page_icon="🕵️", layout="wide")


@st.cache_resource
def get_engine():
    return Engine()


engine = get_engine()
case = engine.case


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
.suspect-row { display: flex; gap: 0.75rem; overflow-x: auto; padding: 0.25rem 0 0.5rem; }
.suspect-card { flex: 1 0 104px; max-width: 160px; text-align: center; position: relative; }
.suspect-card img { width: 100%; display: block; border-radius: 10px; }
.suspect-card.ruled-out img { filter: grayscale(1) brightness(0.55); }
.suspect-card .name { font-family: Georgia, serif; font-size: 0.85rem; margin-top: 0.3rem; line-height: 1.2; }
.suspect-card .status { font-size: 0.75rem; opacity: 0.75; }
.suspect-card .caught { color: #e0645a; font-weight: 600; }
.suspect-card .stamp { position: absolute; top: 38%; left: 50%; transform: translate(-50%, -50%) rotate(-14deg);
  border: 2px solid #c0392b; color: #c0392b; background: rgba(20, 16, 14, 0.75); padding: 0 0.35rem;
  font: 700 0.8rem "Courier New", monospace; letter-spacing: 0.08em; white-space: nowrap; }
@media (max-width: 640px) {
  .suspect-card { flex-basis: 70px; }
  .suspect-card .name { font-size: 0.75rem; }
  .suspect-card .status { font-size: 0.65rem; }
}
.suspect-portrait { width: 140px; max-width: 40vw; border-radius: 10px; }
</style>
"""


@st.cache_data
def portrait_uri(suspect):
    """The suspect's portrait as a data URI, or None if there is no drawing for them."""
    path = PORTRAITS / f"{suspect}.svg"
    if not path.exists():
        return None
    return "data:image/svg+xml;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def suspect_status(game):
    """For each suspect: whether you have questioned them, and how many contradictions you caught."""
    questioned = {event["suspect"] for event in game.history if "suspect" in event}
    caught = {}
    for suspect, _claim in game.contradictions:
        caught[suspect] = caught.get(suspect, 0) + 1
    return {s: {"questioned": s in questioned, "caught": caught.get(s, 0)} for s in case["suspects"]}


def ruled_out(suspect):
    """Whether the player has ticked this suspect off in their notebook."""
    return bool(st.session_state.get(f"note_suspect_{suspect}"))


def suspect_cards(game):
    """A row of portrait cards: who you have questioned, who you caught out, who you ruled out."""
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
        cards.append(
            f'<div class="suspect-card{" ruled-out" if out else ""}">{picture}{stamp}'
            f'<div class="name">{name}</div><div class="status">{line}</div></div>'
        )
    st.markdown(NOIR_CSS + '<div class="suspect-row">' + "".join(cards) + "</div>", unsafe_allow_html=True)


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
    for key in [k for k in st.session_state if str(k).startswith("note_")]:
        del st.session_state[key]


def run(action, *args):
    """Run an engine action, save the game, and turn rule errors into messages."""
    game = current_game()
    try:
        result = action(game, *args)
    except GameError as error:
        st.session_state.flash = ("error", str(error))
        return None
    save(game)
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

# ---- Intro --------------------------------------------------------------------

cover_column, intro_column = st.columns([1, 2], vertical_alignment="center", gap="large")
with cover_column:
    if COVER.exists():
        st.image(str(COVER), width=320)
with intro_column:
    st.title(TITLE)
    st.markdown(
        "It is a stormy Thursday night on the Carcavelos campus. At 23:47 an anonymous number posted "
        "`SV_Final_v3.pdf`, tomorrow's **Semiconductor Valuation** final, to all 212 students in the "
        "cohort group chat. The Dean has made you examiner for the honour council: "
        "*\"I do not want a scandal. I want a name, and I want it before nine.\"*"
    )
    st.caption(game.variables["weather"])
st.divider()

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

suspect_cards(game)

case_tab, question_tab, accuse_tab = st.tabs(["📁 Case file", "🗣️ Question suspects", "⚖️ Accuse"])

# ---- Case file ------------------------------------------------------------------

with case_tab:
    for item in engine.clue_list(game):
        icon = "📄" if item["kind"] == "document" else "📍"
        title = f"{icon} {item['id']}. {item['title']}"
        if item["state"] == "locked":
            st.markdown(f"🔒 ~~{item['id']}. {item['title']}~~ (locked)")
        elif item["state"] == "available":
            if st.button(f"Open {title} ({case['clock']['clue_cost']} min)", key=f"open_{item['id']}"):
                run(engine.open_clue, item["id"])
                st.rerun()
        else:
            clue = engine.read_clue(game, item["id"])
            with st.expander(title):
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
        "Suspect", suspect_ids, format_func=lambda s: case["suspects"][s]["name"]
    )
    brief = engine.character_brief(game, suspect)
    uri = portrait_uri(suspect)
    if uri:
        portrait_column, persona_column = st.columns([1, 3], vertical_alignment="center")
        with portrait_column:
            st.markdown(
                f'<img class="suspect-portrait" src="{uri}" alt="{html.escape(brief["name"])}">',
                unsafe_allow_html=True,
            )
        with persona_column:
            st.caption(brief["persona"])
    else:
        st.caption(brief["persona"])

    with st.form("suspect_chat", clear_on_submit=True):
        question = st.text_input("Your question", help=f"Up to {ai.MAX_QUESTION_LENGTH} characters.")
        send = st.form_submit_button(f"Send question ({case['clock']['question_cost']} min)")
    if send:
        result = run(lambda game: ai.ask(engine, game, suspect, question, cloud_key=cloud_key))
        if result:
            st.session_state.last_answer = result
            st.session_state.pop("last_caught", None)
        st.rerun()

    left, right = st.columns(2)
    with left:
        topic = st.selectbox("Ask about", case["topics"], format_func=lambda t: t.replace("_", " "))
        if st.button(f"Ask ({case['clock']['question_cost']} min)"):
            result = run(engine.ask, suspect, topic)
            if result:
                st.session_state.last_answer = result["line"] or brief["cover"]
                st.session_state.pop("last_caught", None)
                if result["unlocked"]:
                    st.session_state.last_answer += f"\n\n🔓 New clue unlocked: {', '.join(result['unlocked'])}"
                st.rerun()
    with right:
        opened = [c["id"] for c in engine.clue_list(game) if c["state"] == "open"]
        evidence = st.selectbox("Show them a clue", opened or ["(no clues open yet)"])
        if st.button(f"Show clue ({case['clock']['question_cost']} min)", disabled=not opened):
            result = run(engine.present, suspect, evidence)
            if result:
                st.session_state.last_answer = result["reveal"] or "They look at it and shrug."
                st.session_state.last_caught = result.get("contradictions", [])
                if result["unlocked"]:
                    st.session_state.last_answer += f"\n\n🔓 New clue unlocked: {', '.join(result['unlocked'])}"
                st.rerun()
            elif "flash" in st.session_state:
                # Show the refusal under the button, where it is seen on a phone.
                st.error(st.session_state.pop("flash")[1])

    if "last_answer" in st.session_state:
        answer = st.session_state.last_answer
        if isinstance(answer, dict):
            st.text(answer["reply"])
            if answer["unlocked"]:
                st.success(f"🔓 New clue unlocked: {', '.join(answer['unlocked'])}")
        else:
            st.info(answer)
    clue_titles = {c["id"]: c["title"] for c in engine.clue_list(game)}
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
                format_func=lambda o, c=column: label(c, o),
                index=None,  # start empty so a default click can't solve the case
                key=f"accuse_{column}",
            )
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
