#!/usr/bin/env python3
"""Re-render every PDF and every thumbnail in the library, then refresh the manifests.

build_library.py only ever renders books it is adding, so a change to the title page or
to the renderer was invisible to the rest of the library: the PDFs stayed on the old
layout and the cards kept showing the old covers. This walks data/books.json instead,
rebuilds each PDF from its cached text, re-renders each thumbnail from the new PDF, and
recomputes size/page-count so the manifests match what is actually on disk.

Texts come from tools/txt, so this is entirely offline.
"""
import json
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_library as lib  # noqa: E402

BASE = lib.BASE
PDF_DIR = lib.PDF_DIR
TXT_DIR = lib.TXT_DIR
THUMB_DIR = os.path.join(BASE, "assets", "thumbs")
PROCS = int(os.environ.get("REBUILD_PROCS", str(max(2, (os.cpu_count() or 4) - 1))))


def rebuild_pdf(b):
    """Re-render one book from its cached text. Never deletes the existing PDF."""
    bid = b["id"]
    txt = os.path.join(TXT_DIR, bid + ".txt")
    if not os.path.exists(txt) or os.path.getsize(txt) < 8000:
        return bid, "no-text"
    try:
        from build_books import build_pdf
        build_pdf(b)
        return bid, "built"
    except Exception as e:
        return bid, f"error: {type(e).__name__}: {e}"[:120]


def rebuild_thumb(b):
    """Render page 1 of the freshly built PDF into the card thumbnail."""
    bid = b["id"]
    pdf = os.path.join(PDF_DIR, bid + ".pdf")
    dest = os.path.join(THUMB_DIR, bid + ".jpg")
    tmp = os.path.join(TXT_DIR, ".thumb-%s.png" % bid)
    try:
        import subprocess
        from PIL import Image
        subprocess.run(
            ["mutool", "draw", "-o", tmp, "-r", "110", "-F", "png", pdf, "1"],
            check=True, capture_output=True, timeout=120,
        )
        with Image.open(tmp) as im:
            im = im.convert("RGB")
            im.thumbnail((420, 840), Image.LANCZOS)
            im.save(dest, "JPEG", quality=72, optimize=True, progressive=True)
        return bid, "built"
    except Exception as e:
        return bid, f"error: {type(e).__name__}: {e}"[:120]
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def main():
    books = json.load(open(lib.DATA, encoding="utf-8"))
    only = set(sys.argv[1:])
    if only:
        books = [b for b in books if b["id"] in only]
    books = [b for b in books if os.path.exists(os.path.join(PDF_DIR, b["id"] + ".pdf"))]
    print("rebuilding %d books with %d workers" % (len(books), PROCS), flush=True)

    t0 = time.time()
    stats = Counter()
    for n, (bid, status) in enumerate(lib._map_processes(books, rebuild_pdf, PROCS, "pdf"), 1):
        stats[status.split(":")[0]] += 1
        if n % 250 == 0 or n == len(books):
            print("  pdf %d/%d %s (%.0fs)" % (n, len(books), dict(stats), time.time() - t0), flush=True)
    print("pdfs: %s in %.0fs" % (dict(stats), time.time() - t0), flush=True)

    t0 = time.time()
    stats = Counter()
    for n, (bid, status) in enumerate(lib._map_processes(books, rebuild_thumb, PROCS, "thumb"), 1):
        stats[status.split(":")[0]] += 1
        if n % 500 == 0 or n == len(books):
            print("  thumb %d/%d %s (%.0fs)" % (n, len(books), dict(stats), time.time() - t0), flush=True)
    print("thumbs: %s in %.0fs" % (dict(stats), time.time() - t0), flush=True)

    if only:
        return

    # sizes and page counts changed with the new renderer, so refresh every record
    t0 = time.time()
    entries = json.load(open(lib.DATA, encoding="utf-8"))
    paths = [os.path.join(PDF_DIR, e["id"] + ".pdf") for e in entries]
    lib._pagecounts.clear()
    lib.prewarm_pagecounts([p for p in paths if os.path.exists(p)])
    changed = 0
    for e in entries:
        pdf = os.path.join(PDF_DIR, e["id"] + ".pdf")
        if not os.path.exists(pdf):
            continue
        size = os.path.getsize(pdf)
        pages = lib.pdf_pages(pdf)
        if e.get("size") != size or e.get("pages") != pages:
            changed += 1
        e["size"] = size
        e["pages"] = pages
    lib.save_pagecounts()
    entries.sort(key=lambda e: (e["category"], e["title"].lower()))
    with open(lib.DATA, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=1, ensure_ascii=False)
    lite = [
        {
            "id": e["id"], "title": e["title"], "author": e["author"],
            "year": e["year"], "category": e["category"], "size": e["size"],
            "pages": e["pages"], "cover": e.get("cover", ""),
            "desc": (e["desc"][:170].rsplit(" ", 1)[0] + "…") if len(e["desc"]) > 170 else e["desc"],
        }
        for e in entries
    ]
    with open(lib.LITE, "w", encoding="utf-8") as f:
        json.dump(lite, f, separators=(",", ":"), ensure_ascii=False)
    print("manifests refreshed: %d records, %d changed (%.0fs)" % (len(entries), changed, time.time() - t0), flush=True)


if __name__ == "__main__":
    main()