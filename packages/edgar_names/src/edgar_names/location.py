"""Turn free-text locations and EDGAR state codes into comparable keys."""

from __future__ import annotations

import unicodedata

US_STATES: dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "district of columbia": "DC",
    "washington dc": "DC", "washington d c": "DC", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI",
    "wyoming": "WY", "puerto rico": "PR",
}
_US_CODES = frozenset(US_STATES.values())

# Cities that appear without a state on job boards.
_CITY_STATE: dict[str, str] = {
    "san francisco": "CA", "sf": "CA", "los angeles": "CA", "palo alto": "CA",
    "menlo park": "CA", "mountain view": "CA", "san jose": "CA", "berkeley": "CA",
    "oakland": "CA", "san diego": "CA", "santa monica": "CA", "new york city": "NY",
    "nyc": "NY", "brooklyn": "NY", "manhattan": "NY", "boston": "MA", "cambridge": "MA",
    "seattle": "WA", "austin": "TX", "dallas": "TX", "houston": "TX", "miami": "FL",
    "chicago": "IL", "denver": "CO", "boulder": "CO", "atlanta": "GA",
    "bay area": "CA", "san francisco bay area": "CA", "new york city area": "NY",
    "greater new york city area": "NY", "los angeles area": "CA", "greater boston": "MA",
}

# EDGAR uses its own codes for places outside the US. Checked against
# sec.gov/submit-filings/filer-support-resources/edgar-state-country-codes.
EDGAR_COUNTRY: dict[str, str] = {
    "X0": "united kingdom", "I0": "france", "2M": "germany", "L3": "israel",
    "K7": "india", "U0": "singapore", "P7": "netherlands", "L2": "ireland",
    "M0": "japan", "F4": "china", "C3": "australia", "V8": "switzerland",
    "U3": "spain", "V7": "sweden", "L6": "italy", "D5": "brazil", "M5": "korea",
    "O5": "mexico", "F8": "colombia", "2N": "czech republic", "C1": "argentina", "F3": "chile",
    "R9": "poland", "S1": "portugal", "G7": "denmark", "H9": "finland", "Q8": "norway",
    "C0": "united arab emirates", "1H": "estonia", "Q5": "nigeria", "M3": "kenya",
    "K3": "hong kong", "F5": "taiwan", "C9": "belgium", "C4": "austria", "Z2": "serbia",
    **{c: "canada" for c in ("A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "B0", "Z4")},
}
_COUNTRY_ALIASES: dict[str, str] = {
    "uk": "united kingdom", "england": "united kingdom", "london": "united kingdom",
    "united kingdom": "united kingdom", "france": "france", "paris": "france",
    "germany": "germany", "berlin": "germany", "israel": "israel", "tel aviv": "israel",
    "india": "india", "bangalore": "india", "bengaluru": "india", "singapore": "singapore",
    "netherlands": "netherlands", "amsterdam": "netherlands", "ireland": "ireland",
    "dublin": "ireland", "japan": "japan", "tokyo": "japan", "china": "china",
    "australia": "australia", "sydney": "australia", "switzerland": "switzerland",
    "zurich": "switzerland", "spain": "spain", "sweden": "sweden", "stockholm": "sweden",
    "italy": "italy", "brazil": "brazil", "canada": "canada", "toronto": "canada",
    "vancouver": "canada", "montreal": "canada", "korea": "korea", "south korea": "korea",
    "seoul": "korea", "mexico": "mexico", "mexico city": "mexico", "colombia": "colombia",
    "bogota": "colombia", "czech republic": "czech republic", "prague": "czech republic",
    "argentina": "argentina", "buenos aires": "argentina", "chile": "chile", "poland": "poland",
    "warsaw": "poland", "portugal": "portugal", "lisbon": "portugal", "denmark": "denmark",
    "copenhagen": "denmark", "finland": "finland", "helsinki": "finland", "norway": "norway",
    "oslo": "norway", "uae": "united arab emirates", "united arab emirates": "united arab emirates",
    "dubai": "united arab emirates", "estonia": "estonia", "tallinn": "estonia",
    "nigeria": "nigeria", "lagos": "nigeria", "kenya": "kenya", "nairobi": "kenya",
    "hong kong": "hong kong", "taiwan": "taiwan", "taipei": "taiwan", "belgium": "belgium",
    "austria": "austria", "vienna": "austria", "serbia": "serbia", "belgrade": "serbia",
}


def _clean(text: str) -> str:
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return " ".join(text.lower().replace(".", " ").split())


def us_state_code(text: str | None) -> str | None:
    """'California' or 'CA' -> 'CA'; anything else -> None."""
    if not text:
        return None
    t = _clean(text)
    if t.upper() in _US_CODES:
        return t.upper()
    return US_STATES.get(t)


def parse_location(text: str | None) -> tuple[str | None, str | None]:
    """Return (region_key, city) for a free-text location like 'Costa Mesa, California'.

    region_key is a two-letter US state code or a lowercase country name, so it
    can be compared with :func:`edgar_region`.
    """
    if not text:
        return None, None
    if "&" in text or " and " in text.lower() or "/" in text:
        return None, None  # "London & San Francisco": more than one place, no single key
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        return None, None
    city = _clean(parts[0])
    for part in reversed(parts):
        code = us_state_code(part)
        if code:
            return code, city
        country = _COUNTRY_ALIASES.get(_clean(part))
        if country:
            return country, city
    if city in _CITY_STATE:
        return _CITY_STATE[city], city
    if city in _COUNTRY_ALIASES:
        return _COUNTRY_ALIASES[city], city
    return None, city


def edgar_region(state_or_country: str | None) -> str | None:
    """EDGAR stateOrCountry code -> the same key space as parse_location."""
    if not state_or_country:
        return None
    code = state_or_country.strip().upper()
    if code in _US_CODES:
        return code
    return EDGAR_COUNTRY.get(code)
