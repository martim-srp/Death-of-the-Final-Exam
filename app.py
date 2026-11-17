"""The Carcavelos Paper: Streamlit interface.

Run with:  streamlit run app.py

The game state lives in st.session_state on the server. The browser only ever
receives what the engine returns, so locked clues and the solution never reach it.
"""

import streamlit as st

from game.engine import Engine, Game, GameError

st.set_page_config(page_title="The Carcavelos Paper", page_icon="🕵️", layout="wide")


@st.cache_resource
def get_engine():
    return Engine()


engine = get_engine()
case = engine.case


def current_game():
    if "game" not in st.session_state:
        st.session_state.game = engine.new_game().to_dict()
    return Game.from_dict(st.session_state.game)


def save(game):
    st.session_state.game = game.to_dict()


def label(column, option_id):
    return next(o["label"] for o in case["accusation"][column] if o["id"] == option_id)


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
    st.title("🕵️ The Carcavelos Paper")
    st.metric("Time", engine.clock_label(game), help="You must accuse before 09:00.")
    st.progress(game.clock / case["clock"]["limit_minutes"])
    st.caption(
        f"Opening a clue costs {case['clock']['clue_cost']} min. "
        f"A question costs {case['clock']['question_cost']} min."
    )
    st.write(f"Wrong accusations left: **{case['max_strikes'] - game.strikes}**")
    if st.button("New case", use_container_width=True):
        st.session_state.game = engine.new_game().to_dict()
        st.rerun()

flash = st.session_state.pop("flash", None)
if flash:
    getattr(st, flash[0])(flash[1])

# ---- Intro --------------------------------------------------------------------

st.markdown(
    "It is a stormy Thursday night on the Carcavelos campus. At 23:47 an anonymous number posted "
    "`SV_Final_v3.pdf`, tomorrow's **Semiconductor Valuation** final, to all 212 students in the "
    "cohort group chat. The Dean has made you examiner for the honour council: "
    "*\"I do not want a scandal. I want a name, and I want it before nine.\"*"
)
st.caption(game.variables["weather"])

# ---- Case closed ----------------------------------------------------------------

if game.status != "playing":
    solution = engine.solution(game)
    if game.status == "solved":
        st.success(f"Case solved at {engine.clock_label(game)}.")
    else:
        st.error("The case has gone cold.")
    st.subheader("What really happened")
    st.write(
        f"**{label('who', solution['who'])}**: {label('how', solution['how']).lower()}, "
        f"at {label('where', solution['where']).lower()}, {label('why', solution['why']).lower()}."
    )
    st.stop()

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
                    st.code(clue["log"], language=None)
                if clue["hidden_text"] and st.toggle("Show hidden text", key=f"hidden_{item['id']}"):
                    st.warning(clue["hidden_text"])

# ---- Questioning --------------------------------------------------------------

with question_tab:
    suspect_ids = list(case["suspects"])
    suspect = st.selectbox(
        "Suspect", suspect_ids, format_func=lambda s: case["suspects"][s]["name"]
    )
    brief = engine.character_brief(game, suspect)
    st.caption(brief["persona"])

    left, right = st.columns(2)
    with left:
        topic = st.selectbox("Ask about", case["topics"], format_func=lambda t: t.replace("_", " "))
        if st.button(f"Ask ({case['clock']['question_cost']} min)"):
            result = run(engine.ask, suspect, topic)
            if result:
                st.session_state.last_answer = result["line"] or brief["cover"]
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
                if result["unlocked"]:
                    st.session_state.last_answer += f"\n\n🔓 New clue unlocked: {', '.join(result['unlocked'])}"
                st.rerun()

    if "last_answer" in st.session_state:
        st.info(st.session_state.last_answer)

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
                key=f"accuse_{column}",
            )
    if st.button("Make the accusation", type="primary"):
        result = run(engine.accuse, choice["who"], choice["how"], choice["where"], choice["why"])
        if result and result["status"] == "playing":
            st.session_state.flash = (
                "warning",
                f"{result['correct']} of 4 are right. Wrong accusations left: {result['strikes_left']}.",
            )
        st.rerun()
