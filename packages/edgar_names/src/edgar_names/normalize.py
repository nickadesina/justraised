"""Issuer-name normalization shared by Just Raised and PrivateMarks.

The same function runs on both sides of a join (an SEC legal name and a
brand name from some other source) before any comparison. Two forms come
back:

* ``strict``: legal suffixes and brand-ish suffix words removed
  ("Modal Labs, Inc." -> "modal").
* ``brand``: legal suffixes removed but "labs", "ai" and "technologies"
  kept, because for some companies that word is the brand
  ("Scale AI, Inc." -> "scale ai").

Suffixes are stripped from the end of the name only, repeatedly, and never
down to an empty string. A word in the middle of a name is part of the name.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Removed from the end of the name in the strict form.
LEGAL_SUFFIXES: frozenset[str] = frozenset(
    {
        "inc",
        "incorporated",
        "corp",
        "corporation",
        "co",
        "llc",
        "ltd",
        "limited",
        "holdings",
        "labs",
        "technologies",
        "technology",
        "ai",
        "io",
    }
)

# Kept in the brand form even though they are in LEGAL_SUFFIXES.
BRAND_WORDS: frozenset[str] = frozenset({"labs", "ai", "technologies"})

# "pbc" and "plc" are legal forms that show up on SEC filings but never in a
# brand name; stripping them is the same rule as "inc".
_EXTRA_LEGAL = frozenset({"pbc", "plc", "lp", "llp", "sa", "gmbh", "bv", "ag", "pte"})

_DBA_SPLIT = re.compile(r"\b(?:d\s*/\s*b\s*/\s*a|dba|doing business as|f\s*/\s*k\s*/\s*a|fka)\b", re.I)
_APOSTROPHES = re.compile(r"['’`]")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class NormalizedName:
    raw: str
    strict: str
    brand: str

    @property
    def strict_tokens(self) -> tuple[str, ...]:
        return tuple(self.strict.split())


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _tokens(text: str) -> list[str]:
    text = _fold(text).lower()
    text = text.replace("&", " and ")
    text = _APOSTROPHES.sub("", text)
    text = _NON_ALNUM.sub(" ", text)
    return text.split()


def _strip_suffixes(tokens: list[str], removable: frozenset[str]) -> list[str]:
    out = list(tokens)
    while len(out) > 1 and out[-1] in removable:
        out.pop()
    return out


def _strip_leading_the(tokens: list[str]) -> list[str]:
    if len(tokens) > 1 and tokens[0] == "the":
        return tokens[1:]
    return tokens


def normalize(name: str) -> NormalizedName:
    """Normalize one name into its strict and brand forms."""
    tokens = _strip_leading_the(_tokens(name or ""))
    strict = _strip_suffixes(tokens, LEGAL_SUFFIXES | _EXTRA_LEGAL)
    brand = _strip_suffixes(tokens, (LEGAL_SUFFIXES - BRAND_WORDS) | _EXTRA_LEGAL)
    return NormalizedName(raw=name, strict=" ".join(strict), brand=" ".join(brand))


def name_variants(name: str) -> list[NormalizedName]:
    """Normalize a name and any d/b/a or f/k/a parts of it.

    "Acme Holdings, Inc. d/b/a Rocket" yields both "acme" and "rocket".
    """
    parts = [p.strip(" ,;()") for p in _DBA_SPLIT.split(name or "")]
    seen: set[str] = set()
    out: list[NormalizedName] = []
    for part in [name, *parts] if len(parts) > 1 else [name]:
        if not part:
            continue
        n = normalize(part)
        if n.strict and n.strict not in seen:
            seen.add(n.strict)
            out.append(n)
    if len(parts) > 1:
        # Drop the combined form; the split parts are the real names.
        out = [n for n in out if n.raw != name] or out
    return out
