#!/usr/bin/env python3
"""Recover texts for Gutenberg books that ship no plain-text/HTML edition.

The mathematics and logic shelf this run selected is a large share of editions that
Project Gutenberg only mirrors as a PDF or a LaTeX source: every pg*.txt and *.html
path 404s. Rather than drop those books -- they are exactly the AI/logic lineage the
catalogue is missing -- pull the text back out of the PDF that is always available.

Usage: fetch_fallback_texts.py <selection.json> [...]
Writes tools/txt/<book id>.txt for every book whose text is still missing.
"""
import json
import os
import re
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TXT_DIR = os.path.join(BASE, "tools", "txt")

UA = "Mozilla/5.0 (X11; Linux x86_64) fahad-com-book-library/1.0"
# short pamphlets (e.g. "The Secret Guide to Computers", 20 KB) are legitimate books
# even though they clear none of the usual "big enough" bars, so this stays low
MIN_CHARS = 4000
MAX_MB = 12

PDF_URLS = [
    "https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.pdf",
    "https://www.gutenberg.org/files/{gid}/{gid}-pdf.pdf",
    "https://www.gutenberg.org/files/{gid}/{gid}.pdf",
]


def fetch(url, timeout=25):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def pdf_to_text(blob, gid):
    """Extract a plain-text body from a Gutenberg PDF."""
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(blob))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    text = "\n\n".join(parts)
    # Gutenberg PDFs open with licence boilerplate and close with the licence again;
    # keep only the body so the rendered book starts at the title
    m = re.search(
        r"(?im)^\s*(?:this etext|the project gutenberg ebook|start of (?:the )?"
        r"project gutenberg)\b.*?\*\*\*\s*start of (?:the|this) project gutenberg",
        text,
    )
    if m:
        text = text[m.end():]
    m = re.search(r"(?im)^\s*\*\*\*\s*end of (?:the|this) project gutenberg", text)
    if m:
        text = text[: m.start()]
    # a page-1 thumbnail of the title page must not dominate the description
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def ensure_text(book):
    bid = book["id"]
    path = os.path.join(TXT_DIR, bid + ".txt")
    if os.path.exists(path) and os.path.getsize(path) > MIN_CHARS:
        return bid, "cached"
    gid = book["gid"]
    for tmpl in PDF_URLS:
        url = tmpl.format(gid=gid)
        blob = fetch(url)
        if not blob or len(blob) < 20000:
            continue
        if len(blob) > MAX_MB * 1024 * 1024:
            return bid, "too-big"
        try:
            text = pdf_to_text(blob, gid)
        except Exception as e:
            return bid, f"error: {type(e).__name__}"
        if len(text) > MIN_CHARS:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            return bid, "recovered"
        return bid, "empty-extract"
    return bid, "failed"


def main():
    selections = sys.argv[1:] or [os.path.join(BASE, "tools", "theme_selection.json")]
    books = []
    for s in selections:
        books += json.load(open(s, encoding="utf-8"))

    # only the ones still missing a usable text
    todo = []
    for b in books:
        p = os.path.join(TXT_DIR, b["id"] + ".txt")
        if os.path.exists(p) and os.path.getsize(p) > MIN_CHARS:
            continue
        if os.path.exists(os.path.join(BASE, "pdfs", b["id"] + ".pdf")):
            # already rendered, so its text is not the blocker
            continue
        todo.append(b)

    print(f"recovering {len(todo)} books with no text", flush=True)
    stats = {}
    t0 = time.time()
    for n, b in enumerate(todo, 1):
        _bid, status = ensure_text(b)
        stats[status] = stats.get(status, 0) + 1
        if n % 10 == 0 or n == len(todo):
            print(f"  {n}/{len(todo)} {stats} ({time.time()-t0:.0f}s)", flush=True)
    print(f"done: {stats}")


if __name__ == "__main__":
    main()