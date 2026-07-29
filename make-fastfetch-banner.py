#!/usr/bin/env python3
"""Render a fastfetch-style banner for a GitHub profile README: an ASCII-art
portrait beside a personal "system info" block, drawn as a terminal window.

    python3 make-fastfetch-banner.py --src path/to/headshot.jpg --out .

Writes next to --out:
  fastfetch.png    wide terminal banner, sized 2x for a ~880px README column
  fastfetch.svg    same banner as vector text, crisp at any size
  fastfetch.txt    same banner as plain text, for embedding in a README code fence
  avatar.jpg       plain square headshot crop, for the profile picture itself
  avatar-ascii.png the same square crop through the ASCII-art pipeline

Needs Pillow and Source Code Pro. Edit FIELDS to change the info block; edit
PORTRAIT_CROP / AVATAR_CROP if you swap in a different headshot.
"""
import argparse, hashlib, os, pickle, tempfile
from collections import deque
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops, ImageEnhance

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.path.join(HERE, "headshot.jpg")

FONT_DIRS = [HERE, "/usr/share/fonts", "/usr/local/share/fonts", "/Library/Fonts",
             os.path.expanduser("~/.local/share/fonts"), os.path.expanduser("~/.fonts"),
             r"C:\Windows\Fonts"]

def find_font(name):
    """Locate a font file by name; Source Code Pro lives in a different
    directory on every distro, so search rather than hardcode a path."""
    for root in FONT_DIRS:
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            if name in files:
                return os.path.join(dirpath, name)
    raise SystemExit(f"Could not find {name}. Install Source Code Pro "
                     "(Fedora: sudo dnf install adobe-source-code-pro-fonts; "
                     "Debian/Ubuntu: sudo apt install fonts-source-code-pro), "
                     f"or drop the .otf next to {os.path.basename(__file__)}.")

FONT_R = find_font("SourceCodePro-Regular.otf")
FONT_B = find_font("SourceCodePro-Bold.otf")

ap = argparse.ArgumentParser()
ap.add_argument("--src", default=DEFAULT_SRC, help="source headshot")
ap.add_argument("--out", default=".", help="output directory")
ap.add_argument("--cache", default=None, help="dir for the background-mask cache (default: temp)")
ARGS = ap.parse_args()
SRC = ARGS.src
if not os.path.exists(SRC):
    raise SystemExit(f"Headshot not found: {SRC}\nPass one with --src path/to/headshot.jpg")
OUTDIR = os.path.abspath(ARGS.out)
SP  = ARGS.cache or os.path.join(tempfile.gettempdir(), "fastfetch-mask-cache")
os.makedirs(SP, exist_ok=True)
with open(SRC, "rb") as _f:
    SRC_HASH = hashlib.sha256(_f.read()).hexdigest()[:16]
from collections import deque



