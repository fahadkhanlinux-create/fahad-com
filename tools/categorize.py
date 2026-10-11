#!/usr/bin/env python3
"""Map Project Gutenberg metadata to Fahad.com categories and write book descriptions.

Signals are applied strongest-first: explicit subject headings, then the LoC class,
then title/author keywords. Every keyword is matched on word boundaries, and any
subject carrying a "-- Fiction" qualifier wins early so novels never leak into
non-fiction categories.
"""
import json
import os
import re
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
META = os.path.join(BASE, "tools", "guten_meta.json")

CATEGORIES = [
    "Fiction", "Children", "Science", "AI & Computing", "Technology", "History",
    "Biography", "Philosophy", "Psychology", "Self-Help", "Business", "Poetry",
    "Strategy", "Islam & Religion", "Sports & Games", "Society",
    "Language & Reference",
]

LCC_MAP = {
    "PZ": "Children", "PR": "Fiction", "PS": "Fiction", "PT": "Fiction",
    "PG": "Fiction", "PQ": "Fiction", "PL": "Fiction", "PM": "Fiction",
    "PN": "Fiction", "PK": "Fiction", "PA": "Philosophy", "P": "Fiction",
    "QA": "Science", "QB": "Science", "QC": "Science", "QD": "Science",
    "QE": "Science", "QH": "Science", "QK": "Science", "QL": "Science",
    "QM": "Science", "QP": "Science", "QR": "Science", "Q": "Science",
    "R": "Science", "S": "Science", "T": "Science",
    "TA": "Technology", "TC": "Technology", "TD": "Technology", "TE": "Technology",
    "TH": "Technology", "TJ": "Technology", "TP": "Technology", "TR": "Technology",
    "TS": "Technology", "TT": "Technology", "TX": "Technology",
    "U": "Strategy", "V": "Strategy",
    "D": "History", "DA": "History", "DB": "History", "DC": "History",
    "DD": "History", "DE": "History", "DF": "History", "DG": "History",
    "DH": "History", "DK": "History", "DL": "History", "DP": "History",
    "DQ": "History", "DS": "History", "E": "History", "F": "History",
    "G": "History", "DT": "Biography",
    "J": "Society", "K": "Society",
    "BF": "Psychology", "BJ": "Philosophy", "BH": "Philosophy",
    "B": "Philosophy", "BD": "Philosophy", "BL": "Islam & Religion",
    "BP": "Islam & Religion", "BQ": "Islam & Religion", "BR": "Islam & Religion",
    "BS": "Islam & Religion", "BT": "Islam & Religion", "BV": "Islam & Religion",
    "BX": "Islam & Religion",
    "GV": "Sports & Games",
    "HD": "Business", "HF": "Business", "HG": "Business", "HE": "Business",
    "HJ": "Business", "HM": "Society", "HN": "History", "HQ": "Society",
    "HS": "Society", "HT": "Society", "H": "Society",
    "LA": "Science", "LB": "Science", "LC": "Science", "LD": "Society",
    "ML": "Philosophy", "GN": "Philosophy", "GR": "Philosophy",
    "Z": "Fiction", "NC": "Children",
}

# subjects that unambiguously mean fiction
FICTION_SUBJECT = re.compile(
    r"(^|\s)--\s*fiction\b|\bfiction\b|\bstories\b|\bnovels?\b|\btales?\b|"
    r"\bliterature\b|\bverse\b|\bpoetry\b|\bpoems\b",
    re.I,
)
POETRY_SUBJECT = re.compile(r"\bpoetry\b|\bpoems\b|\bverse\b|\blyric\b|\bballad", re.I)
# LCSH personal heading with life dates: "Wagner, Richard, 1813-1883"
PERSON_SUBJECT = re.compile(r"^[A-Z][\w'’\-]+,\s+[A-Z][^:]*\d{3,4}\s*[-–]\s*\d{2,4}\b", re.UNICODE)
CHILDREN_SUBJECT = re.compile(
    r"\bjuvenile\b|\bchildren\b|\bfairy tales\b|\bpicture books\b|"
    r"\byoung readers\b|\bchildren's\b|\bnursery\b|\bboys\b|\bgirls\b",
    re.I,
)

