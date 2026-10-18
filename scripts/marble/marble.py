"""The marbled endpaper: the built-in `marble` artwork of form themes.

Procedural, deterministic and first-party: no photos, no third-party images.

Method (after Jaffer's "mathematical marbling"): ink drops are floated onto a
virtual size bath, each new drop pushing the earlier ink outward into rings.
The bath is then raked with a few gentle, area-preserving strokes (two broad
waves and one wide-tined comb). Every pixel is traced backwards through those
strokes and drops to find which ink it carries. Because every step preserves
area, the share of rose and blush in the result equals the share dropped.

Run from this folder:  uv sync && uv run python marble.py   (about 1.5 minutes)
Writes webapp/src/assets/themes/marble/marble-{panel,strip}*.{avif,webp} and
placeholders.json (blurred WebP data URIs shown while the images load). The
output is deterministic for a given SEED.
"""

from __future__ import annotations

import base64
import json
import io
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
OUT = HERE.parent.parent / "webapp" / "src" / "assets" / "themes" / "marble"
SEED = 1847  # change for a different sheet; keep for reproducible output

# Palette: cloth green leads, deep ink-greens carry the body, blush and rose are veins.
CLOTH = (0x1E, 0x4D, 0x3B)
DEEP = (0x16, 0x3A, 0x2C)
INK = (0x10, 0x2C, 0x21)
SAGE = (0x2B, 0x5E, 0x4A)
BLUSH = (0xF8, 0xEE, 0xEC)
ROSE = (0xA3, 0x30, 0x5A)
PALETTE = np.array([CLOTH, DEEP, INK, SAGE, BLUSH, ROSE], dtype=np.float32)
C_CLOTH, C_DEEP, C_INK, C_SAGE, C_BLUSH, C_ROSE = range(6)
ACCENTS = (C_BLUSH, C_ROSE)

# World units are output pixels of the 2x desktop panel (1440 x 1800).
BLUR = 3.5  # feathering, in output pixels
WORLD = (-420.0, -420.0, 1980.0, 2220.0)  # x0, y0, x1, y1: where ink is dropped


# Colours are thrown one at a time across the whole bath, as a marbler does.
# Each later colour squeezes the earlier ones into veins, so the first colours
# end up as thin lines and the last one as broad "stones".
# (colour, share of the bath, min radius, max radius), in throwing order.
OVERFILL = 1.7  # more ink than bath: drops crowd each other into veins
THROWS = [
    (C_ROSE, 0.09, 34.0, 52.0),
    (C_BLUSH, 0.06, 30.0, 48.0),
    (C_SAGE, 0.10, 36.0, 56.0),
    (C_INK, 0.15, 44.0, 66.0),
    (C_DEEP, 0.22, 56.0, 86.0),
    (C_CLOTH, 0.40, 76.0, 112.0),
]


def build_drops(rng: np.random.Generator) -> list[tuple[float, float, float, int]]:
    x0, y0, x1, y1 = WORLD
    bath = (x1 - x0) * (y1 - y0)
    drops: list[tuple[float, float, float, int]] = []
    for col, share, rmin, rmax in THROWS:
        need = share * bath * OVERFILL
        while need > 0:
            r = float(rng.uniform(rmin, rmax))
            drops.append((float(rng.uniform(x0, x1)), float(rng.uniform(y0, y1)), r, col))
            need -= math.pi * r * r
    return drops


def strokes():
    """Raking strokes, in the order they are drawn. Each is a shear along one
    direction, so its inverse is the same displacement subtracted, and all are
    smooth (no cusps), which keeps vein edges free of kinks."""
    ang = math.radians(-24)  # a gentle diagonal, echoing the original endpaper
    along = (math.cos(ang), math.sin(ang))
    across = (-math.sin(ang), math.cos(ang))
    return [
        # kind, move direction, varies along, amplitude, period, phase
        ("wave", along, across, 720.0, 2300.0, 0.6),   # long stretch: stones become bands
        ("wave", along, across, 230.0, 820.0, 2.4),    # broad combing
        ("wave", across, along, 120.0, 2300.0, 1.1),   # slow swell for gentle flow
        ("wave", along, across, 18.0, 140.0, 0.0),     # soft feathering of each vein
    ]