def subject(box, K=8, mw=340, protect=0.80):
    """Return (crop, mask) with the bokeh background removed."""
    cache = f"{SP}/cache_{SRC_HASH}_{'_'.join(map(str, box))}_{K}_{protect}.pkl"
    if os.path.exists(cache):
        with open(cache, "rb") as f: return pickle.load(f)
    crop = Image.open(SRC).convert("RGB").crop(box)
    MW = mw; MH = int(crop.height*MW/crop.width); N = MW*MH
    small = crop.resize((MW, MH), Image.LANCZOS)
    h, s, v = small.convert("HSV").split()
    H, S, V = map(lambda c: list(c.get_flattened_data()), (h, s, v))
    g = small.convert("L")
    D = list(ImageChops.difference(g, g.filter(ImageFilter.GaussianBlur(2.5)))
             .filter(ImageFilter.GaussianBlur(1.5)).get_flattened_data())
    PY_ = int(protect*MH) if protect else MH + 1
    def prot(i): return (i//MW) >= PY_
    def skin(i): return 3 <= H[i] <= 24 and S[i] >= 45
    def strict(i):
        if prot(i): return False
        if 25 <= H[i] <= 95 and S[i] >= 70 and V[i] >= 60: return True
        if 18 <= H[i] <= 100 and S[i] >= 45 and V[i] >= 90 and D[i] <= 4: return True
        if V[i] >= 165 and D[i] <= 4 and not skin(i): return True
        return False
    def loose(i):
        if prot(i): return False
        if 15 <= H[i] <= 110 and S[i] >= 30 and V[i] >= 40: return True
        if V[i] >= 140 and D[i] <= 7: return True
        return False
    st = [strict(i) for i in range(N)]; lo = [loose(i) for i in range(N)]
    border = [y*MW+x for x in range(MW) for y in (0, MH-1)] + [y*MW+x for y in range(MH) for x in (0, MW-1)]
    INF = 99; dist = [INF]*N; dq = deque()
    for i in border:
        if st[i] and dist[i]: dist[i] = 0; dq.appendleft(i)
    while dq:
        i = dq.popleft(); d = dist[i]; x, y = i % MW, i // MW
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = x+dx, y+dy
            if not (0 <= nx < MW and 0 <= ny < MH): continue
            j = ny*MW+nx
            if st[j]: nd = d
            elif lo[j]: nd = d+1
            else: continue
            if nd <= K and nd < dist[j]:
                dist[j] = nd; (dq.appendleft if nd == d else dq.append)(j)
    subj = [0 if d < INF else 1 for d in dist]
    best, seen = None, [0]*N
    for start in range(N):
        if subj[start] and not seen[start]:
            comp, q = [], deque([start]); seen[start] = 1
            while q:
                i = q.popleft(); comp.append(i); x, y = i % MW, i // MW
                for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    nx, ny = x+dx, y+dy
                    if 0 <= nx < MW and 0 <= ny < MH:
                        j = ny*MW+nx
                        if subj[j] and not seen[j]: seen[j] = 1; q.append(j)
            if best is None or len(comp) > len(best): best = comp
    keep = [0]*N
    for i in best: keep[i] = 255
    m = Image.new("L", (MW, MH)); m.putdata(keep)
    # A radius-1 closing only bridges ~1px gaps -- too weak for a bright,
    # overexposed skin highlight (e.g. forehead glare) that the HSV+D
    # classifiers above mistake for smooth out-of-focus background: that
    # misclassification bites a real notch into the silhouette, connected
    # all the way out to the border, not just a few stray pixels. A much
    # larger closing radius bridges that notch shut while barely moving the
    # true (already-smooth) silhouette edge elsewhere.
    m = m.filter(ImageFilter.MaxFilter(31)).filter(ImageFilter.MinFilter(31)).filter(ImageFilter.GaussianBlur(1.2))
    out = (crop, m.resize(crop.size, Image.LANCZOS))
    with open(cache, "wb") as f: pickle.dump(out, f)
    return out

# ---- glyph ramps, measured from the actual font ----
ASCII_SET = " .'`,^:;~-_+=<>i!lI?/\\|()[]{}rcvunxzjftLCJUYXZOQ0mwqpdbkhao*#MW&8%B@$"
def ramps(cw, ch, fs):
    font = ImageFont.truetype(FONT_R, fs); asc = font.getmetrics()[0]
    def cov(c):
        im = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(im).text((cw/2, asc), c, font=font, fill=255, anchor="ms")
        return sum(im.get_flattened_data())/(255.0*cw*ch)
    a = sorted({c: cov(c) for c in ASCII_SET}.items(), key=lambda kv: kv[1])
    ev = lambda n: [min(a, key=lambda kv: abs(kv[1]-a[-1][1]*k/(n-1)))[0] for k in range(n)]
    return ev(16), ev(14) + ["░", "▒", "▓", "█"]

def tone_lut(gray, mask, head_frac=0.62, plo=0.04, phi=0.95, gamma=0.9):
    """Percentile stretch driven by the HEAD region so the face keeps its range."""
    W, H = gray.size
    cut = int(H*head_frac)*W
    g = list(gray.get_flattened_data()); m = list(mask.get_flattened_data())
    vals = sorted(g[i] for i in range(cut) if m[i] >= 128)
    lo, hi = vals[int(len(vals)*plo)], vals[int(len(vals)*phi)]
    return [max(0, min(255, int((max(0.0, (i-lo)/max(1, hi-lo))**gamma)*255))) for i in range(256)], lo, hi




# ---------------- geometry: sized 2x for a ~880px README column ----------------
CW, CH, FS = 15, 31, 25
COLS, ROWS = 158, 62
PAD_X, PAD_Y, TITLEBAR, MARGIN = 30, 26, 46, 22
PORTRAIT_CROP = (272, 26, 736, 600)      # head, neck and collar
AVATAR_CROP   = (190, 20, 810, 640)      # square head-and-shoulders
PW, P_COL, P_ROW = 92, 1, 4              # ASCII portrait: columns and origin
IC, LABW = 98, 13                        # info block: column and label width
USER = "kwaba@fedora"                    # shell user@host, also fastfetch's title line
CWD  = "~/Documents/ganji759"

FIELDS = [
    ("Name",       "Pacifique Mugisho"),
    ("Role",       "AI/ML Engineer @ NEOTEX.ai (Brussels, remote)"),
    ("Ambassador", "PyTorch · Linux Foundation"),
    ("Location",   "Kampala, Uganda (EAT)"),
    ("Education",  "BSc Mechanical Engineering (Distinction)"),
    None,
    ("Focus",      "Multi-agent LLM systems · Computer Vision"),
    ("",           "Geospatial ML · Physics-Informed NNs"),
    None,
    ("Languages",  "Python · JavaScript · C/C++ · MATLAB"),
    ("ML",         "PyTorch · ExecuTorch · LangGraph · vLLM"),
    ("",           "Transformers · RAG · Hugging Face"),
    ("Frameworks", "FastAPI · Next.js · React · Node.js"),
    ("Cloud",      "Docker · GCP · AWS · Azure · Kubernetes"),
    ("Data",       "MongoDB Atlas · Vector Search"),
    None,
    ("Projects",   "HERON · Shamba AI · Flood Prediction ML"),
    ("Research",   "Thermoacoustic Refrigeration (2025)"),
    ("Community",  "Organiser, Deep Learning IndabaX DRC"),
    None,
    ("GitHub",     "github.com/ganji759"),
    ("Email",      "pacymugisho@gmail.com"),
]

# ---------------- palette: the portfolio's own tokens ----------------
BG, BAR, LINE = (15,19,23), (27,35,43), (42,52,62)
TEXT, MUTED   = (233,230,223), (152,162,171)
ACCENT, GREEN = (236,163,95), (127,168,139)
BLUE, RED, YEL= (122,165,196), (204,75,63), (224,164,60)
ANSI_N = [(27,35,43), RED, GREEN, YEL, (91,135,168), (160,127,168), (95,168,160), MUTED]
ANSI_B = [LINE, (224,101,90), (158,196,168), ACCENT, BLUE, (187,154,196), (127,196,188), TEXT]

TEXT_W, TEXT_H = COLS*CW, ROWS*CH
WIN_W, WIN_H = TEXT_W + 2*PAD_X, TEXT_H + TITLEBAR + 2*PAD_Y
CAN_W, CAN_H = WIN_W + 2*MARGIN, WIN_H + 2*MARGIN
MX, MY = MARGIN, MARGIN

font  = ImageFont.truetype(FONT_R, FS)
fontb = ImageFont.truetype(FONT_B, FS)
ASC   = font.getmetrics()[0]
tfont = ImageFont.truetype(FONT_R, 22)

# Recorded alongside the PIL drawing calls below so the SVG export (further down)
# can reproduce the exact same grid without redoing any pixel analysis: each
# entry is one visible glyph as (row, col, char, rgb_fill, bold).
CELLS = []
CURSORS = []  # (row, col) grid position of each blinking-cursor block

def qcolor(c, step=8):
    """Round an RGB tuple to a coarser grid so adjacent near-identical portrait
    pixels collapse into the same SVG <tspan> run instead of each getting one."""
    return tuple(min(255, ((int(v) + step//2)//step)*step) for v in c)

img = Image.new("RGB", (CAN_W, CAN_H), (8,10,13)); d = ImageDraw.Draw(img)
d.rounded_rectangle([MX, MY, MX+WIN_W-1, MY+WIN_H-1], radius=16, fill=BG, outline=LINE, width=1)
d.rounded_rectangle([MX, MY, MX+WIN_W-1, MY+TITLEBAR+16], radius=16, fill=BAR)
d.rectangle([MX, MY+TITLEBAR-1, MX+WIN_W-1, MY+TITLEBAR-1], fill=LINE)
for i, c in enumerate((RED, YEL, GREEN)):
    cx = MX + 26 + i*24
    d.ellipse([cx-7, MY+TITLEBAR//2-7, cx+7, MY+TITLEBAR//2+7], fill=c)
d.text((MX+WIN_W//2, MY+TITLEBAR//2), f"{USER}: {CWD}", font=tfont, fill=MUTED, anchor="mm")

OX, OY = MX+PAD_X, MY+TITLEBAR+PAD_Y
def put(col, row, text, fill=TEXT, bold=False):
    f = fontb if bold else font
    for k, c in enumerate(text):
        # Always record into CELLS, even spaces: drawing a space glyph is a
        # no-op for the PNG, but CELLS is the only data source for the SVG
        # export -- skipping spaces there means the SVG's <tspan> text joins
        # words together (e.g. "Pacifique Mugisho" -> "PacifiqueMugisho")
        # even though each glyph still gets its own correct x.
        d.text((OX+(col+k)*CW+CW/2, OY+row*CH+ASC), c, font=f, fill=fill, anchor="ms")
        CELLS.append((row, col+k, c, fill, bold))

def prompt(row, cmd=None, cursor=False):
    c = 1
    put(c, row, USER, GREEN, bold=True); c += len(USER)
    put(c, row, ":", MUTED); c += 1
    put(c, row, CWD, BLUE, bold=True); c += len(CWD)
    put(c, row, "$", MUTED); c += 2
    if cmd: put(c, row, cmd, TEXT); c += len(cmd) + 1
    if cursor:
        d.rectangle([OX+c*CW, OY+row*CH+4, OX+c*CW+CW-3, OY+row*CH+CH-4], fill=ACCENT)
        CURSORS.append((row, c))

# ---------------- ASCII-art rendering pipeline (shared by the banner portrait and the standalone avatar) ----------------

# The full printable-ASCII density ramp: every one of the 95 printable ASCII
# characters, in both regular and bold weight (~190 distinct glyphs total),
# sorted by their actual measured ink coverage in this font at this cell
# size. A smaller curated ramp reads as smoother/more photo-like, but the
# dense full ramp -- deliberately leaning into per-glyph shape jitter as
# texture rather than smoothing it away -- is the intended look here.
def _full_ascii_ramp():
    chars = [chr(c) for c in range(0x20, 0x7f)]
    fr, fb = ImageFont.truetype(FONT_R, FS), ImageFont.truetype(FONT_B, FS)
    ar, ab = fr.getmetrics()[0], fb.getmetrics()[0]
    def cov(c, f, a):
        im = Image.new("L", (CW, CH), 0)
        ImageDraw.Draw(im).text((CW/2, a), c, font=f, fill=255, anchor="ms")
        return sum(im.get_flattened_data())/(255.0*CW*CH)
    glyphs = [((c, False), cov(c, fr, ar)) for c in chars] + [((c, True), cov(c, fb, ab)) for c in chars]
    return [g for g, _ in sorted(glyphs, key=lambda kv: kv[1])]
RAMP = _full_ascii_ramp()

def ascii_grid(crop_box, cols):
    """Run subject()+tone_lut()+RAMP+dithering over crop_box laid out `cols`
    characters wide. Returns (rows, IDX, C, M): IDX[i] indexes into RAMP,
    C[i] is the enhanced RGB for that cell, M[i]<40 means no glyph (outside
    the subject mask)."""
    crop, mask = subject(crop_box, protect=None)
    rows = round(cols*(crop.height/crop.width)*(CW/CH))

    sub = Image.new("RGB", crop.size, (0,0,0)); sub.paste(crop, (0,0), mask)
    sub = sub.filter(ImageFilter.GaussianBlur(2))
    sub.paste(Image.new("RGB", crop.size, (0,0,0)), (0,0), mask.point(lambda v: 255-v))

    # A light FIND_EDGES blend restores crisp hair/brow/jaw boundaries that the
    # smoothing blur above softens, without reintroducing pore/blemish noise.
    gray0 = sub.convert("L")
    edges = gray0.filter(ImageFilter.FIND_EDGES)
    gray = Image.blend(gray0, edges, 0.18)

    # Gamma adapts to the head's own mean brightness so both dark and light skin
    # tones land in the RAMP's visible range instead of one fixed curve favoring
    # whichever tone it was tuned on.
    gv, mv = list(gray.get_flattened_data()), list(mask.get_flattened_data())
    head_px = [v for v, m in zip(gv, mv) if m >= 128]
    head_mean = sum(head_px)/max(1, len(head_px))
    gamma = 0.75 if head_mean < 90 else 1.15 if head_mean > 170 else 0.95

    lut, _, _ = tone_lut(gray, mask, head_frac=0.70, plo=0.02, phi=0.95, gamma=gamma)
    L = list(gray.point(lut).resize((cols, rows), Image.LANCZOS).get_flattened_data())
    C = list(ImageEnhance.Color(sub.resize((cols, rows), Image.LANCZOS)).enhance(1.25).get_flattened_data())
    M = list(mask.resize((cols, rows), Image.LANCZOS).get_flattened_data())

    # Floyd-Steinberg error diffusion: quantizing each cell to its nearest RAMP
    # level independently leaves visible banding; diffusing the rounding error
    # into not-yet-visited neighbors trades banding for a much smoother gradient
    # -- the same trick dithered image formats use. Error never crosses the
    # mask boundary, so it can't drag stray marks out into empty background.
    levels = [i*255/(len(RAMP)-1) for i in range(len(RAMP))]
    def nearest_level(v):
        return min(range(len(levels)), key=lambda k: abs(levels[k]-v))
    err = [0.0]*(cols*rows)
    IDX = [0]*(cols*rows)
    for y in range(rows):
        for x in range(cols):
            i = y*cols+x
            if M[i] < 40: continue
            v = max(0.0, min(255.0, L[i]+err[i]))
            k = nearest_level(v)
            IDX[i] = k
            e = v - levels[k]
            if x+1 < cols and M[i+1] >= 40: err[i+1] += e*7/16
            if y+1 < rows:
                if x > 0 and M[i+cols-1] >= 40: err[i+cols-1] += e*3/16
                if M[i+cols] >= 40: err[i+cols] += e*5/16
                if x+1 < cols and M[i+cols+1] >= 40: err[i+cols+1] += e*1/16
    return rows, IDX, C, M

def ramp_color(k, rgb):
    r, g, b = rgb; mx = max(r, g, b, 1)
    col = tuple(min(255, int(v*min(1.45, 205/mx))) for v in (r, g, b))
    lum = k/(len(RAMP)-1)
    col = tuple(int(v*(0.6+0.4*lum)) for v in col)          # highlights stay bright, shadows keep some color
    col = tuple(min(255, round(v/16)*16) for v in col)       # ANSI-ish quantization instead of a smooth photo gradient
    return col

# ---------------- ASCII portrait (banner) ----------------
PH, IDX, C, M = ascii_grid(PORTRAIT_CROP, PW)
for i, k in enumerate(IDX):
    if M[i] < 40: continue
    c, glyph_bold = RAMP[k]
    if c == " ": continue
    col = ramp_color(k, C[i])
    pcol, prow = P_COL+i%PW, P_ROW+i//PW
    d.text((OX+pcol*CW+CW/2, OY+prow*CH+ASC), c, font=(fontb if glyph_bold else font), fill=col, anchor="ms")
    CELLS.append((prow, pcol, c, qcolor(col), glyph_bold))

# ---------------- info block ----------------
info_h = 2 + 1 + len(FIELDS) + 1 + 2
IR = P_ROW + (PH - info_h)//2
put(IC, IR, USER, GREEN, bold=True)
put(IC, IR+1, "─"*len(USER), LINE)
r = IR + 3
for f in FIELDS:
    if f is None: r += 1; continue
    lab, val = f
    if lab: put(IC, r, lab, ACCENT, bold=True)
    put(IC+LABW, r, val, TEXT if lab else MUTED)
    r += 1
r += 1
for k, row in enumerate((ANSI_N, ANSI_B)):
    for j, c in enumerate(row):
        x0 = OX + (IC+j*4)*CW
        d.rectangle([x0, OY+(r+k)*CH+3, x0+4*CW-4, OY+(r+k)*CH+CH-4], fill=c)

prompt(1, "fastfetch")
prompt(P_ROW + PH + 2, cursor=True)

banner = os.path.join(OUTDIR, "fastfetch.png")
img.save(banner)

# ---------------- SVG export ----------------
# Same banner, but every glyph is a real <text>/<tspan> instead of a PIL glyph
# rasterized into a 15x31px cell. Vector text stays crisp at any render size
# instead of baking small glyphs into a fixed-resolution raster. None of the
# analysis changes here -- CELLS/CURSORS just record the same (row, col,
# char, color) decisions already made above.

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def hx(c):
    return "#%02x%02x%02x" % tuple(int(v) for v in c)

_GLYPH_W = {}
def glyph_width(ch, bold):
    key = (ch, bold)
    if key not in _GLYPH_W:
        _GLYPH_W[key] = d.textlength(ch, font=fontb if bold else font)
    return _GLYPH_W[key]

def svg_row(row_no, cells):
    """One <text> per grid row; same-color runs share a <tspan> with an
    explicit per-character x list, so glyphs stay grid-aligned regardless of
    the viewer's actual monospace font metrics, and colors change without
    needing a separate <text> per glyph. x is each glyph's own left edge
    (cell center minus half its measured width) with the default
    text-anchor="start" -- NOT text-anchor="middle" with a shared x list,
    which different SVG renderers resolve inconsistently (some center each
    character on its listed x, some don't), producing the left-shifted
    characters this was fixed for. Left-edge positioning has no such
    ambiguity: every renderer places character N's origin at xs[N], full stop."""
    cells = sorted(cells, key=lambda t: t[0])
    baseline = OY + row_no*CH + ASC
    parts = [f'<text y="{baseline}" font-size="{FS}" xml:space="preserve">']
    run_fill, run_bold, xs, chars = None, None, [], []
    def flush():
        if chars:
            weight = ' font-weight="bold"' if run_bold else ""
            parts.append(f'<tspan x="{" ".join(xs)}" fill="{hx(run_fill)}"{weight}>{esc("".join(chars))}</tspan>')
    for cell_col, ch, fill, bold in cells:
        if fill != run_fill or bold != run_bold:
            flush(); xs, chars = [], []
            run_fill, run_bold = fill, bold
        cell_center = OX + cell_col*CW + CW/2
        xs.append(str(round(cell_center - glyph_width(ch, bold)/2)))
        chars.append(ch)
    flush()
    parts.append("</text>")
    return "".join(parts)

svg = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{CAN_W}" height="{CAN_H}" '
    f'viewBox="0 0 {CAN_W} {CAN_H}" font-family="\'Source Code Pro\', monospace">',
    f'<rect width="{CAN_W}" height="{CAN_H}" fill="{hx((8,10,13))}"/>',
    f'<rect x="{MX}" y="{MY}" width="{WIN_W}" height="{WIN_H}" rx="16" ry="16" '
    f'fill="{hx(BG)}" stroke="{hx(LINE)}" stroke-width="1"/>',
    f'<rect x="{MX}" y="{MY}" width="{WIN_W}" height="{TITLEBAR+16}" rx="16" ry="16" fill="{hx(BAR)}"/>',
    f'<rect x="{MX}" y="{MY+TITLEBAR-1}" width="{WIN_W}" height="1" fill="{hx(LINE)}"/>',
]
for dot_i, dot_c in enumerate((RED, YEL, GREEN)):
    dot_cx = MX + 26 + dot_i*24
    svg.append(f'<circle cx="{dot_cx}" cy="{MY+TITLEBAR//2}" r="7.5" fill="{hx(dot_c)}"/>')
svg.append(
    f'<text x="{MX+WIN_W//2}" y="{MY+TITLEBAR//2}" text-anchor="middle" dominant-baseline="central" '
    f'font-size="22" fill="{hx(MUTED)}">{esc(f"{USER}: {CWD}")}</text>'
)

svg_rows = {}
for cell_row, cell_col, ch, fill, bold in CELLS:
    svg_rows.setdefault(cell_row, []).append((cell_col, ch, fill, bold))
for row_no in sorted(svg_rows):
    svg.append(svg_row(row_no, svg_rows[row_no]))

for swatch_k, swatch_row in enumerate((ANSI_N, ANSI_B)):
    for swatch_j, swatch_c in enumerate(swatch_row):
        sx0 = OX + (IC+swatch_j*4)*CW
        sy0 = OY + (r+swatch_k)*CH + 3
        svg.append(f'<rect x="{sx0}" y="{sy0}" width="{4*CW-3}" height="{CH-6}" fill="{hx(swatch_c)}"/>')

for cur_row, cur_col in CURSORS:
    cx0 = OX + cur_col*CW
    cy0 = OY + cur_row*CH + 4
    svg.append(f'<rect x="{cx0}" y="{cy0}" width="{CW-2}" height="{CH-7}" fill="{hx(ACCENT)}"/>')

svg.append("</svg>")
svg_path = os.path.join(OUTDIR, "fastfetch.svg")
with open(svg_path, "w", encoding="utf-8") as f:
    f.write("".join(svg))

# ---------------- plain-text export (no color, drops straight into a README code fence) ----------------
maxrow = max(cr for cr, *_ in CELLS) + 1
maxcol = max(cc for _, cc, *_ in CELLS) + 1
grid = [[" "]*maxcol for _ in range(maxrow)]
for cr, cc, ch, _fill, _bold in CELLS:
    grid[cr][cc] = ch
text_lines = ["".join(row).rstrip() for row in grid]
while text_lines and not text_lines[-1]:
    text_lines.pop()
txt_path = os.path.join(OUTDIR, "fastfetch.txt")
with open(txt_path, "w", encoding="utf-8") as f:
    f.write("\n".join(text_lines) + "\n")

# ---------------- plain avatar crop ----------------
av = Image.open(SRC).convert("RGB").crop(AVATAR_CROP).resize((1000, 1000), Image.LANCZOS)
avatar = os.path.join(OUTDIR, "avatar.jpg")   # JPEG: a photo as PNG runs ~900KB, near GitHub's 1MB cap
av.save(avatar, quality=92, subsampling=0, optimize=True)

# ---------------- ASCII-art avatar (same pipeline as the banner portrait, square crop, no window chrome) ----------------
AV_COLS = 100
av_rows, av_IDX, av_C, av_M = ascii_grid(AVATAR_CROP, AV_COLS)
av_ascii = Image.new("RGB", (AV_COLS*CW, av_rows*CH), (8,10,13))
av_ascii_d = ImageDraw.Draw(av_ascii)
for i, k in enumerate(av_IDX):
    if av_M[i] < 40: continue
    c, glyph_bold = RAMP[k]
    if c == " ": continue
    col = ramp_color(k, av_C[i])
    acol, arow = i % AV_COLS, i // AV_COLS
    av_ascii_d.text((acol*CW+CW/2, arow*CH+ASC), c, font=(fontb if glyph_bold else font), fill=col, anchor="ms")
avatar_ascii_path = os.path.join(OUTDIR, "avatar-ascii.png")
av_ascii.save(avatar_ascii_path)

print(f"banner {img.size} portrait {PW}x{PH} rows {P_ROW}-{P_ROW+PH-1} info {IR}-{r+1}"
      f"  {os.path.getsize(banner)//1024}KB")
print(f"svg {CAN_W}x{CAN_H}  {os.path.getsize(svg_path)//1024}KB  -> {svg_path}")
print(f"txt {maxcol}x{len(text_lines)}  {os.path.getsize(txt_path)} bytes -> {txt_path}")
print(f"avatar {av.size}  {os.path.getsize(avatar)//1024}KB")
print(f"avatar-ascii {av_ascii.size}  {os.path.getsize(avatar_ascii_path)//1024}KB -> {avatar_ascii_path}")
