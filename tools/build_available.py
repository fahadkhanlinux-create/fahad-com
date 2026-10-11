#!/usr/bin/env python3
"""Render PDFs for every selected book whose text is already on disk."""
import os
import sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "tools"))
from build_library import (  # noqa: E402
    PDF_PROCS, TXT_DIR, PDF_DIR, render, select_books, _map_processes,
)


def main():
    books = select_books()
    ready = [b for b in books if os.path.exists(os.path.join(TXT_DIR, b["id"] + ".txt"))]
    todo = [b for b in ready if not os.path.exists(os.path.join(PDF_DIR, b["id"] + ".pdf"))]
    # smallest first: steady progress, and partial results stay useful if interrupted
    todo.sort(key=lambda b: os.path.getsize(os.path.join(TXT_DIR, b["id"] + ".txt")))
    print(f"selected={len(books)} text-ready={len(ready)} pdf-missing={len(todo)} procs={PDF_PROCS}", flush=True)

    stats = Counter()
    for i, (bid, state) in enumerate(_map_processes(todo, render, PDF_PROCS, "pdf"), 1):
        stats[state if state in ("cached", "built", "failed", "too-big", "unsupported-script", "reference-volume") else "error"] += 1
        if i % 50 == 0:
            print(f"  {i}/{len(todo)} {dict(stats)}", flush=True)
    print(f"render done: {dict(stats)}", flush=True)


if __name__ == "__main__":
    main()