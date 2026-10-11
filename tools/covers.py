#!/usr/bin/env python3
"""Project Gutenberg cover-URL helpers.

Gutenberg serves a small JPEG per ebook at a predictable path
(cache/epub/<gid>/pg<gid>.cover.medium.jpg) for the large majority of books, and
404s for the rest. Callers reference the URL directly and let <img> fall back to the
generated category cover, so a missing image never needs a build-time check.
"""
COVER_TMPL = "https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.cover.medium.jpg"


def cover_url(gid):
    return COVER_TMPL.format(gid=gid)