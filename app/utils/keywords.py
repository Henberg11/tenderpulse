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
# relevant. So we search broad with