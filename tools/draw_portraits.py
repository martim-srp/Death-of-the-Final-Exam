"""Generate the five suspect portraits as small SVG files.

Shared style (matches assets/cover.webp): near-black room, a spotlight from the top right,
a deep red disc behind the head, the figure in parchment and sepia with ink lines, and one
signature prop per suspect. Split lighting: the left of each face falls into shadow.

Run from the repository root to redraw them:  python tools/draw_portraits.py assets/suspects
"""

import sys
from pathlib import Path

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

INK = "#14100e"
INK2 = "#241c18"
RED = "#7d1d1a"
STAMP = "#c0392b"
PAPER = "#efe6d8"
SKIN = "#d9b99a"
SKIN_SH = "#a8846a"
SEPIA = "#6b4f3a"
BRASS = "#b8924f"


def svg(name, body, title):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 250" role="img" aria-label="{title}">
<title>{title}</title>
<defs>
<radialGradient id="spot" cx="0.85" cy="0" r="1.1"><stop offset="0" stop-color="#5a4632"/><stop offset="0.55" stop-color="{INK2}"/><stop offset="1" stop-color="{INK}"/></radialGradient>
<linearGradient id="shade" x1="0" x2="1"><stop offset="0" stop-color="{INK}" stop-opacity="0.55"/><stop offset="0.5" stop-color="{INK}" stop-opacity="0"/></linearGradient>
<clipPath id="frame"><rect x="0" y="0" width="200" height="250" rx="10"/></clipPath>
</defs>
<g clip-path="url(#frame)">
<rect width="200" height="250" fill="url(#spot)"/>
<g fill="#efe6d8" opacity="0.05"><polygon points="120,0 140,0 40,250 20,250"/><polygon points="155,0 175,0 75,250 55,250"/><polygon points="190,0 210,0 110,250 90,250"/></g>
<circle cx="100" cy="100" r="66" fill="{RED}" opacity="0.85"/>
{body}
<rect x="0" y="0" width="200" height="250" fill="url(#shade)"/>
</g>
<rect x="3" y="3" width="194" height="244" rx="8" fill="none" stroke="{BRASS}" stroke-width="2" opacity="0.8"/>
</svg>
"""


def head(cx=100, cy=104, rx=33, ry=41):
    # Neck, face, ear and the shadowed half of the face.
    return f"""<rect x="{cx-12}" y="{cy+28}" width="24" height="34" fill="{SKIN_SH}"/>
<ellipse cx="{cx-rx+1}" cy="{cy+4}" rx="6" ry="9" fill="{SKIN_SH}"/>
<ellipse cx="{cx+rx-1}" cy="{cy+4}" rx="6" ry="9" fill="{SKIN}"/>
<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{SKIN}" stroke="{INK}" stroke-width="1.5"/>
<path d="M{cx} {cy-ry} A{rx} {ry} 0 0 0 {cx} {cy+ry} C{cx-14} {cy+20} {cx-10} {cy-20} {cx} {cy-ry} Z" fill="{SKIN_SH}" opacity="0.6"/>"""


def eyes(cx=100, y=102, gap=13, look=0, brow="flat"):
    brows = {
        "flat": f"M{cx-gap-8} {y-10} L{cx-gap+7} {y-10} M{cx+gap-7} {y-10} L{cx+gap+8} {y-10}",
        "raised": f"M{cx-gap-8} {y-10} Q{cx-gap} {y-16} {cx-gap+7} {y-11} M{cx+gap-7} {y-11} Q{cx+gap} {y-16} {cx+gap+8} {y-10}",
        "worried": f"M{cx-gap-8} {y-9} L{cx-gap+7} {y-14} M{cx+gap-7} {y-14} L{cx+gap+8} {y-9}",
        "frown": f"M{cx-gap-8} {y-14} L{cx-gap+7} {y-9} M{cx+gap-7} {y-9} L{cx+gap+8} {y-14}",
        "sly": f"M{cx-gap-8} {y-11} L{cx-gap+7} {y-11} M{cx+gap-7} {y-12} Q{cx+gap} {y-17} {cx+gap+8} {y-13}",
    }[brow]
    return f"""<path d="{brows}" stroke="{INK}" stroke-width="2.4" stroke-linecap="round" fill="none"/>
