#!/usr/bin/env python3
"""Swap page 1 of every PDF for a freshly drawn cover.

Re-rendering a whole book through reportlab costs seconds per title (justified
Paragraph layout dominates), which is hours for a library this size. The cover is the
only page that changed, so this rewrites nothing else: it draws one page and rebuilds
the file as [new cover] + [existing pages 2..n], leaving every body page byte-identical.

Books already carrying the new cover are skipped, so the pass is safe to re-run.
"""
import json
import os
import sys
import tempfile
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_library as lib  # noqa: E402

BASE = lib.BASE
PDF_DIR = lib.PDF_DIR
PROCS = int(os.environ.get("COVER_PROCS", str(max(2, (os.cpu_count() or 4) - 1))))
# which ids this pass has already rewritten, so a re-run costs nothing
STATE = os.path.join(BASE, "tools", "cover_fixed.json")


def fix_cover(b):
    from pypdf import PdfReader, PdfWriter

    from build_books import make_cover_pdf

    bid = b["id"]
    path = os.path.join(PDF_DIR, bid + ".pdf")
    try:
        reader = PdfReader(path)
        if len(reader.pages) == 0:
            return bid, "empty"

        fd, cover_path = tempfile.mkstemp(suffix=".pdf", dir=PDF_DIR)
        os.close(fd)
        try:
            make_cover_pdf(b, cover_path)
            cover = PdfReader(cover_path)
            writer = PdfWriter()
            writer.add_page(cover.pages[0])
            for page in reader.pages[1:]:
                writer.add_page(page)
            if reader.metadata:
                writer.add_metadata({k: v for k, v in reader.metadata.items() if v})
            out = path + ".new"
            with open(out, "wb") as f:
                writer.write(f)
            os.replace(out, path)
        finally:
            if os.path.exists(cover_path):
                os.remove(cover_path)
        return bid, "fixed"
    except Exception as e:
        return bid, f"error: {type(e).__name__}: {e}"[:140]


def main():
    books = json.load(open(lib.DATA, encoding="utf-8"))
    only = set(sys.argv[1:])
    if only:
        books = [b for b in books if b["id"] in only]
    done = set()
    if os.path.exists(STATE):
        done = set(json.load(open(STATE, encoding="utf-8")))
    if not only:
        books = [b for b in books if os.path.exists(os.path.join(PDF_DIR, b["id"] + ".pdf"))
                 and b["id"] not in done]
    print("cover pass: %d books, %d workers, %d already done"
          % (len(books), PROCS, len(done)), flush=True)

    t0 = time.time()
    stats = Counter()
    for n, (bid, status) in enumerate(lib._map_processes(books, fix_cover, PROCS, "cover"), 1):
        stats[status.split(":")[0]] += 1
        if status == "fixed":
            done.add(bid)
        if n % 250 == 0 or n == len(books):
            with open(STATE, "w", encoding="utf-8") as f:
                json.dump(sorted(done), f)
            rate = n / max(0.1, time.time() - t0)
            print("  %d/%d %s (%.0fs, %.0f/s, eta %.0fmin)"
                  % (n, len(books), dict(stats), time.time() - t0, rate,
                     (len(books) - n) / rate / 60), flush=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(sorted(done), f)
    print("covers: %s in %.0fs" % (dict(stats), time.time() - t0), flush=True)


if __name__ == "__main__":
    main()