#!/usr/bin/env python3
"""
Photographic ASCII / typographic-halftone SVG generator.

    source-prepped.png  ->  profile-ascii.svg        (python scripts/make_ascii_svg.py)

Target look (measured on the reference render, 210 x 216 cells):
  * a regular lattice of heavy, round glyphs on a 5.8 x 5.5 px pitch; where the
    tone is bright the glyphs touch and fuse into a light surface pierced only by
    small dark lattice holes, where it is dark they shrink to a sparse dot texture;
  * a SOFT tonal range: median subject cell is ~1/3 ink, hair and suit sit at
    ~15-20 % (lattice still visible), face / neck are mid-tones, and only the
    shirt, teeth and forehead highlights reach (near) full coverage;
  * no blown-out face and no hard unsharp halos.

To get there reliably for ANY photo, the final tone map is a histogram
specification: whatever the photo's own contrast is, the ranked subject cells
are remapped onto TARGET_FILL_QUANTILES (measured from the reference).

Needs: pillow, numpy
"""

from __future__ import annotations

import html
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# =========================================================
# PARAMETERS
# =========================================================
ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "source-prepped.png"
OUTPUT = ROOT / "profile-ascii.svg"

# --- lattice / typography --------------------------------------------------
WIDTH = 210                 # characters per row (more = finer detail)
CELL_W = 5.80               # px, horizontal pitch of the lattice
CELL_H = 5.50               # px, vertical pitch of the lattice
FONT_SIZE = 11.5            # px; wider than the 5.8 px pitch, so heavy glyphs fuse into a solid surface
                            # whose counters show up as the small dark round dots of the reference
GLYPH_SQUEEZE_Y = 0.76      # vertical squash so glyphs fit the near-square cell
ASPECT_X = 1.09             # reference portrait is ~9% wider than the photo (1269x1239 vs 900x955)
STROKE_WIDTH = 0.6          # px; thicker = bigger fused areas / smaller dark dots
FONT_WEIGHT = 700
FONT_FAMILY = '"DejaVu Sans Mono","Menlo","Consolas","Liberation Mono","Courier New",monospace'
CAP_HEIGHT_EM = 0.729       # cap height / font size (DejaVu Sans Mono)
ADVANCE_EM = 0.602          # natural glyph advance / font size (spacing is added up to CELL_W)

# Fonts used only to *measure* glyph ink coverage (first one found wins).
MEASURE_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/Library/Fonts/DejaVuSansMono-Bold.ttf",
    "C:/Windows/Fonts/consolab.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
]
# Round glyphs only, so every cell reads as a dot of some size.
CANDIDATES = " .'`,:;\"ioc*eaO08@"   # blank + round-ish glyphs, light -> heavy (no slashes: they read as noise)
RAMP_LEVELS = 12
FALLBACK_RAMP = " .:-=+*o%#@"

# --- tone ------------------------------------------------------------------
LOW_PCT, HIGH_PCT = 0.5, 99.5   # percentile stretch (subject only)
EQ_AMOUNT = 0.0             # 0 = linear, 1 = full histogram equalisation (the histogram match below replaces it)
CONTRAST = 1.0              # S-curve around mid-grey (1.0 = none)
GAMMA = 1.0                 # extra gamma before the histogram match (1.0 = none)
SHADOW_FLOOR = 0.0          # minimum tone before the histogram match (the match sets the real floor)
ADAPT_AMOUNT = 0.30         # adaptive local contrast blend (a little eye / teeth detail in shadow)
ADAPT_SIGMA = 4.0           # cells
ADAPT_FLOOR = 0.12          # spread floor, stops flat cloth turning into noise
ADAPT_GAIN = 0.30
ADAPT_KEEP_MEAN = 0.40
EDGE_SIGMA = 1.2            # cells; unsharp radius on the character grid
EDGE_AMOUNT = 0.90          # local sharpening; safe now that the histogram match fixes the global tone
DETAIL_RADIUS = 1.2         # px; full-resolution unsharp before resampling
DETAIL_PERCENT = 60
DITHER = 0.0                # ordered-dither strength in ramp steps (0 = clean halftone)

