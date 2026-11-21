"""The honour council report: a Markdown file the player can download when the case closes.

It sums up the player's investigation and outcome. A cold case stays unsolved in
the story, with the correct answer shown separately for the player after it ends.
"""

from game.engine import GameError

COLUMNS = ("who", "how", "where", "why")


def closing_scene(engine, game):
    """The same outcome on screen and in the report, only after the case closes."""
    if game.status == "playing":
        raise GameError("The ending is only shown when the case is closed.")
    if game.status == "cold":
        return engine.case["cold_ending"]
    return engine.case["variants"][game.variant].get("denouement", "").format_map(game.variables)


def _label(case, column, option_id):
    return next(o["label"] for o in case["accusation"][column] if o["id"] == option_id)


def _plain(text):
    """Keep story text from turning into Markdown formatting in the file."""
    for char in "\\`*_#[]<>|":
        text = text.replace(char, "\\" + char)
    return text


def build(engine, game, examiner="Detective"):
    """The report as Markdown text. Raises GameError while the case is still open."""
    scene = closing_scene(engine, game)
    solution = engine.solution(game)
    solved = game.status == "solved"
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
        outcome = "**The case went cold.** The culprit remains unidentified. The Dean cancels the exam."

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
    if solved:
        lines += [f"- **{c.capitalize()}:** {_plain(_label(case, c, solution[c]))}" for c in COLUMNS]
    else:
        lines += ["The case remains unsolved. No culprit has been identified."]

    if scene:
        heading = "The boardroom confrontation" if solved else "The case remains unsolved"
        lines += ["", f"## {heading}", ""]
        lines += [_plain(p) + "\n" for p in scene.split("\n\n")]

    if not solved:
        lines += ["", "## The correct solution (for the player)", "",
                  "The investigation itself remained unsolved. This is the correct answer for your case.", ""]
        lines += [f"- **{c.capitalize()}:** {_plain(_label(case, c, solution[c]))}" for c in COLUMNS]

    lines += ["", f"*{_plain(title)}. All characters, the course and the companies are fictional.*", ""]
    return "\n".join(lines)
