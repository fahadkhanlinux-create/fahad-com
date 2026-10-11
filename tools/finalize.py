#!/usr/bin/env python3
"""Write data/books.json + data/catalog.json + sitemap.xml from the PDFs on disk."""
import json
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "tools"))
from build_library import (  # noqa: E402
    PDF_DIR, _entry, _index_gids, pdf_pages, save_pagecounts, select_books,
    write_outputs,
)


def main():
    books = select_books(exclude_published=False)
    _index_gids(books)
    entries = []
    for b in books:
        pdf = os.path.join(PDF_DIR, b["id"] + ".pdf")
        if not os.path.exists(pdf):
            continue
        # no year for bulk titles: the front-matter scan mislabels reprints and
        # ancient works, and a wrong year is worse than none
        b["year"] = ""
        entries.append(_entry(
            b["id"], b["title"], b["author"], b["year"], b["category"], b["desc"], pdf,
        ))

    all_entries = write_outputs(entries)
    save_pagecounts()
    total = sum(e["size"] for e in all_entries)
    print(f"books.json: {len(all_entries)} books, {total/1048576:.0f} MB of PDFs")
    print(f"  new this run: {len(entries)}")

    subprocess.run([sys.executable, os.path.join(BASE, "tools", "build_sitemap.py")], check=True)


if __name__ == "__main__":
    main()