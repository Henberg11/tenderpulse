"""
Reads the actual tender PDF (not just the search-results title) and pulls
out two kinds of information:

1. FREE, no AI needed -- structured fields GeM's PDFs print in a consistent,
   labeled format (confirmed against a real downloaded tender document:
   "EMD Detail... Required: No/Yes", "Minimum Average Annual Turnover...",
   "Bid End Date/Time...", "Item Category..."). Plain text pattern matching,
   same approach as the search-results-page extraction in gem_crawler.py.

2. AI-generated, via Gemini's free tier -- a plain-English executive
   summary, eligibility summary, and risk factors, for the fine print that
   isn't in a predictable labeled format (buyer-added special terms,
   disqualification clauses, etc.) and genuinely benefits from an LLM
   actually reading and interpreting it.

NOTE ON FIELD EXTRACTION: the EMD-required=Yes case (where an actual EMD
amount is printed) hasn't been confirmed against a real example yet -- the
one real tender PDF inspected during development had EMD Required: No. The
regex below is a reasonable best guess; if EMD amounts aren't showing up
correctly once real EMD-required tenders are processed, that's the first
place to check and adjust, same as gem_crawler.py's search-page selectors.
"""
import hashlib
import json
import re

import fitz  # PyMuPDF
import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.config import settings
from app.models import Tender, TenderDocument
from app.utils.indian_states import extract_state

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Cap how much PDF text we send to the AI -- keeps requests fast, cheap on
# the free tier's token budget, and focused on the parts of a tender that
# actually matter (most of the useful content is in the first few pages;
# later pages are usually boilerplate T&Cs repeated across every GeM bid).
MAX_AI_INPUT_CHARS = 8000


