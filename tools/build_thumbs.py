#!/usr/bin/env python3
"""Render page 1 of every PDF into a small local cover thumbnail.

The site previously hot-linked Gutenberg's cover endpoint, which 404s for a large
share of the catalogue and adds a third-party request per card. Rendering our own
cover guarantees every card has art, works offline and costs one request served from
our own CDN.

A raw page-1 render is mostly blank paper with a short title block floating in the
middle, which on a 3:4 card reads as an empty white tile. So the title block is
trimmed off its white margin, scaled to fill the card and composited onto the
category gradient the CSS already paints, which turns the same page into a cover.

The covers go out as WebP: painted gradients and a page of type cost roughly three
times as JPEG at the size they look identical, and the thumbnails are the whole
deployment budget (tools/stage_deploy.py). THUMB_EXT is the single place the
extension is decided, because the manifests, the deploy staging and the page-1
rebuild all have to agree on it.
"""
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed

from PIL import Image, ImageChops, ImageDraw, ImageFilter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_DIR = os.path.join(BASE, "pdfs")
THUMB_DIR = os.path.join(BASE, "assets", "thumbs")
BOOKS = os.path.join(BASE, "data", "books.json")

THUMB_EXT = ".webp"
FORMAT = "WEBP"

# mirrors CATEGORY_COLORS in assets/js/app.js and assets/js/book.js so the baked
# gradient matches the one the card would have painted on its own
CATEGORY_COLORS = {
    "Fiction": ("#7c3aed", "#4c1d95"),
    "Children": ("#ec4899", "#9d174d"),
    "Science": ("#0ea5e9", "#075985"),
    "History": ("#f59e0b", "#92400e"),
    "Islam & Religion": ("#10b981", "#065f46"),
    "Philosophy": ("#6366f1", "#312e81"),
    "Self-Help": ("#ef4444", "#7f1d1d"),
    "Business": ("#14b8a6", "#134e4a"),
    "Poetry": ("#d946ef", "#701a75"),
    "Technology": ("#06b6d4", "#155e75"),
    "Psychology": ("#8b5cf6", "#4c1d95"),
    "Strategy": ("#f97316", "#7c2d12"),
    "AI & Computing": ("#22d3ee", "#0e7490"),
    "Biography": ("#a78bfa", "#5b21b6"),
    "Society": ("#84cc16", "#3f6212"),
    "Sports & Games": ("#eab308", "#854d0e"),
    "Language & Reference": ("#64748b", "#1e293b"),
}
FALLBACK_COLORS = ("#475569", "#1e293b")

CANVAS = (504, 672)  # 3:4, same ratio as the .cover frame in the CSS; ~1.8x its width
DPI = 150            # trimmed art is scaled up, so render above card size first
QUALITY = 56
# white at or above this level counts as paper, not ink
TRIM_TOLERANCE = 14
# the trimmed block gets breathing room inside the cover
CONTENT_BOX = (0.84, 0.66)
# rebuild every thumbnail even when one is already on disk; needed after the cover
# pipeline itself changes
FORCE = os.environ.get("FORCE_THUMBS") == "1"


def _rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _gradient(size, c1, c2):
    """Smooth diagonal gradient, the same 160deg sweep the CSS cover paints.

    Built small and scaled up: rotating a full-size linear gradient leaves visible
    banding, and a per-pixel pass at cover size is wasted work.
    """
    n = 64
    ramp = Image.new("RGB", (n, n))
    ramp.putdata([
        tuple(round(a + (b - a) * ((x + y) / (2.0 * n - 2))) for a, b in zip(c1, c2))
        for y in range(n) for x in range(n)
    ])
    return ramp.resize(size, Image.BICUBIC)


def _trim(im):
    """Crop the page down to the printed block, with a little padding."""
    gray = im.convert("L")
    # anything meaningfully darker than paper is ink; getbbox() then returns the
    # bounding box of all the ink on the page
    ink = gray.point(lambda p: 255 if p < 255 - TRIM_TOLERANCE else 0)
    box = ink.getbbox()
    if not box:
        return None
    left, top, right, bottom = box
    pad = max(int(0.04 * (bottom - top)), int(0.04 * (right - left)), 8)
    return im.crop((
        max(left - pad, 0),
        max(top - pad, 0),
        min(right + pad, im.width),
        min(bottom + pad, im.height),
    ))