# Histogram specification: ink coverage (0 = blank .. 1 = densest glyph) of the
# subject cells at the 0, 5, 10 ... 100 % quantiles, measured on the reference.
TARGET_FILL_QUANTILES = [0.045, 0.068, 0.095, 0.122, 0.149, 0.177, 0.205, 0.232, 0.262, 0.295, 0.330,
                         0.370, 0.416, 0.469, 0.530, 0.598, 0.666, 0.739, 0.807, 0.881, 1.0]
HIST_MATCH = 1.0            # 0 = keep the photo's own tone curve, 1 = force the reference histogram

# --- lighting ----------------------------------------------------------------
LIGHT_MIN = 0.55            # brightness multiplier far from the head (1.0 = no vignette)
LIGHT_SX = 0.50             # spotlight half-width,  fraction of subject width
LIGHT_SY = 0.60             # spotlight half-height, fraction of subject height
LIGHT_CY = 0.30             # spotlight centre row,  fraction of subject height
SMOOTH_SIGMA = 0.40         # cells; tiny blur so neighbouring cells do not flicker between glyphs

# --- background detection --------------------------------------------------
BG_THRESHOLD = 247          # near-white pixels connected to the border = background
BG_CLOSE = 3
CROP_MARGIN = 0.02
MASK_ERODE = 4              # px; shrinks the mask to drop the cut-out edge halo
MASK_COVERAGE = 0.5         # a cell is "subject" if >= this fraction of it is subject

# --- svg -------------------------------------------------------------------
TEXT_COLOR = "#c9d1d9"
BACKGROUND = "#0d1117"
PAD_X = 16
PAD_Y = 16
CORNER_RADIUS = 12

# --- animation (plays once, then stays static) -------------------------------
ROW_DELAY = 0.010           # seconds between rows
ROW_DURATION = 0.35         # seconds per row
SLIDE_PX = 14               # left-to-right slide distance

NBSP = "\u00a0"
CHAR_ASPECT = CELL_W / CELL_H   # cell width / cell height
BAYER_4 = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) + 0.5) / 16.0


# =========================================================
# IMAGE LOADING / SUBJECT DETECTION
# =========================================================
def load_image(path: Path) -> Image.Image:
    """Load as grayscale, compositing any alpha onto white."""
    img = Image.open(path)
    if img.mode in ("RGBA", "LA") or "transparency" in img.info:
        img = Image.alpha_composite(Image.new("RGBA", img.size, (255, 255, 255, 255)), img.convert("RGBA"))
    return img.convert("L")


def subject_mask(gray: Image.Image) -> np.ndarray:
    """
    True = subject. Only near-white pixels *connected to the border* are
    background, so a bright shirt or teeth inside the outline survive. The mask
    is then shrunk a few px: the cut-out edge carries a light halo / dark outline
    that would otherwise become a ring of dense glyphs.
    """
    binary = gray.filter(ImageFilter.MinFilter(BG_CLOSE)).point(lambda v: 255 if v >= BG_THRESHOLD else 0)
    w, h = binary.size
    step = 8
    seeds = [(x, y) for x in range(0, w, step) for y in (0, h - 1)] + [(x, y) for y in range(0, h, step) for x in (0, w - 1)]
    for s in seeds:
        if binary.getpixel(s) == 255:           # skip seeds already swallowed by an earlier fill
            ImageDraw.floodfill(binary, s, 128)
    subject = Image.fromarray(((np.asarray(binary) != 128) * 255).astype(np.uint8))
    if MASK_ERODE > 0:
        subject = subject.filter(ImageFilter.MinFilter(2 * MASK_ERODE + 1))
    return np.asarray(subject) > 127