# checked in order against the joined subject list
SUBJECT_RULES = [
    ("Islam & Religion", [
        "bible", "christianity", "christian", "jesus christ", "theology",
        "church", "devotional", "sermon", "mormonism", "buddhism", "hinduism",
        "judaism", "islam", "qur'an", "quran", "koran", "biblical", "gospel",
        "hymns", "prayers", "parables", "christ", "catholic", "protestant",
        "evangelical", "missionary", "sin", "salvation", "soul", "heaven",
    ]),
    ("Psychology", [
        "psychology", "psychoanalysis", "psychoanalytic", "unconscious",
        "mental health", "mental illness", "hypnosis", "hypnotism", "psychic",
        "psychotherapy", "subconscious", "phantasy", "psyche", "emotions",
        "nervous system", "suggestion", "dreams", "habit formation",
        "child development", "intelligence tests", "attention",
    ]),
    ("Biography", [
        "biography", "biographies", "autobiography", "autobiographies",
        "memoirs", "personal narrative", "correspondence", "diaries",
        "letters of", "journal", "diary", "life and work", "criticism and interpretation",
    ]),
    ("AI & Computing", [
        "artificial intelligence", "computing", "computer", "data processing",
        "cybernetics", "information theory", "algorithms", "programming",
        "boolean algebra", "symbolic logic", "mathematical logic", "formal logic",
        "logic, symbolic and mathematical", "electronic computers",
        "telecommunication", "telegraph", "telephone", "wireless telegraphy",
        "machine intelligence", "automata", "number theory", "calculus",
        "algebra", "geometry", "probability", "mathematics", "mathematical",
    ]),
    ("Self-Help", [
        "self-help", "self improvement", "self-development", "success",
        "conduct of life", "willpower", "motivation", "personal finance",
        "time management", "happiness", "productivity", "habits", "moral character",
        "wisdom", "advice", "inspirational", "meditation", "asceticism",
    ]),
    ("Business", [
        "economics", "economy", "commerce", "commercial", "business",
        "finance", "financial", "capital", "banking", "investment", "stock",
        "trade", "industry", "manufacturing", "accounting", "advertising",
        "marketing", "transportation", "railroads", "railways", "cooperative",
        "tariffs", "taxation", "labor", "sociology", "social conditions",
    ]),
    ("Strategy", [
        "military art", "military science", "war", "soldier", "army", "navy",
        "artillery", "fortification", "strategy", "tactics", "naval", "campaign",
        "weapon", "battle", "infantry", "cavalry", "siege", "martial",
    ]),
    ("Children", ["juvenile", "fairy tales", "picture books", "young readers", "nursery"]),
    ("Science", [
        "science", "natural history", "physics", "chemistry", "biology",
        "astronomy", "geology", "zoology", "botany", "botanical", "entomology",
        "evolution", "physiology", "anatomy", "medicine", "medical", "geography",
        "meteorology", "natural philosophy", "mineralogy", "geology and mineralogy",
        "ornithology", "ichthyology", "mycology", "electricity and magnetism",
    ]),
    ("Technology", [
        "engineering", "mechanical engineering", "mechanics", "machinery",
        "electricity", "electrical", "inventions", "invention", "technology",
        "metallurgy", "mining", "locomotive", "steam", "boiler", "construction",
        "architecture", "agriculture", "farming", "horticulture", "gardening",
        "manufactures", "textiles", "chemistry -- technical",
    ]),
    ("History", [
        "history", "historical", "historians", "civilization", "chronicle",
        "annals", "antiquity", "medieval", "antiquities", "biography -- history",
        "social history", "military history", "church history", "archaeology",
    ]),
    ("Philosophy", [
        "philosophy", "philosophical", "ethics", "ethical", "metaphysics",
        "stoicism", "stoics", "idealism", "philosophers", "immortality",
        "consciousness", "aesthetics", "knowledge", "reasoning", "skepticism",
        "soul", "virtue", "morals", "religion and philosophy",
    ]),
    ("Sports & Games", [
        "sports", "sport", "games", "gymnastics", "athletics", "fishing",
        "hunting", "horsemanship", "chess", "cards", "cycling", "swimming",
        "boxing", "rowing", "skating", "skiing",
    ]),
    ("Poetry", ["poetry", "poems", "verse", "poetic", "sonnet", "ballad", "lyric"]),
    ("Language & Reference", ["dictionaries", "dictionary of", "etymolog", "lexicon",
                              "grammar", "thesaurus", "vocabulary", "phrase books"]),
    ("Fiction", ["juvenile fiction", "historical fiction", "fantasy fiction"]),
]

TITLE_RULES = [
    ("Children", ["children", "child", "girl", "boy", "fairy", "juvenile", "nursery", "little folks"]),
    ("Poetry", ["poems", "poetry", "verse", "sonnets", "ballads", "lyrics"]),
    ("Islam & Religion", ["bible", "quran", "koran", "church", "christian", "devotional", "gospel"]),
    ("AI & Computing", ["computer", "calculus", "algebra", "logic", "mathemat", "einstein", "relativity"]),
    ("Technology", ["engine", "electric", "invention", "mechanic", "machine", "telegraph", "steam", "engineering"]),
    ("Science", ["science", "natural history", "astronom", "physics", "chemistr", "biol", "geolog",
                 "zoolog", "botan", "evolution", "medicine", "medical", "electricit"]),
    ("Self-Help", ["self-help", "self help", "success", "habit", "thinking", "thought", "will", "mind",
                   "living", "fortune", "rich", "wisdom", "character"]),
    ("History", ["history", "histor", "empire", "chronicle", "war of"]),
    ("Philosophy", ["philosoph", "ethic", "stoic", "socratic", "plato", "aristotle", "meditations"]),
    ("Psychology", ["psycholog", "psychoanaly", "dream", "habits of"]),
    ("Business", ["econom", "wealth", "money", "commerce", "bank", "capital", "business"]),
    ("Biography", ["life of", "memoir", "autobiograph", "letters of", "diary of"]),
    ("Sports & Games", ["sport", "gymnastic", "fishing", "hunting", "chess"]),
    ("Language & Reference", ["dictionary", "lexicon", "grammar", "thesaurus", "etymolog", "vocabulary"]),
    ("Strategy", ["military", "soldier", "navy", "artillery", "war"]),
]

