#!/usr/bin/env python3
"""Refresh size and page count for every book and rewrite the manifests.

The cover pass rewrites every PDF, so the byte sizes and page counts cached in
data/books.json no longer match what is on disk. The catalog is what the site ships, so
it has to be regenerated before staging a deployment.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_library as lib  # noqa: E402

BASE = lib.BASE


def main():
    entries = json.load(open(lib.DATA, encoding="utf-8"))
    t0 = time.time()
    lib._pagecounts.clear()
    paths = [os.path.join(lib.PDF_DIR, e["id"] + ".pdf") for e in entries]
    lib.prewarm_pagecounts([p for p in paths if os.path.exists(p)])

    changed = 0
    kept = []
    for e in entries:
        pdf = os.path.join(lib.PDF_DIR, e["id"] + ".pdf")
        if not os.path.exists(pdf):
            print("  missing pdf, dropped from manifest:", e["id"])
            continue
        size = os.path.getsize(pdf)
        pages = lib.pdf_pages(pdf)
        if e.get("size") != size or e.get("pages") != pages:
            changed += 1
        e["size"] = size
        e["pages"] = pages
        kept.append(e)
    lib.save_pagecounts()

    kept.sort(key=lambda e: (e["category"], e["title"].lower()))
    with open(lib.DATA, "w", encoding="utf-8") as f:
        json.dump(kept, f, indent=1, ensure_ascii=False)
    lite = [
        {
            "id": e["id"], "title": e["title"], "author": e["author"],
            "year": e["year"], "category": e["category"], "size": e["size"],
            "pages": e["pages"], "cover": e.get("cover", ""),
            "desc": (e["desc"][:170].rsplit(" ", 1)[0] + "…") if len(e["desc"]) > 170 else e["desc"],
        }
        for e in kept
    ]
    with open(lib.LITE, "w", encoding="utf-8") as f:
        json.dump(lite, f, separators=(",", ":"), ensure_ascii=False)
    total = sum(e["size"] for e in kept)
    print("manifest: %d books, %d refreshed, %.0f MB of PDFs (%.0fs)"
          % (len(kept), changed, total / 1048576, time.time() - t0))


if __name__ == "__main__":
    main()