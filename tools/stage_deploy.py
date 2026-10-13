#!/usr/bin/env python3
"""Stage a deployment that fits inside the Vercel Hobby 100 MB upload cap.

The library is ~3.1 GB, far past the Hobby limit, so the split is:

  * every book stays in the manifest and keeps its card, search hit and detail page,
  * every book keeps its thumbnail, because the cards are what the site is made of,
  * as many PDFs as the remaining budget allows are mirrored on Vercel itself,
  * every book carries a mirror URL as well, so a book whose PDF did not fit still
    opens for the reader instead of dead-ending on a 404.

Writes to DEPLOY_DIR with hardlinks for the PDFs, so staging costs no extra disk.
"""
import json
import os
import shutil
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOY_DIR = os.environ.get("DEPLOY_DIR", "/tmp/opencode/fahad-com-deploy")
BUDGET_MB = float(os.environ.get("DEPLOY_BUDGET_MB", "100"))
SAFETY = float(os.environ.get("DEPLOY_SAFETY", "0.90"))
ORIGIN = os.environ.get("DEPLOY_ORIGIN", "https://fahad-com-ten.vercel.app")

# PDFs are served from the public mirror when they do not fit in the Vercel payload.
MIRROR = os.environ.get("PDF_MIRROR", "fahadkhanlinux-create/fahad-com-pdfs")
MIRROR_BRANCH = os.environ.get("PDF_MIRROR_BRANCH", "main")
MIRROR_CDN = "https://cdn.jsdelivr.net/gh/%s@%s/pdfs/%%s.pdf" % (MIRROR, MIRROR_BRANCH)
MIRROR_RAW = "https://raw.githubusercontent.com/%s/%s/pdfs/%%s.pdf" % (MIRROR, MIRROR_BRANCH)

SHELL = [
    "index.html", "book.html", "guard.js", "vercel.json", "robots.txt",
    "assets/css/style.css", "assets/js/app.js", "assets/js/book.js",
    "assets/og-image.jpg",
    ".vercelignore",
]


def mirror_url(template, bid):
    # jsDelivr/raw address the file by its bare name; ids are already [a-z0-9-]
    return template % bid


def dir_bytes(path):
    total = 0
    for dp, _, fns in os.walk(path):
        for fn in fns:
            try:
                total += os.path.getsize(os.path.join(dp, fn))
            except OSError:
                pass
    return total


