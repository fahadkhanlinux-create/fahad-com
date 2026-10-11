#!/usr/bin/env python3
"""Select public-domain books matching the themes Fahad asked for.

The named modern titles (Deep Work, Blue Ocean Strategy, The 5 AM Club,
What Every Body is Saying, Thinking, Fast and Slow) are all still in copyright, so
this picks the public-domain lineage of those subjects instead:

  AI & Computing  -> logic, computing, cybernetics-era theory of mind/machines
  Self-Help       -> habit, self-improvement, personal effectiveness
  Strategy        -> strategy, competition, management, leadership
  Psychology      -> decision-making, judgement, reasoning, influence

Every candidate must be non-fiction (Gutenberg tags fiction explicitly), must have a
usable text/metadata record, and must not already be in the library. Results are
written to tools/theme_selection.json for build_theme_books.py to consume.
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "tools"))

import categorize as C  # noqa: E402

CATALOG = os.path.join(BASE, "tools", "guten_catalog.json")
META = os.path.join(BASE, "tools", "guten_meta.json")
CLASSIFIED = os.path.join(BASE, "tools", "guten_classified.json")
DATA = os.path.join(BASE, "data", "books.json")
OUT = os.path.join(BASE, "tools", "theme_selection.json")

# how many books to take per theme, weighted toward the topics named explicitly
WANT = {
    "AI & Computing": int(os.environ.get("WANT_AI", "120")),
    "Self-Help": int(os.environ.get("WANT_SELFHELP", "180")),
    "Strategy": int(os.environ.get("WANT_STRATEGY", "200")),
    "Psychology": int(os.environ.get("WANT_PSYCH", "160")),
}

FICTION_SUBJECT = re.compile(r"(--\s*fiction\b|\bfiction\b|\bstories\b|\bnovels?\b|\btales?\b)", re.I)
LATIN_OK = re.compile(r"[A-Za-z0-9À-ɏ&,'’\-\.:()! ]")
NON_LATIN_TITLES = 0.3

# Signals per theme. Keyword rules alone were not precise enough: "character" pulled in
# the Odyssey and "tactics" pulled in an artillery handbook, so a theme now has to satisfy
# BOTH an LCC class (the Library of Congress shelf, which is reliable metadata) AND a
# curated keyword subject signal. Only bare, unambiguous phrases are checked in titles.
LCC_FOR = {
    "AI & Computing": {"QA", "TA", "TE", "TK", "TR", "QK", "QL", "QM"},
    "Self-Help": {"BF", "BJ", "T"},
    "Strategy": {"HF", "HD", "HQ", "HC", "HE", "H", "T"},
    "Psychology": {"BF", "BJ", "QH", "QP", "HQ"},
}

THEME_RULES = {
    "AI & Computing": [
        r"artificial intelligence", r"cybernetics", r"logic, symbolic",
        r"algebraic logic", r"mathematical logic", r"symbolic logic",
        r"\blogic\b", r"\bautomata\b", r"\bcomputing\b", r"\bcomputers?\b",
        r"calculating machine", r"\bboole\b", r"boolean", r"data processing",
        r"numerical analysis", r"\bprobability\b", r"\bstatistics\b",
        r"\bmathematics\b", r"\balgebra\b", r"\bgeometry\b", r"\bcalculus\b",
        r"\barithmetic\b", r"\btrigonometry\b", r"\baxioms?\b",
    ],
    "Self-Help": [
        r"self-improv", r"self help", r"self-culture", r"\bself-development\b",
        r"\bmotivation\b", r"will power", r"self-reliance", r"\bperseverance\b",
        r"\bindustr(?:y|ious)\b", r"\bapplication\b", r"\badvice\b",
        r"\bconduct\b", r"\bmanners\b", r"\betiquette\b", r"\bself-control\b",
        r"\bhabits?\b", r"\bsuccess\b", r"\bambition\b",
    ],
    "Strategy": [
        r"\bstrateg", r"\bcompetitive\b", r"\bmarketing\b", r"\bmanagement\b",
        r"\bleadership\b", r"\bbusiness\b", r"\bcommerce\b", r"\bcapital\b",
        r"\bwealth\b", r"\benterprise\b", r"\borganizations?\b", r"\bnegotiat",
        r"political economy", r"art of war", r"military",
    ],
    "Psychology": [
        r"decision[- ]?making", r"\bjudgment\b", r"\bjudgement\b",
        r"\breasoning\b", r"critical thinking", r"problem solving",
        r"\battention\b", r"\bmemory\b", r"\bthinking\b", r"\bmind\b",
        r"\bconsciousness\b", r"\bperception\b", r"\bassociation\b",
        r"\binsight\b", r"\bmotives\b", r"\binfluence\b", r"\bhypnot",
        r"\bhabit\b", r"\bsuggestion\b", r"\bwill\b", r"\bpsycholog",
    ],
}

# single unambiguous phrases are also worth a look in the title
TITLE_RULES = {
    "AI & Computing": [
        r"algebra of logic", r"laws of thought", r"thought machines?", r"\bboole\b",
        r"\bcybernetics\b", r"\bartificial intelligence\b", r"\blogic\b",
        r"calculating engine", r"analytical engine", r"\bcomputers?\b",
    ],
    "Self-Help": [
        r"self[- ]help", r"self[- ]culture", r"self[- ]improv", r"as a man thinketh",
        r"how to (?:live|succeed|be)", r"\bhabits?\b", r"\bsuccess\b",
        r"\bcharacter\b", r"\bmanners\b", r"\bself culture\b",
    ],
    "Strategy": [
        r"art of war", r"\bstrateg", r"business\b", r"leadership\b",
        r"management\b", r"competition\b", r"wealth of nations",
    ],
    "Psychology": [
        r"decision[- ]making", r"\breasoning\b", r"\bjudgment\b", r"\bjudgement\b",
        r"\bmind\b", r"\bmemory\b", r"\battention\b", r"\binsight\b",
        r"interpretation of dreams", r"\bhabits?\b", r"\bpsycholog",
    ],
}

# periodicals, proceedings and multi-volume compilations are not readable how-to books
REJECT_TITLE = re.compile(
    r"\b(journal|proceedings|transactions|bulletin|quarterly|annual report|"
    r"report of the|associat|congress|exposition|vol(?:ume|\.)\s*[0-9ivx]+|"
    r"part\s*[0-9]+|series|no\.\s*[0-9]+|readings|speeches and addresses of|"
    r"extracts? from|collected works\b|complete works\b)\b",
    re.I,
)


def compiled(rules):
    return [re.compile(r"\b" + r + r"\b", re.I) for r in rules]


def mostly_non_latin(text):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    frac = sum(0 if LATIN_OK.match(c) else 1 for c in letters) / len(letters)
    return frac > NON_LATIN_TITLES


def theme_of(lcc, subjects, title, author):
    """Strongest theme for a book, or None when it does not match the ask.

    A theme requires an agreeing LCC class *and* a curated keyword signal, so a
    military tactics handbook cannot become a "Strategy" business title and a myth of
    Odysseus cannot become a "Self-Help" book about its character. The title is a
    fallback only for classics with thin subject metadata.
    """
    hay = " ; ".join(subjects)
    for theme in ("AI & Computing", "Self-Help", "Strategy", "Psychology"):
        if lcc[:2] not in LCC_FOR[theme]:
            continue
        if any(p.search(hay) for p in compiled(THEME_RULES[theme])):
            return theme
    t = " ; " + title
    for theme in ("AI & Computing", "Self-Help", "Strategy", "Psychology"):
        if lcc[:2] not in LCC_FOR[theme]:
            continue
        if any(p.search(t) for p in compiled(TITLE_RULES[theme])):
            return theme
    return None


def main():
    catalog = json.load(open(CATALOG, encoding="utf-8"))
    meta = json.load(open(META, encoding="utf-8")) if os.path.exists(META) else {}
    cls = json.load(open(CLASSIFIED, encoding="utf-8")) if os.path.exists(CLASSIFIED) else {}

    existing = json.load(open(DATA, encoding="utf-8")) if os.path.exists(DATA) else []
    have_ids = {e["id"] for e in existing}
    have_gids = {str(e.get("gid") or e["id"].rsplit("-", 1)[-1]) for e in existing}

    seen_keys = set()
    for e in existing:
        t = re.sub(r"[^a-z0-9]+", " ", (e.get("title") or "").lower()).strip()
        a = re.sub(r"[^a-z0-9]+", " ", (e.get("author") or "").lower()).strip()
        seen_keys.add((t, re.sub(r",.*$", "", a).strip()))

    from build_library import is_reference_volume

    buckets = defaultdict(list)
    seen_gid = set()
    for e in catalog:
        gid = str(e["gid"])
        if gid in have_gids or gid in seen_gid:
            continue
        title = (e.get("title") or "").strip()
        author = (e.get("author") or "").strip() or "Unknown"
        if not title or len(title) < 3 or re.match(r"^(the )?project gutenberg", title, re.I):
            continue
        if REJECT_TITLE.search(title):
            continue
        if mostly_non_latin(title) or mostly_non_latin(author):
            continue
        key = (
            re.sub(r"[^a-z0-9]+", " ", title.lower()).strip(),
            re.sub(r",.*$", "", re.sub(r"[^a-z0-9]+", " ", author.lower()).strip()),
        )
        if key in seen_keys:
            continue

        m = meta.get(gid, {})
        subjects = m.get("subjects", []) or []
        joined = " ; ".join(subjects)
        # Gutenberg tags fiction explicitly; never let a story leak into a how-to shelf
        if FICTION_SUBJECT.search(joined):
            continue
        lcc = (m.get("lcc") or "").strip().upper()
        if lcc.startswith(("P", "F", "J")) and lcc not in ("PA", "BF", "BJ"):
            continue

        theme = theme_of(lcc, subjects, title, author)
        if not theme:
            continue

        seen_keys.add(key)
        seen_gid.add(gid)
        bid = f"{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:58]}-{gid}"
        if bid in have_ids:
            continue
        entry = dict(
            id=bid, gid=int(gid), title=title, author=author, year="", category=theme,
            desc=cls.get(gid, {}).get("desc") or C.make_desc(e, m, theme),
        )
        entry["reference-volume"] = is_reference_volume(entry)
        buckets[theme].append(entry)

    picked = []
    for theme, want in WANT.items():
        pool = buckets.get(theme, [])
        # skip the giant reference volumes; they are not what this shelf is for
        usable = [b for b in pool if not b["reference-volume"]]
        usable.sort(key=lambda b: b["title"].lower())
        picked += usable[:want]
        print(f"{theme:16} matched {len(pool):5}  usable {len(usable):5}  taking {min(want, len(usable))}")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(picked, f, indent=1, ensure_ascii=False)
    print(f"\nwrote {len(picked)} books -> {OUT}")
    print("per category:", dict(Counter(b["category"] for b in picked)))


if __name__ == "__main__":
    main()