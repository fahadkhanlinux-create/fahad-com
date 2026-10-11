#!/usr/bin/env python3
"""Build the Fahad.com library: download Gutenberg texts, render PDFs, write data/books.json.

Resumable — existing .txt and .pdf files are skipped.
"""
import html as html_lib
import json
import multiprocessing as mp
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "tools"))

TXT_DIR = os.path.join(BASE, "tools", "txt")
PDF_DIR = os.path.join(BASE, "pdfs")
DATA = os.path.join(BASE, "data", "books.json")
LITE = os.path.join(BASE, "data", "catalog.json")
CATALOG = os.path.join(BASE, "tools", "guten_catalog.json")
META = os.path.join(BASE, "tools", "guten_meta.json")
CLASSIFIED = os.path.join(BASE, "tools", "guten_classified.json")

TARGET = int(os.environ.get("LIB_TARGET", "2100"))
DL_WORKERS = int(os.environ.get("DL_WORKERS", "6"))
PDF_PROCS = int(os.environ.get("PDF_PROCS", str(max(2, (os.cpu_count() or 4) - 1))))
CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿豈-﫿가-힯]")
# Rendering cost scales with text length, and the long tail here is reference material
# rather than readable books (unabridged dictionaries, fact books, encyclopaedia volumes):
# a 40 MB text is a 3000+ page PDF that takes the better part of an hour to typeset and
# weighs tens of MB on every request. 4 MB still covers ~99% of ordinary books.
MAX_TXT_MB = float(os.environ.get("MAX_TXT_MB", "4"))
FICTION_SHARE = float(os.environ.get("FICTION_SHARE", "0.40"))
CJK_TOLERANCE = float(os.environ.get("CJK_TOLERANCE", "0.02"))

