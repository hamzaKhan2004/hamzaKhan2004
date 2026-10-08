#!/usr/bin/env python3
"""
Photographic ASCII / typographic-halftone SVG generator.

source-prepped.png  ->  profile-ascii.svg

Pipeline:
  1. load grayscale photo
  2. detect the subject (flood-fill the white background from the border,
     so bright shirt/teeth inside the outline are NOT removed)
  3. crop to the subject
  4. local contrast (unsharp) at full resolution, then area-resample to a
     dense character grid, compensating for non-square character cells
  5. global tone curve (percentile stretch + gamma)
  6. luminance -> ink density (light-on-dark, like the target) with
     ordered Bayer dithering for a halftone texture
  7. emit real SVG <text> rows with a one-shot staggered reveal animation
"""

from __future__ import annotations

import html
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# =========================================================
# PARAMETERS
# =========================================================
ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "source-prepped.png"
OUTPUT = ROOT / "profile-ascii.svg"

# --- grid / typography -----------------------------------------------------
WIDTH = 240                 # characters per row (more = finer detail)
FONT_SIZE = 6.0             # px
CHAR_W_EM = 0.6             # advance width of a monospace glyph, in em
LINE_HEIGHT = 6.6           # px between rows
CHAR_ASPECT = (FONT_SIZE * CHAR_W_EM) / LINE_HEIGHT  # cell width / height

# Ink ramp, sparse -> dense. Bright source pixels use dense glyphs.
RAMP = " .,:;irsXA253hMHGS#9B&@"

# --- tone ------------------------------------------------------------------
INVERT_TONE = False         # False: bright = dense ink (matches the target)
CONTRAST = 1.0              # extra contrast multiplier around mid-gray
GAMMA = 1.15                # >1 darkens mids, keeps highlights from clipping
LOW_PCT, HIGH_PCT = 1.0, 99.0   # percentile stretch measured on subject only
SUBJECT_FLOOR = 0.07        # min ink for subject pixels so dark hair keeps its silhouette
LOCAL_RADIUS = 2.0          # unsharp radius (px of the source image)
LOCAL_PERCENT = 160         # unsharp strength: sharpens eyes, lips, lapels
DITHER = 0.9                # Bayer strength in ramp steps (0 = off)

# --- background detection --------------------------------------------------
BG_THRESHOLD = 247          # pixels >= this and connected to the border = background
BG_CLOSE = 3                # MinFilter size: seals tiny gaps in the outline
CROP_MARGIN = 0.03          # fraction of subject size kept around it

# --- svg -------------------------------------------------------------------
TEXT_COLOR = "#c9d1d9"
BACKGROUND = "#0d1117"
PAD_X = 12
PAD_Y = 12
CORNER_RADIUS = 12
FONT_FAMILY = '"DejaVu Sans Mono","Courier New",Consolas,monospace'
FONT_WEIGHT = 600

# --- animation (plays once, then stays static) -------------------------------
ROW_DELAY = 0.014           # seconds between rows
ROW_DURATION = 0.35         # seconds per row
SLIDE_PX = 14               # left-to-right slide distance

NBSP = "\u00a0"

BAYER_4 = (np.array([[0, 8, 2, 10],
                     [12, 4, 14, 6],
                     [3, 11, 1, 9],
                     [15, 7, 13, 5]], dtype=np.float32) + 0.5) / 16.0


# =========================================================
# IMAGE LOADING / SUBJECT DETECTION
# =========================================================
def load_image(path: Path) -> Image.Image:
    """Load as grayscale, compositing any alpha onto white."""
    img = Image.open(path)
    if img.mode in ("RGBA", "LA") or "transparency" in img.info:
        img = img.convert("RGBA")
        base = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(base, img)
    return img.convert("L")


def subject_mask(gray: Image.Image) -> np.ndarray:
    """
    Boolean mask (True = subject).
    Only near-white pixels *connected to the border* are background, so bright
    shirt, teeth and skin highlights inside the outline survive.
    """
    closed = gray.filter(ImageFilter.MinFilter(BG_CLOSE))
    binary = closed.point(lambda v: 255 if v >= BG_THRESHOLD else 0)
    w, h = binary.size
    seeds = []
    step = 8
    seeds += [(x, 0) for x in range(0, w, step)] + [(x, h - 1) for x in range(0, w, step)]
    seeds += [(0, y) for y in range(0, h, step)] + [(w - 1, y) for y in range(0, h, step)]
    for s in seeds:
        if binary.getpixel(s) == 255:
            ImageDraw.floodfill(binary, s, 128)
    return np.asarray(binary) != 128


