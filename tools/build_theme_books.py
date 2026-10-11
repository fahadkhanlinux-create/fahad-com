#!/usr/bin/env python3
"""Download + render the theme books selected by select_themes.py.

Reuses build_library's hardened downloader/renderer so the new books are produced by
exactly the same pipeline that built the existing 6628. Resumable: any text or PDF
already on disk is skipped, so re-running after an interruption is cheap.
"""
import json
import os
import sys
import time
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "tools"))

from build_library import (  # noqa: E402
    DL_WORKERS, PDF_DIR, PDF_PROCS, _map_processes, _map_threads,
    download_text, render,
)

SEL = os.path.join(BASE, "tools", "theme_selection.json")
MIN_BYTES = 5000


def main():
    books = json.load(open(SEL, encoding="utf-8"))
    print(f"selected {len(books)} theme books; dl_workers={DL_WORKERS} pdf_procs={PDF_PROCS}",
          flush=True)

    # --- phase 1: texts -----------------------------------------------------
    print("--- phase 1: texts ---", flush=True)
    t0 = time.time()
    tstats = Counter()
    for i, r in enumerate(_map_threads(books, download_text, DL_WORKERS, "text"), 1):
        tstats[r[1].split(":")[0]] += 1
        if i % 25 == 0 or i == len(books):
            print(f"  text {i}/{len(books)} {dict(tstats)} ({time.time()-t0:.0f}s)", flush=True)
    print(f"texts: {dict(tstats)} in {time.time()-t0:.0f}s", flush=True)

    # --- phase 2: pdfs ------------------------------------------------------
    print("--- phase 2: pdfs ---", flush=True)
    t0 = time.time()
    results = Counter()
    ok = []
    for i, r in enumerate(_map_processes(books, render, PDF_PROCS, "pdf"), 1):
        status = r[1].split(":")[0]
        results[status] += 1
        if r[1] in ("built", "cached"):
            ok.append(r[0])
        if i % 25 == 0 or i == len(books):
            print(f"  pdf {i}/{len(books)} {dict(results)} ({time.time()-t0:.0f}s)", flush=True)
    print(f"pdfs: {dict(results)} in {time.time()-t0:.0f}s", flush=True)

    # --- report which selections produced a PDF ----------------------------
    okset = set(ok)
    out = [b for b in books if b["id"] in okset
           and os.path.exists(os.path.join(PDF_DIR, b["id"] + ".pdf"))
           and os.path.getsize(os.path.join(PDF_DIR, b["id"] + ".pdf")) >= MIN_BYTES]
    with open(os.path.join(BASE, "tools", "theme_built.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"\nrendered {len(out)}/{len(books)} -> tools/theme_built.json")
    print("per category:", dict(Counter(b["category"] for b in out)))
    if results.get("error"):
        print("NOTE: some books failed to render; they are listed as not built above")


if __name__ == "__main__":
    main()