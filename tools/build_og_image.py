#!/usr/bin/env python3
"""Render the social-share card (assets/og-image.jpg, 1200x630).

Same palette and wordmark as assets/css/style.css so the preview looks like
the site itself. Real book covers from assets/thumbs are used on the right so
the card reads as a library rather than a logo.

    python3 tools/build_og_image.py
"""

import json
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THUMBS = os.path.join(ROOT, "assets", "thumbs")
CATALOG = os.path.join(ROOT, "data", "catalog.json")
OUT = os.path.join(ROOT, "assets", "og-image.jpg")

W, H = 1200, 630
BG = (13, 17, 23)
GOLD = (232, 179, 75)
GOLD_2 = (245, 205, 118)
TEXT = (232, 237, 244)
MUTED = (154, 167, 184)

SERIF = "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"
SANS = "/usr/share/fonts/truetype/lato/Lato-Regular.ttf"
SANS_BOLD = "/usr/share/fonts/truetype/lato/Lato-Bold.ttf"
SANS_BLACK = "/usr/share/fonts/truetype/lato/Lato-Black.ttf"


def font(path, size):
    return ImageFont.truetype(path, size)


def glow(img, cx, cy, radius, colour, strength):
    layer = Image.new("RGB", img.size, BG)
    d = ImageDraw.Draw(layer)
    d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=colour)
    layer = layer.filter(ImageFilter.GaussianBlur(radius * 0.45))
    return Image.blend(img, Image.blend(img, layer, 1.0), strength)


def wordmark(draw, x, y, size=78):
    face = font(SERIF, size)
    w = draw.textlength("FAHAD", font=face)
    draw.text((x, y), "FAHAD", font=face, fill=TEXT)
    draw.text((x + w, y), ".COM", font=face, fill=GOLD)
    return x + w + draw.textlength(".COM", font=face)


def pill(draw, x, y, text, colour):
    face = font(SANS_BOLD, 26)
    tw = int(draw.textlength(text, font=face))
    box = [x, y, x + tw + 46, y + 54]
    draw.rounded_rectangle(box, radius=27, outline=(38, 48, 61), width=2, fill=(22, 29, 38))
    draw.ellipse([x + 20, y + 24, x + 32, y + 36], fill=colour)
    draw.text((x + 44, y + 12), text, font=face, fill=TEXT)
    return box[2] - x


def fit(draw, text, path, size, max_w):
    """Largest size <= `size` at which `text` still fits `max_w`."""
    while size > 8 and draw.textlength(text, font=font(path, size)) > max_w:
        size -= 2
    return font(path, size)


def cover_stack(img, books, count=3):
    """Fan a few real covers out on the right, page-1 thumbnails already are."""
    picks = random.sample(books, count)
    cw, ch = 150, 211
    slot = cw + 20
    x0 = W - 48 - (slot * count - 20)
    y0 = (H - ch) // 2 + 4
    for i, b in enumerate(picks):
        path = os.path.join(ROOT, b["cover"])
        if not os.path.exists(path):
            continue
        tile = Image.open(path).convert("RGB")
        tile = tile.resize((cw, ch), Image.LANCZOS)
        # round the corners so the stack matches the card radius on the site
        mask = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, cw - 1, ch - 1], radius=12, fill=255)
        x = x0 + i * slot
        shadow = Image.new("RGBA", (cw + 40, ch + 40), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle(
            [20, 26, 20 + cw, 26 + ch], radius=12, fill=(0, 0, 0, 190)
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(14))
        img.alpha_composite(shadow, (x - 20, y0 - 26))
        img.paste(tile, (x, y0), mask)
    return x0


def build():
    books = []
    if os.path.exists(CATALOG):
        with open(CATALOG, encoding="utf-8") as fh:
            books = [b for b in json.load(fh) if os.path.exists(os.path.join(ROOT, b.get("cover", "")))]
    random.seed(7)

    img = Image.new("RGB", (W, H), BG)
    img = glow(img, W // 2, -120, 620, (44, 36, 18), 0.85)
    img = glow(img, W - 140, H + 120, 460, (24, 30, 40), 0.6)
    img = img.convert("RGBA")

    if books:
        stack_x = cover_stack(img, books)
    else:
        stack_x = W - 48
    draw = ImageDraw.Draw(img)

    left = 84
    col = stack_x - left - 44

    wordmark(draw, left, 96, size=min(76, int(col / 7.6)))
    draw.text((left, 214), "All Types of Books", font=fit(draw, "All Types of Books", SANS_BLACK, 70, col), fill=TEXT)
    draw.text((left, 296), "Free PDF Library", font=fit(draw, "Free PDF Library", SANS_BLACK, 70, col), fill=GOLD_2)
    draw.text(
        (left, 398),
        "Read online in your browser",
        font=fit(draw, "Read online in your browser", SANS, 29, col),
        fill=MUTED,
    )
    draw.text(
        (left, 442),
        "or download the PDF — free.",
        font=fit(draw, "or download the PDF — free.", SANS, 29, col),
        fill=MUTED,
    )

    stats = []
    if books:
        cats = len({b.get("category") for b in books})
        stats.append((f"{len(books):,} books · {cats} categories", GOLD))
    stats.append(("100% free", (125, 211, 252)))
    x = left
    for text, colour in stats:
        x += pill(draw, x, 512, text, colour) + 16

    draw.rectangle([0, H - 6, W, H], fill=GOLD)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.convert("RGB").save(OUT, "JPEG", quality=88, optimize=True, progressive=True)
    print(f"{OUT}  {W}x{H}  {os.path.getsize(OUT) // 1024} KB")


if __name__ == "__main__":
    build()