#!/usr/bin/env python3
"""Merge the curated modern shelf into data/modern.json.

The existing entries in data/modern.json are kept verbatim — this script only
adds the curated additions from tools/modern_shelf_{1,2,3}.py and fills in the
`free` public-domain companion links from tools/modern_free_pools.py.

Nothing that is already in modern.json is removed or rewritten, so running this
repeatedly is safe. Any companion id that does not exist in data/catalog.json is
a hard error: the script refuses to write output rather than emit a dead link.

    python3 tools/build_modern.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from modern_free_pools import POOLS  # noqa: E402
import modern_shelf_1  # noqa: E402
import modern_shelf_2  # noqa: E402
import modern_shelf_3  # noqa: E402

CATALOG = os.path.join(ROOT, "data", "catalog.json")
OUT = os.path.join(ROOT, "data", "modern.json")
OUT_FREE = os.path.join(ROOT, "data", "modern_free.json")

FREE_PER_BOOK = 3


def new_entries():
    return list(modern_shelf_1.BOOKS) + list(modern_shelf_2.BOOKS) + list(modern_shelf_3.BOOKS)


def assign_free(books, per_book=FREE_PER_BOOK):
    """Give each book a stable, rotating slice of its topic's free pool."""
    for i, b in enumerate(books):
        pool = POOLS.get(b["topic"])
        if not pool:
            raise SystemExit("no free pool for topic %r (book %s)" % (b["topic"], b["id"]))
        n = min(per_book, len(pool))
        start = (i * 3) % len(pool)
        picks, seen = [], set()
        for k in range(len(pool)):
            cid = pool[(start + k) % len(pool)]
            if cid in seen:
                continue
            seen.add(cid)
            picks.append(cid)
            if len(picks) == n:
                break
        b["free"] = picks


def main():
    with open(CATALOG, encoding="utf-8") as f:
        catalog = json.load(f)
    valid = {b["id"] for b in catalog}

    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            existing = json.load(f)
    else:
        existing = []

    added = new_entries()
    added_ids = {b["id"] for b in added}

    # Idempotent merge: entries in modern.json that the additions do not own are kept
    # verbatim (these are the original curated titles), and everything the additions
    # own is replaced by the current version of the .py source. That way re-running
    # never duplicates, and editing a digest in the source actually takes effect.
    kept = [b for b in existing if b["id"] not in added_ids]
    replaced = len(existing) - len(kept)
    if replaced:
        print("refreshing %d shelf entries from the curated sources" % replaced)

    assign_free(added)

    # Everything from here is a hard check — a typo must never reach the site.
    problems = []
    seen = set()
    for b in added:
        bid = b["id"]
        if bid in seen:
            problems.append("duplicate id in additions: %s" % bid)
        seen.add(bid)
        for field in ("title", "author", "topic", "pitch", "digest"):
            if not str(b.get(field, "")).strip():
                problems.append("%s: empty %s" % (bid, field))
        if not b.get("year"):
            problems.append("%s: missing year" % bid)
        for cid in b.get("free", []):
            if cid not in valid:
                problems.append("%s: free id not in catalog: %s" % (bid, cid))

    if problems:
        raise SystemExit("modern shelf build failed:\n  " + "\n  ".join(problems))

    merged = kept + added

    # Free-book companions actually shown on the page (deduped across the shelf).
    free_ids = {cid for b in merged for cid in b.get("free", [])}

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # The shelf used to pull the whole 4.5 MB catalog.json just to resolve the few
    # hundred free companions it links to, which meant a slow connection blanked the
    # entire page. Ship only the classics that are actually referenced: a few KB.
    by_id = {b["id"]: b for b in catalog}
    free_ids = sorted({cid for b in merged for cid in b.get("free", [])})
    slim = []
    for cid in free_ids:
        src = by_id.get(cid)
        if not src:
            raise SystemExit("companion missing from catalog: %s" % cid)
        slim.append({
            "id": src["id"],
            "title": src["title"],
            "author": src["author"],
            "cover": src.get("cover", ""),
        })
    with open(OUT_FREE, "w", encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")

    topics = {}
    for b in merged:
        topics[b["topic"]] = topics.get(b["topic"], 0) + 1

    print("modern.json: %d titles (%d preserved, %d from curated sources)"
          % (len(merged), len(kept), len(added)))
    print("categories: %d" % len(topics))
    for t in sorted(topics, key=lambda z: (-topics[z], z)):
        print("  %-26s %d" % (t, topics[t]))
    print("distinct free companions linked: %d" % len(free_ids))
    print("modern_free.json: %d classics, %.0f KB"
          % (len(slim), os.path.getsize(OUT_FREE) / 1024))
    print("free library total: %d titles, untouched" % len(catalog))


if __name__ == "__main__":
    main()