def main():
    books = json.load(open(os.path.join(BASE, "data", "books.json"), encoding="utf-8"))
    thumb_dir = os.path.join(BASE, "assets", "thumbs")
    pdf_dir = os.path.join(BASE, "pdfs")

    budget = BUDGET_MB * 1048576 * SAFETY
    print("budget: %.0f MB (payload cap %.0f MB)" % (budget / 1048576, BUDGET_MB * SAFETY), flush=True)

    if os.path.exists(DEPLOY_DIR):
        shutil.rmtree(DEPLOY_DIR)
    os.makedirs(os.path.join(DEPLOY_DIR, "pdfs"))
    os.makedirs(os.path.join(DEPLOY_DIR, "assets", "thumbs"))
    os.makedirs(os.path.join(DEPLOY_DIR, "data"))

    used = 0
    for rel in SHELL:
        src = os.path.join(BASE, rel)
        dst = os.path.join(DEPLOY_DIR, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        used += os.path.getsize(dst)

    # every book keeps its card: the thumbnails are the site
    books = [b for b in books
             if os.path.exists(os.path.join(thumb_dir, b["id"] + ".jpg"))
             and os.path.exists(os.path.join(pdf_dir, b["id"] + ".pdf"))]
    for b in books:
        src = os.path.join(thumb_dir, b["id"] + ".jpg")
        dst = os.path.join(DEPLOY_DIR, "assets", "thumbs", b["id"] + ".jpg")
        shutil.copy2(src, dst)
        used += os.path.getsize(dst)
    print("thumbs: %d books (%.1f MB)" % (len(books), used / 1048576), flush=True)

    # JSON is written last but must be paid for now, so the PDFs get what is left
    json_per_book = 1400  # books.json + catalog.json, measured per record
    used += json_per_book * len(books)
    print("after thumbs + json: %.1f MB, %.1f MB left for PDFs"
          % (used / 1048576, max(0.0, budget - used) / 1048576), flush=True)

    by_cat = defaultdict(list)
    for b in books:
        by_cat[b["category"]].append(b)
    for cat in by_cat:
        by_cat[cat].sort(key=lambda b: (b["size"], b["title"].lower()))

    local = set()
    idx = {c: 0 for c in by_cat}
    while True:
        progressed = False
        for cat in sorted(by_cat):
            if idx[cat] >= len(by_cat[cat]):
                continue
            b = by_cat[cat][idx[cat]]
            idx[cat] += 1
            if b["id"] in local:
                continue
            cost = b["size"]
            if used + cost > budget:
                continue
            used += cost
            local.add(b["id"])
            progressed = True
        if not progressed:
            break

    for bid in sorted(local):
        src = os.path.join(pdf_dir, bid + ".pdf")
        dst = os.path.join(DEPLOY_DIR, "pdfs", bid + ".pdf")
        try:
            os.link(src, dst)  # same filesystem: staging costs no extra disk
        except OSError:
            shutil.copy2(src, dst)

    manifest = []
    for b in books:
        bid = b["id"]
        rec = dict(b)
        rec["cover"] = "assets/thumbs/%s.jpg" % bid
        rec["local"] = bid in local
        if bid in local:
            rec["file"] = "pdfs/%s.pdf" % bid
        else:
            # no local copy: the reader must not be pointed at a file that was never uploaded
            rec["file"] = ""
        rec["pdf"] = mirror_url(MIRROR_CDN, bid)
        rec["pdf_raw"] = mirror_url(MIRROR_RAW, bid)
        manifest.append(rec)
    manifest.sort(key=lambda b: (b["category"], b["title"].lower()))

    with open(os.path.join(DEPLOY_DIR, "data", "books.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, separators=(",", ":"))
    catalog = [{k: b.get(k, "") for k in
                ["id", "title", "author", "year", "category", "size", "pages",
                 "cover", "desc", "local", "file", "pdf", "pdf_raw"]}
               for b in manifest]
    with open(os.path.join(DEPLOY_DIR, "data", "catalog.json"), "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, separators=(",", ":"))

    with open(os.path.join(DEPLOY_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        f.write("  <url><loc>%s/</loc></url>\n" % ORIGIN)
        for b in manifest:
            f.write("  <url><loc>%s/book?id=%s</loc></url>\n" % (ORIGIN, b["id"]))
        f.write("</urlset>\n")

    # robots.txt shipped a hand-written Sitemap: line pointing at fahad.com, a domain
    # that does not resolve, so crawlers were pointed at nothing. Same origin as the
    # sitemap keeps the two from drifting apart again.
    robots = os.path.join(BASE, "robots.txt")
    if os.path.exists(robots):
        text = open(robots, encoding="utf-8").read()
        lines = [
            ("Sitemap: %s/sitemap.xml" % ORIGIN) if l.startswith("Sitemap:") else l
            for l in text.splitlines()
        ]
        if not any(l.startswith("Sitemap:") for l in lines):
            lines.append("Sitemap: %s/sitemap.xml" % ORIGIN)
        with open(os.path.join(DEPLOY_DIR, "robots.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    total = dir_bytes(DEPLOY_DIR)
    cats = defaultdict(int)
    for b in manifest:
        cats[b["category"]] += 1
    print("staged: %d books, %d PDFs mirrored on Vercel, %d from the mirror"
          % (len(manifest), len(local), len(manifest) - len(local)))
    print("  payload: %.1f MB of %.1f MB budget" % (total / 1048576, budget / 1048576))
    print("  per category:", dict(sorted(cats.items(), key=lambda kv: -kv[1])))

    # Carry the real project link over. Without this Vercel treats the staging dir as a
    # brand-new project and publishes to a throwaway <staging-dir-name>.vercel.app
    # instead of fahad-com-ten, which is how a whole deploy silently landed in the
    # wrong place once already.
    src = os.path.join(BASE, ".vercel")
    dst = os.path.join(DEPLOY_DIR, ".vercel")
    if os.path.isdir(src):
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        proj = json.load(open(os.path.join(src, "project.json"), encoding="utf-8"))
        print("  deploy target: %s" % proj.get("projectName"))


if __name__ == "__main__":
    main()