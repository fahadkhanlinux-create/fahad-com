#!/usr/bin/env python3
"""Bulk-add ~1000 public-domain books from Project Gutenberg."""
import html
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "tools"))
from build_books import build_pdf, slug, fetch_text, BOOKS  # noqa: E402

DATA = os.path.join(BASE, "data", "books.json")
PDF_DIR = os.path.join(BASE, "pdfs")
CACHE = os.path.join(BASE, "tools", "guten_catalog.json")
TARGET = int(os.environ.get("BULK_TARGET", "1000"))

CAT_MAP = [
    ("Children", ["children", "juvenile", "fairy", "juveniles"]),
    ("Poetry", ["poetry", "poems", "verse"]),
    ("Philosophy", ["philosophy"]),
    ("Psychology", ["psychology", "psychanalysis", "psychiatry"]),
    ("Science", ["science", "physics", "biology", "chemistry", "mathematics", "astronomy", "natural history"]),
    ("History", ["history", "historians"]),
    ("Business", ["business", "economics", "commerce", "finance"]),
    ("Strategy", ["strategy", "military"]),
    ("Self-Help", ["self-help", "conduct of life", "success"]),
    ("Technology", ["technology", "engineering", "inventions"]),
    ("Islam & Religion", ["religion", "bibles", "theology", "christian", "islam", "quran"]),
]


def http_get(url, tries=4, timeout=10):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (fahad-books)"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            if a == tries - 1:
                raise
            time.sleep(2 * (a + 1))


def scrape_catalog():
    out = []
    if os.path.exists(CACHE):
        out = json.load(open(CACHE, encoding="utf-8"))
        if len(out) >= TARGET * 2:
            return out
    start = len(out) + 1
    while len(out) < TARGET * 2:
        url = f"https://www.gutenberg.org/ebooks/search/?sort_order=downloads&languages=en&start_index={start}"
        page = http_get(url)
        blocks = re.findall(r'<li class="booklink">(.*?)</li>', page, re.S)
        if not blocks:
            break
        for b in blocks:
            m = re.search(r'href="/ebooks/(\d+)"', b)
            t = re.search(r'<span class="title">(.*?)</span>', b, re.S)
            a = re.search(r'<span class="subtitle">(.*?)</span>', b, re.S)
            if m and t:
                out.append({
                    "gid": int(m.group(1)),
                    "title": html.unescape(re.sub(r"<.*?>", "", t.group(1))).strip(),
                    "author": html.unescape(re.sub(r"<.*?>", "", a.group(1))).strip() if a else "Unknown",
                })
        print(f"catalog: {len(out)}", flush=True)
        start += 25
        time.sleep(1)
    json.dump(out, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return out


def guess_category(subjects):
    s = " ".join(subjects).lower()
    for cat, kws in CAT_MAP:
        if any(k in s for k in kws):
            return cat
    return "Fiction"


def fetch_subjects(gid):
    try:
        page = http_get(f"https://www.gutenberg.org/ebooks/{gid}")
        subs = re.findall(r'<td class="tablecell">\s*<a[^>]*>(.*?)</a>', page)
        # subjects are links in the Subject row; grab text after 'Subject' header
        m = re.search(r"Subject</th>(.*?)</tr>", page, re.S)
        subjects = []
        if m:
            subjects = [html.unescape(re.sub(r"<.*?>", "", x)).strip() for x in re.findall(r">([^<>]+)<", m.group(1))]
        return [s for s in subjects if s]
    except Exception:
        return []


def main():
    catalog = scrape_catalog()
    existing = json.load(open(DATA, encoding="utf-8")) if os.path.exists(DATA) else []
    existing_gids = set()
    for e in existing:
        m = re.search(r"pg(\d+)", e.get("file", ""))
        existing_ids = e["id"]
    existing_gids = {b["gid"] for b in BOOKS}
    existing_keys = {(e["title"].strip().lower(), e["author"].strip().lower()) for e in existing}

    candidates = []
    for c in catalog:
        if c["gid"] in existing_gids:
            continue
        if (c["title"].strip().lower(), c["author"].strip().lower()) in existing_keys:
            continue
        candidates.append(c)
        if len(candidates) >= TARGET:
            break

    print(f"{len(candidates)} new candidates", flush=True)

    # fetch subjects concurrently for category guessing
    CATS_CACHE = os.path.join(BASE, "tools", "guten_cats.json")
    cats = json.load(open(CATS_CACHE, encoding="utf-8")) if os.path.exists(CATS_CACHE) else {}
    todo = [c for c in candidates if str(c["gid"]) not in cats]
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_subjects, c["gid"]): c["gid"] for c in todo}
        for i, f in enumerate(as_completed(futs), 1):
            gid = futs[f]
            try:
                cats[str(gid)] = guess_category(f.result())
            except Exception:
                cats[str(gid)] = "Fiction"
            if i % 50 == 0:
                print(f"subjects {i}/{len(todo)}", flush=True)
                json.dump(cats, open(CATS_CACHE, "w", encoding="utf-8"))
    json.dump(cats, open(CATS_CACHE, "w", encoding="utf-8"))

    books = []
    for c in candidates:
        bid = f"{slug(c['title'])[:60]}-{c['gid']}"
        books.append(dict(
            id=bid, gid=c["gid"], title=c["title"], author=c["author"],
            year="", category=cats.get(str(c["gid"]), "Fiction"),
            desc=f"{c['title']} by {c['author']} — a free public-domain book from Project Gutenberg.",
        ))

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(fetch_text, b): b for b in books}
        for f in as_completed(futs):
            try:
                f.result()
            except Exception as e:
                books.remove(futs[f])
                print(f"  skip {futs[f]['title']}: {e}", flush=True)

    ok = []
    for i, b in enumerate(books, 1):
        try:
            print(f"[{i}/{len(books)}] {b['title']}", flush=True)
            build_pdf(b)
            ok.append(b)
        except Exception as e:
            print(f"  FAILED {b['title']}: {e}", flush=True)

    from pypdf import PdfReader
    entries = list(existing)
    for b in ok:
        pdf = os.path.join(PDF_DIR, b["id"] + ".pdf")
        try:
            pages = len(PdfReader(pdf).pages)
        except Exception:
            pages = None
        entries.append({
            "id": b["id"], "title": b["title"], "author": b["author"],
            "year": b["year"], "category": b["category"], "desc": b["desc"],
            "file": f"pdfs/{b['id']}.pdf", "size": os.path.getsize(pdf), "pages": pages,
        })
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    print(f"Done: {len(entries)} books total, {len(ok)} new", flush=True)


if __name__ == "__main__":
    main()
