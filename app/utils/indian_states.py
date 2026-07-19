"""
GeM's "Department Name And Address" text (captured as organisation_name)
usually ends with the state/UT name -- confirmed against real examples like
"Tribal Welfare and Scheduled Caste (SC) Department Madhya Pradesh" and
"Urban Development Department Karnataka". This extracts it, so tenders can
be filtered by state on the dashboard without needing a separate crawl step.

Note: this is a best-effort text match, not a guaranteed-accurate field
GeM provides explicitly on the search results page. Central government
departments (Ministry of Defence, Railways, etc.) generally won't match any
state -- that's expected and correct, not a bug; they're national bodies.
"""
import re

INDIAN_STATES_AND_UTS: list[str] = [
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
    "Andaman and Nicobar Islands",
    "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Jammu and Kashmir",
    "Ladakh",
    "Lakshadweep",
    "Puducherry",
]

# Longest names first, so "Andhra Pradesh" is checked before a hypothetical
# shorter substring match could interfere -- not currently an issue with
# this list, but a cheap safeguard if the list grows.
_STATES_BY_LENGTH = sorted(INDIAN_STATES_AND_UTS, key=len, reverse=True)


def extract_state(text: str | None) -> str | None:
    """Return the first Indian state/UT name found in the text, or None if
    it looks like a central/national body (Ministry of Defence, Railways,
    etc. won't match any state -- that's expected, not a failure)."""
    if not text:
        return None
    for state in _STATES_BY_LENGTH:
        if re.search(r"\b" + re.escape(state) + r"\b", text, re.IGNORECASE):
            return state
    return None
