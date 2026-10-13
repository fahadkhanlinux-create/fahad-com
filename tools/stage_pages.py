#!/usr/bin/env python3
"""Stage the full library for Cloudflare Pages.

Cloudflare's Free plan allows 20,000 files and 25 MB per file with no cap on total
size, which is what makes the whole 3.2 GB library deployable in one shot where
Vercel Hobby (100 MB) and Pro (1 GB) cannot take it.

The library on disk holds a few hundred PDFs that were never indexed, so they are
dropped here to stay under the file count.
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_thumbs import THUMB_EXT  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOY_DIR = os.environ.get("DEPLOY_DIR", "/tmp/opencode/fahad-com-pages")
FILE_LIMIT = 20000
ORIGIN = "https://fahadcom.pages.dev"


def main():
    books = json.load(open(os.path.join(BASE, "data", "books.json"), encoding="utf-8"))
    thumb_dir = os.path.join(BASE, "assets", "thumbs")
    pdf_dir = os.path.join(BASE, "pdfs")

    if os.path.exists(DEPLOY_DIR):
        shutil.rmtree(DEPLOY_DIR)
    os.makedirs(os.path.join(DEPLOY_DIR, "pdfs"))
    os.makedirs(os.path.join(DEPLOY_DIR, "assets", "thumbs"))
    os.makedirs(os.path.join(DEPLOY_DIR, "data"))

    for rel in ["index.html", "book.html", "modern.html", "guard.js", "vercel.json",
                "robots.txt", "assets/css/style.css", "assets/js/app.js",
                "assets/js/book.js", "assets/js/modern.js",
                "assets/og-image.jpg"]:
        dst = os.path.join(DEPLOY_DIR, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(BASE, rel), dst)

    for b in books:
        src = os.path.join(pdf_dir, b["id"] + ".pdf")
        dst = os.path.join(DEPLOY_DIR, "pdfs", b["id"] + ".pdf")
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)
        shutil.copy2(os.path.join(thumb_dir, b["id"] + THUMB_EXT),
                     os.path.join(DEPLOY_DIR, "assets", "thumbs", b["id"] + THUMB_EXT))

    with open(os.path.join(DEPLOY_DIR, "data", "books.json"), "w", encoding="utf-8") as f:
        json.dump(books, f, ensure_ascii=False, separators=(",", ":"))
    catalog = [{k: b.get(k, "") for k in
                ["id", "title", "author", "year", "category", "size", "pages", "cover", "desc"]}
               for b in books]
    with open(os.path.join(DEPLOY_DIR, "data", "catalog.json"), "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, separators=(",", ":"))
    shutil.copy2(os.path.join(BASE, "data", "modern.json"),
                 os.path.join(DEPLOY_DIR, "data", "modern.json"))

    urls = [ORIGIN + "/", ORIGIN + "/modern.html"]
    urls += [ORIGIN + "/book.html?id=" + b["id"] for b in books]
    with open(os.path.join(DEPLOY_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for u in urls:
            f.write("  <url><loc>%s</loc></url>\n" % u)
        f.write("</urlset>\n")

    # Pages serves .json and .pdf fine, but these keep the MIME type explicit and
    # let long-lived caching be declared in the repo rather than at the CDN edge
    with open(os.path.join(DEPLOY_DIR, "_headers"), "w", encoding="utf-8") as f:
        f.write("/pdfs/*\n  Cache-Control: public, max-age=31536000, immutable\n"
                "  Content-Type: application/pdf\n\n"
                "/assets/thumbs/*\n  Cache-Control: public, max-age=31536000, immutable\n\n"
                "/data/*\n  Cache-Control: public, max-age=3600\n")

    files = sum(len(fns) for _, _, fns in os.walk(DEPLOY_DIR))
    total = sum(os.path.getsize(os.path.join(dp, fn))
                for dp, _, fns in os.walk(DEPLOY_DIR) for fn in fns)
    print("staged: %d books in %s" % (len(books), DEPLOY_DIR))
    print("  files: %d / %d limit" % (files, FILE_LIMIT))
    print("  size:%.1f GB" % (total / 1073741824))
    print("  sitemap: %d urls" % len(urls))
    if files > FILE_LIMIT:
        raise SystemExit("file count over the Pages limit")


if __name__ == "__main__":
    main()