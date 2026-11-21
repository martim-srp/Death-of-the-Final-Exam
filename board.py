"""The game board's HTML: the status bar, the campus map, the evidence cards and the suspects.

These functions only build markup from what the engine has already returned (clue_list,
read_clue and so on), so nothing locked ever reaches the browser: a locked or unopened
clue is drawn face down, with no picture and no text. All story text is escaped.

app.py shows the markup with one small component (BOARD_JS) that sends a tap back to
Python as an "act" string, such as "suspect:ta", "clue:D2", "place:L4" or "accuse".
"""

import base64
import html
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
MIME = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}

# Map pins: (x, y) as fractions of the picture, on the round head of each pin drawn on it.
MAP_PINS = {
    "L1": (0.365, 0.440, "Library"),
    "L3": (0.317, 0.731, "Residence"),
    "L4": (0.537, 0.550, "Faculty"),
    "L5": (0.672, 0.115, "Beach café"),
}
# A place drawn on the map with nothing to search. Neutral, because it is also an answer under "Where".
MAP_SPOTS = {"chiado": (0.088, 0.663, "Chiado", "Off campus, across Lisbon. Nothing to search here tonight.")}
# Where the detective's token stands before searching anywhere: the campus gate on the left.
GATE = (0.20, 0.60)

# Line icons drawn on a 24-pixel grid, stroked in the current text colour. Used instead of emoji.
ICONS = {
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.3-4.3"/>',
    "sheet": '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 2.5h6v3H9zM9 11h6M9 15h4"/>',
    "book": '<path d="M3 5h6a3 3 0 0 1 3 3v12a2 2 0 0 0-2-2H3zM21 5h-6a3 3 0 0 0-3 3v12a2 2 0 0 1 2-2h7z"/>',
    "sound": '<path d="M4 9.5h3.5L12 6v12l-4.5-3.5H4z"/><path d="M15.5 9.5a3.5 3.5 0 0 1 0 5M18.5 7a7 7 0 0 1 0 10"/>',
    "mute": '<path d="M4 9.5h3.5L12 6v12l-4.5-3.5H4z"/><path d="M16 9.5l5 5M21 9.5l-5 5"/>',
    "scale": '<path d="M12 4v16M8 20h8M5 7h14M12 4v3"/><path d="M5 7l-2.5 6a2.5 2.5 0 0 0 5 0zM19 7l-2.5 6a2.5 2.5 0 0 0 5 0z"/>',
    "bolt": '<path d="M13 2.5L5 13.5h6l-1 8 8-11h-6z"/>',
    "lock": '<rect x="5" y="11" width="14" height="9.5" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "unlock": '<rect x="5" y="11" width="14" height="9.5" rx="2"/><path d="M8 11V8a4 4 0 0 1 7.6-1.7"/>',
    "ask": '<path d="M4 5h16v11H10l-5 4v-4H4z"/><path d="M8 9.5h8M8 12.5h5"/>',
    "card": '<rect x="6" y="3" width="12" height="18" rx="2"/><path d="M9 7.5h6M9 11h6M9 14.5h3"/>',
    "doc": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>',
    "pin": '<path d="M12 21s-6.5-6-6.5-11.5a6.5 6.5 0 0 1 13 0C18.5 15 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.3"/>',
    "chart": '<path d="M4 4v16h16M8.5 16v-4M12.5 16V8M16.5 16v-6"/>',
    "cup": '<path d="M4 9h12v4.5A5.5 5.5 0 0 1 10.5 19h-1A5.5 5.5 0 0 1 4 13.5z"/><path d="M16 10.5h1.5a2.5 2.5 0 0 1 0 5H16M8 3.5v2.5M12 3.5v2.5"/>',
    "door": '<path d="M6 21V3.5h12V21M3 21h18"/><path d="M14.5 12h.01"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "medal": '<circle cx="12" cy="15" r="5"/><path d="M8.5 3.5l3.5 6.5 3.5-6.5"/>',
    "map": '<path d="M3 6.5l6-3 6 3 6-3v14l-6 3-6-3-6 3z"/><path d="M9 3.5v14M15 6.5v14"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "calm": '<path d="M19.5 14.5A8 8 0 1 1 9.5 4.5a6.5 6.5 0 0 0 10 10z"/>',
}


def icon(name, cls="ic"):
    """One line icon as inline SVG. Unknown names draw nothing."""
    body = ICONS.get(name)
    if not body:
        return ""
    return (
        f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    )


KIND_ICON = {"document": "doc", "location": "pin"}
# Short names for the cards, so each fits on one line. The full title is in the panel.
CARD_NAMES = {
    "D1": "Leaked PDF", "D2": "Print log", "D3": "Sealed exam", "D4": "Standings", "D5": "Anon number",
    "D6": "Email trail", "D7": "Visitors' book", "D8": "Clipping", "L1": "Gate log", "L2": "Cafeteria",
    "L3": "Residence", "L4": "Faculty", "L5": "Beach café",
}
# A few clues have no picture. Their card shows a big icon instead.
CARD_ICON = {"D4": "chart", "L2": "cup", "L4": "door"}


@lru_cache(maxsize=64)
def data_uri(path):
    """A picture file as a data URI, or None if it does not exist."""
    path = Path(path)
    if not path.is_file():
        return None
    mime = MIME.get(path.suffix.lower(), "application/octet-stream")
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def find_picture(folder, name):
    """The first <name>.<webp|png|jpg|jpeg|svg> in an assets folder, as a data URI."""
    for extension in MIME:
        uri = data_uri(str(ASSETS / folder / f"{name}{extension}"))
        if uri:
            return uri
    return None


def esc(text):
    return html.escape(str(text), quote=True)