def _compose(block, category):
    """Paint the trimmed title block onto the category gradient.

    The scanned page is mounted on a rounded white plate with a soft shadow: pasted
    as bare paper it reads as a white rectangle floating on the colour, whereas a
    plate with an edge reads as a cover with a label on it.
    """
    c1, c2 = CATEGORY_COLORS.get(category, FALLBACK_COLORS)
    w, h = CANVAS
    canvas = _gradient(CANVAS, _rgb(c1), _rgb(c2))

    # a wide highlight behind the middle keeps the plate off a flat wash
    glow = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(glow).ellipse(
        (-w * 0.30, -h * 0.10, w * 1.30, h * 0.95), fill=64
    )
    glow = glow.filter(ImageFilter.GaussianBlur(w * 0.18))
    canvas = Image.composite(Image.new("RGB", CANVAS, (255, 255, 255)), canvas, glow)

    # a dark wash at the foot anchors the card and keeps the category badge legible
    foot = Image.linear_gradient("L").resize(CANVAS)
    foot = foot.point(lambda p: int(p * 0.45))
    canvas = Image.composite(Image.new("RGB", CANVAS, (0, 0, 0)), canvas, foot)

    if block is None:
        return canvas

    radius = int(w * 0.03)
    box_w, box_h = w * CONTENT_BOX[0], h * CONTENT_BOX[1]
    # every cover gets the same plate and the title is fitted inside it: sizing the
    # plate to the title instead leaves a long title filling the card and a short one
    # floating in a stamp, and the grid ends up with no rhythm at all
    pw, ph = int(box_w), int(box_h)
    px, py = (w - pw) // 2, int((h - ph) * 0.46)

    pad = int(w * 0.05)
    block = block.copy()
    block.thumbnail((pw - pad * 2, ph - pad * 2), Image.LANCZOS)

    shadow = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(shadow).rounded_rectangle(
        (px, py + 10, px + pw, py + ph + 10), radius=radius, fill=130
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(w * 0.022))
    canvas = Image.composite(Image.new("RGB", CANVAS, (0, 0, 0)), canvas, shadow)

    plate = Image.new("RGB", (pw, ph), (255, 255, 255))
    mask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, pw - 1, ph - 1), radius=radius, fill=255)
    plate.paste(block, ((pw - block.width) // 2, (ph - block.height) // 2))
    canvas.paste(plate, (px, py), mask)
    return canvas


def _render(job, force=False):
    bid, category, pdf_dir, dest = job
    dest = os.path.join(dest, bid + THUMB_EXT)
    if not (force or FORCE) and os.path.exists(dest) and os.path.getsize(dest) > 1024:
        return bid, "cached", 0

    pdf = os.path.join(pdf_dir, bid + ".pdf")
    tmp_png = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
            tmp_png = fh.name
        # 150 dpi leaves the title crisp once it is scaled into the card
        subprocess.run(
            ["mutool", "draw", "-o", tmp_png, "-r", str(DPI), "-F", "png", pdf, "1"],
            check=True, capture_output=True, timeout=90,
        )
        with Image.open(tmp_png) as im:
            im = im.convert("RGB")
            cover = _compose(_trim(im), category)
            cover.save(dest, FORMAT, quality=QUALITY, method=4)
        size = os.path.getsize(dest)
    except Exception:
        if os.path.exists(dest):
            os.remove(dest)
        return bid, "failed", 0
    finally:
        if tmp_png and os.path.exists(tmp_png):
            os.remove(tmp_png)
    return bid, "built", size


def main():
    os.makedirs(THUMB_DIR, exist_ok=True)
    books = json.load(open(BOOKS, encoding="utf-8"))
    jobs = []
    for b in books:
        if not os.path.exists(os.path.join(PDF_DIR, b["id"] + ".pdf")):
            continue
        jobs.append((b["id"], b.get("category", ""), PDF_DIR, THUMB_DIR))

    total = len(jobs)
    print("covers: %d PDFs to render" % total, flush=True)
    done = {"cached": 0, "built": 0, "failed": 0}
    with ProcessPoolExecutor(max_workers=max(2, (os.cpu_count() or 2))) as ex:
        futs = [ex.submit(_render, j) for j in jobs]
        for n, fut in enumerate(as_completed(futs), 1):
            bid, status, size = fut.result()
            done[status] += 1
            if n % 250 == 0 or n == total:
                print("  %d/%d %s" % (n, total, done), flush=True)

    print("covers: %d built, %d cached, %d failed, %.1f MB total"
          % (done["built"], done["cached"], done["failed"],
             sum(os.path.getsize(os.path.join(THUMB_DIR, f))
                 for f in os.listdir(THUMB_DIR)) / 1048576), flush=True)
    return 1 if done["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())