"""
Keyword sets a crawler matches against tender titles/categories to decide what
to ingest. Kept as data, not hardcoded into crawler logic.
"""

# Precise phrases used to decide "is this tender actually relevant" -- checked
# against each tender's real, full title after it's been fetched from GeM.
SCHOOL_UNIFORM_KEYWORDS: list[str] = [
    "school uniform",
    "pt uniform",
    "sports uniform",
    "sweater",
    "shoes",
    "socks",
    "belt",
    "school bag",
    "textile",
    "apparel",
    "garment",
    "stitching",
    "fabric supply",
    "readymade uniform",
    "tracksuit",
    "school dress",
]

# What we actually type into GeM's search box. GeM's search matches individual
# words, not phrases -- confirmed by testing: searching "school uniform"
# returned 1,118 results, almost all irrelevant (matching "School" in
# education-qualification requirements for cleaning-staff tenders, nothing to
# do with uniforms). Searching just "uniform" returned 63 results, mostly
# relevant. So we search broad with single words here, then filter precisely
# with SCHOOL_UNIFORM_KEYWORDS against each real tender title afterward.
#
# shoes/socks/belt added after confirming a real missed tender
# (GEM/2026/B/7785360, "Full Pants... Belt With Monogram Buckle... School
# Shoes Black...") that never contained the word "uniform" at all -- it just
# listed individual uniform components. Since "shoes", "socks", and "belt"
# are already in SCHOOL_UNIFORM_KEYWORDS above, adding them here both
# surfaces tenders like this AND correctly recognizes them as Core Matches
# once found (no extra step needed) -- they were previously invisible from
# the very first search step, before precise matching ever got a chance to
# run.
GEM_SEARCH_TERMS: list[str] = [
    "uniform",
    "sweater",
    "tracksuit",
    "textile",
    "apparel",
    "garment",
    "stitching",
    "shoes",
    "socks",
    "belt",
]


def matches_any_keyword(text: str, keywords: list[str] | None = None) -> list[str]:
    """Return the list of keywords that matched inside `text` (case-insensitive)."""
    keywords = keywords or SCHOOL_UNIFORM_KEYWORDS
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]