def short_name(name):
    return name.removeprefix("The ")


def parse_act(act, suspects, clues):
    """Turn a tap from the board into (panel, id), or None if it names nothing real.

    The browser sends plain strings, so every id is checked against the case file.
    """
    kind, _, value = str(act or "").partition(":")
    if kind == "next" and not value.startswith("next"):
        return parse_act(value, suspects, clues)  # the next-step strip: same targets, own name
    if kind == "suspect" and value in suspects:
        return ("suspect", value)
    if kind in ("clue", "place") and value in clues:
        return ("clue", value)
    if kind == "spot" and value in MAP_SPOTS:
        return ("spot", value)
    if kind in ("home", "sheet", "accuse", "intro", "tour_done", "calm") and not value:
        return (kind, None)
    return None


# ---- Status bar --------------------------------------------------------------------


def hud_html(clock, minutes_left, limit, strikes_left, max_strikes, caught, avatar_uri, name, calm=False):
    """Time, the fuse burning down to 09:00, accusations left as pips, lies caught, and the buttons.

    calm: whether calm mode is on (no animations, no sounds), shown on its button."""
    hours, minutes = divmod(max(minutes_left, 0), 60)
    burnt = 100 * (1 - max(minutes_left, 0) / limit)
    urgent = " urgent" if minutes_left <= 120 else ""
    pips = "".join(f'<i class="pip{" on" if n < strikes_left else ""}"></i>' for n in range(max_strikes))
    face = f'<img src="{avatar_uri}" alt="">' if avatar_uri else f'<span class="noface">{icon("user")}</span>'
    return (
        f'<div class="hud{urgent}">'
        f'<div class="me" title="{esc(name)}">{face}</div>'
        f'<div class="clock"><b>{esc(clock)}</b><div class="fuse"><i style="width:{burnt:.1f}%"></i></div>'
        f'<small>{hours}h {minutes:02d}m left</small></div>'
        f'<div class="stat" title="Accusations left">{icon("scale")}<span class="pips">{pips}</span><small>tries left</small></div>'
        f'<div class="stat zapstat" title="Lies caught">{icon("bolt")}<b>{caught}</b><small>{"lie" if caught == 1 else "lies"} caught</small></div>'
        '<div class="tools">'
        f'<button data-act="home" title="Leads">{icon("search")}</button>'
        f'<button data-act="sheet" title="Notebook">{icon("sheet")}</button>'
        f'<button data-act="intro" title="Story and rules">{icon("book")}</button>'
        f'<button class="mute" type="button" title="Sound on or off">{icon("sound", "ic on")}{icon("mute", "ic off")}</button>'
        f'<button class="calmbtn{" on" if calm else ""}" data-act="calm" aria-pressed="{"true" if calm else "false"}" '
        f'title="Calm mode: no animations, no sounds{" (on)" if calm else ""}">{icon("calm")}</button>'
        '<button class="accuse" data-act="accuse">Accuse</button></div></div>'
    )


def sfx_html(sound, nonce):
    """An invisible marker that asks the board to play one short sound: flip, tick, stamp or thud."""
    if sound not in ("flip", "tick", "stamp", "thud"):
        return ""
    return f'<i class="sfx" hidden data-sfx="{sound}" data-n="{int(nonce)}"></i>'


def calm_html(on):
    """An invisible marker that switches the board to calm mode: nothing moves, nothing plays.

    For players who find motion, blinking and sound distracting."""
    return '<i class="calm-on" hidden></i>' if on else ""


def tutorial_html():
    """The first-play tour: four short steps, each pointing at one part of the screen."""
    steps = [
        ("map", "The board", "To search a new area, click on the red circle."),
        ("hand", "Your evidence", "Tap an evidence card to open it. Red ones are new."),
        ("suspects", "The suspects", "Tap a face to question them, or show them an evidence card."),
        ("accuse", "Accuse", "Name who, how, where and why before 09:00."),
    ]
    items = "".join(
        f'<div class="step" data-target="{t}" data-i="{i}"><b>{esc(h)}</b><p>{esc(x)}</p></div>' for i, (t, h, x) in enumerate(steps)
    )
    return f'<div class="tour" hidden>{items}<div class="tour-nav"><button class="skip" type="button">Skip</button><span class="dots"></span><button class="next" type="button">Next</button></div></div>'


# ---- Next step ---------------------------------------------------------------------

GOAL_ICON = {"search": "search", "ask": "ask", "show": "card", "sheet": "sheet", "accuse": "scale"}


def goal_act(step):
    """What tapping the next step opens: the clue, the suspect, the case sheet or the accusation."""
    if step["do"] == "search":
        return f"clue:{step['clue']}"
    if step["do"] in ("ask", "show"):
        return f"suspect:{step['suspect']}"
    return step["do"]


def goal_target(step):
    """The id to light up on the board for the next step: a clue, a suspect, or None."""
    if not step:
        return None
    return step.get("clue") if step["do"] == "search" else step.get("suspect")


def goal_html(step, thought=None):
    """The always-visible objective strip: one next step, tap it to go there.

    With a thought, the detective's line leads and the plain step sits above it as the label.
    """
    if not step:
        return ""
    if thought and thought != step["text"]:
        text = f'<small class="plain">{esc(step["text"])}</small><em>{esc(thought)}</em>'
    else:
        text = f'<small>Next step</small>{esc(step["text"])}'
    return (
        f'<button class="goal-bar" data-act="next:{goal_act(step)}"><span class="gi">{icon(GOAL_ICON[step["do"]])}</span>'
        f'<span class="gt">{text}</span><span class="go">›</span></button>'
    )


# ---- The campus map ----------------------------------------------------------------

