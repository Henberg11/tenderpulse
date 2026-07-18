"""
Tests the free (no-AI) structured field extraction against real text shapes
confirmed from an actual downloaded GeM tender PDF (GEM/2026/B/7767826,
inspected during development -- see comments in document_intelligence.py).
"""
from app.services.document_intelligence import extract_structured_fields


def test_extracts_emd_not_required():
    text = """
Bid Details
Bid End Date/Time 16-07-2026 16:00:00
Item Category
Manpower Outsourcing Services - Minimum wage - Unskilled; High School; Others
EMD Detail
Required No
"""
    result = extract_structured_fields(text)
    assert result["emd_required"] is False


def test_extracts_bid_end_date():
    text = "Bid End Date/Time 16-07-2026 16:00:00\nBid Opening Date/Time"
    result = extract_structured_fields(text)
    assert result["bid_end_raw"] == "16-07-2026 16:00:00"


def test_extracts_item_category():
    text = "Item Category\nManpower Outsourcing Services - Minimum wage - Unskilled; High School; Others\nContract Period"
    result = extract_structured_fields(text)
    assert "Manpower Outsourcing" in result["category"]


def test_handles_missing_fields_gracefully():
    # A document with none of the expected labels shouldn't raise --
    # just returns an empty dict.
    result = extract_structured_fields("Some unrelated PDF text with no labels at all")
    assert result == {}


def test_emd_amount_extraction_when_present():
    text = "EMD Amount: 50000\nOther details"
    result = extract_structured_fields(text)
    assert result.get("emd_amount") == 50000.0
