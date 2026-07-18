"""
Tests the keyword matching that decides which raw GeM search results are
"broad matches" vs. "precise, auto-download-worthy matches". This is
business logic that's genuinely easy to get subtly wrong (see: the whole
"school uniform" vs "uniform" saga in ROADMAP.md) -- worth pinning down with
real tests using real data, not just trusting it by inspection.
"""
from app.utils.keywords import matches_any_keyword, SCHOOL_UNIFORM_KEYWORDS


def test_precise_school_uniform_title_matches():
    title = "Pre School Uniform - Shirt as per Government of Gujarat Specification"
    matches = matches_any_keyword(title, SCHOOL_UNIFORM_KEYWORDS)
    assert "school uniform" in matches


def test_unrelated_manpower_tender_does_not_match():
    # Real noise tender confirmed during live testing: matched GeM's own
    # "uniform" search only because of "High School" appearing in an
    # unrelated education-qualification requirement field.
    title = "Manpower Outsourcing Services - Minimum wage - Unskilled; High School; Others"
    matches = matches_any_keyword(title, SCHOOL_UNIFORM_KEYWORDS)
    assert matches == []


def test_pt_uniform_matches():
    title = "PT Uniform ( Sports Shorts ) - Defence"
    matches = matches_any_keyword(title, SCHOOL_UNIFORM_KEYWORDS)
    assert "pt uniform" in matches


def test_broad_uniform_tender_with_no_precise_match_still_returns_empty_not_error():
    # These should be SAVED (broad match) but not auto-downloaded (no
    # precise match) -- confirming the function itself just reports "no
    # match" cleanly rather than raising.
    title = "Biosecurity Scrub Uniform (Top & Bottom)"
    matches = matches_any_keyword(title, SCHOOL_UNIFORM_KEYWORDS)
    assert matches == []


def test_matching_is_case_insensitive():
    title = "CC KND/NIV/CL1/238 PT UNIFORM ( T-SHIRT & SHORTS) S/LARGE"
    matches = matches_any_keyword(title, SCHOOL_UNIFORM_KEYWORDS)
    assert "pt uniform" in matches