NIGHT_DEFS = (
    '<defs><radialGradient id="night" cx="50%" cy="50%" r="75%">'
    '<stop offset="55%" stop-color="#0b1020" stop-opacity="0"/><stop offset="100%" stop-color="#05070f" stop-opacity=".55"/>'
    '</radialGradient><radialGradient id="fog"><stop offset="0%" stop-color="#b9c2d6" stop-opacity=".42"/>'
    '<stop offset="55%" stop-color="#b9c2d6" stop-opacity=".22"/><stop offset="100%" stop-color="#b9c2d6" stop-opacity="0"/>'
    "</radialGradient></defs>"
)



def map_points(clues):
    """One pin per location clue drawn on the map, with its state from clue_list()."""
    points = []
    for item in clues:
        if item["id"] in MAP_PINS:
            x, y, place = MAP_PINS[item["id"]]
            points.append({"id": item["id"], "x": x, "y": y, "place": place, "title": item["title"], "state": item["state"]})
    return points


def detective_spot(opened):
    """Where the detective token stands: the last place searched, or the gate."""
    for clue_id in reversed(opened):
        if clue_id in MAP_PINS:
            return MAP_PINS[clue_id][:2]
    return GATE


PIN_LABEL = {"locked": "locked", "available": "search here", "open": "searched"}


def map_html(map_uri, size, points, opened, picked=None, avatar_uri=None, fresh=(), goal=None):
    """The campus picture as the board: pins for places, the detective's token, Chiado.

    Locked places sit under fog that lifts when they open up. The goal pin (the next step) glows gold.
    """
    width, height = size
    s = width / 1200  # every size below is for a 1200-pixel-wide picture
    parts = [
        f'<svg class="map" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Campus map"><image href="{map_uri}" width="{width}" height="{height}"/>'
        + NIGHT_DEFS
        + f'<rect class="night" width="{width}" height="{height}" fill="url(#night)"/>'
        + f'<g class="mist"><ellipse cx="{width * 0.3:.0f}" cy="{height * 0.35:.0f}" rx="{width * 0.35:.0f}" ry="{height * 0.12:.0f}"/>'
        f'<ellipse cx="{width * 0.75:.0f}" cy="{height * 0.75:.0f}" rx="{width * 0.3:.0f}" ry="{height * 0.1:.0f}"/></g>'
    ]
    for p in points:
        x, y = p["x"] * width, p["y"] * height
        state = p["state"]
        classes = (f"pin {state}" + (" picked" if p["id"] == picked else "") + (" fresh" if p["id"] in fresh else "")
                   + (" goal" if p["id"] == goal else ""))
        label = esc(f"{p['place']}: {PIN_LABEL[state]}")
        thumb = find_picture("clues", p["id"]) if state == "open" else None
        if thumb:
            face = (
                f'<clipPath id="clip{p["id"]}"><circle r="34"/></clipPath>'
                f'<image href="{thumb}" x="-46" y="-34" width="92" height="69" clip-path="url(#clip{p["id"]})" '
                'preserveAspectRatio="xMidYMid slice"/>'
            )
        elif state == "open":
            face = '<circle r="34" fill="#efe6d8"/><text class="glyph" y="10" fill="#14100e">✓</text>'
        elif state == "available":
            face = '<circle r="34" fill="#c0392b"/><text class="glyph" y="11" fill="#fff">?</text>'
        else:
            face = '<circle r="34" fill="#2a221e"/><svg x="-15" y="-16" width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#cdbfa8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + ICONS["lock"] + "</svg>"
        parts.append(
            f'<g class="{classes}" data-act="place:{p["id"]}" transform="translate({x:.0f} {y:.0f}) scale({s:.3f})" '
            f'role="button" tabindex="0" aria-label="{label}"><title>{label}</title>'
            + (f'<circle class="fog" r="120" fill="url(#fog)"/>' if state == "locked" else "")
            + (f'<circle class="lift" r="120" fill="url(#fog)"/>' if p["id"] in fresh and state != "locked" else "")
            + '<circle class="halo" r="46"/><circle class="beacon" r="52"/>'
            f'{face}<circle class="ring" r="34"/>'
            f'<text class="tag" y="62">{esc(p["place"])}</text>'
            f'<circle r="60" fill="#000" fill-opacity="0"/></g>'
        )
    for spot, (sx, sy, place, _note) in MAP_SPOTS.items():
        parts.append(
            f'<g class="pin spot" data-act="spot:{spot}" transform="translate({sx * width:.0f} {sy * height:.0f}) scale({s:.3f})" '
            f'role="button" tabindex="0" aria-label="{esc(place)}: nothing to search"><title>{esc(place)}</title>'
            '<circle class="ring" r="30"/>'
            f'<text class="tag" y="58">{esc(place)}</text><circle r="56" fill="#000" fill-opacity="0"/></g>'
        )
    dx, dy = detective_spot(opened)
    tx, ty = dx * width + 64 * s, dy * height - 52 * s  # beside the pin, never on it
    token = f'<image href="{avatar_uri}" x="-26" y="-26" width="52" height="65" clip-path="url(#detclip)" preserveAspectRatio="xMidYMin slice"/>' if avatar_uri else '<circle r="20" fill="#2a221e"/>'
    parts.append(
        f'<g class="det" data-x="{tx:.0f}" data-y="{ty:.0f}" transform="translate({tx:.0f} {ty:.0f}) scale({s:.3f})">'
        '<clipPath id="detclip"><circle r="26"/></clipPath><circle r="30" fill="#14100e"/>'
        f'{token}<circle r="28" fill="none" stroke="#e8c27a" stroke-width="4"/></g>'
    )
    parts.append("</svg>")
    return "".join(parts)


