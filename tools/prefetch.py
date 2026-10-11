#!/usr/bin/env python3
"""Pre-download Gutenberg texts for the books this run will actually publish."""
import os
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "tools"))
from build_library import download_text, select_books  # noqa: E402

WORKERS = int(os.environ.get("DL_WORKERS", "8"))


def main():
    books = select_books()
    print(f"prefetching {len(books)} books with {WORKERS} workers", flush=True)

    stats = Counter()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(download_text, b): b for b in books}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                stats[f.result()[1]] += 1
            except Exception:
                stats["error"] += 1
            if i % 100 == 0:
                print(f"{i}/{len(books)} {dict(stats)}", flush=True)
    print(f"prefetch done: {dict(stats)}", flush=True)


if __name__ == "__main__":
    main()