def crop_image(gray: Image.Image, mask: np.ndarray) -> tuple[Image.Image, np.ndarray]:
    """Crop to the subject bounding box plus a small margin."""
    ys, xs = np.where(mask)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    mx, my = int((x1 - x0) * CROP_MARGIN), int((y1 - y0) * CROP_MARGIN)
    x0, y0 = max(0, x0 - mx), max(0, y0 - my)
    x1, y1 = min(gray.width, x1 + mx), min(gray.height, y1 + my)
    return gray.crop((x0, y0, x1, y1)), mask[y0:y1, x0:x1]


# =========================================================
# TONE
# =========================================================
def resize_for_characters(gray: Image.Image, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Sharpen at full resolution, then area-average to the character grid. Rows are
    scaled by CELL_W / CELL_H so non-square cells do not distort the face. Each
    source pixel is weighted by the subject mask (normalised averaging), so the
    white background never bleeds into edge cells.
    """
    sharp = np.asarray(gray.filter(ImageFilter.UnsharpMask(DETAIL_RADIUS, DETAIL_PERCENT, 2)), np.float32)
    size = (WIDTH, max(1, round(WIDTH * (gray.height / gray.width) * CHAR_ASPECT / ASPECT_X)))
    m = mask.astype(np.float32)
    box = Image.Resampling.BOX
    num = np.asarray(Image.fromarray(sharp * m).resize(size, box))
    den = np.asarray(Image.fromarray(m).resize(size, box))
    tone = np.where(den > 1e-3, num / np.maximum(den, 1e-3), 0.0) / 255.0
    return tone.astype(np.float32), den > MASK_COVERAGE


def _blur_matrix(n: int, sigma: float) -> np.ndarray:
    """n x n Gaussian smoothing matrix (rows renormalised at the borders)."""
    i = np.arange(n)
    k = np.exp(-0.5 * ((i[:, None] - i[None, :]) / sigma) ** 2)
    k[np.abs(i[:, None] - i[None, :]) > 3 * sigma] = 0.0
    return k / k.sum(axis=1, keepdims=True)


def masked_blur(a: np.ndarray, mask: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian blur that only averages subject cells (matrix form: two matmuls)."""
    ky, kx = _blur_matrix(a.shape[0], sigma), _blur_matrix(a.shape[1], sigma)
    m = mask.astype(np.float32)
    blur = lambda x: ky @ x @ kx.T
    return blur(a * m) / np.maximum(blur(m), 1e-4)


def spotlight(mask: np.ndarray) -> np.ndarray:
    """
    Soft elliptical light centred on the head (centroid of the subject's upper
    part), falling off toward the shoulders and corners.
    """
    h, w = mask.shape
    top = mask[: max(1, int(h * 0.35))]
    cx = np.nonzero(top)[1].mean() if top.any() else w / 2
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d2 = ((xx - cx) / (LIGHT_SX * w)) ** 2 + ((yy - LIGHT_CY * h) / (LIGHT_SY * h)) ** 2
    return LIGHT_MIN + (1 - LIGHT_MIN) * np.exp(-0.5 * d2)


def enhance_contrast(tone: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Tone shaping, measured on the subject only:
      gentle unsharp on the grid -> spotlight -> percentile stretch -> light
      adaptive local contrast -> (optional) equalisation -> S-curve -> gamma
      -> shadow floor (dark hair / suit keep a visible dot lattice).
    """
    tone = tone + EDGE_AMOUNT * (tone - masked_blur(tone, mask, EDGE_SIGMA))
    tone = tone * spotlight(mask)
    lo, hi = np.percentile(tone[mask], [LOW_PCT, HIGH_PCT])
    t = np.clip((tone - lo) / max(hi - lo, 1e-6), 0, 1)

    if ADAPT_AMOUNT > 0:
        mu = masked_blur(t, mask, ADAPT_SIGMA)
        sd = np.sqrt(masked_blur((t - mu) ** 2, mask, ADAPT_SIGMA))
        local = np.clip(0.5 + ADAPT_GAIN * (t - mu) / (sd + ADAPT_FLOOR), 0, 1)
        local = np.clip(local + (mu - 0.5) * ADAPT_KEEP_MEAN, 0, 1)
        t = (1 - ADAPT_AMOUNT) * t + ADAPT_AMOUNT * local

    if EQ_AMOUNT > 0:
        vals = np.sort(t[mask])
        eq = np.searchsorted(vals, t) / max(len(vals) - 1, 1)
        t = (1 - EQ_AMOUNT) * t + EQ_AMOUNT * eq

    t = np.clip(0.5 + (t - 0.5) * CONTRAST, 0, 1) ** GAMMA
    if SMOOTH_SIGMA > 0:
        t = masked_blur(t, mask, SMOOTH_SIGMA)
    t = SHADOW_FLOOR + (1 - SHADOW_FLOOR) * t

    if HIST_MATCH > 0:
        t = (1 - HIST_MATCH) * t + HIST_MATCH * match_histogram(t, mask)
    return np.where(mask, t, 0.0)


def match_histogram(t: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Histogram specification on the subject cells: rank every cell (ties share
    their mean rank), then read the value the reference has at that quantile.
    The order of the cells (= the photo's structure) is untouched, only the
    tone distribution is replaced, so the result has the reference's soft
    mid-tones whatever the contrast of the input photo.
    """
    vals = t[mask]
    order = np.argsort(vals, kind="stable")
    rank = np.empty(len(vals), np.float64)
    rank[order] = np.arange(len(vals))
    sv = vals[order]                                    # average the rank over equal values
    lo, hi = np.searchsorted(sv, vals, "left"), np.searchsorted(sv, vals, "right")
    rank = (lo + hi - 1) / 2.0 / max(len(vals) - 1, 1)
    q = np.asarray(TARGET_FILL_QUANTILES, np.float64)
    out = np.zeros_like(t, dtype=np.float32)
    out[mask] = np.interp(rank, np.linspace(0, 1, len(q)), q)
    return out


# =========================================================
# CHARACTERS
# =========================================================
def measure_ramp() -> tuple[np.ndarray, np.ndarray]:
    """
    Pick RAMP_LEVELS glyphs whose measured ink coverage is evenly spaced.
    Each glyph is drawn on a 3 x 3 lattice (same pitch, stroke and squeeze as
    the SVG) and the ink in the centre cell is counted, so neighbours that touch
    or overlap are accounted for. Coverage is normalised so the densest glyph is
    1.0. Returns (glyphs, coverage), sparse -> dense.
    """
    font_path = next((p for p in MEASURE_FONTS if Path(p).exists()), None)
    if font_path is None:
        return np.array(list(FALLBACK_RAMP)), np.linspace(0.12, 1.0, len(FALLBACK_RAMP), dtype=np.float32)

    ss = 8                                               # supersampling while measuring
    font = ImageFont.truetype(font_path, round(FONT_SIZE * ss))
    cw, ch = CELL_W * ss, CELL_H / GLYPH_SQUEEZE_Y * ss  # cell size before the vertical squash
    cap = FONT_SIZE * CAP_HEIGHT_EM * ss
    stroke = round(STROKE_WIDTH * ss / 2)
    shift = (CELL_W - FONT_SIZE * ADVANCE_EM) / 2 * ss   # glyph centred in its cell
    cov = {}
    for g in CANDIDATES:
        canvas = Image.new("L", (round(cw * 3), round(ch * 3)), 0)
        draw = ImageDraw.Draw(canvas)
        for i in range(3):
            for j in range(3):
                draw.text((j * cw + shift, i * ch + ch / 2 + cap / 2), g, font=font, fill=255,
                          anchor="ls", stroke_width=stroke, stroke_fill=255)
        centre = np.asarray(canvas, np.float32)[round(ch):round(2 * ch), round(cw):round(2 * cw)]
        cov[g] = float(centre.mean() / 255.0)
    top = max(cov.values())
    cov = {g: c / top for g, c in cov.items()}

    chosen: list[str] = []
    for tgt in np.linspace(min(cov.values()), 1.0, RAMP_LEVELS):
        chosen.append(min((g for g in cov if g not in chosen), key=lambda g: abs(cov[g] - tgt)))
    chosen.sort(key=cov.get)
    return np.array(chosen), np.array([cov[g] for g in chosen], np.float32)


def generate_ascii_rows(tone: np.ndarray, mask: np.ndarray) -> list[str]:
    """
    Nearest-coverage glyph per cell, fully vectorised. Optional ordered dither
    (DITHER > 0) breaks banding without destroying the regular lattice.
    pixel_to_character is just the lookup glyphs[index].
    """
    glyphs, cov = measure_ramp()
    want = tone
    if DITHER > 0:
        h, w = tone.shape
        bayer = np.tile(BAYER_4, (h // 4 + 1, w // 4 + 1))[:h, :w]
        want = tone + (bayer - 0.5) * DITHER * (1.0 / len(cov))
    idx = np.abs(want[..., None] - cov).argmin(axis=-1)          # (h, w) index into ramp
    chars = np.where(mask, glyphs[idx], " ")
    return ["".join(row) for row in chars]


# =========================================================
# SVG
# =========================================================
def generate_svg(rows: list[str]) -> str:
    cols = max(len(r) for r in rows)
    svg_w = round(cols * CELL_W + PAD_X * 2)
    svg_h = round(len(rows) * CELL_H + PAD_Y * 2)
    cap = FONT_SIZE * CAP_HEIGHT_EM
    extra = CELL_W - FONT_SIZE * ADVANCE_EM         # letter-spacing needed to reach the pitch

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" '
        f'viewBox="0 0 {svg_w} {svg_h}" xml:space="preserve">',
        "<style>",
        f".a{{font-family:{FONT_FAMILY};font-size:{FONT_SIZE}px;font-weight:{FONT_WEIGHT};"
        f"fill:{TEXT_COLOR};stroke:{TEXT_COLOR};stroke-width:{STROKE_WIDTH}px;"
        f"white-space:pre;text-rendering:geometricPrecision;letter-spacing:{extra:.3f}px;"
        f"animation:r {ROW_DURATION}s ease-out both}}",
        f"@keyframes r{{from{{opacity:0;transform:translateX(-{SLIDE_PX}px)}}"
        f"to{{opacity:1;transform:translateX(0)}}}}",
        "</style>",
        f'<rect width="100%" height="100%" rx="{CORNER_RADIUS}" fill="{BACKGROUND}"/>',
        # glyphs are squashed vertically; y values below are pre-divided by the squeeze
        f'<g transform="scale(1 {GLYPH_SQUEEZE_Y})">',
    ]

    for i, row in enumerate(rows):
        stripped = row.strip(" ")
        if not stripped:
            continue
        lead = len(row) - len(row.lstrip(" "))
        text = html.escape(stripped, quote=False).replace(" ", NBSP)
        x = PAD_X + lead * CELL_W + (CELL_W - FONT_SIZE * ADVANCE_EM) / 2     # glyph centred in its cell
        y = (PAD_Y + (i + 0.5) * CELL_H) / GLYPH_SQUEEZE_Y + cap / 2     # caps centred in the cell
        # textLength pins every glyph to the lattice even if the viewer swaps the font
        out.append(
            f'<text class="a" x="{x:.2f}" y="{y:.2f}" xml:space="preserve" '
            f'textLength="{len(stripped) * CELL_W:.2f}" lengthAdjust="spacing" '
            f'style="animation-delay:{i * ROW_DELAY:.3f}s">{text}</text>'
        )

    out += ["</g>", "</svg>"]
    return "\n".join(out)


# =========================================================
# MAIN
# =========================================================
def main() -> None:
    if not INPUT.exists():
        raise FileNotFoundError(f"Could not find {INPUT}")

    gray = load_image(INPUT)
    mask = subject_mask(gray)
    gray, mask = crop_image(gray, mask)

    tone, cmask = resize_for_characters(gray, mask)
    tone = enhance_contrast(tone, cmask)
    rows = generate_ascii_rows(tone, cmask)

    OUTPUT.write_text(generate_svg(rows), encoding="utf-8")
    print(f"Grid: {WIDTH} x {len(rows)} | wrote {OUTPUT} ({OUTPUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()