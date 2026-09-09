# -*- coding: utf-8 -*-
"""
Generates assets/terminal.svg — the animated header for the profile README.

Boot sequence -> [ OK ] init checks -> `neofetch`, which paints an LED-matrix
banner column by column beside a system readout. CRT scanlines, phosphor glow,
vignette, blinking block cursor.

Two things learned the hard way, both encoded below:
  * The banner is SVG rects, not box-drawing glyphs. Glyph banners smear under
    the glow and drift with whatever monospace font the viewer happens to have.
  * Only the first tspan of a line gets an x. Positioning every span by
    `len * charwidth` assumes an advance ratio (0.601 was wrong; the real one
    here is ~0.55) and the error compounds into visible gaps mid-line.

Everything is timed against one 20s master loop so lines stay in sync across
repeats. Edit BOOT / INFO / WORD below and re-run:

    python assets/_terminal_generator.py
"""
import html, os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "terminal.svg")

W = 1000
TOTAL = 20000.0      # master loop, ms
BAR = 34             # title-bar height
X = 30               # left gutter
FS = 15              # body font-size
LH = 23              # body line-height
CW = FS * 0.5498     # measured advance for the declared stack

C = dict(
    bg="#04070A", edge="#163A2C",
    green="#00FF9C", dimgreen="#12805A",
    white="#E6EDF3", dim="#6E7B8B",
    amber="#FFC15E", cyan="#5BE9FF", mag="#C792EA", red="#FF5F57",
)

# ── 5x7 pixel font ──────────────────────────────────────────────────────────
G = {
    "H": ["X   X", "X   X", "X   X", "XXXXX", "X   X", "X   X", "X   X"],
    "A": [" XXX ", "X   X", "X   X", "XXXXX", "X   X", "X   X", "X   X"],
    "R": ["XXXX ", "X   X", "X   X", "XXXX ", "X  X ", "X   X", "X   X"],
    "S": [" XXXX", "X    ", "X    ", " XXX ", "    X", "    X", "XXXX "],
    "L": ["X    ", "X    ", "X    ", "X    ", "X    ", "X    ", "XXXXX"],
}
WORD = "HARSHAL"
PX, PGAP = 9, 1.5
PPITCH = PX + PGAP

# ── content ─────────────────────────────────────────────────────────────────
BOOT = [
    ("mounting /dev/models",  "PyTorch · HF · LangGraph"),
    ("uplink established",    "Funlingo · SGRAMX"),
    ("payload staged",        "52 repositories"),
]
INFO = [
    ("Role",    [("AI Engineer", C["cyan"], 700)]),
    ("Focus",   [("LLM post-training ", C["amber"], 600), ("(SFT · DPO)", C["dim"], 400)]),
    ("Systems", [("Agentic AI · RAG at scale", C["amber"], 600)]),
    ("Now",     [("SWE ", C["white"], 500), ("@Funlingo", C["green"], 700),
                 ("  ·  ", C["dim"], 400), ("AI ", C["white"], 500), ("@SGRAMX", C["green"], 700)]),
    ("Shipped", [("PRISM · AEGIS · Axiom · Groundwork", C["mag"], 600)]),
    ("Stats",   [("460", C["white"], 700), (" commits   ", C["dim"], 400),
                 ("52", C["white"], 700), (" repos   ", C["dim"], 400),
                 ("34", C["white"], 700), (" stars", C["dim"], 400)]),
]


def pct(ms):
    return round(max(0.0, min(100.0, ms / TOTAL * 100)), 3)


def esc(s):
    return html.escape(str(s), quote=False)


def spans(segs, x):
    """First span anchored; the rest flow, so no advance-ratio drift."""
    out = ['<tspan x="%d" fill="%s" font-weight="%d">%s</tspan>'
           % (x, segs[0][1], segs[0][2], esc(segs[0][0]))]
    out += ['<tspan fill="%s" font-weight="%d">%s</tspan>' % (c, f, esc(t)) for t, c, f in segs[1:]]
    return "".join(out)