# readable noun phrase per category for the generated description
DESC_LABEL = {
    "AI & Computing": "AI and computing",
    "Islam & Religion": "religion",
    "Language & Reference": "reference",
    "Society": "society and culture",
    "Sports & Games": "sports",
}

_RULES = None


def compiled(rules):
    global _RULES
    if _RULES is None:
        out = []
        for cat, kws in rules:
            out.append((cat, [re.compile(r"\b" + re.escape(k) + r"\b", re.I) for k in kws]))
        _RULES = out
    return _RULES


def match_rule(rules, haystack):
    for cat, pats in compiled(rules):
        if any(p.search(haystack) for p in pats):
            return cat
    return None


def humanize(subject):
    parts = [p.strip() for p in re.split(r"\s*--\s*", subject) if p.strip()]
    parts = [re.sub(r"\s*\(Fictitious character\)", "", p).strip() for p in parts]
    parts = [p for p in parts if p and len(p) < 70]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return parts[0] + ": " + ", ".join(parts[1:])


def make_desc(entry, meta, category):
    topics, seen = [], set()
    for raw in meta.get("subjects", []):
        h = humanize(raw)
        if not h or len(h) < 4:
            continue
        k = h.lower()
        if k in seen:
            continue
        seen.add(k)
        topics.append(h)
        if len(topics) == 3:
            break

    author = (entry.get("author") or "").strip()
    label = DESC_LABEL.get(category, category.lower())
    lead = f"A free public-domain {label} classic from Project Gutenberg"
    if topics:
        return lead + " — " + "; ".join(topics) + "."
    if author and author != "Unknown":
        return f"{author}'s {entry.get('title','').strip() or 'book'} — {lead}."
    return lead + "."


def categorize(entry, meta):
    subjects = meta.get("subjects", []) or []
    joined = " ; ".join(subjects)
    lcc = (meta.get("lcc") or "").strip().upper()
    base = LCC_MAP.get(lcc, "")
    title = ((entry.get("title") or "") + " " + (entry.get("author") or "")).lower()

    # 1. poetry is unambiguous
    if POETRY_SUBJECT.search(joined):
        return "Poetry"

    # 2. an LCSH personal heading means a life/biography
    if lcc == "DT" or any(PERSON_SUBJECT.match(s.strip()) for s in subjects):
        return "Biography"

    # 3. an explicit fiction qualifier beats any other subject reading
    if FICTION_SUBJECT.search(joined) and lcc not in ("B", "BD", "BJ", "BH", "BF", "PZ", "GV"):
        return "Fiction"

    # 4. literature class means fiction unless a strong non-fiction signal says otherwise
    if lcc.startswith("P") and lcc not in ("PZ", "PA"):
        strong = match_rule(SUBJECT_RULES, joined)
        if strong in ("Islam & Religion", "Psychology", "Biography", "Poetry"):
            return strong
        return "Fiction"

    # 5. strong subject signals
    cat = match_rule(SUBJECT_RULES, joined)
    if cat:
        return cat

    # 6. LoC class default
    if base and base != "Society":
        return base

    # 7. title / author heuristics
    if lcc == "PZ" or CHILDREN_SUBJECT.search(joined):
        return "Children"
    cat = match_rule(TITLE_RULES, title)
    if cat:
        return cat

    if base:
        return base
    if lcc.startswith("J") or lcc.startswith("H"):
        return "Society"
    return "Fiction"


def main():
    catalog = json.load(open(os.path.join(BASE, "tools", "guten_catalog.json"), encoding="utf-8"))
    meta = json.load(open(META, encoding="utf-8")) if os.path.exists(META) else {}
    out = {}
    dist = Counter()
    for e in catalog:
        m = meta.get(str(e["gid"]), {})
        cat = categorize(e, m)
        dist[cat] += 1
        out[str(e["gid"])] = {"category": cat, "desc": make_desc(e, m, cat)}
    with open(os.path.join(BASE, "tools", "guten_classified.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"classified {len(out)} books (metadata for {len(meta)})")
    for c, n in dist.most_common():
        print(f"  {c:20} {n}")


if __name__ == "__main__":
    main()