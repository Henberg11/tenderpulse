"""
Keyword sets a crawler matches against tender titles/categories to decide what
to ingest. Kept as data, not hardcoded into crawler logic.
"""

# Precise phrases used to decide "is this tender actually relevant" -- checked
# against each tender's real, full title after it's been fetched from GeM.
# shoes/socks/belt kept here (not as search terms, see below) since they're
# still a legitimate signal once a tender's already been found some other
# way -- a genuine uniform set often lists them alongside pants/shirts.
# pant/shirt/kurta/salwar added after confirming, against real tenders
# already captured this session, that these garment pieces are strong,
# consistent signals of genuine uniform-set tenders (e.g. "Full Pants, Full
# Sleeve Shirt, Tie, Sweater...", "Boys Shirt, Boys Pant, Girls Kurta, Girls
# Salwar...").
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
    "pant",
    "shirt",
    "kurta",
    "salwar",
]

# What we actually type into GeM's search box. GeM's search matches individual
# words, not phrases -- confirmed by testing: searching "school uniform"
# returned 1,118 results, almost all irrelevant (matching "School" in
# education-qualification requirements for cleaning-staff tenders, nothing to
# do with uniforms). Searching just "uniform" returned 63 results, mostly
# relevant. So we search broad with single words here, then filter precisely
# with SCHOOL_UNIFORM_KEYWORDS against each real tender title afterward.
#
# Deliberately NOT searching "shoes"/"socks"/"belt" directly -- confirmed via
# real testing that standalone accessory searches pull in a lot of unrelated
# noise (safety boots, industrial belts, footwear for entirely different
# purposes) that has nothing to do with uniforms. Garment pieces
# (pant/shirt/kurta/salwar) are a much more targeted signal: standalone
# clothing tenders on a government portal are almost always institutional/
# uniform-related in the first place. Confirmed against real captured
# tenders this session -- these words appear consistently across genuine
# uniform sets ("Full Pants...Full Sleeve Shirt...", "Boys Shirt, Boys Pant,
# Girls Kurta, Girls Salwar..."). This also happens to catch tenders that
# list individual components without ever using the word "uniform" at all
# (the original gap that prompted this change, GEM/2026/B/7785360).
GEM_SEARCH_TERMS: list[str] = [
    "uniform",
    "sweater",
    "tracksuit",
    "textile",
    "apparel",
    "garment",
    "stitching",
    "pant",
    "pants",
    "shirt",
    "kurta",
    "salwar",
]


def matches_any_keyword(text: str, keywords: list[str] | None = None) -> list[str]:
    """Return the list of keywords that matched inside `text` (case-insensitive)."""
    keywords = keywords or SCHOOL_UNIFORM_KEYWORDS
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]