<ellipse cx="{cx-gap}" cy="{y}" rx="4.5" ry="3" fill="{PAPER}"/><ellipse cx="{cx+gap}" cy="{y}" rx="4.5" ry="3" fill="{PAPER}"/>
<circle cx="{cx-gap+look}" cy="{y}" r="2.2" fill="{INK}"/><circle cx="{cx+gap+look}" cy="{y}" r="2.2" fill="{INK}"/>"""


def nose(cx=100, y=104):
    return f'<path d="M{cx+1} {y} L{cx+5} {y+13} L{cx-1} {y+14}" stroke="{SEPIA}" stroke-width="1.6" fill="none" stroke-linecap="round"/>'


# ---- The Class Representative: navy blazer, cohort pin, the phone that "reported it" --------
class_rep = f"""
<path d="M18 250 C22 196 58 170 100 168 C142 170 178 196 182 250 Z" fill="#1f2a3d" stroke="{INK}" stroke-width="1.5"/>
<path d="M82 168 L100 206 L118 168 Z" fill="{PAPER}"/>
<path d="M100 178 L94 188 L100 236 L106 188 Z" fill="{STAMP}"/>
<path d="M78 168 L100 214 L72 250 L56 250 L66 196 Z" fill="#2b3a54"/><path d="M122 168 L100 214 L128 250 L144 250 L134 196 Z" fill="#2b3a54"/>
<circle cx="132" cy="200" r="5" fill="{BRASS}" stroke="{INK}"/><circle cx="132" cy="200" r="2" fill="{INK}"/>
{head()}
<path d="M66 98 C62 62 84 54 104 56 C128 56 140 72 134 98 C130 84 124 76 112 74 C98 72 84 74 74 80 C70 86 68 92 66 98 Z" fill="#3a2a1e" stroke="{INK}" stroke-width="1.5"/>
<path d="M112 74 C104 70 92 70 84 76" stroke="{INK}" stroke-width="1.5" fill="none"/>
{eyes(look=1, brow='flat')}
{nose()}
<path d="M90 126 Q100 132 112 125" stroke="{INK}" stroke-width="2" fill="none" stroke-linecap="round"/>
<g transform="translate(118 206) rotate(-12)">
<rect x="0" y="0" width="30" height="48" rx="4" fill="{INK}" stroke="{BRASS}" stroke-width="1"/>
<rect x="3" y="5" width="24" height="36" fill="#cfe8d0" opacity="0.9"/>
<rect x="6" y="9" width="15" height="6" rx="3" fill="#4f8a57"/><rect x="9" y="19" width="15" height="6" rx="3" fill="#4f8a57"/><rect x="6" y="29" width="11" height="6" rx="3" fill="{STAMP}"/>
</g>
<path d="M112 206 C118 200 130 200 136 208 L132 228 C124 230 116 226 112 220 Z" fill="{SKIN}" stroke="{INK}" stroke-width="1.2"/>
"""

# ---- The Teaching Assistant: round glasses, cardigan, an empty lanyard, the proofs --------
ta = f"""
<path d="M18 250 C22 196 58 172 100 170 C142 172 178 196 182 250 Z" fill="#5b4a3a" stroke="{INK}" stroke-width="1.5"/>
<path d="M84 170 L100 196 L116 170 Z" fill="#cdd3d6"/>
<path d="M84 172 L96 250 M116 172 L104 250" stroke="{STAMP}" stroke-width="3"/>
<rect x="92" y="232" width="16" height="10" rx="2" fill="none" stroke="{BRASS}" stroke-width="2" stroke-dasharray="3 2"/>
<g fill="{INK}" opacity="0.35"><circle cx="60" cy="214" r="2"/><circle cx="62" cy="230" r="2"/><circle cx="140" cy="214" r="2"/><circle cx="138" cy="230" r="2"/></g>
{head()}
<path d="M64 96 C56 70 66 52 84 54 C86 46 104 44 110 52 C122 46 140 58 136 76 C144 84 138 96 134 98 C132 86 126 78 118 80 C110 72 96 82 88 76 C80 82 70 86 64 96 Z" fill="#2a1d14" stroke="{INK}" stroke-width="1.5"/>
<g fill="#2a1d14"><circle cx="72" cy="66" r="7"/><circle cx="92" cy="54" r="7"/><circle cx="116" cy="54" r="7"/><circle cx="132" cy="68" r="7"/></g>
{eyes(look=-2, brow='worried')}
<g fill="none" stroke="{INK}" stroke-width="2"><circle cx="87" cy="102" r="10"/><circle cx="113" cy="102" r="10"/><path d="M97 101 Q100 98 103 101 M77 100 L68 96 M123 100 L132 96"/></g>
<g fill="{PAPER}" opacity="0.35"><path d="M81 97 L85 95 L84 99 Z"/><path d="M107 97 L111 95 L110 99 Z"/></g>
{nose(y=106)}
<path d="M91 128 Q97 124 103 128 Q108 131 112 127" stroke="{INK}" stroke-width="2" fill="none" stroke-linecap="round"/>
<path d="M134 80 C138 86 138 90 134 92 C130 90 130 86 134 80 Z" fill="#cfe1ea" stroke="{INK}" stroke-width="0.8"/>
<g transform="translate(36 196) rotate(-8)">
<rect x="0" y="6" width="56" height="44" fill="#d8ccb6" stroke="{INK}"/><rect x="4" y="2" width="56" height="44" fill="{PAPER}" stroke="{INK}"/>
<g stroke="{SEPIA}" stroke-width="1.5"><path d="M10 12 H52 M10 18 H48 M10 24 H52 M10 30 H40"/></g>
<path d="M30 34 L50 22" stroke="{STAMP}" stroke-width="2.5"/>
</g>
"""

# ---- The Exchange Student: sunglasses up, linen shirt, a scarf, the café cup ---------------
exchange = f"""
<path d="M18 250 C22 196 58 172 100 170 C142 172 178 196 182 250 Z" fill="#d6c7a8" stroke="{INK}" stroke-width="1.5"/>
<path d="M84 170 L100 214 L116 170" fill="{SKIN_SH}" stroke="{INK}" stroke-width="1.2"/>
<path d="M70 170 C80 186 120 186 130 170 C126 196 112 198 106 192 L112 236 L96 238 L98 192 C88 196 74 192 70 170 Z" fill="{STAMP}" stroke="{INK}" stroke-width="1.2"/>
<g stroke="{RED}" stroke-width="2"><path d="M100 202 L108 236"/></g>
{head()}
<path d="M64 108 C54 70 74 50 100 52 C130 50 148 72 136 112 C134 96 134 84 128 78 C114 86 92 76 84 72 C76 82 70 90 66 108 Z" fill="#7a5a3a" stroke="{INK}" stroke-width="1.5"/>
<path d="M136 112 C142 128 140 140 132 146 M64 108 C58 124 60 136 68 142" stroke="#7a5a3a" stroke-width="6" fill="none" stroke-linecap="round"/>
<g transform="translate(0 -4)"><rect x="72" y="66" width="24" height="13" rx="6" fill="{INK}"/><rect x="104" y="66" width="24" height="13" rx="6" fill="{INK}"/><path d="M96 71 H104" stroke="{INK}" stroke-width="3"/>
<path d="M76 69 L84 68" stroke="{PAPER}" stroke-width="1.5" opacity="0.6"/><path d="M108 69 L116 68" stroke="{PAPER}" stroke-width="1.5" opacity="0.6"/></g>
{eyes(look=2, brow='sly')}
{nose()}
<path d="M90 126 Q104 130 113 120" stroke="{INK}" stroke-width="2" fill="none" stroke-linecap="round"/>
<g transform="translate(128 196)">
<path d="M0 6 L26 6 L22 48 L4 48 Z" fill="{PAPER}" stroke="{INK}" stroke-width="1.2"/>
<rect x="-1" y="2" width="28" height="6" rx="2" fill="{SEPIA}" stroke="{INK}"/>
<rect x="2" y="20" width="22" height="12" fill="{STAMP}" opacity="0.8"/>
<path d="M8 -4 C4 -10 12 -14 8 -20 M17 -4 C13 -10 21 -14 17 -22" stroke="{PAPER}" stroke-width="1.5" fill="none" opacity="0.5"/>
</g>
<path d="M120 214 C124 206 132 208 134 214 L134 232 C128 236 122 232 120 226 Z" fill="{SKIN}" stroke="{INK}" stroke-width="1.2"/>
"""

# ---- The Professor: grey beard, half-moon glasses, tweed, oxblood bow tie, laptop strap -----
tweed = "".join(f'<path d="M{x} 170 L{x-30} 250" stroke="{INK}" stroke-width="0.8" opacity="0.25"/>' for x in range(30, 210, 9))
professor = f"""
<path d="M14 250 C18 194 56 168 100 166 C144 168 182 194 186 250 Z" fill="#7a6248" stroke="{INK}" stroke-width="1.5"/>
<g clip-path="url(#frame)">{tweed}</g>
<path d="M82 166 L100 200 L118 166 Z" fill="{PAPER}"/>
<path d="M88 176 L100 182 L112 176 L112 190 L100 184 L88 190 Z" fill="{STAMP}" stroke="{INK}"/><circle cx="100" cy="183" r="3" fill="{RED}"/>
<path d="M78 166 L100 206 L76 250 L60 250 L68 194 Z" fill="#6a533c"/><path d="M122 166 L100 206 L124 250 L140 250 L132 194 Z" fill="#6a533c"/>
<path d="M150 178 L66 250 L84 250 L160 186 Z" fill="{INK2}" stroke="{INK}"/><rect x="118" y="198" width="10" height="7" fill="{BRASS}" transform="rotate(-40 123 201)"/>
{head(cy=102, rx=34, ry=43)}
<path d="M66 100 C62 86 66 72 72 70 C70 82 72 92 74 100 Z M134 100 C138 86 134 72 128 70 C130 82 128 92 126 100 Z" fill="#b8b2a8" stroke="{INK}" stroke-width="1.2"/>
<path d="M84 66 C92 62 108 62 116 66" stroke="{PAPER}" stroke-width="1.5" fill="none" opacity="0.5"/>
<path d="M70 112 C72 140 86 152 100 152 C114 152 128 140 130 112 C122 124 112 128 100 128 C88 128 78 124 70 112 Z" fill="#c9c3b8" stroke="{INK}" stroke-width="1.5"/>
<path d="M88 124 Q100 118 112 124" stroke="#c9c3b8" stroke-width="5" fill="none"/>
{eyes(y=98, look=-1, brow='frown')}
<g fill="none" stroke="{BRASS}" stroke-width="2"><path d="M76 104 A11 7 0 0 0 98 104 Z M102 104 A11 7 0 0 0 124 104 Z M98 104 Q100 102 102 104"/></g>
{nose(y=102)}
<path d="M92 136 Q100 132 108 136" stroke="{INK}" stroke-width="2" fill="none" stroke-linecap="round"/>
"""

# ---- The Companion: wide-brimmed hat, eyes in shadow, red lips, a pearl, a calling card -----
companion = f"""
<path d="M18 250 C22 196 58 172 100 170 C142 172 178 196 182 250 Z" fill="{INK2}" stroke="{INK}" stroke-width="1.5"/>
<path d="M70 172 C78 160 88 160 100 176 C112 160 122 160 130 172 L120 250 L80 250 Z" fill="#3a2e26" stroke="{INK}" stroke-width="1.2"/>
<path d="M66 102 C58 140 60 170 52 196 C70 190 74 170 76 150 Z M134 102 C142 140 140 170 148 196 C130 190 126 170 124 150 Z" fill="#1b1310" stroke="{INK}" stroke-width="1.2"/>
{head(rx=31)}
<path d="M70 96 C68 76 82 66 100 66 C118 66 132 76 130 96 C120 84 110 82 100 84 C90 82 80 84 70 96 Z" fill="#1b1310"/>
<clipPath id="face"><ellipse cx="100" cy="104" rx="31" ry="41"/></clipPath><rect x="60" y="60" width="80" height="52" fill="{INK}" opacity="0.5" clip-path="url(#face)"/>
<g><ellipse cx="88" cy="104" rx="4" ry="2" fill="{PAPER}" opacity="0.9"/><ellipse cx="112" cy="104" rx="4" ry="2" fill="{PAPER}" opacity="0.9"/>
<circle cx="89" cy="104" r="1.6" fill="{INK}"/><circle cx="113" cy="104" r="1.6" fill="{INK}"/>
<path d="M82 99 Q88 96 94 99 M106 99 Q112 96 118 99" stroke="{INK}" stroke-width="1.8" fill="none"/></g>
{nose(y=108)}
<path d="M90 126 Q95 122 100 125 Q105 122 110 126 Q100 134 90 126 Z" fill="{STAMP}" stroke="{RED}" stroke-width="0.8"/>
<circle cx="132" cy="116" r="3.2" fill="{PAPER}" stroke="{INK}" stroke-width="0.8"/>
<ellipse cx="100" cy="78" rx="78" ry="12" fill="{INK}" stroke="{SEPIA}" stroke-width="1.5"/>
<path d="M66 78 C66 48 82 36 100 36 C118 36 134 48 134 78 Z" fill="{INK}" stroke="{SEPIA}" stroke-width="1.5"/>
<path d="M67 70 C80 74 120 74 133 70 L134 78 C120 82 80 82 66 78 Z" fill="{STAMP}"/>
<g transform="translate(132 206) rotate(14)">
<rect x="0" y="0" width="40" height="24" fill="{PAPER}" stroke="{INK}"/>
<path d="M6 8 H30 M6 14 H24" stroke="{SEPIA}" stroke-width="1.5"/><circle cx="33" cy="17" r="3" fill="{STAMP}"/>
</g>
<path d="M124 216 C128 206 138 206 142 214 L140 232 C132 236 126 232 124 226 Z" fill="{SKIN}" stroke="{INK}" stroke-width="1.2"/>
<path d="M142 214 L141 220" stroke="{STAMP}" stroke-width="3" stroke-linecap="round"/>
"""

PORTRAITS = {
    "class_rep": (class_rep, "The Class Representative"),
    "ta": (ta, "The Teaching Assistant"),
    "exchange": (exchange, "The Exchange Student"),
    "professor": (professor, "The Professor"),
    "companion": (companion, "The Companion"),
}

for key, (body, title) in PORTRAITS.items():
    (OUT / f"{key}.svg").write_text(svg(key, body, title), encoding="utf-8")
print("wrote", len(PORTRAITS))
