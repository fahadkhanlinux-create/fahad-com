#!/usr/bin/env python3
"""Merge the theme books into data/books.json + data/catalog.json, then write sitemap.xml.

The new books are appended to the existing manifest rather than re-selecting the whole
library: select_books() would keep finding the same un-added Gutenberg titles and could
pull thousands of unrelated ones in. Each record is built exactly like the existing ones
so the front-end needs no changes.
"""
import json
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "tools"))

from build_library import _entry, _index_gids, pdf_pages, save_pagecounts  # noqa: E402

DATA = os.path.join(BASE, "data", "books.json")
LITE = os.path.join(BASE, "data", "catalog.json")
BUILT = os.path.join(BASE, "tools", "theme_built.json")
PDF_DIR = os.path.join(BASE, "pdfs")
PAGECOUNTS = os.path.join(BASE, "tools", "pagecounts.json")


def main():
    books = json.load(open(DATA, encoding="utf-8"))
    known = {b["id"] for b in books}
    _index_gids([dict(b, gid=b.get("gid")) for b in books])

    new = json.load(open(BUILT, encoding="utf-8"))
    added, skipped = 0, 0
    for b in new:
        if b["id"] in known:
            skipped += 1
            continue
        pdf = os.path.join(PDF_DIR, b["id"] + ".pdf")
        if not os.path.exists(pdf) or os.path.getsize(pdf) < 5000:
            skipped += 1
            continue
        rec = _entry(b["id"], b["title"], b["author"], b.get("year", ""),
                     b["category"], b["desc"], pdf)
        rec["gid"] = b["gid"]
        books.append(rec)
        known.add(b["id"])
        added += 1

    books.sort(key=lambda e: (e["category"], e["title"].lower()))
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(books, f, indent=1, ensure_ascii=False)

    lite = [
        {
            "id": e["id"], "title": e["title"], "author": e["author"],
            "year": e["year"], "category": e["category"], "size": e["size"],
            "pages": e["pages"], "cover": e.get("cover", ""),
            "desc": (e["desc"][:170].rsplit(" ", 1)[0] + "…") if len(e["desc"]) > 170 else e["desc"],
        }
        for e in books
    ]
    with open(LITE, "w", encoding="utf-8") as f:
        json.dump(lite, f, separators=(",", ":"), ensure_ascii=False)

    total = sum(e["size"] for e in books)
    print(f"added {added}, skipped {skipped}")
    print(f"books.json: {len(books)} books, {total/1048576:.0f} MB of PDFs")

    subprocess.run([sys.executable, os.path.join(BASE, "tools", "build_sitemap.py")], check=True)


if __name__ == "__main__":
    main()