def extract_pdf_text(pdf_path: str) -> str:
    """Pull all text out of a downloaded tender PDF."""
    try:
        doc = fitz.open(pdf_path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text
    except Exception:
        logger.exception(f"[doc-intel] failed to extract text from {pdf_path}")
        return ""


def extract_structured_fields(text: str) -> dict:
    """Free, no-AI extraction of GeM's standardized labeled fields.

    NOTE: only fields confirmed reliable against a real extracted tender PDF
    are included here. "Minimum Average Annual Turnover" was tried and
    dropped -- its label wraps across multiple lines in the real PDF layout
    ("...Annual Turnover of the\\nbidder (For 3 Years)\\n38 Lakh(s)"), which
    made simple line-after matching unreliable. That information still
    reaches the person via the AI eligibility_summary below, which reads the
    whole document rather than pattern-matching single lines."""
    fields: dict = {}

    emd_required = _extract_line_after(text, "Required", within_section="EMD Detail")
    if emd_required:
        fields["emd_required"] = "yes" in emd_required.lower()

    emd_amount = _search_amount(text, r"EMD\s+Amount[^\d]*([\d,]+(?:\.\d+)?)")
    if emd_amount is not None:
        fields["emd_amount"] = emd_amount

    category = _extract_line_after(text, "Item Category")
    if category:
        fields["category"] = category.strip()

    bid_end = _extract_line_after(text, "Bid End Date/Time")
    if bid_end:
        fields["bid_end_raw"] = bid_end.strip()

    # This is the field that actually answers "does this tender need
    # delivery/service in my state" -- confirmed against a real tender PDF
    # where the issuing department (Central Board of Direct Taxes, a
    # central body with no state in its name at all) required delivery
    # specifically in Gujarat. Matching on department name alone (the
    # weaker fallback used in app/services/ingestion.py, for tenders whose
    # PDF hasn't been downloaded yet) would have missed this entirely.
    geo_line = _extract_line_after(text, "Name of states/ UT for geographical presence is required")
    delivery_state = extract_state(geo_line) if geo_line else None
    if not delivery_state:
        # That exact label isn't present on every tender type -- fall back
        # to scanning the whole document for any state name mentioned
        # anywhere (e.g. in a consignee's address block), which is still a
        # meaningfully better signal than the department name alone.
        delivery_state = extract_state(text)
    if delivery_state:
        fields["delivery_state"] = delivery_state

    return fields


def _extract_line_after(text: str, label: str, within_section: str | None = None) -> str | None:
    search_text = text
    if within_section:
        section_match = re.search(re.escape(within_section) + r"(.{0,500})", text, re.DOTALL)
        if not section_match:
            return None
        search_text = section_match.group(1)

    # Separator between label and value varies in real GeM PDFs -- sometimes
    # a colon, sometimes just whitespace on the same line, sometimes the
    # value starts on the next line. This matches all three.
    match = re.search(re.escape(label) + r"\s*:?\s*([^\n]+)", search_text)
    return match.group(1).strip() if match else None


def _search_amount(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


async def summarize_with_gemini(text: str) -> dict | None:
    """Ask Gemini for a plain-English executive summary, eligibility
    summary, and risk factors. Returns None (rather than raising) on any
    non-retryable failure -- a summarization failure shouldn't break
    ingestion of an otherwise-good tender; the free-extraction fields above
    still get saved either way. Rate-limit errors (429, common on the free
    tier when several documents process back-to-back) ARE retried with
    backoff rather than immediately giving up -- confirmed necessary after
    a real crawl run hit this exact error."""
    if not settings.gemini_api_key:
        logger.warning("[doc-intel] no GEMINI_API_KEY configured, skipping AI summary")
        return None

    truncated = text[:MAX_AI_INPUT_CHARS]
    prompt = f"""You are reading a government tender document (India, GeM portal). Based on the text below, respond with ONLY a JSON object (no markdown fences, no other text) with exactly these three keys:

"executive_summary": 2-3 plain-English sentences on what's being procured and the key commercial terms.
"eligibility_summary": who is eligible to bid (turnover, experience, certifications required) in plain English.
"risk_factors": any clauses a bidder should be cautious about (tight deadlines, unusual penalty terms, disqualification conditions) -- or "None noted" if nothing stands out.

Tender document text:
{truncated}"""

    try:
        raw_text = await _call_gemini_with_retry(prompt)
        cleaned = re.sub(r"^```json\s*|\s*```$", "", raw_text.strip(), flags=re.MULTILINE)
        parsed = json.loads(cleaned)
        return {
            "executive_summary": parsed.get("executive_summary"),
            "eligibility_summary": parsed.get("eligibility_summary"),
            "risk_factors": parsed.get("risk_factors"),
        }
    except Exception:
        logger.exception("[doc-intel] Gemini summarization failed")
        return None


def _is_rate_limit_error(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429


@retry(
    retry=retry_if_exception(_is_rate_limit_error),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=5, min=5, max=60),
)
async def _call_gemini_with_retry(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            GEMINI_API_URL.format(model=settings.gemini_model),
            params={"key": settings.gemini_api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
        )
        response.raise_for_status()
        data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


async def process_downloaded_document(
    db: AsyncSession, tender: Tender, file_path: str, source_url: str | None = None
) -> TenderDocument:
    """The orchestration step: takes a file already saved to disk by the
    crawler and (1) records it properly in the database -- this wasn't
    happening at all before, documents were downloaded but never tracked --
    (2) extracts its text, (3) runs free structured-field extraction,
    (4) runs AI summarization, (5) updates the Tender with whatever was
    found. Every step degrades gracefully: a failure in AI summarization
    still leaves the document properly saved and the free-extraction fields
    applied.

    IMPORTANT: three different things need three different "already done"
    checks, not one shared shortcut -- confirmed necessary after a real bug
    where adding delivery-state extraction had zero effect on any tender
    that already had its AI summary, because an earlier version of this
    function returned early the moment an AI summary existed, skipping the
    free-extraction step too. Free structured extraction (EMD, category,
    delivery state) is cheap and un-rate-limited, so it always runs on
    every pass -- only the expensive Gemini call is skipped once a summary
    already exists."""
    content_hash = _hash_file(file_path)

    existing_result = await db.execute(select(TenderDocument).where(TenderDocument.content_hash == content_hash))
    existing_doc = existing_result.scalar_one_or_none()

    if existing_doc:
        text = existing_doc.extracted_text or extract_pdf_text(file_path)
        doc = existing_doc
    else:
        text = extract_pdf_text(file_path)
        doc = TenderDocument(
            tender_id=tender.id,
            file_name=file_path.split("/")[-1],
            file_type="pdf",
            source_url=source_url,
            storage_path=file_path,
            content_hash=content_hash,
            extracted_text=text[:50000] if text else None,  # cap stored text size
        )
        db.add(doc)

    if text:
        structured = extract_structured_fields(text)
        if structured.get("emd_amount") is not None and tender.emd_amount is None:
            tender.emd_amount = structured["emd_amount"]
        if structured.get("category") and not tender.category:
            tender.category = structured["category"][:200]
        if structured.get("delivery_state"):
            # Overrides (not just fills in) the department-name-based guess
            # from ingestion.py -- the actual delivery/service-location
            # field inside the document is a genuinely more reliable signal
            # than inferring from who issued the tender, confirmed by a
            # real case where a central department's tender required
            # Gujarat delivery despite having no state in its own name.
            tender.location = structured["delivery_state"]

        if tender.ai_executive_summary:
            logger.info(f"[doc-intel] {tender.tender_number} already has an AI summary, skipping Gemini call")
        else:
            ai_result = await summarize_with_gemini(text)
            if ai_result:
                tender.ai_executive_summary = ai_result.get("executive_summary")
                tender.ai_eligibility_summary = ai_result.get("eligibility_summary")
                tender.ai_risk_factors = ai_result.get("risk_factors")
                logger.info(f"[doc-intel] AI summary generated for {tender.tender_number}")
            else:
                logger.info(f"[doc-intel] no AI summary for {tender.tender_number} (skipped or failed, see above)")

    await db.flush()
    return doc


def _hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]
