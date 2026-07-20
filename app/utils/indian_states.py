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


# Confirmed necessary via real evidence, not a guess: central-government
# tender documents (Ministry of Defence, Indian Army, Ministry of Tribal
# Affairs) were checked across their FULL text (30,000-47,000+ characters
# each) and genuinely contained no state name anywhere -- extract_state()
# above was correctly returning None, not failing to match something that
# was there. But the consignee address section does list a city, even
# though the specific office name right next to it is masked by GeM with
# asterisks (e.g. "***********BANGALORE"). This maps known cities to their
# state as a further fallback once a direct state-name search comes up
# empty. Deliberately a curated list of state capitals, major metros (with
# common alternate spellings), and cantonment towns -- not exhaustive
# (India has thousands of cities/towns), but covers the pattern actually
# observed in this data: central bodies delivering to major
# cities/cantonments, not obscure small towns.
CITY_TO_STATE: dict[str, str] = {
    # Major metros (plus common alternate/older spellings)
    "Bangalore": "Karnataka", "Bengaluru": "Karnataka",
    "Mumbai": "Maharashtra", "Bombay": "Maharashtra",
    "Pune": "Maharashtra", "Nagpur": "Maharashtra",
    "Chennai": "Tamil Nadu", "Madras": "Tamil Nadu", "Coimbatore": "Tamil Nadu",
    "Kolkata": "West Bengal", "Calcutta": "West Bengal",
    "Hyderabad": "Telangana", "Secunderabad": "Telangana",
    "Ahmedabad": "Gujarat", "Surat": "Gujarat", "Vadodara": "Gujarat", "Rajkot": "Gujarat",
    "Jaipur": "Rajasthan", "Jodhpur": "Rajasthan", "Udaipur": "Rajasthan",
    "Lucknow": "Uttar Pradesh", "Kanpur": "Uttar Pradesh", "Agra": "Uttar Pradesh",
    "Varanasi": "Uttar Pradesh", "Meerut": "Uttar Pradesh", "Allahabad": "Uttar Pradesh",
    "Prayagraj": "Uttar Pradesh",
    "Patna": "Bihar", "Gaya": "Bihar",
    "Bhopal": "Madhya Pradesh", "Indore": "Madhya Pradesh", "Gwalior": "Madhya Pradesh", "Jabalpur": "Madhya Pradesh",
    "Raipur": "Chhattisgarh", "Bilaspur": "Chhattisgarh",
    "Bhubaneswar": "Odisha", "Cuttack": "Odisha",
    "Guwahati": "Assam",
    "Chandigarh": "Chandigarh",
    "Amritsar": "Punjab", "Ludhiana": "Punjab", "Jalandhar": "Punjab",
    "Shimla": "Himachal Pradesh",
    "Dehradun": "Uttarakhand",
    "Ranchi": "Jharkhand", "Jamshedpur": "Jharkhand",
    "Thiruvananthapuram": "Kerala", "Trivandrum": "Kerala", "Kochi": "Kerala", "Cochin": "Kerala",
    "Panaji": "Goa", "Panjim": "Goa",
    "Itanagar": "Arunachal Pradesh",
    "Imphal": "Manipur",
    "Shillong": "Meghalaya",
    "Aizawl": "Mizoram",
    "Kohima": "Nagaland",
    "Gangtok": "Sikkim",
    "Agartala": "Tripura",
    "Srinagar": "Jammu and Kashmir", "Jammu": "Jammu and Kashmir",
    "Leh": "Ladakh",
    "New Delhi": "Delhi", "Delhi": "Delhi",
    "Puducherry": "Puducherry", "Pondicherry": "Puducherry",
    "Port Blair": "Andaman and Nicobar Islands",
    # Common cantonment / military towns (relevant given how often Ministry
    # of Defence / Indian Army tenders appear in this data)
    "Ambala": "Haryana", "Panchkula": "Haryana", "Gurugram": "Haryana", "Gurgaon": "Haryana",
    "Pathankot": "Punjab",
    "Jalandhar Cantt": "Punjab",
    "Roorkee": "Uttarakhand",
    "Mhow": "Madhya Pradesh",
    "Babina": "Uttar Pradesh",
    "Ramgarh": "Jharkhand",
    "Danapur": "Bihar",
    "Wellington": "Tamil Nadu",
    "Belgaum": "Karnataka", "Belagavi": "Karnataka",
    "Kirkee": "Maharashtra", "Khadki": "Maharashtra",
    "Jhansi": "Uttar Pradesh",
    "Dahod": "Gujarat", "Junagadh": "Gujarat", "Bhuj": "Gujarat", "Porbandar": "Gujarat",
    "Chhota Udaipur": "Gujarat", "Valsad": "Gujarat",
}
_CITIES_BY_LENGTH = sorted(CITY_TO_STATE.keys(), key=len, reverse=True)


def extract_state_from_city(text: str | None) -> str | None:
    """Fallback for when no state name is found directly (see extract_state
    above) -- checks for a known city name instead. Deliberately run only
    AFTER extract_state comes up empty, never instead of it -- a direct
    state name is always a more reliable signal than inferring one from a
    city."""
    if not text:
        return None
    for city in _CITIES_BY_LENGTH:
        if re.search(r"\b" + re.escape(city) + r"\b", text, re.IGNORECASE):
            return CITY_TO_STATE[city]
    return None
