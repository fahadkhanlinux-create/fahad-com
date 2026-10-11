#!/usr/bin/env python3
"""Expand the Project Gutenberg catalog and cache per-book metadata (subjects, LoC class, summary)."""
import html
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(BASE, "tools", "guten_catalog.json")
META = os.path.join(BASE, "tools", "guten_meta.json")

CATALOG_TARGET = int(os.environ.get("CATALOG_TARGET", "3600"))
WORKERS = int(os.environ.get("META_WORKERS", "6"))

# (LoC class query, max entries to scan) — tops up thin categories on the site
TOPICAL_QUERIES = [
    ("lcc.QA", 500),
    ("lcc.QB", 200),
    ("lcc.TA", 150),
    ("lcc.QC", 150),
    ("lcc.PZ", 250),
    ("lcc.PR", 300),
]

UA = "Mozilla/5.0 (X11; Linux x86_64) fahad-com-book-library/1.0"
# fail fast on a slow response so one hung request cannot stall the metadata sweep
HTTP_TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", "10"))
_lock = threading.Lock()


def http_get(url, tries=5, timeout=None):
    timeout = timeout or HTTP_TIMEOUT
    last = None
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code in (404, 403):
                return ""
            last = e
        except Exception as e:
            last = e
        time.sleep(1.5 * (a + 1))
    raise RuntimeError(f"GET {url} failed: {last}")


def strip_tags(s):
    return html.unescape(re.sub(r"<.*?>", "", s)).strip()


def _page_entries(page):
    out = []
    for b in re.findall(r'<li class="booklink">(.*?)</li>', page, re.S):
        m = re.search(r'href="/ebooks/(\d+)"', b)
        t = re.search(r'<span class="title">(.*?)</span>', b, re.S)
        a = re.search(r'<span class="subtitle">(.*?)</span>', b, re.S)
        if not (m and t):
            continue
        out.append({
            "gid": int(m.group(1)),
            "title": strip_tags(t.group(1)),
            "author": strip_tags(a.group(1)) if a else "Unknown",
        })
    return out


def _save_catalog(out):
    with open(CATALOG, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)


def scrape_catalog():
    out = json.load(open(CATALOG, encoding="utf-8")) if os.path.exists(CATALOG) else []
    seen = {c["gid"] for c in out}
    start = len(out) + 1
    while len(out) < CATALOG_TARGET:
        url = (
            "https://www.gutenberg.org/ebooks/search/?sort_order=downloads"
            f"&languages=en&start_index={start}"
        )
        page = http_get(url)
        entries = _page_entries(page)
        if not entries:
            print(f"no more results at start_index={start}", flush=True)
            break
        added = 0
        for e in entries:
            if e["gid"] in seen:
                continue
            seen.add(e["gid"])
            out.append(e)
            added += 1
        print(f"catalog: {len(out)} (start_index={start}, +{added})", flush=True)
        start += 25
        if start % 250 == 0:
            _save_catalog(out)
        time.sleep(0.6)
    _save_catalog(out)

    # topical top-ups so category balance is not dictated by download rank alone
    for query, cap in TOPICAL_QUERIES:
        got = 0
        start = 1
        while got < cap:
            url = (
                f"https://www.gutenberg.org/ebooks/search/?query={query}"
                f"&languages=en&sort_order=downloads&start_index={start}"
            )
            entries = _page_entries(http_get(url))
            if not entries:
                break
            added = 0
            for e in entries:
                if e["gid"] in seen:
                    continue
                seen.add(e["gid"])
                out.append(e)
                added += 1
            got += len(entries)
            start += 25
            if added == 0:
                break
            time.sleep(0.6)
        print(f"topical {query}: scanned {got}, catalog={len(out)}", flush=True)
        _save_catalog(out)

    return out


BIBREC = re.compile(r'<table class="bibrec".*?</table>', re.S)
ROW = re.compile(r"<tr\b.*?</tr>", re.S)


def parse_bibrec(page):
    tbl = BIBREC.search(page)
    if not tbl:
        return None
    meta = {"subjects": [], "lcc": "", "summary": "", "gutenberg_year": ""}
    rows = ROW.findall(tbl.group(0))
    fields = []
    for r in rows:
        th = re.search(r"<th[^>]*>(.*?)</th>", r, re.S)
        td = re.search(r"<td[^>]*>(.*?)</td>", r, re.S)
        if th and td:
            fields.append((strip_tags(th.group(1)), td.group(1), r))
    for label, inner, raw in fields:
        if label == "Subject":
            names = re.findall(r'<a class="block"[^>]*>(.*?)</a>', inner, re.S)
            meta["subjects"].extend(strip_tags(n) for n in names if strip_tags(n))
        elif label == "LoC Class":
            m = re.search(r"^([A-Z]{1,2})\s*:", strip_tags(inner))
            if m:
                meta["lcc"] = m.group(1)
        elif label in ("Summary", "Description"):
            text = strip_tags(inner)
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) > 20:
                meta["summary"] = text
        elif label == "Release Date":
            m = re.search(r"\b(1[0-9]{3}|20[0-2][0-9])\b", strip_tags(inner))
            if m:
                meta["gutenberg_year"] = m.group(1)
    return meta


def fetch_meta(gid):
    try:
        page = http_get(f"https://www.gutenberg.org/ebooks/{gid}", tries=4)
        if not page:
            return gid, {"subjects": [], "lcc": "", "summary": "", "gutenberg_year": "", "missing": True}
        m = parse_bibrec(page)
        return gid, (m or {"subjects": [], "lcc": "", "summary": "", "gutenberg_year": ""})
    except Exception as e:
        print(f"  meta fail gid={gid}: {e}", flush=True)
        return gid, None


def main():
    catalog = scrape_catalog()
    print(f"catalog total: {len(catalog)}", flush=True)

    meta = json.load(open(META, encoding="utf-8")) if os.path.exists(META) else {}
    todo = [c["gid"] for c in catalog if str(c["gid"]) not in meta]
    print(f"fetching metadata for {len(todo)} books ...", flush=True)

    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(fetch_meta, g) for g in todo]
        for f in as_completed(futs):
            gid, m = f.result()
            if m is not None:
                meta[str(gid)] = m
            done += 1
            if done % 100 == 0:
                print(f"  meta {done}/{len(todo)}", flush=True)
                with open(META, "w", encoding="utf-8") as fh:
                    json.dump(meta, fh, ensure_ascii=False)

    with open(META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False)
    print(f"metadata cached for {len(meta)} books -> {META}", flush=True)


if __name__ == "__main__":
    main()