css, body = [], []
css.append("text{font-family:ui-monospace,'SF Mono',SFMono-Regular,Menlo,Consolas,"
           "'DejaVu Sans Mono','Liberation Mono',monospace;white-space:pre}")
_n = [0]


def typed(y, segs, start, dur, x=X):
    i = _n[0]; _n[0] += 1
    chars = sum(len(t) for t, _, _ in segs)
    w = int(chars * CW * 1.06) + 10
    css.append("@keyframes t%d{0%%,%s%%{width:0}%s%%,100%%{width:%dpx}}"
               % (i, pct(start), pct(start + dur), w))
    css.append("#c%d rect{animation:t%d %.0fms steps(%d,end) infinite}" % (i, i, TOTAL, max(chars, 1)))
    body.append('<clipPath id="c%d"><rect x="%d" y="%.1f" width="0" height="%d"/></clipPath>'
                % (i, x, y - FS, FS + 8))
    body.append('<text y="%.1f" font-size="%d" clip-path="url(#c%d)">%s</text>'
                % (y, FS, i, spans(segs, x)))


def appear(y, segs, at, x=X, size=FS):
    i = _n[0]; _n[0] += 1
    css.append("@keyframes a%d{0%%,%s%%{opacity:0}%s%%,100%%{opacity:1}}" % (i, pct(at), pct(at + 1)))
    css.append("#a%d{animation:a%d %.0fms linear infinite}" % (i, i, TOTAL))
    body.append('<text id="a%d" y="%.1f" font-size="%d">%s</text>' % (i, y, size, spans(segs, x)))


# ── timeline ────────────────────────────────────────────────────────────────
t, y = 250, BAR + 30

typed(y, [("┌─[", C["dimgreen"], 400), ("harshal@github", C["green"], 700),
          ("]─[", C["dimgreen"], 400), ("~/portfolio", C["cyan"], 500),
          ("]", C["dimgreen"], 400)], t, 650)
t += 750; y += LH
typed(y, [("└─$ ", C["dimgreen"], 400), ("./init.sh --profile", C["white"], 500)], t, 700)
t += 900; y += LH + 4

for label, val in BOOT:
    appear(y, [("[ ", C["dim"], 400), ("OK", C["green"], 700), (" ]  ", C["dim"], 400),
               (label.ljust(24), C["white"], 400),
               ("." * 12 + "  ", C["dimgreen"], 400), (val, C["amber"], 600)], t)
    t += 330; y += LH

t += 250; y += LH - 2
typed(y, [("└─$ ", C["dimgreen"], 400), ("neofetch", C["white"], 500)], t, 500)
t += 700; y += 22

# ── neofetch block: LED banner left, system readout right ───────────────────
BAN_Y = y
cols = [(gi * 6 + cx, [ry for ry in range(7) if G[ch][ry][cx] == "X"])
        for gi, ch in enumerate(WORD) for cx in range(5)]
BAN_MS, px_body = 800, []
for ci, (colx, rows) in enumerate(cols):
    if not rows:
        continue
    at = t + ci * (BAN_MS / len(cols))
    css.append("@keyframes g%d{0%%,%s%%{opacity:0}%s%%,100%%{opacity:1}}" % (ci, pct(at), pct(at + 60)))
    css.append("#g%d{animation:g%d %.0fms linear infinite}" % (ci, ci, TOTAL))
    px_body.append('<g id="g%d">%s</g>' % (ci, "".join(
        '<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="1.5"/>'
        % (X + 2 + colx * PPITCH, BAN_Y + ry * PPITCH, PX, PX) for ry in rows)))
body.append('<g class="glow" fill="%s">%s</g>' % (C["green"], "".join(px_body)))
BAN_W = (max(c for c, _ in cols) + 1) * PPITCH

IX = X + 2 + BAN_W + 44          # readout column
ty = BAN_Y + FS - 1
t2 = t + 420
appear(ty, [("root", C["green"], 700), ("@", C["dim"], 400), ("harshal", C["cyan"], 700)], t2, x=IX)
ty += 18
body.append('<rect x="%d" y="%.1f" width="%d" height="1" fill="%s" opacity=".5"/>'
            % (IX, ty, W - IX - X, C["edge"]))
