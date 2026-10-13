#!/usr/bin/env python3
"""Regenerate sitemap.xml from data/books.json."""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data", "books.json")
SITEMAP = os.path.join(BASE, "sitemap.xml")
ORIGIN = "https://fahad.com"


def main():
    books = json.load(open(DATA, encoding="utf-8"))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        f'  <url><loc>{ORIGIN}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>',
        f'  <url><loc>{ORIGIN}/modern.html</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>',
    ]
    for b in books:
        lines.append(
            f"  <url><loc>{ORIGIN}/book.html?id={b['id']}</loc>"
            f"<changefreq>monthly</changefreq><priority>0.8</priority></url>"
        )
    lines.append("</urlset>")
    with open(SITEMAP, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"sitemap.xml: {len(books) + 2} urls")


if __name__ == "__main__":
    main()