#!/usr/bin/env python3
"""Render page 1 of every PDF into a small local JPEG thumbnail.

The site previously hot-linked Gutenberg's cover endpoint, which 404s for a large
share of the catalogue and adds a third-party request per card. Rendering our own
page-1 thumbnail guarantees every card has art, works offline and costs one
request served from our own CDN.
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_DIR = os.path.join(BASE, "pdfs")
THUMB_DIR = os.path.join(BASE, "assets", "thumbs")
BOOKS = os.path.join(BASE, "data", "books.json")

MAX_EDGE = 420
JPEG_QUALITY = 72
# rebuild every thumbnail even when one is already on disk; needed after the PDFs
# themselves change (a new cover page, for instance)
FORCE = os.environ.get("FORCE_THUMBS") == "1"


def _render(job):
    bid, tmp_png = job
    dest = os.path.join(THUMB_DIR, bid + ".jpg")
    if not FORCE and os.path.exists(dest) and os.path.getsize(dest) > 1024:
        return bid, "cached", 0
    pdf = os.path.join(PDF_DIR, bid + ".pdf")
    try:
        # 110 dpi keeps the title page legible at card size without bloating bytes
        subprocess.run(
            ["mutool", "draw", "-o", tmp_png, "-r", "110", "-F", "png", pdf, "1"],
            check=True, capture_output=True, timeout=60,
        )
        from PIL import Image
        with Image.open(tmp_png) as im:
            im = im.convert("RGB")
            im.thumbnail((MAX_EDGE, MAX_EDGE * 2), Image.LANCZOS)
            im.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
        size = os.path.getsize(dest)
    except Exception:
        if os.path.exists(dest):
            os.remove(dest)
        return bid, "failed", 0
    finally:
        if os.path.exists(tmp_png):
            os.remove(tmp_png)
    return bid, "built", size


def main():
    os.makedirs(THUMB_DIR, exist_ok=True)
    books = json.load(open(BOOKS, encoding="utf-8"))
    jobs = []
    tmp_dir = os.path.join(BASE, "tools", ".thumbtmp")
    os.makedirs(tmp_dir, exist_ok=True)
    for n, b in enumerate(books):
        if not os.path.exists(os.path.join(PDF_DIR, b["id"] + ".pdf")):
            continue
        jobs.append((b["id"], os.path.join(tmp_dir, "%d.png" % n)))

    total = len(jobs)
    print("thumbnails: %d PDFs to render" % total, flush=True)
    done = {"cached": 0, "built": 0, "failed": 0}
    bytes_total = 0
    with ProcessPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(_render, j) for j in jobs]
        for n, fut in enumerate(as_completed(futs), 1):
            bid, status, size = fut.result()
            done[status] += 1
            bytes_total += size
            if n % 250 == 0 or n == total:
                print("  %d/%d %s" % (n, total, done), flush=True)

    print("thumbs: %d built, %d cached, %d failed, %.1f MB total"
          % (done["built"], done["cached"], done["failed"],
             sum(os.path.getsize(os.path.join(THUMB_DIR, f))
                 for f in os.listdir(THUMB_DIR)) / 1048576), flush=True)
    try:
        os.rmdir(tmp_dir)
    except OSError:
        pass
    return 1 if done["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())