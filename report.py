"""The honour council report: a Markdown file the player can download when the case closes.

It sums up the player's investigation (time, the evidence they opened, the lies they caught,
their wrong guesses, badges) and ends with the case's answer and the boardroom scene.
It is built only from what the engine returns, and only once the case is closed:
`engine.solution()` raises while the game is still running, so the report can never
give away the answer during play.
"""

COLUMNS = ("who", "how", "where", "why")


def _label(case, column, option_id):
    return next(o["label"] for o in case["accusation"][column] if o["id"] == option_id)


def _plain(text):
    """Keep story text from turning into Markdown formatting in the file."""
    for char in "\\`*_#[]<>|":
        text = text.replace(char, "\\" + char)
    return text


def build(engine, game, examiner="Detective"):
    """The report as Markdown text. Raises GameError while the case is still open."""
    solution = engine.solution(game)
    case = engine.case
    title = case.get("title", "The case")
    examiner = _plain((examiner or "Detective").strip()[:24] or "Detective")
    hours, minutes = divmod(game.clock, 60)
    clues = engine.clue_list(game)
    opened = [c for c in clues if c["state"] == "open"]
    questions = sum(1 for event in game.history if event.get("action") in ("ask", "present"))
    lies = engine.contradiction_list(game)
    badges = engine.badge_list(game)

    if game.status == "solved":
        outcome = f"**Case solved** at {engine.clock_label(game)}, Friday morning."
    else:
        outcome = "**The case went cold.** No name reached the Dean before nine."

    lines = [
        f"# Honour council report: {_plain(title)}",
        "",
        f"Examiner: **{examiner}**  ",
        "Filed with the Dean, Carcavelos campus.",
        "",
        outcome,
        "",
        "## The investigation",
        "",
        f"- Time used: {hours}h {minutes:02d}m of {case['clock']['limit_minutes'] // 60} hours",
        f"- Evidence examined: {len(opened)} of {len(clues)} clues",
        f"- Questions put to suspects: {questions}",
        f"- Lies caught: {len(lies)}",
        f"- Wrong accusations: {game.strikes} of {case['max_strikes']}",
        "",
        "## Evidence examined",
        "",
    ]
    lines += [f"- {_plain(engine.label(c['id']))}" for c in opened] or ["- None."]
    lines += ["", "## Lies caught", ""]
    if lies:
        names = {s: d["name"] for s, d in case["suspects"].items()}
        for item in lies:
            source = f"evidence {engine.number(item['clue'])}" if item["clue"] else "a clue"
            lines.append(f"- **{_plain(names[item['suspect']])}** said: “{_plain(item['text'])}” Broken by {source}.")
    else:
        lines.append("- None.")
    if badges:
        lines += ["", "## Commendations", ""]
        lines += [f"- {_plain(b['title'])}: {_plain(b['description'])}" for b in badges]

    lines += ["", "## Finding of the council", ""]
    lines += [f"- **{c.capitalize()}:** {_plain(_label(case, c, solution[c]))}" for c in COLUMNS]

    scene = case["variants"][game.variant].get("denouement", "")
    if scene:
        lines += ["", "## Half past seven, the boardroom", ""]
        lines += [_plain(p) + "\n" for p in scene.format_map(game.variables).split("\n\n")]

    lines += ["", f"*{_plain(title)}. All characters, the course and the companies are fictional.*", ""]
    return "\n".join(lines)
