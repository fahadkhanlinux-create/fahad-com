#!/usr/bin/env python3
"""Build the Project Gutenberg catalog + metadata cache from the official CSV dump.

Replaces hours of per-book page scraping: pg_catalog.csv already ships subjects and
LoC class for every book, so guten_catalog.json and guten_meta.json are written in
one pass.

Env:
  PG_CSV        path to pg_catalog.csv (default /tmp/opencode/pg_catalog.csv)
  CATALOG_MIN   minimum English Text rows to emit (default 60000)
"""
import csv
import json
import os
import sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(BASE, "tools", "guten_catalog.json")
META = os.path.join(BASE, "tools", "guten_meta.json")

PG_CSV = os.environ.get("PG_CSV", "/tmp/opencode/pg_catalog.csv")
CATALOG_MIN = int(os.environ.get("CATALOG_MIN", "60000"))


def split_list(raw):
    """Subjects/LoCC are ';'-separated in the CSV; keep the human-readable part."""
    out = []
    for part in (raw or "").split(";"):
        part = part.strip()
        if part:
            out.append(part)
    return out


def clean_author(raw):
    """'Doe, Jane, 1801-1870' -> 'Doe, Jane' (keep comma form; site shows it verbatim)."""
    name = " ".join((raw or "").split())
    if not name or name.lower() in ("unknown", "various", "unknown."):
        return "Unknown"
    parts = name.split(",")
    # drop life dates and trailing role noise: 'Doe, Jane, 1801-1870' -> 'Doe, Jane'
    if len(parts) >= 2:
        for p in parts[1:]:
            p = p.strip()
            if p and not any(ch.isdigit() for ch in p):
                return f"{parts[0].strip()}, {p}"
    return parts[0].strip() or name


def main():
    if not os.path.exists(PG_CSV):
        sys.exit(f"missing catalog dump: {PG_CSV}\n"
                 f"curl -sSL -o {PG_CSV} https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv")

    # previous files, so already-downloaded gids keep their place at the front of the
    # download-rank order and select_books() does not reshuffle the whole library
    old_catalog = json.load(open(CATALOG, encoding="utf-8")) if os.path.exists(CATALOG) else []
    old_meta = json.load(open(META, encoding="utf-8")) if os.path.exists(META) else {}
    old_rank = {c["gid"]: i for i, c in enumerate(old_catalog)}
    print(f"existing catalog: {len(old_catalog)} books, meta: {len(old_meta)}", flush=True)

    csv.field_size_limit(10 ** 7)
    rows = []
    with open(PG_CSV, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("Type") != "Text":
                continue
            # bilingual rows are listed "en; es" — keep them, they carry English text
            langs = [x.strip() for x in (r.get("Language") or "").split(";")]
            if "en" not in langs:
                continue
            try:
                gid = int(r["Text#"])
            except (TypeError, ValueError):
                continue
            title = " ".join((r.get("Title") or "").split())
            if not title:
                continue
            rows.append({
                "gid": gid,
                "title": title,
                "author": clean_author(r.get("Authors") or ""),
                "subjects": split_list(r.get("Subjects")),
                "lcc": (split_list(r.get("LoCC")) or [""])[0].split(":")[0].strip().upper(),
                "gutenberg_year": (r.get("Issued") or "")[:4],
                "bookshelves": [b.strip() for b in split_list(r.get("Bookshelves"))],
            })

    print(f"CSV english Text rows: {len(rows)}", flush=True)

    # keep everything previously known, then append the rest in CSV order
    rows.sort(key=lambda r: old_rank.get(r["gid"], 10 ** 9))

    # A book's id is derived from its title, so changing the title of a gid we already
    # built would orphan its .txt/.pdf on disk and force a needless re-download. The CSV
    # titles are the full ones where the scraped catalog had them truncated, so reuse the
    # title we built with and only take the CSV subject/LoC metadata.
    old_by_gid = {c["gid"]: c for c in old_catalog}
    kept = 0
    for r in rows:
        prev = old_by_gid.get(r["gid"])
        if prev and prev.get("title"):
            if prev["title"] != r["title"]:
                kept += 1
            r["title"] = prev["title"]
            r["author"] = prev.get("author") or r["author"]
    print(f"reused {len(old_by_gid) - kept} existing titles, kept {kept} scraped truncations", flush=True)

    catalog, meta = [], {}
    dist = Counter()
    for r in rows:
        catalog.append({"gid": r["gid"], "title": r["title"], "author": r["author"]})
        m = {
            "subjects": r["subjects"],
            "lcc": r["lcc"],
            "summary": "",
            "gutenberg_year": r["gutenberg_year"],
        }
        # keep any richer summary we had already scraped for this book
        prev = old_meta.get(str(r["gid"]))
        if prev and prev.get("summary"):
            m["summary"] = prev["summary"]
        meta[str(r["gid"])] = m
        dist[r["lcc"][:2] if r["lcc"] else "?"] += 1

    if len(catalog) < CATALOG_MIN:
        print(f"WARNING: only {len(catalog)} rows, expected >= {CATALOG_MIN}", flush=True)

    with open(CATALOG, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False)
    with open(META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)

    print(f"wrote catalog={len(catalog)} meta={len(meta)}", flush=True)
    print("top LoCC prefixes:", dist.most_common(12), flush=True)


if __name__ == "__main__":
    main()