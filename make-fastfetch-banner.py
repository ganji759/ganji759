#!/usr/bin/env python3
"""Render a fastfetch-style banner for a GitHub profile README: an ASCII-art
portrait beside a personal "system info" block, drawn as a terminal window.

    python3 make-fastfetch-banner.py --src path/to/headshot.jpg --out .

Writes two files next to --out:
  fastfetch.png  wide terminal banner, sized 2x for a ~880px README column
  avatar.jpg     plain square headshot crop, for the profile picture itself

Needs Pillow and Source Code Pro. Edit FIELDS to change the info block; edit
PORTRAIT_CROP / AVATAR_CROP if you swap in a different headshot.
"""
import argparse, os, pickle, tempfile
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
from collections import deque



def subject(box, K=8, mw=340, protect=0.80):
    """Return (crop, mask) with the bokeh background removed."""
    cache = f"{SP}/cache_{'_'.join(map(str, box))}_{K}_{protect}.pkl"
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
    m = m.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
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

def tone_lut(gray, mask, head_frac=0.62, plo=0.04, phi=0.96, gamma=0.88):
    """Percentile stretch driven by the HEAD region so the face keeps its range."""
    W, H = gray.size
    cut = int(H*head_frac)*W
    g = list(gray.get_flattened_data()); m = list(mask.get_flattened_data())
    vals = sorted(g[i] for i in range(cut) if m[i] >= 128)
    lo, hi = vals[int(len(vals)*plo)], vals[int(len(vals)*phi)]
    return [max(0, min(255, int((max(0.0, (i-lo)/max(1, hi-lo))**gamma)*255))) for i in range(256)], lo, hi




# ---------------- geometry: sized 2x for a ~880px README column ----------------
CW, CH, FS = 15, 31, 25
COLS, ROWS = 120, 43
PAD_X, PAD_Y, TITLEBAR, MARGIN = 30, 26, 46, 22
PORTRAIT_CROP = (272, 26, 736, 600)      # head, neck and collar
AVATAR_CROP   = (190, 20, 810, 640)      # square head-and-shoulders
PW, P_COL, P_ROW = 58, 1, 4              # ASCII portrait: columns and origin
IC, LABW = 62, 13                        # info block: column and label width
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
        if c != " ":
            d.text((OX+(col+k)*CW+CW/2, OY+row*CH+ASC), c, font=f, fill=fill, anchor="ms")

def prompt(row, cmd=None, cursor=False):
    c = 1
    put(c, row, USER, GREEN, bold=True); c += len(USER)
    put(c, row, ":", MUTED); c += 1
    put(c, row, CWD, BLUE, bold=True); c += len(CWD)
    put(c, row, "$", MUTED); c += 2
    if cmd: put(c, row, cmd, TEXT); c += len(cmd) + 1
    if cursor: d.rectangle([OX+c*CW, OY+row*CH+4, OX+c*CW+CW-3, OY+row*CH+CH-4], fill=ACCENT)

# ---------------- ASCII portrait ----------------
crop, mask = subject(PORTRAIT_CROP, protect=None)
PH = round(PW*(crop.height/crop.width)*(CW/CH))
def _cov(c):
    im = Image.new("L", (CW, CH), 0)
    ImageDraw.Draw(im).text((CW/2, ASC), c, font=font, fill=255, anchor="ms")
    return sum(im.get_flattened_data())/(255.0*CW*CH)
A = sorted({c: _cov(c) for c in ASCII_SET}.items(), key=lambda kv: kv[1]); amax = A[-1][1]
span = lambda n, f0, f1: [min(A, key=lambda kv: abs(kv[1]-amax*(f0+(f1-f0)*k/(n-1))))[0] for k in range(n)]
RAMP = [" ", "."] + span(10, 0.42, 1.0) + ["░","▒","▓","█"]

sub = Image.new("RGB", crop.size, (0,0,0)); sub.paste(crop, (0,0), mask)
sub = sub.filter(ImageFilter.UnsharpMask(radius=4, percent=180, threshold=2))
sub.paste(Image.new("RGB", crop.size, (0,0,0)), (0,0), mask.point(lambda v: 255-v))
gray = sub.convert("L")
lut, _, _ = tone_lut(gray, mask, head_frac=0.70, plo=0.02, phi=0.99, gamma=0.78)
lut = [max(0, min(255, int(255*min(1.0, max(0.0, 0.5+((v/255)-0.5)*1.20))))) for v in lut]
L = list(gray.point(lut).resize((PW, PH), Image.LANCZOS).get_flattened_data())
C = list(ImageEnhance.Color(sub.resize((PW, PH), Image.LANCZOS)).enhance(1.25).get_flattened_data())
M = list(mask.resize((PW, PH), Image.LANCZOS).get_flattened_data())
for i, l in enumerate(L):
    if M[i] < 40: continue
    c = RAMP[min(len(RAMP)-1, l*len(RAMP)//256)]
    if c == " ": continue
    r, g, b = C[i]; mx = max(r, g, b, 1)
    col = tuple(min(255, int(v*min(1.45, 205/mx))) for v in (r, g, b))
    d.text((OX+(P_COL+i%PW)*CW+CW/2, OY+(P_ROW+i//PW)*CH+ASC), c, font=font, fill=col, anchor="ms")

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

# ---------------- plain avatar crop ----------------
av = Image.open(SRC).convert("RGB").crop(AVATAR_CROP).resize((1000, 1000), Image.LANCZOS)
avatar = os.path.join(OUTDIR, "avatar.jpg")   # JPEG: a photo as PNG runs ~900KB, near GitHub's 1MB cap
av.save(avatar, quality=92, subsampling=0, optimize=True)

print(f"banner {img.size} portrait {PW}x{PH} rows {P_ROW}-{P_ROW+PH-1} info {IR}-{r+1}"
      f"  {os.path.getsize(banner)//1024}KB")
print(f"avatar {av.size}  {os.path.getsize(avatar)//1024}KB")
