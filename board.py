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

KIND_ICON = {"document": "📄", "location": "📍"}
# A few clues have no picture. Their card shows a big icon instead.
CARD_ICON = {"D4": "📊", "L2": "☕", "L4": "🚪"}


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
    if kind == "suspect" and value in suspects:
        return ("suspect", value)
    if kind in ("clue", "place") and value in clues:
        return ("clue", value)
    if kind == "spot" and value in MAP_SPOTS:
        return ("spot", value)
    if kind in ("home", "sheet", "accuse", "intro") and not value:
        return (kind, None)
    return None


# ---- Status bar --------------------------------------------------------------------


def hud_html(clock, minutes_left, limit, strikes_left, max_strikes, caught, avatar_uri, name):
    """Time, the fuse burning down to 09:00, accusations left as pips, lies caught, and the buttons."""
    hours, minutes = divmod(max(minutes_left, 0), 60)
    burnt = 100 * (1 - max(minutes_left, 0) / limit)
    urgent = " urgent" if minutes_left <= 120 else ""
    pips = "".join(f'<i class="pip{" on" if n < strikes_left else ""}"></i>' for n in range(max_strikes))
    face = f'<img src="{avatar_uri}" alt="">' if avatar_uri else '<span class="noface">🕵️</span>'
    return (
        f'<div class="hud{urgent}">'
        f'<div class="me">{face}<span class="who"><small>Detective</small>{esc(name)}</span></div>'
        f'<div class="clock"><b>{esc(clock)}</b><div class="fuse"><i style="width:{burnt:.1f}%"></i></div>'
        f"<small>{hours}h {minutes:02d}m to 09:00</small></div>"
        f'<div class="stat" title="Wrong accusations left">⚖️ <span class="pips">{pips}</span></div>'
        f'<div class="stat" title="Lies caught">⚡ <b>{caught}</b></div>'
        '<div class="tools">'
        '<button data-act="home" title="Your leads">🔎</button>'
        '<button data-act="sheet" title="Case sheet">📋</button>'
        '<button data-act="intro" title="Story and how to play">📖</button>'
        '<button class="accuse" data-act="accuse">⚖️ Accuse</button></div></div>'
    )


# ---- The campus map ----------------------------------------------------------------


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