UA = "Mozilla/5.0 (X11; Linux x86_64) fahad-com-book-library/1.0"
# hard ceiling on any single network call: a hung connection must fail fast so the build
# moves on to the next book instead of stalling the worker
HTTP_TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", "10"))
GUTENBERG_END = re.compile(
    r"END OF (THE|THIS) PROJECT GUTENBERG|END-OF-PROJECT-GUTENBERG|End of (the|this) Project Gutenberg", re.I
)
GUTENBERG_START = re.compile(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG EBOOK[^\n]*\n", re.I)
BAD_TITLE = re.compile(r"^(the )?project gutenberg", re.I)
LATIN_OK = re.compile(r"[A-Za-z0-9À-ɏ&,'’\-\.:()! ]")
NON_LATIN_TITLES = float(os.environ.get("NON_LATIN_TITLES", "0.3"))


def mostly_non_latin(text):
    """The library is English-language; CJK/Cyrillic titles are not useful here."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    frac = sum(0 if LATIN_OK.match(c) else 1 for c in letters) / len(letters)
    return frac > NON_LATIN_TITLES

TEXT_URLS = [
    "https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt",
    "https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt.utf-8",
    "https://www.gutenberg.org/cache/epub/{gid}/pg{gid}-0.txt",
    "https://www.gutenberg.org/ebooks/{gid}.txt.utf-8",
    # older editions are only mirrored under the /files/ tree and never under /cache/epub,
    # which is why the whole mathematics shelf 404'd on every path above
    "https://www.gutenberg.org/files/{gid}/{gid}-0.txt",
    "https://www.gutenberg.org/files/{gid}/{gid}.txt",
    "https://www.gutenberg.org/files/{gid}/{gid}-txt.txt",
]
HTML_URLS = [
    "https://www.gutenberg.org/cache/epub/{gid}/pg{gid}-images.html",
    "https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.html",
    "https://www.gutenberg.org/cache/epub/{gid}/pg{gid}-0.html",
    "https://www.gutenberg.org/files/{gid}/{gid}-h/{gid}-h.htm",
    "https://www.gutenberg.org/files/{gid}/{gid}.html",
]
BLOCK_TAG = re.compile(r"(?i)<(br|/p|/div|/h[1-6]|/li|/tr|/blockquote|/section)\b[^>]*>")
ANY_TAG = re.compile(r"(?s)<[^>]+>")


def html_to_text(doc):
    doc = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", " ", doc)
    doc = BLOCK_TAG.sub("\n", doc)
    doc = ANY_TAG.sub("", doc)
    doc = html_lib.unescape(doc)
    doc = doc.replace("\r\n", "\n").replace("\xa0", " ")
    doc = re.sub(r"[ \t]+", " ", doc)
    doc = re.sub(r"\n\s*\n\s*\n+", "\n\n", doc)
    return doc.strip() + "\n"


def _clean_text(data):
    m = GUTENBERG_START.search(data)
    if m:
        data = data[m.end():]
    m = re.search(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG EBOOK", data, re.I)
    if m:
        data = data[: m.start()]
    return data.replace("\r\n", "\n").strip() + "\n"


def _fetch(url, tries=3, timeout=HTTP_TIMEOUT):
    """Returns (body, None) or (None, 'missing'|'error').

    Every request is bounded so one slow response cannot stall the whole build: a timeout
    is retried a couple of times and then the book is reported as failed and skipped.
    """
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace"), None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None, "missing"
            time.sleep(3 * (a + 1))
        except Exception:
            time.sleep(3 * (a + 1))
    return None, "error"


# ---------------------------------------------------------------- text fetch

def download_text(b):
    os.makedirs(TXT_DIR, exist_ok=True)
    path = os.path.join(TXT_DIR, b["id"] + ".txt")
    if os.path.exists(path) and os.path.getsize(path) > 8000:
        return b["id"], "cached"

    gid = b["gid"]
    for tmpl in TEXT_URLS:
        body, _err = _fetch(tmpl.format(gid=gid))
        if body is None:
            continue
        data = _clean_text(body)
        if len(data) > 8000:
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
            return b["id"], "downloaded"
        break

    # newer Project Gutenberg editions ship no plain text — convert the HTML instead
    for tmpl in HTML_URLS:
        body, _err = _fetch(tmpl.format(gid=gid))
        if body is None:
            continue
        data = _clean_text(html_to_text(body))
        if len(data) > 8000:
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
            return b["id"], "from-html"
        break

    return b["id"], "failed"


# ---------------------------------------------------------------- pdf build

def render(b):
    from build_books import build_pdf

    pdf = os.path.join(PDF_DIR, b["id"] + ".pdf")
    if os.path.exists(pdf) and os.path.getsize(pdf) > 5000:
        return b["id"], "cached"
    txt = os.path.join(TXT_DIR, b["id"] + ".txt")
    try:
        if not os.path.exists(txt) or os.path.getsize(txt) < 8000:
            return b["id"], "failed"
        if os.path.getsize(txt) > MAX_TXT_MB * 1024 * 1024:
            return b["id"], "too-big"
        if b.get("reference-volume"):
            return b["id"], "reference-volume"
        if _mostly_unsupported_script(txt):
            return b["id"], "unsupported-script"
        build_pdf(b)
        return b["id"], "built"
    except Exception as e:
        return b["id"], f"error: {type(e).__name__}: {e}"[:160]


# multi-volume encyclopedias, dictionaries and collected-works editions render into
# 1000+ page PDFs that take minutes each and are not what a reader opens this library
# for, so they are flagged at selection time rather than ground through the renderer.
REFERENCE_VOLUME = re.compile(
    r"\b(encyclop(ae|e)dia|encyclop(ae|e)dic|"
    r"dictionary|lexicon|thesaurus|glossary|concordance|"
    r"complete[lr]? [a-z]* ?(works|writings|poems|poetical|poetic)\b|"
    r"(entire|complete)\b.*\bworks\b|"
    r"catalog(ue)? of\b|"
    r"world factbook|"
    r"cyclop(ae|e)dia)\b",
    re.I,
)


def is_reference_volume(b):
    title = (b.get("title") or "").strip()
    # a dictionary rule needs the unabridged/multivolume qualifier: "Webster's
    # Unabridged Dictionary" is one big book, "… Dictionary, Volume 2" is a set member
    if re.search(r"\bdictionar(?:y|ies)\b", title, re.I):
        return bool(re.search(r"\bvol(?:ume|\.)\s*([0-9]+|[ivxl]+)\b", title, re.I)) or \
            not re.search(r"\bunabridged\b", title, re.I)
    if not REFERENCE_VOLUME.search(title):
        return False
    return True


def _mostly_unsupported_script(path):
    """DejaVu has no CJK glyphs, so such books would render as empty boxes."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            sample = f.read(400_000)
    except Exception:
        return False
    if not sample:
        return False
    return len(CJK.findall(sample)) / len(sample) > CJK_TOLERANCE


# ---------------------------------------------------------------- selection

def norm_key(t, a):
    t = re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()
    a = re.sub(r"[^a-z0-9]+", " ", a.lower()).strip()
    a = re.sub(r",.*$", "", a).strip()
    return t, a


def select_books(exclude_published=True):
    from build_books import BOOKS as CURATED

    curated_ids = {b["id"] for b in CURATED}
    curated_gids = {b["gid"] for b in CURATED}

    catalog = json.load(open(CATALOG, encoding="utf-8"))
    meta = json.load(open(META, encoding="utf-8")) if os.path.exists(META) else {}
    cls = json.load(open(CLASSIFIED, encoding="utf-8")) if os.path.exists(CLASSIFIED) else {}

    existing = json.load(open(DATA, encoding="utf-8")) if os.path.exists(DATA) else []
    existing_ids = {e["id"] for e in existing}

    seen_keys = set()
    for b in CURATED:
        seen_keys.add(norm_key(b["title"], b["author"]))
    for e in existing:
        seen_keys.add(norm_key(e["title"], e["author"]))

    # bucket every catalog book by category, preserving download-rank order inside a bucket
    buckets = {}
    seen_gid = set()
    for e in catalog:
        gid = e["gid"]
        if gid in curated_gids or gid in seen_gid:
            continue
        title = (e.get("title") or "").strip()
        author = (e.get("author") or "").strip() or "Unknown"
        if not title or BAD_TITLE.match(title) or len(title) < 3:
            continue
        if mostly_non_latin(title) or mostly_non_latin(author):
            continue
        key = norm_key(title, author)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        seen_gid.add(gid)

        bid = f"{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:58]}-{gid}"
        if bid in curated_ids:
            continue
        if exclude_published and bid in existing_ids:
            continue
        cat = cls.get(str(gid), {}).get("category", "Fiction")
        entry = dict(
            id=bid, gid=gid, title=title, author=author, year="", category=cat,
            desc=cls.get(str(gid), {}).get(
                "desc",
                f"{title} by {author} — a free public-domain book from Project Gutenberg.",
            ),
        )
        entry["reference-volume"] = is_reference_volume(entry)
        buckets.setdefault(cat, []).append(entry)

    # fiction is by far the largest bucket, so reserve a share of the library for it
    # and spread what is left across every other category
    from categorize import CATEGORIES

    order = [c for c in CATEGORIES if buckets.get(c) and c != "Fiction"]
    order += [c for c in buckets if c not in order and c != "Fiction"]

    fiction_want = min(len(buckets.get("Fiction", [])), int(TARGET * FICTION_SHARE))
    picked = buckets.get("Fiction", [])[:fiction_want]

    picked += _round_robin(buckets, order, TARGET - len(picked))

    picked.sort(key=lambda b: (b["category"], b["title"].lower()))
    taken = Counter(b["category"] for b in picked)
    print("available per category: "
          f"{ {c: len(buckets.get(c, [])) for c in ['Fiction'] + order} }", flush=True)
    print(f"selected per category:  {dict(taken)}", flush=True)
    return picked


def _round_robin(buckets, order, want):
    out, idx = [], 0
    while len(out) < want:
        progressed = False
        for cat in order:
            bucket = buckets.get(cat)
            if not bucket or idx >= len(bucket):
                continue
            out.append(bucket[idx])
            progressed = True
            if len(out) >= want:
                break
        if not progressed:
            break
        idx += 1
    return out


# ---------------------------------------------------------------- outputs

PAGECOUNTS = os.path.join(BASE, "tools", "pagecounts.json")
_pagecounts = {}


def pdf_pages(path):
    """Page count, cached on (size) because reading 2000 PDFs with pypdf is slow."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    if not _pagecounts:
        try:
            with open(PAGECOUNTS, encoding="utf-8") as f:
                _pagecounts.update(json.load(f))
        except Exception:
            pass
    key = os.path.basename(path)
    hit = _pagecounts.get(key)
    if hit and hit[0] == size:
        return hit[1]

    pages = None
    try:
        from pypdf import PdfReader
        pages = len(PdfReader(path).pages)
    except Exception:
        pages = None
    _pagecounts[key] = [size, pages]
    return pages


def save_pagecounts():
    try:
        with open(PAGECOUNTS, "w", encoding="utf-8") as f:
            json.dump(_pagecounts, f)
    except Exception as e:
        print(f"  page count cache not saved: {e}", flush=True)


def prewarm_pagecounts(paths, procs=None):
    """Fill the page-count cache for many PDFs at once.

    Reading page counts is pure CPU/IO and a single scan of a few thousand PDFs takes
    tens of minutes, which used to dominate the manifest step. Spread it over a process
    pool instead; each worker is independent so the per-file cache merge is safe.
    """
    todo = [p for p in paths if os.path.exists(p)]
    if not todo:
        return 0
    procs = procs or max(2, min(PDF_PROCS, (os.cpu_count() or 4)))
    todo.sort(key=os.path.getsize)
    t0 = time.time()
    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor(max_workers=procs) as ex:
        for n, res in enumerate(ex.map(_pagecount_one, todo, chunksize=8), 1):
            if res:
                _pagecounts[os.path.basename(res[0])] = res[1:]
            if n % 500 == 0:
                print(f"  pagecounts {n}/{len(todo)} ({time.time()-t0:.0f}s)", flush=True)
    print(f"  pagecounts: {len(todo)} PDFs in {time.time()-t0:.0f}s", flush=True)
    return len(todo)


def _pagecount_one(path):
    try:
        size = os.path.getsize(path)
        from pypdf import PdfReader
        return (path, size, len(PdfReader(path).pages))
    except Exception:
        try:
            return (path, os.path.getsize(path), None)
        except OSError:
            return None


def _entry(bid, title, author, year, category, desc, pdf):
    """One manifest record. `cover` is the Project Gutenberg image for this ebook."""
    from covers import cover_url

    gid = _gid_for(bid)
    return dict(
        id=bid, title=title, author=author, year=year, category=category,
        desc=desc, file=f"pdfs/{bid}.pdf", size=os.path.getsize(pdf),
        pages=pdf_pages(pdf), gid=gid, cover=cover_url(gid) if gid else "",
    )


# a book's id ends in its Gutenberg id, which is what the cover URL is keyed on; built
# from the selected catalog so the manifest step does not have to re-parse it
_gid_by_id = {}

_GID_SUFFIX = re.compile(r"-(\d+)$")


def _gid_for(bid):
    """Gutenberg id for a manifest id, falling back to the numeric suffix.

    Books published by an earlier run are carried over from data/books.json rather than
    re-selected, so they are absent from the index; their ids still end in the ebook id.
    """
    gid = _gid_by_id.get(bid)
    if gid:
        return gid
    m = _GID_SUFFIX.search(bid)
    return int(m.group(1)) if m else None


def _index_gids(books):
    _gid_by_id.clear()
    for b in books:
        _gid_by_id[b["id"]] = b.get("gid")


def write_outputs(extra_entries):
    from build_books import BOOKS as CURATED
    from covers import cover_url

    curated_ids = {b["id"] for b in CURATED}
    _index_gids(select_books(exclude_published=False))

    # Fill the page-count cache in parallel first; afterwards the serial loops below all
    # hit the in-memory cache, so nothing is re-read.
    try:
        with open(PAGECOUNTS, encoding="utf-8") as f:
            _pagecounts.update(json.load(f))
    except Exception:
        pass
    all_pdfs = [
        os.path.join(PDF_DIR, n) for n in os.listdir(PDF_DIR)
        if n.endswith(".pdf") and os.path.getsize(os.path.join(PDF_DIR, n)) >= 5000
    ]
    prewarm_pagecounts(all_pdfs)

    # start from whatever is already published and still on disk, so a partial
    # run can never drop books an earlier run added
    entries, known = [], set()
    if os.path.exists(DATA):
        for e in json.load(open(DATA, encoding="utf-8")):
            pdf = os.path.join(BASE, e.get("file", f"pdfs/{e['id']}.pdf").lstrip("/"))
            if not os.path.exists(pdf):
                continue
            if os.path.getsize(pdf) < 5000:
                continue
            e = dict(e)
            e["file"] = f"pdfs/{e['id']}.pdf"
            e.setdefault("size", os.path.getsize(pdf))
            if e.get("pages") is None:
                e["pages"] = pdf_pages(pdf)
            # carried-over records predate the cover field, so backfill it here
            gid = _gid_for(e["id"])
            e["gid"] = gid
            e["cover"] = e.get("cover") or (cover_url(gid) if gid else "")
            entries.append(e)
            known.add(e["id"])

    for b in CURATED:
        if b["id"] in known:
            continue
        pdf = os.path.join(PDF_DIR, b["id"] + ".pdf")
        if not os.path.exists(pdf) or os.path.getsize(pdf) < 5000:
            continue
        entries.append(_entry(
            b["id"], b["title"], b["author"], b["year"], b["category"], b["desc"], pdf,
        ))
        known.add(b["id"])

    for rec in extra_entries:
        if rec["id"] in known:
            continue
        rec = dict(rec)
        gid = _gid_for(rec["id"])
        rec["gid"] = gid
        rec.setdefault("cover", cover_url(gid) if gid else "")
        entries.append(rec)
        known.add(rec["id"])

    entries.sort(key=lambda e: (e["category"], e["title"].lower()))
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=1, ensure_ascii=False)

    lite = [
        {
            "id": e["id"], "title": e["title"], "author": e["author"],
            "year": e["year"], "category": e["category"], "size": e["size"],
            "pages": e["pages"], "cover": e.get("cover", ""),
            "desc": (e["desc"][:170].rsplit(" ", 1)[0] + "…") if len(e["desc"]) > 170 else e["desc"],
        }
        for e in entries
    ]
    with open(LITE, "w", encoding="utf-8") as f:
        json.dump(lite, f, separators=(",", ":"), ensure_ascii=False)

    return entries


def main():
    print(f"cpu={os.cpu_count()} dl_workers={DL_WORKERS} pdf_procs={PDF_PROCS} target={TARGET}", flush=True)
    books = select_books()
    print(f"selected {len(books)} new books to add", flush=True)

    # phase 1: download texts
    print("--- phase 1: texts ---", flush=True)
    t0 = time.time()
    tstats = Counter()
    for i, r in enumerate(_map_threads(books, download_text, DL_WORKERS, "text"), 1):
        tstats[r[1] if r[1] in ("cached", "downloaded", "failed") else "error"] += 1
        if i % 200 == 0:
            print(f"  text {i}/{len(books)} {dict(tstats)} ({time.time()-t0:.0f}s)", flush=True)
    print(f"texts: {dict(tstats)} in {time.time()-t0:.0f}s", flush=True)

    # phase 2: render PDFs
    print("--- phase 2: pdfs ---", flush=True)
    t0 = time.time()
    results = Counter()
    built = []
    for r in _map_processes(books, render, PDF_PROCS, "pdf"):
        results[r[1] if r[1] in ("cached", "built", "failed", "too-big", "unsupported-script", "reference-volume") else "error"] += 1
        if r[1] in ("built", "cached"):
            built.append(r[0])
        if sum(results.values()) % 100 == 0:
            print(f"  {sum(results.values())}/{len(books)} {dict(results)} ({time.time()-t0:.0f}s)", flush=True)
    print(f"pdfs: {dict(results)} in {time.time()-t0:.0f}s", flush=True)

    # phase 3: manifest
    _index_gids(books)
    byid = {b["id"]: b for b in books}
    entries = []
    for bid in built:
        b = byid[bid]
        pdf = os.path.join(PDF_DIR, bid + ".pdf")
        if not os.path.exists(pdf):
            continue
        b["year"] = ""
        entries.append(_entry(
            bid, b["title"], b["author"], b["year"], b["category"], b["desc"], pdf,
        ))

    all_entries = write_outputs(entries)
    save_pagecounts()
    dist = Counter(e["category"] for e in all_entries)
    total = sum(e["size"] for e in all_entries)
    print(f"\nDONE: {len(all_entries)} books, {total/1048576:.0f} MB of PDFs")
    for c, n in dist.most_common():
        print(f"  {c:20} {n}")


def _map_threads(items, fn, workers, label):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn, b): b for b in items}
        for f in as_completed(futs):
            try:
                yield f.result()
            except Exception as e:
                yield futs[f]["id"], f"error: {e}"[:120]


def _map_processes(items, fn, procs, label):
    ctx = mp.get_context("fork")
    with ctx.Pool(procs) as pool:
        for r in pool.imap_unordered(fn, items, chunksize=1):
            yield r


if __name__ == "__main__":
    main()