ty += 20
for k, segs in INFO:
    t2 += 190
    appear(ty, [(k.ljust(9), C["dimgreen"], 600)] + segs, t2, x=IX)
    ty += LH

y = max(BAN_Y + 7 * PPITCH, ty - LH) + 34
t = max(t + BAN_MS, t2) + 500

# ── final prompt ────────────────────────────────────────────────────────────
appear(y, [("root", C["green"], 700), ("@", C["dim"], 400), ("harshal", C["cyan"], 700),
           (":", C["dim"], 400), ("~", C["mag"], 700), ("# ", C["dim"], 400)], t, x=X)
css.append("@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}")
css.append("@keyframes cur{0%%,%s%%{opacity:0}%s%%,100%%{opacity:1}}" % (pct(t), pct(t + 1)))
css.append("#cur{animation:blink 1.05s steps(1,end) infinite,cur %.0fms linear infinite}" % TOTAL)
css.append(".glow{filter:url(#phosphor)}")
css.append("@media (prefers-reduced-motion:reduce){*{animation:none!important}"
           "[id^=c] rect{width:100%!important}[id^=a],[id^=g]{opacity:1!important}}")

H = int(y + 30)
CURX = X + 15 * CW

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Harshal Andhale — AI Engineer. LLM post-training (SFT, DPO), agentic AI and RAG at scale. SWE intern at Funlingo, AI intern at SGRAMX. Projects: PRISM, AEGIS, Axiom, Groundwork. 460 commits, 52 repositories, 34 stars.">
<style>{"".join(css)}</style>
<defs>
  <filter id="phosphor" x="-20%" y="-20%" width="140%" height="140%">
    <feGaussianBlur stdDeviation="3" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <linearGradient id="glowbar" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#00FF9C"/><stop offset=".5" stop-color="#5BE9FF"/><stop offset="1" stop-color="#C792EA"/>
  </linearGradient>
  <linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#0E1620"/><stop offset="1" stop-color="#04070A"/>
  </linearGradient>
  <radialGradient id="vig" cx="50%" cy="45%" r="78%">
    <stop offset="55%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity=".5"/>
  </radialGradient>
  <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">
    <rect width="4" height="1.4" fill="#00FF9C" opacity=".04"/>
  </pattern>
</defs>

<rect width="{W}" height="{H}" rx="10" fill="{C['bg']}" stroke="{C['edge']}"/>
<path d="M10 0h{W-20}a10 10 0 0 1 10 10v{BAR-10}H0V10A10 10 0 0 1 10 0z" fill="url(#fade)"/>
<rect y="{BAR-1}" width="{W}" height="1" fill="{C['edge']}"/>
<circle cx="22" cy="{BAR//2}" r="5" fill="{C['red']}"/><circle cx="40" cy="{BAR//2}" r="5" fill="#FEBC2E"/><circle cx="58" cy="{BAR//2}" r="5" fill="#28C840"/>
<text x="{W//2}" y="{BAR//2+4}" text-anchor="middle" fill="{C['dimgreen']}" font-size="12" font-family="ui-monospace,Menlo,Consolas,monospace">root@harshal — /bin/zsh — 80×24</text>

{chr(10).join(body)}
<rect id="cur" x="{CURX:.1f}" y="{y-FS+2:.1f}" width="{CW:.1f}" height="{FS}" fill="{C['green']}"/>

<rect y="{BAR}" width="{W}" height="{H-BAR}" fill="url(#scan)" pointer-events="none"/>
<rect width="{W}" height="{H}" rx="10" fill="url(#vig)" pointer-events="none"/>
<rect x="0" y="{H-3}" width="{W}" height="3" fill="url(#glowbar)" opacity=".9"/>
</svg>'''

open(OUT, "w", encoding="utf-8").write(svg)
print(f"wrote {OUT}  ({W}x{H})  loop {TOTAL/1000:.0f}s  banner={WORD} ({BAN_W:.0f}px)")