def map_html(map_uri, size, points, opened, picked=None, avatar_uri=None, fresh=()):
    """The campus picture as the board: pins for places, the detective's token, Chiado."""
    width, height = size
    s = width / 1200  # every size below is for a 1200-pixel-wide picture
    parts = [
        f'<svg class="map" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Campus map"><image href="{map_uri}" width="{width}" height="{height}"/>'
    ]
    for p in points:
        x, y = p["x"] * width, p["y"] * height
        state = p["state"]
        classes = f"pin {state}" + (" picked" if p["id"] == picked else "") + (" fresh" if p["id"] in fresh else "")
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
            face = '<circle r="34" fill="#2a221e"/><text class="glyph small" y="9">🔒</text>'
        parts.append(
            f'<g class="{classes}" data-act="place:{p["id"]}" transform="translate({x:.0f} {y:.0f}) scale({s:.3f})" '
            f'role="button" tabindex="0" aria-label="{label}"><title>{label}</title>'
            '<circle class="halo" r="46"/>'
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
    tx, ty = dx * width + 44 * s, dy * height - 40 * s
    token = f'<image href="{avatar_uri}" x="-26" y="-26" width="52" height="65" clip-path="url(#detclip)" preserveAspectRatio="xMidYMin slice"/>' if avatar_uri else '<text y="10" class="glyph">🕵️</text>'
    parts.append(
        f'<g class="det" data-x="{tx:.0f}" data-y="{ty:.0f}" transform="translate({tx:.0f} {ty:.0f}) scale({s:.3f})">'
        '<clipPath id="detclip"><circle r="26"/></clipPath><circle r="30" fill="#14100e"/>'
        f'{token}<circle r="28" fill="none" stroke="#e8c27a" stroke-width="4"/></g>'
    )
    parts.append("</svg>")
    return "".join(parts)


# ---- Evidence cards ----------------------------------------------------------------


def card_html(item, picked=None, fresh=()):
    """One evidence card. Face up with its picture once opened; face down otherwise."""
    state = item["state"]
    classes = f"card {state}" + (" picked" if item["id"] == picked else "") + (" fresh" if item["id"] in fresh else "")
    title = esc(item["title"])
    if state == "open":
        uri = find_picture("clues", item["id"])
        art = (
            f'<div class="art" style="background-image:url({uri})"></div>' if uri
            else f'<div class="art icon">{CARD_ICON.get(item["id"], KIND_ICON[item["kind"]])}</div>'
        )
    elif state == "available":
        art = '<div class="art back"><span>?</span></div>'
    else:
        art = '<div class="art back locked"><span>🔒</span></div>'
    badge = {"available": '<em class="new">NEW</em>', "open": "", "locked": ""}[state]
    return (
        f'<button class="{classes}" data-act="clue:{item["id"]}" title="{item["id"]}. {title}">'
        f'{art}<div class="id">{KIND_ICON[item["kind"]]} {item["id"]}</div><div class="t">{title}</div>{badge}</button>'
    )


def hand_html(clues, picked=None, fresh=()):
    """Every clue as a card, in case order, so each card keeps its place in the hand."""
    opened = sum(c["state"] == "open" for c in clues)
    return (
        f'<div class="handhead"><b>Evidence</b><span>{opened} of {len(clues)} found</span></div>'
        '<div class="hand">' + "".join(card_html(c, picked, fresh) for c in clues) + "</div>"
    )


# ---- Suspects ----------------------------------------------------------------------


def suspects_html(suspects, picked=None):
    """The five suspects as big cards. Each item: id, name, questioned, caught, ruled_out."""
    cards = []
    for s in suspects:
        uri = find_picture("suspects", s["id"])
        name = esc(short_name(s["name"]))
        classes = "sus" + (" picked" if s["id"] == picked else "") + (" out" if s["ruled_out"] else "")
        marks = ""
        if s["questioned"]:
            marks += '<span class="tick" title="Questioned">✓</span>'
        if s["caught"]:
            marks += f'<span class="zap" title="Caught lying">⚡{s["caught"]}</span>'
        stamp = '<span class="stamp">RULED OUT</span>' if s["ruled_out"] else ""
        picture = f'<img src="{uri}" alt="{esc(s["name"])}">' if uri else '<div class="noimg">👤</div>'
        cards.append(
            f'<button class="{classes}" data-act="suspect:{s["id"]}" aria-label="Question {esc(s["name"])}">'
            f'{picture}<div class="marks">{marks}</div>{stamp}<div class="nm">{name}</div></button>'
        )
    return '<div class="suspects">' + "".join(cards) + "</div>"


# ---- The component: draws the markup and sends taps back to Python ------------------

BOARD_JS = """
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
    const det = root.querySelector(".det");
    const to = det ? det.getAttribute("transform") : null;
    if (det && from && to && from !== to) {
        try { det.animate([{ transform: from.replace(/translate\\(([-\\d.]+) ([-\\d.]+)\\)/, "translate($1px, $2px)") },
                           { transform: to.replace(/translate\\(([-\\d.]+) ([-\\d.]+)\\)/, "translate($1px, $2px)") }],
                          { duration: 800, easing: "ease-in-out" }); } catch (e) {}
    }
    root.querySelectorAll("[data-act]").forEach((el) => {
        const go = () => {
            setTriggerValue("act", el.getAttribute("data-act"));
            if (window.matchMedia("(max-width: 640px)").matches) {
                const panel = document.querySelector(".st-key-panel");
                if (panel) setTimeout(() => panel.scrollIntoView({ behavior: "smooth", block: "start" }), 350);
            }
        };
        el.addEventListener("click", go);
        el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
    });
}
"""

BOARD_CSS = """
:host { --ink: #efe6d8; --red: #c0392b; --gold: #e8c27a; --bg: #14100e; --panel: #1f1814; }
.phone-only { display: none; }
.deck { color: var(--ink); font-family: Georgia, "Times New Roman", serif; user-select: none; }
button { font: inherit; color: inherit; cursor: pointer; }
/* Status bar */
.hud { display: flex; align-items: center; gap: 14px; padding: 8px 12px; background: linear-gradient(#241c18, #1a1411);
  border: 1px solid #3a2e28; border-radius: 14px; margin-bottom: 10px; flex-wrap: wrap; }
.hud .me { display: flex; align-items: center; gap: 8px; }
.hud .me img { width: 40px; height: 40px; border-radius: 50%; object-fit: cover; object-position: top; border: 2px solid var(--gold); }
.hud .who { display: flex; flex-direction: column; font-size: 15px; line-height: 1.1; }
.hud .who small { font: 10px "Courier New", monospace; letter-spacing: .15em; text-transform: uppercase; opacity: .6; }
.hud .clock { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 180px; }
.hud .clock b { font-size: 28px; letter-spacing: .04em; font-variant-numeric: tabular-nums; }
.hud .clock small { font-size: 12px; opacity: .7; white-space: nowrap; }
.hud .fuse { flex: 1; height: 6px; background: #3a2e28; border-radius: 3px; overflow: hidden; min-width: 50px; }
.hud .fuse i { display: block; height: 100%; background: linear-gradient(90deg, var(--gold), var(--red)); }
.hud.urgent .clock b { color: #ff6b5a; animation: throb 1s ease-in-out infinite; }
.hud .stat { font-size: 17px; display: flex; align-items: center; gap: 5px; }
.pips { display: inline-flex; gap: 3px; }
.pip { width: 11px; height: 11px; border-radius: 50%; border: 2px solid var(--red); display: inline-block; }
.pip.on { background: var(--red); }
.tools { display: flex; gap: 6px; }
.tools button { background: #2b221d; border: 1px solid #4a3a31; border-radius: 10px; padding: 6px 10px; font-size: 16px; }
.tools button:hover { border-color: var(--gold); }
.tools .accuse { background: var(--red); border-color: #e05a48; font-weight: bold; letter-spacing: .06em;
  text-transform: uppercase; font-size: 14px; padding: 7px 14px; box-shadow: 0 0 0 0 rgba(192,57,43,.6); animation: beckon 2.4s infinite; }
@keyframes beckon { 0%,70%,100% { box-shadow: 0 0 0 0 rgba(192,57,43,0); } 35% { box-shadow: 0 0 0 6px rgba(192,57,43,.35); } }
@keyframes throb { 50% { opacity: .55; } }
/* Map */
.map { width: 100%; height: auto; display: block; border-radius: 14px; box-shadow: 0 10px 30px rgba(0,0,0,.5); }
.pin { cursor: pointer; }
.pin .ring { fill: none; stroke-width: 6; }
.pin .halo { fill: none; stroke: none; }
.pin.open .ring { stroke: var(--gold); }
.pin.available .ring { stroke: #fff; }
.pin.available .halo { stroke: var(--red); stroke-width: 8; transform-box: fill-box; transform-origin: center; animation: ping 1.6s ease-out infinite; }
.pin.locked .ring { stroke: #5a5048; stroke-dasharray: 6 6; }
.pin.locked { opacity: .85; }
.pin.spot .ring { stroke: #cdbfa8; stroke-dasharray: 5 6; stroke-width: 4; }
.pin.picked .ring { stroke: var(--gold); stroke-width: 9; }
.pin:hover .ring, .pin:focus .ring { stroke-width: 10; }
.pin:focus { outline: none; }
.pin .glyph { font: bold 34px Georgia, serif; text-anchor: middle; }
.pin .glyph.small { font-size: 26px; }
.pin .tag { font: bold 19px Georgia, serif; text-anchor: middle; fill: var(--ink); paint-order: stroke; stroke: #14100e; stroke-width: 6px; }
.pin.fresh { animation: pop .7s ease-out; transform-box: fill-box; transform-origin: center; }
.det { pointer-events: none; filter: drop-shadow(0 4px 6px rgba(0,0,0,.6)); }
@keyframes ping { 0% { transform: scale(.75); opacity: 1; } 100% { transform: scale(1.5); opacity: 0; } }
@keyframes pop { 0% { opacity: 0; } 60% { opacity: 1; } }
/* Evidence hand */
.handhead { display: flex; justify-content: space-between; align-items: baseline; margin: 12px 2px 6px; }
.handhead b { font: bold 12px "Courier New", monospace; letter-spacing: .2em; text-transform: uppercase; color: var(--gold); }
.handhead span { font-size: 12px; opacity: .65; }
.hand { display: grid; grid-template-columns: repeat(13, minmax(0, 1fr)); gap: 6px; }
.card { position: relative; padding: 0; border: 2px solid #4a3a31; border-radius: 9px; background: #efe6d8; color: #2a201b;
  overflow: hidden; text-align: left; transition: transform .18s, box-shadow .18s, border-color .18s;
  display: flex; flex-direction: column; }
.card:hover { transform: translateY(-6px) rotate(-1.5deg); box-shadow: 0 8px 16px rgba(0,0,0,.55); border-color: var(--gold); }
.card .art { aspect-ratio: 1 / 1; background-size: cover; background-position: center; }
.card .art.icon { display: flex; align-items: center; justify-content: center; font-size: 26px; background: #e2d4bd; }
.card .art.back { display: flex; align-items: center; justify-content: center; background:
  repeating-linear-gradient(45deg, #5a1d16 0 6px, #6e241b 6px 12px); color: #f4d9a0; font: bold 26px Georgia, serif; }
.card .art.back.locked { background: repeating-linear-gradient(45deg, #2a221e 0 6px, #332924 6px 12px); font-size: 18px; }
.card .id { font: bold 10px "Courier New", monospace; padding: 3px 5px 0; letter-spacing: .05em; }
.card .t { font-size: 10px; line-height: 1.15; padding: 0 5px 5px; height: 2.3em; overflow: hidden; }
.card.locked { background: #2a221e; color: #8d7f72; border-color: #3a2e28; }
.card.available { border-color: var(--red); box-shadow: 0 0 0 0 rgba(192,57,43,.7); animation: glow 1.8s infinite; }
.card.picked { border-color: var(--gold); transform: translateY(-6px); box-shadow: 0 0 0 3px rgba(232,194,122,.45); }
.card .new { position: absolute; top: 4px; right: 4px; background: var(--red); color: #fff; font: bold 9px "Courier New", monospace;
  padding: 1px 4px; border-radius: 3px; font-style: normal; letter-spacing: .08em; }
.card.fresh { animation: deal .7s cubic-bezier(.2,.9,.3,1.3); }
@keyframes glow { 50% { box-shadow: 0 0 0 4px rgba(192,57,43,.35); } }
@keyframes deal { 0% { transform: translateY(-60px) rotate(-12deg) scale(1.3); opacity: 0; } 100% { transform: none; opacity: 1; } }
/* Suspects */
.suspects { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; }
.sus { position: relative; padding: 0; border: 2px solid #3a2e28; border-radius: 12px; background: #1c1613; overflow: hidden;
  transition: transform .18s, border-color .18s, box-shadow .18s; }
.sus img, .sus .noimg { width: 100%; aspect-ratio: 4 / 5; object-fit: cover; display: block; }
.sus .noimg { display: flex; align-items: center; justify-content: center; font-size: 40px; }
.sus:hover { transform: translateY(-4px); border-color: var(--gold); box-shadow: 0 8px 18px rgba(0,0,0,.5); }
.sus.picked { border-color: var(--red); box-shadow: 0 0 0 3px rgba(192,57,43,.45); }
.sus.out img { filter: grayscale(1) brightness(.5); }
.sus .nm { position: absolute; left: 0; right: 0; bottom: 0; padding: 14px 4px 5px; font-size: 12px; text-align: center; line-height: 1.1;
  background: linear-gradient(transparent, rgba(10,8,7,.92) 45%); }
.sus .marks { position: absolute; top: 5px; right: 5px; display: flex; gap: 3px; }
.sus .tick, .sus .zap { font: bold 11px "Courier New", monospace; border-radius: 10px; padding: 1px 5px; }
.sus .tick { background: #e8c27a; color: #14100e; }
.sus .zap { background: var(--red); color: #fff; }
.sus .stamp { position: absolute; top: 40%; left: 50%; transform: translate(-50%, -50%) rotate(-16deg); border: 2px solid #e0645a;
  color: #e0645a; background: rgba(20,16,14,.7); padding: 1px 4px; font: bold 11px "Courier New", monospace; white-space: nowrap; }
@media (max-width: 640px) {
  .hud { gap: 8px; padding: 6px 8px; }
  .hud .who { display: none; }
  .hud .clock b { font-size: 22px; }
  .hud .clock { min-width: 120px; }
  .hud .clock small { display: none; }
  .phone-only { display: block; margin-bottom: 10px; }
  .tools button { padding: 5px 7px; font-size: 14px; }
  .tools .accuse { font-size: 12px; padding: 6px 9px; }
  .hand { grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 5px; }
  .card .t { display: none; }
  .sus .nm { font-size: 9px; }
  .suspects { gap: 5px; }
}
"""