# ---- Evidence cards ----------------------------------------------------------------


def card_html(item, picked=None, fresh=(), goal=None):
    """One evidence card. Face up with its picture once opened; face down otherwise."""
    state = item["state"]
    is_fresh = item["id"] in fresh
    classes = f"card {state}" + (" picked" if item["id"] == picked else "") + (" goal" if item["id"] == goal else "")
    if is_fresh:
        classes += " flip" if state == "open" else " fresh"
    name = esc(CARD_NAMES.get(item["id"], item["title"]))
    if state == "open":
        uri = find_picture("clues", item["id"])
        art = (
            f'<div class="art" style="background-image:url({uri})"></div>' if uri
            else f'<div class="art icon">{icon(CARD_ICON.get(item["id"], KIND_ICON[item["kind"]]))}</div>'
        )
    elif state == "available":
        art = '<div class="art back"><span>?</span><em class="new">NEW</em></div>'
    else:
        art = f'<div class="art back locked"><span>{icon("lock")}</span></div>'
    return (
        f'<button class="{classes}" data-act="clue:{item["id"]}" title="Evidence {item["number"]}. {esc(item["title"])}">'
        f'{art}<div class="lbl"><b>{item["number"]}</b><span>{name}</span></div></button>'
    )


def hand_columns(count):
    """Columns for the evidence hand on a wide board: two rows, so each card is wide enough
    for its name to break between words. A narrow board (a phone) uses five columns instead."""
    return max(1, (count + 1) // 2)


def hand_html(clues, picked=None, fresh=(), goal=None):
    """All the evidence cards, numbered 1 to 13. Places also have a pin on the map; both open the same card."""
    opened = sum(c["state"] == "open" for c in clues)
    return (
        f'<div class="handhead"><b>Evidence</b><span>{opened} of {len(clues)} found</span></div>'
        f'<div class="hand" lang="en" style="--n:{hand_columns(len(clues))}">' + "".join(card_html(c, picked, fresh, goal) for c in clues) + "</div>"
    )


# ---- Suspects ----------------------------------------------------------------------


# Names that fit under a small portrait when the suspect row is narrow.
TINY_NAME = {"class_rep": "Class Rep", "ta": "TA", "exchange": "Exchange", "professor": "Professor", "companion": "Companion"}


def suspects_html(suspects, picked=None, goal=None):
    """The five suspects as big cards. Each item: id, name, questioned, caught, ruled_out,
    and optionally nerves (0 to 100), drawn as a thin bar along the bottom of the card."""
    cards = []
    for s in suspects:
        uri = find_picture("suspects", s["id"])
        name = (f'<span class="long">{esc(short_name(s["name"]))}</span>'
                f'<span class="short">{esc(TINY_NAME.get(s["id"], short_name(s["name"])))}</span>')
        classes = "sus" + (" picked" if s["id"] == picked else "") + (" out" if s["ruled_out"] else "") + (" goal" if s["id"] == goal else "")
        marks = ""
        if s["questioned"]:
            marks += '<span class="tick" title="Questioned">✓</span>'
        if s["caught"]:
            marks += f'<span class="zap" title="Caught lying">{icon("bolt")}{s["caught"]}</span>'
        stamp = '<span class="stamp">RULED OUT</span>' if s["ruled_out"] else ""
        picture = f'<img src="{uri}" alt="{esc(s["name"])}">' if uri else f'<div class="noimg">{icon("user")}</div>'
        nerves = s.get("nerves")
        bar = ""
        if nerves is not None:
            level = max(0, min(100, int(nerves)))
            full = " full" if level >= 100 else ""
            bar = f'<i class="nv{full}" title="Nerves {level}%"><b style="width:{level}%"></b></i>'
        cards.append(
            f'<button class="{classes}" data-act="suspect:{s["id"]}" aria-label="Question {esc(s["name"])}">'
            f'{picture}<div class="marks">{marks}</div>{stamp}<div class="nm">{name}</div>{bar}</button>'
        )
    return '<div class="suspects">' + "".join(cards) + "</div>"


# ---- The component: draws the markup and sends taps back to Python ------------------

BOARD_JS = r"""
const SOUNDS = {
    flip: [[0, 0.07, 1800, 600, "triangle", 0.10], [0.05, 0.06, 900, 300, "triangle", 0.06]],
    tick: [[0, 0.03, 2400, 2400, "square", 0.04], [0.16, 0.03, 1900, 1900, "square", 0.03]],
    stamp: [[0, 0.18, 140, 45, "sine", 0.5], [0, 0.05, 600, 120, "square", 0.12]],
    thud: [[0, 0.30, 110, 40, "sine", 0.55], [0.12, 0.25, 90, 35, "sine", 0.35]],
};
function muted() { try { return localStorage.getItem("dfe-muted") === "1"; } catch (e) { return false; } }
function audio() {
    if (!window.__dfeAudio) {
        const Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) return null;
        window.__dfeAudio = new Ctx();
    }
    return window.__dfeAudio;
}
function play(name) {
    if (muted() || !SOUNDS[name]) return;
    const ctx = audio();
    if (!ctx || ctx.state !== "running") return;
    const now = ctx.currentTime;
    for (const [at, len, f0, f1, wave, vol] of SOUNDS[name]) {
        const osc = ctx.createOscillator(), gain = ctx.createGain();
        osc.type = wave;
        osc.frequency.setValueAtTime(f0, now + at);
        osc.frequency.exponentialRampToValueAtTime(Math.max(f1, 20), now + at + len);
        gain.gain.setValueAtTime(vol, now + at);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + at + len);
        osc.connect(gain).connect(ctx.destination);
        osc.start(now + at);
        osc.stop(now + at + len + 0.02);
    }
}
if (!window.__dfeUnlock) {
    // Browsers only allow sound after the player has tapped something.
    window.__dfeUnlock = true;
    document.addEventListener("pointerdown", () => { const ctx = audio(); if (ctx && ctx.state !== "running") ctx.resume(); }, true);
}

function tour(root, setTriggerValue) {
    const box = root.querySelector(".tour");
    if (!box) return;
    const steps = [...box.querySelectorAll(".step")];
    const dots = box.querySelector(".dots");
    let i = 0;
    const ring = document.createElement("div");
    ring.className = "tour-ring";
    root.appendChild(ring);
    const target = (name) => {
        if (name === "suspects") {
            const row = document.querySelector(".st-key-suspect_row");
            if (row && row.offsetParent) return row;
            return root.querySelector(".phone-only .suspects");
        }
        return root.querySelector({ map: ".map", hand: ".hand", accuse: ".accuse" }[name]);
    };
    const show = () => {
        steps.forEach((s, n) => s.classList.toggle("on", n === i));
        dots.textContent = steps.map((_, n) => (n === i ? "●" : "○")).join(" ");
        box.querySelector(".next").textContent = i === steps.length - 1 ? "Play" : "Next";
        const el = target(steps[i].dataset.target);
        if (el) {
            el.scrollIntoView({ block: "center", behavior: root.classList.contains("calm") ? "auto" : "smooth" });
            setTimeout(() => {
                const r = el.getBoundingClientRect();
                Object.assign(ring.style, { left: r.left - 6 + "px", top: r.top - 6 + "px", width: r.width + 12 + "px", height: r.height + 12 + "px" });
            }, 350);
        }
    };
    const done = () => { box.hidden = true; ring.remove(); setTriggerValue("act", "tour_done"); };
    box.querySelector(".next").addEventListener("click", () => { if (i < steps.length - 1) { i += 1; show(); } else done(); });
    box.querySelector(".skip").addEventListener("click", done);
    box.hidden = false;
    show();
}

// What a tap opens shows in the panel. When the columns stack (phones, narrow windows) the
// panel sits below the map and the cards, so bring it into view once the redraw has filled it.
// Where the panel is already on screen, nothing moves.
function revealPanel() {
    const before = (document.querySelector(".st-key-panel") || {}).textContent;
    const started = Date.now();
    const check = () => {
        const panel = document.querySelector(".st-key-panel");
        const changed = panel && panel.textContent !== before;
        if (!changed && Date.now() - started < 5000) { setTimeout(check, 150); return; }
        if (!panel) return;
        const r = panel.getBoundingClientRect();
        if (r.top > window.innerHeight * 0.6 || r.bottom < 80) panel.scrollIntoView({ behavior: "smooth", block: "start" });
    };
    setTimeout(check, 150);
}

export default function(component) {
    const { data, setTriggerValue, parentElement } = component;
    let root = parentElement.querySelector(".deck");
    if (!root) {
        root = document.createElement("div");
        root.className = "deck";
        parentElement.appendChild(root);
    }
    const before = root.querySelector(".det");
    const from = before ? before.getAttribute("transform") : null;
    root.innerHTML = data;
    const calm = !!root.querySelector(".calm-on");
    root.classList.toggle("calm", calm);
    const det = root.querySelector(".det");
    const to = det ? det.getAttribute("transform") : null;
    if (det && from && to && from !== to && !calm) {
        const css = (t) => t.replace(/translate\(([-\d.]+) ([-\d.]+)\)/, "translate($1px, $2px)");
        try { det.animate([{ transform: css(from) }, { transform: css(to) }], { duration: 800, easing: "ease-in-out" }); } catch (e) {}
    }
    const sfx = root.querySelector(".sfx");
    if (sfx && window.__dfeLastSfx !== sfx.dataset.n) {
        window.__dfeLastSfx = sfx.dataset.n;
        if (!calm) play(sfx.dataset.sfx);
    }
    const mute = root.querySelector(".mute");
    if (mute) {
        const label = () => { mute.classList.toggle("muted", muted()); };
        label();
        mute.addEventListener("click", () => {
            try { localStorage.setItem("dfe-muted", muted() ? "0" : "1"); } catch (e) {}
            label();
            if (!calm) play("tick");
        });
    }
    root.querySelectorAll("[data-act]").forEach((el) => {
        const go = () => {
            setTriggerValue("act", el.getAttribute("data-act"));
            revealPanel();
        };
        el.addEventListener("click", go);
        el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
    });
    tour(root, setTriggerValue);
}
"""

BOARD_CSS = """
:host { --ink: #efe6d8; --red: #c0392b; --gold: #e8c27a; --bg: #14100e; --type: "Special Elite", "Courier New", monospace;
  --serif: "Playfair Display", Georgia, serif; --prose: Georgia, "Times New Roman", serif;
  --ui: "Source Sans Pro", "Source Sans 3", system-ui, sans-serif; }
.phone-only { display: none; }
.deck { color: var(--ink); font-family: var(--serif); font-variant-numeric: lining-nums; user-select: none; container-type: inline-size; }
button { font: inherit; color: inherit; cursor: pointer; }
/* Status bar */
.hud { display: flex; align-items: center; gap: 14px; padding: 8px 10px; background: linear-gradient(#241c18, #1a1411);
  border: 1px solid #3a2e28; border-radius: 14px; margin-bottom: 10px; }
.hud .me img { width: 40px; height: 40px; border-radius: 50%; object-fit: cover; object-position: top; border: 2px solid var(--gold); display: block; }
.hud .clock { display: flex; align-items: center; gap: 10px; flex: 1; min-width: 0; }
.hud .clock b { font: 700 28px var(--type); letter-spacing: .04em; font-variant-numeric: tabular-nums; }
.hud .clock small { font-size: 12px; opacity: .7; white-space: nowrap; }
.hud .fuse { flex: 1; height: 6px; background: #3a2e28; border-radius: 3px; overflow: hidden; min-width: 30px; }
.hud .fuse i { display: block; height: 100%; background: linear-gradient(90deg, var(--gold), var(--red)); transition: width .6s; }
.hud.urgent .clock b { color: #ff6b5a; animation: throb 1s ease-in-out infinite; }
.hud .stat { font-size: 16px; display: flex; align-items: center; gap: 5px; white-space: nowrap; }
.hud .stat b { font: 700 18px var(--type); }
.hud .stat small { font: 12px var(--ui); color: #cdbfa8; white-space: nowrap; }
.pips { display: inline-flex; gap: 3px; }
.pip { width: 11px; height: 11px; border-radius: 50%; border: 2px solid var(--red); display: inline-block; box-sizing: border-box; }
.pip.on { background: var(--red); }
.tools { display: flex; gap: 6px; }
.tools button { background: #2b221d; border: 1px solid #4a3a31; border-radius: 10px; width: 38px; height: 38px; padding: 0; font-size: 16px; }
.tools button:hover { border-color: var(--gold); }
.tools .accuse { width: auto; background: var(--red); border-color: #e05a48; font: 700 15px var(--type); letter-spacing: .08em;
  text-transform: uppercase; padding: 0 16px; animation: beckon 2.4s infinite; }
@keyframes beckon { 0%,70%,100% { box-shadow: 0 0 0 0 rgba(192,57,43,0); } 35% { box-shadow: 0 0 0 6px rgba(192,57,43,.35); } }
@keyframes throb { 50% { opacity: .55; } }
/* Map */
.map { width: min(100%, calc((100vh - 300px) * 1.5)); min-width: min(100%, 420px); height: auto; display: block; margin: 0 auto;
  border-radius: 14px; box-shadow: 0 10px 30px rgba(0,0,0,.5); }
.pin { cursor: pointer; }
.pin .ring { fill: none; stroke-width: 6; }
.pin .halo { fill: none; stroke: none; }
.pin.open .ring { stroke: var(--gold); }
.pin.available .ring { stroke: #fff; }
.pin.available .halo { stroke: var(--red); stroke-width: 8; transform-box: fill-box; transform-origin: center; animation: ping 1.6s ease-out infinite; }
.pin.locked .ring { stroke: #5a5048; stroke-dasharray: 6 6; }
.pin.spot .ring { stroke: #cdbfa8; stroke-dasharray: 5 6; stroke-width: 4; }
.pin.picked .ring { stroke: var(--gold); stroke-width: 9; }
.pin:hover .ring, .pin:focus .ring { stroke-width: 10; }
.pin:focus { outline: none; }
.pin .glyph { font: bold 34px var(--prose); text-anchor: middle; }
.pin .glyph.small { font-size: 26px; }
.pin .tag { font: 700 19px var(--serif); text-anchor: middle; fill: var(--ink); paint-order: stroke; stroke: #14100e; stroke-width: 6px; }
.pin.fresh { animation: pop .7s ease-out; }
.det { pointer-events: none; filter: drop-shadow(0 4px 6px rgba(0,0,0,.6)); }
@keyframes ping { 0% { transform: scale(.75); opacity: 1; } 100% { transform: scale(1.5); opacity: 0; } }
@keyframes pop { 0% { opacity: 0; } 60% { opacity: 1; } }
/* Evidence hand */
.handhead { display: flex; justify-content: space-between; align-items: baseline; margin: 12px 2px 6px; }
.handhead b { font: 400 13px var(--type); letter-spacing: .2em; text-transform: uppercase; color: var(--gold); }
.handhead span { font-size: 12px; opacity: .65; }
.hand { display: grid; grid-template-columns: repeat(var(--n, 9), minmax(0, 1fr)); gap: 8px; perspective: 900px; }
.card { position: relative; padding: 0; border: 2px solid #4a3a31; border-radius: 10px; background: #efe6d8; color: #2a201b;
  overflow: hidden; text-align: left; display: flex; flex-direction: column; min-width: 0;
  transition: transform .18s, box-shadow .18s, border-color .18s; }
.card:hover { transform: translateY(-5px); box-shadow: 0 8px 16px rgba(0,0,0,.55); border-color: var(--gold); }
.card .art { aspect-ratio: 4 / 3; background-size: cover; background-position: center; position: relative; }
.card .art.icon { display: flex; align-items: center; justify-content: center; font-size: 26px; background: #e2d4bd; }
.card .art.back { display: flex; align-items: center; justify-content: center; color: #f4d9a0; font: 700 26px var(--serif);
  background: repeating-linear-gradient(45deg, #5a1d16 0 6px, #6e241b 6px 12px); }
.card .art.back.locked { background: repeating-linear-gradient(45deg, #2a221e 0 6px, #332924 6px 12px); font-size: 17px; }
.card .lbl { display: flex; flex-direction: column; padding: 3px 6px 5px; min-width: 0; line-height: 1.2; }
.card .lbl b { font: 400 10px var(--type); opacity: .75; }
.card .lbl span { font: 600 11px var(--prose); height: 2.4em; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow-wrap: normal; word-break: normal; hyphens: auto; }
.card.locked { background: #2a221e; color: #8d7f72; border-color: #3a2e28; }
.card.available { border-color: var(--red); animation: glow 1.8s infinite; }
.card.picked { border-color: var(--gold); transform: translateY(-5px); box-shadow: 0 0 0 3px rgba(232,194,122,.45); }
.card .new { position: absolute; top: 4px; right: 4px; background: var(--red); color: #fff; font: 400 9px var(--type);
  padding: 1px 4px; border-radius: 3px; font-style: normal; letter-spacing: .08em; }
.card.fresh { animation: deal .7s cubic-bezier(.2,.9,.3,1.3); }
.card.flip { animation: flip .7s ease-out; }
@keyframes glow { 50% { box-shadow: 0 0 0 4px rgba(192,57,43,.35); } }
@keyframes deal { 0% { transform: translateY(-60px) rotate(-12deg) scale(1.3); opacity: 0; } 100% { transform: none; opacity: 1; } }
@keyframes flip { 0% { transform: rotateY(180deg); } 100% { transform: rotateY(0); } }
/* Suspects */
.suspects { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; }
.sus { position: relative; padding: 0; border: 2px solid #3a2e28; border-radius: 12px; background: #1c1613; overflow: hidden;
  transition: transform .18s, border-color .18s, box-shadow .18s; min-width: 0; }
.sus img, .sus .noimg { width: 100%; aspect-ratio: 4 / 5; object-fit: cover; display: block; }
.sus .noimg { display: flex; align-items: center; justify-content: center; font-size: 40px; }
.sus:hover { transform: translateY(-4px); border-color: var(--gold); box-shadow: 0 8px 18px rgba(0,0,0,.5); }
.sus.picked { border-color: var(--red); box-shadow: 0 0 0 3px rgba(192,57,43,.45); }
.sus.out img { filter: grayscale(1) brightness(.5); }
.sus .nm { position: absolute; left: 0; right: 0; bottom: 0; padding: 16px 3px 5px; font-size: 12px; text-align: center; line-height: 1.1;
  background: linear-gradient(transparent, rgba(10,8,7,.92) 45%); }
.sus .marks { position: absolute; top: 5px; right: 5px; display: flex; gap: 3px; }
.sus .tick, .sus .zap { font: 400 11px var(--type); border-radius: 10px; padding: 1px 5px; }
.sus .tick { background: var(--gold); color: #14100e; }
.sus .zap { background: var(--red); color: #fff; }
.sus .nv { position: absolute; left: 0; right: 0; bottom: 0; height: 4px; background: rgba(58,46,40,.9); }
.sus .nv b { display: block; height: 100%; background: linear-gradient(90deg, #e8c27a, #e0645a); transition: width .6s; }
.sus .nv.full b { background: #e0645a; animation: throb 1.2s infinite; }
.sus .stamp { position: absolute; top: 40%; left: 50%; transform: translate(-50%, -50%) rotate(-16deg); border: 2px solid #e0645a;
  color: #e0645a; background: rgba(20,16,14,.7); padding: 1px 4px; font: 400 11px var(--type); white-space: nowrap; }
/* First-play tour */
.tour { position: fixed; z-index: 1000; left: 50%; bottom: 24px; transform: translateX(-50%); width: min(360px, calc(100vw - 32px));
  background: #1c1613; color: var(--ink); border: 1px solid #3a2e28; border-left: 3px solid var(--gold); border-radius: 14px;
  padding: 14px 16px 12px; box-shadow: 0 18px 50px rgba(0,0,0,.7);
  animation: rise .35s ease-out; }
.tour .step { display: none; }
.tour .step.on { display: block; }
.tour .step b { font: 700 18px var(--serif); }
.tour .step p { margin: 4px 0 10px; font: 15px/1.4 var(--prose); color: #cdbfa8; }
.tour-nav { display: flex; align-items: center; justify-content: space-between; }
.tour-nav .dots { font-size: 10px; letter-spacing: 2px; color: var(--gold); }
.tour-nav button { border-radius: 8px; padding: 6px 14px; border: 1px solid #4a3a31; background: transparent; color: var(--ink); font: 500 14px var(--ui); }
.tour-nav .next { background: var(--red); border-color: var(--red); color: #fff; font-weight: 700; }
.tour-ring { position: fixed; z-index: 999; border: 3px solid var(--gold); border-radius: 14px; pointer-events: none;
  box-shadow: 0 0 0 9999px rgba(8,6,5,.6); transition: all .35s ease; }
@keyframes rise { from { opacity: 0; transform: translate(-50%, 16px); } to { opacity: 1; transform: translate(-50%, 0); } }
@media (max-width: 640px) {
  .hud { flex-wrap: wrap; gap: 8px 10px; padding: 8px; }
  .hud .clock { order: 1; flex: 1 1 auto; }
  .hud .me { order: 0; }
  .hud .me img { width: 34px; height: 34px; }
  .hud .clock b { font-size: 22px; }
  .hud .clock small { display: none; }
  .hud .stat { order: 2; font-size: 14px; }
  .tools { order: 3; flex: 1 1 100%; }
  .tools button { flex: 0 0 38px; }
  .tools .accuse { flex: 1 1 auto; }
  .phone-only { display: block; margin-bottom: 10px; }
  .hand { grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 6px; }
  .card .lbl { padding: 2px 4px 4px; }
  .card .lbl span { font-size: 10px; }
  .sus .nm { font-size: 9px; padding: 12px 2px 4px; }
  .sus .marks { top: 3px; right: 3px; }
  .suspects { gap: 5px; }
  .pin .tag { font-size: 24px; }
}
/* Next step: one objective, always visible */
.goal-bar { display: flex; align-items: center; gap: 10px; width: 100%; margin: 0 0 10px; padding: 8px 12px; text-align: left;
  border: 1px solid rgba(232,194,122,.55); border-radius: 12px; background: linear-gradient(90deg, rgba(232,194,122,.16), rgba(232,194,122,.04));
  color: var(--ink); cursor: pointer; font: 15px/1.3 var(--prose); animation: rise-in .4s ease-out; }
.goal-bar:hover { border-color: var(--gold); background: linear-gradient(90deg, rgba(232,194,122,.26), rgba(232,194,122,.08)); }
.goal-bar .gi { font-size: 22px; flex: 0 0 auto; }
.goal-bar .gt { flex: 1 1 auto; min-width: 0; }
.goal-bar small { display: block; font: 600 10px var(--type); letter-spacing: .16em; text-transform: uppercase; color: var(--gold); }
.goal-bar .go { font-size: 26px; color: var(--gold); flex: 0 0 auto; }
.goal-bar small.plain { text-transform: none; letter-spacing: .04em; font-size: 11px; margin-bottom: 2px; }
.goal-bar em { display: block; font-style: italic; line-height: 1.3; }
@keyframes rise-in { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: none; } }
.card.goal, .sus.goal { border-color: var(--gold); animation: beacon-box 1.8s ease-in-out infinite; }
@keyframes beacon-box { 50% { box-shadow: 0 0 0 4px rgba(232,194,122,.5), 0 0 18px rgba(232,194,122,.45); } }
/* The living map: night vignette, drifting mist, fog over locked places */
.night, .mist, .fog, .lift, .beacon { pointer-events: none; }
.mist ellipse { fill: #c9d3e8; opacity: .07; filter: blur(28px); }
.mist { animation: drift 38s ease-in-out infinite alternate; }
@keyframes drift { from { transform: translateX(-4%); } to { transform: translateX(5%); } }
.fog { animation: breathe 6s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }
@keyframes breathe { 50% { transform: scale(1.08); opacity: .85; } }
.lift { transform-box: fill-box; transform-origin: center; animation: lift 1.6s ease-out forwards; }
@keyframes lift { from { opacity: 1; transform: scale(1); } to { opacity: 0; transform: scale(1.8); } }
.beacon { fill: none; stroke: none; }
.pin.goal .beacon { stroke: var(--gold); stroke-width: 7; transform-box: fill-box; transform-origin: center; animation: ping 1.4s ease-out infinite; }
.pin.goal .ring { stroke: var(--gold); stroke-width: 9; }
.pin.available, .pin.open { transition: filter .2s; }
.pin.available:hover, .pin.open:hover, .pin.goal { filter: drop-shadow(0 0 10px rgba(232,194,122,.8)); }
@media (prefers-reduced-motion: reduce) {
  .mist, .fog, .lift, .pin .halo, .pin.goal .beacon, .card.goal, .sus.goal, .goal-bar { animation: none !important; }
  .lift { opacity: 0; }
}
@media (max-width: 640px) {
  .goal-bar { font-size: 14px; padding: 7px 10px; }
}
/* Line icons */
.ic { width: 1.15em; height: 1.15em; display: inline-block; vertical-align: -0.2em; flex: 0 0 auto; }
.tools button { color: #e8dccb; display: inline-flex; align-items: center; justify-content: center; }
.tools button .ic { width: 19px; height: 19px; }
.tools button:hover { color: var(--gold); }
.mute .off, .mute.muted .on { display: none; }
.tools .calmbtn.on { border-color: var(--gold); color: var(--gold); background: #3a2e1c; }
/* Calm mode: nothing moves or blinks, the drifting mist is gone. Locked places keep their (still) fog. */
.deck.calm *, .deck.calm *::before, .deck.calm *::after { animation: none !important; transition: none !important; }
.deck.calm .mist, .deck.calm .lift { display: none; }
.mute.muted .off { display: inline-block; }
.hud .stat .ic { width: 20px; height: 20px; color: #cdbfa8; }
.hud .zapstat .ic { color: var(--gold); }
.card .art.icon { color: #3a2e28; }
.card .art.icon .ic { width: 30px; height: 30px; }
.card .art.back.locked { color: #8a7a6a; }
.card .art.back.locked .ic { width: 20px; height: 20px; }
.sus .zap { display: inline-flex; align-items: center; gap: 1px; }
.sus .zap .ic { width: 11px; height: 11px; }
.sus .noimg .ic { width: 40px; height: 40px; color: #8a7a6a; }
.goal-bar .gi .ic { width: 24px; height: 24px; color: var(--gold); display: block; }
/* Narrow boards (a small laptop window, a tablet): lay out by the board's own width, not the screen's */
@container (max-width: 700px) {
  .hud { flex-wrap: wrap; gap: 8px 10px; padding: 8px; }
  .hud .clock { order: 1; flex: 1 1 auto; min-width: 0; }
  .hud .me { order: 0; }
  .hud .me img { width: 34px; height: 34px; }
  .hud .clock b { font-size: 22px; }
  .hud .clock small { display: none; }
  .hud .stat { order: 2; font-size: 14px; }
  .tools { order: 3; flex: 1 1 100%; }
  .tools button { flex: 0 0 38px; }
  .tools .accuse { flex: 1 1 auto; }
  .hand { gap: 5px; }
  .card .lbl { padding: 2px 4px 4px; }
  .card .lbl span { font-size: 10px; }
}
@container (max-width: 520px) {
  .hand { grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 6px; }
}
/* The short name is for narrow rows only. This rule must come before the @container rule below,
   or it wins and a narrow row (the desktop side column) shows no name at all. */
.sus .nm .short { display: none; }
@container (max-width: 560px) {
  .suspects { gap: 5px; }
  .sus .nm { font-size: 10px; padding: 12px 2px 4px; }
  .sus .nm .long { display: none; }
  .sus .nm .short { display: inline; }
  .sus .marks { top: 3px; right: 3px; }
}
"""
