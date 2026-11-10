"""Shared SEC issuer-name matching: normalization, fund filters, overrides.

Used by Just Raised (Form D -> talent network) and PrivateMarks (N-PORT
holdings -> private companies). Improve it here and both get better.
"""

from .funds import fund_name_reason, is_fund_filing
from .location import edgar_region, parse_location, us_state_code
from .normalize import BRAND_WORDS, LEGAL_SUFFIXES, NormalizedName, name_variants, normalize
from .overrides import Overrides, load_overrides

__all__ = [
    "BRAND_WORDS",
    "LEGAL_SUFFIXES",
    "NormalizedName",
    "Overrides",
    "edgar_region",
    "fund_name_reason",
    "is_fund_filing",
    "load_overrides",
    "name_variants",
    "normalize",
    "parse_location",
    "us_state_code",
]