def displacement(kind, move, normal, amp, period, extra, px, py):
    s = px * normal[0] + py * normal[1]
    if kind == "wave":
        d = amp * np.sin(2 * np.pi * s / period + extra)
    else:  # comb: smooth periodic pull peaking on each tine
        d = amp * ((1.0 + np.cos(2 * np.pi * s / period)) * 0.5) ** extra
    return d * move[0], d * move[1]


def trace(px: np.ndarray, py: np.ndarray, drops) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Map output points back through strokes and drops to an ink label."""
    px = px.astype(np.float64).copy()
    py = py.astype(np.float64).copy()
    for kind, move, normal, amp, period, extra in reversed(strokes()):
        dx, dy = displacement(kind, move, normal, amp, period, extra, px, py)
        px -= dx
        py -= dy
    label = np.full(px.shape, C_CLOTH, dtype=np.int8)
    open_ = np.ones(px.shape, dtype=bool)
    for cx, cy, r, col in reversed(drops):
        idx = np.nonzero(open_)[0]
        if idx.size == 0:
            break
        ex = px[idx] - cx
        ey = py[idx] - cy
        d2 = ex * ex + ey * ey
        r2 = r * r
        inside = d2 < r2
        hit = idx[inside]
        label[hit] = col
        open_[hit] = False
        out = idx[~inside]
        f = np.sqrt(1.0 - r2 / d2[~inside])
        px[out] = cx + ex[~inside] * f
        py[out] = cy + ey[~inside] * f
    return label, px, py


def render(x0: float, y0: float, w: int, h: int, drops, ss: int = 2) -> tuple[Image.Image, float]:
    """Render a w x h window whose top-left is world (x0, y0); ss = supersampling."""
    gx = x0 + (np.arange(w * ss) + 0.5) / ss
    gy = y0 + (np.arange(h * ss) + 0.5) / ss
    X, Y = np.meshgrid(gx, gy)
    label, sx, sy = trace(X.ravel(), Y.ravel(), drops)
    rgb = PALETTE[label.astype(np.intp)]
    # Very slow tonal drift carried with the ink (like uneven size), +-4%.
    tone = 1.0 + 0.04 * (np.sin(sx / 310.0 + 1.3) * np.cos(sy / 470.0 - 0.4)
                         + 0.5 * np.sin((sx + sy) / 820.0))
    greens = label < C_BLUSH
    rgb[greens] *= tone[greens, None].astype(np.float32)
    img = rgb.reshape(h * ss, w * ss, 3)
    accent = float(np.isin(label, ACCENTS).mean())
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")
    # Soft feathered edges: blur at supersampled size, then downsample.
    im = im.filter(ImageFilter.GaussianBlur(BLUR * ss))
    im = im.resize((w, h), Image.Resampling.LANCZOS)
    return im, accent


def save(im: Image.Image, stem: str, avif_q: int, webp_q: int) -> None:
    im.save(OUT / f"{stem}.avif", "AVIF", quality=avif_q, speed=4)
    im.save(OUT / f"{stem}.webp", "WEBP", quality=webp_q, method=6)


def placeholder(im: Image.Image, width: int = 24) -> str:
    h = max(2, round(im.height * width / im.width))
    tiny = im.resize((width, h), Image.Resampling.BOX).filter(ImageFilter.GaussianBlur(1))
    buf = io.BytesIO()
    tiny.save(buf, "WEBP", quality=40)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    drops = build_drops(np.random.default_rng(SEED))

    panel, acc_p = render(0, 0, 1440, 1800, drops)
    save(panel, "marble-panel-1440x1800", avif_q=50, webp_q=72)
    small = panel.resize((960, 1200), Image.Resampling.LANCZOS)
    save(small, "marble-panel-960x1200", avif_q=52, webp_q=74)
    placeholders = {"panel": placeholder(panel)}

    strip, acc_s = render(-60, 820, 1560, 240, drops)
    save(strip, "marble-strip-1560x240", avif_q=50, webp_q=70)
    placeholders["strip"] = placeholder(strip)
    (OUT / "placeholders.json").write_text(json.dumps(placeholders, indent=4) + "\n")

    print(f"accent (rose + blush) coverage: panel {acc_p:.1%}, strip {acc_s:.1%}")
    for f in sorted(OUT.iterdir()):
        print(f"{f.stat().st_size:>8}  {f.name}")


if __name__ == "__main__":
    main()