def crop_image(gray: Image.Image, mask: np.ndarray) -> tuple[Image.Image, np.ndarray]:
    """Crop to the subject bounding box plus a small margin."""
    ys, xs = np.where(mask)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    mx = int((x1 - x0) * CROP_MARGIN)
    my = int((y1 - y0) * CROP_MARGIN)
    x0, y0 = max(0, x0 - mx), max(0, y0 - my)
    x1, y1 = min(gray.width, x1 + mx), min(gray.height, y1 + my)
    return gray.crop((x0, y0, x1, y1)), mask[y0:y1, x0:x1]


# =========================================================
# TONE
# =========================================================
def resize_for_characters(gray: Image.Image, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Sharpen locally at full resolution, then area-resample to the character
    grid. Rows are reduced by CHAR_ASPECT so the cell shape does not distort
    the face. Large -> small LANCZOS acts as supersampling.
    """
    sharp = gray.filter(ImageFilter.UnsharpMask(LOCAL_RADIUS, LOCAL_PERCENT, 2))
    rows = max(1, round(WIDTH * (gray.height / gray.width) * CHAR_ASPECT))
    tone = np.asarray(sharp.resize((WIDTH, rows), Image.Resampling.LANCZOS), dtype=np.float32) / 255.0
    cover = Image.fromarray((mask * 255).astype(np.uint8)).resize((WIDTH, rows), Image.Resampling.BOX)
    return tone, (np.asarray(cover) > 127)


def enhance_contrast(tone: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Percentile stretch measured on the subject only, then contrast + gamma."""
    lo, hi = np.percentile(tone[mask], [LOW_PCT, HIGH_PCT])
    t = np.clip((tone - lo) / max(hi - lo, 1e-6), 0, 1)
    t = np.clip((t - 0.5) * CONTRAST + 0.5, 0, 1)
    t = t ** GAMMA
    if INVERT_TONE:
        t = 1.0 - t
    t = SUBJECT_FLOOR + t * (1.0 - SUBJECT_FLOOR)
    return np.where(mask, t, 0.0)


# =========================================================
# CHARACTERS
# =========================================================
def pixel_to_character(level: int) -> str:
    return RAMP[max(0, min(level, len(RAMP) - 1))]


def generate_ascii_rows(tone: np.ndarray, mask: np.ndarray) -> list[str]:
    """Ordered-dither the tone into ramp levels; background stays empty."""
    h, w = tone.shape
    bayer = np.tile(BAYER_4, (h // 4 + 1, w // 4 + 1))[:h, :w]
    levels = np.rint(tone * (len(RAMP) - 1) + (bayer - 0.5) * DITHER).astype(int)
    levels = np.where(mask, np.maximum(levels, 1), 0)  # subject never fully blank
    return ["".join(pixel_to_character(int(v)) for v in row) for row in levels]


# =========================================================
# SVG
# =========================================================
def generate_svg(rows: list[str]) -> str:
    char_w = FONT_SIZE * CHAR_W_EM
    cols = max(len(r) for r in rows)
    svg_w = round(cols * char_w + PAD_X * 2)
    svg_h = round(len(rows) * LINE_HEIGHT + PAD_Y * 2)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" '
        f'viewBox="0 0 {svg_w} {svg_h}" xml:space="preserve">',
        "<style>",
        f".a{{font-family:{FONT_FAMILY};font-size:{FONT_SIZE}px;font-weight:{FONT_WEIGHT};"
        f"fill:{TEXT_COLOR};white-space:pre;"
        f"animation:r {ROW_DURATION}s ease-out both}}",
        f"@keyframes r{{from{{opacity:0;transform:translateX(-{SLIDE_PX}px)}}"
        f"to{{opacity:1;transform:translateX(0)}}}}",
        "</style>",
        f'<rect width="100%" height="100%" rx="{CORNER_RADIUS}" fill="{BACKGROUND}"/>',
    ]

    for i, row in enumerate(rows):
        stripped = row.strip(" ")
        if not stripped:
            continue
        lead = len(row) - len(row.lstrip(" "))
        text = html.escape(stripped, quote=False).replace(" ", NBSP)
        x = PAD_X + lead * char_w
        y = PAD_Y + (i + 1) * LINE_HEIGHT - (LINE_HEIGHT - FONT_SIZE) / 2 - FONT_SIZE * 0.2
        # textLength pins the row width even if the viewer swaps the font
        out.append(
            f'<text class="a" x="{x:.2f}" y="{y:.2f}" xml:space="preserve" '
            f'textLength="{len(stripped) * char_w:.2f}" lengthAdjust="spacing" '
            f'style="animation-delay:{i * ROW_DELAY:.3f}s">{text}</text>'
        )

    out.append("</svg>")
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
    print(f"Grid: {WIDTH} x {len(rows)} | wrote {OUTPUT} "
          f"({OUTPUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()