"""Filters that say an SEC issuer is a fund or vehicle, not an operating company."""

from __future__ import annotations

import re

FUND_INDUSTRY_GROUPS: frozenset[str] = frozenset({"pooled investment fund"})
FUND_ENTITY_TYPES: frozenset[str] = frozenset({"limited partnership"})

# Whole-word markers. "holdings lp" is matched as a phrase so that an
# operating company called "X Holdings, Inc." survives.
_FUND_WORDS = re.compile(
    r"\b(fund|funds|capital|partners|ventures|spv|holdings,?\s+l\.?p\.?)\b",
    re.I,
)
# Series markers: "Fund II", "Growth III LLC". Single letters (I, V, X) are
# left alone because they are also brand names ("X Corp").
_ROMAN = re.compile(
    r"\b(ii|iii|iv|vi|vii|viii|ix|xi|xii|xiii|xiv|xv|xvi|xvii|xviii|xix|xx)\b",
    re.I,
)
_SERIES = re.compile(r"\b(a\s+series\s+of|series\s+[a-z0-9]+\s+of)\b", re.I)


def fund_name_reason(name: str) -> str | None:
    """Return why a name looks like a fund vehicle, or None if it does not."""
    if not name:
        return None
    m = _FUND_WORDS.search(name)
    if m:
        return f"name contains '{m.group(1).lower()}'"
    if _SERIES.search(name):
        return "name is a series of another entity"
    m = _ROMAN.search(name)
    if m:
        return f"name has series marker '{m.group(1).upper()}'"
    return None


def is_fund_filing(
    name: str,
    industry_group: str | None = None,
    entity_type: str | None = None,
    exemption_items: list[str] | None = None,
) -> str | None:
    """Return the reason a Form D should be dropped as a fund, or None."""
    if industry_group and industry_group.strip().lower() in FUND_INDUSTRY_GROUPS:
        return "industry group is Pooled Investment Fund"
    if entity_type and entity_type.strip().lower() in FUND_ENTITY_TYPES:
        return "entity type is Limited Partnership"
    # Investment Company Act 3(c)(1) / 3(c)(7) exclusions are only claimed by funds.
    if exemption_items and any(i.upper().startswith("3C") for i in exemption_items):
        return "claims an Investment Company Act 3(c) exclusion"
    return fund_name_reason(name)
