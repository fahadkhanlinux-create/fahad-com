#!/usr/bin/env python3
"""Point every book's cover at its rendered page-1 thumbnail.

Reads data/books.json, rewrites the cover field to assets/thumbs/<id><ext> and
mirrors the same records into data/catalog.json. Run after tools/build_thumbs.py.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_thumbs import THUMB_EXT  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THUMB_DIR = os.path.join(BASE, "assets", "thumbs")
BOOKS = os.path.join(BASE, "data", "books.json")
CATALOG = os.path.join(BASE, "data", "catalog.json")

CATALOG_FIELDS = ["id", "title", "author", "year", "category", "size", "pages", "cover", "desc"]


def thumb_for(bid):
    if os.path.exists(os.path.join(THUMB_DIR, bid + THUMB_EXT)):
        return "assets/thumbs/%s%s" % (bid, THUMB_EXT)
    return None


def main():
    books = json.load(open(BOOKS, encoding="utf-8"))
    local = 0
    catalog = []
    for b in books:
        t = thumb_for(b["id"])
        if t:
            b["cover"] = t
            local += 1
        catalog.append({k: b.get(k, "") for k in CATALOG_FIELDS})

    with open(BOOKS, "w", encoding="utf-8") as f:
        json.dump(books, f, ensure_ascii=False, separators=(",", ":"))
    with open(CATALOG, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, separators=(",", ":"))

    missing = len(books) - local
    print("covers: %d/%d books point at a local thumbnail (%d without art)"
          % (local, len(books), missing))
    print("books.json %.1f MB | catalog.json %.1f MB"
          % (os.path.getsize(BOOKS) / 1048576, os.path.getsize(CATALOG) / 1048576))


if __name__ == "__main__":
    main()