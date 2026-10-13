#!/usr/bin/env python3
"""Sanity-check the Fahad.com library before publishing."""
import json
import os
import re
import sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data", "books.json")
LITE = os.path.join(BASE, "data", "catalog.json")
SITEMAP = os.path.join(BASE, "sitemap.xml")

problems = []


def check(cond, msg):
    if not cond:
        problems.append(msg)
    return cond


def main():
    books = json.load(open(DATA, encoding="utf-8"))
    print(f"books.json: {len(books)} entries")

    ids = [b["id"] for b in books]
    dupes = [i for i, n in Counter(ids).items() if n > 1]
    check(not dupes, f"duplicate ids: {dupes[:5]}")

    seen_titles = Counter((b["title"].strip().lower(), b["author"].strip().lower()) for b in books)
    dupes2 = [t for t, n in seen_titles.items() if n > 1]
    check(not dupes2, f"duplicate title+author: {dupes2[:5]}")

    missing, sizemismatch, badfields = [], [], []
    for b in books:
        p = os.path.join(BASE, b.get("file", ""))
        if not os.path.exists(p):
            missing.append(b["id"])
            continue
        actual = os.path.getsize(p)
        if b.get("size") and abs(actual - b["size"]) > 1024:
            sizemismatch.append((b["id"], b["size"], actual))
        if not b.get("title") or not b.get("author") or not b.get("category") or not b.get("desc"):
            badfields.append(b["id"])
        if b.get("file") != f"pdfs/{b['id']}.pdf":
            badfields.append(b["id"] + " (file path)")

    check(not missing, f"{len(missing)} entries missing a PDF: {missing[:5]}")
    check(not sizemismatch, f"{len(sizemismatch)} size mismatches: {sizemismatch[:3]}")
    check(not badfields, f"{len(badfields)} entries with bad fields: {badfields[:5]}")

    total = sum(b.get("size", 0) for b in books)
    print(f"total PDF size: {total/1048576:.0f} MB")
    print(f"total pages:    {sum(b.get('pages') or 0 for b in books):,}")

    # every category used must have a colour in both JS files
    cats = set(b["category"] for b in books)
    for js in ("assets/js/app.js", "assets/js/book.js"):
        src = open(os.path.join(BASE, js), encoding="utf-8").read()
        for c in sorted(cats):
            check(f'"{c}"' in src, f"category {c!r} has no colour entry in {js}")

    # grid catalog must cover exactly the same books
    if os.path.exists(LITE):
        lite = json.load(open(LITE, encoding="utf-8"))
        check([x["id"] for x in lite] == ids, "catalog.json ids differ from books.json")
        check(all(x.get("desc") for x in lite), "some catalog.json entries have no desc")
        print(f"catalog.json: {len(lite)} entries, "
              f"{os.path.getsize(LITE)/1024:.0f} KB, "
              f"books.json {os.path.getsize(DATA)/1024:.0f} KB")

    # sitemap must list every book
    sm = open(SITEMAP, encoding="utf-8").read()
    # sitemap must list every book. build_sitemap.py writes /book.html?id= — the clean
    # /book?id= form 404s on GitHub Pages, so this check used to fail on a correct sitemap
    check(f"<loc>https://fahad.com/book.html?id={ids[0]}</loc>" in sm, "sitemap missing first book")
    check("<loc>https://fahad.com/modern.html</loc>" in sm, "sitemap missing the modern shelf")
    n = sm.count("<url>")
    check(n == len(books) + 2, f"sitemap has {n} urls for {len(books)} books + home + shelf")

    # the modern shelf: curated entries only, and every free companion must
    # resolve against the grid catalog so the "read this instead" links work
    modern_path = os.path.join(BASE, "data", "modern.json")
    if os.path.exists(modern_path):
        modern = json.load(open(modern_path, encoding="utf-8"))
        catalog_ids = set(ids)
        mids = [b["id"] for b in modern]
        mdupes = [i for i, n in Counter(mids).items() if n > 1]
        check(not mdupes, f"duplicate ids in modern.json: {mdupes[:5]}")
        mbad = [b["id"] for b in modern
                if not all(str(b.get(k, "")).strip() for k in ("title", "author", "topic", "pitch", "digest"))]
        check(not mbad, f"modern.json entries missing fields: {mbad[:5]}")
        mfree = {c for b in modern for c in b.get("free", [])}
        unknown = sorted(mfree - catalog_ids)
        check(not unknown, f"modern.json links to unknown free books: {unknown[:5]}")
        mt = Counter(b["topic"] for b in modern)
        print(f"modern.json: {len(modern)} titles across {len(mt)} categories, "
              f"{len(mfree)} free companions (free library untouched)")
        check(mt.get("Self-Help", 0) >= 28 and mt.get("Psychology", 0) >= 30,
              "modern.json is missing expected productivity/psychology titles")

        # the shelf must not depend on the multi-MB catalog to render: it links a
        # slim companion map, and if that map is missing the page blanks entirely
        free_map = os.path.join(BASE, "data", "modern_free.json")
        if os.path.exists(free_map):
            slim = json.load(open(free_map, encoding="utf-8"))
            slim_ids = {b["id"] for b in slim}
            check(mfree == slim_ids,
                  f"modern_free.json is out of sync with modern.json "
                  f"(missing {sorted(mfree - slim_ids)[:3]})")
            check(all(b.get("title") and b.get("author") for b in slim),
                  "modern_free.json has entries missing title/author")
            kb = os.path.getsize(free_map) / 1024
            check(kb < 400, f"modern_free.json is {kb:.0f} KB — it should stay tiny")
            print(f"modern_free.json: {len(slim)} classics, {kb:.0f} KB "
                  f"(shelf no longer loads the {os.path.getsize(LITE)/1048576:.1f} MB catalog)")
        else:
            check(False, "data/modern_free.json missing — the modern shelf will blank on slow connections")

    dist = Counter(b["category"] for b in books)
    print("\ncategories:")
    for c, n in dist.most_common():
        print(f"  {c:22} {n:5}")

    years = [b["year"] for b in books if b.get("year")]
    print(f"\nentries with a year: {len(years)}/{len(books)}")

    # a plain year, or an ancient-work date like "380 BC" / "5th c. BC" that the
    # curated classics legitimately carry
    bad_year = [y for y in years if not re.fullmatch(r"\d{3,4}", y) and not re.fullmatch(
        r"(?:\d{1,4}|\d{1,2}(?:st|nd|rd|th) c\.)\s*B\.?C\.?", y)]
    check(not bad_year, f"malformed year values: {bad_year[:5]}")

    print()
    if problems:
        print(f"FAILED with {len(problems)} problem(s):")
        for p in problems:
            print("  -", p)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())